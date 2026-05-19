# Phase 10 — Sicherheits-Setup (zentral)

**Zweck:** Eine einzige Quelle der Wahrheit für alle Phase-10-Sicherheits-
und Setup-Konventionen. Stage-Test-Commands-Docs (`phase_10_stage_<X>_test_commands.md`)
**referenzieren** dieses Doc, statt die Inhalte zu duplizieren.

**Geltungsbereich:** Phase 10 Stages A–I. Phase 12/13 können Teile
übernehmen, müssen aber selbst entscheiden was anwendbar bleibt
(z.B. CC-Limits skalieren bei mehr Servos).

**Hintergrund:** CLAUDE.md §9 Hardware-Sicherheit, Phase-10-Mutter-Plan-Doku
[Architektur-Entscheidungen B + C + D](phase_10_single_leg.md#architektur-entscheidungen).

---

## §1 — Aufbockung-Status (gegeben)

Der Hexapod ist an einer **Stock-Halterung** am Tisch montiert (User-
Aufbau, fertig). Die Halterung greift unter den **Bauch** (= base_link)
des Roboters, alle 4 montierten Beine (leg_1/3/5/6) **hängen frei nach
unten**. Keine Bodenkontakt-Möglichkeit.

**Konsequenzen für Phase 10:**

- Schwerkraft-Wirkung: ungesperrte Servos lassen den Joint passiv in den
  Schwerkraft-Anschlag fallen (Femur klappt nach unten, Tibia knickt).
- **Risiko-Domäne**: nur **Selbst-Beschädigung** möglich (Bein-Mechanik
  gegen sich selbst oder gegen Body), keine externen Kollisions-Schäden.
- Stand-Pose-Tests, Bodenkontakt-Tests, Walking → erst Phase 13.

**Aktion vor jeder Stage:** kurze Sicht-Prüfung dass die Stock-Halterung
fest sitzt + Bauch-Befestigung intakt ist + keine Kabel sich um
bewegliche Teile gewickelt haben.

---

## §2 — Bench-PSU-Setpoint-Tabelle pro Stage

**Spannung: 7.0 V durchgehend** (LiPo-Plateau-Mitte, siehe
[Mutter-Plan-Doku §B](phase_10_single_leg.md#b-bench-setup-für-stages-cf-mit-echtem-servo)).

| Stage | Servos angeschlossen | CC-Limit | Begründung |
|---|---|---|---|
| **A** | keine | PSU **AUS** | reine Doku-Stage, keine HW |
| **B** | keine (Tester hat eigene PSU) | PSU **AUS** | Servos sind am HJ-Tester, nicht am Servo2040 |
| **C** | leg_6 coxa (Pin 15) | **3 A** | Diymore 8120MG Stall ~2.5 A × 1.2 Sicherheits |
| **D** | leg_6 coxa + femur (Pin 15, 16) | **7 A** | 3 A Coxa + 4 A Femur (Miuzei MS61 Stall ~3.5 A × 1.15) |
| **E** | leg_6 tibia (Pin 17, allein) | **4 A** | Miuzei MS61 Stall, analog Femur |
| **F** | leg_6 voll (Pin 15, 16, 17) | **8 A** | Σ Idle ~1.5 A + Trajectory-Peaks; 3 gleichzeitige Stalls extrem unwahrscheinlich |
| **G** | leg_6 voll | **8 A** | wie Stage F, gleicher HW-Setup |
| **I** | keine | PSU **AUS** | reine Doku-Stage |

**Spannungs-Toleranz:** PSU auf 7.0 V ± 0.05 V (Anzeige). Bei
Spannungs-Sag unter Last sind 6.8 V kurzfristig okay; **dauerhaft <6.5 V
= PSU-Setpoint zu niedrig**, hochziehen.

**Strom-Verhalten unter Trip-Bedingung:** wenn ein Servo am mech.
Anschlag stallt, springt die PSU in **CC-Modus** → Spannung sinkt
proportional → Servo bekommt weniger Strom → mechanischer Stress
reduziert. Das ist die zweite Sicherheits-Schicht (Plugin-Clamp ist die
erste, Firmware-Watchdog/Overcurrent ist die dritte).

---

## §3 — Verkabelungs-Polarität

Standard-3-Pin-Servo-Stecker (JST-/Futaba-Pattern):

| Pin-Position | Funktion | Farbe (Standard) | Servo2040-Header |
|---|---|---|---|
| 1 (außen) | GND | **braun** oder **schwarz** | GND-Reihe des Headers |
| 2 (mittig) | V+ | **rot** | V+-Reihe des Headers |
| 3 (außen) | Signal | **gelb**, **orange** oder **weiß** | Signal-Reihe (Pin 15/16/17 für leg_6) |

**Servo2040-Header-Orientierung:**

```
Servo-Output-Header (Pin 0..17):
+----+----+----+
| S  | V+ | G  |   ← jeder Servo-Output hat diese 3 Pins
+----+----+----+
  ↑      ↑    ↑
  Signal V+   GND
  (PWM)  (7V) (Common)
```

**Kritisch:** Wenn V+ und GND vertauscht angesteckt werden, fließt der
volle Strom rückwärts durch die Servo-Elektronik. **Servo ist in
~Sekunden zerstört.** Polaritäts-Sichtprüfung vor jedem Stecken
zwingend.

**Pre-Check pro Servo (vor dem ersten Anstecken):**

1. Stecker am Servo selbst inspizieren — passen die Farben zur obigen Tabelle?
2. Falls nicht-Standard-Farben (manche Hersteller weichen ab): Multimeter-Continuity-Test:
   - Schwarz/braun → Servo-Gehäuse-GND oder Servo-Metallteil
   - Rot → Servo-Internes V+ (über mittleren Pin Continuity)
3. **Im Zweifel: nicht anstecken.** Lieber 5 min Multimeter als zerstörter Servo.

---

## §4 — Anschluss-/Abklemm-Sequenz

### Servo anschließen (strikte Reihenfolge):

1. **Bench-PSU OUTPUT AUS** (Output-Taste vom Netzteil, nicht Hauptschalter)
2. Servo-Connector am Servo2040-Header anstecken
   - Polarität wie §3
   - Korrekter Pin-Index (Stage B = irrelevant weil Tester; Stages C–G = leg_6 → Pin 15/16/17)
3. **Sichtprüfung:** Stecker sitzt vollständig (kein Pin daneben, kein Pin
   draußen, keine schiefe Aufnahme)
4. Bench-PSU **OUTPUT AN** drücken
5. **Strom-Anzeige beobachten** in den ersten 2 Sekunden:
   - **< 200 mA pro angeschlossenem Servo** = OK (Idle-Strom)
   - **> 500 mA pro Servo** = sofort PSU AUS, Verkabelung prüfen
   - **PSU springt in CC** = Kurzschluss oder Servo im Stall → PSU AUS, prüfen
6. Servo2040-LED beobachten:
   - Normales Pattern (Idle-Animation oder steady) = OK
   - Boot-Loop / Trip-Anzeige = Firmware-Trip, USB-Cable nochmal stecken
     und Plugin-Log prüfen

### Servo abklemmen (strikte Reihenfolge):

1. **Bench-PSU OUTPUT AUS**
2. Servo-Connector vom Servo2040-Header abziehen
3. (optional) PSU OUTPUT wieder AN wenn ein neuer Test direkt folgt

**Hot-Swap (mit angeschalteter PSU) ist verboten:**

- Beim Anstecken mit Strom: Inrush-Spike + mögliche Polaritäts-
  Fehlmontage in <1 s = Servo-Tod
- Beim Abstecken mit Strom: Funken-Bildung möglich + falls Servo unter
  Last → unkontrollierter Stopp + Bein fällt in Schwerkraft-Anschlag

---

## §5 — Kill-Switch-Konvention

Zwei explizit getrennte Stop-Mechanismen:

### Notaus (sofort stromlos): Bench-PSU **OUTPUT-Taste**

- **Wann:** unerwartetes Verhalten, Stall-Brumm, Rauch-Verdacht,
  Mechanik-Knacken, Kabel-Verklemmung, Vibrations-Anomalie
- **Effekt:** Servo-Rail in <100 ms stromlos → alle Servos passiv →
  Bein-Schwerkraft zieht Joints in den Anschlag (langsam, weich, weil
  keine elektrische Kraft mehr wirkt)
- **PSU-Setpoint bleibt erhalten** (Spannung + CC-Limit) → schneller
  Wiedereinstieg nach Ursachen-Analyse
- **Servo2040-USB bleibt verbunden** → Plugin-Log bleibt aktiv,
  Firmware sieht UNDERVOLTAGE_TRIPPED-Flag wenn V+ unter Schwelle fällt

### Normal-Stop (sauberer Lifecycle-Stop): Ctrl-C am `ros2 launch`

- **Wann:** geplantes Stage-Ende, „alles gut, jetzt aus"
- **Effekt:** Plugin-`on_deactivate` läuft → 18× DISABLE_SERVO an
  Firmware → Servos werden kontrolliert disabled (Pulse-Stream
  stoppt) → Bein wird weich
- **PSU bleibt an** (kein Eingriff am PSU)
- **Servo2040 bleibt aktiv** (USB-CDC weiter offen)

### Wann was?

| Situation | Aktion |
|---|---|
| „Test war erfolgreich, fertig" | Normal-Stop (Ctrl-C) |
| „Trajectory hängt, kein Goal-Reached" | Normal-Stop, dann debuggen |
| „Servo brummt" oder „Bein zuckt nicht erwartet" | Notaus (PSU OFF) |
| „Strom-Anzeige PSU rot/Maxlimit" | Notaus sofort |
| „USB-Disconnect-Smoke" | Normal-Stop ist OK, PSU bleibt an für Reconnect-Test |
| „Plugin-Crash mit Stack-Trace" | Notaus weil unklar in welchem Zustand die Servos sind |

---

## §6 — Initial-Pulse-Schlag-Mitigation

**Problem:** Beim ersten `on_activate` schickt das Plugin nach den
ENABLE-Frames einen neutralen `SET_TARGETS` mit `pulse_zero ≈ 1500 µs`.
Der Servo war vorher stromlos und passiv → mechanisch in der Position,
in die das Bein-Gewicht ihn gezogen hat. Beim ENABLE springt der Servo
**schlagartig** auf die Joint-Mitte (= 1500 µs).

Bei Femur/Tibia mit frei hängendem Bein bedeutet das einen 60–86°-
Sprung gegen Bein-Gewicht → möglicher Stall-Brumm beim ersten
Hochfahren.

### Mitigation pro Stage: User-Hand-Haltung vor dem ersten ENABLE

> **Wichtig:** Das User-Halten ist **aktives Halten gegen die Schwerkraft**
> (Bein passiv = anders als Joint-Mitte beim Femur), aber nur für ~1 s
> während der ENABLE-Sequenz. Nach Plugin-Activate-Log loslassen.

| Stage | Position in der User das Bein halten soll | Begründung |
|---|---|---|
| **C** (coxa) | Bein radial nach außen ausgestreckt, parallel zum Boden | Coxa-Joint nahe Mitte (Bein steht horizontal vom Body weg). **Passive Coxa = frei rotierbar**, User dreht in Mittel-Position. Kaum Kraftaufwand. |
| **D** (coxa + femur) | Bein nach außen, **Femur ~horizontal gegen Schwerkraft halten**, Tibia darf passiv hängen (geknickt) | beide aktive Joints nahe Mitte. **Passive Femur = vertikal nach unten (~-90°)**; User hebt das Bein-Gewicht auf horizontale Höhe und hält ~1 s. Tibia ist inaktiv in Stage D, ihre passive Haltung irrelevant. |
| **E** (tibia allein) | Tibia gestreckt nach unten halten lassen, Knie offen ~0° — **kaum aktives Halten nötig** | **Wenn beide Femur + Tibia passiv hängen → Bein hängt vertikal nach unten → Tibia ist ohnehin gestreckt = nahe Joint-Mitte.** Lediglich kurz prüfen dass das Knie nicht durch Reibung in einer geknickten Position klemmt. |
| **F** (3-Servo voll) | Bein in **Phase-5-Stand-Pose** halten (Fuß ~50 cm unter Body, leicht radial nach außen) | alle 3 Joints nahe ihrer Stand-Pose-Winkel; minimaler Sprung bei ENABLE. **Coxa+Femur+Tibia gegen Schwerkraft halten** (anstrengend, deshalb in F kurze Phase). |

### Schwerkraft-Konflikt-Joint: Femur

Die User-Hand-Haltung ist beim **Femur** am anstrengendsten, weil:
- Passive Femur-Position (Bein hängt frei): **~-π/2 rad = -90° = unten**
- URDF-Joint-Mitte (Plugin sendet als Initial-Pulse): **0 rad = horizontal**
- Gap = ~90° gegen Schwerkraft mit Bein-Gewicht-Last

Coxa und Tibia haben fast kein Gap zwischen Passiv und Joint-Mitte
(siehe Tabelle oben), nur Femur muss aktiv gestützt werden.

### Phase-12-Outlook: Initial-Pulse-Presets als Plugin-Erweiterung

Die User-Hand-Mitigation ist eine **Phase-10-Workflow-Lösung** für
3 Servos. Phase 13 wird das vermutlich per Plugin-Erweiterung lösen:

- YAML pro Servo bekommt `initial_pulse: { suspended: ..., resting: ... }`
- Plugin-Param `initial_pose_preset` wählt das Setup
- Plugin schickt beim ENABLE den preset-spezifischen Pulse (z.B. für
  suspended-Setup an Femur: `pulse_min`-Nähe = -90° = passive Position)
  → **kein Sprung**, kein User-Halten

Realistisch nur **2 Presets** sinnvoll, weil nur 2 mechanisch mögliche
Initial-Aufbauten existieren:

| Preset | Beschreibung | Phase | Passive Bein-Pose |
|---|---|---|---|
| **`suspended`** | Roboter an Stock-Halterung aufgebockt, Beine hängen frei | Phase 10 + Bench-Tests | Femur ~-90° (vertikal unten), Tibia ~0° (gestreckt), Coxa frei |
| **`resting`** | Roboter auf Bauch liegend, Beine vom User in Liege-Pose ausgerichtet | Phase 13 Bring-up | hängt vom konkreten Layout ab; muss pro Servo gemessen werden |

**Kein `stand`-Preset:** Stand ist eine **Ziel-Pose**, keine Start-Pose
— man fährt sie aus suspended oder resting an, man startet nicht aus
ihr.

**Architektur-Details:** Memory-Eintrag
`project_phase13_initial_pose_presets.md` als Cross-Phase-Reminder, plus
Mutter-Plan-Doku [Architektur-Entscheidung C](phase_10_single_leg.md#c-initial-pulse-schlag-mitigation-kritisch-für-erste-aktivierung-pro-servo) listet das als 3. Alternative neben Soft-Start und Ramped-Enable.

### Workflow

1. **Vor `ros2 launch`:** Bein in die genannte Position bringen, mit der
   nicht-dominanten Hand stützen
2. `ros2 launch hexapod_bringup real.launch.py rviz:=true` im anderen Terminal starten
3. **Während ENABLE-Sequenz (~1 s):** Bein weiter halten, Servo greift
   sanft die Joint-Mitten-Pose
4. **Nach Plugin-Activate-Log-Zeile:** Bein **vorsichtig loslassen**, kurz
   beobachten ob Servo die Pose hält
5. Bei Stall-Brumm oder Pose-Drift: Notaus (PSU OFF), Kalibrierungs-
   Werte oder Mechanik-Anschluss prüfen

**Wichtiger Hinweis:** Diese Mitigation ist eine **menschliche**
Sicherheits-Schicht und ersetzt nicht die Plugin-CC-Limit-Schicht und
Firmware-Overcurrent-Schicht. Wenn der User das Bein **nicht** hält
(z.B. unbeabsichtigt), trippt die PSU im CC-Modus + Firmware sendet
ERROR_REPORT/SERVO_OVERCURRENT — der Servo bleibt unbeschädigt. Aber
die User-Hand verhindert dass es überhaupt soweit kommt.

---

## §7 — Pre-Stage-Checkliste (vor jedem Stage-Test)

Diese Punkte vor dem Start jeder Stage B/C/D/E/F/G durchgehen:

- [ ] Hexapod auf Stock-Halterung sitzt fest, keine Kabelverwicklungen
- [ ] PSU auf **7.0 V** eingestellt (Multimeter-Check empfohlen beim
  ersten Mal pro Session)
- [ ] PSU CC-Limit auf den Stage-spezifischen Wert (Tabelle §2)
- [ ] PSU OUTPUT zunächst **AUS**
- [ ] Nur die Stage-spezifischen Servos angeklemmt (Stage C: nur Coxa.
  Stage D: Coxa+Femur. usw.)
- [ ] Polaritäts-Sichtprüfung pro angeklemmtem Servo (§3)
- [ ] USB-Kabel Servo2040 ↔ Desktop steckt
- [ ] Pre-Stage-Bein-Haltung verstanden (§6 Tabelle)
- [ ] Hand an PSU-OUTPUT-Taste (Kill-Switch §5)

Nach Stage:
- [ ] PSU OUTPUT AUS bevor Servos abgeklemmt werden
- [ ] Plugin-Log auf ERROR_REPORTs durchgegangen
- [ ] CSV/Logs falls aufgezeichnet (Stage F) gespeichert

---

## §8 — Wenn was schief geht: Eskalations-Pfad

1. **Symptom genau beobachten:** was tut der Servo, was zeigt der
   Plugin-Log, was zeigt PSU-Anzeige?
2. **Notaus drücken** (PSU OUTPUT OFF) wenn:
   - Sichtbarer Rauch oder ungewöhnlicher Geruch
   - Servo bewegt sich unkontrolliert oder vibriert hochfrequent
   - PSU-Strom-Anzeige am Max-Limit kleben
   - Bein-Mechanik knackt oder klemmt
3. **Dokumentieren** in Plan-Korrektur-Sektion des Stage-Plan-Docs:
   - Was passierte
   - Welches Log + welcher PSU-Wert
   - Hypothese für Ursache
   - Behoben mit (Verkabelung neu, YAML-Anpassung, ...)
4. **Erst dann wieder PSU AN** und Stage fortsetzen oder zurückrollen

**Verbotene Reaktionen:**
- „Vielleicht klappt es beim 2. Versuch" ohne Ursachen-Analyse →
  zerstörte Hardware
- „Ich werd den Servo halt mal höher Strom geben damit er aus dem
  Stall rauskommt" → totalverbrannter Servo
- CLAUDE.md §6 Diagnose-Workflow: erst Beobachtung, dann Hypothese,
  dann gezielter Test, dann Fix. Nicht umgekehrt.
