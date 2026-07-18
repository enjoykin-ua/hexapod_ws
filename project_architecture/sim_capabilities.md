# Sim- & Viz-Fähigkeiten (was wir implementiert haben)

> 🟡 Wachsendes Dokument. Überblick, was Gazebo / RViz + unsere Tools im Projekt leisten.

## Gazebo (Harmonic, via `ros-jazzy-ros-gz`)
- Physik-Sim des Hexapods; Spawn in `power_on_mid` (Init-Pose, nicht T-Pose).
- `gz_ros2_control` stellt das `ros2_control`-System → dieselben Controller/Topics wie HW
  → Code 1:1 portierbar (Sim-Pfad ↔ HW-Pfad nur über Launch unterschieden).
- Reibung an Foot-Kugeln (Stand-/Lauf-Tests am Boden).
- **Kamera-Live-Bild (Block I Ph.4):** gz-Kamera-Sensor (`hexapod.camera.xacro`, vorne oben am
  Body, geradeaus, 1280×720) → `ros_gz_bridge` → `/camera/image_raw` → `web_video_server`
  (:8080, MJPEG) → Handy/Desktop-Browser. Braucht `gz-sim-sensors-system` in der Welt
  (`empty_imu.sdf` + `ramp.sdf.xacro`). Toggle `enable_camera` (Default true). Sim = Gazebo-
  Kamera, real später = Raspi-Cam v1.3 auf demselben Topic. Live gemessen ~11 Hz (Render-Jitter).
- Start: `ros2 launch hexapod_bringup sim.launch.py`.

## RViz
- Modell + `/tf` (robot_state_publisher); HW-Spiegel via `view_hw.rviz` (zeigt echte
  `/joint_states` 1:1) → HW=RViz-Vergleich bei Live-Tests.
- **Reachability-Viz:** erreichbare Fuß-Hülle pro Bein (blau/rot) — `reachability_viz.launch.py`.
- **Torque-/Hitze-Viz:** Gelenk-Momente als Zahl+Farbe pro Pose — `torque_viz.launch.py` (gebaut).
- **Fußkontakt-Viz (A5 St.5):** Fuß wird grün/grau/dunkel je Kontakt — `foot_contact_viz` (Sim+HW).
- Joint-Slider (`joint_state_publisher_gui`) via `display.launch.py` zum manuellen Posen-Fahren.

## Offline-Tools (kein Sim/HW nötig)
- `walking_envelope_check` / `standup_envelope_check` — IK-Simulation gegen Limits.
- Siehe [`tools_catalog.md`](tools_catalog.md).

## Was die Sim NICHT abbildet (Vorsicht)
- **Sim-IK ist lenient** (Phase-5-Pfad ohne Limit-Check) → Limit-Verletzungen, die auf HW
  freezen, fallen in Sim nicht auf. Immer mit den URDF-Limits + Envelopes gegenprüfen.
- Servo-Hitze, Strom, reale Reibung/Schlupf, Servo-Hold-Jitter — nur am echten Roboter.
- **Kamera-Bild ist idealisiert:** die gz-Kamera hat keine Linsenverzeichnung, kein Sensor-Rauschen,
  keine Belichtungs-/Weißabgleich-Effekte und eine gesetzte FoV (1.089 rad). Die reale Raspi-Cam v1.3
  (Phase 7) weicht in FoV/Verzeichnung/Latenz ab → beim HW-Anschluss FoV + `web_video_server`-
  Auflösung/FPS neu justieren (gleiches Topic, Bridge/App unverändert).
- **IMU/Fußkontakt-Closed-Loop ist NUR sim-getestet:** adaptiver Touchdown/Stand + IMU-Leveling
  laufen in der Sim (gz-IMU spawn-referenziert, idealer gz-Kontakt). Auf HW ist die **Sensorik**
  bewiesen (Fuß-Taster St.5 🟢; IMU-Sensing St.6 in Arbeit), das **Closed-Loop-Verhalten** aber
  ungetestet + sim-getunt → HW-Validierung + Retuning nötig (Gains, Schwellen).
