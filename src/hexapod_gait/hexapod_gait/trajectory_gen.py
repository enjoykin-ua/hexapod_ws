"""
Pure-Python Foot-Trajektorien-Generator.

Liefert für eine gegebene Phase (0..1) im Schwung-Zyklus die Foot-
Position im Bein-Frame. Keine ROS-Dependency, einzeln testbar.

Stufe E: Halbsinus-Schwung in Bein-Frame-Z, optional mit linear
interpoliertem Bein-Frame-X-Vortrieb (in Stufe E typisch 0).
"""

from __future__ import annotations

import math


Point3 = tuple[float, float, float]


def stand_pose(radial_neutral: float, body_height: float) -> Point3:
    """
    Konstante Stand-Pose-Foot-Position im Bein-Frame.

    Bein liegt am Neutral-Punkt: radial_neutral entlang +X (radial nach
    außen), 0 in Y, body_height in Z (typisch negativ → Foot unter
    coxa_joint).
    """
    return (radial_neutral, 0.0, body_height)


def swing_traj(
    phase: float,
    radial_neutral: float,
    body_height: float,
    step_height: float,
    step_length: float = 0.0,
) -> Point3:
    """
    Halbsinus-Schwung-Trajektorie im Bein-Frame.

    phase ∈ [0, 1]: 0=Schwung-Start, 0.5=Apex, 1=Touchdown.
    Foot startet bei (radial_neutral - step_length/2, 0, body_height),
    erreicht Apex bei (radial_neutral, 0, body_height + step_height),
    landet bei (radial_neutral + step_length/2, 0, body_height).

    Stufe E: step_length=0 (default) → reiner vertikaler Halbsinus an
    der Neutral-X-Position. Stufe G fügt step_length > 0 hinzu für
    horizontalen Vortrieb.
    """
    phase = max(0.0, min(1.0, phase))

    # Vertikaler Halbsinus: smooth bei Touchdown (sin'(0) = sin'(π) = 0).
    z = body_height + step_height * math.sin(math.pi * phase)

    # Horizontale lineare Interpolation start_x -> end_x.
    x_start = radial_neutral - step_length / 2.0
    x_end = radial_neutral + step_length / 2.0
    x = x_start + (x_end - x_start) * phase

    return (x, 0.0, z)
