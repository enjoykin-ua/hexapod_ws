# hexapod_teleop

Teleop-Knoten für den Hexapod. Stufe A (Phase 6): PS4-Controller via
USB. Stufe B (geplant): BT-Pairing.

Konsumiert `/joy` (von `joy_node` aus `ros-jazzy-joy`), publisht
`/cmd_vel` (geometry_msgs/Twist) und `/cmd_body_height`
(std_msgs/Float64).

## Quickstart

Voraussetzung: Phase-5-Stack läuft (Sim + Stand-Pose + gait_node).

```bash
# Eigenes Terminal:
ros2 launch hexapod_teleop joy_teleop.launch.py
```

Default-Profile: `controller:=ps4_usb`. Andere Controller-YAMLs
können später dazukommen (`controller:=ps4_bt`, `controller:=ps5`).

## PS4 — Mapping (Stufe A, USB)

| PS4-Input | Effekt | Hinweis |
|---|---|---|
| **R1** (halten) | Dead-Man — Bewegung erlaubt | Pflicht für DK 5 |
| **D-Pad ↑** | Vorwärts | nur wenn R1 gehalten |
| **D-Pad ↓** | Rückwärts | nur wenn R1 gehalten |
| **D-Pad ←** | Drehen links (am Stand) | nur wenn R1 gehalten |
| **D-Pad →** | Drehen rechts (am Stand) | nur wenn R1 gehalten |
| **L2** (Trigger) | Body senken (-5 mm) | **nur wenn STANDING** |
| **R2** (Trigger) | Body anheben (+5 mm) | **nur wenn STANDING** |

**Body-Lift-Constraint:** L2/R2 publishen nur dann effektiv,
wenn der Roboter steht (Engine-State == STANDING). Während WALKING/
STOPPING wird die Eingabe von `gait_node` mit Warning-Log ignoriert.

**Multi-Direction:** D-Pad ↑ + ← gleichzeitig = Bogen vor-links
(Engine clampt proportional, Bogen-Form bleibt erhalten).

**L2/R2 Trigger-Logik:** Edge-Detection — ein Druck = ein Schritt.
Hold ändert nicht weiter. Loslassen + neu drücken für nächsten Schritt.

## Achsen-Indizes (PS4 USB, ros-jazzy-joy)

In [config/ps4_usb.yaml](config/ps4_usb.yaml) konfiguriert. Defaults:

| Index | Achse |
|---|---|
| 0 | Linker Stick X (nicht gemappt in Stufe A) |
| 1 | Linker Stick Y (nicht gemappt in Stufe A) |
| 2 | L2 analog (idle=+1.0, fully pressed=-1.0) |
| 3 | Rechter Stick X (nicht gemappt) |
| 4 | Rechter Stick Y (nicht gemappt) |
| 5 | R2 analog |
| 6 | D-Pad X (← = +1.0, → = -1.0 — verifizieren!) |
| 7 | D-Pad Y (↑ = +1.0, ↓ = -1.0) |

| Index | Button |
|---|---|
| 0 | Cross |
| 1 | Circle |
| 2 | Triangle |
| 3 | Square |
| 4 | L1 |
| 5 | R1 (Dead-Man) |
| 6 | L2 digital (nicht genutzt — wir nutzen analog axis_l2) |
| 7 | R2 digital (nicht genutzt) |

> Falls ein Mapping anders ist (BT vs USB, PS5 vs PS4):
> `ros2 topic echo /joy` und Indizes live notieren, dann YAML
> anpassen.

## Topics

**Subscribt:**
- `/joy` (`sensor_msgs/Joy`) — PS-Controller-State von `joy_node`.

**Publisht:**
- `/cmd_vel` (`geometry_msgs/Twist`) — Engine-Input. Twist enthält
  nur `linear.x` und `angular.z`, andere Felder bleiben 0.
- `/cmd_body_height` (`std_msgs/Float64`) — Absolute body_height in
  m. `gait_node` clampt + ignoriert wenn nicht STANDING.

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `/joy` zeigt nichts | Berechtigungen `/dev/input/js0` | User in Gruppe `input` aufnehmen, neu einloggen |
| Roboter fährt rückwärts statt vor | D-Pad-Y-Vorzeichen | YAML: `sign_dpad_y: -1.0` |
| D-Pad ← dreht rechts (verkehrt) | D-Pad-X-Vorzeichen | YAML: `sign_dpad_x: -1.0` |
| L2/R2 funktioniert während Walk nicht | Engine-Constraint (STANDING-only) | Erst R1 loslassen, dann L2/R2 |
| Roboter rührt sich nicht obwohl R1 gehalten | D-Pad nicht erkannt | `ros2 topic echo /joy` — Achse 6/7 ändert sich? |
| Latenz spürbar | `joy_node` Default-Rate niedrig | `autorepeat_rate:=50.0` beim Launch |

## Tests

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_teleop
```

Aktuell nur Style-Tests (flake8, pep257, copyright). Funktionale
Verifikation läuft live, siehe
[../../docs/phase_6_stage_A_test_commands.md](../../docs/phase_6_stage_A_test_commands.md).
