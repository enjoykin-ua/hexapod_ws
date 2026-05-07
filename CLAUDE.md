# Hexapod-Projekt — Arbeitsanweisung für Claude

> **Lies diese Datei und `PHASE.md` zu Beginn jeder Session.**
> `PHASE.md` zeigt dir, in welcher Phase wir gerade arbeiten und verweist
> auf die zugehörige Datei in `docs/`.

---

## 1. Projekt-Kontext

- **Roboter:** 6-beiniger Hexapod, 3 Joints pro Bein (coxa / femur / tibia) = **18 Joints gesamt**.
- **Servo-Treiber:** Servo2040-Board. Kommunikationsprotokoll zwischen ROS2-Node und Servo2040 ist **bereits definiert** und auf Anwendungsebene **unkritisch**. Die ROS-seitige Anbindung erfolgt erst in Phase 7.
- **Recheneinheit Roboter:** Raspberry Pi 4, 8 GB RAM, **Ubuntu Server 24.04 LTS arm64**, headless (kein Desktop-Image).
- **Entwicklungs-/Sim-Rechner:** Ubuntu 24.04 Desktop, NVIDIA RTX 3080.
- **Ziel-Workflow:** Sim am Desktop → Code 1:1 portierbar auf Pi via `ros2_control`-Abstraktion. Pi wird **erst in Phase 7** angefasst.

---

## 2. Tech-Stack (verbindlich, nicht ändern)

| Komponente | Version | Quelle |
|---|---|---|
| OS Desktop | Ubuntu 24.04 LTS Desktop | bereits installiert |
| OS Pi 4 | Ubuntu Server 24.04 LTS arm64 | Raspberry Pi Imager |
| ROS2 | Jazzy Jalisco (LTS bis Mai 2029) | ROS-apt-Repo |
| Simulator | Gazebo Harmonic | über `ros-jazzy-ros-gz` (NICHT über packages.osrfoundation.org) |
| ROS↔Gazebo Bridge | `ros_gz` | `ros-jazzy-ros-gz` |
| Hardware-Abstraktion | `ros2_control` + `gz_ros2_control` | ROS-apt-Repo |
| Visualisierung | `rviz2` | bei `ros-jazzy-desktop` enthalten |
| Sprache High-Level | Python 3.12 (rclpy) | systemweit |
| Sprache Hardware-IF | C++ (rclcpp / pluginlib) | erst in Phase 7 |

**Begründung der Stack-Wahl:** Ab ROS 2 Jazzy kommt Gazebo über sogenannte
*Vendor Packages* aus dem ROS-Repo. Damit ist die Versionierung systematisch
gelöst — es darf **keine** zweite Paketquelle für Gazebo (z. B.
`packages.osrfoundation.org`) eingebunden werden, sonst entstehen genau die
Versions-Konflikte, die wir vermeiden wollen.

---

## 3. User-Profil

- 8+ Jahre Fullstack-SW-Entwicklung
- Master Informationstechnik, Bachelor Technische Informatik
- Embedded-C-Hintergrund, Hardware-Erfahrung (eigenes PoE-Modul, Schaltplan/Layout/Firmware)
- Java für Tooling (Eclipse), Python lesend + Skript-Niveau
- **ROS2 / Gazebo / RViz: Neuling** — aber kein Programmier-Anfänger
- Erkläre auf Peer-Niveau eines erfahrenen Ingenieurs.
  Erläutere ROS2-spezifische Idiome (Lifecycle, DDS, tf2, Launch-Files etc.)
  da diese neu sind, aber spar dir Erklärungen zu Grundlagen wie OOP,
  Build-Systemen, Git, Linux-CLI.

---

## 4. Arbeitsweise

- **Phasenweise.** Aktuelle Phase steht in `PHASE.md`. Phasen werden nicht
  übersprungen, auch wenn der User „mal eben weitergehen" will.
  Wenn der User springen will: höflich blocken und Done-Kriterium der
  aktuellen Phase abfragen.
- **Pro Schritt:** erst Konzept besprechen → dann Implementierung → dann Test.
- **Tests grün vor Commit.** Keine Commits mit roten Tests.
- **Commits referenzieren Phase + Teilziel:** z. B. `phase2: add coxa joint xacro macro`.
- **Bei Unsicherheit nachfragen statt raten.** „Ich weiß es nicht" oder
  „Die Information fehlt" sind valide Antworten. Keine erfundenen Parameter,
  keine erfundenen Bauteile, keine plausibel klingenden Fakten ohne Beleg.
- **Vollständig lesen, nicht fragmentarisch.** Wenn referenzierte Dateien
  oder Quellen geprüft werden, vollständig.
- **Korrekturpflicht.** Wenn der User eine technisch widersprüchliche oder
  unmögliche Anweisung gibt, korrigieren statt blind ausführen.

---

## 5. STRIKTE VERBOTE FÜR SHELL-KOMMANDOS

> **Hintergrund:** Beim letzten Versuch wurde das Ubuntu-System durch
> unkontrollierte System-Updates / Treiber-Eingriffe zerstört. Das passiert
> nicht nochmal.

### Niemals ohne explizites „GENEHMIGT" vom User:

- `sudo apt full-upgrade` / `sudo apt dist-upgrade`
- `do-release-upgrade`
- `add-apt-repository` (jegliche PPAs)
- Installation oder Deinstallation von Paketen, deren Name eines der
  folgenden Wörter enthält:
  `nvidia`, `mesa`, `xorg`, `wayland`, `libgl`, `linux-image`,
  `linux-headers`, `kernel`, `grub`
- Änderungen unter `/etc/apt/`, `/etc/X11/`, `/etc/modprobe.d/`,
  `/etc/default/grub`
- `apt-mark hold` / `apt-mark unhold`
- Eingriffe in Display-Manager (`gdm3`, `lightdm`, `sddm`)
- `reboot`, `shutdown`, `systemctl reboot`, `init 6`
- `rm -rf` außerhalb von `~/hexapod_ws/`
- Schreiben in `/opt/`, `/usr/`, `/etc/` außer wo explizit hier erlaubt

### Erlaubt ohne Rückfrage:

- `sudo apt install ros-jazzy-*` (ausschließlich ROS-Pakete)
- `sudo apt install` für klar dokumentierte Build-Tools aus
  `docs/phase_0_setup.md` (z. B. `git`, `python3-colcon-common-extensions`,
  `ros-dev-tools`)
- `pip install` in `venv` oder mit `--user`
- Alles unter `~/hexapod_ws/`
- `git`-Operationen im Workspace
- `colcon build`, `colcon test`
- ROS-CLI-Befehle (`ros2 ...`, `rviz2`, `gz sim` etc.)

### Goldene Regel

Wenn ein Fehler auftritt und ein System-Update als Lösung erwogen wird:
**STOP.** Erst Diagnose. Welcher konkrete Beweis stützt die Update-Hypothese?
Bei Grafik-/RViz-Anomalien zuerst URDF, Mesh-Pfade, `package://`-URIs,
Material-Definitionen prüfen — **nicht Treiber.**

---

## 6. Fehler-Diagnose-Workflow

1. **Beobachtung exakt formulieren** (was ist das Symptom?)
2. **Logs sammeln** (`ros2 topic echo`, `ros2 node info`, `ros2 doctor`,
   Gazebo-Konsole, RViz-Konsole, `colcon test --event-handlers console_direct+`)
3. **Hypothese formulieren** (mit Beleg)
4. **Hypothese gezielt testen** (kleinster möglicher Eingriff)
5. **Ergebnis bewerten**, ggf. zurück zu 3
6. Erst nach bestätigter Diagnose: Fix anwenden

Verboten als Lösungsansatz: „Ich update mal alles", „Ich installiere
das System neu", „Ich tausche den Treiber".

---

## 7. Workspace-Struktur (Soll)

```
~/hexapod_ws/
├── CLAUDE.md                   # diese Datei
├── PHASE.md                    # aktuelle Phase
├── docs/                       # Phasen-Dokumentation
│   ├── 00_conventions.md
│   ├── phase_0_setup.md
│   ├── phase_1_ros2_basics.md
│   ├── phase_2_description.md
│   ├── phase_3_gazebo.md
│   ├── phase_4_ros2_control.md
│   ├── phase_5_kinematics_gait.md
│   ├── phase_6_teleop.md
│   └── phase_7_pi_port.md
└── src/
    ├── hexapod_description/    # URDF, Meshes (alle Maschinen)
    ├── hexapod_gazebo/         # Sim-Welt, Sim-Plugins (nur Desktop)
    ├── hexapod_control/        # ros2_control config (alle)
    ├── hexapod_kinematics/     # IK-Bibliothek + Tests (alle)
    ├── hexapod_gait/           # Gait-Engine (alle)
    ├── hexapod_teleop/         # Teleop-Knoten (alle)
    ├── hexapod_hardware/       # Custom HardwareInterface (nur Pi, C++)
    └── hexapod_bringup/        # Launch-Files sim/real (alle)
```

Welche Pakete auf welcher Maschine installiert werden, regeln die
Launch-Files in `hexapod_bringup`. Auf dem Pi werden `hexapod_gazebo`
und ggf. `hexapod_teleop` (falls Joystick am Desktop bleibt) gar nicht
gebaut.

---

## 8. Konventionen

Siehe `docs/00_conventions.md` für die vollständige Liste.
Kurzfassung:

- Joint-Naming: `leg_<n>_{coxa,femur,tibia}_joint`, n ∈ 1..6
- `base_link` mittig, +X vorne, +Z oben (REP-103)
- Alle Längen in **Meter**, Winkel in **Radiant**
- SI-Einheiten durchgehend
- Launch-Files in **Python**, nicht XML
- Massen + Inertien aus echtem CAD oder dokumentierter Schätzung
  (NICHT erfinden — wenn unbekannt, Platzhalter mit `# TODO: from CAD`)

---

## 9. Sicherheit (Hardware, Phase 7)

In Phase 7, beim ersten Anschluss echter Servos:

- Roboter MUSS aufgebockt sein (Beine in der Luft, kein Bodenkontakt).
- Hardware-Kill-Switch (Stromtrennung) griffbereit.
- Erst ein einzelner Joint, dann ein Bein, dann alle.
- Servo-Endlagen / Strom-Limits in Software UND Hardware redundant absichern.
- Erste Bewegung mit reduzierter Geschwindigkeit (z. B. 10 % der Nennrate).
