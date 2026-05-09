# Phase 6 — Teleop: Handoff aus Phase 5

> **Lesehinweis:** dieses Doc ist als **Single-Entry-Point** für einen
> neuen Programmierer / KI-Agenten gedacht, der in Phase 6 (Joystick →
> cmd_vel) startet und einen präzisen Überblick braucht **was wo liegt
> und wie es angesprochen wird** — ohne durch alle Phase-5-Stufen-
> Dokus wühlen zu müssen.
>
> Vertiefung optional in
> [phase_5_progress.md](phase_5_progress.md),
> [phase_5_gait_explained.md](phase_5_gait_explained.md),
> [phase_5_ik_explained.md](phase_5_ik_explained.md).

---

## TL;DR

Phase 5 hat einen **omnidirektionalen Tripod-Gait** geliefert, gesteuert
über `/cmd_vel` (Twist). Phase-6-Aufgabe: PS-Controller / Tastatur →
Twist publishen. State-Machine, IK, Tripod-Sequenz, Stand-Pose, Stop-
Logic sind alle erledigt und stabil.

**Kürzester Smoke-Test ob alles funktioniert:**

```bash
# Drei Terminals, dann ein 4. mit Topic-Pub:
T1: ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=true
T2: ros2 launch hexapod_gait stand.launch.py     # warten ~5s
T3: ros2 launch hexapod_gait gait.launch.py
T4: ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05}}'
# → Roboter sollte vorwärts laufen
```

---

## Codebase-Tour

### Pakete im Workspace

```
~/hexapod_ws/src/
├── hexapod_description/      # URDF/Xacro + ros2_control + Sensoren
├── hexapod_gazebo/           # Plain-Sim (Phase 3, ohne Controller)
├── hexapod_control/          # controllers.yaml (1× JSB + 6× JTC)
├── hexapod_bringup/          # Standard-Sim mit Controllern (Phase 4+5)
├── hexapod_kinematics/       # Pure-Python IK/FK (kein rclpy!)
├── hexapod_sensors/          # Foot-Contact Gazebo→ROS Adapter
├── hexapod_gait/             # stand_node + gait_node + State-Machine
├── hexapod_teleop/           # ⚠️ noch nicht angelegt — Phase-6-Aufgabe
└── hexapod_hardware/         # ⚠️ noch nicht angelegt — Phase-7-C++ HW-IF
```

### Phase-6-relevante Files (was du wirklich anschauen solltest)

| Datei | Zweck |
|---|---|
| [src/hexapod_gait/hexapod_gait/gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py) | Subscriber auf `/cmd_vel`. Hier siehst du genau was die Engine erwartet. |
| [src/hexapod_gait/launch/gait.launch.py](../src/hexapod_gait/launch/gait.launch.py) | Alle gait-Parameter mit Defaults und Beschreibungen. |
| [src/hexapod_gait/README.md](../src/hexapod_gait/README.md) | Vollständige Param-Tabelle, State-Machine-Diagramm, Erweiterungs-Anleitung. |
| [src/hexapod_gait/hexapod_gait/gait_patterns.py](../src/hexapod_gait/hexapod_gait/gait_patterns.py) | Verfügbare Gangarten als Daten-Konstanten + `GAIT_PRESETS`-Dict. |

### Files, die Phase 6 in Ruhe lassen kann

Funktionieren wie sie sind. Nur anschauen falls du tiefe Probleme
debuggst:

- `gait_engine.py` — State-Machine + Body-Frame-Mapping
- `trajectory_gen.py` — swing_traj + stance_traj
- `stand_node.py` — one-shot Stand-Pose
- `hexapod_kinematics/*` — IK-Library
- `hexapod_sensors/*` — Foot-Contact-Adapter
- `hexapod_description/urdf/*` — URDF / xacro
- `hexapod_control/config/controllers.yaml` — JTC-Config

---

## ROS-System im Live-Run

Wenn alle Launch-Files aus dem TL;DR laufen, ist das Topic/Node-Bild:

### Nodes

| Node | Quelle | Was er macht |
|---|---|---|
| `/gait_node` | hexapod_gait | Subscribt `/cmd_vel`, publisht 6× JTC-Goals @ 50 Hz |
| `/stand_node` | hexapod_gait | Einmaliger Pub für Stand-Pose, beendet sich (existiert nur kurz) |
| `/foot_contact_publisher` | hexapod_sensors | 6× `/leg_<n>/foot_contact` (Bool) @ 50 Hz |
| `/controller_manager` | gz_ros2_control | Hostet die 7 Controller |
| `/joint_state_broadcaster` | controller_manager | Publisht `/joint_states` aus 18 Joint-States |
| `/leg_<n>_controller` | controller_manager | JTC pro Bein, n=1..6, subscribt `/leg_<n>_controller/joint_trajectory` |
| `/robot_state_publisher` | ros-jazzy-robot-state-publisher | URDF→TF |
| `/ros_gz_bridge` | ros_gz_bridge | Gazebo↔ROS Bridge (Clock + Foot-Contact) |

Inspektion:

```bash
ros2 node list
ros2 node info /gait_node
```

### Topics — was Phase 6 wissen muss

**Inputs** (Phase 6 publisht hier):

| Topic | Type | Wer subscribt | Hinweis |
|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | `/gait_node` | **Phase-6-Hauptkanal**. Pub-Rate ≥ 2 Hz. |

**Outputs** (Phase 6 könnte konsumieren falls nötig):

| Topic | Type | Wer publisht | Was du damit anfangen kannst |
|---|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | JSB | Alle 18 Joint-Positionen + Velocities. Für Diagnose / Visualisierung. |
| `/leg_<n>/foot_contact` | `std_msgs/Bool` | `/foot_contact_publisher` | Bodenkontakt pro Bein. Für Anzeige am Joystick-UI / Status-LEDs. |
| `/tf`, `/tf_static` | `tf2_msgs/TFMessage` | RSP | Vollständiger TF-Tree. |
| `/clock` | `rosgraph_msgs/Clock` | gz_ros2_control | Sim-Zeit. Phase 6 braucht das normalerweise nicht direkt. |

**Internal** (lass in Ruhe):

| Topic | Type | Wer publisht/subscribt | Notiz |
|---|---|---|---|
| `/leg_<n>_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | gait_node → JTC | gait_node-internal. Phase 6 fasst das nicht an. |
| `/leg_<n>_controller/state` | `control_msgs/JointTrajectoryControllerState` | JTC | JTC-Internal-Telemetrie. |
| `/foot_contact_leg_<n>` | `ros_gz_interfaces/Contacts` | gz-bridge | Gazebo-Sensor-Roh-Output, in Bool gewrappt durch foot_contact_publisher. |

Inspektion:

```bash
ros2 topic list
ros2 topic info /cmd_vel              # zeigt Type + Pub/Sub-Count
ros2 topic echo /joint_states         # live joint values
ros2 topic hz /cmd_vel                # rate-check
```

### Parameter

`/gait_node` — alle live abfragbar via `ros2 param get`:

| Parameter | Default | Bedeutung |
|---|---|---|
| `gait_pattern` | `'tripod'` | Preset-Name aus `GAIT_PRESETS` |
| `step_length_max` | `0.05` | Max Schritt-Länge (m). Definiert `linear_max`. |
| `default_linear_x` | `0.0` | Fallback Vorwärts (m/s) wenn keine cmd_vel |
| `default_linear_y` | `0.0` | Fallback Seitwärts (m/s) |
| `default_angular_z` | `0.0` | Fallback Drehung (rad/s) |
| `cmd_vel_timeout` | `0.5` | Sekunden ohne cmd_vel → Defaults |
| `cycle_time` | `2.0` | Tripod-Cycle-Periode (s) |
| `step_height` | `0.03` | Schwung-Höhe (m über Stand-Pose) |
| `body_height` | `-0.052` | Stand-Pose Foot-Z (m, Bein-Frame) |
| `radial_distance` | `0.27` | Stand-Pose Foot-X (m, Bein-Frame) |
| `tick_rate` | `50.0` | Engine-Loop-Rate (Hz) |
| `time_from_start_factor` | `2.0` | JTC-Lookahead = factor / tick_rate |

Inspektion:

```bash
ros2 param list /gait_node
ros2 param get /gait_node gait_pattern
ros2 param get /gait_node step_length_max
```

**Nicht runtime-mutable**: alle Engine-Params sind bei Launch fix
gesetzt. Pattern-Wechsel oder cycle_time-Änderung braucht Node-
Restart. Stufe-F's `enable_walk`-Live-Toggle wurde in Stufe G durch
cmd_vel-Activity-Detection ersetzt.

---

## cmd_vel-Interface

- **Topic:** `/cmd_vel`
- **Type:** `geometry_msgs/Twist`
- **Pub-Rate:** **mindestens 2 Hz**, sonst tritt Activity-Timeout 0.5 s
  ein und Engine fällt auf `default_*` zurück (typisch 0 → STANDING).

| Feld | Bedeutung | Range (clamped) |
|---|---|---|
| `linear.x` | Vorwärts/Rückwärts (m/s, base_link +X = vorne) | ±0.05 |
| `linear.y` | Seitwärts (m/s, base_link +Y = links) | ±0.05 |
| `angular.z` | Drehung (rad/s, +z = gegen Uhrzeigersinn von oben) | ±0.46 |

**Andere Felder** (`linear.z`, `angular.x`, `angular.y`) werden
ignoriert — Body bleibt horizontal in Phase 5.

### Clamping bei Kombi-Motion

Engine clampt **proportional über alle drei Komponenten**: wenn das
schnellste Bein über `linear_max` rauskommt, werden alle drei Werte
mit demselben Faktor runterskaliert.

**Konsequenz für Joystick-Mapping:** Du kannst die Stick-Werte naiv
auf den Twist mappen, Engine sorgt für die korrekte Skalierung. Stick
voll-vorne + voll-rechts (Diagonal-Walk) wird automatisch konsistent
gehandhabt.

### Stoppen

`(linear.x, linear.y, angular.z) ≈ (0, 0, 0)` triggert STOPPING.
Worst-Case-Latenz **1.3 s** bei `cycle_time=2.0` (Default).

### Wo das im Code lebt

- Subscriber-Definition:
  [gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py),
  Zeilen ~`self.create_subscription(Twist, '/cmd_vel', ...)`.
- Activity-Timeout-Logic: `_resolve_command` in derselben Datei.
- Clamping + State-Übergang: `set_command` in
  [gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py).

---

## Verfügbare Gangarten

Definiert in
[gait_patterns.py](../src/hexapod_gait/hexapod_gait/gait_patterns.py)
als `GAIT_PRESETS`-Dict:

| Preset-Name | Beine simultan in der Luft | Verwendung |
|---|---|---|
| `tripod` | 3 von 6 (Default) | Standard-Walk, Phase 6 |
| `single_leg_1` … `single_leg_6` | nur das genannte Bein | Stufe-E-Backward-Compat, Demo, Diagnose |

Auswahl per Launch-Param:

```bash
ros2 launch hexapod_gait gait.launch.py gait_pattern:=tripod
ros2 launch hexapod_gait gait.launch.py gait_pattern:=single_leg_3
```

**Neue Gangart hinzufügen** = neue Konstante in `gait_patterns.py`
+ Eintrag in `GAIT_PRESETS`. Engine-Code wird **null** angefasst.
Beispiel für Wave-Gait:

```python
WAVE = GaitPattern(
    name='wave',
    phase_offset_per_leg={1: 0.0, 2: 1/6, 3: 2/6,
                          4: 3/6, 5: 4/6, 6: 5/6},
    swing_duty=1/6,
)
GAIT_PRESETS = {..., 'wave': WAVE}
```

Hintergrund in [phase_5_gait_explained.md](phase_5_gait_explained.md)
("Gait-Pattern als Daten").

---

## Empfehlung für PS-Controller-Mapping

| Stick | Twist-Feld | Skala |
|---|---|---|
| Linker Stick Y (vor/zurück) | `linear.x` | Stick [-1, 1] → [-0.05, +0.05] m/s |
| Linker Stick X (seitlich) | `linear.y` | Stick [-1, 1] → [-0.05, +0.05] m/s |
| Rechter Stick X | `angular.z` | Stick [-1, 1] → [-0.46, +0.46] rad/s |

**Deadzone:** Stick-Werte mit `|x| < 0.1` als 0 publishen — sonst
triggert Float-Noise vom Stick die Engine zwischen STANDING und
WALKING (`_V_BODY_EPSILON = 1e-4` in der Engine).

**Vorzeichen-Konvention prüfen:** PS-Sticks haben oft Y nach unten
positiv. Ggf. invertieren damit "Stick nach vorne" → `linear.x > 0`.

**Pub-Rate:** ≥ 2 Hz, empfohlen 10–20 Hz. Engine cached den letzten
Wert für 0.5 s.

**ROS-Pakete für Joystick-Input** (nicht in Phase 5 gebaut, aus
Standard-Repos):

```bash
sudo apt install ros-jazzy-joy ros-jazzy-joy-teleop
# oder selbst implementieren mit dem `joy` Topic (sensor_msgs/Joy)
```

---

## Demo-Mode für Schnelltests ohne Joystick

Engine fällt nach 0.5 s ohne cmd_vel auf `default_*`-Werte zurück.
Setzt man die per Launch hoch, läuft der Roboter sofort:

```bash
# Roboter läuft sofort vorwärts:
ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05

# Bogen-Demo:
ros2 launch hexapod_gait gait.launch.py \
  default_linear_x:=0.03 default_angular_z:=0.15

# Reine Drehung:
ros2 launch hexapod_gait gait.launch.py default_angular_z:=0.3
```

Nützlich um den Stack zu prüfen ohne PS-Controller anzustöpseln.

---

## Manueller cmd_vel-Test (Debugging)

```bash
# Vorwärts mit 5 cm/s (kontinuierlich pumpen):
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05}}'

# Drehen gegen Uhrzeigersinn:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'

# Bogen:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.03}, angular: {z: 0.2}}'

# Hard-Stop:
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{}'
```

---

## Diagnose-Cheatsheet

```bash
# 1. Läuft alles?
ros2 node list
ros2 control list_controllers           # 1× JSB + 6× JTC alle "active"

# 2. cmd_vel kommt an?
ros2 topic info /cmd_vel                # Pub-Count > 0?
ros2 topic echo /cmd_vel                # Werte plausibel?

# 3. Was macht die Engine?
ros2 topic echo /leg_1_controller/joint_trajectory  # JTC-Goals von gait_node

# 4. Joints folgen?
ros2 topic echo /joint_states           # 18 Werte ändern sich sichtbar?

# 5. Foot-Contact-Status?
for i in 1 2 3 4 5 6; do
  echo "leg_$i:"
  ros2 topic echo /leg_$i/foot_contact std_msgs/msg/Bool --once
done

# 6. Engine-Params live abfragbar:
ros2 param dump /gait_node

# 7. Body-Pose in Sim:
gz model -m hexapod -p
```

---

## Stolperfallen aus Phase-5-Live-Tests

1. **Stale `ros2 topic pub`-Prozesse** im Hintergrund publishen
   ungewollte cmd_vel. Pre-Test-Cleanup:
   ```bash
   pkill -f "ros2 topic pub"
   ```
2. **`--once` reicht nicht**: nach 0.5 s Activity-Timeout fällt Engine
   auf `default_*` (typisch 0) zurück. Always `--rate 10` oder
   ähnlich.
3. **Yaw-Drift ~1.35°/m** bei langen Geradeaus-Strecken — bekannte
   Phase-5-Sim-Limitation. Phase 6 kompensiert das durch
   User-Korrektur am Joystick.
4. **DK-3-Stopp-Latenz 1.3 s** mit Default `cycle_time=2.0`. Falls
   Phase 6 schnellere Reaktion will: `cycle_time:=1.0` beim Launch
   setzen → Latenz 0.8 s. Schneller geht JTC nicht stabil.
5. **Stale gait_node/stand_node-Prozesse** zwischen Test-Iterationen.
   Cleanup-Snippet aus den Stufen-Test-Dokus übernehmen wenn
   Multi-Publisher-Probleme auftauchen.
6. **`use_sim_time=true`** ist Default in allen Launches. Wenn du
   Phase-6-Code mit Real-Time-Wallclock testest: explizit
   `use_sim_time:=false` setzen oder die Engine arbeitet mit
   `time.monotonic()` (wall-clock) intern eh.

---

## Was du NICHT brauchst zu wissen

- IK-Math (closed-form, deterministisch, läuft automatisch)
- State-Machine-Implementation (auto-Übergänge funktionieren)
- Trajektorien-Form (Halbsinus + Linear, nicht zu tunen)
- Stance-Penetration-Workaround (`body_height=-0.052` ist gesetzt,
  lass es so)
- Phase-5-Stufen-Geschichte (Stufen A-I sind durch)

Alle Details auf Anfrage in
[phase_5_gait_explained.md](phase_5_gait_explained.md).

---

## Phase-7-Vorausschau (Hardware-Port)

Phase 7 wird `controllers.yaml` mit `use_sim_time: false` und
`body_height = -0.047` (statt -0.052, weil echte Servos keinen
JTC-Tracking-Lag haben) anpassen müssen. Das ist Phase-7-Aufgabe,
nicht Phase 6. **Phase-6-Teleop-Code läuft mit beiden Konfigurationen
unverändert** — Twist-Interface ist gleich.

---

## Schnelle Orientierung wenn Kontext verloren

Wenn du in eine neue Session startest und kein Hintergrund-Wissen hast:

1. Lies dieses Doc komplett (~5 min).
2. Schau in [src/hexapod_gait/README.md](../src/hexapod_gait/README.md)
   für Param-Tabelle + Komponenten-Übersicht.
3. Cat-und-skimme
   [src/hexapod_gait/hexapod_gait/gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py)
   (~150 LOC) — siehst die cmd_vel-Subscription und Param-Defaults.
4. Cat-und-skimme
   [src/hexapod_gait/launch/gait.launch.py](../src/hexapod_gait/launch/gait.launch.py) —
   alle Args mit Beschreibungen.
5. Smoke-Test aus dem TL;DR fahren — wenn Roboter läuft, ist der
   Phase-5-Stack OK.
6. Phase 6 implementieren — neues Paket
   `src/hexapod_teleop/` anlegen, Joy-Subscriber → Twist-Publisher
   bauen.

[CLAUDE.md](../CLAUDE.md) und [PHASE.md](../PHASE.md) sind die
Top-Level-Orientierungs-Dokumente, die generell für alle Sessions
gelten.
