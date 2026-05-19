# Phase 8 — Strom- & Elektronik-Bench

**Dauer-Schätzung:** 1–2 Tage (vor allem Verkabelungs- und Mess-Disziplin)
**Maschine:** nur Bench, kein ROS2-Stack
**Vorbedingung:** Phase 7 abgeschlossen, Firmware-Repo läuft mit
Sicherheits-Ebenen

---

## Ziel

Komplettes Bench-Strom-Setup aufbauen und vermessen, **ohne echte Hexapod-
Servos**, **ohne Akku**. Versorgung erfolgt komplett über die Bench-PSU
(RND Lab RND320-KA3305P). Pi wird über einen DCDC-Wandler an der gleichen
PSU versorgt — simuliert die spätere Akku-Topologie, ist aber sicherer
und reproduzierbar.

Am Ende dieser Phase steht ein verkabeltes Bench, an dem in Phase 9 und 10
gefahrlos Tests gemacht werden können.

---

## Hardware-Setup für diese Phase

- Bench-PSU RND Lab RND320-KA3305P (parallel-fähig 10 A), eigene Sicherung
  ab 10 A — **ausreichend** als Primärschutz, kein zusätzliches Sicherungs-
  Element nötig
- DCDC-Wandler (passender Typ für 6–9 V → 5 V ≥ 3 A) — wird in dieser
  Phase ausgewählt und beschafft, falls nicht schon vorhanden
- Servo2040 (aus Phase 7) — Trace-Cut erledigt, USB nur Daten
- Raspberry Pi 4 (8 GB) — wird hier nur stromseitig integriert, OS-Setup
  kommt in Phase 12
- XT60-Kabel 3 m (vom User vorhanden)
- Bulk-Caps am Servo-Rail (1000 µF Elko + 100 nF Keramik)
- Multimeter
- Optional: Strommess-Zange, Oszi

---

## Done-Kriterien

1. DCDC-Wandler beschafft und montiert
2. Verkabelungsplan in `phase_8_progress.md` dokumentiert
3. GND-Stern verifiziert (Multimeter Continuity)
4. Bulk-Caps am Servo-Rail montiert
5. Bench-PSU → DCDC → Pi-5V stabil, kein Spannungsabfall < 4,8 V
6. Servo2040 V+ vom PSU versorgt, USB als Datenverbindung zum Desktop
7. Pi bootet sauber über DCDC, `ls /dev/ttyACM*` zeigt Servo2040
8. Servo2040-Spannungs-ADC liest plausiblen Wert (Phase-7-Firmware liest
   `vrail_mv` über Protokoll-Frame, Wert ~7,4 V)

---

## Stufen

### Stufe A — DCDC-Wandler-Wahl

**Ziel:** Den richtigen Wandler beschaffen, Specs dokumentieren.

#### A.1 Spec festlegen

- Eingangsspannung: **6–9 V** (passend zu späterem 2S-LiPo bzw. Bench-PSU
  auf 7,4 V eingestellt)
- Ausgangsspannung: 5 V
- Ausgangsstrom: ≥ 3 A (Pi 4 kann unter Last ~2,5 A ziehen)
- Wirkungsgrad: möglichst > 85 %
- Schutzfunktionen: Kurzschluss, Überstrom, thermisch

#### A.2 Kandidaten

- **Pololu D24V50F5** — 5 V / 5 A, 4,5–22 V Eingang, kompakt, gut dokumentiert
- **Hobbywing UBEC / Castle CC BEC** — RC-Bereich, für 2–6S LiPo gebaut
- Andere: nach Verfügbarkeit

Auswahl-Entscheidung in `phase_8_progress.md` mit Datum festhalten.

#### A.3 Beschaffung + Eingangstest

- Wandler einzeln am Bench-PSU testen: Eingang 7,4 V, Ausgang gemessen
  bei verschiedenen Lasten (idle, 1 A Last, 2 A Last)
- Spannung darf nicht unter 4,8 V einbrechen
- Rippelmessung mit Oszi optional aber empfehlenswert

**Done-Kriterium A:**
1. Wandler beschafft und ausgepackt
2. Idle/Last-Test mit Bench-PSU bestanden
3. Specs in `phase_8_progress.md`

---

### Stufe B — Verkabelungsplan zeichnen

**Ziel:** Bevor Kabel verlötet werden: Topologie auf Papier/in der Doku.

```
Bench-PSU (7,4 V, 10 A Limit) ──XT60──┬──→ Servo2040 V+ (Servo-Rail)
                                       │
                                       └──→ DCDC-Eingang
                                             │
                                             └──→ Pi 5V (via USB-C-Stecker
                                                          ans Pi-USB-C-Power)

GND (Stern!):
  PSU-GND ──┬── Servo2040-Power-GND
            ├── Servo2040-Logic-GND (sollte board-intern verbunden sein, messen!)
            ├── DCDC-Eingangs-GND
            └── DCDC-Ausgangs-GND ── Pi-GND
```

Wichtige Punkte:
- **Sicherung sitzt in der PSU** (10 A), kein externer Schalter/keine
  externe Sicherung nötig
- USB-Kabel Servo2040 ↔ Desktop ist **nur Datenverbindung**, **keine**
  Stromversorgung — der Trace-Cut auf dem Servo2040 trennt das bereits
- Pi 5V kommt aus dem DCDC, nicht aus dem Desktop-USB
- USB-Kabel Servo2040 ↔ Pi (später in Phase 12) ist ebenfalls nur Daten

Skizze in `phase_8_progress.md` ergänzen (ASCII reicht, oder Foto einer
Handzeichnung).

**Done-Kriterium B:**
1. Topologie-Skizze in der Doku
2. Anschluss-Stellen identifiziert, Kabel-Querschnitte festgelegt
   (Empfehlung: Servo-Rail mit 1,5 mm² wegen Lastspitzen, DCDC-Eingang
   mit 0,75 mm² ausreichend)

---

### Stufe C — Verdrahtung & GND-Stern

**Ziel:** Verkabelung physisch umsetzen, GND-Stern mit Multimeter prüfen.

#### C.1 Verdrahten

- XT60-Stecker (oder XT60H) ans PSU-Output-Kabel
- Servo-Rail-Klemmen am Servo2040 verschrauben
- DCDC-Eingang anschließen
- DCDC-Ausgang an Pi-Stromzufuhr (USB-C oder GPIO-5V — Vorsicht bei
  GPIO-5V: kein Rückspeise-Schutz, USB-C ist sicherer)

#### C.2 GND-Stern verifizieren

Multimeter im Continuity-Mode:

- Pi-GND ↔ Servo2040-Power-GND: < 0,5 Ω
- Servo2040-Logic-GND ↔ Servo2040-Power-GND: durchgängig (board-intern
  verbunden, trotzdem messen — der Trace-Cut könnte versehentlich GND
  mit getroffen haben)
- PSU-GND ↔ alle drei GND-Punkte: durchgängig
- DCDC-Eingangs-GND ↔ DCDC-Ausgangs-GND: oft galvanisch verbunden bei
  Nicht-isolierten Wandlern, sollte 0 Ω sein

#### C.3 Bulk-Caps am Servo-Rail

- 1000 µF Elko (Polarität!) + 100 nF Keramik parallel
- So nah wie möglich an die Servo2040-Schraubklemmen V+/GND
- Polarität-Check **zweimal** vor dem ersten Power-On (Elko verkehrt
  herum = Knall)

**Done-Kriterium C:**
1. Verkabelung verlötet/verklemmt, mechanisch sauber
2. GND-Stern mit Multimeter bestätigt
3. Bulk-Caps montiert, Polarität korrekt

---

### Stufe D — Erst-Power-Up (ohne Servos, ohne Pi-Boot)

**Ziel:** Strom-Topologie verifizieren bevor Pi und Servos angeschlossen
werden.

#### D.1 Erst-Power-Up

PSU auf **7,4 V**, Strombegrenzung **0,5 A**, alles verkabelt:

1. PSU aus, XT60 noch nicht eingesteckt.
2. PSU einschalten, Spannung 7,4 V am PSU-Display verifizieren.
3. XT60 einstecken → kurzer Inrush durch Bulk-Caps (CC-Limit greift evtl.
   einmal kurz, OK).
4. Strom am PSU sollte nach Inrush auf ~0 A zurückfallen.
5. **Messen:**
   - Spannung an Servo2040 V+ (sollte 7,4 V sein)
   - Spannung am DCDC-Ausgang (sollte 5,0 ± 0,1 V sein)
6. PSU **ausschalten** vor nächstem Schritt.

#### D.2 Pi-Boot-Test

7. Pi via USB-C-Kabel an DCDC-Ausgang anschließen.
8. PSU wieder einschalten, **Strom-Limit auf 2 A** hochsetzen.
9. Pi bootet, Strom-Monitor am PSU beobachten:
   - Idle: ~0,4 A
   - Boot-Peak: ~0,8 A
   - **Spannung darf nicht unter 4,8 V einbrechen** (am DCDC-Ausgang messen)

#### D.3 Servo2040 USB ans Desktop (kein Pi!)

Für Phase 8 reicht es, wenn der Servo2040 weiter am Desktop hängt:

10. Servo2040 USB-Kabel ans **Desktop** (nicht Pi).
11. `ls -l /dev/ttyACM*` am Desktop → Servo2040 sichtbar.
12. Vom Desktop aus die Firmware-Test-Tools aus Phase 7 ausführen können.

> **Hinweis:** Das Umstecken auf den Pi passiert in Phase 12. In Phase 8
> und 9 bleibt Servo2040 am Desktop.

**Done-Kriterium D:**
1. PSU-Ausgang stabil 7,4 V
2. DCDC-Ausgang stabil 5,0 V auch unter Pi-Boot-Last
3. Servo2040 vom Desktop als `/dev/ttyACM*` erkennbar
4. Pi bootet sauber, keine Spannungseinbrüche

---

### Stufe E — Servo-Rail-Diagnose über Firmware

**Ziel:** Verifikation, dass die Phase-7-Firmware den Servo-Rail korrekt
misst.

#### E.1 Spannungsmessung

Über das Phase-7-Protokoll-Frame `GET_STATE` den Wert `vrail_mv` lesen.

- Bei PSU = 7,4 V sollte `vrail_mv` ≈ 7400 ± 100 mV sein.
- PSU runterregeln auf 6,0 V → Warning-Frame `WARN_LOW_VOLTAGE` sollte
  vom Servo2040 kommen.
- PSU weiter runter auf 5,7 V → `disable_all_servos`-Trip + Status-Frame
  `UNDERVOLTAGE_TRIPPED`.
- PSU zurück auf 7,4 V → manueller Reset-Frame `0x05 RESET` von Host an
  Servo2040, normaler Betrieb.

#### E.2 Stromtest mit Test-Servo

- Einen Test-Servo (aus Phase-7-Pool) am Output 0 anschließen.
- Bewegen lassen.
- `current_mA[0]` über `GET_STATE` lesen — sollte plausibel im einstelligen
  bis dreistelligen mA-Bereich liegen.

**Done-Kriterium E:**
1. `vrail_mv` plausibel
2. Low-Voltage-Trip funktioniert mit PSU-Stellrad
3. Strommessung an Test-Servo plausibel

---

### Stufe F — Phase-8-Abschluss

- `phase_8_progress.md` finalisieren mit:
  - DCDC-Modell + Spec
  - Verkabelungsskizze
  - Mess-Werte (PSU/DCDC/Pi-Spannungen unter Last)
  - Foto des Bench-Setups (optional, hilft beim Wiederaufbau)
- Git-Commit (nur Docs)
- Tag `phase-8-done`
- `PHASE.md` aktualisieren

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Pi bootet nicht / hängt im Boot | DCDC liefert nicht genug Strom oder Spannungssag | Strom-Limit am PSU prüfen, DCDC-Specs verifizieren, USB-Kabel-Querschnitt prüfen |
| Servo2040 zeigt sich nicht als `/dev/ttyACM*` | dialout-Gruppe, Kabel, USB-Port | `dmesg`, `lsusb`, `sudo usermod -aG dialout $USER` neu einloggen |
| `vrail_mv` liest 0 oder Müll | ADC-Pin falsch verdrahtet, Spannungsteiler kaputt | Pimoroni-Schaltplan prüfen, Pin-Mapping in Firmware |
| Knall beim Power-On | Elko verpolt oder Kurzschluss | PSU sofort aus, Verkabelung neu prüfen |
| Hohe Standby-Verluste | DCDC ineffizient bei niedriger Last | Akzeptieren (Bench-Phase) oder anderen DCDC wählen |
| GND-Stern misst > 1 Ω | Schlechte Klemmverbindung, Kabel zu dünn | Crimps prüfen, Kabel-Querschnitt erhöhen |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Akku-Anschluss (LiPo, Charger, Safe-Bag — alles auf Phase 13+)
- Keine echten Hexapod-Servos (nur 1 Test-Servo aus Phase-7-Pool für Stufe E)
- Kein ROS2-Stack (Servo2040 wird per Python-Test-Skript aus Phase 7
  angesprochen)
- Keine Pi-OS-Installation (kommt in Phase 12)
- Kein Mainline-Mounting im Roboter (Bench bleibt Bench)

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–E Done-Kriterien erfüllt
- [ ] Verkabelungsskizze in `phase_8_progress.md`
- [ ] Mess-Werte dokumentiert
- [ ] DCDC-Modell + Spec im Progress-File
- [ ] Git-Commit + Tag `phase-8-done`
- [ ] `PHASE.md` auf Phase 9 aktualisiert
- [ ] Retrospektive in `phase_8_progress.md`
