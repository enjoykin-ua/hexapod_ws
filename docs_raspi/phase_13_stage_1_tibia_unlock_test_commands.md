# Phase 13 Stage 1 / Teil 2.1 — Test-Commands: Tibia-Unlock +2.5 Live-Validierung

> **Plan:** [`phase_13_stage_1_tibia_unlock_plan.md`](phase_13_stage_1_tibia_unlock_plan.md) §3.2 / Checkliste 2.1.6.
> **Form:** Du führst aus, knappe Status zurück ([[feedback_interactive_stage_test_doc]]).
> Verifikations-Outputs **nicht** trimmen ([[feedback_no_trim_verification_output]]).
> **Voraussetzung:** Code 2.1 ✅ (Build + Tests + standup_envelope GRÜN am Desktop). **Du hast committet.**

⚠️ **Sicherheit (CLAUDE.md §9):** **aufgebockt** (Beine in der Luft), PSU-Kill-Switch
griffbereit. Der Sweep fährt die Tibia in den **neuen, viel tieferen Beuge-Bereich**
(+2.5 = 143°, vorher +1.30 = 74°) — der Fuß **curlt dabei nahe an den Body**. Deshalb:
**erst leg_1 einzeln + langsam beobachten**, dann alle 6. Bei Brummen / Stall / Body-
Berührung **sofort `Strg+C`** und zurück. Aufgebockt ist der Boden irrelevant; einzige
Kollisionsgefahr = Fuß/Tibia gegen das eigene Chassis.

> **REIHENFOLGE (User-Wunsch 2026-06-02):** zuerst **§S — Sim-Gate (RViz + Gazebo)**,
> erst wenn das sauber ist → committen → dann **§T — Hardware**. Nicht direkt auf HW.

---

# §S — SIM-Gate (RViz + Gazebo) — VOR Hardware  [Checkliste 2.1.7]

> Zweck: beweisen, dass (a) das Modell mit +2.5 lädt, (b) die Tibia in **Gazebo** bis
> +2.5 fährt ohne Controller-Error, (c) der **bestehende Gait weiterläuft** (keine
> Regression durch das geänderte Limit), (d) **RViz** das Modell bis +2.5 zeigt.
> Reine Sim — keine HW, kein Risiko. (URDF-Refactor-Smoke-Regel.)

## S0 — Build + Sim starten

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_description hexapod_bringup hexapod_kinematics hexapod_gait
source install/setup.bash
```
**Terminal 1 — Gazebo:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
Warten bis Gazebo offen + die 7 Spawner (`joint_state_broadcaster` + `leg_1..6_controller`)
„configured and activated" zeigen.

## S1 — Gazebo: Tibia fährt bis +2.5 (Limit greift, kein Controller-Error)

**Terminal 2** (Femur oben −0.4, Tibia an die neue Grenze):
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, -0.4, 2.5], time_from_start: {sec: 3}}]}"
sleep 4
ros2 topic echo /joint_states --once
```
**Erwartung:** leg_1_tibia in `/joint_states` erreicht **~2.5** (±0.05) — vor dem Unlock
hätte der Controller bei +1.30 geklippt. Im Gazebo-Fenster faltet leg_1 sichtbar tief ein.
Kein Spawner-Fehler/Crash in Terminal 1.

## S2 — Gazebo: bestehender Gait läuft weiter (Regressions-Check)

> Der Unlock ändert nur Limits, **nicht** die Gait-Params → das Gangbild soll
> **unverändert** sein (kein Freeze/IKError, kein Wegkippen). Das ist der eigentliche
> URDF-Refactor-Smoke. (Sim hat /clock → `use_sim_time` Default `true` ist ok.)

**Terminal 3 — Gait (Aufstehen → STANDING):**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py robot_description_file:="$HEX_URDF" standup_mode:=cartesian auto_standup_duration:=8
```
warten bis `STATE_STANDING`.
**Terminal 4 — Vorwärts laufen:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```
~10 s beobachten, dann `Strg+C`.
**Erwartung:** Aufstehen + Tripod-Laufen wie gehabt, **kein** `IKError`/Freeze (Terminal 3),
Gazebo zeigt das gewohnte Gangbild. (Größere Schritte kommen erst mit 2.2 — hier nur
„keine Regression".)

## S3 — RViz: Modell erreicht +2.5 (vormals rote Zone fahrbar)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait reachability_viz.launch.py
```
Mit dem `joint_state_publisher_gui`-Slider die **leg_1-Tibia** auf Maximum ziehen.
**Erwartung:** Slider geht jetzt **bis +2.5** (vorher +1.30); der schwarze Tibia-Stab
fährt in die früher nur „rote" Zone. Die **blaue** Wolke reicht bis +2.5, **rot** ist
nur noch der schmale Rest bis 2.6.

### Findings §S (User) — ✅ alle grün 2026-06-02
| Test | Status | Notiz |
|---|---|---|
| S1 Gazebo Tibia → ~2.5 in /joint_states, kein Error | ✅ | |
| S2 Aufstehen + Laufen wie gehabt (keine Regression) | ✅ | |
| S3 RViz-Slider/Modell erreicht +2.5 | ✅ | |

> **→ Wenn §S grün: committen, dann §T (Hardware).**

---

# §T — HARDWARE (aufgebockt) — erst NACH §S + Commit  [Checkliste 2.1.8]

## T0 — Build + Launch (neue URDF/Cal laden)

```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description hexapod_kinematics hexapod_gait
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
(on_activate schließt das Relay + fährt auf power_on_mid. **Läuft weiter in Terminal 1.**)

**Terminal 2 — RViz (HW↔Sim-Vergleich):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
Fixed Frame `base_link`. RViz nutzt jetzt die +2.5-URDF → der Slider/das Modell zeigt
die volle Beuge.

---

## T1 — [2.1.6] leg_1 einzeln: Tibia langsam 0 → +2.5 (Reach + Body-Beobachtung)

Femur **oben** (−0.4 rad ≈ 23° hoch, wie beim Laufen), coxa 0, Tibia langsam zur
neuen Grenze. Terminal 3:
```bash
cd ~/hexapod_ws && source install/setup.bash
# Zwischenstufe +1.30 (altes Limit) — Referenz
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, -0.4, 1.30], time_from_start: {sec: 3}}]}"
sleep 4
# Neuer Bereich +2.0
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, -0.4, 2.0], time_from_start: {sec: 3}}]}"
sleep 4
# Neues Limit +2.5
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, -0.4, 2.5], time_from_start: {sec: 4}}]}"
```
**Erwartung:** Tibia faltet weit ein (~143° bei +2.5), **HW = RViz**, kein
`SAFETY FREEZE` (Terminal 1), kein Stall/Brummen. Fuß curlt Richtung Body —
**beobachten, ob/wann er das Chassis berührt.** Berührt er **vor** +2.5 → Marge für
die feet-closer Pose (Teil 2.2) ist kleiner als gedacht → Wert melden.

## T2 — [2.1.6] leg_5 einzeln (puls-engster Servo, max 2479 µs)

leg_5 ist puls-seitig am knappsten (+2.5 → pulse_max 2479, nur 21 µs unter 2500).
Hier zeigt sich, ob +2.5 **ohne Sättigung/Brummen** erreicht wird:
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_5_coxa_joint, leg_5_femur_joint, leg_5_tibia_joint], points: [{positions: [0.0, -0.4, 2.5], time_from_start: {sec: 4}}]}"
```
**Erwartung:** erreicht +2.5 sauber, kein Anschlag-Brummen (Servo nicht in der
500/2500-Sättigung). Falls es bei ~146° „hängt"/brummt → pulse_max zu hoch gepeilt →
melden (dann leg_5-spezifisch nachziehen).

## T3 — [2.1.6] alle 6: Sweep zur neuen Grenze + zurück, kein Freeze

Erst wenn T1/T2 sauber waren. Femur oben, alle 6 zu +2.5, dann zurück auf eine
neutrale Beuge:
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, -0.4, 2.5], time_from_start: {sec: 4}}]}"
done
sleep 6
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, -0.4, 0.5], time_from_start: {sec: 3}}]}"
done
```
**Erwartung:** alle 6 erreichen +2.5 symmetrisch (HW = RViz), kein `SAFETY FREEZE` /
`OVERCURRENT` / `WATCHDOG` (Terminal 1), kein `IKError` (es werden direkte
Joint-Targets gesendet, keine IK — Freeze käme nur aus dem Safety-Layer).

## T4 — [optional, informiert 2.2] Body-Marge bei Femur **horizontal**

Grenzfall: Femur horizontal (0.0) + +2.5 (143°) liegt nahe an der ~150°-Kollisions-
Grenze (laut Hand-Befund §4.2.0). **Sehr langsam, genau beobachten:**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, 0.0, 2.3], time_from_start: {sec: 4}}]}"
```
**Erwartung/Zweck:** Abschätzen, wie viel Body-Marge bei Femur-horizontal real bleibt
(fürs Pose-Tuning in 2.2). **Kein Done-Kriterium** — nur Beobachtung. Bei Berührung
nicht weiter erhöhen.

---

## Findings / Status (User) — Checkliste 2.1.8 — ✅ alle grün 2026-06-02

| Test | Status | Notiz |
|---|---|---|
| T1 leg_1 0→+2.5 (Femur oben), HW=RViz, kein Freeze | ✅ | |
| T2 leg_5 +2.5 ohne Sättigung/Brummen | ✅ | puls-engster Servo ok |
| T3 alle 6 zur Grenze + zurück, kein Freeze | ✅ | symmetrisch |
| T4 (optional) Body-Marge Femur-horizontal | ✅ | informiert Pose-Tuning 2.2 |
</content>
