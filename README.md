# Hexapod Workspace

ROS 2 Jazzy / Gazebo Harmonic Hexapod-Projekt — 6 Beine, 18 Joints,
Servo2040-Hardware-Anbindung in Phase 7.

Phasenweises Vorgehen, verbindliche Konventionen in `CLAUDE.md`,
aktuelle Phase in `PHASE.md`, Phasen-Doku in `docs/`.

## Stand

| Phase | Inhalt | Status |
|---|---|---|
| 0 | Desktop-Setup, ROS-Toolchain | ✅ |
| 1 | ROS 2 Basics (Udemy-Kurs, Phase übersprungen) | ✅ |
| 2 | URDF/Xacro-Beschreibung | ✅ |
| 3 | Gazebo-Simulation | ✅ (alle 6 Kriterien; Kriterium 4 nachträglich in Phase 4 Stufe F verifiziert) |
| 4 | `ros2_control` | ✅ |
| 5 | Inverse Kinematik & Gait | 🟡 aktiv |
| 6 | Teleop | offen |
| 7 | Pi-Portierung & Hardware | offen |

## Pakete

| Paket | Status | Zweck |
|---|---|---|
| `hexapod_description` | ✅ Phase 2 | URDF/Xacro, RViz-Display, ros2_control-Block + gz_ros2_control-Plugin (Phase 4) |
| `hexapod_gazebo` | ✅ Phase 3 | Plain-Sim-Bringup (Launch, Bridge, Reibungswerte im URDF-Gazebo-Tag) |
| `hexapod_control` | ✅ Phase 4 | `ros2_control`-Config (controllers.yaml: JSB + 6 JTC) |
| `hexapod_bringup` | ✅ Phase 4 | Standard-Sim-Launch mit Controller-Spawnern (sim.launch.py) |
| `hexapod_kinematics` | offen | IK |
| `hexapod_gait` | offen | Gait-Engine |
| `hexapod_teleop` | offen | Joystick/Tastatur |
| `hexapod_hardware` | offen | C++ HardwareInterface (Pi) |

## Quickstart

```bash
cd ~/hexapod_ws
colcon build --symlink-install
source install/setup.bash

# Phase 2: nur RViz mit Modell + Slider (kein Sim, kein Controller)
ros2 launch hexapod_description display.launch.py

# Phase 3: Plain-Sim ohne Controller (nur Physik / Reibung debuggen)
ros2 launch hexapod_gazebo sim.launch.py

# Phase 4: Standard-Sim mit ros2_control (1× JSB + 6× JTC active)
ros2 launch hexapod_bringup sim.launch.py
```

---

## Phase 2 — Bericht (2026-05-07)

**Ergebnis:** Hexapod komplett als URDF/Xacro modelliert, in RViz
visualisiert, alle 18 Joints per `joint_state_publisher_gui` bewegbar,
tf-Tree vollständig.

### Was angelegt wurde

Paket `src/hexapod_description/` mit folgender Struktur:

```
hexapod_description/
├── urdf/
│   ├── hexapod.urdf.xacro                 # Top-Level: base_link + 6× leg-Macro
│   ├── leg.xacro                          # Bein-Macro (coxa/femur/tibia/foot)
│   ├── hexapod_physical_properties.xacro  # Maße, Massen, Joint-Limits
│   ├── inertials.xacro                    # box_inertia + sphere_inertia mit Mindestschranke
│   └── materials.xacro                    # orange / grey / black
├── launch/display.launch.py               # RViz + joint_state_publisher_gui + world-tf
├── config/view.rviz                       # RViz-Config (Fixed Frame: world)
├── README.md
├── package.xml
└── CMakeLists.txt
```

Geometrie ausschließlich aus **Boxen** + **Kugel** als Foot-Link.
Alle Werte aus `docs/00_conventions.md` §11 (physisch verifiziert).

### Wichtige Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| `base_link` im **geometrischen Mittelpunkt** des Chassis | REP-103, Konvention §3 — ändern wir nicht |
| `leg_mount_z = 0` (statt initial `body_height/2`) | Coxa-Joint-Achse läuft horizontal durch die Chassis-Z-Mitte. Mit `coxa_height = 58.2 mm > body_height = 43 mm` ragt die Coxa-Box rundum 7.6 mm über Chassis-Ober- und -Unterkante — entspricht der realen Servo-Konstruktion. Konvention §11.3 wurde nachgezogen. |
| Foot-Link als **Kugel** (`r = 8 mm`), nicht Tibia-Ende direkt | Punktkontakt mit dem Boden statt Kantenkontakt der dünnen Tibia-Box → in Gazebo (Phase 3) stabil und vibrationsfrei |
| `inertia_min = 1e-5` als Untergrenze in Inertia-Macros | Tibia-Querschnitt 12 × 12 mm liefert numerisch sehr kleine Inertien (< 1e-5 kg·m²), Solver-Vibration in Gazebo droht — `max(...)` clamped konservativ |
| `world → base_link` Static-Transform mit `z = coxa_height/2 = 29.1 mm` | Phase-2-spezifisch, hebt Roboter so an, dass die Coxa-Unterkanten (= unterster Punkt) auf RViz-Grid-Höhe liegen. Wird in Phase 3 durch Gazebo-Spawn ersetzt. Hardcoded im Launch-File mit Verweis-Kommentar. |
| `--symlink-install` beim Build | URDF/Launch/RViz-Änderungen wirken ohne Rebuild |

### Verifikation

- `colcon build --packages-select hexapod_description` grün
- `xacro` + `check_urdf` parsen das URDF fehlerfrei
- 25 Links / 24 Joints (18 revolute + 6 fixed) im generierten URDF
- `ros2 run tf2_tools view_frames` zeigt vollständigen tf-Tree:
  `base_link → leg_<n>_(coxa→femur→tibia→foot)_link` für alle n=1..6
- RViz-Smoke: alle 6 Beine sichtbar, alle 18 Slider bewegen die richtigen
  Achsen (Coxa um Z, Femur+Tibia um Y), Drehrichtungen plausibel,
  Symmetrie zwischen rechter (leg_1/2/3) und linker Seite (leg_4/5/6)

### Bekannte offene Punkte

- **KDL-Warning** beim `robot_state_publisher`-Start:
  „The root link base_link has an inertia specified in the URDF, but
  KDL does not support a root link with an inertia."
  Workaround wäre ein Dummy-Root-Link mit fixed Joint zu base_link.
  Für Phase 2 unkritisch — die Warning beeinflusst die TF-Berechnung
  nicht. Gegebenenfalls in Phase 4 (`ros2_control`) angehen.
- **`world`-Frame im Launch** ist Phase-2-Display-Hilfe. In Phase 3
  liefert Gazebo den globalen Frame und der `static_transform_publisher`
  fliegt aus dem Display-Launch raus.

### Konventions-Änderungen während Phase 2

- `docs/00_conventions.md` §11.3:
  `leg_mount_z = body_height / 2` → `leg_mount_z = 0`
  (mit Begründung im Konventions-Text dokumentiert)

---

## Phase 3 — Bericht (2026-05-08)

**Ergebnis:** Hexapod läuft in Gazebo Harmonic (über `ros-jazzy-ros-gz`),
spawnt sauber bei `z=0.20`, fällt unter Schwerkraft auf seine 6 Foot-Kugeln,
durchschlägt den Boden nicht. Sim-Zeit fließt mit ~1 kHz nach ROS, RViz
zeigt das Modell mit `use_sim_time:=true`. **5 von 6 Done-Kriterien
erfüllt; Kriterium 4 (Stand-Test) deferiert auf Phase 4** — siehe Hinweis
unten.

### Was angelegt wurde

Paket `src/hexapod_gazebo/` (Resource-only, kein Code):

```
hexapod_gazebo/
├── launch/sim.launch.py          # gz sim + RSP + Spawn + Bridge
├── config/bridge.yaml            # ros_gz_bridge — Phase 3: nur /clock
├── README.md
├── package.xml
└── CMakeLists.txt
```

Erweiterung in `hexapod_description`:
- `urdf/hexapod.gazebo.xacro` — Macro `foot_friction(id)` mit
  `mu1=mu2=1.0`, `kp=1e6`, `kd=100` für jede der 6 Foot-Kugeln,
  eingebunden ans Ende von `hexapod.urdf.xacro`.

### Wichtige Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| Gazebo Harmonic über `ros-jazzy-ros-gz` (Vendor-Package) | CLAUDE.md §2: keine `packages.osrfoundation.org` als zweite Paketquelle, ROS-Apt ist Single-Source |
| Default-Welt `empty.sdf` aus gz-sim, **keine** eigene Welt-SDF | Pragmatisch — `ground_plane` + Sun reichen für Phase 3, Default-First-Strategie aus `phase_3_gazebo.md` |
| `<gazebo>`-Tags in `hexapod_description`, **nicht** in `hexapod_gazebo` | URDF ist Single Source of Truth; Tags werden vom RSP ignoriert (auch auf Pi unschädlich); saubere Trennung von Kinematik und Sim-Spezifika |
| Bridge nur für `/clock`, nicht für Joint-States | Phase-Schnitt — `/joint_states`-Brücke kommt in Phase 4 über `gz_ros2_control`-Plugin direkt im Sim-Prozess (nicht über `parameter_bridge`) |
| `ParameterValue(value_type=str)` um den `xacro`-`Command` | Verhindert, dass rclpy den URDF-XML-String als YAML zu parsen versucht — klassischer ROS2-Stolperstein |
| Spawn-Höhe 0.20 m (LaunchArg, überschreibbar) | Ausreichend Puffer, dass der Roboter beim Spawn nicht im Boden steckt; `spawn_z:=1.5` für Drop-Tests verfügbar |
| Selbst-Kollisionen **aus** | Default — Aktivierung erst nach stabilem Gait und nur pro Link, nicht global; sonst Performance-Verlust + Fehlalarme bei minimal überlappenden Box-Visuals |

### Verifikation

- `colcon build --packages-select hexapod_description hexapod_gazebo --symlink-install` grün
- `xacro` + `check_urdf` parsen das URDF mit den 6 `<gazebo reference="leg_*_foot_link">`-Blöcken
- Launch im normalen User-Terminal: Gazebo öffnet, Welt + Sun + Boden sichtbar, Roboter spawnt und fällt korrekt
- `gz model -m hexapod -p` → Endpose `z=0.029 m` (Body liegt auf Boden, durchbricht nicht)
- `ros2 topic hz /clock` → ~935 Hz (≈ 1 kHz Sim-Step-Rate)
- `ros2 param get /robot_state_publisher use_sim_time` → `True`
- `ros2 param get /ros_gz_bridge use_sim_time` → `True`
- RViz mit `use_sim_time:=true` zeigt das Modell (siehe RViz-Krücke unten)

### Phase-3-Defer: Stand-Test (Done-Kriterium 4)

Beim Versuch, in Gazebo per GUI-Slider die Stand-Pose
(`coxa=0`, `femur=-0.5`, `tibia=+1.0`) zu setzen, hat sich gezeigt: ohne
Server-Plugin (`JointPositionController` oder `gz_ros2_control`) ist in
reinem URDF kein Mechanismus vorhanden, der Joint-Winkel hält. Der GUI-
Slider sendet Position-Topics, aber niemand subscribt.

**Drei Optionen wurden diskutiert, Entscheidung Weg B:**
- **A)** 18 `JointPositionController`-Plugins ad-hoc ins URDF — Wegwerfcode
  für Phase 4 (verworfen).
- **B) gewählt:** Stand-Test auf Phase 4 verschieben. Reibungswerte bleiben
  als konservative Defaults, werden bei der ersten echten Stand-Pose unter
  `gz_ros2_control` verifiziert.
- **C)** Initial-Pose beim Spawn + hohe Joint-Damping — verfälscht die
  Joint-Dynamik temporär (verworfen).

Begründung dokumentiert in `docs/phase_3_progress.md` Stufe E.1, Memory-
Eintrag in `~/.claude/projects/.../memory/project_phase3_defer_stand_test.md`.

### RViz-Andockung — Phase-3-Krücke

Done-Kriterium 6 wurde mit einem dokumentierten Workaround abgenommen:
ohne `/joint_states`-Brücke bleibt `/tf` unvollständig, `base_link`
erscheint nicht im Fixed-Frame-Dropdown. Workaround: zusätzlicher
`joint_state_publisher` (headless) im dritten Terminal publisht alle 18
Joints auf 0, RSP berechnet daraus das vollständige `/tf`. Roboter
erscheint in RViz in Default-Pose — nicht synchron zur Gazebo-Pose. Der
JSP wird **nicht** ins Sim-Launch aufgenommen, weil er in Phase 4 mit
`gz_ros2_control` kollidieren würde.

```bash
# Drei-Terminal-Setup für Phase-3-RViz-Test
ros2 launch hexapod_gazebo sim.launch.py                                # T1
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true                   # T2
ros2 run joint_state_publisher joint_state_publisher \
  --ros-args -p use_sim_time:=true                                      # T3
```

### Bekannte offene Punkte

- **Stand-Test** (Done-Kriterium 4) — deferiert, in **Phase 4 Stufe F
  nachgeholt** (Drift = 0 mm / 0° über 5 s, Default-Reibung ausreichend).
- **KDL-Warning** für `base_link` mit Inertia — aus Phase 2 bekannt, bleibt
  bestehen. Auf **Phase 5** verschoben (Memory-Eintrag
  `project_phase5_kdl_warning_fix.md`).
- **Snap-Library-Konflikt** mit `gz sim gui` (`__libc_pthread_init`-Symbol)
  trat im Claude-Bash-Subshell auf, **nicht** im normalen User-Terminal.
  Workaround dort: headless-Launch (`world:='-s empty.sdf'`). Im
  Default-User-Setup kein Problem.
- **`/joint_states`-Brücke** und aktive Joint-Steuerung — in Phase 4 mit
  `gz_ros2_control` + JSB erledigt (kein `parameter_bridge`-Mapping nötig,
  JSB publisht direkt im Sim-Prozess).

---

## Phase 4 — Bericht (2026-05-08)

**Ergebnis:** `ros2_control` vollständig integriert. Beim Sim-Launch
laufen 7 Controller (1× `JointStateBroadcaster` + 6× `JointTrajectoryController`,
einer pro Bein) im Status `active`. Manueller Bewegungstest auf
mehreren Beinen grün, Stand-Pose stabil (Drift = 0). RViz folgt Gazebo
synchron — die Phase-3-JSP-Krücke ist obsolet. Alle 6 Done-Kriterien
aus `docs/phase_4_ros2_control.md` erfüllt, plus die Phase-3-Defers
aus DK4 eingelöst.

### Was angelegt wurde

Zwei neue Pakete:

```
hexapod_control/
├── config/controllers.yaml       # CM + JSB + 6 JTC, use_sim_time=true
├── README.md
├── package.xml
└── CMakeLists.txt

hexapod_bringup/
├── launch/sim.launch.py          # Standard-Sim-Bringup ab Phase 4
├── README.md
├── package.xml
└── CMakeLists.txt
```

Erweiterung in `hexapod_description`:
- `urdf/hexapod.ros2_control.xacro` — `joint_iface(name, lower, upper)`-
  Macro 18× instanziiert + `gz_ros2_control-system`-Plugin-Block.
  Limit-Werte ziehen direkt aus den Properties in
  `hexapod_physical_properties.xacro` (Single Source of Truth).

Vier neue Konzept-/Test-Dokus in `docs/`:
- `phase_4_controllers_explained.md` — `controllers.yaml`, Lifecycle,
  CLI-Befehle, Phasen-übergreifende Nutzung
- `phase_4_launch_explained.md` — Launch-Files, Substitutions,
  Event-Handler, Spawner-Pattern
- `phase_4_stage_E_test_commands.md` — User-Operations-Handbuch für
  die Inbetriebnahme (3 Terminals, Schritt-für-Schritt)
- `phase_4_stage_F_test_commands.md` — User-Operations-Handbuch für
  Stand-Test + Reibungs-Verifikation

### Wichtige Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| Ein JTC pro Bein (statt 1 großer für alle 18 Joints) | Tripod-Gait braucht parallele Trajektorien (3 schwingen, 3 stützen); Beine isoliert testbar; HW-Fehler isolieren sich |
| Position-only Command-Interface | Servo2040 in Phase 7 spricht ebenfalls Position; State-Interface zusätzlich `velocity` (breiter, viele Controller stützen sich darauf) |
| Limit-Werte aus existierenden Properties (`coxa_lower/upper` etc.) | Single Source of Truth in §11.4 — keine Duplikation zwischen `<limit>` und `<param min/max>` |
| Zweistufige `OnProcessExit`-Sequenz im Launch | Standard-ros2_control-Pattern: spawn-Exit → JSB → JSB-Exit → 6 JTCs. Re-Try-Spam in Logs vermieden |
| `hexapod_gazebo/sim.launch.py` bleibt erhalten | Plain-Sim ohne Controller für Physik-/Reibungs-Debugging |
| Explizit ausgeschriebene 6 JTC-Blöcke in YAML (keine Anchors) | ROS-YAML-Parser haben mit Anchors gelegentlich Macken, alle Tutorials machen es explizit |
| Konzept-Dokus separat von Implementierungs-Notizen | `*_explained.md` bleibt in Phase 5-7 als Nachschlagewerk nützlich; Progress-File pflegt nur den Fortschritts-Tracking |

### Verifikation

- `colcon build --packages-select hexapod_description hexapod_gazebo hexapod_control hexapod_bringup --symlink-install` grün
- `ros2 control list_controllers` → 7 Controller, alle `active`
- `ros2 control list_hardware_interfaces` → 18 cmd `[claimed]` + 36 state
- `ros2 topic list` → `/joint_states` + 6× `/leg_*_controller/joint_trajectory`
- Bewegungstest Bein 1 + Bein 4 + Multi-Bein-Reset + Multi-Bein-Anhebung — alle visuell und in RViz synchron
- **Stand-Test (Phase-3-Defer):** `gz model -m hexapod -p` über 5 s — z=0.0553 m und RPY identisch über alle Samples, Drift = 0
- Default-Reibungswerte (`mu=1.0`, `kp=1e6`, `kd=100`) tragen sauber, kein Tuning nötig

### Konventions-Änderungen während Phase 4

Keine. Stack und Naming aus `00_conventions.md` haben 1:1 getragen,
Limit-Werte aus §11.4 wurden direkt wiederverwendet.

### Bekannte offene Punkte

- **KDL-Warning** weiterhin offen — auf **Phase 5** verschoben
  (Memory-Eintrag `project_phase5_kdl_warning_fix.md` als Reminder).
- **`use_sim_time: true`** in `controllers.yaml` ist Phase-4-6-korrekt, in
  Phase 7 muss entweder per Launch-Override `false` gesetzt oder eine
  separate `controllers.real.yaml` angelegt werden — Kommentar im YAML
  weist explizit darauf hin.
- **Stand-Pose ist visuell asymmetrisch** (`y=-0.020 m`, `yaw=-0.014°`):
  kommt vom Settling des Bauch-Bodenkontakts vor dem Pose-Anfahren,
  nach dem Anheben kein Drift mehr aber auch keine Re-Zentrierung. Wird
  in Phase 5 mit IK-basiertem Anfahren der Stand-Pose verschwinden.
