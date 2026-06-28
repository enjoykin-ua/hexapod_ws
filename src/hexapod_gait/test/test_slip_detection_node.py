"""
Node-Wiring für Slip/Kontaktverlust → Freeze (Block A5 S4-4).

Prüft: Param-Defaults + Spiegelung von cliff_depth auf engine.cliff_probe_depth,
Live-Tuning + Validierung, WALKING-Gating, und den Freeze-Pfad (Stütz-Verlust →
_update_support True + Safety-Freeze gelatcht).
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
import pytest
import rclpy
from rclpy.parameter import Parameter


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


def test_params_default_and_engine_floor(node):
    assert node.get_parameter('slip_detection_enable').value is False
    assert node._slip_detection_enable is False
    assert node.get_parameter('cliff_depth').value == pytest.approx(0.03)
    # off → engine probe-floor unverändert (cliff_probe_depth 0)
    assert node._engine.cliff_probe_depth == pytest.approx(0.0)


def test_enable_mirrors_cliff_depth_to_engine(node):
    res = node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('cliff_depth', Parameter.Type.DOUBLE, 0.035),
    ])
    assert res[0].successful
    assert node._engine.cliff_probe_depth == pytest.approx(0.035)
    # wieder aus → Floor zurück auf 0
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, False),
    ])
    assert node._engine.cliff_probe_depth == pytest.approx(0.0)


@pytest.mark.parametrize('name,ptype,value', [
    ('cliff_depth', Parameter.Type.DOUBLE, -0.01),
    ('slip_debounce_ticks', Parameter.Type.INTEGER, 0),
    ('slip_min_lost_legs', Parameter.Type.INTEGER, 0),
    ('slip_min_lost_legs', Parameter.Type.INTEGER, 7),
    ('slip_grace_stance_phase', Parameter.Type.DOUBLE, 1.0),
])
def test_invalid_params_rejected(node, name, ptype, value):
    res = node.set_parameters([Parameter(name, ptype, value)])
    assert not res[0].successful


def test_disabled_returns_false(node):
    assert node._slip_detection_enable is False
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    assert node._update_support(0.5) is False


def test_resets_when_not_walking(node):
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
    ])
    # STANDING → reset + False
    assert node._engine.state == GaitEngine.STATE_STANDING
    assert node._update_support(0.5) is False
    assert node._support_monitor.freeze_latched is False


def test_freeze_on_sustained_support_loss(node):
    # Grace 0 + debounce 2 + min 1 → ein Stance-Bein verliert Halt → Freeze.
    # Der ever_contacted-Ausschluss (T2-Fix) verlangt, dass das Bein vorher
    # Kontakt HATTE (echter Verlust/Slip, nicht ein toter Sensor von Anfang an).
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('slip_grace_stance_phase', Parameter.Type.DOUBLE, 0.0),
        Parameter('slip_debounce_ticks', Parameter.Type.INTEGER, 2),
        Parameter('slip_min_lost_legs', Parameter.Type.INTEGER, 1),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    assert node._engine.state == GaitEngine.STATE_WALKING
    # Phase 1: Kontakt etablieren (ever_contacted) — t=0.5: Gruppe B in Stance.
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = True
    node._update_support(0.5)
    # Phase 2: Halt verlieren (echter Slip/Kante) → Freeze.
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = False
    frozen = False
    for _ in range(4):
        frozen = node._update_support(0.5)
    assert frozen is True
    assert node._slip_freeze_fired is True
    assert node._support_monitor.freeze_latched is True


def test_no_freeze_when_supported(node):
    # Default-Grace 0.6, alle mit Kontakt → kein Freeze über viele Ticks.
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = True
    frozen = False
    for i in range(30):
        frozen = node._update_support(0.02 * i)
    assert frozen is False
    assert node._support_monitor.freeze_latched is False
