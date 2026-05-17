# Phase 10 — Stufe B — Test-Anleitung (User-Smoke)

**Was geprüft wird:** Erste HW-Arbeit der Phase 10. Mechanische End-Stops
+ **Self-Collision-sichere Anschläge** von leg_6 dokumentieren (stromlos)
+ HJ-Tester Pre-Cal der 3 leg_6-Servos (mit Tester-PSU, ohne Bench-PSU,
ohne Servo2040).

**Strategie B' (User-Entscheid 2026-05-17):** leg_5 bleibt montiert und
wird einmal in worst-case-Pose geschwenkt (Coxa maximal Richtung leg_6).
`pulse_min`/`max` werden so kalibriert dass leg_6 leg_5 **physisch nicht
treffen kann** — Hardware-Sicherheit durch Pulse-Hard-Stops.

**Plan:** [`phase_10_stage_b_plan.md`](phase_10_stage_b_plan.md)
**Audit-Log:** [`phase_10_stage_b_calibration_log.md`](phase_10_stage_b_calibration_log.md)
**Sicherheits-Setup:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md)

**Was NICHT in Stage B ausgeführt wird:**
- **Kein Servo2040-Bringup** (Plugin bleibt aus, USB irrelevant)
- **Keine Bench-PSU** (bleibt AUS während Stage B; Tester nutzt eigene PSU)
- **Keine Stack-Validation** (kommt in Stage C/D/E)
- **Kein direction-Test** (Stage C/D/E)

---

## Bench-Setup (VOR allen Tests!)

> ⚡ **Sicherheits-Hinweis:** Stage B nutzt **nur die Tester-PSU**, nicht
> die Bench-PSU. Bench-PSU darf während Stage B angeschaltet sein, aber
> der OUTPUT muss AUS bleiben.

1. **Bench-PSU OUTPUT AUS** lassen (über die ganze Stage B)
2. **Servo2040 USB-Kabel** kann stecken oder nicht stecken — irrelevant
   für Stage B (Plugin wird nicht gestartet)
3. **HJ-Tester** bereitstellen:
   - Tester-Netzteil (eigenes PSU) verbinden
   - Tester einschalten
   - **Display-Check:** zeigt das Display einen µs-Wert? (z.B. „1500us")
     - Wenn nein: dann ist Stage B blockiert, Plan überdenken
   - **Drehknopf-Check:** dreht der Wert beim Knopf-Drehen?
4. **Tester-PSU-Spannung** auf **7.0 V** einstellen:
   - meistens am Tester ein Poti oder Schalter
   - Verifikations-Wert: Multimeter am Tester-Servo-Ausgang V+/GND →
     7.0 V ± 0.1 V
5. **leg_6-Mechanik-Check:**
   - Hexapod sitzt fest auf Stock-Halterung
   - leg_6 hängt frei nach unten (keine Verklemmungen)
   - alle 3 Servos sind elektrisch **abgeklemmt** (kein Y-Adapter
     oder Servo-Stecker am Servo2040)
6. **leg_5-Vorbereitung für Strategie B' (Self-Collision-Schutz):**
   - leg_5 ist **montiert** (nicht demontieren!)
   - leg_5-Coxa per Hand maximal Richtung leg_6 schwenken (= Bein
     zeigt nach vorne, Richtung +X-Achse, Richtung leg_6)
   - leg_5 loslassen — Servo-Getriebe-Friction sollte die Pose halten
   - Falls leg_5 zurückrutscht: mit Klebeband oder Schaumstoff
     temporär fixieren
   - **leg_5 bleibt in dieser Pose während der ganzen Stage B**
   - Sicht-Prüfung: leg_5 zeigt deutlich Richtung leg_6, nicht in
     passiver Default-Pose

---

## B.0 — Bench-Setup verifizieren (~5 min)

Vor dem ersten Joint-Schwenken nochmal die §1+§7 der `safety_setup.md`
durchgehen. Plus:

### B-T0 — Tester-Display-Check

```text
1. HJ-Tester einschalten (Tester-PSU AN)
2. Display sollte einen µs-Wert zeigen, z.B. "1500us"
3. Drehknopf etwas drehen → Wert ändert sich live
```

**Erwartung:** Display zeigt Pulsweite live beim Knopf-Drehen.

**Falls Display kaputt / fehlt:** Stage B kann mit reinem Drehknopf
ohne Display nicht zuverlässig durchgeführt werden. Stopp, Plan
überdenken — z.B. Multimeter im Frequenz-/Duty-Modus parallel
anschließen, oder direkt zu Stage C übergehen (Stack-Bringup macht
die Kalibrierung dann ohne Tester).

### B-T0.5 — Tester-PSU-Spannung verifizieren

```text
1. Multimeter im DC-V-Modus
2. + an Tester-Servo-Ausgang V+ (mittlerer Pin), - an GND (außen)
3. Wert ablesen
```

**Erwartung:** 7.0 V ± 0.1 V

**Falls anders:** Tester-PSU-Setting anpassen oder im Log notieren
(siehe §4 `phase_10_stage_b_calibration_log.md`).

---

## B.1 — Mech. End-Stop-Check stromlos (~15 min)

> **Sicherheits-Regel:** rein **stromlos**, ohne Tester angeschlossen.
> Servos sind passiv. Bein per Hand vorsichtig schwenken, **keine
> Gewalt** bei Anschlägen.

### B-T1 — leg_6_coxa-Joint (Self-Collision-Check mit leg_5)

> **Wichtig:** leg_5 ist in worst-case-Pose (aus B.0 Schritt 6). Wir
> messen nicht den max. Single-Leg-Anschlag, sondern den Punkt **5° vor
> Berührung mit leg_5**.

```text
1. leg_6 in geometrische Default-Pose bringen (Bein radial nach außen)
2. Coxa-Joint per Hand langsam in die Richtung drehen wo leg_6 zu leg_5
   wandert (= Richtung +Y oder hinten, je nach URDF)
3. Beobachten: Abstand leg_6 zu leg_5 wird kleiner
4. **STOPPEN ~5° vor Berührung** mit leg_5 (= ca. 1-2 cm Luft)
5. Winkel notieren als "Self-Collision-Anschlag" + Beschreibung
   "5° vor leg_5"
6. Coxa in die andere Richtung schwenken — hier ist Self-Collision
   meistens nicht das Problem; Anschlag-Ursache (Body / Servo) notieren
7. In Log §1.1 eintragen
```

**Erwartung:** asymmetrische Anschläge — Self-Collision-seitig enger
(~40–60° statt 90°), andere Richtung näher am URDF-Limit (~85–90°).

### B-T2 — leg_6_femur-Joint

```text
1. Coxa wieder radial außen, Femur passiv (hängt nach unten ~-90°)
2. Femur per Hand HOCH bewegen bis zum Anschlag
   (Bein schlägt nach vorne oder gegen Body-Bauch)
3. Anschlag-Ursache + Winkel notieren
4. Femur ganz nach unten (~ ursprüngliche passive Pose)
5. Femur unter horizontal drücken (Knie geht weiter nach unten/hinten)
   bis zum negativen Anschlag — Beobachtung wie weit das geht
6. Anschlag-Ursache + Winkel notieren
7. In Log §1.2 eintragen
```

**Erwartung:** Femur kann positiv (Bein hoch) bis ~+90° und negativ
(Bein nach hinten) variabel. Body-Kollision oder Servo-Mechanik.

### B-T3 — leg_6_tibia-Joint

```text
1. Coxa radial außen, Femur ~horizontal halten
2. Tibia per Hand in positive Richtung beugen (Knie zuklappen)
   bis zum Anschlag
3. Anschlag-Ursache + Winkel notieren
4. Tibia in negative Richtung beugen (Knie überstrecken)
   - meist sehr schnell mech. Anschlag durch Servo oder Bein-Geometrie
5. Anschlag-Ursache + Winkel notieren
6. In Log §1.3 eintragen
```

**Erwartung:** Tibia hat enge mech. Anschläge (~±80°), oft durch
Servo-Mechanik begrenzt. URDF-Limit ±86° = ±1.50 rad.

---

## B.2 — HJ-Tester Pre-Cal pro Servo (~30 min, ~10 min/Servo)

> **Wichtig:** Pro Servo Signal/V+/GND am Tester. **NIEMALS** parallel
> Tester + Servo2040 am selben Servo (Signal-Konflikt).

### B-T4 — leg_6_coxa Pre-Cal (Pin 15, Diymore 8120MG)

#### Anschluss (Tester-PSU AUS während Stecken!)

```text
1. Tester-PSU AUS (Tester-Schalter)
2. Servo-Stecker von leg_6_coxa-Servo identifizieren (an Servo selbst,
   nicht Servo2040)
3. Stecker am Tester-Servo-Anschluss anstecken
   - Signal = gelb/orange/weiß auf Tester-Signal-Pin
   - V+ = rot auf Tester-V+-Pin
   - GND = braun/schwarz auf Tester-GND-Pin
4. Sichtprüfung: korrekte Polarität
5. Tester-PSU AN
6. Tester-Display zeigt aktuellen Default-µs-Wert (oft 1500 µs)
```

**Erwartung:** Coxa-Servo bewegt das Bein leicht (auf 1500 µs sollte
Bein nahe Radial-Default sein, ±20°).

#### pulse_zero finden

```text
1. Tester-Drehknopf langsam in beide Richtungen drehen
2. Visuell: Coxa-Joint-Mitte = Bein 90° vom Body radial außen
3. Wert ablesen, im Log §2.1 eintragen
```

#### pulse_min finden (Self-Collision-sicher)

```text
1. Tester-Drehknopf langsam in die Richtung drehen wo leg_6 zu leg_5
   wandert
2. Coxa-Joint schwenkt das Bein, Abstand zu leg_5 verkleinert sich
3. **STOPPEN ~5° vor Berührung mit leg_5** (= ca. 1-2 cm Luft)
4. Wert vom Tester-Display ablesen → pulse_min
5. Im Log §2.1 eintragen, Notiz: "5° vor Self-Collision mit leg_5"
6. Falls Servo brummt: SOFORT zur Mitte zurück (= bereits Stall)
```

#### pulse_max finden

```text
1. Tester-Drehknopf langsam in die ANDERE Richtung drehen (weg von leg_5)
2. Hier ist Self-Collision meist kein Thema → bis Single-Leg-Anschlag
   oder URDF-Limit (was zuerst kommt), dann +5–10 µs Sicherheitsabstand
3. Wert ablesen, im Log §2.1 eintragen
```

#### Sanity + Plausibilität

```text
1. Werte vergleichen: pulse_min < pulse_zero < pulse_max ?
2. Alle in [800, 2200] µs ?
3. Spannweite ~800–1000 µs für ±90°-Range erwartet
4. Checkbox-Liste in Log §2.1 ankreuzen
```

#### Abklemmen

```text
1. Tester-PSU AUS
2. Servo-Stecker vom Tester abnehmen
3. Servo bleibt mechanisch am Bein montiert, ist elektrisch komplett ab
```

### B-T5 — leg_6_femur Pre-Cal (Pin 16, Miuzei MS61)

Analog B-T4, aber:

- **Visuelle Joint-Mitte:** Femur horizontal zum Boden (User muss
  Bein dabei gegen Schwerkraft halten, weil passive Pose = -90°)
- **Bei pulse_zero-Mess:** Bein-Hand frei oder gestützt? → Stützen
  empfohlen, gibt stabilere Werte
- Erwartete Spannweite analog Coxa (~800–1000 µs für ±90°)

### B-T6 — leg_6_tibia Pre-Cal (Pin 17, Miuzei MS61)

Analog B-T4, aber:

- **Visuelle Joint-Mitte:** Knie gerade, Tibia in Verlängerung des Femur
- **Passive Tibia-Pose** ist bereits ~gestreckt = nahe Joint-Mitte →
  weniger aktives Halten nötig als bei Femur
- Erwartete Spannweite enger als Coxa/Femur (~900 µs für ±86°)

---

## B.3 — YAML konsolidieren (Claude-Arbeit, ~10 min)

Nach B-T4/T5/T6 grün:
- User meldet Werte aus Log §2.1/§2.2/§2.3 an Claude
- Claude trägt die Werte ins `src/hexapod_hardware/config/servo_mapping.yaml`
  für Pin 15/16/17 ein
- Claude committed mit Commit-Message
  `phase10: leg_6 servo pre-calibration values from HJ tester`
  (oder User macht das, je nach Workflow)
- Log §3 aktualisiert mit „Konsolidiert am [ISO-Date]"

---

## B.4 — CI-Regression-Check (Claude, ~5 min)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_description hexapod_hardware hexapod_bringup
source install/setup.bash
colcon test --packages-select hexapod_hardware hexapod_bringup --event-handlers console_direct+
```

**Erwartung:**
- Build: 3 packages finished, 0 errors
- Test: hexapod_hardware 208/0/20, hexapod_bringup 18/0/0 (= identisch zu Stage-A-Endstand)

---

## Fehlerdiagnose-Tabelle

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| Tester-Display zeigt nichts | Tester-PSU nicht an, oder Tester defekt | Tester-PSU prüfen; falls Tester defekt, Stage B blockiert |
| Servo bewegt sich nicht beim Tester-Drehen | Verkabelung (GND/Signal vertauscht, oder schlechter Kontakt im Stecker) | Stecker neu stecken, Polaritäts-Check |
| Servo brummt am vermeintlichen Anschlag | Tester gibt Pulsweite jenseits mech. Anschlag → Stall | SOFORT zurückdrehen Richtung Mitte; pulse_min/max mit größerem Sicherheitsabstand notieren |
| pulse_zero scheint visuell nicht in der Mitte | Servo-Streuung (typisch ±50 µs), oder Augenmaß-Fehler | mehrmals messen + mitteln; falls > ±100 µs Streuung: Servo evtl. mech. ausgehakt, Bein-Montage prüfen |
| pulse_min > pulse_zero (Reihenfolge falsch) | Tester-Drehrichtung vs. Servo-Drehrichtung verwechselt | Werte tauschen oder neu messen — das ist NICHT direction (direction kommt Stage C) |
| Tester-PSU springt in CC bei Bein-Bewegung | Servo zieht hohen Strom (vermutlich Stall am Anschlag) | sofort zur Mitte, Tester-PSU-CC-Limit checken (sollte ~1 A bei Diymore, ~2 A bei Miuzei reichen) |
| Coxa-Anschlag schlägt gegen anderes Bein (leg_5 oder leg_1) | leg_5/leg_1 sind beim aktuellen Aufbau auch montiert | normal, nur dokumentieren als "Self-Collision mit leg_5"; pulse_min/max entsprechend enger setzen |

---

## Done-Kriterium Stage B (User-Smoke-Anteil)

User bestätigt:
- [ ] B-T0 + B-T0.5: Bench-Setup verifiziert
- [ ] B-T1 + B-T2 + B-T3: Mech. End-Stop-Check für 3 Joints im Log §1
- [ ] B-T4 + B-T5 + B-T6: Tester-Pre-Cal für 3 Servos im Log §2
- [ ] Log-Plausibilitäts-Checkboxes in §2.1/§2.2/§2.3 alle abgehakt
- [ ] Werte an Claude für B.3-Konsolidierung gemeldet

Claude bestätigt:
- [ ] B.3: YAML konsolidiert für Pin 15/16/17
- [ ] B.4: CI-Regression-Check grün
- [ ] Log §3 mit Konsolidierungs-Datum gefüllt
- [ ] Self-Review-Tabelle im `phase_10_progress.md`
