# Phase 1 — ROS2-Grundlagen

**Dauer-Schätzung:** 3–5 Tage (abhängig von Vorerfahrung)
**Maschine:** Desktop
**Vorbedingung:** Phase 0 abgeschlossen

---

## Ziel

ROS2-Konzepte verstanden und einmal selbst angewendet. Kein Hexapod-Code
in dieser Phase — die Investition zahlt sich in Phase 2–7 aus.

> **Diese Phase ist nicht überspringbar.** Wer ohne ROS2-Verständnis
> direkt URDFs baut, verbringt später Tage damit, Probleme zu debuggen,
> deren Ursache er nicht versteht. Bitte ernst nehmen.

---

## Done-Kriterien

1. Eigenes Python-Paket `learn_pubsub` mit Publisher + Subscriber gebaut,
   Nachrichten fließen.
2. Eigenes C++-Paket `learn_service` mit Service-Server + Client gebaut,
   Anfrage/Antwort funktioniert.
3. tf2-Konzept anhand des `r2d2`-Demos verstanden, eigener kleiner
   Static-Transform-Publisher gebaut.
4. Ein eigenes Launch-File (Python), das mehrere Knoten gleichzeitig startet.
5. Ein Parameter über CLI ausgelesen und zur Laufzeit geändert.

Diese Pakete liegen in einem **separaten** Lern-Workspace
(`~/ros2_learn_ws`), nicht im Hexapod-Workspace.

---

## Vorgehen

### 1. Offizielle Tutorials durcharbeiten

URL: <https://docs.ros.org/en/jazzy/Tutorials.html>

Reihenfolge:

- **CLI-Tools** (Configuring Environment, Using turtlesim, Topics, Services,
  Parameters, Actions, rqt-Tools)
- **Client Libraries** (Creating workspace, Creating package, Writing a
  simple publisher/subscriber Python+C++, Service server/client Python+C++)
- **Launch** (Creating a launch file, Integrating launch files into ROS2 packages)
- **tf2** (Introducing tf2, Writing a static broadcaster Python, Writing a
  broadcaster, Writing a listener)
- **URDF** (Building a visual robot model with URDF from scratch — der R2D2)

> **Was du überspringen kannst (vorerst):** ROS1-Bridge, Composable Nodes,
> Quality of Service Profile (QoS) — das brauchst du erst später, falls
> überhaupt.

### 2. Lern-Workspace anlegen

```bash
mkdir -p ~/ros2_learn_ws/src
cd ~/ros2_learn_ws
colcon build
echo "source ~/ros2_learn_ws/install/setup.bash" >> ~/.bashrc
```

### 3. Eigene Mini-Pakete

Mindestens diese vier Pakete selbst bauen (keine Copy-Paste-Übung,
sondern wirklich tippen, lesen, verstehen):

#### `learn_pubsub` (Python)

```bash
cd ~/ros2_learn_ws/src
ros2 pkg create --build-type ament_python --license Apache-2.0 \
  --dependencies rclpy std_msgs learn_pubsub
```

Ein Publisher publiziert auf `/chatter` einen Counter.
Ein Subscriber loggt empfangene Werte. Beide in separaten Knoten,
mit `ros2 run learn_pubsub publisher` startbar (entry_points in
`setup.py` setzen).

#### `learn_service` (C++)

```bash
cd ~/ros2_learn_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 \
  --dependencies rclcpp example_interfaces learn_service
```

Service-Server für `example_interfaces/srv/AddTwoInts`, Client schickt
zwei Zahlen, bekommt Summe zurück.

#### `learn_tf` (Python)

Ein statischer Frame `world → my_frame` mit `tf2_ros::StaticTransformBroadcaster`,
ein Listener, der die Transformation alle 1 s ausgibt.

In RViz `tf` als Display hinzufügen, Frames sichtbar machen.

#### `learn_launch` (Python)

Ein Launch-File, das `learn_pubsub::publisher`, `learn_pubsub::subscriber`
und den TF-Broadcaster gleichzeitig startet, mit einem Argument für die
Publish-Rate.

### 4. Parameter

Nimm den Publisher aus `learn_pubsub` und mach die Publish-Rate zu einem
ROS-Parameter (`self.declare_parameter('rate', 1.0)`).

Lese ihn beim Start, ändere ihn zur Laufzeit per:

```bash
ros2 param set /publisher rate 5.0
```

→ Subscriber muss spürbar mehr Messages bekommen.

---

## Konzept-Checkliste (Selbsttest)

Wenn du diese Fragen ohne Nachschlagen beantworten kannst, ist die Phase
durch:

- [ ] Was ist der Unterschied zwischen Topic, Service und Action?
- [ ] Was macht `rclpy.spin()` vs. `rclpy.spin_once()`?
- [ ] Was ist ein QoS-Profile, und warum gibt es Default-Sensor-Profile?
- [ ] Warum brauchen Custom-Messages eine eigene `*_interfaces`-Paket?
- [ ] Was ist der Unterschied zwischen `ament_python` und `ament_cmake`?
- [ ] Was tut `colcon build --symlink-install` und wann nutzt man es?
- [ ] Was ist `tf2`, und warum kein einfacher Topic für Transformationen?
- [ ] Was ist der Unterschied zwischen `static_transform_publisher` und
      `tf2_ros::TransformBroadcaster`?
- [ ] Wie inspizierst du Topics ohne Code (`ros2 topic ...`)?
- [ ] Wie debuggst du, warum ein Subscriber nichts empfängt?

---

## Stolperfallen

| Symptom | Ursache |
|---|---|
| `Package 'foo' not found` nach `colcon build` | Workspace nicht gesourct, neues Terminal nötig |
| Publisher läuft, Subscriber empfängt nichts | unterschiedliche `ROS_DOMAIN_ID` pro Terminal, oder QoS-Mismatch |
| `setup.py`-Änderung wirkt nicht | `colcon build` neu, oder `--symlink-install` nutzen |
| C++-Build-Fehler `find_package` | Dependency in `CMakeLists.txt` UND `package.xml` nötig |
| Launch-File startet, Knoten sterben sofort | Logs lesen — fast immer eine Exception in `__init__` |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Hexapod-Code, keine Hexapod-Pakete
- Kein Gazebo (außer du willst spielen — bremst aber den Lernfortschritt)
- Kein `ros2_control` (kommt in Phase 4)
- Keine Optimierung, keine QoS-Tuning, keine eigenen Custom-Messages

---

## Phasenabschluss

- [ ] Alle 5 Done-Kriterien erfüllt
- [ ] Konzept-Checkliste durchgegangen
- [ ] Lern-Workspace im Git (separates Repo, oder `.gitkeep`)
- [ ] Timeshift-Snapshot `phase_1_done`
- [ ] Hexapod-Repo: Git-Commit + Tag `phase-1-done` (auch wenn nichts
      am Hexapod-Repo geändert wurde — markiert den Lernfortschritt)
- [ ] `PHASE.md` auf Phase 2 aktualisiert
