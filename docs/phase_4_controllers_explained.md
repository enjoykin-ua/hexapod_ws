# Phase 4 — `controllers.yaml` und das `ros2_control`-Ökosystem erklärt

> **Wann lesen?** Wenn du in Phase 5/6/7 nochmal nachschlagen willst:
> Was macht der `controller_manager`? Wozu ist `controllers.yaml`?
> Welche `ros2 control`-CLI-Befehle gibt es?
> Für die reine Implementierungsschritt-Liste der Phase 4 ist
> `phase_4_progress.md` der richtige Anlaufpunkt.

---

## 1. Die drei Konfigurations-Schichten in `ros2_control`

`ros2_control` trennt strikt zwischen Hardware-Sicht, Software-Sicht und
Lade-Reihenfolge. Wenn du diese drei Ebenen einmal sauber im Kopf hast,
wird der Rest der Phase intuitiv:

| Ebene | Datei / Mechanismus | Beantwortet die Frage |
|---|---|---|
| **Hardware** | `<ros2_control>`-Block im URDF (`hexapod.ros2_control.xacro`) | „Welche Joints gibt es, welche Command-/State-Interfaces hat jeder?" |
| **Software** | `controllers.yaml` (`hexapod_control/config/`) | „Welche Controller existieren, wie heißen sie, welche Joints abonnieren sie, mit welchen Raten?" |
| **Lade-Sequenz** | `spawner`-Knoten im Launch-File (`hexapod_bringup/launch/sim.launch.py`) | „In welcher Reihenfolge werden die Controller aktiviert?" |

`controllers.yaml` ist also genau die mittlere Ebene. Sie sagt **nichts**
über Hardware aus (das macht der URDF-Block), und **nichts** über
Reihenfolge (das macht das Launch-File).

---

## 2. Was steht konkret in `controllers.yaml`?

Zwei Schichten innerhalb der Datei:

### Schicht A — `controller_manager:`

Die **Typdeklaration**. Beantwortet dem `controller_manager` beim Start:
*„Welche Controller soll ich überhaupt kennen?"*

```yaml
controller_manager:
  ros__parameters:
    update_rate: 100  # Hz - wie oft tickt der Control-Loop?
    use_sim_time: true

    joint_state_broadcaster:
      type: joint_state_broadcaster/JointStateBroadcaster

    leg_1_controller:
      type: joint_trajectory_controller/JointTrajectoryController
    # ... leg_2 bis leg_6
```

Wichtig: Das ist **nur die Liste der Namen + Typen**. Der eigentliche
Controller ist hier noch nicht konfiguriert.

### Schicht B — `<controller_name>:` als Top-Level-Keys

Die **Pro-Controller-Konfiguration**. Beantwortet jedem einzelnen Controller:
*„Was ist meine Aufgabe?"*

```yaml
leg_1_controller:
  ros__parameters:
    joints:
      - leg_1_coxa_joint
      - leg_1_femur_joint
      - leg_1_tibia_joint
    command_interfaces: [position]
    state_interfaces:   [position, velocity]
    state_publish_rate: 50.0
    action_monitor_rate: 20.0
```

Diese Schicht-B-Keys liegen **auf gleicher Höhe** mit `controller_manager:` —
das ist ROS2-Standard für Per-Knoten-Parameter (jeder ROS-Knoten kriegt
sein eigenes Top-Level-Mapping).

---

## 3. Wer liest die Datei und wann?

```
                hexapod.ros2_control.xacro (URDF, Stufe B)
                          │
                          │ <plugin>...controllers.yaml</plugin>
                          ▼
   gz sim ─► gz_ros2_control-Plugin ─► controller_manager
                                            │
                                            │  liest Datei beim Start
                                            ▼
                                    +-------------------+
                                    | controllers.yaml  |
                                    +-------------------+
                                            │
                                            │  spawnt Controller (Stufe D)
                                            ▼
                                    JSB + 6× JTC
```

Konkret beim Aufruf von `ros2 launch hexapod_bringup sim.launch.py` (Stufe E):

1. `gz sim` startet die Sim-Engine.
2. Hexapod wird in die Sim gespawnt → das `<gazebo>`-Plugin im URDF
   (`gz_ros2_control-system`) wird vom Sim-Prozess geladen.
3. Das Plugin **embedded** den `controller_manager` direkt in den
   Sim-Prozess (kein eigener ROS-Node!) und übergibt ihm den Pfad aus
   `$(find hexapod_control)/config/controllers.yaml`.
4. Der `controller_manager` liest die YAML, **deklariert** alle 7 Controller
   intern als „bekannt" — sie sind aber noch nicht aktiv.
5. Der `spawner` aus Stufe D triggert dann pro Controller die State-Machine
   `unconfigured → inactive → active`.

In Phase 7 ändert sich nur Schritt 1-3: kein `gz sim`, kein Plugin —
stattdessen läuft `controller_manager` als **eigener ROS-Node** auf dem Pi
und bekommt die YAML per Launch-Argument (oder eine `controllers.real.yaml`).
Schritte 4-5 sind identisch. Genau das ist der Sinn der Hardware-Abstraktion.

---

## 4. Lifecycle eines Controllers (das wichtigste Konzept)

Jeder Controller in ros2_control durchläuft eine State-Machine:

```
   unconfigured ──configure──► inactive ──activate──► active
       ▲                          │                     │
       └────cleanup───────────────┘                     │
                                  ▲                     │
                                  └──── deactivate ─────┘
```

| State | Bedeutung |
|---|---|
| `unconfigured` | Controller ist instanziiert, kennt aber noch keine Joints/Interfaces. |
| `inactive` | Konfiguriert (kennt seine YAML-Sektion), **claimed aber keine** Hardware-Interfaces — `update()` wird nicht aufgerufen. |
| `active` | Hat Hardware-Interfaces gegrabbt, **`update()` läuft** mit `update_rate` aus der YAML — sendet Commands, liest States. |

**Wichtige Konsequenz:** Ein Controller in der YAML ≠ aktiver Controller.
Die YAML *deklariert* nur — erst der `spawner` (Stufe D) triggert den
Übergang nach `active`. Das ist auch, warum die Reihenfolge der Spawner
in Stufe D wichtig ist: `joint_state_broadcaster` zuerst aktivieren,
sonst hat keiner Joint-States zum Lesen.

**Warum dieses Lifecycle-Konzept?** ros2_control will erlauben, einen
Controller im laufenden System auszutauschen, ohne Sim/HW neu zu starten.
Beispiel Phase 5: Custom-Controller fertig → JTC deaktivieren, Custom
laden, aktivieren. Roboter steht währenddessen still, aber alles bleibt
oben.

---

## 5. Wie spreche ich die Datei zur Laufzeit an?

Sobald der Sim läuft, gibt es eine ganze Reihe `ros2 control`-CLI-Befehle,
die direkt mit dem `controller_manager` (und damit indirekt mit
`controllers.yaml`) reden:

```bash
# Welche Controller kennt der CM, in welchem State sind sie?
ros2 control list_controllers

# Welche Hardware-Interfaces gibt es, welche sind claimed?
ros2 control list_hardware_interfaces

# Controller deaktivieren (z.B. Bein 3 freigeben für Custom-Test)
ros2 control set_controller_state leg_3_controller inactive

# Controller wieder aktivieren
ros2 control set_controller_state leg_3_controller active

# Controller komplett austauschen (z.B. JTC durch Custom-Controller)
ros2 control unload_controller leg_3_controller
ros2 control load_controller leg_3_controller
ros2 control set_controller_state leg_3_controller active
```

Außerdem sind alle `ros__parameters` aus der YAML zur Laufzeit als
**ROS-Parameter** abrufbar/setzbar:

```bash
# Was ist aktuell der state_publish_rate von leg_1_controller?
ros2 param get /leg_1_controller state_publish_rate

# Live-Anpassung (greift sofort)
ros2 param set /leg_1_controller state_publish_rate 100.0

# Komplette Parameter-Liste eines Controllers
ros2 param list /leg_1_controller
```

**Wichtig:** Manche Parameter (z.B. `joints`-Liste) sind als „read-only"
markiert — die kann man nur in der YAML ändern und neu laden.
Tuning-Werte wie `state_publish_rate` und PID-Gains sind live-änderbar.

---

## 6. Wie gebe ich Bewegungs-Befehle an einen aktiven Controller?

Jeder `JointTrajectoryController` hört auf einem **Topic** und einer
**Action** (Topic-Variante reicht für die meisten Fälle):

```bash
# Topic-Variante (one-shot, kein Goal-Tracking)
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
    points: [{positions: [0.3, -0.5, 1.0], time_from_start: {sec: 2}}]}'

# Action-Variante (bekommt Result-Feedback, Cancel etc.)
ros2 action send_goal /leg_1_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory \
  '{trajectory: {joint_names: [...], points: [...]}}'
```

Was hier passiert:
1. Message kommt am `/leg_1_controller/joint_trajectory`-Topic an.
2. JTC validiert: Joint-Namen passen zu `joints:`-Liste in YAML?
3. JTC interpoliert zwischen aktueller Pose und Ziel-Punkt(en) — bei
   einem einzelnen Punkt linear in `time_from_start` Sekunden.
4. Pro Tick (100 Hz, aus YAML) wird die interpolierte Position als
   Command-Interface-Wert geschrieben.
5. `gz_ros2_control` greift den Wert ab und setzt ihn als Joint-Position
   in Gazebo.

---

## 7. Wofür diese Datei in späteren Phasen?

| Phase | Nutzung von `controllers.yaml` |
|---|---|
| Phase 4 (jetzt) | Bewegungstest auf einem Bein via `ros2 topic pub /leg_N_controller/joint_trajectory ...`. |
| Phase 5 (IK + Gait) | Die Gait-Engine publisht `JointTrajectory`-Messages an die 6 Bein-Topics. Die YAML ändert sich dabei **nicht**. |
| Phase 6 (Teleop) | Joystick → Teleop-Knoten → Gait-Engine → JTCs. YAML weiterhin unverändert. |
| Phase 7 (Hardware) | YAML wird auf den Pi kopiert. `use_sim_time` auf `false` (per Launch-Override oder zweite YAML). Sonst identisch. |

Das ist der gesamte Witz von ros2_control: **die YAML ist das einzige
Stück Konfiguration, das über alle Phasen stabil bleibt.** Die Ebenen
darüber (IK, Gait, Teleop) und darunter (HardwareInterface-Plugin)
können sich austauschen, der Vertrag in der Mitte bleibt.

---

## 8. Editier- und Debug-Tipps

- **YAML geändert → Sim neu starten.** Es gibt kein
  `controllers.yaml reload` zur Laufzeit. (Einzelne Parameter ja,
  Struktur nein. Wenn du aber nur ein Parameter ändern willst, geht
  `ros2 param set` live.)
- **Joint-Name-Tippfehler in der YAML** → Controller bleibt in `inactive`,
  Logs sagen `joint X not found`. In Stufe C habe ich einen Set-Diff
  als Cross-Check gegen das URDF gebaut — dieses Pattern lohnt sich
  als Pre-Commit-Hook in Phase 5+.
- **`ros2 control list_controllers` zeigt einen Controller in `unconfigured`**
  → meist Spawner-Reihenfolgen-Problem (Stufe D). Mit `--load-only`
  beim Spawner kann man Controller laden ohne zu aktivieren — gut für
  Debugging.
- **`/controller_manager`-Topic-Namespace:** Alle CM-CLI-Befehle haben
  optional `--controller-manager /controller_manager` (Default-Pfad).
  Wenn du mehrere CM-Instanzen laufen hast (Sim + echte HW gleichzeitig
  zum Vergleich), wird das wichtig.
- **Logs lesen:** Wenn beim Sim-Start was hängt, `ros2 launch ... --log-level
  controller_manager:=debug`. Der CM ist sehr gesprächig im Debug-Mode
  und zeigt genau, an welchem Lifecycle-Übergang er hängenbleibt.

---

## 9. Verwandte Dateien im Workspace

- [hexapod.ros2_control.xacro](../src/hexapod_description/urdf/hexapod.ros2_control.xacro) —
  URDF-Block, deklariert die 18 Hardware-Interfaces und lädt das
  `gz_ros2_control`-Plugin
- [controllers.yaml](../src/hexapod_control/config/controllers.yaml) —
  diese Datei
- `sim.launch.py` (kommt in Stufe D) —
  startet `gz sim`, spawnt den Roboter, ruft die `spawner`-Knoten in
  korrekter Reihenfolge auf
- [phase_4_ros2_control.md](phase_4_ros2_control.md) — Stufenplan / Phasen-Beschreibung
- [phase_4_progress.md](phase_4_progress.md) — Fortschritts-Tracking pro Stufe
