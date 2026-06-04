# B4 — Show-Pose (Free-Leg) — Test-Anleitung (SIM + HW)

> **Zweck:** ausführbare Test-Befehle für B4.8 (SIM) und B4.9 (HW aufgebockt → Boden).
> Offline-Tests (Unit/Lint/Envelope/CoG) sind bereits grün — Abschnitt 0.
> Plan: [`B4_show_pose_plan.md`](B4_show_pose_plan.md) · Status: [`B4_show_pose_progress.md`](B4_show_pose_progress.md).
> **Du führst aus, ich werte knappe Status-Meldungen aus.** Reihenfolge: erst SIM komplett sauber, dann HW.

---

## 0. Offline (bereits grün, zur Reproduktion)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_teleop
colcon test-result --test-result-base build/hexapod_gait --verbose
colcon test-result --test-result-base build/hexapod_teleop --verbose
# Erwartet: gait 181 tests / 0 failures / 1 skipped; teleop 28 / 0 / 1. flake8/pep257 grün.

# B4.0 CoG-/Reachability-Nachweis (sichere Show-Stütz-Pose existiert):
python3 tools/show_pose_cog_check.py --show-radial 0.24 --show-z 0.00
# Erwartet: "B4.0 BESTANDEN", Ziel-Marge ≥40 mm für shift in [0.050, 0.090] m.

# Lauf-Envelope unberührt (Bestand):
python3 tools/walking_envelope_check.py check --radial 0.215 --body-height -0.120 \
  --step-length 0.089 --step-height 0.080 --scenario all          # → GREEN (4/4)
```

---

## 1. SIM (B4.8) — RViz + Gazebo, `use_sim_time:=true`

### 1.1 Sim starten (Terminal A)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

### 1.2 Gait starten (Terminal B) — feet-closer-Preset

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
# Erwartet: Auto-Standup → Reposition → STANDING (wie bisher).
```

### 1.3 Show-Service + Topic prüfen (Terminal C)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 service list | grep hexapod_show          # Erwartet: /hexapod_show_toggle
ros2 topic info /cmd_show                       # Erwartet: Type std_msgs/msg/Float64MultiArray
```

### 1.4 In die Show-Pose (STANDING → SHOW_ENTER → SHOW_ACTIVE)

```bash
ros2 service call /hexapod_show_toggle std_srvs/srv/Trigger {}
# Erwartet RViz/Gazebo (~4 s): Körper verschiebt sich ZURÜCK (alle 6 Füße bleiben
#   am Boden), DANN heben die 2 VORDERBEINE (leg_1 vorne-R, leg_6 vorne-L) in die
#   Luft. Roboter steht stabil auf den 4 hinteren Beinen (leg_2,3,4,5), kippt NICHT.
# success=True, message "entering show pose". State-Log: SHOW_ENTER → SHOW_ACTIVE.
# 🟡 BEOBACHTEN: kein Kippen nach vorne; Vorderbeine ~6–8 cm über Boden; kein Freeze.
```

### 1.5 Vorderbeine per /cmd_show bewegen (ohne Controller)

```bash
# B4.11: 6 Werte [l6_lat, l6_vert, l6_radial, l1_lat, l1_vert, l1_radial] in [-1,1].
#   lat = seitwärts, vert = hoch/runter, radial = reach/Tibia-Curl (raus = +).
# WICHTIG: /cmd_show muss FORTLAUFEND kommen (sonst greift der Staleness-Schutz
# nach cmd_vel_timeout=0.5 s → Beine zurück in Neutral). Daher -r 10 (10 Hz).

# Beide Vorderbeine HOCH:
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray "{data: [0.0, 1.0, 0.0, 0.0, 1.0, 0.0]}"
# Erwartet: beide Vorderbeine heben weiter (vertikal +). Ctrl-C → zurück Neutral.

# Linkes Vorderbein (leg_6) SEITWÄRTS, rechtes (leg_1) RUNTER:
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray "{data: [1.0, 0.0, 0.0, 0.0, -1.0, 0.0]}"
# Erwartet: leg_6 schwenkt seitlich, leg_1 senkt sich. Unabhängige Bewegung.

# B4.11 — TIBIA/REACH: beide Vorderbeine voll RAUSstrecken (radial = 1.0):
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray "{data: [0.0, 0.0, 1.0, 0.0, 0.0, 1.0]}"
# Erwartet: die Vorderbeine STRECKEN sich nach außen, die Tibia fährt sichtbar auf
#   (Femur+Tibia ~0.65 rad). Ctrl-C → zurück in die gebeugte Neutral-Hoch-Pose.
#   (Reinrollen ist von der Neutral-Pose femur-limit-blockiert → nur raus.)

# 🟡 BEOBACHTEN: weiche (rate-limitierte) Bewegung, kein Servo-Sprung; in-limit
#   (kein Freeze/IKError im gait_node-Log); Roboter bleibt stabil.
# 🟡 SELBST-KOLLISION (A4 nicht geprüft): visuell prüfen, ob die Vorderbeine sich
#   oder den Körper berühren — falls ja, show_lat_scale/vert_scale/radial_scale senken.

# Staleness-Test: Pub stoppen (Ctrl-C) → Vorderbeine fahren weich in die Neutral-
# Hoch-Pose zurück (Disconnect-Schutz).
```

### 1.6 Raus aus der Show-Pose (SHOW_ACTIVE → SHOW_EXIT → STANDING)

```bash
ros2 service call /hexapod_show_toggle std_srvs/srv/Trigger {}
# Erwartet (~3 s): ZUERST gehen die Vorderbeine RUNTER auf den Boden (wieder
#   6-Bein-Stütze), DANN schiebt sich der Körper wieder nach VORNE → STANDING.
# success=True, message "leaving show pose". State-Log: SHOW_EXIT → STANDING.
# 🟡 BEOBACHTEN: kein Ruck beim Aufsetzen der Vorderbeine; Endpose = normale Walk-Pose.
```

### 1.7 Laufen nach dem Round-Trip (Regression: Show blockiert Laufen nicht)

```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}"
# Erwartet: Roboter läuft normal vorwärts (Tripod). Beweist: nach Show → STANDING
#   ist Fahren wieder möglich.
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}"   # stoppen
```

### 1.8 Guard-Checks (negativ)

```bash
# Show-Toggle während des Laufens → abgelehnt (nur aus STANDING rein):
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}" &
sleep 1; ros2 service call /hexapod_show_toggle std_srvs/srv/Trigger {}
# Erwartet: success=False, "braucht STANDING oder einen SHOW-State". Kein State-Wechsel.
kill %1; ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}"

# cmd_vel während SHOW_ACTIVE wird ignoriert (kein Losfahren):
#   (in Show-Pose gehen, dann cmd_vel publishen → Roboter bleibt in Show, fährt nicht)
```

---

## 2. SIM mit PS4-Controller (optional, B4.8) — End-to-End-UI

```bash
# Terminal D — Teleop (USB; BT: controller:=ps4_bt):
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```

Bedienung:
- **Cross (✕) LANG halten** (~0.8 s) → in die Show-Pose / wieder heraus (Toggle).
- In der Show: **R1 (Dead-Man) HALTEN** + **linker Stick → linkes Vorderbein (leg_6)**,
  **rechter Stick → rechtes Vorderbein (leg_1)**. **Stick X = seitwärts, Stick Y = hoch/runter.**
- **B4.11 Tibia/Reach:** **L2 → leg_6, R2 → leg_1** (analog, R1 gehalten) — Trigger drücken =
  Bein streckt sich raus, Tibia fährt auf; loslassen = zurück in die gebeugte Neutral-Pose.
- **R1 loslassen / Achsen zentrieren** → Vorderbeine fahren in die Neutral-Hoch-Pose zurück.
- Hinweis: Body-Höhe (L2/R2) gibt's nur OHNE R1 — im Show sind die Trigger der Tibia-Curl.

🟡 **Signs verifizieren:** Stick HOCH muss das Bein HEBEN. Falls invertiert →
`sign_show_vert` (bzw. `sign_show_lat`/`sign_show_radial`) in `ps4_usb.yaml`/`ps4_bt.yaml` auf `-1.0`.
🟡 **Trigger-Ruhewert (B4.11):** stehen die Vorderbeine direkt nach dem Eintreten schon teil-
gestreckt, OHNE dass du L2/R2 berührst, melden deine Trigger im Ruhezustand 0 statt +1.0
(`ros2 topic echo /joy` → axes[2]/axes[5] prüfen). Dann muss die Trigger→Curl-Normierung angepasst
werden (kurz Bescheid geben) — Standard-PS4-USB ruht bei +1.0, dann passt es.
🟡 **Tuning:** zu große Auslenkung / Kollision → Skalen am gait_node konservativer:
```bash
ros2 param set /gait_node show_lat_scale 0.04
ros2 param set /gait_node show_vert_scale 0.04
ros2 param set /gait_node show_radial_scale 0.04
```

---

## 3. HW aufgebockt → Boden (B4.9) — ⚠️ CoG-kritisch (nur 4 Stützbeine!)

> **CLAUDE.md §9:** Roboter zuerst **aufgebockt** (Beine in der Luft), Kill-Switch griffbereit.
> Erst nach sauberem Aufgebockt-Lauf auf den Boden. `use_sim_time:=false`.

### 3.1 Aufgebockt (Beine frei in der Luft)

```bash
# Gait auf HW (use_sim_time:=false; sonst blockiert der rclpy-Timer ohne /clock):
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=false
```
- Aufstehen abwarten → STANDING.
- `/hexapod_show_toggle` → Show einnehmen; `/cmd_show` (s. 1.5) → Vorderbeine bewegen.
- 🟡 **BEOBACHTEN:** kein Servo-Stall/Brummen am Extrem; weiche Bewegung; kein Freeze.

### 3.2 Auf dem Boden (vorsichtig, CoG!)

- Roboter auf festen, griffigen Boden (Füße dürfen beim Körper-Rückversatz NICHT rutschen).
- `/hexapod_show_toggle` → **langsam beobachten**: Körper zurück, Vorderbeine hoch — **kippt er?**
- Bei Kipp-Tendenz SOFORT `/hexapod_show_toggle` (raus) oder Kill-Switch.
- 🟡 **Bei Bedarf mehr Reserve:** `show_body_shift_back` erhöhen (max 0.09; mehr CoG-Marge),
  oder `show_front_radial`/`show_front_z` konservativer (Vorderbeine weniger weit/hoch):
```bash
ros2 param set /gait_node show_body_shift_back 0.075
```

---

## 4. Abnahme-Kriterien B4.8 / B4.9

| # | Kriterium | Stufe |
|---|---|---|
| 1 | Rein: Körper zurück → Vorderbeine hoch, **kein Kippen/Freeze** | SIM + HW |
| 2 | Vorderbeine per Stick/Topic unabhängig bewegbar (lat + vert), weich, in-limit | SIM + HW |
| 3 | Raus: Vorderbeine runter → Körper vor → STANDING, **kein Ruck** | SIM + HW |
| 4 | Nach Round-Trip wieder **normal laufen** möglich | SIM + HW |
| 5 | Selbst-Kollision visuell ok (A4 ungeprüft) / sonst Skalen senken | SIM |
| 6 | Auf dem Boden **CoG-stabil** (kippt nicht), kein Fuß-Rutschen | HW Boden |
