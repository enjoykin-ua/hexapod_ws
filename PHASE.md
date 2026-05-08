# Aktive Phase

**Aktuell:** Phase 5 — Inverse Kinematik & Gait
**Datei:** `docs/phase_5_kinematics_gait.md`

> **Phase-4-Übergabe:** Alle 6 Done-Kriterien erfüllt. `ros2_control`
> vollständig integriert (1× JSB + 6× JTC active), Bewegungstest auf
> mehreren Beinen grün, RViz live-synchron mit Gazebo. Phase-3-Defer
> (Stand-Test, DK4) in Stufe F nachgeholt — Default-Reibungswerte
> tragen ohne Tuning, Drift = 0 mm / 0° über 5 s.
>
> **Übergabe-Items für Phase 5:**
> - **KDL-Warning** (`base_link has inertia, but KDL does not support
>   root link with inertia`) bewusst nicht in Phase 4 gefixt — auf Phase 5
>   geschoben. Optionaler Fix mit Dummy-Root-Link, sobald die Warning beim
>   IK/Gait-Debugging stört. Memory-Eintrag siehe
>   `~/.claude/.../memory/project_phase5_kdl_warning_fix.md`.
> - Stand-Pose `[0, -0.5, 1.0]` ist verifiziert stabil. IK-Smoke-Test
>   in Phase 5 sollte als ersten Plausibilitätscheck genau diese Pose
>   per IK reproduzieren (Wunschhöhe ≈ 0.055 m → erwartete Joint-Werte).

---

## Phasen-Übersicht

| # | Name | Datei | Status |
|---|---|---|---|
| 0 | Desktop-Setup | `docs/phase_0_setup.md` | 🟢 abgeschlossen |
| 1 | ROS2-Grundlagen | `docs/phase_1_ros2_basics.md` | 🟢 abgeschlossen (Udemy-Kurs absolviert, Phase übersprungen) |
| 2 | Roboter-Beschreibung (URDF) | `docs/phase_2_description.md` | 🟢 abgeschlossen |
| 3 | Gazebo-Simulation | `docs/phase_3_gazebo.md` | 🟢 abgeschlossen (alle 6 Kriterien; DK4 in Phase 4 Stufe F nachgeholt) |
| 4 | `ros2_control` Integration | `docs/phase_4_ros2_control.md` | 🟢 abgeschlossen |
| 5 | Inverse Kinematik & Gait | `docs/phase_5_kinematics_gait.md` | 🟡 aktiv |
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
