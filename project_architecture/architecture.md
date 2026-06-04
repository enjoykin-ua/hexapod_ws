# System-Architektur

> High-level Karte. Details immer in den verlinkten Source-Dateien verifizieren
> (sie sind die Wahrheit; diese Übersicht kann hinterherhinken — bei Änderungen
> via [`ai_navigation.md`](ai_navigation.md) nachziehen).

## 1. ROS2-Pakete (`src/`)
| Paket | Sprache | Inhalt |
|---|---|---|
| `hexapod_description` | xacro/URDF | Roboter-Modell, Meshes, Joint-Limits, ros2_control-Tags, `display.launch.py`. |
| `hexapod_control` | yaml | Controller-Configs: `controllers.yaml` (Sim), `controllers.real.yaml` (HW). |
| `hexapod_kinematics` | Python | IK/FK (`leg_ik`, `leg_fk`), Geometrie + Limits (`config.py`), `JointLimits`, `HEXAPOD`. |
| `hexapod_gait` | Python | `gait_node` (Knoten), `gait_engine` (State-Machine), `gait_patterns`, `trajectory_gen`, `reachability_viz`; `gait.launch.py`, `stand.launch.py`, `reachability_viz.launch.py`; `config/presets/`. |
| `hexapod_teleop` | Python | `joy_to_twist` (Joy→cmd_vel/cmd_body_height), `config/ps4_usb.yaml`, `joy_teleop.launch.py`. |
| `hexapod_hardware` | C++ | `ros2_control`-SystemInterface-Plugin ↔ Servo2040; `calibration.cpp` (rad↔pulse); `config/servo_mapping.yaml` (Puls-Cal je Pin). |
| `hexapod_sensors` | (Python/URDF) | IMU / Foot-Contact (geplant/teilweise; **Inhalt vor Nutzung verifizieren**). Topic-Konvention IMU: `/imu/data`. |
| `hexapod_gazebo` | xacro/launch | Sim-Welt, Sim-Plugins, `sim.launch.py` (Gazebo-Seite). |
| `hexapod_bringup` | launch | `sim.launch.py` (Gazebo+control+RViz), `real.launch.py` (HW: rsp + controller_manager + spawner). |

## 2. Node-Graph

**Gemeinsam (Sim & HW):**
- `robot_state_publisher` — URDF + `/joint_states` → `/tf`.
- `joint_state_broadcaster` — Controller, publisht `/joint_states`.
- `leg_1..6_controller` — je ein `JointTrajectoryController` (3 Joints/Bein) → fährt die Servos/Sim-Joints.
- `gait_node` — die Lokomotions-Logik (50 Hz). Siehe §3.
- `joy_node` + `joy_to_twist` — nur wenn Teleop läuft.

**Sim-spezifisch:** `gz_ros2_control` (Gazebo-Plugin) stellt das `ros2_control`-System + lädt `controllers.yaml`.
**HW-spezifisch:** `ros2_control_node` (controller_manager) lädt `controllers.real.yaml` + das `hexapod_hardware`-Plugin (statt gz).

## 3. `gait_node` — Schnittstellen
- **Subscribes:** `/cmd_vel` (`geometry_msgs/Twist`), `/cmd_body_height` (`std_msgs/Float64`), `/joint_states` (`sensor_msgs/JointState`, für Ramp-Start).
- **Publishes:** 6× `/leg_<n>_controller/joint_trajectory` (`trajectory_msgs/JointTrajectory`, je 1 Punkt/Tick, Position-only, `time_from_start = tfs_factor/tick_rate`).
- **Service-Client:** `/hexapod_safety_freeze` (`std_srvs/Trigger`) — bei IKError feuert er den Freeze (HW-Plugin-seitiger Hard-Stop).
- **State-Machine (`gait_engine`):** `STARTUP_RAMP` / `CARTESIAN_STANDUP` / `REPOSITION` / `STANDING` / `WALKING` / `STOPPING`. cmd_vel wird in allen Nicht-STANDING/WALKING-Aufsteh-/Reposition-States **ignoriert**.

## 4. Topic-/Service-Übersicht (was wird ausgetauscht)
| Topic/Service | Typ | Von → Nach | Inhalt |
|---|---|---|---|
| `/cmd_vel` | Twist | teleop/extern → gait_node | Soll-Body-Velocity (x,y,ω) |
| `/cmd_body_height` | Float64 | teleop → gait_node | absolute Stand-Höhe (nur STANDING) |
| `/leg_<n>_controller/joint_trajectory` | JointTrajectory | gait_node → JTC | Soll-Joint-Winkel/Bein |
| `/joint_states` | JointState | broadcaster → gait_node, rsp | Ist-Joint-Winkel |
| `/joy` | Joy | joy_node → joy_to_twist | Achsen/Buttons |
| `/robot_description` | String | rsp/launch | URDF-XML (Limit-Quelle fürs Plugin + gait) |
| `/hexapod_safety_freeze` | Trigger (srv) | gait_node → hardware | Hard-Stop-Anforderung |
| `/imu/data` | Imu | (geplant) sensors → balance | Orientierung/Beschl. |

## 5. Hardware-Kette (HW-Pfad)
```
2S LiPo (Ziel) → [Relay-Gate Servo-Rail] → Servo2040 (RP2040) → 18× PWM → Servos
                                                  ↑ USB-CDC (Protokoll) ↕
                              Host (Desktop jetzt / Raspberry Pi 5 Ziel)
                              └ ros2_control_node + hexapod_hardware-Plugin
```
- **Servos:** Coxa = Diymore 8120MG (20 kg·cm); Femur+Tibia = Miuzei MS61 (35 kg·cm). Alle 4.8–8.4 V, 270°. (Memory `project_hexapod_servo_models`.)
- **Relay-Gate:** trennt die Servo-Versorgung (Power-On-Zentrieren der Servos ist HW-fix → aufgebockt booten + smooth rampen).

## 6. ⭐ Limit- & Kalibrierungs-Quellen (kritisch)
- **Joint-Limits stehen an ZWEI Stellen** (müssen synchron sein):
  1. **URDF** — `hexapod.urdf.xacro` (6× `<xacro:leg>`), `hexapod.ros2_control.xacro` (6× `joint_iface`), `hexapod_physical_properties.xacro` (Property-Defaults). Das ist die Quelle fürs Plugin **und** für `gait_node` (parst `/robot_description` live).
  2. **`config.py`** (`hexapod_kinematics`) — `_COXA/_FEMUR/_TIBIA_LIMITS`. Cross-Check: `test_config.py`.
  - ⚠️ Coxa in config.py ist noch **stale** (±1.57 vs URDF ±0.415). Tibia aktuell **−1.00/+2.50** (Stage 1 Teil 2.1).
- **Puls-Kalibrierung:** `servo_mapping.yaml` (je Pin `pulse_min/zero/max`, `direction`). Modell linear, **Slope k=425 µs/rad**, hart in `[500,2500] µs`. `calibration.cpp::radians_to_pulse_us`.
- **Geometrie:** `physical_properties.xacro` + `config.py` (`_L_COXA/_FEMUR/_TIBIA`, body-Maße). Geometrie-Änderung = TABU-nah (großer Rattenschwanz, s. `ai_navigation.md`).

## 7. Launch-Einstiegspunkte
| Zweck | Befehl |
|---|---|
| Sim (Gazebo + control + RViz) | `ros2 launch hexapod_bringup sim.launch.py` |
| HW (controller_manager + Plugin) | `ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid` |
| Gait (Aufstehen→Reposition→Walk) | `ros2 launch hexapod_gait gait.launch.py robot_description_file:=… params_file:=…` |
| Teleop (PS4 USB) | `ros2 launch hexapod_teleop joy_teleop.launch.py` |
| Reachability-Viz | `ros2 launch hexapod_gait reachability_viz.launch.py` |
| Modell-Anzeige (RViz + Slider) | `ros2 launch hexapod_description display.launch.py` |
