"""Unit-Tests für SlopeEstimator (Block A5 TF-1) — ohne ROS."""

import math

from hexapod_gait.slope_estimator import SlopeEstimator
from hexapod_gait.tip_monitor import TIP_CRIT, TIP_NONE, TipMonitor


TAU = 0.5
CLAMP = math.radians(40.0)
DT = 0.02  # 50 Hz


def _est(tau=TAU, clamp=CLAMP):
    return SlopeEstimator(tau, clamp)


# ----- Snap-Init ------------------------------------------------------


def test_first_sample_snaps_to_measurement():
    e = _est()
    # Erstes Sample nach Init → Schätzung = Messung (kein Hochlauf von 0).
    sr, sp = e.update(math.radians(8.0), math.radians(-3.0), DT)
    assert math.isclose(sr, math.radians(8.0), abs_tol=1e-12)
    assert math.isclose(sp, math.radians(-3.0), abs_tol=1e-12)


def test_reset_rearms_snap_init():
    e = _est()
    e.update(math.radians(8.0), 0.0, DT)
    for _ in range(50):
        e.update(math.radians(8.0), 0.0, DT)
    e.reset()
    assert e.slope_roll == 0.0 and e.slope_pitch == 0.0
    # Nach reset snappt das nächste Sample wieder direkt auf die Messung.
    sr, _ = e.update(math.radians(12.0), 0.0, DT)
    assert math.isclose(sr, math.radians(12.0), abs_tol=1e-12)


# ----- Konvergenz / Lag -----------------------------------------------


def test_converges_to_constant_input():
    e = _est()
    target = math.radians(10.0)
    # Snap auf 0-Start: erstes Sample wäre target → stattdessen erst 0 snappen,
    # dann auf target rampen, um den EMA-Lag zu prüfen.
    e.update(0.0, 0.0, DT)  # Snap auf 0
    for _ in range(int(5 * TAU / DT)):  # ~5τ
        e.update(target, 0.0, DT)
    # Nach ~5τ praktisch konvergiert.
    assert math.isclose(e.slope_roll, target, rel_tol=0.02)


def test_lag_after_step_is_below_target_one_tau():
    e = _est()
    e.update(0.0, 0.0, DT)  # Snap auf 0
    step = math.radians(10.0)
    n = int(TAU / DT)  # genau 1 τ Sprung-Antwort
    for _ in range(n):
        e.update(step, 0.0, DT)
    # Nach 1τ erreicht ein EMA ~63% → deutlich unter dem Zielwert (Lag).
    assert 0.4 * step < e.slope_roll < 0.8 * step


def test_pitch_axis_independent_of_roll():
    e = _est()
    e.update(0.0, 0.0, DT)
    for _ in range(200):
        e.update(math.radians(10.0), math.radians(-5.0), DT)
    assert math.isclose(e.slope_roll, math.radians(10.0), rel_tol=0.02)
    assert math.isclose(e.slope_pitch, math.radians(-5.0), rel_tol=0.02)


# ----- Clamp ----------------------------------------------------------


def test_estimate_clamped_to_max():
    e = _est(clamp=math.radians(40.0))
    # Snap auf einen Wert über dem Clamp → direkt geclampt.
    sr, _ = e.update(math.radians(60.0), 0.0, DT)
    assert math.isclose(sr, math.radians(40.0), abs_tol=1e-9)


def test_slow_tipover_does_not_track_past_clamp():
    e = _est(clamp=math.radians(40.0))
    e.update(0.0, 0.0, DT)
    # Langsam über den Clamp hinaus „wegkippen": Schätzung sättigt bei 40°.
    for _ in range(2000):
        e.update(math.radians(80.0), 0.0, DT)
    assert e.slope_roll <= math.radians(40.0) + 1e-9


def test_clamp_setter_reclamps_current_estimate():
    e = _est(clamp=math.radians(40.0))
    e.update(math.radians(30.0), 0.0, DT)
    e.clamp = math.radians(20.0)
    assert e.slope_roll <= math.radians(20.0) + 1e-9


# ----- τ-Sonderfälle --------------------------------------------------


def test_tau_zero_means_filter_off():
    e = _est(tau=0.0)
    e.update(0.0, 0.0, DT)  # Snap auf 0
    # τ=0 → alpha=1 → Schätzung folgt der Messung sofort.
    sr, _ = e.update(math.radians(7.0), 0.0, DT)
    assert math.isclose(sr, math.radians(7.0), abs_tol=1e-12)


def test_nonpositive_dt_holds_estimate():
    e = _est()
    e.update(0.0, 0.0, DT)  # Snap
    e.update(math.radians(5.0), 0.0, DT)
    held = e.slope_roll
    # dt=0 (Tight-Loop) → keine Zeitintegration, Schätzung unverändert.
    e.update(math.radians(20.0), 0.0, 0.0)
    assert e.slope_roll == held


# ----- Residual -------------------------------------------------------


def test_residual_is_measurement_minus_estimate():
    e = _est()
    e.update(math.radians(8.0), math.radians(2.0), DT)  # Snap → est = Messung
    rr, rp = e.residual(math.radians(8.0), math.radians(2.0))
    # Stetiger Hang: Residual ≈ 0.
    assert math.isclose(rr, 0.0, abs_tol=1e-12)
    assert math.isclose(rp, 0.0, abs_tol=1e-12)
    # Schneller Sprung über die Schätzung hinaus → Residual = Sprunghöhe.
    rr2, _ = e.residual(math.radians(28.0), math.radians(2.0))
    assert math.isclose(rr2, math.radians(20.0), abs_tol=1e-12)


# ----- Integration: residual-gefütterter TipMonitor -------------------
# Spiegelt die gait_node-Verdrahtung (TF1.2): TipMonitor bekommt das Residual.


def _tip():
    return TipMonitor(
        math.radians(15.0), math.radians(25.0), math.radians(80.0), 5,
    )


def test_constant_slope_does_not_trip_tip():
    """Stetiger 20°-Hang (> WARN 15° absolut) → Residual ≈ 0 → kein Alarm."""
    e = _est()
    m = _tip()
    slope = math.radians(20.0)
    # Snap auf den Hang, dann viele Ticks auf konstantem Hang.
    e.update(slope, 0.0, DT)
    for _ in range(100):
        e.update(slope, 0.0, DT)
        rr, rp = e.residual(slope, 0.0)
        assert m.update(rr, rp, 0.0) == TIP_NONE


def test_fast_tilt_ramp_trips_tip_via_residual():
    """Anhaltender Kipp über Hang → Filter lagt → Residual trippt CRIT (Rate 0)."""
    e = _est()
    m = _tip()
    slope = math.radians(20.0)
    e.update(slope, 0.0, DT)
    for _ in range(50):
        e.update(slope, 0.0, DT)
    # Fortlaufende Kipp-Rampe (+2°/Tick ≈ 100°/s). Der langsame Filter (τ=0.5 s)
    # hängt weit zurück → Residual wächst über CRIT 25° und bleibt dort (Schätzung
    # sättigt am Clamp 40°, Messung läuft weiter weg) → über die Entprellung → CRIT.
    level = TIP_NONE
    measured = math.radians(20.0)
    for _ in range(40):
        measured += math.radians(2.0)
        e.update(measured, 0.0, DT)
        rr, rp = e.residual(measured, 0.0)
        level = m.update(rr, rp, 0.0)
        if level == TIP_CRIT:
            break
    assert level == TIP_CRIT
