"""
Tests für den adaptiven Touchdown (Block A5 S4-2, Option A).

Option A = downward-only, an ``body_height`` verankert, lag-tolerantes Stance-Gate:
nominaler Schwung+Stance bleiben, das Adaptive senkt den Fuß NUR unter
``body_height`` und erst nach ``probe_start``, wenn bis dahin kein Kontakt kam.
Deckt die Senk-Logik, die **Körper-Höhen-Stabilität auf flachem Boden** (Anti-
Drift-Regression), x,y-Invarianz, Fallback=nominal und die Envelope-Tiefe ab.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_gait.trajectory_gen import stance_traj, swing_traj
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_RADIAL = 0.16
_BODY_H = -0.08
_STEP_H = 0.04
_PROBE_START = 0.35
_SEARCH_END = 0.6
_MAX_DEPTH = 0.02
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
    eng.touchdown_probe_start_stance_phase = _PROBE_START
    eng.touchdown_search_end_stance_phase = _SEARCH_END
    eng.touchdown_max_extra_depth = _MAX_DEPTH
    eng.adaptive_touchdown_enable = adaptive
    return eng


def _cp_stance(eng, stance_phase):
    """cycle_phase für eine gegebene Stance-Phase."""
    sd = eng.pattern.swing_duty
    return sd + stance_phase * (1.0 - sd)


# ----- Senk-Logik (white-box auf _adaptive_touchdown_z) -----

def test_swing_is_nominal_and_resets_state():
    eng = _engine()
    eng._touchdown_z[1] = -0.05      # künstlich setzen, Reset prüfen
    eng._td_searched[1] = True
    z = eng._adaptive_touchdown_z(1, 0.5 * eng.pattern.swing_duty, z_nom=-0.045)
    assert z == pytest.approx(-0.045)        # nominaler Bogen durchgereicht
    assert eng._touchdown_z[1] is None
    assert eng._td_searched[1] is False


def test_stance_pregate_holds_body_height_without_probe():
    eng = _engine()
    eng._foot_contacts[1] = False
    z = eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.2), z_nom=_BODY_H)
    assert z == pytest.approx(_BODY_H)       # kein Tieferreichen vor dem Gate
    assert eng._touchdown_z[1] is None        # nicht eingefroren
    assert eng._td_searched[1] is False       # nicht gesucht


def test_stance_pregate_contact_anchors_body_height():
    # Flacher Boden: Kontakt auf Nominalhöhe vor dem Gate → bei body_height
    # verankern (NICHT tiefer) → kein Körper-Sinken.
    eng = _engine()
    eng._foot_contacts[1] = True
    z = eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.2), z_nom=_BODY_H)
    assert z == pytest.approx(_BODY_H)
    assert eng._touchdown_z[1] == pytest.approx(_BODY_H)


def test_probe_descends_linearly_below_body_height():
    eng = _engine()
    eng._foot_contacts[1] = False
    # Gate-Start: z == body_height (wp=0)
    assert eng._adaptive_touchdown_z(1, _cp_stance(eng, _PROBE_START), _BODY_H) \
        == pytest.approx(_BODY_H)
    eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.1), _BODY_H)   # Reset (pre-gate)
    # Fenster-Mitte: linear zwischen body_height und floor
    mid = 0.5 * (_PROBE_START + _SEARCH_END)
    z_mid = eng._adaptive_touchdown_z(1, _cp_stance(eng, mid), _BODY_H)
    assert z_mid == pytest.approx(0.5 * (_BODY_H + _FLOOR))
    assert z_mid < _BODY_H                                        # nur nach unten
    # Fenster-Ende: floor
    assert eng._adaptive_touchdown_z(1, _cp_stance(eng, _SEARCH_END), _BODY_H) \
        == pytest.approx(_FLOOR)


def test_contact_during_probe_freezes_below_body_height():
    eng = _engine()
    eng._foot_contacts[1] = False
    eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.1), _BODY_H)   # pre-gate
    eng._foot_contacts[1] = True
    z_land = eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.5), _BODY_H)
    assert z_land < _BODY_H                                       # tiefer = Terrain
    assert eng._touchdown_z[1] == pytest.approx(z_land)
    # gehalten für den Rest der Stance
    eng._foot_contacts[1] = False
    assert eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.9), _BODY_H) \
        == pytest.approx(z_land)


def test_past_window_floor_only_if_searched():
    eng = _engine()
    eng._foot_contacts[1] = False
    eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.1), _BODY_H)   # Reset
    eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.5), _BODY_H)   # suchen
    assert eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.9), _BODY_H) \
        == pytest.approx(_FLOOR)
    # frisches Bein, nie im Fenster (Walk-Start mid-Stance) → body_height
    eng2 = _engine()
    assert eng2._adaptive_touchdown_z(2, _cp_stance(eng2, 0.9), _BODY_H) \
        == pytest.approx(_BODY_H)


# ----- Verhalten in _compute_walking_targets (black-box) -----

def _drive_to_walking(eng, t=0.0):
    eng.set_command(0.05, 0.0, 0.0, t)
    assert eng.state == GaitEngine.STATE_WALKING


def test_flat_ground_no_body_drift():
    # DIE Anti-Drift-Regression (Sim-Befund S4-2): mit Kontakt auf flachem Boden
    # darf KEIN Stance-Fuß unter body_height kommandiert werden → Körper bleibt
    # auf Nominalhöhe verankert (kein Absacken/Aufschwingen).
    eng = _engine(adaptive=True)
    _drive_to_walking(eng)
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = True          # Boden überall auf body_height
    for i in range(200):
        t = i * 0.02
        states = eng.leg_gait_states(t)
        targets = eng.compute_foot_targets(t)
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            z = targets[leg.name][2]
            assert z >= _BODY_H - 1e-9             # nie unter body_height
            is_swing, _ = states[leg_id]
            if not is_swing:
                assert z == pytest.approx(_BODY_H)  # Stance exakt nominal


def test_xy_unchanged_only_z_adaptive():
    eng_nom = _engine(adaptive=False)
    eng_ad = _engine(adaptive=True)
    _drive_to_walking(eng_nom)
    _drive_to_walking(eng_ad)
    for leg_id in range(1, 7):
        eng_ad._foot_contacts[leg_id] = False       # sucht (z weicht ab)
    for i in range(200):
        t = i * 0.02
        nom = eng_nom.compute_foot_targets(t)
        ad = eng_ad.compute_foot_targets(t)
        for leg in HEXAPOD.legs:
            assert ad[leg.name][0] == pytest.approx(nom[leg.name][0])
            assert ad[leg.name][1] == pytest.approx(nom[leg.name][1])


def test_fallback_disabled_is_exact_nominal_trajectory():
    eng = _engine(adaptive=False)
    _drive_to_walking(eng)
    t = 0.37
    targets = eng.compute_foot_targets(t)
    for leg in HEXAPOD.legs:
        leg_id = int(leg.name.split('_')[1])
        offset = eng.pattern.phase_offset_per_leg[leg_id]
        cycle_phase = ((t / eng.cycle_time) + offset) % 1.0
        step_vec = eng._compute_step_vec_leg(leg, eng._v_body, eng._omega)
        if cycle_phase < eng.pattern.swing_duty:
            exp = swing_traj(
                cycle_phase / eng.pattern.swing_duty, _RADIAL, _BODY_H,
                _STEP_H, step_vec,
            )
        else:
            stp = (
                (cycle_phase - eng.pattern.swing_duty)
                / (1.0 - eng.pattern.swing_duty)
            )
            exp = stance_traj(stp, _RADIAL, _BODY_H, step_vec)
        assert targets[leg.name] == pytest.approx(exp)


def test_deepest_touchdown_stays_in_limits_no_ikerror():
    # adaptiv AN, alle Kontakte False → jeder Fuß probt bis zum Floor.
    # Voller Cycle compute_joint_angles darf NICHT IKError werfen (Floor GREEN).
    eng = _engine(adaptive=True)
    _drive_to_walking(eng)
    for leg_id in range(1, 7):
        eng._foot_contacts[leg_id] = False
    for i in range(200):
        eng.compute_joint_angles(i * 0.02)


def test_cliff_probe_depth_overrides_floor():
    # S4-4: cliff_probe_depth > max_extra_depth → tieferer Probe-Floor.
    # Floor via past-window-Pfad prüfen (erst Fenster durchlaufen → _td_searched).
    eng = _engine()
    eng._foot_contacts[1] = False
    eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.5), _BODY_H)   # im Fenster suchen
    z_no_cliff = eng._adaptive_touchdown_z(1, _cp_stance(eng, 0.9), _BODY_H)
    assert z_no_cliff == pytest.approx(_FLOOR)                    # body_height − 0.02

    eng2 = _engine()
    eng2._foot_contacts[2] = False
    eng2.cliff_probe_depth = 0.03                                 # > max_extra_depth 0.02
    eng2._adaptive_touchdown_z(2, _cp_stance(eng2, 0.5), _BODY_H)
    z_cliff = eng2._adaptive_touchdown_z(2, _cp_stance(eng2, 0.9), _BODY_H)
    assert z_cliff == pytest.approx(_BODY_H - 0.03)              # tieferer Floor


def test_walking_entry_preanchors_stance_legs():
    # Beim WALKING-Eintritt: Stance-Beine auf body_height vorverankert (kein
    # Walk-Start-Probe), Schwung-Beine frisch (None).
    eng = _engine(adaptive=True)
    eng._touchdown_z[3] = -0.05          # stale
    eng._td_searched[3] = True
    t = 0.37
    _drive_to_walking(eng, t)
    states = eng.leg_gait_states(t)
    for leg in HEXAPOD.legs:
        leg_id = int(leg.name.split('_')[1])
        is_swing, _ = states[leg_id]
        assert eng._td_searched[leg_id] is False
        if is_swing:
            assert eng._touchdown_z[leg_id] is None
        else:
            assert eng._touchdown_z[leg_id] == pytest.approx(_BODY_H)
