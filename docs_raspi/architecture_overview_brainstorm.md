# Architektur-Übersicht — Brainstorm + Komponenten-Katalog

> **Status:** Ideen-Sammlung + Komponenten-Katalog, kein Phasen-Doc.
> Vorbereitung für eine eventuelle vollständige Architektur-Doku
> (z.B. `docs/architecture.md`).
>
> **Zweck:** Tool-Optionen für Visualisierung vergleichen, alle
> Komponenten + Datenflüsse erfassen damit nichts vergessen wird,
> Strategien für systematisches Erfassen sammeln.
>
> **Wann umsetzen:** offen — könnte als eigene Querschnitts-Phase
> oder vor Phase 12 (Pi-Plattform) durchgezogen werden.

---

## 1. Tool-Optionen für die Darstellung

### A. Mermaid (Markdown-embedded) — **Empfehlung**

- Direkt in GitHub/GitLab-Markdown gerendert
- Git-friendly (Text), Diffable
- Alle Diagram-Typen verfügbar: flowchart, sequence, class, state, ER, component
- Aktiv weiterentwickelt
- **Beispiel-Look:**

  ```mermaid
  graph LR
    Joy[PS4-Joystick] --> Teleop[teleop_node]
    Teleop -->|cmd_vel| Gait[gait_node]
    Gait -->|joint_trajectory| JTC[JTC×6]
  ```

### B. PlantUML

- Mächtiger bei komplexen Diagrammen, mehr Optionen
- Braucht Plugin/Extension zum Rendern (GitHub zeigt's nicht nativ)
- Lernkurve etwas steiler

### C. Draw.io / diagrams.net

- Visuell-grafisches Tool, web-basiert
- Schöner als Text-Diagramme aber schwerer zu warten + schlechte Git-Diffs
- Pro: jeder kann's bedienen ohne Syntax-Wissen

### D. C4-Model (Simon Brown)

- **Strukturierter Ansatz** statt freies Diagrammen
- Vier Zoom-Ebenen: Context → Container → Component → Code
- Force systematisch durchzudenken
- Kann mit Mermaid oder PlantUML gerendert werden

### E. rqt_graph (ROS-Live-Topology)

- **Automatisch** generiert aus laufenden ROS-Nodes
- Zeigt Topics + Nodes live
- Aber: nur ROS-Topology, keine Threads/Files/State

### F. Multi-Layer-Approach (Kombination — Vorschlag)

- **C4-Struktur** als Gerüst
- **Mermaid-Diagramme** für die Visualisierungen
- **rqt_graph-Screenshot** als Live-Vergleich
- **Tabellen** für Topics/Params/Files/Tests

---

## 2. Was alles erfasst werden muss — Komplett-Katalog (10 Layer)

### Layer 1: Stakeholder + Externe Systeme

- **User** (Mensch)
  - PS4-Controller (USB)
  - Tastatur (RViz/Gazebo)
  - rqt-GUIs (Phase 11)
- **Externe Hardware**: Bench-PSU, Multimeter, Oszi (Phase 9 pending)
- **Externe Software**: ROS2 Jazzy, Gazebo Harmonic, Ubuntu 24.04

### Layer 2: ROS2-Pakete (8 Stück) + Firmware

| Paket | Sprache | Pflicht-Rolle |
|---|---|---|
| `hexapod_description` | xacro/XML | URDF + Mesh-Quelle |
| `hexapod_gazebo` | XML/SDF + Python | Sim-Welt + sim.launch.py |
| `hexapod_control` | YAML + Python | ros2_control Config |
| `hexapod_kinematics` | Python | IK-Mathematik, kein ROS |
| `hexapod_gait` | Python | gait_node + Engine + Patterns |
| `hexapod_teleop` | Python | PS4 → cmd_vel |
| `hexapod_hardware` | C++ | Servo2040-Plugin (pluginlib) |
| `hexapod_bringup` | Python | Launch-Files (sim/real) |
| `~/hexapod_servo_driver/` | C++ (Pico SDK) | Servo2040-Firmware (separates Repo) |

### Layer 3: Komponenten pro Paket

**hexapod_gait:**

- `gait_node.py` — ROS-Wrapper, 50 Hz Timer
- `gait_engine.py` — State-Maschine (STANDING/WALKING/STOPPING)
- `gait_patterns.py` — Tripod-Preset
- `trajectory_gen.py` — pro-Bein-Trajectory-Berechnung
- `stand_node.py` — initialer Stand-Pose-Setup

**hexapod_hardware (C++):**

- `HexapodSystemHardware` (SystemInterface) — Hauptklasse
- `SerialPort` — USB-CDC-Wrapper (cfmakeraw, O_NONBLOCK+poll)
- `ReaderThread` — Frame-Stream-Parser-Loop
- `Calibration` — YAML-Loader für servo_mapping
- `FrameCodec` — COBS + CRC-16 + Opcode-Encoder/Decoder
- `Reconnect-Logic` — Backoff-Loop

**hexapod_kinematics:**

- `leg_ik()` — die Hauptfunktion
- `base_to_leg_frame()` — Frame-Transform
- `LegConfig`, `HexapodConfig`, `HEXAPOD` — Daten

### Layer 4: Threads / Concurrency

- **gait_node**: Timer-Thread (50 Hz) + Subscription-Thread (cmd_vel) +
  Service-Thread (Phase 11: Param-Callback)
- **hexapod_hardware Plugin**:
  - Main-Thread (ros2_control 50 Hz read+write)
  - Reader-Thread (USB-CDC poll, Frame-Stream)
- **controller_manager**: eigener Real-Time-Thread (RT scheduling
  versucht, fällt auf normal zurück)
- **rclpy / rclcpp Executors**: Default-Multi-Threaded mit
  ReentrantCallbackGroup

### Layer 5: Topics / Services / Actions

| Name | Type | Producer | Consumer |
|---|---|---|---|
| `/cmd_vel` | geometry_msgs/Twist | teleop_node, rqt_publisher, user-CLI | gait_node |
| `/cmd_body_height` | std_msgs/Float64 | teleop_node (L2/R2) | gait_node |
| `/leg_X_controller/joint_trajectory` (×6) | trajectory_msgs/JointTrajectory | gait_node | JTC |
| `/leg_X_controller/follow_joint_trajectory` (×6) | Action | User-Tool, F.2-Skript | JTC |
| `/joint_states` | sensor_msgs/JointState | joint_state_broadcaster | robot_state_publisher, rqt_plot, RViz |
| `/robot_description` | std_msgs/String | robot_state_publisher (Param) | RViz, ros2_control_node |
| `/tf`, `/tf_static` | tf2_msgs/TFMessage | robot_state_publisher | RViz, gait_node? |
| `/foot_contact_<n>` | std_msgs/Bool | Gazebo-Sensor-Plugin (Sim-only) | gait_node (wenn enable_foot_contact=true) |
| `/servo_pulses` (Phase 11 geplant) | tbd | hexapod_hardware Plugin | rqt_plot |

### Layer 6: Files / Configs

- **URDF**: hexapod.urdf.xacro + hexapod_physical_properties.xacro +
  leg.xacro + inertials.xacro
- **YAML**: servo_mapping.yaml (Plugin) + controllers.yaml (Sim) +
  controllers.real.yaml (HW)
- **Launch**: sim.launch.py, real.launch.py, gait.launch.py,
  stand.launch.py, display.launch.py
- **Presets** (Phase 11 geplant): src/hexapod_gait/config/presets/*.yaml
- **Memory**: MEMORY.md + ~16 Einträge

### Layer 7: State Machines

- **GaitEngine**: STANDING ↔ WALKING ↔ STOPPING
- **hexapod_hardware Plugin Lifecycle**: Unconfigured → Inactive →
  Active → Inactive → Finalized
- **JTC**: idle → executing → succeeded/aborted/cancelled
- **Tripod-Pattern**: Group A (1,3,5) Swing | Group B (2,4,6) Stance —
  alterniert pro Cycle-Hälfte
- **Servo2040 Firmware**: Init → Idle → Enabled-Running → Watchdog-Tripped

### Layer 8: Tests

- hexapod_hardware: 208 unit + 20 skipped + launch_testing (in
  hexapod_bringup 18)
- hexapod_kinematics: 28 + 1 skipped (test_config, test_leg_ik,
  test_geometry)
- hexapod_control: 5 (Lint)
- hexapod_gait: 3 (Lint-Only, **keine Unit-Tests** für gait_node!)

### Layer 9: User-Tools / Scripts

- `~/hexapod_servo_driver/tools/log_state.py` — Strom-CSV-Logger
- `~/hexapod_ws/tools/phase_10_f2_ik_probe.py` — IK-Probe
- `colcon build/test` — Standard
- `ros2 ...` CLI
- rqt + rqt_reconfigure + rqt_plot + rqt_topic (Phase 11)

### Layer 10: Hardware

- Raspberry Pi 4 (oder 5) 8 GB
- Servo2040 RP2040 Board (USB-CDC)
- 18 Servos (6× Coxa Diymore 8120MG 20 kg·cm, 12× Femur/Tibia Miuzei
  MS61 35 kg·cm)
- Bench-PSU 7.0 V / 8 A
- DCDC (Phase 8, pausiert)
- Body-Mechanik + Aufhängung

---

## 3. Strategien damit nichts vergessen wird

### 1. C4-Model durchwandern (vier Zoom-Ebenen)

```text
Level 1 — Context:  Wer interagiert mit Hexapod? (User + Hexapod + Bench-Hardware)
Level 2 — Container: Welche Software-Bausteine? (8 ROS-Pakete + Firmware + Sim-Engine)
Level 3 — Component: Welche Klassen/Threads/Files pro Container?
Level 4 — Code:     Welche Funktionen/Methoden pro Component? (meist nur für kritische Pfade)
```

### 2. Datenfluss-Tracing

- Beginne mit User-Input (PS4 oder rqt-Slider)
- Verfolge **jeden Hop** bis zur Servo-PWM-Pulse
- Markiere alle Komponenten die du dabei berührst
- Wiederhole für **alle 3 Input-Quellen** (PS4, rqt_reconfigure,
  F.2-IK-Skript)
- Wiederhole für **alle 2 Output-Pfade** (Sim, HW)

### 3. Phase-für-Phase-Inventar

- Jede Phase 0–13 hat etwas eingeführt (Komponente, Topic, Tool)
- Lese sequenziell die Phase-Docs durch und sammle was neu kam
- Phase 0 (Setup) → was wurde installiert?
- Phase 2 (URDF) → welche xacro-Files?
- Phase 4 (ros2_control) → welche Configs?
- ... usw.

### 4. Live-Topology als Korrektiv

- Sim + HW-Pfad beide starten
- `rqt_graph` → Screenshot vergleichen mit manuellem Diagramm
- `ros2 topic list -t` → vollständige Topic-Liste mit Types
- `ros2 node list && ros2 node info /xyz` → Topic-IO pro Node
- `ros2 param list` → komplette Param-Liste pro Node
- Lücken zwischen Live-Output und Diagramm = etwas vergessen

### 5. Filesystem-Inventar

```bash
find src/ -name "*.py" -o -name "*.cpp" -o -name "*.hpp" | xargs grep -l "rclpy\|rclcpp"
# → alle ROS-Nodes
find src/ -name "*.yaml"
# → alle Configs
find src/ -name "*.xacro" -o -name "*.urdf"
# → alle URDFs
find src/ -name "*.launch.py"
# → alle Launch-Files
```

### 6. Cross-Check mit CLAUDE.md §7 Workspace-Struktur

Die Soll-Struktur in CLAUDE.md ist die kanonische Liste — alles was
darin steht muss im Diagramm sein.

---

## 4. Konkreter Vorschlag — Dokument-Struktur

Wie eine vollständige Architektur-Doku aufgebaut wäre:

```text
docs/architecture.md
├── 1. System-Context (Wer interagiert? — 1 Mermaid-Diagram)
├── 2. Container-View (8 ROS-Pakete + Firmware — 1 Mermaid-Diagram)
├── 3. Component-Views (eine pro großem Container):
│   ├── 3.1 hexapod_gait (Klassen + Threads)
│   ├── 3.2 hexapod_hardware Plugin (Klassen + Threads)
│   ├── 3.3 controller_manager + JTC×6
│   ├── 3.4 Sim-Stack (gz_ros2_control + Gazebo)
│   └── 3.5 Tooling (rqt, rviz2, etc.)
├── 4. Datenfluss-Sequenzen (eine pro Use-Case):
│   ├── 4.1 PS4 → Sim
│   ├── 4.2 PS4 → HW
│   ├── 4.3 rqt_reconfigure → gait_node (Phase 11)
│   ├── 4.4 IK-Probe-Skript → leg_6
│   └── 4.5 gait_node-Tripod-Cycle (intern, mit Phasen)
├── 5. State-Machines (3-4 State-Diagrame)
├── 6. Threading-Modell (Diagram mit Sync-Punkten)
├── 7. Topic/Service/Action-Tabelle (vollständig)
├── 8. File-Inventar (Configs, URDFs, Launches)
└── 9. Phase-Map (Welche Komponente wurde in welcher Phase eingeführt?)
```

**Aufwand-Schätzung**: 1-2 d wenn man's sauber macht. Eher in einer
eigenen „Doku-Phase" oder als Querschnitts-Doku ohne Phasen-Block.

---

## 5. Empfohlene Umsetzungs-Reihenfolge

**Wenn das umgesetzt werden soll:**

1. **Anfang: System-Context + Container-View** mit Mermaid — gibt 80%
   Wert mit 20% Aufwand
2. **Stage 2: Datenfluss-Sequenzen** für die 3-4 wichtigsten Use-Cases
3. **Stage 3: Threading + State-Machines** wenn tiefer
4. **Stage 4: Vollständige Tabellen** (Topics, Params, Files) als
   Referenz-Anhang

**Tooling-Pflicht-Setup für Generierung**:

- VS Code mit Mermaid-Preview-Extension (Live-Render beim Editieren)
- Optional: `mmdc` CLI für PNG/SVG-Export (Markdown → Bild)

---

## 6. Subtile Risiken — was leicht vergessen wird

Hauptrisiken sind die **nicht-offensichtlichen Sachen**:

- **Memory-Einträge** (MEMORY.md, Cross-Session-Wissen)
- **Threading** (oft im Diagramm vergessen)
- **Firmware-Watchdog** (eigene State-Maschine außerhalb ROS)
- **Backoff-Reconnect-Logik** (USB-Recovery)
- **Tests als Komponenten** (launch_testing-Setup hat eigene Topology)
- **Gazebo-Sim-spezifische Components** (foot_contact_sensors,
  gz_ros2_control)
- **Tooling außerhalb ROS** (log_state.py, rqt-Plugins)
- **Param-Server-Topology** (Phase 11 macht das gerade relevant)
- **CLI-Workflows** (`ros2 param dump`, `colcon`, `git`)
- **Hardware außerhalb des Roboters** (Bench-PSU, Multimeter, Hängevorrichtung)

---

## 7. Nächste Schritte (offen)

- [ ] Entscheiden ob Architektur-Doku eine eigene Phase wird oder
      Querschnitts-Doc
- [ ] Tool-Final-Wahl (Mermaid empfohlen)
- [ ] Erste Container-View skizzieren (~2 h Test-Aufwand)
- [ ] Bei Bedarf: VS Code Mermaid-Preview-Extension einrichten
- [ ] Phase-für-Phase-Inventar erstellen als Anhang
