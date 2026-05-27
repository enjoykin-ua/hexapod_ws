# Aktive Phase

**Aktuell:** Phase 12 — Pi-Plattform & Portierung
**Datei:** `docs_raspi/phase_12_pi_platform.md`

> Cross-Phase-Thread `servo_real_cal` (Stages 0/0.5/0.6/A/B/D/E/C/E2) ✅
> 2026-05-25 — Cal aller 18 Pins + Safety-Layer + HW-Walking aufgebockt
> verifiziert. Phase 12 selbst (Pi-Plattform) ist noch nicht angefangen.
>
> **Retros, Übergaben, ausführliche Begründungen:** [`PHASE_NOTES.md`](PHASE_NOTES.md).

---

## Phasen-Übersicht

### Sim-Phasen (Desktop, abgeschlossen)

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟢 abgeschlossen |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | 🟢 abgeschlossen (Udemy-Kurs absolviert, Phase übersprungen) |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | 🟢 abgeschlossen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | 🟢 abgeschlossen (alle 6 Kriterien; DK4 in Phase 4 Stufe F nachgeholt) |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | 🟢 abgeschlossen |
| 5 | Inverse Kinematik & Gait | `docs/phase_5_kinematics_gait.md` | 🟢 abgeschlossen (alle 5 DK + Stufe-H-Omnidirektional) |
| 6 | Teleop (PS4-Controller) | `docs/phase_6_teleop.md` | 🟢 abgeschlossen (PS4 via USB; Tastatur verworfen, Bluetooth deferred) |

### Hardware-Phasen (Bench + Pi, `docs_raspi/`)

| # | Name | Datei | Status |
|---|---|---|---|
| 7 | Servo2040 Firmware | `docs_raspi/phase_7_servo2040_fw.md` | 🟢 abgeschlossen (2026-05-14) |
| 8 | Strom- & Elektronik-Bench | `docs_raspi/phase_8_electronics_bench.md` | ⏸️ pausiert (Deadline: vor Phase 12) |
| 8b | Sim+HW Visual-Mirror (optional) | `docs_raspi/phase_8b_sim_hw_mirror.md` | ⚪ optional |
| 9 | ROS2-Plugin `hexapod_hardware` | `docs_raspi/phase_9_hexapod_hardware.md` | 🟢 abgeschlossen (2026-05-16) |
| 10 | Single-Leg Bring-up + Kalibrierung | `docs_raspi/phase_10_single_leg.md` | 🟢 abgeschlossen (2026-05-19) |
| 11 | Param-GUI mit Live-Tuning (rqt_reconfigure) | `docs_raspi/phase_11_param_gui.md` | 🟢 abgeschlossen (2026-05-21) |
| **12** | **Pi-Plattform & Portierung** | `docs_raspi/phase_12_pi_platform.md` | 🟡 aktiv (noch nicht angefasst) |
| 13 | Voll-Bringup mit echtem Roboter | `docs_raspi/phase_13_full_bringup.md` | ⚪ offen (Sub-Stages B/C/D vorweggenommen durch servo_real_cal-Thread) |

### Cross-Phase-Threads (parallel zu Hauptphasen)

| Thread | Index-Datei | Status |
|---|---|---|
| Servo Real Calibration & Walking aufgebockt am Desktop | `docs_raspi/servo_real_cal_plan.md` | 🟢 abgeschlossen 2026-05-25 (Stages 0/0.5/0.6/A/B/D/E-Sim/C/E2/**F** — alle 18 Pins kalibriert, direction-Map, Safety-Layer Stage 0.5+0.6, HW-Walking aufgebockt mit cmd_vel 0.02/0.03/0.035 m/s ohne IKError, **Stage F: URDF rad-Limits strict-symmetrisch ±0.415/±1.493/±1.161 — Asymmetrie aus E2.3 behoben**) |

### Querschnitts-Docs (`docs_raspi/`, kein eigenes Phasen-Done-Kriterium)

| Name | Datei | Zweck |
|---|---|---|
| Deployment Desktop ↔ Pi | `docs_raspi/dev_workflow_desktop_to_pi.md` | Git + VSCode Remote-SSH-Workflow für Code-Transfer |
| Architektur-Brainstorm | `docs_raspi/architecture_overview_brainstorm.md` | Tool-Vergleich + Komponenten-Katalog (Brainstorm) |
| Hardware-Change-Workflow | `docs/01_hardware_change_workflow.md` | 12 Szenarien (Bein-Geometrie, Servos, USB, Sim↔HW-Switch) |

Status-Legende: ⚪ offen/optional — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert — ⏸️ pausiert (verschoben, kein Blocker)

---

## Beim Phasenwechsel

1. Done-Kriterium der aktuellen Phase nachweislich erfüllt
2. Timeshift-Snapshot anlegen (Name: `phase_<n>_done`)
3. Git-Commit + Tag `phase-<n>-done`
4. `PHASE.md` aktualisieren (Status-Spalte + nächste aktive Phase oben)
5. Kurze Retro nach `PHASE_NOTES.md` schreiben: Was lief gut, was hat länger gedauert, was ist offen
