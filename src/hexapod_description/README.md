# hexapod_description

URDF/Xacro-Beschreibung des 6-beinigen Hexapod-Roboters.
Reine Box-Geometrie für Chassis und Beinsegmente, Kugel als Foot-Link.
Keine externen Meshes/STL.

## Inhalt

```
urdf/
├── hexapod.urdf.xacro                  # Top-Level: base_link + 6× leg-Macro
├── leg.xacro                           # Bein-Macro (coxa/femur/tibia/foot)
├── hexapod_physical_properties.xacro   # Maße, Massen, Joint-Limits
├── inertials.xacro                     # box_inertia / sphere_inertia mit Mindestschranke
└── materials.xacro                     # orange / grey / black
launch/
└── display.launch.py                   # RViz + joint_state_publisher_gui + world-TF
config/
└── view.rviz                           # RViz-Config (Fixed Frame: world)
```

## Zweck

Phase-2-Artefakt: das URDF dient ausschließlich der Visualisierung in
RViz und als gemeinsame Geometrie-Quelle für spätere Phasen
(Gazebo-Spawn in Phase 3, `ros2_control` ab Phase 4, IK ab Phase 5).
Maße und Joint-Limits stammen aus `docs/00_conventions.md` §11.

## Aufruf

```bash
ros2 launch hexapod_description display.launch.py
```

Startet:
- `tf2_ros static_transform_publisher` (`world → base_link`, hebt Roboter
  an, sodass die Coxa-Unterkanten auf `world.z = 0` liegen)
- `robot_state_publisher` (Xacro wird zur Laufzeit verarbeitet)
- `joint_state_publisher_gui` (Slider für die 18 revolute Joints)
- `rviz2 -d config/view.rviz`

## Frame-Tree

```
world
└── base_link
    ├── leg_1_coxa_link → leg_1_femur_link → leg_1_tibia_link → leg_1_foot_link
    ├── leg_2_coxa_link → leg_2_femur_link → leg_2_tibia_link → leg_2_foot_link
    ├── leg_3_coxa_link → leg_3_femur_link → leg_3_tibia_link → leg_3_foot_link
    ├── leg_4_coxa_link → leg_4_femur_link → leg_4_tibia_link → leg_4_foot_link
    ├── leg_5_coxa_link → leg_5_femur_link → leg_5_tibia_link → leg_5_foot_link
    └── leg_6_coxa_link → leg_6_femur_link → leg_6_tibia_link → leg_6_foot_link
```

26 Frames (1 `world` + 1 `base_link` + 6 × 4 Bein-Links).
Joints: 18 `revolute` (3 pro Bein) + 6 `fixed` (foot) + 1 `fixed` (world→base_link).

Live-Verifikation:

```bash
ros2 run tf2_tools view_frames    # erzeugt frames_<timestamp>.pdf
```

## Konventionen / Geometrie

- `base_link` liegt im **geometrischen Mittelpunkt** des Chassis
  (REP-103, siehe `docs/00_conventions.md` §3).
- `world → base_link` ist ein statischer Z-Offset von
  `coxa_height/2 = 0.0291 m`. Begründung: weil
  `coxa_height (0.0582) > body_height (0.043)` und die Coxa-Box
  Z-symmetrisch um den Joint sitzt, sind die Coxa-Unterkanten der
  unterste Punkt des Roboters — der wird auf `world.z = 0` gelegt.
  Dieser `world`-Frame ist Phase-2-spezifisch und wird in Phase 3
  durch den Gazebo-Spawn ersetzt.
- `leg_mount_z = 0` (Konvention §11.3): Coxa-Joint-Achse liegt
  horizontal in der Chassis-Z-Mitte.
- Beine im Uhrzeigersinn nummeriert, beginnend vorne rechts
  (Konvention §1).

## Joint-Limits

Identisch für alle 6 Beine (`docs/00_conventions.md` §11.4):

| Joint | lower | upper | effort | velocity |
|---|---|---|---|---|
| `leg_<n>_coxa_joint`  | −1.57 rad | +1.57 rad | 5.0 Nm | 2.0 rad/s |
| `leg_<n>_femur_joint` | −1.57 rad | +1.57 rad | 5.0 Nm | 2.0 rad/s |
| `leg_<n>_tibia_joint` | −1.50 rad | +1.50 rad | 5.0 Nm | 2.0 rad/s |

`effort` und `velocity` sind Schätzwerte aus dem Servo-Datenblatt,
nicht unter Last verifiziert.
