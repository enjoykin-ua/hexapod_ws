# Phase 4 — Video-Vollbild + UI-Shell — §4-Plan

> **Ziel:** eine **Video-Pipeline** (Gazebo-Kamera → Stream-Server → App) und die **Fahr-Screen-
> Shell** (Vollbild-Video-Hintergrund + Center-View-Toggle + positionierte, **leere** Overlay-
> Slots + Navigation). Phase 4 baut das **Gerüst**; die Slot-**Inhalte** (Status/Dropdowns/3D-
> Viz/Config/Alerts) sind **Phase 5**, der E-Stop **Phase 6**.
>
> **Seite:** ROS (Video-Pipeline) + App (Shell). **Status: 🟡 Plan.** Mit dem User im Detail
> durchgesprochen. Master: [`00_overview.md`](00_overview.md) · Contract: [`interface_contract.md`](interface_contract.md).

---

## 0. Ziel + Abgrenzung

**ROS-Seite:** Gazebo-Kamera-Sensor am Roboter + ros_gz-Bridge → `sensor_msgs/Image` +
`web_video_server` (MJPEG/HTTP :8080). Contract §5 festzurren.

**App-Seite:** eigener **Fahr-Screen** (Querformat) mit Vollbild-Video (MJPEG), **Center-View-
Toggle (Nichts=Default / Kamera / [3D→P5])**, Kamera-an/aus, Verbindungs-Status, und **alle
übrigen Overlay-Slots als leere, positionierte Platzhalter** (Vertrag für Phase 5).

**Sim→Real:** In der Sim ist die Bildquelle die **Gazebo-Kamera**; auf dem Pi später die echte
**Raspi-Cam v1.3** → **gleiches `/camera/image_raw`-Topic**, Stream-Server + App **unverändert**.

**Bewusst NICHT in Phase 4:**
- **Overlay-Inhalte** (safety/tip/state/stance/gait/tempo/foot/battery) — Phase 5 (brauchen den
  Status-Publisher). Nur die **leeren Slots** werden positioniert.
- **Selektierbare Dropdowns** (gait/tempo/stance), **3D-Roboter-Viz**, **Config-Panel-Inhalt**,
  **Alerts-View-Impl** — Phase 5.
- **E-Stop scharf** — Phase 6 (nur reservierte Position).
- **RTSP/H.264/WebRTC** — späteres Latenz-Upgrade (NF4).
- **Echte Raspi-Cam** — Pi/Phase 7. Phase 4 = Gazebo-Kamera.
- **Batterie**, **Snapshot** — vom User gestrichen.

---

## 1. Logik-Skizze / Vorgehen (ROS-Seite)

### 1a. Gazebo-Kamera-Sensor
- Neuer **`hexapod.camera.xacro`** (conditional `enable_camera`, Muster wie `enable_imu`/
  `enable_foot_contact`): ein `camera_link` **vorne oben auf dem Body, geradeaus** (wie am echten
  Hexapod) + gz-Kamera-Sensor. **16:9, ~1280×720 @ ~15 fps** (final justierbar).
- Kamera-Frame in den tf-Baum (für spätere Konsistenz mit der realen Cam).

### 1b. Sim-Welt: Kamera-System
- Die gz-Kamera rendert nur, wenn die Welt das **`gz-sim-sensors-system`** lädt (analog zum
  IMU-System in `empty_imu.sdf`). → **`empty_cam_imu.sdf`** (empty + IMU-System + Sensors-System)
  bzw. Sensors-System in die bestehende Welt ziehen.

### 1c. ros_gz-Bridge
- gz-Kamera-Image → **`/camera/image_raw`** (`sensor_msgs/Image`) (+ `camera_info`). Bridge-
  Config in `hexapod_bringup/config/` (Muster wie `bridge_imu.yaml`).

### 1d. Stream-Server
- **`web_video_server`** (`ros-jazzy-web-video-server`, Stock-Paket) auf **Port 8080**. Serviert
  jedes Image-Topic als MJPEG:
  `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg`.

### 1e. Einhängen in den Bringup
- Kamera-Sensor (URDF) + Bridge + `web_video_server` laufen mit dem **On-Demand-Sim-Stack**
  (`bringup_ondemand mode:=sim` → über `sim.launch.py`/`ramp_walk`), da das Bild erst existiert,
  wenn Gazebo läuft. `enable_camera:=true` als Default im Sim-Pfad.
- **Design-Entscheidung:** `web_video_server` in den On-Demand-Stack (nicht always-on), weil das
  Image-Topic an den schweren Stack gekoppelt ist. (Alternative always-on verworfen: würde ins
  Leere serven, solange kein Stack läuft.)

### 1f. Kamera an/aus
- **Phase 4 = app-seitig** (App fordert den Stream an / stoppt ihn). Der Gazebo-Sensor läuft
  durchgehend (in Sim billig). Die **Contract-Naht `camera_enable`** (ROS-Node-Start/Stop für
  Strom/Wärme) ist **reserviert**, echte Impl = **Pi/Phase 7**.

**Verworfene Alternativen:** WebRTC/RTSP für v1 (Overkill/Aufwand — MJPEG-Erstwurf, Upgrade
später); Video über rosbridge (base64, [D2] — grauenhaft).

---

## 2. Tests-Liste (mit Begründung) + was NICHT

| Test | Prüft | Warum |
|---|---|---|
| **T4.1** `/camera/image_raw` published (`ros2 topic hz`, ~15 Hz) | Gazebo-Cam + Bridge | Quelle steht |
| **T4.2** `web_video_server` liefert MJPEG (Browser Desktop: `http://localhost:8080/stream?topic=/camera/image_raw`) | Stream-Server | Pipeline ROS-seitig |
| **T4.3** vom **Handy-Browser** `http://<Desktop-IP>:8080/stream?...` → Gazebo-Bild sichtbar | Netz-Erreichbarkeit | Vorbedingung App |
| **T4.4** App-Fahr-Screen zeigt das Video **vollflächig** (center-crop, keine Balken) | App-Video-View | Kern-Deliverable |
| **T4.5** Center-Toggle **Nichts↔Kamera**, Kamera-an/aus | Shell-Interaktion | UX-Gerüst |
| **T4.6** alle Overlay-Slots **positioniert** (leer/Label), Navigation Fahr-Screen ↔ Lifecycle | Shell-Layout | Vertrag für Phase 5 |
| **T4.7** Latenz qualitativ „folgbar" (NF4, ~100–300 ms) | Erstwurf-Tauglichkeit | reicht für v1 |

**Bewusst offen / später:** echte Raspi-Cam (Pi); Overlay-Inhalte/Dropdowns/3D-Viz (P5);
Config-Panel/Alerts-Impl (P5); E-Stop scharf (P6); harte Latenzzahl + RTSP/WebRTC (Upgrade).

---

## 3. Progress-Checkliste (→ `phase_4_..._progress.md`, Done-Vertrag)

```
Phase 4 (Video-Vollbild + UI-Shell):
- [ ] P4.1 hexapod.camera.xacro (enable_camera, Body-vorne-oben, geradeaus, 16:9 ~720p@15) + tf-Frame
- [ ] P4.2 Sim-Welt mit gz-sensors-system (empty_cam_imu.sdf); Kamera rendert
- [ ] P4.3 ros_gz-Bridge -> /camera/image_raw (+ camera_info); topic hz ok (T4.1)
- [ ] P4.4 web_video_server (:8080) serviert MJPEG; Desktop+Handy-Browser sehen das Bild (T4.2/T4.3)
- [ ] P4.5 Kamera+Bridge+web_video_server in den On-Demand-Sim-Stack eingehaengt (enable_camera:=true)
- [ ] P4.6 Contract §5 festgezurrt (Protokoll/Port/URL/Topic/Aufloesung/on-off), Version-Bump
- [ ] P4.7 [App] Fahr-Screen: Vollbild-Video (MJPEG, center-crop-fill) + Center-Toggle (Nichts/Kamera)
- [ ] P4.8 [App] Kamera-an/aus + Navigation Fahr-Screen <-> Lifecycle-Screen
- [ ] P4.9 [App] alle Overlay-Slots positioniert (leer/Label) gemaess §5-Slot-Vertrag; Menue+Alerts-Buttons oeffnen leere Views
- [ ] P4.10 Self-Review + Doku (README, architecture-Nachzug, test_commands)
- [ ] P4.11 [Integration, User+App] End-to-End: Handy sieht Gazebo-Video im Fahr-Screen (T4.4-T4.7)
```

---

## 4. Offene Punkte / Risiken

1. **Auflösung/FPS final:** Vorschlag 1280×720@15 (16:9). In Sim frei wählbar; für die reale
   Cam später am Pi angleichen. Justierbar nach dem ersten Live-Blick.
2. **Aspect 16:9 → Phone 19.5:9:** App **center-crop-to-fill** (kein Balken, minimaler Beschnitt);
   späterer In-App-Zoom optional.
3. **web_video_server-Last:** MJPEG ist bandbreitenhungrig; für den Sim-Test am Router unkritisch.
   Am Pi/Hotspot später beobachten (ggf. Auflösung/FPS/RTSP).
4. **Port 8080** frei (nicht 9090) — bei Kollision umkonfigurierbar.

---

## 5. App-Seiten-Brief (self-contained) — die Shell + der Slot-Vertrag für Phase 5

**Aufgabe Phase 4:** Fahr-Screen-**Shell** + Video. Interface = `interface_contract.md §5`.

- **Fahr-Screen (eigener Screen, Querformat-locked):** vom Lifecycle-Screen (Phase 3) per Button
  „Fahren" hinein, per Geste/Back zurück. Der Kishi fährt weiter über `/joy` (Phase 2).
- **Center-View (3-Wege-Toggle, Default = Nichts):**
  - **Nichts** (Default): dunkler Hintergrund, nur Overlay.
  - **Kamera**: Vollbild-MJPEG von `http://<host>:8080/stream?topic=/camera/image_raw&type=mjpeg`
    (Host wie §0), **center-crop-to-fill** (keine schwarzen Balken).
  - **3D-Roboter-Viz**: **reserviert → Phase 5**.
- **Kamera an/aus:** app-seitig (Stream anfordern/stoppen).
- **Overlay-Slots — positioniert + leer/Label (Vertrag für Phase 5), Layout:**

```
┌───────────────────────────────────────────────────────────┐
│ [conn ●]BUILT [safety]  [tip]           [⚠ alerts][⚙][show]│  Top-Leiste
│                                                             │
│              CENTER-VIEW (Nichts / Kamera / 3D)             │
│                                                             │
│ 1 4   [state][stance][gait][tempo]              [⛔ E-STOP] │  Bottom-Leiste
│ 2 5                                             [📷 cam]    │
│ 3 6   (foot-Raster, grün=Kontakt)                          │
└───────────────────────────────────────────────────────────┘
```

  | Slot | Phase-5-Inhalt/Interaktion | in P4 |
  |---|---|---|
  | `conn` | Verbindung rosbridge/Stack (App-intern) | **BUILT** (Anzeige) |
  | `safety` | Freeze/Safety-State (Status-Publisher) | leer |
  | `tip` | Kipp-/Tip-Warnung (`/imu/monitor`) | leer |
  | `state` | Walking/Standing/Sitting/SAT (Anzeige) | leer |
  | `stance` | tief/mittel/hoch — **Anzeige + Dropdown** (standing-only; synchron zu L2/R2 via Status) | leer |
  | `gait` | Gangart — **Dropdown ↑** (standing-only) | leer |
  | `tempo` | Tempo — **Dropdown ↑** (nur aktuell gültige Presets) | leer |
  | `foot 1–6` | 2×3-Raster `1 4 / 2 5 / 3 6`, **Zahl grün = Bein am Boden** (`/foot_contacts`) | leer |
  | `⚙ config` | **rqt-artiges Param-Panel** (Slider/Toggles → rosbridge-Param-Calls) | **BUILT*** Button → leeres Panel |
  | `⚠ alerts` | **Fehler-/Warn-Liste** (aus `/hexapod/alerts`) + **„Alles kopieren"** → Zwischenablage | **BUILT*** Button → leere View |
  | `show` | Show-Pose-Auswahl-Menü (keine/Show-X) | **BUILT*** Button → leeres Menü |
  | `📷 cam` | Kamera an/aus | **BUILT** Toggle |
  | `⛔ E-STOP` | Not-Halt `/hexapod_safety_freeze` | leer (Position reserviert, → P6) |

- **Bewusst noch NICHT:** Live-Daten, Dropdown-Logik, 3D-Viz, Config-/Alerts-/Show-Inhalte —
  Phase 5/6. Phase 4 = **positionierte leere Slots + funktionierendes Video + Navigation**.

**Integration (User):** Sim-Stack starten (Phase 3), App → Fahr-Screen → Kamera-View → Handy
zeigt das Gazebo-Bild vollflächig.

---

## 6. Contract-Touchpoints (→ festzurren)
- **§5 Video** komplett pinnen: MJPEG/`web_video_server`, Port 8080, `/camera/image_raw`,
  URL-Schema, 16:9 ~720p@15, center-crop, `camera_enable` reserviert (Pi). Version-Bump.
- **§6** ergänzen: `/hexapod/alerts` (WARN+ aus `/rosout` republished) `[TBD-Phase 5]`;
  Status-Publisher (state/stance/gait/tempo/safety) `[TBD-Phase 5]`; Set-Stance-direkt `[TBD-Phase 5]`.

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_4_..._progress.md` + `phase_4_..._test_commands.md` (Kontext-Tags).
- `hexapod_bringup`/`hexapod_gazebo` README: Kamera + web_video_server.
- `architecture.md` (+ `ai_navigation.md`): Kamera-Topic + Stream-Server + Video-Kanal.
- Contract v-Bump; App-`CLAUDE.md`-Zeile „Aktuell: Phase 4".

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

> Kalt umsetzbar ohne Gesprächskontext. Alle Muster spiegeln die **IMU-Pipeline** (A5 Stufe 0):
> die Kamera ist strukturell 1:1 analog. Referenz-Dateien zum Nachlesen sind je Schritt genannt.

### Schritt 1 — Kamera-xacro (`hexapod_description/urdf/hexapod.camera.xacro`)
**Muster:** `hexapod_description/urdf/hexapod.imu.xacro` (identische Struktur). Neu anlegen:
```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <!-- Kamera (Block I Phase 4). Muster: hexapod.imu.xacro.
       camera_link vorne oben am Body, geradeaus (wie am echten Hexapod).
       gz-Sensor nur im Sim-Pfad (use_sim); auf HW liefert die Raspi-Cam
       /camera/image_raw direkt (Phase 7). -->
  <link name="camera_link">
    <xacro:box_inertia mass="0.01" x="0.02" y="0.02" z="0.02"/>
  </link>
  <joint name="camera_joint" type="fixed">
    <parent link="base_link"/>
    <!-- xyz aus den Body-Maßen ableiten (hexapod_physical_properties.xacro):
         x = vordere Body-Kante, z = Body-Oberkante. rpy 0 0 0 = geradeaus. -->
    <origin xyz="${cam_x} 0 ${cam_z}" rpy="0 0 0"/>
  </joint>
  <xacro:if value="$(arg use_sim)">
    <gazebo reference="camera_joint">
      <preserveFixedJoint>true</preserveFixedJoint>
      <disableFixedJointLumping>true</disableFixedJointLumping>
    </gazebo>
    <gazebo reference="camera_link">
      <sensor name="camera_sensor" type="camera">
        <always_on>1</always_on>
        <update_rate>15</update_rate>
        <visualize>false</visualize>
        <topic>/camera/sim</topic>
        <camera>
          <horizontal_fov>1.089</horizontal_fov>   <!-- ~62° -->
          <image><width>1280</width><height>720</height><format>R8G8B8</format></image>
          <clip><near>0.05</near><far>50</far></clip>
        </camera>
      </sensor>
    </gazebo>
  </xacro:if>
</robot>
```
⚠️ `cam_x`/`cam_z` an echte Body-Maße anpassen (aus `hexapod_physical_properties.xacro`);
`box_inertia`-Makro existiert bereits (nutzt die IMU auch). Kamera-Frame folgt REP-103.

### Schritt 2 — Toggle + Include in `hexapod.urdf.xacro`
**Muster:** die `enable_imu`-Zeilen (arg + conditional include). Ergänzen:
```xml
<xacro:arg name="enable_camera" default="true"/>
...
<xacro:if value="$(arg enable_camera)">
  <xacro:include filename="hexapod.camera.xacro"/>
</xacro:if>
```
(analog zu `enable_imu` / `hexapod.imu.xacro`, aktuell Z. ~152–154).

### Schritt 3 — Sensors-System in die Welt(en), die der On-Demand-Stack WIRKLICH lädt
⚠️ **Kette geprüft (kritisch!):** `bringup_ondemand mode:=sim → ramp_walk → ramp.launch.py` —
und **`ramp.launch.py` überschreibt die Welt** mit der zur Laufzeit expandierten
`hexapod_gazebo/worlds/ramp.sdf.xacro` (slope_deg=0), die es als `world:=<tempfile>` an
`sim.launch.py` gibt. **Die Default-Welt in `sim.launch.py` greift im On-Demand-Pfad NICHT.**
`ramp.sdf.xacro` lädt `gz-sim-imu-system` + `gz-sim-contact-system`, aber **NICHT** das
Sensors-System → die Kamera bliebe stumm.

**Fix — in `hexapod_gazebo/worlds/ramp.sdf.xacro`** (die tatsächlich geladene Welt) den
Sensors-System-Plugin ergänzen (neben den vorhandenen imu-/contact-Plugins):
```xml
<plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors">
  <render_engine>ogre2</render_engine>
</plugin>
```
Für den **direkten** `sim.launch.py`-Aufruf (ohne ramp) dasselbe in `empty_imu.sdf` (bzw. eine
`empty_cam_imu.sdf`). **Generell: jede Welt, die mit Kamera gefahren wird, braucht das
Sensors-System** (auch `step/trench/rubicon/slope.sdf.xacro`, falls dort später gefahren wird).
imu- + contact-system bleiben unverändert.

### Schritt 4 — Bridge-Config (`hexapod_bringup/config/bridge_camera.yaml`)
**Muster:** `bridge_imu.yaml`. Neu:
```yaml
- ros_topic_name: /camera/image_raw
  gz_topic_name: /camera/sim
  ros_type_name: sensor_msgs/msg/Image
  gz_type_name: gz.msgs.Image
  direction: GZ_TO_ROS
- ros_topic_name: /camera/camera_info
  gz_topic_name: /camera/sim/camera_info   # ⚠️ echten gz-camera_info-Topicnamen verifizieren
  ros_type_name: sensor_msgs/msg/CameraInfo
  gz_type_name: gz.msgs.CameraInfo
  direction: GZ_TO_ROS
```

### Schritt 5 — Wiring in `hexapod_bringup/launch/sim.launch.py`
**Muster:** die `enable_imu` + `imu_bridge`-Behandlung (dort schon vorhanden). `sim.launch.py`
**läuft in der Ramp-Kette** (`ramp.launch.py` inkludiert es) → die Nodes hier greifen auch im
On-Demand-Pfad. Ergänzen:
1. `declare_enable_camera` (default `'true'`).
2. `enable_camera` an den xacro-`Command` durchreichen: `' enable_camera:=', LaunchConfiguration('enable_camera')`.
3. **camera_bridge**-Node (conditional `IfCondition(enable_camera)`), Muster = `imu_bridge` mit `bridge_camera.yaml`.
4. **web_video_server**-Node (conditional `enable_camera`):
> ⚠️ **KEINE** Default-Welt-Änderung in `sim.launch.py` — die greift im On-Demand-Pfad nicht
> (ramp überschreibt die Welt). Das Sensors-System kommt aus der **Welt-Datei** (Schritt 3).
```python
Node(package='web_video_server', executable='web_video_server',
     name='web_video_server', output='screen',
     parameters=[{'port': 8080, 'address': '0.0.0.0'}],
     condition=IfCondition(LaunchConfiguration('enable_camera')))
```
> `sim.launch.py` wird über `ramp_walk`→`bringup_ondemand mode:=sim` (Phase 3) gestartet — die
> Kamera kommt also automatisch mit dem On-Demand-Sim-Stack hoch. `real.launch.py` braucht nichts
> (auf HW ist `use_sim=false` → gz-Sensor aus; `camera_link` bleibt als tf-Frame; echte Cam = Phase 7).

### Schritt 6 — Installation + Build + Test
```bash
sudo apt install -y ros-jazzy-web-video-server        # User führt aus
cd ~/hexapod_ws && colcon build --packages-select hexapod_description hexapod_gazebo hexapod_bringup
source install/setup.bash
# Sim starten (über den Phase-3-Stack oder direkt sim.launch.py) und:
ros2 topic hz /camera/image_raw                        # T4.1: ~15 Hz
# Browser Desktop:  http://localhost:8080/stream?topic=/camera/image_raw&type=mjpeg   (T4.2)
# Browser Handy:    http://<Desktop-IP>:8080/stream?topic=/camera/image_raw&type=mjpeg (T4.3)
```

### Verifizierungs-Punkte (bei Impl prüfen, nicht raten)
- **gz-`camera_info`-Topicname** (Schritt 4) — mit `gz topic -l` bzw. `ros2 topic list` gegenchecken.
- **Body-Mount-Koordinaten** `cam_x`/`cam_z` (Schritt 1) — aus `hexapod_physical_properties.xacro`.
- **web_video_server-Param-Namen** (`port`/`address`) — mit `ros2 param list /web_video_server` prüfen.
- **`horizontal_fov`** — 1.089 rad (~62°) ist ein sinnvoller Default; nach dem ersten Live-Blick justieren.
- **URDF-Konsumenten nicht brechen** ([[feedback_urdf_refactor_full_smoke]]): nach dem xacro-Umbau
  `xacro`-Parse + Sim-Spawn + Walking-Smoke, nicht nur Build.

### App-Seite
Siehe §5 (Shell + Slot-Vertrag). Video-URL = Schritt 6. Kein ROS-Wissen nötig außer §5/§0.

