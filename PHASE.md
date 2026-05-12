# Aktive Phase

**Aktuell:** Phase 7 — Servo2040 Firmware
**Datei:** `docs_raspi/phase_7_servo2040_fw.md`
**Progress-Tracker:** `docs_raspi/phase_7_progress.md`

> **Wichtig:** Ab Phase 7 liegen alle Phasen-Detail-Docs unter `docs_raspi/`,
> nicht mehr unter `docs/`. Phasen 0–6 bleiben in `docs/`.
>
> **Phase-7-Bündel-Hintergrund:** Aus dem ursprünglichen „Phase 7 — Pi-
> Portierung & Hardware" wurden auf Wunsch sechs feiner geschnittene Phasen
> (7–12), damit die `PHASE.md`-Übersicht sauber zeigt wo wir gerade stehen.
> Der erste Mega-Draft liegt als `docs_raspi/_archive_phase_7_brainstorm.md`
> archiviert — als Referenz für Inhalte, nicht mehr aktiv.

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
| 7 | Servo2040 Firmware | `docs_raspi/phase_7_servo2040_fw.md` | 🟡 aktiv |
| 8 | Strom- & Elektronik-Bench | `docs_raspi/phase_8_electronics_bench.md` | ⚪ offen |
| 8b | Sim+HW Visual-Mirror (optional) | `docs_raspi/phase_8b_sim_hw_mirror.md` | ⚪ optional |
| 9 | ROS2-Plugin `hexapod_hardware` | `docs_raspi/phase_9_hexapod_hardware.md` | ⚪ offen |
| 10 | Single-Leg Bring-up + Kalibrierung | `docs_raspi/phase_10_single_leg.md` | ⚪ offen |
| 11 | Pi-Plattform & Portierung | `docs_raspi/phase_11_pi_platform.md` | ⚪ offen |
| 12 | Voll-Bringup mit echtem Roboter | `docs_raspi/phase_12_full_bringup.md` | ⚪ offen |

### Querschnitts-Docs (`docs_raspi/`, kein eigenes Phasen-Done-Kriterium)

| Name | Datei | Zweck |
|---|---|---|
| Deployment Desktop ↔ Pi | `docs_raspi/dev_workflow_desktop_to_pi.md` | Git + VSCode Remote-SSH-Workflow für Code-Transfer |

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert

---

## Beim Phasenwechsel

1. Done-Kriterium der aktuellen Phase nachweislich erfüllt
2. Timeshift-Snapshot anlegen (Name: `phase_<n>_done`)
3. Git-Commit + Tag `phase-<n>-done`
4. Diese Datei aktualisieren (Status + nächste aktive Phase)
5. Kurze Retro: Was lief gut, was hat länger gedauert, was ist offen

---

## Phase-6-Übergabe (vorheriger Stand, archiviert)

PS4-Controller via USB läuft. D-Pad steuert Bewegung (vor/zurück, drehen am
Stand), L2/R2 ändern Body-Höhe (nur im STANDING-State), R1 ist Dead-Man-
Switch. Engine-Erweiterung `gait_node` mit `/cmd_body_height` Topic.
Tastatur-Stufe verworfen, Bluetooth-Pairing deferred.

**Übergabe-Items für Phase 7 ff.:**

- **`controllers.yaml use_sim_time: true`** muss in Phase 9 auf `false`
  (Wallclock am Pi) für `controllers.real.yaml`.
- **`body_height = -0.052`** ist Sim-spezifischer JTC-Tracking-Lag-Workaround.
  HW-Default zurück auf `-0.047` — echte Servos haben keinen Lag.
- **KDL-Warning** weiter offen — am Pi auch unkritisch (User-Entscheidung).
- **`hexapod_hardware`-Paket** (C++ HardwareInterface, pluginlib) wird in
  Phase 9 angelegt — ersetzt `gz_ros2_control` für echte Servo2040-Hardware.
- **Sicherheit:** Hexapod aufbocken für Joint-Tests, Hardware-Kill-Switch
  griffbereit, reduzierte Geschwindigkeit (siehe CLAUDE.md §9).
