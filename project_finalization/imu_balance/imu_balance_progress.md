# A5 IMU-Balance — Progress

> **Done-Vertrag** (CLAUDE.md §4). Die Bullets sind 1:1 aus den Stufen-Plänen.
> **Alle `[x]` einer Stufe = Stufe fertig**, keine retroaktive Anpassung. Pro
> erledigtem Bullet sofort `[ ]`→`[x]` (nicht batchen). Post-Review-Tabelle je
> Stufe nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> Branch: `imu_balance`. Master: [`00_imu_balance_plan.md`](00_imu_balance_plan.md).

---

## Stufe 0 — IMU-Plumbing & Viz  🟢 fertig (Sim verifiziert)

Plan: [`stage_0_imu_plumbing_plan.md`](stage_0_imu_plumbing_plan.md)

```
- [x] 0.1 hexapod.imu.xacro: imu_link+imu_joint (immer, Dummy-Inertia), gz-IMU-Sensor (use_sim-geguarded) - preserve/lumping am imu_joint, sensor am imu_link; include via enable_imu in hexapod.urdf.xacro  [xacro-Logik verifiziert: Sim=Link+Sensor / HW=nur Link / aus=nichts]
- [x] 0.2 worlds/empty_imu.sdf (= empty.sdf + gz-sim-imu-system) als Sim-Default-Welt  [headless load fehlerfrei; libgz-sim8-imu-system vorhanden]
- [x] 0.3 bridge_imu.yaml (gz.msgs.IMU -> sensor_msgs/Imu, /imu/sim -> /imu/data)  [installiert]
- [x] 0.4 sim.launch.py: declare_enable_imu + enable_imu an xacro + imu_bridge + imu_monitor conditional; Default-world = empty_imu.sdf  [--show-args lädt sauber, args korrekt]
- [x] 0.5 imu_monitor-Node in hexapod_sensors (sensor-QoS best_effort, use_sim_time, roll/pitch + /imu/monitor + world->base_link-tf)  [build + flake8/pep257 grün]
- [x] 0.6 RViz zeigt Modell-Neigung (world->base_link-tf aus IMU roll/pitch)  [T0.5 live: Gazebo-Neigung -> RViz-Modell kippt mit]
- [x] 0.7 T0.1-T0.6 grün (Sim); URDF-Full-Smoke via T0.4 (Aufstehen+Laufen) + T0.5 (RViz lädt); Ground-Truth qualitativ bestätigt  [T0.3 strikt-numerisch -> Stufe 2 (statische Rampe)]
- [x] 0.8 hexapod_sensors-README + Konzept-Doku (gz-IMU-Sensor, gz-sim-imu-system, ros_gz-Bridge, sensor_msgs/Imu+Covariance, Sensor-QoS, Quaternion->roll/pitch, REP-103/REP-145)
- [x] 0.9 colcon test + Lint (ament_flake8/pep257) grün  [571 Tests, 0 Fehler]
- [x] 0.10 kritische Self-Review-Tabelle  [unten]
```

**Zusatz (User-Wunsch mid-stage):** leg_1-Femur als **grüner Orientierungs-Marker**
(materials.xacro `green` · leg.xacro `femur_material`-Param · leg_1 = green). Verifiziert
(1× grün / 5× orange); macht Front/Bein-Zuordnung beim Kipp-Test in Gazebo+RViz eindeutig.

### Stufe-0-Post-Review

| Punkt | Status |
|---|---|
| xacro-Logik (Sim Link+Sensor / HW nur Link / aus nichts) | OK (verifiziert) |
| Welt lädt `gz-sim-imu-system` | OK (T0.1 live: /imu/data @ ~98 Hz) |
| `world→base_link`-tf + Modell-Neigung | OK (T0.5: RViz-Modell kippt mit Gazebo) |
| IMU-QoS best_effort | OK (T0.1: Daten fließen) |
| roll/pitch-Reaktion + Achsen | OK (T0.2: Nase->pitch, seitlich->roll) |
| Laufen: roll/pitch stabil | OK (T0.4: ±0.1°, kein Drift-Weg) |
| Ground-Truth strikt-numerisch | 🟡 → Stufe 2 (statische Rampe; flach = self-righting, kein sauberer statischer Winkel) |
| Modell-Neigung nur Orientierung (keine Translation) | 🟢 später (Odom out-of-scope) |
| `imu_link` jetzt auch in HW-URDF (enable_imu default true) | 🟡 vormerken: HW-URDF-Full-Smoke beim 1. HW-Lauf (xacro parst `use_sim:=false` grün; `imu_joint` fixed, kein ros2_control-IF) |
| `use_sim_time` auf HW (Monitor/Balance-Node) | 🟡 vormerken (Risiko 5) |
| robot_description-lenient-WARN in gait.launch (T0.4) | OK — invocations-bedingt (ohne robot_description_file), vorbestehend, IMU-unabhängig |

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
