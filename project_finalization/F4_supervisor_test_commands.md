# Stage F4 — Test-Anleitung (hexapod_supervisor + OS-Guard)

> Plan: [`F4_supervisor_plan.md`](F4_supervisor_plan.md). Alles dev-testbar — der
> echte OS-Shutdown wird **nie** ausgeführt (3-Schicht-Guard). Workspace: `~/hexapod_ws`.

## Voraussetzungen

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_supervisor
source install/setup.bash
```

---

## F4-U — Unit + Lint (ohne HW)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon test --packages-select hexapod_supervisor
colcon test-result --all | grep hexapod_supervisor
```
**Erwartung:** `0 errors, 0 failures` (15 Tests, 1 skip = copyright). Deckt
`os_shutdown` (G1–G4, dev-host für **beide** Hostname-Schreibweisen) und die
Supervisor-State-Machine (S1–S7) ab. flake8/pep257 grün.

---

## F4-Smoke — Dev (sicher: 3-Schicht-Guard blockt `enjoykin-ubutu` hart)

> Wenn der gait-Stack läuft, triggert der Smoke real `/hexapod_shutdown`
> (Roboter setzt sich hin + Relay aus). Aufgebockt unkritisch; sonst gait-Stack
> vorher stoppen, dann zeigt der Node nur „begin + retry".

Terminal A — Node:
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 run hexapod_supervisor shutdown_supervisor
```
Terminal B — false→true-Flanke feuern (latched QoS!):
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: false}"
sleep 1
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: true}"
```
**Erwartung im Node-Log (Terminal A):**
```
shutdown_supervisor up: enable_os_shutdown=False, pi_hostname=''
shutdown requested -> begin controlled shutdown
/hexapod_shutdown accepted: ...            (falls gait-Stack läuft)
OS shutdown on dev host enjoykin-ubutu is hard-blocked
shutdown finished (reason=complete, performed=False, guard=dev-host)
```
`performed=False` + `guard=dev-host` = der Dev-Rechner fährt **nicht** herunter. ✓

---

---

## F4-L1 — Volltest STANDING → Hinsetzen → complete (⚠️ AUFGEBOCKT, dev)

> **Zweck:** der einzige nicht durch Units/Smoke abgedeckte Realfall. Validiert,
> dass die echte Sequenz REPOSITION (~2 s) + Hinsetzen (~5 s) **innerhalb des
> 8 s-Backstops** mit `shutdown_complete` endet (`reason=complete`, NICHT
> `reason=timeout`). Guard blockt den OS-Shutdown auf `enjoykin-ubutu` → sicher.
>
> **Frischer Stack nötig:** damit `/hexapod/shutdown_complete` auf `false` startet
> (sonst latched-`true` aus einem früheren Shutdown → Race-Fix-Pfad statt echtem
> verzögerten Complete). Also real.launch + gait neu starten, NICHT aus einem
> bereits gelatchten Lauf.

1. **Frischer Stack** (Roboter aufgebockt):
```bash
# Terminal A:
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
# Terminal B:
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false
```
2. **Aufstehen** (aus SAT → STANDING) und warten, bis er steht:
```bash
# Terminal C:
cd ~/hexapod_ws && source install/setup.bash
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
```
3. **Supervisor starten** (jetzt ist complete=false):
```bash
# Terminal D:
cd ~/hexapod_ws && source install/setup.bash
ros2 run hexapod_supervisor shutdown_supervisor
```
4. **Shutdown auslösen** — physischer Schalter ≥3 s auf rot, ODER manuell:
```bash
# Terminal E:
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: false}"
sleep 1
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: true}"
```

**Erwartung im Supervisor-Log (Terminal D):**
```
shutdown requested -> begin controlled shutdown         (Zeit T0 notieren)
/hexapod_shutdown accepted: sitting down then relay off ...
... (Roboter repositioniert + setzt sich ~5-7 s) ...
OS shutdown on dev host enjoykin-ubutu is hard-blocked
shutdown finished (reason=complete, performed=False, guard=dev-host)   (Zeit T1)
```

**Bestehens-Kriterien:**
- `reason=complete` (NICHT `reason=timeout`) → Backstop hat NICHT vorzeitig gefeuert.
- **T1 − T0 messen** (Timestamps in `[...]` der zwei WARN-Zeilen) und mit
  `shutdown_complete_timeout` vergleichen — mind. ~3 s Marge.

**Ergebnis (2026-06):** gemessen **T1−T0 ≈ 7,04 s**, `reason=complete`. 8 s-Backstop
gab nur ~1 s Marge → `shutdown_complete_timeout` Default auf **12 s** erhöht (~5 s
Marge). Sit-Dauer ist trajektorien-getimt (reposition ~2 s + sit ~5 s), also stabil.

(Optional WALKING-Fall: vor dem Trigger kurz `cmd_vel` fahren lassen → der
Supervisor loggt „refused -> retrying", bis du das Fahren stoppst → STANDING →
dann läuft Schritt wie oben.)

---

## Erfolgs-Kriterium F4
F4-U grün + Smoke (`guard=dev-host`) + **F4-L1 `reason=complete` mit T1−T0 < 8 s**
→ Progress F4.1–F4.10 abhaken. Der echte OS-Shutdown wird erst in **F5** (Pi,
`enable_os_shutdown=true` + echter `pi_hostname`) scharf — **nie** auf `enjoykin-ubutu`.
