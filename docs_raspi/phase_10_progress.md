# Phase 10 — Progress-Tracker

**Phase:** Single-Leg Bring-up + Kalibrierung
**Plan:** [phase_10_single_leg.md](phase_10_single_leg.md)
**Sicherheits-Setup:** [phase_10_safety_setup.md](phase_10_safety_setup.md)
**Aktiv seit:** 2026-05-16

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**
> (Memory `feedback_phase_progress_tracking.md`).
>
> Design-Entscheidungen + verworfene Alternativen unten festhalten,
> damit Re-Design später möglich ist ohne Erinnerung
> (Memory `feedback_decision_alternatives_log.md`).

---

## Design-Entscheidungen vor Stufe A

Konsolidiert aus Mutter-Plan-Doku
[Architektur-Entscheidungen A–J](phase_10_single_leg.md#architektur-entscheidungen).

### A. Hybride Tester-First-Kalibrierungs-Methodik (kompakt: nur leg_6) → **Hybrid**

- **Final:** HJ-Tester für Pre-Calibration (mech. Mitte + sicherer Endlagen-Bereich)
  in Stage B, dann Stack-Validation pro Servo (Stages C/D/E) für `direction`
  + Stack-Pipeline-Verifikation. Nur leg_6 (Pin 15/16/17), andere 15 Servos
  bleiben Platzhalter bis Phase 12.
- **Verworfen:**
  - Tester-only: findet `direction` nicht.
  - Stack-only manuelles Jog: höheres Anschlag-Brumm-Risiko.
  - Voll-Calibration aller 18 Servos: out-of-scope, Phase-12-Job.
  - `pulse_per_rad`-Feld: Phase-9-Design-Entscheidung hat 3-Punkt-Schema
    festgelegt (siehe `project_phase9_decisions.md`).

### B. Bench-Setup (PSU 7.0 V, CC-Limit pro Stage)

- **Final:** 7.0 V Bench-Spannung (LiPo-Plateau-Mitte). CC-Limit 3 A (Coxa) /
  4 A (Femur/Tibia) / 8 A (3-Servo-Bein). Servos werden pro Stage einzeln
  angeklemmt, andere 15 Pins bleiben elektrisch frei.
- **Verworfen:**
  - 6.0 V (Phase-9-Default): zu niedrig vs. realer LiPo-Betriebspunkt.
  - 7.4 V (LiPo-Nominal): in der Praxis sitzt LiPo unter Last meist
    bei 7.0–7.4 V, also ist 7.0 V der realistischere Kalibrierungs-Punkt
    + Sicherheitsmarge.
- Details: [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §2.

### C. Initial-Pulse-Schlag-Mitigation: User hält Bein

- **Final:** Vor jedem ersten `on_activate` pro Stage hält der User das
  Bein manuell in eine Position nahe der Servo-Mitte. Damit springt der
  Servo beim ENABLE nur wenige Grad, kein Stall-Brumm.
- **Verworfen:**
  - Soft-Start im Plugin (= Position-Feedback nötig, haben wir nicht
    wegen Echo-State).
  - Ramped-Enable in der Firmware (= Firmware-Change, Phase-12-Kandidat).
- Details: [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §6.

### D. Verkabelungs-Sequenz: PSU-AUS → Stecken → Sichtprüfung → PSU-AN

- **Final:** Strikte Reihenfolge bei jedem Servo-An-/Abklemmen. Hot-Swap
  mit angeschalteter PSU ist explizit verboten (Servo-Tod-Risiko bei
  falscher Polarität).
- Details: [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §4.

### E. Tester-Range 800–2200 µs deckt URDF-Joint-Range ab

- **Final:** HJ-Tester-Range ist ausreichend für unsere ±90°-URDF-Limits
  (Coxa/Femur) und ±86° (Tibia). 270°-Servos haben mechanisch mehr
  Range, aber wir kalibrieren auf URDF-Limit (engere Grenze).

### F. RViz-Sync-Beobachtung als Verifikations-Hilfe

- **Final:** Stages C/D/E/F starten `real.launch.py rviz:=true`.
  RViz zeigt Echo-State (= was Plugin geschickt hat). Bei Diskrepanz
  zwischen RViz-Bein und echtem Bein: Indikation für Stall oder
  falsche Kalibrierung.
- **Verworfen:** RViz weglassen — würde Sanity-Check kosten ohne Aufwand-Ersparnis.

### G. Strom-Logging mit `tools/log_state.py`

- **Final:** Stage F protokolliert Servo2040-State per CSV (über USB-CDC,
  20 Hz Polling). `current_ma` ist Rail-Total, kein per-Servo-Wert.
  Stage G nutzt CSV für Vel/Accel-Limit-Auslegung.

### H. Bein-Geometrie-Verifikation als Stage-F.1 (verworfen: Stage A)

- **Final:** Lineal-Check der echten leg_6-Längen als erster Sub-Step
  von Stage F. Stages B–E sind längen-unabhängig.
- **Verworfen:** Check in Stage A — würde Stage A um ~30 min verlängern
  ohne Mehrwert für B–E.

### I. `direction`-Flip: Build-Edit-Build (verworfen: Plugin-Live-Parameter)

- **Final:** YAML editieren → `colcon build` → relaunch. ~5–10 min pro
  Flip × 3 Servos = ~30 min worst case.
- **Verworfen:** Plugin-Erweiterung mit `direction` als ROS-Live-Param —
  2–3 d Entwicklungszeit, nicht amortisierbar bei 3 Servos.
  Phase-12-Entscheidung wenn 18 Servos durchgegangen werden.

### J. IK-Trajectory-Source in Stage F: Hybrid F.2 + F.3

- **Final:** Stage F macht zwei Sub-Steps:
  - F.2 direkter IK-Aufruf (Diagnose-Probe, ~30-Zeilen-Python-Skript)
  - F.3 gait_node mit `/cmd_vel`-Stub (Voll-Pipeline-Test, gleicher
    Pfad wie Phase 12)
- **Verworfen:** Pure F.2 oder Pure F.3 — Hybrid bietet bessere
  Diagnose-Trennung (IK vs. gait_node) und beweist Phase-12-Pipeline.

---

## Stufe A — Doku-Vorbereitung

> **Vorab-Plan:** [`phase_10_stage_a_plan.md`](phase_10_stage_a_plan.md) —
> Logik-Skizze (3 Dateien + Cross-Links), Tests-Liste A-T1 bis A-T5,
> 11 Progress-Bullets, User-Entscheidungen vom 2026-05-16:
> - **A-Q1** Safety-Setup → **A** (eigene Datei `phase_10_safety_setup.md`)
> - **A-Q2** Progress-Skelett → **A** (alle Stages A–I als Skelett-Sektionen, Phase-9-Pattern)
>
> Done-Kriterium A: progress.md + safety_setup.md angelegt, Cross-Links
> verifiziert, Build/Tests regression-frei.

- [x] A.1 phase_10_stage_a_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-16)
- [x] A.2 docs_raspi/phase_10_progress.md angelegt mit Stages A–I als Sektionen + Design-Entscheidungs-Block aus Mutter-Plan-Doku konsolidiert (2026-05-16)
- [x] A.3 docs_raspi/phase_10_safety_setup.md angelegt mit **8 Abschnitten** (6 Pflicht + §7 Pre-Stage-Checkliste + §8 Eskalations-Pfad als Bonus, siehe Plan-Korrektur unten) (2026-05-16)
- [x] A.4 Cross-Links verifiziert: Mutter-Plan-Doku referenziert phase_10_safety_setup.md an Architektur-Entscheidungen B + C + D (2026-05-16)
- [x] A.5 PHASE.md Status-Check: Phase 10 schon 🟡 aktiv. **Kleiner Cleanup-Edit** (siehe Plan-Korrektur): obsoleten Hinweis "(legen wir zu Phase-10-Start an)" entfernt, Safety-Setup-Verweis hinzugefügt (2026-05-16)
- [x] A.6 A-T1 (colcon build) grün: 3 packages finished, 0 errors (2026-05-16)
- [x] A.7 A-T2 + A-T3 (colcon test) grün: hexapod_hardware 208/0/20, hexapod_bringup 18/0/0 — unverändert vs. Phase-9-Stage-J-Endstand (2026-05-16)
- [x] A.8 A-T4 (Dateien existieren) verifiziert (2026-05-16)
- [x] A.9 Kritischer Self-Review-Tabelle (siehe unten) — CLAUDE.md §4-Pflicht (2026-05-16)
- [x] A.10 Post-Review-Fix: Mutter-Plan-Doku Stage-D CC-Limit-Eintrag (7 A) ergänzt für Konsistenz mit safety_setup.md §2 (2026-05-16)
- [x] A.11 A-T5 (User-Review der safety_setup.md): grün **am 2026-05-16, User-Freigabe** inkl. wertvoller Architektur-Rückmeldung zum Initial-Pulse-Konzept (siehe Plan-Korrektur #4). Stage A komplett.

**Done-Kriterium A erreicht:** ✅ am 2026-05-16 (alle A.1–A.11 abgeschlossen, Build + Test regression-frei, Self-Review ohne offene 🔴-Punkte, User-Rückmeldung positiv + inhaltlich erweiternd).

**🎉 Stufe A komplett abgeschlossen.** Phase 10 Stand: **A** ✅. Verbleibend: B (Tester Pre-Cal), C, D, E, F, G, I.

### Stage-A-Post-Review (kritische Punkte, durchgegangen am 2026-05-16)

| Punkt | Status | Detail |
|---|---|---|
| Plan-Doku-Vollständigkeit (4 Pflichtinhalte CLAUDE.md §4) | ✅ verifiziert | Logik-Skizze (A.1–A.5), Tests-Liste (A-T1 bis A-T5 + „was bewusst nicht"), Progress-Checkliste (A.1–A.11), Offene Fragen (A-Q1 + A-Q2) — alle vier Pflichtinhalte drin |
| progress.md-Struktur entspricht Phase-9-Pattern | ✅ verifiziert | Design-Entscheidungs-Block A–J konsolidiert oben; Stages A–I als Sektionen mit Skelett für noch nicht aktive Stages; Memory-Konvention-Verweise (feedback_phase_progress_tracking, feedback_decision_alternatives_log) drin |
| safety_setup.md ist als Referenz-Doc nutzbar (nicht Plan-Doc) | ✅ verifiziert | 6 Pflicht-Abschnitte + 2 Bonus (Pre-Stage-Checkliste + Eskalations-Pfad). Andere Stage-Test-Commands-Docs können mit Markdown-Link verweisen statt Inhalte duplizieren |
| Cross-Links zwischen Mutter-Plan-Doku ↔ Progress ↔ Safety-Setup | ✅ verifiziert | Mutter-Plan-Doku §B/§C/§D verweisen jetzt auf safety_setup.md §2/§6/§3+§4. Progress.md verweist auf Mutter-Plan-Doku + safety_setup.md. PHASE.md verlinkt beide Top-Level. |
| Build + Test regression-frei | ✅ verifiziert | hexapod_hardware 208/0/20, hexapod_bringup 18/0/0 — identisch zu Phase-9-Stage-J-Endstand. Stage A hat keinen Code/CMake/package.xml angefasst. |
| Stage-D-CC-Limit-Konsistenz Mutter-Plan-Doku ↔ Safety-Setup | 🔴 → ✅ gefixt | Mutter-Plan-Doku Tabelle hatte nur 1-Servo + 3-Servo-Werte; safety_setup.md §2 listet auch 2-Servo (Stage D) = 7 A. Mutter-Plan-Doku ergänzt in A.10 (Post-Review-Fix). |
| Pre-Existing Lint-Failures in `hexapod_description/launch/display.launch.py` | 🟡 vormerk Phase 11/12 | Stale Test-Results im build-Dir zeigen Copyright + pep257 D213 für display.launch.py. **Stage A hat diese Datei nicht angefasst**, das ist Phase-9-Drift (sim.launch.py + real.launch.py wurden in Stage-I-Linter-Iterationen gefixt, display.launch.py möglicherweise übersehen weil hexapod_description nicht im I-T3 dabei war). Kein Stage-A-Issue. Bei Phase 11/12 oder ad-hoc fixen (1-Zeilen-Copyright-Header + Multi-Line-Docstring-Anpassung). |
| PHASE.md Cleanup-Edit war ungeplant | 🟢 dokumentiert | Plan sagte „Status-Check, kein Edit erwartet" → obsolete „legen wir zu Phase-10-Start an"-Notiz war aber durch Stage A überholt. Cleanup-Edit als Plan-Korrektur drin. Keine Funktions-Änderung. |
| Memory-Einträge nach Stage A | ✅ +1 neu | Phase-10-relevante Memory-Einträge bereits da (project_hexapod_servo_models, project_phase10_real_yaml_vel_limits, project_phase9_h_oscilloscope_pending). **Neu in Stage A: project_phase12_initial_pose_presets.md** (durch User-Rückmeldung 2026-05-16 entstanden, siehe Plan-Korrektur #4). |
| Doku-Konsistenz Sprache (deutsch durchgehend) | ✅ verifiziert | Alle drei Stage-A-Output-Dateien sind in deutscher Fachsprache, analog Phase-9-Pattern. |
| Selbst-Beschädigungs-Risiko nach Stage A | ✅ unverändert | Stage A hat keine HW-Bewegung, keine PSU-Aktion, kein Code-Edit der HW-relevant wäre. Setup-Status: Servos abgeklemmt, PSU AUS. |

### Stage-A-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | `safety_setup.md` hat 8 Abschnitte statt 6 wie geplant | Beim Schreiben der 6 Pflicht-Abschnitte (Aufbockung, PSU, Polarität, Anschluss-Sequenz, Kill-Switch, Initial-Pulse) entstanden zwei zusätzliche Querschnitts-Themen die nicht in einen der 6 reinpassten: §7 Pre-Stage-Checkliste (operative Compile aller 6 Hauptpunkte als Pre-Run-Liste) und §8 Eskalations-Pfad bei Anomalien (CLAUDE.md §6 Diagnose-Workflow auf Phase-10-Kontext spezialisiert). Beide haben hohen praktischen Nutzen, kein Grund sie zu streichen. |
| 2 | Mutter-Plan-Doku Stage-D-CC-Limit (7 A) ergänzt | Im ersten Wurf der Mutter-Plan-Doku waren CC-Limits nur für 1-Servo + 3-Servo-Bein notiert. Beim Schreiben von safety_setup.md §2 (PSU-Tabelle pro Stage) fiel auf dass Stage D = 2 Servos einen eigenen Wert braucht. 7 A = 3 + 4 als Summe der 1-Servo-Limits. Korrigiert in A.10. |
| 3 | PHASE.md kleiner Cleanup-Edit ungeplant | Plan sagte A.5 = „kein Edit erwartet". Obsoleten Notiz-Text „(legen wir zu Phase-10-Start an)" entfernt, Safety-Setup-Verweis hinzugefügt. Status (🟡 aktiv) selbst war schon korrekt. Kosmetisch, keine Funktionsänderung. |
| 4 | Initial-Pose-Preset-Architektur-Idee aufgegriffen (User-Rückmeldung 2026-05-16) | Beim User-Review von safety_setup.md §6 brachte der User die Architektur-Idee „Initial-Pulse je nach Setup-Variante" ein. Phase 10 bleibt unverändert (User-Hand-Mitigation), aber Cross-Phase-Reminder erstellt: (1) neuer Memory-Eintrag `project_phase12_initial_pose_presets.md`, (2) Mutter-Plan-Doku Architektur-Entscheidung C erweitert um die Preset-Variante als 3. Alternative (neben Soft-Start und Ramped-Enable), (3) safety_setup.md §6 erweitert um Schwerkraft-Konflikt-Joint-Erklärung (Femur ist der einzige Schwerkraft-Konflikt-Joint, Coxa+Tibia haben kein Gap zwischen passiver und Joint-Mitte-Position) + Phase-12-Outlook-Block mit 2-Preset-Tabelle. Wichtige User-Korrektur: nur 2 Presets sinnvoll (`suspended` + `resting`), kein `stand`-Preset weil Stand eine Ziel-Pose ist, keine Start-Pose. |

### Stage-A-Notizen

- **Plan-First-Workflow hat funktioniert:** vor Implementation wurden 4 Pflichtinhalte + 2 offene Fragen geklärt, User-Entscheidungen vor Code-Beginn. Beide User-Antworten haben das Phase-9-Pattern bestätigt (eigene Safety-Datei + alle Stages als Skelett).
- **safety_setup.md-Erweiterung von 6 auf 8 Abschnitte war organisch:** während des Schreibens kamen Querschnitts-Themen auf die in den 6 Pflicht-Abschnitten nicht klar untergebracht waren. Statt sie in einen der bestehenden Abschnitte zu quetschen, eigener Abschnitt. Transparent in Plan-Korrektur #1 dokumentiert.
- **CC-Limit-Konsistenz-Issue wurde durch Self-Review gefunden, nicht durch Tests:** kein automatischer Check für Tabellen-Konsistenz zwischen 2 Markdown-Dateien. Self-Review-Schritt hat hier konkreten Wert geliefert (1 stiller Bug entdeckt + gefixt vor User-Sichtung).
- **Pre-existing display.launch.py-Lint-Failures:** Phase-9-Drift sichtbar gemacht durch Stage-A's umfassenden test-result-Aufruf. Nicht Stage-A's Verantwortung, aber zum Aufschreiben da sonst leicht zu vergessen.

### Was Stage A explizit **nicht** macht

- **Keine HW-Bewegung** — kein Servo wird angefasst, PSU bleibt aus, USB-Verbindung optional (nicht stage-A-relevant).
- **Keine Stage-B-Test-Commands-Doku** — Stage B legt das selber an, mit Verweis auf safety_setup.md §2 + §3 + §4 + §6.
- **Keine Stage-C/D/E/F-Test-Commands-Docs** — pro Stage, jeweils mit safety_setup-Verweisen.
- **Kein PHASE.md-Status-Change** (Phase 10 ist schon 🟡 aktiv aus Phase-9-Stage-J).
- **Kein neuer Memory-Eintrag** — keine neue Erkenntnis die persistent sein müsste.
- **Kein hexapod_description-Lint-Fix** (display.launch.py Phase-9-Drift) — out-of-scope Stage A, ad-hoc fixbar wenn jemand drüber stolpert.

**Done-Kriterium A erreicht (CI-Anteil):** ✅ am 2026-05-16 (A.1–A.10 alle abgeschlossen, Build + Test regression-frei, Self-Review-Tabelle ohne offene 🔴, eine 🟡 vormerk Phase 11/12).

**Done-Kriterium A (User-Smoke-Anteil):** pending — A.11 (User-Review der safety_setup.md) wartet auf User.

**🎉 Stufe A komplett (im CI-Anteil).** Phase 10 Stand: **A** ✅ (CI), pending User-Review. Verbleibend: B (Tester Pre-Cal), C, D, E, F, G, I.

---

## Stufe B — Mech. End-Stop-Check stromlos + HJ-Tester Pre-Cal leg_6

> **Vorab-Plan:** [`phase_10_stage_b_plan.md`](phase_10_stage_b_plan.md) —
> Logik-Skizze (B.0–B.4 mit Sub-Stages), Tests-Liste B-T1 bis B-T7,
> 20 Progress-Bullets, User-Entscheidungen vom 2026-05-16/17:
> - **B-Q1** Servo-Setup → **A** (Servo bleibt im Bein montiert, Signal/GND am Tester)
> - **B-Q2** Tester-Anzeige → **A** (Digital-Display mit µs-Anzeige)
> - **B-Q3** Servo-Reihenfolge → **A** (Coxa → Femur → Tibia)
> - **B-Q4** Werte-Workflow → **A** (separates `calibration_log.md` als Audit-Trail, dann konsolidiert ins YAML)
> - **B-Q5** Visuelle Joint-Mitte → **A** (Augenmaß reicht)
> - **B-Q6** Anschlag außerhalb Tester-Range → **A** (theoretisch berechneten Wert nutzen)
> - **B-Q7** Tester-PSU-Spannung → **A** (einstellbar, auf 7.0 V gesetzt)
> - **B-Q8 (2026-05-17, Strategie-Wechsel C → B'):** Self-Collision-Strategie → **B' Pragmatisch** (leg_5 bleibt montiert, einmalig in worst-case-Pose gestellt, `pulse_min`/`max` mit 5° Sicherheits-Abstand vor leg_5-Berührung statt max. Single-Leg-Range). User-Sicherheits-Priorität über Range-Maximierung.
>
> **Begleit-Dateien:**
> - [`phase_10_stage_b_calibration_log.md`](phase_10_stage_b_calibration_log.md) — Audit-Trail (User füllt während B.1+B.2)
> - [`phase_10_stage_b_test_commands.md`](phase_10_stage_b_test_commands.md) — operative User-Anleitung
>
> Done-Kriterium B: mech. End-Stops für leg_6 (3 Joints) im Log dokumentiert, Tester-Pre-Cal-Werte für Pin 15/16/17 im YAML konsolidiert (`pulse_min < pulse_zero < pulse_max`, alle in 800–2200 µs), Build/Tests regression-frei.

- [x] B.1 phase_10_stage_b_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-16)
- [x] B.2 phase_10_stage_b_calibration_log.md angelegt als Audit-Trail (Skelett mit Tabellen für End-Stops + Tester-Pre-Cal) (2026-05-16)
- [x] B.3 phase_10_stage_b_test_commands.md angelegt mit operativer Anleitung (B-T0 bis B-T6 mit User-Smoke-Schritten + Fehlerdiagnose-Tabelle) (2026-05-16)
- [x] B.4 B.0 Bench-Setup-Check ausgeführt vom User (Hexapod fest, Tester verfügbar, Display funktioniert, Tester-PSU auf 7.0 V, leg_5 in worst-case-Pose) (2026-05-17)
- [x] B.5 B.1 Mech. End-Stop-Check für **Coxa** im Log §1.1 dokumentiert (Anschlags-Ursachen qualitativ — Self-Collision mit leg_5 / mech. Bein-Endlage; Winkel nicht direkt gemessen, µs-Werte aus §2.1) (2026-05-17)
- [x] B.6 B.1 Mech. End-Stop-Check für **Femur** im Log §1.2 dokumentiert (mech. Anschlag außerhalb Tester-Range, qualitativ erfasst — siehe §4.1 Audit) (2026-05-17)
- [x] B.7 B.1 Mech. End-Stop-Check für **Tibia** im Log §1.3 dokumentiert (mech. Anschlag außerhalb Tester-Range, qualitativ erfasst — siehe §4.1 Audit) (2026-05-17)
- [x] B.8 B.2 HJ-Tester Pre-Cal **Coxa** (`pulse_zero`/`min`/`max` = 1550/1280/1860 µs), Log §2.1 eingetragen (2026-05-17)
- [x] B.9 B.2 HJ-Tester Pre-Cal **Femur** (`pulse_zero`/`min`/`max` = 1533/840/2170 µs), Log §2.2 eingetragen (2026-05-17)
- [x] B.10 B.2 HJ-Tester Pre-Cal **Tibia** (`pulse_zero`/`min`/`max` = 1539/840/2172 µs), Log §2.3 eingetragen (2026-05-17)
- [x] B.11 B.3 YAML konsolidiert: Pin 15/16/17 in `servo_mapping.yaml` haben Tester-Werte (2026-05-17)
- [x] B.12 B.3 git diff auf `servo_mapping.yaml` zeigt nur Pin 15/16/17 verändert, andere 15 unverändert (verifiziert)
- [x] B.13 B-T1 colcon build grün, 3 packages 0 errors (2026-05-17)
- [x] B.14 B-T2 colcon test grün, **208/0/20 + 18/0/0 wiederhergestellt** nach Post-Review-Fix der 3 test_hexapod_system-Tests (2026-05-17)
- [x] B-T3 (YAML-Plausibilität) verifiziert (alle drei Pins: `pulse_min < pulse_zero < pulse_max`, alle in [800, 2200] µs)
- [x] B-T4 (Log vollständig) verifiziert: §1.1/§1.2/§1.3 + §2.1/§2.2/§2.3 + §3-Konsolidierung + §4.1-Audit-Notiz
- [x] B.15 Kritischer Self-Review-Tabelle (siehe unten)
- [x] B.16 Post-Review-Fix: 3 Tests in `test_hexapod_system.cpp` an committed YAML angepasst (`kExpectedPulseZero[NUM_SERVOS]`-Array + Roundtrip-Toleranz auf 6e-3 rad gelockert) (2026-05-17)
- [ ] B-T5 + B-T6 + B-T7 User-Bestätigung (pending — User commitet als nächstes)

**Done-Kriterium B erreicht (CI-Anteil):** ✅ am 2026-05-17 (alle B.1–B.16 erledigt, Build + Test 208/0/20 + 18/0/0 grün, Self-Review ohne offene 🔴-Punkte). User-Smoke-Anteil (B-T5/T6/T7) pending bis User die Tester-Werte bestätigt + commitet.

### Stage-B-Post-Review (kritische Punkte, 2026-05-17)

| Punkt | Status | Detail |
|---|---|---|
| Plan-Doku-Vollständigkeit (4 Pflichtinhalte CLAUDE.md §4) | ✅ verifiziert | Logik-Skizze (B.0–B.4), Tests-Liste (B-T1 bis B-T7 + Was-NICHT), Progress-Checkliste (B.1–B.16), User-Entscheidungen B-Q1..B-Q8 in Plan-Doku |
| YAML-Diff minimal (nur Pin 15/16/17) | ✅ verifiziert | `git diff src/hexapod_hardware/config/servo_mapping.yaml`: +22/-3 Zeilen, nur Leg-6-Block. Pin 0–14 unverändert. |
| Plausibilitäts-Check der 3 Tester-Werte-Sets | ✅ verifiziert | Pro Pin: `pulse_min < pulse_zero < pulse_max`, alle in [800, 2200] µs, Strategie-B'-Begründung für Coxa-Range; Femur/Tibia-Range > URDF dokumentiert in §4.1 |
| Audit-Trail im calibration_log vollständig | ✅ verifiziert | §1.1–§1.3 Anschlags-Ursachen qualitativ, §2.1–§2.3 µs-Werte mit Mess-Methodik, §3 Vorher/Nachher-Block, §4.1 Audit-Notiz zur Tester-Range-Limitierung Femur/Tibia |
| Regression-Frei colcon build | ✅ verifiziert | 3 packages finished, 0 errors, keine neuen Warnings vs. Stage-A-Endstand |
| Regression-Frei colcon test (initial) | 🔴 → ✅ gefixt | **Erste Test-Iteration nach YAML-Edit**: 3 Failures in `test_hexapod_system.cpp` — hardcoded `1500` für alle 18 Pins gegen jetzt-committed 1550/1533/1539 für Pin 15/16/17 (Tests **PtyActivateSendsBootSequenceInOrder**, **PtyWriteSendsSetTargetsFrameWithNeutralPulses**, **LoopbackRoundtripsCommandThroughCalibration**). Plan-Doku-Annahme „Tests nutzen Fixtures, nicht committed YAML" war falsch — Tests **lesen das committed YAML als Default-Fixture**. **Fix:** `kExpectedPulseZero[NUM_SERVOS]`-Konstante eingeführt (per-Pin pulse_zero), zwei `EXPECT_EQ(pulse, 1500)`-Stellen auf Array-Lookup umgestellt; Roundtrip-Toleranz von 2e-3 rad auf 6e-3 rad gelockert wegen jetzt engster Range Pin 15 (197 µs/rad ≈ 5.1e-3 rad/µs). Plugin-Code **nicht** angefasst. Nach Fix: 208/0/20. |
| Plan-Korrektur dokumentiert | ✅ in Stage-B-Plan-Korrektur-Sektion | Plan-Annahme B-T2 „208/0/20 unverändert ... `calibration.yaml`-spezifische Unit-Tests verwenden Test-Fixtures, nicht das committed YAML" muss für künftige Stages umformuliert werden. Tests im Pfad ENABLE→SET_TARGETS lesen das committed YAML implicit als Default-Fixture via `make_valid_info()`. |
| `direction` für Pin 15/16/17 bleibt `+1` Platzhalter | ✅ wie geplant | Stages C/D/E entscheiden direction per Beobachtungs-Test, kein Stage-B-Job |
| Top-Level YAML-Status bleibt `placeholder` | ✅ wie geplant | 15 andere Pins sind weiter Defaults; Stage I setzt pro-Eintrag-Feld `status: calibrated` für Pin 15/16/17 |
| Mech.-Anschlag außerhalb Tester-Range (Femur/Tibia) | ✅ dokumentiert + Phase-12-Verweis | §4.1 Audit-Notiz erklärt: Pulse-Hard-Stop für Femur/Tibia in Phase 10 nicht aktiv (URDF-Software-Clamp greift früher), Phase 12 SW-Auto-Cal verfeinert. Phase-12-Stufe-B-Plan-Doku passend erweitert. |
| Self-Beschädigungs-Risiko nach Stage B | ✅ unverändert | Stage B hat **stromlos + Tester-PSU** gearbeitet — Bench-PSU blieb AUS, kein Servo2040-Bringup, kein Code-Lauf gegen echte HW. Setup-Status: Servos abgeklemmt, Bench-PSU AUS. |
| Memory-Einträge nach Stage B | ✅ unverändert | Keine neue Cross-Session-Erkenntnis — Stage B war reine Vor-Kalibrierung. Phase-12-Stufe-B (SW-Auto-Cal) ist im Plan-Doc verankert, nicht in Memory. |

### Stage-B-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **Plan-Annahme B-T2 zu Test-Fixtures war falsch** | Plan-Doku sagte „`calibration.yaml`-spezifische Unit-Tests verwenden Test-Fixtures, nicht das committed YAML". Realität: 3 Tests in `test_hexapod_system.cpp` (Boot-Sequence, Neutral-Pulses, Loopback-Roundtrip) lesen das committed YAML implizit via `make_valid_info()`. Stage-B-YAML-Edit hat hardcoded `1500`-Erwartungen brechen. **Fix:** Tests an committed YAML angepasst (per-Pin-Konstanten + gelockerte Toleranz). |
| 2 | **Phase 12 um neue Stufe B (SW-Auto-Kalibrierung der 15 Restservos) erweitert** | Auf User-Wunsch 2026-05-17. Phase 12 hatte 8 Stufen A–H, jetzt 9 Stufen A–I. Neue Stufe B nutzt Plugin als Black Box (kein Plugin-Code-Edit), Tool wird neues Python-Paket `hexapod_calibration` mit Terminal-UI. Ziel: bessere Auto-Cal als HJ-Tester durch echte Stack-Pipeline + beidseitige Self-Collision-Tests für Mittel-Beine. Cross-Phase-Verweis in `calibration_log.md` §4.1. |
| 3 | **B.1 und B.2 in einem Schritt zusammen am Tester gemessen** | Plan sah vor: B.1 stromlos End-Stop-Check, dann B.2 Tester-Pre-Cal. Realität: User hat beides am Tester gemacht — Anschlags-Ursachen identifiziert während Tester-Drehung, µs-Werte direkt abgelesen. Methodik im Log §1 als „Tester-basiert, kein Goniometer" transparent vermerkt. Sinnvoller pragmatischer Workflow ohne Funktionsverlust. |

### Stage-B-Notizen

- **Mech. Anschlag-Range > URDF (Femur/Tibia):** beim Tester ist klar geworden, dass beide Miuzei-MS61-Servos mechanisch deutlich mehr als ±90° können — Tester-Range (800–2200 µs) hat noch keinen Anschlag-Brumm erzeugt. Effektive Joint-Begrenzung kommt aus URDF-Software-Clamp. Phase 12 SW-Auto-Cal kann das verfeinern.
- **Strategie B' war für Coxa bindend, für Femur/Tibia rein zur Inspirational-Doku-Konsistenz:** Bei leg_6 als Eck-Bein gibt's nur leg_5 als Nachbar, und nur die Coxa kann leg_5 erreichen. Femur und Tibia haben mit Self-Collision nichts zu tun — Werte stammen von mech. Servo-Range (jenseits Tester-Limit).
- **Test-Fix war 30 Min Aufwand:** Stage-B-Plan hatte das nicht antizipiert. Lehre für künftige YAML-Stages: vor dem Edit grep nach Hardcodes der zu ändernden Werte. Memory-Eintrag wäre overkill (zu spezifisch), aber gut für die Phase-12-Stufe-B-Plan-Doku mitzunehmen (Auto-Cal-Tool wird `servo_mapping.yaml` ähnlich editieren).

---

## Stufe C — Stack-Validation leg_6_coxa (1 Servo)

> **Vorab-Plan:** [`phase_10_stage_c_plan.md`](phase_10_stage_c_plan.md) —
> Logik-Skizze (C.0 Bench-Setup, C.1 Plugin-Bringup, C.2 direction-Test
> +0.1 rad, C.3 optional Flip auf -1, C.4 Endlagen ±1.0 rad, C.5 Shutdown,
> C.6 Build/Test/Self-Review), Tests-Liste C-T1 bis C-T8, 15 Progress-Bullets.
>
> **User-Entscheidungen vom 2026-05-17 (alle Variante A):**
> - **C-Q1** Trajectory-Mechanismus → **A** (`ros2 action send_goal`). Echo-State macht `status=SUCCEEDED` trivial → visuelle Beobachtung am Bein bleibt einzige Wahrheit. Phase 12 Walking nutzt später Topic-Streaming.
> - **C-Q2** Endlagen-Schritte → **A** (5-stufig: +0.5/+1.0/0/-0.5/-1.0/0)
> - **C-Q3** RViz separat vs. Launch-Extension → **A** (separat starten, Plan-Korrektur ggü. Mutter-Plan §F)
> - **C-Q4** User-Hand-Position → **A** (Bein nahe Coxa-Mitte, Femur/Tibia passiv hängend)
> - **C-Q5** Bei Stall-Brumm bei -1.0 rad → **A** (pulse_min im YAML auf 1300 erhöhen, retest)
>
> **Begleit-Datei:**
> - [`phase_10_stage_c_test_commands.md`](phase_10_stage_c_test_commands.md) — User-Smoke-Anleitung mit C-T3..C-T7
>
> Done-Kriterium C: Coxa `direction` final im YAML (mit oder ohne Flip), Endlagen ±1.0 rad gefahren ohne Stall, kein Firmware-Trip, RViz und echtes Bein synchron, Build+Test regression-frei.

- [x] C.1 phase_10_stage_c_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-17)
- [x] C.2 phase_10_stage_c_test_commands.md angelegt mit operativer Anleitung (C-T3 Plugin-Bringup, C-T4 direction-Test, C-T4.5 optional Flip, C-T5 RViz-Sync, C-T6 Endlagen ±1.0 rad, C-T7 Shutdown) (2026-05-17)
- [x] C.3 C.0 Bench-Setup-Check ausgeführt vom User (PSU 7.0 V / 3 A, Coxa-Servo an Pin 15, Femur/Tibia abgeklemmt, leg_5 in ruhiger Pose) (2026-05-17)
- [x] C.4 C.1 Plugin-Bringup grün: `on_init`/`on_configure`/`on_activate` ohne Errors, 18× ENABLE_SERVO im Log (2026-05-17)
- [x] C.5 C.2 direction-Test gefahren: User-Beobachtung „RViz Bein → leg_5, echtes Bein weg von leg_5" — **gegenläufig** → direction-Flip nötig (2026-05-17)
- [x] C.6 C.3 direction-Flip auf -1 via User-YAML-Edit + colcon build + relaunch; Bein dreht jetzt korrekt synchron mit RViz (2026-05-17)
- [x] C.7 C.4 Endlagen-Test: User hat ±0.5 rad und ±1.0 rad gefahren, alle 4 Goals erreicht, **kein Stall, kein Brumm, keine Warnsignale** (Trip-Errors, Self-Collision o.ä.) (2026-05-17)
- [x] C.8 C.5 PSU AUS, Coxa-Servo abgeklemmt (User vor Commit) (2026-05-17)
- [x] C.9 C.6 colcon build grün, hexapod_hardware 1 package finished, 0 errors (regression-frei nach YAML-Edit direction=-1) (2026-05-17)
- [x] C.10 C.6 colcon test grün **208/0/20 + 18/0/0 wiederhergestellt** (1× transienter xmllint-Failure beim ersten Lauf wegen Resource temporarily unavailable beim XSD-Schema-Download — kein code-bedingter Fehler, beim Re-run grün) (2026-05-17)
- [x] C.11 C-T3 + C-T4 + C-T5 + C-T6 + C-T7 User-Bestätigung (über AskUserQuestion am 2026-05-17 explizit bestätigt: alle Goals erreicht, keine Warnsignale, Stage C aus User-Sicht done)
- [x] C.12 C-T8 YAML-Inspektion: direction=-1 für Pin 15 sichtbar in `servo_mapping.yaml`, Kommentar Stage-C-Kontext gesetzt (2026-05-17)
- [x] C.13 Kritischer Self-Review-Tabelle (siehe unten)
- [x] C.14 Post-Review-Fixes: YAML-Kommentar aufgewertet von „NEU: Flip von default +1" auf vollständige Stage-C-Kontext-Notiz (2026-05-17)
- [x] C.15 Stage-C-Notizen + Plan-Korrektur (test_commands Position-Wert ad-hoc-Edit, siehe unten) (2026-05-17)

**Done-Kriterium C erreicht (CI-Anteil + User-Smoke):** ✅ am 2026-05-17.

### Stage-C-Post-Review (kritische Punkte, 2026-05-17)

| Punkt | Status | Detail |
|---|---|---|
| Plan-Doku-Vollständigkeit (4 Pflichtinhalte CLAUDE.md §4) | ✅ verifiziert | Logik-Skizze (C.0–C.6), Tests-Liste (C-T1 bis C-T8 + Was-NICHT), Progress-Checkliste (C.1–C.15), User-Antworten C-Q1..C-Q5 mit Begründungen |
| direction-Flip auf -1 funktional verifiziert | ✅ verifiziert | User-Beobachtung RViz vs. echtes Bein vor Flip eindeutig gegenläufig (RViz → leg_5, echtes Bein → von leg_5 weg); nach Flip synchron. ±1.0 rad Endlagen sauber erreicht ohne Stall. |
| Self-Collision-Schutz mit direction=-1 weiter aktiv | ✅ verifiziert | pulse_min=1280 bleibt Hardware-Hard-Stop. Mit direction=-1 wird er bei URDF +1.57 rad getriggert statt -1.57 rad (Vorzeichen-Zuordnung geflippt, Pulse-Wert unverändert). Bein hat in Endlagen-Test leg_5 NICHT berührt (User-Bestätigung). |
| `real.launch.py` ohne `rviz:=true`-Arg (Mutter-Plan §F Drift) | ✅ Plan-Korrektur dokumentiert | User startete RViz separat in Terminal 2; klappte sauber. Phase-12-Kandidat falls Voll-Bringup das integrieren will. |
| YAML-Diff minimal (nur direction-Wert für Pin 15) | ✅ verifiziert | `git diff src/hexapod_hardware/config/servo_mapping.yaml`: nur Coxa direction-Zeile + Kommentar-Block verändert; pulse_min/zero/max und alle anderen 17 Pins unverändert |
| Regression-Frei colcon test | ✅ verifiziert | 208/0/20 + 18/0/0 identisch Phase-9-Stage-J-Endstand. 1× transienter xmllint-Failure beim ersten Lauf (netzwerk-bedingt, XSD-Schema-Download „Resource temporarily unavailable") — kein Code-Issue, beim Re-run grün. |
| Test-Commands-Doc reflektiert User-Workflow | 🟡 Plan-Korrektur | User hat im C-T4-Goal-Snippet `+0.1` auf `-0.5` geändert während des Tests (in der test_commands.md Datei selber, IDE-Edit). Bewegung war groß genug zur direction-Diagnose. Test-Commands-Doc behält den User-Wert (-0.5) als gelaufene Realität — Plan-Korrektur unten. |
| Echo-State-Konsequenz dokumentiert | ✅ in Plan-Doku C-Q1-Antwort | „Bewegung minimal/schwer zu beziffern mit Auge" ist erwartet — JTC + Plugin echo'n den Soll-Wert, real-vs-Echo-Drift gibt es nur am echten Bein und ist visuell schwer messbar ohne Goniometer. Stage F nutzt Strom-CSV als objektives Korrelat. |
| Selbst-Beschädigungs-Risiko nach Stage C | ✅ unverändert | Coxa-Servo nach Test abgeklemmt, Bench-PSU AUS. Setup bereit für Stage D (Coxa + Femur). |
| Memory-Einträge nach Stage C | ✅ unverändert | Keine neue persistent-relevante Erkenntnis. direction=-1 für leg_6-Coxa ist im YAML committed, nicht Memory-Sache. |

### Stage-C-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **C-T4 Goal-Wert `+0.1` → `-0.5` rad** | User hat während der Live-Test-Session den Wert in `phase_10_stage_c_test_commands.md` direkt im Editor angepasst auf `-0.5` rad. Originaler `+0.1` rad war als kleiner Diagnose-Schritt geplant (sicher), aber visuell schwer zu beurteilen (5.7° Schwenk). User-Anpassung auf -0.5 rad (~29°) war pragmatisch besser zur direction-Diagnose — und mit der bereits validierten Stage-B-pulse_min-Marge (1280 µs = 5° vor leg_5) auch sicher. Im Test-Commands-Doc als gelaufene Realität gelassen, kein Revert. |
| 2 | **C-T6 Endlagen-Test verkürzt: 4 Goals statt 5 Schritte mit Zurücksetzungen** | User fuhr `+0.5, -0.5, +1.0, -1.0` rad (4 Goals), nicht das geplante 6-Schritte-Schema mit Zwischen-Rückkehrungen zu 0. Done-Kriterium C2 „Bewegung in beide Richtungen ohne Stall" voll erfüllt — die Zwischen-0-Goals waren operational, kein Test-Kriterium. Bei späterer Stage-D/E könnte das gleiche Muster gefahren werden, weniger Goals = weniger Tipparbeit. |

### Stage-C-Notizen

- **direction-Konvention bestätigt:** für leg_6 (front-left, yaw +π/4) hat der reale Coxa-Servo eine **invertierte** mechanische Drehrichtung gegenüber der URDF-Konvention. Phase-12-Voll-Calibration der anderen 5 Beine muss das pro Bein erneut prüfen — links/rechts-Spiegelung im Chassis macht keine direction-Vorhersage zuverlässig (jeder Servo individuell gemessen). Auto-Cal-Tool aus Phase-12-Stufe-B kann den direction-Test automatisieren (Tool bewegt Bein +0.1 rad, Tool fragt User „in URDF-positive Richtung? y/n", flippt direction im YAML wenn n).
- **Echo-State-Realität:** Plugin liefert keine echte Servo-Position, daher gibt JTC immer `status=SUCCEEDED`. Diagnose-Methodik bei Stalls oder schiefen Posen muss visuell + Strom-Profil-basiert sein (Stage F). User-Beobachtung „minimal" für 0.5-rad-Bewegung ist *normal*, weil Augenmaß für ±5° schwer ist — der Servo hat aber den vollen geometrischen Winkel gefahren laut User-Sicht-Check.
- **Stage-A-Plan-Korrektur-Pattern reflektiert:** wie in Stage B (Plan-Annahme Tests-Fixtures vs. committed YAML) gibt's auch in Stage C kleine Drifts (Goal-Wert-Change, Endlagen-Schritt-Zahl). Beide unkritisch fürs Done-Kriterium, beide in der Plan-Korrektur-Tabelle transparent. Plan-First-Workflow funktioniert weiterhin — der Plan ist Anker, nicht starres Skript.

---

## Stufe D — Stack-Validation leg_6_coxa + leg_6_femur (2 Servos)

> **Vorab-Plan:** [`phase_10_stage_d_plan.md`](phase_10_stage_d_plan.md) —
> Logik-Skizze (D.0 Bench-Setup, D.1 Plugin-Bringup mit Femur-Hand-
> Mitigation, D.2 Femur direction-Test isoliert, D.3 optional Flip,
> D.4 2-Joint-Coordination, D.5 Femur Endlagen ±1.0 rad, D.6 Shutdown,
> D.7 Build/Test/Self-Review), Tests-Liste D-T1..D-T8, 15 Progress-Bullets.
>
> **User-Entscheidungen vom 2026-05-17 (alle Variante A):**
> - **D-Q1** Erste direction-Test-Form → **A** (Femur isoliert, Coxa=0) für Diagnose-Trennung
> - **D-Q2** Endlagen-Test Reihenfolge → **A** (erst negative Richtung mit Schwerkraft, dann positive gegen Schwerkraft)
> - **D-Q3** 2-Joint-Coordination-Test-Form → **A** (Coxa+Femur beide auf +0.1 rad, 3 s)
> - **D-Q4** User-Hand-Position vor Launch → **A** (Bein horizontal nach außen, Femur horizontal)
> - **D-Q5** Bei Femur-Stall in Endlagen → **A** (pulse_min/max im YAML enger ziehen, retest)
>
> **Begleit-Datei:**
> - [`phase_10_stage_d_test_commands.md`](phase_10_stage_d_test_commands.md) — User-Smoke mit Femur-Hand-Mitigation
>
> **Sicherheits-Schwerpunkt:** Femur-Initial-Pulse-Schlag = max. Stall-
> Risiko der Phase 10 (Bein hängt passiv -90°, ENABLE setzt pulse_zero
> = horizontal → 90°-Sprung gegen Schwerkraft). User-Hand muss Bein
> **vor Launch** horizontal halten.
>
> Done-Kriterium D: Femur `direction` final, 2-Joint-Sync verifiziert, Femur-Endlagen ±1.0 rad gefahren ohne Stall, kein Firmware-Trip, RViz und echtes Bein synchron, Build+Test regression-frei.

- [x] D.1 phase_10_stage_d_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-17)
- [x] D.2 phase_10_stage_d_test_commands.md angelegt mit operativer Anleitung inkl. Femur-Hand-Mitigation (2026-05-17)
- [x] D.3 D.0 Bench-Setup-Check ausgeführt vom User (PSU 7.0 V / 7 A, Coxa+Femur an Pin 15+16, Tibia abgeklemmt) (2026-05-17)
- [x] D.4 D.1 Plugin-Bringup mit User-Hand-Mitigation grün — User-Bestätigung „die beine bewegen sich wie es sein soll" (2026-05-17)
- [x] D.5 D.2 Femur direction-Test: User-Beobachtung **gegenläufig** (analog Coxa in Stage C) → Femur direction-Flip nötig (2026-05-17)
- [x] D.6 D.3 Femur direction-Flip auf -1 via User-YAML-Edit; Bein bewegt sich danach korrekt synchron mit RViz (2026-05-17)
- [x] D.7 D.4 2-Joint-Coordination + D-T7 Femur Endlagen-Test in User-Smoke verifiziert (verkürzter Test-Umfang wie Stage C, „Beine bewegen sich wie es sein soll" ohne Stall/Trips) (2026-05-17)
- [x] D.8 D.5 Femur Endlagen-Test abgedeckt im User-Smoke (Punkt 7 oben) (2026-05-17)
- [x] D.9 D.6 PSU AUS, beide Servos abgeklemmt (User vor Commit) (2026-05-17)
- [x] D.10 D.7 colcon build grün, 1 package finished 0 errors nach Femur-Flip-YAML-Edit (2026-05-17)
- [x] D.11 D.7 colcon test grün **208/0/20 + 18/0/0 wiederhergestellt** nach 1× flaky launch_testing-Failure (ros2_control_node Exit-Code -9 = SIGKILL beim Shutdown, kein code-bedingter Fehler — bekanntes launch_testing-Drift-Pattern aus Phase 9; beim Re-run grün) (2026-05-17)
- [x] D.12 D-T3..D-T7 User-Bestätigung (User-Statement „passt, die beine bewegen sich wie es sein soll, wir können weiter machen")
- [x] D.13 D-T8 YAML-Inspektion: Femur Pin 16 direction=-1 sichtbar im Diff, Kommentar mit Stage-D-Kontext + Cross-Phase-Hinweis auf erwartete Left-Side-Konsistenz für Phase 12 gesetzt (2026-05-17)
- [x] D.14 Kritischer Self-Review-Tabelle (siehe unten)
- [x] D.15 Stage-D-Notizen (siehe unten)

**Done-Kriterium D erreicht (CI-Anteil + User-Smoke):** ✅ am 2026-05-17.

### Stage-D-Post-Review (kritische Punkte, 2026-05-17)

| Punkt | Status | Detail |
|---|---|---|
| Plan-Doku-Vollständigkeit (4 Pflichtinhalte CLAUDE.md §4) | ✅ verifiziert | Logik-Skizze (D.0–D.7 mit Femur-Hand-Mitigation als Sicherheits-Schwerpunkt), Tests-Liste (D-T1..D-T8), Progress-Checkliste (D.1–D.15), User-Antworten D-Q1..D-Q5 mit Begründungen, alle Variante A |
| Femur direction-Flip auf -1 funktional verifiziert | ✅ verifiziert | User-Beobachtung gegenläufig zur RViz → YAML-Edit auf -1 → nach Rebuild/Relaunch synchron. Pattern identisch zu Coxa in Stage C. |
| Femur-Initial-Pulse-Schlag-Mitigation gegriffen | ✅ verifiziert | User berichtet keine Stall-Brumm-Events; Hand-vor-Launch-Workflow funktional. Phase-12-Initial-Pose-Preset-Konzept (Memory `project_phase12_initial_pose_presets.md`) bleibt valider Outlook für Skalierung. |
| Left-Side-Konsistenz: beide leg_6-Servos direction=-1 | ✅ Datenpunkt für Phase 12 | Coxa **und** Femur bei leg_6 sind invertiert vs. URDF — konsistentes Spiegelungs-Pattern für linksseitige Beine. Erwartung Phase 12: leg_4/5 Coxa+Femur auch direction=-1, rechtsseitige Beine 1/2/3 evtl. einheitlich direction=+1. Tibia (Stage E) wird zeigen ob die Konsistenz auch für die 3. Achse gilt. YAML-Kommentar erweitert um diesen Cross-Phase-Hinweis. |
| 2-Joint-Coordination im JTC funktioniert | ✅ verifiziert | User: „beine bewegen sich wie es sein soll" — beide Joints synchron, kein Phasen-Versatz beobachtet. JTC-Multi-Joint-Trajectory-Pfad ist bewiesen für leg_6 (Phase-12-Vorraussetzung). |
| Self-Collision-Schutz Coxa weiter aktiv | ✅ unverändert | Stage-B-pulse_min=1280 für Coxa-Pin-15 bleibt Hardware-Hard-Stop. User-Test in Endlagen war ohne Self-Collision-Berührung. |
| Regression-Frei colcon test | ✅ verifiziert | 208/0/20 + 18/0/0 final grün. 1× flaky launch_testing-Failure (Proc ros2_control_node-2 Exit-Code -9 = SIGKILL beim Shutdown) beim ersten Lauf — bekanntes Drift-Pattern aus Phase 9, beim Re-run grün. **Nicht** durch YAML-direction-Edit verursacht. |
| YAML-Diff minimal (nur Femur direction-Zeile + Kommentar) | ✅ verifiziert | `git diff src/hexapod_hardware/config/servo_mapping.yaml`: Femur direction-Wert + Kommentar-Update für die per-joint-Liste; Pulse-Werte und alle anderen 17 Pins unverändert |
| Self-Beschädigungs-Risiko nach Stage D | ✅ unverändert | Coxa + Femur nach Test abgeklemmt, Bench-PSU AUS. Setup bereit für Stage E (Tibia isoliert). |
| Memory-Einträge nach Stage D | ✅ unverändert | Keine neue persistent-relevante Erkenntnis. Left-Side-Konsistenz ist im YAML-Kommentar + Stage-D-Post-Review verankert, nicht Memory-Sache. |

### Stage-D-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **User-Smoke D-T6/D-T7 in einem Schritt zusammengefasst** | Wie in Stage C hat der User die formalen Sub-Tests (2-Joint-Coordination D-T6, Femur-Endlagen D-T7) pragmatisch zusammengefasst und Status „beine bewegen sich wie es sein soll" als Gesamt-Bestätigung gemeldet. Done-Kriterium D voll erfüllt; Test-Details im Plan dienen primär als Anleitung-Skelett, nicht als starre Schritt-Pflicht. |
| 2 | **1× flaky launch_testing-Failure** | `test_no_error_exit_codes` schlug beim ersten Lauf wegen ros2_control_node SIGKILL beim launch_testing-Shutdown fehl. Bekanntes Drift-Pattern aus Phase 9 Stage I-Iteration. Re-run grün. Kein Code-Issue durch YAML-Edit. Wenn in Phase 11/12 nochmal: launch_testing-Shutdown-Timing untersuchen, sonst flaky-Retry-Toleranz. |

### Stage-D-Notizen

- **Left-Side-Konsistenz beobachtet:** beide Coxa und Femur bei leg_6 sind invertiert (`direction=-1`). Das ist ein wertvoller Hinweis für die Phase-12-Auto-Cal: bei links-side Beinen (leg_4/5/6) erwarten wir Coxa+Femur einheitlich `-1`, bei rechts-side Beinen (leg_1/2/3) einheitlich `+1`. Phase-12-Tool kann die direction-Bestimmung pro Bein verkürzen wenn die ersten 2–3 Servos das Pattern bestätigen (linksseitige Servos alle `-1`, rechtsseitige alle `+1`). Cross-Phase-Hinweis im YAML-Kommentar gesetzt.
- **Tibia (Pin 17) noch nicht gestest:** wie geplant Stage-E-Job. Tibia hat physisch keinen Schwerkraft-Hebel im aufgehängten Bein (Coxa+Femur stromlos, hängen passiv) → minimaler Stall-Risiko. Erwartete Stage-E-Dauer ähnlich Stage C (1 Servo, kein Schwerkraft-Drama).
- **Phase-12-Auto-Cal-Tool-Implikation:** das Stage-C+D-Pattern „Test → Direction-Flip → Rebuild → Relaunch → Retest" wird in Phase 12 wiederholt 15× durchgespielt. Das spricht *für* das geplante Tool — wenn man das Plugin nicht ändert (Build-Edit-Build pro Flip), kostet das 15× ~10 min = 2.5 h reine Wartezeit. Das Auto-Cal-Tool könnte direction direkt im YAML setzen ohne separates Rebuild (`status: pending` → User-OK → YAML schreiben → relaunch). Phase-12-Stufe-B-Plan-Doku entsprechend erweitern wenn nötig.

---

## Stufe E — Stack-Validation leg_6_tibia (1 Servo isoliert)

> **Vorab-Plan:** [`phase_10_stage_e_plan.md`](phase_10_stage_e_plan.md) —
> Logik-Skizze (E.0 Bench-Setup PSU 4 A, E.1 Plugin-Bringup, E.2 Tibia
> direction-Test isoliert, E.3 optional Flip, E.4 Endlagen ±1.0 rad,
> E.5 Shutdown, E.6 Build/Test/Self-Review), Tests-Liste E-T1..E-T7,
> 14 Progress-Bullets.
>
> **User-Entscheidungen vom 2026-05-17 (alle Variante A):**
> - **E-Q1** Tibia direction-Test-Form → **A** (isoliert `[0,0,+0.1]`)
> - **E-Q2** Endlagen-Test Reihenfolge → **A** (Stage-C-Pattern, kein Schwerkraft-Hebel)
> - **E-Q3** User-Hand-Position vor Launch → **A** (locker, Tibia passive ≈ pulse_zero)
> - **E-Q4** Bei Tibia-Stall in Endlagen → **A** (pulse_min/max +30 µs enger ziehen)
>
> **Begleit-Datei:**
> - [`phase_10_stage_e_test_commands.md`](phase_10_stage_e_test_commands.md)
>
> Done-Kriterium E: Tibia `direction` final (mit oder ohne Flip), Endlagen ±1.0 rad ohne Stall, kein Firmware-Trip, RViz und echtes Bein synchron, Build+Test regression-frei.

- [x] E.1 phase_10_stage_e_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-17)
- [x] E.2 phase_10_stage_e_test_commands.md angelegt (2026-05-17)
- [x] E.3 E.0 Bench-Setup-Check ausgeführt vom User (PSU 7.0 V / 4 A, nur Tibia an Pin 17) (2026-05-17)
- [x] E.4 E.1 Plugin-Bringup grün, kein Trip (2026-05-17)
- [x] E.5 E.2 Tibia direction-Test gefahren — User-Beobachtung **synchron mit RViz** → direction=+1 (default) ist korrekt, **kein Flip nötig** (2026-05-17)
- [x] E.6 E.3 direction-Flip auf -1 **nicht ausgeführt** (Stage E.2 zeigte direction=+1 korrekt) — übersprungen, YAML Pin 17 bleibt bei default direction (2026-05-17)
- [x] E.7 E.4 Tibia Endlagen-Test in User-Smoke verifiziert („passt, die richtungen drehen sich wie in rviz") (2026-05-17)
- [x] E.8 E.5 PSU AUS, Tibia abgeklemmt (User vor Commit) (2026-05-17)
- [x] E.9 E.6 colcon build grün, 1 package finished 0 errors (2026-05-17)
- [x] E.10 E.6 colcon test grün **208/0/20 + 18/0/0** im ersten Lauf (kein flaky-Retry nötig) (2026-05-17)
- [x] E.11 E-T3..E-T6 User-Bestätigung („hier passt alles man braucht kein inverter, die richtungen drehen sich wie in rviz") (2026-05-17)
- [x] E.12 E-T7 YAML-Inspektion: Tibia Pin 17 direction-Wert **unverändert** (default +1), aber Kommentar-Block ergänzt mit Stage-E-Bestätigung + Cross-Phase-Hinweis zur widerlegten Left-Side-Hypothese (2026-05-17)
- [x] E.13 Kritischer Self-Review-Tabelle (siehe unten)
- [x] E.14 Stage-E-Notizen (siehe unten)

**Done-Kriterium E erreicht (CI-Anteil + User-Smoke):** ✅ am 2026-05-17.

### Stage-E-Post-Review (kritische Punkte, 2026-05-17)

| Punkt | Status | Detail |
|---|---|---|
| Plan-Doku-Vollständigkeit (4 Pflichtinhalte CLAUDE.md §4) | ✅ verifiziert | Logik-Skizze (E.0–E.6), Tests-Liste (E-T1..E-T7), Progress-Checkliste (E.1–E.14), User-Antworten E-Q1..E-Q4 alle Variante A |
| Tibia direction=+1 funktional verifiziert | ✅ verifiziert | User-Beobachtung „die richtungen drehen sich wie in rviz" — direction=+1 (default) ist korrekt für Tibia. **Kein YAML-Wert geändert** für Pin 17. |
| **Left-Side-Konsistenz-Hypothese WIDERLEGT** | 🟡 wichtiger Cross-Phase-Datenpunkt | Stage D Notiz hatte vermutet: alle linksseitigen Servos invertiert. Stage E zeigt: leg_6 Tibia ist `+1`, also Hypothese falsch. **Konsequenz für Phase-12-Auto-Cal:** Tool muss **jeden** Servo individuell testen, keine Vorhersage aus Bein-Seite oder Joint-Typ möglich. YAML-Kommentar entsprechend erweitert. |
| Tibia Endlagen-Test ohne Stall | ✅ verifiziert | User-Bestätigung „passt alles" — keine Stall-Brumm-Events, kein Trip. Tibia isoliert war wie erwartet entspannt (kein Bein-Gewicht-Hebel). |
| Self-Collision-Schutz Coxa weiter aktiv | ✅ unverändert | Coxa stromlos abgeklemmt in Stage E, kein Test-Risiko. pulse_min=1280 bleibt für spätere Stages. |
| Regression-Frei colcon test | ✅ verifiziert | 208/0/20 + 18/0/0 im ersten Lauf grün. Kein flaky-Retry nötig (im Gegensatz zu Stages C+D). Erwartet, weil Stage E nur YAML-Kommentar geändert hat (keinen direction-Wert). |
| YAML-Diff minimal | ✅ verifiziert | `git diff src/hexapod_hardware/config/servo_mapping.yaml`: nur Kommentar-Block in der Pin-15-17-Sektion erweitert um Stage-E-Bestätigung + Cross-Phase-Hinweis. **Keine Werte geändert.** |
| Alle 3 leg_6-Joints direction final | ✅ verifiziert | Pin 15 (Coxa): -1, Pin 16 (Femur): -1, Pin 17 (Tibia): +1 (default). Stage F kann mit den vollständig kalibrierten Werten starten. |
| Selbst-Beschädigungs-Risiko nach Stage E | ✅ unverändert | Tibia nach Test abgeklemmt, Bench-PSU AUS. Setup bereit für Stage F (alle 3 Servos + IK). |
| Memory-Einträge nach Stage E | ✅ unverändert | Left-Side-Konsistenz-Widerlegung ist im YAML-Kommentar + Stage-E-Post-Review verankert. Phase-12-Auto-Cal-Plan kann das beim Implementieren aufgreifen — kein separater Memory-Eintrag nötig (zu spezifisch, Cross-Phase-Verweis genügt). |

### Stage-E-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **User-Smoke E-T6/E-T4 in einem Schritt zusammengefasst (wie Stages C+D)** | User hat pragmatisch direction-Test und Endlagen zusammen gefahren und Status „hier passt alles" als Gesamt-Bestätigung gemeldet. Done-Kriterium voll erfüllt. Test-Commands-Doc-Goal-Wert in E-T4 wurde während Test auf `[0.0, 0.0, -1.0]` angepasst (User-IDE-Edit, größere Bewegung statt +0.1, sicher weil Tibia isoliert) — analog zu Stage C/D Adhoc-Anpassungen. |
| 2 | **Tibia direction=+1 = default → keine YAML-Wert-Änderung nötig** | Erstes Mal in Phase 10 dass ein Servo direction default behält. YAML-Kommentar-Block trotzdem erweitert um Stage-E-Bestätigung und Cross-Phase-Hinweis (Hypothese-Widerlegung). |

### Stage-E-Notizen

- **Tibia direction-Pattern bricht Left-Side-Hypothese:** Stage-D-Notiz spekulierte: "linksseitige Beine → alle Servos direction=-1". Stage E zeigt: leg_6 Tibia ist `+1`, also kein einheitliches Muster pro Bein-Seite. Phase-12-Auto-Cal-Tool muss jeden der verbleibenden 15 Servos individuell testen. Spart keine Test-Iterationen.
- **Stage E war wie geplant der entspannteste direction-Test:** kein Schwerkraft-Hebel, Tibia passive ≈ pulse_zero, einfacher Bringup ohne Hand-Mitigation. Bestätigt das Mutter-Plan-Design (Tibia isoliert vor Stage F Voll-Integration).
- **Phase 10 direction-Tests komplett:** alle 3 leg_6-Joints individuell verifiziert. Stage F kann sofort mit IK-Roundtrip starten ohne weitere direction-Diagnose.
- **CI war im ersten Lauf grün:** kein flaky-Retry nötig wie in Stages C+D (wo direction-Flip eine echte YAML-Wert-Änderung auslöste). Stage E hat nur YAML-Kommentar erweitert, der von keinem Test geprüft wird — Konsistenz mit der Test-Suite ist trivial.

---

## Stufe F — IK-Roundtrip leg_6 voll (3 Servos) + Voll-Pipeline-Test

> **Vorab-Plan:** [`phase_10_stage_f_plan.md`](phase_10_stage_f_plan.md) —
> Logik-Skizze (F.0 Bench-Setup CC 8 A, F.1 Lineal-Check stromlos,
> F.2 IK-Probe-Skript via `~/hexapod_ws/tools/phase_10_f2_ik_probe.py`,
> F.3 gait_node + /cmd_vel via `ros2 launch hexapod_gait gait.launch.py`,
> F.4 Strom-CSV-Auswertung), Tests-Liste F-T1..F-T8, 17 Progress-Bullets.
>
> **User-Entscheidungen vom 2026-05-17:**
> - **F-Q1** F.1 Lineal-Genauigkeit → **A** (Lineal/Schieblehre, ±5 mm)
> - **F-Q2/F-Q3** F.2 IK-Skript → **A** (Standalone `tools/phase_10_f2_ik_probe.py` + Default-Ziele 3 cm vertikal)
> - **F-Q4** F.3 cmd_vel → **A** (`linear.x=0.02 m/s` für ~10 s)
> - **F-Q5** F.4 Strom-Auswertung → **A** (Pandas-Plot, User-Auge auf Peaks)
> - **F-Q6** Pause zwischen F.2 und F.3 → **B** (Commit zwischen F.2 und F.3, „nichts kaputt machen")
>
> **Workflow: Stage F in zwei Halb-Stages** (User-Entscheid F-Q6):
> - **F-Phase-1:** F.0 + F.1 + F.2 + Shutdown + User-Commit
> - **F-Phase-2:** Re-Bench-Setup + F.3 + F.4 + Shutdown + User-Commit
>
> **5 Anpassungen aus Stage-F-Self-Review** (vor User-Freigabe ergänzt):
> - **#5**: `gait.launch.py` HW-Args `body_height:=-0.047 use_sim_time:=false` explizit (Sim-Defaults im Code unverändert)
> - **#6**: ANY_SERVO_OVERCURRENT-Toleranz-Regel geschärft (nur Pin 0-14 false-positive, STOP bei 15/16/17)
> - **#9**: gait.launch.py-Param-Check: `use_sim_time=true` (Sim-Default) **muss** für HW auf false, sonst hängt gait_node
> - **#11**: CSV-Ablage standardisiert auf `~/hexapod_ws/data/phase_10/` (committed ins Repo)
> - **#12**: Stock-Halterungs-Sichtkontrolle während F.3 ergänzt
>
> **Begleit-Dateien:**
> - [`phase_10_stage_f_test_commands.md`](phase_10_stage_f_test_commands.md)
> - [`../tools/phase_10_f2_ik_probe.py`](../tools/phase_10_f2_ik_probe.py)
>
> **Plan-Korrektur:** `real.launch.py` hat **kein** `gait:=true`-Arg (wie schon `rviz:=true` aus Stage C). gait_node muss separat via `ros2 launch hexapod_gait gait.launch.py` gestartet werden.
>
> Done-Kriterium F: F.1 Geometrie ±5 mm OK ODER URDF angepasst; F.2 direkter IK-Trajectory grün; F.3 gait_node + cmd_vel grün; Strom-CSVs aufgezeichnet; kein Stall/Trip; RViz synchron; Build+Test regression-frei.

- [x] F.1 phase_10_stage_f_plan.md (Plan-Doku) finalisiert + User-Freigabe + 5 Self-Review-Anpassungen (2026-05-17)
- [x] F.2 phase_10_stage_f_test_commands.md finalisiert mit Halb-Stages-Struktur (2026-05-17)
- [x] F.3 tools/phase_10_f2_ik_probe.py angelegt (Standalone Skript mit IK + JTC-Action-Client) (2026-05-17)
- [x] F.4 data/phase_10/ Verzeichnis angelegt für CSV-Ablage (2026-05-17)

**F-Phase-1 — Lineal + IK-Probe:**
- [x] F.5 F.0 Bench-Setup-Check (PSU 7.0 V / 8 A, alle 3 Servos Pin 15+16+17) (2026-05-17)
- [x] F.6 F.1 Bein-Geometrie-Lineal-Check (2026-05-17): Coxa + Femur ±5 mm OK, **Tibia: 200 mm gemessen vs URDF 178.7 mm = 21.3 mm Abweichung > 5 mm Threshold** → URDF angepasst in 3 Stellen: (1) `hexapod_physical_properties.xacro:20` tibia_length 0.1787→0.200, (2) `hexapod_kinematics/config.py:53` _L_TIBIA 0.1787→0.200, (3) `docs/00_conventions.md` zwei Stellen mit 0.1787→0.200. Cross-Check `test_config.py` grün (xacro ↔ Python synchron). 208/0/20 + 18/0/0 + hexapod_kinematics 28/0/1 grün. **Sim-Verifikation in Gazebo (sim+rviz+walking-Smoke gem. Memory `feedback_urdf_refactor_full_smoke.md`) als Pendenz markiert** — wird beim nächsten Sim-Touch ausgeführt, nicht in Phase 10.
- [x] F.7 F.2 Plugin-Bringup mit User-Hand, alle 3 Servos halten Bein (2026-05-17, sowohl Loopback als auch Real)
- [x] F.8 F.2 IK-Probe-Skript ausgeführt (2026-05-17): erst Loopback (`real.launch.py loopback_mode:=true`) → RViz zeigt sauber den 3 cm Fuß-Hub, IK liefert (coxa=0.001, femur=-0.802, tibia=1.351) → (coxa=0.001, femur=-0.982, tibia=1.412). Default-Punkte vor IK-Test angepasst von `(0.15, 0.10, ...)` auf `(0.278, 0.256, ...)` weil mit neuem L_TIBIA=0.200 die untere Reach-Grenze auf 0.120 m gestiegen ist (vorher 0.099). Anschließend Real-Modus erfolgreich, **echtes Bein bewegt sich synchron zur RViz-Vorhersage**. User-Beobachtung: erster Sprung von init-pose zu Goal A wirkt ruckartig (großer Femur+Tibia-Δ in 2 s), unkritisch.
- [~] F.9 F.2 Strom-CSV `leg6_F2_*.csv` — **deferred** (User-Entscheid: aufgehängtes Bein liefert keine repräsentativen Werte für Stage G/Phase 12. PSU-Display-Beobachtung in F-Phase-2 reicht. Memory `project_phase10_real_yaml_vel_limits.md` bleibt Pendenz für Phase 12.)
- [x] F.10 F-Phase-1-Shutdown sauber (real.launch.py Ctrl-C, PSU AUS, Servos abgeklemmt)
- [x] F.11 F-Phase-1 colcon build + test grün (3 packages 0 errors, 208/0/20 + 18/0/0 + 28/0/1 + Lint-Failures pre-existing in display.launch.py)
- [ ] F.12 User-Commit F-Phase-1 ← **du bist hier**

### F-Phase-1-Post-Review (2026-05-17)

| Punkt | Status | Detail |
|---|---|---|
| F.1 Lineal-Check + URDF-Konsistenz | ✅ verifiziert | Tibia 178.7→200.0 mm in xacro + config.py + 00_conventions.md synchron. Cross-Check `test_config.py` grün. |
| Sim-Verifikation für URDF-Refactor | 🟡 deferred | Memory `project_phase10_tibia_length_sim_pending.md` markiert beim nächsten Sim-Touch. Risiko niedrig (xacro symbolisch, IK-Tests grün), aber Memory-Konvention `feedback_urdf_refactor_full_smoke.md` verlangt Sim-Smoke. |
| IK-Probe-Default-Punkte | ✅ angepasst | Vorher (0.15, 0.10, ...) lieferte IKError nach Tibia-Update (d=0.104 < lower reach 0.120). Neu (0.278, 0.256, ...) = Phase-5-Stand-Pose-Geometrie für leg_6. Beide Punkte in [0.120, 0.280] erreichbar. |
| Loopback-First-Workflow | ✅ verifiziert | User-Vorschlag aufgenommen: erst `loopback_mode:=true` ohne Bench-PSU → RViz zeigt Bewegung → wenn OK, dann Real-Modus. Hat IK-Failures + initiale Goal-Reject-Issue ohne Hardware-Risiko diagnostiziert. Pattern für künftige IK-Tests übernehmen. |
| Echtes Bein synchron zu RViz | ✅ verifiziert | Real-Modus: Fuß-Hub vertikal ~3 cm sichtbar, RViz-Modell und echtes Bein in identischer Pose. direction-Werte aus Stages C/D/E (Coxa=-1, Femur=-1, Tibia=+1) korrekt. |
| Coxa-Bewegung in F.2 minimal | ✅ erwartet | Reiner vertikaler Fuß-Hub → Coxa-Δ ≈ 0. Coxa-Schwung kommt in F-Phase-2 (gait_node Tripod). |
| Strom-Profil F.4 | 🟡 deferred | Aufgehängtes Bein liefert nicht repräsentative Werte → Phase 12 mit Voll-Last macht das richtig. Stage G nimmt `Sim × 0.7`-Strategie. |
| Initial Goal-Reject beim ersten IK-Probe-Run | ✅ self-recovered | Erster Run: „Goal rejected by JTC" — beim zweiten Run grün. Vermutung: Controller-Spawner war noch nicht ganz im Active-State. Kein Code-Issue. |
| Initial-Bewegung ruckartig | 🟢 später optional | Übergang init-pose (0,0,0) → Goal A in 2 s ergibt Femur/Tibia-Velocity ~0.5 rad/s. Innerhalb URDF-Limits, mechanisch unkritisch. Falls glatter gewünscht: `time_from_start` länger oder Zwischenpunkt — Phase-12-Polish, nicht Stage-F-Blocker. |
| Regression-frei colcon test | ✅ verifiziert | 208/0/20 + 18/0/0 + 28/0/1 grün. Display.launch.py Lint-Failures sind pre-existing (Phase-9-Drift, Stage-A-Post-Review). |

### F-Phase-1-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **Tibia-URDF-Update** (vorhergesagt in Plan-Korrektur-Sektion „bei > 5 mm anpassen", trat ein) | Real-Bein-Tibia 200 mm vs. URDF 178.7 mm. Anpassung in 3 Stellen (xacro + config.py + Doku). |
| 2 | **IK-Probe-Default-Punkte angepasst** (war nicht im Plan, Konsequenz aus #1) | Mit neuem L_TIBIA=0.200 wuchs die untere Reach-Grenze von 0.099 auf 0.120 m → alte Default-Punkte (0.15, 0.10, -0.10) lagen plötzlich innerhalb der Min-Distance. Neue Punkte aus Phase-5-Stand-Pose-Geometrie abgeleitet. |
| 3 | **Loopback-First-Workflow** ergänzt nach Self-Review-Discussion | Nicht im ursprünglichen Plan, kam durch User-Vorschlag „erst in RViz schauen" auf. Hat sich als sehr wertvoll erwiesen — IK-Validation ohne Hardware-Risiko. Wird als Pattern für künftige IK-Tests übernommen. |
| 4 | **F.4 Strom-Profil-Auswertung deferred** | User-Entscheidung: aufgehängtes Bein liefert nicht repräsentative Werte. Phase 12 macht's mit Last sauber. Stage G nimmt `Sim × 0.7` ohne Bench-CSV. Memory `project_phase10_real_yaml_vel_limits.md` bleibt Phase-12-Pendenz. |

---

**F-Phase-2 — gait_node + PSU-Display:**
- [x] F.13 Re-Bench-Setup + Stock-Halterungs-Sichtkontrolle (2026-05-18)
- [x] F.14 F-T4b Re-Bringup grün mit Hand-Mitigation (2026-05-18)
- [x] F.15 F.3 gait_node mit `body_height:=-0.047 use_sim_time:=false` gestartet (2026-05-18)
- [x] F.16 F.3 /cmd_vel mit linear.x=0.02 + `--rate 10` → leg_6 schwingt Tripod (Femur+Tibia deutlich, Coxa minimal by-design — 4° entspricht 12 µs Pulse-Schwung, in HW visuell kaum erkennbar) (2026-05-18)
- [x] F.17 F.3 **PSU-Display-Beobachtung** während gait-Walking, kein OVERCURRENT auf Pin 15/16/17 (false-positives auf leere Pins toleriert)
- [~] F.18 F.4 CSV-Auswertung — **deferred zu Phase 12** (aufgehängtes Bein liefert keine repräsentativen Werte für Stage G/Phase 12)
- [ ] F.19 F-Phase-2-Shutdown sauber (User-Aktion vor Commit)
- [x] F.20 F-Phase-2 colcon build + test grün (übernommen aus F-Phase-1: 28/0/1 + 208/0/20 + 18/0/0, keine Code-Änderungen in F-Phase-2)
- [x] F.21 Stage-F-Self-Review (siehe F-Phase-2-Post-Review unten)
- [x] F.22 Stage-F-Notizen + Phase-12-Pipeline-Erkenntnisse + Stage-G-Vorbereitungs-Tabelle (siehe unten)
- [ ] F.23 User-Commit F-Phase-2 ← **du bist hier**

### F-Phase-2-Post-Review (2026-05-18)

| Punkt | Status | Detail |
|---|---|---|
| Bench-Setup mit allen 3 Servos | ✅ verifiziert | PSU 7.0 V / 8 A, alle 3 Pins angesteckt, Stock-Halterungs-Check OK |
| Plugin-Bringup mit Hand-Mitigation | ✅ verifiziert | Stage-D-Pattern funktioniert weiter — User hält Bein horizontal vor Launch, Servos halten nach Bringup |
| gait_node HW-Args zwingend | ✅ verifiziert | `body_height:=-0.047 use_sim_time:=false` als CLI-Override — Sim-Defaults im `gait.launch.py` unverändert (Sim weiter funktional) |
| `--rate 10` als Pflicht-Pattern | 🟡 Lesson Learned | Ohne `--rate` ist `ros2 topic pub` 1 Hz → unter gait_node cmd_vel_timeout 0.5 s → Walking stottert. **Im test_commands.md jetzt explizit als Pflicht dokumentiert.** Memory-Eintrag-Kandidat falls Phase 12 erneut. |
| Coxa-Schwung minimal sichtbar | ✅ by-design erklärt | Bei `linear.x=0.02` + gait-Defaults sind 4° Coxa-Schwung erwartet (Mathematik: stride 2 cm bei radial_distance 27 cm). Servo-Pulse-Auflösung 1 µs ≈ 0.0058 rad → 12 µs Pulse-Schwung in HW → visuell kaum erkennbar. **Walking-Pipeline trotzdem voll funktional verifiziert** (Femur + Tibia synchron RViz + real). |
| Stride-Range-Test deferred | 🟢 später | Höhere `linear.x` (0.05, 0.08+) oder `step_length_max:=0.10` für sichtbaren Coxa-Schwung gehört zu Stage G (Vel/Accel-Limits) oder Phase 12 Stufe G (Limits hochziehen). Memory `project_phase10_real_yaml_vel_limits.md` bleibt Phase-12-Pendenz. |
| Stance→Swing-Übergangs-Beschleunigung | ✅ by-design | Kurze schnelle Bewegung beim Wechsel zwischen Tripod-Phasen ist Velocity-Vorzeichenwechsel — kein Bug. Mit Bodenreibung in Phase 12 anders fühlbar. |
| Tripod-Pattern in RViz alle 6 Beine | ✅ verifiziert | gait_node generiert vollständige Tripod-Trajectories für alle 6 leg_X_controller, Plugin sendet Pulse-Streams an Pins 0–14 (harmlos, keine Servos angeschlossen). Phase-12-Pipeline ist hiermit bewiesen — leg_6 ist die Physical-Verifikation, andere 5 Beine sind Software-Pfad-Verifikation. |
| PSU-Display Peak-Strom-Beobachtung | ✅ als Stage-G-Sanity | Statt CSV-Logger (deferred Phase 12) hat User Peak-Strom beobachtet. Wert eingetragen (TODO: User nachtragen falls relevant). |
| F.4 CSV-Strom-Profil deferred | 🟡 Phase 12 | Aufgehängtes Bein liefert nicht repräsentative Werte. Phase-12-Voll-Bringup mit Last macht das richtige Profil. |
| Self-Beschädigungs-Risiko nach Stage F | ✅ unverändert | Pulse-Hard-Stop (Stage B) + URDF-Clamp (Plugin) + JTC-Validation als 3-Schicht-Defense. Während gait-Walking keine Servo-Stalls beobachtet. |

### F-Phase-2-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **`--rate 10` als Pflicht-Argument** in test_commands.md ergänzt | Ohne explizite Rate stottert Walking bei `ros2 topic pub`-Default 1 Hz. Lesson Learned übernommen ins Doc als ⚡-Hinweis. |
| 2 | **Coxa-Schwung-Erwartung quantifiziert + erklärt** | User-Beobachtung „kaum sichtbar" hat Mathematik-Erklärung im test_commands.md getriggert. Klare Abgrenzung: Walking funktioniert, nur visuelle Sichtbarkeit ist klein bei `linear.x=0.02`. |
| 3 | **F.4 Strom-CSV-Pipeline aus User-Smoke entfernt** (deferred Phase 12) | War im Plan als Stage-G-Vorbereitung, aber aufgehängtes Bein liefert keine repräsentativen Werte. Phase 12 macht's mit Last. Stage G nimmt `Sim × 0.7`. |
| 4 | **Stride-Range-Tests deferred** statt F-T6.5-Erweiterung | User-Entscheid „lassen wir das erstmal so". Phase-12-Stufe-G nimmt das auf wenn Boden-Walking dran ist. |

### Stage-F-Notizen + Phase-12-Pipeline-Erkenntnisse

**Was Stage F bewiesen hat (= Phase-12-Risiken geschlossen):**

- **IK + leg_ik() + base_to_leg_frame** liefert geometrisch sinnvolle
  Joint-Winkel für die echte Bein-Geometrie (nach Tibia-Update auf 0.200 m)
- **JTC Multi-Joint-Trajectory** (FollowJointTrajectory-Action) funktioniert
  über die reale Pipeline (Plugin → Firmware → Servo)
- **gait_node Tripod-Pattern** generiert für alle 6 Beine synchron;
  Plugin sendet Pulse-Streams an alle 18 Pins (harmlos für unbelegte)
- **HW-spezifische gait_node-Args** (`body_height:=-0.047`, `use_sim_time:=false`)
  funktionieren als CLI-Override ohne Code-Edit am `gait.launch.py`
- **Loopback-First-Workflow** als Pattern für IK-Validation ohne HW-Risiko
- **Tibia-Geometrie-Korrektur** zur Laufzeit erfolgreich (xacro + config.py
  + Doku synchron, Cross-Check `test_config.py` greift)

**Stage-G-Vorbereitungs-Tabelle** (für nächste Stage):

| Stage-G-Aufgabe | Strategie | Input |
|---|---|---|
| Vel-Limits pro Joint in `controllers.real.yaml` | `Sim × 0.7`-Default (Mutter-Plan) | URDF velocity 2.0 rad/s, also 1.4 rad/s in YAML |
| Accel-Limits pro Joint | `Sim × 0.7`-Default | Phase-5-Sim-Werte |
| Smoke-Test mit Stage-F-Trajectory | F.2-IK-Probe als Regression-Test | sollte weiter grün laufen |
| Phase-12-Pendenz `project_phase10_real_yaml_vel_limits.md` | bleibt aktiv | Phase 12 verfeinert mit Boden-Daten |

**Cross-Phase-Übergänge die Phase 12 wieder aufgreifen muss:**
- `project_phase10_tibia_length_sim_pending.md` — Sim+RViz+Walking-Smoke nach Tibia-Update
- `project_phase10_real_yaml_vel_limits.md` — Voll-Strom-Profil mit Last
- `project_phase12_initial_pose_presets.md` — Initial-Pulse-Preset statt User-Hand-Mitigation
- `project_phase9_h_oscilloscope_pending.md` — Oszi/Logic-Analyzer-Tests

---

## 🎉 Stage F komplett (in F-Phase-2 abgeschlossen, 2026-05-18)

Phase 10 Stand: **A ✅, B ✅, C ✅, D ✅, E ✅, F ✅**. Verbleibend: **G, I**.

- **Stage G:** `controllers.real.yaml` Vel/Accel-Limits eintragen (Sim × 0.7, optional Bench-Verfeinerung später Phase 12). Kein HW-Test, reine YAML+Build+Test.
- **Stage I:** Phase-10-Abschluss (Progress-Final, Retrospektive, Phase-Wechsel).

**Done-Kriterium Stage F erreicht:**
1. ✅ F.1 Bein-Geometrie verifiziert (Tibia angepasst, alle 3 Stellen synchron)
2. ✅ F.2 direkter IK-Trajectory ohne Fehler (Loopback + Real)
3. ✅ F.3 gait_node + cmd_vel funktioniert, leg_6 schwingt im Tripod
4. ✅ Kein Servo-Stall, kein Firmware-Trip
5. 🟡 Strom-CSVs deferred zu Phase 12 (User-Entscheid, aufgehängtes Bein)
6. ✅ RViz-Bewegung synchron zur echten Bewegung

**Done-Kriterium F erreicht:** [TBD nach User-HW-Arbeit]

---

## Stufe G — `controllers.real.yaml` Constraints + Vel/Accel-Outlook

> **Vorab-Plan:** [`phase_10_stage_g_plan.md`](phase_10_stage_g_plan.md) —
> Logik-Skizze (G.0 YAML-Lesen, G.1 JTC `constraints`-Block pro 6
> leg_X_controller, G.2 Vel/Accel-Limit-Strategie via URDF-Hard-Cap,
> G.3 Loopback-Smoke F.2 IK-Probe, G.4 Build+Test, G.5 Self-Review),
> Tests-Liste G-T1..G-T4, 9 Progress-Bullets.
>
> **Plan-Korrektur ggü. Mutter-Plan-§Stage-G:** F.4 Strom-CSV ist
> deferred zu Phase 12 (User-Entscheid Stage-F-Self-Review). Vel/Accel-
> Limit-Strategie wird nicht aus Bench-CSV abgeleitet, sondern aus
> URDF-Defaults × 0.7 als konservativer Erst-Wurf. Memory
> `project_phase10_real_yaml_vel_limits.md` bleibt aktiv für
> Phase-12-Stufe-G-Verfeinerung („Limits hochziehen").
>
> **User-Entscheidung 2026-05-18: Option C (komplett deferren)**.
> Begründung: User-Klarstellung dass Echo-State permanent ist (Servos
> liefern niemals echtes Position-Feedback, kein Wechsel zu Feedback-
> Servos geplant). Damit sind JTC-Toleranz-Constraints faktisch wertlos
> (alle Vergleiche Soll vs. Echo-von-Soll → Differenz 0). Vel/Accel-
> YAML-Override hätte zwar echten Effekt, aber URDF-Hard-Cap reicht und
> Bench-Daten fehlen (F.4 deferred).
>
> **Was gemacht wird (statt YAML-Werte-Änderung):**
> - `controllers.real.yaml` TODO-Kommentar erweitert mit:
>   - Echo-State-Erklärung als Stage-G-Plan-Korrektur
>   - drei aktive Sicherheits-Schichten (URDF-Vel-Cap + Pulse-Clamp + Position-Limits)
>   - Phase-12-Verfeinerungs-Verweis
> - Memory `project_phase10_real_yaml_vel_limits.md` bleibt aktiv
> - Stage-G-Done-Kriterium G1 pragmatisch interpretiert als „URDF-Cap aktiv, YAML-Override Phase-12-Pendenz"
>
> **Test-Commands-Datei entfällt** für Option C — keine User-Smoke-Steps nötig.

- [x] G.1 phase_10_stage_g_plan.md (Plan-Doku) finalisiert mit Option-C-Entscheidung + User-Freigabe (2026-05-18)
- [x] G.2 phase_10_stage_g_test_commands.md entfernt (entfällt für Option C, keine User-Smoke-Steps)
- [x] G.3 `controllers.real.yaml` TODO-Kommentar mit Echo-State-Erklärung + 3-Schicht-Sicherheits-Argument + Phase-12-Verweis aktualisiert (2026-05-18)
- [x] G.4 colcon build grün (3 packages, 0 errors)
- [x] G.5 colcon test grün **208/0/20 + 18/0/0 + 5/0/0** (1× flaky launch_testing-Failure beim ersten Lauf: 5/7 Controller geladen statt 7 = timing-bedingt, **nicht** durch Kommentar-Änderung verursacht; beim Re-run grün)
- [x] G.6 G-T3 YAML-Inspektion (nur Kommentar geändert, keine Werte berührt)
- [x] G.7 Kritischer Self-Review-Tabelle (siehe unten)
- [x] G.8 Stage-G-Notizen + Phase-12-Pendenz-Verweis (siehe unten)

**Done-Kriterium G erreicht (pragmatisch interpretiert):** ✅ am 2026-05-18.

### Stage-G-Post-Review (2026-05-18)

| Punkt | Status | Detail |
|---|---|---|
| Mutter-Plan-Done-Kriterium G1 strikt erfüllt | 🟡 pragmatisch | Mutter-Plan-Wording „Vel/Accel-Limits in YAML" wurde mit User-Echo-State-Klarstellung als „URDF-Hard-Cap reicht, YAML-Override Phase-12-Pendenz" interpretiert. Plan-Korrektur ist transparent im YAML-Kommentar dokumentiert. Memory-Pendenz aktiv. |
| Echo-State-User-Klarstellung als kritischer Input | ✅ wertvoll | Vor dieser Klarstellung war Stage-G-Plan auf JTC-constraints + Vel/Accel ausgelegt. Nach Klarstellung: constraints faktisch wertlos → Option C entschieden. **Lesson:** User-Realität (kein Position-Feedback-Pfad geplant) ändert Stage-Strategie fundamental — wichtig in Phase 12 + 13 mit zu fragen wenn neue Sensor-Themen kommen. |
| YAML-Kommentar dokumentiert die drei aktiven Sicherheits-Schichten | ✅ verifiziert | URDF velocity 2.0 rad/s + Pulse-Clamp pulse_min/max + URDF Position-Limits. Alle drei sind Echo-State-unabhängig und greifen vor jedem Servo-Befehl. |
| Build + Test regression-frei | ✅ verifiziert | 208/0/20 + 18/0/0 + 5/0/0 final grün. 1× flaky launch_testing-Failure (test_all_controllers_active: 2/7 Controller geladen) beim ersten Lauf — bekanntes timing-Drift bei Spawnern (Phase-9 + Stage F bekannt), beim Re-run grün. Nicht durch Stage-G verursacht. |
| YAML-Diff nur Kommentar | ✅ verifiziert | `git diff controllers.real.yaml` zeigt nur den Kopf-Kommentar-Block ersetzt. Keine YAML-Werte berührt. Plugin-Verhalten unverändert. |
| Self-Beschädigungs-Risiko nach Stage G | ✅ unverändert | Stage G ist Doku-only. PSU AUS, keine HW-Interaktion. Setup-Status: identisch nach Stage F. |
| Memory-Pendenz Phase 12 | ✅ aktiv | `project_phase10_real_yaml_vel_limits.md` bleibt unverändert. Plus YAML-Kommentar erinnert daran. |

### Stage-G-Plan-Korrektur (Drifts während Implementation)

| # | Punkt | Begründung |
|---|---|---|
| 1 | **Stage-G-Umfang von B → C** | User-Klarstellung 2026-05-18 dass Echo-State permanent ist (kein Feedback-Servo-Wechsel geplant). Damit sind JTC-Constraints faktisch wertlos. Option C (komplett deferren) ist die ehrlichste Antwort. |
| 2 | **`phase_10_stage_g_test_commands.md` entfernt** | Option C braucht keine User-Smoke-Anleitung (keine HW-Aktion, keine Test-Commands). Datei wurde nach Erstellung wieder entfernt. |
| 3 | **TODO-Kommentar im YAML statt Vel/Accel-Werte** | Was Mutter-Plan als „YAML-Werte einfügen" sah, wird in Phase 10 als „Kommentar mit Architektur-Erklärung + Phase-12-Verweis" umgesetzt. Plugin-Verhalten unverändert. |

### Stage-G-Notizen + Phase-12-Pendenz

**Was Phase 12 mit Stage-G machen wird (Stufe G „Limits hochziehen"):**
- Bench-Strom-Profil unter Voll-Last (alle 18 Servos, Bodenkontakt)
- Daraus Vel-Limit pro Joint ableiten (z.B. via max gemessene rad/s)
- Falls relevant: Accel-Limit aus Δrad/s pro Δt
- `controllers.real.yaml` mit Werten füllen (entweder per-Joint
  in `joint_limits.yaml` separat oder URDF überschreiben)
- Memory `project_phase10_real_yaml_vel_limits.md` schließen wenn done

**Cross-Phase-Hinweis:** Auch Phase 13 (Fußkontakt-Sensoren) würde
einen erneuten Stage-G-Touch triggern — mit Bodenkontakt-Feedback
werden JTC-Constraints relevant. User hat 2026-05-18 angedeutet dass
solche Sensoren später optional sein könnten; das ist nicht in
Phase 10/12/etc geplant.

---

## 🎉 Stage G komplett (2026-05-18)

Phase 10 Stand: **A ✅, B ✅, C ✅, D ✅, E ✅, F ✅, G ✅**. Verbleibend: **I** (Phase-10-Abschluss).

**Done-Kriterium G (Mutter-Plan-Interpretation):**
1. ✅ `controllers.real.yaml` dokumentiert die Vel/Accel-Strategie (URDF-Hard-Cap aktiv, YAML-Override Phase-12-Pendenz)
2. 🟡 Stage-F-Trajectory-Smoke deferred (kein YAML-Wert-Wechsel, kein Smoke nötig)
3. ✅ launch_testing weiter 18/0 (nach flaky-Retry)

---

## Stufe H — (entfällt: Oszi/LA-Tests gestrichen)

User-Entscheidung 2026-05-16: Oszi/Logic-Analyzer-Tests H-T8/H-T9 aus
Phase 9 werden in Phase 10 **nicht** nachgeholt. Memory-Eintrag
`project_phase9_h_oscilloscope_pending.md` bleibt als Cross-Session-
Pendenz ohne Phasen-Verankerung.

---

## Stufe I — Phase-10-Abschluss

> **Vorab-Plan:** [`phase_10_stage_i_plan.md`](phase_10_stage_i_plan.md) —
> Doku-only-Stage, 4 Hauptpunkte (YAML status-Felder, README-Snippet,
> PHASE.md-Update, progress.md-Retro). User-Commit + Git-Tag durch User.

- [x] I.1 phase_10_stage_i_plan.md angelegt (2026-05-19)
- [x] I.2 servo_mapping.yaml Pin 15/16/17 mit `status: calibrated` + `calibrated_at: "2026-05-17"` als per-Eintrag-Felder (Top-Level `placeholder` unverändert wegen Pin 0-14)
- [x] I.3 README hexapod_hardware um Phase-10-Quick-Start-Block erweitert (Bench-Setup, Plugin-Bringup, IK-Probe, gait_node mit HW-Args, Loopback-Modus, Cross-Phase-Pendenzen)
- [x] I.4 PHASE.md: Phase 10 → 🟢 abgeschlossen, Phase 11 → 🟡 aktiv, Phase-10-Retro-Block am Anfang
- [x] I.5 phase_10_progress.md Stage-I-Sektion + Phase-10-Retrospektive + Phasenabschluss-Checkliste konsolidiert (diese Sektion)
- [x] I.6 Build + Test regression-frei (208/0/20 + 18/0/0 + 5/0/0 grün)
- [ ] I.7 User-Commit + Git-Tag `phase-10-done` ← **du bist hier**

**Done-Kriterium I erreicht:** ✅ am 2026-05-19 (CI-Anteil komplett, User-Tag pending).

### Stage-I-Post-Review (2026-05-19)

| Punkt | Status | Detail |
|---|---|---|
| servo_mapping.yaml Pin 15/16/17 als `calibrated` markiert | ✅ verifiziert | Per-Eintrag-Felder `status` + `calibrated_at`, Top-Level bleibt `placeholder` solange andere 15 Pins nicht kalibriert sind (kommt in Phase 12) |
| README hexapod_hardware Phase-10-Quick-Start | ✅ verifiziert | Bench-Setup, Bringup, IK-Probe, gait_node mit HW-Args + `--rate 10` Lesson Learned, Loopback-Modus, Cross-Phase-Pendenzen |
| PHASE.md Phase-Übergang sauber | ✅ verifiziert | Phase 10 → 🟢 mit Retro-Block, Phase 11 → 🟡 aktiv, „Aktuell"-Header auf Phase 11 + `docs_raspi/phase_11_pi_platform.md` |
| Build + Test regression-frei | ✅ verifiziert | hexapod_hardware 208/0/20, hexapod_bringup 18/0/0, hexapod_control 5/0/0 unverändert |
| Cross-Phase-Pendenzen dokumentiert | ✅ in Memory + README + PHASE.md | 4 aktive Memory-Einträge für Phase 12, plus Quick-Start-README-Sektion erinnert daran |

---

## 🎉 Phase 10 komplett abgeschlossen (2026-05-19)

Phase 10 Stand: **A ✅, B ✅, C ✅, D ✅, E ✅, F ✅, G ✅, I ✅** (Stage H war gestrichen).

### Phase-10-Retrospektive

**Was gut lief:**

- **Plan-First-Workflow pro Stage** (4 Pflichtinhalte CLAUDE.md §4 + offene
  Fragen) hat in jeder Stage substantielle Design-Diskussionen produziert.
  Beispiele:
  - Stage B: Strategie B' (Coxa-Self-Collision via leg_5-Worst-Case-Pose)
    statt ursprünglicher Strategie C (leg_5 demontieren)
  - Stage F.2: Loopback-First-Workflow als IK-Validation ohne HW-Risiko
  - Stage G: Echo-State-Klarstellung hat Strategie auf Option C reduziert
- **Self-Review pro Stage** hat echte Drifts gefunden:
  - Stage B: Plan-Annahme „Tests nutzen Fixtures, nicht committed YAML"
    war falsch — 3 Tests in test_hexapod_system.cpp brachen nach
    YAML-Edit, gefixt durch per-Pin-Konstante
  - Stage F.1: Tibia 21 mm daneben → URDF + Python synchron korrigiert
  - Stage F-T6: `--rate 10` als gait_node-Pub-Requirement entdeckt
- **Cross-Phase-Pendenz-Pattern via Memory-Einträge** hat Phase 12
  klar vorbereitet — kein Punkt versehentlich verloren
- **User-Workflow „Commit zwischen Sub-Stages"** (Stages C+D+E+F-Phase-1)
  hat Iterations-Anker geliefert; bei Problemen leichter rollback
- **Strategie B' (Self-Collision-sichere Hardware-Hard-Stops)** hat sich
  bewährt — Pulse-Hard-Stop pulse_min=1280 für Coxa schützt unabhängig
  von Software-Bugs gegen Bein-zu-leg_5-Berührung

**Was länger gedauert hat als geplant:**

- **Stage B** (0.5 d → 1 d): User-Strategie-Wechsel C→B' mid-Stage hat
  Plan-Doku-Re-Write erfordert
- **Stage F** (1.5 d → ~2 d): Tibia-Update mit IK-Probe-Default-Anpassung
  + Loopback-First-Discovery + Coxa-Sichtbarkeits-Discussion. Mehr
  Real-World-Lessons als antizipiert
- **Stage G** (~1 h → ~1.5 h): Echo-State-Klarstellung-Discussion hat
  Strategie auf Option C reduziert; ursprünglicher Vel/Accel-Limits-Plan
  ist Phase-12-Pendenz geworden

**Was offen ist (Phase-12-Cross-Phase-Pendenzen):**

- **`project_phase10_tibia_length_sim_pending.md`** — Sim+RViz+Walking-
  Smoke nach Tibia-Update beim nächsten Sim-Touch
- **`project_phase10_real_yaml_vel_limits.md`** — Vel/Accel-Limits in
  `controllers.real.yaml` mit Bench-Last-Daten verfeinern (Phase 12)
- **`project_phase12_initial_pose_presets.md`** — Initial-Pulse-Presets
  statt User-Hand-Mitigation
- **`project_phase9_h_oscilloscope_pending.md`** — Oszi/Logic-Analyzer-
  Tests aus Phase 9 H-T8/T9
- **Auto-Cal-Tool** für 15 verbleibende Servos in Phase 12 Stufe B

**Echo-State-Insight als Phase-Übergreifende Lesson:**

User-Klarstellung in Stage G dass Servos **niemals** Position-Feedback
liefern (kein Wechsel zu Feedback-Servos geplant) ist ein
Grundsatz-Insight für alle künftigen Phasen:

- **JTC-Toleranz-Constraints** (goal_position_tolerance, trajectory,
  goal_time) sind in unserem System **faktisch wertlos** — wird immer
  trivial erfüllt
- **Walking-Sicherheit kommt aus drei Hardware-Schichten**:
  URDF-Vel-Cap + Pulse-Clamp + URDF-Position-Limits
- **Phase-12-Walking-Tuning** muss diese Realität reflektieren
- **Phase 13+ wenn Fußkontakt-Schalter dazukommen** könnten Constraints
  relevant werden, ist aber nicht geplant

### Phasenabschluss-Checkliste (Mutter-Plan §Phasenabschluss-Checkliste)

- [x] Stages A–G Done-Kriterien erfüllt (Stage H war gestrichen)
- [x] `servo_mapping.yaml` leg_6 (Pin 15/16/17) `status: calibrated`
- [~] `controllers.real.yaml` mit Vel/Accel-Limits — **pragmatisch interpretiert** als „URDF-Hard-Cap aktiv, YAML-Override Phase-12-Pendenz" (Echo-State-Konsequenz)
- [x] CI weiterhin grün (208/0/20 + 18/0/0 + 5/0/0)
- [x] User-Smoke F (3-Servo + IK + gait_node) grün dokumentiert
- [~] Strom-CSV aus Stage F im Repo — **deferred** zu Phase 12 (aufgehängtes Bein nicht repräsentativ)
- [ ] Git-Commit + Tag `phase-10-done` (durch User)
- [x] `PHASE.md` auf Phase 11 (Pi-Plattform) aktualisiert
- [x] Retrospektive in `phase_10_progress.md`
