"""
gait_node — rclpy Node, 50 Hz Timer, publisht 6 JointTrajectory.

Stufe H: omnidirektionaler Walk. ``cmd_vel`` mit drei Komponenten
gleichzeitig (linear.x, linear.y, angular.z) wird durchgereicht an die
``GaitEngine``. State-Machine + Body-Frame-Mapping passiert in der
Engine; Node ist nur ROS-Glue (cmd_vel-Subscriber, Timer-Tick,
JointTrajectory-Pubs).

Activity-Timeout: wenn länger als ``cmd_vel_timeout`` Sekunden keine
neue cmd_vel ankommt, fällt Engine zurück auf ``default_linear_x`` /
``default_linear_y`` / ``default_angular_z`` (konfigurierbar, Defaults
0). Wenn alle drei Defaults 0 → STANDING. Andernfalls Demo-Mode ohne
externen cmd_vel-Pub.

Pub-Pattern: 50 Hz Timer-Tick, pro Tick eine 1-Punkt-JointTrajectory
mit ``time_from_start = 2 × (1/tick_rate) = 0.04 s``. JTC interpoliert
linear zwischen Goals → smooth Bewegung.
"""

import time

from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Twist
from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, IKError
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class GaitNode(Node):
    """50 Hz Timer-Loop, gait_engine -> 6 JointTrajectory-Pubs."""

    def __init__(self):
        super().__init__('gait_node')

        self.declare_parameter('gait_pattern', 'tripod')
        self.declare_parameter('step_height', 0.03)
        self.declare_parameter('cycle_time', 2.0)
        self.declare_parameter('tick_rate', 50.0)
        self.declare_parameter('body_height', -0.052)
        self.declare_parameter('radial_distance', 0.27)
        self.declare_parameter('time_from_start_factor', 2.0)
        self.declare_parameter('step_length_max', 0.05)
        self.declare_parameter('default_linear_x', 0.0)
        self.declare_parameter('default_linear_y', 0.0)
        self.declare_parameter('default_angular_z', 0.0)
        self.declare_parameter('cmd_vel_timeout', 0.5)

        pattern_name = str(self.get_parameter('gait_pattern').value)
        if pattern_name not in GAIT_PRESETS:
            raise ValueError(
                f'unknown gait_pattern {pattern_name!r}, '
                f'available: {sorted(GAIT_PRESETS.keys())}'
            )
        self._pattern = GAIT_PRESETS[pattern_name]

        self._step_height = float(self.get_parameter('step_height').value)
        self._cycle_time = float(self.get_parameter('cycle_time').value)
        self._tick_rate = float(self.get_parameter('tick_rate').value)
        self._body_height = float(self.get_parameter('body_height').value)
        self._radial_distance = float(
            self.get_parameter('radial_distance').value
        )
        self._tfs_factor = float(
            self.get_parameter('time_from_start_factor').value
        )
        self._step_length_max = float(
            self.get_parameter('step_length_max').value
        )
        self._default_linear_x = float(
            self.get_parameter('default_linear_x').value
        )
        self._default_linear_y = float(
            self.get_parameter('default_linear_y').value
        )
        self._default_angular_z = float(
            self.get_parameter('default_angular_z').value
        )
        self._cmd_vel_timeout = float(
            self.get_parameter('cmd_vel_timeout').value
        )

        self._tfs_seconds = self._tfs_factor / self._tick_rate

        self._engine = GaitEngine(
            pattern=self._pattern,
            step_height=self._step_height,
            cycle_time=self._cycle_time,
            radial_distance=self._radial_distance,
            body_height=self._body_height,
            step_length_max=self._step_length_max,
        )

        self._pubs = {
            leg.name: self.create_publisher(
                JointTrajectory,
                f'/{leg.name}_controller/joint_trajectory',
                10,
            )
            for leg in HEXAPOD.legs
        }

        self._cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self._on_cmd_vel, 10
        )

        # Wall-clock-Start (time.monotonic) statt Sim-Zeit, damit der
        # Loop nicht an /clock-DDS-Discovery-Race scheitert.
        self._t_start = time.monotonic()
        self._last_cmd_time: float | None = None
        self._last_cmd_v_x = 0.0
        self._last_cmd_v_y = 0.0
        self._last_cmd_omega_z = 0.0
        self._timer = self.create_timer(1.0 / self._tick_rate, self._tick)

        self.get_logger().info(
            f'gait_node init: pattern={self._pattern.name}, '
            f'step_height={self._step_height:.3f} m, '
            f'cycle_time={self._cycle_time:.2f} s, '
            f'body_height={self._body_height:.3f} m, '
            f'step_length_max={self._step_length_max:.3f} m '
            f'(linear_max={self._engine.linear_max:.3f} m/s), '
            f'defaults=(linear_x={self._default_linear_x:.3f}, '
            f'linear_y={self._default_linear_y:.3f}, '
            f'angular_z={self._default_angular_z:.3f}), '
            f'cmd_vel_timeout={self._cmd_vel_timeout:.2f} s, '
            f'tick_rate={self._tick_rate:.0f} Hz'
        )

    def _on_cmd_vel(self, msg: Twist) -> None:
        """cmd_vel-Empfang: Activity-Timestamp + 3 Komponenten cachen."""
        self._last_cmd_time = time.monotonic()
        self._last_cmd_v_x = float(msg.linear.x)
        self._last_cmd_v_y = float(msg.linear.y)
        self._last_cmd_omega_z = float(msg.angular.z)

    def _resolve_command(
        self, now: float
    ) -> tuple[float, float, float]:
        """
        Bestimme aktuelle Soll-Geschwindigkeit für die Engine.

        - Wenn cmd_vel innerhalb ``cmd_vel_timeout`` empfangen wurde:
          letzte (linear.x, linear.y, angular.z) nutzen.
        - Sonst: Fallback auf default_linear_x/y + default_angular_z
          (typisch alle 0 → STANDING via Engine-Logik).
        """
        if (
            self._last_cmd_time is not None
            and (now - self._last_cmd_time) < self._cmd_vel_timeout
        ):
            return (
                self._last_cmd_v_x,
                self._last_cmd_v_y,
                self._last_cmd_omega_z,
            )
        return (
            self._default_linear_x,
            self._default_linear_y,
            self._default_angular_z,
        )

    def _tick(self):
        now = time.monotonic()
        t = now - self._t_start
        v_x, v_y, omega_z = self._resolve_command(now)
        clamped = self._engine.set_command(v_x, v_y, omega_z, t)
        if clamped:
            self.get_logger().warn(
                f'cmd_vel clamped: input '
                f'(vx={v_x:.3f}, vy={v_y:.3f}, '
                f'omega={omega_z:.3f}) > '
                f'max-leg-speed {self._engine.linear_max:.3f} m/s',
                throttle_duration_sec=2.0,
            )

        try:
            angles_per_leg = self._engine.compute_joint_angles(t)
        except IKError as exc:
            self.get_logger().error(f'gait_engine: {exc}')
            return

        for leg in HEXAPOD.legs:
            traj = self._build_trajectory(leg.name, angles_per_leg[leg.name])
            self._pubs[leg.name].publish(traj)

    def _build_trajectory(
        self,
        leg_name: str,
        angles: tuple,
    ) -> JointTrajectory:
        traj = JointTrajectory()
        traj.joint_names = [
            f'{leg_name}_coxa_joint',
            f'{leg_name}_femur_joint',
            f'{leg_name}_tibia_joint',
        ]
        point = JointTrajectoryPoint()
        point.positions = [float(a) for a in angles]
        secs = int(self._tfs_seconds)
        nsecs = int((self._tfs_seconds - secs) * 1e9)
        point.time_from_start = Duration(sec=secs, nanosec=nsecs)
        traj.points = [point]
        return traj


def main(args=None):
    rclpy.init(args=args)
    node = GaitNode()
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
