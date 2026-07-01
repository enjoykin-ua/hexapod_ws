# Rubicon-Welt — Starten, Laufen, PS4-Steuerung (Simulation)

> Hexapod in der Fuel-Outdoor-Welt **Rubicon** (Heightmap-Terrain + Felsen/Stümpfe/Ranger-Station)
> spawnen, aufstehen, geradeaus / mit PS4-Controller herumlaufen. Reiner Sim-Ablauf.
>
> Dateien: Welt [`hexapod_gazebo/worlds/rubicon.sdf`](../../src/hexapod_gazebo/worlds/rubicon.sdf) ·
> Launch [`hexapod_bringup/launch/rubicon.launch.py`](../../src/hexapod_bringup/launch/rubicon.launch.py).

---

## 0. Konventionen & Voraussetzungen

**Sourcing — in JEDEM Terminal zuerst:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

**Einmalig — Fuel-Welt in den Cache laden** (nur falls noch nicht geschehen / auf einem neuen Rechner):
```bash
gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"
```

**Bauen** (nur falls noch nicht / nach Updates):
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gazebo hexapod_bringup --symlink-install
```

---

## 1. Standard-Ablauf (granular: Welt → Aufstehen → Laufen)

### Terminal 1 — Welt + Roboter spawnen (auf der flachen Tal-Strecke)
```bash
ros2 launch hexapod_bringup rubicon.launch.py
```
Der Roboter spawnt im flachen Tal (x≈3, y=0, Boden ~1,3 m) und blickt in +x.

> **Spawn-Höhe tunen, falls nötig:** sinkt er beim Start in den Boden → `spawn_z:=1.6`; fällt er aus
> der Höhe / kippt → `spawn_z:=1.4`. Tal-Bodenhöhen (gemessen): x=3→1.33, x=4→1.35, x=5→1.33, x=6→1.26 m.
> Anderer Startpunkt entlang des Tals: `spawn_x:=5`.

### Terminal 2 — Aufstehen (gait_node → Auto-Standup)
```bash
ros2 launch hexapod_gait gait.launch.py
```
⏳ Aufstehen abwarten — danach ist der Roboter lauffähig.

### Terminal 3 — Geradeaus laufen (ohne Controller)
```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
Anhalten: Publisher mit `Ctrl-C` beenden (oder `ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'`).

---

## 2. Mit PS4-Controller fahren

### Terminal 3 — Teleop starten
```bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
#   per USB-Kabel stattdessen:  controller:=ps4_usb
```
(Bluetooth: Controller per **PS-Taste** verbinden, ist bereits gepairt/getrusted.)

### Terminal 4 — Stick-Geschwindigkeit hochsetzen (sonst max 0,05 m/s)
```bash
ros2 daemon stop
ros2 param set /joy_to_twist linear_x_scale 0.08      # Vorwärts-Tempo am Vollausschlag
ros2 param set /joy_to_twist linear_y_scale 0.06      # optional: seitlich auch schneller
```
> Diese Scales sind **live** (TLS): `param set` wirkt sofort, kein Teleop-Neustart nötig
> (`linear_x_scale`/`linear_y_scale`/`angular_z_scale`/`slow_factor`/`deadzone`).

### Steuerung
- **R1 gedrückt halten** = Dead-Man (nur dann bewegt er sich)
- **Linker Stick** = vor/zurück + seitlich · **Rechter Stick X** = drehen
- **L1** = Langsam-Modus
- **D-Pad ←/→** = Gangart wechseln · **D-Pad ↑/↓** = Schrittweite +/−

---

## 3. Höher heben & schneller laufen (optional)

Empfohlene Startwerte — höherer Beinhub, flottere Kadenz, leicht größere Schritte:

| Ziel | Parameter | von → nach |
|---|---|---|
| Bein höher heben | `step_height` | 0.040 → **0.060** |
| schnellere Bewegung (Kadenz) | `cycle_time` | 2.0 → **1.2** |
| leicht größere Schritte | `step_length_max` | 0.050 → **0.060** |
| Stick-Speed-Cap (Teleop) | `linear_x_scale` | 0.05 → **0.08** |

**`cycle_time` ist `standing_only`** → beim Launch (Terminal 2) mitgeben:
```bash
ros2 launch hexapod_gait gait.launch.py cycle_time:=1.2 step_height:=0.06 step_length_max:=0.06
```
Dann Teleop (Abschnitt 2) starten und `linear_x_scale` hochsetzen.

**Live nachjustieren** (alles außer `cycle_time` geht im Lauf):
```bash
ros2 daemon stop
ros2 param set /gait_node step_height 0.07          # noch höher
ros2 param set /gait_node step_length_max 0.07      # größere Schritte
ros2 param set /joy_to_twist linear_x_scale 0.10    # schneller am Stick
```
**`cycle_time` ändern** nur im **STANDING** (Stick loslassen → STOPPING → STANDING):
```bash
ros2 param set /gait_node cycle_time 1.0
```

> Vorsicht-Reihenfolge: auf dem rauen Terrain lieber hochtasten statt verdoppeln —
> `cycle_time 1.2 / step_height 0.06 / step_length_max 0.06` ist ein gutmütiger Startpunkt.

---

## 4. RViz parallel (optional)
```bash
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"
```
Fixed Frame = `world` → das Modell neigt sich mit (über die IMU-TF).

---

## 5. Hinweise
- **IMU-Balance-Features sind Default aus.** Zum Zuschalten (Leveling, adaptiver Touchdown, Slip,
  Plausibilität, Fault-Inject) siehe [`general_commands_usability.md`](general_commands_usability.md)
  Bereich B/C. Die Welt bringt IMU- und Contact-Plugins schon mit.
- **Terrain ist rau** (Tal ~3°, Felsen drumherum) → ein langsamer Open-Loop-Lauf ist am stabilsten;
  schnell/groß = kippeliger.
- Welt-Name ist intern `empty` (wie `empty_imu.sdf`) → alle Bridges/Topics laufen unverändert.
