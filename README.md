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
| 3 | Gazebo-Simulation | 🟡 aktiv |
| 4 | `ros2_control` | offen |
| 5 | Inverse Kinematik & Gait | offen |
| 6 | Teleop | offen |
| 7 | Pi-Portierung & Hardware | offen |

## Pakete

| Paket | Status | Zweck |
|---|---|---|
| `hexapod_description` | ✅ Phase 2 | URDF/Xacro, RViz-Display |
| `hexapod_gazebo` | offen | Sim-Welt, Spawn |
| `hexapod_control` | offen | `ros2_control`-Config |
| `hexapod_kinematics` | offen | IK |
| `hexapod_gait` | offen | Gait-Engine |
| `hexapod_teleop` | offen | Joystick/Tastatur |
| `hexapod_hardware` | offen | C++ HardwareInterface (Pi) |
| `hexapod_bringup` | offen | Launch-Files sim/real |

## Quickstart

```bash
cd ~/hexapod_ws
colcon build --symlink-install
source install/setup.bash
ros2 launch hexapod_description display.launch.py
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
