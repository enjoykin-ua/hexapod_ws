#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""

Was das Tool jetzt kann (zusammengefasst)

# Single-Check, alle 4 cmd_vel-Szenarien (default)
python3 tools/walking_envelope_check.py check --params-file X.yaml

# Single-Check, nur ein Szenario
python3 tools/walking_envelope_check.py check --params-file X.yaml --scenario sidestep

# 1D-Sweep (Höhe)
python3 tools/walking_envelope_check.py sweep

# 2D-Sweep (Höhe × step_height)
python3 tools/walking_envelope_check.py sweep --step-height-list "0.015,0.020,0.025"

# Preset für gewählte Höhe, alle 4 Szenarien grün + 10% Safety
python3 tools/walking_envelope_check.py recommend --body-height -0.07 --output my.yaml

# Plus Auto-Optimierung von step_height für max Walking-Speed
python3 tools/walking_envelope_check.py recommend --body-height -0.07 --optimize-step-height


================================================================================
Walking-Envelope-Check Tool
================================================================================

Offline-Werkzeug das prüft, ob ein gegebener gait_node-Parameter-Satz einen
kompletten Walking-Cycle durchläuft ohne kinematischen Konflikt. Spart das
manuelle Tuning in Gazebo: ohne Sim-Start in <2 Sekunden weißt du ob Deine
Werte funktionieren würden — und welcher Joint/Bein limitierend ist.

Pure Python, kein ROS-Runtime nötig — nutzt direkt hexapod_kinematics und
hexapod_gait. URDF-Joint-Limits werden via xacro aus der Stage-D-URDF
gelesen.

Konzept-Spec: ./walking_envelope_check.README.md

────────────────────────────────────────────────────────────────────────────────
WAS DAS TOOL PRÜFT (und was NICHT)
────────────────────────────────────────────────────────────────────────────────

PRÜFT (kinematisch):
- Stand-Pose erreichbar (Foot bei radial_distance, body_height passt zu IK)
- Walking-Trajectory pro Bein bleibt innerhalb URDF-Joint-Limits (Stage 0.6
  IK-Joint-Check)
- Foot-Position bleibt innerhalb Bein-Reichweite (L_femur + L_tibia)
- Für 4 cmd_vel-Szenarien (forward, sidestep, yaw, diagonal)

PRÜFT NICHT (gehört zu HW-Test / Phase 13):
- Servo-rad/s-Limits (= max-Drehgeschwindigkeit am Joint)
- Servo-Drehmoment unter Last (Stallstrom, mechanische Toleranz)
- ros2_control velocity-Limits aus controllers.yaml
- Body-Tilt-Stabilität / Kipp-Verhalten (kommt von Gazebo-Physik)

→ Wenn das Tool GREEN sagt, heißt das: kinematisch ok. Ob die Servos das
   schnell genug schaffen, sieht man erst auf HW (Stage E2 aufgebockt).

────────────────────────────────────────────────────────────────────────────────
WORKFLOW-EMPFEHLUNG
────────────────────────────────────────────────────────────────────────────────

1. **Quick-Check** existierender Preset:
       python3 tools/walking_envelope_check.py check \\
           --params-file src/hexapod_gait/config/presets/sim_walk.yaml
   → meldet GREEN / RED + welche cmd_vel-Szenarien problematisch

2. **Übersicht** über erlaubte Walking-Geschwindigkeit je nach Hexapod-Höhe:
       python3 tools/walking_envelope_check.py sweep
   → Tabelle: pro body_height der optimale radial_distance, max-step_length
     und resultierender linear_max (m/s)

3. **Fertiges Preset** für gewählte Höhe automatisch erzeugen:
       python3 tools/walking_envelope_check.py recommend \\
           --body-height -0.07 --output my_preset.yaml
   → YAML-Datei ready zum Laden via gait.launch.py params_file:=…

────────────────────────────────────────────────────────────────────────────────
SUB-COMMANDS
────────────────────────────────────────────────────────────────────────────────

  check    — Single-Config-Check für gegebene Parameter
  sweep    — Übersichts-Tabelle (Höhe optional × step_height)
  recommend — YAML-Preset für gewählte Höhe, alle 4 Szenarien grün

────────────────────────────────────────────────────────────────────────────────
CMD_VEL-SZENARIEN (was getestet wird)
────────────────────────────────────────────────────────────────────────────────

Bei "check --scenario all" + "recommend" werden vier Bewegungs-Szenarien
durchgespielt. Jedes belastet eine andere Stelle der IK-Envelope:

  forward   (linear.x = linear_max)   — stresst Tibia (Knie-Knick)
  sidestep  (linear.y = linear_max)   — stresst Coxa-Range, v.a. Mittel-Beine
  yaw       (angular.z entspr.)       — stresst Coxa-Range, v.a. Eck-Beine
  diagonal  (linear.x+y = linear_max) — kombinierte Stress, oft worst-case

Tests werden immer bei der MAX-cmd_vel-Magnitude durchgeführt (= linear_max).
Wenn der Test bei max grün ist, ist er automatisch bei jedem kleineren
cmd_vel auch grün (Foot-Trajectorie skaliert linear). Daher keine separate
Magnitude-Sweep nötig.

────────────────────────────────────────────────────────────────────────────────
BEISPIELE
────────────────────────────────────────────────────────────────────────────────

# Einfacher Check eines YAML-Presets, alle 4 Szenarien:
  python3 tools/walking_envelope_check.py check \\
      --params-file src/hexapod_gait/config/presets/sim_walk.yaml

# Check direkt mit Werten:
  python3 tools/walking_envelope_check.py check \\
      --radial 0.30 --body-height -0.075 \\
      --step-length 0.03 --step-height 0.02

# Nur forward-walking (schneller, weniger streng):
  python3 tools/walking_envelope_check.py check \\
      --params-file my.yaml --scenario forward

# Übersichts-Sweep über Höhen (1D):
  python3 tools/walking_envelope_check.py sweep

# 2D-Sweep über Höhe × step_height:
  python3 tools/walking_envelope_check.py sweep \\
      --step-height-list 0.015,0.020,0.025,0.030

# Empfehlung für eine bestimmte Höhe (alle 4 Szenarien grün, 10% Reserve):
  python3 tools/walking_envelope_check.py recommend \\
      --body-height -0.07 --output my_preset.yaml

# Empfehlung mit Auto-Optimierung von step_height (max Walking-Speed):
  python3 tools/walking_envelope_check.py recommend \\
      --body-height -0.07 --optimize-step-height

────────────────────────────────────────────────────────────────────────────────
VORAUSSETZUNGEN
────────────────────────────────────────────────────────────────────────────────

  cd ~/hexapod_ws
  colcon build  # falls noch nicht
  source install/setup.bash
  python3 tools/walking_envelope_check.py …

────────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import parse_joint_limits_from_urdf
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import (
    base_to_leg_frame,
    HEXAPOD,
    IKError,
    JointLimits,
    leg_ik,
    leg_to_base_frame,
    rotate_xy,
)


# Default workspace paths — adjust if the script is moved.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_URDF_XACRO = (
    _REPO_ROOT / 'src/hexapod_description/urdf/hexapod.urdf.xacro')


@dataclass
class GaitParams:
    """Subset of gait_node-params that the envelope-check cares about."""

    radial_distance: float
    body_height: float
    step_length_max: float
    step_height: float
    cycle_time: float = 2.0
    gait_pattern: str = 'tripod'

    @classmethod
    def from_yaml(cls, path: Path) -> 'GaitParams':
        with open(path) as f:
            data = yaml.safe_load(f)
        params = data.get('/gait_node', {}).get('ros__parameters', {})
        return cls(
            radial_distance=float(params.get('radial_distance', 0.30)),
            body_height=float(params.get('body_height', -0.075)),
            step_length_max=float(params.get('step_length_max', 0.03)),
            step_height=float(params.get('step_height', 0.02)),
            cycle_time=float(params.get('cycle_time', 2.0)),
            gait_pattern=str(params.get('gait_pattern', 'tripod')),
        )


@dataclass
class CheckResult:
    """Outcome of a single-config envelope check."""

    ok: bool
    linear_max: float
    per_leg_min: dict[str, tuple[float, float, float]]
    per_leg_max: dict[str, tuple[float, float, float]]
    failures: list[dict]  # one entry per failing tick
    first_failure: dict | None
    scenario: str = 'forward'  # which cmd_vel scenario was simulated
    # H1.1 — Margen-Report: minimaler Abstand zum URDF-Limit über den ganzen
    # Lauf, pro Joint-Typ (rad). None = alter Aufrufer ohne Margen-Tracking.
    min_margins: dict[str, float] | None = None
    worst_margin: dict | None = None  # {'joint','leg','margin','tick'}
    # engine-check: Margen der Sequenz-Phasen (Sitdown/Switch) — NUR
    # informativ; die min_margin-Schwelle gilt für die Walk-Phasen (die
    # Sequenzen fahren bewusst grenznah und sind HW-bewährt, z. B. Sitdown-
    # Flatten Femur ~0.07 rad — sie werden auf IKError geprüft, nicht auf Marge).
    seq_min_margins: dict[str, float] | None = None
    # check: Margen der Leveling-Ecken — informativ; die min_margin-Schwelle
    # gilt für den NOMINALEN Pfad. Begründung: der Engine-Fallback degradiert
    # bei knappen Ecken sanft (weniger Leveling), das ist kein Freeze-Risiko —
    # die Ecken müssen nur in-limit sein (sonst failure 'leveling_corner').
    lev_min_margins: dict[str, float] | None = None
    # Anteil der (Tick × Ecke)-Prüfungen, die in-limit sind (1.0 = volle
    # Leveling-Amplitude überall fallback-frei anwendbar). Kein Hard-Fail:
    # schon der heutige validierte tief-Modus schafft die 4°-Voll-Ecken am
    # Swing-Apex nicht (3a-Befund „combined ~2°, Apex bindet") — dafür
    # existiert der Engine-Degradations-Fallback. Die Coverage dient dem
    # VERGLEICH neuer Zellen gegen die heutigen.
    lev_coverage: float | None = None


_JOINT_TYPES = ('coxa', 'femur', 'tibia')


class _MarginTracker:
    """Min-Abstand jedes Joint-Typs zum URDF-Limit über einen Lauf (H1.1)."""

    def __init__(self, joint_limits: dict[str, JointLimits]):
        self._limits = joint_limits
        self.min_margins = {j: math.inf for j in _JOINT_TYPES}
        self.worst: dict | None = None

    def update(self, angles: dict, tick: int, tag: str = '') -> None:
        """Gelenkwinkel eines Ticks einpflegen (alle 6 Beine × 3 Joints)."""
        for leg_name, a in angles.items():
            lim = self._limits.get(leg_name)
            if lim is None:
                continue
            bounds = (
                ('coxa', a[0], lim.coxa_lower, lim.coxa_upper),
                ('femur', a[1], lim.femur_lower, lim.femur_upper),
                ('tibia', a[2], lim.tibia_lower, lim.tibia_upper),
            )
            for joint, val, lo, hi in bounds:
                margin = min(val - lo, hi - val)
                if margin < self.min_margins[joint]:
                    self.min_margins[joint] = margin
                    if self.worst is None or margin < self.worst['margin']:
                        self.worst = {
                            'joint': joint, 'leg': leg_name,
                            'margin': margin, 'tick': tick, 'phase': tag,
                        }

    @property
    def overall(self) -> float:
        return min(self.min_margins.values())


def _leveling_corner_offsets(leveling_deg: float) -> list[tuple[float, float]]:
    """8 Worst-Case-(roll,pitch)-Ecken für eine gegebene Leveling-Amplitude."""
    d = math.radians(leveling_deg)
    dd = d / math.sqrt(2.0)
    return [
        (+d, 0.0), (-d, 0.0), (0.0, +d), (0.0, -d),
        (+dd, +dd), (+dd, -dd), (-dd, +dd), (-dd, -dd),
    ]


def _leveled_ik_fallback_free(
    targets: dict, roll: float, pitch: float,
    joint_limits: dict[str, JointLimits],
) -> dict:
    """
    Exakt der Engine-Stellpfad ``_leveled_ik_at`` — aber OHNE den Degradations-
    Fallback von ``_compute_leveled_ik`` (der skaliert die Korrektur bei IKError
    still herunter → ein Check darüber wäre blind). Wirft IKError, wenn die
    volle Rotation nicht in-limit geht.
    """
    angles = {}
    for leg in HEXAPOD.legs:
        base_pt = leg_to_base_frame(targets[leg.name], leg)
        rot = rotate_xy(base_pt, roll, pitch)
        leg_pt = base_to_leg_frame(rot, leg)
        angles[leg.name] = leg_ik(*leg_pt, leg, joint_limits.get(leg.name))
    return angles


# cmd_vel scenarios that stress different parts of the IK envelope.
# (linear_x_scale, linear_y_scale, omega_z_scale) — scaled by linear_max.
# Names match the per-axis maximum stress: forward exercises tibia,
# sidestep exercises coxa (esp. mid-legs), yaw exercises coxa range
# on outer legs, diagonal combines forward+sidestep.
CMD_VEL_SCENARIOS: dict[str, tuple[float, float, float]] = {
    'forward':  (+1.0, 0.0, 0.0),
    'sidestep': (0.0, +1.0, 0.0),
    'yaw':      (0.0, 0.0, +1.0),  # omega-z scaled, separate from linear
    'diagonal': (+0.7071, +0.7071, 0.0),  # 45° forward+side
}


# ---------------------------------------------------------------------------
# URDF + limits loading
# ---------------------------------------------------------------------------

def load_joint_limits(urdf_xacro_path: Path) -> dict[str, JointLimits]:
    """Run xacro on the given file and parse joint limits per leg."""
    if not urdf_xacro_path.exists():
        raise FileNotFoundError(f'URDF xacro not found: {urdf_xacro_path}')
    try:
        urdf_xml = subprocess.check_output(
            ['xacro', str(urdf_xacro_path)], text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'xacro failed for {urdf_xacro_path}: {e}') from e
    limits = parse_joint_limits_from_urdf(urdf_xml)
    if len(limits) != 6:
        raise RuntimeError(
            f'expected joint limits for 6 legs, got {len(limits)} — '
            f'URDF parse issue?')
    return limits


# ---------------------------------------------------------------------------
# Single-config check (Mode A)
# ---------------------------------------------------------------------------

def check_envelope(
    gait_params: GaitParams,
    joint_limits: dict[str, JointLimits],
    scenario: str = 'forward',
    ticks_per_cycle: int = 100,
    min_margin: float = 0.0,
    leveling_deg: float = 0.0,
    s4_floor: float = 0.0,
) -> CheckResult:
    """
    Simulate one full gait cycle with a given cmd_vel scenario and
    check all 6 legs' IK against joint limits + reach cone.

    scenario: key from CMD_VEL_SCENARIOS. Forward, sidestep, yaw, diagonal
              stress different parts of the IK envelope; pick "forward"
              for the classic vorwärts-walking check or iterate over all
              scenarios via check_envelope_all_scenarios().

    H1.1 — die Anti-Optimismus-Erweiterungen (Defaults = altes Verhalten):
    ticks_per_cycle: jetzt 100 (= reale tick_rate 50 Hz × cycle 2 s).
    min_margin:  GREEN nur, wenn ALLE Joints über den ganzen Lauf mindestens
                 diesen Abstand (rad) zum URDF-Limit halten. 0.0 = nur
                 in-limit (altes, binäres Verhalten). Faustregel Femur-Rand:
                 0.10–0.15 rad.
    leveling_deg: > 0 prüft zusätzlich pro Tick die 8 Worst-Case-Leveling-
                 Ecken (±deg roll/pitch + Diagonalen) **fallback-frei** —
                 der Engine-Degradations-Fallback würde still herunterskalieren
                 und den Check blenden. 4.0 = Walking-Clamp.
    s4_floor:    > 0 aktiviert den ECHTEN adaptiven Touchdown-Pfad (S4-2) mit
                 dieser max_extra_depth und ohne Kontakte → jeder Stance-Fuß
                 probt bis body_height − s4_floor (der reale Terrain-Worst-Case).
    """
    if gait_params.gait_pattern not in GAIT_PRESETS:
        raise ValueError(
            f'unknown gait_pattern {gait_params.gait_pattern!r}; '
            f'available: {sorted(GAIT_PRESETS.keys())}')
    if scenario not in CMD_VEL_SCENARIOS:
        raise ValueError(
            f'unknown cmd_vel scenario {scenario!r}; '
            f'available: {sorted(CMD_VEL_SCENARIOS.keys())}')

    engine = GaitEngine(
        pattern=GAIT_PRESETS[gait_params.gait_pattern],
        step_height=gait_params.step_height,
        cycle_time=gait_params.cycle_time,
        radial_distance=gait_params.radial_distance,
        body_height=gait_params.body_height,
        step_length_max=gait_params.step_length_max,
        joint_limits=joint_limits,
    )
    # H1.1: S4-Worst-Case — echter adaptiver Touchdown-Pfad, keine Kontakte
    # gesetzt → jeder Stance-Fuß probt im Suchfenster bis body_height − s4_floor.
    if s4_floor > 0.0:
        engine.adaptive_touchdown_enable = True
        engine.touchdown_max_extra_depth = s4_floor

    # Translate scenario into a cmd_vel triple. linear_max already
    # accounts for swing_duty + cycle_time. For yaw we scale omega so the
    # outermost mount sees the same tangential leg speed as linear_max.
    lin_x_scale, lin_y_scale, omega_z_scale = CMD_VEL_SCENARIOS[scenario]
    linear_max = engine.linear_max
    cmd_v_x = lin_x_scale * linear_max
    cmd_v_y = lin_y_scale * linear_max
    # outer-most mount distance (rough; HEXAPOD leg mounts at body_length/2)
    max_mount_radius = 0.105  # body_length/2 of 0.175 + a small fudge
    cmd_omega_z = omega_z_scale * (linear_max / max_mount_radius)

    # Drive engine into STATE_WALKING and sweep ≥1 full cycle. We sample
    # 2 cycles to make sure both swing and stance halves of every leg are
    # exercised (tripod phase offsets); 50 ticks/cycle is plenty for the
    # smooth Bezier trajectory.
    n_ticks = ticks_per_cycle * 2
    dt = gait_params.cycle_time / ticks_per_cycle

    per_leg_min: dict[str, list[float]] = {
        leg.name: [math.inf] * 3 for leg in HEXAPOD.legs
    }
    per_leg_max: dict[str, list[float]] = {
        leg.name: [-math.inf] * 3 for leg in HEXAPOD.legs
    }
    failures: list[dict] = []

    margins = _MarginTracker(joint_limits)
    lev_margins = _MarginTracker(joint_limits)
    lev_offsets = (
        _leveling_corner_offsets(leveling_deg) if leveling_deg > 0.0 else []
    )
    lev_checked = 0
    lev_ok = 0

    for tick in range(n_ticks + 1):
        t = tick * dt
        engine.set_command(cmd_v_x, cmd_v_y, cmd_omega_z, t)
        try:
            angles = engine.compute_joint_angles(t)
        except IKError as exc:
            msg = str(exc)
            failures.append({
                'tick': tick,
                'time': t,
                'reason': 'joint_limit' if 'joint limit' in msg else 'out_of_reach',
                'message': msg,
            })
            continue
        margins.update(angles, tick)
        for leg in HEXAPOD.legs:
            a = angles[leg.name]
            for i in range(3):
                if a[i] < per_leg_min[leg.name][i]:
                    per_leg_min[leg.name][i] = a[i]
                if a[i] > per_leg_max[leg.name][i]:
                    per_leg_max[leg.name][i] = a[i]

        # H1.1: Worst-Case-Leveling-Ecken auf DENSELBEN Fuß-Targets,
        # fallback-frei (siehe _leveled_ik_fallback_free-Docstring).
        for roll, pitch in lev_offsets:
            targets = engine.compute_foot_targets(t)
            lev_checked += 1
            try:
                lev_angles = _leveled_ik_fallback_free(
                    targets, roll, pitch, joint_limits)
            except IKError:
                # KEIN failure: der Engine-Fallback degradiert hier sanft
                # (weniger Leveling); die Ecke zählt nur gegen die Coverage.
                continue
            lev_ok += 1
            lev_margins.update(lev_angles, tick, tag='leveling')

    # H1.1: Margen-Schwelle — Unterschreitung ist ein eigener Failure-Grund
    # (ok bleibt "len(failures) == 0", Report zeigt Ort + Wert).
    if min_margin > 0.0 and margins.overall < min_margin:
        w = margins.worst or {}
        failures.append({
            'tick': w.get('tick', -1),
            'time': -1.0,
            'reason': 'margin_below_threshold',
            'message': (
                f'min joint margin {margins.overall:.4f} rad '
                f'({w.get("joint", "?")} {w.get("leg", "?")}'
                f'{" @" + w["phase"] if w.get("phase") else ""}) '
                f'< required {min_margin:.4f} rad'
            ),
        })

    return CheckResult(
        ok=(len(failures) == 0),
        linear_max=engine.linear_max,
        per_leg_min={k: tuple(v) for k, v in per_leg_min.items()},
        per_leg_max={k: tuple(v) for k, v in per_leg_max.items()},
        failures=failures,
        first_failure=failures[0] if failures else None,
        scenario=scenario,
        min_margins=dict(margins.min_margins),
        worst_margin=margins.worst,
        lev_min_margins=(
            dict(lev_margins.min_margins) if lev_offsets else None),
        lev_coverage=(lev_ok / lev_checked if lev_checked else None),
    )


def check_envelope_all_scenarios(
    gait_params: GaitParams,
    joint_limits: dict[str, JointLimits],
    **check_kwargs,
) -> dict[str, CheckResult]:
    """Run check_envelope for every CMD_VEL_SCENARIOS entry. Returns dict."""
    return {
        name: check_envelope(
            gait_params, joint_limits, scenario=name, **check_kwargs)
        for name in CMD_VEL_SCENARIOS
    }


# ---------------------------------------------------------------------------
# H1.1 — engine-check: Transition-Coverage auf der echten Engine
# ---------------------------------------------------------------------------

def engine_transition_check(
    gait_params: GaitParams,
    joint_limits: dict[str, JointLimits],
    min_margin: float = 0.10,
    s4_floor: float = 0.0,
    switch_to: tuple[float, float, float] | None = None,
    switch_step_height: float = 0.025,
    ticks_per_cycle: int = 100,
) -> CheckResult:
    """
    Die Übergänge prüfen, die ``check_envelope`` (steady-state) nicht sieht —
    dort trat der dokumentierte Stance-Modi-Fehler auf („Tool GREEN, echter
    Engine-Pfad fehlert"). Phasen:

    A) WALKING-Start bei mehreren Phasenlagen (mid-cycle-Einstieg),
    B) Richtungswechsel mitten im Lauf (forward→sidestep→yaw→diagonal ohne
       Stopp) + STOPPING-Settle bis STANDING,
    C) Stance-Switch hin + Lauf im Zielmodus + zurück (``switch_to`` =
       (radial, body_height, step_height); prüft den Radius-Wechsel!),
    D) Sitdown-Kette (Reposition→Lower→Flatten→SAT) + der Post-Standup-
       Reposition-Pfad (standup_radial → radial). Der kartesische Standup
       selbst ist modus-unabhängig (immer standup_radial + power_on-Pose)
       und bleibt beim ``standup_envelope_check``.

    Margen werden über ALLE Phasen getrackt; ``min_margin`` (Default 0.10 rad
    — dieses Gate ist neu, keine Back-Compat-Last) gilt wie in check_envelope.
    ``s4_floor`` wirkt in den WALKING-Phasen (echter S4-Probe-Pfad).
    """
    dt = gait_params.cycle_time / ticks_per_cycle
    cy = ticks_per_cycle
    failures: list[dict] = []
    margins = _MarginTracker(joint_limits)          # Walk-Phasen (Schwelle)
    seq_margins = _MarginTracker(joint_limits)      # Sequenzen (informativ)

    def _is_sequence_tag(tag: str) -> bool:
        return tag.startswith('D:') or tag.startswith('C:switch')

    def new_engine() -> GaitEngine:
        e = GaitEngine(
            pattern=GAIT_PRESETS[gait_params.gait_pattern],
            step_height=gait_params.step_height,
            cycle_time=gait_params.cycle_time,
            radial_distance=gait_params.radial_distance,
            body_height=gait_params.body_height,
            step_length_max=gait_params.step_length_max,
            joint_limits=joint_limits,
        )
        if s4_floor > 0.0:
            e.adaptive_touchdown_enable = True
            e.touchdown_max_extra_depth = s4_floor
        return e

    def run(engine: GaitEngine, t0: float, n: int, tag: str,
            cmd: tuple[float, float, float] | None = None) -> float:
        """n Ticks fahren; cmd (falls gesetzt) jeden Tick anlegen. Returns t."""
        t = t0
        for _ in range(n):
            if cmd is not None:
                engine.set_command(cmd[0], cmd[1], cmd[2], t)
            try:
                angles = engine.compute_joint_angles(t)
            except IKError as exc:
                failures.append({
                    'tick': int(t / dt), 'time': t,
                    'reason': 'joint_limit' if 'joint limit' in str(exc)
                    else 'out_of_reach',
                    'message': f'[{tag}] {exc}',
                })
            else:
                tracker = seq_margins if _is_sequence_tag(tag) else margins
                tracker.update(angles, int(t / dt), tag=tag)
            t += dt
        return t

    def settle_to_standing(engine: GaitEngine, t0: float, tag: str) -> float:
        """cmd=0 anlegen und bis STANDING ticken (cap 3 Zyklen)."""
        t = run(engine, t0, 1, tag, cmd=(0.0, 0.0, 0.0))
        cap = 3 * cy
        while engine.state != GaitEngine.STATE_STANDING and cap > 0:
            t = run(engine, t, 1, tag)
            cap -= 1
        if engine.state != GaitEngine.STATE_STANDING:
            failures.append({
                'tick': int(t / dt), 'time': t,
                'reason': 'no_settle',
                'message': f'[{tag}] engine never settled to STANDING '
                           f'(state={engine.state})',
            })
        return t

    def fwd(engine: GaitEngine) -> tuple[float, float, float]:
        lm = engine.linear_max
        return (lm, 0.0, 0.0)

    # --- Phase A: WALKING-Start bei mehreren Phasenlagen --------------------
    for frac in (0.0, 0.13, 0.37, 0.61, 0.87):
        e = new_engine()
        t = run(e, 0.0, max(1, int(frac * cy)), 'A:standing')  # STANDING-Vorlauf
        t = run(e, t, 2 * cy, f'A:start@{frac:.2f}', cmd=fwd(e))
        settle_to_standing(e, t, f'A:settle@{frac:.2f}')

    # --- Phase B: Richtungswechsel mitten im Lauf ---------------------------
    e = new_engine()
    lm = e.linear_max
    max_mount_radius = 0.105
    t = run(e, 0.0, int(1.5 * cy), 'B:forward', cmd=(lm, 0.0, 0.0))
    t = run(e, t, cy, 'B:sidestep', cmd=(0.0, lm, 0.0))
    t = run(e, t, cy, 'B:yaw', cmd=(0.0, 0.0, lm / max_mount_radius))
    t = run(e, t, cy, 'B:diagonal', cmd=(0.7071 * lm, 0.7071 * lm, 0.0))
    settle_to_standing(e, t, 'B:settle')

    # --- Phase C: Stance-Switch hin / Lauf im Zielmodus / zurück ------------
    if switch_to is not None:
        r2, bh2, sh2 = switch_to
        e = new_engine()
        t = run(e, 0.0, 5, 'C:standing')
        if not e.start_stance_switch(t, r2, bh2, sh2, duration=3.0,
                                     switch_step_height=switch_step_height):
            failures.append({'tick': 0, 'time': t, 'reason': 'switch_refused',
                             'message': '[C] start_stance_switch returned '
                                        'False (state != STANDING?)'})
        cap = int(3.0 / dt) + 2 * cy
        while e.state != GaitEngine.STATE_STANDING and cap > 0:
            t = run(e, t, 1, 'C:switch_to')
            cap -= 1
        t = run(e, t, 2 * cy, 'C:walk_target_mode', cmd=fwd(e))
        t = settle_to_standing(e, t, 'C:settle_target')
        e.start_stance_switch(
            t, gait_params.radial_distance, gait_params.body_height,
            gait_params.step_height, duration=3.0,
            switch_step_height=switch_step_height)
        cap = int(3.0 / dt) + 2 * cy
        while e.state != GaitEngine.STATE_STANDING and cap > 0:
            t = run(e, t, 1, 'C:switch_back')
            cap -= 1

    # --- Phase D: Sitdown-Kette + Post-Standup-Reposition -------------------
    e = new_engine()
    t = run(e, 0.0, 5, 'D:standing')
    if e.start_sitdown(t, lower_duration=2.0, flatten_duration=2.0):
        cap = int((e.reposition_cycle_time + 2.0 + 2.0) / dt) + 2 * cy
        while e.state != GaitEngine.STATE_SAT and cap > 0:
            t = run(e, t, 1, 'D:sitdown')
            cap -= 1
        if e.state != GaitEngine.STATE_SAT:
            failures.append({'tick': int(t / dt), 'time': t,
                             'reason': 'no_sat',
                             'message': f'[D] sitdown never reached SAT '
                                        f'(state={e.state})'})
    else:
        failures.append({'tick': 0, 'time': t, 'reason': 'sitdown_refused',
                         'message': '[D] start_sitdown returned False'})
    # Post-Standup-Pfad: Reposition standup_radial → Modus-radial.
    e = new_engine()
    t = run(e, 0.0, 5, 'D:standing2')
    e.start_reposition(t)   # Defaults: standup_radial → radial_distance
    cap = int(e.reposition_cycle_time / dt) + 2 * cy
    while e.state != GaitEngine.STATE_STANDING and cap > 0:
        t = run(e, t, 1, 'D:reposition')
        cap -= 1

    if min_margin > 0.0 and margins.overall < min_margin:
        w = margins.worst or {}
        failures.append({
            'tick': w.get('tick', -1), 'time': -1.0,
            'reason': 'margin_below_threshold',
            'message': (
                f'min joint margin {margins.overall:.4f} rad '
                f'({w.get("joint", "?")} {w.get("leg", "?")} '
                f'@{w.get("phase", "?")}) < required {min_margin:.4f} rad'
            ),
        })

    empty = {leg.name: (0.0, 0.0, 0.0) for leg in HEXAPOD.legs}
    return CheckResult(
        ok=(len(failures) == 0),
        linear_max=GaitEngine(
            pattern=GAIT_PRESETS[gait_params.gait_pattern],
            step_height=gait_params.step_height,
            cycle_time=gait_params.cycle_time,
            radial_distance=gait_params.radial_distance,
            body_height=gait_params.body_height,
            step_length_max=gait_params.step_length_max,
            joint_limits=joint_limits,
        ).linear_max,
        per_leg_min=empty, per_leg_max=empty,
        failures=failures,
        first_failure=failures[0] if failures else None,
        scenario='transitions',
        min_margins=dict(margins.min_margins),
        worst_margin=margins.worst,
        seq_min_margins=dict(seq_margins.min_margins),
    )


def format_check_result(
    result: CheckResult,
    gait_params: GaitParams,
    joint_limits: dict[str, JointLimits],
) -> str:
    """Human-readable single-config report."""
    lines: list[str] = []
    lines.append('=== Walking-Envelope Check ===')
    lines.append(
        f'gait params: radial={gait_params.radial_distance:.3f}, '
        f'body_height={gait_params.body_height:.3f}, '
        f'step_length_max={gait_params.step_length_max:.3f}, '
        f'step_height={gait_params.step_height:.3f}, '
        f'cycle_time={gait_params.cycle_time:.2f}, '
        f'pattern={gait_params.gait_pattern}')
    lines.append(f'linear_max: {result.linear_max:.4f} m/s '
                 f'(scenario={result.scenario})')
    lines.append('')
    if result.scenario == 'transitions':
        # engine-check: per-leg-Hülle nicht getrackt (Margen-Report unten
        # ist die Aussage) — Block überspringen.
        return _format_check_tail(result, lines)
    lines.append('Per-leg rad min .. max (3 sig fig), '
                 'limits and reserve to closer side:')
    lines.append(
        f'  {"leg":7} {"joint":5} {"min":>7} {"max":>7}    '
        f'{"lower":>7} {"upper":>7}   reserve')
    joint_names = ('coxa', 'femur', 'tibia')
    for leg in HEXAPOD.legs:
        jl = joint_limits[leg.name]
        limits_per_joint = [
            (jl.coxa_lower, jl.coxa_upper),
            (jl.femur_lower, jl.femur_upper),
            (jl.tibia_lower, jl.tibia_upper),
        ]
        for i, joint_name in enumerate(joint_names):
            rmin = result.per_leg_min[leg.name][i]
            rmax = result.per_leg_max[leg.name][i]
            lo, hi = limits_per_joint[i]
            reserve_low = rmin - lo
            reserve_high = hi - rmax
            tightest = min(reserve_low, reserve_high)
            marker = '  ⚠ tight' if tightest < 0.05 else ''
            lines.append(
                f'  {leg.name:7} {joint_name:5} '
                f'{rmin:+7.3f} {rmax:+7.3f}    '
                f'{lo:+7.3f} {hi:+7.3f}   {tightest:+.3f}{marker}'
            )
    lines.append('')
    return _format_check_tail(result, lines)


def _format_check_tail(result: CheckResult, lines: list[str]) -> str:
    """Gemeinsamer Report-Schluss: Margen-Sektion (H1.1) + Result-Zeile."""
    if result.min_margins is not None:
        parts = []
        for joint in _JOINT_TYPES:
            m = result.min_margins[joint]
            m_s = f'{m:.3f}' if math.isfinite(m) else 'n/a'
            parts.append(f'{joint} {m_s}')
        lines.append('min joint margins [rad]: ' + ' | '.join(parts))
        if result.worst_margin:
            w = result.worst_margin
            deg = math.degrees(w['margin'])
            lines.append(
                f'  tightest: {w["joint"]} @ {w["leg"]} '
                f'(tick {w["tick"]}{", " + w["phase"] if w.get("phase") else ""}'
                f') = {w["margin"]:.4f} rad ({deg:.1f}°)')
        if result.lev_min_margins is not None:
            parts = []
            for joint in _JOINT_TYPES:
                m = result.lev_min_margins[joint]
                m_s = f'{m:.3f}' if math.isfinite(m) else 'n/a'
                parts.append(f'{joint} {m_s}')
            cov = (
                f'{result.lev_coverage * 100.0:.1f}%'
                if result.lev_coverage is not None else 'n/a')
            lines.append(
                f'leveling corners: coverage {cov} in-limit '
                '(kein Gate — Fallback degradiert sanft); margins [rad]: '
                + ' | '.join(parts))
        if result.seq_min_margins is not None:
            parts = []
            for joint in _JOINT_TYPES:
                m = result.seq_min_margins[joint]
                m_s = f'{m:.3f}' if math.isfinite(m) else 'n/a'
                parts.append(f'{joint} {m_s}')
            lines.append(
                'sequence margins [rad] (informativ, ohne Schwelle — '
                'Sitdown/Switch fahren bewusst grenznah): '
                + ' | '.join(parts))
        lines.append('')

    if result.ok:
        lines.append('Result: ✓ GREEN — all 6 legs within IK + joint limits '
                     'across the cycle.')
    else:
        f = result.first_failure
        lines.append(f'Result: ❌ RED — {len(result.failures)} failing tick(s).')
        lines.append(f'  first failure: tick={f["tick"]} t={f["time"]:.3f}s '
                     f'reason={f["reason"]}')
        lines.append(f'  message: {f["message"]}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Height-Sweep (Mode B)
# ---------------------------------------------------------------------------

@dataclass
class SweepRow:
    body_height: float
    step_height: float
    radial_distance: float | None
    max_step_length: float | None
    linear_max: float | None
    bottleneck: str


def _all_scenarios_green(
    gp: GaitParams,
    joint_limits: dict[str, JointLimits],
) -> tuple[bool, str]:
    """Run ALL 4 scenarios; return (all_green, first_failing_reason_else_'')."""
    for scenario in CMD_VEL_SCENARIOS:
        r = check_envelope(gp, joint_limits, scenario=scenario)
        if not r.ok:
            return False, f'{scenario}:{r.first_failure["reason"]}'
    return True, ''


def _find_max_step_length(
    gait_params_template: GaitParams,
    joint_limits: dict[str, JointLimits],
    radial: float,
    body_height: float,
    step_search_lo: float = 0.0,
    step_search_hi: float = 0.10,
    tol: float = 0.002,
    all_scenarios: bool = True,
) -> tuple[float, str] | tuple[None, str]:
    """
    Binary search for the maximum step_length_max that still gives GREEN
    at given (radial, body_height). With all_scenarios=True, all 4
    cmd_vel scenarios (forward/sidestep/yaw/diagonal) must be green —
    this is the conservative "works for any motion" envelope.
    """
    def test(step: float) -> tuple[bool, str]:
        gp = GaitParams(
            radial_distance=radial,
            body_height=body_height,
            step_length_max=step,
            step_height=gait_params_template.step_height,
            cycle_time=gait_params_template.cycle_time,
            gait_pattern=gait_params_template.gait_pattern,
        )
        if all_scenarios:
            return _all_scenarios_green(gp, joint_limits)
        r = check_envelope(gp, joint_limits, scenario='forward')
        return r.ok, ('' if r.ok else f'forward:{r.first_failure["reason"]}')

    # Anchor: even smallest step must work (= stand pose feasible).
    ok_lo, reason_lo = test(max(step_search_lo, 1e-4))
    if not ok_lo:
        return None, reason_lo

    # Binary-search: find largest step within tol that is fully green.
    lo, hi = step_search_lo, step_search_hi
    last_bottleneck = 'unknown'
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        ok, reason = test(mid)
        if ok:
            lo = mid
        else:
            hi = mid
            last_bottleneck = reason
    return lo, last_bottleneck


def _find_optimal_radial(
    gait_params_template: GaitParams,
    joint_limits: dict[str, JointLimits],
    body_height: float,
    radial_search_lo: float = 0.20,
    radial_search_hi: float = 0.32,
    radial_step: float = 0.005,
) -> tuple[float | None, float, str]:
    """
    Scan radial_distance in steps, find the one that allows the largest
    step_length_max for this body_height. Returns (best_radial,
    best_step_length, bottleneck) or (None, 0, reason) if nothing works.
    """
    best_radial: float | None = None
    best_step = 0.0
    best_bottleneck = 'unknown'
    radial = radial_search_lo
    while radial <= radial_search_hi + 1e-9:
        max_step, bottleneck = _find_max_step_length(
            gait_params_template, joint_limits, radial, body_height)
        if max_step is not None and max_step > best_step:
            best_step = max_step
            best_radial = radial
            best_bottleneck = bottleneck
        radial += radial_step
    if best_radial is None:
        return None, 0.0, best_bottleneck
    return best_radial, best_step, best_bottleneck


def sweep_heights(
    gait_params_template: GaitParams,
    joint_limits: dict[str, JointLimits],
    height_min: float,
    height_max: float,
    height_step: float,
    step_height_list: list[float] | None = None,
) -> list[SweepRow]:
    """Run a height sweep (optionally × step_height), find best (radial,
    step_length) per (body_height, step_height) combination.

    step_height_list: if None, uses gait_params_template.step_height once
    (1D-Sweep). If list, runs each step_height value (2D-Sweep). All 4
    cmd_vel scenarios must be green at the chosen step_length.
    """
    step_heights = step_height_list if step_height_list else [
        gait_params_template.step_height]
    swing_duty = GAIT_PRESETS[gait_params_template.gait_pattern].swing_duty
    stance_dur = gait_params_template.cycle_time * (1.0 - swing_duty)

    rows: list[SweepRow] = []
    h = height_min
    while h <= height_max + 1e-9:
        for sh in step_heights:
            # Use a fresh template with the current step_height
            template = GaitParams(
                radial_distance=gait_params_template.radial_distance,
                body_height=gait_params_template.body_height,
                step_length_max=gait_params_template.step_length_max,
                step_height=sh,
                cycle_time=gait_params_template.cycle_time,
                gait_pattern=gait_params_template.gait_pattern,
            )
            best_radial, best_step, bottleneck = _find_optimal_radial(
                template, joint_limits, h)
            if best_radial is None:
                rows.append(SweepRow(
                    body_height=h, step_height=sh, radial_distance=None,
                    max_step_length=None, linear_max=None,
                    bottleneck=f'no working radial ({bottleneck})'))
            else:
                linear_max = best_step / stance_dur
                rows.append(SweepRow(
                    body_height=h, step_height=sh,
                    radial_distance=best_radial,
                    max_step_length=best_step, linear_max=linear_max,
                    bottleneck=bottleneck))
        h += height_step
    return rows


# ---------------------------------------------------------------------------
# Recommend mode — pro Höhe ein ready-to-use Preset mit Safety-Reserve
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    body_height: float
    radial_distance: float
    step_length_max: float
    step_height: float
    cycle_time: float
    gait_pattern: str
    linear_max: float
    safety_margin: float    # fraction (e.g. 0.10 = 10% reserve applied)
    bottleneck: str

    def to_yaml(self) -> str:
        return (
            '# Auto-generated by tools/walking_envelope_check.py recommend\n'
            f'# bottleneck at envelope edge: {self.bottleneck}\n'
            f'# safety margin applied: {self.safety_margin * 100:.0f}%\n'
            '/gait_node:\n'
            '  ros__parameters:\n'
            f'    radial_distance: {self.radial_distance:.3f}\n'
            f'    body_height: {self.body_height:.3f}\n'
            f'    step_length_max: {self.step_length_max:.3f}\n'
            f'    step_height: {self.step_height:.3f}\n'
            f'    cycle_time: {self.cycle_time:.2f}\n'
            f'    gait_pattern: {self.gait_pattern}\n'
        )


def _recommend_at_step_height(
    body_height: float,
    joint_limits: dict[str, JointLimits],
    step_height: float,
    cycle_time: float,
    gait_pattern: str,
    safety_margin: float,
) -> Recommendation | None:
    """Helper: find best radial+step_length at fixed step_height."""
    template = GaitParams(
        radial_distance=0.30, body_height=body_height,
        step_length_max=0.0, step_height=step_height,
        cycle_time=cycle_time, gait_pattern=gait_pattern,
    )
    best_radial, max_step, bottleneck = _find_optimal_radial(
        template, joint_limits, body_height)
    if best_radial is None:
        return None
    # Apply safety margin: cut step_length_max by `safety_margin` so the
    # final envelope has headroom. Re-verify the trimmed value.
    safe_step = max_step * (1.0 - safety_margin)
    gp_check = GaitParams(
        radial_distance=best_radial, body_height=body_height,
        step_length_max=safe_step, step_height=step_height,
        cycle_time=cycle_time, gait_pattern=gait_pattern,
    )
    ok, _ = _all_scenarios_green(gp_check, joint_limits)
    if not ok:
        return None
    stance_dur = cycle_time * (1.0 - GAIT_PRESETS[gait_pattern].swing_duty)
    return Recommendation(
        body_height=body_height,
        radial_distance=best_radial,
        step_length_max=safe_step,
        step_height=step_height,
        cycle_time=cycle_time,
        gait_pattern=gait_pattern,
        linear_max=safe_step / stance_dur,
        safety_margin=safety_margin,
        bottleneck=bottleneck,
    )


def recommend_for_height(
    body_height: float,
    joint_limits: dict[str, JointLimits],
    step_height: float = 0.02,
    cycle_time: float = 2.0,
    gait_pattern: str = 'tripod',
    safety_margin: float = 0.10,
    optimize_step_height: bool = False,
    step_height_range: tuple[float, float, float] = (0.010, 0.040, 0.005),
) -> Recommendation | None:
    """
    Find best gait params for a given body_height, ensuring ALL 4 cmd_vel
    scenarios (forward/sidestep/yaw/diagonal) stay green. Apply
    safety_margin (multiplicative) to step_length_max so live walking
    has reserve for tracking latency / mech-tolerance.

    optimize_step_height: if True, also sweep step_height in
    step_height_range = (min, max, step). Picks the step_height that
    maximises linear_max. Default False = use given step_height fixed.
    """
    if not optimize_step_height:
        return _recommend_at_step_height(
            body_height, joint_limits, step_height,
            cycle_time, gait_pattern, safety_margin)

    # Sweep step_height, pick the one giving the highest linear_max.
    sh_min, sh_max, sh_step = step_height_range
    best: Recommendation | None = None
    sh = sh_min
    while sh <= sh_max + 1e-9:
        rec = _recommend_at_step_height(
            body_height, joint_limits, sh,
            cycle_time, gait_pattern, safety_margin)
        if rec is not None and (best is None or rec.linear_max > best.linear_max):
            best = rec
        sh += sh_step
    return best


def format_sweep_result(rows: list[SweepRow], template: GaitParams) -> str:
    lines: list[str] = []
    lines.append('=== Walking-Envelope Sweep ===')
    lines.append(f'cycle_time={template.cycle_time:.2f}, '
                 f'pattern={template.gait_pattern}, '
                 f'all 4 cmd_vel scenarios must stay green')
    lines.append('')
    lines.append(
        f'  {"height":>8}  {"step_h":>7}  {"radial":>7}  {"max_step":>9}  '
        f'{"linear_max":>11}  bottleneck')
    for r in rows:
        if r.radial_distance is None:
            lines.append(
                f'  {r.body_height:+.3f}   {r.step_height:.3f}     -'
                f'        -           -          {r.bottleneck}')
        else:
            lines.append(
                f'  {r.body_height:+.3f}   {r.step_height:.3f}   '
                f'{r.radial_distance:.3f}   '
                f'{r.max_step_length:.3f}    {r.linear_max:.4f} m/s   '
                f'{r.bottleneck}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _add_h1_args(p: argparse.ArgumentParser, min_margin_default: float) -> None:
    """H1.1-Optionen (Margen-Schwelle, Leveling-Ecken, S4-Floor)."""
    p.add_argument(
        '--min-margin', type=float, default=min_margin_default,
        help='GREEN nur, wenn alle Joints mindestens diesen Abstand (rad) '
             'zum URDF-Limit halten. 0.0 = nur in-limit (binär). '
             f'Faustregel Femur-Rand: 0.10-0.15. Default: {min_margin_default}.')
    p.add_argument(
        '--leveling-deg', type=float, default=0.0,
        help='Zusätzlich die 8 Worst-Case-Leveling-Ecken (±deg roll/pitch + '
             'Diagonalen) fallback-frei prüfen. 4.0 = Walking-Clamp. '
             'Default: 0.0 (aus).')
    p.add_argument(
        '--s4-floor', type=float, default=0.0,
        help='Adaptiven Touchdown-Probe-Floor mitprüfen: echter S4-2-Pfad '
             'mit dieser max_extra_depth, ohne Kontakte -> Stance-Füße proben '
             'bis body_height - s4_floor. Default: 0.0 (aus).')
    p.add_argument('--ticks-per-cycle', type=int, default=100)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Walking-Envelope-Check Tool (offline IK simulation).',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest='cmd', required=True)

    # Common arg: URDF source
    def add_urdf_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            '--urdf', type=Path, default=_DEFAULT_URDF_XACRO,
            help=f'Path to URDF xacro (default: {_DEFAULT_URDF_XACRO})')

    # Mode A: check
    p_check = sub.add_parser('check', help='Single-config envelope check.')
    add_urdf_arg(p_check)
    p_check.add_argument('--params-file', type=Path,
                         help='YAML preset path (e.g. sim_walk.yaml).')
    p_check.add_argument('--radial', type=float)
    p_check.add_argument('--body-height', type=float)
    p_check.add_argument('--step-length', type=float)
    p_check.add_argument('--step-height', type=float)
    p_check.add_argument('--cycle-time', type=float, default=2.0)
    p_check.add_argument('--gait-pattern', type=str, default='tripod')
    p_check.add_argument(
        '--scenario', type=str, default='all',
        choices=['all'] + list(CMD_VEL_SCENARIOS.keys()),
        help='cmd_vel scenario to simulate. "all" runs all 4 '
             '(forward, sidestep, yaw, diagonal) and reports each. '
             'Default: all (most thorough).')
    _add_h1_args(p_check, min_margin_default=0.0)

    # Mode D (H1.1): engine-check — Transition-Coverage auf der echten Engine
    p_eng = sub.add_parser(
        'engine-check',
        help='Transition-Check auf der echten GaitEngine: WALKING-Start bei '
             'mehreren Phasenlagen, Richtungswechsel im Lauf, STOPPING-Settle, '
             'optional Stance-Switch (--switch-to) + Sitdown/Reposition. '
             'Schließt die "steady-state-only"-Lücke von check. '
             'GREEN erst ab --min-margin (Default 0.10 rad).')
    add_urdf_arg(p_eng)
    p_eng.add_argument('--params-file', type=Path)
    p_eng.add_argument('--radial', type=float)
    p_eng.add_argument('--body-height', type=float)
    p_eng.add_argument('--step-length', type=float)
    p_eng.add_argument('--step-height', type=float)
    p_eng.add_argument('--cycle-time', type=float, default=2.0)
    p_eng.add_argument('--gait-pattern', type=str, default='tripod')
    p_eng.add_argument(
        '--switch-to', type=str, default='',
        help='Ziel-Stance-Modus als "radial,body_height,step_height" '
             '(z. B. "0.18,-0.100,0.10") — prüft Stance-Switch hin, Lauf im '
             'Zielmodus und Switch zurück (inkl. Radius-Wechsel).')
    p_eng.add_argument('--switch-step-height', type=float, default=0.025)
    _add_h1_args(p_eng, min_margin_default=0.10)

    # Mode B: sweep
    p_sweep = sub.add_parser('sweep', help='Height-sweep — find optimal '
                             'radial + max step_length per body_height. '
                             'Optional 2D mit --step-height-list.')
    add_urdf_arg(p_sweep)
    p_sweep.add_argument('--height-min', type=float, default=-0.080)
    p_sweep.add_argument('--height-max', type=float, default=-0.030)
    p_sweep.add_argument('--height-step', type=float, default=0.01)
    p_sweep.add_argument('--step-height', type=float, default=0.02,
                         help='Fixed step_height for 1D sweep '
                              '(ignored if --step-height-list given).')
    p_sweep.add_argument(
        '--step-height-list', type=str, default='',
        help='Comma-separated step_height values for 2D-sweep (e.g. '
             '"0.015,0.020,0.025"). Output gets one row per (height, '
             'step_height) combination.')
    p_sweep.add_argument('--cycle-time', type=float, default=2.0)
    p_sweep.add_argument('--gait-pattern', type=str, default='tripod')

    # Mode C: recommend — output ready-to-paste YAML preset
    p_rec = sub.add_parser(
        'recommend',
        help='Recommend ready-to-paste gait_node preset for a given '
             'body_height. All 4 cmd_vel scenarios must stay green '
             'with the chosen safety margin.')
    add_urdf_arg(p_rec)
    p_rec.add_argument('--body-height', type=float, required=True,
                       help='Target body_height in m (negative). '
                            'Example: --body-height -0.07')
    p_rec.add_argument('--step-height', type=float, default=0.02)
    p_rec.add_argument('--cycle-time', type=float, default=2.0)
    p_rec.add_argument('--gait-pattern', type=str, default='tripod')
    p_rec.add_argument(
        '--safety-margin', type=float, default=0.10,
        help='Fraction by which step_length_max is trimmed from the '
             'envelope edge for runtime headroom (default: 0.10 = 10%%).')
    p_rec.add_argument(
        '--optimize-step-height', action='store_true',
        help='Sweep step_height in 0.010..0.040 (step 0.005) too and '
             'pick the value that gives the highest linear_max for the '
             'given body_height.')
    p_rec.add_argument(
        '--output', type=Path,
        help='Write the YAML to this path (also printed to stdout).')

    args = parser.parse_args()
    joint_limits = load_joint_limits(args.urdf)

    def resolve_gait_params(cmd_name: str) -> GaitParams:
        """--params-file XOR die vier CLI-Werte (check + engine-check)."""
        if args.params_file:
            return GaitParams.from_yaml(args.params_file)
        missing = [name for name, val in [
            ('--radial', args.radial),
            ('--body-height', args.body_height),
            ('--step-length', args.step_length),
            ('--step-height', args.step_height),
        ] if val is None]
        if missing:
            parser.error(
                f'{cmd_name}: provide --params-file OR all of: '
                + ', '.join(missing))
        return GaitParams(
            radial_distance=args.radial,
            body_height=args.body_height,
            step_length_max=args.step_length,
            step_height=args.step_height,
            cycle_time=args.cycle_time,
            gait_pattern=args.gait_pattern,
        )

    if args.cmd == 'check':
        gp = resolve_gait_params('check')
        h1_kwargs = dict(
            ticks_per_cycle=args.ticks_per_cycle,
            min_margin=args.min_margin,
            leveling_deg=args.leveling_deg,
            s4_floor=args.s4_floor,
        )
        if args.scenario == 'all':
            results = check_envelope_all_scenarios(
                gp, joint_limits, **h1_kwargs)
            print(format_check_result(results['forward'], gp, joint_limits))
            print('')
            print('=== All cmd_vel scenarios ===')
            all_green = True
            for name, r in results.items():
                if r.ok:
                    print(f'  {name:9} ✓ GREEN')
                else:
                    all_green = False
                    f = r.first_failure
                    print(f'  {name:9} ❌ {f["reason"]} '
                          f'(t={f["time"]:.2f}s): {f["message"][:90]}...')
            return 0 if all_green else 1
        result = check_envelope(
            gp, joint_limits, scenario=args.scenario, **h1_kwargs)
        print(format_check_result(result, gp, joint_limits))
        return 0 if result.ok else 1

    if args.cmd == 'engine-check':
        gp = resolve_gait_params('engine-check')
        switch_to = None
        if args.switch_to:
            try:
                parts = [float(x) for x in args.switch_to.split(',')]
                if len(parts) != 3:
                    raise ValueError
                switch_to = (parts[0], parts[1], parts[2])
            except ValueError:
                parser.error(
                    '--switch-to expects "radial,body_height,step_height" '
                    f'(got {args.switch_to!r})')
        result = engine_transition_check(
            gp, joint_limits,
            min_margin=args.min_margin,
            s4_floor=args.s4_floor,
            switch_to=switch_to,
            switch_step_height=args.switch_step_height,
            ticks_per_cycle=args.ticks_per_cycle,
        )
        print(format_check_result(result, gp, joint_limits))
        if not result.ok:
            reasons = {}
            for f in result.failures:
                reasons[f['reason']] = reasons.get(f['reason'], 0) + 1
            print('  failure reasons: ' + ', '.join(
                f'{k}×{v}' for k, v in sorted(reasons.items())))
        return 0 if result.ok else 1

    if args.cmd == 'sweep':
        template = GaitParams(
            radial_distance=0.30,  # not used directly — replaced per-iter
            body_height=0.0,       # not used directly
            step_length_max=0.0,   # not used directly
            step_height=args.step_height,
            cycle_time=args.cycle_time,
            gait_pattern=args.gait_pattern,
        )
        step_height_list: list[float] | None = None
        if args.step_height_list.strip():
            try:
                step_height_list = [
                    float(x) for x in args.step_height_list.split(',')]
            except ValueError as e:
                parser.error(
                    f'invalid --step-height-list: {e} '
                    f'(expected comma-separated floats)')
        rows = sweep_heights(
            template, joint_limits,
            args.height_min, args.height_max, args.height_step,
            step_height_list=step_height_list)
        print(format_sweep_result(rows, template))
        return 0

    if args.cmd == 'recommend':
        rec = recommend_for_height(
            body_height=args.body_height,
            joint_limits=joint_limits,
            step_height=args.step_height,
            cycle_time=args.cycle_time,
            gait_pattern=args.gait_pattern,
            safety_margin=args.safety_margin,
            optimize_step_height=args.optimize_step_height,
        )
        if rec is None:
            print(f'No working preset found for body_height={args.body_height} '
                  f'with all 4 cmd_vel scenarios + {args.safety_margin*100:.0f}% '
                  'safety margin. Try a different height or lower margin.')
            return 1
        yaml_out = rec.to_yaml()
        print(yaml_out)
        print(f'# linear_max = {rec.linear_max:.4f} m/s')
        if args.output:
            args.output.write_text(yaml_out)
            print(f'# wrote: {args.output}')
        return 0

    return 0


if __name__ == '__main__':
    sys.exit(main())
