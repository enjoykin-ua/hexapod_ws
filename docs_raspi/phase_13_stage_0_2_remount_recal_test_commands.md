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

**Messwerte-Tabelle (User füllt aus):**

| Pin | Bein | dir | pulse_zero (horiz) | up-µs | down-µs | → pulse_min | → pulse_max |
|---|---|---|---|---|---|---|---|
| 1  | leg_1 femur | +1 | | | | | |
| 4  | leg_2 femur | +1 | | | | | |
| 7  | leg_3 femur | +1 | | | | | |
| 10 | leg_4 femur | −1 | | | | | |
| 13 | leg_5 femur | −1 | | | | | |
| 16 | leg_6 femur | −1 | | | | | |

**(0.2.6) Speichern** (Pre-Check `pulse_min < pulse_zero < pulse_max` pro Pin):
```bash
hexapod-save-cal        # Alias (Memory project_phase11_convenience_aliases), sonst:
ros2 service call /save_calibration std_srvs/srv/Trigger {}
```

---

## 3 — Limit-Herleitung (§1.3, Magnituden)

Pro Pin `k` aus **altem** Cal: `k = (pulse_max_alt − pulse_min_alt) / 2.986`
(alte Limits ±1.493). Dann:
- `joint_upper = |down_µs − pulse_zero_neu| / k`
- `joint_lower = −|up_µs − pulse_zero_neu| / k`

| Pin | k (alt) | joint_lower (−) | joint_upper (+) |
|---|---|---|---|
| 1  | | | |
| 4  | | | |
| 7  | | | |
| 10 | | | |
| 13 | | | |
| 16 | | | |

**(0.2.8) Entscheidung global vs per-Bein:** streuen die 6 `joint_upper`/
`joint_lower` < ~2° → **global** (konservativstes Min). Sonst → **per-Bein**.
→ Claude trägt die Werte in `hexapod_physical_properties.xacro` + `config.py`
ein (0.2.9/0.2.10), Build + IK-Regression-Tests (0.2.11/0.2.12).

---

## 4 — Verifikation (nach Re-Cal + Limit-Update + Build)

| # | Befehl / Aktion | Erwartung |
|---|---|---|
| 0.2.13 | alle Femurs `rad=0` (JTC, wie §1) + RViz offen | HW **horizontal** UND RViz horizontal — identisch |
| 0.2.14 | alle Femurs `rad=-0.611` | HW **~35° hoch** UND RViz identisch; PWM ≈ Servo-Mitte (~1500) |
| 0.2.15 | Femur langsam über `[joint_lower, joint_upper]` sweepen | kein PWM-OoR-Freeze, kein Servo-Stall am Anschlag |
| 0.2.16 | Relay aus → Plugin neu → `/hexapod_relay_set true` | Femurs fahren auf ~35° hoch (= Servo-Mitte), **kein** Sprung Richtung horizontal |
| (opt.) | Protraktor an 1–2 Beinen am Down-Anschlag vs. `joint_upper·180/π` | Abweichung ≤ ±2° |

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
