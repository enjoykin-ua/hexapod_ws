# Phase 3 — Test-Befehle: Bringup-/Shutdown-Lifecycle (Sim)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:**
> **▶ ROS (hexapod_ws)** = Desktop-Terminal · **▶ App** = *echte App = Integration P3.13*.
> Hier simulieren `ros2 service call`-Befehle, was die App über rosbridge macht.
>
> **Ziel:** Always-On-Schicht hoch, Stack **on demand** starten (Roboter kommt **auf dem
> Bauch** hoch), per Button aufstehen/fahren/hinsetzen, sauber stoppen (keine Zombies),
> guarded Pi-Shutdown (Dev-Host = **nur Dry-Run**, Desktop bleibt an).
> Plan: [`phase_3_lifecycle_plan.md`](phase_3_lifecycle_plan.md).

---

## Vorbereitung

**▶ ROS:**
```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_gait hexapod_bringup hexapod_supervisor
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

## Setup: Always-On-Schicht (Terminal 1, ▶ ROS)

```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py        # mode:=sim (Default)
```
> Startet rosbridge + shutdown_supervisor + bringup_launcher. **Kein** Gazebo (das kommt on demand).

**Terminal 2 (▶ ROS)** = Prüf-/Steuer-Befehle (jeweils zuerst sourcen).

---

## T3.1 — Always-On-Schicht oben

```bash
ros2 node list | grep -E "rosbridge_websocket|rosapi|shutdown_supervisor|bringup_launcher"
ros2 service list | grep -E "hexapod_bringup_(start|stop|status)|hexapod_pi_shutdown"
```
**✅ Erwartung:** alle vier Nodes gelistet; die vier Launcher-Services da.

## T3.2 — Stack starten → Roboter kommt AUF DEM BAUCH hoch

```bash
ros2 service call /hexapod_bringup_start std_srvs/srv/Trigger {}
```
→ Gazebo startet (dauert ~15 s). **Beobachten:** Roboter spawnt, sinkt auf den Bauch (SAT) und
**bleibt liegen** — er steht **nicht** automatisch auf und läuft **nicht** los.

```bash
ros2 topic echo /hexapod/bringup_running --qos-reliability reliable \
  --qos-durability transient_local --once          # data: true
ros2 service call /hexapod_bringup_status std_srvs/srv/Trigger {}   # message: running (pid=…)
```
**✅ Erwartung:** Roboter auf dem Bauch, `bringup_running=true`, Status `running`.

## T3.3 — Aufstehen (Button) → fahren → Hinsetzen

```bash
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}         # SAT → steht auf
# fahren (App-Ersatz-Client, R1 + Stick vor):
python3 ~/hexapod_ws/tools/joy_ws_test_client.py --host 127.0.0.1 --duration 5 --forward 0.6
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}         # STANDING → zurück auf den Bauch
```
**✅ Erwartung:** steht auf → läuft ~5 s vorwärts → setzt sich wieder auf den Bauch. Reused
die bestehenden Services — dieselbe Kette wie in Phase 2.

## T3.4 — Stack stoppen → keine Zombies, rosbridge lebt

```bash
ros2 service call /hexapod_bringup_stop std_srvs/srv/Trigger {}
sleep 3
ros2 node list | grep -E "gait_node|ros_gz|controller_manager"   # sollte LEER sein
ps aux | grep -E "gz sim|bringup_ondemand|gait_node" | grep -v grep   # keine verwaisten Prozesse
ros2 node list | grep -E "rosbridge_websocket|bringup_launcher"  # LEBEN weiter
```
**✅ Erwartung:** Gazebo/gait/controller weg, **keine** verwaisten Prozesse; rosbridge +
Launcher laufen weiter. `bringup_running` wird `false`.

## T3.5 — Status spiegelt den Zustand

```bash
ros2 service call /hexapod_bringup_status std_srvs/srv/Trigger {}   # message: stopped
ros2 topic echo /hexapod/bringup_running --qos-reliability reliable \
  --qos-durability transient_local --once          # data: false
```
**✅ Erwartung:** `stopped` / `false`.

## T3.6 — Pi-Shutdown bei laufendem Stack → Dry-Run (Desktop bleibt an)

```bash
ros2 service call /hexapod_bringup_start std_srvs/srv/Trigger {}    # erst wieder hochfahren
# (kurz warten bis Gazebo oben; Roboter auf dem Bauch reicht)
ros2 service call /hexapod_pi_shutdown std_srvs/srv/Trigger {}
```
**✅ Erwartung:** Der Roboter setzt sich (falls stehend) hin, dann Relay-Aus — und im
**Terminal 1** loggt der `shutdown_supervisor` **„would shut down now (dry run)"** bzw.
„OS shutdown on dev host … is hard-blocked". **Der Desktop fährt NICHT herunter.**

## T3.7 — Pi-Shutdown bei idle Stack → direkter Dry-Run

```bash
ros2 service call /hexapod_bringup_stop std_srvs/srv/Trigger {}     # sicher stoppen
ros2 service call /hexapod_pi_shutdown std_srvs/srv/Trigger {}
```
**✅ Erwartung:** Response `message: idle poweroff: performed=False (dev-host)`; Desktop bleibt an.

## T3.8 — Default (auto_standup_on_start:=true) unverändert

```bash
# In einem eigenen Terminal (Always-On NICHT nötig) — das alte Verhalten:
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0
```
**✅ Erwartung:** Roboter **steht automatisch auf** (wie bisher) — der Bauch-Start ist nur bei
`auto_standup_on_start:=false` (das der Launcher setzt), Default bleibt Auto-Standup.

---

## Was NICHT in Phase 3 (scope-out)
- Echte App-Integration (Connect-/Start-Screen, Buttons) = **P3.13** (Android-Session + User).
- Echter Pi-Poweroff = HW-Netz-Stage (Dev-Host nur Dry-Run).
- Video/Status-Overlay/Recovery (Phasen 4/5/6).

## Melde-Vorlage
T3.1 Nodes/Services? · T3.2 Roboter auf dem Bauch + running=true? · T3.3 auf/fahren/ab? ·
T3.4 sauber weg + keine Zombies + rosbridge lebt? · T3.5 stopped/false? · T3.6 Dry-Run +
Desktop an? · T3.7 idle Dry-Run? · T3.8 Default steht auf? Plus Auffälligkeiten.
