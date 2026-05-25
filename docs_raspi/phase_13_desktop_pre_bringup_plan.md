# Phase 13 — Desktop Pre-Bringup-Plan

> **Status:** Brainstorm + Design-Decisions für die Desktop-Pre-Stufen
> festgelegt 2026-05-25. Dieser Plan ist der **Vertrag** für die
> kommenden Stages F (servo_real_cal) und A–D (Phase 13 Desktop). Stage-
> spezifische Plan-/Test-Commands-Files werden in eigenen Files erstellt
> und referenzieren diesen Plan.
>
> **Phase-Kontext:** Phase 13 hat zwei Profile:
> - **Desktop-Pre-Bringup** (hier) — Walking-Tuning + PS4-Vollbetrieb +
>   LUT-Infrastruktur am Desktop mit aufgebocktem Hexapod, BEVOR Phase
>   12 (Pi-Plattform) angefasst wird. Servo2040 hängt am Desktop-USB.
> - **Pi-Voll-Bringup** ([`phase_13_full_bringup.md`](phase_13_full_bringup.md))
>   — die ursprünglichen Pi-Stufen, nach Phase 12. Kommt später.
>
> **Vorbedingung:** Cross-Phase-Thread `servo_real_cal` ✅ 2026-05-25
> ([`servo_real_cal_plan.md`](servo_real_cal_plan.md)), Phase 11 ✅
> (rqt-Live-Cal-Infrastruktur).

---

## 1. Ziel

Vier zusammenhängende Ergebnisse am Ende der Desktop-Pre-Stufen:

1. **Femur-Asymmetrie behoben** — alle 6 Femur-Servos bei `rad=0`
   visuell horizontal (Stage F)
2. **Höhen-Slot-Infrastruktur steht** — `gait_node` kann zwischen
   diskreten body_height-Slots wechseln, pro Slot sind valide
   radial_distance / step_length_max / step_height vordefiniert
3. **Lift-and-Reposition** — Slot-Wechsel löst Tripod-3+3-Sequenz aus,
   keine Foot-Schramm beim Stand-Pose-Wechsel
4. **PS4-Vollbetrieb mit Modifier-Tasten** — L2/R2/L1+L2 + D-Pad
   verstellen die 5 Walking-Parameter diskret (STANDING-only)

Nach Abschluss: Hexapod aufgebockt mit User-PS4-Kontrolle voll
einstellbar, ready für Boden-Walking (das kommt in einer späteren
Phase-13-Pi-Stufe oder einer separaten Floor-Walking-Stage).

## 2. Stage-Übersicht

| Stage | Dateien | Inhalt | Aufwand | Wer | Status |
|---|---|---|---|---|---|
| `servo_real_cal` **Stage F** | `servo_real_cal_stage_f_femur_plan.md` + `_test_commands.md` | Femur-Asymmetrie-Fix (Wasserwaage + pulse_zero trim + `/save_calibration`) | 30-60 min interaktiv | User+Claude | 🟡 Plan in Arbeit |
| Phase 13 Desktop **Stage A** | `phase_13_desktop_stage_a_lut_plan.md` + `_test_commands.md` | LUT-Infrastruktur: `walking_envelope_check.py recommend-multi` + `height_slots.yaml`-Generator + `gait_node` Slot-Loading + REPOSITIONING-State + Unit-Tests | ~2-3 h Code | Claude | ⚪ offen |
| Phase 13 Desktop **Stage B** | `phase_13_desktop_stage_b_teleop_plan.md` + `_test_commands.md` | `hexapod_teleop` PS4-Mapping-Erweiterung (L2/R2/L1+L2-Modifier) + Unit-Tests | ~1-2 h Code | Claude | ⚪ offen |
| Phase 13 Desktop **Stage C** | `phase_13_desktop_stage_c_suspended_walking_test_commands.md` | Walking-Tests aufgebockt mit LUT: pro Slot Stand-Pose + Walk durchprobieren | ~1-2 h interaktiv | User+Claude | ⚪ offen |
| Phase 13 Desktop **Stage D** | `phase_13_desktop_stage_d_ps4_suspended_test_commands.md` | PS4-Vollbetrieb-Test aufgebockt mit allen Modifier-Kombinationen | ~1 h interaktiv | User+Claude | ⚪ offen |

**Total:** ~6-9 h verteilt über 2-3 Sessions.

Die zwei interaktiven Stages (C+D) haben **kein eigenes Plan-File** —
nur Test-Commands. Begründung: sie validieren die in Stages A+B gebauten
Features ohne zusätzliche Design-Entscheidungen. Test-Commands enthalten
embedded Erfolgs-Kriterien.

## 3. Design-Entscheidungen

### 3.1 LUT-Storage = YAML-Datei

**Entscheidung:** Pre-computed YAML unter
`src/hexapod_gait/config/height_slots.yaml`, generiert via Tool-Erweiterung,
geladen von `gait_node` beim Start.

**Schema (Vorschlag, finalisiert in Stage A):**
```yaml
# Generiert von: tools/walking_envelope_check.py recommend-multi
# Generiert am:  2026-05-26 (Beispiel)
# Cal-Stand:     servo_mapping.yaml MD5: <hash>
slots:
  - index: 0
    body_height: -0.10
    defaults:
      radial_distance: 0.28
      step_length_max: 0.025
      step_height: 0.015
    valid_ranges:
      radial_distance: [0.24, 0.31]
      step_length_max: [0.010, 0.045]
      step_height: [0.005, 0.035]
  - index: 1
    body_height: -0.08
    # ...
```

**Verworfene Alternativen:**

| Option | Verworfen weil |
|---|---|
| **B) Inline-LUT in `gait_node.py`** | Code-Diff statt YAML-Diff bei Cal-Änderungen, Recompile nötig, schlechter sichtbar |
| **C) Eigener Service-Node `height_slot_server`** | Overhead für 3-5 statische Werte; mehr ROS-Topology; langsamer beim Slot-Wechsel; unnötige Komplexität |

**Generator-Workflow:** Einmalig (oder nach Cal-Änderungen):
```bash
python3 tools/walking_envelope_check.py recommend-multi \
  --slot-step 0.02 --search-range -0.12 -0.02 \
  --output src/hexapod_gait/config/height_slots.yaml
```

→ Generator läuft am Build-/Setup-Zeit, **nicht zur Laufzeit**. Im
laufenden System wird nur YAML gelesen.

### 3.2 Slot-Range = Tool-entdeckt

**Entscheidung:** Tool sweept `body_height` von z.B. -0.12 bis -0.02
in 2-cm-Schritten und gibt nur **viable Slots** zurück (Slot mit
nicht-leerer step_length-Envelope, also `step_length_max_max > 0.01`
oder ähnliche Schwelle).

**Verworfen:** Vorab-Festlegung der Slots (z.B. fixe Liste
{-0.10, -0.08, -0.06, -0.04, -0.02}). Risiko dass einer der pre-gewählten
Slots IK-Limit-bedingt nicht erreichbar ist — wäre erst zur Laufzeit als
Fehler sichtbar.

**Begründung:** mit aktuellem Cal-Stand wissen wir nicht ob `body_height`
= -0.10 erreichbar ist. Tool soll das discovery machen.

### 3.3 Step-Größen pro Parameter

| Parameter | Step-Größe | Range (heuristisch) | Diskrete Auswahl |
|---|---|---|---|
| `body_height` | **2 cm** | Tool entdeckt, ~-0.12 bis -0.02 | exakte Slot-Werte (vom Tool ausgewählt) |
| `radial_distance` | **1 cm** | Tool entdeckt pro Slot, ca. 0.20-0.32 | Default = Slot-Mitte; ±1 cm Steps innerhalb valid_range; Fallback "nächst-möglicher Wert" wenn Step nicht-exakt erreichbar |
| `step_height` | **1 cm** | Tool entdeckt pro Slot, ca. 1-4 cm | gleicher Fallback wie radial |
| `step_length_max` | **vom Tool getrieben** (vermutlich 1 cm, finalisiert in Stage A nach Tool-Run) | Tool entdeckt pro Slot, ca. 0.5-6 cm | gleicher Fallback wie radial |
| `cycle_time` | **0.5 s** | 1.0 - 5.0 s | exakte 0.5-Schritte |

**Wichtig:** "diskrete Auswahl" mit Fallback "nächst-möglicher Wert" heißt:
- User drückt PS4 für "+1 Step radial_distance"
- gait_node prüft ob aktueller Wert + 1 cm im valid_range des aktiven Slots liegt
- Wenn ja: setzen
- Wenn nein: auf nächst-möglichen Wert clampen (z.B. valid_range_max) + WARN-Log

### 3.4 PS4-Mapping (final)

| Eingabe | Effekt | Step-Größe | Wann erlaubt |
|---|---|---|---|
| **R1 (gehalten) + D-Pad ↑/↓** | vorwärts / rückwärts laufen (Twist.linear.x) | continuous | jederzeit (Dead-Man) |
| **R1 (gehalten) + D-Pad ←/→** | drehen am Stand (Twist.angular.z) | continuous | jederzeit (Dead-Man) |
| **L2 (gehalten) + D-Pad ↑/↓** | body_height Slot ±1 (Lift-and-Reposition) | 2 cm | nur STATE_STANDING |
| **L2 (gehalten) + D-Pad ←/→** | radial_distance ±1 Step (Lift-and-Reposition) | 1 cm | nur STATE_STANDING |
| **R2 (gehalten) + D-Pad ↑/↓** | step_height ±1 Step (kein Lift) | 1 cm | nur STATE_STANDING |
| **R2 (gehalten) + D-Pad ←/→** | step_length_max ±1 Step (kein Lift) | tool-driven (vermutlich 1 cm) | nur STATE_STANDING |
| **L1+L2 (beide gehalten) + D-Pad ↑/↓** | cycle_time ±0.5 s | 0.5 s | nur STATE_STANDING |

**Edge-Detection:** Wie aktuelles L2/R2 in Phase 6 — ein Press = ein
Step. Hold-Repeat wäre ein anderes Mental-Modell und nicht gewünscht.

**Konflikt-Auflösung:** D-Pad kann nicht gleichzeitig R1+Movement UND
Modifier+Param. User-Workflow:
1. User läuft mit R1 + D-Pad → STATE_WALKING
2. User lässt R1 los → STATE_STOPPING → STATE_STANDING (1-2 s)
3. User drückt L2/R2/L1+L2 + D-Pad → Parameter wird verstellt (ggf.
   mit Lift-and-Reposition)
4. User drückt R1 + D-Pad → STATE_WALKING wieder

### 3.5 Slot-Mode vs. Legacy-Mode

**Entscheidung:** Beide Modi parallel verfügbar, Default ist Slot-Mode
wenn `height_slots.yaml` vorhanden ist.

**Slot-Mode (Default):**
- `height_slots.yaml` geladen
- `gait_node` Param `height_slot_index` (Integer) wählt aktiven Slot
- `body_height` / `radial_distance` / `step_length_max` / `step_height`
  werden aus Slot übernommen
- rqt_reconfigure Live-Sliders für diese Params bleiben **lesbar zur
  Visualisierung** aber non-functional (oder mit WARN bei Set-Versuch)
- PS4-Modifier wirken auf Slot-Werte

**Legacy-Mode:**
- `gait_node` Param `use_height_slots:=false` ODER `height_slots.yaml`
  fehlt
- Sliders gewinnen wie in Phase 11 — `body_height` etc. sind direkt
  einstellbar
- PS4-Modifier-Tasten wirken im Legacy-Mode auf die Phase-6-Logik
  (continuous L2/R2 wie aktuell) — oder werden zu no-op (Detail in
  Stage B finalisieren)
- Phase-11-Workshop-Doku bleibt valide

**4-Anker-Doku-Strategie** (damit der Modus nicht vergessen wird):

1. `src/hexapod_gait/README.md` — prominente Sektion "Walking-Modes:
   Slot vs. Legacy" mit Beispiel-Aufrufen
2. `gait_node.py` Module-Docstring (Top des Files) — kurze Modus-
   Beschreibung
3. `phase_13_desktop_stage_a_lut_plan.md` — Design-Entscheidungen-
   Sektion mit Begründung
4. Memory `project_gait_node_slot_vs_legacy_mode.md` — Cross-Session-
   Reminder

### 3.6 REPOSITIONING-State (Lift-and-Reposition)

**Entscheidung:** Neuer State `REPOSITIONING` in `GaitEngine` parallel
zu `STANDING` / `WALKING` / `STOPPING`. Tripod-3+3-Sequenz (Set A =
legs 1+3+5 / Set B = legs 2+4+6).

**State-Diagram-Erweiterung:**
```
STANDING --[cmd_vel != 0]--> WALKING
STANDING --[slot_change]--> REPOSITIONING --[done]--> STANDING
WALKING  --[cmd_vel == 0]--> STOPPING --[Beine eingefroren]--> STANDING
WALKING  --[slot_change attempt]--> bleibt WALKING + WARN-Log (ignored)
STOPPING --[slot_change attempt]--> bleibt STOPPING + WARN-Log (ignored)
```

**REPOSITIONING-Logik:**

1. Engine speichert aktuelle Foot-Targets (alt-Stand-Pose) + neue
   Foot-Targets (neu-Stand-Pose) pro Bein
2. Phase 1 (~1.5 s): Tripod-Set A (legs 1/3/5) hebt sich auf
   `foot_z + lift_height` (z.B. +3 cm Bezier-Swing), bewegt sich
   horizontal zu neuer X/Y, senkt sich auf neue `body_height`
3. Phase 2 (~1.5 s): Tripod-Set B (legs 2/4/6) gleiche Sequenz
4. State zurück auf STANDING
5. Während REPOSITIONING: `cmd_vel` ignoriert + WARN-Log;
   andere PS4-Param-Verstellungen blockiert

**Implementation-Hinweis für Stage A:** kann als Erweiterung von
`gait_engine.compute_joint_angles` implementiert werden (analog zu
STOPPING-Logik). Pure-Python testbar.

### 3.7 STANDING-only-Constraint für Param-Verstellung

**Entscheidung:** Alle Parameter (body_height, radial_distance,
step_height, step_length_max, cycle_time) sind **nur in
STATE_STANDING** verstellbar.

**Begründung:**

- PS4-D-Pad hat nur einen Eingang gleichzeitig → physisch kein
  paralleles R1+Move und L2/R2+Param möglich
- body_height/radial_distance würden mid-Walk sprünge in den
  Foot-Trajectories verursachen
- step_height/step_length_max wären technisch mid-Walk OK
  (Engine berechnet Trajectory pro Tick fresh), aber siehe D-Pad-
  Constraint
- Einheitliches Mental-Modell ist einfacher als "manche während
  Walking, andere nur STANDING"

**Verworfene Alternative:** WALKING-tunable mit rechtem Stick als
Param-Steuerung. Verworfen weil PS4-rechter-Stick aktuell ungenutzt
ist, aber das Konzept "Stick = continuous, D-Pad = discrete" würde
brechen. Plus User muss zwei Hände gleichzeitig koordinieren —
unschöne UX.

## 4. Q&A-Log

Audit-Trail der Design-Diskussion 2026-05-25. Reihenfolge wie geführt.

### Q-final-1 — Step-Größen pro Parameter

**Frage:** Sind die Step-Größen (2cm / 1cm / 5mm / 5mm) korrekt
gewählt? `step_height` + `step_length_max` mit 5 mm zu fein?

**User-Antwort (2026-05-25):** 5 mm zu klein. `step_height` mit 1 cm
versuchen. `step_length_max` vom Tool ermitteln lassen und ggf.
nachträglich tiefer-stufen wenn Slot-Kombis infinitesimal nah
beieinander.

**Entscheidung:** body_height 2cm / radial 1cm / step_height 1cm /
step_length_max tool-driven / cycle_time 0.5s. Plus Fallback "nächst-
möglicher Wert" wenn ±1 Step nicht-exakt erreichbar.

### Q-final-2 — Mental-Modell STANDING-only

**Frage:** PS4-D-Pad-Konflikt — Param-Verstellung nur STANDING oder
auch WALKING (mit rechtem Stick als Alternative)?

**User-Antwort:** STANDING-only ist gut, simpler.

**Entscheidung:** Alle Parameter STANDING-only. Bedingt einheitliches
Mental-Modell siehe §3.7.

### Q-final-3 — Lift-and-Reposition Variante

**Frage:** Tripod 3+3 vs. Sequenziell 1×6 vs. direkte JTC-Lerp ohne
Lift?

**User-Antwort:** Variante A (Tripod 3+3).

**Entscheidung:** REPOSITIONING-State mit Tripod-3+3-Sequenz siehe
§3.6.

### Q-new-1 — cycle_time-Steuerung

**Frage:** `cycle_time` auch in der LUT/PS4-Steuerung haben? Falls ja:
welcher Modifier?

**User-Antwort:** Ja, mit L1+L2-Kombi gehalten + D-Pad ↑/↓. Range
1-5 s, nur STANDING.

**Entscheidung:** L1+L2 + D-Pad ↑/↓ = cycle_time ±0.5 s, STANDING-only.

### Q-new-2 — Step-Größen-Details

Wurde in Q-final-1 abgedeckt.

### R1 — Femur-Re-Cal Auswirkung auf sim_walk.yaml

**Frage:** Muss `walking_envelope_check.py` nach Stage F neu laufen?

**Analyse (2026-05-25):** Ursprünglich vermutet ja, dann re-evaluiert:

- Stage F ändert nur `pulse_zero` der 6 Femur-Pins (= wo "rad=0" im
  PWM-Range sitzt)
- `pulse_min`/`pulse_max` bleiben (mechanische Anschläge unverändert)
- URDF `joint_lower`/`joint_upper` bleiben
- Plugin-Slope-Formel (`calibration.cpp`) sorgt dafür dass
  `rad=joint_upper → pulse_max` und `rad=joint_lower → pulse_min`
  **immer** stimmt — egal wo `pulse_zero` liegt
- ⇒ erreichbarer rad-Range ist nach Stage F unverändert
- ⇒ `walking_envelope_check.py` arbeitet in rad-Space → Envelope
  identisch
- ⇒ `sim_walk.yaml` bleibt valide

**Entscheidung:** Risiko gestrichen. Kein Re-Run nötig. Die LUT-
Generierung in Stage A läuft natürlich gegen den dann aktuellen
Cal-Stand inkl. Stage F-Updates.

### R2 — Plugin Stage 0.5 PWM-OoR-Freeze während Stage F

**Frage:** Was wenn User in rqt_reconfigure versehentlich `pulse_zero`
außerhalb [pulse_min, pulse_max] setzt? Plugin-Stage-0.5-Hard-Stop
würde dann beim nächsten "rad=0"-Kommando feuern.

**Analyse:** rqt_reconfigure hat globale `floating_point_range`
[800, 2200] µs aus Phase 11 Stage B — **weiter** als individuelle
Servo-Range [pulse_min, pulse_max]. Theoretisch möglich, falsch zu
tippen.

**Mitigation:** Pre-Check-Befehl in Stage-F Test-Commands der vor
`/save_calibration` einmal verifiziert dass `pulse_min < pulse_zero
< pulse_max` für alle 6 Femur-Pins.

**Entscheidung:** Mitigation umsetzen. In Praxis: aktuelle Femur-
pulse_zeros (1445-1560 µs) liegen weit von pulse_min/max-Edges (~815-
2120 µs), ±50 µs Trim ist locker drin. Pre-Check ist Sicherheitsnetz.

### R3 — REPOSITIONING als neuer State

**Frage:** Brauchen wir tatsächlich einen neuen State, oder kann man
das in STANDING ad-hoc machen?

**Antwort:** Ja, brauchen wir.

**Begründung:** Während Lift-and-Reposition (3 s Dauer) muss klar
sein:

- cmd_vel ist ignoriert
- PS4-Param-Verstellungen sind blockiert (sonst Doppel-Trigger)
- Engine berechnet andere Trajectory-Form als in STANDING
  (Bezier-Lift + horizontaler Move + Bezier-Land)
- Visuelle/Topic-Indication dass Robot gerade rekonfiguriert

Ein dedicated State ist sauberer als STANDING-with-flag.

### R4 — Slot-Mode vs. Legacy-Mode Doku-Strategie

**Frage:** Wo dokumentieren wir die Mode-Existenz damit sie später
nicht vergessen wird?

**User-Antwort:** Bin mir nicht sicher wo.

**Entscheidung:** 4-Anker-Strategie siehe §3.5 — `hexapod_gait/README.md`,
`gait_node.py` Docstring, `phase_13_desktop_stage_a_lut_plan.md`
Design-Sektion, Memory `project_gait_node_slot_vs_legacy_mode.md`.

## 5. Risiken & Mitigations

| # | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | ~~Femur-Re-Cal invalidiert sim_walk.yaml~~ | **GESTRICHEN** — kein realer Effekt auf rad-Range | — |
| R2 | Plugin Stage 0.5 PWM-OoR-Freeze wenn pulse_zero falsch eingestellt | mittel (rqt-Range zu weit) | Pre-Check vor `/save_calibration` in Stage F |
| R3 | REPOSITIONING-State falsch implementiert → Beine kollidieren | gering (Pure-Python testbar) | Unit-Tests für Lift-Trajectory + Sub-Phase-Übergang; aufgebockt = kein Boden-Kontakt; Foot-Hover-Distance konservativ wählen |
| R4 | Slot-Mode-Aktivierung versehentlich → Phase-11-Workshop-Demo bricht | gering | Default-Behavior pro `height_slots.yaml`-Existenz; explizit `use_height_slots:=false` für Legacy-Demo |
| R5 (neu) | User trifft physisch L1+L2-Combo schlecht (PS4-Ergonomie) | unbekannt | Test in Stage D; alternative Modifier-Mapping vormerken (z.B. Square+L2) |
| R6 (neu) | walking_envelope_check.py recommend-multi findet zu wenige viable Slots (< 3) | mittel | Vor Stage A: trial-run; Fallback `--slot-step 0.01` (1 cm statt 2 cm) oder bigger search-range |

## 6. Offene Punkte (für später, nicht jetzt entschieden)

| # | Frage | Wann zu klären |
|---|---|---|
| O1 | L1+L2-Combo ergonomisch — bequem aushaltbar? | Stage D Live-Test |
| O2 | `step_length_max` Step-Größe konkret — 1 cm oder feiner? | Stage A nach erstem Tool-Run |
| O3 | `cycle_time` an Slot gekoppelt? (z.B. tiefe Pose = langsamer Gait sicherer) | Stage C Walking-Tests; ggf. Phase-13-Pendenz |
| O4 | Sollen alte `cmd_body_height`-Float-Topic + L2/R2-continuous-Senken-Anheben aus Phase 6 in Legacy-Mode erhalten bleiben? | Stage B Design-Detail |
| O5 | Visualisierung des aktiven Slots in rqt — eigenes Topic `/gait_slot_state`? | Stage A Design-Detail |
| O6 | Was wenn Stage F einen Femur mechanisch nicht horizontal trimmbar findet (z.B. Servo-Mount asymm)? Option C aus Memory (URDF mount_offset)? | Stage F Live-Findings |

## 7. Stage-Implementation-Skeletons

> **Zweck:** Kurze Skizze pro Stage (A–D) mit Implementation-Items +
> Stage-spezifischen Offenen Fragen. Soll **nicht** den späteren
> Stage-Plan ersetzen (der wird pro Stage in eigenem File erstellt),
> sondern als Cross-Session-Reminder dienen damit nach Pause/Compact
> die Knöpfe + offenen Fragen wieder sichtbar sind.

### 7.1 Stage A — LUT-Infrastruktur

**Implementation-Items:**

1. **Tool-Erweiterung** `tools/walking_envelope_check.py`:
   - Neuer Sub-Befehl `recommend-multi`
   - Args: `--search-range <min> <max>` (Default `-0.12 -0.02`),
     `--slot-step <m>` (Default `0.02`), `--output <path>`,
     `--safety-margin <float>` (Default `0.10`)
   - Logik: body_height sweep in `--slot-step`-Schritten, pro Slot
     `recommend` ausführen, viable Slots filtern (Schwelle:
     `step_length_max_max >= 0.01`), YAML dumpen
   - Tests in `tools/test_walking_envelope_check.py` ergänzen

2. **YAML-Schema** `src/hexapod_gait/config/height_slots.yaml`:
   ```yaml
   meta:
     generated_at: <ISO 8601>
     cal_yaml_md5: <hash von servo_mapping.yaml>
     tool_version: <git short hash>
     safety_margin: 0.10
   slots:
     - index: 0
       body_height: -0.10
       defaults:
         radial_distance: 0.28
         step_length_max: 0.025
         step_height: 0.015
       valid_ranges:
         radial_distance: [0.24, 0.31]
         step_length_max: [0.010, 0.045]
         step_height: [0.005, 0.035]
     # ... weitere Slots
   ```

3. **gait_node-Änderungen** (`src/hexapod_gait/hexapod_gait/gait_node.py`):
   - Neue Params (in `_GAIT_PARAMS` ergänzen):
     - `height_slots_file` (string, Default: `'$(find hexapod_gait)/config/height_slots.yaml'`)
     - `use_height_slots` (bool, Default: auto — true wenn YAML existiert)
     - `height_slot_index` (int, Default: middle slot, range `[0, len(slots)-1]`)
   - YAML-Loading-Methode bei Init (mit Schema-Validation)
   - Slot-Wechsel-Handler (auf Topic-Empfang ODER on_param_change —
     siehe A-Q1)
   - Trigger REPOSITIONING-State bei Slot-Change in STANDING

4. **gait_engine-Änderungen** (`src/hexapod_gait/hexapod_gait/gait_engine.py`):
   - Neuer State `STATE_REPOSITIONING`
   - Neue Methode `enter_repositioning(new_targets_per_leg, t)` analog
     `_enter_stopping`
   - `compute_joint_angles` erweitert für REPOSITIONING:
     - Sub-Phase A (`0` bis `~lift_duration`): Tripod-Set A (legs 1/3/5)
       Bezier-Lift + Horizontal-Move + Bezier-Land zu neuen Foot-Targets
     - Sub-Phase B (`~lift_duration` bis `~2*lift_duration`): Tripod-Set
       B (legs 2/4/6) gleiche Sequenz
     - Auto-Transition zurück zu STANDING wenn Sub-Phase B fertig

5. **Unit-Tests:**
   - `test_height_slots_yaml_load` (parsing + validation)
   - `test_slot_index_clamp` (out-of-range → clamp + WARN)
   - `test_repositioning_state_transitions`
   - `test_repositioning_trajectory_continuity` (foot_z hebt/senkt sich
     glatt, keine Sprünge)
   - `test_repositioning_ignores_cmd_vel`

6. **Doku-Anker für Slot-Mode (R4-Strategie):**
   - `src/hexapod_gait/README.md` — neue Sektion "Walking-Modes:
     Slot vs. Legacy" mit Beispiel-Aufrufen
   - `gait_node.py` Module-Docstring um Modus-Beschreibung erweitern
   - Memory `project_gait_node_slot_vs_legacy_mode.md` anlegen

**Offene A-Qs (in Stage-A-Plan-Doku zu entscheiden):**

| # | Frage | Vorschlag |
|---|---|---|
| A-Q1 | Slot-Wechsel via `ros2 param set /gait_node height_slot_index N` ODER eigenes Topic `/cmd_height_slot` (Int32)? | **Topic** — passt zum existing `/cmd_body_height`-Pattern, ist Hot-Path-freundlicher als Param-Roundtrip |
| A-Q2 | Default-Slot bei Start? | **Middle-Slot** (`len(slots) // 2`) — fängt vermutlich die aktuelle sim_walk.yaml -0.07 |
| A-Q3 | YAML-File fehlt → Verhalten? | **Auto-Fallback Legacy-Mode** mit WARN-Log statt Init-Error — Robustheit |
| A-Q4 | REPOSITIONING-Lift-Höhe? | **Param `repositioning_lift_height`, Default 0.03 m** — konservativ, anpassbar |
| A-Q5 | REPOSITIONING-Dauer pro Tripod-Sub-Phase? | **`repositioning_phase_duration`, Default 1.5 s** (gesamt ~3 s) — analog zu cycle_time-Skala |
| A-Q6 | Wer triggert REPOSITIONING — gait_node intern bei Slot-Wechsel oder Topic-Pub von außen erlaubt? | **Intern bei Slot-Wechsel** (auto). Topic `/trigger_repositioning` als Dev-Override möglich, nicht Pflicht |

### 7.2 Stage B — PS4-Mapping-Erweiterung

**Implementation-Items:**

1. **`src/hexapod_teleop/hexapod_teleop/joy_to_twist.py` Erweiterung:**
   - Modifier-State-Tracking (boolean flags für L1, L2, R2 button-states
     aus `/joy`-Topic)
   - Edge-Detection separat per (modifier-combo + D-Pad-Direction)
   - Publishen auf 5 neue Topics (siehe unten)
   - R1-Dead-Man + R1+D-Pad-Movement bleibt unverändert (Phase-6-Code)

2. **5 neue ROS-Topics** (gait_node subscribt):
   - `/cmd_height_slot_delta` (`std_msgs/Int8`: +1 oder -1) — L2 + D-Pad ↑/↓
   - `/cmd_radial_distance_delta` (`std_msgs/Int8`: +1 oder -1) — L2 + D-Pad ←/→
   - `/cmd_step_height_delta` (`std_msgs/Int8`) — R2 + D-Pad ↑/↓
   - `/cmd_step_length_delta` (`std_msgs/Int8`) — R2 + D-Pad ←/→
   - `/cmd_cycle_time_delta` (`std_msgs/Int8`) — L1+L2 + D-Pad ↑/↓

3. **`src/hexapod_teleop/config/ps4_usb.yaml` Mapping-Erweiterungen:**
   - Button-Indices für L1, L2, R1, R2, D-Pad-Achsen
   - Modifier-Mode-Konfiguration (welche Button-Combo löst welches Topic aus)
   - Step-Sizes pro Topic (passend zu §3.3): wahrscheinlich im
     gait_node, nicht im teleop (Teleop publisht nur +1/-1)

4. **gait_node-Subscribers** für die 5 neuen Topics + Verarbeitung:
   - Im STANDING-State: Delta auf aktuellen Parameter anwenden
   - `body_height` / `radial_distance`: REPOSITIONING-State auslösen
   - `step_height` / `step_length_max` / `cycle_time`: Param direkt
     updaten (kein Lift nötig)
   - In WALKING/STOPPING/REPOSITIONING: ignorieren + WARN-Log
   - Range-Clamp + WARN wenn out-of-range (z.B. Slot-Index außerhalb
     `[0, N-1]`)

5. **Unit-Tests:**
   - `test_modifier_state_tracking`
   - `test_edge_detection_per_modifier_combo`
   - `test_walking_param_delta_publish_correctness`
   - `test_gait_node_delta_processing_in_standing`
   - `test_gait_node_delta_ignored_in_walking`

**Offene B-Qs:**

| # | Frage | Vorschlag |
|---|---|---|
| B-Q1 | Delta-Topics (Int8 ±1) oder Absolut-Wert-Topics (Float64)? | **Delta** — einfacher PS4-Press-zu-Topic-Mapping, gait_node hält absoluten State |
| B-Q2 | 5 separate Topics oder 1 `/cmd_walking_param` mit Discriminator-Field? | **5 separate** — konsistent mit existing `/cmd_body_height`-Pattern, klarere Topic-Semantik |
| B-Q3 | Drei Modifier gleichzeitig (z.B. L1+L2+R2) — Verhalten? | **Strict-Priorität:** L1+L2 = cycle_time. Sonst L2 = höhe/radial. Sonst R2 = step. Wenn L1+L2+R2 alle gleichzeitig → erste-passende-Combo wirken lassen + WARN-Log |
| B-Q4 | Legacy-Mode L2/R2-Verhalten — Phase-6-continuous-cmd_body_height beibehalten? | **Legacy:** continuous L2/R2 = senken/anheben body_height (Phase 6 unverändert). Slot-Mode: discrete Delta. Mode-Switch via `use_height_slots`-Param |
| B-Q5 | Wann ist `R1 + L2 + D-Pad` valide — Movement oder Param-Adjust? | **R1 ist Dead-Man-Switch**, L2 ist Modifier. Wenn beide gleichzeitig: gait_node muss entscheiden. **Vorschlag:** STANDING-Constraint gewinnt — Param-Adjust nur wenn `STATE_STANDING` und kein cmd_vel im Flight. Im Doubt: keine Aktion + WARN. |
| B-Q6 | Foot-Trajectory-Visualisierung in rqt für REPOSITIONING-Verlauf? | **Out-of-Scope für Stage B** — Phase-13-Pendenz oder Dev-Tool später |

### 7.3 Stage C — Walking-Tests aufgebockt mit LUT

**Test-Workflow:**

1. Plugin starten (`real.launch.py`) — alle 6 Beine in T-Pose
2. gait_node mit `use_height_slots:=true` + sim_walk.yaml-Preset
3. Pro Slot (`index=0` bis `N-1`):
   - Slot-Wechsel via Topic-Pub `/cmd_height_slot_delta` ODER direkt
     `ros2 param set /gait_node height_slot_index <N>` (je nach A-Q1)
   - REPOSITIONING-Lauf abwarten (~3 s) — visuell glatt?
   - Stand-Pose visuell ok? Femur-Symmetrie rechts/links sauber
     (post-Stage-F)?
   - `cmd_vel` 0.02 m/s — Walking 30 s ohne IKError?
   - Zurück STANDING, dann nächster Slot
4. Wenn alle Slots durchlaufen:
   - Welche Slots sind 100% sauber?
   - Welcher ist der neue "Default" (ersetzt sim_walk.yaml -0.07)?
   - sim_walk.yaml ggf. updaten oder default-slot-index in gait_node anpassen

**Output:**
- Findings-Tabelle in Stage-C-Test-Commands-Doku (Slot × Stand-Pose-OK
  × Walking-OK × Auffälligkeiten)
- Ggf. neue Default-Slot-Entscheidung

**Offene C-Qs:**

| # | Frage | Vorschlag |
|---|---|---|
| C-Q1 | sim_walk.yaml automatisch updaten oder manuell entscheiden? | **Manuell** nach Stage C — User entscheidet welcher Slot Default wird, dann walking_envelope_check.py regeneriert sim_walk.yaml ODER gait_node-Default-Slot-Index wird angepasst |
| C-Q2 | Tempo-Treppe pro Slot oder nur Default-Tempo (0.02 m/s)? | **Nur Default-Tempo** in Stage C; Tempo-Treppe pro Slot ist Wiederholung von Stage E2.5, kommt später wenn Boden-Walking-Phase ansteht |
| C-Q3 | Bei Slot-Versagen (IKError mid-Walk) — STAGE abbrechen oder skip-and-continue? | **Skip-and-continue** — Stage soll alle Slots durchprobieren, am Ende die Reste-Liste bereinigen. Ggf. invaliden Slot aus height_slots.yaml entfernen |

### 7.4 Stage D — PS4-Vollbetrieb-Test aufgebockt

**Test-Workflow:**

1. `real.launch.py` + `gait_node` (Slot-Mode) + `joy_teleop` alle laufen
2. Test-Schritte sequenziell:
   - **R1 + D-Pad ↑/↓ + ←/→:** Walking verifizieren (Phase-6-Logik
     unverändert)
   - **L2 + D-Pad ↑:** body_height-Slot +1, REPOSITIONING-Visual ok?
   - **L2 + D-Pad ↓:** body_height-Slot -1
   - **L2 + D-Pad ←:** radial_distance -1cm, REPOSITIONING ok?
   - **L2 + D-Pad →:** radial_distance +1cm
   - **R2 + D-Pad ↑:** step_height +1cm (kein Lift, sofort wirksam)
   - **R2 + D-Pad ↓:** step_height -1cm
   - **R2 + D-Pad ←:** step_length_max -Step
   - **R2 + D-Pad →:** step_length_max +Step
   - **L1+L2 + D-Pad ↑/↓:** cycle_time ±0.5 s
   - Walking nach jedem Param-Change verifizieren (R1 + D-Pad)
3. **L1+L2-Ergonomie-Check:** ist Combo bequem haltbar (O1 aus §6)?
4. **Edge-Cases:**
   - Param-Verstellung in STATE_WALKING (R1 gehalten + L2-Press):
     korrekt ignoriert + WARN-Log?
   - Param-Verstellung in STATE_REPOSITIONING (während Slot-Wechsel
     läuft): korrekt ignoriert?
   - Modifier-Konflikt (L1+L2+R2 alle gehalten): Strict-Priorität wie
     in B-Q3 entschieden?

**Offene D-Qs:**

| # | Frage | Vorschlag |
|---|---|---|
| D-Q1 | Test-Reihenfolge — Walking first oder Param-Verstellungen first? | **Param first** — verifiziert Slot-Mode + Modifier-Logik, BEVOR Walking-Test-Komplexität dazukommt. Walking nach Param-Change als Sanity am Ende jeder Param-Stufe |
| D-Q2 | Erfolgs-Kriterium gesamt? | **Alle 5 Modifier-Kombis funktional + REPOSITIONING glatt + Walking nach Param-Wechsel weiterhin sauber + L1+L2-Ergonomie akzeptabel + Edge-Cases korrekt** |
| D-Q3 | Was wenn L1+L2-Combo physisch unbequem? | **Plan B in Memory festhalten:** alternative Modifier (z.B. Square+L2 oder PS+L2). Nicht Stage-D-Blocker, aber dokumentieren für späteren Mapping-Refactor |
| D-Q4 | Sollen wir Phase-13-Pi-Pendant testen (PS4 am Pi statt Desktop)? | **NEIN, out-of-scope** — Phase-12-Pi-Plattform-Stage. Hier nur Desktop. |

---

## 8. Cross-References

**Plan-Vorgänger:**
- [`servo_real_cal_plan.md`](servo_real_cal_plan.md) — Cross-Phase-
  Thread, alle Stages 0–E2 ✅
- [`servo_real_cal_stage_e2_hw_plan.md`](servo_real_cal_stage_e2_hw_plan.md)
  §13.1 — Femur-Asymmetrie-Finding aus E2.3

**Phase-13-Pi-Pendant:**
- [`phase_13_full_bringup.md`](phase_13_full_bringup.md) — Pi-Stufen
  A-I, kommt nach Phase 12. Stufe B dort = Pi-Recheck + Femur-Asym-
  Fix (jetzt vorgezogen am Desktop in Stage F)

**Tool:**
- [`tools/walking_envelope_check.py`](../tools/walking_envelope_check.py)
- [`tools/walking_envelope_check.README.md`](../tools/walking_envelope_check.README.md)

**Convention:**
- [`docs/00_conventions.md`](../docs/00_conventions.md) — Naming,
  Frames, Joint-Limits

**Memory-Einträge (relevant):**
- `project_servo_real_cal_done.md` — Cross-Phase-Thread DONE
- `project_phase13_femur_zero_asymmetry.md` — Stage F Pendenz
- `project_phase13_gait_launch_sim_time_default.md` — `use_sim_time:=false`
  auf HW Pflicht
- `project_gait_node_slot_vs_legacy_mode.md` — wird in Stage A angelegt
- `project_phase13_initial_pose_presets.md` — Cross-Phase-Outlook
- `project_hexapod_servo_models.md` — Servo-Specs (Diymore 8120MG /
  Miuzei MS61)

**Workflow-Regeln:**
- [`CLAUDE.md`](../CLAUDE.md) §4 — Plan-First, Self-Review, Tests-Grün
- [`PHASE.md`](../PHASE.md) — aktuelle Phase
- [`PHASE_NOTES.md`](../PHASE_NOTES.md) — Retros + Phasen-Schnitte-
  Begründungen

---

**Erstellt 2026-05-25.** Nächste Schritte: Stage F Plan + Test-Commands
schreiben (siehe Stage-Übersicht §2 Reihenfolge). Updates an PHASE.md /
README.md / servo_real_cal_plan.md / Memory kommen nach Stage F live.
