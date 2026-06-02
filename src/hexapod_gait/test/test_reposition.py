"""
Tests für Phase 13 Stage 1 Teil 2.3 — STATE_REPOSITION in gait_engine.

Zwei-Phasen Standup → Tripod-Reposition → Walk:
  - Aufstehen nutzt ``standup_radial_distance`` (breite, touchdown-sichere Pose).
  - Danach automatisch Tripod-Reposition (Gruppe {1,3,5} dann {2,4,6}) auf
    ``radial_distance`` (nähere Walk-Pose); nie >3 Beine in der Luft.
  - Wertneutral: die Engine kennt keine konkreten radii — sie kommen als Params.

Pure-Python (pytest, kein rclpy). Deckt §2 des Plans
phase_13_stage_1_two_phase_reposition_plan.md ab.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits, leg_fk
import pytest


_TRIPOD = GAIT_PRESETS['tripod']

# Aktuelle URDF-Limits NACH dem Tibia-Unlock (Stage 1 Teil 2.1): tibia bis
# +2.50. Die nähere Walk-Pose (radial 0.220) braucht diese Beuge — mit dem
# alten +1.30 wäre sie out-of-limit (genau der Grund für den Unlock).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-1.00, tibia_upper=2.50,
)

_POWER_ON_MID = {
    'leg_1': (-0.069, -0.469, 0.4946),
    'leg_2': (0.156, -0.637, 0.5181),
    'leg_3': (-0.111, -0.439, 0.2591),
    'leg_4': (0.026, -0.477, 0.4286),
    'leg_5': (0.104, -0.419, 0.1978),
    'leg_6': (0.052, -0.496, 0.3503),
}

_STANDUP_RADIAL = 0.295    # breite Aufsteh-Pose
_WALK_RADIAL = 0.220       # nähere Walk-Pose (Tool-Ergebnis)
_BH = -0.080
_STEP_HEIGHT = 0.040
_STANDUP_DUR = 4.0
_REPOS_DUR = 2.0
_BH_START = -0.0135


def _make_engine(
    standup_radial: float = _STANDUP_RADIAL,
    walk_radial: float = _WALK_RADIAL,
    repos_dur: float = _REPOS_DUR,
) -> GaitEngine:
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=_STEP_HEIGHT,
        cycle_time=2.0,
        radial_distance=walk_radial,
        body_height=_BH,
        step_length_max=0.089,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
        standup_radial_distance=standup_radial,
        reposition_cycle_time=repos_dur,
    )


def _finish_standup(engine: GaitEngine) -> None:
    """Standup starten + bis ans Ende treiben (löst den Übergang aus)."""
    engine.start_cartesian_standup(
        dict(_POWER_ON_MID), t=0.0, duration=_STANDUP_DUR,
        phase1_fraction=0.4, body_height_start=_BH_START,
    )
    engine.compute_joint_angles(_STANDUP_DUR)  # progress>=1 → Übergang


def _repos_samples(n: int = 19):
    """progress-Werte echt innerhalb (0,1) der Reposition (kein Endpunkt)."""
    return [
        _STANDUP_DUR + (i + 1) / (n + 1) * _REPOS_DUR for i in range(n)
    ]


def _in_air_count(angles) -> int:
    n = 0
    for leg in HEXAPOD.legs:
        foot = leg_fk(*angles[leg.name], leg)
        if foot[2] > _BH + 1e-4:
            n += 1
    return n


def test_standup_touchdown_uses_standup_radial():
    """Touchdown/Endpose des Aufstehens liegen auf standup_radial, nicht walk."""
    engine = _make_engine()
    engine.start_cartesian_standup(
        dict(_POWER_ON_MID), t=0.0, duration=_STANDUP_DUR,
        phase1_fraction=0.4, body_height_start=_BH_START,
    )
    for leg in HEXAPOD.legs:
        assert engine._cart_touchdown[leg.name][0] == pytest.approx(
            _STANDUP_RADIAL
        )
        assert engine._cart_push_end[leg.name][0] == pytest.approx(
            _STANDUP_RADIAL
        )


def test_standup_path_in_limits_at_wide_radial():
    """Aufsteh-Pfad @ standup_radial 0.295 ist limit-konform (kein IKError)."""
    engine = _make_engine()
    engine.start_cartesian_standup(
        dict(_POWER_ON_MID), t=0.0, duration=_STANDUP_DUR,
        phase1_fraction=0.4, body_height_start=_BH_START,
    )
    # Samples echt innerhalb der Standup-Dauer (Zustand bleibt STANDUP).
    for i in range(1, 40):
        t = i / 40.0 * _STANDUP_DUR
        engine.compute_joint_angles(t)  # wirft IKError bei Limit-Verletzung


def test_standup_triggers_reposition_when_radii_differ():
    """Nach dem Aufstehen → STATE_REPOSITION (radii unterscheiden sich)."""
    engine = _make_engine()
    _finish_standup(engine)
    assert engine.state == GaitEngine.STATE_REPOSITION


def test_no_reposition_when_radii_equal():
    """standup_radial == walk_radial → direkt STANDING (Skip, eps)."""
    engine = _make_engine(standup_radial=0.295, walk_radial=0.295)
    _finish_standup(engine)
    assert engine.state == GaitEngine.STATE_STANDING


def test_reposition_path_in_limits():
    """Reposition-Trajektorie ist über den ganzen Pfad limit-konform."""
    engine = _make_engine()
    _finish_standup(engine)
    for t in _repos_samples():
        engine.compute_joint_angles(t)  # wirft IKError bei Limit-Verletzung
    assert engine.state == GaitEngine.STATE_REPOSITION  # Endpunkt nicht erreicht


def test_reposition_max_three_legs_in_air():
    """Tripod: nie mehr als 3 Beine gleichzeitig in der Luft (statisch stabil)."""
    engine = _make_engine()
    _finish_standup(engine)
    for t in _repos_samples():
        angles = engine.compute_joint_angles(t)
        assert _in_air_count(angles) <= 3


def test_reposition_each_group_lifts():
    """Beide Tripod-Gruppen heben in ihrer Hälfte tatsächlich ab (kein No-op)."""
    engine = _make_engine()
    _finish_standup(engine)
    # erste Hälfte: Gruppe A (1,3,5) schwingt
    a = engine.compute_joint_angles(_STANDUP_DUR + 0.25 * _REPOS_DUR)
    air_a = {
        leg.name for leg in HEXAPOD.legs
        if leg_fk(*a[leg.name], leg)[2] > _BH + 1e-4
    }
    assert air_a == {'leg_1', 'leg_3', 'leg_5'}
    # zweite Hälfte: Gruppe B (2,4,6) schwingt
    b = engine.compute_joint_angles(_STANDUP_DUR + 0.75 * _REPOS_DUR)
    air_b = {
        leg.name for leg in HEXAPOD.legs
        if leg_fk(*b[leg.name], leg)[2] > _BH + 1e-4
    }
    assert air_b == {'leg_2', 'leg_4', 'leg_6'}


def test_reposition_ends_at_walk_radial_standing():
    """Reposition-Ende → STANDING, alle Füße auf walk_radial @ body_height."""
    engine = _make_engine()
    _finish_standup(engine)
    angles = engine.compute_joint_angles(_STANDUP_DUR + _REPOS_DUR)
    assert engine.state == GaitEngine.STATE_STANDING
    for leg in HEXAPOD.legs:
        foot = leg_fk(*angles[leg.name], leg)
        assert foot[0] == pytest.approx(_WALK_RADIAL, abs=1e-3)
        assert foot[1] == pytest.approx(0.0, abs=1e-3)
        assert foot[2] == pytest.approx(_BH, abs=1e-3)


def test_reposition_value_neutral_other_radii():
    """Wertneutral: andere radii (0.28→0.24) laufen generisch — kein Hardcode."""
    engine = _make_engine(standup_radial=0.28, walk_radial=0.24)
    _finish_standup(engine)
    assert engine.state == GaitEngine.STATE_REPOSITION
    for t in _repos_samples():
        angles = engine.compute_joint_angles(t)
        assert _in_air_count(angles) <= 3
    end = engine.compute_joint_angles(_STANDUP_DUR + _REPOS_DUR)
    assert engine.state == GaitEngine.STATE_STANDING
    for leg in HEXAPOD.legs:
        assert leg_fk(*end[leg.name], leg)[0] == pytest.approx(0.24, abs=1e-3)


def test_cmd_vel_ignored_during_reposition():
    """cmd_vel wird während der Reposition ignoriert (erst STANDING nimmt an)."""
    engine = _make_engine()
    _finish_standup(engine)
    assert engine.state == GaitEngine.STATE_REPOSITION
    engine.set_command(0.05, 0.0, 0.0, _STANDUP_DUR + 0.5 * _REPOS_DUR)
    # set_command darf den Reposition-State NICHT auf WALKING kippen.
    assert engine.state == GaitEngine.STATE_REPOSITION
