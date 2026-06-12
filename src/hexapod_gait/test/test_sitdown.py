"""
Tests für Block B1 — Hinsetz-/Abschalt-Sequenz in gait_engine.

Umkehrung des Aufstehens, drei Phasen + SAT-Idle:
  - Phase 1 (Füße raus): reuse STATE_REPOSITION mit vertauschten radii
    (radial_distance → standup_radial_distance), after=SITDOWN_LOWER.
  - STATE_SITDOWN_LOWER: reverse-kartesisch — Füße x/y fix @ standup_radial,
    body_height → body_height_start (Bauch am Boden).
  - STATE_SITDOWN_FLATTEN: Joint-Space-Lerp aller Joints zu rad 0.
  - STATE_SAT: bestromt, idle, hält rad 0.
Aufstehen aus SAT nutzt das bestehende start_cartesian_standup (start-pose-
agnostisch). cmd_vel wird in allen Sitdown-Phasen + SAT ignoriert.

Wertneutral: die Engine kennt keine konkreten radii/Höhen — sie kommen als
Params. Pure-Python (pytest, kein rclpy). Deckt §2 des Plans
project_finalization/B1_sitdown_plan.md ab.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, JointLimits, leg_fk
import pytest


_TRIPOD = GAIT_PRESETS['tripod']

# URDF-Limits (leg_changes S4): coxa ±0.415 / femur ±1.57 / tibia -0.28/+2.50
# (strikt aus config.py + hexapod.ros2_control.xacro — Memory two_joint_limit_sources).
_URDF_LIMITS = JointLimits(
    coxa_lower=-0.415, coxa_upper=0.415,
    femur_lower=-1.57, femur_upper=1.57,
    tibia_lower=-0.28, tibia_upper=2.50,
)

# Stance-Werte (mittel-Stance / breite Aufsteh-Pose, leg_changes S4).
_WALK_RADIAL = 0.145       # Walk-Pose (mittel-Stance)
_STANDUP_RADIAL = 0.17     # breite Aufsteh-/Hinsetz-Pose
_BH = -0.10                # Walk-Körperhöhe (mittel)
_BH_START = -0.0135        # Foot-z bei Bauch am Boden
_STEP_HEIGHT = 0.040

_REPOS_DUR = 2.0           # Phase 1 (reposition_cycle_time)
_LOWER_DUR = 3.0           # Phase 2 (sitdown_duration * lower_fraction)
_FLATTEN_DUR = 2.0         # Phase 3 (sitdown_duration * (1 - lower_fraction))

# Phasen-Grenzen auf der t-Achse (Start bei t=0 aus STANDING).
_T_REPOS_END = _REPOS_DUR
_T_LOWER_END = _REPOS_DUR + _LOWER_DUR
_T_FLATTEN_END = _REPOS_DUR + _LOWER_DUR + _FLATTEN_DUR


def _make_engine(
    walk_radial: float = _WALK_RADIAL,
    standup_radial: float = _STANDUP_RADIAL,
    body_height: float = _BH,
) -> GaitEngine:
    return GaitEngine(
        pattern=_TRIPOD,
        step_height=_STEP_HEIGHT,
        cycle_time=2.0,
        radial_distance=walk_radial,
        body_height=body_height,
        step_length_max=0.089,
        joint_limits={leg.name: _URDF_LIMITS for leg in HEXAPOD.legs},
        standup_radial_distance=standup_radial,
        reposition_cycle_time=_REPOS_DUR,
    )


def _start_sitdown(engine: GaitEngine) -> bool:
    return engine.start_sitdown(
        t=0.0,
        lower_duration=_LOWER_DUR,
        flatten_duration=_FLATTEN_DUR,
        body_height_start=_BH_START,
    )


def _samples(t0: float, t1: float, n: int = 19):
    """progress-Werte echt innerhalb (t0, t1) (kein Endpunkt)."""
    return [t0 + (i + 1) / (n + 1) * (t1 - t0) for i in range(n)]


def _drive(engine: GaitEngine, t_end: float, dt: float = 0.02):
    """
    Dicht ticken von 0 bis t_end (wie der 50-Hz-Node), letzte Angles zurück.

    Nötig, weil die Phasen-Übergänge lazy sind: jede Phase startet ihre Uhr beim
    Tick, der die Vorgänger-Grenze überschreitet. Ein direkter Sprung auf einen
    Grenz-Zeitpunkt löst nur EINEN Übergang pro Call aus — der Node ticked dicht.
    """
    angles = None
    n = int(round(t_end / dt))
    for i in range(1, n + 1):
        angles = engine.compute_joint_angles(i * dt)
    return angles


def _in_air_count(angles, body_height: float = _BH) -> int:
    n = 0
    for leg in HEXAPOD.legs:
        foot = leg_fk(*angles[leg.name], leg)
        if foot[2] > body_height + 1e-4:
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Trigger-Guards
# --------------------------------------------------------------------------- #

def test_sitdown_only_from_standing():
    """start_sitdown aus Nicht-STANDING-States = No-op (return False)."""
    engine = _make_engine()
    # WALKING
    engine.set_command(0.05, 0.0, 0.0, 0.0)
    assert engine.state == GaitEngine.STATE_WALKING
    assert _start_sitdown(engine) is False
    assert engine.state == GaitEngine.STATE_WALKING


def test_sitdown_starts_reposition_from_standing():
    """Aus STANDING: start_sitdown → REPOSITION (Phase 1, Füße raus)."""
    engine = _make_engine()
    assert engine.state == GaitEngine.STATE_STANDING
    assert _start_sitdown(engine) is True
    assert engine.state == GaitEngine.STATE_REPOSITION


def test_sitdown_rejects_nonpositive_durations():
    """lower/flatten_duration <= 0 → ValueError (Config-Bug)."""
    engine = _make_engine()
    with pytest.raises(ValueError):
        engine.start_sitdown(0.0, lower_duration=0.0, flatten_duration=1.0)
    with pytest.raises(ValueError):
        engine.start_sitdown(0.0, lower_duration=1.0, flatten_duration=-1.0)


# --------------------------------------------------------------------------- #
# Phase 1 — Reposition aus (Füße raus, rückwärts)
# --------------------------------------------------------------------------- #

def test_sitdown_phase1_widens_feet():
    """Phase 1: Füße von walk_radial nach standup_radial (raus), nicht rein."""
    engine = _make_engine()
    _start_sitdown(engine)
    # Endpose der Reposition (knapp vor Übergang) liegt auf standup_radial.
    angles = engine.compute_joint_angles(_T_REPOS_END * 0.999)
    for leg in HEXAPOD.legs:
        foot = leg_fk(*angles[leg.name], leg)
        assert foot[0] == pytest.approx(_STANDUP_RADIAL, abs=2e-3)


def test_sitdown_phase1_max_three_in_air():
    """Phase 1 Tripod: nie mehr als 3 Beine gleichzeitig in der Luft."""
    engine = _make_engine()
    _start_sitdown(engine)
    for t in _samples(0.0, _T_REPOS_END):
        angles = engine.compute_joint_angles(t)
        assert _in_air_count(angles) <= 3


def test_sitdown_phase1_both_groups_lift():
    """Beide Tripod-Gruppen heben in ihrer Hälfte tatsächlich ab."""
    engine = _make_engine()
    _start_sitdown(engine)
    a = engine.compute_joint_angles(0.25 * _REPOS_DUR)
    air_a = {
        leg.name for leg in HEXAPOD.legs
        if leg_fk(*a[leg.name], leg)[2] > _BH + 1e-4
    }
    assert air_a == {'leg_1', 'leg_3', 'leg_5'}
    b = engine.compute_joint_angles(0.75 * _REPOS_DUR)
    air_b = {
        leg.name for leg in HEXAPOD.legs
        if leg_fk(*b[leg.name], leg)[2] > _BH + 1e-4
    }
    assert air_b == {'leg_2', 'leg_4', 'leg_6'}


# --------------------------------------------------------------------------- #
# Phase 2 — Lower (Körper absenken, reverse-kartesisch)
# --------------------------------------------------------------------------- #

def test_sitdown_lower_xy_fixed_z_monotonic():
    """Phase 2: Füße x/y fix @ standup_radial, z steigt monoton zu bh_start."""
    engine = _make_engine()
    _start_sitdown(engine)
    dt = 0.02
    n = int(round(_T_FLATTEN_END / dt))
    prev_z = None
    saw_lower = False
    for i in range(1, n + 1):
        angles = engine.compute_joint_angles(i * dt)
        if engine.state != GaitEngine.STATE_SITDOWN_LOWER:
            continue
        saw_lower = True
        for leg in HEXAPOD.legs:
            foot = leg_fk(*angles[leg.name], leg)
            assert foot[0] == pytest.approx(_STANDUP_RADIAL, abs=2e-3)
            assert foot[1] == pytest.approx(0.0, abs=2e-3)
        z = leg_fk(*angles['leg_1'], HEXAPOD.legs[0])[2]
        if prev_z is not None:
            assert z >= prev_z - 1e-6
        prev_z = z
    assert saw_lower


# --------------------------------------------------------------------------- #
# Phase 3 — Flatten (Beine flach zu rad 0)
# --------------------------------------------------------------------------- #

def test_sitdown_flatten_ends_rad_zero_fallback():
    """Ohne rest_joints (Fallback): Endpose alle 18 Joints == rad 0."""
    engine = _make_engine()
    _start_sitdown(engine)  # rest_joints=None → Fallback rad 0
    angles = _drive(engine, _T_FLATTEN_END + 0.2)
    assert engine.state == GaitEngine.STATE_SAT
    for leg in HEXAPOD.legs:
        assert angles[leg.name] == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)


# Plausible „Beine hoch"-Spawn-Pose (femur hoch, tibia gebeugt), in-limit.
_SPAWN_POSE = {leg.name: (0.0, -0.4, 0.5) for leg in HEXAPOD.legs}


def test_sitdown_rest_pose_is_spawn_pose():
    """Mit rest_joints (Spawn-Pose): Phase 3 endet in der Spawn-Pose, nicht rad 0."""
    engine = _make_engine()
    engine.start_sitdown(
        t=0.0, lower_duration=_LOWER_DUR, flatten_duration=_FLATTEN_DUR,
        body_height_start=_BH_START, rest_joints=dict(_SPAWN_POSE),
    )
    angles = _drive(engine, _T_FLATTEN_END + 0.2)
    assert engine.state == GaitEngine.STATE_SAT
    for leg in HEXAPOD.legs:
        assert angles[leg.name] == pytest.approx(_SPAWN_POSE[leg.name], abs=1e-9)


def test_sat_holds_spawn_pose_indefinitely():
    """SAT hält die Spawn-Ruhe-Pose statisch (auch viel später)."""
    engine = _make_engine()
    engine.start_sitdown(
        t=0.0, lower_duration=_LOWER_DUR, flatten_duration=_FLATTEN_DUR,
        body_height_start=_BH_START, rest_joints=dict(_SPAWN_POSE),
    )
    _drive(engine, _T_FLATTEN_END + 0.2)
    angles = engine.compute_joint_angles(_T_FLATTEN_END + 50.0)
    for leg in HEXAPOD.legs:
        assert angles[leg.name] == pytest.approx(_SPAWN_POSE[leg.name], abs=1e-9)


def test_sitdown_rest_pose_path_in_limits():
    """Flatten-Lerp lower-end → Spawn-Pose bleibt in-limit (box-konvex)."""
    engine = _make_engine()
    engine.start_sitdown(
        t=0.0, lower_duration=_LOWER_DUR, flatten_duration=_FLATTEN_DUR,
        body_height_start=_BH_START, rest_joints=dict(_SPAWN_POSE),
    )
    _drive(engine, _T_FLATTEN_END + 0.2)  # IKError-frei (Lower) + Lerp in-limit
    assert engine.state == GaitEngine.STATE_SAT


def test_sitdown_flatten_stays_in_limits():
    """Flatten-Lerp bleibt box-konvex in-limit (jeder Joint in [min,max])."""
    engine = _make_engine()
    _start_sitdown(engine)
    dt = 0.02
    n = int(round((_T_FLATTEN_END + 0.2) / dt))
    saw_flatten = False
    for i in range(1, n + 1):
        angles = engine.compute_joint_angles(i * dt)
        if engine.state != GaitEngine.STATE_SITDOWN_FLATTEN:
            continue
        saw_flatten = True
        for leg in HEXAPOD.legs:
            c, f, ti = angles[leg.name]
            assert _URDF_LIMITS.coxa_lower <= c <= _URDF_LIMITS.coxa_upper
            assert _URDF_LIMITS.femur_lower <= f <= _URDF_LIMITS.femur_upper
            assert _URDF_LIMITS.tibia_lower <= ti <= _URDF_LIMITS.tibia_upper
    assert saw_flatten


# --------------------------------------------------------------------------- #
# Gesamt-Pfad + SAT
# --------------------------------------------------------------------------- #

def test_sitdown_full_path_in_limits():
    """Gesamter Hinsetz-Pfad (alle Phasen) ist limit-konform (kein IKError)."""
    engine = _make_engine()
    _start_sitdown(engine)
    _drive(engine, _T_FLATTEN_END + 0.2)  # wirft IKError bei Limit-Verletzung
    assert engine.state == GaitEngine.STATE_SAT


def test_sitdown_ends_in_sat():
    """Nach der ganzen Sequenz: Endzustand SAT, hält rad 0 (auch viel später)."""
    engine = _make_engine()
    _start_sitdown(engine)
    _drive(engine, _T_FLATTEN_END + 0.2)
    assert engine.state == GaitEngine.STATE_SAT
    angles = engine.compute_joint_angles(_T_FLATTEN_END + 100.0)
    assert engine.state == GaitEngine.STATE_SAT
    for leg in HEXAPOD.legs:
        assert angles[leg.name] == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)


def test_cmd_vel_ignored_in_sitdown_and_sat():
    """cmd_vel kippt keinen Sitdown-/SAT-State auf WALKING."""
    engine = _make_engine()
    _start_sitdown(engine)
    # Mitten in der Lower-Phase (dicht ticken bis LOWER erreicht)
    dt = 0.02
    n = int(round(_T_FLATTEN_END / dt))
    for i in range(1, n + 1):
        engine.compute_joint_angles(i * dt)
        if engine.state == GaitEngine.STATE_SITDOWN_LOWER:
            break
    assert engine.state == GaitEngine.STATE_SITDOWN_LOWER
    engine.set_command(0.05, 0.0, 0.0, i * dt)
    assert engine.state == GaitEngine.STATE_SITDOWN_LOWER
    # Weiter auf DERSELBEN t-Achse bis SAT ticken — NICHT _drive (das würde
    # die Zeit auf t=0 zurücksetzen und die Lower-Smoothstep-Rampe rückwärts
    # extrapolieren → out-of-reach Foot-Target; der enge leg_changes-Envelope
    # deckt das auf, der alte weite hat es maskiert).
    n_full = int(round((_T_FLATTEN_END + 0.2) / dt))
    for j in range(i + 1, n_full + 1):
        engine.compute_joint_angles(j * dt)
    assert engine.state == GaitEngine.STATE_SAT
    engine.set_command(0.05, 0.0, 0.0, _T_FLATTEN_END + 1.0)
    assert engine.state == GaitEngine.STATE_SAT


# --------------------------------------------------------------------------- #
# Aufstehen aus SAT (start-pose-agnostisch)
# --------------------------------------------------------------------------- #

def test_standup_from_sat_in_limits():
    """SAT (rad 0) → start_cartesian_standup: Pfad in-limit, endet STANDING."""
    engine = _make_engine()
    _start_sitdown(engine)
    _drive(engine, _T_FLATTEN_END + 0.2)
    assert engine.state == GaitEngine.STATE_SAT

    # Aufstehen aus der SAT-Pose (rad 0 je Bein) — wie der Node es täte.
    sat_joints = {leg.name: (0.0, 0.0, 0.0) for leg in HEXAPOD.legs}
    t0 = _T_FLATTEN_END
    standup_dur = 4.0
    engine.start_cartesian_standup(
        sat_joints, t=t0, duration=standup_dur,
        phase1_fraction=0.4, body_height_start=_BH_START,
    )
    assert engine.state == GaitEngine.STATE_CARTESIAN_STANDUP
    # Standup-Pfad in-limit
    for t in _samples(t0, t0 + standup_dur, n=40):
        engine.compute_joint_angles(t)
    # Nach dem Standup folgt die Reposition (radii unterscheiden sich) → bis Ende
    engine.compute_joint_angles(t0 + standup_dur)  # Übergang → REPOSITION
    assert engine.state == GaitEngine.STATE_REPOSITION
    # Reposition bis ans Ende treiben → STANDING
    end = engine.compute_joint_angles(t0 + standup_dur + _REPOS_DUR)
    assert engine.state == GaitEngine.STATE_STANDING
    for leg in HEXAPOD.legs:
        foot = leg_fk(*end[leg.name], leg)
        assert foot[0] == pytest.approx(_WALK_RADIAL, abs=2e-3)
        assert foot[2] == pytest.approx(_BH, abs=2e-3)


# --------------------------------------------------------------------------- #
# Wertneutralität + Regression
# --------------------------------------------------------------------------- #

def test_sitdown_value_neutral_other_radii():
    """Andere radii (0.14↔0.18) laufen generisch — kein Hardcode."""
    engine = _make_engine(walk_radial=0.14, standup_radial=0.18)
    assert _start_sitdown(engine) is True
    _drive(engine, _T_FLATTEN_END + 0.2)
    assert engine.state == GaitEngine.STATE_SAT


def test_default_reposition_unchanged_after_standup():
    """Regression: Standup ohne sitdown → Reposition → STANDING (after-Default)."""
    power_on_mid = {leg.name: (0.0, -0.4, 0.4) for leg in HEXAPOD.legs}
    engine = _make_engine()
    engine.start_cartesian_standup(
        power_on_mid, t=0.0, duration=4.0,
        phase1_fraction=0.4, body_height_start=_BH_START,
    )
    engine.compute_joint_angles(4.0)  # → REPOSITION (after=STANDING default)
    assert engine.state == GaitEngine.STATE_REPOSITION
    engine.compute_joint_angles(4.0 + _REPOS_DUR)  # → STANDING (nicht SITDOWN)
    assert engine.state == GaitEngine.STATE_STANDING
