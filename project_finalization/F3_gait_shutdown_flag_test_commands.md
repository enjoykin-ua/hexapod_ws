# Stage F3 — Test-Anleitung (gait_node: `/hexapod/shutdown_complete`)

> Plan: [`F3_gait_shutdown_flag_plan.md`](F3_gait_shutdown_flag_plan.md). Unit ohne HW;
> Live braucht den realen Stack. Workspace: `~/hexapod_ws`. User führt aus.

## Voraussetzungen

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
```

---

## F3-U1..U4 — Unit + Lint (ohne HW)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon test --packages-select hexapod_gait
colcon test-result --all | grep hexapod_gait
```
**Erwartung:** `0 errors, 0 failures`. `test_sitdown_node.py` enthält die neuen
F3-Tests (Init-`false`, `_on_shutdown` aus SAT → publish `true`, aus STANDING kein
verfrühtes `true`). flake8/pep257 grün.

---

## F3-L1 — Live: latched Init `false` (Board nötig, NICHT-destruktiv)

Terminal A — Hardware + gait_node (aufgebockt):
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```
Terminal B — gait_node (HW: use_sim_time:=false, sonst blockt der Timer):
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false
```
Terminal C — Topic mitlesen (reliable + transient_local!):
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 topic echo /hexapod/shutdown_complete \
  --qos-reliability reliable --qos-durability transient_local
```
**Erwartung:** `data: false` (latched Init). Roboter bewegt sich nicht.

## F3-L2 — Live: Flip auf `true` bei Shutdown (⚠️ AUFGEBOCKT, destruktiv)

> Achtung: `/hexapod_shutdown` **setzt den Roboter hin und schaltet das Relay aus**.
> Nur **aufgebockt** ausführen. Roboter vorher in **STANDING** oder **SAT** bringen.

Terminal C lässt den Echo aus F3-L1 laufen. Terminal D:
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 service call /hexapod_shutdown std_srvs/srv/Trigger {}
```
**Erwartung:** Roboter setzt sich hin → bei SAT Relay-Aus → Terminal C zeigt
**`data: true`**. (Recovery: Relay-On/Reboot, da `_shutdown_latched` terminal ist.)

---

## Erfolgs-Kriterium F3
F3-U1..U4 grün **und** F3-L1 (`false`) + F3-L2 (`true`) → Progress F3.1–F3.7
abhaken, dann Self-Review (Plan §3, F3.8). Danach F4 (Supervisor + Guard).
