# Stufe 3a — Leveling im WALKING

> Sub-Stufe von [Stufe 3](stage_3_walking_slope_plan.md) (Block A5). **Ziel:** das
> statische Körper-Leveling aus Stufe 2 auch **während des Laufens** wirken lassen —
> der Körper bleibt horizontal, während der Roboter auf einem milden Hang läuft.
> Kleinster Delta zu Stufe 2 (Stellpfad existiert, nur Gating + Scrub).
>
> **Status: ⚪ offen — §4-Plan-Review.** Voraussetzung: Stufe 2 (🟢).
> **Setpoint horizontal (α=0)**, Params **fix** (keine θ-Adaption — das ist 3c).

---

## 0. Kontext & Voraussetzungen

- Stufe 2 liefert `BalanceController`, `rotate_xy`-Stellpfad + Clamp + IKError-Fallback
  in der Engine, `/imu/data`-Sub + `_update_leveling` im Node — **aber gegated auf
  nur STANDING**. 3a hebt dieses Gating auf WALKING (+ STOPPING).
- Memory: **gz-IMU spawn-referenziert** → Roboter flach spawnen. Die Ramp-Welt
  (flach→Hang→flach) passt perfekt: Roboter spawnt flach, **läuft** in den Hang.

## 1. Logik-Skizze / Pseudocode

### A. Stellpfad-Gating auf WALKING (+ STOPPING) erweitern
- **Engine** (`compute_joint_angles`): die Leveling-Verzweigung von
  `state == STANDING` auf `state in (STANDING, WALKING, STOPPING)` erweitern. Der
  Rotations-Stellpfad (`_compute_leveled_ik`) bleibt unverändert — er dreht die
  Fuß-Targets, egal ob sie aus `_compute_standing_targets` oder den Walking-/
  Stopping-Trajektorien kommen (B4-Round-Trip auf beliebige Targets).
- **Node** (`_update_leveling`): Gating von `== STANDING` auf
  `in (STANDING, WALKING, STOPPING)`. Sonst (Aufstehen/Show/Stance-Switch/SAT): wie
  bisher Reset + Offset 0/0. STOPPING mitnehmen, damit der Körper beim Auslaufen
  nicht kurz „aufschnappt".
- Die Rotation wirkt **uniform auf alle 6 Fuß-Targets** (Swing + Stance). Für
  Swing-Beine (in der Luft) ist das harmlos — sie landen konsistent zur gelevelten
  Körperlage; für Stance-Beine entsteht der Scrub (B).

### B. Fuß-Scrub in der Stütz-Kette (Risiko 3)
- Im Stand war der Scrub ein Einmal-Effekt (~25 mm bei 10°). Im Lauf bewegen sich
  die Stance-Füße ohnehin (stance_traj); die Leveling-Rotation legt sich drauf.
- **Selbst-begrenzend:** jedes Bein hebt pro Cycle ab (Swing) und setzt neu auf →
  der Scrub **akkumuliert nicht**, er wird jeden Schritt zurückgesetzt. Walking ist
  hier **gutmütiger** als statisches Leveln.
- v1: **Slew-Limit (schon da) + kleine Winkel akzeptieren**, kein Reposition-Trigger
  (Risiko 3). Watch-Item in Sim: sichtbares Rutschen/Innere-Kräfte.

### C. Walking-max_level_angle + Hang-Grenzen (Offline gemessen)
- **Offline-Befund (Voll-Leveling = Körper horizontal, URDF-Limits + CoG):**
  - reiner **Pitch** (gerade hoch/runter): in-limit bis **~25°**
  - reiner **Roll** (seitlich/quer): bis **~20°**
  - **kombiniert/diagonal**: nur bis **~10°** (schwache Achse)
  - **CoG unkritisch** (Marge 155–200 mm bis 30°); **Reibung** µ=1.2 → Rutschen erst
    ~50°. → Der Engpass beim Voll-Leveling sind die **Joint-Limits**, nicht Kippen/Schlupf.
- **Walking-Hülle:** `tools/leveling_envelope_check.py` auf einen ganzen Walking-Cycle
  bei θ erweitern (Phasen abtasten, schlimmste zählt) → bestätigt den Walking-Wert.
- **Walking-Hülle (Offline gemessen, Fallback-frei, Default-step_height):** uniformes
  Leveling auf ALLE Beine cappt bei **~4° (Pitch/Roll), ~2° (combined)** — der gelevelte
  **Swing-Apex** (Fuß hoch, nahe Tibia-Limit) bindet. Nur-Stance-Leveln gäbe ~13°, aber
  mit ~25 mm Touchdown-Sprung → verworfen (User-Wahl: uniform, sauber).
- **Clamp-Politik 3a = state-abhängig:** `leveling_max_angle_deg` = **10°** (STANDING,
  Stufe-2-Hülle, kein Regress) · neuer `leveling_max_angle_walking_deg` = **4°**
  (WALKING/STOPPING). Engine wählt nach State. Kein Phase-Flackern, kein Stand-Regress.
  **Mehr Walking-Range = 3c** (hang-bewusste Schwunghöhe + Param-Adaption — NICHT
  step_height blind senken, sonst Schürf-Gefahr bergauf; User-Hinweis).
- **Echter Climbing-Ceiling = Servo-Torque (HW, Block A)**, nicht Kinematik/CoG/Reibung.
  In Sim (kein Servo-Limit) sind 30° machbar; auf HW mit Torque-Tool messen.

### D. Ramp-/Keil-Welt (flach→Hang→flach), parametrisch
- `ramp.sdf.xacro` (analog `slope.sdf.xacro`): ebener Anlauf + geneigte Rampe (**Winkel
  via Arg**) + ebenes Plateau. Roboter spawnt **flach** auf dem ebenen Teil, läuft per
  `cmd_vel` in die Rampe. Hohe Reibung (µ≥1.0). Welt-Name „empty" behalten.
- **Test-Ladder (User):** **0, 6, 12, 18, 24, 30°** (0 + bis Maximum in Schritten, Max
  als letzter). Zeigt die Sim früher Schluss (Dynamik/Scrub/Torque-frei aber Kippen),
  wird der real erreichte Winkel der letzte (z.B. „…, 24°").

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| Unit/Engine Leveling@WALKING | Offset wird in WALKING **und** STOPPING angewandt (nicht nur STANDING); Round-Trip; Offset 0 → unverändert | pytest grün |
| Offline-Walking-Hülle vs θ | gelevelter Walking-Cycle bei θ∈{6,12,18,24,30°} in-limit (schlimmste Phase, pitch/roll/combined) → Walking-max_level_angle | Tool grün |
| Sim (live, am Ende) | Rampe **hoch + runter** (Ladder 0/6/12/18/24/30°): Körper levelt (IMU pitch sinkt Richtung 0 bis zum Clamp), **kein** Freeze, Scrub klein; messen wo es real bricht | Ground-Truth + IMU |

**Bewusst NICHT:** θ→Parameter-Adaption (3c), Gyro-Wackel-Dämpfung (3b),
Gangart-Auto-Switch (3c), Slip (3d), per-Fuß-Terrain (Stufe 4).

## 3. Progress-Checkliste (Template → Progress-File)

```
- [ ] 3a.1 Stellpfad-Gating Engine+Node auf WALKING (+STOPPING) erweitert
- [ ] 3a.2 Offline-Walking-Hüllen-Check vs θ (Tool-Erweiterung) → leveling_max_angle (Walking) bestätigt
- [ ] 3a.3 Ramp-Welt ramp.sdf.xacro (flach→Hang→flach) + Launch-Resolve (flach spawnen)
- [ ] 3a.4 Unit/Engine-Tests (Leveling in WALKING+STOPPING, Round-Trip, Offset 0)
- [ ] 3a.5 Sim-Verify Rampe hoch/runter gelevelt + kein Freeze + Scrub ok (test_commands)
- [ ] 3a.6 README/Konzept-Update (Gating WALKING, Walking-Scrub, Ramp-Welt)
- [ ] 3a.7 colcon test + Lint grün
- [ ] 3a.8 kritische Self-Review-Tabelle
```

## 4. Offene Punkte für User-Review (vor Code entscheiden)

- **Gating-Umfang:** WALKING **+ STOPPING** *(Vorschlag — sonst „schnappt" der Körper
  beim Auslaufen)* vs. nur WALKING?
- **Fuß-Scrub:** Slew + kleine Winkel akzeptieren *(Vorschlag — Walking setzt die Füße
  jeden Schritt neu, Scrub akkumuliert nicht)* vs. Reposition-Trigger?
- **Walking-max_level_angle:** denselben Param `leveling_max_angle_deg` wiederverwenden,
  Wert = min(statisch 10°, Walking-Offline-Ergebnis) *(Vorschlag)* vs. eigener
  Walking-Param?
- **Leveling auf Swing-Beine:** uniform auf alle 6 Targets *(Vorschlag — konsistente
  Körperlage, für Swing harmlos)* vs. nur Stance-Beine drehen?
- **Ramp-Welt-Geometrie:** eine Rampe (eben→Steigung→Plateau) *(Vorschlag)* vs. nur
  geneigte Ebene wie Stufe 2; Winkel via Arg, mild (3/5/8°)?
- **Test-Tuning:** Slew evtl. höher im Lauf (schnellere Hang-Folge) — auf der Rampe
  nachziehen, Startwerte = Stufe-2-Werte.

## 5. Design-Entscheidungen (vorläufig — final beim Plan-Review)

| Entscheidung | Gewählt (Vorschlag) | Alternative | Warum |
|---|---|---|---|
| Gating | STANDING+WALKING+STOPPING | nur WALKING | kein Aufschnappen beim Auslaufen |
| Scrub | Slew + kleine Winkel | Reposition-Trigger | Walking resettet Füße je Schritt (kein Akkumulieren) |
| Stellpfad | uniform auf alle 6 Targets (Swing+Stance) | nur Stance (~13° aber Touchdown-Sprung) | konsistente Körperlage, kein Touchdown-Jump; **Swing-Apex bindet** → kleiner Walking-Clamp |
| Clamp | **state-abhängig**: STANDING 10° (Stufe-2-Hülle), WALKING/STOPPING 4° (Offline: Swing-Apex bindet bei Default-step_height) | ein Param / immer 10° + Fallback | kein Stand-Regress, kein Phase-Flackern; mehr Walking-Range = 3c |
| Welt | Ramp (eben→Hang→Plateau), flach spawnen | geneigte Ebene | reales „in den Hang laufen", IMU welt-referenziert |
