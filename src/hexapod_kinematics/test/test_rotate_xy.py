"""Tests für geometry.rotate_xy — Body-Leveling-Rotation (Block A5 Stufe 2)."""

import math

from hexapod_kinematics import rotate_xy
import pytest


def test_zero_is_identity():
    point = (0.16, -0.02, -0.08)
    assert rotate_xy(point, 0.0, 0.0) == pytest.approx(point, abs=1e-12)


def test_pure_roll_about_x():
    # Rx(90°) auf (0,0,1) -> (0,-1,0): X fest, Y/Z drehen.
    assert rotate_xy((0.0, 0.0, 1.0), math.pi / 2.0, 0.0) == pytest.approx(
        (0.0, -1.0, 0.0), abs=1e-12,
    )


def test_pure_pitch_about_y():
    # Ry(90°) auf (1,0,0) -> (0,0,-1): Y fest, X/Z drehen.
    assert rotate_xy((1.0, 0.0, 0.0), 0.0, math.pi / 2.0) == pytest.approx(
        (0.0, 0.0, -1.0), abs=1e-12,
    )


def test_roll_keeps_x():
    rotated = rotate_xy((0.7, 0.3, -0.5), math.radians(12.0), 0.0)
    assert rotated[0] == pytest.approx(0.7, abs=1e-12)


def test_pitch_keeps_y():
    rotated = rotate_xy((0.7, 0.3, -0.5), 0.0, math.radians(12.0))
    assert rotated[1] == pytest.approx(0.3, abs=1e-12)


def test_norm_preserved():
    # Rotation ist längen-erhaltend.
    point = (0.16, -0.02, -0.08)
    rot = rotate_xy(point, math.radians(9.0), math.radians(-6.0))
    n0 = math.sqrt(sum(c * c for c in point))
    n1 = math.sqrt(sum(c * c for c in rot))
    assert n1 == pytest.approx(n0, abs=1e-12)


def test_small_roll_tilts_foot_in_y():
    # Fuß unter dem Body (0,0,-z): kleine positive roll → Fuß wandert in +Y
    # (Rx: y' = -sr·z = -sr·(-z) = +sr·z für z<0).
    rot = rotate_xy((0.0, 0.0, -0.1), math.radians(5.0), 0.0)
    assert rot[1] > 0.0
    assert rot[0] == pytest.approx(0.0, abs=1e-12)
