# Phase 3 — Bringup-/Shutdown-Lifecycle — ROS-Seite §4-Plan

> **Ziel:** Die App startet/stoppt den schweren Gait-/Sim-Stack **on demand** und fährt den Pi
> **kontrolliert herunter** — kein Terminal mehr. Löst das Henne-Ei-Problem ([D7]) über eine
> **Always-On-Schicht** (rosbridge + Supervisor + **neuer Launcher-Node**), die ab Boot läuft.
>
> **Seite:** ROS (dieses Dokument) + App (parallel, §5-Brief). **Status: 🟡 Plan.**
> Design-Entscheidungen mit dem User bereits abgestimmt (Bauch+Button-Flow, Launch-per-Config).
> Master: [`00_overview.md`](00_overview.md) · Contract: [`interface_contract.md`](interface_contract.md).

---

## 0. Ziel + Abgrenzung

**Schichtung ([D7]):**
- **Always-On** (systemd ab Boot; in Sim manuell): `rosbridge` (Phase 2) + `shutdown_supervisor`
  (Block F, existiert) + **`bringup_launcher`** (neu, dieser Phase). Diese Schicht steht, bevor
  die App verbindet.
- **On-Demand** (von der App gestartet): der schwere Walk-Stack (Sim: Gazebo+gait / Pi: HW+gait)
  + `joy_to_twist(app)`. rosbridge bleibt oben.

**Kern-Flow (mit dem User abgestimmt):**
```
App „Verbinden" (WebSocket) → App „Hexapod starten" (bringup_start)
  → Stack kommt hoch, Roboter auf dem BAUCH (SAT, auto_standup_on_start:=false)
  → App „Aufstehen" (/hexapod_stand_up) → steht → volle Steuerung (/joy)
  → App „Hinsetzen" (/hexapod_sit_down) → zurück auf den Bauch
  → App „Hexapod stoppen" (bringup_stop) → Stack runter
  → App „Pi ausschalten" (Bestätigung → hexapod_pi_shutdown) → kontrolliert + guarded aus
```

**Bewusst NICHT in Phase 3:** kein Video (Phase 4), kein Status-Overlay/Diagnostics (Phase 5),
kein Recovery (Phase 6). **Kein echter Pi-Poweroff-Test** (Dev-Host ist hart-geguarded → nur
Dry-Run; scharf erst auf dem Pi in der HW-Netz-Stage). Reiner Desktop-Sim-De-Risk.

---

## 1. Logik-Skizze / Vorgehen

### 1a. `bringup_launcher`-Node (in `hexapod_supervisor`, wo Guard + `os_shutdown` schon liegen)
Vier Services (alle `std_srvs/Trigger`, rosbridge-freundlich) + ein latched Status-Topic:

| Service/Topic | Wirkung |
|---|---|
| `/hexapod_bringup_start` | startet den On-Demand-Stack als Subprozess (1b). Idempotent: läuft schon → `success=true`, message „already running". |
| `/hexapod_bringup_stop` | sauberer Stopp des Subprozesses (1b). |
| `/hexapod_bringup_status` | `message` = `running`/`stopped` (+ PID). |
| `/hexapod/bringup_running` (`std_msgs/Bool`, **latched** `transient_local`) | für den App-Connect-/Start-Screen (State ohne Polling). |
| `/hexapod_pi_shutdown` | Pi ausschalten (1d), guarded. |

**Design-Begründung Ort:** `hexapod_supervisor` ist laut [D7] der natürliche Platz — der
`shutdown_supervisor` + `os_shutdown.guarded_shutdown` (dreifacher Dev-Host-Guard) liegen schon
dort, die Shutdown-Logik wird direkt wiederverwendet.

### 1b. Subprozess-Management (der „Realitäts-Haken" aus [D7] — keine Zombies)
- **Start:** `subprocess.Popen(['ros2','launch', pkg, file, *args], start_new_session=True)` →
  eigene **Prozessgruppe** (die `ros2 launch`-Kinder hängen dran). Env wird vom (gesourceten)
  Node geerbt.
- **Stop:** `os.killpg(pgid, SIGINT)` (ros2 launch fährt seine Kinder sauber runter) → warten
  mit Timeout → eskalieren `SIGTERM` → `SIGKILL` → `wait()` (reap). Kein verwaister Prozess.
- **Status:** `Popen.poll()` (None = läuft). Bei unerwartetem Exit → Status-Topic auf `false`,
  loggen.
- **Guards:** nur ein Stack gleichzeitig (zweites `bringup_start` = no-op); `bringup_stop` ohne
  laufenden Stack = no-op-`success`.

### 1c. gait_node: `auto_standup_on_start` (Bauch + Button)
- Neuer Parameter **`auto_standup_on_start`** (Default `true` = **heutiges Verhalten unverändert**).
- Heute triggert der erste vollständige `/joint_states` **unbedingt** den Standup
  ([`gait_node.py:1442-1471`](../../src/hexapod_gait/hexapod_gait/gait_node.py#L1442)).
- Bei `false`: **kein** Auto-Ramp — stattdessen Engine in **SAT** (Bauch/Spawn-Pose, die
  `_spawn_joints` sind genau dort schon erfasst, [[project_b1_sat_rest_pose_is_spawn]]),
  `_ramp_triggered=True` setzen → `_tick` **hält** die Bauch-Pose. Der bestehende
  `/hexapod_stand_up`-Service (verlangt State SAT) rampt dann auf Knopfdruck hoch
  (start-pose-agnostisch, identisch zum Auto-Standup, nur getriggert).
- **Care-Point (Test!):** die Engine muss in SAT die **Spawn-Pose stabil halten**, ohne vorher
  je gestanden zu haben (Boot→SAT→stand_up). Reuse der Sitdown-End-/SAT-Hold-Maschinerie; per
  Unit-Test + Sim absichern.

### 1d. `hexapod_pi_shutdown` (guarded, beide Zustände)
- **Stack läuft:** publiziere `/hexapod/shutdown_request=true` → der bestehende
  `shutdown_supervisor` fährt die getestete Kette (kontrolliertes Hinsetzen via
  `/hexapod_shutdown` → warten auf `shutdown_complete` → guarded OS-Poweroff). **Kein**
  Duplikat der Sit-Logik.
- **Stack idle:** direkter `os_shutdown.guarded_shutdown(...)` (nichts zum Hinsetzen).
- **Beide** laufen durch `guarded_shutdown` → **Dev-Host wird NIE ausgeschaltet** (harter
  Hostname-Block `enjoykin-ubutu` + `enable_os_shutdown` + `pi_hostname`-Match). Auf dem Dev-Host
  = Dry-Run-Log.

### 1e. Ziel-Launch per Config (Sim vs Pi, [siehe Q3])
- Der Launcher liest, **was** er startet, aus einem Config-Param (nicht hartcodiert):
  ```yaml
  bringup_launcher:
    ros__parameters:
      bringup_launch_pkg:  hexapod_bringup
      bringup_launch_file: bringup_ondemand.launch.py
      bringup_launch_args: ["mode:=sim"]         # Pi: ["mode:=real"]
  ```
- Neue **`bringup_ondemand.launch.py`**: komponiert {Walk-Stack (Sim `ramp_walk` flach /
  Pi `real.launch.py`+gait, per `mode`-Arg) + `joy_teleop(joy_source:=app)`}, alles mit
  **`auto_standup_on_start:=false`**. **Ohne** rosbridge (das ist always-on). → EIN Prozessbaum.
- `gait.launch.py` + `ramp_walk.launch.py` bekommen den `auto_standup_on_start`-Arg durchgereicht.

### 1f. Always-On-Launch + systemd
- Neue **`always_on.launch.py`** (hexapod_bringup): `rosbridge` + `shutdown_supervisor` +
  `bringup_launcher`. Das startet die systemd-Unit auf dem Pi.
- systemd-Artefakt aus Phase 2 (`hexapod_rosbridge.service`) → auf **`hexapod_always_on.service`**
  erweitern/umbenennen (startet `always_on.launch.py`). Weiterhin **Dev-Host: nicht scharf.**

**Verworfene Alternativen:**
- *Auto-Start des schweren Stacks beim Boot* — bequemer, aber der Roboter könnte losbewegen,
  bevor man bereit ist. On-Demand + Bauch-Start ist der sichere Default ([D7]).
- *Launcher als eigenes neues Paket* — verworfen; `hexapod_supervisor` hat Guard+os_shutdown schon.
- *App shutdown = direkt `/hexapod_shutdown`* — scheitert, wenn der Stack aus ist (Service
  fehlt → hängt). Deshalb der Launcher-Wrapper, der beide Zustände abdeckt.
- *Zwei Subprozesse (walk + teleop getrennt)* — komplexeres Lifecycle; ein `bringup_ondemand`
  = ein Prozessbaum ist sauberer.

---

## 2. Tests-Liste (mit Begründung) + was NICHT

| Test | Prüft | Warum |
|---|---|---|
| **T3.1** `always_on.launch.py` bringt rosbridge + supervisor + launcher hoch | Always-On-Schicht | Grundlage |
| **T3.2** `bringup_start` (via rosbridge/CLI) → Sim kommt hoch, Roboter **auf dem Bauch** (SAT), fährt NICHT los | On-Demand + Bauch-Start | Sicherheits-Default |
| **T3.3** `/hexapod_stand_up` → steht; `/joy` fährt; `/hexapod_sit_down` → Bauch | Button-Standup reused | Kern-Flow |
| **T3.4** `bringup_stop` → Stack sauber weg, **keine Zombie-/verwaisten Prozesse** (`ps`), rosbridge lebt weiter | Subprozess-Mgmt | der D7-Realitäts-Haken |
| **T3.5** `bringup_status` + `/hexapod/bringup_running` spiegeln running/stopped | Status | Connect-Screen |
| **T3.6** `hexapod_pi_shutdown` bei laufendem Stack → Hinsetzen läuft, dann **Dry-Run** („would shut down") — Desktop bleibt AN | Shutdown-Kette + Guard | Sicherheit |
| **T3.7** `hexapod_pi_shutdown` bei idle Stack → direkter **Dry-Run**, Desktop bleibt AN | Idle-Poweroff-Pfad | Vollständigkeit |
| **T3.8** `auto_standup_on_start:=true` (Default) unverändert = Auto-Standup | Regression | bestehende Bringups nicht brechen |
| **T3.9** Unit-Tests: Launcher-Subprozess-FSM (start/stop/doppelt/Crash), SAT-Hold-at-Spawn | Logik headless | CI, kein Sim nötig |

**Bewusst offen / später:** echter **Pi-Poweroff** (HW-Netz-Stage, nicht Dev-Host); App-UI
(Connect-/Start-Screen, Buttons, Shutdown-Bestätigung = §5, Android-Session); Video/Status/
Recovery (Phasen 4/5/6).

---

## 3. Progress-Checkliste (→ `phase_3_..._progress.md`, Done-Vertrag)

```
Phase 3 (Bringup-/Shutdown-Lifecycle, ROS-Seite):
- [ ] P3.1 gait_node: Param auto_standup_on_start (Default true = unverändert); false -> SAT-Hold-at-Spawn, wartet auf /hexapod_stand_up
- [ ] P3.2 gait.launch.py + ramp_walk.launch.py reichen auto_standup_on_start durch
- [ ] P3.3 bringup_ondemand.launch.py (mode:=sim|real): Walk-Stack + joy_teleop(app), auto_standup_on_start:=false, OHNE rosbridge
- [ ] P3.4 bringup_launcher-Node (hexapod_supervisor): 4 Trigger-Services + latched /hexapod/bringup_running
- [ ] P3.5 Subprozess-Mgmt: Prozessgruppe, SIGINT->TERM->KILL, reap, poll-Status, Single-Instance-Guard (keine Zombies)
- [ ] P3.6 hexapod_pi_shutdown: Stack-laeuft -> shutdown_request (Block-F-Kette); idle -> direkter guarded_shutdown; beides Dev-Host-hart-geguarded
- [ ] P3.7 always_on.launch.py (rosbridge + shutdown_supervisor + bringup_launcher) + launcher.sim.yaml/launcher.real.yaml
- [ ] P3.8 systemd hexapod_always_on.service (Artefakt; Dev NICHT scharf)
- [ ] P3.9 Unit-Tests (Launcher-FSM, SAT-Hold) + colcon test/lint gruen
- [ ] P3.10 Contract: 4 Launcher-Services + /hexapod/bringup_running festgezurrt (§6 -> §2/§3), Version-Bump
- [ ] P3.11 Live-Sim-Test T3.1-T3.8 gruen (test_commands)
- [ ] P3.12 Self-Review + Doku (supervisor README, architecture-Nachzug, §5-App-Brief)
- [ ] P3.13 [Integration, User+App] Connect-/Start-Screen + Start/Stop/Stand/Sit/Shutdown-Buttons gegen die Services
```

---

## 4. Offene Punkte / Risiken (Design bereits abgestimmt)

1. **SAT-Hold-at-Spawn** (1c) ist der einzige heikle Code-Punkt — Engine muss die Bauch-Pose
   halten, ohne je gestanden zu haben. Mit Unit-Test + Sim absichern (T3.9/T3.2).
2. **Env-Vererbung an den Subprozess:** der Launcher-Node muss aus einem **gesourceten**
   Environment laufen (ROS + Workspace-Overlay), damit `ros2 launch` im Kind funktioniert. In
   `always_on.launch.py`/systemd sicherstellen (ExecStart sourcet).
3. **Timing:** `bringup_status` direkt nach `bringup_start` = „starting" (Gazebo braucht Sekunden).
   Der Launcher meldet „running" sobald der Subprozess lebt; „Roboter steht" ist ein separater
   Zustand (kommt in Phase 5 über den Status-Publisher). Für Phase 3 reicht Prozess-lebt.

---

## 5. App-Seiten-Brief (self-contained für die Android-Session)

**Aufgabe Phase 3:** Connect-/Start-Screen + Lifecycle-Buttons. Interface = `interface_contract.md`.
- **Verbinden:** WebSocket zur Always-On-Schicht (`ws://<host>:9090`); Reconnect-tauglich (NF8).
- **Stack-State anzeigen:** verlässliche Primärquelle = **`/hexapod_bringup_status`** (Trigger)
  **pollen** — beim Connect + nach jedem Start/Stop; `message` = `running (pid=…)`/`stopped`.
  **Optionaler Live-Push:** `/hexapod/bringup_running` (latched Bool) subscriben — **funktioniert**
  über rosbridge 2.7.0 (Contract §7.4 geklärt, kein ROS-Change). Deterministisch mit explizitem
  `qos` im subscribe-Frame: `"qos":{"history":"keep_last","depth":1,"durability":"transient_local","reliability":"reliable"}`
  → gelatchter Wert kommt sofort. Primärquelle bleibt trotzdem das Status-Polling (null Timing-/
  Latch-Risiko); der Live-Push ist die Kür.
- **Buttons → Services** (`call_service`, `std_srvs/Trigger` = leere Request):
  „Hexapod starten" → `/hexapod_bringup_start` · „stoppen" → `/hexapod_bringup_stop` ·
  „Aufstehen" → `/hexapod_stand_up` · „Hinsetzen" → `/hexapod_sit_down`.
- **„Pi ausschalten"** — großer Button + **zweistufiger Bestätigungs-Dialog (App-seitig)** →
  `/hexapod_pi_shutdown`. Danach Verbindung erwartbar weg → UI zeigt „heruntergefahren".
- **Bewusst noch NICHT:** Video, Status-Overlay, Recovery, Not-Halt (Phasen 4/5/6).

**Integration (User):** Always-On-Schicht am Desktop → App verbindet → Start/Aufstehen/Fahren/
Hinsetzen/Stop/Shutdown-Buttons gegen die Sim durchklicken; Shutdown = Dry-Run (Desktop bleibt an).

---

## 6. Contract-Touchpoints (§6 → festzurren)
Die vier `[TBD-Phase 3]`-Zeilen in [`interface_contract.md §6`](interface_contract.md) mit Typ
festzurren + nach §2/§3 hochziehen (Version-Bump + Changelog):
- `/hexapod_bringup_start` / `_stop` / `_status` — `std_srvs/Trigger`.
- `/hexapod_pi_shutdown` — `std_srvs/Trigger` (guarded; App zeigt Bestätigung).
- `/hexapod/bringup_running` — `std_msgs/Bool` (latched, `transient_local`).

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_3_..._progress.md` (Done-Vertrag) + `phase_3_..._test_commands.md` (Kontext-Tags) —
  Letzteres vor dem Live-Test final.
- `hexapod_supervisor/README.md`: Launcher-Abschnitt (Services, Subprozess-Mgmt, Config sim/real).
- `architecture.md` (+ `ai_navigation.md`): Launcher-Node + Always-On-Schicht nachtragen.
- Contract v-Bump; App-`CLAUDE.md`-Zeile „Aktuell: Phase 3".
