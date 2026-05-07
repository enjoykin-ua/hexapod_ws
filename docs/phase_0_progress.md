# Phase 0 — Fortschritt

Beim Neustart: diese Datei lesen, dann mit dem ersten offenen Schritt weitermachen.

---

## Erledigt

- [x] Timeshift installiert, Snapshot angelegt (pre-ros)
- [x] `git` installiert (2.43.0)
- [x] Locale geprüft: `de_DE.UTF-8` — kein Handlungsbedarf
- [x] Universe-Repo bereits aktiv — kein Handlungsbedarf
- [x] ROS2-apt-Repo eingerichtet via `ros2-apt-source` 1.2.0~noble
- [x] ROS2 Stack installiert (alle Pakete auf `ii`):
  - `ros-jazzy-desktop` 0.11.0
  - `ros-jazzy-ros-gz` 1.0.22
  - `ros-jazzy-ros2-control` 4.44.0
  - `ros-jazzy-ros2-controllers` 4.39.0
  - `ros-jazzy-gz-ros2-control` 1.2.17
  - `ros-jazzy-joint-state-publisher-gui` (als Abhängigkeit)
  - `ros-jazzy-xacro` 2.1.1
  - `ros-dev-tools` 1.0.1
- [x] **Schritt 5** — Environment in `~/.bashrc` eingetragen:
  `source /opt/ros/jazzy/setup.bash`, `ROS_DOMAIN_ID=42`, `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`
- [x] **Schritt 6** — ÜBERSPRUNGEN (bewusst): `QT_QPA_PLATFORM=xcb` wird nur gesetzt
  wenn `gz sim` tatsächlich ein schwarzes Fenster zeigt. Fix ist bekannt.
- [x] **Schritt 7** — Workspace angelegt: `~/hexapod_ws/src` + `colcon build`
  → `Summary: 0 packages finished` ✅

---

- [x] **Schritt 8** — `source ~/hexapod_ws/install/setup.bash` in `~/.bashrc` eingetragen

---

## Offen (nächster Schritt: 9)

- [ ] **Schritt 9** — Git-Identität setzen + `git init` + `.gitignore` + erster Commit
- [x] **Schritt 10** — 4 Smoke-Tests grün:
  1. talker / listener ✅
  2. `gz sim` ✅ (libEGL-Warnungen harmlos, Fenster öffnet korrekt)
  3. `rviz2` ✅ (OpenGL 4.6 bestätigt)
  4. `colcon build` ✅ (0 packages, 0 errors)
  > Hinweis: Neue Terminals sourced `~/.bashrc` automatisch. Bereits offene
  > Terminals einmalig mit `source ~/.bashrc` aktivieren.
- [ ] Timeshift-Snapshot `phase_0_done` anlegen
- [ ] Git-Tag `phase-0-done`
- [ ] `PHASE.md` auf Phase 1 setzen
