"""
gait_node — rclpy Node, 50 Hz Timer, publisht 6 JointTrajectory.

Stufe F: Daten-getriebene Gangart via ``gait_pattern``-Parameter
(Preset-Name aus ``GAIT_PRESETS``). State-Machine STANDING ↔ WALKING
via ``enable_walk``-rclpy-Param mit Live-Toggle (``ros2 param set``).
Konsumiert ``hexapod_gait.gait_engine.GaitEngine``.

Pub-Pattern: 50 Hz Timer-Tick, pro Tick eine 1-Punkt-JointTrajectory
mit ``time_from_start = 2 × (1/tick_rate) = 0.04 s`` pro
``leg_<n>_controller/joint_trajectory``. JTC interpoliert linear
zwischen den Goals → smooth Bewegung.

Lifetime: läuft bis Ctrl+C. ``enable_walk`` toggelt zwischen STANDING
(alle 6 Stand-Pose) und WALKING (Pattern-Logik) ohne Restart.
"""

import time

from builtin_interfaces.msg import Duration
from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, IKError
from rcl_interfaces.msg import SetParametersResult
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


class GaitNode(Node):
    """50 Hz Timer-Loop, gait_engine -> 6 JointTrajectory-Pubs."""

    def __init__(self):
        super().__init__('gait_node')

        self.declare_parameter('gait_pattern', 'tripod')
        self.declare_parameter('enable_walk', False)
        self.declare_parameter('step_height', 0.03)
        self.declare_parameter('cycle_time', 2.0)
        self.declare_parameter('tick_rate', 50.0)
        self.declare_parameter('body_height', -0.052)
        self.declare_parameter('radial_distance', 0.27)
        self.declare_parameter('time_from_start_factor', 2.0)

        pattern_name = str(self.get_parameter('gait_pattern').value)
        if pattern_name not in GAIT_PRESETS:
            raise ValueError(
                f'unknown gait_pattern {pattern_name!r}, '
                f'available: {sorted(GAIT_PRESETS.keys())}'
            )
        self._pattern = GAIT_PRESETS[pattern_name]

        self._enable_walk = bool(self.get_parameter('enable_walk').value)
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
            pattern=self._pattern,
            step_height=self._step_height,
            cycle_time=self._cycle_time,
            radial_distance=self._radial_distance,
            body_height=self._body_height,
            enable_walk=self._enable_walk,
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

        self.add_on_set_parameters_callback(self._on_param_change)

        self.get_logger().info(
            f'gait_node init: pattern={self._pattern.name}, '
            f'enable_walk={self._enable_walk}, '
            f'step_height={self._step_height:.3f} m, '
            f'cycle_time={self._cycle_time:.2f} s, '
            f'body_height={self._body_height:.3f} m, '
            f'tick_rate={self._tick_rate:.0f} Hz, '
            f'time_from_start={self._tfs_seconds * 1000:.1f} ms'
        )

    def _on_param_change(self, params) -> SetParametersResult:
        """
        Live-Toggle für ``enable_walk`` via ``ros2 param set``.

        Andere Parameter sind nicht live-änderbar (würden inkonsistente
        Engine-States erzeugen — z. B. Pattern-Wechsel mitten im Cycle).
        Werden ignoriert mit Log-Warning.
        """
        for param in params:
            if param.name == 'enable_walk':
                new_value = bool(param.value)
                self._enable_walk = new_value
                self._engine.enable_walk = new_value
                self.get_logger().info(
                    f'enable_walk -> {new_value} '
                    f'({"WALKING" if new_value else "STANDING"})'
                )
            else:
                self.get_logger().warn(
                    f'param {param.name!r} cannot be changed at runtime, '
                    'restart the node to apply'
                )
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'parameter {param.name!r} is not runtime-mutable'
                    ),
                )
        return SetParametersResult(successful=True)

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
