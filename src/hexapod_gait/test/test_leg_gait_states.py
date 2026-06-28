"""Tests für GaitEngine.leg_gait_states (Block A5 S4-1) — read-only Swing-Phase."""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_RADIAL = 0.16
_BODY_H = -0.08


def _urdf_limits():
    return {
        leg.name: JointLimits(
            leg.coxa_limits[0], leg.coxa_limits[1],
            leg.femur_limits[0], leg.femur_limits[1],
            leg.tibia_limits[0], leg.tibia_limits[1],
        )
        for leg in HEXAPOD.legs
    }


def _engine():
    return GaitEngine(
        pattern=_TRIPOD, step_height=0.04, cycle_time=2.0,
        radial_distance=_RADIAL, body_height=_BODY_H, step_length_max=0.03,
        joint_limits=_urdf_limits(),
    )


def test_standing_returns_all_stance():
    eng = _engine()
    assert eng.state == GaitEngine.STATE_STANDING
    states = eng.leg_gait_states(0.0)
    assert all(states[i] == (False, 0.0) for i in range(1, 7))


def test_walking_matches_swing_stance_formula():
    eng = _engine()
    eng.set_command(0.05, 0.0, 0.0, 0.0)  # → WALKING
    assert eng.state == GaitEngine.STATE_WALKING
    t = 0.37
    states = eng.leg_gait_states(t)
    for leg in HEXAPOD.legs:
        leg_id = int(leg.name.split('_')[1])
        offset = eng.pattern.phase_offset_per_leg.get(leg_id)
        cycle_phase = ((t / eng.cycle_time) + offset) % 1.0
        if cycle_phase < eng.pattern.swing_duty:
            exp = (True, cycle_phase / eng.pattern.swing_duty)
        else:
            exp = (
                False,
                (cycle_phase - eng.pattern.swing_duty)
                / (1.0 - eng.pattern.swing_duty),
            )
        assert states[leg_id][0] == exp[0]
        assert states[leg_id][1] == pytest.approx(exp[1])


def test_is_swing_consistent_with_target_z():
    # Querprobe gegen die ECHTEN Trajektorien: ein Swing-Bein hebt
    # (z >= body_height), ein Stance-Bein liegt exakt auf body_height.
    eng = _engine()
    eng.set_command(0.05, 0.0, 0.0, 0.0)
    t = 0.25
    states = eng.leg_gait_states(t)
    targets = eng.compute_foot_targets(t)
    for leg in HEXAPOD.legs:
        leg_id = int(leg.name.split('_')[1])
        is_swing, _ = states[leg_id]
        z = targets[leg.name][2]
        if is_swing:
            assert z >= eng.body_height - 1e-9
        else:
            assert z == pytest.approx(eng.body_height)
