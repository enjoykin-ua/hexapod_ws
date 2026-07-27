#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""Envelope-Check der Body-Pose („Look-Around", Block I Phase 8).

================================================================================
Look-Around-Envelope-Check (Block I Phase 8 — Body-Pose bei fixen Füßen)
================================================================================

Offline-Werkzeug für die Show **„Look-Around"** (`STATE_BODY_POSE`): der Roboter
steht, alle 6 Füße bleiben **weltfest am Boden**, und der **Körper** wird um
``(dx, dy, dz, roll, pitch, yaw)`` bewegt. Das Tool belegt die Envelope-Grenzen,
die als Param-Defaults in den ``gait_node`` gehen (Plan §4.4), **bevor** Code
darauf aufbaut (CLAUDE.md §4 + Memory ``feedback_validate_hardware_hypothesis_via_code``).

Modell (rein kinematisch, quasi-statisch) — identisch zur Engine:
    foot_base_fix = leg_to_base_frame((radial, 0, body_height), leg)   # weltfest
    R             = Rz(yaw) · Ry(pitch) · Rx(roll)                     # Körper
    foot_in_body  = R⁻¹ · (foot_base_fix − (dx,dy,dz))
    angles        = leg_ik(base_to_leg_frame(foot_in_body, leg), leg, URDF_LIMITS)

Nutzt die ECHTEN ``leg_ik``/``joint_load`` und die ECHTEN URDF-Joint-Limits via
xacro (zwei-Limit-Quellen: geprüft wird gegen die **URDF**, nicht config.py).
Keine Parallel-Mathe.

────────────────────────────────────────────────────────────────────────────────
GATE-KRITERIEN (Exit 0)
────────────────────────────────────────────────────────────────────────────────
1. **Einzelachse an der Default-Grenze** (alle anderen DOF = 0) ist für **jede**
   Stance-Höhe limit-konform. Das ist die harte Bedingung — die Per-Achse-Clamps
   im Node dürfen nie allein schon out-of-envelope führen.
2. **CoG-Marge** > ``--margin-goal`` (Default 30 mm) an allen erreichbaren
   Stichproben (6-Bein-Stützpolygon, im **Welt-Frame** gerechnet, damit die
   Körper-Neigung korrekt eingeht).

**Kein** Gate-Kriterium sind die Kombinations-Ecken: dass nicht jede Kombination
aller Achsen gleichzeitig erreichbar ist, ist bekannt und **bewusst** ([D-Show-8]) —
die Engine fängt das per Greedy-Achsen-Nachführung ab (Plan §1b.2). Ihr Anteil
wird als Kennzahl berichtet, damit man den Effekt der Grenzen einschätzen kann.

Nutzung:
    python3 tools/look_around_envelope_check.py                  # Gate + Kennzahlen
    python3 tools/look_around_envelope_check.py --sweep          # Einzelachs-Maxima
    python3 tools/look_around_envelope_check.py --dx 0.06 --pitch-deg 18
================================================================================
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from hexapod_gait.joint_load import (
    MassModel,
    _convex_hull,
    _signed_margin,
    compute_load,
)

from hexapod_kinematics import HEXAPOD, IKError, leg_ik
from hexapod_kinematics.geometry import base_to_leg_frame, leg_to_base_frame

# walking_envelope_check liegt im selben tools/-Verzeichnis (load_joint_limits
# ruft xacro auf die URDF und parst die Limits — dieselbe Quelle wie das Plugin).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walking_envelope_check import _DEFAULT_URDF_XACRO, load_joint_limits  # noqa: E402


# Stance-Modi (radial, body_height) — 1:1 aus gait_node._STANCE_MODES. Hier
# dupliziert, um das Tool ROS-frei zu halten; bei Änderung dort mitziehen.
_STANCE_MODES = (
    ('tief', 0.160, -0.065),
    ('mittel', 0.160, -0.080),
    ('hoch', 0.160, -0.100),
)

# Reihenfolge der DOF in allen Ausgaben/Tupeln.
_DOF_NAMES = ('dx', 'dy', 'dz', 'roll', 'pitch', 'yaw')


def rot_body_inv(point, roll: float, pitch: float, yaw: float):
    """
    ``R⁻¹ · point`` mit ``R = Rz(yaw)·Ry(pitch)·Rx(roll)`` (REP-103-RPY).

    Exakte Inverse (Rx(−roll)·Ry(−pitch)·Rz(−yaw)) — **nicht**
    ``rotate_xy(p, −roll, −pitch)``, das wäre Ry(−pitch)·Rx(−roll) und damit
    eine andere Reihenfolge. Muss identisch zur Engine bleiben.
    """
    x, y, z = point
    c, s = math.cos(-yaw), math.sin(-yaw)
    x, y = c * x - s * y, s * x + c * y
    c, s = math.cos(-pitch), math.sin(-pitch)
    x, z = c * x + s * z, -s * x + c * z
    c, s = math.cos(-roll), math.sin(-roll)
    y, z = c * y - s * z, s * y + c * z
    return (x, y, z)


def rot_body(point, roll: float, pitch: float, yaw: float):
    """``R · point`` (Vorwärts-Rotation, für den CoG-Rücktransport in Weltkoord.)."""
    x, y, z = point
    c, s = math.cos(roll), math.sin(roll)
    y, z = c * y - s * z, s * y + c * z
    c, s = math.cos(pitch), math.sin(pitch)
    x, z = c * x + s * z, -s * x + c * z
    c, s = math.cos(yaw), math.sin(yaw)
    x, y = c * x - s * y, s * x + c * y
    return (x, y, z)


def foot_targets_fixed(radial: float, body_height: float) -> dict:
    """Weltfeste Fuß-Positionen der Stand-Pose im base-Frame (Snapshot-Äquivalent)."""
    return {
        leg.name: leg_to_base_frame((radial, 0.0, body_height), leg)
        for leg in HEXAPOD.legs
    }


def body_pose_angles(foot_fix: dict, dof, joint_limits: dict):
    """
    Joint-Winkel aller 6 Beine für eine Body-Pose. Wirft ``IKError``.

    ``dof`` = ``(dx, dy, dz, roll, pitch, yaw)``.
    """
    dx, dy, dz, roll, pitch, yaw = dof
    angles = {}
    for leg in HEXAPOD.legs:
        fx, fy, fz = foot_fix[leg.name]
        rel = (fx - dx, fy - dy, fz - dz)
        p_body = rot_body_inv(rel, roll, pitch, yaw)
        angles[leg.name] = leg_ik(
            *base_to_leg_frame(p_body, leg), leg, joint_limits.get(leg.name),
        )
    return angles


def cog_margin_world(foot_fix: dict, dof, angles: dict, masses: MassModel) -> float:
    """
    CoG-Marge (m) im 6-Bein-Stützpolygon, im **Welt-Frame** gerechnet.

    ``compute_load`` liefert den CoG im **Körper**-Frame; bei geneigtem Körper
    wäre dessen xy-Projektion gegen die Schwerkraft falsch (Fehler ≈ h·tan(pitch),
    bei 15° und 8 cm Höhe schon ~21 mm). Daher: CoG zurück in den Welt-Frame
    (``R·cog + d``) und dort gegen die **fixen** Fuß-xy projizieren — dort zeigt
    z tatsächlich entgegen der Schwerkraft.
    """
    load = compute_load(angles, masses=masses)
    dx, dy, dz, roll, pitch, yaw = dof
    cx, cy, cz = rot_body(load.cog_base, roll, pitch, yaw)
    cog_world = (cx + dx, cy + dy)
    hull = _convex_hull([(p[0], p[1]) for p in foot_fix.values()])
    return _signed_margin(cog_world, hull)


def sweep_axis(foot_fix, axis_idx: int, joint_limits, step: float, limit: float):
    """Max. Auslenkung einer einzelnen Achse in + und − (alle anderen DOF 0)."""
    out = {}
    for sign in (+1, -1):
        val = 0.0
        while abs(val) < limit:
            nxt = val + sign * step
            dof = [0.0] * 6
            dof[axis_idx] = nxt
            try:
                body_pose_angles(foot_fix, dof, joint_limits)
            except IKError:
                break
            val = nxt
        out[sign] = val
    return out


def check_single_axes(foot_fix, grenzen, joint_limits, masses, margin_goal):
    """
    Gate 1+2: jede Achse allein an ihrer Default-Grenze (+/−).

    Returns ``(ok, rows)`` mit ``rows`` = ``(name, wert, status, margin_mm)``.
    """
    ok = True
    rows = []
    for idx, name in enumerate(_DOF_NAMES):
        g = grenzen[idx]
        if g == 0.0:
            rows.append((name, 0.0, 'AUS (v1)', None))
            continue
        for sign in (+1, -1):
            dof = [0.0] * 6
            dof[idx] = sign * g
            try:
                angles = body_pose_angles(foot_fix, dof, joint_limits)
            except IKError as exc:
                ok = False
                rows.append((name, sign * g, f'RED {str(exc)[:60]}', None))
                continue
            margin = cog_margin_world(foot_fix, dof, angles, masses)
            status = 'GREEN'
            if margin < margin_goal:
                ok = False
                status = 'RED CoG'
            rows.append((name, sign * g, status, margin * 1000.0))
    return ok, rows


# Bedien-Gesten, die **eine** Hand in **einer** Bewegung erzeugt — die müssen an
# ihren Grenzen voll erreichbar sein, sonst fühlt sich schon ein einzelner Stick
# „beschnitten" an. Format: ``(label, ((achs_index, gewicht), …))``.
#
# **Gewicht 0.75 bei Stick-Diagonalen (statt 1.0):** ein Analog-Stick läuft in
# einem runden Gate — bei diagonalem Vollausschlag steht jede Achse bei ~0.71
# (1/√2), nicht bei 1.0. Beide Achsen gleichzeitig auf 1.0 ist mit einem Stick
# physisch nicht erreichbar; 0.75 gibt darauf noch etwas Marge. Trigger (dz)
# sind davon unabhängig → dort volles Gewicht.
#
# Alles darüber (wandern UND schauen UND heben gleichzeitig, zwei Hände) ist
# bewusst dem Greedy-Clamp überlassen — das ist keine einzelne Geste mehr.
_DIAG = 0.75
_GESTURES = (
    ('rechter Stick diagonal', ((4, _DIAG), (5, _DIAG))),        # pitch + yaw
    ('linker Stick diagonal', ((0, _DIAG), (1, _DIAG))),         # dx + dy
    ('pitch voll + Höhe voll', ((4, 1.0), (2, 1.0))),
    ('yaw voll + Höhe voll', ((5, 1.0), (2, 1.0))),
    ('rechter Stick diag + Höhe', ((4, _DIAG), (5, _DIAG), (2, 1.0))),
)


def check_gestures(foot_fix, grenzen, joint_limits):
    """
    Gate 3: jede Bedien-Geste an ihren Grenzen, alle Vorzeichen-Kombis.

    Returns ``(ok, rows)`` mit ``rows`` = ``(label, ok, erste_fehlermeldung)``.
    """
    ok_all = True
    rows = []
    for label, axes in _GESTURES:
        gesture_ok = True
        first_fail = None
        for mask in range(2 ** len(axes)):
            dof = [0.0] * 6
            for bit, (idx, weight) in enumerate(axes):
                sign = 1 if (mask >> bit) & 1 else -1
                dof[idx] = grenzen[idx] * weight * sign
            try:
                body_pose_angles(foot_fix, dof, joint_limits)
            except IKError as exc:
                gesture_ok = False
                if first_fail is None:
                    first_fail = str(exc)[:70]
        ok_all = ok_all and gesture_ok
        rows.append((label, gesture_ok, first_fail))
    return ok_all, rows


def check_corners(foot_fix, grenzen, joint_limits, masses):
    """
    Kennzahl (kein Gate): Anteil der Vorzeichen-Ecken, die voll erreichbar sind.

    Ecken über die aktiven Achsen (Grenze 0 = Achse aus → nicht variiert).
    Liefert ``(n_ok, n_total, min_margin_mm)`` — die Marge nur über erreichbare
    Ecken (unerreichbare fängt der Greedy-Clamp der Engine ab, [D-Show-8]).
    """
    active = [i for i, g in enumerate(grenzen) if g != 0.0]
    n_total = 2 ** len(active)
    n_ok = 0
    min_margin = None
    for mask in range(n_total):
        dof = [0.0] * 6
        for bit, idx in enumerate(active):
            dof[idx] = grenzen[idx] * (1 if (mask >> bit) & 1 else -1)
        try:
            angles = body_pose_angles(foot_fix, dof, joint_limits)
        except IKError:
            continue
        n_ok += 1
        margin = cog_margin_world(foot_fix, dof, angles, masses)
        if min_margin is None or margin < min_margin:
            min_margin = margin
    return n_ok, n_total, (None if min_margin is None else min_margin * 1000.0)


def main() -> int:
    """CLI: Gate-Check der Default-Grenzen (+ optionaler Einzelachs-Sweep)."""
    ap = argparse.ArgumentParser(
        description='Look-Around-Envelope-Check (Block I Phase 8).')
    ap.add_argument('--urdf', type=Path, default=_DEFAULT_URDF_XACRO)
    ap.add_argument('--dx', type=float, default=0.050,
                    help='body_pose_dx_max (m, Default 0.050)')
    ap.add_argument('--dy', type=float, default=0.035,
                    help='body_pose_dy_max (m, Default 0.035)')
    ap.add_argument('--dz', type=float, default=0.020,
                    help='body_pose_dz_max (m, Default 0.020)')
    ap.add_argument('--roll-deg', type=float, default=0.0,
                    help='body_pose_roll_max_deg (Default 0 = v1 aus)')
    ap.add_argument('--pitch-deg', type=float, default=12.0,
                    help='body_pose_pitch_max_deg (Default 12)')
    ap.add_argument('--yaw-deg', type=float, default=10.0,
                    help='body_pose_yaw_max_deg (Default 10)')
    ap.add_argument('--margin-goal', type=float, default=0.030,
                    help='min. CoG-Marge (m, Default 0.030 wie show_safety_margin)')
    ap.add_argument('--total-mass', type=float, default=None,
                    help='echtes Gesamtgewicht (kg); sonst URDF-Summe')
    ap.add_argument('--sweep', action='store_true',
                    help='zusätzlich die Einzelachs-Maxima ausrastern')
    args = ap.parse_args()

    joint_limits = load_joint_limits(args.urdf)
    masses = MassModel(total_mass=args.total_mass)
    grenzen = (
        args.dx, args.dy, args.dz,
        math.radians(args.roll_deg),
        math.radians(args.pitch_deg),
        math.radians(args.yaw_deg),
    )

    print('=== Look-Around-Envelope-Check (Phase 8, Body-Pose bei fixen Füßen) ===')
    print(f'Grenzen: dx=±{args.dx * 1000:.0f}mm dy=±{args.dy * 1000:.0f}mm '
          f'dz=±{args.dz * 1000:.0f}mm roll=±{args.roll_deg:.0f}° '
          f'pitch=±{args.pitch_deg:.0f}° yaw=±{args.yaw_deg:.0f}°')
    print(f'CoG-Ziel: ≥ {args.margin_goal * 1000:.0f} mm '
          f'(Masse {masses.total():.2f} kg, 6-Bein-Polygon, Welt-Frame)')

    all_green = True
    for name, radial, body_height in _STANCE_MODES:
        foot_fix = foot_targets_fixed(radial, body_height)
        print(f'\n--- Stance {name} (radial={radial:.3f}, '
              f'body_height={body_height:.3f}) ---')

        if args.sweep:
            print('  Einzelachs-Maxima (alle anderen DOF = 0):')
            for idx, dof_name in enumerate(_DOF_NAMES):
                is_ang = idx >= 3
                step = math.radians(0.5) if is_ang else 0.002
                limit = math.radians(45) if is_ang else 0.20
                r = sweep_axis(foot_fix, idx, joint_limits, step, limit)
                if is_ang:
                    print(f'    {dof_name:6s}: +{math.degrees(r[1]):6.1f}° / '
                          f'{math.degrees(r[-1]):6.1f}°')
                else:
                    print(f'    {dof_name:6s}: +{r[1] * 1000:6.1f}mm / '
                          f'{r[-1] * 1000:6.1f}mm')

        ok, rows = check_single_axes(
            foot_fix, grenzen, joint_limits, masses, args.margin_goal)
        all_green = all_green and ok
        print('  Gate 1+2 — Einzelachse an der Grenze:')
        for dof_name, val, status, margin_mm in rows:
            idx = _DOF_NAMES.index(dof_name)
            shown = (f'{math.degrees(val):+6.1f}°' if idx >= 3
                     else f'{val * 1000:+6.1f}mm')
            margin_txt = '' if margin_mm is None else f'  CoG {margin_mm:6.1f} mm'
            print(f'    {dof_name:6s} {shown}  {status}{margin_txt}')

        gestures_ok, gesture_rows = check_gestures(
            foot_fix, grenzen, joint_limits)
        all_green = all_green and gestures_ok
        print('  Gate 3 — Bedien-Gesten an der Grenze:')
        for label, ok_gesture, fail in gesture_rows:
            print(f'    {label:24s} {"GREEN" if ok_gesture else "RED  " + fail}')

        n_ok, n_total, min_margin = check_corners(
            foot_fix, grenzen, joint_limits, masses)
        margin_txt = ('—' if min_margin is None
                      else f'{min_margin:.1f} mm (min über erreichbare)')
        print(f'  Kennzahl — Kombinations-Ecken erreichbar: {n_ok}/{n_total}'
              f'   CoG {margin_txt}')
        print('    (nicht erreichbare Ecken fängt der Greedy-Achsen-Clamp der '
              'Engine ab — [D-Show-8])')

    print('')
    print('GREEN — Einzelachsen + Stick-Paare + CoG-Marge über alle '
          'Stance-Höhen ok'
          if all_green else
          'RED — Einzelachs-Grenze, Stick-Paar oder CoG-Marge verletzt')
    return 0 if all_green else 1


if __name__ == '__main__':
    sys.exit(main())
