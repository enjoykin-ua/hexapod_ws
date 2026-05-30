# Phase 13 Stage 0.2 — Test-Commands (Femur-Umbau + Re-Cal)

> **Plan:** [`phase_13_stage_0_2_remount_recal_plan.md`](phase_13_stage_0_2_remount_recal_plan.md).
> **Form:** User führt aus, knappe Status (Memory `feedback_interactive_stage_test_doc`).
> Verifikations-Outputs nicht trimmen (`feedback_no_trim_verification_output`).
> **Status:** ⚪ bereit, startet nach Commit.

⚠️ **Sicherheit:** Roboter aufgebockt, PSU-Kill-Switch griffbereit. Beim
Umbau pro Bein einzeln arbeiten, andere Beine halten ihre Position.

---

## 0 — Setup

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false   # use_sim_time MUSS false (HW)
# zweites Terminal:
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"   # Servos bestromen
```
Diagnose-Topic für PWM-Ablesung aktivieren (Phase 11 Stage C):
```bash
ros2 param set /<hardware_node> publish_servo_pulses true     # exakter Node-Name aus Phase 11
ros2 topic echo /servo_pulses                                 # 18 Werte, Index 0..17
```

---

## 1 — Mech-Umbau (§6-Servo-Trick), pro Bein

**Alle 6 Femurs auf rad=+0.611 (35° runter) fahren + halten:**
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory \
    trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, 0.611, 0.0], time_from_start: {sec: 2}}]}"
done
```
Die JTC **hält** danach von selbst (kein Re-Publish nötig).

**Pro Bein (1 → 6):**
1. Femur-Segment vom Servo-Horn lösen (Horn/Welle bleiben in Position).
2. Segment in die **Horizontale** drehen (Wasserwaage) und festschrauben.
3. *(Servo hält weiter +0.611 — Welle verrutscht nicht.)*

**Nach allen 6: rad=0 kommandieren:**
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory \
    trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
done
```
**Erwartung (0.2.1):** alle Femurs zeigen jetzt **~35° nach oben**.
**K2-Check (0.2.2):** pro Bein bestätigen: 35°-Ruhepose berührt **keinen**
Body-/Coxa-Anschlag. **Direction-Check:** wenn ein Bein 35° *runter* statt
*hoch* zeigt → Segment um die Gegenrichtung neu montieren.

> Hinweis: RViz zeigt jetzt bei rad=0 noch *horizontal* (stale Cal) — HW aber
> 35° hoch. Das ist erwartet bis Re-Cal fertig (§2).

---

## 2 — Re-Cal der 6 Femur-Pins (Weg A)

Pro Femur-Pin (Output-Index **1, 4, 7, 10, 13, 16**), via rqt_reconfigure
(Phase-11-Live-Cal):
```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

**(K4) Clamp zuerst weiten** — pulse_min runter / pulse_max hoch innerhalb
[800, 2200], damit die neuen Anschläge erreichbar sind.

Pro Pin messen (PWM am `/servo_pulses`-Topic ablesen):
1. **pulse_zero** — Femur visuell **horizontal** stellen → PWM notieren.
2. **Up-Anschlag** — nach oben bis Body/Coxa-Kollision → PWM notieren.
3. **Down-Anschlag** — nach unten bis Anschlag → PWM notieren.

**(K1) Numerisch zuordnen:** `pulse_min = min(up, down)`,
`pulse_max = max(up, down)`. Rechts (1/4/7… dir +1): up=min, down=max.
Links (10/13/16… dir −1): down=min, up=max.

**Messwerte (gemessen 2026-05-30; up/down bei ±90° zur Horizontalen):**

| Pin | Bein | dir | pulse_zero (horiz) | up-µs (90° hoch) | down-µs (90° runter) | → pulse_min | → pulse_max |
|---|---|---|---|---|---|---|---|
| 1  | leg_1 femur | +1 | 1700 | 1030 | 2350 | 1030 | 2350 |
| 4  | leg_2 femur | +1 | 1780 | 1090 | 2370 | 1090 | 2370 |
| 7  | leg_3 femur | +1 | 1690 | 1010 | 2340 | 1010 | 2340 |
| 10 | leg_4 femur | −1 | 1295 | 1970 | 670  | 670  | 1970 |
| 13 | leg_5 femur | −1 | 1325 | 1980 | 690  | 690  | 1980 |
| 16 | leg_6 femur | −1 | 1290 | 1955 | 655  | 655  | 1955 |

→ in `servo_mapping.yaml` eingetragen (Pins 1/4/7/10/13/16), `pulse_min<zero<max` ✓.

**(0.2.6) Gespeichert:** Werte wurden **direkt von Claude in `servo_mapping.yaml`
geschrieben** (Pins 1/4/7/10/13/16). ⚠️ **NICHT** `/save_calibration` /
`hexapod-save-cal` aufrufen — das würde die yaml mit den rqt-Live-Werten
überschreiben.

---

## 3 — Limits + Steigungs-Cross-Check (Ist 2026-05-30)

Da up/down bei **±90° (=1.5708 rad)** gemessen wurden, ergibt sich die Steigung
**direkt** aus den 3 Referenzpunkten (−90° / 0° / +90°): `slope = |Δµs| / 1.5708`.

| Pin | Bein | slope_up µs/rad | slope_down µs/rad |
|---|---|---|---|
| 1  | leg_1 | 427 | 414 |
| 4  | leg_2 | 439 | 376 |
| 7  | leg_3 | 433 | 414 |
| 10 | leg_4 | 430 | 398 |
| 13 | leg_5 | 417 | 404 |
| 16 | leg_6 | 423 | 404 |

**Cross-Check:** alle ~376–439, Schnitt ~415 µs/rad → passt zur alten Steigung
(2120−1460)/1.57 ≈ **420** → Messungen konsistent. (Leg_2 down 376 leicht
flacher, unkritisch — per-Pin-Cal fängt's ab.)

**(0.2.8) Limit-Entscheidung: GLOBAL symmetrisch.** Da beidseitig saubere ±90°
gemessen wurden, sind die Limits für alle 6 Beine gleich:
`joint_lower = −1.57`, `joint_upper = +1.57`.

**(0.2.9/0.2.10) KORREKTUR (nach Sweep-Freeze):** die Femur-Limits werden über
**per-Bein-Overrides** gesetzt, NICHT über die `femur_lower`-Property. Die
Stage-F-Overrides standen stale auf **±1.493** in `hexapod.urdf.xacro` (6×) +
`hexapod.ros2_control.xacro` (6×). Da pulse_min/max bei **±90°** gemessen wurden,
MUSS `joint_limit = ±1.57` (≈90°) sein (Cal-Formel: rad=joint_lower→pulse_min) —
sonst Skalenfehler + Freeze bei rad<−1.493. → Overrides auf **±1.57** korrigiert,
`hexapod_description` neu gebaut, generierte URDF verifiziert (alle 6 Femur-Joints
`lower=-1.57 upper=1.57`). `config.py` war schon (-1.57,1.57) → jetzt konsistent.
IK-Regression: 351 Tests, 0 Failures.

---

## 4 — Verifikation (nach Re-Cal + Build, **kein FW-Reflash** — nur yaml geändert)

> **Ist-Stand 2026-05-30:** up/down bei **±90°** gemessen. Geändert:
> `servo_mapping.yaml` (6 Femur-Pins) **+** Femur-Joint-Limits ±1.493→±1.57
> (per-Bein-Overrides in `hexapod.urdf.xacro` + `hexapod.ros2_control.xacro`,
> siehe §3-Korrektur). `colcon test` 351/0 grün. **Kein FW-Reflash** (nur
> Host-Seite); aber **Relaunch nötig** damit die neue URDF (±1.57) lädt.

**A — Plugin neu starten (lädt neue yaml).** Terminal 1: `Strg+C`, dann:
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
```

**B — RViz (HW↔Sim-Vergleich).** Terminal 3:
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2
```
Einmalig: **Add → RobotModel**, *Description Topic* = `/robot_description`;
**Fixed Frame** = `base_link`.

**C — Relay an.** Terminal 2:
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"
```

**D — [0.2.13] rad=0 → horizontal.** Terminal 2:
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory \
    trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
done
```
**Erwartung:** alle 6 Femurs physisch **horizontal** UND RViz identisch.

**E — [0.2.14] rad=−0.611 → ~35° hoch.** Terminal 2 (Femur-Wert `-0.611`):
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory \
    trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint],
      points: [{positions: [0.0, -0.611, 0.0], time_from_start: {sec: 2}}]}"
done
```
**Erwartung:** Femurs **~35° hoch** (HW) UND RViz identisch. Kein OoR-Freeze in Terminal 1.

**F — [0.2.15] Sweep über die Range.** Terminal 2 (90° hoch → horizontal → 90° runter):
```bash
# Femur 90° hoch (knapp innerhalb Limit ±1.57)
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, -1.5, 0.0], time_from_start: {sec: 2}}]}"
done
sleep 4
# horizontal
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
done
sleep 4
# Femur 90° runter (knapp innerhalb Limit)
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 1.5, 0.0], time_from_start: {sec: 2}}]}"
done
```
**Erwartung:** Femurs fahren 90° hoch ↔ horizontal ↔ 90° runter, **kein**
OoR-Freeze (`SAFETY FREEZE` in Terminal 1), **kein** Stall/Brummen am Anschlag.

**G — [0.2.16] Power-On-Check.**
```bash
# Terminal 2: Relay aus
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: false}"
# Terminal 1: Strg+C, dann
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
# Terminal 2: Relay an
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"
```
**Erwartung:** Servo-Mitte (1500 µs) liegt im **erhöhten** Bereich (≈ ~27° hoch
nach Messung, nicht exakt 35°), nicht horizontal/unten.
⚠️ **Bekannt (→ Stage 0.3):** das Startup-Verhalten ist hier noch messy — das
alte Preset "suspended" (femur=+1.45 ≈ 90° runter) ist nach dem Umbau obsolet,
und ein JTC-read-Race kann einzelne Beine (v.a. leg_1) abweichen lassen. Wird in
0.3 (relay-gated Init-Sequenz + K3-Init-Pose) gelöst. Für 0.2 irrelevant —
explizite Befehle (D/E/F) funktionieren korrekt.

**(optional)** Protraktor an 1–2 Beinen bei rad=+1.5708 (90° runter) gegen
`joint_upper·180/π` — Abweichung ≤ ±2°.

## Findings-Tabelle Verifikation (User)

| Schritt | Status | Beobachtung |
|---|---|---|
| D rad=0 → horizontal (HW=RViz) | | |
| E rad=−0.611 → 35° hoch (HW=RViz) | | |
| F Sweep ±1.5 ohne Freeze/Stall | | |
| G Power-On erhöht | | |

---

## Findings / Status (User)

| Schritt | Status | Notiz |
|---|---|---|
| 0.2.1 Umbau 6 Femurs | | |
| 0.2.2 35° kollisionsfrei | | |
| 0.2.4/0.2.5 Re-Cal | | |
| 0.2.7 Limits hergeleitet | | |
| 0.2.8 global/per-Bein | | |
| 0.2.13–0.2.16 Live-Verif | | |
