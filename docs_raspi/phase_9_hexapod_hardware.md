# Phase 9 — ROS2-Plugin `hexapod_hardware`

**Dauer-Schätzung:** 2–4 Tage (C++-Plugin + Echo-State-Korrektur + Launch-Files)
**Maschine:** Desktop (Servo2040 hängt am Desktop, Pi noch nicht im Spiel)
**Vorbedingung:** Phase 7 abgeschlossen (Firmware mit Protokoll), Phase 8
abgeschlossen (Bench-Strom steht)

---

## Ziel

Ein neues C++-Paket `hexapod_hardware` im `hexapod_ws`, das als pluginlib-
Plugin einen `ros2_control`-`SystemInterface` exportiert und mit der
Servo2040-Firmware aus Phase 7 über USB-CDC spricht.

Damit lässt sich der komplette ROS2-Stack (gait_node, JTC, JSB, teleop)
**am Desktop** gegen echte Servo2040-Hardware fahren — kein Pi nötig in
dieser Phase.

URDF und Launch-Files werden so umgebaut, dass per LaunchArg `mode:=sim|hw`
zwischen Gazebo und echter HW gewählt wird (Option A aus der Planung).

---

## Architektur-Entscheidungen

### A. Sim/HW-Switch via xacro-Conditional (Option A)

URDF bekommt einen `use_sim`-Argument. `gz_ros2_control` oder
`hexapod_hardware` wird zur Laufzeit ausgewählt — **nie beide gleichzeitig**.

```xml
<xacro:arg name="use_sim" default="true"/>
<xacro:property name="use_sim" value="$(arg use_sim)"/>

<ros2_control name="HexapodSystem" type="system">
  <hardware>
    <xacro:if value="${use_sim}">
      <plugin>gz_ros2_control/GazeboSimSystem</plugin>
    </xacro:if>
    <xacro:unless value="${use_sim}">
      <plugin>hexapod_hardware/HexapodSystemHardware</plugin>
      <param name="serial_port">/dev/ttyACM0</param>
      <param name="calibration_file">$(find hexapod_hardware)/config/servo_mapping.yaml</param>
    </xacro:unless>
  </hardware>
  ...
</ros2_control>
```

### B. Echo-State (kein echtes Position-Feedback)

Die Servos liefern **kein Position-Feedback**. Konsequenz für
`SystemInterface::read()`:

```cpp
hardware_interface::return_type HexapodSystemHardware::read(...) {
    // Servo2040 kann uns last_pulse zurückgeben (was zuletzt geschickt
    // wurde, nicht was die Servos wirklich tun)
    // Wir reflektieren das als position-State zurück
    for (int i = 0; i < 18; i++) {
        hw_state_positions_[i] = pulse_us_to_radians(last_pulse_us_[i], i);
    }
    return hardware_interface::return_type::OK;
}
```

**Folge:** JTC-Tracking-Error ist strukturell immer ~0. Tools wie
`stopped_velocity_tolerance` sind auf der HW unwirksam. Diagnose-Ersatz
ist Current-Sense (Effort-Interface).

Diese Limitation **muss** in `README.md` des Pakets dokumentiert werden.

### C. Optional: Effort-State aus Strommessung

`current_mA` pro Servo aus Servo2040-Frame → als `effort`-State-Interface
exportieren. Nicht echtes Drehmoment, aber proportional. Hilfreich für
Logging und Stall-Detection im Stack.

### D. Loopback-Mode

Plugin-Parameter `loopback_mode:=true|false`:
- `true`: `read()` gibt die zuletzt geschriebenen Commands als State
  zurück, **kein** Serial-Port wird geöffnet → der gesamte
  `ros2_control`-Stack ist testbar ohne dass Servo2040 angeschlossen
  ist.
- `false`: echte Servo2040-Anbindung über `/dev/ttyACM0`.

---

## Done-Kriterien

1. Paket `hexapod_hardware` baut grün
2. Plugin lädt via pluginlib (`ros2 control list_hardware_components` zeigt
   `hexapod_hardware/HexapodSystemHardware`)
3. xacro-Switch `use_sim:=true|false` funktioniert, beide Builds grün
4. `real.launch.py` startet erfolgreich auf Desktop
5. Loopback-Mode: alle Controller active, JTC akzeptiert Trajectories
6. Echte Anbindung mit Servo2040 (ohne echte Servos, nur Servo2040-Board
   am Desktop): PWM-Signale am Servo2040-Output-Pin mit Oszi/Logic-Analyzer
   messbar
7. `controllers.real.yaml` mit reduzierten Limits committed
8. README dokumentiert Echo-State-Limitation

---

## Stufen

### Stufe A — Paket anlegen

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 hexapod_hardware
```

`package.xml`:
```xml
<depend>hardware_interface</depend>
<depend>pluginlib</depend>
<depend>rclcpp</depend>
<depend>rclcpp_lifecycle</depend>
<depend>controller_manager</depend>
```

Struktur:
```
hexapod_hardware/
├── CMakeLists.txt
├── package.xml
├── hexapod_hardware.xml          # pluginlib-Export
├── README.md
├── include/hexapod_hardware/
│   ├── hexapod_system.hpp        # SystemInterface-Subklasse
│   ├── servo2040_protocol.hpp    # Frame-Encoder/Decoder
│   └── calibration.hpp           # YAML-Reader + rad↔pulse-Konversion
├── src/
│   ├── hexapod_system.cpp
│   ├── servo2040_protocol.cpp
│   └── calibration.cpp
├── config/
│   └── servo_mapping.yaml        # final hier (aus Phase 7 verschoben)
└── test/
    └── test_calibration.cpp      # Unit-Tests der Konversion
```

**Done-Kriterium A:**
1. Paket baut leer grün (mit Skelett-Klassen)

---

### Stufe B — Frame-Encoder/Decoder

Implementiert die Protokoll-Spec aus Phase 7:
- `SET_TARGETS`-Frame zusammenbauen (18 int16 Pulse-µs + CRC16 + COBS)
- `STATE`-Frame parsen (last_pulse, current_mA, voltage_mV, status_flags)
- `ENABLE_SERVO`, `RESET`-Frames
- Unsolicited `ERROR_REPORT`/`WARNING`-Frames empfangen

Unit-Tests (`test/test_servo2040_protocol.cpp`):
- Bekannte Frame-Hex-Strings encoden/decoden, prüfen
- CRC-Korrektheit
- COBS-Roundtrip

**Done-Kriterium B:**
1. Protokoll-Code mit Unit-Tests, alle grün

---

### Stufe C — Kalibrierungs-Lib

`calibration.hpp/.cpp`:
- Lädt `servo_mapping.yaml`
- Pro Joint: `output_idx`, `direction`, `pulse_zero`, `pulse_per_rad`,
  `pulse_min`, `pulse_max`
- `double radians_to_pulse_us(int joint_idx, double rad)`
- `double pulse_us_to_radians(int joint_idx, double pulse)` (Inverse für
  Echo-State)
- Clamping passiert auf Servo2040-Seite (Hard-Clamp), hier nur Konversion

Unit-Tests:
- `rad=0` → `pulse_zero`
- `rad=±π/4` → erwarteter Pulse mit Direction
- Roundtrip rad → pulse → rad ist identity

**Done-Kriterium C:**
1. Lib + Unit-Tests grün
2. Skelett-YAML mit Platzhalter-Werten (echte Kalibrierung kommt in Phase 10)

---

### Stufe D — `HexapodSystemHardware`-Klasse

Subklasse von `hardware_interface::SystemInterface`.

| Methode | Aufgabe |
|---|---|
| `on_init` | URDF parsen (joint-Liste, Limits), Kalibrierungs-YAML laden, interne Vektoren allokieren |
| `on_configure` | Serial-Port öffnen (`/dev/ttyACM0`, termios), Handshake-Frame mit Servo2040 senden |
| `on_activate` | `ENABLE`-Frames für alle 18 Servos schicken (Servo2040 macht den Stagger) |
| `on_deactivate` | `DISABLE`-Frames, Port schließen |
| `export_state_interfaces` | je Joint: `position`, optional `velocity`, optional `effort` (= Strommessung) |
| `export_command_interfaces` | je Joint: `position` |
| `read` | letztes `STATE`-Frame parsen (oder Echo wenn loopback), positions/effort befüllen |
| `write` | command-Vektor → Pulse-µs konvertieren → `SET_TARGETS`-Frame senden |

`loopback_mode`-Parameter: in `on_configure` Serial überspringen, in `read`
direkt `last_command_` zurückreflektieren.

USB-Reconnect-Logik: in `read`/`write` Fehler abfangen, bei Disconnect
`/dev/ttyACM0` neu öffnen versuchen (mit Backoff). Wenn nicht möglich:
ros2_control bekommt return_type::ERROR und Controller geht in „inactive".

**Done-Kriterium D:**
1. Klasse implementiert, baut grün
2. Loopback-Mode funktional
3. USB-Reconnect-Logik mit simuliertem Disconnect (Kabel ziehen) getestet

---

### Stufe E — Plugin-Registrierung

`hexapod_hardware.xml`:
```xml
<library path="hexapod_hardware">
  <class name="hexapod_hardware/HexapodSystemHardware"
         type="hexapod_hardware::HexapodSystemHardware"
         base_class_type="hardware_interface::SystemInterface">
    <description>Hexapod via Servo2040 USB-CDC.</description>
  </class>
</library>
```

`CMakeLists.txt`:
```cmake
pluginlib_export_plugin_description_file(hardware_interface hexapod_hardware.xml)
```

Verifikation:
```bash
colcon build --packages-select hexapod_hardware
source install/setup.bash
ros2 pkg prefix hexapod_hardware
# pluginlib factory:
ros2 control list_hardware_components   # erst nach Stufe G mit launch
```

**Done-Kriterium E:**
1. Plugin-XML korrekt, CMake-Export gesetzt
2. pluginlib findet das Plugin

---

### Stufe F — URDF-Anpassung & `controllers.real.yaml`

#### F.1 URDF

`src/hexapod_description/urdf/hexapod.ros2_control.xacro` bekommt
`use_sim`-Argument und das `<xacro:if>`-Switching (siehe Architektur-
Entscheidung A oben).

#### F.2 `controllers.real.yaml`

Kopie von `controllers.yaml` mit:
- `use_sim_time: false` (Wallclock)
- Velocity- und Acceleration-Limits **drastisch reduziert** (ca. 30 % der
  Sim-Werte) für Bring-up. Wird in Phase 12 hochgezogen.

```yaml
controller_manager:
  ros__parameters:
    update_rate: 50
    use_sim_time: false  # WICHTIG: false für echte HW
    ...

leg_1_controller:
  ros__parameters:
    joints: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint]
    constraints:
      goal_time: 1.0
      stopped_velocity_tolerance: 0.0   # JTC kann strukturell nicht erkennen, wir lassen es lax
      ...
```

**Done-Kriterium F:**
1. URDF baut in beiden Modi (sim/hw) grün
2. `controllers.real.yaml` committed

---

### Stufe G — `real.launch.py`

Im Paket `hexapod_bringup`:

```python
# Pseudocode
def generate_launch_description():
    use_loopback = LaunchConfiguration('loopback', default='false')

    robot_description = ...   # xacro mit use_sim:=false
    
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[robot_description, 'controllers.real.yaml',
                    {'loopback_mode': use_loopback}])
    
    rsp = Node('robot_state_publisher', use_sim_time=False)
    
    jsb_spawner = Spawner('joint_state_broadcaster')
    leg_spawners = [Spawner(f'leg_{n}_controller') for n in 1..6]
    
    # KEIN gazebo, KEIN ros_gz_bridge
    return LaunchDescription([...])
```

LaunchArgs:
- `loopback:=true|false` (default false)
- `serial_port:=/dev/ttyACM0`
- `controller:=ps4_usb` (für joy_teleop, optional)

**Done-Kriterium G:**
1. `ros2 launch hexapod_bringup real.launch.py loopback:=true` startet
   sauber
2. `ros2 control list_controllers` zeigt 1× JSB + 6× JTC, alle active

---

### Stufe H — Echte Servo2040-Anbindung (ohne Hexapod-Servos)

Servo2040 vom Desktop aus angesprochen, **keine** Servos angeschlossen
(noch — Phase 10 macht den Anschluss).

```bash
ros2 launch hexapod_bringup real.launch.py loopback:=false
```

Verifikation mit Logic-Analyzer/Oszi an einem Servo2040-Output-Pin:
- Bei Joint=0: PWM-Puls ~1500 µs
- JTC bekommt Trajectory → PWM-Puls verändert sich entsprechend
- Watchdog feuert wenn ros2_control gestoppt wird (Servo2040 disabled
  alles)

**Done-Kriterium H:**
1. PWM-Signal am Servo2040-Output messbar
2. Pulse-Wert entspricht dem erwarteten Wert aus Kalibrierungs-YAML
3. Watchdog auf Servo2040-Seite greift bei Stack-Stop

---

### Stufe I — Tests & Doku

#### I.1 Unit-Tests

- `test_servo2040_protocol`: Encoder/Decoder
- `test_calibration`: rad↔pulse-Konversion

#### I.2 launch_testing

Smoke-Test: Node startet, alle Controller spawnen, in 10 s kein Crash.

#### I.3 README

`hexapod_hardware/README.md`:
- Zweck
- Topics (gleiche wie Sim, mit Verweis auf Phase-6-Doku)
- Parameter (`serial_port`, `calibration_file`, `loopback_mode`)
- Beispiel-Launch
- **Klar dokumentiert: Echo-State, keine echte Position-Validierung**
- Reconnect-Verhalten

**Done-Kriterium I:**
1. Unit-Tests grün
2. launch_testing-Smoke grün
3. README komplett, Echo-State-Limitation klar

---

### Stufe J — Phase-9-Abschluss

- `phase_9_progress.md` finalisieren
- Git-Commit, Tag `phase-9-done`
- `PHASE.md` auf Phase 10 aktualisieren

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `controller_manager` findet Plugin nicht | `pluginlib_export_plugin_description_file` fehlt im CMake | XML + CMake prüfen, `colcon build --packages-select hexapod_hardware` clean |
| `read`/`write` werden nicht aufgerufen | Controller im Inactive-State | `ros2 control list_controllers`, `ros2 control switch_controllers --activate ...` |
| `/dev/ttyACM0` Permission denied | dialout-Gruppe | `sudo usermod -aG dialout $USER`, neu einloggen |
| Frame-Drift, CRC-Fehler | Baudrate-Mismatch oder USB-Treiber-Buffering | termios non-canonical mode, VTIME=0, VMIN=0; oder libserial |
| JTC „goal_time exceeded" | Echo-State ist 0-Tracking, aber Trajectory braucht echte Zeit | `goal_time_tolerance` hochsetzen |
| Roboter bewegt sich falsch herum | `direction` (±1) in YAML falsch | Eintrag korrigieren, neu builden (oder als param überschreiben) |
| Reconnect klemmt, Plugin bleibt in ERROR | Reconnect-Backoff zu aggressiv | Backoff-Logik mit Exponential, ros2_control-Manager kann re-activate |
| Servo2040-Frame-Rate sinkt unter 30 Hz | termios VMIN/VTIME falsch, blockierende reads | non-blocking IO, oder Reader-Thread |

---

## Was in dieser Phase **NICHT** gemacht wird

- Keine echten Hexapod-Servos angeschlossen (Phase 10)
- Keine Bewegungs-Tests am echten Roboter
- Kein Pi (Phase 11)
- Kein Akku (Phase 13+)

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–I Done-Kriterien erfüllt
- [ ] Unit-Tests grün
- [ ] Loopback-Mode auf Desktop funktioniert
- [ ] Echte Servo2040-Anbindung mit Oszi-Verifikation
- [ ] `controllers.real.yaml` committed
- [ ] `real.launch.py` committed
- [ ] README dokumentiert Echo-State-Limitation
- [ ] Git-Commit + Tag `phase-9-done`
- [ ] `PHASE.md` auf Phase 10 aktualisiert
- [ ] Retrospektive in `phase_9_progress.md`
