#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
================================================================================
Show-Pose CoG-/Reachability-Check  (Block B4 — Body-Pose / Show-Pose, B4.0)
================================================================================

KRITISCHER VORAB-CHECK fuer B4 (vor jeglichem Engine-Code, CLAUDE.md §4 +
Memory ``feedback_validate_hardware_hypothesis_via_code``).

Frage (B4.0, Plan ``project_finalization/B4_show_pose_plan.md`` §5):
  Gibt es einen Koerper-Rueckversatz ``body_shift_back``, bei dem
    (a) die CoG-Marge im 4-Bein-Stuetzpolygon (leg_2,3,4,5) komfortabel > 0
        ist (Ziel >= 30-50 mm), waehrend die 2 Vorderbeine (leg_1, leg_6)
        angehoben in der Luft sind, UND
    (b) alle 4 Stuetzbeine dabei in-reach UND in den URDF-Joint-Limits
        bleiben (der Rueckversatz zieht die Stuetzfuesse im Body-Frame nach
        vorne -> kann Reichweite/coxa-Limit sprengen)?

Wenn KEIN solcher Shift existiert -> Show-Pose-Konzept anpassen (kleinerer
Lift / Stuetze anders) BEVOR codiert wird.

Modell (rein kinematisch, quasi-statisch):
  - Stand-Pose: jeder Fuss im Bein-Frame bei (radial, 0, body_height).
  - Koerper-Rueckversatz ``s``: Koerper translatiert um -s entlang base-X,
    die Fuesse bleiben weltfest am Boden -> im Body-Frame wandern die
    Stuetzfuesse um +s nach vorne (+X). (= Plan §3 STATE_SHOW_ENTER Phase a.)
  - Vorderbeine 1,6: angehoben in eine neutrale Hoch-Pose (Bein-Frame
    (show_radial, 0, show_z)), unabhaengig von s (in der Luft, body-fest).
  - Pro Kandidat-Pose: leg_ik (mit URDF-Limits!) fuer alle 6 Beine, dann
    ``joint_load.compute_load`` mit stance_legs = [leg_2,3,4,5].

Nutzt die ECHTEN ``leg_ik``/``leg_fk`` + ``joint_load`` (dieselbe Mathe wie
Engine/HW) und die ECHTEN URDF-Joint-Limits via xacro (dieselbe Quelle wie das
Plugin auf der HW, Goldene Regel #2/#3 ai_navigation.md). KEINE Parallel-Mathe.

PRUEFT NICHT (-> Sim / HW, Plan §6 scope-out):
  - Selbst-Kollision der Vorderbeine (A4 pausiert -> visuell in Sim)
  - dynamisches Kippen unter Last (quasi-statisch via CoG-Marge)
  - Servo-Stall/Drehmoment am Extrem (HW-Beobachtung)

Aufruf:
  python3 tools/show_pose_cog_check.py
  python3 tools/show_pose_cog_check.py --show-radial 0.12 --show-z 0.04
  python3 tools/show_pose_cog_check.py --radial 0.215 --body-height -0.120 \
      --shift-max 0.12 --shift-step 0.005 --margin-goal 0.040
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from hexapod_gait.gait_node import parse_joint_limits_from_urdf
from hexapod_gait.joint_load import MassModel, compute_load

from hexapod_kinematics import HEXAPOD, IKError
from hexapod_kinematics.geometry import base_to_leg_frame, leg_to_base_frame
from hexapod_kinematics.leg_ik import leg_ik


_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_URDF_XACRO = (
    _REPO_ROOT / 'src/hexapod_description/urdf/hexapod.urdf.xacro')

# Bein-Layout (config.py): 1=vorne-R, 2=mitte-R, 3=hinten-R,
#                          4=hinten-L, 5=mitte-L, 6=vorne-L.
_SUPPORT_LEGS = ('leg_2', 'leg_3', 'leg_4', 'leg_5')
_FRONT_LEGS = ('leg_1', 'leg_6')


def load_joint_limits(urdf_xacro_path: Path) -> dict:
    """Run xacro on the given file and parse per-leg joint limits (URDF=HW)."""
    if not urdf_xacro_path.exists():
        raise FileNotFoundError(f'URDF xacro not found: {urdf_xacro_path}')
    try:
        urdf_xml = subprocess.check_output(
            ['xacro', str(urdf_xacro_path)], text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f'xacro failed for {urdf_xacro_path}: {e}') from e
    return parse_joint_limits_from_urdf(urdf_xml)


def _ik_or_none(foot_leg, cfg, limits):
    """leg_ik mit URDF-Limit-Pruefung; (angles, None) ok / (None, reason)."""
    try:
        ang = leg_ik(foot_leg[0], foot_leg[1], foot_leg[2], cfg, limits)
        return ang, None
    except IKError as e:
        return None, str(e)


def _front_lift_angles(show_radial, show_z, limits):
    """Vorderbeine 1,6 angehoben: Bein-Frame (show_radial, 0, show_z)."""
    out = {}
    reasons = {}
    for name in _FRONT_LEGS:
        cfg = HEXAPOD.by_name(name)
        ang, reason = _ik_or_none((show_radial, 0.0, show_z), cfg,
                                  limits.get(name))
        out[name] = ang
        reasons[name] = reason
    return out, reasons


def _support_angles(radial, body_height, shift, limits):
    """Stuetzbeine 2,3,4,5: Stand-Fuss +shift (base-X), zurueck in Bein-Frame."""
    out = {}
    reasons = {}
    for name in _SUPPORT_LEGS:
        cfg = HEXAPOD.by_name(name)
        # Stand-Fuss im Bein-Frame -> base, +shift nach vorne, -> Bein-Frame.
        foot_base_stand = leg_to_base_frame((radial, 0.0, body_height), cfg)
        foot_base_shift = (foot_base_stand[0] + shift,
                           foot_base_stand[1], foot_base_stand[2])
        foot_leg = base_to_leg_frame(foot_base_shift, cfg)
        ang, reason = _ik_or_none(foot_leg, cfg, limits.get(name))
        out[name] = ang
        reasons[name] = reason
    return out, reasons


def analyze(urdf_xacro, radial, body_height, show_radial, show_z,
            shift_max, shift_step, margin_goal, total_mass):
    """Sweep body-shift-back, print CoG-margin + support-in-limit table."""
    limits = load_joint_limits(urdf_xacro)
    if not limits:
        print('FEHLER: keine URDF-Joint-Limits geladen (xacro leer/ungueltig).')
        return 2

    # URDF-Limits ueberblick (sollte alle 6 Beine identisch sein, Stage F).
    l1 = limits['leg_1']
    print('=' * 78)
    print('B4.0 Show-Pose CoG-/Reachability-Check')
    print('=' * 78)
    print(f'URDF-Limits (leg_1, rad): coxa [{l1.coxa_lower:+.3f},'
          f' {l1.coxa_upper:+.3f}]  femur [{l1.femur_lower:+.3f},'
          f' {l1.femur_upper:+.3f}]  tibia [{l1.tibia_lower:+.3f},'
          f' {l1.tibia_upper:+.3f}]')
    print(f'Stand-Pose: radial={radial:.3f}  body_height={body_height:+.3f}')
    print(f'Vorderbein-Hoch-Pose: show_radial={show_radial:.3f}'
          f'  show_z={show_z:+.3f}')
    masses = MassModel(total_mass=total_mass) if total_mass else MassModel()
    print(f'Masse-Modell: total={masses.total():.3f} kg'
          f'  (body_center={masses.body_center_mass():.3f} kg)')
    print()

    # Vorderbein-Hoch-Pose pruefen (s-unabhaengig).
    front, front_reasons = _front_lift_angles(show_radial, show_z, limits)
    front_ok = all(front[n] is not None for n in _FRONT_LEGS)
    print('--- Vorderbeine (1,6) Hoch-Pose ---')
    for name in _FRONT_LEGS:
        if front[name] is not None:
            c, f, t = front[name]
            print(f'  {name}: OK  coxa={c:+.3f} femur={f:+.3f} tibia={t:+.3f}')
        else:
            print(f'  {name}: INFEASIBLE  {front_reasons[name]}')
    if not front_ok:
        print('\n>> Vorderbein-Hoch-Pose nicht erreichbar -> show_radial/'
              'show_z anpassen. Abbruch.')
        return 1
    print()

    # Shift-Sweep.
    print('--- Body-Shift-Sweep (Stuetze 2,3,4,5; Vorderbeine in der Luft) ---')
    header = (f'{"shift[m]":>9} {"margin[mm]":>11} {"stable":>7} '
              f'{"support in-limit":>17}  notes')
    print(header)
    print('-' * len(header))

    n_steps = int(round(shift_max / shift_step)) + 1
    feasible = []   # (shift, margin_m)
    for i in range(n_steps):
        s = round(i * shift_step, 6)
        support, sup_reasons = _support_angles(radial, body_height, s, limits)
        sup_ok = all(support[n] is not None for n in _SUPPORT_LEGS)

        if not sup_ok:
            bad = [n for n in _SUPPORT_LEGS if support[n] is None]
            note = '; '.join(f'{n}: {sup_reasons[n].split(":")[0]}'
                             for n in bad)
            print(f'{s:>9.3f} {"--":>11} {"--":>7} {"NO":>17}  {note}')
            continue

        all_angles = {}
        all_angles.update({n: support[n] for n in _SUPPORT_LEGS})
        all_angles.update({n: front[n] for n in _FRONT_LEGS})
        load = compute_load(all_angles, stance_legs=list(_SUPPORT_LEGS),
                            masses=masses)
        margin_mm = load.stability_margin_m * 1000.0
        goal_mark = ' <- >= goal' if margin_mm >= margin_goal * 1000.0 else ''
        print(f'{s:>9.3f} {margin_mm:>11.1f} '
              f'{("yes" if load.stable else "NO"):>7} {"yes":>17}'
              f'  cog_x={load.cog_base[0]:+.4f}{goal_mark}')
        if load.stable and margin_mm > 0:
            feasible.append((s, load.stability_margin_m))

    print()
    print('=' * 78)
    if not feasible:
        print('ERGEBNIS: KEIN sicherer Shift gefunden (keine Pose mit Marge>0 '
              'UND allen Stuetzbeinen in-limit).')
        print('-> B4-Konzept anpassen (kleinerer Front-Lift / andere Stuetze) '
              'BEVOR codiert wird.')
        return 1

    best = max(feasible, key=lambda t: t[1])
    goal_hits = [t for t in feasible if t[1] * 1000.0 >= margin_goal * 1000.0]
    print(f'ERGEBNIS: {len(feasible)} Shift(s) mit Marge>0 + Stuetze in-limit.')
    print(f'  Beste Marge: {best[1] * 1000.0:.1f} mm bei shift={best[0]:.3f} m.')
    if goal_hits:
        lo = min(t[0] for t in goal_hits)
        hi = max(t[0] for t in goal_hits)
        print(f'  Ziel (>= {margin_goal * 1000:.0f} mm) erreicht fuer '
              f'shift in [{lo:.3f}, {hi:.3f}] m.')
        print('  => B4.0 BESTANDEN: sichere statische Show-Stuetz-Pose '
              'existiert.')
        return 0
    print(f'  Ziel (>= {margin_goal * 1000:.0f} mm) NICHT erreicht '
          f'(max {best[1] * 1000.0:.1f} mm).')
    print('  => Grenzwertig: Konzept/Parameter pruefen (mehr Shift? kleinerer '
          'Lift? Marge-Ziel senken?).')
    return 1


def main() -> int:
    """Parse CLI args and run the B4.0 show-pose CoG/reachability check."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--urdf-xacro', type=Path, default=_DEFAULT_URDF_XACRO,
                    help=f'URDF xacro (default: {_DEFAULT_URDF_XACRO})')
    ap.add_argument('--radial', type=float, default=0.215,
                    help='Stand-Pose radial_distance (m), Default 0.215')
    ap.add_argument('--body-height', type=float, default=-0.120,
                    help='Stand-Pose body_height (m), Default -0.120')
    ap.add_argument('--show-radial', type=float, default=0.12,
                    help='Vorderbein-Hoch-Pose radial (m), Default 0.12')
    ap.add_argument('--show-z', type=float, default=0.04,
                    help='Vorderbein-Hoch-Pose z im Bein-Frame (m), Default +0.04')
    ap.add_argument('--shift-max', type=float, default=0.12,
                    help='Max. Body-Rueckversatz (m), Default 0.12')
    ap.add_argument('--shift-step', type=float, default=0.005,
                    help='Sweep-Schrittweite (m), Default 0.005')
    ap.add_argument('--margin-goal', type=float, default=0.040,
                    help='Ziel-CoG-Marge (m), Default 0.040 (= 40 mm)')
    ap.add_argument('--total-mass', type=float, default=None,
                    help='Echtes Gesamtgewicht (kg); Default = URDF-Summe')
    args = ap.parse_args()
    return analyze(args.urdf_xacro, args.radial, args.body_height,
                   args.show_radial, args.show_z, args.shift_max,
                   args.shift_step, args.margin_goal, args.total_mass)


if __name__ == '__main__':
    sys.exit(main())
