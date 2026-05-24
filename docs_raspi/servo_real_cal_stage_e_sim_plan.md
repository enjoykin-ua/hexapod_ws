# Stage E (Sim-Vorab) — Sim-Walking-Verifikation

> **Status:** Vorab-Sim-Smoke ohne Hardware, vor Stage C (Direction-Cal HW).
>
> **Operative Anleitung:** [`servo_real_cal_stage_e_sim_test_commands.md`](servo_real_cal_stage_e_sim_test_commands.md)
> (Terminal-für-Terminal-Snippets mit erwarteten Outputs).
>
> **Vorbedingungen:** Stages 0/0.5/0.6/A/B/D fertig & committed
> (servo_real_cal_plan.md status-Tabelle alle ✅).

---

## 1. Ziel

Verifizieren dass die in Stage A/B/D eingetragenen Cal-Werte (PWM in
servo_mapping.yaml + rad-Limits in URDF) im **Sim-Stack** (Gazebo +
ros2_control + gait_engine) ein **stabiles Walking** produzieren —
**bevor wir die Hardware aufbocken**.

Damit fangen wir math-/cal-Probleme früh ab, ohne Servo-Risiko.

## 2. Was Stage E (Sim) verifiziert

| Aspekt | Verifikations-Mechanismus |
|---|---|
| URDF konsistent (`<limit>` ↔ `<param min/max>`) | Plugin-Init im Sim würde sonst loud failen — beobachtbar in Gazebo-Launch-Log |
| Stand-Pose erreichbar mit den neuen rad-Limits | RViz/Gazebo Visual — alle 6 Beine radial nach außen, keine verdrehten Joints |
| IK kommt mit den engeren Limits klar | gait_node-Logs: keine `IKError: joint limit ...` bei normaler Stand-Pose |
| gait_engine produziert Walking-Trajektorien innerhalb URDF-Range | gait_node-Logs: keine IKError bei `cmd_vel`-Befehlen |
| Plugin-side safety_freeze triggert NICHT im Sim | Sim nutzt gz_ros2_control, nicht hexapod_hardware → safety_freeze ist Plugin-spezifisch, ist im Sim nicht aktiv |
| Stage-0.6-IK-Joint-Limit-Check funktioniert end-to-end | bei extremem `cmd_vel`: IK wirft joint-limit-Error, gait_node loggt + Service-Fallback-Log |
| Mittel-Beine (leg_2/leg_5) mit ihrer engeren Coxa-Range halten Tripod-Gait | visual: keine asynchronen Beine, keine Bein-Hänger |

## 3. Was Stage E (Sim) NICHT verifiziert

- Echte Servo-Bewegung (kein Strom, keine Mechanik-Toleranz)
- Direction-Map (Sim nutzt URDF-rad direkt, kein PWM-Mapping)
- Plugin-Calibration-Load (Sim nutzt gz_ros2_control)
- Pose-Stabilität auf echtem Boden (Sim hat ideale Reibung)
- Mount-Spiel, Servo-Latenz, Strom-Begrenzungen

→ Diese Aspekte kommen in **Stage E2 (HW-Walking aufgebockt)** nach
Stage C (Direction-Cal).

## 4. Sub-Stages

### E.1 — Hexapod spawnt in Gazebo

`sim.launch.py` startet sauber durch. Gazebo zeigt Hexapod in Stand-Pose.
Keine xacro-Errors im Launch-Log.

**Erfolg:**
- Roboter ist sichtbar in Gazebo-Window
- Alle 6 Beine ausgestreckt radial nach außen
- Body schwebt knapp über dem Boden (body_height ≈ -0.05 m)
- Keine "joint limit violation"-Errors im Terminal

### E.2 — Controller-Manager + JointTrajectoryControllers loaded

`ros2 control list_controllers` zeigt 6 active controllers (einen pro Bein).

**Erfolg:**
- 6 Einträge mit Status `active`

### E.3 — gait_node startet im Sim-Mode

gait_node startet ohne IK-Init-Errors. URDF wird via `/robot_description`
geparst, gait_engine kriegt joint_limits per Bein.

**Erfolg:**
- gait_node-Log: `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- Status STATE_STANDING (visual: Hexapod hält Stand-Pose)

### E.4 — Walking-Smoke mit kleiner cmd_vel

`cmd_vel linear.x = 0.02 m/s` (entspricht ~2 cm/s — sehr langsam, sicher
innerhalb step_length_max).

**Erfolg:**
- Hexapod bewegt sich nach vorne
- Alle 6 Beine im Tripod-Rhythmus (3 stance / 3 swing alternierend)
- KEINE IKError-Logs in 30 Sekunden Walking
- KEINE asynchronen Beine, KEINE Glitches

### E.5 — Extremfall-Test (provoziert IK-Joint-Limit-Error)

Sehr großes `cmd_vel linear.x = 0.5 m/s` (10× normal) — soll IK an die
Limits zwingen.

**Erfolg:**
- gait_node-Log: `IK failed for leg_X ... : joint limit ...`
- gait_node-Log: `/hexapod_safety_freeze service not available — proceeding with local stop only` (Sim hat kein hexapod_hardware-Plugin)
- Hexapod stoppt lokal (kein neuer Trajectory-Publish in betroffenen Ticks)
- KEIN Crash, KEIN Hänger

### E.6 — Sauber Beenden

Strg+C in alle Terminals. Keine zombie-Prozesse.

## 5. Risiken & Failure-Modes

| Symptom | Wahrscheinliche Ursache | Aktion |
|---|---|---|
| Gazebo-Spawn schlägt fehl mit URDF-Parse-Error | xacro-Output invalid | `xacro` manuell ausführen, Error lokalisieren |
| Hexapod spawnt verdreht / Bein klappt durch Boden | URDF-Limits-Wert falsch (z.B. lower > upper) | Plan-Doku-Stage-D-rad-Limits prüfen, Cal-Doku Tab. 3.3 sync |
| IKError bei Stand-Pose ohne cmd_vel | Stand-Pose-Foot-Punkt ist außerhalb URDF-Joint-Limits | gait_node defaults check: radial_distance / body_height / step_height passen zu cal-Range? Ggf. Stage 0.6 sagt: Cal zu eng |
| Walking startet aber Mittel-Bein hängt | leg_2/5 Coxa-Range zu eng für aktuellen step_length_max | gait_node Param `step_length_max` reduzieren |
| Hexapod fällt um nach 1-2 Schritten | Cal-Werte mit Sim-Physik inkompatibel (z.B. Femur kann nicht hoch genug heben) | Cal-Doku-Werte prüfen, evtl. Phase-13-Pendenz dokumentieren |
| safety_freeze loggt im Sim | gait_engine löst aus, aber Sim hat kein hexapod_hardware | OK — Stage 0.6 Service-Fallback-Pfad funktioniert |
| Build-Error nach Pull | Stage 0-D nicht alle committed/installed | `colcon build` aller 4 Pakete + neu sourcen |

## 6. Erfolgs-Kriterien — Stage E (Sim) DONE

| # | Kriterium |
|---|---|
| 1 | sim.launch.py startet ohne Errors |
| 2 | Hexapod sichtbar in Gazebo, Stand-Pose visuell normal |
| 3 | 6 active controllers in `ros2 control list_controllers` |
| 4 | gait_node-Log zeigt URDF-Joint-Limits-Parse erfolgreich für 6 Beine |
| 5 | Walking mit cmd_vel x=0.02 läuft ≥30 s ohne IKError |
| 6 | Extremfall cmd_vel x=0.5 produziert erwartete joint-limit-Logs + lokalen Stop |
| 7 | Sauberes Beenden ohne zombie-Prozesse |

## 7. Was passiert wenn alles grün

→ Cal-Werte sind sim-getestet → bereit für Stage C (HW-Direction-Cal).

→ In Stage C verwenden wir die Sim-Stand-Pose als Referenz: HW-Joints
müssen sich genau wie Sim-Joints bewegen (sonst direction-Flip).

## 8. Was passiert wenn Probleme

- **Wenn IK-Errors bei normaler Stand-Pose:** Cal-Werte sind zu eng.
  Vermutlich Tibia oder Femur (siehe Cal-Doku 3.5 Tibia-Mount-Offset).
  → Cal-Doku Tab. 3.3 prüfen, ggf. neu vermessen.

- **Wenn Hexapod kippt:** mech-Limits zu schmal um Stand-Pose zu halten.
  Möglich dass Cal-Tab. 3.3 für ein Bein zu klein gewählt ist.
  → Cal-Doku Findings re-checken, ggf. Stage-13-Pendenz „cal nachmessen".

- **Wenn Walking funktioniert aber Mittel-Bein hängt:** leg_2/5 Coxa-Range
  (50°) ist enger als step_length_max der gait_node defaults.
  → gait_node Param `step_length_max` per rqt_reconfigure reduzieren bis
  IK-Errors verschwinden. Wert dokumentieren für Stage E2 (HW).

## 9. Beobachtungs-Notizen

User soll während E.4-E.5 Notizen machen:
- **Walking-Visual:** glatt / ruckelig / asynchron?
- **Tibia-Bewegung:** zeigt sie sichtbare Range-Nutzung oder ist sie immer
  „in der Mitte"? (Antwort beeinflusst ob asymm-Limits sich auszahlen)
- **Mittel-Beine:** halten die Tripod-Sync oder fallen sie raus?
- **Body-Höhe:** stabil oder oszilliert sie?

Diese Notizen helfen bei Stage E2 (HW): wenn Sim glatt läuft aber HW
ruckelt, ist's Servo-Latenz / Strom-Limit / Mechanik. Wenn schon Sim
ruckelt: Cal-Werte oder gait-Params.

---

**Erstellt 2026-05-24 nach Stage D abgeschlossen. Operative Anleitung
liegt in [`servo_real_cal_stage_e_sim_test_commands.md`](servo_real_cal_stage_e_sim_test_commands.md).**
