"""
Tests für Block B4 — Show-Pose (Free-Leg), Teil B4.1 (SHOW_ENTER + SHOW_ACTIVE).

Stütze auf den 4 hinteren Beinen (leg_2,3,4,5), die 2 Vorderbeine (leg_1,6)
frei in der Luft. Zwei Phasen (B4.1):
  - STATE_SHOW_ENTER: Phase a (alle 6 am Boden) Körper-Rückversatz, Phase b
    Vorderbeine heben; CoG-Marge im 4-Bein-Polygon-Gate pro Tick in Phase b.
  - STATE_SHOW_ACTIVE: hält die eingenommene Show-Pose statisch.
STATE_SHOW_EXIT (zurück nach STANDING) + Joystick-Folgen kommen in B4.2/B4.3.

Wertneutral: die Engine kennt keine konkreten Posen/Margen — sie kommen als
Args von start_show_enter. Pure-Python (pytest, kein rclpy). Deckt die
B4.1-Zeilen der Checkliste in project_finalization/B4_show_pose_plan.md ab.
"""

from hexapod_gait.gait_engine import (
    _SHOW_FRONT_LEGS,
    _SHOW_SUPPORT_LEGS,
    GaitEngine,
)
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_gait.joint_load import compute_load
from hexapod_kinematics import HEXAPOD, JointLimits, leg_fk, leg_to_base_frame
import pytest


_TRIPOD = GAIT_PRESETS['tripod']

# URDF-Limits (= HW, Stage F symmetrisch + Tibia-Unlock): coxa ±0.415,
# femur ±1.57, tibia -1.00..+2.50.
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-1.00, tibia_upper=2.50,
)

# Stand-/Walk-Pose (feet_closer_walk.yaml).
_WALK_RADIAL = 0.215
_BH = -0.120

# Show-Parameter (B4.0-bestätigt: Shift 0.065 → Marge ~50 mm; moderate
# Vorderbein-Hoch-Pose radial 0.22 / z -0.04 = Fuß ~80 mm über Boden).
_SHOW_DURATION = 4.0
_SHIFT_BACK = 0.065
_SHIFT_FRACTION = 0.5
_FRONT_RADIAL = 0.22
_FRONT_Z = -0.04
_SAFETY_MARGIN = 0.030
_RETURN_RATE = 0.5        # m/s (B4.2 Nachführ-/Rückkehr-Rate)


def _make_engine() -> GaitEngine:
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.080,
        cycle_time=2.0,
        radial_distance=_WALK_RADIAL,
        body_height=_BH,
        step_length_max=0.089,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
        standup_radial_distance=0.295,
        reposition_cycle_time=2.0,
    )


def _start_show(
    engine: GaitEngine,
    shift_back: float = _SHIFT_BACK,
    safety_margin: float = _SAFETY_MARGIN,
    front_radial: float = _FRONT_RADIAL,
    front_z: float = _FRONT_Z,
) -> bool:
    return engine.start_show_enter(
        t=0.0,
        duration=_SHOW_DURATION,
        body_shift_back=shift_back,
        shift_fraction=_SHIFT_FRACTION,
        front_radial=front_radial,
        front_z=front_z,
        safety_margin=safety_margin,
        return_rate=_RETURN_RATE,
    )


def _tick_through(engine: GaitEngine, t_end: float, n: int = 200):
    """Engine in n Schritten bis t_end ticken (wie der reale 50-Hz-Loop)."""
    out = None
    for i in range(1, n + 1):
        out = engine.compute_joint_angles(t_end * i / n)
    return out


def _assert_in_limits(angles):
    for name, (c, f, t) in angles.items():
        assert _URDF_LIMITS.coxa_lower <= c <= _URDF_LIMITS.coxa_upper, \
            f'{name} coxa {c} out of URDF limit'
        assert _URDF_LIMITS.femur_lower <= f <= _URDF_LIMITS.femur_upper, \
            f'{name} femur {f} out of URDF limit'
        assert _URDF_LIMITS.tibia_lower <= t <= _URDF_LIMITS.tibia_upper, \
            f'{name} tibia {t} out of URDF limit'


def _foot_base_z(angles, leg_name) -> float:
    leg = HEXAPOD.by_name(leg_name)
    foot_leg = leg_fk(*angles[leg_name], leg)
    return leg_to_base_frame(foot_leg, leg)[2]


def _front_foot_leg(angles, leg_name):
    """Vorderbein-Foot im Bein-Frame (x=radial, y=lateral, z=vertikal)."""
    leg = HEXAPOD.by_name(leg_name)
    return leg_fk(*angles[leg_name], leg)


# --------------------------------------------------------------------------
# Toggle-Guards
# --------------------------------------------------------------------------
def test_show_enter_only_from_standing():
    engine = _make_engine()
    assert engine.state == GaitEngine.STATE_STANDING
    assert _start_show(engine) is True
    assert engine.state == GaitEngine.STATE_SHOW_ENTER


def test_show_enter_rejected_when_not_standing():
    engine = _make_engine()
    # In WALKING wechseln, dann Show ablehnen.
    engine.set_command(0.05, 0.0, 0.0, 0.0)
    assert engine.state == GaitEngine.STATE_WALKING
    assert _start_show(engine) is False
    assert engine.state == GaitEngine.STATE_WALKING


def test_show_enter_validates_args():
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_show_enter(0.0, 0.0, _SHIFT_BACK, _SHIFT_FRACTION,
                                _FRONT_RADIAL, _FRONT_Z, _SAFETY_MARGIN)
    with pytest.raises(ValueError):
        engine.start_show_enter(0.0, _SHOW_DURATION, _SHIFT_BACK, 0.0,
                                _FRONT_RADIAL, _FRONT_Z, _SAFETY_MARGIN)
    with pytest.raises(ValueError):
        engine.start_show_enter(0.0, _SHOW_DURATION, _SHIFT_BACK, 1.0,
                                _FRONT_RADIAL, _FRONT_Z, _SAFETY_MARGIN)


# --------------------------------------------------------------------------
# ENTER-Pfad in-limit + Phasen-Geometrie
# --------------------------------------------------------------------------
def test_enter_path_all_in_limits():
    engine = _make_engine()
    _start_show(engine)
    for i in range(1, 40):
        t = _SHOW_DURATION * i / 40.0
        angles = engine.compute_joint_angles(t)
        _assert_in_limits(angles)


def test_support_feet_stay_on_ground():
    engine = _make_engine()
    _start_show(engine)
    # Über die ganze ENTER-Phase bleiben die 4 Stützfüße auf Boden-Höhe (z=BH).
    for i in range(1, 40):
        t = _SHOW_DURATION * i / 40.0
        angles = engine.compute_joint_angles(t)
        for name in _SHOW_SUPPORT_LEGS:
            assert abs(_foot_base_z(angles, name) - _BH) < 1e-6, \
                f'{name} foot left ground at t={t}'


def test_front_feet_lift_in_phase_b():
    engine = _make_engine()
    _start_show(engine)
    # Kurz vor Ende (Phase b fast fertig) sind die Vorderfüße deutlich oben.
    angles = None
    for i in range(1, 200):
        angles = engine.compute_joint_angles(_SHOW_DURATION * i / 200.0)
    for name in _SHOW_FRONT_LEGS:
        lift = _foot_base_z(angles, name) - _BH
        assert lift > 0.05, f'{name} only lifted {lift * 1000:.0f} mm'


# --------------------------------------------------------------------------
# CoG-Marge-Gate
# --------------------------------------------------------------------------
def test_cog_margin_above_threshold_over_phase_b():
    """Design-Garantie: die ENTER-Trajektorie hält die Marge >= safety_margin."""
    engine = _make_engine()
    _start_show(engine)
    # Phase b liegt bei progress in (shift_fraction, 1).
    for i in range(1, 30):
        progress = _SHIFT_FRACTION + (1.0 - _SHIFT_FRACTION) * i / 30.0
        t = _SHOW_DURATION * progress
        angles = engine.compute_joint_angles(t)
        load = compute_load(angles, stance_legs=list(_SHOW_SUPPORT_LEGS))
        assert load.stability_margin_m >= _SAFETY_MARGIN, \
            f'margin {load.stability_margin_m * 1000:.1f} mm < goal at p={progress}'
        assert engine.state in (
            GaitEngine.STATE_SHOW_ENTER, GaitEngine.STATE_SHOW_ACTIVE)


def test_cog_gate_freezes_on_unsafe_pose():
    """Kein Rückversatz + hohe Marge-Schwelle → Gate hält letzte sichere Pose."""
    engine = _make_engine()
    _start_show(engine, shift_back=0.0, safety_margin=0.060)
    angles = _tick_through(engine, _SHOW_DURATION * 1.2, n=240)
    # Gate hat eingegriffen: nie nach SHOW_ACTIVE übergegangen, eingefroren.
    assert engine.state == GaitEngine.STATE_SHOW_ENTER
    # Gehaltene Pose ist in-limit (sichere Zwischenpose).
    _assert_in_limits(angles)
    # Weiteres Ticken ändert nichts (statischer Hold).
    later = engine.compute_joint_angles(_SHOW_DURATION * 2.0)
    assert later == angles


# --------------------------------------------------------------------------
# Übergang ENTER → ACTIVE + statisches Halten
# --------------------------------------------------------------------------
def test_enter_reaches_show_active():
    engine = _make_engine()
    _start_show(engine)
    _tick_through(engine, _SHOW_DURATION, n=200)
    # Ein Tick bei/über progress=1 schaltet auf SHOW_ACTIVE.
    engine.compute_joint_angles(_SHOW_DURATION)
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE


def test_show_active_holds_pose_static_and_in_limit():
    engine = _make_engine()
    _start_show(engine)
    _tick_through(engine, _SHOW_DURATION, n=200)
    a1 = engine.compute_joint_angles(_SHOW_DURATION)
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE
    a2 = engine.compute_joint_angles(_SHOW_DURATION + 5.0)
    assert a1 == a2          # statisch
    _assert_in_limits(a2)
    # Endpose: Vorderbeine in neutraler Hoch-Pose (Fuß über Boden), Stütze unten.
    for name in _SHOW_FRONT_LEGS:
        assert _foot_base_z(a2, name) - _BH > 0.05
    for name in _SHOW_SUPPORT_LEGS:
        assert abs(_foot_base_z(a2, name) - _BH) < 1e-6


# --------------------------------------------------------------------------
# cmd_vel wird in den Show-States ignoriert
# --------------------------------------------------------------------------
def test_cmd_vel_ignored_in_show_enter():
    engine = _make_engine()
    _start_show(engine)
    engine.compute_joint_angles(_SHOW_DURATION * 0.3)
    clamped = engine.set_command(0.1, 0.0, 0.0, _SHOW_DURATION * 0.3)
    assert clamped is False
    assert engine.state == GaitEngine.STATE_SHOW_ENTER


def test_cmd_vel_ignored_in_show_active():
    engine = _make_engine()
    _start_show(engine)
    _tick_through(engine, _SHOW_DURATION, n=200)
    engine.compute_joint_angles(_SHOW_DURATION)
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE
    clamped = engine.set_command(0.1, 0.05, 0.02, _SHOW_DURATION + 1.0)
    assert clamped is False
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE


# --------------------------------------------------------------------------
# B4.3 — STATE_SHOW_EXIT (Round-Trip zurück nach STANDING)
# --------------------------------------------------------------------------
_EXIT_DURATION = 3.0


def _enter_to_active(engine: GaitEngine):
    _start_show(engine)
    _tick_through(engine, _SHOW_DURATION, n=200)
    engine.compute_joint_angles(_SHOW_DURATION)
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE


def test_exit_guard_only_from_show_states():
    engine = _make_engine()
    # Aus STANDING ablehnen.
    assert engine.start_show_exit(0.0, _EXIT_DURATION) is False
    assert engine.state == GaitEngine.STATE_STANDING


def test_exit_validates_duration():
    engine = _make_engine()
    _enter_to_active(engine)
    with pytest.raises(ValueError):
        engine.start_show_exit(0.0, 0.0)


def test_round_trip_ends_in_standing_walk_pose():
    engine = _make_engine()
    _enter_to_active(engine)
    assert engine.start_show_exit(0.0, _EXIT_DURATION) is True
    assert engine.state == GaitEngine.STATE_SHOW_EXIT
    _tick_through(engine, _EXIT_DURATION, n=150)
    end = engine.compute_joint_angles(_EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_STANDING
    # Endpose == reguläre Walk-Stand-Pose (alle 6 Füße auf radial 0.215 @ BH).
    standing = engine.compute_joint_angles(_EXIT_DURATION + 1.0)
    for leg in HEXAPOD.legs:
        for a, b in zip(end[leg.name], standing[leg.name]):
            assert abs(a - b) < 1e-9
    for leg in HEXAPOD.legs:
        assert abs(_foot_base_z(end, leg.name) - _BH) < 1e-6


def test_exit_path_all_in_limits():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.start_show_exit(0.0, _EXIT_DURATION)
    for i in range(1, 40):
        angles = engine.compute_joint_angles(_EXIT_DURATION * i / 40.0)
        _assert_in_limits(angles)


def test_exit_lowers_front_before_shifting_body():
    """EXIT-Reihenfolge: erst Vorderbeine runter (6-Bein-Stütze), dann Körper vor."""
    engine = _make_engine()
    _enter_to_active(engine)
    engine.start_show_exit(0.0, _EXIT_DURATION)
    front_down_t = None
    for i in range(1, 200):
        t = _EXIT_DURATION * i / 200.0
        angles = engine.compute_joint_angles(t)
        front_lift = max(
            _foot_base_z(angles, n) - _BH for n in _SHOW_FRONT_LEGS)
        # Stütz-Fuß bleibt immer am Boden (z=BH) über die ganze EXIT-Phase.
        for n in _SHOW_SUPPORT_LEGS:
            assert abs(_foot_base_z(angles, n) - _BH) < 1e-6
        if front_down_t is None and front_lift < 1e-4:
            front_down_t = t
    # Vorderbeine erreichen den Boden vor dem Ende (zuerst runter).
    assert front_down_t is not None and front_down_t < _EXIT_DURATION


def test_can_walk_after_round_trip():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.start_show_exit(0.0, _EXIT_DURATION)
    _tick_through(engine, _EXIT_DURATION, n=150)
    engine.compute_joint_angles(_EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_STANDING
    # Nach dem Round-Trip ist Fahren wieder möglich.
    engine.set_command(0.05, 0.0, 0.0, _EXIT_DURATION + 0.1)
    assert engine.state == GaitEngine.STATE_WALKING


def test_exit_from_mid_enter():
    """EXIT mitten in ENTER (Vorderbeine halb oben) endet sauber in STANDING."""
    engine = _make_engine()
    _start_show(engine)
    # Bis in Phase b ticken (~75 % ENTER), dann EXIT.
    _tick_through(engine, _SHOW_DURATION * 0.75, n=150)
    engine.start_show_exit(_SHOW_DURATION * 0.75, _EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_SHOW_EXIT
    t0 = _SHOW_DURATION * 0.75
    for i in range(1, 160):
        engine.compute_joint_angles(t0 + _EXIT_DURATION * i / 160.0)
    end = engine.compute_joint_angles(t0 + _EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_STANDING
    _assert_in_limits(end)
    for leg in HEXAPOD.legs:
        assert abs(_foot_base_z(end, leg.name) - _BH) < 1e-6


def test_exit_from_frozen_enter():
    """EXIT aus eingefrorenem ENTER (unsichere Pose) endet sauber in STANDING."""
    engine = _make_engine()
    _start_show(engine, shift_back=0.0, safety_margin=0.060)
    _tick_through(engine, _SHOW_DURATION * 1.2, n=240)
    assert engine.state == GaitEngine.STATE_SHOW_ENTER  # frozen
    engine.start_show_exit(_SHOW_DURATION * 1.2, _EXIT_DURATION)
    t0 = _SHOW_DURATION * 1.2
    for i in range(1, 160):
        angles = engine.compute_joint_angles(t0 + _EXIT_DURATION * i / 160.0)
        _assert_in_limits(angles)
    end = engine.compute_joint_angles(t0 + _EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_STANDING
    for leg in HEXAPOD.legs:
        assert abs(_foot_base_z(end, leg.name) - _BH) < 1e-6


# --------------------------------------------------------------------------
# B4.2 — Vorderbeine folgen Joystick-Offsets (/cmd_show) in SHOW_ACTIVE
# --------------------------------------------------------------------------
def _active_tick(engine: GaitEngine, t0: float, n: int, dt: float = 0.02):
    """Tick n-mal im ACTIVE-State ab t0 (Schrittweite dt); → (angles, t)."""
    angles = None
    t = t0
    for _ in range(n):
        t += dt
        angles = engine.compute_joint_angles(t)
    return angles, t


def test_offset_moves_front_legs_lateral_and_vertical():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.set_show_offsets({'leg_1': (0.03, 0.02), 'leg_6': (-0.03, 0.02)})
    angles, _ = _active_tick(engine, _SHOW_DURATION, 60)  # 1.2 s → eingeschwungen
    _assert_in_limits(angles)
    # leg_1 (rechts): lateral +0.03, vertikal +0.02 ggü. Neutral (0, front_z).
    f1 = _front_foot_leg(angles, 'leg_1')
    assert abs(f1[1] - 0.03) < 2e-3
    assert abs(f1[2] - (_FRONT_Z + 0.02)) < 2e-3
    f6 = _front_foot_leg(angles, 'leg_6')
    assert abs(f6[1] - (-0.03)) < 2e-3
    # Stützbeine unbeeinflusst: weiter am Boden.
    for n in _SHOW_SUPPORT_LEGS:
        assert abs(_foot_base_z(angles, n) - _BH) < 1e-6


def test_offset_clamped_to_urdf_limits_no_ikerror():
    engine = _make_engine()
    _enter_to_active(engine)
    # Riesiger seitlicher Soll-Offset → muss am Coxa-Limit clampen, kein Crash.
    engine.set_show_offsets({'leg_1': (0.5, 0.0), 'leg_6': (0.5, 0.0)})
    angles, _ = _active_tick(engine, _SHOW_DURATION, 120)
    _assert_in_limits(angles)   # nie über URDF-Limit, kein IKError


def test_offset_rate_limited_no_jump():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.set_show_offsets({'leg_1': (0.1, 0.0), 'leg_6': (0.0, 0.0)})
    # Ein einzelner Tick mit dt=0.02 darf den Offset um max rate*dt = 0.01 m
    # bewegen (kein Sprung auf 0.1).
    a1 = engine.compute_joint_angles(_SHOW_DURATION + 0.02)
    lat = _front_foot_leg(a1, 'leg_1')[1]
    assert lat <= _RETURN_RATE * 0.02 + 1e-9
    assert lat > 0.0


def test_offset_returns_to_neutral_rate_limited():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.set_show_offsets({'leg_1': (0.04, 0.0), 'leg_6': (0.04, 0.0)})
    _active_tick(engine, _SHOW_DURATION, 60)
    # R1 los / Stick zentriert → Soll 0.
    engine.set_show_offsets({'leg_1': (0.0, 0.0), 'leg_6': (0.0, 0.0)})
    angles, _ = _active_tick(engine, _SHOW_DURATION + 1.2, 60)
    for n in _SHOW_FRONT_LEGS:
        assert abs(_front_foot_leg(angles, n)[1]) < 2e-3   # zurück bei Neutral


def test_offset_fades_during_exit_without_jump():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.set_show_offsets({'leg_1': (0.03, 0.02), 'leg_6': (-0.03, 0.02)})
    _, t = _active_tick(engine, _SHOW_DURATION, 60)
    prev = engine.compute_joint_angles(t)
    engine.start_show_exit(t, _EXIT_DURATION)
    # Über den EXIT: keine ruckartigen Joint-Sprünge zwischen Ticks.
    for i in range(1, 160):
        cur = engine.compute_joint_angles(t + _EXIT_DURATION * i / 160.0)
        for leg in HEXAPOD.legs:
            for a, b in zip(prev[leg.name], cur[leg.name]):
                assert abs(a - b) < 0.05   # rad/Tick, glatt
        prev = cur
    end = engine.compute_joint_angles(t + _EXIT_DURATION)
    assert engine.state == GaitEngine.STATE_STANDING
    for leg in HEXAPOD.legs:
        assert abs(_foot_base_z(end, leg.name) - _BH) < 1e-6


def test_offsets_reset_on_reenter():
    engine = _make_engine()
    _enter_to_active(engine)
    engine.set_show_offsets({'leg_1': (0.04, 0.02), 'leg_6': (0.04, 0.02)})
    _active_tick(engine, _SHOW_DURATION, 60)
    # Round-Trip raus → STANDING (monotone Zeit ab Exit-Start).
    t0 = _SHOW_DURATION + 1.2
    engine.start_show_exit(t0, _EXIT_DURATION)
    for i in range(1, 151):
        engine.compute_joint_angles(t0 + _EXIT_DURATION * i / 150.0)
    engine.compute_joint_angles(t0 + _EXIT_DURATION + 0.5)
    assert engine.state == GaitEngine.STATE_STANDING
    # Erneut rein → Offsets müssen 0 sein (Neutral), trotz alter set_show_offsets.
    t_re = 100.0
    engine.start_show_enter(
        t=t_re, duration=_SHOW_DURATION, body_shift_back=_SHIFT_BACK,
        shift_fraction=_SHIFT_FRACTION, front_radial=_FRONT_RADIAL,
        front_z=_FRONT_Z, safety_margin=_SAFETY_MARGIN, return_rate=_RETURN_RATE)
    for i in range(1, 201):
        engine.compute_joint_angles(t_re + _SHOW_DURATION * i / 200.0)
    a = engine.compute_joint_angles(t_re + _SHOW_DURATION + 0.5)
    assert engine.state == GaitEngine.STATE_SHOW_ACTIVE
    for n in _SHOW_FRONT_LEGS:
        assert abs(_front_foot_leg(a, n)[1]) < 1e-6   # kein Alt-Offset
