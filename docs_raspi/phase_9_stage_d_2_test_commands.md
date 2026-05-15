# Phase 9 — Stufe D.2 — Test-Anleitung

**Was geprüft wird:** Der Reader-Thread (`Servo2040Reader`) startet
sauber, joined sauber, läuft im Hintergrund Bytes vom `SerialPort` zu
lesen und in Frames zu zerlegen, dispatcht nach Opcode korrekt
(STATE → Cache, ERROR_REPORT → Queue, ACK/NACK → Debug-Log, unbekannt
→ Warn), verwirft ungültige Frames ohne State zu „poisonen", und
zerstört sich sauber im Destruktor (kein Thread-Leak, kein Detach).

**Was NICHT in D.2 geprüft wird:**
- Reconnect-Logik bei Disconnect → **D.7**
- ERROR_REPORT-Logging-Detail (Code → Klartext) → **D.8**
- Plugin-Integration (`on_init` etc.) → **D.3+**

D.2 ist ein **C++-Unit-Test-Smoke-Test mit `openpty(3)`** — der
Master-Pty simuliert die Firmware-Seite, der Slave wird vom
`SerialPort` adoptiert.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.2.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `Summary: 1 package finished [X.XXs]`
- **Kein** Block mit `stderr: hexapod_hardware`
- Keine `warning:`-Zeilen

---

## Test D.2.2 — Volle Test-Suite grün (8/8)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** Letzte Zusammenfassung
`100% tests passed, 0 tests failed out of 8`.

Die acht Tests sind:
1. `test_calibration` (30 gtest-Cases, unverändert seit C)
2. `test_serial_port` (14 gtest-Cases, unverändert seit D.1)
3. **`test_servo2040_reader`** — neu in D.2 (17 gtest-Cases, läuft ~12 s
   wegen TearDown-Timeouts pro Pty-Test)
4. `test_servo2040_protocol` (36 gtest-Cases, unverändert seit B)
5. `cppcheck`
6. `lint_cmake`
7. `uncrustify`
8. `xmllint`

> **Laufzeit-Hinweis:** Die Reader-Tests sind die langsamsten in der
> Suite — jeder einzelne PTY-Test mit `TearDown`-`reader_.stop()`
> wartet im Worst Case ~1 s bis der Read-Timeout im Reader greift.
> 11 Tests × ~1 s = ~11 s Reader-Test-Block. Insgesamt `colcon test`
> braucht damit ~20 s statt der vorher ~5 s.

---

## Test D.2.3 — Alle 17 Reader-gtest-Cases sichtbar machen

```bash
./build/hexapod_hardware/test_servo2040_reader
```

**Erwartung am Ende:**
```
[==========] 17 tests from 2 test suites ran. (~17 s total)
[  PASSED  ] 17 tests.
```

Die zwei Test-Suites:

- **`ReaderLifecycle` (6 Tests)**:
  - `IsRunningAfterStartFalseAfterStop` — Basis-Lifecycle
  - `DoubleStartThrows` — start() bei laufendem Thread wirft
  - `StopIsIdempotent` — doppeltes stop() OK
  - `StopJoinsCleanlyWithin1500ms` — Stop-Latenz unter 1.5 s
  - **`RepeatedStartStopLeavesNoThreadBehind`** — 5× start/stop-Zyklen
    mit Frame-Verkehr dazwischen; verifiziert dass `is_running()` /
    `died()` korrekt nach jedem Stop ist (kein vergessener Thread)
  - **`DestructorJoinsRunningThread`** — RAII: Destructor stoppt+joined
    bei Scope-Exit (kein Detach)

- **`ReaderPty` (11 Tests)** — alle mit openpty-Fixture:
  - `StateFrameLandsInCache` — STATE-Frame → `latest_state()` peekable
  - `ErrorReportLandsInQueue` — ERROR_REPORT → `drain_error_queue` liefert ihn
  - `MultipleErrorReportsAccumulateInOrder` — drei Reports in Reihenfolge gesammelt
  - `DrainConsumesQueue` — zweiter Drain ist leer (drain ist konsumierend)
  - `GarbageBytesAreDiscarded` — random bytes + 0x00 → Cache bleibt leer, kein died
  - `UnknownOpcodeIsDiscarded` — gültiges Frame mit Opcode `0x99` → WARN, nicht in Cache
  - `CorruptedCrcIsDiscarded` — Bit-Flip in einem Frame → wird verworfen
  - `AckAndNackAreSilentlyAccepted` — beide → DEBUG-Log, nichts in Cache/Queue
  - `MultipleFramesBackToBackAllProcessed` — STATE + ERROR_REPORT in einem write
  - `ChunkedDeliveryIsReassembledCorrectly` — byte-by-byte mit Mikropause → reassembly
  - `LoneDelimiterByteIsIgnored` — einzelnes 0x00 → kein bogus empty frame, kein Crash

---

## Test D.2.4 — Thread-Hygiene fokussiert

Speziell für den „kein Thread läuft heimlich weiter"-Aspekt:

```bash
./build/hexapod_hardware/test_servo2040_reader \
    --gtest_filter="ReaderLifecycle.*"
```

**Erwartung:** alle 6 Tests passed, total < 3 s.

Wenn `RepeatedStartStopLeavesNoThreadBehind` failt: irgendwo bleibt
ein Thread joinable nach `stop()` — `lifecycle_mtx_` in der `.cpp`
prüfen, oder ob `stop_requested_` korrekt vor `join()` gesetzt wird.

Wenn `DestructorJoinsRunningThread` über 1.5 s braucht: `~Servo2040Reader`
ruft `stop()` nicht auf, oder `stop()` selbst hängt.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `GarbageBytesAreDiscarded` crasht mit „Speicherauszug" | `RCLCPP_*_THROTTLE` ohne initialisiertes rclcpp (Clock-UB) | im Reader `RCLCPP_WARN` ohne THROTTLE nutzen |
| `RepeatedStartStopLeavesNoThreadBehind` zeigt `is_running()==true` nach stop | `stop()` joined nicht, oder `thread_` ist nach join noch joinable | `stop()` im Reader prüfen, ob `thread_.join()` aufgerufen wird |
| `DestructorJoinsRunningThread` > 1.5 s | Destruktor ruft nicht `stop()` auf | `~Servo2040Reader` definiert? |
| `ErrorReportLandsInQueue` hängt oder crasht | use-after-free (typischer Fall: `*std::make_unique<T>()`) im Test | Test-Pattern reparieren: niemals `*ptr` von einem Temporary nehmen |
| Build-Fehler `openpty` not found im neuen Test | Test-Link fehlt | `CMakeLists.txt`: `target_link_libraries(test_servo2040_reader ${PROJECT_NAME} util)` |

---

## Statusmeldung an Claude

- `D.2.1–D.2.4 alle grün` → weiter mit D.3 (on_init mit URDF-Parsing + Calibration-Lookup-Tabelle)
- `D.2.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
