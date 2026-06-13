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
  an der Femur-(−90°)-Wand → IKError/Schleifen), sondern am **breiten `standup_radial` 0.21**
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
| Gangmuster | `hexapod_gait/hexapod_gait/gait_patterns.py` |
| Lauf-Presets | `hexapod_gait/config/presets/*.yaml` |
| Controller-Config | `hexapod_control/config/controllers{,.real}.yaml` |
| Teleop-Mapping | `hexapod_teleop/config/ps4_usb.yaml`, `joy_to_twist.py` |
| Analyse-Tools | `tools/` (+ [`tools_catalog.md`](tools_catalog.md)) |

## 4. Offene Stages / was als Nächstes
→ [`../project_finalization/00_backlog.md`](../project_finalization/00_backlog.md)
