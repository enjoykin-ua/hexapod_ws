# Phase 9 — Stufe D.6 — Plan

> **Status:** **RETROSPEKTIV erstellt** — eigentlich gehört dieser Plan VOR
> die Implementation (CLAUDE.md §4-Update). Code + Tests sind bereits
> geschrieben (Build grün, Tests noch nicht gefahren). User-Review der
> Plan-Doku entscheidet, ob die Implementation so bleibt oder angepasst wird.
>
> **Parent-Plan:** [`phase_9_stage_d_plan.md §D.6`](phase_9_stage_d_plan.md)
> — Architektur-Skizze von write/read, joint→pin-Mapping, Echo-State.
>
> **Test-Anleitung:** [`phase_9_stage_d_6_test_commands.md`](phase_9_stage_d_6_test_commands.md)
> (wird nach Implementations-Freigabe finalisiert).

---

## Ziel der Sub-Stage

Die zwei `read()` / `write()`-Methoden, die `ros2_control` bei jedem
50-Hz-Tick aufruft, werden voll implementiert. Ersetzt die Stubs aus
Stufe A. Nach D.6 ist das Plugin in Loopback-Mode end-to-end testbar
(Trajectory rein → Pulse-Konversion → Echo zurück) und in non-loopback
sendet es bei jedem Tick einen `SET_TARGETS`-Frame.

Was D.6 fertig stellt:
- Übersetzung **Joint-Position (rad)** ↔ **Pulse-µs** via `Calibration`
- **Joint-Index-Mapping**: URDF-Slot `i` → Servo-Pin `output_idx` (in Aktion,
  in D.3 wurde nur die Tabelle gebaut)
- **NaN-Sanity-Check** im write-Pfad (keine NaN auf die Wire)
- **Pulse-Overflow-Clamp** auf int16-Range (UB-Vermeidung beim cast)
- **ERROR_REPORT-Drainage** im read-Pfad (Reader-Queue leeren, ein-Log
  pro Eintrag — Format-Detail kommt in D.8)
- **Reader-died()-Check** in beiden Hooks → `return_type::ERROR` →
  `controller_manager` deaktiviert den Plugin

Was D.6 **nicht** macht:
- Kein Reconnect — D.7 (D.6-Verhalten bei mid-run-Disconnect: write/read
  returnt ERROR, Plugin geht in inactive)
- Keine ERROR_REPORT-Übersetzungs-Tabelle (Code → human-readable) — D.8
- Keine `GET_STATE`-Polling (Architektur-Entscheidung B in Plan-Doku, kein
  STATE-Konsument in Phase 9)

---

## `write()`-Logik (Pseudocode)

```cpp
return_type write(time, period) {
    // Defensive: Reader hat schon disconnect erkannt → keinen Wire-Output
    if (!loopback_mode_ && reader_.died()) {
        RCLCPP_ERROR_ONCE("write(): reader thread died");
        return ERROR;
    }

    // Pro URDF-Slot: rad → pulse_us, mit NaN-Sanity und int16-Clamp
    for (i = 0; i < info_.joints.size(); ++i) {
        output_idx = joint_to_output_idx_[i];
        rad = hw_command_positions_[i];

        if (std::isnan(rad)) {
            RCLCPP_WARN("NaN for joint '%s' — reusing last good pulse");
            continue;   // last_command_pulse_us_[output_idx] bleibt
        }

        pulse_d = calibration_.radians_to_pulse_us(output_idx, rad);
        pulse_clamped = std::clamp(pulse_d, INT16_MIN, INT16_MAX);
        last_command_pulse_us_[output_idx] = static_cast<int16_t>(round(pulse_clamped));
    }

    if (loopback_mode_) return OK;

    auto frame = encode_set_targets(seq_.fetch_add(1), last_command_pulse_us_);
    try { serial_port_.write_all(frame.data(), frame.size()); }
    catch (const std::exception & e) {
        RCLCPP_ERROR("write_all failed: %s", e.what());
        return ERROR;
    }
    return OK;
}
```

### Begründung der Design-Entscheidungen

**NaN-Handling: keep-last-good + WARN (kein THROTTLE).**
NaN aus dem Trajectory-Stack ist ein **echter Bug** im Upstream (z.B.
Spline-Numerik-Glitch). Wir wollen das laut sehen, nicht throttlen.
`RCLCPP_WARN_THROTTLE` braucht einen Clock — den `*Clock::make_shared()`-
Workaround haben wir in D.2 als UAF identifiziert (Temporary stirbt). Bis
wir den korrekten Clock aus `SystemInterface::get_clock()` ans Logging
binden (D.8 oder Phase 10), bleibt es bei plain WARN. Spam-Vermeidung:
auf echter HW kommen NaNs nicht im Normalbetrieb vor; in CI tracken wir
über Tests.

**Int16-Clamp vor static_cast<int16_t>.**
`Calibration::radians_to_pulse_us` extrapoliert linear über die
Joint-Limits hinaus (kein Hard-Clamp dort — by design, um Limit-Verletzungen
sichtbar zu machen). Bei rad=100 (z.B. korrupter Controller-State) ergibt
das pulse ≈ 1.3e6 µs, weit jenseits int16. Ein direkter
`static_cast<int16_t>` auf so einen Wert ist **implementation-defined
behaviour** (C++17) bzw. **UB** in extremen Fällen. `std::clamp` zwingt
auf int16-Range → cast wohldefiniert. Firmware clampt nochmal auf
pulse_min/pulse_max (Phase-7 Stufe C.1) — Defense in Depth.

**Wire-I/O nur in non-loopback, Konversion immer.**
Loopback skipt `encode_set_targets + write_all`, aber **macht die
Pulse-Konversion trotzdem** — damit read() im selben Tick den
Echo-State sinnvoll spiegeln kann. Sonst würde Loopback nur
`hw_state_positions_ = 0` produzieren statt eines korrekten Roundtrips.

**Reader-died-Check am Anfang, nicht später.**
Auch wenn der Konversions-Code dann nicht „durchlaufen" wird, wollen wir
einen disconnect-state nicht durch noch mehr Code laufen lassen.
`RCLCPP_ERROR_ONCE` macht den Log nicht spammy beim wiederholten Tick.

**seq_ via `fetch_add(1)`.**
Bereits in D.5 als atomic eingeführt; write() inkrementiert pro Frame
genau einmal. Wraparound bei 256 ist harmless (Firmware stateless wrt SEQ).

---

## `read()`-Logik (Pseudocode)

```cpp
return_type read(time, period) {
    // Echo via Pulse-Konversion: pulse_us → rad
    for (i = 0; i < info_.joints.size(); ++i) {
        output_idx = joint_to_output_idx_[i];
        hw_state_positions_[i] = calibration_.pulse_us_to_radians(
            output_idx, last_command_pulse_us_[output_idx]);
    }

    if (loopback_mode_) return OK;

    // ERROR_REPORTs vom Reader-Thread drainen + loggen
    for (const auto & er : reader_.drain_error_queue()) {
        RCLCPP_ERROR("Firmware error: code=0x%02X servo=%u aux=%d (D.8: detail)",
                     er.error_code, er.servo_idx, er.aux);
    }

    // Reader gestorben?
    if (reader_.died()) {
        RCLCPP_ERROR_ONCE("Reader died — see earlier FATAL log");
        return ERROR;
    }
    return OK;
}
```

### Begründung

**Echo geht durch beide Konversionen (rad → pulse → rad).**
Sub-Millisekunde-Rundungsverlust pro Joint (1 µs ≈ 1.6 mrad bei
1000 µs/rad). Test `LoopbackRoundtripsCommandThroughCalibration`
verifiziert ≤ 2 mrad Toleranz.

**Drain VOR died-Check.**
Wenn der Reader-Thread mit `died_=true` aussteigt, könnten in der
error_queue noch ungelesene Reports stehen (z.B. der WATCHDOG-Trip,
der den Disconnect ausgelöst hat). Erst alles lesen, **dann** signalisieren.

**Plain `RCLCPP_ERROR` ohne THROTTLE für Error-Reports.**
Auf echter HW selten (Watchdog, Overcurrent — Ereignisse, nicht Stream).
Spam-Risiko niedrig, Diagnostik-Wert hoch.

**`RCLCPP_ERROR_ONCE` für died-Meldung.**
Schon einmal beim ersten ERROR-Return gemeldet. ros2_control wird das
Plugin daraufhin in `inactive` bringen — kein zweiter read()-Aufruf
mehr (oder erst nach manuellem Re-Activate, da kommt erneut der Log).

---

## Tests (Suite `HexapodSystemWriteRead`, ~7 Tests)

| # | Test | Was wird geprüft |
|---|---|---|
| 1 | `LoopbackRoundtripsCommandThroughCalibration` | 7 verschiedene rad-Werte (-1.5 .. +1.5) durch alle 18 Joints; nach write → read muss `state ≈ command` (Toleranz 2 mrad für Pulse-Rundung) |
| 2 | `LoopbackZeroRadStaysAtPulseZero` | Anchor: rad=0 → pulse=1500 → rad=0 **exakt** (keine Rundung weil 1500 ganzzahlig). Sanity gegen Pulse-Konversions-Bugs |
| 3 | `LoopbackNanCommandIsLoggedAndIgnored` | Slot 5 auf 0.5, dann NaN, dann lesen → muss noch ≈ 0.5 sein (NICHT NaN). Andere Slots werden aktualisiert |
| 4 | `LoopbackClampsAbsurdRadInsteadOfUB` | rad=100 / rad=-100 → write throw-frei, state ist `finite` (= clamp griff, kein UB) |
| 5 | `PtyWriteSendsSetTargetsFrameWithNeutralPulses` | non-loopback: 18× rad=0 → genau 1 SET_TARGETS-Frame auf master mit 18× 0xDC 0x05 (= 1500 µs LE) |
| 6 | `PtyReadDrainsFirmwareErrorReports` | Inject ERROR_REPORT (WATCHDOG_TRIPPED) auf master; nach 100 ms read() → OK (Drain läuft, kein Crash) |
| 7 | `PtyReadReturnsErrorWhenReaderDies` | master close → reader detektiert POLLHUP → died → read() → ERROR |
| 8 | `PtyWriteReturnsErrorWhenReaderDies` | gleiche Disconnect-Situation für write() — bricht VOR write_all ab mit ERROR |

(Plus die schon vorhandenen 23 Tests in Suiten `HexapodSystemInit`,
`HexapodSystemConfigure`, `HexapodSystemActivate` — bleiben unverändert.)

### Was die Tests NICHT prüfen (bewusst weggelassen)

- **Joint-Permutations-Mapping im write-Pfad.** D.3 hat das schon
  über `export_command_interfaces`-Reihenfolge verifiziert. D.6 nutzt
  `joint_to_output_idx_` aber zeigt das Mapping nur indirekt (Roundtrip-
  Test mit kanonischer Reihenfolge ist ausreichend).
- **Genaue Pulse-Werte für rad ≠ 0/anchors.** Wäre Re-Implementierung der
  piecewise-linearen Konversion im Test → kein zusätzlicher Wert (siehe
  D.5 PtyActivateSendsBootSequenceInOrder, das nur pulse_zero-Anker prüft).
- **ERROR_REPORT-Log-Content-Verifikation.** Verschoben auf D.8.
- **Performance-Tests (50 Hz Echtzeit-Verhalten).** Wäre Phase-11-Material;
  Stufe D ist Funktional, nicht Performance.

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Das ist der **Done-Kriterium-Vertrag**. Sub-Stage D.6 ist fertig, wenn
alle Bullets unten `[x]` sind — keine Retroaktiv-Anpassung erlaubt.

- [ ] D.6.1 `<cmath>` + `<climits>` Includes in `src/hexapod_system.cpp` ergänzt
- [ ] D.6.2 `write()` implementiert mit:
  1. `reader_.died()`-Defensive-Check (non-loopback) → ERROR_ONCE + return ERROR
  2. Pro Joint i: `joint_to_output_idx_[i]` lookup, NaN-Check (WARN + keep last good), `radians_to_pulse_us`, `std::clamp` auf int16-Range, `last_command_pulse_us_[output_idx]` Update
  3. In loopback: nur Konversion, kein Wire-I/O — return OK
  4. Non-loopback: `encode_set_targets` + `serial_port_.write_all`, catch → ERROR
- [ ] D.6.3 `read()` implementiert mit:
  1. Pro Joint i: Echo via `pulse_us_to_radians(output_idx, last_command_pulse_us_[output_idx])` → `hw_state_positions_[i]`
  2. Non-loopback: `reader_.drain_error_queue()`, pro Eintrag RCLCPP_ERROR mit Code/Servo/Aux (Format-Detail D.8)
  3. `reader_.died()`-Check → ERROR_ONCE + return ERROR
- [ ] D.6.4 Tests `test_hexapod_system.cpp` neue Suite `HexapodSystemWriteRead` (8 Tests):
  - `LoopbackRoundtripsCommandThroughCalibration` (7 rad-Werte ±1.5, alle 18 Slots, Toleranz 2 mrad)
  - `LoopbackZeroRadStaysAtPulseZero` (exakte Identität bei 0)
  - `LoopbackNanCommandIsLoggedAndIgnored` (NaN bei Slot 5 → keep 0.5, andere Slots tracken 0.1)
  - `LoopbackClampsAbsurdRadInsteadOfUB` (rad=±100 → finite state, no UB)
  - `PtyWriteSendsSetTargetsFrameWithNeutralPulses` (rad=0 → SET_TARGETS mit 18× 1500 µs)
  - `PtyReadDrainsFirmwareErrorReports` (ERROR_REPORT-Frame inject → read() OK + Drain läuft)
  - `PtyReadReturnsErrorWhenReaderDies` (master close → POLLHUP → died → read() ERROR)
  - `PtyWriteReturnsErrorWhenReaderDies` (gleiches für write() → ERROR ohne Exception)
- [ ] D.6.5 Test-Helper im anonymous namespace: `read_handle()` (via `get_optional().value()` für jazzy-4.44-API-Drift), `write_handle()` (via `set_value()` mit `[[nodiscard]]`-ASSERT)
- [ ] D.6.6 `colcon build`: grün, keine Warnings (insb. keine `get_value()`-Deprecation-Warnings)
- [ ] D.6.7 `colcon test`: alle gtests grün, `test_hexapod_system` jetzt 31 Tests; total mind. **176 tests, 0 errors, 0 failures**
- [ ] D.6.8 Self-Review-Tabelle in `phase_9_progress.md` mit Status-Spalte (`OK` / `🔴 fixen` / `🟡 vormerken` / `🟢 später`)
- [ ] D.6.9 Eventuelle Post-Review-Fixes mit erklärenden Code-Kommentaren
- [ ] D.6.10 `phase_9_stage_d_6_test_commands.md` finalisiert mit Test-Filter-Befehlen + Erwartungen + Fehler-Diagnose-Tabelle
- [ ] D.6.11 README.md: Status auf D.6/8, Lifecycle-Tabelle `read` / `write` von 🟡 auf ✅
- [ ] D.6.12 progress.md: D.6-Sektion mit obigen Bullets + Notizen + Post-Review-Tabelle + „Was Stufe D.6 explizit nicht macht"

---

## Was offen ist und User-Feedback braucht

Bitte einmal kurz checken bevor ich Tests laufe + Self-Review + Doku finalisiere:

1. **Plain `RCLCPP_WARN` für NaN, kein THROTTLE** — OK so oder lieber
   selbst-gemachte Counter-basierte Throttle (z.B. „log alle 50 Ticks =
   1 s")? Aktuell hat Phase 9 generell keinen Clock-Zugriff vom Plugin,
   D.8 könnte das geradeziehen.
2. **`Reader-died()`-Check vor Konversion im write()** — oder lieber
   nach? Aktuell: vor (kein Aufwand wenn FD eh tot). Alternative wäre:
   immer last_command_pulse_us_ updaten (für Lifecycle-Konsistenz beim
   Re-Activate), aber nur write_all skippen.
3. **Test-Toleranz 2 mrad im Roundtrip** — passt das, oder eher konservativ?
   Theoretisch sind es ~1.6 mrad bei pulse_zero. Größere Werte zeigen
   einen Konversions-Bug. 2 mrad lässt Headroom für `int16_t round()`.
4. **`RCLCPP_ERROR_ONCE` für died-Meldung** — vs. plain `RCLCPP_ERROR`
   (jeder Tick) vs. selbst-gemachter „nur beim Transition false→true"-Trigger?
   `_ONCE` ist callsite-global, also über alle Instanzen — bei mehreren
   Plugin-Instanzen in einer Pi-Session würde nur der erste loggen. Für
   Single-Plugin-Setup ist das egal.
5. **Implementations-Größe** — write() ist ~50 Zeilen, read() ist ~35 Zeilen.
   Lesbar? Oder aufteilen in private Helper (z.B. `convert_commands_to_pulses()`)?

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt diesen Plan → Feedback
2. ☐ Bei Bedarf: Code/Tests anpassen
3. ☐ Tests laufen: `colcon test --packages-select hexapod_hardware`
4. ☐ Kritischer Self-Review (Pflicht-Schritt nach CLAUDE.md §4)
5. ☐ Post-Review-Fixes wenn was auftaucht
6. ☐ Doku-Update: progress.md (D.6-Bullets + Post-Review-Tabelle),
      README.md (Status auf D.6/8, Lifecycle-Tabelle write/read = ✅)
7. ☐ Test-Anleitung `phase_9_stage_d_6_test_commands.md` finalisieren
8. ☐ Fertig-Meldung für User-Commit
