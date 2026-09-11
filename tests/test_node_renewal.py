import time
from unittest.mock import Mock
import pytest
from fastapi import HTTPException
from server.app import Manager, RenewNodeBody
from server.demo import DemoDevice
from server.device import GuardedSerial, signature, text_signature
from meshtastic.protobuf import mesh_pb2, admin_pb2, portnums_pb2


def manager():
    m = Manager()
    m.device = DemoDevice()
    return m


def test_demo_and_session_guard():
    m = manager()
    body = RenewNodeBody(node_id='!de000002', epoch=m.epoch)
    before = m.device.entries.copy()
    result = m.renew_node(body)
    assert result['node_renewals'][body.node_id]['status'] == 'simulated'
    assert m.device.entries == before
    with pytest.raises(HTTPException) as e:
        m.renew_node(body)
    assert e.value.status_code == 409
    body.epoch = 'old-session'
    with pytest.raises(HTTPException):
        m.renew_node(body)


def test_own_unknown_and_readonly_rejected():
    m = manager()
    for target in (m.device.node_id, '!ffffffff', '!00000000', '!12345678'):
        with pytest.raises(HTTPException):
            m.renew_node(RenewNodeBody(node_id=target, epoch=m.epoch))
    m.device.demo = False
    with pytest.raises(HTTPException) as e:
        m.renew_node(RenewNodeBody(node_id='!de000002', epoch=m.epoch))
    assert e.value.status_code == 403


def test_pending_requires_public_key_not_just_node_reappearance():
    m = manager()
    m.node_renewals['!de000002'] = dict(status='waiting')
    m.device.nodes = Mock(return_value=[dict(id='!de000002', has_public_key=False)])
    assert m.renewal_state()['!de000002']['status'] == 'waiting'
    m.device.nodes.return_value[0]['has_public_key'] = True
    assert m.renewal_state()['!de000002']['status'] == 'received'


def test_packet_grants_are_exact_and_expire():
    g = object.__new__(GuardedSerial)
    g.myInfo = mesh_pb2.MyNodeInfo(my_node_num=123)
    g.write_grants = {}; g.nodeinfo_grants = {}
    a = admin_pb2.AdminMessage(remove_by_nodenum=456)
    p = mesh_pb2.ToRadio()
    p.packet.to = 123
    p.packet.decoded.portnum = portnums_pb2.ADMIN_APP
    p.packet.decoded.payload = a.SerializeToString()
    with pytest.raises(PermissionError): g.inspect_packet(p)
    g.write_grants[signature(a)] = time.monotonic()+10
    assert g.inspect_packet(p) is True
    p.packet.to = 456
    with pytest.raises(PermissionError): g.inspect_packet(p)
    p.packet.decoded.portnum = portnums_pb2.NODEINFO_APP
    p.packet.decoded.payload = b'public-info'
    p.packet.decoded.want_response = True
    with pytest.raises(PermissionError): g.inspect_packet(p)
    key = text_signature(456, 0, b'public-info')
    g.nodeinfo_grants[key] = time.monotonic()+10
    assert g.inspect_packet(p) is False
    p.packet.to = 789
    with pytest.raises(PermissionError): g.inspect_packet(p)
    p.packet.to = 456
    g.nodeinfo_grants[key] = time.monotonic()-1
    with pytest.raises(PermissionError): g.inspect_packet(p)


@pytest.mark.parametrize('failure', [False, True])
def test_transport_removes_only_target_and_never_retries_on_timeout(failure):
    from server.device import RealDevice
    from meshtastic.protobuf import channel_pb2
    d = object.__new__(RealDevice)
    d.node_num = 123
    d.entries = {'channel.0': channel_pb2.Channel(index=0, role=1)}
    d.iface = Mock()
    own = {'num': 123, 'user': {'id': '!0000007b', 'longName': 'Me'}}
    peer = {'num': 456, 'user': {'id': '!000001c8'}}
    other = {'num': 789}
    d.iface.nodesByNum = {123: own, 456: peer, 789: other}
    d.iface.nodes = {'!000001c8': peer}
    d.iface.write_grants = {}; d.iface.nodeinfo_grants = {}
    d.exchange = Mock(side_effect=TimeoutError() if failure else None)
    if failure:
        with pytest.raises(TimeoutError): d.renew_node('!000001c8')
        assert 456 in d.iface.nodesByNum
        d.iface.sendData.assert_not_called()
    else:
        d.renew_node('!000001c8')
        assert 456 not in d.iface.nodesByNum
        d.iface.sendData.assert_called_once()
        assert d.iface.sendData.call_args.kwargs['destinationId'] == 456
        assert d.iface.sendData.call_args.kwargs['wantResponse'] is True
    d.exchange.assert_called_once()
    assert d.exchange.call_args.args[0].remove_by_nodenum == 456
    assert d.iface.nodesByNum[123] is own
    assert d.iface.nodesByNum[789] is other
    assert not d.iface.write_grants and not d.iface.nodeinfo_grants
