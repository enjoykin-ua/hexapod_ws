"""
Tests for Phase 13 Stage A — STATE_STARTUP_RAMP in gait_engine.

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

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD
import pytest


_TRIPOD = GAIT_PRESETS['tripod']


def _make_engine() -> GaitEngine:
    """Engine mit Phase-11/13-Defaults — reproduzierbar, IK-erreichbar."""
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.03,
        cycle_time=2.0,
        radial_distance=0.27,
        body_height=-0.052,
        step_length_max=0.05,
    )


def _suspended_start_joints() -> dict[str, tuple[float, float, float]]:
    """Stage-A-suspended-Preset-Werte fuer alle 6 Beine."""
    return {leg.name: (0.0, 1.45, 0.0) for leg in HEXAPOD.legs}


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
    engine.start_ramp(_suspended_start_joints(), t=0.0, duration=4.0)
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_startup_ramp_auto_transitions_to_standing():
    """Nach progress >= 1.0 wechselt Engine selbsttaetig zu STANDING."""
    engine = _make_engine()
    engine.start_ramp(_suspended_start_joints(), t=0.0, duration=4.0)
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
    start = _suspended_start_joints()
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
    start = _suspended_start_joints()
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
    start = _suspended_start_joints()
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
    start = _suspended_start_joints()
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
    engine.start_ramp(_suspended_start_joints(), t=0.0, duration=4.0)
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
    engine.start_ramp(_suspended_start_joints(), t=0.0, duration=4.0)
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
            _suspended_start_joints(), t=0.0, duration=0.0
        )


def test_startup_ramp_rejects_negative_duration():
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_ramp(
            _suspended_start_joints(), t=0.0, duration=-1.0
        )


def test_startup_ramp_missing_legs_fall_back_to_target():
    """Fehlende Beine in start_joints: Start = Target, keine Bewegung."""
    engine = _make_engine()
    start = _suspended_start_joints()
    # leg_3 fehlt
    del start['leg_3']
    engine.start_ramp(start, t=0.0, duration=4.0)
    target = engine._compute_stand_pose_joints()

    # Bei progress=0.5 ist leg_3 weiterhin am Target (kein Lerp)
    out = engine.compute_joint_angles(t=2.0)
    for i in range(3):
        assert out['leg_3'][i] == pytest.approx(target['leg_3'][i], abs=1e-9)
    # leg_1 ist auf Lerp-Mitte zwischen suspended und stand
    expected_leg1_femur = 0.5 * (1.45 + target['leg_1'][1])
    assert out['leg_1'][1] == pytest.approx(
        expected_leg1_femur, abs=1e-9
    )
