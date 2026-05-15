# Phase 9 — Stufe B — Test-Anleitung

**Was geprüft wird:** Der Wire-Protokoll-Layer (`servo2040_protocol.*`)
ist korrekt implementiert: CRC-16/CCITT-FALSE liefert den kanonischen
Selbsttest-Wert, COBS-Roundtrip funktioniert für alle relevanten
Eingaben (inkl. Edge-Cases an der 254/255-Byte-Grenze), alle vier
Frame-Encoder produzieren Bytes, die der Decoder korrekt zurückliest,
und CRC-Korruption / Frame-Truncation werden zuverlässig erkannt.

**Was NICHT in Stufe B geprüft wird:**
- Echte USB-Kommunikation mit Servo2040 → **Stufe H**
- Streaming-Reader (Bytes häppchenweise + auf 0x00 splitten) → **Stufe D**
- Plugin-Lifecycle, `read()`/`write()` → **Stufe D**

Diese Stufe ist ein reiner **C++-Unit-Test-Smoke-Test**. Kein
ROS-Stack, kein Servo2040 angeschlossen.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test B.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `Summary: 1 package finished [X.XXs]`
- **Kein** Block mit `stderr: hexapod_hardware`
- Keine `warning:`-Zeilen im Output

---

## Test B.2 — Volle Test-Suite grün (6/6)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** Letzte Zusammenfassung zeigt
`100% tests passed, 0 tests failed out of 6`.

Die sechs Tests sind:
1. `test_calibration` — Stub aus Stufe A (1 gtest-Case)
2. **`test_servo2040_protocol`** — neu in Stufe B (29 gtest-Cases)
3. `cppcheck`
4. `lint_cmake`
5. `uncrustify`
6. `xmllint`

---

## Test B.3 — Alle 29 gtest-Cases sichtbar machen

Den gtest direkt aufrufen, damit man sieht welche Test-Cases laufen:

```bash
./build/hexapod_hardware/test_servo2040_protocol
```

**Erwartung am Ende:**
```
[==========] 29 tests from 5 test suites ran. (X ms total)
[  PASSED  ] 29 tests.
```

Die fünf Test-Suites sind:
- `Crc16CcittFalse` (3 Tests) — Self-Test 0x29B1, empty input, Determinismus
- `Cobs` (10 Tests) — Empty, single zero, no zeros, zero in middle, alle
  256 Byte-Werte, 254/255-Byte-Grenze, Reject Zero in Stream, Reject Truncated
- `Frame` (11 Tests) — Encode-Trailing-Zero, Roundtrips für GET_STATE/RESET/
  ENABLE/DISABLE/SET_TARGETS (neutral, distinct, negative), Decode-ohne-Trailer,
  Reject Corrupted CRC, Reject Truncated, Reject Empty
- `PayloadDecoders` (4 Tests) — STATE valid, STATE wrong length, ERROR_REPORT
  valid, ERROR_REPORT wrong length
- `EndToEnd` (1 Test) — encode STATE-Frame → decode_frame → decode_state

---

## Test B.4 — CRC-Selbsttest punktuell

Optional, zur Beruhigung dass die zentrale CRC-Konstante stimmt:

```bash
./build/hexapod_hardware/test_servo2040_protocol --gtest_filter="*SelfTestString*"
```

**Erwartung:**
```
[ RUN      ] Crc16CcittFalse.SelfTestString123456789
[       OK ] Crc16CcittFalse.SelfTestString123456789 (0 ms)
```

Dieser Test verifiziert `crc16("123456789") == 0x29B1`. Wenn der grün
ist, ist die CRC-Implementation kompatibel mit der Servo2040-Firmware
(die in Phase 7 mit demselben Vektor verifiziert wurde).

---

## Test B.5 — Wire-Format-Probe per Hex-Dump

Optional und manuell — damit man **sieht** wie ein Frame auf der Wire
aussieht. Lokales kleines Programm im build-Verzeichnis nicht da, aber
mit `xxd` kann man den encoded Wire-Output über einen Mini-Roundtrip
sichtbar machen. Wer das später für Vergleich mit der Firmware braucht:
`tools/test_servo2040.py` im fw-Repo macht das gleiche in Python und
gibt Hex-Strings aus.

Konkret das Phase-9-relevante Beispiel aus PROTOCOL.md §4.1
(SET_TARGETS, alle 18 Servos auf 1500 µs):

Pre-COBS (43 Byte):
```
00 01 24 DC 05 DC 05 DC 05 DC 05 DC 05 DC 05 DC 05
DC 05 DC 05 DC 05 DC 05 DC 05 DC 05 DC 05 DC 05 DC
05 DC 05 DC 05 DC 05 CRCL CRCH
```

Unser Test `Frame.RoundtripSetTargetsAllNeutral` verifiziert exakt
dieses Layout (Bytes 3..38 = `DC 05` × 18 im decodeten Frame).

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `Crc16CcittFalse.SelfTestString*` failt | Init-Register nicht `0xFFFF`, oder Polynom-Reflektion versehentlich an | `crc16_ccitt_false` in `src/servo2040_protocol.cpp` prüfen — Init und Schleife |
| `Cobs.BoundaryAt254*` failt | 0xFF-Chain-Extension nicht korrekt — entweder Encoder hängt fälschlicherweise implizite Null an, oder Decoder fügt eine ein | Beide Branches in `cobs_encode`/`cobs_decode` neu prüfen — Block-Länge bei `count == 0xFF` |
| `Frame.RoundtripSetTargetsNegativePulse` failt | int16-zu-uint8-Konversion mit Sign-Extension-Bug | `encode_set_targets` und Wire-Layout in den Test re-checken — beide Seiten müssen die int16-Bytes als unsigned behandeln |
| `Frame.DecodeRejectsCorruptedCrc` läuft als **PASSED** wenn es FAILT erwartet wird | Decoder akzeptiert kaputten CRC | `decode_frame` CRC-Vergleich prüfen |

---

## Statusmeldung an Claude

Nach Durchlauf der Tests reicht eine knappe Rückmeldung:
- `B.1–B.3 alle grün` → wir können mit Stufe C (Kalibrierungs-Lib mit
  yaml-cpp und piecewise-linearer Konversion) weitermachen
- `B.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe der gtest-Logs ist nicht nötig — nur bei Fehlern den
relevanten gtest-Output (failende Assertion + Datei:Zeile).
