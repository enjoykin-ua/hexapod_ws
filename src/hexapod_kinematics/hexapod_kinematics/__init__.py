"""hexapod_kinematics — pure-Python IK/FK library for the hexapod legs."""

from hexapod_kinematics.config import HEXAPOD, HexapodConfig, LegConfig
from hexapod_kinematics.geometry import (
    base_to_leg_frame,
    leg_to_base_frame,
    rotate_z,
)
from hexapod_kinematics.leg_ik import IKError, leg_fk, leg_ik

__all__ = [
    'HEXAPOD',
    'HexapodConfig',
    'IKError',
    'LegConfig',
    'base_to_leg_frame',
    'leg_fk',
    'leg_ik',
    'leg_to_base_frame',
    'rotate_z',
]
