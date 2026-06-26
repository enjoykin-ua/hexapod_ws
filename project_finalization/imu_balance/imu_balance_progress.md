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
- **Stufe 2 (statisches Leveling): 🟢 fertig (Sim verifiziert).** 2.1–2.10 ✅
  (615 Tests, 0 Fehler; max_level_angle=10° offline bestätigt; Live: pitch 8°→1.5°
  Totband, korrekte Richtung, kein Freeze). **Self-Review fand + behob einen
  Vorzeichen-Bug** im Stellpfad; Live-Diagnose deckte die **spawn-referenzierte
  gz-IMU** auf (→ flach spawnen, Memory). **User committet selbst.**
- **Stufe 3 zerlegt in 3a→3b→3c→3d** ([stage_3_walking_slope_plan.md](stage_3_walking_slope_plan.md) §0.5).
  **3a (Leveling im WALKING): 🟢 fertig (Sim verifiziert).** 620 Tests; Gating
  WALKING+STOPPING, state-abh. Clamp 10°/4°, Ramp-Welt; Live: Leveling wirkt (klein
  ~4°), Ramp-Geometrie-Bug gefixt, Kletter-Deckel ~12° (fixe Params) = 3c-Input.
  **User committet selbst.**
- **➡️ NÄCHSTER SCHRITT:** **3b** (Wackel-Dämpfung, Gyro-D-Term im BalanceController,
  B3-Fix) ODER **3c** (Hang-Param-Adaption fürs Klettern) — User-Wahl; je §4-Plan-Review.
- **Vorausgeplant (⚪ offen):** Stufe 3/4 — Pläne geschrieben (+ Stufe-2-Review-
  Verfeinerungen), Code je nach Freigabe.
- **➡️ NÄCHSTER SCHRITT:** **Stufe 2 (statisches Leveling)**,
  [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md). **§4-Plan-Review
  erledigt** — Entscheidungen stehen in §4/§5: Clamp = fester max 10° + IKError-Fallback ·
  Setpoint horizontal · parametrische `slope.sdf` + stehend spawnen (5/8/10°) · Tip
  unverändert + Startup-Grace (milde Hänge) · Leveling+Tip live tunbar · nur STANDING.
  **User liest den Plan → dann Code (2.1–2.10).** Test-Markdown erst am Ende der Stufe.
- **Arbeitsweise:** CLAUDE.md §4 (Plan → Freigabe → Code → Test → Self-Review),
  §5 (**Agent macht NIE git**). Stufen-Pläne haben `[ ]`-Template; **abgehakt wird hier**.
- **Doku-Querverweise (Master §7) ✅ nachgezogen:** `architecture.md` (`/imu/data`
  real → gait_node, hexapod_sensors-IMU, slope-Welt, geometry.rotate_xy) ·
  `ai_navigation.md` (Eintrag „IMU-Balance/Leveling/Kipp ändern" + §3-Tabelle).

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

## Stufe 2 — Statisches Körper-Leveling  🟢 fertig (Sim verifiziert)

Plan: [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md)

```
- [x] 2.1 Parametrische slope.sdf.xacro (geneigte Box, Winkel via xacro-Arg, gz-sim-imu-system) + slope.launch.py (expandiert Welt, spawnt um Hangwinkel gepitcht) + sim.launch.py spawn_roll/pitch_deg-Args  [xacro expandiert, `gz sdf --check`=Valid, beide Launches konstruieren; Hinweis: Body-pitched-Spawn + Auto-Standup (kein echter pre-stood-Spawn) → Live-Check 2.7]
- [x] 2.2 BalanceController (ROS-frei): Totband-PI + Slew + Anti-Windup + max-Clamp + Unit-Tests  [11 Unit-Tests grün, inkl. Closed-Loop-Konvergenz]
- [x] 2.3 geometry.rotate_xy-Helfer + gait_engine: set_body_orientation_offset + R-Rotation in compute_joint_angles (STANDING) + Clamp VOR IK (URDF-Limits) + IKError-Fallback (skalieren statt freezen)  [15 Tests grün: rotate_xy + Round-Trip + Clamp + Fallback-Degradation + STANDING-Gating]
- [x] 2.4 gait_node: BalanceController-Wiring (STANDING-Gating) + Params + Live-Tuning via _on_param_change (Leveling- UND Stufe-1-Tip-Params) + optionaler Startup-Grace-Gate  [9 Node-Tests grün; rclpy-Smoke ok]
- [x] 2.5 Offline-Envelope/CoG-Check (tools/leveling_envelope_check.py, θ als Arg, ECHTE URDF-Limits) für θ∈{5,8,10,12,15°} × Stance × {roll,pitch,combined}; CoG via compute_load  [10° in ALLEN Modi in-limit + CoG-stabil (Marge ~180–200mm); ab 12° combined/tief→LIM, ab 15° überall combined→LIM ⇒ max_level_angle=10° bestätigt; 5 Tool-Tests grün]
- [x] 2.6 Fuß-Scrub bewertet  [bei 10° voll: 15–21mm (roll/pitch), 24–33mm (combined, hoch); bei 5° 10–14mm. Über Slew 8°/s ~1.25s verteilt → ~0.4mm/Tick. v1 AKZEPTIERT; Reposition-Trigger vorgemerkt falls 2.7 Schlupf zeigt]
- [x] 2.7 Sim-Verify auf milder Schräge (8°) **live bestätigt:** flach gespawnt → IMU pitch 8° (Ground-Truth bestätigt); Leveling AN → pitch 8°→1.5° (= Totband), **Richtung korrekt** (Vorzeichen-Fix verifiziert), glatt, kein Freeze. Doku: [stage_2_static_leveling_test_commands.md](stage_2_static_leveling_test_commands.md)
- [x] 2.8 README/Konzept-Update (Leveling, Stellpfad, Clamp+Fallback, parametrische Welt, Params, Tool)  [hexapod_gait/README.md]
- [x] 2.9 colcon test + Lint grün  [615 Tests, 0 Fehler/Failures, 53 skipped; +35 ggü. Stufe 1; flake8/pep257 grün]
- [x] 2.10 kritische Self-Review-Tabelle  [unten]
```

### Stufe-2-Post-Review

| Punkt | Status |
|---|---|
| BalanceController (Totband-PI/Slew/Anti-Windup/Clamp) | OK (11 Unit-Tests inkl. Closed-Loop-Konvergenz) |
| Engine-Stellpfad Round-Trip (rotate_xy + Frames + IK/FK) | OK (FK reproduziert rotierte Targets, abs 1e-6) |
| Clamp VOR IK auf max_level_angle | OK (white-box-Test: 30°-Offset → 10° angewandt) |
| IKError-Fallback (skalieren statt freezen) | OK (60°-Offset degradiert, kein Raise; echte Bad-Pose raised) |
| max_level_angle=10° envelope-sicher (URDF-Limits) | OK (Tool: alle Stance×{roll,pitch,combined} in-limit+CoG-stabil; ab 12° combined LIM) |
| Nur-STANDING-Gating | OK (WALKING ignoriert Offset, Test) |
| Live-Tuning Leveling+Tip | OK (Node-Tests + rclpy-Smoke; Monitor-Rebuild) |
| Startup-Grace unterdrückt Tip bei Konvergenz | OK (Node-Test) |
| **Leveling-RICHTUNG (levelt vs. anti-levelt)** | ✅ **Bug im Self-Review gefunden + behoben + live bestätigt:** Engine wandte `R(+corr)` an → positive Rückkopplung. Fix: Füße um `−corr`. **Live (T2.2): pitch 8°→1.5°, korrekte Richtung.** Regressionsgesichert (Round-Trip-Test `-roll,-pitch`; Tool ±-Vorzeichen) |
| **Spawn-Pose / gz-IMU-Referenz** | ✅ **Live-Befund (T2.0/T2.1):** gz-IMU ist **spawn-referenziert** → gepitchter Spawn maskierte die Neigung (las 0° statt 8°). Fix: `slope.launch.py` spawnt jetzt **flach** → IMU liest echten Hang (8° verifiziert, Ground-Truth bestätigt). Memory `project_gz_imu_spawn_referenced` |
| Inter-Bein-Selbstkollision (A4) bei Leveling | 🟡 vormerken: compute_load prüft CoG/Polygon, NICHT Inter-Bein-Kollision; bei ≤10° auf Stand-Pose (~25mm Scrub) gering — visuell in T2.2 prüfen |
| Auto-Standup statt pre-stood-Spawn auf Schräge | 🟡 live (T2.1): mild tragfähig; bei Haken slope_deg senken; pre-stood = Stufe 3 |
| Fuß-Scrub bei 10° (15–33mm, ~0.4mm/Tick) | OK (akzeptiert v1; Reposition vorgemerkt falls T2.2 Schlupf) |
| dt aus monotonic (nicht /clock) in Leveling | 🟢 später (konsistent mit bestehendem wall-clock-Tick; RTF=1 unkritisch) |
| Tip-Live-Tuning löscht CRIT-Latch (Rebuild) | 🟡 minor: nur beim aktiven Tunen relevant, akzeptabel |
| CoG-Check flat-leveled-Annahme | 🟢 später (gültig für gelevelte Pose = Body horizontal) |

---

## Stufe 3a — Leveling im WALKING  🟢 fertig (Sim verifiziert)

Plan: [`stage_3a_leveling_walking_plan.md`](stage_3a_leveling_walking_plan.md)

```
- [x] 3a.1 Stellpfad-Gating Engine+Node auf WALKING (+STOPPING) + state-abh. Clamp (STANDING 10° / WALKING 4°)  [py-compile + Smoke]
- [x] 3a.2 Offline-Walking-Hüllen-Check vs θ (leveling_envelope_check --walking, Fallback-frei) → Walking-Hülle: Pitch/Roll ~4°, combined ~2° (Swing-Apex bindet)
- [x] 3a.3 Ramp-Welt ramp.sdf.xacro (flach→Hang→Plateau, Winkel via Arg) + ramp.launch.py + sim.launch.py spawn_x  [xacro+gz sdf valid, Launches konstruieren]
- [x] 3a.4 Unit/Engine-Tests (Leveling WALKING+STOPPING, Walking-Clamp 4° vs STANDING 10°, Round-Trip) + Node-Tests + Tool-Tests  [620 colcon + 7 Tool grün]
- [x] 3a.5 Sim-Verify **live bestätigt:** Rampe (8°-Welt sauber, kein Absatz, kurzer Anlauf) hochgelaufen; Leveling AN → Körper-Neigung sichtbar (klein, ~Walking-Clamp 4°) kleiner als AUS, kein Freeze. Ramp-Geometrie-Fix (Absatz→0mm) + spawn_x=−0.7 + gait `leveling_enable`-Launch-Arg. **Kletter-Deckel ~12° (fixe Params) = 3c-Input**
- [x] 3a.6 README/Konzept-Update (Gating WALKING, state-abh. Clamp, Walking-Hülle, Ramp-Welt)  [hexapod_gait/README.md]
- [x] 3a.7 colcon test + Lint grün  [620 Tests, 0 Fehler; +7 Tool-Tests; ramp/sim-Launch konstruieren]
- [x] 3a.8 kritische Self-Review-Tabelle  [unten]
```

> **Befund 3a:** uniformes Walking-Leveling cappt bei **~4° (Pitch/Roll), ~2° (combined)** —
> der gelevelte Swing-Apex bindet (nicht step_height senken → Schürf-Gefahr; mehr Range =
> 3c hang-bewusste Schwunghöhe). State-abh. Clamp: STANDING 10° (kein Regress), WALKING 4°.

### Stufe-3a-Post-Review

| Punkt | Status |
|---|---|
| Gating Engine+Node auf WALKING+STOPPING | OK (test_walking_applies_leveling, test_stopping_applies_leveling) |
| State-abhängiger Clamp (STANDING 10° / WALKING 4°) | OK (test_walking/standing_uses_*_clamp) |
| Walking-Hülle offline gemessen (~4°/2°) | OK (Tool --walking + 2 Tool-Tests) |
| Vorzeichen im Walking (FK-Round-Trip) | OK (Round-Trip-Test, aus Stufe 2 getragen) |
| **Controller-Clamp-Sprung beim State-Wechsel** | ✅ **Self-Review-Fund + Fix:** Engine-Clamp sprang 4°→10° beim Anhalten am Hang (Ruck). Fix: Controller-Clamp state-abhängig mitführen → dessen Slew glättet WALKING↔STANDING. Engine-Clamps = Backstop |
| Swing-Apex bindet → kleiner Walking-Clamp | 🟡 ~4° ist klein; echte Hang-Range = 3c (hang-bewusste Schwunghöhe, NICHT step_height senken) |
| **Tip-Interaktion auf Steilrampe** | 🟡 erwartet: ab ~18° Rampe übersteigt Rest-Neigung (Hang−4°) `tip_angle_warn` → Stopp. Steil-Test: tip-Schwelle live hoch; echter Fix (residual-tip) = 3c |
| Ramp-Welt Übergang flach→Rampe | 🟡 live (T3a.1): evtl. kleiner Lip am Knick (x=0) — Roboter sollte drüberlaufen |
| Fuß-Scrub im Walking | 🟢 selbst-begrenzend (Füße replanten je Schritt); live T3a.2 sichten |
| Climbing-Ceiling | 🟢 später: Sim CoG/µ (~50°), HW = Servo-Torque (Block A) — separat messen |
| use_sim_time / dt aus monotonic | 🟢 später (wie Stufe 2, wall-clock-Tick) |
| **Leveling im Lauf wirkt (Live)** | ✅ verifiziert: Körper-Neigung mit Leveling sichtbar kleiner (klein ~4°-Clamp, erwartet) |
| **Ramp-Geometrie-Bug (Live-Fund)** | ✅ Plateau lag tiefer (Box-Überschuss) → fixed (Oberkante exakt am Plateau, 0mm Absatz, alle Winkel); spawn_x −0.7 (war zu weit) |
| **Kletter-Stall >12° (fixe Params, Live)** | 🟡 → **3c**: Vortrieb/CoG am Steilhang (nicht Reibung — Fuß µ=1.0); Fußschalter = Stufe-4-Terrain, kein Smooth-Slope-Vortrieb; HW-Ceiling = Servo-Torque |
| ros2-param-set „Node not found" (Live) | ✅ stale Daemon; `leveling_enable` als gait.launch-Arg ergänzt (umgeht es) |

---

## Stufen 3b–4 — ⚪ offen (vorausgeplant, Implementierung nach §4-Freigabe)

Pläne geschrieben (Logik/Tests/Design/offene Punkte) zum Nachlesen; Code +
Test-Markdown pro Stufe nach Freigabe:

- **Stufe 2 — Statisches Leveling:** [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md)
  — `BalanceController` + Rotations-Stellpfad + Clamp + Schräg-Welten. Risiken 1/2/3/6 scharf.
- **Stufe 3 — Leveling im Laufen + Hang-Parameter:** [`stage_3_walking_slope_plan.md`](stage_3_walking_slope_plan.md)
  — Gyro-Dämpfung, θ→Parameter-Familie (Weg A), Gangart-Auto-Switch. **A/B-Entscheidung mit Daten.**
- **Stufe 4 — Terrain (Weg B + Fußkontakte):** [`stage_4_terrain_adaptive_plan.md`](stage_4_terrain_adaptive_plan.md)
  — adaptiver Touchdown, Plausibilitäts-Fail-Safe. Forschungs-grade, braucht E2-Taster.
```
