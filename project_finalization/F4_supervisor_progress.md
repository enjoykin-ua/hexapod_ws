# Stage F4 — Progress (hexapod_supervisor + OS-Guard)

> Done-Vertrag aus [`F4_supervisor_plan.md`](F4_supervisor_plan.md) §3.
> Neues Paket `src/hexapod_supervisor`. Test-Anleitung:
> [`F4_supervisor_test_commands.md`](F4_supervisor_test_commands.md).

## Checkliste

- [x] F4.1  Paket hexapod_supervisor (package.xml/setup.py/cfg/resource/LICENSE/launch)
- [x] F4.2  os_shutdown.py: guarded_shutdown (3-Schicht-Guard, dev-host `DEV_HOSTS` hart)
- [x] F4.3  shutdown_supervisor.py: Params + Subs + Clients + State-Machine
- [x] F4.4  Arm/Flanke (Baseline, kein Startup-True-Trigger)
- [x] F4.5  Retry /hexapod_shutdown (K2) + Backstop-Timeout + Fallback-Relay-Off
- [x] F4.6  guarded OS-Shutdown am Ende (Dry-Run auf Dev) + Complete-Race-Fix
- [x] F4.7  Tests F4-G1..G4 + F4-S1..S7 (15 Tests, parametrisierter Dev-Host-Block)
- [x] F4.8  colcon build + test + flake8/pep257 grün (570 Tests gesamt, 0 failures)
- [x] F4.9  Dev-Smoke: Node läuft, Flip → ganze Kette → `guard=dev-host`, sauberer Exit
- [x] F4.10 Self-Review (siehe unten)
- [x] F4.11 Volltest STANDING (aufgebockt, dev): gemessen T1−T0 ≈ **7,04 s**, `reason=complete`.
            8 s-Backstop zu knapp (~1 s) → `shutdown_complete_timeout` Default auf **12 s** erhöht (~5 s Marge).

## Self-Review (CLAUDE.md §4) — inkl. Smoke-Funde

| Punkt | Status |
|---|---|
| 3-Schicht-Guard, Reihenfolge dev-host → enable → hostname | OK |
| 🔴→fix **Hostname-Typo**: echt `enjoykin-ubutu`, Smoke zeigte Single-Spelling verfehlt → `DEV_HOSTS` blockt beide | gefixt |
| 🔴→fix **Complete-Race**: latched `complete` kann vor Service-Antwort kommen → bei Accept `_complete` prüfen | gefixt |
| 🔴→fix **ExternalShutdownException** bei SIGTERM → in main() gefangen | gefixt |
| Arm/Baseline: Startup-True triggert nicht; nur echte 0→1-Flanke | OK |
| Storno (request→false) mitten im Shutdown wird ignoriert (Entscheidung latcht) | OK |
| Retry endlos bei WALKING (K2-strikt), kein Roboter-Drop | OK |
| Backstop force-relay-off als Notnetz | OK |
| os_shutdown isoliert, `run`/`hostname` injizierbar, nie real auf Dev ausgeführt | OK |
| 15 Pkt-Tests + Lint grün, Dev-Smoke sauber | OK |

## Offen

- **F4 fertig** (Code + 15 Tests + Dev-Smoke + STANDING-Volltest F4-L1). Echter
  OS-Shutdown nie auf Dev ausgeführt. F4-L1 fand zu-knappe Backstop-Marge → auf 12 s gefixt.
- **F5:** Bringup-Einhängung, Pi-Deployment (polkit/sudoers, echter `pi_hostname` +
  `enable_os_shutdown=true` ganz spät), End-to-End Schalter→OS-Halt am Pi.
- **⚠️ Vormerken F5:** `pi_hostname` = echter **Pi**-Hostname (NICHT `enjoykin-ubutu`).
