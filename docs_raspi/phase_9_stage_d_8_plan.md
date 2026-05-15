# Phase 9 — Stufe D.8 — Plan

> **Status:** Plan, noch nicht implementiert. **Code beginnt erst nach
> User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_stage_d_plan.md §D.8`](phase_9_stage_d_plan.md)
> — Übersetzungs-Tabelle Error-Code → Log-Message.
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_d_8_test_commands.md`).

---

## Ziel der Sub-Stage

Aktuell (Stand D.6/D.7): `read()` drainet die `ErrorReport`-Queue vom
Reader-Thread und loggt jeden Eintrag mit einer **generischen** Message:

```
[ERROR] Firmware error: code=0x40 servo_idx=0 aux=0 (per-code detail comes in stage D.8)
```

Das ist diagnose-arm — der User sieht den Hex-Code, muss aber in
`PROTOCOL.md §3.4` nachschlagen was 0x40 bedeutet. D.8 ersetzt das durch
**human-readable Messages mit interpretiertem `aux`-Feld**, z.B.:

```
[FATAL] Firmware: WATCHDOG_TRIPPED — all servos disabled. Send RESET to recover.
[WARN]  Firmware: PULSE_OUT_OF_RANGE on servo 7, clamped to 2500 µs
[ERROR] Firmware: SERVO_OVERCURRENT on servo 3 at 850 mA, that servo disabled
[ERROR] Firmware: TOTAL_OVERCURRENT at 4200 mA — all servos disabled
```

Damit ist eine Fehler-Diagnose **direkt aus den ROS-Logs** machbar —
Phase-10-Bringup wird das brauchen, wenn die ersten echten Servos
loslegen und sich vermutlich Strom/Spannungs-Probleme zeigen werden.

---

## Was D.8 NICHT macht

- **Kein neuer Code im Reader-Thread.** Die Drainage läuft schon (D.6),
  wir tauschen nur die Log-Formatierung im Plugin's `read()`.
- **Kein Auto-Recovery** bei bestimmten Codes (z.B. auto-RESET nach
  WATCHDOG_TRIPPED). User entscheidet manuell — bewusste Phase-9-Design-
  Entscheidung (Plan-Doku §7).
- **Kein NaN-Throttle aus D.6-Post-Review** — orthogonal zu D.8.
  Falls in Phase 10/11 nötig: dort als kleines Standalone-Fix.
- **Kein Counter-basiertes Log-Throttle** für sich wiederholende Codes.
  Bei einem hängenden Servo könnte z.B. SERVO_OVERCURRENT bei jedem
  Tick kommen — wäre Spam. Aber: in der Firmware ist `send_error` schon
  „nur einmal pro Trip-Event" gestaltet (Phase-7 stage C.1), also
  in der Praxis kein Spam.

---

## Logik-Skizze

### Neue freie Funktion `format_error_report`

Ich schlage ein **neues Modul** vor, weil die Funktion eine
abgegrenzte Aufgabe hat und so leicht isoliert testbar ist:

```
src/hexapod_hardware/
├── include/hexapod_hardware/
│   ├── error_report_log.hpp     # NEU
│   └── ...
├── src/
│   ├── error_report_log.cpp     # NEU
│   └── ...
└── test/
    ├── test_error_report_log.cpp  # NEU
    └── ...
```

**API-Skizze:**

```cpp
// error_report_log.hpp
namespace hexapod_hardware
{

// Categorise an ErrorReport for log-level routing. Different codes need
// different severity (a watchdog trip is louder than a clamped pulse).
enum class ErrorSeverity { WARN, ERROR, FATAL };

// Returns the severity that read() should use to log this report.
ErrorSeverity severity_for(const ErrorReport & er);

// Format a human-readable single-line message for the given report.
// The format includes:
//   - the symbolic error name (e.g. "WATCHDOG_TRIPPED")
//   - servo_idx if relevant for that code
//   - aux value interpreted per code (mA, µs, mV, expected-LEN, ...)
//   - a hint for recovery if applicable
// Always returns SOMETHING, even for unknown codes (fallback hex dump).
std::string format_error_report(const ErrorReport & er);

}  // namespace hexapod_hardware
```

### Integration in `read()`

```cpp
// In hexapod_system.cpp, replacing the current generic log:
for (const auto & er : reader_.drain_error_queue()) {
  const std::string msg = format_error_report(er);
  switch (severity_for(er)) {
    case ErrorSeverity::WARN:
      RCLCPP_WARN(plugin_logger(), "%s", msg.c_str());
      break;
    case ErrorSeverity::ERROR:
      RCLCPP_ERROR(plugin_logger(), "%s", msg.c_str());
      break;
    case ErrorSeverity::FATAL:
      RCLCPP_FATAL(plugin_logger(), "%s", msg.c_str());
      break;
  }
}
```

### Pro Error-Code: Severity + Message-Vorschlag

Aus PROTOCOL.md §3.4 (Phase-7 Firmware) und meiner Einschätzung der
operativen Konsequenz — **angepasst an User-Entscheidungen vom 2026-05-15**
(siehe „Finale Entscheidungen" weiter unten):

| Code | Severity | Format-String (Pseudo) | Begründung |
|---|---|---|---|
| `0x01 FRAME_CRC` | WARN | `"Firmware reported CRC error on incoming frame"` | Single Frame verworfen — Firmware re-syncs; Plugin reagiert nicht. Diagnose-nützlich aber nicht kritisch |
| `0x02 FRAME_MALFORMED` | WARN | `"Firmware reported malformed frame (LEN field mismatch, expected %d)"` | gleiche Klasse wie CRC: single Frame weg, kein Roboter-Risiko |
| `0x03 UNKNOWN_OPCODE` | WARN | `"Firmware reported unknown opcode — host/firmware protocol drift?"` | Host hat einen Opcode geschickt den die Firmware nicht kennt. Eher Plugin-Bug als Hardware-Problem |
| `0x04 PAYLOAD_LEN` | WARN | `"Firmware reported payload length mismatch (expected %d for that opcode)"` | wie 0x02, single Frame |
| `0x10 PULSE_OUT_OF_RANGE` | WARN | `"Firmware clamped pulse on servo %u to %d µs (host calibration too generous?)"` | Phase-9-Design: Firmware clampt, meldet einmal. Hinweis auf zu weite Calibration |
| ~~`0x20 SERVO_OVERCURRENT`~~ | — | (weggelassen) | **Servo2040 hat keinen Per-Servo-Stromsensor → Firmware kann das physikalisch nicht senden. Fällt in „unknown code"-Fallback** |
| `0x21 TOTAL_OVERCURRENT` | FATAL | `"Total servo current %d mA exceeded limit — ALL servos disabled"` | Hard-Trip, ganzer Roboter aus. Sehr ernst |
| `0x30 UNDERVOLTAGE` | ERROR | `"Firmware reported undervoltage at %d mV — check power supply"` | **Keine WARN/TRIP-Unterscheidung im Plugin** (User-Entscheidung Variante B). Severity ERROR ist actionable, deckt beide Fälle |
| `0x40 WATCHDOG_TRIPPED` | FATAL | `"WATCHDOG_TRIPPED — host stopped sending frames > 200 ms, all servos disabled. Send RESET + ENABLE_SERVO to recover."` | Hard-Trip. Operative Konsequenz: Plugin sollte sich neu booten/aktivieren |
| Unbekannter Code (inkl. 0x20) | ERROR | `"Unknown firmware error: code=0x%02X servo_idx=%u aux=%d"` | Forward-Compat falls Phase-7-Firmware-Update neue Codes einführt (oder Per-Servo-Sensing-Hardware-Revision später) |

---

## Tests

### Plan: pro Code ein Format-Test + ein Severity-Test

Wir testen `format_error_report` und `severity_for` **direkt als pure
functions** — kein RCLCPP-Log-Capture nötig, viel sauberer.

**Suite `ErrorReportLogFormat`** (~10 Tests, angepasst nach User-Entscheidungen):

| # | Test | Was wird geprüft |
|---|---|---|
| 1 | `FrameCrcIsWarnAndMentionsCrc` | Code 0x01: severity=WARN, Message enthält "CRC" |
| 2 | `FrameMalformedMentionsExpectedLen` | Code 0x02 mit aux=42: Message enthält "42" (expected LEN) |
| 3 | `UnknownOpcodeIsWarnAndMentionsDrift` | Code 0x03: WARN, Hinweis auf protocol-drift |
| 4 | `PayloadLenMentionsExpectedSize` | Code 0x04 mit aux=18: Message enthält "18" |
| 5 | `PulseOutOfRangeMentionsServoIdxAndClamped` | Code 0x10, servo_idx=7, aux=2500: enthält "7" und "2500" |
| 6 | `TotalOvercurrentIsFatalAndMentionsLimit` | Code 0x21, aux=4200: severity=FATAL, enthält "4200" und "ALL" |
| 7 | `UndervoltageIsErrorAndMentionsMv` | Code 0x30 mit aux=4500: severity=ERROR, enthält "4500", **eine einheitliche Message** (kein WARN/TRIP-Split) |
| 8 | `WatchdogTrippedIsFatalAndMentionsReset` | Code 0x40: severity=FATAL, enthält "RESET" |
| 9 | `UnknownCodeFallsBackToHexDump` | Code 0xAB (nicht in Spec): severity=ERROR, Message enthält "0xAB" |
| 10 | `ServoOvercurrentCodeFallsBackToUnknown` | Code 0x20: severity=ERROR, Message enthält "0x20" und "Unknown" (verifiziert dass 0x20 als Forward-Compat-Code im unknown-Pfad landet, nicht versehentlich versteckt) |
| 11 | `AllSpecCodesReturnNonEmptyString` | Smoke: alle 0x01/0x02/0x03/0x04/0x10/0x21/0x30/0x40 + 1× unknown produzieren nicht-leere Strings |

Für jeden Test eine simple Assertion mit `EXPECT_NE(msg.find("..."), std::string::npos)`.

### Integration-Test im Plugin (HexapodSystemWriteRead-Suite)

**Frage an dich (Q5 unten):** Brauchen wir einen Plugin-Integration-Test,
oder reichen die Format-Tests + der bestehende D.6-`PtyReadDrainsFirmwareErrorReports`?
Mein Vorschlag: **nein, keine Plugin-Integration**. Der D.6-Test
verifiziert schon dass die Pipeline (master inject → reader → drain →
plugin.read() loggt) funktioniert. D.8 verändert nur die Formatierung
des Logs — Log-Inhalt zu prüfen würde RCLCPP-Log-Capture brauchen
(komplex). Format-Tests reichen.

---

## Finale Entscheidungen (vom User am 2026-05-15 freigegeben)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Wo lebt `format_error_report`? | **A — Neues Modul `error_report_log.hpp/.cpp`** | Klar abgegrenzt, leicht testbar (~50 Z. Code + ~60 Z. Test) |
| 2 | Severity-Mapping & Code-Liste | **Severity-Tabelle OK, aber 0x20 SERVO_OVERCURRENT weglassen (Variante A)** | Servo2040 hat keinen Per-Servo-Stromsensor → Firmware kann den Code physikalisch nicht senden. Wenn er trotzdem käme (FW-Bug oder zukünftige Hardware-Rev), fällt er sauber in den „unknown code"-Fallback |
| 3 | UNDERVOLTAGE WARN/TRIP-Unterscheidung | **B — keine Unterscheidung, eine generische Message mit Severity ERROR** | Vermeidet Annahmen über die Firmware-Konvention (`servo_idx=0xFF` vs `0x00` war nur Plan-Doku-Spekulation, nicht in FW verifiziert). Bei Bedarf in Phase 10 nachjustieren wenn auf der Bench tatsächlich Undervoltage auftritt |
| 4 | Sprache der Log-Messages | **Englisch** | ROS-Norm, kompatibel mit `ros2 log`-Tools |
| 5 | Plugin-Integration-Test mit Log-Capture? | **Nein** (mein Vorschlag) | D.6-`PtyReadDrainsFirmwareErrorReports` deckt schon Pipeline ab; Format-Tests reichen für D.8 |
| 6 | NaN-Throttle in D.8 mitnehmen? | **A — skip** (mein Vorschlag) | Orthogonal zu ERROR_REPORT-Logging, Scope-Creep-Risiko. In Phase 10/H wenn spammy → eigenständiges Fix mit Counter-Throttle |

**Konsequenzen für die Implementation:**
- Plan-Liste reduziert auf **8 spezifizierte Codes** + 1 Fallback (statt 9+1)
- Tests reduziert auf **11 Tests** (statt 12) — keine Sub-Cases für UNDERVOLTAGE, 0x20 testet nur dass der Fallback greift
- Severity-Enum hat 3 Werte (WARN, ERROR, FATAL) — unverändert

---

## ~~Was offen ist und User-Feedback braucht~~ (entschieden, siehe oben)

1. **Wo lebt `format_error_report`?**
   - **A: Neues Modul `error_report_log.hpp/.cpp`** (mein Vorschlag) —
     klar abgegrenzt, leicht testbar, eigene Test-Datei. ~50 Zeilen Code,
     ~60 Zeilen Test.
   - B: Free function im anonymen Namespace in `hexapod_system.cpp` —
     weniger Files, aber Tests müssen Friend oder direkt via
     `test_hexapod_system.cpp` ergänzt werden.
   - C: Static-Method in `HexapodSystemHardware` — überflüssig OOP,
     ohne State-Bezug.

2. **Severity-Mapping passt so?** Aus der Tabelle:
   - Frame-Layer-Errors (CRC, MALFORMED, UNKNOWN_OPCODE, PAYLOAD_LEN) → **WARN**
   - PULSE_OUT_OF_RANGE → **WARN** (firmware clampt, Roboter läuft)
   - SERVO_OVERCURRENT → **ERROR** (1 Servo aus)
   - TOTAL_OVERCURRENT / UNDERVOLTAGE_TRIP / WATCHDOG_TRIPPED → **FATAL** (alle aus)
   - UNDERVOLTAGE_WARN → **WARN**
   - Unknown → **ERROR** (Forward-Compat)

   Alternative: alles auf ERROR vereinfachen. Aber Severity hilft beim
   Filtern in `ros2 topic echo /rosout`.

3. **UNDERVOLTAGE-Unterscheidung über `servo_idx`-Feld** OK? Das ist die
   PROTOCOL.md-spezifizierte Konvention. Wenn die Firmware mal das
   `aux`-Feld nutzen würde, müssten wir hier nachziehen. Aktuell: passt.

4. **Format-String-Stil: Sprachlich?** Aktuell schlage ich englische
   Messages vor (Kompatibilität mit `ros2 log`-Tools, üblicher ROS-
   Konvention). Alternative: deutsche Messages, passend zum
   Projekt-Kontext. Empfehlung: **englisch** (ROS-Norm), Kommentare aber
   weiterhin auf Deutsch.

5. **Plugin-Integration-Test?**
   - Mein Vorschlag: **nein** (Format-Tests reichen, D.6-Test deckt Pipeline ab).
   - Alternative: ein neuer Test in `HexapodSystemWriteRead` der
     z.B. WATCHDOG_TRIPPED injizt und via redirect von stderr den
     Log-Output capturet (Boilerplate ist groß).

6. **NaN-Throttle aus D.6-Post-Review** — in D.8 mitnehmen, oder skip?
   Aktuell: orthogonal, könnte reinpassen weil wir eh am Logging-Code
   arbeiten. Aber: Scope-Creep-Risiko. Vorschlag: **skip in D.8,
   eigenständiges Fix in Phase 10 falls in der Praxis spammy.**

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Sub-Stage fertig:

- [ ] D.8.1 Neues Modul `include/hexapod_hardware/error_report_log.hpp`:
  - `enum class ErrorSeverity { WARN, ERROR, FATAL };`
  - `ErrorSeverity severity_for(const ErrorReport &);`
  - `std::string format_error_report(const ErrorReport &);`
- [ ] D.8.2 Neues Modul `src/error_report_log.cpp`:
  - switch-Statement für **8 spezifizierte Codes** (0x01, 0x02, 0x03, 0x04, 0x10, 0x21, 0x30, 0x40) → severity + format
  - **0x20 SERVO_OVERCURRENT NICHT im switch** (Servo2040-Hardware kann das nicht senden — Variante A)
  - **UNDERVOLTAGE (0x30) ohne Sub-Case** — eine ERROR-Message mit Spannungswert (Variante B)
  - Fallback für unbekannte Codes (inkl. 0x20) → ERROR + hex-dump
- [ ] D.8.3 `hexapod_system.cpp` `read()` umstellen:
  - Generic-Log ersetzen durch `format_error_report` + severity-basierter `RCLCPP_*`-Aufruf
  - Comment im Code zeigt auf D.8-Plan-Doku
- [ ] D.8.4 `CMakeLists.txt`:
  - `error_report_log.cpp` zur Library hinzufügen
  - `ament_add_gtest(test_error_report_log ...)` registrieren
- [ ] D.8.5 Tests `test/test_error_report_log.cpp` neue Suite `ErrorReportLogFormat` (**11 Tests**):
  - 8 spezifizierte Codes: pro Code Severity-Check + Format-Substring-Check
  - 1× unknown Code (z.B. 0xAB) → ERROR + hex-dump
  - 1× SERVO_OVERCURRENT (0x20) → fällt in unknown-Fallback (verifiziert dass 0x20 nicht versehentlich im switch)
  - 1× Smoke-Test: alle 8 Codes + 1 unknown produzieren nicht-leere Strings
- [ ] D.8.6 `colcon build`: grün, keine Warnings (insbesondere keine unused-variable in switch)
- [ ] D.8.7 `colcon test`: alle gtests grün, total mind. **193 tests, 0 errors, 0 failures**
  (11 neue ErrorReportLogFormat-Tests + bestehende 182)
- [ ] D.8.8 Kritische Self-Review-Tabelle in `phase_9_progress.md`
- [ ] D.8.9 Post-Review-Fixes wenn etwas auftaucht
- [ ] D.8.10 `phase_9_stage_d_8_test_commands.md` finalisiert
- [ ] D.8.11 README.md: Status Stufe D komplett ✅ (alle 8 Sub-Stages), Lifecycle-Tabelle final, neuer Abschnitt **„Firmware-Error-Diagnose"** mit Code-Tabelle
- [ ] D.8.12 progress.md: D.8-Sektion mit Bullets + Post-Review-Tabelle + „Was D.8 nicht macht"
- [ ] D.8.13 PHASE.md: nichts ändern (Phase 9 ist noch nicht fertig, Stufen E–J kommen)

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt diesen Plan + die 6 Fragen → Feedback / Freigabe
2. ☐ Bei Bedarf: Plan anpassen
3. ☐ Code: D.8.1–D.8.4 (neues Modul + Integration + CMake)
4. ☐ Tests D.8.5 (~12 Tests)
5. ☐ Build + colcon test grün
6. ☐ Kritischer Self-Review (Pflicht-Schritt CLAUDE.md §4)
7. ☐ Eventuelle Post-Review-Fixes
8. ☐ Doku-Update: progress.md, README.md, test_commands.md
9. ☐ Fertig-Meldung für User-Commit

Mit D.8 ist **Stufe D vollständig**. Danach geht's an die Plugin-
Integration-Stufen E, F, G (URDF-Switch, controllers.real.yaml,
real.launch.py).
