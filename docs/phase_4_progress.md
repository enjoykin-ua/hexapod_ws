# Phase 4 — Fortschritt

Beim Neustart: diese Datei lesen, dann mit dem ersten offenen Schritt weitermachen.
Stufenplan A–F abgeleitet aus `docs/phase_4_ros2_control.md`.

> **Konvention:** Pro erledigtem Bullet sofort `[ ]`→`[x]` setzen, nicht batchen
> (siehe Memory-Eintrag `feedback_phase_progress_tracking.md`).

> **Aus Phase 3 mitgenommen** (siehe `phase_3_progress.md` Stufe E.1):
> Done-Kriterium 4 (Stand-Test mit `coxa=0/femur=-0.5/tibia=+1.0`) und die
> erste echte Verifikation der Reibungswerte (`mu1=mu2=1.0`, `kp=1e6`,
> `kd=100`) wurden auf Phase 4 deferiert. Beides wird in **Stufe F** abgearbeitet,
> sobald `ros2_control` Joint-Steuerung etabliert hat.

---

## Stufe A — Paket-Skelette `hexapod_control` + `hexapod_bringup` ✅

**Ziel:** Zwei neue ROS2-Pakete neben `hexapod_description` und `hexapod_gazebo`.
Saubere Trennung der Verantwortlichkeiten:

- **`hexapod_control`** trägt die `controllers.yaml` (Reglerkonfiguration).
  Auf Pi und Desktop identisch installiert — die Konfiguration ist
  hardware-unabhängig, weil `ros2_control` über das `HardwareInterface`
  abstrahiert.
- **`hexapod_bringup`** orchestriert ab Phase 4 alle Launch-Files
  (`sim.launch.py`, später `real.launch.py`). Aufgabe: das richtige Set
  Pakete pro Maschine starten. Auf dem Pi würden `hexapod_gazebo` und
  ggf. `hexapod_teleop` schlicht nicht gebaut.

**Was wir machen:** Zwei `ament_cmake`-Pakete erzeugen, Verzeichnis-
struktur (`config/` bzw. `launch/`) anlegen, `package.xml` mit Deps
füllen, leere Builds verifizieren.

**Warum jetzt schon `hexapod_bringup` und nicht erst in Phase 6:**
Sobald wir Controller-Spawner sequenzialisieren müssen, lohnt sich ein
eigenes Paket — sonst wird das Phase-3-`hexapod_gazebo`-Launch zu einem
Monster. Bringup-Layering ist auch das Standard-Pattern in der ROS2-
Community.

**Frage zu klären in Stufe D:** Was passiert mit `hexapod_gazebo/launch/sim.launch.py`?
Optionen werden in Stufe D behandelt — A nimmt nur die neuen Pakete an.

- [x] Tools verifiziert (`ros-jazzy-ros2-control`, `ros-jazzy-ros2-controllers`, `ros-jazzy-controller-manager`, `ros-jazzy-gz-ros2-control`) — `apt list --installed | grep -E 'ros2-control|gz-ros2-control'`
- [x] `ros2 pkg create --build-type ament_cmake --license Apache-2.0 --maintainer-email "noreply@gmx.net" --maintainer-name "enjoykin-ua" hexapod_control` in `src/`
- [x] `ros2 pkg create --build-type ament_cmake --license Apache-2.0 --maintainer-email "noreply@gmx.net" --maintainer-name "enjoykin-ua" hexapod_bringup` in `src/`
- [x] Verzeichnisse `hexapod_control/config/`, `hexapod_bringup/launch/` angelegt; auto-generierte `include/`, `src/` entfernt (Resource-only)
- [x] `hexapod_control/CMakeLists.txt`: `install(DIRECTORY config DESTINATION share/${PROJECT_NAME})`
- [x] `hexapod_bringup/CMakeLists.txt`: `install(DIRECTORY launch DESTINATION share/${PROJECT_NAME})`
- [x] `hexapod_control/package.xml` `<exec_depend>`s: `ros2_control`, `ros2_controllers`, `controller_manager`
- [x] `hexapod_bringup/package.xml` `<exec_depend>`s: `ros_gz_sim`, `ros_gz_bridge`, `hexapod_description`, `hexapod_gazebo`, `hexapod_control`, `xacro`, `robot_state_publisher`, `controller_manager`, `joint_state_broadcaster`, `joint_trajectory_controller`
- [x] `colcon build --packages-select hexapod_control hexapod_bringup` grün (leere Pakete bauen)

---

## Stufe B — URDF um `<ros2_control>`-Block + `gz_ros2_control`-Plugin erweitern ⬜

**Ziel:** Das URDF lernt zwei neue Dinge:
1. Pro Joint ein `<command_interface>` (Position-Soll) und `<state_interface>`
   (Position + Velocity-Ist). Macht den Joint für `ros2_control` greifbar.
2. Ein `<plugin>`-Block, der beim Sim-Start in Gazebo das `gz_ros2_control`-
   System-Plugin lädt — das ist die Brücke, die `controller_manager` in
   den Sim-Prozess einbettet und `controllers.yaml` lädt.

**Was wir machen:** Eine neue Datei `urdf/hexapod.ros2_control.xacro`
anlegen, mit einem Macro `joint_iface(name)`, 18× instanziiert. Plus
das `gz_ros2_control`-Plugin als `<gazebo>`-Block. Top-Level-`hexapod.urdf.xacro`
um den Include erweitern.

**Designentscheidung — Position-only Command-Interface:** Phase 4 nutzt
nur Position-Command, kein Velocity oder Effort. Servo2040 in Phase 7
spricht ebenfalls Position. State-Interfaces (Position + Velocity) sind
breiter, weil sich die meisten Controller darauf stützen.

**Designentscheidung — Joint-Limits aus Konventionen:** Die `<param name="min/max">`
in `command_interface` müssen mit den `<limit>`-Werten in den Joint-
Definitionen (`hexapod_physical_properties.xacro` §11.4) konsistent sein.
Doppeltes Sicherheitsnetz: `controller_manager` clamped auf Interface-
Limits, Gazebo zusätzlich auf Joint-Limits.

**Wichtig — `$(find ...)`-Pfad-Substitution:** Funktioniert in xacro,
weil xacro die Substitution **vor** dem Spawn auflöst. Setzt voraus,
dass `hexapod_control` gebaut und gesourct ist (sonst findet der Spawn
das Paket nicht und der Plugin-Block schlägt fehl).

- [ ] Neue Datei `hexapod_description/urdf/hexapod.ros2_control.xacro` angelegt (xacro-Header)
- [ ] Macro `joint_iface(name, min, max)` mit `<command_interface name="position">` (mit `<param min/max>`) und `<state_interface position>` + `<state_interface velocity>`
- [ ] `<ros2_control name="GazeboSimSystem" type="system">`-Block mit `<plugin>gz_ros2_control/GazeboSimSystem</plugin>`
- [ ] Macro 18× instanziiert (alle Joints, Limits aus `00_conventions.md` §11.4)
- [ ] `<gazebo>`-Block mit `<plugin filename="gz_ros2_control-system" name="gz_ros2_control::GazeboSimROS2ControlPlugin">` + `<parameters>$(find hexapod_control)/config/controllers.yaml</parameters>`
- [ ] In `hexapod.urdf.xacro` am Ende (vor `</robot>`): `<xacro:include filename="hexapod.ros2_control.xacro"/>` mit Kommentar-Banner
- [ ] `xacro hexapod.urdf.xacro > /tmp/hexapod.urdf` läuft fehlerfrei
- [ ] `check_urdf /tmp/hexapod.urdf` weiterhin grün
- [ ] Im generierten URDF: 18× `<joint name="leg_*_*_joint">` innerhalb des `<ros2_control>`-Blocks (`grep -c '<joint name=' /tmp/hexapod.urdf`)
- [ ] Im generierten URDF: 18× `<command_interface name="position"` und 18× `<state_interface name="position"`
- [ ] `colcon build --packages-select hexapod_description` grün (Plugin-Pfad-Auflösung erfordert dass `hexapod_control` aus Stufe A schon installiert ist!)

---

## Stufe C — `controllers.yaml` schreiben ⬜

**Ziel:** Die Konfiguration des `controller_manager` plus aller 7 Controller
(1× JSB + 6× JTC). Diese YAML wird vom `gz_ros2_control`-Plugin geladen
sobald die Sim startet.

**Architektur:**
- **`joint_state_broadcaster` (JSB)** — sammelt aktuelle Positions-/Geschwindigkeits-
  States aller Joints und publisht `/joint_states`. Muss als **erstes** aktiv
  sein, sonst hat RSP keine Live-Werte und `/tf` bleibt leer.
- **6× `joint_trajectory_controller` (JTC), einer pro Bein** — empfängt
  `JointTrajectory`-Goals, fährt zwischen Wegpunkten linear/cubic interpoliert
  ab.

**Designentscheidung — ein Controller pro Bein, nicht einer für alle 18 Joints:**
- Pro: parallel laufende Trajektorien (essentiell für Tripod-Gait, wo
  3 Beine gleichzeitig schwingen während 3 stützen)
- Pro: einzelne Beine isoliert testbar, Hardware-Fehler isoliert
- Contra: 6× YAML-Block — akzeptabel, machen wir per Copy-Paste

**Designentscheidung — `update_rate=100 Hz`:** Standard für Trajectory-Control.
Bei Ruckeln auf 200 Hz erhöhen, bei CPU-Last auf 50 Hz reduzieren. Im
Phase-3-`/clock` lief Sim mit ~1 kHz; 100 Hz Controller-Rate über 1 kHz
Sim-Rate ist sauber (10× Oversampling der Sim).

**`use_sim_time: true` ist Pflicht** — sonst läuft `controller_manager`
auf Wallclock während die Sim Sim-Zeit-Stempel publisht; Trajektorien-
Timeouts greifen falsch.

- [ ] `hexapod_control/config/controllers.yaml` angelegt
- [ ] `controller_manager` Block: `update_rate: 100`, `use_sim_time: true`
- [ ] Controller-Liste unter `controller_manager.ros__parameters`: `joint_state_broadcaster` + `leg_1_controller`..`leg_6_controller` mit Type `joint_trajectory_controller/JointTrajectoryController`
- [ ] Pro Bein-Controller: `joints` (3 Joint-Namen), `command_interfaces: [position]`, `state_interfaces: [position, velocity]`, `state_publish_rate: 50.0`, `action_monitor_rate: 20.0`
- [ ] YAML syntaktisch valide (`yaml.safe_load`)
- [ ] Joint-Namen in `joints`-Listen exakt zu URDF-Namen passend (`grep` Cross-Check gegen generiertes URDF)
- [ ] `colcon build --packages-select hexapod_control` grün; YAML wird nach `install/.../share/hexapod_control/config/` kopiert

---

## Stufe D — Bringup-Launch-File ⬜

**Ziel:** `hexapod_bringup/launch/sim.launch.py` ist ab jetzt der einzige
Launcher für die Sim. Phase-3-`hexapod_gazebo/launch/sim.launch.py`
behalten wir parallel als „Plain-Sim ohne Controller" — nützlich für
Tests, die nur Physik betreffen.

**Was wir machen:** Phase-3-Launch als Basis nehmen, vier neue Spawner-
Knoten ergänzen, Reihenfolge per Event-Handler erzwingen.

**Architektur des erweiterten Launches:**
1. Wie Phase 3: `gz sim`, `robot_state_publisher`, Spawn, Bridge.
2. **Neu:** Sobald der Spawn erfolgreich ist, lädt `gz_ros2_control` das
   Plugin im Sim-Prozess; der `controller_manager` wird darüber verfügbar.
3. **Spawner-Sequenz** (kritisch in der Reihenfolge):
   - Erst `joint_state_broadcaster` aktivieren — sonst hat keiner die
     Joint-States.
   - Dann `leg_1..leg_6_controller`. Können parallel gespawnt werden,
     müssen aber alle nach JSB.
4. **`OnProcessExit`-Event-Handler** sequentialisieren das: JSB-Spawner
   ist One-Shot, beim Exit triggert er die Bein-Controller-Spawner.

**Designfrage — JSP-Krücke aus Phase 3:** Wird **obsolet**. Sobald JSB
aktiv ist, kommt `/joint_states` aus der Sim — die Phase-3-Krücke
(`joint_state_publisher` headless) **darf nicht mehr** gestartet werden,
sonst doppelte Publisher und Konflikte.

**Designentscheidung — `hexapod_gazebo/launch/sim.launch.py` behalten:**
Phase-3-Launcher bleibt als „nur Physik, ohne Controller" für isolierte
URDF-/Reibungs-Debugging-Sessions. `hexapod_bringup/launch/sim.launch.py`
ist die Standard-Variante ab Phase 4.

- [ ] `hexapod_bringup/launch/sim.launch.py` angelegt
- [ ] Basis-Aktionen aus Phase 3 übernommen (xacro→robot_description, gz_sim, RSP, Spawn, Bridge)
- [ ] LaunchArgs übernommen (`urdf`, `world`, `spawn_z`)
- [ ] Spawner-Node `joint_state_broadcaster` über `controller_manager/spawner` (One-Shot)
- [ ] 6× Spawner-Node für `leg_1_controller`..`leg_6_controller`
- [ ] `RegisterEventHandler` mit `OnProcessExit`: JSB-Exit → Bein-Controller-Spawner starten
- [ ] `colcon build --packages-select hexapod_bringup` grün
- [ ] `ros2 launch hexapod_bringup sim.launch.py --print` (Dry-Run) listet alle erwarteten Aktionen ohne Python-Fehler
- [ ] `hexapod_gazebo/launch/sim.launch.py` bleibt unverändert (alternativer „Plain-Sim"-Launcher) und ist im hexapod_gazebo-README dokumentiert

---

## Stufe E — Inbetriebnahme + Controller-Verifikation ⬜

**Ziel:** Done-Kriterien 1–6 aus `phase_4_ros2_control.md` erfüllen.
Sim läuft, Controller sind aktiv, ein einzelner Joint reagiert auf
ein manuelles Trajektorien-Goal.

**Was wir verifizieren:**
- **Kriterium 1:** `hexapod_control` baut (in Stufe A erledigt — hier nur
  bestätigen).
- **Kriterium 2:** beim Launch alle 7 Controller hochgefahren.
- **Kriterium 3:** `ros2 control list_controllers` zeigt alle als `active`.
- **Kriterium 4:** `ros2 control list_hardware_interfaces` listet 18
  Position-Command + 18 Position-State + 18 Velocity-State Interfaces.
- **Kriterium 5:** Bewegungstest auf einem Bein.
- **Kriterium 6:** `/joint_states` publisht Live-Werte aller 18 Joints.

**Wichtige Erwartungs-Klarstellung:** Der RViz-`base_link → coxa → femur → tibia`-
Tree ist jetzt **ohne JSP-Krücke** vollständig — `gz_ros2_control` plus JSB
liefert echte Live-`/joint_states`, RSP rechnet daraus `/tf`, RViz folgt
Gazebo synchron. Damit ist auch die Erwartung „RViz-Modell bewegt sich
mit Gazebo" aus Phase 3 (deferiert in E.2) jetzt **erfüllt**.

- [ ] `colcon build --packages-select hexapod_description hexapod_gazebo hexapod_control hexapod_bringup --symlink-install` grün
- [ ] `source install/setup.bash`
- [ ] `ros2 launch hexapod_bringup sim.launch.py` startet ohne Crash; alle 4 Sim-Komponenten + JSB-Spawner + 6 JTC-Spawner laufen durch
- [ ] `ros2 control list_controllers` → `joint_state_broadcaster` (active), `leg_1_controller`..`leg_6_controller` (alle active)
- [ ] `ros2 control list_hardware_interfaces` → 18 `available command interfaces` (position) + 36 `available state interfaces` (18 position + 18 velocity)
- [ ] `ros2 topic list` zeigt `/joint_states` + 6× `/leg_*_controller/joint_trajectory`
- [ ] `ros2 topic echo /joint_states --once` → 18 Joint-Namen, alle Positionen ~0 (Default-Pose)
- [ ] Manueller Bewegungstest: `ros2 topic pub --once /leg_1_controller/joint_trajectory ...` mit Ziel `[0.3, -0.5, 1.0]`, `time_from_start=2s`; Bein 1 in Gazebo bewegt sich sichtbar
- [ ] In RViz mit `use_sim_time:=true`: Modell folgt Gazebo synchron (Phase-3-E.2-Defer eingelöst); JSP-Krücke ist obsolet und **nicht** zu starten
- [ ] Zweiter Bewegungstest auf einem anderen Bein (z. B. Bein 4) zur Bestätigung der Symmetrie

---

## Stufe F — Phase-3-Defers einsammeln: Stand-Test + Reibungswerte verifizieren ⬜

**Ziel:** Done-Kriterium 4 aus Phase 3 nachholen. Roboter steht stabil
auf seinen 6 Foot-Kugeln in der Test-Pose, Reibungswerte sind unter
echter Last verifiziert (oder nachjustiert).

**Vorgehen:**
1. Stand-Pose `coxa=0`, `femur=-0.5`, `tibia=+1.0` auf alle 6 Beine
   gleichzeitig fahren — am sinnvollsten als ein Mini-Skript oder via
   gemeinsamer Trajektorie pro Bein-Controller.
2. Roboter beobachten: steht er stabil? Zittert er? Rutschen Beine weg?
3. Numerische Stabilität verifizieren: `gz model -m hexapod -p` über
   5 Sekunden hinweg konstant (`z`, `RPY` ändern sich um < 1 mm/0.5°)?

**Falls Probleme — Stellschrauben (Reihenfolge):**
- **Wegrutschen** → `mu1`, `mu2` von `1.0` auf `1.5` in
  `hexapod.gazebo.xacro`.
- **Zittern** → `kp` von `1e6` auf `1e7`; falls weiterhin: `inertia_min`
  von `1e-5` auf `1e-4` in `inertials.xacro`.
- **Beine geben unter Last nach** → Controller-PID zu schwach;
  Trajektorien-Goal mit längerer `time_from_start` testen, ggf. JTC-
  Position-Gains in `controllers.yaml` setzen (default funktioniert oft).
- **Roboter springt beim Pose-Anfahren** → Trajektorie zu schnell;
  `time_from_start` von 2s auf 4s erhöhen.

**Doku-Folge:** Wenn Werte passen → in `hexapod_gazebo/README.md` den
„noch nicht verifiziert"-Abschnitt durch verifizierte Werte ersetzen.
Wenn Werte angepasst wurden → in `hexapod.gazebo.xacro` ändern und
kurz im Phase-4-Bericht festhalten.

- [ ] Stand-Pose-Skript / Multi-Trajectory: alle 6 Beine fahren auf `coxa=0/femur=-0.5/tibia=+1.0` in 4 s
- [ ] Roboter sitzt nach Pose-Setting auf 6 Foot-Kugeln (nicht auf dem Bauch); visuell verifiziert
- [ ] `gz model -m hexapod -p` zeigt konstante Pose über 5 s (Drift `< 1 mm` / `< 0.5°`)
- [ ] Kein sichtbares Zittern oder Wegrutschen
- [ ] Reibungswerte (`mu1`, `mu2`, `kp`, `kd`) **verifiziert** oder **nachjustiert**; Werte im `hexapod_gazebo/README.md` aktualisiert (Defer-Hinweis durch verifizierte Werte ersetzt)
- [ ] `inertia_min` ggf. nachgezogen in `inertials.xacro` (falls Zittern)
- [ ] Memory-Eintrag `project_phase3_defer_stand_test.md` als „erledigt" markiert oder gelöscht
- [ ] Phase-3-Done-Kriterium 4 in `phase_3_progress.md` und Workspace-`README.md` von ⏸ auf ✅ aktualisieren (mit Verweis auf Phase-4-Verifikation)

---

## Phasenabschluss ⬜

**Ziel:** Phase 4 formell schließen. Drei Ebenen wie immer: technisch
(Done-Kriterien grün), dokumentarisch (READMEs + Workspace-Bericht),
prozessual (Snapshot, Git-Tag, `PHASE.md`-Update, Retro).

**Optional in dieser Phase mit erledigen:**
- **KDL-Warning** (`base_link has inertia, but KDL does not support root link with inertia`)
  aus Phase 2/3 — wenn der RSP-Output stört oder im Phase-5-Debugging
  blendet, hier mit Dummy-Root-Link fixen. Sonst auf Phase 5 schieben.

**Was Phase 4 NICHT macht** (gemäß `phase_4_ros2_control.md`):
- Keine IK (Phase 5)
- Keine Gait-Engine (Phase 5)
- Kein Teleop (Phase 6)
- Kein Custom-Controller (`JointTrajectoryController` reicht)

- [ ] Alle 6 Done-Kriterien aus `phase_4_ros2_control.md` erfüllt:
  - [ ] 1) `hexapod_control` baut
  - [ ] 2) Beim Launch sind `joint_state_broadcaster` + 6× `joint_trajectory_controller` aktiv
  - [ ] 3) `ros2 control list_controllers` zeigt alle Controller `active`
  - [ ] 4) `ros2 control list_hardware_interfaces` zeigt 18 Position-Command + 18 Position-State (+ 18 Velocity-State)
  - [ ] 5) Manueller Trajectory-Goal bewegt Bein 1 sichtbar in Gazebo
  - [ ] 6) `/joint_states` zeigt aktuelle Positionen aller 18 Joints
- [ ] Bewegungstest auf mindestens zwei Beinen erfolgreich (Stufe E)
- [ ] **Phase-3-Defers eingelöst:** Stand-Test bestanden, Reibungswerte verifiziert/nachjustiert (Stufe F)
- [ ] `README.md` in `hexapod_control/` und `hexapod_bringup/` aktuell (Zweck, Launch-Aufruf, Controller-Liste, bekannte Stolperfallen)
- [ ] `hexapod_gazebo/README.md` Defer-Hinweis durch verifizierte Reibungswerte ersetzt
- [ ] `package.xml` in beiden neuen Paketen ohne `TODO:`-Stubs
- [ ] (optional) KDL-Warning gefixt mit Dummy-Root-Link, sonst auf Phase 5 schieben (im README dokumentieren)
- [ ] Timeshift-Snapshot `phase_4_done` angelegt — **User-Aufgabe**
- [ ] Git-Commit + Tag `phase-4-done` — **User-Aufgabe**
- [ ] `PHASE.md` auf Phase 5 aktualisiert (Status: Phase 4 🟢, Phase 5 🟡)
- [ ] Workspace-`README.md` um Phase-4-Bericht ergänzt
- [ ] Retro: Was lief gut, was hat länger gedauert, was bleibt offen

---

## Retro Phase 4

_(wird beim Phasenabschluss befüllt)_

**Was lief gut**
-

**Was hat länger gedauert**
-

**Was bleibt offen**
-
