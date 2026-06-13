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

## PS4 — Mapping (Block C1+, USB)

> Design-Prinzip: Teleop = reines UI. Es sendet Intents (`/cmd_vel`,
> `/cmd_body_height`, Service-Calls); State/Logik/Limits liegen im `gait_node`.
> Voller Plan + Stage-Aufteilung: `project_finalization/C_teleop.md`.

| PS4-Input | Effekt | Hinweis |
|---|---|---|
| **Linker Stick** | Fahren omnidirektional: Y=vor/zurück (linear.x), X=seitwärts (linear.y) — **analog** | nur mit Dead-Man |
| **Rechter Stick X** | Drehen (angular.z) | nur mit Dead-Man |
| **R1** (halten) | **Dead-Man** — Fahren nur während gehalten | Safety (Pflicht) |
| **L1** (halten) | „Langsam/Präzise" — halbes Tempo (`slow_factor`) | rein lokal |
| **L2 / R2** (Druck) | Körper **senken / heben um 1 cm** | clampt lokal + `gait_node`; nur STANDING |
| **△ Triangle** (Druck) | **Sit/Stand-Toggle** → `/hexapod_sit_stand_toggle` | gait_node löst nach State auf |
| **○ Circle** (lang) | **Shutdown** → `/hexapod_shutdown` | Long-Press, terminal (Relay aus) |
| **✕ Cross** (lang) | **Show-Pose** (B4) — **aktuell DEAKTIVIERT** (`show_enabled:false`) | leg_changes/S6: aktuelle Show-Pose auf HW instabil → Teleop schickt weder `/hexapod_show_toggle` noch `/cmd_show`. Code bleibt; `show_enabled:=true` reaktiviert. |
| **D-Pad ←/→** | Gangart vorige/nächste (→ = next) | C2: Intent `/hexapod_cycle_gait`; nur STANDING |
| **D-Pad ↑/↓** | Schrittweite größer/kleiner | C2: Intent `/hexapod_adjust_step_length`; clampt |

**Tempo:** Dosierung über Stick-Auslenkung (analog) + L1=langsam. „Weiter/schneller"
über Schrittweite (D-Pad ↑/↓, C2).

**Höhe-Constraint:** L2/R2 ändern ein lokales Ziel (geclampt auf
`body_height_min/max`) und publishen `/cmd_body_height`; `gait_node` clampt
nochmals und ignoriert ≠STANDING (Warning-Log).

**Long-Press:** Circle/Cross feuern erst nach `longpress_sec` (Default 0.8 s) —
gegen Versehen. Triangle = normaler Druck (Rising-Edge).

## Achsen-/Button-Indizes (PS4 USB, ros-jazzy-joy)

In [config/ps4_usb.yaml](config/ps4_usb.yaml) konfiguriert (alle Indizes/Vorzeichen/
Skalen/Schwellen YAML-tunbar). Defaults:

| Achse | Belegung | Button | Belegung |
|---|---|---|---|
| 0 | Linker Stick X → seitwärts | 0 | Cross (Show-Pose-Hook, lang) |
| 1 | Linker Stick Y → vor/zurück | 1 | Circle (Shutdown, lang) |
| 2 | L2 analog (idle +1 / gedrückt −1) | 2 | Triangle (Sit/Stand-Toggle) |
| 3 | Rechter Stick X → drehen | 3 | Square (frei) |
| 4 | Rechter Stick Y (frei, B4) | 4 | L1 (langsam) |
| 5 | R2 analog | 5 | R1 (Dead-Man) |
| 6/7 | D-Pad X/Y → Gangart / Schrittweite (C2) | … | … |

> Vorzeichen (`sign_lx/ly/rx`) und Indizes USB vs BT verifizieren:
> `ros2 topic echo /joy` und Sticks/Buttons live bewegen.

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
