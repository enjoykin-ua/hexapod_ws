# Phase 5 Stufe H — Test-Befehle

Live-Verifikation des **omnidirektionalen Tripod-Gaits**: `linear.x` +
`linear.y` + `angular.z` gleichzeitig. Roboter dreht, läuft seitwärts,
und kann Kurven fahren.

> Sim-Output nach `/tmp/sim.log`. Memory-Eintrag
> `feedback_interactive_stage_test_doc.md`.

> **Zeitschätzung:** 15–20 min für Standard-Verifikation. Drei
> separate Bewegungs-Modi + Kombi-Test + optionaler Demo-Mode.

> **Voraussetzungen:**
> - Stufe G grün (Vorwärtslauf via cmd_vel.linear.x verifiziert).
> - Stand-Pose-Default body_height=-0.052.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source install/setup.bash
```

Falls Pakete neu gebaut werden müssen:

```bash
colcon build --packages-select hexapod_kinematics hexapod_sensors hexapod_gait hexapod_description hexapod_bringup
source install/setup.bash
```

### Cleanup-Snippet (mit Stufe-G-Lehre: pkill alte topic-pubs!)

```bash
pkill -9 -f "ros2 topic pub" 2>/dev/null
pkill -9 -f "ros2" 2>/dev/null
pkill -9 -f "gz" 2>/dev/null
pkill -9 -f "ruby" 2>/dev/null
pkill -9 -f "parameter_bridge" 2>/dev/null
pkill -9 -f "robot_state_publisher" 2>/dev/null
pkill -9 -f "controller_manager" 2>/dev/null
pkill -9 -f "foot_contact_publisher" 2>/dev/null
pkill -9 -f "stand_node" 2>/dev/null
pkill -9 -f "gait_node" 2>/dev/null
sleep 4

ps aux | grep -E "(foot_contact|stand_node|gait_node|ros2|gz|hexapod)" | grep -v grep
```

> **Wichtig:** der `pkill -f "ros2 topic pub"` ist neu — Stufe-G-Live-
> Test hatte Stale-Pubs mit `linear.x=0.350` aus früheren Manuell-Tests.

---

## Schritt 1 — Sim mit Foot-Contact starten (Terminal 1)

```bash
cd ~/hexapod_ws
source install/setup.bash

# Cleanup-Snippet von oben einmal ausführen, dann:
ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=true > /tmp/sim.log 2>&1 &
sleep 12

ros2 control list_controllers
```

**Erwartet:** alle 7 Controller `active`.

---

## Schritt 2 — Stand-Pose anfahren (Terminal 2)

```bash
cd ~/hexapod_ws
source install/setup.bash

ros2 launch hexapod_gait stand.launch.py
sleep 6
```

---

## Schritt 3 — gait_node starten (Terminal 2)

```bash
ros2 launch hexapod_gait gait.launch.py
```

**Erwartet — Init-Log:**

```
gait_node init: pattern=tripod, ..., 
                step_length_max=0.050 m (linear_max=0.050 m/s),
                defaults=(linear_x=0.000, linear_y=0.000, angular_z=0.000),
                cmd_vel_timeout=0.50 s, ...
```

Default: alle drei `default_*` auf 0 → STANDING.

---

## Schritt 4 — DK-Stufe-H-1: Drehen (Terminal 3)

### Drehung gegen den Uhrzeigersinn (positive omega, ROS-konvention)

```bash
cd ~/hexapod_ws
source install/setup.bash

# Position vor Drehung sampeln:
echo "=== Body-Pose VOR Drehung CCW ==="
gz model -m hexapod -p

# omega = +0.3 rad/s für 6 s (~ 1 vollständige Drehung wäre 2π/0.3 ≈ 21 s,
# 6 s ergibt ~17% Drehung = ~62°):
timeout 6 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{angular: {z: 0.3}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Drehung-Stop ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Roboter steht "auf der Stelle" und dreht sich
gegen den Uhrzeigersinn (von oben gesehen). Body-x/y bleiben ~konstant
(Schwankung <50 mm), Yaw wandert.

**Akzeptanz-Kriterium:**
- Yaw-Differenz Sample 2 - Sample 1 ≈ +0.3 rad/s · 6 s = +1.8 rad
  (≈ 103°). **Tolerance ±50%** (Foot-Slip in Sim) → erwartet
  Yaw-Drift in [+0.9, +2.7] rad.
- |x_2 - x_1| < 0.10 m und |y_2 - y_1| < 0.10 m (Body bleibt ~auf der
  Stelle).

### Drehung im Uhrzeigersinn (negative omega)

```bash
echo "=== Body-Pose VOR Drehung CW ==="
gz model -m hexapod -p

timeout 6 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{angular: {z: -0.3}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Drehung-CW-Stop ==="
gz model -m hexapod -p
```

**Erwartet:** Yaw bewegt sich diesmal in -X-Richtung (negativ).

---

## Schritt 5 — DK-Stufe-H-2: Seitwärtslaufen (Terminal 3)

### Seitwärts +Y (links in Body-Frame, Standard-ROS-Konvention)

```bash
echo "=== Body-Pose VOR Seitwärts +Y ==="
gz model -m hexapod -p

timeout 6 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {y: 0.05}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Seitwärts-Stop ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Roboter läuft seitlich nach **links** (in
seiner eigenen +Y-Richtung).

**Akzeptanz-Kriterium:**
- y_2 - y_1 ≈ +0.05 m/s · 6 s = +0.30 m. **Tolerance ±50%** → erwartet
  in [+0.15, +0.45 m].
- |x_2 - x_1| < 0.05 m (kein systematisches Vorwärts-Driften).
- |Yaw_2 - Yaw_1| < 0.087 rad (5°).

### Seitwärts -Y (rechts)

```bash
echo "=== Body-Pose VOR Seitwärts -Y ==="
gz model -m hexapod -p

timeout 6 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {y: -0.05}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Seitwärts-Rechts-Stop ==="
gz model -m hexapod -p
```

**Erwartet:** y_2 - y_1 ≈ -0.30 m, x stationär.

---

## Schritt 6 — Kombi-Motion: Vorwärts + Drehen = Bogen (Terminal 3)

```bash
echo "=== Body-Pose VOR Bogen ==="
gz model -m hexapod -p

# Linear.x = 0.03, omega = 0.2 → Bogen-Radius = 0.03/0.2 = 0.15 m
timeout 8 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.03}, angular: {z: 0.2}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Bogen-Stop ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Roboter läuft auf einem Bogen — gleichzeitig
vorwärts und gegen den Uhrzeigersinn drehend. Theoretischer Radius
≈ 0.15 m (R = v/ω).

**Akzeptanz-Kriterium:**
- Sowohl x als auch y haben sich verändert (nicht nur eine Achse).
- Yaw hat sich gedreht: erwartet 0.2 · 8 = 1.6 rad (≈ 92°), tolerance
  ±50%.
- Roboter ist nicht "geradeaus" gelaufen (das würde Bogen-Implementation
  brechen).

---

## Schritt 7 — Kombi-Motion: alle drei zusammen (Terminal 3)

Gleichzeitig vorwärts, seitwärts, drehen. Die proportionale Clamping-
Strategie tritt hier wahrscheinlich in Aktion.

```bash
echo "=== Body-Pose VOR Kombi ==="
gz model -m hexapod -p

# Alle drei: vx=0.04, vy=0.02, omega=0.15
# Max-leg-speed ≈ 0.04 + 0.15·0.109 + |vy|-Beitrag → wahrscheinlich >0.05
timeout 6 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.04, y: 0.02}, angular: {z: 0.15}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Kombi-Stop ==="
gz model -m hexapod -p
```

**Erwartet — Log in Terminal 2:** Wahrscheinlich:

```
[gait_node]: cmd_vel clamped: input (vx=0.040, vy=0.020, omega=0.150) > 
             max-leg-speed 0.050 m/s
```

**Erwartet visuell:** Roboter macht eine schräge Schraubenkurve, alle
drei Bewegungen anteilig. Wenn clamped → entsprechend langsamer, aber
**gleicher Bogen-Verlauf**.

---

## Schritt 8 — Rückwärts (linear.x negativ)

Vorwärts wurde in Stufe G durchgetestet. Hier verifizieren wir, dass
**negative `linear.x`** sauber rückwärts laufen lässt — Symmetrie-Check
der Trajektorien-Mathematik.

```bash
echo "=== Body-Pose VOR Rückwärts ==="
gz model -m hexapod -p

# Negative linear.x → Roboter sollte rückwärts laufen:
timeout 5 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: -0.05}}'

sleep 1.5

echo "=== Body-Pose 1.5 s nach Rückwärts-Stop ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Roboter läuft sichtbar **rückwärts** (in -X
des Body-Frames). Tripod-Sequenz wie bei Vorwärts, nur Schritt-Vektor
gespiegelt.

**Akzeptanz-Kriterium:**
- x_2 - x_1 ≈ -0.05 m/s · 5 s = -0.25 m. **Tolerance ±50%** → erwartet
  in [-0.05, -0.40 m] (negativer Wert).
- |y_2 - y_1| < 0.05 m (kein systematisches Driften).
- |Yaw_2 - Yaw_1| < 0.087 rad (5°).

**Backward-Compat-Stufe-G** ist implizit erfüllt: Schritt 4 (CCW
Drehen mit `angular.z=0.3`), Schritt 5 (Seitwärts mit `linear.y=0.05`)
und alle anderen Stufe-H-Schritte basieren auf der gleichen Engine —
wenn die durchlaufen, dann auch reine `linear.x = +0.05` (= Stufe G).

---

## Schritt 9 — Demo-Mode mit angular.z (Terminal 2 + 3)

Beende gait_node und starte mit `default_angular_z`:

```bash
# Terminal 2: Ctrl+C, dann:
ros2 launch hexapod_gait gait.launch.py default_angular_z:=0.2
```

**Erwartet:** Roboter dreht sich sofort nach Launch ohne externe
cmd_vel. Body-x/y stationär, Yaw wandert.

```bash
# Terminal 3: einfach beobachten, oder pose-checken:
sleep 5
gz model -m hexapod -p
```

**Erwartet:** Yaw ist gedreht. x/y im Rahmen.

Beenden mit `Ctrl+C` in Terminal 2.

---

## Schritt 10 — Demo-Mode mit Kombi (Terminal 2)

```bash
# Terminal 2:
ros2 launch hexapod_gait gait.launch.py \
  default_linear_x:=0.03 default_angular_z:=0.15
```

**Erwartet:** Roboter läuft sofort einen Bogen. Demo-tauglich für
Video / Vorführung.

---

## Schritt 11 — Aufräumen

```bash
# Terminal 2: Ctrl+C
# Terminal 1: kill %1
```

---

## Optionale Variationen

### Schnellere Drehung mit größerem step_length_max

```bash
ros2 launch hexapod_gait gait.launch.py step_length_max:=0.08
```

→ omega_max ≈ 0.08 / (0.109 · stance_duration) → bei cycle_time=2 ist
stance_duration=1, also omega_max ≈ 0.73 rad/s.

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.6}}'
```

### Diagonal-Walk (45°-Linie)

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.035, y: 0.035}}'
```

→ Bewegungs-Vektor (0.035, 0.035) hat Magnitude 0.0495 < 0.05 → kein
Clamp. Roboter läuft 45° vorwärts-links.

### Rückwärts dreht andersrum (rückwärts-bogen)

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: -0.03}, angular: {z: 0.2}}'
```

→ Roboter läuft rückwärts mit gleichzeitiger CCW-Drehung — eine
"S-Form".

---

## Stolpersteine zu erwarten

(Aus Stufen E–G übertragen + Stufe-H-spezifische.)

1. **Stale `ros2 topic pub`-Prozesse** (Stufe-G-Lehre) — der `pkill -f
   "ros2 topic pub"` im Cleanup ist explizit dafür da.

2. **Drehung "wackelt" sichtbar** — bei pure rotation hat jedes Bein
   eine andere step_vec-Richtung (tangential). Das ergibt ein
   asymmetrisches Tripod-Pattern (Beine schieben in unterschiedliche
   Richtungen). Body kann dabei minimal "eiern". Bei moderate omega
   (≤0.3 rad/s) sollte das aber nicht progressiv wegkippen.

3. **Diagonale Bewegung wird gerade gelaufen** — wenn `linear.y` keine
   sichtbare Wirkung hat: Engine-Code checken auf vy-Plumbing.
   `cmd_vel`-Topic-Echo prüfen ob y-Wert ankommt.

4. **Pure rotation läuft trotzdem voran** — Bug-Hint dass omega-Beitrag
   in `_compute_step_vec_leg` mit linear-Beitrag verrechnet wird (statt
   addiert). Sollte sich nicht passieren mit korrekter Implementation.

5. **Clamping triggert immer** — wenn auch mit kleinen cmd_vel-Werten
   immer Warnings kommen: `step_length_max` hochsetzen oder `cycle_time`
   kürzer (verlängert linear_max).

6. **Yaw-Drift wie in Stufe G** — bei pure `linear.x` weiterhin
   borderline 1-2°/m. Das ist Stufe-G-Limitation, kein Stufe-H-Bug.
