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

### C.0 — Vor-Arbeit (proto layer + main-loop umbau)

War nicht im ursprünglichen Plan, ist aber Voraussetzung für C.1–C.3.

- [x] C.0 `src/proto/{crc,cobs,frame}.{hpp,cpp}` neu geschrieben (CRC-16/CCITT-FALSE, COBS encode/decode, FrameAssembler streaming decoder, encode_frame)
- [x] C.0 `main.cpp` komplett neu: 100 Hz Tick, non-blocking USB-Read, GET_STATE/RESET/NACK-Handler. Banner kommt nach `stdio_usb_connected()` (kein Timeout-Race mehr).
- [x] C.0 `src/config.hpp` neu (Opcodes, Error-Codes, Status-Flags, Timing-Konstanten)
- [x] C.0 alte Files raus: `includes.hpp`, `command.hpp`, `CommandHandler.hpp`, `commands/`, `utils/conversion.hpp`
- [x] C.0 `CMakeLists.txt`: proto/.cpp Files + Include-Pfade
- [x] C.0 `tools/flash_and_verify.py`: Retry-Pfad nutzt jetzt `picotool reboot -f -a`
- [x] C.0 Build grün (51 KB .uf2, ~80 KB kleiner als legacy)
- [x] C.0 Smoke-Test: `flash_and_verify.py` läuft in 3.5 s grün durch (verifiziert: USB-CDC, Boot-Banner-Sync, Loop läuft)

### C.1 — Hard-Clamp + SET_TARGETS + ServoCluster init

- [x] C.1 ServoCluster init (pio0 SM 0, SERVO_1..SERVO_18) in `main()`
- [x] C.1 Hard-Clamp-Logik direkt in `main.cpp` (`clamp_pulse(idx, val, clamped_out)` mit `pulse_min_us[]/pulse_max_us[]`-Arrays — keine eigene `safety/`-Datei nötig)
- [x] C.1 SET_TARGETS-Handler: 36 Byte Payload validieren, 18× int16 LE entpacken, Clamp anwenden, in `target_pulse_us[]` speichern
- [x] C.1 on_tick(): target → current (in C.3 ratenlimitiert) → `cluster.pulse(i, val, false)` + `cluster.load()`
- [x] C.1 ENABLE_SERVO-Handler: per-servo enable/disable, status-flag bookkeeping
- [x] C.1 ERR_PULSE_OUT_OF_RANGE wenn Wert geclamped wurde (erster geclamped Servo im Frame als servo_idx + raw value als aux)
- [x] C.1 Build grün, Boot grün (User verifiziert)

### C.2 — Watchdog

- [x] C.2 Watchdog implementiert (`cfg::WATCHDOG_TIMEOUT_MS = 200`)
- [x] C.2 `watchdog_armed`-Flag — armiert beim ersten validen Frame, damit Boot-Up nicht sofort trippt
- [x] C.2 Trip-Logik in `on_tick()`: disable_all + status-flag setzen + unsolicited ERROR_REPORT (seq=0)
- [x] C.2 RESET clears `WATCHDOG_TRIPPED` + disarmiert Watchdog (Recovery-Pfad)
- [x] C.2 ENABLE_SERVO im TRIPPED-State → NACK mit reason=WATCHDOG_TRIPPED (laut PROTOCOL.md §6)
- [x] C.2 Build grün, Boot grün (User verifiziert)

### C.3 — Soft-Ramp

- [x] C.3 Soft-Ramp implementiert (`cfg::MAX_DELTA_PULSE_PER_TICK_US = 20`, = 2000 µs/s @ 100 Hz)
- [x] C.3 Pro Servo: `delta = target - current`, capped auf ±20 µs/Tick
- [x] C.3 Build grün

### C.4 — Python-Test-Skript

- [x] C.4 `tools/test_servo2040.py` geschrieben (~330 Zeilen, Stdlib-only — kein pyserial)
- [x] C.4 Eigene CRC-16/CCITT-FALSE-Implementation + Self-Test (`crc16("123456789") == 0x29B1`)
- [x] C.4 Eigener COBS-Encoder/Decoder + Frame-Helpers
- [x] C.4 `test_hard_clamp` — out-of-range below min und above max, verifiziert ERROR_REPORT + STATE-Echo
- [x] C.4 `test_watchdog` — stallt 350 ms, prüft unsolicited ERROR + status flag + ENABLE_SERVO-NACK + RESET-Recovery
- [x] C.4 `test_soft_ramp` — Sprung-Test (1500 → 2500), prüft dass nach 100 ms current ~ 1700 (nicht 2500), nach voller Rampe = 2500
- [x] C.4 Frame-Round-Trip-Test (encode/decode) bestanden vor Hardware-Lauf
- [x] C.4 End-to-End am Board verifiziert (2026-05-14, alle 3 Tests grün in 3.4 s)
- [ ] CSV-Logging für Strom/Pulse pro Servo (kommt später in Stufe E)

**Done-Kriterium C erreicht:** ✅ (am 2026-05-14: alle Board-Tests grün)

### Bugs beim Board-Test (C.4 Postmortem)

Zwei Bugs haben sich gegenseitig versteckt — beide gleichzeitig aufgetreten,
keiner allein hätte das vollständige Bild erzeugt.

#### Bug 1: Fehlendes `stdio_flush()` in `send_frame()` (Hauptproblem)

**Ursache:** Der RP2040 kommuniziert über USB-CDC-ACM (`/dev/ttyACM0`). TinyUSB
puffert Bytes intern in einem 64-Byte-Ring-Buffer; ein USB-Paket geht erst raus
wenn der Buffer voll läuft oder explizit geflusht wird.

`send_frame()` rief `putchar_raw()` in einer Schleife auf → Bytes landen im
TinyUSB-Buffer. Kleine Frames (ACK = 7 Byte, ERROR_REPORT = 12 Byte) füllten
den Buffer nicht → blieben dauerhaft stecken. Große Frames (STATE_RESPONSE =
82 Byte) liefen über → Paket ging raus und riss dabei gepufferte ACKs mit.

Symptom: In `probe.py` kamen STATE-Frames an, kleine Frames (ACK, NACK,
ERROR_REPORT) nicht.

**Fix:** `stdio_flush()` am Ende jedes `send_frame()`-Aufrufs → ruft intern
`tud_cdc_write_flush()` auf → erzwingt sofortigen USB-Paket-Versand unabhängig
von der Puffer-Füllmenge.

#### Bug 2: TTY im "Cooked Mode" auf Python-Seite (verstecktes Problem)

**Ursache:** Beim Öffnen von `/dev/ttyACM0` mit `os.open()` ist die
Linux-Kernel-TTY-Line-Discipline aktiv — dieselbe wie für normale Terminals:

- `ICRNL`: empfangenes `0x0D` (CR) → `0x0A` (LF) automatisch umgewandelt
- `ONLCR`: gesendetes `0x0A` → `0x0D 0x0A` expandiert

Das binäre COBS+CRC-Protokoll kann jeden Byte-Wert im Frame enthalten,
insbesondere in CRC-Bytes. Wenn der CRC-Low-Byte des ERROR_REPORT zufällig
`0x0D` war:

```
Firmware sendet:  [..., 0x0D, crc_hi, 0x00]
Host empfängt:    [..., 0x0A, crc_hi, 0x00]   ← 0x0D→0x0A durch ICRNL
→ CRC-Check schlägt fehl → decode_frame() → None → Frame wird still verworfen
→ Test läuft in Timeout
```

Der STATE-Frame funktionierte in `probe.py` zufällig immer weil seine bekannten
Nutzdaten (z.B. `0xDC05` für 1500 µs) kein `0x0D` enthielten.

**Fix:** `tty.setraw(self.fd)` nach dem Öffnen in der `Link`-Klasse →
deaktiviert die gesamte Line Discipline → Bytes kommen 1:1 durch, kein
Byte-Mangling.

---

## Stufe D — Per-Servo-Enable verifizieren

> **Ansatz (aus API-Review B.1 festgelegt):** ServoCluster + ENABLE_SERVO per-servo,
> 50 ms Stagger zwischen Servos (D.1-Pfad). `Servo`-Einzelklasse ist kein Option
> weil RP2040 nur 8 PIO-State-Machines hat — zu wenig für 18 unabhängige Kanäle.

- [x] D.1 Staged-Enable mit 2× MG996R am Board verifiziert (2026-05-14,
      PSU 6,0 V / 3,0 A, `python3 tools/test_servo2040.py --servos 2 --manual`)
- [x] D.1 Physische Beobachtung bestätigt: Servos engagen nacheinander, Bewegung passend
- [x] D-Erkenntnis: ServoCluster ENABLE_SERVO per-servo funktioniert korrekt;
      Snap-to-neutral beim Enable ist erwartetes Verhalten (Servo springt auf
      current_pulse_us = 1500 µs, danach folgt soft-ramp für weitere Sollwert-Änderungen)

**Done-Kriterium D erreicht:** ✅ (am 2026-05-14)

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
- **Final:** 200 ms (`cfg::WATCHDOG_TIMEOUT_MS = 200` in `config.hpp`)
- **Begründung:** 10 verpasste Frames bei 50 Hz Host-Rate — genug Toleranz
  für OS-Jitter auf dem Desktop, aber schnell genug für echte Disconnect-Erkennung.
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
