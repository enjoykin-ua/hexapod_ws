# Phase 9 — Stufe D.6 — Test-Anleitung

**Was geprüft wird:** `write()` konvertiert `hw_command_positions_[i]` (rad,
URDF-Slot) durch `Calibration::radians_to_pulse_us` in
`last_command_pulse_us_[output_idx]` (µs, Servo-Pin) und schickt im
non-loopback Modus pro Tick einen `SET_TARGETS`-Frame. `read()` echot
den letzten Pulse als Radiant zurück, drainet die ERROR_REPORT-Queue,
und surface't `reader_.died()` als `return_type::ERROR`.

**Was NICHT in D.6 geprüft wird:**
- Reconnect bei mid-run-Disconnect → **D.7**
- ERROR_REPORT-Übersetzungs-Tabelle (Code → human-readable) → **D.8**
- Performance / 50 Hz Echtzeit-Verhalten → Phase 11

D.6 nutzt `openpty(3)` für PTY-basierte Tests — kein echter Servo2040
nötig.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.6.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine
`warning:`. Insbesondere KEINE `get_value() is deprecated`-Warnings (Test-
Helper nutzt das neue `get_optional()`-API).

---

## Test D.6.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 177 tests, 0 errors, 0 failures, 15 skipped`

---

## Test D.6.3 — D.6-Tests fokussiert (9 Tests, ~2.5 s)

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="HexapodSystemWriteRead.*"
```

**Erwartung:**
```
[==========] 9 tests from HexapodSystemWriteRead (~2.5 s total)
[  PASSED  ] 9 tests.
```

Die neun Tests:

| Test | Was geprüft wird |
|---|---|
| `LoopbackRoundtripsCommandThroughCalibration` | 7 rad-Werte (-1.5 .. +1.5) durch alle 18 Joints; write → read muss `state ≈ command` mit ≤ 2 mrad Toleranz liefern |
| `LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` | reverse-sortierte URDF + distinkte Werte pro Slot → verifiziert dass `joint_to_output_idx_` in BEIDEN Hooks (write + read) angewandt wird, NICHT nur in on_init gebaut |
| `LoopbackZeroRadStaysAtPulseZero` | Anchor-Test: rad=0 → pulse=1500 → rad=0 EXAKT (keine Rundung) |
| `LoopbackNanCommandIsLoggedAndIgnored` | Slot 5 erst auf 0.5, dann auf NaN → muss noch ≈ 0.5 sein (last good gehalten); andere Slots tracken 0.1 |
| `LoopbackClampsAbsurdRadInsteadOfUB` | rad=±100 (extrem) → write throw-frei, state ist `std::isfinite` (= clamp griff, keine UB beim int16-cast) |
| `PtyWriteSendsSetTargetsFrameWithNeutralPulses` | non-loopback: 18× rad=0 → genau 1 SET_TARGETS-Frame auf master mit 18× 0xDC 0x05 (= 1500 µs LE) |
| `PtyReadDrainsFirmwareErrorReports` | Inject WATCHDOG_TRIPPED-Frame auf master; nach 100 ms read() → OK (drain läuft, Crash-frei) |
| `PtyReadReturnsErrorWhenReaderDies` | master close → reader detektiert POLLHUP → died_ → read() → ERROR |
| `PtyWriteReturnsErrorWhenReaderDies` | gleiche Disconnect-Situation für write() → ERROR ohne system_error-Exception |

---

## Test D.6.4 — Permutations-Mapping-Test einzeln

Der Post-Review-Fix-Test verifiziert die wichtigste D.6-Eigenschaft:
das `joint_to_output_idx_`-Mapping wird tatsächlich in den write/read-
Hooks angewandt (nicht nur in on_init gebaut).

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*EchoesAreSlotCorrectWithPermutedJointOrder*"
```

**Was passiert wenn das Mapping versehentlich weggelassen wird:**
- Bei `hw_state_positions_[output_idx] = ...` statt `hw_state_positions_[i] = ...`
  würde Slot i's Wert auf Slot (17-i) landen → Test failt mit per-Slot-Mismatch.
- Bei kanonischer URDF wäre der Bug **unsichtbar** (joint_to_output_idx_[i] = i),
  daher die reverse-URDF-Konstruktion im Test.

---

## Test D.6.5 — Roundtrip-Genauigkeit überprüfen

Die Pulse-Konversion hat strukturelle Rundungsverluste:
- `radians_to_pulse_us` liefert `double`, gerundet auf int16
- 1 µs Pulse-Step entspricht ≈ 1.6 mrad bei Standard-Slope (~636 µs/rad)
- Test-Toleranz `2e-3` rad (= 2 mrad) lässt Buffer für `std::round`

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*Roundtrips*"
```

Wenn die Genauigkeit irgendwann mal nicht reicht (z.B. Calibration
liefert subtil falsche Werte), failt der Test mit konkretem rad-Wert
und Toleranz-Verletzung — gute Debug-Spur.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `LoopbackRoundtripsCommandThroughCalibration` failt mit > 2 mrad | Konversions-Bug in `Calibration` (slope-Berechnung, direction-Flip) | `test_calibration.cpp` separat fahren um die Konversion zu isolieren |
| `LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` failt mit Wert-Mismatch pro Slot | `joint_to_output_idx_` vergessen in write() oder read() | Code-Stelle suchen wo `last_command_pulse_us_[i]` statt `last_command_pulse_us_[output_idx]` benutzt wird (oder umgekehrt mit `hw_state_positions_`) |
| `LoopbackNanCommandIsLoggedAndIgnored` failt mit NaN im state | NaN-Sanity in write() fehlt | `std::isnan(rad)`-Check vor `radians_to_pulse_us` einbauen |
| `LoopbackClampsAbsurdRadInsteadOfUB` failt mit non-finite state | int16-Clamp vor `static_cast<int16_t>` fehlt | `std::clamp(pulse_d, INT16_MIN, INT16_MAX)` einfügen |
| `PtyWriteSendsSetTargetsFrameWithNeutralPulses` failt mit 0 Frames | write_all schreibt nicht oder loopback_mode hat skip-Bug | Reader-Logs prüfen, `loopback_mode_`-Wert verifizieren |
| `PtyReadDrainsFirmwareErrorReports` failt mit ERROR-Return | drain läuft nicht oder reader.died() ohne Grund true | Reader-Logs prüfen, evtl. Sleep nach inject erhöhen (Race) |
| `PtyReadReturnsErrorWhenReaderDies` failt mit OK statt ERROR | reader.died()-Check in read() fehlt | Check nach drain() einfügen |
| `PtyWriteReturnsErrorWhenReaderDies` failt mit Crash/Exception | catch um write_all fehlt oder reader.died()-Check fehlt | Defensive-Layer in write() einbauen |
| Build-Fehler `get_value() deprecated` | Test nutzt alte API | Test-Helper `read_handle()` über `get_optional().value()` ist Pflicht |
| Build-Fehler `set_value()` ist `[[nodiscard]]` | Test ruft set_value ohne Konsum auf | Helper `write_handle()` mit `ASSERT_TRUE` benutzen |

---

## Statusmeldung an Claude

- `D.6.1–D.6.5 alle grün` → weiter mit **D.7** (USB-Reconnect-Logik mit
  Backoff: shared_mutex-Race-Protection, Backoff-Schleife im Reader-Thread,
  manuelle Recovery-Procedure dokumentieren)
- `D.6.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
