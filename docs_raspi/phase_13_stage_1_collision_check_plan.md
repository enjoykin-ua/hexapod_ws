# Phase 13 Stage 1 / Teil 2 — Selbst-Kollisions-Check (Weg B-Voll) + Lauf-Reichweite freischalten

> **STATUS: ⏸️ DEFERRED — verschoben (Re-Decision User 2026-06-02).**
> Für das **reine Vorwärts-/Omni-Laufen** (Stage 1) wird der Laufzeit-Kollisions-Check
> **nicht gebraucht**: Gait + Standup halten den Femur immer oben und die Füße außen,
> die kollisionsgefährdete Ecke wird nie kommandiert. Stattdessen wurde das Tibia-Limit
> hart auf das strikt-symmetrische Mechanik-Max **+2.50** freigeschaltet (Weg A), mit
> Design-Zeit-Sicherheit per Envelope-Check. Umsetzung:
> **[`phase_13_stage_1_tibia_unlock_plan.md`](phase_13_stage_1_tibia_unlock_plan.md)**.
>
> **Dieser Plan (Weg B) bleibt gültig und wird nachgerüstet, wenn dynamische Posen
> dazukommen** (Balance / unebener Boden / Body-Pose-Teleop) — dort triggert der Check
> echt und ist die saubere, geometrie-getriebene Lösung. Begründung des femur-gekoppelten
> Befunds weiter unten + in `phase_13_stage_1_walk_optimization_plan.md` §4.2.0.
>
> ---
>
> **(historisch) Entscheidung 2026-06-01:** Weg B-Voll — geometrie-getriebener
> Selbst-Kollisions-Check (Fuß + Tibia-Segment vs Body) statt starrem konstantem
> Tibia-Limit. Am 2026-06-02 für Stage 1 zugunsten Weg A (hart freischalten) zurückgestellt.

---

## 0. ⭐ FÜR DEN NÄCHSTEN CHAT: Was zuerst lesen
1. **`CLAUDE.md`** §4 (Plan→Freigabe→Tests→Self-Review), §5 (Shell-Verbote), §9 (HW-Safety).
2. **`PHASE.md`**, **`docs/00_conventions.md`** §11.4 (Limits).
3. **`phase_13_stage_1_walk_optimization_plan.md`** — der Übergeordnete: §1 Warum,
   §2 Sichtweisen, **§4.2.0 der zentrale femur-gekoppelte Kollisions-Befund**, Teil 1 (RViz).
4. **DIESE Datei** komplett.

**Code, der gelesen/geändert wird:**
- **`src/hexapod_kinematics/hexapod_kinematics/leg_ik.py`** — hier kommt der Check rein
  (analog zum bestehenden `joint_limits`-IKError-Pfad aus Stage 0.6).
- **`src/hexapod_kinematics/hexapod_kinematics/geometry.py`** / `config.py` — Bein-Längen,
  Mount-Transform; ggf. neues Modul `collision.py` für das Body-Modell.
- **`src/hexapod_description/urdf/hexapod_physical_properties.xacro`** — die **echten
  Body-Maße** (`body_length 0.175`, `body_width 0.130`, `body_height 0.043`, Coxa-Box).
- **`hexapod.urdf.xacro`** / `ros2_control.xacro` / config.py — Tibia-`upper` aufs
  mechanische Maximum (~+2.6) anheben (der Check übernimmt die Sicherheit).
- **`src/hexapod_hardware/config/servo_mapping.yaml`** — Tibia-`pulse_min/max` nachziehen (k=425).
- **`tools/walking_envelope_check.py`** + `standup_envelope_check.py` — sollten den
  Kollisions-Check **mitnutzen**, damit die Tool-Validierung der echten Sicherheit entspricht.
- **Memory:** `project_two_joint_limit_sources`, `project_phase11_convenience_aliases`.

---

## 1. Warum (kurz)
Das Tibia-Beuge-Limit ist **femur-gekoppelt** (Body-Kollision): Femur oben → Tibia ~150°,
Femur unten → ~90°. Ein **konstantes** URDF-Limit kann das nicht abbilden — entweder zu
konservativ (verschenkt Lauf-Reichweite) oder unsicher. Ein **geometrischer Selbst-
Kollisions-Check** löst das exakt: das Tibia-Joint-Limit darf aufs mechanische Maximum,
und der Check verhindert pose-abhängig, dass der Fuß in den Body fährt. Damit wird die
**feet-closer Lauf-Pose** (kleineres radial, mehr Stride) sicher möglich.

---

## 2. Logik-Skizze (Weg B-Voll)

### 2.1 Body-Kollisions-Modell (aus echten Maßen, nicht hardkodiert)
- **Chassis-Box:** zentriert auf `base_link`, `body_length × body_width × body_height`
  (aus `hexapod_physical_properties.xacro`). + ggf. die Coxa-Segmente (seitliche Auswüchse).
- **Sicherheitsmarge** `m` (Param, HW-kalibriert gegen die echten Stopp-Punkte).
- Repräsentation: eine `BodyCollision`-Struktur (Box-Halbmaße + Marge), aus den
  config/xacro-Werten gebaut → ändern sich die Maße, passt sich das Modell an.

### 2.2 Der Check (Fuß + Tibia-Segment vs Body) — **B-Voll**
Gegeben eine Pose (coxa/femur/tibia):
1. FK → **Knie-Punkt** + **Fuß-Punkt** in `base_link` (Transform via mount_yaw/xyz —
   die Logik existiert schon in `reachability_viz._foot_base`; Knie analog mit nur Femur).
2. **Fuß-vs-Box:** liegt der Fuß-Punkt in der Body-Box (+ Marge)? → Kollision.
3. **Segment-vs-Box:** schneidet die Strecke Knie→Fuß die Body-Box (+ Marge)? → Kollision.
   (Segment-AABB-Schnitt, Standard-Geometrie.)
- **B-min** wäre nur Schritt 2 (Fuß); **B-Voll** = Schritt 2 **+** 3 (Segment) → fängt
  auch „Bein streift den Body, Fuß noch außen". Bein-Bein (B-max) **weggelassen**
  (Hexapod-Coxa ±24° → praktisch nie).

### 2.3 Integration in `leg_ik` (gleiches Muster wie der Joint-Limit-Check)
- `leg_ik` bekommt ein **optionales** `body_collision`-Arg (Modell + Marge).
  - **Übergeben** → nach Winkel-Berechnung + Joint-Limit-Check zusätzlich Kollisions-Check;
    bei Treffer `IKError("self-collision: Fuß/Tibia im Body")`.
  - **Nicht übergeben** → lenient (Backwards-Compat, wie beim `joint_limits`-Arg).
- Gait-Engine + Standup fangen `IKError` schon → `safety_freeze`. Der Check ist also ein
  **Sicherheitsnetz + Enabler**: er erlaubt das höhere Tibia-Limit, ohne dass die IK je
  versehentlich eine body-kollidierende Pose erzeugt.
  > **Wichtig:** Beim Laufen sind die Füße weit außen (radial ≥0.25) → der Check
  > **triggert im Normalbetrieb nie**. Sein Wert ist: das Tibia-Limit sicher hochsetzen
  > zu dürfen. Die Gait-Trajektorien bleiben kollisionsfrei by design.

### 2.4 Tibia-Limit aufs mechanische Maximum anheben
- Mit dem Check als Wächter: URDF-Tibia-`upper` → mechanisches Max (~+2.6 / 149°, aus
  0.6.5) in xacro + ros2_control + Property + config.py; servo_mapping `pulse_min/max`
  = `pulse_zero ∓ 425·limit` (k=425), innerhalb [500,2500]; `pulse_min<zero<max`; 1500 in-range.
- generierte URDF verifizieren; `test_config.py`-Cross-Check.

### 2.5 (danach) Feet-closer Lauf-Pose + Re-Tune
- Mit höherem Limit + Check: kleineres `radial` (Füße näher) → mehr Vorwärts-Reichweite.
  Mit `walking_envelope_check recommend` (das jetzt den Kollisions-Check mitnutzt) die
  validierte (radial/step_length/step_height)-Config finden; `cycle_time` für Tempo.
- Trade-off Sidestep (kleines radial stresst Coxa) → omnidirektional vs vorwärts-optimiert (§7.5).

### 2.6 (danach) Zwei-Phasen Standup → Reposition → Walk
- Aufstehen (Füße-draußen, Touchdown-sicher) → in STANDING per Tripod 3+3 die Füße auf
  die nähere Lauf-Pose umsetzen → laufen. (Eigene Engine-Erweiterung, evtl. eigene Sub-Stage.)

---

## 3. Tests-Liste mit Begründung
### 3.1 Pure-Python / Unit
| Test | Prüft |
|---|---|
| `collision`-Unit: Posen klar im Body → Kollision, Posen außen → frei | Korrektheit Box + Segment-Check |
| Marge-Verhalten (knapp innen/außen) | Marge greift |
| `leg_ik` mit `body_collision`-Arg wirft IKError bei Kollision; ohne Arg lenient | Integration + Backwards-Compat |
| IK-Regression (bestehende Tests ohne Arg unverändert grün) | nichts kaputt |
| `walking_envelope_check` / `standup_envelope_check` mit Kollisions-Check noch GRÜN für die genutzten Posen | Tool-Konsistenz |
### 3.2 Live (HW aufgebockt)
| Test | Prüft |
|---|---|
| Tibia-Sweep über neues Max → Check stoppt **genau dort wo Fuß/Body kollidieren** (vs User-Hand-Beobachtung) | Marge HW-kalibriert |
| Laufen aufgebockt mit feet-closer Pose → kein Freeze (Check triggert nicht), größere Schritte | Enabler funktioniert |
### 3.3 Bewusst NICHT
- Bein-Bein-Kollision (B-max), genaues Coxa-Auswuchs-Modell (erst falls nötig).

---

## 4. Progress-Checkliste (→ eigener Progress-Abschnitt)
```
### Teil 2a — Body-Kollisions-Check (Weg B-Voll)
- [ ] 2a.1  BodyCollision-Modell aus physical_properties (Box + Marge-Param)
- [ ] 2a.2  Check: Fuß-vs-Box + Tibia-Segment-vs-Box (collision.py / in leg_ik)
- [ ] 2a.3  leg_ik: optionales body_collision-Arg → IKError bei Kollision (lenient ohne Arg)
- [ ] 2a.4  Unit-Tests (in/out/Marge) + IK-Regression grün
- [ ] 2a.5  gait_node/Engine + Standup übergeben das Modell an leg_ik
- [ ] 2a.6  walking_/standup_envelope_check nutzen den Check mit
- [ ] 2a.7  HW: Check-Stopp-Punkt vs User-Hand-Beobachtung → Marge kalibriert

### Teil 2b — Tibia-Limit aufs Mechanik-Max
- [ ] 2b.1  URDF/ros2_control/Property/config.py Tibia-upper → ~+2.6 (k=425, pulse_min/max)
- [ ] 2b.2  colcon build + test (hardware/kinematics/gait) grün; generierte URDF verifiziert
- [ ] 2b.3  standup_envelope_check noch GRÜN
- [ ] 2b.4  Live aufgebockt: Tibia fährt neuen Bereich, Check greift an der Kollisionsgrenze

### Teil 2c — Feet-closer Lauf-Pose + Re-Tune
- [ ] 2c.1  walking_envelope_check recommend (mit Check) → validierte Config
- [ ] 2c.2  radial/step_length/step_height/cycle gesetzt (+ Sidestep-Entscheidung §7.5)
- [ ] 2c.3  Sim → HW griffiger Boden: echter Vortrieb, größere Schritte
- [ ] 2c.4  Preset gespeichert

### Teil 2d — (optional) Zwei-Phasen Standup→Reposition→Walk
- [ ] 2d.1  Konzept/Engine Reposition (Tripod 3+3) + Tests + Sim→HW

- [ ] 2x  Self-Review pro Teil + Design-Log
```

---

## 5. Offene Punkte für User-Review (vor Code)
| # | Frage | Vorschlag |
|---|---|---|
| 5.1 | Body-Modell: nur Chassis-Box, oder + Coxa-Auswüchse? | **Erst Box** (einfach), Coxa-Box nur falls die HW-Kalibrierung (2a.7) es braucht |
| 5.2 | Marge `m` (Sicherheitsabstand zum Body) — Startwert? | z.B. **10 mm**, dann gegen Hand-Beobachtung feintunen |
| 5.3 | Check immer-an in `leg_ik` oder opt-in per Arg? | **Opt-in per Arg** (wie joint_limits) — Gait/Standup übergeben es, Unit-Tests bleiben lenient |
| 5.4 | Performance: Check pro Fuß pro Tick (50 Hz × 6) | Box+Segment = wenige Vergleiche → unkritisch; messen falls Zweifel |
| 5.5 | Tibia-Limit-Zielwert: volles Mechanik-Max (~+2.6) oder mit kleiner Marge (~+2.4)? | **+2.6** (Check sichert eh ab), oder +2.4 für Slope-Rundungs-Reserve |
| 5.6 | Walking omnidirektional vs vorwärts-optimiert (alt §7.5) | nach 2c-Envelope entscheiden |
| 5.7 | Zwei-Phasen (2d) jetzt oder später? | **später** — erst sehen ob das einfache Limit+Pose-Tuning reicht |

---

## 6. Cross-References
- Übergeordnet + Befund: [`phase_13_stage_1_walk_optimization_plan.md`](phase_13_stage_1_walk_optimization_plan.md) §4.2.0
- Präzedenz IKError-Muster: `leg_ik.py` (Stage 0.6 joint_limits-Check), gait_engine safety_freeze
- Body-Maße: `hexapod_physical_properties.xacro` · Transform: `reachability_viz._foot_base`
- Tibia-Cal-Kontext: `phase_13_stage_0_6_6_tibia_recal_plan.md`, `phase_13_stage_0_6_5_tibia_measure_test_commands.md`
- Tools: `walking_envelope_check.py`, `standup_envelope_check.py`
