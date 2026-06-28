"""Tests für SupportMonitor (Block A5 S4-4) — Stütz-Verlust → Freeze."""

from hexapod_gait.support_monitor import SupportMonitor


_DEB = 8
_MIN = 1
_GRACE = 0.6


def _mon():
    return SupportMonitor(
        debounce_ticks=_DEB, min_lost_legs=_MIN, grace_stance_phase=_GRACE,
    )


# legs-Tupel = (is_stance, stance_phase, contact).
def _legs(stance=True, sp=0.7, contact=True):
    """Erzeuge alle 6 Beine mit gleichem Zustand."""
    return {i: (stance, sp, contact) for i in range(1, 7)}


def test_supported_never_lost():
    mon = _mon()
    for _ in range(50):
        n, frz = mon.update(_legs(stance=True, sp=0.8, contact=True))
    assert n == 0
    assert frz is False


def test_swing_never_lost():
    mon = _mon()
    for _ in range(50):
        # Schwung-Beine (is_stance False) zählen nie, auch ohne Kontakt
        n, frz = mon.update({i: (False, 0.0, False) for i in range(1, 7)})
    assert n == 0
    assert frz is False


def test_grace_suppresses_early_stance():
    # Stance, kein Kontakt, aber VOR der Grace (sp < 0.6) → nie lost.
    mon = _mon()
    for _ in range(50):
        n, frz = mon.update(_legs(stance=True, sp=0.3, contact=False))
    assert n == 0
    assert frz is False


def test_lost_after_grace_and_debounce():
    # Ein Bein: Stance, kein Kontakt, nach Grace → nach debounce lost → Freeze.
    mon = _mon()
    legs = {1: (True, 0.7, False)}
    legs.update({i: (True, 0.7, True) for i in range(2, 7)})  # Rest gestützt
    frz = False
    for tick in range(_DEB):
        n, frz = mon.update(legs)
        if tick < _DEB - 1:
            assert n == 0          # noch nicht genug Ticks
    assert n == 1
    assert frz is True             # min_lost_legs=1 → Freeze


def test_debounce_exceeds_contact_timeout():
    # < debounce Ticks ohne Kontakt → KEIN Freeze (deckt contact_timeout-Lag).
    mon = _mon()
    legs = {1: (True, 0.7, False)}
    legs.update({i: (True, 0.7, True) for i in range(2, 7)})
    for _ in range(_DEB - 1):
        n, frz = mon.update(legs)
    assert frz is False
    assert _DEB > 5                # Entprellung muss contact_timeout (~5) überschreiten


def test_leaky_alternating_no_freeze():
    # Abwechselnd kein-Kontakt/Kontakt (legitimes Prellen) → Leaky netto ~0 →
    # KEIN Freeze, auch über viele Ticks.
    mon = _mon()
    legs_no = {1: (True, 0.7, False)}
    legs_no.update({i: (True, 0.7, True) for i in range(2, 7)})
    legs_yes = {i: (True, 0.7, True) for i in range(1, 7)}
    frz = False
    for _ in range(40):
        _, frz = mon.update(legs_no)    # +1
        _, frz = mon.update(legs_yes)   # -1
    assert frz is False


def test_leaky_mostly_lost_freezes():
    # Überwiegend kein Kontakt (3:1) trotz gelegentlichem Brühren → Leaky
    # akkumuliert → Freeze (der Kipp-über-Kante-Fall).
    mon = _mon()
    legs_no = {1: (True, 0.7, False)}
    legs_no.update({i: (True, 0.7, True) for i in range(2, 7)})
    legs_yes = {i: (True, 0.7, True) for i in range(1, 7)}
    frz = False
    for _ in range(40):
        for _ in range(3):
            _, frz = mon.update(legs_no)   # +3
        _, frz = mon.update(legs_yes)      # -1 → netto +2
        if frz:
            break
    assert frz is True


def test_min_lost_legs_threshold():
    # min_lost_legs=2 → ein verlorenes Bein reicht NICHT.
    mon = SupportMonitor(debounce_ticks=_DEB, min_lost_legs=2, grace_stance_phase=_GRACE)
    legs = {1: (True, 0.7, False)}
    legs.update({i: (True, 0.7, True) for i in range(2, 7)})
    for _ in range(_DEB + 3):
        n, frz = mon.update(legs)
    assert n == 1
    assert frz is False
    # zweites Bein verliert auch → Freeze
    legs[2] = (True, 0.7, False)
    for _ in range(_DEB):
        n, frz = mon.update(legs)
    assert n == 2
    assert frz is True


def test_latch_holds_until_reset():
    mon = _mon()
    legs_lost = {1: (True, 0.7, False)}
    legs_lost.update({i: (True, 0.7, True) for i in range(2, 7)})
    for _ in range(_DEB):
        mon.update(legs_lost)
    assert mon.freeze_latched is True
    # alle wieder gestützt → Latch bleibt
    _, frz = mon.update({i: (True, 0.7, True) for i in range(1, 7)})
    assert frz is True
    mon.reset()
    assert mon.freeze_latched is False
    _, frz = mon.update({i: (True, 0.7, True) for i in range(1, 7)})
    assert frz is False
