# Stage F2 — Progress (hexapod_hardware: Bit 7 → `/hexapod/shutdown_request`)

> Done-Vertrag aus [`F2_hw_shutdown_publisher_plan.md`](F2_hw_shutdown_publisher_plan.md) §3.
> Test-Anleitung: [`F2_hw_shutdown_publisher_test_commands.md`](F2_hw_shutdown_publisher_test_commands.md).

## Checkliste

- [x] F2.1  servo2040_protocol.hpp: `status_flag::SHUTDOWN_REQUEST` (1u<<7) Mirror
- [x] F2.2  hexapod_system.hpp: `shutdown_request_pub_` + `last_shutdown_request_` + `std_msgs/msg/bool.hpp`
- [x] F2.3  on_configure: latched Publisher `/hexapod/shutdown_request` + Initial `false`
- [x] F2.4  read(): `latest_state()` Bit 7 konsumieren, publish-on-change
- [x] F2.4b write(): gedrosselter GET_STATE-Poll (~5 Hz) — Live-Befund, ohne den bleibt `latest_state()` leer
- [x] F2.5  Unit-Test `DecodeStateShutdownRequestBit` in test_servo2040_protocol.cpp
- [x] F2.6  colcon build + test + lint grün (552 Tests, 0 failures)
- [x] F2.7  Live grün: latched `data: false` + Schalter-Flip false→true→false am Topic verifiziert (User-bestätigt, reliable+transient_local)
- [x] F2.8  Self-Review-Tabelle (keine 🔴-Punkte)

## Self-Review (CLAUDE.md §4)

| Punkt | Status |
|---|---|
| Mirror-Konstante == FW `1u<<7` | OK |
| Publisher vor Loopback-Return → CI/Tests haben Topic | OK |
| Initial `false` bei on_configure | OK |
| `read()` nullopt-safe (`std::optional`), nur `!loopback` | OK |
| publish-on-change + Publisher-Null-Check | OK |
| QoS latched (transient_local, depth 1) — F4 muss matchen | OK |
| `std_msgs/msg/bool.hpp` Include | OK |
| re-on_configure idempotent | OK |
| Build + 552 Tests + Lint grün | OK |

## Offen

- Keine. Stage F2 **fertig** (alle Bullets ✅, Live user-bestätigt). → F3 (gait_node Confirm-Flag).
- **F4-Vertrag (vormerken):** Supervisor muss QoS `reliable` + `transient_local` + depth 1 matchen ([[project_latched_topic_qos_reliable]]).
