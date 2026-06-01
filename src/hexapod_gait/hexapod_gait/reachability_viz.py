# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Reachability-Viz (Phase 13 Stage 1, Teil 1).

Zeigt die **erreichbare Fuss-Huelle pro Bein** als RViz-MarkerArray. Sweept
coxa/femur/tibia ueber ihre Grenzen, rechnet ``leg_fk`` → Fuss im Bein-Frame →
base_link (via mount_yaw/mount_xyz), und publisht zwei Punkt-Wolken:

  - **blau** : erreichbar mit dem AKTUELLEN URDF-Tibia-Limit (live aus der xacro).
  - **rot**  : ZUSAETZLICH erreichbar mit der vollen kalibrierten Tibia-Beuge
               (``tibia_full_upper``, default ~150° aus Stage 0.6.5).

Der rote Bereich = der verschenkte Fuss-Raum, den das konservative +1.30-Limit
aktuell abschneidet (Stage-1-Motivation).

Parameter (live setzbar, Re-Publish alle ~1.5 s):
  - ``leg``              : 'leg_1'..'leg_6' (default 'leg_1') oder 'all'.
                           Umschalten: ros2 param set /reachability_viz leg leg_3
  - ``resolution``       : Sweep-Schritte pro Gelenk (default 14 → 14³ Punkte/Bein).
  - ``tibia_full_upper`` : rotes Tibia-Beuge-Limit in rad (default 2.60 ≈ 149°).

Pure FK, keine HW/Sim noetig — laeuft gegen das URDF-Modell in RViz
(base_link-Frame vom robot_state_publisher; siehe reachability_viz.launch.py).
"""

from __future__ import annotations

import math
import subprocess

from ament_index_python.packages import get_package_share_directory

from geometry_msgs.msg import Point

from hexapod_gait.gait_node import parse_joint_limits_from_urdf
from hexapod_kinematics import HEXAPOD
from hexapod_kinematics.leg_ik import leg_fk

import rclpy
from rclpy.node import Node

from std_msgs.msg import ColorRGBA

from visualization_msgs.msg import Marker, MarkerArray


_LEG_NAMES = tuple(f'leg_{i}' for i in range(1, 7))


def _foot_base(leg_cfg, coxa: float, femur: float, tibia: float) -> tuple:
    """leg_fk (Bein-Frame) → base_link via mount_yaw (Rz) + mount_xyz."""
    x, y, z = leg_fk(coxa, femur, tibia, leg_cfg)
    yaw = leg_cfg.mount_yaw
    cy, sy = math.cos(yaw), math.sin(yaw)
    mx, my, mz = leg_cfg.mount_xyz
    return (mx + x * cy - y * sy, my + x * sy + y * cy, mz + z)


def _frange(lo: float, hi: float, n: int):
    if n <= 1:
        yield lo
        return
    step = (hi - lo) / (n - 1)
    for i in range(n):
        yield lo + i * step


class ReachabilityViz(Node):
    """Publisht die erreichbare Fuss-Huelle (blau=aktuell, rot=volle Tibia)."""

    def __init__(self) -> None:
        super().__init__('reachability_viz')
        self.declare_parameter('leg', 'leg_1')
        self.declare_parameter('resolution', 14)
        self.declare_parameter('tibia_full_upper', 2.60)

        self._pub = self.create_publisher(MarkerArray, 'reachability_markers', 1)

        # URDF-Limits live aus der xacro (gleiche Quelle wie das Plugin/Tools).
        xacro_path = (
            get_package_share_directory('hexapod_description')
            + '/urdf/hexapod.urdf.xacro')
        urdf_xml = subprocess.check_output(['xacro', xacro_path], text=True)
        self._limits = parse_joint_limits_from_urdf(urdf_xml)

        # Periodischer Re-Publish → ros2-param-set (leg-Umschaltung) wirkt
        # automatisch beim naechsten Tick; RViz bekommt die Marker auch bei
        # spaetem Verbinden.
        self._timer = self.create_timer(1.5, self._publish)
        self._publish()

    def _selected_legs(self) -> list:
        leg = self.get_parameter('leg').get_parameter_value().string_value
        if leg == 'all':
            return list(_LEG_NAMES)
        if leg in _LEG_NAMES:
            return [leg]
        self.get_logger().warn(
            f"leg='{leg}' unbekannt — nutze 'leg_1'. "
            f"Gueltig: {_LEG_NAMES} oder 'all'.")
        return ['leg_1']

    def _build_points(self, leg_names: list, n: int, tibia_full: float):
        """Sweep → (blaue Punkte, rote Punkte) in base_link."""
        blue: list[Point] = []
        red: list[Point] = []
        for name in leg_names:
            leg_cfg = HEXAPOD.by_name(name)
            lim = self._limits[name]
            t_lo = lim.tibia_lower
            t_hi_now = lim.tibia_upper            # aktuelles URDF-Limit (blau)
            t_hi_full = max(tibia_full, t_hi_now)  # rotes Voll-Limit
            for c in _frange(lim.coxa_lower, lim.coxa_upper, n):
                for f in _frange(lim.femur_lower, lim.femur_upper, n):
                    for t in _frange(t_lo, t_hi_full, n):
                        x, y, z = _foot_base(leg_cfg, c, f, t)
                        p = Point(x=x, y=y, z=z)
                        if t <= t_hi_now + 1e-9:
                            blue.append(p)
                        else:
                            red.append(p)
        return blue, red

    def _make_marker(self, ns: str, points: list, color: ColorRGBA) -> Marker:
        m = Marker()
        m.header.frame_id = 'base_link'
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = ns
        m.id = 0
        m.type = Marker.POINTS
        m.action = Marker.ADD
        m.scale.x = 0.004
        m.scale.y = 0.004
        m.color = color
        m.pose.orientation.w = 1.0
        m.points = points
        return m

    def _publish(self) -> None:
        n = max(2, self.get_parameter('resolution')
                .get_parameter_value().integer_value)
        tibia_full = self.get_parameter('tibia_full_upper') \
            .get_parameter_value().double_value
        legs = self._selected_legs()
        blue, red = self._build_points(legs, n, tibia_full)

        arr = MarkerArray()
        arr.markers.append(self._make_marker(
            'reach_current', blue,
            ColorRGBA(r=0.1, g=0.4, b=1.0, a=0.5)))
        arr.markers.append(self._make_marker(
            'reach_extra_tibia', red,
            ColorRGBA(r=1.0, g=0.15, b=0.1, a=0.7)))
        self._pub.publish(arr)
        self.get_logger().info(
            f"reachability: legs={legs} n={n} tibia_full={tibia_full:.2f} "
            f"→ {len(blue)} blau (aktuell) + {len(red)} rot (extra Tibia-Beuge)")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ReachabilityViz()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
