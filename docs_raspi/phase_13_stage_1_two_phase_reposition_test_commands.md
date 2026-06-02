# Phase 13 Stage 1 / Sub-Stage 2.3 — Test-Commands: Zwei-Phasen Standup→Reposition→Walk

> **Plan:** [`phase_13_stage_1_two_phase_reposition_plan.md`](phase_13_stage_1_two_phase_reposition_plan.md).
> **Engine-Lösung** (ersetzt den Live-Param-Quicktest aus 2.2.3): die Engine steht mit
> `standup_radial_distance` (0.295) auf und repositioniert danach **automatisch + smooth
> per Tripod** auf `radial_distance` (0.220). Kein manuelles `param set`, kein Fuß-Sprung.
> **Form:** Du führst aus, knappe Status zurück. **REIHENFOLGE: erst §S (Sim), dann —
> wenn grün + committet — §T (HW).**
>
> **Self-contained Preset** `feet_closer_walk.yaml` trägt beide radii → einfach laden.

---

# §S — SIM-Gate (RViz + Gazebo)  [Checkliste 2.3.8]

## S0 — Build + Sim starten
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_description hexapod_bringup
source install/setup.bash
```
**Terminal 1 — Gazebo:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
Warten bis Gazebo offen + 7 Spawner aktiv.

## S1 — Gait mit Preset: Aufstehen → AUTO-Reposition → STANDING
**Terminal 2** (Preset laden — die Engine macht die Zwei-Phasen selbst):
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
PRESET="$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml"
ros2 launch hexapod_gait gait.launch.py \
    robot_description_file:="$HEX_URDF" \
    params_file:="$PRESET" \
    standup_mode:=cartesian auto_standup_duration:=8
```
**Erwartung (visuell in Gazebo/RViz):**
1. **Aufstehen** mit Füßen *weit draußen* (radial 0.295) — kein IK-Fail (das war der
   Femur->90°-Punkt, jetzt umgangen).
2. **Danach automatisch:** zuerst Beine **{1,3,5}** heben & wandern nach innen, dann
   **{2,4,6}** — eine **smoothe Tripod-Bewegung** (kein Sprung), bis alle Füße näher
   stehen (radial 0.220).
3. Stabiler Stand, **kein** `IKError`/Freeze im Terminal-2-Log.

## S2 — Vorwärts laufen
**Terminal 3:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.08}}'
```
~10–15 s, dann `Strg+C`.
**Erwartung:** deutlich größere Schritte/Hub als die alte Pose, sauberer Tripod, kein
Freeze. (cmd_vel *während* der Reposition wird ignoriert — erst STANDING nimmt an.)

## S3 — Omnidirektional gegenprüfen
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {y: 0.06}}'      # seitwärts
# Strg+C, dann:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'      # drehen
# Strg+C, dann:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05, y: 0.04}}'  # diagonal
```
Jeweils ~8 s, `Strg+C`. **Erwartung:** alle Richtungen sauber, kein IKError/Freeze.

### Findings §S (User)
| Test | Status | Notiz |
|---|---|---|
| S1 Aufstehen @0.295 → smoothe Auto-Tripod-Reposition → 0.220, kein Jump/IK-Fail | | Reposition sichtbar in 2 Gruppen? |
| S2 Vorwärts: größere Schritte/Hub | | |
| S3 Seitwärts/Drehen/Diagonal sauber | | |

> **→ Wenn §S grün: committen, dann §T (HW).**

---

# §T — HARDWARE (aufgebockt → Boden) — erst NACH §S + Commit  [Checkliste 2.3.9]

⚠️ **Sicherheit (CLAUDE.md §9):** **aufgebockt** zuerst, PSU-Kill-Switch griffbereit.
Erst aufgebockt die Reposition + das Laufen ansehen; **dann** Boden.

## T0 — Hardware + Gait mit Preset (use_sim_time:=false!)
**Terminal 1 — Hardware:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Terminal 2 — RViz (HW-Spiegel):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
**Terminal 3 — Gait mit Preset:**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
PRESET="$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    params_file:="$PRESET" \
    standup_mode:=cartesian auto_standup_duration:=8
```
**Erwartung (aufgebockt):** Aufstehen @0.295 → smoothe Tripod-Reposition → 0.220,
HW=RViz, kein `OVERCURRENT`/`WATCHDOG`/`SAFETY FREEZE` (T1)/`IKError` (T3), keine
Body-Berührung.

## T1 — Vorwärts aufgebockt
**Terminal 4:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.06}}'
```
~10 s, `Strg+C`. Optional 0.08.

## T2 — Boden: echter Vortrieb (jetzt mit smoother Reposition möglich)
Roboter auf griffigen Boden, T0+T1 wiederholen.
**Erwartung:** Reposition **stabil am Boden** (kein Kippen — der Sprung-Reset, der das
verhindert hätte, ist jetzt eine smoothe Tripod-Bewegung), dann echter Vortrieb mit
größeren Schritten.

### Findings §T (User)
| Test | Status | Notiz |
|---|---|---|
| T0 aufgebockt: Aufstehen + smoothe Reposition, kein Freeze | | |
| T1 Vorwärts aufgebockt, größere Schritte | | |
| T2 Boden: Reposition stabil + echter Vortrieb | | |
