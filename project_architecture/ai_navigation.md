# AI-Navigation — „Ich ändere X, wo schaue ich, was muss ich nachziehen?"

> **Zuerst lesen bei JEDER Änderung.** Diese Datei kodiert die Stolpersteine, über die
> wir mehrfach gefallen sind. Sie ergänzt (nicht ersetzt) `CLAUDE.md` (Arbeitsweise) +
> die Memory-Einträge. Architektur-Kontext: [`architecture.md`](architecture.md).

## 0. Goldene Regeln (immer)
1. **Zwei Limit-Quellen** — URDF (3 Dateien) **und** `config.py` müssen synchron sein
   (Cross-Check `test_config.py`). [[project_two_joint_limit_sources]]
2. **Sim ist lenient** — die Phase-5-Sim-IK prüft Limits nicht; ein Pose-Fehler, der in
   Sim „grün" ist, **freezt auf HW**. Daher jede Pose mit den **URDF-Limits** + den
   Envelope-Tools validieren. [[feedback_validate_hardware_hypothesis_via_code]]
3. **Alle Konsumenten nachvalidieren** — `gait_node` (parst URDF live), `reachability_viz`,
   `walking_envelope_check`, `standup_envelope_check` lesen die Limits/Geometrie unabhängig.
   Nach einer Änderung **alle** prüfen, nicht nur Build/xacro-Parse. [[feedback_urdf_refactor_full_smoke]]
4. **Tests grün + Lint grün vor Commit** (`colcon test`, `ament_flake8`/`ament_pep257`).
   User committet selbst. [[feedback_user_does_commits]]
5. **Sim VOR Hardware** verifizieren (RViz + Gazebo), dann aufgebockt, dann Boden.

## 1. Änderungs-Landkarte (X → Dateien → Validierung)

### Joint-Limit ändern (z.B. Tibia-Beuge)
- **Dateien:** `hexapod_physical_properties.xacro` (Property) · `hexapod.urdf.xacro` (6×) ·
  `hexapod.ros2_control.xacro` (6×) · `config.py` (`_*_LIMITS`) · `servo_mapping.yaml`
  (Beuge-/Streck-Puls-Bound: `pulse = pulse_zero ∓ 425·limit`, in `[500,2500]`).
- **Validieren:** generierte URDF prüfen (`xacro …`) · `colcon test hexapod_kinematics`
  (`test_config`) + `hexapod_hardware` (Calibration-Roundtrip) · `standup_envelope_check`
  + `walking_envelope_check` grün · Sim+RViz-Smoke. (Vorbild: Phase 13 Stage 1 Teil 2.1.)

### Geometrie ändern (Bein-Längen, Body-Maße) — ⚠️ großer Rattenschwanz
- **Dateien:** `physical_properties.xacro` + ggf. Meshes + `config.py` (`_L_*`, body-Maße).
- **Folgen:** IK/FK, Reachability, **Re-Kalibrierung** der betroffenen Servos, alle Presets,
  Stand-/Walk-Posen neu validieren. Nicht ohne Modell-Rechnung + bewusste Freigabe.
  (Geometrie-TABU-nah.)

### Servo getauscht / neu kalibriert
- **Dateien:** `servo_mapping.yaml` (Pin: `pulse_min/zero/max`, `direction`).
- **Validieren:** Calibration-Roundtrip-Test · rad=0 visuell gerade (HW=RViz) · Sweep ohne
  Freeze. Detaillierter Workflow: [`change_workflows.md`](change_workflows.md) + `docs/01_hardware_change_workflow.md`.

### Gait-Parameter tunen (radial, body_height, step_length/height, cycle …)
- **Wo:** ein **Preset** in `hexapod_gait/config/presets/*.yaml` (bevorzugt) ODER
  `gait.launch.py`-Defaults. Live-Tuning via `ros2 param set /gait_node …` (manche
  `standing_only`!).
- **Validieren:** `walking_envelope_check recommend/check` (nutzt URDF-Limits live) +
  `standup_envelope_check` für den Aufsteh-Pfad (eigene Pose!). **Beide separat** — eine
  Walk-Pose kann gehen, der Standup-Pfad dorthin aber nicht (Femur-90°-Befund 2.3).
- **Constraint-Fallen:** `body_height` fp_range-Floor = −0.110 (leg_changes/S5); `body_height_min ≤ body_height ≤ body_height_max`; `standing_only`-Params nur im STANDING setzbar.

### Neue Gangart
- **Wo:** `gait_patterns.py` — neuer `GaitPattern(phase_offset_per_leg, swing_duty)` +
  Eintrag in `GAIT_PRESETS`. Tripod-Gruppen-Konvention: {1,3,5}/{2,4,6}.
- **Validieren:** Engine-/Walking-Tests, Envelope, Sim.

### Teleop-Mapping / neue Controller-Funktion
- **Dateien:** `hexapod_teleop/config/ps4_usb.yaml` (Indizes/Skalen) · `joy_to_twist.py` (Logik).
- **Falle:** `joy_to_twist` publisht beim Start **einmalig** `/cmd_body_height = body_height_init`
  → muss == Gait-`body_height` sein, sonst sackt der Stand ab. Bei Höhen-Änderung nachziehen.
- **Live-Tuning der Tempo-Scales (TLS):** `linear_x_scale`/`linear_y_scale`/`angular_z_scale`/
  `slow_factor`/`deadzone` sind **live** per `ros2 param set /joy_to_twist …` verstellbar
  (`_on_param_change`, validate-then-apply: Scales ≥ 0, slow_factor ∈ [0,1], deadzone ∈ [0,1)).
  Die **strukturellen** Params (`axis_*`/`*_button`/`sign_*`) bleiben **Start-only** (im Hot-Path gilt
  der Startwert). Wer eine neue *live*-Tuning-Größe ergänzt, muss sie in `_on_param_change` (validate +
  apply) eintragen — sonst wirkt der `param set` nicht (das war der ursprüngliche Bug: alle Scales nur
  beim Start gelesen). **Plan/Tests:** `project_finalization/imu_balance/teleop_live_scales_plan.md`.
- **Validieren:** `colcon test hexapod_teleop` (`test_live_scales` — live-Update je Param, negativ/Range
  abgelehnt, struktureller Param kein Crash, atomarer Reject).

### Standup / Reposition / Zwei-Phasen-Logik
- **Wo:** `gait_engine.py` (States `CARTESIAN_STANDUP`/`REPOSITION`, `start_*`, `_compute_*`).
  Params: `standup_radial_distance` (breit, touchdown-sicher), `radial_distance` (Walk),
  `reposition_cycle_time`. **Engine wertneutral** — Pose-Zahlen leben in Config/Preset.
- **Falle:** cmd_vel muss in jedem neuen Aufsteh-/Reposition-State ignoriert werden
  (sonst kippt es fälschlich auf WALKING) — siehe `set_command`-Guard.

### Stance-Modi (3 Lauf-Höhen, Stage 1) ändern
- **Voll-Doku:** [`../project_finalization/stance_modes_plan.md`](../project_finalization/stance_modes_plan.md).
- **Wo:** `gait_node.py` — Tabelle `_STANCE_MODES` (name, radial, body_height, step_height), Service
  `/hexapod_cycle_stance` (SetBool true=höher/false=tiefer, clamp, nur STANDING), `_do_stance_switch`,
  Sit-Routing (`_pending_sitdown` + `_SIT_SAFE_MIN_BH`). `gait_engine.py` — `STATE_STANCE_SWITCH`,
  `start_stance_switch`, `_stance_switch_foot` (gekoppelte Tripod-Reposition radial+body_height).
  `joy_to_twist.py` — L2/R2 ohne R1 → cycle_stance.
- **Modi/Werte ändern:** nur die `_STANCE_MODES`-Tabelle (offline-validiert!). Default-Boot-Pose =
  Index 1 (mittel) = die `body_height`/`radial_distance`/`step_height`-Param-Defaults.
- **Fallen:** (1) **leg_changes/S5+S6: einheitlicher WALK-Radius 0.160 über alle Höhen** (tief −0.065 /
  mittel −0.080 / hoch −0.100). Aufstehen/Hinsetzen läuft NICHT an 0.160 (dort reiten die Vorderbeine
  an der Femur-(−90°)-Wand → IKError/Schleifen), sondern am **breiten `standup_radial` 0.20**
  (≈ power_on_mid → schürffreier Touchdown) **+ Tripod-Reposition** auf 0.160
  ([[project_standup_vertical_touchdown_infeasible]]). Kein Sit-Routing über mittel nötig (alle Höhen >
  `_SIT_SAFE_MIN_BH` −0.115); die Routing-Logik bleibt nur als Sicherung für via /cmd_body_height tiefer
  gesetzte Höhen. (2) Jeder neue Modus + jeder Übergang muss offline envelope-grün
  + in-limit sein (Femur-±90° koppelt body_height↔step_height↔radial). (3) `switch_step_height` klein
  halten (Apex unter Femur-Wand bei Zwischenhöhen). (4) cmd_vel im Switch ignoriert (`set_command`-Guard).
- **Validieren:** `colcon test hexapod_gait hexapod_teleop` (`test_stance_switch` —
  v.a. `test_mode_walks_all_directions_no_ikerror`) + Lint · bei Werte-Änderung **mit der ECHTEN
  ENGINE** validieren (GaitEngine + set_command über alle cmd_vel-Richtungen, full cycle, IKError
  fangen) — ⚠️ **`walking_envelope_check` ist am Femur-Wand-Rand zu optimistisch** (meldet GREEN, wo
  der echte Engine-Pfad fehlert); Radien daher mit Femur-Marge (~≥0.15 rad), nicht am Min-Radial-Rand.
  Transitions/Standup/Sit-Reposition ebenfalls real-engine prüfen · SIM · HW.

### Show-Pose / Free-Leg (B4) ändern
- **Voll-Doku:** [`../project_finalization/B4_show_pose_progress.md`](../project_finalization/B4_show_pose_progress.md)
  (IST-Architektur, Parameter-Referenz, Änderungs-Landkarte) + `B4_show_pose_plan.md` §9 (Design-Log).
- **Wo (3 Schichten):** `gait_engine.py` (States `SHOW_ENTER`/`SHOW_ACTIVE`/`SHOW_EXIT`, gemeinsamer
  Skalar σ∈[0,1], `start_show_enter`/`start_show_exit`/`set_show_offsets`, `_show_foot`/`_front_foot`,
  CoG-Gate) · `gait_node.py` (Service `/hexapod_show_toggle`, Sub `/cmd_show`, `show_*`-Params,
  `_update_show_offsets`) · `joy_to_twist.py` (`_show_pose_hook`→Toggle, `_show_from_joy`→`/cmd_show`,
  `ps4_*.yaml`).
- **Pose/Verhalten tunen:** alles über `show_*`-**Params** (wertneutral) — `show_body_shift_back`
  (Stütz-Verlagerung), `show_front_radial`/`show_front_z` (Neutral-Hoch-Pose), `show_*_scale`
  (Stick/Trigger→m), `show_return_rate`, `show_safety_margin`, Dauern. NICHTS in der Engine hardcoden.
- **Fallen:** (1) `show_body_shift_back` **≥ 0.05 halten** (sonst CoG-Marge < 30 mm) und **≤ 0.09**
  (Stütz-Coxa-Limit ±0.415). (2) **Femur ±1.57 (±90°)** begrenzt Vorderbein-Hub + blockiert „curl-in"
  (radial nur raus). (3) **Kein Laufzeit-CoG-Gate in SHOW_ACTIVE** — die URDF-Joint-Limits binden den
  CoG implizit (offline bewiesen); wer die **Reichweiten-Hülle vergrößert** (Skalen/Neutral/neue Achse),
  muss den Worst-Case **neu prüfen** (s.u.). (4) cmd_vel in allen SHOW-States ignoriert (`set_command`-Guard).
  (5) `/cmd_show` = `Float64MultiArray[6]` `[l6_lat,l6_vert,l6_radial, l1_lat,l1_vert,l1_radial]` —
  Reihenfolge bei Änderung in Node **und** Teleop synchron halten.
- **Validieren:** `colcon test hexapod_gait` (`test_show_pose`/`test_show_node`) + `hexapod_teleop`
  (`test_joy_to_twist`) + Lint · **Offline-CoG/Reach neu** bei Hüllen-Änderung
  (`python3 tools/show_pose_cog_check.py` für die ENTER-Pose; den Offset-Worst-Case-Sweep aus
  `B4_show_pose_plan.md` §4a/§9 nachfahren) · **Sim** (RViz+Gazebo, [`B4_show_pose_test_commands.md`](../project_finalization/B4_show_pose_test_commands.md))
  · **HW aufgebockt → Boden** (CoG-kritisch, nur 4 Stützbeine!).

### IMU-Balance / Leveling / Kipp-Erkennung (A5) ändern
- **Voll-Doku:** [`../project_finalization/imu_balance/`](../project_finalization/imu_balance/00_imu_balance_plan.md)
  (Master-Plan + Stufen-Pläne + `imu_balance_progress.md` Done-Vertrag + Self-Reviews).
- **Stand:** Stufe 0 (IMU-Plumbing/Viz) + 1 (Kipp-Erkennung→Safe-State) + 2 (statisches
  Leveling) + 3a (Leveling im Laufen) 🟢 Sim. **Terrain-Following** (Klettern via Voll-Leveln
  **verworfen** → Körper folgt dem Boden): **TF-1** (passiv + slope-bewusster Tip) + **TF-2**
  (aktiv: roll→0, pitch folgt Hang, Gyro-Dämpfung) 🟡 Code+Tests fertig, Sim-Verify offen.
- **Wo (3 Schichten, je Fähigkeit):**
  - **Regler (ROS-frei):** `tip_monitor.py` (`TipMonitor` — Schwellen/Entprellung/Latch,
    Stufe 1) · `balance_controller.py` (`BalanceController` — Totband-PI + **Gyro-D (TF-2)** +
    Slew + Anti-Windup) · `slope_estimator.py` (`SlopeEstimator` — langsamer Tiefpass + Residual,
    **TF-1**). Alle unit-testbar wie `hexapod_kinematics`.
  - **Stellpfad (Engine):** `gait_engine.py` — `set_body_orientation_offset` +
    `_compute_leveled_ik`/`_leveled_ik_at` (R(roll,pitch)-Rotation aller Fuß-Targets via
    `rotate_xy`, STANDING **und** WALKING/STOPPING, Clamp `max_level_angle(_walking)` VOR IK +
    IKError-Fallback). **TF-2 reuset diesen Pfad unverändert** (Korrekturen klein).
  - **ROS-Glue (Node):** `gait_node.py` — `/imu/data`-Sub (Sensor-QoS, cacht roll/pitch +
    Kipprate + **signierte Gyro-Achsen** für D), `_update_slope_estimate` (TF-1, publisht
    `/imu/slope`, **VOR** Tip+Leveling), `_update_tip` (residual-gefüttert + Startup-Grace),
    `_update_leveling` (modus-abh.: **terrain** = pitch-Residual/roll-roh + Gyro / **horizontal** =
    beide roh), `_rebuild_tip_monitor`, alle `tip_*`/`leveling_*`/`slope_*`-Params **live**.
- **Verhalten tunen:** alles über **Params** (live): `leveling_enable/mode/kp/ki/`**`kd`**`/`
  `deadband_deg/slew_max_dps/max_level_angle_deg/max_level_angle_walking_deg/startup_grace`,
  `slope_aware_tip_enable/slope_estimate_tau_s/slope_clamp_deg`, `tip_angle_warn/crit_deg`,
  `tip_rate_crit_dps/tip_debounce_ticks`. NICHTS in Engine/Regler hardcoden.
- **TF-Modus (`leveling_mode`):** `terrain` (Default) = roll→0, **pitch folgt dem Hang** (pitch-
  Eingang = Residual gegen die `SlopeEstimator`-Schätzung) + Gyro-D; `horizontal` = Stufe-2-Voll-
  Leveln (roll+pitch→0, fürs statische Horizontal-Stehen).
- **Fallen:** (1) **`max_level_angle` offline-bewiesen** (10° STANDING / 4° WALKING,
  `tools/leveling_envelope_check.py`). (2) **gz-IMU spawn-referenziert** → in Sim **flach spawnen**
  (`slope.launch.py`/`ramp.launch.py` Default), Memory `project_gz_imu_spawn_referenced`.
  (3) **Vorzeichen:** Fuß-Rotation = −Körper-Korrektur **und** Gyro-D = −Kd·Rate (beide pin per
  Test; sonst positive Rückkopplung/Aufschwingen). (4) **Slope-Schätzung + Leveling + Tip auf
  `_LEVELING_NODE_STATES`** halten (STANDING/WALKING/STOPPING) — desynct gaten → terrain-pitch
  levelt im STOPPING fälschlich auf 0. (5) **D rausch-verstärkend:** Sim rauschfrei → `Kd` auf HW
  konservativ. (6) **roll→0 nur Geradeaus** — Quer-/Diagonal-Hang ist der Nachfolge-Block
  **`TF-Quer`** (roll-Residual + `cmd_vel`-Richtungslogik, [TF-2-Plan §6](../project_finalization/imu_balance/stage_3b_active_tf_plan.md)); Kante/Stufe = Stufe 4 (Fußtaster). (7) Zwei
  Limit-Quellen — Clamp gegen **URDF**-Limits.
- **Schräg-Welten:** `slope.launch.py` (statische Box) / `ramp.launch.py slope_deg:=8.0`
  (flach→Hang→Plateau zum Hineinlaufen) — beide parametrisch, **flach gespawnt**.
- **Validieren:** `colcon test hexapod_kinematics hexapod_gait` (`test_balance_controller`,
  `test_slope_estimator`, `test_gait_engine_leveling`, `test_leveling_node`, `test_rotate_xy`,
  `test_tip_monitor`) + Lint · **Offline** `python3 tools/leveling_envelope_check.py` · **Sim**
  (TF-1 [`stage_3a_passive_tf_test_commands.md`](../project_finalization/imu_balance/stage_3a_passive_tf_test_commands.md) ·
  TF-2 [`stage_3b_active_tf_test_commands.md`](../project_finalization/imu_balance/stage_3b_active_tf_test_commands.md)).

### Fußkontakt / adaptiver Touchdown + Adaptive Stand (Terrain, A5 Stufe 4) ändern
- **Voll-Doku:** [`../project_finalization/imu_balance/stage_4_terrain_adaptive_plan.md`](../project_finalization/imu_balance/stage_4_terrain_adaptive_plan.md)
  (Umbrella, Methoden-Wahl fixed-timing) + S4-1 (Consumer/Verifikation) + S4-2 (adaptiver Touchdown im
  WALKING) + **S4-7 (Adaptive Stand — der statische Zwilling im STANDING**,
  [`stage_4f_adaptive_stand_plan.md`](../project_finalization/imu_balance/stage_4f_adaptive_stand_plan.md)).
- **Stand:** S4-1 🟢 (Kontakt-Consumer + Diagnose). **S4-2 🟢 Sim-verifiziert** (adaptiver Touchdown
  **Option A** — downward-only, an `body_height` verankert, lag-tolerant). ⚠️ Erst-Entwurf (Senkung
  vom Apex bis Floor, Freeze an Kontakthöhe) war **closed-loop-instabil** (Körper-Anker verloren +
  ~13-Tick-Lag → Drift); daher Option A. **S4-6 🟢 Sim-verifiziert** (Graben-Welt zeigt den per-Fuß-
  Reach: `cmd_z` −0.105 vs −0.080, Roll halbiert). **S4-4 🟢 Sim-verifiziert** (Slip/Kante → Freeze,
  `SupportMonitor` Leaky-Zähler). **S4-5 🟢 sim-verifiziert** (Sensor-Fault-Fail-Safe: `SensorHealthMonitor`
  flaggt stuck-on = lückenlose Apex-Pässe / dead → Bein maskieren = adaptiv-aus + aus Slip-Zählung + WARN,
  kein Freeze; T1 stuck_on ✅ / T2 stuck_off ✅; FP-Kaskade + Slip-Race + Geister-Flags gefunden+behoben).
  **✅ STUFE-4-KERN KOMPLETT** (S4-1/2/4/5/6); offen nur das optionale S4-3 (free-gait).
  **S4-7 (Adaptive Stand) 🟡 Code+Tests+Envelope+Doku fertig, Sim-Verify (Rubicon) offen** — im
  STANDING senkt jedes Bein downward-only bis Kontakt (auf unebenem Grund aufsetzen statt hängen).
- **Kontakt-Quelle — zwei Backends, EINE Naht:** der Consumer (`gait_node`) abonniert **immer** die
  6 `/leg_<n>/foot_contact` (`std_msgs/Bool`). Wer sie speist, hängt an Sim vs. HW — **beim Ändern der
  Kontakt-Topics beide Quellen + den gait_node-Sub anfassen.**
  - **Sim:** gz-contact pro `foot_link` ([`hexapod.foot_contact.xacro`](../src/hexapod_description/urdf/hexapod.foot_contact.xacro))
    → [`bridge_foot_contact.yaml`](../src/hexapod_bringup/config/bridge_foot_contact.yaml)
    → [`foot_contact_publisher.py`](../src/hexapod_sensors/hexapod_sensors/foot_contact_publisher.py)
    (Event→Dauer-`Bool`, **50 Hz dauernd**) → `/leg_<n>/foot_contact`. Default an (`enable_foot_contact:=true`).
  - **HW (A5 Stufe 5):** 6 Fuß-Taster am Servo2040 (SENSOR_1..6, interner Pull-Up gegen GND). Firmware
    `GET_INPUTS` (0x40)→`INPUTS` (0xC0), entprellter 1-Byte-Bitmaske ([`hexapod_servo_driver`](../../hexapod_servo_driver/src/main.cpp) `poll_inputs`/`handle_get_inputs`, PROTOCOL.md §3.2 v1.1).
    Das Host-Plugin ([`hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp)) sendet
    GET_INPUTS pro write()-Zyklus, cached `InputsSnapshot(bits,stamp)` im Reader und **publisht dieselben
    6 Bool-Topics** — freshness-gated (100 ms; FW-Stille → kein Publish → gait-Live-Guard trippt).
    Schalter: `publish_foot_contacts` (`real.launch.py`, default an), Remap `sensor_leg_map`. **gait_node
    + S4-Pipeline unverändert.** Bench: `hexapod_servo_driver/tools/probe_inputs.py`.
  - **Wir bauen den Consumer, nicht die Sensorik.**
- **Wo (3 Schichten):**
  - **Engine (ROS-frei):** `gait_engine.py` — `_compute_walking_targets` ruft pro Bein
    `_adaptive_touchdown_z(leg_id, cycle_phase, z_nom)` (NUR z adaptiv, x,y nominal; **Option A**:
    nominaler Schwung+Stance bleiben, Probe **nur unter `body_height`** ab Stance-Gate); per-Bein
    `_touchdown_z` + `_td_searched`; `set_foot_contacts()` (Cache vom Node); `adaptive_touchdown_enable`
    (vom Node pro Tick). WALKING-Eintritt: Stance-Beine auf `body_height` vorverankert.
  - **Engine — Adaptive Stand (S4-7):** `_compute_standing_targets(t)` ruft pro Bein
    `_adaptive_stand_z(leg_id, t)` (statischer Zwilling: downward-only ab `body_height` mit
    `stand_conform_rate·(t−t_stand_entry)`, Freeze bei Kontakt, Floor `body_height−stand_conform_max_depth`);
    per-Bein `_stand_conform_z` + `_t_stand_entry` + `_stand_conform_bh`; `reset_stand_conform(t)` bei
    STANDING-Eintritt (via `_prev_state`-Snapshot in `compute_joint_angles`) UND body_height-Änderung
    (self-detect). `t=None`-Pfad (aus `_compute_stand_pose_joints`) + `adaptive_stand_enable=false` =
    **bit-identisch** zur starren Pose. Node: `adaptive_stand_enable = param AND pipeline_live`
    (gleicher Contact-Live-Guard wie S4-2), Live-Enable in STANDING → `reset_stand_conform`.
  - **Node-Glue:** `gait_node.py` — 6 Subs `/leg_<n>/foot_contact` (`_make_foot_contact_cb`, stempelt
    Frische), `_update_foot_contacts` (Diagnose + Kontakte an Engine + **Contact-Live-Guard** →
    `engine.adaptive_touchdown_enable = param AND pipeline_live`), `_debug_leg1_contact` (Mess-Werkzeug).
  - **Diagnose (ROS-frei):** `contact_diagnostic.py` (`ContactDiagnostic` — Latenz/Apex/Gap/Quote).
  - **Slip/Kante → Freeze (ROS-frei, S4-4):** `support_monitor.py` (`SupportMonitor`, wie `TipMonitor`)
    — Stance-Bein ohne Kontakt nach Grace (entprellt) → Freeze; `gait_node._update_support` (WALKING-
    Gating, `_trigger_safety_freeze` = Stufe 1) + `engine.cliff_probe_depth` (Probe-Floor = `cliff_depth`).
  - **Sensor-Plausibilität → maskieren (ROS-frei, S4-5):** `sensor_health_monitor.py`
    (`SensorHealthMonitor`, wie `TipMonitor`) — **stuck-on** = **3 lückenlose Apex-Pässe in Folge**
    (Band 0.3–0.7; robust gg. das gz-Apex-Artefakt, das gesund lückenhaften Apex-Kontakt liefert) /
    **dead** = überhaupt kein Kontakt über `dead_cycles` Cycles (stuck-on erscheint nie als dead) →
    Bein latched flaggen. `gait_node._update_sensor_health`
    (WALKING-Gating, `_apply_sensor_fault_inject` VOR allen Consumern, **reset bei aktivem Freeze** →
    keine Geister-Flags auf eingefrorenen Kontakten) → **Maskierung:** `engine.set_adaptive_masked_legs`
    (S4-2 adaptiv-aus, Open-Loop) + Ausschluss aus `_update_support` (faulty → is_stance=False → nicht
    gezählt) + throttled WARN. **Kein** Freeze (Degradation). **Race-Fix (T2):** ein Bein, das die
    Episode **nie** Kontakt hatte (`_ever_contacted`, toter Sensor von Start), wird **sofort** aus dem
    Slip-Freeze ausgeschlossen (sonst freezt S4-4 in ~1 s, bevor die dead-Erkennung über 2 Cycles
    maskiert) — nur bei aktivem S4-5; ein Bein, das Kontakt **hatte** und verliert, freezt weiter.
- **Verhalten tunen:** alles über **Params** (live): `adaptive_touchdown_enable` (Default false,
  Opt-in), `touchdown_probe_start_stance_phase` (0.35, Stance-Gate für die Abwärts-Suche),
  `touchdown_search_end_stance_phase` (0.6, Such-Ende → danach Floor), `touchdown_max_extra_depth`
  (0.02 m, Floor unter `body_height`). **S4-4:** `slip_detection_enable` (false), `cliff_depth`
  (0.03, Grenze folgbar↔Abgrund), `slip_debounce_ticks` (8, > contact_timeout 5), `slip_min_lost_legs`
  (1), `slip_grace_stance_phase` (0.6, cycle_time-abhängig wie probe_start). **S4-5:**
  `sensor_plausibility_enable` (false), `sensor_apex_band_low/high` (0.3/0.7, low>contact_timeout-Nachhall),
  `sensor_apex_fault_cycles` (3, lückenlose Apex-Pässe in Folge), `sensor_dead_cycles` (2, **Cycles** →
  Ticks via cycle_time·tick_rate, Rebuild), `sensor_fault_inject` (`''`, Debug-Hook `'<leg>:stuck_on|stuck_off'`).
  **S4-7 (Adaptive Stand):** `adaptive_stand_enable` (false, Opt-in), `stand_conform_max_depth` (0.04 m,
  Floor unter `body_height`, ≥0; Rubicon-Dips ~3–5 cm, 0.02 war zu flach; Envelope-Max über alle Modi
  = 0.05), `stand_conform_rate` (0.02 m/s, >0). Envelope je Stance-Höhe:
  `python3 tools/stand_conform_envelope_check.py` (tief/mittel/hoch GREEN, Floor hoch −0.140).
- **Fallen:** (1) **Körper-Anker NICHT aufgeben** — der Erst-Entwurf (Freeze an Kontakthöhe, auch
  über `body_height`) war closed-loop-instabil (Drift). Option A hält den Anker bei `body_height`
  und senkt **nur nach unten**. (2) **`probe_start` > Kontakt-Lag in Stance-Phasen** (bei
  `cycle_time=2.0` ≈ 0.27; 0.35 hat Marge) — sonst sucht der Fuß auf flachem Boden **bevor** der
  laggy Kontakt registriert → Absacken. Bei schnellerem Cycle `probe_start` hochsetzen. (3) **Kontakt
  = Optimierung, nie load-bearing** — Contact-Live-Guard (Topic-Frische < 0.5 s) schaltet bei toter
  Pipeline adaptiv aus → nominaler Fallback. (4) **Envelope:** Floor `body_height − max_extra_depth`
  mit `walking_envelope_check check --body-height <bh−depth> --scenario all` prüfen (0.02 GREEN
  mittel+hoch); IKError nur Backstop. (5) **Zwei Limit-Quellen** — Envelope/IK gegen **URDF**-Limits.
  (6) Sim **isoliert** testen (`leveling_enable:=false`). (7) **S4-5 gz-Apex-Artefakt** — der gz-Kontakt
  meldet auch gesund **lückenhaften** Apex-Kontakt (contact_timeout + Fußkugel-Clearance); naive „Apex-
  Kontakt = Fault"-Logik flaggt reihenweise gesunde Beine (Sim-Befund T1). Daher stuck-on = **lückenlose
  Apex-Pässe in Folge** + Band ab 0.3 (past Nachhall). (8) **Sensor-Fault = Optimierung verlieren, nicht
  stoppen** — ein geflaggtes Bein degradiert auf Open-Loop, löst aber **keinen** Freeze aus (Backstop:
  Tip + gesunde Beine).
- **Welten (S4-6):** **Graben** `hexapod_gazebo/worlds/trench.sdf.xacro` (2 Plattformen z=0 +
  ground_plane tiefer = Lücke; via `trench.launch.py`/`trench_walk.launch.py`) = die **klare Demo**
  des per-Fuß-Reach (Körper bleibt eben, `cmd_z`~−0.10). **Stufe** `step.sdf.xacro` (signiert
  `step_drop` +=ab/−=auf) = funktionaler Beleg, aber **vom Körper-Pitch geschluckt** (~3 mm, schwache
  Demo — daher der Graben). Reach-Budget: `|drop| ≲ max_extra_depth` (Demo `max_extra_depth:=0.025`).
  Sanfter Hang = `ramp.sdf.xacro`. Alle `*_walk.launch.py` = Ein-Befehl, `leveling_enable` Default false.
- **Validieren:** `colcon test hexapod_kinematics hexapod_gait` (`test_adaptive_touchdown`,
  `test_adaptive_touchdown_node`, `test_support_monitor`, `test_slip_detection_node`,
  `test_sensor_health_monitor`, `test_sensor_plausibility_node`,
  `test_leg_gait_states`, `test_contact_diagnostic`, `test_foot_contact_node`) + Lint · **Offline**
  `walking_envelope_check` (Floor-Tiefe) · **Sim**
  ([`stage_4b_…`](../project_finalization/imu_balance/stage_4b_adaptive_touchdown_test_commands.md) +
  [`stage_4c_step_worlds_test_commands.md`](../project_finalization/imu_balance/stage_4c_step_worlds_test_commands.md) +
  [`stage_4e_plausibility_test_commands.md`](../project_finalization/imu_balance/stage_4e_plausibility_test_commands.md)).

### Neuer Knoten / Topic
- **Wo:** Bringup-Launch (`hexapod_bringup`), ggf. eigenes Paket. Topic-Konventionen aus
  `architecture.md` §4 einhalten.

## 2. Validierungs-Gates (Reihenfolge)
1. `colcon build --packages-select <betroffen>` → grün.
2. Generierte URDF prüfen (bei URDF-Änderung).
3. `colcon test --packages-select <betroffen>` (Unit + `ament_flake8`/`ament_pep257`) → grün.
4. Eigen-Tools: `walking_envelope_check`, `standup_envelope_check`, (geplant) torque-viz.
5. **Sim** (RViz + Gazebo) — Modell lädt, kein Regress, läuft.
6. **HW aufgebockt** → **HW Boden** (CLAUDE.md §9 Safety).

## 3. Wo finde ich …?
| Gesucht | Datei |
|---|---|
| IK/FK + Geometrie + Limits (Python) | `hexapod_kinematics/config.py`, `leg_ik.py` |
| Joint-Limits (URDF) | `hexapod_description/urdf/hexapod.urdf.xacro` (+ `ros2_control.xacro`, `physical_properties.xacro`) |
| Puls-Cal je Servo | `hexapod_hardware/config/servo_mapping.yaml` |
| Gait-Logik / State-Machine | `hexapod_gait/hexapod_gait/gait_engine.py`, `gait_node.py` |
| IMU-Balance / Leveling / Kipp-Erkennung (A5) | `hexapod_gait/{tip_monitor,balance_controller}.py`, `gait_engine._compute_leveled_ik`, `gait_node._update_{tip,leveling}`; `project_finalization/imu_balance/` |
| Gangmuster | `hexapod_gait/hexapod_gait/gait_patterns.py` |
| Lauf-Presets | `hexapod_gait/config/presets/*.yaml` |
| Controller-Config | `hexapod_control/config/controllers{,.real}.yaml` |
| Teleop-Mapping | `hexapod_teleop/config/ps4_usb.yaml`, `joy_to_twist.py` |
| Analyse-Tools | `tools/` (+ [`tools_catalog.md`](tools_catalog.md)) |

## 4. Offene Stages / was als Nächstes
→ [`../project_finalization/00_backlog.md`](../project_finalization/00_backlog.md)
