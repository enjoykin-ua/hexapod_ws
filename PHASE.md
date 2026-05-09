# Aktive Phase

**Aktuell:** Phase 6 — Teleop (Tastatur, PS-Controller)
**Datei:** `docs/phase_6_teleop.md` (Phasenplan, noch zu schreiben)
**Handoff:** `docs/phase_6_teleop_handoff.md` — kompakter Einstiegspunkt

> **Phase-5-Übergabe:** Alle 5 Done-Kriterien erfüllt + Stufe-H-Bonus
> (omnidirektional via `linear.y` + `angular.z`). Hexapod läuft in
> Gazebo eigenständig vorwärts/rückwärts/seitwärts/drehend/Bogen,
> gesteuert via `/cmd_vel` (Twist). State-Machine STANDING/WALKING/
> STOPPING mit sauberem Settling, proportionales Clamping, Demo-Mode
> via `default_*`-Params.
>
> **Übergabe-Items für Phase 6:**
> - **Lies primär `docs/phase_6_teleop_handoff.md`** — kompaktes
>   Phase-5-Output-Interface (cmd_vel-Format, Standard-Bringup,
>   PS-Controller-Mapping-Empfehlung, Stolperfallen). Phase-5-
>   Vollmaterial nur bei Bedarf.
> - **cmd_vel-Pub-Rate ≥ 2 Hz** sonst Activity-Timeout 0.5 s →
>   Engine fällt auf `default_*` (typisch 0 → STANDING) zurück.
> - **Limits:** `linear.x/y` ±0.05 m/s, `angular.z` ±0.46 rad/s.
>   Engine clampt proportional bei Übersteuerung.
> - **KDL-Warning** weiter nicht gefixt — User-Entscheidung, stört
>   am Pi auch nicht. Memory-Eintrag bleibt als Reminder.
> - **Yaw-Drift ~1.35°/m** bei langen Geradeaus-Strecken bekannte
>   Sim-Limitation. Phase 6 kompensiert durch User-Korrektur am
>   Joystick.

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
| 6 | Teleop (Tastatur, PS-Controller) | `docs/phase_6_teleop.md` | 🟡 aktiv |
| 7 | Pi-Portierung & Hardware | `docs/phase_7_pi_port.md` | ⚪ offen |

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 abgeschlossen — 🔴 blockiert

---

## Beim Phasenwechsel

1. Done-Kriterium der aktuellen Phase nachweislich erfüllt
2. Timeshift-Snapshot anlegen (Name: `phase_<n>_done`)
3. Git-Commit + Tag `phase-<n>-done`
4. Diese Datei aktualisieren (Status + nächste aktive Phase)
5. Kurze Retro: Was lief gut, was hat länger gedauert, was ist offen
