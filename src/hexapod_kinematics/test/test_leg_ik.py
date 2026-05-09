"""
Tests für leg_ik.leg_ik und leg_ik.leg_fk.

Strategie:
- Stützpunkte: Neutral, gestreckt, seitlich, tief gehoben.
- Out-of-reach: weit + nah -> IKError.
- Round-Trip: FK(IK(p)) ≈ p für ein zufälliges Raster reachable Punkte.
- Phase-4-Übergabe-Smoke: Stand-Pose [0, -0.5, +1.0] reproduziert.
- Links-Rechts-Symmetrie: identische Bein-Frame-Eingaben -> identische
  Joint-Winkel über alle 6 Beine (mechanische Symmetrie).
"""

import math
import random

from hexapod_kinematics import HEXAPOD, IKError, leg_fk, leg_ik
import pytest


LEG = HEXAPOD.legs[0]
L_C = LEG.L_coxa
L_F = LEG.L_femur
L_T = LEG.L_tibia


# ----- Stützpunkte ---------------------------------------------------


def test_neutral_pose_phase4_handover():
    """
    Phase-4-Stand-Pose [0, -0.5, +1.0] reproduziert.

    FK auf [0, -0.5, +1.0] gibt den "neutralen" Foot in Bein-Frame.
    IK darauf muss [0, -0.5, +1.0] zurückgeben.
    """
    foot = leg_fk(0.0, -0.5, 1.0, LEG)
    angles = leg_ik(*foot, LEG)
    assert angles == pytest.approx((0.0, -0.5, 1.0), abs=1e-9)


def test_fully_extended():
    """
    Foot voll gestreckt entlang +X -> alle Joints = 0.

    Toleranz 1e-6 (statt 1e-9 wie sonst): an dieser Singularität liegt
    acos-Argument exakt bei 1.0, FP-Drift in der Größenordnung
    sqrt(eps_machine) ≈ 1e-8 ist hier unvermeidbar.
    """
    foot = (L_C + L_F + L_T, 0.0, 0.0)
    angles = leg_ik(*foot, LEG)
    assert angles == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_lateral_with_coxa_rotation():
    """Foot mit y != 0: theta_coxa muss rotieren."""
    foot = (0.20, 0.05, -0.05)
    theta_c, theta_f, theta_t = leg_ik(*foot, LEG)
    expected_coxa = math.atan2(0.05, 0.20)
    assert theta_c == pytest.approx(expected_coxa, abs=1e-9)
    fk_back = leg_fk(theta_c, theta_f, theta_t, LEG)
    assert fk_back == pytest.approx(foot, abs=1e-9)


def test_deep_lifted():
    """Foot tief gehoben (z stark negativ): tibia stark geknickt."""
    foot = (0.10, 0.0, -0.15)
    theta_c, theta_f, theta_t = leg_ik(*foot, LEG)
    assert theta_t > 1.0  # stark geknickt
    fk_back = leg_fk(theta_c, theta_f, theta_t, LEG)
    assert fk_back == pytest.approx(foot, abs=1e-9)


# ----- Out-of-reach --------------------------------------------------


def test_out_of_reach_far():
    """Foot zu weit -> IKError."""
    with pytest.raises(IKError):
        leg_ik(1.0, 0.0, 0.0, LEG)


def test_out_of_reach_close():
    """
    Foot zu nah am Femur-Joint -> IKError.

    Min reachable d = |L_femur - L_tibia|. Foot bei
    (L_coxa, 0, 0) gibt d = 0, weit unter dem Minimum.
    """
    with pytest.raises(IKError):
        leg_ik(L_C, 0.0, 0.0, LEG)


def test_out_of_reach_just_beyond_max():
    """
    Foot knapp jenseits der Maximalreichweite -> IKError.

    Maximalreichweite ist L_coxa + L_femur + L_tibia in radialer Richtung.
    """
    max_reach = L_C + L_F + L_T
    with pytest.raises(IKError):
        leg_ik(max_reach + 0.01, 0.0, 0.0, LEG)


# ----- Round-Trip-Raster --------------------------------------------


def test_fk_ik_roundtrip_random_grid():
    """
    FK(IK(p)) ≈ p für 50 zufällige Punkte im erreichbaren Bereich.

    Sicherer Test gegen Vorzeichen-Bugs in IK oder FK: wenn beide
    konsistent falsch sind, würde das auch andere Tests breaken.
    """
    rng = random.Random(42)  # deterministisch
    min_d = abs(L_F - L_T) + 0.005  # kleiner Sicherheitsabstand
    max_d = L_F + L_T - 0.005
    n_tested = 0
    for _ in range(50):
        # Zufällige reachable Position: r in [coxa+min_d, coxa+max_d],
        # Höhe z so dass d im erlaubten Bereich bleibt.
        r = rng.uniform(L_C + min_d, L_C + max_d)
        z_max = math.sqrt(max_d ** 2 - (r - L_C) ** 2) - 0.001
        if z_max < 0:
            continue
        z = rng.uniform(-z_max, z_max)
        # Coxa-Drehung dazumixen: y != 0 möglich.
        coxa_rot = rng.uniform(-1.0, 1.0)
        x = r * math.cos(coxa_rot)
        y = r * math.sin(coxa_rot)
        original = (x, y, z)
        angles = leg_ik(*original, LEG)
        fk_back = leg_fk(*angles, LEG)
        assert fk_back == pytest.approx(original, abs=1e-9), \
            f'roundtrip failed for {original}: got {fk_back}'
        n_tested += 1
    assert n_tested >= 30, f'only {n_tested}/50 points reachable, raster too tight'


# ----- Links-Rechts-Symmetrie ---------------------------------------


def test_all_legs_identical_ik():
    """
    Foot in Bein-Frame -> identische Joint-Winkel über alle 6 Beine.

    Mechanische Symmetrie aus Stufe A: alle Beine teilen dasselbe
    URDF-Macro, Spiegelung steckt nur in mount_yaw. Die IK-Math im
    Bein-Frame ist daher links=rechts identisch.
    """
    foot = (0.20, 0.03, -0.05)
    angles_per_leg = [leg_ik(*foot, leg) for leg in HEXAPOD.legs]
    for i, angles in enumerate(angles_per_leg[1:], start=1):
        assert angles == pytest.approx(angles_per_leg[0], abs=1e-12), \
            f'leg {i + 1} differs from leg 1 for symmetric foot input'


def test_neutral_pose_consistent_across_legs():
    """
    Phase-4-Smoke gilt für alle 6 Beine, nicht nur Bein 1.

    Aus den Joint-Winkeln [0, -0.5, +1.0] muss der Foot-Punkt im
    Bein-Frame identisch sein für alle 6 Beine (mechanische Symmetrie).
    """
    feet = [leg_fk(0.0, -0.5, 1.0, leg) for leg in HEXAPOD.legs]
    for i, foot in enumerate(feet[1:], start=1):
        assert foot == pytest.approx(feet[0], abs=1e-12), \
            f'leg {i + 1} stand-foot differs from leg 1'
