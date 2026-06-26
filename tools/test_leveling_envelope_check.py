# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
Tests für tools/leveling_envelope_check.py (Block A5 Stufe 2, Checkliste 2.5).

Bestätigt gegen die committed URDF, dass das ``max_level_angle`` (10°) in allen
Stance×Orientierungs-Modi envelope-sicher ist, und dass das Tool steilere
Winkel korrekt als out-of-limit erkennt.

Run:
    cd ~/hexapod_ws && source install/setup.bash
    pytest tools/test_leveling_envelope_check.py -v
"""

import sys
from pathlib import Path

import pytest

_TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOL_DIR))
import leveling_envelope_check as lec  # noqa: E402
import walking_envelope_check as wec  # noqa: E402

_URDF_XACRO = (
    _TOOL_DIR.parent / 'src/hexapod_description/urdf/hexapod.urdf.xacro')


@pytest.fixture(scope='module')
def limits():
    return wec.load_joint_limits(_URDF_XACRO)


def test_10deg_safe_in_all_modes(limits):
    """max_level_angle 10° in allen Stance×Orientierungs-Modi in-limit + stabil."""
    for sname, bh in lec._STANCE_MODES:
        for oname, rf, pf in lec._ORIENT_MODES:
            r = lec.evaluate(10.0, rf, pf, bh, limits)
            assert r['ok'], f'{sname}/{oname}: {r["detail"] or "CoG"}'


def test_max_safe_theta_confirms_10(limits):
    best = lec.max_safe_theta(limits, [5.0, 8.0, 10.0, 12.0, 15.0])
    assert best == pytest.approx(10.0)


def test_steep_combined_violates_limits(limits):
    """15° combined verletzt in mindestens einem Stance die URDF-Limits."""
    violated = any(
        not lec.evaluate(15.0, 1.0, 1.0, bh, limits)['in_limit']
        for _, bh in lec._STANCE_MODES
    )
    assert violated


def test_roll_only_10deg_in_limits(limits):
    for _, bh in lec._STANCE_MODES:
        assert lec.evaluate(10.0, 1.0, 0.0, bh, limits)['in_limit']


def test_zero_theta_is_stable_plain_stand(limits):
    r = lec.evaluate(0.0, 1.0, 1.0, -0.080, limits)
    assert r['in_limit'] and r['ok']
    assert r['margin_m'] > 0.05  # flacher Stand: dicke CoG-Marge
