#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
================================================================================
Stand-Conform-Envelope-Check (Block A5 S4-7)
================================================================================

Offline-Werkzeug für den **adaptiven Stand** (S4-7). Es prüft, ob die statische
Stand-Pose bei ``radial_distance`` von ``body_height`` bis zum Konform-Floor
``body_height − stand_conform_max_depth`` für **jede Stance-Höhe** kinematisch
sauber ist — d.h. jeder abgesenkte Fuß bleibt innerhalb der **URDF-Joint-Limits**
(zwei-Limit-Quellen: geprüft wird gegen die URDF, nicht gegen config.py) und der
Bein-Reichweite. Das ist der Stand-Pendant zum ``walking_envelope_check`` (Lauf-
Floor); nur z variiert (x,y = radial, 0 sind im Stand fix).

Pure Python, kein ROS-Runtime — nutzt ``leg_ik`` + die xacro-expandierte URDF.

Nutzung:
    python3 tools/stand_conform_envelope_check.py                # alle Stance-Modi
    python3 tools/stand_conform_envelope_check.py --max-depth 0.03
    python3 tools/stand_conform_envelope_check.py --radial 0.160 --body-height -0.100

Exit 0 = alle geprüften (Modus × Tiefe) GREEN, sonst 1.
================================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hexapod_kinematics import HEXAPOD, IKError, leg_ik

# walking_envelope_check liegt im selben tools/-Verzeichnis (load_joint_limits
# ruft xacro auf die Stage-D-URDF und parst die Limits).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from walking_envelope_check import _DEFAULT_URDF_XACRO, load_joint_limits  # noqa: E402


# Stance-Modi (radial, body_height) — 1:1 aus gait_node._STANCE_MODES. Hier
# dupliziert, um das Tool ROS-frei zu halten; bei Änderung dort mitziehen.
_STANCE_MODES = (
    ('tief', 0.160, -0.065),
    ('mittel', 0.160, -0.080),
    ('hoch', 0.160, -0.100),
)


def check_stand_floor(radial, body_height, max_depth, joint_limits, n_steps=20):
    """
    Prüfe die statische Stand-Pose von body_height bis zum Floor für alle Beine.

    Rastert z in ``n_steps`` von ``body_height`` bis ``body_height − max_depth``
    ab und ruft ``leg_ik`` pro Bein mit den URDF-Limits. Returns
    ``(ok, first_fail)`` — ``first_fail`` = ``(leg_name, z, message)`` oder None.
    """
    for i in range(n_steps + 1):
        z = body_height - max_depth * (i / n_steps)
        for leg in HEXAPOD.legs:
            try:
                leg_ik(radial, 0.0, z, leg, joint_limits.get(leg.name))
            except IKError as exc:
                return False, (leg.name, z, str(exc))
    return True, None


def main() -> int:
    """CLI: prüfe den Stand-Floor je Stance-Modus (oder custom radial/Höhe)."""
    parser = argparse.ArgumentParser(
        description='Stand-Conform-Envelope-Check (S4-7).',
    )
    parser.add_argument('--urdf', type=Path, default=_DEFAULT_URDF_XACRO)
    parser.add_argument('--max-depth', type=float, default=0.04,
                        help='stand_conform_max_depth (m, Default 0.04). '
                             'Envelope-Grenze über alle Stance-Modi = 0.05.')
    parser.add_argument('--radial', type=float, default=None,
                        help='Nur diesen radial prüfen (sonst alle Stance-Modi).')
    parser.add_argument('--body-height', type=float, default=None,
                        help='Nur diese Höhe prüfen (mit --radial).')
    args = parser.parse_args()

    joint_limits = load_joint_limits(args.urdf)

    if args.radial is not None and args.body_height is not None:
        cases = [('custom', args.radial, args.body_height)]
    else:
        cases = list(_STANCE_MODES)

    print('=== Stand-Conform-Envelope Check (S4-7) ===')
    print(f'max_depth = {args.max_depth:.3f} m (Floor = body_height − max_depth)')
    print(f'{"mode":8} {"radial":>7} {"body_h":>8} {"floor":>8}  result')
    all_green = True
    for name, radial, body_height in cases:
        floor = body_height - args.max_depth
        ok, fail = check_stand_floor(
            radial, body_height, args.max_depth, joint_limits)
        if ok:
            print(f'{name:8} {radial:7.3f} {body_height:8.3f} {floor:8.3f}  '
                  '✓ GREEN')
        else:
            all_green = False
            leg_name, z, msg = fail
            print(f'{name:8} {radial:7.3f} {body_height:8.3f} {floor:8.3f}  '
                  f'❌ RED @ {leg_name} z={z:.4f}: {msg[:70]}')

    print('')
    print('GREEN' if all_green else 'RED — mindestens ein Modus out-of-envelope')
    return 0 if all_green else 1


if __name__ == '__main__':
    sys.exit(main())
