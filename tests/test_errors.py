"""Errors must describe the selected transport and never echo raw exceptions."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from serial import SerialException

from server.app import Manager, create_app


@pytest.mark.parametrize('transport,error,expected,excluded', [
    ('serial', SerialException('Cannot configure port: private-diagnostic'), 'inicializar', 'TCP'),
    ('serial', SerialException("could not open port: Acesso negado. private-diagnostic"), 'porta ocupada', 'TCP'),
    ('serial', SerialException('device lost: private-diagnostic'), 'USB/Serial', 'TCP'),
    ('serial', TimeoutError('private-diagnostic'), 'dentro do prazo', 'TCP'),
    ('tcp', ConnectionRefusedError('private-diagnostic'), 'recusou a conexão TCP', 'USB/Serial'),
    ('tcp', TimeoutError('private-diagnostic'), 'comunicação TCP', 'USB/Serial'),
])
def test_failed_initial_connect_keeps_transport_context(transport, error, expected, excluded):
    manager = Manager()
    manager.connect = Mock(side_effect=error)
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as c:
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        endpoint = {'port': 'COM9'} if transport == 'serial' else {'transport': 'tcp', 'host': 'radio.local'}
        result = c.post('/api/connect', json=endpoint)
        assert result.status_code == 503
        assert expected in result.json()['detail'] and excluded not in result.text
        assert 'private-diagnostic' not in result.text
        state = c.get('/api/state')
        assert 'private-diagnostic' not in state.text
        assert not state.json()['session_active']


@pytest.mark.parametrize('transport', ['serial', 'tcp'])
def test_section_read_uses_selected_session_transport(transport):
    manager = Manager()
    manager.connect(demo=True)
    manager.device.demo = False
    manager.device.host = 'radio.local' if transport == 'tcp' else None
    manager.device.read = Mock(side_effect=TimeoutError())
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as c:
        c.headers['x-mesh-token'] = c.get('/api/session').json()['token']
        result = c.post('/api/read/config.lora', json={})
        assert result.status_code == 503
        assert ('USB/Serial' in result.text) == (transport == 'serial')
        assert ('TCP' in result.text) == (transport == 'tcp')
