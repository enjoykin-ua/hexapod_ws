# Phase 3 — Fortschritt

Beim Neustart: diese Datei lesen, dann mit dem ersten offenen Schritt weitermachen.
Stufenplan A–E abgeleitet aus `docs/phase_3_gazebo.md`.

> **Konvention:** Pro erledigtem Bullet sofort `[ ]`→`[x]` setzen, nicht batchen
> (siehe Memory-Eintrag `feedback_phase_progress_tracking.md`).

---

## Stufe A — Paket-Skelett `hexapod_gazebo` ✅

**Ziel:** Ein zweites ROS2-Paket neben `hexapod_description` anlegen, das alles
Sim-Spezifische bündelt. Trennung ist bewusst: `hexapod_description` läuft
auf Desktop **und** Pi, `hexapod_gazebo` nur am Desktop. Auf dem Pi wird das
Paket später schlicht nicht gebaut — keine Sim-Abhängigkeiten in der
Hardware-Chain.

**Was wir machen:** `ament_cmake`-Paket erzeugen, Verzeichnisse für Launch-
und Config-Dateien anlegen, `package.xml` mit den Sim-Abhängigkeiten füllen
(`ros_gz_sim`, `ros_gz_bridge` usw.) und einen leeren Build verifizieren.
Noch keine eigene Welt-Datei — wir nutzen die in Gazebo Harmonic mitgelieferte
`empty.sdf` (enthält bereits `ground_plane` + Sun-Light), siehe Welt-Strategie
in `phase_3_gazebo.md`.

**Warum `ament_cmake` statt `ament_python`:** Das Paket installiert nur
Resource-Dateien (Launch, YAML), kein Python-Code wird kompiliert oder
exportiert. `ament_cmake` ist der ROS2-Standard für solche Resource-only-Pakete
und ist konsistent mit `hexapod_description`.

- [x] Tools/Pakete verifiziert (`ros-jazzy-ros-gz` 1.0.22, `ros-jazzy-ros-gz-sim` 1.0.22, `ros-jazzy-ros-gz-bridge` 1.0.22; Bonus: `ros-jazzy-gz-ros2-control` 1.2.17 für Phase 4 schon da)
- [x] `gz sim --version` → Gazebo Sim 8.11.0 (= Harmonic), `gz topic -l` exit 0 (leer, da keine Sim läuft — erwartet)
- [x] `ros2 pkg create --build-type ament_cmake --license Apache-2.0 --maintainer-email "noreply@gmx.net" --maintainer-name "enjoykin-ua" hexapod_gazebo` in `src/` (konsistent zu `hexapod_description`)
- [x] Verzeichnisstruktur angelegt: `launch/`, `config/` (kein `worlds/` — Default-Welt aus gz-sim); auto-generierte `include/`, `src/` entfernt (Resource-only-Paket)
- [x] `CMakeLists.txt`: `install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})`; auto-generierte C++-Boilerplate (`-Wall`, `find_package`-Stub) entfernt
- [x] `package.xml` `<exec_depend>`s: `ros_gz_sim`, `ros_gz_bridge`, `hexapod_description`, `xacro`, `robot_state_publisher` (keine `TODO:`-Stubs, Description bei pkg-create gesetzt)
- [x] `colcon build --packages-select hexapod_gazebo` grün (1.41s); `install/hexapod_gazebo/share/hexapod_gazebo/{launch,config}` vorhanden

---

## Stufe B — URDF um Gazebo-Aspekte erweitern ✅

> Änderungen in `hexapod_description`, **nicht** in `hexapod_gazebo`.

**Ziel:** Das URDF aus Phase 2 ist physikalisch valide (Massen, Inertien,
Kollisionen), aber es fehlen die **Sim-spezifischen Eigenschaften**, die
Gazebo zur Kontaktberechnung braucht — vor allem Reibung an den 6 Foot-Kugeln.
Ohne diese Werte würde Gazebo Defaults nehmen, die für unseren Box-Roboter
unbrauchbar sind (Beine rutschen weg, Kontakt zittert).

**Warum in `hexapod_description` und nicht in `hexapod_gazebo`:** Das URDF
ist die Single Source of Truth für das Robotermodell. Gazebo-Tags
(`<gazebo reference="...">`) gehören ins Modell, weil sie Eigenschaften
einzelner Links beschreiben. Sie werden vom `robot_state_publisher` einfach
ignoriert, sind also auch auf dem Pi unschädlich. Eine eigene gazebo-Xacro-
Datei (`hexapod.gazebo.xacro`) hält sie aber sauber getrennt vom Kinematik-
Teil.

**Was die Werte bedeuten:**
- `mu1`, `mu2` — Coulomb-Reibungskoeffizienten in zwei Tangentialrichtungen
  des Kontakts. `1.0` entspricht Gummi auf Beton — griffig genug, dass die
  Beine nicht wegrutschen.
- `kp` — Kontakt-Steifigkeit (Federkonstante des Penalty-basierten Kontakts).
  Zu niedrig → Foot sinkt sichtbar in den Boden ein. Zu hoch → numerische
  Instabilität, Roboter springt.
- `kd` — Kontakt-Dämpfung. Verhindert Bouncing beim ersten Bodenkontakt.

**Selbst-Kollisionen lassen wir aus** (Default in Gazebo): Aktivierung pro
Link kostet Performance und führt bei einem 18-DOF-Roboter schnell zu
Fehlalarmen, wenn benachbarte Box-Visuals minimal überlappen. Erst nachdem
Gait und IK stabil laufen, falls überhaupt nötig.

- [x] Neue Datei `hexapod_description/urdf/hexapod.gazebo.xacro` angelegt (xacro-Header, robot-Tag mit xacro-NS)
- [x] Macro `foot_friction(id)` mit `<gazebo reference="leg_${id}_foot_link">` + `mu1=mu2=1.0`, `kp=1e6`, `kd=100`
- [x] Macro 6× instanziiert (`id=1..6`)
- [x] In `hexapod.urdf.xacro` am Ende (vor `</robot>`): `<xacro:include filename="hexapod.gazebo.xacro"/>` mit Kommentar-Banner
- [x] `xacro hexapod.urdf.xacro > /tmp/hexapod.urdf` läuft fehlerfrei (694 Zeilen)
- [x] `check_urdf /tmp/hexapod.urdf` weiterhin grün, `base_link has 6 child(ren)`
- [x] Im generierten URDF sind 6 `<gazebo reference="leg_*_foot_link">`-Blöcke vorhanden (alle 6 IDs verifiziert via `grep`)
- [x] `colcon build --packages-select hexapod_description` grün (0.51s)
- [x] Selbst-Kollisionen bewusst **aus** gelassen (kein `<self_collide>`-Tag); dokumentiert in Stufe-B-Vorwort + Macro-Kommentar in `hexapod.gazebo.xacro`
- [x] Inertien/Massen unverändert aus Phase 2 (`inertia_min = 1.0e-5` in `inertials.xacro`); falls später Zittern: erhöhen

### Befehls-Cheatsheet (Stufe B + allgemeines URDF/Build-Workflow)

Diese Befehle werden ab jetzt nach **jeder Änderung an einer Xacro/URDF-Datei
oder am Build-System** wiederkehrend gebraucht. Reihenfolge im Alltag:
xacro → check_urdf → (optional graph) → colcon build → source.

**URDF aus Xacro generieren (zum manuellen Inspizieren / Validieren):**
```bash
cd ~/hexapod_ws/src/hexapod_description/urdf
xacro hexapod.urdf.xacro > /tmp/hexapod.urdf
wc -l /tmp/hexapod.urdf          # Zeilen-Anzahl als grobe Sanity-Probe
```

**URDF strukturell validieren:**
```bash
check_urdf /tmp/hexapod.urdf
# Erwartet: "Successfully Parsed XML" + Baumdruck mit allen Links
```

**Gazebo-Tags / Patterns im generierten URDF zählen + auflisten:**
```bash
grep -c '<gazebo reference=' /tmp/hexapod.urdf      # Anzahl der gazebo-Blöcke
grep    '<gazebo reference=' /tmp/hexapod.urdf      # alle Vorkommen anzeigen
grep -c '<self_collide>'    /tmp/hexapod.urdf       # erwartet: 0 in Phase 3
grep    'inertia_min'       urdf/inertials.xacro    # aktueller Schranken-Wert
```

**Frame-Tree als PDF (visuelle Verifikation der Kinematik-Struktur):**
```bash
urdf_to_graphiz /tmp/hexapod.urdf       # erzeugt hexapod.gv + hexapod.pdf
# braucht graphviz: sudo apt install graphviz  (einmalig)
```

**URDF nach SDF konvertieren (zeigt, wie Gazebo das Modell sieht):**
```bash
gz sdf -p /tmp/hexapod.urdf > /tmp/hexapod.sdf
# nützlich, um zu prüfen ob mu1/mu2/kp/kd korrekt im SDF landen
```

**Paket bauen:**
```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_description
colcon build --packages-select hexapod_description hexapod_gazebo   # mehrere
colcon build --symlink-install --packages-select hexapod_description
# --symlink-install: Resource-Dateien werden symlinkt statt kopiert.
# Folge: Änderungen an .xacro / .yaml / launch.py wirken ohne Rebuild,
# nur ein erneutes "source install/setup.bash" ist nicht nötig.
```

**Workspace-Env nach Build aktivieren (pro neuem Terminal!):**
```bash
source ~/hexapod_ws/install/setup.bash
# Alternative, falls nur ein Paket: source install/hexapod_description/share/...
# Tipp: in ~/.bashrc kann das einmalig per
#   [ -f ~/hexapod_ws/install/setup.bash ] && source ~/hexapod_ws/install/setup.bash
# eingetragen werden, damit es für jedes Terminal automatisch gilt.
```

**ROS-Pakete-Sichtbarkeit prüfen:**
```bash
ros2 pkg list | grep hexapod                      # alle eigenen Pakete sichtbar?
ros2 pkg prefix hexapod_description               # Install-Pfad des Pakets
ros2 pkg xml hexapod_description                  # die installierte package.xml
```

**Wenn etwas „komisch" wirkt (Build-Cache verdächtig):**
```bash
cd ~/hexapod_ws
rm -rf build/ install/ log/                       # nuklearer Reset, sicher
colcon build                                      # alles frisch bauen
# NICHT verwechseln mit "sudo apt"-Eingriffen — siehe CLAUDE.md §5.
```

---

## Stufe C — Bridge-Config + Launch-File ✅

**Ziel:** Gazebo und ROS2 sind zwei getrennte Middleware-Welten — Gazebo
spricht intern `gz-transport`, ROS2 spricht DDS. Damit Topics, Services und
vor allem die **Sim-Zeit** zwischen beiden Welten fließen können, brauchen
wir die `ros_gz_bridge`. Außerdem brauchen wir ein Launch-File, das alle
Komponenten in der richtigen Reihenfolge hochfährt.

### C.1 Bridge-Config

**Ziel:** Eine deklarative YAML-Config, die der `parameter_bridge` lädt,
statt Topics einzeln per CLI-Argumenten zu mappen. Ist robuster gegen Tippfehler
und versionierbar.

**Was wir brücken — und was nicht:** In Phase 3 nur `/clock` (Sim → ROS).
Sobald Gazebo läuft, **muss** ROS auf Sim-Zeit umgestellt werden, sonst hat
`robot_state_publisher` einen anderen Zeit-Begriff als die Sim, und tf-Lookups
schlagen fehl. Joint-States, Cmd-Topics usw. kommen erst in Phase 4 mit
`ros2_control` dazu — die laufen dann nicht über die Bridge, sondern über
`gz_ros2_control`-Plugin direkt im Sim-Prozess.

**`GZ_TO_ROS` als Richtung:** Sim ist Master der Zeit, ROS-Knoten sind
Konsumenten. Die andere Richtung (`ROS_TO_GZ`) wäre falsch und würde nicht
funktionieren.

- [x] `hexapod_gazebo/config/bridge.yaml` angelegt mit nur `/clock` (`GZ_TO_ROS`, `rosgraph_msgs/msg/Clock` ↔ `gz.msgs.Clock`)
- [x] YAML syntaktisch valide (`yaml.safe_load` → 1 Eintrag mit 5 Pflichtfeldern: `ros_topic_name`, `gz_topic_name`, `ros_type_name`, `gz_type_name`, `direction`)

### C.2 Launch-File `sim.launch.py`

**Ziel:** Ein einziger Befehl (`ros2 launch hexapod_gazebo sim.launch.py`)
fährt die komplette Sim hoch. Reproduzierbar, ohne dass man sich CLI-
Argumente merken muss.

**Die 4 Aktionen im Launch und ihre Reihenfolge:**

1. **xacro → `robot_description`-Parameter** — Das URDF wird beim Launch
   aus den `.xacro`-Dateien generiert (nicht im Build-Schritt!). `Command(['xacro ', ...])`
   ist eine Launch-Substitution, die zur Laufzeit ausgeführt wird. Vorteil:
   Änderungen an Macros wirken nach `ros2 launch` ohne `colcon build`
   (mit `--symlink-install`).
2. **`gz sim` über `ros_gz_sim`-Launch-Include** — Statt `gz sim` direkt
   per `ExecuteProcess` zu starten, inkludieren wir das offizielle Launch-File
   aus `ros_gz_sim`. Das setzt nebenbei wichtige Env-Vars (z. B. Plugin-
   Pfade) korrekt. `gz_args='-r empty.sdf'` heißt: `-r` = run (sofort starten,
   nicht pausiert), `empty.sdf` = die Standard-Welt aus gz-sim.
3. **`robot_state_publisher` mit `use_sim_time: True`** — Publisht tf-Frames
   aus dem URDF + aktuellen Joint-States. Die `use_sim_time`-Flag ist
   **kritisch** — siehe C.1.
4. **Spawn-Node `ros_gz_sim/create`** — Liest `/robot_description` aus dem
   ROS-Parameter-Server, übersetzt zu SDF und spawnt das Modell in der
   laufenden Sim. `-z 0.20` = 20 cm über dem Boden, damit der Roboter beim
   Spawn nicht im Boden steckt. `-name hexapod` = Modellname in Gazebo,
   wichtig für spätere Topic-Pfade.
5. **Bridge-Node** — Lädt die `bridge.yaml` und startet die `/clock`-Brücke.

**Reihenfolge in der Praxis:** Alle Nodes können parallel gestartet werden;
ROS2-Launch garantiert keine harte Sequenz, die Nodes warten intern auf
ihre Abhängigkeiten (Spawn wartet auf `/robot_description`, Bridge auf
`gz sim`-Process).

- [x] `hexapod_gazebo/launch/sim.launch.py` angelegt
- [x] xacro → `robot_description` via `Command(['xacro ', LaunchConfiguration('urdf')])`, gewrappt in `ParameterValue(..., value_type=str)` (verhindert YAML-Reparse durch rclpy)
- [x] `IncludeLaunchDescription` für `ros_gz_sim/launch/gz_sim.launch.py` mit `gz_args='-r <world>'` und `on_exit_shutdown=true` (Launch endet, wenn Gazebo geschlossen wird)
- [x] `robot_state_publisher`-Node mit `use_sim_time: True`
- [x] Spawn-Node `ros_gz_sim/create` mit `-topic /robot_description -name hexapod -z <spawn_z>`
- [x] Bridge-Node `ros_gz_bridge/parameter_bridge` mit `config_file=…/bridge.yaml` und `use_sim_time: True`
- [x] LaunchArguments: `urdf` (Default = `hexapod_description/urdf/hexapod.urdf.xacro`), `world` (Default = `empty.sdf`), `spawn_z` (Default = `0.20`)
- [x] `colcon build --packages-select hexapod_gazebo` grün (0.09s)
- [x] `ros2 launch hexapod_gazebo sim.launch.py --print` (Dry-Run) listet 3 LaunchArgs + IncludeLaunchDescription (gz_sim) + 3 ExecuteProcesses (RSP, Spawn, Bridge) ohne Python-Fehler

### Ablaufplan: Was passiert beim `ros2 launch hexapod_gazebo sim.launch.py`

Grobsicht — wie aus den 4 Aktionen im Launch-File ein laufender Sim-Stack wird:

```
                 ros2 launch sim.launch.py
                            │
       ┌────────────────────┼────────────────────────────────┐
       │                    │                                │
       ▼                    ▼                                ▼
  LaunchArguments      Substitutions ausgewertet     4 Aktionen parallel
  (urdf, world,        - default_urdf-Pfad           starten
   spawn_z mit         - bridge.yaml-Pfad
   Defaults gesetzt)   - xacro ausgeführt → URDF-XML-String

  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                      │
  │   (1) IncludeLaunchDescription → ros_gz_sim/gz_sim.launch.py         │
  │       └─► startet Prozess `gz sim -r empty.sdf`                      │
  │           └─► Welt geladen: ground_plane + sun                       │
  │           └─► Physik-Loop läuft (g = -9.81 m/s²)                     │
  │                                                                      │
  │   (2) Node: robot_state_publisher                                    │
  │       parameter robot_description = <URDF-String aus xacro>          │
  │       use_sim_time = True                                            │
  │       └─► publisht /robot_description (latched) + /tf                │
  │                                                                      │
  │   (3) Node: ros_gz_sim/create  (Spawn)                               │
  │       wartet auf Topic /robot_description                            │
  │       └─► liest URDF, konvertiert zu SDF                             │
  │       └─► Service-Call an gz sim: "spawn entity 'hexapod' @ z=0.20"  │
  │           └─► Roboter erscheint, fällt unter Schwerkraft             │
  │           └─► Foot-Kugeln treffen ground_plane                       │
  │               (mu1/mu2/kp/kd aus URDF-Gazebo-Tags aktiv)             │
  │       └─► Node beendet sich nach erfolgreichem Spawn (One-Shot)      │
  │                                                                      │
  │   (4) Node: ros_gz_bridge/parameter_bridge                           │
  │       config_file = bridge.yaml                                      │
  │       use_sim_time = True                                            │
  │       └─► subscribt gz-Topic /clock                                  │
  │       └─► publisht ROS-Topic /clock (rosgraph_msgs/msg/Clock)        │
  │           └─► alle ROS-Nodes mit use_sim_time:=true                  │
  │               benutzen ab jetzt Sim-Zeit statt Wallclock             │
  │                                                                      │
  └──────────────────────────────────────────────────────────────────────┘
```

**Datenfluss zur Laufzeit:**

```
   Gazebo (Physik-Engine) ─── /clock (Sim-Zeit) ───► ros_gz_bridge ───► ROS /clock
                          ─── /world/.../pose-info ──────────────────► (in Phase 4
                                                                          gebrückt)
   Gazebo                 ◄── Spawn-Service-Call ───── ros_gz_sim/create
                                                        ▲
                                                        │ /robot_description
                                                        │ (latched topic)
                                                        │
   robot_state_publisher  ────────────────────────────────────┘
       URDF-Parameter
```

**Was Phase 3 noch NICHT macht** (kommt in Phase 4):
- Kein `/joint_states`-Topic von Gazebo nach ROS — RSP hat in Phase 3 keine
  Live-Gelenkwinkel und kann das tf-Modell nicht aktualisieren. RViz würde
  daher den Roboter in seiner Spawn-Pose sehen, nicht in der echten Sim-Pose.
- Kein Controller, der Joints aktiv hält. Daher fallen Beine unter Schwerkraft
  passiv mit dem Körper zusammen — das ist erwartetes Verhalten, kein Bug.
- Keine Joint-Cmd-Topics. Stand-Pose nur manuell über Gazebo-GUI (Stufe E).

### Befehls-Cheatsheet (Stufe C / Sim-Bedienung)

**Sim starten / stoppen:**
```bash
ros2 launch hexapod_gazebo sim.launch.py
# Override per LaunchArgument:
ros2 launch hexapod_gazebo sim.launch.py spawn_z:=0.50
ros2 launch hexapod_gazebo sim.launch.py world:=empty.sdf
ros2 launch hexapod_gazebo sim.launch.py urdf:=/pfad/zu/eigener.urdf.xacro

# Dry-Run (zeigt geplante Aktionen, startet nichts):
ros2 launch hexapod_gazebo sim.launch.py --print

# Sauberes Stoppen: Ctrl+C im Launch-Terminal (on_exit_shutdown=true
# räumt alle Kindprozesse auf). Falls etwas hängt:
pkill -f 'gz sim'
pkill -f 'parameter_bridge'
pkill -f 'robot_state_publisher'
pkill -f 'ros_gz_sim'
ps aux | grep -E '(gz sim|ruby|parameter_bridge|robot_state)' | grep -v grep
```

**ROS-Seite inspizieren (zweites Terminal mit `source install/setup.bash`):**
```bash
ros2 topic list                                      # alle ROS-Topics
ros2 topic echo /clock                               # tickt Sim-Zeit?
ros2 topic hz /clock                                 # Tick-Rate (~1000 Hz Sim-Default)
ros2 topic info /clock                               # Publisher/Subscriber-Anzahl
ros2 node list                                       # laufende ROS-Nodes
ros2 node info /robot_state_publisher                # Topics/Params/Services dieses Nodes
ros2 param list /robot_state_publisher               # Parameter
ros2 param get /robot_state_publisher use_sim_time   # → True erwartet
ros2 topic echo /tf_static --once                    # statische tf-Frames
```

**Gazebo-Seite inspizieren:**
```bash
gz topic -l                                          # alle gz-Topics
gz topic -i -t /clock                                # Type-Info zu einem Topic
gz topic -e -t /clock                               # Topic live mitlesen (Ctrl+C)
gz model -l                                          # Modelle in der laufenden Sim
gz model -m hexapod -p                               # Pose des Hexapods
gz service -l                                        # verfügbare Services
gz sim --help                                        # CLI-Optionen von gz sim
```

**Bridge-Probleme diagnostizieren:**
```bash
# Lädt der Bridge-Node die Config? Logs anschauen:
ros2 launch hexapod_gazebo sim.launch.py 2>&1 | grep -i bridge

# Prüfen, ob Config-Pfad korrekt zum Install-Path zeigt:
ros2 pkg prefix hexapod_gazebo
ls $(ros2 pkg prefix hexapod_gazebo)/share/hexapod_gazebo/config/
```

**URDF-Pfad zur Laufzeit verifizieren:**
```bash
# So sieht der RSP das robot_description-Topic:
ros2 topic echo /robot_description --once | head -20
```

**Hot-Reload-Workflow nach `--symlink-install`:**
```bash
# Änderung an .xacro / launch.py / yaml → kein Rebuild nötig:
# Sim einfach mit Ctrl+C beenden und neu launchen.
# Aber: Änderungen an package.xml / CMakeLists.txt brauchen Rebuild.
colcon build --packages-select hexapod_gazebo --symlink-install
```

---

## Stufe D — Erste Inbetriebnahme ✅

**Ziel:** Erster vollständiger End-to-End-Test. Wir wollen sehen, dass alle
Komponenten aus Stufen A–C zusammen funktionieren: Build grün, Launch ohne
Crash, Roboter spawnt korrekt, fällt unter Schwerkraft auf den Boden,
Sim-Zeit fließt nach ROS.

**Erwartetes Verhalten:** Der Roboter erscheint bei `z=0.20 m`, fällt frei,
6 Foot-Kugeln treffen den Boden, Roboter setzt sich auf — vermutlich auf
dem Bauch, weil alle Joints bei Spawn auf 0 rad stehen und damit die Beine
gerade nach außen ragen statt den Körper zu stützen. Das ist in Phase 3
**OK** — Stehen testen wir aktiv erst in Stufe E mit manuell gesetzten
Joint-Winkeln.

**Was wir verifizieren:**
- Welt + Boden korrekt geladen (kein „leere Szene"-Bug, siehe Tabelle in
  `phase_3_gazebo.md`).
- Physik plausibel: Roboter durchschlägt nicht den Boden, kollabiert nicht
  in sich (das wäre ein Inertien- oder Mass-Bug aus Phase 2).
- `/clock` tickt → Bridge funktioniert, ROS und Gazebo teilen sich eine
  Zeitachse.
- `/tf` aktualisiert mit Sim-Zeit-Stempeln → `robot_state_publisher` hat
  `use_sim_time` korrekt übernommen.

**Wenn etwas schiefgeht:** Erst die Stolperfallen-Tabelle in
`phase_3_gazebo.md` durchgehen, **nicht** spekulativ Treiber/System updaten
(siehe CLAUDE.md §5 Goldene Regel). Typische Ursachen sind Pfadfehler im
Launch oder fehlende `<gazebo>`-Tags im URDF.

- [x] `colcon build --packages-select hexapod_description hexapod_gazebo --symlink-install` grün (1.33s gesamt)
- [x] `source install/setup.bash` im Terminal (im Test-Setup pro Bash-Aufruf)
- [x] `ros2 launch hexapod_gazebo sim.launch.py` startet ohne Crash (User-Test, GUI-Modus); im Claude-Terminal nur headless via `world:='-s empty.sdf'` (Snap-Library-Konflikt mit `gz sim gui` in Claude-Shell, in User-Terminal kein Problem)
- [x] Gazebo-Fenster öffnet sich, Welt mit Sun + `ground_plane` sichtbar (User-bestätigt)
- [x] Roboter erscheint bei `z=0.20 m`, fällt unter Schwerkraft auf den Boden (visuell + headless via `gz model -m hexapod -p` → Endpose `z=0.029 m`)
- [x] Roboter durchschlägt **nicht** den Boden (Done-Kriterium 3) — Endpose `z=0.029 > 0`
- [x] Roboter kollabiert nicht in sich (keine Inertien-Explosion) — User-bestätigt; Beine liegen passiv ausgestreckt (kein Controller in Phase 3, erwartet)
- [x] In zweitem Terminal: `ros2 topic list` zeigt `/clock` (+ `/tf`, `/tf_static`, `/robot_description`, `/joint_states`)
- [x] `ros2 topic echo /clock` → tickt mit ~935 Hz (~1 kHz Sim-Step-Rate); Bridge funktioniert (Done-Kriterium 5)
- [x] `/tf_static` zeigt fixe Transforms (foot-Joints); dynamische `/tf`-Updates kommen erst in Phase 4 mit `/joint_states`-Bridging via `gz_ros2_control`
- [x] `use_sim_time=True` auf `/robot_state_publisher` und `/ros_gz_bridge` verifiziert (`ros2 param get`)
- [x] `gz model -l` zeigt `ground_plane` + `hexapod` in Welt `empty`
- [x] KDL-Warning für `base_link` mit Inertia weiterhin vorhanden (aus Phase 2 bekannt, nicht funktional kritisch — Phase-4-Thema)
- [x] Keine Stolperfallen aus der Tabelle aktiv (rutschen/zittern/springen nicht beobachtet)

### Verifikations-Workflow (Stufe D)

So wurde die "läuft alles zusammen?"-Frage zerlegt — Reihenfolge zum
Wiederholen, falls nach späteren Änderungen der Sim-Stack erneut abgenommen
werden muss:

```
  1. Build verify
       └─► colcon build --packages-select hexapod_description hexapod_gazebo
           --symlink-install   (1–2 s erwartet)

  2. Source verify
       └─► source install/setup.bash
           (pro neuem Terminal! sonst kennt ros2 die Pakete nicht)

  3. Launch starten
       ├─ Terminal A:  ros2 launch hexapod_gazebo sim.launch.py
       │              -> Gazebo öffnet sich (GUI-Mode)
       │
       └─ Alternative: headless für reine Topic-Tests
                       ros2 launch hexapod_gazebo sim.launch.py world:='-s empty.sdf'
                       (-s = server only, keine GUI; siehe Hinweis unten)

  4. ROS-Sicht prüfen (Terminal B, gesourced)
       ├─► ros2 topic list                     erwartet: /clock dabei
       ├─► ros2 topic hz /clock --window 100   erwartet: ~1000 Hz (Sim-Step)
       ├─► ros2 topic echo /clock --once       erwartet: sec/nanosec > 0
       ├─► ros2 param get /robot_state_publisher use_sim_time   -> True
       ├─► ros2 param get /ros_gz_bridge use_sim_time           -> True
       └─► ros2 node list                      erwartet: /robot_state_publisher,
                                                         /ros_gz_bridge

  5. Gazebo-Sicht prüfen (Terminal B oder C — gz braucht kein source)
       ├─► gz model --list                     erwartet: ground_plane, hexapod
       ├─► gz model -m hexapod -p              erwartet: z > 0 (kein Durchbruch)
       └─► gz topic -l                         erwartet: /clock, /world/.../...

  6. Sauber stoppen (Terminal A: Ctrl+C; bei Hängern: siehe Cheatsheet unten)
```

**Hinweis zum headless-Workaround `world:='-s empty.sdf'`:**
Funktioniert, weil das LaunchArgument `world` als Suffix an `gz_args` gehängt
wird (`-r ` + `world` ⇒ `-r -s empty.sdf`). Der `-s`-Flag schaltet die GUI
ab und startet nur den Server. Pragmatisch, aber semantisch unsauber —
falls dauerhafte Headless-Unterstützung gewünscht ist, sollte später ein
eigenes `headless`-LaunchArgument ergänzt werden.

### Befehls-Cheatsheet (Stufe D / Inbetriebnahme + Diagnose)

**Pose-Verifikation (kann der Roboter wirklich stehen?):**
```bash
# Aktuelle Modell-Pose abfragen (XYZ + RPY):
gz model -m hexapod -p

# Erwartet in Phase 3 (Body liegt passiv):
#   XYZ: ~ (0, 0, 0.029)   <- Body-Höhe-Hälfte über Boden
#   RPY: ~ 0,0,0           <- nicht gekippt
# z gegen 0 -> Body durchbricht den Boden (Bug)
# z stark schwankend -> kollabiert / explodiert (Inertien-Bug)

# Pose im 1-Hz-Tempo live mitlesen:
gz topic -e -t /world/empty/dynamic_pose/info | head -50
```

**Bridge-Health (tickt /clock?):**
```bash
# Tick-Rate und Stabilität (Sim-Default: 1 kHz)
ros2 topic hz /clock --window 200

# Aktuelle Sim-Zeit ablesen:
ros2 topic echo /clock --once

# Wenn /clock fehlt obwohl Bridge gestartet:
# - bridge.yaml-Pfad falsch? -> ros2 launch ... 2>&1 | grep -i bridge
# - direction: GZ_TO_ROS gesetzt?
# - gz topic -l zeigt /clock auf gz-Seite?
```

**Stop / Cleanup (besonders wichtig nach Crash):**
```bash
# Sauberer Stop:
#   im Launch-Terminal: Ctrl+C einmal -> on_exit_shutdown räumt auf

# Wenn was hängt (z. B. nach Snap-Konflikt):
pkill -INT -f 'ros2 launch hexapod_gazebo'   # SIGINT zuerst (sauber)
sleep 2
pkill -f 'gz sim'                            # Server (überlebt manchmal)
pkill -f 'parameter_bridge'
pkill -f 'robot_state_publisher'

# Verbleibende Prozesse anzeigen:
ps aux | grep -E '(gz sim|parameter_bridge|robot_state|ros_gz)' | grep -v grep
```

**Fault-Tree — wenn etwas nicht stimmt:**

| Symptom | Erste Checks |
|---|---|
| Gazebo-GUI crasht mit `__libc_pthread_init` | Snap-Library-Konflikt, nicht Treiber. `LD_LIBRARY_PATH` prüfen, ob `/snap/...` darin steht. Workaround: headless (`world:='-s empty.sdf'`) oder Snap-Apps deinstallieren, die LD-Pfade setzen. |
| Roboter spawnt nicht | `ros2 topic echo /robot_description --once \| head` — leer? xacro-Fehler. Voll? Spawn-Service-Problem (`gz service -l`, `gz service -i ... /create`). |
| Roboter sinkt durch den Boden | `gz model -m hexapod -p` zeigt `z<0`? Welt ohne `ground_plane` geladen — `gz_args` muss `empty.sdf` enthalten, nicht leere Szene. |
| `/clock` fehlt in `ros2 topic list` | Bridge-Crash. Launch-Output nach `Creating GZ->ROS Bridge` durchsuchen. `bridge.yaml`-Pfad und Permissions prüfen. |
| `/clock` da, aber tickt nicht (`ros2 topic hz` zeigt nichts) | Sim pausiert? `gz service -s /world/empty/control --reqtype gz.msgs.WorldControl --reptype gz.msgs.Boolean --timeout 1000 --req 'pause: false'` |
| RSP `use_sim_time=False` | Parameter wird nicht durchgereicht. Launch-File prüfen: `parameters=[{... 'use_sim_time': True}]` muss als dict-Eintrag drin sein. |
| `tf` zeigt sich nicht aktualisierend | Erwartet in Phase 3! Kein `/joint_states`-Bridging → RSP hat keine Live-Winkel. Kommt mit `gz_ros2_control` in Phase 4. |
| `KDL warning: root link has inertia` | Kosmetisch, aus Phase 2 bekannt. Nicht-blockierend. Fix in Phase 4 mit Dummy-Root-Link erwogen. |

**Fundstellen, wenn was im Launch hakt:**
```bash
# Live-Logs des aktuellen Launches:
tail -f ~/.ros/log/latest/launch.log

# Alle Logs des letzten Runs:
ls -lt ~/.ros/log/ | head -3
ls ~/.ros/log/latest/                        # pro Node ein Verzeichnis
```

---

## Stufe E — Statisches Stehen + RViz-Andockung ⬜

**Ziel:** Done-Kriterien 4 und 6 nachweisen — der Roboter kann unter
Schwerkraft stabil auf seinen 6 Foot-Kugeln stehen, wenn die Joints in
einer geeigneten Stand-Pose festgehalten werden, und das Modell ist auch
in RViz live mit Sim-Zeit sichtbar.

### E.1 Manueller Stand-Test

**Ziel:** Verifizieren, dass die in Stufe B gesetzten Reibungs- und Kontakt-
Werte für ein stabiles Stehen ausreichen. **Manuell**, weil wir noch keinen
Controller haben — die Gazebo-GUI hat einen eingebauten Joint-Slider, mit
dem sich Position-Targets pro Joint setzen lassen.

**Die Test-Pose (`coxa=0`, `femur=-0.5`, `tibia=+1.0`):** Eine grobe
Standard-Hexapod-Pose. Coxa neutral = Beine radial nach außen wie im URDF
modelliert. Femur leicht nach unten, Tibia geknickt — das bringt die Foot-
Kugeln unter den Körper. Die exakten Werte für eine optimale Pose entwickeln
wir erst in Phase 5 (Inverse Kinematik); für Phase 3 reicht „steht stabil
ohne Zittern".

**Erfolgskriterien:** Kein konstantes Zittern (= Inertien/`kp` passen),
kein Wegrutschen der Füße (= `mu1/mu2` passen), kein Kippen (= Schwerpunkt
liegt über dem Stützpolygon der 6 Kontakte). Falls eines davon scheitert,
zeigt die Stolperfallen-Tabelle in `phase_3_gazebo.md` die jeweils
zuständige Stellschraube.

**Warum die finalen Werte ins README:** Phase 4 (`ros2_control`) baut auf
diesen Werten auf. Wenn wir später einen Gait debuggen, müssen wir
nachvollziehen können, mit welcher Reibung das Stehen kalibriert wurde.

- [ ] In Gazebo-GUI Joint-Slider geöffnet (Entity Tree → hexapod → Joints)
- [ ] Test-Pose gesetzt: coxa=0, femur=-0.5 rad, tibia=+1.0 rad (alle 6 Beine)
- [ ] Roboter steht stabil auf 6 Foot-Kugeln, kein konstantes Zittern (Done-Kriterium 4)
- [ ] Kein Wegrutschen → `mu1/mu2`-Werte ausreichend
- [ ] Falls Zittern: `kp` / `inertia_min` schrittweise erhöht und Wert dokumentiert
- [ ] Finale Reibungs-/Kontaktwerte (`mu1`, `mu2`, `kp`, `kd`) im Paket-README dokumentiert

### E.2 RViz optional an Sim andocken

**Ziel:** Done-Kriterium 6 — RViz visualisiert das Modell live aus der Sim,
mit synchronisierter Zeit. Praktisch ist das später beim Debuggen
unverzichtbar: Gazebo zeigt die physikalische Realität, RViz zeigt, was
ROS „glaubt" (tf-Frames, Sensor-Topics, geplante Trajektorien). Diskrepanzen
zwischen beiden Sichten sind oft die schnellste Bug-Quelle.

**`use_sim_time:=true` ist Pflicht:** Ohne diesen Parameter läuft RViz auf
Wall-Clock, während alle Topics Sim-Zeit-Stempel tragen. Ergebnis sind
abgelaufene tf-Lookups („transform from past not available") und ein
eingefrorenes Modell. Gilt für **jeden** ROS-Node, der parallel zur Sim
läuft.

**Optional, weil:** RViz ist hier ein Komfort-Werkzeug, kein Done-Kriterium-
Blocker — Phase 3 funktioniert auch ohne. Aber kostet 30 Sekunden und
spart später Stunden.

- [ ] `rviz2` in zweitem Terminal mit `--ros-args -p use_sim_time:=true` gestartet
- [ ] Fixed Frame auf `base_link` (oder `world`) gesetzt
- [ ] `RobotModel` + `TF` Display zeigt Modell live, synchron zur Sim (Done-Kriterium 6)
- [ ] Bei Joint-Bewegung in Gazebo-GUI bewegt sich RViz-Modell mit

---

## Phasenabschluss ⬜

**Ziel:** Phase formell schließen, sodass Phase 4 sauber starten kann.
Drei Ebenen: technisch (alle Done-Kriterien grün), dokumentarisch
(README + Reibungswerte festgehalten, Workspace-Bericht), prozessual
(Snapshot, Git-Tag, `PHASE.md`-Update, Retro).

**Warum Timeshift-Snapshot vor dem Tag:** Wenn Phase 4 etwas Tiefgreifendes
am URDF oder am Build-System bricht, wollen wir auf den exakten Stand
zurückspringen können — Git allein reicht nicht, weil Build-Artefakte
und installierte ROS-Pakete nicht im Repo liegen.

**Retro nicht überspringen:** Selbst wenn die Phase glatt lief, ist der
„was hat länger gedauert"-Punkt das wertvollste Lessons-Learned-Material
für die nächsten Phasen. Bei Phase 2 z. B. die Coxa-Z-Position — solche
Erkenntnisse gehen sonst beim Phasenwechsel verloren.

- [ ] Alle 6 Done-Kriterien aus `phase_3_gazebo.md` erfüllt:
  - [ ] 1) `hexapod_gazebo` baut
  - [ ] 2) `ros2 launch hexapod_gazebo sim.launch.py` startet Gazebo + Roboter + Bodenebene
  - [ ] 3) Roboter fällt nicht durch den Boden, kollabiert nicht
  - [ ] 4) Bei manuell gesetzten Joint-Winkeln steht der Roboter stabil
  - [ ] 5) `/clock` ist in ROS sichtbar
  - [ ] 6) RViz mit `use_sim_time:=true` zeigt Modell live
- [ ] `README.md` in `hexapod_gazebo/` aktuell (Zweck, Launch-Aufruf, Reibungswerte, Bekannte Stolperfallen)
- [ ] `package.xml` ohne `TODO:`-Stubs
- [ ] Timeshift-Snapshot `phase_3_done` angelegt
- [ ] Git-Commit + Tag `phase-3-done`
- [ ] `PHASE.md` auf Phase 4 aktualisiert (Status: Phase 3 🟢, Phase 4 🟡)
- [ ] Workspace-`README.md` um Phase-3-Bericht ergänzt
- [ ] Retro: Was lief gut, was hat länger gedauert, was bleibt offen

---

## Retro Phase 3

_(wird beim Phasenabschluss befüllt)_

**Was lief gut**
-

**Was hat länger gedauert**
-

**Was bleibt offen**
-
