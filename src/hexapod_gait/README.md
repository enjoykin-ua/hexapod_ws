# hexapod_gait

ROS-Knoten für Stand-Pose und Gait-Engine. Konsumiert
[hexapod_kinematics](../hexapod_kinematics/) für die IK pro Bein,
publiziert `JointTrajectory` an die 6 JTC-Controller aus Phase 4.

## Komponenten

| Datei | Zweck |
|---|---|
| [stand_node.py](hexapod_gait/stand_node.py) | One-shot rclpy-Knoten: fährt alle 6 Beine in Stand-Pose und beendet sich |
| [gait_node.py](hexapod_gait/gait_node.py) | 50 Hz Timer-Loop, cmd_vel-Subscriber, Engine-Tick → 6 JointTrajectory-Pubs |
| [gait_engine.py](hexapod_gait/gait_engine.py) | Pure-Python State-Machine STANDING / WALKING / STOPPING / STARTUP_RAMP + Body-Frame-Mapping |
| [gait_patterns.py](hexapod_gait/gait_patterns.py) | `GaitPattern`-Dataclass + Presets `TRIPOD`, `SINGLE_LEG_1..6`, erweiterbar für Wave/Ripple |
| [trajectory_gen.py](hexapod_gait/trajectory_gen.py) | Pure-Python `swing_traj` (Halbsinus) + `stance_traj` (linear) im Bein-Frame |

## Launch-Quickstart

### Stand-Pose anfahren

```bash
ros2 launch hexapod_gait stand.launch.py
```

Fährt alle 6 Beine in
`(radial=0.27, 0, body_height=-0.052)` (Stufe-F-Default mit 5 mm
globaler Penetration für JTC-Tracking-Lag). Beendet sich nach ~5 s.

### Stand-up / Aufstehen (Phase 13 Stage 0.4)

Auf der echten Hardware ist `stand_node` (one-shot, cartesian) **nicht** der
Aufsteh-Pfad — das macht der **STARTUP_RAMP-State** in `gait_node`/`gait_engine`:

- Nach dem HW-Plugin-Init (`hexapod_hardware` Stage 0.3) stehen die Servos auf
  der **power_on_mid-Pose** (Servo-Mitte 1500 µs: Femurs ~27° hoch, Beine
  angehoben/eingezogen, Bauch liegt auf).
- `gait_node` liest diese Pose beim ersten `/joint_states`-Empfang und rampt
  per Smooth-Step (`s = p²(3−2p)`) **alle 6 Beine gleichzeitig** in Joint-Space
  zur Stand-Pose hoch — der Hexapod **steht vom Bauch auf**. Auto-Übergang →
  STANDING bei `progress ≥ 1`; `cmd_vel` wird während des Ramps ignoriert.
- **all-6 simultan, nicht Tripod 3+3** (Stage-0 DL-7): Beim Aufstehen vom Bauch
  ist Bauch/Boden die Stütze, nicht die Beine — kein Stativ nötig. Tripod 3+3
  braucht man nur, wenn der Körper allein auf den Beinen steht und Füße
  umgesetzt werden (z. B. Bein-Radius im Stand ändern). all-6 verteilt zudem die
  Lift-Last auf 6 statt 3 Servos.
- **In-Limits garantiert**: Smooth-Step interpoliert monoton zwischen
  power_on_mid und Stand-Pose; beide liegen in den URDF-Limits → jeder
  Zwischenwert auch. Kein Stage-0.5/0.6-Plugin-Freeze während des Aufstehens
  (Test `test_power_on_mid_start_ramp_in_limits`).
- Param `auto_standup_duration` (Default 4.0 s) steuert die Ramp-Dauer. Das
  obsolete `suspended`-Preset (femur=+1.45) ist **nicht** mehr der Startpunkt
  (war Pre-0.3).

### Gait starten

```bash
# Default: STANDING bis cmd_vel kommt
ros2 launch hexapod_gait gait.launch.py

# Demo-Mode: läuft sofort vorwärts ohne externe cmd_vel
ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05

# Demo-Mode: läuft im Bogen
ros2 launch hexapod_gait gait.launch.py \
  default_linear_x:=0.03 default_angular_z:=0.15

# Stufe-E-Backward-Compat: nur ein Bein schwingt
ros2 launch hexapod_gait gait.launch.py \
  gait_pattern:=single_leg_1 default_linear_x:=0.05

# Phase 11 Stage D: mit Preset-File starten
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
```

### Phase 11 — Live-Param-Tuning + Preset-Workflow

- Stage A — alle 14 gait_node-Params sind live via `ros2 param set` /
  `rqt_reconfigure` tunbar (Range-Constraints + atomic-all-or-nothing-
  Validation). Details in [gait_node.py](hexapod_gait/gait_node.py)
  `_GAIT_PARAMS`-Tabelle.
- Stage D — Preset-YAMLs unter [`config/presets/`](config/presets/),
  ladbar via `params_file:=<path>.yaml`-Launch-Arg. Erzeugung via
  `ros2 param dump /gait_node ...`.
- **Convenience:** [`tools/hexapod-shell-aliases.sh`](../../tools/hexapod-shell-aliases.sh)
  bietet `hexapod-save-walking-params`, `hexapod-load-walking-preset`,
  `hexapod-save-cal` etc. Opt-in: in `~/.bashrc` aufnehmen.
- **Setup-Doku:** [`docs_raspi/phase_11_rqt_setup.md`](../../docs_raspi/phase_11_rqt_setup.md)
  beschreibt rqt-Multi-Plugin-Aufbau + Save/Load-Workflows.
- **Workshop-Doku** (Stage E):
  [`docs_raspi/phase_11_sim_tuning_workshop.md`](../../docs_raspi/phase_11_sim_tuning_workshop.md)
  mit 6 Test-Szenarien (defensive/demo/aggressive Walk, Drehen,
  Kurvenfahrt, body_height-Variation) — Sim-Manual für sinnvolles
  Walking-Tuning.

### Walk steuern via cmd_vel

```bash
# Vorwärts
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05}}'

# Drehen gegen Uhrzeigersinn
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'

# Seitwärts +Y (links)
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {y: 0.05}}'

# Bogen
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.03}, angular: {z: 0.2}}'

# Stoppen
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{linear: {x: 0.0}}'
```

## cmd_vel-Format

`geometry_msgs/Twist`. Verwendete Felder:

| Feld | Bedeutung | Range |
|---|---|---|
| `linear.x` | Vorwärts/Rückwärts (m/s, base_link +X) | clamped auf `±linear_max` |
| `linear.y` | Seitwärts (m/s, base_link +Y = links) | clamped auf `±linear_max` |
| `angular.z` | Drehung (rad/s, +z = gegen Uhrzeigersinn von oben) | clamped auf `±linear_max / R_max` |

**`linear.z`, `angular.x`, `angular.y` werden ignoriert** — Body bleibt
horizontal in Phase 5.

**Clamping** (Stufe-H-Design-Entscheidung 1): wenn die maximale
Bein-Geschwindigkeit `|v_at_leg_mount|` über `linear_max` läuft, werden
alle drei Inputs proportional skaliert. Bewegungs-Richtung bleibt
erhalten, nur langsamer. Engine loggt `cmd_vel clamped`-Warning
(throttled 2 s).

## Knoten-Parameter

`gait_node` (stand:`stand.launch.py`, gait:`gait.launch.py`):

| Parameter | Default | Bedeutung |
|---|---|---|
| `gait_pattern` | `'tripod'` | Preset aus `GAIT_PRESETS`: tripod, single_leg_1..6 |
| `step_length_max` | `0.05` | Max Schritt-Länge (m) — definiert `linear_max = step_length_max / stance_duration` |
| `default_linear_x` | `0.0` | Fallback Vorwärts (m/s) wenn keine cmd_vel ankommt |
| `default_linear_y` | `0.0` | Fallback Seitwärts (m/s) |
| `default_angular_z` | `0.0` | Fallback Drehung (rad/s) |
| `cmd_vel_timeout` | `0.5` | Sekunden ohne cmd_vel → Fallback auf Defaults |
| `cycle_time` | `2.0` | Sekunden pro Tripod-Cycle (1 s Swing + 1 s Stance) |
| `step_height` | `0.03` | Schwung-Höhe (m über Stand-Pose) |
| `body_height` | `-0.052` | Stand-Pose Foot-Z (m, Bein-Frame) |
| `radial_distance` | `0.27` | Stand-Pose Foot-X (m, Bein-Frame) |
| `tick_rate` | `50.0` | Engine-Loop-Rate (Hz) |
| `time_from_start_factor` | `2.0` | JTC-Lookahead = factor / tick_rate |

## State-Machine

```
        cmd_vel(|v|>eps)             |v|≈eps
STANDING ────────────────► WALKING ────────────► STOPPING
   ▲                          ▲                      │
   │                          │ cmd_vel(|v|>eps)     │ alle Beine
   │                          └──────────────────────┘ settled
   │                                                  │
   └──────────────────────────────────────────────────┘
                    auto-Transition
```

- **STANDING**: alle 6 Beine in Stand-Pose, kein Cycle.
- **WALKING**: Tripod-Pattern, Foot-Vortrieb gemäß cmd_vel mit
  Mount-Yaw-Rotation pro Bein.
- **STOPPING**: Beine in der Luft schwingen mit eingefrorener step_vec
  fertig (max 1 s bei cycle_time=2). Stütz-Beine interpolieren in
  0.3 s zu Neutral. Worst-Case-Latenz: 1.3 s (cycle_time=2) bzw. 0.8 s
  (cycle_time=1).

## Gait-Pattern erweitern

Neue Gangart hinzufügen = neue Konstante in `gait_patterns.py`:

```python
WAVE = GaitPattern(
    name='wave',
    phase_offset_per_leg={1: 0.0, 2: 1/6, 3: 2/6,
                          4: 3/6, 5: 4/6, 6: 5/6},
    swing_duty=1/6,
)

GAIT_PRESETS = {..., 'wave': WAVE}
```

→ Engine-Code muss **null** angefasst werden. Pattern-Logik ist
identisch, nur die Daten unterscheiden sich. Siehe Stufe-F-Design-
Entscheidung 4 in
[docs/phase_5_progress.md](../../docs/phase_5_progress.md).

## Konzept-Hintergrund

- **IK-Math**:
  [docs/phase_5_ik_explained.md](../../docs/phase_5_ik_explained.md)
- **Gait-State-Machine + Body-Frame-Mapping + Tripod-Math**:
  [docs/phase_5_gait_explained.md](../../docs/phase_5_gait_explained.md)
- **Phase-5-Verlauf**:
  [docs/phase_5_progress.md](../../docs/phase_5_progress.md)
- **Test-Anleitungen pro Stufe**:
  [docs/phase_5_stage_C..H_test_commands.md](../../docs/)

## Tests aufrufen

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_gait
colcon test-result --verbose --test-result-base build/hexapod_gait
```

Erwartet: **3 Tests, 0 Failures, 1 skipped**. Aktuell nur Style-Tests
(flake8, pep257); funktionale Tests werden Pure-Python via Smoke-
Tests in den Stufen-Test-Doks abgedeckt.

## Stolperfallen (aus Live-Bringup destilliert)

1. **Stale Prozesse** — `gait_node`, `stand_node`,
   `foot_contact_publisher`, `ros2 topic pub` — pro Test-Lauf
   komplett cleanen. Cleanup-Snippet in den
   `phase_5_stage_*_test_commands.md`.
2. **JTC-Tracking-Lag** im Continuous-Pub-Mode. Lösung:
   `body_height = -0.052` (5 mm Penetration global), Detail in
   Stufe-F-Designentscheidung.
3. **`use_sim_time` + `get_clock().now()` Race** — Timer-Logik
   nutzt `time.monotonic()` (Wall-Clock), nicht Sim-Time.
4. **cmd_vel mit `--once`** triggert nicht sicher Walk — wegen
   `cmd_vel_timeout` 0.5 s. Stattdessen `--rate 10` für
   kontinuierliche Pubs.
5. **`single_leg_*` Pattern + cmd_vel** — Wenn nur ein Bein im
   Pattern aktiv ist, schwingt es nicht zwingend in Body-X-Richtung.
   `gait_pattern:=single_leg_1` ist primär ein Stufe-E-
   Backward-Compat-Modus, kein Walk-Mode.
