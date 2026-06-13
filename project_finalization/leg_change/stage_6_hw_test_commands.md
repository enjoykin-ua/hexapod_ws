# Stage 6 (HW Desktop) — Test-/Live-Anleitung (Bein-Umbau `leg_changes`)

> **Plan:** [`stage_6_hw_plan.md`](stage_6_hw_plan.md) · Cal-Anleitung (S2): [`test_commands.md`](test_commands.md) TEIL A.
> **Interaktiv** — du führst aus, knappe Status-Meldungen zurück
> ([[feedback_test_commands_in_doc_not_chat]]). **Maschine: Desktop**, Servo2040 `/dev/ttyACM0`.
> Branch `leg_changes`. Reihenfolge **aufgebockt → Boden** (CLAUDE.md §9).

## ⚠️ Safety (CLAUDE.md §9) — vor JEDEM Schritt
- **Aufgebockt/aufgehängt** — Beine frei, kein Bodenkontakt (bis S6.4).
- **PSU-Kill-Switch in der Hand.** Bei Stall / Ruck / `OVERCURRENT` / `WATCHDOG` /
  ungewollter Bewegung → **sofort trennen**.
- **`real.launch.py` muss durchlaufen**, solange getestet wird (Plugin-Loop =
  Watchdog-Heartbeat). Nicht zwischendrin beenden → sonst Relay-Drop.
- Erste Bewegungen **langsam**; erst ein Verständnis, dann mehr.

---

## S6.0 — Build + sourcen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
git branch --show-current          # "leg_changes"
colcon build --symlink-install
source install/setup.bash
```

---

## S6.1 — Cal-Verify (GATE, = Plan-Bullet 2.4)  [S6-T1]
> Ziel: die S2-Cal der neuen Beine **physisch** bestätigen. **KEIN gait, kein Aufstehen.**

```bash
# Terminal 1 (läuft durch!) — echte HW, Servos → power_on_mid (Default)
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```
- [ ] Alle 18 Servos smooth auf `power_on_mid` (1500 µs), Relay an, **kein Trip**.
- [ ] Alle 6 `leg_*_controller` + `joint_state_broadcaster` „activated".

```bash
# Terminal 2 — RViz HW-Spiegel (zeigt die kommandierte Pose live)
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view_hw.rviz
```

```bash
# Terminal 3 — rad 0 an alle Beine (Bein = gestreckt). LANGSAM (time_from_start 2 s).
cd ~/hexapod_ws && source install/setup.bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}"
done
```
- [ ] **HW == RViz:** alle Beine bei rad 0 **gestreckt/horizontal**, kein schiefes
      Segment; die echten Beine stimmen mit dem RViz-Modell überein (Cal ok).
- [ ] Falls ein Bein sichtbar abweicht → melden (Cal-Pin nachjustieren, S2/TEIL A).

```bash
# Terminal 3 — vorsichtiger Sweep EINES Beins (klein, langsam). leg_1 als Beispiel:
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
'{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.2, -0.3, 0.3], time_from_start: {sec: 2}}]}'
# zurück auf rad 0:
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
'{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```
- [ ] Sweep folgt sauber, **kein** `SAFETY_FREEZE` / Stall / Ruck / Anschlag-Knall.
- [ ] (Optional pro Bein wiederholen, klein bleiben — innerhalb der Limits.)

> **GATE:** Erst wenn S6.1 sauber ist → S6.2. Sonst Cal/Limits prüfen, nicht aufstehen.

---

## S6.2 — Aufstehen aufgebockt  [S6-T2/T3]
Terminal 1 (`real.launch.py`) läuft weiter.
```bash
# Terminal 2 (läuft durch) — gait_node auf HW: use_sim_time FALSE + Limit-Check aktiv
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
> **S6-Update (schürffrei-Fix):** Aufstehen läuft jetzt am **breiten** standup_radial
> **0.21** (≈ power_on_mid → Füße stehen schon dort → fast senkrechter, schürffreier
> Touchdown), **dann Tripod-Reposition auf 0.160** (Walk-Pose). Ein Reposition-Hop
> ist also **erwartet + gewollt** (war vorher das Schleifen-Problem am engen 0.160).

- [ ] Auto-Standup: Touchdown **breit** (~0.21), Bauch hebt **schürffrei** ab (kein Schleifen kurz vor Boden), dann **Reposition** (Beine gehoben + nach innen versetzt) auf radial 0.160.
- [ ] **Schleift der Touchdown jetzt nicht mehr?** (Hauptfrage.) Reposition-Schritt selbst schürffrei (Beine gehoben)?
- [ ] Steht stabil aufgebockt; Log: `Cartesian-Standup gestartet … radial=0.210, body_height=-0.080` (dann Reposition auf 0.160).

```bash
# Terminal 3 — Hinsetzen/Aufstehen je Höhe testen (aufgebockt)
ros2 service call /hexapod_sit_down  std_srvs/srv/Trigger     # hinsetzen (Rest)
ros2 service call /hexapod_stand_up  std_srvs/srv/Trigger     # wieder aufstehen
# Höhe wechseln (höher/tiefer), dann Sit/Stand erneut:
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool '{data: true}'   # → höher (bis "hoch")
ros2 service call /hexapod_sit_down  std_srvs/srv/Trigger     # ⚠️ direkt-Sit aus "hoch" (-0.100)
ros2 service call /hexapod_stand_up  std_srvs/srv/Trigger
```
- [ ] Sit/Stand in jeder Höhe sauber.
- [ ] **direkt-Sit aus „hoch" (−0.100):** größter Absenk-Weg — Absenken **ohne Stall/
      Ruck**? Falls es hier hakt → melden (dann route ich Sit aus „hoch" über mittel).

---

## S6.3 — Laufen + Gangarten + Teleop aufgebockt  [S6-T4]
```bash
# Terminal 4 — Teleop (PS4). USB: ps4_usb (Default). use_sim_time bleibt false.
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```
Oder ohne Controller (deterministisch, langsam vorwärts):
```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.02, y: 0.0, z: 0.0}, angular: {z: 0.0}}'
```
- [ ] **Tripod** forward/sidestep/yaw/diagonal: Beine bewegen sauber, kein `IKError`/Freeze/Stall.
- [ ] **Stance-Switch** L2/R2 (tief/mittel/hoch) aufgebockt sauber.
- [ ] **Schrittweite** D-Pad ↑/↓ (0.030–0.070) + **Gangarten** D-Pad ←/→ durchschalten.
- [ ] Strom grob plausibel (kein Dauer-Stall-Strom), keine Überhitzung spürbar.

> **GATE:** Erst wenn S6.2 + S6.3 aufgebockt sauber sind → Boden (S6.4).

---

## S6.4 — Boden  [S6-T5/T6]
> Roboter vom Bock auf festen, ebenen Boden. Kill-Switch bereit. Stack neu starten
> (real.launch + gait wie oben) oder durchlaufen lassen, dann hinsetzen→aufstehen am Boden.
- [ ] **Aufstehen am Boden:** Bauch hebt ab, Füße **schürffrei**, steht stabil; Strom plausibel (kein Dauer-Stall).
- [ ] **Laufen am Boden:** Tripod vorwärts stabil, kein Wegrutschen/Einknicken.
- [ ] Stance-Switch + Gangarten am Boden (Tripod zuerst; Nicht-Tripod darf wackeln — open-loop, A5).

---

## S6.5 — Sauberes Beenden
```bash
# Hinsetzen + Shutdown (Relay aus), dann Terminals Strg+C
ros2 service call /hexapod_shutdown std_srvs/srv/Trigger   # sitzt hin + Relay aus (terminal)
# danach Terminal 1 (real.launch) Strg+C
```

---

## Schnell-Diagnose (HW)
| Symptom | wahrscheinlich | Sofort |
|---|---|---|
| Servo zuckt/Trip beim Enable | Power-On-Zentrieren / Anschlag | Kill-Switch; aufgebockt? power_on_mid? |
| Bein bei rad 0 schief (≠ RViz) | Cal-pulse_zero verschoben | S6.1 stoppen; Pin nachjustieren (TEIL A) |
| `SAFETY_FREEZE` beim Sweep/Lauf | PWM am Cal-Limit / Pose out-of-limit | Limits/Cal prüfen; kleiner kommandieren |
| gait reagiert nicht / steht | `use_sim_time` true → Timer still | gait mit **`use_sim_time:=false`** starten |
| Stall/Hitze beim Stehen am Boden | Pose zu gestreckt / Last | Kill-Switch; aufgebockt prüfen; body_height |
| `WATCHDOG`/Relay-Drop | real.launch beendet / Frame-Stille | Terminal 1 muss durchlaufen |
