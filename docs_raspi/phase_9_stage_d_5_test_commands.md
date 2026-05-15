# Phase 9 — Stufe D.5 — Test-Anleitung

**Was geprüft wird:** `on_activate` schickt die 3-Phasen-Boot-Sequenz
(RESET → 18× ENABLE_SERVO mit 50 ms Stagger → SET_TARGETS neutral),
`on_deactivate` schickt 18× ENABLE_SERVO(false) ohne Stagger. In
Loopback-Mode werden beide Hooks ohne Wire-I/O und Stagger durchgelaufen
(schnelle CI). Failure-Pfad: bei mid-Activate-USB-Disconnect bricht
on_activate sauber mit ERROR ab, ohne Exception aus dem Lifecycle-Hook
zu schleudern.

**Was NICHT in D.5 geprüft wird:**
- write/read mit Pulse-Konversion → **D.6**
- Reconnect bei mid-run-Disconnect → **D.7**
- ERROR_REPORT-Logging-Übersetzung → **D.8**

D.5 nutzt `openpty(3)` für PTY-basierte Tests — kein echter Servo2040
nötig. Die Tests verifizieren byteweise was auf der „Wire" landet (master
end der PTY).

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.5.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine `warning:`.

---

## Test D.5.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 168 tests, 0 errors, 0 failures, 15 skipped`

---

## Test D.5.3 — D.5-Tests fokussiert (6 Tests, ~8 s)

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="HexapodSystemActivate.*"
```

**Erwartung:**
```
[==========] 6 tests from HexapodSystemActivate (~8 s total)
[  PASSED  ] 6 tests.
```

Die sechs Tests:

| Test | Was geprüft wird |
|---|---|
| `LoopbackActivateAndDeactivateAreFast` | Loopback-Mode: `on_activate` < 100 ms (kein Stagger), `on_deactivate` < 50 ms |
| `PtyActivateSendsBootSequenceInOrder` | pty-Pair: nach `on_activate` exakt 20 Frames auf master-end — 1× RESET (cmd=0x50), 18× ENABLE_SERVO mit pin=0..17 und enable=0x01, 1× SET_TARGETS mit allen 18 Pulses = 1500 µs (0xDC 0x05 LE). SEQ 0..19 in Order |
| `PtyActivateRespectsStaggerTiming` | Wallclock-Dauer von `on_activate`: 800..1200 ms (Soll: 10 ms + 18×50 ms = 910 ms; ±200 ms für Scheduler-Jitter) |
| `PtyDeactivateSendsDisableForAllServos` | nach Activate: `on_deactivate` < 200 ms (kein Stagger), schickt 18 ENABLE_SERVO mit pin=0..17 und enable=0x00 |
| `PtyActivateDeactivateCycleCanRepeat` | 2 × full Activate/Deactivate-Zyklus; SEQ läuft über Cycles weiter (76 Frames < 256, kein wraparound observable) |
| `ActivateFailsCleanlyIfPortIsBroken` | master closen vor `on_activate` → Reader-Thread detektiert POLLHUP → `died_=true` → `on_activate` bricht beim ersten send_frame mit FATAL+ERROR ab, kein Exception-Throw aus Lifecycle |

---

## Test D.5.4 — Boot-Sequenz-Inhalt byteweise verifizieren

Der `PtyActivateSendsBootSequenceInOrder`-Test prüft jeden einzelnen
Wire-Frame:

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*PtyActivateSendsBootSequenceInOrder*"
```

Wenn der Test grün ist, ist sichergestellt:

1. **Frame 0** ist `RESET` (cmd=0x50, payload empty, SEQ=0)
2. **Frames 1..18** sind `ENABLE_SERVO` (cmd=0x20) mit:
   - `payload[0]` = pin-Index 0..17 in Order (NICHT permutiert)
   - `payload[1]` = 0x01 (enable=true)
   - SEQ = 1..18 in Order
3. **Frame 19** ist `SET_TARGETS` (cmd=0x01) mit:
   - 36 Byte Payload = 18 × int16-LE
   - Alle 18 Pulse-Werte = 1500 µs (= `pulse_zero` aus `config/servo_mapping.yaml`)
   - SEQ = 19

**Hinweis:** Wenn Phase 10 die `pulse_zero`-Werte pro Servo individualisiert
(z.B. 1480 oder 1520 statt 1500), wird dieser Test FAILEN — das ist
Absicht (Regression-Detection für YAML-Drift).

---

## Test D.5.5 — Stagger-Timing nachweisen

Ohne den 50 ms-Stagger zwischen den ENABLE_SERVO-Frames würde die ganze
Boot-Sequenz in Single-Digit-Millisekunden fertig sein. Der Test verifiziert
die designed cadence:

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*PtyActivateRespectsStaggerTiming*"
```

**Was passiert wenn der Stagger ausversehen entfernt wird:**
- Test failt mit `Activate completed in 5 ms — no stagger?` weil
  `dt_ms > 800` nicht erfüllt
- ABER: in echter Hardware würden die 18 Servo-Inrush-Peaks gleichzeitig
  über die Bench-PSU laufen → Overcurrent-Cut-Off → Boot schlägt fehl
  → Roboter ist nicht in einer sauberen Initial-Pose

→ Den Stagger NICHT entfernen, auch wenn die 900 ms unangenehm lang
wirken. Phase-7-Design-Entscheidung D.1.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `LoopbackActivateAndDeactivateAreFast` failt mit > 100 ms | Stagger nicht auf 0 in Loopback | `const auto stagger = loopback_mode_ ? 0ms : 50ms;` prüfen |
| `PtyActivateSendsBootSequenceInOrder`: nur 19 Frames | `seq_` nicht atomic-inkrementiert / Encoder hat throwed | Reader-Logs auf FATAL-Einträge prüfen, encode_*-Calls auf payload-size checken |
| `PtyActivateSendsBootSequenceInOrder`: pulse != 1500 | `pulse_zero` in `config/servo_mapping.yaml` geändert? | YAML-defaults checken; falls Phase 10 customized: Test-Erwartung anpassen |
| `PtyActivateRespectsStaggerTiming` < 800 ms | Stagger versehentlich entfernt | siehe oben — bewusst KEIN Fix |
| `PtyActivateRespectsStaggerTiming` > 1200 ms | CI-Maschine schwer ausgelastet | Test einmal solo laufen lassen; wenn reproducibel: Stagger-Konstante prüfen |
| `PtyDeactivateSendsDisableForAllServos` failt mit > 200 ms | Stagger fälschlich auch in `on_deactivate` | Deactivate hat absichtlich KEINEN Stagger — Code prüfen |
| `ActivateFailsCleanlyIfPortIsBroken` failt mit Exception | `send_frame`-Lambda catched nicht alle exceptions | try/catch um `write_all` checken; reader_.died()-Check vor write |
| Build-Fehler `<poll.h> not found` | test_hexapod_system.cpp Include fehlt | `#include <poll.h>` ergänzen |

---

## Statusmeldung an Claude

- `D.5.1–D.5.5 alle grün` → weiter mit **D.6** (`read()` / `write()`: Echo-State via
  Calibration::pulse_us_to_radians, NaN-Handling, Pulse-Overflow-Clamp,
  ERROR_REPORT-Drainage)
- `D.5.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
