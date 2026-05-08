# Phase 3 — Stufe D Tryout

Spielwiese, Inspektion und Debug-Befehle für den Stand nach Stufe D.

## Status: Was geht, was geht (noch) nicht

**Was geht:**
- Gazebo Harmonic startet mit Welt + Boden + Sun.
- Hexapod spawnt bei `z=0.20`, fällt unter Schwerkraft, setzt sich auf den Boden.
- Reibung an den 6 Foot-Kugeln (`mu1=mu2=1.0`, `kp=1e6`, `kd=100`).
- ROS sieht Sim-Zeit über `/clock` (~1 kHz Tick).
- `/tf_static` liefert die fixen Transforms (foot-Joints).

**Was (noch) NICHT geht — kommt in Phase 4:**
- RViz und Gazebo sind **nicht synchronisiert.** Es gibt kein
  `/joint_states`-Bridging zwischen Gazebo und ROS, deshalb hat
  `robot_state_publisher` keine Live-Gelenkwinkel und tf-Updates fehlen.
- Joints werden **nicht aktiv gesteuert.** Wenn du den Roboter spawnst,
  fallen die Beine passiv mit der Schwerkraft. Manuelles Posing nur über
  die Gazebo-GUI-Slider.
- Kein Gait, keine IK, keine Teleop. Phasen 5–6.

## Vorbereitung

In jedem neuen Terminal:
```bash
cd ~/hexapod_ws
source install/setup.bash
```

Empfehlung: zwei Terminals parallel offen halten — eines für den Launch
(blockiert), eines fürs Inspizieren.

---

## 1. Spielwiese — was sich gerade anschauen lässt

### 1.1 RViz mit Joint-Slidern (Phase-2-Launcher, kein Gazebo)
```bash
ros2 launch hexapod_description display.launch.py
```
Statisches Studio-Setup. RViz + GUI mit 18 Slidern (einer pro Joint).
Probiere die Stand-Pose: alle `coxa=0`, alle `femur=-0.5`, alle `tibia=+1.0`.
So sieht der Roboter aus, wenn er später in Gazebo wirklich stehen können
soll. Reine Kinematik — keine Schwerkraft, kein Boden.

### 1.2 Gazebo-Sim starten (Standard)
```bash
ros2 launch hexapod_gazebo sim.launch.py
```
Roboter spawnt bei `z=0.20`, fällt, landet auf dem Bauch.

### 1.3 Drop-Test aus großer Höhe
```bash
ros2 launch hexapod_gazebo sim.launch.py spawn_z:=2.0
```
Spawn aus 2 m. Stress-Test für Inertien — bleibt der Roboter stabil oder
zerlegt es ihn? (Sollte stabil bleiben.)

### 1.4 Andere Welt
```bash
ros2 launch hexapod_gazebo sim.launch.py world:='shapes.sdf'
```
`shapes.sdf` ist eine Default-Welt aus gz-sim mit ein paar Geometrie-
Objekten. Zeigt, dass das `world`-Argument flexibel ist.

### 1.5 Headless (kein GUI-Fenster)
```bash
ros2 launch hexapod_gazebo sim.launch.py world:='-s empty.sdf'
```
Server-only. Sinnvoll auf SSH-Sessions oder wenn nur Topics inspiziert
werden sollen. (Workaround-Charakter — siehe Stufe-D-Doku.)

### 1.6 Sim mit Debug-Logs
```bash
ros2 launch hexapod_gazebo sim.launch.py --log-level DEBUG 2>&1 | less
```
Volle Verbosity — hilfreich, wenn etwas im Hintergrund stillschweigend
schiefgeht.

---

## 2. Inspizieren — was läuft da eigentlich?

Sim muss laufen. Alle Befehle in einem **zweiten Terminal** (gesourced).

### 2.1 ROS-Seite — Topics und Nodes
```bash
ros2 topic list                                  # alle ROS-Topics
ros2 node list                                   # laufende ROS-Nodes
ros2 topic info /clock                           # wer publisht /clock?
ros2 topic info /tf_static                       # statische Transforms
```

### 2.2 Sim-Zeit live mitlesen
```bash
ros2 topic echo /clock                           # rauscht im ms-Takt durch
ros2 topic hz /clock --window 200                # Tick-Rate (~1000 Hz)
```
Tipp: in Gazebo auf **Pause** drücken (oder Shortcut `Space`). Die Zeit
friert ein — Beweis, dass `/clock` wirklich Sim-Zeit ist.

### 2.3 Sim-Parameter prüfen
```bash
ros2 param get /robot_state_publisher use_sim_time   # → True
ros2 param get /ros_gz_bridge use_sim_time           # → True
ros2 param list /robot_state_publisher
```

### 2.4 Gazebo-Seite — Modelle und Topics
```bash
gz model --list                                  # ground_plane + hexapod erwartet
gz model -m hexapod -p                           # aktuelle Pose (XYZ + RPY)
gz model -m hexapod --info                       # Detailinfos: Links, Joints, Inertien
gz topic -l                                      # alle gz-Topics
gz topic -i -t /clock                            # Type-Info
gz service -l                                    # verfügbare Services
```

### 2.5 Pose live in der Konsole verfolgen
```bash
while true; do gz model -m hexapod -p | grep -A2 Pose; echo "---"; sleep 1; done
```
Wenn du den Roboter im Gazebo-GUI verschiebst, ändern sich die Werte.

### 2.6 ROS-Graphen visualisieren (Bonus)
```bash
rqt_graph
```
GUI-Werkzeug. Zeigt, welcher Node welches Topic publisht/subscribt.
Phase 3: nicht spannend (nur RSP, Bridge), wird ab Phase 4 sinnvoll.

---

## 3. Debug-Tricks

### 3.1 Sim pausieren / starten via Service
```bash
# Pausieren:
gz service -s /world/empty/control \
  --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean \
  --timeout 1000 --req 'pause: true'

# Wieder starten:
gz service -s /world/empty/control \
  --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean \
  --timeout 1000 --req 'pause: false'
```

### 3.2 Sim einen einzelnen Step machen lassen (im Pause-Modus)
```bash
gz service -s /world/empty/control \
  --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean \
  --timeout 1000 --req 'multi_step: 1'
```
Step-by-step-Debugging. Praktisch, wenn ein Effekt nur im ersten ms
auftritt und du ihn fangen willst.

### 3.3 ros2 doctor — allgemeiner Health-Check
```bash
ros2 doctor
ros2 doctor --report                             # ausführlich
```
Listet ROS-Distro, Versionen, Netzwerk, RMW-Implementierung. Wenn etwas
seltsames mit der DDS-Discovery passiert, hier zuerst nachschauen.

### 3.4 Launch-Log nachträglich lesen
```bash
ls -lt ~/.ros/log/ | head -3                     # letzte Sessions
ls ~/.ros/log/latest/                            # pro Node ein Verzeichnis
cat ~/.ros/log/latest/launch.log
cat ~/.ros/log/latest/gazebo-1-stdout.log
cat ~/.ros/log/latest/parameter_bridge-4-stdout.log
```

### 3.5 Welche Plugins lädt Gazebo wirklich?
```bash
echo $GZ_SIM_SYSTEM_PLUGIN_PATH                  # System-Plugin-Suchpfad
echo $GZ_SIM_RESOURCE_PATH                       # Welten + Modelle
```
Wichtig in Phase 4, wenn `gz_ros2_control` als Plugin geladen werden muss.

---

## 4. URDF / SDF unter die Lupe nehmen

### 4.1 URDF aus Xacro generieren und ansehen
```bash
xacro src/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/hexapod.urdf
less /tmp/hexapod.urdf
wc -l /tmp/hexapod.urdf                          # ~694 Zeilen erwartet
check_urdf /tmp/hexapod.urdf                     # strukturelle Validierung
```

### 4.2 Wie sieht Gazebo das Modell? (URDF → SDF konvertieren)
```bash
gz sdf -p /tmp/hexapod.urdf > /tmp/hexapod.sdf
less /tmp/hexapod.sdf

# Sind die Reibungswerte korrekt im SDF gelandet?
grep -A2 '<friction>' /tmp/hexapod.sdf | head -30
grep '<mu>'           /tmp/hexapod.sdf
grep '<kp>'           /tmp/hexapod.sdf
```

### 4.3 Frame-Tree als PDF
```bash
urdf_to_graphiz /tmp/hexapod.urdf
xdg-open hexapod.pdf
```
Visualisierung aller 25 Links und 24 Joints. Wenn ein Joint im falschen
Ast hängt, sieht man's hier sofort.

### 4.4 Live-Frame-Tree aus laufender Sim
Sim muss laufen. Im **dritten Terminal**:
```bash
ros2 run tf2_tools view_frames
```
Erzeugt `frames_<timestamp>.pdf` — zeigt nur Frames, die aktuell von
publishern berichtet werden. In Phase 3 also kleiner als der URDF-Tree
(weil ohne `/joint_states` keine dynamischen tfs entstehen).

### 4.5 Was steckt in `/robot_description`?
```bash
ros2 topic echo /robot_description --once 2>/dev/null | head -30
```
Bestätigt, dass das URDF wirklich live aus dem Launch ankommt. Wenn das
Topic leer ist, ist der xacro-Pfad im Launch falsch.

---

## 5. Wenn die Sim hakt — Cleanup

### 5.1 Sauberer Stop
Im Launch-Terminal: **Ctrl+C** einmal drücken. `on_exit_shutdown=true`
räumt Kindprozesse auf.

### 5.2 Wenn was hängt
```bash
pkill -INT -f 'ros2 launch hexapod_gazebo'       # SIGINT (sanft)
sleep 2
pkill -f 'gz sim'                                # Server überlebt manchmal
pkill -f 'parameter_bridge'
pkill -f 'robot_state_publisher'

# Was läuft noch?
ps aux | grep -E '(gz sim|parameter_bridge|robot_state|ros_gz)' | grep -v grep
```

### 5.3 Build-Cache zurücksetzen (selten nötig)
```bash
cd ~/hexapod_ws
rm -rf build install log
colcon build
```
**Niemals** mit `sudo apt`-Eingriffen verwechseln (siehe CLAUDE.md §5).

---

## 6. Was DU NICHT (jetzt) versuchen solltest

- **Joints aktiv per ROS-Topic kommandieren** → Phase 4. Das funktioniert
  noch nicht. Wenn du es trotzdem versuchst (`ros2 topic pub /joint_..`):
  es passiert nichts. Kein Bug, sondern Phase-3-Scope.
- **`gz_ros2_control` aktivieren** → Phase 4. Plugin ist installiert, aber
  noch nicht im URDF eingebunden.
- **Eigene Welt mit Hindernissen erstellen** → optional in Phase 5/6,
  Phase 3 nutzt bewusst die Default-Welt.
- **Mehrere Hexapods gleichzeitig spawnen** → das Launch-File ist auf
  einen einzigen `name=hexapod` festgepinnt. Müsste man parametrisieren.

---

## 7. Quick-Reference: häufigste Workflows

| Vorhaben | Befehl |
|---|---|
| Sim starten | `ros2 launch hexapod_gazebo sim.launch.py` |
| Sim aus 1 m fallen lassen | `ros2 launch hexapod_gazebo sim.launch.py spawn_z:=1.0` |
| Sim ohne GUI | `ros2 launch hexapod_gazebo sim.launch.py world:='-s empty.sdf'` |
| RViz mit Slidern (kein Sim) | `ros2 launch hexapod_description display.launch.py` |
| Sim-Zeit prüfen | `ros2 topic hz /clock` |
| Roboter-Pose in Sim | `gz model -m hexapod -p` |
| Sim pausieren | `gz service -s /world/empty/control … 'pause: true'` |
| Welche Welt-Modelle? | `gz model --list` |
| URDF generieren | `xacro src/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/hexapod.urdf` |
| Frame-Tree als PDF | `urdf_to_graphiz /tmp/hexapod.urdf` |
| Sim hart stoppen | `pkill -f 'gz sim'; pkill -f 'parameter_bridge'` |
