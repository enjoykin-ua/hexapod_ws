# Phase 9 — Stufe G — Test-Anleitung

**Was geprüft wird:** Der `real.launch.py`-Bringup im
`hexapod_bringup`-Paket startet den vollen ros2_control-Stack OHNE
Gazebo: `robot_state_publisher` + `controller_manager` (mit
`hexapod_hardware`-Plugin) + Spawner-Chain (JSB + 6× JTC). Beide
LaunchArgs (`loopback_mode`, `serial_port`) werden korrekt
durchgereicht. Der Sim-Pfad (Phase 4–6) bleibt regression-frei.

**Was NICHT in G in CI geprüft wird:**
- echter Servo2040-Anschluss (Stage H)
- Trajectory-Publishen + JTC-Reaktion (Stage H/I)
- gait + teleop im real.launch.py (bewusst nicht inline, siehe Plan-Doku
  „Was Stufe G NICHT macht")

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_bringup hexapod_description hexapod_control hexapod_hardware
source install/setup.bash
```

> **In JEDEM neuen Terminal das du für G-T4 / G-T5 / G-T7 / G-T8 öffnest,
> die drei Source-Zeilen (`cd ~/hexapod_ws`, `source /opt/ros/jazzy/setup.bash`,
> `source install/setup.bash`) wieder ausführen** — sonst sieht ROS2
> die Pakete + Plugins nicht.

---

## Test G-T1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_bringup --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine
`warning:`. `real.launch.py` wird als Symlink unter
`install/hexapod_bringup/share/hexapod_bringup/launch/` installiert.

---

## Test G-T2 — Launch-Syntax + Args sichtbar

```bash
ros2 launch hexapod_bringup real.launch.py --show-args
```

**Erwartung:**
```
Arguments (pass arguments as '<name>:=<value>'):

    'loopback_mode':
        true: Plugin oeffnet KEINEN seriellen Port ...
        (default: 'false')

    'serial_port':
        USB-CDC-Device der Servo2040 ...
        (default: '/dev/ttyACM0')
```

---

## Test G-T3 — xacro mit LaunchConfig-Args strukturell korrekt

```bash
xacro ~/hexapod_ws/src/hexapod_description/urdf/hexapod.urdf.xacro \
    use_sim:=false loopback_mode:=true serial_port:=/dev/ttyACM1 \
    | grep -A 4 "<hardware>" | head -10
```

**Erwartung:**
```xml
<hardware>
  <plugin>hexapod_hardware/HexapodSystemHardware</plugin>
  <param name="serial_port">/dev/ttyACM1</param>
  <param name="calibration_file">/home/enjoykin/hexapod_ws/install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml</param>
  <param name="loopback_mode">true</param>
```

---

## Test G-T4 — **Loopback-Bringup-Smoke (Stage-G-Hauptbeweis)**

Vorgezogen aus Stage F's verschobenem F-T9. Verifiziert dass der
gesamte ros2_control-Stack über das `hexapod_hardware`-Plugin im
Loopback-Modus durchläuft.

### Schritt 1 — Launch starten

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

**Erwartung im Log** (in dieser Reihenfolge):
```
[robot_state_publisher]: got segment base_link ...                       ← RSP lädt URDF
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_init ...           ← Plugin lädt
[ros2_control_node-2] [INFO]: ... loopback_mode=true ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_configure ...       ← Plugin konfiguriert
[ros2_control_node-2] [INFO]: ... loopback skipping serial open ...
[spawn_joint_state_broadcaster] [INFO]: Loaded joint_state_broadcaster      ← JSB spawned
[spawn_joint_state_broadcaster] [INFO]: Configured and activated ...
[spawn_leg_1_controller] [INFO]: Loaded leg_1_controller                    ← 6 JTCs spawnen parallel
[spawn_leg_1_controller] [INFO]: Configured and activated ...
... (analog leg_2 bis leg_6)
```

Keine `[ERROR]`/`[FATAL]`-Zeilen. Wenn alle 7 Spawner mit „Configured
and activated" exit'en, ist die End-to-End-Verdrahtung gesund.

### Schritt 2 — Plugin-Status verifizieren

**Terminal 2** (während Terminal 1 noch läuft):
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
```

(Der `name: GazeboSimSystem` ist ein historisches Logging-Label aus dem
URDF-`<ros2_control name="...">`-Attribut — Renaming auf "HexapodSystem"
ist Stage-J-Vormerk, siehe Stage-F-Self-Review.)

### Schritt 3 — Controller-Status verifizieren

**Terminal 2** (gleich danach):
```bash
ros2 control list_controllers
```

**Erwartung:** 7 Zeilen `active`:
```
joint_state_broadcaster   joint_state_broadcaster/JointStateBroadcaster   active
leg_1_controller          ...JointTrajectoryController                    active
leg_2_controller          ...                                             active
leg_3_controller          ...                                             active
leg_4_controller          ...                                             active
leg_5_controller          ...                                             active
leg_6_controller          ...                                             active
```

### Cleanup

Ctrl-C in Terminal 1 beendet alles sauber.

---

## Test G-T5 — Args-Override-Smoke

Verifiziert dass beide LaunchArgs sauber durchgereicht werden, indem
ein abweichender `serial_port` gesetzt wird (Plugin sieht den Wert im
Loopback-Modus zwar, öffnet aber nichts).

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true serial_port:=/dev/null
```

**Erwartung:** identischer Lauf zu G-T4. Im Log unter dem `on_init`-
Banner taucht `serial_port=/dev/null` auf (statt `/dev/ttyACM0`). Da
loopback_mode=true ist, wird `/dev/null` nicht geöffnet — kein Crash.

**Terminal 2** (Verifikation):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 param get /controller_manager robot_description 2>&1 | grep '<param name="serial_port"'
```

**Erwartung:** **eine** Zeile mit `<param name="serial_port">/dev/null</param>`
(als Substring im veröffentlichten robot_description).

> Der tightere grep-Filter `'<param name="serial_port"'` (statt nur
> `"serial_port"`) filtert den Treffer aus dem XML-Doku-Kommentar in
> `hexapod.ros2_control.xacro` raus (der Text dort enthält
> wörtlich „serial_port" und würde sonst als zweite Match-Zeile
> auftauchen, was inhaltlich harmlos aber visuell verwirrend ist).

### Cleanup
Ctrl-C in Terminal 1.

---

## Test G-T6 — `hexapod_hardware`-Tests weiter alle grün (Plugin-Regression)

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --test-result-base build/hexapod_hardware --verbose | tail -3
```

**Erwartung:** `Summary: 208 tests, 0 errors, 0 failures, 20 skipped`
(unverändert vs Stage-F-Endstand). Plugin-Code ist in Stage G nicht
angefasst, also strikt 0 Diff zu erwarten.

---

## Test G-T7 — Sim-Pfad regression-frei (sim.launch.py)

Analog Stage F's F-T8: bei einem Paket-weiten Refactor in `hexapod_bringup`
muss auch der bestehende Sim-Pfad weiterhin starten.

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

**Erwartung:** identisch zu F-T8a — Gazebo öffnet, Hexapod sichtbar,
nach ~3 s alle 7 Controller active. Keine neuen `[ERROR]`/`[FATAL]`s
die in Stage F nicht da waren.

**Terminal 2:**
```bash
ros2 control list_controllers
```

**Erwartung:** 7 Zeilen `active` (wie F-T8a).

### Cleanup
Ctrl-C in Terminal 1.

---

## Test G-T8 — Sim-Walking-Regression (sim + gait + teleop + PS4)

Per Memory-Konvention `feedback_urdf_refactor_full_smoke.md`: auch wenn
Stage G nicht direkt URDF anfasst, ist es eine Bringup-Änderung am
selben Paket → Walking-Smoke einmal durchziehen.

### Voraussetzungen
- PS4-Controller via USB angeschlossen
- Gazebo läuft (aus G-T7, Terminal 1)

### Sequenz (analog F-T10)

**Terminal 2:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_gait gait.launch.py
```

**Terminal 3:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
```

### Was am Controller drücken (Phase-6-Bindings)

| Eingabe | Erwartung |
|---|---|
| **R1 halten** + D-Pad ↑ | Roboter läuft 5 s vorwärts, Tripod-Gait sichtbar |
| **R1 halten** + D-Pad ← oder → | Roboter dreht auf der Stelle |
| **R1 halten** + L2 oder R2 | Body-Höhe variiert |
| R1 loslassen | Roboter friert sofort ein (Dead-Man) |

Identisches Verhalten zu F-T10 erwartet (keine Veränderung am Sim-Stack
durch Stage G).

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| G-T1 Build-Warnung „package hexapod_hardware not found" | `<exec_depend>` in package.xml fehlt oder hexapod_hardware nicht gebaut | `colcon build hexapod_hardware` zuerst, dann `colcon build hexapod_bringup` |
| G-T2 `--show-args` zeigt nur einen oder gar keinen LaunchArg | `DeclareLaunchArgument` im LaunchDescription-`return`-Block vergessen | beide `declare_*`-Variablen müssen im `return LaunchDescription([...])` als erste Items vorkommen |
| G-T3 xacro-Output zeigt noch Default-Werte trotz Override | xacro-CLI-Syntax verstanden? Werte müssen wie `name:=value` (Doppelpunkt-Gleich) übergeben werden | `xacro hexapod.urdf.xacro use_sim:=false ...` exakt so eingeben |
| G-T4 `Failed to load joint_state_broadcaster` | controller_manager noch nicht hochgekommen als Spawner gestartet wurde | Plugin-on_configure failt? Logs prüfen. Falls Calibration nicht gefunden: `colcon build hexapod_hardware` rebuild |
| G-T4 `list_hardware_components` zeigt nichts | Resource-Index nicht im AMENT_PREFIX_PATH | `source install/setup.bash` im **Verifikations-Terminal** wiederholen |
| G-T4 list_controllers zeigt nur JSB, keine JTCs | OnProcessExit-Chain nicht ausgelöst — JSB-Spawner crash'te vielleicht | Terminal-1-Log nach `[spawn_joint_state_broadcaster]`-Zeile durchsuchen, Exit-Code prüfen |
| G-T5 `ros2 param get` zeigt riesigen URDF-String anstelle der gesuchten Zeile | grep-Filter zu strikt | volle Ausgabe ohne grep zeigen lassen, dann visuell nach `<param name="serial_port">` suchen |
| G-T6 hexapod_hardware-Tests failt mit neuer Failure | Sehr unwahrscheinlich — Plugin-Code in Stage G nicht angefasst. Falls doch: `colcon build hexapod_hardware --cmake-clean-cache && colcon test` | |
| G-T7 sim.launch.py failt nach Stage G | hexapod_bringup-Refactor hat ungewollt sim.launch.py beeinflusst | `git diff src/hexapod_bringup/launch/sim.launch.py` — sollte 0 Diff zeigen |
| G-T8 PS4 reagiert nicht | joy_node sieht Controller nicht | `ls /dev/input/js*`, `evtest` zur Verifikation |

---

## Statusmeldung an Claude

- `G-T1–G-T8 alle grün` → **Stufe G komplett.** Weiter mit **Stufe H**
  (echte Servo2040-Anbindung mit Oszi/Logic-Analyzer)
- `G-T4/T5/T7/T8` mit konkretem Fehler-Symptom → ich diagnostiziere
- Wenn nur User-Smokes (G-T4/T5/T7/T8) noch offen: ich warte auf User-Run

Vollausgabe nur bei Fehler; sonst kurz „G-TX grün" reicht.
