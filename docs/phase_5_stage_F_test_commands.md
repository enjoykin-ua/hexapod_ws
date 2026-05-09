# Phase 5 Stufe F — Test-Befehle

Live-Verifikation des **statischen Tripod-Patterns** mit STANDING↔WALKING-
State-Machine. Tripod-Gruppen A {1,3,5} und B {2,4,6} schwingen
abwechselnd mit Phasen-Offset 0.5, **kein Vortrieb** (kommt erst in
Stufe G). Foot-Contact-Sensoren aus Stufe D zeigen Stütz-Tripod live.

> Sim-Output nach `/tmp/sim.log`. Memory-Eintrag
> `feedback_interactive_stage_test_doc.md`.

> **Zeitschätzung:** 10–15 min für die Standard-Verifikation, abhängig
> davon wie viele Tests man durchläuft. Sequenz unten ist die in der
> Live-Session zu validierende Reihenfolge.

> **Voraussetzung:** Stufe E vollständig grün (Single-Leg-Schwung
> verifiziert), Sim/JTC/Bringup aus Phase 4 funktioniert.

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

> ⚠️ **Wichtig:** vor jedem Test-Lauf voll cleanen. Stufe-E-Stolperstein
> war stale `gait_node`-Prozesse als Multi-Publisher. Gleiche Disziplin
> hier.

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

# Verify nichts mehr läuft (sollte leer sein bzw. nur Sys-Prozesse zeigen):
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

Warten bis Gazebo-Fenster offen ist und Roboter auf dem Bauch liegt.

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
# warten bis "process has finished cleanly" loggt (~5 s)
sleep 6
```

**Wichtig:** stand.launch.py nutzt jetzt `body_height=-0.052` (Stufe-F-
Default mit globaler Penetration). Phase-4 / Stufe-C-Verhalten nicht
mehr 1:1 — Roboter steht 5 mm "tiefer". Füße werden gegen den Boden
gedrückt, da JTC-Tracking-Lag den realen Foot etwa auf -0.047 hält.

**Verify visuell:** alle 6 Foot-Kugeln auf dem Boden, Roboter stabil
in Stand-Pose. Body steht ~5 mm tiefer als in Stufe E (kaum sichtbar,
~5 % der Stand-Höhe).

**Verify Foot-Contact** (eine kurze Stichprobe):

```bash
timeout 3 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool > /tmp/leg1_stand.log 2>&1
echo "stand leg 1 — true count:"
grep -c "data: true" /tmp/leg1_stand.log
echo "stand leg 1 — false count:"
grep -c "data: false" /tmp/leg1_stand.log
```

**Erwartet:** `true count >> false count` (Stand mit globalem 5 mm
Penetration → fast permanent Kontakt).

---

## Schritt 3 — gait_node starten in STANDING (Terminal 2)

> **Wichtig:** Default `enable_walk:=false` → STANDING. Roboter bewegt
> sich nicht, alle 6 Beine bleiben in Stand-Pose. Erst nach explizitem
> Toggle (Schritt 4) startet der Tripod.

```bash
ros2 launch hexapod_gait gait.launch.py
```

**Erwartet — Init-Log:**

```
gait_node init: pattern=tripod, enable_walk=False,
                step_height=0.030 m, cycle_time=2.00 s,
                body_height=-0.052 m,
                tick_rate=50 Hz, time_from_start=40.0 ms
```

**Erwartet visuell:** Roboter steht still (kein Schwung). Stütz-Pose
gehalten. `gait_node` publisht 50 Hz Stand-Pose-Goals an alle 6 JTCs.

`gait_node` läuft kontinuierlich. Beenden mit `Ctrl+C` in Terminal 2.

---

## Schritt 4 — STANDING → WALKING togglen (Terminal 3)

```bash
cd ~/hexapod_ws
source install/setup.bash

ros2 param set /gait_node enable_walk true
```

**Erwartet — Log in Terminal 2:**

```
[gait_node]: enable_walk -> True (WALKING)
```

**Erwartet visuell:** sofort startet Tripod-Gait.
- Gruppe A {Bein 1, 3, 5} schwingt 1 s lang gemeinsam (1 cm im Apex,
  ~3 cm step_height).
- Gleichzeitig stützt Gruppe B {Bein 2, 4, 6}.
- Nach 1 s Wechsel: Gruppe B schwingt, Gruppe A stützt.
- Roboter steht stabil auf 3 Beinen während des Schwungs (kein
  Wegrutschen, kein progressives Kippen).

---

## Schritt 5 — Numerische Phasen-Sync-Verifikation (Terminal 3)

```bash
echo "=== /joint_states snapshot — Tripod sollte sichtbar sein ==="
ros2 topic echo /joint_states sensor_msgs/msg/JointState --once
```

**Erwartet (mehrfach `--once` ausführen, um Phasen zu sehen):**

Bei der **gleichen Sample-Zeit**:
- `leg_1_femur_joint`, `leg_3_femur_joint`, `leg_5_femur_joint`:
  **identische Werte** (alle 3 in gleicher Phase, da Offset 0).
- `leg_2_femur_joint`, `leg_4_femur_joint`, `leg_6_femur_joint`:
  **identische Werte untereinander, aber unterschiedlich von 1/3/5**
  (Offset 0.5).
- Wenn Gruppe A im Apex ist: `leg_1/3/5_femur_joint` ≈ `-0.67`,
  `leg_2/4/6_femur_joint` ≈ `-0.47` (Stance bei body_height=-0.052).
- Bei umgekehrter Phase entsprechend.

> **Warum dieselben Werte je Gruppe:** Engine setzt für alle Beine
> dieselbe Stand-Pose-Geometrie (`radial_distance=0.27`, body-frame-Y=0)
> ein. Da auch der mount_yaw symmetrisch wirkt und IK-Werte im Bein-
> Frame berechnet werden, sind Gruppe-A-Beine identisch (kein Vortrieb,
> kein step_length).

---

## Schritt 6 — Foot-Contact-Toggle live verifizieren (Terminal 3)

Tripod-Gait sollte zwei Gruppen toggeln sehen lassen — eine Gruppe
zeigt Kontakt während die andere in der Luft ist.

```bash
# 8 s sample = 4 Cycles à 2 s, sollte ~50/50 toggle zeigen:
timeout 8 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool > /tmp/leg1.log 2>&1
echo "=== leg 1 (Gruppe A): ==="
echo "true count:"
grep -c "data: true" /tmp/leg1.log
echo "false count:"
grep -c "data: false" /tmp/leg1.log

timeout 8 ros2 topic echo /leg_2/foot_contact std_msgs/msg/Bool > /tmp/leg2.log 2>&1
echo "=== leg 2 (Gruppe B, sollte zu leg 1 invers toggeln): ==="
echo "true count:"
grep -c "data: true" /tmp/leg2.log
echo "false count:"
grep -c "data: false" /tmp/leg2.log

# Quer-Check: dieselbe Phase wie 1
timeout 8 ros2 topic echo /leg_3/foot_contact std_msgs/msg/Bool > /tmp/leg3.log 2>&1
echo "=== leg 3 (Gruppe A, sollte mit leg 1 sync sein): ==="
echo "true count:"
grep -c "data: true" /tmp/leg3.log
```

**Erwartet:**
- **leg 1, leg 3, leg 5 (Gruppe A):** ähnliche Verteilung (z. B. ~120
  true / ~210 false in 8 s, wie Stufe E mit Cycle 2 s und 1 s Stance).
  Genaue Anzahl schwankt durch JTC-Konvergenz pro Stance-Phase.
- **leg 2, leg 4, leg 6 (Gruppe B):** **invertierte** Verteilung — wenn
  leg 1 gerade `false` zeigt, sollte leg 2 `true` zeigen, und vice
  versa. Insgesamt etwa wie Gruppe A (auch ~50/50).
- **Wichtig:** alle 6 Beine müssen `true count > 0` haben (Done-
  Kriterium: Stütz-Tripod erreicht Boden).

> **Hinweis:** Anders als Stufe E gibt's hier KEIN klares "ein Stütz-
> Bein hat ständig Kontakt" — alle 6 wechseln. Das ist das Tripod-
> Verhalten.

### Wenn `true count` für irgendein Bein 0 ist

(Stufe-F-spezifischer Bug-Fall, falls Penetrations-Wert nicht reicht
oder Body kippt.)

```bash
# 1) Body-Höhe prüfen — sollte konstant ~0.052-0.054 m sein:
gz model -m hexapod -p

# 2) Code-Stand verifizieren — body_height -0.052 muss in installierter
#    gait.launch.py + stand.launch.py stehen:
grep -c "0.052" install/hexapod_gait/share/hexapod_gait/launch/gait.launch.py
grep -c "0.052" install/hexapod_gait/share/hexapod_gait/launch/stand.launch.py

# 3) GaitPattern verifizieren:
grep "phase_offset_per_leg" install/hexapod_gait/lib/python*/site-packages/hexapod_gait/gait_patterns.py | head -2

# 4) Stale Prozesse prüfen:
ps aux | grep -E "(gait_node|foot_contact_publisher)" | grep -v grep

# 5) Wenn 4) mehrere gait_node zeigt → Cleanup-Snippet erneut + Sim
#    neu starten ab Schritt 1.
```

Falls 1) zeigt dass Body z < 0.045 m oder > 0.06 m oszilliert: Body
hebt/senkt sich → Penetrations-Wert anpassen. Globale Empfehlung:
nicht > 5 mm gehen, sonst Vibration im Gait-Cycle.

---

## Schritt 7 — WALKING → STANDING togglen (Terminal 3)

```bash
ros2 param set /gait_node enable_walk false
```

**Erwartet — Log in Terminal 2:**

```
[gait_node]: enable_walk -> False (STANDING)
```

**Erwartet visuell:** Tripod stoppt **innerhalb von ~1 Cycle** (max
2 s, weil JTC noch zur Stand-Pose interpolieren muss von dem aktuellen
Joint-Zustand). Roboter steht still in Stand-Pose, alle 6 Beine am
Boden, Foot-Contact alle `true`.

```bash
sleep 3
echo "=== alle 6 sollten true zeigen nach STANDING ==="
for i in 1 2 3 4 5 6; do
  timeout 2 ros2 topic echo /leg_${i}/foot_contact std_msgs/msg/Bool > /tmp/leg${i}_standing.log 2>&1
  echo "leg ${i} — true count:"
  grep -c "data: true" /tmp/leg${i}_standing.log
done
```

**Erwartet:** alle 6 zeigen `true count >> 0`.

---

## Schritt 8 — Stützphasen-Stabilität (Terminal 3)

Verifizieren, dass der Body während aktiven Tripod-Walks nicht driftet
oder progressiv kippt:

```bash
# Toggle wieder auf WALKING
ros2 param set /gait_node enable_walk true
sleep 2

echo "=== Body-Pose über 10 s = 5 Cycles ==="
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "Sample $i:"
  gz model -m hexapod -p
  sleep 1
done
```

**Erwartet:**
- z bleibt im Bereich ~0.050-0.055 m (kleine Oszillation durch
  Tripod-Wechsel, aber **kein progressives Wegkippen / Senken**).
- y bleibt bei ~0 ± 0.001 m (kein systematisches Kriechen — kein
  Vortrieb in Stufe F, also Body-Position muss stationär bleiben).
- x bleibt stationär (kein Vortrieb).
- RPY: Roll und Pitch oszillieren minimal (~1°), aber zentriert um 0.

**Akzeptanz-Kriterium:** Roboter rutscht weniger als 5 mm in 10 s,
kippt nie über 5° hinaus.

> **Hinweis:** wenn `gz model` mit "Service call to /gazebo/worlds
> timed out" failt, einfach nochmal probieren — DDS-CLI-Race, nichts
> Echtes kaputt.

---

## Schritt 9 — Backward-Compat-Test Stufe E (optional)

Verifiziert dass `gait_pattern:=single_leg_1` weiterhin Stufe-E-
Verhalten reproduziert.

Erst aktuellen gait_node beenden:

```bash
# Terminal 2:
# Ctrl+C
```

Dann Single-Leg-Pattern starten (Terminal 2):

```bash
ros2 launch hexapod_gait gait.launch.py \
  gait_pattern:=single_leg_1 \
  enable_walk:=true \
  cycle_time:=2.0 \
  step_height:=0.06
```

**Erwartet visuell:** wie in Stufe E — Bein 1 schwingt einzeln, andere
5 stehen still. Init-Log zeigt `pattern=single_leg_1`.

```bash
# Foot-Contact-Diagnose:
timeout 8 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool > /tmp/leg1.log 2>&1
grep -c "data: true" /tmp/leg1.log
grep -c "data: false" /tmp/leg1.log
```

**Erwartet:** ähnlich Stufe-E-Werte (~120 true, ~210 false bei
cycle_time=2). Wenn ja → Backward-Compat OK.

---

## Schritt 10 — Aufräumen

Terminal 2: `Ctrl+C` → gait_node beendet sich sauber.

Terminal 1: 

```bash
kill %1   # oder das vollständige Cleanup-Snippet von oben
```

---

## Optionale Variationen

### Schnellerer Tripod (cycle_time=1.0)

```bash
ros2 launch hexapod_gait gait.launch.py \
  enable_walk:=true \
  cycle_time:=1.0 step_height:=0.03
```

0.5 s Swing + 0.5 s Stance. JTC hat weniger Konvergenz-Zeit pro Phase
— Stufe-E-Stance-Penetrations-Lehre gilt: bei zu schnellem Cycle
zeigen Foot-Contact-Sensoren weniger zuverlässig `true`.

### Höherer Schwung (step_height=0.06)

```bash
ros2 launch hexapod_gait gait.launch.py \
  enable_walk:=true \
  cycle_time:=2.0 step_height:=0.06
```

6 cm Schwung-Höhe — sehr deutlich sichtbar, gut für Demo / Video.
Roboter könnte minimal mehr wackeln, weil Schwerpunkt höher pendelt.

### IK-Out-of-Reach-Test

```bash
ros2 launch hexapod_gait gait.launch.py \
  enable_walk:=true step_height:=0.5
```

50 cm Schwung → IKError pro Tick, Stand-Pose wird gehalten (Engine
catched IKError und keine Pubs für betroffenen Cycle).

---

## Stolpersteine zu erwarten

(Mehrere sind aus Stufe E übertragen — falls sie wieder auftreten.)

1. **Stale `gait_node`/`stand_node`-Prozesse** verwirren Multi-
   Publisher-Topology → Cleanup-Snippet jedes Mal komplett laufen
   lassen.

2. **Body wackelt sichtbar bei Tripod-Wechsel** — wenn 3 Beine in der
   Luft sind, nehmen die anderen 3 100 % Last. Bei body_height=-0.052
   und step_height=0.03 sollte das stabil sein. Wenn Body zu sehr
   schwankt: Penetrations-Wert prüfen (sollte konsistent -0.052 sein
   in stand und gait Launch-Files).

3. **`enable_walk`-Toggle reagiert nicht** — Param-Callback muss
   `SetParametersResult(successful=True)` zurückgeben. Prüfen mit
   `ros2 param get /gait_node enable_walk` (sollte den neu gesetzten
   Wert zeigen).

4. **Andere Params zur Laufzeit ändern** funktioniert **nicht** —
   Param-Callback gibt `successful=False` zurück für alles außer
   `enable_walk`. Für andere Werte: gait_node neu starten.

5. **Foot-Contact zeigt einseitig nur eine Gruppe** — Falls z. B. nur
   leg 1, 3, 5 toggeln und 2, 4, 6 permanent `false`: Body kippt
   wahrscheinlich. Penetrations-Wert prüfen, oder Mass/Inertia in
   URDF kontrollieren.
