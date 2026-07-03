"""
Node-Wiring für das terrain-anpassende Stehen (Block A5 S4-7, Adaptive Stand).

Prüft: Param-Defaults + Spiegelung auf die Engine, Live-Tuning + Validierung,
den Contact-Live-Guard (Pipeline tot/stale → adaptiv aus), den Enable-Edge-
Reset in STANDING und dass nur STANDING adaptiv absenkt (Walk/Sit/Show nicht).
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
    assert node.has_parameter('adaptive_stand_enable')
    assert node.get_parameter('adaptive_stand_enable').value is False
    assert node._adaptive_stand_enable is False
    assert node._engine.adaptive_stand_enable is False
    assert node._engine.stand_conform_max_depth == pytest.approx(0.04)
    assert node._engine.stand_conform_rate == pytest.approx(0.02)


def test_live_tuning_mirrors_to_engine(node):
    res = node.set_parameters([
        Parameter('stand_conform_max_depth', Parameter.Type.DOUBLE, 0.03),
        Parameter('stand_conform_rate', Parameter.Type.DOUBLE, 0.05),
    ])
    assert res[0].successful
    assert node._engine.stand_conform_max_depth == pytest.approx(0.03)
    assert node._engine.stand_conform_rate == pytest.approx(0.05)


@pytest.mark.parametrize('name,value', [
    ('stand_conform_max_depth', -0.01),
    ('stand_conform_rate', 0.0),
    ('stand_conform_rate', -0.02),
])
def test_invalid_params_rejected(node, name, value):
    res = node.set_parameters([
        Parameter(name, Parameter.Type.DOUBLE, value),
    ])
    assert not res[0].successful


def test_guard_off_when_pipeline_never_received(node):
    node._adaptive_stand_enable = True
    assert node._foot_contact_received is False
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_stand_enable is False


def test_guard_on_when_pipeline_fresh(node):
    node._adaptive_stand_enable = True
    node._make_foot_contact_cb(1)(Bool(data=False))   # frischer Empfang
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_stand_enable is True


def test_guard_off_when_pipeline_stale(node):
    node._adaptive_stand_enable = True
    node._foot_contact_received = True
    node._last_foot_contact_msg_t = time.monotonic() - 1.0   # > 0.5 s stale
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_stand_enable is False


def test_guard_off_when_param_disabled_even_if_fresh(node):
    node._adaptive_stand_enable = False
    node._make_foot_contact_cb(1)(Bool(data=True))
    node._update_foot_contacts(0.0)
    assert node._engine.adaptive_stand_enable is False


def test_live_enable_in_standing_resets_conform(node):
    # Engine startet in STANDING. Live-Enable → frischer Konform-Anker (t_entry),
    # sonst würde die Descent gegen ein altes _t_stand_entry rechnen.
    assert node._engine.state == GaitEngine.STATE_STANDING
    node._engine._t_stand_entry = -999.0   # künstlich alt
    res = node.set_parameters([
        Parameter('adaptive_stand_enable', Parameter.Type.BOOL, True),
    ])
    assert res[0].successful
    assert node._adaptive_stand_enable is True
    assert node._engine._t_stand_entry > -999.0   # Reset frisch gestempelt


def test_standing_adaptive_no_crash(node):
    # Integrations-Smoke: STANDING + adaptiv AN + frische Kontakte (uneben) →
    # Tick läuft, kein IKError. Node startet in STANDING.
    node._adaptive_stand_enable = True
    for i in range(20):
        # unebenes Terrain simulieren: Bein 1+2 kein Kontakt (senken), Rest schon
        node._make_foot_contact_cb(1)(Bool(data=False))
        node._make_foot_contact_cb(3)(Bool(data=True))
        t = 0.02 * i
        node._update_foot_contacts(t)
        node._engine.compute_joint_angles(t)
    assert node._engine.state == GaitEngine.STATE_STANDING


def test_walking_state_not_adaptive_stand(node):
    # In WALKING darf der adaptive STAND-Pfad nicht greifen (nur STANDING) —
    # compute_foot_targets nutzt dort _compute_walking_targets.
    node._adaptive_stand_enable = True
    node._make_foot_contact_cb(1)(Bool(data=False))
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)
    assert node._engine.state == GaitEngine.STATE_WALKING
    node._update_foot_contacts(0.0)
    # adaptive_stand_enable ist zwar True (Guard live), aber der Stand-Konform-
    # State bleibt unberührt, weil compute_foot_targets im WALKING nicht in
    # _compute_standing_targets läuft.
    node._engine.compute_joint_angles(0.0)
    for leg_id in range(1, 7):
        assert node._engine._stand_conform_z[leg_id] is None
