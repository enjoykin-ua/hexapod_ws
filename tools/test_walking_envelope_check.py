# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
Tests for tools/walking_envelope_check.py.

Run via:
    cd ~/hexapod_ws
    source install/setup.bash
    pytest tools/test_walking_envelope_check.py -v

These tests cover the public functions of the tool — check_envelope,
check_envelope_all_scenarios, sweep_heights, recommend_for_height —
against the real URDF + cal-values committed in this repo.
"""

import sys
from pathlib import Path

import pytest


# Import the tool's module: tools/ is not a package, so we add it to
# sys.path manually.
_TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOL_DIR))
import walking_envelope_check as wec  # noqa: E402


_URDF_XACRO = (
    _TOOL_DIR.parent / 'src/hexapod_description/urdf/hexapod.urdf.xacro')
_SIM_PRESET = (
    _TOOL_DIR.parent / 'src/hexapod_gait/config/presets/sim_walk.yaml')


@pytest.fixture(scope='module')
def joint_limits():
    """Real joint limits from the committed Stage-D URDF."""
    return wec.load_joint_limits(_URDF_XACRO)


# ---------------------------------------------------------------------------
# load_joint_limits
# ---------------------------------------------------------------------------


def test_load_joint_limits_returns_six_legs(joint_limits):
    """URDF parse should give one JointLimits per leg."""
    assert len(joint_limits) == 6
    assert set(joint_limits.keys()) == {f'leg_{n}' for n in range(1, 7)}


def test_load_joint_limits_leg3_tibia_upper_is_engster(joint_limits):
    """Sanity-check: leg_3 tibia_upper = +1.185 is the tightest tibia
    limit across all 6 legs (per Cal-Doku Tab. 3.3 finding)."""
    tibia_uppers = [
        joint_limits[f'leg_{n}'].tibia_upper for n in range(1, 7)
    ]
    assert min(tibia_uppers) == pytest.approx(
        joint_limits['leg_3'].tibia_upper)


# ---------------------------------------------------------------------------
# check_envelope
# ---------------------------------------------------------------------------


def test_check_envelope_sim_preset_forward_green(joint_limits):
    """The committed sim_walk.yaml preset must be GREEN for forward
    walking — that's the use-case it was tuned for."""
    gp = wec.GaitParams.from_yaml(_SIM_PRESET)
    result = wec.check_envelope(gp, joint_limits, scenario='forward')
    assert result.ok, (
        f'sim_walk.yaml forward check unexpectedly RED: '
        f'{result.first_failure}')
    assert result.scenario == 'forward'
    assert len(result.failures) == 0


def test_check_envelope_absurd_step_length_is_red(joint_limits):
    """Step length way beyond reach must fail."""
    gp = wec.GaitParams(
        radial_distance=0.30, body_height=-0.07,
        step_length_max=0.50,  # absurd
        step_height=0.02,
    )
    result = wec.check_envelope(gp, joint_limits, scenario='forward')
    assert not result.ok
    assert result.first_failure is not None
    assert result.first_failure['reason'] in (
        'joint_limit', 'out_of_reach')


def test_check_envelope_unknown_scenario_raises(joint_limits):
    gp = wec.GaitParams.from_yaml(_SIM_PRESET)
    with pytest.raises(ValueError, match='unknown cmd_vel scenario'):
        wec.check_envelope(gp, joint_limits, scenario='moonwalk')


# ---------------------------------------------------------------------------
# check_envelope_all_scenarios
# ---------------------------------------------------------------------------


def test_check_all_scenarios_returns_four_entries(joint_limits):
    gp = wec.GaitParams.from_yaml(_SIM_PRESET)
    results = wec.check_envelope_all_scenarios(gp, joint_limits)
    assert set(results.keys()) == {
        'forward', 'sidestep', 'yaw', 'diagonal'}
    for r in results.values():
        assert isinstance(r, wec.CheckResult)


# ---------------------------------------------------------------------------
# sweep_heights
# ---------------------------------------------------------------------------


def test_sweep_heights_returns_rows(joint_limits):
    template = wec.GaitParams(
        radial_distance=0.30, body_height=0.0,
        step_length_max=0.0, step_height=0.02,
    )
    rows = wec.sweep_heights(
        template, joint_limits,
        height_min=-0.07, height_max=-0.05, height_step=0.01)
    # 3 heights × 1 step_height = 3 rows
    assert len(rows) == 3
    for r in rows:
        assert isinstance(r, wec.SweepRow)
        assert -0.071 <= r.body_height <= -0.049
        assert r.step_height == pytest.approx(0.02)


def test_sweep_heights_2d_with_step_height_list(joint_limits):
    template = wec.GaitParams(
        radial_distance=0.30, body_height=0.0,
        step_length_max=0.0, step_height=0.02,
    )
    rows = wec.sweep_heights(
        template, joint_limits,
        height_min=-0.06, height_max=-0.05, height_step=0.01,
        step_height_list=[0.015, 0.020, 0.025])
    # 2 heights × 3 step_heights = 6 rows
    assert len(rows) == 6
    step_heights = {r.step_height for r in rows}
    assert step_heights == {0.015, 0.020, 0.025}


# ---------------------------------------------------------------------------
# recommend_for_height
# ---------------------------------------------------------------------------


def test_recommend_returns_valid_preset_for_reasonable_height(joint_limits):
    """body_height=-0.07 is well within reach + cal range."""
    rec = wec.recommend_for_height(
        body_height=-0.07, joint_limits=joint_limits)
    assert rec is not None
    assert rec.body_height == pytest.approx(-0.07)
    assert 0.20 < rec.radial_distance < 0.33
    assert rec.step_length_max > 0
    assert rec.linear_max > 0
    assert rec.safety_margin == pytest.approx(0.10)


def test_recommend_yaml_contains_all_required_keys(joint_limits):
    rec = wec.recommend_for_height(
        body_height=-0.07, joint_limits=joint_limits)
    yaml_text = rec.to_yaml()
    for key in ['/gait_node', 'radial_distance', 'body_height',
                'step_length_max', 'step_height',
                'cycle_time', 'gait_pattern']:
        assert key in yaml_text


def test_recommend_optimize_step_height_picks_best(joint_limits):
    """With --optimize-step-height the tool may pick a different
    step_height than the default, but must return something."""
    rec = wec.recommend_for_height(
        body_height=-0.07, joint_limits=joint_limits,
        optimize_step_height=True)
    assert rec is not None
    # The optimized step_height must come from the sweep range
    assert 0.010 - 1e-6 <= rec.step_height <= 0.040 + 1e-6
