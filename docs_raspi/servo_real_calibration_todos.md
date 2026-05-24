# Servo-Real-Calibration — Cal-Daten & Findings

> **Status (2026-05-24):** Cal komplett, alle 18 Servos vermessen, Mount-
> Tausch leg_2↔leg_5 durchgeführt + nachkalibriert. Mount-Pattern ist
> jetzt **systematisch links/rechts gespiegelt**.
>
> Implementation läuft nach [`servo_real_cal_plan.md`](servo_real_cal_plan.md)
> (Stages 0–E). Diese Doku hier ist die **Daten-Quelle**, der Plan ist
> der **Umsetzungs-Vertrag**.

---

## 1. Ziel

Sauber-konsistente Cal aller 18 Servos im realen Hexapod, sodass:

1. **Cal-Werte** (`pulse_min`/`pulse_zero`/`pulse_max` pro Servo) auf
   den mechanischen Anschlägen oder Self-Collision-Grenzen basieren
2. **URDF-Joint-Limits** (`joint_lower`/`joint_upper` pro Joint) auf
   die echte erreichbare rad-Range gesetzt sind
3. **Math konsistent:** wenn IK rad=+0.5 kommandiert, geht der Servo
   physisch genau dorthin
4. **Walking funktioniert** im Sim UND auf echter Hardware

## 2. Hintergrund

In Phase 11 (rqt-Live-Cal abgeschlossen 2026-05-21) wurde erkannt,
dass die bisherige Cal aus `servo_calibration_approach.md` math-
inkonsistent ist — pulse_min/max basierten auf mech-Stops, aber URDF-
Limits waren pauschal ±1.57. Folge: Plugin-Math und IK-Position
divergierten.

Lösungsweg: **Weg B** — Cal-Werte UND URDF beide auf die echte
Hardware-Realität synchronisieren. Diese Doku enthält die Cal-Daten,
[`servo_real_cal_plan.md`](servo_real_cal_plan.md) dokumentiert die
Code-Umsetzung.

## 3. Cal-Daten (Stand 2026-05-24)

### 3.1 rad/µs-Konstante (Phase-1-Ergebnis)

**Validated über alle 18 Servos:** ~7.32 µs/° = **0.00237 rad/µs**

- Coxa (Diymore 8120MG, 270°-Servo): ~0.00239 rad/µs
- Femur (Miuzei MS61, 270°-Servo): ~0.00239 rad/µs
- Tibia (Miuzei MS61, 270°-Servo): ~0.00237 rad/µs
- Streuung: ±1-3% (= Servo-Toleranz, normal)

Sehr nah am Datenblatt-Wert 7.36 µs/° für 270°-Servos. Konstante
**0.00237 rad/µs** für alle 18 Servos verwendbar (= 422.0 µs/rad).

### 3.2 PWM-Werte für servo_mapping.yaml

Numerisch sortiert für Plugin-Schema (`pulse_min < pulse_zero < pulse_max`):

| Pin | Joint | pulse_min | pulse_zero | pulse_max |
|---|---|---|---|---|
| 0 | leg_1_coxa | 1145 | 1460 | 1700 |
| 1 | leg_1_femur | 815 | 1460 | 2120 |
| 2 | leg_1_tibia | 870 | 1680 | 2185 |
| 3 | leg_2_coxa | 1375 | 1575 | 1750 |
| 4 | leg_2_femur | 880 | 1550 | 2190 |
| 5 | leg_2_tibia | 860 | 1680 | 2200 |
| 6 | leg_3_coxa | 1200 | 1410 | 1745 |
| 7 | leg_3_femur | 800 | 1445 | 2100 |
| 8 | leg_3_tibia | 790 | 1620 | 2120 |
| 9 | leg_4_coxa | 1200 | 1520 | 1700 |
| 10 | leg_4_femur | 870 | 1560 | 2190 |
| 11 | leg_4_tibia | 815 | 1320 | 2140 |
| 12 | leg_5_coxa | 1350 | 1550 | 1750 |
| 13 | leg_5_femur | 860 | 1530 | 2190 |
| 14 | leg_5_tibia | 885 | 1390 | 2210 |
| 15 | leg_6_coxa | 1290 | 1530 | 1870 |
| 16 | leg_6_femur | 840 | 1540 | 2170 |
| 17 | leg_6_tibia | 850 | 1340 | 2170 |

> **Tausch-Historie:** leg_2 und leg_5 wurden ursprünglich (2026-05-21)
> physisch vertauscht montiert (Bein-Module). Am 2026-05-24 wurde das
> korrigiert; die hier eingetragenen Werte sind die nach-Tausch-Werte.
> Die Coxa-Servos sind body-fest und ändern sich beim Bein-Tausch nicht.

### 3.3 rad-Limits für URDF

Berechnet mit `rad_per_µs = 0.00237`:
- `joint_upper = (pulse_max − pulse_zero) × 0.00237`
- `joint_lower = (pulse_min − pulse_zero) × 0.00237`

| Pin | Joint | joint_lower | joint_upper |
|---|---|---|---|
| 0 | leg_1_coxa | -0.747 | +0.569 |
| 1 | leg_1_femur | -1.529 | +1.564 |
| 2 | leg_1_tibia | -1.920 | +1.197 |
| 3 | leg_2_coxa | -0.474 | +0.415 |
| 4 | leg_2_femur | -1.588 | +1.517 |
| 5 | leg_2_tibia | -1.943 | +1.232 |
| 6 | leg_3_coxa | -0.498 | +0.794 |
| 7 | leg_3_femur | -1.529 | +1.553 |
| 8 | leg_3_tibia | -1.967 | +1.185 |
| 9 | leg_4_coxa | -0.758 | +0.427 |
| 10 | leg_4_femur | -1.636 | +1.493 |
| 11 | leg_4_tibia | -1.197 | +1.943 |
| 12 | leg_5_coxa | -0.474 | +0.474 |
| 13 | leg_5_femur | -1.588 | +1.564 |
| 14 | leg_5_tibia | -1.197 | +1.943 |
| 15 | leg_6_coxa | -0.569 | +0.806 |
| 16 | leg_6_femur | -1.659 | +1.493 |
| 17 | leg_6_tibia | -1.161 | +1.967 |

> **Konvention:** Werte sind **PWM-zentrisch** — joint_upper ist die
> rad-Differenz von pulse_zero zu pulse_max (also „mechanisch-positive"
> Drehrichtung des Servos), joint_lower analog zu pulse_min. Die
> Joint-Konventions-Spiegelung (URDF-rad-Sign ≠ Mech-Drehung bei
> direction=-1) handhabt das Plugin nach Stage-0-Fix transparent —
> keine URDF-Spiegelung im Eintrag nötig.

### 3.4 Initial-Posen (Bauchlage + Testbench + Stand)

Drei vordefinierte Posen für Phase-13-Plugin-Initial-Pose-Mechanik.
Plugin schreibt diese PWM-Werte beim Boot **direkt zur Firmware**
(bypass Joint-rad-Mapping), kein IK involved. Hier nur Daten — die
Plugin-Erweiterung selber ist Phase-13-Material, siehe Memory
`project_phase13_initial_pose_presets.md`.

#### `pose_hardware_init` — Bauchlage

Hexapod liegt auf dem Bauch (Body horizontal am Boden). Default-Pose
beim Hardware-Boot bevor der Hexapod aufgerichtet wird.

- **Coxa:** `pulse_zero` (Bein radial nach außen vom Body weg)
- **Femur:** mech-Anschlag in „Bein-senkrecht-oben"-Richtung
  (Femur-Endpunkt zeigt zum Himmel)
- **Tibia:** mech-Anschlag in „Tibia-vom-Körper-weg"-Richtung
  (parallel zur Boden-Ebene)

Resultat: T-Pose-ähnliche Hocke, alle Bein-Spitzen liegen seitlich
neben dem Body am Boden. Stabile Ausgangsposition fürs Aufstehen.

| Pin | Joint | hw_init_pwm |
|---|---|---|
| 0 | leg_1_coxa | 1460 |
| 1 | leg_1_femur | 815 |
| 2 | leg_1_tibia | 870 |
| 3 | leg_2_coxa | 1575 |
| 4 | leg_2_femur | 880 |
| 5 | leg_2_tibia | 860 |
| 6 | leg_3_coxa | 1410 |
| 7 | leg_3_femur | 800 |
| 8 | leg_3_tibia | 790 |
| 9 | leg_4_coxa | 1520 |
| 10 | leg_4_femur | 2190 |
| 11 | leg_4_tibia | 2140 |
| 12 | leg_5_coxa | 1550 |
| 13 | leg_5_femur | 2190 |
| 14 | leg_5_tibia | 2210 |
| 15 | leg_6_coxa | 1530 |
| 16 | leg_6_femur | 2170 |
| 17 | leg_6_tibia | 2170 |

#### `pose_testbench_hang` — Aufgebockt, Beine hängend

Hexapod aufgebockt, Beine hängen senkrecht nach unten ohne
Bodenkontakt. Default-Pose für Test/Cal-Sessions am Bench.

- **Coxa:** `pulse_zero` (Bein radial vom Body weg)
- **Femur:** mech-Anschlag in „Bein-zu-Boden"-Richtung
  (Femur hängt senkrecht nach unten)
- **Tibia:** `pulse_zero` (Tibia in Verlängerung Femur, gerade)

Resultat: alle 6 Beine hängen senkrecht nach unten, gerade gestreckt.
Energetisch günstig — Schwerkraft hält Beine in dieser Position,
Servos müssen kein Drehmoment dauernd halten.

> **Pulse-zero-Note:** Tibia auf pulse_zero (= Bein-0°-rad) bedeutet
> Tibia ist exakt gerade (in Verlängerung Femur). Der Servo selbst
> steht dabei um den Mount-Offset (~155 µs ≈ 9°) von seiner
> geometrischen Mitte versetzt. Alternative wäre Servo-Mitte
> (= leicht gewinkelte Tibia, Servo zentriert) — bewusst nicht
> gewählt, weil „Bein gerade" das natürlichere Visual ist.

| Pin | Joint | testbench_pwm |
|---|---|---|
| 0 | leg_1_coxa | 1460 |
| 1 | leg_1_femur | 2120 |
| 2 | leg_1_tibia | 1680 |
| 3 | leg_2_coxa | 1575 |
| 4 | leg_2_femur | 2190 |
| 5 | leg_2_tibia | 1680 |
| 6 | leg_3_coxa | 1410 |
| 7 | leg_3_femur | 2100 |
| 8 | leg_3_tibia | 1620 |
| 9 | leg_4_coxa | 1520 |
| 10 | leg_4_femur | 870 |
| 11 | leg_4_tibia | 1320 |
| 12 | leg_5_coxa | 1550 |
| 13 | leg_5_femur | 860 |
| 14 | leg_5_tibia | 1390 |
| 15 | leg_6_coxa | 1530 |
| 16 | leg_6_femur | 840 |
| 17 | leg_6_tibia | 1340 |

#### `pose_standing` — Stand auf dem Boden

Hexapod steht auf eigenen Beinen am Boden, Body angehoben in
Walking-Standardhöhe. Wird **nicht hand-kalibriert** sondern
**aus RViz-IK abgeleitet**:

1. Phase 13: Stand-Pose in RViz konfigurieren (Body-Höhe + Foot-
   Positionen) via IK
2. RViz-Joint-States ablesen → entsprechende rad-Werte pro Joint
3. Joint-rad → PWM über Plugin-Cal-Math (nach Stage-0-Fix konsistent)
4. PWM-Werte hier eintragen + auf HW verifizieren (Servo-Position
   stimmt mit RViz visuell überein)

→ **PWM-Tabelle: TODO Phase 13** (kommt nach Stand-Verifikation auf
echter HW).

### 3.5 Findings & Pattern

Nach Mount-Tausch ist das Mount-Pattern systematisch links/rechts
gespiegelt — kein „Snowflake pro Bein" mehr.

**1. Femur-Konvention pro Bein-Seite:**

| Bein-Seite | Servo-Wirkrichtung | Konvention |
|---|---|---|
| rechts (leg_1, 2, 3) | PWM↑ = Bein↓ | A |
| links (leg_4, 5, 6) | PWM↑ = Bein↑ | B |

→ Konsequenz für Stage C (Direction-Cal): direction_normal-Map
wird voraussichtlich pro Bein-Seite einheitlich (statt 6× individuell).

**2. Tibia-Mount-Offset (Servo-Mitte vs Bein-0°-Pose):**

| Bein | Mount-Offset |
|---|---|
| leg_1 (r) | +155 µs |
| leg_2 (r) | +140 µs |
| leg_3 (r) | +160 µs |
| leg_4 (l) | −160 µs |
| leg_5 (l) | −190 µs ⚠ leicht erhöht |
| leg_6 (l) | −155 µs |

Mount-Offset entsteht weil das Servo-Horn auf diskreten Spline-Positionen
auf der Welle sitzt — die „perfekte" Mitte trifft man fast nie. Rechts
einheitlich +140/+160, links −155/−160, leg_5 leicht über dem Pattern
mit −190 µs (= ~26° Servo-Offset).

→ Asymmetrie pro Tibia: pulse_zero liegt nicht mittig zwischen
pulse_min und pulse_max. Plugin-Math nach Stage 0 handhabt das
sauber (siehe [`servo_real_cal_plan.md`](servo_real_cal_plan.md)
Stage 0).

**3. Coxa-Mount-Offset = 0:**

Bei allen 6 Coxa-Servos ist pulse_zero == Servo-Mitte (kein
mechanischer Mount-Versatz). Coxa-Asymmetrie kommt ausschließlich
aus dem Self-Collision-Limit (Nachbarbeine im Weg auf einer Seite).

**4. Range-Pair-Symmetrie:**

| Pair | Coxa Range | Femur Range | Tibia Range |
|---|---|---|---|
| leg_1 ↔ leg_6 | 555/580 µs | 1305/1330 µs | 1315/1320 µs |
| leg_2 ↔ leg_5 | 375/400 µs | 1310/1330 µs | 1340/1325 µs |
| leg_3 ↔ leg_4 | 545/500 µs | 1300/1320 µs | 1330/1325 µs |

Alle Paare innerhalb ±8% Diff → Mechanik ist sauber gebaut und
links/rechts gespiegelt.

**5. Mittel-Beine haben deutlich kürzere Coxa-Range:**

- Eck-Beine (leg_1, 3, 4, 6): ~70-80° Coxa-Range
- Mittel-Beine (leg_2, 5): ~50° Coxa-Range

Physikalisch plausibel — Mittel-Beine haben Nachbarn auf BEIDEN
Seiten (vorne+hinten), mehr Self-Collision-Constraints. Für Walking:
gait_node `step_length_max` so wählen dass Mittel-Beine mitkommen.

**6. leg_4 ↔ leg_5 Tibia rad-Limits IDENTISCH:**

Trotz unterschiedlicher absoluter PWM-Niveaus (Mount-Offsets −160 vs
−190 µs) sind die rad-Limits nach Berechnung identisch:
`(-1.197, +1.943)`. Indiziert dass die mechanische Range zwischen
linken Beinen sehr konsistent ist; die PWM-Verschiebung ist reine
Horn-Spline-Diskretisierung.

**7. Walking-Envelope-Befund (Stage E Sim-Vorab, 2026-05-24):**

Die Cal-Werte aus Tab. 3.3 sind **enger als die gait_node-Defaults aus
Phase 4-6 (±1.57)** annehmen. In Sim-Tuning (Stage E) ermittelt:

- **Default Stand-Pose (radial=0.27, body_height=-0.052) ist NICHT
  erreichbar** — fordert tibia=+1.332 rad, Limit ist nur +1.197
  (leg_1) bzw. +1.185 (leg_3).
- **Engster Bottleneck: leg_3 tibia_upper = +1.185 rad** beschränkt
  Stand-Pose-Höhe + radial_distance.
- **Working Sim-Preset (manuell tuned):** radial=0.30, body_height=-0.075,
  step_length_max=0.03, step_height=0.02 → linear_max=0.015 m/s
  (siehe `src/hexapod_gait/config/presets/sim_walk.yaml`).
- **Zweiter Bottleneck bei größeren step_length:** geometrische
  out-of-reach `L_femur + L_tibia = 0.2799 m`. Bei radial=0.30 +
  step_length>0.05 wird Foot-Drift > 0.2799.

→ **Implikation:** gait_node-Param-Tuning muss zur Cal passen, nicht
andersrum. Manuelles Try-and-Error in Sim ist ineffizient — die
Spec für ein systematisches Auto-Tuning-Tool ist in
[`walking_envelope_tool_spec.md`](walking_envelope_tool_spec.md)
beschrieben (geplant, noch nicht implementiert).

## 4. Implementation-Plan

Siehe **[`servo_real_cal_plan.md`](servo_real_cal_plan.md)** —
6 Stages (0, A–E) mit Logik-Skizze, Tests, Progress-Checkliste,
offenen Q&A-Punkten pro Stage.

Kurzübersicht:

| Stage | Was |
|---|---|
| **0** | Plugin-Math-Fix (direction-aware slope) + 2 neue Tests |
| **A** | URDF-Macro-Refactor (pro-Joint-Limit-Args) |
| **B** | servo_mapping.yaml mit Tab. 3.2 |
| **C** | Direction-Cal HW+RViz parallel (alle 18 Pins) |
| **D** | URDF mit Tab. 3.3 (PWM-zentrisch, keine Spiegelung) |
| **E** | Sim-Verifikation + Walking aufgebockt |

## 5. Was bewusst NICHT in dieser Cal-Pipeline ist

- **Pose-Management (Initial/Stand/Shutdown):** Phase-13-Material, Memory
  `project_phase13_initial_pose_presets.md`. Bauchlage-PWMs in
  Sektion 3.4 sind Reference-Daten für Phase 13, kein Stage-0-bis-E-Code.
- **Vel/Accel-Limit-Tuning unter Last:** Memory
  `project_phase10_real_yaml_vel_limits.md`, Phase-13-Pendenz.
- **Auto-Cal-Tool** für zukünftige Servo-Tauschs: Phase 13+ falls
  jemals gewollt.
- **Bodengebundenes Walking:** Stage E geht bis „aufgebockt walking
  grün". Boden-Walking ist Phase-13-Voll-Bringup-Sache.

## 6. Math-Quick-Reference

```
# Cal-Konstante (Phase 1):
rad_per_µs = 0.00237  rad/µs
           = 422.0    µs/rad   (= 1/rad_per_µs)

# rad-Limits aus PWM-Cal (Phase 2):
joint_upper = (pulse_max - pulse_zero) × 0.00237   # in rad
joint_lower = (pulse_min - pulse_zero) × 0.00237   # in rad

# Plugin-Math (nach Stage 0 Fix):
#   piecewise-linear um pulse_zero, slope direction-aware
#   für direction=+1 unverändert ggü altem Code
#   für direction=-1: slope_right und slope_left getauscht
```

## 7. Verbundene Dokumente

### Pflicht zum Lesen

1. [`CLAUDE.md`](../CLAUDE.md) — Projekt-Konvention, Workflow
2. [`PHASE.md`](../PHASE.md) — aktuelle Phase (Phase 12 aktiv, Cal-Arbeit Cross-Phase)
3. **[`servo_real_cal_plan.md`](servo_real_cal_plan.md)** — Implementation-Plan
4. Diese Datei — Cal-Daten + Findings

### Code-Quellen

- [`src/hexapod_hardware/src/calibration.cpp`](../src/hexapod_hardware/src/calibration.cpp)
  — Plugin-Math (vor Stage-0-Fix)
- [`src/hexapod_hardware/config/servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml)
  — aktuelle Cal (wird in Stage B überschrieben)
- [`src/hexapod_description/urdf/leg.xacro`](../src/hexapod_description/urdf/leg.xacro)
  — Bein-Macro (wird in Stage A erweitert)
- [`src/hexapod_description/urdf/hexapod_physical_properties.xacro`](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
  §11.4 — globale Joint-Limit-Defaults (bleiben unverändert)

### Memory-Einträge (automatisch geladen)

- `project_hexapod_servo_models.md` — Diymore + Miuzei Specs
- `project_phase11_convenience_aliases.md` — `hexapod-save-cal`-Alias
- `project_phase13_initial_pose_presets.md` — Phase-13-Pose-Management
- `feedback_decision_alternatives_log.md` — strukturierter Plan-Workflow
- `feedback_user_does_commits.md` — User committet selbst

---

**Erstellt 2026-05-21 nach erster Cal-Session. Updated 2026-05-24 nach
Mount-Tausch leg_2↔leg_5 + leg_5-Re-Cal. Daten sind final, Implementation
folgt [`servo_real_cal_plan.md`](servo_real_cal_plan.md).**
