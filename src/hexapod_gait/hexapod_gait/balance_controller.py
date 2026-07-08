"""
BalanceController v2 — ROS-freie Körper-Leveling-Regelung (Block A5 Stufe 2 + 7).

Schmale, austauschbare Regler-Schnittstelle (gleiche Trennung wie ``TipMonitor``
/ ``hexapod_kinematics`` — unit-testbar ohne ROS). Konsumiert die gemessene
Körper-Neigung (roll/pitch, rad) und liefert pro Tick eine **Körper-Rotations-
Korrektur** ``(corr_roll, corr_pitch)`` (rad), die der gait_engine-Stellpfad als
Rotation ``R(corr_roll, corr_pitch)`` auf alle 6 Fuß-Targets anwendet (Soll 0/0).

**Stufe 7 (v2)** — pro Achse (roll/pitch) getrennt konfigurierbar, mit
**Zwei-Fenster-Hysterese** und optionalem **Dual-Tiefpass**:

- **Zwei-Fenster-Hysterese (E1):** nicht-regelnd → **start** bei ``|m_slow| ≥ outer``;
  regelnd → **stop** (P=0, Integrator eingefroren) bei ``|m_fast| < inner``. Dazwischen
  hält der Zustand → **kein Rand-Chatter** (der Stufe-2-Grenzzyklus). Bei
  ``inner == outer`` reduziert sich das exakt auf das alte Single-Totband
  (regelnd ⇔ ``|x| ≥ inner``).
- **Dual-Tiefpass (E2, nur wenn ``apply_filter`` und ``tau_slow > 0``):** fast/slow-EMA
  auf den Eingang. Der **slow**-Filter entscheidet „resume" (ignoriert Transiente),
  der **fast**-Filter „stop" (schnelles Settle). ``apply_filter=False`` (Eingang ist
  bereits ein Slope-Residual → Slope-Schätzer ist die langsame Stufe) ⇒ **kein**
  zweiter Filter (``m_fast = m_slow = measured``). ``tau_fast=0`` ⇒ ``m_fast = measured``.
- **Snap-Init (B):** erstes Sample nach ``reset()`` setzt die Filter direkt auf die
  Messung (kein Hochlauf von 0 → kein verzögertes Engagement am gekippten Roboter).
- **Stellgröße-Eingang (D):** ``error = -m_fast`` (geglättet wenn gefiltert, sonst
  == ``measured``).
- **Gyro-D (E6):** ``d = -kd·gyro_rate`` — dämpft die Drehrate (Wackeln), wirkt
  **immer** (auch im „nicht-regelnd"-Hold; Wackeln = kleiner Winkel + hohe Rate),
  auf der **rohen** Gyro-Rate. ⚠️ D rausch-verstärkend → auf HW ``kd`` konservativ.
- **Anti-Windup + Clamp:** Integrator + Ausgang auf ``±max_level_angle`` (gemeinsam,
  state-abhängig 10/4° vom gait_node via ``set_gains`` gesetzt). Muss offline
  envelope-sicher bewiesen sein (Stufe-2-Checkliste 2.5).
- **Slew:** ``|Δout/dt| ≤ slew_max`` (Scrub-Schutz; deckelt auch die Lurch-Rate).

Vorzeichen: ``corr`` kontert die gemessene Neigung (``error = -measured``) — die
konkrete Dreh-Richtung im Base-Frame setzt der Engine-Stellpfad (``rotate_xy``)
und wird in Sim/Round-Trip-Test verifiziert.

**Backward-Compat:** der alte Konstruktor ``(kp, ki, deadband, slew_max,
max_level_angle, kd=0)`` erzeugt beide Achsen symmetrisch mit ``inner == outer ==
deadband`` und ``tau_fast == tau_slow == 0`` ⇒ **exakt** das Stufe-2-Verhalten
(``resume ≥ D``, ``stop < D`` ⇒ regelnd iff ``|x| ≥ D``; ``error = -measured``).
Per-Achse-Feintuning über ``set_axis_gains``.
"""

from __future__ import annotations


def _clamp(value: float, limit: float) -> float:
    """Symmetrischer Clamp auf ``[-limit, limit]``."""
    if value > limit:
        return limit
    if value < -limit:
        return -limit
    return value


class _Axis:
    """Per-Achse Gains + Regler-/Filter-Zustand (roll bzw. pitch)."""

    def __init__(
        self, kp: float, ki: float, kd: float, inner: float, outer: float,
        slew_max: float, tau_fast: float, tau_slow: float,
    ):
        # Gains
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.inner = float(inner)
        self.outer = float(outer)
        self.slew_max = float(slew_max)
        self.tau_fast = float(tau_fast)
        self.tau_slow = float(tau_slow)
        # State
        self.integ = 0.0        # Integrator-Beitrag (rad, Ki eingerechnet)
        self.out = 0.0          # zuletzt emittierte Korrektur (rad)
        self.m_fast = 0.0       # fast-EMA des Eingangs
        self.m_slow = 0.0       # slow-EMA des Eingangs
        self.regulating = False  # Hysterese-Latch
        self.initialized = False  # Snap-Init-Flag

    def reset(self) -> None:
        """Integrator + Ausgang + Filter + Latch nullen (State-Gating/Recovery)."""
        self.integ = 0.0
        self.out = 0.0
        self.m_fast = 0.0
        self.m_slow = 0.0
        self.regulating = False
        self.initialized = False


class BalanceController:
    """Per-Achse Totband-PI + Hysterese + Dual-Tiefpass + Gyro-D. Keine ROS-Dependency."""

    def __init__(
        self,
        kp: float,
        ki: float,
        deadband: float,
        slew_max: float,
        max_level_angle: float,
        kd: float = 0.0,
    ):
        """
        Back-Compat-Konstruktor (beide Achsen symmetrisch).

        ``inner == outer == deadband``, Filter aus (``tau_fast == tau_slow ==
        0``). Alle Winkel in rad, ``slew_max`` in rad/s, ``ki`` in 1/s, ``kd``
        in s. ``max_level_angle`` = gemeinsamer harter Clamp (rad). Per-Achse-
        Werte via ``set_axis_gains``.
        """
        self._max = float(max_level_angle)
        self._roll = _Axis(kp, ki, kd, deadband, deadband, slew_max, 0.0, 0.0)
        self._pitch = _Axis(kp, ki, kd, deadband, deadband, slew_max, 0.0, 0.0)

    def _axis(self, name: str) -> _Axis:
        return self._roll if name == 'roll' else self._pitch

    def reset(self) -> None:
        """Beide Achsen zurücksetzen (State-Gating / Recovery)."""
        self._roll.reset()
        self._pitch.reset()

    def set_gains(
        self,
        kp: float | None = None,
        ki: float | None = None,
        deadband: float | None = None,
        slew_max: float | None = None,
        max_level_angle: float | None = None,
        kd: float | None = None,
    ) -> None:
        """
        Back-Compat „beide Achsen"-Setter (+ gemeinsamer ``max_level_angle``).

        ``deadband`` setzt ``inner = outer = deadband`` auf beiden Achsen. Bei
        kleinerem ``max_level_angle`` werden die gehaltenen Integratoren sofort
        nachgeclampt.
        """
        for ax in (self._roll, self._pitch):
            if kp is not None:
                ax.kp = float(kp)
            if ki is not None:
                ax.ki = float(ki)
            if kd is not None:
                ax.kd = float(kd)
            if deadband is not None:
                ax.inner = float(deadband)
                ax.outer = float(deadband)
            if slew_max is not None:
                ax.slew_max = float(slew_max)
        if max_level_angle is not None:
            self._max = float(max_level_angle)
            self._roll.integ = _clamp(self._roll.integ, self._max)
            self._pitch.integ = _clamp(self._pitch.integ, self._max)

    def set_axis_gains(
        self,
        axis: str,
        kp: float | None = None,
        ki: float | None = None,
        kd: float | None = None,
        inner: float | None = None,
        outer: float | None = None,
        slew_max: float | None = None,
        tau_fast: float | None = None,
        tau_slow: float | None = None,
    ) -> None:
        """Per-Achse-Setter (``axis`` = ``'roll'`` | ``'pitch'``). Nur Übergebenes."""
        ax = self._axis(axis)
        if kp is not None:
            ax.kp = float(kp)
        if ki is not None:
            ax.ki = float(ki)
        if kd is not None:
            ax.kd = float(kd)
        if inner is not None:
            ax.inner = float(inner)
        if outer is not None:
            ax.outer = float(outer)
        if slew_max is not None:
            ax.slew_max = float(slew_max)
        if tau_fast is not None:
            ax.tau_fast = float(tau_fast)
        if tau_slow is not None:
            ax.tau_slow = float(tau_slow)

    @property
    def correction(self) -> tuple[float, float]:
        """Zuletzt emittierte Korrektur ``(corr_roll, corr_pitch)`` (rad)."""
        return (self._roll.out, self._pitch.out)

    @property
    def converged(self) -> bool:
        """
        Konvergenz-Flag: **beide Achsen nicht-regelnd** (eingeschwungen/Hold).

        Genutzt für den Startup-Grace-Gate (Tip während aktiver Leveling-Konvergenz
        unterdrücken). Nach ``reset()`` True. ⚠️ Kann True sein, während der Körper
        zwischen ``inner`` und ``outer`` (bis ~``outer``) schief steht.
        """
        return (not self._roll.regulating) and (not self._pitch.regulating)

    def update(
        self, roll: float, pitch: float, dt: float,
        gyro_roll: float = 0.0, gyro_pitch: float = 0.0,
        filter_roll: bool = True, filter_pitch: bool = True,
    ) -> tuple[float, float]:
        """
        Ein Tick: gemessene roll/pitch (rad) + dt (s) → Korrektur (rad).

        ``gyro_roll/pitch`` = signierte Achsen-Drehraten (rad/s) für Gyro-D.
        ``filter_roll/pitch`` = **True** wenn der Eingang **roh** ist (Dual-TP
        anwenden), **False** wenn er bereits slope-gefiltert ist (Residual →
        kein zweiter Filter). gait_node setzt ``filter_roll=True`` immer,
        ``filter_pitch = (mode != 'terrain')``. ``dt <= 0`` → Slew-Step 0.
        """
        out_roll = self._update_axis(
            self._roll, roll, dt, gyro_roll, filter_roll,
        )
        out_pitch = self._update_axis(
            self._pitch, pitch, dt, gyro_pitch, filter_pitch,
        )
        return (out_roll, out_pitch)

    def _update_axis(
        self, ax: _Axis, measured: float, dt: float,
        gyro_rate: float, apply_filter: bool,
    ) -> float:
        """Eine Achse: Snap-Init + Dual-TP + Hysterese + PI + Gyro-D + Slew → out."""
        # (B) Snap-Init: erstes Sample nach reset → Filter direkt auf die Messung.
        if not ax.initialized:
            ax.m_fast = measured
            ax.m_slow = measured
            ax.initialized = True

        # (1) Dual-Tiefpass NUR wenn Eingang roh UND Filter an. Sonst m = measured.
        #     terrain-pitch (apply_filter=False) → m=measured=Residual (kein Doppelfilter).
        if apply_filter and ax.tau_slow > 0.0 and dt > 0.0:
            a_fast = dt / (ax.tau_fast + dt) if ax.tau_fast > 0.0 else 1.0
            a_slow = dt / (ax.tau_slow + dt)
            ax.m_fast = ax.m_fast + a_fast * (measured - ax.m_fast)
            ax.m_slow = ax.m_slow + a_slow * (measured - ax.m_slow)
        else:
            ax.m_fast = measured
            ax.m_slow = measured

        # (2) Hysterese-Latch: resume via slow (≥ outer), stop via fast (< inner).
        #     inner == outer → Single-Schwelle (regelnd iff |x| ≥ inner) == Stufe 2.
        if not ax.regulating:
            if abs(ax.m_slow) >= ax.outer:
                ax.regulating = True
        else:
            if abs(ax.m_fast) < ax.inner:
                ax.regulating = False

        # (3) Regelung — Soll 0, Stellgröße-Eingang = m_fast.
        error = -ax.m_fast
        if not ax.regulating:
            p_term = 0.0  # Integrator eingefroren (HÄLT die Korrektur)
        else:
            p_term = ax.kp * error
            if dt > 0.0:
                ax.integ = _clamp(ax.integ + ax.ki * error * dt, self._max)

        # Gyro-D (E6): immer aktiv (auch im Hold), auf roher Rate.
        d_term = -ax.kd * gyro_rate
        raw = _clamp(p_term + ax.integ + d_term, self._max)

        # (4) Slew-Rate-Limit.
        max_step = ax.slew_max * dt if dt > 0.0 else 0.0
        delta = raw - ax.out
        if delta > max_step:
            ax.out = ax.out + max_step
        elif delta < -max_step:
            ax.out = ax.out - max_step
        else:
            ax.out = raw
        return ax.out
