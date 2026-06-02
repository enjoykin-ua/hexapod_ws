# Projekt-Finalisierung — Backlog (offene Stages bis zum fertigen Roboter)

> Die noch offenen Arbeitsblöcke, um das Projekt zu finalisieren (Brainstorm 2026-06-02,
> geordnet). **Referenz-Wissen** (Architektur, AI-Navigation, Tools) liegt getrennt in
> [`../project_architecture/`](../project_architecture/00_overview.md).
> Verlinkt aus `PHASE.md`. Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 fertig — ⏸️ pausiert — 💤 deferiert.

> **Stand:** Phase 13 Stage 1 (Lauf-Optimierung) ist weit gediehen — Tibia-Unlock +2.50,
> feet-closer high Walk-Pose (body −0.120, Hub 8 cm), Zwei-Phasen Standup→Reposition→Walk,
> PS4-USB-Teleop laufen (Sim + aufgebockt). Dieser Backlog ist das, was *danach* noch kommt.

---

## Block A — Lokomotion-Kern
| # | Stage | Status | Notiz |
|---|---|---|---|
| A1 | **Hinsetz-/Abschalt-Sequenz** | ⚪ | Umkehrung des Aufstehens: Walk-Pose → Füße raus (Rück-Reposition) → Körper sanft absenken → Relay/Servos lösen. Inkl. graceful-shutdown VOR Stromtrennung (Servos zentrieren beim Power-Off). **Wichtig für sicheren Realbetrieb.** |
| A2 | **Velocity-Feedforward (Zittern-Fix)** | ⚪ | Soll-Geschwindigkeit in die Trajectory-Punkte → JTC interpoliert durch statt Stop-pro-Punkt. `tfs_factor` mildert nur. |
| A3 | **Weitere Gangarten** | ⚪ | Wave/metachronal (stabilste, 5 Beine tragen → **senkt Tibia-Last/Hitze ~40%**), Ripple, Tetrapod. Billig: `GaitPattern`-Einträge. + Gangart-Wechsel im Lauf. |
| A4 | **Body-Pose ohne Laufen + „Show"-Pose** | ⚪ | Körper neigen/verlagern auf Stützbeinen; 2 Vorderbeine frei in der Luft bewegen (winken/„graben"/Spinnen-Pose). Statisch = CoG muss im Rest-Stützpolygon bleiben (nutzt Torque/CoG-Tool C). Erst gescriptete Posen, dann interaktiv. ⚠️ **Framing mit User final klären** (gescriptete Spaß-Pose vs. Balance-Capability). |
| A5 | **Volle 5 cm Körperhöhe (−0.130)** | 💤 | Standup kann −0.130 nicht direkt; bräuchte Body-Lift-in-Reposition (`standup_body_height` + Reposition interpoliert Höhe mit). Erst falls 4 cm nicht reichen. |

## Block B — Teleop / Steuerungs-UX
| # | Stage | Status | Notiz |
|---|---|---|---|
| B1 | **PS4 USB-Steuerung** | 🟢 | Läuft (Sim + aufgebockt). R1=Deadman + D-Pad. |
| B2 | **Live-Verstell-Backend (Höhe/Schritt/Gangart)** | ⚪ | Backend großteils da (ROS-Params + cmd_body_height). Sauberer Param-Bridge-Pfad Controller→Param + STANDING-Schutz. |
| B3 | **PS4-Belegung erweitern** | ⚪ | Tasten für Höhe/Schrittweite/Hub/Gangart/Tempo; klare Modi (Fahr- vs Trim-Modus). Nutzt B2. |
| B4 | **Bluetooth** | ⚪ | `ps4_bt.yaml`-Profil + Pairing; erst wenn USB rund. + Comms-Loss → sicherer Stopp. |

## Block C — Analyse & Optimierung (Hitze)
| # | Stage | Status | Notiz |
|---|---|---|---|
| C1 | **Torque-/Hitze-Viz-Tool** | ⚪ | Quasi-statische Gelenk-Momente (Jᵀ·F) pro Pose → RViz Zahl+Farbe; Sweep → last-optimale (radial,Höhe). Coxa ~0 für Vertikallast (bestätigt User-Intuition). Femur+Tibia = gleicher Servo (35 kg·cm) → Ziel: Momente ausbalancieren. |
| C2 | **Pose-Optimierung gegen Hitze** | ⚪ | Mit C1 die last-minimale/-gleichmäßige Pose finden; + Wave-Gait (A3). |
| C3 | **Tibia-Längen-/Geometrie-Studie** | 💤 | L_femur 0.080 vs L_tibia 0.200 (2,5×!) → Tibia-lastig. Geometrie-Änderung könnte umverteilen, ABER HW-TABU (Rattenschwanz). **Erst C1 rechnen lassen**, dann entscheiden. |
| C4 | **Strom-/Thermo-Messung** | ⚪ | Kann Servo2040 Servo-Strom lesen? → echte Messung gegen Modell C1. Belastbarste Hitze-Datenquelle. |
| C5 | **Selbst-Kollisions-Check (Weg B)** | 💤 | **Bewusst deferiert — wir laufen erstmal OHNE (Weg A, Tibia hart freigeschaltet).** Nachrüsten bei Balance/Terrain/Body-Pose, wo der Check echt triggert. Plan existiert: `docs_raspi/phase_13_stage_1_collision_check_plan.md`. |
| C6 | **IMU-Integration → Balance** | ⚪ | Eigenes Sensor-Plugin, `/imu/data`; Körper-Leveling, Kipp-Erkennung; Vorstufe Terrain. |

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
| E2 | **Terrain / Foot-Contact-Sensorik** | 💤 | Fuß-Schalter (im URDF conditional) → adaptiver Touchdown, unebener Boden, Schlupf/Sturz-Erkennung. **Binär = Kontakt, nicht Kraft** (nicht für Hitze). Auf flachem Boden jetzt kein Gewinn → mit Balance/Terrain. |
| E3 | **Preset-/Config-Management** | ⚪ | „Default-Walk"-Preset, gespeicherte Profile, sauberes Laden. |

---

## Empfohlene Reihenfolge (grob, Abhängigkeiten)
1. **A1 Hinsetzen** + **C1 Torque-Tool** (+ **A3 Wave-Gait**) — Betriebssicherheit + Hitze, beide ohne HW-Umbau, C1 entscheidet die Geometrie-Frage.
2. **A2 Feedforward** (Gangbild) · **B2/B3 Teleop-Verstellung**.
3. **D1 Pi** · **D2 Elektrik** + **D3/D4** — Weg zu untethered (parallel vorbereitbar).
4. **B4 BT · C5/C6 Balance · E1/E2 Robustheit** — nach dem Kern.

> Bei Beginn einer Stage: Plan-Doku nach `CLAUDE.md` §4 (Plan→Freigabe→Tests→Self-Review),
> Arbeits-Detail nach `docs_raspi/` (oder hier als Stage-Datei), Referenz nach `project_architecture/`.
