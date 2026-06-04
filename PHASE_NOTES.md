# Phase-Notizen — Retros, Begründungen, Übergaben

> Supplementär zu [`PHASE.md`](PHASE.md). Diese Datei enthält die
> ausführlichen Retros, historischen Kontext, Übergabe-Items und
> Begründungen für Phase-Schnitte. PHASE.md selbst zeigt nur die aktuelle
> Phase + die kompakte Tabellen-Übersicht.

---

## Phasen-Hintergrund

**Wichtig:** Ab Phase 7 liegen alle Phasen-Detail-Docs unter `docs_raspi/`,
nicht mehr unter `docs/`. Phasen 0–6 bleiben in `docs/`.

**Phase-7-Bündel-Hintergrund:** Aus dem ursprünglichen „Phase 7 — Pi-
Portierung & Hardware" wurden auf Wunsch sechs feiner geschnittene
Phasen (7–12), damit die Übersicht sauber zeigt wo wir gerade stehen.
Der erste Mega-Draft liegt als `docs_raspi/_archive_phase_7_brainstorm.md`
archiviert — als Referenz für Inhalte, nicht mehr aktiv.

**Cross-Phase-Thread `servo_real_cal` (2026-05-24/25):** Nach Phase 11✅
wurde nicht direkt mit Phase 12 (Pi-Plattform) weitergemacht. Stattdessen
wurde ein Cross-Phase-Thread eingeschoben — Stages 0/0.5/0.6/A/B/D/E/C/E2
— um die Cal-Probleme aus Phase 10/11 sauber zu adressieren (Plugin-Math,
direction-Map, Stage 0.5/0.6 Safety-Layer, URDF-rad-Limit-Sync, HW-Walking
aufgebockt). Plan-Index: `docs_raspi/servo_real_cal_plan.md`. Memory-
Eintrag: `project_servo_real_cal_done.md`. Dieser Thread hat de facto
Phase-13 Sub-Stages B/C/D vorweggenommen — Phase 13 wurde entsprechend
auf "Pi-Recheck statt Erst-Bringup" angepasst.

---

## Phase-11-Retro (Param-GUI, ✅ 2026-05-21)

Alle 6 Stages A–F durchgelaufen. Live-Param-Surfaces für gait_node
(14 Params), Plugin-Cal (72 Params), Diagnostic-Topic + Preset-
Workflow + Workshop-Doku stehen. CI-Tests durchgängig grün
(hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware
220/0/20).

**Was gut lief:** Strikter Plan-First-Workflow pro Stage mit
ausführlichen Q&A-Tabellen (A-Q1..A-Q8 in Stage A, B-Q1..B-Q9 in
Stage B, etc.) hat substantielle Design-Diskussionen produziert
und Alternativen dokumentiert. Self-Reviews haben in fast jeder
Stage echte Bugs gefunden (Stage A: Phase-6-Topic-Handler-Sync-
Bug; Stage B: Range-Mismatch [800,2200] vs YAML-Default 500 +
Node-Name-Lowercase-Doku; Stage D: cwd-Falle bei relativem
params_file). Memory-Konvention `feedback_decision_alternatives_log.md`
wurde ausführlich umgesetzt. User-Q&A-Pattern hat Plan-Doku-
Qualität sichtbar erhöht (User korrigierte z.B. Pose-Management-
Verständnis → Phase-13-Scope-Notiz). Engine-Property-Refactor in
Stage A.0a (`stance_duration`/`linear_max` als computed Properties
statt Cache) war strategisch — sonst hätte Live-Cycle-Time-Update
Cache-Drift verursacht.

**Was länger gedauert hat:** Stage B (Plan ~1 d → ~1.5 d) wegen
F1-F6-Plan-Korrekturen vor Code-Beginn (Timestamp-bak,
is_active_-Member, std_srvs-Dep, README-Update, YAML-Schema,
tmpdir-Pattern). Stage D wegen ROS-Jazzy-Doku-Bugs:
`ros2 param dump` hat keine `--output-dir`/`--filename`-Args mehr
(nur stdout-Redirect), `rqt`-Container nicht via `ros2 run`
sondern direkt aus PATH. Beide entdeckt im User-Smoke.

**Was offen ist:** Cross-Phase-Pendenzen die in Phase 13 landen
müssen — `project_phase10_real_yaml_vel_limits.md`,
`project_phase13_initial_pose_presets.md`,
`project_phase9_h_oscilloscope_pending.md`, Auto-Cal-Tool für 15
verbleibende Servos (überholt durch servo_real_cal-Thread). Plus
Phase 8 (Strom- & Elektronik-Bench) ist harte Deadline vor Phase 12-Start.

**Schlüssel-Insight:** Live-Param-Tuning + Preset-Persistenz hat
sich als Game-Changer für Cal-Sessions herausgestellt. Stage-B-
`/save_calibration` mit Timestamp-bak macht beliebig viele
Cal-Iterationen schmerzfrei (kein Datenverlust durch Überschreiben).
Stage-D-`params_file`-Mechanismus für Gait-Presets erlaubt Demo-
Reproduzierbarkeit über mehrere Sessions hinweg. Diese
Infrastruktur wird in Phase 13 mit echter HW noch wertvoller.

---

## Phase-10-Retro (Single-Leg Bring-up + Kalibrierung, ✅ 2026-05-19)

Alle 8 Stages A–G + I durchgelaufen (Stage H war eh gestrichen).
leg_6 (Pin 15/16/17) ist voll kalibriert; IK + gait_node-Walking auf
echter Hardware verifiziert (aufgehängt, ohne Bodenkontakt).

**Was gut lief:** Strikter Plan-First-Workflow pro Stage (4 Pflichtinhalte
+ offene Fragen) hat substantielle Diskussionen produziert — z.B. Strategie B'
für Coxa-Self-Collision-Schutz in Stage B, Loopback-First-Workflow in Stage F.2.
Memory-Konvention `feedback_urdf_refactor_full_smoke.md` hat in Stage F1
(Tibia-Update) direkt gegriffen — Sim-Verifikation als Phase-12-Pendenz markiert
statt vergessen. User-Pattern „Commit zwischen Sub-Stages" (Stages C+D+E+F-Phase-1)
hat Iterations-Anker geliefert. Self-Reviews haben in jeder Stage echte Drifts
gefunden (Plan-Annahme Test-Fixtures in Stage B → Reality committed YAML; Stride-
Range-Test deferred in F-T6 etc.).

**Was länger gedauert hat als geplant:** Stage B 0.5 d → 1 d wegen User-Strategie-
Wechsel C→B' (Self-Collision-Sicherheit über Range-Maximierung). Stage F war
1.5 d Wildcard → ~2 d wegen Tibia-Update mit IK-Probe-Default-Anpassung +
Loopback-First-Discovery + Coxa-Sichtbarkeits-Discussion. Stage G war als
~1 h geplant, hat ~1.5 h gebraucht wegen Echo-State-Klarstellung-Discussion
die Strategie auf Option C reduziert hat.

**Was offen ist:** Cross-Phase-Pendenzen (nach Phase-11-Renumbering 2026-05-19
zeigen Refs auf Phase 13 statt vorheriger Phase 12):
- `project_phase10_tibia_length_sim_pending.md` (Sim-Verifikation nach Tibia-Update — könnte in Phase 11 mit Sim-Tuning erledigt werden)
- `project_phase10_real_yaml_vel_limits.md` (Vel/Accel mit Bench-Last — Phase 13)
- `project_phase13_initial_pose_presets.md` (Initial-Pulse-Preset statt Hand — Phase 13)
- `project_phase9_h_oscilloscope_pending.md` (Oszi/Logic-Analyzer-Tests)
- Auto-Cal-Tool für 15 verbleibende Servos — **überholt durch servo_real_cal-Thread 2026-05-25**

**Echo-State-Klarstellung als Schlüssel-Insight:** User-Realität (Servos
liefern niemals Position-Feedback, kein Wechsel zu Feedback-Servos geplant)
hat Stage-G-Strategie fundamental geändert (Option C statt Option B).
Phase 13 muss mit dieser Realität planen — JTC-Toleranz-Constraints
sind faktisch wertlos in unserem System; Schutz kommt aus den drei
Hardware-Schichten (URDF-Cap + Pulse-Clamp + Position-Limits).

---

## Phase-9-Retro (hexapod_hardware-Plugin, ✅ 2026-05-16)

Alle 10 Stufen A–J durchgelaufen. CI-Anteil voll grün (208 Plugin-Tests +
18 launch_testing-Tests), Hardware-Pfad bis Plugin↔Firmware-Pipeline mit
echtem Servo2040 ohne Hexapod-Servos verifiziert. **Ausstehende Items:**
Oszi/Logic-Analyzer-Verifikation (Stage H H-T8/H-T9) — dokumentiert in
Memory-Eintrag `project_phase9_h_oscilloscope_pending.md` als Cross-Session-
Reminder; bei Hardware-Verfügbarkeit (z.B. Phase 10 Bench-Setup) nachholen.

**Was gut lief:** der Plan-First-Workflow mit jeweils 4–5 offenen Fragen
pro Stufe hat substantielle Design-Diskussionen produziert (z.B. F-Q1
velocity-State-Mismatch, G-Q1 loopback-Default, H-Q1 Bench-Netzteil-
Setup) die im Code-Edit allein nicht aufgekommen wären. Memory-Konvention
`feedback_urdf_refactor_full_smoke.md` aus Stage F hat in Stage G + H
direkt gegriffen.

**Was länger gedauert hat als geplant:** Hardware-Stages (H, I) hatten
mehr Real-World-Lessons als antizipiert (USB-CDC-Boot-Garbage,
ros2_control Auto-Deactivate-Bei-Write-Fail, Linter-Pattern-Lerncurve
für launch_testing). Plan-Korrektur-Sektionen pro Stage haben das
transparent gemacht. Bei F-Q5 wurde F-T9 nach Stage G verschoben weil
die „einzelner CLI-Aufruf reicht"-Annahme an rcl-Parser-Limitierung
gescheitert ist.

**Was offen ist:** (1) Oszi/Logic-Analyzer-Tests (siehe oben), (2)
optional `phase-7-done`-Tag retroaktiv im fw-Repo (Doku-Hygiene aus
Stage H H-T3), (3) Plugin-API-Migration `export_*_interfaces()` →
`on_export_*_interfaces()` ist out-of-scope geblieben (alte API gewinnt
wenn Override non-empty) — Pragma-Suppression in test_plugin_registration.cpp.

---

## Phase-7-Übergabe (Servo2040 Firmware, ✅ 2026-05-14)

Alle Stufen A–G grün am Board verifiziert, Doku in
`docs_raspi/phase_7_progress.md` (inkl. Pimoroni-API-Erkenntnis-Tabelle +
Retrospektive). Stufe H Git-Aktionen (`phase-7-done`-Tag in fw-Repo und
hexapod_ws, Commit der phase_7-Docs) macht der User beim Phasenwechsel.

---

## Phase 8 Pausen-Status (2026-05-14)

**Phase 8 (Bench-Elektronik):** Inhalt (DCDC-Wandler für Pi, GND-Stern,
Bulk-Caps) wird erst gebraucht wenn der Pi ins Spiel kommt. Phase 9 + 10
laufen weiterhin am Desktop mit der bestehenden Bench-PSU-Verkabelung aus
Phase 7. **Harte Deadline: vor Beginn Phase 12 (Pi-Plattform) muss Phase 8
durch sein.**

**Phase 8b (Sim+HW-Mirror):** Architektur-Abgrenzung macht den Mirror
unabhängig — kann jederzeit ergänzend gebaut werden, ist aber kein
Done-Kriterium für 9/10/11/12.

---

## Phase-6-Übergabe (Teleop, ✅ 2026-05-10)

PS4-Controller via USB läuft. D-Pad steuert Bewegung (vor/zurück, drehen am
Stand), L2/R2 ändern Body-Höhe (nur im STANDING-State), R1 ist Dead-Man-
Switch. Engine-Erweiterung `gait_node` mit `/cmd_body_height` Topic.
Tastatur-Stufe verworfen, Bluetooth-Pairing deferred.

**Übergabe-Items für Phase 7 ff. (zum Teil später eingelöst):**

- **`controllers.yaml use_sim_time: true`** musste in Phase 9 auf `false`
  (Wallclock am Pi) für `controllers.real.yaml`. ✓
- **`body_height = -0.052`** war Sim-spezifischer JTC-Tracking-Lag-Workaround.
  HW-Default zurück auf `-0.047` — echte Servos haben keinen Lag. ✓
- **KDL-Warning** weiter offen — am Pi auch unkritisch (User-Entscheidung).
- **`hexapod_hardware`-Paket** (C++ HardwareInterface, pluginlib) in
  Phase 9 angelegt — ersetzt `gz_ros2_control` für echte Servo2040-Hardware. ✓
- **Sicherheit:** Hexapod aufbocken für Joint-Tests, Hardware-Kill-Switch
  griffbereit, reduzierte Geschwindigkeit (siehe CLAUDE.md §9). ✓ (Stages 10,
  E2 nutzen das durchgängig)

---

# Archiv: Frühe Phasen-Berichte (Phase 2–6, aus README.md ausgelagert 2026-06-04)

> Diese detaillierten Bau-Berichte standen ursprünglich in der README. Sie sind **historisch**
> (Stand der jeweiligen Phase) und werden **nicht mehr aktiv gepflegt** — als Referenz erhalten,
> nicht als aktueller Stand lesen. Aktueller Projekt-Stand: `PHASE.md` + `project_finalization/`.

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

---

## Phase 5 — Bericht (2026-05-09)

**Ergebnis:** Hexapod läuft in Gazebo eigenständig **omnidirektional**
über `/cmd_vel` (Twist). Alle 5 Done-Kriterien erfüllt, plus
Omnidirektional-Erweiterung (linear.y + angular.z) als Stufe H. Roboter
kann vorwärts, rückwärts, seitwärts, drehen und Bögen fahren. Sauberer
STANDING/WALKING/STOPPING-State-Machine, proportionales Clamping,
default-Demo-Mode ohne externe cmd_vel.

### Was angelegt wurde

Drei neue Pakete:

```
hexapod_kinematics/                    # Pure-Python IK/FK-Library
├── hexapod_kinematics/
│   ├── config.py                      # LegConfig Dataclass, HEXAPOD-Konstante (Single Source of Truth)
│   ├── geometry.py                    # rotate_z, base↔leg-frame
│   └── leg_ik.py                      # closed-form IK + leg_fk
├── test/                              # 28 Tests (17 IK, 6 geometry, 3 config-cross-check, +Style)
└── README.md

hexapod_sensors/                       # Stufe D — Gazebo→ROS Foot-Contact
├── hexapod_sensors/
│   └── foot_contact_publisher.py      # 6× Bool/Bein, 100 ms Decay
└── (Tests via integration)

hexapod_gait/                          # Gait-Engine + ROS-Knoten
├── hexapod_gait/
│   ├── stand_node.py                  # one-shot Stand-Pose (Stufe C)
│   ├── trajectory_gen.py              # swing_traj (Halbsinus) + stance_traj (Linear)
│   ├── gait_patterns.py               # GaitPattern Dataclass + TRIPOD/SINGLE_LEG_*-Presets
│   ├── gait_engine.py                 # State-Machine + Body-Frame-Mapping (Pure-Python)
│   └── gait_node.py                   # 50 Hz Timer, cmd_vel-Subscriber, JTC-Pubs
├── launch/{stand,gait}.launch.py
└── README.md
```

Erweiterungen in bestehenden Paketen:
- `hexapod_description/urdf/hexapod.foot_contact.xacro` — 6 Contact-Sensoren mit `<topic>` inside `<contact>`-Block (Stufe-D-Bug-Lehre).
- `hexapod_bringup/launch/sim.launch.py` — `enable_foot_contact` LaunchArg + 2 IfCondition-Nodes (Bridge + Publisher).

Acht neue Konzept-/Test-Dokus in `docs/`:
- `phase_5_progress.md` — vollständiger Stufen-Tracker A–I mit Design-Entscheidungen + Live-Werten
- `phase_5_kinematics_gait.md` — Phasenplan
- `phase_5_ik_explained.md` — IK-Math-Hintergrund
- `phase_5_gait_explained.md` — Gait-Konzept (State-Machine, Trajektorien, Body↔Bein-Frame, Pattern-Daten-Shape)
- `phase_5_stage_C_test_commands.md` (Stand-Pose)
- `phase_5_stage_D_test_commands.md` (Foot-Contact)
- `phase_5_stage_E_test_commands.md` (Single-Leg-Schwung)
- `phase_5_stage_F_test_commands.md` (Statisches Tripod)
- `phase_5_stage_G_test_commands.md` (Vorwärts via cmd_vel)
- `phase_5_stage_H_test_commands.md` (Omnidirektional)
- `phase_6_teleop_handoff.md` — kompakter Phase-6-Einstiegspunkt (cmd_vel-Interface, Mapping-Empfehlung, Stolperfallen)
- `01_hardware_change_workflow.md` — neuer Cross-Phase-Reference für Hardware-Änderungen

### Stufen-Übersicht

| Stufe | Inhalt | Live-verifiziert |
|---|---|---|
| A | Paket-Skelett `hexapod_kinematics` (Pure-Python, kein rclpy) | ✅ |
| B | IK + FK + 28 Pure-Python-Tests | ✅ |
| C | `stand_node` (one-shot rclpy, 6× JointTrajectory mit 4 s Lerp) | ✅ Stand-Pose stabil |
| D | Foot-Contact-Sensoren (Gazebo Contact → ROS Bool/Bein) | ✅ Toggle-bar |
| E | Single-Leg-Schwung in der Luft (Pre-Tripod) | ✅ Bein 1 schwingt |
| F | Statisches Tripod-Pattern + GaitPattern-Datenstruktur | ✅ Phasen-Sync 0.5 |
| G | Vorwärts-Walk via cmd_vel + State-Machine + sauberer Stopp | ✅ DK 2,3,4,5 |
| H | Omnidirektional: linear.y + angular.z (Drehen + Seitwärts + Bogen) | ✅ |
| I | Phasenabschluss + Doku | ✅ |

### Wichtige Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| **Pure-Python `hexapod_kinematics`** ohne rclpy | IK-Math als Library testbar mit `pytest`, kein ROS-Setup nötig. Wichtigste Architektur-Entscheidung. |
| **Closed-Form-IK** statt numerischer Solver | Deterministisch, keine Konvergenz-Probleme, ~µs pro Bein. Knie-oben-Konvention. |
| **`GaitPattern`-Dataclass** statt Strategy-Pattern | Alle realistischen statischen Gangarten unterscheiden sich nur in `phase_offset_per_leg` + `swing_duty`. Phase-8-Wave/Ripple = 5 Zeilen pro Pattern. |
| **`body_height = -0.052`** (5 mm tiefer als Phase-4) | JTC-Tracking-Lag-Workaround: Engine kommandiert 5 mm unter Boden, Boden gibt nicht nach, Foot landet exakt → Sensor toggelt zuverlässig. **Phase-7-HW**: Wert zurück auf -0.047. |
| **`time.monotonic()` statt `get_clock().now()`** | DDS-/clock-Discovery-Race in Sim-Bringup vermieden. Engine-Timing wall-clock-basiert. |
| **State-Machine STANDING/WALKING/STOPPING** mit auto-Transitionen | cmd_vel.linear=0 triggert sauberes Settling (Beine in Luft schwingen fertig, Stütz-Beine 0.3 s zu Neutral). Worst-Case-Latenz 1.3 s. |
| **Proportionales Clamping** statt pro-Achse | Bei Kombi-Motion bleibt Bewegungs-Richtung erhalten — User commandiert Bogen, kriegt Bogen (nur ggf. langsamer). |
| **`cmd_vel`-Activity-Timeout 0.5 s** + `default_*`-Fallback | Sicherheits-Mechanismus (cmd_vel-Publisher tot → Roboter hört auf zu laufen) UND Demo-Mode (`default_linear_x:=0.05` für Vorführung). |

### Verifikation

- `colcon build --packages-select hexapod_kinematics hexapod_sensors hexapod_gait` grün
- **`hexapod_kinematics` pytest:** 28 Tests, 0 Failures, 1 skipped (Style: Copyright)
- **`hexapod_gait` Style-Tests:** flake8 + pep257 grün
- **DK 1**: `hexapod_kinematics` gebaut, Pure-Python-Tests grün ✅
- **DK 2**: `cmd_vel.linear.x = 0.05` → sichtbares Vorwärtslaufen (Body-x von 0 → 4.4 m über mehrere Tests akkumuliert) ✅
- **DK 3**: `cmd_vel = 0` → Roboter steht nach 1.3 s in Stand-Pose (cycle_time=2). Strikt <0.5 s nicht erreicht — Roadmap-Wert relaxed dokumentiert. ✅ (relaxed)
- **DK 4**: Tripod-Sequenz erkennbar — 3 schwingen, 3 stützen, alternierend, Foot-Contact-Toggle bestätigt ✅
- **DK 5**: Kein Wegrutschen für kurze Strecken — y-Drift +0.002 m über 9.7 s Walk, Yaw-Drift +0.0017 rad. ✅ (mit dokumentierter Limitation: Yaw-Drift ~1.35°/m bei langen Strecken)
- **Stufe H bonus**: Drehen CCW+CW, Seitwärts +Y/-Y, Bogen, Kombi-3-Achsen, Rückwärts — alle live verifiziert ✅

### Konventions-Änderungen während Phase 5

Keine harten Konventions-Änderungen. `body_height = -0.052` (statt -0.047)
ist ein Sim-spezifischer JTC-Tracking-Lag-Workaround, in
[phase_5_progress.md](docs/phase_5_progress.md) Stufe-F-Design-
Entscheidung 1 dokumentiert. Phase-7-HW setzt zurück auf -0.047.

### Bekannte offene Punkte

- **KDL-Warning** weiter offen — bewusst auf **Phase 6/7** geschoben
  (User-Entscheidung 2026-05-09: stört aktuell und am Pi nicht).
- **Yaw-Drift ~1.35°/m** bei langen Geradeaus-Strecken — Sim-Foot-
  Friction-Asymmetrie. Phase 6 (Teleop) kompensiert durch
  User-Korrektur. Phase 8+ Closed-Loop-Yaw wäre saubere Lösung.
- **DK 3 Stopp-Latenz <0.5 s** strikt nicht erreicht (real 0.8–1.3 s
  abhängig von cycle_time). Roadmap-Wert relaxed akzeptiert.
- **`controllers.yaml` `use_sim_time: true`** und `body_height = -0.052`
  bleiben bis Phase 7. Dort Switch auf `false` und `-0.047` (echte
  Servos haben keinen JTC-Lag).

---

## Phase 6 — Bericht (2026-05-10)

**Ergebnis:** Hexapod wird per **PS4-Controller via USB** gesteuert.
D-Pad fährt + dreht, L2/R2 senken/anheben den Body (nur im Stand),
R1 ist Dead-Man-Switch. Plus Engine-Erweiterung in `gait_node`:
runtime-mutable `body_height` über `/cmd_body_height` mit
STANDING-only-Constraint. **DK 2-5 erfüllt** (DK 1 Tastatur formal
verworfen — direkter Sprung zu PS4 sparte 1+ Tag und ein Wayland-
Risiko).

### Was angelegt wurde

Ein neues Paket:

```
hexapod_teleop/
├── hexapod_teleop/
│   └── joy_to_twist.py            # /joy → /cmd_vel + /cmd_body_height
├── config/
│   └── ps4_usb.yaml               # Achsen-/Button-Mapping PS4 USB
├── launch/
│   └── joy_teleop.launch.py       # joy_node + joy_to_twist
├── README.md                      # Mapping-Tabelle + Stolperfallen
└── package.xml + setup.py
```

Erweiterung in `hexapod_gait`:
- `gait_node.py` neue Subscription `/cmd_body_height` (Float64) mit
  STANDING-State-Check + Clamp auf `[body_height_min, body_height_max]`.
- `gait.launch.py` neue Args `body_height_min=-0.080`, `body_height_max=-0.030`.
- Engine selbst unverändert — `body_height` wurde schon seit Phase 5
  per Tick fresh gelesen, Mutation von außen wirkt sofort.

Neue Dokus in `docs/`:
- `phase_6_progress.md` — Stufen-Tracker A (Stufe B Bluetooth deferred)
- `phase_6_stage_A_test_commands.md` — 13 Test-Schritte mit klaren
  T1/T2/T3/T4-Indikatoren

### PS4-Mapping (Stufe A, USB)

| PS4-Input | Effekt |
|---|---|
| **R1** halten | Dead-Man (Bewegung erlaubt) |
| **D-Pad ↑/↓** | Vorwärts / Rückwärts |
| **D-Pad ←/→** | Drehen am Stand |
| **L2** Trigger | Body senken (-5 mm pro Press) |
| **R2** Trigger | Body anheben (+5 mm pro Press) |

Body-Lift gilt nur wenn Engine im STANDING-State — während Walk
ignoriert mit Warning-Log.

### Wichtige Designentscheidungen

| Entscheidung | Begründung |
|---|---|
| Tastatur-Stufe verworfen | Custom-kbd_to_twist wäre Wegwerfcode (joy_to_twist deckt dasselbe ab). pynput-Wayland-Risiko entfiel. Phase-Dauer von 2-4 Tage auf 0,5 Tag reduziert. |
| **R1** als Dead-Man | Standard-PS-Konvention. Sicherheits-Reflex schon in Sim üben (Phase 7 mit echten Servos braucht das zwingend). |
| **D-Pad** statt Sticks | User-Mental-Modell "Tank-Steuerung" — links/rechts dreht statt seitwärts. Sticks frei für künftige Erweiterung (linear.y, Speed-Scale). |
| **L2/R2 Edge-Detection** statt kontinuierlich | "Ein Druck = ein Schritt". Hold-Repeat würde ein anderes Mental-Modell brauchen. |
| **Body-Height nur im STANDING** mutable | Body-Pose-Wechsel mitten im Walk-Cycle würde den Roboter zum Kippen bringen. Engine-State-Check als Sicherheits-Constraint. |
| **YAML-getriebenes Mapping** | Achsen-Indizes/Vorzeichen/Schwellen pro Controller (PS4 USB, später BT, PS5) als YAML, kein Code-Change nötig. |

### Verifikation

- `colcon build --packages-select hexapod_gait hexapod_teleop` grün
- `colcon test` grün (flake8 + pep257; 1 Iteration für I100-Import-Order)
- Pure-Python Engine-Body-Height-Mutation-Smoke-Test grün
- **Live (2026-05-10):** alle 11 Verifikations-Bullets aus
  `phase_6_stage_A_test_commands.md` durchgelaufen — D-Pad-Bewegung,
  Drehen am Stand, R1-Dead-Man-Stopp, L2/R2-Body-Lift,
  STANDING-only-Constraint, Multi-Direction-Bogen.

### Konventions-Änderungen während Phase 6

Keine. Cmd_vel-Interface aus Phase 5 unverändert. Neuer Topic
`/cmd_body_height` ist additiv.

### Phase-6-Live-Bug

`joy_node`-Parameter-Bug: initial `device_name: /dev/input/js0` —
falsch, weil `device_name` ein SDL-Joystick-Name-String-Match ist
(z.B. "Sony Computer Entertainment Wireless Controller"), nicht ein
Linux-Device-Pfad. Fix: auf `device_id: 0` (int, SDL-Joystick-Index)
gewechselt. Dokumentiert in
[phase_6_progress.md](docs/phase_6_progress.md) Stufe-A-Notiz 1.

### Bekannte offene Punkte

- **Bluetooth-Pairing** (Stufe B) deferred — bei Bedarf später, kein
  technisches Risiko (selbe Code-Basis, neues YAML).
- **Sticks-Mapping** nicht implementiert (LS/RS für linear.y oder
  Speed-Modulation). User hat das nicht gewollt in Stufe A.
- **`controllers.yaml use_sim_time: true`** und `body_height=-0.052`
  bleiben bis Phase 7.
- **KDL-Warning** weiter offen.
