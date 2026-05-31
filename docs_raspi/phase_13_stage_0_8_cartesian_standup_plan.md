# Phase 13 — Stage 0.8 (provisorisch): Kartesisches schürffreies Aufstehen

> **STATUS: 🟡 GETRIGGERT (2026-05-31) — Plan steht, Code/Umnummerierung offen.**
> **Trigger erfüllt:** 0.6-Live (HW aufgebockt, T4) bestätigt, dass die Füße beim
> joint-space-Aufstehen sichtbar einwärts wandern (Schürf-Befund 0.5, Memory
> `project_phase13_standup_foot_scrape`). Nächste Arbeit: §8 offene Punkte mit
> User klären → §9 Umnummerierung (0.8→0.7, Boden→0.8) → implementieren.
>
> **⚠️ Nummerierung provisorisch:** Diese Datei heißt „0.8", damit die schon
> definierten Stages 0.6 (HW aufgebockt) + 0.7 (Boden-Test) jetzt **nicht**
> angefasst werden. Bei Aktivierung erfolgt ein **Tausch** (§9): dieser Plan
> wird zur **0.7** (kommt VOR dem Boden-Test), der aktuelle Boden-Test wandert
> auf **0.8**.

---

## 1. Warum (Befund aus 0.5)

Das Aufstehen ([STARTUP_RAMP](../src/hexapod_gait/hexapod_gait/gait_engine.py#L506))
interpoliert **joint-space** (smooth-step der Winkel), nicht kartesisch. Folge
(FK-Rechnung über den Ramp, leg_1 repräsentativ):

| | Fuß horizontal (rx) | Fuß vertikal (rz) |
|---|---|---|
| Start power_on_mid | 0.310 m | +0.078 m (Fuß eingezogen, über Coxa) |
| Mitte p≈0.4 | 0.317 m (Bulge raus) | +0.021 m |
| Ende Stand | 0.295 m | −0.080 m |

In der **belasteten** zweiten Hälfte wandert der Fuß **~15–22 mm nach innen**,
während der Körper hochgedrückt wird → auf dem Boden = Schürfen/Schürfen unter
Last. Wurzel = Winkel-Lerp hält Fuß-x nicht konstant. **NICHT** die Tibia-Länge
(0.2 m verstärkt nur den Hebel) — Tibia kürzen wäre zudem URDF-Geometrie und
damit §7.7-TABU (bricht IK/FK/Cal/sim↔HW).

## 1a. HW-Befunde 0.6 + Strom-Analyse (entscheidend, 2026-05-31)

Der User hat das aktuelle joint-space-Aufstehen am **Boden** (außerplanmäßig)
und **aufgebockt** (0.6) getestet. Befunde:

- **Stehen kostet nur ~400 mA** (18 Servos, = ~22 mA/Servo). Das **statische
  Stützen** des Körpergewichts in der Stand-Pose ist also **billig**.
- **Aufstehen am Boden zieht >3,5 A** → Overcurrent-Trip + Voltage-Drop (die
  Bench-PSU kann den Spitzenstrom nicht schnell genug liefern; LiPo könnte, dann
  aber >10 A — zu hoch). Strom-Limit musste auf 7000 mA, löst das aber nicht.

**Schlussfolgerung (der eigentliche Grund für 0.8):** Da der Strom beim *Halten*
verschwindet, ist der Aufsteh-Peak **fast vollständig Schürf-Reibung**, nicht
Hub-Last. Das ist die Wurzel — und cartesian (schürffrei) eliminiert genau sie.

**Geometrie-Rechnung (echte FK, bestätigt die Diagnose):**

- Bauch-Box-Höhe 0.043 m, Coxa mittig (leg_mount_z=0) → bei aufliegendem Bauch
  ist die Coxa nur **~21,5 mm** über Grund → **`body_height_start ≈ −0.0135 m`**
  (Fuß am Boden, rz relativ Coxa; Foot-Radius 0.008 eingerechnet).
  *(Anm.: Bauch-Box ist in der URDF schmaler als die Coxa-Spannweite beschrieben,
  liegt aber auf dem Bauch auf — für die Höhe vernachlässigbar, so beibehalten.)*
- Cartesian Phase 2 hält **rx = 0.295 konstant** = exakt der Hebelarm der
  Stand-Pose (Fuß→Femur-Achse = 0.251 m). Da der Stand bei rx 0.295 nur 400 mA
  zieht, bleibt das Stütz-Drehmoment über den **ganzen** Hub auf Stand-Niveau —
  **kein** Drehmoment-Peak durch Geometrie.
- Knie-Beugung über Phase 2: **43°→58°** (gebeugt, d/reach 90–94 %) → **keine**
  Streckungs-Singularität. Die früher vermutete „gestrecktes-Bein-zieht-zu-viel"-
  Sorge ist damit **widerlegt**.

**Prognose:** cartesian-Aufstehen zieht nahe dem Stand-Strom (~400 mA) statt
>3,5 A — der Schürf-Anteil (~3,1 A) fällt weg. **Zu verifizieren am Boden mit
Strom-Logging (das ist das eigentliche Done-Kriterium von 0.8).**

**Geschwindigkeit:** Der User-Constraint „nicht schneller als jetzt" wird
eingehalten (auto_standup_duration ≥ heutige ~4 s). **Wichtig (Korrektur):** der
Strom-Treiber ist das **Schürfen**, nicht die Geschwindigkeit — nur langsamer
machen (ohne cartesian) würde weiter schürfen. Cartesian ist der Hebel, langsam
bleiben ist das konservative Sahnehäubchen.

**End-Pose-Frage (User):** Die gute Pose, die ihm beim Halten gefiel, **ist** die
aktuelle Stand-Pose (radial 0.295 / bh −0.080) und **exakt der Endpunkt** von
Phase 2 → mit cartesian **identisch erreichbar**, keine andere Position nötig.
Cartesian ändert nur den **Weg** dorthin, nicht das Ziel.

## 2. Konzept: zwei Phasen, schürffrei by design

Ein sauberes Aufstehen vom Bauch zerfällt zwingend in zwei Phasen, weil
power_on_mid **keine** gültige Stand-artige IK-Pose ist (Füße über der Coxa):

- **Phase 1 — Touchdown (bauch-gestützt):** Füße von der eingezogenen
  power_on_mid-Pose nach außen-unten zu den finalen Boden-Aufsetzpunkten
  `(radial_final, 0, body_height_start)` bringen. Hier **dürfen** sich die Füße
  in x+y bewegen — der **Bauch trägt** noch, die Füße sind unbelastet → kein
  Schürfen unter Last.
- **Phase 2 — Push (Füße fix):** Fuß-x+y **fix** bei `(radial_final, 0)`, nur
  `body_height` von `body_height_start` → `−0.080` rampen. Pro Tick
  `stand_pose(radial_final, body_height(t))` → `leg_ik`. Coxa bleibt 0, der
  Fuß-Weltpunkt steht → **null Schürfen by design.** Der Körper schiebt sich
  senkrecht über die fixen Füße hoch.

### ⚠️ Design-Regel (verhindert Komplexitätssprung)
**Alle Foot-Platzierung VOR dem Abheben** (in Phase 1, bauch-gestützt). Sobald
der Bauch abhebt (Phase 2, Füße tragen), würde ein Bein-Anheben zum Umsetzen
die Stützbasis auf 5 Beine reduzieren → erforderte **statische Stabilität =
Tripod 3+3** (vgl. 0.4 DL-7). Das vermeiden wir, indem in Phase 2 **kein** Fuß
mehr versetzt wird, nur senkrecht gedrückt → all-6 bleibt gültig, kein Tripod.
Ein Zwischen-Reposition ist nur Fallback, falls die Reichweite zwei Touchdown-
Etappen erzwingt — und auch dann **nur solange der Bauch trägt**.

## 3. Architektur-Ausgangslage (gute Nachricht)

Die Engine ist **durchgängig kartesisch**: `compute_foot_targets` → cartesian
Targets, `leg_ik` → Winkel; der Tick-Dispatcher
[compute_joint_angles](../src/hexapod_gait/hexapod_gait/gait_engine.py#L467)
verzweigt schon nach State. `stand_pose(radial, body_height)`,
`swing_traj` (Fuß-Bogen) und `stance_traj` existieren. **Nur** STARTUP_RAMP ist
der joint-space-Sonderfall. Der Umbau nutzt also vorhandene Maschinerie —
keine neue Architektur, kein neues Paket, **keine** Geometrie-/Hardware-Änderung.

## 4. Logik-Skizze / Pseudocode

```
# Neuer State STATE_CARTESIAN_STANDUP (ersetzt oder ergänzt STARTUP_RAMP).
# Trigger wie bisher: erster vollständiger /joint_states-Empfang.

start_cartesian_standup(start_joints, t, duration):
    start_foot[leg]   = leg_fk(start_joints[leg])          # power_on_mid kartesisch
    touchdown[leg]    = (radial_final, 0, body_height_start)
    push_end[leg]     = stand_pose(radial_final, body_height_final)  # (r,0,-0.080)
    # phase1_frac z.B. 0.4 der Gesamtdauer

compute_cartesian_standup_angles(t):
    p = (t - t0) / duration
    for leg:
        if p < phase1_frac:                                # PHASE 1 Touchdown
            s = smoothstep(p / phase1_frac)
            foot = lerp(start_foot[leg], touchdown[leg], s)
            # optional z-Bogen (swing-artig), damit der Fuß nicht über den
            # Boden schleift, falls die direkte Linie zu flach ginge
        else:                                              # PHASE 2 Push
            s = smoothstep((p - phase1_frac) / (1 - phase1_frac))
            bh = lerp(body_height_start, body_height_final, s)
            foot = (radial_final, 0, bh)                   # x+y FIX → schürffrei
        angles[leg] = leg_ik(*foot, leg, limits[leg])      # in-limits geprüft!
    if p >= 1.0: state = STANDING
    return angles
```

**Design-Begründungen:**
- Phase 2 hält `radial` + `y` konstant und variiert nur `body_height` → die IK
  hält coxa=0 und bewegt nur femur/tibia → Fuß senkrecht unter dem Mount → der
  Schürf-Mechanismus ist eliminiert, nicht nur reduziert.
- `start_foot` via `leg_fk` nötig, weil power_on_mid als **Joint**-Pose gegeben
  ist, Phase 1 aber kartesisch interpoliert.
- Offene Frage Phase-1-Methode (§7): reiner kartesischer Lerp kann durch
  IK-ungültige Regionen laufen → ggf. joint-space-Phase-1 oder z-Bogen.

## 5. Arbeitspakete

> **Risiko-Lage nach 0.6 verschoben:** Phase 2 (Push) ist dank konstantem
> Hebelarm + 400-mA-Stand-Befund **gutartig** (kein Drehmoment-Peak, keine
> Singularität). Der heikle Teil ist jetzt **B (Phase-1-Touchdown)** + **C
> (body_height_start treffen)** — dort entscheidet sich, ob Phase 1 schürffrei
> bleibt. Und **F (Strom-Validierung am Boden)** ist das **eigentliche
> Done-Kriterium**, nicht die Sim.

| # | Inhalt | Größe |
|---|---|---|
| A | Phase-2 cartesian Push (body_height-Rampe, radial fix, reuse `stand_pose`/`leg_ik`) | klein |
| B | **Phase-1 Touchdown-Platzierung** (power_on_mid → Aufsetzpunkte) — Füße fast senkrecht runter, **kein vorzeitiger Bodenkontakt** (sonst schürft Phase 1); ggf. z-Bogen | mittel — **Kern-Risiko** |
| C | **`body_height_start ≈ −0.0135 m`** verifizieren/kalibrieren (Sim + Boden) — zu hoch → Körper fällt am Übergang, zu tief → Füße setzen zu früh + schürfen | klein-mittel — **Kern-Risiko** |
| D | **In-Limits + Reachability über den GANZEN Pfad neu beweisen** — der 0.4-Monotonie-Beweis gilt bei cartesian nicht mehr; IK kann zwischendrin an Limits/Singularität | mittel — sicherheitskritisch |
| E | Offline-Tool (Stil `walking_envelope_check.py`): Touchdown-Punkte + Zielhöhe + In-Limits-Envelope vorab rechnen | klein-mittel |
| F | **Strom-Validierung am Boden** (mit Strom-Logging): Aufsteh-Peak nahe Stand-Niveau statt >3,5 A? **Das eigentliche Done-Kriterium** | mittel — Live-Beweis |

## 6. Tests-Liste mit Begründung

### 6.1 Pure-Python (pytest)
| Test | Prüft | Warum |
|---|---|---|
| `cartesian_standup_path_in_limits` | alle Zwischensamples (beide Phasen) × 18 Joints ∈ URDF-Limits | kein HW-Freeze (ersetzt den 0.4-Monotonie-Beweis, der hier nicht mehr greift) |
| `cartesian_standup_reachable` | jeder Zwischen-Foot-Target hat gültige IK-Lösung (kein out-of-reach) | cartesian kann unerreichbare Punkte erzeugen |
| `phase2_foot_xy_constant` | in Phase 2 ist rx (und y) über alle Samples konstant (±ε) | **der Schürf-frei-Beweis** |
| `phase1_no_premature_ground_contact` | in Phase 1 bleibt der Fuß-Welt-z ≥ 0 bis zum Touchdown-Punkt (mit body_height_start + z-Bogen) | Phase 1 darf nicht selbst schürfen (Kern-Risiko B/C) |
| `cartesian_standup_endpoint_is_stand_pose` | Ende == `stand_pose(radial_final, −0.080)` alle 6 Beine | korrektes Ziel (= die gute Pose) |
| `phase2_body_height_monotonic` | body_height monoton start→ziel | kein Durchsacken |

### 6.2 Live (das eigentliche Done-Kriterium)
- **Strom am Boden** (Paket F): Aufsteh-Peak nahe Stand-Niveau (~400 mA-Bereich),
  **kein** Overcurrent-Trip / Voltage-Drop mit der Bench-PSU. Schürf-frei visuell
  bestätigt (Füße stehen in Phase 2 fix). Das ist der Beweis, dass 0.8 das
  ursprüngliche Problem (>3,5 A) löst.

### 6.3 Bewusst NICHT testbar in Pure-Python (→ HW-Stages)
- Servo-Stall-Moment, reale Reibung/Grip (bleibt Fuß real fix?), echte
  Bauch-Auflagehöhe → Sim + HW aufgebockt + Boden.

## 7. Progress-Checkliste (vorläufig, → progress-File bei Aktivierung als 0.7.x nach Tausch)

```
- [ ] X.1  Offline-Tool: Touchdown-Punkte + body_height_start + In-Limits-Envelope
- [ ] X.2  STATE_CARTESIAN_STANDUP + Phase-1 Touchdown-Logik (kein vorzeitiger Bodenkontakt)
- [ ] X.3  Phase-2 cartesian Push (radial fix, body_height-Rampe)
- [ ] X.4  In-Limits/Reachability-Tests über ganzen Pfad (ersetzt 0.4-Monotonie-Beweis)
- [ ] X.5  Schürf-frei-Test (rx in Phase 2 konstant) + Phase-1-kein-vorzeitiger-Kontakt-Test
- [ ] X.6  colcon test hexapod_gait grün (+ lint)
- [ ] X.7  Sim-Visualisierung: kein Einwärts-Schürfen mehr sichtbar; body_height_start-Gegenprobe
- [ ] X.8  HW aufgebockt: Bewegung sauber, Füße in Phase 2 senkrecht
- [ ] X.9  **HW Boden + Strom-Logging: Aufsteh-Peak nahe Stand-Niveau, kein Trip/Voltage-Drop** (Done-Kriterium)
- [ ] X.10 README/Doku: STARTUP_RAMP → cartesian standup, joint-space als Legacy
- [ ] X.11 Self-Review-Tabelle, Fixe erledigt
```

## 8. Offene Punkte für User-Review (vor Code-Start, nach 0.6-Trigger)

| # | Frage | Tendenz |
|---|---|---|
| 8.1 | Phase-1-Methode: joint-space-lerp vs. kartesisch-mit-z-Bogen vs. `swing_traj`-reuse? | erst Reachability prüfen (E), dann wählen |
| 8.2 | `body_height_start`: analytisch aus Bauch-Box oder in Sim messen? | beides — analytisch + 1× Sim-Gegenprobe |
| 8.3 | Ein State mit zwei Phasen oder zwei States? | ein State, zwei Phasen (einfacher, ein Trigger) |
| 8.4 | Reicht all-6 in beiden Phasen (Platzierung vor Abheben) → kein Tripod? | Erwartung **ja** (§2 Design-Regel) — in D verifizieren |
| 8.5 | Duration-Aufteilung Phase1/Phase2 + Gesamtdauer? | Param, Default ~40/60 %, gesamt ≥ heutige ~4 s (User: nicht schneller) |
| 8.6 | Joint-space STARTUP_RAMP als Legacy-Fallback behalten oder ersetzen? | behalten (aufgebockt nützlich), cartesian als neuer Default |
| 8.7 | **`body_height_start` real treffen:** −0.0135 m ist Geometrie-Rechnung. Wie kalibrieren (Sim-Drop-Ruhelage messen? Boden-Feintuning-Param?) ohne dass Phase 1 schürft oder der Körper am Übergang fällt? | Param + Sim-Messung, Boden-Feintuning |
| 8.8 | **Strom-Logging-Quelle am Boden:** Diagnostic-Topic (`publish_servo_pulses`/Strom-Telemetrie) vs. PSU-Anzeige — welche Granularität reicht für den Peak-Nachweis? | beides, PSU für Peak |

## 9. Umnummerierungs-Plan (bei Aktivierung auszuführen)

**Aktueller Stand (Stage-0-Plan §6):**
- 0.6 = HW Live aufgebockt (Init + Stand-up)
- 0.7 = Boden-Test (Hexapod liegt am Bauch, Aufstehen all-6)

**Nach Trigger (0.6 bestätigt Umbau-Bedarf):**
- 0.6 = HW aufgebockt — **bleibt**
- **0.7 = kartesisches schürffreies Aufstehen** (dieser Plan, umbenannt von 0.8)
- **0.8 = Boden-Test** (der bisherige 0.7-Inhalt wandert hierher)

**Begründung der Reihenfolge:** Der Boden-Test soll mit dem **finalen,
schürffreien** Aufstehen laufen — nicht mit dem joint-space-Schürf-Aufstehen.
Also muss das bessere Aufstehen **vor** dem Boden-Test fertig sein → es schiebt
sich als neue 0.7 davor, der Boden-Test rückt auf 0.8.

**Konkrete Edits beim Tausch (NICHT jetzt):**
1. `phase_13_stage_0_plan.md` §6-Tabelle: 0.7-Zeile = kartesisch, 0.8-Zeile = Boden.
2. Diese Datei umbenennen `…_stage_0_8_…` → `…_stage_0_7_…`, Bullets X.→0.7.
3. Boden-Test-Plan/test_commands auf 0.8 anlegen.
4. `phase_13_stage_0_progress.md` + DL-Log entsprechend.

## 10. Aufwand-Einschätzung

**Eine Stage mit ~10 Bullets**, durchläuft die volle Kette Logik→Sim→HW
(weil last-tragend + neue Sicherheits-Beweise D). **Keine** ganze Phase: kein
neues Paket, keine neue Architektur, keine Geometrie-/HW-Änderung — lokalisiert
in `gait_engine.py` + `trajectory_gen.py`, nutzt vorhandene IK. Kern-Risiko +
Hauptarbeit liegt in **B** (Touchdown-Design) und **D** (Reachability/In-Limits-
Beweis, der den eleganten 0.4-Monotonie-Beweis ersetzen muss).

## 11. Cross-References
- Befund: `phase_13_stage_0_progress.md` 0.5-Final-Review (F-Scrape), Memory
  `project_phase13_standup_foot_scrape`
- Tabu: `phase_13_stage_0_5_sim_standup_plan.md` §7.7 (URDF-Geometrie),
  0.4 DL-7 (all-6 vs Tripod)
- Code: [`gait_engine.py`](../src/hexapod_gait/hexapod_gait/gait_engine.py)
  (STARTUP_RAMP, compute_joint_angles) ·
  [`trajectory_gen.py`](../src/hexapod_gait/hexapod_gait/trajectory_gen.py)
  (stand_pose/swing_traj) · [`leg_ik.py`](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py)
  (leg_ik/leg_fk) · `tools/walking_envelope_check.py` (Envelope-Tool-Vorlage)
