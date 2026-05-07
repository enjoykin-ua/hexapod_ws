# 00 — Konventionen

Diese Konventionen werden in Phase 0 / Phase 2 verbindlich festgelegt
und ab dann **nicht mehr geändert**. Spätere Änderungen sind teuer,
weil Joint-Namen, Frames und Achsen in URDF, Controllern, IK, Gait,
Hardware-Interface und Launch-Files auftauchen.

---

## 1. Beine: Nummerierung

Verbindliche Konvention für dieses Projekt:

- Blick von **oben** auf den Roboter, +X = Fahrtrichtung vorne.
- Beine im **Uhrzeigersinn** durchnummeriert, beginnend vorne rechts.

```
              +X (vorne)
                ▲
                |
       leg_6  --+--  leg_1
           \   |   /
            \  |  /
   leg_5 ----[base_link]---- leg_2     ─► +Y (links)
            /  |  \
           /   |   \
       leg_4  --+--  leg_3
```

| Bein-ID | Position | yaw (Coxa-Mountpoint) |
|---|---|---|
| leg_1 | vorne rechts | -π/4 |
| leg_2 | mitte rechts | -π/2 |
| leg_3 | hinten rechts | -3π/4 |
| leg_4 | hinten links | +3π/4 |
| leg_5 | mitte links | +π/2 |
| leg_6 | vorne links | +π/4 |

---

## 2. Joints

Pro Bein drei Joints, von Körper zu Fuß:

| Joint | Beschreibung | Drehachse (im Joint-Frame) |
|---|---|---|
| `leg_<n>_coxa_joint` | Hüfte, schwenkt das Bein horizontal | Z |
| `leg_<n>_femur_joint` | Schenkel, hebt/senkt das Bein | Y |
| `leg_<n>_tibia_joint` | Schienbein, knickt das Bein ein | Y |

Alle Joints: `revolute` (mit Limits!), nicht `continuous`.

**Joint-Limits** sind im URDF zwingend zu setzen
(`<limit lower upper effort velocity>`). Werte siehe §11.

---

## 3. Frames (REP-103)

- `base_link` — Bezugsframe des Roboterkörpers, Ursprung im
  geometrischen Mittelpunkt des Chassis.
- `+X` zeigt nach vorne (Fahrtrichtung)
- `+Y` zeigt nach links
- `+Z` zeigt nach oben

Pro Bein:

- `leg_<n>_coxa_link` — Coxa-Segment (Hüfte, horizontal schwenkbar)
- `leg_<n>_femur_link` — Femur-Segment (Oberschenkel)
- `leg_<n>_tibia_link` — Tibia-Segment (Unterschenkel)
- `leg_<n>_foot_link` — Fußkugel am Tibia-Ende, **mit Kollision**.
  Erfüllt zwei Aufgaben:
  1. Punktkontakt mit dem Boden (statt Kantenkontakt der dünnen Tibia-Box).
     Das verhindert Rutsch- und Vibrations-Effekte beim Stehen/Laufen.
  2. Definiert den TCP-Frame für IK-Targets (Phase 5).

> **Designentscheidung Foot-Link:** Da Beinsegmente als dünne Boxen
> modelliert sind (Tibia: 0.1787 × 0.012 × 0.012 m), würde ein direkter
> Bodenkontakt der Tibia-Box auf einer Kante stattfinden — physikalisch
> instabil, im Gazebo-Solver vibrationsanfällig. Eine kleine Kugel
> (r ≈ 0.008 m) am Tibia-Ende erzeugt einen sauberen Punktkontakt und
> ist gleichzeitig der natürliche TCP-Frame für die IK.

---

## 4. Einheiten

- Längen: **Meter**
- Winkel: **Radiant**
- Massen: **Kilogramm**
- Trägheitsmomente: **kg·m²**
- Kräfte: **Newton**
- Drehmomente: **Newtonmeter**
- Zeit: **Sekunden**

Keine Mischung. Keine cm, keine Grad, keine Gramm.
Konvertierung an den Systemgrenzen (UI, Logs) erlaubt, intern strikt SI.

---

## 5. Sprachwahl pro Paket

| Paket | Sprache | Begründung |
|---|---|---|
| `hexapod_description` | XML/Xacro | URDF |
| `hexapod_gazebo` | XML/SDF + Python | Welt + Launch |
| `hexapod_control` | YAML + Python | Config + Launch |
| `hexapod_kinematics` | Python | reine Mathe, gut testbar, ohne ROS lauffähig |
| `hexapod_gait` | Python | High-Level State Machine |
| `hexapod_teleop` | Python | Mapping-Logik |
| `hexapod_hardware` | **C++** | `ros2_control`-HardwareInterface ist C++-Plugin (pluginlib) |
| `hexapod_bringup` | Python | Launch-Files |

---

## 6. Launch-Files

- **Immer Python** (`*.launch.py`), nicht XML.
- Pro Anwendungsfall ein Top-Level-Launch:
  - `display.launch.py` — nur RViz mit Robotermodell
  - `sim.launch.py` — Gazebo + Robot + Controller + RViz
  - `real.launch.py` — Hardware + Controller + (optional RViz remote)
- Sub-Launches via `IncludeLaunchDescription` zusammensetzen, nicht alles
  in eine Datei kippen.

---

## 7. Tests

- `hexapod_kinematics`: pytest-Tests **ohne ROS**.
  Mathe muss isoliert grün sein, bevor sie in Gait integriert wird.
- ROS-Knoten: `launch_testing` für Smoke-Tests (Knoten startet, Topics
  publishen, keine Crashs in 10 s).
- `colcon test` muss vor jedem Commit grün sein.

---

## 8. Git

- Ein Repo: das gesamte `~/hexapod_ws/`.
- Commit-Messages: `phase<n>: <kurze Beschreibung>`.
- Tags pro Phasenende: `phase-<n>-done`.
- Branches optional, Solo-Projekt → main reicht.
- Pflicht ins Repo: `CLAUDE.md`, `PHASE.md`, `docs/`, `src/`.
- Nicht ins Repo: `build/`, `install/`, `log/`, `__pycache__/`,
  IDE-Konfigs (`.vscode/`).

---

## 9. Code-Stil

- Python: PEP-8, `ruff` oder `black` als Formatter.
- C++: ROS2-Standard-Style.
- Keine TODOs ohne Issue-Referenz oder konkretes Datum.
- Keine auskommentierten Code-Blöcke im Commit (außer mit Begründung).

---

## 10. Dokumentation

- Jedes Paket hat eine `README.md` mit:
  - Zweck
  - Topics In / Out
  - Parameter
  - Beispiel-Launch
- Keine veralteten READMEs. Wenn der Code sich ändert, ändert sich
  die README.
- `package.xml`-Felder `<maintainer>` und `<license>` sind beim Anlegen
  des Pakets zu füllen — keine `TODO:`-Stubs im Commit.

---

## 11. Verifizierte Geometrie und Joint-Limits

Diese Werte stammen aus dem realen Hexapod und sind physisch verifiziert.
Sie werden im Xacro als Konstanten gepflegt (`hexapod_physical_properties.xacro`)
und sind die einzige Stelle, an der sie geändert werden dürfen.

### 11.1 Chassis

| Größe | Wert |
|---|---|
| `body_length` | 0.175 m |
| `body_width` | 0.130 m |
| `body_width_middle` | 0.170 m (für mittlere Beine, breiterer Mountpunkt) |
| `body_height` | 0.043 m |
| `base_mass` | 0.5 kg |

### 11.2 Beinsegmente

| Segment | L × B × H | Masse |
|---|---|---|
| Coxa  | 0.0436 × 0.0254 × 0.0582 m | 0.1167 kg |
| Femur | 0.07994 × 0.059 × 0.020 m | 0.1167 kg |
| Tibia | 0.1787 × 0.012 × 0.012 m | 0.1167 kg |
| Foot  | Kugel, r = 0.008 m | 0.005 kg |

### 11.3 Mountpunkte der Beine (relativ zu `base_link`)

`leg_mount_z = 0` für alle Beine — die Coxa-Joint-Achse liegt
horizontal in der Chassis-Z-Mitte (= Z-Mitte von `base_link`).
Die Coxa-Box ist Z-symmetrisch um den Joint und ragt
`(coxa_height − body_height) / 2 ≈ 0.0076 m` über die Chassis-
Ober- und Unterkante hinaus, weil `coxa_height > body_height`
(Servo-Block etwas höher als der Chassis-Querschnitt).

| Bein | x | y | yaw |
|---|---|---|---|
| leg_1 | +body_length/2 | -body_width/2 | -π/4 |
| leg_2 | 0.0 | -body_width_middle/2 | -π/2 |
| leg_3 | -body_length/2 | -body_width/2 | -3π/4 |
| leg_4 | -body_length/2 | +body_width/2 | +3π/4 |
| leg_5 | 0.0 | +body_width_middle/2 | +π/2 |
| leg_6 | +body_length/2 | +body_width/2 | +π/4 |

### 11.4 Joint-Limits (physisch verifiziert)

Werte am realen Roboter durch Anfahren des mechanischen Anschlags ermittelt.
Über alle 6 Beine identisch eingemessen.

| Joint | lower | upper | effort | velocity |
|---|---|---|---|---|
| `leg_<n>_coxa_joint` | -1.57 rad | +1.57 rad | 5.0 Nm | 2.0 rad/s |
| `leg_<n>_femur_joint` | -1.57 rad | +1.57 rad | 5.0 Nm | 2.0 rad/s |
| `leg_<n>_tibia_joint` | -1.50 rad | +1.50 rad | 5.0 Nm | 2.0 rad/s |

> **Hinweis zu effort/velocity:** Diese sind Schätzwerte aus dem Servo-
> Datenblatt-Bereich und nicht am realen Roboter unter Last vermessen.
> Sie sind für Sim ausreichend, für die Hardware-Phase 7 gegebenenfalls
> verfeinern. Markierung im Xacro: `<!-- effort/velocity: vom Servo-DB -->`
>
> **Hinweis zu pro-Bein-Abweichung:** Aktuell für alle 6 Beine gleich.
> Falls in Phase 3 oder Phase 7 festgestellt wird, dass einzelne Beine
> mechanisch andere Anschläge haben (z. B. wegen Chassis-Kollision an
> mittleren Beinen), wird das Bein-Macro so erweitert, dass Limits per
> Parameter überschrieben werden können. Default bleibt obige Tabelle.

### 11.5 Inertia-Mindestschranke

Wegen sehr dünner Tibia-Geometrie (0.012 × 0.012 m Querschnitt) ergibt
die Standardformel `(1/12)·m·(b² + c²)` numerisch sehr kleine Werte
(< 1e-5 kg·m²), was im Gazebo-Physics-Solver zu Vibrationen führen kann.

Daher: alle berechneten Inertien werden im Macro per `max(value, 1e-5)`
auf einen Mindestwert geclamped. Das ist physikalisch eine kleine
Konservativismus-Reserve (Inertien werden minimal überschätzt) und
mechanisch unkritisch.

Implementierung im `inertials.xacro` — siehe Phase 2.

---

## 12. Verbindliche Naming-Konventionen (Zusammenfassung)

Diese Liste ist die Single Source of Truth für Namen im gesamten Projekt:

| Element | Schema | Beispiel |
|---|---|---|
| ROS-Pakete | `hexapod_<funktion>` | `hexapod_description` |
| Bein-ID | `leg_<n>` mit n ∈ 1..6 | `leg_3` |
| Link-Namen | `<bein>_<segment>_link` | `leg_3_femur_link` |
| Joint-Namen | `<bein>_<segment>_joint` | `leg_3_femur_joint` |
| Foot-Frame | `<bein>_foot_link` | `leg_3_foot_link` |
| Controller | `<bein>_controller` | `leg_3_controller` |
| Topics (Bein-spezifisch) | `/<bein>_controller/...` | `/leg_3_controller/joint_trajectory` |

**Verboten:** Bezeichnungen wie `fr/fl/mr/ml/br/bl`, `front_right`, oder
zusammengesetzte Joint-Suffixe wie `_base_to_coxa_joint`.
