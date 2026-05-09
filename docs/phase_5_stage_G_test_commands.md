# Phase 5 Stufe G — Test-Befehle

Live-Verifikation des **vollständigen Tripod-Gaits per `/cmd_vel`** —
**Phase-5-Done-Kriterien 2, 3, 4, 5**. Roboter läuft sichtbar vorwärts,
stoppt bei `cmd_vel.linear.x = 0` sauber, Tripod-Sequenz erkennbar,
kein Wegrutschen.

> Sim-Output nach `/tmp/sim.log`. Memory-Eintrag
> `feedback_interactive_stage_test_doc.md`.

> **Zeitschätzung:** 15–25 min für die Standard-Verifikation. Etwas
> mehr Aufwand als Stufe F, weil mehrere DK-Tests + Demo-Mode + cmd_vel-
> Pubs.

> **Voraussetzungen:**
> - Stufe F vollständig grün (Tripod statisch verifiziert).
> - Sim/JTC/Bringup aus Phase 4 funktioniert.
> - Stand-Pose-Default body_height=-0.052 in stand.launch.py.

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

### Vollständiges Sim-Cleanup-Snippet

> ⚠️ **Wichtig:** wie immer vor jedem Test-Lauf voll cleanen. Stale
> `gait_node`/`stand_node`/`foot_contact_publisher`-Prozesse aus
> früheren Sessions hängen sonst als Multi-Publisher auf den selben
> Topics herum.

```bash
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

# Verify nichts mehr läuft:
ps aux | grep -E "(foot_contact|stand_node|gait_node|ros2|gz|hexapod)" | grep -v grep
```

---

## Schritt 1 — Sim mit Foot-Contact starten (Terminal 1)

```bash
cd ~/hexapod_ws
source install/setup.bash

# Cleanup-Snippet von oben einmal ausführen, dann:
ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=true > /tmp/sim.log 2>&1 &
sleep 12
```

**Verify:**

```bash
ros2 control list_controllers
```

**Erwartet:** `joint_state_broadcaster` + 6× `leg_<n>_controller` alle
mit `active`.

---

## Schritt 2 — Stand-Pose anfahren (Terminal 2)

```bash
cd ~/hexapod_ws
source install/setup.bash

ros2 launch hexapod_gait stand.launch.py
sleep 6
```

**Verify visuell:** alle 6 Foot-Kugeln auf dem Boden, Roboter stabil
in Stand-Pose mit body_height=-0.052.

---

## Schritt 3 — gait_node starten (Terminal 2)

> **Wichtig:** Default `default_linear_x:=0.0` → kein cmd_vel-Fallback,
> Engine bleibt STANDING bis externe cmd_vel kommt.

```bash
ros2 launch hexapod_gait gait.launch.py
```

**Erwartet — Init-Log:**

```
gait_node init: pattern=tripod, step_height=0.030 m, cycle_time=2.00 s,
                body_height=-0.052 m, step_length_max=0.050 m
                (linear_max=0.050 m/s), default_linear_x=0.000 m/s,
                cmd_vel_timeout=0.50 s, tick_rate=50 Hz
```

**Erwartet visuell:** Roboter steht still — Engine ist STANDING, weil
keine cmd_vel + default_linear_x=0.

---

## Schritt 4 — DK 2: Vorwärtslauf via cmd_vel (Terminal 3)

```bash
cd ~/hexapod_ws
source install/setup.bash

# Position vor Start sampeln:
echo "=== Body-Pose VOR Walk ==="
gz model -m hexapod -p

# cmd_vel pumpen mit 10 Hz für 5 s (= ~5 Cycles bei cycle_time=2):
timeout 5 ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.05, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'

# Position nach Stop sampeln:
echo "=== Body-Pose NACH Walk ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Sobald cmd_vel kommt, startet Tripod-Gait. Roboter
läuft sichtbar **vorwärts** (in +X-Richtung des Sim-Frames).

**DK 2 Akzeptanz-Kriterium:** Body-X-Position muss mindestens **0.10 m**
gewachsen sein in 5 s (theoretisch 0.05 m/s · 5 s = 0.25 m, aber
JTC-Lag und Foot-Schlupf reduzieren das ~50%).

> **Hinweis:** Nach `timeout` ist der cmd_vel-Pub weg → Activity-Timeout
> 0.5 s tritt ein → Engine geht STOPPING → STANDING. Das ist Teil von
> DK 3 (siehe Schritt 5).

---

## Schritt 5 — DK 3: Stopp-Latenz (Terminal 3)

Aus dem vorherigen Schritt sollten wir gerade aus dem `timeout 5` raus
sein. Engine sollte innerhalb 0.5 s + Settling-Time (max 1 s + 0.3 s)
in STANDING sein.

Manueller Hard-Stop-Test mit explizit `cmd_vel.linear.x = 0`:

```bash
# Walk wieder starten, 4 s laufen lassen:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.05}}' &
PUB_PID=$!
sleep 4

# Hard-Stop: einmal cmd_vel = 0 publishen, dann pub killen
ros2 topic pub --once /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.0}}'
kill $PUB_PID 2>/dev/null
sleep 1.5

# Sample Body-Pose 1 s nach Stop:
echo "=== Body-Pose 1.5 s nach Stop ==="
gz model -m hexapod -p
```

**Erwartet visuell:** Roboter stoppt **innerhalb 1.3 s** (= max
swing_duration 1 s + STANCE_SETTLING_TIME 0.3 s). Beine in der Luft
landen sauber, dann alle 6 in Stand-Pose, kein progressives Weiterlaufen.

**DK 3 Akzeptanz-Kriterium:** Body-X-Drift in den 2 s **nach** dem
Stop-Befehl < 5 mm. Wenn gait_node weiterläuft (ohne neue cmd_vel),
muss er in STANDING sein.

> **Bemerkung zu "<0.5 s":** Mit `cycle_time=2.0` ist swing_duration
> 1 s, also Worst-Case-Stopp-Latenz 1.3 s — DK-3-Roadmap-Wert
> "<0.5 s" formal nicht erfüllt. Test mit `cycle_time:=1.0` (Schritt
> 7) erreicht <0.8 s.

---

## Schritt 6 — DK 4 + DK 5: Tripod-Sequenz + Foot-Contact + Wegrutsch-Check

Walk wieder starten und während dessen Foot-Contact-Toggle messen:

```bash
# Walk starten, im Hintergrund pumpen:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.05}}' &
PUB_PID=$!
sleep 1

# 8 s Foot-Contact-Sample = 4 Cycles:
timeout 8 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool > /tmp/leg1.log 2>&1
echo "=== leg 1 (Gruppe A): ==="
echo "true count:" ; grep -c "data: true" /tmp/leg1.log
echo "false count:" ; grep -c "data: false" /tmp/leg1.log

timeout 8 ros2 topic echo /leg_2/foot_contact std_msgs/msg/Bool > /tmp/leg2.log 2>&1
echo "=== leg 2 (Gruppe B, sollte invers zu leg 1): ==="
echo "true count:" ; grep -c "data: true" /tmp/leg2.log
echo "false count:" ; grep -c "data: false" /tmp/leg2.log

# Body-Pose während Walk samplen:
echo "=== Body-Pose während Walk (10 s) ==="
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "Sample $i:"
  gz model -m hexapod -p
  sleep 1
done

# Walk stoppen:
kill $PUB_PID 2>/dev/null
sleep 1.5
```

**DK 4 Erwartet — Tripod-Sequenz:**
- leg 1 (Gruppe A): ähnliche Toggle-Verteilung wie in Stufe F
  (~165/175 true/false in 8 s).
- leg 2 (Gruppe B): invers — wenn leg 1 false, leg 2 true.
- Beide haben `true count > 0`.

**DK 5 Erwartet — kein Wegrutschen:**
Aus den 10 Body-Pose-Samples (10 s Vortrieb bei 0.05 m/s, theoretisch
0.5 m Strecke):
- **x bewegt sich vorwärts:** Sample 10 - Sample 1 ≥ 0.10 m (50% von
  theoretisch 0.5 m, JTC-Lag-Verlust akzeptiert).
- **y-Drift klein:** |y_10 - y_1| < 0.05 m (kein systematisches
  Seitwärtsdriften).
- **Yaw-Drift klein:** |Yaw_10 - Yaw_1| < 0.087 rad (= 5°). Kein
  progressives Drehen.
- **z stationär:** im 0.05–0.06 m-Bereich (Tripod-Cycle-Wackel).

> **Hinweis:** Wenn x-Bewegung deutlich kleiner als 0.10 m ist, prüfen:
> 1. cmd_vel kommt überhaupt an (`ros2 topic echo /cmd_vel`)?
> 2. linear.x wird nicht geclamped (Init-Log zeigt linear_max=0.05).
> 3. Foot-Schlupf wegen zu wenig Reibung — physics-Materials in URDF prüfen.

---

## Schritt 7 — DK 3 strikt: <0.5 s mit cycle_time=1.0 (Terminal 2 + 3)

Beende aktuellen `gait_node` und starte neu mit kürzerem Cycle:

```bash
# Terminal 2: Ctrl+C
# Terminal 2 neu starten:
ros2 launch hexapod_gait gait.launch.py cycle_time:=1.0
```

**Erwartet — Init-Log:**

```
gait_node init: pattern=tripod, step_height=0.030 m, cycle_time=1.00 s,
                ..., linear_max=0.100 m/s, ...
```

> Mit `cycle_time=1.0`: stance_duration=0.5 s → linear_max =
> step_length_max / 0.5 = 0.05/0.5 = 0.10 m/s. swing_duration=0.5 s →
> Worst-Case-Stopp-Latenz 0.5 + 0.3 = 0.8 s. Immer noch nicht <0.5 s
> strikt aber näher dran.

In Terminal 3:

```bash
# 3 s Walk:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.05}}' &
PUB_PID=$!
sleep 3

# Hard-Stop:
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{linear: {x: 0.0}}'
kill $PUB_PID 2>/dev/null

# 0.5 s + 0.3 s = 0.8 s warten dann pose check:
sleep 0.8
echo "=== Body-Pose 0.8 s nach Stop (cycle_time=1) ==="
gz model -m hexapod -p
```

**Erwartet:** Roboter steht (oder ist innerhalb der nächsten ~50ms
da). Body-x-Position bleibt nach 0.8 s stabil.

---

## Schritt 8 — Demo-Mode (default_linear_x)

Beende gait_node und starte mit `default_linear_x` direkt:

```bash
# Terminal 2: Ctrl+C, dann:
ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05
```

**Erwartet visuell:** Roboter läuft sofort nach Launch vorwärts ohne
externen cmd_vel-Pub. State-Log direkt nach Init: WALKING.

```bash
# Terminal 3: keine cmd_vel-Pubs nötig, einfach Position checken
sleep 6
gz model -m hexapod -p
```

**Erwartet:** Body-X gewachsen.

Zum Stoppen einfach `Ctrl+C` in Terminal 2 (oder cmd_vel-Pub mit 0).

---

## Schritt 9 — Limits-Test: linear.x über Max (Terminal 3)

```bash
# Terminal 2: Ctrl+C, dann zurück zu default cycle_time:
ros2 launch hexapod_gait gait.launch.py
```

In Terminal 3:

```bash
# linear.x = 0.20 m/s (4× über Max)
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.20}}' &
PUB_PID=$!
sleep 3
kill $PUB_PID
sleep 1.5
```

**Erwartet — Log in Terminal 2:** alle ~2 s eine Warning:

```
[gait_node]: cmd_vel clamped: input (0.200, 0.000) > linear_max 0.050 m/s
```

Roboter läuft trotzdem, aber nur mit Max-Geschwindigkeit (0.05 m/s).

---

## Schritt 10 — Aufräumen

```bash
# Terminal 2: Ctrl+C → gait_node beendet
# Terminal 1:
kill %1   # oder das vollständige Cleanup-Snippet von oben
```

---

## Optionale Variationen

### Längere Schritte (höher step_length_max)

```bash
ros2 launch hexapod_gait gait.launch.py step_length_max:=0.08
```

→ linear_max steigt auf 0.08 m/s. Roboter kann schneller laufen.
Aber: bei zu großem step_length droht Foot-Schlupf, weil JTC die
großen Bewegungen nicht in stance_duration konvergiert.

### Höhere Schwung-Höhe

```bash
ros2 launch hexapod_gait gait.launch.py step_height:=0.06
```

6 cm Schwung — sichtbarer für Demo / Video.

### Rückwärts (linear.x negativ)

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: -0.04}}'
```

Roboter läuft rückwärts. Selbe Mechanik, Vorzeichen umgedreht.

### IK-Out-of-Reach-Test

```bash
ros2 launch hexapod_gait gait.launch.py step_length_max:=0.5 step_height:=0.5
```

50 cm Schritt + 50 cm Schwung → IKError pro Tick, Engine catched
und keine Pubs für betroffenen Tick (Stand-Pose wird via JTC gehalten).
Erwartet: massive `IKError`-Logs, Roboter bleibt aber stabil stehen.

Mit `Ctrl+C` beenden.

---

## Stolpersteine zu erwarten

(Mehrere aus Stufen E + F übertragen — falls sie wieder auftreten.)

1. **Stale Prozesse** verwirren Multi-Publisher-Topology → Cleanup-
   Snippet jedes Mal komplett laufen lassen.

2. **Body-Drift in Y oder Yaw** beim Vorwärtslauf — wenn der Roboter
   "schräg" läuft statt geradeaus:
   - Mount-Yaw in URDF prüfen (LegConfig in
     [hexapod_kinematics/config.py](../src/hexapod_kinematics/hexapod_kinematics/config.py)).
   - rotate_z-Vorzeichen in `_compute_step_vec_leg` prüfen (Stufe-G-
     Implementations-Bug-Fall: bei falschem Sign läuft er
     rückwärts/seitlich).

3. **Roboter rührt sich nicht trotz cmd_vel** — meist weil Activity-
   Timeout zwischen den Pubs greift. Lösung: `ros2 topic pub --rate 10`
   (kontinuierlich) statt `--once`. Oder `cmd_vel_timeout:=2.0` für
   den Test hochsetzen.

4. **Body-Schock beim Stopp** — wenn Engine in den ersten Stopp-Tick
   harten Sprung macht: STANCE_SETTLING_TIME aus
   [gait_engine.py](../src/hexapod_gait/hexapod_gait/gait_engine.py)
   anpassen (höher = weicher, aber langsamer).

5. **DK-3-Latenz nicht erfüllt** — Worst-Case ist swing_duration +
   STANCE_SETTLING_TIME. Mit cycle_time=2: 1.3 s. Mit cycle_time=1:
   0.8 s. Strikt <0.5 s wäre cycle_time=0.5 s nötig — JTC würde dann
   aber kaum konvergieren.

6. **Foot-Schlupf bei großer linear.x** — wenn Body-Bewegung schneller
   als JTC-Konvergenz: Foot rutscht über Boden. Sichtbare DK-5-
   Verletzung. Lösung: kleineres step_length_max oder längeres
   cycle_time.
