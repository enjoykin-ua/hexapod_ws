# Stufe 0 — IMU-Plumbing & Visualisierung

> Stufe 0 von Block A5 ([Master](00_imu_balance_plan.md)). **Ziel:** `/imu/data`
> fließt in Sim (HW-Pfad nur skizziert), ist **sichtbar und getraut** — **noch
> keine Regelung**. Fundament + Beobachtbarkeit; entschärft alle Folge-Stufen.
> Plan-Doku nach CLAUDE.md §4. Test-Befehle: [`stage_0_imu_plumbing_test_commands.md`](stage_0_imu_plumbing_test_commands.md).
>
> **Verifiziert gegen den echten Code** (foot_contact.xacro, ros2_control.xacro,
> urdf.xacro, sim.launch.py, empty.sdf, gz Harmonic 8.11.0). Korrekturen aus der
> Verifikation sind unten markiert.

---

## 1. Logik-Skizze / Pseudocode

Sim-Pfad — spiegelt 1:1 die bestehende Fußkontakt-Pipeline
(`hexapod.foot_contact.xacro` → Bridge → Adapter-Node):

1. **`hexapod.imu.xacro`** (neu):
   - `imu_link` + `imu_joint` (`fixed`, an `base_link`). `rpy` aus der Montage-Cal
     (Default `0 0 0`; in Sim damit **REP-103/REP-145**-ausgerichtet, +X vorne /
     +Z oben). Position: mittig L/R, Z = base_link-Mitte (Höhe für die
     **Orientierung** egal). `imu_link` braucht eine **kleine Dummy-Inertia**
     (unlumpter Link).
   - ✅ **[verifiziert] preserve/lumping an den JOINT, Sensor an den LINK**
     (genau wie `foot_contact.xacro`):
     - `<gazebo reference="imu_joint"><preserveFixedJoint>true</preserveFixedJoint><disableFixedJointLumping>true</disableFixedJointLumping></gazebo>`
     - `<gazebo reference="imu_link"><sensor name="imu_sensor" type="imu">` mit
       `<topic>/imu/sim</topic>`, `<update_rate>` (50/100 Hz, §4), `always_on`,
       `<imu>`-Block (Orientierung **an**, optional Rauschen — Default leicht/aus, §4).
   - **Sim/HW-Trennung:** `imu_link`/`imu_joint` existieren **immer** (Frame auch
     auf HW für tf); der `<gazebo><sensor>`-Block in `<xacro:if value="${use_sim}">`
     (nur Sim, wie der gz_ros2_control-Plugin-Block). Auf HW liefert der
     `bno055`-Treiber `/imu/data`.
   - Include via neuem xacro-arg `enable_imu` (Default `true`) in
     `hexapod.urdf.xacro`, analog `enable_foot_contact` (`<xacro:if value="$(arg enable_imu)">`).
2. ✅ **[verifiziert — NEU/Pflicht] `worlds/empty_imu.sdf`** (in `hexapod_gazebo`):
   `empty.sdf` (Harmonic) enthält **kein `gz-sim-imu-system`** → ein IMU-Sensor
   bliebe **stumm**. Lösung: eigene Welt = Inhalt von `empty.sdf` **+**
   `<plugin filename="gz-sim-imu-system" name="gz::sim::systems::Imu"/>`.
   Als **Sim-Default-Welt** setzen (Superset: behält physics/contact/scene →
   Fußkontakt läuft weiter; ohne IMU-Sensoren ist das imu-system inert).
3. **`bridge_imu.yaml`** (neu, `hexapod_bringup/config/`): `gz.msgs.IMU` →
   `sensor_msgs/msg/Imu`, gz-Topic `/imu/sim` → ROS `/imu/data`, `GZ_TO_ROS`
   (Format 1:1 wie `bridge_foot_contact.yaml`).
4. **`sim.launch.py`**: `declare_enable_imu` + `enable_imu:=` an die xacro-`Command`
   durchreichen (neben `enable_foot_contact`) + `imu_bridge`-Node + `imu_monitor`-Node,
   beide `condition=IfCondition(LaunchConfiguration('enable_imu'))`; Default-`world`
   auf `empty_imu.sdf` (Pfad-Auflösung: PathJoinSubstitution auf
   `hexapod_gazebo/worlds/empty_imu.sdf` bzw. worlds-Dir auf `GZ_SIM_RESOURCE_PATH`,
   sonst findet gz die Welt nicht).
5. **`imu_monitor`-Node** (neu, in `hexapod_sensors`): abonniert `/imu/data`
   **mit Sensor-Daten-QoS (best_effort)** — sonst kommt vom Bridge-Publisher nichts
   an (analog latched-Topic-QoS-Stolperstein). Rechnet **roll/pitch** aus dem
   Quaternion + **Gyro-Betrag**. **Drei Ausgaben:** (a) Log throttled; (b) Topic
   `/imu/monitor` (`Vector3` roll/pitch/yaw) für echo/Plot/Bag; (c) **tf-Broadcast
   `world → base_link` aus roll/pitch (yaw=0, Translation fix)** → so **neigt sich das
   Roboter-MODELL in RViz** mit der gemessenen Lage (nur Orientierung, keine
   Translation; RViz-Fixed-Frame = `world`; zero-dependency, **gleich in Sim und HW**).
   Nimmt `use_sim_time` als Param (Risiko 5). **Reine Beobachtung, kein Regeln.**
   *Hinweis:* aktuell wird **kein** `world→base_link` gepublisht (nur `/clock`
   gebridged) → RViz zeigt heute die Körperneigung NICHT; (c) liefert sie.
6. **Orientierungs-Cal (Kipp-Test):** Körper in Gazebo definiert kippen → prüfen,
   welche `/imu/data`-Achse positiv wird → Sensor→base_link-Rotation bestätigen.
   In Sim per URDF schon ausgerichtet; **verankert die Methode** für die HW-Montage-Cal.

**HW-Pfad (nur skizziert, NICHT Teil von Stufe 0):** `bno055`-Treiber (I2C 0x28,
„IMU"-Fusionsmodus) publisht `/imu/data`. Treiber-Wahl = offener Punkt (Master §8).

---

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done wenn |
|---|---|---|
| **T0.1** | `/imu/data` existiert + Rate | gz-Sensor + **imu-system in der Welt** + Bridge laufen | `ros2 topic hz /imu/data` ≈ `update_rate` (kein Topic → Welt-Plugin/Bridge fehlt) |
| **T0.2** | roll/pitch reagieren | Sensor liefert plausible Orientierung | Körper in Gazebo kippen → roll/pitch **vorzeichenrichtig** |
| **T0.3** | Ground-Truth-Abgleich | IMU == Sim-Wahrheit | gekippt: `/imu/data`-roll/pitch ≈ Gazebo-Modell-Pose (±Tol.) |
| **T0.4** | Vibration mit aktiven Servos | fused Winkel stabil trotz Gangart | beim Laufen: roll/pitch-Ruhe-Drift klein, kein Wegdriften (Risiko 4) |
| **T0.5** | RViz-Viz | Lage sichtbar | RViz zeigt IMU-Orientierung (tf/Display) |
| **T0.6** | `enable_imu`-Toggle | sauber abschaltbar | `enable_imu:=false` → kein `/imu/data`, kein Node, kein Fehler |

> **URDF-Refactor → Full-Smoke (Pflicht, Memory `urdf_refactor_full_smoke`):** Stufe 0
> erweitert die URDF (`hexapod.imu.xacro` in `hexapod.urdf.xacro`) → xacro-Parse reicht
> **nicht**. Validieren mit **Sim + RViz + Walking-Smoke** (kein Regress; `gait_node`
> parst `/robot_description` live). T0.4 deckt Walking, T0.5 RViz.

**Bewusst NICHT getestet (scope-out):** Regelung/Leveling (Stufe 2), Kipp-Reaktion
(Stufe 1), HW-`bno055`-Treiber (HW-Stufe), Mag/Heading (nicht genutzt, D4),
Loop-Gains, Feintuning gz-Rauschen (grob hier, fein in Stufe 2).

---

## 3. Progress-Checkliste (→ [`imu_balance_progress.md`](imu_balance_progress.md))

```
- [ ] 0.1 hexapod.imu.xacro: imu_link+imu_joint (immer, Dummy-Inertia), gz-IMU-Sensor (use_sim-geguarded) - preserve/lumping am imu_joint, sensor am imu_link; include via enable_imu in hexapod.urdf.xacro
- [ ] 0.2 worlds/empty_imu.sdf (= empty.sdf + gz-sim-imu-system) als Sim-Default-Welt; ohne das Plugin bleibt /imu/data stumm
- [ ] 0.3 bridge_imu.yaml (gz.msgs.IMU -> sensor_msgs/Imu, /imu/sim -> /imu/data)
- [ ] 0.4 sim.launch.py: declare_enable_imu + enable_imu an xacro + imu_bridge + imu_monitor conditional; Default-world = empty_imu.sdf
- [ ] 0.5 imu_monitor-Node in hexapod_sensors (sensor-QoS best_effort, use_sim_time, roll/pitch/gyro, Log + Viz)
- [ ] 0.6 RViz zeigt Modell-Neigung (world->base_link-tf aus IMU roll/pitch)
- [ ] 0.7 T0.1-T0.6 grün (Sim) inkl. URDF-Full-Smoke (sim+rviz+walking); Ground-Truth-Abgleich dokumentiert
- [ ] 0.8 hexapod_sensors-README + Konzept-Doku (gz-IMU-Sensor, gz-sim-imu-system, ros_gz-Bridge, sensor_msgs/Imu+Covariance, Sensor-QoS, Quaternion->roll/pitch, REP-103/REP-145)
- [ ] 0.9 colcon test + Lint (ament_flake8/pep257) grün
- [ ] 0.10 kritische Self-Review-Tabelle
```

---

## 4. Entscheidungen + Offene Punkte

**Entschieden (User-Freigabe):**
- **IMU-Rate:** 100 Hz publishen, Regler tickt 50 Hz (100 Hz = BNO-055-Fusions-Decke;
  schneller bringt nichts, Aktuatorik limitiert auf ~50 Hz).
- **Default-Welt:** `empty_imu.sdf` wird neuer Sim-Default (Superset, vermeidet den
  „IMU-stumm"-Footgun).
- **`imu_monitor`-Output:** (a) Log throttled + (b) Topic `/imu/monitor` + (c) tf
  `world→base_link` aus roll/pitch (yaw=0) → **Roboter-Modell neigt sich in RViz**
  (Sim + HW gleich).
- **Node-Ort:** `hexapod_sensors`.

**Noch offen (in der Implementierung zu klären, kein Blocker):**
- **gz-Sensor-Rauschen:** erst leicht/aus, Feintuning in Stufe 2.
- **Ground-Truth-Mechanik (T0.3):** Modell-Pose via `gz topic` lesen oder Pose-Bridge?
  (Finalisierung nach Implementierung.)

---

## 5. Design-Entscheidungen (Stufe 0)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Sim-IMU-Quelle | gz-Sensor + ros_gz-Bridge → `/imu/data` | ros2_control-**SensorInterface** in Sim | gz-Sensor+Bridge direkt; SensorInterface = Overhead. Bleibt **HW-Option** (Master §8). |
| Welt | eigenes `empty_imu.sdf` (+ imu-system), als Default | `empty.sdf` lassen | empty.sdf hat **kein imu-system** → Sensor stumm (verifiziert). |
| Frame vs. Sensor | `imu_link` immer, `<sensor>` `use_sim`-geguarded | beides conditional / beides immer | Frame auch auf HW (tf) nötig; gz-Sensor nur Sim. |
| Adapter-Node | eigener `imu_monitor` | `foot_contact_publisher` erweitern | andere Verantwortung (Lage vs. Kontakt), eigene QoS/Rate. |
| roll/pitch-Quelle | aus `orientation`-Quaternion (Fusion) | Gyro selbst integrieren | Fusion driftfrei + schwerkraft-referenziert. |
| Paket | `hexapod_sensors` | neues Paket | gleiche Adapter-Rolle wie `foot_contact_publisher`. |
