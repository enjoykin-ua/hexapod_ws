# Stage F1 — Progress (servo2040 FW: Schalter → Bit 7)

> Done-Vertrag aus [`F1_fw_switch_bit_plan.md`](F1_fw_switch_bit_plan.md) §3.
> FW-Code im Repo `~/hexapod_servo_driver` (separat committet). Bench-Tests:
> [`F1_fw_switch_bit_test_commands.md`](F1_fw_switch_bit_test_commands.md).

## Checkliste

- [x] F1.1  config.hpp: `SHUTDOWN_HOLD_MS=3000` + `status::SHUTDOWN_REQUEST` (1u<<7)
- [x] F1.2  main.cpp: `switch_armed` + `switch_open_since` + `shutdown_request` Globals
- [x] F1.3  main.cpp: `poll_switch()` um Arm + 3-s-Halten erweitert
- [x] F1.4  main.cpp: `handle_get_state()` leitet Bit 7 aus `shutdown_request` ab
- [x] F1.5  LED-Rohpegel (grün/rot) unverändert (Regression — Code unangetastet)
- [x] F1.6  Build grün (`make`, keine Warnung)
- [x] F1.7  Bench F1-T1..T5 grün (via `flash_and_verify.py` + `log_state.py`) — User-bestätigt
- [x] F1.8  PROTOCOL.md: Bit 7 `SHUTDOWN_REQUEST` dokumentiert (+ Bits 5/6 nachgezogen)
- [x] F1.9  Self-Review-Tabelle (keine 🔴-Punkte)

## Self-Review (CLAUDE.md §4)

| Punkt | Status |
|---|---|
| Arm-Guard: Boot-OPEN setzt kein Bit (armed=false gated 3-s-Check) | OK |
| 3-s-Halten als Per-Tick-Check, unabhängig von Debounce-Flanke | OK |
| 1-Tick-Bounce während Halten resettet `switch_open_since` nicht | OK |
| Schließen storniert Request (track-level) | OK |
| Bit 7 am Sendezeitpunkt abgeleitet → RESET/Trip stört nicht | OK |
| `shutdown_request` überlebt RESET (physischer Input, korrekt) | OK |
| LED-Rohpegel unverändert | OK |
| `switch_open_since` zero-init nie live verglichen (armed-gate) | OK |
| `poll_switch` läuft standalone + im Tick | OK |
| Build grün, keine Warnung | OK |

## Offen

- Keine. Stage F1 **fertig** (alle Bullets ✅). → F2 (HW Bool-Publisher).
