#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
Leveling-Envelope-Check — Block A5 Stufe 2 (Checkliste 2.5).

Offline-Screen: bleibt die **gelevelte Stand-Pose** bei Hangwinkel θ in den
**URDF-Joint-Limits** und **CoG-stabil**? Bestätigt das ``max_level_angle``
(Start 10°), das der BalanceController-Clamp nutzt (Risiko 1: nie out-of-
envelope durch Leveling).

Reproduziert **exakt** den Engine-Stellpfad (``_leveled_ik_at``): stand_pose-
Targets → ``rotate_xy(roll, pitch)`` im Base-Frame → ``leg_ik`` gegen die
**echten URDF-Limits** (via xacro, wie ``walking_envelope_check`` — NICHT die
loseren config.py-Limits, Memory „zwei Limit-Quellen") → ``compute_load``
(CoG/Stützpolygon/Marge).

Modi je θ:  roll=θ · pitch=θ · combined roll=pitch=θ (worst-case Ecke).
Stance-Modi (body_height bei radial 0.160):  tief −0.065 · mittel −0.080 ·
hoch −0.100 (= _STANCE_MODES in gait_node).

PRÜFT (kinematisch + statisch):
- Alle 6 Beine in URDF-Joint-Limits nach der Leveling-Rotation
- Fuß in Reichweite (leg_ik out-of-reach)
- Statische CoG-Stabilität (Marge CoG→Stützpolygon-Rand, flat-leveled-Annahme:
  Body horizontal → base-Z ≈ Schwerkraft, gültig für die GELEVELTE Pose)

PRÜFT NICHT (→ Gazebo/HW, 2.7):
- Dynamik/Schlupf, Servo-Drehmoment, Fuß-Scrub-Kräfte, Reibungsgrenze.

Usage:
    python3 tools/leveling_envelope_check.py
    python3 tools/leveling_envelope_check.py --theta-list 5,8,10,12,15,20
    python3 tools/leveling_envelope_check.py --max-level-angle 10 --min-margin-mm 5
Exit 0 wenn ``--max-level-angle`` in ALLEN Stance×Modi grün, sonst 1.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import sys

# tools/ ist kein Package — load_joint_limits aus dem Nachbar-Tool ziehen
# (liest die echten URDF-Limits via xacro).
_TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_TOOL_DIR))
import walking_envelope_check as wec  # noqa: E402

from hexapod_gait.joint_load import compute_load  # noqa: E402
from hexapod_gait.trajectory_gen import stand_pose  # noqa: E402
from hexapod_kinematics import (  # noqa: E402
    base_to_leg_frame,
    HEXAPOD,
    IKError,
    JointLimits,
    leg_ik,
    leg_to_base_frame,
    rotate_xy,
)


_URDF_XACRO = _TOOL_DIR.parent / 'src/hexapod_description/urdf/hexapod.urdf.xacro'

# (name, body_height) bei radial 0.160 — = _STANCE_MODES in gait_node.
_STANCE_MODES = (('tief', -0.065), ('mittel', -0.080), ('hoch', -0.100))
_RADIAL = 0.160
# (name, roll_faktor, pitch_faktor) — beide Vorzeichen je Achse (ein Hang kippt
# in beide Richtungen) + die 4 combined-Ecken (worst-case). Der Engine-Stellpfad
# rotiert die Füße um die Hang-Magnitude θ; die Richtung hängt vom Hang ab.
_ORIENT_MODES = (
    ('roll+', 1.0, 0.0), ('roll-', -1.0, 0.0),
    ('pitch+', 0.0, 1.0), ('pitch-', 0.0, -1.0),
    ('comb++', 1.0, 1.0), ('comb+-', 1.0, -1.0),
    ('comb-+', -1.0, 1.0), ('comb--', -1.0, -1.0),
)


def leveled_angles(
    theta_rad: float,
    roll_f: float,
    pitch_f: float,
    body_height: float,
    limits: dict[str, JointLimits],
    radial: float = _RADIAL,
) -> dict[str, tuple]:
    """
    Gelevelte Joint-Winkel — exakt der Engine-Stellpfad.

    Wirft ``IKError`` (out-of-limit ODER out-of-reach) wenn die Rotation einen
    Fuß aus dem Envelope schiebt.
    """
    corr_roll = theta_rad * roll_f
    corr_pitch = theta_rad * pitch_f
    angles: dict[str, tuple] = {}
    for leg in HEXAPOD.legs:
        target = stand_pose(radial, body_height)
        base_pt = leg_to_base_frame(target, leg)
        rot = rotate_xy(base_pt, corr_roll, corr_pitch)
        leg_pt = base_to_leg_frame(rot, leg)
        angles[leg.name] = leg_ik(*leg_pt, leg, limits[leg.name])
    return angles


def evaluate(
    theta_deg: float,
    roll_f: float,
    pitch_f: float,
    body_height: float,
    limits: dict[str, JointLimits],
    radial: float = _RADIAL,
    min_margin_m: float = 0.005,
) -> dict:
    """Einen (θ, Orientierung, Stance)-Fall bewerten."""
    theta = math.radians(theta_deg)
    try:
        angles = leveled_angles(
            theta, roll_f, pitch_f, body_height, limits, radial,
        )
    except IKError as exc:
        return {
            'in_limit': False, 'margin_m': None, 'stable': False,
            'ok': False, 'detail': str(exc),
        }
    load = compute_load(angles)
    margin = load.stability_margin_m
    cog_ok = load.stable and margin >= min_margin_m
    return {
        'in_limit': True, 'margin_m': margin, 'stable': load.stable,
        'ok': cog_ok, 'detail': '',
    }


def max_safe_theta(
    limits: dict[str, JointLimits],
    theta_candidates,
    radial: float = _RADIAL,
    min_margin_m: float = 0.005,
) -> float:
    """Größter θ-Kandidat, bei dem ALLE Stance×Orientierungs-Modi grün sind."""
    best = 0.0
    for theta in sorted(theta_candidates):
        all_ok = True
        for _, body_height in _STANCE_MODES:
            for _, rf, pf in _ORIENT_MODES:
                if not evaluate(
                    theta, rf, pf, body_height, limits, radial, min_margin_m,
                )['ok']:
                    all_ok = False
                    break
            if not all_ok:
                break
        if all_ok:
            best = theta
        else:
            break
    return best


def _fmt_margin(m) -> str:
    return '   n/a' if m is None else f'{m * 1000.0:6.1f}'


def run_report(
    theta_list, limits, radial=_RADIAL, min_margin_m=0.005,
) -> None:
    """Tabelle θ × Stance × Orientierung ausgeben."""
    print(
        f'Leveling-Envelope-Check  (radial={radial:.3f} m, '
        f'min_margin={min_margin_m * 1000:.1f} mm, URDF-Limits)\n'
    )
    header = f'{"θ°":>4} {"stance":>7} {"orient":>9} {"in-lim":>7} {"margin/mm":>10} {"OK":>4}'
    print(header)
    print('-' * len(header))
    for theta in theta_list:
        for sname, bh in _STANCE_MODES:
            for oname, rf, pf in _ORIENT_MODES:
                r = evaluate(theta, rf, pf, bh, limits, radial, min_margin_m)
                flag = 'OK' if r['ok'] else ('LIM' if not r['in_limit'] else 'CoG')
                print(
                    f'{theta:4.0f} {sname:>7} {oname:>9} '
                    f'{"yes" if r["in_limit"] else "NO":>7} '
                    f'{_fmt_margin(r["margin_m"]):>10} {flag:>4}'
                )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Leveling-Envelope-Check (A5 Stufe 2, Checkliste 2.5).',
    )
    parser.add_argument(
        '--theta-list', default='5,8,10,15',
        help='Komma-Liste der zu prüfenden Hangwinkel in Grad (default 5,8,10,15).',
    )
    parser.add_argument(
        '--max-level-angle', type=float, default=10.0,
        help='Zu bestätigender Clamp-Winkel in Grad (Exit-Code-Kriterium, default 10).',
    )
    parser.add_argument(
        '--min-margin-mm', type=float, default=5.0,
        help='Minimale CoG-Stabilitätsmarge in mm (default 5).',
    )
    parser.add_argument(
        '--radial', type=float, default=_RADIAL,
        help=f'Radialer Fuß-Abstand (default {_RADIAL}).',
    )
    parser.add_argument(
        '--urdf', type=Path, default=_URDF_XACRO,
        help='Pfad zur URDF-xacro (Default: committed Stage-D-URDF).',
    )
    args = parser.parse_args()

    limits = wec.load_joint_limits(args.urdf)
    theta_list = [float(x) for x in args.theta_list.split(',') if x.strip()]
    min_margin_m = args.min_margin_mm / 1000.0

    run_report(theta_list, limits, args.radial, min_margin_m)

    candidates = sorted(set(theta_list) | {args.max_level_angle})
    best = max_safe_theta(limits, candidates, args.radial, min_margin_m)
    print(f'→ Max. envelope-sicherer Hangwinkel (alle Stance×Modi): {best:.0f}°')
    if best >= args.max_level_angle:
        print(
            f'✓ max_level_angle={args.max_level_angle:.0f}° ist bestätigt '
            '(in allen Modi in-limit + CoG-stabil).'
        )
        return 0
    print(
        f'✗ max_level_angle={args.max_level_angle:.0f}° NICHT durchgehend sicher '
        f'— Clamp auf {best:.0f}° senken oder Stance/Geometrie anpassen.'
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
