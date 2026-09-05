"""Synthetic device, never connected to a port. Used by the UI and tests."""
import copy
from .messages import MessageBox, BROADCAST
import time
from google.protobuf import json_format, message_factory
from .schema import DEFINITIONS, as_dict


class DemoDevice:
    demo = True
    node_id = "!de000001"
    port = "SIMULADOR"

    def __init__(self):
        self.messages = MessageBox()
        self.message_packets = 0
        self.entries = {}
        self.writes = 0
        self.active = True
        for key, definition in DEFINITIONS.items():
            self.entries[key] = message_factory.GetMessageClass(definition["descriptor"])() if definition["descriptor"] else {"text": ""}
        fixtures = {
            "owner": {"id": self.node_id, "long_name": "Estação de demonstração", "short_name": "DEMO", "hw_model": "T_DECK"},
            "config.device": {"role": "CLIENT", "tzdef": "BRT3", "node_info_broadcast_secs": 10800},
            "config.lora": {"use_preset": True, "modem_preset": "LONG_FAST", "region": "ANZ", "hop_limit": 3, "tx_enabled": True, "tx_power": 20, "channel_num": 20},
            "config.network": {"wifi_enabled": True, "wifi_ssid": "Rede de exemplo", "wifi_psk": "demo-password"},
            "config.bluetooth": {"enabled": True, "fixed_pin": 123456},
            "module.mqtt": {"enabled": False, "address": "mqtt.example.org", "password": "demo-only"},
            "module.telemetry": {"device_update_interval": 900, "environment_measurement_enabled": True},
            "channel.0": {"role": "PRIMARY", "settings": {"name": "", "psk": "AQ=="}},
            "channel.1": {"index": 1, "role": "SECONDARY", "settings": {"name": "Equipe", "psk": "AQ=="}},
        }
        for i in range(2, 8):
            fixtures[f"channel.{i}"] = {"index": i, "role": "DISABLED"}
        for key, fixture in fixtures.items():
            json_format.ParseDict(fixture, self.entries[key])
        self.entries["canned_text"] = {"text": "Olá!|Cheguei bem.|Preciso de ajuda."}
        self.entries["ringtone"] = {"text": "demo:d=4,o=5,b=100:c,e,g"}

    def connected(self):
        return self.active

    def read(self, key):
        return copy.deepcopy(self.entries[key])

    def write(self, key, value):
        self.writes += 1
        self.entries[key] = copy.deepcopy(value)
        return self.read(key)

    def summary(self):
        owner = as_dict(self.entries["owner"])
        return {"id": self.node_id, "name": owner["long_name"], "short_name": owner["short_name"], "port": self.port,
                "metadata": {"hw_model": "T_DECK", "firmware_version": "Simulado · 2.7", "role": "CLIENT"},
                "metrics": {"batteryLevel": 84, "voltage": 4.06, "uptimeSeconds": 14700, "channelUtilization": 2.4, "airUtilTx": 0.3},
                "position": {}, "write_packets": 0, "read_packets": 0, "simulated_writes": self.writes}

    def nodes(self):
        return [{"id": self.node_id if i == 0 else f"!de0000{i+1:02x}",
                 "name": name, "short_name": name[:4], "hardware": "T_DECK" if i == 0 else "HELTEC_V3",
                 "last_heard": int(time.time()) - i * 90, "snr": None if i == 0 else 8 - i,
                 "hops": i % 3, "via_mqtt": i > 3, "local": i == 0}
                for i, name in enumerate(["Estação de demonstração", "Base norte", "Ponto da serra", "Equipe trilha", "Gateway central", "Estação leste"])]

    def close(self):
        self.active = False

    def send_text(self, text, destination, channel, box, item_id):
        self.message_packets += 1
        box.update(item_id, status='simulated', packet_id=100000 + self.message_packets)

    def simulate_incoming(self):
        sequence = len(self.messages.snapshot())
        self.messages.receive({'from': 0xde000002, 'to': BROADCAST, 'channel': 0,
            'id': 200000 + sequence, 'decoded': {'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Olá, equipe! Mensagem de canal simulada.'}}, self.node_id)
        self.messages.receive({'from': 0xde000003, 'to': int(self.node_id[1:], 16), 'channel': 0,
            'id': 300000 + sequence, 'decoded': {'portnum': 'TEXT_MESSAGE_APP',
            'text': 'Mensagem direta de demonstração.'}}, self.node_id)
