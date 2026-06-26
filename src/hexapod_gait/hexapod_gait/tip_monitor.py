"""
TipMonitor — ROS-freie Kipp-/Sturz-Erkennung (Block A5 Stufe 1).

Schwellen-Wächter mit Entprellung + Latch, unit-testbar ohne ROS (gleiche
Trennung wie ``hexapod_kinematics``). Konsumiert roll/pitch (rad) + Kipprate
(rad/s) und liefert ein Level:

- ``TIP_CRIT``: |Winkel| >= ``angle_crit`` ODER |Kipprate| >= ``rate_crit``,
  über ``debounce_ticks`` gehalten. **Gelatcht** — bleibt CRIT bis ``reset()``
  (entspricht „Freeze bis manuelle Recovery"; gait_node feuert den Freeze nur
  auf der steigenden Flanke).
- ``TIP_WARN``: |Winkel| >= ``angle_warn`` über ``debounce_ticks``.
- ``TIP_NONE``: sonst.

Die Entprellung (N aufeinanderfolgende Ticks) verhindert Fehlalarm durch den
Gang-Ripple. State-Gating (nur STANDING/WALKING auswerten) macht der gait_node
über ``reset()``.
"""

import math


TIP_NONE = 'none'
TIP_WARN = 'warn'
TIP_CRIT = 'crit'


def quat_to_roll_pitch(x, y, z, w):
    """Quaternion -> (roll, pitch) in Radiant (schwerkraft-referenziert)."""
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(sinp)
    return roll, pitch


class TipMonitor:
    """Kipp-Schwellen + Entprellung + Latch. Keine ROS-Dependency."""

    def __init__(self, angle_warn, angle_crit, rate_crit, debounce_ticks):
        """Winkel ``angle_*`` in rad, ``rate_crit`` in rad/s, debounce in Ticks."""
        self._angle_warn = float(angle_warn)
        self._angle_crit = float(angle_crit)
        self._rate_crit = float(rate_crit)
        self._debounce = max(1, int(debounce_ticks))
        self._warn_count = 0
        self._crit_count = 0
        self._latched_crit = False

    def reset(self):
        """Zähler + Latch zurücksetzen (State-Gating / Recovery)."""
        self._warn_count = 0
        self._crit_count = 0
        self._latched_crit = False

    @property
    def crit_latched(self):
        """Latch-Flag, True ab dem ersten CRIT bis ``reset()``."""
        return self._latched_crit

    def update(self, roll, pitch, tilt_rate):
        """
        Ein Tick: roll/pitch (rad) + tilt_rate (rad/s) -> Level.

        ``tilt_rate`` = Betrag der Kipp-Drehrate (z.B. hypot(gyro_x, gyro_y)).
        CRIT ist gelatcht: ist es einmal gesetzt, liefert ``update`` CRIT bis
        ``reset()``.
        """
        if self._latched_crit:
            return TIP_CRIT

        tilt = max(abs(roll), abs(pitch))

        if tilt >= self._angle_crit or abs(tilt_rate) >= self._rate_crit:
            self._crit_count += 1
        else:
            self._crit_count = 0
        if self._crit_count >= self._debounce:
            self._latched_crit = True
            return TIP_CRIT

        if tilt >= self._angle_warn:
            self._warn_count += 1
        else:
            self._warn_count = 0
        if self._warn_count >= self._debounce:
            return TIP_WARN

        return TIP_NONE
