"""
Inverse + Forward Kinematics pro Bein, geschlossene Form.

Bein-Frame-Konvention (siehe geometry.py): Origin am coxa_joint, +X
radial nach außen, +Z oben. Joint-Drehrichtungen aus der URDF
(``leg.xacro``):

- coxa: Achse +Z, positiv = CCW von oben.
- femur: Achse +Y, positiv = Bein nach UNTEN (``Ry(θ)·(1,0,0) =
  (cos θ, 0, -sin θ)``).
- tibia: Achse +Y, positiv = Tibia knickt weiter nach UNTEN relativ
  zur Femur-Richtung.

Knie-Konvention: hardcoded "Knie oben" (siehe Stufe-B-Design-Entscheidung
3 in phase_5_progress.md).

Fehlerbehandlung:
- IKError("foot out of reach") wenn Cosinus-Argument außerhalb [-1, 1]
  (= Foot-Punkt geometrisch nicht erreichbar).
- IKError("joint limit") wenn das ``joint_limits``-Arg übergeben wird
  UND einer der berechneten Joint-Winkel außerhalb des per-Joint-rad-
  Range liegt (Stage 0.6 Frühwarnung — sofortiger Freeze in gait_engine).
- Ohne ``joint_limits``-Arg: lenient (= bisheriges Phase-5-Verhalten,
  Backwards-Compat für Tests).
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from hexapod_kinematics.config import LegConfig


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]

# Numerische Toleranz für Cos-Argument-Clamping. Schützt gegen
# Floating-Point-Drift, bei dem ein cos-Argument minimal außerhalb
# [-1, 1] liegt obwohl der Punkt mathematisch genau erreichbar ist.
_COS_EPS = 1e-9


@dataclass(frozen=True)
class JointLimits:
    """
    Per-Bein-Joint-Limits in rad (URDF-Konvention).

    Stage 0.6: optional an ``leg_ik`` übergeben. Wenn gesetzt, prüft IK
    nach Berechnung ob die drei Joint-Werte innerhalb [lower, upper]
    liegen — sonst IKError("joint limit ...").

    Quelle: URDF ``<limit lower upper>``, in gait_node beim Init aus
    ``/robot_description`` geparst und an gait_engine übergeben.
    """

    coxa_lower: float
    coxa_upper: float
    femur_lower: float
    femur_upper: float
    tibia_lower: float
    tibia_upper: float


class IKError(ValueError):
    """
    Foot-Punkt nicht erreichbar.

    Unterscheidung über die Exception-Message:
    - "out of reach ..." = geometrisch nicht erreichbar (Reichweiten-Kegel)
    - "joint limit ..." = rad-Wert außerhalb URDF-Limits (Stage 0.6)
    """


def leg_ik(
    x: float,
    y: float,
    z: float,
    leg_cfg: LegConfig,
    joint_limits: JointLimits | None = None,
) -> JointAngles:
    """
    Berechne Joint-Winkel für einen Foot-Punkt im Bein-Frame.

    Eingabe: ``(x, y, z)`` = Foot-Link-Center im Bein-Frame des
    angegebenen Beins (siehe ``geometry.base_to_leg_frame`` für die
    Konvertierung aus base_link). Optional ``joint_limits`` für
    Stage-0.6-Joint-Limit-Prüfung.

    Ausgabe: ``(theta_coxa, theta_femur, theta_tibia)`` in Radiant,
    URDF-Konvention (positives ``theta_femur`` zeigt nach unten,
    positives ``theta_tibia`` knickt weiter nach unten).

    Wirft ``IKError``:
    - "out of reach ..." wenn der Punkt geometrisch außerhalb des
      Reichweitenbereichs liegt
    - "joint limit ..." wenn ``joint_limits`` gesetzt ist und ein
      Joint-Wert außerhalb des erlaubten rad-Range liegt
    """
    L_c = leg_cfg.L_coxa
    L_f = leg_cfg.L_femur
    L_t = leg_cfg.L_tibia

    # Schritt 1: Coxa rotiert das Bein in der XY-Ebene zur Foot-Azimut.
    theta_coxa = math.atan2(y, x)

    # Schritt 2: In der durch Coxa rotierten Ebene weiter rechnen.
    # Horizontale Distanz vom Coxa-Joint, dann minus Coxa-Länge gibt
    # die Distanz vom Femur-Joint in der "Bein-Ebene".
    r_total = math.hypot(x, y)
    r = r_total - L_c

    # Schritt 3: Direkte Distanz Femur-Joint -> Foot.
    d = math.hypot(r, z)

    # Schritt 4: Reichweiten-Check. Cosinus-Satz erfordert d im
    # Intervall [|L_f - L_t|, L_f + L_t]. Außerhalb -> IKError.
    cos_tibia_arg = (d * d - L_f * L_f - L_t * L_t) / (2.0 * L_f * L_t)
    if cos_tibia_arg < -1.0 - _COS_EPS or cos_tibia_arg > 1.0 + _COS_EPS:
        raise IKError(
            f'foot ({x:.4f}, {y:.4f}, {z:.4f}) out of reach for leg '
            f'{leg_cfg.name!r}: d={d:.4f}, '
            f'reachable range [{abs(L_f - L_t):.4f}, {L_f + L_t:.4f}]'
        )
    cos_tibia_arg = max(-1.0, min(1.0, cos_tibia_arg))

    # Schritt 5: Tibia-Knickwinkel (Cosinus-Satz).
    # Wertebereich [0, π], positiv im "Knie oben"-Modus.
    theta_tibia = math.acos(cos_tibia_arg)

    # Schritt 6: Femur-Hubwinkel.
    # alpha: Math-Winkel der Linie Femur-Joint -> Foot über die Horizontale,
    # positiv wenn Foot UNTER dem Femur-Joint (z < 0 -> -z > 0).
    # beta: Innenwinkel im Bein-Dreieck am Femur-Joint zwischen Femur
    # und Foot-Linie.
    alpha = math.atan2(-z, r)
    cos_beta_arg = (L_f * L_f + d * d - L_t * L_t) / (2.0 * L_f * d)
    cos_beta_arg = max(-1.0, min(1.0, cos_beta_arg))
    beta = math.acos(cos_beta_arg)

    # URDF-Konvention: positives theta_femur = Bein nach unten. Im
    # "Knie oben"-Modus muss Femur über die Foot-Linie nach oben kippen
    # (math: alpha + beta), das negieren wir = alpha - beta.
    theta_femur = alpha - beta

    # Stage 0.6: optional gegen URDF-Joint-Limits prüfen. Bei Verletzung
    # IKError ("joint limit ...") werfen — gait_engine catched das und
    # triggert sofortigen safety_freeze (N=1, User-Wahl 2026-05-24).
    if joint_limits is not None:
        if not (joint_limits.coxa_lower <= theta_coxa <= joint_limits.coxa_upper):
            raise IKError(
                f'joint limit: leg {leg_cfg.name!r} coxa rad={theta_coxa:.4f} '
                f'outside [{joint_limits.coxa_lower:.4f}, '
                f'{joint_limits.coxa_upper:.4f}] (foot=({x:.4f}, {y:.4f}, {z:.4f}))'
            )
        if not (joint_limits.femur_lower <= theta_femur <= joint_limits.femur_upper):
            raise IKError(
                f'joint limit: leg {leg_cfg.name!r} femur rad={theta_femur:.4f} '
                f'outside [{joint_limits.femur_lower:.4f}, '
                f'{joint_limits.femur_upper:.4f}] (foot=({x:.4f}, {y:.4f}, {z:.4f}))'
            )
        if not (joint_limits.tibia_lower <= theta_tibia <= joint_limits.tibia_upper):
            raise IKError(
                f'joint limit: leg {leg_cfg.name!r} tibia rad={theta_tibia:.4f} '
                f'outside [{joint_limits.tibia_lower:.4f}, '
                f'{joint_limits.tibia_upper:.4f}] (foot=({x:.4f}, {y:.4f}, {z:.4f}))'
            )

    return (theta_coxa, theta_femur, theta_tibia)


def leg_fk(
    theta_coxa: float,
    theta_femur: float,
    theta_tibia: float,
    leg_cfg: LegConfig,
) -> Point3:
    """
    Berechne Foot-Position aus Joint-Winkeln (Forward-Kinematics).

    Inverse Verifikation für ``leg_ik``: ``leg_fk(*leg_ik(p, cfg), cfg)``
    muss ``p`` zurückgeben (bis auf numerische Toleranz).

    Implementiert die URDF-Konvention der ``leg.xacro``-Joint-Origins:
    - coxa rotiert um +Z, dann femur_joint bei (L_coxa, 0, 0).
    - femur rotiert um +Y, dann tibia_joint bei (L_femur, 0, 0) im
      femur-rotierten Frame.
    - tibia rotiert um +Y, dann foot bei (L_tibia, 0, 0) im
      femur+tibia-rotierten Frame.
    """
    L_c = leg_cfg.L_coxa
    L_f = leg_cfg.L_femur
    L_t = leg_cfg.L_tibia

    # Im durch coxa rotierten Frame: tibia_joint und foot liegen alle
    # in der lokalen X-Z-Ebene. Y-Komponente entsteht erst durch die
    # finale Coxa-Rotation am Ende.
    # Femur dreht +X um +Y um theta_femur: (cos_f, 0, -sin_f).
    # Tibia ist relative zu Femur um theta_tibia gedreht; im global
    # rotierten Frame ist die Tibia-Richtung um (theta_femur + theta_tibia)
    # gedreht (parallele Drehachsen).
    cos_f = math.cos(theta_femur)
    sin_f = math.sin(theta_femur)
    cos_ft = math.cos(theta_femur + theta_tibia)
    sin_ft = math.sin(theta_femur + theta_tibia)

    # In der coxa-rotierten X-Z-Ebene: Foot-Position relativ zu coxa_joint.
    # = (L_coxa, 0, 0) + L_femur*(cos_f, 0, -sin_f) + L_tibia*(cos_ft, 0, -sin_ft)
    rx = L_c + L_f * cos_f + L_t * cos_ft
    rz = -L_f * sin_f - L_t * sin_ft

    # Coxa-Rotation um +Z um theta_coxa zurück anwenden.
    cos_c = math.cos(theta_coxa)
    sin_c = math.sin(theta_coxa)
    x = cos_c * rx
    y = sin_c * rx
    z = rz

    return (x, y, z)
