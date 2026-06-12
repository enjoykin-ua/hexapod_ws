"""
Tests fuer Phase 13 Finalisierung Stage A1 — joint_load.py (Torque-Modell).

Deckt §2.1 des Plans `project_finalization/A1_torque_viz_plan.md` ab:
- Hand-nachgerechnete Einfach-Pose (Jᵀ·F)
- Symmetrischer 6er-Stand → gleiche Stuetzkraefte (CoG-Modell ⊇ Even-Split)
- Coxa ≈ 0 unter Vertikallast
- Schwingbein → Eigengewicht-Moment ≠ 0
- Stabilitaet (CoG innen/außen)
- total_mass-Override skaliert
- Sweep-Sanity (Fuss weiter draußen → mehr Tibia-Moment)
"""

from hexapod_gait.joint_load import (
    compute_load,
    G,
    leg_joint_torques,
    MassModel,
    SERVO_NM,
)
from hexapod_kinematics import HEXAPOD, leg_ik
import pytest


_LEG1 = HEXAPOD.by_name('leg_1')


def _stand_angles(radial: float = 0.145, bh: float = -0.10) -> dict:
    """Symmetrische Stand-Pose: jedes Bein Fuss bei (radial, 0, bh)."""
    a = leg_ik(radial, 0.0, bh, _LEG1)
    return {cfg.name: a for cfg in HEXAPOD.legs}


def test_hand_verified_torque_zero_mass():
    """Femur=Tibia=0, masselos, Fuss-Kraft F → τ = -L·F (Hand-Rechnung)."""
    f = 10.0
    massless = MassModel(base_mass=0.0, segment_mass=0.0, foot_mass=0.0)
    tc, tf, tt = leg_joint_torques((0.0, 0.0, 0.0), _LEG1, f, massless)
    assert tc == pytest.approx(0.0, abs=1e-9)
    assert tt == pytest.approx(-_LEG1.L_tibia * f, abs=1e-9)
    assert tf == pytest.approx(-(_LEG1.L_femur + _LEG1.L_tibia) * f, abs=1e-9)


def test_coxa_zero_under_vertical_load():
    """Coxa-Moment ist 0 fuer reine Vertikallast (Achse +Z)."""
    angles = _stand_angles()
    load = compute_load(angles)
    for leg in load.legs.values():
        assert leg.coxa.torque_nm == pytest.approx(0.0, abs=1e-9)


def test_symmetric_stand_equal_support_forces():
    """Symmetrischer 6er-Stand → alle Stuetzkraefte ≈ M*g/6 (B ⊇ Even-Split)."""
    angles = _stand_angles()
    load = compute_load(angles)
    expected = load.total_mass * G / 6.0
    for leg in load.legs.values():
        assert leg.is_stance
        assert leg.foot_force_n == pytest.approx(expected, rel=1e-6)
    total = sum(leg.foot_force_n for leg in load.legs.values())
    assert total == pytest.approx(load.total_mass * G, rel=1e-9)  # ΣF = M*g


def test_symmetric_stand_is_stable():
    """Schwerpunkt mittig im 6er-Polygon → stabil, Marge > 0."""
    load = compute_load(_stand_angles())
    assert load.stable
    assert load.stability_margin_m > 0.0


def test_degenerate_two_leg_stance_unstable():
    """Nur 2 Stuetzbeine → Polygon entartet → instabil."""
    load = compute_load(_stand_angles(), stance_legs=['leg_1', 'leg_4'])
    assert not load.stable


def test_swing_leg_selfweight_nonzero_coxa_zero():
    """Angehobenes Bein (Fuss-Kraft 0): Femur/Tibia ≠ 0 (Eigengewicht), Coxa ≈ 0."""
    angles = _stand_angles()
    # leg_1 als Swing markieren (nicht in stance_legs)
    stance = [n for n in (c.name for c in HEXAPOD.legs) if n != 'leg_1']
    load = compute_load(angles, stance_legs=stance)
    leg1 = load.legs['leg_1']
    assert leg1.foot_force_n == pytest.approx(0.0, abs=1e-9)
    assert abs(leg1.femur.torque_nm) > 1e-4
    assert abs(leg1.tibia.torque_nm) > 1e-4
    assert leg1.coxa.torque_nm == pytest.approx(0.0, abs=1e-9)


def test_total_mass_override_scales():
    """total_mass=3.0 → groessere Last als Default-URDF-Summe (~2.63 kg)."""
    angles = _stand_angles()
    default = compute_load(angles)
    heavy = compute_load(angles, masses=MassModel(total_mass=3.0))
    assert heavy.total_mass == pytest.approx(3.0, rel=1e-6)
    assert default.total_mass < 3.0
    leg = 'leg_1'
    assert heavy.legs[leg].foot_force_n > default.legs[leg].foot_force_n
    assert heavy.legs[leg].tibia.torque_nm < default.legs[leg].tibia.torque_nm
    # (Tibia-Moment negativ → "größere Last" = betragsmäßig größer)
    assert abs(heavy.legs[leg].tibia.torque_nm) > abs(
        default.legs[leg].tibia.torque_nm)


def test_foot_further_out_higher_tibia_torque():
    """Sweep-Sanity: größeres radial → höheres Tibia-Moment (Hebelarm)."""
    near = compute_load(_stand_angles(radial=0.14, bh=-0.10))
    far = compute_load(_stand_angles(radial=0.18, bh=-0.10))
    assert abs(far.legs['leg_1'].tibia.torque_nm) > abs(
        near.legs['leg_1'].tibia.torque_nm)


def test_util_pct_matches_rating():
    """% Auslastung = |τ| / Nennmoment * 100."""
    load = compute_load(_stand_angles(), masses=MassModel(total_mass=3.0))
    leg = load.legs['leg_1']
    assert leg.tibia.util_pct == pytest.approx(
        abs(leg.tibia.torque_nm) / SERVO_NM['tibia'] * 100.0, rel=1e-9)
