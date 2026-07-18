# Phase 4 — Video-Vollbild + UI-Shell — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_4_video_shell_plan.md`](phase_4_video_shell_plan.md) §3.
> **ROS-Seite implementiert + statisch verifiziert** (xacro-Parse + `colcon build`); die
> eingebetteten **Live-Assertions** (T4.1–T4.3: `topic hz` + Browser Desktop/Handy) und die
> **App-Shell** (P4.7–P4.9) + **End-to-End** (P4.11) sind **offen (User bzw. Android-Session)**.

```
Phase 4 (Video-Vollbild + UI-Shell):
- [x] P4.1 hexapod.camera.xacro (enable_camera, Body-vorne-oben, geradeaus, 16:9 ~720p@15) + tf-Frame
- [x] P4.2 Sim-Welt mit gz-sensors-system (ramp.sdf.xacro + empty_imu.sdf); Kamera rendert
- [x] P4.3 ros_gz-Bridge -> /camera/image_raw (+ camera_info); topic hz ok (T4.1)          [✅ Live: ~11 Hz, v1-Toleranz]
- [x] P4.4 web_video_server (:8080) serviert MJPEG; Desktop+Handy-Browser sehen das Bild (T4.2/T4.3)   [✅ Live: Desktop+Handy]
- [x] P4.5 Kamera+Bridge+web_video_server in den On-Demand-Sim-Stack eingehaengt (enable_camera:=true)
- [x] P4.6 Contract §5 festgezurrt (Protokoll/Port/URL/Topic/Aufloesung/on-off), Version-Bump  [v0.7 mit Plan; v0.8 = Host+Verfügbarkeit für App-Bau]
- [x] P4.7 [App] Fahr-Screen: Vollbild-Video (MJPEG, center-crop-fill) + Center-Toggle (Nichts/Kamera)  [✅ Android-Session]
- [x] P4.8 [App] Kamera-an/aus + Navigation Fahr-Screen <-> Lifecycle-Screen                 [✅ Android-Session]
- [x] P4.9 [App] alle Overlay-Slots positioniert (leer/Label) gemaess §5-Slot-Vertrag; Menue+Alerts-Buttons oeffnen leere Views  [✅ Android-Session]
- [x] P4.10 Self-Review + Doku (README, architecture-Nachzug, test_commands)
- [x] P4.11 [Integration, User+App] End-to-End: Handy sieht Gazebo-Video im Fahr-Screen (T4.4-T4.7)  [✅ User+App, end-to-end verifiziert]
```

## Stand — ROS-Seite implementiert + statisch verifiziert, Live-Pipeline + App offen

**Fertig + statisch verifiziert** (xacro-Parse grün für `enable_camera:=true/false` × `use_sim:=true/false`,
`ramp.sdf.xacro`-Expansion mit Sensors-System, `colcon build` grün):

- **`hexapod_description`:**
  - Neu `urdf/hexapod.camera.xacro` — `camera_link`/`camera_joint` (immer, tf-Frame; auf HW =
    Raspi-Cam-Naht), gz-Kamera-Sensor (`use_sim`-geguarded, Topic `/camera/sim`, 1280×720@15,
    `horizontal_fov` 1.089 rad ≈ 62°). Mount vorne oben am Body, geradeaus
    (`xyz = body_length/2, 0, body_height/2`, rpy 0 0 0).
  - `urdf/hexapod.urdf.xacro` — `enable_camera`-Arg (Default `true`) + conditional Include
    (analog `enable_imu`).
- **`hexapod_gazebo`:**
  - `worlds/ramp.sdf.xacro` + `worlds/empty_imu.sdf` — `gz-sim-sensors-system` (ogre2) ergänzt.
    **Kritisch:** der On-Demand-Sim-Stack lädt `ramp.sdf.xacro` (nicht die `sim.launch.py`-
    Default-Welt) — ohne dieses Plugin bliebe die Kamera stumm.
- **`hexapod_bringup`:**
  - Neu `config/bridge_camera.yaml` — gz `/camera/sim` → `sensor_msgs/Image` `/camera/image_raw`
    (+ `camera_info`).
  - `launch/sim.launch.py` — `enable_camera`-Arg (Default `true`, an den xacro-`Command`
    durchgereicht) + conditional `camera_bridge`-Node + conditional `web_video_server`-Node
    (:8080, `address` 0.0.0.0).

**Verifizierungs-Punkte (Plan §8) — Stand:**
- ✅ **Include-Kette selbst geprüft:** `bringup_ondemand mode:=sim` → `ramp_walk.launch.py`
  (`slope_deg:=0.0`) → `ramp.launch.py` → expandiert `ramp.sdf.xacro` (Tempfile) →
  `sim.launch.py world:=<tempfile>`. `ramp.launch.py` reicht **nur** `world/enable_imu/spawn_z/
  spawn_x` durch → `enable_camera` fällt korrekt auf den `sim.launch.py`-Default `true` zurück.
- ✅ **Install-Regeln:** beide Pakete nutzen `install(DIRECTORY …)` → neue `camera.xacro` +
  `bridge_camera.yaml` landen automatisch im `share`.
- ✅ **Body-Mount** aus `hexapod_physical_properties.xacro` abgeleitet (`body_length` 0.175 →
  cam_x 0.0875; `body_height` 0.043 → cam_z 0.0215).
- 🟡 **`web_video_server` NICHT installiert** → User: `sudo apt install -y ros-jazzy-web-video-server`
  (Build bricht nicht, aber der Node startet erst nach Install). Danach Param-Namen
  (`port`/`address`) via `ros2 param list /web_video_server` live gegenchecken.
- 🟡 **gz-`camera_info`-Topicname** (`/camera/sim/camera_info` angenommen) — beim ersten Live-Lauf
  mit `gz topic -l | grep camera` verifizieren. Für T4.1–T4.3 (MJPEG) **nicht** kritisch (nur das
  Image-Topic zählt); relevant für spätere Cam-Kalibrierung.
- 🟡 **`horizontal_fov` 1.089 rad (~62°)** — Default; nach dem ersten Live-Blick justierbar.

**✅ PHASE 4 KOMPLETT** — ROS-Seite + App-Shell (Android-Session) + End-to-End-Integration
(T4.4–T4.7) vom User verifiziert: Handy zeigt das Gazebo-Video vollflächig im Fahr-Screen,
Center-Toggle + Kamera-an/aus + Overlay-Slots + Navigation funktionieren. Nächste ROS-Arbeit =
**Phase 5** (Status-Publisher + Alerts + Set-Stance → füllt die in P4 positionierten leeren Slots).

### Live-Test-Befund (User) — Video-Pipeline verifiziert

- **T4.1 ✅ (~11.2–11.3 Hz):** `/camera/image_raw` published. Unter 15 Hz durch Rendering-Jitter
  des `gz-sim-sensors-system` unter Last (min 0.055s ≈ 18 Hz, max 0.466s Stall → kein sauberes
  RTF-Skalieren, sondern Scheduling-Jitter). **v1-Toleranz** (Plan §4.1: „~15 fps, justierbar");
  T4.7 flüssig bestätigt. Hebel bei Bedarf: Auflösung runter (z.B. 848×480). **Kein Config-Bug**
  (Sensor korrekt auf `update_rate` 15).
- **T4.1b ✅ beide Verify-Punkte bestanden:** `gz topic -l` listet `/camera/sim/camera_info`
  (exakt wie in `bridge_camera.yaml` angenommen → **keine Änderung nötig**). `ros2 param list
  /web_video_server` bestätigt `port` + `address`. (Zusätzliches `/camera/camera_info` = die
  gebridgte ROS-Seite, harmlos.)
- **T4.2 ✅ Desktop / T4.3 ✅ Handy:** Live-Gazebo-Bild sichtbar, ändert sich beim Gehen. Handy via
  Index-Seite (`http://<host>:8080` → Stream anklicken). Der **rohe** `…/stream?…&type=mjpeg`-
  Endpunkt (= App-URL) blieb einmal schwarz → test_commands T4.2 präzisiert (Index vs. roher
  Endpunkt; die App braucht den rohen). **Beim App-Bau (P4.7) gegenchecken.**
- **T4.7 ✅:** Latenz folgbar, läuft gut.
- **T4.11 ✅ Walking-Smoke:** Roboter lief mit aktiver Kamera normal vorwärts (Kamera bricht
  Spawn/tf/Walking nicht). `tf2_echo base_link camera_link` = translation **[0.087, 0.000, 0.021]**,
  Rotation identity — exakt der geplante Mount (`cam_x=body_length/2`, `cam_z=body_height/2`,
  geradeaus). URDF-Refactor-Vollprobe komplett ([[feedback_urdf_refactor_full_smoke]]).
  (Doku-Fix vorab: `joy_ws_test_client.py` scheiterte an „Connection refused :9090" — spricht
  **rosbridge**, das `ramp_walk.launch.py` nicht startet; test_commands auf direkten `/cmd_vel`-
  Publish korrigiert.)

## Self-Review (P4.10)

| # | Punkt | Status |
|---|---|---|
| 1 | Kamera-xacro spiegelt IMU-Muster 1:1 (`preserve/lumping` am Joint, Sensor am Link, `use_sim`-Guard) | OK |
| 2 | `camera_joint` hat `<child>` (im Plan-Snippet fehlte er — fixed-Joint braucht parent+child) | OK (ergänzt) |
| 3 | Sensors-System in die **wirklich geladene** Welt (`ramp.sdf.xacro`), nicht nur `empty_imu.sdf` | OK (Kette geprüft) |
| 4 | `enable_camera` erreicht die xacro auch im On-Demand-Pfad (Default-Fallback in `sim.launch.py`) | OK (Kette geprüft) |
| 5 | URDF-Refactor: xacro-Parse für alle 4 Arg-Kombis grün, `colcon build` grün | OK |
| 6 | URDF-Konsumenten nicht gebrochen: Sim-Spawn + Walking-Smoke ([[feedback_urdf_refactor_full_smoke]]) | OK — T4.11 Live grün (Roboter lief, `camera_link` tf [0.087, 0, 0.021]) |
| 7 | `camera_link` als tf-Frame auch auf HW (Raspi-Cam-Naht, Phase 7) | OK (immer erzeugt, Sensor use_sim-guarded) |
| 8 | Rendering-Dependency: Sensors-System braucht ogre2 (nur Desktop-Sim relevant; Pi baut kein gz) | OK (dokumentiert) |
| 9 | `web_video_server` bindet `0.0.0.0` → Handy erreicht es (Vorbedingung T4.3) | OK (Param gesetzt) — Live-Verify T4.3 |
| 10 | gz-`camera_info`-Topicname geraten | 🟡 vormerken (Live gegenchecken; für MJPEG unkritisch) |
| 11 | `web_video_server` Runtime-Dep nicht installiert | 🟡 vormerken (User: `apt install`, im test_commands prominent) |

Keine 🔴. Die 🟡 sind Live-Verifizierungs-Punkte (Plan §8) bzw. der geplante User-sudo-Schritt; die
🟢 ist der Pflicht-Live-Smoke (T4.11), dessen statische Gates (Parse/Build) grün sind.

## Design-Entscheidungen (mit Alternativen)

- **Sensors-System in `empty_imu.sdf` ergänzt (statt neue `empty_cam_imu.sdf`):** eine kanonische
  „empty"-Welt, minimale Fläche, Sensors-System ist ohne Kamera funktional inert. Verworfen: neue
  Welt + Default-Welt-Umverdrahtung in `sim.launch.py` (fragmentiert den Welt-Satz).
  Trade-off: die Default-Welt bekommt eine ogre2-Rendering-Abhängigkeit — auf dem Dev-Desktop
  (GPU+Display) unkritisch, der Pi baut kein Gazebo.
- **Kamera-Sensor läuft durchgehend (kein ROS-seitiges an/aus in Phase 4):** in Sim billig; die
  Contract-Naht `camera_enable` (Strom/Wärme am Pi) ist reserviert → Phase 7. „Kamera an/aus" ist
  Phase 4 rein app-seitig (Stream anfordern/stoppen). Verworfen: gz-Sensor pro Toggle laden/
  entladen (Overkill, in Sim kein Nutzen).
- **`bridge_camera.yaml` mappt zusätzlich `camera_info`** (obwohl für MJPEG nicht nötig): hält die
  Sim-Naht konsistent mit der späteren realen Cam (Kalibrierung/Intrinsics, Phase 7). Kostet nichts.
- **`web_video_server` im On-Demand-Stack (nicht always-on):** das Image-Topic existiert erst mit
  Gazebo. Verworfen: always-on (würde ins Leere serven, solange kein Stack läuft) — 1:1 die
  Plan-§1e-Entscheidung.
