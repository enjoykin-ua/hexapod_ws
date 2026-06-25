# A5 IMU-Balance — Progress

> **Done-Vertrag** (CLAUDE.md §4). Die Bullets sind 1:1 aus den Stufen-Plänen.
> **Alle `[x]` einer Stufe = Stufe fertig**, keine retroaktive Anpassung. Pro
> erledigtem Bullet sofort `[ ]`→`[x]` (nicht batchen). Post-Review-Tabelle je
> Stufe nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> Branch: `imu_balance`. Master: [`00_imu_balance_plan.md`](00_imu_balance_plan.md).

---

## Stufe 0 — IMU-Plumbing & Viz  ⚪ offen

Plan: [`stage_0_imu_plumbing_plan.md`](stage_0_imu_plumbing_plan.md)

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

### Stufe-0-Post-Review
_(nach Implementierung — Tabelle Punkt | Status)_

---

## Stufe 1 — Kipp-/Sturz-Erkennung → Safe-State  ⚪ offen

Plan: [`stage_1_tip_detection_plan.md`](stage_1_tip_detection_plan.md)

```
- [ ] 1.1 TipMonitor: Schwellen-/Hysterese-/Edge-Logik als testbare Funktion/Klasse (ohne ROS)
- [ ] 1.2 /imu/data-Subscriber in gait_node (sensor-QoS) + roll/pitch/gyro-Ableitung
- [ ] 1.3 State-Gating (Auswertung nur in STANDING/WALKING, sonst reset)
- [ ] 1.4 Reaktion ueber VORHANDENE Safe-State-Mechanik (/hexapod_safety_freeze | B1-Sit), edge/latch, EIN Arbiter mit comms-loss - freeze/sit/gestaffelt nach §4
- [ ] 1.5 Parameter deklariert + dokumentiert (tip_angle_warn/crit, tip_rate_crit, debounce_ticks)
- [ ] 1.6 T1.1-T1.6 grün (Unit + Sim)
- [ ] 1.7 README/Konzept-Update (Safe-State-Verhalten, Schwellen, Gating, Arbiter)
- [ ] 1.8 colcon test + Lint grün
- [ ] 1.9 kritische Self-Review-Tabelle
```

### Stufe-1-Post-Review
_(nach Implementierung)_

---

## Stufen 2–4 — noch nicht ausgeplant

Werden nach Freigabe + Abschluss der Vorstufen separat geplant (CLAUDE.md §4):

- **Stufe 2 — Statisches Leveling:** `BalanceController` (austauschbar) +
  Rotations-Stellpfad + Envelope-Clamp + **Schräg-Welt(en)**. Risiken 1/2/3/6
  werden hier scharf.
- **Stufe 3 — Leveling im Laufen + Hang-Parameter:** Gyro-Dämpfung,
  θ→Parameter-Familie (Weg A), Gangart-Auto-Switch. **A/B-Entscheidung mit Daten.**
- **Stufe 4 — Terrain (Weg B):** Fußkontakt-Consumer, adaptiver Touchdown. Viel
  später, eigene Planung.
```
