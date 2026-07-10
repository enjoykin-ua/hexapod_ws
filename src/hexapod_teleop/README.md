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
| **L2 / R2** (Druck, ohne R1) | **Stance-Modus tiefer / höher** (tief/mittel/hoch) | Stage 1: Intent `/hexapod_cycle_stance`; nur STANDING. Mit R1 = Show-Tibia-Curl (B4.11) |
| **△ Triangle** (Druck) | **Sit/Stand-Toggle** → `/hexapod_sit_stand_toggle` | gait_node löst nach State auf |
| **○ Circle** (lang) | **Shutdown** → `/hexapod_shutdown` | Long-Press, terminal (Relay aus) |
| **✕ Cross** (lang) | **Show-Pose** (B4) — **aktuell DEAKTIVIERT** (`show_enabled:false`) | leg_changes/S6: aktuelle Show-Pose auf HW instabil → Teleop schickt weder `/hexapod_show_toggle` noch `/cmd_show`. Code bleibt; `show_enabled:=true` reaktiviert. |
| **D-Pad ←/→** | Gangart vorige/nächste (→ = next) | C2: Intent `/hexapod_cycle_gait`; nur STANDING |
| **D-Pad ↑/↓** | **Tempo-Preset schneller/langsamer** (langsam/mittel/schnell/aggressiv) | H2: `cycle_time` am gait_node + eigene Scales (`_TEMPO_MODES`); nur STANDING (gait-Guard). Ersetzt das C3-Schrittweiten-Binding — der Service `/hexapod_adjust_step_length` bleibt (ohne Teleop-Binding) |

**Tempo (H2):** Dosierung über Stick-Auslenkung (analog) + L1=langsam; die **Stufe**
über D-Pad ↑/↓ (Tempo-Presets). Die Schrittweite selbst ist per Stance-Modus
gedeckelt (`step_length_max`, gait_node) und wird vom Stick ohnehin moduliert.

### Tempo-Presets (Block H2) — Konzept

Tempo = **nur** `cycle_time` (gait_node) + joy-Scales (Teleop) — die Lauf-Envelope
(Bein-Hülle) hängt an Schrittweite/Hub/Höhe/Radius, nicht am Tempo, darum brauchen
die Stufen keine eigene Envelope-Validierung. Die Tabelle `_TEMPO_MODES`
(`joy_to_twist.py`) trägt `(name, cycle_time, linear_x/y_scale, angular_z_scale)`:

| Stufe | cycle_time | Scales (x/y/z) | Hinweis |
|---|---|---|---|
| langsam | 3.3 | 0.03 / 0.03 / 0.28 | |
| mittel | 2.6 | 0.04 / 0.04 / 0.35 | |
| **schnell (Boot)** | 2.0 | 0.05 / 0.05 / 0.46 | = YAML-Scales → erster D-Pad-Druck **sprungfrei** |
| aggressiv | 1.5 | 0.17 / 0.13 / 1.2 | User-erprobt; Scales > `linear_max` ⇒ Engine clampt (WARN, ok) |

*(Startwerte — Sim-Tuning H2.5 zieht die finalen Werte nach.)*

**Zwei-Schritt-Protokoll** (neues ROS2-Idiom hier: `rclpy.parameter_client.
AsyncParameterClient` = vorgefertigte Service-Clients auf die Param-Services eines
*fremden* Nodes, `/gait_node/set_parameters` etc., mit Future statt Blockieren):

1. D-Pad-Edge → `cycle_time` des Ziel-Presets als Param-Set-Request an den
   **gait_node** (dessen `standing_only`-Validator ist der EINE Tempo-Guard).
2. Erst im Future-done-Callback bei **Erfolg**: eigene Scales aus der Tabelle via
   `set_parameters` auf sich selbst (läuft durch die TLS-validate-then-apply-Mechanik
   → eigener Param-Server bleibt synchron).

Ablehnung (nicht STANDING), Service-Exception, gait_node abwesend oder ausbleibende
Antwort (2-s-Timeout-Lock gegen Request-Stau) ⇒ **lokal ändert sich nichts** — kein
halber Tempo-Wechsel (gait läuft alt, Teleop skaliert neu = inkonsistent).

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
| 6/7 | D-Pad X/Y → Gangart (C2) / Tempo-Preset (H2) | … | … |

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
| D-Pad ↑ macht langsamer statt schneller | D-Pad-Y-Vorzeichen | YAML: `sign_dpad_y: -1.0` |
| D-Pad ← dreht rechts (verkehrt) | D-Pad-X-Vorzeichen | YAML: `sign_dpad_x: -1.0` |
| L2/R2 funktioniert während Walk nicht | Engine-Constraint (STANDING-only) | Erst R1 loslassen, dann L2/R2 |
| Roboter rührt sich nicht obwohl R1 gehalten | D-Pad nicht erkannt | `ros2 topic echo /joy` — Achse 6/7 ändert sich? |
| Latenz spürbar | `joy_node` Default-Rate niedrig | `autorepeat_rate:=50.0` beim Launch |

## Tests

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_teleop
```

Funktionale Unit-Tests: `test_joy_to_twist.py` (Mapping/Dead-Man/Edge/Intents),
`test_live_scales.py` (TLS-Live-Tuning), `test_tempo_presets.py` (H2 Tempo-Cycle:
Tabelle, Sprungfrei-Invariante, Reject-/Timeout-Pfade), `test_bt_config.py` —
plus Style (flake8, pep257). Live-Verifikation:
[../../docs/phase_6_stage_A_test_commands.md](../../docs/phase_6_stage_A_test_commands.md)
+ `project_finalization/H2_speed_presets_test_commands.md` (Tempo).
