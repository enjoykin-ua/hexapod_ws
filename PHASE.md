# Aktive Phase

**Aktuell:** Phase 4 — `ros2_control`-Integration
**Datei:** `docs/phase_4_ros2_control.md`

> **Phase-3-Übergabe:** 5 von 6 Done-Kriterien erfüllt. Done-Kriterium 4
> (manueller Stand-Test) wurde bewusst auf Phase 4 deferiert, weil Phase 3
> ohne `gz_ros2_control` keinen Joint-Controller hat. Erste Aufgabe in
> Phase 4: Reibungswerte (`mu1=mu2=1.0`, `kp=1e6`, `kd=100`) unter realer
> Stand-Pose verifizieren. Begründung in `docs/phase_3_progress.md` Stufe E.1.

---

## Phasen-Übersicht

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟢 abgeschlossen |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | 🟢 abgeschlossen (Udemy-Kurs absolviert, Phase übersprungen) |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | 🟢 abgeschlossen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | 🟢 abgeschlossen (5/6 Kriterien; Stand-Test deferiert auf Phase 4) |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | 🟡 aktiv |
| 5 | Inverse Kinematik & Gait | `docs/phase_5_kinematics_gait.md` | ⚪ offen |
| 6 | Teleop (Tastatur, PS-Controller) | `docs/phase_6_teleop.md` | ⚪ offen |
| 7 | Pi-Portierung & Hardware | `docs/phase_7_pi_port.md` | ⚪ offen |

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert

---

## Beim Phasenwechsel

1. Done-Kriterium der aktuellen Phase nachweislich erfüllt
2. Timeshift-Snapshot anlegen (Name: `phase_<n>_done`)
3. Git-Commit + Tag `phase-<n>-done`
4. Diese Datei aktualisieren (Status + nächste aktive Phase)
5. Kurze Retro: Was lief gut, was hat länger gedauert, was ist offen
