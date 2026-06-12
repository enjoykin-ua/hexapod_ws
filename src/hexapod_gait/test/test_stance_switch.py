"""
Tests für den Stance-Modus-Wechsel (Phase 13 Stage 1) in gait_engine.

STATE_STANCE_SWITCH fährt per Tripod-Reposition radial UND body_height
gleichzeitig vom Ist- zum Ziel-Modus (kleiner switch_step_height → Apex unter
Femur-Wand). Nur aus STANDING; cmd_vel ignoriert. Endet im Ziel-Modus → STANDING.

3 validierte Modi (leg_changes S4): hoch (-0.13/0.13), mittel (-0.10/0.145),
tief (-0.07/0.16), alle step_height 0.04. Pure-Python (pytest, kein rclpy).
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_TRIPOD = GAIT_PRESETS['tripod']
_URDF = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)
# (radial, body_height, step_height) je Modus — mit Femur-Marge gewählt
# (real-engine-validiert, NICHT am Min-Radial-Rand). leg_changes S4.
HOCH = (0.13, -0.13, 0.04)
MITTEL = (0.145, -0.10, 0.04)
TIEF = (0.16, -0.07, 0.04)
_SWITCH_DUR = 2.0


def _engine(mode=MITTEL) -> GaitEngine:
    radial, bh, sh = mode
    return GaitEngine(
        pattern=_TRIPOD, step_height=sh, cycle_time=2.0,
        radial_distance=radial, body_height=bh, step_length_max=0.03,
        joint_limits={leg.name: _URDF for leg in HEXAPOD.legs},
        standup_radial_distance=0.17, reposition_cycle_time=2.0,
    )


def _switch(engine, target, t=0.0):
    r, bh, sh = target
    return engine.start_stance_switch(t, r, bh, sh, _SWITCH_DUR)


def _assert_in_limits(angles):
    for name, (c, f, t) in angles.items():
        assert _URDF.coxa_lower <= c <= _URDF.coxa_upper, f'{name} coxa {c}'
        assert _URDF.femur_lower <= f <= _URDF.femur_upper, f'{name} femur {f}'
        assert _URDF.tibia_lower <= t <= _URDF.tibia_upper, f'{name} tibia {t}'


# ----- Guards ----------------------------------------------------------
def test_switch_only_from_standing():
    engine = _engine()
    assert engine.state == GaitEngine.STATE_STANDING
    assert _switch(engine, HOCH) is True
    assert engine.state == GaitEngine.STATE_STANCE_SWITCH


def test_switch_rejected_when_not_standing():
    engine = _engine()
    engine.set_command(0.05, 0.0, 0.0, 0.0)   # → WALKING
    assert engine.state == GaitEngine.STATE_WALKING
    assert _switch(engine, HOCH) is False


def test_switch_validates_duration():
    engine = _engine()
    with pytest.raises(ValueError):
        engine.start_stance_switch(0.0, 0.13, -0.13, 0.04, 0.0)


# ----- Pfad in-limit + Zielzustand für alle Übergänge ------------------
@pytest.mark.parametrize('frm,to', [
    (MITTEL, HOCH), (HOCH, MITTEL), (MITTEL, TIEF), (TIEF, MITTEL),
    (HOCH, TIEF), (TIEF, HOCH),
])
def test_switch_path_in_limits_and_reaches_target(frm, to):
    engine = _engine(frm)
    _switch(engine, to)
    for i in range(1, 40):
        angles = engine.compute_joint_angles(_SWITCH_DUR * i / 40.0)
        _assert_in_limits(angles)
    # Über das Ende → Ziel-Modus übernommen, STANDING.
    end = engine.compute_joint_angles(_SWITCH_DUR + 0.5)
    assert engine.state == GaitEngine.STATE_STANDING
    r, bh, sh = to
    assert engine.radial_distance == pytest.approx(r)
    assert engine.body_height == pytest.approx(bh)
    assert engine.step_height == pytest.approx(sh)
    _assert_in_limits(end)


def test_switch_max_three_legs_in_air():
    """Tripod: nie mehr als 3 Beine gleichzeitig im Swing (statisch stabil)."""
    engine = _engine(MITTEL)
    _switch(engine, HOCH)
    # In jeder Hälfte schwingen genau die 3 Beine einer Gruppe.
    for i in range(1, 40):
        p = i / 40.0
        # Gruppe ungerade (1,3,5) Hälfte 1, gerade (2,4,6) Hälfte 2 → max 3.
        swinging = sum(
            1 for leg in HEXAPOD.legs
            if (int(leg.name.split('_')[1]) % 2 == 1 and p < 0.5)
            or (int(leg.name.split('_')[1]) % 2 == 0 and 0.5 <= p < 1.0)
        )
        assert swinging <= 3


def test_cmd_vel_ignored_during_switch():
    engine = _engine(MITTEL)
    _switch(engine, TIEF)
    engine.compute_joint_angles(_SWITCH_DUR * 0.3)
    clamped = engine.set_command(0.1, 0.0, 0.0, _SWITCH_DUR * 0.3)
    assert clamped is False
    assert engine.state == GaitEngine.STATE_STANCE_SWITCH


@pytest.mark.parametrize('mode', [HOCH, MITTEL, TIEF])
def test_mode_walks_all_directions_no_ikerror(mode):
    """
    Jeder Modus läuft über ALLE cmd_vel-Richtungen @ step_length_max in-limit.

    KRITISCH (echte Engine): fängt Modi am Femur-Wand-Rand (Min-Radial-Bug —
    das Envelope-Tool sagt GREEN, aber der echte Engine-Pfad fehlert).
    """
    from hexapod_kinematics import IKError
    radial, bh, sh = mode
    engine = GaitEngine(
        pattern=_TRIPOD, step_height=sh, cycle_time=2.0,
        radial_distance=radial, body_height=bh, step_length_max=0.03,
        joint_limits={leg.name: _URDF for leg in HEXAPOD.legs},
        standup_radial_distance=radial, reposition_cycle_time=2.0,
    )
    lin = engine.linear_max
    directions = [
        (lin, 0.0, 0.0), (0.0, lin, 0.0), (0.0, 0.0, 2.0),
        (lin * 0.7, lin * 0.7, 0.0), (lin * 0.6, 0.0, 1.2),
        (-lin, 0.0, 0.0), (0.0, -lin, 0.0), (-lin * 0.7, -lin * 0.7, 0.0),
    ]
    for vx, vy, om in directions:
        engine._state = GaitEngine.STATE_STANDING
        engine.set_command(vx, vy, om, 0.0)
        for i in range(220):
            try:
                engine.compute_joint_angles(i * 0.02)
            except IKError as exc:
                raise AssertionError(
                    f'mode radial={radial} bh={bh}: IKError bei '
                    f'cmd=({vx:.3f},{vy:.3f},{om:.2f}): {exc}'
                )


def test_body_height_monotonic_to_target():
    """body_height-Rampe ist monoton von from → to (kein Über-/Unterschwingen)."""
    engine = _engine(MITTEL)   # -0.100
    _switch(engine, HOCH)      # -0.140 (tiefer)
    # leg_2 z (≈ body_height der Stützphase) sollte monoton fallen.
    from hexapod_kinematics import leg_fk
    prev = None
    for i in range(1, 41):
        a = engine.compute_joint_angles(_SWITCH_DUR * i / 40.0)
        # leg_2 (gerade) schwingt erst in Hälfte 2; in Hälfte 1 ist es Stütze
        # → z folgt der globalen bh-Rampe.
        if i <= 20:
            z = leg_fk(*a['leg_2'], HEXAPOD.by_name('leg_2'))[2]
            if prev is not None:
                assert z <= prev + 1e-9
            prev = z
