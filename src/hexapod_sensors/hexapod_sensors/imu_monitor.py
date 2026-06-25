"""
imu_monitor — Beobachtungs-Adapter für die IMU (Block A5 Stufe 0).

Abonniert ``/imu/data`` (sensor_msgs/Imu) mit Sensor-Daten-QoS und macht die
Lage sichtbar/debugbar — OHNE jede Regelung:

- berechnet roll/pitch/yaw aus dem Orientierungs-Quaternion,
- loggt sie throttled (in Grad, menschenlesbar),
- publisht sie als ``geometry_msgs/Vector3`` auf ``/imu/monitor`` (in Radiant,
  SI — für echo/Plot/Bag),
- broadcastet ein ``world -> base_link``-tf aus roll/pitch (yaw=0) → das
  Roboter-Modell **neigt sich in RViz** mit der gemessenen Lage (RViz-Fixed-Frame
  = ``world``). Gleich in Sim und (später) auf HW.

Hinweis: yaw wird im tf auf 0 gesetzt — ohne Magnetometer driftet absolutes yaw,
und für die Lage-Visualisierung sind nur roll/pitch (schwerkraft-referenziert)
stabil. Translation ist fix (``viz_height``) — es wird nur Orientierung gezeigt.
"""

import math

from geometry_msgs.msg import TransformStamped, Vector3
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from tf2_ros import TransformBroadcaster


def quat_to_euler(x, y, z, w):
    """Quaternion -> (roll, pitch, yaw) in Radiant (ZYX-Konvention)."""
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = max(-1.0, min(1.0, 2.0 * (w * y - z * x)))
    pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return roll, pitch, yaw


def euler_to_quat(roll, pitch, yaw):
    """(roll, pitch, yaw) in Radiant -> Quaternion (x, y, z, w)."""
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    w = cr * cp * cy + sr * sp * sy
    return x, y, z, w


class ImuMonitor(Node):
    """/imu/data -> roll/pitch/yaw: Log + /imu/monitor + world->base_link-tf."""

    def __init__(self):
        super().__init__('imu_monitor')

        self.declare_parameter('parent_frame', 'world')
        self.declare_parameter('child_frame', 'base_link')
        self.declare_parameter('viz_height', 0.15)
        self.declare_parameter('log_period_sec', 0.5)
        self._parent = self.get_parameter('parent_frame').value
        self._child = self.get_parameter('child_frame').value
        self._viz_height = float(self.get_parameter('viz_height').value)
        self._log_period = float(self.get_parameter('log_period_sec').value)

        self._pub = self.create_publisher(Vector3, '/imu/monitor', 10)
        self._tf = TransformBroadcaster(self)
        self._sub = self.create_subscription(
            Imu, '/imu/data', self._on_imu, qos_profile_sensor_data,
        )

        self.get_logger().info(
            f'imu_monitor init: /imu/data -> /imu/monitor + tf '
            f'{self._parent}->{self._child} (roll/pitch, yaw=0)'
        )

    def _on_imu(self, msg: Imu):
        """Pro IMU-Sample: roll/pitch/yaw -> Log, /imu/monitor, tf-Broadcast."""
        q = msg.orientation
        roll, pitch, yaw = quat_to_euler(q.x, q.y, q.z, q.w)

        self._pub.publish(Vector3(x=roll, y=pitch, z=yaw))

        self.get_logger().info(
            f'roll={math.degrees(roll):6.1f}  pitch={math.degrees(pitch):6.1f}'
            f'  yaw={math.degrees(yaw):6.1f}  [deg]',
            throttle_duration_sec=self._log_period,
        )

        # Modell-Neigung in RViz: world->base_link nur aus roll/pitch (yaw=0,
        # driftfrei), Translation fix.
        tf = TransformStamped()
        tf.header.stamp = self.get_clock().now().to_msg()
        tf.header.frame_id = self._parent
        tf.child_frame_id = self._child
        tf.transform.translation.z = self._viz_height
        qx, qy, qz, qw = euler_to_quat(roll, pitch, 0.0)
        tf.transform.rotation.x = qx
        tf.transform.rotation.y = qy
        tf.transform.rotation.z = qz
        tf.transform.rotation.w = qw
        self._tf.sendTransform(tf)


def main(args=None):
    """Entry point."""
    rclpy.init(args=args)
    node = ImuMonitor()
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
