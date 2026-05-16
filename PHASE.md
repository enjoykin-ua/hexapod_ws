# Aktive Phase

**Aktuell:** Phase 10 — Single-Leg Bring-up + Kalibrierung
**Datei:** `docs_raspi/phase_10_single_leg.md`
**Progress-Tracker:** `docs_raspi/phase_10_progress.md` (legen wir zu Phase-10-Start an)

> **Phase 9 (ROS2-Plugin `hexapod_hardware`):** ✅ abgeschlossen am 2026-05-16.
> Alle 10 Stufen A–J durchgelaufen. CI-Anteil voll grün (208 Plugin-Tests +
> 18 launch_testing-Tests), Hardware-Pfad bis Plugin↔Firmware-Pipeline mit
> echtem Servo2040 ohne Hexapod-Servos verifiziert. **Ausstehende Items:**
> Oszi/Logic-Analyzer-Verifikation (Stage H H-T8/H-T9) — dokumentiert in
> Memory-Eintrag `project_phase9_h_oscilloscope_pending.md` als Cross-Session-
> Reminder; bei Hardware-Verfügbarkeit (z.B. Phase 10 Bench-Setup) nachholen.
>
> **Phase-9-Retro (kurz):**
> - **Was gut lief:** der Plan-First-Workflow mit jeweils 4–5 offenen Fragen
>   pro Stufe hat substantielle Design-Diskussionen produziert (z.B. F-Q1
>   velocity-State-Mismatch, G-Q1 loopback-Default, H-Q1 Bench-Netzteil-
>   Setup) die im Code-Edit allein nicht aufgekommen wären. Memory-Konvention
>   `feedback_urdf_refactor_full_smoke.md` aus Stage F hat in Stage G + H
>   direkt gegriffen.
> - **Was länger gedauert hat als geplant:** Hardware-Stages (H, I) hatten
>   mehr Real-World-Lessons als antizipiert (USB-CDC-Boot-Garbage,
>   ros2_control Auto-Deactivate-Bei-Write-Fail, Linter-Pattern-Lerncurve
>   für launch_testing). Plan-Korrektur-Sektionen pro Stage haben das
>   transparent gemacht. Bei F-Q5 wurde F-T9 nach Stage G verschoben weil
>   die „einzelner CLI-Aufruf reicht"-Annahme an rcl-Parser-Limitierung
>   gescheitert ist.
> - **Was offen ist:** (1) Oszi/Logic-Analyzer-Tests (siehe oben), (2)
>   optional `phase-7-done`-Tag retroaktiv im fw-Repo (Doku-Hygiene aus
>   Stage H H-T3), (3) Plugin-API-Migration `export_*_interfaces()` →
>   `on_export_*_interfaces()` ist out-of-scope geblieben (alte API gewinnt
>   wenn Override non-empty) — Pragma-Suppression in test_plugin_registration.cpp.
>
> **Git-Aktionen zum Phasenwechsel** (`phase-9-done`-Tag im hexapod_ws,
> Commit der phase_9-Docs) macht der User beim Phasenwechsel.

> **Phase 7 (Servo2040 Firmware):** ✅ abgeschlossen am 2026-05-14.
> Alle Stufen A–G grün am Board verifiziert, Doku in `docs_raspi/phase_7_progress.md`
> (inkl. Pimoroni-API-Erkenntnis-Tabelle + Retrospektive). Stufe H Git-Aktionen
> (`phase-7-done`-Tag in fw-Repo und hexapod_ws, Commit der phase_7-Docs)
> macht der User beim Phasenwechsel.
>
> **Phase 8 (Bench-Elektronik) ⏸️ pausiert (2026-05-14):**
> Inhalt (DCDC-Wandler für Pi, GND-Stern, Bulk-Caps) wird erst gebraucht wenn
> der Pi ins Spiel kommt. Phase 9 + 10 laufen weiterhin am Desktop mit der
> bestehenden Bench-PSU-Verkabelung aus Phase 7. **Harte Deadline: vor Beginn
> Phase 11 (Pi-Plattform) muss Phase 8 durch sein.**
>
> **Phase 8b (Sim+HW-Mirror) ⚪ bleibt optional:** Architektur-Abgrenzung
> macht den Mirror unabhängig — kann jederzeit ergänzend gebaut werden,
> ist aber kein Done-Kriterium für 9/10/11/12.

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
| 7 | Servo2040 Firmware | `docs_raspi/phase_7_servo2040_fw.md` | 🟢 abgeschlossen (2026-05-14) |
| 8 | Strom- & Elektronik-Bench | `docs_raspi/phase_8_electronics_bench.md` | ⏸️ pausiert (deadline: vor Phase 11) |
| 8b | Sim+HW Visual-Mirror (optional) | `docs_raspi/phase_8b_sim_hw_mirror.md` | ⚪ optional |
| 9 | ROS2-Plugin `hexapod_hardware` | `docs_raspi/phase_9_hexapod_hardware.md` | 🟢 abgeschlossen (2026-05-16; Oszi-Verifikation H-T8/H-T9 pending bei Hardware-Verfügbarkeit) |
| 10 | Single-Leg Bring-up + Kalibrierung | `docs_raspi/phase_10_single_leg.md` | 🟡 aktiv |
| 11 | Pi-Plattform & Portierung | `docs_raspi/phase_11_pi_platform.md` | ⚪ offen |
| 12 | Voll-Bringup mit echtem Roboter | `docs_raspi/phase_12_full_bringup.md` | ⚪ offen |

### Querschnitts-Docs (`docs_raspi/`, kein eigenes Phasen-Done-Kriterium)

| Name | Datei | Zweck |
|---|---|---|
| Deployment Desktop ↔ Pi | `docs_raspi/dev_workflow_desktop_to_pi.md` | Git + VSCode Remote-SSH-Workflow für Code-Transfer |

Status-Legende: ⚪ offen/optional — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert — ⏸️ pausiert (verschoben, kein Blocker)

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
