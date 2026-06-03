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

## 1.2 Tetrapod testen (B3.2) — SIM

Aufbau wie Abschnitt 1 (Sim + Gait, STANDING). Dann Terminal C:
```bash
ros2 param set /gait_node gait_pattern tetrapod
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Erwartet:** immer **2 Beine gleichzeitig** in der Luft, und zwar ein **Diagonal-Paar**
({1,4} = vorne-R+hinten-L, dann {2,5} = mitte-R+mitte-L, dann {3,6} = hinten-R+vorne-L),
die anderen 4 tragen. Tempo **zwischen** Tripod und Wave (linear_max ~0.067 m/s).
> ⚠️ **Bekannt (Sim 2026-06-03):** Tetrapod (und Ripple) bringen den Körper im Open-Loop zum
> **periodischen Neigen/Rollen** — statisch stabil (kippt nicht um, Marge 114/120 mm), aber ohne
> Körper-Lage-Regelung wackelt es. Echter Fix = **A5 IMU-Balance** (zurückgestellt). Dämpfen geht
> per Live-Tuning: `cycle_time` hoch (z.B. 3.0) + `step_height` runter (z.B. 0.05). Auf HW evtl.
> anders (Servo-Nachgiebigkeit). Tripod bleibt die ruhige Alltags-Gangart.
Zurück: `Strg+C`, dann `ros2 param set /gait_node gait_pattern tripod` (im STANDING).

## 1.3 Ripple testen (B3.3) — SIM

Aufbau wie Abschnitt 1. Dann Terminal C:
```bash
ros2 param set /gait_node gait_pattern ripple
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Erwartet:** **2 Beine** in der Luft, immer **echt diagonal** (verschiedene Seite UND Reihe),
als Welle rundherum (Reihenfolge **1,5,3,6,2,4**). Stütz-Marge ~120 mm (≈ Tripod/Tetrapod) →
stabil. Gleiches Tempo wie Tetrapod (~0.067 m/s). Zurück: `Strg+C`, dann `gait_pattern tripod`.
> Hinweis: die frühere Reihenfolge 3,4,2,5,1,6 hatte beide Hinterbeine kurz gleichzeitig in der
> Luft → Marge nur ~7 mm → kippelte; mit 1,5,3,6,2,4 behoben (B3.3-Stabilitätsanalyse).

---

## 4. HW — alle drei Gangarten (nacheinander)

HW-Aufbau wie Abschnitt 2 (real.launch.py + Gait mit Preset, `use_sim_time:=false`,
warten bis STANDING). Dann je Gangart im STANDING umschalten + aufgebockt laufen, dann Boden:
```bash
# im STANDING umschalten (eine der drei), dann laufen:
ros2 param set /gait_node gait_pattern wave        # bzw. tetrapod / ripple
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'   # wave
#   tetrapod/ripple: x bis ~0.05 möglich (höheres linear_max)
```
Zwischen den Gangarten: `Strg+C`, `gait_pattern tripod` (STANDING), dann nächste Gangart.
Optional Last/Hitze je Gangart mit `torque_viz` beobachten (B3.6): Wave/Ripple sollten die
per-Bein-Last senken (mehr tragende Beine als Tripod).
