# Gait-Engine — Konzept-Hintergrund

> **Lesehinweis:** Dieses Dokument erklärt das Gait-Konzept hinter
> [hexapod_gait](../src/hexapod_gait/) im Detail — gedacht als
> Nachschlagewerk für Phase 6/7 (Teleop, HW-Port) und für künftige
> Erweiterungen (Wave, Ripple, dynamische Gangarten in Phase 8+).
>
> Komplementär zu [phase_5_ik_explained.md](phase_5_ik_explained.md)
> (IK-Math), [phase_5_progress.md](phase_5_progress.md) (Was-wurde-
> wann-gemacht-Tracker) und [phase_5_kinematics_gait.md](phase_5_kinematics_gait.md)
> (Phasenplan).

---

## Was das Modul tut

Aus einem Twist-Befehl `(linear.x, linear.y, angular.z)` und einer
**Gangart-Definition** (welche Beine wann schwingen) erzeugt die
Engine pro Tick (50 Hz) für jedes der 6 Beine eine Foot-Position im
Bein-Frame. IK aus
[hexapod_kinematics](../src/hexapod_kinematics/) macht daraus Joint-
Winkel, die als `JointTrajectory` an die JTC-Controller publiziert
werden.

**State-Machine** verhindert, dass cmd_vel-Glitches den Roboter
abrupt durcheinanderbringen: STANDING ↔ WALKING ↔ STOPPING mit
sauberem Settling.

---

## Layered Architecture

```
┌────────────────────────────────────────────────────────────┐
│ gait_node.py        — ROS-Glue: cmd_vel sub, 50 Hz Timer   │
│   ├── _on_cmd_vel   — Twist (linear.xyz, angular.z) cachen │
│   ├── _resolve_cmd  — Activity-Timeout + default_*-Fallback│
│   └── _tick         — engine.set_command + IK + Pubs       │
├────────────────────────────────────────────────────────────┤
│ gait_engine.py      — Pure-Python State-Machine            │
│   ├── set_command   — clamping + state transitions         │
│   ├── compute_foot_targets — STANDING/WALKING/STOPPING     │
│   └── _compute_step_vec_leg — Body→Bein-Frame mapping      │
├────────────────────────────────────────────────────────────┤
│ gait_patterns.py    — GaitPattern (Daten-Struktur)         │
│   ├── TRIPOD        — {1,3,5}@0.0  {2,4,6}@0.5  duty=0.5   │
│   ├── SINGLE_LEG_*  — 6 Stufe-E-Backward-Compat-Presets    │
│   └── (extensible)  — Wave, Ripple, ... 5-Zeilen-Patches   │
├────────────────────────────────────────────────────────────┤
│ trajectory_gen.py   — Reine Math, kein State              │
│   ├── stand_pose    — neutrale Foot-Position               │
│   ├── swing_traj    — Halbsinus + linear in Bein-Frame     │
│   └── stance_traj   — linear in Bein-Frame, Z=body_height  │
├────────────────────────────────────────────────────────────┤
│ hexapod_kinematics  — IK + Frame-Helfer (siehe IK-Doku)    │
└────────────────────────────────────────────────────────────┘
```

**Layering-Prinzip:** untere Layer haben keine Dependencies auf
obere. `trajectory_gen` und `gait_patterns` sind reine Daten/Math.
`gait_engine` koordiniert State + Patterns + Trajectories. `gait_node`
ist die einzige Schicht mit `import rclpy`.

---

## Gait-Pattern als Daten

Die zentrale Architektur-Entscheidung in Stufe F: **alle realistischen
statischen Gangarten unterscheiden sich nur in zwei Werten** — der
Phasen-Offset-Tabelle pro Bein und der Swing-Duty.

```python
@dataclass(frozen=True)
class GaitPattern:
    name: str
    phase_offset_per_leg: dict[int, float | None]  # None = nie schwingen
    swing_duty: float  # Anteil des Cycles in Swing
```

| Gangart | Phasen-Offsets | Swing-Duty | Beine simultan in der Luft |
|---|---|---|---|
| Tripod | `{1:0, 3:0, 5:0, 2:.5, 4:.5, 6:.5}` | 0.5 | 3 von 6 |
| Wave | `{1:0, 2:1/6, 3:2/6, 4:3/6, 5:4/6, 6:5/6}` | 1/6 | 1 von 6 |
| Ripple | `{1:0, 4:1/3, 5:2/3, 2:0, 3:1/3, 6:2/3}` | 1/3 | 2 von 6 |
| Single-Leg-N | `{N: 0}` (others None) | 0.5 | 1 (nur Bein N) |

Der Engine-Algorithmus ist für alle Patterns identisch:

```python
phase_in_leg_cycle = ((t / cycle_time) + offset[leg_id]) % 1.0
if phase_in_leg_cycle < swing_duty:
    foot_target = swing_traj(...)
else:
    foot_target = stance_traj(...)
```

**Konsequenz:** neue Gangart = neue Pattern-Konstante + Eintrag in
`GAIT_PRESETS`. Engine-Code wird **null** angefasst. Phase-8-Wave-
Erweiterung kostet 5 Zeilen.

---

## Body-Frame ↔ Bein-Frame Mapping (Stufe G+H)

Der Twist-Befehl ist im `base_link`-Frame. Jedes Bein hat ein eigenes
lokales Koordinatensystem (Bein-Frame), das per `mount_yaw` rotiert
ist. Die Engine muss pro Bein:

1. Die **Body-Velocity am Bein-Mount-Punkt** berechnen — bei pure
   Translation gleich für alle Beine, bei Rotation pro Bein
   unterschiedlich.
2. Diese Velocity in den **Bein-Frame rotieren**.
3. Daraus den **Schritt-Vektor** für das Cycle ableiten.

### Schritt 1: Body-Velocity am Mount-Punkt (Rigid-Body-Formel)

Für einen starren Körper, der sich mit `(vx, vy, 0)` translatiert UND
mit `omega` um die Z-Achse rotiert, ist die Velocity an einem Punkt
`P = (mount_x, mount_y, 0)` im Body-Frame:

```
v_at_mount = v_center + omega × P
            = (vx, vy, 0) + (0, 0, omega) × (mount_x, mount_y, 0)
            = (vx - omega·mount_y, vy + omega·mount_x, 0)
```

Das ist das 2D-Cross-Produkt mit z-only Rotation. Implementation in
`_compute_step_vec_leg`:

```python
mx, my, _ = leg.mount_xyz
vx_at_mount = v_body_x - omega * my
vy_at_mount = v_body_y + omega * mx
```

### Schritt 2: Rotation in Bein-Frame

Bein-Frame +X zeigt radial nach außen, ist also gegenüber base_link
um `mount_yaw` rotiert. Velocity-Vektor von base_link nach Bein-Frame:

```python
v_in_leg_frame = rotate_z((vx_at_mount, vy_at_mount, 0), -leg.mount_yaw)
```

Negativer Yaw, weil wir in den **rotierten** Frame transformieren
(inverse Rotation des Frames = umgekehrtes Vorzeichen).

### Schritt 3: Schritt-Vektor pro Cycle

Der Schritt-Vektor ist die **Body-Versetzung im Bein-Frame über die
Stance-Dauer**:

```python
step_vec_leg = (v_in_leg_frame[0] * stance_duration,
                v_in_leg_frame[1] * stance_duration)
```

Vorzeichen ist **positiv** — entspricht der Body-Bewegung in
Bein-Frame-Koordinaten. Die Foot-Bewegung ist die Inverse, das wird
implizit durch die Plus/Minus-Symmetrie in `swing_traj` und
`stance_traj` erzeugt:

- `stance_traj`: Foot von `+step_vec/2` nach `-step_vec/2` (Body
  bewegt sich vorwärts → Foot trailt hinten).
- `swing_traj`: Foot von `-step_vec/2` nach `+step_vec/2` (Foot setzt
  vorne wieder auf, gleicher Punkt wo Stance der nächsten Phase
  beginnt).

**Stufe-G-Bug-Lehre:** initial war ein Sign-Fehler drin (`-v_leg *
stance_duration`), gefangen in Pure-Python-Smoke-Test vor Live-Sim.
Bei umgekehrtem Vorzeichen wäre der Roboter rückwärts gelaufen.

---

## Trajektorien

### Swing (Halbsinus + Linear)

Im Bein-Frame, Phase 0..1:

```
x(phase) = (radial - dx/2) + dx · phase
y(phase) = -dy/2          + dy · phase
z(phase) = body_height + step_height · sin(π · phase)
```

- `phase = 0` → Foot am Touchdown der vorherigen Stance (`-step/2`).
- `phase = 0.5` → Apex (Höhe = body_height + step_height, Position
  mittig).
- `phase = 1` → Touchdown der neuen Stance (`+step/2`).

Halbsinus ist gewählt weil `sin'(0) = sin'(π) = 0` → Touchdown ohne
vertikale Geschwindigkeit, kein Bounce. Stufe-E-Designentscheidung.

### Stance (Linear)

Im Bein-Frame, Phase 0..1:

```
x(phase) = (radial + dx/2) - dx · phase
y(phase) = dy/2            - dy · phase
z(phase) = body_height                       (konstant)
```

Foot bewegt sich linear von `+step/2` nach `-step/2` während der
Stance-Dauer. Body bewegt sich entsprechend vorwärts. In Sim **mit
JTC-Tracking-Lag-Korrektur** durch `body_height = -0.052` (5 mm
unterhalb Boden), sonst kein sicherer Foot-Boden-Kontakt — Stufe-F-
Designentscheidung.

---

## State-Machine

### States

- **STANDING**: alle 6 Beine in Stand-Pose `(radial, 0, body_height)`,
  kein Cycle. Ausgabe ist statisch.
- **WALKING**: Pattern-Logik aktiv, Foot-Targets pro Tick aus
  `swing_traj` oder `stance_traj` mit aktueller `step_vec_leg`.
- **STOPPING**: Sauberer Übergang zu STANDING. Beine in Swing
  schwingen mit eingefrorener step_vec fertig (max 1 s bei
  cycle_time=2). Stütz-Beine interpolieren in 0.3 s zu Neutral.

### Übergänge

```
STANDING ──cmd_vel(|v_at_leg|>eps)──► WALKING
WALKING  ──cmd_vel(|v_at_leg|<eps)──► STOPPING
STOPPING ──auto: alle Beine settled──► STANDING
STOPPING ──cmd_vel(|v_at_leg|>eps)──► WALKING (sofort resume)
```

`|v_at_leg|` ist die maximale Bein-Mount-Velocity über alle 6 Beine
— bei pure Translation gleich `|cmd_vel.linear|`, bei Rotation
abhängig von `R_max` (~0.109 m bei unserer Hexapod-Geometrie).

`eps = 1e-4 m/s` — klein genug dass Float-Noise kein WALKING
triggert, groß genug dass User-Wert `0.001` nicht als Stopp
interpretiert wird.

### Stop-Logik im Detail (Stufe-G/H-Design)

Bei `WALKING → STOPPING` wird pro Bein eingefroren:

- `cycle_phase_at_stop[leg_id]` — Phase im Cycle zum Stop-Zeitpunkt.
- `stance_pos_at_stop[leg_id]` — Foot-Position bei Stop, falls Bein
  in Stance war (für Settling-Lerp).
- `_v_body_at_stop`, `_omega_at_stop` — eingefrorener Twist (für
  Schwung-Vollendung).

Während STOPPING (Zeit `tau = t - t_stop_start`):

- **Bein war in Swing**: weiter swingen mit eingefrorener step_vec.
  Wenn Swing-Phase=1 erreicht → Foot bei landed-Position →
  Linear-Interpolation zu Neutral über `_STANCE_SETTLING_TIME = 0.3 s`.
- **Bein war in Stance**: linear interpolieren von `stance_pos_at_stop`
  zu Neutral über 0.3 s.

Wenn alle Beine auf Neutral angekommen → automatisch State =
STANDING.

**Worst-Case-Latenz**: `swing_remaining + 0.3 s`. Bei cycle_time=2
und swing_duty=0.5: max 1 s + 0.3 s = 1.3 s. Bei cycle_time=1: max
0.5 s + 0.3 s = 0.8 s.

---

## Clamping (Stufe-H-Design)

Das Bein-Mount-Geschwindigkeits-Limit `linear_max = step_length_max
/ stance_duration` gilt **pro Bein**. Bei pure Translation ist es
gleichbedeutend mit `|cmd_vel.linear| ≤ linear_max`. Bei Rotation
hat jedes Bein eine andere Geschwindigkeit (Außen-Beine schneller),
und bei Kombi-Motion ist es Vektor-Summe.

**Proportionales Skalieren** wenn das schnellste Bein über Limit:

```python
max_speed = max(|v_at_leg_mount|) over all 6 legs
if max_speed > linear_max:
    scale = linear_max / max_speed
    v_body_x *= scale
    v_body_y *= scale
    omega_z *= scale
```

**Konsequenz:** User commandiert `(0.04, 0.02, 0.15)` (Schraubenkurve
mit kleinem Radius). Engine clampt alle drei gleichmäßig runter →
**gleiche Schraubenkurve, nur langsamer**. Bewegungs-Richtung bleibt
exakt erhalten.

Alternative wäre Pro-Achse-Clampen (`vx`, `vy`, `omega` getrennt) —
das verzerrt aber die Bewegungs-Richtung. Stufe-H-Design-Entscheidung 1
hat sich für proportional entschieden.

---

## Phasen-Sync zwischen Beinen einer Tripod-Gruppe

Bei Tripod schwingen Beine 1, 3, 5 synchron, dann 2, 4, 6. **In Sync**
heißt: zur gleichen Wall-Clock-Zeit haben alle drei den gleichen
`cycle_phase` und damit den gleichen Trajektorien-Wert.

Das entsteht automatisch aus der Pattern-Definition: alle drei
Gruppe-A-Beine haben `offset = 0.0`, alle Gruppe-B-Beine `offset =
0.5`. `cycle_phase = (t/cycle_time + offset) % 1.0` ist deterministisch
und gleicht innerhalb der Gruppe.

Live-Verifikation in Stufe F bestätigte: bei Gruppe A mid-stance
zeigen `leg_1_femur_joint`, `leg_3_femur_joint`, `leg_5_femur_joint`
identische Werte (im Float-Rauschen, ~1e-3 rad). Inter-Gruppen-
Differenz ist 0.124 rad bei body_height=-0.052 und step_height=0.03 —
das ist die IK-bedingte Höhen-Differenz zwischen Stand-Pose und Apex.

---

## JTC-Tracking-Lag-Workaround

Der `JointTrajectoryController` aus Phase 4 hat eine intrinsische
Tracking-Latenz: bei 50 Hz Continuous-Pubs mit
`time_from_start = 0.04 s` läuft der reale Joint-Wert ~0.5–1 mm hinter
dem Goal her. In Sim-Stand wäre das harmlos (Federung), im Walk
führt's zu Foot-knapp-überm-Boden-Effekten.

**Lösung**: alle Foot-Z-Targets sind **um 5 mm tiefer kommandiert** als
die nominelle Stand-Pose.

- Phase-4-Stand-Pose hatte `body_height = -0.047` m.
- Stufe-F-Default ist `body_height = -0.052` m (5 mm tiefer).

JTC trackt einen Punkt 5 mm unterhalb Boden, Boden gibt nicht nach →
Foot landet exakt auf Boden, kontinuierliche Penetration → Stufe-D-
Foot-Contact-Sensoren feuern zuverlässig. Symmetrisch über alle 6
Beine, kein Hebel-Problem.

**Phase-7-HW** entfernt diesen Workaround — echte Servos haben keinen
JTC-Lag, dann body_height zurück auf -0.047.

---

## Activity-Timeout & default_-Fallback

`gait_node` cached letzten cmd_vel-Empfang in `_last_cmd_time`.

```python
if (now - last_cmd_time) < cmd_vel_timeout:
    use cached (v_x, v_y, omega_z)
else:
    use (default_linear_x, default_linear_y, default_angular_z)
```

`cmd_vel_timeout = 0.5 s` aus Phase-5-Roadmap.

**Demo-Mode**: `default_linear_x = 0.05` setzt Roboter in dauerhaftes
Vorwärts ohne externen cmd_vel-Pub. Nützlich für Vorführung.

**Sicherheits-Aspekt**: wenn ein cmd_vel-Publisher abstürzt, fällt
Engine nach 0.5 s auf Defaults zurück. Bei `default_*=0` ist das
STANDING — der Roboter hört auf zu laufen. Wichtiger Sicherheits-
Mechanismus für Phase 6/7.

---

## Phase-5-Limitations und offene Punkte

### Yaw-Drift bei langen Strecken

Bei pure linear.x > 1 m läuft der Roboter mit ~1.35°/m Yaw-Drift.
Mögliche Ursachen:
- Foot-Friction-Asymmetrie zwischen den 6 Beinen (Sim-Materials).
- Mini-Asymmetrie im URDF (mount_yaw könnte Float-genau nicht
  perfekt symmetrisch sein).
- Sim-Physics-Integrations-Drift bei vielen Cycles.

**Phase-5-Scope:** akzeptiert für kurze Strecken (<1 m). In Phase 6
(Teleop) durch User-Korrektur mit cmd_vel kompensiert. Phase-8-
Closed-Loop-Yaw-Korrektur ist die saubere Lösung.

### DK-3-Latenz

Done-Kriterium 3 fordert `<0.5 s` Stopp-Latenz. Mit cycle_time=2 sind's
real 1.3 s, mit cycle_time=1 sind's 0.8 s. Strikt <0.5 s wäre nur mit
cycle_time=0.5 erreichbar — JTC würde dann aber kaum konvergieren.

**Bewertung:** Roadmap-DK relaxiert auf "<1.5 s" akzeptiert. Phase-7-HW
ist anders dimensioniert, dann neu zu bewerten.

### Static-only Gangarten

Engine kann aktuell nur statisch stabile Gangarten (Tripod, Wave,
Ripple). Dynamisches Rennen mit ballistischen Phasen wäre Phase 10+
und würde eine Strategy-Pattern-Refaktorierung der Engine brauchen
(siehe Stufe-F-Design-Entscheidung 4 zur Trade-off-Diskussion).

---

## Erweiterungs-Roadmap

| Was | Wo | Aufwand |
|---|---|---|
| Wave-Gait | `gait_patterns.py`: 5 Zeilen Konstante | trivial |
| Ripple-Gait | `gait_patterns.py`: 5 Zeilen | trivial |
| Live-Pattern-Switch | `gait_node.py`: Param-Callback wie Stufe F's `enable_walk` | klein |
| Adaptive Schritt-Höhe | `gait_engine.py`: step_height ∝ |v_body| | klein |
| Closed-Loop-Yaw-Korrektur | neue ROS-Subscription auf `/imu` oder `/odom`, P-Regler | mittel |
| Dynamische Gangarten (Rennen) | Strategy-Pattern Refactor + Bezier-Trajektorien | groß (Phase 10+) |
| Body-Pose-Modulation (Roll/Pitch) | swing_traj/stance_traj um Z-Rotation pro Bein erweitern | mittel |
| HW-Port (Phase 7) | gait_node bleibt; controllers.real.yaml + body_height -0.047 | mittel |

Erweiterungs-Quickwins für Phase 6 (Teleop) und Phase 8+ sind in den
ersten 3–4 Zeilen jeweils klein. Engine-Architektur skaliert.
