import copy
from types import SimpleNamespace
from unittest.mock import Mock
import time

import pytest
from fastapi.testclient import TestClient
from meshtastic.protobuf import mesh_pb2, portnums_pb2

from server.app import Manager, create_app
from server.device import GuardedSerial, RealDevice, text_signature
from server.messages import MessageBox, BROADCAST
from server.demo import DemoDevice


@pytest.fixture
def client():
    manager = Manager()
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as c:
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        c.post('/api/demo', json={}).raise_for_status()
        yield c, manager


def review(c, **overrides):
    return c.post('/api/messages/preview', json={'text': 'Olá!', 'channel': 0, **overrides})


@pytest.mark.parametrize('destination', [None, '!de000002'])
def test_channel_and_direct_send_are_reviewed_once_without_configuration_changes(client, destination):
    c, manager = client
    before = copy.deepcopy(manager.device.entries)
    p = review(c, destination=destination).json()
    assert not c.get('/api/messages').json()['messages']
    r = c.post('/api/messages/send', json={'token': p['token']})
    assert r.status_code == 200
    item = r.json()['messages'][0]
    assert item['text'] == 'Olá!' and item['status'] == 'simulated'
    assert item['conversation'] == (f'direct:{destination}' if destination else 'channel:0')
    assert c.post('/api/messages/send', json={'token': p['token']}).status_code == 409
    assert manager.device.message_packets == 1 and manager.device.writes == 0
    assert manager.device.entries == before


@pytest.mark.parametrize('changes', [{'text': ' '}, {'text': '😀' * 59}, {'text': 'a\u0000b'},
    {'channel': 8}, {'channel': True}, {'channel': 7}, {'destination': '!ffffffff'},
    {'destination': '!00000000'}, {'destination': '!de000001'}, {'destination': '!ab123456'}])
def test_invalid_text_and_destinations_never_transmit(client, changes):
    c, manager = client
    assert review(c, **changes).status_code in (400, 409, 422)
    assert manager.device.message_packets == 0


def test_readonly_and_stale_reviews_block_transmission(client):
    c, manager = client
    p = review(c).json()
    manager.device.demo = False
    assert review(c).status_code == 403
    assert c.post('/api/messages/send', json={'token': p['token']}).status_code == 403
    manager.allow_writes = True
    manager.device.entries['channel.0'].settings.name = 'Changed'
    assert c.post('/api/messages/send', json={'token': p['token']}).status_code == 409
    assert manager.device.message_packets == 0


def test_failed_send_is_unknown_and_never_retried(client):
    c, manager = client
    p = review(c).json()
    manager.device.send_text = Mock(side_effect=TimeoutError())
    assert c.post('/api/messages/send', json={'token': p['token']}).status_code == 502
    assert c.get('/api/messages').json()['messages'][0]['status'] == 'unknown'
    assert c.post('/api/messages/send', json={'token': p['token']}).status_code == 409
    assert manager.device.send_text.call_count == 1


def test_receiving_channel_and_dm_does_not_send_or_change_configuration(client):
    c, manager = client
    r = c.post('/api/messages/receive', json={})
    assert r.status_code == 200 and not r.json()['listening']
    items = r.json()['messages']
    assert {m['conversation'] for m in items} == {'channel:0', 'direct:!de000003'}
    assert all(m['direction'] == 'in' for m in items)
    assert manager.device.message_packets == manager.device.writes == 0
    c.post('/api/disconnect', json={})
    assert c.get('/api/messages').json()['messages'] == []


def test_receive_window_is_bounded_cancellable_and_releases_serial(client, monkeypatch):
    c, manager = client
    c.post('/api/disconnect', json={})
    opened = []
    class FakeRadio(DemoDevice):
        demo = False
        def __init__(self, port):
            super().__init__()
            self.port = port
            opened.append(self)
        def attach_messages(self, box):
            self.messages = box
    monkeypatch.setattr('server.device.RealDevice', FakeRadio)
    monkeypatch.setattr('server.app.list_ports.comports', lambda: [SimpleNamespace(device='FAKE')])
    c.post('/api/connect', json={'port': 'FAKE'}).raise_for_status()
    def wait(seconds):
        assert seconds == 30
        assert c.get('/api/messages').json()['listening']
        c.post('/api/messages/stop', json={}).raise_for_status()
        assert manager.listen_stop.is_set()
    monkeypatch.setattr(manager.listen_stop, 'wait', wait)
    c.post('/api/messages/receive', json={}).raise_for_status()
    assert len(opened) == 2 and all(not dev.active for dev in opened)
    assert not c.get('/api/state').json()['connected']
    assert not c.get('/api/messages').json()['listening']


def test_transport_text_grant_is_exact_single_submission_and_separate_counter(monkeypatch):
    guard = object.__new__(GuardedSerial)
    guard.write_grants = {}
    guard.text_grants = {}
    guard.write_packets = guard.read_packets = guard.message_packets = 0
    value = mesh_pb2.ToRadio()
    value.packet.to = BROADCAST
    value.packet.channel = 1
    value.packet.decoded.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
    value.packet.decoded.payload = b'Approved'
    with pytest.raises(PermissionError):
        guard.inspect_packet(value)
    key = text_signature(BROADCAST, 1, b'Approved')
    guard.text_grants[key] = time.monotonic() + 30
    changed = copy.deepcopy(value)
    changed.packet.to = 123
    with pytest.raises(PermissionError):
        guard.inspect_packet(changed)
    write = Mock()
    monkeypatch.setattr('meshtastic.serial_interface.SerialInterface._sendToRadioImpl', write)
    guard._sendToRadio(value)
    assert write.call_count == 1 and guard.message_packets == 1 and guard.write_packets == 0
    with pytest.raises(PermissionError):
        guard._sendToRadio(value)


def test_real_adapter_preserves_destination_channel_and_ack_semantics():
    dev = object.__new__(RealDevice)
    dev.iface = Mock(text_grants={}, responseHandlers={}, queue={})
    box = MessageBox()
    item = box.outgoing('Olá', '!de000002', 1, '!de000001')
    def send(payload, **kw):
        assert payload == 'Olá'.encode()
        assert kw['destinationId'] == 0xde000002 and kw['channelIndex'] == 1
        assert kw['portNum'] == portnums_pb2.PortNum.TEXT_MESSAGE_APP
        kw['onResponse']({'decoded': {'routing': {'errorReason': 'NONE'}}})
        return SimpleNamespace(id=123)
    dev.iface.sendData.side_effect = send
    dev.send_text('Olá', '!de000002', 1, box, item)
    assert box.snapshot()[0]['status'] == 'ack'
    assert not dev.iface.text_grants


def test_inbox_deduplicates_isolates_dm_and_tracks_late_ack():
    box = MessageBox()
    packet = {'from': 2, 'to': BROADCAST, 'channel': 1, 'id': 10,
              'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': '<script>alert(1)</script>'}}
    box.receive(packet, '!00000001')
    box.receive(packet, '!00000001')
    assert len(box.snapshot()) == 1
    packet['id'] = 11
    packet['to'] = 3
    box.receive(packet, '!00000001')
    assert len(box.snapshot()) == 1  # Another node's direct message is excluded.
    outgoing = box.outgoing('Test', '!00000002', 0, '!00000001')
    box.update(outgoing, packet_id=12, status='unconfirmed')
    box.receive({'from': 2, 'to': 1, 'decoded': {'portnum': 'ROUTING_APP',
        'requestId': 12, 'routing': {'errorReason': 'NONE'}}}, '!00000001')
    assert box.snapshot()[-1]['status'] == 'ack'
