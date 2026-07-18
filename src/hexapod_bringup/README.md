# hexapod_bringup

Top-Level-Launch-Orchestrierung für den Hexapod. **Resource-only-Paket**
(reine Python-Launch-Files, kein Code).

## Inhalt

```
launch/
├── sim.launch.py        # Standard-Sim-Bringup mit ros2_control (ab Phase 4)
├── real.launch.py       # HW-Bringup mit hexapod_hardware-Plugin (ab Phase 9 Stage G)
├── slope.launch.py      # A5: statische Schräg-Welt (Leveling Stufe 2)
├── ramp.launch.py       # A5: Ramp-Welt flach→Hang→Plateau (nur Sim+Spawn)
└── ramp_walk.launch.py  # A5: EIN-Befehl-Bringup = ramp + gait_node (Auto-Standup)
```

> **A5-Komfort:** `ramp_walk.launch.py` startet Sim **und** gait_node in einem Aufruf →
> der Roboter spawnt + steht automatisch auf (Stabilisierung `terrain` an). Danach nur
> noch `/cmd_vel`. Beispiel:
> `ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=16.0 gait_pattern:=ripple`.
> Args: `slope_deg`, `gait_pattern` (tripod|wave|tetrapod|ripple), `leveling_enable`,
> `gait_delay` (Wartezeit bis gait_node-Start, bei langsamem Kaltstart erhöhen).

## Block I — App-Steuerung über rosbridge (Phase 2)

Für die Handy-/Kishi-Steuerung ([`project_finalization/app_control_requirements/`](../../project_finalization/app_control_requirements/00_overview.md))
publisht die Android-App `sensor_msgs/Joy` über **rosbridge** (WebSocket + JSON) statt über
einen lokalen `joy_node`. Die bestehende `joy_to_twist`-Kette läuft dabei **unverändert** (D3).

```
launch/
├── rosbridge.launch.py   # rosbridge_websocket + rosapi (:9090) — die App<->ROS-Naht (D2)
└── app_teleop.launch.py  # Komfort: rosbridge + joy_to_twist(app-Modus) in EINEM Aufruf
systemd/
└── hexapod_rosbridge.service  # Pi-Always-On-Artefakt (D7) — auf dem Dev-Host NICHT scharf schalten
```

**Konzept — wer publisht `/joy`?** Neuer Arg `joy_source` in `hexapod_teleop/joy_teleop.launch.py`:
- `controller` (Default): `joy_node` (PS4-USB) + `joy_to_twist` — wie bisher (NF7-Fallback).
- `app`: **nur** `joy_to_twist`; die App ist die alleinige `/joy`-Quelle über rosbridge.
  **NF7:** immer genau eine Quelle (kein Doppel-Publisher → sonst Zucken).

**Sim-Test (ohne Handy):** `tools/joy_ws_test_client.py` publisht `/joy` über rosbridge
(App-Ersatz). Ablauf:
```bash
# Terminal 1: Sim-Walk (flach), Roboter steht auf
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0
# Terminal 2: rosbridge + app-Teleop
ros2 launch hexapod_bringup app_teleop.launch.py
# Terminal 3: /joy senden -> Roboter fährt
python3 tools/joy_ws_test_client.py --host 127.0.0.1 --duration 5 --forward 0.6
```
Voll-Anleitung: [`phase_2_control_baseline_test_commands.md`](../../project_finalization/app_control_requirements/phase_2_control_baseline_test_commands.md).

> **rosbridge = Unicast-TCP** → kein DDS-Multicast-Problem; funktioniert über Router (Sim)
> **und** Handy-Hotspot (real HW) **identisch** (D2/D4). Der `use_sim_time`-Arg ist der einzige
> Unterschied: `true` in der Sim (gegen `/clock`), `false` auf dem Pi.

## Block I — Video-Pipeline (Phase 4, Kamera → MJPEG)

Zweiter Kanal **neben** rosbridge (Video ist **nicht** rosbridge — eigener HTTP-Stream-Server,
Contract §5). Kette in der Sim:

```
gz-Kamera-Sensor            (hexapod_description/urdf/hexapod.camera.xacro, Topic /camera/sim)
  → ros_gz_bridge           (config/bridge_camera.yaml)  → /camera/image_raw (sensor_msgs/Image)
  → web_video_server :8080  (MJPEG)  → Handy/Desktop-Browser
```
URL: `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg` (`<host>` = Desktop-IP in Sim,
Pi-IP real). `sim.launch.py`-Arg **`enable_camera`** (Default `true`) startet `camera_bridge` +
`web_video_server` conditional und reicht `enable_camera` an die xacro durch.

> **⚠️ Welt braucht `gz-sim-sensors-system`** (analog `gz-sim-imu-system`), sonst rendert der
> Kamera-Sensor nicht. Der On-Demand-Stack (`bringup_ondemand mode:=sim` → `ramp_walk` →
> `ramp.launch.py`) lädt `hexapod_gazebo/worlds/ramp.sdf.xacro` — dort **und** in `empty_imu.sdf`
> (direkter `sim.launch.py`-Default) ist das Plugin ergänzt. `enable_camera` wird von
> `ramp.launch.py` **nicht** durchgereicht → fällt korrekt auf den `sim.launch.py`-Default `true` zurück.

> **Runtime-Dependency:** `sudo apt install -y ros-jazzy-web-video-server` (Stock-Paket; kein
> Build-Dep — ohne Install startet nur der Node nicht). **HW (Phase 7):** `use_sim=false` → kein
> gz-Sensor; `camera_link` bleibt tf-Frame; die Raspi-Cam v1.3 publisht `/camera/image_raw` direkt.

Test-Anleitung: [`phase_4_video_shell_test_commands.md`](../../project_finalization/app_control_requirements/phase_4_video_shell_test_commands.md).

## Zweck

Ab Phase 4 ist dieses Paket der **Standard-Launcher für die Sim**
(`sim.launch.py`) und ab Phase 9 Stage G zusätzlich der **Standard-
Launcher für die echte Hardware** (`real.launch.py`).

Beide Launcher haben dieselbe Topologie (RSP + controller_manager +
Spawner-Chain JSB → 6 JTC mit OnProcessExit), unterscheiden sich aber
in der Hardware-Backend-Wahl: `sim.launch.py` lädt
`gz_ros2_control/GazeboSimSystem` über Gazebo, `real.launch.py` lädt
`hexapod_hardware/HexapodSystemHardware` direkt im
`ros2_control_node`-Prozess (kein Gazebo). Der URDF-Switch dahinter
ist Stage F (`use_sim`-xacro-arg in
`hexapod_description/urdf/hexapod.ros2_control.xacro`).

Beide Launcher starten **kein gait und kein teleop inline** — das bleibt
modular getrennt:
- `ros2 launch hexapod_gait gait.launch.py` (Phase 5)
- `ros2 launch hexapod_teleop joy_teleop.launch.py` (Phase 6)

## Standard-Aufruf

```bash
ros2 launch hexapod_bringup sim.launch.py
```

LaunchArguments mit Defaults:

| Argument | Default | Bedeutung |
|---|---|---|
| `urdf` | `<hexapod_description>/urdf/hexapod.urdf.xacro` | Top-Level Xacro |
| `world` | `empty.sdf` | wird an `gz sim`-`-r` durchgereicht |
| `spawn_z` | `0.20` | Spawn-Höhe in Metern |

Beispiele:

```bash
# Drop-Test aus 1.5 m
ros2 launch hexapod_bringup sim.launch.py spawn_z:=1.5

# Andere Welt
ros2 launch hexapod_bringup sim.launch.py world:='shapes.sdf'

# Trockenlauf ohne tatsächliche Sim-Aktion (nur Aktions-Tree zeigen)
ros2 launch hexapod_bringup sim.launch.py --print
```

## Was passiert beim Launch

```
Beim Start (parallel):
  ├── gz sim                       (ros_gz_sim/gz_sim.launch.py inkl., on_exit_shutdown)
  ├── robot_state_publisher        (use_sim_time=True, URDF aus xacro)
  ├── spawn_hexapod                (ros_gz_sim/create, One-Shot)
  └── ros_gz_bridge                (config/bridge.yaml aus hexapod_gazebo, /clock)

Stufe 1 — nach spawn_hexapod-Exit:
  └── controller_manager/spawner joint_state_broadcaster (One-Shot)

Stufe 2 — nach JSB-Spawner-Exit (parallel):
  ├── controller_manager/spawner leg_1_controller
  ├── controller_manager/spawner leg_2_controller
  ├── controller_manager/spawner leg_3_controller
  ├── controller_manager/spawner leg_4_controller
  ├── controller_manager/spawner leg_5_controller
  └── controller_manager/spawner leg_6_controller
```

Die zweistufige `OnProcessExit`-Sequenz stellt sicher:
- JSB startet erst, wenn der Roboter in der Sim ist (sonst kein
  `controller_manager` da)
- JTCs starten erst, wenn JSB aktiv ist (sonst keine Joint-States
  zum Lesen)

---

## Real-Hardware-Bringup (Stufe G)

```bash
# Default: echte Servo2040-Hardware ueber /dev/ttyACM0
ros2 launch hexapod_bringup real.launch.py

# Loopback-Modus: Plugin oeffnet keinen seriellen Port,
# nuetzlich fuer CI / Dry-Run / Bringup-Smoke ohne Hardware
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true

# Anderen USB-Port (z.B. wenn /dev/ttyACM0 schon belegt ist)
ros2 launch hexapod_bringup real.launch.py serial_port:=/dev/ttyACM1

# Beides kombinieren
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true serial_port:=/dev/null
```

LaunchArguments mit Defaults:

| Argument | Default | Bedeutung |
|---|---|---|
| `loopback_mode` | `false` | `true`: Plugin öffnet KEINEN seriellen Port und liefert geschriebene Commands als state zurück (CI / Dry-Run / Bringup-Smoke). `false`: echte Servo2040-Anbindung über `serial_port`. |
| `serial_port` | `/dev/ttyACM0` | USB-CDC-Device der Servo2040. Nur relevant wenn `loopback_mode=false`. |

### Was passiert beim Launch

```
Beim Start (parallel):
  ├── robot_state_publisher        (use_sim_time=False, URDF aus xacro
  │                                 mit use_sim:=false + LaunchConfigs)
  └── ros2_control_node            (laedt hexapod_hardware-Plugin via
                                    pluginlib, on_init + on_configure)

Stufe 1 — direkt:
  └── controller_manager/spawner joint_state_broadcaster (One-Shot)

Stufe 2 — nach JSB-Spawner-Exit (parallel):
  ├── controller_manager/spawner leg_1_controller
  ├── ... (leg_2 bis leg_6)
  └── controller_manager/spawner leg_6_controller
```

Unterschiede zu `sim.launch.py`:
- **kein `gz sim`**, **keine `ros_gz_bridge`** (Plugin spricht direkt mit
  der Hardware via USB-CDC, kein /clock-Topic)
- **`use_sim_time=False`** (Wallclock, Phase-6-Übergabe-Notiz)
- **`controllers.real.yaml`** statt `controllers.yaml` (update_rate=50,
  state_interfaces=[position] — Plugin exportiert kein velocity, siehe
  `hexapod_control/README.md`)
- **kein gait, kein teleop, kein RViz** im Launch (modular bei Bedarf
  separat starten)

### Verifikations-Befehle (nach Launch in einem zweiten Terminal)

```bash
ros2 control list_hardware_components
# Erwartung: 1 Eintrag mit plugin name: hexapod_hardware/HexapodSystemHardware, state: active

ros2 control list_controllers
# Erwartung: 7 Zeilen active (joint_state_broadcaster + 6× leg_*_controller)
```

### Wann nutzt man welchen Launch?

| Szenario | Launch | loopback_mode |
|---|---|---|
| Sim-Entwicklung (Phase 4–6 Verhalten) | `sim.launch.py` | n/a |
| CI / Bringup-Verdrahtungs-Smoke ohne Hardware | `real.launch.py` | `true` |
| Bench-Test mit Servo2040 (ohne Servos angeschlossen) | `real.launch.py` | `false` (Default) |
| Echter Hexapod, aufgebockt | `real.launch.py` | `false` |
| Echter Hexapod, mit Roboter aufm Boden (Phase 12) | `real.launch.py` | `false` |

---

## Beziehung zu anderen Paketen

| Paket | Wird von hexapod_bringup wofür benutzt? |
|---|---|
| `hexapod_description` | URDF (xacro), inklusive `<ros2_control>`-Block + Plugin |
| `hexapod_gazebo` | `bridge.yaml` aus `config/` (für `/clock`) — nur `sim.launch.py` |
| `hexapod_control` | `controllers.yaml` (Sim) / `controllers.real.yaml` (HW) aus `config/` |
| `hexapod_hardware` | `HexapodSystemHardware`-Plugin (pluginlib, via URDF) — nur `real.launch.py` |
| `ros_gz_sim` | `gz_sim.launch.py` als Sub-Launch (gz-Start + Spawn) — nur `sim.launch.py` |
| `ros_gz_bridge` | `parameter_bridge` mit `bridge.yaml` — nur `sim.launch.py` |
| `controller_manager` | `spawner`-Executable für die 7 Spawner-Knoten + `ros2_control_node` (nur `real.launch.py`) |
| `robot_state_publisher` | RSP-Knoten (xacro→URDF→`/tf`) |

## Phase-3-Alternative behalten

[hexapod_gazebo/launch/sim.launch.py](../hexapod_gazebo/launch/sim.launch.py)
bleibt als „**Plain-Sim ohne Controller**"-Launcher erhalten. Nützlich,
wenn du Bodenkontakt-Verhalten oder Reibungswerte ohne Controller-Layer
debuggen willst.

| Frage | Launch-File |
|---|---|
| „Standard-Sim mit Controllern" | `hexapod_bringup sim.launch.py` ← **default** |
| „Nur Physik, ohne Controller" | `hexapod_gazebo sim.launch.py` |

## Konzept-Hintergrund

Vollständige Erklärung von ROS2-Launch-Files (LaunchDescription,
Substitutions, Event-Handler, Spawner-Pattern, `--print`-Dry-Run,
Erweiterung in Phase 5/6/7) in
[../../docs/phase_4_launch_explained.md](../../docs/phase_4_launch_explained.md).

## Bekannte Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `gz sim` öffnet sich nicht | Snap-`LD_LIBRARY_PATH`-Konflikt (Phase-3-Issue) | aus normalem Terminal starten, oder `world:='-s empty.sdf'` (headless) |
| Spawner-Timeout `Wait for service ... timed out` | controller_manager nicht verfügbar | Spawn-Knoten muss vor JSB exiten (OnProcessExit) — Logs prüfen |
| `Could not find a parameter file` | `$(find hexapod_control)` schlägt fehl | `install/setup.bash` neu sourcen |
| Bewegung wirkt nicht in RViz | `use_sim_time` fehlt am RViz-Aufruf | `ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true` |
