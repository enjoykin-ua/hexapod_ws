# Phase 7 — Pi-Portierung & Hardware: Handoff aus Phase 6

> **Lesehinweis:** dieses Doc ist als **Single-Entry-Point** für
> Phase 7 gedacht. Du findest hier was wo liegt, was Phase 7 ändern
> muss, was unverändert übernommen wird, und welche Sicherheits-
> Vorgaben ab jetzt zwingend gelten (echte Servos!).
>
> Vertiefung optional in:
> - [phase_5_progress.md](phase_5_progress.md) /
>   [phase_5_gait_explained.md](phase_5_gait_explained.md) — Engine,
>   IK, Trajektorien
> - [phase_6_progress.md](phase_6_progress.md) — PS4-Teleop
> - [phase_6_teleop_handoff.md](phase_6_teleop_handoff.md) — cmd_vel-
>   Interface (gilt 1:1 weiter, auch am Pi)
>
> [CLAUDE.md](../CLAUDE.md) §9 (Hardware-Sicherheit) **MUSS** vor dem
> ersten echten Joint-Test gelesen sein.

---

## TL;DR

Phasen 0-6 haben einen funktionierenden Hexapod-Stack in **Sim**
geliefert: Walk via cmd_vel, PS4-Controller-Teleop, omnidirektional,
Body-Lift im Stand. Phase 7 portiert das auf den **Raspberry Pi 4
mit Servo2040-Hardware**.

**Phase-7-Aufgabe** in einem Satz: Ersetze `gz_ros2_control` durch
ein **C++ `hexapod_hardware`-Paket**, das via `pluginlib` einen
`ros2_control`-`SystemInterface` exportiert und mit dem Servo2040-
Board über das vereinbarte Protokoll redet. Engine, Gait, Teleop,
URDF, controllers.yaml laufen unverändert weiter.

---

## Was bleibt unverändert (Sim ↔ HW)

| Komponente | Anmerkung |
|---|---|
| `hexapod_kinematics` | Pure-Python IK, kein ROS-Stack — funktioniert am Pi 1:1 |
| `hexapod_gait` | Engine + gait_node + stand_node — unverändert |
| `hexapod_teleop` | joy_to_twist + ps4_usb.yaml — unverändert |
| `hexapod_description` URDF/Xacro | Joint-Geometrie identisch (gleicher Roboter) |
| `controllers.yaml` Struktur | 1× JSB + 6× JTC — gleich, aber zwei Werte ändern (siehe unten) |
| `/cmd_vel`-Interface | Twist mit linear.x/y + angular.z — gleich |
| `/cmd_body_height`-Interface | Float64, nur im STANDING — gleich |

---

## Was Phase 7 ändert

### 1. `hexapod_hardware` — neues C++-Paket

Ersetzt `gz_ros2_control` durch echten HW-Treiber.

```
src/hexapod_hardware/                 # NEU, C++ ament_cmake
├── CMakeLists.txt
├── package.xml
├── include/hexapod_hardware/
│   └── hexapod_system.hpp           # SystemInterface-Subklasse
├── src/
│   ├── hexapod_system.cpp           # Implementation
│   └── servo2040_protocol.cpp       # Protokoll-Adapter (Serial/I²C/USB)
├── plugins.xml                      # pluginlib-Export
└── README.md
```

`SystemInterface` muss implementieren:
- `on_init()` — Servo2040-Verbindung öffnen
- `export_state_interfaces()` — 18× position + velocity States
- `export_command_interfaces()` — 18× position Commands
- `read()` — pro Tick: aktuelle Servo-Positionen lesen
- `write()` — pro Tick: neue Soll-Positionen senden

### 2. URDF: `<ros2_control>`-Plugin tauschen

In `hexapod_description/urdf/hexapod.ros2_control.xacro`:

```xml
<!-- Sim (Phase 4-6): -->
<plugin>gz_ros2_control/GazeboSimSystem</plugin>

<!-- HW (Phase 7, neu): -->
<plugin>hexapod_hardware/HexapodSystem</plugin>
```

Variante: per LaunchArg + xacro-Conditional zwischen Sim/HW
umschalten.

### 3. `controllers.yaml` — zwei Werte umstellen

Aktuell (Phase 4-6):

```yaml
controller_manager:
  ros__parameters:
    use_sim_time: true        # ← FALSCH am Pi
```

In Phase 7:

```yaml
controller_manager:
  ros__parameters:
    use_sim_time: false       # Wallclock
```

Empfohlen: zweite Datei `controllers.real.yaml` mit `use_sim_time:
false`, zur Laufzeit per LaunchArg gewählt.

### 4. `body_height` Default: `-0.052` → `-0.047`

Sim hatte 5 mm globale Penetration als JTC-Tracking-Lag-Workaround
(Stufe-F-Designentscheidung 1). **Echte Servos haben keinen Lag** →
Default zurück.

Betroffen:
- `gait_node.py` Default-Param `body_height = -0.047`
- `gait.launch.py` Default `-0.047`
- `stand_node.py` Default `-0.047`
- `stand.launch.py` Default `-0.047`
- `joy_to_twist.py` Default `body_height_init = -0.047`

Empfohlen: per LaunchArg umschaltbar `mode:=sim|hw` der die Defaults
auswählt, oder zwei separate Launch-Files
`gait_sim.launch.py`/`gait_hw.launch.py`.

---

## Servo2040-Anbindung (Phase 7-Hauptarbeit)

> **Vom User in CLAUDE.md §1 als "bereits definiert" deklariert:**
> Kommunikationsprotokoll zwischen ROS2-Knoten und Servo2040 ist
> definiert. ROS-seitig erfolgt die Anbindung erst hier in Phase 7.

Du brauchst:
- Protokoll-Spec vom User (in welcher Form: Serial-Frames, I²C-
  Register, USB-HID, ...)
- Servo-Mapping: welche Servo2040-PWM-Lanes entsprechen welchen
  18 Joints (`leg_<n>_(coxa|femur|tibia)_joint`)
- Joint-Limits aus
  [hexapod_physical_properties.xacro](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
  in Servo-Pulse-Werte umrechnen
- Servo-Calibration: Joint-Winkel = 0 → welche Pulse-Width pro Servo

---

## ROS-System auf dem Pi

Nach Phase-7-Fertigstellung läuft auf dem Pi:

```
/joint_state_broadcaster        # JSB — wie Sim
/leg_<n>_controller             # JTC × 6 — wie Sim
/controller_manager             # CM — wie Sim
/robot_state_publisher          # RSP — wie Sim
/gait_node                      # Gait — wie Sim
/joy_node                       # Joystick — wie Sim
/joy_to_twist                   # Teleop — wie Sim
```

**Nicht mehr** auf dem Pi:
- `/ros_gz_bridge` (Gazebo entfällt)
- `/foot_contact_publisher` (Stufe-D-Sim-Sensor — echte HW hat keine
  Foot-Contact-Sensoren outof-the-box; Phase-8-Erweiterung optional)

---

## Empfohlene Stufen-Aufteilung Phase 7

Ähnlich Phase 5/6: granular, jede Stufe live verifiziert.

| Stufe | Inhalt | Voraussetzung |
|---|---|---|
| A | Pi-Setup: Ubuntu Server 24.04, ROS2 Jazzy, Workspace clonen | — |
| B | `hexapod_hardware`-Paket-Skelett (CMakeLists, package.xml, leeres SystemInterface) | A |
| C | Servo2040-Protokoll-Adapter (lese-only, ein Joint testen) | B + HW-Kill-Switch + aufgebockt |
| D | Voll-Bidirectional ein Joint (read + write Position) | C |
| E | Alle 18 Joints, kein Gait — nur Stand-Pose anfahren | D |
| F | Gait-Tests aufgebockt (Beine in der Luft, kein Bodenkontakt) | E |
| G | Stand-Pose mit Bodenkontakt (Roboter trägt sich selbst) | F |
| H | Walk-Tests via cmd_vel (auf weichem Untergrund, in 10% Geschwindigkeit) | G |
| I | PS4-Teleop am Pi | H |
| J | Phasen-Abschluss + Doku | I |

**Kritische Sicherheits-Stufen:** C → D → E. Erst single-Joint, dann
ein Bein, dann alles. Aufgebockt!

---

## CLAUDE.md §9 Sicherheits-Recap

Kopiere bei Phase-7-Start in dein Working-Memory:

- **Roboter aufbocken** (Beine in der Luft) für ersten Joint-Test
- **Hardware-Kill-Switch griffbereit** (Stromtrennung)
- **Erst ein einzelner Joint, dann ein Bein, dann alle**
- **Servo-Endlagen + Strom-Limits** in SW UND HW redundant
- **Erste Bewegung mit reduzierter Geschwindigkeit** (10% Nennrate)

---

## Diagnose-Cheatsheet (am Pi)

```bash
# 1. ROS2 läuft?
ros2 node list

# 2. HardwareInterface geladen?
ros2 control list_hardware_components       # erwartet: hexapod_hardware/HexapodSystem

# 3. Controller alle aktiv?
ros2 control list_controllers               # erwartet: 1× JSB + 6× JTC, alle "active"

# 4. Joints kommen rein?
ros2 topic echo /joint_states               # 18 Werte ändern sich (oder konstant wenn aufgebockt)

# 5. Servo2040-Verbindung sauber?
# → eigenes Diagnose-Tool im hexapod_hardware-Paket (z.B. CLI das
#   Servo2040-Status liest)

# 6. cmd_vel-Pipeline am Pi:
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{linear: {x: 0.0}}'
# erwartet: gait_node geht in STANDING, alle 18 Joints konvergieren
# zu Stand-Pose
```

---

## Was Phase 7 NICHT macht

- **Keine neuen Gangarten** (Wave, Ripple) — bleiben Phase 8+
- **Keine Sensor-Integration** (IMU, Kamera) — Phase 8+
- **Kein Closed-Loop-Yaw-Korrektur** — Phase 8+
- **Keine PS-Controller-Bluetooth** (Stufe B aus Phase 6 übergeben,
  kann am Pi nachgeholt werden, ist aber nicht zwingend Phase 7)
- **Kein KDL-Warning-Fix** (User-Entscheidung: stört am Pi nicht)

---

## Schnelle Orientierung wenn Kontext verloren

1. Lies dieses Doc komplett (~5 min).
2. Lies [CLAUDE.md](../CLAUDE.md) §9 (Sicherheit).
3. Cat-und-skimme
   [src/hexapod_description/urdf/hexapod.ros2_control.xacro](../src/hexapod_description/urdf/hexapod.ros2_control.xacro)
   — siehst den `<plugin>`-Block der getauscht werden muss.
4. Cat-und-skimme
   [src/hexapod_control/config/controllers.yaml](../src/hexapod_control/config/controllers.yaml)
   — `use_sim_time: true` ist der Phase-4-7-Übergabe-Punkt.
5. Frag den User nach dem Servo2040-Protokoll (definiert, aber nicht
   im Repo).
6. Lege `src/hexapod_hardware/` an, beginne mit Stufe B (Skelett).

[CLAUDE.md](../CLAUDE.md), [PHASE.md](../PHASE.md), und
[README.md](../README.md) sind die Top-Level-Orientierungs-Dokumente.
