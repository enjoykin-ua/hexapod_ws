# Stance-Modi — Test-Anleitung (SIM + HW)

> Für S.6 (SIM) + S.7 (HW). Offline (S.0–S.5) ist grün. Plan:
> [`stance_modes_plan.md`](stance_modes_plan.md). **Du führst aus, ich werte Status aus.**
> 3 Modi: **hoch** −0.140/0.225 · **mittel** −0.100/0.245 (Boot) · **tief** −0.070/0.255, alle step 0.080,
> step_length 0.089. (Radien mit Femur-Marge — real-engine-validiert, nicht am Tool-Rand.)

## 0. Offline (grün, Reproduktion)
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop && source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_teleop
colcon test-result --test-result-base build/hexapod_gait --verbose      # 201/0/1-skip
colcon test-result --test-result-base build/hexapod_teleop --verbose    # 30/0/1-skip
# Envelope je Modus (Hinweis: Tool ist am Rand zu optimistisch — maßgeblich ist
# der echte-Engine-Test test_mode_walks_all_directions_no_ikerror in der Suite):
for r_bh in "0.225 -0.140" "0.245 -0.100" "0.255 -0.070"; do set -- $r_bh
  python3 tools/walking_envelope_check.py check --radial $1 --body-height $2 \
    --step-length 0.089 --step-height 0.080 --scenario all | grep -i result; done   # 3× GREEN
```

## 1. SIM (S.6) — `use_sim_time:=true`
### 1.1 Starten (ohne feet_closer-Preset — Defaults = mittel)
```bash
# Terminal A:
ros2 launch hexapod_bringup sim.launch.py
# Terminal B (Gait, Defaults = Modus mittel -0.100/0.220):
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  use_sim_time:=true
# Erwartet: Aufstehen → Reposition → STANDING in Modus "mittel" (Körper ~10 cm hoch).
```

### 1.2 Modi cyclen + jeweils laufen (Terminal C)
```bash
ros2 service list | grep cycle_stance       # /hexapod_cycle_stance vorhanden

# höher → hoch (-0.140): Körper hebt + Beine ziehen rein (Reposition).
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}"
# Erwartet: ~2 s gekoppelte Reposition (radial 0.220→0.190, Körper sinkt auf -0.140).
#   message "stance -> hoch". Danach laufen:
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}"   # läuft, KEINE IKError
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}"

# höher nochmal → bleibt hoch (clamp): message "bereits am höchsten".
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}"

# tiefer → mittel → tief (-0.070): Beine weiter raus.
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: false}"   # → mittel
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: false}"   # → tief
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}"   # läuft in tief
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}}"
# 🟡 BEOBACHTEN je Modus: Übergang weich (kein Ruck/Freeze), Laufen ohne IKError-Log,
#   kein Kippen; Selbst-Kollision der Beine visuell prüfen (A4 ungeprüft).
```

### 1.3 Hinsetzen aus jedem Modus (inkl. Routing aus hoch)
```bash
# In hoch wechseln, dann hinsetzen → MUSS erst auf mittel switchen, dann sitzen:
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}"    # → hoch (von mittel)
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}
# Erwartet Log: 'sit-down aus "hoch": erst Switch auf mittel, dann hinsetzen'.
#   Ablauf: Stance-Switch hoch→mittel (~2 s) → dann normale Hinsetz-Sequenz → SAT.
#   KEIN out-of-reach/IKError.
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}                    # → mittel
# Aus mittel/tief direkt hinsetzen (kein Routing):
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}                    # direkt, ok
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
```

## 2. SIM mit PS4-Controller (S.6)
```bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```
- **L2 / R2 (OHNE R1)** = Stance-Modus **tiefer / höher** (3 Stufen, geklemmt).
- **R1 halten + Sticks** = fahren wie gehabt; **Cross-lang** = Show; **in Show R1+L2/R2** = Tibia-Curl.
- 🟡 **Wichtig:** stufenlose Höhe gibt es nicht mehr — L2/R2 cyclen jetzt die Modi.
- step_length-Trim (D-Pad ↑/↓) jetzt in **0.01**-Schritten, max 0.12.

## 3. HW aufgebockt → Boden (S.7)
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  use_sim_time:=false
```
- Aufgebockt: alle 3 Modi cyclen + je laufen; aus jedem Modus hinsetzen (hoch via mittel).
- 🟡 **BEOBACHTEN:** Übergänge weich, kein Servo-Stall/Brummen; in hoch (tiefste/engste Pose) wird die
  Tibia am kühlsten — prüfen, ob die engere Pose mechanisch sauber sitzt.
- Dann Boden: Modi cyclen + laufen; **kein Fuß-Rutschen** beim Reposition-Anteil des Switch; CoG-stabil.

## 4. Abnahme-Kriterien
| # | Kriterium | Stufe |
|---|---|---|
| 1 | Boot → STANDING in mittel, läuft | SIM+HW |
| 2 | L2/R2 cyclen alle 3 Modi, Übergang weich, je laufen ohne IKError | SIM+HW |
| 3 | Hinsetzen aus hoch routet über mittel (kein out-of-reach) | SIM+HW |
| 4 | Hinsetzen aus mittel/tief direkt | SIM+HW |
| 5 | Clamp an den Enden (kein Wrap) | SIM |
| 6 | Selbst-Kollision beim Switch visuell ok | SIM |
| 7 | HW: kein Fuß-Rutschen, CoG-stabil, Tibia kühler in hoch | HW |
