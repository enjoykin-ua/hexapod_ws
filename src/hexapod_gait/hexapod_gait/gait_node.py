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

from collections import namedtuple
from dataclasses import dataclass
import math
import time
import xml.etree.ElementTree as ET

from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Twist
from hexapod_gait.balance_controller import BalanceController
from hexapod_gait.contact_diagnostic import ContactDiagnostic
from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_patterns import GAIT_PRESETS
from hexapod_gait.sensor_health_monitor import SensorHealthMonitor
from hexapod_gait.slope_estimator import SlopeEstimator
from hexapod_gait.support_monitor import SupportMonitor
from hexapod_gait.tip_monitor import (
    quat_to_roll_pitch,
    TIP_CRIT,
    TIP_NONE,
    TIP_WARN,
    TipMonitor,
)
from hexapod_kinematics import HEXAPOD, IKError, JointLimits, leg_fk
from rcl_interfaces.msg import (
    FloatingPointRange,
    ParameterDescriptor,
    ParameterType,
    SetParametersResult,
)
import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    qos_profile_sensor_data,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import Imu, JointState
from std_msgs.msg import Bool, Float64, Float64MultiArray
from std_srvs.srv import SetBool, Trigger
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


# Block A5 Stufe 2/3a — States, in denen das Body-Leveling im Node aktiv ist:
# STANDING (Stufe 2) + WALKING/STOPPING (Leveling im Lauf, Stufe 3a).
_LEVELING_NODE_STATES = (
    GaitEngine.STATE_STANDING,
    GaitEngine.STATE_WALKING,
    GaitEngine.STATE_STOPPING,
)

# Block A5 Stufe 7 — per-Achse Leveling-Gains (BalanceController v2). Jede Zeile
# wird als Param ``leveling_<suffix>_{roll,pitch}`` deklariert. is_deg=True →
# Param ist in Grad/Grad-pro-s und wird für den Controller nach rad umgerechnet.
# (suffix, set_axis_gains-kwarg, is_deg, default)
_LEVELING_AXIS_SPECS = (
    ('kp', 'kp', False, 0.4),
    ('ki', 'ki', False, 0.1),
    ('kd', 'kd', False, 0.03),
    ('deadband_inner_deg', 'inner', True, 1.5),
    ('deadband_outer_deg', 'outer', True, 1.5),
    ('slew_max_dps', 'slew_max', True, 8.0),
    ('tau_fast_s', 'tau_fast', False, 0.0),
    ('tau_slow_s', 'tau_slow', False, 0.0),
)


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
            'valid values: tripod | wave | tetrapod | ripple | '
            'single_leg_1 .. single_leg_6'
        ),
        description=(
            'Gait-Pattern-Name aus GAIT_PRESETS. '
            'Live-Wechsel nur in STANDING-State (Engine-Reset-Risiko).'
        ),
    ),
    _ParamSpec(
        name='step_height', default=0.040,
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
        fp_range=(-0.110, -0.020, 0.001),
        description=(
            'Stand-Pose Foot-Z im Bein-Frame (m). Default -0.080 = Stance-Modus '
            '"mittel" (Standup-/Boot-Basis). leg_changes: Walk-Radius 0.160 '
            'einheitlich; Aufstehen/Hinsetzen via breitem standup_radial 0.20 + '
            'Reposition (schürffrei). fp_range-Floor -0.110 für den Modus "hoch". '
            'Live-Update nur in STANDING (analog cmd_body_height).'
        ),
    ),
    _ParamSpec(
        name='radial_distance', default=0.160, standing_only=True,
        fp_range=(0.10, 0.21, 0.001),
        description=(
            'Radialer Foot-Neutral-Abstand vom Coxa-Mount im Bein-Frame (m). '
            'leg_changes: Default 0.160 = WALK-Pose (alle Stance-Höhen). Das '
            'Aufstehen läuft am breiteren standup_radial_distance (0.21, schürffrei) '
            'und repositioniert dann hierher. Walking envelope-grün '
            '(tools/walking_envelope_check). Live-Update nur in STANDING.'
        ),
    ),
    _ParamSpec(
        name='standup_radial_distance', default=0.200, standing_only=True,
        fp_range=(0.10, 0.22, 0.001),
        description=(
            'Radialer Foot-Abstand für die AUFSTEH-Pose (m). leg_changes/S6: '
            'Default 0.200 — nah an der power_on_mid-Fuß-Pose (~0.217) → Touchdown '
            'nahezu SENKRECHT (kaum Horizontalbewegung → schürffrei), statt am engen '
            'Walk-Radius 0.160 an der Femur-(−90°)-Wand einwärts zu schleifen. '
            'Begrenzt durch die Reichweite bei der tiefsten Höhe (hoch −0.100): '
            '(0.20,−0.100) d=0.186 < 0.194; 0.21 wäre dort out-of-reach. Nach dem '
            'Aufstehen Tripod-Reposition (Beine gehoben → schürffrei) auf 0.160. '
            'standup == radial → keine Reposition. Live nur in STANDING.'
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
        name='step_length_max', default=0.050,
        fp_range=(0.01, 0.15, 0.001),
        description=(
            'Max Stride pro Cycle (m). Begrenzt linear_max = '
            'step_length_max / stance_duration. leg_changes: Default 0.050 '
            '(max-leg-speed 0.05 m/s @ cycle 2.0) — envelope-grün bis ~0.08 '
            '@ radial 0.160, mit Marge gewählt. Live-Update wirkt sofort.'
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
        name='body_height_min', default=-0.110, standing_only=True,
        fp_range=(-0.140, -0.020, 0.001),
        description=(
            'Untere Schranke body_height (m). Cross-Constraint: '
            'min < body_height < max. leg_changes: -0.110 (Floor für Modus '
            '"hoch" -0.100). STANDING-only.'
        ),
    ),
    _ParamSpec(
        name='body_height_max', default=-0.060, standing_only=True,
        fp_range=(-0.120, -0.020, 0.001),
        description=(
            'Obere Schranke body_height (m). Cross-Constraint: '
            'min < body_height < max. leg_changes: -0.060 (Decke über Modus '
            '"tief" -0.065). STANDING-only.'
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
    _ParamSpec(
        name='step_length_intent_step', default=0.010,
        fp_range=(0.001, 0.02, 0.001),
        description=(
            'Block C2: Schrittgröße pro /hexapod_adjust_step_length-Intent (m). '
            'Controller-Schrittweiten-Trim (D-Pad ↑/↓). Stage 1: 0.01 (war 0.005).'
        ),
    ),
    _ParamSpec(
        name='step_length_intent_min', default=0.030,
        fp_range=(0.01, 0.15, 0.001),
        description=(
            'Block C2: untere Clamp-Grenze für den Schrittweiten-Trim (m). '
            'leg_changes: 0.030 (Default-Start 0.050, D-Pad-↓ bis 0.030).'
        ),
    ),
    _ParamSpec(
        name='step_length_intent_max', default=0.070,
        fp_range=(0.01, 0.15, 0.001),
        description=(
            'Block C2: obere Clamp-Grenze für den Schrittweiten-Trim (m). '
            'leg_changes: 0.070 — envelope-grün @ radial 0.160 (bis ~0.08, mit '
            'Marge zur Femur-Wand). D-Pad-↑ bis hierher.'
        ),
    ),
    # Phase 13 Stage 1 — Stance-Modus-Wechsel.
    _ParamSpec(
        name='stance_switch_duration', default=2.0,
        fp_range=(0.5, 6.0, 0.1),
        description=(
            'Stage 1: Dauer des Stance-Modus-Wechsels (Tripod-Reposition + '
            'body_height-Lerp) in s. Min ~1 s gegen Schnapp-Bewegung.'
        ),
    ),
    _ParamSpec(
        name='stance_switch_step_height', default=0.025,
        fp_range=(0.010, 0.060, 0.005),
        description=(
            'Stage 1: Fuß-Hub während des Stance-Wechsels (m). Klein, damit der '
            'Swing-Apex bei keiner Zwischenhöhe die Femur-±90°-Wand trifft.'
        ),
    ),
    # Block B4 — Show-Pose (Free-Leg). Nicht STANDING-only: werden beim
    # Show-Toggle gelesen (wie die B1-Sitdown-Params), nicht mid-State mutiert.
    _ParamSpec(
        name='show_enter_duration', default=4.0,
        fp_range=(1.0, 15.0, 0.1),
        description=(
            'Block B4: Dauer der SHOW_ENTER-Bewegung (Körper zurück + '
            'Vorderbeine hoch) in s. Langsam = CoG-schonend.'
        ),
    ),
    _ParamSpec(
        name='show_exit_duration', default=3.0,
        fp_range=(1.0, 15.0, 0.1),
        description=(
            'Block B4: Dauer der SHOW_EXIT-Bewegung (Vorderbeine runter + '
            'Körper vor) zurück nach STANDING in s.'
        ),
    ),
    _ParamSpec(
        name='show_body_shift_back', default=0.065,
        fp_range=(0.0, 0.10, 0.001),
        description=(
            'Block B4: Körper-Rückversatz für die Show-Stütz-Pose (m). '
            'B4.0: ≥0.05 halten (Worst-Case-Offset-CoG-Marge ≥30 mm); '
            'Obergrenze ~0.09 (Stütz-Coxa-Limit ±0.415). Default 0.065 '
            '(~50 mm Marge).'
        ),
    ),
    _ParamSpec(
        name='show_shift_fraction', default=0.5,
        fp_range=(0.1, 0.9, 0.05),
        description=(
            'Block B4: Anteil von show_enter_duration auf Phase a '
            '(Körper-Rückversatz, alle 6 Füße am Boden), Rest = Phase b '
            '(Vorderbeine heben). Default 0.5.'
        ),
    ),
    _ParamSpec(
        name='show_safety_margin', default=0.030,
        fp_range=(0.0, 0.10, 0.001),
        description=(
            'Block B4: Mindest-CoG-Marge im 4-Bein-Polygon während '
            'SHOW_ENTER Phase b (m). Unterschreitung → Hold (Freeze) der '
            'letzten sicheren Pose. Default 0.030.'
        ),
    ),
    _ParamSpec(
        name='show_front_radial', default=0.22,
        fp_range=(0.12, 0.28, 0.001),
        description=(
            'Block B4: radialer Foot-Abstand der neutralen Vorderbein-'
            'Hoch-Pose (m). Höher heben braucht größeres radial '
            '(Femur-Limit ±1.57). Default 0.22 (~80 mm über Boden).'
        ),
    ),
    _ParamSpec(
        name='show_front_z', default=-0.04,
        fp_range=(-0.12, 0.04, 0.001),
        description=(
            'Block B4: Foot-z der neutralen Vorderbein-Hoch-Pose im '
            'Bein-Frame (m). Boden liegt bei body_height. Default -0.04.'
        ),
    ),
    _ParamSpec(
        name='show_return_rate', default=0.5,
        fp_range=(0.05, 2.0, 0.05),
        description=(
            'Block B4: max. Nachführ-/Rückkehr-Rate der Vorderbein-Offsets '
            '(m/s) in SHOW_ACTIVE. Gegen ruckartige Servo-Bewegung beim '
            'Loslassen (R1) / Stick-Zentrieren. Default 0.5.'
        ),
    ),
    _ParamSpec(
        name='show_lat_scale', default=0.06,
        fp_range=(0.0, 0.12, 0.005),
        description=(
            'Block B4: Skala Stick-X [-1..1] → seitlicher Vorderbein-Offset '
            '(m) in SHOW_ACTIVE. Konservativ (Coxa-Limit clampt eh). '
            'Default 0.06.'
        ),
    ),
    _ParamSpec(
        name='show_vert_scale', default=0.06,
        fp_range=(0.0, 0.12, 0.005),
        description=(
            'Block B4: Skala Stick-Y [-1..1] → vertikaler Vorderbein-Offset '
            '(m, hoch/runter) in SHOW_ACTIVE. Default 0.06.'
        ),
    ),
    _ParamSpec(
        name='show_radial_scale', default=0.05,
        fp_range=(0.0, 0.08, 0.005),
        description=(
            'Block B4.11: Skala Trigger [0..1] → radialer Vorderbein-Offset '
            '(m, reach/Tibia-Curl) in SHOW_ACTIVE. Trigger drücken = Bein '
            'streckt sich raus (Tibia fährt auf). Offline-CoG-safe bis 0.06 '
            '(~43 mm Marge); Default 0.05. Negativ-Reach (einrollen) ist von '
            'der Neutral-Pose femur-limit-blockiert → einseitig raus.'
        ),
    ),
)

# Block C2 — Gangart-Cycle-Reihenfolge fürs Controller-Umschalten
# (/hexapod_cycle_gait). single_leg_* bleiben Debug-only (nicht im Cycle).
_GAIT_CYCLE_ORDER = ('tripod', 'wave', 'tetrapod', 'ripple')

# Stance-Modi (radial, body_height, step_height), offline envelope-validiert
# (tools/walking_envelope_check.py + standup_envelope_check.py). Reihenfolge
# aufsteigende Körperhöhe: Index 0 = tief (geduckt), 2 = hoch. /hexapod_cycle_stance
# data=True → höher (Index+1), False → tiefer (Index-1), geklemmt (kein Wrap).
# "mittel" (Index 1) ist die Standup-/Boot-Basis.
_StanceMode = namedtuple('_StanceMode', 'name radial body_height step_height')
# leg_changes (S5/S6, kürzere Beine, reach 0.074..0.194): einheitlicher WALK-
# Radius 0.160 für alle Höhen. Das Aufstehen/Hinsetzen läuft NICHT an 0.160 (dort
# reiten die Vorderbeine an der Femur-(-90°)-Wand → Schleifen), sondern am breiten
# standup_radial 0.20 (≈ power_on_mid, schürffreier Touchdown) → danach Tripod-
# Reposition auf 0.160 (S6-HW-Finding, [[project_standup_vertical_touchdown_infeasible]]).
# (0.20 statt 0.21: bei der tiefsten Höhe hoch −0.100 wäre 0.21 out-of-reach.)
# Kein Routing über mittel nötig (alle Höhen > _SIT_SAFE_MIN_BH). Walking grün @ 0.160,
# Standup grün @ 0.20 zu allen drei body_height. Envelope am Femur-Rand optimistisch →
# echte Engine/Sim/HW validieren (test_stance_switch + B.4/B.5 + S6).
_STANCE_MODES = (
    _StanceMode('tief', 0.160, -0.065, 0.040),
    _StanceMode('mittel', 0.160, -0.080, 0.040),
    _StanceMode('hoch', 0.160, -0.100, 0.040),
)
_STANCE_DEFAULT_IDX = 1   # mittel
# Tiefste body_height, aus der direkt hingesetzt werden kann. leg_changes: alle
# Modi (tiefste "hoch" -0.100) liegen über -0.115 → jede Höhe direkt sit-/standup-
# fähig, kein Routing nötig. ⚠️ real-engine (test_sitdown) gegenchecken.
_SIT_SAFE_MIN_BH = -0.115

# Phase 13 Stage A — Timeout-Warning fuer fehlende /joint_states.
# Wenn nach diesem Zeitraum kein /joint_states empfangen wurde, wird
# einmalig ein ERROR-Log gefeuert (typische Ursache: joint_state_
# broadcaster nicht gestartet / gecrasht).
_JOINT_STATES_TIMEOUT_S = 10.0

# Block A5 S4-2 — Contact-Live-Guard: maximale Staleness der Fußkontakt-Pipeline.
# Der foot_contact_publisher publisht 50 Hz; > 0.5 s ohne Message (= 25 verpasste
# Ticks) gilt als toter/abwesender Publisher → adaptiver Touchdown wird ausgesetzt.
_FOOT_CONTACT_STALE_S = 0.5


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
        # Block C2 — Schrittweiten-Trim-Intent (Controller).
        self._step_length_intent_step = float(
            self.get_parameter('step_length_intent_step').value
        )
        self._step_length_intent_min = float(
            self.get_parameter('step_length_intent_min').value
        )
        self._step_length_intent_max = float(
            self.get_parameter('step_length_intent_max').value
        )
        # Block B4 — Show-Pose-Parameter.
        self._show_enter_duration = float(
            self.get_parameter('show_enter_duration').value
        )
        self._show_exit_duration = float(
            self.get_parameter('show_exit_duration').value
        )
        self._show_body_shift_back = float(
            self.get_parameter('show_body_shift_back').value
        )
        self._show_shift_fraction = float(
            self.get_parameter('show_shift_fraction').value
        )
        self._show_safety_margin = float(
            self.get_parameter('show_safety_margin').value
        )
        self._show_front_radial = float(
            self.get_parameter('show_front_radial').value
        )
        self._show_front_z = float(
            self.get_parameter('show_front_z').value
        )
        self._show_return_rate = float(
            self.get_parameter('show_return_rate').value
        )
        self._show_lat_scale = float(
            self.get_parameter('show_lat_scale').value
        )
        self._show_vert_scale = float(
            self.get_parameter('show_vert_scale').value
        )
        self._show_radial_scale = float(
            self.get_parameter('show_radial_scale').value
        )
        # Phase 13 Stage 1 — Stance-Modus-Wechsel.
        self._stance_switch_duration = float(
            self.get_parameter('stance_switch_duration').value
        )
        self._stance_switch_step_height = float(
            self.get_parameter('stance_switch_step_height').value
        )
        # Aktiver Modus-Index (Boot = mittel). Cyclen via /hexapod_cycle_stance.
        self._stance_idx = _STANCE_DEFAULT_IDX
        # Hinsetzen aus "hoch" (-0.140) routet erst auf mittel: Flag = Hinsetzen
        # nachholen, sobald der Stance-Switch fertig ist (STANDING).
        self._pending_sitdown = False

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

        # Block F3 — latched "shutdown sequence complete" flag for the
        # supervisor (Block F4): goes True the moment sit-down + relay-off
        # finished (_do_relay_off_and_latch). Latched (transient_local +
        # reliable, depth 1) so a late/restarting supervisor gets the current
        # value; same QoS contract as /hexapod/shutdown_request (F2).
        self._shutdown_complete_pub = self.create_publisher(
            Bool, '/hexapod/shutdown_complete',
            QoSProfile(
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE))
        self._publish_shutdown_complete(False)

        self._cmd_vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self._on_cmd_vel, 10
        )

        self._cmd_body_height_sub = self.create_subscription(
            Float64, '/cmd_body_height', self._on_cmd_body_height, 10
        )

        # Block B4 — /cmd_show: 4 Stick-Werte für die Vorderbeine in SHOW_ACTIVE.
        self._cmd_show_sub = self.create_subscription(
            Float64MultiArray, '/cmd_show', self._on_cmd_show, 10
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

        # Block A5 Stufe 1 — Kipp-/Sturz-Erkennung. /imu/data mit Sensor-QoS
        # (best_effort) abonnieren; Schwellen-Logik in der ROS-freien
        # TipMonitor-Klasse. Params in Grad / Grad-pro-s (menschenlesbar) -> rad.
        # Deklaration VOR add_on_set_parameters_callback -> loest _on_param_change
        # nicht aus (Live-Set tunet hier nicht; Relaunch zum Aendern, Feintuning
        # auf der Rampe in Stufe 2).
        self.declare_parameter('tip_detection_enable', True)
        # Stufe 7 (E5): Kipp-Schwellen per Achse (roll kippt seitlich früher als
        # pitch beim länglichen Roboter). Rate/Debounce achsen-übergreifend.
        self.declare_parameter('tip_angle_warn_deg_roll', 15.0)
        self.declare_parameter('tip_angle_warn_deg_pitch', 15.0)
        self.declare_parameter('tip_angle_crit_deg_roll', 25.0)
        self.declare_parameter('tip_angle_crit_deg_pitch', 25.0)
        self.declare_parameter('tip_rate_crit_dps', 80.0)
        self.declare_parameter('tip_debounce_ticks', 5)
        # Tip-Params als Member halten → Live-Rebuild des Monitors über
        # _on_param_change (Feintuning auf der Schräge, §4-Entscheidung).
        self._tip_detection_enable = bool(
            self.get_parameter('tip_detection_enable').value
        )
        self._tip_angle_warn_deg_roll = float(
            self.get_parameter('tip_angle_warn_deg_roll').value
        )
        self._tip_angle_warn_deg_pitch = float(
            self.get_parameter('tip_angle_warn_deg_pitch').value
        )
        self._tip_angle_crit_deg_roll = float(
            self.get_parameter('tip_angle_crit_deg_roll').value
        )
        self._tip_angle_crit_deg_pitch = float(
            self.get_parameter('tip_angle_crit_deg_pitch').value
        )
        self._tip_rate_crit_dps = float(
            self.get_parameter('tip_rate_crit_dps').value
        )
        self._tip_debounce_ticks = int(
            self.get_parameter('tip_debounce_ticks').value
        )
        self._tip_monitor = self._build_tip_monitor()
        self._imu_roll: float | None = None
        self._imu_pitch = 0.0
        self._imu_tilt_rate = 0.0
        self._imu_gyro_roll = 0.0  # TF-2: signierte Achsen-Drehraten (rad/s)
        self._imu_gyro_pitch = 0.0
        self._tip_crit_fired = False
        self._imu_sub = self.create_subscription(
            Imu, '/imu/data', self._on_imu, qos_profile_sensor_data,
        )

        # Block A5 Stufe 2 — statisches Körper-Leveling. BalanceController
        # (ROS-frei) konsumiert die IMU-roll/pitch und liefert pro Tick eine
        # Körper-Rotations-Korrektur, die die Engine im STANDING-Pfad auf die
        # Fuß-Targets dreht (set_body_orientation_offset). Params menschenlesbar
        # in Grad / Grad-pro-s → rad. Default leveling_enable=False (Opt-in;
        # auf flachem Boden ohnehin No-Op, da Korrektur → 0). Alle Params live
        # tunbar (§4-Entscheidung) — siehe _apply_param.
        self.declare_parameter('leveling_enable', False)
        self.declare_parameter('leveling_mode', 'terrain')
        # Stufe 7 (E4): per-Achse-Gains (kp/ki/kd/inner/outer/slew/tau je roll,
        # pitch). Default roll==pitch, inner==outer, tau==0 → exakt Stufe-2-
        # Verhalten (E9). Der Name→(axis,kwarg,is_deg)-Lookup treibt _on_param_change.
        self._leveling_axis_param_map: dict[str, tuple[str, str, bool]] = {}
        for suffix, kwarg, is_deg, default in _LEVELING_AXIS_SPECS:
            for axis in ('roll', 'pitch'):
                pname = f'leveling_{suffix}_{axis}'
                self.declare_parameter(pname, default)
                self._leveling_axis_param_map[pname] = (axis, kwarg, is_deg)
        self.declare_parameter('leveling_max_angle_deg', 10.0)
        self.declare_parameter('leveling_max_angle_walking_deg', 4.0)
        self.declare_parameter('leveling_startup_grace', True)
        self._leveling_enable = bool(
            self.get_parameter('leveling_enable').value
        )
        # TF-2: Modus 'terrain' (roll→0, pitch folgt Hang via Residual + Gyro-D)
        # vs. 'horizontal' (Stufe 2/3a Voll-Leveln auf 0/0). HW8.7b: 'auto' =
        # state-abhängig (STANDING→horizontal, WALKING/STOPPING→terrain) —
        # Auflösung pro Tick in _update_leveling. Code-Default bleibt 'terrain'
        # (kein Sim-Regress); 'auto' ist der HW-Arbeitswert (hw_terrain.yaml).
        self._leveling_mode = str(self.get_parameter('leveling_mode').value)
        self._leveling_startup_grace = bool(
            self.get_parameter('leveling_startup_grace').value
        )
        self._leveling_max_angle_deg = float(
            self.get_parameter('leveling_max_angle_deg').value
        )
        self._leveling_max_angle_walking_deg = float(
            self.get_parameter('leveling_max_angle_walking_deg').value
        )
        # BalanceController v2: Back-Compat-Konstruktor (symmetrisch aus roll-
        # Defaults), dann per-Achse-Gains (inner/outer/tau + pitch) einspielen.
        self._balance = BalanceController(
            kp=float(self.get_parameter('leveling_kp_roll').value),
            ki=float(self.get_parameter('leveling_ki_roll').value),
            kd=float(self.get_parameter('leveling_kd_roll').value),
            deadband=math.radians(float(
                self.get_parameter('leveling_deadband_inner_deg_roll').value
            )),
            slew_max=math.radians(float(
                self.get_parameter('leveling_slew_max_dps_roll').value
            )),
            max_level_angle=math.radians(self._leveling_max_angle_deg),
        )
        self._apply_leveling_axis_params()
        self._engine.max_level_angle = math.radians(self._leveling_max_angle_deg)
        self._engine.max_level_angle_walking = math.radians(
            self._leveling_max_angle_walking_deg
        )
        self._last_leveling_t: float | None = None

        # Block A5 TF-1 — passiv Terrain-Following + slope-bewusster Tip.
        # Ein langsamer Tiefpass auf die IMU-Neigung schätzt den Untergrund
        # (der Körper folgt ihm bei passivem TF von allein); der TipMonitor
        # bekommt das Residual (Ist − Hang) statt der rohen Neigung → er feuert
        # relativ zum Hang, nicht absolut (kein Fehlalarm auf gewollter Hang-
        # Neigung). Kein neuer Stellpfad — aktive Stabilisierung ist TF-2.
        # Params live tunbar (§4); Clamp ±40° deckt die Charakterisierung bis
        # 35° ab, ohne dass die Schätzung künstlich sättigt.
        self.declare_parameter('slope_aware_tip_enable', True)
        self.declare_parameter('slope_estimate_tau_s', 0.5)
        self.declare_parameter('slope_clamp_deg', 40.0)
        self._slope_aware_tip_enable = bool(
            self.get_parameter('slope_aware_tip_enable').value
        )
        self._slope_estimate_tau_s = float(
            self.get_parameter('slope_estimate_tau_s').value
        )
        self._slope_clamp_deg = float(
            self.get_parameter('slope_clamp_deg').value
        )
        self._slope_est = SlopeEstimator(
            self._slope_estimate_tau_s,
            math.radians(self._slope_clamp_deg),
        )
        self._last_slope_t: float | None = None
        self._slope_pub = self.create_publisher(
            Float64MultiArray, '/imu/slope', 10,
        )

        # Block A5 Stufe 4 / S4-1 — Fußkontakt-Consumer + Verifikation.
        # 6 Subscriber auf /leg_<n>/foot_contact (Bool, vom foot_contact_publisher,
        # läuft per Default in der Sim). KEIN Verhaltens-Change — nur cachen +
        # quantitativ messen (ContactDiagnostic), de-risk vor S4-2 (adaptiver
        # Touchdown). Graceful ohne Pipeline (kein Topic → alle False).
        self.declare_parameter('foot_contact_debug_enable', True)
        self._foot_contact_debug_enable = bool(
            self.get_parameter('foot_contact_debug_enable').value
        )
        self._foot_contact = {leg_id: False for leg_id in range(1, 7)}
        self._contact_diag = ContactDiagnostic(tuple(range(1, 7)))
        self._foot_contact_subs = {
            leg_id: self.create_subscription(
                Bool, f'/leg_{leg_id}/foot_contact',
                self._make_foot_contact_cb(leg_id), 10,
            )
            for leg_id in range(1, 7)
        }
        self._foot_contacts_pub = self.create_publisher(
            Float64MultiArray, '/foot_contacts', 10,
        )
        self._last_contact_log_t = time.monotonic()
        # S4-1 Mess-Zusatz (a): tatsächliche Sim-Gelenkstellung → FK-Fuß-z von
        # Bein 1, um bei jeder Kontakt-Flanke kommandiert vs. tatsächlich zu
        # vergleichen (klärt den ~13-Tick-Offset). Nutzt das bestehende
        # `_latest_joints` (vom vorhandenen /joint_states-Sub gepflegt).
        self._leg1 = next(
            leg for leg in HEXAPOD.legs if leg.name == 'leg_1'
        )
        self._dbg_prev_contact1 = False

        # Block A5 Stufe 4 / S4-2 — adaptiver Touchdown (kontrollierte Senk-Rate).
        # Opt-in (Default false, wie leveling_enable). Params live tunbar; werden
        # auf die Engine gespiegelt. adaptive_touchdown_enable wird pro Tick mit
        # dem Contact-Live-Guard verUNDet (toter Publisher → adaptiv aus →
        # nominaler swing_traj-Fallback, kein Durchsacken).
        self.declare_parameter('adaptive_touchdown_enable', False)
        self.declare_parameter('touchdown_probe_start_stance_phase', 0.35)
        self.declare_parameter('touchdown_search_end_stance_phase', 0.6)
        self.declare_parameter('touchdown_max_extra_depth', 0.02)
        self._adaptive_touchdown_enable = bool(
            self.get_parameter('adaptive_touchdown_enable').value
        )
        self._engine.touchdown_probe_start_stance_phase = float(
            self.get_parameter('touchdown_probe_start_stance_phase').value
        )
        self._engine.touchdown_search_end_stance_phase = float(
            self.get_parameter('touchdown_search_end_stance_phase').value
        )
        self._engine.touchdown_max_extra_depth = float(
            self.get_parameter('touchdown_max_extra_depth').value
        )
        # Contact-Live-Guard: der foot_contact_publisher publisht 50 Hz dauernd
        # (true/false). Frische = "je empfangen UND letzte Msg < N s her".
        # Stille (toter/abwesender Publisher) → Pipeline tot → adaptiv aus.
        self._foot_contact_received = False
        self._last_foot_contact_msg_t = 0.0

        # Block A5 Stufe 4 / S4-7 — terrain-anpassendes Stehen (Adaptive Stand).
        # Statischer Zwilling von S4-2: im STANDING senkt jedes Bein bis Kontakt
        # ab (auf unebenem Grund aufsetzen statt in der Luft hängen). Opt-in
        # (Default false); nutzt dieselbe Fußkontakt-Pipeline + denselben
        # Contact-Live-Guard wie S4-2. Params live tunbar; Tiefe/Rate direkt auf
        # die Engine gespiegelt, enable pro Tick mit dem Live-Guard verUNDet.
        self.declare_parameter('adaptive_stand_enable', False)
        self.declare_parameter('stand_conform_max_depth', 0.04)
        self.declare_parameter('stand_conform_rate', 0.02)
        self._adaptive_stand_enable = bool(
            self.get_parameter('adaptive_stand_enable').value
        )
        self._engine.stand_conform_max_depth = float(
            self.get_parameter('stand_conform_max_depth').value
        )
        self._engine.stand_conform_rate = float(
            self.get_parameter('stand_conform_rate').value
        )

        # Block A5 Stufe 4 / S4-4 — Slip/Kontaktverlust → Freeze (Safe-State).
        # Opt-in (Default false). Ein Stance-Fuß ohne Kontakt nach der Grace
        # (Kante/Abgrund: Boden tiefer als cliff_depth; oder Slip) → SupportMonitor
        # → Freeze (wie Stufe-1-Tip-CRIT). cliff_depth = Grenze folgbares Terrain
        # ↔ Abgrund: wird (wenn armiert) als adaptiver Probe-Floor auf die Engine
        # gespiegelt. Nur in WALKING ausgewertet.
        self.declare_parameter('slip_detection_enable', False)
        self.declare_parameter('cliff_depth', 0.03)
        self.declare_parameter('slip_debounce_ticks', 8)
        self.declare_parameter('slip_min_lost_legs', 1)
        self.declare_parameter('slip_grace_stance_phase', 0.6)
        self._slip_detection_enable = bool(
            self.get_parameter('slip_detection_enable').value
        )
        self._cliff_depth = float(self.get_parameter('cliff_depth').value)
        self._slip_debounce_ticks = int(
            self.get_parameter('slip_debounce_ticks').value
        )
        self._slip_min_lost_legs = int(
            self.get_parameter('slip_min_lost_legs').value
        )
        self._slip_grace_stance_phase = float(
            self.get_parameter('slip_grace_stance_phase').value
        )
        self._support_monitor = SupportMonitor(
            debounce_ticks=self._slip_debounce_ticks,
            min_lost_legs=self._slip_min_lost_legs,
            grace_stance_phase=self._slip_grace_stance_phase,
        )
        self._slip_freeze_fired = False
        # S4-5/S4-4-Glue: pro WALKING-Episode merken, ob ein Bein **je** Kontakt
        # hatte. Ein Bein, das nie Kontakt hatte (toter/stuck-off-Sensor von
        # Anfang an), gab nie Stütze → es kann sie nicht „verlieren" → aus der
        # Slip-Freeze-Zählung ausschließen (sonst Fehl-Freeze BEVOR die dead-
        # Erkennung über 2 Cycles maskieren kann — Sim-Befund T2). Ein echter
        # Slip/Kante (Bein HATTE Kontakt, verliert ihn) bleibt ein Freeze.
        self._ever_contacted = {leg_id: False for leg_id in range(1, 7)}
        self._engine.cliff_probe_depth = (
            self._cliff_depth if self._slip_detection_enable else 0.0
        )

        # Block A5 Stufe 4 / S4-5 — Plausibilität + Sensor-Fault-Fail-Safe.
        # Opt-in (Default false). Ein defekter Fußkontakt-Sensor (stuck-on =
        # klemmt „Kontakt" / dead = klemmt „kein Kontakt") darf S4-2/S4-4 nicht
        # korrumpieren. Plausibilitäts-Anker = Gait-Phase (Apex = Fuß oben →
        # Kontakt unmöglich; kein Touchdown über N Cycles = tot). Reaktion:
        # geflaggtes Bein latched MASKIEREN (adaptiv-aus + aus Slip-Zählung) +
        # throttled WARN — kein Freeze (Taster = Optimierung, nie load-bearing).
        # `sensor_dead_cycles` ist cycle_time-UNABHÄNGIG (Cycles); der Node
        # rechnet via cycle_time·tick_rate in Ticks um (→ Rebuild).
        self.declare_parameter('sensor_plausibility_enable', False)
        self.declare_parameter('sensor_apex_band_low', 0.3)
        self.declare_parameter('sensor_apex_band_high', 0.7)
        self.declare_parameter('sensor_apex_fault_cycles', 3)
        self.declare_parameter('sensor_dead_cycles', 2)
        # Sim-Test-Hook (Default aus, klar Debug): zwingt den gecachten Kontakt
        # EINES Beins auf einen Klemm-Wert, um die Erkennung in der fault-freien
        # Sim zu provozieren. Format '<leg>:stuck_on' | '<leg>:stuck_off';
        # '' / 'none' = aus.
        self.declare_parameter('sensor_fault_inject', '')
        self._sensor_plausibility_enable = bool(
            self.get_parameter('sensor_plausibility_enable').value
        )
        self._sensor_apex_band_low = float(
            self.get_parameter('sensor_apex_band_low').value
        )
        self._sensor_apex_band_high = float(
            self.get_parameter('sensor_apex_band_high').value
        )
        self._sensor_apex_fault_cycles = int(
            self.get_parameter('sensor_apex_fault_cycles').value
        )
        self._sensor_dead_cycles = int(
            self.get_parameter('sensor_dead_cycles').value
        )
        self._sensor_fault_inject = self._parse_sensor_fault_inject(
            self.get_parameter('sensor_fault_inject').value
        )
        # Set der aktuell maskierten Beine (latched bis State-Wechsel/Reset).
        self._sensor_faulty: set[int] = set()
        self._sensor_health_monitor = None
        self._rebuild_sensor_health_monitor()

        # Wall-clock-Start (time.monotonic) statt Sim-Zeit, damit der
        # Loop nicht an /clock-DDS-Discovery-Race scheitert.
        self._t_start = time.monotonic()
        self._last_cmd_time: float | None = None
        self._last_cmd_v_x = 0.0
        self._last_cmd_v_y = 0.0
        self._last_cmd_omega_z = 0.0

        # Block B4/B4.11 — /cmd_show-State: zuletzt empfangene 6 Achsen-Werte
        # [leg6_lat, leg6_vert, leg6_radial, leg1_lat, leg1_vert, leg1_radial]
        # in [-1, 1] (Teleop hat Dead-Man R1 bereits angewandt → 0 wenn
        # losgelassen). Staleness (> cmd_vel_timeout ohne /cmd_show) → als 0
        # behandelt (Disconnect-Schutz: Vorderbeine kehren in Neutral zurück).
        self._cmd_show = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._last_cmd_show_time: float | None = None

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
        # Block C1+ — ein Intent-Service für den Teleop: „Sitz/Steh-Wechsel".
        # Der Teleop kennt den State NICHT (reines UI); hier wird nach State
        # aufgelöst (STANDING→sit, SAT→stand). Delegiert an die B1-Handler.
        self._sit_stand_toggle_srv = self.create_service(
            Trigger, '/hexapod_sit_stand_toggle', self._on_sit_stand_toggle,
            callback_group=self._cb_group,
        )
        # Block C2 — Teleop-Intents: Gangart cyclen + Schrittweite trimmen.
        # SetBool: data=True → nächste Gangart / Schritt größer; False → prev /
        # kleiner. Logik/Clamp/STANDING-Schutz hier (Teleop bleibt UI).
        self._cycle_gait_srv = self.create_service(
            SetBool, '/hexapod_cycle_gait', self._on_cycle_gait,
            callback_group=self._cb_group,
        )
        self._adjust_step_length_srv = self.create_service(
            SetBool, '/hexapod_adjust_step_length', self._on_adjust_step_length,
            callback_group=self._cb_group,
        )
        # Block B4 — Show-Pose-Toggle (Teleop-Intent, reines UI). Nach State
        # aufgelöst: STANDING → SHOW_ENTER, SHOW_* → SHOW_EXIT zurück STANDING.
        self._show_toggle_srv = self.create_service(
            Trigger, '/hexapod_show_toggle', self._on_show_toggle,
            callback_group=self._cb_group,
        )
        # Phase 13 Stage 1 — Stance-Modus cyclen (SetBool: true=höher, false=
        # tiefer; nur STANDING). Teleop: L2/R2 ohne R1.
        self._cycle_stance_srv = self.create_service(
            SetBool, '/hexapod_cycle_stance', self._on_cycle_stance,
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

    def _on_imu(self, msg: Imu) -> None:
        """IMU-Empfang: roll/pitch + Kipprate (Stufe 1) + Gyro-Achsen (TF-2)."""
        q = msg.orientation
        self._imu_roll, self._imu_pitch = quat_to_roll_pitch(
            q.x, q.y, q.z, q.w
        )
        # Stufe 1: Kipprate (Betrag) für den TipMonitor.
        self._imu_tilt_rate = math.hypot(
            msg.angular_velocity.x, msg.angular_velocity.y
        )
        # TF-2: signierte Achsen-Drehraten für den Gyro-D-Term (rad/s).
        self._imu_gyro_roll = msg.angular_velocity.x
        self._imu_gyro_pitch = msg.angular_velocity.y

    def _make_foot_contact_cb(self, leg_id: int):
        """
        Closure pro Bein (S4-1): cacht den Bool-Kontakt-State.

        S4-2: stempelt zusätzlich den Empfangs-Zeitpunkt (egal welcher Wert) für
        den Contact-Live-Guard — der Publisher publisht 50 Hz dauernd, Stille =
        toter Publisher.
        """
        def _cb(msg: Bool) -> None:
            self._foot_contact[leg_id] = bool(msg.data)
            self._foot_contact_received = True
            self._last_foot_contact_msg_t = time.monotonic()
        return _cb

    def _on_cmd_show(self, msg: Float64MultiArray) -> None:
        """
        ``/cmd_show``-Empfang (Block B4): 4 Stick-Werte cachen + Timestamp.

        Erwartet ``[leg6_lat, leg6_vert, leg6_radial, leg1_lat, leg1_vert,
        leg1_radial]`` in [-1, 1] (Teleop hat Skala-Normierung + Dead-Man R1
        angewandt). Kürzere/leere Arrays werden ignoriert (malformed → kein
        State-Change). Die Skalierung + das Setzen an die Engine passiert im
        Tick (nur in SHOW_ACTIVE), damit es synchron zum Rate-Limit läuft.
        """
        if len(msg.data) >= 6:
            self._cmd_show = [float(v) for v in msg.data[:6]]
            self._last_cmd_show_time = time.monotonic()

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

        # Stage 1 — verzögertes Hinsetzen: wenn aus "hoch" geroutet wurde, ist
        # der Stance-Switch auf mittel jetzt fertig (STANDING) → Hinsetzen jetzt.
        if self._pending_sitdown and (
            self._engine.state == GaitEngine.STATE_STANDING
        ):
            self._pending_sitdown = False
            self._start_sitdown_sequence()

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

        # Block A5 TF-1 — Hang-Schätzung VOR der Tip-Auswertung aktualisieren
        # (der slope-bewusste Tip nutzt das Residual gegen diese Schätzung).
        self._update_slope_estimate()

        # Block A5 Stufe 1 — Kipp-/Sturz-Erkennung (nur STANDING/WALKING).
        # WARN: Befehl auf 0 → Roboter stoppt/settelt. CRIT (Winkel/Rate):
        # Safety-Freeze (einmalig, gelatcht) + diesen Tick nicht publishen.
        tip = self._update_tip()
        if tip == TIP_CRIT:
            if not self._tip_crit_fired:
                self.get_logger().error(
                    'Kipp-CRIT erkannt (Winkel/Rate über Limit) — Safety-Freeze'
                )
                self._trigger_safety_freeze()
                self._tip_crit_fired = True
            return
        if tip == TIP_WARN:
            v_x, v_y, omega_z = 0.0, 0.0, 0.0
            self.get_logger().warn(
                'Kipp-WARN erkannt — stoppe (cmd_vel=0)',
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

        # Block B4 — in SHOW_ACTIVE die Joystick-Offsets der Vorderbeine
        # setzen (vor compute, damit das Rate-Limit diesen Tick greift).
        if self._engine.state == GaitEngine.STATE_SHOW_ACTIVE:
            self._update_show_offsets(now)

        # Block A5 Stufe 2 — Body-Leveling-Korrektur setzen (nur STANDING).
        self._update_leveling()

        # Block A5 S4-5 — Sim-Fault-Inject (Debug): EINEN gecachten Kontakt auf
        # Klemm-Wert zwingen, BEVOR irgendwas ihn liest (Erkennung provozieren).
        self._apply_sensor_fault_inject()

        # Block A5 S4-5 — Sensor-Plausibilität: defekte Sensoren flaggen +
        # maskieren (Set self._sensor_faulty) + warnen. VOR foot_contacts/support,
        # damit die Maskierung auf S4-2 (adaptiv) und S4-4 (Slip) durchschlägt.
        self._update_sensor_health(t)

        # Block A5 S4-1 — Fußkontakt cachen + Diagnose (kein Verhaltens-Change).
        self._update_foot_contacts(t)

        # Block A5 S4-4 — Slip/Kontaktverlust (Kante/Abgrund) → Freeze (nur WALKING).
        if self._update_support(t):
            return  # Stütz-Verlust → Safety-Freeze, diesen Tick nicht publishen

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

    def _update_leveling(self) -> None:
        """
        Block A5 Stufe 2/3a/TF-2 — Body-Stabilisierungs-Korrektur pro Tick setzen.

        In STANDING (Stufe 2) **und** WALKING/STOPPING (Stufe 3a) + Leveling aktiv +
        IMU vorhanden: ``BalanceController.update`` → ``engine.set_body_orientation_offset``.
        Sonst (Aufstehen/Show/Stance-Switch/SAT): Controller-``reset`` + Offset 0/0
        (dort kippt der Körper gewollt). ``dt`` aus ``time.monotonic`` (erster Tick
        dt=0 → Controller hält 0, Slew-Step 0).

        **TF-2 Modus-abhängige Reglereingänge** (Sollwert intern 0):
        - ``terrain``: roll = roh (→ roll auf 0), pitch = **Residual** (IMU − Hang-
          Schätzung → pitch folgt dem Hang, nur Wackeln wird korrigiert).
        - ``horizontal`` (Stufe 2/3a): roll = roh, pitch = roh (Voll-Leveln auf 0/0).
        Beide Modi bekommen den **Gyro-D-Term** (signierte Achsen-Drehraten).
        """
        if (
            not self._leveling_enable
            or self._imu_roll is None
            or self._engine.state not in _LEVELING_NODE_STATES
        ):
            self._balance.reset()
            self._engine.set_body_orientation_offset(0.0, 0.0)
            self._last_leveling_t = None
            return
        now = time.monotonic()
        dt = (
            0.0 if self._last_leveling_t is None
            else now - self._last_leveling_t
        )
        self._last_leveling_t = now
        # Stufe 3a — Self-Review-Fix: den state-abhängigen Clamp AUCH am Controller
        # setzen (STANDING 10° / WALKING/STOPPING 4°), damit dessen Slew-Limit den
        # Übergang glättet. Sonst springt der reine Engine-Clamp beim State-Wechsel
        # (z.B. Anhalten am Hang: 4°→10° in einem Tick) → Körper-Ruck. Die
        # Engine-Clamps bleiben als Backstop.
        state_max = (
            self._engine.max_level_angle
            if self._engine.state == GaitEngine.STATE_STANDING
            else self._engine.max_level_angle_walking
        )
        self._balance.set_gains(max_level_angle=state_max)
        # HW8.7b: 'auto' löst den effektiven Modus pro Tick aus dem Engine-State
        # auf — STANDING = horizontal (voll ausleveln: eine Gang-End-Schräge auf
        # ebenem Boden sähe der Slope-Schätzer als „Hang" und ließe sie stehen),
        # WALKING **und STOPPING** = terrain (STOPPING gehört zum Lauf-Block,
        # sonst zieht das Anhalten am Hang den Körper ruckartig waagerecht).
        # Kein Controller-Reset am Übergang: der Slew-Limiter glättet den
        # Eingangs-Sprung Residual↔roh (derselbe Mechanismus wie der
        # 3a-Clamp-Fix oben).
        mode = self._leveling_mode
        if mode == 'auto':
            mode = (
                'horizontal'
                if self._engine.state == GaitEngine.STATE_STANDING
                else 'terrain'
            )
        # TF-2: pitch im terrain-Modus gegen die Hang-Schätzung (Residual), roll
        # roh (→0). Der SlopeEstimator (TF-1) wurde diesen Tick bereits in
        # _update_slope_estimate aktualisiert (läuft vor _update_leveling).
        roll_in = self._imu_roll
        if mode == 'terrain':
            pitch_in = self._imu_pitch - self._slope_est.slope_pitch
        else:  # 'horizontal'
            pitch_in = self._imu_pitch
        # Stufe 7 (A): Filter-Flag pro Achse — roll ist immer roh (→0), pitch nur
        # im horizontal-Modus roh; im terrain-Modus ist pitch_in ein Residual
        # (Slope-Schätzer = langsame Stufe → KEIN zweiter Filter im Regler).
        # Folgt dem EFFEKTIVEN Modus (im 'auto'-STANDING also horizontal=roh).
        corr = self._balance.update(
            roll_in, pitch_in, dt,
            self._imu_gyro_roll, self._imu_gyro_pitch,
            filter_roll=True,
            filter_pitch=(mode != 'terrain'),
        )
        self._engine.set_body_orientation_offset(*corr)

    def _build_tip_monitor(self) -> TipMonitor:
        """Baue den TipMonitor aus den per-Achse Tip-Param-Membern (Stufe 7 E5)."""
        return TipMonitor(
            math.radians(self._tip_angle_warn_deg_roll),
            math.radians(self._tip_angle_crit_deg_roll),
            math.radians(self._tip_rate_crit_dps),
            self._tip_debounce_ticks,
            angle_warn_pitch=math.radians(self._tip_angle_warn_deg_pitch),
            angle_crit_pitch=math.radians(self._tip_angle_crit_deg_pitch),
        )

    def _rebuild_tip_monitor(self) -> None:
        """Baue den TipMonitor neu (Live-Tuning der Tip-Schwellen)."""
        self._tip_monitor = self._build_tip_monitor()
        self._tip_crit_fired = False

    def _apply_leveling_axis_params(self) -> None:
        """Alle per-Achse-Leveling-Gains aus den Params in den Controller schreiben."""
        for axis in ('roll', 'pitch'):
            kwargs = {}
            for suffix, kwarg, is_deg, _default in _LEVELING_AXIS_SPECS:
                val = float(
                    self.get_parameter(f'leveling_{suffix}_{axis}').value
                )
                kwargs[kwarg] = math.radians(val) if is_deg else val
            self._balance.set_axis_gains(axis, **kwargs)

    def _update_slope_estimate(self) -> None:
        """
        Block A5 TF-1 — Hang-Schätzung (langsamer Tiefpass auf die IMU-Neigung).

        Aktiv in STANDING/WALKING/STOPPING (deckungsgleich mit dem Stell-Pfad
        ``_LEVELING_NODE_STATES``, damit die TF-2-pitch-Regelung auch im STOPPING
        das Residual gegen den echten Hang bildet) — in Transition-States
        (Aufstehen/Hinsetzen/Reposition/Show/Stance-Switch) kippt der Körper
        *gewollt*, das ist nicht der Untergrund → Schätzung reset (Snap-Init beim
        Wiedereintritt verhindert einen künstlichen Residual-Sprung). Ohne IMU →
        reset, nicht publizieren.

        Publiziert die Schätzung in Grad auf ``/imu/slope`` (Sim-Verifikation:
        „trackt die Schätzung den echten Hang?", Grundlage für TF-2).
        """
        if self._imu_roll is None:
            self._slope_est.reset()
            self._last_slope_t = None
            return
        if self._engine.state not in _LEVELING_NODE_STATES:
            self._slope_est.reset()
            self._last_slope_t = None
        else:
            now = time.monotonic()
            dt = (
                0.0 if self._last_slope_t is None
                else now - self._last_slope_t
            )
            self._last_slope_t = now
            self._slope_est.update(self._imu_roll, self._imu_pitch, dt)

        msg = Float64MultiArray()
        msg.data = [
            math.degrees(self._slope_est.slope_roll),
            math.degrees(self._slope_est.slope_pitch),
        ]
        self._slope_pub.publish(msg)

    def _update_foot_contacts(self, t: float) -> None:
        """
        Block A5 S4-1 — Fußkontakt cachen → Diagnose → publishen/loggen.

        **KEIN Verhaltens-Change.** Speist die ``ContactDiagnostic`` mit
        ``(contact, is_swing, local_phase, is_walking)`` pro Bein (Phase read-only
        aus ``engine.leg_gait_states``). Publisht ``/foot_contacts`` (6× 0/1) und
        loggt throttled (1 Hz) die Diagnose-Zusammenfassung. Die quantitative
        Verifikation für den adaptiven Touchdown (S4-2).
        """
        states = self._engine.leg_gait_states(t)
        is_walking = self._engine.state == GaitEngine.STATE_WALKING
        for leg_id in range(1, 7):
            is_swing, local_phase = states.get(leg_id, (False, 0.0))
            self._contact_diag.update(
                leg_id, self._foot_contact[leg_id], is_swing, local_phase,
                is_walking,
            )

        # S4-2 — Kontakte an die Engine durchreichen + adaptiven Touchdown nur
        # scharf schalten, wenn (a) der Param es will UND (b) die Pipeline lebt
        # (Contact-Live-Guard). Pipeline tot/abwesend → adaptiv aus → die Engine
        # fällt auf den nominalen swing_traj zurück (kein Durchsacken). VOR
        # compute_joint_angles (dieser Tick nutzt frische Kontakte/Phase).
        pipeline_live = (
            self._foot_contact_received
            and (time.monotonic() - self._last_foot_contact_msg_t)
            < _FOOT_CONTACT_STALE_S
        )
        self._engine.set_foot_contacts(self._foot_contact)
        self._engine.adaptive_touchdown_enable = (
            self._adaptive_touchdown_enable and pipeline_live
        )
        # S4-7 — adaptives Stehen mit demselben Live-Guard: Param AND Pipeline
        # lebt. Toter/stale Publisher → aus → starre Stand-Pose (kein Absacken).
        self._engine.adaptive_stand_enable = (
            self._adaptive_stand_enable and pipeline_live
        )
        # S4-5 — geflaggte Beine vom adaptiven Touchdown ausnehmen (Open-Loop;
        # ihr Kontakt ist nicht vertrauenswürdig). Leeres Set = Normalfall.
        self._engine.set_adaptive_masked_legs(self._sensor_faulty)

        msg = Float64MultiArray()
        msg.data = [1.0 if self._foot_contact[i] else 0.0 for i in range(1, 7)]
        self._foot_contacts_pub.publish(msg)

        if self._foot_contact_debug_enable:
            self._debug_leg1_contact(t)
            now = time.monotonic()
            if now - self._last_contact_log_t >= 1.0:
                self._last_contact_log_t = now
                self._log_contact_diag()

    def _update_support(self, t: float) -> bool:
        """
        Block A5 S4-4 — Stütz-Verlust (Slip/Kante) erkennen → Freeze.

        Returns ``True`` wenn gefreezt wird (Caller publisht diesen Tick nicht).
        Nur in WALKING ausgewertet (Vortrieb über Kanten); sonst Monitor-Reset.
        Freeze ist gelatcht + einmalig (steigende Flanke), wie Tip-CRIT. Recovery
        über State-Wechsel (cmd_vel=0 → STOPPING → reset).
        """
        if not self._slip_detection_enable:
            return False
        if self._engine.state != GaitEngine.STATE_WALKING:
            self._support_monitor.reset()
            self._slip_freeze_fired = False
            self._ever_contacted = {leg_id: False for leg_id in range(1, 7)}
            return False
        states = self._engine.leg_gait_states(t)
        legs = {}
        for leg_id in range(1, 7):
            is_swing, local_phase = states.get(leg_id, (False, 0.0))
            if self._foot_contact[leg_id]:
                self._ever_contacted[leg_id] = True
            # Aus der Stütz-Verlust-Zählung ausschließen (als „nicht Stance"
            # durchreichen → SupportMonitor-Lost-Zähler bleibt 0). Beides nur bei
            # aktivem S4-5 (pures S4-4 behält sein verifiziertes Freeze-Verhalten):
            #  - als defekt geflaggtes Bein (Kontakt nicht vertrauenswürdig);
            #  - T2-Fix: Bein, das diese Episode NIE Kontakt hatte (toter Sensor
            #    von Anfang an) — es gab nie Stütze, also kein „Verlust"; sonst
            #    Fehl-Freeze BEVOR die dead-Erkennung (2 Cycles) maskieren kann.
            excluded = leg_id in self._sensor_faulty or (
                self._sensor_plausibility_enable
                and not self._ever_contacted[leg_id]
            )
            is_stance = (not is_swing) and (not excluded)
            legs[leg_id] = (
                is_stance, local_phase, self._foot_contact[leg_id],
            )
        n_lost, freeze = self._support_monitor.update(legs)
        if freeze:
            if not self._slip_freeze_fired:
                self.get_logger().error(
                    f'Stütz-Verlust erkannt ({n_lost} Bein(e) ohne Halt — '
                    'Kante/Abgrund oder Slip) — Safety-Freeze'
                )
                self._trigger_safety_freeze()
                self._slip_freeze_fired = True
            return True
        return False

    def _rebuild_support_monitor(self) -> None:
        """Baue den SupportMonitor mit aktuellen Params neu (S4-4, live-Tuning)."""
        self._support_monitor = SupportMonitor(
            debounce_ticks=self._slip_debounce_ticks,
            min_lost_legs=self._slip_min_lost_legs,
            grace_stance_phase=self._slip_grace_stance_phase,
        )
        self._slip_freeze_fired = False

    @staticmethod
    def _parse_sensor_fault_inject(raw):
        """
        S4-5 — den Test-Hook-String parsen → ``(leg, value)`` oder ``None``.

        ``'<leg>:stuck_on'`` → ``(leg, True)`` (klemmt Kontakt), ``'<leg>:stuck_off'``
        → ``(leg, False)`` (klemmt kein-Kontakt). ``''`` / ``'none'`` (und alles
        Ungültige, das die Validierung nicht abfängt) → ``None`` (aus). ``leg`` ∈ 1..6.
        """
        s = str(raw).strip().lower()
        if not s or s == 'none':
            return None
        parts = s.split(':')
        if len(parts) != 2:
            return None
        leg_s, mode = parts
        try:
            leg = int(leg_s)
        except ValueError:
            return None
        if leg not in range(1, 7):
            return None
        if mode == 'stuck_on':
            return (leg, True)
        if mode == 'stuck_off':
            return (leg, False)
        return None

    def _apply_sensor_fault_inject(self) -> None:
        """
        S4-5 Test-Hook — den gecachten Kontakt EINES Beins auf Klemm-Wert zwingen.

        Läuft pro Tick **vor** allen Kontakt-Consumern (Health-Monitor, Engine,
        Support), damit der injizierte Fault end-to-end sichtbar ist. ``None`` =
        aus (Normalfall, kein Overhead). Der nächste Subscriber-Callback
        überschreibt den Cache wieder mit dem echten Wert → die Injection wird
        jeden Tick neu angewandt (deterministisch zum Tick-Zeitpunkt).
        """
        inj = self._sensor_fault_inject
        if inj is None:
            return
        leg, value = inj
        self._foot_contact[leg] = value

    def _update_sensor_health(self, t: float) -> None:
        """
        Block A5 S4-5 — Fußkontakt-Sensor-Plausibilität → flaggen + warnen.

        Speist den ``SensorHealthMonitor`` mit ``(is_swing, local_phase, contact)``
        pro Bein (Phase read-only aus ``engine.leg_gait_states``) und pflegt das
        Set ``self._sensor_faulty`` (latched bis State-Wechsel). Auf der steigenden
        Flanke eines neuen Faults: WARN mit Grund; solange Beine maskiert sind:
        throttled Reminder. **Keine Reaktion außer Maskierung** (Open-Loop +
        Slip-Ausschluss erledigen ``_update_foot_contacts`` / ``_update_support``).
        Nur in WALKING ausgewertet (sonst reset → Latch fällt beim Anhalten).
        """
        if not self._sensor_plausibility_enable:
            if self._sensor_faulty:
                self._sensor_faulty = set()
                self._sensor_health_monitor.reset()
            return
        # Bei aktivem Safety-Freeze (Slip oder Tip) ist der Roboter eingefroren:
        # der Engine-State bleibt WALKING und t läuft weiter, aber die Beine
        # bewegen sich nicht → die berechnete Phase cyclet über eingefrorene
        # Kontakte → Geister-Flags (Sim-Befund T2). Daher: nicht auswerten, reset.
        if self._slip_freeze_fired or self._tip_crit_fired:
            if self._sensor_faulty:
                self._sensor_faulty = set()
            self._sensor_health_monitor.reset()
            return
        if self._engine.state != GaitEngine.STATE_WALKING:
            if self._sensor_faulty:
                self._sensor_faulty = set()
            self._sensor_health_monitor.reset()
            return

        states = self._engine.leg_gait_states(t)
        legs = {}
        for leg_id in range(1, 7):
            is_swing, local_phase = states.get(leg_id, (False, 0.0))
            legs[leg_id] = (is_swing, local_phase, self._foot_contact[leg_id])
        result = self._sensor_health_monitor.update(legs)

        new_faulty = {lid for lid, (faulty, _) in result.items() if faulty}
        for leg_id in sorted(new_faulty - self._sensor_faulty):
            reason = result[leg_id][1]
            self.get_logger().warn(
                f'Sensor fault leg {leg_id} ({reason}) — ignoring contact '
                '(adaptive off + excluded from slip count)'
            )
        self._sensor_faulty = new_faulty
        if self._sensor_faulty:
            self.get_logger().warn(
                f'Foot-contact sensor(s) masked: {sorted(self._sensor_faulty)}',
                throttle_duration_sec=5.0,
            )

    def _rebuild_sensor_health_monitor(self) -> None:
        """
        Baue den SensorHealthMonitor mit aktuellen Params neu (S4-5, live-Tuning).

        ``dead_ticks`` wird hier aus ``sensor_dead_cycles · cycle_time ·
        tick_rate`` gerechnet (cycle_time-unabhängiger Param in Cycles) — daher
        auch Rebuild bei cycle_time/tick_rate-Änderung. Latch (``_sensor_faulty``)
        wird mit zurückgesetzt.
        """
        dead_ticks = max(1, int(round(
            self._sensor_dead_cycles * self._cycle_time * self._tick_rate
        )))
        self._sensor_health_monitor = SensorHealthMonitor(
            apex_lo=self._sensor_apex_band_low,
            apex_hi=self._sensor_apex_band_high,
            apex_fault_cycles=self._sensor_apex_fault_cycles,
            dead_ticks=dead_ticks,
        )
        self._sensor_faulty = set()

    def _debug_leg1_contact(self, t: float) -> None:
        """
        S4-1 Mess-Zusatz (a): kommandiert vs. tatsächlich bei Bein-1-Flanke.

        Loggt bei jeder Kontakt-Flanke von Bein 1 das **kommandierte** Fuß-z
        (Engine-Target) gegen das **tatsächliche** Fuß-z (FK aus /joint_states) —
        klärt, ob der Kontakt feuert, wenn der echte Sim-Fuß den Boden erreicht,
        und wie groß der Ausführungs-Lag ist.
        """
        c = self._foot_contact[1]
        if c == self._dbg_prev_contact1:
            return
        self._dbg_prev_contact1 = c

        cmd = self._engine.compute_foot_targets(t).get('leg_1')
        cmd_z = cmd[2] if cmd else float('nan')
        actual = self._latest_joints.get('leg_1')
        act_z = leg_fk(*actual, self._leg1)[2] if actual else float('nan')
        is_swing, ph = self._engine.leg_gait_states(t).get(1, (False, 0.0))
        phase_s = f'{"swing" if is_swing else "stance"}{ph:.2f}'
        self.get_logger().info(
            f'L1 contact {"RISE" if c else "FALL"} | '
            f'cmd_z={cmd_z:.4f} act_z={act_z:.4f} '
            f'dz={(act_z - cmd_z) * 1000:.1f}mm bh={self._engine.body_height:.4f} '
            f'phase={phase_s}'
        )

    def _log_contact_diag(self) -> None:
        """Throttled-Log der Kontakt-Diagnose-Zusammenfassung (S4-1)."""
        summ = self._contact_diag.summary()
        bits = ''.join(
            '1' if self._foot_contact[i] else '0' for i in range(1, 7)
        )
        parts = []
        for leg_id in range(1, 7):
            s = summ[leg_id]
            lat = s['latency_avg']
            lat_s = f'{lat:.1f}' if lat is not None else '-'
            parts.append(
                f'L{leg_id} td{s["touchdowns"]} lat{lat_s}/{s["latency_max"]} '
                f'miss{s["missed_touchdown"]} apex{s["apex_false"]} '
                f'gap{s["stance_gap"]}'
            )
        self.get_logger().info(
            f'foot_contact [{bits}] | ' + ' | '.join(parts)
        )

    def _update_tip(self) -> str:
        """
        Block A5 Stufe 1 — Kipp-Level aus der IMU (nur STANDING/WALKING).

        Gating: in allen anderen States (Aufstehen/Hinsetzen/Reposition/Show/
        Stance-Switch) kippt der Körper gewollt → TipMonitor reset + NONE.
        Ohne bisher empfangene IMU → NONE.

        Stufe 2 — Startup-Grace: während aktiver Leveling-Konvergenz (Controller
        noch nicht im Totband) Tip in STANDING unterdrücken, damit die Anfangs-
        Schräglage auf der Rampe nicht als Kippen feuert (WARN wäre dort eh nur
        cmd_vel=0). Greift nur bei aktivem Leveling + Grace-Flag.

        TF-1 — slope-bewusster Tip: bei ``slope_aware_tip_enable`` bekommt der
        Monitor das **Residual** (Ist-Neigung − Hang-Schätzung) statt der rohen
        Neigung → ein stetiger Hang fällt heraus (Residual ≈ 0), ein echter Kipp
        bleibt sichtbar (Filter lagt). Die **Kipprate bleibt roh** (Sturz-Drehrate
        ist hang-unabhängig → primärer Schnell-Fänger).
        """
        if not self._tip_detection_enable:
            return TIP_NONE
        if self._engine.state not in (
            GaitEngine.STATE_STANDING, GaitEngine.STATE_WALKING,
        ):
            self._tip_monitor.reset()
            self._tip_crit_fired = False
            return TIP_NONE
        if self._imu_roll is None:
            return TIP_NONE
        if (
            self._leveling_enable
            and self._leveling_startup_grace
            and self._engine.state == GaitEngine.STATE_STANDING
            and not self._balance.converged
        ):
            self._tip_monitor.reset()
            return TIP_NONE
        if self._slope_aware_tip_enable:
            roll_in, pitch_in = self._slope_est.residual(
                self._imu_roll, self._imu_pitch,
            )
        else:
            roll_in, pitch_in = self._imu_roll, self._imu_pitch
        return self._tip_monitor.update(
            roll_in, pitch_in, self._imu_tilt_rate,
        )

    # ===== Block B1 — Hinsetz-/Abschalt-Services + Fail-safe ============== #

    def _sitdown_durations(self) -> tuple[float, float]:
        """(lower_duration, flatten_duration) aus sitdown_duration + fraction."""
        lower = self._sitdown_duration * self._sitdown_lower_fraction
        flatten = self._sitdown_duration * (1.0 - self._sitdown_lower_fraction)
        return lower, flatten

    def _start_sitdown_sequence(self) -> bool:
        """
        Hinsetz-Sequenz in der Engine starten (nur sinnvoll aus STANDING).

        Stage 1: Ist die Pose tiefer als sit-safe (Modus "hoch", −0.140 — die
        Sit-Reposition auf standup_radial 0.295 wäre dort out-of-reach), wird
        ZUERST ein Stance-Switch auf mittel gefahren und das Hinsetzen via
        ``_pending_sitdown`` nachgeholt, sobald der Switch fertig ist (STANDING,
        im Tick). Sonst direkt. Phase 1 nutzt reposition_cycle_time, Phase 2+3
        die abgeleiteten lower/flatten-Dauern. Returns Erfolg.
        """
        if self._engine.body_height < _SIT_SAFE_MIN_BH:
            ok = self._do_stance_switch(_STANCE_DEFAULT_IDX)   # → mittel
            if ok:
                self._pending_sitdown = True
                self.get_logger().info(
                    'sit-down aus "hoch": erst Switch auf mittel, dann hinsetzen'
                )
            return ok
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

    def _on_sit_stand_toggle(self, request, response):
        """``/hexapod_sit_stand_toggle``: nach State auflösen (Teleop-Intent)."""
        state = self._engine.state
        if state == GaitEngine.STATE_STANDING:
            return self._on_sit_down(request, response)
        if state == GaitEngine.STATE_SAT:
            return self._on_stand_up(request, response)
        response.success = False
        response.message = (
            f'sit_stand_toggle: nichts zu tun in state={state} '
            '(braucht STANDING oder SAT)'
        )
        return response

    def _on_cycle_gait(self, request, response):
        """``/hexapod_cycle_gait`` (SetBool): nächste/vorige Gangart, nur STANDING."""
        if self._engine.state != GaitEngine.STATE_STANDING:
            response.success = False
            response.message = (
                f'cycle_gait nur in STANDING (state={self._engine.state})'
            )
            return response
        order = _GAIT_CYCLE_ORDER
        try:
            idx = order.index(self._pattern.name)
        except ValueError:
            idx = -1 if request.data else 0  # aktuelle nicht im Cycle → Rand
        step = 1 if request.data else -1
        nxt = order[(idx + step) % len(order)]
        self._load_gait_pattern(nxt)
        response.success = True
        response.message = f'gait_pattern -> {nxt}'
        self.get_logger().info(f'cycle_gait: {response.message}')
        return response

    def _on_adjust_step_length(self, request, response):
        """``/hexapod_adjust_step_length`` (SetBool): step_length_max ± clampt."""
        sign = 1.0 if request.data else -1.0
        new = self._step_length_max + sign * self._step_length_intent_step
        new = max(
            self._step_length_intent_min,
            min(self._step_length_intent_max, new),
        )
        self._step_length_max = new
        self._engine.step_length_max = new
        response.success = True
        response.message = (
            f'step_length_max -> {new:.3f} m '
            f'(linear_max={self._engine.linear_max:.3f} m/s)'
        )
        self.get_logger().info(f'adjust_step_length: {response.message}')
        return response

    # ===== Block B4 — Show-Pose-Toggle + Vorderbein-Offsets ============== #

    def _on_show_toggle(self, request, response):
        """
        ``/hexapod_show_toggle`` (Trigger, Teleop-Intent, reines UI).

        Nach State aufgelöst: STANDING → SHOW_ENTER (Show einnehmen);
        SHOW_ENTER/ACTIVE/EXIT → SHOW_EXIT (zurück STANDING, danach Laufen
        wieder möglich). In jedem anderen State (Aufstehen/Sitzen/Walking)
        abgelehnt — Show nur aus dem ruhigen Stand bzw. wieder heraus.
        """
        state = self._engine.state
        now = time.monotonic()
        t = now - self._t_start
        if state == GaitEngine.STATE_STANDING:
            try:
                ok = self._engine.start_show_enter(
                    t, self._show_enter_duration, self._show_body_shift_back,
                    self._show_shift_fraction, self._show_front_radial,
                    self._show_front_z, self._show_safety_margin,
                    self._show_return_rate,
                )
            except ValueError as exc:
                response.success = False
                response.message = f'show_enter failed: {exc}'
                self.get_logger().error(response.message)
                return response
            self._cmd_show = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            response.success = ok
            response.message = (
                'entering show pose' if ok else 'show_enter rejected'
            )
            if ok:
                self.get_logger().info('show_toggle: STANDING → SHOW_ENTER')
            return response
        if state in (
            GaitEngine.STATE_SHOW_ENTER,
            GaitEngine.STATE_SHOW_ACTIVE,
            GaitEngine.STATE_SHOW_EXIT,
        ):
            try:
                ok = self._engine.start_show_exit(t, self._show_exit_duration)
            except ValueError as exc:
                response.success = False
                response.message = f'show_exit failed: {exc}'
                self.get_logger().error(response.message)
                return response
            response.success = ok
            response.message = (
                'leaving show pose' if ok else 'show_exit rejected'
            )
            if ok:
                self.get_logger().info(
                    f'show_toggle: {state} → SHOW_EXIT → STANDING'
                )
            return response
        response.success = False
        response.message = (
            f'show_toggle: nichts zu tun in state={state} '
            '(braucht STANDING oder einen SHOW-State)'
        )
        return response

    def _update_show_offsets(self, now: float) -> None:
        """
        In SHOW_ACTIVE die Stick-Werte → Meter skalieren + an Engine geben.

        Staleness-Schutz: ohne frisches /cmd_show (> cmd_vel_timeout) werden
        die Offsets auf 0 gesetzt → die Vorderbeine kehren rate-limitiert in
        die Neutral-Pose zurück (Disconnect / Teleop-Crash). Mapping:
        ``[leg6_lat, leg6_vert, leg6_radial, leg1_lat, leg1_vert, leg1_radial]``.
        """
        fresh = (
            self._last_cmd_show_time is not None
            and (now - self._last_cmd_show_time) < self._cmd_vel_timeout
        )
        cs = self._cmd_show if fresh else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        self._engine.set_show_offsets({
            'leg_6': (cs[0] * self._show_lat_scale,
                      cs[1] * self._show_vert_scale,
                      cs[2] * self._show_radial_scale),
            'leg_1': (cs[3] * self._show_lat_scale,
                      cs[4] * self._show_vert_scale,
                      cs[5] * self._show_radial_scale),
        })

    def _on_cycle_stance(self, request, response):
        """
        ``/hexapod_cycle_stance`` (SetBool): Stance-Modus wechseln, nur STANDING.

        ``data=True`` → höher (Index+1 Richtung "hoch"), ``False`` → tiefer
        (Index-1 Richtung "tief"). Geklemmt an den Enden (kein Wrap, da die
        Höhen physisch begrenzt sind). Startet den Engine-Stance-Switch
        (Reposition + body_height-Lerp) zum Ziel-Modus.
        """
        if self._engine.state != GaitEngine.STATE_STANDING:
            response.success = False
            response.message = (
                f'cycle_stance nur in STANDING (state={self._engine.state})'
            )
            return response
        step = 1 if request.data else -1
        new_idx = max(0, min(len(_STANCE_MODES) - 1, self._stance_idx + step))
        if new_idx == self._stance_idx:
            response.success = True
            response.message = (
                f'stance bereits am {"höchsten" if step > 0 else "tiefsten"} '
                f'Modus ({_STANCE_MODES[self._stance_idx].name})'
            )
            return response
        ok = self._do_stance_switch(new_idx)
        mode = _STANCE_MODES[new_idx]
        response.success = ok
        response.message = (
            f'stance -> {mode.name} (bh={mode.body_height}, radial={mode.radial})'
            if ok else 'cycle_stance rejected'
        )
        if ok:
            self.get_logger().info(f'cycle_stance: {response.message}')
        return response

    def _do_stance_switch(self, new_idx: int) -> bool:
        """
        Engine-Stance-Switch zu ``_STANCE_MODES[new_idx]`` starten + Node-State.

        Nur sinnvoll aus STANDING (Engine prüft). Bei Erfolg: ``_stance_idx`` +
        Node-Member (radial/body_height/step_height) auf den Ziel-Modus.
        """
        mode = _STANCE_MODES[new_idx]
        now = time.monotonic()
        t = now - self._t_start
        try:
            ok = self._engine.start_stance_switch(
                t, mode.radial, mode.body_height, mode.step_height,
                self._stance_switch_duration, self._stance_switch_step_height,
            )
        except ValueError as exc:
            self.get_logger().error(f'stance switch failed: {exc}')
            return False
        if ok:
            self._stance_idx = new_idx
            self._radial_distance = mode.radial
            self._body_height = mode.body_height
            self._step_height = mode.step_height
        return ok

    def _do_relay_off_and_latch(self) -> None:
        """Relay öffnen (Servos stromlos) + terminalen Shutdown-Latch setzen."""
        self._fire_relay(False)
        self._shutdown_latched = True
        self._relay_off_after_sat = False
        # Block F3 — sit-down + relay-off are done: signal the supervisor (F4)
        # that the OS may now shut down (no magic wait, see F_systemsteuerung E5).
        self._publish_shutdown_complete(True)
        self.get_logger().info(
            'Shutdown terminal: relay off, stand_up gesperrt bis Relay-On/Reboot'
        )

    def _publish_shutdown_complete(self, done: bool) -> None:
        """Block F3 — latched /hexapod/shutdown_complete (False init, True latch)."""
        self._shutdown_complete_pub.publish(Bool(data=done))

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

        # 1h. TF-1 slope-Params: τ >= 0 (0 = Filter aus), clamp > 0.
        for p in params:
            if p.name == 'slope_estimate_tau_s' and p.value < 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'slope_estimate_tau_s must be >= 0, got {p.value}'
                    ),
                )
            if p.name == 'slope_clamp_deg' and p.value <= 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'slope_clamp_deg must be > 0, got {p.value}',
                )

        # 1i. TF-2/HW8.7b leveling_mode ∈ {horizontal, terrain, auto}.
        for p in params:
            if p.name == 'leveling_mode' and p.value not in (
                'horizontal', 'terrain', 'auto',
            ):
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'unknown leveling_mode {p.value!r}, '
                        f'valid: horizontal | terrain | auto'
                    ),
                )

        # 1i2. Stufe 7 — per-Achse Leveling-Fenster/Filter: >= 0 und inner <= outer.
        for p in params:
            if (
                p.name.startswith('leveling_tau_fast_s_')
                or p.name.startswith('leveling_tau_slow_s_')
                or p.name.startswith('leveling_deadband_inner_deg_')
                or p.name.startswith('leveling_deadband_outer_deg_')
                or p.name.startswith('leveling_slew_max_dps_')
            ) and p.value < 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'{p.name} must be >= 0, got {p.value}',
                )
        _batch = {p.name: p.value for p in params}
        for axis in ('roll', 'pitch'):
            inner_name = f'leveling_deadband_inner_deg_{axis}'
            outer_name = f'leveling_deadband_outer_deg_{axis}'
            inner = _batch.get(
                inner_name, self.get_parameter(inner_name).value
            )
            outer = _batch.get(
                outer_name, self.get_parameter(outer_name).value
            )
            if inner > outer:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'{inner_name} ({inner}) must be <= '
                        f'{outer_name} ({outer})'
                    ),
                )

        # 1j. S4-2 adaptiver Touchdown: Stance-Probe-Fenster + Tiefe plausibel.
        td_probe = self._engine.touchdown_probe_start_stance_phase
        td_search = self._engine.touchdown_search_end_stance_phase
        for p in params:
            if p.name == 'touchdown_probe_start_stance_phase':
                if not 0.0 <= p.value < 1.0:
                    return SetParametersResult(
                        successful=False,
                        reason=(
                            'touchdown_probe_start_stance_phase must be in '
                            f'[0,1), got {p.value}'
                        ),
                    )
                td_probe = p.value
            if p.name == 'touchdown_search_end_stance_phase':
                if not 0.0 < p.value <= 1.0:
                    return SetParametersResult(
                        successful=False,
                        reason=(
                            'touchdown_search_end_stance_phase must be in '
                            f'(0,1], got {p.value}'
                        ),
                    )
                td_search = p.value
            if p.name == 'touchdown_max_extra_depth' and p.value < 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'touchdown_max_extra_depth must be >= 0, got {p.value}'
                    ),
                )
        if td_probe >= td_search:
            return SetParametersResult(
                successful=False,
                reason=(
                    f'touchdown_probe_start_stance_phase ({td_probe}) must be '
                    f'< touchdown_search_end_stance_phase ({td_search})'
                ),
            )

        # 1k. S4-4 Slip/Kante: cliff_depth ≥ 0, debounce ≥ 1, min_legs ∈ [1,6],
        # grace ∈ [0,1).
        for p in params:
            if p.name == 'cliff_depth' and p.value < 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'cliff_depth must be >= 0, got {p.value}',
                )
            if p.name == 'slip_debounce_ticks' and p.value < 1:
                return SetParametersResult(
                    successful=False,
                    reason=f'slip_debounce_ticks must be >= 1, got {p.value}',
                )
            if p.name == 'slip_min_lost_legs' and not 1 <= p.value <= 6:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'slip_min_lost_legs must be in [1,6], got {p.value}'
                    ),
                )
            if p.name == 'slip_grace_stance_phase' and not 0.0 <= p.value < 1.0:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'slip_grace_stance_phase must be in [0,1), got {p.value}'
                    ),
                )

        # 1l. S4-5 Plausibilität: apex_band ∈ [0,1] mit low < high (atomar),
        # apex_fault_cycles ≥ 1, dead_cycles ≥ 1, inject-Format gültig.
        apex_lo = self._sensor_apex_band_low
        apex_hi = self._sensor_apex_band_high
        for p in params:
            if p.name == 'sensor_apex_band_low':
                if not 0.0 <= p.value <= 1.0:
                    return SetParametersResult(
                        successful=False,
                        reason=(
                            f'sensor_apex_band_low must be in [0,1], got {p.value}'
                        ),
                    )
                apex_lo = p.value
            if p.name == 'sensor_apex_band_high':
                if not 0.0 <= p.value <= 1.0:
                    return SetParametersResult(
                        successful=False,
                        reason=(
                            f'sensor_apex_band_high must be in [0,1], got '
                            f'{p.value}'
                        ),
                    )
                apex_hi = p.value
            if p.name == 'sensor_apex_fault_cycles' and p.value < 1:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'sensor_apex_fault_cycles must be >= 1, got {p.value}'
                    ),
                )
            if p.name == 'sensor_dead_cycles' and p.value < 1:
                return SetParametersResult(
                    successful=False,
                    reason=f'sensor_dead_cycles must be >= 1, got {p.value}',
                )
            if (
                p.name == 'sensor_fault_inject'
                and str(p.value).strip().lower() not in ('', 'none')
                and self._parse_sensor_fault_inject(p.value) is None
            ):
                return SetParametersResult(
                    successful=False,
                    reason=(
                        "sensor_fault_inject must be '' | 'none' | "
                        "'<1-6>:stuck_on' | '<1-6>:stuck_off', got "
                        f"'{p.value}'"
                    ),
                )
        if apex_lo >= apex_hi:
            return SetParametersResult(
                successful=False,
                reason=(
                    f'sensor_apex_band_low ({apex_lo}) must be < '
                    f'sensor_apex_band_high ({apex_hi})'
                ),
            )

        # 1m. S4-7 Adaptive Stand: Floor-Tiefe ≥ 0, Absenk-Rate > 0.
        for p in params:
            if p.name == 'stand_conform_max_depth' and p.value < 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=(
                        f'stand_conform_max_depth must be >= 0, got {p.value}'
                    ),
                )
            if p.name == 'stand_conform_rate' and p.value <= 0.0:
                return SetParametersResult(
                    successful=False,
                    reason=f'stand_conform_rate must be > 0, got {p.value}',
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
            # S4-5: dead_ticks = dead_cycles·cycle_time·tick_rate → Rebuild.
            self._rebuild_sensor_health_monitor()
        elif name == 'tick_rate':
            self._tick_rate = value
            self._tfs_seconds = self._tfs_factor / self._tick_rate
            self._restart_timer()
            # S4-5: dead_ticks hängt an tick_rate → Rebuild.
            self._rebuild_sensor_health_monitor()
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
        elif name == 'step_length_intent_step':
            self._step_length_intent_step = value
        elif name == 'step_length_intent_min':
            self._step_length_intent_min = value
        elif name == 'step_length_intent_max':
            self._step_length_intent_max = value
        elif name == 'show_enter_duration':
            self._show_enter_duration = value
        elif name == 'show_exit_duration':
            self._show_exit_duration = value
        elif name == 'show_body_shift_back':
            self._show_body_shift_back = value
        elif name == 'show_shift_fraction':
            self._show_shift_fraction = value
        elif name == 'show_safety_margin':
            self._show_safety_margin = value
        elif name == 'show_front_radial':
            self._show_front_radial = value
        elif name == 'show_front_z':
            self._show_front_z = value
        elif name == 'show_return_rate':
            self._show_return_rate = value
        elif name == 'show_lat_scale':
            self._show_lat_scale = value
        elif name == 'show_vert_scale':
            self._show_vert_scale = value
        elif name == 'show_radial_scale':
            self._show_radial_scale = value
        elif name == 'stance_switch_duration':
            self._stance_switch_duration = value
        elif name == 'stance_switch_step_height':
            self._stance_switch_step_height = value
        elif name == 'gait_pattern':
            self._load_gait_pattern(value)
        # Block A5 Stufe 2 — Leveling-Params live (§4-Entscheidung).
        elif name == 'leveling_enable':
            self._leveling_enable = bool(value)
            if not self._leveling_enable:
                self._balance.reset()
                self._engine.set_body_orientation_offset(0.0, 0.0)
                self._last_leveling_t = None
        elif name == 'leveling_mode':
            # 'terrain' | 'horizontal' (TF-2) | 'auto' (HW8.7b, state-abhängig)
            self._leveling_mode = str(value)
        elif name == 'leveling_startup_grace':
            self._leveling_startup_grace = bool(value)
        # Stufe 7 (E4): per-Achse Leveling-Gains live via Name→(axis,kwarg,is_deg).
        elif name in self._leveling_axis_param_map:
            axis, kwarg, is_deg = self._leveling_axis_param_map[name]
            self._balance.set_axis_gains(
                axis, **{kwarg: math.radians(value) if is_deg else value},
            )
        elif name == 'leveling_max_angle_deg':
            self._leveling_max_angle_deg = value
            self._balance.set_gains(max_level_angle=math.radians(value))
            self._engine.max_level_angle = math.radians(value)
        elif name == 'leveling_max_angle_walking_deg':
            self._leveling_max_angle_walking_deg = value
            self._engine.max_level_angle_walking = math.radians(value)
        # Block A5 Stufe 1/7 — Tip-Params live: Monitor rebuild (per Achse E5).
        elif name == 'tip_detection_enable':
            self._tip_detection_enable = bool(value)
        elif name == 'tip_angle_warn_deg_roll':
            self._tip_angle_warn_deg_roll = value
            self._rebuild_tip_monitor()
        elif name == 'tip_angle_warn_deg_pitch':
            self._tip_angle_warn_deg_pitch = value
            self._rebuild_tip_monitor()
        elif name == 'tip_angle_crit_deg_roll':
            self._tip_angle_crit_deg_roll = value
            self._rebuild_tip_monitor()
        elif name == 'tip_angle_crit_deg_pitch':
            self._tip_angle_crit_deg_pitch = value
            self._rebuild_tip_monitor()
        elif name == 'tip_rate_crit_dps':
            self._tip_rate_crit_dps = value
            self._rebuild_tip_monitor()
        elif name == 'tip_debounce_ticks':
            self._tip_debounce_ticks = int(value)
            self._rebuild_tip_monitor()
        # Block A5 TF-1 — slope-bewusster Tip + Hang-Schätzung live (§4).
        elif name == 'slope_aware_tip_enable':
            self._slope_aware_tip_enable = bool(value)
        elif name == 'slope_estimate_tau_s':
            self._slope_estimate_tau_s = float(value)
            self._slope_est.tau = float(value)
        elif name == 'slope_clamp_deg':
            self._slope_clamp_deg = float(value)
            self._slope_est.clamp = math.radians(float(value))
        # Block A5 S4-1 — Fußkontakt-Debug live. false→true setzt die Diagnose-
        # Zähler zurück (frisches Mess-Fenster pro Konfig in der Verifikation).
        elif name == 'foot_contact_debug_enable':
            new_dbg = bool(value)
            if new_dbg and not self._foot_contact_debug_enable:
                self._contact_diag.reset()
            self._foot_contact_debug_enable = new_dbg
        # Block A5 S4-2 — adaptiver Touchdown live. enable wirkt erst im Tick
        # (mit Live-Guard verUNDet); Fenster/Tiefe direkt auf die Engine.
        elif name == 'adaptive_touchdown_enable':
            self._adaptive_touchdown_enable = bool(value)
        elif name == 'touchdown_probe_start_stance_phase':
            self._engine.touchdown_probe_start_stance_phase = float(value)
        elif name == 'touchdown_search_end_stance_phase':
            self._engine.touchdown_search_end_stance_phase = float(value)
        elif name == 'touchdown_max_extra_depth':
            self._engine.touchdown_max_extra_depth = float(value)
        # Block A5 S4-7 — Adaptive Stand live. enable wirkt erst im Tick (mit
        # Live-Guard verUNDet); Tiefe/Rate direkt auf die Engine. Ein Live-Enable
        # mitten im Stand braucht einen frischen Konform-Anker (sonst rechnet die
        # Descent gegen ein altes _t_stand_entry → sofort Floor).
        elif name == 'adaptive_stand_enable':
            was_enabled = self._adaptive_stand_enable
            self._adaptive_stand_enable = bool(value)
            if (
                self._adaptive_stand_enable
                and not was_enabled
                and self._engine.state == GaitEngine.STATE_STANDING
            ):
                t = time.monotonic() - self._t_start
                self._engine.reset_stand_conform(t)
        elif name == 'stand_conform_max_depth':
            self._engine.stand_conform_max_depth = float(value)
        elif name == 'stand_conform_rate':
            self._engine.stand_conform_rate = float(value)
        # Block A5 S4-4 — Slip/Kante live. enable + cliff_depth spiegeln auf den
        # Engine-Probe-Floor; Monitor-Params → Rebuild.
        elif name == 'slip_detection_enable':
            self._slip_detection_enable = bool(value)
            self._engine.cliff_probe_depth = (
                self._cliff_depth if self._slip_detection_enable else 0.0
            )
            if not self._slip_detection_enable:
                self._support_monitor.reset()
                self._slip_freeze_fired = False
        elif name == 'cliff_depth':
            self._cliff_depth = float(value)
            self._engine.cliff_probe_depth = (
                self._cliff_depth if self._slip_detection_enable else 0.0
            )
        elif name == 'slip_debounce_ticks':
            self._slip_debounce_ticks = int(value)
            self._rebuild_support_monitor()
        elif name == 'slip_min_lost_legs':
            self._slip_min_lost_legs = int(value)
            self._rebuild_support_monitor()
        elif name == 'slip_grace_stance_phase':
            self._slip_grace_stance_phase = float(value)
            self._rebuild_support_monitor()
        # Block A5 S4-5 — Plausibilität live. enable + inject wirken direkt;
        # Monitor-Params (Band/Count/dead_cycles) → Rebuild (auch dead_ticks).
        elif name == 'sensor_plausibility_enable':
            self._sensor_plausibility_enable = bool(value)
            if not self._sensor_plausibility_enable:
                self._sensor_health_monitor.reset()
                self._sensor_faulty = set()
        elif name == 'sensor_apex_band_low':
            self._sensor_apex_band_low = float(value)
            self._rebuild_sensor_health_monitor()
        elif name == 'sensor_apex_band_high':
            self._sensor_apex_band_high = float(value)
            self._rebuild_sensor_health_monitor()
        elif name == 'sensor_apex_fault_cycles':
            self._sensor_apex_fault_cycles = int(value)
            self._rebuild_sensor_health_monitor()
        elif name == 'sensor_dead_cycles':
            self._sensor_dead_cycles = int(value)
            self._rebuild_sensor_health_monitor()
        elif name == 'sensor_fault_inject':
            self._sensor_fault_inject = self._parse_sensor_fault_inject(value)

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
