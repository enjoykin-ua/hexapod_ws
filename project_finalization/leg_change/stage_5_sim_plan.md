# Stage 5 (Sim/Gazebo) — Plan (Bein-Umbau `leg_changes`)

> **Vorgänger:** S4 (Re-Param) ✅ — Produktiv-Posen eingetragen, alle gait-Tests
> grün (204/0/28skip). **Diese Stage = S5 (Sim).** Danach S6 (HW-Desktop).
> **Plan nach CLAUDE.md §4** — User-Freigabe einholen BEVOR Code/Sim läuft.
> Live-/Sim-Befehle stehen vollständig in
> [`stage_5_sim_test_commands.md`](stage_5_sim_test_commands.md),
> nicht im Chat ([[feedback_test_commands_in_doc_not_chat]]).

> **🟢 STATUS:** Modell visuell ok (B.1–B.3 vom User bestätigt). Code/Params/Presets/
> Tests **implementiert + grün** (s. §7). **Offen:** der User verifiziert das
> finale Aufstehen + Tripod-Lauf mit den NEUEN Werten visuell in Sim (B.4/B.5
> erneut), dann S5 fertig → S6.

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
- [x] 5.3a Gazebo-Spawn: Modell visuell korrekt (kurze Beine), keine Mesh-/URDF-Fehler (User B.1)
- [x] 5.3b RViz display + Reachability-Viz: tf2 vollständig, Hülle plausibel, mittel-Pose mit Marge (User B.2/B.3)
- [x] 6.1  Stand-Pose-Werte berechnet (radial 0.160 / body_height -0.080), envelope-grün → Code+Launch+teleop
- [x] 6.2  Aufsteh-Pfad: Einzel-Radius 0.160 == standup_radial → KEINE Reposition (radial 0.150 unmöglich, Min 0.160)
- [x] 6.2b _SIT_SAFE_MIN_BH -0.115 bleibt (alle Höhen direkt sit-fähig); D4: 3 Höhen bei radial 0.160 (alle direkt aufstehbar)
- [x] 6.3  step_length_max 0.050 (Default) / D-Pad-Cycle 0.030–0.070 / step_height 0.040 — envelope-grün
- [x] 6.5  Preset-Cleanup: 4 aktualisiert (sim_walk Test-grün), 4 gelöscht, tools_catalog/ai_navigation/C_teleop/README nachgezogen
- [x] 6.6  colcon test gait 205/0/28 · teleop 30/0/1 · kinematics 36/0/1 · pytest tools 11/0 — kein Regress
- [x] 6.7  Self-Review-Tabelle (§7) + stage_5_sim_test_commands.md final
- [ ] 6.8  **User-Sim-Verify mit NEUEN Werten**: Aufstehen (direkt, kein Reposition-Hop) + Tripod-Lauf stabil, kein Clamp-Spam
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

---

## 6. Berechnete + implementierte Endwerte (S5)

> **Kernbefund (korrigiert die User-Annahme „radial 0.150"):** Beim Aufstehen liegt
> der Bauch am Boden (Coxa 21.5 mm hoch). Bei radial < 0.160 zwingt der Touchdown
> den Femur über −90° (−1.57): radial 0.150 → Femur −1.668 (🔴), 0.155 → −1.582 (🔴),
> **0.160 → grün**. → **0.160 ist das schmalste direkt-aufstehbare Radial.**
>
> **Design (User bestätigt): Einzel-Radius 0.160, keine Reposition.** `radial ==
> standup_radial == 0.160` → die Engine überspringt die Reposition; alle drei Höhen
> stehen direkt auf (kein Routing über mittel mehr).

| Param | alt (S4) | **neu (S5)** | Beleg |
|---|---|---|---|
| `radial_distance` (Default = mittel) | 0.145 | **0.160** | walking + standup envelope-grün |
| `standup_radial_distance` | 0.170 | **0.160** (= radial) | keine Reposition |
| `body_height` (mittel/Default) | −0.100 | **−0.080** | „stand zu hoch" → 2 cm tiefer, stabiler; grün |
| Stance tief / mittel / hoch (body_height) | −0.070/−0.100/−0.130 | **−0.065 / −0.080 / −0.100** | alle @ radial 0.160 standup-grün |
| Stance radial (alle) | 0.160/0.145/0.130 | **0.160 einheitlich** | s. Kernbefund |
| `step_height` | 0.040 | 0.040 | unverändert |
| `step_length_max` (Default) | 0.030 | **0.050** | linear_max 0.05 m/s → Clamp-Spam weg; grün bis ~0.08 |
| D-Pad-Cycle `step_length_intent_min/max` | 0.020/0.089 | **0.030 / 0.070** | feste Schrittweiten 0.03…0.07, Start 0.05 |
| `body_height_min` / `_max` | −0.140/−0.030 | **−0.110 / −0.060** | umschließt tief −0.065 … hoch −0.100 |
| `_SIT_SAFE_MIN_BH` | −0.115 | −0.115 | alle Höhen darüber → direkt sit-fähig |

**Synchron geändert (4 Quellen + Tests + Presets):** `gait_node.py` (_STANCE_MODES,
_GAIT_PARAMS, intent-Range) · `gait.launch.py` · `stand.launch.py` · teleop
(`joy_to_twist.py` + `ps4_usb.yaml` + `ps4_bt.yaml`) · Tests (`test_param_callback`
5×, `test_show_node` hoch→direkt + neuer Routing-Sicherungs-Test, `test_walking_envelope_check`
radial-Range) · Presets (4 aktualisiert, 4 gelöscht) · Docs (presets/README,
tools_catalog, ai_navigation, C_teleop §1a).

**Folge-Bugfix (vom Sim-Test aufgedeckt): Sit-down-Shuffle.** `start_sitdown`
rief **immer** `start_reposition(radial → standup_radial)` — bei gleichen radii
(0.160) ein No-op-Tripod-„Schritt auf der Stelle" über `reposition_cycle_time`,
sichtbar als unnötiger Shuffle vor dem Hinsetzen. Fix: `_REPOSITION_EPS`-Skip
(wie `_finish_standup`) → bei radial ≈ standup_radial direkt `SITDOWN_LOWER`.
Tests: 4× `test_sitdown_node` + 2× `test_show_node` REPOSITION→SITDOWN_LOWER
(Default-radii gleich); `test_sitdown`/`test_reposition` (unterschiedliche radii)
testen den Reposition-Pfad weiter. Standup war schon korrekt (hatte den Skip).

### Verworfene Alternativen
- **radial 0.150 (User-Wunsch):** kinematisch unmöglich für direktes Aufstehen
  (Femur-Wand). Verworfen zugunsten 0.160 (1 cm breiter, dafür reposition-frei).
- **Laufen 0.150 + Reposition auf Standup 0.160:** mehr Komplexität für 1 cm
  schmaler. Verworfen (User wählte Einzel-Radius).
- **2 Höhen / 1 Höhe:** nicht nötig — bei Einzel-Radius 0.160 sind alle 3 Höhen
  problemlos direkt aufstehbar, also alle behalten.

---

## 7. Self-Review (CLAUDE.md §4)

| Punkt | Status | Befund |
|---|---|---|
| radial 0.150 vs 0.160 — Annahme per Mathe falsifiziert, nicht blind umgesetzt | OK | standup_envelope_check: Min direkt-aufstehbar = 0.160 ([[feedback_validate_hardware_hypothesis_via_code]]) |
| Walking + Standup envelope-grün für alle 3 Höhen @ radial 0.160 | OK | check (4 Szenarien) + standup −0.065/−0.080/−0.100 alle GRÜN |
| Boot-Default 4-fach synchron (Node/gait.launch/stand.launch/teleop) | OK | mittel −0.080 / 0.160 überall; body_height_init == body_height |
| rad-Limits NICHT angefasst (S1-final) | OK | nur Pose-Params geändert ([[project_two_joint_limit_sources]]) |
| Test-Migration vollständig (kein Regress) | OK | gait 205/0/28 · teleop 30/0/1 · kinematics 36/0/1 · tools 11/0 |
| Sit-Routing-Logik: tote „hoch"-Annahme ersetzt, Sicherungspfad weiter getestet | OK | test_sit_below_sit_safe_routes_through_mittel (erzwungen) + test_sit_from_hoch_direct |
| Preset-Test-Anker (sim_walk) grün | OK | test_check_envelope_sim_preset_forward_green |
| Sit-down-Shuffle (No-op-Reposition) — vom Sim-Test gefunden + gefixt | OK | _REPOSITION_EPS-Skip in start_sitdown; 6 Tests migriert |
| `cmd_vel clamped`-Spam beim Lauf | 🟡 vormerken | max-leg-speed 0.050 == teleop-Voll-Stick 0.050 → Diagonal-Drift kippt knapp drüber (harmlos). D-Pad ↑ hebt step_length_max; ggf. Default 0.060 (User-Entscheid) |
| `body_height_min/max` Node==Launch (S4-Lücke −0.140/−0.030) | OK | jetzt beidseitig −0.110/−0.060 |
| Reposition-Engine-Code bleibt (für standup>radial), nur deaktiviert | OK | wertneutral; reaktivierbar falls je standup>radial gewünscht |
| **Strom/Drehmoment-Beweis** | 🟢 später | Sim kinematisch; echter Strom erst S6/Boden |
| **Sim-Visual-Verify der NEUEN Werte** (Aufstehen direkt + Lauf) | 🔴 offen | User B.4/B.5 erneut → dann S5 fertig (Bullet 6.8) |
| Nicht-Tripod-Wackeln | 🟢 später | Open-loop, A5 IMU ([[project_nontripod_gait_wobble]]) |
