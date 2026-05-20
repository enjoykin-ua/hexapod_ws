# Phase 11 — Progress-Tracker

**Phase:** Param-GUI mit Live-Tuning (rqt_reconfigure)
**Plan:** [phase_11_param_gui.md](phase_11_param_gui.md)
**Aktiv seit:** 2026-05-19

> **Session-Continuity-Hinweis (für neue Chat-Session):**
>
> Aktueller Stand: **Stage A wartet auf User-Freigabe**.
> Plan-Doku ist in [`phase_11_stage_a_plan.md`](phase_11_stage_a_plan.md).
> Vor Code-Beginn: **Pre-Implementation Code-Inspection** lesen (im
> Plan-Doc Abschnitt „🔍 Pre-Implementation Code-Inspection") — das
> klärt gait_node-Struktur, GaitEngine-State-Machine, existing
> `cmd_body_height`-Topic-Handler als Vorbild.
>
> **8 offene Fragen (A-Q1..A-Q8)** stehen unter „User-Antworten" in der
> Plan-Doku — User muss freigeben. Wichtigste Anpassung gegenüber dem
> ursprünglichen Plan: `gait_pattern`, `body_height`, `tick_rate`,
> `cycle_time` werden **nur in STANDING-State** live tunbar (analog
> bestehender `/cmd_body_height`-Topic-Pattern, gait_node.py line 168-171).
> Sicherer als ursprünglich vorgeschlagen — kein Mid-Walk-Kipp-Risiko.

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**
> (Memory `feedback_phase_progress_tracking.md`).

---

## Design-Entscheidungen vor Stufe A

Konsolidiert aus Mutter-Plan-Doku
[Architektur-Entscheidungen A–D](phase_11_param_gui.md#architektur-entscheidungen).

### A. Tool-Wahl: rqt_reconfigure (Standard ROS-GUI) — Final

- **Final:** rqt_reconfigure als zentrales GUI, plus rqt_plot + rqt_topic
  als Multi-Plugin-Layout
- **Verworfen:** Custom rqt-Plugin (Punkt 2 aus Diskussion), RViz-Panel,
  Gazebo-Plugin, PyQt-Standalone, Foxglove, Web-App+rosbridge
- **Begründung:** User-Wunsch „Slider mit Namen" wird von rqt_reconfigure
  out-of-the-box erfüllt. Custom Plugin wäre Sahne aber 3-5 d Mehraufwand.

### B. Save/Load-Workflow — ros2 param dump + params_file-Arg

- **Final:** Combo aus `ros2 param dump` (CLI Save) + `params_file:=...`
  Launch-Arg (Load) + Preset-YAMLs in `src/hexapod_gait/config/presets/`
- **Verworfen:** GUI-Save-Button (wäre Custom Plugin), Live-Persistence
  in Plugin-Internal-State
- **Bonus:** Bash-Aliases für `hexapod-save-walking-params` als
  optional User-Comfort

### C. Echo-State-Realität (aus Phase-10-Stage-G übernommen)

- **Final:** JTC-Toleranz-Constraints bleiben deferred (Echo-State macht
  sie wertlos). Phase 11 fokussiert auf Vel/Accel-Limits via Live-Param
  (echter Effekt auf Trajectory-Spline).

### E. Engine-Property-Refactor (Stage-A-spezifisch, 2026-05-20) — Final

- **Final:** `_stance_duration` und `_linear_max` als read-only Properties
  in `GaitEngine` (live aus `cycle_time` / `step_length_max` / `pattern.swing_duty`
  berechnet) — Plan-Doku [phase_11_stage_a_plan.md](phase_11_stage_a_plan.md)
  Finding 2 Option A
- **Verworfen:** Option B (Setter-Methoden mit Cache-Invalidierung —
  disziplin-abhängig, vergessener Setter = Cache-Drift), Option C (Status
  quo — Live-Update für `cycle_time` / `step_length_max` / `pattern` nicht
  möglich, Done-Kriterium A verletzt)
- **Begründung:** strukturell unmöglich, dass Cache veraltet. Externe
  API (`engine.linear_max`) bleibt identisch (war schon Property).

### D. Plugin-Live-Cal: `/servo_pulses` Diagnostic-Topic

- **Final:** Plugin publiziert 18 Pulse-µs-Werte als ROS-Topic für
  rqt_plot-Visualisierung
- **Plus:** Plugin-Live-Param-Callback für pulse_min/zero/max/direction
  → Live-Servo-Cal via rqt_reconfigure möglich

---

## Stufe A — gait_node Param-Callback

> **Vorab-Plan:** [`phase_11_stage_a_plan.md`](phase_11_stage_a_plan.md)
> (wird bei Stage-A-Start angelegt)

- [x] A.1 phase_11_stage_a_plan.md (Plan-Doku) finalisiert + User-Freigabe (2026-05-20)
- [x] A.2 phase_11_stage_a_test_commands.md angelegt (Skelett, 9 Tests, 2026-05-20)
- [x] A.2a Engine-Property-Refactor (`stance_duration`/`linear_max` als Properties — Plan-Doku Finding 2, Option A) (2026-05-20, Build+Linter grün)
- [x] A.3 gait_node ParameterDescriptors für alle 14 Params deklariert (2026-05-20)
- [x] A.4 `on_set_parameters_callback` registriert mit atomic-all-or-nothing-Validation (2026-05-20)
- [x] A.5 Helper-Methoden `_restart_timer` + `_load_gait_pattern` + `_apply_param` (2026-05-20; `_recompute_stand_pose` entfällt — Finding 1)
- [x] A.6 Edge-Case-Handling via `_STANDING_ONLY_PARAMS`-frozenset (body_height, body_height_min/max, radial_distance, cycle_time, tick_rate, gait_pattern) + MutuallyExclusiveCallbackGroup für Timer (2026-05-20)
- [x] A.7 A-T1 colcon build hexapod_gait grün (2026-05-20)
- [x] A.8 A-T2 colcon test hexapod_gait grün — 18 passed, 1 skipped (15 neue Param-Callback-Tests in `test_param_callback.py` + 3 Linter; 2026-05-20)
- [x] A.9 A-T3 keine Regression: hexapod_bringup 18/0/0, hexapod_hardware 208/0/20 unverändert (2026-05-20)
- [x] A.10 User-Smoke A-T4..A-T8 ✅ (T9 🟢 übersprungen, durch Unit-Tests abgedeckt). Doku-Fix A-T5 (Direction) + Code-Fix `param updated`-Log nach Apply (2026-05-20)
- [x] A.11 Self-Review-Tabelle (CLAUDE.md §4-Pflicht): 1× 🔴 gefunden + gefixt (Topic-Handler Sync-Bug + Regression-Test → 19 Tests grün), 2× 🟡 (Threading bei MultiThread, Engine-Validation-Range-Konsistenz), 2× 🟢 später (2026-05-20)
- [x] A.12 Stage-A-Notizen + Übergang Stage B (2026-05-20)

**Done-Kriterium A:** ✅ erreicht 2026-05-20 — alle 14 gait_node-Params via
ParameterDescriptor mit Range deklariert, `on_set_parameters_callback`
mit atomic-all-or-nothing-Validation + STANDING-only-Constraint für
sicherheitskritische Params (`_STANDING_ONLY_PARAMS`), Engine-Property-
Refactor (`stance_duration`/`linear_max`), Sync-Bug im Phase-6-Topic-
Handler gefixt, Log-Feedback nach Apply, 20/0/1 Tests grün, keine
Regression in hexapod_bringup/hardware, User-Smoke A-T4..A-T8 bestätigt.

### Stage-A-Notizen (für Stage B + Folge-Phasen)

- **Engine-Property-Refactor** (`stance_duration`/`linear_max` als
  Properties) ist die Basis für saubere Live-Updates auf
  `cycle_time` / `step_length_max` / `pattern`. Pattern für Stage B:
  wenn die hexapod_hardware Plugin-Klasse ähnliche Caches hat (z.B.
  pro Pin gecachte rad↔µs-Maps), die ebenfalls zu Properties machen.
- **`_STANDING_ONLY_PARAMS`-frozenset** als zentrale Policy-Definition
  funktioniert gut. Stage B braucht das analoge Pattern für
  Plugin-State-Constraints (z.B. „pulse_min/max nur in idle ändern").
- **atomic-all-or-nothing-Validation** hat sich bewährt — Test-Pattern
  via `set_parameters_atomically` ist sauber. Für `ros2 param load`-
  Workflows in Stage D direkt nachnutzbar.
- **rqt_reconfigure Slider-Min/Max** werden in `_declare_params_with_descriptors`
  inline gepflegt — gleicher Mechanismus für Stage-B-Plugin-Params
  (pulse_min/zero/max/direction pro Pin).
- **Logging-Konvention**: `param updated: <name>=<value>` nach
  erfolgreichem Apply gibt User-Feedback ohne Spam (bei rejected
  Updates kein Log, dafür `SetParametersResult.reason`).
- **CallbackGroup-Muster:** `MutuallyExclusiveCallbackGroup` für den
  Tick-Timer ist Future-Proof gegen MultiThreaded-Executor. Bei
  SingleThreaded (= unsere main()) ohnehin sequentiell. Stage B kann
  dasselbe Pattern für den Plugin-write()-Pfad nutzen falls nötig.
- **Cross-Phase-Pendenzen offen für Stage B:**
  - Self-Review-Punkt 2 🟡: bei MultiThreaded-Executor-Wechsel Locking
    ergänzen
  - Self-Review-Punkt 3 🟡: Range-Validation der Descriptors gegen
    Engine-`__init__`-Validation-Bedingungen halten
  - Self-Review-Punkt 7 🟢: launch_testing-E2E-Test als optional

### Übergang Stage B

**Stage B** = hexapod_hardware Plugin Live-Cal Param-Callback (C++,
pluginlib). Plugin um `on_set_parameters_callback` für
`pin_X_pulse_min/zero/max/direction` (18 Pins × 4 Werte = 72 Params)
erweitern. Plus Helper-Service `/save_calibration` der die Live-Werte
zurück in `servo_mapping.yaml` schreibt.

**Vorbereitung Stage B:**
- Plan-Doku `phase_11_stage_b_plan.md` mit 4 Pflichtinhalten (CLAUDE.md
  §4) inkl. Code-Inspection von hexapod_hardware Plugin
- Klärung: 72 separate Params (`pin_15_pulse_min`...) oder Namespace
  pro Pin (`pin_15.pulse_min`)? → Plan-Frage B-Q
- Validation pulse_min < pulse_zero < pulse_max, alle in [800, 2200] µs

Phase 11 Stage A — abgeschlossen 2026-05-20.

### Post-Stage-Refactor: `_GAIT_PARAMS`-Spec-Tabelle (2026-05-20)

Vor Beginn Stage B durchgeführt um Wartbarkeit + Stage-B-Vorbild zu
verbessern. User-Initiative — Inline-`declare_parameter`-Boilerplate
(14× ähnliche Blöcke, ~195 Zeilen) durch tabellarische Spec ersetzt.

**Vorher:** 14 separate `self.declare_parameter(name, default,
ParameterDescriptor(...))`-Blöcke inline in `_declare_params_with_descriptors`,
plus parallel gepflegtes `_STANDING_ONLY_PARAMS`-frozenset.

**Nachher:** `@dataclass(frozen=True) _ParamSpec` + `_GAIT_PARAMS`-Tuple
am Modul-Anfang als Single Source of Truth. `_STANDING_ONLY_PARAMS` wird
daraus generiert (kein Drift möglich). `_declare_params_with_descriptors`
schrumpft auf eine 19-Zeilen-Schleife.

**Optionen evaluiert:**

| Option | Mechanismus | Empfehlung |
|---|---|---|
| 1 — Tuple-List | `(name, default, min, max, step, standing_only)`-Tuples | verworfen — Tuple-Indizes unleserlich, String-Param `gait_pattern` passt nicht ins Schema |
| **2 — Dataclass** | `_ParamSpec` mit optionalen `fp_range`/`string_constraint` | **✅ gewählt** — typed, String+Float in einer Liste, generiert `_STANDING_ONLY_PARAMS` |
| 3 — Dict für Ranges only | Inline-Calls + `_PARAM_RANGES`-Dict | verworfen — halbherzig, Default/Description bleiben verteilt |

**Begründung Option 2:** Stage B hat 72 Pin-Cal-Params — Tabelle ist da
zwingend, Pattern jetzt einführen ist konsistent. Plus: `_STANDING_ONLY_PARAMS`
wird abgeleitet → eine Quelle der Wahrheit, kein Drift-Risiko.

**Was NICHT in die Tabelle gewandert ist:** die `_apply_param`-Apply-
Logik. Pro Param ist die wirklich unique (Timer-Restart, Engine-Attribute,
Pattern-Load) und bleibt als if/elif-Chain — Generalisierungsversuch wäre
mehr Indirektion als Lösung.

**Bonus-Cleanup:**
- Stale Build-Artefakte im src-Tree gelöscht (`src/build/`,
  `src/install/`, `src/hexapod_gait/build/`, `src/hexapod_gait/install/`)
  — Reste von früheren versehentlichen Builds aus dem src-Verzeichnis,
  mit `COLCON_IGNORE` markiert aber von Linter erreichbar
- [`.flake8`](../src/hexapod_gait/.flake8) angelegt mit
  `extend-exclude = build,install` — verhindert dass künftige stale
  Artefakte im src-Tree den Linter brechen

**Test-Bilanz nach Refactor:** hexapod_gait 20/0/1, hexapod_bringup
18/0/0, hexapod_hardware 208/0/20 — identisch zu vor Refactor.

---

## Stufe-A-Post-Review (Self-Review vor User-Smoke, 2026-05-20)

CLAUDE.md §4-Pflicht-Schritt. Geprüft auf Edge-Cases, Race-Conditions,
Konsistenz mit Phase-6-Code, Test-Coverage, Plan-Doku-Drift.

| # | Punkt | Status |
|---|---|---|
| 1 | **🔴 Sync-Bug Phase-6-Topic-Handler:** `_on_cmd_body_height` setzte nur `self._engine.body_height`, nicht `self._body_height`. Stage-A-Param-Callback liest aber `self._body_height` für Cross-Constraint-Pre-Validation → stale-Decision möglich nach Topic-Update | 🔴→OK **gefixt** in [gait_node.py:188-191](../src/hexapod_gait/hexapod_gait/gait_node.py#L188-L191) + Regression-Test `test_cmd_body_height_topic_syncs_node_member` |
| 2 | `MutuallyExclusiveCallbackGroup` deckt nur Timer; Param-Callback und cmd_vel/cmd_body_height-Subscriber sind außerhalb der Group. Bei SingleThreadedExecutor (`rclpy.spin` default) egal — bei MultiThreaded möglich Race | 🟡 vormerken — main() nutzt SingleThreaded, kein akutes Problem. Wenn jemand zu MultiThreaded wechselt, Locking ergänzen (oder alle Callbacks in dieselbe Group) |
| 3 | Engine `__init__` validiert `cycle_time > 0`, `step_length_max > 0`; Live-Update macht keine Re-Validation. Aktuell durch ParameterDescriptor-Range geschützt (`cycle_time` ≥ 0.5, `step_length_max` ≥ 0.01) | 🟡 vormerken — falls Range später erweitert wird, Range-Match mit Engine-Validation re-prüfen |
| 4 | `_load_gait_pattern` setzt `self._engine.pattern` direkt. Engine speichert pattern-bezogene `_cycle_phase_at_stop` nur im STOPPING-State. Pattern-Update STANDING-only → STOPPING-State unmöglich beim Wechsel | OK |
| 5 | `_apply_param` hat kein Else-Branch für unbekannten Param-Namen — silent skip. `use_sim_time` wird in Pre-Validation gefiltert, sonst keine Quelle für unbekannte Namen | OK (defensive, aber unreachable) |
| 6 | Atomic-Test `test_param_set_atomic_apply_two_valid` nutzt `set_parameters_atomically` statt `set_parameters` — das ist auch die API die `ros2 param load` (YAML-Multi-Param) verwendet. Korrekt für User-Erwartung | OK |
| 7 | launch_testing-End-to-End-Test (Plan §A.5 erwähnt `test_gait_param_live`) nicht implementiert — Unit-Tests + User-Smoke A-T4..A-T9 decken den Bereich ab | 🟢 später — bei Bedarf nachziehen, kein Done-Blocker |
| 8 | Engine-Property-Refactor (A.2a) keine eigenen Engine-Tests, indirekt verifiziert durch `test_param_set_cycle_time_updates_engine_linear_max` + `test_param_set_step_length_max_updates_engine` | OK |
| 9 | Default-Werte aller Params durch sich selbst gegen Range geprüft (Descriptor verbietet out-of-range bei `declare_parameter`) | OK |
| 10 | `body_height_min`/`max`-Updates während WALKING werden korrekt abgelehnt (STANDING-only); aber: Test deckt nur `body_height` ab. Cross-Variation `body_height_min` in WALKING fehlt | 🟢 später — abgedeckt durch STANDING-only-Set-Logik, redundanter Test |

**Self-Review-Ergebnis:** 1× 🔴 gefunden + gefixt + Regression-Test ergänzt
(Punkt 1). 2× 🟡 vorgemerkt (Punkte 2, 3), 2× 🟢 später (Punkte 7, 10), Rest OK.
Stage A ready für User-Smoke A-T4..A-T9.

---

## Stufe-A-User-Smoke-Ergebnisse (2026-05-20)

User-Smoke in Sim ausgeführt. Setup-Anpassung: `sim.launch.py` startet
**kein RViz** — separates Terminal 1b mit `rviz2 -d view.rviz` nötig
(test_commands.md korrigiert).

| Test | Status | Anmerkung |
|---|---|---|
| **A-T4** `ros2 param set /gait_node body_height -0.060` | ✅ | Terminal-Output + rqt-View zeigen Update |
| **A-T5** rqt-Slider `body_height` -0.052 → -0.040 | ✅ + Doku-Fix | Body **senkt sich** (Test-Doku hatte "hebt sich" falsch — `body_height` ist Foot-Z im Bein-Frame, weniger negativ = Foot näher am Coxa = Body tiefer). test_commands.md korrigiert |
| **A-T6** `gait_pattern` von `tripod` → `single_leg_3` | ✅ + Code-Fix | Initial: User sah weder Roboter-Reaktion noch Log-Eintrag → UX-Lücke. Post-Smoke-Fix: `_on_param_change` loggt jetzt nach erfolgreichem Apply `param updated: <name>=<value>` (siehe [gait_node.py:_on_param_change](../src/hexapod_gait/hexapod_gait/gait_node.py) Apply-Block). Pattern-Wechsel selbst war wirksam — durch A-T8 belegt |
| **A-T7** Invalider Wert (`body_height -1.0`) | ✅ | Wie erwartet abgelehnt, Slider springt zurück |
| **A-T8** Param-Update in WALKING ablehnen | ✅ | `single_leg_3` aus T6 + cmd_vel → nur leg_3 bewegt (= T6-Pattern-Wechsel war wirksam!). Param-Update in WALKING wird abgelehnt wie erwartet |
| **A-T9** Atomic Cross-Constraint via `ros2 param load` | 🟢 übersprungen | Unit-Tests decken den Bereich vollständig ab: `test_param_set_atomic_apply_two_valid` (happy path) + `test_param_set_atomic_rollback_one_invalid` (atomic rollback). Manuelle E2E-Verifikation optional |

**Post-Smoke-Code-Änderung:** `_on_param_change` loggt nach erfolgreichem
Apply die Param-Liste (`param updated: name=value, ...`). Damit hat
jeder Slider-Drag und jeder `ros2 param set` ein sichtbares Feedback
im gait_node-Terminal. 20 Tests grün (vorher 19) — Logging brach keinen
bestehenden Test.

---

## Stufe B — hexapod_hardware Plugin Live-Cal

**Plan-Doku:** [`phase_11_stage_b_plan.md`](phase_11_stage_b_plan.md)
**Test-Anleitung:** [`phase_11_stage_b_test_commands.md`](phase_11_stage_b_test_commands.md)

Aktiv seit 2026-05-20. Plan-Doku finalisiert mit User-Freigabe der
9 offenen Fragen B-Q1..B-Q9 + 6 Plan-Review-Korrekturen F1..F6
(Timestamp-bak, is_active_-Member, std_srvs-Dep, README-Update,
YAML-Format-Schema, tmpdir-Pattern-Reuse).

### Stage-B-Fortschritt

- [x] B.1 Plan-Doku finalisiert + User-Freigabe + F1..F6-Fixes (2026-05-20)
- [x] B.2 phase_11_stage_b_test_commands.md Skelett (2026-05-20)
- [x] B.3 Calibration-API erweitert: `mutex_`, `snapshot`, `update_servo_cal`, `save_to_file` (mit Timestamp-bak) (2026-05-20)
- [x] B.4 `register_live_cal_params()` + `PinParamSpec`-Tabelle für 72 Pin-Params (Range [500, 2500] entsprechend YAML-Defaults) (2026-05-20)
- [x] B.5 `is_active_` atomic-Member + Set in `on_activate`/`on_deactivate` (F2) (2026-05-20)
- [x] B.6 `on_param_change`-Callback mit atomic-Validation + Direction-active-Reject (2026-05-20)
- [x] B.7 `/save_calibration`-Service (Trigger + Timestamp-bak + flat YAML mit Header-Template, F1+F5) (2026-05-20)
- [x] B.8 package.xml + CMakeLists.txt: `std_srvs`-Dep (F3) (2026-05-20)
- [x] B.9 Logging `cal updated: <name> = <value>` nach Apply (2026-05-20)
- [x] B.10 colcon build hexapod_hardware grün (2026-05-20)
- [x] B.11 colcon test hexapod_hardware grün: **220/0/20** (war 208/0/20 → +12 neue Stage-B-Tests in test_calibration.cpp: snapshot, update_servo_cal happy/invalid/out-of-range, radians_to_pulse_us-Live-Update, 5 SaveToFile-Tests inkl. Timestamp-bak-Pattern) (2026-05-20)
- [x] B.12 Regression: hexapod_gait 20/0/1 unverändert, hexapod_bringup 18/0/0 (Initial: Range-Mismatch [800,2200] vs YAML-Default 500 → declare_parameter-Reject. Fix: Range auf [500, 2500] erweitert für Firmware-Standard-Servo-Range — Validation in update_servo_cal schützt zusätzlich) (2026-05-20)
- [x] B.12a README hexapod_hardware mit Phase-11-Stage-B-Block (Live-Cal-Param-Liste, Direction-Restriction, Save-Service mit Backup-Strategie, Cal-Session-Beispiel) (2026-05-20)
- [x] B.13 User-Smoke (2026-05-20): B-T4 ✅ (nach Doku-Fix Node-Name), B-T5 ✅, B-T6 ✅, B-T7 🟢 übersprungen (Save-Service-E2E durch User-Discretion), B-T8a 🟢 übersprungen (Inactive-Accept trivial), B-T8b ✅ (Active-Reject mit klarer reason "pin_15.direction_normal can only change in 'inactive' lifecycle state"). Plus zwei Doku-Bugs entdeckt + gefixt: (a) Node-Name lowercase `/hexapodsystem` statt `/HexapodSystem`, (b) `ros2 lifecycle` greift bei Hardware-Components nicht — korrekt ist `ros2 control list_hardware_components`
- [x] B.14 Self-Review-Tabelle (CLAUDE.md §4-Pflicht; F7 + F8 explizit) (2026-05-20)
- [x] B.15 Stage-B-Notizen + Übergang Stage C (2026-05-20)

### Stage-B-Notizen (für Stage C + Folge-Phasen)

- **`get_node()` ist nach Basis-Klasse `on_init` verfügbar** — gibt
  `rclcpp::Node::SharedPtr` zurück (nicht LifecycleNode!). Damit kann
  das Plugin `declare_parameter`, `add_on_set_parameters_callback`,
  `create_service` usw. nutzen — analog ein regulärer Node.
- **Plugin-Lifecycle ≠ ROS-Lifecycle** — Hardware-Components in
  ros2_control haben ihr eigenes Lifecycle (unconfigured / inactive /
  active), gemanaged über `ros2 control`-CLI nicht `ros2 lifecycle`.
  Plugin trackt aktuellen State selbst (`std::atomic<bool> is_active_`
  in `on_activate`/`on_deactivate` gesetzt) — `get_lifecycle_state()`
  API gibt es nicht auf `rclcpp::Node`.
- **Node-Name lowercase-Konvention** — `<ros2_control name="HexapodSystem">`
  im URDF wird beim Mappen zum ROS-Node-Namen lowercased zu
  `/hexapodsystem`. Wichtig für Stage-C-Topic-Namen (z.B.
  `/servo_pulses`-Topic gehört unter den Plugin-Node-Namespace).
- **`std::mutex` in `Calibration`** funktioniert sauber für Live-Cal
  + Hot-Path-Reads. ~45 µs/s Overhead bei 50 Hz × 18 Joints — nicht
  messbar. Bei Stage C (Topic-Publish-Pfad): selber Mutex schützt auch
  Snapshot-Reads für das Diagnostic-Topic.
- **YAML-Save-Strategie** mit Timestamp-`.bak-YYYY-MM-DDTHH-MM-SS`
  bewährt sich — kein Daten-Verlust auch bei intensiven Cal-Sessions.
  Header-Banner macht klar dass das ein Auto-Save ist und das
  Original im Backup liegt.
- **Atomic-all-or-nothing-Pattern** zweite Phase-11-Stage erfolgreich
  (nach Stage A). Wird auch in Stage D-Pattern (`ros2 param load`-
  Multi-Param-Update von Preset-YAMLs) direkt nutzbar.
- **`PinParamSpec`-Tabelle** als C++-Pendant zum `_GAIT_PARAMS`-
  Tuple aus Stage A funktioniert sauber — Single Source of Truth für
  72 Pin-Params + `_STANDING_ONLY_PARAMS`-Äquivalent
  (`is_active_`-Check pro Direction-Param).
- **Doku-Lesson:** Node-Namen + Lifecycle-CLI im Test-Doku-Pattern
  vorab via `ros2 node list` + `ros2 control list_hardware_components`
  verifizieren statt im Plan auszudenken. Beide Bugs hier im
  User-Smoke entdeckt.

### Übergang Stage C

**Stage C** = `/servo_pulses` Diagnostic-Topic (~0.5 d laut Mutter-Plan).
Plugin publisht die 18 aktuellen Pulse-µs-Werte als ROS-Topic für
Visualisierung in `rqt_plot`.

**Vorbereitung Stage C:**
- Plan-Doku `phase_11_stage_c_plan.md` mit 4 Pflichtinhalten (CLAUDE.md
  §4) inkl. offene Fragen (C-Q1..)
- Klärung: `std_msgs/Int32MultiArray` (einfach) oder Custom-Message
  `HexapodPulses` (sauberer mit Timestamp + per-Pin-Namen)?
- Topic-Rate: 50 Hz (matched controller_manager.update_rate) bestätigt
- Publishing-Pfad: in `write()` direkt (nach `update_servo_cal`-Apply)
  oder separat per Timer?

Phase 11 Stage B — abgeschlossen 2026-05-20.

### Stufe-B-Post-Review (Self-Review vor User-Smoke, 2026-05-20)

| # | Punkt | Status |
|---|---|---|
| 1 | **🔴 Range-Mismatch [800, 2200] vs. YAML-Default 500** entdeckt beim hexapod_bringup-Regression-Test: declare_parameter rejected mit „doesn't comply with integer range" → on_init-FATAL. Fix in Range-Define ([500, 2500] = Firmware-Standard-Servo-Range) | 🔴→OK **gefixt** in [hexapod_system.cpp register_live_cal_params](../src/hexapod_hardware/src/hexapod_system.cpp), Plan-Doku-Range-Wert auch aktualisiert |
| 2 | **F7 — Lifecycle-State-Race:** `is_active_` ist atomic, aber zwischen `on_param_change`-Pre-Check und Apply könnte ein Deactivate dazwischenfunken. Apply mit `update_servo_cal` würde dann mit dem alten "is active"-Verständnis laufen, aber State ist schon inactive. Praktisch irrelevant (Sekunden vs. ms), aber theoretisch möglich | 🟡 vormerken — bei MultiThreaded-Race-Bug-Reports erst diesen Pfad prüfen |
| 3 | **F8 — User-Smoke B-T8 in B-T8a/B-T8b gesplittet** (Plan + test_commands.md) | OK |
| 4 | **get_node()-Null-Tolerance im Unit-Test-Pfad** — `register_live_cal_params()` skippt mit WARN wenn null Node. Konsequenz: Plugin-Level-Unit-Tests im Standalone-Modus testen die Live-Cal-Logik NICHT (test_hexapod_system.cpp). Coverage via test_calibration.cpp (für API selbst) + User-Smoke B-T4..B-T8 (für End-to-End) | 🟡 vormerken — wenn echte Plugin-Param-Tests gewünscht: Mock-Node-Pattern oder launch_testing-Test mit echtem controller_manager (B+-Erweiterung später) |
| 5 | **Save-Service E2E nicht in CI** — Service registriert in on_configure (auch im loopback), aber kein bestehender Test ruft ihn auf. Coverage via User-Smoke B-T7 | 🟡 vormerken — analog Punkt 4: launch_testing-Test mit Service-Call wäre nice-to-have |
| 6 | **Test-Time-Sleep im SaveToFile-Test (2 × 1.1s = 2.2s)** wegen Sekunden-Auflösung der Timestamp-Suffixe — wenn 2 Saves in derselben Sekunde, kollidieren bak-Filenames. Alternative: Mikrosekunden-Auflösung — würde Test schnell machen aber Filenames weniger user-friendly | 🟡 vormerken — bei Test-Slowness-Beschwerden auf µs-Auflösung wechseln |
| 7 | **YAML-Save überschreibt pro-Pin-`status: calibrated`-Marker** — Original-YAML hat pro Pin 15-17 die `status: calibrated` + `calibrated_at: "2026-05-17"` Metadaten aus Phase-10-Stage-I. Save-Output hat `status` + `calibrated_at` nur top-level | 🟢 später — Pro-Pin-Status-Erhaltung ist Polish, evtl. Phase-13-Verbesserung |
| 8 | **Logging-Spam bei Multi-Param-Update** — `ros2 param load` mit 72-Pin-YAML würde 72 INFO-Log-Zeilen erzeugen (eine pro Param). Stage A loggt analog batch-orientiert in einer Zeile (`param updated: <names>`) | 🟢 später — bei User-Lautstärke-Beschwerden auf Batch-Logging analog Stage A umstellen |
| 9 | **Direction-Flip mid-inactive aber pulse_zero ≠ Mittelpunkt** = Servo-Sprung beim nächsten Active. Aktuell akzeptiert. User-Anweisung in README: bei Direction-Wechsel direkt danach pulse_zero validieren (Sichtkontrolle) | 🟢 später — Phase-13-Real-HW-Issue, Software-Fix nicht trivial (würde Pulse-Anpassung beim Direction-Flip erfordern) |
| 10 | **Pin-Lookup im Callback O(N)** — linear search durch `pin_param_specs_` für jeden Param. 72 Specs × 72 max-Params = 5184 max compares pro Multi-Update. Param-Updates passieren <1/s, vernachlässigbar | OK |
| 11 | **save_to_file Snapshot-Race** — Calibration-Snapshot unter Lock, dann YAML-Emit ohne Lock. Wenn Param-Callback während Emit feuert, sieht Emit den Pre-Update-Snapshot. Das ist gewünschtes Verhalten (point-in-time snapshot der Save-Triggerzeit) | OK |
| 12 | **Atomic-Pre-Validation testet alle Cal-Felder im selben Update** — wenn Update z.B. {pin_15.direction_normal, pin_16.pulse_zero} während active: Direction-Reject → BEIDE rejected (atomic-Logik). User-konfusion möglich. README erwähnt das nicht explizit | 🟢 später — bei User-Beschwerde README-Hinweis ergänzen |
| 13 | **🔴 Node-Name-Doku falsch** — Test-Doku schrieb `/controller_manager` als Plugin-Node-Namen, dann `/HexapodSystem`. Realität: ros2_control lowercased zu `/hexapodsystem` (User-Smoke-Discovery 2026-05-20). Da Controller-Manager `allow_undeclared_parameters=true` hat, akzeptierte `ros2 param set /controller_manager pin_15.pulse_zero` ohne Fehler → User-Verwirrung, ob Plugin gehört | 🔴→OK **gefixt** in [phase_11_stage_b_test_commands.md](phase_11_stage_b_test_commands.md) + [hexapod_hardware/README.md](../src/hexapod_hardware/README.md). Fallstrick-Hinweis explizit dokumentiert |

**Self-Review-Ergebnis:** 2× 🔴 gefunden + gefixt (Range-Mismatch via
CI-Regression + Node-Name-Lowercase-Doku via User-Smoke). 4× 🟡
vorgemerkt (Lifecycle-Race, Plugin-Level-Test-Coverage, Test-Sleep,
Save-E2E-Coverage). 4× 🟢 später (pro-Pin-Status-Erhaltung,
Logging-Spam, Direction-Sprung, Atomic-User-Konfusion). Stage B ready
für User-Smoke B-T4..B-T8a/b mit `/hexapodsystem` als Node.

---

## Stufe C — Diagnostic-Topic `/servo_pulses`

**Plan-Doku:** [`phase_11_stage_c_plan.md`](phase_11_stage_c_plan.md)
**Test-Anleitung:** [`phase_11_stage_c_test_commands.md`](phase_11_stage_c_test_commands.md)

Aktiv seit 2026-05-20.

- [x] C.1 Plan-Doku finalisiert + User-Freigabe C-Q1..C-Q5 (2026-05-20)
- [x] C.2 phase_11_stage_c_test_commands.md Skelett (2026-05-20)
- [x] C.3 Header + Imports + Publisher-Member (`pulses_pub_`) + Atomic-Flag (`publish_pulses_enabled_`) (2026-05-20)
- [x] C.4 Publisher + Param-Declaration in `register_live_cal_params` (Default false, IntegerRange für Pin-Params bleibt, neuer Bool-Param `publish_servo_pulses`) (2026-05-20)
- [x] C.5 Param-Callback erweitert (`publish_servo_pulses` early-Branch vor PinParamSpec-Filter, atomic.store + Logger) (2026-05-20)
- [x] C.6 Publish-Block in `write()` mit Doppel-Bedingung (Param-Toggle + `pulses_pub_->get_subscription_count() > 0`) (2026-05-20)
- [x] C.7 CMakeLists.txt + package.xml: `std_msgs`-Dep (2026-05-20)
- [x] C.8 colcon build hexapod_hardware grün (2026-05-20)
- [x] C.9 colcon test: hexapod_hardware 220/0/20 (unverändert; Stage-C-Tests im get_node()-null-Standalone-Pfad skip wie Stage B; E2E via User-Smoke), hexapod_gait 20/0/1, hexapod_bringup 18/0/0 — keine Regression (2026-05-20)
- [x] C.10 README hexapod_hardware Phase-11-Stage-C-Block mit Topic-Beschreibung + rqt_plot-Workflow (2026-05-20)
- [x] C.11 User-Smoke C-T4..C-T7 (2026-05-20): C-T4 ✅ Default false + Topic /hexapodsystem/servo_pulses existiert, C-T5 ✅ Toggle on via `ros2 param set publish_servo_pulses true` + `ros2 topic echo --once` zeigt 18 Pulse-Werte exakt aus YAML-Cal (Pin 15=1550, Pin 16=1533, Pin 17=1539 = leg_6, Pin 0-14=1500 defaults). Subscriber-Check funktioniert wie spezifiziert (count=0 → no publish, sobald echo subscribed wird → Publish startet). rqt_plot/data[N]-Indexing in Jazzy hat einen bekannten Bug (+button bleibt ausgegraut bei Array-Indexing) — Stage-C-Verifikation läuft via CLI, rqt_plot-Bug ist Tool-Limitation nicht Plugin-Bug. Option 1 (CLI-Verifikation reicht) User-gewählt 2026-05-20
- [x] C.12 Self-Review (siehe oben — 0× 🔴, 1× 🟡 Test-Coverage, 1× 🟢 Custom-Msg-Polish) (2026-05-20)
- [x] C.13 Stage-C-Notizen + Übergang Stage D (2026-05-20)

### Stage-C-Notizen (für Stage D + Folge-Phasen)

- **Subscriber-aware-Publish-Pattern bewährt** — `get_subscription_count() > 0`
  als Doppel-Check macht das Plugin null-Cost wenn niemand schaut.
  Plus Live-Param-Toggle (`publish_servo_pulses` default `false`) = User
  hat zwei Hebel.
- **`Int32MultiArray.data[N]`-Indexing in `rqt_plot` (Jazzy) ist
  unzuverlässig** — `+`-Button bleibt ausgegraut. Stage-D-`rqt_setup_doku`
  sollte das explizit als „Limitation" notieren mit den
  Workaround-Optionen (CLI-echo, Topic ohne Index plotten, Phase-13-
  Custom-Msg).
- **Pulse-Werte sind YAML-getreu** — User-Smoke bestätigt `data[15..17]` =
  exakte Cal-Werte aus servo_mapping.yaml. Das ist auch für Phase-13-
  Strom-Profil-Auswertung relevant: Pulse → Servo-Bewegung → Stromaufnahme,
  diese Korrelation läuft sauber durch.
- **Doppel-Bedingung Param + Subscriber** spart auf Pi 4 ~4 KB/s
  (~50 µs CPU-Zeit/s) wenn Cal-Session nicht aktiv ist. Bei dauerhaftem
  Sim-Walking spielt das keine Rolle, aber auf dem Pi nicht egal.
- **Topic-Pfad** `/hexapodsystem/servo_pulses` aus `~/servo_pulses`-
  Relative-Path im Plugin-Node-Namespace expanded. Konsistent mit
  ROS-Namespace-Konvention.

### Übergang Stage D

**Stage D** = rqt-Setup-Doku + Save/Load-Workflow (~1 d).

**Inhalte:**
- `params_file:=`-Arg in 3 Launch-Files (`gait.launch.py`,
  `real.launch.py`, `sim.launch.py`) → Preset-YAMLs ladbar beim Launch
- Preset-Verzeichnis `src/hexapod_gait/config/presets/` mit README
- rqt-Setup-Doku (`docs_raspi/phase_11_rqt_setup.md`) — Multi-Plugin-
  Layout (rqt_reconfigure + rqt_plot + rqt_topic in einer rqt-Perspective),
  Save/Load-Workflow via `ros2 param dump`
- Optional: Bash-Alias-Datei `tools/hexapod-shell-aliases.sh`
  (`hexapod-save-walking-params`, `hexapod-load-preset` etc.)

**Cross-Phase-Pendenzen die Stage D beachten muss:**
- Stage A `_GAIT_PARAMS`-Pattern → `ros2 param dump /gait_node` exportiert
  die 14 Live-Params sauber
- Stage B `pin_*.pulse_*` + `direction_normal` → `ros2 param dump
  /hexapodsystem` exportiert die 72 Cal-Params + den `publish_servo_pulses`
  Stage-C-Toggle
- `set_parameters_atomically`-Semantik für Multi-Param-Load (siehe Stage A
  Test-Patterns) → `ros2 param load` macht das ohnehin atomic

Phase 11 Stage C — abgeschlossen 2026-05-20.

### Stufe-C-Post-Review (Self-Review vor User-Smoke, 2026-05-20)

| # | Punkt | Status |
|---|---|---|
| 1 | Doppel-Bedingung `publish_pulses_enabled_ && subscription_count > 0` schützt vor "Toggle vergessen auszuschalten"-Overhead. Bei Param `true` aber kein Subscriber: Atomic-Load + Funktions-Call ≈ ~10 ns/Tick = 500 ns/s — Faktor 8000 günstiger als Serialization | OK |
| 2 | Publisher lebt immer (kein lazy-create) — Topic ist auch bei Param `false` discoverable via `ros2 topic list`. Das ist gewünschtes Verhalten für `rqt_topic`-Discovery | OK |
| 3 | `Int32MultiArray.data` ist `int32`, aber unsere Pulse sind `int16`. Cast widening, kein Daten-Verlust | OK |
| 4 | Publish-Block VOR dem wire-Send → auch im `loopback_mode_` sieht der Topic Daten (loopback skippt `serial_port_.write_all`). Konsistent für CI/Tests + Bench-Loopback | OK |
| 5 | `publish_servo_pulses`-Param-Update läuft NICHT durch die PinParamSpec-Filter-Schleife (early-Branch) → kein false-Match. Nach Param-Apply gibt es trotzdem das Standard-`successful=true`-Result | OK |
| 6 | Atomic `publish_pulses_enabled_` ↔ `write()`-Read-Path race-frei (atomic.load ≈ memory_order_seq_cst Default). Param-Callback schreibt, write() liest — kein Lock nötig | OK |
| 7 | `publish_servo_pulses`-Param-Update wird im Atomic-all-or-nothing-Block NICHT mit-validiert (eigener early-Branch) — sollte aber konsistent sein, da unkritisch. Kein Cross-Constraint mit Pin-Params | OK |
| 8 | Tests für Stage C: keine neuen Unit-Tests (analog Stage B get_node()-null-Skip). E2E via User-Smoke C-T4..C-T7 | 🟡 vormerken — gleicher Punkt wie Stage-B-Self-Review-4, gleicher Trade-off |
| 9 | rqt_plot bei Multi-Pin-Anzeige (z.B. `data[0], data[3], data[6]...`) zeigt nur die Pin-Indizes, nicht Joint-Namen. User muss YAML konsultieren für Pin→Joint-Mapping | 🟢 später — Custom-Message mit Per-Pin-Joint-Namen wäre Phase-13-Polish (laut Plan-Doku C-Q1 verworfen) |

**Self-Review-Ergebnis:** Keine 🔴, 1× 🟡 (analog Stage B Test-Coverage),
1× 🟢 (Custom-Msg-Polish deferred). Stage C ready für User-Smoke.

---

## Stufe D — rqt-Setup-Doku + Save/Load-Workflow

**Plan-Doku:** [`phase_11_stage_d_plan.md`](phase_11_stage_d_plan.md)
**Test-Anleitung:** [`phase_11_stage_d_test_commands.md`](phase_11_stage_d_test_commands.md)
**Setup-Doku:** [`phase_11_rqt_setup.md`](phase_11_rqt_setup.md)

Aktiv seit 2026-05-20. User-Freigabe D-Q1=A, D-Q2=A, D-Q3=A, D-Q4=B.

- [x] D.1 phase_11_stage_d_plan.md finalisiert + User-Freigabe (2026-05-20)
- [x] D.2 phase_11_stage_d_test_commands.md Skelett (2026-05-20)
- [x] D.3 `params_file`-Arg in gait.launch.py via OpaqueFunction-Pattern (D-Q1 Option A) — Inline-Defaults werden geladen, dann Preset darüber gelegt (rclpy late-precedence) (2026-05-20)
- [x] D.4 Preset-Verzeichnis `src/hexapod_gait/config/presets/` mit README + `defensive_walk.yaml` (manuell kuratiert, langsam-sicher) (2026-05-20)
- [x] D.5 `current_state.yaml` mit aktuellen Stage-A-Defaults committed (statt per ros2 param dump generated — zukünftige Tuning-Sessions überschreiben das) (2026-05-20)
- [x] D.6 `docs_raspi/phase_11_rqt_setup.md`: Multi-Plugin-Layout-Doku, 3 Save-Workflows (Gait + Cal + lokale Perspective), Load-Workflows, rqt_plot-Limitation, Convenience-Aliases-Sektion, kompletter Cal-Session-Workflow (2026-05-20)
- [x] D.7 `tools/hexapod-shell-aliases.sh` mit 5 Bash-Funktionen + selbst-dokumentierendem Top-Kommentar (D-Q3 Option A) (2026-05-20)
  - [x] D.7a Script mit Top-Kommentar (Use-Case, Source-Befehl, Funktions-Tabelle, Beispiel-Workflow) (2026-05-20)
  - [x] D.7b `tools/README.md` als Tools-Verzeichnis-Index (2026-05-20)
  - [x] D.7c „Convenience Aliases (optional)"-Sektion 5 in `phase_11_rqt_setup.md` (2026-05-20)
  - [x] D.7d 2-Zeiler-Pointer in `src/hexapod_gait/README.md` Phase-11-Block (2026-05-20)
  - [x] D.7e 2-Zeiler-Pointer in `src/hexapod_hardware/README.md` Phase-11-Block (2026-05-20)
  - [x] D.7f Memory-Eintrag `project_phase11_convenience_aliases.md` + MEMORY.md-Index (2026-05-20)
- ~~D.8 rqt-Perspective committen~~ — entfällt (D-Q4 Option B: nur Setup-Doku)
- [x] D.9 setup.py erweitert: Preset-YAMLs + README landen im share/hexapod_gait/config/presets/ install-tree (2026-05-20)
- [x] D.10 colcon build + Regression: hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware 220/0/20 — alle grün, kein Regression (2026-05-20)
- [x] D.11 User-Smoke D-T3..D-T7 ✅ (2026-05-20): D-T3 Defaults (implicit), D-T4 params_file-Override (cycle_time=4.0 + Preset-Werte propagieren), D-T5 dump-Roundtrip (`my_test_session.yaml` korrekt erzeugt + reload), D-T6 Bash-Aliases (5 Funktionen vorhanden, `alias_test.yaml` erzeugt), D-T7 rqt-Multi-Plugin-Layout. Plus zwei Doku-Bugs in User-Smoke gefunden + gefixt: (a) `ros2 param dump` in Jazzy hat keine `--output-dir`/`--filename`-Args mehr — Redirect via `>` ist Standard, (b) rqt-Container wird direkt mit `rqt` aufgerufen statt `ros2 run rqt rqt` (Quirk: nur in /opt/ros/jazzy/bin, nicht als ros2-run-executable registriert)
- [x] D.12 Self-Review-Tabelle (siehe unten, 2026-05-20)
- [x] D.13 Stage-D-Notizen + Übergang Stage E (2026-05-20)

### Stage-D-Notizen (für Stage E + Folge-Phasen)

- **`ros2 param dump` Syntax in Jazzy:** kein `--output-dir`/`--filename`
  mehr (gab's in Foxy/Galactic). Nur stdout → Redirect via `>` ist
  Standard. Bei künftigen Param-Dump-Sessions daran denken.
- **`rqt`-Container-Quirk:** Executable liegt in `/opt/ros/jazzy/bin/`,
  nicht unter `lib/<pkg>/`. Direkt mit `rqt` aufrufen (PATH), NICHT
  `ros2 run rqt rqt`. Standalone-Plugins (`rqt_reconfigure`, `rqt_plot`)
  laufen weiter über `ros2 run`.
- **OpaqueFunction-Pattern für conditional Launch-Args** hat sich
  bewährt — saubere Trennung zwischen Plan-Zeit (LaunchArg-Deklaration)
  und Launch-Zeit (Substitution-Evaluation). Stage E könnte das
  Pattern für eigene optionale Test-Args wiederverwenden.
- **Preset-File-Strategie** (Inline-Defaults + späteres params_file =
  Override) ist ROS2-Standard. Wer das nicht weiß könnte fragen
  „warum gewinnen meine YAML-Werte?" — Setup-Doku Sektion 3.1 erklärt
  das explizit.
- **5-fache Discoverability** für tools/hexapod-shell-aliases.sh hat
  sich angefühlt wie Overkill beim Schreiben — aber genau das ist der
  Zweck: jeder Pfad zu Phase-11-Tooling soll das Script finden.
  Bewährt: Memory-Eintrag wird in künftigen Claude-Sessions
  automatisch geladen.
- **Cross-Phase-Pendenzen Stage D schließt:** keine direkt. Stage D
  ist ein "Polish + Workflow"-Stage ohne offene Pendenzen-Liste.
- **Cross-Phase-Pendenzen die Stage D NICHT schließt:**
  - `project_phase10_tibia_length_sim_pending.md` — Sim-Verifikation
    Tibia-Update bleibt für Stage E
  - `project_phase13_initial_pose_presets.md` — Initial-Pose-Presets
    bleiben Phase 13

### Übergang Stage E

**Stage E** = Sim-Tuning-Workshop-Doku + Best-Param-Preset-YAMLs
(~0.5 d laut Mutter-Plan).

**Inhalte:**
- Workshop-Doku `docs_raspi/phase_11_sim_tuning_workshop.md` mit
  Test-Szenarien (langsamer Vorwärts-Walk, schneller Vorwärts,
  Drehen auf der Stelle, Kurvenfahrt, body_height-Variationen,
  Single-Leg-Debug)
- 2-3 weitere Preset-YAMLs in `src/hexapod_gait/config/presets/`:
  z.B. `demo_walk.yaml`, `aggressive_walk.yaml`, evtl.
  `single_leg_3_test.yaml`
- **Cross-Phase-Pendenz:** Sim-Verifikation Tibia-Update aus Phase 10
  (Memory `project_phase10_tibia_length_sim_pending.md`) — Stage E ist
  eine Sim-Session, passt um diese zu erledigen

**Done-Kriterium D:** ✅ erreicht 2026-05-20 — `params_file:=`-Arg in
gait.launch.py funktional (Default + Preset-Override via OpaqueFunction-
Pattern), Preset-Verzeichnis mit `defensive_walk.yaml` +
`current_state.yaml`, vollständige Setup-Doku in
`phase_11_rqt_setup.md` (Multi-Plugin-Layout + 3 Save-Workflows + rqt_plot-
Limitation + Cal-Session-Workflow), Bash-Aliases mit 5 Funktionen + 5-
facher Discoverability, alle Tests grün (20/0/1, 18/0/0, 220/0/20),
User-Smoke D-T3..D-T7 bestätigt.

Phase 11 Stage D — abgeschlossen 2026-05-20.

### Stufe-D-Post-Review (Self-Review vor User-Smoke, 2026-05-20)

| # | Punkt | Status |
|---|---|---|
| 1 | **OpaqueFunction-Pattern für conditional params_file** — Standard ROS2-Launch-Idiom für „wenn LaunchConfiguration leer, skip". Cleaner als IfCondition-Doppel-Node-Pattern | OK |
| 2 | **Inline-Defaults werden explizit zu `float` konvertiert** vor Übergabe an Node — sonst landen sie als Strings im Param-Server und ParameterDescriptor-Validation aus Stage A schmeißt Range-Verletzung (LaunchConfiguration ist immer string) | OK |
| 3 | **`current_state.yaml` ist manuell gepflegt statt dump-generated** — User hat Stage D ohne Live-Session committet, daher kein echter Dump. Bei nächstem Tuning-Session-Save wird die Datei automatisch aktualisiert (oder via hexapod-save-walking-params überschrieben) | 🟡 vormerken — falls Stage-A-Default später ändert, manuelle Sync nötig bis erster echter Dump |
| 4 | **Preset-File ohne führendes `--- yaml-doc-marker`** — ros2 param dump generiert es ohne, daher konsistent | OK |
| 5 | **Stale build/install in src/hexapod_gait** wurden während implementation versehentlich erzeugt (durch python3 -m ament_pep257 mit cd src/hexapod_gait + colcon build aus falschem cwd). Aufgeräumt + .flake8 aus Stage-A-Refactor verhindert dass es Tests bricht | OK — gefangen durch Stage-A-`.flake8`-Schutz |
| 6 | **Bash-Aliases nutzen `${HEXAPOD_WS:-${HOME}/hexapod_ws}`** — User kann via Environment-Variable überschreiben falls anderer Pfad. Documented in Top-Kommentar | OK |
| 7 | **5-fache Discoverability** voll implementiert: File-Top-Kommentar + tools/README.md + phase_11_rqt_setup.md Sektion 5 + 2× Paket-README-Pointer + Memory-Eintrag (D.7a-D.7f) | OK |
| 8 | **rqt-Perspective bewusst nicht committed** (D-Q4 Option B) — Setup-Doku in phase_11_rqt_setup.md beschreibt manuellen Aufbau ausführlich. User-Smoke D-T7 verifiziert dass die Doku klar genug ist | 🟡 vormerken — wenn D-T7 zeigt dass Doku unklar, Plan-Korrektur auf Option A (Perspective doch committen) |
| 9 | **Stage-A-`_GAIT_PARAMS`-Defaults und `current_state.yaml`-Inhalt müssen synchron bleiben** — Drift wenn Stage A erweitert wird ohne `current_state.yaml` zu updaten | 🟡 vormerken — bei Stage-A-Erweiterung beide Stellen mit-updaten |
| 10 | **Preset-Files überschreiben Inline-Defaults durch späteres Auftreten in parameters-Liste** — ROS2-Standard-Pattern, dokumentiert. Wenn User unklar wäre wieso „seine YAML-Werte gewinnen" → README-Hinweis | OK |
| 11 | **Convenience-Aliases nutzen hardcoded `src/hexapod_gait/config/presets/`-Pfad** — bei Repo-Layout-Änderung müsste auch das Script aktualisiert werden | OK aber 🟡 — User könnte selber `$HEXAPOD_PRESETS_DIR` env-var via Override einbauen wenn nötig |
| 12 | **rqt_plot-Limitation Stage C wird in phase_11_rqt_setup.md erwähnt** mit drei Workarounds (CLI-echo, ohne Indexing, Toggle-Test) — User hat das Wissen, kein Setup-Fall mehr | OK |

**Self-Review-Ergebnis:** 0× 🔴, 4× 🟡 (alle minor maintenance-Konsistenz-
Punkte: current_state.yaml-Sync, Perspective-Doku-Klarheit-via-Smoke,
Stage-A-Drift-Risiko, Preset-Pfad-Hardcoded). Stage D ready für
User-Smoke D-T3..D-T7.

---

## Stufe E — Sim-Tuning-Workshop + Best-Param-Presets

> Wird mit Stage-E-Plan-Doku aufgefüllt sobald Stage D fertig ist.

Plus: Sim-Verifikation Tibia-Update (Memory `project_phase10_tibia_length_sim_pending.md`) erledigen.

---

## Stufe F — Phase-11-Abschluss

> Wird mit Stage-F-Plan-Doku aufgefüllt sobald Stage E fertig ist.

**Stages-F-Output (Erwartung):**

- F.1 phase_11_progress.md final
- F.2 README hexapod_gait + hexapod_hardware Phase-11-Quick-Start
- F.3 PHASE.md: Phase 11 → 🟢, Phase 12 (Pi-Plattform) → 🟡
- F.4 Git-Commit + Tag `phase-11-done` (durch User)
- F.5 Retrospektive
