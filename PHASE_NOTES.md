# Phase-Notizen — Retros, Begründungen, Übergaben

> Supplementär zu [`PHASE.md`](PHASE.md). Diese Datei enthält die
> ausführlichen Retros, historischen Kontext, Übergabe-Items und
> Begründungen für Phase-Schnitte. PHASE.md selbst zeigt nur die aktuelle
> Phase + die kompakte Tabellen-Übersicht.

---

## Phasen-Hintergrund

**Wichtig:** Ab Phase 7 liegen alle Phasen-Detail-Docs unter `docs_raspi/`,
nicht mehr unter `docs/`. Phasen 0–6 bleiben in `docs/`.

**Phase-7-Bündel-Hintergrund:** Aus dem ursprünglichen „Phase 7 — Pi-
Portierung & Hardware" wurden auf Wunsch sechs feiner geschnittene
Phasen (7–12), damit die Übersicht sauber zeigt wo wir gerade stehen.
Der erste Mega-Draft liegt als `docs_raspi/_archive_phase_7_brainstorm.md`
archiviert — als Referenz für Inhalte, nicht mehr aktiv.

**Cross-Phase-Thread `servo_real_cal` (2026-05-24/25):** Nach Phase 11✅
wurde nicht direkt mit Phase 12 (Pi-Plattform) weitergemacht. Stattdessen
wurde ein Cross-Phase-Thread eingeschoben — Stages 0/0.5/0.6/A/B/D/E/C/E2
— um die Cal-Probleme aus Phase 10/11 sauber zu adressieren (Plugin-Math,
direction-Map, Stage 0.5/0.6 Safety-Layer, URDF-rad-Limit-Sync, HW-Walking
aufgebockt). Plan-Index: `docs_raspi/servo_real_cal_plan.md`. Memory-
Eintrag: `project_servo_real_cal_done.md`. Dieser Thread hat de facto
Phase-13 Sub-Stages B/C/D vorweggenommen — Phase 13 wurde entsprechend
auf "Pi-Recheck statt Erst-Bringup" angepasst.

---

## Phase-11-Retro (Param-GUI, ✅ 2026-05-21)

Alle 6 Stages A–F durchgelaufen. Live-Param-Surfaces für gait_node
(14 Params), Plugin-Cal (72 Params), Diagnostic-Topic + Preset-
Workflow + Workshop-Doku stehen. CI-Tests durchgängig grün
(hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware
220/0/20).

**Was gut lief:** Strikter Plan-First-Workflow pro Stage mit
ausführlichen Q&A-Tabellen (A-Q1..A-Q8 in Stage A, B-Q1..B-Q9 in
Stage B, etc.) hat substantielle Design-Diskussionen produziert
und Alternativen dokumentiert. Self-Reviews haben in fast jeder
Stage echte Bugs gefunden (Stage A: Phase-6-Topic-Handler-Sync-
Bug; Stage B: Range-Mismatch [800,2200] vs YAML-Default 500 +
Node-Name-Lowercase-Doku; Stage D: cwd-Falle bei relativem
params_file). Memory-Konvention `feedback_decision_alternatives_log.md`
wurde ausführlich umgesetzt. User-Q&A-Pattern hat Plan-Doku-
Qualität sichtbar erhöht (User korrigierte z.B. Pose-Management-
Verständnis → Phase-13-Scope-Notiz). Engine-Property-Refactor in
Stage A.0a (`stance_duration`/`linear_max` als computed Properties
statt Cache) war strategisch — sonst hätte Live-Cycle-Time-Update
Cache-Drift verursacht.

**Was länger gedauert hat:** Stage B (Plan ~1 d → ~1.5 d) wegen
F1-F6-Plan-Korrekturen vor Code-Beginn (Timestamp-bak,
is_active_-Member, std_srvs-Dep, README-Update, YAML-Schema,
tmpdir-Pattern). Stage D wegen ROS-Jazzy-Doku-Bugs:
`ros2 param dump` hat keine `--output-dir`/`--filename`-Args mehr
(nur stdout-Redirect), `rqt`-Container nicht via `ros2 run`
sondern direkt aus PATH. Beide entdeckt im User-Smoke.

**Was offen ist:** Cross-Phase-Pendenzen die in Phase 13 landen
müssen — `project_phase10_real_yaml_vel_limits.md`,
`project_phase13_initial_pose_presets.md`,
`project_phase9_h_oscilloscope_pending.md`, Auto-Cal-Tool für 15
verbleibende Servos (überholt durch servo_real_cal-Thread). Plus
Phase 8 (Strom- & Elektronik-Bench) ist harte Deadline vor Phase 12-Start.

**Schlüssel-Insight:** Live-Param-Tuning + Preset-Persistenz hat
sich als Game-Changer für Cal-Sessions herausgestellt. Stage-B-
`/save_calibration` mit Timestamp-bak macht beliebig viele
Cal-Iterationen schmerzfrei (kein Datenverlust durch Überschreiben).
Stage-D-`params_file`-Mechanismus für Gait-Presets erlaubt Demo-
Reproduzierbarkeit über mehrere Sessions hinweg. Diese
Infrastruktur wird in Phase 13 mit echter HW noch wertvoller.

---

## Phase-10-Retro (Single-Leg Bring-up + Kalibrierung, ✅ 2026-05-19)

Alle 8 Stages A–G + I durchgelaufen (Stage H war eh gestrichen).
leg_6 (Pin 15/16/17) ist voll kalibriert; IK + gait_node-Walking auf
echter Hardware verifiziert (aufgehängt, ohne Bodenkontakt).

**Was gut lief:** Strikter Plan-First-Workflow pro Stage (4 Pflichtinhalte
+ offene Fragen) hat substantielle Diskussionen produziert — z.B. Strategie B'
für Coxa-Self-Collision-Schutz in Stage B, Loopback-First-Workflow in Stage F.2.
Memory-Konvention `feedback_urdf_refactor_full_smoke.md` hat in Stage F1
(Tibia-Update) direkt gegriffen — Sim-Verifikation als Phase-12-Pendenz markiert
statt vergessen. User-Pattern „Commit zwischen Sub-Stages" (Stages C+D+E+F-Phase-1)
hat Iterations-Anker geliefert. Self-Reviews haben in jeder Stage echte Drifts
gefunden (Plan-Annahme Test-Fixtures in Stage B → Reality committed YAML; Stride-
Range-Test deferred in F-T6 etc.).

**Was länger gedauert hat als geplant:** Stage B 0.5 d → 1 d wegen User-Strategie-
Wechsel C→B' (Self-Collision-Sicherheit über Range-Maximierung). Stage F war
1.5 d Wildcard → ~2 d wegen Tibia-Update mit IK-Probe-Default-Anpassung +
Loopback-First-Discovery + Coxa-Sichtbarkeits-Discussion. Stage G war als
~1 h geplant, hat ~1.5 h gebraucht wegen Echo-State-Klarstellung-Discussion
die Strategie auf Option C reduziert hat.

**Was offen ist:** Cross-Phase-Pendenzen (nach Phase-11-Renumbering 2026-05-19
zeigen Refs auf Phase 13 statt vorheriger Phase 12):
- `project_phase10_tibia_length_sim_pending.md` (Sim-Verifikation nach Tibia-Update — könnte in Phase 11 mit Sim-Tuning erledigt werden)
- `project_phase10_real_yaml_vel_limits.md` (Vel/Accel mit Bench-Last — Phase 13)
- `project_phase13_initial_pose_presets.md` (Initial-Pulse-Preset statt Hand — Phase 13)
- `project_phase9_h_oscilloscope_pending.md` (Oszi/Logic-Analyzer-Tests)
- Auto-Cal-Tool für 15 verbleibende Servos — **überholt durch servo_real_cal-Thread 2026-05-25**

**Echo-State-Klarstellung als Schlüssel-Insight:** User-Realität (Servos
liefern niemals Position-Feedback, kein Wechsel zu Feedback-Servos geplant)
hat Stage-G-Strategie fundamental geändert (Option C statt Option B).
Phase 13 muss mit dieser Realität planen — JTC-Toleranz-Constraints
sind faktisch wertlos in unserem System; Schutz kommt aus den drei
Hardware-Schichten (URDF-Cap + Pulse-Clamp + Position-Limits).

---

## Phase-9-Retro (hexapod_hardware-Plugin, ✅ 2026-05-16)

Alle 10 Stufen A–J durchgelaufen. CI-Anteil voll grün (208 Plugin-Tests +
18 launch_testing-Tests), Hardware-Pfad bis Plugin↔Firmware-Pipeline mit
echtem Servo2040 ohne Hexapod-Servos verifiziert. **Ausstehende Items:**
Oszi/Logic-Analyzer-Verifikation (Stage H H-T8/H-T9) — dokumentiert in
Memory-Eintrag `project_phase9_h_oscilloscope_pending.md` als Cross-Session-
Reminder; bei Hardware-Verfügbarkeit (z.B. Phase 10 Bench-Setup) nachholen.

**Was gut lief:** der Plan-First-Workflow mit jeweils 4–5 offenen Fragen
pro Stufe hat substantielle Design-Diskussionen produziert (z.B. F-Q1
velocity-State-Mismatch, G-Q1 loopback-Default, H-Q1 Bench-Netzteil-
Setup) die im Code-Edit allein nicht aufgekommen wären. Memory-Konvention
`feedback_urdf_refactor_full_smoke.md` aus Stage F hat in Stage G + H
direkt gegriffen.

**Was länger gedauert hat als geplant:** Hardware-Stages (H, I) hatten
mehr Real-World-Lessons als antizipiert (USB-CDC-Boot-Garbage,
ros2_control Auto-Deactivate-Bei-Write-Fail, Linter-Pattern-Lerncurve
für launch_testing). Plan-Korrektur-Sektionen pro Stage haben das
transparent gemacht. Bei F-Q5 wurde F-T9 nach Stage G verschoben weil
die „einzelner CLI-Aufruf reicht"-Annahme an rcl-Parser-Limitierung
gescheitert ist.

**Was offen ist:** (1) Oszi/Logic-Analyzer-Tests (siehe oben), (2)
optional `phase-7-done`-Tag retroaktiv im fw-Repo (Doku-Hygiene aus
Stage H H-T3), (3) Plugin-API-Migration `export_*_interfaces()` →
`on_export_*_interfaces()` ist out-of-scope geblieben (alte API gewinnt
wenn Override non-empty) — Pragma-Suppression in test_plugin_registration.cpp.

---

## Phase-7-Übergabe (Servo2040 Firmware, ✅ 2026-05-14)

Alle Stufen A–G grün am Board verifiziert, Doku in
`docs_raspi/phase_7_progress.md` (inkl. Pimoroni-API-Erkenntnis-Tabelle +
Retrospektive). Stufe H Git-Aktionen (`phase-7-done`-Tag in fw-Repo und
hexapod_ws, Commit der phase_7-Docs) macht der User beim Phasenwechsel.

---

## Phase 8 Pausen-Status (2026-05-14)

**Phase 8 (Bench-Elektronik):** Inhalt (DCDC-Wandler für Pi, GND-Stern,
Bulk-Caps) wird erst gebraucht wenn der Pi ins Spiel kommt. Phase 9 + 10
laufen weiterhin am Desktop mit der bestehenden Bench-PSU-Verkabelung aus
Phase 7. **Harte Deadline: vor Beginn Phase 12 (Pi-Plattform) muss Phase 8
durch sein.**

**Phase 8b (Sim+HW-Mirror):** Architektur-Abgrenzung macht den Mirror
unabhängig — kann jederzeit ergänzend gebaut werden, ist aber kein
Done-Kriterium für 9/10/11/12.

---

## Phase-6-Übergabe (Teleop, ✅ 2026-05-10)

PS4-Controller via USB läuft. D-Pad steuert Bewegung (vor/zurück, drehen am
Stand), L2/R2 ändern Body-Höhe (nur im STANDING-State), R1 ist Dead-Man-
Switch. Engine-Erweiterung `gait_node` mit `/cmd_body_height` Topic.
Tastatur-Stufe verworfen, Bluetooth-Pairing deferred.

**Übergabe-Items für Phase 7 ff. (zum Teil später eingelöst):**

- **`controllers.yaml use_sim_time: true`** musste in Phase 9 auf `false`
  (Wallclock am Pi) für `controllers.real.yaml`. ✓
- **`body_height = -0.052`** war Sim-spezifischer JTC-Tracking-Lag-Workaround.
  HW-Default zurück auf `-0.047` — echte Servos haben keinen Lag. ✓
- **KDL-Warning** weiter offen — am Pi auch unkritisch (User-Entscheidung).
- **`hexapod_hardware`-Paket** (C++ HardwareInterface, pluginlib) in
  Phase 9 angelegt — ersetzt `gz_ros2_control` für echte Servo2040-Hardware. ✓
- **Sicherheit:** Hexapod aufbocken für Joint-Tests, Hardware-Kill-Switch
  griffbereit, reduzierte Geschwindigkeit (siehe CLAUDE.md §9). ✓ (Stages 10,
  E2 nutzen das durchgängig)
