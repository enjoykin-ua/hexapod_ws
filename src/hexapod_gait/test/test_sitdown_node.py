"""
Block-B1-Glue-Tests für gait_node: Hinsetz-Services + Comms-Loss-Fail-safe.

Strategie (wie test_param_callback.py): GaitNode direkt instanziieren, die
Service-Handler als Methoden mit Trigger.Request/Response aufrufen (kein
Executor-Roundtrip). Engine-State wird für die Guard-Tests direkt gesetzt; der
Relay-Service ist im Unit-Test nicht verfügbar → _fire_relay skippt (wie Sim).

Deckt B1.4 (Services + Guards), B1.5 (Shutdown-Latch) und B1.6 (Comms-Loss).
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
from hexapod_kinematics import HEXAPOD
import pytest
import rclpy
from std_srvs.srv import SetBool, Trigger


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


def _rad0_joints():
    return {leg.name: (0.0, 0.0, 0.0) for leg in HEXAPOD.legs}


def _call(handler):
    """Service-Handler mit frischem Trigger.Request/Response aufrufen."""
    return handler(Trigger.Request(), Trigger.Response())


def _setbool(handler, data):
    """SetBool-Handler mit data aufrufen."""
    req = SetBool.Request()
    req.data = data
    return handler(req, SetBool.Response())


# ----- Params / Registrierung ----------------------------------------- #

def test_new_params_have_range(node):
    """Die 3 neuen B1-Params haben FloatingPointRange (rqt-Slider)."""
    for name in (
        'sitdown_duration', 'sitdown_lower_fraction',
        'comms_loss_sitdown_timeout',
    ):
        fr = node.describe_parameter(name).floating_point_range
        assert len(fr) == 1, f'{name} fehlt FloatingPointRange'
        assert fr[0].from_value < fr[0].to_value


def test_comms_loss_default_off(node):
    """Comms-Loss ist per Default aus (0)."""
    assert node._comms_loss_sitdown_timeout == 0.0


# ----- sit_down -------------------------------------------------------- #

def test_sit_down_from_standing(node):
    """Service sit_down aus STANDING startet die Sequenz (→ REPOSITION)."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _call(node._on_sit_down)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_REPOSITION
    assert node._relay_off_after_sat is False  # Rest: bestromt bleiben


def test_sit_down_passes_spawn_pose_as_rest(node):
    """Die mitgeschnittene Spawn-Pose wird als SAT-Ruhe-Pose durchgereicht."""
    spawn = {leg.name: (0.0, -0.4, 0.5) for leg in HEXAPOD.legs}
    node._spawn_joints = spawn
    _call(node._on_sit_down)
    assert node._engine._sitdown_rest_joints == spawn


def test_sit_down_rest_none_without_spawn(node):
    """Ohne mitgeschnittene Spawn-Pose → rest_joints None (Engine-Fallback)."""
    node._spawn_joints = {}
    _call(node._on_sit_down)
    assert node._engine._sitdown_rest_joints is None


def test_sit_down_rejected_when_not_standing(node):
    """Service sit_down außerhalb STANDING wird abgelehnt (kein Change)."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _call(node._on_sit_down)
    assert resp.success is False
    assert node._engine.state == GaitEngine.STATE_WALKING


# ----- stand_up -------------------------------------------------------- #

def test_stand_up_from_sat(node):
    """Service stand_up aus SAT startet das (kartesische) Aufstehen."""
    node._engine._state = GaitEngine.STATE_SAT
    node._latest_joints = _rad0_joints()
    resp = _call(node._on_stand_up)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_CARTESIAN_STANDUP


def test_stand_up_rejected_when_not_sat(node):
    """Service stand_up außerhalb SAT wird abgelehnt."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _call(node._on_stand_up)
    assert resp.success is False
    assert node._engine.state == GaitEngine.STATE_STANDING


def test_stand_up_rejected_when_latched(node):
    """Nach Shutdown (Latch) wird stand_up abgelehnt, auch aus SAT."""
    node._engine._state = GaitEngine.STATE_SAT
    node._latest_joints = _rad0_joints()
    node._shutdown_latched = True
    resp = _call(node._on_stand_up)
    assert resp.success is False
    assert 'latched' in resp.message
    assert node._engine.state == GaitEngine.STATE_SAT


def test_stand_up_rejected_without_joints(node):
    """Service stand_up ohne empfangene /joint_states wird abgelehnt."""
    node._engine._state = GaitEngine.STATE_SAT
    node._latest_joints = {}
    resp = _call(node._on_stand_up)
    assert resp.success is False


# ----- shutdown -------------------------------------------------------- #

def test_shutdown_from_sat_latches(node):
    """Service shutdown aus SAT: sofort Relay-Aus (Sim skip) + Latch."""
    node._engine._state = GaitEngine.STATE_SAT
    resp = _call(node._on_shutdown)
    assert resp.success is True
    assert node._shutdown_latched is True


def test_shutdown_from_standing_arms_relay(node):
    """Service shutdown aus STANDING: Hinsetzen + Relay-Flag (noch kein Latch)."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _call(node._on_shutdown)
    assert resp.success is True
    assert node._relay_off_after_sat is True
    assert node._shutdown_latched is False  # erst bei SAT
    assert node._engine.state == GaitEngine.STATE_REPOSITION


def test_shutdown_rejected_mid_sequence(node):
    """Service shutdown während laufender Sequenz (REPOSITION) abgelehnt."""
    node._engine._state = GaitEngine.STATE_REPOSITION
    resp = _call(node._on_shutdown)
    assert resp.success is False


# ----- Sit/Stand-Toggle (C1+ Teleop-Intent) --------------------------- #

def test_toggle_from_standing_sits(node):
    """Toggle aus STANDING → Hinsetzen (Teleop kennt State nicht)."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _call(node._on_sit_stand_toggle)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_REPOSITION


def test_toggle_from_sat_stands(node):
    """Toggle aus SAT → Aufstehen."""
    node._engine._state = GaitEngine.STATE_SAT
    node._latest_joints = _rad0_joints()
    resp = _call(node._on_sit_stand_toggle)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_CARTESIAN_STANDUP


def test_toggle_rejected_when_walking(node):
    """Toggle aus WALKING (weder STANDING noch SAT) → abgelehnt."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _call(node._on_sit_stand_toggle)
    assert resp.success is False
    assert node._engine.state == GaitEngine.STATE_WALKING


# ----- C2: Gangart cyclen + Schrittweite trimmen ---------------------- #

def test_cycle_gait_advances_and_wraps(node):
    """cycle_gait (next) läuft tripod→wave→tetrapod→ripple→tripod (Wrap)."""
    assert node._pattern.name == 'tripod'
    seq = []
    for _ in range(5):
        _setbool(node._on_cycle_gait, True)
        seq.append(node._pattern.name)
    assert seq == ['wave', 'tetrapod', 'ripple', 'tripod', 'wave']
    assert node._engine.pattern.name == 'wave'


def test_cycle_gait_prev(node):
    """cycle_gait (data=False) geht rückwärts (tripod→ripple)."""
    assert node._pattern.name == 'tripod'
    _setbool(node._on_cycle_gait, False)
    assert node._pattern.name == 'ripple'


def test_cycle_gait_rejected_when_not_standing(node):
    """cycle_gait nur in STANDING."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _setbool(node._on_cycle_gait, True)
    assert resp.success is False
    assert node._pattern.name == 'tripod'


def test_adjust_step_length_clamps(node):
    """Schrittweite +/- clampt auf [intent_min, intent_max]."""
    for _ in range(100):
        _setbool(node._on_adjust_step_length, True)
    assert node._step_length_max == pytest.approx(node._step_length_intent_max)
    assert node._engine.step_length_max == pytest.approx(
        node._step_length_intent_max
    )
    for _ in range(100):
        _setbool(node._on_adjust_step_length, False)
    assert node._step_length_max == pytest.approx(node._step_length_intent_min)


# ----- Comms-Loss-Fail-safe ------------------------------------------- #

def test_comms_loss_disabled_no_trigger(node):
    """Default (timeout 0): kein Auto-Hinsetzen, selbst bei stale cmd."""
    node._comms_loss_sitdown_timeout = 0.0
    node._last_cmd_time = 100.0
    node._check_comms_loss(now=10_000.0)
    assert node._engine.state == GaitEngine.STATE_STANDING


def test_comms_loss_triggers_when_stale(node):
    """Fail-safe: timeout>0 + cmd verstummt + STANDING → Auto-Hinsetzen."""
    node._comms_loss_sitdown_timeout = 5.0
    node._last_cmd_time = 100.0
    node._check_comms_loss(now=110.0)  # 10 s > 5 s
    assert node._engine.state == GaitEngine.STATE_REPOSITION
    assert node._relay_off_after_sat is False  # Rest, nicht Shutdown


def test_comms_loss_no_fire_without_any_cmd(node):
    """Nie ein cmd_vel empfangen (last_cmd None) → kein false-fire."""
    node._comms_loss_sitdown_timeout = 5.0
    node._last_cmd_time = None
    node._check_comms_loss(now=10_000.0)
    assert node._engine.state == GaitEngine.STATE_STANDING


def test_comms_loss_only_from_standing(node):
    """Aus WALKING feuert der Fail-safe NICHT (erst cmd_vel_timeout stoppt)."""
    node._comms_loss_sitdown_timeout = 5.0
    node._last_cmd_time = 100.0
    node._engine._state = GaitEngine.STATE_WALKING
    node._check_comms_loss(now=110.0)
    assert node._engine.state == GaitEngine.STATE_WALKING


def test_comms_loss_within_timeout_no_trigger(node):
    """Frischer cmd (< timeout) → kein Trigger."""
    node._comms_loss_sitdown_timeout = 5.0
    node._last_cmd_time = 100.0
    node._check_comms_loss(now=103.0)  # 3 s < 5 s
    assert node._engine.state == GaitEngine.STATE_STANDING
