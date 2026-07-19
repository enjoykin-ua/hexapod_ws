"""
Block I Phase 6 — E-Stop (/hexapod_estop) + Recovery (/hexapod_recover).

Zwei Ebenen (wie test_startup_ramp.py + test_sitdown_node.py):

- **Engine (pure, kein rclpy):** die Recovery-Joint-Space-Ramp aus einer
  beliebigen *gültigen* eingefrorenen Pose bleibt über den ganzen Rückweg
  innerhalb der URDF-Limits (T6.4, [D6]-Kernargument: konvexe Kombination
  zweier in-limits-Posen kann kein Limit verletzen).
- **Node (GaitNode direkt, Handler als Methoden aufgerufen):** der Freeze-Gate
  hält den Tick latched (T6.1/T6.2), Recovery ist ursachen-agnostisch
  (T6.3/T6.5), setzt Latches + Monitore zurück (T6.6) und lehnt ohne komplette
  /joint_states sauber ab (T6.7). Der Recovery-Rückweg nutzt start_ramp
  (Joint-Space, STARTUP_RAMP), NICHT start_cartesian_standup (CARTESIAN_STANDUP).
"""

import time
from unittest.mock import MagicMock

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest
import rclpy
from std_srvs.srv import Trigger


_TRIPOD = GAIT_PRESETS['tripod']


# Echte strikt-symmetrische URDF-Joint-Limits (wie test_startup_ramp.py):
# coxa ±0.415, femur ±1.57, tibia -0.28/+2.50. Quelle: config.py +
# hexapod.ros2_control.xacro (leg_changes). NICHT die config.py-Slope-Defaults.
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

_BOUNDS = (
    (_URDF_LIMITS.coxa_lower, _URDF_LIMITS.coxa_upper),
    (_URDF_LIMITS.femur_lower, _URDF_LIMITS.femur_upper),
    (_URDF_LIMITS.tibia_lower, _URDF_LIMITS.tibia_upper),
)


def _make_engine() -> GaitEngine:
    """Engine mit den leg_changes-Stand-Pose-Defaults (mittel-Stance)."""
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.04,
        cycle_time=2.0,
        radial_distance=0.145,
        body_height=-0.10,
        step_length_max=0.03,
    )


# Eine plausible eingefrorene Mid-Walk-Pose je Bein, klar innerhalb der Limits.
_FROZEN_MIDWALK = {leg.name: (0.20, -0.50, 0.90) for leg in HEXAPOD.legs}

# Eine eingefrorene Pose NAHE den Limits (aber gültig): stresst das
# konvexe-Kombination-Argument — selbst von einer extremen gültigen Startpose
# aus bleibt der Lerp in den Stand in-limits.
_FROZEN_NEAR_LIMIT = {leg.name: (0.40, -1.50, 2.40) for leg in HEXAPOD.legs}


def _assert_ramp_in_limits(engine: GaitEngine, duration: float) -> None:
    """Alle 18 Joints über 21 Ramp-Stichproben (inkl. Endpunkte) in-limits."""
    for k in range(21):
        t = k * (duration / 20.0)
        angles = engine.compute_joint_angles(t)
        for leg in HEXAPOD.legs:
            for i in range(3):
                lo, hi = _BOUNDS[i]
                v = angles[leg.name][i]
                assert lo <= v <= hi, (
                    f'{leg.name} joint {i} = {v:.4f} out of limits '
                    f'[{lo}, {hi}] at t={t:.3f}'
                )
        # compute_joint_angles auto-transitions zu STANDING bei progress>=1;
        # re-arm, damit die nächste Stichprobe weiter im Ramp ausgewertet wird.
        if engine.state == GaitEngine.STATE_STANDING:
            engine._state = GaitEngine.STATE_STARTUP_RAMP


# ===================================================================== #
# Engine-Ebene — T6.4: Ramp verletzt kein Joint-Limit
# ===================================================================== #


def test_recover_ramp_stays_in_limits_from_midwalk_pose():
    """T6.4: Recovery-Ramp aus Mid-Walk-Pose bleibt komplett in-limits."""
    engine = _make_engine()
    engine.start_ramp(_FROZEN_MIDWALK, t=0.0, duration=3.0)
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP
    _assert_ramp_in_limits(engine, duration=3.0)


def test_recover_ramp_stays_in_limits_from_near_limit_pose():
    """
    T6.4: selbst aus einer near-limit (gültigen) Pose bleibt der Lerp in-limits.

    [D6]-Kernargument: der Rückweg ist die konvexe Kombination zweier
    in-limits-Posen pro Gelenk → kann die Box-Limits nicht verlassen.
    """
    engine = _make_engine()
    # Sanity: die Startpose selbst ist in-limits.
    for leg in HEXAPOD.legs:
        for i in range(3):
            lo, hi = _BOUNDS[i]
            assert lo <= _FROZEN_NEAR_LIMIT[leg.name][i] <= hi
    engine.start_ramp(_FROZEN_NEAR_LIMIT, t=0.0, duration=3.0)
    _assert_ramp_in_limits(engine, duration=3.0)


def test_recover_ramp_endpoint_is_stand_pose():
    """Ramp-Ende == Stand-Pose-IK für alle 6 Beine (Recovery landet im Stand)."""
    engine = _make_engine()
    engine.start_ramp(_FROZEN_MIDWALK, t=0.0, duration=3.0)
    out_end = engine.compute_joint_angles(t=3.0)
    target = engine._compute_stand_pose_joints()
    for leg in HEXAPOD.legs:
        for i in range(3):
            assert out_end[leg.name][i] == pytest.approx(
                target[leg.name][i], abs=1e-9
            )


# ===================================================================== #
# Node-Ebene — Freeze-Gate + Recovery-Service
# ===================================================================== #


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
    """Vollständige, gültige /joint_states-Pose (alle 6 Beine, rad 0)."""
    return {leg.name: (0.0, 0.0, 0.0) for leg in HEXAPOD.legs}


def _call(handler):
    return handler(Trigger.Request(), Trigger.Response())


# ----- E-Stop + Freeze-Gate (T6.1 / T6.2) ----------------------------- #

def test_estop_sets_frozen(node):
    """E-Stop-Service setzt _safety_frozen + meldet Erfolg."""
    assert node._safety_frozen is False
    resp = _call(node._on_estop)
    assert resp.success is True
    assert node._safety_frozen is True
    assert 'E-STOP' in resp.message


def test_freeze_gate_blocks_tick(node):
    """
    T6.1: bei _safety_frozen hält der Tick vor dem pre-Ramp-Guard (latched).

    Beweis über den pre-Ramp-Guard: _ramp_triggered=False + abgelaufener
    Timeout würde _joint_states_timeout_logged setzen — passiert NUR, wenn
    der Tick den Freeze-Gate passiert. Bei Freeze bleibt es False.
    """
    node._safety_frozen = True
    node._ramp_triggered = False
    node._joint_states_timeout_logged = False
    node._t_start = time.monotonic() - 999.0
    node._tick()
    assert node._joint_states_timeout_logged is False


def test_tick_proceeds_when_not_frozen(node):
    """Gate ist transparent: ohne Freeze läuft der Tick über den Gate hinaus."""
    node._safety_frozen = False
    node._ramp_triggered = False
    node._joint_states_timeout_logged = False
    node._t_start = time.monotonic() - 999.0
    node._tick()
    # Erreicht den pre-Ramp-Guard → Timeout-WARN gesetzt = Tick nicht gegatet.
    assert node._joint_states_timeout_logged is True


def test_estop_gates_tick_no_set_command(node):
    """T6.2: nach E-Stop ruft der Tick set_command NICHT (kein Kommandieren)."""
    node._ramp_triggered = True  # pre-Ramp-Guard passiert (falls Gate offen)
    node._engine.set_command = MagicMock()
    _call(node._on_estop)
    node._tick()
    node._engine.set_command.assert_not_called()


# ----- Recovery (T6.3 / T6.5 / T6.6 / T6.7) --------------------------- #

def test_recover_from_frozen_standing(node):
    """T6.3: Recovery aus eingefrorenem STANDING → Joint-Space-Ramp (STARTUP)."""
    node._latest_joints = _rad0_joints()
    _call(node._on_estop)
    assert node._safety_frozen is True
    resp = _call(node._on_recover)
    assert resp.success is True
    assert node._safety_frozen is False
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP
    assert 'ramp' in resp.message


def test_recover_is_cause_agnostic_from_walking(node):
    """T6.5: Recovery funktioniert auch aus (eingefrorenem) WALKING."""
    node._latest_joints = _rad0_joints()
    node._engine._state = GaitEngine.STATE_WALKING
    node._safety_frozen = True
    resp = _call(node._on_recover)
    assert resp.success is True
    assert node._safety_frozen is False
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_recover_uses_joint_space_not_cartesian(node):
    """[D6]: Recovery rampt Joint-Space (STARTUP_RAMP), NICHT cartesian."""
    node._latest_joints = _rad0_joints()
    node._safety_frozen = True
    # Auch wenn der Boot-Standup-Modus cartesian ist, muss Recovery joint-space
    # nehmen (start_ramp → STARTUP_RAMP; start_cartesian_standup → CARTESIAN).
    node._standup_mode = 'cartesian'
    _call(node._on_recover)
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP
    assert node._engine.state != GaitEngine.STATE_CARTESIAN_STANDUP


def test_recover_resets_latches_and_monitors(node):
    """T6.6: Recovery setzt Freeze/Tip/Slip-Latches + alle 4 Monitore zurück."""
    node._latest_joints = _rad0_joints()
    node._safety_frozen = True
    node._tip_crit_fired = True
    node._slip_freeze_fired = True
    node._balance.reset = MagicMock()
    node._slope_est.reset = MagicMock()
    node._support_monitor.reset = MagicMock()
    node._tip_monitor.reset = MagicMock()

    resp = _call(node._on_recover)

    assert resp.success is True
    assert node._safety_frozen is False
    assert node._tip_crit_fired is False
    assert node._slip_freeze_fired is False
    node._balance.reset.assert_called_once()
    node._slope_est.reset.assert_called_once()
    node._support_monitor.reset.assert_called_once()
    node._tip_monitor.reset.assert_called_once()


def test_recover_rejected_without_joints(node):
    """T6.7: Recovery ohne komplette /joint_states → sauberer Reject."""
    node._latest_joints = {}
    node._safety_frozen = True
    resp = _call(node._on_recover)
    assert resp.success is False
    assert 'joint_states' in resp.message
    # Kein halber Rückweg: State unverändert, Freeze bleibt scharf.
    assert node._engine.state != GaitEngine.STATE_STARTUP_RAMP
    assert node._safety_frozen is True


def test_recover_rejected_when_shutdown_latched(node):
    """Recovery nach Shutdown-Latch abgelehnt (wie stand_up)."""
    node._latest_joints = _rad0_joints()
    node._shutdown_latched = True
    resp = _call(node._on_recover)
    assert resp.success is False
    assert 'latched' in resp.message
    assert node._engine.state != GaitEngine.STATE_STARTUP_RAMP


def test_recover_duration_param_has_range(node):
    """recover_duration ist deklariert mit FloatingPointRange (rqt-Slider)."""
    fr = node.describe_parameter('recover_duration').floating_point_range
    assert len(fr) == 1
    assert fr[0].from_value < fr[0].to_value
    assert node._recover_duration == pytest.approx(3.0)
