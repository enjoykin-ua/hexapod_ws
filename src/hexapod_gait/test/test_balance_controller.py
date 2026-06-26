"""Unit-Tests für BalanceController (Block A5 Stufe 2) — ohne ROS."""

import math

from hexapod_gait.balance_controller import BalanceController


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
