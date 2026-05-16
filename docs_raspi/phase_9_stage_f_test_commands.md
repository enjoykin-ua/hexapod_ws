# Phase 9 — Stufe F — Test-Anleitung

**Was geprüft wird:** Das URDF baut + parsed in beiden Modi (`use_sim:=true`
für Gazebo, `use_sim:=false` für `hexapod_hardware`-Plugin),
`controllers.real.yaml` ist syntaktisch valide und matched den Plugin-
Vertrag (nur position-state), und der Sim-Pfad (Phase 4–6) bleibt voll
funktional regression-frei (RViz-Modell + Roboter steht + Tripod-Walking
mit PS4).

**Was NICHT in F in CI geprüft wird:**
- echter Servo2040-Anschluss (Stage H)
- volle `real.launch.py` mit Spawner-Skripten (Stage G — F-T9 ist nur ein
  vorgezogener `ros2_control_node`-Smoke)
- launch_testing-Suite (überzogen für die XML-Refactor-Frage)

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_description hexapod_control hexapod_hardware
source install/setup.bash
```

> **In JEDEM neuen Terminal das du für F-T8 / F-T9 / F-T10 öffnest, beide Source-Zeilen ausführen** — sonst sieht ROS2 die Pakete + Plugins nicht und die Launch-Files scheitern mit „package not found" oder leeren `ros2 control list_*`-Outputs. Die Source-Zeilen sind unten in jedem Terminal-Block nochmal mit aufgeführt.

---

## Test F-T1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_description hexapod_control hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 3 packages finished`, kein `stderr`-Block, keine
`warning:`. `controllers.real.yaml` wird als Symlink unter
`install/hexapod_control/share/hexapod_control/config/` installiert.

---

## Test F-T2 — Sim-URDF byte-equal zum Pre-F-Stand (Regression-Check)

```bash
xacro ~/hexapod_ws/src/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/sim_urdf_post_F.xml
# Pre-F-Snapshot wurde vor dem Refactor genommen und liegt unter /tmp/sim_urdf_pre_F.xml
diff /tmp/sim_urdf_pre_F.xml /tmp/sim_urdf_post_F.xml
```

**Erwartung:** Diff zeigt ausschließlich Edits in **XML-Kommentar-Blöcken**
(Header der ros2_control-Sektion, Gazebo-Block-Doku, Limits-Kommentar) —
keine Element-, Attribut- oder Wert-Diffs. Strukturelle Gleichheit
verifizierbar mit:

```bash
python3 -c "
import re
strip = lambda p: re.sub(r'\s+', ' ', re.sub(r'<!--.*?-->', '', open(p).read(), flags=re.DOTALL)).strip()
print('IDENTICAL' if strip('/tmp/sim_urdf_pre_F.xml') == strip('/tmp/sim_urdf_post_F.xml') else 'DIFFERS')
"
```

**Erwartung:** `IDENTICAL`.

---

## Test F-T3 — HW-URDF strukturell korrekt

```bash
xacro ~/hexapod_ws/src/hexapod_description/urdf/hexapod.urdf.xacro use_sim:=false > /tmp/hw_urdf_F.xml
grep -A 4 "<hardware>" /tmp/hw_urdf_F.xml | head -10
```

**Erwartung:**
```
<hardware>
  <plugin>hexapod_hardware/HexapodSystemHardware</plugin>
  <param name="serial_port">/dev/ttyACM0</param>
  <param name="calibration_file">/home/enjoykin/hexapod_ws/install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml</param>
  <param name="loopback_mode">false</param>
```

Strukturelle Counts:
```bash
echo "position-states: $(grep -c 'state_interface name="position"' /tmp/hw_urdf_F.xml)"
echo "velocity-states: $(grep -c 'state_interface name="velocity"' /tmp/hw_urdf_F.xml || true)"
echo "gazebo-blocks  : $(grep -c '<gazebo>' /tmp/hw_urdf_F.xml || true)"
```

**Erwartung:** `position-states: 18`, `velocity-states: 0`, `gazebo-blocks: 0`.

---

## Test F-T4 — Args-Override durchgereicht

```bash
xacro ~/hexapod_ws/src/hexapod_description/urdf/hexapod.urdf.xacro \
    use_sim:=false loopback_mode:=true serial_port:=/dev/null \
    > /tmp/hw_urdf_F_overrides.xml
grep -A 4 "<hardware>" /tmp/hw_urdf_F_overrides.xml | head -10
```

**Erwartung:** `serial_port=/dev/null` und `loopback_mode=true` im
Plugin-Block, Rest unverändert.

---

## Test F-T5 — `check_urdf` für beide Modi

```bash
check_urdf /tmp/sim_urdf_post_F.xml | head -3
echo "---"
check_urdf /tmp/hw_urdf_F.xml | head -3
```

**Erwartung beide:** `robot name is: hexapod` + `Successfully Parsed XML`
+ `root Link: base_link has 6 child(ren)`.

---

## Test F-T6 — `controllers.real.yaml` syntaktisch valide

```bash
python3 -c "
import yaml
d = yaml.safe_load(open('~/hexapod_ws/src/hexapod_control/config/controllers.real.yaml'.replace('~', '$HOME')))
cm = d['controller_manager']['ros__parameters']
assert cm['update_rate'] == 50, cm['update_rate']
assert cm['use_sim_time'] is False, cm['use_sim_time']
for n in range(1, 7):
    leg = d[f'leg_{n}_controller']['ros__parameters']
    assert leg['state_interfaces'] == ['position'], leg['state_interfaces']
    assert leg['command_interfaces'] == ['position']
print('YAML OK')
"
```

**Erwartung:** `YAML OK`.

---

## Test F-T7 — `hexapod_hardware`-Tests weiter alle grün (Stage-A–E-Regression)

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --test-result-base build/hexapod_hardware --verbose | tail -3
```

**Erwartung:** `Summary: 208 tests, 0 errors, 0 failures, 20 skipped`
(unverändert vs Stage-E-Endstand).

---

## Test F-T8 — Sim-Pfad voll funktional: Gazebo + RViz + Roboter steht

**Was hier wirklich verifiziert wird:** der URDF-Refactor hat keine
visuellen / tf2- / mesh-Pfad-Regressions eingeführt. Reines „URDF parsed
sauber" (F-T2/T5) reicht NICHT — subtile Bugs (kaputte Material-Referenz,
fehlende package://-Auflösung, falsch verkettete tf2-Frames) zeigen sich
erst bei der Visualisierung.

### F-T8a — sim.launch.py + Stand-Verifikation

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

**Erwartung:**
- Gazebo-Fenster öffnet, Hexapod-Modell sichtbar (orange Body, 6 Beine
  symmetrisch montiert)
- Im Log: kein `[ERROR]`, kein `[FATAL]`. Erwartete `[WARN]`s aus früheren
  Phasen sind OK (KDL-Root-Inertia o.ä.).
- Roboter steht **stabil** (kein Wegrollen, kein Umkippen)
- Nach ~3 Sekunden: alle 6 JTCs + JSB sind active. Verifizieren in
  Terminal 2:

**Terminal 2:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 control list_controllers
```

**Erwartung:** 7 Zeilen mit `active`:
```
joint_state_broadcaster   joint_state_broadcaster/JointStateBroadcaster   active
leg_1_controller          ...JointTrajectoryController                    active
leg_2_controller          ...                                             active
leg_3_controller          ...                                             active
leg_4_controller          ...                                             active
leg_5_controller          ...                                             active
leg_6_controller          ...                                             active
```

### F-T8b — RViz-Visualisierung

**Terminal 3** (während sim.launch.py noch läuft):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
rviz2 -d ~/hexapod_ws/src/hexapod_description/config/view.rviz
```

**Erwartung:**
- RViz-Fenster öffnet
- Hexapod-Modell ist sichtbar (RobotModel-Display gegen `/robot_description`)
- TF-Display zeigt alle 6 Bein-Frames (`leg_<n>_{coxa,femur,tibia,foot}_link`)
- **Kein roter Status-Marker** im Display-Tree (Status-Spalte = grün/OK)
- Modell bewegt sich live mit den Joint-States (während Stand-Pose: minimal)

Alternative URDF-only-Variante (ohne Sim, nur RSP + JSP-GUI + RViz):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_description display.launch.py
```

→ Gleiche Erwartung an Modell-Sichtbarkeit; mit JSP-GUI-Slidern kann man
manuell Joints bewegen und sehen ob alle Beine korrekt animiert werden.

---

## Test F-T9 — ⏭️ verschoben nach Stage G

**Status:** F-T9 wurde am 2026-05-16 nach Stage G verschoben. Begründung:
in der Implementations-Phase kam raus, dass F-T9 inhaltlich genau das
abdeckt was Stage G's Done-Kriterien 1+2 sind („real.launch.py startet
sauber" + „list_controllers zeigt JSB + 6× JTC active"). Ein
Wegwerf-Launch-File in `/tmp/` für F-T9 zu schreiben + danach in Stage G
denselben Inhalt nochmal final zu schreiben wäre Doppel-Arbeit.

**Vorlage in `/tmp/f_t9_smoke.launch.py`** ist bereits zu ~95 % fertig
(RSP + ros2_control_node + JSB-Spawner + 6 leg-JTC-Spawner mit
OnProcessExit-Chain). Stage G fügt nur hinzu:
- Launch-Args (`loopback_mode:=true|false`, `serial_port:=...`)
- Finalen Ort (`hexapod_bringup/launch/real.launch.py`)
- README-Doku-Block

Plan-Doku-Korrektur: F-Q5-Antwort revidiert (A → B nach Implementations-
Realität). Stage F endet damit nach den CI-grünen F-T1–F-T7 + den
User-Smokes F-T8 (Sim + RViz + Stand) + F-T10 (End-to-End Walking).

---

## ~~Original-F-T9-Block (Referenz für Stage G)~~

Was in Stage G aufgegriffen wird (zur Wiedervorlage):

**Was hier verifiziert wird:** Plugin lädt mit der HW-URDF + real.yaml in
einem echten controller_manager (Stage-G/H-Setup-Smoke ohne echten
Servo2040).

> **Warum kein direkter `ros2 run robot_state_publisher -p robot_description:="$(xacro ...)"`?**
> Das xacro-Output enthält `=`, `<`, `>` und Newlines, die der `rcl`-
> Argument-Parser als seine eigene Syntax fehlinterpretiert (Fehler
> *„Couldn't parse parameter override rule"*). Der saubere Weg ist eine
> Launch-Datei mit `Command(['xacro ', ...])` + `ParameterValue`. Stage G
> baut diese als finale `real.launch.py` in `hexapod_bringup/launch/`;
> für F-T9 nutzen wir einen ad-hoc-Smoke-Launch in `/tmp/`.

### Schritt 1 — Ad-hoc Smoke-Launch in /tmp erstellen

Der Launch-File ist bereits angelegt unter `/tmp/f_t9_smoke.launch.py`.
Falls die Datei fehlt (frisches `/tmp` nach Reboot), neu schreiben mit
diesem Heredoc-Block (inhaltlich identisch zur Datei):

```bash
cat > /tmp/f_t9_smoke.launch.py <<'PYEOF'
from launch import LaunchDescription
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_desc = FindPackageShare('hexapod_description')
    pkg_ctrl = FindPackageShare('hexapod_control')
    xacro_path = PathJoinSubstitution([pkg_desc, 'urdf', 'hexapod.urdf.xacro'])
    real_yaml = PathJoinSubstitution([pkg_ctrl, 'config', 'controllers.real.yaml'])
    robot_description = {
        'robot_description': ParameterValue(
            Command(['xacro ', xacro_path, ' use_sim:=false', ' loopback_mode:=true']),
            value_type=str,
        ),
        'use_sim_time': False,
    }
    rsp = Node(package='robot_state_publisher', executable='robot_state_publisher',
               name='robot_state_publisher', output='screen', parameters=[robot_description])
    cm = Node(package='controller_manager', executable='ros2_control_node',
              name='controller_manager', output='screen',
              parameters=[robot_description, real_yaml])
    spawn_jsb = Node(package='controller_manager', executable='spawner',
                     name='spawn_joint_state_broadcaster',
                     arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
                     output='screen')
    leg_spawners = [
        Node(package='controller_manager', executable='spawner',
             name=f'spawn_leg_{i}_controller',
             arguments=[f'leg_{i}_controller', '--controller-manager', '/controller_manager'],
             output='screen')
        for i in range(1, 7)
    ]
    return LaunchDescription([
        rsp, cm, spawn_jsb,
        RegisterEventHandler(event_handler=OnProcessExit(
            target_action=spawn_jsb, on_exit=leg_spawners)),
    ])
PYEOF
```

### Schritt 2 — Smoke-Launch starten

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch /tmp/f_t9_smoke.launch.py
```

**Erwartung:** im Log siehst du in dieser Reihenfolge:
```
[robot_state_publisher]: got segment base_link ...                          ← RSP lädt URDF
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_init ...              ← Plugin lädt
[ros2_control_node-2] [INFO]: ... loopback_mode=true ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_configure ...          ← Plugin konfiguriert
[ros2_control_node-2] [INFO]: ... loopback skipping serial open ...
[spawn_joint_state_broadcaster] [INFO]: Loaded joint_state_broadcaster        ← JSB spawned
[spawn_joint_state_broadcaster] [INFO]: Configured and activated ...
[spawn_leg_1_controller] [INFO]: Loaded leg_1_controller                      ← 6 JTCs spawnen parallel
[spawn_leg_1_controller] [INFO]: Configured and activated ...
... (analog leg_2 bis leg_6)
```

Keine `[ERROR]`/`[FATAL]`-Zeilen. Wenn alle 7 Spawner mit „Configured
and activated" exit'en, ist die Verdrahtung Plugin↔URDF↔real.yaml↔
controller_manager↔Spawner gesund.

### Schritt 3 — Plugin-Status verifizieren

**Terminal 2** (während Schritt 2 noch läuft):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 control list_hardware_components
```

**Erwartung:** Ein Eintrag, ungefähr:
```
Hardware Component 1
  name: GazeboSimSystem
  type: system
  plugin name: hexapod_hardware/HexapodSystemHardware
  state: id=3 label=active
  ...
```

(Der `name: GazeboSimSystem` ist hier ein historisches Logging-Label aus
dem URDF-`<ros2_control name="...">`-Attribut — **nicht** der Plugin-Name.
Plugin-Name ist die `plugin name`-Zeile darunter. Renaming auf
"HexapodSystem" laut Mutter-Plan-Doku ist ein offener Punkt für Stage J.)

```bash
ros2 control list_controllers
```

**Erwartung:** 7 Zeilen `active` (joint_state_broadcaster + 6× JTC),
**identisch zur Sim-Variante** — bestätigt dass der Switch funktioniert.

**Cleanup:** alle Terminals mit Ctrl-C beenden.

---

## Test F-T10 — End-to-End Walking-Test (sim + gait + teleop + PS4)

**Was hier verifiziert wird:** der volle IK + Gait + Teleop-Pfad
(Phase 4–6) bleibt voll funktional. Bei dem URDF-Refactor-Umfang reicht
F-T8 („Roboter steht") nicht — wir wollen einmal sehen dass er auch
**läuft**.

### Voraussetzungen

- PS4-Controller via USB angeschlossen
- Gazebo läuft (aus F-T8a, Terminal 1)

### Sequenz

**Terminal 1** (bereits aus F-T8a — falls neu geöffnet, Source-Block wiederholen):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

**Terminal 2:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_gait gait.launch.py
```

**Erwartung:** kein `[ERROR]`/`[FATAL]`; gait_node läuft, hört auf
`/cmd_vel` und `/cmd_body_height`.

**Terminal 3:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
```

**Erwartung:** joy_node erkennt Controller, kein Topic-Mapping-Error.

### Was am Controller drücken (Phase-6-Bindings)

| Eingabe | Erwartung |
|---|---|
| **R1 halten** (Dead-Man) + D-Pad ↑ | Roboter läuft 5 s vorwärts, sichtbarer Tripod-Gait (3 Beine in der Luft, 3 am Boden, alternierend) |
| **R1 halten** + D-Pad ← oder → | Roboter dreht auf der Stelle (gleiches Tripod-Pattern, aber mit Yaw) |
| **R1 halten** + L2 oder R2 | Body-Höhe sichtbar variiert (~5–10 cm Range) |
| R1 loslassen | Roboter friert sofort ein (Dead-Man) |

### Bestätigungs-Topics (Terminal 4 optional, parallel)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 topic hz /joint_states
# Erwartung: ~50 Hz konstant (matches controllers.yaml update_rate)

ros2 topic echo /leg_1/foot_contact --once
# Erwartung: Bool true/false (Phase-5-Foot-Contact-Sensor)
```

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| F-T2 Diff zeigt strukturelle Element-Änderungen | xacro-Refactor hat ungewollt was an `<state_interface>` o.ä. geändert | xacro-Output mit `--inorder` neu generieren, gegen `/tmp/sim_urdf_pre_F.xml` diffen, Conditional-Blöcke prüfen |
| F-T3 zeigt `<gazebo>`-Block trotz `use_sim:=false` | `<xacro:if value="${use_sim}">` fehlt um den `<gazebo>`-Block | `hexapod.ros2_control.xacro` letzten Block prüfen |
| F-T3 zeigt `velocity` state_interface trotz `use_sim:=false` | `<xacro:if value="${use_sim}">` fehlt im `joint_iface`-Macro um `<state_interface name="velocity"/>` | macro im `hexapod.ros2_control.xacro` prüfen |
| F-T4 `serial_port` ist nicht überschrieben | `<xacro:arg name="serial_port">` fehlt im Top-File **oder** im Include — prüfen mit `grep -r "xacro:arg.*serial_port" src/hexapod_description/urdf/` | Fehlende Deklaration ergänzen (per F-Q2-Antwort: BEIDE Stellen) |
| F-T5 `check_urdf` failt mit „No URDF found" | xacro-Output-Pfad falsch oder leer | `xacro` direkt aufrufen, Stderr lesen — meist fehlende `$(find ...)`-Auflösung weil `install/setup.bash` nicht gesourct |
| F-T6 yaml-Validate failt | Tab statt Spaces, falsches Indent | Datei im Editor öffnen, sichtbare Whitespace-Marker aktivieren |
| F-T7 hexapod_hardware-Tests failt | URDF-Refactor hat irgendwie Test-Helper-Pfade gebrochen | unwahrscheinlich (Tests bauen synthetische HardwareInfo); falls doch, in `test_helpers.hpp` schauen ob Refactor-Konstanten getroffen wurden |
| F-T8 Gazebo-Modell unsichtbar / mesh nicht geladen | URDF-`package://`-Pfad nicht aufgelöst | `ament_prefix_path` prüfen, `colcon build hexapod_description` rebuild |
| F-T8 RViz zeigt rote Status-Marker | Fixed-Frame falsch oder TF-Tree gebrochen | RViz Fixed-Frame auf `world` setzen, `ros2 run tf2_tools view_frames` für TF-Diagnose |
| F-T9 ros2_control_node startet, aber list_hardware_components zeigt nichts | controller_manager kennt das Plugin nicht — Resource-Index nicht im AMENT_PREFIX_PATH | `source install/setup.bash` in dem Terminal in dem ros2_control_node läuft; ggf. `colcon build hexapod_hardware` rebuild |
| F-T9 Plugin lädt, aber on_init failt mit „Calibration file not found" | xacro-`$(find hexapod_hardware)` lieferte falschen Pfad | xacro mit `--inorder` aufrufen, generierten URDF nach `<param name="calibration_file">` greppen, manuell prüfen ob Pfad existiert |
| F-T10 Roboter zuckt aber läuft nicht | gait_node-Konfiguration unstimmig oder JTC-Tracking-Error | gait_node-Logs prüfen; Phase-5-DK4 wiederholen |
| F-T10 Roboter kippt um | Foot-Contact-Reibung nicht aktiv (Phase 3 DK4) | `enable_foot_contact:=true` im sim.launch.py-Aufruf prüfen |
| F-T10 PS4 reagiert nicht | joy_node sieht Controller nicht | `ls /dev/input/js*`, `evtest` zur Verifikation, ggf. `sudo chmod a+rw /dev/input/js0` einmalig |

---

## Statusmeldung an Claude

- `F-T1–F-T10 alle grün` → **Stufe F komplett.** Weiter mit **Stufe G**
  (`real.launch.py` zusammen mit Spawner-Skripten)
- `F-T8/T9/T10` mit konkretem Fehler-Symptom → ich diagnostiziere
- Wenn nur `F-T8/T9/T10` (User-Smokes) noch offen: ich warte auf User-Run

Vollausgabe nur bei Fehler; sonst kurz „F-TX grün" reicht.
