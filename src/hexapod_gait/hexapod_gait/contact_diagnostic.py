"""
ContactDiagnostic — ROS-freie Fußkontakt-Verifikation (Block A5 Stufe 4 / S4-1).

Misst pro Bein, ob das Kontaktsignal beim Laufen **rechtzeitig + plausibel** ist —
die Voraussetzung für den adaptiven Touchdown (S4-2). **Reine Messung, keine
Reaktion** (die Reaktion auf Implausibilität ist S4-5). Unit-testbar ohne ROS
(gleiche Trennung wie ``tip_monitor`` / ``slope_estimator``).

Pro Tick bekommt jedes Bein ``(contact, is_swing, local_phase, is_walking)`` und
der Diagnostiker führt Zähler:

- **Touchdown-Latenz:** beim Übergang Swing→Stance (erwarteter Touchdown) zählen,
  wie viele Ticks bis ``contact`` steigt. ``latency_sum/count`` + ``latency_max``
  (in Ticks; bei 50 Hz = 20 ms/Tick). Findet ein Bein in der ganzen Stance keinen
  Kontakt → ``missed_touchdown``.
- **Apex-Fehlkontakt:** ``contact`` im mittleren Schwung (Fuß sollte oben sein) →
  ``apex_false`` (Sensor-Geist / zu großer Fuß).
- **Stance-Aussetzer:** **kein** ``contact`` in der Stance-Mitte (belastetes Bein) →
  ``stance_gap`` (Fuß schwebt / JTC-Lag).
- **Quote:** ``true_ticks / total_ticks`` (nur WALKING).

Die Latenz-/Plausibilitäts-Metriken laufen **nur im WALKING** (nur dort hat die
per-Bein-Phase Bedeutung). ``is_walking=False`` → der Tick wird ignoriert.
"""

from __future__ import annotations


# Fenster (lokale Phase 0..1) für die Plausibilitäts-Checks.
_APEX_LO, _APEX_HI = 0.2, 0.8       # Schwung-Mitte: Fuß sollte oben sein
_STANCE_LO, _STANCE_HI = 0.2, 0.8   # Stance-Mitte: Fuß sollte belastet sein


class _LegStat:
    """Zähler + Flanken-State für ein Bein."""

    __slots__ = (
        'total_ticks', 'true_ticks', 'touchdowns', 'latency_sum',
        'latency_max', 'missed_touchdown', 'apex_false', 'stance_gap',
        '_prev_contact', '_prev_is_swing', '_awaiting', '_ticks_waited',
        '_seen',
    )

    def __init__(self):
        self.total_ticks = 0
        self.true_ticks = 0
        self.touchdowns = 0
        self.latency_sum = 0
        self.latency_max = 0
        self.missed_touchdown = 0
        self.apex_false = 0
        self.stance_gap = 0
        self._prev_contact = False
        self._prev_is_swing = False
        self._awaiting = False     # warten auf Touchdown-Kontakt nach Stance-Start
        self._ticks_waited = 0
        self._seen = False         # schon mindestens ein Tick gesehen


class ContactDiagnostic:
    """Kontakt-Plausibilität/-Latenz pro Bein. Keine ROS-Dependency."""

    def __init__(self, leg_ids=(1, 2, 3, 4, 5, 6)):
        """``leg_ids`` = die zu überwachenden Bein-IDs."""
        self._legs = tuple(leg_ids)
        self._stat = {leg_id: _LegStat() for leg_id in self._legs}

    def reset(self):
        """Alle Zähler + Flanken-State zurücksetzen."""
        for leg_id in self._legs:
            self._stat[leg_id] = _LegStat()

    def update(self, leg_id, contact, is_swing, local_phase, is_walking):
        """
        Ein Tick für ein Bein.

        ``contact`` bool, ``is_swing`` bool, ``local_phase`` ∈ [0,1],
        ``is_walking`` bool.
        Nur im WALKING werden die phasen-basierten Metriken geführt; sonst wird
        der Tick verworfen (und der Flanken-State zurückgesetzt, damit ein
        Touchdown nicht über eine Transition hinweg „weitergezählt" wird).
        """
        st = self._stat.get(leg_id)
        if st is None:
            return
        if not is_walking:
            st._awaiting = False
            st._ticks_waited = 0
            st._prev_contact = contact
            st._prev_is_swing = is_swing
            st._seen = False
            return

        st.total_ticks += 1
        if contact:
            st.true_ticks += 1

        # Swing->Stance-Übergang = erwarteter Touchdown → ab jetzt auf Kontakt warten.
        if st._seen and st._prev_is_swing and not is_swing:
            st._awaiting = True
            st._ticks_waited = 0
        # Stance->Swing-Übergang während noch gewartet wird = nie Kontakt gefunden.
        elif st._seen and not st._prev_is_swing and is_swing and st._awaiting:
            st.missed_touchdown += 1
            st._awaiting = False
            st._ticks_waited = 0

        if st._awaiting:
            # Steigende Flanke des Kontakts → Latenz festhalten.
            if contact and not st._prev_contact:
                st.touchdowns += 1
                st.latency_sum += st._ticks_waited
                st.latency_max = max(st.latency_max, st._ticks_waited)
                st._awaiting = False
                st._ticks_waited = 0
            else:
                st._ticks_waited += 1

        # Plausibilität (nur loggen, nicht reagieren).
        if is_swing and _APEX_LO < local_phase < _APEX_HI and contact:
            st.apex_false += 1
        if (not is_swing) and _STANCE_LO < local_phase < _STANCE_HI and not contact:
            st.stance_gap += 1

        st._prev_contact = contact
        st._prev_is_swing = is_swing
        st._seen = True

    def summary(self):
        """
        Pro Bein ein dict mit den Zählern + abgeleiteten Größen.

        ``latency_avg`` in Ticks (None wenn keine Touchdowns), ``true_quote`` ∈
        [0,1] (None wenn keine Ticks).
        """
        out = {}
        for leg_id in self._legs:
            st = self._stat[leg_id]
            out[leg_id] = {
                'total_ticks': st.total_ticks,
                'true_quote': (
                    st.true_ticks / st.total_ticks
                    if st.total_ticks else None
                ),
                'touchdowns': st.touchdowns,
                'latency_avg': (
                    st.latency_sum / st.touchdowns
                    if st.touchdowns else None
                ),
                'latency_max': st.latency_max,
                'missed_touchdown': st.missed_touchdown,
                'apex_false': st.apex_false,
                'stance_gap': st.stance_gap,
            }
        return out
