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
from hexapod_gait.gait_patterns import GAIT_PRESETS, RIPPLE, TETRAPOD, WAVE
from hexapod_kinematics import HEXAPOD, JointLimits
import pytest


_RIGHT = {1, 2, 3}
_LEFT = {4, 5, 6}
# Reihen (fore-aft): vorne {1,6}, mitte {2,5}, hinten {3,4}.
_ROW = {1: 'front', 6: 'front', 2: 'mid', 5: 'mid', 3: 'rear', 4: 'rear'}

# URDF-Limits (leg_changes: coxa ±0.415 / femur ±1.57 / tibia -0.28/+2.50,
# strikt aus config.py + hexapod.ros2_control.xacro — Memory two_joint_limit_sources).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

# Walk-Pose (mittel-Stance, leg_changes S4), pattern-unabhängig.
_WALK_RADIAL = 0.145
_BH = -0.10
_STEP_HEIGHT = 0.040
_STEP_LENGTH_MAX = 0.03
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


def _air_sets_over_cycle(pattern):
    """Menge der in-der-Luft-Beine an jeder gesampelten Cycle-Phase."""
    return [frozenset(_swinging_legs(pattern, phi)) for phi in _sample_phases()]


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


# ============================ TETRAPOD =============================== #

def test_tetrapod_registered():
    assert 'tetrapod' in GAIT_PRESETS
    assert GAIT_PRESETS['tetrapod'] is TETRAPOD
    assert TETRAPOD.name == 'tetrapod'


def test_tetrapod_offsets_valid_and_complete():
    _assert_offsets_valid_and_complete(TETRAPOD)
    assert TETRAPOD.swing_duty == pytest.approx(1.0 / 3.0)


def test_tetrapod_each_leg_swings():
    _assert_each_leg_swings(TETRAPOD)


def test_tetrapod_max_two_in_air_diagonal_pair():
    """Immer genau ein DIAGONAL-Paar (2 Beine) in der Luft, 4 tragen."""
    pairs = {frozenset({1, 4}), frozenset({2, 5}), frozenset({3, 6})}
    for air in _air_sets_over_cycle(TETRAPOD):
        assert len(air) == 2
        assert air in pairs


def test_tetrapod_lift_order_diagonal_pairs():
    """Paare heben in Reihenfolge {1,4}→{2,5}→{3,6}."""
    assert _lift_order(TETRAPOD) == [1, 4, 2, 5, 3, 6]


def test_tetrapod_linear_max_plausible():
    _assert_linear_max(TETRAPOD)
    wave_lm = _make_engine(WAVE).linear_max
    tetra_lm = _make_engine(TETRAPOD).linear_max
    tripod_lm = _make_engine(GAIT_PRESETS['tripod']).linear_max
    assert wave_lm < tetra_lm < tripod_lm


def test_tetrapod_walk_in_limits():
    # vx unter Tetrapod-linear_max (~0.067 m/s).
    _assert_walk_in_limits(TETRAPOD, vx=0.05)


# ============================== RIPPLE =============================== #

def test_ripple_registered():
    assert 'ripple' in GAIT_PRESETS
    assert GAIT_PRESETS['ripple'] is RIPPLE
    assert RIPPLE.name == 'ripple'


def test_ripple_offsets_valid_and_complete():
    _assert_offsets_valid_and_complete(RIPPLE)
    assert RIPPLE.swing_duty == pytest.approx(1.0 / 3.0)


def test_ripple_each_leg_swings():
    _assert_each_leg_swings(RIPPLE)


def test_ripple_two_in_air_truly_diagonal():
    """
    Immer 2 Beine in der Luft, ECHT diagonal: verschiedene Seite UND Reihe.

    Nur „kontralateral" (verschiedene Seite) reicht nicht — beide Hinterbeine
    gleichzeitig (kontralateral, aber gleiche Reihe) lassen die Stütz-Marge auf
    ~7 mm einbrechen (B3.3-Analyse). Verschiedene Reihe verhindert das.
    """
    for air in _air_sets_over_cycle(RIPPLE):
        assert len(air) == 2
        assert len(air & _RIGHT) == 1 and len(air & _LEFT) == 1  # Seite
        rows = {_ROW[lid] for lid in air}
        assert len(rows) == 2, f'gleiche Reihe in der Luft: {air}'  # Reihe


def test_ripple_lift_order_diagonal_round():
    """Hebe-Reihenfolge 1→5→3→6→2→4 (echte Diagonalen, rundherum)."""
    assert _lift_order(RIPPLE) == [1, 5, 3, 6, 2, 4]


def test_ripple_linear_max_plausible():
    _assert_linear_max(RIPPLE)
    # gleiche swing_duty wie Tetrapod → gleiche linear_max.
    assert _make_engine(RIPPLE).linear_max == pytest.approx(
        _make_engine(TETRAPOD).linear_max
    )


def test_ripple_walk_in_limits():
    _assert_walk_in_limits(RIPPLE, vx=0.05)
