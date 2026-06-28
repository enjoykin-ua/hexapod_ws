# IMU-Balance — Allgemeine Befehls-Referenz (Simulation)

> **Zweck:** eine handliche Sammel-Referenz aller Befehle rund um den A5-Block (IMU-Balance) **in der
> Simulation** — granular (mehrere Terminals: Welt starten → aufstehen → loslaufen), alle Feature-
> Schalter, gruppierte Parameter, RViz parallel zu Gazebo. **Nur Sim**, nicht echte Hardware.
>
> Stand: Stufe-4-Kern komplett (S4-1/2/4/5/6 sim-verifiziert). Quelle der Befehle: die `stage_*_test_commands.md`
> + die Launch-Files (`hexapod_bringup`, `hexapod_gait`). Branch `imu_balance`.

---

## 0. Konventionen & Vorbereitung

**Sourcing — in JEDEM Terminal zuerst:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

**Bauen (nach Code-Änderungen):**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_gazebo hexapod_bringup hexapod_description hexapod_sensors --symlink-install
```

**Vor dem ersten `ros2 param set`:** einmal `ros2 daemon stop` (sonst „Node not found" durch stale Daemon).

**⚠️ Zwei Klassen von Parametern:**
- **`standing_only`** (`gait_pattern`, `body_height`, `cycle_time`, `tick_rate`, `radial_distance`,
  `standup_*` …): lassen sich **nur im STANDING** ändern (im WALKING abgelehnt). Am einfachsten **beim
  Launch** als Arg setzen, oder vor dem Loslaufen.
- **live-tunbar** (alle `leveling_*`, `tip_*`, `slope_*`, `adaptive_*`/`touchdown_*`, `slip_*`/`cliff_*`,
  `sensor_*`, `foot_contact_debug_enable`): jederzeit per `ros2 param set` (auch im Lauf).

**Node-Name** für alle `param set`/`param get`: `/gait_node`.

---

## 1. Bereich A — Simulation starten (granular, mehrere Terminals)

> Die „alte" Drei-Schritt-Prozedur: **(T1) Gazebo + Welt + Spawn** → **(T2) Aufstehen** → **(T3) Loslaufen**.
> Der Roboter steht über den **Auto-Standup** des `gait_node` auf (sobald T2 läuft). Die Ein-Befehl-
> Abkürzung (`*_walk.launch.py`, macht T1+T2 in einem) steht in [Anhang Z](#z-ein-befehl-abkürzungen).

### Terminal 1 — Gazebo + Welt laden + Roboter spawnen

Je nach Welt **einen** dieser Befehle:

```bash
# (a) Leere Welt (flacher Boden, gz-IMU) — der Standard
ros2 launch hexapod_bringup sim.launch.py world:=empty_imu.sdf

# (b) Rampe (flacher Anlauf → Hang → Plateau); Hangwinkel via slope_deg
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
#     weitere: slope_deg:=16.0  (steiler) · spawn_x:=-0.7 (Start vor dem Hang)

# (c) Graben / "Loch" (zwei Plattformen + Lücke quer zur Laufrichtung)
ros2 launch hexapod_bringup trench.launch.py trench_depth:=0.02 trench_width:=0.10
#     weitere: trench_depth:=0.025 · trench_x:=0.0 (Graben-Mitte)

# (d) Scharfe Stufe ab/auf (signiert: + = ab, - = auf)
ros2 launch hexapod_bringup step.launch.py step_drop:=0.02
#     weitere: step_drop:=0.04 (Grenze fixed-timing) · step_drop:=-0.02 (Stufe auf, Gegenprobe)

# (e) Statisch gekippte Box (für Stufe-2-STANDING-Leveling; Roboter spawnt flach, Box gepitcht)
ros2 launch hexapod_bringup slope.launch.py slope_deg:=8.0
```

> **Wichtig (IMU welt-referenziert):** der Roboter spawnt **flach** (Default), sonst maskiert ein
> gepitchter Spawn die echte Hang-Neigung. Bei Rampe/Graben/Stufe ist das schon so eingestellt.
> `sim.launch.py` startet außerdem die Controller (joint_state_broadcaster + 6 Bein-Controller),
> die IMU- und Fußkontakt-Bridges, den `foot_contact_publisher` und den `imu_monitor`.

`sim.launch.py`-Args (auch von ramp/trench/step durchgereicht): `world`, `spawn_x`, `spawn_z`,
`spawn_roll_deg`, `spawn_pitch_deg`, `enable_imu` (Default true), `enable_foot_contact` (Default true).

### Terminal 2 — Aufstehen (gait_node starten → Auto-Standup)

```bash
ros2 launch hexapod_gait gait.launch.py
```
⏳ Der Roboter steht über den Auto-Standup (cartesian) auf und ist danach lauffähig.

Mit Optionen (Beispiele):
```bash
# Leveling im Lauf an (Rampe/unebener Boden); Gangart wählen
ros2 launch hexapod_gait gait.launch.py leveling_enable:=true gait_pattern:=tripod

# andere Pose/Timing direkt beim Start (standing_only-Params)
ros2 launch hexapod_gait gait.launch.py body_height:=-0.090 radial_distance:=0.160 cycle_time:=2.0
```
Nützliche `gait.launch.py`-Args: `gait_pattern` (tripod|wave|tetrapod|ripple), `leveling_enable`
(Default false), `body_height`, `radial_distance`, `cycle_time`, `tick_rate`, `step_height`,
`step_length_max`, `cmd_vel_timeout`, `params_file` (YAML-Preset), `use_sim_time` (Default false —
in Sim ok, der Tick läuft wall-clock).

### Terminal 3 — Loslaufen
Siehe [Bereich D](#4-bereich-d--loslaufen-in-gazebo-cmd_vel). Kurz:
```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```

---

## 2. Bereich B — IMU-Balance-Features ein/aus

> Alle Schalter sind **live** per `ros2 param set` (vorher einmal `ros2 daemon stop`). `true`/`false`.
> Viele lassen sich auch beim `gait.launch.py`-Start als Arg setzen.

```bash
ros2 daemon stop   # einmalig vor dem ersten set

# --- Stufe 1: Kipp-/Sturz-Erkennung → Safe-State ---
ros2 param set /gait_node tip_detection_enable true        # Kipp-CRIT → Freeze, WARN → cmd_vel=0

# --- Stufe 2/3a/TF-2: Körper-Leveling / Stabilisierung ---
ros2 param set /gait_node leveling_enable true              # Body-Leveling an
ros2 param set /gait_node leveling_mode terrain             # terrain = Hang folgen (pitch) + roll→0
ros2 param set /gait_node leveling_mode horizontal          # horizontal = voll waagerecht (beide →0)

# --- TF-1: slope-bewusster Tip (Hang-Schätzung) ---
ros2 param set /gait_node slope_aware_tip_enable true       # Tip nutzt Residual (IMU − Hangschätzung)

# --- S4-1: Fußkontakt-Diagnose-Log ---
ros2 param set /gait_node foot_contact_debug_enable true    # throttled Diagnose-Log + /foot_contacts

# --- S4-2: adaptiver Touchdown ---
ros2 param set /gait_node adaptive_touchdown_enable true    # Fuß reicht über Kante/Loch nach (Open-Loop-Fallback)

# --- S4-4: Slip / Kontaktverlust → Freeze ---
ros2 param set /gait_node slip_detection_enable true        # Stütz-Fuß ohne Halt → Safety-Freeze

# --- S4-5: Sensor-Plausibilität / Fault-Fail-Safe ---
ros2 param set /gait_node sensor_plausibility_enable true   # defekter Taster → flaggen + maskieren + WARN (kein Freeze)
```

**Fault injizieren (S4-5 Sim-Test-Hook, Debug):** zwingt EINEN Fußkontakt auf einen Klemm-Wert.
```bash
ros2 param set /gait_node sensor_fault_inject "1:stuck_on"    # Bein 1 klemmt auf "Kontakt"
ros2 param set /gait_node sensor_fault_inject "2:stuck_off"   # Bein 2 klemmt auf "kein Kontakt" (tot)
ros2 param set /gait_node sensor_fault_inject "none"          # aus (Default '')
```

**Alles auf einmal (Stage-4-Voll-Demo aufgebaut):**
```bash
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 param set /gait_node slip_detection_enable true
ros2 param set /gait_node sensor_plausibility_enable true
```

---

## 3. Bereich C — Parameter-Gruppen (Tuning)

> Pro Gruppe gehört zusammen, was dasselbe Verhalten steuert. Defaults in Klammern. Live per
> `ros2 param set /gait_node <name> <wert>` (außer die als *standing_only* markierte Gruppe G1).

### G1 — Grund-Pose & Timing  *(standing_only — nur im STANDING ändern, am besten als Launch-Arg)*
```bash
ros2 param set /gait_node gait_pattern tripod        # tripod | wave | tetrapod | ripple
ros2 param set /gait_node body_height -0.080         # Körperhöhe (m, negativ = tiefer)  [min -0.110 / max -0.060]
ros2 param set /gait_node radial_distance 0.160      # Fuß-Radialabstand (m)
ros2 param set /gait_node cycle_time 2.0             # Schrittzyklus-Dauer (s)  → kleiner = schneller
ros2 param set /gait_node tick_rate 50.0             # Loop-Rate (Hz)
ros2 param set /gait_node step_height 0.040          # Schwung-Höhe (m)
ros2 param set /gait_node step_length_max 0.050      # max. Schrittlänge (m)
```
> ⚠️ Mehrere Folge-Params (`slip_grace_stance_phase`, `touchdown_probe_start_stance_phase`,
> `sensor_dead_cycles`) hängen am `cycle_time` — bei schnellerem Zyklus dort nachziehen (s. Gruppen).

### G2 — Kipp-/Sturz-Erkennung (Stufe 1)
```bash
ros2 param set /gait_node tip_detection_enable true
ros2 param set /gait_node tip_angle_warn_deg 15.0    # WARN-Schwelle (→ cmd_vel=0)
ros2 param set /gait_node tip_angle_crit_deg 25.0    # CRIT-Schwelle (→ Safety-Freeze)
ros2 param set /gait_node tip_rate_crit_dps 80.0     # Kipprate-CRIT (°/s)
ros2 param set /gait_node tip_debounce_ticks 5       # Entprellung (Ticks)
```

### G3 — Körper-Leveling / Stabilisierung (Stufe 2 / 3a / TF-2)
```bash
ros2 param set /gait_node leveling_enable true
ros2 param set /gait_node leveling_mode terrain          # terrain | horizontal
ros2 param set /gait_node leveling_kp 0.4                # P-Gain
ros2 param set /gait_node leveling_ki 0.1                # I-Gain
ros2 param set /gait_node leveling_kd 0.03               # D-Gain (Gyro-Dämpfung, TF-2)
ros2 param set /gait_node leveling_deadband_deg 1.5      # Totband (darunter inaktiv)
ros2 param set /gait_node leveling_slew_max_dps 8.0      # max. Stell-Rate (°/s)
ros2 param set /gait_node leveling_max_angle_deg 10.0    # Clamp im STANDING
ros2 param set /gait_node leveling_max_angle_walking_deg 4.0   # Clamp im WALKING
ros2 param set /gait_node leveling_startup_grace true    # Tip beim Konvergieren unterdrücken
```
> Sichtbarere Dämpfung beim Nicht-Tripod-Wackeln: `leveling_deadband_deg` ↓ (z.B. 0.3) + `kp`/`kd` ↑.
> **Vorsicht auf HW** (Rauschen) — in Sim gratis.

### G4 — Terrain-Following / Hang-Schätzung (TF-1)
```bash
ros2 param set /gait_node slope_aware_tip_enable true
ros2 param set /gait_node slope_estimate_tau_s 0.5      # Tiefpass-Zeitkonstante (s)
ros2 param set /gait_node slope_clamp_deg 40.0          # Clamp der Hang-Schätzung (°)
```

### G5 — Adaptiver Touchdown (S4-2)
```bash
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 param set /gait_node touchdown_probe_start_stance_phase 0.35   # Stance-Gate, ab dem nach unten gesucht wird (∈[0,1))
ros2 param set /gait_node touchdown_search_end_stance_phase 0.6     # Such-Ende, dann Floor halten (> probe_start)
ros2 param set /gait_node touchdown_max_extra_depth 0.02            # max. Tiefe unter body_height (m)
```
> ⚠️ `touchdown_probe_start_stance_phase` muss **> Kontakt-Lag in Stance-Phasen** (~0.27 bei cycle_time 2.0)
> bleiben, sonst Drift auf flachem Boden. Bei schnellerem Zyklus hochsetzen.

### G6 — Slip / Kante → Freeze (S4-4)
```bash
ros2 param set /gait_node slip_detection_enable true
ros2 param set /gait_node cliff_depth 0.03              # Grenze folgbar↔Abgrund (m unter body_height; > = Freeze)
ros2 param set /gait_node slip_debounce_ticks 8         # Ticks ohne Halt bis Freeze (muss > contact_timeout ≈5)
ros2 param set /gait_node slip_min_lost_legs 1          # gleichzeitig haltlose Stütz-Beine bis Freeze (∈[1,6])
ros2 param set /gait_node slip_grace_stance_phase 0.6   # Stance-Phase-Grace (darunter no-contact nicht gewertet; cycle_time-abh.)
```

### G7 — Sensor-Plausibilität / Fault-Fail-Safe (S4-5)
```bash
ros2 param set /gait_node sensor_plausibility_enable true
ros2 param set /gait_node sensor_apex_band_low 0.3      # Apex-Band unten (>contact_timeout-Nachhall; low<high)
ros2 param set /gait_node sensor_apex_band_high 0.7     # Apex-Band oben
ros2 param set /gait_node sensor_apex_fault_cycles 3    # lückenlose Apex-Pässe in Folge bis stuck-on (2=schneller/4=robuster)
ros2 param set /gait_node sensor_dead_cycles 2          # Cycles ohne Kontakt bis dead (cycle_time-unabhängig)
ros2 param set /gait_node sensor_fault_inject "none"    # Sim-Test-Hook (s. Bereich B)
```

**Aktuelle Werte ansehen / alle dumpen:**
```bash
ros2 param get /gait_node leveling_enable
ros2 param list /gait_node
ros2 param dump /gait_node                              # ganzes YAML (als Preset wiederverwendbar via params_file:=)
```

---

## 4. Bereich D — Loslaufen in Gazebo (cmd_vel)

> Omnidirektional: `linear.x` vor/zurück, `linear.y` seitlich, `angular.z` drehen. `-r 10` = 10 Hz
> dauerhaft publizieren (Dead-Man — hört das Publizieren auf, bremst der Roboter über `cmd_vel_timeout`).

```bash
# Geradeaus vorwärts (langsam)
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'

# Rückwärts
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: -0.04}}'

# Seitlich (strafe)
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {y: 0.03}}'

# Auf der Stelle drehen
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{angular: {z: 0.3}}'

# Kombiniert (vorwärts + Kurve)
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}, angular: {z: 0.2}}'

# Anhalten: Publisher mit Ctrl-C beenden, ODER explizit 0 senden
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
```

**Recovery nach einem Safety-Freeze** (Tip-CRIT oder Slip): `cmd_vel=0` (Publisher Ctrl-C) → der Node
geht STOPPING → STANDING → Latch wird zurückgesetzt; danach läuft er wieder normal.

---

## 5. Bereich E — RViz parallel zu Gazebo

> `sim.launch.py` veröffentlicht schon `robot_state_publisher` (TF aus `/joint_states`) und den
> `imu_monitor` (`world→base_link`-TF aus IMU-roll/pitch). RViz muss daher **nur** mit der passenden
> Config geöffnet werden — **kein** `display.launch.py` (das startet einen 2. robot_state_publisher
> + joint_state_publisher_gui, der mit den echten Gelenkwerten kollidiert).

```bash
# In einem ZUSÄTZLICHEN Terminal (Sim läuft schon):
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"
```
- **Fixed Frame = `world`** → das Modell **neigt sich mit** Gazebo (über die IMU-TF).
- Das Bein `leg_1` ist als **grüner Femur** markiert (Front/Bein-Zuordnung beim Kipp-Test).

Alternative Configs: `view_reach.rviz` (Reachability), `view_torque.rviz` (Torque-Heatmap).

---

## 6. Bereich F — Beobachten (Topics & Diagnose)

```bash
# IMU roll/pitch/yaw (vom imu_monitor, 1 Hz Log)  +  rohe IMU
ros2 topic echo /imu/monitor
ros2 topic echo /imu/data --once

# Hang-Schätzung (TF-1):  [roll_deg, pitch_deg]
ros2 topic echo /imu/slope

# Fußkontakte (6× 0/1) + einzelne Bein-Topics (Bool)
ros2 topic echo /foot_contacts
ros2 topic echo /leg_1/foot_contact

# Node-Status / Topics / Frequenzen
ros2 node info /gait_node
ros2 topic hz /imu/data
```
> Latched/transient_local-Topics (z.B. `/hexapod/shutdown_request`) brauchen
> `--qos-reliability reliable --qos-durability transient_local`, sonst kommt der gelatchte Wert nicht an.

---

## Z. Ein-Befehl-Abkürzungen (Referenz)

> Macht T1+T2 (Welt + Spawn + Aufstehen) in **einem** Launch; danach nur noch `cmd_vel`. Praktisch für
> schnelle Demos; für die granulare Kontrolle nimm Bereich A.

```bash
# Rampe laufen (Leveling Default an)
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=8.0 gait_pattern:=tripod
ros2 launch hexapod_bringup ramp_walk.launch.py leveling_enable:=false        # passiv (TF-1)

# Graben (Stage 4 isoliert: leveling Default aus)
ros2 launch hexapod_bringup trench_walk.launch.py trench_depth:=0.02

# Stufe ab/auf
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=0.04
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=-0.02              # Stufe auf (Gegenprobe)
```
Danach in einem 2. Terminal: `ros2 daemon stop` → Feature-Schalter (Bereich B) → `cmd_vel` (Bereich D).

Gemeinsame Args: `gait_pattern`, `leveling_enable`, `spawn_x`, `gait_delay` (Default 12 s, Controller
erst hoch). Welt-spezifisch: `slope_deg` / `trench_depth`+`trench_width`+`trench_x` / `step_drop`.

---

## Typischer Demo-Ablauf (Beispiel: adaptiver Touchdown über dem Graben)

```bash
# T1: Graben-Welt + Spawn
ros2 launch hexapod_bringup trench.launch.py trench_depth:=0.02 trench_width:=0.10
# T2: Aufstehen
ros2 launch hexapod_gait gait.launch.py
# T3 (RViz, optional): rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"
# T4: Features scharf
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true
# T5: loslaufen
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
# Beobachten: ros2 topic echo /foot_contacts   |   imu_monitor-Log
```
