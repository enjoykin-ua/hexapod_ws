# Phase 4 — Launch-Files und das `sim.launch.py`-Bringup erklärt

> **Wann lesen?** Wenn du in Phase 5/6/7 einen neuen Launch (z. B.
> `gait.launch.py`, `teleop.launch.py`, `real.launch.py`) bauen
> willst und nochmal nachsehen musst, wie ROS2-Launch-Files
> strukturiert sind, was Substitutions sind, oder wie Event-Handler
> funktionieren.
> Für die reine Implementierungsschritt-Liste der Phase 4 ist
> `phase_4_progress.md` der richtige Anlaufpunkt.

---

## 1. Was ist ein Launch-File?

Ein Launch-File ist die **deklarative Beschreibung, wie ein
ROS2-System gestartet wird**. Es beantwortet:

- Welche Knoten (Nodes) sollen laufen?
- Mit welchen Parametern?
- In welcher Reihenfolge?
- Auf welche Konfigurations-Argumente reagieren sie?

ROS2 unterstützt drei Sprachen für Launch-Files: Python, XML, YAML.
**Wir nutzen ausschließlich Python** (siehe `00_conventions.md` §6) —
nur Python erlaubt Conditionals, Schleifen, Substitutions in voller
Form, und das brauchen wir spätestens in Phase 6 (Teleop mit
unterschiedlichen Joystick-Typen).

Konvention: pro Anwendungsfall **ein** Top-Level-Launch:

| Launch | Zweck | Phase |
|---|---|---|
| `display.launch.py` | Nur RViz mit Robotermodell | 2 |
| `hexapod_gazebo/sim.launch.py` | „Plain-Sim ohne Controller" | 3 |
| `hexapod_bringup/sim.launch.py` | **Standard-Sim mit `ros2_control`** | 4 |
| `gait.launch.py` (geplant) | Sim + IK + Gait | 5 |
| `teleop.launch.py` (geplant) | Sim + IK + Gait + Joystick | 6 |
| `real.launch.py` (geplant) | Hardware + Controller | 7 |

Sub-Launches kombiniert man via `IncludeLaunchDescription`
(z. B. `gait.launch.py` includiert `sim.launch.py`).

---

## 2. Aufbau eines ROS2-Python-Launch-Files

Jedes Python-Launch-File hat eine Funktion
`generate_launch_description()`, die ein `LaunchDescription`-Objekt
zurückgibt. Dieses Objekt ist eine **Liste von Actions** plus
deklarierte LaunchArguments und Event-Handler:

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description() -> LaunchDescription:
    my_node = Node(package='foo', executable='bar')
    return LaunchDescription([my_node])
```

Wichtige Action-Klassen, die wir in Phase 4 benutzen:

| Klasse | Zweck | Importiert aus |
|---|---|---|
| `DeclareLaunchArgument` | LaunchArg deklarieren (`urdf:=...`) | `launch.actions` |
| `IncludeLaunchDescription` | Anderen Launch einbinden (z. B. `gz_sim.launch.py`) | `launch.actions` |
| `Node` | ROS2-Knoten starten | `launch_ros.actions` |
| `RegisterEventHandler` | auf Events reagieren | `launch.actions` |
| `OnProcessExit` | konkretes Event: Prozess beendet | `launch.event_handlers` |

Drei Konzept-Schichten innerhalb eines Launch-Files:

```
+----------------------------------------------------------+
| LaunchDescription                                        |
|                                                          |
|  +-----------+  +----------+  +-----------------------+ |
|  | Args      |  | Actions  |  | EventHandler          | |
|  | (decl)    |  | (Nodes,  |  | (on_exit, on_start,   | |
|  |           |  |  Include)|  |  ...)                 | |
|  +-----------+  +----------+  +-----------------------+ |
+----------------------------------------------------------+
```

Bei `ros2 launch <pkg> <file>` werden:
1. Args aus CLI eingelesen (Defaults aus `DeclareLaunchArgument`)
2. Alle Actions aus der Liste gestartet (parallel, sofern keine
   Abhängigkeit)
3. EventHandler bleiben aktiv und feuern bei passendem Event

---

## 3. Substitutions — warum nicht einfach Strings?

**Falsch (funktioniert nicht):**
```python
urdf_path = "/home/enjoykin/hexapod_ws/install/.../hexapod.urdf.xacro"
```
- Hardcoded → bricht auf jedem anderen Rechner
- Wird zur **Modul-Import-Zeit** evaluiert, nicht zur Launch-Zeit

**Richtig:**
```python
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

default_urdf = PathJoinSubstitution([
    FindPackageShare('hexapod_description'), 'urdf', 'hexapod.urdf.xacro',
])
```

**Was Substitutions sind:** Lazy-evaluated Werte, die vom
Launch-System erst zur Laufzeit aufgelöst werden. Vorteile:

- `FindPackageShare('foo')` → resolvt zum installierten Share-Pfad,
  sucht entlang `AMENT_PREFIX_PATH`. Funktioniert auf jedem Rechner.
- `LaunchConfiguration('urdf')` → hält den Wert eines LaunchArgs.
  Wenn der User `ros2 launch ... urdf:=/anderer/pfad.xacro` aufruft,
  greift dieser Pfad — sonst der `default_value`.
- `PathJoinSubstitution([...])` → fügt Substitutions zu einem Pfad
  zusammen, ohne sie vorher in Strings zu konvertieren.

**Faustregel:** Sobald irgendein Pfad/Wert von einem Paket-Pfad
oder LaunchArg abhängt, **niemals** als Plain-String — immer
Substitutions.

Eine besondere Substitution ist `Command`:

```python
from launch.substitutions import Command
robot_description = Command(['xacro ', LaunchConfiguration('urdf')])
```

`Command([...])` ruft beim Launch ein Shell-Kommando auf und nimmt
dessen stdout als Wert. Hier: ruft `xacro <pfad>` auf, kriegt das
generierte URDF als String.

---

## 4. Der `ParameterValue(value_type=str)`-Gotcha

```python
from launch_ros.parameter_descriptions import ParameterValue

robot_description = ParameterValue(
    Command(['xacro ', LaunchConfiguration('urdf')]),
    value_type=str,
)
```

**Warum nicht direkt `Command([...])` als Parameter-Wert?**

Wenn du einen String an einen ROS2-Parameter gibst, versucht
`rclpy` ihn als YAML zu parsen — weil ROS-Parameter normalerweise
typisiert sind und YAML der Default-Format ist. Bei einem URDF-
String beginnt das aber mit `<?xml ...>` und enthält Doppelpunkte,
geschweifte Klammern etc. — der YAML-Parser interpretiert das als
Map, was beim `robot_state_publisher` zu kryptischen Fehlern
führt („expected str, got dict").

`ParameterValue(..., value_type=str)` zwingt den Wert als String
durchzureichen, ohne YAML-Parse-Versuch.

**Faustregel:** Sobald ein Parameter aus einer dynamischen
Substitution (`Command`, `LaunchConfiguration`) einen langen oder
strukturierten String trägt, **immer** in `ParameterValue(value_type=str)`
einwickeln.

---

## 5. `IncludeLaunchDescription` — Sub-Launches einbinden

Statt `gz sim` selbst von Hand zu starten, includieren wir das
offizielle `gz_sim.launch.py` aus `ros_gz_sim`:

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

gz_sim = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        PathJoinSubstitution([
            FindPackageShare('ros_gz_sim'), 'launch', 'gz_sim.launch.py',
        ]),
    ),
    launch_arguments={
        'gz_args': ['-r ', LaunchConfiguration('world')],
        'on_exit_shutdown': 'true',
    }.items(),
)
```

Was passiert:
- `PythonLaunchDescriptionSource(<pfad>)` lädt das andere Launch-File
- `launch_arguments` werden als die `DeclareLaunchArgument`s des
  Sub-Launches durchgereicht (hier: `gz_args` und `on_exit_shutdown`)
- `on_exit_shutdown: true` — wenn `gz sim` beendet wird, beendet
  sich der gesamte Launch (sonst würden RSP, Bridge etc. weiterlaufen)

Das ist die **bevorzugte Methode**, externe Komponenten einzubinden —
besser als mit `ExecuteProcess` von Hand. Vorteil: das Sub-Launch
darf seine eigenen Args, Substitutions und Event-Handler mitbringen,
und ROS-Konventionen bleiben gewahrt.

---

## 6. Spawner-Pattern in `ros2_control`

Der `controller_manager` weiß zwar nach dem Sim-Start, welche
Controller existieren (aus `controllers.yaml`), aber sie sind alle
in `unconfigured`. Aktivieren passiert über das **Spawner-Tool**:

```python
spawn_jsb = Node(
    package='controller_manager',
    executable='spawner',
    name='spawn_joint_state_broadcaster',
    arguments=[
        'joint_state_broadcaster',
        '--controller-manager', '/controller_manager',
    ],
    output='screen',
)
```

Was der Spawner intern tut (siehe auch [phase_4_controllers_explained.md](phase_4_controllers_explained.md) §4):
1. Verbindet sich mit `/controller_manager/load_controller`
2. Verbindet sich mit `/controller_manager/configure_controller`
3. Verbindet sich mit `/controller_manager/switch_controller` (→ `active`)
4. **Exitet** (One-Shot — Prozess endet)

Der Exit-Schritt ist wichtig — er erlaubt uns, mit `OnProcessExit`
auf erfolgreiches Spawning zu reagieren.

**Wichtige Spawner-Argumente:**

| Argument | Zweck |
|---|---|
| `<controller_name>` | Welcher Controller (Name aus YAML) |
| `--controller-manager <pfad>` | Wo läuft der CM (Default `/controller_manager`) |
| `--load-only` | Nur laden + konfigurieren, **nicht** aktivieren — gut für Debug |
| `--inactive` | Laden + konfigurieren, dann auf `inactive` (statt `active`) |
| `--namespace <ns>` | Wenn der CM in einem Namespace läuft |

---

## 7. Event-Handler — Sequenzialisierung von Aktionen

Manche Aktionen dürfen **erst nach** anderen passieren. Bei uns:

```
spawn-Node (One-Shot, exitet wenn Roboter in Sim ist)
            │
            │ OnProcessExit
            ▼
JSB-Spawner (One-Shot, exitet wenn JSB active ist)
            │
            │ OnProcessExit
            ▼
6× Bein-Controller-Spawner (parallel)
```

Code dafür:

```python
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit

# Stage 1: spawn-Exit -> JSB-Spawner
after_spawn_start_jsb = RegisterEventHandler(
    event_handler=OnProcessExit(
        target_action=spawn,        # auf welchen Prozess hören?
        on_exit=[spawn_jsb],         # was triggern, wenn er exitet?
    ),
)

# Stage 2: JSB-Spawner-Exit -> 6 Bein-Spawner
after_jsb_start_leg_controllers = RegisterEventHandler(
    event_handler=OnProcessExit(
        target_action=spawn_jsb,
        on_exit=leg_controller_spawners,  # Liste, alle 6 starten parallel
    ),
)
```

**Wichtig:** Die Spawner-Nodes (`spawn_jsb`, `leg_controller_spawners`)
landen **nicht direkt** in der `LaunchDescription`-Liste — nur die
Event-Handler. Sonst würden sie sofort beim Launch-Start gestartet,
parallel zu allem anderen.

```python
return LaunchDescription([
    declare_urdf, declare_world, declare_spawn_z,  # Args
    gz_sim, robot_state_publisher, spawn, bridge,   # parallel beim Start
    after_spawn_start_jsb,                          # Event-Handler (Spawner sind drin)
    after_jsb_start_leg_controllers,                # Event-Handler (Spawner sind drin)
])
```

**Andere nützliche Event-Handler** (für spätere Phasen):

| Handler | Wann feuert er? |
|---|---|
| `OnProcessExit` | Prozess hat beendet (egal ob Erfolg oder Crash) |
| `OnProcessStart` | Prozess wurde gerade gestartet |
| `OnProcessIO` | Wenn Prozess stdout/stderr eine Zeile schreibt (z. B. „server up" abfangen) |
| `OnShutdown` | Beim Beenden des gesamten Launches |
| `OnExecutionComplete` | Generischer Action-Abschluss |

---

## 8. Dry-Run mit `--print`

```bash
ros2 launch hexapod_bringup sim.launch.py --print
```

Gibt die LaunchDescription als ASCII-Tree aus, ohne tatsächlich
etwas zu starten. Verifiziert:

- Python-Syntax und Imports OK
- LaunchDescription korrekt aufgebaut
- Alle Actions und EventHandler in der erwarteten Hierarchie

Was `--print` **nicht** prüft:

- Tatsächliche Pfad-Existenz (Substitutions sind noch nicht aufgelöst)
- Ob die Sim wirklich startet (kein gz sim wird angerührt)
- Ob die Controller wirklich aktiv werden (kein CM wird angesprochen)

Für die echten Tests: `ros2 launch ...` ohne `--print` und
`ros2 control list_controllers` in einem zweiten Terminal (Stufe E).

---

## 9. Wie wird `sim.launch.py` in späteren Phasen erweitert?

| Phase | Erweiterung |
|---|---|
| Phase 5 | Neuer Launch `gait.launch.py` — includiert `sim.launch.py`, fügt Gait-Engine-Knoten hinzu |
| Phase 6 | `teleop.launch.py` — includiert `gait.launch.py`, fügt Joystick-Knoten + Topic-Mapping hinzu |
| Phase 7 | Neuer Launch `real.launch.py` — **kein** `gz sim`, **kein** Spawn, **kein** Bridge. Stattdessen: `ros2_control_node` als eigener Knoten, lädt das Custom-HardwareInterface (Servo2040). Spawner-Sequenz JSB → 6× JTC bleibt **identisch** |

Pattern: nie das bestehende Launch-File brechen, immer ein neues
darüberlegen, das es includiert. So bleibt `sim.launch.py` für
Phase-4-Tests (manuelle Trajektorien) und `gait.launch.py` für
Phase-5-Tests verfügbar.

---

## 10. Editier- und Debug-Tipps

- **`--print` vor jedem `colcon build`** — fängt Python-Syntax-Fehler ab,
  schneller als ein voller Build-Lauf.
- **Logs pro Knoten:** jeder `Node(...)` hat `output='screen'` →
  stdout/stderr landen im selben Terminal. Für detaillierte Logs:
  `--log-level <node>:=debug`.
- **Wenn ein Knoten beim Start crasht und dich rauswirft:**
  `Node(... emulate_tty=True, output={'both': 'log'})` — schreibt
  Logs nach `~/.ros/log/<launch>/<node>.log` statt auf den Screen.
  Dann nach Crash dort nachschauen.
- **Wenn ein Spawner hängt:** entweder läuft der CM noch nicht (→
  Reihenfolgen-Problem, EventHandler einbauen) oder Controller-Name
  passt nicht zur YAML (→ `ros2 control list_controllers` zeigt nur
  registrierte Namen).
- **`ros2 launch --show-arguments hexapod_bringup sim.launch.py`** —
  listet alle verfügbaren LaunchArgs mit ihren Defaults und
  Beschreibungen. Nützlich, wenn du später vergessen hast, was
  eigentlich überschrieben werden kann.

---

## 11. Verwandte Dateien im Workspace

- [hexapod_bringup/launch/sim.launch.py](../src/hexapod_bringup/launch/sim.launch.py) —
  diese Datei (Standard-Sim ab Phase 4)
- [hexapod_gazebo/launch/sim.launch.py](../src/hexapod_gazebo/launch/sim.launch.py) —
  „Plain-Sim ohne Controller" (Phase-3-Variante, bewusst behalten)
- [hexapod_description/urdf/hexapod.ros2_control.xacro](../src/hexapod_description/urdf/hexapod.ros2_control.xacro) —
  ros2_control-Block + `gz_ros2_control`-Plugin (Stufe B)
- [hexapod_control/config/controllers.yaml](../src/hexapod_control/config/controllers.yaml) —
  Controller-Definitionen (Stufe C)
- [phase_4_controllers_explained.md](phase_4_controllers_explained.md) —
  Konzept-Hintergrund zu `controllers.yaml` und Lifecycle
- [phase_4_progress.md](phase_4_progress.md) — Fortschritts-Tracking pro Stufe
