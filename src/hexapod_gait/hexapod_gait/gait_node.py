"""
gait_node — rclpy Node, 50 Hz Timer, publisht 6 JointTrajectory.

Stufe E: Single-Leg-Schwung. Bein `which_leg` schwingt periodisch eine
Halbsinus-Bahn in der Luft, Rest steht. Konsumiert
``hexapod_gait.gait_engine.GaitEngine``.

Pub-Pattern: 50 Hz Timer-Tick, pro Tick eine 1-Punkt-JointTrajectory
mit ``time_from_start = 2 × (1/tick_rate) = 0.04 s`` pro
``leg_<n>_controller/joint_trajectory``. JTC interpoliert linear
zwischen den Goals → smooth Bewegung.

Lifetime: läuft bis Ctrl+C. Kein Auto-Exit (anders als stand_node aus
Stufe C, weil hier kontinuierlicher Loop).
"""

import time

from builtin_interfaces.msg import Duration
from hexapod_gait.gait_engine import GaitEngine
from hexapod_kinematics import HEXAPOD, IKError
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class GaitNode(Node):
    """50 Hz Timer-Loop, gait_engine -> 6 JointTrajectory-Pubs."""

    def __init__(self):
        super().__init__('gait_node')

        self.declare_parameter('which_leg', 1)
        self.declare_parameter('step_height', 0.05)
        self.declare_parameter('cycle_time', 1.0)
        self.declare_parameter('tick_rate', 50.0)
        self.declare_parameter('body_height', -0.047)
        self.declare_parameter('radial_distance', 0.27)
        self.declare_parameter('time_from_start_factor', 2.0)

        self._which_leg = int(self.get_parameter('which_leg').value)
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

        self._tfs_seconds = self._tfs_factor / self._tick_rate

        self._engine = GaitEngine(
            which_leg=self._which_leg,
            step_height=self._step_height,
            cycle_time=self._cycle_time,
            radial_distance=self._radial_distance,
            body_height=self._body_height,
        )

        self._pubs = {
            leg.name: self.create_publisher(
                JointTrajectory,
                f'/{leg.name}_controller/joint_trajectory',
                10,
            )
            for leg in HEXAPOD.legs
        }

        # Wall-clock-Start (time.monotonic) statt Sim-Zeit, damit der
        # Loop nicht an /clock-DDS-Discovery-Race scheitert (gleiche
        # Erkenntnis wie in foot_contact_publisher Stufe D).
        self._t_start = time.monotonic()
        self._timer = self.create_timer(1.0 / self._tick_rate, self._tick)

        self.get_logger().info(
            f'gait_node init: which_leg={self._which_leg}, '
            f'step_height={self._step_height:.3f} m, '
            f'cycle_time={self._cycle_time:.2f} s, '
            f'tick_rate={self._tick_rate:.0f} Hz, '
            f'time_from_start={self._tfs_seconds * 1000:.1f} ms'
        )

    def _tick(self):
        t = time.monotonic() - self._t_start
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
