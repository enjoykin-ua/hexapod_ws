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

## Stufe C — Bridge-Config + Launch-File ⬜

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

- [ ] `hexapod_gazebo/config/bridge.yaml` angelegt mit nur `/clock` (`GZ_TO_ROS`, `rosgraph_msgs/msg/Clock` ↔ `gz.msgs.Clock`)
- [ ] YAML syntaktisch valide (`python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))' bridge.yaml`)

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

- [ ] `hexapod_gazebo/launch/sim.launch.py` angelegt
- [ ] xacro → `robot_description` via `Command(['xacro ', PathJoinSubstitution([..., 'urdf', 'hexapod.urdf.xacro'])])`
- [ ] `IncludeLaunchDescription` für `ros_gz_sim/launch/gz_sim.launch.py` mit `gz_args='-r empty.sdf'`
- [ ] `robot_state_publisher`-Node mit `use_sim_time: True`
- [ ] Spawn-Node `ros_gz_sim/create` mit `-topic /robot_description -name hexapod -z 0.20`
- [ ] Bridge-Node `ros_gz_bridge/parameter_bridge` mit `config_file=…/bridge.yaml`
- [ ] LaunchArgument für URDF-Pfad optional, Default = `hexapod_description`-Share-Path
- [ ] `colcon build --packages-select hexapod_gazebo` grün
- [ ] `ros2 launch hexapod_gazebo sim.launch.py --print` (Dry-Run) listet alle 4 Aktionen ohne Python-Fehler

---

## Stufe D — Erste Inbetriebnahme ⬜

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

- [ ] `colcon build --packages-select hexapod_description hexapod_gazebo` grün
- [ ] `source install/setup.bash` im Terminal
- [ ] `ros2 launch hexapod_gazebo sim.launch.py` startet ohne Crash
- [ ] Gazebo-Fenster öffnet sich, Welt mit Sun + `ground_plane` sichtbar
- [ ] Roboter erscheint bei `z=0.20 m`, fällt unter Schwerkraft auf den Boden
- [ ] Roboter durchschlägt **nicht** den Boden (Done-Kriterium 3)
- [ ] Roboter kollabiert nicht in sich (keine Inertien-Explosion)
- [ ] In zweitem Terminal: `ros2 topic list` zeigt `/clock`
- [ ] `ros2 topic echo /clock` → tickt → Bridge funktioniert (Done-Kriterium 5)
- [ ] `ros2 topic echo /tf` zeigt aktualisierte Transforms (rsp läuft mit `use_sim_time`)
- [ ] Stolperfallen-Tabelle gegengeprüft, falls Symptome auftreten — Fixes dokumentiert in README

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
