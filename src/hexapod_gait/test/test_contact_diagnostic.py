"""Unit-Tests für ContactDiagnostic (Block A5 S4-1) — ohne ROS."""

from hexapod_gait.contact_diagnostic import ContactDiagnostic


def _d():
    return ContactDiagnostic((1,))


# ----- Quote / Grundverhalten ----------------------------------------


def test_non_walking_ticks_ignored():
    d = _d()
    for _ in range(10):
        d.update(1, True, False, 0.5, False)  # is_walking=False
    s = d.summary()[1]
    assert s['total_ticks'] == 0
    assert s['true_quote'] is None


def test_true_quote_counts_walking_ticks():
    d = _d()
    # 3× Kontakt, 1× kein Kontakt (alle WALKING, Stance außerhalb der Fenster).
    for c in (True, True, False, True):
        d.update(1, c, False, 0.0, True)
    s = d.summary()[1]
    assert s['total_ticks'] == 4
    assert s['true_quote'] == 0.75


# ----- Plausibilität --------------------------------------------------


def test_apex_false_contact_flagged():
    d = _d()
    d.update(1, False, True, 0.1, True)   # Schwung-Start, kein Kontakt
    d.update(1, True, True, 0.5, True)    # Apex MIT Kontakt → implausibel
    assert d.summary()[1]['apex_false'] == 1


def test_stance_gap_flagged():
    d = _d()
    d.update(1, True, False, 0.0, True)    # Stance-Start mit Kontakt
    d.update(1, False, False, 0.5, True)   # Stance-Mitte OHNE Kontakt → Aussetzer
    assert d.summary()[1]['stance_gap'] == 1


def test_clean_walk_no_implausible():
    d = _d()
    # sauberer Zyklus: Schwung ohne Kontakt, Stance mit Kontakt.
    seq = [
        (False, True, 0.3), (False, True, 0.6),     # Schwung, Fuß oben
        (True, False, 0.3), (True, False, 0.6),     # Stance, belastet
    ]
    for contact, sw, ph in seq * 3:
        d.update(1, contact, sw, ph, True)
    s = d.summary()[1]
    assert s['apex_false'] == 0
    assert s['stance_gap'] == 0


# ----- Touchdown-Latenz ----------------------------------------------


def test_touchdown_latency_immediate():
    d = _d()
    d.update(1, False, True, 0.9, True)    # später Schwung
    # Stance-Start + Kontakt im selben Tick → Latenz 0.
    d.update(1, True, False, 0.0, True)
    s = d.summary()[1]
    assert s['touchdowns'] == 1
    assert s['latency_avg'] == 0
    assert s['latency_max'] == 0


def test_touchdown_latency_delayed():
    d = _d()
    d.update(1, False, True, 0.9, True)    # Schwung
    d.update(1, False, False, 0.0, True)   # Stance-Start, noch kein Kontakt
    d.update(1, True, False, 0.05, True)   # Kontakt 1 Tick später → Latenz 1
    s = d.summary()[1]
    assert s['touchdowns'] == 1
    assert s['latency_avg'] == 1
    assert s['latency_max'] == 1


def test_missed_touchdown_when_no_contact_in_stance():
    d = _d()
    d.update(1, False, True, 0.9, True)    # Schwung
    d.update(1, False, False, 0.1, True)   # Stance-Start, kein Kontakt (awaiting)
    d.update(1, False, False, 0.6, True)   # Stance-Mitte, immer noch keiner
    d.update(1, False, True, 0.1, True)    # wieder Schwung → Touchdown verpasst
    s = d.summary()[1]
    assert s['missed_touchdown'] == 1
    assert s['touchdowns'] == 0
    assert s['stance_gap'] >= 1            # Stance-Mitte ohne Kontakt


# ----- Reset ----------------------------------------------------------


def test_reset_clears_counters():
    d = _d()
    d.update(1, True, False, 0.5, True)
    d.update(1, False, False, 0.5, True)
    d.reset()
    s = d.summary()[1]
    assert s['total_ticks'] == 0
    assert s['stance_gap'] == 0
    assert s['touchdowns'] == 0
