"""Unit-Tests für TipMonitor (Block A5 Stufe 1) — ohne ROS."""

import math

from hexapod_gait.tip_monitor import (
    quat_to_roll_pitch,
    TIP_CRIT,
    TIP_NONE,
    TIP_WARN,
    TipMonitor,
)


WARN = math.radians(15.0)
CRIT = math.radians(25.0)
RATE = math.radians(80.0)
DEB = 5


def _mon():
    return TipMonitor(WARN, CRIT, RATE, DEB)


def test_level_below_warn_is_none():
    m = _mon()
    for _ in range(20):
        assert m.update(math.radians(5.0), 0.0, 0.0) == TIP_NONE


def test_warn_needs_debounce():
    m = _mon()
    # debounce-1 Ticks über warn -> noch NONE
    for _ in range(DEB - 1):
        assert m.update(math.radians(18.0), 0.0, 0.0) == TIP_NONE
    # debounce-ter Tick -> WARN
    assert m.update(math.radians(18.0), 0.0, 0.0) == TIP_WARN


def test_warn_resets_below_threshold():
    m = _mon()
    for _ in range(DEB - 1):
        m.update(math.radians(18.0), 0.0, 0.0)
    # einmal drunter -> Zähler zurück, kein WARN beim nächsten Über-Tick
    assert m.update(math.radians(5.0), 0.0, 0.0) == TIP_NONE
    assert m.update(math.radians(18.0), 0.0, 0.0) == TIP_NONE


def test_crit_by_angle_latches():
    m = _mon()
    for _ in range(DEB - 1):
        assert m.update(math.radians(30.0), 0.0, 0.0) == TIP_NONE
    assert m.update(math.radians(30.0), 0.0, 0.0) == TIP_CRIT
    assert m.crit_latched
    # bleibt CRIT, auch wenn Winkel wieder eben wird (Latch)
    assert m.update(0.0, 0.0, 0.0) == TIP_CRIT


def test_crit_by_pitch_axis():
    m = _mon()
    for _ in range(DEB):
        m.update(0.0, math.radians(30.0), 0.0)
    assert m.crit_latched


def test_crit_by_rate():
    m = _mon()
    # Winkel klein, aber Kipprate über rate_crit
    for _ in range(DEB - 1):
        assert m.update(0.0, 0.0, math.radians(120.0)) == TIP_NONE
    assert m.update(0.0, 0.0, math.radians(120.0)) == TIP_CRIT


def test_reset_clears_latch_and_counts():
    m = _mon()
    for _ in range(DEB):
        m.update(math.radians(30.0), 0.0, 0.0)
    assert m.crit_latched
    m.reset()
    assert not m.crit_latched
    assert m.update(math.radians(5.0), 0.0, 0.0) == TIP_NONE


def test_quat_identity_is_level():
    roll, pitch = quat_to_roll_pitch(0.0, 0.0, 0.0, 1.0)
    assert abs(roll) < 1e-9
    assert abs(pitch) < 1e-9


def test_quat_roll_20deg():
    # 20° Roll um X: q = (sin(10°), 0, 0, cos(10°))
    half = math.radians(10.0)
    roll, pitch = quat_to_roll_pitch(math.sin(half), 0.0, 0.0, math.cos(half))
    assert abs(roll - math.radians(20.0)) < 1e-6
    assert abs(pitch) < 1e-6


# ----- Stufe 7 (E5): per-Achse-Schwellen ------------------------------


def _mon_per_axis():
    # Roll strenger (crit 20°) als pitch (crit 30°); warn beide 15°.
    return TipMonitor(
        math.radians(15.0), math.radians(20.0), RATE, DEB,
        angle_warn_pitch=math.radians(15.0),
        angle_crit_pitch=math.radians(30.0),
    )


def test_per_axis_crit_roll_fires_at_lower_angle():
    m = _mon_per_axis()
    # 22° roll ≥ crit_roll 20° → CRIT nach Debounce.
    for _ in range(DEB - 1):
        assert m.update(math.radians(22.0), 0.0, 0.0) == TIP_NONE
    assert m.update(math.radians(22.0), 0.0, 0.0) == TIP_CRIT


def test_per_axis_crit_pitch_higher_threshold_no_crit():
    m = _mon_per_axis()
    # 22° pitch < crit_pitch 30° → kein CRIT (aber ≥ warn_pitch 15° → WARN).
    lvl = TIP_NONE
    for _ in range(DEB):
        lvl = m.update(0.0, math.radians(22.0), 0.0)
    assert lvl == TIP_WARN
    assert not m.crit_latched


def test_symmetric_constructor_backcompat():
    # Ohne pitch-Args → beide Achsen gleiche Schwelle (altes Verhalten).
    m = TipMonitor(WARN, CRIT, RATE, DEB)
    for _ in range(DEB):
        lvl = m.update(0.0, math.radians(30.0), 0.0)
    assert lvl == TIP_CRIT  # 30° pitch ≥ 25° crit (symmetrisch)
