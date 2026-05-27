# Stage F (Femur-Asymmetrie-Fix via Wasserwaage) — Test-Commands [ARCHIVIERT]

> **⚠️ ARCHIVIERT 2026-05-25 — Test-Commands nie ausgeführt.**
>
> Diese Test-Commands waren für den Wasserwaage-Trim-Ansatz. Nach
> tieferer Analyse stellte sich heraus: Asymmetrie ist URDF-rad-
> Limit-Encoding, nicht pulse_zero-Drift. Neuer Ansatz:
> [`servo_real_cal_stage_f_urdf_symmetrize_test_commands.md`](servo_real_cal_stage_f_urdf_symmetrize_test_commands.md).
>
> **Datei bleibt als Audit-Trail erhalten.**

---

# Stage F (Femur-Asymmetrie-Fix) — Test-Commands [historische Version]

> Operative Anleitung für die Femur-pulse_zero-Re-Cal. Plan-Doku +
> Erfolgs-Kriterien:
> [`servo_real_cal_stage_f_femur_plan.md`](servo_real_cal_stage_f_femur_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (`hexapod_bringup real.launch.py`, Servo2040 + USB)
> - `T2` = RViz (`display.launch.py with_jsp_gui:=false`, optional visual)
> - `T3` = Joint-Trajectory-Publisher + `ros2 param set` + Inspect
> - `T4` = rqt_reconfigure (optional GUI-Alternative zu CLI)
>
> User führt aus, meldet pro Femur kurz Status: ✓ horizontal getrimmt +
> neuer pulse_zero-Wert.

---

## ⚠️ SAFETY — vor jedem Befehl

- ✅ Hexapod aufgebockt, alle 6 Beine hängen frei
- ✅ Hardware-Kill-Switch am Servo-PSU griffbereit
- ✅ Wasserwaage bereit (libellengenau)
- ✅ Niemand/nichts im 30 cm-Radius
- ✅ Workspace gebaut + gesourct in allen Terminals:
  ```bash
  cd ~/hexapod_ws
  colcon build
  source install/setup.bash
  ```

**Notfall-Stop:** Kill-Switch first → dann Strg+C in T1/T3.

---

## SCHRITT 1 — Plugin starten (T1)

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartung:**
- Plugin-Init-Logs durchgelaufen (`Stage 0.5: /hexapod_safety_reset service ready`, 6× `Configured and activated leg_<n>_controller`)
- KEIN `safety_freeze`-Trigger
- Alle 6 Beine visuell in T-Pose

**❌ Falls safety_freeze beim Init:** STOP — irgendein pulse_zero ist
bereits außerhalb [pulse_min, pulse_max]. Cal-Doku prüfen.

---

## SCHRITT 2 — RViz starten (T2, optional)

**T2:**
```bash
ros2 launch hexapod_description display.launch.py with_jsp_gui:=false
```

> Nutzbar als visueller Cross-Check parallel zur Hardware. Nicht zwingend.

---

## SCHRITT 3 — Sanity Pre-Stage-F (T3)

Alle 6 Femur-Servos zu rad=0 fahren und Stand-Bild als "vorher"
festhalten — visueller Beweis dass Asymmetrie noch da ist.

**T3 — alle 6 Beine sequenziell auf rad=0:**

```bash
for N in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${N}_controller/joint_trajectory \
    trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [\"leg_${N}_coxa_joint\", \"leg_${N}_femur_joint\", \"leg_${N}_tibia_joint\"],
      points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
  sleep 3
done
```

**Erwartung:** alle 6 Beine in T-Pose. Visuell sollten die Femur-
Segmente **nicht alle gleich** liegen — rechts (legs 1/2/3) und links
(legs 4/5/6) systematisch unterschiedlich ~5° gegen Horizontal.

→ **Foto/Beobachtung notieren** als Pre-Stage-F-Referenz.

---

## SCHRITT 4 — Pro Femur trimmen

> **Reihenfolge (F-Q2-Vorschlag):** rechts-erst → leg_1, leg_2, leg_3,
> dann links → leg_4, leg_5, leg_6.
>
> **Pin-Mapping Femur:**
>
> | Bein | Pin |
> |---|---|
> | leg_1 (vorne rechts) | 1 |
> | leg_2 (mitte rechts) | 4 |
> | leg_3 (hinten rechts) | 7 |
> | leg_4 (hinten links) | 10 |
> | leg_5 (mitte links) | 13 |
> | leg_6 (vorne links) | 16 |
>
> **Trim-Schritt (F-Q1):** 10 µs für Erst-Annäherung, 5 µs für Fein-Trim.

### 4.1 leg_1 Femur (Pin 1)

**Schritt 1 — Aktuellen Wert lesen (T3):**
```bash
ros2 param get /hexapodsystem pin_1.pulse_zero
```
→ Erwartet: ~1460 µs. **Notieren als alten Wert.**

**Schritt 2 — Bein zu rad=0 fahren (T3):**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Schritt 3 — Wasserwaage anlegen** (Oberkante Femur-Segment, parallel
zur Femur-Längsachse). Libelle zeigt Ausschlag.

**Schritt 4 — Trim live:**
```bash
# Trim-Beispiel — pulse_zero um 10 µs erhöhen (oder senken je nach Ausschlag):
ros2 param set /hexapodsystem pin_1.pulse_zero 1470
```

Bein bewegt sich live nach (Plugin liest Param sofort). Wasserwaage
beobachten. Solange wiederholen mit ±10 µs / ±5 µs bis Libelle in Mitte.

> **Alternative via rqt (T4):**
> ```bash
> ros2 run rqt_reconfigure rqt_reconfigure
> ```
> → Pin "1" auswählen → Slider `pulse_zero` klicken.

**Schritt 5 — Finaler Wert ablesen + notieren:**
```bash
ros2 param get /hexapodsystem pin_1.pulse_zero
```
→ **Notieren als neuer Wert.**

**Status leg_1:** alt = ____  µs, neu = ____  µs, Δ = ____  µs

### 4.2 leg_2 Femur (Pin 4)

**Aktuellen Wert lesen:**
```bash
ros2 param get /hexapodsystem pin_4.pulse_zero
```

**Bein zu rad=0 (nur dieses Bein):**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Trim (Beispiel):**
```bash
ros2 param set /hexapodsystem pin_4.pulse_zero 1540
```

**Status leg_2:** alt = ____  µs, neu = ____  µs

### 4.3 leg_3 Femur (Pin 7)

**Aktuellen Wert lesen:**
```bash
ros2 param get /hexapodsystem pin_7.pulse_zero
```

**Bein zu rad=0:**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Trim:**
```bash
ros2 param set /hexapodsystem pin_7.pulse_zero <neuer_wert>
```

**Status leg_3:** alt = ____  µs, neu = ____  µs

### 4.4 leg_4 Femur (Pin 10)

**Aktuellen Wert lesen:**
```bash
ros2 param get /hexapodsystem pin_10.pulse_zero
```

**Bein zu rad=0:**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Trim:**
```bash
ros2 param set /hexapodsystem pin_10.pulse_zero <neuer_wert>
```

**Status leg_4:** alt = ____  µs, neu = ____  µs

### 4.5 leg_5 Femur (Pin 13)

**Aktuellen Wert lesen:**
```bash
ros2 param get /hexapodsystem pin_13.pulse_zero
```

**Bein zu rad=0:**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Trim:**
```bash
ros2 param set /hexapodsystem pin_13.pulse_zero <neuer_wert>
```

**Status leg_5:** alt = ____  µs, neu = ____  µs

### 4.6 leg_6 Femur (Pin 16)

**Aktuellen Wert lesen:**
```bash
ros2 param get /hexapodsystem pin_16.pulse_zero
```

**Bein zu rad=0:**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Trim:**
```bash
ros2 param set /hexapodsystem pin_16.pulse_zero <neuer_wert>
```

**Status leg_6:** alt = ____  µs, neu = ____  µs

---

## SCHRITT 5 — Pre-Check vor Persistierung (T3, KRITISCH)

> **Mitigation R2 aus Pre-Bringup-Plan:** Verifizieren dass alle 6
> neuen pulse_zero-Werte innerhalb [pulse_min, pulse_max] liegen,
> sonst feuert Plugin Stage 0.5 safety_freeze beim Restart.

**T3 — Pre-Check für alle 6 Femur-Pins:**

```bash
for PIN in 1 4 7 10 13 16; do
  MIN=$(ros2 param get /hexapodsystem pin_${PIN}.pulse_min | grep -oP '\d+')
  ZERO=$(ros2 param get /hexapodsystem pin_${PIN}.pulse_zero | grep -oP '\d+')
  MAX=$(ros2 param get /hexapodsystem pin_${PIN}.pulse_max | grep -oP '\d+')
  if [ "$ZERO" -gt "$MIN" ] && [ "$ZERO" -lt "$MAX" ]; then
    echo "Pin ${PIN}: ✓ ${MIN} < ${ZERO} < ${MAX}"
  else
    echo "Pin ${PIN}: ❌ ${MIN} < ${ZERO} < ${MAX} — VERLETZT, NICHT PERSISTIEREN"
  fi
done
```

**Erwartung:** alle 6 Zeilen ✓.

**❌ Falls eine Zeile ❌:** STOP, **nicht** zu Schritt 6. Stattdessen:
- Welcher Pin? `pulse_zero` korrigieren (raus aus dem Anschlag)
- Pre-Check nochmal laufen lassen

---

## SCHRITT 6 — Persistierung via `/save_calibration` (T3)

**Nur wenn Schritt 5 alle ✓ zeigt.**

**T3:**
```bash
ros2 service call /save_calibration std_srvs/srv/Trigger '{}'
```

**Erwartung:**
- Response: `success: true`, `message` enthält Pfad zur Backup-Datei
  (z.B. `servo_mapping.yaml.bak.2026-05-25T10-30-45`)
- Plugin-Logs (T1) zeigen Persistierung-Bestätigung

**Verifizieren in T3:**
```bash
ls -la src/hexapod_hardware/config/servo_mapping.yaml*
```
→ Erwartet: Original `.yaml` (geändert) + `.bak.<timestamp>`-File.

**Diff prüfen:**
```bash
diff src/hexapod_hardware/config/servo_mapping.yaml.bak.* \
     src/hexapod_hardware/config/servo_mapping.yaml | head -50
```
→ Erwartet: nur Pins 1, 4, 7, 10, 13, 16 `pulse_zero`-Zeilen geändert.

---

## SCHRITT 7 — Plugin-Restart + Sanity (T1)

**T1 — Strg+C zum aktuellen Plugin, dann neu starten:**

```bash
# Strg+C zuerst, dann:
ros2 launch hexapod_bringup real.launch.py
```

**Erwartung:**
- Plugin-Init wie in Schritt 1, KEIN safety_freeze
- Plugin lädt YAML mit den **neuen** pulse_zero-Werten

**Verifizieren in T3:**
```bash
ros2 param get /hexapodsystem pin_1.pulse_zero
# Sollte den neuen Wert zeigen (nicht 1460 aus dem Pre-Stage-F-Stand)
```

---

## SCHRITT 8 — Stand-Pose-Symmetrie-Test mit gait_node (T2 + visual)

> **Direkt-Verifikation des Stage F Ziels.** Stand-Pose vor Stage F
> war visuell asymmetrisch rechts/links (das war der Trigger für Stage
> F). Nach Stage F sollte sie symmetrisch sein.

**T2 (neu — gait_node ohne cmd_vel):**
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

**Erwartung:**
- gait_node-Init-Logs wie in Stage E2.3
- **KEIN** `IKError`
- **KEIN** `safety_freeze` in T1
- Alle 6 Beine fahren simultan in Stand-Pose
- **Visuell:** Femur rechts (legs 1/2/3) und links (legs 4/5/6) sind
  jetzt **symmetrisch eingeknickt** (vergleiche mit Pre-Stage-F-Foto
  aus Schritt 3)

→ **Foto/Beobachtung als Post-Stage-F-Referenz notieren.**

**Bei ✓:** Stage F erfolgreich. Strg+C in T2 zum Beenden.

**Bei ❌ (visuell immer noch asymmetrisch):** Wasserwaage-Trim hat nicht
voll gegriffen. Möglich:
- Stage F-Trim war zu grob → Schritt 4 mit feineren 5-µs-Steps wiederholen
- Mechanische Asymmetrie (Servo-Mount) → R-Femur-Mechanisch — STAGE F
  schließen mit Restproblem, Option C (URDF mount_offset) als Phase-13-
  Pendenz öffnen

---

## SCHRITT 9 — (Optional) Walking-Sanity (T3)

> Bestätigt R1-Streichung — sim_walk.yaml bleibt valid nach Stage F.

**T3 (gait_node läuft weiter aus Schritt 8):**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartung:** Walking läuft wie in Stage E2.4 (Tripod-Rhythmus, kein
IKError). 30 s laufen lassen.

**Strg+C in T3, T2, T1 zum Beenden.**

---

## SCHRITT 10 — Sauber Beenden

Reihenfolge:
1. T3 — cmd_vel-Publisher (falls noch läuft)
2. T2 — gait_node
3. T1 — Plugin (`real.launch.py`)
4. T4 / RViz (falls offen)

**Verifikation:**
```bash
ps aux | grep -E "gait_node|controller_manager|hexapod" | grep -v grep
```
→ Erwartet: leer.

---

## Status-Meldung an Claude

Nach Stage F kurz Bescheid geben:

```
Stage F (Femur-Asymmetrie-Fix):
  S1 Plugin-Start (vor Stage F):  ✓ / ❌
  S3 Pre-Stage-F Asymm sichtbar:  ✓ / ❌
  S4 Trims (alt → neu) µs:
    leg_1 (Pin 1):   1460 → ____
    leg_2 (Pin 4):   1550 → ____
    leg_3 (Pin 7):   1445 → ____
    leg_4 (Pin 10):  1560 → ____
    leg_5 (Pin 13):  1530 → ____
    leg_6 (Pin 16):  1540 → ____
  S5 Pre-Check (alle pulse_min<zero<max): ✓ / ❌
  S6 /save_calibration + Backup: ✓ / ❌
  S7 Plugin-Restart (kein freeze): ✓ / ❌
  S8 Stand-Pose visuell symmetrisch: ✓ / ❌
  S9 (optional) Walking 0.02 m/s: ✓ / ❌
  S10 Sauber beendet: ✓ / ❌

Beobachtungen:
  - Wasserwaage-Trim für jeden Femur möglich?  <ja/nein, welcher Bein wenn nein>
  - Trim-Steps gebraucht pro Bein:             <ca-Zahl>
  - Mechanische Auffälligkeiten:               <kurz>
```

---

## Diagnostik-Snippets bei Problemen

### Wenn pulse_zero out-of-range gesetzt wurde und freeze triggered

**T3:**
```bash
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger '{}'
# Dann betroffenen Pin korrigieren:
ros2 param set /hexapodsystem pin_<N>.pulse_zero <korrigierter_wert>
```

Falls reset-Service den freeze nicht löst: Plugin-Restart (`real.launch.py` neu).

### Wenn YAML-Persistierung fehlschlägt (`/save_calibration` Response success: false)

T1-Plugin-Logs prüfen:
```bash
# In T1 visuell scrollen oder:
ros2 log get /hexapodsystem
```

Manuelles Backup + Edit-Path:
```bash
cp src/hexapod_hardware/config/servo_mapping.yaml \
   src/hexapod_hardware/config/servo_mapping.yaml.bak.manual.$(date +%FT%H-%M-%S)
# Werte manuell in YAML editieren als Fallback
```

### Wenn nach Stage F neuer IKError in gait_node

Sollte laut R1-Analyse nicht passieren. Wenn doch:
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  body_height:=-0.05 \
  step_length_max:=0.02 \
  # ... konservativere Werte als sim_walk.yaml
```
→ Konservativ-Test bestätigt ob Cal-Stand neu envelope nötig.

### Wenn pre-Stage-F Stand-Pose schon symmetrisch wirkt

Möglich dass die 5° aus E2.3-Beobachtung subjektiv überschätzt waren.
- Wasserwaage trotzdem anlegen pro Femur → wenn Libelle wirklich in
  Mitte: nichts trimmen für diesen Pin, weiter zum nächsten
- Stage F kann auch teil-trivial enden, falls Asymmetrie schon klein war

---

**Erstellt 2026-05-25.** Plan + Konzept liegt in
[`servo_real_cal_stage_f_femur_plan.md`](servo_real_cal_stage_f_femur_plan.md).
Übergeordnet: [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md).
