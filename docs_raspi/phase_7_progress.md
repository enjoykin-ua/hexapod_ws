# Phase 7 — Progress-Tracker

**Phase:** Servo2040 Firmware
**Plan:** [phase_7_servo2040_fw.md](phase_7_servo2040_fw.md)
**Aktiv seit:** 2026-05-12

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**.
> Design-Entscheidungen + verworfene Alternativen unten festhalten,
> damit Re-Design später möglich ist.

---

## Stufe A — Repo-Aufsetzung & SDK-Review

- [ ] A.1 Bestehenden User-Code-Stand geklont nach `~/hexapod_servo2040_fw_old/`
- [ ] A.1 Notizen zum bestehenden Code: was funktioniert hat, was nicht
- [ ] A.2 Neues Repo angelegt (Name + Ort siehe Design-Entscheidungen unten)
- [ ] A.2 `CLAUDE.md` im Firmware-Repo geschrieben
- [ ] A.2 `README.md` mit Quickstart
- [ ] A.2 `.gitignore` (build-Artefakte, IDE-Configs)
- [ ] A.3 Pico-SDK als Submodul/Pfad eingebunden
- [ ] A.3 Pimoroni `pimoroni-pico` als Submodul/Pfad eingebunden
- [ ] A.3 CMakeLists baut leeres `main.cpp` grün
- [ ] A.3 Hello-World-Flash erfolgreich (LED blinkt o. ä.)
- [ ] A.4 Servo2040-Schaltplan-PDF nach `docs_raspi/refs_phase_7/` (lokal, nicht committet)
- [ ] A.4 Pinout-Übersicht lokal
- [ ] A.4 RP2040-Datasheet lokal

**Done-Kriterium A erreicht:** ⬜

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

- **Vorschlag:** `~/hexapod_servo2040_fw/`
- **Final:** ____
- **Verworfen:**
  - ____ (Grund: ____)

### GitHub-Remote

- **Final:** ____
- **Verworfen:**
  - ____

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
