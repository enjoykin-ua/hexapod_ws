"""
Tests for Phase 13 Stage A + Stage 0.4 — STATE_STARTUP_RAMP in gait_engine.

Stage 0.4: the real init pose is now power_on_mid (servo centre 1500 us,
see hexapod_hardware Stage 0.3), NOT the obsolete suspended preset
(femur=1.45). The start-pose fixture below reflects that. The stand-up
is all-6 simultaneous (NOT tripod 3+3 — see Stage-0 DL-7).

Pure-Python (pytest, no rclpy). Covers:
- T3: linear/smooth-step lerp from start_joints to stand-pose target,
      endpoint exact at duration boundary.
- T4: state transitions: STARTUP_RAMP starts on start_ramp(), auto-
      transitions to STANDING after progress >= 1.
- T5: set_command() ignores cmd_vel while in STARTUP_RAMP (no state
      change, no clamp).
- T6: start_ramp() rejects duration <= 0.

Plugin-side YAML-load + PWM-conversion tests (T1, T2, T7) live in the
hexapod_hardware gtest suite.
"""

import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits, leg_ik
import pytest


_TRIPOD = GAIT_PRESETS['tripod']


def _make_engine() -> GaitEngine:
    """Engine mit Stage-0.4-Stand-Pose-Defaults — IK-erreichbar + in-limits."""
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.03,
        cycle_time=2.0,
        # Stage 0.4: radial 0.295 / body_height -0.080 (war 0.27 / -0.052).
        # Die alte Pose verletzte das Tibia-Limit (1.33 > 1.161 rad) -> auf HW
        # Stage-0.5-Freeze; in lenienter Phase-5-Sim nie aufgefallen.
        radial_distance=0.295,
        body_height=-0.080,
        step_length_max=0.05,
    )


# ECHTE URDF-Joint-Limits, die das Plugin via set_joint_limits aus
# hexapod.urdf.xacro nimmt (Stage F strict-min + Stage 0.2 femur):
# coxa ±0.415, femur ±1.57, tibia ±1.161. NICHT die config.py-Defaults
# (±1.57/±1.50) — die Slope-Formel haengt von den Limits ab, daher muss
# der In-Limits-Test die echten Werte nutzen.
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-1.161, tibia_upper=1.161,
)


# power_on_mid start pose (servo centre 1500 us -> rad per joint), the
# real plugin init pose after Stage 0.3. Computed from servo_mapping.yaml
# via pulse_us_to_radians(1500) MIT den echten URDF-Limits (s. _URDF_LIMITS);
# hard-coded here so the gait test stays free of a hexapod_hardware import.
# Per leg: (coxa, femur, tibia) rad. Falls die Femur-Cal je neu vermessen
# wird, diese Werte nachziehen.
# Source: docs_raspi/phase_13_stage_0_4_standup_plan.md §3.1.
_POWER_ON_MID = {
    'leg_1': (-0.069, -0.469, 0.258),
    'leg_2': (0.156, -0.637, 0.255),
    'leg_3': (-0.111, -0.439, 0.168),
    'leg_4': (0.026, -0.477, 0.255),
    'leg_5': (0.104, -0.419, 0.156),
    'leg_6': (0.052, -0.496, 0.224),
}


def _power_on_mid_start_joints() -> dict[str, tuple[float, float, float]]:
    """Real Stage-0.3 init pose (power_on_mid) per leg, as ramp start."""
    return dict(_POWER_ON_MID)


# ---------------------------------------------------------------------
# T4 — State-Transitions
# ---------------------------------------------------------------------


def test_startup_ramp_initial_state_is_standing():
    """Engine startet defaultmaessig in STANDING (nicht STARTUP_RAMP)."""
    engine = _make_engine()
    assert engine.state == GaitEngine.STATE_STANDING


def test_startup_ramp_state_after_start_ramp():
    """start_ramp() setzt _state auf STARTUP_RAMP."""
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_startup_ramp_auto_transitions_to_standing():
    """Nach progress >= 1.0 wechselt Engine selbsttaetig zu STANDING."""
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    # Erster tick mid-Ramp — bleibt in STARTUP_RAMP
    _ = engine.compute_joint_angles(t=2.0)
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP
    # Tick nach Ramp-Ende — wechselt zu STANDING
    _ = engine.compute_joint_angles(t=4.001)
    assert engine.state == GaitEngine.STATE_STANDING


# ---------------------------------------------------------------------
# T3 — Smooth-Step-Lerp-Math
# ---------------------------------------------------------------------


def test_startup_ramp_endpoint_at_progress_1():
    """Bei progress >= 1.0: Output == Ramp-Target (= Stand-Pose-IK)."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=0.0, duration=4.0)
    out_end = engine.compute_joint_angles(t=4.0)
    # Compare gegen direkt-berechnete Stand-Pose
    target = engine._compute_stand_pose_joints()
    for leg in HEXAPOD.legs:
        for i in range(3):
            assert out_end[leg.name][i] == pytest.approx(
                target[leg.name][i], abs=1e-9
            )


def test_startup_ramp_start_at_progress_0():
    """Bei progress = 0: Output == Start-Joints (smooth-step s(0)=0)."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=10.0, duration=4.0)
    out_start = engine.compute_joint_angles(t=10.0)
    for leg in HEXAPOD.legs:
        for i in range(3):
            assert out_start[leg.name][i] == pytest.approx(
                start[leg.name][i], abs=1e-9
            )


def test_startup_ramp_midpoint_is_lerp_average():
    """Smooth-Step bei progress=0.5 = arithmetisches Mittel pro Joint."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=0.0, duration=4.0)
    target = engine._compute_stand_pose_joints()
    out_mid = engine.compute_joint_angles(t=2.0)  # progress=0.5
    for leg in HEXAPOD.legs:
        for i in range(3):
            expected = 0.5 * (start[leg.name][i] + target[leg.name][i])
            assert out_mid[leg.name][i] == pytest.approx(expected, abs=1e-9)


def test_startup_ramp_smooth_step_monotonic():
    """Smooth-Step-Lerp ist nicht-fallend pro Joint ueber 11 Stichproben."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=0.0, duration=4.0)
    samples = []
    for k in range(11):
        t = k * 0.4  # 0.0 ... 4.0
        angles = engine.compute_joint_angles(t)
        samples.append({
            leg.name: angles[leg.name] for leg in HEXAPOD.legs
        })
        # Re-set state, weil compute_joint_angles auto-transitions zu
        # STANDING wenn progress >= 1. Wir wollen fuer den naechsten
        # sample-Tick im Ramp bleiben — also setze state zurueck.
        if engine.state == GaitEngine.STATE_STANDING:
            engine._state = GaitEngine.STATE_STARTUP_RAMP

    # Monotonie pro Bein/Joint
    for leg in HEXAPOD.legs:
        for i in range(3):
            seq = [s[leg.name][i] for s in samples]
            # Richtung herausfinden: ueber alle 11 samples zwischen
            # start und end (Vorzeichen muss konsistent sein).
            delta_total = seq[-1] - seq[0]
            if abs(delta_total) < 1e-9:
                # Joint bewegt sich nicht — alle samples ~ identisch
                for v in seq:
                    assert v == pytest.approx(seq[0], abs=1e-9)
            else:
                sign = 1.0 if delta_total > 0 else -1.0
                for prev, curr in zip(seq, seq[1:]):
                    assert sign * (curr - prev) >= -1e-9, (
                        f'{leg.name} joint {i}: non-monotonic '
                        f'{prev} -> {curr} (overall sign {sign})'
                    )


# ---------------------------------------------------------------------
# T5 — cmd_vel-Ignoranz waehrend Ramp
# ---------------------------------------------------------------------


def test_startup_ramp_ignores_cmd_vel():
    """set_command() in STARTUP_RAMP: kein state-change, kein clamp."""
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    clamped = engine.set_command(0.05, 0.0, 0.0, t=1.0)
    # Kein Clamp gesetzt
    assert clamped is False
    # State unveraendert
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP
    # Engine-interne v_body sollte (0,0) bleiben (nicht 0.05)
    assert engine._v_body == (0.0, 0.0)
    assert engine._omega == 0.0


def test_startup_ramp_cmd_vel_works_after_ramp_finished():
    """Nach STANDING-Uebergang reagiert set_command() wieder normal."""
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    # Erst Ramp komplettieren
    _ = engine.compute_joint_angles(t=4.001)
    assert engine.state == GaitEngine.STATE_STANDING
    # Jetzt cmd_vel = WALKING-Trigger
    engine.set_command(0.02, 0.0, 0.0, t=4.1)
    assert engine.state == GaitEngine.STATE_WALKING


# ---------------------------------------------------------------------
# T6 — start_ramp Input-Validation
# ---------------------------------------------------------------------


def test_startup_ramp_rejects_zero_duration():
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_ramp(
            _power_on_mid_start_joints(), t=0.0, duration=0.0
        )


def test_startup_ramp_rejects_negative_duration():
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_ramp(
            _power_on_mid_start_joints(), t=0.0, duration=-1.0
        )


def test_startup_ramp_missing_legs_fall_back_to_target():
    """Fehlende Beine in start_joints: Start = Target, keine Bewegung."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    # leg_3 fehlt
    del start['leg_3']
    engine.start_ramp(start, t=0.0, duration=4.0)
    target = engine._compute_stand_pose_joints()

    # Bei progress=0.5 ist leg_3 weiterhin am Target (kein Lerp)
    out = engine.compute_joint_angles(t=2.0)
    for i in range(3):
        assert out['leg_3'][i] == pytest.approx(target['leg_3'][i], abs=1e-9)
    # leg_1 ist auf Lerp-Mitte zwischen power_on_mid und stand
    start_leg1_femur = _POWER_ON_MID['leg_1'][1]
    expected_leg1_femur = 0.5 * (start_leg1_femur + target['leg_1'][1])
    assert out['leg_1'][1] == pytest.approx(
        expected_leg1_femur, abs=1e-9
    )


# ---------------------------------------------------------------------
# Stage 0.4 — power_on_mid stand-up (all-6 simultaneous, in-limits)
# ---------------------------------------------------------------------


def test_power_on_mid_ramp_endpoint_is_stand_pose():
    """Ramp end == stand-pose IK for all 6 legs (power_on_mid start)."""
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    out_end = engine.compute_joint_angles(t=4.0)
    target = engine._compute_stand_pose_joints()
    for leg in HEXAPOD.legs:
        for i in range(3):
            assert out_end[leg.name][i] == pytest.approx(
                target[leg.name][i], abs=1e-9
            )


def test_power_on_mid_start_ramp_in_limits():
    """
    Every intermediate sample of all 18 joints stays within URDF limits.

    Smooth-step lerps monotonically from power_on_mid to stand-pose, so if
    both endpoints are in-limits every sample is too — this asserts it
    empirically over 21 samples (incl. endpoints) so a future engine change
    that breaks monotonicity would be caught. In-limits over the whole ramp
    is the HW-safety property: no Stage-0.5/0.6 plugin freeze during stand-up.
    """
    engine = _make_engine()
    engine.start_ramp(_power_on_mid_start_joints(), t=0.0, duration=4.0)
    lim = _URDF_LIMITS
    bounds = (
        (lim.coxa_lower, lim.coxa_upper),
        (lim.femur_lower, lim.femur_upper),
        (lim.tibia_lower, lim.tibia_upper),
    )
    for k in range(21):
        t = k * 0.2  # 0.0 .. 4.0
        angles = engine.compute_joint_angles(t)
        for leg in HEXAPOD.legs:
            for i in range(3):
                lo, hi = bounds[i]
                v = angles[leg.name][i]
                assert lo <= v <= hi, (
                    f'{leg.name} joint {i} = {v:.4f} out of limits '
                    f'[{lo}, {hi}] at t={t:.2f}'
                )
        # compute_joint_angles auto-transitions to STANDING at progress>=1;
        # re-arm so the next sample is still evaluated in-ramp.
        if engine.state == GaitEngine.STATE_STANDING:
            engine._state = GaitEngine.STATE_STARTUP_RAMP


def test_power_on_mid_ramp_all_six_simultaneous():
    """
    All 6 legs advance with the SAME smooth-step factor at a given progress.

    Verifies the stand-up is all-6 simultaneous (Stage-0 DL-7), not a
    staggered tripod. For each leg/joint the realised fraction
    (angle-start)/(target-start) must equal the shared smooth-step s at the
    sample time (joints with start==target are skipped — no motion, fraction
    undefined).
    """
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=0.0, duration=4.0)
    target = engine._compute_stand_pose_joints()
    for progress in (0.25, 0.5, 0.75):
        s_expected = progress * progress * (3.0 - 2.0 * progress)
        angles = engine.compute_joint_angles(t=progress * 4.0)
        for leg in HEXAPOD.legs:
            for i in range(3):
                span = target[leg.name][i] - start[leg.name][i]
                if abs(span) < 1e-6:
                    continue
                frac = (angles[leg.name][i] - start[leg.name][i]) / span
                assert frac == pytest.approx(s_expected, abs=1e-9), (
                    f'{leg.name} joint {i}: fraction {frac:.6f} != shared '
                    f's {s_expected:.6f} at progress {progress}'
                )
        engine._state = GaitEngine.STATE_STARTUP_RAMP


def test_power_on_mid_ramp_monotonic():
    """Each joint moves monotonically start->target (no slam/overshoot)."""
    engine = _make_engine()
    start = _power_on_mid_start_joints()
    engine.start_ramp(start, t=0.0, duration=4.0)
    samples = []
    for k in range(11):
        t = k * 0.4
        angles = engine.compute_joint_angles(t)
        samples.append({leg.name: angles[leg.name] for leg in HEXAPOD.legs})
        if engine.state == GaitEngine.STATE_STANDING:
            engine._state = GaitEngine.STATE_STARTUP_RAMP
    for leg in HEXAPOD.legs:
        for i in range(3):
            seq = [s[leg.name][i] for s in samples]
            delta_total = seq[-1] - seq[0]
            if abs(delta_total) < 1e-9:
                for v in seq:
                    assert v == pytest.approx(seq[0], abs=1e-9)
            else:
                sign = 1.0 if delta_total > 0 else -1.0
                for prev, curr in zip(seq, seq[1:]):
                    assert sign * (curr - prev) >= -1e-9, (
                        f'{leg.name} joint {i}: non-monotonic '
                        f'{prev} -> {curr}'
                    )


def test_stand_pose_in_limits_for_all_legs():
    """
    Stand-pose must be IK-reachable + within strict URDF limits, all 6 legs.

    Stage 0.4 regression: this would have caught the bug fixed in 0.4 — the old
    stand pose (radial 0.27 / body_height -0.052) needed tibia 1.33 rad, over
    the +-1.161 limit -> HW Stage-0.5 freeze. leg_ik with _URDF_LIMITS raises
    IKError on any out-of-limit joint, so a regression of the stand-pose
    defaults fails loudly here.
    """
    foot = (0.295, 0.0, -0.080)  # Stage-0.4 stand pose
    for leg in HEXAPOD.legs:
        # Must not raise IKError (geometry reach + strict joint limits).
        angles = leg_ik(*foot, leg, _URDF_LIMITS)
        # Stand-up direction from power_on_mid: femur RISES (less negative,
        # legs push down/out), tibia tucks MORE (knee bends to lift body).
        assert angles[1] > _POWER_ON_MID[leg.name][1] - 1e-6, (
            f'{leg.name} femur should rise from power_on_mid to stand'
        )
        assert angles[2] > _POWER_ON_MID[leg.name][2], (
            f'{leg.name} tibia should tuck more from power_on_mid to stand'
        )
        # coxa target centered (radial neutral pose, y=0).
        assert abs(angles[0]) < 1e-6
        assert not math.isnan(angles[0])
        # explicit limit guard (belt-and-suspenders to the IK strict-check).
        assert _URDF_LIMITS.tibia_lower <= angles[2] <= _URDF_LIMITS.tibia_upper
