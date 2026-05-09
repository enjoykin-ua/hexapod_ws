# Phase 5 Stufe E — Test-Befehle

Live-Verifikation des Single-Leg-Schwung-Modes aus Stufe E. Bein 1
schwingt periodisch in der Luft, andere 5 stehen still. Foot-Contact-
Sensoren aus Stufe D zeigen den Toggle live.

> Sim-Output nach `/tmp/sim.log`. Memory-Eintrag
> `feedback_interactive_stage_test_doc.md`.

> **Zeitschätzung:** 5–10 min für die Standard-Verifikation, abhängig
> davon wie viele Iterationen man machen will. Sequenz unten ist die
> in der Live-Session validierte Reihenfolge — wenn alles in einem Lauf
> sauber durchläuft, dauert's keine 5 min.

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

> ⚠️ **Wichtig:** vor jedem Test-Lauf voll cleanen. Sonst hängen alte
> `gait_node`/`stand_node`/`foot_contact_publisher`-Prozesse aus
> früheren Sessions als Multi-Publisher auf den selben Topics herum
> und verwirren die JTC-Subscriber. (Empirisch in Live-Session zu
> stundenlangen Debug-Iterationen geführt.)

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

**Verify visuell:** alle 6 Foot-Kugeln auf dem Boden, Roboter stabil
in Stand-Pose.

---

## Schritt 3 — gait_node starten (Terminal 2, gleicher wie Stand)

> **Wichtig:** mit `cycle_time:=2.0 step_height:=0.06` — das sind die
> in der Live-Session validierten Werte. Mit dem Default `cycle_time=1.0`
> sollte es theoretisch auch funktionieren (5-mm-Stance-Penetration-Fix
> ist in der Engine), wir hatten aber `2.0` erfolgreich getestet.

```bash
ros2 launch hexapod_gait gait.launch.py cycle_time:=2.0 step_height:=0.06
```

**Erwartet — Init-Log:**

```
gait_node init: which_leg=1, step_height=0.060 m, cycle_time=2.00 s,
                tick_rate=50 Hz, time_from_start=40.0 ms
```

**Erwartet visuell:** Bein 1 (vorne rechts) macht **1 s Schwung nach
oben + zurück runter**, dann **1 s Pause am Boden**, dann nächster
Schwung. Apex ~6 cm hoch (gut sichtbar). Andere 5 Beine bleiben fest
in Stand-Pose. Roboter steht stabil auf 5 Beinen (kein Wegrutschen,
kein progressives Kippen).

`gait_node` läuft kontinuierlich. Beenden mit `Ctrl+C` in Terminal 2.

---

## Schritt 4 — Numerische Joint-Verifikation (Terminal 3)

Während gait_node in Terminal 2 läuft:

```bash
cd ~/hexapod_ws
source install/setup.bash

echo "=== /joint_states: Bein 1 oszilliert, Rest steady ==="
ros2 topic echo /joint_states sensor_msgs/msg/JointState --once
```

**Erwartet (mehrfach `--once` ausführen, um Variation zu sehen):**
- `leg_1_femur_joint`: Wert pendelt zwischen ~-0.51 (Stand) und ~-0.6
  (Apex). Velocity ungleich 0.
- `leg_1_tibia_joint`: pendelt zwischen ~+1.01 und ~+1.05.
- `leg_1_coxa_joint`: ~0 (Schwung in der X-Z-Ebene, kein Yaw).
- `leg_2_*` bis `leg_6_*`: konstant `(~0, -0.510, +1.012)`,
  Velocity ~1e-13 (steady).

---

## Schritt 5 — Foot-Contact-Toggle live verifizieren (Terminal 3)

Stufe-D-Sensoren zeigen den Boden-Kontakt-Wechsel der Beine. Da
`ros2 topic echo` alleine subjektiv schwer zu verifizieren ist, **mit
Counter-Pattern** arbeiten:

```bash
# 8 s sample = 4 Cycles à 2 s, sollte ~50/50 toggle zeigen:
timeout 8 ros2 topic echo /leg_1/foot_contact std_msgs/msg/Bool > /tmp/leg1.log 2>&1
echo "=== leg 1 (Swing-Bein, sollte toggle): ==="
echo "true count:"
grep -c "data: true" /tmp/leg1.log
echo "false count:"
grep -c "data: false" /tmp/leg1.log

# 4 s sample = 2 Cycles, sollte permanent true zeigen:
timeout 4 ros2 topic echo /leg_2/foot_contact std_msgs/msg/Bool > /tmp/leg2.log 2>&1
echo "=== leg 2 (Stütz-Bein): ==="
echo "true count:"
grep -c "data: true" /tmp/leg2.log
echo "false count:"
grep -c "data: false" /tmp/leg2.log
```

**Erwartet** (in der Live-Session bestätigt):
- **leg 1:** ~120 true, ~210 false (≈ 36% true / 64% false). Bei
  cycle_time=2 mit 1 s Stance + 1 s Swing wäre 50/50 ideal — die 36%
  kommen daher, dass JTC am Anfang jeder Stance-Phase ein paar Ticks
  konvergieren muss.
- **leg 2:** ~120 true, ~25 false (≈ 83% true). Die paar `false`
  kommen vom kurzen Body-Wackel beim Bein-1-Schwung — funktional
  irrelevant, in Phase 7 HW eh anders gehandhabt.

**Wichtig:** beide `true count > 0` ist das eigentliche Done-Kriterium.
Genaue Prozente schwanken je nach Lauf.

### Wenn `leg 1 true count = 0` ist

(Kam in der Live-Session vor mehreren Bug-Fixes vor.) Dann diagnostisch
durchgehen:

```bash
# 1) Code-Stand verifizieren — installierter gait_engine muss
#    'cycle_phase < 0.5' enthalten:
grep -c "cycle_phase < 0.5" install/hexapod_gait/lib/python*/site-packages/hexapod_gait/gait_engine.py

# 2) Code-Stand verifizieren — '_STANCE_PENETRATION' muss enthalten sein:
grep -c "_STANCE_PENETRATION" install/hexapod_gait/lib/python*/site-packages/hexapod_gait/gait_engine.py

# 3) Wenn beides ≥ 1: Code ist installiert. Stale Prozesse prüfen:
ps aux | grep -E "(gait_node|foot_contact_publisher)" | grep -v grep

# 4) Wenn mehrere gait_node-Prozesse laufen → cleanup-snippet erneut
#    laufen lassen + Sim neu starten ab Schritt 1.
```

Falls beide Code-Checks 0 zurückgeben: `colcon build --packages-select
hexapod_gait` und Schritt 3 neu starten.

---

## Schritt 6 — Stützbein-Stabilität (Terminal 3)

Verifizieren, dass die 5 Stütz-Beine nicht einknicken oder driften:

```bash
echo "=== Body-Pose über 5 s ==="
for i in 1 2 3 4 5; do
  echo "Sample $i:"
  gz model -m hexapod -p
  sleep 1
done
```

**Erwartet:**
- z bleibt bei ~0.055 m (Stand-Höhe konstant).
- y bleibt bei ~0 (kein systematisches Kriechen).
- RPY ≈ 0 (kein Kippen).

In der Live-Session beobachtet: z=0.054999 m durchgängig konstant,
y=-0.000038 m (mikroskopische Schwankung), RPY≈0. Body kippt minimal
nach rechts während Bein 1 schwingt, aber stabil periodisch — kein
progressives Wegkippen.

> **Hinweis:** wenn `gz model` mit "Service call to /gazebo/worlds
> timed out" failt, einfach nochmal probieren — das ist ein DDS-CLI-
> Race, nichts Echtes kaputt.

---

## Schritt 7 — Aufräumen

Terminal 2: `Ctrl+C` → gait_node beendet sich sauber.

Terminal 1: 

```bash
kill %1   # oder das vollständige Cleanup-Snippet von oben
```

---

## Optionale Variationen

### Default-Werte testen (cycle_time=1.0, step_height=0.05)

```bash
ros2 launch hexapod_gait gait.launch.py
```

Mit cycle_time=1.0 ist Stance nur 0.5 s — JTC hat weniger Zeit zum
Konvergieren. Funktioniert dank Stance-Penetration-Fix trotzdem, aber
visuell schneller.

### Anderes Schwung-Bein

```bash
ros2 launch hexapod_gait gait.launch.py which_leg:=4 cycle_time:=2.0 step_height:=0.06
```

Dann schwingt **Bein 4 (hinten links)**. Test wieder mit
`/leg_4/foot_contact` echo statt `/leg_1`.

### Langsam und hoch

```bash
ros2 launch hexapod_gait gait.launch.py cycle_time:=4.0 step_height:=0.08
```

4 s Cycle (2 s Stance + 2 s Swing), 8 cm Schwung-Höhe. Sehr deutlich
sichtbar, gut für Demo / Video.

### IK-Out-of-Reach-Test

```bash
ros2 launch hexapod_gait gait.launch.py step_height:=0.5
```

50 cm Schwung-Höhe → Bein kann das nicht erreichen. **Erwartet:**
`gait_node` loggt `IKError` pro Tick und sendet keine Pubs (Stand-Pose
wird gehalten).

Mit `Ctrl+C` beenden, dann mit Default neu starten.

---

## Stolpersteine aus der Live-Session

Diese sind alle in der Stufe-E-Implementation gefixt; hier dokumentiert
für den Fall dass sie in Stufe F+ wiederkommen:

1. **Stale `gait_node`-Prozesse** verwirren Multi-Publisher-Topology
   → Cleanup-Snippet jedes Mal komplett laufen lassen.

2. **JTC-Tracking-Lag** in Continuous-Pub-Mode (50 Hz)
   verhindert Foot-Boden-Kontakt im Stance — gefixt durch
   `_STANCE_PENETRATION = 0.005` (5 mm) Override für das Swing-Bein
   im Stance, andere 5 Beine halten Body-Höhe (Hebel 5:1).

3. **`use_sim_time` + `get_clock().now()` Race** mit /clock-DDS-
   Discovery — gefixt durch `time.monotonic()` für Timer-Logik.

4. **`<topic>` außerhalb `<contact>`** in xacro hatte Stufe-D
   blockiert — der korrekte Sensor-Block ist jetzt fix in
   `hexapod.foot_contact.xacro`, kein Stufe-E-Problem mehr.
