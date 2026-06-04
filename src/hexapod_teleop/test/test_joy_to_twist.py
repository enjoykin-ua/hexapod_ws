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
        self.last = None
        self._ready = ready

    def service_is_ready(self):
        return self._ready

    def call_async(self, req):
        self.count += 1
        self.last = getattr(req, 'data', None)


def _joy(lx=0.0, ly=0.0, rx=0.0, l2=1.0, r2=1.0, dpad_x=0.0, dpad_y=0.0,
         buttons=None):
    """Joy-Message bauen. l2/r2 idle = +1.0; buttons = Liste gedrückter Indizes."""
    m = Joy()
    axes = [0.0] * 8
    axes[0] = lx
    axes[1] = ly
    axes[3] = rx
    axes[2] = l2
    axes[5] = r2
    axes[6] = dpad_x
    axes[7] = dpad_y
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


# ----- D-Pad (C2: Gangart / Schrittweite) ----------------------------- #

def test_dpad_right_cycles_gait_next(node):
    """D-Pad rechts (raw -1) → cycle_gait next (data=True)."""
    node._cycle_gait_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_x=-1.0))
    assert node._cycle_gait_client.count == 1
    assert node._cycle_gait_client.last is True


def test_dpad_left_cycles_gait_prev(node):
    """D-Pad links (raw +1) → cycle_gait prev (data=False)."""
    node._cycle_gait_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_x=1.0))
    assert node._cycle_gait_client.last is False


def test_dpad_up_step_bigger(node):
    """D-Pad hoch (raw +1) → adjust_step_length größer (data=True)."""
    node._step_length_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_y=1.0))
    assert node._step_length_client.last is True


def test_dpad_down_step_smaller(node):
    """D-Pad runter (raw -1) → adjust_step_length kleiner (data=False)."""
    node._step_length_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_y=-1.0))
    assert node._step_length_client.last is False


def test_dpad_hold_no_refire(node):
    """D-Pad gehalten → nur ein Call; Release+Repress feuert erneut (Lockout 0)."""
    node._dpad_lockout_sec = 0.0   # Debounce aus → reine Edge-Logik prüfen
    node._cycle_gait_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_x=-1.0))
    node._on_joy(_joy(dpad_x=-1.0))   # gehalten
    assert node._cycle_gait_client.count == 1
    node._on_joy(_joy(dpad_x=0.0))    # loslassen
    node._on_joy(_joy(dpad_x=-1.0))   # neuer Edge
    assert node._cycle_gait_client.count == 2


def test_dpad_debounce_blocks_double(node):
    """Debounce: sofortiges 0→1→0→1 (HAT-Flackern) feuert nur EINMAL."""
    node._dpad_lockout_sec = 0.3   # Default; Test läuft in µs → 2. Trigger blockt
    node._cycle_gait_client = _FakeClient(ready=True)
    node._on_joy(_joy(dpad_x=-1.0))   # Edge 1 → feuert
    node._on_joy(_joy(dpad_x=0.0))    # kurz über 0 (Flackern)
    node._on_joy(_joy(dpad_x=-1.0))   # Edge 2 sofort → vom Lockout geblockt
    assert node._cycle_gait_client.count == 1


# ----- Block B4 — Show-Pose (Cross-Toggle + /cmd_show-Mapping) -------- #

def _joy_show(lx=0.0, ly=0.0, rx=0.0, ry=0.0, l2=1.0, r2=1.0, buttons=None):
    """Joy mit R-Stick-Y (axis 4) + Triggern (axis 2/5) für die Show-Tests."""
    m = Joy()
    axes = [0.0] * 8
    axes[0] = lx
    axes[1] = ly
    axes[3] = rx
    axes[4] = ry
    axes[2] = l2   # L2 (idle +1.0)
    axes[5] = r2   # R2 (idle +1.0)
    axes[6] = 0.0
    axes[7] = 0.0
    m.axes = axes
    b = [0] * 12
    for i in buttons or []:
        b[i] = 1
    m.buttons = b
    return m


def test_show_pose_hook_calls_toggle(node):
    """Cross-Long-Press-Hook ruft den /hexapod_show_toggle-Intent."""
    node._show_toggle_client = _FakeClient(ready=True)
    node._show_pose_hook()
    assert node._show_toggle_client.count == 1


def test_show_from_joy_zero_without_deadman(node):
    """Ohne R1 (Dead-Man) → /cmd_show = [0]*6 (auch bei gedrückten Triggern)."""
    arr = node._show_from_joy(
        _joy_show(lx=1.0, ly=1.0, rx=1.0, ry=1.0, l2=-1.0, r2=-1.0)
    )
    assert list(arr.data) == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_show_from_joy_maps_sticks_with_deadman(node):
    """R1 gehalten: [l6_lat,l6_vert,l6_radial,l1_lat,l1_vert,l1_radial]."""
    node._sign_show_lat = 1.0
    node._sign_show_vert = 1.0
    arr = node._show_from_joy(
        _joy_show(lx=1.0, ly=0.5, rx=-1.0, ry=0.3, buttons=[_R1])
    )
    # Trigger idle → radial 0.
    assert list(arr.data) == pytest.approx([1.0, 0.5, 0.0, -1.0, 0.3, 0.0])


def test_show_from_joy_trigger_radial(node):
    """L2/R2 (analog) → radialer Offset pro Bein (R1-gated)."""
    node._sign_show_radial = 1.0
    # L2 voll gedrückt (-1.0 → frac 1.0), R2 idle (+1.0 → 0).
    arr = node._show_from_joy(_joy_show(l2=-1.0, r2=1.0, buttons=[_R1]))
    assert arr.data[2] == pytest.approx(1.0)   # leg_6 radial
    assert arr.data[5] == pytest.approx(0.0)   # leg_1 radial
    # R2 halb gedrückt (0.0 → frac 0.5).
    arr = node._show_from_joy(_joy_show(l2=1.0, r2=0.0, buttons=[_R1]))
    assert arr.data[2] == pytest.approx(0.0)
    assert arr.data[5] == pytest.approx(0.5)


def test_show_from_joy_deadzone(node):
    """Stick-Werte unter Deadzone → 0 (auch mit Dead-Man)."""
    arr = node._show_from_joy(
        _joy_show(lx=0.05, ly=0.05, rx=0.05, ry=0.05, buttons=[_R1])
    )
    assert list(arr.data) == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_show_from_joy_vertical_sign(node):
    """sign_show_vert invertiert die Vertikal-Achsen (l6_vert=[1]/l1_vert=[4])."""
    node._sign_show_vert = -1.0
    arr = node._show_from_joy(_joy_show(ly=0.5, ry=0.4, buttons=[_R1]))
    assert arr.data[1] == pytest.approx(-0.5)
    assert arr.data[4] == pytest.approx(-0.4)


def test_on_joy_publishes_cmd_show(node):
    """_on_joy publisht /cmd_show jeden Callback (zustandsloser Teleop)."""
    node._cmd_show_pub = _FakeClient(ready=True)
    node._cmd_show_pub.publish = lambda msg: setattr(
        node._cmd_show_pub, 'last', list(msg.data))
    node._on_joy(_joy_show(lx=1.0, buttons=[_R1]))
    assert node._cmd_show_pub.last[0] == pytest.approx(1.0)
    assert len(node._cmd_show_pub.last) == 6


def test_body_height_suppressed_while_deadman(node):
    """B4.11: R2-Höhenverstellung NUR ohne R1 (mit R1 = Curl, kein Höhen-Edge)."""
    start = node._target_body_height
    # Mit R1 gehalten: R2-Edge darf die Höhe NICHT ändern.
    node._on_joy(_joy_show(r2=-1.0, buttons=[_R1]))
    assert node._target_body_height == pytest.approx(start)
    # Ohne R1: R2-Edge hebt die Höhe (Reset des Edge-State über idle-Frame).
    node._on_joy(_joy_show(r2=1.0))     # idle → _r2_was False
    node._on_joy(_joy_show(r2=-1.0))    # Edge → +1 step (raise)
    assert node._target_body_height > start
