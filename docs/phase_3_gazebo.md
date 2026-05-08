# Phase 3 — Gazebo-Simulation

**Dauer-Schätzung:** 3–7 Tage
**Maschine:** nur Desktop
**Vorbedingung:** Phase 2 abgeschlossen, URDF in RViz korrekt,
Foot-Links vorhanden

---

## Ziel

Der Hexapod existiert in Gazebo Harmonic, fällt nicht durch den Boden,
steht stabil unter Schwerkraft auf seinen 6 Foot-Kugeln, wenn die
Joint-Winkel passend gesetzt sind.

> **Wichtig:** In dieser Phase steht der Roboter nur. Er bewegt sich
> noch nicht selbst. Bewegung kommt mit `ros2_control` in Phase 4.

---

## Done-Kriterien

1. Paket `hexapod_gazebo` baut.
2. `ros2 launch hexapod_gazebo sim.launch.py` startet Gazebo mit
   geladenem Roboter in einer Welt mit Bodenebene.
3. Roboter wird nicht durchs Boden gespült, kollabiert nicht in sich.
4. Bei manuell gesetzten Joint-Winkeln (z. B. via Gazebo-GUI oder
   `gz topic pub`) steht der Roboter stabil auf den Beinen, ohne
   konstantes Zittern.
5. Sim-Zeit (`/clock`-Topic) ist in ROS sichtbar
   (`ros2 topic echo /clock` läuft).
6. RViz kann optional an die Sim angedockt werden und zeigt
   das Modell mit `use_sim_time:=true` live.

---

## Welt-Strategie: Standard-Welt nutzen

Für dieses Projekt reicht die in Gazebo Harmonic eingebaute Standard-
Welt. Das ist der pragmatische Weg — keine eigene Welt-Datei pflegen,
keine SDF-Plugins selbst zusammenstellen.

Konkret: Im Launch wird Gazebo mit einer der mitgelieferten Welten
gestartet. Empfehlung: **`empty.sdf` aus `gz-sim`** (kommt mit
`ros-jazzy-ros-gz`, hat eine Bodenebene und Sun-Light).

### Wichtige Klärung: Wann ist „leer" wirklich leer?

Gazebo Harmonic hat zwei häufig verwechselte Standardwelten:

| Welt | Boden vorhanden? | Bemerkung |
|---|---|---|
| `empty.sdf` (gz-sim) | **ja** (`ground_plane`) + Sun | Standard-Default, hier verwenden |
| Komplett leere Szene (Editor „New") | **nein** | Roboter fällt ins Unendliche |

Wenn der Roboter beim Start ins Bodenlose fällt, ist nicht „der Boden
durchsichtig", sondern es wurde die zweite Variante geladen. Lösung:
explizit `empty.sdf` als Argument an `gz sim` übergeben.

> **Optional, falls Probleme:** Eine minimale eigene Welt
> `worlds/hexapod_empty.sdf` kann später als Fallback angelegt werden,
> mit explizitem `ground_plane`-Include. Erst wenn die Default-Welt
> nicht zuverlässig funktioniert. Default-First-Strategie.

---

## Paket anlegen

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 \
  --maintainer-email "<deine@mail>" \
  hexapod_gazebo
```

Verzeichnis:

```
hexapod_gazebo/
├── CMakeLists.txt
├── package.xml
├── README.md
├── launch/
│   └── sim.launch.py
└── config/
    └── bridge.yaml          # ros_gz_bridge-Config (initial: nur /clock)
```

Keine `worlds/`-Verzeichnis nötig (Default-Welt aus gz-sim).

`CMakeLists.txt`:
```cmake
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})
```

`package.xml` Dependencies (`<exec_depend>`):
- `ros_gz_sim`
- `ros_gz_bridge`
- `hexapod_description`
- `xacro`
- `robot_state_publisher`

---

## URDF um Gazebo-Aspekte erweitern

In `hexapod_description` (nicht in `hexapod_gazebo`!) muss das URDF
einige Gazebo-spezifische Eigenschaften bekommen. Dafür eine neue
Datei `urdf/hexapod.gazebo.xacro` anlegen und in `hexapod.urdf.xacro`
einbinden.

### Reibung an den Foot-Kugeln

Da der Bodenkontakt jetzt sauber über die Foot-Kugeln läuft (Phase 2),
genügt es, dort die Reibungswerte zu setzen:

```xml
<!-- hexapod.gazebo.xacro -->
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <xacro:macro name="foot_friction" params="id">
    <gazebo reference="leg_${id}_foot_link">
      <mu1>1.0</mu1>
      <mu2>1.0</mu2>
      <kp>1000000.0</kp>   <!-- Steifigkeit des Kontaktpunkts -->
      <kd>100.0</kd>       <!-- Dämpfung -->
    </gazebo>
  </xacro:macro>

  <xacro:foot_friction id="1"/>
  <xacro:foot_friction id="2"/>
  <xacro:foot_friction id="3"/>
  <xacro:foot_friction id="4"/>
  <xacro:foot_friction id="5"/>
  <xacro:foot_friction id="6"/>

</robot>
```

Werte:
- `mu1 = mu2 = 1.0` → griffig (Gummi-auf-Beton). Zu niedrig (< 0.3) →
  Beine rutschen. Zu hoch (> 2.0) → unrealistisch, kann numerische
  Probleme geben.
- `kp/kd` → Kontakt-Steifigkeit/Dämpfung. Default-Werte für stabilen
  Punktkontakt mit kleinen Kugeln. Falls Roboter durch den Boden
  klappert: `kp` erhöhen.

### Selbst-Kollisionen

In Gazebo per Default **aus**. Lass das so. Aktivieren erst, wenn alles
andere stabil läuft — und dann pro Link gezielt mit `<self_collide>`-
Tag, nicht global.

### Inertien und Massen

Bereits in Phase 2 mit Mindestschranke gesetzt (`inertia_min = 1e-5`).
Falls Roboter in Gazebo trotzdem zittert oder explodiert: Schranke
erhöhen auf z. B. `1e-4`, oder Massen prüfen (Mindestmasse 0.01 kg
pro Link — wir sind mit 0.005 kg beim Foot knapp drüber, beobachten).

---

## Top-Level URDF erweitern

In `urdf/hexapod.urdf.xacro` am Ende einbinden:

```xml
<xacro:include filename="hexapod.gazebo.xacro"/>
```

> **Hinweis:** Der `<ros2_control>`-Block kommt erst in Phase 4 dazu.
> In Phase 3 wird Gazebo den Roboter spawnen und unter Schwerkraft
> simulieren, aber die Joints werden noch nicht aktiv gesteuert.

---

## Bridge-Config

`config/bridge.yaml`:

```yaml
- ros_topic_name: /clock
  gz_topic_name: /clock
  ros_type_name: rosgraph_msgs/msg/Clock
  gz_type_name: gz.msgs.Clock
  direction: GZ_TO_ROS
```

> Nur `/clock` in Phase 3. Joint-Topics kommen in Phase 4 dazu.

---

## Launch-File `sim.launch.py`

Aufgaben:

1. xacro → URDF in `robot_description`-Parameter
2. `gz sim` mit `empty.sdf` starten (`ros_gz_sim`-Launch-Include)
3. Roboter spawnen via `ros_gz_sim`/`create` mit
   `-topic /robot_description -name hexapod -z 0.20`
4. `robot_state_publisher` mit `use_sim_time: true`
5. `ros_gz_bridge` mit `bridge.yaml`

Skizze (Pseudocode — Claude Code implementiert es):

```python
# launch/sim.launch.py
gz_sim = IncludeLaunchDescription(
    PythonLaunchDescriptionSource(
        os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
    ),
    launch_arguments={'gz_args': '-r empty.sdf'}.items()
)

robot_description = Command(['xacro ', LaunchConfiguration('urdf')])

robot_state_publisher = Node(
    package='robot_state_publisher',
    executable='robot_state_publisher',
    parameters=[{'robot_description': robot_description,
                 'use_sim_time': True}]
)

spawn = Node(
    package='ros_gz_sim',
    executable='create',
    arguments=['-topic', '/robot_description',
               '-name', 'hexapod',
               '-z', '0.20']  # genug Höhe für sicheren Spawn
)

bridge = Node(
    package='ros_gz_bridge',
    executable='parameter_bridge',
    parameters=[{'config_file':
        PathJoinSubstitution([..., 'config', 'bridge.yaml'])}]
)
```

> **Spawn-Höhe:** 0.20 m ist großzügig. Roboter ist beim Spawn frei
> in der Luft, fällt unter Schwerkraft auf den Boden. Wenn er beim
> Spawn schon im Boden steckt: Höhe weiter erhöhen oder Roboter-Inhalt
> prüfen (Origin-Fehler im URDF).

---

## Erste Inbetriebnahme

```bash
colcon build --packages-select hexapod_description hexapod_gazebo
source install/setup.bash
ros2 launch hexapod_gazebo sim.launch.py
```

Erwartete Beobachtung:
- Gazebo öffnet sich, Welt geladen, Sun + Bodenebene sichtbar.
- Roboter erscheint bei z=0.20 m, fällt unter Schwerkraft.
- 6 Foot-Kugeln berühren Boden, Roboter setzt sich auf.
- Aufgrund neutraler Joint-Winkel (alle 0) wird der Roboter
  vermutlich auf dem Bauch landen — das ist OK in Phase 3.

In zweitem Terminal:
```bash
ros2 topic echo /clock
```
→ tickt = Sim läuft, Bridge funktioniert.

---

## Statisches Stehen testen

Ohne Controller (Phase 4) kannst du in Gazebo Joint-Winkel **manuell**
über die GUI setzen:
- Im Gazebo-Menü → Entity Tree → Roboter → Joints
- Sliders für jeden Joint zum Testen

Setze einen Stand-Pose-Versuch:
- Coxa-Joints: 0 (Beine in Standard-Spreizung)
- Femur-Joints: leichter Winkel nach unten (z. B. -0.5 rad)
- Tibia-Joints: knicken (z. B. +1.0 rad)

Ziel: Roboter steht stabil auf den Foot-Kugeln, kein Vibrieren,
kein Wegrutschen.

> **Wenn Roboter zittert oder springt:**
> - `mu1/mu2` erhöhen (auf 1.5)
> - `kp` erhöhen (auf 1e7)
> - `inertia_min` in Phase-2-Macro erhöhen auf 1e-4
> - Boxen-Kanten der Tibia berühren sich nicht mit dem Boden? prüfen
>   (Foot-Kugel muss tiefster Punkt sein)

---

## Stolperfallen (Box-Roboter spezifisch)

| Symptom | Ursache | Fix |
|---|---|---|
| Roboter rutscht weg | μ zu niedrig | `mu1/mu2 = 1.0`, ggf. `1.5` |
| Roboter zittert/vibriert | Inertien zu klein, oder `kp` zu niedrig | `inertia_min` hoch, `kp` auf 1e6 oder 1e7 |
| Roboter springt beim Spawn | Spawn-Position liegt im Boden | `-z` höher setzen |
| Tibia-Box hängt am Boden statt Fuß-Kugel | Foot-Kollision falsch positioniert | `foot_joint` origin = `${tibia_length} 0 0` prüfen |
| Roboter dreht sich beim Stehen | Reibung asymmetrisch oder Inertien-Tensor falsch | Inertien neu prüfen, `inertia_min` einheitlich |
| Roboter fällt durch Boden | Welt hat keine `ground_plane` | `gz_args` muss `empty.sdf` enthalten, nicht leere Szene |
| `gz sim` startet nicht / crasht | Wayland + NVIDIA | `QT_QPA_PLATFORM=xcb`, Xorg-Session — **kein** Treiberupdate |
| `/clock` nicht in `ros2 topic list` | Bridge nicht gestartet | Launch-Logs lesen, `bridge.yaml` Pfad prüfen |
| `robot_description` leer | xacro-Fehler oder Pfad falsch | `xacro` manuell laufen lassen, Output prüfen |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein `ros2_control` (Phase 4)
- Keine Bewegung, keine IK, keine Gangsteuerung
- Keine Sensoren (IMU, Kamera)
- Keine Selbstkollision aktivieren
- Keine eigene Welt-Datei (Default reicht)

---

## Phasenabschluss

- [ ] Alle 6 Done-Kriterien erfüllt
- [ ] Roboter steht stabil bei manuell gesetzten Joint-Winkeln
- [ ] `/clock` in ROS sichtbar
- [ ] README in `hexapod_gazebo/` aktuell
- [ ] Reibungswerte (`mu1/mu2/kp/kd`) dokumentiert in README
- [ ] Timeshift-Snapshot `phase_3_done`
- [ ] Git-Commit + Tag `phase-3-done`
- [ ] `PHASE.md` auf Phase 4 aktualisiert
