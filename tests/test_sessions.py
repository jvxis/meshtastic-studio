"""Exercise short physical sessions with a fake transport; never open a COM port."""
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from server.app import Manager, create_app
from server.demo import DemoDevice
from server.device import RealDevice
from server.schema import DEFINITIONS, as_dict, prepare


@pytest.fixture
def borrowed(monkeypatch):
    radio = DemoDevice()
    opened = []

    class Transport(DemoDevice):
        demo = False

        def __init__(self, port):
            super().__init__()
            self.port = port
            self.node_id = radio.node_id
            self.entries = copy.deepcopy(radio.entries)
            self.close_count = 0
            opened.append(self)

        def read(self, key):
            self.entries[key] = copy.deepcopy(radio.entries[key])
            return self.entries[key]

        def write(self, key, value):
            radio.write(key, value)
            return self.read(key)

        def close(self):
            self.close_count += 1
            super().close()

    monkeypatch.setattr('server.device.RealDevice', Transport)
    monkeypatch.setattr('server.app.list_ports.comports', lambda: [SimpleNamespace(device='FAKE')])
    manager = Manager(allow_writes=True)
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as cli:
        cli.headers['x-mesh-token'] = cli.get('/api/session').json()['token']
        cli.post('/api/connect', json={'port': 'FAKE'}).raise_for_status()
        yield cli, manager, radio, opened
    assert all(dev.close_count == 1 for dev in opened)


def preview(cli):
    entry = cli.get('/api/state').json()['sections']['config.lora']
    entry['values']['hop_limit'] = 4
    return cli.post('/api/preview', json={'section': 'config.lora', 'revision': entry['revision'],
                                        'values': entry['values']}).json()


def apply(cli, p):
    return cli.post('/api/apply', json={'token': p['token'], 'confirmation': p['confirmation']})


def test_snapshot_preview_and_state_do_not_hold_or_reopen_serial(borrowed):
    cli, manager, radio, opened = borrowed
    state = cli.get('/api/state').json()
    assert state['session_active'] and not state['connected'] and state['observed_at']
    assert state['sections']['config.lora']['available']
    preview(cli)
    cli.get('/api/session')
    assert len(opened) == 1 and opened[0].close_count == 1
    cli.post('/api/read/config.network', json={}).raise_for_status()
    cli.post('/api/refresh', json={}).raise_for_status()
    assert len(opened) == 3 and all(d.close_count == 1 for d in opened)
    assert radio.writes == 0


def test_apply_reconnects_once_and_closes_after_verification(borrowed):
    cli, _, radio, opened = borrowed
    p = preview(cli)
    result = apply(cli, p)
    assert result.status_code == 200 and radio.writes == 1
    assert not result.json()['connected'] and len(opened) == 2
    assert result.json()['sections']['config.lora']['values']['hop_limit'] == 4
    assert apply(cli, p).status_code == 409
    assert len(opened) == 2  # Replayed token never opens the port.


def test_edit_from_device_screen_blocks_stale_draft_and_releases_port(borrowed):
    cli, _, radio, opened = borrowed
    p = preview(cli)
    radio.entries['config.lora'].hop_limit = 5
    assert apply(cli, p).status_code == 409 and radio.writes == 0
    assert opened[-1].close_count == 1


def test_replaced_radio_is_never_written_or_bound_to_previous_session(borrowed):
    cli, manager, radio, opened = borrowed
    p = preview(cli)
    original_id = manager.device.node_id
    radio.node_id = '!de999999'
    assert apply(cli, p).status_code == 400
    assert radio.writes == 0 and manager.device.node_id == original_id
    assert opened[-1].close_count == 1
    assert cli.post('/api/refresh', json={}).status_code == 400


def test_failed_read_or_write_releases_port_and_never_retries_write(borrowed, monkeypatch):
    cli, manager, radio, opened = borrowed
    p = preview(cli)
    def failed_write(*args):
        radio.writes += 1
        raise TimeoutError()
    monkeypatch.setattr('server.device.RealDevice.write', failed_write)
    assert apply(cli, p).status_code == 502
    assert radio.writes == 1 and opened[-1].close_count == 1
    assert 'config.lora' not in manager.device.entries
    monkeypatch.setattr('server.device.RealDevice.read', Mock(side_effect=TimeoutError()))
    assert cli.post('/api/read/ui', json={}).status_code == 503
    assert opened[-1].close_count == 1


def test_failed_handshake_closes_transport(monkeypatch):
    guard = Mock()
    guard.connect.side_effect = TimeoutError()
    monkeypatch.setattr('server.device.GuardedSerial', Mock(return_value=guard))
    with pytest.raises(TimeoutError):
        RealDevice('FAKE')
    guard.close.assert_called_once()


def test_deprecated_fields_cannot_be_edited_and_omission_preserves_them():
    radio = DemoDevice()
    original = radio.entries['config.position']
    original.gps_enabled = True
    values = as_dict(original)
    values['gps_enabled'] = False
    with pytest.raises(ValueError, match='gps_enabled'):
        prepare('config.position', values, original)
    del values['gps_enabled']
    values['gps_mode'] = 'ENABLED'
    target, changes = prepare('config.position', values, original)
    assert target.gps_enabled
    assert [c['path'] for c in changes] == ['gps_mode']
    fields = {f['name']: f for f in DEFINITIONS['config.position']['fields']}
    assert fields['gps_enabled']['deprecated'] and fields['gps_enabled']['readonly']
    assert not fields['gps_mode']['readonly']


def test_every_top_level_deprecated_field_is_protected():
    radio = DemoDevice()
    for key, definition in DEFINITIONS.items():
        for field in definition['fields']:
            if not field.get('deprecated'):
                continue
            original = radio.entries[key]
            values = as_dict(original)
            value = values[field['name']]
            values[field['name']] = (not value if isinstance(value, bool) else
                                     value + 1 if isinstance(value, int) else
                                     next((o for o in field['options'] if o != value), 'INVALID') if field['kind'] == 'enum'
                                     else value + 'changed')
            with pytest.raises(ValueError):
                prepare(key, values, original)
