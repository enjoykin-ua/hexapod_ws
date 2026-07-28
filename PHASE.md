# Aktive Phase

**Aktuell:** **Block I — Mobile-Teleop-App** (Handy + Razer Kishi steuert den Roboter).
**Der Roboter selbst ist FERTIG:** HW + Elektrik (2S LiPo) komplett verdrahtet + in Betrieb, läuft
**untethered im Gelände** auf der echten Hardware — Gangarten, Stance-Modi, Hang-Lauf auf/ab,
Stufen hoch/runter, Hinsetzen/Aufstehen, IMU-Balance, alles was der PS4-Controller bedient hat.
Kamera (Raspi-Cam) + Audio (MAX98357A) sind **verkabelt + hello-world-in-Betrieb**; offen ist deren
ROS-/App-Integration. **Aktuelle Arbeit = App + Feature-Erweiterungen:** Block-I-App
Phasen 1–6 + 7A + 7B fertig (Kishi-Mapping, Teleop, Lifecycle, Video, Status/Config-Panel,
E-Stop+Recovery, **Audio**, **echte Raspi-Cam** — je Sim-/Desktop-verifiziert) und **Phase 8 —
Show „Look-Around"** 🟢 (Körper bewegt sich in 6 DOF über fixen Füßen, App-Show-Menü mit
Platzhaltern für Dancing/Free-Leg; Contract v0.13) — **in Sim UND am echten Roboter verifiziert**.
**Aktiv: Phase 9 — Feld-Autonomie** (Repo-Seite 🟢): Always-On-Schicht ab Boot als systemd-Dienst
(**kein Dev-Rechner/SSH mehr nötig**), reparierter Poweroff (`pi_hostname` war leer → der Pi fuhr
nie herunter), App-Buttons „Pi herunterfahren"/„Stack neu starten", HW-Preset im App-Bringup +
Comms-Loss-Fail-safe; offen sind die Pi-Schritte + die App-Seite. Danach: Politur (Reconnect,
Controller-Profile).
Detail: [`project_finalization/app_control_requirements/`](project_finalization/app_control_requirements/00_overview.md)
· auch: Rubicon-Scene für den App-Flow, Video-Pipeline, Config-Manifest.
_(Historie Pi-Plattform Phase 12: [`docs_raspi/phase_12_progress.md`](docs_raspi/phase_12_progress.md).)_

> **📚 Projekt-Referenz (Architektur, AI-Navigation, Tools):** [`project_architecture/`](project_architecture/00_overview.md)
> **🗂️ Finalisierungs-Backlog (offene Stages A–E):** [`project_finalization/00_backlog.md`](project_finalization/00_backlog.md)
> **🕘 Retros, Übergaben, ausführliche Begründungen:** [`PHASE_NOTES.md`](PHASE_NOTES.md)

> **Wo stehen wir — kurz:** Der **Roboter ist fahrbereit und läuft untethered** (HW + Elektrik +
> Pi + Lokomotion + IMU-Balance komplett, im Gelände getestet — Gangarten, Stance, Hang auf/ab,
> Sit/Stand, alles was der PS4-Controller kann). Die frühere „Weg-nach-vorne"-Liste (Pi-Plattform,
> Elektronik Phase 8, Voll-Bringup Phase 13) ist damit **abgeschlossen**. Die aktuelle Arbeit läuft
> im **Block I (Mobile-Teleop-App)**: das Handy ersetzt den PS4-Controller und bringt Bildschirm,
> Video, Status-Overlay, Config-Panel und Lifecycle dazu — Phasen 1–6 fertig, 7–8 offen (s. u.).

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
| 8 | Strom- & Elektronik-Bench | `docs_raspi/phase_8_electronics_bench.md` | 🟢 abgeschlossen (2S-LiPo-Versorgung + Rails + Absicherung/Kill-Switch verbaut; Roboter läuft mit Akku) |
| 8b | Sim+HW Visual-Mirror (optional) | `docs_raspi/phase_8b_sim_hw_mirror.md` | ⚪ optional |
| 9 | ROS2-Plugin `hexapod_hardware` | `docs_raspi/phase_9_hexapod_hardware.md` | 🟢 abgeschlossen (2026-05-16) |
| 10 | Single-Leg Bring-up + Kalibrierung | `docs_raspi/phase_10_single_leg.md` | 🟢 abgeschlossen (2026-05-19) |
| 11 | Param-GUI (rqt_reconfigure) | `docs_raspi/phase_11_param_gui.md` | 🟢 abgeschlossen (2026-05-21) |

> **Phase 12/13 — abgeschlossen:** Phase 12 (Pi-Plattform) + Phase 13 (Voll-Bringup) sind **erreicht** —
> der Stack läuft am Pi (`loopback_mode:=false`), der Roboter fährt **untethered mit Akku im Gelände**.
> Die Lokomotions-Features (Gangarten, Stance-Modi, Show, Hang-Lauf, Sit/Stand) sind vom
> Finalisierungs-Block-System **auf die echte HW übertragen und dort verifiziert**.

### Finalisierungs-Blöcke (Desktop, `project_finalization/`)

> Die Hauptarbeit nach den Bench-Phasen. Detail-Backlog: [`project_finalization/00_backlog.md`](project_finalization/00_backlog.md).

| Block | Inhalt | Status |
|---|---|---|
| **A** Analyse & Optimierung | Torque-/Hitze-Tool (A1 ✅); A2–A4 pausiert; **A5 IMU-Balance** (Branch `imu_balance`): Stufe 0/1/2/3a + **Terrain-Following TF-1/TF-2 🟢 Sim** (⏸️ pausiert, [§7](project_finalization/imu_balance/stage_3_terrain_following_plan.md)) · **Stufe 4 Terrain-adaptiv (Fußkontakte) 🟢 Sim** (S4-1/2/4/5/6/7) · **Stufe 5 HW-Fußkontakte 🟢 Sensor-Kette live-verifiziert** (Taster→FW GET_INPUTS→Plugin-Bool-Topics→RViz) · **Stufe 6 HW-IMU (BNO-055) 🟢 HW** (IP1/IP2) · **Stufe 7 Balance-Regler v2 🟢 HW-verifiziert** (Zwei-Fenster-Hysterese + Dual-Tiefpass + per-Achse; behebt das HW-Pendeln, hält sauber horizontal; Konfig in hw_balance.yaml). **Balance + Hang-Folgen laufen auf dem echten Roboter** (im Gelände verifiziert); IP3-Feintuning ist optionale Politur. | 🟢 A1 / 🟢 **A5 St.4/5/6/7 HW** / 🟡 IP3-Feintuning |
| **B** Lokomotion-Kern | Hinsetzen/Shutdown (B1), Gangarten Wave/Tetra/Ripple (B3), **Show-Pose + Tibia-Reach** (B4/B4.11); B2 verworfen, B5 deferiert | 🟢 Sim + **HW** (am echten Roboter) |
| **S1** Stance-Modi (3 Lauf-Höhen) | hoch/mittel/tief, L2/R2-Cycle, gekoppelte Reposition+Höhen-Lerp — ersetzt stufenlose Höhe (Envelope-sicher) | 🟢 Sim + **HW** |
| **C** Teleop / Steuerungs-UX | PS4 USB (C1/C2) + Live-Verstellung Gangart/Schrittweite (C3) + Bluetooth (C4) | 🟢 abgeschlossen |
| **D** Hardware-Bring-up / Plattform | **D1 Pi-Plattform (=Phase 12)** · **D2 Elektrik 2S LiPo (=Phase 8)** · D3 LVC/Telemetrie · D4 Power-On-Sequenz · D5 untethered | 🟢 **abgeschlossen** (Roboter fährt untethered mit Akku) |
| **I** Mobile-Teleop-App | Handy+Kishi statt PS4-BT: Mapping/Teleop/Lifecycle/Video/Status+Config (Ph.1–5) · E-Stop+Recovery (Ph.6) · Audio (Ph.7A) · echte Cam (Ph.7B) · **Show „Look-Around" (Ph.8)** · **Feld-Autonomie (Ph.9)** · Politur (Ph.10) | 🟡 **aktiv** — Ph.1–7B 🟢 · **Ph.8 🟢 Sim + HW verifiziert** (Körper-Pose über fixen Füßen, App-Show-Menü, Contract v0.13) · **Ph.9 🟡 Repo-Seite 🟢** (Always-On ab Boot, reparierter Poweroff, HW-Preset im App-Pfad; offen: Pi-Schritte + App-Buttons, Contract v0.13.1) |
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

> Der Roboter (HW/Elektrik/Lokomotion) ist fertig — der Weg nach vorne ist die **Mobile-Teleop-App
> (Block I)** + Feature-Erweiterungen. Detail: [`app_control_requirements/`](project_finalization/app_control_requirements/00_overview.md).

1. ✅ **Block-I App Phasen 1–5** fertig: Kishi→`/joy`-Mapping, Teleop über rosbridge, Bringup-/
   Shutdown-Lifecycle, Video-Vollbild (Gazebo-Cam → MJPEG), Status-Overlay + rqt-artiges Config-
   Panel. App-Seite implementiert. Nebenbei: Rubicon-Scene für den App-Flow (`always_on scene:=rubicon`).
2. ✅ **Phase 6 — Recovery + Not-Halt** fertig (Sim-E2E-verifiziert): **`/hexapod_estop`**
   (latched Freeze, gated den Tick, Sim+HW) + **`/hexapod_recover`** (ursachen-agnostisch: Freeze
   lösen + Latches/Monitore reset + Joint-Space-Ramp in den Stand, [D6]); App-E-STOP-/Recover-Button.
   Contract v0.10. **HW-Verifikation T6.8** am echten Roboter deferiert (Defer-Pattern).
3. ✅ **Phase 7A — Audio** fertig (Sim-verifiziert): neues Paket `hexapod_audio` spielt mp3s auf dem
   Roboter-Speaker (MAX98357A) — **Auto-Sounds** bei Aufstehen/Hinsetzen/Höhenwechsel/Freeze (explizite
   Cues vom gait_node, **Recovery stumm**) + **Soundboard** (`/hexapod/play_sound`); Mute via
   `sound_enable`. Contract v0.11. **HW (echte mp3s + Speaker) + App-Buttons** deferiert (Defer-Pattern).
4. ✅ **Phase 7B — echte Raspi-Cam am Roboter** fertig: OV5647 publisht `/camera/image_raw` auf
   dem Pi (via `rpicam-vid` MJPEG → `CompressedImage`) + `camera_enable` → `web_video_server` + App
   unverändert. Contract v0.12.
5. ✅ **Phase 8 — Show „Look-Around"** fertig (**Sim + HW verifiziert**): der Roboter steht, alle
   6 Füße bleiben fix, der **Körper** bewegt sich in 6 DOF (umschauen/wandern/Höhe, R1-Dead-Man,
   federt zurück) — die Kamera schwenkt mit. Auswahl über den Param **`show_mode`** aus dem
   **App-Show-Menü** (app-exklusiv); **Dancing/Free-Leg** als Platzhalter vorgebaut, damit die App
   für sie später nicht mehr angefasst werden muss. Zweistufige Sicherung (Per-Achse-Envelope +
   Greedy-Achsen-Clamp) → **kein Freeze aus der Show**. Contract v0.13,
   `phase_8_look_around_progress.md`.
6. **Phase 9 — Feld-Autonomie (aktiv, Repo-Seite 🟢):** der Roboter ist **ohne Dev-Rechner**
   benutzbar — Always-On-Schicht ab Boot (systemd-User-Dienst + linger), **reparierter Poweroff**
   (`pi_hostname` war leer → `host-mismatch`, der Pi fuhr nie herunter und wurde am Hauptschalter
   hart getrennt), App-Buttons „Pi herunterfahren" (wirkt auch bei hängendem Stack) und „Stack neu
   starten", **HW-Preset im App-Bringup** (Balance + Terrain-Features waren dort bisher aus!) +
   Comms-Loss-Fail-safe (25 s). Pi-Einstellungen in `tools/provision_pi.sh` (Neuaufsetz-Fall).
   Contract v0.13.1, `phase_9_field_autonomy_progress.md`.
7. **Phase 10 — Politur:** Reconnect-Handling, Controller-Profile (Portabilität), Robustheit (App).
7. **Optionale Politur (jederzeit):** A5 IP3-Feintuning (Terrain-Following im Laufen), Fußtaster-
   Latenz-Recheck auf HW (aus dem App-Overlay-Test), **Dancing/Free-Leg ROS-seitig umsetzen**
   (App-Menü steht schon), Audio-Knarz-Fix (Stützelko im Finalaufbau).

---

## Beim Phasenwechsel / Block-Abschluss

1. Done-Kriterium nachweislich erfüllt (Tests grün, Sim/HW verifiziert)
2. Timeshift-Snapshot anlegen (Name: `<phase/block>_done`)
3. Git-Commit + Tag
4. Diese Datei aktualisieren (Status + nächster aktiver Block/Phase oben)
5. Kurze Retro nach `PHASE_NOTES.md`: Was lief gut, was hat länger gedauert, was ist offen
