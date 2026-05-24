"""
Tests for Stage 0.6 — URDF joint-limit parse + gait_engine integration.

Covers:
- ``parse_joint_limits_from_urdf`` happy-path + edge cases (empty,
  malformed, missing joints).
- ``GaitEngine`` with joint_limits dict triggers IKError("joint limit ...")
  in compute_joint_angles when IK angle exceeds bounds.
- ``GaitEngine`` without joint_limits stays in lenient mode (Phase-5).

NOT covered here (out of pytest scope, deferred to launch_testing /
manual verification):
- gait_node async service-client to /hexapod_safety_freeze
- hexapod_system handle_safety_freeze callback wiring (= gtest)
"""

import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import parse_joint_limits_from_urdf
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, IKError, JointLimits
import pytest


# ----- parse_joint_limits_from_urdf -----------------------------------


def _make_min_urdf(coxa_lower=-1.57, coxa_upper=+1.57,
                   femur_lower=-1.57, femur_upper=+1.57,
                   tibia_lower=-1.50, tibia_upper=+1.50):
    """Build a minimal URDF XML covering the 18 hexapod joints."""
    joints = []
    for n in range(1, 7):
        joints.append(
            f'<joint name="leg_{n}_coxa_joint" type="revolute">'
            f'<limit lower="{coxa_lower}" upper="{coxa_upper}" '
            'effort="5" velocity="2"/></joint>'
        )
        joints.append(
            f'<joint name="leg_{n}_femur_joint" type="revolute">'
            f'<limit lower="{femur_lower}" upper="{femur_upper}" '
            'effort="5" velocity="2"/></joint>'
        )
        joints.append(
            f'<joint name="leg_{n}_tibia_joint" type="revolute">'
            f'<limit lower="{tibia_lower}" upper="{tibia_upper}" '
            'effort="5" velocity="2"/></joint>'
        )
    return f'<?xml version="1.0"?><robot name="hexapod">{"".join(joints)}</robot>'


def test_parse_empty_string_returns_empty_dict():
    """Empty URDF → lenient fallback (no limits)."""
    assert parse_joint_limits_from_urdf('') == {}
    assert parse_joint_limits_from_urdf('   ') == {}


def test_parse_malformed_xml_returns_empty_dict():
    """Broken XML → lenient fallback, no exception bubbles up."""
    assert parse_joint_limits_from_urdf('<robot>not closed') == {}


def test_parse_full_urdf_returns_six_legs():
    """Happy path: 18 joints with limits → 6 JointLimits entries."""
    urdf = _make_min_urdf()
    result = parse_joint_limits_from_urdf(urdf)
    assert set(result.keys()) == {f'leg_{n}' for n in range(1, 7)}
    for leg_name, jl in result.items():
        assert jl.coxa_lower == pytest.approx(-1.57)
        assert jl.coxa_upper == pytest.approx(+1.57)
        assert jl.tibia_lower == pytest.approx(-1.50)
        assert jl.tibia_upper == pytest.approx(+1.50)


def test_parse_skips_legs_with_missing_joint():
    """Incomplete leg triple → dropped silently (no partial entries)."""
    # build URDF, then remove leg_3_tibia entry
    urdf = _make_min_urdf().replace(
        '<joint name="leg_3_tibia_joint" type="revolute">'
        '<limit lower="-1.5" upper="1.5" effort="5" velocity="2"/></joint>',
        ''
    )
    result = parse_joint_limits_from_urdf(urdf)
    # leg_3 dropped because its tibia joint is missing
    assert 'leg_3' not in result
    # others still present
    assert {'leg_1', 'leg_2', 'leg_4', 'leg_5', 'leg_6'}.issubset(result.keys())


# ----- GaitEngine + joint_limits --------------------------------------


def _make_engine(joint_limits=None):
    """Build a minimal engine for testing."""
    return GaitEngine(
        pattern=GAIT_PRESETS['tripod'],
        step_height=0.04,
        cycle_time=1.0,
        radial_distance=0.16,
        body_height=-0.05,
        step_length_max=0.05,
        joint_limits=joint_limits,
    )


def test_gait_engine_lenient_without_joint_limits():
    """No joint_limits → IK runs lenient, compute_joint_angles succeeds for stand."""
    engine = _make_engine()
    angles = engine.compute_joint_angles(0.0)
    assert len(angles) == 6
    for leg in HEXAPOD.legs:
        assert leg.name in angles
        # neutral-pose angles are finite
        for theta in angles[leg.name]:
            assert math.isfinite(theta)


def test_gait_engine_with_loose_limits_succeeds():
    """With loose limits (±π) every IK result fits → compute_joint_angles ok."""
    limits = {
        leg.name: JointLimits(
            coxa_lower=-math.pi, coxa_upper=+math.pi,
            femur_lower=-math.pi, femur_upper=+math.pi,
            tibia_lower=-math.pi, tibia_upper=+math.pi,
        )
        for leg in HEXAPOD.legs
    }
    engine = _make_engine(joint_limits=limits)
    angles = engine.compute_joint_angles(0.0)
    assert len(angles) == 6


def test_gait_engine_with_tight_limits_raises_joint_limit_ikerror():
    """Force IK joint-limit violation with deliberately too-tight limits."""
    # Default gait neutral pose at t=0 produces |femur|≈2.2, |tibia|≈2.8
    # rad in "knee-up" branch. Use ±0.1 to guarantee a violation.
    limits = {
        leg.name: JointLimits(
            coxa_lower=-0.1, coxa_upper=+0.1,
            femur_lower=-0.1, femur_upper=+0.1,
            tibia_lower=-0.1, tibia_upper=+0.1,
        )
        for leg in HEXAPOD.legs
    }
    engine = _make_engine(joint_limits=limits)
    with pytest.raises(IKError) as exc_info:
        engine.compute_joint_angles(0.0)
    # gait_engine wraps the IKError; "joint limit" must survive so
    # gait_node._tick can route it to /hexapod_safety_freeze.
    assert 'joint limit' in str(exc_info.value)
