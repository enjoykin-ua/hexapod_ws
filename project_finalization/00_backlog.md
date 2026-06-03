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
| B4 | **Body-Pose ohne Laufen + „Show"-Pose** | ⚪ | Körper neigen/verlagern auf Stützbeinen; 2 Vorderbeine frei in der Luft bewegen (winken/„graben"/Spinnen-Pose). Statisch = CoG im Rest-Stützpolygon (nutzt joint_load CoG/Polygon aus A1). Erst gescriptete Posen, dann interaktiv. ⚠️ Framing mit User final klären. |
| B5 | **Volle 5 cm Körperhöhe (−0.130)** | 💤 | Standup kann −0.130 nicht direkt; bräuchte Body-Lift-in-Reposition (`standup_body_height` + Reposition interpoliert Höhe mit). Erst falls 4 cm nicht reichen. |

## Block C — Teleop / Steuerungs-UX
> **Plan + volle Belegungs-Tabelle + Handover:** [`C_teleop.md`](C_teleop.md). Design-Prinzip:
> Teleop = reines UI (Intents), `gait_node` = State/Logik. Reihenfolge: C1+ (USB) → C2 → C4.
| # | Stage | Status | Notiz |
|---|---|---|---|
| C1 | **PS4 USB-Steuerung** | 🟢 (Basis) | Läuft (Sim + aufgebockt). R1=Deadman + D-Pad + L2/R2-Höhe. |
| C1+ | **USB erweitern: Sticks omnidir. + Sit/Stand-Toggle + Shutdown + Show-Pose-Hook** | 🟢 (2026-06-03) | Topics + discrete Intent-Services (Sit/Stand-Toggle neu im gait_node). SIM+HW(USB) ok. Show-Pose nur Hook (B4). Feinjustage am Ende von C offen. |
| C2 | **Live-Param/Intent-Bridge (Gangart-Wechsel + Schrittweite)** | ⚪ | Komplexer, getrennt: Intents `/hexapod_cycle_gait` + Schrittweite; gait_node cyclet/clampt + STANDING-Schutz. (Ex-C2/C3 zusammengefasst.) |
| C4 | **Bluetooth** | ⚪ | `ps4_bt.yaml`-Profil + Pairing; erst wenn USB rund. Comms-Loss → B1-Fail-safe. |

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
