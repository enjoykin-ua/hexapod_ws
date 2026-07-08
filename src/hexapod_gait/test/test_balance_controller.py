"""Unit-Tests für BalanceController (Block A5 Stufe 2) — ohne ROS."""

import math

from hexapod_gait.balance_controller import BalanceController
import pytest


DT = 0.02  # 50 Hz


def _ctrl(
    kp=0.3, ki=0.8, deadband_deg=1.0, slew_dps=60.0, max_deg=20.0,
):
    return BalanceController(
        kp=kp,
        ki=ki,
        deadband=math.radians(deadband_deg),
        slew_max=math.radians(slew_dps),
        max_level_angle=math.radians(max_deg),
    )


def test_fresh_controller_is_neutral_and_converged():
    c = _ctrl()
    assert c.correction == (0.0, 0.0)
    assert c.converged  # error-Cache 0 → im Totband


def test_deadband_no_chatter():
    # Neigung innerhalb des Totbands → keine Korrektur (P=0, Integrator frozen).
    c = _ctrl(deadband_deg=2.0)
    for _ in range(200):
        corr = c.update(math.radians(1.0), math.radians(-1.5), DT)
    assert abs(corr[0]) < 1e-9
    assert abs(corr[1]) < 1e-9
    assert c.converged


def test_first_tick_dt_zero_holds_zero():
    # dt<=0 → kein Slew-Step, Ausgang bleibt 0.
    c = _ctrl()
    corr = c.update(math.radians(10.0), 0.0, 0.0)
    assert corr == (0.0, 0.0)


def test_dt_zero_holds_previous_output():
    c = _ctrl()
    for _ in range(50):
        c.update(math.radians(10.0), 0.0, DT)
    held = c.correction
    corr = c.update(math.radians(10.0), 0.0, 0.0)  # dt=0
    assert corr == held


def test_slew_rate_limits_first_step():
    # Großer Sprung-Bedarf → erster Schritt höchstens slew_max·dt.
    c = _ctrl(slew_dps=5.0, max_deg=20.0)
    corr = c.update(math.radians(40.0), 0.0, 0.1)
    assert abs(corr[0]) <= math.radians(5.0) * 0.1 + 1e-12


def test_anti_windup_and_max_clamp():
    # Dauerhaft große Neigung (open loop) → Ausgang nie über max_level_angle.
    c = _ctrl(max_deg=10.0, slew_dps=200.0)
    last = (0.0, 0.0)
    for _ in range(2000):
        last = c.update(math.radians(40.0), 0.0, DT)
        assert abs(last[0]) <= math.radians(10.0) + 1e-9
    # gegen das negative Limit gelaufen (kontert positive Neigung).
    assert last[0] < -math.radians(9.5)


def test_sign_counters_tilt():
    # Positive roll-Neigung → negative Korrektur (kontert), und umgekehrt.
    c = _ctrl(slew_dps=200.0)
    for _ in range(10):
        corr_pos = c.update(math.radians(8.0), 0.0, DT)
    c.reset()
    for _ in range(10):
        corr_neg = c.update(math.radians(-8.0), 0.0, DT)
    assert corr_pos[0] < 0.0
    assert corr_neg[0] > 0.0


def test_axes_independent():
    c = _ctrl(slew_dps=200.0)
    for _ in range(50):
        corr = c.update(0.0, math.radians(8.0), DT)
    assert abs(corr[0]) < 1e-9    # roll bleibt 0
    assert abs(corr[1]) > 1e-3    # pitch reagiert


def test_converged_flips_with_tilt():
    c = _ctrl(deadband_deg=1.0)
    c.update(math.radians(10.0), 0.0, DT)
    assert not c.converged
    c.reset()
    assert c.converged


def test_closed_loop_converges_to_level():
    # Vereinfachtes Plant-Modell: gemessene Neigung = Hang + angewandte
    # Korrektur (Korrektur levelt den Körper). Erwartung: Neigung -> ~0,
    # Korrektur -> ~ -Hang (hält die Lage über den Integrator).
    c = _ctrl(kp=0.3, ki=0.8, deadband_deg=1.0, slew_dps=60.0, max_deg=20.0)
    slope = math.radians(10.0)
    measured = slope
    corr = (0.0, 0.0)
    for _ in range(2000):
        corr = c.update(measured, 0.0, DT)
        measured = slope + corr[0]
    assert abs(measured) < math.radians(1.0) + 1e-3   # im Totband
    assert abs(corr[0] - (-slope)) < math.radians(2.0)  # ≈ -Hang
    assert c.converged


def test_set_gains_reclamps_integrator():
    # Integrator auf -20° aufgelaufen, dann max auf 5° gesenkt → Ausgang folgt.
    c = _ctrl(max_deg=20.0, slew_dps=400.0)
    for _ in range(2000):
        c.update(math.radians(40.0), 0.0, DT)
    assert c.correction[0] < -math.radians(15.0)
    c.set_gains(max_level_angle=math.radians(5.0))
    # Integrator ist sofort reclampt; der Ausgang slewt aufs neue Limit nach.
    for _ in range(20):
        corr = c.update(math.radians(40.0), 0.0, DT)
    assert abs(corr[0]) <= math.radians(5.0) + 1e-9


# ----- TF-2: Gyro-D-Term ----------------------------------------------


def test_kd_zero_keeps_stage2_behavior():
    """Kd=0 (Default): durchgereichte Gyro-Raten ändern nichts (Back-Compat)."""
    c1 = _ctrl()
    c2 = _ctrl()
    for _ in range(10):
        a = c1.update(math.radians(5.0), math.radians(-3.0), DT)
        b = c2.update(
            math.radians(5.0), math.radians(-3.0), DT,
            math.radians(50.0), math.radians(-40.0),
        )
        assert a == b


def test_gyro_d_opposes_positive_rate():
    """Positive roll-Drehrate → negative Korrektur (wirkt der Rate entgegen)."""
    c = _ctrl(ki=0.0)
    c.set_gains(kd=0.1)
    corr = c.update(0.0, 0.0, DT, gyro_roll=math.radians(50.0))
    assert corr[0] < 0.0


def test_gyro_d_opposes_negative_rate():
    """Negative pitch-Drehrate → positive Korrektur (gegenläufig)."""
    c = _ctrl(ki=0.0)
    c.set_gains(kd=0.1)
    corr = c.update(0.0, 0.0, DT, gyro_pitch=math.radians(-50.0))
    assert corr[1] > 0.0


def test_gyro_d_acts_inside_deadband():
    """Im Winkel-Totband (P/I aus) dämpft D trotzdem die Drehrate."""
    c = _ctrl(deadband_deg=2.0, ki=0.0)
    c.set_gains(kd=0.1)
    # Winkel 1° < Totband 2° → P/I=0; nur die Rate treibt den Ausgang.
    corr = c.update(math.radians(1.0), 0.0, DT, gyro_roll=math.radians(50.0))
    assert corr[0] != 0.0


def test_gyro_d_respects_clamp():
    """Auch ein riesiger D-Beitrag bleibt im max_level_angle-Clamp."""
    c = _ctrl(max_deg=10.0, slew_dps=100000.0, ki=0.0)
    c.set_gains(kd=1.0)
    corr = c.update(0.0, 0.0, DT, gyro_roll=math.radians(1000.0))
    assert abs(corr[0]) <= math.radians(10.0) + 1e-9


def _osc_late_peak(kd, steps=400):
    """Spätzeit-Amplitude eines symplektischen Oszillator-Plants bei Kd (P+D, ki=0)."""
    c = _ctrl(kp=0.5, ki=0.0, deadband_deg=0.5, slew_dps=100000.0, max_deg=60.0)
    c.set_gains(kd=kd)
    a = math.radians(5.0)
    v = 0.0
    w2 = 150.0
    late = 0.0
    for i in range(steps):
        corr = c.update(a, 0.0, DT, gyro_roll=v)[0]
        v += w2 * (corr - a) * DT      # semi-implizit (symplektisch) → stabil
        a += v * DT
        if i > steps // 2:
            late = max(late, abs(a))
    return late


def test_gyro_d_damps_oscillation():
    """Closed-Loop: mit Gyro-D klingt die Schwingung ab, ohne nicht."""
    assert _osc_late_peak(kd=0.05) < 0.3 * _osc_late_peak(kd=0.0)


# ----- Stufe 7 (v2): Zwei-Fenster-Hysterese ---------------------------


def test_hysteresis_enter_exit():
    """Hysterese: resume ≥ outer, stop < inner; dazwischen gehalten (Latch)."""
    c = _ctrl(slew_dps=100000.0, max_deg=60.0)
    c.set_axis_gains('roll', inner=math.radians(1.0), outer=math.radians(2.0))
    ax = c._roll
    c.update(math.radians(1.5), 0.0, DT)   # zwischen, nie gestartet → aus
    assert not ax.regulating
    c.update(math.radians(2.5), 0.0, DT)   # ≥ outer → an
    assert ax.regulating
    c.update(math.radians(1.5), 0.0, DT)   # zwischen → bleibt an (Latch)
    assert ax.regulating
    c.update(math.radians(0.5), 0.0, DT)   # < inner → aus
    assert not ax.regulating


def test_no_edge_chatter():
    """Signal oszilliert eng über outer → Latch flippt genau EINMAL (kein Chatter)."""
    c = _ctrl(slew_dps=100000.0, max_deg=60.0)
    c.set_axis_gains('roll', inner=math.radians(1.0), outer=math.radians(2.0))
    ax = c._roll
    prev = ax.regulating
    flips = 0
    for _ in range(10):
        for val in (2.2, 1.8, 2.1, 1.85, 2.3, 1.9):  # bleibt über inner
            c.update(math.radians(val), 0.0, DT)
            if ax.regulating != prev:
                flips += 1
                prev = ax.regulating
    assert flips == 1


def test_backcompat_single_threshold_at_equality():
    """inner==outer: regelnd iff |x|≥D (resume ≥, stop <) — wie altes Totband."""
    c = _ctrl(deadband_deg=1.5, slew_dps=100000.0)  # inner==outer==1.5
    ax = c._roll
    c.update(math.radians(1.0), 0.0, DT)   # < 1.5 → aus
    assert not ax.regulating
    c.update(math.radians(1.5), 0.0, DT)   # ≥ 1.5 → an
    assert ax.regulating
    c.update(math.radians(1.4), 0.0, DT)   # < 1.5 → aus
    assert not ax.regulating


def test_converged_reflects_not_regulating():
    c = _ctrl(deadband_deg=1.0, slew_dps=100000.0)
    assert c.converged                      # frisch → nicht regelnd
    c.update(math.radians(5.0), 0.0, DT)    # roll regelt
    assert not c.converged
    c.update(math.radians(0.5), 0.0, DT)    # < inner → stop
    assert c.converged


# ----- Stufe 7 (v2): Dual-Tiefpass + Filter-Flag (A) + Snap-Init (B) ---


def test_dual_lowpass_smooths_when_filter_on():
    c = _ctrl(slew_dps=100000.0)
    c.set_axis_gains(
        'roll', tau_slow=1.0, tau_fast=0.0,
        inner=math.radians(1.0), outer=math.radians(2.0),
    )
    ax = c._roll
    c.update(0.0, 0.0, DT, filter_roll=True)             # Snap m_slow=0
    c.update(math.radians(10.0), 0.0, DT, filter_roll=True)
    assert ax.m_slow < math.radians(10.0)               # slow lagt (gefiltert)
    assert ax.m_fast == pytest.approx(math.radians(10.0))  # tau_fast=0 → =measured


def test_filter_bypass_when_flag_false():
    """apply_filter=False (Residual) → kein Filter, m=measured (Finding A)."""
    c = _ctrl(slew_dps=100000.0)
    c.set_axis_gains(
        'roll', tau_slow=1.0, tau_fast=0.5,
        inner=math.radians(1.0), outer=math.radians(2.0),
    )
    ax = c._roll
    c.update(0.0, 0.0, DT, filter_roll=False)            # Snap
    c.update(math.radians(10.0), 0.0, DT, filter_roll=False)
    assert ax.m_slow == pytest.approx(math.radians(10.0))  # kein Lag (bypass)
    assert ax.m_fast == pytest.approx(math.radians(10.0))


def test_snap_init_no_rampup_engages_immediately():
    c = _ctrl(slew_dps=100000.0)
    c.set_axis_gains(
        'roll', tau_slow=5.0, inner=math.radians(1.0), outer=math.radians(2.0),
    )
    ax = c._roll
    c.update(math.radians(8.0), 0.0, DT, filter_roll=True)  # erstes Sample am Hang
    assert ax.m_slow == pytest.approx(math.radians(8.0))    # Snap statt Hochlauf
    assert ax.regulating                                    # |8°|≥outer → sofort an


def test_set_axis_gains_independent():
    c = _ctrl()
    c.set_axis_gains('roll', kp=1.3)
    c.set_axis_gains('pitch', kp=0.5)
    assert c._roll.kp == pytest.approx(1.3)
    assert c._pitch.kp == pytest.approx(0.5)
