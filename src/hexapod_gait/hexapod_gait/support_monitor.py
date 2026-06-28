"""
SupportMonitor — ROS-freie Stütz-Verlust-Erkennung (Block A5 Stufe 4 / S4-4).

Erkennt, wenn ein **belasteter Fuß keinen Halt hat** — über eine Kante/einen
Abgrund (der adaptive Touchdown findet bis ``cliff_depth`` keinen Boden) oder
weil ein Stance-Fuß den Kontakt **verloren** hat (Slip). Beides hat dieselbe
Reaktion: **Freeze** (Safe-State, vom gait_node ausgelöst — wie Stufe-1-Tip-CRIT).

Kern-Regel (robust + adaptiv-unabhängig): **ein Stance-Bein, das bis zu einer
Stance-Phase-Grace keinen Kontakt hat, gilt als „Halt verloren".** Die Grace
lässt dem Touchdown/Probe Zeit (deckt den ~13-Tick-JTC-Lag ab); danach ist
„kein Kontakt" ein echter Stütz-Verlust. Die Entprellung (``debounce_ticks``)
muss den ``contact_timeout`` (0.1 s ≈ 5 Ticks, der die fallende Slip-Flanke
verzögert) überschreiten, sonst Fehlalarm.

Schwellen-Wächter mit Entprellung + Latch, unit-testbar ohne ROS (gleiche
Trennung wie ``TipMonitor``/``hexapod_kinematics``). State-Gating (nur WALKING
auswerten) macht der gait_node über ``reset()``.
"""


_LEG_IDS = (1, 2, 3, 4, 5, 6)


class SupportMonitor:
    """Stütz-Verlust-Erkennung (Slip/Kante) → Freeze. Keine ROS-Dependency."""

    def __init__(self, debounce_ticks, min_lost_legs, grace_stance_phase):
        """
        Schwellen mit Entprellung + Latch initialisieren.

        ``debounce_ticks`` Ticks ohne Kontakt (nach Grace) bis „lost" (muss >
        contact_timeout ≈ 5 Ticks sein). ``min_lost_legs`` gleichzeitig verlorene
        Stütz-Beine bis Freeze. ``grace_stance_phase`` ∈ [0,1): unterhalb wird ein
        no-contact-Stance-Bein NICHT gewertet (Touchdown-Fenster).
        """
        self._debounce = max(1, int(debounce_ticks))
        self._min_lost = max(1, int(min_lost_legs))
        self._grace = float(grace_stance_phase)
        self._lost_ticks = {leg_id: 0 for leg_id in _LEG_IDS}
        self._latched = False

    def reset(self):
        """Zähler + Latch zurücksetzen (State-Gating / Recovery)."""
        for leg_id in _LEG_IDS:
            self._lost_ticks[leg_id] = 0
        self._latched = False

    @property
    def freeze_latched(self):
        """Latch-Flag, True ab dem ersten Freeze bis ``reset()``."""
        return self._latched

    def update(self, legs):
        """
        Ein Tick. ``legs``: ``{leg_id: (is_stance, stance_phase, contact)}``.

        Pro Bein, **Leaky-Zähler** (robust gegen intermittierenden Kontakt beim
        Kippen über eine Kante):
        - Schwung **oder** Stance **vor** der Grace (Touchdown-Fenster) → Zähler 0
          (frischer Stance, kein Stütz-Anspruch).
        - Stance **nach** der Grace, **kein** Kontakt → Zähler **+1**.
        - Stance **nach** der Grace, Kontakt → Zähler **−1** (nicht voll zurück;
          gelegentliches Brühren beim Kippen setzt den Verlust nicht zurück, aber
          legitimes Prellen mit ~50 % Kontakt bleibt netto gedeckelt → kein Fehlalarm).

        Ein Bein ist „lost", wenn der Zähler ``debounce_ticks`` erreicht. Erreichen
        ``min_lost_legs`` Beine das gleichzeitig → **Freeze gelatcht** (bis ``reset()``).

        Returns ``(n_lost, freeze_latched)``.
        """
        for leg_id in _LEG_IDS:
            is_stance, stance_phase, contact = legs.get(
                leg_id, (False, 0.0, False),
            )
            if not is_stance or stance_phase < self._grace:
                self._lost_ticks[leg_id] = 0
            elif contact:
                self._lost_ticks[leg_id] = max(0, self._lost_ticks[leg_id] - 1)
            else:
                self._lost_ticks[leg_id] += 1

        n_lost = sum(
            1 for leg_id in _LEG_IDS
            if self._lost_ticks[leg_id] >= self._debounce
        )
        if n_lost >= self._min_lost:
            self._latched = True
        return n_lost, self._latched
