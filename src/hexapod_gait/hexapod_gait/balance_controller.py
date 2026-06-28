"""
BalanceController — ROS-freie statische Körper-Leveling-Regelung (Block A5 Stufe 2).

Schmale, austauschbare Regler-Schnittstelle (gleiche Trennung wie ``TipMonitor``
/ ``hexapod_kinematics`` — unit-testbar ohne ROS). Konsumiert die gemessene
Körper-Neigung (roll/pitch, rad) und liefert pro Tick eine **Körper-Rotations-
Korrektur** ``(corr_roll, corr_pitch)`` (rad), die der gait_engine-Stellpfad als
Rotation ``R(corr_roll, corr_pitch)`` auf alle 6 Fuß-Targets anwendet, um den
Körper horizontal zu halten (Soll = 0/0).

v1-Gesetz pro Achse (Master D3): **Totband-PI + Gyro-D + Slew-Rate-Limit + Anti-Windup**.

- ``error = 0 − measured`` (Soll = 0; im TF-2-terrain-Modus speist der gait_node
  pro Achse die passende Größe ein — roll roh, pitch = Residual gegen den Hang —
  sodass „Soll 0" jeweils „roll→0" bzw. „pitch folgt Hang" bedeutet).
- **Totband:** ``|error| < deadband`` → P-Term = 0 und Integrator **eingefroren**
  (gehalten). So jagen die 18 Servos nicht dem IMU-Rauschen / Gang-Ripple um die
  Soll hinterher; die im Integrator gespeicherte Korrektur **hält** die Lage.
- **PI:** ``out = Kp·error + I``, ``I += Ki·error·dt`` (nur außerhalb Totband).
- **Gyro-D (TF-2):** ``d = −Kd·gyro_rate`` — dämpft die Drehrate (Wackeln),
  wirkt **immer** (auch im Winkel-Totband: Wackeln hat kleinen Winkel, aber hohe
  Rate). ``Kd=0`` (Default) → Stufe-2-Verhalten unverändert. ``d`` geht **vor** den
  Slew (Slew bindet die Gesamt-Stellbewegung weiter als Scrub-Schutz). ⚠️ D
  differenziert → rausch-verstärkend (Sim rauschfrei, HW ggf. ``Kd`` senken).
- **Anti-Windup:** Integrator-Beitrag ``I`` auf ``±max_level_angle`` geclampt,
  ``out`` final auf ``±max_level_angle`` geclampt.
- **Slew:** ``|Δout/dt| ≤ slew_max`` (sanfte Stellbewegung → schützt vor
  Fuß-Scrub-Spikes; Risiko 3).

Vorzeichen: ``corr`` kontert die gemessene Neigung (``error = −measured``) — die
konkrete Dreh-Richtung im Base-Frame setzt der Engine-Stellpfad (``rotate_xy``)
und wird in Sim/Round-Trip-Test verifiziert.

Austauschbar: hinter dieselbe ``update(roll, pitch, dt)``-Schnittstelle passt als
zweite Implementierung das Dual-Tiefpass/Dual-Fenster-Schema (Master D3).
"""

from __future__ import annotations


def _clamp(value: float, limit: float) -> float:
    """Symmetrischer Clamp auf ``[-limit, limit]``."""
    if value > limit:
        return limit
    if value < -limit:
        return -limit
    return value


class BalanceController:
    """Totband-PI + Slew + Anti-Windup pro Achse. Keine ROS-Dependency."""

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
        Alle Winkel in rad, ``slew_max`` in rad/s, ``ki`` in 1/s, ``kd`` in s.

        ``deadband`` = Halb-Breite des Totbands (rad). ``max_level_angle`` =
        harter Ausgangs-/Integrator-Clamp (rad); muss offline als
        envelope-sicher bewiesen sein (Stufe-2-Checkliste 2.5). ``kd`` =
        Gyro-Dämpfungs-Gain (TF-2); Default 0 → Stufe-2-Verhalten.
        """
        self._kp = float(kp)
        self._ki = float(ki)
        self._kd = float(kd)
        self._deadband = float(deadband)
        self._slew_max = float(slew_max)
        self._max = float(max_level_angle)
        # Per-Achse: Integrator-Beitrag (rad, Ki bereits eingerechnet),
        # zuletzt emittierte Korrektur (rad), zuletzt gesehener error (rad).
        self._i_roll = 0.0
        self._i_pitch = 0.0
        self._out_roll = 0.0
        self._out_pitch = 0.0
        self._err_roll = 0.0
        self._err_pitch = 0.0

    def reset(self) -> None:
        """Integrator + Ausgang + error-Cache nullen (State-Gating / Recovery)."""
        self._i_roll = 0.0
        self._i_pitch = 0.0
        self._out_roll = 0.0
        self._out_pitch = 0.0
        self._err_roll = 0.0
        self._err_pitch = 0.0

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
        Live-Tuning (rqt_reconfigure): nur übergebene Gains überschreiben.

        Bei kleinerem ``max_level_angle`` wird der gehaltene Integrator-Beitrag
        sofort nachgeclampt, damit ``out`` nicht über dem neuen Limit klebt.
        """
        if kp is not None:
            self._kp = float(kp)
        if ki is not None:
            self._ki = float(ki)
        if kd is not None:
            self._kd = float(kd)
        if deadband is not None:
            self._deadband = float(deadband)
        if slew_max is not None:
            self._slew_max = float(slew_max)
        if max_level_angle is not None:
            self._max = float(max_level_angle)
            self._i_roll = _clamp(self._i_roll, self._max)
            self._i_pitch = _clamp(self._i_pitch, self._max)

    @property
    def correction(self) -> tuple[float, float]:
        """Zuletzt emittierte Korrektur ``(corr_roll, corr_pitch)`` (rad)."""
        return (self._out_roll, self._out_pitch)

    @property
    def converged(self) -> bool:
        """
        Konvergenz-Flag: beide Achsen zuletzt im Totband (|error| < deadband).

        Genutzt für den Stufe-2-Startup-Grace-Gate (Tip während aktiver
        Leveling-Konvergenz unterdrücken). Nach ``reset()`` True (error=0).
        """
        return (
            abs(self._err_roll) < self._deadband
            and abs(self._err_pitch) < self._deadband
        )

    def update(
        self, roll: float, pitch: float, dt: float,
        gyro_roll: float = 0.0, gyro_pitch: float = 0.0,
    ) -> tuple[float, float]:
        """
        Ein Tick: gemessene roll/pitch (rad) + dt (s) → Korrektur (rad).

        ``gyro_roll/pitch`` = signierte Achsen-Drehraten (rad/s) für den Gyro-D-
        Term (TF-2); Default 0 → reines Stufe-2-PI. ``dt <= 0`` (erster Tick /
        Zeitsprung): Ausgang unverändert halten (Slew-Step 0), kein Integrieren.
        """
        self._out_roll, self._i_roll, self._err_roll = self._update_axis(
            roll, dt, self._i_roll, self._out_roll, gyro_roll,
        )
        self._out_pitch, self._i_pitch, self._err_pitch = self._update_axis(
            pitch, dt, self._i_pitch, self._out_pitch, gyro_pitch,
        )
        return (self._out_roll, self._out_pitch)

    def _update_axis(
        self, measured: float, dt: float, integ: float, prev_out: float,
        gyro_rate: float = 0.0,
    ) -> tuple[float, float, float]:
        """Eine Achse: Totband-PI + Gyro-D + Anti-Windup + Slew. Returns (out, I, error)."""
        error = -measured  # Soll = 0 (gait_node speist roll roh / pitch-Residual ein)

        if abs(error) < self._deadband:
            # Totband: P aus, Integrator einfrieren (hält die Korrektur).
            p_term = 0.0
        else:
            p_term = self._kp * error
            if dt > 0.0:
                integ += self._ki * error * dt
                integ = _clamp(integ, self._max)  # Anti-Windup

        # Gyro-D (TF-2): dämpft die Drehrate, wirkt IMMER (auch im Totband —
        # Wackeln = kleiner Winkel + hohe Rate). Kd=0 → kein Beitrag.
        d_term = -self._kd * gyro_rate

        raw = _clamp(p_term + integ + d_term, self._max)

        # Slew-Rate-Limit: |Δout| ≤ slew_max·dt.
        max_step = self._slew_max * dt if dt > 0.0 else 0.0
        delta = raw - prev_out
        if delta > max_step:
            out = prev_out + max_step
        elif delta < -max_step:
            out = prev_out - max_step
        else:
            out = raw
        return out, integ, error
