# Stage F3 — Progress (gait_node: `/hexapod/shutdown_complete`)

> Done-Vertrag aus [`F3_gait_shutdown_flag_plan.md`](F3_gait_shutdown_flag_plan.md) §3.
> Test-Anleitung: [`F3_gait_shutdown_flag_test_commands.md`](F3_gait_shutdown_flag_test_commands.md).

## Checkliste

- [x] F3.1  Importe: `Bool` + `QoSProfile`/`DurabilityPolicy`/`ReliabilityPolicy`
- [x] F3.2  __init__: latched Publisher `/hexapod/shutdown_complete` + Init `false`
- [x] F3.3  `_publish_shutdown_complete(done)` Helper
- [x] F3.4  `_do_relay_off_and_latch`: nach Latch `_publish_shutdown_complete(True)`
- [x] F3.5  Unit-Tests F3-U1..U3 in test_sitdown_node.py (4 neue Tests)
- [x] F3.6  colcon test + flake8 + pep257 grün (556 Tests, 0 failures)
- [ ] F3.7  Live F3-L1 (`false`) + F3-L2 (`true` bei Shutdown, aufgebockt) — **User**
- [x] F3.8  Self-Review-Tabelle (keine 🔴-Punkte)

## Self-Review (CLAUDE.md §4)

| Punkt | Status |
|---|---|
| Publisher latched (transient_local + reliable + depth 1) = F2-Vertrag | OK |
| Init `false` in `__init__` nach Publisher-Erzeugung | OK |
| Helper publisht `Bool(data)` | OK |
| `true` nach `_shutdown_latched=True` | OK |
| Semantik false→true einmalig, kein Reset | OK |
| `_do_relay_off_and_latch` feuert nur einmal (guard) | OK |
| flake8/pep257 + Build + 556 Tests grün | OK |

## Offen

- **F3.7 Live-Tests** durch User (Board, aufgebockt). Danach Stage F3 fertig → F4.
