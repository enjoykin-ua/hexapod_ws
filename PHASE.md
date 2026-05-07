# Aktive Phase

**Aktuell:** Phase 0 — Desktop-Setup
**Datei:** `docs/phase_0_setup.md`

---

## Phasen-Übersicht

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟡 aktiv |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | ⚪ offen |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | ⚪ offen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | ⚪ offen |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | ⚪ offen |
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
