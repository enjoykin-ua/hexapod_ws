# B1 — Hinsetz-/Abschalt-Sequenz — Test-Anleitung (SIM + HW)

> **Zweck:** ausführbare Test-Befehle für B1.9 (SIM) und B1.10 (HW aufgebockt → Boden).
> Offline-Tests (Unit/Lint/Envelope, B1.7/B1.8) sind bereits grün — siehe unten Abschnitt 0.
> Plan: [`B1_sitdown_plan.md`](B1_sitdown_plan.md). Du führst aus, ich werte knappe Status-Meldungen aus.

---

## 0. Offline (bereits grün, zur Reproduktion)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
colcon test --packages-select hexapod_gait
colcon test-result --test-result-base build/hexapod_gait --verbose
# Erwartet: 111 tests, 0 failures, 1 skipped (copyright). flake8/pep257 grün.

# Envelope unberührt grün:
python3 tools/walking_envelope_check.py check --radial 0.215 --body-height -0.120 \
  --step-length 0.089 --step-height 0.080 --scenario all          # → GREEN (4/4)
python3 tools/standup_envelope_check.py --radial 0.295 --bh-final -0.120   # → GRÜN
```

---

## 1. SIM (B1.9) — RViz + Gazebo, `use_sim_time:=true`

### 1.1 Sim starten (Terminal A)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

### 1.2 Gait starten (Terminal B) — feet-closer-Preset

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
# Erwartet: Auto-Standup → Reposition → STANDING (wie bisher).
```

### 1.3 Services prüfen (Terminal C)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 service list | grep hexapod_
# Erwartet u.a.: /hexapod_sit_down  /hexapod_stand_up  /hexapod_shutdown
```

### 1.4 Hinsetzen (Rest) — STANDING → SAT

```bash
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}
# Erwartet RViz/Gazebo: Füße erst nach AUSSEN (Reposition), Körper sinkt sanft auf
#   den Bauch, dann gehen die Beine in die BOOT-/SPAWN-POSE (Beine HOCH) — NICHT
#   flach auf den Boden. success=True, message "Rest".
# State-Log: REPOSITION → SITDOWN_LOWER → SITDOWN_FLATTEN → SAT.
# 🟢 ERWARTET (User 2026-06-03): Endpose = Spawn-Pose (Beine hoch), Bauch trägt.
#   Das Hinlegen der Beine passiert NICHT kontrolliert — erst beim Relay-Aus (HW).
# 🟡 BEOBACHTEN: kein Durchschießen/Kippen; stabile Bauchlage mit Beinen hoch.
```

### 1.5 Aufstehen aus SAT — SAT → STANDING

```bash
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
# Erwartet: kartesisches Aufstehen von der flachen Pose → Touchdown → Push →
#   Reposition → STANDING. success=True.
# 🟡 BEOBACHTEN (Self-Review #7): beim Touchdown aus rad-0 kein vorzeitiger
#   Boden-Kontakt / Ruck (Bauch ist gestützt).
```

### 1.6 cmd_vel wird in Sitdown/SAT ignoriert

```bash
# Während/ nach dem Hinsetzen (state SAT) cmd_vel schicken → darf NICHT laufen:
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
# Erwartet: Roboter bleibt sitzen (keine Bewegung). Ctrl-C zum Stoppen.
```

### 1.7 Shutdown (terminal) — Sim ohne Relay

```bash
ros2 service call /hexapod_shutdown std_srvs/srv/Trigger {}
# Erwartet: hinsetzen (falls STANDING) → SAT; Log "Relay-Aus" + WARN
#   "/hexapod_relay_set not available" (OK in Sim, kein Plugin). success=True.
# Danach stand_up ablehnen lassen:
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
# Erwartet: success=False, message enthält "latched".
#
# Wiederinbetriebnahme: gait_node neu starten (im gait-Terminal Ctrl-C, dann
# gait.launch.py aus 1.2 erneut) → Latch weg, Auto-Standup läuft wieder an.
# (sim.launch.py muss NICHT neu gestartet werden.)
```

### 1.8 Comms-Loss-Fail-safe (OPTIONAL — Funktionsnachweis)

> **Was das ist:** Sicherheitsfunktion fürs Laufen am Boden. Wenn ein steuernder
> Controller (PS4) die Verbindung verliert → `/cmd_vel` verstummt → Roboter setzt
> sich nach `comms_loss_sitdown_timeout` Sekunden **automatisch hin** (Rest, bestromt),
> statt regungslos stehen zu bleiben. Bei Reconnect per `stand_up` wieder hoch.
> **Default AUS (0)** — im Normalbetrieb inaktiv. Dieser Test ist optional und ändert
> nichts an 1.4/1.5; **überspringbar**, wenn du den Disconnect-Fall nicht prüfen willst.
>
> **Voraussetzung:** Roboter im **STANDING** (NICHT SAT/latched) — also **vor** dem
> Shutdown-Test 1.7 ausführen, oder gait vorher neu starten. „Idle ≠ Disconnect": ein
> verbundener Controller sendet dauernd `/cmd_vel` (auch 0) → kein Timeout; nur echtes
> Verstummen feuert, und nur wenn vorher mindestens ein `/cmd_vel` ankam.

```bash
# (Terminal D, optional) State + Logs mitlesen:
#   ros2 topic echo /rosout | grep -i comms     # oder einfach die gait-Konsole (Terminal B)

# 1) Fail-safe aktivieren (z.B. 3 s) — Roboter muss STANDING sein:
ros2 param set /gait_node comms_loss_sitdown_timeout 3.0

# 2) GENAU EINEN cmd_vel senden (setzt "zuletzt empfangen"-Zeit), dann NICHTS mehr:
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0}}'

# 3) ~3 s warten, NICHTS senden. Erwartet:
#    - gait-Konsole: WARN "comms-loss: no /cmd_vel for ... auto sit-down (Rest)"
#    - Roboter setzt sich hin → SAT (bestromt, Beine in Spawn-Pose hoch).
#    - Wieder hochholen:
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}

# 4) Fail-safe wieder ausschalten (Normalbetrieb):
ros2 param set /gait_node comms_loss_sitdown_timeout 0.0
```

### 1.9 End-to-End: geradeaus laufen → anhalten → hinsetzen

> Voraussetzung: Roboter im STANDING (nach 1.2). `linear.x 0.03 m/s` liegt klar unter
> `linear_max` (≈0.089) → kein Clamp. Stoppen = cmd_vel-Pub beenden (Ctrl-C); nach
> `cmd_vel_timeout` (0.5 s) ohne neue cmd_vel geht die Engine STOPPING → STANDING.

```bash
# 1) GERADEAUS LAUFEN (vorwärts, 0.03 m/s) — Terminal C, läuft dauerhaft mit -r 10:
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
#    Erwartet: Tripod-Gang vorwärts. (Drehen: angular.z; seitwärts: linear.y.)

# 2) ANHALTEN: in Terminal C Ctrl-C (cmd_vel verstummt).
#    Erwartet: sauberer Stopp → STOPPING → STANDING (innerhalb ~1 s).
#    Optional explizit 0 senden statt Ctrl-C:
#      ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0}}'

# 3) HINSETZEN (Rest) — erst wenn wieder STANDING:
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}
#    Erwartet: Füße raus → Körper auf den Bauch → Beine hoch in Spawn-Pose → SAT.

# 4) Wieder aufstehen (zurück zu STANDING, z.B. um erneut zu laufen):
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
```

> **Hinweis:** `/hexapod_sit_down` wird nur im STANDING angenommen. Wenn du Schritt 3
> direkt während des Laufens (WALKING) aufrufst, kommt `success=False` — erst anhalten
> (Schritt 2), dann hinsetzen.

---

## 2. HW aufgebockt → Boden (B1.10) — `use_sim_time:=false`

> **CLAUDE.md §9 Safety:** aufgebockt (Beine frei), Kill-Switch griffbereit, reduzierte
> Geschwindigkeit. Erst aufgebockt das ganze Sit-/Stand-/Shutdown-Spiel, dann Boden.

### 2.1 HW-Stack starten

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
# Zweites Terminal: Gait mit use_sim_time:=false (Memory: sim_time-Default blockt HW)
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=false
```

### 2.2 Aufgebockt: Hinsetzen + Aufstehen (wie 1.4/1.5)

```bash
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}
# Beobachten: smooth, kein Servo-Freeze (IKError-Log?), kein Watchdog-Trip.
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}
```

### 2.3 Aufgebockt: Shutdown mit echtem Relay

```bash
ros2 service call /hexapod_shutdown std_srvs/srv/Trigger {}
# Erwartet: hinsetzen → SAT → Relay öffnet (Servos werden schlaff, KEIN aktiver Ruck).
# Status-Bit prüfen (Relay sollte AUS sein). stand_up → abgelehnt (latched).

# --- WIEDERINBETRIEBNAHME nach Shutdown (terminal/latched) ----------------
# Der Shutdown ist bewusst terminal: das Node-Flag _shutdown_latched=True sperrt
# /hexapod_stand_up, damit niemand mit stromlosen Servos ein Aufstehen kommandiert.
# Das Flag wird NUR durch einen Neustart des gait_node zurückgesetzt (Reinit →
# Latch False → Boot-Ramp/Auto-Standup läuft wieder kontrolliert an). Ablauf:
#
#   1) Relay wieder schließen (Servos bekommen Strom). AUFGEBOCKT lassen!
ros2 service call /hexapod_relay_set std_srvs/srv/SetBool '{data: true}'
#   2) gait_node neu starten = im gait-Terminal (das mit gait.launch.py) Ctrl-C,
#      dann denselben gait.launch.py-Befehl aus 2.1 erneut ausführen. Beim Start
#      liest der Node die aktuelle Pose und fährt das Auto-Aufstehen kontrolliert.
#      (real.launch.py / Sim-Stack müssen NICHT neu gestartet werden — nur gait.)
# --------------------------------------------------------------------------
```

### 2.4 Boden (erst nach erfolgreichem aufgebockt-Test)

- Roboter steht am Boden → `/hexapod_sit_down` → muss kontrolliert, ohne Kippen sitzen.
- `/hexapod_stand_up` → kontrolliert hoch.
- `/hexapod_shutdown` → sitzt, dann Relay aus → bleibt sicher liegen (kein Fallen).

---

## 3. Was als „fertig" gilt (B1.9 / B1.10)

- **B1.9 SIM:** 1.4–1.8 alle wie erwartet, kein Freeze/Kippen, Services + Latch + Comms-Loss korrekt.
- **B1.10 HW:** 2.2/2.3 aufgebockt sauber, dann 2.4 Boden sicher (hinsetzen + aufstehen + shutdown).
