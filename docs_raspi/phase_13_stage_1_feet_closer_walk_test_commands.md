# Phase 13 Stage 1 / Teil 2.2 — Test-Commands: Feet-closer Walk (Sim → HW)

> **Plan:** [`phase_13_stage_1_tibia_unlock_plan.md`](phase_13_stage_1_tibia_unlock_plan.md) §2 Sub-Stage 2.2.
> **Preset:** `src/hexapod_gait/config/presets/feet_closer_walk.yaml`
> (radial 0.220 / step_length 0.089 / step_height 0.040 / bh −0.080 / cycle 2.0).
> **Form:** Du führst aus, knappe Status zurück. **REIHENFOLGE: erst §S (Sim RViz+Gazebo),
> dann — wenn grün + committet — §T (HW aufgebockt).** (User-Wunsch: Sim vor HW.)
>
> **Was wir sehen wollen:** sichtbar **größere Schritte** (Schrittweite ~2× = 0.089 statt
> 0.05) und **mehr Coxa-Schwenk/Hub** als bisher, **ohne** `IKError`/Freeze, in **alle**
> Richtungen (vorwärts / seitwärts / drehen). Die Füße stehen näher am Körper.

---

# §S — SIM-Gate (RViz + Gazebo)  [Checkliste 2.2.3]

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

## S1 — Gait mit Feet-closer-Preset (Aufstehen → STANDING)

**Terminal 2:**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
PRESET="$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml"
ros2 launch hexapod_gait gait.launch.py \
    robot_description_file:="$HEX_URDF" \
    params_file:="$PRESET" \
    standup_mode:=cartesian auto_standup_duration:=8
```
warten bis `STATE_STANDING`.
**Erwartung:** Roboter steht mit **Füßen näher am Körper** (radial 0.220) — die Beine
sehen weniger gestreckt aus als bisher (sichtbar gebeugteres Knie).

## S2 — Vorwärts laufen (sichtbar größere Schritte)

**Terminal 3:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.08}}'
```
~10–15 s beobachten (Gazebo + RViz), dann `Strg+C`.
**Erwartung:** deutlich **größere Schritte + mehr Hub** als vorher, sauberer Tripod,
**kein** `IKError`/Freeze (Terminal 2), kein Umkippen. (0.08 m/s nutzt fast den vollen
neuen linear_max 0.089.)

## S3 — Omnidirektional gegenprüfen (das war RED-kritisch)

```bash
# Seitwärts
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {y: 0.06}}'
# (Strg+C, dann) Drehen
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'
# (Strg+C, dann) Diagonal
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05, y: 0.04}}'
```
Jeweils ~8 s, dann `Strg+C`.
**Erwartung:** alle Richtungen sauber, **kein** `IKError`/Freeze (im Envelope offline
alle ✓ grün — hier die Sim-Bestätigung).

### Findings §S (User)
| Test | Status | Notiz |
|---|---|---|
| S1 Stand-Pose Füße näher (radial 0.220), kein Freeze | | |
| S2 Vorwärts: sichtbar größere Schritte/Hub, kein IKError | | |
| S3 Seitwärts / Drehen / Diagonal sauber | | |

> **→ Wenn §S grün: committen, dann §T (Hardware).**

---

# §T — HARDWARE (aufgebockt) — erst NACH §S + Commit  [Checkliste 2.2.4]

⚠️ **Sicherheit (CLAUDE.md §9):** aufgebockt, PSU-Kill-Switch griffbereit. Erst
langsam/kurz, bei Brummen/Stall/Body-Kontakt sofort `Strg+C`.

## T0 — Hardware + Gait mit Preset

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
**Terminal 3 — Gait mit Preset (use_sim_time:=false!):**
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
warten bis `STATE_STANDING`.

## T1 — Vorwärts aufgebockt
**Terminal 4:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.06}}'
```
~10 s, dann `Strg+C`. Optional 0.08.
**Erwartung:** größere Schritte/Hub als bisher, HW=RViz, kein `OVERCURRENT`/`WATCHDOG`/
`SAFETY FREEZE` (T1) / `IKError` (T3), keine Body-Berührung.

## T2 — (überlappt 2.2.5) griffiger Boden: echter Vortrieb
Roboter auf griffigen Boden, T0+T1 wiederholen.
**Erwartung:** echter Vortrieb (nicht „auf der Stelle"), Strom im Rahmen.

### Findings §T (User)
| Test | Status | Notiz |
|---|---|---|
| T1 Vorwärts aufgebockt, kein Freeze/Overcurrent | | |
| T2 griffiger Boden: echter Vortrieb | | |
