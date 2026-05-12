# Phase 7 — Servo2040 Firmware

**Dauer-Schätzung:** offen — neue Domäne (Embedded-Firmware), Kalenderzeit nicht Story-Points
**Maschine:** nur Desktop (Servo2040 hängt per USB am Desktop)
**Vorbedingung:** Phase 6 abgeschlossen
**Repo:** **eigenes Git-Repo** außerhalb von `hexapod_ws` (Name + Ort wird in Stufe A festgelegt)

---

## Ziel

Eine eigenständige C++-Firmware für das **Pimoroni Servo2040**-Board, die:

1. Vom Host (Desktop oder später Pi) über USB-CDC Sollwert-Frames für bis
   zu 18 Servos entgegennimmt
2. Pro Servo ein **Hard-Clamp** auf kalibrierte Pulse-Min/Max anwendet
3. Einen **Watchdog** hat: ohne gültiges Frame vom Host > Timeout → alle
   Servos stromlos
4. **Soft-Ramp** macht: max. ΔPulse pro Tick, kein Sprung-Sollwert kommt
   physisch beim Servo an
5. **Strom-Limits** pro Servo und total durchsetzt (Current-Sense-API
   des Servo2040)
6. **Low-Voltage-Cutoff** für den Servo-Rail bietet (vorbereitet, auch
   wenn Akku erst später kommt)
7. Beim Boot **gestaffelt** enabled (siehe Stufe D — zentrale offene Frage)

Die Firmware kennt **kein ROS2**. Sie ist nur das Bindeglied zwischen einem
Host und 18 PWM-Kanälen, mit Sicherheits-Logik dazwischen.

---

## Hardware-Setup für diese Phase

- **Servo2040-Board** (Pimoroni, RP2040, 18-Kanal) — vorhanden, Trace-Cut
  bereits durchgeführt (Servo-Power kommt extern, USB nur Daten)
- **Bench-PSU** RND Lab RND320-KA3305P, parallel-fähig (10 A)
- **2–3 schwache Test-Servos** (vom User vorhanden, können nichts kaputt
  machen) — ein Pool zum Ausprobieren
- **USB-Kabel** Servo2040 ↔ Desktop
- **Multimeter** (Spannung, Strom)
- **Optional, dringend empfohlen:** Pi Pico Debug-Probe (SWD) für
  Firmware-Debugging
- **Optional:** Logic-Analyzer oder Oszi für PWM-Verifikation

Hersteller-Referenz (in Stufe A lokal nach `docs_raspi/refs_phase_7/`
herunterladen):
- Produktseite: https://shop.pimoroni.com/products/servo-2040
- Pimoroni `pimoroni-pico` SDK-Repo
- Pi Pico SDK (`pico-sdk`)

---

## Done-Kriterien

1. Servo2040-Firmware-Repo lokal aufgesetzt, mit eigener `CLAUDE.md` und
   eigenem README
2. Protokoll-Spezifikation eingefroren und im Repo dokumentiert
3. Pimoroni-API-Frage **Per-Servo-Enable** verifiziert (siehe Stufe D):
   entweder funktional ODER dokumentierter Fallback
4. Hard-Clamp greift bei Out-of-Range-Sollwert (Test bestanden)
5. Watchdog disabled alle Servos bei USB-Disconnect (hörbar/messbar
   verifiziert)
6. Soft-Ramp verifiziert (kein Sprung-Sollwert kommt durch)
7. Strom-Limit pro Servo disabled bei manueller Blockade (Stall-Test)
8. Low-Voltage-Cutoff-Logik vorhanden (auch wenn Akku noch nicht angeschlossen)
9. Standalone-Test: 2–3 Test-Servos fahren definiert per Python-Test-Script
   (kein ROS2 nötig)

---

## Stufen

### Stufe A — Repo-Aufsetzung & SDK-Review

**Ziel:** Eigenes Firmware-Repo, Pimoroni- und Pico-SDK lokal, Build läuft.

#### A.1 Bestehenden Code-Stand sichten

Der User hat bereits einen ersten Wurf in einer GitHub-Repo. Diese in
Stufe A klonen und sichten — **nicht 1:1 übernehmen**, sondern als Vorlage
zum Verstehen, was schon da war und welche Probleme der User damals
hatte (insbesondere: Per-Servo-Enable funktionierte nicht).

- Repo-URL vom User
- Klonen nach `~/hexapod_servo2040_fw_old/` zur Referenz (nicht das
  Arbeits-Repo!)
- Code lesen, Notizen in `phase_7_progress.md`

#### A.2 Neues Repo anlegen

- Name + Ort: **wird hier festgelegt**, Vorschlag `~/hexapod_servo2040_fw/`
- Eigene `CLAUDE.md` mit:
  - Sprache: C++ (Pimoroni-SDK)
  - Build-System: CMake + Pico-SDK
  - Coding-Konventionen
  - Hinweis: **kein ROS2** in diesem Repo
  - Protokoll-Definition als verbindlicher Anhang (entsteht in Stufe B)
- `README.md` mit Quickstart (Flashen, Test-Skript)
- `.gitignore` (build-Artefakte, IDE-Configs)

#### A.3 Pico-SDK + Pimoroni-Libs

- Pico-SDK als Submodul oder Pfad
- Pimoroni `pimoroni-pico` als Submodul (für `Servo`-Klasse, `ServoCluster`,
  `analog`-API)
- CMakeLists, leeres `main.cpp` baut grün
- Erstes Hello-World-Flash auf das Servo2040 (LED blinkt o. ä.)

#### A.4 Hersteller-Doku lokal archivieren

`docs_raspi/refs_phase_7/`:
- Servo2040-Schaltplan-PDF (von Pimoroni)
- Pinout-Übersicht
- Datasheet RP2040 (für PIO / ADC)

> **Hinweis:** das `refs_phase_7/`-Verzeichnis ist **lokal**, nicht
> committet (Lizenz der Pimoroni-Materialien beachten).

**Done-Kriterium A:**
1. Bestehender User-Code lokal geklont, gesichtet, Notizen
2. Neues leeres Repo mit CLAUDE.md/README/.gitignore
3. Build-System grün, Hello-World flashbar
4. Hersteller-Doku lokal verfügbar

---

### Stufe B — Pimoroni-API-Review & Protokoll-Definition

**Ziel:** Vor irgendeinem Code-Schreiben: was bietet die Pimoroni-API
genau, und welches Wire-Protokoll fahren wir.

#### B.1 Pimoroni-API systematisch durchgehen

Aktiv verifizieren — was im README steht ist nicht immer was die SDK
aktuell hergibt:

- **PWM-Frequenz pro Kanal:** welche Werte sind unterstützt? Digital-Servos
  vertragen meist 250–333 Hz, muss aber für unseren konkreten Servo-Typ
  empirisch bestätigt werden.
- **Per-Servo `enable()`/`disable()`-API:** existiert sie auf der
  `Servo`-Einzelklasse? Auf `ServoCluster`? **Zentrale offene Frage aus
  Phase-7-Planung** — siehe Stufe D.
- **Current-Sense-API:** wie wird gemultiplext, welche ADC-Range,
  Konversionsfaktor zu Ampere?
- **Servo-Rail-Spannungsmessung:** welcher ADC-Pin, welcher Teiler?
- **USB-CDC:** Standard-CDC-ACM (Pi sieht `/dev/ttyACMx`) oder Custom
  Bulk-Endpoint?

Erkenntnisse in `phase_7_progress.md` Stufe B festhalten.

#### B.2 Protokoll definieren

Vorschlag, in Stufe B final festzunageln:

**Frame-Format** (Binary, COBS-framed über USB-CDC):

```
[SEQ:1] [CMD:1] [LEN:1] [PAYLOAD:LEN] [CRC16:2]
```

**Kommandos** (Beispiele, anzupassen):

| Code | Name | Richtung | Payload |
|---|---|---|---|
| `0x01` | `SET_TARGETS` | Host → Servo2040 | 18 × int16 Pulse-µs |
| `0x02` | `GET_STATE` | Host → Servo2040 | — |
| `0x02` (Antwort) | `STATE` | Servo2040 → Host | 18 × int16 last_pulse, 18 × uint16 current_mA, voltage_mV, status_flags |
| `0x03` | `ENABLE_SERVO` | Host → Servo2040 | servo_idx (uint8), on/off (uint8) |
| `0x04` | `SET_CALIBRATION` | Host → Servo2040 | servo_idx, pulse_min, pulse_max (optional persistent in Flash?) |
| `0x05` | `RESET` | Host → Servo2040 | — |
| `0x7F` | `ERROR_REPORT` | Servo2040 → Host (unsolicited) | error_code, servo_idx |

**Design-Entscheidungen** im Repo dokumentieren:

- **Wire-Format Pulse-µs vs. Joint-rad?**
  Empfehlung: **Pulse-µs auf dem Wire**, Host (= `hexapod_hardware`) macht
  die Joint-rad → Pulse-µs-Konversion mit Kalibrierungs-Tabelle. Hält die
  Firmware dumm und unabhängig von URDF-Werten.
- **Update-Rate Host → Servo2040:** 50 Hz reicht (gait_node läuft mit 50 Hz),
  100 Hz als Headroom OK.
- **Bytes/Sekunde-Budget:** 50 Hz × ~50 Byte/Frame = 2,5 kB/s — USB-CDC hat
  1+ MB/s Bandbreite, kein Engpass.

#### B.3 Protokoll im Repo dokumentieren

`PROTOCOL.md` im Firmware-Repo:
- Frame-Format
- Kommando-Tabelle mit Payload-Layout (Byte-genau)
- CRC-Spezifikation (Polynom, Init-Wert, Reflect-Strategie)
- Beispiel-Frames als Hex-Dump
- Error-Code-Tabelle

**Done-Kriterium B:**
1. Pimoroni-API-Erkenntnisse dokumentiert, insbesondere Antwort zu
   PWM-Frequenz, Per-Servo-Enable, Current-Sense, USB-CDC
2. `PROTOCOL.md` final, Frame-Format eingefroren
3. Design-Entscheidung Pulse-µs vs. Joint-rad festgehalten

---

### Stufe C — Sicherheits-Ebenen 1, 2, 5 implementieren

**Ziel:** Die drei Ebenen, die **keine** echten Servos brauchen, zuerst
bauen und mit losen Test-Servos verifizieren. Reihenfolge nicht zufällig:
Watchdog + Hard-Clamp + Soft-Ramp sind die, die einen Software-Bug am Host
hardwareseitig abfangen.

#### C.1 Ebene 1 — Hard-Clamp pro Servo

Pro Servo: kalibrierte `pulse_min[i]` / `pulse_max[i]` als Konstanten
(später optional aus Flash). Im PWM-Output-Pfad **vor** der Hardware:

```cpp
if (target_pulse < pulse_min[i]) target_pulse = pulse_min[i];
if (target_pulse > pulse_max[i]) target_pulse = pulse_max[i];
```

**Verifikation:** Host schickt absichtlich Out-of-Range-Pulse, Logic-Analyzer
oder Oszi am Servo-Pin zeigt: Pulse bleibt am Clamp-Wert kleben.

#### C.2 Ebene 2 — Watchdog

```cpp
static uint32_t last_valid_frame_ms = 0;

void on_frame_received() {
    last_valid_frame_ms = millis();
}

void watchdog_tick() {
    if (millis() - last_valid_frame_ms > WATCHDOG_TIMEOUT_MS) {
        disable_all_servos();          // PWM-Output deaktivieren
        state = WATCHDOG_TRIPPED;
    }
}
```

`WATCHDOG_TIMEOUT_MS` = 200 ms als Default (50 Hz Host = 20 ms Frame-Abstand,
200 ms = 10 verpasste Frames Toleranz).

**Verifikation:** USB-Kabel ziehen während ein Test-Servo bewegt wird →
Servo wird stromlos (hörbar — Servo wird „weich", lässt sich von Hand
verdrehen).

#### C.3 Ebene 5 — Soft-Ramp

```cpp
// max ΔPulse pro Tick — z.B. 20 µs/Tick bei 100 Hz = 2000 µs/s
int16_t delta = target_pulse - current_pulse[i];
if (abs(delta) > MAX_DELTA_PER_TICK) {
    delta = (delta > 0 ? 1 : -1) * MAX_DELTA_PER_TICK;
}
current_pulse[i] += delta;
servo[i].set_pulse(current_pulse[i]);
```

**Verifikation:** Host schickt sofortigen Sprung von 1000 µs auf 2000 µs.
Test-Servo fährt rampig in ~500 ms, nicht in einem Sprung. Oszi-Trace
zeigt die Rampe.

**Done-Kriterium C:**
1. Hard-Clamp greift, Out-of-Range-Test bestanden
2. Watchdog greift bei USB-Disconnect
3. Soft-Ramp verhindert Sprung-Sollwerte
4. Test-Skript am Host (Python + pyserial) kann diese drei Tests automatisiert
   fahren

---

### Stufe D — Per-Servo-Enable verifizieren (zentrale offene Frage)

**Ziel:** Klären, ob 18 Servos gestaffelt enabled werden können oder ob
alle gleichzeitig anlaufen.

> **Hintergrund:** Der User hat in seinem ersten Firmware-Wurf erlebt,
> dass die Servos beim `enable()` alle gleichzeitig auf ihre Zielposition
> losgelaufen sind. Das erzeugt einen großen Inrush-Strom-Peak und sieht
> mechanisch schlecht aus. Wir wollen das vermeiden.
>
> **Hypothese:** Auf der `Servo`-Einzelklasse (eine Instanz pro PWM-Pin)
> sollte `enable()`/`disable()` pro Servo unabhängig funktionieren. Auf
> `ServoCluster` (zentraler PIO-State-Machine-Treiber für alle 18) ist
> das eher schwierig.

#### D.1 Test mit 2 Servos, Einzelklasse

```cpp
Servo s0(SERVO_0_PIN);
Servo s1(SERVO_1_PIN);

s0.value(0.0);     // Mitte
s1.value(0.0);

s0.enable();
sleep_ms(500);
s1.enable();       // 500 ms später
```

**Beobachten:**
- Läuft `s0` los, wenn `s1` noch disabled ist? (Erwartet: ja)
- Läuft `s1` erst los, wenn enabled wird? (Erwartet: ja)
- Strom-Profil am PSU: zwei getrennte Inrush-Peaks oder ein gemeinsamer?

#### D.2 Test mit allen 18, gestaffelt

Wenn D.1 funktioniert:

```cpp
for (int i = 0; i < 18; i++) {
    servos[i].value(stand_pose_normalized[i]);
}
for (int i = 0; i < 18; i++) {
    servos[i].enable();
    sleep_ms(50);   // 18 × 50 ms = 900 ms total
}
```

Mit 2–3 Test-Servos (Rest unbestückt), die in unterschiedlichen
Stand-Positionen sind. Beobachten ob sie nacheinander anlaufen.

#### D.3 Wenn `Servo` einzeln nicht reicht — `ServoCluster`-Pfad

Falls die `Servo`-Einzelklasse nicht 18 unabhängige PIO-State-Machines
hergibt (RP2040 hat 2 PIOs × 4 SM = 8 SMs, das könnte zu wenig sein
für 18 separate Kanäle), umstellen auf `ServoCluster`:

- Vorab alle 18 `target_pulse[i] = stand_pose_us[i]` setzen
- Dann `cluster.enable_all()` — alle laufen los, aber zu **identischen
  Zielen wenn vorher manuell vorpositioniert**, also minimale Bewegung
- Soft-Ramp (Stufe C.3) macht den Rest

#### D.4 Fallback-Dokumentation

Worst-Case wenn weder D.1 noch D.3 sauber funktioniert: Workflow-Doku
„Beine vor Power-On mechanisch vorpositionieren":
- Bilder der erwarteten Vor-Boot-Pose pro Bein
- Toleranz: ±10° pro Joint genügt mit Soft-Ramp
- Wird in Phase 10/12-Doku referenziert

**Done-Kriterium D:**
1. Erkenntnis dokumentiert: welcher der drei Pfade (D.1/D.3/D.4) funktioniert
2. Boot-Sequenz-Implementierung im Firmware-Code
3. Wenn D.4: Vor-Boot-Pose-Doku angelegt

---

### Stufe E — Strom-Limits & Low-Voltage-Cutoff

**Ziel:** Sicherheits-Ebenen 3, 4 und Low-Voltage. Brauchen Current-Sense,
sind also ohne echten Last-Test schwierig — werden mit 1–2 Test-Servos
unter manuellem Stall-Test verifiziert.

#### E.1 Ebene 3 — Per-Servo Strom-Limit

```cpp
// Current-Sense Mux durchschalten, ADC samplen
uint16_t current_ma = read_servo_current(i);
current_avg[i] = (7 * current_avg[i] + current_ma) / 8;   // Glättung

if (current_avg[i] > STALL_THRESHOLD_MA[i]) {
    disable_servo(i);
    send_error_frame(ERR_SERVO_OVERCURRENT, i);
}
```

`STALL_THRESHOLD_MA[i]` zunächst konservativ — 80 % des Datenblatt-
Stallstroms pro Servo-Typ. Für die schwachen Test-Servos: nachschauen,
für die echten 20/35-kg-Servos in Phase 10 endgültig kalibrieren.

**Verifikation:** Test-Servo manuell mit der Hand blockieren → Servo wird
stromlos, Error-Frame am Host sichtbar (Python-Test-Skript loggt).

#### E.2 Ebene 4 — Total-Strom-Limit

```cpp
uint32_t sum_currents = 0;
for (int i = 0; i < 18; i++) sum_currents += current_avg[i];

if (sum_currents > TOTAL_MAX_MA) {
    disable_all_servos();
    send_error_frame(ERR_TOTAL_OVERCURRENT, 0);
}
```

`TOTAL_MAX_MA`: konservativ unter der PSU-Sicherung (10 A), z. B. 8 A.

#### E.3 Low-Voltage-Cutoff

Servo2040 hat ADC am Servo-Rail. Spannung samplen:

```cpp
uint16_t vrail_mv = read_servo_rail_voltage();
if (vrail_mv < UNDERVOLTAGE_WARN_MV) {     // z.B. 6.0 V = 3.0V/Zelle LiPo
    send_warning_frame(WARN_LOW_VOLTAGE, vrail_mv);
}
if (vrail_mv < UNDERVOLTAGE_CRIT_MV) {     // z.B. 5.8 V
    disable_all_servos();
    state = UNDERVOLTAGE_TRIPPED;
}
```

Akku-Innenwiderstand erzeugt unter Last bereits Sag — Schwellen vorerst
mit Bench-PSU validieren (PSU runterregeln, beobachten ob Warn/Crit greifen),
echte Akku-Kalibrierung erst in Phase 13+ wenn Akku da ist.

**Done-Kriterium E:**
1. Per-Servo-Strom-Limit greift bei manueller Blockade
2. Total-Strom-Limit greift (kann mit Bench-PSU CC-Limit simuliert werden)
3. Low-Voltage-Cutoff greift bei PSU-Spannung < Schwelle
4. Error-/Warning-Frames erreichen den Host sichtbar

---

### Stufe F — Servo-Mapping vorbereiten

**Ziel:** Tabelle, die Servo2040-Output-Pin 0–17 dem Joint-Namen
(`leg_<n>_(coxa|femur|tibia)_joint`) und einer Drehrichtung (±1) zuordnet.

Wird **parallel** in zwei Stellen gepflegt:
- In der Firmware: als Konstanten (für lokale Hard-Clamps + Default-Pose)
- In `hexapod_hardware/config/servo_mapping.yaml` (Phase 9): für die
  Konversion Joint-rad → Pulse-µs

Inhalt der YAML (Vorschlag):

```yaml
servo2040_output_to_joint:
  0:  {joint: leg_1_coxa_joint,  direction:  1, pulse_min: 1000, pulse_max: 2000, pulse_zero: 1500, pulse_per_rad: 318.3}
  1:  {joint: leg_1_femur_joint, direction:  1, ...}
  2:  {joint: leg_1_tibia_joint, direction:  1, ...}
  ...
  15: {joint: leg_6_coxa_joint,  direction: -1, ...}
  16: {joint: leg_6_femur_joint, direction: -1, ...}
  17: {joint: leg_6_tibia_joint, direction: -1, ...}
```

In Phase 7 sind die Werte **Platzhalter** (Standard-Servo-Range), die echte
Kalibrierung erfolgt erst in Phase 10 pro echtem Servo am Roboter.

**Done-Kriterium F:**
1. Mapping-Tabelle in Firmware-Konstanten
2. YAML-Skelett in einem temporären Ort (wird in Phase 9 ins
   `hexapod_hardware`-Paket verschoben)
3. `direction`-Konvention dokumentiert (warum links- und rechts-Beine
   anders drehen)

---

### Stufe G — Standalone-Host-Test-Skript

**Ziel:** Ein Python-Skript am Desktop, das mit dem Servo2040 redet, alle
Sicherheits-Ebenen testet, und das ohne ROS2 läuft. Wird in Phase 9 später
durch `hexapod_hardware` ersetzt, ist hier aber das Test-Vehikel.

`tools/test_servo2040.py` im Firmware-Repo:

```python
#!/usr/bin/env python3
import serial, struct, time

ser = serial.Serial('/dev/ttyACM0', 1000000, timeout=0.1)

def send_set_targets(pulses_us):
    # COBS-Frame mit CRC16
    ...

def send_enable(idx, on):
    ...

# Test 1: Bewege Servo 0 von 1000 auf 2000 und zurück
# Test 2: Schicke Out-of-Range (500 µs), erwarte Clamp
# Test 3: Stoppe Frames für 500 ms, erwarte Watchdog-Trip
# ...
```

Was das Skript abdeckt:
- Frame-Encoding/Decoding (verifiziert Protokoll-Spec)
- Manuelles Anfahren einzelner Servos
- Reproduzierbare Tests aller Sicherheits-Ebenen
- CSV-Log von Strom + Sollwert für Plot

**Done-Kriterium G:**
1. Skript läuft, kann 2–3 angeschlossene Test-Servos definiert bewegen
2. Alle Sicherheits-Tests aus Stufen C, D, E automatisiert ausführbar
3. CSV-Logging für Strom/Pulse pro Servo

---

### Stufe H — Phase-7-Abschluss

- `phase_7_progress.md` finalisieren mit allen Live-Werten
- Erkenntnis-Tabelle pro Pimoroni-API-Frage (was funktioniert, was nicht)
- Repo-Tag im Firmware-Repo: `phase-7-done`
- Git-Commit im `hexapod_ws` (nur die `docs_raspi/phase_7_*`-Files
  betroffen, kein Code-Change im Workspace)
- Tag `phase-7-done` im `hexapod_ws`
- `PHASE.md` auf Phase 8 aktualisieren
- Kurze Retro: was lief gut, was hat länger gedauert, was ist offen

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Pico-SDK CMake findet `pico_sdk_init()` nicht | `PICO_SDK_PATH` nicht gesetzt | `export PICO_SDK_PATH=...` oder per-Repo `.envrc` |
| Servo2040 als `/dev/ttyACMx` nicht sichtbar | dialout-Gruppe, Kabel, oder Servo2040 nicht im USB-CDC-Mode | `dmesg`, `lsusb`, `sudo usermod -aG dialout $USER` + neu einloggen |
| Servo zittert im disabled-Zustand | Floating PWM-Pin | `Servo`-Klasse setzt typischerweise Pin auf LOW bei `disable()`, prüfen |
| Watchdog feuert ständig auch bei aktivem Host | Timeout zu eng (50 ms?) oder Host-Frame-Rate zu niedrig | Default 200 ms, Frame-Rate am Host messen |
| Hard-Clamp greift nicht obwohl Out-of-Range | Clamp im falschen Code-Pfad (nach PWM-Write?) | Clamp **vor** `servo.set_pulse()`, nicht danach |
| Current-Sense liest Mist | Mux-Settling-Zeit zu kurz | Pimoroni-API-Doku zu Mux-Switching-Delay prüfen |
| Soft-Ramp wirkt zu langsam | `MAX_DELTA_PER_TICK` zu klein bei hoher Tick-Rate | Tick-Rate × Delta-Tick = Pulse/Sekunde, Ziel ~2000–4000 µs/s |

---

## Was in dieser Phase **NICHT** gemacht wird

- Keine Anbindung an ROS2 (kommt in Phase 9)
- Keine echten Hexapod-Servos am Servo2040 angeschlossen (nur 2–3 Test-
  Servos für Funktionstests)
- Kein Akku-Anschluss (alles über Bench-PSU)
- Keine Bein-Kinematik in der Firmware (Firmware bleibt dumm — Pulse-µs in,
  Pulse-µs aus, mit Sicherheits-Logik dazwischen)
- Keine Kalibrierung der echten Servos (kommt in Phase 10 pro echtem
  Roboter-Servo)

---

## Konventionen, die hier festgelegt werden

(Werden in Stufe H ins Firmware-Repo `CLAUDE.md` und nach Bedarf nach
`docs/00_conventions.md` im hexapod_ws übertragen.)

- Wire-Format: Pulse-µs (int16)
- Frame-Rate Host → Firmware: 50 Hz (100 Hz max)
- Watchdog-Timeout: 200 ms
- Soft-Ramp: 20 µs/Tick bei 100 Hz Tick-Rate (= 2000 µs/s)
- Boot-Stagger pro Servo: 50 ms (= 900 ms total für 18 Servos)
- Servo-Mapping-Konvention: Output-Pin 0–17 ↔ Joint-Name + direction (±1)
- Sicherheits-Ebenen-Nummerierung wie in `CLAUDE.md` §9 / dieser Phase

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen-Done-Kriterien A–G erfüllt
- [ ] Pimoroni-API-Fragen beantwortet (Stufe B + D)
- [ ] Sicherheits-Ebenen 1–5 implementiert und getestet (mit Test-Servos)
- [ ] Standalone-Test-Skript funktioniert
- [ ] Servo-Mapping-Skelett vorbereitet (Stufe F)
- [ ] Konventionen-Erweiterungen dokumentiert
- [ ] Firmware-Repo Tag `phase-7-done`
- [ ] hexapod_ws Git-Commit + Tag `phase-7-done`
- [ ] `PHASE.md` auf Phase 8 aktualisiert
- [ ] Retrospektive in `phase_7_progress.md`
