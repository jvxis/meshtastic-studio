"""Bounded, in-memory text history. No device configuration or disk persistence."""
import copy
from datetime import datetime, timezone
import secrets
import threading

MAX_TEXT_BYTES = 233
BROADCAST = 0xFFFFFFFF


def now():
    return datetime.now(timezone.utc).isoformat()


class MessageBox:
    def __init__(self):
        self.lock = threading.RLock()
        self.items = []

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.items)

    def outgoing(self, text, destination, channel, local_id):
        with self.lock:
            item = {"id": secrets.token_hex(12), "direction": "out", "text": text,
                    "sender": local_id, "destination": destination, "channel": channel,
                    "conversation": f"direct:{destination}" if destination else f"channel:{channel}",
                    "time": now(), "status": "preparing", "packet_id": None, "via_mqtt": False}
            self.items.append(item)
            self.items = self.items[-300:]
            return item["id"]

    def update(self, item_id, **values):
        with self.lock:
            for item in self.items:
                if item["id"] == item_id:
                    item.update(values)
                    if values.get('packet_id'):
                        self.items = [m for m in self.items if m['id'] == item_id or
                                      (m['sender'], m['packet_id']) != (item['sender'], item['packet_id'])]
                    return

    def receive(self, packet, local_id):
        decoded = packet.get("decoded", {})
        source, dest = packet.get("from"), packet.get("to")
        if not isinstance(source, int) or not isinstance(dest, int):
            return
        local_num = int(local_id[1:], 16)
        with self.lock:
            if decoded.get("portnum") in ("ROUTING_APP", 5) and dest == local_num:
                request = decoded.get("requestId")
                reason = decoded.get("routing", {}).get("errorReason", "NONE")
                for item in self.items:
                    if item["direction"] == "out" and item["packet_id"] == request and request:
                        item["status"] = "ack" if reason == "NONE" else "rejected"
                return
            if decoded.get("portnum") not in ("TEXT_MESSAGE_APP", 1):
                return
            if dest not in (local_num, BROADCAST) and source != local_num:
                return
            text = decoded.get("text")
            if not isinstance(text, str) or not text:
                return
            packet_id = packet.get("id")
            sender = f"!{source:08x}"
            if packet_id and any(m["packet_id"] == packet_id and m["sender"] == sender for m in self.items):
                return
            direct = dest != BROADCAST
            destination = f"!{dest:08x}" if direct else None
            peer = destination if source == local_num else sender
            channel = packet.get("channel", 0)
            self.items.append({"id": secrets.token_hex(12), "packet_id": packet_id,
                "direction": "out" if source == local_num else "in", "sender": sender,
                "destination": destination, "channel": channel,
                "conversation": f"direct:{peer}" if direct else f"channel:{channel}",
                "text": text[:1000], "time": now(), "status": "observed" if source == local_num else "received",
                "via_mqtt": bool(packet.get("viaMqtt", False))})
            self.items = self.items[-300:]
