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

> Wird mit Stage-D-Plan-Doku aufgefüllt sobald Stage C abgeschlossen ist.

**Stages-D-Output (Erwartung):**
- D.1 Coxa + Femur am Pin 15 + 16 angeschlossen
- D.2 2-Joint-Trajectory parallel
- D.3 Femur direction final
- D.4 Endlagen-Test ±1.0 rad

---

## Stufe E — Stack-Validation leg_6_tibia (1 Servo isoliert)

> Wird mit Stage-E-Plan-Doku aufgefüllt sobald Stage D abgeschlossen ist.

**Stages-E-Output (Erwartung):**
- E.1 Tibia an Pin 17 angeschlossen, Coxa + Femur abgeklemmt
- E.2 Trajectory ±0.1 rad und ±1.0 rad
- E.3 Tibia direction final

---

## Stufe F — IK-Roundtrip leg_6 voll (3 Servos) + Voll-Pipeline-Test

> Wird mit Stage-F-Plan-Doku aufgefüllt sobald Stage E abgeschlossen ist.

**Stages-F-Output (Erwartung):**
- F.1 Bein-Geometrie-Verifikation (Lineal-Check vs. URDF)
- F.2 Direkter IK-Aufruf via Python-Skript (Diagnose-Probe)
- F.3 gait_node mit `/cmd_vel`-Stub (Voll-Pipeline-Test)
- F.4 Strom-Profil-Auswertung für Stage G

---

## Stufe G — `controllers.real.yaml` Vel/Accel-Limits

> Wird mit Stage-G-Plan-Doku aufgefüllt sobald Stage F abgeschlossen ist.

**Stages-G-Output (Erwartung):**
- G.1 Vel/Accel-Werte aus Stage-F-CSV ableiten
- G.2 `controllers.real.yaml` per-Joint-Limits eingetragen
- G.3 Smoke-Test mit Stage-F-Trajectory
- G.4 launch_testing weiter 18/0
- Memory-Pendenz `project_phase10_real_yaml_vel_limits.md` abgehakt

---

## Stufe H — (entfällt: Oszi/LA-Tests gestrichen)

User-Entscheidung 2026-05-16: Oszi/Logic-Analyzer-Tests H-T8/H-T9 aus
Phase 9 werden in Phase 10 **nicht** nachgeholt. Memory-Eintrag
`project_phase9_h_oscilloscope_pending.md` bleibt als Cross-Session-
Pendenz ohne Phasen-Verankerung.

---

## Stufe I — Phase-10-Abschluss

> Wird mit Stage-I-Plan-Doku aufgefüllt sobald Stage G abgeschlossen ist.

**Stages-I-Output (Erwartung):**
- I.1 phase_10_progress.md final
- I.2 servo_mapping.yaml Status pro leg_6-Eintrag: `calibrated`
- I.3 README hexapod_hardware Phase-10-Quick-Start-Snippet
- I.4 PHASE.md: Phase 10 → 🟢, Phase 11 → 🟡
- I.5 Git-Commit + Tag `phase-10-done` (durch User)
- I.6 Retrospektive
