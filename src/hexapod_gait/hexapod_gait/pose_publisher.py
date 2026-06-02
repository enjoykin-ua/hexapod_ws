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
Pose-Publisher — statische Stand-Pose als ``/joint_states`` (ohne Sim/HW).

Publisht eine symmetrische Stand-Pose, um ein Modell in RViz in einer konkreten
Pose anzuzeigen — z.B. um die
aktuelle feet-closer Stand-Pose (radial 0.215 / body_height −0.120) mit dem
``torque_viz`` zu betrachten. Rechnet die Joint-Winkel per ``leg_ik`` aus
``radial`` + ``body_height`` (jedes Bein Fuss bei (radial, 0, body_height)).

Params (live setzbar):
  - ``radial`` (m, default 0.215), ``body_height`` (m, default −0.120)
  - ``rate`` (Hz, default 10)
"""

from __future__ import annotations

from hexapod_kinematics import HEXAPOD, IKError, leg_ik

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState


class PosePublisher(Node):
    """Publisht eine statische Stand-Pose auf /joint_states."""

    def __init__(self) -> None:
        super().__init__('pose_publisher')
        self.declare_parameter('radial', 0.215)
        self.declare_parameter('body_height', -0.120)
        self.declare_parameter('rate', 10.0)

        self._pub = self.create_publisher(JointState, '/joint_states', 10)
        rate = max(1.0, self.get_parameter('rate').get_parameter_value().double_value)
        self._names = [
            f'{cfg.name}_{j}_joint'
            for cfg in HEXAPOD.legs
            for j in ('coxa', 'femur', 'tibia')
        ]
        self.create_timer(1.0 / rate, self._publish)
        self.get_logger().info(
            f'pose_publisher: radial={self.get_parameter("radial").value:.3f} '
            f'body_height={self.get_parameter("body_height").value:.3f}')

    def _publish(self) -> None:
        radial = self.get_parameter('radial').get_parameter_value().double_value
        bh = self.get_parameter('body_height').get_parameter_value().double_value
        positions = []
        for cfg in HEXAPOD.legs:
            try:
                c, f, t = leg_ik(radial, 0.0, bh, cfg)
            except IKError as exc:
                self.get_logger().warn(
                    f'pose unreachable for {cfg.name}: {exc}',
                    throttle_duration_sec=5.0)
                c = f = t = 0.0
            positions.extend((c, f, t))
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = self._names
        msg.position = positions
        self._pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PosePublisher()
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
