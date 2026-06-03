# C2 — Gangart-/Schrittweiten-Intents — Test-Anleitung

> SIM (C2.5) + HW (C2.6). Offline (Unit/Lint) grün — Abschnitt 0. Plan: [`C_teleop.md`](C_teleop.md) §C2.
> Intents im `gait_node` (Teleop = UI): `/hexapod_cycle_gait` (SetBool: true=next/false=prev,
> nur STANDING), `/hexapod_adjust_step_length` (SetBool: true=+/false=−, geclampt).

---

## 0. Offline (bereits grün)
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_teleop
colcon test-result --test-result-base build/hexapod_gait --verbose    # 144, 0 fail
colcon test-result --test-result-base build/hexapod_teleop --verbose  # 20, 0 fail
```

---

## 1. SIM (C2.5)

**Terminal A — Sim:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
**Terminal B — Gait (feet-closer-Preset), warten bis `STATE_STANDING`:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
```
**Terminal C — Teleop (für 1.2; für 1.1 nicht nötig):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
```
**Terminal D — Test-Befehle (eigenes Terminal):**
```bash
cd ~/hexapod_ws && source install/setup.bash
```

### 1.1 Direkt per Service (ohne Controller, schnellster Check) — in Terminal D
```bash
# Gangart durchschalten (nur im STANDING):
ros2 service call /hexapod_cycle_gait std_srvs/srv/SetBool '{data: true}'   # next
ros2 service call /hexapod_cycle_gait std_srvs/srv/SetBool '{data: false}'  # prev
#   → Log: gait_pattern -> wave/tetrapod/ripple/tripod (Wrap). Im WALKING → success=False.

# Schrittweite trimmen (jederzeit):
ros2 service call /hexapod_adjust_step_length std_srvs/srv/SetBool '{data: true}'   # +0.005 m
ros2 service call /hexapod_adjust_step_length std_srvs/srv/SetBool '{data: false}'  # -0.005 m
#   → Log: step_length_max -> X.XXX m (clampt auf [0.02, 0.10]).
ros2 param get /gait_node step_length_max    # Wert gegenlesen
```

### 1.2 Per PS4-Controller (D-Pad)
```bash
# im STANDING:
#  D-Pad →  : nächste Gangart   |  D-Pad ←  : vorige Gangart
#  D-Pad ↑  : Schrittweite +    |  D-Pad ↓  : Schrittweite −
# Dann mit R1 + linkem Stick losfahren und den Effekt sehen.
```
**Erwartet:** Gangart wechselt nur im Stand (im Lauf abgelehnt); Schrittweite ändert Stride/Tempo
sichtbar; ein D-Pad-Druck = ein Schritt (Rising-Edge, kein Dauerfeuer beim Halten).
> Richtung verkehrt? `sign_dpad_x`/`sign_dpad_y` in `ps4_usb.yaml` flippen, Teleop neu starten.

---

## 2. HW aufgebockt → Boden (C2.6) — `use_sim_time:=false`

> ⚠️ **CLAUDE.md §9:** Roboter **aufgebockt** (Beine frei), **PSU-Kill-Switch griffbereit**,
> langsam/kurz. Relay schaltet beim Plugin-Activate automatisch ein.

**Terminal 1 — Hardware:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Terminal 2 — RViz HW-Spiegel (optional):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
**Terminal 3 — Gait (`use_sim_time:=false`! + Preset), warten bis `STATE_STANDING`:**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml
```
**Terminal 4 — Teleop (PS4 USB):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
```
**Terminal 5 — Test-Befehle (im STANDING):**
```bash
cd ~/hexapod_ws && source install/setup.bash
# Gangart wechseln (oder D-Pad → am Controller):
ros2 service call /hexapod_cycle_gait std_srvs/srv/SetBool '{data: true}'
# Laufen, Gangart beobachten:
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
# Schrittweite größer (oder D-Pad ↑):
ros2 service call /hexapod_adjust_step_length std_srvs/srv/SetBool '{data: true}'
ros2 param get /gait_node step_length_max
```
Aufgebockt sauber → **dann Boden**: Gangart/Schrittweite live ändern, kein Freeze.

> **Hinweis (Ende-C-Pendenz):** Schrittweite ist auf [0.02, 0.10] geclampt — schützt grob, aber
> ungültige Kombis aus Höhe+Schrittweite+Gangart können noch IK-Freeze geben. Die saubere
> Validierung (nur envelope-grüne Kombinationen) ist die Feinjustage am Ende von Block C
> (s. `C_teleop.md`).

## 3. Fertig-Kriterium
- **C2.5 SIM:** cycle_gait wechselt (Wrap, STANDING-Guard), step_length clampt, D-Pad triggert.
- **C2.6 HW:** dito aufgebockt → Boden, kein Freeze im gültigen Bereich.
