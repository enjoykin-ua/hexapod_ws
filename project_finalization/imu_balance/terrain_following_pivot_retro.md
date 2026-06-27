# A5 Richtungswechsel — Voll-Leveling fürs Klettern → Terrain-Following (Retro)

> **Was hier steht:** warum der bisherige „Klettern via Körper-Leveling + θ-Geometrie-
> Tabelle"-Ansatz (Stufe 3c-1) nach dem Sim-Test **verworfen** wurde und wir auf
> **Terrain-Following** umgestiegen sind. Der neue Plan: [`terrain_following_plan.md`](stage_3_terrain_following_plan.md).
> Stand: 2026-06-27.

---

## Was probiert wurde (Stufe 3c-1, gebaut + Sim-getestet)

Ziel war, den in 3a beobachteten Kletter-Deckel (~12° mit fixen Params) zu lösen, indem
der **Körper am Hang waagerecht gelevelt** wird und die Walk-Geometrie via einer offline
bewiesenen **θ→Param-Tabelle** (body_height/radial/step_length) mitgeführt wird. Gebaut:

- **Apex-Boost** (hang-bewusste Schwunghöhe) in `swing_traj`/`gait_engine`.
- **Offline-Tool** `tools/slope_param_table.py` (`sweep`/`curate`) → `config/slope_params.yaml`.
- **`SlopeTable`** (ROS-frei) + `gait_node._update_slope_adapt` (θ=tilt+corr, Totband, Slew).
- Tabelle im **`--anchor-nominal`-Modus** (Option A): θ=0 = Nominal-Stance, step nie über
  Nominal, body/radial nur am Hang nach Bedarf. Voll-gelevelt ~±8° Range.

Alles war Sim-getestet, Tests grün (gait 282 + kinematics 43 + 16 Tool).

## Was der Sim-Test zeigte (warum verworfen)

Beim Hochlaufen einer 8°-Rampe mit Voll-Leveling:

1. **Sieht unnatürlich/sprawlig aus.** Um den Körper *exakt waagerecht* (Wasserwaage) gegen
   den Hang zu halten, muss die Tabelle die Beine **breit spreizen** (radial ~0.19) und den
   Körper **tief legen** (~−0.11). Der User-Befund: **„Körper waagerecht zur Wasserwaage =
   unschön; Körper parallel zur Steigung = natürlich."**
2. **Plateau-Reset-Bug.** Auf dem Plateau oben stellte sich der Roboter **nicht** auf den
   Ursprungs-Stand zurück — er blieb in der Hang-Geometrie. Ursache: der Leveling-
   Integrator hält im Totband die Korrektur fest → die θ-Schätzung (tilt+corr) sieht den
   Hang weiter → Geometrie bleibt hängen.
3. **Trippeln.** step_length schrumpft mit dem Hang → der Roboter wird sehr langsam; der
   User wollte eher normale/längere Schritte + höheres Fußheben.
4. **„Zu spät adaptiert"** — die Aufricht-Regelung hinkte dem Hang hinterher.

## Der entscheidende Nachweis (Bein-Streckung war ein Leveling-Artefakt)

Verdacht „die Talbeine sind am Hang schon gestreckt" — analytisch gegen die echten
Kinematik-Werte geprüft (radial 0.160, body_height −0.080):

| Fall | reach (alle Beine) | tibia (Knie) | Symmetrie |
|---|---|---|---|
| **Terrain-following** (Körper ‖ Hang) | 0.179 m (alle 6 gleich) | 95.7° | perfekt symmetrisch |
| Leveln 8° (Körper waagerecht) | bis 0.185 m | bis 84.8° (Knie ~11° offener) | 2 Beine gestreckt |

→ **Bei terrain-following ist die Bein-Geometrie identisch zur Flach-Pose — null Streckung.**
Die Streckung kam **nur** vom Leveln (Fuß-Rotation gegen den Hang). Damit ist die echte
Kletter-Grenze bei terrain-following **nicht** das Bein, sondern **Schwerpunkt/Kippen +
Traktion** (vermutlich steiler als die ~8° des Voll-Levelings).

## Die Entscheidung (User)

**Klettern via Voll-Leveling + θ-Geometrie-Tabelle verworfen.** Neuer Ansatz:
**Terrain-Following** — der Körper **folgt dem Boden** (flach → waagerecht, Hang →
hangparallel); der IMU dient nicht mehr zum Waagerecht-Zwingen, sondern für
**Sicherheit + Wackel-Dämpfung + Hang-Wissen**. Achsen-Trennung: **roll → auf 0 ausrichten**
(Links-rechts ist beim Geradeaus-Klettern immer unerwünscht), **pitch → dem Hang folgen**.
Details: [`terrain_following_plan.md`](stage_3_terrain_following_plan.md).

## Was rückgängig gemacht wurde / was bleibt

- **Zurückgesetzt** (Code, via `git reset --hard` + `git clean` auf „3c 1 plan created"):
  Apex-Boost (`trajectory_gen`/`gait_engine`), `slope_table.py`, `slope_param_table.py` +
  Tests, `_update_slope_adapt` + Slope-Params in `gait_node`, `config/slope_params.yaml`,
  `setup.py`-Config-Install, `gait.launch.py` `slope_adapt_enable`-Arg, README-3c-1-Sektion.
  **Alles liegt in der Git-History** — falls Teil-Leveling/Schwerpunkt-Hilfe je den
  Apex-Boost o.ä. brauchen, per cherry-pick zurückholbar.
- **Behalten (Fundament, weiterverwendet):** Stufe 0 (IMU-Plumbing), Stufe 1 (Kipp-/Sturz-
  Erkennung), Stufe 2 `BalanceController` (Regler-Basis — Sollwert wird für TF umgepolt),
  3a-Verkabelung (Leveling-State-Gating → wird Wackel-Dämpf-Gating), slope-/ramp-Welten.

## Verworfene Detail-Pläne (markiert, als Referenz behalten)

- [`stage_3c_slope_params_plan.md`](discarded/stage_3c_slope_params_plan.md) — 3c-Umbrella (Weg-A-
  Geometrie-Tabelle). **Verworfen** für Klettern; die 3b/3d-Ideen (Wackel-Dämpfung, Schlupf)
  leben im neuen TF-Plan weiter.
- [`stage_3c_1_param_table_plan.md`](discarded/stage_3c_1_param_table_plan.md) — 3c-1-Detailplan. **Verworfen.**
- [`stage_3c_1_test_commands.md`](discarded/stage_3c_1_test_commands.md) — 3c-1-Testbefehle. **Verworfen.**

## Lektion

Test-getrieben gearbeitet: das 3c-1-Experiment hat **in der Sim** gezeigt, dass Leveln-zur-
Wasserwaage fürs Klettern der falsche Hebel ist (sprawlig, Plateau-Bug, langsam). Der Code
war das Experiment, die **Erkenntnis** ist das Ergebnis — kein vergeudeter Aufwand, sondern
billig erkauftes Wissen (vs. das erst auf der echten HW zu merken).
