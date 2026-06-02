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
Torque-/Hitze-Viz (Phase 13 Finalisierung, Stage A1, Live-RViz-Node).

Abonniert ``/joint_states``, rechnet via ``joint_load.compute_load`` die
quasi-statische Gelenk-Auslastung und publisht eine ``MarkerArray``:

  - **Pro Gelenk ein TEXT_VIEW_FACING-Marker DIREKT an der Gelenk-Position**
    (base_link) mit ``"<N·m> / <%>"``, eingefärbt nach %-Schwelle (grün/gelb/rot).
  - **CoG-Marker** (Kugel) auf Boden-Ebene, **Stütz-Polygon** (LINE_STRIP),
    **Stabilitäts-Marge** als Text.

Stütz-Erkennung: Füße deren z (base) ≈ Minimum (am Boden) gelten als Stütz;
angehobene als Swing (``stance_z_threshold``). Reiner Stand → alle 6 Stütz.

Reagiert live auf jsp-Slider / Sim / HW. Pure-Viz, ändert nichts am Roboter.
Param ``total_mass`` (kg) für echte Zahlen (Default 0 = URDF-Massen).
"""

from __future__ import annotations

import math

from geometry_msgs.msg import Point

from hexapod_gait.joint_load import compute_load, MassModel
from hexapod_kinematics import HEXAPOD, leg_fk

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState

from std_msgs.msg import ColorRGBA

from visualization_msgs.msg import Marker, MarkerArray


_GREEN = ColorRGBA(r=0.1, g=0.8, b=0.1, a=1.0)
_YELLOW = ColorRGBA(r=0.95, g=0.8, b=0.1, a=1.0)
_RED = ColorRGBA(r=0.95, g=0.15, b=0.1, a=1.0)
_CYAN = ColorRGBA(r=0.1, g=0.8, b=0.9, a=1.0)


def _foot_base(angles, cfg):
    """Fuss-Position (base_link) via leg_fk + mount_yaw/xyz."""
    x, y, z = leg_fk(*angles, cfg)
    cy, sy = math.cos(cfg.mount_yaw), math.sin(cfg.mount_yaw)
    mx, my, mz = cfg.mount_xyz
    return (mx + x * cy - y * sy, my + x * sy + y * cy, mz + z)


class TorqueViz(Node):
    """Publisht Gelenk-Auslastung (N·m + %) als RViz-Marker am Modell."""

    def __init__(self) -> None:
        super().__init__('torque_viz')
        self.declare_parameter('total_mass', 0.0)        # 0 = URDF-Massen
        self.declare_parameter('stance_z_threshold', 0.02)
        self.declare_parameter('pct_green_below', 50.0)
        self.declare_parameter('pct_yellow_below', 80.0)
        self.declare_parameter('text_size', 0.018)

        self._pub = self.create_publisher(MarkerArray, 'torque_markers', 1)
        self._last_js: JointState | None = None
        self.create_subscription(
            JointState, '/joint_states', self._on_js, 10)
        # Re-Publish ~5 Hz aus dem letzten /joint_states (RViz-schonend).
        self.create_timer(0.2, self._publish)

    def _on_js(self, msg: JointState) -> None:
        self._last_js = msg

    def _color(self, pct: float) -> ColorRGBA:
        g = self.get_parameter('pct_green_below').value
        y = self.get_parameter('pct_yellow_below').value
        if pct < g:
            return _GREEN
        if pct < y:
            return _YELLOW
        return _RED

    def _angles_from_js(self, msg: JointState) -> dict | None:
        pos = dict(zip(msg.name, msg.position))
        out = {}
        for cfg in HEXAPOD.legs:
            try:
                out[cfg.name] = (
                    pos[f'{cfg.name}_coxa_joint'],
                    pos[f'{cfg.name}_femur_joint'],
                    pos[f'{cfg.name}_tibia_joint'],
                )
            except KeyError:
                return None
        return out

    def _stance(self, all_angles: dict) -> tuple[list, float]:
        feet_z = {
            cfg.name: _foot_base(all_angles[cfg.name], cfg)[2]
            for cfg in HEXAPOD.legs
        }
        min_z = min(feet_z.values())
        thr = self.get_parameter('stance_z_threshold').value
        stance = [n for n, z in feet_z.items() if z <= min_z + thr]
        return stance, min_z

    def _publish(self) -> None:
        if self._last_js is None:
            return
        all_angles = self._angles_from_js(self._last_js)
        if all_angles is None:
            return
        stance, ground_z = self._stance(all_angles)
        tm = self.get_parameter('total_mass').value
        masses = MassModel(total_mass=tm) if tm and tm > 0.0 else MassModel()
        load = compute_load(all_angles, stance_legs=stance, masses=masses)

        arr = MarkerArray()
        size = self.get_parameter('text_size').value
        mid = 0

        def text_marker(pos, text, color):
            nonlocal mid
            m = Marker()
            m.header.frame_id = 'base_link'
            m.header.stamp = self.get_clock().now().to_msg()
            m.ns = 'torque_text'
            m.id = mid
            mid += 1
            m.type = Marker.TEXT_VIEW_FACING
            m.action = Marker.ADD
            m.pose.position = Point(x=pos[0], y=pos[1], z=pos[2])
            m.pose.orientation.w = 1.0
            m.scale.z = size
            m.color = color
            m.text = text
            return m

        def sphere_marker(pos, color):
            nonlocal mid
            m = Marker()
            m.header.frame_id = 'base_link'
            m.header.stamp = self.get_clock().now().to_msg()
            m.ns = 'torque_joint'
            m.id = mid
            mid += 1
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            m.pose.position = Point(x=pos[0], y=pos[1], z=pos[2])
            m.pose.orientation.w = 1.0
            m.scale.x = m.scale.y = m.scale.z = 0.014
            m.color = color
            return m

        for cfg in HEXAPOD.legs:
            leg = load.legs[cfg.name]
            leg_short = 'L' + cfg.name.split('_')[1]
            # coxa ~0 unter Vertikallast → ausgelassen (Femur/Tibia tragen)
            for jl, jshort in ((leg.femur, 'Femur'), (leg.tibia, 'Tibia')):
                col = self._color(jl.util_pct)
                # Kugel GENAU am Gelenk (Anker), Text leicht darueber.
                arr.markers.append(sphere_marker(jl.position_base, col))
                tpos = (jl.position_base[0], jl.position_base[1],
                        jl.position_base[2] + 0.016)
                arr.markers.append(text_marker(
                    tpos,
                    f'{leg_short} {jshort}\n{jl.torque_nm:+.2f}Nm {jl.util_pct:.0f}%',
                    col))

        # CoG-Kugel auf Boden-Ebene
        cog = Marker()
        cog.header.frame_id = 'base_link'
        cog.header.stamp = self.get_clock().now().to_msg()
        cog.ns = 'cog'
        cog.id = 0
        cog.type = Marker.SPHERE
        cog.action = Marker.ADD
        cog.pose.position = Point(
            x=load.cog_base[0], y=load.cog_base[1], z=ground_z)
        cog.pose.orientation.w = 1.0
        cog.scale.x = cog.scale.y = cog.scale.z = 0.02
        cog.color = _CYAN if load.stable else _RED
        arr.markers.append(cog)

        # Stütz-Polygon (LINE_STRIP, geschlossen) auf Boden-Ebene
        if len(load.support_polygon) >= 3:
            poly = Marker()
            poly.header.frame_id = 'base_link'
            poly.header.stamp = self.get_clock().now().to_msg()
            poly.ns = 'support_polygon'
            poly.id = 0
            poly.type = Marker.LINE_STRIP
            poly.action = Marker.ADD
            poly.scale.x = 0.004
            poly.color = _CYAN if load.stable else _RED
            poly.pose.orientation.w = 1.0
            pts = [Point(x=x, y=y, z=ground_z)
                   for x, y in load.support_polygon]
            pts.append(pts[0])
            poly.points = pts
            arr.markers.append(poly)

        # Stabilitäts-Text am CoG
        arr.markers.append(text_marker(
            (load.cog_base[0], load.cog_base[1], ground_z + 0.03),
            f'CoG {"OK" if load.stable else "INSTABIL"} '
            f'(Marge {load.stability_margin_m * 1000:.0f} mm)',
            _CYAN if load.stable else _RED))

        self._pub.publish(arr)
        peak = max(
            max(leg.femur.util_pct, leg.tibia.util_pct)
            for leg in load.legs.values())
        self.get_logger().info(
            f'torque_viz: M={load.total_mass:.2f}kg stance={len(stance)} '
            f'peak={peak:.0f}% stable={load.stable} '
            f'marge={load.stability_margin_m * 1000:.0f}mm',
            throttle_duration_sec=2.0)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TorqueViz()
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
