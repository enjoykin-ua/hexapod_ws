"""
Tests für Phase 13 Stage 0.7 — STATE_CARTESIAN_STANDUP in gait_engine.

Kartesisches schürffreies Aufstehen vom Bauch in zwei Phasen:
  Phase 1 (Touchdown): Füße kartesisch von power_on_mid → Boden-Aufsetzpunkt
    (radial, 0, body_height_start). Bauch trägt, Füße unbelastet/in der Luft.
  Phase 2 (Push): x+y fix, nur body_height rampt → Körper hebt senkrecht über
    den fixen Füßen, kein Schürfen.

Pure-Python (pytest, kein rclpy). Deckt §6.1 des Plans
phase_13_stage_0_7_cartesian_standup_plan.md ab:
- Pfad in URDF-Limits (beide Phasen) + erreichbar (kein IKError)
- Phase 2: Fuß-x+y konstant (Schürf-frei-Beweis) + body_height monoton
- Phase 1: kein vorzeitiger Bodenkontakt (Bauch trägt, Coxa fix)
- Endpose == Stand-Pose; cmd_vel ignoriert; Param-Validierung
"""

import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits, leg_fk, leg_ik
import pytest


_TRIPOD = GAIT_PRESETS['tripod']

# ECHTE URDF-Joint-Limits (wie das Plugin via set_joint_limits): coxa ±0.415,
# femur ±1.57, tibia -0.28/+2.50 (leg_changes, strikt-symmetrisch aus config.py
# + hexapod.ros2_control.xacro). NICHT die config.py-Slope-Defaults — die
# IK-Slope haengt von den Limits ab (Memory two_joint_limit_sources).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

# power_on_mid (1500 us) rad pro Bein — Quelle: tools/standup_envelope_check.py /
# test_startup_ramp.py::_POWER_ON_MID (leg_changes S2/S3.1-Cal). Bei Neu-Cal nachziehen.
_POWER_ON_MID = {
    'leg_1': (-0.0692, -0.7732, 0.8491),
    'leg_2': (0.1556, -0.9523, 0.9089),
    'leg_3': (-0.1115, -0.8431, 1.0046),
    'leg_4': (0.0259, -0.8157, 1.0485),
    'leg_5': (0.1037, -0.8276, 0.9745),
    'leg_6': (0.0519, -0.7697, 0.8464),
}

# Geometrie (hexapod_physical_properties.xacro + config.py); fuer den
# Phase-1-Welt-z-Check. body_height_box/2 = Coxa-Hoehe bei aufliegendem Bauch.
_BODY_HEIGHT_BOX = 0.043
_FOOT_RADIUS = 0.008
_COXA_Z_BELLY = _BODY_HEIGHT_BOX / 2.0          # 0.0215 m
# Cartesian standup operiert an der BREITEN standup_radial (Touchdown bei
# Bauch-Hoehe braucht >=0.16 wg. Femur-±1.57; danach narrowt die Reposition
# auf Walk 0.145). Alt war _RADIAL == alte standup_radial 0.295.
_BH_START = -0.0135
_RADIAL = 0.17
_BH_FINAL = -0.10
_DURATION = 4.0
_PHASE1_FRAC = 0.4


def _make_engine(with_limits: bool = True) -> GaitEngine:
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.04,
        cycle_time=2.0,
        radial_distance=_RADIAL,
        body_height=_BH_FINAL,
        step_length_max=0.03,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs}
        if with_limits else None,
    )


def _start(engine: GaitEngine) -> None:
    engine.start_cartesian_standup(
        dict(_POWER_ON_MID), t=0.0, duration=_DURATION,
        phase1_fraction=_PHASE1_FRAC, body_height_start=_BH_START,
    )


def _samples(n: int = 41):
    """t-Werte über die ganze Rampe (inkl. Endpunkt)."""
    return [i * _DURATION / (n - 1) for i in range(n)]


def _in_limits(angles, lim: JointLimits) -> bool:
    c, f, t = angles
    return (
        lim.coxa_lower - 1e-6 <= c <= lim.coxa_upper + 1e-6
        and lim.femur_lower - 1e-6 <= f <= lim.femur_upper + 1e-6
        and lim.tibia_lower - 1e-6 <= t <= lim.tibia_upper + 1e-6
    )


# --- State + Trigger --------------------------------------------------------

def test_initial_state_is_cartesian_standup():
    engine = _make_engine()
    _start(engine)
    assert engine.state == GaitEngine.STATE_CARTESIAN_STANDUP


def test_auto_transitions_to_standing_at_end():
    engine = _make_engine()
    _start(engine)
    engine.compute_joint_angles(_DURATION + 0.1)
    assert engine.state == GaitEngine.STATE_STANDING


# --- §6.1 In-Limits + Reachability über den ganzen Pfad ---------------------

def test_cartesian_standup_path_in_limits():
    """Jeder Zwischensample × 18 Joints ∈ URDF-Limits (kein HW-Freeze)."""
    engine = _make_engine()
    _start(engine)
    for t in _samples():
        angles = engine.compute_joint_angles(t)
        for name, ang in angles.items():
            assert _in_limits(ang, _URDF_LIMITS), (
                f'{name} out of limits at t={t:.3f}: {ang}'
            )


def test_cartesian_standup_reachable_no_ikerror():
    """Mit aktiven Limits wirft der ganze Pfad keinen IKError."""
    engine = _make_engine(with_limits=True)
    _start(engine)
    for t in _samples():
        engine.compute_joint_angles(t)  # raises IKError on violation


# --- §6.1 Phase 2: Schürf-frei-Beweis (Fuß-x+y konstant) --------------------

def _phase2_ts():
    return [t for t in _samples(81)
            if t / _DURATION >= _PHASE1_FRAC + 1e-9 and t < _DURATION - 1e-9]


def test_phase2_foot_xy_constant():
    """In Phase 2 ist die radiale Fuß-Position (und y) konstant = Schürf-frei."""
    engine = _make_engine()
    _start(engine)
    for leg in HEXAPOD.legs:
        for t in _phase2_ts():
            angles = engine.compute_joint_angles(t)
            foot = leg_fk(*angles[leg.name], leg)
            rx = math.hypot(foot[0], foot[1])
            assert abs(rx - _RADIAL) < 1e-6, (
                f'{leg.name} radial drift in phase 2 at t={t:.3f}: '
                f'rx={rx:.6f} != {_RADIAL}'
            )
            assert abs(foot[1]) < 1e-6, (
                f'{leg.name} y-drift in phase 2 at t={t:.3f}: y={foot[1]:.6f}'
            )


def test_phase2_body_height_monotonic():
    """Fuß-z (= body_height) fällt monoton von bh_start nach bh_final."""
    engine = _make_engine()
    _start(engine)
    prev = None
    for t in _phase2_ts():
        angles = engine.compute_joint_angles(t)
        z = leg_fk(*angles['leg_1'], HEXAPOD.legs[0])[2]
        if prev is not None:
            assert z <= prev + 1e-9, f'body_height not monotonic at t={t:.3f}'
        prev = z


# --- §6.1 Phase 1: kein vorzeitiger Bodenkontakt ----------------------------

def test_phase1_no_premature_ground_contact():
    """
    Phase 1: kein vorzeitiger Bodenkontakt (Bauch trägt, Coxa fix).

    In Phase 1 trägt der Bauch (Coxa fix bei _COXA_Z_BELLY); der Fuß fällt.
    Fuß-Welt-z muss >= Foot-Radius bleiben bis zum Touchdown — sonst würde
    Phase 1 selbst schürfen.
    """
    engine = _make_engine()
    _start(engine)
    phase1_ts = [t for t in _samples(81) if t / _DURATION < _PHASE1_FRAC]
    for leg in HEXAPOD.legs:
        for t in phase1_ts:
            angles = engine.compute_joint_angles(t)
            foot_z = leg_fk(*angles[leg.name], leg)[2]
            world_z = _COXA_Z_BELLY + foot_z
            assert world_z >= _FOOT_RADIUS - 1e-4, (
                f'{leg.name} premature ground contact at t={t:.3f}: '
                f'world_z={world_z * 1000:.2f} mm < foot_radius'
            )


def test_touchdown_reaches_ground():
    """Am Phase-1-Ende (Touchdown) sitzt der Fuß genau auf Boden-Niveau."""
    engine = _make_engine()
    _start(engine)
    t_touchdown = _PHASE1_FRAC * _DURATION
    angles = engine.compute_joint_angles(t_touchdown)
    for leg in HEXAPOD.legs:
        foot_z = leg_fk(*angles[leg.name], leg)[2]
        world_z = _COXA_Z_BELLY + foot_z
        assert abs(world_z - _FOOT_RADIUS) < 1e-6, (
            f'{leg.name} touchdown not at ground: world_z={world_z * 1000:.2f} mm'
        )


# --- §6.1 Endpose == Stand-Pose ---------------------------------------------

def test_endpoint_is_stand_pose():
    """Ramp-Ende == Stand-Pose-IK (radial 0.17 / bh -0.10) für alle Beine."""
    engine = _make_engine()
    _start(engine)
    angles = engine.compute_joint_angles(_DURATION)
    for leg in HEXAPOD.legs:
        expected = leg_ik(_RADIAL, 0.0, _BH_FINAL, leg, _URDF_LIMITS)
        got = angles[leg.name]
        for a, b in zip(got, expected):
            assert abs(a - b) < 1e-9, (
                f'{leg.name} endpoint != stand pose: {got} vs {expected}'
            )


def test_phase1_phase2_continuous_at_handover():
    """Am Phase1→Phase2-Übergang ist der Foot-Target stetig (kein Sprung)."""
    engine = _make_engine()
    _start(engine)
    t_hand = _PHASE1_FRAC * _DURATION
    a_before = engine.compute_joint_angles(t_hand - 1e-4)
    a_after = engine.compute_joint_angles(t_hand + 1e-4)
    for leg in HEXAPOD.legs:
        for x, y in zip(a_before[leg.name], a_after[leg.name]):
            assert abs(x - y) < 1e-3, f'{leg.name} jump at handover'


# --- cmd_vel-Ignore + Param-Validierung -------------------------------------

def test_cmd_vel_ignored_during_cartesian_standup():
    engine = _make_engine()
    _start(engine)
    clamped = engine.set_command(0.1, 0.0, 0.0, 1.0)
    assert clamped is False
    assert engine.state == GaitEngine.STATE_CARTESIAN_STANDUP


def test_rejects_nonpositive_duration():
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_cartesian_standup(dict(_POWER_ON_MID), 0.0, 0.0)


@pytest.mark.parametrize('frac', [0.0, 1.0, -0.1, 1.5])
def test_rejects_invalid_phase1_fraction(frac):
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_cartesian_standup(
            dict(_POWER_ON_MID), 0.0, 4.0, phase1_fraction=frac,
        )


def test_missing_leg_no_movement():
    """Fehlt ein Bein in start_joints, ist seine Start-Pose = Touchdown."""
    engine = _make_engine()
    partial = {k: v for k, v in _POWER_ON_MID.items() if k != 'leg_3'}
    engine.start_cartesian_standup(
        partial, 0.0, _DURATION, _PHASE1_FRAC, _BH_START,
    )
    # leg_3 start_foot == touchdown → Phase 1 bewegungslos für leg_3.
    a0 = engine.compute_joint_angles(0.0)
    a_mid = engine.compute_joint_angles(0.5 * _PHASE1_FRAC * _DURATION)
    for x, y in zip(a0['leg_3'], a_mid['leg_3']):
        assert abs(x - y) < 1e-9, 'leg_3 should not move in phase 1'
