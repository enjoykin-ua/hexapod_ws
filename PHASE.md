# Aktive Phase

**Aktuell:** Phase 7 — Pi-Portierung & Hardware
**Datei:** `docs/phase_7_pi_port.md` (Phasenplan, noch zu schreiben)
**Handoff:** `docs/phase_7_hw_port_handoff.md` — kompakter Einstiegspunkt

> **Phase-6-Übergabe:** PS4-Controller via USB läuft. D-Pad steuert
> Bewegung (vor/zurück, drehen am Stand), L2/R2 ändern Body-Höhe (nur
> im STANDING-State), R1 ist Dead-Man-Switch. Engine-Erweiterung
> `gait_node` mit `/cmd_body_height` Topic. Tastatur-Stufe verworfen
> (direkter Sprung zu PS4 sparte 1+ Tag), Bluetooth-Pairing deferred
> (optional, bei Bedarf).
>
> **Übergabe-Items für Phase 7:**
> - **Lies primär `docs/phase_7_hw_port_handoff.md`** — kompakte
>   Codebase-Tour (Topics, Pakete, Sim-Spezifika die Phase 7 ändern
>   muss, Servo2040-Anbindung).
> - **`controllers.yaml use_sim_time: true`** muss in Phase 7 auf
>   `false` (Wallclock am Pi) — Kommentar im YAML weist drauf hin
>   seit Phase 4.
> - **`body_height = -0.052`** ist Sim-spezifischer JTC-Tracking-Lag-
>   Workaround. Phase-7-Default zurück auf `-0.047` — echte Servos
>   haben keinen Lag.
> - **KDL-Warning** weiter offen — am Pi auch unkritisch (User-
>   Entscheidung).
> - **`hexapod_hardware`-Paket** (C++ HardwareInterface, pluginlib)
>   muss neu angelegt werden — ersetzt `gz_ros2_control` für echte
>   Servo2040-Hardware.
> - **Sicherheit:** Hexapod aufbocken (Beine in der Luft) für ersten
>   Joint-Test, Hardware-Kill-Switch griffbereit, reduzierte
>   Geschwindigkeit (siehe CLAUDE.md §9).

---

## Phasen-Übersicht

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟢 abgeschlossen |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | 🟢 abgeschlossen (Udemy-Kurs absolviert, Phase übersprungen) |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | 🟢 abgeschlossen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | 🟢 abgeschlossen (alle 6 Kriterien; DK4 in Phase 4 Stufe F nachgeholt) |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | 🟢 abgeschlossen |
| 5 | Inverse Kinematik & Gait | `docs/phase_5_kinematics_gait.md` | 🟢 abgeschlossen (alle 5 DK + Stufe-H-Omnidirektional) |
| 6 | Teleop (PS4-Controller) | `docs/phase_6_teleop.md` | 🟢 abgeschlossen (PS4 via USB; Tastatur verworfen, Bluetooth deferred) |
| 7 | Pi-Portierung & Hardware | `docs/phase_7_pi_port.md` | 🟡 aktiv |

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert

---

## Beim Phasenwechsel

1. Done-Kriterium der aktuellen Phase nachweislich erfüllt
2. Timeshift-Snapshot anlegen (Name: `phase_<n>_done`)
3. Git-Commit + Tag `phase-<n>-done`
4. Diese Datei aktualisieren (Status + nächste aktive Phase)
5. Kurze Retro: Was lief gut, was hat länger gedauert, was ist offen
