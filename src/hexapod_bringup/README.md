# hexapod_bringup

Top-Level-Launch-Orchestrierung für den Hexapod. **Resource-only-Paket**
(reine Python-Launch-Files, kein Code).

## Inhalt

```
launch/
└── sim.launch.py    # Standard-Sim-Bringup mit ros2_control (ab Phase 4)
```

## Zweck

Ab Phase 4 ist dieses Paket der **einzige Standard-Launcher für die Sim**.
Es kombiniert die Phase-3-Sim-Bringup-Aktionen (`gz sim`, `robot_state_publisher`,
Spawn, ros_gz-Bridge) mit den `ros2_control`-Spawner-Knoten (1× JSB + 6× JTC).

Ab Phase 5 kommen weitere Top-Level-Launches dazu (`gait.launch.py`,
später `teleop.launch.py`, in Phase 7 `real.launch.py`), die diesen
Sim-Bringup als Sub-Launch includieren.

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

## Beziehung zu anderen Paketen

| Paket | Wird von hexapod_bringup wofür benutzt? |
|---|---|
| `hexapod_description` | URDF (xacro), inklusive `<ros2_control>`-Block + Plugin |
| `hexapod_gazebo` | `bridge.yaml` aus `config/` (für `/clock`) |
| `hexapod_control` | `controllers.yaml` aus `config/` (vom URDF-Plugin geladen) |
| `ros_gz_sim` | `gz_sim.launch.py` als Sub-Launch (gz-Start + Spawn) |
| `ros_gz_bridge` | `parameter_bridge` mit `bridge.yaml` |
| `controller_manager` | `spawner`-Executable für die 7 Spawner-Knoten |
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
