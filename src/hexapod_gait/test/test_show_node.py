"""
Block-B4-Glue-Tests für gait_node: Show-Pose-Toggle + /cmd_show-Offsets.

Strategie (wie test_sitdown_node.py): GaitNode direkt instanziieren, die
Service-/Subscriber-Handler als Methoden aufrufen (kein Executor-Roundtrip).
Engine-State wird für Guard-Tests direkt gesetzt.

Deckt B4.4 (Toggle-Service + Guards, /cmd_show-Subscriber + Skalierung +
Staleness, Params).
"""

import time

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
import pytest
import rclpy
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import Trigger


_SHOW_PARAMS = (
    'show_enter_duration', 'show_exit_duration', 'show_body_shift_back',
    'show_shift_fraction', 'show_safety_margin', 'show_front_radial',
    'show_front_z', 'show_return_rate', 'show_lat_scale', 'show_vert_scale',
)


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


def _toggle(node):
    return node._on_show_toggle(Trigger.Request(), Trigger.Response())


# ----- Params --------------------------------------------------------- #

def test_show_params_have_range(node):
    """Alle 10 Show-Params haben FloatingPointRange (rqt-Slider)."""
    for name in _SHOW_PARAMS:
        fr = node.describe_parameter(name).floating_point_range
        assert len(fr) == 1, f'{name} fehlt FloatingPointRange'
        assert fr[0].from_value < fr[0].to_value


def test_show_param_defaults(node):
    """Defaults entsprechen der B4.0/B4.2-Empfehlung."""
    assert node._show_body_shift_back == pytest.approx(0.065)
    assert node._show_shift_fraction == pytest.approx(0.5)
    assert node._show_safety_margin == pytest.approx(0.030)


# ----- Toggle --------------------------------------------------------- #

def test_show_toggle_from_standing_enters(node):
    """Toggle aus STANDING → SHOW_ENTER."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_ENTER


def test_show_toggle_from_active_exits(node):
    """Toggle aus SHOW_ACTIVE → SHOW_EXIT (Round-Trip raus)."""
    node._engine._state = GaitEngine.STATE_SHOW_ACTIVE
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_EXIT


def test_show_toggle_from_enter_exits(node):
    """Toggle mitten in SHOW_ENTER → SHOW_EXIT (auch aus Enter herausführbar)."""
    node._engine._state = GaitEngine.STATE_SHOW_ENTER
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_EXIT


def test_show_toggle_rejected_when_walking(node):
    """Toggle aus WALKING wird abgelehnt (kein State-Change)."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _toggle(node)
    assert resp.success is False
    assert node._engine.state == GaitEngine.STATE_WALKING


def test_show_toggle_resets_cmd_show_on_enter(node):
    """Beim Eintreten werden alte Stick-Werte verworfen (Neutral-Start)."""
    node._cmd_show = [1.0, 1.0, 1.0, 1.0]
    _toggle(node)
    assert node._cmd_show == [0.0, 0.0, 0.0, 0.0]


# ----- /cmd_show-Subscriber ------------------------------------------- #

def test_cmd_show_caches_four_values(node):
    """/cmd_show speichert die 4 Werte + Timestamp."""
    msg = Float64MultiArray()
    msg.data = [0.5, -0.5, 0.25, 0.75]
    node._on_cmd_show(msg)
    assert node._cmd_show == [0.5, -0.5, 0.25, 0.75]
    assert node._last_cmd_show_time is not None


def test_cmd_show_ignores_malformed(node):
    """Zu kurzes Array → ignoriert (kein State-Change)."""
    node._cmd_show = [0.0, 0.0, 0.0, 0.0]
    msg = Float64MultiArray()
    msg.data = [0.1, 0.2]
    node._on_cmd_show(msg)
    assert node._cmd_show == [0.0, 0.0, 0.0, 0.0]


# ----- /cmd_show → Engine-Offsets (Skalierung + Staleness) ------------ #

def test_update_show_offsets_scales_and_maps(node):
    """Stick→Meter-Skalierung + Mapping leg6/leg1 an die Engine."""
    node._show_lat_scale = 0.06
    node._show_vert_scale = 0.05
    node._cmd_show = [1.0, -1.0, -0.5, 0.5]  # [l6_lat,l6_vert,l1_lat,l1_vert]
    node._last_cmd_show_time = time.monotonic()
    node._update_show_offsets(time.monotonic())
    tgt = node._engine._show_offset_target
    assert tgt['leg_6'] == pytest.approx((0.06, -0.05))
    assert tgt['leg_1'] == pytest.approx((-0.03, 0.025))


def test_update_show_offsets_stale_zeroes(node):
    """Ohne frisches /cmd_show (Disconnect) → Offsets 0 (Rückkehr Neutral)."""
    node._show_lat_scale = 0.06
    node._show_vert_scale = 0.06
    node._cmd_show = [1.0, 1.0, 1.0, 1.0]
    # Timestamp weit in der Vergangenheit → stale.
    node._last_cmd_show_time = time.monotonic() - 10.0
    node._update_show_offsets(time.monotonic())
    tgt = node._engine._show_offset_target
    assert tgt['leg_6'] == pytest.approx((0.0, 0.0))
    assert tgt['leg_1'] == pytest.approx((0.0, 0.0))
