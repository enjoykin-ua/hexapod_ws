# Stage C — Direction-Cal Test-Commands

> Operative Anleitung zur Direction-Cal pro Servo-Pin. Plan + Konzept:
> [`servo_real_cal_stage_c_plan.md`](servo_real_cal_stage_c_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (hexapod_hardware mit Servo2040 + USB)
> - `T2` = RViz als visuelle URDF-Referenz
> - `T3` = Joint-Trajectory-Publisher + Inspection
> - `T4` = rqt_reconfigure (Live-Param-GUI für direction-Flips per Mausklick)
>
> **Warum nur RViz, kein Gazebo:** Gazebo nutzt `gz_ros2_control` —
> dieses Plugin und `hexapod_hardware` können nicht gleichzeitig auf
> denselben Joint-Pool zugreifen (ros2_control-Constraint). RViz nur
> nutzt das URDF + JointStatePublisher und zeigt die per-Trajectory
> kommandierten Joint-Werte als Visualisierung. Genau das was wir für
> Direction-Vergleich brauchen.
>
> User führt aus, gibt pro Bein/Joint kurz Status (✓ stimmt / ❌ direction
> flippen + welcher Pin).

---

## VORBEREITUNG — vor Session

**Sicherheit zuerst:**
- ✅ Hexapod aufgebockt (Beine ohne Bodenkontakt)
- ✅ Hardware-Kill-Switch (Stromtrennung Servo-PSU) griffbereit
- ✅ Augen weg von Beinen beim ersten Test pro Bein

**Was beim Plugin-Start passiert** (Schritt 1):
- Plugin sendet beim Activate **pulse_zero** pro Pin = kalibrierte
  Neutral-Pose (Coxa radial nach außen, Femur horizontal, Tibia gerade)
- Das ist die Stand-Pose, **nicht** pulse_min oder pulse_max → kein
  mechanischer Anschlag-Stress
- Bei aufgebockt: Beine hängen, Servos halten Stand-Pose mit Drehmoment

**Was beim Joint-Trajectory-Publish in Schritten 3-8 passiert:**
- rad=±0.3 ist **weit innerhalb** aller URDF-Joint-Limits (engste
  Range ist leg_3 tibia_upper=+1.185 rad → 0.3 nutzt 25%)
- Bei falscher direction: Servo dreht in andere Richtung als RViz, aber
  PWM bleibt innerhalb [pulse_min, pulse_max] → kein Schaden
- Stage 0.5 safety_freeze ist aktiv: falls PWM doch out-of-range
  (z.B. wegen Cal-Bug), Plugin friert sofort ein

**Workspace gebaut + gesourct in allen 4 Terminals:**
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

## SCHRITT 2 — RViz als URDF-Referenz starten

**T2 (RViz):**
```bash
ros2 launch hexapod_description display.launch.py with_jsp_gui:=false
```

> **`with_jsp_gui:=false` ist wichtig:** ohne diesen Arg startet
> `display.launch.py` auch `joint_state_publisher_gui` der ebenfalls
> `/joint_states` publisht — Race mit dem Plugin-Echo aus T1, RViz
> springt zwischen beiden Quellen. Mit dem Arg läuft `joint_state_-
> publisher_gui` nicht, /joint_states kommt nur vom Plugin.
>
> **Was passiert:** `display.launch.py` startet RViz mit dem URDF +
> `robot_state_publisher`. Die Joint-Position in RViz reflektiert die
> aktuellen `/joint_states` — und das Plugin in T1 publisht
> `/joint_states` mit den aus den Joint-Trajectory-Commands abgeleiteten
> rad-Werten.
>
> **Was du in RViz siehst:** die Joints folgen der **URDF-Konvention**
> wie sie ros2_control + Plugin sie verarbeitet.
> **Was du am Hexapod siehst:** die mechanische Drehrichtung des Servos.
>
> Stimmen beide überein → direction richtig. Stimmen sie NICHT überein
> → direction muss geflippt werden.

---

## SCHRITT 2b — rqt_reconfigure öffnen (für direction-Flips per GUI)

**T4 (rqt_reconfigure):**
```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

> **Was du dort siehst:** Plugin-Node `/hexapodsystem` mit 72 Live-Cal-
> Params (18 Pins × 4 Felder: pulse_min, pulse_zero, pulse_max,
> direction). Plus die gait_node-Params falls gait läuft (in Stage C
> nicht).
>
> **Für direction-Flip:** Pin auswählen, Param `pin_<N>.direction`
> finden, von `1` auf `-1` (oder umgekehrt) setzen. Sofort wirksam,
> kein Neustart nötig.
>
> **Alternative via CLI** (falls rqt nicht passt):
> ```bash
> ros2 param set /hexapodsystem pin_<N>.direction -1
> ```

---

## SCHRITT 3 — Direction-Cal pro Joint-Sorte (alle 6 Beine)

**T3:**

Vorgehen: ein Joint-Typ (Coxa / Femur / Tibia) nach dem anderen über
ALLE 6 Beine. Pro Bein 1 Befehl publishen, in RViz vs HW vergleichen,
ggf. direction flippen, dann nächstes Bein. Reihenfolge **leg_6
zuerst** als Sanity-Anker (Phase-10-direction `-1/-1/+1` ist im YAML
vorgespeichert — sollte ohne flip stimmen, sonst überraschend).

**Pin-Map:**

| Bein | coxa pin | femur pin | tibia pin |
|---|---|---|---|
| leg_1 | 0 | 1 | 2 |
| leg_2 | 3 | 4 | 5 |
| leg_3 | 6 | 7 | 8 |
| leg_4 | 9 | 10 | 11 |
| leg_5 | 12 | 13 | 14 |
| leg_6 | 15 | 16 | 17 |

> **Pro Befehl-Block unten:** publish → 2 s warten (Trajectory-Zeit) →
> RViz vs HW vergleichen → ✓ notieren ODER `pin_<N>.direction` in T4
> (rqt_reconfigure) flippen → Befehl nochmal publishen → ✓ notieren.
> Dann zum nächsten Bein.

---

### 3a — Coxa-Test, alle 6 Beine (rad=+0.3 auf Coxa)

**leg_6 (pin 15, Sanity-Anker — sollte stimmen)**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_1 (pin 0)**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_2 (pin 3)**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_3 (pin 6)**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_4 (pin 9)**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_5 (pin 12)**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**Direction-Flip falls nötig** (statt Mausklick in T4 rqt):
```bash
ros2 param set /hexapodsystem pin_<N>.direction -1
# Dann Trajectory-Befehl für betroffenes Bein nochmal publishen
```

---

### 3b — Femur-Test, alle 6 Beine (rad=+0.3 auf Femur)

**leg_6 (pin 16, Sanity-Anker)**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_1 (pin 1)**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_2 (pin 4)**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_3 (pin 7)**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_4 (pin 10)**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_5 (pin 13)**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, 0.3, 0.0], time_from_start: {sec: 2}}]}'
```

---

### 3c — Tibia-Test, alle 6 Beine (rad=+0.3 auf Tibia)

**leg_6 (pin 17, Sanity-Anker)**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

**leg_1 (pin 2)**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

**leg_2 (pin 5)**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

**leg_3 (pin 8)**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

**leg_4 (pin 11)**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

**leg_5 (pin 14)**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.3], time_from_start: {sec: 2}}]}'
```

---

### 3d — Alle 6 Beine zurück auf Neutral (rad=0)

**leg_6**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_1**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_2**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_3**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_4**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

**leg_5**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

> **leg_6 Sanity-Check fail (3a/3b/3c gibt ❌)?** Überraschend — Phase 10
> hatte verifiziert. STOP, melden. Mögliche Ursachen: Mount geändert,
> servo_mapping.yaml manipuliert, Bug.

> **leg_2 unbekannt:** Mount-Tausch 2026-05-24 hat die direction-Map
> verändert. Erwarte ggf. mehrere Flips an pin_3/4/5.

---

## SCHRITT 4 — Direction-Map persistieren

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

## SCHRITT 5 — Sauber Beenden

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

3a Coxa-Test:
  pin 15 leg_6 : ✓ original / ❌ flipped to -1 (Sanity-Anker, Phase 10)
  pin 0  leg_1 : ✓ / ❌
  pin 3  leg_2 : ✓ / ❌
  pin 6  leg_3 : ✓ / ❌
  pin 9  leg_4 : ✓ / ❌
  pin 12 leg_5 : ✓ / ❌

3b Femur-Test:
  pin 16 leg_6 : ✓ / ❌
  pin 1  leg_1 : ✓ / ❌
  pin 4  leg_2 : ✓ / ❌
  pin 7  leg_3 : ✓ / ❌
  pin 10 leg_4 : ✓ / ❌
  pin 13 leg_5 : ✓ / ❌

3c Tibia-Test:
  pin 17 leg_6 : ✓ / ❌
  pin 2  leg_1 : ✓ / ❌
  pin 5  leg_2 : ✓ / ❌
  pin 8  leg_3 : ✓ / ❌
  pin 11 leg_4 : ✓ / ❌
  pin 14 leg_5 : ✓ / ❌

3d alle zurück auf Neutral: ✓ / ❌
Save-Service:                ✓ / ❌

Auffälligkeiten:
  - safety_freeze trigger? <ja/nein, bei welchem Pin>
  - Servo-Brummen / Anschlag-Berührung? <ja/nein>
  - leg_2 post-Mount-Tausch: <wie viele Flips waren nötig>
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
