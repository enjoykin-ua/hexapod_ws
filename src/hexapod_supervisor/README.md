# hexapod_supervisor

Systemsteuerung/Lifecycle (Block F + Block I). Zwei Nodes:

## `shutdown_supervisor` (Block F)

Kontrollierter Shutdown: abonniert `/hexapod/shutdown_request` (HW-Schalter, latched), ruft bei
steigender Flanke `/hexapod_shutdown` (retry bis STANDING/SAT), wartet auf
`/hexapod/shutdown_complete` und fährt den Pi **guarded** herunter. Config: `config/supervisor.yaml`.
Launch: `ros2 launch hexapod_supervisor supervisor.launch.py`.

## `bringup_launcher` (Block I Phase 3)

**On-Demand-Lifecycle** für die App. Teil der Always-On-Schicht (neben rosbridge +
`shutdown_supervisor`). Startet/stoppt den schweren Gait-/Sim-/HW-Stack als **Subprozess**
(`ros2 launch …`) und bietet einen guarded Pi-Shutdown.

| Service (`std_srvs/Trigger`) | Wirkung |
|---|---|
| `/hexapod_bringup_start` | Stack starten (idempotent). Ziel-Launch aus Config (`bringup_launch_*`): Sim = `bringup_ondemand.launch.py mode:=sim`, Pi = `mode:=real`. Roboter kommt **auf dem Bauch** hoch (`auto_standup_on_start:=false`). |
| `/hexapod_bringup_stop` | Stack sauber stoppen: `SIGINT→SIGTERM→SIGKILL` an die **Prozessgruppe**, reap → **keine Zombies**. rosbridge lebt weiter. |
| `/hexapod_bringup_status` | `message` = `running (pid=…)` / `stopped`. |
| `/hexapod_pi_shutdown` | Pi ausschalten. Stack läuft → `/hexapod/shutdown_request=true` (Block-F-Kette: Hinsetzen + guarded Poweroff); idle → direkter `guarded_shutdown`. **Dev-Host = nur Dry-Run.** |

Topic: `/hexapod/bringup_running` (`std_msgs/Bool`, latched `transient_local`) — Stack-State für
den App-Connect-Screen.

**Configs:** `config/launcher.sim.yaml` (Desktop) / `config/launcher.real.yaml` (Pi). Der
Shutdown-Guard (`enable_os_shutdown`/`pi_hostname`) ist identisch zu `supervisor.yaml` — auf dem
Pi in **beiden** die `hostname`-Ausgabe als `pi_hostname` eintragen.

**Sicherheit:** Der Pi-Poweroff läuft ausschließlich über `os_shutdown.guarded_shutdown` mit
dreifachem Guard (harter `DEV_HOSTS`-Block + `enable_os_shutdown` + `pi_hostname`-Match) → auf
dem Dev-Host feuert **nie** ein echter Shutdown (nur Dry-Run-Log).

## Always-On-Schicht starten

```bash
ros2 launch hexapod_bringup always_on.launch.py            # mode:=sim (Desktop, manuell)
ros2 launch hexapod_bringup always_on.launch.py mode:=real # Pi (systemd: hexapod_always_on.service)
```

Kontext + Contract (die App-Naht): `project_finalization/app_control_requirements/interface_contract.md`
(§2a Launcher-Services). Phasen-Doku: `.../phase_3_lifecycle_*`.
