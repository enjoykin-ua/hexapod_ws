"""
Pure-Python Foot-Trajektorien-Generator.

Liefert für eine gegebene Phase (0..1) im Schwung- bzw. Stance-Cycle
die Foot-Position im Bein-Frame. Keine ROS-Dependency, einzeln testbar.

Stufe E: Halbsinus-Schwung in Bein-Frame-Z, optional skalarer
``step_length`` in Bein-Frame-X (in Stufe E typisch 0).

Stufe G: ``step_length`` skalar verallgemeinert auf 2D ``step_vec``
(dx, dy) im Bein-Frame, weil Body-Vortrieb nach Mount-Yaw-Rotation
nicht parallel zur Bein-X-Achse liegt. Neue ``stance_traj``-Funktion
für die Stützphase mit Vortrieb.
"""

from __future__ import annotations

import math


Point3 = tuple[float, float, float]
Vec2 = tuple[float, float]


def stand_pose(radial_neutral: float, body_height: float) -> Point3:
    """
    Konstante Stand-Pose-Foot-Position im Bein-Frame.

    Bein liegt am Neutral-Punkt: ``radial_neutral`` entlang +X (radial
    nach außen), 0 in Y, ``body_height`` in Z (typisch negativ → Foot
    unter coxa_joint).
    """
    return (radial_neutral, 0.0, body_height)


def swing_traj(
    phase: float,
    radial_neutral: float,
    body_height: float,
    step_height: float,
    step_vec: Vec2 = (0.0, 0.0),
) -> Point3:
    """
    Halbsinus-Schwung-Trajektorie im Bein-Frame.

    ``phase`` ∈ [0, 1]: 0 = Schwung-Start, 0.5 = Apex, 1 = Touchdown.

    Foot startet bei ``(radial_neutral - dx/2, -dy/2, body_height)``
    (Touchdown-Position der vorherigen Stance), erreicht Apex bei
    ``(radial_neutral, 0, body_height + step_height)``, landet bei
    ``(radial_neutral + dx/2, +dy/2, body_height)``.

    ``step_vec = (dx, dy)`` ist der **Body-Schritt-Vektor in Bein-
    Frame-Koordinaten** — also bereits durch Mount-Yaw-Rotation
    transformiert. Stufe E: ``(0, 0)`` (kein Vortrieb). Stufe G:
    `rotate_z(-mount_yaw, (v_body_x, v_body_y, 0)) * stance_duration`.
    """
    phase = max(0.0, min(1.0, phase))
    dx, dy = step_vec

    x_start = radial_neutral - dx / 2.0
    y_start = -dy / 2.0
    x_end = radial_neutral + dx / 2.0
    y_end = dy / 2.0

    x = x_start + (x_end - x_start) * phase
    y = y_start + (y_end - y_start) * phase
    # Vertikaler Halbsinus: smooth bei Touchdown (sin'(0) = sin'(π) = 0).
    z = body_height + step_height * math.sin(math.pi * phase)

    return (x, y, z)


def stance_traj(
    phase: float,
    radial_neutral: float,
    body_height: float,
    step_vec: Vec2 = (0.0, 0.0),
) -> Point3:
    """
    Stützphasen-Trajektorie mit Vortrieb im Bein-Frame.

    ``phase`` ∈ [0, 1]: 0 = Stance-Anfang (Foot vorne), 1 = Stance-
    Ende (Foot hinten, gleich Schwung-Start der nächsten Phase).

    Foot bewegt sich linear von ``(radial_neutral + dx/2, +dy/2)``
    nach ``(radial_neutral - dx/2, -dy/2)``, Z konstant auf
    ``body_height``. Geschwindigkeit ist die Inverse der Body-
    Geschwindigkeit (Foot bleibt am Boden, Body bewegt sich
    drüber → Foot relativ zum Body rückwärts).

    Stufe E/F: ``step_vec = (0, 0)`` → Foot stationär am Neutral-
    Punkt während Stance. Stufe G: ``step_vec ≠ 0`` → Foot bewegt
    sich rückwärts.
    """
    phase = max(0.0, min(1.0, phase))
    dx, dy = step_vec

    x_start = radial_neutral + dx / 2.0
    y_start = dy / 2.0
    x_end = radial_neutral - dx / 2.0
    y_end = -dy / 2.0

    x = x_start + (x_end - x_start) * phase
    y = y_start + (y_end - y_start) * phase

    return (x, y, body_height)
