# Phase 5 — Inverse Kinematik & Gangsteuerung

**Dauer-Schätzung:** 1–3 Wochen (Hauptphase)
**Maschine:** nur Desktop
**Vorbedingung:** Phase 4 abgeschlossen, Joints fahren auf Trajectory-Goals

---

## Ziel

Der Hexapod läuft in Gazebo eigenständig geradeaus, gesteuert durch
`/cmd_vel` (Twist-Nachricht). Tripod-Gait als erste Gangart.

---

## Done-Kriterien

1. Paket `hexapod_kinematics` gebaut, **Pure-Python-Tests grün** (ohne ROS).
2. Paket `hexapod_gait` gebaut, läuft als Knoten.
3. `ros2 topic pub /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'`
   bewirkt sichtbares Vorwärtslaufen in Gazebo.
4. Bei `cmd_vel = 0` bleibt der Roboter in Standpose stehen.
5. Tripod-Sequenz erkennbar: drei Beine in Schwungphase, drei in Stützphase.

---

## Aufteilung in zwei Pakete

### `hexapod_kinematics` — pure Mathematik

```
hexapod_kinematics/
├── package.xml
├── setup.py
├── hexapod_kinematics/
│   ├── __init__.py
│   ├── leg_ik.py            # IK pro Bein
│   ├── geometry.py          # Helfer (rotation, translation)
│   └── config.py            # Längen, Offsets als dataclass
└── test/
    ├── test_leg_ik.py
    └── test_geometry.py
```

> **Wichtig:** `hexapod_kinematics` darf **kein** `import rclpy` haben.
> Reine Python-Library, mit `pytest` testbar, ohne ROS-Stack.
> Das ist die wichtigste Architektur-Entscheidung dieser Phase.

### `hexapod_gait` — ROS-Knoten, der die Library nutzt

```
hexapod_gait/
├── package.xml
├── setup.py
├── hexapod_gait/
│   ├── __init__.py
│   ├── gait_node.py         # rclpy-Knoten
│   ├── gait_engine.py       # State Machine, Foot-Targets
│   └── trajectory_gen.py    # Bezier oder Sinus für Schritte
└── test/
    └── test_gait_engine.py
```

---

## IK pro Bein (geschlossene Form)

Hexapod-Beine mit 3 DOF (coxa, femur, tibia) sind **analytisch lösbar**,
kein numerischer Solver nötig.

Eingabe: Fußpunkt (x, y, z) im **Bein-Frame** (also relativ zum
`coxa_joint`).
Ausgabe: (θ_coxa, θ_femur, θ_tibia) in Radiant.

Standard-Algorithmus (Skizze, ohne konkrete Längen — die kommen aus
`config.py`):

```
1. θ_coxa = atan2(y, x)

2. Distanz in der durch coxa rotierten Ebene:
   r  = sqrt(x² + y²) - L_coxa
   z' = z

3. Direkte Distanz von femur_joint zu Fuß:
   d = sqrt(r² + z'²)
   if d > L_femur + L_tibia: out of reach → exception

4. Knickwinkel tibia (Gesetz des Cosinus):
   cos_θ3 = (d² - L_femur² - L_tibia²) / (2 * L_femur * L_tibia)
   θ_tibia = acos(cos_θ3)         # Vorzeichen je nach Konvention

5. Hubwinkel femur:
   α  = atan2(z', r)
   β  = acos((L_femur² + d² - L_tibia²) / (2 * L_femur * d))
   θ_femur = α + β   oder  α - β  (je nach Konvention "Knie oben/unten")
```

> 🔧 **Vorzeichen + Knie-Konvention:** Das ist Bein-spezifisch (links/rechts)
> und musst du am eigenen Modell verifizieren. Pure-Python-Tests sind genau
> dafür da.

### Tests für IK

```python
def test_ik_neutral_pose():
    # Standardpose: Fuß auf z=-0.10, x=0.15, y=0
    angles = leg_ik(0.15, 0.0, -0.10, leg_config)
    # Forward-Kinematik der zurückkommenden Winkel muss
    # wieder denselben Punkt liefern
    fk_pos = leg_fk(*angles, leg_config)
    assert np.allclose(fk_pos, [0.15, 0.0, -0.10], atol=1e-6)

def test_ik_out_of_reach():
    with pytest.raises(IKError):
        leg_ik(10.0, 0.0, 0.0, leg_config)
```

> **Forward-Kinematik (FK)** auch implementieren, allein zum Testen der IK.
> Wenn FK(IK(p)) = p, ist die IK korrekt.

---

## Gait-Engine

### Konzept Tripod-Gait

Die 6 Beine teilen sich in zwei Gruppen:

- **Gruppe A:** Bein 1, 3, 5
- **Gruppe B:** Bein 2, 4, 6

(Ungerade vs. gerade Bein-Indizes — bei der oben definierten Nummerierung
sind das jeweils alternierende Beine.)

In jedem Zyklus T:
- Phase 0..T/2: Gruppe A in **Schwung**, Gruppe B in **Stütze**
- Phase T/2..T: umgekehrt

### Foot-Trajectory pro Phase

- **Stützphase:** Fuß bewegt sich linear rückwärts (entgegengesetzt zur
  Fahrtrichtung) in Boden-Höhe. Schiebt den Körper voran.
- **Schwungphase:** Fuß hebt ab, bewegt sich vorwärts, setzt wieder auf.
  Trajektorie: halber Bezier-Bogen oder Sinus über Hub-Höhe.

Parameter:
- `step_length` — wie weit ein Schritt
- `step_height` — wie hoch wird gehoben
- `cycle_time T` — Schrittdauer
- `body_height` — Z-Offset des Körpers über Boden

> 🔧 **Erste Werte:** step_length 0.04 m, step_height 0.02 m, T = 1.0 s,
> body_height = -0.10 m (im Bein-Frame). Anpassen.

### State-Machine

```
States: STANDING, WALKING

STANDING:
    foot_targets = neutral_pose pro Bein
    if |cmd_vel| > epsilon: → WALKING

WALKING:
    phase = (now - t_start) / T  mod 1.0
    for each leg:
        if leg in group_A: leg_phase = phase
        if leg in group_B: leg_phase = (phase + 0.5) mod 1.0
        if leg_phase < 0.5: stance_traj(leg, leg_phase * 2)
        else:               swing_traj(leg, (leg_phase - 0.5) * 2)
    if |cmd_vel| < epsilon for >0.5s: → STANDING (in neutral pose)
```

### Knoten-Interface

`gait_node`:
- **Subscribe:** `/cmd_vel` (geometry_msgs/Twist)
- **Publish:** `/leg_<n>_controller/joint_trajectory` für n=1..6
- **Parameter:** alle Gait-Parameter (über `declare_parameter`)
- **Update-Rate:** 50 Hz (Timer-Callback)

In jedem Tick:
1. Aktuelle Phase berechnen
2. Pro Bein: Foot-Target im Bein-Frame berechnen (Stütze oder Schwung)
3. IK aufrufen → Joint-Winkel
4. Trajectory-Goal mit kurzem `time_from_start` (z. B. 0.05 s) publishen

> **Designwarnung:** Trajectory-Goals mit kurzem `time_from_start` sind
> ein Hack. Sauberer wäre `forward_position_controller` oder ein
> Custom-Controller. Aber für den Anfang akzeptabel und kompatibel mit
> dem `JointTrajectoryController` aus Phase 4. Refactor in Phase 7
> denkbar.

---

## Foot-Bodenkontakt-Sensoren (toggle-bar)

In Phase 5 (nach Stand-Pose, vor Single-Leg-Schwung) wird pro Foot ein
binäres Bodenkontakt-Signal als ROS-Topic verfügbar gemacht. Dient als
**passives Diagnose-Werkzeug** für die Live-Stufen Single-Leg, Tripod,
Vollgait — der Tripod-Pattern-Check (DK5) wird dadurch direkt
beobachtbar (`ros2 topic echo /leg_<n>/foot_contact`).

**Toggle:** LaunchArg `enable_foot_contact:=true|false`. Aus zwei Gründen
ein-/abschaltbar:
1. **Reine Open-Loop-Tests** (Vergleich gegen die Sensor-frei-Variante,
   Fokus auf reines IK/Gait-Verhalten ohne Sensor-Lärm im Topic-Listing).
2. **Zukunfts-Phase, in der Closed-Loop-Konsumenten kommen** — dort
   bleibt der Toggle als Schnellschalter, falls Sensor-Defekt oder
   Closed-Loop-Bug vorliegt.

**Nicht in Phase 5 enthalten:** Konsumieren des Signals durch die
Gait-Engine (Closed-Loop-Adaption Schwung↔Stütze). Das ist Phase 6+
oder dedizierte Folge-Phase. In Phase 5 nur **Publisher + Bridge**,
keine Konsumenten.

**Architektur-Skizze:**
- Sim: `<sensor type="contact">`-Plugin pro `foot_link` in einer neuen
  `hexapod.foot_contact.xacro`, conditional-included via
  `<xacro:if value="${enable_foot_contact}">`.
- Bridge: `ros_gz_bridge` mit zusätzlichen 6 Mappings für
  `/leg_<n>/foot_contact` (`std_msgs/Bool` empfohlen) — conditional
  in `hexapod_bringup/sim.launch.py` per `IfCondition`.
- HW (Phase 7): physische Microschalter pro Foot, ROS-Treiber publisht
  auf gleichen Topic-Namen — Sim/HW-Abstraktion über Topic-Pattern wie
  bei Joints.

---

## Roadmap innerhalb Phase 5

1. **Schritt 1 — IK isoliert:** `hexapod_kinematics` mit Tests, ohne ROS.
2. **Schritt 2 — Standpose:** Neuer Knoten `stand_node`, der die
   Neutral-IK berechnet und einmal eine Trajectory pro Bein publisht.
   Roboter steht in Wunschpose. (≠ Phase 3, weil dort manuell.)
3. **Schritt 2.5 — Foot-Bodenkontakt-Sensoren (toggle-bar):**
   `<sensor type="contact">` pro Foot in der Sim, gebrückt nach ROS als
   `/leg_<n>/foot_contact`. Ein-/abschaltbar via `enable_foot_contact`-
   LaunchArg. Verifikation gegen Stand-Pose-Baseline (alle 6 = `True`),
   gegen manuell angehobenes Bein (das eine = `False`).
4. **Schritt 3 — Bein einzeln Schwung:** Eines Beines in der Luft eine
   Sinusbahn fahren, Rest steht. Validiert IK + Trajectory-Pipeline.
5. **Schritt 4 — Statisches Tripod-Pattern:** Beine bewegen sich abwechselnd
   in der Luft (Roboter aufgebockt oder im Stand-only-Modus).
6. **Schritt 5 — Vollständiger Tripod-Gait, geradeaus.** Ende-Kriterium.
7. **Schritt 6 (optional):** Drehen um Z (`cmd_vel.angular.z`).
8. **Schritt 7 (optional):** Seitwärts laufen (`cmd_vel.linear.y`).

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| IK liefert `nan` | Ziel außerhalb Reichweite, Cosinus-Argument außerhalb [-1,1] | Bereich clampen, `IKError` werfen |
| Roboter zuckt statt zu laufen | Trajectory-Updates kommen zu schnell und kollidieren | Update-Rate auf 50 Hz, `time_from_start` ≥ 2/Rate |
| Beine kollidieren mit Chassis | Joint-Limits zu großzügig oder Standpose falsch | Limits prüfen, Standpose neu rechnen |
| Roboter rutscht beim Laufen weg | Stützbeine bewegen sich nicht synchron entgegen Fahrtrichtung | Phasen-Synchronisation prüfen |
| Roboter kippt nach hinten/vorne | Schwerpunkt wandert aus dem Stütz-Dreieck | Stand höher, Beine weiter spreizen |
| `cmd_vel = 0` → Roboter zittert weiter | State-Machine geht nicht in STANDING zurück | Timeout-Logik prüfen |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein dynamic balancing (Stabilisierungsregler)
- Kein PS-Controller (Phase 6)
- Keine Sensorik (IMU)
- Keine andere Gangart als Tripod (außer du willst, optional am Ende)
- Keine Pi-Portierung (Phase 7)

---

## Phasenabschluss

- [ ] Alle 5 Done-Kriterien erfüllt
- [ ] `pytest` in `hexapod_kinematics` grün
- [ ] Tripod-Gait dokumentiert (Diagramm in README)
- [ ] Parameter-Werte in `controllers.yaml` und Gait-Config dokumentiert
- [ ] Timeshift-Snapshot `phase_5_done`
- [ ] Git-Commit + Tag `phase-5-done`
- [ ] `PHASE.md` auf Phase 6 aktualisiert
