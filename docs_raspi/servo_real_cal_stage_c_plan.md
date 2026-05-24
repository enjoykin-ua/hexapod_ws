# Stage C — Direction-Cal HW+Sim parallel

> **Operative Anleitung:** [`servo_real_cal_stage_c_test_commands.md`](servo_real_cal_stage_c_test_commands.md)
> (Terminal-Setup + Snippets pro Bein).
>
> **Status:** ⏳ wartet auf interaktive Session am Hexapod.
> Vorbedingungen alle erfüllt: Stages 0/0.5/0.6/A/B/D ✅, Sim-Smoke ✅
> (2026-05-24).

---

## 1. Ziel

Pro Servo-Pin ermitteln, ob `direction_normal` auf `+1` oder `-1` gehört.
Plus optional Cal-Werte minimal nachjustieren falls man im Walking-Test
mech-Anschlag-Berührungen entdeckt.

**Operationaler Test:** publiziere einen kleinen Joint-Command (rad=+0.3)
für einen Joint, vergleiche visuell:
- **In RViz** wie der Joint sich dreht (= URDF-Joint-rad-Konvention)
- **An der Hardware** wie der Servo sich dreht (= mech Drehrichtung)

Beide Richtungen müssen ÜBEREINSTIMMEN. Falls nicht: `direction_normal`
für diesen Pin flippen (von +1 → -1 oder umgekehrt) via Live-Param.

## 2. Sicherheits-Schicht aus den vorherigen Stages

Drei Defense-Layer sind aktiv, falls ein Direction-Cal-Test Probleme
provoziert:

| Layer | Wer | Wann triggert |
|---|---|---|
| **URDF-Joint-Limits** | ros2_control JTC clampt rad-Befehl auf URDF-Range | Wenn rad-Command außerhalb [joint_lower, joint_upper] aus Stage D |
| **Stage 0.5 Plugin-Hard-Stop** | Plugin freezed wenn berechnetes pulse außerhalb [pulse_min, pulse_max] | Wenn IK + direction-Setup pulse out-of-range produziert |
| **Stage 0.6 IK-Joint-Limit-Check** | gait_engine wirft IKError, ruft Freeze-Service | Nicht aktiv in Direction-Cal (Stage C nutzt JTC direkt, kein gait_engine) |

→ Bei direction-Mismatch + großem rad-Command würde Plugin spätestens
in Layer 2 stoppen. **Empfehlung: kleine Commands (±0.3 rad) für Tests**,
damit auch bei Mismatch der Servo nicht ans mech-Limit geht.

## 3. Vorbedingungen

| # | Punkt | Status |
|---|---|---|
| 1 | Hexapod aufgebockt, Beine ohne Bodenkontakt | ✅ User 2026-05-23 bestätigt |
| 2 | Servo2040 + USB-Verbindung + Bench-PSU bereit | (User-Check vor Start) |
| 3 | servo_mapping.yaml aktuell (Stage B + Stage D) | ✅ committed |
| 4 | URDF mit echten rad-Limits (Stage D) | ✅ committed |
| 5 | Stage 0.5 + 0.6 safety_freeze-Mechanik aktiv | ✅ committed |
| 6 | leg_6 direction-Werte aus Phase 10 erhalten (-1/-1/+1) | ✅ vorgespeichert in YAML |

## 4. Sub-Stages

### C.1 — Setup + RViz-Reference

Plugin im real-Mode starten (T1) + RViz parallel mit URDF (T2). RViz
visualisiert die per-Plugin gepublishten `/joint_states` und zeigt die
**URDF-rad-Konvention** für jeden Joint. **Kein Gazebo** — gz_ros2_control
und hexapod_hardware können nicht gleichzeitig denselben Joint-Pool
besitzen. RViz ist nur Visualisierung, kein zweites Control-Backend.

Erfolg: Plugin steht in T1 + RViz zeigt Hexapod in Stand-Pose in T2.
JointTrajectory-Publish bewegt Servo (HW) UND Joint-Visual (RViz)
synchron.

### C.2 — leg_6 als Sanity-Anker

leg_6 wurde in Phase 10 schon walking-verifiziert mit direction-Werten
-1/-1/+1. Diese Werte sind im servo_mapping.yaml (Stage B) erhalten
geblieben. **Verifikation:** kleine Commands (±0.3 rad) auf jeden der 3
leg_6-Joints, prüfen:

- coxa (pin 15): RViz dreht in eine Richtung, HW dreht in selbe?
- femur (pin 16): analog
- tibia (pin 17): analog

Erfolg: alle 3 stimmen — Methodik verifiziert. Falls eine direction-
Wert in HW anders aussieht als RViz: Phase-10-Direction falsch +
Mount hat sich seit Phase 10 verändert (unwahrscheinlich, aber check).

### C.3 — leg_1 (Default direction=+1)

Im YAML steht aktuell direction=+1 für alle Pin 0/1/2. Pro Joint:
1. Joint-Command publishen (rad=+0.3)
2. Vergleich RViz vs HW
3. Falls Mismatch: `ros2 param set /hexapodsystem pin_<N>.direction -1`
4. Re-Test mit selbem Command — sollte jetzt stimmen

### C.4 — leg_5 (Default direction=+1)

Analog. Mount-Tausch 2026-05-24 hat leg_5 mit dem alten leg_2-Bein
bestückt. Direction-Pattern ist daher unbekannt — vermutlich Coxa-
Drehrichtung anders als bei leg_4 (Cal-Doku Findings sagen leg_5 hat
Coxa-Servo „verdreht" im Vergleich zu leg_4).

### C.5 — leg_4 (Default direction=+1)

Analog. Linkes Bein wie leg_5, aber mit Original-Bein-Modul.

### C.6 — leg_3 (Default direction=+1)

Rechtes Bein. Mount unverändert seit Cal-Session.

### C.7 — leg_2 (Default direction=+1)

Rechtes Bein, jetzt mit Mount-Tausch-Bein. Direction-Pattern dürfte zur
rechten Seite passen, aber Bein-Modul-Drehrichtung könnte anders sein.

### C.8 — Persistieren

`/save_calibration` schreibt die direction-Werte ins install-Tree-YAML
mit Timestamp-Backup. Danach manuell von install/ nach src/ kopieren
damit's in Git landet.

## 5. Erwartete Direction-Map (Hypothese)

Basierend auf Cal-Doku Findings 3.5 + Mount-Tausch-Befund:

| Pin | Joint | Hypothese | Beweisbasis |
|---|---|---|---|
| 0 | leg_1_coxa | +1 (rechts default) | Mount-Konv A für rechte Beine |
| 1 | leg_1_femur | +1 | Konv A |
| 2 | leg_1_tibia | +1 | Konv A |
| 3 | leg_2_coxa | +1 (rechts) | Mount-Tausch macht leg_2 jetzt zu „links" — könnte aber -1 sein. **Unsicher.** |
| 4 | leg_2_femur | +1 oder -1 | Mount-Tausch — **Unsicher.** |
| 5 | leg_2_tibia | +1 oder -1 | Mount-Tausch — **Unsicher.** |
| 6-8 | leg_3 | +1 (rechts) | Mount unverändert |
| 9-11 | leg_4 | -1 (links) | Mount-Spiegel zu rechts |
| 12-14 | leg_5 | -1 oder Mix | Mount-Tausch — **Unsicher.** |
| 15-17 | leg_6 | **-1/-1/+1** ✅ | Phase 10 stack-verified |

→ **Sicher: leg_6.** Unsicher: leg_2 + leg_5 (Mount-Tausch hat Pattern
verändert). Stage C wird das pro Bein klären.

## 6. Erfolgs-Kriterien Stage C DONE

| # | Kriterium |
|---|---|
| 1 | Alle 18 Pins haben verified direction (RViz=HW match) |
| 2 | servo_mapping.yaml in src/ enthält die finale direction-Map |
| 3 | Keine safety_freeze-Trigger während Cal-Tests |
| 4 | leg_6 direction unverändert (Sanity-Check für Phase-10-Konsistenz) |

## 7. Was nach Stage C kommt

**Stage E2 (HW-Walking aufgebockt):** mit der gefixten Direction-Map
das Sim-Preset live auf HW testen. Single-Joint → ein Bein → Tripod-
Walking. Plugin + Stage-0.5/0.6-Safety-Mechanismen sind aktiv —
falls IK out-of-Cal-Range, Plugin freezed.

## 8. Risiken & Failure-Modes

| Symptom | Wahrscheinliche Ursache | Aktion |
|---|---|---|
| safety_freeze triggert beim Joint-Command | direction falsch + rad-Command führt zu pulse out-of-range | `/hexapod_safety_reset`, direction flippen, kleineren Command nehmen |
| Bein dreht aber Servo brummt am Anschlag | direction richtig aber rad-Command zu groß für Cal-Range | Command auf ±0.2 reduzieren |
| RViz und HW gehen in entgegengesetzte Richtungen | direction falsch — flippen | direction-Wert ändern, re-test |
| RViz und HW gehen in selbe Richtung aber unterschiedlich weit | Slope-Mismatch (sollte nach Stage-0-Fix nicht passieren) | Cal-Werte re-vermessen für betroffenen Pin |
| Mehrere Beine reagieren auf einen Joint-Command | YAML-Mapping defekt | servo_mapping.yaml prüfen |

## 9. Verbundene Dokumente

- [`servo_real_calibration_todos.md`](servo_real_calibration_todos.md) — Cal-Daten
- [`servo_real_cal_plan.md`](servo_real_cal_plan.md) — Stage-Übersicht
- [`servo_real_cal_stage_c_test_commands.md`](servo_real_cal_stage_c_test_commands.md) — operative Anleitung
- [`tools/walking_envelope_check.py`](../tools/walking_envelope_check.py) — Tool für Re-Tuning nach Cal-Update

---

**Erstellt 2026-05-24 nach Stage E (Sim) abgeschlossen. Stage C ist
interaktive HW-Session — der eigentliche Cal-Arbeit-Punkt.**
