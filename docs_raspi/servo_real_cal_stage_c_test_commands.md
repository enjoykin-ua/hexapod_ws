# Stage C — Direction-Cal Test-Commands

> Operative Anleitung zur Direction-Cal pro Servo-Pin. Plan + Konzept:
> [`servo_real_cal_stage_c_plan.md`](servo_real_cal_stage_c_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (hexapod_hardware mit Servo2040 + USB)
> - `T2` = Sim-Stack als visuelle Referenz (Gazebo headless oder RViz allein)
> - `T3` = Joint-Trajectory-Publisher + Live-Param-Sets + Inspection
>
> User führt aus, gibt pro Bein/Joint kurz Status (✓ stimmt / ❌ direction
> flippen + welcher Pin).

---

## VORBEREITUNG — vor Session

**Sicherheit zuerst:**
- ✅ Hexapod aufgebockt (Beine ohne Bodenkontakt)
- ✅ Hardware-Kill-Switch (Stromtrennung Servo-PSU) griffbereit
- ✅ Augen weg von Beinen beim ersten Test pro Bein

**Workspace gebaut + gesourct in allen 3 Terminals:**
```bash
cd ~/hexapod_ws
colcon build
source install/setup.bash
```

---

## SCHRITT 1 — Plugin starten (HW)

**T1 (Plugin):**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartung in T1:**
- Log: `Stage 0.5: /hexapod_safety_reset service ready`
- Log: `Stage 0.6: /hexapod_safety_freeze service ready`
- Log: `controller_manager` aktiv, 6 controllers loaded
- KEINE ERROR-Logs

**Falls Servo2040 nicht erreichbar** (kein /dev/ttyACM0): STOP, USB
prüfen, Stromversorgung Servo2040 prüfen.

---

## SCHRITT 2 — RViz als Sim-Referenz starten

**T2 (RViz):**
```bash
ros2 launch hexapod_description display.launch.py
```

> **Hinweis:** display.launch.py startet RViz mit dem URDF und einem
> `joint_state_publisher` + `robot_state_publisher`. Die Joint-Position
> in RViz ist das was der URDF + JointTrajectoryController vorgibt
> (nicht das was die HW tatsächlich macht — wir vergleichen die zwei
> visuell).

**Alternative wenn display.launch.py nicht da ist oder andere Sim-Stack
gewollt:** Gazebo via `sim.launch.py` parallel zu T1 starten. Aber
Achtung: gz_ros2_control vs hexapod_hardware können nicht gleichzeitig
denselben Joint-Pool besitzen — daher zwei separate ros2_control-
Sessions nötig (different namespaces oder different Hosts).

**Pragmatisch:** RViz allein reicht für visuelle Direction-Reference.

---

## SCHRITT 3 — Sanity-Check: leg_6 (Phase-10-Anker)

**T3:**

leg_6 hat im YAML direction=-1/-1/+1 aus Phase 10 vorgespeichert. Test
diese drei Joints — sollten ohne flip stimmen.

### 3a — leg_6_coxa (pin 15)

```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Beobachten:**
- **RViz (T2):** leg_6 dreht visuell in eine Richtung
- **HW (sichtbar am Roboter):** leg_6 coxa-Servo dreht in...
- **Match?** ✓ oder ❌

### 3b — leg_6_femur

```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

Beobachten + Match? ✓ oder ❌

### 3c — leg_6_tibia

```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

Beobachten + Match? ✓ oder ❌

### 3d — Zurück auf Neutral

```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Wenn leg_6 nicht stimmt:** überraschend (Phase 10 hatte's verifiziert).
STOP, melden — könnte sein dass Mount geändert wurde oder anderer Bug.

---

## SCHRITT 4 — leg_1 (Default direction=+1, unbekannt)

Test für jeden der 3 Joints analog zu Schritt 3. Wenn ein Joint
**nicht** mit RViz stimmt, direction flippen via Live-Param.

### 4a — leg_1_coxa (pin 0)

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

Match? Wenn ❌:
```bash
ros2 param set /hexapodsystem pin_0.direction -1
```
Dann Test wiederholen, jetzt sollte's stimmen.

Falls weiterhin ❌: STOP, melden.

### 4b — leg_1_femur (pin 1)

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

Match? Wenn ❌: `ros2 param set /hexapodsystem pin_1.direction -1` + Re-Test.

### 4c — leg_1_tibia (pin 2)

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

Match? Wenn ❌: `ros2 param set /hexapodsystem pin_2.direction -1` + Re-Test.

### 4d — Zurück auf Neutral

```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

---

## SCHRITT 5 — leg_5 (pins 12-14)

Analog zu Schritt 4, ersetze `leg_1` → `leg_5` und `pin_0/1/2` → `pin_12/13/14`.

Falls direction-Flip nötig:
```bash
ros2 param set /hexapodsystem pin_12.direction -1   # coxa
ros2 param set /hexapodsystem pin_13.direction -1   # femur
ros2 param set /hexapodsystem pin_14.direction -1   # tibia
```

---

## SCHRITT 6 — leg_4 (pins 9-11)

Analog. Pin-Map: 9=coxa, 10=femur, 11=tibia. Topic: `/leg_4_controller/joint_trajectory`.

---

## SCHRITT 7 — leg_3 (pins 6-8)

Analog. Pin-Map: 6=coxa, 7=femur, 8=tibia. Topic: `/leg_3_controller/joint_trajectory`.

---

## SCHRITT 8 — leg_2 (pins 3-5)

Analog. Pin-Map: 3=coxa, 4=femur, 5=tibia. Topic: `/leg_2_controller/joint_trajectory`.

> **Achtung leg_2:** wegen Mount-Tausch 2026-05-24 ist die direction-
> Map am unbekanntesten. Erwarte ggf. alle 3 flips nötig.

---

## SCHRITT 9 — Direction-Map persistieren

Alle direction-Werte sind jetzt im Plugin-RAM geändert. **Save:**

**T3:**
```bash
ros2 service call /save_calibration std_srvs/srv/Trigger
```

**Erwartung:**
- `success: True`
- `message: "saved 18 cals to install/.../servo_mapping.yaml (backup as .bak-<timestamp>)"`

**Install → src kopieren** (damit's in Git landet):
```bash
cp install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml \
   src/hexapod_hardware/config/servo_mapping.yaml
```

---

## SCHRITT 10 — Sauber Beenden

In dieser Reihenfolge Strg+C:
1. **T3** — (alle aktiven Publisher)
2. **T2** — RViz / Sim
3. **T1** — Plugin (sauberes Plugin-Disable über controller_manager)

**Erwartung:** Servos gehen in „Disable"-Modus (kein Drehmoment), Beine
hängen lose. Keine zombie-Prozesse: `ps aux | grep -E "ros2|hexapod" | grep -v grep` zeigt nichts.

---

## STATUS-MELDUNG AN CLAUDE

Nach allem kurz dieses Format:

```
Stage C Direction-Cal (2026-05-XX):

leg_6 (Sanity, Phase-10-Anker):
  pin 15 coxa  : ✓ / ❌
  pin 16 femur : ✓ / ❌
  pin 17 tibia : ✓ / ❌

leg_1:
  pin 0 coxa   : ✓ original / ❌ flipped to -1
  pin 1 femur  : ✓ / ❌
  pin 2 tibia  : ✓ / ❌

leg_5:
  pin 12       : ✓ / ❌
  ...

leg_4: ...
leg_3: ...
leg_2 (post-Mount-Tausch): ...

Save-Service: ✓ /  ❌

Auffälligkeiten:
  - safety_freeze trigger? <ja/nein, bei welchem Pin>
  - Servo-Brummen / Anschlag-Berührung? <ja/nein>
```

---

## FALLBACK-Diagnose

### Wenn safety_freeze triggert

```bash
# Reset:
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger

# Aktuellen Plugin-Param-State checken:
ros2 param get /hexapodsystem pin_<N>.direction
ros2 param get /hexapodsystem pin_<N>.pulse_min
ros2 param get /hexapodsystem pin_<N>.pulse_zero
ros2 param get /hexapodsystem pin_<N>.pulse_max
```

### Wenn Topic-Publish keine Bewegung auslöst

```bash
# Check ob Joint im URDF richtig benannt:
ros2 topic info /leg_<N>_controller/joint_trajectory

# Check ob Controller aktiv:
ros2 control list_controllers
```

### Wenn HW vs RViz nicht eindeutig vergleichbar

Größeren Joint-Command publishen (z.B. ±0.5 rad statt ±0.3) damit
Bewegung deutlicher sichtbar — aber NUR wenn vorheriger Test ohne
safety_freeze + ohne Mech-Anschlag-Brummen geklappt hat.
