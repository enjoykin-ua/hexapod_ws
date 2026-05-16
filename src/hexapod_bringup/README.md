# hexapod_bringup

Top-Level-Launch-Orchestrierung für den Hexapod. **Resource-only-Paket**
(reine Python-Launch-Files, kein Code).

## Inhalt

```
launch/
├── sim.launch.py     # Standard-Sim-Bringup mit ros2_control (ab Phase 4)
└── real.launch.py    # HW-Bringup mit hexapod_hardware-Plugin (ab Phase 9 Stage G)
```

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
