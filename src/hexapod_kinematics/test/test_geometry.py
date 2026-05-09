"""Tests für geometry.py — rotate_z + base/leg-Frame-Konvertierungen."""

import math

from hexapod_kinematics import base_to_leg_frame, HEXAPOD, leg_to_base_frame, rotate_z
import pytest


def test_rotate_z_zero_yaw_identity():
    point = (1.5, -2.3, 0.7)
    assert rotate_z(point, 0.0) == pytest.approx(point, abs=1e-12)


def test_rotate_z_90_degrees():
    """Punkt (1, 0, 0) um +π/2 -> (0, 1, 0). Z bleibt unverändert."""
    rotated = rotate_z((1.0, 0.0, 0.5), math.pi / 2.0)
    assert rotated == pytest.approx((0.0, 1.0, 0.5), abs=1e-12)


def test_rotate_z_180_degrees():
    rotated = rotate_z((1.0, 2.0, 3.0), math.pi)
    assert rotated == pytest.approx((-1.0, -2.0, 3.0), abs=1e-12)


def test_rotate_z_inverse_roundtrip():
    """rotate_z(rotate_z(p, +yaw), -yaw) = p für beliebiges yaw."""
    point = (0.4, -0.7, 1.1)
    yaw = 0.873
    forward = rotate_z(point, yaw)
    back = rotate_z(forward, -yaw)
    assert back == pytest.approx(point, abs=1e-12)


def test_base_to_leg_at_mount_origin():
    """
    Punkt am coxa_joint von Bein N -> (0, 0, 0) im Bein-Frame.

    Ein Punkt direkt am Mount-Punkt (also bei mount_xyz in base_link)
    muss im Bein-Frame der Origin sein.
    """
    for leg in HEXAPOD.legs:
        result = base_to_leg_frame(leg.mount_xyz, leg)
        assert result == pytest.approx((0.0, 0.0, 0.0), abs=1e-12), \
            f'mount_xyz of {leg.name} should map to bein-frame origin'


def test_leg_to_base_at_origin():
    """Origin des Bein-Frames -> mount_xyz in base_link."""
    for leg in HEXAPOD.legs:
        result = leg_to_base_frame((0.0, 0.0, 0.0), leg)
        assert result == pytest.approx(leg.mount_xyz, abs=1e-12)


def test_base_leg_roundtrip():
    """leg_to_base(base_to_leg(p)) = p für alle 6 Beine + 5 Stichproben."""
    points = [
        (0.0, 0.0, 0.0),
        (0.1, 0.2, -0.05),
        (-0.1, 0.3, 0.0),
        (0.5, -0.5, 0.5),
        (0.0, 0.0, 1.0),
    ]
    for leg in HEXAPOD.legs:
        for p in points:
            result = leg_to_base_frame(base_to_leg_frame(p, leg), leg)
            assert result == pytest.approx(p, abs=1e-12), \
                f'roundtrip failed for {leg.name} with {p}: got {result}'


def test_outward_x_in_base_link():
    """
    +X im Bein-Frame zeigt radial nach außen vom Body.

    Bein 1 (vorne rechts, mount_yaw = -π/4): +X im Bein-Frame zeigt nach
    base_link-Richtung (cos(-π/4), sin(-π/4)) = (0.707, -0.707), also
    diagonal vorn-rechts. Das verifiziert das mount_yaw-Vorzeichen.
    """
    leg_1 = HEXAPOD.by_name('leg_1')
    # Punkt bei (1, 0, 0) im Bein-Frame -> mount_xyz + Rz(-π/4)·(1,0,0) in base
    base = leg_to_base_frame((1.0, 0.0, 0.0), leg_1)
    expected = (
        leg_1.mount_xyz[0] + math.cos(-math.pi / 4.0),
        leg_1.mount_xyz[1] + math.sin(-math.pi / 4.0),
        leg_1.mount_xyz[2],
    )
    assert base == pytest.approx(expected, abs=1e-12)
