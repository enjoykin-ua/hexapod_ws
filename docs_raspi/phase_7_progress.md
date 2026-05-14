# Phase 7 — Progress-Tracker

**Phase:** Servo2040 Firmware
**Plan:** [phase_7_servo2040_fw.md](phase_7_servo2040_fw.md)
**Aktiv seit:** 2026-05-12

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**.
> Design-Entscheidungen + verworfene Alternativen unten festhalten,
> damit Re-Design später möglich ist.

---

## Stufe A — Repo-Aufsetzung & SDK-Review

- [x] A.1 Bestehenden User-Code-Stand geklont nach `/home/enjoykin/hexapod_servo_driver/` (User-Entscheidung: nicht in `_old`-Referenz, sondern direkt als Arbeits-Repo weiternutzen — siehe Design-Entscheidungen)
- [x] A.1 Notizen zum bestehenden Code: was funktioniert hat, was nicht (siehe Abschnitt "Sichtung bestehender Code" unten)
- [x] A.2 Repo-Entscheidung: bestehendes Repo `hexapod_servo_driver` wird Arbeits-Repo (kein neues angelegt)
- [x] A.2 `CLAUDE.md` im Firmware-Repo geschrieben (10 Abschnitte: Zweck, Beziehung zu hexapod_ws, Tech-Stack, Soll-Struktur, Arbeitsweise, Tag-Strategie, Strikte Grenzen, Konventionen, Build/Flash, Erst-Diagnose)
- [x] A.2 `README.md` erweitert (Voraussetzungen, Build, Flash mit beiden Varianten, picotool-Source-Build, Test-Verweis Stufe G, Architektur-Diagramm)
- [x] A.2 `.gitignore` (build-Artefakte, IDE-Configs) — vorhanden, kurz aber funktional
- [x] A.3 Pico-SDK als Pfad eingebunden (`/home/enjoykin/pico-sdk`, `PICO_SDK_PATH` in `~/.bashrc`)
- [x] A.3 Pimoroni `pimoroni-pico` als Pfad eingebunden (`/home/enjoykin/pimoroni-pico`, auto-detected als Geschwister)
- [x] A.3 CMakeLists baut grün (bestehender Code, nicht leeres `main.cpp` — produziert `Hexapod_servo_driver.uf2`, 131 KB)
- [x] A.3 Hello-World-Flash erfolgreich (User am 2026-05-14 mit Servo2040 verifiziert: `/dev/ttyACM0` erscheint nach Flash, USB-CDC läuft. Anleitung: `phase_7_stage_a_test_commands.md`)
- [x] A.5 (zusätzlich) `tools/flash_and_verify.py` im fw-Repo angelegt — Stdlib-only Python, ein Aufruf macht Pre-Check + BOOTSEL-Force + Flash + Boot-Message-Verify mit klarem ✓/✗-Output. Spart Tipparbeit für die mehrfachen Flash-Zyklen in Stufe B–G.
- [x] A.4 Servo2040-Schaltplan-PDF nach `docs_raspi/refs_phase_7/` (`servo2040_schematic.pdf`, 95 KB, von shop.pimoroni.com)
- [x] A.4 Pinout-Übersicht lokal (`servo2040_mechanical_drawing.png`, 99 KB; vollständige Pin-Zuordnung in `/home/enjoykin/pimoroni-pico/libraries/servo2040/servo2040.hpp` — alle 18 Servo-Pins, ADC-Mux, LED, Sense-Konstanten)
- [x] A.4 RP2040-Datasheet lokal (`rp2040-datasheet.pdf`, 5.3 MB, von datasheets.raspberrypi.com)

### Zusätzlich erledigt (nicht im ursprünglichen Bullet-Plan):

- [x] ARM-Cross-Toolchain via apt: `gcc-arm-none-eabi 13.2.1`, `libnewlib-arm-none-eabi 4.4.0`, `libstdc++-arm-none-eabi-newlib`, `libusb-1.0-0-dev`
- [x] `picotool v2.2.0-a4` aus Source gebaut (Ubuntu 24.04 hat kein Paket), Symlink unter `~/.local/bin/picotool`

**Done-Kriterium A erreicht:** ✅ (am 2026-05-14: alle Bullets erledigt, Hello-World-Flash verifiziert, Flash-Helper-Skript als Bonus angelegt)

---

## Sichtung bestehender Code (A.1)

Klon: `/home/enjoykin/hexapod_servo_driver/` — 14 Commits, letzter Stand „pushups running".

### Was funktioniert (laut Commit-Historie und Code-Lesung):

- **USB-CDC-Loop** in `main.cpp`: `stdio_usb_connected()` Wait → `getchar_timeout_us(1000000)` Byte-Parser
- **Sentinel-Framing**: Start `0x55`, End `0xAA`, dazwischen `[opcode][args...]`
- **Command-Pattern**: `CommandHandler` mit `std::map<uint8_t, unique_ptr<Command>>`, dynamische Registrierung in `main`. Pro Command eigene Header-Datei unter `src/commands/`.
- **`ServoCluster`** (Pimoroni) für alle 18 Pins (`SERVO_1..SERVO_18`), `pio0` SM 0.
- **Voltage/Current-Read** über `AnalogReader` (Pimoroni `analogmux` / `analog`).
- **WS2812-LED-Bus** aktiv (`pio1` SM 0).
- **7 implementierte Kommandos**: `GET_VOLTAGE` (0x01), `GET_CURRENT` (0x02), `READ_SWITCH` (0x03), `SET_LED` (0x04), `SET_LEDS` (0x05), `SET_SERVO_PULSE` (0x06), `SET_SERVO_PULSES` (0x07).
- **Wire-Format Pulse**: 4-Byte **float** (little-endian) µs. Beispiel-Frame als Doku im Command-Header.

### Was gegenüber Phase-7-Plan **komplett fehlt**:

| Plan-Stufe | Feature | Status im bestehenden Code |
|---|---|---|
| C.1 | Hard-Clamp pro Servo | ❌ — `servos.pulse(pin, pulse_width)` geht direkt durch |
| C.2 | Watchdog (USB-Disconnect → disable_all) | ❌ — kein Timeout, kein `disable()` |
| C.3 | Soft-Ramp (max ΔPulse/Tick) | ❌ — Sollwert wird sofort gesetzt |
| D | Per-Servo-Enable, Boot-Stagger | ❌ — `ServoCluster` wird nur einmal `init()` aufgerufen, alle 18 Pins gleichzeitig |
| E.1 | Per-Servo Strom-Limit (Trip) | ❌ — Strom wird gelesen, aber keine Trip-Logik |
| E.2 | Total-Strom-Limit | ❌ — gleiches Bild |
| E.3 | Low-Voltage-Cutoff | ❌ — Voltage wird gelesen, aber kein Trip |
| B | CRC im Frame | ❌ — Sentinel-Framing ohne Schutz |
| B | Unsolicited Error-Frames | ❌ — Antworten nur auf Anfrage |

### Konflikte / Klärungsbedarf gegenüber Plan:

- **Wire-Format**: Plan empfiehlt `int16 Pulse-µs` (2 Byte), bestehender Code nutzt `float` (4 Byte). Bandbreitenseitig irrelevant (USB-CDC), aber Plan-Konformität fordert int16. → Entscheidung in Stufe B.
- **Framing**: Plan fordert COBS+CRC16, bestehend ist `0x55`/`0xAA` Sentinel ohne CRC. USB-CDC hat eigene CRC auf Transport-Ebene — Risiko begrenzt, aber bei späterem UART-Wechsel nötig. → Entscheidung in Stufe B.
- **Update-Rate**: bestehender Loop blockiert mit `getchar_timeout_us(1_000_000)` — 1 s Timeout pro Byte. Mit Watchdog (200 ms) inkompatibel → Loop muss umgebaut werden zu non-blocking `tud_cdc_available()` / kürzerer Timeout in Stufe C.

### Was wir aus dem bestehenden Code **behalten**:

- Command-Pattern + `CommandHandler` als Architektur-Basis
- `src/commands/`-Verzeichnis-Layout
- USB-CDC-Anbindung (`stdio_init_all`, `stdio_usb_connected`)
- `ServoCluster` (mit Vorbehalt — Stufe D klärt ob Einzel-`Servo`-Klasse für Per-Servo-Enable nötig wird)
- `AnalogReader` für Voltage/Current

### Was wir **umbauen / ersetzen**:

- Frame-Format: COBS+CRC, evtl. neue Opcodes
- Main-Loop: non-blocking, fester Tick (z.B. 100 Hz)
- Wire-Format Pulse: `int16` statt `float`
- Sicherheits-Ebenen 1–5 von Grund auf neu

---

## Stufe B — Pimoroni-API-Review & Protokoll-Definition

### API-Review-Erkenntnisse

- [x] B.1 PWM-Frequenz pro Kanal → `Servo`: pro Instanz frei (Konstruktor `freq` / Setter `frequency(float)`). **`ServoCluster`: nur globale Frequenz** für alle Cluster-Servos (eine PIO-State-Machine). Default = `ServoState::DEFAULT_FREQUENCY` (50 Hz typ.).
- [x] B.1 Per-Servo `enable()`/`disable()`-API auf `Servo`-Klasse → **Ja** (`drivers/servo/servo.hpp:38-40`).
- [x] B.1 Per-Servo enable auf `ServoCluster` → **Ja** + `bool load`-Parameter erlaubt staged Enable: alle einzeln vorbereiten (`load=false`), dann `load()` für gleichzeitige Anwendung im nächsten DMA-Tick. Oder einzeln mit `load=true` für Stagger.
- [x] B.1 Current-Sense-API → `AnalogMux` (3 Adress-Pins) + `Analog::read_current()`. Konstanten in `servo2040.hpp`: `SHUNT_RESISTOR=0.003 Ω`, `CURRENT_GAIN=69`, `CURRENT_OFFSET=-0.02`. Mux-Adresse **0b111 = CURRENT_SENSE**, geteilt über `SHARED_ADC` (GPIO 29). Mux-Settling-Zeit noch in `analogmux.cpp` zu verifizieren bei Stufe E.
- [x] B.1 Servo-Rail-Spannungsmessung → Mux-Adresse **0b110 = VOLTAGE_SENSE**, gleicher `SHARED_ADC`. Spannungsteiler `VOLTAGE_GAIN = 3.9/13.9 ≈ 0.281` → `V_rail = V_adc / 0.281`. Bei 6.0 V Rail → V_adc ≈ 1.68 V (im 3.3 V ADC-Range). Bei 8.4 V (LiPo voll) → V_adc ≈ 2.36 V.
- [x] B.1 USB-CDC → **Standard CDC-ACM** (über `pico_enable_stdio_usb 1` in CMakeLists). Host sieht `/dev/ttyACM*`. Im Hello-World-Flash bereits verifiziert.

### Konsequenzen für Plan-Stufen

- **Hardware-Wahl**: Single `Servo`-Klasse nutzt Hardware-PWM-Slices (8 × 2 = 16 Kanäle), reicht **nicht für 18 Servos**. → `ServoCluster` (PIO+DMA) ist Pflicht. Per-Servo-Enable funktioniert dort über `bool load`-Mechanismus.
- **Stufe D (Per-Servo-Enable) gelöst**: Der alte „alle laufen gleichzeitig los"-Effekt kam vom alten Code, der `cluster.init()` ohne vorab gesetzte Pulse aufgerufen hat. Zwei Pfade verfügbar:
  - **D.1** (gestaffelt nacheinander): `for i: enable(i, true); sleep_ms(50)` → 18 × 50 ms = 900 ms Boot, klar getrennte Inrush-Peaks
  - **D.3** (alle gleichzeitig auf vorab gesetzte Pose): `pulse(i, stand_pose_us, false)` für alle, dann `enable_all()` — kein Sprung, weil schon auf Stand-Pose
  - **D.4** (mechanische Vorpositionierung) als Worst-Case-Fallback voraussichtlich nicht nötig.
- **Stufe C/E** (Sicherheit): Pimoroni-API liefert keine Watchdog-Logik — selbst Tick-basiert bauen. Hard-Clamp/Soft-Ramp im PWM-Output-Pfad vor `cluster.pulse(...)`. Strom-Sense per Mux-Switch + ADC-Read pro Servo.

### Protokoll

- [x] B.2 Frame-Format final: COBS + CRC-16/CCITT-FALSE über `SEQ ‖ CMD ‖ LEN ‖ PAYLOAD`
- [x] B.2 Kommando-Tabelle final (13 Opcodes, siehe `PROTOCOL.md` §3 — inkl. LED-Steuerung 0x30/0x31 für die 6 onboard WS2812-LEDs und Switch-/Sensor-Read 0x40 für die 6 externen Sensor-Pins + USER_SW; nachgetragen am 2026-05-14)
- [x] B.2 CRC-Spezifikation: CRC-16/CCITT-FALSE (Polynom 0x1021, Init 0xFFFF, no reflect, XorOut 0x0000)
- [x] B.2 Wire-Format Pulse: int16 LE µs (umgestellt von altem float)
- [x] B.2 Update-Rate Host → Firmware: 50 Hz Default, bis 100 Hz erlaubt
- [x] B.3 `PROTOCOL.md` im fw-Repo geschrieben (8 Abschnitte: Transport, Frame-Encoding, Kommandos, Beispiele, Boot, Watchdog, Impl-Hinweise, Versionierung)
- [x] B.3 Beispiel-Frames als Hex-Dump in `PROTOCOL.md` §4 (SET_TARGETS, GET_STATE, ENABLE_SERVO, RESET)

**Done-Kriterium B erreicht:** ✅ (am 2026-05-14)

---

## Stufe C — Sicherheits-Ebenen 1, 2, 5

- [ ] C.1 Hard-Clamp pro Servo implementiert (`pulse_min`/`pulse_max` aus Konstanten)
- [ ] C.1 Out-of-Range-Test bestanden (Oszi/Logic-Analyzer)
- [ ] C.2 Watchdog implementiert (`WATCHDOG_TIMEOUT_MS = 200`)
- [ ] C.2 USB-Disconnect-Test bestanden (Servo wird stromlos)
- [ ] C.3 Soft-Ramp implementiert (`MAX_DELTA_PER_TICK`)
- [ ] C.3 Sprung-Sollwert-Test bestanden (kein Sprung kommt physisch an)
- [ ] C.4 Python-Test-Skript am Host kann diese drei Tests automatisiert fahren

**Done-Kriterium C erreicht:** ⬜

---

## Stufe D — Per-Servo-Enable verifizieren

- [ ] D.1 Test mit 2 Servos, Einzelklasse `Servo`: Pfad funktioniert? → ____
- [ ] D.2 Test mit 18 Servos gestaffelt: Pfad funktioniert? → ____
- [ ] D.3 Fallback `ServoCluster` mit vorab gesetzten Targets getestet → ____
- [ ] D.4 Falls D.4 (Worst-Case): Vor-Boot-Pose-Doku angelegt
- [ ] D-Erkenntnis dokumentiert (welcher der drei Pfade gewinnt)

**Done-Kriterium D erreicht:** ⬜

---

## Stufe E — Strom-Limits & Low-Voltage-Cutoff

- [ ] E.1 Per-Servo-Strom-Limit implementiert
- [ ] E.1 Stall-Test bestanden (Servo manuell blockiert → disabled + Error-Frame)
- [ ] E.2 Total-Strom-Limit implementiert
- [ ] E.2 Total-Trip-Test bestanden (PSU-CC-Limit simuliert)
- [ ] E.3 Low-Voltage-Cutoff implementiert (`UNDERVOLTAGE_WARN_MV`, `_CRIT_MV`)
- [ ] E.3 Trip-Test mit PSU-Stellrad bestanden
- [ ] E.3 Reset-Frame nach Trip funktioniert

**Done-Kriterium E erreicht:** ⬜

---

## Stufe F — Servo-Mapping vorbereiten

- [ ] F.1 Mapping-Tabelle in Firmware-Konstanten (Output 0–17 ↔ Joint)
- [ ] F.2 YAML-Skelett unter `~/hexapod_servo2040_fw/contrib/servo_mapping.yaml`
      (wird in Phase 9 in `hexapod_hardware/config/` verschoben)
- [ ] F.3 `direction`-Konvention dokumentiert

**Done-Kriterium F erreicht:** ⬜

---

## Stufe G — Standalone-Host-Test-Skript

- [ ] G `tools/test_servo2040.py` geschrieben
- [ ] G Frame-Encoder/Decoder Python ↔ Firmware kompatibel
- [ ] G Bewegungs-Test mit 2–3 Test-Servos läuft
- [ ] G Sicherheits-Test-Suite (C, D, E) automatisiert ausführbar
- [ ] G CSV-Logging für Strom/Pulse pro Servo

**Done-Kriterium G erreicht:** ⬜

---

## Stufe H — Phase-7-Abschluss

- [ ] H Erkenntnis-Tabelle pro Pimoroni-API-Frage in Doku
- [ ] H Firmware-Repo Tag `phase-7-done`
- [ ] H hexapod_ws Git-Commit (nur `docs_raspi/phase_7_*` betroffen)
- [ ] H hexapod_ws Tag `phase-7-done`
- [ ] H `PHASE.md` auf Phase 8 aktualisiert
- [ ] H Retrospektive (siehe unten)

**Done-Kriterium H erreicht:** ⬜

---

## Design-Entscheidungen (mit verworfenen Alternativen)

> Pro Stufe ergänzen, damit Re-Design später möglich ist ohne sich erinnern
> zu müssen warum es so wurde wie es ist.

### Repo-Name + Ort

- **Vorschlag (Plan):** neues Repo `~/hexapod_servo2040_fw/`
- **Final:** `/home/enjoykin/hexapod_servo_driver/` (bestehendes Repo, am 2026-05-14 entschieden)
- **Verworfen:**
  - Neues leeres Repo (Grund: User-Entscheidung — vorhandener Code-Stand ist die solide Architektur-Basis, nur Sicherheits-Schicht muss neu)
  - Klon-als-Referenz nach `~/hexapod_servo2040_fw_old/` (Grund: redundant, wenn wir direkt am bestehenden weiterarbeiten)

### GitHub-Remote

- **Final:** `https://github.com/enjoykin-ua/hexapod_servo_driver.git` (bestehend, beibehalten)
- **Verworfen:**
  - Neues Repo unter neuem Namen (Grund: siehe oben — wir bauen auf dem bestehenden auf)

### Wire-Format Pulse

- **Final:** `int16` LE µs (Host und Firmware verwenden ganzzahlige Mikrosekunden).
  Umgestellt von altem `float`-Format des `legacy-pushups`-Stands. Begründung:
  PWM ist intern ohnehin ganzzahlig, 1 µs Auflösung ist 50× feiner als jeder
  Servo schafft, und int16 spart 50 % Bandbreite. Wertebereich ±32 768 µs deckt
  Standard-Servo-Range (500–2500 µs) locker ab.

### Frame-Format

- **Final:** COBS-Encoding + CRC-16/CCITT-FALSE über `SEQ ‖ CMD ‖ LEN ‖ PAYLOAD`,
  Frame-Trenner ein einzelnes `0x00`-Byte am Frame-Ende.
- **Was COBS ist:** Consistent Overhead Byte Stuffing — ersetzt jedes `0x00`
  im Payload durch einen Zähler, sodass `0x00` nur als Frame-Trenner vorkommen
  kann. Empfänger kann jederzeit auf den nächsten Frame resync'en, indem er
  bis zum nächsten `0x00` liest. Overhead: maximal 1 Byte pro 254 Payload-Byte.
- **Wozu CRC zusätzlich**: USB-CDC hat Transport-CRC, aber sobald wir später
  auf UART portieren oder Frames über andere Wege (z.B. SPI) gehen, fängt
  CRC-16 alle 1- und 2-Bit-Fehler und alle Burst-Fehler ≤ 16 Bit ab. Schutz
  davor, dass ein Bit-Flip einen Servo auf eine völlig falsche Position
  schickt.

### CRC-Polynom

- **Final:** CRC-16/CCITT-FALSE (Polynom `0x1021`, Init `0xFFFF`, no reflect,
  XorOut `0x0000`).
- **Was das ist:** Standard-CRC-16-Variante im Embedded-Bereich. Selbsttest
  über den String `"123456789"` ergibt `0x29B1` — bekannt-konstanter Wert,
  damit man die Implementation gegen ihn verifizieren kann. Lookup-Table:
  256 Einträge × 2 Byte = 512 Byte Flash. Berechnung pro Byte: ein XOR + ein
  Shift + ein Tabellen-Lookup.

### Update-Rate Host → Firmware

- **Final:** 50 Hz Default, bis 100 Hz erlaubt.
- 50 Hz ist die `gait_node`-Rate aus Phase 5/6 — passt nahtlos. 100 Hz als
  Headroom für Phase 9, falls der Host nervöser pingen will. Watchdog-Timeout
  200 ms = 10 Frames Toleranz bei 50 Hz, 20 Frames bei 100 Hz.

### Per-Servo-Enable-Pfad

- **Final:** D.1 — gestaffelt nacheinander, 50 ms Pause zwischen Servos.
  Boot dauert 18 × 50 ms = 900 ms, dafür separate Inrush-Strom-Peaks pro
  Servo (PSU- und Akku-freundlich).
- **Verworfen:**
  - D.3 (alle gleichzeitig auf vorab gesetzte Stand-Pose) — Grund:
    gemeinsamer Inrush-Peak. Bei 18 Servos × ~1 A Hold-Strom = ≥18 A Spitze
    beim Anlauf, knapp am 10-A-PSU-Limit der RND-Bench-PSU. Bei späterem
    Akku-Betrieb noch enger. Bleibt als Notfall-Option dokumentiert.
  - D.4 (manuelle Vorpositionierung) — Grund: Worst-Case-Fallback, wird
    voraussichtlich nicht gebraucht weil D.1 funktional verifiziert ist
    (Pimoroni-API-Review B.1).

### Watchdog-Timeout

- **Vorschlag:** 200 ms
- **Final:** ____
- **Verworfen:**
  - 50 ms (Grund: false-positives bei Pi-Timing-Jitter)
  - 500 ms (Grund: zu langsam bei echtem Crash)

---

## Retrospektive (Stufe H)

> Bei Phasen-Abschluss füllen.

**Was lief gut:**

-

**Was hat länger gedauert als gedacht:**

-

**Was bleibt offen für spätere Phasen:**

-
