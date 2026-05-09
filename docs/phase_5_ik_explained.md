# Inverse + Forward Kinematics pro Bein — Konzept-Hintergrund

> **Lesehinweis:** Dieses Dokument erklärt das IK-Konzept hinter
> [hexapod_kinematics](../src/hexapod_kinematics/) im Detail — gedacht
> als Nachschlagewerk für Stufen C-H von Phase 5 und alle weiteren
> Phasen, in denen IK-Verhalten zur Frage wird (Gait-Tuning, neue
> Bein-Geometrie, Hardware-Port).

> Komplementär zu [phase_5_progress.md](phase_5_progress.md) (Was-wurde-
> wann-gemacht-Tracker) und [phase_5_kinematics_gait.md](phase_5_kinematics_gait.md)
> (Phasenplan).

---

## Problemstellung

**Eingabe:** Wunsch-Foot-Position eines Beins, gegeben als `(x, y, z)` im
**Bein-Frame** (siehe unten). Einheit: Meter.

**Ausgabe:** Joint-Winkel `(θ_coxa, θ_femur, θ_tibia)` in Radiant, die das
Bein in genau diese Foot-Position bringen — in **URDF-Konvention** (siehe
unten).

**Modell:** Drei serielle Drehgelenke pro Bein. coxa rotiert um Z, femur und
tibia rotieren um Y. Drei Bein-Segmente mit fixen Längen
(`L_coxa, L_femur, L_tibia` aus [config.py](../src/hexapod_kinematics/hexapod_kinematics/config.py)).

**Lösungsweg:** Geschlossene Form (analytisch lösbar), kein numerischer
Solver nötig. Alle Schritte sind Skalar-Math (`atan2`, `acos`, `sqrt`,
`hypot`). Pure Python, keine numpy-Dependency.

---

## Bein-Frame-Konvention

Der Bein-Frame ist das lokale Koordinatensystem, in dem die IK arbeitet.
Eine Frame pro Bein, alle 6 mechanisch identisch ausgerichtet:

- **Origin**: Position des `coxa_joint` des Beins in `base_link`. In der
  URDF aus den Mount-Parametern in [hexapod.urdf.xacro](../src/hexapod_description/urdf/hexapod.urdf.xacro)
  abgeleitet (`mount_xyz` pro Bein, gespiegelt in
  [config.py::LegConfig.mount_xyz](../src/hexapod_kinematics/hexapod_kinematics/config.py)).
- **Rotation**: Z-Achse identisch zu base_link, X-Y-Ebene um `mount_yaw`
  rotiert (z. B. `-π/4` für Bein 1).
- **+X**: zeigt **radial nach außen vom Body weg**. Bei allen Joints = 0
  zeigt das ausgestreckte Bein in diese Richtung.
- **+Z**: parallel zu base_link-Z, zeigt nach oben.
- **+Y**: rechtshändig komplettiert das System.

**Konsequenz:** Da alle 6 Beine mechanisch identisch sind und sich nur in
`mount_xyz` und `mount_yaw` unterscheiden, ist die IK-Math **für alle Beine
identisch**. Die Spiegelung links/rechts steckt ausschließlich in
`mount_yaw`. Test
[test_all_legs_identical_ik](../src/hexapod_kinematics/test/test_leg_ik.py)
macht das explizit.

**Frame-Konvertierung** zwischen base_link und Bein-Frame:
[geometry.py](../src/hexapod_kinematics/hexapod_kinematics/geometry.py) —
`base_to_leg_frame` (für IK-Eingabe), `leg_to_base_frame` (für
Debug/Anzeige).

---

## Joint-Drehrichtungs-Konvention (URDF)

Aus [leg.xacro](../src/hexapod_description/urdf/leg.xacro):

| Joint | Achse | Positive Rotation bewirkt |
|---|---|---|
| `leg_<n>_coxa_joint` | `+Z` | Coxa-Segment rotiert CCW (von oben gesehen) — Foot schwenkt im Uhrzeigersinn um die Z-Achse zur +Y-Seite |
| `leg_<n>_femur_joint` | `+Y` | Femur-Segment rotiert von +X zu **-Z**, also **nach UNTEN** |
| `leg_<n>_tibia_joint` | `+Y` | Tibia knickt **weiter nach unten** relativ zur Femur-Richtung |

**Right-hand-rule** für die Femur/Tibia-Rotation: Daumen entlang +Y,
Finger zeigen Rotationsrichtung. `Ry(θ) · (1, 0, 0) = (cos θ, 0, -sin θ)` —
positive Rotation um +Y dreht +X nach -Z.

**Konsequenz für die Stand-Pose** `[θ_coxa=0, θ_femur=-0.5, θ_tibia=+1.0]`:
- coxa = 0: Bein zeigt entlang +X (nach außen, kein Schwenk).
- femur = -0.5: **negative** Rotation = Bein dreht **nach OBEN**
  (Knie hebt sich).
- tibia = +1.0: positive Rotation = Tibia knickt **nach UNTEN** relativ
  zur Femur-Richtung. Foot kommt zum Boden zurück.

Klassische "Knie oben"-Hexapod-Stand-Pose (siehe nächster Abschnitt).

---

## "Knie oben"-Konvention

Bei einer 2-Link-Arm-IK (Femur + Tibia) gibt es für jeden erreichbaren
Foot **zwei Lösungen**: das Knie kann oben oder unten vom Foot-Linie
sein. Mathematisch erscheinen sie als die zwei Vorzeichen von `β` im
Cosinus-Satz.

**Knie oben (gewählt):**
- Femur kippt nach oben.
- Tibia knickt von dort wieder nach unten zum Foot.
- Knie liegt höher als die Linie Coxa-Joint→Foot.
- Stand-Pose: `θ_femur ≈ -0.5`, `θ_tibia ≈ +1.0`.

**Knie unten (verworfen):**
- Femur kippt nach unten — durch den Boden, mechanisch absurd.
- Tibia knickt zurück nach oben zum Foot.
- Knie liegt unter der Foot-Linie, kollidiert mit Boden.
- Sinnvoll nur für inverse Roboter (Spinne unter einer Decke); kein
  Anwendungsfall für unseren Hexapod.

**Implementiert:** Hardcoded Knie oben. Code in
[leg_ik.py::leg_ik](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py)
verwendet `θ_femur = α - β`, `θ_tibia = +acos(...)` (immer positiv).

**Falls Knie unten je nötig:** 5 Code-Zeilen-Erweiterung —
`knee_up: bool = True`-Parameter in `leg_ik`, der bei `False`
Vorzeichen invertiert. Stufe-B-Design-Entscheidung 3 in
[phase_5_progress.md](phase_5_progress.md).

---

## IK-Schritte (geschlossene Form)

```
Eingabe: foot = (x, y, z) im Bein-Frame
         leg_cfg mit L_coxa, L_femur, L_tibia
Ausgabe: (theta_coxa, theta_femur, theta_tibia)
```

**Schritt 1 — Coxa-Schwenk:**
```
theta_coxa = atan2(y, x)
```
Coxa rotiert das Bein in der XY-Ebene zum Foot-Azimut.

**Schritt 2 — In die Bein-Ebene wechseln:**
```
r_total = sqrt(x² + y²)        # horizontale Distanz vom coxa_joint
r       = r_total - L_coxa     # ... vom femur_joint (entlang rotierter +X)
```
Nach diesem Schritt rechnen wir in der durch coxa rotierten X-Z-Ebene mit
Foot bei `(r, z)` relativ zu femur_joint.

**Schritt 3 — Direkte Distanz Femur-Joint → Foot:**
```
d = sqrt(r² + z²)
```

**Schritt 4 — Reichweiten-Check:**
```
cos_θ_tibia = (d² - L_femur² - L_tibia²) / (2 · L_femur · L_tibia)
if cos_θ_tibia ∉ [-1, 1]: raise IKError
```
Außerhalb `[-1, 1]` heißt: kein Dreieck mit den Seitenlängen
`(L_femur, L_tibia, d)` möglich. Foot ist entweder zu weit
(`d > L_f + L_t`) oder zu nah (`d < |L_f - L_t|`).

**Schritt 5 — Tibia-Knickwinkel:**
```
theta_tibia = acos(cos_θ_tibia)     # in [0, π], Knie-oben-Konvention
```

**Schritt 6 — Femur-Hubwinkel:**
```
α    = atan2(-z, r)                            # Foot-Linie über Horizontale
β    = acos((L_femur² + d² - L_tibia²) / (2·L_femur·d))   # Innenwinkel im Dreieck
theta_femur = α - β                            # URDF-Konvention
```

**Warum `α - β`?** In Standard-Mathematik (Math-Winkel CCW um +Y) wäre
der Femur-Winkel `α + β` (Femur kippt um β über die Foot-Linie nach
oben). URDF-Konvention dreht Vorzeichen (positiv = nach unten), also
negieren: `θ_femur = -(α_math + β)`. Mit `α = atan2(-z, r) = -α_math` für
`z < 0` ergibt das `θ_femur = α - β`.

**Verifikation Stand-Pose** (siehe
[test_neutral_pose_phase4_handover](../src/hexapod_kinematics/test/test_leg_ik.py)):
- `foot = leg_fk(0, -0.5, 1.0)` → ≈ `(0.27, 0, -0.047)` im Bein-Frame.
- `leg_ik(0.27, 0, -0.047)` → `(0, -0.5, 1.0)` ± 1e-9. ✅

---

## FK als Inversen-Verifikation

[leg_fk](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py) berechnet
die Foot-Position aus den Joint-Winkeln (Forward-Kinematics). Aus der URDF-
Joint-Origin-Kette:

```
foot = R_z(θ_coxa) · [
  (L_coxa, 0, 0)                                         # coxa-Segment
  + L_femur · (cos(θ_femur), 0, -sin(θ_femur))           # femur-Segment
  + L_tibia · (cos(θ_femur+θ_tibia), 0, -sin(θ_femur+θ_tibia))   # tibia-Segment
]
```

(Femur und Tibia drehen beide um +Y mit parallelen Achsen, also
addieren sich die Winkel zur globalen Tibia-Richtung in der
coxa-rotierten Ebene.)

**Wozu FK separat?** Pure-Python-Test ohne ROS. Wenn `FK(IK(p)) ≈ p`
für ein zufälliges Raster reachable Punkte, ist die IK
mathematisch korrekt. Vorzeichen-Bugs in IK (oder FK) würden den
Round-Trip brechen. Test
[test_fk_ik_roundtrip_random_grid](../src/hexapod_kinematics/test/test_leg_ik.py)
prüft das mit deterministischem RNG (`random.Random(42)`) über 50 Punkte.

---

## Edge-Cases und numerische Toleranz

### Voll gestreckte Pose (acos-Singularität)

Bei `foot = (L_coxa+L_femur+L_tibia, 0, 0)` ist `d = L_femur+L_tibia` exakt
und `cos_β_arg = 1.0`. Floating-Point-Drift kann das Argument minimal über
1.0 schieben → ohne Schutz `math.domain error`. Code hat zwei Schutz-Maßnahmen:
1. Reichweiten-Check toleriert `_COS_EPS = 1e-9` Überschießen vor IKError.
2. Vor `acos()` wird das Argument auf `[-1, 1]` geclampt.

Resultat: `acos(1.0) = 0`, aber bei FP-Drift entsteht `acos(1-ε) = sqrt(2ε)`,
also Joint-Winkel-Drift in der Größenordnung `sqrt(eps_machine) ≈ 1e-8`.
Für reale Hardware (Servos mit ~0.1° Auflösung = 1.7e-3 rad) **vollständig
irrelevant**. Test
[test_fully_extended](../src/hexapod_kinematics/test/test_leg_ik.py)
verwendet daher `abs=1e-6` Toleranz.

### Out-of-reach

Zwei Fälle:
- **Zu weit:** `d > L_femur + L_tibia`. Foot liegt außerhalb der
  Maximal-Reichweite. Beispiel: `foot = (1.0, 0, 0)`.
- **Zu nah:** `d < |L_femur - L_tibia|`. Foot liegt innerhalb der
  Minimal-Reichweite (Bein kann nicht so eng zusammenfalten).
  Beispiel: `foot = (L_coxa, 0, 0)` (direkt am femur_joint).

Beide werfen `IKError` (Subklasse von `ValueError`). Limits sind in
[leg_ik.py](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py)
explizit am Cosinus-Argument geprüft.

### Joint-Limit-Verletzung

**Wird NICHT von `leg_ik` geprüft** (Stufe-B-Design-Entscheidung 2:
Lenient). Begründung: IK ist Math-Funktion, Limit-Check ist
Controller-Verantwortung (Gait-Engine in Stufe G clampt Foot-Targets;
JTC clampt zusätzlich auf Hardware-Interface-Limits aus Phase 4).

**Falls strict-Verhalten je nötig:** Wrapper-Funktion `leg_ik_checked`
zusätzlich anlegen. Bestehende `leg_ik` bleibt lenient.

---

## Verwendung in der Gait-Engine (Vorschau Stufe E-G)

Pro 50-Hz-Tick:
```python
# 1) Foot-Target im base_link berechnen (Stützphase oder Schwungphase)
foot_in_base = compute_foot_target(leg_id, phase, cmd_vel)

# 2) Ins Bein-Frame transformieren
foot_in_bein = base_to_leg_frame(foot_in_base, leg_cfg)

# 3) IK
try:
    angles = leg_ik(*foot_in_bein, leg_cfg)
except IKError:
    # Foot-Target unmöglich -> Gait-Engine-Bug oder Parameter zu groß
    # In Stufe G: clampen auf Reachable-Range vor IK
    ...

# 4) Joint-Limits prüfen (Gait-Engine-Verantwortung)
clamped = clamp_to_limits(angles, leg_cfg)

# 5) Trajectory-Goal an JTC publishen
publish_trajectory(leg_id, clamped, time_from_start=0.05)
```

Stufe C verwendet diesen Flow vereinfacht (kein Phase, eine fixe
Neutral-Pose). Stufe D ergänzt periodische Schwung-Trajektorien für
ein Bein. Stufe F/G erweitern auf Tripod-Gait mit cmd_vel.

---

## Tests-Übersicht

| Datei | Tests | Was geprüft wird |
|---|---|---|
| [test_config.py](../src/hexapod_kinematics/test/test_config.py) | 7 | Cross-Check `config.py` ↔ xacro (Stufe A) |
| [test_geometry.py](../src/hexapod_kinematics/test/test_geometry.py) | 8 | rotate_z, base/leg-Frame-Konvertierung, Round-Trip pro Bein |
| [test_leg_ik.py](../src/hexapod_kinematics/test/test_leg_ik.py) | 10 | IK-Stützpunkte, Out-of-reach, Round-Trip-Raster, Symmetrie über alle 6 Beine |
| ament_flake8/pep257 | 2 | Code-Style |

Aufruf: `colcon test --packages-select hexapod_kinematics
--event-handlers console_direct+`. **Pure-Python**, kein ROS-Stack
nötig — die Tests laufen auch in einem isolierten venv mit nur
`pytest` installiert.

---

## Konventionen-Wiederholung

Aus [00_conventions.md](00_conventions.md) und Stufe-A/B-Design-Entscheidungen:

- Längen in Meter, Winkel in Radiant, SI durchgehend.
- Joint-Naming: `leg_<n>_{coxa,femur,tibia}_joint`.
- `base_link` mittig im Body, +X vorn, +Z oben (REP-103).
- Bein-Frame: Origin am coxa_joint, +X radial nach außen.
- Knie-Konvention: hardcoded Knie oben.
- IK-Errors: nur geometrisch out-of-reach, keine Joint-Limit-Prüfung.
- Library: pure Python (`math`-Modul), keine numpy-Dependency.

Bei Änderungen an Bein-Geometrie oder Joint-Limits siehe
[01_hardware_change_workflow.md](01_hardware_change_workflow.md).
