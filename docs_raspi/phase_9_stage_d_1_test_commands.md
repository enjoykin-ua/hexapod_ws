# Phase 9 — Stufe D.1 — Test-Anleitung

**Was geprüft wird:** Der `SerialPort`-Wrapper öffnet einen POSIX-FD
sauber, leakt nichts bei Exceptions, transportiert alle 256 Byte-Werte
binär-exakt (insbesondere `0x0D` und `0x0A` — die cfmakeraw-Verifikation
schützt vor dem Phase-7 C.4 Bug-Klasse), liefert Read-Timeouts korrekt,
wirft beim Write-Timeout, und der `std::shared_mutex` serialisiert
korrekt gegen die Reconnect-Phase.

**Was NICHT in D.1 geprüft wird:**
- Reader-Thread-Logik → **D.2**
- Echte USB-Anbindung an Servo2040 → **Stufe H**
- Reconnect-Backoff bei echtem USB-Disconnect → **Stufe H**

D.1 ist ein reiner **C++-Unit-Test-Smoke-Test mit `openpty(3)`** (Master-/
Slave-PTY-Pair). Kein ROS-Stack, keine Hardware.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.1.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `Summary: 1 package finished [X.XXs]`
- **Kein** Block mit `stderr: hexapod_hardware`
- Keine `warning:`-Zeilen

---

## Test D.1.2 — Volle Test-Suite grün (7/7)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** Letzte Zusammenfassung
`100% tests passed, 0 tests failed out of 7`.

Die sieben Tests sind:
1. `test_calibration` (30 gtest-Cases, unverändert seit C)
2. `test_serial_port` — **neu in D.1** (14 gtest-Cases)
3. `test_servo2040_protocol` (36 gtest-Cases, unverändert seit B)
4. `cppcheck`
5. `lint_cmake`
6. `uncrustify`
7. `xmllint`

---

## Test D.1.3 — Alle 14 SerialPort-gtest-Cases sichtbar machen

```bash
./build/hexapod_hardware/test_serial_port
```

**Erwartung am Ende:**
```
[==========] 14 tests from 3 test suites ran. (~1.2 s total)
[  PASSED  ] 14 tests.
```

Die drei Test-Suites:

- **`SerialPortLifecycle` (5 Tests)** — default-konstruiert ist closed,
  adopt_fd macht open, close ist idempotent, doppeltes adopt_fd wirft,
  `open()` auf nicht-existenten Path wirft `std::system_error` mit
  Pfad-Name in der Message

- **`SerialPortPty` (7 Tests)** — alle mit openpty-Fixture:
  - `RoundtripAll256ByteValues` — alle 0x00..0xFF kommen byte-exakt durch
  - **`CarriageReturnSurvivesByteExact`** — `0x0D` rein, `0x0D` raus
    (NICHT `0x0A`! Wenn dieser Test failt mit `0x0A`, ist cfmakeraw nicht
    aktiv und die Phase-7-Bug-Klasse ist wieder offen)
  - **`LineFeedSurvivesByteExact`** — `0x0A` rein, `0x0A` raus (kein
    Stripping)
  - **`MixedCrLfSequencesSurviveExact`** — gemischte CR/LF-Sequenz mit
    eingebettetem 0x00 byte-exakt durch
  - `ReadSomeReturnsZeroOnTimeout` — Master schreibt nichts, `read_some`
    blockiert ~1 s und returnst 0 (kein Crash, kein Throw)
  - `WriteAllDeliversAllBytes` — alle geschriebenen Bytes kommen auf
    der Master-Seite an
  - `WriteBlocksUntilExclusiveLockReleased` — Thread hält
    `exclusive_lock` für 200 ms, paralleler `write_all`-Thread blockiert
    solange (verifiziert mit Zeitmessung) und kann erst danach schreiben

- **`SerialPortError` (2 Tests)** — `write_all` und `read_some` auf
  geschlossenem Port werfen `std::runtime_error`

---

## Test D.1.4 — cfmakeraw-Wirksamkeit fokussiert

Optional, um spezifisch die Bug-Klasse aus Phase 7 C.4 zu verifizieren:

```bash
./build/hexapod_hardware/test_serial_port \
    --gtest_filter="*CarriageReturn*:*LineFeed*:*MixedCrLf*"
```

**Erwartung:**
```
[       OK ] SerialPortPty.CarriageReturnSurvivesByteExact
[       OK ] SerialPortPty.LineFeedSurvivesByteExact
[       OK ] SerialPortPty.MixedCrLfSequencesSurviveExact
[  PASSED  ] 3 tests.
```

Falls einer dieser Tests fehlschlägt mit Werten wie `0x0A` statt `0x0D`,
ist `cfmakeraw()` nicht (oder falsch) angewendet — siehe
`src/serial_port.cpp::configure_termios()`.

---

## Test D.1.5 — Mutex-Serialisierung fokussiert

Optional, um spezifisch das Reconnect-Race-Pattern zu verifizieren:

```bash
./build/hexapod_hardware/test_serial_port \
    --gtest_filter="*WriteBlocksUntilExclusive*"
```

**Erwartung:**
```
[       OK ] SerialPortPty.WriteBlocksUntilExclusiveLockReleased
```

Test misst dass der Writer-Thread für mind. 200 ms blockiert hat bevor
der `exclusive_lock` freigegeben wurde — wenn er früher zurückkommt,
serialisiert der Mutex nicht und der Reconnect-Race aus D.7 ist offen.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `CarriageReturnSurvivesByteExact` zeigt `0x0A` | `cfmakeraw` fehlt oder ICRNL aktiv | `configure_termios()` in `src/serial_port.cpp` prüfen |
| `ReadSomeReturnsZeroOnTimeout` schlägt mit Hang fehl | `poll()`-Timeout zu hoch oder `O_NONBLOCK` nicht gesetzt | `READ_TIMEOUT_MS`-Konstante + `open()`-Flags |
| `WriteBlocksUntilExclusiveLockReleased` returnst zu früh | `write_all` nimmt keinen shared_lock | `write_all()`-Implementation: `std::shared_lock<...> lock(mtx_);` muss vor dem write-Loop stehen |
| `OpenNonexistentPathThrowsSystemError` failt | falsche Exception-Klasse | `open()`-throw muss `std::system_error` mit `system_category()` sein, Message muss Pfad enthalten |
| Build-Fehler `openpty` / `-lutil` not found | Test-Link fehlt | `CMakeLists.txt`: `target_link_libraries(test_serial_port ${PROJECT_NAME} util)` |

---

## Statusmeldung an Claude

- `D.1.1–D.1.5 alle grün` → weiter mit D.2 (Reader-Thread)
- `D.1.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler, nur der relevante gtest-Output.
