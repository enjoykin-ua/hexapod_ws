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

## IMU-Pipeline (Sim)

```
gz-IMU-Sensor (hexapod.imu.xacro, /imu/sim)
  -> ros_gz_bridge (bridge_imu.yaml)
    -> /imu/data (sensor_msgs/Imu)
      -> imu_monitor -> /imu/monitor + tf world->base_link
```

**Welt:** Der gz-IMU-Sensor publisht nur, wenn die Welt das **`gz-sim-imu-system`**
lädt — `empty.sdf` hat es nicht, daher `empty_imu.sdf` (Default in `sim.launch.py`).

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
- **Sim vs. HW:** Sim = gz-Sensor lokal am Dev-Rechner. HW (später) = `bno055`-Node am
  Pi → ROS2-DDS im LAN → Dev-RViz (Cross-Machine-DDS aktuell deferiert).

## Beispiel

```bash
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true
ros2 topic echo /imu/monitor
rviz2 -d "$(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz"
```
