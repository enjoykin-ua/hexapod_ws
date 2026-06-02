# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Quasi-statisches Gelenk-Last-Modell (Phase 13 Finalisierung, Stage A1).

Rechnet pro Pose die **Haltemomente** je Gelenk (coxa/femur/tibia) + die
**Auslastung in % der Servo-Nennleistung**, plus Schwerpunkt (CoG) und
Stabilitäts-Marge. Grundlage fuer das Torque-/Hitze-Viz (RViz-Node) + den
Sweep (CLI).

Modell (CoG-basiert, Weg B):
  1. Roboter-Schwerpunkt aus allen Link-Massen (Koerper+Akku mittig, je Bein
     3 Segment-Schwerpunkte = Segment-Mitten via FK).
  2. Vertikale Stuetzkraefte F_i der Boden-Beine aus statischem Gleichgewicht
     (Summe = M*g, Momentengleichgewicht ueber dem CoG). n>3 = least-norm
     (np.linalg.lstsq), F_i<0 wird geclampt + Instabilitaet geflaggt.
  3. Pro Bein Gelenk-Momente = Summe der Momente aller DISTALEN Kraefte um die
     jeweilige Gelenkachse: Eigengewicht der distalen Segmente (Gravitation -Z)
     + (nur Stuetzbeine) Fuss-Reaktionskraft (+Z) am Fuss.
  4. % = |tau| / Servo-Nennmoment.
  5. Stabilitaets-Marge = vorzeichenbehafteter Abstand CoG_xy -> Rand des
     Stuetz-Polygons (positiv = innen/stabil).

Massen spiegeln ``hexapod_physical_properties.xacro`` (NICHT dort geaendert) und
sind als Parameter ueberschreibbar (``total_mass`` = echtes Wiegegewicht, der
Ueberschuss wird mittig als Koerper-/Akku-Masse addiert).

Pure Python + numpy (Gravitation -Z im Bein-Frame, da Mount nur Yaw ist).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from hexapod_kinematics import HEXAPOD

import numpy as np


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]

# --- Konstanten (Spiegel physical_properties.xacro / Memory servo_models) ---
G = 9.80665                          # m/s^2

_BASE_MASS = 0.5                     # kg, Chassis (base_link)
_SEGMENT_MASS = 0.1167               # kg, je Bein-Segment (coxa/femur/tibia)
_FOOT_MASS = 0.005                   # kg, Fuss-Kugel

# Servo-Nennmoment in N*m (kg*cm * 0.0980665). Konservativ (Nennwert; bei 8.4 V
# real etwas mehr Reserve). Coxa = Diymore 20 kg*cm, Femur/Tibia = Miuzei 35.
_KGCM_TO_NM = 0.0980665
SERVO_NM = {
    'coxa': 20.0 * _KGCM_TO_NM,      # ~1.961 N*m
    'femur': 35.0 * _KGCM_TO_NM,     # ~3.432 N*m
    'tibia': 35.0 * _KGCM_TO_NM,     # ~3.432 N*m
}


@dataclass
class MassModel:
    """Massen-Parametrisierung (Default = URDF; total_mass ueberschreibt)."""

    base_mass: float = _BASE_MASS
    segment_mass: float = _SEGMENT_MASS
    foot_mass: float = _FOOT_MASS
    # Optional: echtes Gesamtgewicht (kg). Der Ueberschuss ggue. der URDF-Summe
    # wird mittig (base_link-Origin) als Koerper-/Akku-Masse addiert.
    total_mass: float | None = None

    def urdf_sum(self) -> float:
        return (
            self.base_mass
            + 18.0 * self.segment_mass
            + 6.0 * self.foot_mass
        )

    def body_center_mass(self) -> float:
        """base_mass + (Akku-/Restmasse, falls total_mass gesetzt), mittig."""
        if self.total_mass is None:
            return self.base_mass
        extra = self.total_mass - self.urdf_sum()
        return self.base_mass + max(0.0, extra)

    def total(self) -> float:
        if self.total_mass is not None:
            return max(self.total_mass, self.urdf_sum())
        return self.urdf_sum()


@dataclass
class JointLoad:
    """Last eines Gelenks."""

    torque_nm: float
    util_pct: float                  # |tau| / Nennmoment * 100
    position_base: Point3            # fuer RViz-Marker (am Gelenk)


@dataclass
class LegLoad:
    coxa: JointLoad
    femur: JointLoad
    tibia: JointLoad
    foot_force_n: float              # vertikale Stuetzkraft (0 wenn Swing)
    is_stance: bool


@dataclass
class RobotLoad:
    legs: dict[str, LegLoad]
    cog_base: Point3
    total_mass: float
    support_polygon: list = field(default_factory=list)   # [(x,y), ...] CCW
    stability_margin_m: float = 0.0  # >0 = CoG innen (stabil)
    stable: bool = True
    stance_feet_base: dict = field(default_factory=dict)  # name -> (x,y,z)


# --------------------------------------------------------------------------
# Geometrie: Gelenk-Positionen
# --------------------------------------------------------------------------
def _leg_joint_positions(
    coxa: float, femur: float, tibia: float, cfg,
) -> tuple[Point3, Point3, Point3, Point3]:
    """(coxa_joint, hip/femur_joint, knee/tibia_joint, foot) im Bein-Frame."""
    l_c, l_f, l_t = cfg.L_coxa, cfg.L_femur, cfg.L_tibia
    cos_c, sin_c = math.cos(coxa), math.sin(coxa)
    cos_f, sin_f = math.cos(femur), math.sin(femur)
    cos_ft, sin_ft = math.cos(femur + tibia), math.sin(femur + tibia)

    hip_rx = l_c
    knee_rx = l_c + l_f * cos_f
    knee_rz = -l_f * sin_f
    foot_rx = knee_rx + l_t * cos_ft
    foot_rz = knee_rz - l_t * sin_ft

    def to_leg(rx: float, rz: float) -> Point3:
        return (cos_c * rx, sin_c * rx, rz)

    return (
        (0.0, 0.0, 0.0),
        to_leg(hip_rx, 0.0),
        to_leg(knee_rx, knee_rz),
        to_leg(foot_rx, foot_rz),
    )


def _to_base(p: Point3, cfg) -> Point3:
    """Bein-Frame -> base_link (mount_yaw um Z + mount_xyz)."""
    x, y, z = p
    yaw = cfg.mount_yaw
    cy, sy = math.cos(yaw), math.sin(yaw)
    mx, my, mz = cfg.mount_xyz
    return (mx + x * cy - y * sy, my + x * sy + y * cy, mz + z)


def _axes(coxa: float) -> tuple[Point3, Point3]:
    """Gelenkachsen im Bein-Frame: (coxa=+Z, femur/tibia=Rz(coxa)*+Y)."""
    return (0.0, 0.0, 1.0), (-math.sin(coxa), math.cos(coxa), 0.0)


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _mid(a: Point3, b: Point3) -> Point3:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)


# --------------------------------------------------------------------------
# Pro-Bein-Gelenkmomente (Bein-Frame; Gravitation -Z, Fuss-Reaktion +Z)
# --------------------------------------------------------------------------
def leg_joint_torques(
    angles: JointAngles, cfg, foot_force_n: float, masses: MassModel,
) -> tuple[float, float, float]:
    """
    Haltemomente (coxa, femur, tibia) in N*m.

    Summe der Momente aller DISTALEN Kraefte um jede Gelenkachse:
    Segment-Eigengewicht (an Segment-Mitte, -Z) + Fuss-Reaktionskraft (+Z,
    nur Stuetzbein) am Fuss.
    """
    coxa_a, femur_a, tibia_a = angles
    p_coxa, p_hip, p_knee, p_foot = _leg_joint_positions(
        coxa_a, femur_a, tibia_a, cfg,
    )
    axis_z, axis_y = _axes(coxa_a)

    m_seg = masses.segment_mass
    w_coxa = (0.0, 0.0, -m_seg * G)
    w_femur = (0.0, 0.0, -m_seg * G)
    w_tibia = (0.0, 0.0, -(m_seg + masses.foot_mass) * G)  # Fuss zur Tibia
    com_coxa = _mid(p_coxa, p_hip)
    com_femur = _mid(p_hip, p_knee)
    com_tibia = _mid(p_knee, p_foot)
    f_react = (0.0, 0.0, foot_force_n)

    # (Kraft, Angriffspunkt) je Last
    loads = [
        (w_coxa, com_coxa),
        (w_femur, com_femur),
        (w_tibia, com_tibia),
        (f_react, p_foot),
    ]

    def torque_about(joint_p: Point3, axis: Point3, distal) -> float:
        total = (0.0, 0.0, 0.0)
        for force, point in distal:
            r = (point[0] - joint_p[0], point[1] - joint_p[1],
                 point[2] - joint_p[2])
            m = _cross(r, force)
            total = (total[0] + m[0], total[1] + m[1], total[2] + m[2])
        return _dot(axis, total)

    # Distal-Sets: coxa = alle; femur = ohne coxa-Segment; tibia = nur tibia+Fuss.
    tau_coxa = torque_about(p_coxa, axis_z, loads)
    tau_femur = torque_about(p_hip, axis_y, loads[1:])
    tau_tibia = torque_about(p_knee, axis_y, loads[2:])
    return tau_coxa, tau_femur, tau_tibia


# --------------------------------------------------------------------------
# Schwerpunkt + Stuetzkraefte + Stabilitaet
# --------------------------------------------------------------------------
def robot_cog_base(
    all_angles: dict[str, JointAngles], masses: MassModel,
) -> tuple[Point3, float]:
    """Roboter-Schwerpunkt (base_link) + Gesamtmasse."""
    msum = masses.body_center_mass()
    acc = [0.0, 0.0, 0.0]   # body+Akku mittig bei (0,0,0) -> kein Beitrag xy/z=0
    m_seg, m_foot = masses.segment_mass, masses.foot_mass
    for cfg in HEXAPOD.legs:
        a = all_angles[cfg.name]
        p_coxa, p_hip, p_knee, p_foot = _leg_joint_positions(*a, cfg)
        for com_leg, m in (
            (_mid(p_coxa, p_hip), m_seg),
            (_mid(p_hip, p_knee), m_seg),
            (_mid(p_knee, p_foot), m_seg),
            (p_foot, m_foot),
        ):
            bx, by, bz = _to_base(com_leg, cfg)
            acc[0] += m * bx
            acc[1] += m * by
            acc[2] += m * bz
            msum += m
    cog = (acc[0] / msum, acc[1] / msum, acc[2] / msum)
    return cog, msum


def _convex_hull(points: list) -> list:
    """Andrew monotone chain (CCW). points = [(x,y), ...]."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _signed_margin(cog_xy: tuple, hull: list) -> float:
    """Min. Abstand CoG->Polygon-Kante; >0 innen (CCW-Hull), <0 außen."""
    if len(hull) < 3:
        return -1.0
    cx, cy = cog_xy
    min_signed = math.inf
    n = len(hull)
    for i in range(n):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        elen = math.hypot(ex, ey)
        if elen < 1e-12:
            continue
        # Linker Normalenabstand (CCW-Hull -> innen = links = positiv).
        # e × (c-a) z-Komponente: positiv wenn c links der gerichteten Kante a→b.
        signed = (ex * (cy - ay) - ey * (cx - ax)) / elen
        min_signed = min(min_signed, signed)
    return min_signed if min_signed != math.inf else -1.0


def support_forces(
    stance_feet: dict[str, Point3], cog_xy: tuple, weight_n: float,
) -> tuple[dict[str, float], bool]:
    """
    Vertikale Stuetzkraefte je Stuetzbein aus statischem Gleichgewicht.

    Loest A*F=b mit A=[[1..],[x..],[y..]], b=[W, W*cx, W*cy] (least-norm via
    lstsq). Negative Kraefte -> auf 0 geclampt + ``stable=False`` (CoG am/ueber
    Polygon-Rand). Bei 0 Stuetzbeinen -> leeres dict.
    """
    names = list(stance_feet.keys())
    if not names:
        return {}, False
    xs = np.array([stance_feet[n][0] for n in names])
    ys = np.array([stance_feet[n][1] for n in names])
    cx, cy = cog_xy
    a_mat = np.vstack([np.ones_like(xs), xs, ys])
    b_vec = np.array([weight_n, weight_n * cx, weight_n * cy])
    f_sol, *_ = np.linalg.lstsq(a_mat, b_vec, rcond=None)
    stable = bool(np.all(f_sol >= -1e-6))
    f_sol = np.clip(f_sol, 0.0, None)
    return {n: float(f_sol[i]) for i, n in enumerate(names)}, stable


# --------------------------------------------------------------------------
# Top-level
# --------------------------------------------------------------------------
def compute_load(
    all_angles: dict[str, JointAngles],
    stance_legs: list[str] | None = None,
    masses: MassModel | None = None,
) -> RobotLoad:
    """
    Vollstaendige Last-Auswertung fuer eine Pose (alle 6 Beine).

    ``stance_legs`` = Beine mit Bodenkontakt (Default: alle 6). Swing-Beine
    haben Fuss-Kraft 0 (nur Eigengewicht-Momente).
    """
    masses = masses or MassModel()
    leg_names = [cfg.name for cfg in HEXAPOD.legs]
    if stance_legs is None:
        stance_legs = list(leg_names)
    cfg_by = {cfg.name: cfg for cfg in HEXAPOD.legs}

    cog, total_mass = robot_cog_base(all_angles, masses)
    weight = total_mass * G

    # Fuss-Positionen (base) der Stuetzbeine
    stance_feet: dict[str, Point3] = {}
    for name in stance_legs:
        a = all_angles[name]
        _, _, _, foot = _leg_joint_positions(*a, cfg_by[name])
        stance_feet[name] = _to_base(foot, cfg_by[name])

    forces, stable = support_forces(stance_feet, (cog[0], cog[1]), weight)
    hull = _convex_hull([(p[0], p[1]) for p in stance_feet.values()])
    margin = _signed_margin((cog[0], cog[1]), hull)

    legs: dict[str, LegLoad] = {}
    for cfg in HEXAPOD.legs:
        a = all_angles[cfg.name]
        f_foot = forces.get(cfg.name, 0.0)
        tc, tf, tt = leg_joint_torques(a, cfg, f_foot, masses)
        p_coxa, p_hip, p_knee, _ = _leg_joint_positions(*a, cfg)
        legs[cfg.name] = LegLoad(
            coxa=JointLoad(tc, abs(tc) / SERVO_NM['coxa'] * 100.0,
                           _to_base(p_coxa, cfg)),
            femur=JointLoad(tf, abs(tf) / SERVO_NM['femur'] * 100.0,
                            _to_base(p_hip, cfg)),
            tibia=JointLoad(tt, abs(tt) / SERVO_NM['tibia'] * 100.0,
                            _to_base(p_knee, cfg)),
            foot_force_n=f_foot,
            is_stance=cfg.name in stance_legs,
        )

    return RobotLoad(
        legs=legs, cog_base=cog, total_mass=total_mass,
        support_polygon=hull, stability_margin_m=margin,
        stable=stable and margin > 0.0,
        stance_feet_base=stance_feet,
    )
