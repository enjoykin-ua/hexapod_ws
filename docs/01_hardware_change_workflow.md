# Hardware-Änderungen am Hexapod — Anpassungs-Workflow

> **Zweck:** Cross-Phasen-Referenz. Wenn am Roboter mechanisch etwas geändert
> wird (Bein-Segmente, Servos, Massen, Body-Dimensionen, Foot-Geometrie),
> stehen hier die Dateien, die mitgezogen werden müssen, und die Tests, die
> Drift abfangen. Komplementär zu [00_conventions.md](00_conventions.md), das
> die Konventionen selbst dokumentiert (was und warum) — diese Datei
> dokumentiert das **Wie ändern** (wo, in welcher Reihenfolge, was wird
> automatisch propagiert, was muss manuell mitgepflegt werden).

---

## Single-Source-of-Truth-Prinzip

**Drei Wahrheits-Orte** im Workspace:

1. [hexapod_description/urdf/hexapod_physical_properties.xacro](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
   — alle physikalischen Konstanten (Längen, Massen, Limits, Effort, Foot-Radius).
2. [hexapod_description/urdf/hexapod.urdf.xacro](../src/hexapod_description/urdf/hexapod.urdf.xacro)
   — Bein-Mountpunkt-Formeln (`±body_length/2`, `mount_yaw ∈ {±π/4, ±π/2, ±3π/4}`).
3. [hexapod_kinematics/hexapod_kinematics/config.py](../src/hexapod_kinematics/hexapod_kinematics/config.py)
   — Spiegelung der Werte für die IK-Library, **manuelles Mirror** der xacro.

Punkt 1+2 propagieren xacro-intern automatisch in alle abgeleiteten URDF-
Stellen (Joint-Origins, Inertia, Visual/Collision, ros2_control-Limits).
Punkt 3 ist die einzige manuelle Pflege-Stelle — der Cross-Check-Test
[hexapod_kinematics/test/test_config.py](../src/hexapod_kinematics/test/test_config.py)
fängt Drift ab (`colcon test --packages-select hexapod_kinematics` wird rot).

---

## Änderungs-Szenarien

### 1. Bein-Segment-Größen ändern

**Beispiel:** `femur_length` von `0.07994` auf `0.085` ändern.

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `<xacro:property name="femur_length" value="0.085"/>` setzen.
2. `hexapod_kinematics/config.py` — `_L_FEMUR = 0.085` setzen.
3. `colcon build --packages-select hexapod_kinematics`.
4. `colcon test --packages-select hexapod_kinematics` → muss grün sein (Cross-Check-Test verifiziert).
5. Sim-Neustart: `ros2 launch hexapod_bringup sim.launch.py` — RSP rendert URDF neu.

**Was automatisch propagiert** (keine manuelle Anpassung):
- Joint-Origins (`<origin xyz="${femur_length} 0 0"/>` in `leg.xacro`).
- Box-Inertia (`<xacro:box_inertia x="${femur_length}" .../>`).
- Visual + Collision-Box.
- ros2_control-Block (Limits sind unabhängig von Längen).

**Was zusätzlich zu prüfen:**
- **Stand-Pose-Höhe** ändert sich — Phase-4-Übergabe-Smoke (Phase-5-Stufe-C
  Live-Verifikation) re-laufen lassen. Erwartet: `body_height ≈ 0.055 m`
  ± Längen-Anpassung.
- **IK-Reichweite** ändert sich — Phase-5-Stufe-B-Tests werten das
  automatisch aus (out-of-reach-Test), kein manueller Eingriff nötig.

### 2. Joint-Limits / Servo-Winkel ändern

**Beispiel:** `tibia_upper` von `+1.50` auf `+1.20` reduzieren (z. B. weil
neue Servos einen kleineren Bereich haben).

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `<xacro:property name="tibia_upper" value="1.20"/>`.
2. `hexapod_kinematics/config.py` — `_TIBIA_LIMITS = (-1.50, 1.20)`.
3. `colcon build --packages-select hexapod_description hexapod_kinematics`.
4. `colcon test --packages-select hexapod_kinematics` → grün.
5. Sim-Neustart.

**Was automatisch propagiert:**
- `<limit lower="..." upper="..."/>` in den Joint-Definitionen (`leg.xacro`).
- `<param name="min/max">` im ros2_control-Block (`hexapod.ros2_control.xacro`)
  — **doppeltes Sicherheitsnetz** wie in Phase-4-Stufe-B dokumentiert.

**Was zusätzlich zu prüfen:**
- **IK-Validity** — falls die Stand-Pose `[0, -0.5, 1.0]` außerhalb der neuen
  Limits liegt, muss eine neue Stand-Pose definiert werden. Phase-5-Stufe-B-
  Smoke-Test zeigt das.
- **Hardware-Sicherheit Phase 7** — Software-Limits **und** Servo-
  Endlagen-Hard-Stops (mechanisch oder Strom-Limit) müssen redundant
  passen. Siehe CLAUDE.md §9.

### 3. Servo-Drehmoment / -Geschwindigkeit ändern

**Beispiel:** `joint_effort` von `5.0` Nm auf `8.0` Nm (stärkere Servos).

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `joint_effort` und/oder `joint_velocity`.
2. `colcon build --packages-select hexapod_description`.
3. Sim-Neustart.

**Was automatisch propagiert:**
- `<limit effort="..." velocity="..."/>` in allen Joint-Definitionen (`leg.xacro`).

**Was NICHT betroffen ist:**
- `hexapod_kinematics/config.py` — IK ist drehmoment-/geschwindigkeitsfrei.
  Cross-Check-Test ignoriert diese Werte (er prüft nur Längen + Position-Limits).

**Was zusätzlich zu prüfen:**
- **Gait-Tempo** — bei höherer Servo-Geschwindigkeit kann `cycle_time T` in
  Phase-5-Stufe-G reduziert werden. Phase-7-Hardware-Sicherheits-Limit
  („erste Bewegung mit reduzierter Geschwindigkeit", siehe CLAUDE.md §9)
  davon unabhängig.

### 4. Massen ändern

**Beispiel:** `base_mass` von `0.5` auf `0.7` (z. B. nach Akku-Upgrade).

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `base_mass`, `segment_mass` oder `foot_mass`.
2. `colcon build --packages-select hexapod_description`.
3. Sim-Neustart.

**Was automatisch propagiert:**
- Inertia-Berechnungen (`<xacro:box_inertia mass="${base_mass}" .../>`).

**Was NICHT betroffen ist:**
- `hexapod_kinematics/config.py` — IK ist massenfrei.
- Reibungswerte (`mu1=mu2=1.0`, `kp`, `kd` in `hexapod.gazebo.xacro`) — bei
  moderaten Massen-Änderungen kein Re-Tuning nötig (Phase-4-Stufe-F bestätigt:
  Default-Reibung trägt die aktuelle Masse mit Drift = 0).

**Was zusätzlich zu prüfen:**
- **Stand-Stabilität** — bei deutlich höherem Gewicht den Phase-4-Stufe-F-
  Drift-Test re-laufen lassen (`gz model -m hexapod -p` über 5 s).
- **Servo-Kapazität (Hardware)** — physische Servos müssen das Gesamtgewicht
  in Stand-Pose tragen. Reine URDF-Frage gibt darauf keine Antwort; das
  prüfst du auf der echten HW oder per Drehmoment-Berechnung.

### 5. Body-Dimensionen ändern (Chassis-Größe)

**Beispiel:** `body_length` von `0.175` auf `0.20` (längeres Chassis).

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `body_length`, `body_width`,
   `body_width_middle`, `body_height`.
2. `hexapod_kinematics/config.py` — `_BODY_LENGTH`, `_BODY_WIDTH`,
   `_BODY_WIDTH_MIDDLE` setzen.
3. `colcon build --packages-select hexapod_description hexapod_kinematics`.
4. `colcon test --packages-select hexapod_kinematics` → grün
   (Mountpunkt-Cross-Check verifiziert).
5. Sim-Neustart.

**Was automatisch propagiert:**
- Base-Link-Visual + Collision + Inertia (`hexapod.urdf.xacro`).
- **Bein-Mountpunkte** (`mount_x="${body_length/2}"` etc. in
  `hexapod.urdf.xacro`) — neue Bein-Positionen, neue IK-Targets.

**Was zusätzlich zu prüfen:**
- **Stand-Pose-Geometrie** ändert sich substanziell — Phase-5-Stufe-C re-validieren.
- **Stütz-Dreieck-Stabilität** beim Tripod-Gait — Phase-5-Stolperfalle
  „Roboter kippt nach hinten/vorne" beachten. Phase-5-Stufe-F ggf. mit
  angepasster `step_length` neu kalibrieren.

### 6. Foot-Geometrie ändern (Radius, Masse)

**Beispiel:** `foot_radius` von `0.008` auf `0.012` (größere Fuß-Kugeln).

**Was zu tun:**
1. `hexapod_physical_properties.xacro` — `foot_radius` und/oder `foot_mass`.
2. `hexapod_kinematics/config.py` — `_FOOT_RADIUS = 0.012`.
3. `colcon build --packages-select hexapod_description hexapod_kinematics`.
4. `colcon test --packages-select hexapod_kinematics` → grün.
5. Sim-Neustart.

**Was automatisch propagiert:**
- Foot-Visual + Collision-Sphere + Sphere-Inertia (`leg.xacro`).
- Reibungs-Block (`hexapod.gazebo.xacro` referenziert `leg_<n>_foot_link`,
  Größe transparent für Reibung).

**Was zusätzlich zu prüfen:**
- **Foot-Mittelpunkt vs. Boden-Kontakt-Punkt** — der Foot-Link-Center liegt
  `foot_radius` über dem Boden. IK rechnet auf Foot-Link-Center, nicht auf
  Kontakt-Punkt. Bei Radius-Änderung verschiebt sich die effektive Stand-
  Höhe — `body_height`-Annahmen in Phase 5 ggf. anpassen.

### 7. Mountpunkt-Konvention ändern (selten)

**Beispiel:** `mount_yaw` von Bein 2 von `-π/2` auf `-π/3` (Bein zeigt jetzt
nicht mehr 90°, sondern 60° nach außen).

**Was zu tun:**
1. `hexapod.urdf.xacro` — `<xacro:leg id="2" ... mount_yaw="${-pi/3}"/>`.
2. `hexapod_kinematics/config.py` — `_LEG_DEFINITIONS` für `leg_2` anpassen.
3. `hexapod_kinematics/test/test_config.py` —
   `test_mount_positions_match_xacro_formulas` Erwartungs-Liste anpassen.
4. `colcon build --packages-select hexapod_description hexapod_kinematics`.
5. `colcon test --packages-select hexapod_kinematics` → grün.

**Was zu beachten:**
- Diese Änderung ist **konventions-relevant** (00_conventions.md §11.3
  beschreibt das aktuelle Layout). Bei Änderung dort auch nachziehen.
- Tripod-Stabilität ändert sich potenziell — Stütz-Dreieck-Geometrie
  prüfen (Phase-5-Stufe-F oder neue Stand-Stabilitäts-Verifikation).

---

## Verifikations-Checkliste (nach jeder Änderung)

```bash
# 1. URDF parst sauber
xacro src/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/hexapod.urdf
check_urdf /tmp/hexapod.urdf

# 2. hexapod_kinematics baut + Cross-Check grün
colcon build --packages-select hexapod_description hexapod_kinematics
source install/setup.bash
colcon test --packages-select hexapod_kinematics --event-handlers console_direct+

# 3. Sim startet sauber
ros2 launch hexapod_bringup sim.launch.py

# 4. Stand-Pose-Drift
ros2 topic pub --once /leg_1_controller/joint_trajectory ... [0, -0.5, 1.0]
# (sechsmal für alle Beine, dann 5 Sekunden gz model -m hexapod -p)
```

Welche Tests in welcher Phase verfügbar sind:
- Phase 4 abgeschlossen: `colcon build`, `xacro`-Parse, Sim-Launch, Stand-Drift.
- Phase 5 ab Stufe A: Cross-Check-Test in `hexapod_kinematics`.
- Phase 5 ab Stufe B: IK/FK-Round-Trip-Tests, IK-Reichweite-Tests.
- Phase 5 ab Stufe D: Foot-Kontakt-Topics als Live-Diagnose verfügbar
  (Toggle-bar, siehe Phase-5-Stufe-D).

---

## Was diese Datei NICHT abdeckt

- **Servo2040-Firmware-Anpassungen** (Phase 7) — separate
  Hardware-Doku, sobald Phase 7 aktiv ist.
- **Mesh-Dateien (CAD-Visuals)** — aktuell nutzt der Hexapod nur primitive
  Box/Sphere-Visuals, keine Meshes. Wenn eingeführt: Mesh-Pfade über
  `package://hexapod_description/meshes/...` referenzieren, dann
  `colcon build` nicht vergessen wegen Resource-Install.
- **Reibungs-/Damping-Tuning** — siehe `hexapod_gazebo/README.md`,
  Phase-3- und Phase-4-Doku.
- **Inertien aus echtem CAD** — aktuell aus Box-Approximation berechnet
  (`inertials.xacro`). Wenn präzisere CAD-Inertien vorliegen, dort
  einsetzen, dann auf `# TODO: from CAD`-Kommentare achten (CLAUDE.md §8).
