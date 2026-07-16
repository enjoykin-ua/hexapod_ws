"""
Bringup-Launcher (Block I Phase 3) — On-Demand-Lifecycle für die App.

Teil der Always-On-Schicht (neben rosbridge + shutdown_supervisor). Startet/stoppt
den schweren Gait-/Sim-/HW-Stack als **Subprozess** (``ros2 launch …``) und bietet
einen guarded Pi-Shutdown. Die App ruft die Services über rosbridge.

Services (alle ``std_srvs/Trigger``):
  - ``/hexapod_bringup_start``  — Stack starten (idempotent).
  - ``/hexapod_bringup_stop``   — Stack sauber stoppen (SIGINT→TERM→KILL, keine Zombies).
  - ``/hexapod_bringup_status`` — ``message`` = running(pid)/stopped.
  - ``/hexapod_pi_shutdown``    — Pi ausschalten (guarded, beide Zustände).

Topic:
  - ``/hexapod/bringup_running`` (``std_msgs/Bool``, latched) — für den Connect-Screen.

Der Pi-Shutdown ist dreifach geguarded (``os_shutdown.guarded_shutdown``): auf dem
Dev-Host feuert **nie** ein echter Poweroff (nur Dry-Run-Log).
"""

import os
import signal
import subprocess

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy
from std_msgs.msg import Bool
from std_srvs.srv import Trigger

from .os_shutdown import guarded_shutdown


def _latched_qos() -> QoSProfile:
    """Latched QoS (reliable + transient_local, depth 1) für Status/Request."""
    return QoSProfile(
        depth=1,
        reliability=QoSReliabilityPolicy.RELIABLE,
        durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
    )


class BringupLauncher(Node):
    """Startet/stoppt den On-Demand-Stack + guarded Pi-Shutdown (Block I Ph.3)."""

    SIGINT_TIMEOUT_S = 10.0
    SIGTERM_TIMEOUT_S = 5.0
    SIGKILL_TIMEOUT_S = 2.0

    def __init__(self) -> None:
        """Deklariere Params, lege Services/Topic an, publiziere Startzustand."""
        super().__init__('bringup_launcher')

        # Welchen On-Demand-Stack starten? Sim vs Pi = andere Args (Q3).
        self.declare_parameter('bringup_launch_pkg', 'hexapod_bringup')
        self.declare_parameter('bringup_launch_file', 'bringup_ondemand.launch.py')
        self.declare_parameter('bringup_launch_args', ['mode:=sim'])
        # Shutdown-Guard — identisch zu shutdown_supervisor (Dev bleibt sicher).
        self.declare_parameter('enable_os_shutdown', False)
        self.declare_parameter('pi_hostname', '')
        self.declare_parameter('shutdown_command', 'sudo shutdown -h now')

        self._proc = None  # subprocess.Popen des laufenden Stacks (oder None)

        self._running_pub = self.create_publisher(
            Bool, '/hexapod/bringup_running', _latched_qos())
        self._publish_running(False)

        # Bei laufendem Stack: Shutdown über den expliziten Supervisor-Service
        # anstoßen (NICHT auf das HW-Schalter-Topic /hexapod/shutdown_request
        # publishen — dessen Baseline-Semantik verschluckt den ersten Request).
        self._shutdown_req_client = self.create_client(
            Trigger, '/hexapod_request_shutdown')

        self.create_service(Trigger, '/hexapod_bringup_start', self._on_start)
        self.create_service(Trigger, '/hexapod_bringup_stop', self._on_stop)
        self.create_service(Trigger, '/hexapod_bringup_status', self._on_status)
        self.create_service(Trigger, '/hexapod_pi_shutdown', self._on_pi_shutdown)

        # Reap + Statuswechsel bei unerwartetem Exit des Subprozesses.
        self._poll_timer = self.create_timer(1.0, self._poll_proc)

        self.get_logger().info(
            'bringup_launcher up: pkg=%s file=%s args=%s' % (
                self.get_parameter('bringup_launch_pkg').value,
                self.get_parameter('bringup_launch_file').value,
                list(self.get_parameter('bringup_launch_args').value)))

    # ------------------------------------------------------------------ helpers
    def _is_running(self) -> bool:
        """Prüft, ob ein Subprozess existiert und noch lebt."""
        return self._proc is not None and self._proc.poll() is None

    def _publish_running(self, running: bool) -> None:
        """Latched ``/hexapod/bringup_running`` aktualisieren."""
        msg = Bool()
        msg.data = running
        self._running_pub.publish(msg)

    def _poll_proc(self) -> None:
        """Unerwarteten Exit erkennen: reap + Status auf false."""
        if self._proc is not None and self._proc.poll() is not None:
            self.get_logger().warn(
                'bringup subprocess exited unexpectedly (code=%s)'
                % self._proc.returncode)
            self._proc = None
            self._publish_running(False)

    def _terminate_proc(self) -> bool:
        """SIGINT→SIGTERM→SIGKILL an die Prozessgruppe, reap. True = sauber (SIGINT)."""
        try:
            pgid = os.getpgid(self._proc.pid)
        except ProcessLookupError:
            return True
        for sig, timeout, clean in (
            (signal.SIGINT, self.SIGINT_TIMEOUT_S, True),
            (signal.SIGTERM, self.SIGTERM_TIMEOUT_S, False),
            (signal.SIGKILL, self.SIGKILL_TIMEOUT_S, False),
        ):
            try:
                os.killpg(pgid, sig)
                self._proc.wait(timeout=timeout)
                return clean
            except subprocess.TimeoutExpired:
                continue
            except ProcessLookupError:
                return clean
        return False

    # ----------------------------------------------------------------- services
    def _on_start(self, request, response):
        """``/hexapod_bringup_start`` — Stack als Subprozess starten (idempotent)."""
        if self._is_running():
            response.success = True
            response.message = 'already running (pid=%d)' % self._proc.pid
            return response
        pkg = str(self.get_parameter('bringup_launch_pkg').value)
        launch_file = str(self.get_parameter('bringup_launch_file').value)
        extra = [str(a) for a in self.get_parameter('bringup_launch_args').value]
        cmd = ['ros2', 'launch', pkg, launch_file] + extra
        try:
            # start_new_session=True → eigene Prozessgruppe (killpg beim Stop).
            self._proc = subprocess.Popen(cmd, start_new_session=True)
        except (OSError, ValueError) as exc:
            self._proc = None
            response.success = False
            response.message = 'failed to start: %s' % exc
            self.get_logger().error(response.message)
            return response
        self._publish_running(True)
        response.success = True
        response.message = 'started (pid=%d): %s' % (self._proc.pid, ' '.join(cmd))
        self.get_logger().info(response.message)
        return response

    def _on_stop(self, request, response):
        """``/hexapod_bringup_stop`` — Stack sauber stoppen (keine Zombies)."""
        if not self._is_running():
            self._proc = None
            self._publish_running(False)
            response.success = True
            response.message = 'not running'
            return response
        pid = self._proc.pid
        clean = self._terminate_proc()
        self._proc = None
        self._publish_running(False)
        response.success = True
        response.message = 'stopped (pid=%d, %s)' % (
            pid, 'clean' if clean else 'forced')
        self.get_logger().info(response.message)
        return response

    def _on_status(self, request, response):
        """``/hexapod_bringup_status`` — running(pid)/stopped im message-Feld."""
        response.success = True
        response.message = (
            'running (pid=%d)' % self._proc.pid if self._is_running()
            else 'stopped')
        return response

    def _on_pi_shutdown(self, request, response):
        """``/hexapod_pi_shutdown`` — Pi ausschalten, guarded, beide Zustände."""
        if self._is_running():
            # Stack läuft → Block-F-Kette (Hinsetzen + guarded Poweroff) über den
            # expliziten Supervisor-Service anstoßen (fire-and-forget).
            if not self._shutdown_req_client.service_is_ready():
                response.success = False
                response.message = (
                    '/hexapod_request_shutdown not available '
                    '(shutdown_supervisor up?)')
                self.get_logger().error(response.message)
                return response
            self._shutdown_req_client.call_async(Trigger.Request())
            response.success = True
            response.message = (
                'shutdown requested (stack running → controlled sit-down + '
                'guarded poweroff via shutdown_supervisor)')
            self.get_logger().warn(response.message)
            return response
        # Stack idle → direkter guarded Poweroff (nichts zum Hinsetzen).
        performed, reason = guarded_shutdown(
            bool(self.get_parameter('enable_os_shutdown').value),
            str(self.get_parameter('pi_hostname').value),
            str(self.get_parameter('shutdown_command').value),
            self.get_logger())
        response.success = True
        response.message = 'idle poweroff: performed=%s (%s)' % (performed, reason)
        self.get_logger().warn(response.message)
        return response

    def destroy_node(self) -> None:
        """Zombie-Schutz: laufenden Stack beim Node-Shutdown sauber stoppen."""
        if self._is_running():
            self.get_logger().info('bringup_launcher shutdown → stopping stack')
            self._terminate_proc()
            self._proc = None
        super().destroy_node()


def main(args=None) -> None:
    """Entry-Point: Node spinnen bis Ctrl-C/Shutdown."""
    rclpy.init(args=args)
    node = BringupLauncher()
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
