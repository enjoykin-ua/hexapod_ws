# A5 IMU-Balance — Progress

> **Done-Vertrag** (CLAUDE.md §4). Die Bullets sind 1:1 aus den Stufen-Plänen.
> **Alle `[x]` einer Stufe = Stufe fertig**, keine retroaktive Anpassung. Pro
> erledigtem Bullet sofort `[ ]`→`[x]` (nicht batchen). Post-Review-Tabelle je
> Stufe nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> Branch: `imu_balance`. Master: [`00_imu_balance_plan.md`](00_imu_balance_plan.md).

---

## Stand & nächster Schritt (Übergabe)

> **🧭 NEUER CHAT, KURZ: Wir sind in Block A5 → Stufe 4 (Terrain-adaptiv, Fußkontakte).**
> **TF (Stufe 3, IMU-Hang-Laufen) ist 🟢 Sim-fertig + ⏸️ pausiert** (Wiedereinstieg
> [stage_3 §7](stage_3_terrain_following_plan.md)). **Aktiv: Stufe 4.** **S4-1 (Kontakt-Consumer +
> Verifikation) 🟢 fertig** — Signal verifiziert (Sensor korrekt; ~13-Tick-Offset = Ausführungs-Lag
> des schnellen Aufsetzers, kein Defekt). **➡️ NÄCHSTER SCHRITT: S4-2 (adaptiver Touchdown mit
> kontrollierter Senk-Rate) implementieren** — **Plan ist geschrieben + handoff-vollständig:**
> [`stage_4b_adaptive_touchdown_plan.md`](stage_4b_adaptive_touchdown_plan.md) (S4-1-Befunde +
> Code-Anker + §4-Vorschläge drin). §4-Workflow: **erst User-Freigabe** zum Plan, dann Code → Test
> → Self-Review. Tests aktuell **272 grün** (gait). **User committet selbst.**

- **Fertig (Sim verifiziert):** Stufe 0 (IMU-Plumbing/Viz) 🟢 · Stufe 1 (Kipp-
  Erkennung → Safe-State) 🟢. Branch `imu_balance` (**User committet selbst**).
- **Stufe 2 (statisches Leveling): 🟢 fertig (Sim verifiziert).** 2.1–2.10 ✅
  (615 Tests, 0 Fehler; max_level_angle=10° offline bestätigt; Live: pitch 8°→1.5°
  Totband, korrekte Richtung, kein Freeze). **Self-Review fand + behob einen
  Vorzeichen-Bug** im Stellpfad; Live-Diagnose deckte die **spawn-referenzierte
  gz-IMU** auf (→ flach spawnen, Memory). **User committet selbst.**
- **Stufe 3 zerlegt in 3a→3b→3c→3d** ([stage_3_walking_slope_plan.md](discarded/stage_3_walking_slope_plan.md) §0.5).
  **3a (Leveling im WALKING): 🟢 fertig (Sim verifiziert).** 620 Tests; Gating
  WALKING+STOPPING, state-abh. Clamp 10°/4°, Ramp-Welt; Live: Leveling wirkt (klein
  ~4°), Ramp-Geometrie-Bug gefixt, Kletter-Deckel ~12° (fixe Params) = 3c-Input.
  **User committet selbst.**
- **⚠️ RICHTUNGSWECHSEL (2026-06-27): Klettern via Leveln → Terrain-Following.** Stufe 3c-1
  (θ→Param-Tabelle + Voll-Leveling) wurde **gebaut + Sim-getestet → verworfen**: Körper
  waagerecht halten sieht sprawlig aus, Plateau-Reset-Bug, Trippeln. Der **Code wurde
  zurückgesetzt** (`git reset` auf „3c 1 plan created"; liegt in der History). **Neuer
  Ansatz:** Körper folgt dem Boden (flach → waagerecht, Hang → hangparallel), IMU für
  **Sicherheit + Wackel-Dämpfung + Hang-Wissen**. Achsen-Trennung: **roll → 0 ausrichten,
  pitch → folgen**.
  - **Neuer Plan:** [`terrain_following_plan.md`](stage_3_terrain_following_plan.md) (TF-1/2/3).
  - **Warum + Nachweis (Bein-Streckung = Leveling-Artefakt):** [`terrain_following_pivot_retro.md`](terrain_following_pivot_retro.md).
  - **TF-1 (passiv TF + slope-bewusster Tip): 🟢 fertig (Sim-verifiziert).** `SlopeEstimator`
    + slope-bewusster Tip (residual beide Achsen) + `/imu/slope`. Sim-Befund: Schätzung trackt
    den Hang, **Grenze = Knick/Kante** (nicht Hang-Laufen) [[project_tf1_climb_limit_is_edge]].
  - **TF-2 (aktive Stab.: roll→0, pitch→folgen + Gyro-D): 🟢 fertig (Sim-verifiziert, flach).**
    `leveling_mode {terrain,horizontal}`, Gyro-D, alles live tunbar. Sim-Befund: Nicht-Tripod
    wackelt prinzipbedingt (Open-Loop), Dämpfung wirkt begrenzt; Totband-Hebel notiert. **651 Tests.**
  - **⏸️ PAUSIERT nach TF-2 (2026-06-28, User-Entscheid).** Grund: sichtbarer IMU-Mehrwert in Sim
    klein (Gazebo ohne Servo-Nachgiebigkeit/Rauschen → Wert zeigt sich erst auf HW, Prinzip D6);
    größeres offenes Problem (Knick/unebener Weg) = **Stufe 4 (Fußkontakte)**, kein Balance-Thema.
    **Rückkehr** nach Stufe 4 + HW-Tests. **Wiedereinstieg grob vorgeplant:**
    [`stage_3_terrain_following_plan.md` §7](stage_3_terrain_following_plan.md) (P0 HW-Validierung ·
    P1 TF-3 Schwerpunkt/Schlupf · P2 TF-Quer · P3 Gang-Stabilisierung · P4 Auto-Tuning).
- **Verworfen + markiert (Referenz):** `stage_3c_slope_params_plan.md`, `stage_3c_1_param_table_plan.md`,
  `stage_3c_1_test_commands.md`. Stufe 0/1/2 + `BalanceController`/Welten **bleiben** Fundament.
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

Plan: [`stage_3a_leveling_walking_plan.md`](discarded/stage_3a_leveling_walking_plan.md)

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

## Stufe 3c-1 — θ→Param-Tabelle + Voll-Leveling  ❌ VERWORFEN (siehe Retro)

> **Gebaut + Sim-getestet → verworfen** (2026-06-27). Voll-Leveling fürs Klettern sieht
> sprawlig aus + Plateau-Reset-Bug + Trippeln. **Code zurückgesetzt** (`git reset` auf
> „3c 1 plan created"; liegt in der History). **Nachfolge: Terrain-Following.**
>
> Begründung, Sim-Befunde + Nachweis (Bein-Streckung war ein Leveling-Artefakt):
> [`terrain_following_pivot_retro.md`](terrain_following_pivot_retro.md).
> Neuer Plan: [`terrain_following_plan.md`](stage_3_terrain_following_plan.md).
>
> Die ehemalige 3c-1-Checkliste + Post-Review-Tabelle stehen in der Git-History
> (Commit-Stand vor dem Reset) bzw. im verworfenen [Plan](discarded/stage_3c_1_param_table_plan.md).

---

## Terrain-Following (TF) — ⚪ offen, neuer Ansatz

Umbrella: [`stage_3_terrain_following_plan.md`](stage_3_terrain_following_plan.md). Stufen:
- **TF-1** (passiv terrain-following + slope-bewusster Tip) — Plan: [`stage_3a_passive_tf_plan.md`](stage_3a_passive_tf_plan.md) 🟡 **Code+Tests fertig, Sim-Verify (User) offen**
- **TF-2** (aktive Körper-Stabilisierung: roll→0, pitch→folgen + Gyro-Wackel-Dämpfung) — Plan: [`stage_3b_active_tf_plan.md`](stage_3b_active_tf_plan.md) **🟢 fertig (Sim-verifiziert, flacher Boden).** `leveling_mode {horizontal,terrain}` Default terrain · Gyro-D · `Kd≈0.03`/Totband 1.5 (konservativ, HW-tauglich; Tuning live). Sim-Befund: tetrapod/ripple wackeln prinzipbedingt (Open-Loop), Dämpfung wirkt begrenzt (Totband-Hebel). **User committet selbst.**
- **TF-Quer** (Quer-/Diagonal-Traversieren: roll-Residual + cmd_vel-Richtungslogik) — nach TF-2, [TF-2-Plan §6](stage_3b_active_tf_plan.md). ⚪ vorgemerkt (User-Wunsch, in ai_navigation nach TF-2-Abschluss).
- **TF-3** (optional: Schwerpunkt-Hilfe + Schlupf) — Plan folgt

### TF-1 — Passiv TF + slope-bewusster Tip

Plan: [`stage_3a_passive_tf_plan.md`](stage_3a_passive_tf_plan.md) · Test-Doku:
[`stage_3a_passive_tf_test_commands.md`](stage_3a_passive_tf_test_commands.md)

**§4-Freigabe-Entscheidungen (User):** residual **beide Achsen** (roll+pitch) · `/imu/slope`
**publizieren** · τ-Start **0.5 s** · Charakterisierung **8/12/16/20/25/35°** · Slope-Clamp
**±40°** (deckt 35° ab, sonst künstliche Sättigung → Agent-Entscheidung).

```
TF-1:
- [x] TF1.1 Hang-Schätzung in gait_node (langsamer Tiefpass auf roll/pitch, τ-Param, Clamp ±max)  [ROS-frei in slope_estimator.py, Snap-Init; _update_slope_estimate, State-Gating STANDING/WALKING]
- [x] TF1.2 slope-bewusster Tip: residual (= IMU − Schätzung) an TipMonitor, tilt_rate roh; Param slope_aware_tip_enable (+ live)  [residual beide Achsen; TipMonitor unverändert]
- [x] TF1.3 (optional) Hang-Schätzung auf /imu/slope publizieren (Sim-Verifikation)  [Float64MultiArray [roll_deg, pitch_deg]]
- [x] TF1.4 Unit-Tests (Tiefpass, residual+Clamp, slope-aware Tip feuert/feuert-nicht) + Node-Smoke  [test_slope_estimator.py 14 Tests + test_leveling_node.py TF-1-Block 7 Tests]
- [x] TF1.5 colcon test + Lint grün  [gait 243 / kinematics 42 passed, 0 Fehler; flake8/pep257 grün]
- [x] TF1.6 README/Konzept-Update (hexapod_gait: passiv TF, Hang-Schätzung, slope-bewusster Tip)
- [x] TF1.7 Test-Doku stage_3a_passive_tf_test_commands.md (Rampen-Ladder 8–35°)  [Sim-Verify durch User offen]
- [x] TF1.8 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)  [unten]
```

> **Sim-Verify (User, erste Runde 8/16/35°):** Hang-Schätzung **bestätigt** —
> `/imu/slope` trackt den echten Hang, Körper hangparallel, kein Fehlalarm.
> **Zentraler Befund:** die Kletter-Grenze ist der **Knick** (Übergang flach↔Hang /
> Hang↔Plateau), **nicht** das Laufen *auf* dem Hang. 8° sauber; 16° kommt hoch, aber
> am konvexen Plateau-Scheitel hängen die mittleren Beine auf der Kante + vordere/hintere
> ohne Bodenkontakt; 35° = quasi Stufe/Bordstein, Knick flach→Hang passiv nicht machbar.
> **Scope-Trennung:** Wackeln/Seitneigung → TF-2 (Dämpfung+roll→0); „Bein findet keinen
> Boden an Kante/Stufe" → **Stufe 4 (Fußkontakte)**, NICHT TF-2. Details + Tabelle in der
> [Test-Doku](stage_3a_passive_tf_test_commands.md) (Abschnitt „Befund: die Grenze ist der KNICK").

### TF-1-Post-Review

| Punkt | Status |
|---|---|
| `SlopeEstimator` (EMA `α=dt/(τ+dt)`, Clamp, Snap-Init) | OK (14 Unit-Tests: Konvergenz/Lag, Clamp, τ-Sonderfälle, Residual) |
| Residual an `TipMonitor`, Kipprate roh | OK (`test_slope_aware_tip_ignores_constant_slope` + Roh-Gegenprobe feuert) |
| `TipMonitor` unverändert (bekommt nur residual) | OK (kein Refactor; Stufe-1-Logik bleibt geprüft) |
| Estimator-State-Gating = Tip-Gating (STANDING/WALKING) | OK (mirror; Transition-States reset) |
| Snap-Init verhindert Fehl-Tip beim (Wieder-)Eintritt am Hang | OK (`test_slope_estimate_snaps_in_standing`; residual ≈ 0 ab Tick 1) |
| Slope-Clamp ±40° deckt Charakterisierung bis 35° | OK (sonst sättigt die Schätzung bei <Hang → künstlicher residual) |
| `/imu/slope` publiziert jeden Tick (Grad) | OK; in Transition-States [0,0] (reset) — harmlos, beobachtbar |
| Live-Params + Validierung (τ≥0, clamp>0) | OK (`test_slope_params_live_tunable` + `_reject_invalid`) |
| Ohne IMU graceful (reset, kein publish, Tip NONE) | OK (`test_slope_estimate_reset_without_imu`) |
| Reihenfolge im Tick (Schätzung VOR Tip) | OK (residual nutzt die aktuelle Schätzung) |
| residual **beide** Achsen vs. nur pitch | OK (User-Entscheid; beim Geradeaus-Klettern folgt roll-LP ~0 → `res_roll ≈ roll`, Tip bleibt empfindlich) |
| Gait-Ripple im Walking → residual | 🟢 Ripple ist schnell (bleibt im residual), aber klein (< WARN); Entprellung (Stufe 1) fängt es — wie auf flachem Boden |
| Flat→Ramp-Knick: kurzer residual-Spike beim Eintritt | 🟡 **Sim beobachten** (T3): τ-Lag erzeugt kurz residual ~ Pitch-Sprung; Debounce(5)+15°-Marge sollte es absorbieren; sonst τ leicht senken |
| Kein neuer Stellpfad (passiv) → kein IK/Envelope-Risiko | OK (Risiko 1/2/6 N/A für TF-1; aktive Rotation erst TF-2) |
| `/imu/slope` in `architecture.md` nachziehen | 🟢 später (bei Live-Schaltung, Master §7 — Sim-only Diagnose-Topic) |
| use_sim_time / dt aus monotonic | 🟢 später (konsistent mit bestehendem wall-clock-Tick, wie Stufe 2/3a) |
| **Passiver Kletter-Limit (Sim)** | ✅ **User-Sim-Verify (8/16/35°):** Grenze = **Knick/Kante** (konvexer Plateau-Scheitel, Stufe bei 35°), nicht Hang-Laufen. Schätzung trackt korrekt, kein Fehlalarm. Scope: Wackeln→TF-2, Bodenkontakt-an-Kante→Stufe 4 |
| **Hang-Schätzung trackt echten Hang (Live)** | ✅ `/imu/slope` ≈ echter Hangwinkel (8°: −7.98°), pendelt ein; Körper hangparallel |

### TF-2 — Aktive Körper-Stabilisierung (roll→0, pitch→folgen) + Gyro-Dämpfung

Plan: [`stage_3b_active_tf_plan.md`](stage_3b_active_tf_plan.md) (§4-Freigabe erteilt).

```
TF-2:
- [x] TF2.1 gait_node _on_imu: signierte Gyro-Achsenraten cachen (_imu_gyro_roll/pitch)
- [x] TF2.2 BalanceController: Gyro-D-Term (update(...,gyro_roll=0,gyro_pitch=0), d=−Kd·rate, D vor Slew, im Totband aktiv) + Kd in set_gains, rückwärtskompatibel
- [x] TF2.3 gait_node: leveling_mode (horizontal|terrain, Default terrain) → terrain füttert pitch=residual/roll=roh, horizontal=beide roh; Gyro durchreichen  [Slope-Schätzung jetzt auf _LEVELING_NODE_STATES (inkl. STOPPING) ausgerichtet]
- [x] TF2.4 Params leveling_mode + leveling_kd deklariert + live (_on_param_change, mode-String-Validierung)
- [x] TF2.5 Unit-Tests (Gyro-D Vorzeichen/Totband/Clamp+Slew, pitch-Residual-Regelung, Closed-Loop-Dämpfung) + Node-Wiring-Tests  [+7 BalanceController +5 Node]
- [x] TF2.6 colcon test + Lint grün  [651 Tests, 0 Fehler; gait 254 / kinematics 42; flake8/pep257 grün]
- [x] TF2.7 README/Konzept-Update (terrain-Modus, per-Achse-Sollwert, Gyro-D, Modus-Schalter, Params)
- [x] TF2.8 Test-Doku stage_3b_active_tf_test_commands.md (komfortabel: strikte Reihenfolge, Kd/slew-Tuning Schritt für Schritt, terrain-vs-horizontal) + **Sim-Verify durch User (flacher Boden)**  [Befund unten]
- [x] TF2.9 kritische Self-Review-Tabelle  [unten]
```

> **TF-2 🟢 Sim-verifiziert (flacher Boden, alle Gangarten).** Befund: tripod wackelfrei
> (erwartet, nichts zu dämpfen), wave grenzwertig ok, **tetrapod/ripple wackeln gangsynchron
> ±1–2°** (prinzipbedingtes Open-Loop-CoG-Wandern, [[project_nontripod_gait_wobble]]). **Schlüssel-
> Erkenntnis:** das `leveling_deadband_deg` (1.5°) ist **größer** als die Wackel-Amplitude →
> die P/I-Regelung ist beim kleinen Wackeln **inaktiv** (nur Gyro-D wirkt). Stärkere Sichtbarkeit
> braucht **Totband ↓** (z.B. 0.3°) + Kp/Kd ↑ — in Sim gratis, auf HW Vorsicht (Rausch/Zittern).
> Defaults (Kd 0.03 / Totband 1.5) bewusst **konservativ belassen** (HW-tauglich); Tuning live.
> **Grenze:** „tripod-ruhig" für Nicht-Tripod ist mit *reaktivem* Leveling nicht erreichbar →
> bräuchte aktive Gang-/Schwerpunkt-Stabilisierung (TF-3-nah, out-of-scope hier).
> User-Entscheid: „Tests reichen aktuell" → TF-2 abgeschlossen. **User committet selbst.**
> Idee geparkt: **Auto-Tuning-Tool** (Script findet Gains pro Gangart/Höhe selbst; Konzept
> durchgesprochen, §4-Plan bei Bedarf — nicht jetzt).

### TF-2-Post-Review

| Punkt | Status |
|---|---|
| Gyro-D (Vorzeichen kontert Rate / im Totband aktiv / im Clamp / Kd=0 Back-Compat) | OK (5 Unit-Tests) |
| Closed-Loop-Dämpfung (Schwingung klingt mit Kd ab) | OK (`test_gyro_d_damps_oscillation`, symplektischer Plant) |
| terrain: pitch = Residual (folgt Hang) / roll = roh (→0), per-Achse | OK (`test_terrain_mode_pitch_follows_slope_roll_to_zero`: roll stellt, pitch nicht) |
| horizontal-Modus erhalten (Voll-Leveln pitch→0) | OK (`test_horizontal_mode_levels_pitch`) |
| Gyro-Achsenraten erreichen den Controller | OK (`test_gyro_d_reaches_controller`) |
| Modus-String-Validierung + Live-Tuning (mode/kd) | OK (`test_leveling_mode_live_and_validation`) |
| **Slope-Schätzung auf `_LEVELING_NODE_STATES` (inkl. STOPPING) ausgerichtet** | ✅ **Self-Review-Fix:** TF-1 gatete nur STANDING/WALKING → im STOPPING wäre slope=0 → terrain-pitch fälschlich auf 0 gelevelt (Ruck beim Anhalten am Hang). Jetzt deckungsgleich mit dem Stellpfad. Strikt besser auch für TF-1 (Tip im STOPPING eh aus) |
| Snap-Init verhindert Stell-Sprung bei State-Wiedereintritt | OK (Slope snappt auf Messung → Residual 0 erster Tick → keine pitch-Korrektur) |
| Tick-Reihenfolge (Slope-Schätzung VOR _update_leveling) | OK (Residual nutzt die aktuelle Schätzung) |
| Stellpfad/Envelope unverändert (Korrekturen klein) | OK (keine θ-Tabelle/Tool; Clamp 10/4° + IKError-Fallback = Backstop) |
| **horizontal-Modus bekommt jetzt auch Gyro-D** (Kd-Default 0.03) | 🟡 minor: zusätzliche Dämpfung (harmlos/eher gut); für **exakte** Stufe-2-Reproduktion `leveling_kd:=0` |
| **Kd-Vorzeichen nicht validiert** (negativ = Anti-Dämpfung/instabil) | 🟡 konsistent mit kp/ki (Gains werden dem Tuner vertraut, keine Sign-Checks); Doku warnt |
| D differenziert → rausch-verstärkend | 🟡 Sim rauschfrei zeigt's nicht → auf HW `Kd` konservativ (D6: Sim=Logik, HW=Gains) |
| D vs. Slew (Dämpfungs-Bandbreite) | 🟡 `slew_max` als Stellknopf; Fallback „D am Slew vorbei" dokumentiert |
| **Totband > Wackel-Amplitude → P/I beim kleinen Wackeln inaktiv** | 🟡 **Sim-Befund (User):** Wackeln ±1–2° < Totband 1.5° → nur Gyro-D wirkt. Hebel = Totband ↓ + Kp/Kd ↑ (live); Defaults konservativ (HW). In Tuning-Doku aufnehmen |
| Quer-/Diagonal-Hang (roll→0 statt folgen) | 🟢 später — eigener Block **TF-Quer** (roll-Residual + cmd_vel-Richtung), dokumentiert (Plan §6) |
| Kante/Stufe (Plateau-Scheitel, 35°-Bordstein) | 🟢 Stufe 4 (Fußtaster), kein Balance-Problem |
| Nicht-Tripod „tripod-ruhig" unerreichbar (reaktiv) | 🟢 später — bräuchte aktive Gang-/Schwerpunkt-Stabilisierung (TF-3-nah); out-of-scope |
| **Sim-Verify (User): flacher Boden, alle Gangarten** | ✅ tripod wackelfrei (erwartet), wave ok, tetrapod/ripple ±1–2° gangsynchron; Dämpfung wirkt (begrenzt durch Totband); kein Freeze. „Tests reichen aktuell" → TF-2 abgeschlossen |

---

## Stufe 4 — Terrain-adaptiv (Fußkontakte)  🟡 in Arbeit

Umbrella: [`stage_4_terrain_adaptive_plan.md`](stage_4_terrain_adaptive_plan.md) (Methode **fixed-timing**
gewählt; free-gait als dokumentierte Alternative). Teil-Stufen: **S4-1 🟢** (Consumer+Verifikation) →
**S4-2 ⚪ (Plan fertig, Code offen)** (adaptiver Touchdown) → (S4-4/S4-5) → (S4-3) → S4-6.

> **➡️ NÄCHSTER SCHRITT (für neuen Chat): S4-2 implementieren.** Plan (Handoff-vollständig, inkl.
> S4-1-Befunde + Code-Anker + §4): [`stage_4b_adaptive_touchdown_plan.md`](stage_4b_adaptive_touchdown_plan.md).
> **Kern:** adaptiver Touchdown via **kontrollierter Senk-Rate** bis Kontakt (statt schneller
> Halbsinus). Engine-z-adaptiv (x,y unverändert), per-Bein `touchdown_z`, Fallback nominal,
> Contact-Live-Guard. §4-Workflow: Plan ist geschrieben → **User-Freigabe einholen** → Code → Test
> → Self-Review. §4-Vorschläge im Plan §4 (Senk-Fenster 0.6/0.3, max_depth 0.02, Default false).

### S4-1 — Fußkontakt-Consumer + Verifikation

Plan: [`stage_4a_contact_verify_plan.md`](stage_4a_contact_verify_plan.md) (§4-Freigabe erteilt).
**Kein Verhaltens-Change** — nur Consumer + quantitative Messung (de-risk vor S4-2).

```
S4-1:
- [x] S4-1.1 gait_node: 6 Subscriber /leg_<n>/foot_contact (Bool) + State-Cache (graceful ohne Pipeline)  [_make_foot_contact_cb, QoS 10]
- [x] S4-1.2 Engine read-only leg_gait_states() (per-Bein is_swing + local_phase), kein Verhaltens-Change  [WALKING echte Phase, sonst alle (False,0)]
- [x] S4-1.3 ContactDiagnostic (ROS-frei): Flanken/Latenz/Apex-Fehlkontakt/Stance-Aussetzer/Quote  [contact_diagnostic.py]
- [x] S4-1.4 Debug-Log (throttled 1 Hz) + /foot_contacts-Topic (Float64MultiArray 0/1); Param foot_contact_debug_enable (live)
- [x] S4-1.5 Unit-Tests (ContactDiagnostic 9, leg_gait_states 3) + Node-Smoke 5  [+17]
- [x] S4-1.6 colcon test + Lint grün  [669 Tests, 0 Fehler; gait 272 / kinematics 42; flake8/pep257 grün]
- [x] S4-1.7 README/Konzept (hexapod_gait: Kontakt-Consumer + Diagnose; Pipeline-Verweis)
- [x] S4-1.8 Test-Doku stage_4a_contact_verify_test_commands.md + **Sim-Verify durch User** (inkl. Mess-Zusatz a: act_z vs cmd_z)  [Befund unten — Signal verifiziert]
- [x] S4-1.9 kritische Self-Review-Tabelle  [unten]
```

> **§4-Entscheide (User):** Debug = Log **+** `/foot_contacts`-Topic · Latenz-Schwelle steigende
> Flanke ≤ 2 Ticks + keine Apex-Fehlkontakte · Matrix flach+Hang × cycle {2.0,1.0} × step {0.04,0.06}
> · Hebel 2/3 erlaubt, Hebel 4 nur Notfall (Umbrella §3). **User committet selbst.**
>
> **S4-1 🟢 fertig (Sim-verifiziert).** Mess-Zusatz (a) hat den ~13-Tick-Offset als reinen
> Ausführungs-Lag (kommandiert vs. tatsächlich) entlarvt — Sensor korrekt. **S4-2 freigegeben**
> (adaptiver Touchdown mit kontrollierter Senk-Rate). **User committet selbst.**

### S4-1-Post-Review

| Punkt | Status |
|---|---|
| ContactDiagnostic (Latenz/Apex/Gap/Missed/Quote) | OK (9 Unit-Tests; Latenz 0 + 1 + missed + apex + gap gepinnt) |
| leg_gait_states WALKING vs STANDING/Transition | OK (3 Tests: Formel-Konsistenz + Querprobe gegen Target-z) |
| Node-Wiring (6 Subs, Cache, Diag-Feed, Publish, Param) | OK (6 Node-Smoke-Tests inkl. WALKING-Feed + Reset) |
| **Kein Verhaltens-Change** | OK (`_update_foot_contacts` liest/cacht/publisht/loggt — modifiziert Engine/Targets nicht) |
| Tick-Reihenfolge (gleicher `t` wie compute) | OK (nach `_update_leveling`, vor `compute_joint_angles(t)`) |
| Graceful ohne Pipeline | OK (keine Topics → Cache False; Diag meldet korrekt gap/missed, kein Crash) |
| QoS Match (Sub 10 reliable = Publisher 10) | OK |
| Reset bei `debug_enable` false→true | OK (frisches Mess-Fenster pro Konfig; Test); intendiert, dokumentiert |
| leg_gait_states-Formel dupliziert `_compute_walking_targets` | 🟡 minor: read-only, klar dokumentiert; bewusst nicht den Hot-Path refactort |
| Latenz vs. gap-Fenster überlappen in früher Stance | 🟡 minor: bei hoher Latenz zählt der frühe-Stance-Bereich (0.2–0.3) evtl. als gap — verwandte Metriken, akzeptiert |
| `/foot_contacts` publisht jeden Tick (auch ohne Consumer) | 🟢 harmlos (kleine Msg); fürs UI/echo nützlich |
| Diag nur in WALKING (STOPPING/STANDING ignoriert) | 🟢 gewollt — nur stetiger Lauf wird gemessen |
| Apex/Stance-Fenster (0.2–0.8) hardcoded | 🟢 ausreichend; bei Bedarf später Param |
| **Sim-Verify (User) + Mess-Zusatz (a): Signal verifiziert** | ✅ **Befund:** Sensor **zuverlässig + korrekt** (`miss 0`; feuert exakt bei Fußkugel-Bodenberührung — `act_z` bei RISE = `bh + Kugelradius 8mm`). Die ~13-Tick-„Latenz" = **reiner Ausführungs-Lag** (kommandiert vs. tatsächlich, Sim): der schnelle Halbsinus-Aufsetzer wird vom JTC ~8.8mm hinterhergetrackt. **Kein Sensor-/Pipeline-Defekt.** |
| **Konsequenz für S4-2 (datenbelegt)** | adaptiver Touchdown mit **kontrollierter, langsamer Senk-Rate** in der späten Schwungphase → tatsächlicher Fuß trackt eng → Kontakt feuert prompt. Mess-Zusatz `_debug_leg1_contact` (act_z vs cmd_z via FK aus /joint_states) bleibt als Debug |

---

## Stufen 3b–4 — ⚪ offen (vorausgeplant, Implementierung nach §4-Freigabe)

Pläne geschrieben (Logik/Tests/Design/offene Punkte) zum Nachlesen; Code +
Test-Markdown pro Stufe nach Freigabe:

- **Stufe 2 — Statisches Leveling:** [`stage_2_static_leveling_plan.md`](stage_2_static_leveling_plan.md)
  — `BalanceController` + Rotations-Stellpfad + Clamp + Schräg-Welten. Risiken 1/2/3/6 scharf.
- **Stufe 3 — Leveling im Laufen + Hang-Parameter:** [`stage_3_walking_slope_plan.md`](discarded/stage_3_walking_slope_plan.md)
  — Gyro-Dämpfung, θ→Parameter-Familie (Weg A), Gangart-Auto-Switch. **A/B-Entscheidung mit Daten.**
- **Stufe 4 — Terrain (Weg B + Fußkontakte):** [`stage_4_terrain_adaptive_plan.md`](stage_4_terrain_adaptive_plan.md)
  — adaptiver Touchdown, Plausibilitäts-Fail-Safe. Forschungs-grade, braucht E2-Taster.
```
