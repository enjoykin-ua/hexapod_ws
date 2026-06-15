"""
Shutdown supervisor node (Block F4).

Watches ``/hexapod/shutdown_request``; on a real rising edge it drives the
existing ``/hexapod_shutdown`` service (retrying until the robot is in a
sit-able state), waits for ``/hexapod/shutdown_complete``, then performs a
guarded OS shutdown. The dangerous OS call lives in
:func:`hexapod_supervisor.os_shutdown.guarded_shutdown`.

The supervisor itself contains no gait/relay logic — ``/hexapod_shutdown``
already does sit-down + relay-off + latch idempotently.
"""

from hexapod_supervisor.os_shutdown import guarded_shutdown
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool
from std_srvs.srv import SetBool, Trigger


def _latched_qos():
    """Build the latched QoS for F2/F3 publishers (reliable + transient_local)."""
    return QoSProfile(
        depth=1,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        reliability=ReliabilityPolicy.RELIABLE)


class ShutdownSupervisor(Node):
    """Orchestrates the controlled shutdown triggered by the hardware switch."""

    STATE_IDLE = 'IDLE'
    STATE_SHUTTING_DOWN = 'SHUTTING_DOWN'
    STATE_DONE = 'DONE'

    def __init__(self):
        """Declare params, wire subs/clients and log the guard configuration."""
        super().__init__('shutdown_supervisor')

        self.declare_parameter('enable_os_shutdown', False)
        self.declare_parameter('pi_hostname', '')
        self.declare_parameter('shutdown_command', 'sudo shutdown -h now')
        self.declare_parameter('shutdown_retry_period', 1.0)
        # Backstop must comfortably exceed the real STANDING->sit time. Measured
        # ~7.0 s live (reposition ~2 s + sitdown ~5 s); 8 s left <1 s margin, so
        # 12 s gives ~5 s headroom against a slightly slower sit-down (F4-L1).
        self.declare_parameter('shutdown_complete_timeout', 12.0)
        self.declare_parameter('force_relay_off_on_timeout', True)

        self._state = self.STATE_IDLE
        self._last_request = None
        self._service_ok = False
        self._complete = False
        self._retry_timer = None
        self._backstop_timer = None
        self._shutdown_future = None

        self._shutdown_client = self.create_client(Trigger, '/hexapod_shutdown')
        self._relay_client = self.create_client(SetBool, '/hexapod_relay_set')

        self.create_subscription(
            Bool, '/hexapod/shutdown_request', self._on_request, _latched_qos())
        self.create_subscription(
            Bool, '/hexapod/shutdown_complete', self._on_complete,
            _latched_qos())

        self.get_logger().info(
            'shutdown_supervisor up: enable_os_shutdown=%s, pi_hostname=%r'
            % (self.get_parameter('enable_os_shutdown').value,
               self.get_parameter('pi_hostname').value))

    # ----- request edge / arm ------------------------------------------- #
    def _on_request(self, msg):
        """Baseline the first (latched) value; trigger only on a real 0->1 edge."""
        if self._last_request is None:
            self._last_request = msg.data
            if msg.data:
                self.get_logger().warn(
                    'shutdown_request already True at startup -> baselined, '
                    'NOT triggering (toggle the switch to request a shutdown)')
            return
        rising = (not self._last_request) and msg.data
        self._last_request = msg.data
        if rising and self._state == self.STATE_IDLE:
            self._begin_shutdown()

    def _begin_shutdown(self):
        """Enter SHUTTING_DOWN and start retrying ``/hexapod_shutdown``."""
        self.get_logger().warn('shutdown requested -> begin controlled shutdown')
        self._state = self.STATE_SHUTTING_DOWN
        self._service_ok = False
        period = self.get_parameter('shutdown_retry_period').value
        self._retry_timer = self.create_timer(
            period, self._try_shutdown_service)
        self._try_shutdown_service()

    def _try_shutdown_service(self):
        """Call ``/hexapod_shutdown``; retry while it refuses (not STANDING/SAT)."""
        if self._service_ok:
            return
        if self._shutdown_future is not None and \
                not self._shutdown_future.done():
            return
        if not self._shutdown_client.service_is_ready():
            self.get_logger().warn('/hexapod_shutdown not available yet, retry')
            return
        self._shutdown_future = self._shutdown_client.call_async(
            Trigger.Request())
        self._shutdown_future.add_done_callback(self._on_shutdown_response)

    def _on_shutdown_response(self, future):
        """Handle the ``/hexapod_shutdown`` reply; arm the backstop on success."""
        if future.exception() is not None:
            self.get_logger().warn(
                '/hexapod_shutdown call failed: %s' % future.exception())
            return
        resp = future.result()
        if not resp.success:
            self.get_logger().info(
                '/hexapod_shutdown refused (%s) -> retrying' % resp.message)
            return
        self.get_logger().info(
            '/hexapod_shutdown accepted: %s' % resp.message)
        self._service_ok = True
        self._cancel_timer('_retry_timer')
        if self._complete:
            # Completion already latched/seen (robot was already SAT) — the
            # complete message can arrive before this service response, so we
            # must not wait for a fresh one (would fall back to the backstop).
            self._finish('complete')
            return
        timeout = self.get_parameter('shutdown_complete_timeout').value
        self._backstop_timer = self.create_timer(timeout, self._on_backstop)

    # ----- completion / backstop ---------------------------------------- #
    def _on_complete(self, msg):
        """Record completion; finish once the shutdown service also succeeded."""
        self._complete = msg.data
        if self._state == self.STATE_SHUTTING_DOWN and self._service_ok \
                and msg.data:
            self._finish('complete')

    def _on_backstop(self):
        """Backstop: no completion in time -> force relay off, shut down anyway."""
        if self._state != self.STATE_SHUTTING_DOWN:
            return
        self.get_logger().warn(
            'shutdown_complete not seen within timeout -> backstop fallback')
        if self.get_parameter('force_relay_off_on_timeout').value \
                and self._relay_client.service_is_ready():
            req = SetBool.Request()
            req.data = False
            self._relay_client.call_async(req)
        self._finish('timeout')

    def _finish(self, reason):
        """Cancel timers and perform the guarded OS shutdown exactly once."""
        if self._state == self.STATE_DONE:
            return
        self._cancel_timer('_retry_timer')
        self._cancel_timer('_backstop_timer')
        self._state = self.STATE_DONE
        performed, why = guarded_shutdown(
            self.get_parameter('enable_os_shutdown').value,
            self.get_parameter('pi_hostname').value,
            self.get_parameter('shutdown_command').value,
            self.get_logger())
        self.get_logger().warn(
            'shutdown finished (reason=%s, performed=%s, guard=%s)'
            % (reason, performed, why))

    def _cancel_timer(self, attr):
        """Cancel and drop a timer member by attribute name, if present."""
        timer = getattr(self, attr)
        if timer is not None:
            timer.cancel()
            setattr(self, attr, None)


def main(args=None):
    """Spin the shutdown supervisor node."""
    rclpy.init(args=args)
    node = ShutdownSupervisor()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
