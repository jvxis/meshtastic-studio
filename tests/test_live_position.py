"""Live protobuf callbacks must not break the JSON API. No hardware is opened."""
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from meshtastic.protobuf import mesh_pb2, portnums_pb2, telemetry_pb2

from server.app import Manager, create_app
from server.device import DeviceSession, GuardedTCP, RealDevice


@pytest.mark.parametrize('cached', [False, True])
def test_bootstrap_after_live_gps_and_telemetry(cached):
    iface = GuardedTCP('unused.invalid', connectNow=False)
    iface._writeBytes = Mock(side_effect=AssertionError('No transport I/O allowed'))
    local_num = 0xde000001
    iface.myInfo = mesh_pb2.MyNodeInfo(my_node_num=local_num)
    iface.nodesByNum = {local_num: {'num': local_num, 'user': {'id': '!de000001'}}}
    iface.nodes = {'!de000001': iface.nodesByNum[local_num]}
    iface.isConnected.set()
    real = object.__new__(RealDevice)
    real.iface = iface
    real.node_num, real.node_id = local_num, '!de000001'
    real.host, real.tcp_port, real.port = None, 4403, 'FAKE'
    real.entries, real.metadata = {}, {}
    real.close = Mock()
    session = DeviceSession('FAKE', read_initial=False)
    session.node_id = real.node_id
    session.transport = real
    manager = Manager()
    manager.device = session
    with TestClient(create_app(manager), base_url='http://127.0.0.1') as client:
        assert client.get('/api/session').status_code == 200
        position = mesh_pb2.Position(latitude_i=123456789, longitude_i=234567890, altitude=123)
        packet = mesh_pb2.MeshPacket(to=0xffffffff, id=91)
        setattr(packet, 'from', local_num)
        packet.decoded.portnum = portnums_pb2.PortNum.POSITION_APP
        packet.decoded.payload = position.SerializeToString()
        iface._handlePacketFromRadio(packet)
        stored_position = iface.nodesByNum[local_num]['position']
        assert isinstance(stored_position['raw'], mesh_pb2.Position)
        telemetry = telemetry_pb2.Telemetry()
        telemetry.device_metrics.battery_level = 87
        packet.decoded.portnum = portnums_pb2.PortNum.TELEMETRY_APP
        packet.decoded.payload = telemetry.SerializeToString()
        iface._handlePacketFromRadio(packet)
        if cached:
            session._summary = real.summary()
            session._nodes = real.nodes()
            session.transport = None
        for path in ('state', 'session'):
            response = client.get('/api/' + path)
            assert response.status_code == 200, response.text
            state = response.json()['state'] if path == 'session' else response.json()
            assert state['device']['position']['latitude'] == pytest.approx(12.3456789)
            assert state['device']['position']['altitude'] == 123
            assert state['device']['metrics']['batteryLevel'] == 87
            assert 'raw' not in state['device']['position']
        assert stored_position['raw'] == position  # Internal library data is untouched.
        iface._writeBytes.assert_not_called()
