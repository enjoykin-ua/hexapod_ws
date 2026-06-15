# Stage F5 — Progress (Integration + Pi-Deployment)

> Done-Vertrag aus [`F5_integration_plan.md`](F5_integration_plan.md) §3.
> **F5a** (Dev) implementiert; **F5b** (Pi) als Checkliste vorbereitet, gekoppelt an
> Block D1 (ROS2-auf-Pi).

## F5a — Integration (Dev)

- [x] F5a.1  `config/supervisor.yaml` (enable_os_shutdown=true, pi_hostname leer, Timeouts)
- [x] F5a.2  `supervisor.launch.py` lädt die yaml (verifiziert: `enable=True, pi_hostname=''`)
- [x] F5a.3  `setup.py` installiert `config/*.yaml` (verifiziert installiert)
- [x] F5a.4  `real.launch.py`: `with_supervisor`-Arg + Include supervisor.launch.py
- [x] F5a.5  colcon build + alle Tests grün (Bringup-Loopback-Launch-Test inkl.), Lint grün
- [ ] F5a.6  Live: `real.launch.py` → Supervisor auto-up; Flip → `guard=dev-host`;
            `with_supervisor:=false` → kein Supervisor — **User** (aufgebockt)
- [x] F5a.7  Self-Review (siehe unten)

## F5b — Pi-Deployment (später, vorbereitet, an Block D1 gekoppelt)

- [ ] F5b.1  `pi_hostname` in supervisor.yaml = `hostname` am Pi
- [ ] F5b.2  Shutdown-Privileg (sudoers NOPASSWD `/sbin/shutdown` o. polkit)
- [ ] F5b.3  Branch `leg_changes` + `colcon build` am Pi (ROS2 muss installiert sein)
- [ ] F5b.4  End-to-End physischer Schalter → Pi fährt sauber runter
            (`performed=True, guard=executed`)

## Self-Review (CLAUDE.md §4)

| Punkt | Status |
|---|---|
| yaml-Params greifen (verifiziert) | OK |
| Dev doppelt geschützt trotz `enable=true` (host-mismatch + DEV_HOSTS) | OK |
| Auto-Start in real.launch.py; `with_supervisor:=false` Off-Schalter | OK |
| Bringup-Loopback-Launch-Test grün, Lint grün | OK |
| Dependency hexapod_bringup → hexapod_supervisor | OK |
| Nebenwirkung Schalter-Flip auf Dev = real Hinsetzen+Relay (Guard blockt nur OS) | bewusst |

## Offen

- **F5a.6** Live-Tests durch User (aufgebockt). Danach F5a fertig.
- **F5b** komplett auf den Pi verschoben (braucht ROS2-auf-Pi = Block D1). Plug-and-play
  bis auf `pi_hostname` + Shutdown-Privileg.
