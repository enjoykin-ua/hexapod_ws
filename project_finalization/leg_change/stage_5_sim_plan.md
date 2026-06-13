# Stage 5 (Sim/Gazebo) — Plan (Bein-Umbau `leg_changes`)

> **Vorgänger:** S4 (Re-Param) ✅ — Produktiv-Posen eingetragen, alle gait-Tests
> grün (204/0/28skip). **Diese Stage = S5 (Sim).** Danach S6 (HW-Desktop).
> **Plan nach CLAUDE.md §4** — User-Freigabe einholen BEVOR Code/Sim läuft.
> Live-/Sim-Befehle stehen vollständig in
> [`stage_5_sim_test_commands.md`](stage_5_sim_test_commands.md),
> nicht im Chat ([[feedback_test_commands_in_doc_not_chat]]).

---

## 0. Ziel dieser Stage (User-Vorgabe verfeinert)

Die mathematische Validierung (S3 Envelope) und die Test-Migration (S4) sind durch.
S5 ist die **visuelle/physikalische Bestätigung in Gazebo + RViz** — Gazebo ist
lenient und versteckt IK-Freeze/out-of-reach, deshalb war `test_stance_switch`
(real-engine) schon die härtere Wahrheit; S5 zeigt, ob es **physikalisch** stabil ist.

**Konkretes User-Ziel:**
1. **Eine solide „mittlere" Höhe** finden, auf der der Roboter **stabil im Tripod
   läuft** UND auf die er **stabil aufsteht**. Falls direktes Aufstehen auf die
   Lauf-Pose nicht sauber geht: der bestehende **Zwei-Phasen-Aufsteh-Mechanismus
   mit Zwischen-Reposition** (`standup_radial_distance` → Tripod-Reposition →
   `radial_distance`) wird genutzt — genau wie früher bei den langen Beinen.
2. **Veraltete Höhen/Presets löschen** (alle aktuellen Presets haben alte radii
   0.215–0.295 → mit den kurzen Beinen out-of-reach).
3. Modell visuell + Reachability-Viz verifizieren (Checklisten-Bullet 5.3).

> **Mechanismus existiert bereits** (kein neuer Code nötig): `standup_radial_distance`
> (0.17, breite touchdown-sichere Aufsteh-Pose) ≠ `radial_distance` (0.145, mittel-
> Walk-Pose) → die Engine repositioniert nach dem Aufstehen automatisch per Tripod
> (`reposition_cycle_time` 2.0 s). S5 prüft, ob dieser Pfad in Sim **schürffrei +
> kippfrei** ist und tuned ggf. `standup_radial` / `reposition_cycle_time` / die
> mittel-radii nach.

---

## 1. Logik-Skizze / Ablauf (was passiert, in welcher Reihenfolge, warum)

S5 ist überwiegend **Verifikation** (keine Engine-Logik-Änderung — `gait_engine.py`
ist wertneutral). Code/Config wird nur an drei Stellen angefasst: (a) Preset-Cleanup,
(b) evtl. Fein-Tuning der mittel-Params falls Sim es verlangt, (c) `sim_walk.yaml`
neu generieren. Reihenfolge bewusst „erst gucken, dann anfassen":

```
S5.1  Modell-Visual-Check
        ros2 launch hexapod_bringup sim.launch.py
        → Gazebo: 6 Beine kurz (Femur 0.060 / Tibia 0.134), keine Mesh-/URDF-Fehler,
          Bauch nahe Boden in power_on_mid-Spawnpose (spawn_z 0.05).
        ros2 launch hexapod_description display.launch.py   (RViz, reines Modell)
        → tf2-Baum vollständig, keine fehlenden Frames, Proportionen plausibel.
        WARUM zuerst: ein falsches Modell macht jeden weiteren Sim-Test wertlos.

S5.2  Reachability-Viz
        ros2 launch hexapod_gait reachability_viz.launch.py
        → erreichbare Fuß-Hülle (blau=aktuelles Limit) konsistent mit neuem
          reach-Band d ∈ [0.074, 0.194]. Mittel-Pose (radial 0.145 @ bh -0.10)
          liegt sichtbar INNERHALB der Hülle, mit Marge zum Rand.
        WARUM: visueller Gegencheck der S3-Mathe, bevor wir die Engine drauf loslassen.

S5.3  Aufstehen in Sim (Zwei-Phasen + Reposition)
        Sim-Stack + gait_node (use_sim_time:=true), Boot → /hexapod_stand_up.
        Erwartung: cartesian Touchdown (standup_radial 0.17) → senkrechter Push
          → Tripod-Reposition auf mittel (radial 0.145). Bauch hebt sauber ab,
          Füße schürfen nicht hörbar/sichtbar nach innen, kein Kippeln.
        Falls direktes Aufstehen (standup_radial == radial) probiert werden soll:
          nur wenn Sim zeigt, dass der Femur dabei nicht an die ±-Wand läuft.
        Tuning-Hebel falls instabil: standup_radial ↑ (mehr Touchdown-Marge),
          reposition_cycle_time ↑ (langsamer = kippärmer), standup_phase1_fraction.

S5.4  Tripod-Lauf @ mittel
        Aus STANDING: cmd_vel forward / sidestep / yaw / diagonal.
        Erwartung: stabiler Tripod, kein IK-OutOfReach-WARN-Spam, kein Body-Wobble
          über das tripod-typische Maß (Nicht-Tripod-Wackeln ist bekannt + scope-out,
          [[project_nontripod_gait_wobble]]). Stride bis step_length_max 0.03.
        Tuning-Hebel: step_height (0.04 Start), step_length_max (0.03 Start) via
          walking_envelope_check recommend / --optimize-step-height nachziehen.

S5.5  Param-Finalisierung (mittel zuerst)
        Aus S5.3/S5.4: finale Werte für mittel (radial/body_height/step_height/
          step_length_max), standup_radial, reposition_cycle_time, _SIT_SAFE_MIN_BH
          (tiefste direkt-Sit-bh real-engine). 2-vs-3-Höhen-Entscheid (D4): mittel
          ist Pflicht; tief/hoch nur behalten, wenn sie in Sim ebenfalls sauber
          aufstehen+laufen, sonst auf mittel reduzieren (Code-Kommentar dokumentiert).
        Synchron halten (goldene Regel S4): gait_node.py _STANCE_MODES[1] ==
          _GAIT_PARAMS-Defaults == gait.launch.py == stand.launch.py == teleop
          body_height_init. Bei jeder Änderung alle 4 Quellen mitziehen.

S5.6  Preset-Cleanup (User-Entscheid: 4 Stile aktualisieren, 3 Artefakte löschen)
        AKTUALISIEREN (neue Geometrie, Charakteristik erhalten):
          - sim_walk    → mittel-Lauf-Pose (kanonisch + Test-Anker, regen via Tool)
          - defensive_walk → langsam-sicher (große cycle_time, kleine Schritte; für S6-HW)
          - demo_walk   → sichtbarer Lauf (etwas höherer step_height)
          - aggressive_walk → schneller Stil (kleinere cycle_time, größerer Stride)
          feet_closer_walk → geht in sim_walk auf (Konzept obsolet, alle Posen jetzt
            feet-closer) → LÖSCHEN.
        LÖSCHEN (Wegwerf-Artefakte ohne kuratierte Absicht, von keinem Test referenziert):
          - current_state.yaml (war param-dump-Snapshot)
          - alias_test.yaml / my_test_session.yaml (Save/Load-Alias-Test-Fixtures)
        tools_catalog.md + ai_navigation.md Preset-Liste nachziehen.
```

### Berührte Dateien (Erwartung — final nach S5.5 fix)
| Datei | Änderung | Quelle/Sync |
|---|---|---|
| `gait_node.py` `_STANCE_MODES` / `_SIT_SAFE_MIN_BH` / step-Defaults | nur falls Sim Tuning verlangt | Zentralstelle |
| `gait.launch.py` / `stand.launch.py` | synchron zu obigem | 2./3. Limit-/Pose-Quelle |
| `joy_to_twist.py` + `ps4_*.yaml` | nur falls body_height_init/Schranken sich ändern | teleop-Sync |
| `config/presets/{sim_walk,defensive_walk,demo_walk,aggressive_walk}.yaml` | aktualisiert (neue Geometrie) | sim_walk = Test-Anker |
| `config/presets/{feet_closer_walk,current_state,alias_test,my_test_session}.yaml` | gelöscht | feet_closer → sim_walk |
| `project_architecture/tools_catalog.md` + `ai_navigation.md` | Preset-Liste nachziehen | Doc-Sync |
| `test_commands.md` (Teil S5) | Sim-Befehle final | interaktive Anleitung |

> Falls S5.1–S5.4 zeigen, dass die S4-Startwerte (mittel 0.145/-0.10, step 0.04/0.03,
> standup_radial 0.17) bereits stabil sind: **keine Code-Änderung an den Posen** —
> dann beschränkt sich S5 auf Verifikation + Preset-Cleanup + `sim_walk.yaml`.

---

## 2. Tests-Liste (Done-Marker) + bewusst NICHT getestet

**Automatisiert (CI-fähig, ich führe aus):**
- `colcon test --packages-select hexapod_gait` bleibt **204/0/28skip** — kein Regress
  durch evtl. Param-Tuning (falls Posen geändert: betroffene Test-Konstanten mit-migrieren).
- `colcon test --packages-select hexapod_kinematics` bleibt **36/0**.
- `colcon test --packages-select hexapod_teleop` bleibt grün (falls teleop-Sync nötig).
- `python3 -m pytest tools/test_walking_envelope_check.py` grün — **sim_walk.yaml
  regeneriert** → `test_check_envelope_sim_preset_forward_green` wieder GRÜN
  (aktuell würde es mit alter sim_walk RED).

**Live-Sim (User führt aus, knappe Status-Meldung — `stage_5_sim_test_commands.md`):**
- S5-T1 Gazebo-Spawn: Modell korrekt, keine URDF/Mesh-Fehler in Konsole.
- S5-T2 RViz display: tf2 vollständig, Proportionen plausibel.
- S5-T3 Reachability-Viz: Hülle konsistent, mittel-Pose innerhalb mit Marge.
- S5-T4 Aufstehen: Bauch hebt ab, Reposition auf mittel, schürffrei, kippfrei.
- S5-T5 Tripod-Lauf: forward/sidestep/yaw/diagonal stabil, kein IK-WARN-Spam.

**Bewusst NICHT getestet (scope-out, dokumentiert):**
- **Strom/Drehmoment-Beweis** — Sim-Physik ≠ echter Servo-Strom. Erst S6/Boden
  (Handover S4 §Self-Review „🟢 später"). S5 ist kinematisch/visuell.
- **HW (aufgehängt/Boden)** — S6/S7.
- **Nicht-Tripod-Gangarten (wave/tetrapod/ripple)** Wackel-Feintuning — bekannt
  open-loop-instabil ([[project_nontripod_gait_wobble]]), echter Fix = A5 IMU. S5
  prüft nur, dass sie **ohne IK-Freeze** laufen, nicht dass sie wackelfrei sind.
- **tief/hoch final am Boden** — D4-Entscheid in Sim getroffen, HW-Bestätigung S6.
- **Terrain/Foot-Contact** — Block E2.

---

## 3. Progress-Checkliste (Done-Vertrag — nach Implementierung in plan.md §5 abhaken)

> Aktualisiert die `plan.md`-Bullets **5.3** und **6.1–6.4**. Pro erledigtem Bullet
> sofort `[ ]`→`[x]`, nicht batchen ([[feedback_phase_progress_tracking]]).

```
### S5 — Sim/Gazebo
- [ ] 5.3a Gazebo-Spawn: Modell visuell korrekt (kurze Beine), keine Mesh-/URDF-Fehler
- [ ] 5.3b RViz display + Reachability-Viz: tf2 vollständig, Hülle plausibel, mittel-Pose mit Marge
- [ ] 6.1  Stand-Pose mittel (radial/body_height) in Sim bestätigt (stabil aufgestanden)
- [ ] 6.2  Aufsteh-Pfad: Zwei-Phasen + Reposition schürffrei/kippfrei; standup_radial + reposition_cycle_time final
- [ ] 6.2b _SIT_SAFE_MIN_BH real-engine bestimmt; 2-vs-3-Höhen-Entscheid (D4) dokumentiert
- [ ] 6.3  Tripod-Lauf @ mittel stabil (forward/sidestep/yaw/diagonal, kein IK-Freeze); step_height/step_length_max final
- [ ] 6.5  Preset-Cleanup: sim_walk.yaml regeneriert (Test grün), veraltete Presets gelöscht, tools_catalog/ai_navigation nachgezogen
- [ ] 6.6  colcon test gait/kinematics/teleop kein Regress; pytest tools/ grün
- [ ] 6.7  Self-Review-Tabelle (CLAUDE.md §4) + test_commands.md Teil S5 final
```
(6.4 Show-CoG entfällt — Show ist aus diesem Thread raus, S4.)

---

## 4. Entscheidungen (vom User bestätigt — Plan gelockt)

1. **Presets:** 4 kuratierte Stile **aktualisieren** (sim_walk/defensive/demo/
   aggressive auf neue Geometrie umrechnen, Charakteristik erhalten); 3 Wegwerf-
   Artefakte **löschen** (current_state/alias_test/my_test_session); feet_closer →
   in sim_walk aufgehen lassen. sim_walk bleibt Test-Anker (grün).

2. **2 vs 3 Stance-Höhen (D4):** **mittel voll validieren**, tief/hoch in Sim **mit
   dem bestehenden Teleop mitprüfen**. Nur behalten, was sauber aufsteht+läuft; sonst
   reduzieren (mittel allein oder mittel+tief). Final am Boden (S6) gegenchecken.

3. **Aufsteh-Strategie:** **bestehenden Mechanismus** (cartesian Zwei-Phasen +
   Reposition standup_radial 0.17 → radial 0.145) nehmen und **nur tunen**. Kein
   neuer Aufsteh-Code. **Offen by design:** ob die Zwischen-Reposition mit den
   kurzen Beinen überhaupt nötig ist — das zeigt sich, sobald die real erreichbare
   Höhe feststeht (S5.3). Falls direktes Aufstehen auf die Lauf-Pose sauber geht
   (standup_radial == radial), entfällt die Reposition (= einfacherer Pfad).

---

## 5. Fallstricke (aus S4 übernommen)
- **Boot-Default 3-fach synchron** (Node/Launch/teleop body_height_init) — sonst Body-Sprung.
- **Zwei Limit-Quellen** (URDF/Plugin vs config.py) — bei Posen-Änderung NICHT die
  rad-Limits anfassen (die sind S1-final); nur Pose-Params ([[project_two_joint_limit_sources]]).
- **Envelope optimistisch am Femur-Rand** → die laufende Engine/Sim ist die Wahrheit,
  nicht das Tool. Bei Konflikt mehr Femur-Marge (radien etwas größer).
- **Gazebo lenient** → „läuft in Sim" ≠ „läuft auf HW". S5-Grün ist notwendig, nicht
  hinreichend; S6 (HW aufgehängt) bleibt Pflicht.
- **sim_walk.yaml Test-Kopplung** — nicht einfach löschen ohne Test mitzubehandeln.
```
