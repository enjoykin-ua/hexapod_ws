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

Phase 6: zusätzlich ``/cmd_body_height``-Subscription. Erlaubt
Runtime-Mutation der ``GaitEngine.body_height`` — nur wenn Engine im
STANDING-State (Sicherheit gegen Kippen mitten im Walk-Cycle).

Pub-Pattern: 50 Hz Timer-Tick, pro Tick eine 1-Punkt-JointTrajectory
mit ``time_from_start = 2 × (1/tick_rate) = 0.04 s``. JTC interpoliert
linear zwischen Goals → smooth Bewegung.
"""

from dataclasses import dataclass
import time
import xml.etree.ElementTree as ET

from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Twist
from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_kinematics import HEXAPOD, IKError, JointLimits
from rcl_interfaces.msg import (
    FloatingPointRange,
    ParameterDescriptor,
    ParameterType,
    SetParametersResult,
)
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from std_srvs.srv import SetBool, Trigger
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


# =====================================================================
# Stage 0.6 — URDF Joint-Limits Parser
# =====================================================================
def parse_joint_limits_from_urdf(urdf_xml: str) -> dict[str, JointLimits]:
    """
    Parse <joint><limit lower upper> tags from a URDF/xacro-expanded XML string.

    Returns dict keyed by leg name (e.g. "leg_1") with one JointLimits per
    leg, built from the three per-leg joints (coxa/femur/tibia). Joints
    whose name doesn't match the ``leg_<n>_{coxa,femur,tibia}_joint``
    convention are silently ignored (e.g. fixed joints, fingers in some
    future variant). Legs that aren't fully covered (missing one or more
    joints) are dropped — partial entries would be a bug magnet at
    runtime.

    Empty or invalid URDF → empty dict (gait_engine falls back to lenient
    mode, = Phase-5 behaviour). This makes the limits-injection feature
    opt-in: if the launch-file doesn't pass robot_description, nothing
    breaks; only the Stage-0.6 freeze is silently disabled.
    """
    if not urdf_xml.strip():
        return {}
    try:
        root = ET.fromstring(urdf_xml)
    except ET.ParseError:
        return {}

    # Collect raw per-joint limits keyed by joint name.
    per_joint: dict[str, tuple[float, float]] = {}
    for j in root.iter('joint'):
        jname = j.attrib.get('name', '')
        if not jname.startswith('leg_'):
            continue
        limit_el = j.find('limit')
        if limit_el is None:
            continue
        try:
            lower = float(limit_el.attrib['lower'])
            upper = float(limit_el.attrib['upper'])
        except (KeyError, ValueError):
            continue
        per_joint[jname] = (lower, upper)

    # Build per-leg JointLimits from the joint triplets.
    result: dict[str, JointLimits] = {}
    for leg in HEXAPOD.legs:
        coxa = per_joint.get(f'{leg.name}_coxa_joint')
        femur = per_joint.get(f'{leg.name}_femur_joint')
        tibia = per_joint.get(f'{leg.name}_tibia_joint')
        if coxa is None or femur is None or tibia is None:
            continue  # incomplete triple → drop, lenient mode for this leg
        result[leg.name] = JointLimits(
            coxa_lower=coxa[0], coxa_upper=coxa[1],
            femur_lower=femur[0], femur_upper=femur[1],
            tibia_lower=tibia[0], tibia_upper=tibia[1],
        )
    return result


# =====================================================================
# Phase 11 Stage A — gait_node Parameter-Specs (Single Source of Truth)
# =====================================================================
#
# Alle 14 live-tunbaren gait_node-Parameter sind hier in einer Tabelle
# definiert: Name, Default, Range/Constraint, STANDING-only-Flag.
#
# Vorteile:
# - Slider-Min/Max + Step an einem Ort einstellbar
# - _STANDING_ONLY_PARAMS-Set wird abgeleitet, nicht doppelt gepflegt
# - declare_parameter-Loop deklariert alle einheitlich
#
# Was hier NICHT lebt: die ``_apply_param``-Apply-Logik. Pro Param ist
# die wirklich unique (Engine-Attribute, Timer-Restart, Pattern-Load)
# — bleibt als if/elif-Chain im Node.
#
# Stage-B-Vorbild: analoges Pattern für 72 Pin-Cal-Params.


@dataclass(frozen=True)
class _ParamSpec:
    """Deklarations-Spec für einen gait_node-Parameter."""

    name: str
    default: float | str
    description: str
    standing_only: bool = False
    fp_range: tuple[float, float, float] | None = None  # (min, max, step)
    string_constraint: str | None = None  # additional_constraints für String


_GAIT_PARAMS: tuple[_ParamSpec, ...] = (
    _ParamSpec(
        name='gait_pattern', default='tripod', standing_only=True,
        string_constraint=(
            'valid values: tripod | wave | single_leg_1 .. single_leg_6'
        ),
        description=(
            'Gait-Pattern-Name aus GAIT_PRESETS. '
            'Live-Wechsel nur in STANDING-State (Engine-Reset-Risiko).'
        ),
    ),
    _ParamSpec(
        name='step_height', default=0.03,
        fp_range=(0.005, 0.10, 0.001),
        description=(
            'Foot-Hub-Höhe im Swing (m). '
            'Live-Update wirkt ab nächstem Swing.'
        ),
    ),
    _ParamSpec(
        name='cycle_time', default=2.0, standing_only=True,
        fp_range=(0.5, 6.0, 0.05),
        description=(
            'Zeit pro Gait-Cycle (s). '
            'Live-Update nur in STANDING (Stride-Math-Konsistenz).'
        ),
    ),
    _ParamSpec(
        name='tick_rate', default=50.0, standing_only=True,
        fp_range=(10.0, 200.0, 1.0),
        description=(
            'Timer-Frequenz für gait-Tick (Hz). '
            'Live-Update nur in STANDING (Timer-Restart-Race).'
        ),
    ),
    _ParamSpec(
        name='body_height', default=-0.080, standing_only=True,
        fp_range=(-0.120, -0.020, 0.001),
        description=(
            'Stand-Pose Foot-Z im Bein-Frame (m). '
            'Phase 13 Stage 0.4: Default -0.080 (mit radial 0.295). Der alte '
            '-0.052 verletzte mit radial 0.27 das Tibia-Limit (1.33>1.161 rad) '
            '-> HW-Freeze; in der lenienten Phase-5-Sim nie aufgefallen. '
            'Live-Update nur in STANDING (analog cmd_body_height).'
        ),
    ),
    _ParamSpec(
        name='radial_distance', default=0.295, standing_only=True,
        fp_range=(0.10, 0.35, 0.001),
        description=(
            'Radialer Foot-Neutral-Abstand vom Coxa-Mount '
            'im Bein-Frame (m). Phase 13 Stage 0.4: Default 0.295 (war 0.27). '
            'Weiter gestreckt -> Tibia knickt weniger -> in URDF-Limit '
            '(Tibia -1.00/+2.50 ab Stage 1 Teil 2.1; war +1.30). Gueltige '
            '(body_height, radial)-Paare siehe '
            'phase_13_stage_0_4_standup_plan.md Tab. 3.3. '
            'Live-Update nur in STANDING (Stand-Pose-Reset).'
        ),
    ),
    _ParamSpec(
        name='standup_radial_distance', default=0.295, standing_only=True,
        fp_range=(0.10, 0.35, 0.001),
        description=(
            'Phase 13 Stage 1 Teil 2.3 (Zwei-Phasen): radialer Foot-Abstand '
            'für die AUFSTEH-Pose (m). Breit genug, dass der Standup-Touchdown '
            '(Bauch am Boden) den Femur nicht über ±90° zwingt. Nach dem '
            'Aufstehen repositioniert die Engine per Tripod auf radial_distance '
            '(die nähere Walk-Pose). standup==radial_distance → keine '
            'Reposition (Default-Verhalten). Live nur in STANDING.'
        ),
    ),
    _ParamSpec(
        name='reposition_cycle_time', default=2.0, standing_only=True,
        fp_range=(1.0, 10.0, 0.1),
        description=(
            'Phase 13 Stage 1 Teil 2.3: Dauer der Tripod-Reposition '
            'standup_radial → radial_distance (s). Min 1.0 s gegen '
            'Schnapp-Bewegung/Kipp-Risiko am Boden. Live nur in STANDING '
            '(nicht mid-Reposition — Timing-Race).'
        ),
    ),
    _ParamSpec(
        name='time_from_start_factor', default=2.0,
        fp_range=(1.0, 10.0, 0.1),
        description=(
            'JTC time_from_start = factor / tick_rate. '
            'Lookahead-Math-Faktor. Live-Update wirkt sofort.'
        ),
    ),
    _ParamSpec(
        name='step_length_max', default=0.05,
        fp_range=(0.01, 0.15, 0.001),
        description=(
            'Max Stride pro Cycle (m). Begrenzt linear_max = '
            'step_length_max / stance_duration. Live-Update wirkt '
            'sofort auf nächsten Cycle.'
        ),
    ),
    _ParamSpec(
        name='default_linear_x', default=0.0,
        fp_range=(-0.1, 0.1, 0.005),
        description=(
            'Fallback cmd_vel.linear.x bei cmd_vel-Timeout (m/s). '
            'Live-Update wirkt beim nächsten Timeout-Check.'
        ),
    ),
    _ParamSpec(
        name='default_linear_y', default=0.0,
        fp_range=(-0.1, 0.1, 0.005),
        description=(
            'Fallback cmd_vel.linear.y bei cmd_vel-Timeout (m/s). '
            'Live-Update wirkt beim nächsten Timeout-Check.'
        ),
    ),
    _ParamSpec(
        name='default_angular_z', default=0.0,
        fp_range=(-1.0, 1.0, 0.05),
        description=(
            'Fallback cmd_vel.angular.z bei cmd_vel-Timeout (rad/s). '
            'Live-Update wirkt beim nächsten Timeout-Check.'
        ),
    ),
    _ParamSpec(
        name='cmd_vel_timeout', default=0.5,
        fp_range=(0.05, 5.0, 0.05),
        description=(
            'cmd_vel-Activity-Timeout (s). Nach Timeout greifen '
            'default_linear_x/y/angular_z. Live-Update wirkt sofort.'
        ),
    ),
    _ParamSpec(
        name='body_height_min', default=-0.115, standing_only=True,
        fp_range=(-0.120, -0.020, 0.001),
        description=(
            'Untere Schranke body_height (m). Cross-Constraint: '
            'min < body_height < max. Phase 13 Stage 0.4: -0.115 (war -0.080) '
            '— innerhalb des bei radial 0.295 gueltigen Bereichs (bis -0.120). '
            'STANDING-only.'
        ),
    ),
    _ParamSpec(
        name='body_height_max', default=-0.030, standing_only=True,
        fp_range=(-0.120, -0.020, 0.001),
        description=(
            'Obere Schranke body_height (m). Cross-Constraint: '
            'min < body_height < max. STANDING-only.'
        ),
    ),
    _ParamSpec(
        name='auto_standup_duration', default=8.0, standing_only=True,
        fp_range=(1.0, 15.0, 0.1),
        description=(
            'Phase 13 Stage A: Dauer der Auto-Stand-Pose-Ramp in s. '
            'Wird beim ersten /joint_states-Empfang getriggert; Engine '
            'lerpt von der aktuellen Joint-Pose smooth zur Default-Stand-'
            'Pose. Default 8.0 s (Stage 0.7: langsamer = niedrigerer Strom-'
            'Spitzenwert / weniger PSU-Spannungseinbruch beim Hochdruecken). '
            'STANDING-only (Live-Update nach Ramp-Ende moeglich).'
        ),
    ),
    _ParamSpec(
        name='standup_mode', default='cartesian', standing_only=True,
        string_constraint='valid values: cartesian | joint_space',
        description=(
            'Phase 13 Stage 0.7: Aufsteh-Modus. "cartesian" (default) = '
            'schuerffreies Zwei-Phasen-Aufstehen (Touchdown + senkrechter '
            'Push mit fixen Fuessen). "joint_space" = Legacy-STARTUP_RAMP '
            '(joint-space-Lerp, schuerft am Boden). STANDING-only.'
        ),
    ),
    _ParamSpec(
        name='standup_phase1_fraction', default=0.4, standing_only=True,
        fp_range=(0.1, 0.9, 0.05),
        description=(
            'Phase 13 Stage 0.7: Anteil der Aufsteh-Dauer auf Phase 1 '
            '(Touchdown), Rest = Phase 2 (Push). Nur bei standup_mode='
            'cartesian. Default 0.4. STANDING-only.'
        ),
    ),
    _ParamSpec(
        name='body_height_start', default=-0.0135, standing_only=True,
        fp_range=(-0.030, 0.005, 0.0005),
        description=(
            'Phase 13 Stage 0.7: Foot-z relativ Coxa beim Touchdown '
            '(Coxa-Hoehe bei aufliegendem Bauch, negativ). Default '
            '-0.0135 m (Bauch-Box 0.043 / Foot-R 0.008, siehe '
            'standup_envelope_check.py). Nur bei standup_mode=cartesian. '
            'Real justierbar. STANDING-only.'
        ),
    ),
    # Block B1 — Hinsetz-/Abschalt-Sequenz. Nicht STANDING-only: werden beim
    # Sit-down-Trigger (Service/Fail-safe) gelesen, nicht mid-State mutiert.
    _ParamSpec(
        name='sitdown_duration', default=5.0,
        fp_range=(1.0, 15.0, 0.1),
        description=(
            'Block B1: Dauer Phase 2+3 des Hinsetzens (Lower + Flatten) in s. '
            'Phase 1 (Füße raus) nutzt reposition_cycle_time. Analog '
            'auto_standup_duration; langsamer = stromschonenderes Absenken.'
        ),
    ),
    _ParamSpec(
        name='sitdown_lower_fraction', default=0.6,
        fp_range=(0.1, 0.9, 0.05),
        description=(
            'Block B1: Anteil von sitdown_duration auf Phase 2 (Lower, '
            'lasttragendes Absenken), Rest = Phase 3 (Flatten zu rad 0). '
            'Default 0.6.'
        ),
    ),
    _ParamSpec(
        name='comms_loss_sitdown_timeout', default=0.0,
        fp_range=(0.0, 30.0, 0.5),
        description=(
            'Block B1: Comms-Loss-Fail-safe (s). 0 = AUS (Default). >0: wenn '
            'so lange kein /cmd_vel mehr ankam (echtes Disconnect; idle-'
            'Controller autorepeatet 0) und der Roboter STEHT, automatisch '
            'Hinsetzen (Rest, bestromt). Aus WALKING stoppt erst der '
            'cmd_vel_timeout. Auf 0 lassen ohne Controller (sonst false-fire).'
        ),
    ),
)

# Phase 13 Stage A — Timeout-Warning fuer fehlende /joint_states.
# Wenn nach diesem Zeitraum kein /joint_states empfangen wurde, wird
# einmalig ein ERROR-Log gefeuert (typische Ursache: joint_state_
# broadcaster nicht gestartet / gecrasht).
_JOINT_STATES_TIMEOUT_S = 10.0


# Abgeleitet aus _GAIT_PARAMS — keine Doppel-Pflege.
_STANDING_ONLY_PARAMS = frozenset(
    p.name for p in _GAIT_PARAMS if p.standing_only
)


class GaitNode(Node):
    """50 Hz Timer-Loop, gait_engine -> 6 JointTrajectory-Pubs."""

    def __init__(self):
        super().__init__('gait_node')

        self._declare_params_with_descriptors()

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
        # Phase 13 Stage 1 Teil 2.3 — Zwei-Phasen Standup → Reposition.
        self._standup_radial_distance = float(
            self.get_parameter('standup_radial_distance').value
        )
        self._reposition_cycle_time = float(
            self.get_parameter('reposition_cycle_time').value
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
        self._body_height_min = float(
            self.get_parameter('body_height_min').value
        )
        self._body_height_max = float(
            self.get_parameter('body_height_max').value
        )
        self._auto_standup_duration = float(
            self.get_parameter('auto_standup_duration').value
        )
        # Phase 13 Stage 0.7 — Aufsteh-Modus + cartesian-Parameter.
        self._standup_mode = str(
            self.get_parameter('standup_mode').value
        )
        self._standup_phase1_fraction = float(
            self.get_parameter('standup_phase1_fraction').value
        )
        self._body_height_start = float(
            self.get_parameter('body_height_start').value
        )
        # Block B1 — Hinsetz-/Abschalt-Parameter.
        self._sitdown_duration = float(
            self.get_parameter('sitdown_duration').value
        )
        self._sitdown_lower_fraction = float(
            self.get_parameter('sitdown_lower_fraction').value
        )
        self._comms_loss_sitdown_timeout = float(
            self.get_parameter('comms_loss_sitdown_timeout').value
        )

        self._tfs_seconds = self._tfs_factor / self._tick_rate

        # Stage 0.6: parse joint-limits from the URDF (passed in as the
        # `robot_description` parameter, conventionally set by the
        # launch-file via xacro-expansion). Empty/missing → empty dict
        # → gait_engine runs lenient (phase-5 behaviour preserved).
        self.declare_parameter(
            'robot_description', '',
            ParameterDescriptor(
                type=ParameterType.PARAMETER_STRING,
                description=(
                    'URDF XML. If set, per-leg joint limits are parsed '
                    'and passed to gait_engine for Stage-0.6 freeze.'),
                read_only=True,
            ),
        )
        urdf_xml = str(self.get_parameter('robot_description').value)
        joint_limits = parse_joint_limits_from_urdf(urdf_xml)
        if joint_limits:
            self.get_logger().info(
                f'Stage 0.6: parsed joint limits for {len(joint_limits)} '
                'legs from robot_description'
            )
        else:
            self.get_logger().warn(
                'Stage 0.6: robot_description empty or unparseable — '
                'IK runs in lenient mode (no joint-limit freeze)'
            )

        self._engine = GaitEngine(
            pattern=self._pattern,
            step_height=self._step_height,
            cycle_time=self._cycle_time,
            radial_distance=self._radial_distance,
            body_height=self._body_height,
            step_length_max=self._step_length_max,
            joint_limits=joint_limits,
            standup_radial_distance=self._standup_radial_distance,
            reposition_cycle_time=self._reposition_cycle_time,
        )

        # Stage 0.6: async service-client for the hexapod_safety_freeze
        # service. On IKError in _tick we fire-and-forget a Trigger call;
        # the effective local stop is the missing publish in that tick,
        # the service is just the explicit "tell plugin to hard-stop too"
        # signal. Service not available (sim without plugin) → call
        # silently no-ops, gait still stops locally.
        self._safety_freeze_client = self.create_client(
            Trigger, '/hexapod_safety_freeze')
        self._safety_freeze_logged_unreachable = False

        # Block B1 — Relay-Client (/hexapod_relay_set, SetBool). data=False
        # öffnet das Relay (Servos stromlos). Gefeuert beim Shutdown, sobald
        # die Hinsetz-Sequenz SAT erreicht. Service fehlt (Sim ohne Plugin) →
        # einmal WARN + skip (wie _trigger_safety_freeze).
        self._relay_set_client = self.create_client(
            SetBool, '/hexapod_relay_set')
        self._relay_logged_unreachable = False

        # Block B1 — Sit-down/Shutdown-State (Node-seitig):
        #  _latest_joints: zuletzt empfangene vollständige Joint-Pose (für
        #    stand_up aus SAT, start-pose-agnostisch).
        #  _relay_off_after_sat: Shutdown wurde getriggert → beim Erreichen von
        #    SAT Relay-Aus feuern.
        #  _shutdown_latched: nach Relay-Aus terminal — stand_up wird abgelehnt
        #    bis Relay-On/Reboot.
        self._latest_joints: dict[str, tuple] = {}
        self._relay_off_after_sat = False
        self._shutdown_latched = False
        # Block B1 (User 2026-06-03): Boot-/Spawn-Pose (erste vollständige
        # /joint_states) als SAT-Ruhe-Pose. Der Roboter setzt sich am Ende in
        # genau die Pose, in der er gespawnt/gebootet ist (Beine hoch) — das
        # passive Hinlegen der Beine passiert erst beim Relay-Aus.
        self._spawn_joints: dict[str, tuple] = {}

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

        self._cmd_body_height_sub = self.create_subscription(
            Float64, '/cmd_body_height', self._on_cmd_body_height, 10
        )

        # Phase 13 Stage A — /joint_states-Subscriber fuer Ramp-Trigger.
        # Erstes Empfang loest start_ramp() mit den aktuellen Joint-
        # Positions als Start aus. Bis dahin publisht _tick KEINE
        # Trajectories (sonst wuerde JTC sofort zur Stand-Pose-Lerp-
        # Start-Position springen statt vom realen Joint-State zu
        # rampen). Best-Effort: wenn ein Joint im JointState fehlt,
        # warten wir auf die naechste Message.
        self._joint_states_sub = self.create_subscription(
            JointState, '/joint_states', self._on_joint_states, 10
        )

        # Wall-clock-Start (time.monotonic) statt Sim-Zeit, damit der
        # Loop nicht an /clock-DDS-Discovery-Race scheitert.
        self._t_start = time.monotonic()
        self._last_cmd_time: float | None = None
        self._last_cmd_v_x = 0.0
        self._last_cmd_v_y = 0.0
        self._last_cmd_omega_z = 0.0

        # Phase 13 Stage A — Ramp-Trigger-State.
        # _ramp_triggered=True ab erstem vollstaendigem /joint_states-
        # Empfang (alle 18 Joints gefunden). Vorher: _tick publisht
        # keine Trajectories. _joint_states_timeout_logged: einmaliger
        # ERROR nach _JOINT_STATES_TIMEOUT_S ohne Empfang.
        self._ramp_triggered = False
        self._joint_states_timeout_logged = False

        # Phase 11 Stage A — Timer in MutuallyExclusiveCallbackGroup,
        # damit _restart_timer() bei tick_rate-Update keinen Race mit
        # einem aktiven _tick produziert (relevant für MultiThreaded-
        # Executor; bei SingleThreaded ohnehin sequentiell).
        self._cb_group = MutuallyExclusiveCallbackGroup()
        self._timer = self.create_timer(
            1.0 / self._tick_rate,
            self._tick,
            callback_group=self._cb_group,
        )

        # Block B1 — Hinsetz-/Abschalt-Services. In derselben
        # MutuallyExclusiveCallbackGroup wie der Timer → kein Race mit _tick
        # auf den Engine-State (relevant nur unter MultiThreadedExecutor;
        # default SingleThreaded ohnehin sequentiell).
        self._sit_down_srv = self.create_service(
            Trigger, '/hexapod_sit_down', self._on_sit_down,
            callback_group=self._cb_group,
        )
        self._stand_up_srv = self.create_service(
            Trigger, '/hexapod_stand_up', self._on_stand_up,
            callback_group=self._cb_group,
        )
        self._shutdown_srv = self.create_service(
            Trigger, '/hexapod_shutdown', self._on_shutdown,
            callback_group=self._cb_group,
        )

        # Phase 11 Stage A — Live-Param-Updates via rqt_reconfigure.
        self.add_on_set_parameters_callback(self._on_param_change)

        self.get_logger().info(
            f'gait_node init: pattern={self._pattern.name}, '
            f'step_height={self._step_height:.3f} m, '
            f'cycle_time={self._cycle_time:.2f} s, '
            f'body_height={self._body_height:.3f} m '
            f'(range [{self._body_height_min:.3f}, '
            f'{self._body_height_max:.3f}]), '
            f'step_length_max={self._step_length_max:.3f} m '
            f'(linear_max={self._engine.linear_max:.3f} m/s), '
            f'defaults=(linear_x={self._default_linear_x:.3f}, '
            f'linear_y={self._default_linear_y:.3f}, '
            f'angular_z={self._default_angular_z:.3f}), '
            f'cmd_vel_timeout={self._cmd_vel_timeout:.2f} s, '
            f'tick_rate={self._tick_rate:.0f} Hz, '
            f'auto_standup_duration={self._auto_standup_duration:.2f} s '
            '(waiting for /joint_states to trigger ramp)'
        )

    def _declare_params_with_descriptors(self) -> None:
        """
        Deklariere alle Parameter aus ``_GAIT_PARAMS`` mit Descriptors.

        Range-Descriptors ermöglichen rqt_reconfigure-Slider statt
        Text-Eingabe-Felder. Spec-Tabelle ist Single Source of Truth
        für Defaults, Ranges und STANDING-only-Policy — siehe
        ``_GAIT_PARAMS`` am Modul-Anfang.

        Phase 11 Stage A — siehe phase_11_stage_a_plan.md.
        """
        for spec in _GAIT_PARAMS:
            kwargs = {
                'description': spec.description,
                'type': (
                    ParameterType.PARAMETER_STRING
                    if isinstance(spec.default, str)
                    else ParameterType.PARAMETER_DOUBLE
                ),
            }
            if spec.fp_range is not None:
                mn, mx, step = spec.fp_range
                kwargs['floating_point_range'] = [
                    FloatingPointRange(
                        from_value=mn, to_value=mx, step=step,
                    ),
                ]
            if spec.string_constraint is not None:
                kwargs['additional_constraints'] = spec.string_constraint
            self.declare_parameter(
                spec.name, spec.default,
                ParameterDescriptor(**kwargs),
            )

    def _on_cmd_vel(self, msg: Twist) -> None:
        """cmd_vel-Empfang: Activity-Timestamp + 3 Komponenten cachen."""
        self._last_cmd_time = time.monotonic()
        self._last_cmd_v_x = float(msg.linear.x)
        self._last_cmd_v_y = float(msg.linear.y)
        self._last_cmd_omega_z = float(msg.angular.z)

    def _on_joint_states(self, msg: JointState) -> None:
        """
        Phase 13 Stage A — beim ersten vollstaendigen Empfang: Ramp triggern.

        Wir bauen ein dict ``{leg_name: (coxa, femur, tibia)}`` aus dem
        JointState. Wenn ein Joint fehlt (z.B. JointState kommt von
        einem partiellen Broadcaster): wir warten auf die naechste
        Message — keine Ramp-Trigger.

        Nach erfolgreichem Trigger: Subscriber bleibt registriert
        (kein destroy), aber die Methode returnt sofort wenn
        ``_ramp_triggered``. Das vermeidet teures Re-Parsing bei
        jedem JointState-Tick im Standby.
        """
        # JointState als name/position arrays parsen. Verfuegbar machen
        # als dict {joint_name: position} fuer einfacheres Lookup.
        if len(msg.name) != len(msg.position):
            # Defekte Message — ignorieren, naechste abwarten
            return
        positions = dict(zip(msg.name, msg.position))

        start_joints: dict[str, tuple] = {}
        for leg in HEXAPOD.legs:
            coxa_name = f'{leg.name}_coxa_joint'
            femur_name = f'{leg.name}_femur_joint'
            tibia_name = f'{leg.name}_tibia_joint'
            if (
                coxa_name not in positions
                or femur_name not in positions
                or tibia_name not in positions
            ):
                # Unvollstaendige Joint-Liste — auf naechste Message warten
                return
            start_joints[leg.name] = (
                float(positions[coxa_name]),
                float(positions[femur_name]),
                float(positions[tibia_name]),
            )

        # Block B1: aktuelle vollständige Pose IMMER cachen (auch nach dem
        # Boot-Ramp-Trigger) — der stand_up-Service braucht sie als start-pose-
        # agnostischen Aufsteh-Start aus SAT.
        self._latest_joints = start_joints

        # Block B1: die erste vollständige Pose = Spawn-/Boot-Pose festhalten
        # (SAT-Ruhe-Ziel beim Hinsetzen). Genau hier, VOR dem Ramp-Trigger, ist
        # es noch die ungestandene Start-Pose.
        if not self._spawn_joints:
            self._spawn_joints = start_joints

        if self._ramp_triggered:
            return

        # Alle 18 Joints da → Aufstehen triggern. Stage 0.7: Modus-Switch
        # cartesian (default, schuerffrei) vs. joint_space (Legacy-Ramp).
        now = time.monotonic()
        t = now - self._t_start
        cartesian = self._standup_mode == 'cartesian'
        try:
            if cartesian:
                self._engine.start_cartesian_standup(
                    start_joints, t, self._auto_standup_duration,
                    self._standup_phase1_fraction, self._body_height_start,
                )
            else:
                self._engine.start_ramp(
                    start_joints, t, self._auto_standup_duration,
                )
        except (ValueError, IKError) as exc:
            # IKError/ValueError bei der Aufsteh-Initialisierung waere ein
            # Configuration-Bug (radial/body_height/phase1 nicht gueltig) —
            # log + drop. Engine bleibt in STANDING (Default). User muss
            # params korrigieren.
            self.get_logger().error(
                f'Auto-Standup ({self._standup_mode}) failed to start: {exc}'
            )
            self._ramp_triggered = True  # nicht nochmal versuchen
            return

        self._ramp_triggered = True
        if cartesian:
            self.get_logger().info(
                f'Cartesian-Standup gestartet: '
                f'{self._auto_standup_duration:.2f} s '
                f'(phase1={self._standup_phase1_fraction:.2f}, '
                f'bh_start={self._body_height_start:.4f}) zur Stand-Pose '
                f'(radial={self._radial_distance:.3f}, '
                f'body_height={self._body_height:.3f})'
            )
        else:
            self.get_logger().info(
                f'Auto-Stand-Pose-Ramp (joint-space) gestartet: '
                f'{self._auto_standup_duration:.2f} s zur Default-Stand-Pose '
                f'(radial={self._radial_distance:.3f}, '
                f'body_height={self._body_height:.3f})'
            )

    def _on_cmd_body_height(self, msg: Float64) -> None:
        """
        body_height-Update: nur wenn Engine im STANDING-State.

        Phase-6-Sicherheits-Constraint: Body-Pose-Wechsel mitten im
        Walk-Cycle würde den Roboter zum Kippen bringen. Daher
        ignorieren wir Updates während WALKING/STOPPING mit
        Warning-Log.
        """
        if self._engine.state != GaitEngine.STATE_STANDING:
            self.get_logger().warn(
                f'cmd_body_height ignored: state={self._engine.state}, '
                'must be STANDING.',
                throttle_duration_sec=1.0,
            )
            return

        target = float(msg.data)
        clamped = max(
            self._body_height_min,
            min(self._body_height_max, target),
        )
        if clamped != target:
            self.get_logger().warn(
                f'cmd_body_height clamped: {target:.4f} -> {clamped:.4f} '
                f'(range [{self._body_height_min:.3f}, '
                f'{self._body_height_max:.3f}])'
            )

        # Phase 11 Stage A — Node-Member synchron halten mit Engine.
        # Sonst würde Stage-A-Param-Callback in der Cross-Constraint-
        # Pre-Validation einen veralteten body_height lesen.
        self._body_height = clamped
        self._engine.body_height = clamped
        self.get_logger().info(
            f'body_height -> {clamped:.4f} m'
        )

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

        # Phase 13 Stage A — pre-Ramp: solange kein /joint_states empfangen
        # wurde, KEINE Trajectories publishen. Sonst wuerde JTC sofort
        # zur Stand-Pose-IK-Pose springen statt sanft von der realen
        # Joint-Position zu rampen. Plus einmalige Timeout-WARN nach
        # _JOINT_STATES_TIMEOUT_S — typische Ursache: joint_state_
        # broadcaster nicht aktiv.
        if not self._ramp_triggered:
            elapsed = now - self._t_start
            if (
                elapsed > _JOINT_STATES_TIMEOUT_S
                and not self._joint_states_timeout_logged
            ):
                self.get_logger().error(
                    f'No /joint_states received within '
                    f'{_JOINT_STATES_TIMEOUT_S:.0f} s — gait_node will not '
                    'start Auto-Stand-Pose-Ramp. Check that '
                    'joint_state_broadcaster is running and publishing.'
                )
                self._joint_states_timeout_logged = True
            return

        # Block B1 — Comms-Loss-Fail-safe (opt-in). Kann eine Hinsetz-Sequenz
        # starten (nur aus STANDING); danach ignoriert set_command cmd_vel.
        self._check_comms_loss(now)

        # Phase 13 Stage A — WARN wenn cmd_vel waehrend STARTUP_RAMP
        # ankommt (Engine ignoriert es eh in set_command). Throttled
        # damit auch ein rate-publisher (50 Hz cmd_vel) nicht spammt.
        v_x, v_y, omega_z = self._resolve_command(now)
        if (
            self._engine.state == GaitEngine.STATE_STARTUP_RAMP
            and (abs(v_x) + abs(v_y) + abs(omega_z)) > 1e-4
        ):
            self.get_logger().warn(
                'cmd_vel received during STARTUP_RAMP — ignored. Wait '
                f'~{self._auto_standup_duration:.1f} s for ramp to complete.',
                throttle_duration_sec=2.0,
            )

        # State VOR set_command merken, damit wir den
        # STARTUP_RAMP→STANDING-Uebergang loggen koennen, der entweder
        # in set_command (n/a, da Ramp cmd_vel ignoriert) ODER in
        # compute_joint_angles (progress>=1) passiert.
        state_before = self._engine.state

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
            # Stage 0.6: IKError covers two cases:
            #  - geometric "out of reach ..." (Phase-5 case)
            #  - "joint limit ..." (new, Stage-0.6 case)
            # Effective local stop: we return without publishing — JTC
            # holds the last good trajectory.
            self.get_logger().error(f'gait_engine: {exc}')

            # For joint-limit violations, additionally trigger the plugin
            # hard-stop via /hexapod_safety_freeze (async fire-and-forget,
            # Q3-decision: realtime safety over confirmation).
            if 'joint limit' in str(exc):
                self._trigger_safety_freeze()
            return

        # Phase 13 Stage A — State-Transition-Log (einmal beim Wechsel)
        if (
            state_before == GaitEngine.STATE_STARTUP_RAMP
            and self._engine.state == GaitEngine.STATE_STANDING
        ):
            self.get_logger().info(
                'Engine state: STARTUP_RAMP -> STANDING '
                '(Auto-Stand-Pose-Ramp complete)'
            )

        for leg in HEXAPOD.legs:
            traj = self._build_trajectory(leg.name, angles_per_leg[leg.name])
            self._pubs[leg.name].publish(traj)

        # Block B1 — Shutdown: sobald die Hinsetz-Sequenz SAT erreicht hat,
        # Relay-Aus feuern + terminal latchen (genau einmal). SAT hält danach
        # rad 0; auf HW ist das Relay offen → Servos stromlos/schlaff.
        if (
            self._relay_off_after_sat
            and self._engine.state == GaitEngine.STATE_SAT
        ):
            self.get_logger().info('SAT erreicht — Shutdown: Relay-Aus')
            self._do_relay_off_and_latch()

    def _trigger_safety_freeze(self) -> None:
        """
        Stage 0.6: async-call /hexapod_safety_freeze on IK joint-limit error.

        Fire-and-forget — we do NOT await the response (would block the
        50 Hz tick, see Q3-decision 2026-05-24). The effective stop is
        already in place by the time this fires: _tick returns without
        publishing a new trajectory, so JTC holds the last good position.

        If the service is unreachable (e.g. sim without hexapod_hardware
        plugin), we log once and continue. The local stop is sufficient
        in sim — there's no servo to slam in any case.
        """
        if not self._safety_freeze_client.service_is_ready():
            if not self._safety_freeze_logged_unreachable:
                self.get_logger().error(
                    '/hexapod_safety_freeze service not available — '
                    'proceeding with local stop only (no plugin-side freeze). '
                    'This is OK in sim, but on hardware indicates a missing '
                    'or crashed hexapod_hardware plugin.'
                )
                self._safety_freeze_logged_unreachable = True
            return
        # call_async returns a Future we deliberately ignore — the
        # plugin will process the Trigger request on its own executor.
        self._safety_freeze_client.call_async(Trigger.Request())

    # ===== Block B1 — Hinsetz-/Abschalt-Services + Fail-safe ============== #

    def _sitdown_durations(self) -> tuple[float, float]:
        """(lower_duration, flatten_duration) aus sitdown_duration + fraction."""
        lower = self._sitdown_duration * self._sitdown_lower_fraction
        flatten = self._sitdown_duration * (1.0 - self._sitdown_lower_fraction)
        return lower, flatten

    def _start_sitdown_sequence(self) -> bool:
        """
        Hinsetz-Sequenz in der Engine starten (nur sinnvoll aus STANDING).

        Phase 1 nutzt reposition_cycle_time (Engine-intern), Phase 2+3 die
        hier abgeleiteten lower/flatten-Dauern. Returns Erfolg.
        """
        now = time.monotonic()
        t = now - self._t_start
        lower_dur, flatten_dur = self._sitdown_durations()
        # SAT-Ruhe-Pose = Boot-/Spawn-Pose (Beine hoch). Falls noch nie eine
        # vollständige Pose empfangen wurde → None (Engine-Fallback rad 0).
        rest = self._spawn_joints if self._spawn_joints else None
        try:
            return self._engine.start_sitdown(
                t, lower_dur, flatten_dur, self._body_height_start,
                rest_joints=rest,
            )
        except (ValueError, IKError) as exc:
            self.get_logger().error(f'sit-down failed to start: {exc}')
            return False

    def _on_sit_down(self, request, response):
        """``/hexapod_sit_down`` (Rest): nur STANDING → Hinsetzen, bleibt SAT."""
        if self._engine.state != GaitEngine.STATE_STANDING:
            response.success = False
            response.message = (
                f'sit_down only from STANDING, state={self._engine.state}'
            )
            return response
        self._relay_off_after_sat = False  # Rest: bestromt bleiben
        ok = self._start_sitdown_sequence()
        response.success = ok
        response.message = (
            'sitting down (Rest, powered)' if ok else 'sit_down failed to start'
        )
        if ok:
            self.get_logger().info('sit_down: STANDING → Hinsetzen (Rest)')
        return response

    def _on_stand_up(self, request, response):
        """``/hexapod_stand_up``: nur SAT (nicht latched) → Aufstehen → STANDING."""
        if self._shutdown_latched:
            response.success = False
            response.message = (
                'shutdown latched — enable relay / reboot before stand_up'
            )
            return response
        if self._engine.state != GaitEngine.STATE_SAT:
            response.success = False
            response.message = (
                f'stand_up only from SAT, state={self._engine.state}'
            )
            return response
        if len(self._latest_joints) != len(HEXAPOD.legs):
            response.success = False
            response.message = 'no complete /joint_states received yet'
            return response
        now = time.monotonic()
        t = now - self._t_start
        try:
            if self._standup_mode == 'cartesian':
                self._engine.start_cartesian_standup(
                    self._latest_joints, t, self._auto_standup_duration,
                    self._standup_phase1_fraction, self._body_height_start,
                )
            else:
                self._engine.start_ramp(
                    self._latest_joints, t, self._auto_standup_duration,
                )
        except (ValueError, IKError) as exc:
            response.success = False
            response.message = f'stand_up failed: {exc}'
            self.get_logger().error(response.message)
            return response
        response.success = True
        response.message = 'standing up from SAT'
        self.get_logger().info(
            f'stand_up: SAT → Aufstehen ({self._standup_mode})'
        )
        return response

    def _on_shutdown(self, request, response):
        """``/hexapod_shutdown`` (terminal): hinsetzen (falls nötig) + Relay-Aus."""
        state = self._engine.state
        if state == GaitEngine.STATE_SAT:
            # Sitzt schon → sofort Relay-Aus + latchen.
            self._do_relay_off_and_latch()
            response.success = True
            response.message = 'already SAT — relay off (shutdown, terminal)'
            return response
        if state == GaitEngine.STATE_STANDING:
            self._relay_off_after_sat = True  # _tick feuert Relay-Aus bei SAT
            ok = self._start_sitdown_sequence()
            if not ok:
                self._relay_off_after_sat = False
            response.success = ok
            response.message = (
                'sitting down then relay off (shutdown, terminal)'
                if ok else 'shutdown failed to start sit-down'
            )
            if ok:
                self.get_logger().info(
                    'shutdown: STANDING → Hinsetzen, dann Relay-Aus bei SAT'
                )
            return response
        response.success = False
        response.message = (
            f'shutdown only from STANDING or SAT, state={state}'
        )
        return response

    def _do_relay_off_and_latch(self) -> None:
        """Relay öffnen (Servos stromlos) + terminalen Shutdown-Latch setzen."""
        self._fire_relay(False)
        self._shutdown_latched = True
        self._relay_off_after_sat = False
        self.get_logger().info(
            'Shutdown terminal: relay off, stand_up gesperrt bis Relay-On/Reboot'
        )

    def _fire_relay(self, on: bool) -> None:
        """
        ``/hexapod_relay_set`` (SetBool) async feuern (fire-and-forget).

        Service nicht verfügbar (Sim ohne hexapod_hardware-Plugin) → einmal
        WARN + skip. In Sim gibt es kein Relay; das Hinsetzen selbst ist der
        sichere Endzustand.
        """
        if not self._relay_set_client.service_is_ready():
            if not self._relay_logged_unreachable:
                self.get_logger().warn(
                    '/hexapod_relay_set service not available — skipping relay '
                    'control. OK in sim; on hardware indicates a missing or '
                    'crashed hexapod_hardware plugin.'
                )
                self._relay_logged_unreachable = True
            return
        req = SetBool.Request()
        req.data = on
        self._relay_set_client.call_async(req)

    def _check_comms_loss(self, now: float) -> None:
        """
        Comms-Loss-Fail-safe (opt-in): bei verstummtem /cmd_vel auto-Hinsetzen.

        Nur aktiv wenn ``comms_loss_sitdown_timeout > 0`` UND schon mal ein
        /cmd_vel ankam (sonst kein false-fire in Sim/manuell). Triggert nur aus
        STANDING — aus WALKING bringt der reguläre ``cmd_vel_timeout`` den
        Roboter erst über STOPPING → STANDING (er ist üblicherweise ≪ dem
        comms-loss-Timeout). Sobald die Sequenz läuft (state != STANDING),
        blockt der State-Guard ein Re-Trigger. Endzustand: SAT (Rest, bestromt
        — NICHT Shutdown, damit Reconnect wieder aufstehen kann).
        """
        timeout = self._comms_loss_sitdown_timeout
        if timeout <= 0.0 or self._last_cmd_time is None:
            return
        if (now - self._last_cmd_time) < timeout:
            return
        if self._engine.state != GaitEngine.STATE_STANDING:
            return
        self.get_logger().warn(
            f'comms-loss: no /cmd_vel for {now - self._last_cmd_time:.1f} s '
            f'(> {timeout:.1f} s) — auto sit-down (Rest)',
            throttle_duration_sec=5.0,
        )
        self._relay_off_after_sat = False
        self._start_sitdown_sequence()

    def _on_param_change(self, params) -> SetParametersResult:
        """
        Live-Update-Callback für alle gait-Parameter.

        Phase 11 Stage A — atomic-all-or-nothing-Validation:

        1. **Pre-Validation** (kein State-Change):
           - ``use_sim_time`` read-only ablehnen
           - STANDING-only-Params (siehe ``_STANDING_ONLY_PARAMS``) nur
             akzeptieren wenn Engine in STATE_STANDING
           - Cross-Constraint ``body_height_min < body_height_max``
           - Cross-Constraint ``body_height ∈ [min, max]``
           - ``gait_pattern`` ∈ GAIT_PRESETS
        2. **Apply** (ab hier kein Fail mehr möglich):
           Pro Param interne Member + ggf. Engine-Attribute updaten;
           ``tick_rate`` triggert ``_restart_timer``; ``gait_pattern``
           triggert ``_load_gait_pattern``.

        Bei einem einzigen Validation-Fail wird KEIN Update durchgeführt
        — rqt_reconfigure zeigt den ``reason``-String als Fehler.
        """
        # === 1. PRE-VALIDATION ===

        # 1a. use_sim_time bleibt read-only nach Init
        # (Clock-Mode-Wechsel zur Laufzeit ist in rclpy nicht zuverlässig).
        for p in params:
            if p.name == 'use_sim_time':
                return SetParametersResult(
                    successful=False,
                    reason='use_sim_time is read-only after init',
                )

        # 1b. Build proposed new state für Cross-Constraint-Checks
        proposed = {
            'body_height': self._body_height,
            'body_height_min': self._body_height_min,
            'body_height_max': self._body_height_max,
            'cycle_time': self._cycle_time,
            'tick_rate': self._tick_rate,
            'radial_distance': self._radial_distance,
            'gait_pattern': self._pattern.name,
        }
        for p in params:
            if p.name in proposed:
                proposed[p.name] = p.value

        # 1c. STANDING-only-Check
        if self._engine.state != GaitEngine.STATE_STANDING:
            rejected = []
            for p in params:
                if p.name not in _STANDING_ONLY_PARAMS:
                    continue
                current = (
                    self._pattern.name
                    if p.name == 'gait_pattern'
                    else getattr(self, f'_{p.name}', None)
                )
                if p.value != current:
                    rejected.append(p.name)
            if rejected:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'params {rejected} require STATE_STANDING, '
                        f'current state={self._engine.state}'
                    ),
                )

        # 1d. Cross-Constraint body_height_min < body_height_max
        if proposed['body_height_min'] >= proposed['body_height_max']:
            return SetParametersResult(
                successful=False,
                reason=(
                    f'body_height_min={proposed["body_height_min"]:.4f} '
                    f'must be < body_height_max='
                    f'{proposed["body_height_max"]:.4f}'
                ),
            )

        # 1e. Cross-Constraint body_height ∈ [min, max]
        if not (
            proposed['body_height_min']
            <= proposed['body_height']
            <= proposed['body_height_max']
        ):
            return SetParametersResult(
                successful=False,
                reason=(
                    f'body_height={proposed["body_height"]:.4f} outside '
                    f'[{proposed["body_height_min"]:.4f}, '
                    f'{proposed["body_height_max"]:.4f}]'
                ),
            )

        # 1f. gait_pattern ∈ GAIT_PRESETS
        for p in params:
            if p.name == 'gait_pattern' and p.value not in GAIT_PRESETS:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'unknown gait_pattern {p.value!r}, '
                        f'available: {sorted(GAIT_PRESETS.keys())}'
                    ),
                )

        # 1g. standup_mode ∈ {cartesian, joint_space} (Stage 0.7)
        for p in params:
            if p.name == 'standup_mode' and p.value not in (
                'cartesian', 'joint_space',
            ):
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'unknown standup_mode {p.value!r}, '
                        f'valid: cartesian | joint_space'
                    ),
                )

        # === 2. APPLY (kein Fail mehr möglich) ===
        for p in params:
            self._apply_param(p.name, p.value)

        # User-Feedback: bei rqt_reconfigure-Slider-Drag oder
        # `ros2 param set` sieht User sonst keinen Beleg dass der
        # Update angekommen ist (z.B. gait_pattern-Wechsel in STANDING
        # ist still bis cmd_vel kommt).
        changes = ', '.join(f'{p.name}={p.value}' for p in params)
        self.get_logger().info(f'param updated: {changes}')

        return SetParametersResult(successful=True)

    def _apply_param(self, name: str, value) -> None:
        """
        Einen Param aufs Node- und Engine-State anwenden.

        Vorausgesetzt ``_on_param_change`` hat vorher validiert. Hier
        passieren nur Attribut-Sets + Helper-Aufrufe — kein Validation,
        kein Fail.
        """
        if name == 'body_height':
            self._body_height = value
            self._engine.body_height = value
        elif name == 'body_height_min':
            self._body_height_min = value
        elif name == 'body_height_max':
            self._body_height_max = value
        elif name == 'cycle_time':
            self._cycle_time = value
            self._engine.cycle_time = value
        elif name == 'tick_rate':
            self._tick_rate = value
            self._tfs_seconds = self._tfs_factor / self._tick_rate
            self._restart_timer()
        elif name == 'radial_distance':
            self._radial_distance = value
            self._engine.radial_distance = value
        elif name == 'standup_radial_distance':
            self._standup_radial_distance = value
            self._engine.standup_radial_distance = value
        elif name == 'reposition_cycle_time':
            self._reposition_cycle_time = value
            self._engine.reposition_cycle_time = value
        elif name == 'step_height':
            self._step_height = value
            self._engine.step_height = value
        elif name == 'step_length_max':
            self._step_length_max = value
            self._engine.step_length_max = value
        elif name == 'time_from_start_factor':
            self._tfs_factor = value
            self._tfs_seconds = self._tfs_factor / self._tick_rate
        elif name == 'default_linear_x':
            self._default_linear_x = value
        elif name == 'default_linear_y':
            self._default_linear_y = value
        elif name == 'default_angular_z':
            self._default_angular_z = value
        elif name == 'cmd_vel_timeout':
            self._cmd_vel_timeout = value
        elif name == 'auto_standup_duration':
            self._auto_standup_duration = value
        elif name == 'standup_mode':
            self._standup_mode = value
        elif name == 'standup_phase1_fraction':
            self._standup_phase1_fraction = value
        elif name == 'body_height_start':
            self._body_height_start = value
        elif name == 'sitdown_duration':
            self._sitdown_duration = value
        elif name == 'sitdown_lower_fraction':
            self._sitdown_lower_fraction = value
        elif name == 'comms_loss_sitdown_timeout':
            self._comms_loss_sitdown_timeout = value
        elif name == 'gait_pattern':
            self._load_gait_pattern(value)

    def _restart_timer(self) -> None:
        """
        Timer mit aktueller ``_tick_rate`` neu erstellen.

        Cancel + destroy alten Timer, dann neuen mit selber CallbackGroup
        erzeugen. Sicher unter ``MutuallyExclusiveCallbackGroup`` —
        kein ``_tick`` kann zwischen cancel und create_timer feuern.
        """
        self._timer.cancel()
        self.destroy_timer(self._timer)
        self._timer = self.create_timer(
            1.0 / self._tick_rate,
            self._tick,
            callback_group=self._cb_group,
        )

    def _load_gait_pattern(self, name: str) -> None:
        """
        Pattern aus GAIT_PRESETS in Node + Engine umladen.

        Pattern-Existenz wird im ``_on_param_change`` Pre-Validation
        geprüft — hier wird vorausgesetzt dass ``name`` valide ist.
        Engine-Properties ``stance_duration``/``linear_max`` rechnen
        nach dem Pattern-Wechsel automatisch neu (A.2a-Refactor).
        """
        self._pattern = GAIT_PRESETS[name]
        self._engine.pattern = self._pattern

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
