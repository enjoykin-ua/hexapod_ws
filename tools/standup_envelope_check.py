#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
================================================================================
Stand-up-Envelope-Check Tool  (Phase 13 Stage 0.7, Arbeitspaket E)
================================================================================

Offline-Werkzeug, das den **kartesischen schürffreien Aufsteh-Pfad** rein
kinematisch durchrechnet — BEVOR Engine-Code angefasst wird. Beantwortet die
offenen §8-Designfragen des Plans
``docs_raspi/phase_13_stage_0_7_cartesian_standup_plan.md`` datengetrieben:

  - §8.7  body_height_start (Coxa-Höhe bei aufliegendem Bauch)
  - §8.4  Reachability/In-Limits über Phase 1 (Touchdown) + Phase 2 (Push)
  - §8.1  Phase-1-Methode: reicht ein direkter kartesischer Lerp ohne
          vorzeitigen Bodenkontakt + ohne IK-Limit-Verletzung?

Pure Python, kein ROS-Runtime — nutzt direkt ``hexapod_kinematics``
(echte ``leg_ik``/``leg_fk``) und liest die URDF-Joint-Limits via xacro
(dieselbe Quelle wie das Plugin auf der HW). KEINE Parallel-Mathe.

PRÜFT (kinematisch):
  - body_height_start aus der Bauch-Geometrie
  - Phase 1 (power_on_mid → Touchdown): jeder Zwischen-Foot ∈ URDF-Limits,
    erreichbar, und Fuß-Welt-z bleibt über Grund bis zum Touchdown
    (= kein vorzeitiges Schürfen in Phase 1)
  - Phase 2 (Touchdown → Stand, radial fix): jeder Zwischen-Foot ∈ Limits,
    erreichbar, Knie-Beugung (Singularitäts-Abstand), rad-Margin zum Limit

PRÜFT NICHT (→ Sim / HW):
  - Servo-rad/s, Drehmoment/Stall, reale Reibung/Grip, echte Bauch-Auflagehöhe,
    Strom (das eigentliche Done-Kriterium misst der Boden-Test 0.8)

Aufruf:
  python3 tools/standup_envelope_check.py
  python3 tools/standup_envelope_check.py --radial 0.295 --bh-final -0.080 --steps 20
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

from hexapod_kinematics import HEXAPOD, IKError
from hexapod_kinematics.leg_ik import leg_fk, leg_ik
from hexapod_gait.gait_node import parse_joint_limits_from_urdf

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_URDF_XACRO = (
    _REPO_ROOT / 'src/hexapod_description/urdf/hexapod.urdf.xacro')

# --- Geometrie-Konstanten (Single Source: hexapod_physical_properties.xacro
#     + hexapod_kinematics/config.py). Hier gespiegelt fuer die bh_start-
#     Rechnung; bei Aenderung dort nachziehen. ---------------------------------
_BODY_HEIGHT_BOX = 0.043      # base_link Kollisions-Box-Hoehe (m)
_LEG_MOUNT_Z = 0.0            # Coxa-Achse auf base_link-Mitte
_FOOT_RADIUS = 0.008          # Foot-Kugel-Radius (m)

# power_on_mid (1500 us) rad pro Bein = pulse_us_to_radians(1500) mit der
# aktuellen Cal. Bein-Umbau (leg_changes): neu gerechnet aus servo_mapping.yaml
# (S3.1), Coxa gegen die alte Cal validiert (unveraendert). Bei Neu-Cal nachziehen
# — weitere Konsumenten: hexapod.ros2_control.xacro initial + die 3 gait-Tests.
_POWER_ON_MID = {
    'leg_1': (-0.0692, -0.7732, 0.8491),
    'leg_2': (0.1556, -0.9523, 0.9089),
    'leg_3': (-0.1115, -0.8431, 1.0046),
    'leg_4': (0.0259, -0.8157, 1.0485),
    'leg_5': (0.1037, -0.8276, 0.9745),
    'leg_6': (0.0519, -0.7697, 0.8464),
}


def load_joint_limits(urdf_xacro_path: Path) -> dict:
    """Run xacro on the given file and parse per-leg joint limits."""
    if not urdf_xacro_path.exists():
        raise FileNotFoundError(f'URDF xacro not found: {urdf_xacro_path}')
    try:
        urdf_xml = subprocess.check_output(
            ['xacro', str(urdf_xacro_path)], text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'xacro failed for {urdf_xacro_path}: {e}') from e
    return parse_joint_limits_from_urdf(urdf_xml)


def coxa_height_at_belly() -> float:
    """Coxa-Achsen-Hoehe ueber Grund, wenn der Bauch aufliegt (m)."""
    # Box zentriert auf base_link, Coxa bei leg_mount_z → Unterkante bei
    # -box/2; aufliegend = Unterkante auf Grund → Coxa bei box/2 + mount_z.
    return _BODY_HEIGHT_BOX / 2.0 + _LEG_MOUNT_Z


def body_height_start() -> float:
    """foot_z relativ Coxa, sodass die Fuss-Kugel den Boden beruehrt (m)."""
    return _FOOT_RADIUS - coxa_height_at_belly()


def knee_bend_deg(rx: float, rz: float, leg_cfg) -> float:
    """Knie-Beugung in Grad (0 = voll gestreckt = Singularitaet)."""
    l_f, l_t = leg_cfg.L_femur, leg_cfg.L_tibia
    d = math.hypot(rx - leg_cfg.L_coxa, rz)
    c = (l_f * l_f + l_t * l_t - d * d) / (2.0 * l_f * l_t)
    c = max(-1.0, min(1.0, c))
    return 180.0 - math.degrees(math.acos(c))


def radial_of(foot: tuple) -> float:
    """Horizontale (radiale) Reichweite eines Foot-Punkts im Bein-Frame."""
    return math.hypot(foot[0], foot[1])


def smoothstep(p: float) -> float:
    return p * p * (3.0 - 2.0 * p)


def _check_pose(foot: tuple, leg_cfg, limits, lim) -> dict:
    """leg_ik fuer einen Foot-Punkt; sammelt Status + rad-Margins."""
    out = {'foot': foot, 'ok': True, 'reason': '', 'angles': None,
           'min_margin': math.inf, 'tight_joint': ''}
    try:
        angles = leg_ik(foot[0], foot[1], foot[2], leg_cfg, limits)
    except IKError as e:
        out['ok'] = False
        out['reason'] = str(e)
        return out
    out['angles'] = angles
    # rad-Margin zum jeweils naechsten URDF-Limit pro Joint
    bounds = [
        (lim.coxa_lower, lim.coxa_upper),
        (lim.femur_lower, lim.femur_upper),
        (lim.tibia_lower, lim.tibia_upper),
    ]
    names = ('coxa', 'femur', 'tibia')
    for a, (lo, hi), nm in zip(angles, bounds, names):
        margin = min(a - lo, hi - a)
        if margin < out['min_margin']:
            out['min_margin'] = margin
            out['tight_joint'] = nm
    return out


def analyze(urdf_xacro: Path, radial: float, bh_final: float,
            steps: int) -> int:
    joint_limits = load_joint_limits(urdf_xacro)
    bh_start = body_height_start()
    coxa_z = coxa_height_at_belly()

    print('=' * 78)
    print('Stand-up-Envelope-Check — kartesisches schürffreies Aufstehen (0.7)')
    print('=' * 78)
    print(f'Bauch-Box-Höhe         : {_BODY_HEIGHT_BOX * 1000:.1f} mm')
    print(f'Coxa über Grund (Bauch): {coxa_z * 1000:.1f} mm')
    print(f'Foot-Radius            : {_FOOT_RADIUS * 1000:.1f} mm')
    print(f'→ body_height_start    : {bh_start * 1000:.2f} mm  (§8.7)')
    print(f'radial_final           : {radial:.3f} m')
    print(f'body_height_final      : {bh_final:.3f} m')
    print(f'Push-Schritte          : {steps}')
    print()

    all_ok = True

    for leg in HEXAPOD.legs:
        lim = joint_limits.get(leg.name)
        if lim is None:
            print(f'[{leg.name}] KEINE URDF-Limits gefunden — ABBRUCH')
            return 2
        pom = _POWER_ON_MID[leg.name]
        start_foot = leg_fk(pom[0], pom[1], pom[2], leg)
        touchdown = (radial, 0.0, bh_start)
        stand = (radial, 0.0, bh_final)

        print(f'── {leg.name} ' + '─' * (74 - len(leg.name)))
        print(f'  power_on_mid foot : radial {radial_of(start_foot):.3f} '
              f'z {start_foot[2] * 1000:+.1f} mm  '
              f'(Welt-z {(coxa_z + start_foot[2]) * 1000:+.1f} mm)')

        # --- Phase 1: power_on_mid → Touchdown (direkter kartesischer Lerp) ---
        p1_ok = True
        p1_min_margin = math.inf
        p1_min_worldz = math.inf
        p1_tight = ''
        for i in range(steps + 1):
            s = smoothstep(i / steps)
            foot = tuple(start_foot[k] + s * (touchdown[k] - start_foot[k])
                         for k in range(3))
            r = _check_pose(foot, leg, lim, lim)
            world_z = coxa_z + foot[2]
            # vor dem letzten Schritt darf der Fuss den Boden nicht beruehren
            if i < steps and world_z <= _FOOT_RADIUS:
                p1_ok = False
            if world_z < p1_min_worldz:
                p1_min_worldz = world_z
            if not r['ok']:
                p1_ok = False
                p1_tight = f"@p={i/steps:.2f}: {r['reason']}"
            elif r['min_margin'] < p1_min_margin:
                p1_min_margin = r['min_margin']
                p1_tight = f"{r['tight_joint']} (rad-Margin {r['min_margin']:.3f})"

        td = _check_pose(touchdown, leg, lim, lim)
        print(f'  Touchdown  ({radial:.3f}, 0, {bh_start * 1000:+.1f}mm): '
              + ('OK ' if td['ok'] else f"FAIL — {td['reason']}")
              + (f", Knie {knee_bend_deg(radial, bh_start, leg):.0f}°"
                 if td['ok'] else ''))
        p1_status = 'OK ' if p1_ok else 'FAIL'
        print(f'  Phase 1 (cart Lerp): {p1_status}  min-rad-Margin '
              f'{p1_min_margin:.3f} ({p1_tight});  '
              f'min Fuß-Welt-z {p1_min_worldz * 1000:+.1f} mm '
              f'(>{_FOOT_RADIUS * 1000:.0f} = kein vorzeitiger Kontakt)')

        # --- Phase 2: Touchdown → Stand (radial fix, nur body_height) --------
        p2_ok = True
        p2_min_margin = math.inf
        p2_tight = ''
        knee_lo, knee_hi = math.inf, -math.inf
        for i in range(steps + 1):
            s = smoothstep(i / steps)
            bh = bh_start + s * (bh_final - bh_start)
            foot = (radial, 0.0, bh)
            r = _check_pose(foot, leg, lim, lim)
            kb = knee_bend_deg(radial, bh, leg)
            knee_lo, knee_hi = min(knee_lo, kb), max(knee_hi, kb)
            if not r['ok']:
                p2_ok = False
                p2_tight = f"@bh={bh * 1000:.0f}mm: {r['reason']}"
            elif r['min_margin'] < p2_min_margin:
                p2_min_margin = r['min_margin']
                p2_tight = f"{r['tight_joint']} (rad-Margin {r['min_margin']:.3f})"
        p2_status = 'OK ' if p2_ok else 'FAIL'
        print(f'  Phase 2 (push fix) : {p2_status}  min-rad-Margin '
              f'{p2_min_margin:.3f} ({p2_tight});  '
              f'Knie {knee_lo:.0f}°→{knee_hi:.0f}° (0°=Singularität)')

        all_ok = all_ok and p1_ok and p2_ok and td['ok']
        print()

    print('=' * 78)
    print('ERGEBNIS: ' + ('GRÜN — Aufsteh-Pfad kinematisch sauber für alle 6 '
                          'Beine' if all_ok else
                          'ROT — mindestens ein Bein/Schritt verletzt Limits '
                          'oder schürft in Phase 1'))
    print('=' * 78)
    print('Hinweis: kinematisch ok ≠ Strom ok. Der Strom-Beweis (~400 mA '
          'statt >3,5 A) kommt erst am Boden-Test (Stage 0.8).')
    return 0 if all_ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--urdf', type=Path, default=_DEFAULT_URDF_XACRO,
                    help=f'URDF xacro (default: {_DEFAULT_URDF_XACRO})')
    ap.add_argument('--radial', type=float, default=0.295,
                    help='radial_final (Touchdown + Stand), default 0.295')
    ap.add_argument('--bh-final', type=float, default=-0.080,
                    help='body_height_final (Stand), default -0.080')
    ap.add_argument('--steps', type=int, default=20,
                    help='Zwischenschritte pro Phase, default 20')
    args = ap.parse_args()
    return analyze(args.urdf, args.radial, args.bh_final, args.steps)


if __name__ == '__main__':
    sys.exit(main())
