# Stufe 0 — Test-Befehle (Sim, interaktiv)

> **Skizze vor Implementierung** (CLAUDE.md §4: Test-Liste reicht vorab; final nach
> Code). Du führst die Befehle aus, knappe Status-Meldung zurück. Alle Befehle
> vollständig + aus dem Doc aufrufbar. Setzt gebauten + gesourceten Workspace voraus.
>
> ⚠️ Einige Topics/Args (`enable_imu`, `/imu/data`, `imu_monitor`) existieren erst
> **nach** der Stufe-0-Implementierung — bis dahin ist dies der Soll-Ablauf.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_description hexapod_gazebo hexapod_bringup hexapod_sensors
source install/setup.bash
```

> Die IMU-Welt `empty_imu.sdf` liegt in `hexapod_gazebo` — daher dort mitbauen.

---

## T0.1 — `/imu/data` existiert + Rate

Sim mit IMU starten (Default-Welt = `empty_imu.sdf` mit `gz-sim-imu-system`;
explizit zur Sicherheit angegeben):

```bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Welt-/Spawn-/Lauf-Sanity** (Roboter steht + läuft in der IMU-Welt; in weiteren
Terminals, jeweils `source install/setup.bash`):

```bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**Erwartung:** Gazebo lädt `empty_imu.sdf` ohne Fehler, Roboter spawnt, steht auf und
läuft; Fußkontakt läuft weiter (Superset-Welt behält das contact-system).

In einem zweiten Terminal (`source install/setup.bash`):

```bash
ros2 topic list | grep imu
ros2 topic hz /imu/data
```

**Erwartung:** `/imu/data` erscheint; `hz` ≈ konfigurierte `update_rate` (50/100 Hz).

> IMU ist Sensor-Daten → ggf. best_effort-QoS. Falls `echo`/`hz` nichts zeigt:
> `--qos-reliability best_effort` testen.

```bash
ros2 topic echo /imu/data --once
```

**Erwartung:** `orientation` (Quaternion), `angular_velocity`, `linear_acceleration`
plausibel (in Ruhe: `linear_acceleration.z` ≈ +9.81, Rest ≈ 0).

---

## T0.2 — roll/pitch reagieren (Kipp-Test)

Im Gazebo-GUI das Roboter-Modell mit dem **Rotations-Werkzeug** kippen
(Nase runter, dann eine Seite runter) **oder** das Modell auf einer Schräge
spawnen. Dabei beobachten:

```bash
ros2 topic echo /imu/data --field orientation
# zusätzlich, wenn imu_monitor läuft:
ros2 topic echo /imu/monitor   # roll/pitch in Grad (Form siehe Stage-0-Plan §4)
```

**Erwartung:** Nase runter → pitch ändert sich vorzeichenrichtig; Seite runter →
roll. Zurück in die Waage → beide ≈ 0.

---

## T0.3 — Ground-Truth-Abgleich

Modell definiert kippen (z.B. 15°) und die Gazebo-Wahrheit gegen `/imu/data`
halten:

```bash
# Gazebo-Modell-Pose (Ground Truth) auslesen:
gz topic -e -t /world/empty/dynamic_pose/info | head
# parallel die IMU-Schätzung:
ros2 topic echo /imu/monitor
```

**Erwartung:** IMU-roll/pitch ≈ Modell-Neigung (±Toleranz, z.B. < 1–2°).
*(Exakter Topic-/Feldpfad wird nach Implementierung finalisiert.)*

---

## T0.4 — Vibration mit aktiven Servos

Aufstehen + laufen lassen, dabei die Lage-Ruhe prüfen:

```bash
# in weiteren Terminals (jeweils gesourcet):
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
# Lage beobachten:
ros2 topic echo /imu/monitor
```

**Erwartung:** roll/pitch zappeln gangbedingt leicht, **driften aber nicht weg**;
in Ruhe wieder ≈ 0. (Beleg, dass der fused Winkel trotz Servo-Aktivität brauchbar
ist — Risiko 4.)

---

## T0.5 — RViz-Visualisierung

```bash
ros2 launch hexapod_description display.launch.py
# bzw. RViz mit der Stufe-0-Konfig; IMU-Orientierung als Display/tf einblenden
```

**Erwartung:** Die IMU-Lage ist in RViz sichtbar und folgt dem Kippen.

---

## T0.6 — `enable_imu`-Toggle

```bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=false
ros2 topic list | grep imu    # -> leer erwartet
```

**Erwartung:** kein `/imu/data`, kein `imu_monitor`, Sim startet fehlerfrei.

---

## Status-Rückmeldung (Vorlage)

```
T0.1 hz=__   T0.2 react=OK/__   T0.3 dGT=__°   T0.4 drift=__   T0.5 rviz=OK/__   T0.6 toggle=OK/__
```
