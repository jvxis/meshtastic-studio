"""Continuous desktop reception with fake serial/TCP radios only."""
import copy
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from server.app import Manager, create_app
from server.demo import DemoDevice
from server.messages import BROADCAST


def until(predicate):
    deadline = time.monotonic() + 5
    while not predicate():
        assert time.monotonic() < deadline, 'Background reception did not settle'
        time.sleep(.01)


@pytest.fixture(params=['serial', 'tcp'])
def active_radio(monkeypatch, request):
    radio = DemoDevice()
    opened = []

    class Transport(DemoDevice):
        demo = False

        def __init__(self, port=None, *, host=None, tcp_port=4403):
            super().__init__()
            self.port = f'{host}:{tcp_port}' if host else port
            self.node_id = radio.node_id
            self.entries = copy.deepcopy(radio.entries)
            self.close_count = 0
            opened.append(self)

        def attach_messages(self, box):
            self.messages = box

        def read(self, key):
            self.entries[key] = copy.deepcopy(radio.entries[key])
            return self.entries[key]

        def write(self, key, value):
            radio.write(key, value)
            return self.read(key)

        def summary(self):
            return {**super().summary(), 'message_packets': self.message_packets}

        def close(self):
            self.close_count += 1
            super().close()

    monkeypatch.setattr('server.device.RealDevice', Transport)
    monkeypatch.setattr('server.app.list_ports.comports', lambda: [SimpleNamespace(device='FAKE')])
    manager = Manager(allow_writes=True)
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as client:
        client.headers['x-mesh-token'] = client.get('/api/session').json()['token']
        endpoint = {'transport': 'tcp', 'host': 'radio.local'} if request.param == 'tcp' else {'port': 'FAKE'}
        client.post('/api/connect', json=endpoint).raise_for_status()
        yield client, manager, radio, opened, Transport
    assert manager.active_thread is None
    assert all(dev.close_count == 1 for dev in opened)


def start(client, manager):
    client.post('/api/messages/active', json={}).raise_for_status()
    until(lambda: manager.active_phase == 'active')


def stop(client, manager):
    client.post('/api/messages/stop', json={}).raise_for_status()
    until(lambda: manager.active_thread is None)


def test_active_receives_and_keeps_state_available_until_explicit_stop(active_radio):
    c, m, radio, opened, _ = active_radio
    start(c, m)
    assert len(opened) == 2 and opened[-1].close_count == 0
    state = c.get('/api/state').json()
    assert state['connected'] and state['active_phase'] == 'active'
    assert state['sections']['config.lora']['available']
    for index, destination in enumerate([BROADCAST, int(m.device.node_id[1:], 16)]):
        m.active_transport.messages.receive({'from': 0xde000002, 'to': destination,
            'channel': 1, 'id': 100+index, 'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'Received'}}, m.device.node_id)
    assert len(c.get('/api/messages').json()['messages']) == 2
    assert c.post('/api/messages/active', json={}).status_code == 409
    assert c.post('/api/messages/receive', json={}).status_code == 409
    stop(c, m)
    assert c.get('/api/messages').json()['active_phase'] == 'off'
    assert not c.get('/api/state').json()['connected']
    assert len(opened) == 2 and radio.writes == 0
    assert len(m.device.messages.snapshot()) == 2


@pytest.mark.parametrize('destination', [None, '!de000002'])
def test_send_uses_existing_connection_and_receives_while_waiting_for_ack(active_radio, monkeypatch, destination):
    c, m, radio, opened, transport = active_radio
    start(c, m)
    entered, resume = threading.Event(), threading.Event()
    original = transport.send_text

    def delayed(self, text, dest, channel, box, item):
        entered.set()
        assert resume.wait(5)
        original(self, text, dest, channel, box, item)

    monkeypatch.setattr(transport, 'send_text', delayed)
    review = c.post('/api/messages/preview', json={'text': 'Desktop', 'channel': 1, 'destination': destination}).json()
    results = []
    sender = threading.Thread(target=lambda: results.append(c.post('/api/messages/send', json={'token': review['token']})))
    sender.start()
    try:
        assert entered.wait(5)
        m.active_transport.messages.receive({'from': 0xde000002, 'to': BROADCAST, 'channel': 1,
            'id': 500, 'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'During send'}}, m.device.node_id)
        assert len(c.get('/api/messages').json()['messages']) == 2
        before = time.monotonic()
        c.post('/api/messages/stop', json={}).raise_for_status()
        assert time.monotonic() - before < 1
        assert opened[-1].close_count == 0  # Let the current send finish before closing.
    finally:
        resume.set()
        sender.join(5)
    until(lambda: m.active_thread is None)
    assert results[0].status_code == 200
    assert len(opened) == 2 and radio.writes == 0
    assert m.device.message_packets == 1
    assert c.post('/api/messages/send', json={'token': review['token']}).status_code == 409
    assert len(opened) == 2


def test_active_checks_fresh_channel_before_send_and_keeps_settings_usable(active_radio):
    c, m, radio, opened, _ = active_radio
    start(c, m)
    review = c.post('/api/messages/preview', json={'text': 'Desktop', 'channel': 1}).json()
    radio.entries['channel.1'].settings.name = 'Changed elsewhere'
    assert c.post('/api/messages/send', json={'token': review['token']}).status_code == 409
    assert not m.device.messages.snapshot()
    c.post('/api/read/config.lora', json={}).raise_for_status()
    entry = c.get('/api/state').json()['sections']['config.lora']
    entry['values']['hop_limit'] = 4
    p = c.post('/api/preview', json={'section': 'config.lora', 'revision': entry['revision'], 'values': entry['values']}).json()
    c.post('/api/apply', json={'token': p['token'], 'confirmation': p['confirmation']}).raise_for_status()
    assert radio.writes == 1 and len(opened) == 2
    assert c.get('/api/state').json()['sections']['config.lora']['values']['hop_limit'] == 4
    assert m.active_phase == 'active'


def test_readonly_active_listening_never_enables_sending(active_radio):
    c, m, radio, opened, _ = active_radio
    m.allow_writes = False
    start(c, m)
    assert not c.get('/api/messages').json()['can_send']
    assert c.post('/api/messages/preview', json={'text': 'Blocked', 'channel': 0}).status_code == 403
    assert radio.writes == 0 and len(opened) == 2


def test_connection_loss_closes_once_without_reconnect_and_can_restart_manually(active_radio):
    c, m, _, opened, _ = active_radio
    start(c, m)
    m.active_transport.active = False
    until(lambda: m.active_thread is None)
    state = c.get('/api/messages').json()
    assert not state['listening'] and state['active_phase'] == 'error' and state['listen_error']
    assert len(opened) == 2 and opened[-1].close_count == 1
    start(c, m)
    assert len(opened) == 3
    c.post('/api/disconnect', json={}).raise_for_status()
    assert m.device is None and m.active_thread is None


def test_stop_during_handshake_waits_then_closes_without_activating(active_radio, monkeypatch):
    c, m, _, opened, transport = active_radio
    entered, resume = threading.Event(), threading.Event()
    original = transport.__init__

    def delayed(self, *args, **kwargs):
        entered.set()
        assert resume.wait(5)
        original(self, *args, **kwargs)

    monkeypatch.setattr(transport, '__init__', delayed)
    c.post('/api/messages/active', json={}).raise_for_status()
    assert entered.wait(5)
    try:
        assert c.get('/api/messages').json()['active_phase'] == 'starting'
        c.post('/api/messages/stop', json={}).raise_for_status()
        assert c.get('/api/messages').json()['active_phase'] == 'stopping'
    finally:
        resume.set()
    until(lambda: m.active_thread is None)
    assert m.active_phase == 'off' and len(opened) == 2


def test_wrong_radio_on_active_start_is_rejected(active_radio):
    c, m, radio, opened, _ = active_radio
    original_id = m.device.node_id
    radio.node_id = '!de999999'
    c.post('/api/messages/active', json={}).raise_for_status()
    until(lambda: m.active_thread is None)
    assert m.active_phase == 'error' and m.device.node_id == original_id
    assert len(opened) == 2 and opened[-1].close_count == 1
    c.post('/api/disconnect', json={}).raise_for_status()
    state = c.get('/api/messages').json()
    assert state['active_phase'] == 'off' and not state['listen_error']


def connect_desktop(client, manager, opened):
    dev = manager.device
    endpoint = {'transport': 'tcp', 'host': dev.host} if dev.host else {'port': dev.port}
    client.post('/api/disconnect', json={}).raise_for_status()
    opened.clear()
    return client.post('/api/connect', json={**endpoint, 'mode': 'desktop'})


def test_desktop_connect_receives_and_sends_on_first_connection(active_radio):
    c, m, radio, opened, _ = active_radio
    response = connect_desktop(c, m, opened)
    response.raise_for_status()
    state = response.json()
    assert state['connected'] and state['active_phase'] == 'active'
    assert state['connection_mode'] == 'desktop'
    assert len(opened) == 1 and opened[0].close_count == 0
    assert c.get('/api/messages').json()['listening']
    m.active_transport.messages.receive({'from': 0xde000002, 'to': BROADCAST,
        'channel': 1, 'id': 901, 'decoded': {'portnum': 'TEXT_MESSAGE_APP', 'text': 'First connection'}}, m.device.node_id)
    assert len(c.get('/api/messages').json()['messages']) == 1
    for destination in (None, '!de000002'):
        grant = c.post('/api/messages/preview', json={'text': 'Desktop', 'channel': 1, 'destination': destination}).json()
        c.post('/api/messages/send', json={'token': grant['token']}).raise_for_status()
    c.post('/api/read/config.lora', json={}).raise_for_status()
    assert len(opened) == 1 and radio.writes == 0
    stop(c, m)
    assert opened[0].close_count == 1
    # Desktop operations cannot silently reopen after the user disconnects.
    assert c.post('/api/read/config.lora', json={}).status_code == 409
    assert len(opened) == 1 and len(m.device.messages.snapshot()) == 3
    start(c, m)
    assert len(opened) == 2


def test_desktop_drop_blocks_operations_without_reconnecting(active_radio):
    c, m, radio, opened, _ = active_radio
    m.allow_writes = False
    connect_desktop(c, m, opened).raise_for_status()
    assert not c.get('/api/messages').json()['can_send']
    m.active_transport.active = False
    until(lambda: m.active_thread is None)
    assert c.get('/api/state').json()['connected'] is False
    assert m.active_phase == 'error'
    assert c.post('/api/refresh', json={}).status_code == 409
    assert len(opened) == 1 and opened[0].close_count == 1 and radio.writes == 0


def test_desktop_worker_start_failure_releases_initial_connection(active_radio, monkeypatch):
    c, m, _, opened, _ = active_radio
    original = threading.Thread.start

    def fail_worker(self):
        if self.name == 'desktop reception':
            raise RuntimeError('Simulated thread failure')
        return original(self)

    monkeypatch.setattr(threading.Thread, 'start', fail_worker)
    assert connect_desktop(c, m, opened).status_code == 503
    assert m.device is None and m.active_thread is None and m.active_transport is None
    assert len(opened) == 1 and opened[0].close_count == 1


def test_desktop_stop_during_handoff_closes_initial_connection(active_radio, monkeypatch):
    c, m, _, opened, _ = active_radio
    original = threading.Thread.start

    def stop_before_worker(self):
        if self.name == 'desktop reception':
            m.stop_reception()
        return original(self)

    monkeypatch.setattr(threading.Thread, 'start', stop_before_worker)
    connect_desktop(c, m, opened).raise_for_status()
    until(lambda: m.active_thread is None)
    assert len(opened) == 1 and opened[0].close_count == 1
    assert m.active_phase == 'off' and not m.device.connected()


def test_desktop_initial_handshake_failure_does_not_leave_session(active_radio, monkeypatch):
    c, m, _, opened, _ = active_radio
    def fail(*args, **kwargs):
        raise TimeoutError('Simulated handshake timeout')
    monkeypatch.setattr('server.device.RealDevice', fail)
    assert connect_desktop(c, m, opened).status_code == 503
    assert m.device is None and m.active_thread is None and not opened


def test_cancel_desktop_initial_handshake_releases_without_starting_receiver(active_radio, monkeypatch):
    c, m, _, opened, transport = active_radio
    entered, resume = threading.Event(), threading.Event()
    original = transport.__init__
    def delayed(self, *args, **kwargs):
        entered.set()
        assert resume.wait(5)
        original(self, *args, **kwargs)
    monkeypatch.setattr(transport, '__init__', delayed)
    responses = []
    connector = threading.Thread(target=lambda: responses.append(connect_desktop(c, m, opened)))
    connector.start()
    try:
        assert entered.wait(5)
        assert c.get('/api/messages').json()['active_phase'] == 'starting'
        c.post('/api/messages/stop', json={}).raise_for_status()
    finally:
        resume.set()
        connector.join(5)
    assert responses[0].status_code == 409
    assert m.device is None and m.active_thread is None
    assert len(opened) == 1 and opened[0].close_count == 1


def test_managed_shutdown_releases_active_serial_or_tcp(active_radio):
    c, m, _, opened, _ = active_radio
    connect_desktop(c, m, opened).raise_for_status()
    stopped = []
    def on_shutdown():
        assert opened[0].close_count == 1
        assert m.active_thread is None and m.device is None
        stopped.append(True)
    with TestClient(create_app(m, shutdown_callback=on_shutdown), base_url='http://127.0.0.1') as managed:
        managed.headers['x-mesh-token'] = managed.get('/api/session').json()['token']
        managed.post('/api/shutdown', json={}).raise_for_status()
    assert stopped == [True] and len(opened) == 1
