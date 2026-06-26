"""Tests für den Body-Leveling-Stellpfad in der GaitEngine (Block A5 Stufe 2)."""

import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import (
    HEXAPOD,
    IKError,
    JointLimits,
    leg_fk,
    leg_to_base_frame,
    rotate_xy,
)
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_RADIAL = 0.16
_BODY_H = -0.08


def _urdf_limits() -> dict[str, JointLimits]:
    return {
        leg.name: JointLimits(
            leg.coxa_limits[0], leg.coxa_limits[1],
            leg.femur_limits[0], leg.femur_limits[1],
            leg.tibia_limits[0], leg.tibia_limits[1],
        )
        for leg in HEXAPOD.legs
    }


def _engine(max_level_deg=10.0, max_level_walking_deg=4.0, limits=None) -> GaitEngine:
    eng = GaitEngine(
        pattern=_TRIPOD, step_height=0.04, cycle_time=2.0,
        radial_distance=_RADIAL, body_height=_BODY_H, step_length_max=0.03,
        joint_limits=limits if limits is not None else _urdf_limits(),
    )
    eng.max_level_angle = math.radians(max_level_deg)
    eng.max_level_angle_walking = math.radians(max_level_walking_deg)
    return eng


def test_zero_offset_equals_plain_stand_ik():
    eng = _engine()
    plain = eng.compute_joint_angles(0.0)
    eng.set_body_orientation_offset(0.0, 0.0)
    assert eng.compute_joint_angles(0.0) == plain


def test_leveling_changes_pose():
    eng = _engine()
    plain = eng.compute_joint_angles(0.0)
    eng.set_body_orientation_offset(math.radians(8.0), 0.0)
    leveled = eng.compute_joint_angles(0.0)
    assert leveled != plain


def test_leveling_roundtrip_matches_rotated_targets():
    # FK der gelevelten Winkel muss die im Base-Frame rotierten Stand-Targets
    # reproduzieren. Vorzeichen: die FUSS-Rotation = −Körper-Korrektur, also
    # rotate_xy(..., -roll, -pitch) (validiert rotate_xy + Frames + IK/FK + Sign).
    eng = _engine()
    roll, pitch = math.radians(7.0), math.radians(-5.0)
    eng.set_body_orientation_offset(roll, pitch)
    leveled = eng.compute_joint_angles(0.0)

    stand = eng._compute_standing_targets()
    for leg in HEXAPOD.legs:
        foot_leg = leg_fk(*leveled[leg.name], leg)
        foot_base = leg_to_base_frame(foot_leg, leg)
        expected = rotate_xy(
            leg_to_base_frame(stand[leg.name], leg), -roll, -pitch,
        )
        assert foot_base == pytest.approx(expected, abs=1e-6)


def test_offset_clamped_to_max_level_angle():
    # Offset 30° aber max 10° → Fuß-Rotation = −clamp(30°,10°) = −10° (white-box
    # vs _leveled_ik_at mit dem geclampten, negierten Wert).
    eng = _engine(max_level_deg=10.0)
    eng.set_body_orientation_offset(math.radians(30.0), 0.0)
    got = eng.compute_joint_angles(0.0)
    expected = eng._leveled_ik_at(
        eng._compute_standing_targets(), math.radians(-10.0), 0.0,
    )
    assert got == expected


def test_leveled_pose_in_limits_at_max():
    # 10° Leveling auf der Stand-Pose bleibt in den URDF-Limits (kein Freeze).
    limits = _urdf_limits()
    eng = _engine(max_level_deg=10.0, limits=limits)
    eng.set_body_orientation_offset(math.radians(10.0), math.radians(10.0))
    angles = eng.compute_joint_angles(0.0)  # darf nicht werfen
    for name, (c, f, t) in angles.items():
        lim = limits[name]
        assert lim.coxa_lower <= c <= lim.coxa_upper, f'{name} coxa {c}'
        assert lim.femur_lower <= f <= lim.femur_upper, f'{name} femur {f}'
        assert lim.tibia_lower <= t <= lim.tibia_upper, f'{name} tibia {t}'


def test_ikerror_fallback_degrades_instead_of_freezing():
    # Übertriebener max (60°) + 60°-Offset → volle Rotation verletzt Limits.
    # Erwartung: KEIN IKError (Fallback skaliert runter), gültige Pose zurück.
    limits = _urdf_limits()
    eng = _engine(max_level_deg=60.0, limits=limits)
    eng.set_body_orientation_offset(math.radians(60.0), 0.0)
    angles = eng.compute_joint_angles(0.0)  # darf NICHT werfen
    assert set(angles.keys()) == {leg.name for leg in HEXAPOD.legs}


def test_genuine_bad_base_pose_still_raises():
    # Grundpose selbst out-of-reach (radial absurd groß) → auch Skala 0 failt
    # → echter IKError (Freeze NICHT durch Leveling unterdrückt).
    limits = _urdf_limits()
    eng = GaitEngine(
        pattern=_TRIPOD, step_height=0.04, cycle_time=2.0,
        radial_distance=0.50, body_height=_BODY_H, step_length_max=0.03,
        joint_limits=limits,
    )
    eng.max_level_angle = math.radians(10.0)
    eng.set_body_orientation_offset(math.radians(5.0), 0.0)
    with pytest.raises(IKError):
        eng.compute_joint_angles(0.0)


def test_walking_applies_leveling():
    # Stufe 3a: in WALKING wird das Offset angewandt (nicht mehr ignoriert).
    eng = _engine()
    eng.set_command(0.05, 0.0, 0.0, 0.0)  # → WALKING
    assert eng.state == GaitEngine.STATE_WALKING
    eng.set_body_orientation_offset(math.radians(3.0), 0.0)  # < walking-Clamp 4°
    walking = eng.compute_joint_angles(0.3)

    ref = _engine()
    ref.set_command(0.05, 0.0, 0.0, 0.0)
    assert walking != ref.compute_joint_angles(0.3)


def test_walking_uses_walking_clamp():
    # In WALKING gilt der engere Walking-Clamp (4°), nicht der STANDING-Clamp (10°).
    eng = _engine(max_level_deg=10.0, max_level_walking_deg=4.0)
    eng.set_command(0.05, 0.0, 0.0, 0.0)  # → WALKING
    eng.set_body_orientation_offset(math.radians(8.0), 0.0)  # > 4°
    got = eng.compute_joint_angles(0.3)
    # Foot-Rotation = −clamp(8°, 4°) = −4° auf die Walking-Targets.
    targets = eng.compute_foot_targets(0.3)
    expected = eng._leveled_ik_at(targets, math.radians(-4.0), 0.0)
    assert got == expected


def test_standing_uses_standing_clamp():
    # In STANDING gilt der volle Clamp (10°) — 8° wird voll angewandt.
    eng = _engine(max_level_deg=10.0, max_level_walking_deg=4.0)
    eng.set_body_orientation_offset(math.radians(8.0), 0.0)
    got = eng.compute_joint_angles(0.0)
    expected = eng._leveled_ik_at(
        eng._compute_standing_targets(), math.radians(-8.0), 0.0,
    )
    assert got == expected


def test_stopping_applies_leveling():
    # STOPPING ist auch im Leveling-Pfad (kein Aufschnappen beim Auslaufen).
    eng = _engine()
    eng.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    eng.set_command(0.0, 0.0, 0.0, 0.5)   # → STOPPING
    assert eng.state == GaitEngine.STATE_STOPPING
    eng.set_body_orientation_offset(math.radians(3.0), 0.0)
    got = eng.compute_joint_angles(0.5)

    ref = _engine()
    ref.set_command(0.05, 0.0, 0.0, 0.0)
    ref.set_command(0.0, 0.0, 0.0, 0.5)
    assert got != ref.compute_joint_angles(0.5)
