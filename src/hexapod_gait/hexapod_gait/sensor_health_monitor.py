"""
SensorHealthMonitor — ROS-freie Fußkontakt-Sensor-Plausibilität (Block A5 S4-5).

Erkennt einen **defekten Fußkontakt-Sensor**, der das Verhalten sonst
**verschlechtern** würde (Umbrella §2.D: „Taster = Optimierung, nie
load-bearing" — ein Sensor-Fault darf degradieren, aber nicht stoppen oder
in die Irre führen). Zwei Fehlerbilder mit der **Gait-Phase als
Plausibilitäts-Anker** (geometrische Grundwahrheit):

- **stuck-on** (klemmt auf „Kontakt"): ein gesunder Fuß ist im **Schwung-Apex**
  in der Luft → Kontakt dort ist physikalisch unmöglich. **ABER:** der gz-Sim-
  Kontakt + ``contact_timeout`` + Fußkugel-Clearance meldet auch bei gesunden
  Beinen **lückenhaften** Kontakt im Apex (S4-1/S4-2-Artefakt). Daher der
  robuste Diskriminator: nicht „irgendein Apex-Kontakt", sondern **ein ganzer
  Schwung-Pass durch das Apex-Band mit Kontakt an JEDEM Tick (lückenlos)**, und
  das über ``apex_fault_cycles`` **aufeinanderfolgende** Pässe. Ein klemmender
  Sensor (immer True) liefert lückenlose Pässe; ein gesundes Bein hat pro Pass
  mindestens eine Kontakt-Lücke → der Zähler resettet → trippt nie (auch der
  Walk-Start-Transient = ein einzelner Pass wird so gefiltert). stuck-on
  korrumpiert beide Vorstufen: er friert den adaptiven Touchdown (S4-2) per
  Phantom-Kontakt zu früh ein UND täuscht S4-4 „immer gestützt" vor (→ kein
  Freeze über einer Kante, gefährlich).
- **dead/stuck-off** (klemmt auf „kein Kontakt" / tot): **überhaupt kein
  Kontakt** über ``dead_ticks`` Ticks beim Laufen = toter Sensor. Resettet bei
  JEDEM Kontakt → ein stuck-on-Sensor (immer True) wird so **nie** fälschlich
  als dead geflaggt (sonst überschriebe das den ``stuck_on``-Grund). Weniger
  gefährlich (Bein bekommt nur keine Optimierung → Open-Loop), kann aber in
  S4-4 einen Dauer-**Fehl-Freeze** auslösen.

**Reaktion (im gait_node, nicht hier): ignorieren + warnen.** Ein geflaggtes
Bein wird latched **maskiert** — S4-2 adaptiv-aus (nominaler Bogen, Open-Loop)
und aus der S4-4-Stütz-Zählung ausgeschlossen. Kein Freeze (Stopp-Schutz
bleibt der Stufe-1-Tip + die gesunden Beine).

Schwellen-Wächter mit Pass-Logik + Latch, unit-testbar ohne ROS (gleiche
Trennung wie ``TipMonitor`` / ``SupportMonitor`` / ``hexapod_kinematics``).
State-Gating (nur WALKING auswerten) macht der gait_node über ``reset()``.
"""


_LEG_IDS = (1, 2, 3, 4, 5, 6)

REASON_STUCK_ON = 'stuck_on'
REASON_DEAD = 'dead'

# Ein Apex-Pass muss mindestens so viele Ticks im Band spannen, um zu zählen —
# filtert degenerate Rand-Clips (z.B. ein einzelner Tick am Band-Rand bei grober
# Phasen-Quantisierung). Ein echter Schwung-Pass durch 0.3–0.7 spannt bei 50 Hz
# ~20 Ticks, liegt also klar darüber.
_MIN_APEX_PASS_TICKS = 3


class _LegHealth:
    """Pass-/Flanken-State + Flag für ein Bein (latched bis ``reset()``)."""

    __slots__ = ('apex_pass_active', 'apex_pass_full', 'apex_pass_ticks',
                 'apex_full_passes', 'ticks_since_contact', 'faulty', 'reason')

    def __init__(self):
        self.apex_pass_active = False   # gerade im Apex-Band (ein Schwung-Pass)
        self.apex_pass_full = True      # bisher lückenlos Kontakt in diesem Pass
        self.apex_pass_ticks = 0        # Apex-Ticks im aktuellen Pass
        self.apex_full_passes = 0       # aufeinanderfolgende lückenlose Pässe
        self.ticks_since_contact = 0    # Ticks seit letztem Kontakt (dead)
        self.faulty = False
        self.reason = None


class SensorHealthMonitor:
    """Sensor-Plausibilität pro Bein (stuck-on / dead). Keine ROS-Dependency."""

    def __init__(self, apex_lo, apex_hi, apex_fault_cycles, dead_ticks):
        """
        Schwellen mit Pass-Logik + Latch initialisieren.

        ``apex_lo``/``apex_hi`` ∈ [0,1]: das Schwung-Apex-Band (lokale Phase),
        in dem ``contact`` unmöglich ist (default 0.3/0.7 — past dem
        ``contact_timeout``-Nachhall am Schwung-Anfang). ``apex_fault_cycles``:
        Anzahl **aufeinanderfolgender** Schwung-Pässe mit lückenlosem Apex-
        Kontakt bis stuck-on-Flag (default 3). ``dead_ticks``: Ticks ohne
        Touchdown bis dead-Flag (der Node rechnet ``sensor_dead_cycles ·
        cycle_time · tick_rate`` → cycle_time-unabhängig).
        """
        self._apex_lo = float(apex_lo)
        self._apex_hi = float(apex_hi)
        self._apex_fault_cycles = max(1, int(apex_fault_cycles))
        self._dead_ticks = max(1, int(dead_ticks))
        self._leg = {leg_id: _LegHealth() for leg_id in _LEG_IDS}

    def reset(self):
        """Zähler + Flags zurücksetzen (State-Gating / Recovery)."""
        for leg_id in _LEG_IDS:
            self._leg[leg_id] = _LegHealth()

    @property
    def faulty_legs(self):
        """Menge der aktuell geflaggten Bein-IDs (latched bis ``reset()``)."""
        return {leg_id for leg_id in _LEG_IDS if self._leg[leg_id].faulty}

    def update(self, legs):
        """
        Ein Tick. ``legs``: ``{leg_id: (is_swing, local_phase, contact)}``.

        Pro Bein:
        - **stuck-on (Pass-Logik):** im Apex-Band (Schwung, ``apex_lo ≤ phase ≤
          apex_hi``) wird ein „Pass" geöffnet; jeder Tick **ohne** Kontakt setzt
          ``apex_pass_full=False``. Beim Verlassen des Bandes wird der Pass
          geschlossen: war er lückenlos (und ≥ ``_MIN_APEX_PASS_TICKS`` lang) →
          ``apex_full_passes += 1``, sonst → ``= 0`` (Reset). ``apex_full_passes
          ≥ apex_fault_cycles`` → Fault ``stuck_on``. Robust gegen das gz-Apex-
          Artefakt: ein gesundes Bein hat pro Pass eine Lücke → resettet → nie.
        - **dead:** jeder ``contact`` → ``ticks_since_contact = 0``; sonst
          ``+= 1``. ``ticks_since_contact ≥ dead_ticks`` → Fault ``dead``. (Reset
          bei JEDEM Kontakt → stuck-on (immer True) erscheint nie als dead.)

        Faulty ist **latched**: ist ein Bein einmal geflaggt, bleibt es bis
        ``reset()`` geflaggt (keine Auto-Recovery in v1 — die WARN-Logs bleiben
        trackbar). Returns ``{leg_id: (faulty, reason)}``.
        """
        for leg_id in _LEG_IDS:
            h = self._leg[leg_id]
            is_swing, phase, contact = legs.get(leg_id, (False, 0.0, False))
            if h.faulty:
                continue  # Latched — kein Wieder-Einschalten bis reset()

            # --- stuck-on: lückenloser Apex-Pass über N Pässe in Folge ---
            in_apex = is_swing and self._apex_lo <= phase <= self._apex_hi
            if in_apex:
                if not h.apex_pass_active:
                    h.apex_pass_active = True
                    h.apex_pass_full = True
                    h.apex_pass_ticks = 0
                h.apex_pass_ticks += 1
                if not contact:
                    h.apex_pass_full = False
            elif h.apex_pass_active:
                # Band verlassen → Pass schließen + bewerten.
                h.apex_pass_active = False
                if h.apex_pass_full and h.apex_pass_ticks >= _MIN_APEX_PASS_TICKS:
                    h.apex_full_passes += 1
                else:
                    h.apex_full_passes = 0
            if h.apex_full_passes >= self._apex_fault_cycles:
                h.faulty = True
                h.reason = REASON_STUCK_ON

            # --- dead/stuck-off: überhaupt kein Kontakt über dead_ticks ---
            if contact:
                h.ticks_since_contact = 0
            else:
                h.ticks_since_contact += 1
            if h.ticks_since_contact >= self._dead_ticks:
                h.faulty = True
                h.reason = REASON_DEAD

        return {
            leg_id: (self._leg[leg_id].faulty, self._leg[leg_id].reason)
            for leg_id in _LEG_IDS
        }
