# Projekt-Finalisierung — Backlog (offene Stages bis zum fertigen Roboter)

> Die noch offenen Arbeitsblöcke, um das Projekt zu finalisieren (Brainstorm 2026-06-02,
> geordnet). **Referenz-Wissen** (Architektur, AI-Navigation, Tools) liegt getrennt in
> [`../project_architecture/`](../project_architecture/00_overview.md).
> Verlinkt aus `PHASE.md`. Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 fertig — ⏸️ pausiert — 💤 deferiert.

> **Stand:** Phase 13 Stage 1 (Lauf-Optimierung) ist weit gediehen — Tibia-Unlock +2.50,
> feet-closer high Walk-Pose (body −0.120, Hub 8 cm), Zwei-Phasen Standup→Reposition→Walk,
> PS4-USB-Teleop laufen (Sim + aufgebockt).
>
> **Reihenfolge (User 2026-06-02):** Block A (Analyse) war zuerst — **A1 (Torque-Tool)
> erledigt; RViz zeigte keine kritischen Last-Extrempunkte → Rest von Block A pausiert.**
> Danach: **erst Lokomotion-Kern (Block B), dann Teleop (Block C)** — diese Reihenfolge
> macht mehr Sinn (Funktionalität vor Bedien-Komfort).

---

## Block A — Analyse & Optimierung (Hitze, Kräfte)  ⏸️ PAUSIERT (außer A1 ✅)
> A1 erledigt; Last-Auslastung niedrig (~15–30 %), keine Extrempunkte → Analyse vorerst genug.

| # | Stage | Status | Notiz |
|---|---|---|---|
| A1 | **Torque-/Hitze-Viz-Tool** | 🟢 | joint_load-Modell + Live-RViz (`torque_viz`, Last am Gelenk) + Sweep (`torque_sweep`). Plan/Tests: `A1_torque_viz_plan.md`. Befund: statisch Femur>Tibia, Peak niedrig. |
| A2 | **Pose-Optimierung gegen Hitze** | ⏸️ | Mit A1 die last-minimale/-gleichmäßige Pose festziehen. Pausiert (keine Extrempunkte gesehen). |
| A3 | **Tibia-Längen-/Geometrie-Studie** | ⏸️ | Nur falls Hitze später doch kritisch (HW-TABU, erst A1-Modell rechnen). |
| A4 | **Selbst-Kollisions-Check (Weg B)** | ⏸️ | Bewusst OHNE (Weg A, Tibia hart freigeschaltet). Nachrüsten bei Balance/Terrain/Body-Pose. Plan: `docs_raspi/phase_13_stage_1_collision_check_plan.md`. |
| A5 | **IMU-Integration → Balance** | ⏸️ | Eigenes Sensor-Plugin, `/imu/data`; Körper-Leveling, Kipp-Erkennung; Vorstufe Terrain. **Auch der echte Fix für das dynamische Körper-Wackeln von Tetrapod/Ripple (B3)** — aktive Lage-Regelung macht die asymmetrisch stützenden Gangarten ruhig. |

## Block B — Lokomotion-Kern  ⬅ ALS NÄCHSTES
| # | Stage | Status | Notiz |
|---|---|---|---|
| B1 | **Hinsetz-/Abschalt-Sequenz** | 🟢 (2026-06-03) | Umkehrung des Aufstehens: Walk-Pose → Füße raus (Rück-Reposition) → Körper sanft absenken → Relay/Servos lösen. Inkl. graceful-shutdown VOR Stromtrennung (Servos zentrieren beim Power-Off). **Wichtig für sicheren Realbetrieb.** |
| B2 | **Velocity-Feedforward (Zittern-Fix)** | ❌ (2026-06-03) | Versucht (Finite-Diff → `JointTrajectoryPoint.velocities`, `allow_nonzero_velocity_at_trajectory_end`) — **kein beobachtbarer Nutzen** (Sim: keine Servo-Dynamik; HW: kein Unterschied) → vollständig zurückgebaut. Falls Zittern je real stört: Hebel = Vel/Accel-Limits im JTC, nicht dieser FF. Details: `B_lokomotion_kern.md` §B2. |
| B3 | **Weitere Gangarten** | 🟢 (2026-06-03) | Wave/Tetrapod/Ripple als `GaitPattern`-Einträge (137 Tests grün), Umschalten via `gait_pattern`-Param. Sim+HW verifiziert: Tripod+Wave am stabilsten; **Tetrapod/Ripple nutzbar, volle Ruhe erst mit A5 IMU-Balance** (Open-Loop-Wackeln). Details: `B3_gaits_plan.md`. |
| B4 | **Body-Pose + „Show"-Pose (Free-Leg)** | 🟢 Sim (2026-06-04) | Show rein/raus + Vorderbeine per Joystick (lat/vert) + **B4.11 Tibia-Reach** (Trigger). CoG-gesichert, Round-Trip. Sim verifiziert; HW aufgebockt offen. Plan/Progress/Test: `B4_show_pose_*`. |
| S1 | **Stance-Modi (3 Lauf-Höhen)** | 🟢 Sim (2026-06-04) | hoch/mittel/tief (real-engine-validiert, Femur-Marge), L2/R2-Cycle, gekoppelte Reposition+Höhen-Lerp, Sit-aus-hoch-Routing. Ersetzt stufenlose Höhe. `stance_modes_*`. HW offen. |
| B5 | **Volle 5 cm Körperhöhe (−0.130)** | 💤 | Standup kann −0.130 nicht direkt; bräuchte Body-Lift-in-Reposition. (hoch-Modus −0.140 ist bereits via Stance-Switch-Lift gelöst — B5 nur falls als Standup-Direktziel nötig.) |

## Block C — Teleop / Steuerungs-UX
> **Detailplan + Belegungs-Tabelle + Handover:** [`C_teleop.md`](C_teleop.md) (dort als Stages
> C1+/C2 gegliedert = hier C2/C3). Design-Prinzip: Teleop = reines UI (Intents), `gait_node` = Logik.

| # | Stage | Status | Notiz |
|---|---|---|---|
| C1 | **PS4 USB-Grundsteuerung** | 🟢 | Fahren/Drehen + L2/R2-Höhe + R1-Dead-Man (Phase 6, Sim + aufgebockt). |
| C2 | **USB-Steuerung erweitert** | 🟢 (2026-06-03) | Linker Stick omnidir. (x/y) + rechter Stick dreh, L1=langsam, L2/R2 ±1 cm Höhe, △ Sit/Stand-Toggle, ○-lang Shutdown, ✕-lang Show-Pose-Hook (B4). Neuer Service `/hexapod_sit_stand_toggle`. SIM+HW(USB) ok. Details: `C_teleop.md`. |
| C3 | **Live-Verstellung: Gangart + Schrittweite** | 🟢 (2026-06-03) | D-Pad ←/→ Gangart, ↑/↓ Schrittweite via Intents `/hexapod_cycle_gait` + `/hexapod_adjust_step_length` (gait_node cyclt/clampt + STANDING-Schutz; Teleop-Debounce). SIM ok; HW via B3+C2 abgedeckt. |
| C4 | **Bluetooth** | 🟢 (2026-06-03) | DS4 via headless-`bluetoothctl` gekoppelt (bonded+trusted, Reconnect per PS-Taste), `/joy` über BT, `hid-playstation`-Layout = USB → `ps4_bt.yaml` unverändert. Doc: `C4_test_commands.md`. Comms-Loss → B1-Fail-safe. |

> **Offen am Ende von Block C (Feinjustage, s. `C_teleop.md`):** Vorzeichen/Skalen/longpress/
> deadzone; **+ nur envelope-gültige Kombinationen** aus Höhe×Schrittweite×Gangart zulassen
> (Live-Tuning kann sonst in out-of-reach/IK-Freeze laufen).

## Block D — Hardware-Bring-up / Plattform
| # | Stage | Status | Notiz |
|---|---|---|---|
| D1 | **ROS2 auf Raspberry Pi** (=Phase 12) | ⚪ | Pi hat nur Ubuntu. ROS2 Jazzy arm64, Workspace-Subset bauen (ohne Gazebo), `hexapod_hardware`+Servo2040-USB am Pi, gegen Bench fahren. Unabhängig → parallel vorbereitbar. |
| D2 | **Elektrik 2S LiPo finalisieren** (=Phase 8) | ⏸️ | User macht Elektrik (ich nur grob). 2S LiPo ~5200 mAh / 50C → Regelung Servo-Rail vs Pi-Rail/BEC, Absicherung, Kill-Switch (vorhanden), Strom-/Spannungs-Monitoring. |
| D3 | **Software: LVC + Batterie-Telemetrie** | ⚪ | Unterspannungs-Cutoff (2S nicht unter ~6,0–6,6 V), Batterie ins ROS, Low-Battery → Warnung→Hinsetzen. |
| D4 | **Boot-/Power-On-Sequenz am Boden** | ⚪ | Servos zentrieren beim Einschalten (HW-fix). Definierte Sequenz (aufgebockt booten ODER Relay-Gate + sofort kontrolliertes Aufstehen), sonst flailt er. |
| D5 | **Mechanik/Verkabelung untethered** | ⚪ | Kabelführung, Akku-Halterung, Zugentlastung; Cal-Drift-Re-Check nach Betrieb/Hitze. |

## Block E — Robustheit / später
| # | Stage | Status | Notiz |
|---|---|---|---|
| E1 | **Fehler-/Safe-State im Realbetrieb** | ⚪ | Definiertes Verhalten bei Overcurrent/Watchdog/IKError/Comms-Loss im Lauf (freeze → hinsetzen?). |
| E2 | **Terrain / Foot-Contact-Sensorik** | 💤 | Fuß-Schalter (im URDF conditional) → adaptiver Touchdown, unebener Boden, Schlupf/Sturz-Erkennung. **Binär = Kontakt, nicht Kraft.** Auf flachem Boden jetzt kein Gewinn → mit Balance/Terrain. |
| E3 | **Preset-/Config-Management** | ⚪ | „Default-Walk"-Preset, gespeicherte Profile, sauberes Laden. |

## Block F — Systemsteuerung / Lifecycle  🟡 AKTIV
> Master-Plan + Architektur-Entscheidungen: [`F_systemsteuerung_plan.md`](F_systemsteuerung_plan.md).
> Hardware-Shutdown-Schalter am Servo2040 (A1/GP27) → kontrolliertes Hinsetzen +
> Relay-Aus + sauberer Pi-Shutdown. Viel der ROS-Kette existiert schon
> (`/hexapod_shutdown`, Sit-Sequenz, `/hexapod_relay_set`) — neu sind FW-Bit,
> Bool-Publisher, Supervisor-Node + Shutdown-Guard.

| # | Stage | Status | Notiz |
|---|---|---|---|
| F1 | **servo2040 FW: Schalter → `status_flags` Bit 7** | 🟢 | 3-s-Halten + Arm-nach-CLOSED, LED-Rohpegel bleibt. Bench T1–T5 grün. Plan/Test/Progress: `F1_fw_switch_bit_*`. FW-Progress hier (Block F), NICHT phase_7. |
| F2 | **hexapod_hardware: Bit 7 → latched Bool `/hexapod/shutdown_request`** | 🟢 | `read()` konsumiert `latest_state()`, latched Publisher; **+ GET_STATE-Poll in write()** (Live-Befund — sonst nie STATE_RESPONSE). Sub-Echo braucht reliable+transient_local. Live grün. `F2_*`. |
| F3 | **gait_node: latched Bool `/hexapod/shutdown_complete`** | 🟢 | Vorhandenes `_shutdown_latched` als latched Topic (false→true einmalig). Unit + Live (aufgebockt) grün. `F3_*`. |
| F4 | **hexapod_supervisor (neues Paket) + Guard** | 🟢 | Node + 3-Schicht-OS-Guard (DEV_HOSTS hart, `enable_os_shutdown`, Hostname). Arm/Flanke, K2-Retry, Backstop 12 s, Complete-Race-Fix. 15 Tests + Dev-Smoke + STANDING-Volltest (7,04 s, reason=complete) grün. Smoke/Test fanden Hostname-Typo + Race + zu-knappen Backstop. `F4_*`. |
| F5 | **Integration + Pi-Deployment** | 🟡 | **F5a (jetzt, Dev):** supervisor.yaml + Einhängung in real.launch.py (Auto-Start, eine Config überall, Guard entscheidet per Host). **F5b (später, Pi):** pi_hostname + sudoers + Branch/Build + End-to-End — gekoppelt an Block D1 (ROS2-auf-Pi). Plan: `F5_integration_plan.md`. |
| F6 | **Pi-Update Ablaufplan (Runbook)** | 🟡 | Branch-Wechsel `leg_changes` + Subset-Rebuild (`--packages-skip hexapod_gazebo hexapod_sensors`) + F5b-Scharfschalten am Pi (`hexapod-pi`). Cal-Recheck geparkt (Bein 3). `F6_pi_update_checklist.md`. |

---

## Empfohlene Reihenfolge (grob, Abhängigkeiten)
1. **Block B — Lokomotion-Kern:** **B1 Hinsetzen** (Betriebssicherheit) + **B3 Wave-Gait**
   (stabiler, last-ärmer), dann **B2 Feedforward** (Gangbild), **B4 Body-Pose/Show**.
2. **Block C — Teleop:** **C2/C3 Live-Verstellung + Belegung**, dann **C4 BT**.
3. **Block D — Plattform:** **D1 Pi** + **D2 Elektrik** + **D3/D4** (Weg zu untethered, parallel vorbereitbar).
4. **Block E — Robustheit** + (bei Bedarf reaktiviert) **Block A** (A2/A3/A4/A5).

> Bei Beginn einer Stage: Plan-Doku nach `CLAUDE.md` §4 (Plan→Freigabe→Tests→Self-Review)
> **+ eine Test-Markdown** (`<stage>_test_commands.md`, je Stage). Arbeits-Detail nach
> `docs_raspi/` oder hier als Stage-Datei; Referenz nach `project_architecture/`.
