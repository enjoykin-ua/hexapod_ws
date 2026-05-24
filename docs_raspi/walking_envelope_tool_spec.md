# Walking-Envelope-Check-Tool — Spec & Konzept

> **Status:** ✅ implementiert 2026-05-24 unter
> [`tools/walking_envelope_check.py`](../tools/walking_envelope_check.py)
> + Tests [`tools/test_walking_envelope_check.py`](../tools/test_walking_envelope_check.py)
> (11/11 pytest grün).
>
> **Verwendung:** ausführliche Doku im File-Kopf
> [`tools/walking_envelope_check.py`](../tools/walking_envelope_check.py).
>
> Diese Spec hier bleibt als Konzept-Beleg + Architektur-Beschreibung.

---

## 1. Problem-Statement

Nach Stage D haben wir 18 echte Joint-rad-Limits pro Bein im URDF. Die
gait_node-Defaults aus Phase 4-6 (radial_distance=0.27, body_height=-0.052
etc.) waren für unrealistisch-breite ±1.57-Limits getuned. Mit den
engeren HW-Cal-Werten gilt:

1. **Nicht jede Stand-Pose ist erreichbar** — engste Cal-Werte
   beschränken `(radial_distance, body_height)`-Kombinationen.
2. **Nicht jeder step_length_max** ist innerhalb des Stand-Pose-
   Walking-Envelopes — Foot-Drift im Stride muss in IK-Range bleiben.
3. **Engster Bottleneck wechselt** je nach Param-Wahl:
   - bei kleinem radial: leg_3 tibia_upper (+1.185 rad)
   - bei großem radial: max-reach `L_femur+L_tibia` (0.2799 m) →
     geometrische out-of-reach
   - bei extremem y-Offset (cmd_vel.linear.y): coxa-Range, Mittel-Beine
     leg_2/leg_5 mit nur ±0.42 rad

Manuelles Tuning durch try-and-error in Sim findet zwar Working-Combos
(siehe `config/presets/sim_walk.yaml`), aber:

- ist langsam (Sim-Restart, cmd_vel-publish, beobachten, repeat)
- ist nicht reproduzierbar (Cal-Updates ändern Limits → Tuning veraltet)
- gibt keinen Überblick über die **Form** des Envelopes (welcher Param
  ist am limitierendsten? Wie viel Reserve in welche Richtung?)

→ Brauchen ein systematisches Tool das offline (ohne Sim) den Envelope
berechnet.

---

## 2. Was das Tool tut

### Mode A — Single-Config-Check

**Eingabe:** ein Satz gait_node-Parameter (entweder als YAML-File oder
als CLI-Args).

**Verarbeitung:**
1. URDF parsen (oder direkt `hexapod_kinematics.HEXAPOD` + Stage-D-Limits aus Cal-Doku)
2. `gait_engine.GaitEngine` mit den Params instanziieren
3. Pro Bein-Cycle (t = 0..cycle_time in 50-Hz-Ticks):
   - `compute_foot_targets(t)` für ein simuliertes cmd_vel-Setup
   - Für jedes Foot-Target: `leg_ik(*target, leg_cfg, joint_limits=...)`
   - Wenn `IKError("joint limit ...")`: Bein/Joint/rad/limit notieren
   - Wenn `IKError("out of reach ...")`: Bein/d/reach-range notieren
4. Min/Max der erreichten rad-Werte pro Bein/Joint sammeln

**Ausgabe:**
- `✓ GREEN` oder `❌ RED` (irgendwo IKError im Cycle)
- Pro Bein/Joint: erreichte rad-Min/Max, Reserve zum Limit
- Bei RED: kritischer Tick + Foot-Position + Bein + Grund

**Use-Case:** Du änderst Param XYZ, ruft Script → in < 1 s siehst du
ob's geht. Kein Sim-Restart nötig.

### Mode B — Height-Sweep (User-Konzept 2026-05-24)

**Eingabe:** body_height-Range (z.B. `-0.080 ... -0.030, step 0.01`) +
fixe Restparameter (gait_pattern, cycle_time, step_height).

**Verarbeitung:** für jede body_height:
1. **Optimales radial_distance** finden (binary search):
   - radial muss so groß sein dass Stand-Tibia-Limit eingehalten wird
   - radial muss so klein sein dass max-reach (`L_F+L_T`) bei Walking-Foot-Drift nicht überschritten
2. **Maximum step_length_max** finden (binary search bei optimalem radial):
   - größtes step_length bei dem alle 6 Beine alle Cycle-Ticks lang ohne IKError durchkommen

**Ausgabe — Tabelle:**

| body_height | radial_distance | max step_length_max | max linear_max | Bottleneck-Joint |
|---|---|---|---|---|
| -0.040 | 0.32 | 0.025 | 0.025 m/s | leg_3 tibia_upper |
| -0.050 | 0.31 | 0.030 | 0.030 m/s | leg_3 tibia_upper |
| -0.060 | 0.30 | 0.035 | 0.035 m/s | reach-cone (leg_2) |
| -0.070 | 0.30 | 0.040 | 0.040 m/s | reach-cone |
| -0.075 | 0.30 | 0.045 | 0.045 m/s | reach-cone |
| -0.080 | 0.29 | 0.038 | 0.038 m/s | leg_2 coxa |

**Use-Case:** Du willst Hexapod auf bestimmter Höhe (z.B. -0.06 weil
visuell schöner). Aus Tabelle siehst du: maximaler Walking-Speed 0.035 m/s
mit radial=0.30 und step_length=0.035. Direkt eintragen, kein Tuning.

### Mode C — Visualisation (optional, später)

Heatmap mit body_height (x-Achse) × radial_distance (y-Achse) ×
step_length_max (Farbe). Zeigt sofort wo die Sweet-Spots liegen.

→ matplotlib + ggf. interaktiv. Phase-13-nice-to-have.

---

## 3. Math-Komponenten

### 3.1 IK-Joint-Limit-Check pro Foot-Target

Ist bereits in `hexapod_kinematics.leg_ik` implementiert (Stage 0.6).
Tool nutzt diese Funktion direkt — keine Math-Replikation.

### 3.2 Walking-Foot-Trajectorie pro Tick

Ist in `hexapod_gait.gait_engine.compute_foot_targets(t)` implementiert.
Tool nutzt diese Funktion direkt.

### 3.3 cmd_vel-Setup für Sweep

Worst-Case cmd_vel = `linear_max` in jede Richtung (linear.x, linear.y,
angular.z separat). Tool führt 3 Sweep-Runs durch (eins pro Achse) +
optional Diagonal-Mix.

### 3.4 Cycle-Sampling

Pro Cycle 50 Ticks (= 50 Hz × cycle_time). Reichend für Joint-Min/Max-
Detection (Bezier-Trajectorie ist glatt).

---

## 4. Implementation-Skizze

**Datei:** `tools/walking_envelope_check.py` (~150 Zeilen Python)

**Dependencies:** kein ROS nötig — pure Python.
- `hexapod_kinematics` (für IK + HEXAPOD config)
- `hexapod_gait.gait_engine` + `gait_patterns` (für Trajectorie)
- `hexapod_gait.gait_node.parse_joint_limits_from_urdf` (für URDF-Parse)

**CLI:**
```bash
# Mode A: Single check
python3 tools/walking_envelope_check.py check \
  --radial 0.30 --body-height -0.075 --step-length 0.03 --step-height 0.02

# Mode B: Height sweep
python3 tools/walking_envelope_check.py sweep \
  --height-min -0.080 --height-max -0.030 --height-step 0.01
```

**Output Mode A:**
```
=== Walking-Envelope Check ===
gait_node params: radial=0.300, body_height=-0.075, step_length_max=0.030, step_height=0.020
URDF-Source: install/.../hexapod.urdf.xacro

Cycle simulated: 0.0 .. 2.0 s (50 ticks)
cmd_vel scenario: linear.x = +linear_max = 0.015 m/s

Per-leg rad min/max:
  leg_1 coxa  : -0.012 .. +0.012  (limits -0.747 / +0.569,  84% Reserve coxa+)
  leg_1 femur : +0.612 .. +0.687  (limits -1.529 / +1.564,  56% Reserve femur+)
  leg_1 tibia : +1.094 .. +1.131  (limits -1.920 / +1.197,   5% Reserve tibia+)  ⚠ knapp
  leg_2 coxa  : ...
  ...

Result: ✓ GREEN
Bottleneck: leg_3 tibia_upper at t=0.42s (rad=1.181, limit=1.185, 0.004 Reserve)
```

**Output Mode B:**
```
=== Height Sweep ===
body_height ranges -0.080 .. -0.030 step 0.01

  height  radial  max_step_len  linear_max  bottleneck
  -0.030    -        -            -          unreachable
  -0.040  0.320  0.025          0.025       leg_3 tibia_upper
  ...
  -0.075  0.300  0.045          0.045       reach-cone (leg_1)
  -0.080  0.295  0.038          0.038       leg_2 coxa
```

---

## 5. Wie der User das Tool benutzt

### Szenario 1 — Schnellcheck nach Param-Edit

Du hast in einem YAML `radial_distance=0.32, step_length_max=0.04`
eingetragen. Bevor du Sim startest:

```bash
python3 tools/walking_envelope_check.py check --params-file <yaml>
```

Wenn GREEN: in Sim laden, läuft sicher durch.
Wenn RED: Output sagt dir welcher Bottleneck wo, du adjustest, repeat.

### Szenario 2 — „Ich will Hexapod auf Höhe X — was geht?"

```bash
python3 tools/walking_envelope_check.py sweep
```

Tabelle anschauen. Höhe wählen. Werte aus der Zeile in dein Preset YAML
kopieren. Done.

### Szenario 3 — Nach Cal-Update

Wenn in Phase 13 die Cal-Werte aktualisiert werden (z.B. Direction-Cal
oder neue Mech-Anschläge): Sweep neu laufen lassen, neuer Sim-Preset
ist berechnet statt geraten.

---

## 6. Was das Tool NICHT macht

- **Servo-Mechanik / Drehmoment / Strom-Limits** — Tool ist rein
  kinematisch. Bei Walking unter Last könnten Servos hängen bleiben
  was Tool nicht sieht. Phase-13-Bench-Test.
- **Body-Tilt-Stabilität** — Tool prüft Foot-Trajectories pro Bein, nicht
  ob Hexapod kippt. Sim mit Physics fängt das ab.
- **Gait-Patterns andere als tripod** — Default-Run nutzt tripod.
  Andere Patterns (single_leg_X) brauchen Pattern-Arg.
- **Optimierung „besser als max"** — Tool findet maximal-erlaubt, nicht
  optimal-stabil. Für stabile Walking brauchts ggf. konservativeren
  Wert (90% des max).

---

## 7. Implementation-Reihenfolge wenn wir's bauen

1. **Mode A (Single-Check)** — ~30 min, sehr nützlich für Tuning-Iterationen
2. **Mode B (Sweep)** — ~1 h, baut auf Mode A auf (Optimizer-Loop)
3. **Mode C (Visualisation)** — optional, ~30 min mit matplotlib
4. **Tests** — pytest, ~30 min

**Gesamt:** ~2-3 h, low-risk weil nutzt vorhandene gait_engine + leg_ik.

---

## 8. Verwandte Dokumente

- [`servo_real_calibration_todos.md`](servo_real_calibration_todos.md) Tab. 3.3 — Cal-rad-Limits (Input)
- [`servo_real_cal_plan.md`](servo_real_cal_plan.md) Stages 0.6 + D — IK-Joint-Limit-Check ist die Math-Basis
- [`servo_real_cal_stage_e_sim_plan.md`](servo_real_cal_stage_e_sim_plan.md) — der Stage-E-Tuning-Aufwand der dieses Tool motiviert
- [`src/hexapod_gait/config/presets/sim_walk.yaml`](../src/hexapod_gait/config/presets/sim_walk.yaml) — manuell getunete Walking-Envelope-Werte (Stage E 2026-05-24)

---

**Erstellt 2026-05-24 nach Stage E (Sim-Vorab) Tuning-Erfahrung. Tool
ist noch nicht implementiert — Spec dient als Vertrag für die spätere
Implementation.**
