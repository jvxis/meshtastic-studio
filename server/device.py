"""Local-only adapter with a packet-level allowlist and explicit write grants."""
import copy
import hashlib
import threading
import time
from google.protobuf import json_format
from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import admin_pb2, mesh_pb2, portnums_pb2
from .schema import DEFINITIONS, OWNER_FIELDS, as_dict

READS = {"get_channel_request", "get_owner_request", "get_config_request",
         "get_module_config_request", "get_canned_message_module_messages_request",
         "get_device_metadata_request", "get_ringtone_request", "get_ui_config_request"}
WRITES = {"set_owner", "set_channel", "set_config", "set_module_config",
          "set_canned_message_module_messages", "set_ringtone_message", "store_ui_config"}


def signature(command):
    clean = admin_pb2.AdminMessage()
    clean.CopyFrom(command)
    clean.ClearField("session_passkey")
    return hashlib.sha256(clean.SerializeToString(deterministic=True)).hexdigest()


class GuardedSerial(SerialInterface):
    def __init__(self, *args, **kwargs):
        self.write_grants = {}
        self.write_packets = 0
        self.read_packets = 0
        super().__init__(*args, **kwargs)

    def inspect_packet(self, packet):
        kind = packet.WhichOneof("payload_variant")
        if kind in {"want_config_id", "heartbeat", "disconnect"}:
            return False
        if kind != "packet" or packet.packet.decoded.portnum != portnums_pb2.PortNum.ADMIN_APP:
            raise PermissionError("Pacote bloqueado: apenas consultas administrativas locais são permitidas.")
        local_num = self.myInfo.my_node_num if self.myInfo else None
        if local_num is None or packet.packet.to not in (0, local_num):
            raise PermissionError("Comandos para nós remotos estão bloqueados.")
        command = admin_pb2.AdminMessage.FromString(packet.packet.decoded.payload)
        action = command.WhichOneof("payload_variant")
        if action in READS:
            return False
        if action in WRITES and self.write_grants.get(signature(command), 0) > time.monotonic():
            return True
        raise PermissionError("Gravação bloqueada pela proteção da porta serial.")

    def _sendToRadio(self, packet):
        self.inspect_packet(packet)  # Reject before a forbidden packet can enter the retry queue.
        return super()._sendToRadio(packet)

    def _sendToRadioImpl(self, packet):
        mutating = self.inspect_packet(packet)
        result = super()._sendToRadioImpl(packet)
        if mutating:
            self.write_packets += 1
        else:
            self.read_packets += 1
        return result


def read_request(key):
    request = admin_pb2.AdminMessage()
    if key.startswith("config."):
        request.get_config_request = admin_pb2.AdminMessage.ConfigType.Value(key.split(".")[1].upper() + "_CONFIG")
        expected = "get_config_response"
    elif key.startswith("module."):
        from meshtastic.protobuf import localonly_pb2
        name = key.split(".")[1]
        request.get_module_config_request = localonly_pb2.LocalModuleConfig.DESCRIPTOR.fields_by_name[name].index
        expected = "get_module_config_response"
    elif key.startswith("channel."):
        request.get_channel_request = int(key.split(".")[1]) + 1
        expected = "get_channel_response"
    else:
        request_name, expected = {
            "owner": ("get_owner_request", "get_owner_response"),
            "ui": ("get_ui_config_request", "get_ui_config_response"),
            "canned_text": ("get_canned_message_module_messages_request", "get_canned_message_module_messages_response"),
            "ringtone": ("get_ringtone_request", "get_ringtone_response"),
        }[key]
        setattr(request, request_name, True)
    return request, expected


def write_command(key, value):
    command = admin_pb2.AdminMessage()
    if key.startswith("config."):
        getattr(command.set_config, key.split(".")[1]).CopyFrom(value)
    elif key.startswith("module."):
        getattr(command.set_module_config, key.split(".")[1]).CopyFrom(value)
    elif key.startswith("channel."):
        command.set_channel.CopyFrom(value)
    elif key == "owner":
        command.set_owner.CopyFrom(value)
        for field in value.DESCRIPTOR.fields:
            if field.name not in OWNER_FIELDS:
                command.set_owner.ClearField(field.name)
    elif key == "ui":
        command.store_ui_config.CopyFrom(value)
    elif key == "canned_text":
        command.set_canned_message_module_messages = value["text"]
    elif key == "ringtone":
        command.set_ringtone_message = value["text"]
    else:
        raise ValueError("Configuração não suportada.")
    return command


class RealDevice:
    demo = False

    def __init__(self, port):
        self.port = port
        self.iface = GuardedSerial(devPath=port, timeout=40)
        self.node_num = self.iface.myInfo.my_node_num
        self.node_id = f"!{self.node_num:08x}"
        self.metadata = as_dict(self.iface.metadata) if self.iface.metadata else {}
        self.entries = {}
        for prefix, config in [("config", self.iface.localNode.localConfig), ("module", self.iface.localNode.moduleConfig)]:
            for f, value in config.ListFields():
                if f.message_type:
                    self.entries[f"{prefix}.{f.name}"] = copy.deepcopy(value)
        for ch in self.iface.localNode.channels or []:
            self.entries[f"channel.{ch.index}"] = copy.deepcopy(ch)
        local = (self.iface.nodesByNum or {}).get(self.iface.myInfo.my_node_num, {})
        if local.get("user"):
            self.entries["owner"] = json_format.ParseDict(local["user"], mesh_pb2.User(), ignore_unknown_fields=True)

    def connected(self):
        return bool(self.iface.isConnected.is_set() and not self.iface._wantExit
                    and self.iface.myInfo and self.iface.myInfo.my_node_num == self.node_num)

    def exchange(self, command, expected=None, timeout=10):
        if not self.connected():
            raise RuntimeError("A conexão com o dispositivo foi interrompida.")
        done = threading.Event()
        outcome = {}

        def response(packet):
            decoded = packet.get("decoded", {})
            routing = decoded.get("routing")
            if routing is not None:
                reason = routing.get("errorReason", "NONE")
                if reason != "NONE":
                    outcome["error"] = f"O dispositivo recusou a operação: {reason}"
                elif expected:
                    outcome["error"] = "O dispositivo confirmou o pacote, mas não retornou a configuração."
                else:
                    outcome["ack"] = True
            else:
                raw = decoded.get("admin", {}).get("raw")
                if raw is not None and expected and raw.WhichOneof("payload_variant") == expected:
                    outcome["value"] = copy.deepcopy(getattr(raw, expected))
                else:
                    outcome["error"] = "Resposta administrativa inesperada."
            done.set()

        local = self.iface.localNode
        session = self.iface._getOrCreateByNum(local.nodeNum).get("adminSessionPassKey")
        if session:
            command.session_passkey = session
        packet = self.iface.sendData(command, destinationId=local.nodeNum,
            portNum=portnums_pb2.PortNum.ADMIN_APP, wantAck=True, wantResponse=bool(expected),
            onResponse=response, onResponseAckPermitted=not bool(expected),
            channelIndex=local._getAdminChannelIndex(), pkiEncrypted=True)
        try:
            if not done.wait(timeout):
                raise TimeoutError("O dispositivo não respondeu a tempo. A configuração pode não ser suportada neste firmware.")
            if outcome.get("error"):
                raise RuntimeError(outcome["error"])
            return outcome.get("value")
        finally:
            if packet:
                self.iface.responseHandlers.pop(packet.id, None)
                self.iface.queue.pop(packet.id, None)

    def read(self, key):
        request, expected = read_request(key)
        for attempt in range(2):
            try:
                value = self.exchange(request, expected)
                break
            except TimeoutError:
                if attempt:
                    raise
                time.sleep(0.3)  # Only reads may be repeated, never a write command.
        if key.startswith(("config.", "module.")):
            field = key.split(".")[1]
            if not value.HasField(field):
                raise RuntimeError("O firmware não retornou esta seção.")
            value = copy.deepcopy(getattr(value, field))
        elif key.startswith("channel.") and value.index != int(key.split(".")[1]):
            raise RuntimeError("O dispositivo retornou outro canal.")
        elif key in ("ringtone", "canned_text"):
            value = {"text": value}
        self.entries[key] = value
        return value

    def write(self, key, value):
        if not self.iface._getOrCreateByNum(self.iface.localNode.nodeNum).get("adminSessionPassKey"):
            self.exchange(admin_pb2.AdminMessage(get_config_request=admin_pb2.AdminMessage.SESSIONKEY_CONFIG), "get_config_response")
        command = write_command(key, value)
        sig = signature(command)
        self.iface.write_grants[sig] = time.monotonic() + 20
        try:
            self.exchange(command)
        finally:
            self.iface.write_grants.pop(sig, None)
        # ACK only confirms delivery. Verify persisted fields using an independent read.
        return self.read(key)

    def summary(self):
        local = (self.iface.nodesByNum or {}).get(self.node_num, {})
        owner = as_dict(self.entries["owner"]) if "owner" in self.entries else {}
        return {"id": self.node_id, "name": owner.get("long_name", self.node_id),
                "short_name": owner.get("short_name", ""), "port": self.port,
                "metadata": self.metadata,
                "metrics": copy.deepcopy(local.get("deviceMetrics", {})),
                "position": copy.deepcopy(local.get("position", {})),
                "write_packets": self.iface.write_packets, "read_packets": self.iface.read_packets}

    def nodes(self):
        result = []
        for node in list((self.iface.nodesByNum or {}).values()):
            user = node.get("user", {})
            result.append({"id": user.get("id", f"!{node['num']:08x}"),
                           "name": user.get("longName", "Sem identificação"),
                           "short_name": user.get("shortName", ""), "hardware": user.get("hwModel", "—"),
                           "last_heard": node.get("lastHeard"), "snr": node.get("snr"),
                           "hops": node.get("hopsAway"), "via_mqtt": node.get("viaMqtt", False),
                           "local": node["num"] == self.node_num})
        return result

    def close(self):
        self.iface.write_grants.clear()
        self.iface.close()
