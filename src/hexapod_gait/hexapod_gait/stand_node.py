"""
stand_node — One-Shot Stand-Pose-Publisher.

Lifecycle (Stufe-C-Design-Entscheidung 3, One-Shot mit Auto-Exit):
1. Knoten init, Parameter laden, 6 Publisher anlegen.
2. Pro Bein IK auf Foot-Target (radial_distance, 0, body_height) im
   Bein-Frame -> Joint-Winkel.
3. ``discovery_wait`` Sekunden spinnen, damit DDS die Publisher-Subscriber-
   Matches abwickelt. Diagnostisch wird ``count_subscribers`` geloggt;
   ein Wert von 0 ist im rclpy-Jazzy-Graph-State zeitweise unzuverlässig
   und führt **nicht** zum Fehler — die Pub geht trotzdem raus.
4. Pub 6× JointTrajectory mit time_from_start = transition_duration.
5. Sleep 0.5 s für DDS-Auslieferung.
6. Sauberer rclpy.shutdown() + Exit-Code.

Override-Verhalten: Wer auch immer als nächster auf
``/leg_<n>_controller/joint_trajectory`` publisht (z. B. gait_node aus
Stufe E), ersetzt das Stand-Goal sofort. Das ist eine JTC-Eigenschaft,
unabhängig vom Lebenszyklus dieses Knotens.
"""

import time

from builtin_interfaces.msg import Duration
from hexapod_kinematics import HEXAPOD, IKError, leg_ik
import rclpy
from rclpy.node import Node
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


# Wartezeit nach den Pubs, damit DDS die Messages auch wirklich
# raus an die JTCs ausliefert, bevor der Knoten exit. Empirischer Wert,
# 0.5 s ist großzügig.
_DDS_FLUSH_SECONDS = 0.5


class StandNode(Node):
    """One-Shot-Knoten: berechne IK pro Bein, publishe Trajectory, exit."""

    def __init__(self):
        super().__init__('stand_node')

        self.declare_parameter('body_height', -0.052)
        self.declare_parameter('radial_distance', 0.27)
        self.declare_parameter('transition_duration', 4.0)
        self.declare_parameter('discovery_wait', 2.0)

        self._body_height = float(self.get_parameter('body_height').value)
        self._radial = float(self.get_parameter('radial_distance').value)
        self._duration = float(self.get_parameter('transition_duration').value)
        self._discovery_wait = float(
            self.get_parameter('discovery_wait').value
        )

        # Pro Bein ein Publisher auf /leg_<n>_controller/joint_trajectory.
        # QoS-Default (depth 10, RELIABLE, VOLATILE) passt zum JTC.
        self._topics = {
            leg.name: f'/{leg.name}_controller/joint_trajectory'
            for leg in HEXAPOD.legs
        }
        self._pubs = {
            name: self.create_publisher(JointTrajectory, topic, 10)
            for name, topic in self._topics.items()
        }

        self.get_logger().info(
            f'stand_node init: foot_target='
            f'({self._radial:.4f}, 0.0, {self._body_height:.4f}) '
            f'in Bein-Frame, transition={self._duration:.1f}s'
        )

    def run(self) -> int:
        """Hauptablauf — gibt Exit-Code zurück (0 = ok)."""
        # Schritt 1: IK pro Bein vorberechnen.
        foot = (self._radial, 0.0, self._body_height)
        angles_per_leg = {}
        for leg in HEXAPOD.legs:
            try:
                angles_per_leg[leg.name] = leg_ik(*foot, leg)
            except IKError as exc:
                self.get_logger().error(
                    f'IK failed for {leg.name}: {exc}'
                )
                return 1

        # Schritt 2: DDS-Discovery-Settling. Spin für discovery_wait
        # Sekunden, damit DDS die Subscriber-Matches abwickelt.
        # Diagnostik via count_subscribers; 0-Werte sind im rclpy-Jazzy-
        # Graph-State zeitweise unzuverlässig (siehe Modul-Docstring),
        # daher non-fatal.
        self.get_logger().info(
            f'waiting {self._discovery_wait:.1f}s for DDS discovery'
        )
        deadline = time.monotonic() + self._discovery_wait
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

        counts = {
            name: self.count_subscribers(topic)
            for name, topic in self._topics.items()
        }
        if all(c > 0 for c in counts.values()):
            self.get_logger().info(
                f'all 6 JTCs visible in graph (counts={counts})'
            )
        else:
            missing = [n for n, c in counts.items() if c == 0]
            self.get_logger().warn(
                f'JTCs not visible in local graph state (missing='
                f'{missing}); publishing anyway. Verify externally with '
                f'`ros2 topic info /leg_1_controller/joint_trajectory`.'
            )

        # Schritt 3: 6× publish.
        for leg in HEXAPOD.legs:
            angles = angles_per_leg[leg.name]
            traj = self._build_trajectory(leg.name, angles)
            self._pubs[leg.name].publish(traj)
            self.get_logger().info(
                f'pub {leg.name}: '
                f'coxa={angles[0]:+.4f} '
                f'femur={angles[1]:+.4f} '
                f'tibia={angles[2]:+.4f}'
            )

        # Schritt 4: DDS-Flush.
        flush_end = time.monotonic() + _DDS_FLUSH_SECONDS
        while time.monotonic() < flush_end:
            rclpy.spin_once(self, timeout_sec=0.05)

        self.get_logger().info(
            f'stand pose dispatched, JTC will reach target in ~'
            f'{self._duration:.1f}s; exiting'
        )
        return 0

    def _build_trajectory(
        self,
        leg_name: str,
        angles: tuple,
    ) -> JointTrajectory:
        """Konstruiere JointTrajectory mit einem End-Punkt."""
        traj = JointTrajectory()
        traj.joint_names = [
            f'{leg_name}_coxa_joint',
            f'{leg_name}_femur_joint',
            f'{leg_name}_tibia_joint',
        ]

        point = JointTrajectoryPoint()
        point.positions = [float(a) for a in angles]
        secs = int(self._duration)
        nsecs = int((self._duration - secs) * 1e9)
        point.time_from_start = Duration(sec=secs, nanosec=nsecs)
        traj.points = [point]

        return traj


def main(args=None):
    rclpy.init(args=args)
    node = StandNode()
    try:
        rc = node.run()
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return rc


if __name__ == '__main__':
    main()
