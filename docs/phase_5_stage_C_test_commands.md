# Phase 5 Stufe C — Test-Befehle

Live-Verifikation des `stand_node` aus Stufe C. User führt die Befehle
in den jeweiligen Terminals aus, meldet knapp den Status pro Schritt
zurück (kein Vollausgabe-Dump in den Chat).

> **Sim-Output** wird nach `/tmp/sim.log` umgeleitet, damit Terminal 1
> verfügbar bleibt und der Chat-Kontext nicht überflutet wird (Memory-
> Eintrag `feedback_interactive_stage_test_doc.md`).

---

## Vorbereitung in jedem Terminal

```bash
cd ~/hexapod_ws
source install/setup.bash
```

Falls noch nicht gebaut:

```bash
colcon build --packages-select hexapod_kinematics hexapod_gait
source install/setup.bash
```

---

## Schritt 1 — Sim mit Phase-4-Bringup starten (Terminal 1)

```bash
ros2 launch hexapod_bringup sim.launch.py > /tmp/sim.log 2>&1 &
```

**Erwartet:**
- Gazebo-Fenster öffnet sich, Hexapod liegt auf dem Bauch (Default-Pose
  alle Joints = 0, wie Phase-4-Stufe-E beobachtet).
- Im `/tmp/sim.log`: 7 Spawner-Meldungen, alle mit `Successfully loaded
  controller [...] into state active`.

**Status-Meldung an Claude:** „Sim läuft, 7 Controller active" oder
genauer Fehler (z. B. „1 Spawner failed").

---

## Schritt 2 — Controller-Status prüfen (Terminal 2)

```bash
ros2 control list_controllers
```

**Erwartet:**

```
joint_state_broadcaster joint_state_broadcaster/JointStateBroadcaster active
leg_1_controller        joint_trajectory_controller/JointTrajectoryController active
leg_2_controller        joint_trajectory_controller/JointTrajectoryController active
leg_3_controller        joint_trajectory_controller/JointTrajectoryController active
leg_4_controller        joint_trajectory_controller/JointTrajectoryController active
leg_5_controller        joint_trajectory_controller/JointTrajectoryController active
leg_6_controller        joint_trajectory_controller/JointTrajectoryController active
```

**Status-Meldung:** „7 Controller active" oder Liste der fehlenden.

---

## Schritt 3 — `stand_node` starten (Terminal 2)

```bash
ros2 launch hexapod_gait stand.launch.py
```

**Erwartet (Logs im selben Terminal, ~3 s Gesamtdauer bis zum Exit):**

```
[stand_node]: stand_node init: foot_target=(0.2700, 0.0, -0.0470) in Bein-Frame, transition=4.0s
[stand_node]: waiting 2.0s for DDS discovery
[stand_node]: all 6 JTCs visible in graph (counts={'leg_1': 1, ..., 'leg_6': 1})
[stand_node]: pub leg_1: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: pub leg_2: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: pub leg_3: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: pub leg_4: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: pub leg_5: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: pub leg_6: coxa=+0.0000 femur=-0.5089 tibia=+1.0102
[stand_node]: stand pose dispatched, JTC will reach target in ~4.0s; exiting
```

**Akzeptabler alternativer Pfad** — falls der lokale rclpy-Graph-State
die JTC-Subscriptions nicht rechtzeitig sieht (bekanntes
DDS-Discovery-Race in rclpy/Jazzy):

```
[stand_node]: waiting 2.0s for DDS discovery
[stand_node]: JTCs not visible in local graph state (missing=[...]);
              publishing anyway. Verify externally with `ros2 topic info ...`.
[stand_node]: pub leg_1: ...
...
[stand_node]: stand pose dispatched, JTC will reach target in ~4.0s; exiting
```

In dem Fall trotzdem prüfen ob der Roboter die Stand-Pose erreicht (er
sollte) — der externe `ros2 topic info` zeigt 1 Subscription, also
**ist** der JTC im Netzwerk subscribed; nur die rclpy-API meldet das
inkonsistent. Pub geht trotzdem an.

Knoten beendet sich von selbst, Prompt kommt zurück. Im Gazebo-Fenster
fährt der Roboter über die nächsten 4 s sanft in die Stand-Pose
(Beine knicken sich, er hebt sich auf die 6 Foot-Kugeln).

**Status-Meldung:** „Roboter steht auf 6 Kugeln" oder „Fehler: <Logzeile>".

---

## Schritt 4 — Joint-Werte verifizieren (Terminal 3)

```bash
ros2 topic echo /joint_states sensor_msgs/msg/JointState --once
```

> **Hinweis zur expliziten Typangabe:** Ohne den expliziten Typ
> `sensor_msgs/msg/JointState` versucht `ros2 topic echo` erst, den Typ
> aus dem ROS-Graphen zu ermitteln. In einem frischen Terminal kann das
> Sekunden dauern (DDS-Discovery-Race) und meldet "topic does not appear
> to be published yet", obwohl JSB längst publisht. Mit explizitem Typ
> entfällt der Lookup und der echo läuft sofort. Gleicher Mechanismus
> wie der `discovery_wait` im stand_node.

**Erwartet (alle 18 Joints):**

- 6× `*_coxa_joint`: position ≈ 0.0 (±0.01 rad, in der Praxis ~1e-18 = FP-Rauschen)
- 6× `*_femur_joint`: position ≈ -0.510 (±0.01 rad, in der Praxis ±2e-5)
- 6× `*_tibia_joint`: position ≈ +1.012 (±0.01 rad, in der Praxis ±2e-4)
- velocity ≈ 0 (steht still nach Settling, ~1e-13 rad/s)
- effort = NaN (kein Effort-State-Interface deklariert, Phase 4 dokumentiert)

Stufe-B-Smoke wird damit live verifiziert: IK auf
`(0.27, 0, -0.047)` → `(0, -0.510, 1.012)`. Toleranz ±0.01 rad
fängt JTC-Settling-Restdrift ab.

**Status-Meldung:** „Joint-Werte passen ±0.01 rad" oder konkrete
Abweichung pro Joint.

---

## Schritt 5 — Body-Drift-Check (Terminal 3)

5 Samples mit 1 s Abstand:

```bash
for i in 1 2 3 4 5; do
  echo "Sample $i:"
  gz model -m hexapod -p
  sleep 1
done
```

**Erwartet:**
- `pose.position.z` ≈ 0.055 m (Stand-Höhe wie Phase-4-Stufe-F).
- Drift über 5 s: **< 1 mm** (z) **und < 0.5°** (RPY).
- Phase-4-Stufe-F erreichte Drift = 0; gleicher Wert hier erwartet
  (gleiche Pose, gleiche Reibungs-Defaults).

**Status-Meldung:** „Drift = 0" oder „Drift max <Wert>".

---

## Schritt 6 — Aufräumen

Sim beenden (Terminal 1 oder mit Job-Control):

```bash
kill %1
```

Oder im Gazebo-Fenster `Ctrl+C` im Sim-Terminal.

**Status-Meldung:** „Sim beendet."

---

## Optionale Variationen (für späteres Tuning)

### Anderen `body_height` testen

```bash
# Roboter höher (femur weniger geknickt):
ros2 launch hexapod_gait stand.launch.py body_height:=-0.06

# Roboter tiefer (femur stärker geknickt, näher an Tibia-Limit):
ros2 launch hexapod_gait stand.launch.py body_height:=-0.03
```

### Out-of-reach-Fall (sollte sauber failen)

```bash
ros2 launch hexapod_gait stand.launch.py body_height:=-0.30
```

**Erwartet:** stand_node failt mit `IK failed for leg_1: ... out of
reach for ... d=0.X, reachable range [...]`. Knoten exit ≠ 0.

### Override-Test (validiert Stufe-C-Lifecycle-Konzept)

In Terminal 2 nach Schritt 3 (Roboter steht):

```bash
# Während der Roboter steht, manueller Trajectory-Goal an Bein 1:
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.5, -1.0, 1.5], time_from_start: {sec: 2}}]}'
```

**Erwartet:** Bein 1 fährt ohne Beteiligung von stand_node in die neue
Pose. JTC-Override-Mechanik wirkt unabhängig vom (bereits exit-en)
stand_node.

**Status-Meldung:** „Override hat funktioniert, Bein 1 in neuer Pose."
