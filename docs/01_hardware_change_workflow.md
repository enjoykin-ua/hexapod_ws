# Hardware-Änderungen am Hexapod — Anpassungs-Workflow

> **Zweck:** Cross-Phasen-Referenz. Wenn am Roboter mechanisch etwas geändert
> wird (Bein-Segmente, Servos, Massen, Body-Dimensionen, Foot-Geometrie) ODER
> am Hardware-Anbindungs-Stack (Servo-Kalibrierung, USB-Port, Loopback,
> Sim↔HW-Switch), stehen hier die Dateien, die mitgezogen werden müssen, und
> die Tests, die Drift abfangen. Komplementär zu
> [00_conventions.md](00_conventions.md), das die Konventionen selbst
> dokumentiert (was und warum) — diese Datei dokumentiert das **Wie ändern**
> (wo, in welcher Reihenfolge, was wird automatisch propagiert, was muss
> manuell mitgepflegt werden).
>
> **Zwei Schichten von Quellen:** der „Roboter-Modell-Stack" (Phasen 0–5,
> Single-Source-of-Truth-Prinzip unten) und der „Hardware-Anbindungs-Stack"
> (Phase 7 ff., siehe Abschnitt „Hardware-Quellen-Stack ab Phase 9"). Die
> beiden Schichten sind **orthogonal** — Änderungen in der einen verlangen
> in den meisten Fällen keine Anpassung in der anderen.

---

## Single-Source-of-Truth-Prinzip (Roboter-Modell, Phasen 0–5)

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

## Hardware-Quellen-Stack ab Phase 9

Mit Phase 7 (Servo2040-Firmware) + Phase 9 (`hexapod_hardware`-Plugin)
kommen **drei zusätzliche Wahrheits-Orte** für die Hardware-Anbindung
hinzu — parallel zu den Roboter-Modell-Quellen oben, aber **orthogonal**:

4. [hexapod_servo_driver/](https://github.com/enjoykin-ua/hexapod_servo_driver) — separates Repo,
   Firmware auf dem Servo2040. Wire-Protokoll definiert in
   [PROTOCOL.md](https://github.com/enjoykin-ua/hexapod_servo_driver/blob/main/PROTOCOL.md).
   Endet an der USB-CDC-Schnittstelle. Wird in Phase 7 entwickelt und
   anschließend mit Tag `phase-7-done` eingefroren — solange das
   Wire-Protokoll Version 1.x bleibt, hier nichts anfassen.
5. [hexapod_hardware/config/servo_mapping.yaml](../src/hexapod_hardware/config/servo_mapping.yaml)
   — Servo-Pin → Joint-Name + Pulse-Kalibrierung (`pulse_min/zero/max`,
   `direction`) pro Servo. **Canonical Source** liegt im fw-Repo unter
   `contrib/servo_mapping.yaml`, wird in `hexapod_hardware/config/`
   gespiegelt. Phase-10-Kalibrierungstool schreibt diese Datei.
6. [hexapod_description/urdf/hexapod.ros2_control.xacro](../src/hexapod_description/urdf/hexapod.ros2_control.xacro)
   — `<param>`-Block für das Plugin: `serial_port`, `calibration_file`,
   `loopback_mode`. Wird in Phase 9 Stufe F erweitert um den
   `use_sim:=true|false`-Xacro-Switch für Sim ↔ HW.
7. [hexapod_control/config/controllers.real.yaml](../src/hexapod_control/config/controllers.real.yaml)
   *(kommt in Phase 9 Stufe F)* — HW-spezifische Controller-Limits
   (reduzierte vel/accel gegenüber Sim-Werten), `use_sim_time:false`.

**Warum die Trennung sauber funktioniert:** im **Direct-Drive-Setup**
(Servo-Welle = Joint-Achse) dreht jeder Servo dieselbe Anzahl Radiant
für dieselbe Pulsbreite — unabhängig von Beinlänge, Massen oder
Mountpunkten. Geometrie- und Mechanik-Änderungen wirken sich auf den
Roboter-Modell-Stack (Quellen 1–3) aus, **nicht** auf die Servo-
Kalibrierung (Quelle 5). Begründung in
[docs_raspi/phase_9_progress.md](../docs_raspi/phase_9_progress.md)
„Design-Entscheidung Option C".

---

## Änderungs-Szenarien

**Übersicht der Szenarien:**

| # | Szenario | Quelle die betroffen ist |
|---|---|---|
| 1 | Bein-Segment-Größen | URDF Konstanten + IK-config.py |
| 2 | Joint-Limits / Servo-Winkel | URDF Konstanten + IK-config.py |
| 3 | Servo-Drehmoment / -Geschwindigkeit (URDF-Werte) | URDF Konstanten |
| 4 | Massen | URDF Konstanten |
| 5 | Body-Dimensionen | URDF Konstanten + IK-config.py |
| 6 | Foot-Geometrie | URDF Konstanten + IK-config.py |
| 7 | Mountpunkt-Konvention (selten) | URDF + IK-config.py + Test |
| 8 | Servo gegen anderes Modell tauschen | `servo_mapping.yaml` |
| 9 | Servo gespiegelt / gedreht montieren | `servo_mapping.yaml` |
| 10 | USB-Port wechselt | `hexapod.ros2_control.xacro` `<param>` |
| 11 | Loopback-Modus für CI aktivieren | `hexapod.ros2_control.xacro` `<param>` |
| 12 | Sim ↔ Hardware umschalten (Phase 9 Stufe F) | Launch-Argument `use_sim` |

---

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

### 8. Servo gegen ein anderes Modell tauschen

**Beispiel:** Stall-Servo verbrannt, neuer Servo (anderes Modell, anderer
PWM-Bereich: statt 500–2500 µs jetzt 800–2200 µs, andere Steigung µs/rad).

**Was zu tun:**
1. `hexapod_hardware/config/servo_mapping.yaml` — für den betroffenen Servo-
   Pin den Eintrag aktualisieren: `pulse_min`, `pulse_max`, ggf. `pulse_zero`
   neu setzen.
2. **Empfohlen:** Phase-10-Kalibrierungstool laufen lassen (sobald
   verfügbar) — fährt automatisch zu den mechanischen Anschlägen und
   schreibt die echten Werte ins YAML zurück.
3. Manuelle Alternative bis dahin: per `ros2 topic pub` einzelnen Joint
   schrittweise jog'en, mechanischen Anschlag identifizieren, Pulse-Wert
   notieren, ins YAML eintragen.
4. `colcon build --packages-select hexapod_hardware` (YAML wird ins
   install/share kopiert).
5. Plugin neu starten (Stack restarten).

**Was automatisch propagiert:**
- `Calibration::load_from_file` parst die neuen Werte beim nächsten
  `on_init`. Piecewise-linear Konversion rechnet mit den neuen
  Steigungen automatisch.

**Was NICHT betroffen ist:**
- URDF — Joint-Limits (mechanisch) bleiben unverändert solange der neue
  Servo die gleiche Joint-Range schafft.
- `hexapod_kinematics/config.py` — IK ist servo-frei.
- Firmware — sieht nur Pulse-Bytes, kennt das Servo-Modell nicht.

**Was zusätzlich zu prüfen:**
- Erster Bring-up mit reduzierten Limits in `controllers.real.yaml`
  (CLAUDE.md §9 — Hexapod aufbocken, Hardware-Kill-Switch).

### 9. Servo gespiegelt / um 90° gedreht montieren

**Beispiel:** Coxa-Servo eines Beins wurde gewendet (z.B. nach
Reparatur). Pulse-Zero verschoben oder Drehrichtung relativ zur
URDF-Joint-Achse invertiert.

**Was zu tun:**
1. `hexapod_hardware/config/servo_mapping.yaml` für den betroffenen Pin:
   - `pulse_zero` anpassen (wo ist jetzt die Joint-Mitte in µs?)
   - bei Drehrichtungs-Flip: `direction: -1` setzen (war vorher `+1`)
2. `colcon build --packages-select hexapod_hardware`.
3. Plugin neu starten.

**Was automatisch propagiert:**
- `Calibration::pulse_us_to_radians` und `radians_to_pulse_us` rechnen
  mit der neuen Direction. Echo-State im Plugin bleibt selbst-konsistent.

**Was NICHT betroffen ist:**
- URDF, IK, Gait — alle joint-axis-orientiert, nicht servo-orientiert.

**Was zusätzlich zu prüfen:**
- **Erste Aktivierung sehr vorsichtig** — wenn `direction`-Flip falsch
  herum eingetragen ist, fährt der Servo bei positivem cmd in die
  „falsche" Richtung, möglicherweise gegen einen mechanischen Anschlag.
  Tipp: bei niedrigem Geschwindigkeitslimit testen, Stand-Pose-Ziel
  vorgeben, beobachten, ob das Bein wirklich „runter" geht.
- **Phase-10-Kalibrierungstool** wird (sobald verfügbar) den Direction-
  Test automatisieren: jog +0.1 rad, prüfe ob Bein nach unten oder oben
  fährt, ggf. `direction` flippen.

### 10. USB-Port wechselt (`ttyACM0` → `ttyACM1` o.ä.)

**Beispiel:** Anderer Desktop, anderer Pi, oder anderes USB-Gerät hängt
parallel dran und nimmt den Port `/dev/ttyACM0` weg.

**Was zu tun:**
1. `hexapod.ros2_control.xacro` — im `<param name="serial_port">`-
   Eintrag den neuen Pfad eintragen, z.B. `/dev/ttyACM1`.
2. Plugin neu starten.

**Was automatisch propagiert:**
- `on_init` liest den neuen Pfad, `on_configure` öffnet den.

**Was NICHT betroffen ist:**
- Alles andere.

**Was zusätzlich zu prüfen:**
- User in `dialout`-Gruppe? (`id` → `dialout` muss da sein, sonst
  `EACCES` beim Port-Open).
- **Stable Symlink via `udev` (optional, empfohlen für Pi)** — eine
  `udev`-Regel kann den Servo2040 unabhängig vom Plug-Reihenfolge an
  einen festen Pfad wie `/dev/hexapod_servo2040` binden:
  ```
  # /etc/udev/rules.d/99-hexapod-servo2040.rules
  SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", ATTRS{idProduct}=="0003", \
      SYMLINK+="hexapod_servo2040", GROUP="dialout", MODE="0660"
  ```
  Dann den Symlink im URDF nutzen statt des `ttyACM*`-Pfads.

### 11. Loopback-Modus für CI / Code-Tests aktivieren

**Beispiel:** CI-Pipeline soll das Plugin laden und durchlaufen, ohne
dass eine echte Servo2040-Hardware angeschlossen ist (z.B. PR-Builds).

**Was zu tun:**
1. `hexapod.ros2_control.xacro` — `<param name="loopback_mode">true</param>`.
   Alternativ: Launch-Argument das den `<param>` überschreibt — kommt
   in Phase 9 Stufe G.
2. Plugin neu starten.

**Was Loopback-Mode bewirkt:**
- `on_configure` öffnet **keinen** Serial-Port, startet **keinen**
  Reader-Thread.
- `on_activate` schickt **keine** ENABLE_SERVO-Frames (Stagger-Pause
  wird auf 0 reduziert — fertig in <100 ms statt 900 ms).
- `write()` schickt **keine** SET_TARGETS-Frames, sondern reflektiert
  direkt in `last_command_pulse_us_`.
- `read()` macht weiterhin Echo-State (last_command zurück nach Joint-rad),
  also ist der ros2_control-Stack komplett konsistent — JTC akzeptiert
  Trajectories, JSB publisht `/joint_states`, alles als ob.

**Was NICHT betroffen ist:**
- URDF, IK, Gait, Teleop — alle laufen normal.

**Was zusätzlich zu prüfen:**
- **Vergiss nicht zurückzuschalten** vor echtem HW-Bring-up. Empfehlung:
  zwei verschiedene Launch-Files / Launch-Args (kommt in Stufe G:
  `real.launch.py` mit `loopback:=false` als Default).

### 12. Sim ↔ Hardware umschalten (Phase 9 Stufe F)

**Beispiel:** Du willst denselben Gait-Code einmal in Gazebo (Sim) und
einmal mit echter Servo2040-Hardware fahren.

**Was zu tun (sobald Stufe F implementiert ist):**
- Sim: `ros2 launch hexapod_bringup sim.launch.py` — Default
  `use_sim:=true`, lädt `gz_ros2_control`, nutzt
  `controllers.yaml`.
- HW: `ros2 launch hexapod_bringup real.launch.py` — setzt
  `use_sim:=false`, lädt `hexapod_hardware/HexapodSystemHardware`,
  nutzt `controllers.real.yaml`.

**Was Phase 9 Stufe F dafür einrichtet:**
- URDF (`hexapod.ros2_control.xacro`) bekommt einen `<xacro:if>` der
  zur Build-/Launch-Zeit zwischen `gz_ros2_control` und
  `hexapod_hardware` als Plugin-Klasse wählt.
- `controllers.real.yaml` wird angelegt mit `use_sim_time:false` und
  reduzierten vel/accel-Limits (~30% der Sim-Werte für sicheren Bring-up).

**Was NICHT betroffen ist:**
- Gait, Teleop, IK, alle High-Level-Knoten sind plugin-agnostisch —
  sie sprechen mit dem `controller_manager`, der unter der Haube
  entweder Sim oder HW fährt.

**Was zusätzlich zu prüfen:**
- **HW-Default-Body-Höhe:** `body_height = -0.052` in Sim (Phase-6-
  JTC-Tracking-Lag-Workaround) muss in HW zurück auf `-0.047`. Wird
  in Stufe F als HW-Default gesetzt.

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

- **Servo2040-Firmware-Anpassungen** (Wire-Protokoll, Sicherheits-Schichten,
  Watchdog-Timing, Strom-Limits) — siehe separates Repo
  [hexapod_servo_driver/](https://github.com/enjoykin-ua/hexapod_servo_driver),
  insbesondere [PROTOCOL.md](https://github.com/enjoykin-ua/hexapod_servo_driver/blob/main/PROTOCOL.md)
  und [phase_7_progress.md](../docs_raspi/phase_7_progress.md). Solange
  das Wire-Protokoll bei Version 1.x bleibt, wirkt sich Firmware-Anpassung
  **nicht** auf den hexapod_ws aus (Firmware ist „dumm" — kennt nur
  Pulse-Bytes, keine Joints, keine Kinematik).
- **Mesh-Dateien (CAD-Visuals)** — aktuell nutzt der Hexapod nur primitive
  Box/Sphere-Visuals, keine Meshes. Wenn eingeführt: Mesh-Pfade über
  `package://hexapod_description/meshes/...` referenzieren, dann
  `colcon build` nicht vergessen wegen Resource-Install.
- **Reibungs-/Damping-Tuning** — siehe `hexapod_gazebo/README.md`,
  Phase-3- und Phase-4-Doku.
- **Inertien aus echtem CAD** — aktuell aus Box-Approximation berechnet
  (`inertials.xacro`). Wenn präzisere CAD-Inertien vorliegen, dort
  einsetzen, dann auf `# TODO: from CAD`-Kommentare achten (CLAUDE.md §8).
- **IMU-Anbindung** — wenn IMU dazukommt, eigenes Paket (z.B.
  `hexapod_imu_hardware`) mit eigenem `<ros2_control type="sensor">`-Block.
  Plan: siehe Memory `project_imu_separate_sensor_plugin`.
- **Gait-/Teleop-Parameter-Tuning** — keine Hardware-Änderung; siehe
  jeweilige Paket-READMEs und Phase-5- / Phase-6-Docs.
