"""Tests für das Body-Leveling-Wiring im gait_node (Block A5 Stufe 2)."""

import math
import time

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
from hexapod_gait.tip_monitor import TIP_NONE
import pytest
import rclpy
from rclpy.parameter import Parameter


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    yield n
    n.destroy_node()


# ----- Deklaration / Defaults -----------------------------------------


def test_leveling_params_declared(node):
    for name in (
        'leveling_enable', 'leveling_kp', 'leveling_ki',
        'leveling_deadband_deg', 'leveling_slew_max_dps',
        'leveling_max_angle_deg', 'leveling_startup_grace',
    ):
        assert node.has_parameter(name)
    assert node.get_parameter('leveling_enable').value is False
    # Engine-Clamp wurde aus dem Param gesetzt.
    assert node._engine.max_level_angle == pytest.approx(math.radians(10.0))


# ----- Leveling-Update-Pfad -------------------------------------------


def test_leveling_disabled_holds_zero_offset(node):
    node._imu_roll, node._imu_pitch = math.radians(10.0), 0.0
    node._update_leveling()
    assert node._engine._level_roll == 0.0
    assert node._engine._level_pitch == 0.0


def test_leveling_enabled_sets_offset_in_standing(node):
    node._leveling_enable = True
    node._imu_roll, node._imu_pitch = math.radians(10.0), 0.0
    assert node._engine.state == GaitEngine.STATE_STANDING
    # dt erzwingen (Tight-Loop hätte ~0 dt → kein sichtbarer Stellweg). Der
    # Konvergenz-Verlauf ist in den BalanceController-Tests abgedeckt; hier
    # zählt nur: enabled+IMU+STANDING → Offset wird vom Controller gesetzt.
    node._last_leveling_t = time.monotonic() - 0.5
    node._update_leveling()
    # Korrektur kontert die positive Neigung → negativer roll-Offset.
    assert node._engine._level_roll < 0.0


def test_leveling_not_applied_without_imu(node):
    node._leveling_enable = True
    node._imu_roll = None
    node._update_leveling()
    assert node._engine._level_roll == 0.0


# ----- Live-Tuning -----------------------------------------------------


def test_leveling_max_angle_live_updates_engine(node):
    res = node.set_parameters([
        Parameter('leveling_max_angle_deg', Parameter.Type.DOUBLE, 6.0),
    ])
    assert res[0].successful
    assert node._engine.max_level_angle == pytest.approx(math.radians(6.0))


def test_leveling_max_angle_walking_param(node):
    assert node.has_parameter('leveling_max_angle_walking_deg')
    assert node._engine.max_level_angle_walking == pytest.approx(math.radians(4.0))
    res = node.set_parameters([
        Parameter('leveling_max_angle_walking_deg', Parameter.Type.DOUBLE, 5.0),
    ])
    assert res[0].successful
    assert node._engine.max_level_angle_walking == pytest.approx(math.radians(5.0))


def test_leveling_active_in_walking(node):
    # Stufe 3a: _update_leveling setzt das Offset auch in WALKING.
    node._leveling_enable = True
    node._imu_roll, node._imu_pitch = math.radians(6.0), 0.0
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # → WALKING
    assert node._engine.state == GaitEngine.STATE_WALKING
    node._last_leveling_t = time.monotonic() - 0.5  # dt erzwingen
    node._update_leveling()
    assert node._engine._level_roll < 0.0


def test_leveling_enable_live(node):
    res = node.set_parameters([
        Parameter('leveling_enable', Parameter.Type.BOOL, True),
    ])
    assert res[0].successful
    assert node._leveling_enable is True


def test_tip_warn_live_rebuilds_monitor(node):
    res = node.set_parameters([
        Parameter('tip_angle_warn_deg', Parameter.Type.DOUBLE, 20.0),
    ])
    assert res[0].successful
    assert node._tip_angle_warn_deg == 20.0
    assert node._tip_monitor._angle_warn == pytest.approx(math.radians(20.0))


# ----- Startup-Grace ---------------------------------------------------


def test_startup_grace_suppresses_tip_during_convergence(node):
    node._leveling_enable = True
    node._leveling_startup_grace = True
    node._imu_roll, node._imu_pitch, node._imu_tilt_rate = (
        math.radians(12.0), 0.0, 0.0,
    )
    # Controller aus dem Totband holen → converged False.
    node._balance.update(math.radians(12.0), 0.0, 0.02)
    assert not node._balance.converged
    assert node._update_tip() == TIP_NONE  # unterdrückt trotz 12° > warn


def test_grace_off_lets_tip_evaluate(node):
    node._leveling_enable = True
    node._leveling_startup_grace = False
    node._imu_roll, node._imu_pitch, node._imu_tilt_rate = (
        math.radians(12.0), 0.0, 0.0,
    )
    node._balance.update(math.radians(12.0), 0.0, 0.02)
    # Grace aus → Tip wertet aus (kein Sofort-WARN wegen Debounce, aber != reset
    # durch Grace). Nach debounce-Ticks würde WARN feuern; hier nur 1 Tick → NONE.
    node._update_tip()  # darf nicht crashen; Pfad ist der normale update


# ----- TF-1: Hang-Schätzung + slope-bewusster Tip ----------------------


def test_slope_params_declared(node):
    for name in (
        'slope_aware_tip_enable', 'slope_estimate_tau_s', 'slope_clamp_deg',
    ):
        assert node.has_parameter(name)
    assert node.get_parameter('slope_aware_tip_enable').value is True
    assert node.get_parameter('slope_estimate_tau_s').value == pytest.approx(0.5)
    assert node.get_parameter('slope_clamp_deg').value == pytest.approx(40.0)
    # Clamp in den ROS-freien Schätzer als rad durchgereicht.
    assert node._slope_est.clamp == pytest.approx(math.radians(40.0))


def test_slope_estimate_snaps_in_standing(node):
    node._imu_roll, node._imu_pitch = math.radians(8.0), math.radians(-2.0)
    assert node._engine.state == GaitEngine.STATE_STANDING
    node._update_slope_estimate()
    # Erstes Sample → Snap auf die Messung (kein Hochlauf).
    assert node._slope_est.slope_roll == pytest.approx(math.radians(8.0))
    assert node._slope_est.slope_pitch == pytest.approx(math.radians(-2.0))


def test_slope_estimate_reset_without_imu(node):
    node._imu_roll, node._imu_pitch = math.radians(8.0), 0.0
    node._update_slope_estimate()  # snap auf 8°
    node._imu_roll = None
    node._update_slope_estimate()  # ohne IMU → reset
    assert node._slope_est.slope_roll == 0.0
    assert node._last_slope_t is None


def test_slope_aware_tip_ignores_constant_slope(node):
    # 20° stetiger Hang (> WARN 15° absolut) → Residual ≈ 0 → kein Alarm.
    node._slope_aware_tip_enable = True
    node._imu_roll, node._imu_pitch, node._imu_tilt_rate = (
        math.radians(20.0), 0.0, 0.0,
    )
    for _ in range(60):
        node._update_slope_estimate()
        assert node._update_tip() == TIP_NONE


def test_raw_tip_would_warn_on_same_slope(node):
    # Gegenprobe: ohne slope-Awareness feuert die absolute Schwelle bei 20°.
    node._slope_aware_tip_enable = False
    node._imu_roll, node._imu_pitch, node._imu_tilt_rate = (
        math.radians(20.0), 0.0, 0.0,
    )
    level = TIP_NONE
    for _ in range(node._tip_debounce_ticks + 2):
        node._update_slope_estimate()
        level = node._update_tip()
    assert level != TIP_NONE  # absolute 20° > WARN 15° → WARN/CRIT


def test_slope_params_live_tunable(node):
    res = node.set_parameters([
        Parameter('slope_estimate_tau_s', Parameter.Type.DOUBLE, 1.5),
        Parameter('slope_clamp_deg', Parameter.Type.DOUBLE, 25.0),
        Parameter('slope_aware_tip_enable', Parameter.Type.BOOL, False),
    ])
    assert res[0].successful
    assert node._slope_est.tau == pytest.approx(1.5)
    assert node._slope_est.clamp == pytest.approx(math.radians(25.0))
    assert node._slope_aware_tip_enable is False


def test_slope_params_reject_invalid(node):
    res = node.set_parameters([
        Parameter('slope_estimate_tau_s', Parameter.Type.DOUBLE, -1.0),
    ])
    assert not res[0].successful
    res2 = node.set_parameters([
        Parameter('slope_clamp_deg', Parameter.Type.DOUBLE, 0.0),
    ])
    assert not res2[0].successful
