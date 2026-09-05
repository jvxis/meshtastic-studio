"""TCP validation and a framed loopback radio; no physical radio is used."""
import socket
import threading
import time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from meshtastic.protobuf import mesh_pb2, admin_pb2, portnums_pb2, channel_pb2, config_pb2

from server.app import ConnectBody, Manager, create_app
from server.device import DeviceSession, GuardedTCP, signature


@pytest.mark.parametrize('host', ['192.168.1.50', 'radio.local', '::1', 'fd00::123'])
def test_valid_tcp_hosts(host):
    assert ConnectBody(transport='tcp', host=host).host == host


@pytest.mark.parametrize('body', [
    {'host': ''}, {'host': 'http://radio.local'}, {'host': 'radio.local:4403'},
    {'host': 'radio/name'}, {'host': 'a b'}, {'host': '999.1.1.1'},
    {'host': '0.0.0.0'}, {'host': '224.0.0.1'}, {'host': 'radio', 'tcp_port': 0},
    {'host': 'radio', 'tcp_port': 65536}, {'host': 'radio', 'tcp_port': True},
    {'host': 'radio', 'tcp_port': 4403.5}, {'host': 'radio', 'port': 'COM9'},
])
def test_invalid_endpoint_never_opens_a_transport(body, monkeypatch):
    factory = Mock()
    monkeypatch.setattr('server.app.DeviceSession', factory)
    with TestClient(create_app(), base_url='http://127.0.0.1') as c:
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        assert c.post('/api/connect', json={'transport': 'tcp', **body}).status_code == 422
    factory.assert_not_called()


def test_socket_failure_does_not_reconnect_or_hide_partial_send(monkeypatch):
    guard = GuardedTCP('radio.local', connectNow=False)
    guard.socket = Mock()
    connect = Mock()
    monkeypatch.setattr('server.device.socket.create_connection', connect)
    guard.socket.sendall.side_effect = OSError('connection lost')
    with pytest.raises(OSError):
        guard._writeBytes(b'frame')
    assert guard.socket.sendall.call_count == 1
    guard.socket.recv.return_value = b''
    assert guard._readBytes(1) == b'' and guard._wantExit
    guard.close()
    guard.close()
    connect.assert_not_called()


def test_tcp_write_grant_is_consumed_without_queue_wait():
    guard = GuardedTCP('radio.local', connectNow=False)
    guard.socket = Mock()
    guard.myInfo = mesh_pb2.MyNodeInfo(my_node_num=123)
    guard.queueStatus = mesh_pb2.QueueStatus(free=0)
    command = admin_pb2.AdminMessage(set_ringtone_message='approved')
    packet = mesh_pb2.ToRadio()
    packet.packet.to = 123
    packet.packet.decoded.portnum = portnums_pb2.PortNum.ADMIN_APP
    packet.packet.decoded.payload = command.SerializeToString()
    guard.write_grants[signature(command)] = time.monotonic() + 20
    guard._sendToRadio(packet)
    with pytest.raises(PermissionError):
        guard._sendToRadio(packet)
    assert guard.write_packets == 1 and guard.socket.sendall.call_count == 1
    assert not guard.queue
    guard.close()


def test_tcp_connect_timeout_releases_resources(monkeypatch):
    connect = Mock(side_effect=TimeoutError('unreachable'))
    monkeypatch.setattr('server.device.socket.create_connection', connect)
    with pytest.raises(TimeoutError):
        DeviceSession(host='radio.local', tcp_port=4404)
    connect.assert_called_once_with(('radio.local', 4404), timeout=5)


def test_real_tcp_framing_handshake_and_release():
    received, failures = [], []
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(5)

    def radio():
        try:
            with listener.accept()[0] as peer:
                peer.settimeout(5)
                buffer = b''
                while data := peer.recv(4096):
                    buffer += data
                    while True:
                        start = buffer.find(b'\x94\xc3')
                        if start < 0:
                            buffer = buffer[-1:]
                            break
                        buffer = buffer[start:]
                        if len(buffer) < 4:
                            break
                        length = int.from_bytes(buffer[2:4], 'big')
                        if len(buffer) < length + 4:
                            break
                        request = mesh_pb2.ToRadio.FromString(buffer[4:4+length])
                        buffer = buffer[4+length:]
                        kind = request.WhichOneof('payload_variant')
                        received.append(kind)
                        if kind == 'want_config_id':
                            replies = [mesh_pb2.FromRadio(my_info=mesh_pb2.MyNodeInfo(my_node_num=123)),
                                       mesh_pb2.FromRadio(metadata=mesh_pb2.DeviceMetadata(firmware_version='test')),
                                       mesh_pb2.FromRadio(node_info=mesh_pb2.NodeInfo(num=123, user=mesh_pb2.User(id='!0000007b', long_name='Test radio'))),
                                       mesh_pb2.FromRadio(config=config_pb2.Config(lora=config_pb2.Config.LoRaConfig(hop_limit=3))),
                                       mesh_pb2.FromRadio(channel=channel_pb2.Channel(index=0, role=channel_pb2.Channel.PRIMARY)),
                                       mesh_pb2.FromRadio(config_complete_id=request.want_config_id)]
                            for reply in replies:
                                raw = reply.SerializeToString()
                                frame = b'\x94\xc3' + len(raw).to_bytes(2, 'big') + raw
                                peer.sendall(frame[:3])
                                peer.sendall(frame[3:])
                        elif kind == 'disconnect':
                            return
        except Exception as error:
            failures.append(error)

    worker = threading.Thread(target=radio, daemon=True)
    worker.start()
    try:
        session = DeviceSession(host='127.0.0.1', tcp_port=listener.getsockname()[1])
        assert session.node_id == '!0000007b' and not session.connected()
        assert session.summary()['transport'] == 'tcp'
        assert session.write_packets == session.message_packets == 0
        worker.join(5)
        assert not worker.is_alive() and not failures
        assert 'want_config_id' in received and 'disconnect' in received
        assert 'packet' not in received
    finally:
        listener.close()
        worker.join(5)
