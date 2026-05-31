# Stage 0.7 — Kartesisches schürffreies Aufstehen: Entstehungs-/Verständnis-Doku

> Begleit-Dokument zum Plan `phase_13_stage_0_7_cartesian_standup_plan.md` und
> dem Progress-Tracker `phase_13_stage_0_progress.md`. Hier wird **erklärt**,
> *was* gemacht wurde, *warum*, *was gerechnet werden musste* und *wie getestet*
> wurde — mit kleinen Code-Ausschnitten. Ziel: die Stage nachvollziehbar machen.
> (Die maßgeblichen Verträge bleiben Plan + Progress; dies ist die Erzählung.)

---

## 0. TL;DR

Das alte Aufstehen interpolierte die **Gelenkwinkel** linear. Nebenwirkung: die
Füße wandern dabei ~15–22 mm nach innen → am Boden **Schürfen unter Last** →
>3,5 A Strom, Spannungseinbruch. Stage 0.7 ersetzt das durch ein **kartesisches**
Aufstehen in zwei Phasen: erst die Füße (bauch-gestützt, unbelastet) zum
Boden-Aufsetzpunkt bringen, dann den Körper **senkrecht** über den **fixen**
Füßen hochdrücken. „Senkrecht über fixen Füßen" = Fuß-x/y bleibt konstant → kein
Schürfen, by design. Die Endpose ist identisch zur alten — nur der *Weg* ist neu.

---

## 1. Das Problem (warum diese Stage überhaupt)

Die Aufsteh-Logik aus Stage 0.4 (`STARTUP_RAMP`) macht einen **Joint-Space-Lerp**:
sie nimmt die Start-Gelenkwinkel (power_on_mid) und die Ziel-Gelenkwinkel
(Stand-Pose) und interpoliert smooth dazwischen:

```python
# alt (Joint-Space): pro Joint linear interpolieren
angle = start_angle + (target_angle - start_angle) * s   # s = smoothstep(progress)
```

Das Problem: **Gleichmäßige Winkel-Interpolation heißt NICHT gleichmäßige
Fuß-Bewegung.** Die Vorwärtskinematik (FK) ist nichtlinear (Sinus/Cosinus), also
zeichnet der Fuß eine *gekrümmte* Bahn. Konkret (aus der FK gerechnet):

| | Fuß horizontal (rx) | Fuß vertikal (rz) |
|---|---|---|
| Start power_on_mid | 0,310 m | +0,078 m |
| Mitte | 0,317 m | +0,021 m |
| Ende Stand | 0,295 m | −0,080 m |

→ Der Fuß wandert in der belasteten zweiten Hälfte **~22 mm nach innen**. Am
Boden = Reibung × Weg × Körpergewicht = viel Strom.

**Der entscheidende Messwert (HW, Stage 0.6):** *Stehen* kostet nur **~400 mA**,
*Aufstehen* zieht **>3,5 A**. Da das Halten billig ist, ist der Aufsteh-Strom fast
nur **Schürf-Reibung** — nicht das Heben des Gewichts. Das war der Beweis, dass
ein schürffreier Weg das Problem an der Wurzel löst.

**Was wir NICHT gemacht haben:** die Tibia kürzen (User-Idee). Das wäre eine
URDF-Geometrie-Änderung (§7.7 TABU — bricht IK/FK/Kalibrierung) und hätte das
Schürfen nur verkleinert, nicht beseitigt. Per Mathe widerlegt, nicht per Bauch.

---

## 2. Die Idee: zwei Phasen

power_on_mid ist **keine** gültige „Stand-artige" Pose — die Füße sind
eingezogen, *über* der Coxa-Achse (rz = +0,078 m). Man kann also nicht einfach
„body_height runterrampen". Daher zwei Phasen:

```
Phase 1 — TOUCHDOWN (bauch-gestützt):
    Füße von power_on_mid kartesisch nach unten zu den Aufsetzpunkten
    (radial, 0, body_height_start). Bauch trägt → Füße unbelastet → keine Reibung.

Phase 2 — PUSH (Füße fix):
    x+y bleiben fix am Aufsetzpunkt, nur z (= body_height) rampt zu -0.080.
    Körper hebt senkrecht über den Füßen → kein Schürfen unter Last.
```

**Design-Regel (verhindert einen Komplexitätssprung):** Alle Fuß-Platzierung
passiert in **Phase 1, solange der Bauch trägt**. In Phase 2 wird **kein** Fuß
mehr versetzt — nur senkrecht gedrückt. Würde man Füße umsetzen *nachdem* der
Bauch abgehoben hat, bräuchte man statische Stabilität (Tripod 3+3). Das umgehen
wir komplett.

---

## 3. Die Mathe (was berechnet werden musste)

### 3.1 `body_height_start` — wie tief sitzt der Körper auf dem Bauch?

Die Bauch-Kollisionsbox ist 0,043 m hoch, die Coxa-Achse sitzt mittig
(`leg_mount_z = 0`). Liegt der Bauch auf, ist die Coxa also `0,043 / 2 = 21,5 mm`
über Grund. Der Fuß (Kugel, Radius 8 mm) berührt den Boden, wenn sein Zentrum bei
+8 mm Welt-Höhe ist. Im Bein-Frame (relativ zur Coxa) heißt das:

```
body_height_start = FOOT_RADIUS - coxa_höhe = 0.008 - 0.0215 = -0.0135 m
```

→ In Phase 2 rampt `body_height` von **−0,0135 m** (Bauch am Boden) nach
**−0,080 m** (Stand).

### 3.2 Vorwärtskinematik (FK): von Winkeln zur Fuß-Position

Um die Fuß-Bahn zu prüfen, braucht man `leg_fk` (im Bein-Frame, x-z-Ebene):

```python
rx = L_coxa + L_femur*cos(θf) + L_tibia*cos(θf + θt)   # horizontale Reichweite
rz = -L_femur*sin(θf) - L_tibia*sin(θf + θt)            # vertikal (− = unter Coxa)
```

Mit `L_coxa=0.0436, L_femur=0.07994, L_tibia=0.200`. Diese Funktion existiert
bereits (`hexapod_kinematics.leg_fk`) — wir haben sie genutzt, **nicht** neu
gerechnet.

### 3.3 Warum Phase 2 stromgünstig ist (Hebelarm-Argument)

Das Stütz-Drehmoment am Femur-Gelenk ist proportional zum **horizontalen
Hebelarm** Fuß→Femur-Achse = `rx − L_coxa`. In Phase 2 ist `rx = radial = 0,295`
**konstant** → der Hebelarm bleibt konstant `0,251 m` über den ganzen Hub. Da der
Stand bei genau diesem `rx` nur 400 mA zieht, bleibt das Drehmoment (und damit der
Strom) über das gesamte Aufstehen auf Stand-Niveau. **Kein Drehmoment-Peak.**

Außerdem: die **Knie-Beugung** bleibt 43°→58° (0° wäre voll gestreckt =
Singularität = unendliches Drehmoment). Also weit weg von der Singularität.

---

## 4. Das Offline-Tool (Validierung VOR dem Code)

Bevor eine Zeile Engine-Code angefasst wurde, haben wir den ganzen Aufsteh-Pfad
rein rechnerisch geprüft: `tools/standup_envelope_check.py`. Es nutzt die **echte**
`leg_ik`/`leg_fk` + die **echten** URDF-Limits (via xacro geladen) — keine
Parallel-Mathe.

Es prüft pro Bein, über beide Phasen, an vielen Stützstellen:
- ist jede Zwischen-Pose **innerhalb der Gelenk-Limits** und **erreichbar**?
- bleibt der Fuß in **Phase 1 über dem Boden** bis zum Touchdown (kein
  vorzeitiges Schürfen)?
- wie eng ist die Reserve zum nächsten Limit?

Ergebnis: **GRÜN** für alle 6 Beine, `body_height_start = −13,5 mm`, Phase 1
direkter Lerp reicht (kein Bogen nötig), limitierend ist die Tibia mit ~8°
Reserve. Damit waren die offenen Design-Fragen (§8 im Plan) **datengetrieben**
beantwortet, statt geraten.

> Lehre aus früheren Stages: erst Hypothese per Code/Mathe falsifizieren, dann
> bauen. Das Tool ist genau dieser Schritt.

---

## 5. Die Engine-Änderungen (`gait_engine.py`)

Die Gait-Engine war schon **durchgängig kartesisch** (Walking erzeugt Fuß-Targets
→ IK). Nur das Aufstehen war der Joint-Space-Sonderfall. Also war der Umbau
lokal: ein neuer State + zwei Methoden.

### 5.1 Neuer State

```python
STATE_CARTESIAN_STANDUP = 'CARTESIAN_STANDUP'
```

### 5.2 `start_cartesian_standup(...)` — die Targets vorbereiten

Beim ersten `/joint_states`-Empfang wird die gemessene Start-Pose via `leg_fk` in
kartesische Fuß-Targets übersetzt und die drei Eckpunkte pro Bein gespeichert:

```python
for leg in HEXAPOD.legs:
    touchdown = (self.radial_distance, 0.0, body_height_start)   # Boden-Aufsetzpunkt
    start_foot = leg_fk(*start_joints[leg.name], leg)            # power_on_mid → kartesisch
    self._cart_start_foot[leg.name] = start_foot
    self._cart_touchdown[leg.name]  = touchdown
    self._cart_push_end[leg.name]   = stand_pose(self.radial_distance, self.body_height)
self._state = self.STATE_CARTESIAN_STANDUP
```

### 5.3 `_compute_cartesian_standup_angles(t)` — der Tick

Pro Engine-Tick wird je nach Fortschritt die Phase gewählt und ein Fuß-Target
gerechnet, dann per IK in Winkel übersetzt:

```python
progress = (t - self._cart_start_t) / self._cart_duration
if progress >= 1.0:
    self._state = self.STATE_STANDING
    return self._cartesian_standup_ik(self._cart_push_end, t)   # Endpose = Stand-Pose

p1 = self._cart_phase1_frac                # z.B. 0.4
for leg in HEXAPOD.legs:
    touchdown = self._cart_touchdown[leg.name]
    if progress < p1:                      # --- PHASE 1: Touchdown ---
        s = smoothstep(progress / p1)
        targets[leg.name] = _lerp(self._cart_start_foot[leg.name], touchdown, s)
    else:                                  # --- PHASE 2: Push ---
        s = smoothstep((progress - p1) / (1.0 - p1))
        end = self._cart_push_end[leg.name]
        z = touchdown[2] + (end[2] - touchdown[2]) * s
        targets[leg.name] = (touchdown[0], touchdown[1], z)   # x,y FIX, nur z!
return self._cartesian_standup_ik(targets, t)
```

Der Kern der Schürf-Freiheit steht in der `else`-Zeile: in Phase 2 werden nur
`touchdown[0]` (= radial) und `touchdown[1]` (= 0) **unverändert** durchgereicht,
und nur `z` interpoliert. Damit kann sich die Fuß-x/y-Position gar nicht ändern.

### 5.4 Anbindung: Dispatcher + cmd_vel ignorieren

```python
# compute_joint_angles(): neuer Zweig
if self._state == self.STATE_CARTESIAN_STANDUP:
    return self._compute_cartesian_standup_angles(t)

# set_command(): während des Aufstehens kein Walking starten
if self._state in (self.STATE_STARTUP_RAMP, self.STATE_CARTESIAN_STANDUP):
    return False
```

`_cartesian_standup_ik` ruft pro Bein `leg_ik` und wirft bei Limit-/Reach-Fehler
einen `IKError` **mit Bein-Kontext** — denselben Pfad, den der `gait_node._tick`
schon abfängt (→ `/hexapod_safety_freeze`). Kein neues Crash-Risiko.

---

## 6. Die gait_node-Integration (`gait_node.py`)

Drei neue Parameter (live-justierbar, nur in STANDING):

| Param | Default | Bedeutung |
|---|---|---|
| `standup_mode` | `cartesian` | `cartesian` (neu) oder `joint_space` (Legacy-Ramp) |
| `standup_phase1_fraction` | `0.4` | Anteil Phase 1 (Touchdown) an der Gesamtdauer |
| `body_height_start` | `-0.0135` | Coxa-Höhe bei aufliegendem Bauch |

Der Trigger beim ersten `/joint_states` wählt den Modus:

```python
if self._standup_mode == 'cartesian':
    self._engine.start_cartesian_standup(start_joints, t, self._auto_standup_duration,
                                         self._standup_phase1_fraction, self._body_height_start)
else:
    self._engine.start_ramp(start_joints, t, self._auto_standup_duration)   # Legacy
```

Dazu kam die Param-Validierung (`standup_mode` muss `cartesian|joint_space` sein,
analog zur bestehenden `gait_pattern`-Prüfung) und das Live-Apply.

---

## 7. Die Tests (`test_cartesian_standup.py`, 17 Stück)

Beim Joint-Space-Ramp war „in-limits" trivial: zwischen zwei in-limit-Endpunkten
liegt monoton alles dazwischen auch in-limits. **Bei kartesisch gilt das nicht
mehr** — die IK kann zwischendrin an Limits oder Reichweite stoßen. Also muss der
ganze Pfad explizit getestet werden:

- `path_in_limits` — jede Zwischen-Pose × 18 Joints ∈ URDF-Limits.
- `reachable_no_ikerror` — mit aktiven Limits wirft der Pfad keinen IKError.
- `phase2_foot_xy_constant` — **der Schürf-frei-Beweis**: in Phase 2 ist die
  radiale Fuß-Position konstant (< 1e-6). Gerechnet über `leg_fk` aus den
  Winkeln zurück zur Fuß-Position.
- `phase1_no_premature_ground_contact` + `touchdown_reaches_ground`.
- `endpoint_is_stand_pose`, `handover-stetig`, `cmd_vel-ignore`, Param-Validierung.

**Eine physikalische Feinheit, die in die Tests einfloss:** *Welcher Punkt ist
fix?*
- **Phase 1**: der Bauch trägt → die **Coxa** ist fix (21,5 mm über Boden), der
  Fuß fällt. Also gilt der „kein vorzeitiger Bodenkontakt"-Test (Fuß-Welt-z =
  `coxa_höhe + rz` muss ≥ Foot-Radius bleiben) nur hier.
- **Phase 2**: der Fuß ist am Boden fix → die Coxa hebt. Hier gilt stattdessen
  „Fuß-x/y konstant".

Diese Unterscheidung ist wichtig, sonst testet man die falsche Größe.

---

## 8. Stolpersteine / Fixes (was nicht auf Anhieb ging)

| Problem | Ursache | Fix |
|---|---|---|
| rclpy lehnt `body_height_start=-0.0135` ab | FloatingPointRange-Step war `0.001` → −0,0135 liegt nicht auf dem Raster (zwischen −0,013 und −0,014) | Step auf `0.0005` verfeinert |
| `pep257 D205` | Docstring hatte keine Leerzeile zwischen Summary und Beschreibung | Summary-Zeile + Leerzeile eingefügt |
| `E501` Zeile zu lang | Docstring 82 > 79 Zeichen | gekürzt |
| Smoke-Test fand Methode nicht | installiertes Paket war alte Version | `colcon build` vor dem Test |

Alle Fixes verifiziert: **colcon test 61/0/1-skip**, flake8/pep257/param_callback grün.

---

## 9. Geänderte/neue Dateien (Übersicht)

| Datei | Art | Inhalt |
|---|---|---|
| `tools/standup_envelope_check.py` | **neu** | Offline-Kinematik-Check (Paket E) |
| `src/hexapod_gait/hexapod_gait/gait_engine.py` | geändert | State + 2 Methoden + Dispatcher + cmd_vel |
| `src/hexapod_gait/hexapod_gait/gait_node.py` | geändert | 3 Params + Trigger-Switch + Validierung |
| `src/hexapod_gait/test/test_cartesian_standup.py` | **neu** | 17 Tests |
| `src/hexapod_gait/README.md` | geändert | CARTESIAN_STANDUP-Abschnitt |
| `docs_raspi/phase_13_stage_0_7_*` + `phase_13_stage_0_progress.md` | Doku | Plan §5a/§8, Checkliste, Code-Self-Review |

**Was NICHT angefasst wurde:** die URDF-Geometrie, die IK/FK-Formeln, das
HW-Plugin, der Joint-Space-Ramp (bleibt als Legacy-Modus). Lokaler Eingriff,
große Wirkung.

---

## 10. Was jetzt offen ist (du testest es)

Die Mathematik + Logik sind bewiesen (pure-Python). Was die Tests **nicht**
zeigen können — und du in Sim/HW prüfst:

- **0.7.7 Sim**: steht der Roboter in Gazebo jetzt **kartesisch** auf? Stehen die
  Füße in Phase 2 sichtbar **senkrecht** (kein Einwärts-Schürfen mehr)? Passt
  `body_height_start` zur Sim-Bauch-Auflage?
- **0.7.8 HW aufgebockt**: saubere Bewegung (Achtung: aufgebockt fahren die Füße
  „zum Boden" der nicht da ist → ggf. `standup_mode:=joint_space` zum Vergleich).
- **0.7.9 HW Boden + Strom-Logging**: **das eigentliche Done-Kriterium** —
  Aufsteh-Strom nahe Stand-Niveau (~400 mA) statt >3,5 A, kein Trip/Spannungseinbruch.

Kurz: „kinematisch korrekt" ist bewiesen, „spart wirklich Strom" misst erst der
Boden-Test.
