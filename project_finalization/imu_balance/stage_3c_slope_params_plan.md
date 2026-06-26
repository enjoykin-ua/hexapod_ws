# Stufe 3c — Hang-Parameter-Adaption (Weg A) + Auto-Gait-Switch

> Sub-Stufe von [Stufe 3](stage_3_walking_slope_plan.md) (Block A5). **Ziel:** den
> Roboter **steilere Hänge hochlaufen** lassen, indem Walk-Parameter an den Hangwinkel
> θ angepasst werden (Weg-A-Fundament). Löst den in **3a** beobachteten **Kletter-Deckel
> ~12°** (fixe Params → Vortrieb/CoG-Stall).
>
> **Status: ⚪ offen. §4-Entscheidungen GELOCKT (s. §5).** Geschnitten in **3c-1 → 3c-2 →
> 3c-3**, jede mit eigenem §4-Mini-Review (Logik/Tests/Checkliste bestätigen) → Freigabe →
> Code → Test → Self-Review. Voraussetzung: 3a (🟢). Umbrella-Detail:
> [stage_3_walking_slope_plan.md](stage_3_walking_slope_plan.md) §1.C/§4/§5.

---

## 0. Zuschnitt (3 Teil-Stufen)

| Teil | Inhalt | Kern-Deliverable |
|---|---|---|
| **3c-1** | Offline-θ→Param-**Tabelle** + Online-Eval; `body_height`/`radial`/`step` adaptiv + **hang-bewusste Schwunghöhe** | YAML-Tabelle + gait_node liest IMU-θ → setzt Params rate-limitiert; Klettern > 12° |
| **3c-2** | **Auto-Gangart-Switch** (Tripod→Wave, Hysterese) + **Setpoint-Blend α·θ** | steilere Hänge stabiler + mehr Beinrange |
| **3c-3** | **Offline-Batch** (20 linear + 20 wechselnd) + **A/B-Entscheidung** (mit Daten) + **Torque-Report** | dokumentierte Hülle + Weg-A bestätigt + HW-Realitäts-Check |

---

## 1. Logik-Skizze

### 3c-1 — θ→Param-Tabelle + Online-Eval

- **Offline-Tool** `tools/slope_param_table.py` (Muster: `walking_envelope_check.py` +
  `leveling_envelope_check.py`): sweept θ (z.B. −30…+30° in 2° Schritten, **signiert** —
  uphill +, downhill −). Pro θ sucht es den **envelope-grünen + CoG-stabilen** Parametersatz
  `(body_height, radial, step_length, step_height)` mit dem **meisten Vortrieb/Kletter-
  Reserve**. Validierung = **echte URDF-Limits** (`load_joint_limits`) + CoG
  (`joint_load.compute_load`). **Downhill: konservativere CoG-Marge** (CoG kippt nach vorn).
  Output: **YAML-Tabelle** `θ → params` (+ Max-θ je Richtung).
- **Online (gait_node):** IMU-θ aus roll/pitch (Bergab-Richtung aus der Projektion, kein
  yaw). θ→params **bei θ-Änderung (Totband ~2–3°) auswerten + cachen**, lineare
  Interpolation zwischen Tabellenpunkten. Engine-Params **rate-limitiert** setzen (kontinuierl.
  Eingänge in WALKING, NICHT der diskrete `STATE_STANCE_SWITCH`), **Envelope-Clamp je
  Zwischen-Tick**. Feed-Forward (Tabelle) + Closed-Loop (IMU-Residuum) — Tabelle = Vorsteuerung.
- **Hang-bewusste Schwunghöhe:** Apex-Clearance **+= (Vorwärts-Schrittanteil)·tan(θ)** bergauf
  (Boden steigt vor dem Fuß an → mehr Anheben). Im `swing_traj` / Engine. NICHT `step_height`
  global senken (Schürf-Gefahr; 3a-Befund).

### 3c-2 — Auto-Gait-Switch + Setpoint-Blend

- **Gangart-Switch:** θ < `gait_switch_deg` (Param, ~15°) → **Tripod**; darüber → **Wave**
  (5 Füße unten, statisch stabiler). **Hysterese** (z.B. ±2°) gegen Flattern an der Schwelle.
  Reuse B3 `gait_pattern`. Switch nur an einem sicheren Punkt (z.B. alle Füße unten).
- **Setpoint-Blend α·θ:** Leveling-Soll = **α·θ** statt 0 (α∈[0,1]: 0=horizontal wie 3a,
  1=hangparallel). α als Param (Default **0**); das Offline-Tool findet **α(θ)**, das die
  Kletter-Range maximiert (Beinrange ↔ CoG-Marge). Greift im `BalanceController`-Setpoint.

### 3c-3 — Offline-Batch + A/B + Torque-Report

- **Offline-Batch:** 20 lineare + 20 wechselnde Hänge → Planer liefert in-limit + CoG-stabile
  Params über θ; Max-θ je Richtung. pytest/Skript, viele Fälle billig.
- **A/B-Entscheidung (mit Daten):** bestätigen, dass **Weg A** (Tabelle + Online-Eval) die
  glatten Zielhänge schafft. **B (Online-Replan + Fußkontakte) → Stufe 4** (unebenes Terrain).
  Ergebnis dokumentieren.
- **Torque-Report (informativ, KEIN Gate):** das Offline-Tool meldet je θ den **Peak-Joint-
  Torque** (`joint_load.leg_joint_torques`, Block-A1-Modell) → Zahl zum Gegenchecken gegen
  Servo-Spec + Hitze. Gate bleibt Kinematik + CoG (User-Entscheid: Servos voraussichtlich
  stark genug, evtl. wärmer).

## 2. Tests

- **Unit:** θ→params-Lookup/Interpolation, Rate-Limiter, Gait-Switch-Hysterese, Setpoint-Blend.
- **Offline-Batch (3c-3):** 20 linear + 20 wechselnd grün (in-limit + CoG-stabil je θ).
- **Sim (User):** Rampe **>12° hochlaufen** mit adaptierten Params; wechselnder Hang (Params
  folgen θ stetig, kein Sprung/Freeze am Knick); Auto-Switch greift; Setpoint-Blend zeigt
  mehr Kletter-Range. Ramp-Welt aus 3a (`ramp.sdf.xacro`) wiederverwenden/erweitern.
- **HW:** deferiert.

## 3. Progress-Checklisten (je Teil-Stufe ins Progress-File)

```
3c-1:
- [ ] 3c1.1 Offline-Tool tools/slope_param_table.py (θ-Sweep signiert, URDF-Limits + CoG) → YAML-Tabelle
- [ ] 3c1.2 Hang-bewusste Schwunghöhe (Apex += step_fwd·tan(θ) bergauf) in Engine + Tests
- [ ] 3c1.3 gait_node: θ→params online (Totband+cache, lineare Interp, rate-limitiert, Envelope-Clamp je Tick) + Params
- [ ] 3c1.4 Unit-Tests (Lookup/Interp/Rate-Limiter) + colcon/Lint
- [ ] 3c1.5 Sim-Verify Klettern >12° + Self-Review
3c-2:
- [ ] 3c2.1 Auto-Gait-Switch Tripod→Wave (gait_switch_deg + Hysterese, sicherer Switch-Punkt)
- [ ] 3c2.2 Setpoint-Blend α·θ im BalanceController (Param, Default 0) + Tool findet α(θ)
- [ ] 3c2.3 Unit-Tests + colcon/Lint + Sim-Verify + Self-Review
3c-3:
- [ ] 3c3.1 Offline-Batch 20 linear + 20 wechselnd
- [ ] 3c3.2 Torque-Report je θ (joint_load, informativ)
- [ ] 3c3.3 A/B/Hybrid-Entscheidung dokumentiert (mit Daten)
- [ ] 3c3.4 README/Konzept + colcon/Lint + Self-Review
```

## 4. Offene Punkte (je Teil-Stufe vorm Code kurz bestätigen)

- **3c-1:** Tabellen-Schrittweite (2°?) + Param-Slew-Raten (Startwerte) + Totband (2–3°?).
- **3c-2:** `gait_switch_deg` (~15°?) + Hysterese + α(θ)-Form (linear ab θ_α? gedeckelt?).
- **3c-3:** Batch-Winkel-Set + Akzeptanz der Weg-A-Bestätigung.
- Sonst: Startwerte auf der Rampe tunen (alle live).

## 5. Design-Entscheidungen (GELOCKT im §4-Review)

| Entscheidung | Gewählt | Warum |
|---|---|---|
| θ→param-Repräsentation | **YAML-Tabelle (~2° Schritte) + lineare Interp** | inspektierbar, nie außerhalb bewiesener Punkte; Tool in tools/ |
| Uphill/Downhill | **signiertes θ; bergab konservativere CoG-Marge** | CoG-nach-vorn-Gefahr bergab |
| Schwunghöhe am Hang | **Apex += step_fwd·tan(θ) bergauf** | Schürffrei ohne step_height global zu senken (3a-Befund) |
| Param-Wechsel im Lauf | **rate-limitiert kontinuierlich + Envelope-Clamp je Tick** | flüssig, kein Stopp; kein STANCE_SWITCH |
| Setpoint | **Blend α·θ, Default α=0, offline α(θ) getunt** | Beinrange ↔ CoG; echter Kletter-Hebel |
| Gangart-Switch | **Tripod→Wave + Hysterese** | Wave am Steilhang statisch stabilster; einfachste robuste Wahl |
| A/B | **Weg A (Tabelle+Online-Eval); B → Stufe 4** | glatte Hänge brauchen kein B; B = Fußkontakte/Terrain |
| HW-Torque | **Gate = Kinematik+CoG; Torque nur informativ (joint_load)** | Servos vermutlich stark genug (User); Zahl gratis zum Gegencheck |
| Echtzeit | **θ-Eval bei Änderung + cachen** | Lookup µs, kein 50-Hz-Budget-Problem |
