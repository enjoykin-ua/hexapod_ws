# Stufe 6 / IP1 — HW-IMU-Treiber (BNO-055 → `/imu/data`)

> Teil-Stufe von Block A5. **Ziel:** die in der Sim verifizierte IMU-Balance-Pipeline (Kipp-Erkennung
> St.1, Leveling St.2, Terrain-Following St.3) auf **echte Hardware** bringen — ein ROS2-Node am Pi
> liest die BNO-055 über I2C und publisht `sensor_msgs/Imu` auf `/imu/data`.
>
> **Status: 🟡 Plan — Freigabe offen.** Voraussetzung: IMU-Hello-World 🟢 (Sensor am Pi bewiesen,
> [`../peripherals_tests/imu_bno055.md`](../peripherals_tests/imu_bno055.md)).
>
> **Die Naht (macht alles einfach):** Der `gait_node` abonniert `/imu/data` (`sensor_msgs/Imu`,
> QoS best_effort) und zieht roll/pitch **direkt aus der Orientierungs-Quaternion**
> ([gait_node.py:1265-1277](../../src/hexapod_gait/hexapod_gait/gait_node.py#L1265-L1277) →
> `quat_to_roll_pitch`) + Gyro aus `angular_velocity.x/y`. In der Sim erzeugt der gz-IMU-Sensor +
> `ros_gz`-Bridge dieses Topic. **Auf HW erzeugen wir dasselbe `/imu/data` aus der BNO-055 → der
> gesamte Balance-Konsument (gait_node, tip_monitor, balance_controller, imu_monitor) bleibt
> UNVERÄNDERT.**

---

## 0. Kontext + Ist-Zustand

- **HW steht + ist bewiesen:** BNO-055 (Bosch 9-DOF, On-Chip-Fusion) fest **flach, mittig, in 90°-
  Schritten** im Roboter verschraubt, per **Qwiic/I2C am Pi** (`/dev/i2c-1`, Adresse `0x28`). Die
  Hello-World (`imu_bno055.md`) hat am Pi verifiziert: `i2cdetect` → `0x28`, `CHIP_ID = 0xA0`,
  NDOF-Fusion, Euler/Quaternion/Gyro plausibel beim Kippen, Cal steigt → 3. **smbus2** als I2C-Zugang
  (bewusst nicht Adafruit/Blinka — auf Pi 5/RP1 robuster).
- **Kein ROS-Treiber vorhanden:** `/imu/data` hat auf HW **keinen** Publisher — `real.launch.py`
  enthält null IMU; die gz-IMU ist rein Sim. → Das baut IP1.
- **Konsument (unverändert, nur Referenz):**
  - `gait_node._on_imu` — `msg.orientation` → `quat_to_roll_pitch` (roll/pitch), `angular_velocity.x/y`
    (Gyro roll/pitch). **`linear_acceleration` wird NICHT genutzt.** Kein tf, kein Offset, kein
    Startup-Zeroing.
  - `imu_monitor` ([hexapod_sensors](../../src/hexapod_sensors/hexapod_sensors/imu_monitor.py)) —
    `/imu/data` → `/imu/monitor` (Vector3 roll/pitch/yaw) + `world→base_link`-tf (RViz-Neigung).
  - QoS: `qos_profile_sensor_data` (best_effort) auf beiden Seiten.

## 1. Hardware / Verdrahtung (verbindlich, schon erledigt)

- BNO-055 per **Qwiic** (JST-SH 4-polig: GND/3V3/SDA/SCL) am Pi-I2C-Bus 1, Adresse **`0x28`**.
- **Montage:** flach, mittig, orthogonal (90°-Schritte) → **AXIS_MAP** deckt die Achsen-Ausrichtung ab
  (§5). I2C-Baudrate **50 kHz** (in `/boot/firmware/config.txt`, gegen BNO-Clock-Stretching) — bleibt.
- Nur der **Pi** erreicht den Sensor; der Dev-Rechner nicht → IP1-Sensor-Test läuft am Pi (§3, §Bringup).

## 2. Logik-Skizze / Pseudocode

### 2.1 Node-Struktur

Neuer Node **`bno055_imu`** im Paket **`hexapod_sensors`** (wo `imu_monitor` schon wohnt), Python +
**smbus2** (reuse der Hello-World-Register-Logik). Timer-getrieben.

```
Params (alle mit Default):
  i2c_bus=1, i2c_addr=0x28, frame_id='imu_link', publish_rate=50.0 (Hz)
  axis_map_config=0x24, axis_map_sign=0x00        # BNO Default P1 = Identität; IP2 setzt die Montage
  roll_offset=0.0, pitch_offset=0.0 (rad)         # Zero-Offset; IP2 misst, IP1 = 0
  frame 'imu_link' (existiert im URDF immer)

on_start():
  bus = SMBus(i2c_bus)
  assert read(CHIP_ID) == 0xA0                     # sonst FATAL + exit (falscher Sensor/Verkabelung)
  write(OPR_MODE, CONFIG); sleep 25ms
  write(UNIT_SEL, 0x00)                            # m/s^2, dps, Grad, Celsius (rad-Umrechnung im Node)
  write(PWR_MODE, NORMAL); write(SYS_TRIGGER, 0x00)
  write(AXIS_MAP_CONFIG, axis_map_config); write(AXIS_MAP_SIGN, axis_map_sign)   # VOR NDOF, in CONFIG
  write(OPR_MODE, NDOF); sleep 20ms
  log("BNO-055 NDOF aktiv, AXIS_MAP=0x.. sign=0x..")
  timer(1/publish_rate) -> tick()

tick():
  try:
    quat_raw = read_block(QUA_DATA, 8)             # W,X,Y,Z je int16 LE, /16384
    gyro_raw = read_block(GYR_DATA, 6)             # X,Y,Z je int16 LE, /16 -> dps
    calib    = read(CALIB_STAT)                    # sys/gyr/acc/mag je 2 bit
  except OSError:                                  # Clock-Stretching o.ä. -> Tick droppen
    warn_throttled("I2C read failed, skipping tick"); return
  imu = build_imu(quat_raw, gyro_raw, roll_offset, pitch_offset, frame_id, stamp=now)
  imu_pub.publish(imu)                             # /imu/data, best_effort
  publish_calib(calib)                             # /imu/calib (diagnostic), P1
```

### 2.2 Reine Konvertierung (unit-testbar, kein ROS/I2C)

```
parse_quat(bytes8) -> (x,y,z,w):                   # BNO-Reihenfolge W,X,Y,Z -> ROS x,y,z,w
  w = s16(b0,b1)/16384; x = s16(b2,b3)/16384
  y = s16(b4,b5)/16384; z = s16(b6,b7)/16384
  return (x,y,z,w)

parse_gyro(bytes6) -> (gx,gy,gz) in rad/s:         # dps/16 * pi/180
  return (s16(b0,b1)/16 * DEG2RAD, s16(b2,b3)/16 * DEG2RAD, s16(b4,b5)/16 * DEG2RAD)

build_imu(quat_raw, gyro_raw, roll0, pitch0, frame, stamp) -> sensor_msgs/Imu:
  (x,y,z,w) = parse_quat(quat_raw)
  # Zero-Offset: kleine Montage-Restschräge herausdrehen, sodass Basis-eben -> roll/pitch = 0.
  # Fixe Korrektur-Quaternion q_corr(roll=-roll0, pitch=-pitch0, yaw=0), vor die (schon AXIS_MAP-
  # ausgerichtete) Quaternion komponiert. roll0=pitch0=0 (IP1-Default) -> Identität, unveraendert.
  q_pub = compose(q_corr(-roll0,-pitch0,0), (x,y,z,w))
  imu.orientation = q_pub
  imu.angular_velocity = parse_gyro(gyro_raw)      # AXIS_MAP richtet die Gyro-Achsen mit aus
  imu.linear_acceleration = 0 ; imu.linear_acceleration_covariance[0] = -1   # nicht geliefert
  imu.orientation_covariance / angular_velocity_covariance = kleine Diagonale (Konsument ignoriert sie)
  imu.header.frame_id = frame; imu.header.stamp = stamp
  return imu
```

**Begründung je Design-Entscheidung:**
- **Nur Quaternion + Gyro lesen (kein Accel):** der Konsument nutzt nur `orientation` + `angular_velocity`.
  Spart I2C-Last + Latenz. `linear_acceleration` bleibt leer mit Cov `-1` (Konvention „nicht geliefert").
- **50 Hz @ 50 kHz:** Regler tickt 50 Hz; 14 Datenbytes/Tick sind bei 50 kHz vernachlässigbar (riesige
  Marge). 50 kHz bleibt aus der Hello-World (kein Re-Test des Clock-Stretchings).
- **AXIS_MAP im Chip (in CONFIG, vor NDOF):** richtet die Fusions-Ausgabe (Quaternion **und** Gyro) auf
  `base_link` aus. Orthogonale 90°-Montage → genau der AXIS_MAP-Anwendungsfall.
- **Zero-Offset als Quaternion-Komposition im Node (Default Identität):** der Konsument hat **kein**
  Offset/Zeroing (Code-verifiziert) → die Montage-Restschräge muss **upstream** raus. Kein Auto-Zero
  beim Boot (Roboter bootet aufgebockt, nicht flach) → gemessener Param (IP2).
- **`time`-Stamp + `imu_link`-Frame:** Node-Uhr (use_sim_time=false auf HW). `imu_link` existiert im
  URDF immer (Sim + HW).
- **Robustheit (Tick droppen bei OSError):** sporadisches Clock-Stretching darf nicht crashen und keine
  Garbage-Daten publishen. Sensor-Ausfall fängt der `/imu/data`-Live-Guard downstream ab (Features aus).

### 2.3 Integration

- Node ins Paket `hexapod_sensors`, Entry-Point in `setup.py`.
- **`real.launch.py`:** `bno055_imu` + `imu_monitor` im HW-Pfad starten, conditional auf `enable_imu`
  (der Arg existiert schon im URDF). `imu_monitor` gibt `/imu/monitor` + RViz-Neigung — praktisch für
  den Kipp-Test.
- **Dependency:** `smbus2` muss dem ROS-Python-Interpreter am Pi verfügbar sein (pip/rosdep) — Setup im
  Bringup-Doc (`stage_6_hw_imu_test_commands.md`).

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Ort |
|---|---|---|
| **Unit: parse_quat** | BNO-Reihenfolge W,X,Y,Z + /16384 → ROS (x,y,z,w) korrekt (bekannte Bytes) | pytest (Dev, kein HW) |
| **Unit: parse_gyro** | int16/16 · π/180 → rad/s, Vorzeichen | pytest |
| **Unit: build_imu Felder** | frame_id, `linear_acceleration_covariance[0]=-1`, Gyro→angular_velocity | pytest |
| **Unit: zero_offset=0 = Identität** | roll0=pitch0=0 → Quaternion unverändert publiziert | pytest |
| **Unit: zero_offset ≠ 0** | flache Quaternion + Offset → publizierte roll/pitch = 0 (Small-Angle) | pytest |
| **build/lint** | `colcon build/test hexapod_sensors` + flake8/pep257/copyright grün | Dev |
| **Pi: Node lebt + Rate** | `ros2 topic hz /imu/data` ≈ 50 Hz; `/imu/monitor` tickt | Live (Pi) |
| **Pi: Kipp-Test (Achsen + Vorzeichen)** | Roboter um roll-Achse kippen → `/imu/monitor` roll folgt (richtiges Vorzeichen), pitch ~0; ditto pitch. **Verifiziert, dass AXIS_MAP die Quaternion korrekt gedreht hat.** | Live (Pi), zum Dev gestreamt |
| **Pi: RViz-Neigung** | Modell neigt sich in RViz mit der echten Lage (imu_monitor-tf) | Live (Pi→Dev) |

**Bewusst NICHT (→ scope-out / spätere IP):**
- **AXIS_MAP-Werte + Zero-Offset bestimmen** → IP2 (`stage_6b`), der Kipp-Test hier zeigt nur, *dass*
  eine Ausrichtung nötig ist / stimmt.
- **Closed-Loop-Verhalten** (Leveling bewegt Beine, Gain-Retuning) → IP3 (`stage_6c`), braucht Power.
- **Magnetometer / Heading (yaw):** unbenutzt (mag-basiert, driftet, nahe Servos unbrauchbar).
- **Cal-Persistenz** über Power-Cycle: nicht nötig (Gyro/Accel re-cal in Sekunden).

## 4. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
IP1 (HW-IMU-Treiber):
- [ ] IP1.1 bno055_imu Node (smbus2, NDOF-Init, AXIS_MAP, 50 Hz Timer) in hexapod_sensors
- [ ] IP1.2 Reine Konvertierung (parse_quat/parse_gyro/build_imu inkl. zero-offset) als testbare Funktionen
- [ ] IP1.3 sensor_msgs/Imu auf /imu/data (best_effort) + /imu/calib (Cal-Status, P1) + I2C-Fehler-Robustheit
- [ ] IP1.4 Params (i2c_bus/addr, publish_rate, frame_id, axis_map_config/sign, roll/pitch_offset) + Entry-Point setup.py
- [ ] IP1.5 real.launch.py: bno055_imu + imu_monitor im HW-Pfad (enable_imu); smbus2-Dep dokumentiert
- [ ] IP1.6 Unit-Tests (parse/build/offset) + colcon test/lint grün (Dev, ohne HW)
- [ ] IP1.7 Deploy Dev→Pi (Bringup-Doc) + Pi-Verify: /imu/data ~50 Hz, Kipp-Test (Achsen/Vorzeichen), RViz-Neigung  ← HW, User
- [ ] IP1.8 kritische Self-Review-Tabelle
```

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| ROS-Treiber | **eigener smbus2-Node** | flynneva `bno055`; ros2_control-SensorInterface | reuse der bewiesenen Hello-World-Logik, null Fremd-Deps, Pi-5-robust, volle Kontrolle über die Message; Konsument braucht nur `/imu/data` |
| Was lesen | **Quaternion + Gyro** | +Accel | `linear_acceleration` code-verifiziert unbenutzt; spart I2C |
| Rate/Bus | **50 Hz @ 50 kHz** | 100 Hz / 100 kHz | Regler 50 Hz; 50 kHz aus Hello-World bewiesen, riesige Marge |
| Achsen-Ausrichtung | **AXIS_MAP im Chip (A)** | Node-Rotation (B); URDF-`imu_link`+tf (C) | orthogonale 90°-Montage → AXIS_MAP reicht; B nur bei krummer Montage nötig (dokumentiert, **nicht** implementiert); C fällt raus, weil der Konsument die Quaternion direkt liest (kein tf) |
| Zero-Referenz | **Node-Param, upstream abgezogen** | Auto-Zero beim Start; Konsument-Offset | Konsument hat kein Offset; Boot ist nicht flach (aufgebockt) → gemessener Param (IP2) statt Auto-Zero; upstream hält Konsument unverändert |
| Cal-Handling | **sofort publishen + /imu/calib (P1)** | ab Cal-Schwelle gaten (P2) | roll/pitch (accel-basiert) sofort brauchbar; Gaten riskiert Nie-Start bei Stillstand |
| Robustheit | **Tick droppen bei OSError, throttled Log** | Retry-Loop / Crash | Clock-Stretching ist sporadisch; Live-Guard downstream deckt echte Ausfälle |

## 6. Offene Punkte für User-Review

1. **AXIS_MAP ↔ Quaternion (Verifikations-Risiko):** der BNO-055-Achsen-Remap sollte laut Datenblatt
   **alle** Fusions-Ausgaben inkl. Quaternion drehen — es gibt aber Firmware-Berichte, dass nur
   Euler/Vektoren betroffen sind. **Der Pi-Kipp-Test (IP1.7) ist genau der Nachweis.** Falls die
   Quaternion **nicht** mitgedreht wird → Contingency: Node-Rotation (B) doch aktivieren (kleine, exakte
   90°-Quaternion-Komposition). Als Risiko markiert, Fallback designt.
2. **smbus2-Dep am Pi:** wie stellen wir `smbus2` dem ROS-Python bereit (pip system-wide auf Ubuntu 24.04
   ggf. `--break-system-packages`, oder rosdep, oder vendored)? Detail im Bringup-Doc.
3. **`/imu/calib`-Format:** eigenes kleines Topic (z. B. `std_msgs/UInt8MultiArray` sys/gyr/acc/mag) oder
   `diagnostic_msgs`? Vorschlag: schlichtes UInt8-Array + Startup-Log.
4. **imu_monitor `viz_height`/Frames auf HW:** `world→base_link` mit fixem `viz_height` — auf HW ok als
   reine Neigungs-Viz (kein echtes world-Frame). Bestätigen.

## 7. Handoff / Code-Anker

- **Reuse:** `~/peripheries/bno055_hello.py` + `bno055_full.py` (Register-Map, smbus2, Init-Sequenz) aus
  [`../peripherals_tests/imu_bno055.md`](../peripherals_tests/imu_bno055.md).
- **Neu:** `hexapod_sensors/hexapod_sensors/bno055_imu.py` + `test/test_bno055_imu.py`; `setup.py`
  Entry-Point; `hexapod_sensors/package.xml` (smbus2-Dep).
- **Ändern:** `hexapod_bringup/launch/real.launch.py` (bno055_imu + imu_monitor, `enable_imu`).
- **Konsument unverändert:** `gait_node.py:1265-1277`, `tip_monitor.py:28`,
  `imu_monitor.py`, `balance_controller.py`.
- **BNO-Register:** `AXIS_MAP_CONFIG=0x41`, `AXIS_MAP_SIGN=0x42`, `QUA_DATA=0x20` (8B, /16384),
  `GYR_DATA=0x14` (6B, /16→dps), `CALIB_STAT=0x35`, `OPR_MODE=0x3D`, NDOF=0x0C.
