# B3 — Weitere Gangarten (Wave / Tetrapod / Ripple) — detaillierter Sub-Stage-Plan

> **Status:** ⚪ Plan zur Freigabe (CLAUDE.md §4). Block-Kontext: [`B_lokomotion_kern.md`](B_lokomotion_kern.md) §B3.
> Architektur/Gates: [`../project_architecture/ai_navigation.md`](../project_architecture/ai_navigation.md) §„Neue Gangart".
> Test-Anleitung (nach Code final): `B3_gaits_test_commands.md`.

---

## 0. Ziel (1 Satz)

Drei zusätzliche statische Gangarten **Wave → Tetrapod → Ripple** (nacheinander) bereitstellen —
stabiler/last-ärmer als Tripod —, **rein als Daten-Einträge** (`GaitPattern` + `GAIT_PRESETS`),
**ohne Engine-Code-Änderung**, umschaltbar im STANDING via `gait_pattern`-Param. Tripod bleibt Default.

---

## 1. Logik-Skizze (reine Daten, kein Engine-Code)

Die Engine ist generisch: sie liest `phase_offset_per_leg` (wann schwingt Bein i) und `swing_duty`
(Anteil des Cycles im Swing). Eine Gangart = diese zwei Werte. Bein-Layout: 1=vorne-R, 2=mitte-R,
3=hinten-R, 4=hinten-L, 5=mitte-L, 6=vorne-L.

**Wave** (metachronal, **1 Bein** in der Luft, 5 tragen → last-ärmste):
```
swing_duty = 1/6
Reihenfolge 3→2→1→4→5→6 (rechts hinten→vorne, dann links hinten→vorne)
offsets = {3:0, 2:1/6, 1:2/6, 4:3/6, 5:4/6, 6:5/6}
→ max 1 Bein gleichzeitig in der Luft
```

**Tetrapod** (2 Beine/Phase, 3 Diagonal-Paare):
```
swing_duty = 1/3
Diagonal-Paare {1,4}, {2,5}, {3,6} mit offsets 0, 1/3, 2/3
offsets = {1:0, 4:0, 2:1/3, 5:1/3, 3:2/3, 6:2/3}
→ max 2 Beine (je ein diagonales Paar) gleichzeitig in der Luft
```

**Ripple** (überlappende Welle, 2 Beine in der Luft, kontralateral):
```
swing_duty = 1/3
Reihenfolge 3→4→2→5→1→6 (Seiten alternierend, hinten→vorne)
offsets = {3:0, 4:1/6, 2:2/6, 5:3/6, 1:4/6, 6:5/6}
→ max 2 Beine in der Luft, immer kontralateral (verschiedene Seiten)
```

**Folgen (automatisch, kein Code):** `linear_max = step_length_max / stance_duration` sinkt mit
kleinerem swing_duty (längere Stützphase): bei feet_closer (step_length_max 0.089, cycle 2.0) →
Tripod ~0.089, Tetrapod/Ripple ~0.067, Wave ~0.053 m/s. Gewollt (langsamer = stabiler/last-ärmer).

**Wertneutral / Pose orthogonal:** Pattern ändert NUR das Timing. Pose (radial/body_height) +
Stride (step_length_max/step_height/cycle_time) sind dieselben für alle Gangarten → **kein
Repositioning/Höhenwechsel beim Umschalten** (Füße stehen schon, nur künftige Schwünge ändern
Timing). Per-Gangart-Profile (eigene Pose/Stride + Reposition beim Wechsel) bewusst → **Block E3**.

**Dateien:** `hexapod_gait/gait_patterns.py` (3 neue `GaitPattern` + `GAIT_PRESETS`-Einträge);
`gait_node.py` nur den `gait_pattern`-`additional_constraints`-Hinweistext erweitern
(tripod | wave | tetrapod | ripple | single_leg_1..6). Keine Engine-Änderung, keine YAML, keine
Pose-Default-Änderung. `single_leg_*` bleiben unverändert.

---

## 2. Tests-Liste (+ Begründung, + was bewusst NICHT)

**Unit (`test/test_gait_patterns.py`, pytest, kein rclpy) — je Gangart:**
1. `offsets_valid` — alle 6 Beine haben Offset in [0,1) (kein `None`), swing_duty in (0,1)
   (deckt `GaitPattern.__post_init__` + Vollständigkeit ab).
2. `each_leg_swings_once` — jedes Bein schwingt genau einmal pro Cycle.
3. `max_legs_in_air` — über den ganzen Cycle gesampelt: Wave ≤1, Tetrapod ≤2, Ripple ≤2
   gleichzeitig in der Luft (Engine-Swing-Bedingung `(phi+offset)%1 < swing_duty` repliziert).
   **Statische Stabilität** — Kern-Kriterium jeder Gangart.
4. `air_legs_balanced` — die gleichzeitig schwingenden Beine sind „sicher":
   - Wave: immer ≤1 (trivially stabil).
   - Tetrapod: die 2 in der Luft sind genau ein Diagonal-Paar ({1,4}/{2,5}/{3,6}).
   - Ripple: die 2 in der Luft sind kontralateral (eins ∈ {1,2,3}, eins ∈ {4,5,6}).
5. `linear_max_plausible` — über eine Engine-Instanz mit dem Pattern: `linear_max` =
   `step_length_max / (cycle_time·(1−swing_duty))` (erwarteter Wert je Gangart).
6. `walk_in_limits` — Engine im WALKING mit dem Pattern + URDF-Limits, ein Cycle gesampelt →
   kein IKError (bestätigt: Pattern läuft mit der feet_closer-Pose limit-konform).
7. `registered_in_presets` — `'wave'`/`'tetrapod'`/`'ripple'` ∈ `GAIT_PRESETS`, Name == Key.

**Regression/Lint (B3-…):** alle bestehenden Tests + `ament_flake8`/`ament_pep257` grün.

**Bewusst NICHT getestet (scope-out):**
- **Foot-Envelope je Gangart** — die *Foot-Trajektorie pro Bein* (Swing-Apex/Radial) ist
  **pattern-unabhängig** (nur das Timing zwischen den Beinen ändert sich) → `walking_envelope_check`
  liefert für alle Gangarten dasselbe Ergebnis wie Tripod. Wird je Gangart einmal als Sanity
  gefahren, ist aber kein erwarteter Unterschied (in der Test-Doc vermerkt).
- **Dynamisches Kippen / Schlupf unter Last** — quasi-statisches Modell; echtes Verhalten = HW.
- **Hitze-/Last-Vergleich quantitativ** — HW-Beobachtung via `torque_viz` (B3.6), kein Unit-Test.
- **CoG-Marge je Phase (joint_load)** — by-construction stabil (≥4 tragende Beine, balanciert);
  formaler CoG-Check ist B4-Thema. Hier optional, nicht Done-Kriterium.

---

## 3. Progress-Checkliste (Done-Vertrag, 1:1 nach `B_lokomotion_kern.md` §B3)

```
> Reihenfolge: erst Wave, dann Tetrapod, dann Ripple. Je Gangart die VOLLE Kette einzeln:
> Code → Unit-Tests → Lint → SIM → HW (aufgebockt → Boden), DANN erst die nächste Gangart.
- [ ] B3.1  Wave  — Pattern (3,2,1,4,5,6 + swing_duty 1/6) + GAIT_PRESETS; Tests+Lint; SIM; HW
- [ ] B3.2  Tetrapod — Pattern (1/3, Diagonal {1,4}{2,5}{3,6}); Tests+Lint; SIM; HW
- [ ] B3.3  Ripple — Pattern (3,4,2,5,1,6, 1/3, überlappend); Tests+Lint; SIM; HW
- [ ] B3.4  Unit-Tests je Pattern: max-Beine-in-Luft, linear_max plausibel, Offsets gültig, balanced
- [ ] B3.5  Gangart-Wechsel im Stand (gait_pattern ist standing_only) sauber; Hinweistext erweitert
- [ ] B3.6  Je Gangart Hitze-/Stabilitäts-Beobachtung (torque_viz) beim HW-Test aus B3.1–B3.3
- [ ] B3.7  Self-Review + Test-Markdown (je Gangart Befund festhalten)
```

> **Umsetzungs-Rhythmus (User 2026-06-03):** jede Gangart die **volle Kette einzeln** —
> B3.1 Wave (Code+Tests+Lint → du: SIM → du: HW) → erst dann B3.2 Tetrapod (gleiche Kette) →
> dann B3.3 Ripple. B3.4 wächst mit (Tests je Pattern), B3.6 ist die HW-Beobachtung innerhalb
> jeder Gangart-Kette. So ist jede Gangart komplett verifiziert (inkl. HW), bevor die nächste kommt.

---

## 4. Offene Punkte / Entscheidungen (User-Freigabe 2026-06-03)

- ✅ **Wave-Reihenfolge:** 3,2,1,4,5,6 (rechts hinten→vorne, dann links). Erledigt.
- ✅ **Tetrapod-Paare:** Diagonal {1,4},{2,5},{3,6}. Erledigt.
- ✅ **Ripple-Reihenfolge:** 3,4,2,5,1,6 (kontralateral-alternierend). Erledigt.
- ✅ **Scope:** nur Patterns, gleiche Walk-Pose/Regler für alle; per-Gangart-Profile (eigene
  Pose/Stride + Reposition beim Wechsel) → **Block E3** vorgemerkt. Erledigt.
- ✅ **Namen/Keys:** `wave`, `tetrapod`, `ripple`; `single_leg_*` bleiben. Default `tripod`. Erledigt.
- ⏳ **Wave-Vortriebs-Gleichmäßigkeit:** Reihenfolge ist stabil (1 Bein); ob 3,2,1,4,5,6 *flüssig*
  genug aussieht oder eine alternative Ordnung angenehmer ist → in Sim (B3.1) final beurteilen.
