# Phase 7 Stage E — Test-Anleitung: Strom/Spannungsüberwachung

**Vorbedingung:** Stage-D-Tests grün, neue Firmware (vE) geflasht.

---

## Hardware-Setup

1. **Servo2040** per USB am Desktop (`/dev/ttyACM0`).
2. **2× MG996R** an Ausgängen **0** und **1**.
3. **Bench-PSU** am Servo-Rail:
   - **Spannung:** `6,0 V`
   - **Current-Limit:** `3,0 A`
4. PSU einschalten bevor du das Skript startest.

---

## Neu flashen

Die Firmware hat sich geändert (Stage E Sensing). Erst flashen:

```bash
cd ~/hexapod_servo_driver
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release && make -j$(nproc)
cd ..
python3 tools/flash_and_verify.py
```

Erwarteter Banner nach Flash:
```
Servo2040 USB-UART Communication Started (vE total-current + undervoltage)
```

---

## Tests ausführen

```bash
python3 tools/test_stage_e.py
```

Das Skript führt drei Tests durch:

---

## E.0 — Sensing Sanity (automatisch)

Kein manueller Eingriff nötig. Das Skript:
- Wartet 0,5 s auf IIR-Filtereinlauf (8 Samples × 50 ms)
- Prüft Rail-Spannung im Bereich 3–9 V
- Prüft dass kein Spurious-Trip bei Leerlauf

**Erwartete Ausgabe:**
```
[..] E.0 sensing sanity: verify ADC readings are plausible (no servos loaded)
     warming up ADC filter (0.5 s)…
[OK] rail voltage = 5980 mV  (5.98 V)
[OK] status flags = 0x10  (no spurious trips)
     rail current at idle (servos disabled) = 12 mA
[OK] rail current with 2 servos at neutral = 480 mA
[OK] rail voltage = 5975 mV
```

---

## E.1 — Overcurrent Trip (manuell: Servo stallieren)

**Was du tun musst:**
1. Wenn das Skript `>>> GRIP servo 0's output shaft firmly` zeigt:
   - Greife die Abtriebswelle von Servo 0 **fest** und halte sie blockiert.
   - MG996R Stallstrom ≈ 2500 mA → Gesamtstrom ≈ 3000 mA → Trip bei 3500 mA.
   - Halte für ca. 5–10 s bis der Trip ausgelöst wird (IIR braucht ~400 ms).
2. Nach `[OK] ERROR_REPORT/TOTAL_OVERCURRENT received` Welle loslassen.

**PSU-Ammeter:** Du siehst den Strom von ~500 mA auf ~3000 mA ansteigen und dann
nach dem Trip auf 0 fallen (alle Servos disabled).

**Erwartete Ausgabe:**
```
[..] E.1 overcurrent trip: manually stall servo 0 to exceed 3500 mA
     baseline current = 480 mA (servos at neutral)
     >>> GRIP servo 0's output shaft firmly to stall it. …
     waiting for ERROR_REPORT/TOTAL_OVERCURRENT (up to 15 s)…
[OK] ERROR_REPORT/TOTAL_OVERCURRENT received  (measured ≈ 3612 mA)
[OK] status flags = 0x14  (TOTAL_OVERCURRENT_TRIPPED + ANY_SERVO_DISABLED)
[OK] after RESET: flags = 0x10  (trip cleared)
```

---

## E.2 — Undervoltage Warn + Trip (manuell: PSU runterregeln)

**Zwei Phasen:**

### Phase 1 — Warning (5,5 V)
1. Wenn das Skript `>>> Slowly lower the PSU voltage…` zeigt:
   - Drehe die PSU-Spannung **langsam** von 6,0 V auf ~5,5 V.
   - Der Warn-ERROR_REPORT kommt sobald Rail < 5,5 V.
2. Stoppe beim `[OK] UNDERVOLTAGE warning received`.

### Phase 2 — Critical Trip (5,0 V)
1. Wenn das Skript `>>> Continue lowering the PSU to below 5.0 V` zeigt:
   - Drehe weiter auf ~4,9 V.
   - Der Trip-ERROR_REPORT kommt sobald Rail < 5,0 V → alle Servos stromlos.
2. Stoppe beim `[OK] UNDERVOLTAGE critical trip received`.

### Recovery
1. Drehe PSU zurück auf 6,0 V.
2. Drücke Enter → Skript sendet RESET und prüft dass die Flags gelöscht sind.

**Erwartete Ausgabe:**
```
[..] E.2 undervoltage: lower PSU to trigger warn then critical trip
     baseline rail voltage = 5980 mV  (5.98 V)
     >>> Slowly lower the PSU voltage from 6.0 V toward 5.5 V…
     waiting for UNDERVOLTAGE warning (servo_idx = 0xFF, up to 20 s)…
[OK] UNDERVOLTAGE warning received  (5490 mV)
[OK] status flags = 0x30  (UNDERVOLTAGE_WARNING set, no trip yet)
     >>> Continue lowering the PSU to below 5.0 V…
     waiting for UNDERVOLTAGE critical trip (servo_idx = 0x00, up to 20 s)…
[OK] UNDERVOLTAGE critical trip received  (4960 mV)
[OK] status flags = 0x12  (UNDERVOLTAGE_TRIPPED + ANY_SERVO_DISABLED)
     >>> Turn PSU back up to 6.0 V, then press Enter.
[OK] after RESET: flags = 0x10  voltage = 5990 mV  (trip cleared)

=== OK ALL STAGE-E TESTS PASSED in 87.3s ===
```

---

## Ergebnis eintragen

Nach erfolgreichem Test in `docs_raspi/phase_7_progress.md` die E-Bullets
auf `[x]` setzen und Done-Kriterium E auf ✅.
