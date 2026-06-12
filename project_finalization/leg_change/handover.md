# Bein-Umbau — Handover für den nächsten Chat

> **Du bist hier richtig, wenn:** der Bein-Umbau (kürzere Femur+Tibia) umgesetzt
> werden soll. Die **Hardware-Cal ist fertig** — alle Werte stehen unten. Deine
> Aufgabe: Werte in die Modell-/Cal-Dateien eintragen, in Gazebo/RViz + Envelope
> validieren, dann (später) HW. **Branch:** `leg_changes` (von `main` @ Tag
> `legs-tibia-long`). Nichts ist am Roboter-Modell bisher geändert — nur diese
> Doku + `test_commands.md` existieren.

---

## 0. Zuerst lesen (in dieser Reihenfolge)

1. `CLAUDE.md` + `PHASE.md` (Standard-Einstieg).
2. [`project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md)
   — **„Ich ändere X → aktualisiere Y → validiere mit Z"**; bei Geometrie/Limit-
   Änderungen die zentrale Navigations-Datei (zwei Limit-Quellen, Cal-Pipeline,
   Validierungs-Gates). Übersicht: [`project_architecture/00_overview.md`](../../project_architecture/00_overview.md).
3. [`plan.md`](plan.md) — der 9-Schritt-Ablauf + Design-Entscheidungen D1–D5.
4. [`test_commands.md`](test_commands.md) — die Live-/Cal-Prozedur; **A.3d** = die rohen Cal-Notizen.
5. [`docs/01_hardware_change_workflow.md`](../../docs/01_hardware_change_workflow.md)
   **Szenario 1 (Bein-Segment-Größen)** + **Pflicht-Sektion „Lokomotion neu validieren"** — das ist die Datei-Checkliste, NICHT duplizieren.
6. `docs/00_conventions.md §11` (alte Geometrie-Tabelle — die du aktualisierst).
7. Memories: `two_joint_limit_sources`, `phase13_femur_zero_asymmetry`, `urdf_refactor_full_smoke`.

---

## 1. Die neuen Werte (alles fertig gemessen/gerechnet)

### Geometrie (nur Längen + Massen ändern, B×H + Foot UNVERÄNDERT)

| Segment | Länge alt → neu | Breite × Höhe | Masse alt → neu |
|---|---|---|---|
| Coxa  | 0.0436 (unverändert) | 0.0254 × 0.0582 | 0.1167 (unverändert) |
| Femur | 0.07994 → **0.060** | 0.059 × 0.020 (gleich) | 0.1167 → **0.102** |
| Tibia | 0.200 → **0.134** | 0.012 × 0.012 (gleich) | 0.1167 → **0.118** |
| Foot  | Kugel r=0.008 (unverändert) | — | 0.005 (unverändert) |

> Massen: beide Segmente zusammen 220 g, Tibia +15 % → Femur 0.102 kg, Tibia 0.118 kg.
> **`physical_properties.xacro` hat aktuell EINEN `segment_mass=0.1167`** für beide —
> das muss in **`femur_mass` + `tibia_mass`** aufgeteilt werden (Macro-Aufrufe anpassen).
> Inertien propagieren danach **automatisch** über das `inertials.xacro`-Macro
> (Box-Formel + 1e-5-Clamp) — nicht von Hand rechnen.

Reichweite neu: innen `|L_f−L_t|` = **0.074 m**, außen `L_f+L_t` = **0.194 m**
(alt 0.120 / 0.280). → Stand-Höhe, `radial_distance`, `step_length` müssen neu (Schritt 6).

### Servo-Cal → `servo_mapping.yaml` (12 Einträge ersetzen; Coxa unberührt)

**Quelle = diese Tabelle** (NICHT die evtl. gespeicherte yaml — es wurde KEIN
`/save_calibration` gemacht). `A→pulse_zero`, größerer Anschlag→`pulse_max`,
kleinerer→`pulse_min`. **directions bleiben wie alt.**

**Femur** (dir: rechts +1 / links −1):
| Pin | Joint | pulse_min | pulse_zero | pulse_max | dir |
|---|---|---|---|---|---|
| 1  | leg_1_femur | 1162 | 1828 | 2485 | +1 |
| 4  | leg_2_femur | 1247 | 1890 | 2500 | +1 |
| 7  | leg_3_femur | 1206 | 1841 | 2499 | +1 |
| 10 | leg_4_femur |  502 | 1155 | 1819 | −1 |
| 13 | leg_5_femur |  517 | 1150 | 1814 | −1 |
| 16 | leg_6_femur |  536 | 1172 | 1841 | −1 |

**Tibia** (dir: rechts −1 / links +1):
| Pin | Joint | pulse_min | pulse_zero | pulse_max | dir |
|---|---|---|---|---|---|
| 2  | leg_1_tibia | 800 | 1860 | 2017 | −1 |
| 5  | leg_2_tibia | 798 | 1901 | 2016 | −1 |
| 8  | leg_3_tibia | 845 | 1940 | 2090 | −1 |
| 11 | leg_4_tibia | 895 | 1050 | 2123 | +1 |
| 14 | leg_5_tibia | 930 | 1079 | 2159 | +1 |
| 17 | leg_6_tibia | 970 | 1134 | 2215 | +1 |

`pulse_min < pulse_zero < pulse_max` ist bei allen 12 erfüllt (geprüft).

### rad-Limits → `hexapod.urdf.xacro` (6×) + `config.py`

| Joint | aktuell | NEU | Begründung |
|---|---|---|---|
| Coxa  | ±1.57 | **±1.57 (unverändert)** | nicht umgebaut |
| Femur | ±1.57 | **±1.57 (unverändert)** | gemessene Anschläge ~±84–90° (Servo-Ende = mech. Anschlag); ±1.57 nominal, per-Servo-Cal fängt die Variation |
| Tibia | [−1.00, +2.50] | **[−0.28, +2.50]** | Überstrecken-Anschlag der neuen Tibia ist viel enger (gemessen ~16–22°, engste Leg 2 = 115 µs → −0.28 rad). Einknicken ~unverändert (engste Leg 1 ~+2.54, +2.50 sicher) |

> **Slope-Hinweis:** Tibia-rad aus dem **Femur-slope** (~655 µs/90° = 7.28 µs/°)
> umrechnen, NICHT aus dem gemessenen Knie-90° (~616 µs — visuell leicht
> unterschätzt). Sonst kommen die Tibia-Limits ~12 % zu groß raus.
> **Vorzeichen** (+ = einknicken, − = überstrecken) ist konsistent mit der
> Stand-Pose (`tibia ≈ +0.758`) — beim Eintragen mit einem rad→pulse-Roundtrip
> gegenchecken (`test_config.py`-Logik / `Calibration`-Roundtrip-Tests).

---

## 2. Was zu tun ist

### Schritt 3 + 4 — Werte eintragen (Kern)
- [ ] `src/hexapod_hardware/config/servo_mapping.yaml`: 12 Femur/Tibia-Einträge ersetzen (Tabelle oben), Coxa unberührt. **Backup vorher** (`.bak`).
- [ ] `src/hexapod_description/urdf/hexapod_physical_properties.xacro`: `femur_length`/`tibia_length`, `segment_mass` → `femur_mass`/`tibia_mass` aufteilen, `tibia_lower` −1.00 → **−0.28**. (Inertia propagiert via Macro.)
- [ ] `src/hexapod_description/urdf/hexapod.urdf.xacro`: per-Bein `tibia_lower` 6× anpassen (Femur/Coxa bleiben).
- [ ] `src/hexapod_kinematics/hexapod_kinematics/config.py`: `_FEMUR_LEN`/`_TIBIA_LEN` (falls vorhanden) + `_TIBIA_LIMITS = (-0.28, 2.50)` spiegeln.
- [ ] **Zwei Limit-Quellen synchron** (URDF == config.py) — `test_config.py` fängt Drift.

### Schritt 5 — Cross-Check + Sim (vor HW!)
- [ ] `colcon test --packages-select hexapod_kinematics` grün (xacro↔config.py).
- [ ] **Envelope-Tools (Mathe, ZUERST — Sim ist lenient und versteckt out-of-reach):**
      `tools/walking_envelope_check.py`, `standup_envelope_check.py`, `show_pose_cog_check.py`.
- [ ] **Gazebo-Spawn + RViz** (User will explizit in Gazebo testen) + `reachability_viz.launch.py` — Modell stimmt visuell, Reichweite plausibel.

### Schritt 6 — Re-Parametrierung (aus neuer Geometrie)
- [ ] Stand-Pose-Höhe + `radial_distance` neu (kompaktere Reichweite!).
- [ ] **Laufhöhen: evtl. nur noch 2 statt 3** — aus Envelope bestimmen (User-Erwartung, separat besprechen).
- [ ] `step_length` / `cycle_time` / Walking-Params neu tunen (Sim).

### Schritt 7–9 (später)
- [ ] HW-Validierung **am Desktop** (nicht Pi): aufgehängt → Boden (Init, Aufstehen, Laufen, Gangarten, Teleop).
- [ ] Pi-Kurztest.
- [ ] `00_conventions.md §11` (Geometrie-Tabelle) aktualisieren · Self-Review · Merge `leg_changes`→`main` (+ Tag z. B. `legs-v2-done`).

---

## 3. Fallstricke

- **Zwei Limit-Quellen** (URDF *und* config.py) müssen gleich sein.
- **Tibia asymmetrisch, aber alle 6 Beine GLEICH** (nicht per-Bein → das war der alte
  `femur_zero_asymmetry`-Bug). Coxa/Femur symmetrisch.
- **Mathe-Envelope vor Sim** (Sim lenient maskiert IK-Freeze, der auf HW zuschlägt).
- **Validierung: Sim → HW-aufgehängt → Boden**, alles am **Desktop**; Pi nur Kurztest.
- **URDF-Refactor full smoke** (Memory): nicht nur build/xacro-parse — sim + rviz +
  walking smoke, sonst bleiben mesh-/tf2-/Konsumenten-Bugs verborgen.
- User macht **Commits selbst** (`feedback_user_does_commits`); Live-HW-Befehle ins
  `test_commands.md`, nicht in den Chat.

---

## 4. Offene Entscheidungen (mit User klären, nicht raten)
- Laufhöhen 2 vs 3 (Schritt 6, aus Envelope).
- Ob `tibia_lower = −0.28` (engste, Leg 2) oder etwas weiter (~−0.36, Rest) — engste ist
  sicher, aber sehr knapp; mit User abwägen sobald Envelope zeigt, ob −0.28 reicht.
