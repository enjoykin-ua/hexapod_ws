# Phase 2 — Roboter-Beschreibung (URDF / Xacro)

**Dauer-Schätzung:** 3–7 Tage
**Maschine:** Desktop
**Vorbedingung:** Phase 1 abgeschlossen, ROS2-Konzepte verstanden

---

## Ziel

Der Hexapod ist als URDF beschrieben, in `rviz2` sichtbar, mit dem
`joint_state_publisher_gui` lassen sich alle 18 Joints einzeln bewegen,
die Kinematik sieht plausibel aus (Achsen drehen in die richtigen
Richtungen, Beinlängen stimmen).

Die Geometrie verwendet ausschließlich **Boxen** (Chassis und
Beinsegmente) plus **eine kleine Kugel** als Foot-Link am Ende jeder
Tibia. Keine externen Meshes/STL — der Roboter ist optisch einfach,
funktional vollständig.

---

## Done-Kriterien

1. Paket `hexapod_description` baut und installiert sauber.
2. `ros2 launch hexapod_description display.launch.py` öffnet RViz mit
   sichtbarem Roboter und Joint-GUI-Slidern.
3. Alle 6 Beine sichtbar, alle 18 Joints in der GUI bewegbar.
4. `check_urdf` validiert das URDF ohne Fehler.
5. tf-Tree (`ros2 run tf2_tools view_frames`) zeigt vollständige
   Kette `base_link → leg_<n>_coxa_link → leg_<n>_femur_link →
   leg_<n>_tibia_link → leg_<n>_foot_link` für n=1..6.
6. README in `hexapod_description/` ist vorhanden und beschreibt
   Zweck, Launch-Aufruf, Frame-Tree.

---

## Strategie

Da die Geometrie aus Boxen besteht und alle Maße bereits verifiziert
sind (siehe `00_conventions.md` §11), entfällt die sonst übliche
Iteration „Primitive → Mesh". Stufenplan:

1. **Stufe A:** Chassis + 1 Bein als Box-Geometrie, ohne Foot-Link
2. **Stufe B:** Foot-Link (Kugel) am Bein anhängen, in RViz validiert
3. **Stufe C:** Bein als Xacro-Macro, 6× instanziiert mit korrekten
   Mountpunkten und yaw-Offsets
4. **Stufe D:** Inertien (mit Mindestschranke), Kollisionsgeometrien,
   Joint-Limits aus `00_conventions.md` §11.4
5. **Stufe E:** Smoke-Test in RViz, tf-Tree-Verifikation

---

## Paket anlegen

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_cmake --license Apache-2.0 \
  --maintainer-email "<deine@mail>" \
  hexapod_description
```

> `--maintainer-email` setzen, damit `package.xml` keine `TODO:`-Stubs
> enthält. License Apache-2.0 ist Standard für ROS2-Projekte.

Verzeichnisstruktur:

```
hexapod_description/
├── CMakeLists.txt
├── package.xml
├── README.md
├── urdf/
│   ├── hexapod.urdf.xacro                  # Top-Level
│   ├── leg.xacro                           # Bein-Macro
│   ├── inertials.xacro                     # Inertia-Helfer mit Schranke
│   ├── materials.xacro                     # Farben
│   └── hexapod_physical_properties.xacro   # Maße, Massen, Limits
├── launch/
│   └── display.launch.py
└── config/
    └── view.rviz
```

`CMakeLists.txt` muss `urdf/`, `launch/`, `config/` installieren:

```cmake
install(DIRECTORY urdf launch config
        DESTINATION share/${PROJECT_NAME})
```

`package.xml` als `<exec_depend>`:
- `xacro`
- `robot_state_publisher`
- `joint_state_publisher_gui`
- `rviz2`

---

## Physical-Properties-Datei (Single Source of Truth)

`urdf/hexapod_physical_properties.xacro`:

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Chassis -->
  <xacro:property name="body_length"        value="0.175"/>
  <xacro:property name="body_width"         value="0.130"/>
  <xacro:property name="body_width_middle"  value="0.170"/>
  <xacro:property name="body_height"        value="0.043"/>
  <xacro:property name="base_mass"          value="0.5"/>

  <!-- Beinsegmente -->
  <xacro:property name="coxa_length" value="0.0436"/>
  <xacro:property name="coxa_width"  value="0.0254"/>
  <xacro:property name="coxa_height" value="0.0582"/>

  <xacro:property name="femur_length" value="0.07994"/>
  <xacro:property name="femur_width"  value="0.059"/>
  <xacro:property name="femur_height" value="0.020"/>

  <xacro:property name="tibia_length" value="0.1787"/>
  <xacro:property name="tibia_width"  value="0.012"/>
  <xacro:property name="tibia_height" value="0.012"/>

  <xacro:property name="segment_mass" value="0.1167"/>

  <!-- Foot (Kugel am Tibia-Ende für Punktkontakt) -->
  <xacro:property name="foot_radius" value="0.008"/>
  <xacro:property name="foot_mass"   value="0.005"/>

  <!-- Joint-Limits (physisch verifiziert) -->
  <xacro:property name="coxa_lower"   value="-1.57"/>
  <xacro:property name="coxa_upper"   value=" 1.57"/>
  <xacro:property name="femur_lower"  value="-1.57"/>
  <xacro:property name="femur_upper"  value=" 1.57"/>
  <xacro:property name="tibia_lower"  value="-1.50"/>
  <xacro:property name="tibia_upper"  value=" 1.50"/>
  <xacro:property name="joint_effort"   value="5.0"/>  <!-- aus Servo-DB -->
  <xacro:property name="joint_velocity" value="2.0"/>  <!-- aus Servo-DB -->

  <!-- Mountpunkte der Beine als Liste:
       (id, mount_x, mount_y, yaw) -->
  <xacro:property name="leg_mount_z" value="${body_height/2}"/>

</robot>
```

> Konstanten zentral, alles andere referenziert sie nur.

---

## Inertia-Macro mit Mindestschranke

`urdf/inertials.xacro`:

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <!-- Mindest-Inertia, um Solver-Vibration bei dünnen Geometrien zu vermeiden -->
  <xacro:property name="inertia_min" value="1.0e-5"/>

  <xacro:macro name="box_inertia" params="mass x y z">
    <inertial>
      <mass value="${mass}"/>
      <inertia
        ixx="${max((1.0/12.0)*mass*(y*y + z*z), inertia_min)}"
        ixy="0.0" ixz="0.0"
        iyy="${max((1.0/12.0)*mass*(x*x + z*z), inertia_min)}"
        iyz="0.0"
        izz="${max((1.0/12.0)*mass*(x*x + y*y), inertia_min)}"/>
    </inertial>
  </xacro:macro>

  <xacro:macro name="sphere_inertia" params="mass radius">
    <inertial>
      <mass value="${mass}"/>
      <inertia
        ixx="${max((2.0/5.0)*mass*radius*radius, inertia_min)}"
        ixy="0.0" ixz="0.0"
        iyy="${max((2.0/5.0)*mass*radius*radius, inertia_min)}"
        iyz="0.0"
        izz="${max((2.0/5.0)*mass*radius*radius, inertia_min)}"/>
    </inertial>
  </xacro:macro>

</robot>
```

> Die `max(..., inertia_min)`-Klammer ist die in Konventionen §11.5
> spezifizierte Mindestschranke. Konservativ, robust, eine Codestelle.

---

## Materialien

`urdf/materials.xacro`:

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">
  <material name="orange"><color rgba="1.0 0.5 0.0 1.0"/></material>
  <material name="grey">  <color rgba="0.4 0.4 0.4 1.0"/></material>
  <material name="black"> <color rgba="0.1 0.1 0.1 1.0"/></material>
</robot>
```

> Wenn Links im RViz **weiß** dargestellt werden, ist die Material-
> Definition kaputt oder fehlt. Das ist ein URDF-Problem,
> **kein Treiber-Problem**.

---

## Bein-Macro

`urdf/leg.xacro` definiert ein Bein-Macro mit den Joints
coxa → femur → tibia → foot:

```xml
<?xml version="1.0"?>
<robot xmlns:xacro="http://www.ros.org/wiki/xacro">

  <xacro:macro name="leg" params="id mount_x mount_y mount_z mount_yaw">

    <!-- ===== Coxa ===== -->
    <joint name="leg_${id}_coxa_joint" type="revolute">
      <parent link="base_link"/>
      <child  link="leg_${id}_coxa_link"/>
      <origin xyz="${mount_x} ${mount_y} ${mount_z}"
              rpy="0 0 ${mount_yaw}"/>
      <axis xyz="0 0 1"/>
      <limit lower="${coxa_lower}" upper="${coxa_upper}"
             effort="${joint_effort}" velocity="${joint_velocity}"/>
    </joint>

    <link name="leg_${id}_coxa_link">
      <visual>
        <origin xyz="${coxa_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${coxa_length} ${coxa_width} ${coxa_height}"/>
        </geometry>
        <material name="grey"/>
      </visual>
      <collision>
        <origin xyz="${coxa_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${coxa_length} ${coxa_width} ${coxa_height}"/>
        </geometry>
      </collision>
      <xacro:box_inertia mass="${segment_mass}"
                         x="${coxa_length}" y="${coxa_width}" z="${coxa_height}"/>
    </link>

    <!-- ===== Femur ===== -->
    <joint name="leg_${id}_femur_joint" type="revolute">
      <parent link="leg_${id}_coxa_link"/>
      <child  link="leg_${id}_femur_link"/>
      <origin xyz="${coxa_length} 0 0" rpy="0 0 0"/>
      <axis xyz="0 1 0"/>
      <limit lower="${femur_lower}" upper="${femur_upper}"
             effort="${joint_effort}" velocity="${joint_velocity}"/>
    </joint>

    <link name="leg_${id}_femur_link">
      <visual>
        <origin xyz="${femur_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${femur_length} ${femur_width} ${femur_height}"/>
        </geometry>
        <material name="orange"/>
      </visual>
      <collision>
        <origin xyz="${femur_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${femur_length} ${femur_width} ${femur_height}"/>
        </geometry>
      </collision>
      <xacro:box_inertia mass="${segment_mass}"
                         x="${femur_length}" y="${femur_width}" z="${femur_height}"/>
    </link>

    <!-- ===== Tibia ===== -->
    <joint name="leg_${id}_tibia_joint" type="revolute">
      <parent link="leg_${id}_femur_link"/>
      <child  link="leg_${id}_tibia_link"/>
      <origin xyz="${femur_length} 0 0" rpy="0 0 0"/>
      <axis xyz="0 1 0"/>
      <limit lower="${tibia_lower}" upper="${tibia_upper}"
             effort="${joint_effort}" velocity="${joint_velocity}"/>
    </joint>

    <link name="leg_${id}_tibia_link">
      <visual>
        <origin xyz="${tibia_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${tibia_length} ${tibia_width} ${tibia_height}"/>
        </geometry>
        <material name="grey"/>
      </visual>
      <collision>
        <origin xyz="${tibia_length/2} 0 0" rpy="0 0 0"/>
        <geometry>
          <box size="${tibia_length} ${tibia_width} ${tibia_height}"/>
        </geometry>
      </collision>
      <xacro:box_inertia mass="${segment_mass}"
                         x="${tibia_length}" y="${tibia_width}" z="${tibia_height}"/>
    </link>

    <!-- ===== Foot (Kugel am Tibia-Ende, Punktkontakt) ===== -->
    <joint name="leg_${id}_foot_joint" type="fixed">
      <parent link="leg_${id}_tibia_link"/>
      <child  link="leg_${id}_foot_link"/>
      <origin xyz="${tibia_length} 0 0" rpy="0 0 0"/>
    </joint>

    <link name="leg_${id}_foot_link">
      <visual>
        <geometry>
          <sphere radius="${foot_radius}"/>
        </geometry>
        <material name="black"/>
      </visual>
      <collision>
        <geometry>
          <sphere radius="${foot_radius}"/>
        </geometry>
      </collision>
      <xacro:sphere_inertia mass="${foot_mass}" radius="${foot_radius}"/>
    </link>

  </xacro:macro>

</robot>
```

> **Wichtige Designdetails:**
> - Visual+Collision Origins um `length/2` versetzt → die Box wächst
>   vom Joint weg in +X-Richtung. Macht die Kette sauber referenzierbar.
> - Tibia → Foot ist `fixed`, kein Joint. Foot ist nur ein Frame plus
>   Kollisionskugel.
> - Coxa-Achse ist Z (Schwenken), Femur und Tibia sind Y (Heben/Knicken).
>   Wenn Bein in falsche Richtung geht: Achse invertieren (`0 0 -1`)
>   ist meist einfacher als RPY anpassen.

---

## Top-Level URDF

`urdf/hexapod.urdf.xacro`:

```xml
<?xml version="1.0"?>
<robot name="hexapod" xmlns:xacro="http://www.ros.org/wiki/xacro">

  <xacro:include filename="hexapod_physical_properties.xacro"/>
  <xacro:include filename="materials.xacro"/>
  <xacro:include filename="inertials.xacro"/>
  <xacro:include filename="leg.xacro"/>

  <!-- ===== Base ===== -->
  <link name="base_link">
    <visual>
      <geometry>
        <box size="${body_length} ${body_width} ${body_height}"/>
      </geometry>
      <material name="grey"/>
    </visual>
    <collision>
      <geometry>
        <box size="${body_length} ${body_width} ${body_height}"/>
      </geometry>
    </collision>
    <xacro:box_inertia mass="${base_mass}"
                       x="${body_length}" y="${body_width}" z="${body_height}"/>
  </link>

  <!-- ===== Beine ===== -->
  <xacro:leg id="1"
             mount_x="${ body_length/2}" mount_y="${-body_width/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${-pi/4}"/>
  <xacro:leg id="2"
             mount_x="0"                 mount_y="${-body_width_middle/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${-pi/2}"/>
  <xacro:leg id="3"
             mount_x="${-body_length/2}" mount_y="${-body_width/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${-3*pi/4}"/>
  <xacro:leg id="4"
             mount_x="${-body_length/2}" mount_y="${ body_width/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${ 3*pi/4}"/>
  <xacro:leg id="5"
             mount_x="0"                 mount_y="${ body_width_middle/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${ pi/2}"/>
  <xacro:leg id="6"
             mount_x="${ body_length/2}" mount_y="${ body_width/2}"
             mount_z="${leg_mount_z}"    mount_yaw="${ pi/4}"/>

</robot>
```

---

## Launch-File `display.launch.py`

`launch/display.launch.py` (Pseudocode-Skizze, vollständige
Implementierung in Phase 2 von Claude Code zu erstellen):

```python
# Aufgaben:
# 1. Pfad zur Xacro-Datei finden
# 2. xacro-Verarbeitung zur Laufzeit (Command-Substitution)
# 3. Knoten:
#    - robot_state_publisher (mit robot_description als Parameter)
#    - joint_state_publisher_gui (Slider-GUI)
#    - rviz2 (mit -d config/view.rviz)
```

> **Verbindlich:** Python-Launch-File, kein XML.

Test:

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_description
source install/setup.bash
ros2 launch hexapod_description display.launch.py
```

In RViz:
- Fixed Frame: `base_link`
- Add → RobotModel
- Add → TF
- Speichern unter `config/view.rviz`

---

## URDF validieren

```bash
ros2 run xacro xacro \
  src/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/hexapod.urdf
check_urdf /tmp/hexapod.urdf
```

`check_urdf` muss den Baum vollständig drucken.

tf-Tree visualisieren:

```bash
ros2 run tf2_tools view_frames
# erzeugt frames.pdf — muss alle 6 Beine bis foot_link enthalten
```

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Links weiß im RViz | Material fehlt oder falsch referenziert | `<material name="..."/>` prüfen, `materials.xacro` includen |
| Bein dreht in falsche Richtung | Joint-Achse falsch | Achse invertieren (`0 0 -1`) |
| Bein „explodiert" beim Joint-Slider | Origin-Offset falsch | parent-Frame-Origin prüfen, `length/2`-Offsets der Boxen |
| `joint_state_publisher_gui` zeigt keine Slider | Joints sind `fixed` statt `revolute` | außer `foot_joint` müssen alle revolute sein |
| RViz zeigt nichts, „No tf data" | `robot_state_publisher` nicht gestartet | Parameter `robot_description` prüfen |
| Foot-Frame fehlt in `view_frames` | Foot-Joint falsch deklariert | Typ `fixed`, parent=tibia, child=foot |
| Tibia ragt durch Foot-Kugel | Origin der Foot-Kollision falsch | Foot-Joint origin = `${tibia_length} 0 0` |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Gazebo, keine Physik, keine Sim
- Kein `<ros2_control>`-Block im URDF (Phase 4)
- Keine Selbstkollision aktivieren (Phase 3 falls überhaupt)
- Keine Mesh-Dateien
- Keine Sensoren

---

## Phasenabschluss

- [ ] Alle 6 Done-Kriterien erfüllt
- [ ] `check_urdf` grün, tf-Tree vollständig (inkl. foot_link)
- [ ] README in `hexapod_description/` aktuell
- [ ] `package.xml` ohne `TODO:`-Stubs
- [ ] Timeshift-Snapshot `phase_2_done`
- [ ] Git-Commit + Tag `phase-2-done`
- [ ] `PHASE.md` auf Phase 3 aktualisiert
