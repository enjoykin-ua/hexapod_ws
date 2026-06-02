#!/usr/bin/env python3
# Copyright 2026 enjoykin — Apache-2.0
"""
Torque-/Hitze-Sweep (Phase 13 Finalisierung, Stage A1, CLI).

Sweept eine symmetrische Stand-Pose über (radial, body_height) und rechnet pro
Pose via ``hexapod_gait.joint_load`` die Gelenk-Auslastung. Findet die
last-minimale / best-balancierte Pose (Femur ≈ Tibia) — als Gegenstück zum
Live-RViz-Node (``torque_viz``).

Annahme: symmetrischer 6-Bein-Stand (jedes Bein Fuss bei (radial, 0, bh)).
CoG mittig → alle Beine gleich belastet (CoG-Modell = Even-Split im Symmetriefall).

Beispiel:
  python3 tools/torque_sweep.py --total-mass 3.0 \
      --radial-min 0.18 --radial-max 0.30 --radial-step 0.01 \
      --height-min -0.120 --height-max -0.060 --height-step 0.01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# hexapod_gait + hexapod_kinematics aus dem Workspace importierbar machen,
# falls nicht gesourct (Best-Effort; normal via `source install/setup.bash`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'
                       / 'hexapod_gait'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'
                       / 'hexapod_kinematics'))

from hexapod_gait.joint_load import compute_load, MassModel, SERVO_NM  # noqa: E402,E501
from hexapod_kinematics import HEXAPOD, IKError, leg_ik  # noqa: E402


_LEG1 = HEXAPOD.by_name('leg_1')


def _frange(lo: float, hi: float, step: float):
    n = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 4) for i in range(n)]


def _eval(radial: float, bh: float, masses: MassModel):
    """Return (femur%, tibia%, peak%, balance, margin_mm) oder None (unreachable)."""
    try:
        angles = leg_ik(radial, 0.0, bh, _LEG1)
    except IKError:
        return None
    all_angles = {cfg.name: angles for cfg in HEXAPOD.legs}
    load = compute_load(all_angles, masses=masses)
    leg = load.legs['leg_1']
    fp, tp = leg.femur.util_pct, leg.tibia.util_pct
    peak = max(fp, tp)
    return fp, tp, peak, abs(fp - tp), load.stability_margin_m * 1000.0


def main() -> int:
    """CLI-Einstieg: Sweep parsen, rechnen, Tabelle + Empfehlung ausgeben."""
    ap = argparse.ArgumentParser(
        description='Torque-/Hitze-Sweep (symmetrischer Stand).')
    ap.add_argument('--total-mass', type=float, default=None,
                    help='Echtes Gesamtgewicht kg (Default: URDF-Summe ~2.63).')
    ap.add_argument('--radial-min', type=float, default=0.18)
    ap.add_argument('--radial-max', type=float, default=0.30)
    ap.add_argument('--radial-step', type=float, default=0.01)
    ap.add_argument('--height-min', type=float, default=-0.120)
    ap.add_argument('--height-max', type=float, default=-0.060)
    ap.add_argument('--height-step', type=float, default=0.01)
    args = ap.parse_args()

    masses = MassModel(total_mass=args.total_mass)
    print('=== Torque-/Hitze-Sweep (symmetrischer 6-Bein-Stand) ===')
    print(f'Gesamtmasse: {masses.total():.3f} kg  '
          f'(Servo-Nenn: Femur/Tibia {SERVO_NM["femur"]:.2f} N·m, '
          f'Coxa {SERVO_NM["coxa"]:.2f} N·m; % = |τ|/Nenn, konservativ)')
    print()
    print('  radial   height   femur%   tibia%    peak%   balance   marge[mm]')

    best = None  # (peak, radial, bh, row)
    best_bal = None  # (balance, ...)
    for bh in _frange(args.height_min, args.height_max, args.height_step):
        for radial in _frange(args.radial_min, args.radial_max,
                              args.radial_step):
            res = _eval(radial, bh, masses)
            if res is None:
                print(f'  {radial:.3f}   {bh:+.3f}     —  (out of reach)')
                continue
            fp, tp, peak, bal, marge = res
            flag = '' if marge > 0 else '  ⚠instabil'
            print(f'  {radial:.3f}   {bh:+.3f}   {fp:6.1f}   {tp:6.1f}   '
                  f'{peak:6.1f}   {bal:6.1f}   {marge:7.0f}{flag}')
            if marge > 0:
                if best is None or peak < best[0]:
                    best = (peak, radial, bh)
                if best_bal is None or bal < best_bal[0]:
                    best_bal = (bal, radial, bh, fp, tp)

    print()
    if best:
        print(f'→ Last-minimal (kleinstes peak%): radial={best[1]:.3f}, '
              f'body_height={best[2]:+.3f} → peak {best[0]:.1f}%')
    if best_bal:
        print(f'→ Best balanciert (Femur≈Tibia): radial={best_bal[1]:.3f}, '
              f'body_height={best_bal[2]:+.3f} → '
              f'Femur {best_bal[3]:.1f}% / Tibia {best_bal[4]:.1f}% '
              f'(Δ {best_bal[0]:.1f}%)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
