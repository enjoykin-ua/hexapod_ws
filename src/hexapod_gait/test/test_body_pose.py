"""
Tests für Block I Phase 8 — Body-Pose („Look-Around", Körper über fixen Füßen).

Deckt die Engine-Seite der Plan-Checkliste (P8.1/P8.2/P8.2b) ab:
  - T8.1  Neutral (alle DOF 0) == Standing-Pose, **bit-genau**
  - T8.2  6-DOF-Auslenkungen bleiben in den URDF-Limits (alle Envelope-Ecken)
  - T8.4  Return-to-Origin (rate-limitiert, monoton) + Exit → STANDING
  - T8.10 Greedy-Achsen-Clamp: eine Achse am Anschlag blockiert die anderen
          nicht; **kein IKError** verlässt die Body-Pose
  - T8.11 cmd_vel wird im BODY_POSE ignoriert

Pure-Python (pytest, kein rclpy). Die Envelope-Zahlen stammen aus
``tools/look_around_envelope_check.py`` (Plan §4.4) — dieselben Defaults wie im
gait_node. Geprüft wird gegen die **URDF**-Limits (zwei Limit-Quellen!).
"""

import itertools
import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, IKError, JointLimits, leg_ik
import pytest


_TRIPOD = GAIT_PRESETS['tripod']

# URDF-Limits (hexapod.urdf.xacro / hexapod_physical_properties.xacro).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

# Stance-Modi (radial, body_height) — 1:1 aus gait_node._STANCE_MODES.
_STANCES = (
    ('tief', 0.160, -0.065),
    ('mittel', 0.160, -0.080),
    ('hoch', 0.160, -0.100),
)

# Envelope-Defaults der gait_node-Params (Plan §4.4, Tool-belegt).
_DX, _DY, _DZ = 0.050, 0.035, 0.020
_PITCH, _YAW = math.radians(12.0), math.radians(10.0)

_TICK = 0.02   # 50 Hz


def _make_engine(radial=0.160, body_height=-0.080) -> GaitEngine:
    """Engine mit Stance-Pose + URDF-Limits (wie im gait_node)."""
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=0.05,
        cycle_time=2.0,
        radial_distance=radial,
        body_height=body_height,
        step_length_max=0.08,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
    )


def _run(engine, t, ticks):
    """``ticks`` Engine-Ticks fahren, letzte Angles + Endzeit zurückgeben."""
    angles = None
    for _ in range(ticks):
        t += _TICK
        angles = engine.compute_joint_angles(t)
    return angles, t


def _assert_in_limits(angles, context=''):
    """Alle 18 Gelenkwinkel gegen die URDF-Limits prüfen."""
    bounds = (
        (_URDF_LIMITS.coxa_lower, _URDF_LIMITS.coxa_upper),
        (_URDF_LIMITS.femur_lower, _URDF_LIMITS.femur_upper),
        (_URDF_LIMITS.tibia_lower, _URDF_LIMITS.tibia_upper),
    )
    for leg in HEXAPOD.legs:
        for i in range(3):
            lo, hi = bounds[i]
            v = angles[leg.name][i]
            assert lo <= v <= hi, (
                f'{context}{leg.name} joint{i} = {v:.4f} outside [{lo}, {hi}]'
            )


# ----- T8.1 Nullpunkt --------------------------------------------------- #

@pytest.mark.parametrize('name,radial,bh', _STANCES)
def test_neutral_pose_is_standing_pose_bit_exact(name, radial, bh):
    """T8.1: DOF = 0 liefert bit-genau die Stand-Pose (kein Eintritts-Sprung)."""
    engine = _make_engine(radial, bh)
    stand = engine.compute_joint_angles(0.0)
    assert engine.start_body_pose(0.0)
    assert engine.state == GaitEngine.STATE_BODY_POSE
    first = engine.compute_joint_angles(0.0)
    for leg in HEXAPOD.legs:
        assert first[leg.name] == stand[leg.name], (
            f'{name}/{leg.name}: Eintritt in die Body-Pose ist nicht bit-genau'
        )


def test_start_body_pose_only_from_standing():
    """start_body_pose ist ein No-op außerhalb von STANDING (Defense-in-depth)."""
    engine = _make_engine()
    engine.start_ramp({}, 0.0, 2.0)          # → STARTUP_RAMP
    assert not engine.start_body_pose(0.1)
    assert engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_stop_body_pose_outside_show_is_noop():
    """stop_body_pose meldet False, wenn gar keine Body-Pose läuft."""
    engine = _make_engine()
    assert not engine.stop_body_pose(0.0)
    assert engine.state == GaitEngine.STATE_STANDING


def test_foot_snapshot_survives_adaptive_stand():
    """
    Der Fuß-Snapshot hält die per Bein konform abgesenkten Füße fest ([D-Show-11]).

    Mit aktivem Adaptive Stand (S4-7) verankert ein Bein über einer Senke tiefer.
    Eintritt → Show → Verlassen muss exakt dorthin zurückkehren (kein Hochziehen
    auf die starre Pose), und der nächste STANDING-Tick darf nicht nachspringen.
    """
    engine = _make_engine()
    engine.adaptive_stand_enable = True
    t = 0.0
    engine.reset_stand_conform(t)
    # leg_1 findet erst spät Kontakt (Senke), die anderen sofort.
    engine.set_foot_contacts({1: False, 2: True, 3: True, 4: True, 5: True,
                              6: True})
    _, t = _run(engine, t, 50)
    engine.set_foot_contacts({i: True for i in range(1, 7)})
    before, t = _run(engine, t, 10)
    assert engine._stand_conform_z[1] < engine._stand_conform_z[2], (
        'Testaufbau: leg_1 sollte tiefer verankert sein'
    )

    assert engine.start_body_pose(t)
    engine.set_body_pose_target((0.0, 0.0, 0.0, 0.0, math.radians(8), 0.0))
    _, t = _run(engine, t, 300)
    assert engine.stop_body_pose(t)
    for _ in range(600):
        t += _TICK
        exit_pose = engine.compute_joint_angles(t)
        if engine.state == GaitEngine.STATE_STANDING:
            break
    assert engine.state == GaitEngine.STATE_STANDING
    after = engine.compute_joint_angles(t + _TICK)
    for leg in HEXAPOD.legs:
        assert exit_pose[leg.name] == before[leg.name], (
            f'{leg.name}: Exit trifft die Eintritts-Pose nicht'
        )
        assert after[leg.name] == exit_pose[leg.name], (
            f'{leg.name}: erster STANDING-Tick springt nach dem Exit'
        )


# ----- T8.2 / T8.10 Limits + Greedy-Clamp ------------------------------- #

@pytest.mark.parametrize('name,radial,bh', _STANCES)
def test_all_envelope_corners_stay_in_limits(name, radial, bh):
    """
    T8.2/T8.10: alle 32 Vorzeichen-Ecken der Envelope anfahren.

    Erwartung: **kein** IKError verlässt die Engine (der Greedy-Clamp bzw. der
    Notausgang fängt jede unerreichbare Kombination ab) und jeder emittierte
    Gelenkwinkel liegt in den URDF-Limits.
    """
    engine = _make_engine(radial, bh)
    t = 0.0
    assert engine.start_body_pose(t)
    for signs in itertools.product((1, -1), repeat=5):
        engine.set_body_pose_target((
            signs[0] * _DX, signs[1] * _DY, signs[2] * _DZ,
            0.0, signs[3] * _PITCH, signs[4] * _YAW,
        ))
        angles, t = _run(engine, t, 200)
        _assert_in_limits(angles, f'{name} {signs}: ')
    assert engine.state == GaitEngine.STATE_BODY_POSE


@pytest.mark.parametrize('name,radial,bh', _STANCES)
def test_single_axis_reaches_its_limit(name, radial, bh):
    """
    Jede Achse allein erreicht ihren vollen Envelope-Wert (Gate 1 des Tools).

    Belegt, dass die Per-Achse-Defaults nicht schon einzeln beschnitten werden —
    sonst wäre der Envelope-Param eine Lüge.
    """
    engine = _make_engine(radial, bh)
    limits = (_DX, _DY, _DZ, 0.0, _PITCH, _YAW)
    for idx, want in enumerate(limits):
        if want == 0.0:
            continue
        for sign in (1, -1):
            engine._state = GaitEngine.STATE_STANDING
            t = 0.0
            assert engine.start_body_pose(t)
            target = [0.0] * 6
            target[idx] = sign * want
            engine.set_body_pose_target(target)
            angles, t = _run(engine, t, 400)
            got = engine.body_pose[idx]
            assert got == pytest.approx(sign * want, abs=1e-6), (
                f'{name}: Achse {idx} erreicht nur {got:.4f} statt '
                f'{sign * want:.4f}'
            )
            _assert_in_limits(angles, f'{name} axis{idx}: ')


def test_greedy_clamp_does_not_block_everything():
    """
    T8.10: alle fünf Achsen gleichzeitig ans Maximum → jede kommt ein Stück weit.

    Kinematisch ist diese Kombination unmöglich (Plan §4.4). Ein globaler Clamp
    (oder ein Alles-oder-nichts-Schritt) würde die Bewegung komplett anhalten;
    der Greedy-Clamp bringt jede Achse so weit wie möglich. Geprüft wird genau
    das: **keine** Achse bleibt bei 0, keine überschreitet ihr Maximum, und die
    Gelenkwinkel bleiben in den URDF-Limits.
    """
    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((_DX, _DY, _DZ, 0.0, _PITCH, _YAW))
    angles, t = _run(engine, t, 400)
    dx, dy, dz, _roll, pitch, yaw = engine.body_pose
    assert dz == pytest.approx(_DZ, abs=1e-6), 'dz (höchste Priorität) blockiert'
    for name, got, want in (
        ('dx', dx, _DX), ('dy', dy, _DY),
        ('pitch', pitch, _PITCH), ('yaw', yaw, _YAW),
    ):
        assert 0.0 < got <= want + 1e-9, (
            f'{name} = {got:.4f} (erwartet: >0 und <= {want:.4f})'
        )
    _assert_in_limits(angles)


def test_blocked_axis_does_not_stop_the_others():
    """
    T8.10 (Kern): eine Achse am Anschlag blockiert die übrigen nicht.

    Zuerst pitch allein voll ausfahren (dort ist die Envelope ausgereizt), dann
    zusätzlich seitwärts wandern. Erwartung: dy kommt trotzdem in Bewegung —
    und der bereits erreichte pitch wird **nicht** von selbst zurückgedrängt
    (die Prioritäts-Reihenfolge wirkt auf den Zuwachs pro Tick, nicht rückwirkend
    — sonst würden sich Achsen ohne Zutun des Nutzers bewegen).
    """
    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((0.0, 0.0, 0.0, 0.0, _PITCH, 0.0))
    _, t = _run(engine, t, 400)
    pitch_before = engine.body_pose[4]
    assert pitch_before == pytest.approx(_PITCH, abs=1e-6)

    engine.set_body_pose_target((0.0, _DY, 0.0, 0.0, _PITCH, 0.0))
    angles, t = _run(engine, t, 400)
    dy_after = engine.body_pose[1]
    assert dy_after > 0.0, 'dy bleibt trotz freier Envelope stehen'
    assert engine.body_pose[4] == pytest.approx(pitch_before, abs=1e-9), (
        'pitch wurde zurückgedrängt'
    )
    _assert_in_limits(angles)


def test_no_ikerror_escapes_body_pose():
    """
    Aus der Body-Pose darf **nie** ein IKError nach außen dringen.

    Sonst würde der gait_node einen Safety-Freeze auslösen — mitten in einer
    Show, die per Definition sicher sein soll. Geprüft mit absichtlich weit
    überzogenen Zielen (jenseits jedes Envelope-Params).
    """
    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    for signs in itertools.product((1, -1), repeat=3):
        engine.set_body_pose_target((
            signs[0] * 0.30, signs[1] * 0.30, signs[2] * 0.20,
            math.radians(40), math.radians(40), math.radians(40),
        ))
        try:
            angles, t = _run(engine, t, 300)
        except IKError as exc:      # pragma: no cover - der Fehlerfall
            pytest.fail(f'IKError aus der Body-Pose: {exc}')
        _assert_in_limits(angles, f'overdrive {signs}: ')


def test_rescue_after_external_param_change():
    """
    Notausgang: ungültig gewordene Ist-Pose bricht die Show nicht ab.

    Wird die Pose durch eine externe Änderung unerreichbar, halbiert die Engine
    Richtung 0, statt einen IKError zu werfen.

    body_height ist zwar standing_only (also während der Show gesperrt) — der
    Notausgang ist die Absicherung gegen künftige Pfade, die das umgehen.
    """
    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((_DX, _DY, _DZ, 0.0, _PITCH, _YAW))
    _, t = _run(engine, t, 400)
    # Fuß-Snapshot künstlich unerreichbar machen (simuliert eine Geometrie-
    # Änderung mitten in der Show).
    engine._body_pose_foot_fix = {
        name: (x * 1.6, y * 1.6, z)
        for name, (x, y, z) in engine._body_pose_foot_fix.items()
    }
    angles, t = _run(engine, t, 5)
    assert angles is not None
    assert engine.state == GaitEngine.STATE_BODY_POSE


# ----- T8.4 Return-to-Origin + Exit ------------------------------------- #

def test_return_to_origin_is_rate_limited_and_monotone():
    """T8.4: neutrale Sticks → DOF laufen rate-limitiert + monoton gegen 0."""
    engine = _make_engine()
    engine.body_pose_rate_lin = 0.08
    engine.body_pose_rate_ang = math.radians(30.0)
    t = 0.0
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((0.0, 0.0, 0.0, 0.0, _PITCH, 0.0))
    _, t = _run(engine, t, 400)
    assert engine.body_pose[4] == pytest.approx(_PITCH, abs=1e-6)

    engine.set_body_pose_target((0.0,) * 6)   # Sticks losgelassen
    prev = engine.body_pose[4]
    for _ in range(400):
        t += _TICK
        engine.compute_joint_angles(t)
        cur = engine.body_pose[4]
        assert cur <= prev + 1e-12, 'Rückweg ist nicht monoton'
        step = abs(cur - prev)
        assert step <= engine.body_pose_rate_ang * _TICK + 1e-9, (
            f'Rate-Limit verletzt: {step:.6f} rad in einem Tick'
        )
        prev = cur
        if cur == 0.0:
            break
    assert engine.body_pose[4] == pytest.approx(0.0, abs=1e-4)
    # Ohne Exit-Flag bleibt die Engine in der Show (nur der Körper federt zurück).
    assert engine.state == GaitEngine.STATE_BODY_POSE


def test_exit_returns_to_standing_after_convergence():
    """T8.4: stop_body_pose federt zurück und wechselt dann nach STANDING."""
    engine = _make_engine()
    t = 0.0
    stand = engine.compute_joint_angles(t)
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((_DX, 0.0, 0.0, 0.0, _PITCH, _YAW))
    _, t = _run(engine, t, 400)
    assert engine.state == GaitEngine.STATE_BODY_POSE

    assert engine.stop_body_pose(t)
    exit_pose = None
    for _ in range(1000):
        t += _TICK
        exit_pose = engine.compute_joint_angles(t)
        if engine.state == GaitEngine.STATE_STANDING:
            break
    assert engine.state == GaitEngine.STATE_STANDING
    assert engine.body_pose == (0.0,) * 6
    for leg in HEXAPOD.legs:
        assert exit_pose[leg.name] == stand[leg.name], (
            f'{leg.name}: Rückkehr trifft die Stand-Pose nicht bit-genau'
        )


def test_exit_ignores_new_stick_input():
    """Während des Exits ziehen neue Stick-Werte den Körper nicht zurück."""
    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    engine.set_body_pose_target((0.0, 0.0, 0.0, 0.0, _PITCH, 0.0))
    _, t = _run(engine, t, 400)
    assert engine.stop_body_pose(t)
    engine.set_body_pose_target((0.0, 0.0, 0.0, 0.0, _PITCH, 0.0))   # ignoriert
    for _ in range(1000):
        t += _TICK
        engine.compute_joint_angles(t)
        if engine.state == GaitEngine.STATE_STANDING:
            break
    assert engine.state == GaitEngine.STATE_STANDING


def test_set_target_outside_body_pose_is_ignored():
    """set_body_pose_target wirkt nur im BODY_POSE (zustandsloser Teleop!)."""
    engine = _make_engine()
    engine.set_body_pose_target((_DX, _DY, _DZ, 0.0, _PITCH, _YAW))
    assert engine.body_pose == (0.0,) * 6
    angles = engine.compute_joint_angles(0.0)
    _assert_in_limits(angles)


# ----- T8.11 cmd_vel-Guard --------------------------------------------- #

def test_cmd_vel_ignored_in_body_pose():
    """T8.11: cmd_vel darf die Show nicht nach WALKING kippen."""
    engine = _make_engine()
    assert engine.start_body_pose(0.0)
    clamped = engine.set_command(0.05, 0.03, 0.4, 0.1)
    assert clamped is False
    assert engine.state == GaitEngine.STATE_BODY_POSE


# ----- Rotations-Mathe -------------------------------------------------- #

def test_rot_body_inv_is_true_inverse():
    """
    ``_rot_body_inv`` ist die exakte Inverse von ``R = Rz·Ry·Rx``.

    Pinnt die Reihenfolge: ``rotate_xy(p, -roll, -pitch)`` wäre sie NICHT (das
    ist Ry·Rx statt Rx·Ry) — mit yaw und großen Winkeln driftet das sichtbar.
    """
    from hexapod_gait.gait_engine import _rot_body_inv

    def _rot_body(point, roll, pitch, yaw):
        x, y, z = point
        c, s = math.cos(roll), math.sin(roll)
        y, z = c * y - s * z, s * y + c * z
        c, s = math.cos(pitch), math.sin(pitch)
        x, z = c * x + s * z, -s * x + c * z
        c, s = math.cos(yaw), math.sin(yaw)
        x, y = c * x - s * y, s * x + c * y
        return (x, y, z)

    roll, pitch, yaw = 0.21, -0.13, 0.35
    for p in ((0.2, -0.18, -0.08), (0.0, 0.0, 0.1), (-0.15, 0.05, 0.0)):
        back = _rot_body_inv(_rot_body(p, roll, pitch, yaw), roll, pitch, yaw)
        for a, b in zip(p, back):
            assert a == pytest.approx(b, abs=1e-12)


def test_body_pose_matches_direct_ik():
    """
    Die Engine-Pose stimmt mit der unabhängig gerechneten Transformation überein.

    Zweitrechnung ohne Engine-Interna: fixe Fuß-Position (base) → ``R⁻¹·(p−d)``
    → ``leg_ik``. Schützt davor, dass Engine und Envelope-Tool auseinanderlaufen.
    """
    from hexapod_gait.gait_engine import _rot_body_inv
    from hexapod_kinematics.geometry import base_to_leg_frame, leg_to_base_frame

    engine = _make_engine()
    t = 0.0
    assert engine.start_body_pose(t)
    dof = (0.03, -0.02, 0.01, 0.0, math.radians(7), math.radians(-6))
    engine.set_body_pose_target(dof)
    angles, t = _run(engine, t, 600)
    assert engine.body_pose == pytest.approx(dof, abs=1e-6)

    dx, dy, dz, roll, pitch, yaw = dof
    for leg in HEXAPOD.legs:
        foot_base = leg_to_base_frame((0.160, 0.0, -0.080), leg)
        rel = (foot_base[0] - dx, foot_base[1] - dy, foot_base[2] - dz)
        expect = leg_ik(
            *base_to_leg_frame(_rot_body_inv(rel, roll, pitch, yaw), leg),
            leg, _URDF_LIMITS,
        )
        for got, want in zip(angles[leg.name], expect):
            assert got == pytest.approx(want, abs=1e-9)
