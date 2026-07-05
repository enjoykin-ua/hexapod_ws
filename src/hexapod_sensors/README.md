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

### `bno055_imu` (Block A5 Stufe 6 / IP1) — **HW-Treiber**

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
  `publish_rate` (50 Hz), `axis_map_config` (0x24) / `axis_map_sign` (0x00) — BNO-
  Achsen-Remap; `roll_offset` / `pitch_offset` (rad, Montage-Restschräge, Default 0).
- **Reine Konvertierung** (`s16`/`parse_quat`/`parse_gyro`/`build_imu`) ist ROS-/I2C-frei
  und unit-getestet (`test/test_bno055_imu.py`) — läuft in CI am Dev **ohne** Sensor.
- **Robustheit:** I2C-`OSError` (Clock-Stretching) → Tick droppen + throttled WARN,
  kein Crash. Fehlender Sensor / kein smbus2 beim Start → sauberer FATAL-Log + Exit.
- **smbus2:** wird **lazy** (erst im Node) importiert → Dev-Tests brauchen es nicht.
  Bereitstellung am Pi: `stage_6_hw_imu_test_commands.md` (kein rosdep-Dep, Doku-only).

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
- **BNO-AXIS_MAP:** Achsen-Remap **im Chip** (Register `0x41/0x42`, nur im CONFIG-Modus
  schreibbar) richtet die Fusions-Ausgabe auf `base_link` (REP-103) aus — für orthogonale
  90°-Montage. **Verifikations-Risiko (IP1.7):** ob der Remap auch die *Quaternion* dreht
  (nicht nur Euler/Vektoren) ist per Kipp-Test zu bestätigen; Fallback = Node-Rotation.
- **Zero-Offset:** kleine Montage-Restschräge wird **upstream** im Node herausgedreht
  (feste Korrektur-Quaternion), weil der Konsument kein Offset/Zeroing hat. Default 0
  (Identität); der gemessene Wert kommt in IP2.
- **`enable_imu` default false auf HW** (≠ Sim always-on): Der Treiber öffnet echte
  Hardware und würde bei fehlendem Sensor jeden Servo-Bringup mit FATAL stören → bewusst
  opt-in. Der `imu_link` bleibt trotzdem immer im URDF (Toggle steuert nur die Nodes).

## Beispiel

```bash
# Sim (Dev):
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true
ros2 topic echo /imu/monitor
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"

# HW (Pi) — Details: project_finalization/imu_balance/stage_6_hw_imu_test_commands.md
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true
ros2 topic hz /imu/data      # ~50 Hz
ros2 topic echo /imu/calib   # [sys, gyr, acc, mag]
```
