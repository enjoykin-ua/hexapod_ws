# Phase 2 — Fortschritt

Beim Neustart: diese Datei lesen, dann mit dem ersten offenen Schritt weitermachen.
Stufenplan A–E gemäss `docs/phase_2_description.md` §Strategie.

---

## Stufe A — Paket-Skelett, Chassis + 1 Bein (ohne Foot, Box-Visuals) ✅

- [x] Tools verifiziert (`ros-jazzy-xacro`, `ros-jazzy-joint-state-publisher-gui`, `ros-jazzy-robot-state-publisher`)
- [x] `ros2 pkg create hexapod_description` (`ament_cmake`, Apache-2.0, `--maintainer-email`)
- [x] Verzeichnisstruktur angelegt: `urdf/`, `launch/`, `config/`
- [x] `CMakeLists.txt`: `install(DIRECTORY urdf launch config DESTINATION share/${PROJECT_NAME})`
- [x] `package.xml` `<exec_depend>`s: `xacro`, `robot_state_publisher`, `joint_state_publisher_gui`, `rviz2` (keine `TODO:`-Stubs)
- [x] `urdf/hexapod_physical_properties.xacro` (Maße, Massen, Limits aus Konventionen §11)
- [x] `urdf/materials.xacro` (orange / grey / black)
- [x] `urdf/inertials.xacro` (`box_inertia` Macro mit `inertia_min = 1e-5`)
- [x] `urdf/leg.xacro` initial: coxa + femur + tibia (ohne Foot-Link, Foot kommt in Stufe B)
- [x] `urdf/hexapod.urdf.xacro` Top-Level: `base_link` + 1 Bein-Instanz (`leg_1`)
- [x] `xacro hexapod.urdf.xacro > /tmp/hexapod.urdf` läuft ohne Fehler
- [x] `check_urdf /tmp/hexapod.urdf` grün, Baum vollständig gedruckt
- [x] `colcon build --packages-select hexapod_description` grün

---

## Stufe B — Foot-Link (Kugel) am Bein-Ende

- [ ] `sphere_inertia` Macro in `inertials.xacro` ergänzt (mit `inertia_min`-Schranke)
- [ ] Foot-Link in `leg.xacro`: `joint type=fixed`, parent=tibia, child=foot, origin `${tibia_length} 0 0`
- [ ] Foot-Link mit `<visual>` + `<collision>` (Kugel `foot_radius`) und `sphere_inertia`
- [ ] `xacro` + `check_urdf` erneut grün, Foot-Link erscheint im Baum

---

## Stufe C — Bein als Macro, 6× instanziiert

- [ ] In `hexapod.urdf.xacro` alle 6 Beine instanziiert mit Mountpunkten + yaw aus Konventionen §11.3
- [ ] `xacro` + `check_urdf` grün
- [ ] Frame-Anzahl plausibel: `1 base_link + 6 × 4 = 25` Links

---

## Stufe D — Inertien, Kollisionen, Joint-Limits final

- [ ] `box_inertia` und `sphere_inertia` mit `max(..., inertia_min)` an allen Links
- [ ] Alle Links haben `<collision>` mit derselben Geometrie wie `<visual>`
- [ ] Alle revolute Joints haben `<limit>` mit Werten aus Konventionen §11.4
- [ ] Foot-Joint ist `fixed` (kein Slider in `joint_state_publisher_gui`)
- [ ] Cross-Check gegen `docs/00_conventions.md` §11 (Maße, Massen, Mountpunkte, Limits)

---

## Stufe E — Launch, RViz, tf-Tree, README

- [x] `launch/display.launch.py` (xacro Command-Substitution, `robot_state_publisher`, `joint_state_publisher_gui`, `rviz2 -d view.rviz`) — vorgezogen für Smoke-Test mit 1 Bein
- [x] `config/view.rviz` initial: Fixed Frame `base_link`, Displays `RobotModel` + `TF` + `Grid`
- [x] `colcon build --symlink-install` grün
- [ ] `ros2 launch hexapod_description display.launch.py` öffnet RViz ohne Fehler
- [ ] Alle 6 Beine sichtbar, alle 18 Joints in Slider-GUI bewegbar, Drehrichtungen plausibel
- [ ] `ros2 run tf2_tools view_frames` erzeugt `frames.pdf` mit allen 6 Beinen bis `foot_link`
- [ ] `README.md` in `hexapod_description/` (Zweck, Launch-Aufruf, Frame-Tree-Auszug)

---

## Phasenabschluss

- [ ] Alle 6 Done-Kriterien aus `phase_2_description.md` erfüllt
- [ ] `package.xml` ohne `TODO:`-Stubs
- [ ] Timeshift-Snapshot `phase_2_done`
- [ ] Git-Commit + Tag `phase-2-done`
- [ ] `PHASE.md` auf Phase 3 aktualisiert
- [ ] Kurze Retro: was lief gut, was hat länger gedauert, was bleibt offen
