# Aktive Phase

**Aktuell:** **Hardware-Bring-up** — **Phase 12 (Pi-Plattform) ✅ Kern fertig**:
ROS2-Stack baut + läuft headless am Pi (`hexapod-pi`, Loopback, alle Controller
active), Provisioning-Skript + Recovery-Pfad stehen, Servo2040 am Pi erkannt
(`/dev/servo2040`). Als Nächstes: **erster echter HW-Start am Pi**
(`loopback_mode:=false`, Phase 13 — **aufgebockt**, §9) bzw. **Elektronik** (Phase 8 / D2).
_(Phase-12-Detail: [`docs_raspi/phase_12_progress.md`](docs_raspi/phase_12_progress.md);
deferiert: D DDS/RViz, G.2 rsync.)_
**Davor abgeschlossen (Sim/Bench, 2026-06):** Lokomotion-Kern, Teleop, Lauf-Konfiguration
(Stance-Modi) und Show-Pose — Details in [`project_finalization/`](project_finalization/00_backlog.md)
(Blöcke B/C + Stance-Modi + B4).

> **📚 Projekt-Referenz (Architektur, AI-Navigation, Tools):** [`project_architecture/`](project_architecture/00_overview.md)
> **🗂️ Finalisierungs-Backlog (offene Stages A–E):** [`project_finalization/00_backlog.md`](project_finalization/00_backlog.md)
> **🕘 Retros, Übergaben, ausführliche Begründungen:** [`PHASE_NOTES.md`](PHASE_NOTES.md)

> **Wo stehen wir — kurz:** Nach den Bench-Phasen (7–11) lief die Arbeit nicht streng linear in
> „Phase 12/13", sondern aufgrund von Implementierungs-Findings im **Finalisierungs-Block-System**
> (`project_finalization/`, Blöcke A–E). Dort wurden der **Lokomotion-Kern** (Hinsetzen, Gangarten,
> Show-Pose), der **Teleop** (USB+BT, Live-Verstellung) und die **Lauf-Konfiguration** (Stance-Modi
> statt stufenloser Höhe) fertig — alles in Sim, teils aufgebockt. Der Cross-Phase-Thread
> `servo_real_cal` hat parallel Cal + Safety + HW-Walking-aufgebockt erledigt. **Was bleibt: die
> echte Hardware-Plattform** — Pi-Portierung (Phase 12) und Elektronik (Phase 8) — und dann der
> **Voll-Bringup** (Phase 13) auf dem fahrbereiten Roboter.

---

## Phasen-Übersicht

### Sim-Phasen (Desktop, abgeschlossen)

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟢 abgeschlossen |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | 🟢 abgeschlossen (Udemy-Kurs; Phase übersprungen) |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | 🟢 abgeschlossen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | 🟢 abgeschlossen |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | 🟢 abgeschlossen |
| 5 | Inverse Kinematik & Gait | `docs/phase_5_kinematics_gait.md` | 🟢 abgeschlossen |
| 6 | Teleop (PS4 USB) | `docs/phase_6_teleop.md` | 🟢 abgeschlossen (BT/Stance/Show kamen in den Finalisierungs-Blöcken dazu) |

### Hardware-Phasen (Bench, `docs_raspi/`)

| # | Name | Datei | Status |
|---|---|---|---|
| 7 | Servo2040 Firmware | `docs_raspi/phase_7_servo2040_fw.md` | 🟢 abgeschlossen (2026-05-14) |
| 8 | Strom- & Elektronik-Bench | `docs_raspi/phase_8_electronics_bench.md` | ⏸️ **offen — kommt mit dem HW-Bring-up** (Block D2) |
| 8b | Sim+HW Visual-Mirror (optional) | `docs_raspi/phase_8b_sim_hw_mirror.md` | ⚪ optional |
| 9 | ROS2-Plugin `hexapod_hardware` | `docs_raspi/phase_9_hexapod_hardware.md` | 🟢 abgeschlossen (2026-05-16) |
| 10 | Single-Leg Bring-up + Kalibrierung | `docs_raspi/phase_10_single_leg.md` | 🟢 abgeschlossen (2026-05-19) |
| 11 | Param-GUI (rqt_reconfigure) | `docs_raspi/phase_11_param_gui.md` | 🟢 abgeschlossen (2026-05-21) |

> **Phase 12/13 — Umstrukturierung:** Phase 13 („Desktop-Pre-Bringup → Voll-Bringup") wurde **nicht
> als eine lineare Phase** abgearbeitet. **Stage 0** (Boot → Aufstehen → stabil am Boden, inkl.
> Femur-Umbau + Relay) ist erledigt; die geplante Stage 1 (Lauf-Optimierung) und alles Weitere
> (Hinsetzen, Gangarten, Show, Teleop, Stance-Modi) liefen im **Finalisierungs-Block-System** unten.
> **Phase 12 (Pi-Plattform) ✅ Kern abgeschlossen** (Stack baut + läuft am Pi, Loopback;
> Servo2040 erkannt). **Phase 13** ist das **End-Ziel** (Voll-Bringup auf dem Pi-getriebenen
> Roboter) — der erste echte HW-Start am Pi (`loopback_mode:=false`, aufgebockt) leitet sie ein.

### Finalisierungs-Blöcke (Desktop, `project_finalization/`)

> Die Hauptarbeit nach den Bench-Phasen. Detail-Backlog: [`project_finalization/00_backlog.md`](project_finalization/00_backlog.md).

| Block | Inhalt | Status |
|---|---|---|
| **A** Analyse & Optimierung | Torque-/Hitze-Tool (A1 ✅); A2–A4 pausiert; **A5 IMU-Balance: Stufe 0/1/2/3a + Terrain-Following TF-1/TF-2 🟢 Sim** (IMU, Kipp-Erkennung, Leveling, Hang-folgen + Gyro-Dämpfung; Branch `imu_balance`) — **⏸️ pausiert nach TF-2**, Rückkehr nach Stufe 4 + HW (Wiedereinstieg: [`stage_3_terrain_following_plan.md` §7](project_finalization/imu_balance/stage_3_terrain_following_plan.md)) | 🟢 A1 / ⏸️ A5 (Sim done) / ⏸️ Rest |
| **B** Lokomotion-Kern | Hinsetzen/Shutdown (B1), Gangarten Wave/Tetra/Ripple (B3), **Show-Pose + Tibia-Reach** (B4/B4.11); B2 verworfen, B5 deferiert | 🟢 Sim (HW aufgebockt offen) |
| **S1** Stance-Modi (3 Lauf-Höhen) | hoch/mittel/tief, L2/R2-Cycle, gekoppelte Reposition+Höhen-Lerp — ersetzt stufenlose Höhe (Envelope-sicher) | 🟢 Sim (HW offen) |
| **C** Teleop / Steuerungs-UX | PS4 USB (C1/C2) + Live-Verstellung Gangart/Schrittweite (C3) + Bluetooth (C4) | 🟢 abgeschlossen |
| **D** Hardware-Bring-up / Plattform | **D1 Pi-Plattform (=Phase 12)** · **D2 Elektrik 2S LiPo (=Phase 8)** · D3 LVC/Telemetrie · D4 Power-On-Sequenz · D5 untethered | 🟡 **als Nächstes** |
| **E** Robustheit / später | Safe-State im Lauf (E1), Terrain/Foot-Contact (E2), Preset-Management (E3) | ⚪ später |

### Cross-Phase-Threads

| Thread | Index-Datei | Status |
|---|---|---|
| Servo Real Calibration & Walking aufgebockt | `docs_raspi/servo_real_cal_plan.md` | 🟢 abgeschlossen 2026-05-25 (alle 18 Pins kalibriert, direction-Map, Safety-Layer, HW-Walking aufgebockt, URDF-Limits strict-symmetrisch) |

### Querschnitts-Docs (kein eigenes Done-Kriterium)

| Name | Datei | Zweck |
|---|---|---|
| Deployment Desktop ↔ Pi | `docs_raspi/dev_workflow_desktop_to_pi.md` | Git + VSCode Remote-SSH-Workflow für Code-Transfer |
| Hardware-Change-Workflow | `docs/01_hardware_change_workflow.md` | 13 Szenarien (Bein-Geometrie/Limits/Knie-Winkel, Servos, USB, Sim↔HW) + Pflicht-Sektion „Lokomotion neu validieren" |

Status-Legende: ⚪ offen/optional — 🟡 aktiv/als Nächstes — 🟢 abgeschlossen — 🔴 blockiert — ⏸️ pausiert

---

## Weg nach vorne (Reihenfolge)

1. **HW aufgebockt:** die neuen Sim-Features (Stance-Modi, Show-Pose, B4.11) einmal aufgebockt → Boden
   verifizieren (CLAUDE.md §9: Kill-Switch, langsam), bevor sie am Boden laufen.
2. ✅ **Phase 12 — Pi-Plattform (Block D1):** ROS2 Jazzy arm64, Workspace **ohne** Gazebo gebaut,
   Loopback grün, Servo2040 am Pi erkannt (`/dev/servo2040`). Provisioning + Recovery dokumentiert.
   Offen: erster echter HW-Start (`loopback_mode:=false`, → Phase 13, aufgebockt).
3. **Phase 8 — Elektronik (Block D2):** 2S-LiPo-Versorgung, Servo-Rail vs. Pi-Rail/BEC, Absicherung,
   Kill-Switch, Strom-/Spannungs-Monitoring. (User macht die Elektrik.)
4. **D3/D4/D5:** LVC + Batterie-Telemetrie · sichere Power-On-Sequenz (Servos zentrieren beim
   Einschalten → aufgebockt booten oder Relay-Gate) · Verkabelung untethered + Cal-Drift-Re-Check.
5. **Block E — Robustheit:** Safe-State bei Overcurrent/Watchdog/Comms-Loss im Lauf.
6. **Phase 13 — Voll-Bringup (Ziel):** der komplette Stack auf dem fahrbaren, untethered Roboter.
7. **Optional/mittelfristig:** A5 IMU-Balance — Stufe 0/1/2/3a + Terrain-Following TF-1/TF-2
   🟢 Sim (IMU, Kipp-Erkennung, Leveling, Hang-folgen + Gyro-Dämpfung). **⏸️ Pausiert nach TF-2**
   (sichtbarer Mehrwert erst auf HW; Knick/unebener Weg = Stufe 4). **Rückkehr** nach Stufe 4 +
   HW-Tests — Wiedereinstiegs-Punkte (P0 HW-Validierung · TF-3 Schwerpunkt/Schlupf · TF-Quer ·
   Gang-Stabilisierung · Auto-Tuning) grob vorgeplant in
   [`stage_3_terrain_following_plan.md` §7](project_finalization/imu_balance/stage_3_terrain_following_plan.md).

---

## Beim Phasenwechsel / Block-Abschluss

1. Done-Kriterium nachweislich erfüllt (Tests grün, Sim/HW verifiziert)
2. Timeshift-Snapshot anlegen (Name: `<phase/block>_done`)
3. Git-Commit + Tag
4. Diese Datei aktualisieren (Status + nächster aktiver Block/Phase oben)
5. Kurze Retro nach `PHASE_NOTES.md`: Was lief gut, was hat länger gedauert, was ist offen
