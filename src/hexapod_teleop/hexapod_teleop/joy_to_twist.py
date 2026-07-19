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
- D-Pad ←/→ (C2)   = Gangart prev/next → /hexapod_cycle_gait
- D-Pad ↑/↓ (H2)   = Tempo-Preset schneller/langsamer (_TEMPO_MODES: cycle_time
  am gait_node via AsyncParameterClient + eigene joy-Scales; ersetzt das
  C3-Schrittweiten-Binding — /hexapod_adjust_step_length bleibt als Service).

Alle Indizes/Skalen/Schwellen sind YAML-Parameter (``config/ps4_usb.yaml``) →
BT/PS5 nur anderes YAML, gleicher Code.
"""

from collections import namedtuple
import json
import time

from geometry_msgs.msg import Twist
from rcl_interfaces.msg import SetParametersResult
import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.parameter_client import AsyncParameterClient
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Joy
from std_msgs.msg import Float64, Float64MultiArray, String
from std_srvs.srv import SetBool, Trigger


# Block H2 — Tempo-Presets. Tempo = NUR cycle_time (gait_node) + joy-Scales
# (cmd-Limits hier) — envelope-frei bewiesen (die Bein-Hülle hängt an
# Schrittweite/Hub/Höhe/Radius, nicht am Tempo; H2-Plan §0). Die Tabelle lebt
# im Teleop (UX-Besitzer der Scales); der standing_only-Guard für cycle_time
# lebt als DIE eine Wahrheit im gait_node (Ablehnung → keine Scale-Änderung).
# Reihenfolge aufsteigendes Tempo; D-Pad ↑ = Index+1 (schneller), geklemmt.
# Boot-Index "schnell" = EXAKT die heutigen YAML-Scales → der erste D-Pad-
# Druck erzeugt keinen Verhaltens-Sprung. "aggressiv" = User-erprobt (die
# Scales sind cmd-Limits; die Engine clampt zusätzlich proportional auf
# linear_max = step_length_max/stance — 0.17 > linear_max ⇒ WARN+clamp, ok).
# Startwerte — finale Werte nach Sim-Tuning H2.5 nachziehen (Muster
# hw_balance: Code trägt Startwerte, Tuning-Ergebnis wird nachgezogen).
_TempoMode = namedtuple(
    '_TempoMode',
    'name cycle_time linear_x_scale linear_y_scale angular_z_scale')
_TEMPO_MODES = (
    _TempoMode('langsam', 3.3, 0.03, 0.03, 0.28),
    _TempoMode('mittel', 2.6, 0.04, 0.04, 0.35),
    _TempoMode('schnell', 2.0, 0.05, 0.05, 0.46),
    _TempoMode('aggressiv', 1.5, 0.17, 0.13, 1.2),
)
_TEMPO_DEFAULT_IDX = 2   # schnell (= Boot: cycle_time-Default 2.0 + YAML-Scales)

# Antwort-Timeout für den cycle_time-Request: bleibt die Future so lange ohne
# Antwort (gait_node zwischen ready-Check und Antwort weg), wird der nächste
# D-Pad-Druck wieder zugelassen (sonst wäre der Tempo-Cycle dauerhaft blockiert).
_TEMPO_REQUEST_TIMEOUT_S = 2.0


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

        # --- D-Pad (C2: Gangart · H2: Tempo-Presets) ---
        self.declare_parameter('axis_dpad_x', 6)   # ←/→ : Gangart prev/next
        self.declare_parameter('axis_dpad_y', 7)   # ↑/↓ : Tempo schneller/langsamer
        self.declare_parameter('sign_dpad_x', 1.0)
        self.declare_parameter('sign_dpad_y', 1.0)
        self.declare_parameter('dpad_threshold', 0.5)
        # Debounce: nach einem D-Pad-Intent für diese Zeit kein weiterer (gegen
        # Flackern des HAT-Achswerts beim Tippen → sonst Doppel-Auslöser →
        # überspringt jede zweite Gangart).
        self.declare_parameter('dpad_lockout_sec', 0.3)

        # --- Skalen (matchen Engine-Limits) ---
        self.declare_parameter('linear_x_scale', 0.05)
        self.declare_parameter('linear_y_scale', 0.05)
        self.declare_parameter('angular_z_scale', 0.46)
        self.declare_parameter('slow_factor', 0.5)

        # --- Body-Height (Topic-Pfad, gait_node clampt zusätzlich) ---
        # body_height_init = Stance-Modus "mittel" (Standup-Basis), einmalig
        # beim Start publisht (Stand-Sync). Stufenlose Höhe via L2/R2 gibt es
        # nicht mehr (→ Stance-Modi); _adjust_body_height bleibt nur Helper.
        # leg_changes: mittel -0.080, min-Floor -0.110 (Modus "hoch" -0.100).
        self.declare_parameter('body_height_init', -0.080)
        self.declare_parameter('body_height_step', 0.01)
        self.declare_parameter('body_height_min', -0.110)
        self.declare_parameter('body_height_max', -0.060)

        # --- Show-Pose (B4): rechter Stick-Y (leg_1 vertikal) + Vorzeichen ---
        # Linker Stick → leg_6, rechter Stick → leg_1; X=seitwärts, Y=hoch/runter.
        # Signs treiber-/konventionsabhängig (in Sim verifizieren: Stick hoch =
        # Bein heben). /cmd_show wird wie cmd_vel per R1-Dead-Man gegated.
        self.declare_parameter('axis_ry', 4)   # rechter Stick Y (leg_1 vertikal)
        self.declare_parameter('sign_show_lat', 1.0)
        self.declare_parameter('sign_show_vert', 1.0)
        # B4.11 — Tibia-Curl/Reach: L2 → leg_6, R2 → leg_1 (analog, R1-gated).
        # Trigger drücken = Bein streckt sich raus (Tibia fährt auf). Body-Höhe
        # (L2/R2) gibt es nur OHNE R1 → kein Konflikt im Show.
        self.declare_parameter('sign_show_radial', 1.0)
        # Show-Pose im Teleop aktiv? Default false (leg_changes/S6): die aktuelle
        # Show-Pose ist auf echter HW nicht stabil → Teleop schickt WEDER den
        # /hexapod_show_toggle-Intent (Cross) NOCH /cmd_show. Der gait_node-Show-
        # Code bleibt unangetastet; Wiedereinschalten = show_enabled:=true (bzw.
        # später eine neue, stabile Show-Pose daraus bauen).
        self.declare_parameter('show_enabled', False)

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
        self._axis_dpad_x = int(g('axis_dpad_x').value)
        self._axis_dpad_y = int(g('axis_dpad_y').value)
        self._sign_dpad_x = float(g('sign_dpad_x').value)
        self._sign_dpad_y = float(g('sign_dpad_y').value)
        self._dpad_threshold = float(g('dpad_threshold').value)
        self._dpad_lockout_sec = float(g('dpad_lockout_sec').value)
        self._linear_x_scale = float(g('linear_x_scale').value)
        self._linear_y_scale = float(g('linear_y_scale').value)
        self._angular_z_scale = float(g('angular_z_scale').value)
        self._slow_factor = float(g('slow_factor').value)
        self._body_height_step = float(g('body_height_step').value)
        self._body_height_min = float(g('body_height_min').value)
        self._body_height_max = float(g('body_height_max').value)
        # Show-Pose (B4 / B4.11).
        self._axis_ry = int(g('axis_ry').value)
        self._sign_show_lat = float(g('sign_show_lat').value)
        self._sign_show_vert = float(g('sign_show_vert').value)
        self._sign_show_radial = float(g('sign_show_radial').value)
        self._show_enabled = bool(g('show_enabled').value)

        self._target_body_height = float(g('body_height_init').value)

        # Edge-/Long-Press-Tracking.
        self._l2_was = False
        self._r2_was = False
        self._btn_prev: dict[int, bool] = {}
        self._press_start: dict[int, float] = {}
        self._press_fired: dict[int, bool] = {}
        self._dpad_x_prev = 0   # diskrete D-Pad-Richtung (-1/0/+1)
        self._dpad_y_prev = 0
        self._dpad_x_last_fire = -1e9  # monotonic-Zeit des letzten X-Intents
        self._dpad_y_last_fire = -1e9

        self._cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self._body_height_pub = self.create_publisher(
            Float64, '/cmd_body_height', 10
        )
        # Block B4 — /cmd_show: 4 Stick-Werte für die Vorderbeine (SHOW_ACTIVE).
        self._cmd_show_pub = self.create_publisher(
            Float64MultiArray, '/cmd_show', 10
        )
        # Block I Phase 5 — aktives Tempo-Preset fürs App-Overlay (JSON, latched
        # → ein spät verbindender App-Subscriber bekommt sofort den Ist-Wert).
        self._tempo_pub = self.create_publisher(
            String, '/hexapod/tempo',
            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                       reliability=ReliabilityPolicy.RELIABLE),
        )

        # Intent-Service-Clients (reines UI → call_async, kein Warten).
        self._toggle_client = self.create_client(
            Trigger, '/hexapod_sit_stand_toggle'
        )
        self._shutdown_client = self.create_client(
            Trigger, '/hexapod_shutdown'
        )
        self._cycle_gait_client = self.create_client(
            SetBool, '/hexapod_cycle_gait'
        )
        # Block H2 — Tempo-Presets: cycle_time wird als Parameter am gait_node
        # gesetzt (AsyncParameterClient = die Param-Service-Clients zu
        # /gait_node/set_parameters etc.). Der gait-seitige standing_only-
        # Validator ist der EINE Guard: Ablehnung → keine lokale Scale-Änderung.
        # (Das frühere D-Pad-↑/↓-Binding /hexapod_adjust_step_length ist damit
        # umgewidmet; der gait-Service selbst bleibt bestehen.)
        self._gait_param_client = AsyncParameterClient(self, 'gait_node')
        self._tempo_idx = _TEMPO_DEFAULT_IDX
        self._tempo_request_pending = False
        self._tempo_request_time = 0.0
        # Block B4 — Show-Pose-Toggle (Cross lang).
        self._show_toggle_client = self.create_client(
            Trigger, '/hexapod_show_toggle'
        )
        # Phase 13 Stage 1 — Stance-Modus cyclen (L2/R2 ohne R1).
        self._cycle_stance_client = self.create_client(
            SetBool, '/hexapod_cycle_stance'
        )
        # Block I Phase 5 — Tempo-Setz-Weg für den App-Dropdown: SetBool-Service
        # (true=schneller / false=langsamer), symmetrisch zu cycle_gait/stance.
        # Der App-Dropdown macht cycle-to-target via tempo_idx aus /hexapod/tempo.
        self._cycle_tempo_srv = self.create_service(
            SetBool, '/hexapod_cycle_tempo', self._on_cycle_tempo
        )
        self._toggle_logged = False
        self._shutdown_logged = False
        self._cycle_gait_logged = False
        self._show_toggle_logged = False
        self._cycle_stance_logged = False

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

        # TLS — Tempo-Params live-tunbar (sonst nur beim Start gelesen). Wie der
        # gait_node: validate-then-apply. Nur die Tuning-Werte, nicht die Struktur.
        self.add_on_set_parameters_callback(self._on_param_change)

        # Block I Phase 5 — initiales Tempo-Preset latchen (Overlay-Startwert).
        self._publish_tempo()

    def _on_param_change(self, params):
        """
        Live-Tuning der Tempo-Parameter (TLS): validate-then-apply.

        Übernimmt im Lauf nur die **Tuning-Werte** (``linear_x_scale``,
        ``linear_y_scale``, ``angular_z_scale``, ``slow_factor``, ``deadzone``).
        Strukturelle Params (Achsen-/Button-/Sign-Indizes) bleiben Start-only —
        sie werden hier nicht behandelt → im Hot-Path gilt weiter der Startwert
        (kein Regress). Erst alles prüfen (kein Teil-Apply bei Fehler), dann setzen.
        """
        # 1. VALIDATE — bei Ungültigem sofort raus, nichts angewandt.
        for p in params:
            if (
                p.name in (
                    'linear_x_scale', 'linear_y_scale', 'angular_z_scale',
                )
                and p.value < 0.0
            ):
                return SetParametersResult(
                    successful=False,
                    reason=f'{p.name} must be >= 0, got {p.value}',
                )
            if p.name == 'slow_factor' and not 0.0 <= p.value <= 1.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'slow_factor must be in [0,1], got {p.value}',
                )
            if p.name == 'deadzone' and not 0.0 <= p.value < 1.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'deadzone must be in [0,1), got {p.value}',
                )

        # 2. APPLY — kein Fail mehr möglich.
        for p in params:
            if p.name == 'linear_x_scale':
                self._linear_x_scale = float(p.value)
            elif p.name == 'linear_y_scale':
                self._linear_y_scale = float(p.value)
            elif p.name == 'angular_z_scale':
                self._angular_z_scale = float(p.value)
            elif p.name == 'slow_factor':
                self._slow_factor = float(p.value)
            elif p.name == 'deadzone':
                self._deadzone = float(p.value)

        return SetParametersResult(successful=True)

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

    def _trigger_frac(self, msg: Joy, idx: int) -> float:
        """Analog-Trigger → Druck-Anteil [0, 1] (idle +1.0 → 0, voll -1.0 → 1)."""
        return max(0.0, min(1.0, (1.0 - self._axis(msg, idx)) / 2.0))

    def _show_from_joy(self, msg: Joy) -> Float64MultiArray:
        """
        Vorderbein-Achsen (B4/B4.11) → /cmd_show in [-1, 1].

        Reihenfolge ``[l6_lat, l6_vert, l6_radial, l1_lat, l1_vert, l1_radial]``.
        Linker Stick → leg_6, rechter Stick → leg_1; X=seitwärts (lateral),
        Y=hoch/runter (vertikal). L2 → leg_6 radial, R2 → leg_1 radial (Trigger
        drücken = Bein streckt sich raus / Tibia fährt auf). Per R1-Dead-Man
        gegated (= 0 wenn nicht gehalten), wie cmd_vel. Der gait_node skaliert
        auf Meter und nutzt es NUR im SHOW_ACTIVE-State (sonst ignoriert) — der
        Teleop bleibt zustandslos und publisht beides (cmd_vel + cmd_show).
        """
        arr = Float64MultiArray()
        if not self._button(msg, self._deadman_button):
            arr.data = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            return arr
        l6_lat = self._sign_show_lat * self._apply_deadzone(
            self._axis(msg, self._axis_lx))
        l6_vert = self._sign_show_vert * self._apply_deadzone(
            self._axis(msg, self._axis_ly))
        l6_radial = self._sign_show_radial * self._trigger_frac(
            msg, self._axis_l2)
        l1_lat = self._sign_show_lat * self._apply_deadzone(
            self._axis(msg, self._axis_rx))
        l1_vert = self._sign_show_vert * self._apply_deadzone(
            self._axis(msg, self._axis_ry))
        l1_radial = self._sign_show_radial * self._trigger_frac(
            msg, self._axis_r2)
        arr.data = [l6_lat, l6_vert, l6_radial, l1_lat, l1_vert, l1_radial]
        return arr

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

        # 1) Fahren (Sticks, Dead-Man-gated). Plus /cmd_show (Vorderbeine, B4):
        # nur publishen wenn show_enabled — sonst bleibt die (auf HW instabile)
        # Show-Pose komplett unerreichbar (leg_changes/S6). Der gait_node nutzt
        # cmd_show ohnehin nur in SHOW_ACTIVE; ohne den Toggle (s.u.) wird dieser
        # State nie betreten.
        self._cmd_vel_pub.publish(self._twist_from_joy(msg))
        if self._show_enabled:
            self._cmd_show_pub.publish(self._show_from_joy(msg))

        # 2) Stance-Modus cyclen (L2/R2 Edge, NUR ohne R1). Stage 1: ersetzt die
        # frühere stufenlose Höhe (die brach die Lauf-Envelope). L2 = tiefer,
        # R2 = höher. Mit R1 sind die Trigger der Tibia-Curl im Show (B4.11) —
        # zustandslos getrennt. Edge-State mitführen gegen Phantom-Edge.
        l2 = self._axis(msg, self._axis_l2) < self._trigger_threshold
        r2 = self._axis(msg, self._axis_r2) < self._trigger_threshold
        deadman = self._button(msg, self._deadman_button)
        if not deadman:
            if l2 and not self._l2_was:
                self._call_setbool(self._cycle_stance_client, False,
                                   'cycle_stance')   # tiefer
            if r2 and not self._r2_was:
                self._call_setbool(self._cycle_stance_client, True,
                                   'cycle_stance')    # höher
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
        if self._show_enabled and self._longpress(
            self._button_cross, self._button(msg, self._button_cross), now
        ):
            self._show_pose_hook()

        # 4) D-Pad-Intents: ←/→ Gangart (C2), ↑/↓ Tempo-Preset (H2, ersetzt
        # das C3-Schrittweiten-Binding). Rising-Edge.
        dx = self._axis(msg, self._axis_dpad_x) * self._sign_dpad_x
        dy = self._axis(msg, self._axis_dpad_y) * self._sign_dpad_y
        cur_x = self._dpad_dir(dx)
        cur_y = self._dpad_dir(dy)
        # Rising-Edge UND Debounce-Lockout (gegen HAT-Flackern → Doppel-Trigger).
        if (cur_x != 0 and self._dpad_x_prev == 0
                and now - self._dpad_x_last_fire >= self._dpad_lockout_sec):
            # rechts (raw -1 → cur_x<0) = nächste Gangart; links = vorige.
            self._call_setbool(
                self._cycle_gait_client, cur_x < 0, 'cycle_gait'
            )
            self._dpad_x_last_fire = now
        if (cur_y != 0 and self._dpad_y_prev == 0
                and now - self._dpad_y_last_fire >= self._dpad_lockout_sec):
            # hoch (cur_y>0) = schneller; runter = langsamer.
            self._cycle_tempo(cur_y > 0, now)
            self._dpad_y_last_fire = now
        self._dpad_x_prev = cur_x
        self._dpad_y_prev = cur_y

    # ---------- Block H2 — Tempo-Presets (D-Pad ↑/↓) ----------

    def _cycle_tempo(self, faster: bool, now: float) -> bool:
        """
        Tempo-Index cyclen (geklemmt, kein Wrap) — Zwei-Schritt-Protokoll.

        (1) ``cycle_time`` am gait_node setzen (AsyncParameterClient-Future).
        Der gait-seitige standing_only-Guard ist die EINE Wahrheit: lehnt er
        ab (nicht STANDING) oder bleibt die Antwort aus, ändert sich lokal
        NICHTS (kein halber Tempo-Wechsel). (2) Erst im done-Callback bei
        Erfolg die eigenen Scales aus der Tabelle setzen (durch die
        validate-then-apply-Live-Mechanik, Param-Server bleibt konsistent).

        Return (Block I Phase 5): ``True`` = Request rausgegangen bzw. bereits
        am Limit (kein Fehler); ``False`` = blockiert (läuft noch / gait-Param-
        Services nicht bereit). Der D-Pad-Aufrufer ignoriert den Wert; der
        Service ``/hexapod_cycle_tempo`` mappt ihn auf ``SetBool.success``.
        """
        if self._tempo_request_pending:
            if now - self._tempo_request_time < _TEMPO_REQUEST_TIMEOUT_S:
                self.get_logger().warn(
                    'Tempo-Wechsel läuft noch (Antwort ausstehend) — ignoriert.',
                    throttle_duration_sec=2.0,
                )
                return False
            # Timeout: gait_node antwortet nicht (weg zwischen ready-Check
            # und Antwort) → Lock lösen, nichts wurde geändert.
            self._tempo_request_pending = False
            self.get_logger().warn(
                'Tempo-Request-Timeout (gait_node antwortet nicht) — '
                'Scales unverändert.',
            )
        step = 1 if faster else -1
        new_idx = max(0, min(len(_TEMPO_MODES) - 1, self._tempo_idx + step))
        if new_idx == self._tempo_idx:
            self.get_logger().info(
                f'Tempo bereits am {"schnellsten" if faster else "langsamsten"}'
                f' ({_TEMPO_MODES[self._tempo_idx].name})'
            )
            return True
        if not self._gait_param_client.services_are_ready():
            self.get_logger().warn(
                'Tempo-Wechsel: gait_node-Param-Services nicht verfügbar — '
                'ignoriert (läuft gait_node?).',
                throttle_duration_sec=2.0,
            )
            return False
        mode = _TEMPO_MODES[new_idx]
        self._tempo_request_pending = True
        self._tempo_request_time = now
        future = self._gait_param_client.set_parameters([
            Parameter('cycle_time', Parameter.Type.DOUBLE, mode.cycle_time),
        ])
        future.add_done_callback(
            lambda fut: self._on_tempo_response(fut, new_idx)
        )
        return True

    def _on_cycle_tempo(self, request, response):
        """
        Block I Phase 5 — /hexapod_cycle_tempo (SetBool) → ein Tempo-Schritt.

        Wrappt ``_cycle_tempo`` (``data=true`` schneller / ``false`` langsamer).
        ``success`` = wurde ein Schritt initiiert bzw. sind wir schon am Limit
        (True) / blockiert (False: läuft noch / Services nicht bereit). Das
        tatsächliche neue Tempo kommt über ``/hexapod/tempo`` (der App-Dropdown
        cyclet damit zum Ziel). Standing_only greift serverseitig im gait_node.
        """
        ok = self._cycle_tempo(request.data, time.monotonic())
        direction = 'schneller' if request.data else 'langsamer'
        response.success = ok
        response.message = (
            f'tempo cycle {direction} angefordert (Ergebnis via /hexapod/tempo)'
            if ok else
            'tempo cycle blockiert (läuft noch / Param-Services nicht bereit)'
        )
        return response

    def _on_tempo_response(self, future, new_idx: int) -> None:
        """Antwort des gait_node auf den cycle_time-Set auswerten (Schritt 2)."""
        self._tempo_request_pending = False
        mode = _TEMPO_MODES[new_idx]
        exc = future.exception()
        if exc is not None:
            self.get_logger().warn(
                f'Tempo-Wechsel fehlgeschlagen (Service-Fehler: {exc}) — '
                'Scales unverändert.'
            )
            return
        result = future.result().results[0]
        if not result.successful:
            # Typisch: standing_only-Reject (nicht STANDING).
            self.get_logger().warn(
                f'Tempo nur im Stand — gait_node lehnt ab: {result.reason}',
                throttle_duration_sec=2.0,
            )
            return
        # cycle_time ist gesetzt → jetzt die eigenen Scales (validate-then-
        # apply über den TLS-Callback, hält den eigenen Param-Server synchron).
        self._tempo_idx = new_idx
        self.set_parameters([
            Parameter('linear_x_scale', Parameter.Type.DOUBLE,
                      mode.linear_x_scale),
            Parameter('linear_y_scale', Parameter.Type.DOUBLE,
                      mode.linear_y_scale),
            Parameter('angular_z_scale', Parameter.Type.DOUBLE,
                      mode.angular_z_scale),
        ])
        self.get_logger().info(
            f'Tempo -> {mode.name} (cycle_time={mode.cycle_time}, scales='
            f'{mode.linear_x_scale}/{mode.linear_y_scale}/'
            f'{mode.angular_z_scale})'
        )
        # Block I Phase 5 — geändertes Tempo-Preset fürs Overlay latchen.
        self._publish_tempo()

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

    def _publish_tempo(self) -> None:
        """
        Block I Phase 5 — aktives Tempo-Preset + Live-Scales fürs Overlay (JSON).

        Latched auf ``/hexapod/tempo``; publiziert beim Start + nach jedem
        Tempo-Wechsel (``_on_tempo_response``). Die Scales sind die aktuell
        wirksamen (``self._*_scale``) — ein Tempo-Preset setzt sie, ein manueller
        Config-Panel-Param-Set ebenfalls (dann liest die App selbst nach).
        Contract §6 (Phase 5).
        """
        payload = {
            'tempo': _TEMPO_MODES[self._tempo_idx].name,
            'tempo_idx': self._tempo_idx,
            'linear_x_scale': self._linear_x_scale,
            'linear_y_scale': self._linear_y_scale,
            'angular_z_scale': self._angular_z_scale,
        }
        self._tempo_pub.publish(String(data=json.dumps(payload)))

    def _dpad_dir(self, value: float) -> int:
        """Diskrete D-Pad-Richtung: +1 / -1 / 0 anhand der Schwelle."""
        if value > self._dpad_threshold:
            return 1
        if value < -self._dpad_threshold:
            return -1
        return 0

    def _call_intent(self, client, name: str) -> None:
        """Rufe einen Trigger-Intent fire-and-forget; sonst einmal WARN."""
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

    def _call_setbool(self, client, data: bool, name: str) -> None:
        """Rufe einen SetBool-Intent (data) fire-and-forget; sonst einmal WARN."""
        if not client.service_is_ready():
            attr = f'_{name}_logged'
            if not getattr(self, attr, True):
                self.get_logger().warn(
                    f'Intent "{name}": Service nicht verfügbar — ignoriert '
                    '(läuft gait_node?).'
                )
                setattr(self, attr, True)
            return
        req = SetBool.Request()
        req.data = data
        client.call_async(req)
        self.get_logger().info(f'Intent gesendet: {name}={data}')

    def _show_pose_hook(self) -> None:
        """
        Show-Pose-HOOK (Cross lang, B4): Toggle-Intent an den gait_node.

        Reines UI — der Teleop kennt den State nicht; der gait_node löst auf
        (STANDING → Show einnehmen, SHOW_* → wieder heraus nach STANDING).
        Die Vorderbein-Bewegung läuft separat über /cmd_show (siehe
        ``_show_from_joy``), nur in SHOW_ACTIVE wirksam.
        """
        self._call_intent(self._show_toggle_client, 'show_toggle')


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
