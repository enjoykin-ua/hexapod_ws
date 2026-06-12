# Re-Parametrierung (S4) — Handover für den nächsten Chat

> **Du bist hier richtig, wenn:** nach dem Bein-Umbau (kürzere Femur+Tibia) die
> neuen Stand-/Lauf-Posen eingetragen und die ~93 roten `hexapod_gait`-Tests
> migriert werden sollen. **S1–S3 sind fertig** (Modell, Cal, Envelope-Validierung).
> Branch `leg_changes`. Diese Doku ist ein eigenständiger Anker — alles Nötige steht hier.
>
> **Reihenfolge:** Diese Stage = **S4 (Re-Param)**, DANACH **S5 (Sim/Gazebo)**.
> (Die alte plan.md-Nummerierung hatte Sim vor Re-Param — bewusst getauscht:
> man kann nicht sinnvoll simulieren, bevor die neuen Posen drin sind.)

---

## ✅ FORTSCHRITT (Teil 1 ✅, Teil 2 ✅ — S4 fertig)

**Teil 2 (Test-Migration) ABGESCHLOSSEN** — `colcon test hexapod_gait hexapod_teleop`:
- **hexapod_gait: 204 tests, 0 failures, 28 skipped** (war 71 fail / 28 skip).
- **hexapod_teleop: 30 tests, 0 failures, 1 skip.**
- **hexapod_kinematics: 36 tests, 0 failures** (kein Regress).
- ✅ KRITISCH real-engine: `test_stance_switch::test_mode_walks_all_directions_no_ikerror`
  **alle 3 Modi GREEN**.
- Envelope-Recheck final: Walking mittel/tief/hoch alle Szenarien GREEN; Standup 0.17/-0.10 GRÜN.

**Migrierte Dateien + nennenswerte Abweichungen vom Handover-Plan:**
- `test_joint_load`, `test_gait_patterns`, `test_stance_switch`, `test_sitdown`,
  `test_startup_ramp`, `test_cartesian_standup`, `test_reposition`: Posen + `_POWER_ON_MID`
  (neue 18 rad) + Modus-Tripel migriert.
- **Alle Test-`_URDF_LIMITS` tibia auf -0.28/+2.50 vereinheitlicht** (war teils -1.00 lower) —
  strikt config.py + ros2_control.xacro (Memory `two_joint_limit_sources`).
- **`test_cartesian_standup._RADIAL` = 0.17, NICHT 0.145** (Handover §3 sagte 0.145).
  Begründung: der kartesische Standup operiert an der **breiten standup_radial**; Touchdown
  bei Bauch-Höhe (z=-0.0135) braucht radial ≥0.16 (femur ±1.57 — bei 0.145 wäre femur -1.76,
  out-of-limit). Der real-engine-IK ist die Wahrheit (CLAUDE.md §4). Alt war `_RADIAL` == alte
  standup_radial 0.295, jetzt == neue standup_radial 0.17 — konsistent mit `test_reposition`.
- **`step_length_max` in `test_stance_switch` 0.089→0.03**, `step_height` mehrere Dateien
  0.080→0.04 (Produktiv-Werte; Handover listete sie nicht je Datei, aber nötig/konsistent).
- **`test_param_callback`** linear_max 0.025→0.015 (Node-Default step_length_max 0.03 — das
  vom Handover als „71 statt 70" vorhergesagte Produktiv-Default-Test).
- **`test_sitdown::test_cmd_vel_ignored_in_sitdown_and_sat`**: `_drive()` (setzt t auf 0.02
  zurück) → forward-continue ersetzt. Latenter Test-Bug (Lower-Smoothstep rückwärts
  extrapoliert → out-of-reach), vom alten weiten Envelope maskiert, vom engen aufgedeckt.
- `value_neutral`-Tests (sitdown/reposition): 0.24/0.28 bzw. 0.28/0.24 → reachable 0.14/0.18.

### Self-Review (CLAUDE.md §4)
| Punkt | Status |
|---|---|
| Alle 3 Stance-Modi real-engine GREEN über alle cmd_vel-Richtungen | OK |
| Test-`_URDF_LIMITS` == echte URDF (tibia -0.28/+2.50) statt gedriftet | OK |
| `_POWER_ON_MID` (3 Test-Kopien) == Tool + ros2_control.xacro (18 rad) | OK |
| cartesian_standup an standup_radial 0.17 (femur-konform, statt 0.145) | OK |
| step_height/step_length_max == Produktiv (0.04/0.03) | OK |
| kinematics 36/0 — kein Regress | OK |
| Envelope GREEN ≠ Strom-Beweis (kommt am Boden-Test) | 🟢 später (Phase 13/S5) |
| flake8/pep257 melden tools/*.py-Lint (S3) — nur bei pytest-from-root, nicht in colcon | 🟡 vormerken (eigenes tools/-Lint-Cleanup, nicht S4-Scope) |
| Genaue radii (0.16/0.145/0.13) ggf. +0.005…0.01 Femur-Marge | 🟢 später (S5 Sim/HW-Verify) |

---

## ⏳ FORTSCHRITT (HISTORISCH — Teil 1 ✅, Teil 2 begonnen)

**Teil 1 (Produktiv-Posen) ERLEDIGT** — `hexapod_gait` baut, Werte verifiziert:
- `gait_node.py`: `_STANCE_MODES` tief(0.160,−0.070,0.040) / mittel(0.145,−0.100,0.040) /
  hoch(0.130,−0.130,0.040); `_SIT_SAFE_MIN_BH=−0.115`; Defaults `radial_distance` 0.145,
  `standup_radial_distance` 0.170, `step_height` 0.040, `step_length_max` 0.03;
  radial+standup `fp_range` auf (0.10, 0.21). (`body_height` −0.100 = mittel, unverändert.)
- `gait.launch.py`: step_height 0.040, radial 0.145, step_length_max 0.03.
- `stand.launch.py`: body_height −0.100, radial 0.145.
- teleop `body_height_init` −0.100 **unverändert** (== mittel, schon konsistent).
- **Femur-Marge real-validiert** (`walking_envelope_check` @ step 0.03 / diagonal):
  tief 0.24 / mittel 0.49 / hoch 0.88 rad — sicher (besser als alte lange Beine).

**Teil 2 (Test-Migration) STAND:** `hexapod_gait` **71 fail / 28 skip** (war 93 / 1).
- ✅ `test_show_pose.py` — modul-`pytestmark = pytest.mark.skip` (Show raus).
- ⬜ **OFFEN (7 Dateien)** — §3-Tabelle. Reihenfolge: niedrig (`test_joint_load`, `test_gait_patterns`)
  → mittel (`test_sitdown`, `test_stance_switch`) → hoch (`test_startup_ramp`, `test_cartesian_standup`,
  `test_reposition`: `_POWER_ON_MID` + `_URDF_LIMITS` tibia → −0.28/+2.50 + Posen).
- ⚠️ **71 (nicht 70) fail** → evtl. 1 Test prüft die in Teil 1 geänderten Produktiv-Defaults;
  beim `colcon test` sichtbar, mit-migrieren.
- **Migrations-Zielwerte = die finalen Produktiv-Werte oben** (z.B. `test_stance_switch`
  HOCH/MITTEL/TIEF = genau tief/mittel/hoch von oben).

**Done am Ende:** `colcon test hexapod_gait hexapod_teleop` grün (show=skipped), v.a.
`test_stance_switch` real-engine; `colcon test hexapod_kinematics` weiterhin 36/0.

---

## 0. Stand + zuerst lesen

**Erledigt (Werte stehen, Tests grün):**
- **S1 Modell** ✅ — Längen (L_femur 0.060, L_tibia 0.134), Massen-Split, rad-Limits
  (tibia −0.28/+2.50, coxa ±0.415, femur ±1.57). `hexapod_kinematics` 36/0.
- **S2 Cal** ✅ — 12 Femur/Tibia-Pins in `servo_mapping.yaml`. `hexapod_hardware` grün.
- **S3 Envelope** ✅ — Reichweite/Walking/Standup/Last gerechnet. `power_on_mid`
  (18 rad) neu + in `standup_envelope_check.py` + `ros2_control.xacro` eingetragen.
  Coxa-config-Fix (±0.415). Details + Empfehlungen: [`stage_3_envelope_plan.md §6`](stage_3_envelope_plan.md).

**Test-Stand JETZT:** `hexapod_kinematics` 36/0, `hexapod_teleop` 30/0, `hexapod_hardware`
grün; **`hexapod_gait` 93/204 rot** — **das ist deine Aufgabe** (Migrations-Zustand,
User-Entscheid „rot bis S4", in plan.md notiert).

**Zuerst lesen:** `CLAUDE.md` · `plan.md` (Test-Status-Block) ·
[`stage_3_envelope_plan.md §6`](stage_3_envelope_plan.md) (Posen-Empfehlungen + Warnungen) ·
[`project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md) §1
„Stance-Modi (3 Lauf-Höhen) ändern" + „Gait-Parameter tunen" ·
[`project_finalization/stance_modes_plan.md`](../stance_modes_plan.md) (Voll-Doku Stance-Modi).
Memories: `two_joint_limit_sources`, `project_phase13_stance_modes`, `gait_offset_convention`.

**Neue Reichweite (hart):** Fuß erreichbar nur bei 3D-Distanz vom Femur-Joint
`d = hypot(radial − 0.0436, body_height) ∈ [0.0740, 0.1940]`. Alte Posen
(radial 0.21–0.30) sind out-of-reach — das ist die Bruch-Ursache aller 93 Tests.

---

## 1. Die neuen Werte (aus S3 — STARTWERTE, real-engine validieren!)

### 1.1 Die 3 Stance-Modi (envelope-grün, S3)
| Modus | radial | body_height | step_height | Bedeutung |
|---|---|---|---|---|
| **tief** (Körper tief) | **0.16** | **−0.07** | 0.04 | Fuß nah unter Coxa |
| **mittel** (BOOT-Default) | **0.145** | **−0.10** | 0.04 | Start-Pose + Standup-Basis |
| **hoch** (Körper hoch) | **0.13** | **−0.13** | 0.04 | nur via Switch |

> Alt war: tief (0.255,−0.070), mittel (0.245,−0.100), hoch (0.225,−0.140) — radii ~0.10 zu groß.
> ⚠️ **Namen wie alt:** „hoch" = Körper hoch = tiefstes body_height. `_STANCE_DEFAULT_IDX=1` (mittel).

### 1.2 Weitere Params
| Param | alt | neu (Start) | Quelle |
|---|---|---|---|
| `standup_radial_distance` | 0.295 | **0.17** | S3: grün alle Höhen @ ≥0.16 (breiter Touchdown wg. Femur-±90°) |
| `step_length_max` | 0.05/0.089 (Node/Launch divergent!) | **0.03** | S3-walking grün; Max via `walking_envelope_check recommend` nachtunen |
| `step_height` (Modi + Default) | 0.080 | **0.04** | alt zu groß für L_tibia 0.134; via `--optimize-step-height` feintunen |
| `body_height_min` | −0.140 | **−0.135** | knapp unter „hoch" |
| `body_height_max` | −0.030 | **−0.060** | knapp über „tief" |
| `_SIT_SAFE_MIN_BH` | −0.120 | **real-engine bestimmen** | tiefste bh für direkt-Sit (sonst Route über mittel) |
| `body_height_start` | −0.0135 | **−0.0135 (unverändert)** | Bauch-Box-Geometrie (0.043) unverändert |

> **`step_length_max`-Konflikt auflösen:** Node-Spec sagt 0.05, `gait.launch.py` sagt 0.089
> (Launch gewinnt). Auf EINEN neuen Wert synchronisieren.

---

## 2. Teil 1 — Produktiv-Posen eintragen (synchron halten!)

> **Goldene Regel:** `_STANCE_MODES[1]` (mittel) == `_GAIT_PARAMS`-Defaults ==
> `gait.launch.py`-Args == teleop `body_height_init`. Sonst springt der Body beim
> Boot / ersten Stance-Cycle / Teleop-Start.

| Datei:Zeile | alt → neu | was |
|---|---|---|
| `gait_node.py:521-525` | `_STANCE_MODES` 3 Tripel (s. 1.1) | **Zentralstelle** der 3 Höhen |
| `gait_node.py:530` | `_SIT_SAFE_MIN_BH −0.120` → real-engine | Sit-Routing-Schwelle |
| `gait_node.py:177` | `body_height −0.100` → **−0.10** | Default == mittel (fp_range ggf. anpassen) |
| `gait_node.py:187` | `radial_distance 0.245` → **0.145** | Default == mittel |
| `gait_node.py:200` | `standup_radial_distance 0.295` → **0.17** | breite Aufsteh-Pose |
| `gait_node.py:230` | `step_length_max 0.05` → **0.03** | + Konflikt mit Launch auflösen |
| `gait_node.py:153` | `step_height 0.080` → **0.04** | Swing-Hub |
| `gait_node.py:271,280` | `bh_min −0.140 / bh_max −0.030` → **−0.135 / −0.060** | Schranken |
| `gait.launch.py:67,77,96,42,149,158` | body_height −0.100→−0.10, radial 0.245→0.145, step_length_max 0.089→0.03, step_height 0.080→0.04, bh_min −0.140→−0.135, bh_max −0.030→−0.060 | **2. Quelle, synchron** |
| `joy_to_twist.py:90` + `ps4_bt.yaml:57` + `ps4_usb.yaml:61` | `body_height_init −0.100` → **−0.10** | == mittel (Falle: Body-Sprung sonst) |
| `joy_to_twist.py:92-93` + `ps4_*.yaml:59-60/63-64` | bh_min/max → −0.135/−0.060 | teleop-Clamp |
| `stand.launch.py:22,33` | bh −0.080→−0.10, radial 0.295→0.145 | ⚠️ war inkonsistent, mit angleichen |

`gait_engine.py` ist **wertneutral** — nichts anzupassen (außer evtl. `body_height_start`-Fallbacks
falls Bauch-Höhe sich änderte; tut sie nicht). Presets: nur bei Bedarf neue erzeugen
(`walking_envelope_check recommend --body-height -0.10 --output ...`); alte sind veraltet.

---

## 3. Teil 2 — gait-Test-Migration (93 rot → grün)

**KEIN conftest.py / keine zentrale Test-Konstante — jede Datei einzeln.** Zwei
Migrations-Vektoren: (A) out-of-reach-Posen auf neue Werte, (B) `_URDF_LIMITS`
tibia auf −0.28/+2.50 (driftet, teils sogar −1.00/+1.30 veraltet).

| Datei (Fails) | Aufwand | was tun |
|---|---|---|
| `test_show_pose.py` (23) | **skip** | modul-level `pytestmark = pytest.mark.skip(reason="Show raus aus leg_changes — separate Re-Param")` |
| `test_joint_load.py` (8) | niedrig | nur `radial=`-Args: `_stand_angles(radial=0.25→0.145, bh=-0.10)` (:28), Sweep `0.20/0.27` (:108-109) → erreichbar (z.B. 0.14/0.18). **Last-Asserts tracken L_tibia automatisch — NICHT neu rechnen.** |
| `test_gait_patterns.py` (3) | niedrig | `_WALK_RADIAL 0.215→0.145` (:33), `_BH −0.120→−0.10` (:34), `_STEP_LENGTH_MAX 0.089→0.03` (:37); `_URDF_LIMITS` tibia ist schon +2.50 ✓ |
| `test_stance_switch.py` (11) | mittel | 3 Modus-Tripel `HOCH/MITTEL/TIEF` (:26-28) auf neue Werte (1.1), `standup_radial 0.295→0.17` (:38), Inline `0.190,−0.140` (:72,:131); `_URDF` tibia +2.50 ✓. **Das ist der real-engine-Test — muss alle cmd_vel-Richtungen grün sein.** |
| `test_sitdown.py` (15) | mittel | `_WALK_RADIAL 0.215→0.145` (:36), `_STANDUP_RADIAL 0.295→0.17` (:37), `_BH −0.120→−0.10` (:38); `_SPAWN_POSE` (:223) prüfen |
| `test_startup_ramp.py` (14) | **hoch** | `_POWER_ON_MID` (:68-75) → **neue Werte (s.u.)**; Stand `radial 0.295→0.145, bh −0.080→−0.10` (:42,44), `foot=(0.295,…)` (:391); **`_URDF_LIMITS` tibia (:56-57) `−1.00/+1.30` → `−0.28/+2.50`** |
| `test_cartesian_standup.py` (10) | **hoch** | `_POWER_ON_MID` (:41-48) → neue Werte; `_RADIAL 0.295→0.145, _BH_FINAL −0.080→−0.10` (:56-57); **`_URDF_LIMITS` tibia (:35) `−1.00/+1.30` → `−0.28/+2.50`** |
| `test_reposition.py` (9) | **hoch** | `_POWER_ON_MID` (:31-38) → neue Werte; `_STANDUP_RADIAL 0.295→0.17` (:40), `_WALK_RADIAL 0.220→0.145` (:41), `_BH −0.080→−0.10` (:42); `_URDF` tibia +2.50 ✓ |

### `_POWER_ON_MID` — neue Werte (3× identisch ersetzen)
```python
_POWER_ON_MID = {
    'leg_1': (-0.0692, -0.7732, 0.8491),
    'leg_2': (0.1556, -0.9523, 0.9089),
    'leg_3': (-0.1115, -0.8431, 1.0046),
    'leg_4': (0.0259, -0.8157, 1.0485),
    'leg_5': (0.1037, -0.8276, 0.9745),
    'leg_6': (0.0519, -0.7697, 0.8464),
}
```
(= `pulse_us_to_radians(1500)` mit der S2-Cal, Coxa-validiert. Stehen schon korrekt
in `standup_envelope_check.py` + `ros2_control.xacro` — von dort kopierbar.)

> ⚠️ `test_show_node.py` war nicht in der Failure-Liste — falls es eigene Posen hat, separat prüfen.

---

## 4. Validierung (Done-Kriterium S4)

1. `colcon build --packages-select hexapod_gait hexapod_teleop --symlink-install`
2. `colcon test --packages-select hexapod_gait hexapod_teleop` → **alle grün** (außer show = skipped).
3. **KRITISCH — real-engine:** `test_stance_switch.py::test_mode_walks_all_directions_no_ikerror`
   muss grün sein. ⚠️ `walking_envelope_check` ist am Femur-Wand-Rand **zu optimistisch**
   (ai_navigation): wenn der real-engine-Test fehlert, wo der Envelope GREEN sagt, die
   radii mit mehr Femur-Marge wählen (~≥0.15 rad), nicht am Min-Radial-Rand.
4. Recheck mit den **finalen** Werten:
   `python3 tools/walking_envelope_check.py check --radial <mittel> --body-height -0.10 --scenario all` ·
   `python3 tools/standup_envelope_check.py --radial 0.17 --bh-final -0.10` (alle Modi-bh durchgehen).
5. `colcon test --packages-select hexapod_kinematics` weiterhin 36/0 (kein Regress).
6. Self-Review-Tabelle (CLAUDE.md §4), dann S4 fertig → **S5 (Sim)**.

---

## 5. Fallstricke
- **5 power_on_mid-Stellen:** 2 in S3 erledigt (Tool + ros2_control), **3 Test-Kopien hier** (synchron!).
- **2 Limit-Quellen + Test-`_URDF_LIMITS`:** mehrere Tests hardcoden tibia-Limits, die von
  config.py (−0.28/+2.50) abweichen → mit-migrieren, sonst testen sie gegen falsche Grenzen.
- **Boot-Default 3-fach** (Node/Launch/teleop body_height_init) — sonst Body-Sprung.
- **Envelope optimistisch am Femur-Rand** → `test_stance_switch` real-engine ist die Wahrheit.
- **Stance-Übergänge:** „hoch" (−0.13) evtl. nicht direkt sit-/standup-fähig → Routing über mittel
  (`_SIT_SAFE_MIN_BH`), wie bei den langen Beinen. Real-engine prüfen.
- User macht **Commits selbst**; rote gait-Tests bis S4-Ende akzeptiert (dann grün).

## 6. Offene Punkte (mit User / via Tool klären)
1. **step_height / step_length_max final** — via `walking_envelope_check recommend
   --optimize-step-height` für die mittel-Höhe; 0.04/0.03 sind nur Startwerte.
2. **`_SIT_SAFE_MIN_BH`** — real-engine bestimmen (tiefste direkt-Sit-bh).
3. **Genaue Stance-Modi-radii** — 0.16/0.145/0.13 sind envelope-grün, aber mit
   `test_stance_switch` (real-engine, Femur-Marge) gegenchecken; ggf. radial +0.005…0.01.
4. **Presets** — alte (sim_walk etc.) löschen/aktualisieren oder lassen? (Nur `feet_closer_walk`
   war halbwegs aktuell, jetzt auch veraltet.)
