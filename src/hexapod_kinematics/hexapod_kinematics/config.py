"""
Hexapod geometric configuration — single source of truth for the IK math.

Values mirror ``hexapod_description/urdf/hexapod_physical_properties.xacro``
and the leg mount formulas in ``hexapod.urdf.xacro``. The cross-check test
``test/test_config.py`` parses the xacro source and fails on drift.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LegConfig:
    """
    Geometry of a single hexapod leg.

    All distances in meters, all angles in radians (REP-103, SI).
    Mount frame origin = ``coxa_joint`` position in ``base_link``.
    Bein-frame +X = outward (away from body), +Z = up.
    """

    name: str
    mount_xyz: tuple[float, float, float]
    mount_yaw: float
    L_coxa: float
    L_femur: float
    L_tibia: float
    coxa_limits: tuple[float, float]
    femur_limits: tuple[float, float]
    tibia_limits: tuple[float, float]
    foot_radius: float


@dataclass(frozen=True)
class HexapodConfig:
    """Container for all 6 leg configurations."""

    legs: tuple[LegConfig, ...]

    def by_name(self, name: str) -> LegConfig:
        for leg in self.legs:
            if leg.name == name:
                return leg
        raise KeyError(f'unknown leg name: {name!r}')


# Mechanical constants (mirrored from hexapod_physical_properties.xacro).
_L_COXA = 0.0436
_L_FEMUR = 0.060
_L_TIBIA = 0.134
_FOOT_RADIUS = 0.008

_COXA_LIMITS = (-1.57, 1.57)
_FEMUR_LIMITS = (-1.57, 1.57)
# Tibia-Beuge +2.50 (143°) = strikt-symmetrisches Mechanik-Max, von allen 6
# Servos puls-seitig erreichbar (leg_5-bound). Bein-Umbau (leg_changes, kuerzere
# Tibia): Streck-Anschlag -1.00 → -0.28 verengt (neuer enger Ueberstreck-Anschlag,
# handover.md §1). Konsistent zur URDF (Property via test_config.py; die 6 per-Bein-
# Werte je urdf/ros2_control via test_per_leg_limits). Memory two_joint_limit_sources.
_TIBIA_LIMITS = (-0.28, 2.50)

# Body dimensions for mountpoint computation (mirrored from xacro).
_BODY_LENGTH = 0.175
_BODY_WIDTH = 0.130
_BODY_WIDTH_MIDDLE = 0.170
_LEG_MOUNT_Z = 0.0

# Mount layout: arrangement around the body, mirrors hexapod.urdf.xacro
# §11.3 of 00_conventions.md. Beine 1-3: rechts (mount_y < 0).
# Beine 4-6: links (mount_y > 0). Mechanik aller 6 Beine identisch.
_LEG_DEFINITIONS: tuple[tuple[str, float, float, float], ...] = (
    ('leg_1',  _BODY_LENGTH / 2.0,  -_BODY_WIDTH / 2.0,        -math.pi / 4.0),
    ('leg_2',  0.0,                 -_BODY_WIDTH_MIDDLE / 2.0, -math.pi / 2.0),
    ('leg_3', -_BODY_LENGTH / 2.0,  -_BODY_WIDTH / 2.0,        -3.0 * math.pi / 4.0),
    ('leg_4', -_BODY_LENGTH / 2.0,   _BODY_WIDTH / 2.0,         3.0 * math.pi / 4.0),
    ('leg_5',  0.0,                  _BODY_WIDTH_MIDDLE / 2.0,  math.pi / 2.0),
    ('leg_6',  _BODY_LENGTH / 2.0,   _BODY_WIDTH / 2.0,         math.pi / 4.0),
)


HEXAPOD = HexapodConfig(
    legs=tuple(
        LegConfig(
            name=name,
            mount_xyz=(mx, my, _LEG_MOUNT_Z),
            mount_yaw=myaw,
            L_coxa=_L_COXA,
            L_femur=_L_FEMUR,
            L_tibia=_L_TIBIA,
            coxa_limits=_COXA_LIMITS,
            femur_limits=_FEMUR_LIMITS,
            tibia_limits=_TIBIA_LIMITS,
            foot_radius=_FOOT_RADIUS,
        )
        for name, mx, my, myaw in _LEG_DEFINITIONS
    )
)
