# hexapod_kinematics

Pure-Python IK/FK-Library für die Hexapod-Beine. **Keine ROS-Dependency**
— `import rclpy` ist hier verboten und durch das Test-Setup verifiziert.
Ergebnis: alle Math-Tests laufen mit reinem `pytest` ohne ROS-Stack
(siehe Phase 5 Stufe A-Designentscheidung in
[docs/phase_5_progress.md](../../docs/phase_5_progress.md)).

## Zweck

- **Inverse Kinematik (`leg_ik`)**: Foot-Position im Bein-Frame
  → `(θ_coxa, θ_femur, θ_tibia)` in Radiant.
- **Forward Kinematik (`leg_fk`)**: Joint-Winkel → Foot-Position.
  Wird zur Test-Verifikation und für Round-Trip-Checks genutzt.
- **Geometrie-Helfer (`rotate_z`, `base_to_leg_frame`,
  `leg_to_base_frame`)**: Frame-Transformationen zwischen `base_link`
  und Bein-Frame.
- **Konfiguration (`HEXAPOD`, `LegConfig`)**: Single Source of Truth für
  Bein-Längen, Mount-Punkte, Joint-Limits, Mount-Yaws. Werte gespiegelt
  aus
  [hexapod_description/urdf/hexapod_physical_properties.xacro](../hexapod_description/urdf/hexapod_physical_properties.xacro)
  und [hexapod.urdf.xacro](../hexapod_description/urdf/hexapod.urdf.xacro);
  Cross-Check-Test
  [test/test_config.py](test/test_config.py) parst die xacro-Quelle und
  failt bei Drift.

## API-Quickstart

```python
from hexapod_kinematics import HEXAPOD, leg_ik, leg_fk, IKError

# Stand-Pose: foot 27 cm vor coxa, 47 mm tiefer (in Bein-Frame).
leg = HEXAPOD.by_name('leg_1')
foot_target = (0.27, 0.0, -0.047)

theta_coxa, theta_femur, theta_tibia = leg_ik(*foot_target, leg)
# (0.0, -0.500, +1.000)  — die Phase-4-Stand-Pose

# Round-Trip-Verify:
foot_back = leg_fk(theta_coxa, theta_femur, theta_tibia, leg)
# foot_back ≈ foot_target  (bis auf ~1e-9 Float-Rauschen)
```

`leg_ik` wirft `IKError` bei out-of-reach Targets oder bei Werten, die
über `coxa_limits` / `femur_limits` / `tibia_limits` rauslaufen.

`HEXAPOD.legs` ist ein 6-Tuple (`leg_1` … `leg_6`). Pro `LegConfig`:

| Feld | Bedeutung |
|---|---|
| `name` | `'leg_1'` … `'leg_6'` |
| `mount_xyz` | Position des `coxa_joint` in `base_link` (m) |
| `mount_yaw` | Z-Rotation des Bein-Frames ggü. `base_link` (rad) |
| `L_coxa`, `L_femur`, `L_tibia` | Segmentlängen (m) |
| `coxa_limits`, `femur_limits`, `tibia_limits` | Joint-Limits (rad) |
| `foot_radius` | Foot-Kugel-Radius (m) — nur Info, IK nutzt's nicht |

## IK-Konvention

- **Bein-Frame +X** = radial nach außen (von `base_link`-Center weg).
- **Bein-Frame +Z** = parallel zu `base_link`-Z (oben).
- **Bein-Frame +Y** = rechtshändig komplettiert.
- **Foot-Z negativ** = unter coxa-Joint (Standard für Stand-Pose).
- **Knie-Oben-Konvention**: bei mehreren IK-Lösungen wird die mit
  `θ_femur ≤ 0` gewählt — das Knie zeigt nach oben.

Detail-Erklärung mit Math-Herleitung in
[docs/phase_5_ik_explained.md](../../docs/phase_5_ik_explained.md).

## Tests aufrufen

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_kinematics
colcon test-result --verbose --test-result-base build/hexapod_kinematics
```

Erwartet: **28 Tests, 0 Failures, 1 skipped** (test_copyright).

Direkt mit pytest (ohne ROS-Setup, da pure Python):

```bash
cd ~/hexapod_ws/src/hexapod_kinematics
python3 -m pytest test/test_leg_ik.py test/test_geometry.py test/test_config.py -v
```

## Test-Coverage

- **`test_leg_ik.py`** (17 Tests): Stand-Pose-Reproduktion, Round-Trip
  IK→FK→IK, Symmetrie zwischen Beinen, Out-of-Reach-Fälle, Joint-Limit-
  Verletzungen, Edge-Cases (foot direkt überm Mount, fully extended).
- **`test_geometry.py`** (6 Tests): `rotate_z` Identität / 90°-Schritte,
  `base_to_leg_frame` Round-Trip, Bein-1-Stand-Pose-Konvertierung
  base ↔ leg.
- **`test_config.py`** (3 Tests): xacro-Source-Parsing-Sync für Bein-
  Längen / Mount-Layout / Joint-Limits — Drift-Detektion.

## Architektur-Notizen

- **Pure Python**, keine numpy/scipy. Skalar-Math (`math.atan2`,
  `math.acos`, `math.sqrt`, `math.hypot`) ist für 18 Joints schnell
  genug (50 Hz Tick mit µs-Latenz pro IK-Call).
- **Closed-Form IK** (analytisch lösbar), kein numerischer Solver.
  Konsequenz: deterministisch, keine Konvergenz-Probleme,
  reproduzierbar.
- **Frozen dataclasses** für `LegConfig` und `HexapodConfig` — keine
  Runtime-Mutation, sicher in Multi-Threading-Szenarien.
- **`_COS_EPS = 1e-9`** Clamping in `leg_ik` für `acos`-Singularität bei
  fully-extended Beinen.

## Konsumiert von

- [hexapod_gait](../hexapod_gait/) — Tripod-Gait-Engine ruft `leg_ik`
  pro Tick für alle 6 Beine.
- Geplant Phase 7: HW-Treiber-Code (C++) wird die gleiche Math-
  Konvention nutzen, dann aus C++ neu implementiert (oder via
  pybind11-Bridge).
