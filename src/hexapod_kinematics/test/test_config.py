"""
Cross-check: hexapod_kinematics.config matches the URDF/xacro source.

Bricht, sobald jemand einen Wert in hexapod_physical_properties.xacro oder
ein Mountpunkt-Formular in hexapod.urdf.xacro ändert, ohne config.py zu
aktualisieren. Einziger Wächter gegen Config-Drift (Stufe-A-Design-
Entscheidung 2: "abschreiben + Cross-Check-Test").
"""

import math
from pathlib import Path
import re

from hexapod_kinematics.config import HEXAPOD
import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PROPERTIES_XACRO = (
    WORKSPACE_ROOT
    / 'src'
    / 'hexapod_description'
    / 'urdf'
    / 'hexapod_physical_properties.xacro'
)


def _parse_xacro_properties(path: Path) -> dict:
    """
    Parse <xacro:property name="X" value="Y"/> with literal numeric Y.

    Properties whose value contains expressions (z.B. ${pi/4}) werden
    übersprungen — die werden erst in der Mountpunkt-Verifikation
    rekonstruiert.
    """
    text = path.read_text()
    pattern = (
        r'<xacro:property\s+name="([^"]+)"\s+'
        r'value="\s*(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*"\s*/>'
    )
    return {m.group(1): float(m.group(2)) for m in re.finditer(pattern, text)}


@pytest.fixture(scope='module')
def xacro_props():
    if not PROPERTIES_XACRO.exists():
        pytest.fail(
            'xacro source not found at '
            f'{PROPERTIES_XACRO} — workspace layout broken?'
        )
    return _parse_xacro_properties(PROPERTIES_XACRO)


def test_six_legs():
    assert len(HEXAPOD.legs) == 6


def test_leg_names_canonical():
    expected = ['leg_1', 'leg_2', 'leg_3', 'leg_4', 'leg_5', 'leg_6']
    assert [leg.name for leg in HEXAPOD.legs] == expected


def test_leg_lengths_match_xacro(xacro_props):
    leg = HEXAPOD.legs[0]
    assert leg.L_coxa == xacro_props['coxa_length']
    assert leg.L_femur == xacro_props['femur_length']
    assert leg.L_tibia == xacro_props['tibia_length']
    assert leg.foot_radius == xacro_props['foot_radius']


def test_joint_limits_match_xacro(xacro_props):
    leg = HEXAPOD.legs[0]
    assert leg.coxa_limits == (
        xacro_props['coxa_lower'],
        xacro_props['coxa_upper'],
    )
    assert leg.femur_limits == (
        xacro_props['femur_lower'],
        xacro_props['femur_upper'],
    )
    assert leg.tibia_limits == (
        xacro_props['tibia_lower'],
        xacro_props['tibia_upper'],
    )


def test_all_legs_mechanically_identical():
    """
    Alle 6 Beine teilen sich dasselbe <xacro:macro name="leg">.

    Falls dieser Test bricht, wurde an einem einzelnen Bein etwas
    individualisiert — dann muss entschieden werden, ob das auch im URDF
    so sein soll.
    """
    first = HEXAPOD.legs[0]
    for leg in HEXAPOD.legs[1:]:
        assert leg.L_coxa == first.L_coxa
        assert leg.L_femur == first.L_femur
        assert leg.L_tibia == first.L_tibia
        assert leg.coxa_limits == first.coxa_limits
        assert leg.femur_limits == first.femur_limits
        assert leg.tibia_limits == first.tibia_limits
        assert leg.foot_radius == first.foot_radius


def test_mount_positions_match_xacro_formulas(xacro_props):
    """
    Mountpunkte aus HEXAPOD gegen die Formeln in hexapod.urdf.xacro.

    Falls die Beinanordnung (z.B. Bein-Indizes oder yaw-Pattern) im
    URDF geändert wird, muss diese Test-Erwartung mitgezogen werden —
    der Test ist somit auch Doku, welche Anordnung kanonisch ist.
    """
    bl = xacro_props['body_length']
    bw = xacro_props['body_width']
    bwm = xacro_props['body_width_middle']
    z = xacro_props['leg_mount_z']

    expected = [
        ('leg_1', (bl / 2.0,  -bw / 2.0,  z), -math.pi / 4.0),
        ('leg_2', (0.0,        -bwm / 2.0, z), -math.pi / 2.0),
        ('leg_3', (-bl / 2.0, -bw / 2.0,  z), -3.0 * math.pi / 4.0),
        ('leg_4', (-bl / 2.0,  bw / 2.0,  z),  3.0 * math.pi / 4.0),
        ('leg_5', (0.0,         bwm / 2.0, z),  math.pi / 2.0),
        ('leg_6', (bl / 2.0,   bw / 2.0,  z),  math.pi / 4.0),
    ]

    for (exp_name, exp_xyz, exp_yaw), leg in zip(expected, HEXAPOD.legs):
        assert leg.name == exp_name
        assert leg.mount_xyz == pytest.approx(exp_xyz, abs=1e-12)
        assert leg.mount_yaw == pytest.approx(exp_yaw, abs=1e-12)


def test_by_name_lookup():
    leg = HEXAPOD.by_name('leg_3')
    assert leg.name == 'leg_3'
    with pytest.raises(KeyError):
        HEXAPOD.by_name('leg_99')
