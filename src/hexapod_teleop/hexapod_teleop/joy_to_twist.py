"""
joy_to_twist — PS-Controller (geometry_msgs/Joy) -> /cmd_vel + /cmd_body_height.

Stufe A (Phase 6): PS4 via USB. D-Pad fährt + dreht, L2/R2 ändert
body_height (nur wenn Roboter steht), R1 ist Dead-Man-Switch.

Mapping ist über rclpy-Parameter konfiguriert (Defaults für PS4-USB
in ``config/ps4_usb.yaml``). Achsen-Indizes, Vorzeichen, Schwellen,
Schritte und der Dead-Man-Button-Index sind YAML-tunbar — sodass
Stufe-B-BT oder PS5 mit gleicher Code-Basis aber anderem YAML laufen.

State:
- ``_target_body_height`` (Float, m): aktuelle Soll-Höhe. Initialisiert
  aus ``body_height_init``-Param. L2/R2-Press ändert diesen Wert um
  ``body_height_step`` und publisht den absoluten Wert auf
  ``/cmd_body_height`` (Float64).
- ``_l2_was_pressed``, ``_r2_was_pressed`` (bool): Edge-Detection für
  Trigger — ein Druck = ein Schritt. Halten = nur ein Schritt
  (User-Mental-Modell).
"""

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Float64


class JoyToTwist(Node):
    """PS-Controller-/joy/-Subscriber → cmd_vel + cmd_body_height."""

    def __init__(self):
        super().__init__('joy_to_twist')

        # Achsen-Mapping (Defaults für PS4-USB ros-jazzy-joy).
        self.declare_parameter('axis_dpad_x', 6)
        self.declare_parameter('axis_dpad_y', 7)
        self.declare_parameter('axis_l2', 2)
        self.declare_parameter('axis_r2', 5)

        # Vorzeichen pro Achse — bei manchen Drivern ist D-Pad-X
        # invertiert. PS4-USB-Default-Konvention: D-Pad ↑ = +1, ← = +1.
        self.declare_parameter('sign_dpad_x', 1.0)
        self.declare_parameter('sign_dpad_y', 1.0)

        # Trigger-Schwelle: PS4-USB-Default idle = +1.0, fully pressed
        # = -1.0. "Gedrückt" wenn Wert unter Schwelle. 0.5 = halb
        # durchgedrückt.
        self.declare_parameter('trigger_threshold', 0.5)

        # Dead-Man: Button-Index. PS4 USB: R1 = Index 5.
        self.declare_parameter('deadman_button', 5)

        # Skalen für cmd_vel (matchen Engine).
        self.declare_parameter('linear_x_scale', 0.05)
        self.declare_parameter('angular_z_scale', 0.46)

        # Body-Height-State.
        self.declare_parameter('body_height_init', -0.052)
        self.declare_parameter('body_height_step', 0.005)

        self._axis_dpad_x = int(self.get_parameter('axis_dpad_x').value)
        self._axis_dpad_y = int(self.get_parameter('axis_dpad_y').value)
        self._axis_l2 = int(self.get_parameter('axis_l2').value)
        self._axis_r2 = int(self.get_parameter('axis_r2').value)
        self._sign_dpad_x = float(self.get_parameter('sign_dpad_x').value)
        self._sign_dpad_y = float(self.get_parameter('sign_dpad_y').value)
        self._trigger_threshold = float(
            self.get_parameter('trigger_threshold').value
        )
        self._deadman_button = int(self.get_parameter('deadman_button').value)
        self._linear_x_scale = float(
            self.get_parameter('linear_x_scale').value
        )
        self._angular_z_scale = float(
            self.get_parameter('angular_z_scale').value
        )
        self._body_height_step = float(
            self.get_parameter('body_height_step').value
        )

        self._target_body_height = float(
            self.get_parameter('body_height_init').value
        )
        self._l2_was_pressed = False
        self._r2_was_pressed = False

        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._body_height_pub = self.create_publisher(
            Float64, '/cmd_body_height', 10
        )

        # Initial-Body-Height publishen, damit gait_node initial-state
        # konsistent ist (falls anderer Default als Engine).
        self._publish_body_height()

        self._joy_sub = self.create_subscription(
            Joy, '/joy', self._on_joy, 10
        )

        self.get_logger().info(
            f'joy_to_twist init: '
            f'D-Pad axes (x={self._axis_dpad_x}, y={self._axis_dpad_y}, '
            f'signs ({self._sign_dpad_x:+.0f}, {self._sign_dpad_y:+.0f})), '
            f'L2 axis={self._axis_l2}, R2 axis={self._axis_r2}, '
            f'threshold={self._trigger_threshold}, '
            f'deadman button={self._deadman_button}, '
            f'scales (linear={self._linear_x_scale:.3f}, '
            f'angular={self._angular_z_scale:.3f}), '
            f'body_step={self._body_height_step:.4f} m'
        )

    def _on_joy(self, msg: Joy) -> None:
        """Joy-Callback: D-Pad → cmd_vel, L2/R2 → cmd_body_height."""
        # cmd_vel — nur wenn Dead-Man (R1) gehalten ist.
        deadman_held = (
            self._deadman_button < len(msg.buttons)
            and msg.buttons[self._deadman_button] == 1
        )
        twist = Twist()

        if deadman_held:
            dpad_x_raw = (
                msg.axes[self._axis_dpad_x]
                if self._axis_dpad_x < len(msg.axes) else 0.0
            )
            dpad_y_raw = (
                msg.axes[self._axis_dpad_y]
                if self._axis_dpad_y < len(msg.axes) else 0.0
            )
            dpad_x = dpad_x_raw * self._sign_dpad_x
            dpad_y = dpad_y_raw * self._sign_dpad_y

            if dpad_y > 0.5:
                twist.linear.x = +self._linear_x_scale
            elif dpad_y < -0.5:
                twist.linear.x = -self._linear_x_scale

            if dpad_x > 0.5:
                twist.angular.z = +self._angular_z_scale
            elif dpad_x < -0.5:
                twist.angular.z = -self._angular_z_scale

        # Wenn Dead-Man nicht gehalten: Twist bleibt 0 → Engine stoppt.
        self._cmd_vel_pub.publish(twist)

        # body_height — Edge-Detection auf L2/R2 (Trigger).
        # Triggers sind analoge Achsen: idle = +1.0, fully pressed = -1.0.
        # "Gedrückt" wenn Achse unter trigger_threshold.
        l2_value = (
            msg.axes[self._axis_l2]
            if self._axis_l2 < len(msg.axes) else 1.0
        )
        r2_value = (
            msg.axes[self._axis_r2]
            if self._axis_r2 < len(msg.axes) else 1.0
        )
        l2_pressed = l2_value < self._trigger_threshold
        r2_pressed = r2_value < self._trigger_threshold

        if l2_pressed and not self._l2_was_pressed:
            self._adjust_body_height(-1)
        if r2_pressed and not self._r2_was_pressed:
            self._adjust_body_height(+1)

        self._l2_was_pressed = l2_pressed
        self._r2_was_pressed = r2_pressed

    def _adjust_body_height(self, sign: int) -> None:
        """
        Update _target_body_height um sign * step und publish.

        Clamping passiert engine-seitig in gait_node (gegen
        body_height_min/max-Params). Hier nur lokales Tracking + Publish.
        Engine ignoriert Werte wenn nicht im STANDING — also einfach
        publishen, gait_node entscheidet.
        """
        self._target_body_height += sign * self._body_height_step
        self._publish_body_height()
        self.get_logger().info(
            f'body_height target -> {self._target_body_height:+.4f} m '
            f'({"raise" if sign > 0 else "lower"})'
        )

    def _publish_body_height(self) -> None:
        msg = Float64()
        msg.data = self._target_body_height
        self._body_height_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = JoyToTwist()
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
