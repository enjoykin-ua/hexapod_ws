"""
PS-Controller (Joy) → /cmd_vel + /cmd_body_height + Posture-Intents (C1+).

Block C1+ (Teleop-Erweiterung): analoge Sticks (omnidirektional), L1=langsam,
L2/R2=Höhe ±1 cm, R1=Dead-Man, Face-Buttons = Intents an den gait_node.

**Design-Prinzip (C §0): Teleop ist reines UI.** Er kennt KEINEN Engine-State und
enthält KEINE Entscheidungslogik — er sendet nur Intents (cmd_vel, cmd_body_height,
Service-Calls). Was damit passiert (State, Limits, Clamps), entscheidet der gait_node.

Mapping (PS4 USB):
- Linker Stick:  Y → linear.x (vor/zurück), X → linear.y (seitwärts)  [analog]
- Rechter Stick X → angular.z (drehen)
- R1 (halten) = Dead-Man — Fahren nur während gehalten (sonst cmd_vel=0)
- L1 (halten) = langsam (Skalen × slow_factor)
- L2 / R2 (Druck) = Körper senken / heben um body_height_step (1 cm), lokal geclampt
- Triangle (Druck) = Sit/Stand-Toggle  → /hexapod_sit_stand_toggle
- Circle (lang)    = Shutdown          → /hexapod_shutdown
- Cross  (lang)    = Show-Pose-HOOK    → (Stub/Log, Verhalten kommt mit Block B4)
- D-Pad ist in C1+ NICHT belegt (Gangart/Schrittweite folgen in C2).

Alle Indizes/Skalen/Schwellen sind YAML-Parameter (``config/ps4_usb.yaml``) →
BT/PS5 nur anderes YAML, gleicher Code.
"""

import time

from geometry_msgs.msg import Twist
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from std_msgs.msg import Float64
from std_srvs.srv import Trigger


class JoyToTwist(Node):
    """PS-Controller-/joy/-Subscriber → cmd_vel + cmd_body_height + Intents."""

    def __init__(self):
        super().__init__('joy_to_twist')

        # --- Achsen (PS4 USB ros-jazzy-joy Defaults) ---
        self.declare_parameter('axis_lx', 0)   # linker Stick X (seitwärts)
        self.declare_parameter('axis_ly', 1)   # linker Stick Y (vor/zurück)
        self.declare_parameter('axis_rx', 3)   # rechter Stick X (drehen)
        self.declare_parameter('axis_l2', 2)
        self.declare_parameter('axis_r2', 5)

        # Vorzeichen pro Achse (Treiber-/Konventions-abhängig → live prüfen).
        self.declare_parameter('sign_lx', 1.0)
        self.declare_parameter('sign_ly', 1.0)
        self.declare_parameter('sign_rx', 1.0)

        # Stick-Deadzone gegen Drift.
        self.declare_parameter('deadzone', 0.10)

        # --- Buttons (PS4 USB) ---
        self.declare_parameter('deadman_button', 5)    # R1
        self.declare_parameter('slow_button', 4)       # L1
        self.declare_parameter('button_triangle', 2)
        self.declare_parameter('button_circle', 1)
        self.declare_parameter('button_cross', 0)

        # Trigger (L2/R2): analog, idle=+1.0, gedrückt=-1.0 → "gedrückt" < thr.
        self.declare_parameter('trigger_threshold', 0.5)
        self.declare_parameter('longpress_sec', 0.8)

        # --- Skalen (matchen Engine-Limits) ---
        self.declare_parameter('linear_x_scale', 0.05)
        self.declare_parameter('linear_y_scale', 0.05)
        self.declare_parameter('angular_z_scale', 0.46)
        self.declare_parameter('slow_factor', 0.5)

        # --- Body-Height (Topic-Pfad, gait_node clampt zusätzlich) ---
        self.declare_parameter('body_height_init', -0.120)
        self.declare_parameter('body_height_step', 0.01)   # 1 cm pro Druck
        self.declare_parameter('body_height_min', -0.120)
        self.declare_parameter('body_height_max', -0.030)

        g = self.get_parameter
        self._axis_lx = int(g('axis_lx').value)
        self._axis_ly = int(g('axis_ly').value)
        self._axis_rx = int(g('axis_rx').value)
        self._axis_l2 = int(g('axis_l2').value)
        self._axis_r2 = int(g('axis_r2').value)
        self._sign_lx = float(g('sign_lx').value)
        self._sign_ly = float(g('sign_ly').value)
        self._sign_rx = float(g('sign_rx').value)
        self._deadzone = float(g('deadzone').value)
        self._deadman_button = int(g('deadman_button').value)
        self._slow_button = int(g('slow_button').value)
        self._button_triangle = int(g('button_triangle').value)
        self._button_circle = int(g('button_circle').value)
        self._button_cross = int(g('button_cross').value)
        self._trigger_threshold = float(g('trigger_threshold').value)
        self._longpress_sec = float(g('longpress_sec').value)
        self._linear_x_scale = float(g('linear_x_scale').value)
        self._linear_y_scale = float(g('linear_y_scale').value)
        self._angular_z_scale = float(g('angular_z_scale').value)
        self._slow_factor = float(g('slow_factor').value)
        self._body_height_step = float(g('body_height_step').value)
        self._body_height_min = float(g('body_height_min').value)
        self._body_height_max = float(g('body_height_max').value)

        self._target_body_height = float(g('body_height_init').value)

        # Edge-/Long-Press-Tracking.
        self._l2_was = False
        self._r2_was = False
        self._btn_prev: dict[int, bool] = {}
        self._press_start: dict[int, float] = {}
        self._press_fired: dict[int, bool] = {}

        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._body_height_pub = self.create_publisher(
            Float64, '/cmd_body_height', 10
        )

        # Intent-Service-Clients (reines UI → call_async, kein Warten).
        self._toggle_client = self.create_client(
            Trigger, '/hexapod_sit_stand_toggle'
        )
        self._shutdown_client = self.create_client(
            Trigger, '/hexapod_shutdown'
        )
        self._toggle_logged = False
        self._shutdown_logged = False

        # Initial-Body-Height publishen (muss == Gait-body_height sein, sonst
        # sackt der Stand ab — ai_navigation §1).
        self._publish_body_height()

        self._joy_sub = self.create_subscription(
            Joy, '/joy', self._on_joy, 10
        )

        self.get_logger().info(
            'joy_to_twist (C1+) init: '
            f'sticks lx={self._axis_lx}/ly={self._axis_ly}/rx={self._axis_rx} '
            f'(deadzone={self._deadzone}), deadman={self._deadman_button}, '
            f'slow={self._slow_button}x{self._slow_factor}, '
            f'scales=({self._linear_x_scale:.3f},'
            f'{self._linear_y_scale:.3f},{self._angular_z_scale:.3f}), '
            f'body_step={self._body_height_step:.3f} m '
            f'[{self._body_height_min:.3f},{self._body_height_max:.3f}], '
            f'longpress={self._longpress_sec:.2f}s'
        )

    # ---------- Helfer (rein, testbar) ----------

    def _apply_deadzone(self, value: float) -> float:
        """Setze Werte unterhalb der Deadzone auf 0 (gegen Stick-Drift)."""
        return 0.0 if abs(value) < self._deadzone else value

    def _axis(self, msg: Joy, idx: int) -> float:
        """Achswert oder 0.0 wenn Index außerhalb."""
        return msg.axes[idx] if 0 <= idx < len(msg.axes) else 0.0

    def _button(self, msg: Joy, idx: int) -> bool:
        """Prüfe, ob der Button gedrückt ist (Index-sicher)."""
        return 0 <= idx < len(msg.buttons) and msg.buttons[idx] == 1

    def _twist_from_joy(self, msg: Joy) -> Twist:
        """
        Berechne Twist (omnidirektional) aus den Sticks.

        Nur wenn Dead-Man gehalten; sonst Null-Twist. L1 skaliert auf
        ``slow_factor``.
        """
        twist = Twist()
        if not self._button(msg, self._deadman_button):
            return twist  # Dead-Man nicht gehalten → Stop
        scale = self._slow_factor if self._button(
            msg, self._slow_button) else 1.0
        lx = self._apply_deadzone(self._axis(msg, self._axis_lx))
        ly = self._apply_deadzone(self._axis(msg, self._axis_ly))
        rx = self._apply_deadzone(self._axis(msg, self._axis_rx))
        twist.linear.x = self._sign_ly * ly * self._linear_x_scale * scale
        twist.linear.y = self._sign_lx * lx * self._linear_y_scale * scale
        twist.angular.z = self._sign_rx * rx * self._angular_z_scale * scale
        return twist

    def _rising_edge(self, idx: int, pressed: bool) -> bool:
        """Gib True genau beim Übergang nicht-gedrückt → gedrückt."""
        prev = self._btn_prev.get(idx, False)
        self._btn_prev[idx] = pressed
        return pressed and not prev

    def _longpress(self, idx: int, pressed: bool, now: float) -> bool:
        """Gib True einmalig, wenn der Button ≥ longpress_sec gehalten wurde."""
        if not pressed:
            self._press_start.pop(idx, None)
            self._press_fired[idx] = False
            return False
        if idx not in self._press_start:
            self._press_start[idx] = now
            self._press_fired[idx] = False
        held = now - self._press_start[idx]
        fired = self._press_fired.get(idx, False)
        if not fired and held >= self._longpress_sec:
            self._press_fired[idx] = True
            return True
        return False

    # ---------- Joy-Callback ----------

    def _on_joy(self, msg: Joy) -> None:
        """Joy-Callback: Sticks → cmd_vel, L2/R2 → Höhe, Buttons → Intents."""
        now = time.monotonic()

        # 1) Fahren (Sticks, Dead-Man-gated).
        self._cmd_vel_pub.publish(self._twist_from_joy(msg))

        # 2) Höhe (L2/R2 Edge, ±step, lokal geclampt).
        l2 = self._axis(msg, self._axis_l2) < self._trigger_threshold
        r2 = self._axis(msg, self._axis_r2) < self._trigger_threshold
        if l2 and not self._l2_was:
            self._adjust_body_height(-1)
        if r2 and not self._r2_was:
            self._adjust_body_height(+1)
        self._l2_was = l2
        self._r2_was = r2

        # 3) Posture-Intents.
        if self._rising_edge(
            self._button_triangle, self._button(msg, self._button_triangle)
        ):
            self._call_intent(self._toggle_client, 'sit_stand_toggle')
        if self._longpress(
            self._button_circle, self._button(msg, self._button_circle), now
        ):
            self._call_intent(self._shutdown_client, 'shutdown')
        if self._longpress(
            self._button_cross, self._button(msg, self._button_cross), now
        ):
            self._show_pose_hook()

    def _adjust_body_height(self, sign: int) -> None:
        """Ändere das Höhen-Ziel um sign*step, clampe lokal, publishe."""
        target = self._target_body_height + sign * self._body_height_step
        self._target_body_height = max(
            self._body_height_min, min(self._body_height_max, target)
        )
        self._publish_body_height()
        self.get_logger().info(
            f'body_height target -> {self._target_body_height:+.4f} m '
            f'({"raise" if sign > 0 else "lower"})'
        )

    def _publish_body_height(self) -> None:
        """Gib das aktuelle Höhen-Ziel auf /cmd_body_height aus."""
        msg = Float64()
        msg.data = self._target_body_height
        self._body_height_pub.publish(msg)

    def _call_intent(self, client, name: str) -> None:
        """Rufe einen Intent-Service fire-and-forget; sonst einmal WARN."""
        if not client.service_is_ready():
            attr = f'_{name}_logged'
            if not getattr(self, attr, True):
                self.get_logger().warn(
                    f'Intent "{name}": Service nicht verfügbar — ignoriert '
                    '(läuft gait_node?).'
                )
                setattr(self, attr, True)
            return
        client.call_async(Trigger.Request())
        self.get_logger().info(f'Intent gesendet: {name}')

    def _show_pose_hook(self) -> None:
        """
        Show-Pose-HOOK (Cross lang) — Verhalten kommt mit Block B4.

        Bewusst nur Log/Stub: Body-Tilt + Free-Leg gibt es noch nicht. B4 hängt
        hier das eigentliche Posen/Wackeln ein (Binding + Long-Press stehen).
        """
        self.get_logger().warn(
            'Show-Pose (Cross lang) noch nicht implementiert — kommt mit '
            'Block B4 (Body-Pose/Free-Leg). Hook ist bereit.',
            throttle_duration_sec=5.0,
        )


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
