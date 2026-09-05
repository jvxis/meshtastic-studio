import copy
import time
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from meshtastic.protobuf import mesh_pb2, admin_pb2, portnums_pb2
from server.app import Manager, create_app
from server.device import GuardedSerial, GuardedTCP, RealDevice, signature, read_request, write_command
from server.schema import MASK, DEFINITIONS, prepare, as_dict


@pytest.fixture
def client():
    manager = Manager(allow_writes=False)
    with TestClient(create_app(manager), base_url="http://127.0.0.1") as cli:
        cli.headers["x-mesh-token"] = cli.get("/api/session").json()["token"]
        cli.post("/api/demo", json={}).raise_for_status()
        yield cli, manager


def preview_for(cli, key, update):
    entry = cli.get("/api/state").json()["sections"][key]
    values = entry["values"]
    values.update(update)
    return cli.post("/api/preview", json={"section": key, "revision": entry["revision"], "values": values})


def test_secrets_are_redacted_everywhere(client):
    cli, _ = client
    data = cli.get("/api/session").text
    assert "demo-password" not in data and "demo-only" not in data
    assert MASK in data
    state = cli.get("/api/state").json()
    assert state["sections"]["config.bluetooth"]["values"]["fixed_pin"] == MASK
    assert state["sections"]["channel.0"]["values"]["settings"]["psk"] == MASK


def test_edit_preview_is_readonly_and_simulated_apply_preserves_secret(client):
    cli, manager = client
    preview = preview_for(cli, "config.network", {"wifi_ssid": "Minha rede"}).json()
    assert manager.device.writes == 0
    assert [c["path"] for c in preview["changes"]] == ["wifi_ssid"]
    result = cli.post("/api/apply", json={"token": preview["token"], "confirmation": preview["confirmation"]})
    assert result.status_code == 200
    assert manager.device.writes == 1
    assert manager.device.entries["config.network"].wifi_psk == "demo-password"
    assert result.json()["sections"]["config.network"]["values"]["wifi_ssid"] == "Minha rede"


def test_real_mode_cannot_apply_even_with_valid_preview(client):
    cli, manager = client
    manager.device.demo = False
    preview = preview_for(cli, "config.network", {"wifi_ssid": "Never send"}).json()
    assert not preview["can_apply"]
    result = cli.post("/api/apply", json={"token": preview["token"], "confirmation": preview["confirmation"]})
    assert result.status_code == 403
    assert manager.device.writes == 0


def test_server_flag_enables_only_reviewed_writes_on_fake_device(client):
    cli, manager = client
    manager.device.demo = False
    manager.allow_writes = True
    result = cli.post("/api/apply", json={"token": "invented", "confirmation": "APLICAR !de000001"})
    assert result.status_code == 409 and manager.device.writes == 0
    preview = preview_for(cli, "config.lora", {"hop_limit": 4}).json()
    result = cli.post("/api/apply", json={"token": preview["token"], "confirmation": preview["confirmation"]})
    assert result.status_code == 200 and manager.device.writes == 1


def test_wrong_confirmation_and_token_replay(client):
    cli, manager = client
    preview = preview_for(cli, "config.lora", {"hop_limit": 4}).json()
    bad = cli.post("/api/apply", json={"token": preview["token"], "confirmation": "APLICAR !other"})
    assert bad.status_code == 400 and manager.device.writes == 0
    good = {"token": preview["token"], "confirmation": preview["confirmation"]}
    assert cli.post("/api/apply", json=good).status_code == 200
    assert cli.post("/api/apply", json=good).status_code == 409
    assert manager.device.writes == 1


def test_stale_read_prevents_write_and_expires_token(client):
    cli, manager = client
    preview = preview_for(cli, "config.lora", {"hop_limit": 4}).json()
    manager.device.entries["config.lora"].hop_limit = 5
    result = cli.post("/api/apply", json={"token": preview["token"], "confirmation": preview["confirmation"]})
    assert result.status_code == 409 and manager.device.writes == 0


def test_preview_expiration_and_disconnect(client):
    cli, manager = client
    p = preview_for(cli, "config.lora", {"hop_limit": 4}).json()
    manager.previews[p["token"]]["expires"] = time.monotonic() - 1
    assert cli.post("/api/apply", json={"token": p["token"], "confirmation": p["confirmation"]}).status_code == 409
    cli.post("/api/disconnect", json={})
    cli.post("/api/demo", json={})
    assert cli.post("/api/apply", json={"token": p["token"], "confirmation": p["confirmation"]}).status_code == 409


def test_failed_verification_never_reports_success(client):
    cli, manager = client
    p = preview_for(cli, "config.lora", {"hop_limit": 4}).json()
    manager.device.write = Mock(return_value=copy.deepcopy(manager.device.entries["config.lora"]))
    result = cli.post("/api/apply", json={"token": p["token"], "confirmation": p["confirmation"]})
    assert result.status_code == 502
    assert "config.lora" not in manager.device.entries
    assert not manager.previews


@pytest.mark.parametrize("update", [{"unknown": 1}, {"hop_limit": -1}, {"hop_limit": 1.2},
                                    {"hop_limit": True}, {"region": "UNKNOWN_VALUE"}, {"tx_enabled": "false"}])
def test_invalid_protocol_values_rejected(client, update):
    cli, manager = client
    assert preview_for(cli, "config.lora", update).status_code == 400
    assert manager.device.writes == 0


def test_secret_change_is_redacted_in_diff(client):
    cli, _ = client
    result = preview_for(cli, "config.network", {"wifi_psk": "brand-new-secret"})
    assert result.status_code == 200
    assert "brand-new-secret" not in result.text and "demo-password" not in result.text
    assert "protegido" in result.text


def test_channel_keys_and_indices_are_validated(client):
    cli, _ = client
    assert preview_for(cli, "channel.0", {"index": 1}).status_code == 400
    assert preview_for(cli, "channel.0", {"settings": {"name": "bad", "psk": "not@base64"}}).status_code == 400
    assert preview_for(cli, "channel.0", {"settings": {"name": "bad", "psk": "YWJj"}}).status_code == 400
    assert preview_for(cli, "channel.0", {"role": "DISABLED"}).status_code == 400
    assert preview_for(cli, "channel.1", {"role": "PRIMARY"}).status_code == 400


def test_owner_validation_and_immutable_fields(client):
    cli, _ = client
    assert preview_for(cli, "owner", {"short_name": "TOO_LONG"}).status_code == 400
    assert preview_for(cli, "owner", {"public_key": "AQ=="}).status_code == 400


def test_nanopb_limits_match_embedded_storage(client):
    cli, manager = client
    assert preview_for(cli, "config.lora", {"ignore_incoming": [1, 2, 3, 4]}).status_code == 400
    assert preview_for(cli, "config.lora", {"tx_power": 128}).status_code == 400
    assert preview_for(cli, "config.network", {"wifi_ssid": "x" * 100}).status_code == 400
    assert preview_for(cli, "owner", {"short_name": "😀😀"}).status_code == 400
    assert manager.device.writes == 0


def test_request_errors_do_not_echo_secrets(client):
    cli, _ = client
    response = cli.post("/api/preview", json={"section": "config.network", "values": {"wifi_psk": "never-echo-me"}})
    assert response.status_code == 422
    assert "never-echo-me" not in response.text


def test_all_schema_groups_have_commands_and_queries(client):
    cli, manager = client
    for key in DEFINITIONS:
        request, response = read_request(key)
        assert request.WhichOneof("payload_variant").startswith("get_")
        assert response.endswith("response")
        command = write_command(key, manager.device.entries[key])
        assert command.WhichOneof("payload_variant")
    state = cli.get("/api/state").json()
    assert "module.statusmessage" in state["sections"] and "module.tak" in state["sections"]


def test_csrf_origin_and_host_protection(client):
    cli, manager = client
    assert cli.post("/api/disconnect", json={}, headers={"x-mesh-token": "bad"}).status_code == 403
    assert cli.get("/api/session", headers={"Origin": "https://evil.example"}).status_code == 403
    assert cli.get("/api/state", headers={"Host": "evil.example"}).status_code == 400
    assert cli.get("/api/state", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert manager.device.connected()


def make_guard(guard_type=GuardedSerial):
    guard = object.__new__(guard_type)
    guard.myInfo = mesh_pb2.MyNodeInfo(my_node_num=123)
    guard.write_grants = {}
    return guard


def packet(command, dest=123):
    value = mesh_pb2.ToRadio()
    value.packet.to = dest
    value.packet.decoded.portnum = portnums_pb2.PortNum.ADMIN_APP
    value.packet.decoded.payload = command.SerializeToString()
    return value


@pytest.mark.parametrize("guard_type", [GuardedSerial, GuardedTCP])
def test_transport_guard_rejects_mutations_and_remote_commands(guard_type):
    guard = make_guard(guard_type)
    assert guard.inspect_packet(mesh_pb2.ToRadio(want_config_id=123)) is False
    assert guard.inspect_packet(packet(admin_pb2.AdminMessage(get_owner_request=True))) is False
    for cmd in [admin_pb2.AdminMessage(reboot_seconds=1), admin_pb2.AdminMessage(factory_reset_device=1),
                admin_pb2.AdminMessage(set_time_only=12), admin_pb2.AdminMessage(set_ringtone_message="test")]:
        with pytest.raises(PermissionError):
            guard.inspect_packet(packet(cmd))
    with pytest.raises(PermissionError):
        guard.inspect_packet(packet(admin_pb2.AdminMessage(get_owner_request=True), dest=456))
    forbidden = packet(admin_pb2.AdminMessage(get_owner_request=True))
    forbidden.packet.decoded.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
    with pytest.raises(PermissionError):
        guard.inspect_packet(forbidden)


@pytest.mark.parametrize("guard_type", [GuardedSerial, GuardedTCP])
def test_transport_grant_is_exact_and_expires(guard_type):
    guard = make_guard(guard_type)
    approved = admin_pb2.AdminMessage(set_ringtone_message="approved")
    guard.write_grants[signature(approved)] = time.monotonic() + 10
    assert guard.inspect_packet(packet(approved)) is True
    with pytest.raises(PermissionError):
        guard.inspect_packet(packet(admin_pb2.AdminMessage(set_ringtone_message="different")))
    guard.write_grants[signature(approved)] = time.monotonic() - 1
    with pytest.raises(PermissionError):
        guard.inspect_packet(packet(approved))


def test_read_retries_once_on_timeout_without_writing():
    from meshtastic.protobuf import config_pb2
    device = object.__new__(RealDevice)
    device.entries = {}
    config = config_pb2.Config()
    config.lora.hop_limit = 3
    device.exchange = Mock(side_effect=[TimeoutError(), config])
    assert device.read("config.lora").hop_limit == 3
    assert device.exchange.call_count == 2
    for call in device.exchange.call_args_list:
        assert call.args[0].WhichOneof("payload_variant") == "get_config_request"


def test_unresponsive_read_has_bounded_retries():
    device = object.__new__(RealDevice)
    device.entries = {}
    device.exchange = Mock(side_effect=TimeoutError())
    with pytest.raises(TimeoutError):
        device.read("ui")
    assert device.exchange.call_count == 2


def test_unknown_protobuf_fields_survive_edit(client):
    _, manager = client
    original = copy.deepcopy(manager.device.entries["config.lora"])
    # Unknown field 999, varint 7; an older client must preserve firmware extensions.
    original.MergeFromString(bytes([0xB8, 0x3E, 0x07]))
    values = as_dict(original)
    values["hop_limit"] = 4
    candidate, _ = prepare("config.lora", values, original)
    assert bytes([0xB8, 0x3E, 0x07]) in candidate.SerializeToString()


def test_loopback_ui_headers(client):
    cli, _ = client
    response = cli.get("/")
    assert response.status_code == 200 and "Mesh Studio" in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"
