#!/usr/bin/env python3
# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0
"""
apex_meter — realer Fuß-Hub aus /joint_states (Block H / H1.5).

Misst, wie viel vom kommandierten ``step_height`` auf der Hardware WIRKLICH
ankommt: abonniert ``/joint_states``, rechnet pro Bein die Fuß-Position per
FK (Bein-Frame) und reportet den **Hub** = max(z) − min(z) über ein
Rolling-Fenster. Beim Laufen ist min(z) ≈ Stance-Höhe (body_height) und
max(z) ≈ real erreichter Schwung-Apex → Hub direkt mit ``step_height``
vergleichbar, ohne body_height kennen zu müssen.

Read-only (kein Publisher außer Konsole), Sim + HW identisch. Aufruf:

    # während der Roboter läuft (Sim oder HW, eigenes Terminal):
    python3 tools/apex_meter.py
    # Fenster/Takt anpassen:
    python3 tools/apex_meter.py --window 6.0 --period 1.0

Interpretation: ``hub`` deutlich < ``step_height`` ⇒ Verlust durch Servo-Lag
(schneller Halbsinus) + Einfedern der Stützbeine (Körper sackt beim Tripod).
Gegenprobe: ``cycle_time`` erhöhen → Lag-Anteil sinkt; der Rest ist Einfedern.
"""

from __future__ import annotations

import argparse
import time
from collections import deque

from hexapod_kinematics import HEXAPOD, leg_fk
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class ApexMeter(Node):
    """Rolling-Fenster über die FK-Fuß-Höhe je Bein → Hub-Report."""

    def __init__(self, window_s: float, period_s: float):
        """Fenster (s) + Report-Periode (s) festlegen, Sub/Timer anlegen."""
        super().__init__('apex_meter')
        self._window_s = window_s
        self._legs = {
            leg.name: leg for leg in HEXAPOD.legs
        }
        # pro Bein: deque[(monotonic_t, z)]
        self._hist: dict[str, deque] = {
            name: deque() for name in self._legs
        }
        self.create_subscription(
            JointState, '/joint_states', self._on_joint_states, 10)
        self.create_timer(period_s, self._report)
        self.get_logger().info(
            f'apex_meter: Fenster {window_s:.1f}s, Report alle {period_s:.1f}s '
            f'— hub = max(z)−min(z) je Bein (vergleiche mit step_height).')

    def _on_joint_states(self, msg: JointState) -> None:
        now = time.monotonic()
        idx = {name: i for i, name in enumerate(msg.name)}
        for leg_name, leg in self._legs.items():
            try:
                angles = tuple(
                    msg.position[idx[f'{leg_name}_{j}_joint']]
                    for j in ('coxa', 'femur', 'tibia')
                )
            except (KeyError, IndexError):
                continue  # unvollständige Message (z.B. Teil-Publisher)
            z = leg_fk(*angles, leg)[2]
            hist = self._hist[leg_name]
            hist.append((now, z))
            cutoff = now - self._window_s
            while hist and hist[0][0] < cutoff:
                hist.popleft()

    def _report(self) -> None:
        parts = []
        for n in range(1, 7):
            hist = self._hist[f'leg_{n}']
            if len(hist) < 5:
                parts.append(f'L{n} ---')
                continue
            zs = [z for _, z in hist]
            hub_mm = (max(zs) - min(zs)) * 1000.0
            parts.append(f'L{n} {hub_mm:5.1f}')
        self.get_logger().info('hub[mm] ' + ' | '.join(parts))


def main() -> None:
    """CLI-Einstieg: Args parsen, Node spinnen bis Ctrl-C."""
    parser = argparse.ArgumentParser(
        description='Realer Fuß-Hub (max−min FK-z) je Bein aus /joint_states.')
    parser.add_argument('--window', type=float, default=10.0,
                        help='Rolling-Fenster in s (default 10 — deckt >=2 '
                             'Gait-Zyklen bei cycle_time 2.0).')
    parser.add_argument('--period', type=float, default=2.0,
                        help='Report-Intervall in s (default 2).')
    args, ros_args = parser.parse_known_args()

    rclpy.init(args=ros_args)
    node = ApexMeter(window_s=args.window, period_s=args.period)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
