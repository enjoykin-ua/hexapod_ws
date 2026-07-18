# System-Architektur

> High-level Karte. Details immer in den verlinkten Source-Dateien verifizieren
> (sie sind die Wahrheit; diese Übersicht kann hinterherhinken — bei Änderungen
> via [`ai_navigation.md`](ai_navigation.md) nachziehen).

## 1. ROS2-Pakete (`src/`)
| Paket | Sprache | Inhalt |
|---|---|---|
| `hexapod_description` | xacro/URDF | Roboter-Modell, Meshes, Joint-Limits, ros2_control-Tags, `display.launch.py`. Sensor-xacros: `hexapod.imu.xacro`, `hexapod.foot_contact.xacro`, **`hexapod.camera.xacro`** (Block I Ph.4: `enable_camera`, gz-Kamera-Sensor `/camera/sim` → Video, camera_link tf-Frame auch auf HW). |
| `hexapod_control` | yaml | Controller-Configs: `controllers.yaml` (Sim), `controllers.real.yaml` (HW). |
| `hexapod_kinematics` | Python | IK/FK (`leg_ik`, `leg_fk`), Geometrie (`geometry.py`: `rotate_z`, `rotate_xy`, base↔leg-Frame) + Limits (`config.py`), `JointLimits`, `HEXAPOD`. |
| `hexapod_gait` | Python | `gait_node` (Knoten), `gait_engine` (State-Machine + Body-Leveling-Stellpfad + S4 adaptiver Touchdown/Stand), `gait_patterns`, `trajectory_gen`, `tip_monitor` (A5 St.1), `balance_controller` (A5 St.2), `reachability_viz`, `torque_viz`, `foot_contact_viz` (A5 St.5, Fuß-Marker); `gait.launch.py`, `stand.launch.py`; `config/presets/`. **Ph.5:** publisht `/hexapod/status` (5 Hz, JSON). |
| `hexapod_teleop` | Python | `joy_to_twist` (Joy→cmd_vel/cmd_body_height; Tempo-Scales `linear_x/y_scale`/`angular_z_scale`/`slow_factor`/`deadzone` **live-tunbar** via `param set`), `config/ps4_usb.yaml`, `joy_teleop.launch.py`. **Block I:** `joy_teleop.launch.py` hat `joy_source:=controller\|app` — `app` = nur `joy_to_twist`, die Android-App publisht `/joy` über rosbridge (kein `joy_node`, NF7: genau 1 Quelle). **Ph.5:** publisht `/hexapod/tempo` (latched, aktives Preset). |
| `hexapod_hardware` | C++ | `ros2_control`-SystemInterface-Plugin ↔ Servo2040; `calibration.cpp` (rad↔pulse); `config/servo_mapping.yaml` (Puls-Cal je Pin); publisht auf HW die 6 `/leg_<n>/foot_contact` aus GET_INPUTS (A5 St.5) + `/hexapod/shutdown_request`. |
| `hexapod_sensors` | Python/URDF | **IMU real** (A5 Stufe 0): `imu_monitor` (`/imu/data`→roll/pitch, `/imu/monitor`, world→base_link-tf); Foot-Contact-Publisher. IMU-xacro in `hexapod_description` (`hexapod.imu.xacro`). |
| `hexapod_gazebo` | xacro/launch | Sim-Welt, Sim-Plugins, `worlds/empty_imu.sdf` (+ `slope.sdf.xacro`, A5 Stufe 2), `sim.launch.py` (Gazebo-Seite). **Ph.4:** `worlds/empty_imu.sdf` + `ramp.sdf.xacro` tragen zusätzlich `gz-sim-sensors-system` (Kamera-Rendering). |
| `hexapod_bringup` | launch | `sim.launch.py` (Gazebo+control+RViz), `real.launch.py` (HW: rsp + controller_manager + spawner). **Block I:** `rosbridge.launch.py` (rosbridge_websocket+rosapi :9090), `app_teleop.launch.py` (rosbridge + `joy_to_twist` app-Modus); **Ph.3:** `always_on.launch.py` (rosbridge+supervisor+bringup_launcher, ab Boot), `bringup_ondemand.launch.py` (on-demand Walk+Teleop, mode sim/real, Bauch-Start), `systemd/hexapod_always_on.service`. **Ph.4:** `config/bridge_camera.yaml` + `web_video_server`-Node (:8080 MJPEG) in `sim.launch.py` (`enable_camera`, Default true) = Video-Kanal (Kanal 2, nicht rosbridge). |
| `hexapod_supervisor` | Python | **Block F/I — Lifecycle + HMI-Glue.** **Ph.5:** `hmi_status` (Always-On) latcht `/hexapod/capabilities` + `/hexapod/config_manifest` (aus `config/hmi_config_manifest.yaml`, 39 Params) + republished `/rosout` WARN+ auf `/hexapod/alerts`. `shutdown_supervisor` (lauscht HW-Schalter `/hexapod/shutdown_request` → kontrolliertes Hinsetzen via `/hexapod_shutdown` → `/hexapod/shutdown_complete` → guarded OS-Poweroff; `os_shutdown.guarded_shutdown` mit **3-fach-Guard**: Dev-Host-Hardblock + `enable_os_shutdown` + `pi_hostname`). **Ph.3:** `bringup_launcher` (startet/stoppt den On-Demand-Stack als Subprozess-Gruppe, `SIGINT→TERM→KILL`, keine Zombies; 4 Trigger-Services + latched `/hexapod/bringup_running`; guarded `/hexapod_pi_shutdown`) + expliziter `/hexapod_request_shutdown`-Service. `config/{supervisor,launcher.sim,launcher.real}.yaml`. |

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
- **State-Machine (`gait_engine`):** `STARTUP_RAMP` / `CARTESIAN_STANDUP` / `REPOSITION` / `STANDING` / `WALKING` / `STOPPING` / `SAT` (+ Sitdown-/Show-States). cmd_vel wird in allen Nicht-STANDING/WALKING-Aufsteh-/Reposition-States **ignoriert**.
- **Bauch-Start (Block I Ph.3):** Param `auto_standup_on_start` (Default `true` = Auto-Standup beim ersten `/joint_states`, unverändert). `false` → `gait_engine.hold_sat_at(spawn)`: bleibt in **SAT** (Bauch-/Spawn-Pose), Aufstehen nur per `/hexapod_stand_up` (sicherer On-Demand-Default, [D7]).

## 4. Topic-/Service-Übersicht (was wird ausgetauscht)
| Topic/Service | Typ | Von → Nach | Inhalt |
|---|---|---|---|
| `/cmd_vel` | Twist | teleop/extern → gait_node | Soll-Body-Velocity (x,y,ω) |
| `/cmd_body_height` | Float64 | teleop → gait_node | absolute Stand-Höhe (nur STANDING) |
| `/leg_<n>_controller/joint_trajectory` | JointTrajectory | gait_node → JTC | Soll-Joint-Winkel/Bein |
| `/joint_states` | JointState | broadcaster → gait_node, rsp | Ist-Joint-Winkel |
| `/joy` | Joy | joy_node **oder** App→rosbridge → joy_to_twist | Achsen/Buttons (PS4-Layout). **Block I:** App publisht `/joy` (**RELIABLE** Pflicht) über rosbridge statt joy_node. Naht/Mapping: `project_finalization/app_control_requirements/interface_contract.md` |
| `/robot_description` | String | rsp/launch | URDF-XML (Limit-Quelle fürs Plugin + gait) |
| `/hexapod_safety_freeze` | Trigger (srv) | gait_node → hardware | Hard-Stop-Anforderung |
| `/imu/data` | Imu | sensors/sim → gait_node | Orientierung/Gyro → Kipp-Erkennung (A5 St.1) + Body-Leveling (A5 St.2, `leveling_enable`, nur STANDING). Sensor-QoS best_effort. ⚠️ gz-IMU **spawn-referenziert** → Sim flach spawnen. **HW-Quelle** = eigener `bno055_imu`-Node (Stufe 6, geplant), Sim = gz-Sensor+Bridge |
| `/leg_<n>/foot_contact` | Bool | sensors/HW-Plugin → gait_node | Fuß-Bodenkontakt/Bein → S4 (adaptiver Touchdown/Stand, Plausibilität). **Sim-Quelle** = `foot_contact_publisher` (aus gz-Contact); **HW-Quelle** (A5 Stufe 5 🟢) = `hexapod_hardware`-Plugin aus Servo2040 GET_INPUTS. gait_node cacht + Live-Guard 0.5 s |
| `/camera/image_raw` | Image | gz-Kamera→Bridge (Sim) / Raspi-Cam (HW) → **App** | Video-Kanal (Block I Ph.4). Sim: `hexapod.camera.xacro` (Topic `/camera/sim`, 1280×720@15) → `bridge_camera.yaml`. **Nicht rosbridge:** `web_video_server` :8080 serviert es als MJPEG (`http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg`, Contract §5). Welt braucht `gz-sim-sensors-system` (ramp.sdf.xacro/empty_imu.sdf). HW = Raspi-Cam v1.3 (Phase 7), gleiches Topic |
| `/hexapod/status` | String (JSON) | gait_node → **App** | Overlay-Live-Zustand (Block I Ph.5, 5 Hz): state/stance/gait/safety/tip + dyn. H1/H2-Caps. Contract §6a |
| `/hexapod/tempo` | String (JSON, latched) | joy_to_twist → **App** | aktives Tempo-Preset + Scales (Ph.5) |
| `/hexapod/capabilities` · `/hexapod/config_manifest` | String (JSON, latched) | `hmi_status` → **App** | Enums (Dropdowns) + kuratierte Whitelist der verstellbaren Params (Config-Panel; App rendert generisch, get/set via native rosbridge-Param-Services). Ph.5, Always-On → beim Connect da |
| `/hexapod/alerts` | String (JSON, latched N=50) | `hmi_status` (aus `/rosout`) → **App** | WARN/ERROR/FATAL-Liste (Ph.5) |
| `/hexapod_bringup_start` / `_stop` / `_status` | Trigger (srv) | App → `bringup_launcher` | On-Demand-Stack starten/stoppen/Status (Block I Ph.3) |
| `/hexapod_pi_shutdown` | Trigger (srv) | App → `bringup_launcher` | Pi ausschalten, guarded (Stack läuft → Block-F-Kette; idle → direkter Poweroff; **Dev = Dry-Run**) |
| `/hexapod/bringup_running` | Bool (latched) | `bringup_launcher` → App | läuft der schwere Stack? (Connect-/Start-Screen) |
| `/hexapod_request_shutdown` | Trigger (srv) | `bringup_launcher` → `shutdown_supervisor` | expliziter Shutdown-Trigger (umgeht die Latched-Topic-Baseline von `/hexapod/shutdown_request`) |

## 5. Hardware-Kette (HW-Pfad)
```
2S LiPo (Ziel) → [Relay-Gate Servo-Rail] → Servo2040 (RP2040) → 18× PWM → Servos
                                                  ↑ USB-CDC (Protokoll) ↕
                              Host (Desktop jetzt / Raspberry Pi 5 Ziel)
                              └ ros2_control_node + hexapod_hardware-Plugin
```
- **Servos:** Coxa = Diymore 8120MG (20 kg·cm); Femur+Tibia = Miuzei MS61 (35 kg·cm). Alle 4.8–8.4 V, 270°. (Memory `project_hexapod_servo_models`.)
- **Relay-Gate:** trennt die Servo-Versorgung (Power-On-Zentrieren der Servos ist HW-fix → aufgebockt booten + smooth rampen).
- **Fuß-Taster (A5 St.5 🟢):** 6× NO-Microswitch an den Servo2040-SENSOR-Kanälen (interner Pull-Up gegen GND) → FW `GET_INPUTS` → Plugin publisht `/leg_<n>/foot_contact`.
- **IMU (A5 St.6, geplant):** BNO-055 per **Qwiic/I2C direkt am Pi** (`0x28`) → eigener `bno055_imu`-Node → `/imu/data`. **Nicht** am Servo2040.

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
| Sim (Gazebo + control + RViz) | `ros2 launch hexapod_bringup sim.launch.py` (**Ph.4:** inkl. Kamera + `web_video_server` :8080, `enable_camera:=true` Default; Video-URL `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg`) |
| HW (controller_manager + Plugin) | `ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid` |
| Gait (Aufstehen→Reposition→Walk) | `ros2 launch hexapod_gait gait.launch.py robot_description_file:=… params_file:=…` |
| Teleop (PS4 USB) | `ros2 launch hexapod_teleop joy_teleop.launch.py` |
| **App-Teleop (Block I)** | `ros2 launch hexapod_bringup app_teleop.launch.py` (rosbridge :9090 + `joy_to_twist` app-Modus) |
| rosbridge allein | `ros2 launch hexapod_bringup rosbridge.launch.py` |
| **Always-On (Block I Ph.3)** | `ros2 launch hexapod_bringup always_on.launch.py` (rosbridge + supervisor + `bringup_launcher`; App startet den schweren Stack on demand via `/hexapod_bringup_start`) |
| Reachability-Viz | `ros2 launch hexapod_gait reachability_viz.launch.py` |
| Modell-Anzeige (RViz + Slider) | `ros2 launch hexapod_description display.launch.py` |
