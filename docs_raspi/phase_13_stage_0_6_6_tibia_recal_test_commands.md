# Phase 13 Stage 0.6.6 — Test-Commands: Tibia-Re-Cal Live-Validierung

> **Plan:** [`phase_13_stage_0_6_6_tibia_recal_plan.md`](phase_13_stage_0_6_6_tibia_recal_plan.md).
> **Form:** User führt aus, knappe Status zurück (Memory `feedback_interactive_stage_test_doc`).
> Verifikations-Outputs **nicht** trimmen (`feedback_no_trim_verification_output`).
> **Voraussetzung:** Code 0.6.6 ✅ (Build + 435 Tests + Envelope grün). User hat committet.

⚠️ **Sicherheit (CLAUDE.md §9):** **aufgebockt** zuerst, PSU-Kill-Switch
griffbereit. Erst aufgebockt (T1–T4 + Standup), dann Boden (T5 Strom). Sweep (T4)
langsam, bei Brummen/Stall sofort zurück.

---

## 0 — Build + Launch (neue Cal/URDF laden)

```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description hexapod_kinematics hexapod_gait
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
(on_activate schließt das Relay + fährt auf power_on_mid.)

**RViz (HW↔Sim-Vergleich), Terminal 2:**
```bash
cd ~/hexapod_ws && source install/setup.bash && rviz2
```
Add → RobotModel (Description Topic `/robot_description`), Fixed Frame `base_link`.

---

## T1 — [0.6.6.10] rad=0 → alle 6 Tibias GERADE (pulse_zero-Check)

Femur horizontal (rad 0), Tibia rad 0 → die virtuelle Knie→Fuß-Linie muss
**gerade in Femur-Verlängerung** liegen. Terminal 3:
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
done
```
**Erwartung:** alle 6 Beine gestreckt-gerade (Fuß auf Femur-Linie), HW = RViz.
**Falls ein Bein sichtbar schief:** Pin notieren → `pulse_zero` ±wenige µs
nachtrimmen (rqt, dann sag mir den Wert für die yaml). ~±4° Peilungs-Rest ist erwartbar.

## T2 — [0.6.6.11] rad=+0.758 → Tibia ~43° (Slope-Check)

```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, 0.0, 0.758], time_from_start: {sec: 2}}]}"
done
```
**Erwartung:** Tibia knickt **~43°** von gerade ein (NICHT ~75° wie mit der alten
Cal), HW = RViz. Das ist der Kern-Fix (Über-Knick weg).

## T3 — [0.6.6.11] power_on_mid + Sweep, kein Freeze

power_on_mid steht schon nach Launch (Tibia ~0.2–0.5 rad). **Sweep** über die
Limits (langsam beobachten):
```bash
# Beuge nahe Limit (+1.25, knapp unter +1.30)
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 0.0, 1.25], time_from_start: {sec: 3}}]}"
done
sleep 5
# Streck nahe Limit (-0.95, knapp über -1.00)
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 0.0, -0.95], time_from_start: {sec: 3}}]}"
done
```
**Erwartung:** fährt sauber zu beiden Limits, **kein** `SAFETY FREEZE` (Terminal 1),
**kein** Stall/Brummen. (Bei +1.25 darf der Fuß dem Body nahekommen — beobachten,
nicht in Kollision fahren; falls er anschlägt, Beuge-Limit war zu hoch → melden.)

## T4 — [0.6.6.12] Stand-up aufgebockt (Schürf-Check optisch) — eigenständiger Test

> **Drei getrennte Terminals, kein `&`-Backgrounding.** `real.launch.py` (Hardware)
> läuft durchgehend in Terminal 1; `gait.launch.py` kommt in ein eigenes Terminal
> dazu und steuert die schon laufenden JTCs (es startet **keine** zweite Hardware).
> Frischer Start, damit der Stand-up sauber aus power_on_mid rampt.

**Terminal 1 — Hardware (vorheriges mit `Strg+C` beenden, dann neu):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
→ Init: alle 6 in power_on_mid (Bauch-Pose), Relay an. **Läuft weiter.**

**Terminal 2 — RViz (HW-Spiegel; startet `real.launch.py` aus T1 hat /joint_states + /tf):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
→ Hexapod in power_on_mid, Fixed Frame `base_link`, **keine** „Fixed Frame does not exist".

**Terminal 3 — Stand-up starten (kartesisch, wie 0.7):**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian \
    auto_standup_duration:=8
```
(`robot_description_file` → gait nutzt die **echten** URDF-Limits −1.00/+1.30,
nicht-lenient; `use_sim_time:=false` → kein Timer-Block ohne /clock.)

**Erwartung:** all-6 Aufstehen, **RViz spiegelt synchron**; mit korrigierter
Geometrie kommandiert die IK die richtige, steilere Tibia-Stellung → die Füße
sollten **deutlich weniger einwärts wandern** als in 0.6 (das war der Über-Knick).
Stabile Endpose (coxa~0 / femur −0.24 / tibia +0.76). Terminal 1: kein
`OVERCURRENT`/`WATCHDOG`/`SAFETY FREEZE`; Terminal 3: kein `IKError`.

## T5 — [0.6.6.12] Boden + Strom (Done-Indikator, überlappt 0.7/0.8)

Roboter auf den Boden (Bauch auf), Strom mitloggen (wie 0.7-Boden-Test):
**Erwartung:** Aufsteh-Strom **deutlich näher am Stand-Niveau** (~400 mA) statt
>3,5 A, kein Voltage-Drop/Trip. (Formales Done-Kriterium ist 0.7/0.8; hier
Plausibilität, dass der Tibia-Fix das Schürfen reduziert.)

## T6 — [0.6.6.13] Laufen-Re-Check aufgebockt — eigenständiger Test

> **Vier Terminals.** Setup = T4 (Hardware + RViz + Gait); cmd_vel kommt erst dazu,
> wenn der Gait nach dem Aufstehen in **STATE_STANDING** ist. Frischer Start.

**Terminal 1 — Hardware (vorheriges `Strg+C`, dann neu):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```

**Terminal 2 — RViz:**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```

**Terminal 3 — Gait (Aufstehen → STANDING):**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian \
    auto_standup_duration:=8
```
→ warten bis das Aufstehen fertig ist (Log `STATE_STANDING` / Roboter steht).

**Terminal 4 — Laufen starten (erst NACH STANDING), Vorwärts 0.03 m/s:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```
→ ~8–10 s beobachten, dann **`Strg+C`** (Roboter hält die Stand-Pose). Optional
sanfter `0.02` oder schneller `0.035`.

**Erwartung:** Laufen aufgebockt ohne `IKError`/Freeze (Terminal 3) / `OVERCURRENT`/
`WATCHDOG` (Terminal 1); RViz spiegelt das Gangbild. Fuß-Genauigkeit sollte sich
verbessern (Vorwärts-Walking braucht tibia **+1.185** — jetzt in-limit +1.30,
vorher am alten 1.161 geklippt). **Falls Gangbild auffällig anders/schlechter:**
Presets waren für die schiefe Geometrie getunt → re-tunen (Plan §4.6).

---

## Findings / Status (User)

| Test | Status | Notiz |
|---|---|---|
| T1 rad=0 → 6× gerade (HW=RViz) | ✅ | pulse_zero ok, kein Trim nötig |
| T2 rad=+0.758 → ~43° | ✅ | ~43° statt alter ~75° — Slope-Fix sichtbar |
| T3 Sweep ±Limit ohne Freeze/Stall | ✅ | sauber |
| T4/T5 Aufstehen am Boden + Strom | ✅ | steht stabil (nicht hoch), Strom **weit unter Limit** |
| T6 Laufen-Re-Check | ✅/🟢 | Beine bewegen, kein IKError; Vortrieb gering = Boden-Reibung + Schritthöhe/-weite → Tuning (Next-Steps) |
