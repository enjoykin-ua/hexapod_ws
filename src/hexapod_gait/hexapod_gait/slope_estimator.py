"""
SlopeEstimator — ROS-freie Hang-Schätzung (Block A5 TF-1).

Langsamer Tiefpass (EMA) auf die IMU-Neigung (roll/pitch). Weil der Körper bei
passivem Terrain-Following dem Boden **folgt** (Bein-Geometrie identisch zur
Flach-Pose, siehe ``terrain_following_pivot_retro.md``), IST die langsame
Neigungs-Komponente der Untergrund (= „der Hang"). Der schnelle Anteil
(Gang-Ripple, beginnender Sturz) bleibt im **Residual** = Ist-Neigung −
Hang-Schätzung sichtbar — das speist die slope-bewusste Kipp-Erkennung.

Unit-testbar ohne ROS (gleiche Trennung wie ``tip_monitor`` /
``balance_controller``).

Designpunkte:
- **Snap-Init:** das erste Sample nach ``reset()`` setzt die Schätzung direkt
  auf die Messung (kein Hochlauf von 0) → kein künstlicher Residual-Transient
  beim (Wieder-)Aktivieren auf einem Hang (z.B. nach dem Aufstehen am Hang).
- **Clamp:** die Schätzung wird auf ±``clamp`` begrenzt, damit ein *langsames*
  Wegkippen die Schätzung nicht beliebig „mitwandern" lässt (sonst würde der
  Residual nie groß → Tip-Erkennung wäre blind für langsames Umkippen).
- **τ → α:** ``alpha = dt / (tau + dt)`` (zeitkonstanten-korrektes EMA, robust
  gegen variable dt). ``tau <= 0`` → ``alpha = 1`` (Filter aus, Schätzung = Ist).
"""


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


class SlopeEstimator:
    """Langsamer Tiefpass auf roll/pitch + Residual. Keine ROS-Dependency."""

    def __init__(self, tau_s, clamp):
        """``tau_s`` = Filter-Zeitkonstante [s], ``clamp`` = Max-|Hang| [rad]."""
        self._tau = max(0.0, float(tau_s))
        self._clamp = abs(float(clamp))
        self._slope_roll = 0.0
        self._slope_pitch = 0.0
        self._initialized = False

    def reset(self):
        """Schätzung auf 0 + Snap-Init scharf (nächstes Sample = Messung)."""
        self._slope_roll = 0.0
        self._slope_pitch = 0.0
        self._initialized = False

    @property
    def slope_roll(self):
        """Aktuelle Hang-Schätzung roll [rad]."""
        return self._slope_roll

    @property
    def slope_pitch(self):
        """Aktuelle Hang-Schätzung pitch [rad]."""
        return self._slope_pitch

    @property
    def tau(self):
        """Filter-Zeitkonstante [s]."""
        return self._tau

    @tau.setter
    def tau(self, value):
        self._tau = max(0.0, float(value))

    @property
    def clamp(self):
        """Betrags-Grenze der Schätzung [rad]."""
        return self._clamp

    @clamp.setter
    def clamp(self, value):
        self._clamp = abs(float(value))
        self._slope_roll = _clamp(self._slope_roll, -self._clamp, self._clamp)
        self._slope_pitch = _clamp(self._slope_pitch, -self._clamp, self._clamp)

    def update(self, roll, pitch, dt):
        """
        Ein Tick: EMA der Neigung. ``dt`` in s. Liefert (slope_roll, slope_pitch).

        Erstes Sample nach ``reset()`` → Snap auf die (geclampte) Messung. Bei
        ``dt <= 0`` (und τ > 0) keine Zeitintegration → Schätzung unverändert.
        """
        if not self._initialized:
            self._slope_roll = _clamp(roll, -self._clamp, self._clamp)
            self._slope_pitch = _clamp(pitch, -self._clamp, self._clamp)
            self._initialized = True
            return self._slope_roll, self._slope_pitch

        if self._tau <= 0.0:
            alpha = 1.0
        elif dt > 0.0:
            alpha = dt / (self._tau + dt)
        else:
            alpha = 0.0

        self._slope_roll = _clamp(
            self._slope_roll + alpha * (roll - self._slope_roll),
            -self._clamp, self._clamp,
        )
        self._slope_pitch = _clamp(
            self._slope_pitch + alpha * (pitch - self._slope_pitch),
            -self._clamp, self._clamp,
        )
        return self._slope_roll, self._slope_pitch

    def residual(self, roll, pitch):
        """Ist-Neigung − Hang-Schätzung [rad] — der schnelle/Kipp-Anteil."""
        return roll - self._slope_roll, pitch - self._slope_pitch
