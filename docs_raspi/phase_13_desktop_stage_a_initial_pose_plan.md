# Phase 13 Desktop Stage A — Initial-Pose-Preset "suspended" + Auto-Stand-Pose-Ramp

> **Übergeordneter Plan:** [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md)
> §2 Stage-Übersicht + §7.1 Stage-A-Skeleton.
>
> **Operative Anleitung:** [`phase_13_desktop_stage_a_initial_pose_test_commands.md`](phase_13_desktop_stage_a_initial_pose_test_commands.md).
>
> **Vorbedingung:** Cross-Phase-Thread `servo_real_cal` komplett
> ([`servo_real_cal_plan.md`](servo_real_cal_plan.md) Stages 0..F alle ✅).

---

## 1. Ziel

Zwei zusammenhängende Probleme beheben:

1. **Plugin-Start-Sprung:** aktuell sendet Plugin beim Activate `pulse_zero`
   pro Joint = "horizontale T-Pose". Wenn PSU vorher aus war und die Beine
   nach unten hängen, **springen alle Servos ruckartig** in die T-Pose hoch.
   Das ist nicht nur unschön, sondern stresst Mechanik + Servos.

2. **Übergang zu Stand-Pose nicht kontrolliert:** sobald gait_node startet,
   schickt der erste 50-Hz-Tick die Stand-Pose-IK-Werte als
   JointTrajectory raus. JTC interpoliert über den `time_from_start`-Zeit
   (Default 0.04 s) zur neuen Position → ebenfalls quasi instantan,
   nicht "sanft".

Stage A liefert:
- **Initial-Pose-Preset "suspended"**: Plugin sendet PWMs für "Beine
  hängen frei" beim Activate. Keine ruckartige Bewegung mehr.
- **Auto-Stand-Pose-Ramp**: gait_node fährt sanft (Default 4 s) von der
  aktuellen Joint-Position zur Stand-Pose. Erst danach wird `cmd_vel`
  angenommen.

Das ist die Vorbereitung für alle weiteren Live-Test-Stages (B-E) —
jeder Plugin-Restart wird damit entspannter und sanfter.

## 2. Was Stage A verifiziert

| Aspekt | Verifikations-Mechanismus |
|---|---|
| Plugin lädt YAML-Preset korrekt | Plugin-Init-Log: `loaded initial pose preset 'suspended' from <path>` |
| Plugin sendet Suspended-PWMs beim Activate (statt pulse_zero) | `/joint_states` direkt nach Activate zeigt suspended-rad-Werte; **Beine bleiben unten** (visuell) |
| Auto-Stand-Pose-Ramp läuft im gait_node | `/joint_states`-Echo zeigt smooth lerp über 4 s; gait_node-Log `STARTUP_RAMP → STANDING` |
| `cmd_vel` während Ramp wird ignoriert | gait_node-WARN-Log; Beine bewegen sich nicht zusätzlich |
| Fallback wenn Preset fehlt | Wenn `initial_poses.yaml` fehlt oder Preset-Name unbekannt: Plugin lädt pulse_zero + WARN-Log (Legacy-Verhalten, kein Crash) |
| `use_sim_time:=false` Mini-Fix | gait.launch.py Default auf `false`, HW-Walking-Tests benötigen kein explizites Override mehr |

## 3. Was Stage A NICHT verifiziert (scope-out)

- "resting"-Preset für Boden-Start (kommt später, wenn Floor-Walking-Stage)
- Auto-Stand-Pose-Ramp nach `/hexapod_safety_reset` (Phase-13-Pendenz O7)
- Sanftes REPOSITIONING zwischen Slot-Wechseln (= Stage B-Inhalt)
- Strom-Profil während Ramp (Servos haben aufgebockt eh wenig Last)
- UNDERVOLTAGE_TRIPPED-Recovery ohne Plugin-Restart: aktuell muss bei
  PSU-Off-While-Running ein Plugin-Restart erfolgen (UNDERVOLTAGE_TRIPPED
  ist latched in der FW). Bench-Workflow: PSU aus + Strg+C + Plugin neu
  starten zwischen Tests. Phase 13 Pi-Akku-Workflow ggf. eigene Stage
  (Auto-Recovery via Service `/hexapod_full_recovery` oder Plugin-side
  auto-trigger nach voltage-healthy).
- FW-Side-Optimierung Pendenz: ``handle_set_targets()`` in
  hexapod_servo_driver koennte bei !servo_enabled[i] direkt
  current_pulse_us = target setzen (Soft-Ramp ist Safety nur fuer
  aktive Servos). Wuerde den 400 ms pre-enable-Breather im Plugin
  ueberfluessig machen. Score: ~3 Zeilen FW-Aenderung +
  Co-Versionierung Plugin↔FW.

## 4. Logik-Skizze

### 4.1 YAML-Schema `initial_poses.yaml`

Datei: `src/hexapod_hardware/config/initial_poses.yaml`

```yaml
# Initial-Pose-Presets für hexapod_hardware-Plugin.
# Joint-Werte in URDF-rad-Space. Plugin konvertiert pro Servo zu PWM
# via existing Calibration::radians_to_pulse_us (siehe direction-Map +
# Slope-Formel in calibration.cpp).
#
# Alle 6 Beine bekommen identische rad-Werte. Plugin handhabt die
# direction-Spiegelung pro Servo automatisch (Stage C direction-Map).
#
# Neue Presets können ergänzt werden — Plugin wählt via Launch-Arg
# `initial_pose:=<name>`.

poses:
  suspended:
    description: "Roboter aufgebockt, Beine hängen frei nach unten durch Schwerkraft"
    joints:
      coxa: 0.0       # Bein zeigt radial nach außen, kein horizontaler Schwenk
      femur: 1.45     # Femur fast am oberen mechanischen Anschlag (Stage-F-Limit +1.493). URDF-Achse (0,1,0): +π/2 dreht +X auf -Z → Bein vertikal nach unten. direction-Map spiegelt fuer linke Beine (4/5/6) automatisch.
      tibia: 0.0      # Tibia in Verlängerung des Femurs → ganzes Bein hängt vertikal nach unten

  pulse_zero:
    description: "Legacy: Plugin sendet rad=0 für alle Joints (horizontale T-Pose). Pre-Stage-A-Default."
    joints:
      coxa: 0.0
      femur: 0.0
      tibia: 0.0
```

**Begründung Suspended-Werte:**
- `femur=+1.45` (statt `+1.493 = exakt am Anschlag`): kleine Safety-Margin.
  URDF-femur-Achse ist (0,1,0). Bei rad=0 zeigt der Femur radial nach
  AUSSEN (horizontal, +X-Richtung). Bei rad=+π/2 dreht Y-Rotation +X
  auf -Z (rechte-Hand-Regel) → Bein zeigt vertikal nach UNTEN. rad=+1.45
  ≈ +83° ist nahe diesem Anschlag mit Safety-Margin. direction-Map im
  servo_mapping.yaml (linke Beine 4/5/6 direction=-1) spiegelt
  automatisch zur korrekten Servo-PWM-Richtung. Beim Plugin-Activate
  sendet der Servo seinen Hold-Strom; wenn die Schwerkraft das Bein
  schon nach unten gezogen hat, ist der Servo gerade dort wo er hin
  soll. Strom-Reserve gegen Stall.
- `tibia=0.0`: wenn Femur bei +1.45 rad steht (≈ +83° physisch, fast
  vertikal nach unten), und Tibia bei 0 rad (= in Verlängerung des
  Femurs), hängt das ganze Bein vertikal nach unten. Konsistent mit
  Schwerkraft-Equilibrium.

### 4.2 Plugin-Erweiterung (hexapod_hardware)

Datei: `src/hexapod_hardware/src/hexapod_system.cpp` + Header

**Änderungen:**

1. **Launch-Arg in URDF** (`hexapod.urdf.xacro` + `hexapod.ros2_control.xacro`):
   - Neuer `<xacro:arg name="initial_pose" default="suspended"/>`
   - Plugin-`<param>`-Block in ros2_control.xacro bekommt Eintrag
     `<param name="initial_pose">$(arg initial_pose)</param>` (im
     HW-Pfad)
   - Plus: `<param name="initial_poses_file">$(find hexapod_hardware)/config/initial_poses.yaml</param>`

2. **HexapodSystem-Klasse:**
   - In `on_init` (oder `on_configure`): YAML-File lesen, Preset-Lookup
     für `initial_pose`-Param-Name. Wenn fehlt → fallback auf pulse_zero
     + RCLCPP_WARN
   - Member: `std::array<double, NUM_SERVOS> initial_rad_per_joint_`
   - In `on_activate`: statt aktueller "all pulse_zero" → für jeden
     Joint `initial_rad_per_joint_[i]` durch `Calibration::radians_to_pulse_us`
     konvertieren und als erste PWM-Frame senden

3. **Edge-Cases:**
   - YAML-Parse-Fehler: WARN + fallback pulse_zero
   - Preset-Name nicht in YAML: WARN + fallback pulse_zero
   - Joint-Wert außerhalb URDF-Limit: WARN + clamp auf Limit
   - PWM-OoR nach Konvertierung: Stage-0.5 safety_freeze würde triggern
     → Pre-Validate dass berechnete PWM in `[pulse_min, pulse_max]` liegt

### 4.3 gait_node Auto-Stand-Pose-Ramp

Datei: `src/hexapod_gait/hexapod_gait/gait_node.py` + `gait_engine.py`

**Änderungen:**

1. **Neuer State in `GaitEngine`:**
   - `STATE_STARTUP_RAMP` parallel zu STANDING/WALKING/STOPPING
   - Initial-State bei Engine-Konstruktor: `STARTUP_RAMP` (statt
     STANDING)
   - State-Transition: `STARTUP_RAMP → STANDING` nach Ramp-Ende

2. **Ramp-Logik in `gait_engine.py`:**
   - Methode `start_ramp(initial_joint_positions, duration_s, t_now)`
   - Speichert: `_ramp_start_joints` (dict by leg-name → 3-tuple),
     `_ramp_target_joints` (Stand-Pose-rad), `_ramp_start_t`, `_ramp_duration`
   - In `compute_joint_angles(t)`: wenn STARTUP_RAMP:
     - `progress = (t - _ramp_start_t) / _ramp_duration`
     - Wenn `progress >= 1.0`: state ← STANDING, return target
     - Sonst: linear lerp pro Joint `start + (target - start) * progress`
     - Bonus: Smooth-Step `s = progress*progress*(3 - 2*progress)` für
       sanfteren Übergang ohne harte Endpunkt-Steigung

3. **gait_node-Integration:**
   - Neuer Param `auto_standup_duration` (Default 4.0 s, range
     [1.0, 10.0])
   - Beim ersten `/joint_states`-Empfang: trigger ramp mit aktuellen
     Joint-Positions als Start, default-Stand-Pose als Target
   - Default-Stand-Pose hartkodiert in Stage A (radial=0.295,
     body_height=-0.07); wird in Stage B durch Slot-Lookup ersetzt
   - Engine-State-Check in `_tick`: wenn STARTUP_RAMP, ignoriere
     cmd_vel + throttled WARN-Log (alle 2 s)
   - Stand-Pose-IK passiert wie sonst (`_engine.compute_joint_angles`),
     nur die State-Machine wählt zwischen Ramp-Lerp und normalem
     STANDING-IK

4. **gait.launch.py Mini-Fix:**
   - `default_value='true'` → `default_value='false'` für `use_sim_time`
   - Sim-Doku (`servo_real_cal_stage_e_sim_test_commands.md`) updaten
     dass `use_sim_time:=true` jetzt explizit gesetzt werden muss

### 4.4 Aufruf-Reihenfolge in real.launch.py

Stage A nutzt die existing `OnProcessExit`-Pattern:

```
real.launch.py:
  1. robot_state_publisher (mit URDF inkl. initial_pose-Arg)
  2. ros2_control_node (lädt Plugin → on_init → liest initial_poses.yaml)
  3. spawn_joint_state_broadcaster
  4. OnProcessExit (JSB-Spawner exited)
     → 6 leg_<n>_controller-Spawner
  5. (NEU optional in Stage A) OnProcessExit (letzter leg-Spawner exited)
     → gait_node mit korrektem robot_description_file + use_sim_time:=false
```

→ gait_node startet **erst nachdem alle JTCs aktiv sind**. Plugin hat
schon `on_activate` durchlaufen und Suspended-PWMs gesendet. gait_node
erhält dann `/joint_states` und startet den Ramp.

**Alternative (einfacher):** gait_node bleibt in `gait.launch.py`,
User startet beide Launches manuell hintereinander. Stage A real.launch.py
bleibt unverändert. **Vorschlag A-Q7:** gait_node-Integration in
real.launch.py auf später (z.B. Stage E) verschieben — für Stage A
reicht manueller Start in T2 wie in E2/F.

## 5. Tests-Liste mit Begründung

### 5.1 Unit-Tests (CI-tauglich, Pure-Python)

| # | Test | Begründung |
|---|---|---|
| T1 | `test_initial_pose_yaml_load` | YAML parsing + Preset-Lookup funktioniert; Fehlerfälle (missing file, unknown preset) liefern dokumentiertes Fallback-Verhalten |
| T2 | `test_initial_pose_pwm_conversion` (Plugin-side, GTest) | rad-Werte aus Preset → PWM via Calibration → in [pulse_min, pulse_max]-Range pro Pin |
| T3 | `test_startup_ramp_linear_lerp` | Lerp ist linear (mit Smooth-Step optional); Endpunkt = target nach `duration` |
| T4 | `test_startup_ramp_state_transitions` | Engine startet in STARTUP_RAMP → wechselt zu STANDING nach Ramp-Ende |
| T5 | `test_startup_ramp_ignores_cmd_vel` | `set_command()` während STARTUP_RAMP ändert nichts an Engine-State; WARN wird geloggt |
| T6 | `test_startup_ramp_duration_clamp` | `auto_standup_duration` außerhalb [1.0, 10.0] wird auf Range geclamped |
| T7 | `test_initial_pose_missing_yaml_fallback` | Plugin-side: wenn YAML fehlt → fallback pulse_zero, kein Crash |

### 5.2 Live-Tests (interaktiv, HW aufgebockt)

| # | Test | Begründung |
|---|---|---|
| L1 | PSU aus → Beine hängen frei → PSU an + Plugin-Start → **Beine bleiben unten** | Direkt-Verifikation des Stage-A-Ziels: kein Sprung |
| L2 | Nach Plugin-Activate: `ros2 topic echo --once /joint_states` zeigt suspended-rad-Werte | Plugin sendet Preset-PWMs korrekt |
| L3 | gait_node startet → Beine fahren sanft in ~4 s zur Stand-Pose | Auto-Stand-Pose-Ramp visuell |
| L4 | Während Ramp: cmd_vel publish → Beine bewegen sich nicht zusätzlich; gait_node-WARN sichtbar | cmd_vel-Block während Ramp |
| L5 | Nach Ramp: cmd_vel funktioniert wie gewohnt (E2/F-Verhalten) | Normale Walking-Funktionalität nicht kaputt |
| L6 | `initial_pose:=pulse_zero` Launch-Arg → Legacy-Verhalten (T-Pose, ruckhaft) | Fallback-Pfad funktional |
| L7 | `initial_poses.yaml` umbenannt → Plugin startet mit WARN + pulse_zero | Robustheit bei fehlendem File |

### 5.3 Bewusst NICHT getestet (scope-out)

- Strom-Profil während Ramp — aufgebockt minimal, Boden-Walking-Stage prüft das
- "resting"-Preset für Floor — eigene Stage
- Auto-Stand-Pose-Ramp nach Safety-Reset (Phase-13-Pendenz)

## 6. Progress-Checkliste

Wird in Stage A-Plan nach Live-Test als `phase_<n>_progress`-Stil
abgehakt:

- [ ] A.1 YAML-File `src/hexapod_hardware/config/initial_poses.yaml` mit
      `suspended` + `pulse_zero` Presets erstellt
- [ ] A.2 URDF + ros2_control.xacro: `initial_pose`-Launch-Arg +
      `<param>` für Plugin
- [ ] A.3 Plugin C++-Erweiterung: YAML-Loader + on_activate-Hook +
      PWM-Pre-Validate
- [ ] A.4 Plugin Unit-Tests (T2, T7) grün
- [ ] A.5 gait_engine `STATE_STARTUP_RAMP` + `start_ramp()`-Methode
- [ ] A.6 gait_node Param `auto_standup_duration` + Ramp-Trigger bei
      erstem `/joint_states`-Empfang
- [ ] A.7 gait_node ignoriert cmd_vel während Ramp (WARN-Log)
- [ ] A.8 Pure-Python Unit-Tests (T1, T3-T6) grün
- [ ] A.9 `gait.launch.py` `use_sim_time`-Default auf `false` umgestellt
- [ ] A.10 Sim-Test-Commands-Doku updated: `use_sim_time:=true` jetzt
      explizit
- [ ] A.11 Live L1: PSU-an + Plugin-Start → keine ruckartige Bewegung
- [ ] A.12 Live L2: `/joint_states` zeigt suspended-Werte
- [ ] A.13 Live L3: gait_node-Ramp visuell sanft, ~4 s
- [ ] A.14 Live L4: cmd_vel während Ramp blockt
- [ ] A.15 Live L5: Walking nach Ramp wie E2/F
- [ ] A.16 Live L6: `initial_pose:=pulse_zero` Fallback
- [ ] A.17 Live L7: missing YAML Fallback
- [ ] A.18 Self-Review-Tabelle ausgefüllt
- [ ] A.19 Memory-Update: `project_phase13_gait_launch_sim_time_default.md`
      als ✅ (durch use_sim_time-Default-Fix)
- [ ] A.20 Memory-Update: `project_phase13_initial_pose_presets.md` als
      ✅ (durch Stage A umgesetzt)
- [ ] A.21 `phase_13_desktop_pre_bringup_plan.md` Stage A → ✅

## 7. Offene Punkte für User-Review (mit Vorschlägen)

| # | Frage | Vorschlag |
|---|---|---|
| A-Q1 | Suspended-Joint-Werte: `femur=+1.45` (mit Safety-Margin) oder `+1.493` (am Anschlag)? | **+1.45** — kleine Reserve gegen Servo-Stall. Plugin-Strom-Limit bietet zusätzliche Sicherheit. Vorzeichen POSITIV: URDF-femur-Y-Achse, +π/2 dreht +X auf -Z (Bein nach unten) — siehe Begründung §4.1 |
| A-Q2 | Auto-Stand-Pose-Ramp lebt in gait_node ODER neues separates `auto_standup_node`? | **gait_node** — kleiner Zustand, integriert sich sauber in State-Machine; vermeidet extra Node-Lifecycle |
| A-Q3 | Trigger für Ramp: Plugin-Activate-Detection ODER explicit Topic/Service ODER beim ersten `/joint_states`? | **Bei erstem `/joint_states`-Empfang** — robust, kein extra Service nötig, funktioniert auch nach Plugin-Restart |
| A-Q4 | Default-Slot-Stand-Pose: in Stage A hartkodiert oder schon aus LUT? | **Hartkodiert** (radial=0.295, body_height=-0.07) — LUT kommt erst in Stage B. Konstanten in gait_node-Params, später durch Slot-Lookup ersetzt |
| A-Q5 | Verhalten wenn cmd_vel während Ramp kommt? | **Ignorieren + WARN-Log** (throttled 2 s). Kein cmd_vel-Queue, User soll warten bis Ramp fertig |
| A-Q6 | `use_sim_time`-Fix als Stage-A-Item oder eigener Mini-Commit vorher? | **Mit-Stage-A** — 5 min Aufwand, gehört thematisch zur Initial-Setup-Klärung |
| A-Q7 | Aufruf-Reihenfolge: gait_node-Integration in real.launch.py oder weiterhin manueller Start? | **Manueller Start in T2** — wie E2/F. real.launch.py-Integration ist eigene Stage später (z.B. Stage E nach PS4-Vollbetrieb-Test) |
| A-Q8 | Smooth-Step-Ramp ODER reiner linearer Lerp? | **Smooth-Step** (`s = p²(3-2p)`) — Start + End sanfter (Geschwindigkeits-Null an beiden Enden), kein zusätzlicher Aufwand |

## 8. Risiken & Mitigations

| # | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | Suspended-rad-Werte produzieren PWM außerhalb [pulse_min, pulse_max] | gering (Werte innerhalb URDF-rad-Limits) | Plugin Pre-Validate vor on_activate: berechne PWM, vergleiche mit Range, WARN+fallback wenn out-of-bounds |
| R2 | Ramp-Default-Stand-Pose unerreichbar für IK | sehr gering (= aktuelle sim_walk-Werte) | Sanity-Test in gait_node-Init: IK mit Default-Werten probieren, WARN wenn nicht erreichbar |
| R3 | gait_node startet bevor Plugin `on_activate` fertig → `/joint_states` initial leer | mittel | Engine `STATE_STARTUP_RAMP` triggert erst beim ersten `/joint_states`-Empfang (nicht beim Node-Start). Bis dahin: keine Trajectory-Publishes |
| R4 | `use_sim_time:=false`-Default bricht Stage-E-Sim-Tests | mittel | Sim-Test-Commands-Doku updaten (`use_sim_time:=true` explizit) + Memory `project_phase13_gait_launch_sim_time_default.md` schließen |
| R5 | Plugin-Loop in Endlos-WARN wenn YAML fehlt | gering | Einmaliges WARN beim on_init, dann silent fallback. Keine Loop. |
| R6 | Ramp zu schnell visuell wirkt immer noch ruckhaft | mittel | Default 4 s; User kann live `ros2 param set /gait_node auto_standup_duration 6.0` setzen für sanfteren Übergang |

## 9. Self-Review

### 9.1 Code-Review (vor Live, 2026-05-28)

| Punkt | Status | Detail |
|---|---|---|
| Plugin: YAML-Loader best-effort, kein throw aus on_init | OK | `load_initial_pose_preset()` fängt YAML-Parse-Errors, missing-File, unknown-Preset jeweils mit WARN + Fallback pulse_zero pro Pin |
| Plugin: Pre-Validate PWM ∈ [pulse_min, pulse_max] | OK | Pro Pin OoR-Check mit ±1 µs FP-Tolerance (analog write()-Pfad); OoR → WARN + Fallback pulse_zero für den Pin (verhindert Stage-0.5 freeze beim Activate) |
| Plugin: on_activate sendet `initial_pulse_us_` statt `pulse_zero` | OK | last_command_pulse_us_ wird nach send synchronisiert → read() echoed direkt die Initial-Pose |
| Plugin: missing `initial_poses_file` Param (= empty) | OK | `param_or` Default "" → load-Funktion sieht leer → WARN + Fallback pulse_zero, kein Crash |
| Engine: cmd_vel-Block in STARTUP_RAMP | OK | `set_command` returnt sofort `False` ohne State-Mutation oder v_body-Update |
| Engine: STARTUP_RAMP → STANDING auto-transition | OK | `_compute_startup_ramp_angles` setzt `_state = STANDING` bei progress >= 1, returnt Endpunkt |
| Engine: Smooth-Step-Math `s = p²(3-2p)` | OK | Unit-Tests `test_startup_ramp_midpoint_is_lerp_average` (s(0.5)=0.5) + `test_startup_ramp_smooth_step_monotonic` (nicht-fallend) |
| Engine: fehlende Beine in start_joints | OK | Start = Target → keine Bewegung; Test `test_startup_ramp_missing_legs_fall_back_to_target` |
| Engine: Stand-Pose nicht erreichbar | OK | `start_ramp` lässt IKError aus `_compute_stand_pose_joints` durch; gait_node fängt `(ValueError, IKError)` und markiert ramp_triggered=True ohne State-Change |
| gait_node: erstes `/joint_states` triggert Ramp | OK | `_on_joint_states` parsed alle 18 Joints, return early bei unvollständig (wartet auf nächste Msg) oder bei `_ramp_triggered` |
| gait_node: pre-Ramp keine Trajectories publishen | OK | `_tick` returnt early wenn `not _ramp_triggered`; verhindert dass JTC den Start-Punkt auf Stand-Pose-IK setzt statt vom realen Joint-State zu rampen |
| gait_node: /joint_states-Timeout-Warning | OK | 10 s Timeout → einmaliger ERROR-Log via `_joint_states_timeout_logged`-Flag; gait_node bleibt am Leben |
| gait_node: cmd_vel-WARN throttled 2 s | OK | nur wenn STARTUP_RAMP aktiv UND cmd_vel != 0 |
| gait_node: STARTUP_RAMP→STANDING Log einmal | OK | state-before / state-after Vergleich pro Tick, INFO-Log nur bei Transition |
| Test-Commands: SCHRITT 1 entfernt | OK | Pre-Stage-A-Reproduktion wird durch SCHRITT 6 (L6 pulse_zero) abgedeckt |
| Test-Commands: Sauber-Beenden + PSU-Reset zwischen Tests | OK | Pflicht-Block vor SCHRITT 1, 6, 7 — verhindert "Servo noch in alter Pose vom letzten Test" |
| Test-Commands: Wartezeiten (~5 s nach PSU-an, ~5 s nach gait_node-Start für Ramp-Ende) | OK | In SCHRITT 1, 3, 5 dokumentiert |
| `gait.launch.py` use_sim_time Default false | OK | Default `'false'`; Sim-Test-Commands (servo_real_cal_stage_e_sim_test_commands.md) hatten schon `use_sim_time:=true` explizit, kein Doku-Update nötig |
| colcon build hexapod_hardware + hexapod_gait | OK | grün 2026-05-28 |
| colcon test hexapod_hardware: 238 grün | OK | inkl. 5 neue `InitialPosePreset.*` Tests |
| colcon test hexapod_gait: 39 grün | OK | inkl. 11 neue `test_startup_ramp` Tests (alle T3-T6 + Edge-Cases) |

### 9.2 Live-Test (vom User auszufüllen)

| Punkt | Status | Detail |
|---|---|---|
| L1: keine ruckartige Bewegung beim Plugin-Start | (offen) | |
| L2: /joint_states zeigt suspended-Werte | (offen) | |
| L3: 4-s-Ramp sanft sichtbar | (offen) | |
| L4: cmd_vel-Block während Ramp | (offen) | |
| L5: Walking nach Ramp wie E2/F | (offen) | |
| L6: pulse_zero-Fallback funktional | (offen) | |
| L7: missing-YAML-Fallback funktional | (offen) | |
| `use_sim_time:=false`-Default geprüft | (offen) | |

## 10. Was passiert wenn alles grün

- Memory `project_phase13_initial_pose_presets.md` als ✅ markieren
- Memory `project_phase13_gait_launch_sim_time_default.md` als ✅
- `phase_13_desktop_pre_bringup_plan.md` Stage A → ✅
- PHASE.md updaten (Cross-Phase-Thread-Status oder neuer Phase-13-Desktop-Status)
- Bereit für Stage B (LUT-Infrastruktur)

## 11. Was passiert wenn Probleme

| Problem | Aktion |
|---|---|
| Plugin lädt YAML nicht | YAML-Pfad in URDF-`<param>` prüfen; Plugin-Logs auf Parse-Error |
| Beine springen trotzdem hoch | Suspended-rad-Werte → PWM-Berechnung manuell durchrechnen; vergleichen mit aktueller Plugin-PWM beim Activate |
| Ramp ruckhaft trotz 4 s | Smooth-Step aktiv? Tick-Rate 50 Hz konstant? gait_node-Log auf Skipped-Ticks prüfen |
| cmd_vel-Block geht nicht | Engine-State im gait_node loggen; prüfen ob `set_command()` State-Check macht |
| `use_sim_time`-Fix bricht Sim | Sim-Test-Commands-Doku überprüfen, ggf. Sim-Launches mit `use_sim_time:=true` explizit |

---

**Erstellt 2026-05-28.** Operative Anleitung liegt in
[`phase_13_desktop_stage_a_initial_pose_test_commands.md`](phase_13_desktop_stage_a_initial_pose_test_commands.md).
