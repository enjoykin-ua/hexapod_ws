# Sim- & Viz-Fähigkeiten (was wir implementiert haben)

> 🟡 Wachsendes Dokument. Überblick, was Gazebo / RViz + unsere Tools im Projekt leisten.

## Gazebo (Harmonic, via `ros-jazzy-ros-gz`)
- Physik-Sim des Hexapods; Spawn in `power_on_mid` (Init-Pose, nicht T-Pose).
- `gz_ros2_control` stellt das `ros2_control`-System → dieselben Controller/Topics wie HW
  → Code 1:1 portierbar (Sim-Pfad ↔ HW-Pfad nur über Launch unterschieden).
- Reibung an Foot-Kugeln (Stand-/Lauf-Tests am Boden).
- Start: `ros2 launch hexapod_bringup sim.launch.py`.

## RViz
- Modell + `/tf` (robot_state_publisher); HW-Spiegel via `view_hw.rviz` (zeigt echte
  `/joint_states` 1:1) → HW=RViz-Vergleich bei Live-Tests.
- **Reachability-Viz:** erreichbare Fuß-Hülle pro Bein (blau/rot) — `reachability_viz.launch.py`.
- **(geplant) Torque-/Hitze-Viz:** Gelenk-Momente als Zahl+Farbe pro Pose.
- Joint-Slider (`joint_state_publisher_gui`) via `display.launch.py` zum manuellen Posen-Fahren.

## Offline-Tools (kein Sim/HW nötig)
- `walking_envelope_check` / `standup_envelope_check` — IK-Simulation gegen Limits.
- Siehe [`tools_catalog.md`](tools_catalog.md).

## Was die Sim NICHT abbildet (Vorsicht)
- **Sim-IK ist lenient** (Phase-5-Pfad ohne Limit-Check) → Limit-Verletzungen, die auf HW
  freezen, fallen in Sim nicht auf. Immer mit den URDF-Limits + Envelopes gegenprüfen.
- Servo-Hitze, Strom, reale Reibung/Schlupf, Servo-Hold-Jitter — nur am echten Roboter.
