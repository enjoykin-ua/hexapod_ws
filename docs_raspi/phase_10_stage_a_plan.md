# Phase 10 — Stufe A — Plan

> **Status:** Plan, noch nicht implementiert.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe A — Phase-10-Mutter-Plan-Doku + Sicherheits-Setup-Doku +
> Progress-Tracker-Skelett.
>
> **Hinweis:** Die Mutter-Plan-Doku selbst ist am 2026-05-16 bereits
> finalisiert + User-freigegeben. Stage A erledigt jetzt die
> **flankierenden Doku-Items** (Progress-Tracker + Sicherheits-Setup-
> Doku), bevor Stage B die erste echte HW-Arbeit (Tester-Pre-Cal)
> beginnt.

---

## Ziel

Phase 10 startet mit zwei Doku-Vorbereitungs-Schritten, **bevor irgendein
Servo angefasst wird:**

1. **`phase_10_progress.md`** anlegen — der Tracker für Stages A–I,
   analog zu [`phase_9_progress.md`](phase_9_progress.md). Hier landen
   alle Bullets `[ ]`→`[x]` pro Stage (Memory `feedback_phase_progress_tracking.md`),
   plus die Design-Entscheidungen aus der Mutter-Plan-Doku als
   konsolidierter Block.
2. **`phase_10_safety_setup.md`** anlegen — ein zentrales Sicherheits-
   Setup-Doc, das alle Stages B–G in ihren Test-Commands-Docs
   referenzieren statt zu duplizieren. Inhalt: Bench-PSU-Setup,
   Verkabelungs-Polarität, Anschluss-/Abklemm-Sequenz, Kill-Switch-
   Konvention, Initial-Pulse-Schlag-Mitigation, Aufbockung.

Kein Code-Edit, kein Build (außer Regression-Check), kein User-Smoke
mit HW.

---

## Logik-Skizze

### A.1 — `docs_raspi/phase_10_progress.md` anlegen

Inhalts-Struktur (analog `phase_9_progress.md`):

```markdown
# Phase 10 — Progress-Tracker

**Phase:** Single-Leg Bring-up + Kalibrierung
**Plan:** [phase_10_single_leg.md](phase_10_single_leg.md)
**Aktiv seit:** 2026-05-16

> Pro erledigtem Bullet [ ] → [x] umstellen, nicht batchen.

---

## Design-Entscheidungen vor Stage A

(Konsolidiert aus Mutter-Plan-Doku Architektur-Entscheidungen A–J)

### A. Hybride Tester-First-Kalibrierungs-Methodik (kompakt: nur leg_6)
[Kurz-Beschreibung + Verworfen-Block + Verweis auf Mutter-Plan-Doku-Sektion A]

### B. Bench-Setup
[Verweis auf Mutter-Plan-Doku-Sektion B + safety_setup.md]

[... A–J analog ...]

---

## Stufe A — Doku-Vorbereitung

> Done-Kriterium A (aus Plan): phase_10_progress.md + phase_10_safety_setup.md
> angelegt, Build/Tests regression-frei.

- [ ] A.1 phase_10_stage_a_plan.md (diese Plan-Doku) finalisiert + User-Freigabe
- [ ] A.2 docs_raspi/phase_10_progress.md angelegt mit Stages A–I als Sektionen + Design-Entscheidungs-Block
- [ ] A.3 docs_raspi/phase_10_safety_setup.md angelegt
- [ ] A.4 Cross-Links verifiziert (Mutter-Plan → Stage-Plan → Progress, alle Safety-Verweise → safety_setup.md)
- [ ] A.5 PHASE.md Status-Check (sollte schon Phase 10 als 🟡 aktiv zeigen aus Phase-9-Stage-J)
- [ ] A.6 colcon build + colcon test regression-frei (A-T1)
- [ ] A.7 Kritischer Self-Review (CLAUDE.md §4-Pflicht)
- [ ] A.8 Eventuelle Post-Review-Fixes

**Done-Kriterium A erreicht:** [TBD]

---

## Stufe B — Mech. End-Stop-Check + HJ-Tester Pre-Cal leg_6
[Skelett, wird in Stage B aufgefüllt]

[... C–I als Skelett-Sektionen ...]
```

Stage-B–I-Sektionen sind leer/Skelett, werden pro Stage aufgefüllt.

### A.2 — `docs_raspi/phase_10_safety_setup.md` anlegen

Zentrale Sicherheits-Doku, von allen Stage-Test-Commands-Docs
referenziert (Memory `feedback_interactive_stage_test_doc.md`).
Strukturiert in 6 Abschnitte:

1. **Aufbockung-Status (gegeben):** Stock-Halterung am Bauch, alle
   Beine hängen frei nach unten, keine Bodenkontakt-Möglichkeit. Foto-
   Verweis bei Bedarf.
2. **Bench-PSU-Setpoint-Tabelle:** pro Stage welche Spannung + CC-Limit:
   - Stage B (offline): PSU AUS während Tester-Arbeit
   - Stage C (1 Coxa): 7.0 V, CC 3 A
   - Stage D (Coxa+Femur): 7.0 V, CC 7 A (= 3 + 4)
   - Stage E (1 Tibia): 7.0 V, CC 4 A
   - Stage F (3-Servo voll): 7.0 V, CC 8 A
3. **Verkabelungs-Polaritäts-Diagramm:**
   - Tabelle Servo-Pin (Farbe Standard) ↔ Servo2040-Header
   - Visuelle Skizze (ASCII oder Markdown-Tabelle) wie der 3-Pin-Stecker
     orientiert ist
4. **Anschluss-/Abklemm-Sequenz:** strikte Reihenfolge PSU-AUS → Stecken
   → Sichtprüfung → PSU-AN → Strom-Check; und umgekehrt für Abklemmen.
   Explizit: **Hot-Swap mit angeschalteter PSU = Servo-Tod-Risiko.**
5. **Kill-Switch-Konvention:**
   - **Notaus** = Bench-PSU OUTPUT-Taste (sofort stromlos, Servos
     werden passiv, Bein fällt durch Schwerkraft sanft in Anschlag)
   - **Normal-Stop** = Ctrl-C am `ros2 launch`-Terminal (sauberer
     `on_deactivate` mit 18× DISABLE_SERVO, PSU bleibt eingestellt
     für schnellen Wiedereinstieg)
6. **Initial-Pulse-Schlag-Mitigation:** User-Aktion vor erstem Enable
   pro Stage:
   - Coxa (Stage C): Bein per Hand in Radial-Außen-Pose halten
   - Femur (Stage D): Bein horizontal nach außen halten, Femur ~horizontal
   - Tibia (Stage E): Tibia gestreckt nach unten halten
   - Voll (Stage F): Bein in Phase-5-Stand-Pose halten

### A.3 — Cross-Links

Mutter-Plan-Doku und Progress-Tracker referenzieren das Safety-Setup-Doc
mit `[safety_setup.md](phase_10_safety_setup.md)` an den relevanten
Stellen. Vermeidet Inhalts-Duplikation.

### A.4 — PHASE.md-Check

PHASE.md ist seit Phase-9-Stage-J auf Phase 10 = 🟡 aktiv gesetzt
(Eintrag „Datei: docs_raspi/phase_10_single_leg.md"). Stage A muss das
nur **verifizieren**, kein Edit nötig.

### A.5 — Regression-Check

`colcon build + colcon test` bleiben grün, weil Stage A keine Code-
Änderungen macht. Nur Doku-Dateien neu/geändert. Erwartung: 208/0
hexapod_hardware + 18/0 hexapod_bringup unverändert.

---

## Tests (alle CI, kein User-Smoke mit HW)

| # | Test | Erwartung |
|---|---|---|
| A-T1 | `colcon build --packages-select hexapod_description hexapod_hardware hexapod_bringup` | grün, keine Warnings (regression-frei) |
| A-T2 | `colcon test --packages-select hexapod_hardware` | 208/0 unverändert (Code nicht angefasst) |
| A-T3 | `colcon test --packages-select hexapod_bringup` | 18/0 unverändert (launch_testing weiter grün) |
| A-T4 | `ls docs_raspi/phase_10_progress.md docs_raspi/phase_10_safety_setup.md` | beide Dateien existieren |
| A-T5 | User-Review der `phase_10_safety_setup.md` | User bestätigt Verständlichkeit + Vollständigkeit als nutzbares Sicherheits-Doc |

### Was bewusst NICHT in Stage A getestet wird

- **Keine HW-Bewegung** — Stage A ist reine Doku, kein Servo wird angefasst.
- **Keine Stage-B-Test-Commands-Doku** — gehört zu Stage B's Plan-Doku (das
  Polaritäts-Diagramm und die Anschluss-Sequenz liegen ab Stage A
  zentral in `safety_setup.md`, Stage-B-Test-Commands-Doku verweist
  darauf).
- **Keine Stage-C/D/E/F-Test-Commands-Docs** — pro Stage geschrieben,
  jeweils mit Verweis auf `safety_setup.md`.
- **Kein PHASE.md-Edit** — Phase 10 ist bereits in Phase-9-Stage-J als
  🟡 aktiv markiert. Wenn der Check ergibt dass was nicht stimmt, dann
  als Post-Review-Fix.
- **Keine Memory-Einträge angelegt** — alle Phase-10-relevanten Memory-
  Einträge existieren bereits (siehe MEMORY.md).

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

Diese Bullets werden 1:1 in `phase_10_progress.md` Stage-A-Sektion kopiert
und dort `[ ]`→`[x]` umgestellt.

- [ ] A.1 phase_10_stage_a_plan.md (diese Plan-Doku) finalisiert + User-Freigabe
- [ ] A.2 docs_raspi/phase_10_progress.md angelegt mit Stages A–I als Sektionen + Design-Entscheidungs-Block aus Mutter-Plan-Doku konsolidiert
- [ ] A.3 docs_raspi/phase_10_safety_setup.md angelegt mit 6 Pflicht-Abschnitten (Aufbockung, PSU-Tabelle, Polarität, Anschluss-Sequenz, Kill-Switch, Initial-Pulse-Mitigation)
- [ ] A.4 Cross-Links verifiziert: Mutter-Plan-Doku referenziert phase_10_safety_setup.md an Architektur-Entscheidungen B + C + D
- [ ] A.5 PHASE.md Status-Check: Phase 10 schon 🟡 aktiv (kein Edit erwartet)
- [ ] A.6 A-T1 (colcon build) grün, regression-frei
- [ ] A.7 A-T2 + A-T3 (colcon test) grün, 208/0 + 18/0 unverändert
- [ ] A.8 A-T4 (Dateien existieren) verifiziert
- [ ] A.9 Kritischer Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] A.10 Eventuelle Post-Review-Fixes
- [ ] A.11 A-T5 (User-Review der safety_setup.md) — User-Smoke per Lesen, kein HW-Aufwand

**Done-Kriterium A erreicht:** wenn alle Bullets `[x]` UND
Self-Review keine 🔴 offenen Punkte hat.

---

## Offene Fragen für User-Review

Zwei kleine Tradeoffs sollten vor Implementation entschieden werden:

### A-Q1 — Safety-Setup als eigene Datei oder Mutter-Plan-Doku-Sektion?

| Variante | Vorteil | Nachteil |
|---|---|---|
| **A: Eigene Datei `phase_10_safety_setup.md`** (Default) | klar separiert; andere Stage-Test-Commands-Docs verweisen mit kurzem Markdown-Link; Mutter-Plan-Doku bleibt schlank | eine Datei mehr im Repo |
| B: Sektion in der Mutter-Plan-Doku | alles an einem Ort | Mutter-Plan-Doku wächst; jeder Stage-Test-Commands-Verweis muss mit `#section-anchor` arbeiten |

**Meine Empfehlung:** A (eigene Datei). `safety_setup.md` ist
funktional ein **Referenz-Doc**, nicht ein **Plan-Doc** — semantisch
sauberer wenn getrennt. Phase 9 hatte das nicht weil dort keine
externe HW im Spiel war.

### A-Q2 — `phase_10_progress.md`: Skelett-Sektionen für alle Stages A–I jetzt, oder pro Stage anlegen?

| Variante | Vorteil | Nachteil |
|---|---|---|
| **A: Alle Stages A–I als Skelett-Sektionen sofort** (Default) | klare Navigation; sieht aus wie Phase-9-Pattern | Stage B–I-Sektionen sind erst Mal leer |
| B: Nur Stage A jetzt, B–I pro Stage anlegen | Datei wächst organisch | weniger Übersicht beim Phase-Start |

**Meine Empfehlung:** A (alle Skelett-Sektionen sofort). Phase 9's
progress.md hatte das auch so, war hilfreich für die Übersicht.

---

## Erwartete Stage-A-Dauer

- A.1 Plan-Doku schreiben: ~30 min (erledigt mit dieser Datei)
- A.2 progress.md anlegen: ~30 min
- A.3 safety_setup.md anlegen: ~60 min (6 Abschnitte sauber dokumentieren)
- A.4–A.5 Cross-Links + PHASE.md-Check: ~15 min
- A.6–A.8 Build + Test + Regression-Check: ~5 min
- A.9 Self-Review: ~15 min
- A.10 Post-Review-Fixes: 0–30 min je nach Review-Ergebnis
- A.11 User-Review der safety_setup.md: User-Zeit

**Schätzung:** ~2.5 h Claude-Arbeit + User-Review. Innerhalb der
Mutter-Plan-Doku-Schätzung von 0.5 d für Stage A.
