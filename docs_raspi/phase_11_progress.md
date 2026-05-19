# Phase 11 — Progress-Tracker

**Phase:** Param-GUI mit Live-Tuning (rqt_reconfigure)
**Plan:** [phase_11_param_gui.md](phase_11_param_gui.md)
**Aktiv seit:** 2026-05-19

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

### D. Plugin-Live-Cal: `/servo_pulses` Diagnostic-Topic

- **Final:** Plugin publiziert 18 Pulse-µs-Werte als ROS-Topic für
  rqt_plot-Visualisierung
- **Plus:** Plugin-Live-Param-Callback für pulse_min/zero/max/direction
  → Live-Servo-Cal via rqt_reconfigure möglich

---

## Stufe A — gait_node Param-Callback

> **Vorab-Plan:** [`phase_11_stage_a_plan.md`](phase_11_stage_a_plan.md)
> (wird bei Stage-A-Start angelegt)

- [ ] A.1 phase_11_stage_a_plan.md (Plan-Doku) finalisiert + User-Freigabe
- [ ] A.2 phase_11_stage_a_test_commands.md angelegt
- [ ] A.3 gait_node `on_set_parameters_callback` registriert
- [ ] A.4 ParameterDescriptor mit Range für alle gait-Params
- [ ] A.5 Param-Callback updated Live-State (body_height, step_height,
       cycle_time, tick_rate, radial_distance, step_length_max,
       gait_pattern, etc.)
- [ ] A.6 Edge-Case-Handling (Param-Wechsel während WALKING)
- [ ] A.7 Unit-Tests für Param-Validation + Live-Updates
- [ ] A.8 launch_testing-Smoke mit Param-Updates
- [ ] A.9 User-Smoke: rqt_reconfigure öffnen, Slider verschieben in Sim
- [ ] A.10 Self-Review (CLAUDE.md §4-Pflicht)
- [ ] A.11 User-Commit

**Done-Kriterium A:** [TBD nach Implementation]

---

## Stufe B — hexapod_hardware Plugin Live-Cal

> Wird mit Stage-B-Plan-Doku aufgefüllt sobald Stage A fertig ist.

---

## Stufe C — Diagnostic-Topic `/servo_pulses`

> Wird mit Stage-C-Plan-Doku aufgefüllt sobald Stage B fertig ist.

---

## Stufe D — rqt-Setup-Doku + Save/Load-Workflow

> Wird mit Stage-D-Plan-Doku aufgefüllt sobald Stage C fertig ist.

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
