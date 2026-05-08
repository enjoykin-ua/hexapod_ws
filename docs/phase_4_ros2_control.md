# Phase 4 — `ros2_control` Integration

**Dauer-Schätzung:** 3–5 Tage
**Maschine:** nur Desktop
**Vorbedingung:** Phase 3 abgeschlossen, Roboter steht in Gazebo

---

## Ziel

Joints werden über `ros2_control`-Controller bewegt. Du kannst per
`ros2 topic pub` einen Joint-Trajectory-Befehl absetzen, und der
entsprechende Joint im Gazebo-Modell folgt. Damit ist die
**Hardware-Abstraktion** etabliert — derselbe Controller-Stack wird in
Phase 7 mit der echten Hardware funktionieren, ohne dass IK oder Gait
geändert werden müssen.

---

## Done-Kriterien

1. Paket `hexapod_control` baut.
2. Beim Start von `sim.launch.py` (jetzt erweitert) sind aktiv:
   - `joint_state_broadcaster` → publiziert `/joint_states`
   - 6× `joint_trajectory_controller` (einer pro Bein) — empfangen
     Trajektorien-Goals
3. `ros2 control list_controllers` zeigt alle Controller im Status `active`.
4. `ros2 control list_hardware_interfaces` zeigt alle 18 Position-Command-
   und 18 Position-State-Interfaces.
5. Ein manuell publizierter Trajectory-Goal auf
   `/leg_1_controller/joint_trajectory` bewegt die drei Joints von Bein 1
   im Gazebo-Modell sichtbar.
6. `/joint_states` zeigt aktuelle Positionen aller 18 Joints.

---

## Architektur-Konzept

```
+----------------+     +-------------------+     +----------------+
|  Gait (Phase5) | --> | JointTrajectory   | --> | gz_ros2_control|
|  Phase 6 Tele  |     | Controller        |     | (Plugin in Sim)|
+----------------+     +-------------------+     +-------+--------+
                                                          |
                                                          v
                                                 +-----------------+
                                                 | Gazebo-Joint    |
                                                 +-----------------+

In Phase 7 wird das Plugin (gz_ros2_control) durch ein Custom-
HardwareInterface ersetzt, das die Servo2040 ansteuert.
Alles oberhalb bleibt unverändert.
```

---

## Paket anlegen

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 \
  hexapod_control
```

Verzeichnis:

```
hexapod_control/
├── CMakeLists.txt
├── package.xml
├── README.md
├── config/
│   └── controllers.yaml
└── launch/
    └── (kein eigenes — Bringup integriert es)
```

`package.xml`-Dependencies (`<exec_depend>`): `ros2_control`,
`ros2_controllers`, `controller_manager`.

---

## URDF um `<ros2_control>`-Block erweitern

In `hexapod_description/urdf/hexapod.urdf.xacro` einen `<ros2_control>`-
Block hinzufügen, der für **alle 18 Joints** ein Position-Command-
und ein Position-State-Interface definiert.

Skizze (gekürzt, Macro-Aufruf pro Joint):

```xml
<ros2_control name="GazeboSimSystem" type="system">
  <hardware>
    <plugin>gz_ros2_control/GazeboSimSystem</plugin>
  </hardware>
  <xacro:macro name="joint_iface" params="name">
    <joint name="${name}">
      <command_interface name="position">
        <param name="min">-1.57</param>
        <param name="max"> 1.57</param>
      </command_interface>
      <state_interface name="position"/>
      <state_interface name="velocity"/>
    </joint>
  </xacro:macro>

  <xacro:joint_iface name="leg_1_coxa_joint"/>
  <xacro:joint_iface name="leg_1_femur_joint"/>
  <xacro:joint_iface name="leg_1_tibia_joint"/>
  <!-- … bis leg_6_tibia_joint -->
</ros2_control>
```

Plus das Gazebo-Plugin, das `controller_manager` lädt:

```xml
<gazebo>
  <plugin filename="gz_ros2_control-system"
          name="gz_ros2_control::GazeboSimROS2ControlPlugin">
    <parameters>$(find hexapod_control)/config/controllers.yaml</parameters>
  </plugin>
</gazebo>
```

> **Pfad-Substitution `$(find ...)`:** Funktioniert in URDF, weil das
> Xacro-Tool das vor dem Spawn auflöst — vorausgesetzt, das Paket ist
> gebaut und gesourct.

---

## Controller-Konfiguration `controllers.yaml`

```yaml
controller_manager:
  ros__parameters:
    update_rate: 100  # Hz
    use_sim_time: true

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

    leg_1_controller:
      type: joint_trajectory_controller/JointTrajectoryController
    leg_2_controller:
      type: joint_trajectory_controller/JointTrajectoryController
    # ... bis leg_6_controller

leg_1_controller:
  ros__parameters:
    joints:
      - leg_1_coxa_joint
      - leg_1_femur_joint
      - leg_1_tibia_joint
    command_interfaces:
      - position
    state_interfaces:
      - position
      - velocity
    state_publish_rate: 50.0
    action_monitor_rate: 20.0

# Analog für leg_2..leg_6
```

> **Designentscheidung:** Ein Controller pro Bein (statt einem für alle 18
> Joints). Vorteile:
> - Trajektorien können pro Bein parallel laufen (wichtig für Tripod-Gait)
> - Einzelne Beine isoliert testbar
> - Bei Hardware-Fehler fällt nicht der ganze Roboter aus
>
> Nachteil: 6× so viel YAML. Akzeptabel.

---

## Bringup-Paket

Erzeuge **jetzt** auch das Bringup-Paket, das ab Phase 4 alle Launch-
Files orchestriert:

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 \
  hexapod_bringup
```

`hexapod_bringup/launch/sim.launch.py` ersetzt jetzt das aus Phase 3 und
ergänzt den Controller-Start:

```python
# Pseudocode
# 1. xacro → robot_description
# 2. Gazebo starten (wie Phase 3)
# 3. Roboter spawnen (wie Phase 3)
# 4. robot_state_publisher (wie Phase 3)
# 5. NEU: controller-spawner-Knoten:
#    - joint_state_broadcaster
#    - leg_1_controller .. leg_6_controller
```

Die Controller werden mit dem `controller_manager`-Spawner aktiviert:

```python
spawn_jsb = Node(
    package='controller_manager',
    executable='spawner',
    arguments=['joint_state_broadcaster',
               '--controller-manager', '/controller_manager']
)

# pro Bein analog
```

> Wichtig: **Reihenfolge.** Erst `joint_state_broadcaster`, dann die
> Trajectory-Controller. Mit `RegisterEventHandler` + `OnProcessExit`
> sequenzialisieren.

---

## Inbetriebnahme

```bash
colcon build
source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

In zweitem Terminal:

```bash
ros2 control list_controllers
```

Erwartung:

```
joint_state_broadcaster   joint_state_broadcaster/JointStateBroadcaster   active
leg_1_controller          joint_trajectory_controller/JointTrajectoryController  active
leg_2_controller          ...                                                    active
... bis leg_6_controller
```

```bash
ros2 control list_hardware_interfaces
```

Erwartung: 18 Position-Command-Interfaces (`available command interfaces`)
und 18 Position-State-Interfaces.

---

## Manueller Bewegungstest

`ros2 topic pub` für eine Trajektorie auf Bein 1:

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
    points: [{positions: [0.3, -0.5, 1.0], time_from_start: {sec: 2}}]}'
```

Erwartung: Bein 1 fährt in Gazebo binnen 2 s in die Zielposition.

> **Wenn nichts passiert:** Logs lesen. Häufig fehlt `use_sim_time: true`
> beim `controller_manager`, oder der Controller-Spawner ist zu früh
> gestartet (vor Gazebo).

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `controller_manager` startet nicht | Plugin-Pfad falsch im URDF | `$(find hexapod_control)`-Substitution prüfen |
| Controller bleiben in `inactive` | Spawner-Reihenfolge / Timing | Event-Handler nutzen, sequenziell |
| Joints reagieren nicht auf Topic | Falscher Topic-Name oder Joint-Name | `ros2 topic list`, `ros2 topic info` |
| `joint_states` leer | `joint_state_broadcaster` nicht aktiv | als ersten Controller spawnen |
| Bewegung ruckelt | `update_rate` zu niedrig | auf 100–200 Hz erhöhen |
| Joints überschießen / oszillieren | Trajektorie zu schnell / Limits zu hoch | `time_from_start` erhöhen, `effort/velocity` Joint-Limits prüfen |
| Logs voll mit `clock` warnings | `use_sim_time` nicht überall gesetzt | bei jedem Knoten als Parameter |

---

## Was in dieser Phase **NICHT** gemacht wird

- Keine IK
- Keine Gangsteuerung
- Kein Teleop
- Kein Custom-Controller (das käme erst, wenn `JointTrajectoryController`
  als zu langsam/unflexibel erwiesen wird — ist es vermutlich nicht)

---

## Phasenabschluss

- [ ] Alle 6 Done-Kriterien erfüllt
- [ ] Bewegungstest auf mindestens zwei Beinen erfolgreich
- [ ] README in `hexapod_control/` und `hexapod_bringup/` aktuell
- [ ] Timeshift-Snapshot `phase_4_done`
- [ ] Git-Commit + Tag `phase-4-done`
- [ ] `PHASE.md` auf Phase 5 aktualisiert
