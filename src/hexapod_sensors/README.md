# hexapod_sensors

Sensor-Adapter zwischen Sim-Sensor-Outputs (Gazebo) bzw. HW und den
ROS-Konventions-Topics. Reine Adapter/Beobachtungs-Knoten — **keine Regelung**.

## Knoten

### `foot_contact_publisher` (Phase 5 Stufe D)

Konvertiert die Gazebo-Contact-Sensoren in ein dauerhaftes Bool-Signal.

- **Subscribes:** 6× `/leg_<n>/foot_contact_raw` (`ros_gz_interfaces/Contacts`)
- **Publishes:** 6× `/leg_<n>/foot_contact` (`std_msgs/Bool`), timer-basiert
- **Parameter:** `publish_rate` (50 Hz), `contact_timeout` (0.1 s)

### `imu_monitor` (Block A5 Stufe 0)

Macht die IMU-Lage sichtbar/debugbar (`/imu/data` → roll/pitch).

- **Subscribes:** `/imu/data` (`sensor_msgs/Imu`, **Sensor-QoS = best_effort**)
- **Publishes:**
  - `/imu/monitor` (`geometry_msgs/Vector3`: x=roll, y=pitch, z=yaw, **Radiant**)
  - tf **`world → base_link`** aus roll/pitch (yaw=0) → Roboter-Modell **neigt sich
    in RViz** (Fixed Frame = `world`)
  - Log: roll/pitch/yaw in **Grad** (throttled)
- **Parameter:** `parent_frame` (`world`), `child_frame` (`base_link`),
  `viz_height` (0.15 m), `log_period_sec` (0.5)

### `bno055_imu` (Block A5 Stufe 6 / IP1+IP2) — **HW-Treiber**

Liest die **BNO-055** (Bosch 9-DOF, On-Chip-Fusion) am Pi über I2C (smbus2, NDOF)
und erzeugt **dasselbe `/imu/data`, das in der Sim die gz-IMU liefert**. Damit bleibt
die komplette Balance-Pipeline (gait_node/tip_monitor/balance_controller/imu_monitor)
auf HW unverändert.

- **Liest (I2C 0x28):** Quaternion (`QUA_DATA`, /16384) + Gyro (`GYR_DATA`, dps→rad/s)
  + Cal-Status (`CALIB_STAT`). **Kein Accel** — der Konsument nutzt `linear_acceleration`
  nicht (bleibt leer, Kovarianz `[0]=-1`).
- **Publishes:**
  - `/imu/data` (`sensor_msgs/Imu`, **best_effort**) — `orientation` + `angular_velocity`
  - `/imu/calib` (`std_msgs/UInt8MultiArray`: `[sys, gyr, acc, mag]`, je 0–3)
- **Parameter:** `i2c_bus` (1), `i2c_addr` (0x28), `frame_id` (`imu_link`),
  `publish_rate` (50 Hz), `axis_map_config` / `axis_map_sign` (BNO-Achsen-Remap),
  `roll_offset` / `pitch_offset` (rad, Montage-Restschräge). Die **kalibrierten Werte**
  liegen in [`config/imu_calibration.yaml`](config/imu_calibration.yaml) (IP2, HW-verifiziert):
  `axis_map_config=0x21`, `axis_map_sign=0x04`, `roll_offset=-0.0384`, `pitch_offset=0.0576`.
  Die Node-Defaults (`0x24`/`0x00`/`0`/`0`) = „keine Kalibrierung" und greifen nur **ohne**
  YAML — daher beim isolierten Start `--ros-args --params-file …/imu_calibration.yaml` nötig.
- **Reine Konvertierung** (`s16`/`parse_quat`/`parse_gyro`/`build_imu`) ist ROS-/I2C-frei
  und unit-getestet (`test/test_bno055_imu.py`) — läuft in CI am Dev **ohne** Sensor.
- **Robustheit:** I2C-`OSError` (Clock-Stretching) → Tick droppen + throttled WARN,
  kein Crash. Fehlender Sensor / kein smbus2 beim Start → sauberer FATAL-Log + Exit.
- **smbus2:** wird **lazy** (erst im Node) importiert → Dev-Tests brauchen es nicht.
  Bereitstellung am Pi: `stage_6_hw_imu_test_commands.md` (kein rosdep-Dep, Doku-only).

### `hexapod_camera` (`rpicam_node`, Block I Phase 7B) — **HW-Kamera**

Die echte **Raspberry-Pi-Kamera v1.3 (OV5647)** am Pi → ROS. Publisht die Frames als
**`sensor_msgs/CompressedImage`** (JPEG) auf **`/camera/image_raw/compressed`** — dieselbe
Topic-Basis, die in der Sim der Gazebo-Kamera-Sensor **roh** liefert. Der bestehende
`web_video_server` (:8080) streamt es; die App wählt den Stream-`type` je Host
(**Variante A**, Contract §5): Sim `type=mjpeg` (roh), **HW `type=ros_compressed`** (JPEGs
durchgereicht → **kein Pi-Decode**).

- **Quelle (Param `source`):**
  - `rpicam` (Default, **Pi**): `rpicam-vid --codec mjpeg -o -` als Subprozess; der MJPEG-
    Bytestrom wird in einzelne JPEGs (`FFD8…FFD9`) zerlegt + publiziert. (Byte-Stuffing `FF00` /
    Restart-Marker → `FFD9` tritt nur als echtes EOI auf → zuverlässiges Framing.)
  - `test` (**Desktop**): publisht `assets/test_pattern.jpg` in der `framerate`-Loop → die Kette
    Node→CompressedImage→web_video_server→Bild ist **ohne Pi** verifizierbar.
- **Publishes:** `/camera/image_raw/compressed` (`sensor_msgs/CompressedImage`, `format="jpeg"`,
  `frame_id="camera_link"`).
- **Parameter:** `source` (`rpicam|test`), `width`/`height` (1280×720), `framerate` (15),
  `frame_id` (`camera_link`), `test_image` (share/assets), **`camera_enable`** (bool) — startet/stoppt
  die Quelle **live** (rpicam-Subprozess bzw. test-Timer; Strom/Wärme).
- **Robustheit:** fehlt `rpicam-vid` (Dev/kein Userland) → einmal ERROR, `_proc=None`, **kein Crash**;
  Subprozess-Exit → Reader-Thread endet sauber; 4-MB-Sanity-Cap gegen korrupten Strom.
- **HW-Voraussetzung:** `rpicam-vid` = System-Binary (Pi-Fork `libcamera` + `rpicam-apps`, aus
  `~/camera_build/`) — Setup in
  [`project_finalization/peripherals_tests/camera_ov5647_v13.md`](../../project_finalization/peripherals_tests/camera_ov5647_v13.md).
  **Kein** rosdep-Dep (wie `smbus2`). `source:=test` (Desktop) braucht es nicht.
- **Launch:** `hexapod_bringup/launch/camera.launch.py` (Node + `web_video_server`); real via
  `bringup_ondemand mode:=real` (`source:=rpicam`). **Sim-Kamera bleibt** in `sim.launch.py`
  (gz-Bridge, roh).
- **Tests:** `test/test_rpicam_node.py` (JPEG-Framing inkl. Split, Publish-Kontrakt, source=test,
  camera_enable, Robustheit). Desktop-E2E: `phase_7b_camera_test_commands.md`.

## IMU-Pipeline (Sim)

```
gz-IMU-Sensor (hexapod.imu.xacro, /imu/sim)
  -> ros_gz_bridge (bridge_imu.yaml)
    -> /imu/data (sensor_msgs/Imu)
      -> imu_monitor -> /imu/monitor + tf world->base_link
```

**Welt:** Der gz-IMU-Sensor publisht nur, wenn die Welt das **`gz-sim-imu-system`**
lädt — `empty.sdf` hat es nicht, daher `empty_imu.sdf` (Default in `sim.launch.py`).

## IMU-Pipeline (HW)

```
BNO-055 (I2C 0x28, NDOF-Fusion)
  -> bno055_imu (smbus2, 50 Hz)
    -> /imu/data (sensor_msgs/Imu)   <- IDENTISCHE Naht wie Sim
      -> imu_monitor -> /imu/monitor + tf world->base_link
      -> gait_node/tip_monitor/balance_controller (UNVERÄNDERT)
```

**Toggle:** `real.launch.py enable_imu:=true` (Default **false** — opt-in, s.u.).

## Konzepte (ROS2/gz)

- **gz-Sensor + System-Plugin:** Ein `<sensor type="imu">` liefert nur Daten, wenn
  die Welt das zugehörige System-Plugin lädt (analog `gz-sim-contact-system` für die
  Fußsensoren). Deshalb `empty_imu.sdf` = `empty.sdf` + `gz-sim-imu-system`.
- **ros_gz_bridge:** mappt gz-Nachrichtentypen ↔ ROS-Typen (hier `gz.msgs.IMU` ↔
  `sensor_msgs/Imu`). Config = YAML-Liste aus `{ros_topic, gz_topic, ros_type,
  gz_type, direction}`.
- **`sensor_msgs/Imu`:** `orientation` (Quaternion) + `angular_velocity` +
  `linear_acceleration` (je mit Covarianz-Feldern).
- **Sensor-QoS (best_effort):** Sensor-Streams laufen typ. best_effort. Ein
  **best_effort-Subscriber ist mit reliable- UND best_effort-Publishern kompatibel**;
  ein reliable-Subscriber wäre es nur mit reliable-Pub. Daher `imu_monitor` =
  best_effort (`qos_profile_sensor_data`) — robust gegen die Bridge-QoS.
- **Quaternion → roll/pitch/yaw:** Die Orientierung ist singularitätsfrei als
  Quaternion. Euler-Winkel nur für menschenlesbare Anzeige/Schwellen.
- **REP-103 / REP-145:** +X vorne, +Y links, +Z oben (Körper); IMU-Frame-Konvention.
  `imu_link` mit `rpy 0 0 0` ist damit ausgerichtet; auf HW per Kipp-Test einmessen.
- **tf `world→base_link` für Modell-Neigung:** RViz zeigt die Körperlage nur, wenn ein
  Transform die `base_link`-Orientierung in einem festen Frame trägt. `imu_monitor`
  liefert das aus roll/pitch (yaw=0 → driftfrei ohne Magnetometer). **Nur Orientierung,
  keine Translation** (Odom out-of-scope).
- **Sim vs. HW:** Sim = gz-Sensor lokal am Dev-Rechner. HW = `bno055_imu`-Node am
  Pi → ROS2-DDS im LAN → Dev-RViz. **Beide erzeugen dasselbe `/imu/data`** → der
  Balance-Konsument ist quellen-agnostisch (dieselbe „eine Naht"-Idee wie bei den
  Fußkontakten).
- **BNO-055 NDOF-Modus:** On-Chip-Sensor-Fusion (Accel+Gyro+Mag) → fertige, driftarme
  `orientation`-Quaternion **im Chip** — kein Madgwick/EKF im ROS-Node nötig. Der Node
  ist damit ein dünner Register-Leser.
- **I2C-Clock-Stretching (BNO-Pi-Fallstrick):** Der BNO-055 hält SCL sporadisch → auf
  dem Pi via `i2c_arm_baudrate=50000` entschärft. Ein trotzdem auftretender `OSError`
  darf **nicht** crashen → Tick droppen. Echte Ausfälle fängt der `/imu/data`-Live-Guard
  im gait_node (Features aus statt Garbage).
- **BNO-AXIS_MAP (IP2 = `0x21`/`0x04`):** Achsen-Remap **im Chip** (Register `0x41`/`0x42`,
  nur im CONFIG-Modus schreibbar) richtet **alle** Fusions-Ausgaben (Quaternion **und** Gyro)
  auf `base_link` aus — für die orthogonale 90°-Einbaulage.
  - **`AXIS_MAP_CONFIG` (Permutation):** drei 2-Bit-Felder, je „welche Chip-Achse → Ausgabe-X/Y/Z"
    (`00=X, 01=Y, 10=Z`). `0x24` = Identität; **`0x21`** = X↔Y getauscht (Z bleibt) → korrigiert
    die 90°-Z-Einbauverdrehung dieses Sensors (im Kipp-Test: rechte Seite hoch → *roll* statt *pitch*).
  - **`AXIS_MAP_SIGN` (Vorzeichen):** drei Bits (Z Y X), `1=negativ`. Ein reiner X↔Y-Swap spiegelt
    das System (linkshändig) → genau **eine** Achse muss invertiert werden, damit es rechtshändig +
    richtig orientiert ist. Empirisch die 4 config-`0x21`-Placement-Signs durchgetestet: **`0x04`**
    (Z neg) gibt flach 0 + REP-103-Vorzeichen (rechte Seite hoch → roll neg, Nase hoch → pitch neg).
  - **Verifiziert (IP1.7/IP2.1):** der Remap dreht die **Quaternion** mit → die Node-Rotation-
    Contingency war **nicht** nötig; yaw-unabhängig (Chip-intern).
- **Zero-Offset (IP2, yaw-unabhängig):** die feine Montage-Restschräge (~4°, Sensor gegen `base_link`
  verkippt) wird im Node (`build_imu`) herausgedreht, weil der Konsument kein Zeroing hat.
  **Body- vs. World-Frame ist hier kritisch:** die Korrektur-Quaternion wird **rechts** komponiert
  (`q_pub = q_sensor ⊗ q_corr`), damit sie im **Roboter-Frame** wirkt und **yaw-unabhängig** ist.
  Eine Links-/World-Komposition wäre yaw-abhängig — bei realem mag-yaw verteilt sie die Korrektur
  falsch auf roll/pitch (IP2-Befund: pitch 3.3→6.5° bei yaw −112°). `roll_offset`/`pitch_offset` =
  die bei ebener Basis gemessenen Flach-Winkel (rad); Regressionstest
  `test_zero_offset_cancels_mounting_tilt_any_yaw` prüft 6 yaw. **Lehre:** Frame-/Rotations-
  Korrekturen immer mit `yaw≠0` unit-testen — der alte `yaw=0`-only-Test fing den Bug nicht.
- **`enable_imu` default false auf HW** (≠ Sim always-on): Der Treiber öffnet echte
  Hardware und würde bei fehlendem Sensor jeden Servo-Bringup mit FATAL stören → bewusst
  opt-in. Der `imu_link` bleibt trotzdem immer im URDF (Toggle steuert nur die Nodes).

## Beispiel

```bash
# Sim (Dev):
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true
ros2 topic echo /imu/monitor
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"

# HW (Pi) — isolierter IMU-Test, kein Servo-Strom/Relay. Details: stage_6_hw_imu_test_commands.md
ros2 run hexapod_sensors bno055_imu --ros-args \
  --params-file "$(ros2 pkg prefix hexapod_sensors)/share/hexapod_sensors/config/imu_calibration.yaml"
ros2 topic hz /imu/data      # ~50 Hz
ros2 topic echo /imu/calib   # [sys, gyr, acc, mag]
# voller HW-Bringup mit IMU (loopback_mode:=true = ohne Servo-Power/Relay):
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true enable_imu:=true
```
