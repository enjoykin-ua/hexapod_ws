# hexapod_gazebo

Gazebo-Harmonic-Bringup für die Hexapod-Simulation. **Desktop-only** —
auf dem Pi wird dieses Paket nicht gebaut.

> **Ab Phase 4: dies ist der „Plain-Sim ohne Controller"-Launcher.**
> Der Standard-Bringup für die Sim ist jetzt
> `ros2 launch hexapod_bringup sim.launch.py` — der startet zusätzlich
> zu allem hier auch die `ros2_control`-Controller (`joint_state_broadcaster`
> + 6× `joint_trajectory_controller`, einer pro Bein).
>
> `hexapod_gazebo/launch/sim.launch.py` (dieses Paket) bleibt bewusst
> erhalten als isolierter Physik-/Reibungs-Test ohne Controller-Layer:
> nützlich, wenn du Bodenkontakt-Verhalten, Inertien oder Spawn-Pose
> debuggen willst, ohne dass JTC oder JSB ins Bild spielen.

## Was dieses Paket tut

- Startet Gazebo Harmonic über `ros_gz_sim` mit der Default-Welt (`empty.sdf`,
  enthält `ground_plane` + Sun).
- Spawnt den Hexapod aus dem URDF von `hexapod_description`.
- Brückt `/clock` von Gazebo nach ROS2 (`rosgraph_msgs/msg/Clock`), sodass
  jeder ROS-Node mit `use_sim_time:=true` Sim-Zeit statt Wallclock nutzt.

Was es **nicht** tut: Joints aktiv steuern, Sensoren bridgen, Joint-States
nach ROS2 brücken — das alles macht der Phase-4-Bringup
(`hexapod_bringup`).

## Standard-Aufruf

```bash
ros2 launch hexapod_gazebo sim.launch.py
```

LaunchArguments mit Default-Werten:

| Argument | Default | Bedeutung |
|---|---|---|
| `urdf` | `<hexapod_description>/urdf/hexapod.urdf.xacro` | Top-Level Xacro |
| `world` | `empty.sdf` | wird an `gz sim`-`-r` durchgereicht |
| `spawn_z` | `0.20` | Spawn-Höhe in Metern |

Beispiele:
```bash
# Drop-Test aus 1.5 m
ros2 launch hexapod_gazebo sim.launch.py spawn_z:=1.5

# Andere Default-Welt aus gz-sim
ros2 launch hexapod_gazebo sim.launch.py world:='shapes.sdf'

# Headless (Server-only, keine GUI)
ros2 launch hexapod_gazebo sim.launch.py world:='-s empty.sdf'
```

## Komponenten im Launch

`sim.launch.py` startet vier Aktionen parallel:

1. **`gz sim`** über `ros_gz_sim/gz_sim.launch.py` mit `gz_args='-r <world>'`
   und `on_exit_shutdown=true`.
2. **`robot_state_publisher`** mit `use_sim_time=True` und dem URDF aus
   xacro als `robot_description`-Parameter.
3. **Spawn-Node `ros_gz_sim/create`** — One-Shot: liest `/robot_description`,
   konvertiert URDF→SDF, ruft Spawn-Service in `gz sim` auf.
4. **Bridge `ros_gz_bridge/parameter_bridge`** mit `config/bridge.yaml` —
   Phase 3: nur `/clock` (`GZ_TO_ROS`).

## Reibungs- und Kontaktwerte (Foot-Kugeln)

Die Reibung liegt **nicht** in diesem Paket, sondern in
`hexapod_description/urdf/hexapod.gazebo.xacro` (Macro `foot_friction`).
Phase-3-Defaults für jede der 6 Foot-Kugeln:

| Parameter | Wert | Bedeutung |
|---|---|---|
| `mu1`, `mu2` | `1.0` | Coulomb-Reibung in beide Tangentialrichtungen (Gummi/Beton) |
| `kp` | `1.0e6` | Kontakt-Steifigkeit (Penalty-Feder) |
| `kd` | `100` | Kontakt-Dämpfung |

> **✅ Verifiziert in Phase 4 Stufe F (2026-05-08):** Default-Werte
> tragen den Roboter unter realer Stand-Last sauber. Stand-Pose
> `coxa=0/femur=-0.5/tibia=+1.0` auf alle 6 Beine, Drift gemessen via
> `gz model -m hexapod -p` über 5 s: **z und RPY bit-genau identisch
> über alle Samples, Drift = 0 mm / 0°** (Done-Kriterium fordert nur
> < 1 mm / < 0.5°). Kein Zittern, kein Wegrutschen — kein Tuning der
> Default-Werte nötig. Details in `docs/phase_4_progress.md` Stufe F
> Umsetzungsnotizen.
>
> **Falls in späteren Phasen (5+) doch Probleme auftreten** (z. B. unter
> dynamischer Gait-Last):
> - Wegrutschen → `mu1`, `mu2` auf `1.5`
> - Zittern → `kp` auf `1.0e7`, ggf. `inertia_min` von `1.0e-5` auf
>   `1.0e-4` in `hexapod_description/urdf/inertials.xacro`

## RViz-Andockung (Phase-3-Krücke, Phase-4-Ersatz)

In Phase 3 hat Gazebo keine `/joint_states`-Brücke nach ROS, deshalb hat
`robot_state_publisher` keine Live-Gelenkwinkel und das `/tf`-Topic ist
unvollständig — RViz kann den Roboter nicht zeichnen.

**Workaround für die Phase-3-RViz-Abnahme** (wird in Phase 4 obsolet):

```bash
# Terminal 1
ros2 launch hexapod_gazebo sim.launch.py

# Terminal 2 — RViz mit Sim-Zeit
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true

# Terminal 3 — JSP-Krücke (alle Joints auf 0)
ros2 run joint_state_publisher joint_state_publisher \
  --ros-args -p use_sim_time:=true
```

In RViz dann „Add → By display type → RobotModel" und Fixed Frame auf
`base_link` setzen. Der Roboter erscheint in Default-Pose (alle Joints
= 0), nicht synchron zur Gazebo-Pose. Phase 4 ersetzt die Krücke durch
echte Live-States aus `gz_ros2_control`.

## Bekannte Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Gazebo-GUI crasht mit `__libc_pthread_init` | Snap-Library-Konflikt mit `gz sim gui` | Workaround: `world:='-s empty.sdf'` (headless). Im normalen User-Terminal trat der Crash nicht auf — kommt aus exotischen `LD_LIBRARY_PATH`-Konstellationen. |
| Roboter sinkt durch den Boden | Welt ohne `ground_plane` | `gz_args` muss `empty.sdf` (oder andere Default-Welt) enthalten, nicht eine leere Szene aus dem GUI-Editor. |
| `/clock` fehlt in `ros2 topic list` | Bridge-Crash | Launch-Logs nach „Creating GZ->ROS Bridge" durchsuchen. `bridge.yaml`-Pfad und Permissions prüfen. |
| RViz zeigt Roboter nicht | `Fixed Frame=map` und/oder fehlende `/joint_states` | Fixed Frame auf `base_link` umstellen + JSP-Krücke starten (siehe oben). |
| `joint_state_publisher_gui`-Slider in Gazebo wirkungslos | Kein Server-Plugin — Phase 4 | Phase-Scope; nicht versuchen. |
| KDL-Warning für `base_link` mit Inertia | `kdl_parser` mag keine Wurzel-Inertia | Aus Phase 2 bekannt, nicht funktional kritisch. Fix erwogen in Phase 4 mit Dummy-Root-Link. |

Vollständige Diagnose-Befehle in `docs/phase_3_progress.md` (Cheatsheets
am Ende der Stufen B/C/D) und `docs/phase_3_stage_D_tryout.md`.

## Phase-3-Status

**Alle 6 Done-Kriterien aus `docs/phase_3_gazebo.md` erfüllt** (Kriterium 4
nachträglich in **Phase 4 Stufe F** verifiziert):

| # | Kriterium | Status |
|---|---|---|
| 1 | `hexapod_gazebo` baut | ✅ |
| 2 | Launch startet Gazebo + Roboter + Bodenebene | ✅ |
| 3 | Roboter durchschlägt Boden nicht, kollabiert nicht | ✅ |
| 4 | Stabiler Stand bei manuell gesetzten Joint-Winkeln | ✅ (Phase 4 Stufe F: Drift = 0 mm / 0° über 5 s, Default-Reibung ausreichend) |
| 5 | `/clock` in ROS sichtbar | ✅ (~935 Hz) |
| 6 | RViz zeigt Modell mit `use_sim_time:=true` | ✅ (Phase 3: mit JSP-Krücke; Phase 4 Stufe E: ohne JSP-Krücke synchron via JSB) |
