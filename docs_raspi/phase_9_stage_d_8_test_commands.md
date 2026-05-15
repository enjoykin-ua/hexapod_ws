# Phase 9 — Stufe D.8 — Test-Anleitung

**Was geprüft wird:** Bei einem `ERROR_REPORT`-Frame von der Firmware
formatiert das Plugin eine **per-Code human-readable Message** und wählt
die passende **Severity** (`WARN` / `ERROR` / `FATAL`). Damit ist
Diagnose direkt aus den ROS-Logs lesbar, ohne Hex-Look-up in
`PROTOCOL.md`.

**Was NICHT in D.8 in CI geprüft wird:**
- RCLCPP-Log-Output-Capture (komplex, nicht nötig — Format-Tests sind
  pure-function und prüfen die formatierten Strings direkt)
- Per-Servo-Stromsensor-Codes (`0x20 SERVO_OVERCURRENT`) — Servo2040
  hat das nicht; getestet ist nur dass der Code im unknown-Fallback
  landet

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.8.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine `warning:`.

---

## Test D.8.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 200 tests, 0 errors, 0 failures, 18 skipped`

---

## Test D.8.3 — D.8-Tests fokussiert (11 Tests, < 100 ms)

```bash
./build/hexapod_hardware/test_error_report_log
```

**Erwartung:**
```
[==========] 11 tests from ErrorReportLogFormat (< 100 ms total)
[  PASSED  ] 11 tests.
```

Die elf Tests:

| Test | Was geprüft wird |
|---|---|
| `FrameCrcIsWarnAndMentionsCrc` | `0x01`: severity=WARN, Message enthält "CRC" |
| `FrameMalformedMentionsExpectedLen` | `0x02` mit `aux=42`: severity=WARN, Message enthält "malformed" + "42" |
| `UnknownOpcodeIsWarnAndMentionsDrift` | `0x03`: severity=WARN, Message enthält "drift" |
| `PayloadLenMentionsExpectedSize` | `0x04` mit `aux=18`: severity=WARN, Message enthält "payload" + "18" |
| `PulseOutOfRangeMentionsServoIdxAndClamped` | `0x10`, `servo_idx=7`, `aux=2500`: severity=WARN, Message enthält "clamped" + "servo 7" + "2500" |
| `TotalOvercurrentIsFatalAndMentionsLimit` | `0x21` mit `aux=4200`: severity=FATAL, Message enthält "4200" + "ALL" |
| `UndervoltageIsErrorAndMentionsMv` | `0x30` mit `aux=4500`: severity=ERROR, Message enthält "undervoltage" + "4500"; **kein "TRIP"** (Variante B: einheitlich, keine Sub-Cases) |
| `WatchdogTrippedIsFatalAndMentionsReset` | `0x40`: severity=FATAL, Message enthält "WATCHDOG" + "RESET" |
| `UnknownCodeFallsBackToHexDump` | `0xAB` (nicht in Spec): severity=ERROR, Message enthält "Unknown" + "0xAB" |
| `ServoOvercurrentCodeFallsBackToUnknown` | `0x20`: severity=ERROR, Message enthält "Unknown" + "0x20". **Pinnt das Contract** — wenn jemand 0x20 versehentlich im switch ergänzt, failt der Test |
| `AllSpecCodesReturnNonEmptyString` | Smoke: alle 8 Codes + 1 unknown produzieren nicht-leere Strings |

---

## Test D.8.4 — Plugin-Integration manuell verifizieren

Der bestehende D.6-Test `PtyReadDrainsFirmwareErrorReports` injiziert
einen `WATCHDOG_TRIPPED`-Frame via PTY-Master und ruft `plugin.read()`.
Mit D.8 sieht man im Log jetzt die formatierte Message statt der generischen:

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*PtyReadDrainsFirmwareErrorReports*" 2>&1 | grep -E "FATAL|ERROR|WARN"
```

**Erwartung:** im Output muss vorkommen:
```
[FATAL] WATCHDOG_TRIPPED — host stopped sending frames > 200 ms, all servos disabled. Send RESET + ENABLE_SERVO to recover.
```

(NICHT mehr „Firmware error: code=0x40 servo_idx=0 aux=0 (per-code detail comes in stage D.8)" wie vor D.8.)

---

## Test D.8.5 — Severity-Routing verifizieren

Die Severity wird im D.6-`PtyReadDrainsFirmwareErrorReports`-Test
indirekt geprüft: `WATCHDOG_TRIPPED` muss als `[FATAL]` geloggt werden,
nicht `[ERROR]`. Verifiziert durch:

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*PtyReadDrainsFirmwareErrorReports*" 2>&1 | grep "FATAL"
```

Mindestens eine FATAL-Zeile mit WATCHDOG_TRIPPED-Text erwartet.

---

## Test D.8.6 — Severity-Klassen einzeln

Die `ErrorReportLogFormat`-Tests verifizieren auch die Severity pro Code.
Sortiert nach Severity:

```bash
# WARN: 5 Codes (FRAME_CRC, FRAME_MALFORMED, UNKNOWN_OPCODE, PAYLOAD_LEN, PULSE_OUT_OF_RANGE)
./build/hexapod_hardware/test_error_report_log \
    --gtest_filter="*Crc*:*Malformed*:*UnknownOpcode*:*PayloadLen*:*PulseOutOfRange*"

# FATAL: 2 Codes (TOTAL_OVERCURRENT, WATCHDOG_TRIPPED)
./build/hexapod_hardware/test_error_report_log \
    --gtest_filter="*TotalOvercurrent*:*Watchdog*"

# ERROR: UNDERVOLTAGE + Unknown-Fallback
./build/hexapod_hardware/test_error_report_log \
    --gtest_filter="*Undervoltage*:*UnknownCode*:*ServoOvercurrent*"
```

Jeder Aufruf sollte alle gefilterten Tests grün durchlaufen lassen.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| Format-Test failt mit „expected substring 'X' not found" | Wording im Format-String geändert oder Translation falsch | `format_error_report` im switch-Case anpassen, Test-Strings synchronisieren |
| `ServoOvercurrentCodeFallsBackToUnknown` failt mit „Unknown nicht im String" | Jemand hat `0x20` versehentlich im switch ergänzt | 0x20-Case wieder rausnehmen (Servo2040 hat kein per-servo sensing — siehe Plan-Doku §D.8 Variante A) |
| `UndervoltageIsErrorAndMentionsMv` failt mit „TRIP im String gefunden" | Jemand hat WARN/TRIP-Split eingebaut | Plan-Doku §D.8 Variante B: einheitliche Message ohne Sub-Cases |
| `WatchdogTrippedIsFatalAndMentionsReset` failt mit „RESET nicht im String" | Recovery-Hint vergessen | RESET-Hint MUSS in der Message stehen — Firmware NACKs ENABLE_SERVO bis RESET den Trip clear't |
| Severity-Check failt | switch-case-Gruppe in `severity_for` falsch | Plan-Doku §D.8 Severity-Mapping konsultieren |
| Plugin-Test sieht `[ERROR]` statt `[FATAL]` für Watchdog | severity_for-switch fehlt WATCHDOG_TRIPPED | In `severity_for` muss WATCHDOG_TRIPPED in die FATAL-case-Gruppe |
| Build-Fehler `args...` → `args ...` | uncrustify-Style | Space vor parameter-pack-expansion (`args ...`) |
| Build-Warnung `unused-parameter` im switch | Variadic-Args nicht alle verwendet | snprintf-Helper sollte alle Args konsumieren |
| `AllSpecCodesReturnNonEmptyString` failt mit Empty-String | Default-Branch fehlt oder schlägt fehl | `format_error_report` MUSS für jeden möglichen uint8_t-Code etwas non-empty liefern |

---

## Statusmeldung an Claude

- `D.8.1–D.8.6 alle grün` → **Stufe D komplett.** Weiter mit **Stufe E**
  (Plugin-Registrierung: `ros2 control list_hardware_components`,
  pluginlib-Loader-Smoke-Test)
- `D.8.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
