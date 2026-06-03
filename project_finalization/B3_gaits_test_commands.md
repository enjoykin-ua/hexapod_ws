# B3 — Gangarten (Wave / Tetrapod / Ripple) — Test-Anleitung

> Pro Gangart: Offline (Unit/Lint) → SIM → HW (aufgebockt → Boden). Plan: [`B3_gaits_plan.md`](B3_gaits_plan.md).
> Umschalten geht nur im **STANDING** (`gait_pattern` ist `standing_only`). Default = `tripod`.

---

## 0. Offline (je Gangart, bereits grün für Wave)

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
colcon test --packages-select hexapod_gait
colcon test-result --test-result-base build/hexapod_gait --verbose
# Wave: 123 tests, 0 failures, 1 skipped. flake8/pep257 grün.
```

---

## 1. SIM — gemeinsamer Aufbau (für alle Gangarten gleich)

**Terminal A — Sim:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
**Terminal B — Gait (Default tripod, feet-closer-Pose), warten bis `STATE_STANDING`:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
```

---

## 1.1 Wave testen (B3.1)

```bash
# Terminal C — im STANDING auf Wave umschalten:
ros2 param set /gait_node gait_pattern wave
#   → erwartet: param updated: gait_pattern=wave (im STANDING akzeptiert).

# vorwärts laufen (Wave-linear_max ~0.053 m/s; 0.04 bleibt drunter):
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**Erwartet in RViz/Gazebo:**
- Es ist immer **nur 1 Bein gleichzeitig in der Luft**, die anderen 5 tragen.
- Hebe-Reihenfolge **3→2→1→4→5→6** (rechts hinten→vorne, dann links hinten→vorne).
- Deutlich **langsamerer** Vortrieb als Tripod, dafür sehr ruhig/stabil.

```bash
# Anhalten + zurück auf Tripod:
#   Terminal C: Strg+C
ros2 param set /gait_node gait_pattern tripod   # nur im STANDING
```
> **Gegencheck Guard:** Umschalten WÄHREND des Laufens (WALKING) ablehnen lassen:
> `ros2 param set /gait_node gait_pattern wave` während cmd_vel läuft → erwartet
> `success=False ... requires STATE_STANDING`.

---

## 2. HW aufgebockt → Boden (je Gangart)

> ⚠️ CLAUDE.md §9: aufgebockt, Kill-Switch griffbereit, kurz/langsam.

**Terminal 1 — Hardware:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Terminal 2 — Gait (use_sim_time:=false!) + Preset, warten bis STANDING:**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  robot_description_file:="$HEX_URDF" \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml
```
**Terminal 3 — Gangart wählen + laufen (aufgebockt):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 param set /gait_node gait_pattern wave          # im STANDING
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**Optional — Last/Hitze beobachten (B3.6), separates Terminal:**
```bash
# torque_viz / torque-Beobachtung (tools/) — Wave sollte die per-Bein-Last
# senken (5 statt 3 tragende Beine).
```
Aufgebockt sauber → **dann Boden**: kurz vorwärts, Stabilität/kein Kippen prüfen.

---

## 3. Tetrapod (B3.2) / Ripple (B3.3) — folgen nach Wave

Gleicher Ablauf, nur `gait_pattern tetrapod` bzw. `ripple` (werden nach Wave-Freigabe
implementiert + hier ergänzt). Erwartung: 2 Beine in der Luft (Tetrapod = Diagonal-Paar,
Ripple = kontralateral), Tempo zwischen Tripod und Wave.
