"""Node-Smoke für das Fußkontakt-Wiring im gait_node (Block A5 S4-1)."""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
import pytest
import rclpy
from rclpy.parameter import Parameter
from std_msgs.msg import Bool


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    yield n
    n.destroy_node()


def test_foot_contact_params_and_state(node):
    assert node.has_parameter('foot_contact_debug_enable')
    assert node.get_parameter('foot_contact_debug_enable').value is True
    # 6 Subscriber + Cache angelegt, Default alle False.
    assert set(node._foot_contact.keys()) == set(range(1, 7))
    assert all(v is False for v in node._foot_contact.values())
    assert len(node._foot_contact_subs) == 6


def test_callback_updates_cache(node):
    cb = node._make_foot_contact_cb(3)
    cb(Bool(data=True))
    assert node._foot_contact[3] is True
    cb(Bool(data=False))
    assert node._foot_contact[3] is False


def test_update_standing_ignored_by_diag(node):
    # STANDING → is_walking False → Diagnose zählt nicht, aber kein Crash + publisht.
    assert node._engine.state == GaitEngine.STATE_STANDING
    node._update_foot_contacts(0.0)
    assert node._contact_diag.summary()[1]['total_ticks'] == 0


def test_update_walking_feeds_diag(node):
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # → WALKING
    assert node._engine.state == GaitEngine.STATE_WALKING
    for i in range(5):
        node._foot_contact[1] = True
        node._update_foot_contacts(0.1 * i)
    assert node._contact_diag.summary()[1]['total_ticks'] == 5


def test_debug_enable_live(node):
    res = node.set_parameters([
        Parameter('foot_contact_debug_enable', Parameter.Type.BOOL, False),
    ])
    assert res[0].successful
    assert node._foot_contact_debug_enable is False


def test_debug_enable_rising_resets_diag(node):
    # Diagnose mit ein paar WALKING-Ticks füllen ...
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)
    for i in range(3):
        node._update_foot_contacts(0.1 * i)
    assert node._contact_diag.summary()[1]['total_ticks'] == 3
    # ... dann false→true → frisches Mess-Fenster.
    node.set_parameters([
        Parameter('foot_contact_debug_enable', Parameter.Type.BOOL, False),
    ])
    node.set_parameters([
        Parameter('foot_contact_debug_enable', Parameter.Type.BOOL, True),
    ])
    assert node._contact_diag.summary()[1]['total_ticks'] == 0
