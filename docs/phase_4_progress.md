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

## Stufe B — URDF um `<ros2_control>`-Block + `gz_ros2_control`-Plugin erweitern ✅

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

- [x] Neue Datei `hexapod_description/urdf/hexapod.ros2_control.xacro` angelegt (xacro-Header)
- [x] Macro `joint_iface(name, min, max)` mit `<command_interface name="position">` (mit `<param min/max>`) und `<state_interface position>` + `<state_interface velocity>` _(Param-Namen `lower`/`upper` statt `min`/`max`, wiederverwendet die Properties aus `hexapod_physical_properties.xacro`)_
- [x] `<ros2_control name="GazeboSimSystem" type="system">`-Block mit `<plugin>gz_ros2_control/GazeboSimSystem</plugin>`
- [x] Macro 18× instanziiert (alle Joints, Limits aus `00_conventions.md` §11.4)
- [x] `<gazebo>`-Block mit `<plugin filename="gz_ros2_control-system" name="gz_ros2_control::GazeboSimROS2ControlPlugin">` + `<parameters>$(find hexapod_control)/config/controllers.yaml</parameters>`
- [x] In `hexapod.urdf.xacro` am Ende (vor `</robot>`): `<xacro:include filename="hexapod.ros2_control.xacro"/>` mit Kommentar-Banner
- [x] `xacro hexapod.urdf.xacro > /tmp/hexapod.urdf` läuft fehlerfrei
- [x] `check_urdf /tmp/hexapod.urdf` weiterhin grün (`base_link has 6 child(ren)`, alle 6 Beine vollständig)
- [x] Im generierten URDF: 18× `<command_interface name="position"` und 18× `<state_interface name="position"` (`<command_interface>` kommt nur im `<ros2_control>`-Block vor → eindeutiger Beleg für 18 ros2_control-Joint-Refs) — zusätzlich verifiziert: 18× `<state_interface name="velocity"`, 1× `<ros2_control>`-Block, 1× `gz_ros2_control-system`-Plugin
- [x] `colcon build --packages-select hexapod_description` grün (Plugin-Pfad-Auflösung erfordert dass `hexapod_control` aus Stufe A schon installiert ist!)

### Umsetzungsnotizen Stufe B

**Datei-Layout:** Separate Datei `hexapod.ros2_control.xacro` neben dem
schon existierenden `hexapod.gazebo.xacro` — gleiches Pattern (eigene
xacro-Datei, am Ende von `hexapod.urdf.xacro` per `<xacro:include>`
eingebunden, Banner-Kommentar). Konsistent zur Phase-2/3-Struktur.

**Macro-Signatur:** `joint_iface(name, lower, upper)` statt der im Plan
formulierten `(name, min, max)`. Grund: die Param-Namen `lower`/`upper`
matchen die existierenden Properties (`coxa_lower`, `coxa_upper`, ...) in
`hexapod_physical_properties.xacro` und vermeiden mentales Umsortieren
beim Lesen. Im URDF werden die Werte trotzdem in `<param name="min">`
und `<param name="max">` geschrieben (das ist die ros2_control-Schema-
Vorgabe und nicht verhandelbar).

**Limit-Werte — keine Duplikation:** Die 18 Macro-Aufrufe übergeben
`${coxa_lower}` / `${coxa_upper}` / `${femur_*}` / `${tibia_*}` aus den
existierenden Properties. Das hält §11.4 (00_conventions.md) als
Single Source of Truth — wenn dort jemand Limits ändert, ändern sich
sowohl die mechanischen `<limit>`-Werte (über `leg.xacro`) als auch
die ros2_control-`<param min/max>` automatisch mit. Doppeltes
Sicherheitsnetz bleibt, doppelte Wartung wird vermieden.

**Macro-Layout im Block:** 6 Bein-Gruppen à 3 Aufrufe (`coxa`, `femur`,
`tibia`), durch Kommentar `<!-- Bein N -->` getrennt. Lesbarer als 18
flache Aufrufe, gleiches Muster wie `<xacro:foot_friction id="N"/>` in
`hexapod.gazebo.xacro` (dort allerdings noch kompakter mit `id`-Param).
Bewusste Entscheidung gegen ein zusätzliches Bein-Wrapper-Macro: in
einem Resource-File ist explizite Aufzählung der 18 Joint-Namen
auditierbar (man sieht direkt, welche Joints angemeldet sind).

**Plugin-Block:** `gz_ros2_control-system` mit `$(find hexapod_control)`
für den controllers.yaml-Pfad. `$(find ...)` wird **nicht** zur xacro-
Zeit aufgelöst (bleibt als Text-String im generierten URDF), sondern
erst beim Sim-Start vom `gz_ros2_control`-Plugin. Daher braucht es
beim `xacro`-/`check_urdf`-Test keine gesourctes `hexapod_control` —
das wird erst in Stufe E (Spawn) wichtig.

**grep-Bullet-Bereinigung:** Der ursprüngliche Bullet
`grep -c '<joint name=' = 18` war falsch (zählt mech. Joints +
ros2_control-Refs zusammen, also nicht 18). Durch User-Entscheidung
(Option B) gestrichen. Beleg für die 18 ros2_control-Joint-Refs liegt
jetzt eindeutig beim `command_interface`-Check (`command_interface`
kommt nur im `<ros2_control>`-Block vor, keine Mehrdeutigkeit).
Zusätzliche Stichproben-Counts (`state_interface velocity`, Anzahl
`<ros2_control>`-Blöcke, `gz_ros2_control-system`-Plugin) als
Querprüfung mitverifiziert.

**Was Stufe B explizit NICHT macht:**
- Keine `controllers.yaml` (Stufe C)
- Keine Launch-Anpassung (Stufe D)
- Kein Sim-Lauftest mit aktivem Plugin (Stufe E)
- Kein Bewegungstest auf einem Joint (Stufe E)

---

## Stufe C — `controllers.yaml` schreiben ✅

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

- [x] `hexapod_control/config/controllers.yaml` angelegt
- [x] `controller_manager` Block: `update_rate: 100`, `use_sim_time: true`
- [x] Controller-Liste unter `controller_manager.ros__parameters`: `joint_state_broadcaster` + `leg_1_controller`..`leg_6_controller` mit Type `joint_trajectory_controller/JointTrajectoryController`
- [x] Pro Bein-Controller: `joints` (3 Joint-Namen), `command_interfaces: [position]`, `state_interfaces: [position, velocity]`, `state_publish_rate: 50.0`, `action_monitor_rate: 20.0`
- [x] YAML syntaktisch valide (`yaml.safe_load`)
- [x] Joint-Namen in `joints`-Listen exakt zu URDF-Namen passend (Set-Diff URDF↔YAML: 18=18, leere Differenz in beide Richtungen, exakter MATCH)
- [x] `colcon build --packages-select hexapod_control` grün; YAML wird nach `install/.../share/hexapod_control/config/` kopiert

### Umsetzungsnotizen Stufe C

> **Konzept-Hintergrund** (was die Datei ist, wer sie liest, Lifecycle,
> CLI-Befehle, Phasen-übergreifende Nutzung): siehe
> [phase_4_controllers_explained.md](phase_4_controllers_explained.md).
> Dort steht alles, was über die reine Implementierung hinausgeht und
> auch in Phase 5-7 noch als Nachschlagewerk dient.

**YAML-Aufbau — zwei Schichten:** Oben `controller_manager:` mit
`update_rate`, `use_sim_time` und der **Typdeklarations-Liste** der 7
Controller (JSB + 6× JTC). Unten 6× Top-Level-Block `leg_N_controller:`
mit der eigentlichen Konfiguration (`joints`, `command_interfaces`,
`state_interfaces`, Publish-Rates). Das ist die ROS2-Standardstruktur:
ein Top-Level-Key pro Knoten mit `ros__parameters` darunter.

**Stilentscheidung — explizit ausgeschriebene 6 Bein-Blöcke:** Bewusst
keine YAML-Anchors (`&jtc_defaults` / `*jtc_defaults`). Gründe:
- ROS2-Parameter-Loader haben mit Anchors gelegentlich Macken
- Alle ros2_control-Tutorials/Beispiele schreiben es explizit aus
- Auditierbarkeit: man sieht direkt, welche 3 Joint-Namen in welchem
  Bein-Controller stehen, ohne Anchor-Auflösung im Kopf

Resultat: ~95 Zeilen YAML, davon ~50 Zeilen reine Wiederholung. Akzeptabel.

**`use_sim_time: true` als Phase-7-Schuld:** In Phase 4-6 (Sim-only)
korrekt. Phase 7 (echte HW) braucht `false` — das wird dann entweder
per Launch-Argument überschrieben oder eine separate `controllers.real.yaml`
angelegt. Kommentar im YAML weist explizit darauf hin, damit das in
Phase 7 nicht übersehen wird.

**Was bewusst NICHT in der YAML steht:**
- **Keine PID-/Position-Gains** für die JTC. Default-Mode des JTC ist
  Open-Loop-Trajektorien-Interpolation (Joint-Position-Soll wird
  direkt durchgereicht). Reicht für den manuellen Bewegungstest in
  Stufe E. Wenn Stufe F (Stand-Test unter Last) Probleme zeigt,
  Gains dort nachjustieren.
- **Kein expliziter `joints`-Filter beim JSB.** Ohne Filter publisht
  JSB alle Joints, die der `controller_manager` kennt — das sind
  unsere 18 aus dem `<ros2_control>`-Block. Genau der gewünschte Effekt.
- **Keine `interface_name`-Override beim JSB.** Default greift sich
  `position`+`velocity` von allen verfügbaren `<state_interface>`s ab
  (siehe Stufe B: 18 position + 18 velocity).

**Cross-Check als Set-Diff:** Statt `grep` (textbasiert, fehleranfällig
bei Whitespace/Anführungszeichen) ein Python-Snippet, das beide
Joint-Listen in `set()` lädt und Differenzen in beide Richtungen
ausgibt. Resultat: `MATCH=True`, `len=18=18`, beide Diffs leer.

**`$(find hexapod_control)`-Ende-zu-Ende:** Die YAML ist jetzt unter
`install/hexapod_control/share/hexapod_control/config/controllers.yaml`
deployed. Damit löst der Plugin-Block aus Stufe B (`<parameters>$(find
hexapod_control)/config/controllers.yaml</parameters>`) ab Stufe E
korrekt auf — vorausgesetzt `install/setup.bash` ist beim Sim-Start
gesourct.

**Was Stufe C explizit NICHT macht:**
- Kein Launch (Stufe D)
- Kein Spawner-Aufruf (Stufe D)
- Kein Sim-Test mit aktiver YAML (Stufe E)
- Keine PID-Tuning-Iteration (ggf. Stufe F)

---

## Stufe D — Bringup-Launch-File ✅

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

- [x] `hexapod_bringup/launch/sim.launch.py` angelegt
- [x] Basis-Aktionen aus Phase 3 übernommen (xacro→robot_description, gz_sim, RSP, Spawn, Bridge)
- [x] LaunchArgs übernommen (`urdf`, `world`, `spawn_z`)
- [x] Spawner-Node `joint_state_broadcaster` über `controller_manager/spawner` (One-Shot)
- [x] 6× Spawner-Node für `leg_1_controller`..`leg_6_controller`
- [x] `RegisterEventHandler` mit `OnProcessExit`: JSB-Exit → Bein-Controller-Spawner starten _(zweistufige Sequenz: Spawn-Exit → JSB → JSB-Exit → 6× Bein-Spawner; Option 2)_
- [x] `colcon build --packages-select hexapod_bringup` grün
- [x] `ros2 launch hexapod_bringup sim.launch.py --print` (Dry-Run) listet alle erwarteten Aktionen ohne Python-Fehler (3× DeclareLaunchArgument, 1× IncludeLaunchDescription, 3× ExecuteProcess + 2× RegisterEventHandler mit verschachtelten Spawnern verifiziert)
- [x] `hexapod_gazebo/launch/sim.launch.py` bleibt unverändert (alternativer „Plain-Sim"-Launcher) und ist im hexapod_gazebo-README dokumentiert (Hinweis-Box oben in `hexapod_gazebo/README.md`)

### Umsetzungsnotizen Stufe D

> **Konzept-Hintergrund** (Launch-File-Aufbau, Substitutions, Spawner-
> Pattern, Event-Handler, `ParameterValue(value_type=str)`-Gotcha,
> `--print`-Dry-Run, wie der Launch in Phase 5/6/7 erweitert wird):
> siehe [phase_4_launch_explained.md](phase_4_launch_explained.md).

**Strukturentscheidung — Phase-3-Launch 1:1 übernommen + erweitert:**
Der Phase-3-Launch [hexapod_gazebo/launch/sim.launch.py](../src/hexapod_gazebo/launch/sim.launch.py)
ist sauber strukturiert. Die 7 dortigen Aktionen (3× DeclareLaunchArgument
+ 1× IncludeLaunchDescription für gz_sim + 3× Node für RSP/Spawn/Bridge)
werden 1:1 übernommen, inklusive `ParameterValue(value_type=str)`-Wrapping
um den `Command(['xacro ', ...])`-Aufruf (verhindert YAML-Parse-Versuch
von rclpy auf den URDF-String). LaunchArgs (`urdf`, `world`, `spawn_z`)
und ihre Defaults bleiben identisch — User-Aufrufe wie
`spawn_z:=1.5` funktionieren weiter wie in Phase 3.

**Sequenzialisierung — zweistufige `OnProcessExit`-Kette (Option 2):**
Standard-ros2_control-Pattern statt einstufiger Variante.

```
gz_sim, RSP, spawn, bridge   (parallel beim Launch-Start)
        spawn-Exit ─► JSB-spawner
                         JSB-Exit ─► leg_1..leg_6 spawner (parallel)
```

Begründung gegen die einstufige Variante (JSB-Spawner sofort beim
Launch-Start mit Re-Tries): Re-Try-Spam in den Logs verstellt die
Sicht auf echte Probleme, und dieses Pattern ist in jedem
ros2_control-Tutorial der Standard. Kostenpunkt: **eine** zusätzliche
Codezeile (zweiter `RegisterEventHandler`).

**Spawner-Nodes nicht in `LaunchDescription`-Liste:** Stattdessen
nur die zwei `RegisterEventHandler`. Wenn die Spawner direkt in der
Liste stünden, würden sie sofort beim Launch-Start parallel zu allem
anderen gestartet — genau das, was wir mit Option 2 vermeiden wollen.

**Bein-Spawner per List-Comprehension generiert:** Statt 6× Copy-
Paste-Node-Definitionen.

```python
leg_controller_spawners = [
    Node(
        package='controller_manager',
        executable='spawner',
        name=f'spawn_leg_{i}_controller',
        arguments=[f'leg_{i}_controller', '--controller-manager', '/controller_manager'],
        output='screen',
    )
    for i in range(1, 7)
]
```

Bewusst kompakt, weil pro Bein nichts variiert außer der ID. Wenn
in Phase 5+ pro Bein unterschiedliche Spawner-Args nötig werden
(z. B. PID-Profile pro Bein), kann das aufgelöst werden.

**Kein neues Bridge-Mapping für `/joint_states`:** Die Phase-3-Bridge
(`bridge.yaml` mit nur `/clock`) bleibt unverändert. Grund: sobald
`gz_ros2_control` plus JSB läuft, publisht JSB `/joint_states` direkt
als ROS-Topic im Sim-Prozess — keine `gz↔ros`-Bridge nötig dafür.
Wäre eine doppelte Quelle, wenn man's trotzdem konfiguriert.

**`hexapod_gazebo/README.md`-Update:** Hinweis-Box oben rein, dass
Phase-4-Bringup ab jetzt der Standard ist und der Phase-3-Launcher
bewusst als „Plain-Sim ohne Controller" für Physik-/Reibungs-Debugging
erhalten bleibt. Die JSP-Krücken-Sektion bleibt stehen — wird in der
Phase-4-Variante obsolet, ist aber für Plain-Sim-Sessions weiterhin
relevant.

**Verifikation `--print`:** Dry-Run zeigt korrekte Struktur:
3× `DeclareLaunchArgument`, 1× `IncludeLaunchDescription` (gz_sim),
3× `ExecuteProcess` (RSP, spawn_hexapod, ros_gz_bridge),
1× `RegisterEventHandler` mit `OnProcessExit` und 1× nested Spawner
(JSB), 1× `RegisterEventHandler` mit `OnProcessExit` und 6× nested
Spawnern (leg_1..leg_6_controller). Was `--print` **nicht** prüft:
tatsächlicher Sim-Start, Plugin-Auflösung, Controller-Aktivierung —
das alles ist Stufe E.

**Was Stufe D explizit NICHT macht:**
- Kein echter Sim-Start (Stufe E)
- Kein `ros2 control list_controllers`-Check (Stufe E)
- Kein Bewegungstest (Stufe E)
- Kein RViz-Integration (separat startbar; falls in Phase 5+ ein
  `display:=true` LaunchArg gewünscht ist, dort ergänzen)

---

## Stufe E — Inbetriebnahme + Controller-Verifikation ✅

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

- [x] `colcon build --packages-select hexapod_description hexapod_gazebo hexapod_control hexapod_bringup --symlink-install` grün (4 packages finished, keine Fehler)
- [x] `source install/setup.bash` _(Vorbereitung in allen 3 Terminals durch User)_
- [x] `ros2 launch hexapod_bringup sim.launch.py` startet ohne Crash; alle 4 Sim-Komponenten + JSB-Spawner + 6 JTC-Spawner laufen durch _(Roboter liegt erwartungsgemäß auf dem Bauch — Default-Pose alle Joints=0 heißt Beine horizontal ausgestreckt. Stand auf Foot-Kugeln kommt erst in Stufe F mit `coxa=0/femur=-0.5/tibia=+1.0`)_
- [x] `ros2 control list_controllers` → `joint_state_broadcaster` (active), `leg_1_controller`..`leg_6_controller` (alle active) — bestätigt
- [x] `ros2 control list_hardware_interfaces` → 18 `available command interfaces` (position) + 36 `available state interfaces` (18 position + 18 velocity) — bestätigt; alle 18 command interfaces zusätzlich `[claimed]` (JTCs halten ihre Interfaces aktiv)
- [x] `ros2 topic list` zeigt `/joint_states` + 6× `/leg_*_controller/joint_trajectory` — exakt 7 Zeilen, bestätigt
- [x] `ros2 topic echo /joint_states --once` → 18 Joint-Namen, alle Positionen ~0 (Default-Pose) — bestätigt; coxa/tibia ~0 (FP-Noise e-19), femur ~0.012 rad (Bodenkontakt-Penetration der Bauch-Pose, harmlos), velocity ~0 (steht still), effort=NaN (erwartet — kein effort-State-Interface deklariert, JSB füllt Slot mit NaN)
- [x] Manueller Bewegungstest: `ros2 topic pub --once /leg_1_controller/joint_trajectory ...` mit Ziel `[0.3, -0.5, 1.0]`, `time_from_start=2s`; Bein 1 in Gazebo bewegt sich sichtbar — bestätigt; Bein 1 fährt smooth in 2s, Hexapod hebt sich auf einer Seite an
- [x] In RViz mit `use_sim_time:=true`: Modell folgt Gazebo synchron (Phase-3-E.2-Defer eingelöst); JSP-Krücke ist obsolet und **nicht** zu starten — bestätigt; RViz folgt allen Bein-Bewegungen live
- [x] Zweiter Bewegungstest auf einem anderen Bein (z. B. Bein 4) zur Bestätigung der Symmetrie — bestätigt; zusätzlich Multi-Bein-Tests 7b (Reset auf Ursprung, alle 6 synchron) und 7c (alle 6 angehoben mit `[0.3, -1.0, 1.5]`) durchgeführt; Bein-Bewegungen synchron, Körperhöhe stieg dabei aber **nicht linear** mit den Joint-Werten (geometrisches IK-Verhalten — siehe Notizen)

### Umsetzungsnotizen Stufe E

> **Test-Anleitung** (User-Operations-Handbuch mit allen Befehlen pro
> Terminal, Erwartungen, Status-Format): siehe
> [phase_4_stage_E_test_commands.md](phase_4_stage_E_test_commands.md).

**Vorgehensweise — interaktiv mit klarer Rollen-Aufteilung:** Im Gegensatz
zu A-D (alles per Bash-Tool durch Claude ausführbar) erforderte E erstmals
echte Sim-Ausführung mit GUI. Lösung: User führt alle Befehle in eigenen
Terminals aus, Claude wartet auf knappe Status-Rückmeldungen. Vorteil:
Claude-Kontext bleibt schlank (Sim + 7 Spawner würden hunderte Log-Zeilen
liefern); User hat klare Schritt-für-Schritt-Anweisung. Memory-Eintrag
[feedback_interactive_stage_test_doc.md](file:///home/enjoykin/.claude/projects/-home-enjoykin-hexapod-ws/memory/feedback_interactive_stage_test_doc.md)
für zukünftige Live-Stufen (Phase 7 HW-Tests).

**Test-Schritte 1-7:**
- Schritt 1 — Full Build (4 Pakete, `--symlink-install` für YAML/Launch-
  Live-Reload) → grün
- Schritt 2 — Sim-Start; Hexapod fällt aus 0.20 m, **liegt auf dem Bauch**
  (erwartetes Verhalten bei Default-Pose alle Joints=0); alle 7 Spawner
  durchgelaufen
- Schritt 3 — `list_controllers` 7 active, `list_hardware_interfaces`
  18 cmd `[claimed]` + 36 state, `topic list` 7 erwartete Topics
- Schritt 4 — `/joint_states`-Echo: 18 Joints, coxa/tibia ~0 (FP-Noise
  e-19), femur ~0.012 rad (Bauch-Bodenkontakt-Penetration, harmlos),
  velocity ~0, **effort=NaN** (erwartet — kein effort-State-Interface
  deklariert; JSB füllt Slot mit NaN)
- Schritt 5 — Bewegungstest Bein 1 mit `[0.3, -0.5, 1.0]` über 2 s →
  smooth Bewegung, Hexapod hebt sich einseitig
- Schritt 6 — RViz parallel mit `use_sim_time:=true`, RobotModel +
  Fixed Frame `base_link` → folgt Gazebo synchron, Phase-3-E.2-Defer
  („RViz-Modell folgt Gazebo") damit eingelöst
- Schritt 7 — Bein-4-Symmetrie-Test (7a) + Multi-Bein-Tests (7b Reset,
  7c „doppelt anheben" auf `[0.3, -1.0, 1.5]`) → alle 6 Beine fahren
  synchron via `for...&;wait`-Pattern

**Erkenntnis aus Schritt 7c — Geometrie ist nichtlinear:** „Doppelt so
hohe Joint-Werte" ≠ doppelt so hoher Körper. Bei tibia=1.5 (am Limit)
knickt das Bein so stark ein, dass der Foot näher zum Coxa-Joint zieht
statt einfach „länger nach unten" zu reichen. Folge: Körper hebt sich
weniger als naiv erwartet. Die Auflösung kommt mit echter inverser
Kinematik in Phase 5 — dort gibt man eine Wunschhöhe vor und IK rechnet
die passenden Joint-Winkel rückwärts.

**`A message was lost!!!`-Warning bei `--once`:** bekannter ros2-CLI-
Warnhinweis, irrelevant — der Subscriber wird kurz nach dem
Topic-Connect fertig und verpasst eine Frühnachricht. Tritt bei
`topic echo --once` und `topic pub --once` auf, beeinträchtigt nichts.

**Stand auf den Foot-Kugeln in Phase 4 noch nicht erreicht:** Stufe-7c-
Pose hebt zwar an, aber ohne IK ist die Höhe instabil/asymmetrisch
und coxa-Schwenk verzerrt die Geometrie. Saubere Stand-Pose ist
**Aufgabe von Stufe F** mit `[0, -0.5, 1.0]` (kein coxa-Schwenk,
moderater Hub) und Reibungs-Verifikation.

**Was Stufe E NICHT erreicht hat / NICHT machen sollte:**
- Kein stabiler Stand auf Foot-Kugeln (→ Stufe F)
- Keine PID-Tuning-Iteration (→ Stufe F bei Bedarf)
- Keine multi-Bein-Trajektorien-Synchronisation für Gait (→ Phase 5)
- Kein RViz-Launch-Integration (eigener manueller Aufruf reichte)

---

## Stufe F — Phase-3-Defers einsammeln: Stand-Test + Reibungswerte verifizieren ✅

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

- [x] Stand-Pose-Skript / Multi-Trajectory: alle 6 Beine fahren auf `coxa=0/femur=-0.5/tibia=+1.0` in 4 s — bestätigt, for-loop mit `&;wait`-Pattern
- [x] Roboter sitzt nach Pose-Setting auf 6 Foot-Kugeln (nicht auf dem Bauch); visuell verifiziert — bestätigt
- [x] `gz model -m hexapod -p` zeigt konstante Pose über 5 s (Drift `< 1 mm` / `< 0.5°`) — **Drift = 0**: `z=0.055348 m` und `RPY=[0, 0, -0.000253]` rad **identisch** über alle 5 Samples
- [x] Kein sichtbares Zittern oder Wegrutschen — bestätigt
- [x] Reibungswerte (`mu1`, `mu2`, `kp`, `kd`) **verifiziert** (Default-Werte `mu=1.0`, `kp=1e6`, `kd=100` ausreichend, **kein Tuning nötig**); Werte im `hexapod_gazebo/README.md` aktualisiert
- [x] `inertia_min` ggf. nachgezogen in `inertials.xacro` (falls Zittern) — **nicht nötig**, kein Zittern aufgetreten
- [x] Memory-Eintrag `project_phase3_defer_stand_test.md` als „erledigt" markiert oder gelöscht
- [x] Phase-3-Done-Kriterium 4 in `phase_3_progress.md` und Workspace-`README.md` von ⏸ auf ✅ aktualisieren (mit Verweis auf Phase-4-Verifikation)

### Umsetzungsnotizen Stufe F

> **Test-Anleitung** (User-Operations-Handbuch mit allen Befehlen pro
> Terminal): siehe
> [phase_4_stage_F_test_commands.md](phase_4_stage_F_test_commands.md).

**Resultat — Pfad A (Default-Werte ausreichend):** Kein Reibungs-/
Inertia-Tuning nötig, kein PID-Eingriff. Die Phase-3-Reibungs-Defaults
(`mu1=mu2=1.0`, `kp=1e6`, `kd=100`) tragen den Roboter unter realer
Stand-Last sauber. Damit ist das Phase-3-Defer endgültig eingelöst und
keine `hexapod.gazebo.xacro`-Änderung nötig.

**Stand-Pose-Wahl:** `[0, -0.5, 1.0]` mit `time_from_start=4 s`.
Bewusste Unterschiede zu Stufe-7c-„Anhebe-Pose":
- coxa = 0 statt 0.3 → kein Schwenk, jedes Bein zeigt natürlich in
  seine Mountpunkt-Richtung (kanonische Stand-Pose, ohne IK
  analytisch nachvollziehbar)
- femur = -0.5 statt -1.0 → moderater Hub, kein Extrem-Knicken
- tibia = 1.0 statt 1.5 → fern vom Limit, strukturell stabil
- 4 s statt 2 s → sanfteres Anfahren, kein Spring-Effekt beim
  ersten Foot-Bodenkontakt

**Numerische Stabilität — besser als Done-Kriterium fordert:**
`gz model -m hexapod -p` über 5 Samples mit 1 s Abstand:
- z = 0.055348 m **identisch** in allen 5 Samples
- RPY = [0, 0, -0.000253] rad **identisch** in allen 5 Samples
- Drift = **0 mm / 0°** (Done-Kriterium fordert nur < 1 mm / < 0.5°)

Dass die Pose bit-genau über 5 s konstant bleibt, ist physikalisch
plausibel: bei stabilem Stand mit ausreichend Reibung gibt es keine
Tendenz zur Bewegung, der Solver findet einen Fixpunkt. Die kleine
Restpose-Asymmetrie (`y=-0.020 m`, `yaw=-0.014°`) kommt vom Settling
des asymmetrischen Bauch-Bodenkontakts vor dem Pose-Anfahren — ist
nach dem Anheben nicht mehr aktiv und verschwindet nicht mehr von
selbst (kein Drift, aber auch keine Re-Zentrierung).

**Was Stufe F NICHT machte (alles Phase-5-Themen oder unnötig):**
- Kein PID-Tuning (Default-JTC reicht offensichtlich)
- Kein Multi-Pose-Test (Aufgabe der IK in Phase 5)
- Kein KDL-Warning-Fix (siehe Phasenabschluss-Optionen)

---

## Phasenabschluss ✅

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

- [x] Alle 6 Done-Kriterien aus `phase_4_ros2_control.md` erfüllt:
  - [x] 1) `hexapod_control` baut
  - [x] 2) Beim Launch sind `joint_state_broadcaster` + 6× `joint_trajectory_controller` aktiv
  - [x] 3) `ros2 control list_controllers` zeigt alle Controller `active`
  - [x] 4) `ros2 control list_hardware_interfaces` zeigt 18 Position-Command + 18 Position-State (+ 18 Velocity-State)
  - [x] 5) Manueller Trajectory-Goal bewegt Bein 1 sichtbar in Gazebo
  - [x] 6) `/joint_states` zeigt aktuelle Positionen aller 18 Joints
- [x] Bewegungstest auf mindestens zwei Beinen erfolgreich (Stufe E) — Bein 1 + Bein 4 + Multi-Bein-Tests (7b Reset, 7c Anhebung)
- [x] **Phase-3-Defers eingelöst:** Stand-Test bestanden, Reibungswerte verifiziert/nachjustiert (Stufe F) — Drift = 0 mm / 0° über 5 s, kein Tuning nötig
- [x] `README.md` in `hexapod_control/` und `hexapod_bringup/` aktuell (Zweck, Launch-Aufruf, Controller-Liste, bekannte Stolperfallen)
- [x] `hexapod_gazebo/README.md` Defer-Hinweis durch verifizierte Reibungswerte ersetzt
- [x] `package.xml` in beiden neuen Paketen ohne `TODO:`-Stubs (Description gesetzt: Kurzbeschreibung des Paket-Zwecks)
- [x] (optional) KDL-Warning gefixt mit Dummy-Root-Link, sonst auf Phase 5 schieben (im README dokumentieren) — **auf Phase 5 verschoben**, Memory-Eintrag `project_phase5_kdl_warning_fix.md` als Reminder
- [x] Timeshift-Snapshot `phase_4_done` angelegt — **User-Aufgabe**
- [x] Git-Commit + Tag `phase-4-done` — **User-Aufgabe**
- [x] `PHASE.md` auf Phase 5 aktualisiert (Status: Phase 4 🟢, Phase 5 🟡) — inklusive Übergabe-Block für Phase 5 (KDL-Warning + Stand-Pose-Plausibilitätscheck)
- [x] Workspace-`README.md` um Phase-4-Bericht ergänzt (was angelegt, Designentscheidungen, Verifikation, offene Punkte; Stand-Tabelle und Pakete-Tabelle aktualisiert)
- [x] Retro: Was lief gut, was hat länger gedauert, was bleibt offen — siehe unten

---

## Retro Phase 4

**Was lief gut**
- **Stufenplan A→F linear durchgelaufen** ohne Sprünge oder Rollbacks.
  Jede Stufe sauber abhakbar, Konzept-vor-Implementation-vor-Test
  konsequent durchgezogen.
- **Wiederverwendung der Limit-Properties (`coxa_lower/upper` etc.) im
  ros2_control-Block** — keine Wert-Duplikation, Single-Source-of-Truth-
  Prinzip aus §11.4 sauber gewahrt.
- **Zweistufige `OnProcessExit`-Sequenz** statt naiver Re-Try-Variante:
  saubere Logs, klar nachvollziehbare Lade-Reihenfolge.
- **Konzept-Dokus separat** (`*_explained.md` neben `*_progress.md`):
  bleiben in Phase 5-7 als Nachschlagewerk verfügbar, ohne den
  Fortschritts-Tracker zu fluten.
- **Test-Doku-Pattern für interaktive Stufen**: `phase_4_stage_E_test_commands.md`
  und `..._F...md` haben in Stufen E/F den Kontext schlank gehalten —
  Sim-Logs liefen lokal in `/tmp/sim.log`, Status-Rückmeldungen einzeilig.
  Memory-Eintrag dafür angelegt, gilt für alle künftigen Live-Stufen
  (Phase 7 HW).
- **Stand-Test (Phase-3-Defer) sofort grün**: Default-Reibungswerte
  ausreichend, kein Tuning-Lauf nötig. Drift = 0 über 5 s.

**Was hat länger gedauert**
- **`grep -c '<joint name='`-Verifikations-Bullet in Stufe B**: war im
  Progress-File falsch formuliert (zählt mech. Joints + ros2_control-Refs
  zusammen, nicht 18). Diskussion + User-Entscheidung kostete eine
  Iteration. Lessons learned: bei Verifikations-Befehlen vorher selbst
  rechnen, was tatsächlich erwartet wird.
- **`tail -20`-Trim in Stufe-B-Verifikation hat `leg_1` aus `check_urdf`-
  Output verdeckt** — User musste fragen, ob `leg_1` fehlt. War nur
  visueller Effekt, aber Vertrauen geschadet. Memory-Eintrag
  `feedback_no_trim_verification_output.md` angelegt.
- **Stufe-7c-Höhe-Verdopplung war nicht-linear**: User-Erwartung (doppelt
  so hoch beim Körper) wurde nicht erfüllt, weil naive Joint-Wert-
  Verdopplung das Bein einfach stärker einklappt statt es zu strecken.
  War aber ein Lehrmoment für die Notwendigkeit von IK in Phase 5.

**Was bleibt offen**
- **KDL-Warning** für `base_link` mit Inertia weiterhin offen — auf
  Phase 5 verschoben (Memory-Eintrag als Reminder). Funktional unkritisch.
- **`use_sim_time: true` in `controllers.yaml`** ist Phase-4-6-korrekt,
  in Phase 7 muss überschrieben werden. Kommentar im YAML weist darauf
  hin, aber konkrete Lösung (Launch-Override vs. zweite YAML) ist
  Phase-7-Entscheidung.
- **Stand-Pose ist visuell asymmetrisch** (`y=-0.020 m`, `yaw=-0.014°`):
  Settling-Effekt vor dem Pose-Anfahren. Verschwindet in Phase 5 mit
  IK-basiertem Anfahren.
- **Echte IK + dynamische Posen** — komplette Phase 5.
- **Headless-LaunchArg** in `hexapod_bringup/sim.launch.py` für CI-Tests
  fehlt noch (bekannt seit Phase-3-Retro).
