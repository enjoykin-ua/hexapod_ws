# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
Regressions-Tests für das Massen-Modell (Block I Phase 10, FL-T7).

Der Bein-Umbau hat Femur und Tibia unterschiedlich schwer gemacht (0.102 /
0.118 kg), das Modell rechnete aber weiter mit einem **Einheits-Segment** von
0.1167 kg für alle 18 — ein Stand von vor dem Umbau. Für die Show-CoG-Rechnung
ist das relevant (die angehobenen Vorderbeine ziehen den Schwerpunkt nach vorn),
für Torque-Analyse und Leveling-Envelope soll sich aber **nichts** ändern.

Deshalb sind die per-Segment-Massen **optional**: ohne sie muss das Modell
bit-identisch zum Vorzustand rechnen. Genau das pinnen diese Tests — plus die
Konstanten gegen die URDF, damit sie nicht auseinanderlaufen.
"""

from pathlib import Path
import re

from hexapod_gait.joint_load import (
    MassModel,
    REAL_FEMUR_MASS,
    REAL_TIBIA_MASS,
    robot_cog_base,
)
from hexapod_kinematics import HEXAPOD

import pytest


_XACRO = (Path(__file__).resolve().parents[2]
          / 'hexapod_description/urdf/hexapod_physical_properties.xacro')


def _xacro_property(name: str) -> float:
    if not _XACRO.is_file():
        pytest.skip(f'{_XACRO} nicht vorhanden (Paket ohne Workspace)')
    text = _XACRO.read_text()
    m = re.search(rf'name="{name}"\s+value="([-0-9.eE]+)"', text)
    assert m, f'{name} nicht in {_XACRO.name} gefunden'
    return float(m.group(1))


def test_default_model_unchanged():
    """Ohne per-Segment-Massen bleibt alles wie vor Phase 10 (Bestand-Schutz)."""
    m = MassModel()
    assert m.segment_masses() == (0.1167, 0.1167, 0.1167)
    assert m.urdf_sum() == pytest.approx(0.5 + 18 * 0.1167 + 6 * 0.005)


def test_default_cog_unchanged():
    """Der Schwerpunkt einer Referenz-Pose ist ohne die neuen Felder identisch."""
    angles = {leg.name: (0.0, -0.5, 1.2) for leg in HEXAPOD.legs}
    cog_old, m_old = robot_cog_base(angles, MassModel())
    # Explizit auf segment_mass gesetzt = derselbe Zustand wie ohne Argumente.
    cog_new, m_new = robot_cog_base(
        angles, MassModel(femur_mass=0.1167, tibia_mass=0.1167))
    assert m_new == pytest.approx(m_old)
    for a, b in zip(cog_old, cog_new):
        assert a == pytest.approx(b, abs=1e-15)


def test_real_masses_match_urdf():
    """Die Konstanten müssen mit der URDF übereinstimmen (Drift-Schutz)."""
    assert REAL_FEMUR_MASS == pytest.approx(_xacro_property('femur_mass'))
    assert REAL_TIBIA_MASS == pytest.approx(_xacro_property('tibia_mass'))
    # Die Coxa blieb beim Umbau unverändert und ist weiter das Einheits-Segment.
    assert MassModel().segment_mass == pytest.approx(
        _xacro_property('coxa_mass'))


def test_real_masses_are_lighter_than_the_old_assumption():
    """
    Das alte Einheits-Segment überschätzt die Beinmassen.

    Die Show-Rechnung ist mit ihm also konservativ, nicht optimistisch.
    """
    real = MassModel(femur_mass=REAL_FEMUR_MASS, tibia_mass=REAL_TIBIA_MASS)
    assert real.urdf_sum() < MassModel().urdf_sum()
    assert real.urdf_sum() == pytest.approx(
        0.5 + 6 * (0.1167 + REAL_FEMUR_MASS + REAL_TIBIA_MASS) + 6 * 0.005)
