# Handover — Stage E2 (HW-Walking aufgebockt)

> **Stand 2026-05-24 nach Stage C abgeschlossen.** Diese Doku ist der
> Einstieg für die nächste Session (nach Context-Compact).

## Wo wir sind

Stages 0/0.5/0.6/A/B/D/E(Sim)/**C** alle ✅ abgeschlossen. Nur noch:
- **Stage E2** — HW-Walking aufgebockt (interaktiv mit dir am Roboter)

## Was wir gerade abgeschlossen haben (Stage C)

Direction-Cal HW+RViz parallel — direction-Map für alle 18 Pins
verifiziert + in `src/hexapod_hardware/config/servo_mapping.yaml`
persistiert. Pattern:
- **Coxa (alle 6):** direction = -1
- **Femur rechts (1/2/3):** +1, **Femur links (4/5/6):** -1
- **Tibia rechts (1/2/3):** -1, **Tibia links (4/5/6):** +1

Stage-C-Tests (Re-Test) ALLE ✓ — RViz match HW für alle 18 Pins.

## Was Stage E2 macht

Mit der gefixten Direction-Map das Sim-Preset live auf HW testen
(aufgebockt, keine Boden-Berührung):

1. Single-Joint pro Bein (±0.3 rad) — wie Stage C aber als Roundtrip-Check
2. Ein ganzes Bein (alle 3 Joints koordiniert)
3. Mehrere Beine simultan
4. gait_node mit `defensive_walk` oder `sim_walk.yaml`, langsames cmd_vel
5. Alle 6 Beine in Tripod-Gait aufgebockt
6. Tempo hoch (0.02 → 0.04 → 0.05) bis IKError / Probleme

**Safety-Layer aktiv:** Stage 0.5 freeze auf pulse-OoR, Stage 0.6 IK-
Joint-Check + safety_freeze-Service.

## Wichtige Dateien — Stage E2 wird brauchen

| Datei | Zweck |
|---|---|
| `docs_raspi/servo_real_cal_plan.md` | Stage-Übersicht, Status aller Stages, Stage-E-Plan (E2 Sektion in E.1) |
| `docs_raspi/servo_real_cal_stage_e_sim_plan.md` + `_test_commands.md` | Vorlage für Stage E2 (Sim-Pendant) — Struktur kopieren für HW |
| `docs_raspi/servo_real_cal_stage_c_test_commands.md` | T1/T2/T3-Setup, Plugin-Start, Sicherheits-Hinweise — Vorlage für E2 |
| `src/hexapod_gait/config/presets/sim_walk.yaml` | Walking-Preset (radial=0.295, body_height=-0.070, step_length_max=0.035, step_height=0.020) |
| `src/hexapod_hardware/config/servo_mapping.yaml` | Final Cal + direction-Map (Stage B+C committed) |
| `tools/walking_envelope_check.py` | Auto-Tuning falls HW-Walking andere Werte braucht |

## Erster Schritt nach Compact

1. **Plan + test_commands für Stage E2 schreiben** (analog zu Stage E Sim, aber mit HW):
   - `docs_raspi/servo_real_cal_stage_e2_hw_plan.md`
   - `docs_raspi/servo_real_cal_stage_e2_hw_test_commands.md`
2. Sicherheits-Setup recap: aufgebockt, Kill-Switch, langsam beginnen
3. Plugin in real.launch.py + gait_node mit sim_walk.yaml-preset starten
4. Walking schrittweise hoch testen

## Wichtige Memory + Konventionen

- `feedback_phase_progress_tracking.md` — Plan-Doku pro Bullet sofort updaten
- `feedback_interactive_stage_test_doc.md` — Test-Commands.md vor interaktiver Session schreiben
- `feedback_user_does_commits.md` — User macht Commits selbst, kein Vorschlag mit Co-Authored-By
- `feedback_decision_alternatives_log.md` — Q&A-Pattern mit Optionen + User-Wahl im Plan dokumentieren
- `feedback_no_trim_verification_output.md` — Bash-Outputs nicht trimmen für Verifikation
- Memory-Eintrag erstellen: `project_servo_real_cal_done.md` falls Stage E2 erfolgreich

## Phasen-Kontext

- PHASE.md sagt Phase 12 = Pi-Plattform aktiv
- Servo-Real-Cal ist Cross-Phase-Thread parallel zu Phase 12
- Nach Stage E2 + Memory-Update kann Phase 13 (Voll-Bringup) starten
- Phase-13-Pendenzen (siehe Plan-Doku Sektion „Phase-13-Pendenz"):
  - pose_standing-PWMs definieren (RViz-IK)
  - Auto-Standing-Rampe nach safety_freeze-Reset
  - Step-Truncate über alle Beine bei IK-Joint-Limit-Error
  - /gait_health-Status-Topic
  - Plugin /hexapod_safety_state State-Topic
  - Initial-Pose-Plugin-Erweiterung (pose_hardware_init via Tab. 3.4 Sektion)

---

**Commit-Vorschlag für Stage C / aktuelles arbeit:**

```bash
git add src/hexapod_hardware/config/servo_mapping.yaml \
        src/hexapod_hardware/test/test_hexapod_system.cpp \
        src/hexapod_description/launch/display.launch.py \
        docs_raspi/servo_real_cal_stage_c_test_commands.md \
        docs_raspi/servo_real_cal_plan.md \
        docs_raspi/HANDOVER_STAGE_E2.md
```

```
phase12: stage C direction-cal verifiziert (alle 18 pins)

Direction-map: coxa alle -1; femur rechts +1 / links -1; tibia rechts
-1 / links +1. RViz match HW für alle 18 pins. servo_mapping.yaml
committed. display.launch.py: neuer with_jsp_gui:=false arg gegen race
mit plugin-/joint_states. Test-tolerance auf 6e-3 wegen mid-leg coxa
direction-flip-roundtrip-drift.
```
