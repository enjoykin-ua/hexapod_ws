# A5 IMU-Balance — Progress

> **Done-Vertrag** (CLAUDE.md §4). Die Bullets sind 1:1 aus den Stufen-Plänen.
> **Alle `[x]` einer Stufe = Stufe fertig**, keine retroaktive Anpassung. Pro
> erledigtem Bullet sofort `[ ]`→`[x]` (nicht batchen). Post-Review-Tabelle je
> Stufe nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> Branch: `imu_balance`. Master: [`00_imu_balance_plan.md`](00_imu_balance_plan.md).

---

## Stand & nächster Schritt (Übergabe)

- **Fertig (Sim verifiziert):** Stufe 0 (IMU-Plumbing/Viz) 🟢 · Stufe 1 (Kipp-
  Erkennung → Safe-State) 🟢. Branch `imu_balance` (**User committet selbst**).
- **Vorausgeplant (⚪ offen):** Stufe 2/3/4 — Pläne geschrieben, Code je nach Freigabe.
- **➡️ NÄCHSTER SCHRITT:** **Stufe 2 (statisches Leveling)**,
  [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md). **§4-Plan-Review
  erledigt** — Entscheidungen stehen in §4/§5: Clamp = fester max 10° + IKError-Fallback ·
  Setpoint horizontal · parametrische `slope.sdf` + stehend spawnen (5/8/10°) · Tip
  unverändert + Startup-Grace (milde Hänge) · Leveling+Tip live tunbar · nur STANDING.
  **User liest den Plan → dann Code (2.1–2.10).** Test-Markdown erst am Ende der Stufe.
- **Arbeitsweise:** CLAUDE.md §4 (Plan → Freigabe → Code → Test → Self-Review),
  §5 (**Agent macht NIE git**). Stufen-Pläne haben `[ ]`-Template; **abgehakt wird hier**.
- **Doku-Querverweise noch offen (Master §7):** `architecture.md` (`/imu/data` von
  „geplant" auf real) · `ai_navigation.md` (Eintrag „ich ändere Balance/IMU → …").

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

## Stufe 1 — Kipp-/Sturz-Erkennung → Safe-State  🟢 fertig (Sim verifiziert)

Plan: [`stage_1_tip_detection_plan.md`](stage_1_tip_detection_plan.md)

```
- [x] 1.1 TipMonitor: Schwellen-/Entprellung-/Latch-Logik als testbare Klasse (ohne ROS)  [9 Unit-Tests grün]
- [x] 1.2 /imu/data-Subscriber in gait_node (sensor-QoS best_effort) + roll/pitch + Kipprate
- [x] 1.3 State-Gating (Auswertung nur in STANDING/WALKING, sonst reset)
- [x] 1.4 Reaktion: WARN->cmd_vel=0, CRIT->/hexapod_safety_freeze (edge/latch); KEIN Sit (User-Entscheid)
- [x] 1.5 Parameter deklariert + dokumentiert (tip_detection_enable, tip_angle_warn/crit_deg, tip_rate_crit_dps, tip_debounce_ticks)
- [x] 1.6 T1.6 (Unit) + T1.1-T1.5 (Sim) grün  [CRIT feuert+lokaler Stopp; T1.2/T1.3 ohne Fehlalarm; T1.4-Gating implizit via Aufstehen in T1.2/T1.3]
- [x] 1.7 README/Konzept-Update (hexapod_gait README: Safe-State, Schwellen, Gating, no-IMU-degradation)
- [x] 1.8 colcon test + Lint grün  [580 Tests, 0 Fehler]
- [x] 1.9 kritische Self-Review-Tabelle  [unten]
```

### Stufe-1-Post-Review

| Punkt | Status |
|---|---|
| TipMonitor-Logik (Schwellen/Entprellung/Latch/Reset) | OK (9 Unit-Tests) |
| WARN→cmd_vel=0 vor set_command | OK (Tick-Hook vor set_command) |
| CRIT→freeze einmalig (edge) + skip publish | OK (Latch + `_tip_crit_fired`); in Sim kein freeze-Service → lokaler Stopp (JTC hält), erwartet |
| Gating nur STANDING/WALKING | OK (Live: Aufstehen in T1.2/T1.3 ohne Fehlalarm) |
| Ohne IMU: graceful (NONE, normales Laufen) | OK (`_imu_roll is None` → NONE) |
| QoS `/imu/data` best_effort | OK (`qos_profile_sensor_data`) |
| Kein Hinsetzen als crit-Reaktion | OK (User: Sit würde am Hang selbst kippen) |
| tip-Params Init-only (nicht in `_on_param_change`) | 🟡 Live-Tuning erst Stufe 2 (Relaunch zum Ändern) |
| Recovery nach CRIT-Freeze | 🟡 via State-Wechsel (sit/stand-Service) → reset; auf flachem Boden ungetestet |
| Live T1.1/T1.5 (crit feuert) | OK (Topple → „Kipp-CRIT … Safety-Freeze"; präzise Schwelle → Stufe-2-Rampe) |
| Live-Funktionstest (Integration) | OK (T1.1–T1.5 Sim grün) |

---

## Stufen 2–4 — ⚪ offen (vorausgeplant, Implementierung nach §4-Freigabe)

Pläne geschrieben (Logik/Tests/Design/offene Punkte) zum Nachlesen; Code +
Test-Markdown pro Stufe nach Freigabe:

- **Stufe 2 — Statisches Leveling:** [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md)
  — `BalanceController` + Rotations-Stellpfad + Clamp + Schräg-Welten. Risiken 1/2/3/6 scharf.
- **Stufe 3 — Leveling im Laufen + Hang-Parameter:** [`stage_3_walking_slope_plan.md`](stage_3_walking_slope_plan.md)
  — Gyro-Dämpfung, θ→Parameter-Familie (Weg A), Gangart-Auto-Switch. **A/B-Entscheidung mit Daten.**
- **Stufe 4 — Terrain (Weg B + Fußkontakte):** [`stage_4_terrain_adaptive_plan.md`](stage_4_terrain_adaptive_plan.md)
  — adaptiver Touchdown, Plausibilitäts-Fail-Safe. Forschungs-grade, braucht E2-Taster.
```
