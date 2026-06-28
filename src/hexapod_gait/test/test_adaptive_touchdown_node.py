"""
Node-Wiring für den adaptiven Touchdown (Block A5 S4-2).

Prüft: Param-Defaults + Spiegelung auf die Engine, Live-Tuning + Validierung,
das Durchreichen der Kontakte an die Engine und den Contact-Live-Guard
(Pipeline tot/stale → adaptiv aus).
"""

import time

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


def test_params_default_and_mirrored_to_engine(node):
    assert node.has_parameter('adaptive_touchdown_enable')
    assert node.get_parameter('adaptive_touchdown_enable').value is False
    assert node._adaptive_touchdown_enable is False
    # Probe-Fenster/Tiefe auf die Engine gespiegelt
    assert node._engine.touchdown_probe_start_stance_phase == pytest.approx(0.35)
    assert node._engine.touchdown_search_end_stance_phase == pytest.approx(0.6)
    assert node._engine.touchdown_max_extra_depth == pytest.approx(0.02)


def test_live_tuning_mirrors_to_engine(node):
    res = node.set_parameters([
        Parameter('adaptive_touchdown_enable', Parameter.Type.BOOL, True),
        Parameter(
            'touchdown_probe_start_stance_phase', Parameter.Type.DOUBLE, 0.4),
        Parameter(
            'touchdown_search_end_stance_phase', Parameter.Type.DOUBLE, 0.7),
        Parameter('touchdown_max_extra_depth', Parameter.Type.DOUBLE, 0.03),
    ])
    assert res[0].successful
    assert node._adaptive_touchdown_enable is True
    assert node._engine.touchdown_probe_start_stance_phase == pytest.approx(0.4)
    assert node._engine.touchdown_search_end_stance_phase == pytest.approx(0.7)
    assert node._engine.touchdown_max_extra_depth == pytest.approx(0.03)


@pytest.mark.parametrize('name,value', [
    ('touchdown_probe_start_stance_phase', 1.0),
    ('touchdown_probe_start_stance_phase', -0.1),
    ('touchdown_search_end_stance_phase', 1.5),
    ('touchdown_search_end_stance_phase', 0.0),
    ('touchdown_max_extra_depth', -0.01),
])
def test_invalid_params_rejected(node, name, value):
    res = node.set_parameters([
        Parameter(name, Parameter.Type.DOUBLE, value),
    ])
    assert not res[0].successful


def test_probe_must_be_below_search_end_rejected(node):
    # probe_start >= search_end → Cross-Constraint-Fail.
    res = node.set_parameters([
        Parameter(
            'touchdown_probe_start_stance_phase', Parameter.Type.DOUBLE, 0.7),
        Parameter(
            'touchdown_search_end_stance_phase', Parameter.Type.DOUBLE, 0.5),
    ])
    assert not res[0].successful


def test_contacts_passed_to_engine(node):
    node._foot_contact[2] = True
    node._foot_contact[5] = True
    node._update_foot_contacts(0.0)
    assert node._engine._foot_contacts[2] is True
    assert node._engine._foot_contacts[5] is True
    assert node._engine._foot_contacts[1] is False


def test_guard_off_when_pipeline_never_received(node):
    # Param AN, aber nie eine Kontakt-Message empfangen → adaptiv bleibt AUS.
    node._adaptive_touchdown_enable = True
    assert node._foot_contact_received is False
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_touchdown_enable is False


def test_guard_on_when_pipeline_fresh(node):
    node._adaptive_touchdown_enable = True
    # Callback simuliert frischen Empfang (setzt received + timestamp)
    node._make_foot_contact_cb(1)(Bool(data=False))
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_touchdown_enable is True


def test_guard_off_when_pipeline_stale(node):
    node._adaptive_touchdown_enable = True
    node._foot_contact_received = True
    # letzte Message > Stale-Schwelle (0.5 s) her → toter Publisher
    node._last_foot_contact_msg_t = time.monotonic() - 1.0
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_touchdown_enable is False


def test_guard_off_when_param_disabled_even_if_fresh(node):
    # Param AUS dominiert auch bei frischer Pipeline.
    node._adaptive_touchdown_enable = False
    node._make_foot_contact_cb(1)(Bool(data=True))
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_touchdown_enable is False


def test_walking_with_adaptive_no_crash(node):
    # Integrations-Smoke: WALKING + adaptiv AN + frische Kontakte → Tick läuft.
    node._adaptive_touchdown_enable = True
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)
    assert node._engine.state == GaitEngine.STATE_WALKING
    for i in range(10):
        node._make_foot_contact_cb(1)(Bool(data=(i % 2 == 0)))
        t = 0.02 * i
        node._update_foot_contacts(t)
        node._engine.compute_joint_angles(t)
