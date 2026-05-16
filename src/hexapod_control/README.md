# hexapod_control

`ros2_control`-Konfiguration für den Hexapod. **Resource-only-Paket**
(reine YAML-Konfiguration, kein Code).

## Inhalt

```
config/
├── controllers.yaml        # Sim-Pfad (Phase 4–6): controller_manager + 1× JSB + 6× JTC, position+velocity-state
└── controllers.real.yaml   # HW-Pfad (Phase 9 Stage F): selber Aufbau, position-state only, update_rate 50, use_sim_time false
```

## Zweck

Definiert die **Software-Sicht** auf das `ros2_control`-System:
welche Controller existieren, mit welchem Typ, welche Joints sie
abonnieren, mit welchen Update-/Publish-Raten. Die Hardware-Sicht
(welche Joints + Interfaces überhaupt existieren) liegt im
`<ros2_control>`-Block des URDF in
[hexapod_description/urdf/hexapod.ros2_control.xacro](../hexapod_description/urdf/hexapod.ros2_control.xacro).

Das Paket ist auf **Desktop und Pi gleichermaßen installiert**.
Welche der beiden yamls geladen wird, hängt vom Launch-Pfad ab:

- **Sim** (Phase 4–6): das `gz_ros2_control`-Plugin in
  `hexapod.ros2_control.xacro` lädt `controllers.yaml` direkt im
  Gazebo-Prozess. Pfad-Auflösung per `$(find hexapod_control)`.
- **HW** (Phase 9 Stage G ff.): `ros2_control_node` aus `real.launch.py`
  lädt `controllers.real.yaml` als `--params-file`-Argument.

Beide yamls definieren dieselben 7 Controller (1× JSB + 6× JTC). Die
Diffs (siehe Top-Comment in `controllers.real.yaml`) reflektieren rein
die Hardware-Realität:

| Setting | controllers.yaml | controllers.real.yaml | Begründung |
|---|---|---|---|
| `update_rate` | 100 Hz | 50 Hz | Plugin-SET_TARGETS-Tickrate per Stage D.5/D.6-Design ist 50 Hz; höhere Rate würde nur USB-Bus saturieren |
| `use_sim_time` | true | false | Wallclock am Pi/Desktop, nicht /clock aus Gazebo |
| `state_interfaces` (per leg_X_controller) | `[position, velocity]` | `[position]` | hexapod_hardware-Plugin exportiert nur position (Echo-State, kein Velocity-Feedback vom Servo2040) |

**TODO Phase 10:** Vel/Accel-Limits (constraints-Block) aus Bench-
Trajektorie ableiten und in `controllers.real.yaml` ergänzen — siehe
TODO-Kommentar im File und `phase_9_stage_f_plan.md`.

## Architektur

```
+-----------------+
| controller_     |   liest beim Start
| manager         | <─────────────── controllers.yaml
+--------+--------+
         │
         │ spawnt + aktiviert
         ▼
   joint_state_broadcaster   (publiziert /joint_states, alle 18 Joints)
   leg_1_controller          (JTC, 3 Joints von Bein 1)
   leg_2_controller          (JTC, 3 Joints von Bein 2)
   ...
   leg_6_controller          (JTC, 3 Joints von Bein 6)
```

Pro Bein ein eigener `JointTrajectoryController` — Vorteile:
- Tripod-Gait mit parallelen Trajektorien (3 schwingen, 3 stützen)
- Beine isoliert testbar
- Hardware-Fehler isolieren sich auf ein Bein

## Wichtige Parameter (aus `controllers.yaml`)

| Parameter | Wert | Bedeutung |
|---|---|---|
| `update_rate` | 100 Hz | Control-Loop des `controller_manager` |
| `use_sim_time` | true | **Phase 4-6**, in Phase 7 auf `false` ändern |
| `command_interfaces` (pro JTC) | `[position]` | passt zu URDF-Deklaration |
| `state_interfaces` (pro JTC) | `[position, velocity]` | passt zu URDF-Deklaration |
| `state_publish_rate` | 50.0 Hz | wie oft jeder JTC seinen State publiziert |
| `action_monitor_rate` | 20.0 Hz | wie oft Action-Goals geprüft werden |

## Topics In / Out

Pro Bein-Controller (Beispiel `leg_1_controller`):

| Topic | Typ | Richtung |
|---|---|---|
| `/leg_1_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | **In** (Goals) |
| `/leg_1_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | **In** (Action) |
| `/leg_1_controller/controller_state` | `control_msgs/msg/JointTrajectoryControllerState` | **Out** (State, 50 Hz) |

JointStateBroadcaster:

| Topic | Typ | Richtung |
|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | **Out** (alle 18 Joints) |

## Aktivierung

Dieses Paket allein lädt die Controller nicht — es liefert nur die
Konfigurations-Datei. Aktivierung erfolgt im
[hexapod_bringup/launch/sim.launch.py](../hexapod_bringup/launch/sim.launch.py)
über die `controller_manager/spawner`-Knoten in einer zweistufigen
`OnProcessExit`-Sequenz.

## Manueller Bewegungstest

Bei laufender Sim:

```bash
# Bein 1 in Stand-Pose fahren
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
    points: [{positions: [0.0, -0.5, 1.0], time_from_start: {sec: 4}}]}'
```

Weitere Beispiele (Multi-Bein, Reset, Stand-Pose) in
[../../docs/phase_4_stage_E_test_commands.md](../../docs/phase_4_stage_E_test_commands.md)
und [../../docs/phase_4_stage_F_test_commands.md](../../docs/phase_4_stage_F_test_commands.md).

## Konzept-Hintergrund

Vollständige Erklärung von `controller_manager`, Lifecycle, CLI-Befehlen
und Phasen-übergreifender Nutzung der YAML in
[../../docs/phase_4_controllers_explained.md](../../docs/phase_4_controllers_explained.md).

## Bekannte Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Spawner exitet mit `controller not found` | Name-Mismatch Spawner-Args ↔ YAML | Joint-Namen-Set-Diff (s. Stufe C) |
| Controller bleibt in `inactive` | Joint-Mismatch URDF ↔ YAML | URDF-Joints `grep` gegen `controllers.yaml` |
| Bewegung passiert nicht | `use_sim_time` falsch oder Topic-Name vertippt | `ros2 param get /controller_manager use_sim_time` |
| `joint_states` leer | JSB nicht aktiv | `ros2 control list_controllers` |
