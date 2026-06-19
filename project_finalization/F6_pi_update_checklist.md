# Stage F6 — Pi-Update Ablaufplan (leg_changes + Block F auf den Pi)

> Teil von [Block F](F_systemsteuerung_plan.md). **Runbook**, kein Code — die
> Schritte, um den Pi (`hexapod-pi`) auf den aktuellen Stand (neue Beine + Block F
> Shutdown-Feature) zu bringen. Pi war schon eingerichtet (Phase 12 ✅: ROS2, BT,
> SSH); der Update ist im Kern Branch-Wechsel + Rebuild + F5b-Scharfschalten.

**Zugang:** `ssh hexapod-pi` (passwortlos; Pi = `hexapod-pi` / `192.168.2.65` / User
`pi`). Details: [`../docs_raspi/dev_workflow_desktop_to_pi.md`](../docs_raspi/dev_workflow_desktop_to_pi.md).

---

## 0. Vorbedingungen (auf dem Dev, vorher)
- [ ] Alle Block-F-Commits + neue Beine lokal committed **und gepusht**:
      `git push origin leg_changes` (der Pi pullt von origin — ungepusht = unsichtbar).
- [ ] Board mit F1-FW (Schalter-Bit) am Roboter, Schalter an A1 verdrahtet
      → **kein Re-Flash**, solange das Board mit dem Roboter umzieht.

## 1. Branch wechseln + pullen (am Pi)
```bash
ssh hexapod-pi
cd ~/hexapod_ws
git status                    # FIRST: sauber? (uncommitted Änderungen schützt git → checkout bricht sonst ab)
git log --oneline -5          # lokale Commits, die NICHT auf origin sind?
git fetch
git checkout leg_changes      # vom bisherigen Branch (main o.ä.)
git pull
```
- **Sauber** → läuft glatt durch (getrackte Dateien werden auf `leg_changes` gebracht).
- **Lokale Änderungen/Commits** → git überschreibt NICHT still (Abbruch/Konflikt). Erst
  klären — ⚠️ v.a. falls `servo_mapping.yaml` lokal am Pi editiert wurde (Cal nicht
  blind verlieren). Bewusst: `git stash` (aufheben) oder `git checkout -- <datei>` (verwerfen).

## 2. Subset bauen (am Pi)
```bash
colcon build --symlink-install
source install/setup.bash
```
- **`hexapod_gazebo`** ist am Pi via `COLCON_IGNORE`-Marker (untracked, bleibt über
  Branch-Wechsel) automatisch ausgeschlossen → kein `--packages-skip` nötig.
- **`hexapod_sensors` NICHT skippen** — `hexapod_bringup` hängt davon ab (package.xml),
  Skip → Bringup-Build failt (`package.sh not found`). hexapod_sensors baut sauber
  (ament_python; `ros_gz_interfaces` ist nur Runtime, auf HW ungenutzt).
- **Neues Paket `hexapod_supervisor`** baut automatisch mit. **Keine neuen apt-Pakete**
  (rclpy/std_msgs/std_srvs/launch_ros sind da) → kein `rosdep` nötig.
- **Nach Branch-Wechsel mit `--symlink-install`:** bei „can't copy …yaml: doesn't
  exist" (kaputter Symlink vom alten Branch) → `rm -rf build install log` und neu bauen.

## 3. Smoke-Verify aufgebockt (am Pi, USB-getethered ok)
```bash
# Term A: ros2 launch hexapod_bringup real.launch.py
# Term B: ros2 launch hexapod_gait gait.launch.py
# Term C: ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
# Term D: ros2 launch hexapod_teleop joy_teleop.launch.py            # USB
#         (oder controller:=ps4_bt für den schon gekoppelten DS4)
```
- [ ] Steht auf, läuft per Teleop (R1 Dead-Man halten).
- [ ] Supervisor-Node ist da (`ros2 node list | grep shutdown_supervisor`) — startet
      automatisch mit real.launch.py.

## 4. F5b — Shutdown scharfschalten (wenn Smoke ok)
- [ ] `pi_hostname: hexapod-pi` in
      `src/hexapod_supervisor/config/supervisor.yaml` eintragen → `colcon build
      --symlink-install --packages-select hexapod_supervisor` → `source install/setup.bash`.
- [ ] NOPASSWD-sudoers fürs Shutdown-Kommando (sonst feuert der non-interaktive
      Supervisor-`sudo shutdown` nicht):
      ```bash
      echo 'pi ALL=(root) NOPASSWD: /sbin/shutdown' | sudo tee /etc/sudoers.d/hexapod-shutdown
      sudo chmod 440 /etc/sudoers.d/hexapod-shutdown
      ```
- [ ] End-to-End: Schalter ≥3 s rot → hinsetzen → Relay-Aus → Log
      `shutdown finished (reason=complete, performed=True, guard=executed)` → **Pi
      fährt sauber runter** (SD intakt). ⚠️ Jetzt ist es **scharf** — der echte
      OS-Shutdown.

## 5. Geparkt / vor scharfem Bodenbetrieb prüfen
- [ ] **Cal-Recheck** (rad=0 visuell, HW = RViz) nach dem Bein-Wechsel — v.a. die
      betroffenen Pins (Bein 3 separat, vorerst zurückgestellt).

---

## Rollback (falls am Pi etwas klemmt)
```bash
cd ~/hexapod_ws
git checkout main        # zurück auf den vorigen lauffähigen Stand
colcon build --symlink-install --packages-skip hexapod_gazebo hexapod_sensors
```

## Notizen
- `use_sim_time` Default ist `false` (HW-Pfad) → bei `gait.launch.py` **kein** Arg nötig.
- BT-Controller ist schon gekoppelt (C4) → `controller:=ps4_bt`; USB ist Default.
- `pi_hostname=hexapod-pi`: auf dem **Dev** weiterhin sicher (host-mismatch + harter
  `DEV_HOSTS`-Block) — der Pi-Wert blockt den Dev-Rechner nicht.
