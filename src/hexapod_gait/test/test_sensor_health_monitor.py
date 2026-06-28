"""
Tests für SensorHealthMonitor (Block A5 S4-5) — Sensor-Plausibilität.

Deckt: stuck-on (lückenloser Apex-Pass über N aufeinanderfolgende Pässe —
robust gegen das gz-Apex-Artefakt aus lückenhaftem Kontakt), dead (überhaupt
kein Kontakt über dead_ticks; stuck-on erscheint nie als dead), gesundes Bein
(nie faulty), Latch + reset, Min-Pass-Länge.

legs-Tupel = ``(is_swing, local_phase, contact)``.
"""

from hexapod_gait.sensor_health_monitor import (
    REASON_DEAD,
    REASON_STUCK_ON,
    SensorHealthMonitor,
)


# apex_fault_cycles klein; dead_ticks groß sofern nicht getestet → isoliert
# stuck-on bzw. dead.
def _mon(apex_lo=0.3, apex_hi=0.7, cycles=3, dead=100000):
    return SensorHealthMonitor(
        apex_lo=apex_lo, apex_hi=apex_hi, apex_fault_cycles=cycles,
        dead_ticks=dead,
    )


def _apex_pass(mon, leg, contact_seq, others=None):
    """
    Einen Schwung-Pass durch das Apex-Band [0.3,0.7] simulieren, dann schließen.

    ``contact_seq`` = Kontakt-Werte pro In-Band-Tick; danach ein Tick außerhalb
    des Bandes (Stance) → schließt den Pass. ``others`` = zusätzliche Beine pro
    Tick (z.B. ein Bein das parallel dead wird). Gibt das letzte Result zurück.
    """
    n = len(contact_seq)
    res = None
    for i, c in enumerate(contact_seq):
        phase = 0.3 + 0.4 * (i + 0.5) / n  # in [0.3,0.7] verteilt
        legs = {leg: (True, phase, c)}
        if others:
            legs.update(others)
        res = mon.update(legs)
    legs = {leg: (False, 0.1, False)}  # Band verlassen → Pass schließen
    if others:
        legs.update(others)
    res = mon.update(legs)
    return res


# --- stuck-on (Pass-Logik) ------------------------------------------------

def test_stuck_on_flags_after_full_passes():
    mon = _mon(cycles=3)
    res = None
    for _ in range(3):
        res = _apex_pass(mon, 1, [True] * 6)
    assert res[1] == (True, REASON_STUCK_ON)
    assert mon.faulty_legs == {1}


def test_stuck_on_not_before_cycles():
    mon = _mon(cycles=3)
    res = None
    for _ in range(2):  # nur 2 < 3 lückenlose Pässe
        res = _apex_pass(mon, 1, [True] * 6)
    assert res[1] == (False, None)


def test_gappy_apex_never_stuck_on():
    # Das gz-Artefakt: meist Kontakt im Apex, aber EINE Lücke pro Pass →
    # resettet jeden Pass → nie stuck-on (das war der Falsch-Positiv-Fix).
    mon = _mon(cycles=3)
    res = None
    for _ in range(50):
        res = _apex_pass(mon, 1, [True, True, False, True, True, True])
    assert res[1] == (False, None)


def test_single_full_pass_does_not_persist():
    # Walk-Start-Transient = ein einzelner lückenloser Pass, danach lückenhaft →
    # Reset → nie geflaggt (braucht N IN FOLGE).
    mon = _mon(cycles=3)
    _apex_pass(mon, 1, [True] * 6)                       # 1 voll
    _apex_pass(mon, 1, [True, False, True, True, True])  # lückenhaft → Reset
    res = None
    for _ in range(2):
        res = _apex_pass(mon, 1, [True] * 6)             # nur 2 in Folge
    assert res[1] == (False, None)


def test_early_swing_contact_below_band_ignored():
    # contact_timeout-Nachhall: Kontakt bei Phase 0.1 (< apex_lo 0.3) öffnet
    # keinen Pass → nie stuck-on.
    mon = _mon(cycles=3)
    res = None
    for _ in range(200):
        res = mon.update({1: (True, 0.1, True)})
    assert res[1] == (False, None)


def test_short_apex_pass_does_not_count():
    # Ein 2-Tick-Pass (< _MIN_APEX_PASS_TICKS=3) zählt nicht als voller Pass.
    mon = _mon(cycles=3)
    res = None
    for _ in range(10):
        res = _apex_pass(mon, 1, [True, True])
    assert res[1] == (False, None)


# --- dead -----------------------------------------------------------------

def test_dead_flags_after_dead_ticks():
    mon = _mon(cycles=1000, dead=10)
    res = None
    for _ in range(10):
        res = mon.update({1: (False, 0.5, False)})  # nie Kontakt
    assert res[1] == (True, REASON_DEAD)
    assert 1 in mon.faulty_legs


def test_dead_not_before_dead_ticks():
    mon = _mon(cycles=1000, dead=10)
    res = None
    for _ in range(9):
        res = mon.update({1: (False, 0.5, False)})
    assert res[1] == (False, None)


def test_any_contact_resets_dead():
    # Periodischer Kontakt (Periode 6 < dead_ticks 10) → nie dead.
    mon = _mon(cycles=1000, dead=10)
    res = None
    for cycle in range(10):
        for ph in range(6):
            contact = (ph >= 3)  # zweite Hälfte = Stance-Kontakt
            res = mon.update({1: (ph < 3, 0.5, contact)})
    assert res[1] == (False, None)


def test_stuck_on_never_flagged_dead():
    # Schlüssel-Regression: stuck-on (immer Kontakt) darf NIE als dead erscheinen,
    # auch über viele dead_ticks hinweg.
    mon = _mon(cycles=1000, dead=10)
    res = None
    for _ in range(200):
        res = mon.update({1: (False, 0.5, True)})  # immer Kontakt (stuck-on-artig)
    assert res[1] == (False, None)


# --- gesund (Regression) --------------------------------------------------

def test_healthy_leg_never_faulty():
    # Realistischer Voll-Cycle, plausible Kontakte → nie faulty (alle 6 Beine).
    mon = _mon(cycles=3, dead=200)
    res = None
    for cycle in range(10):
        for ph in range(50):
            frac = ph / 50.0
            if frac < 0.5:                # Schwung: Fuß oben, kein Kontakt
                leg = (True, frac / 0.5, False)
            else:                         # Stance: Kontakt
                leg = (False, (frac - 0.5) / 0.5, True)
            res = mon.update({i: leg for i in range(1, 7)})
    assert all(not faulty for faulty, _ in res.values())
    assert mon.faulty_legs == set()


# --- Latch + reset --------------------------------------------------------

def test_latch_holds_until_reset():
    mon = _mon(cycles=2)
    for _ in range(2):
        _apex_pass(mon, 1, [True] * 6)
    assert mon.faulty_legs == {1}
    # Jetzt nur noch lückenhafte (gesunde) Pässe → bleibt latched.
    res = None
    for _ in range(20):
        res = _apex_pass(mon, 1, [True, False, True, True, True])
    assert res[1] == (True, REASON_STUCK_ON)
    assert mon.faulty_legs == {1}
    # reset() löscht den Latch.
    mon.reset()
    assert mon.faulty_legs == set()
    res = _apex_pass(mon, 1, [True, False, True, True, True])
    assert res[1] == (False, None)


def test_independent_legs():
    # Bein 1 stuck-on (2 volle Pässe), Bein 4 dead (kein Kontakt) — unabhängig.
    mon = _mon(cycles=2, dead=8)
    res = None
    others = {4: (False, 0.5, False)}  # Bein 4: Stance ohne Kontakt → dead
    for _ in range(2):
        res = _apex_pass(mon, 1, [True] * 6, others=others)
    assert res[1] == (True, REASON_STUCK_ON)
    assert res[4] == (True, REASON_DEAD)
