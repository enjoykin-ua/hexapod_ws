"""
Unit tests for the shutdown supervisor state machine (Block F4, F4-S1..S6).

GaitNode-style strategy: instantiate the node directly and drive its callbacks;
service clients and the OS-shutdown call are mocked, so nothing touches HW or
the OS. Timers are created but never fire (the node is not spun).
"""

from unittest.mock import MagicMock, patch

from hexapod_supervisor.shutdown_supervisor import ShutdownSupervisor
import pytest
import rclpy
from std_msgs.msg import Bool


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    """Init/shutdown rclpy once for the module."""
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    """Fresh ShutdownSupervisor per test."""
    n = ShutdownSupervisor()
    yield n
    n.destroy_node()


def _bool(value):
    msg = Bool()
    msg.data = value
    return msg


def _response(success, message='x'):
    resp = MagicMock()
    resp.success = success
    resp.message = message
    return resp


def _future(resp):
    fut = MagicMock()
    fut.exception.return_value = None
    fut.result.return_value = resp
    return fut


def test_startup_true_is_baselined(node):
    """F4-S1: a latched True at startup is baselined, NOT triggered."""
    node._begin_shutdown = MagicMock()
    node._on_request(_bool(True))
    node._begin_shutdown.assert_not_called()
    assert node._state == ShutdownSupervisor.STATE_IDLE


def test_rising_edge_triggers(node):
    """F4-S2: a real False->True edge begins the shutdown."""
    node._begin_shutdown = MagicMock()
    node._on_request(_bool(False))
    node._on_request(_bool(True))
    node._begin_shutdown.assert_called_once()


def test_retrigger_after_storno(node):
    """F4-S6: True->False->True triggers again (cancel then re-request)."""
    node._begin_shutdown = MagicMock()
    node._on_request(_bool(False))
    node._on_request(_bool(True))
    node._on_request(_bool(False))
    node._on_request(_bool(True))
    assert node._begin_shutdown.call_count == 2


def test_service_refused_keeps_retrying(node):
    """F4-S3: a refused /hexapod_shutdown leaves service_ok False (no backstop)."""
    node._state = ShutdownSupervisor.STATE_SHUTTING_DOWN
    node._on_shutdown_response(_future(_response(False, 'walking')))
    assert node._service_ok is False
    assert node._backstop_timer is None


def test_service_accepted_then_complete_finishes(node):
    """F4-S4: accepted service + complete flag -> guarded shutdown, DONE."""
    node._state = ShutdownSupervisor.STATE_SHUTTING_DOWN
    with patch(
        'hexapod_supervisor.shutdown_supervisor.guarded_shutdown',
        return_value=(False, 'disabled'),
    ) as gs:
        node._on_shutdown_response(_future(_response(True, 'ok')))
        assert node._service_ok is True
        node._on_complete(_bool(True))
        gs.assert_called_once()
    assert node._state == ShutdownSupervisor.STATE_DONE


def test_complete_already_latched_finishes_on_accept(node):
    """F4-S7: complete latched before the service response -> finish on accept."""
    node._state = ShutdownSupervisor.STATE_SHUTTING_DOWN
    node._on_complete(_bool(True))
    assert node._state == ShutdownSupervisor.STATE_SHUTTING_DOWN  # not yet (no ok)
    with patch(
        'hexapod_supervisor.shutdown_supervisor.guarded_shutdown',
        return_value=(False, 'disabled'),
    ) as gs:
        node._on_shutdown_response(_future(_response(True, 'already SAT')))
        gs.assert_called_once()
    assert node._state == ShutdownSupervisor.STATE_DONE


def test_backstop_finishes_with_relay_off(node):
    """F4-S5: backstop timeout forces relay-off and shuts down anyway."""
    node._state = ShutdownSupervisor.STATE_SHUTTING_DOWN
    node._service_ok = True
    node._relay_client.service_is_ready = MagicMock(return_value=True)
    node._relay_client.call_async = MagicMock()
    with patch(
        'hexapod_supervisor.shutdown_supervisor.guarded_shutdown',
        return_value=(False, 'disabled'),
    ) as gs:
        node._on_backstop()
        node._relay_client.call_async.assert_called_once()
        gs.assert_called_once()
    assert node._state == ShutdownSupervisor.STATE_DONE
