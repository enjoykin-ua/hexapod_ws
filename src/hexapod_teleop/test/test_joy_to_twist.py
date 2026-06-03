"""
Tests für joy_to_twist (C1+) — Mapping, Dead-Man, Höhe, Edge, Intents.

Strategie wie test_param_callback (hexapod_gait): Node direkt instanziieren,
die reinen Helfer + den Joy-Callback mit gebauten Joy-Messages aufrufen.
Service-Clients werden durch ein Fake ersetzt (zählt call_async). Long-Press-
Timing wird über den injizierten ``now``-Parameter getestet (keine echte Uhr).
"""

from hexapod_teleop.joy_to_twist import JoyToTwist
import pytest
import rclpy
from sensor_msgs.msg import Joy


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = JoyToTwist()
    yield n
    n.destroy_node()


class _FakeClient:
    """Service-Client-Ersatz: zählt call_async, ready konfigurierbar."""

    def __init__(self, ready=True):
        self.count = 0
        self._ready = ready

    def service_is_ready(self):
        return self._ready

    def call_async(self, _req):
        self.count += 1


def _joy(lx=0.0, ly=0.0, rx=0.0, l2=1.0, r2=1.0, buttons=None):
    """Joy-Message bauen. l2/r2 idle = +1.0; buttons = Liste gedrückter Indizes."""
    m = Joy()
    axes = [0.0] * 8
    axes[0] = lx
    axes[1] = ly
    axes[3] = rx
    axes[2] = l2
    axes[5] = r2
    m.axes = axes
    b = [0] * 12
    for i in buttons or []:
        b[i] = 1
    m.buttons = b
    return m


_R1 = 5   # Dead-Man
_L1 = 4   # slow
_TRI = 2
_CIRC = 1
_CROSS = 0


# ----- Stick → Twist -------------------------------------------------- #

def test_no_motion_without_deadman(node):
    """Ohne Dead-Man (R1) ist der Twist 0, auch bei vollem Stick."""
    t = node._twist_from_joy(_joy(ly=1.0, lx=1.0, rx=1.0))
    assert t.linear.x == 0.0 and t.linear.y == 0.0 and t.angular.z == 0.0


def test_forward_with_deadman(node):
    """R1 + Stick hoch → linear.x = +linear_x_scale."""
    t = node._twist_from_joy(_joy(ly=1.0, buttons=[_R1]))
    assert t.linear.x == pytest.approx(node._linear_x_scale)
    assert t.linear.y == 0.0


def test_sidestep_and_turn(node):
    """Linker Stick X → linear.y, rechter Stick X → angular.z (mit R1)."""
    t = node._twist_from_joy(_joy(lx=1.0, rx=1.0, buttons=[_R1]))
    assert t.linear.y == pytest.approx(node._linear_y_scale)
    assert t.angular.z == pytest.approx(node._angular_z_scale)


def test_deadzone_suppresses_drift(node):
    """Stick-Wert unter Deadzone → 0."""
    small = node._deadzone * 0.5
    t = node._twist_from_joy(_joy(ly=small, buttons=[_R1]))
    assert t.linear.x == 0.0


def test_slow_modifier_scales(node):
    """L1 gehalten → Skalen × slow_factor."""
    t = node._twist_from_joy(_joy(ly=1.0, buttons=[_R1, _L1]))
    assert t.linear.x == pytest.approx(
        node._linear_x_scale * node._slow_factor
    )


# ----- Höhe (Clamp) --------------------------------------------------- #

def test_height_clamped_to_max(node):
    """Viele +Schritte → auf body_height_max geclampt."""
    for _ in range(100):
        node._adjust_body_height(+1)
    assert node._target_body_height == pytest.approx(node._body_height_max)


def test_height_clamped_to_min(node):
    """Viele -Schritte → auf body_height_min geclampt."""
    for _ in range(100):
        node._adjust_body_height(-1)
    assert node._target_body_height == pytest.approx(node._body_height_min)


# ----- Edge / Long-Press ---------------------------------------------- #

def test_rising_edge(node):
    """_rising_edge liefert True nur beim Übergang nicht→gedrückt."""
    assert node._rising_edge(_TRI, False) is False
    assert node._rising_edge(_TRI, True) is True
    assert node._rising_edge(_TRI, True) is False   # gehalten, kein Edge
    assert node._rising_edge(_TRI, False) is False
    assert node._rising_edge(_TRI, True) is True


def test_longpress_fires_once_after_duration(node):
    """_longpress feuert einmalig nach longpress_sec, reset beim Loslassen."""
    d = node._longpress_sec
    assert node._longpress(_CIRC, True, 0.0) is False
    assert node._longpress(_CIRC, True, d - 0.01) is False
    assert node._longpress(_CIRC, True, d + 0.01) is True
    assert node._longpress(_CIRC, True, d + 0.5) is False  # schon gefeuert
    assert node._longpress(_CIRC, False, d + 0.6) is False  # reset
    assert node._longpress(_CIRC, True, d + 0.6) is False  # neuer Start
    assert node._longpress(_CIRC, True, d + 0.6 + d) is True


# ----- Intents -------------------------------------------------------- #

def test_call_intent_fires_when_ready(node):
    """_call_intent ruft call_async wenn Service ready."""
    fake = _FakeClient(ready=True)
    node._call_intent(fake, 'sit_stand_toggle')
    assert fake.count == 1


def test_call_intent_noop_when_unavailable(node):
    """Service nicht verfügbar → kein Call, kein Crash."""
    fake = _FakeClient(ready=False)
    node._toggle_logged = False
    node._call_intent(fake, 'toggle')
    assert fake.count == 0


def test_triangle_press_calls_toggle(node):
    """Triangle (Rising-Edge) im Joy-Callback → Toggle-Intent gesendet."""
    node._toggle_client = _FakeClient(ready=True)
    node._on_joy(_joy(buttons=[_TRI]))
    assert node._toggle_client.count == 1
    # gehalten (kein neuer Edge) → kein weiterer Call
    node._on_joy(_joy(buttons=[_TRI]))
    assert node._toggle_client.count == 1
