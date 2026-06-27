# Stufe 3c-1 — θ→Param-Tabelle + hang-bewusste Schwunghöhe + Online-Eval

> # ❌ VERWORFEN (2026-06-27)
> Dieser Ansatz (Klettern via Voll-Leveling + θ-Geometrie-Tabelle) wurde nach dem Sim-Test
> verworfen — sieht sprawlig aus, Plateau-Reset-Bug, Trippeln. **Nachfolge: Terrain-Following**
> ([Plan](../stage_3_terrain_following_plan.md), [Retro/Begründung](../terrain_following_pivot_retro.md)).
> Code wurde zurückgesetzt (Git-History). Dieses Dokument bleibt nur als **Referenz** des
> verworfenen Wegs.

> Erste Teil-Stufe von [3c](stage_3c_slope_params_plan.md) (Block A5). **Ziel:** den in
> 3a beobachteten **Kletter-Deckel ~12°** lösen, indem die Walk-Geometrie (body_height /
> radial / step_length / step_height-Boost) **kontinuierlich an den Hangwinkel θ** angepasst
> wird — offline bewiesene Param-Hülle (Weg A), online ausgewertet + rate-limitiert.
>
> **Status: ⚪ offen — Plan finalisiert, wartet auf User-Freigabe.** §4-Entscheidungen
> (Umbrella §5) + die 3c-1-Detailpunkte unten sind im Klärungs-Round mit dem User GELOCKT.
> Implementierung erst nach Freigabe (User liest → committet → gibt frei).

---

## 0. Geklärte Entscheidungen (Klärungs-Round, GELOCKT)

| # | Punkt | Entscheidung |
|---|---|---|
| 1 | Online-Pfad bypasst STANDING-only-Gate | θ→Param schreibt Engine-Attribute **direkt mit eigenem Slew** (nicht über `_apply_param`); Slope-Adapt ist eigener Opt-in-Schalter `slope_adapt_enable`. Bei aktivem Schalter **übernimmt die Tabelle** body_height/radial/step_length → manuelle Stance-Switch-Cycles werden geblockt. |
| 2 | Tool-Suchraum | **3-D-Gitter** (body_height × radial × step_length), **step_height optional nur nach OBEN** (≥ Basis, Schürf-TABU). Tool **dumpt die volle grüne Menge** je θ in eine Datei → **separates Kurations-Skript** liest den Dump und erzeugt die YAML (der rohe Dump kommt **nie** in den Agent-Kontext). |
| 3 | θ-Sweep | **−35°…+35° in 1°-Schritten**, YAML **auto-truncated bei Max-θ je Richtung**. |
| 4 | Apex-Boost | **Per-Bein-Gradient (voll)**: `boost = max(0, fwd·tan θ)`, fwd = Projektion des Bein-Schrittvektors auf die Bergauf-Richtung; bergab kein Absenken. |
| 5a | Präzedenz | Slope-Adapt aktiv → Tabelle gewinnt, manuelle Stance-Modi blockiert. |
| 5b | θ-Richtung | **Volle Magnitude + Richtung** (Seit-/Diagonal-Lauf am Hang) — dieselbe Hang-Definition wie der Apex-Boost. |
| 5c | Downhill | 3c-1 = nur **konservative CoG-Marge** (größeres min_margin für θ<0). Echte Bergab-Robustheit (Fuß erreicht Boden nicht → „in der Luft stehen") braucht **Fußtaster = Stufe 4**. |
| 5d | Speed am Hang | step_length sinkt am Steilhang → **automatisch langsamer** (ok für v1); spätere Option „nicht drosseln" offen gehalten. |
| 5e | Slew-Startwerte | body_height ~0.02 m/s, radial ~0.02 m/s, step_length ~0.03 m/s (alle live-tunbar). |
| 5f | Setpoint | bleibt **horizontal (α=0)** in 3c-1; α·θ-Blend erst 3c-2. |
| θ-Totband | Cache-Schwelle | **2.5°** — *nicht* Nachregel-Trigger fürs Leveling (das hat sein eigenes 1.5°-Totband), sondern: erst wenn θ-Schätzung um >2.5° vom gecachten Wert wegläuft, Tabelle neu nachschlagen. |

---

## 1. Logik-Skizze / Pseudocode

### 1.1 Offline-Tool `tools/slope_param_table.py` (zwei Subcommands)

Muster: `leveling_envelope_check.py` (rohe Foot-Rotation, **nicht** `compute_joint_angles` —
dessen IKError-Fallback würde Limit-Verletzungen maskieren) + `walking_envelope_check.py`
(`load_joint_limits` via xacro, GaitEngine-Cycle, `compute_load` für CoG).

**Subcommand `sweep` (die schwere Gittersuche → Dump):**
```
für θ in range(-35, +35, 1°):                      # signiert, uphill +, downhill −
    corr = leveling-Soll bei θ (α=0 → Body horizontal); Hang-Richtung aus θ-Vorzeichen/Achse
    für bh in body_height-Gitter (z.B. -0.060..-0.110 @ 2.5mm):
      für rad in radial-Gitter (z.B. 0.12..0.21 @ 5mm):
        für sh in step_height-Liste (Default nur Basis; optional ≥ Basis):
          step_len = binär-Suche max step_length, das den GELEVELTEN Walking-Cycle
                     envelope-grün (URDF-Limits, rohe Rotation, alle Schwung-/Stütz-Phasen)
                     hält — inkl. Apex-Boost(θ) (sonst überschätzt man die Clearance).
          falls step_len > 0:
            load = compute_load(statische gelevelte Pose)         # CoG, flat-leveled-Annahme
            margin_ok = load.stable and margin >= min_margin(θ)   # downhill (θ<0) strenger
            torque_peak = max joint-torque (joint_load, informativ — kein Gate)
            falls margin_ok: dump-Zeile (θ, bh, rad, sh, step_len, margin, torque_peak)
schreibe ALLE grünen Zeilen → tools/_out/slope_param_sweep.csv   (potenziell groß, intermediate)
```
- **min_margin(θ):** uphill (θ≥0) z.B. 5 mm, downhill (θ<0) z.B. 15 mm (konservativer, CoG kippt nach vorn; Punkt 5c).
- **CoG-Modell:** `compute_load` wie `leveling_envelope_check` — bei *gelevelter* Pose ist der Body horizontal → base-Z ≈ Schwerkraft, Annahme exakt.
- **Torque:** `joint_load.leg_joint_torques` (Block-A1-Modell) je Zeile — nur als Spalte, **kein** Filter (Gate = Kinematik+CoG; Detail 3c-3).

**Subcommand `curate` (separates Auswerten → YAML):**
```
lies slope_param_sweep.csv
für jedes θ: Kandidaten-Zeilen = alle grünen
Auswahl-Politik:  maximiere step_length (Vortrieb) unter margin ≥ min_margin(θ)
                  Tie-Break: tiefere body_height (CoG/Torque-Reserve)
GLATTHEIT ERZWINGEN (kritisch für Online-Interpolation):
  - body_height monoton fallend mit |θ|, radial monoton, step_length monoton fallend mit |θ|
  - Ausreißer glätten / auf die monotone Hülle zwingen (sonst springt die Tabelle →
    Online-Interpolation zwischen Zeilen fährt durch unbewiesene Zwischen-Sätze)
truncate bei Max-θ je Richtung (erste θ-Stufe ohne grüne Zeile)
schreibe config/slope_params.yaml  (θ → {body_height, radial, step_length, step_height})
drucke KOMPAKTE Zusammenfassung (je θ die gewählte Zeile + Max-θ) — NICHT den rohen Dump
```
- **YAML** (`src/hexapod_gait/config/slope_params.yaml`) wird **committed** (der bewiesene Artefakt); der rohe CSV-Dump ist intermediate (nicht committed).
- **Warum Dump→Kuration getrennt:** die „beste"-Wahl bei mehreren freien Params ist eine *Politik*, kein eindeutiges Optimum. Getrennt = Politik explizit + inspizierbar, und der große Dump bleibt aus dem Agent-Kontext (User-Wunsch).

### 1.2 Hang-bewusste Schwunghöhe (Engine + `swing_traj`)

- `swing_traj` bekommt optionalen Param `apex_boost` (m, Default 0):
  `z = body_height + (step_height + apex_boost)·sin(π·phase)` — Boost skaliert dieselbe
  Sinus-Hülle → **0 bei Touchdown/Start** (glatt, `sin'(0)=sin'(π)=0`), Peak am Apex.
- Engine hält einen **Hang-Gradienten** `g_body` (Bergauf-Einheitsvektor × tan θ, Body-Frame),
  gesetzt vom Node via neue Methode `set_slope_gradient(gx, gy)`; Default (0,0) → boost 0 →
  **bit-identisch zum heutigen Verhalten** (regressionssicher).
- Pro Schwung-Bein in `_compute_walking_targets`/`_compute_stopping_targets`:
  `g_leg = rotate_z(-mount_yaw, g_body)`; `fwd = step_vec_leg · g_leg`;
  `apex_boost = max(0, fwd)` (Einheit m, da `step_vec` in m und `g_body` = tan θ dimensionslos).
  `max(0,…)` = bergab kein Absenken.
- **Komposition mit Leveling:** Boost wirkt im Bein-Frame **vor** der Leveling-Rotation
  (`_leveled_ik_at`) — beide überlagern sich sauber (erst mehr Clearance, dann rotieren).

### 1.3 Online-Auswertung (`gait_node`)

Neue Methode `_update_slope_adapt()`, im Tick **vor** `_update_leveling()` aufgerufen
(θ-Schätzung braucht die im *vorigen* Tick angewandte Leveling-Korrektur — siehe unten).

```
falls not slope_adapt_enable or imu is None or state not in WALKING-ish:
    # kein Override — Engine-Params bleiben auf ihren manuellen Werten; Gradient 0
    engine.set_slope_gradient(0,0); reset Slope-Cache; return

# θ-SCHÄTZUNG (kritisch): IMU misst bei aktivem Leveling nur die REST-Neigung.
# Echter Hang = Rest-Neigung + bereits angewandte Leveling-Korrektur.
tilt_vec   = (imu_roll, imu_pitch)
corr_vec   = engine.applied_leveling_corr          # (_level_roll,_level_pitch), 0 wenn Leveling aus
slope_vec  = tilt_vec + corr_vec                   # Vorzeichen via Round-Trip-Logik gepinnt
θ          = |slope_vec|  (signiert nach Bergab-Richtung); Bergauf-Einheitsvektor = -slope_vec/|.|

# TOTBAND + CACHE
falls |θ - θ_cached| > 2.5°:
    θ_cached = θ
    target = interp_table(slope_params.yaml, θ)    # lineare Interp zwischen 2 Zeilen;
                                                   # jenseits Max-θ → letzte grüne Zeile (clamp)

# RATE-LIMIT (synchron!) — alle Params mit demselben fraktionalen Fortschritt Richtung target,
# damit Zwischenzustände auf der Strecke zwischen zwei bewiesenen Tabellen-Zeilen liegen
# (Envelope-Clamp je Tick = Backstop, kein Freeze durch transiente Achsen-Mischung).
engine.body_height   = slew(engine.body_height,   target.body_height,   bh_slew·dt)
engine.radial_distance = slew(engine.radial_distance, target.radial,    rad_slew·dt)
engine.step_length_max = slew(engine.step_length_max, target.step_length, sl_slew·dt)
engine.step_height   = slew(engine.step_height,   target.step_height,   sh_slew·dt)

# Hang-Gradient für den Apex-Boost
engine.set_slope_gradient(*(-slope_unit · tan θ))
```
- **Envelope-Clamp je Tick:** die Engine-IK clampt ohnehin gegen URDF-Limits
  (`compute_joint_angles` → IKError). Synchroner Slew + glatte/monotone Tabelle hält die
  Zwischenzustände grün; die IK-Limit-Prüfung ist der Backstop.
- **`step_length_max`-Adaption ↔ Speed:** kleineres step_length am Steilhang ⇒ kleineres
  `linear_max` ⇒ Engine klemmt cmd_vel ⇒ automatisch langsamer (Punkt 5d).
- **Präzedenz:** `_cycle_stance` (L2/R2) bei aktivem Slope-Adapt früh mit WARN abbrechen (5a).

### 1.4 Engine-Erweiterung

- `set_slope_gradient(gx, gy)` + Feld `_slope_g = (gx, gy)` (Default 0,0).
- `applied_leveling_corr` Property → `(_level_roll, _level_pitch)` (für θ-Schätzung im Node).
- `_compute_walking_targets`/`_compute_stopping_targets`: Apex-Boost je Schwung-Bein (1.2).

---

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Engine: Apex-Boost** | `swing_traj` mit `apex_boost>0` hebt Apex, Touchdown/Start unverändert (z=body_height) | Unit: z(0)=z(1)=body_height, z(0.5)=body_height+step_height+boost |
| **Engine: Per-Bein-Gradient** | Bergauf (g_body≠0) → Vorder-/Bergauf-Beine kriegen boost>0, Bergab-Anteil → boost=0 (`max(0,·)`) | Unit: dot-Projektion korrekt je mount_yaw |
| **Engine: Gradient 0 = Regression** | `set_slope_gradient(0,0)` → bit-identisch zu heute | Unit: Targets == ohne Boost |
| **Tabelle: Lookup/Interp** | lineare Interpolation zwischen zwei θ-Zeilen; Clamp jenseits Max-θ | Unit: bekannte Stützpunkte + Mittelwert + Rand |
| **Slew/Rate-Limiter** | synchroner Slew, kein Sprung; erreicht target | Unit: monotone Annäherung, |Δ|≤rate·dt |
| **θ-Schätzung** | `slope = tilt + corr`; Vorzeichen/Richtung | Unit: corr=0 → slope=tilt; corr≠0 rekonstruiert Hang |
| **Tool sweep (klein)** | Mini-Sweep (wenige θ) liefert nur envelope+CoG-grüne Zeilen, rohe Rotation (kein Fallback) | pytest: bekannte θ grün/rot |
| **Tool curate** | Auswahl-Politik + Monotonie-Erzwingung + Truncate; YAML-Form | pytest: springende Eingabe → monotone Ausgabe |
| **Node-Smoke** | `slope_adapt_enable` Param + `_update_slope_adapt` läuft, blockt Stance-Cycle | rclpy-Smoke + Unit |
| colcon + Lint | flake8/pep257 grün, alle bestehenden Tests grün | 620 + neue, 0 Fehler |
| **Sim (User)** | Rampe **>12° hochlaufen** mit Adaption; wechselnder Hang (Params folgen θ stetig, kein Sprung/Freeze am Knick); θ-Schätzung trackt echten Hang (mit Leveling an) | qualitativ + `/imu/monitor` |

**Bewusst NICHT getestet (deferred):**
- Bergab „Fuß erreicht Boden nicht / in der Luft" → braucht Fußtaster = **Stufe 4** (Punkt 5c).
- Auto-Gait-Switch Tripod→Wave + Setpoint-Blend α·θ → **3c-2**.
- Offline-Batch (20 lin + 20 wechselnd) + A/B + Torque-Report → **3c-3**.
- Servo-Torque als Gate (HW) — Torque hier nur informative Spalte.
- Dynamik/Schlupf/Reibungsgrenze → Gazebo/HW.

---

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
3c-1:
- [ ] 3c1.1 Engine: swing_traj apex_boost + set_slope_gradient + applied_leveling_corr + Per-Bein-Boost in _compute_walking/_stopping_targets (Gradient 0 = Regression)
- [ ] 3c1.2 Engine-Unit-Tests (Apex-Boost, Per-Bein-Gradient, Regression Gradient 0)
- [ ] 3c1.3 Offline-Tool tools/slope_param_table.py — Subcommand `sweep` (3-D-Gitter, signierter θ-Sweep ±35°/1°, rohe Rotation + URDF-Limits + CoG min_margin(θ) + Apex-Boost(θ), Torque-Spalte) → CSV-Dump
- [ ] 3c1.4 Tool Subcommand `curate` (liest Dump, Politik max-step_length + Monotonie-Erzwingung + Truncate Max-θ) → config/slope_params.yaml + kompakte Summary
- [ ] 3c1.5 Tool-Unit-Tests (sweep klein grün/rot, curate Monotonie+Truncate) + slope_params.yaml erzeugt
- [ ] 3c1.6 gait_node: _update_slope_adapt (θ=tilt+corr-Schätzung, Totband 2.5°+cache, lineare Interp, synchroner Slew, set_slope_gradient) + Params (slope_adapt_enable, slope_param_file, slope_deadband_deg, *_slew) + Tabellen-Loader
- [ ] 3c1.7 Präzedenz: _cycle_stance bei aktivem slope_adapt blocken (WARN)
- [ ] 3c1.8 Node-Unit-Tests (Tabellen-Interp/Clamp, Slew, θ-Schätzung, Stance-Block) + rclpy-Smoke
- [ ] 3c1.9 colcon test + Lint grün (alle bestehenden + neue)
- [ ] 3c1.10 README/Konzept-Update (hexapod_gait: Slope-Adapt-Pfad, θ-Schätzung, Tool sweep/curate, Apex-Boost)
- [ ] 3c1.11 Test-Doku stage_3c_1_test_commands.md (Rampe >12°, wechselnder Hang) + Sim-Verify durch User
- [ ] 3c1.12 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

---

## 4. Offene Punkte für User-Review (vor Code)

- **θ-Schätzung `slope = tilt + corr`** — die wichtigste neue Annahme. In Sim verifizieren,
  dass die Schätzung den *echten* Hang trackt, auch wenn Leveling aktiv ist (sonst sieht die
  Tabelle den Hang nie). Falls die Schätzung zappelt: leichtes Tiefpass auf θ erwägen.
- **Gitter-Auflösung** (body_height 2.5 mm? radial 5 mm?) vs. Rechenzeit (Größenordnung Minuten).
  Startwerte oben; bei zu langsam vergröbern, bei zu grob verfeinern — reines Offline-Tuning.
- **min_margin uphill/downhill** (5 / 15 mm) — Startwerte; auf der Rampe/in Gazebo nachziehen.
- **Synchroner Slew als Envelope-Garant** — reicht „monotone Tabelle + synchroner Slew + IK-Clamp",
  oder soll der Slope-Slew bei IKError (wie Leveling) **skalieren statt freezen**? (v1: IK-Clamp
  als Backstop; Skalieren nur falls Sim Freezes zeigt.)
- **step_height-nach-oben** als optionale Gitter-Achse — in 3c-1 Default aus (nur Basis +
  Apex-Boost); aktivieren falls die Hülle es braucht.

---

## 5. Design-Entscheidungen (mit verworfenen Alternativen)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Tool-Suchraum | 3-D-Gitter (bh×rad×step_len), step_height nur ≥Basis | (a) nur bh+step_len (zu eng, lässt radial-Reserve liegen); (b) volle 4-D inkl. step_height-Senkung | radial ist echter Kletter-Hebel (Stützbreite↔Reichweite); step_height senken = Schürf-TABU |
| Tabellen-Erzeugung | Dump (volle grüne Menge) → separates `curate` → YAML | direkt in einem Lauf die „beste" Zeile picken | Politik explizit+inspizierbar; roher Dump bleibt aus dem Agent-Kontext (User) |
| **Auswahl-Politik (User-Entscheid)** | **Option A `--anchor-nominal`**: θ=0 = Nominal-Stance, step ≤ Nominal, body/radial ≤ Nominal + nur am Hang nach Bedarf | max-Vortrieb (committet die θ=0-Zeile aggressiv: −0.060/0.170/0.13) | flach = unverändert (Umbrella §1.C „θ=0 = Stance-Modi"); slope_adapt = reiner Hang-Hebel. **Preis:** Voll-Leveling (α=0) envelope-teuer → Range nur ~±8° (max-Vortrieb käme ±20°). Upgrade auf Option B = reiner Tabellen-Tausch (`slope_param_file` live), kein Code |
| Glattheit | Monotonie über θ im `curate` erzwungen | unabhängiges Per-θ-Optimum | springende Tabelle ⇒ Online-Interpolation fährt durch unbewiesene Sätze |
| θ-Schätzung | `slope = IMU-tilt + angewandte Leveling-corr` | nur IMU-tilt | gelevelter Körper liest sonst ~0 statt Hang |
| Apex-Boost | `max(0, fwd·tan θ)` per Bein, skaliert Sinus-Hülle | step_height global senken (3a-Versuchung) | Schürffrei bergauf, glatter Touchdown, bergab keine Reduktion |
| Param-Wechsel im Lauf | direkte Engine-Attribute + synchroner Slew, STANDING-Gate bypassed | über `_apply_param` (standing_only blockt WALKING) | Adaption MUSS im Lauf wirken; eigener Slew = Sicherheit statt Gate |
| Präzedenz | Slope-Adapt > manuelle Stance-Modi (blockiert) | beide gleichzeitig / Stance als θ=0-Basis | ein Höhen-Herr im Lauf, sonst Konflikt |
| Setpoint | α=0 (horizontal) | α·θ-Blend | Blend = 3c-2-Hebel, hält 3c-1 fokussiert |
| Downhill | nur konservative CoG-Marge | volle Bergab-Lokomotion | „Fuß-in-der-Luft" braucht Fußtaster = Stufe 4 |
