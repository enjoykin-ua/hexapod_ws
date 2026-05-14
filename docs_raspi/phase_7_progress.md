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
- [ ] A.2 `CLAUDE.md` im Firmware-Repo geschrieben — **offen** (bestehendes Repo hat keine)
- [ ] A.2 `README.md` mit Quickstart — **erweitern** (bestehende ist minimal, ohne Sicherheits-Hinweise)
- [x] A.2 `.gitignore` (build-Artefakte, IDE-Configs) — vorhanden, kurz aber funktional
- [x] A.3 Pico-SDK als Pfad eingebunden (`/home/enjoykin/pico-sdk`, `PICO_SDK_PATH` in `~/.bashrc`)
- [x] A.3 Pimoroni `pimoroni-pico` als Pfad eingebunden (`/home/enjoykin/pimoroni-pico`, auto-detected als Geschwister)
- [x] A.3 CMakeLists baut grün (bestehender Code, nicht leeres `main.cpp` — produziert `Hexapod_servo_driver.uf2`, 131 KB)
- [ ] A.3 Hello-World-Flash erfolgreich (User-Aktion mit Board) — **offen**
- [ ] A.4 Servo2040-Schaltplan-PDF nach `docs_raspi/refs_phase_7/` (lokal, nicht committet) — **offen**
- [ ] A.4 Pinout-Übersicht lokal — **offen**
- [ ] A.4 RP2040-Datasheet lokal — **offen**

### Zusätzlich erledigt (nicht im ursprünglichen Bullet-Plan):

- [x] ARM-Cross-Toolchain via apt: `gcc-arm-none-eabi 13.2.1`, `libnewlib-arm-none-eabi 4.4.0`, `libstdc++-arm-none-eabi-newlib`, `libusb-1.0-0-dev`
- [x] `picotool v2.2.0-a4` aus Source gebaut (Ubuntu 24.04 hat kein Paket), Symlink unter `~/.local/bin/picotool`

**Done-Kriterium A erreicht:** ⬜ (offen: CLAUDE.md im fw-Repo, README erweitern, Hello-World-Flash, A.4 Hersteller-Doku)

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

- [ ] B.1 PWM-Frequenz pro Kanal: unterstützte Werte ermittelt → ____
- [ ] B.1 Per-Servo `enable()`/`disable()`-API: existiert auf `Servo`-Klasse? → ____
- [ ] B.1 Per-Servo enable auf `ServoCluster`? → ____
- [ ] B.1 Current-Sense-API: Mux-Verhalten, ADC-Range, Konversionsfaktor → ____
- [ ] B.1 Servo-Rail-Spannungsmessung: Pin, Spannungsteiler → ____
- [ ] B.1 USB-CDC: Standard-CDC-ACM oder Custom? → ____

### Protokoll

- [ ] B.2 Frame-Format final festgelegt
- [ ] B.2 Kommando-Tabelle final
- [ ] B.2 CRC-Spezifikation (Polynom, Init, Reflect)
- [ ] B.2 Wire-Format-Entscheidung: Pulse-µs vs. Joint-rad → ____
- [ ] B.2 Update-Rate-Entscheidung Host → Servo2040 → ____ Hz
- [ ] B.3 `PROTOCOL.md` im Firmware-Repo geschrieben
- [ ] B.3 Beispiel-Frames als Hex-Dump in `PROTOCOL.md`

**Done-Kriterium B erreicht:** ⬜

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

### Wire-Format

- **Vorschlag:** Pulse-µs auf der Wire (Host konvertiert rad ↔ pulse)
- **Final:** ____
- **Verworfen:**
  - Joint-rad auf der Wire (Grund: Firmware bliebe von URDF-Werten abhängig)

### CRC-Polynom

- **Vorschlag:** CRC16-CCITT (0x1021)
- **Final:** ____
- **Verworfen:**
  - CRC8 (Grund: zu schwach für 18×int16-Payload)

### Update-Rate Host → Servo2040

- **Vorschlag:** 50 Hz
- **Final:** ____
- **Verworfen:**
  - 100 Hz als Default (Grund: Headroom OK aber CPU/USB-Lärm)

### Per-Servo-Enable-Pfad

- **Vorschlag:** D.1 (Einzelklasse `Servo`)
- **Final:** ____
- **Verworfen:**
  - D.3 (Cluster mit pre-set targets) — Grund: ____
  - D.4 (Manuelle Vorpositionierung) — Grund: Worst-Case-Fallback

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
