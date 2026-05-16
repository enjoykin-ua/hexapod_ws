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
- [ ] A.11 A-T5 (User-Review der safety_setup.md) — User-Smoke per Lesen, pending

**Done-Kriterium A erreicht:** ✅ am 2026-05-16 (CI-Anteil: A.1–A.10 alle abgeschlossen, Build + Test regression-frei, Self-Review ohne offene 🔴-Punkte). User-Anteil A.11 (Review der safety_setup.md) wartet auf User.

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

> Wird mit Stage-B-Plan-Doku aufgefüllt sobald Stage A abgeschlossen ist.

**Stages-B-Output (Erwartung aus Mutter-Plan-Doku):**
- B.1 Mech. End-Stop-Check (leg_6, 3 Joints) ohne Strom
- B.2 HJ-Tester Pre-Cal pro Servo (pulse_zero, pulse_min, pulse_max)
- B.3 Werte in `servo_mapping.yaml` für Pin 15/16/17 eingetragen

---

## Stufe C — Stack-Validation leg_6_coxa (1 Servo)

> Wird mit Stage-C-Plan-Doku aufgefüllt sobald Stage B abgeschlossen ist.

**Stages-C-Output (Erwartung):**
- C.1 Coxa-Servo am Pin 15 angeschlossen, PSU-AUS-→-AN-Sequenz
- C.2 Plugin Bringup, erste Trajectory ±0.1 rad
- C.3 direction final in YAML
- C.4 Endlagen-Test ±1.0 rad, kein Stall

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
