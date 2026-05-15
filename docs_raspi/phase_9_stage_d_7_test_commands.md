# Phase 9 — Stufe D.7 — Test-Anleitung

**Was geprüft wird:** Bei einem USB-Disconnect stirbt der Reader-Thread
nicht mehr (D.6-Verhalten), sondern geht in eine Backoff-Schleife und
versucht wiederholt `open(path)`. Während des Backoff bleibt
`is_running()` true und `died()` false. `write()` schlägt mit ERROR
fehl (Port closed), `read()` echoiert weiterhin den letzten Sollwert.
Bei erfolgreichem Reopen läuft der Reader normal weiter — Plugin bleibt
in INACTIVE bis User `switch_controllers --activate` aufruft.

**Was NICHT in D.7 in CI geprüft wird (User-Entscheidung Plan-Option C):**
- Reconnect-Erfolgs-Pfad (`open()` klappt nach Disconnect) → **Stage H** mit echter HW
- ERROR_REPORT-Übersetzungs-Tabelle → **D.8**

PTYs können den slave-Pfad nach master-close nicht wiederbeleben, daher
testen wir in CI nur „Reader bleibt im Backoff + stoppt sauber". Den
Erfolgs-Pfad kann Stage H mit z.B. firmware-SIGINT oder USB-authorized-
Toggle triggern.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.7.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine `warning:`.

---

## Test D.7.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 182 tests, 0 errors, 0 failures, 15 skipped`

---

## Test D.7.3 — D.7-Tests fokussiert (5 Tests, ~1.5 s)

```bash
./build/hexapod_hardware/test_servo2040_reader \
    --gtest_filter="ReaderReconnect.*"
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="HexapodSystemReconnect.*"
```

**Erwartung:**
```
[==========] 4 tests from ReaderReconnect (~1 s)
[  PASSED  ] 4 tests.
[==========] 1 test from HexapodSystemReconnect (~0.5 s)
[  PASSED  ] 1 test.
```

Die fünf Tests:

| Test (Suite) | Was geprüft wird |
|---|---|
| `ReaderReconnect.ReaderEntersReconnectLoopInsteadOfDying` | pty-Pair + master close → Reader sieht POLLHUP, geht in Backoff. Nach 200 ms: `is_running()=true`, `died()=false` |
| `ReaderReconnect.ReconnectBackoffRespectsStopSignal` | pty-Pair + master close + 300 ms Wait → Reader ist mid-Backoff. `stop()` muss in < 200 ms joinen (50-ms-Sleep-Chunks) |
| `ReaderReconnect.AdoptedFdMarksDiedBecauseNoPathToRetry` | `port.adopt_fd(...)` (kein Pfad) + master close → Reader kann nicht reconnecten, setzt `died_=true`, exit |
| `ReaderReconnect.ParallelWriteDoesNotCrashDuringReconnect` | 1-kHz-Writer-Thread parallel zu Disconnect → kein Crash, write_all liefert mix aus OK (vor Disconnect) und throw (nach close) |
| `HexapodSystemReconnect.PluginSurfacesErrorWhileReaderRetriesReconnect` | full lifecycle: configure → disconnect → 5× write() ERROR persistent, read() OK (echo), on_cleanup unterbricht Backoff in < 500 ms |

---

## Test D.7.4 — Tests an D.7-Semantik in HexapodSystemWriteRead

D.7 hat zwei D.6-Tests angepasst (waren auf der alten Annahme „pty-close
→ reader.died()=true" gebaut). Diese laufen jetzt mit der D.7-Vertrags-
änderung:

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="HexapodSystemWriteRead.PtyRead*:HexapodSystemWriteRead.PtyWrite*ReturnsError*"
```

**Erwartung:**
- `PtyReadStaysOkWhileReaderRetriesReconnect` — verifiziert: `read()`=OK
  während Backoff (Reader retried, `died_=false`)
- `PtyWriteReturnsErrorWhilePortClosedDuringReconnect` — verifiziert:
  `write()`=ERROR (Port closed, write_all wirft "port not open")

Beide Tests sind in `HexapodSystemWriteRead`-Suite (D.6) verblieben weil
sie auf den D.6-Code-Pfaden testen, aber die Erwartungen sind jetzt
D.7-konsistent. Code-Kommentare im Test erklären den Vertragwechsel.

---

## Test D.7.5 — Backoff-Sequenz visuell verifizieren

Die ReaderReconnect-Tests loggen jede Backoff-Iteration als WARN. Bei
voller Test-Ausgabe sieht man die Folge:

```bash
./build/hexapod_hardware/test_servo2040_reader \
    --gtest_filter="ReaderReconnect.ReaderEntersReconnectLoopInsteadOfDying"
```

**Erwartete Log-Sequenz:**
```
[ERROR] Servo2040Reader: read failed (...) — entering reconnect-loop
[WARN]  Servo2040Reader: reconnect attempt 1 — waiting 100 ms before trying to re-open '/dev/pts/N'
[WARN]  Servo2040Reader: reconnect attempt 2 — waiting 200 ms before trying to re-open '/dev/pts/N'
...
```

Die zeitlichen Abstände im Log entsprechen der Backoff-Sequenz
`{100, 200, 500, 1000, 2000, 5000, 5000}` ms (nach 200 ms Wait
ist Test-Ende, daher sieht man nur die ersten zwei Iter).

---

## Test D.7.6 — Stop-Latenz präzise messen

Die 50-ms-Sleep-Chunks im reconnect_loop garantieren, dass `stop()`
während Backoff nicht 5 s warten muss. Verifiziert durch:

```bash
./build/hexapod_hardware/test_servo2040_reader \
    --gtest_filter="ReaderReconnect.ReconnectBackoffRespectsStopSignal"
```

**Erwartung:** `stop()` returnt in < 200 ms (siehe `EXPECT_LT` im Test).
Sollte das je auf < 100 ms tightenen, kann der Test entsprechend
verschärft werden.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `ReaderEntersReconnectLoopInsteadOfDying` failt mit `died()=true` | Reader-Code geht direkt zu died_=true ohne reconnect_loop | `loop()`-`catch (system_error)` muss `reconnect_loop(port)` aufrufen statt `died_=true; return;` |
| `ReconnectBackoffRespectsStopSignal` failt mit > 200 ms | Sleep ist nicht in Chunks unterteilt | `reconnect_loop` muss `sleep_for(50ms)` in Schleife mit `stop_requested_`-Check nutzen, nicht `sleep_for(wait_ms)` am Stück |
| `AdoptedFdMarksDiedBecauseNoPathToRetry` failt mit Reader-läuft-weiter | Early-out für `path.empty()` fehlt im reconnect_loop | Nach `port.path()`: wenn empty → `died_=true; return false;` |
| `ParallelWriteDoesNotCrashDuringReconnect` SEGFAULT | mutex-Inkonsistenz oder UAF zwischen Reader und Writer | shared_mutex-Locks in SerialPort prüfen, kein externer Lock im reconnect_loop |
| `PluginSurfacesErrorWhileReaderRetriesReconnect` failt mit `write()=OK` | Reader hat Disconnect nicht erkannt oder Port-State falsch | Reader-Logs auf "read failed" prüfen, port.is_open() im Plugin checken |
| `PluginSurfacesErrorWhileReaderRetriesReconnect` failt mit `read()=ERROR` | reader.died()-Check in read() triggert fälschlich | `died_` darf bei Disconnect mit valid path NICHT true werden |
| `PtyReadStaysOkWhileReaderRetriesReconnect` failt mit ERROR | D.6-Code-Pfad zur ERROR-Surface (alte D.6-Annahme) statt OK | Verifizieren dass reader.died() bei retries false bleibt |
| openpty SEGFAULT bei Test-Run | `nullptr` als slave_fd übergeben | Alle openpty-Aufrufe brauchen `&slave_fd` + `::close(slave_fd)` direkt danach |
| Reader-Thread hängt nach reader.stop() | stop_requested_ wird im Sleep-Chunk nicht geprüft | inner for-loop in reconnect_loop muss `!stop_requested_` als Bedingung haben |

---

## Statusmeldung an Claude

- `D.7.1–D.7.6 alle grün` → weiter mit **D.8** (ERROR_REPORT-Logging-Detail:
  pro Error-Code human-readable Message-Translation, evtl. NaN-Throttle
  wenn nötig)
- `D.7.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
