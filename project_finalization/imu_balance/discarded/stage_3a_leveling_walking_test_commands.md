# Stufe 3a — Test-Befehle (interaktiv)

> Du führst die Tests aus, knappe Status-Meldung zurück. Jeder Testfall ist
> eigenständig (frische Terminals + Sourcing). Setzt Stufe 2 (🟢) voraus.

## Konventionen

- **Sourcing** (jeder Block): `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Zwischen Tests:** alle Terminals mit `Strg-C` beenden.
- **`/imu/monitor`** = `Vector3` mit **x=roll, y=pitch, z=yaw** in **Radiant**
  (× 57.3 = Grad). Auf der um +Y geneigten Rampe ist **y (pitch)** der Hangwinkel.
  Bequemer: das imu_monitor-Terminal loggt roll/pitch/yaw direkt in **Grad**.
- Leveling im Lauf ist **klein** (Walking-Clamp ~4°, weil der gelevelte Swing-Apex
  bindet). Der Test zeigt den Unterschied **mit vs. ohne** Leveling beim Hochlaufen.

---

## Einmalig: bauen

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## T3a.U — Unit- + Tool-Tests (ohne Sim)

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon test --packages-select hexapod_kinematics hexapod_gait \
  --pytest-args -k "leveling or balance or rotate_xy" --event-handlers console_direct+
colcon test-result --verbose
# Offline-Walking-Hülle (Pitch/Roll ~4°, combined ~2°):
python3 tools/leveling_envelope_check.py --walking --theta-list 2,4,6,8,10
pytest tools/test_leveling_envelope_check.py -q
```
**Erwartung:** Paket-Tests grün; Walking-Tool zeigt enge Hülle (combined fällt früh).

---

## T3a.1 — Rampe lädt, Roboter steht flach, läuft hoch (Leveling AUS)

**Terminal 1 (Ramp-Welt 8°):**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
**Terminal 2 (gait):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
**Terminal 3 (pitch):** `ros2 topic echo /imu/monitor`

**Terminal 4 (langsam vorwärts in die Rampe):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
> Kurzer Anlauf (~0.7 m, `spawn_x:=-0.7`); die Rampe steigt ab x=0. Bei `slope_deg`
> via `ramp.launch.py slope_deg:=…`. Mehr/weniger Anlauf: `spawn_x:=…`.

**Erwartung:** Roboter spawnt flach (pitch ≈ 0), steht auf, läuft +x in die Rampe;
beim Hochlaufen steigt **pitch (y) auf ~8°** (Körper neigt mit der Rampe, Leveling
aus). Kein Freeze.

---

## T3a.2 — Leveling AN: Körper neigt sich beim Hochlaufen weniger

Wie T3a.1, aber gait **mit Leveling-Arg** starten (Terminal 2 statt der T3a.1-Variante):
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
Dann Terminal 1 (Welt), 3 (`/imu/monitor`), 4 (`cmd_vel` vorwärts) wie T3a.1.

> **Live umschalten statt Neustart?** `ros2 param set /gait_node leveling_enable true`.
> Meldet das **„Node not found"**, ist der ROS2-Daemon stale (häufig nach mehreren
> Launches) → einmal `ros2 daemon stop` (startet neu) + `ros2 node list` zur
> Bestätigung, dann `ros2 param set` erneut. Der Launch-Arg oben umgeht das.

**Erwartung:** beim Hochlaufen bleibt **pitch (y) ~4° niedriger** als ohne Leveling
(Walking-Clamp ~4°) — also auf der 8°-Rampe ~4–5° statt ~8°. Glatt, **kein** Freeze,
kein sichtbarer Fuß-Schlupf-Exzess. (Der Effekt ist bewusst klein — volles
Hang-Leveling im Lauf kommt mit 3c.)

**Gegencheck Stand vs. Lauf:** auf der Rampe **anhalten** (`cmd_vel`=0, Terminal 4
`Strg-C`) → im STANDING levelt es bis ~8° (STANDING-Clamp 10°) → pitch geht weiter
Richtung 0. Beim Wiederanlaufen klemmt es zurück auf den 4°-Walking-Clamp.

---

## T3a.3 — Test-Ladder (wie weit kommt er hoch)

Je Winkel T3a.1/T3a.2 mit `slope_deg:=` aus **0, 6, 12, 18, 24, 30** neu starten
und beobachten: läuft er hoch, levelt (bis Clamp), kein Freeze/Umkippen? Den real
erreichten Maximalwinkel melden (z.B. „bis 18° sauber, ab 24° rutscht/kippt er").

> **Hinweis Tip-Erkennung:** ab ~18° Rampe übersteigt die Rest-Neigung (Hang − 4°
> Leveling) die `tip_angle_warn` (15°) → die Stufe-1-Kipp-Erkennung stoppt (cmd_vel=0).
> Das ist **erwartet** (Steilhang-Tip relativ zum Soll = 3c). Für die Steil-Ladder
> die Schwelle live anheben: `ros2 param set /gait_node tip_angle_warn_deg 35` (und
> `tip_angle_crit_deg 45`), oder `ros2 param set /gait_node tip_detection_enable false`.

---

## Bekannte Grenzen (3a)

- **Walking-Leveling ist klein (~4°)** — der gelevelte Swing-Apex bindet. Echtes
  Steilhang-Leveling im Lauf = **3c** (hang-bewusste Schwunghöhe + Param-Adaption).
  `step_height` NICHT senken (Schürf-Gefahr bergauf).
- **Climbing-Ceiling in Sim** = CoG/Reibung (µ=1.2 → ~50°); auf **HW = Servo-Torque**
  (Block A), der echte Engpass — separat messen.
