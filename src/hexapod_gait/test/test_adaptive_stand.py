"""
Tests für das terrain-anpassende Stehen (Block A5 S4-7, Adaptive Stand).

Statischer Zwilling von S4-2: im STANDING senkt jedes Bein downward-only von
``body_height`` ab, bis der Taster Kontakt meldet → dort einfrieren; kein
Kontakt bis zum Floor → am Floor halten. Deckt Absenk-Logik, Freeze-bei-Kontakt,
Dip-zu-tief, x,y-Invarianz, AUS=bit-identisch, Reset bei STANDING-Eintritt und
Re-Konform bei body_height-Änderung ab.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_gait.trajectory_gen import stand_pose
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_RADIAL = 0.16
_BODY_H = -0.08
_STEP_H = 0.04
_MAX_DEPTH = 0.02
_RATE = 0.02
_FLOOR = _BODY_H - _MAX_DEPTH


def _urdf_limits():
    return {
        leg.name: JointLimits(
            leg.coxa_limits[0], leg.coxa_limits[1],
            leg.femur_limits[0], leg.femur_limits[1],
            leg.tibia_limits[0], leg.tibia_limits[1],
        )
        for leg in HEXAPOD.legs
    }


def _engine(adaptive=False):
    eng = GaitEngine(
        pattern=_TRIPOD, step_height=_STEP_H, cycle_time=2.0,
        radial_distance=_RADIAL, body_height=_BODY_H, step_length_max=0.03,
        joint_limits=_urdf_limits(),
    )
    eng.stand_conform_max_depth = _MAX_DEPTH
    eng.stand_conform_rate = _RATE
    eng.adaptive_stand_enable = adaptive
    return eng


# ----- white-box auf _adaptive_stand_z -----

def test_no_contact_descends_over_time():
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    eng._foot_contacts[1] = False
    assert eng._adaptive_stand_z(1, 0.0) == pytest.approx(_BODY_H)  # descent 0
    # nach 0.5 s: descent = rate·0.5 = 0.01 → z = body_height − 0.01
    assert eng._adaptive_stand_z(1, 0.5) == pytest.approx(_BODY_H - 0.01)
    assert eng._adaptive_stand_z(1, 0.5) < _BODY_H                  # nur nach unten


def test_contact_during_descent_freezes_at_current_z():
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    eng._foot_contacts[1] = False
    eng._adaptive_stand_z(1, 0.3)                 # senkt (kein Kontakt)
    eng._foot_contacts[1] = True
    z_land = eng._adaptive_stand_z(1, 0.5)        # Kontakt bei aktueller Höhe
    assert z_land == pytest.approx(_BODY_H - _RATE * 0.5)
    assert z_land < _BODY_H
    assert eng._stand_conform_z[1] == pytest.approx(z_land)
    # gehalten für den Rest des Stands (auch wenn Kontakt wieder wegfällt)
    eng._foot_contacts[1] = False
    assert eng._adaptive_stand_z(1, 5.0) == pytest.approx(z_land)


def test_dip_too_deep_holds_floor():
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    eng._foot_contacts[2] = False
    # t groß genug, dass die Descent über den Floor hinausginge → Clamp + Freeze.
    z = eng._adaptive_stand_z(2, 100.0)
    assert z == pytest.approx(_FLOOR)
    assert eng._stand_conform_z[2] == pytest.approx(_FLOOR)
    # danach am Floor gehalten (auch bei kleinerem t)
    assert eng._adaptive_stand_z(2, 0.1) == pytest.approx(_FLOOR)


def test_immediate_contact_anchors_body_height():
    # Erhöhung/flach: Kontakt schon bei body_height (Descent≈0) → hier verankern.
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    eng._foot_contacts[3] = True
    z = eng._adaptive_stand_z(3, 0.0)
    assert z == pytest.approx(_BODY_H)
    assert eng._stand_conform_z[3] == pytest.approx(_BODY_H)


# ----- black-box über _compute_standing_targets / compute_joint_angles -----

def test_disabled_is_bit_identical_stand_pose():
    eng_off = _engine(adaptive=False)
    neutral = stand_pose(_RADIAL, _BODY_H)
    # kein Kontakt → würde bei aktivem Adaptive absenken; bei AUS exakt neutral
    for leg_id in range(1, 7):
        eng_off._foot_contacts[leg_id] = False
    for i in range(50):
        t = i * 0.02
        targets = eng_off.compute_foot_targets(t)
        for leg in HEXAPOD.legs:
            assert targets[leg.name] == pytest.approx(neutral)
    # KEINE State-Mutation (bit-identisch zum starren Verhalten)
    for leg_id in range(1, 7):
        assert eng_off._stand_conform_z[leg_id] is None


def test_xy_unchanged_only_z_adaptive():
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    nx, ny, _ = stand_pose(_RADIAL, _BODY_H)
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = False        # sucht → z weicht ab
    for i in range(50):
        t = i * 0.02
        targets = eng.compute_foot_targets(t)
        for leg in HEXAPOD.legs:
            assert targets[leg.name][0] == pytest.approx(nx)
            assert targets[leg.name][1] == pytest.approx(ny)
            assert targets[leg.name][2] <= _BODY_H + 1e-9   # nur nach unten


def test_standing_entry_resets_conform():
    # Nach dem WALKING wieder in STANDING → frischer Absenk-Vorgang ab t_entry.
    eng = _engine(adaptive=True)
    # künstlich alten Konform-State setzen (als käme er aus einer alten Episode)
    eng._stand_conform_z[1] = -0.099
    eng._t_stand_entry = 0.0
    eng._prev_state = GaitEngine.STATE_WALKING     # letzter Tick war WALKING
    eng._state = GaitEngine.STATE_STANDING         # jetzt STANDING (Eintritt)
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = False
    t = 10.0
    eng.compute_joint_angles(t)                    # löst reset_stand_conform aus
    assert eng._t_stand_entry == pytest.approx(t)  # Anker frisch = Eintritts-t
    assert eng._stand_conform_z[1] is None         # alter Freeze gelöscht


def test_body_height_change_reconforms():
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    eng._foot_contacts[1] = False
    eng._adaptive_stand_z(1, 0.5)                  # senkt auf altem body_height
    # body_height ändert sich (z.B. /cmd_body_height im Stand)
    eng.body_height = -0.10
    targets = eng.compute_foot_targets(5.0)        # triggert Re-Konform
    assert eng._t_stand_entry == pytest.approx(5.0)
    assert eng._stand_conform_bh == pytest.approx(-0.10)
    # neuer Floor = -0.10 − 0.02 = -0.12; frisch ab neuem body_height gesenkt
    assert targets['leg_1'][2] <= -0.10 + 1e-9
    assert targets['leg_1'][2] >= -0.12 - 1e-9


def test_full_floor_stand_no_ikerror():
    # adaptiv AN, alle Kontakte False → jeder Fuß senkt bis Floor. Voller
    # Stand-Zyklus compute_joint_angles darf NICHT IKError werfen (Floor GREEN).
    eng = _engine(adaptive=True)
    eng._prev_state = GaitEngine.STATE_STOPPING    # STANDING-Eintritt erzwingen
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = False
    for i in range(300):
        eng.compute_joint_angles(i * 0.02)


def test_stand_pose_joints_helper_is_nominal():
    # _compute_stand_pose_joints (Ramp-/Reposition-Ziel) muss NOMINAL bleiben,
    # auch bei aktivem Adaptive (t=None-Pfad) — sonst driftet das Ramp-Ziel.
    eng = _engine(adaptive=True)
    eng.reset_stand_conform(0.0)
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = False
    nominal = eng._compute_standing_targets()      # t=None
    neutral = stand_pose(_RADIAL, _BODY_H)
    for leg in HEXAPOD.legs:
        assert nominal[leg.name] == pytest.approx(neutral)
