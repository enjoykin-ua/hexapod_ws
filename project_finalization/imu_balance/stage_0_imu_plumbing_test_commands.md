# Stufe 0 — Test-Befehle (Sim, interaktiv)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** — er listet alle Terminals + Befehle, die er braucht, und setzt
> **nicht** voraus, dass aus einem vorherigen Test noch etwas läuft.

## Konventionen

- **Pro Test:** öffne die unten genannten Terminals **frisch**. Jeder Befehls-Block
  beginnt mit dem Sourcing — einfach 1:1 kopieren.
- **Zwischen zwei Tests:** alle Terminals des vorherigen Tests mit **`Strg-C`**
  beenden (sonst laufen mehrere Gazebo-Instanzen gleichzeitig).
- **Sourcing-Zeile** (steht in jedem Block schon drin):
  ```bash
  source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
  ```
- ⚠️ Manche Topics/Args existieren erst **nach** der Stufe-0-Implementierung — das
  ist der Soll-Ablauf (Code ist implementiert + gebaut).

---

## Einmalig vorab: Workspace bauen

**Terminal (einmalig):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_description hexapod_gazebo hexapod_bringup hexapod_sensors
```

---

## T0.1 — `/imu/data` existiert + Rate

**Terminal 1 — Sim starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Prüfung:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic list | grep imu
ros2 topic hz /imu/data
ros2 topic echo /imu/data --once
```

> Falls `hz`/`echo` nichts zeigt: IMU ist Sensor-Daten → best_effort probieren:
> `ros2 topic echo /imu/data --once --qos-reliability best_effort`

**Erwartung:** `/imu/data` (+ `/imu/monitor`) erscheinen; `hz` ≈ 100 Hz; im `echo`
ist `linear_acceleration.z` ≈ +9.81 in Ruhe, `orientation` ein Quaternion.

---

## T0.2 — roll/pitch reagieren (Kippen)

**Terminal 1 — Sim starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Lage live beobachten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```
(`/imu/monitor` = `Vector3` x=roll, y=pitch, z=yaw in **Radiant**; das `imu_monitor`-Log
im Sim-Terminal zeigt die Werte zusätzlich in **Grad**.)

**Aktion im Gazebo-Fenster (Terminal 1):** Hexapod-Modell anklicken → Rotations-
Werkzeug (Toolbar oben bzw. Taste `r`) → um die X- bzw. Y-Achse kippen. Dabei am
besten die **`[deg]`-Zeilen im Sim-Terminal 1** beobachten (lesbarer als die
rad-Floats auf `/imu/monitor`).

**Deterministische Alternative — Terminal 3 (Modell ~20° gekippt absetzen):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
gz service -s /world/empty/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 --req 'name: "hexapod", position: {z: 0.35}, orientation: {x: 0.1736, w: 0.9848}'
```
(setzt den Hexapod mit ~20° Roll aus 0.35 m ab → `roll` springt auf ~20° und
pendelt aus.)

**Erwartung:** Beim Kippen ändern sich `roll`/`pitch` vorzeichenrichtig (eben →
≈ 0). Auf flachem Boden richtet er sich wieder auf — der Transient genügt als
Nachweis.

---

## T0.3 — Ground-Truth-Abgleich (IMU vs. Gazebo-Wahrheit)

**Terminal 1 — Sim starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — IMU-Schätzung:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```

**Terminal 3 — Gazebo-Wahrheit (Modell-Pose):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
gz topic -e -t /world/empty/dynamic_pose/info | grep -A12 'hexapod'
```

**Aktion im Gazebo-Fenster (Terminal 1):** Modell um einen definierten Winkel
(z.B. ~15°) kippen und halten (oder auf eine Schräge legen).

**Erwartung:** IMU-roll/pitch (Terminal 2) ≈ Modell-Neigung aus der Gazebo-Pose
(Terminal 3), ±1–2°. *(Exakte Feld-Extraktion wird hier finalisiert — offener
Punkt aus dem Plan §4.)*

---

## T0.4 — Vibration mit aktiven Servos (Laufen)

**Terminal 1 — Sim starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Gait starten (Aufstehen):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

**Terminal 3 — Vorwärts laufen lassen:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**Terminal 4 — Lage beobachten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```

**Erwartung:** roll/pitch zappeln gangbedingt leicht, **driften aber nicht weg**;
beim Stoppen (Terminal 3 mit `Strg-C`) wieder ≈ 0. (Beleg: fused Winkel trotz
Servo-Aktivität brauchbar — Risiko 4.)

---

## T0.5 — RViz-Visualisierung (Modell neigt sich)

**Terminal 1 — Sim starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Nur RViz** (nicht `display.launch.py` — das startet einen zweiten
robot_state_publisher und kollidiert mit der Sim):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"
```

**Aktion im Gazebo-Fenster (Terminal 1):** Modell kippen (Rotations-Werkzeug / `r`).

**Erwartung:** Das Roboter-Modell in RViz **neigt sich mit** (Fixed Frame = `world`,
getrieben vom `imu_monitor`-tf). Läuft kein `imu_monitor`, bliebe das Modell aus.

---

## T0.6 — `enable_imu`-Toggle (sauber abschaltbar)

**Terminal 1 — Sim OHNE IMU starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=false
```

**Terminal 2 — Prüfung:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic list | grep imu        # -> leer erwartet
ros2 node list | grep imu_monitor # -> leer erwartet
```

**Erwartung:** kein `/imu/data`, kein `/imu/monitor`, kein `imu_monitor`-Node,
Sim startet fehlerfrei.

---

## Status-Rückmeldung (Vorlage)

```
T0.1 hz=__Hz   T0.2 react=OK/__   T0.3 dGT=__°   T0.4 drift=__   T0.5 rviz_tilt=OK/__   T0.6 toggle=OK/__
```
