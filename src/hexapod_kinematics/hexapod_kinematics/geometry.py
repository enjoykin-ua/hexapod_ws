"""
Geometric helpers — frame conversions zwischen base_link und Bein-Frame.

Bein-Frame: Origin am ``coxa_joint`` des jeweiligen Beins, gedreht um
``mount_yaw`` (Z-Achse) relativ zu base_link. +X zeigt radial nach außen
vom Body weg, +Z parallel zu base_link-Z (oben).

Pure-Python (math-Modul), kein numpy. Single-Point-Operationen.
"""

from __future__ import annotations

import math

from hexapod_kinematics.config import LegConfig


Point3 = tuple[float, float, float]


def rotate_z(point: Point3, yaw: float) -> Point3:
    """
    Drehe einen 3D-Punkt um die Z-Achse um ``yaw`` (Radiant).

    Z bleibt unverändert. Anwendbar in beide Richtungen — für die
    inverse Rotation einfach ``-yaw`` übergeben.
    """
    x, y, z = point
    c = math.cos(yaw)
    s = math.sin(yaw)
    return (c * x - s * y, s * x + c * y, z)


def rotate_xy(point: Point3, roll: float, pitch: float) -> Point3:
    """
    Drehe einen 3D-Punkt um die Base-X-Achse (roll), dann Base-Y-Achse (pitch).

    Body-Leveling (Block A5 Stufe 2): ``R = Ry(pitch) · Rx(roll)`` — erst roll
    um +X, dann pitch um +Y, beides um den base_link-Ursprung. ``roll``/``pitch``
    in Radiant, REP-103-Konvention (roll um +X, pitch um +Y).

    Für kleine Leveling-Winkel ist die Reihenfolge unkritisch; sie ist hier
    fest als Rx-zuerst definiert, damit der Stellpfad deterministisch ist.
    """
    x, y, z = point
    cr = math.cos(roll)
    sr = math.sin(roll)
    # Rx(roll): X fest, Y/Z drehen.
    y1 = cr * y - sr * z
    z1 = sr * y + cr * z
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    # Ry(pitch): Y fest, X/Z drehen.
    x2 = cp * x + sp * z1
    z2 = -sp * x + cp * z1
    return (x2, y1, z2)


def base_to_leg_frame(point_in_base: Point3, leg_cfg: LegConfig) -> Point3:
    """
    Transformiere einen Punkt aus base_link in den Bein-Frame des Beins.

    Schritt 1: Translation um -mount_xyz (Origin auf coxa_joint legen).
    Schritt 2: Inverse Z-Drehung um mount_yaw.

    Resultat ist der Punkt im Bein-Frame, direkt als IK-Eingabe
    verwendbar.
    """
    mx, my, mz = leg_cfg.mount_xyz
    bx, by, bz = point_in_base
    translated = (bx - mx, by - my, bz - mz)
    return rotate_z(translated, -leg_cfg.mount_yaw)


def leg_to_base_frame(point_in_leg: Point3, leg_cfg: LegConfig) -> Point3:
    """
    Transformiere einen Punkt aus dem Bein-Frame zurück nach base_link.

    Inverse zu ``base_to_leg_frame``: erst um +mount_yaw drehen, dann
    +mount_xyz translieren. Nützlich für Debug-Output (Foot-Position
    in base_link nach FK).
    """
    rotated = rotate_z(point_in_leg, leg_cfg.mount_yaw)
    mx, my, mz = leg_cfg.mount_xyz
    rx, ry, rz = rotated
    return (rx + mx, ry + my, rz + mz)
