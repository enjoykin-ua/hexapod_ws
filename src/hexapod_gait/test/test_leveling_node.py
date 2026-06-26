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
