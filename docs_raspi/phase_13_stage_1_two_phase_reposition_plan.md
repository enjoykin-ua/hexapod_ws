# Phase 13 Stage 1 / Sub-Stage 2.3 — Zwei-Phasen: Standup → Tripod-Reposition → Walk

> **STATUS: ⚪ PLAN — erstellt 2026-06-02. Zu reviewen + freigeben VOR Code.**
>
> **Warum:** Befund 2.2.3 — die feet-closer Walk-Pose (radial 0.220) ist NUR im Stand
> (bh −0.080) erreichbar, NICHT am Standup-Touchdown (Bauch am Boden → Femur >90°,
> mech. Limit ±1.57 → IK-Fail). Der Live-Param-Quicktest (instantaner Fuß-Sprung) hat
> das Prinzip in Sim bewiesen, taugt aber nicht für den Boden. → saubere **Tripod-
> Reposition** in der Engine. Übergeordnet: `phase_13_stage_1_tibia_unlock_plan.md` §2.6.

---

## 0. ⭐ Designprinzip (User-Vorgabe 2026-06-02): KEINE hartkodierten Pose-Zahlen
Die konkreten Werte (Standup-radial 0.295, Walk-radial 0.220, step_length 0.089,
step_height 0.040) sind **Tool-Ergebnisse** (`walking_envelope_check`) und leben
**ausschließlich in Config** (Launch-Defaults + Preset-YAML). Der Engine-/Produktiv-Code
enthält **keine** dieser Zahlen — er liest zwei Params und arbeitet **wertneutral**:
- `standup_radial_distance` — breite, touchdown-sichere Aufsteh-Pose,
- `radial_distance` — die Walk-Ziel-Pose,

und repositioniert generisch **von standup_radial → radial_distance**, egal welche Zahlen.
Neue Pose finden = nur Config/Preset ändern, **kein** Code-Change.

**Lese-Liste:** `CLAUDE.md` §4, `PHASE.md`, `phase_13_stage_1_tibia_unlock_plan.md`
(§2.6 + Befund 2.2.3), `gait_engine.py` (States + `start_cartesian_standup` +
`stand_pose` + WALKING-Tripod), `gait_node.py` (_ParamSpec + _apply_param).

**Code/Config, das geändert wird:**
- `src/hexapod_gait/hexapod_gait/gait_engine.py` — neuer State + Reposition-Logik.
- `src/hexapod_gait/hexapod_gait/gait_node.py` — `standup_radial_distance`-Param + Durchreichen.
- `src/hexapod_gait/launch/gait.launch.py` — `standup_radial_distance`-Default (0.295).
- `src/hexapod_gait/config/presets/feet_closer_walk.yaml` — beide radial-Werte (self-contained).
- Tests: `test/test_cartesian_standup.py`, neuer `test/test_reposition.py`.

---

## 1. Logik-Skizze / Pseudocode

### 1.1 Engine: neuer State `STATE_REPOSITION` + Param `standup_radial_distance`
- Neues Attr `self.standup_radial_distance` (vom Node gesetzt).
- `start_cartesian_standup` nutzt **`standup_radial_distance`** für Touchdown + Endpose
  (statt `radial_distance`) → Standup endet mit Füßen auf der breiten, sicheren Pose.
- Neue Methode `start_reposition(from_radial, to_radial, t)`:
  - Tripod-Gruppen A=(leg_1,3,5), B=(leg_2,4,6) (Standard-Tripod, wie WALKING).
  - Zwei Halb-Zyklen: Gruppe A lupft (`step_height`), interpoliert radial from→to, setzt ab;
    dann Gruppe B analog. Stützbeine halten ihr radial.
  - Dauer: `reposition_cycle_time` (= `cycle_time` wiederverwenden, oder eigener Param — §4-Frage).
- `compute_joint_angles` in `STATE_REPOSITION`: rechnet die Reposition-Trajektorie
  (Swing-Bein: radial-Lerp + z-Hub-Bogen; Stütz-Bein: statisch). Nach 2 Halb-Zyklen → done.

### 1.2 Auto-Trigger (nach Standup, User-Wahl)
Im Übergang `STATE_CARTESIAN_STANDUP` → (fertig):
```
if standup_radial_distance != radial_distance (mit eps):
    start_reposition(from=standup_radial_distance, to=radial_distance) → STATE_REPOSITION
else:
    STATE_STANDING            # nichts zu reposition
```
Nach `STATE_REPOSITION`-Ende → `STATE_STANDING` (jetzt auf Walk-radial). Ab da unverändert:
STANDING/WALKING nutzen `self.radial_distance` (= Walk-Pose).

### 1.3 Node: Param durchreichen (wertneutral)
- Neuer `_ParamSpec('standup_radial_distance', default=0.295, standing_only=True, ...)`.
- In `__init__` an die Engine geben; in `_apply_param` setzen (`self._engine.standup_radial_distance = value`).
- **Keine Zahl im Code** — Default steht im _ParamSpec/Launch, Override im Preset.

### 1.4 Config (self-contained Preset)
`feet_closer_walk.yaml` bekommt **beide**:
```
standup_radial_distance: 0.295   # breite Aufsteh-Pose (standup-grün)
radial_distance:         0.220   # Walk-Ziel (Tool-Ergebnis)
step_length_max:         0.089
step_height:             0.040
```
→ Launch mit diesem Preset: Standup @0.295 → Auto-Reposition → 0.220 → laufen. Ohne Code-Zahl.

---

## 2. Tests-Liste mit Begründung
### 2.1 Unit (pure Python)
| Test | Prüft |
|---|---|
| Reposition-Trajektorie: alle 6 Beine über den ganzen Reposition-Pfad **in-limit** (from 0.295 → to 0.220 @ bh −0.080, mit step_height-Lift) | Kein IK-Fail beim Umsetzen |
| Standup nutzt jetzt `standup_radial_distance` (Endpose = breite Pose) | Touchdown bleibt femur-sicher |
| Auto-Trigger: nach Standup → STATE_REPOSITION wenn radii ≠, sonst direkt STANDING | State-Maschine korrekt |
| Reposition-Ende → STATE_STANDING auf `radial_distance` | Endzustand = Walk-Pose |
| Tripod-Gruppen: nie >3 Beine gleichzeitig in der Luft | Statische Stabilität |
| **Wertneutral:** Test mit anderen radii (z.B. 0.28→0.20) läuft generisch | Keine 0.220/0.295-Hardcodes |
| Regression: `test_cartesian_standup`, `test_startup_ramp`, `test_param_callback` grün | Nichts kaputt |
### 2.2 Tool/Envelope
| `standup_envelope_check --radial 0.295` grün; `walking_envelope_check` @0.220 grün | Beide Phasen je für sich validiert |
### 2.3 Live (Sim VOR HW)
| SIM (RViz+Gazebo): Standup @0.295 → **smooth Tripod-Reposition** (kein Sprung) → 0.220 → laufen, kein IKError | Engine-Lösung ersetzt den Quicktest-Sprung |
| HW aufgebockt: dito, kein Freeze/Overcurrent | HW-Verify |
| HW griffiger Boden: Reposition stabil (kein Kippen) + echter Vortrieb | Das war mit dem Sprung NICHT möglich |
### 2.4 Bewusst NICHT
- Rück-Reposition (raus, vor Sitdown) — User: erst nur rein.
- Sitdown-Sequenz, Reposition während des Laufens.

---

## 3. Progress-Checkliste
```
### Sub-Stage 2.3 — Zwei-Phasen Standup → Reposition → Walk
- [x] 2.3.1  Engine: standup_radial_distance-Attr; start_cartesian_standup nutzt es (Touchdown+Endpose = breite Pose)
- [x] 2.3.2  Engine: STATE_REPOSITION + start_reposition + _reposition_foot Tripod 3+3 (wertneutral, Smooth-Step + Halbsinus-Hub)
- [x] 2.3.3  Engine: Auto-Trigger _finish_standup (radii≠ >1mm → REPOSITION) → STANDING; skip wenn gleich
- [x] 2.3.4  Node: standup_radial_distance + reposition_cycle_time Params (standing_only) + durchreichen + _apply_param
- [x] 2.3.5  Preset feet_closer_walk.yaml self-contained (beide radii + reposition_cycle_time); Node-Defaults decken No-Preset (kein Launch-Arg nötig, Loop deklariert)
- [x] 2.3.6  Unit-Tests test_reposition.py (10): in-limit, Trigger, skip, wertneutral, max-3-in-air, Gruppen-Lift, cmd_vel-ignored, Endpose; +Regression (71 gesamt, 0 Fail) + Lint grün
- [x] 2.3.7  standup_envelope @0.295 GRÜN + walking_envelope @0.220 GRÜN (alle 4 Szenarien)
- [ ] 2.3.8  SIM (RViz+Gazebo): smooth Reposition, größere Schritte, omni, kein IKError — Anleitung `phase_13_stage_1_two_phase_reposition_test_commands.md` §S
- [ ] 2.3.9  DANACH HW aufgebockt → HW Boden (echter Vortrieb, stabil) — §T
- [x] 2.3.10 Self-Review + Design-Log (s.u. §6 / §7)

> **Stand 2026-06-02: Desktop-Anteil 2.3 ✅** (2.3.1–2.3.7, 2.3.10). Offen: Sim-Gate 2.3.8
> (User, RViz+Gazebo), dann HW 2.3.9. **Bonus-Bugfix:** set_command ignorierte cmd_vel
> nicht in REPOSITION → behoben (cmd_vel würde sonst die Reposition auf WALKING kippen);
> per test_cmd_vel_ignored_during_reposition abgesichert. Pre-existing Q000 in
> reachability_viz.py mitgefixt.
```

---

## 4. Offene Punkte für User-Review (vor Code)
| # | Frage | ✅ ENTSCHEIDUNG (User 2026-06-02) |
|---|---|---|
| 4.1 | Reposition-Dauer: `cycle_time` wiederverwenden oder eigener Param? | ✅ **eigener Param `reposition_cycle_time`**, `standing_only` (nur änderbar wenn der Roboter steht), **Default = cycle_time-Wert (2.0)**, geklemmt auf **≥ 1.0 s** (gegen Schnapp-Bewegung/Kipp-Risiko am Boden). Mid-Reposition NICHT änderbar (Timing-Race). |
| 4.2 | Reposition-Hub: `step_height` wiederverwenden? | ✅ **ja, step_height wiederverwenden** (kein neuer Param) |
| 4.3 | Param-Name `standup_radial_distance` ok? | ✅ ja |
| 4.4 | Reposition eigener State ODER Walk-Cycle (v=0)? | ✅ **eigener State** `STATE_REPOSITION` |
| 4.5 | Skip wenn `standup_radial == radial_distance`? | ✅ ja, eps = 1 mm |

---

## 5. Cross-References
- Übergeordnet + Befund: [`phase_13_stage_1_tibia_unlock_plan.md`](phase_13_stage_1_tibia_unlock_plan.md) §2.6 / Befund 2.2.3
- Test-Doku (Quicktest, ersetzt durch Engine): [`phase_13_stage_1_feet_closer_walk_test_commands.md`](phase_13_stage_1_feet_closer_walk_test_commands.md)
- Engine: `gait_engine.py` (States, start_cartesian_standup, stand_pose, WALKING-Tripod)
- Preset: `config/presets/feet_closer_walk.yaml`
- Memory: [[project_two_joint_limit_sources]], [[feedback_urdf_refactor_full_smoke]], [[project_phase11_convenience_aliases]]
- Test-Doku 2.3 (Engine): [`phase_13_stage_1_two_phase_reposition_test_commands.md`](phase_13_stage_1_two_phase_reposition_test_commands.md)
- Tests: `src/hexapod_gait/test/test_reposition.py`

---

## 6. Kritischer Self-Review (2.3, 2026-06-02)
| # | Punkt | Status |
|---|---|---|
| 1 | standup_radial_distance steuert Touchdown+Endpose; Walk-radial via Auto-Reposition; **keine Pose-Zahl im Engine-Code** (alles Params) | OK |
| 2 | Reposition limit-konform über den ganzen Pfad (Test + walking_envelope @0.220) | OK |
| 3 | Tripod: nie >3 Beine in der Luft (Test) — statische Stabilität | OK |
| 4 | Auto-Trigger + eps-Skip (radii gleich → kein unnötiger Cycle) (Test) | OK |
| 5 | Wertneutralität mit anderen radii (0.28→0.24) (Test) → kein Hardcode | OK |
| 6 | **Bug gefunden+behoben:** set_command kippte in REPOSITION fälschlich auf WALKING bei cmd_vel → jetzt ignoriert (wie STANDUP); Test deckt's ab | OK (war 🔴) |
| 7 | Regression (71 Tests) + Lint (flake8/pep257) grün; pre-existing Q000 in reachability_viz mitgefixt | OK |
| 8 | **Reposition-Stabilität am Boden** (3 schmale Stützbeine während Gruppe-B-Swing) nur kinematisch geprüft, nicht dynamisch (CoG/Momentum) | 🟡 HW-Boden-Test 2.3.9 beobachtet (aufgebockt zuerst) |
| 9 | reposition_cycle_time min 1.0 s (fp_range) gegen Schnapp-Bewegung; standing_only gegen mid-flight-Timing-Race | OK |
| 10 | Reposition nur „rein" (0.295→0.220); Rück-Reposition vor Sitdown nicht gebaut (User: später) | 🟢 später (scope) |
| 11 | Nicht-Tripod-Pattern (single_leg) bei Reposition: Beine ohne offset → direkt Ziel (degeneriert) — Reposition ist nur für Tripod gedacht | 🟢 ok (Default tripod; Edge dokumentiert) |

**Fazit:** Kein offenes 🔴 (der gefundene cmd_vel-Bug ist gefixt+getestet). 🟡 = HW-Boden-
Stabilität, die der Gate-Test 2.3.9 (aufgebockt→Boden) absichert, bevor 2.3 final „fertig" ist.

## 7. Design-Log (Entscheidungen + verworfene Alternativen)
- **Eigener State `STATE_REPOSITION`** statt Walk-Cycle mit v=0: klarer, eigene Tests, keine
  cmd_vel-Semantik-Vermischung. (§4.4)
- **Auto-Trigger nach Standup** (statt bei erstem cmd_vel / separatem Befehl): einfachster
  Ablauf, Roboter ist nach dem Aufstehen lauf-bereit. (User-Wahl)
- **Wertneutral** (zwei Params, Engine kennt keine Zahl): explizite User-Vorgabe — neue Pose
  = nur Config/Preset ändern, kein Code. Verworfen: 0.220/0.295 im Code.
- **reposition_cycle_time eigener Param** (nicht cycle_time wiederverwenden): Reposition-
  Tempo unabhängig vom Lauf-Tempo sanft halten; min 1.0 s + standing_only als Schutz. (§4.1)
- **Tripod 3+3 sequenziell** (Gruppe A, dann B): max 3 Beine in der Luft = statisch stabil;
  Smooth-Step für radial + Halbsinus-Hub (wie swing_traj-Charakter). Verworfen: alle 6
  gleichzeitig (instabil), oder instantaner Sprung (= der 2.2.3-Quicktest, am Boden untauglich).
- **Reposition nur rein**: Rück-Reposition (raus vor Sitdown) deferred — kein Sitdown im Scope.
- **High-Body-Retune (Weg 1, 2026-06-02):** Preset auf body_height −0.120 (4 cm höher) +
  step_height 0.080 (Fuß-Hub 8 cm) + walk-radial 0.215 retuned (Envelope grün, reine
  Config). −0.120 ist das max. direkt-aufstehbare bei standup_radial 0.295.
- **Sub-Stage 2.4 (DEFERRED) — Body-Lift-in-Reposition für volle 5 cm (−0.130):** Standup
  kann −0.130 nicht direkt (out-of-reach @ Touchdown-radial 0.295; kein radial erfüllt
  beides). Lösung wäre: `standup_body_height` (moderat) + Reposition interpoliert
  **body_height mit** (analog zum radialen). Erst bauen, wenn 4 cm nicht reichen.
