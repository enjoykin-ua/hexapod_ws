# Phase 10 — Stufe B — Plan

> **Status:** Plan, in Vorbereitung der HW-Arbeit.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe B — Mech. End-Stop-Check stromlos + HJ-Tester Pre-Cal leg_6.
>
> **Vorbedingung:** Stage A komplett (Mutter-Plan-Doku +
> [`phase_10_safety_setup.md`](phase_10_safety_setup.md) +
> [`phase_10_progress.md`](phase_10_progress.md) angelegt + User-freigegeben).
> Hexapod aufgebockt an Stock-Halterung, leg_6 (Pin 15/16/17) mit
> Diymore 8120MG (Coxa) + Miuzei MS61 (Femur, Tibia) mechanisch montiert.
> **leg_5 bleibt ebenfalls mechanisch montiert** (dient als Self-Collision-
> Referenz während Stage B — siehe Strategie B' unten).

---

## Ziel

**Erste HW-Arbeit der Phase 10**, aber **ohne Stack-Bringup** (keine
Servo2040-USB, keine Plugin-Aktivierung, Bench-PSU bleibt AUS).

**Strategie B' — Konservativ-Pragmatisch (User-Entscheid 2026-05-17):**
`pulse_min`/`pulse_max` für leg_6 werden so kalibriert, dass leg_6 das
Nachbar-Bein **leg_5 unter keinen Umständen treffen kann** — auch bei
Software-Vollbug oder falscher Trajectory. Dafür wird leg_5 **einmal in
eine worst-case Pose** geschwenkt (Coxa maximal Richtung leg_6) und
bleibt passiv in dieser Pose während der gesamten Stage B (Servo-Getriebe-
Friction hält ohne Strom). `pulse_min`/`pulse_max` werden mit **5°
Sicherheits-Abstand vor dem Berührungspunkt** mit leg_5 gesetzt.

Drei Liefer-Items:

1. **Mech. End-Stops + Self-Collision-Anschläge von leg_6 dokumentiert**
   (B.1): per Hand jeden der 3 Joints durchgeschwenkt. **Für Coxa und
   Femur ist Self-Collision mit leg_5 (in worst-case-Pose) der bindende
   Anschlag**, für Tibia meist nur Single-Leg-Mechanik oder URDF-Limit.
2. **HJ-Tester Pre-Calibration der 3 leg_6-Servos** (B.2): pro Servo
   die drei Pulsweiten-Werte (`pulse_zero`, `pulse_min`, `pulse_max`)
   am Tester ablesen, **mit leg_5 in worst-case-Referenzpose**. Werte
   landen in einem **separaten Audit-Log**
   ([`phase_10_stage_b_calibration_log.md`](phase_10_stage_b_calibration_log.md)),
   dann konsolidiert ins YAML für Pins 15/16/17 (B.3).
3. **YAML-Konsolidierung** (B.3): Werte aus dem Audit-Log ins
   `servo_mapping.yaml`.

Nach Stage B sind alle 3 leg_6-Servos im YAML **vor-kalibriert mit
Self-Collision-Sicherheit**:

- `pulse_min`/`max` = Self-Collision-sichere Hard-Stops mit 5°
  Sicherheits-Abstand zu leg_5 worst-case-Pose
- `pulse_zero` = visuelle Joint-Mitte (Augenmaß)
- `direction` bleibt überall `+1` als Platzhalter — Stack-Validation
  in Stages C/D/E entscheidet das per Beobachtungs-Test
- YAML-Status pro Eintrag bleibt `placeholder` (Tester-Stand, kein
  Stack-Beweis) — Stage I setzt das auf `calibrated` nach den Stages C–F

---

## User-Antworten (vor Implementation, 2026-05-16)

Diese Punkte wurden vor Stage-B-Start geklärt:

| Frage | Antwort | Konsequenz |
|---|---|---|
| **B-Q1** Servo-Setup für Tester | **A** — Servo bleibt im Bein montiert, nur Signal/GND-Kabel am Tester | Bein bewegt sich beim Tester-Drehen sichtbar; `pulse_zero` ist direkt visuelle Bein-Mitte; mechanische Anschläge des Beins sind die echten Pre-Cal-Endlagen |
| **B-Q2** Tester-Anzeige | **A** — Digital-Display mit live µs-Anzeige | Wert direkt ablesbar, kein Multimeter nötig |
| **B-Q3** Servo-Reihenfolge | **A** — Coxa → Femur → Tibia | Konsistent mit Stages C/D/E |
| **B-Q4** Werte-Workflow | **A** — separates `phase_10_stage_b_calibration_log.md` als Audit-Trail, am Ende ins YAML konsolidiert | klarer Audit-Pfad: Tester-Ablesung ↔ YAML-Wert nachvollziehbar |

---

## Logik-Skizze

### B.0 — Bench-Setup-Check (Vorbereitung, ~5 min)

Sicherheits-Check vor jeder echten HW-Arbeit (siehe
[`phase_10_safety_setup.md`](phase_10_safety_setup.md) §1+§7):

- Hexapod sitzt fest auf Stock-Halterung
- Alle Beine hängen passiv (keine Verklemmungen, keine Kabel-Wickel)
- Bench-PSU OUTPUT AUS (für Stage B nicht gebraucht, bleibt zur Sicherheit aus)
- HJ-Tester verfügbar:
  - Tester-PSU vorhanden (eigenes Netzteil, getrennt von Bench-PSU)
  - Digital-Display testen: Tester einschalten → Display zeigt aktuellen
    µs-Wert (z.B. „1500us" als Default-Mitte)
  - Tester-Servo-Kabel verfügbar (3-Pin-Servo-Stecker)

### B.1 — Mech. End-Stops + Self-Collision-Check stromlos (~20 min)

**Vorbereitung (einmalig, gilt für ganze Stage B):**

1. **leg_5 in worst-case-Pose schwenken:** leg_5-Coxa per Hand maximal
   Richtung leg_6 drehen (= Bein zeigt nach vorne, Richtung +X). Bein
   per Hand loslassen — Servo-Getriebe-Friction hält die Pose ohne Strom.
2. Sicht-Prüfung: bleibt leg_5 in dieser Pose? Falls nicht (rutscht zurück)
   → mit Klebeband oder Schaumstoff temporär fixieren.

**Pro Joint von leg_6** (in Reihenfolge **Coxa → Femur → Tibia**):

1. Joint per Hand vorsichtig in **eine Richtung** schwenken
2. Anschlag identifizieren — was kommt zuerst?
   - **Self-Collision mit leg_5** (relevant für Coxa, evtl. Femur)
   - **Body-Kollision** (Bein gegen Chassis-Kante)
   - **Servo-Mechanik** (Servo-interner Anschlag)
   - **URDF-Limit** (theoretisch, nicht physisch — nur als Vergleich)
3. Bei Self-Collision: ~5° vor Berührungspunkt mit leg_5 stoppen
   (= Sicherheits-Marge für `pulse_min`/`pulse_max`)
4. Winkel mit Augenmaß schätzen (±5° genug)
5. Wiederholen für andere Richtung
6. Eintrag im `phase_10_stage_b_calibration_log.md` §1

Wichtig: **Stromlos arbeiten.** Servos sind passiv = drehen sich frei.
Keine Gewalt bei Anschlägen.

### B.2 — HJ-Tester Pre-Cal pro Servo (~30 min, ~10 min pro Servo)

Pro Servo (Coxa → Femur → Tibia):

#### B.2.x.1 — Tester anschließen
- Tester-PSU AN
- Servo-Connector mit Y-Adapter oder Umstecken: **Signal + GND** an
  Tester; **V+** kommt aus Tester-PSU (nicht aus Bench-PSU!)
- Sichtprüfung: korrekte Polarität (Standard-Farbschema, siehe
  [`safety_setup.md`](phase_10_safety_setup.md) §3)

#### B.2.x.2 — `pulse_zero` finden
- Tester-Drehknopf auf typische Mitte (~1500 µs) stellen
- Visuelle Joint-Mitte-Prüfung:
  - **Coxa:** Bein zeigt radial nach außen vom Body weg (90° vom Body-Längsachse)
  - **Femur:** Femur-Segment horizontal zum Boden (Wasserwaage oder Augenmaß)
  - **Tibia:** Knie offen, Tibia-Segment in Verlängerung des Femur-Segments (gerader Knie-Winkel)
- Tester-Drehknopf fein-justieren bis visuelle Mitte erreicht
- Display-Wert ablesen → notieren als `pulse_zero_coxa` (bzw. femur, tibia)

#### B.2.x.3 — `pulse_min` finden (Self-Collision-sicher)
- **Vorbedingung:** leg_5 ist in worst-case-Pose (aus B.1-Vorbereitung)
- Tester-Drehknopf langsam in **eine Richtung** drehen
- Beobachten wo leg_6 hingeht relativ zu leg_5:
  - Falls Richtung Self-Collision mit leg_5: **~5° vor Berührungspunkt**
    stoppen, das wird `pulse_min` (Hardware-Hard-Stop, leg_6 kann
    leg_5 nicht treffen)
  - Falls Richtung weg von leg_5: bis mech. Single-Leg-Anschlag, dann
    +5–10 µs Sicherheits-Abstand
- Display-Wert ablesen → notieren als `pulse_min_<joint>`
- **Sicherheits-Regel:** wenn Servo zu brummen anfängt = bereits Stall,
  sofort wegdrehen

#### B.2.x.4 — `pulse_max` finden (Self-Collision-sicher)
- Tester-Drehknopf langsam in die **andere Richtung** drehen
- Analog B.2.x.3, dieses Mal zur anderen Endlage
- Wieder: Self-Collision-Punkt mit leg_5 vorrangig vor Single-Leg-Anschlag

#### B.2.x.5 — Sanity-Check
- Stelle 3 Werte aufschreiben:
  - `pulse_min < pulse_zero < pulse_max` (Reihenfolge muss stimmen)
  - alle Werte in Tester-Bereich (800–2200 µs)
  - Spannweite plausibel: bei 180° URDF-Range (±90°) erwarten wir
    ~1000–2000 µs (mit etwas Asymmetrie wenn pulse_zero nicht
    exakt 1500 µs ist)
- Wenn unplausibel: nochmal messen (Servo-Streuung +/- 50 µs für
  pulse_zero ist okay, ungewöhnliche Werte deuten auf Mess-Fehler)

#### B.2.x.6 — Tester abklemmen
- Tester-PSU AUS
- Servo-Connector wieder vom Tester abnehmen (Servo bleibt mechanisch
  am Bein montiert, ist nach Stage B aber **elektrisch komplett
  abgeklemmt**)

### B.3 — YAML konsolidieren (~10 min)

Werte aus dem `phase_10_stage_b_calibration_log.md` ins
`src/hexapod_hardware/config/servo_mapping.yaml` übertragen für Pin
15/16/17:

```yaml
# vorher (Platzhalter aus Phase 7):
15: { joint: leg_6_coxa_joint  }
16: { joint: leg_6_femur_joint }
17: { joint: leg_6_tibia_joint }

# nachher (Tester-Pre-Cal):
15:
  joint: leg_6_coxa_joint
  pulse_min:  <Tester-Wert>
  pulse_zero: <Tester-Wert>
  pulse_max:  <Tester-Wert>
  # direction: 1 (Platzhalter, Stage C entscheidet)
16:
  joint: leg_6_femur_joint
  pulse_min:  <Tester-Wert>
  pulse_zero: <Tester-Wert>
  pulse_max:  <Tester-Wert>
17:
  joint: leg_6_tibia_joint
  pulse_min:  <Tester-Wert>
  pulse_zero: <Tester-Wert>
  pulse_max:  <Tester-Wert>
```

Top-Level YAML-Status bleibt `placeholder` (andere 15 Pins sind weiter
Defaults). Phase-12-Job wird die anderen 15 Servos kalibrieren.

### B.4 — Build + Test + Self-Review

- `colcon build --packages-select hexapod_hardware` → muss grün bleiben
  (YAML wird zur Build-Zeit nicht ge-parsed, nur zur Laufzeit, also
  Build-OK ist Sanity)
- `colcon test --packages-select hexapod_hardware` → 208/0/20 unverändert
  (kein Code-Pfad ist betroffen; `calibration.yaml`-spezifische
  Unit-Tests verwenden Test-Fixtures, nicht das committed YAML)
- Self-Review-Tabelle pro CLAUDE.md §4

---

## Tests (überwiegend CI + User-Smoke ohne Stack)

| # | Test | Erwartung | Wer |
|---|---|---|---|
| B-T1 | `colcon build --packages-select hexapod_description hexapod_hardware hexapod_bringup` | grün, keine Warnings (regression-frei) | Claude |
| B-T2 | `colcon test --packages-select hexapod_hardware hexapod_bringup` | 208/0/20 + 18/0/0 unverändert vs. Stage-A-Endstand | Claude |
| B-T3 | YAML-Plausibilität: für jeden der 3 leg_6-Pins gilt `pulse_min < pulse_zero < pulse_max`, alle in [800, 2200] µs | strukturell OK | Claude |
| B-T4 | `phase_10_stage_b_calibration_log.md` ist vollständig (3 End-Stop-Eintragungen + 3 Tester-Pre-Cal-Eintragungen) | dokumentiert | Claude |
| B-T5 (User) | Mech. End-Stop-Tabelle stimmt mit gefühlter Realität überein | manuelle Bestätigung | User |
| B-T6 (User) | Tester-Pre-Cal: User hat alle 3 Servos durchgemessen, Werte aus Log nachvollziehbar | manuelle Bestätigung | User |
| B-T7 (Spot-Check) | Manuelle YAML-Inspektion: konkrete Werte sind im YAML drin, nicht mehr Defaults für Pin 15/16/17 | sichtbar im Diff | Claude + User |

### Was bewusst NICHT in Stage B getestet wird

- **Keine Stack-Aktivierung** — Plugin wird nicht hochgefahren, keine
  Bench-PSU für Servo2040, keine ROS2-Node läuft mit dem neuen YAML
  (kommt in Stage C).
- **Kein direction-Wert verifiziert** — Stage C/D/E machen das per
  Beobachtungs-Test pro Servo.
- **Keine Trajectory durch JTC** — Stage C+.
- **Kein Strom-Profil** — kein Strom-Fluss in Stage B (kein Bench-PSU,
  Tester hat seine eigene PSU mit milliampere-Bereich, nicht
  vergleichbar mit Stack-Strömen).
- **Keine IK** — Stage F.

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

Diese Bullets werden 1:1 in `phase_10_progress.md` Stage-B-Sektion
kopiert und dort `[ ]`→`[x]` umgestellt.

- [ ] B.1 phase_10_stage_b_plan.md (diese Plan-Doku) finalisiert + User-Freigabe
- [ ] B.2 phase_10_stage_b_calibration_log.md angelegt als Audit-Trail (Skelett mit Tabellen für End-Stops + Tester-Pre-Cal)
- [ ] B.3 phase_10_stage_b_test_commands.md angelegt mit operativer Anleitung (User-Smoke-Schritte für B-T5 + B-T6)
- [ ] B.4 B.0 Bench-Setup-Check ausgeführt vom User (Hexapod fest, Tester verfügbar, Display funktioniert)
- [ ] B.5 B.1 Mech. End-Stop-Check stromlos für **Coxa** abgeschlossen, Log eingetragen
- [ ] B.6 B.1 Mech. End-Stop-Check stromlos für **Femur** abgeschlossen, Log eingetragen
- [ ] B.7 B.1 Mech. End-Stop-Check stromlos für **Tibia** abgeschlossen, Log eingetragen
- [ ] B.8 B.2 HJ-Tester Pre-Cal **Coxa** (`pulse_zero`/`min`/`max`), Log eingetragen
- [ ] B.9 B.2 HJ-Tester Pre-Cal **Femur**, Log eingetragen
- [ ] B.10 B.2 HJ-Tester Pre-Cal **Tibia**, Log eingetragen
- [ ] B.11 B.3 YAML konsolidiert: Pin 15/16/17 in `servo_mapping.yaml` haben Tester-Werte
- [ ] B.12 B.3 git diff auf `servo_mapping.yaml` zeigt nur Pin 15/16/17 verändert, andere 15 unverändert
- [ ] B.13 B-T1 colcon build grün, regression-frei
- [ ] B.14 B-T2 colcon test grün, 208/0/20 + 18/0/0 unverändert
- [ ] B-T3 (YAML-Plausibilität) verifiziert
- [ ] B-T4 (Log vollständig) verifiziert
- [ ] B.15 Kritischer Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] B.16 Eventuelle Post-Review-Fixes
- [ ] B-T5 + B-T6 + B-T7 User-Bestätigung

**Done-Kriterium B erreicht:** wenn alle Bullets `[x]` UND
Self-Review keine 🔴 offenen Punkte hat UND User die User-Smoke-Tests
B-T5/T6/T7 bestätigt hat.

---

## Entschiedene Fragen vor B.4-Start

Drei Detail-Punkte wurden am 2026-05-16 geklärt:

| Frage | Antwort | Konsequenz |
|---|---|---|
| **B-Q5** Visuelle Joint-Mitte | **A** — Augenmaß reicht | Coxa = Bein 90° vom Body, Femur = horizontal, Tibia = Knie offen/gestreckt. ±3–5° Toleranz in `pulse_zero` ist OK, Stage C/D/E korrigiert per Stack-Beobachtung. |
| **B-Q6** Mech. Anschlag außerhalb Tester-Range | **A** — theoretisch berechneten Wert nutzen | Falls mech. Anschlag jenseits Tester-Range liegt: `pulse_min`/`max` aus URDF-Limit + geschätzter µs/rad-Steigung berechnen. Im Log explizit als „berechnet" markieren. |
| **B-Q7** Tester-PSU-Spannung | **A** — Tester-PSU einstellbar, auf **7.0 V** setzen | Servo-Charakteristik bei Pre-Cal identisch zur Stack-Validation (Stages C–F). `pulse_zero`/`min`/`max` direkt verwertbar ohne Spannungs-Anpassung. |

---

## Erwartete Stage-B-Dauer

- B.1 Plan-Doku schreiben: ~30 min (erledigt mit dieser Datei)
- B.2 calibration_log.md anlegen: ~15 min (Skelett mit Tabellen)
- B.3 test_commands.md anlegen: ~30 min (operative User-Smoke-Anleitung)
- B.4 B.0 Bench-Setup-Check: User-Zeit, ~5 min
- B.5–B.7 B.1 End-Stop-Check (3 Joints): User-Zeit, ~15 min
- B.8–B.10 B.2 Tester-Pre-Cal (3 Servos): User-Zeit, ~30 min (10 min pro Servo)
- B.11 YAML konsolidieren: ~10 min Claude (mit User-Verifikation)
- B.12 git diff verifizieren: ~2 min
- B.13–B.14 Build + Test: ~5 min
- B-T3 + B-T4: ~5 min
- B.15 Self-Review: ~15 min
- B-T5/T6/T7 User-Bestätigung: User-Zeit, ~10 min

**Schätzung:** ~1.5 h Claude-Arbeit + ~1.5 h User-HW-Arbeit + ~0.5 h Sync
= **~3.5 h Gesamt** (entspricht etwa 0.5 d aus Mutter-Plan-Schätzung).
