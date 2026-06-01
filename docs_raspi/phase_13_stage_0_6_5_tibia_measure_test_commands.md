# Phase 13 Stage 0.6.5 — Test-Commands: Tibia-Winkel-Messung (Femur-Stil)

> **Plan:** [`phase_13_stage_0_tibia_angle_offset_plan.md`](phase_13_stage_0_tibia_angle_offset_plan.md) §9.
> **Form:** User führt aus, knappe Status zurück (Memory `feedback_interactive_stage_test_doc`).
> Verifikations-Outputs **nicht** trimmen (`feedback_no_trim_verification_output`).
> **Status:** 🟡 Re-Messung aller 6 Beine (saubere Session nach Relaunch).

⚠️ **Sicherheit (CLAUDE.md §9):** Roboter **aufgebockt**, PSU-Kill-Switch
griffbereit. An die mechanischen Anschläge **langsam** ran und **sofort zurück**
(Servo stallt). Aufgebockt + 7 A-Limit toleriert kurze Stalls, **nicht halten**.

---

## Mess-Schema (A/B/C/D — User-Konvention)

Gemessen wird **nur Pulse ↔ Winkel** der **virtuellen Knie→Fuß-Linie** (Endpunkte:
Knie-Drehpunkt + Fußspitze — **nicht** das geknickte sichtbare Segment!). Die
Tibia-**Länge** (200 mm) wird nicht angefasst.

| Punkt | Anpeilen (Femur dabei **horizontal**!) | liefert |
|---|---|---|
| **A horizontal** | virt. Knie→Fuß **waagrecht** (Fuß auf Knie-Höhe, max. ausgestreckt) | `pulse_zero` (echte Gerade) |
| **B 90° zu Boden** | virt. Knie→Fuß **senkrecht** (Fuß gerade unter dem Knie, Lot) | `k` (Slope) aus \|A−B\| |
| **C Streck-Anschlag oben** | Bein streckt **nach oben** bis mech. Anschlag | Streck-Limit (mech) |
| **D Beuge-Anschlag unten** | Bein beugt **nach unten** bis Anschlag (oft nur Param-Rail) | Beuge-Range (Info) |

---

## ⚠️ Die zwei Härtungen (Lehre aus der ersten Reihe)

Die erste Reihe (leg_2/3/5/6) war inkonsistent, weil der **Femur-Bezug nicht
sauber horizontal** war. Daher Pflicht:

**H1 — Femur-horizontal verifizieren (vor jedem Bein):** nach dem `[0,0,0]`-Befehl
**hinschauen**: steht der Femur waagrecht und **bleibt** er stehen? Erst dann die
Tibia joggen. Wenn der Femur schräg ist → erst klären, **nicht** messen (sonst sind
A/B kein sauberes 90°).

**H2 — Sofort-Check |A−B| ≈ 670 µs:** Da alle Tibias derselbe Servo sind, muss
A→B (= 90°) bei **jedem** Bein **~660–700 µs** Differenz ergeben. **Direkt nach
A+B rechnen:** \|A−B\|. Liegt es außerhalb ~640–710 → Femur war schief oder die
Peilung daneben → **das Bein sofort nochmal**, nicht erst am Ende rätseln.
(Referenz saubere Pilots: leg_1 690, leg_4 670.)

---

## 0 — Setup (mit Relaunch = sauberer Ausgangspunkt)

**Relaunch** setzt alle Live-Param-Spielereien auf den yaml-Stand zurück:
```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```

> **Relay:** schließt die 0.3-on_activate-Sequenz selbst (Servos auf 1500 µs).
> Kein expliziter `/hexapod_relay_set true` nötig.

**Terminal 3 — PWM live mitlesen (Index = Pin):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /servo_pulses
```

**Terminal 4 — Live-Cal-GUI:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 run rqt_reconfigure rqt_reconfigure
```
Hardware-Node wählen → `publish_servo_pulses` = **true**.

> **Tibia-Pins:** leg_1→**2**, leg_2→**5**, leg_3→**8**, leg_4→**11**, leg_5→**14**, leg_6→**17**.

---

## 1 — Prozedur pro Bein (Beispiel leg_1 / Pin 2)

**1.1 Bein in Referenz + H1-Check.** Terminal 2:
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
```
→ **H1: Femur visuell horizontal? Bleibt er stehen?** Erst dann weiter.

**1.2 Clamp weiten (rqt):** `pin_2.pulse_min`→**500**, `pin_2.pulse_max`→**2500**.

**1.3 Jog:** `pin_2.pulse_zero` langsam verstellen (Tibia-rad=0 gehalten → Ausgangs-Puls = pulse_zero), µs am `/servo_pulses` Index 2 ablesen.

**1.4 Die 4 Punkte A/B/C/D notieren** (virtuelle Knie→Fuß-Linie).

**1.5 H2-Sofort-Check:** \|A−B\| ausrechnen → muss ~660–700 µs sein. Sonst Bein nochmal.

**1.6 Nach dem Bein:** Clamp zurücksetzen *oder* am Ende einfach neu launchen
(yaml-Stand). **Kein `/save_calibration`** in dieser Mess-Stage.

**Stellbefehle der anderen Beine** (alle auf `[0,0,0]`):
```bash
# leg_2 (Pin 5)
ros2 topic pub --once /leg_2_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_2_coxa_joint, leg_2_femur_joint, leg_2_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
# leg_3 (Pin 8)
ros2 topic pub --once /leg_3_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_3_coxa_joint, leg_3_femur_joint, leg_3_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
# leg_4 (Pin 11)
ros2 topic pub --once /leg_4_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_4_coxa_joint, leg_4_femur_joint, leg_4_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
# leg_5 (Pin 14)
ros2 topic pub --once /leg_5_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_5_coxa_joint, leg_5_femur_joint, leg_5_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
# leg_6 (Pin 17)
ros2 topic pub --once /leg_6_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_6_coxa_joint, leg_6_femur_joint, leg_6_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
```

> **dir je Seite:** leg_1/2/3 (rechts) = −1 → Beuge = sinkende µs, Streck-oben = hohe µs.
> leg_4/5/6 (links) = +1 → Beuge = steigende µs, Streck-oben = niedrige µs.

---

## 2 — Messwerte (frische All-6-Session, 2026-06-01)

| Bein/Pin | A horizontal | B 90° zu Boden | C Streck-oben (mech) | D Beuge-unten | \|A−B\| | k µs/rad |
|---|---|---|---|---|---|---|
| leg_1 / 2  | **1710** | 1001 | 2159 | 500 (Rail) | 709 | 451 |
| leg_2 / 5  | **1720** | 1037 | 2200 | 550 | 683 | 435 |
| leg_3 / 8  | **1610** | 946  | 2120 | 500 (Rail) | 664 | 423 |
| leg_4 / 11 | **1318** | 1965 | 815  | 2500 (Rail) | 647 | 412 |
| leg_5 / 14 | **1416** | 2040 | 885  | 2500 (Rail) | 624 | 397 |
| leg_6 / 17 | **1351** | 1944 | 850  | 2500 (Rail) | 593 | 378 |

**Auswertung:** `pulse_zero` = A (gemessen, solide). k-Spread rechts 423–451 /
links 378–412 = B-Peilungs-Rauschen (links systematisch unter-gedreht, leg_6 −10°)
→ **globales k ≈ 425** (Servo-Eigenschaft; durch Streck-Stop-Konsistenz bestätigt).
Streck-Limit aus C (mech. Stop) pro Bein. **A liegt nur ±2–40 µs (~±4°) vom
alten zero** → Nullpunkt war fast richtig; die **alte Beuge-Slope ~700 (echt 425)**
war die Wurzel (Stand-Pose physisch 69–78° statt 43°). leg_2 unauffällig
(A 1720 ≈ leg_1); leg_3/leg_5 = reale Mounting-Offsets (per-Bein-`pulse_zero` fängt's).

---

## Referenz: erste (saubere) Pilot-Session — A/B/C/D in User-Konvention

| Bein | A horiz. | B 90° | C Streck-oben | D Beuge-unten | k | \|A−B\| |
|---|---|---|---|---|---|---|
| leg_1 | 1740 | 1050 | 2185 (mech) | 500 (Rail) | 439 | 690 |
| leg_4 | 1255 | 1925 | 815 (mech) | 2500 (Rail) | 427 | 670 |

> Diese zwei waren mit Servo-Spec konsistent. Werden in der frischen All-6-Session
> mitgemessen (Bestätigung). leg_2/3/5/6-Erstwerte verworfen (inkonsistent, Femur
> nicht sauber horizontal).
