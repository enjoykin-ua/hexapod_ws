# Stage F5 — Test-Anleitung (Integration + Pi-Deployment)

> Plan: [`F5_integration_plan.md`](F5_integration_plan.md). **F5a** ist dev-testbar
> (Guard blockt `enjoykin-ubutu`). **F5b** ist die Pi-Checkliste (später).

## Voraussetzungen

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_supervisor hexapod_bringup
source install/setup.bash
```

---

## F5a-L1 — Supervisor startet automatisch mit (aufgebockt)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```
**Erwartung:** im Launch-Log erscheint **ohne Extra-Befehl**:
```
[shutdown_supervisor]: shutdown_supervisor up: enable_os_shutdown=True, pi_hostname=''
```
`pi_hostname=''` → auf Dev fährt nichts runter (Guard). Prüfen:
```bash
ros2 node list | grep shutdown_supervisor
```

## F5a-L2 — Flip → guard=dev-host (VOLLER Stack nötig, aufgebockt)

> **Wichtig:** Diese Kette braucht **`/hexapod_shutdown`** — den liefert
> **gait_node**. Ohne laufenden gait-Stack loggt der Supervisor nur
> `/hexapod_shutdown not available yet, retry` (das ist korrektes Warte-Verhalten,
> nicht der fertige Test). Also ALLE Terminals starten:

**Terminal A — Hardware + Supervisor (Supervisor startet hier automatisch mit):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```

**Terminal B — gait_node (liefert `/hexapod_shutdown`):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false
```

**Roboter-Zustand prüfen** — `/hexapod_shutdown` akzeptiert nur aus **STANDING**
oder **SAT**. Nach dem Boot ist er i. d. R. in **SAT** (Boot-/Ruhe-Pose) → passt.
Optional aufstehen lassen, um den STANDING→Sit-Pfad zu sehen (Term C):
```bash
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
```

**Terminal D — Auslösen** (physischer Schalter ≥3 s rot **oder** manuell):
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: false}"
sleep 1
ros2 topic pub -1 --qos-reliability reliable --qos-durability transient_local \
  /hexapod/shutdown_request std_msgs/msg/Bool "{data: true}"
```

**Erwartung im real.launch.py-Log (Terminal A):**
```
shutdown requested -> begin controlled shutdown
/hexapod_shutdown accepted: ...
OS shutdown on dev host enjoykin-ubutu is hard-blocked
shutdown finished (reason=complete, performed=False, guard=dev-host)
```
→ Dev fährt **nicht** runter; Roboter setzt sich hin + Relay aus (aufgebockt ok).

**Troubleshooting:**
- `... not available yet, retry` (dauerhaft) → **gait-Stack (Term B) läuft nicht**.
- `/hexapod_shutdown refused (... state=...) -> retrying` → Roboter ist nicht in
  STANDING/SAT (z. B. WALKING/STARTUP) → warten bis STANDING oder `/hexapod_stand_up`.

## F5a-L3 — Off-Schalter

```bash
ros2 launch hexapod_bringup real.launch.py with_supervisor:=false
ros2 node list | grep shutdown_supervisor   # -> KEIN Treffer
```
**Erwartung:** der Supervisor-Node startet NICHT.

---

## F5b — Pi-Deployment-Checkliste (später, am Pi)

> Erst wenn der Pi ROS2-Jazzy + Workspace hat (Block D1). Plug-and-play bis auf:

1. **Hostname holen:** am Pi `hostname` ausführen.
2. **Eintragen:** `pi_hostname:` in
   `src/hexapod_supervisor/config/supervisor.yaml` = dieser Wert. `colcon build`.
3. **Shutdown-Privileg** (endgültige Wahl am Pi), z. B. sudoers:
   ```bash
   echo 'DEINUSER ALL=(root) NOPASSWD: /sbin/shutdown' | sudo tee /etc/sudoers.d/hexapod-shutdown
   sudo chmod 440 /etc/sudoers.d/hexapod-shutdown
   ```
4. **End-to-End** (aufgebockt → Boden): `real.launch.py` + gait + Schalter ≥3 s →
   hinsetzen → Relay-Aus → Log `performed=True, guard=executed` → **Pi fährt sauber
   runter**, SD intakt.

---

## Erfolgs-Kriterium
**F5a:** L1 (Auto-Start) + L2 (`guard=dev-host`) + L3 (Off-Schalter) grün →
F5a.1–F5a.7 abhaken. **F5b** wird am Pi abgearbeitet (Block D1).
