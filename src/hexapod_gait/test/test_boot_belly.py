"""
Block I Phase 3 — Boot-Bauch-Halten (``auto_standup_on_start=false``).

Reiner Engine-Test (kein ROS/Sim) für ``GaitEngine.hold_sat_at``: die Engine geht
direkt in ``STATE_SAT`` und hält die übergebene (Spawn-)Pose je Bein — ohne je
gestanden zu haben. Sichert den Care-Point aus dem Phase-3-Plan (§1c) ab: der
Roboter bleibt auf dem Bauch, bis ``/hexapod_stand_up`` ihn hochrampt.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

# Eine plausible Bauch-/Spawn-Pose je Bein (rad, innerhalb der Limits). Der Test
# prüft nur, dass die Engine GENAU diese Pose in SAT statisch hält.
_SPAWN = {leg.name: (0.0, -1.2, 1.5) for leg in HEXAPOD.legs}


def _make_engine() -> GaitEngine:
    """Frische Engine (Default-State = STANDING nach Konstruktion)."""
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.040,
        cycle_time=2.0,
        radial_distance=0.145,
        body_height=-0.10,
        step_length_max=0.089,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
        standup_radial_distance=0.17,
        reposition_cycle_time=2.0,
    )


def test_hold_sat_at_sets_sat_state():
    """hold_sat_at → Engine ist in STATE_SAT (Bauch), nicht mehr STANDING."""
    engine = _make_engine()
    assert engine.state != GaitEngine.STATE_SAT
    engine.hold_sat_at(_SPAWN)
    assert engine.state == GaitEngine.STATE_SAT


def test_hold_sat_at_holds_spawn_pose():
    """In SAT liefert compute_joint_angles exakt die übergebene Spawn-Pose."""
    engine = _make_engine()
    engine.hold_sat_at(_SPAWN)
    angles = engine.compute_joint_angles(0.0)
    for leg in HEXAPOD.legs:
        assert angles[leg.name] == pytest.approx(_SPAWN[leg.name])


def test_hold_sat_at_stable_over_ticks():
    """Die Bauch-Pose bleibt über viele Ticks konstant (stabiles Halten)."""
    engine = _make_engine()
    engine.hold_sat_at(_SPAWN)
    first = engine.compute_joint_angles(0.0)
    later = first
    for i in range(1, 50):
        later = engine.compute_joint_angles(i * 0.02)
    for leg in HEXAPOD.legs:
        assert later[leg.name] == pytest.approx(first[leg.name])
