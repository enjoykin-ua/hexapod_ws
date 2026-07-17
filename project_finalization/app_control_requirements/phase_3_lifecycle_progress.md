# Phase 3 — Bringup-/Shutdown-Lifecycle — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_3_lifecycle_plan.md`](phase_3_lifecycle_plan.md) §3.
> ROS-Seite implementiert + Unit-/Lint-getestet; Live-Sim-Test (P3.11) + App-Integration
> (P3.13) offen (User).

```
Phase 3 (Bringup-/Shutdown-Lifecycle, ROS-Seite):
- [x] P3.1 gait_node: Param auto_standup_on_start (Default true = unverändert); false -> SAT-Hold-at-Spawn, wartet auf /hexapod_stand_up
- [x] P3.2 gait.launch.py + ramp_walk.launch.py reichen auto_standup_on_start durch
- [x] P3.3 bringup_ondemand.launch.py (mode:=sim|real): Walk-Stack + joy_teleop(app), auto_standup_on_start:=false, OHNE rosbridge
- [x] P3.4 bringup_launcher-Node (hexapod_supervisor): 4 Trigger-Services + latched /hexapod/bringup_running
- [x] P3.5 Subprozess-Mgmt: Prozessgruppe, SIGINT->TERM->KILL, reap, poll-Status, Single-Instance-Guard (keine Zombies)
- [x] P3.6 hexapod_pi_shutdown: Stack-laeuft -> shutdown_request (Block-F-Kette); idle -> direkter guarded_shutdown; beides Dev-Host-hart-geguarded
- [x] P3.7 always_on.launch.py (rosbridge + shutdown_supervisor + bringup_launcher) + launcher.sim.yaml/launcher.real.yaml
- [x] P3.8 systemd hexapod_always_on.service (Artefakt; Dev NICHT scharf)
- [x] P3.9 Unit-Tests (Launcher-FSM 9x, SAT-Hold 3x) + colcon test/lint gruen (895 Tests, 0 failures)
- [x] P3.10 Contract: 4 Launcher-Services + /hexapod/bringup_running festgezurrt (§2a/§3), v0.5
- [x] P3.11 Live-Sim-Test T3.1-T3.8 gruen (test_commands) — T3.6-Bug gefunden+gefixt, Runde 2 alle gruen
- [x] P3.12 Self-Review + Doku (supervisor README, architecture-Nachzug, §5-App-Brief)
- [x] P3.13 [Integration, User+App] End-to-End via App verifiziert: Start/Aufstehen/Fahren/Hinsetzen/Stop/Neustart + Pi-Shutdown (Dev-Dry-Run korrekt); Status-Poll (Option A) ok
```

## Stand — ROS-Seite implementiert + getestet, Live-Sim + App offen

**Fertig + verifiziert** (`colcon build` grün, `colcon test` **895 Tests / 0 errors / 0 failures**,
Lint clean):
- `hexapod_gait`: `gait_engine.hold_sat_at` (SAT-Hold-at-Spawn) + `gait_node`-Param
  `auto_standup_on_start` (Boot-Bauch-Branch in `_on_joint_states`).
- Launches: `gait.launch.py`/`ramp_walk.launch.py` (`auto_standup_on_start`-Arg),
  `bringup_ondemand.launch.py` (mode sim/real), `always_on.launch.py`.
- `hexapod_supervisor`: `bringup_launcher`-Node (4 Trigger-Services + latched
  `/hexapod/bringup_running` + Subprozess-Mgmt + guarded Pi-Shutdown), `launcher.sim/real.yaml`.
- systemd-Artefakt `hexapod_always_on.service` (Dev NICHT scharf).
- Tests: `test_boot_belly.py` (3×), `test_bringup_launcher.py` (9×).
- Contract **v0.5** (§2a/§3), architecture + ai_navigation + app-`CLAUDE.md` nachgezogen.
- Nebenbei: `rubicon.launch.py` fehlender Apache-Header ergänzt (vorbestehend, hielt bringup
  rot); Phase-2-`rosbridge`/`app_teleop`-Docstrings „Args:"→„Argumente:" (pep257).

**Offen:** P3.11 Live-Sim-Test (User, [`phase_3_lifecycle_test_commands.md`](phase_3_lifecycle_test_commands.md)) ·
P3.13 App-Integration (Android-Session + User).

### Live-Test-Befund (P3.11, Runde 1) — T3.6-Bug gefunden + gefixt

T3.1–T3.5 + T3.8 ✅ (Bauch-Start, Aufstehen/Fahren/Hinsetzen, sauberer Stop ohne Zombies,
Status-Spiegel, Default-Auto-Standup). **T3.6 deckte einen echten Bug auf:** der Launcher
publishte den Shutdown auf das **latched** `/hexapod/shutdown_request` — der `shutdown_supervisor`
**baselined** aber die *erste* Nachricht auf diesem Topic (Block-F-Schutz gegen einen beim Boot
gedrückten HW-Schalter), sodass der App-Request (= erste Nachricht in der Sim) als Startwert
verschluckt wurde („already True at startup -> baselined, NOT triggering"). **Fix:** neuer
expliziter Supervisor-Service **`/hexapod_request_shutdown`** (Trigger → `_begin_shutdown` direkt,
idempotent), den der Launcher jetzt statt des Topic-Publishes aufruft. HW-Schalter-Pfad
(`_on_request`) bleibt unberührt. +3 Tests (Launcher-no-supervisor + 2× Supervisor-Service).

**Runde 2 (nach Fix) — alle grün:** T3.6 loggt jetzt `begin controlled shutdown` →
`/hexapod_shutdown accepted: already SAT — relay off` → `OS shutdown … hard-blocked`
(`performed=False, guard=dev-host`), Desktop bleibt an. T3.7 idle → `idle poweroff:
performed=False (dev-host)`. **P3.11 komplett — Phase 3 ROS-Seite sim-verifiziert abgeschlossen.**

## Self-Review (P3.12)

| # | Punkt | Status |
|---|---|---|
| 1 | SAT-Hold-at-Spawn: Engine hält Spawn-Pose in SAT, ohne je gestanden zu haben | OK (test_boot_belly 3×) |
| 2 | Launcher-FSM: start/stop/doppelt/Crash/status/shutdown-Routing | OK (test_bringup_launcher 9×) |
| 3 | Subprozess: Prozessgruppe + SIGINT→TERM→KILL + reap → keine Zombies | OK (test) — **echter Prozessbaum in P3.11 live gegenchecken** |
| 4 | Pi-Shutdown dreifach geguarded (DEV_HOSTS-Hard-Block) → Dev nie Poweroff | OK (reuse `os_shutdown`, test) |
| 5 | `auto_standup_on_start` Default true = bestehende Bringups unverändert | OK (Regression 454 gait-Tests grün) |
| 6 | rosbridge bleibt beim `bringup_stop` oben (nur der Subprozess stirbt) | OK (Design) — P3.11 live |
| 7 | colcon build + test (3 Pakete) + Lint grün | OK |
| 8 | mode:=real (Pi) | 🟡 vorbereitet, auf echter HW **nicht** getestet (HW-Netz-Stage) |
| 9 | Live-Sim-Verhalten (Gazebo-Timing, Bauch-Pose visuell, Dry-Run-Log) | 🟢 P3.11 (User) |
| 10 | App-Integration (Screens/Buttons) | 🟢 P3.13 (Android-Session) |

Keine 🔴. Die 🟡/🟢 sind bewusst nach P3.11 (Live-Sim) bzw. HW-Netz-Stage verlagert.

## Design-Entscheidungen (mit Alternativen)

- **`hold_sat_at` reused `_sitdown_rest_joints`/`_compute_sat_angles`** statt neuer SAT-Logik:
  minimaler Eingriff, die SAT-Hold-Maschinerie ist getestet. Verworfen: eine eigene
  „SUSPENDED"-State-Maschine (Doppelung).
- **`auto_standup_on_start` als gait_node-Param** (nicht neuer Node): der Ramp-Trigger sitzt
  schon im Node; ein Boot-Flag ist die kleinste Änderung. Default true hält alles Bestehende.
- **Launcher in `hexapod_supervisor`** (nicht neues Paket): Guard + `os_shutdown` + Block-F-Kette
  liegen dort. Verworfen: eigenes `hexapod_launcher`-Paket (Duplizierung der Guard-Logik).
- **`pi_shutdown` routet bei laufendem Stack über `/hexapod/shutdown_request`** (statt die
  Sit+Poweroff-Logik zu duplizieren) → reused die getestete `shutdown_supervisor`-Kette.
- **Ein `bringup_ondemand`-Prozessbaum** (Walk + Teleop zusammen) statt zwei Subprozesse:
  einfacheres Lifecycle (ein `killpg`).
- **Bauch-Start (`auto_standup_on_start:=false`) als Default im On-Demand-Stack:** sicherer
  On-Demand-Default ([D7]) + passt zum HW-Power-On-Zentrieren ([[project_phase13_initial_pose_presets]]).
