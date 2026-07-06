# Stufe 6 / IP3 — Test-Befehle: IMU-Balance-Tuning auf HW

> **Copy-paste-fertig.** Jeder Test enthält **alle** Terminals/Befehle, die er braucht (Source, Bringup,
> Aufstehen, Teleop, Tuning) — nichts zusammensuchen. Param-Namen + Launch-Args gegen `gait_node`/
> Launch-Code **verifiziert**. Plan: [`stage_6c_imu_hw_balance_tuning_plan.md`](stage_6c_imu_hw_balance_tuning_plan.md).
> HW-Gain-Store: [`config/presets/hw_balance.yaml`](../../src/hexapod_gait/config/presets/hw_balance.yaml).
>
> **Ablauf:** Du führst aus (auf dem **Pi**, per SSH), meldest knapp zurück (Status + abgelesene Zahlen);
> ich werte aus und schlage den nächsten Gain-Schritt vor. Git machst du selbst.

## ⚠️ Safety (CLAUDE.md §9)
- **2S-LiPo dran, Roboter aufgebockt** (Beine frei), **PSU/Kill-Switch in der Hand** — bei jedem Stall/
  Ruck/Aufschwingen sofort trennen.
- **Reihenfolge:** IP3.1 (Kipp-Erkennung, defensiv) **zuerst** — sie ist das Safe-State-Netz für 3.2/3.3.
- Leveling/TF (3.2/3.3) mit **kleiner Korrektur-Rate** starten (`leveling_slew_max_dps` klein), dann hoch.
- Kein DDS/Netzwerk-Setup nötig: alle Befehle laufen **lokal auf dem Pi** (SSH-Terminals). RViz am Dev ist
  optional (nur bei gemeinsamem Router-Netz, s. Anhang).

---

## Schritt 0 — Einmalig pro Session: Build + PS4-Controller per Bluetooth

**0a — Bauen + sourcen** (nur nötig, wenn `hexapod_gait`/`hw_balance.yaml` geändert wurde):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_sensors hexapod_teleop
source install/setup.bash
```

**0b — PS4-DS4 per Bluetooth verbinden** (bereits gekoppelt/trusted, MAC `D0:27:88:3D:68:9A`):
```bash
# Normalfall: einfach die PS-Taste am Controller druecken -> verbindet automatisch (trusted).
# Pruefen, dass er da ist:
ls /dev/input/js*          # js0 sollte existieren
# Reconnect erzwingen, falls PS-Taste nicht reicht:
bluetoothctl connect D0:27:88:3D:68:9A
```
> Neu koppeln (nur falls verloren): `bluetoothctl` → Controller in Pairing-Mode (Share+PS ~5 s bis
> Lightbar doppelblinkt) → `scan on` → `pair <MAC>` → `trust <MAC>` → `connect <MAC>`. Details:
> [`../C4_test_commands.md`](../C4_test_commands.md).

> **Ohne Controller** geht alles genauso per `ros2 topic pub /cmd_vel …` (in jedem Test als Alternative
> angegeben).

---

## IP3.1 — Kipp-Erkennung kalibrieren (aufgebockt, defensiv zuerst)

**Ziel:** fehlalarmfrei in Ruhe + langsamem Gang, aber CRIT/Freeze rechtzeitig bei echtem Kippen.

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU (2S-LiPo dran, aufgebockt, Kill-Switch bereit!) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py \
    loopback_mode:=false \
    enable_imu:=true \
    initial_pose:=power_on_mid
#   -> Controller aktiv + Relay/Servo-Power + bno055_imu + imu_monitor. Laeuft weiter.
```
```bash
# ── Terminal 2 (Pi): Gait-Node + AUTOMATISCHES Aufstehen (kartesisch, ~8 s) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
#   Der gait_node steht beim Start AUTOMATISCH kartesisch auf (~8 s) — das sind die
#   Node-Defaults (standup_mode=cartesian, auto_standup_duration=8.0), keine Launch-Args.
#   -> Roboter steht automatisch auf (aufgebockt: Beine strecken/beugen in der Luft),
#      danach STANDING. robot_description_file => URDF-Limits aktiv (Pflicht fuer Leveling-Clamp).
```
```bash
# ── Terminal 3 (Pi): Baseline-Rauschen im Stand beobachten ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /imu/monitor
#   Vector3: x=roll, y=pitch, z=yaw in RADIANT (Grad = rad*57.3). Alternativ die roll/pitch-
#   Grad-Zeilen im imu_monitor-Log (Terminal 1) ablesen. Ziel: Peak-|roll|/|pitch| im Ruhe-
#   Stand notieren (= Rausch-Baseline in Grad).
```
```bash
# ── Terminal 4 (Pi): Schwellen live justieren (Namen EXAKT so) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 param set /gait_node tip_angle_warn_deg  <X>   # Sim 15 ; > (Baseline-Rausch + Gang-Ripple + Marge)
ros2 param set /gait_node tip_angle_crit_deg  <Y>   # Sim 25 ; > warn, aber rechtzeitig vor echtem Kippen
ros2 param set /gait_node tip_rate_crit_dps   <Z>   # Sim 80 ; Kipprate-Schwelle gg. schnelles Wegkippen
ros2 param set /gait_node tip_debounce_ticks  <N>   # Sim 5  ; hoeher = mehr Ripple-Unterdrueckung, traeger
```

**Prüfen:**
- **IP3.1a fehlalarmfrei:** Ruhe **und** langsamer Gang → **kein** WARN/CRIT im gait_node-Log (Terminal 2).
  Gang starten — PS4 (linker Stick leicht nach vorn) **oder** ohne Controller:
  ```bash
  # Terminal 3 (statt echo) — langsamer Gang, aufgebockt:
  ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
  # stoppen: Strg+C, dann einmal Null senden:
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
  ```
- **IP3.1b CRIT feuert:** aufgebockt von Hand kippen → gait_node loggt `Kipp-CRIT … Safety-Freeze`
  **rechtzeitig** (vor dem Umschlagpunkt).
- Werte notieren → `hw_balance.yaml` (tip_*-Block).
```bash
# Recovery nach CRIT-Freeze (Latch loesen): hinsetzen + wieder aufstehen
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger '{}'
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger '{}'
```
```bash
# Shutdown (am Ende jedes Tests): Terminal 2 Strg+C (gait), dann Terminal 1 Strg+C (real).
```

---

## IP3.2 — Statisches Leveling im Stand (`horizontal`)

**Ziel:** kein Zittern/Oszillieren; Körper levelt nach leichtem Kippen zurück.

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py \
    loopback_mode:=false \
    enable_imu:=true \
    initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + automatisches Aufstehen ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
#   Der gait_node steht beim Start AUTOMATISCH kartesisch auf (~8 s) — das sind die
#   Node-Defaults (standup_mode=cartesian, auto_standup_duration=8.0), keine Launch-Args.
#   -> steht automatisch auf, dann STANDING (Leveling gilt nur in STANDING).
```
```bash
# ── Terminal 3 (Pi): Lage live mitschauen ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /imu/monitor          # roll/pitch [rad] — soll gegen ~0 gehen, wenn Leveling greift
```
```bash
# ── Terminal 4 (Pi): Leveling scharfstellen + Kd-Sweep ──
cd ~/hexapod_ws && source install/setup.bash
ros2 param set /gait_node leveling_mode          horizontal   # roll+pitch -> 0
ros2 param set /gait_node leveling_kd            0.01          # KLEIN starten (Sim 0.03; D rauscht)
ros2 param set /gait_node leveling_deadband_deg   1.5          # Sim 1.5
ros2 param set /gait_node leveling_slew_max_dps   4.0          # klein starten (Sim 8) -> Rate zaehmen
ros2 param set /gait_node leveling_enable         true         # ERST jetzt scharf (IP3.1-Netz steht)
# Kd schrittweise hoch bis knapp vor Zittern, dann einen Schritt zurueck:
ros2 param set /gait_node leveling_kd            0.02
ros2 param set /gait_node leveling_kd            0.03
```

**Prüfen:**
- **IP3.2a kein Oszillieren:** im Stand ruhig, **kein Zittern**. Bei Zittern → `leveling_kd` runter.
- **IP3.2b levelt zurück:** aufgebockt leicht kippen / auf schiefe Unterlage → Körper levelt zurück,
  ohne aufzuschwingen. Danach `leveling_slew_max_dps` wieder hoch für zügigeres, ruckfreies Nachführen:
  ```bash
  ros2 param set /gait_node leveling_slew_max_dps 8.0
  ```
- `leveling_max_angle_deg` (10°) ist der Clamp — **nicht** höher ohne `leveling_envelope_check`.
- HW-Werte (`leveling_kd`/`leveling_deadband_deg`/`leveling_slew_max_dps`) notieren → `hw_balance.yaml`.
```bash
# Leveling wieder aus (sicher) + Shutdown:
ros2 param set /gait_node leveling_enable false
# Terminal 2 Strg+C, dann Terminal 1 Strg+C
```

---

## IP3.3 — Terrain-Following im Laufen (`terrain`) — höchstes Risiko, langsam!

**Ziel:** flach geradeaus stabil (Gyro-D dämpft Wackeln, kein Aufschwingen); leichter Hang → Körper folgt.

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py \
    loopback_mode:=false \
    enable_imu:=true \
    initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + automatisches Aufstehen ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
#   Der gait_node steht beim Start AUTOMATISCH kartesisch auf (~8 s) — das sind die
#   Node-Defaults (standup_mode=cartesian, auto_standup_duration=8.0), keine Launch-Args.
```
```bash
# ── Terminal 3 (Pi): PS4-Teleop per Bluetooth (fahren mit dem linken Stick) ──
#   Voraussetzung: Controller verbunden (Schritt 0b: PS-Taste). Ohne Controller: cmd_vel-Alternative unten.
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
#   -> linker Stick vor = langsam geradeaus. △/○ = Stand/Sit, L2/R2 = Stance-Modus (siehe Anhang).
```
```bash
# ── Terminal 4 (Pi): terrain-Modus scharf + TF-Gains tunen ──
cd ~/hexapod_ws && source install/setup.bash
ros2 param set /gait_node leveling_mode    terrain     # roll->0, pitch folgt Hang-Residual + Gyro-D
ros2 param set /gait_node leveling_kd       0.02        # Gyro-D KONSERVATIV auf HW (Sim 0.03; D rauscht)
ros2 param set /gait_node leveling_enable   true
# gegen zappeligen Hang-Schaetzer ggf. langsamer:
ros2 param set /gait_node slope_estimate_tau_s 0.8      # Sim 0.5 ; groesser = traeger/glatter
```

**Prüfen:**
- **IP3.3a flach stabil:** langsam geradeaus (PS4 linker Stick leicht) → Gyro-D dämpft Gang-Wackeln,
  **kein Aufschwingen**. Bei Aufschwingen: sofort `leveling_enable false` bzw. Kill-Switch.
- **IP3.3b Hang folgen:** leichter Hang → Körper folgt (pitch hangparallel), wackelt nicht auf.
  **Grenz-Hang** (ab wann unsauber) notieren.
- `leveling_max_angle_walking_deg` (4°) ist der Walking-Clamp — nicht höher ohne Re-Check.
- **Ohne Controller** (cmd_vel-Alternative statt Terminal 3):
  ```bash
  ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'   # stoppen
  ```
- HW-Werte (`leveling_kd`, `slope_estimate_tau_s`, Grenz-Hang) notieren → `hw_balance.yaml`.
```bash
# Leveling aus + stoppen + Shutdown:
ros2 param set /gait_node leveling_enable false
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
# Terminal 3 Strg+C (teleop), Terminal 2 Strg+C (gait), Terminal 1 Strg+C (real)
```

---

## IP3.4 — HW-Gains sichern + Ladeweg verifizieren

1. Gefundene HW-Werte in [`config/presets/hw_balance.yaml`](../../src/hexapod_gait/config/presets/hw_balance.yaml)
   eintragen (Sim-Default-Kommentar je Zeile stehen lassen).
2. Bauen, damit das Preset nach `share/…/presets/` installiert wird:
   ```bash
   cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
   colcon build --packages-select hexapod_gait
   source install/setup.bash
   ```
3. Laden verifizieren (Terminal 1 = real.launch.py wie oben läuft):
   ```bash
   HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
   ros2 launch hexapod_gait gait.launch.py \
       use_sim_time:=false \
       robot_description_file:="$HEX_URDF" \
       params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/hw_balance.yaml
   # in einem weiteren Terminal pruefen, dass die HW-Werte greifen:
   ros2 param get /gait_node leveling_kd
   ros2 param get /gait_node tip_angle_warn_deg
   ```
4. Progress-File [`imu_balance_progress.md`](imu_balance_progress.md) IP3-Checkliste abhaken.

---

## Anhang — Referenz (Services, Buttons, RViz)

**Zustands-Services** (alle `std_srvs/srv/Trigger`, außer Stance = `SetBool`):
```bash
ros2 service call /hexapod_stand_up          std_srvs/srv/Trigger '{}'   # SAT -> STANDING (Aufstehen)
ros2 service call /hexapod_sit_down          std_srvs/srv/Trigger '{}'   # STANDING -> SAT (Hinsetzen)
ros2 service call /hexapod_sit_stand_toggle  std_srvs/srv/Trigger '{}'   # nach State toggeln
ros2 service call /hexapod_safety_freeze     std_srvs/srv/Trigger '{}'   # Not-Freeze (manuell)
ros2 service call /hexapod_cycle_stance      std_srvs/srv/SetBool '{data: true}'  # Stance-Hoehe wechseln
```

**PS4-Buttons** (Layout wie USB, `hid-playstation`): linker Stick = fahren, △ = Aufstehen, ○ = Hinsetzen,
L2/R2 = Stance-Modus (tief/mittel/hoch), Options/Share = Gangart/Schrittweite (siehe
[`../C_teleop.md`](../C_teleop.md)). Reconnect: PS-Taste. Verbindung weg → `/joy` verstummt → B1-Fail-safe.

**Sanity-Checks:**
```bash
ros2 node list                          # /gait_node, /bno055_imu, /imu_monitor, /joy_node da?
ros2 topic hz /imu/data                 # ~50 Hz?
ros2 topic echo /joy                    # Sticks/Buttons bewegen -> Werte aendern sich?
ros2 param get /gait_node leveling_kd   # Node lebt, Params da
```

**Optional RViz am Dev** (nur bei gemeinsamem Router-Netz + gleicher `ROS_DOMAIN_ID`):
```bash
ros2 bag record /imu/data /imu/monitor /imu/slope   # Bag liegt am DEV
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```

## Was NICHT hier getestet wird (→ separat/später)
- **Taster/Fußkontakt-Closed-Loop (S4)** gleichzeitig — eigener HW-Test; Kombi-Integration **nach** IP3.3.
- **Quer-Hang (`TF-Quer`)**, **Auto-Tuning**, **Kante/Stufe** (S4-Terrain).
