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
import math
import subprocess
import sys
from pathlib import Path

from hexapod_gait.gait_node import parse_joint_limits_from_urdf
from hexapod_gait.joint_load import (
    MassModel,
    _convex_hull,
    _signed_margin,
    compute_load,
)

from hexapod_kinematics import HEXAPOD, IKError
from hexapod_kinematics.geometry import (
    base_to_leg_frame,
    leg_to_base_frame,
    rotate_xy,
)
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


# Phase 10: die Neutral-Pose der Vorderbeine bekommt einen LATERALEN Anteil
# (show_front_lat) — dadurch zeigen die Beine nach vorne statt schraeg nach
# aussen. Das Vorzeichen ist pro Bein gespiegelt, damit BEIDE nach vorne
# schwenken: leg_1 (vorne rechts, mount_yaw -45 Grad) und leg_6 (vorne links,
# +45 Grad) drehen gegensinnig auf die Koerper-Laengsachse zu.
_FRONT_LAT_SIGN = {'leg_1': +1.0, 'leg_6': -1.0}


def _front_lift_angles(show_radial, show_z, limits, show_lat=0.0,
                       offset=(0.0, 0.0, 0.0)):
    """
    Vorderbeine 1,6 angehoben.

    Bein-Frame-Ziel = ``(radial + d_radial, ±(lat + d_lat), z + d_vert)``.
    ``offset`` ist die Stick-/Trigger-Auslenkung ``(d_lat, d_vert, d_radial)``
    in Metern — bei ``(0,0,0)`` ist es die reine Neutral-Pose.
    """
    d_lat, d_vert, d_radial = offset
    out = {}
    reasons = {}
    for name in _FRONT_LEGS:
        cfg = HEXAPOD.by_name(name)
        sign = _FRONT_LAT_SIGN[name]
        target = (show_radial + d_radial,
                  sign * (show_lat + d_lat),
                  show_z + d_vert)
        ang, reason = _ik_or_none(target, cfg, limits.get(name))
        out[name] = ang
        reasons[name] = reason
    return out, reasons


def _support_feet_world(radial, body_height, shift):
    """
    Weltfeste Stuetzfuss-Positionen (Boden), bevor der Koerper gepitcht wird.

    Der Rueckversatz wird als ``+shift`` auf die Fuesse modelliert (aequivalent
    zu ``-shift`` des Koerpers) — Konvention aus B4.0, unveraendert.
    """
    feet = {}
    for name in _SUPPORT_LEGS:
        cfg = HEXAPOD.by_name(name)
        stand = leg_to_base_frame((radial, 0.0, body_height), cfg)
        feet[name] = (stand[0] + shift, stand[1], stand[2])
    return feet


def _support_angles(radial, body_height, shift, limits, pitch=0.0):
    """
    Stuetzbeine 2,3,4,5 mit optional gepitchtem Koerper.

    Die Fuesse stehen **weltfest** am Boden; kippt der Koerper um ``pitch``,
    wandern sie im koerperfesten Frame um ``-pitch``. Genau diese Punkte
    bekommt die IK. Bei ``pitch=0`` identisch zum B4.0-Verhalten.
    """
    out = {}
    reasons = {}
    world = _support_feet_world(radial, body_height, shift)
    for name in _SUPPORT_LEGS:
        cfg = HEXAPOD.by_name(name)
        foot_body = rotate_xy(world[name], 0.0, -pitch) if pitch else world[name]
        foot_leg = base_to_leg_frame(foot_body, cfg)
        ang, reason = _ik_or_none(foot_leg, cfg, limits.get(name))
        out[name] = ang
        reasons[name] = reason
    return out, reasons


def _margin_world(all_angles, world_feet, masses, pitch=0.0):
    """
    CoG-Marge im **Welt-Frame** (horizontale Ebene), Pitch-korrekt.

    ``compute_load`` liefert den Schwerpunkt im koerperfesten Frame. Ist der
    Koerper geneigt, ist dessen xy-Projektion **nicht** die Projektion, gegen
    die die Schwerkraft arbeitet — deshalb wird der CoG um ``+pitch`` in die
    Welt zurueckgedreht und dort gegen die weltfeste Fuss-Huelle geprueft.
    Bei ``pitch=0`` ist das Ergebnis identisch zu ``load.stability_margin_m``.
    """
    load = compute_load(all_angles, stance_legs=list(_SUPPORT_LEGS),
                        masses=masses)
    cog = rotate_xy(load.cog_base, 0.0, pitch) if pitch else load.cog_base
    hull = _convex_hull([(p[0], p[1]) for p in world_feet.values()])
    return _signed_margin((cog[0], cog[1]), hull), load


def _sweep_offsets(radial, body_height, shift, pitch, limits, masses,
                   show_radial, show_lat, show_z,
                   lat_scale, vert_scale, radial_scale, steps):
    """
    Worst-Case ueber die gesamte Stick-/Trigger-Huelle (Phase 10, FL-T1/T2).

    Die Neutral-Marge allein genuegt nicht: schwenken die Vorderbeine nach
    vorne/oben, zieht ihre Masse den Schwerpunkt Richtung Kippkante. Geprueft
    wird das kartesische Produkt aus Stick-X (lat, ±), Stick-Y (vert, ±) und
    Trigger (radial, **einseitig** 0..1 — der Trigger kennt keine Gegenrichtung).

    Returns ``(n_ok, n_total, worst_margin_m, worst_offset, sample_unreachable)``
    oder ``None``, wenn schon die Stuetz-Pose out-of-limit ist.
    """
    support, _ = _support_angles(radial, body_height, shift, limits, pitch)
    if not all(support[n] is not None for n in _SUPPORT_LEGS):
        return None
    world = _support_feet_world(radial, body_height, shift)

    n_ok = 0
    n_total = 0
    worst = None
    worst_at = None
    unreachable = []
    div = max(steps - 1, 1)
    for i in range(steps):
        s_lat = -1.0 + 2.0 * i / div
        for j in range(steps):
            s_vert = -1.0 + 2.0 * j / div
            for k in range(steps):
                s_trig = k / div          # einseitig 0..1
                n_total += 1
                offset = (s_lat * lat_scale,
                          s_vert * vert_scale,
                          s_trig * radial_scale)
                front, _r = _front_lift_angles(show_radial, show_z, limits,
                                               show_lat, offset)
                if not all(front[n] is not None for n in _FRONT_LEGS):
                    if len(unreachable) < 5:
                        unreachable.append(offset)
                    continue
                n_ok += 1
                all_angles = {}
                all_angles.update({n: support[n] for n in _SUPPORT_LEGS})
                all_angles.update({n: front[n] for n in _FRONT_LEGS})
                margin, _load = _margin_world(all_angles, world, masses, pitch)
                if worst is None or margin < worst:
                    worst = margin
                    worst_at = offset
    return n_ok, n_total, worst, worst_at, unreachable


def analyze(urdf_xacro, radial, body_height, show_radial, show_z,
            shift_max, shift_step, margin_goal, total_mass,
            show_lat=0.0, pitch_deg=0.0, sweep=False,
            lat_scale=0.04, vert_scale=0.05, radial_scale=0.03, steps=5):
    """Sweep body-shift-back, print CoG-margin + support-in-limit table."""
    limits = load_joint_limits(urdf_xacro)
    if not limits:
        print('FEHLER: keine URDF-Joint-Limits geladen (xacro leer/ungueltig).')
        return 2
    # Vorzeichen-Konvention: der ANWENDER-Parameter ist anschaulich
    # (positiv = Nase hoch). rotate_xy/REP-103 dreht bei positivem pitch die
    # Nase nach UNTEN (Ry: +X -> -Z), deshalb hier negiert. Engine und Tool
    # muessen dieselbe Konvention benutzen — sonst rechnet die Auslegung etwas
    # anderes als der Roboter tut.
    pitch = -math.radians(pitch_deg)

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
          f'  show_lat={show_lat:.3f}  show_z={show_z:+.3f}')
    if pitch_deg:
        print(f'Koerper-Pitch: {pitch_deg:+.1f} Grad'
              f'  (positiv = Nase hoch = CoG nach hinten)')
    masses = MassModel(total_mass=total_mass) if total_mass else MassModel()
    print(f'Masse-Modell: total={masses.total():.3f} kg'
          f'  (body_center={masses.body_center_mass():.3f} kg)')
    if show_lat:
        coxa_neutral = math.atan2(show_lat, show_radial)
        coxa_max = math.atan2(show_lat + lat_scale, show_radial)
        print(f'Coxa-Budget: neutral {coxa_neutral:+.3f} rad'
              f'  ({math.degrees(coxa_neutral):.1f} Grad),'
              f'  max mit Stick {coxa_max:+.3f} rad'
              f'  (Limit {l1.coxa_upper:+.3f})')
    # Bodenfreiheit des tiefsten Fusspunkts (ohne Pitch gerechnet = konservativ:
    # ein Nase-hoch-Pitch hebt die VORDEREN Fuesse zusaetzlich an).
    ground_clear_mm = (show_z - vert_scale - body_height) * 1000.0
    print(f'Bodenfreiheit tiefster Fusspunkt: {ground_clear_mm:.0f} mm'
          f'  (show_z {show_z:+.3f} - vert_scale {vert_scale:.3f}'
          f' vs. Boden {body_height:+.3f})')
    print()

    # Vorderbein-Hoch-Pose pruefen (s-unabhaengig).
    front, front_reasons = _front_lift_angles(show_radial, show_z, limits,
                                              show_lat)
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
        support, sup_reasons = _support_angles(radial, body_height, s, limits,
                                               pitch)
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
        margin_m, load = _margin_world(
            all_angles, _support_feet_world(radial, body_height, s),
            masses, pitch)
        margin_mm = margin_m * 1000.0
        goal_mark = ' <- >= goal' if margin_mm >= margin_goal * 1000.0 else ''
        print(f'{s:>9.3f} {margin_mm:>11.1f} '
              f'{("yes" if margin_mm > 0 else "NO"):>7} {"yes":>17}'
              f'  cog_x={load.cog_base[0]:+.4f}{goal_mark}')
        if margin_mm > 0:
            feasible.append((s, margin_m))

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
        print('  => Neutral-Pose BESTANDEN: sichere statische Show-Stuetz-Pose '
              'existiert.')
        rc = 0
    else:
        print(f'  Ziel (>= {margin_goal * 1000:.0f} mm) NICHT erreicht '
              f'(max {best[1] * 1000.0:.1f} mm).')
        print('  => Grenzwertig: Konzept/Parameter pruefen (mehr Shift? '
              'kleinerer Lift? Marge-Ziel senken?).')
        rc = 1

    if not sweep:
        return rc

    # ── Phase 10 (FL-T1/T2/T3): die AUSGELENKTE Huelle ───────────────────
    # Die Neutral-Marge oben ist nur die halbe Wahrheit — schwenken die
    # Vorderbeine nach vorne/oben, zieht ihre Masse den CoG Richtung Kante.
    shift_used = best[0]
    print()
    print('=' * 78)
    print(f'STICK-/TRIGGER-HUELLE bei shift={shift_used:.3f} m'
          f'  (lat +-{lat_scale:.3f}, vert +-{vert_scale:.3f},'
          f' radial 0..{radial_scale:.3f}, {steps}^3 Punkte)')
    print('=' * 78)
    res = _sweep_offsets(radial, body_height, shift_used, pitch, limits,
                         masses, show_radial, show_lat, show_z,
                         lat_scale, vert_scale, radial_scale, steps)
    if res is None:
        print('  Stuetz-Pose bei diesem Shift nicht in-limit — Abbruch.')
        return 1
    n_ok, n_total, worst, worst_at, unreachable = res
    pct = 100.0 * n_ok / n_total if n_total else 0.0
    print(f'  erreichbar: {n_ok}/{n_total} = {pct:.0f} %')
    if unreachable:
        print('  nicht erreichbar, Beispiele (d_lat, d_vert, d_radial):')
        for off in unreachable:
            print(f'    ({off[0]:+.3f}, {off[1]:+.3f}, {off[2]:+.3f})')
    if worst is None:
        print('  KEIN Punkt der Huelle erreichbar -> Auslegung unbrauchbar.')
        return 1
    print(f'  Worst-Case-CoG-Marge: {worst * 1000.0:.1f} mm'
          f'  bei (d_lat, d_vert, d_radial) ='
          f' ({worst_at[0]:+.3f}, {worst_at[1]:+.3f}, {worst_at[2]:+.3f})')
    print(f'  Bodenfreiheit tiefster Punkt: {ground_clear_mm:.0f} mm')

    ok_hull = pct >= 95.0
    ok_margin = worst * 1000.0 >= margin_goal * 1000.0
    ok_ground = ground_clear_mm >= 10.0
    print()
    print(f'  [{"OK " if ok_hull else "FAIL"}] Huelle >= 95 % erreichbar')
    print(f'  [{"OK " if ok_margin else "FAIL"}] Worst-Case-Marge >= '
          f'{margin_goal * 1000:.0f} mm')
    print(f'  [{"OK " if ok_ground else "FAIL"}] Bodenfreiheit >= 10 mm')
    if ok_hull and ok_margin and ok_ground:
        print('  => AUSLEGUNG BESTANDEN (FL-T1/T2/T3).')
        return rc
    print('  => AUSLEGUNG DURCHGEFALLEN — Parameter anpassen.')
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
    # ── Phase 10 (Show „Free-Leg") ───────────────────────────────────────
    ap.add_argument('--show-lat', type=float, default=0.0,
                    help='Lateraler Anteil der Neutral-Pose (m), Default 0.0 '
                         '(= B4-Verhalten, Bein zeigt in Montagerichtung). '
                         'Phase 10: 0.04 -> Beine zeigen nach vorne')
    ap.add_argument('--pitch-deg', type=float, default=0.0,
                    help='Koerper-Pitch (Grad), positiv = Nase hoch (intern negiert, '
                         'siehe analyze). Default 0.0 = B4-Verhalten')
    ap.add_argument('--sweep', action='store_true',
                    help='zusaetzlich die gesamte Stick-/Trigger-Huelle pruefen '
                         '(FL-T1/T2/T3) statt nur der Neutral-Pose')
    ap.add_argument('--lat-scale', type=float, default=0.04,
                    help='Stick-X-Skala fuer den Huellen-Sweep (m)')
    ap.add_argument('--vert-scale', type=float, default=0.05,
                    help='Stick-Y-Skala fuer den Huellen-Sweep (m)')
    ap.add_argument('--radial-scale', type=float, default=0.03,
                    help='Trigger-Skala fuer den Huellen-Sweep (m, einseitig)')
    ap.add_argument('--steps', type=int, default=5,
                    help='Rasterpunkte je Achse im Huellen-Sweep (Default 5)')
    args = ap.parse_args()
    return analyze(args.urdf_xacro, args.radial, args.body_height,
                   args.show_radial, args.show_z, args.shift_max,
                   args.shift_step, args.margin_goal, args.total_mass,
                   show_lat=args.show_lat, pitch_deg=args.pitch_deg,
                   sweep=args.sweep, lat_scale=args.lat_scale,
                   vert_scale=args.vert_scale,
                   radial_scale=args.radial_scale, steps=args.steps)


if __name__ == '__main__':
    sys.exit(main())
