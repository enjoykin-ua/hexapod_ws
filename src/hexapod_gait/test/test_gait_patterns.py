"""
Tests für Block B3 — zusätzliche Gangarten (Wave / Tetrapod / Ripple).

Reine Daten-Patterns (``GaitPattern`` + ``GAIT_PRESETS``), Engine generisch.
Geprüft wird je Gangart: Offsets gültig + vollständig, jedes Bein schwingt 1×,
max-Beine-in-der-Luft (statische Stabilität), die gleichzeitig schwingenden
Beine sind balanciert (Diagonal/kontralateral), linear_max plausibel, und der
WALKING-Pfad ist mit der feet-closer-Pose + URDF-Limits limit-konform.

Bein-Layout: 1=vorne-R, 2=mitte-R, 3=hinten-R, 4=hinten-L, 5=mitte-L, 6=vorne-L.
Pure-Python (pytest, kein rclpy). B3.1 = Wave; Tetrapod/Ripple folgen.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS, WAVE
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_RIGHT = {1, 2, 3}
_LEFT = {4, 5, 6}

# URDF-Limits (Stand 2026-06: Tibia +2.50, s. servo_real_cal Stage F).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-1.00, tibia_upper=2.50,
)

# Feet-closer-Walk-Pose (preset), pattern-unabhängig.
_WALK_RADIAL = 0.215
_BH = -0.120
_STEP_HEIGHT = 0.080
_STEP_LENGTH_MAX = 0.089
_CYCLE = 2.0


def _swinging_legs(pattern, phi: float) -> set:
    """
    Bein-IDs, die bei globaler Cycle-Phase ``phi`` schwingen.

    Repliziert exakt die Engine-Bedingung aus ``_compute_walking_targets``:
    ``cycle_phase = (phi + offset) % 1`` ; Swing wenn ``cycle_phase < swing_duty``.
    """
    out = set()
    for leg_id, off in pattern.phase_offset_per_leg.items():
        if off is None:
            continue
        if ((phi + off) % 1.0) < pattern.swing_duty:
            out.add(leg_id)
    return out


def _sample_phases(n: int = 240):
    """Cycle-Phasen leicht gegen exakte Tiling-Grenzen versetzt (Float-robust)."""
    return [(i + 0.5) / n for i in range(n)]


def _make_engine(pattern) -> GaitEngine:
    return GaitEngine(
        pattern=pattern,
        step_height=_STEP_HEIGHT,
        cycle_time=_CYCLE,
        radial_distance=_WALK_RADIAL,
        body_height=_BH,
        step_length_max=_STEP_LENGTH_MAX,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
    )


# ===================== generische Pattern-Checks ====================== #

def _assert_offsets_valid_and_complete(pattern):
    offs = pattern.phase_offset_per_leg
    assert set(offs.keys()) == {1, 2, 3, 4, 5, 6}, 'alle 6 Beine erwartet'
    for leg_id, off in offs.items():
        assert off is not None, f'Bein {leg_id} muss schwingen (kein None)'
        assert 0.0 <= off < 1.0, f'Offset {off} außerhalb [0,1)'
    assert 0.0 < pattern.swing_duty < 1.0


def _assert_each_leg_swings(pattern):
    """Über den Cycle gesehen ist jedes Bein irgendwann in der Luft."""
    seen = set()
    for phi in _sample_phases():
        seen |= _swinging_legs(pattern, phi)
    assert seen == {1, 2, 3, 4, 5, 6}


def _max_in_air(pattern) -> int:
    return max(len(_swinging_legs(pattern, phi)) for phi in _sample_phases())


def _lift_order(pattern) -> list:
    """
    Tatsächliche zeitliche HEBE-Reihenfolge der Beine.

    Ein Bein beginnt seinen Swing bei ``phi = (1 - offset) % 1`` (Engine-
    Konvention, s. ``_compute_walking_targets``). Sortiert nach diesem
    Start-phi (Tie-Break leg_id). So wird die echte Reihenfolge geprüft,
    NICHT die Offset-Sortierung (die ist invertiert!).
    """
    starts = {}
    for leg_id, off in pattern.phase_offset_per_leg.items():
        if off is None:
            continue
        starts[leg_id] = (1.0 - off) % 1.0
    return [
        lid for lid, _ in sorted(starts.items(), key=lambda kv: (kv[1], kv[0]))
    ]


def _assert_linear_max(pattern):
    eng = _make_engine(pattern)
    expected = _STEP_LENGTH_MAX / (_CYCLE * (1.0 - pattern.swing_duty))
    assert eng.linear_max == pytest.approx(expected, rel=1e-9)


def _assert_walk_in_limits(pattern, vx: float):
    """Ein Cycle WALKING mit dem Pattern → kein IKError (limit-konform)."""
    eng = _make_engine(pattern)
    eng.set_command(vx, 0.0, 0.0, 0.0)
    assert eng.state == GaitEngine.STATE_WALKING
    for i in range(1, 121):
        eng.compute_joint_angles(i / 120.0 * _CYCLE)  # wirft bei Verletzung


# ============================== WAVE ================================== #

def test_wave_registered():
    assert 'wave' in GAIT_PRESETS
    assert GAIT_PRESETS['wave'] is WAVE
    assert WAVE.name == 'wave'


def test_wave_offsets_valid_and_complete():
    _assert_offsets_valid_and_complete(WAVE)
    assert WAVE.swing_duty == pytest.approx(1.0 / 6.0)


def test_wave_each_leg_swings():
    _assert_each_leg_swings(WAVE)


def test_wave_max_one_leg_in_air():
    """Wave: NIE mehr als 1 Bein gleichzeitig in der Luft (5 tragen)."""
    assert _max_in_air(WAVE) == 1


def test_wave_lift_order_back_to_front_per_side():
    """ZEITLICHE Hebe-Reihenfolge 3→2→1→4→5→6 (rechts hinten→vorne, dann links)."""
    assert _lift_order(WAVE) == [3, 2, 1, 4, 5, 6]


def test_wave_linear_max_plausible():
    _assert_linear_max(WAVE)
    # Wave ist langsamer als Tripod (längere Stützphase).
    assert _make_engine(WAVE).linear_max < _make_engine(
        GAIT_PRESETS['tripod']
    ).linear_max


def test_wave_walk_in_limits():
    # vx klar unter Wave-linear_max (~0.053 m/s).
    _assert_walk_in_limits(WAVE, vx=0.04)
