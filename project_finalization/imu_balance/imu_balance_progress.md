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
> Verifikation) 🟢 fertig** (Signal verifiziert). **S4-2 (adaptiver Touchdown, Option A) 🟢
> Sim-verifiziert.** ⚠️ Der Erst-Entwurf war closed-loop-instabil (Körper-Anker verloren + ~13-Tick-
> Lag → Ducken/Rückwärts); **Option A** (nominaler Anker bei `body_height`, downward-only, Stance-Gate
> 0.35) ist **Sim-bestätigt stabil**: `cmd_z` Stance −0.0800, am konvexen Scheitel geführt bis
> −0.0862 (~6 mm Nachreichen), `dz` 8–14 mm, kein Absacken. Wackeln = Tripod-CoG (kein Touchdown-
> Effekt). **S4-6 (Stufen- + Graben-Welt) 🟢 Sim-verifiziert** (Graben: `cmd_z` −0.105 vs −0.080,
> Roll ±1.3° vs ±2.7°). **S4-4 (Slip/Kontaktverlust → Freeze) 🟡 Code+Tests+Doku fertig, Sim-Verify
> offen:** `SupportMonitor` (ROS-frei, wie TipMonitor) — Stance-Bein ohne Kontakt nach Grace →
> Freeze (= Stufe 1); `cliff_depth` 0.03 = Grenze folgbares Terrain ↔ Abgrund (→ `engine.cliff_probe_depth`);
> Default `slip_detection_enable` false. **🟢 Sim-verifiziert (nach Leaky-Fix):** Fall 1 (sauber über
> Kante) **und** Fall 2 (Roboter kippt, intermittierender Kontakt) freezen jetzt beide; flach kein
> Fehlalarm. **➡️ NÄCHSTER SCHRITT: S4-5** (Plausibilität/Sensor-Fault-Fail-Safe = letzter Stufe-4-
> Baustein) — **Plan geschrieben + §4-freigegeben** ([stage_4e](stage_4e_plausibility_plan.md):
> stuck-on+dead, ignorieren+warnen, latched, Inject-Hook), Implementierung steht aus. Tests **715
> grün** (+21 S4-4). **User committet selbst.** ⏸️
> Zurückgestellt: ramp_walk-Standup-Regression [[project_ramp_walk_standup_joint_space_regression]].
> **⏸️ Zurückgestellt (eigene Aufgabe, NICHT S4-2):** `ramp_walk` steht **joint-space statt
> kartesisch** auf (alle 6 Füße schleifen gleichzeitig nach innen, HW-Risiko) — Verdacht:
> Auto-Standup-Trigger nimmt `start_ramp()` statt `start_cartesian_standup()` trotz
> `standup_mode=cartesian`. Memory [[project_ramp_walk_standup_joint_space_regression]].

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
**S4-2 🟢 Sim-verifiziert** (adaptiver Touchdown, Option A) → **S4-6 (vorgezogen, als Nächstes)** → (S4-4/S4-5) → (S4-3).

> **➡️ NÄCHSTER SCHRITT: S4-6 (vorgezogen) — Mini-Stufen-/Knick-Welt.** S4-2 ist Sim-verifiziert
> stabil + selektiv (Befund im S4-2-Block unten); der sichtbare Payoff braucht einen Höhensprung
> ≫ 6 mm (auf dem sanften 8°-Hang verlangt das Terrain nur ~6 mm). Daher zuerst eine echte Stufen-/
> Knick-SDF bauen (eigene maßstabsgerechte Welt, z.B. 2–3 cm Kante), dann S4-2 dort demonstrieren.
> Slip/Plausibilität (S4-4/S4-5) danach. **User committet selbst.**

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

### S4-2 — Adaptiver Touchdown (Option A: downward-only, lag-Gate)  🟢 Sim-verifiziert (stabil + selektives Nachreichen)

Plan: [`stage_4b_adaptive_touchdown_plan.md`](stage_4b_adaptive_touchdown_plan.md) (§4-Freigabe erteilt) ·
Test-Doku: [`stage_4b_adaptive_touchdown_test_commands.md`](stage_4b_adaptive_touchdown_test_commands.md)

> **⚠️ REDESIGN nach Sim (Option A).** Der erste Entwurf (Senkung vom Schwung-Apex bis Floor, Freeze
> an der Kontakthöhe) war in der Sim **closed-loop-instabil** (User-Befund T1.B): er ersetzte die
> feste Stance-Höhe (= Körper-Anker) durch „Fuß = Kontakthöhe"; der ~13-Tick-Kontakt-Lag (NICHT
> geschwindigkeitsabhängig — `lat 14–16`, `dz 22–33 mm`, `cmd_z` bis Floor −0.10 auf flachem Boden)
> ließ den Fuß über den echten Boden hinausreichen → Körper-Drift → **Ducken + Rückwärtslaufen**
> (phasenlagen-abhängig). **Option A (umgesetzt):** nominaler Schwung+Stance bleiben (Anker bei
> `body_height`), das Adaptive senkt **nur unter `body_height`** und **erst ab einem Stance-Gate**
> (`touchdown_probe_start_stance_phase` 0.35), wenn bis dahin kein Kontakt kam (Gate wartet den Lag
> ab). Flacher Boden = nominal = stabil; nur tieferer Boden (Knick/Loch) löst Nachreichen aus.
> Aufgegeben (waren die Instabilitätsquelle): „Buckel→höher" + „flat-Latenz senken".
>
> **§4 (Option A):** `touchdown_probe_start_stance_phase` **0.35** / `touchdown_search_end_stance_phase`
> **0.6** / `touchdown_max_extra_depth` **0.02** (Floor envelope-GREEN mittel −0.100 / hoch −0.120) ·
> Default `adaptive_touchdown_enable` **false** · **Contact-Live-Guard = Topic-Frische** (< 0.5 s) ·
> Walk-Start: Stance-Beine auf `body_height` vorverankert. **User committet selbst.**

```
S4-2:
- [x] S4-2.1 Engine: set_foot_contacts() + per-Bein touchdown_z/_td_searched + adaptive-Params; z-adaptiv NUR in _compute_walking_targets (x,y unverändert)
- [x] S4-2.2 Senk-Logik (Option A, ROS-frei): downward-only ab Stance-Gate, nominaler Anker bei body_height, Reset im Schwung, Walk-Start-Vorverankerung  [Redesign nach Sim, s. oben]
- [x] S4-2.3 gait_node: Kontakt-States an Engine durchreichen + adaptive_touchdown_enable (Default false, live) + Contact-Live-Guard (Pipeline tot/stale → adaptiv aus)
- [x] S4-2.4 Params: adaptive_touchdown_enable, touchdown_probe_start_stance_phase, touchdown_search_end_stance_phase, touchdown_max_extra_depth (alle live, validiert inkl. probe<search, dokumentiert)
- [x] S4-2.5 Unit-Tests (Senk-Logik, **Anti-Drift flach**, x,y unverändert, Fallback=nominal, Envelope-Floor, Walk-Start-Vorverankerung) + Node-Tests  [+25: 11 Engine + 14 Node]
- [x] S4-2.6 colcon test + Lint grün  [694 colcon-Aggregat, 0 Fehler; gait 325 / kinematics 43 pytest; flake8/pep257 grün]
- [x] S4-2.7 README/Konzept (adaptiver Touchdown, Senk-Fenster, per-Fuß-Höhe, Fallback+Guard, Params)
- [x] S4-2.8 Test-Doku stage_4b_adaptive_touchdown_test_commands.md (flach: **Stabilität** A/B; ramp-Knick: reicht nach + kommt drüber)  [**Sim-Verify ✅ — Befund unten**]
- [x] S4-2.9 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)  [unten]
```

> **Sim-Verify-Befund (User, ramp 8° + T3-Tuning, `_debug_leg1` + foot_contact-Diagnose):**
> 1. **Instabilität behoben (Kern-Ergebnis).** `cmd_z` in der Stance bleibt kontrolliert: flach/sanfter
>    Hang exakt **−0.0800**, nur am **konvexen Plateau-Scheitel** geführt bis **−0.0862** (~6 mm
>    Nachreichen) und zurück. `dz` durchweg gesund **8–14 mm**. **Kein** Floor-Durchsacken, **kein**
>    Wegsacken/Rückwärtslaufen mehr (vs. Erst-Entwurf). Option A trägt.
> 2. **Selektives Nachreichen bestätigt.** Obere Kante (konvex, pitch −8°→0°) → `cmd_z` reicht
>    nach unten; untere/konkave Ecke (pitch 0°→−8°) **und** flacher Boden → `cmd_z` bleibt −0.0800
>    (korrekt nichts). Ohne `adaptive_touchdown_enable` bleibt `cmd_z` auch am Scheitel −0.0800.
> 3. **„Mit/ohne sieht ähnlich aus" — erklärt:** der Nachreich-Hub ist auf dem sanften 8°-Scheitel
>    nur ~6 mm (Terrain verlangt nicht mehr); das sichtbare Bild dominiert das **Roll-Wackeln ±1–2°**,
>    = prinzipbedingtes **Tripod-CoG-Wackeln** ([[project_nontripod_gait_wobble]]), **kein** Touchdown-
>    Effekt (mit/ohne identisch). **Sichtbarer Payoff braucht eine Stufe/scharfen Knick → S4-6.**
> 4. **Diagnose-Hinweis:** hohe `apex`-Zähler auf dem Hang = kumulatives **Artefakt** (`contact_timeout`
>    0.1 s hält das Bool ~5 Ticks in den Schwung → zählt als Apex-Kontakt); **`miss 0`** überall →
>    kein echter verpasster Touchdown, kein Regelproblem.
>
> **➡️ Nächster Schritt für sichtbaren Nutzen: S4-6** (Mini-Stufen-/Knick-Welt, Höhensprung ≫ 6 mm).

### S4-2-Post-Review (Option A)

| Punkt | Status |
|---|---|
| **Closed-loop-Körper-Drift (Erst-Entwurf) — Sim-Befund** | ✅ **Bug gefunden + behoben (Redesign Option A).** Erst-Entwurf verlor den Körper-Anker (Fuß=Kontakthöhe) → mit ~13-Tick-Lag Über-Reichen → Ducken/Rückwärts. Option A: Anker bei `body_height`, downward-only, Stance-Gate |
| **Sim-Verify Option A (ramp 8°)** | ✅ **stabil + selektives Nachreichen** (Befund-Block oben): `cmd_z` Stance −0.0800, am konvexen Scheitel bis −0.0862 (~6 mm), `dz` 8–14 mm, `miss 0`. Payoff-Sichtbarkeit braucht Stufe/Knick → S4-6 |
| **Anti-Drift flach** (Stance-Fuß nie unter `body_height` bei Kontakt) | OK (`test_flat_ground_no_body_drift`, 200 Ticks × 6 Beine — die Regression, die der Erst-Entwurf gerissen hätte) |
| Pre-Gate Kontakt → bei `body_height` verankern (kein Tieferreichen) | OK (`test_stance_pregate_contact_anchors_body_height`) |
| Probe nur **unter** `body_height`, linear (konstante Senk-Geschw.) | OK (`test_probe_descends_linearly_below_body_height`, `z < body_height`) |
| Kontakt im Probe → tiefer einfrieren (echte Terrain-Höhe, Knick/Loch) | OK (`test_contact_during_probe_freezes_below_body_height`) |
| x,y bit-identisch zu nominal (nur z adaptiv) | OK (`test_xy_unchanged…`, 200 Ticks × 6 Beine) |
| Fallback adaptiv-aus = exakt nominal (keine State-Mutation) | OK (`test_fallback_disabled_is_exact…`) |
| Tiefster Touchdown (Floor) in-limit, kein IKError-Freeze | OK (offline GREEN bh−0.02 alle 4 Szenarien + voller-Cycle-Test) |
| Contact-Live-Guard (tot/stale/param-aus → adaptiv aus) | OK (4 Node-Tests; Topic-Frische statt letztes-True) |
| Walk-Start: Stance-Beine auf `body_height` vorverankert (kein 1-Cycle-Probe) | OK (`test_walking_entry_preanchors_stance_legs`) |
| Probe-Gate muss > Kontakt-Lag in Stance-Phasen sein (sonst flat-Drift) | 🟡 cycle_time-abhängig: 0.35 hat Marge bei `cycle_time=2.0` (Lag ≈ 0.27); bei schnellerem Cycle `probe_start` hochsetzen (Test-Doku-Hinweis) |
| „Buckel→höher" + „flat-Latenz senken" aufgegeben | 🟢 bewusst (waren die Instabilitätsquelle); Buckel = Open-Loop (Fuß bei `body_height`) |
| STOPPING droppt Terrain-Höhen (settle zu `body_height`) | 🟢 kurzer Übergang, eigener Pfad — bewusst (adaptiv nur WALKING) |
| Kombination mit Leveling (rotiert adaptive-z downstream) | 🟢 später: geometrisch sauber; Stage 4 zunächst isoliert (`leveling_enable:=false`) |
| Param-Validierung (Stance-Phasen + `probe_start < search_end`, Tiefe ≥0) atomic | OK (`test_invalid_params_rejected` + `test_probe_must_be_below_search_end_rejected`) |

### S4-6 — Stufen- + Graben-Welt (Demo des adaptiven Touchdowns)  🟢 Sim-verifiziert (Graben zeigt den per-Fuß-Reach)

Plan: [`stage_4c_step_worlds_plan.md`](stage_4c_step_worlds_plan.md) (§4-Freigabe erteilt) ·
Test-Doku: [`stage_4c_step_worlds_test_commands.md`](stage_4c_step_worlds_test_commands.md)

> **§4-Entscheide (User):** scharfe **Stufe ab** zuerst · Höhen **2 cm** (Payoff, Demo-Marge
> `max_extra_depth:=0.025`) **+ 4 cm** (fixed-timing-Grenze) · **Stufe-auf-Gegenprobe** via negativem
> `step_drop` · Geometrie obere Box + `ground_plane` · `step.sdf.xacro`/`step.launch.py`/
> `step_walk.launch.py` (analog ramp) · eine Stufe (Treppe später). **Kein Engine-/Node-Code.**
> **User committet selbst.**

```
S4-6:
- [x] S4-6.1 step.sdf.xacro (obere Box @ +step_drop + ground_plane, scharfe Kante; signiert +=ab/−=auf) + trench.sdf.xacro (2 Plattformen + tieferer ground_plane = Graben)
- [x] S4-6.2 step.launch.py + step_walk.launch.py + trench.launch.py + trench_walk.launch.py (Ein-Befehl, leveling_enable Default false)
- [x] S4-6.3 gz sdf --check Valid (step 0.02/0.04/−0.02; trench 0.02) + alle Launches konstruieren  [Geometrie verifiziert]
- [x] S4-6.4 install (Directory-Glob worlds/+launch/) + colcon build grün
- [x] S4-6.5 Test-Doku stage_4c_step_worlds_test_commands.md (T1–T3 Stufe + **T4 Graben = die klare Demo**, exakte „was-du-siehst"-Beschreibung)  [**Sim-Verify ✅ Stufe + Graben (Befund unten)**]
- [x] S4-6.6 Doku-Querverweise (Umbrella S4-6, ai_navigation Welten-Eintrag, Memory)
- [x] S4-6.7 kritische Self-Review-Tabelle  [unten]
```

> **Sim-Verify-Befund Stufe (User, 2 cm ab, A/B):** funktional ✅ — Option A stabil (`cmd_z`
> verankert, `miss 0`, `dz` 8–12 mm), reicht am Kanten-Schritt nach (`cmd_z −0.0833`). **ABER als
> Demo schwach:** eine **vollbreite Stufe ab** wird fast komplett vom Körper-**Pitch** geschluckt
> (Körper kippt ~5° = atan(0.02/0.2) über die Kante → Vorderbeine erreichen den unteren Boden von
> selbst, Touchdown-Anteil nur ~3 mm). **Konsequenz: Graben-Welt `trench.sdf.xacro` ergänzt** —
> schmaler Graben quer zur Laufrichtung, 4 Beine auf den Plattformen halten den Körper eben → nur
> das einzelne Bein reicht runter → per-Fuß-Reach isoliert sichtbar (`cmd_z` ~−0.10). **Graben-Sim-
> Verify durch User offen** ([Test-Doku T4](stage_4c_step_worlds_test_commands.md)).

### S4-6-Post-Review

| Punkt | Status |
|---|---|
| `gz sdf --check` Valid (3 Stufenwerte) | OK (Valid für 0.02/0.04/−0.02) |
| Geometrie: Box-Oberkante = `|step_drop|`, ab=Start-Seite / auf=Ziel-Seite | OK (Pose verifiziert: ab x∈[−2,0] top 0.02/0.04; auf x∈[0,2] top 0.02) |
| IMU welt-referenziert → flach spawnen | OK (sim.launch Default flach; [[project_gz_imu_spawn_referenced]]) |
| Spawn-Höhe richtet sich nach Start-Fläche (ab=Box-Top, auf=ground) | OK (`spawn_z = start_z + clearance` im Launch) |
| Box überlappt `ground_plane` (beide static) | 🟢 unkritisch (keine Dynamik; höhere Fläche trägt) |
| Kein Engine-/Node-Code (reine Welt) | OK (nur SDF/Launch; S4-2-Logik unverändert) |
| **2-cm-Demo-Marge knapp** (2 cm Stufe vs. 2 cm Reach) | 🟡 Test-Doku setzt `max_extra_depth:=0.025` für die Demo (envelope-GREEN bis −0.12); Default-Param bleibt 0.02 |
| 4-cm-Stufe = fixed-timing-Grenze (Fuß am Floor, kein Boden) | 🟢 gewollt + dokumentiert (motiviert S4-3) |
| Launches installiert (symlink) + konstruieren | OK (`--show-args` grün, share-Symlinks vorhanden) |
| **Vollbreit-Stufe = schwache Demo (Pitch schluckt sie)** | ✅ **Sim-Befund + behoben:** Stufe ab → Körper pitcht ~5° → Touchdown-Anteil nur ~3 mm. **Graben-Welt ergänzt** (Pitch-frei, per-Fuß-Reach ~2 cm) |
| `trench.sdf.xacro` Geometrie (2 Plattformen z=0 + ground_plane z=−depth, Lücke=Graben) | OK (gz valid; near x∈[−2.05,−0.05] / far x∈[0.05,2.05] / Graben 0.10 breit / Boden −0.02) |
| Graben schmal genug → Stütz-Beine halten Körper eben (kein Pitch-Cheat) | 🟡 `trench_width` 0.10 Default — bei zu breit kippt der Körper (wie Stufe), bei zu schmal trifft kein Bein; live tunbar |
| **Sim-Verify Graben (T4) ✅** | **per-Fuß-Reach klar belegt:** AN `cmd_z` bis **−0.105** über dem Graben (`act_z`−0.088, ~2.5 cm) vs AUS `−0.080` durchgehend; Roll **±1.3° (AN) vs ±2.7° (AUS)** (Körper ~2× ruhiger); `miss 0` |
| **`miss`-Vorhersage korrigiert** | 🟡 `miss` bleibt in **beiden** 0 (10-cm-Graben → Füße straddeln teils) — Signatur = **Reach + halbierter Roll**, NICHT ein `miss`-Sprung (Test-Doku korrigiert) |
| Stufe (T1) als Demo | 🟢 funktional-ok aber subtil (~3 mm, Pitch schluckt sie) — bleibt als funktionaler Beleg + Grenze (4 cm) + Gegenprobe (auf); der **Graben ist die Demo** |

### S4-4 — Slip / Kontaktverlust → Freeze  🟢 Sim-verifiziert (nach Leaky-Fix)

Plan: [`stage_4d_slip_detection_plan.md`](stage_4d_slip_detection_plan.md) (§4-Freigabe erteilt) ·
Test-Doku: [`stage_4d_slip_detection_test_commands.md`](stage_4d_slip_detection_test_commands.md)

> **§4-Entscheide (User):** `cliff_depth` **0.03 (mittel)**, live tunbar (später ggf. erhöhen) ·
> Reaktion = **nur Freeze** (v1, wie Stufe 1; Bein-Zurückziehen = S4-4b später) · `min_lost_legs`
> **1** (an gerader Kante 1 Bein/Tripod → früh stoppen) · grace 0.6 / debounce 8 (> contact_timeout).
> **User committet selbst.**

```
S4-4:
- [x] S4-4.1 SupportMonitor (ROS-frei): per-Bein Entprellung + Latch + reset; Halt-Verlust = Stance+kein-Kontakt nach Grace
- [x] S4-4.2 Engine: cliff_probe_depth-Attribut → Floor = body_height − max(max_extra_depth, cliff_probe_depth)
- [x] S4-4.3 gait_node: SupportMonitor-Wiring (WALKING-Gating, reset sonst) + Freeze (steigende Flanke, _trigger_safety_freeze, kein Publish) + cliff_probe_depth setzen
- [x] S4-4.4 Params: slip_detection_enable (false), cliff_depth (0.03), slip_debounce_ticks (8), slip_min_lost_legs (1), slip_grace_stance_phase (0.6) — live, validiert, Monitor-Rebuild
- [x] S4-4.5 Unit-Tests (Halt-Verlust, Grace, Schwung-Reset, min_legs+Latch, Entprellung, **Leaky**) + Engine + Node-Smoke  [+21: 9 SupportMonitor + 11 Node + 1 Engine]
- [x] S4-4.6 colcon test + Lint grün  [715 colcon-Aggregat, 0 Fehler; flake8/pep257 grün]
- [x] S4-4.7 README/Konzept (Slip/Kante → Freeze, cliff_depth-Grenze, Entprellung vs contact_timeout, Params)
- [x] S4-4.8 Test-Doku stage_4d_slip_detection_test_commands.md (Kante step_drop:=0.06 A/B + flach kein Fehlalarm)  [**Sim-Verify durch User offen**]
- [x] S4-4.9 kritische Self-Review-Tabelle  [unten]
```

### S4-4-Post-Review

| Punkt | Status |
|---|---|
| SupportMonitor (Entprellung/Latch/Grace/min_legs) | OK (8 Unit-Tests) |
| Grace deckt JTC-Lag → kein Fehlalarm flach | OK (`test_grace…` + `test_no_freeze_when_supported`; Grace 0.6 > Lag-Phase 0.27) |
| Debounce > contact_timeout (5 Ticks) | OK (`test_debounce_exceeds_contact_timeout`; 8 > 5) |
| Freeze gelatcht + einmalig + Recovery via State-Wechsel | OK (`test_latch…`; `_update_support` reset bei nicht-WALKING) |
| `cliff_depth` → `engine.cliff_probe_depth` (tieferer Floor) | OK (Engine `test_cliff_probe_depth_overrides_floor` + Node) |
| Gating WALKING-only | OK (`test_resets_when_not_walking`) |
| Reaktion = `_trigger_safety_freeze` (= Stufe 1) | OK (wiederverwendet, kein neuer Pfad) |
| `min_legs=1` Fehl-Trigger auf Terrain/Graben? | 🟢 nein — Abfall ≤ cliff_depth findet Kontakt → gestützt; nur > cliff_depth freezt |
| **`slip_grace_stance_phase` cycle_time-abhängig** | 🟡 vormerken (wie S4-2 `probe_start`); bei schnellerem Cycle hochsetzen (live, Doku-Hinweis) |
| **Freeze-Latenz ≈ grace+debounce (~0.76 s → ~3 cm Weg über Kante)** | 🟡 minor: bei cycle 2.0 + v 0.04; `debounce`/`grace` runter für schnelleren Stopp; v1 ok |
| Slip adaptiv-unabhängig (Kern = no-contact-past-grace) | OK (cliff_probe nur Zusatz-Reach) |
| Bein-Zurückziehen / Sensor-Fault | 🟢 später: S4-4b (Zurückziehen) / S4-5 (Plausibilität) — v1 = nur Freeze |
| **Sim-Verify (User): Leaky-Fix bestätigt ✅** | 1. Runde inkonsistent (Fall 1 froze, Fall 2 kippte ohne Freeze — intermittierender Kontakt setzte den consecutive-Zähler zurück). **Leaky-Zähler** (Kontakt = −1) **re-verifiziert: auch der kippende Fall freezt jetzt.** Fall 1 + Fall 2 beide → Freeze; flach kein Fehlalarm |
| **Residual: sehr schnelles Kippen kann Debounce überholen** | 🟡 Leaky braucht ~Debounce Ticks Akkumulation; bei extrem schnellem Tip Stufe-1-Tip als Backstop / Kombination mit Tip-Winkel = spätere Robustheit (S4-5-nah) |

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
