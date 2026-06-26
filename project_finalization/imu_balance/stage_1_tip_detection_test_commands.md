# Stufe 1 — Test-Befehle (interaktiv)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** — eigene Terminals + Befehle, setzt **nicht** voraus, dass aus
> einem vorherigen Test noch etwas läuft.

## Konventionen

- **Pro Test:** Terminals frisch öffnen; jeder Block beginnt mit dem Sourcing.
- **Zwischen zwei Tests:** alle Terminals mit **`Strg-C`** beenden.
- **Sourcing-Zeile** (steht in jedem Block):
  ```bash
  source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
  ```
- Setzt Stufe 0 voraus (IMU läuft in der Sim, `/imu/data`). Die Kipp-Erkennung
  lebt im `gait_node`; auf flachem Boden ist die *präzise* Schwelle schwer zu
  treffen (self-righting) → die **Logik** ist über die Unit-Tests (T1.6)
  bewiesen, die Live-Tests prüfen die **Integration** (feuert die Reaktion,
  keine Fehlalarme, Gating).

---

## Einmalig vorab: bauen

**Terminal (einmalig):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
```

---

## T1.6 — Unit-Tests (Schwellen-Logik, ohne Sim)

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon test --packages-select hexapod_gait --pytest-args -k test_tip_monitor --event-handlers console_direct+
colcon test-result --verbose
```

**Erwartung:** `test_tip_monitor`-Tests grün (Schwellen, Entprellung, Latch,
Reset, Rate-Trigger, Quaternion→roll/pitch).

---

## T1.2 — Stehen: kein Fehlalarm

**Terminal 1 — Sim:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Gait (Aufstehen → STANDING):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

**Erwartung:** Nach dem Aufstehen steht der Roboter; in Terminal 2 erscheint
**kein** `Kipp-WARN`/`Kipp-CRIT`. (Die `robot_description ... lenient`-Warnung ist
invocations-bedingt und harmlos — siehe Stufe 0.)

---

## T1.3 — Laufen: kein Fehlalarm

**Terminal 1 — Sim:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Gait:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

**Terminal 3 — Vorwärts laufen:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**Erwartung:** Roboter läuft mehrere Zyklen, **kein** `Kipp-WARN`/`Kipp-CRIT` in
Terminal 2 (Gang-Ripple ±0.1° << 15°, Entprellung greift).

---

## T1.4 — Gating beim Aufstehen

> Hinweis: implizit schon durch T1.2/T1.3 abgedeckt (das Aufstehen läuft dort mit,
> ohne Fehlalarm). Separater Lauf nur, falls du es isoliert sehen willst.

**Terminal 1 — Sim:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Gait (frisch → durchläuft CARTESIAN_STANDUP/REPOSITION):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

**Erwartung:** Während des Aufstehens kippt der Körper aus dem Bauch *gewollt* —
in Terminal 2 erscheint **kein** `Kipp-WARN`/`Kipp-CRIT` (State-Gating: nur
STANDING/WALKING). Erst danach (STANDING) ist die Erkennung scharf.

---

## T1.1 / T1.5 — CRIT feuert (Umkippen)

**Terminal 1 — Sim:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true world:=empty_imu.sdf
```

**Terminal 2 — Gait (aufstehen lassen, bis STANDING):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

**Terminal 3 — Roboter steil kippen (fällt um → >25° gehalten):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
gz service -s /world/empty/set_pose --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 --req 'name: "hexapod", position: {z: 0.4}, orientation: {x: 0.342, w: 0.940}'
```
(≈40° Roll aus 0.4 m → er kippt; Winkel bleibt >25° über mehr als 0.1 s.)

**Erwartung:** In Terminal 2 erscheint **`Kipp-CRIT erkannt … Safety-Freeze`**;
danach publisht `gait_node` keine Trajektorien mehr (eingefroren). Alternativ den
Roboter im Gazebo-GUI per Rotations-Werkzeug umstoßen — sobald >25° (oder schnelle
Kipprate >80°/s), feuert CRIT.

> **Recovery:** Sit/Stand-Service (`ros2 service call /hexapod_sit_stand_toggle
> std_srvs/srv/Trigger {}`) wechselt den State → Gating-Reset, Erkennung wieder normal.

---

## Status-Rückmeldung (Vorlage)

```
T1.6 unit=__   T1.2 quiet_stand=__   T1.3 quiet_walk=__   T1.4 gate=__   T1.1/T1.5 crit_freeze=__
```
