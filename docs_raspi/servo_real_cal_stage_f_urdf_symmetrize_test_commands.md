# Stage F (URDF rad-Limits symmetrieren) — Test-Commands

> Operative Anleitung zur URDF-Symmetrisierung. Plan + Konzept:
> [`servo_real_cal_stage_f_urdf_symmetrize_plan.md`](servo_real_cal_stage_f_urdf_symmetrize_plan.md).
>
> **Ersetzt** den archivierten Wasserwaage-Ansatz:
> [`_archive_servo_real_cal_stage_f_femur_wasserwaage_test_commands.md`](_archive_servo_real_cal_stage_f_femur_wasserwaage_test_commands.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (`hexapod_bringup real.launch.py`)
> - `T2` = gait_node (`gait.launch.py` mit sim_walk.yaml)
> - `T3` = cmd_vel-Publisher + Inspect
> - `T4` = optional RViz / rqt_reconfigure
>
> **Reihenfolge:** URDF-Patch → Build → Plugin-Sanity → gait_node-Sanity
> → Walking-Tempo-Treppe → Beenden.

---

## ⚠️ SAFETY — vor Live-Test

- ✅ Hexapod aufgebockt, Beine hängen frei
- ✅ Kill-Switch am Servo-PSU griffbereit
- ✅ 30 cm-Radius frei

**Notfall-Stop:** Kill-Switch zuerst, dann Strg+C in T3 / T2 / T1.

---

## SCHRITT 0 — Pre-Stage-F Backup-Notiz

Vor jedem URDF-Edit: aktuelle Werte als Backup notieren (Git ist eh
Versionierung, das ist nur Sicherheit für Schnell-Rollback).

**T3:**
```bash
cd ~/hexapod_ws
git diff src/hexapod_description/urdf/hexapod.urdf.xacro
git diff src/hexapod_description/urdf/hexapod.ros2_control.xacro
```
Erwartet: leerer Output (= sauberer Stand).

---

## SCHRITT 1 — `hexapod.urdf.xacro` patchen

> **Zielwerte (strict-symmetric für alle 6 Beine):**
> - coxa: `lower="-0.415" upper="0.415"`
> - femur: `lower="-1.493" upper="1.493"`
> - tibia: `lower="-1.161" upper="1.161"`

Datei: `src/hexapod_description/urdf/hexapod.urdf.xacro`

Suche die Sektion mit den 6 `<xacro:leg id="N" ... />`-Aufrufen. Setze
ALLE 6 Aufrufe auf die identischen symmetrischen Werte. Beispiel für
leg_1 — die anderen 5 analog:

**Vorher:**
```xml
<xacro:leg id="1"
           mount_x="${ body_length/2}" mount_y="${-body_width/2}"
           mount_z="${leg_mount_z}"    mount_yaw="${-pi/4}"
           coxa_lower="-0.747"  coxa_upper="0.569"
           femur_lower="-1.529" femur_upper="1.564"
           tibia_lower="-1.920" tibia_upper="1.197"/>
```

**Nachher:**
```xml
<xacro:leg id="1"
           mount_x="${ body_length/2}" mount_y="${-body_width/2}"
           mount_z="${leg_mount_z}"    mount_yaw="${-pi/4}"
           coxa_lower="-0.415"  coxa_upper="0.415"
           femur_lower="-1.493" femur_upper="1.493"
           tibia_lower="-1.161" tibia_upper="1.161"/>
```

**Dasselbe Schema für legs 2-6** (mount_x/y/yaw bleiben unverändert,
nur die 6 rad-Limit-Werte ersetzen).

---

## SCHRITT 2 — `hexapod.ros2_control.xacro` patchen

Datei: `src/hexapod_description/urdf/hexapod.ros2_control.xacro`

Alle 18 `<xacro:joint_iface ...>`-Aufrufe auf identische Werte:

**Pro Bein (Beispiel leg_1, andere 5 analog):**

**Vorher:**
```xml
<xacro:joint_iface name="leg_1_coxa_joint"  lower="-0.747" upper="0.569"/>
<xacro:joint_iface name="leg_1_femur_joint" lower="-1.529" upper="1.564"/>
<xacro:joint_iface name="leg_1_tibia_joint" lower="-1.920" upper="1.197"/>
```

**Nachher:**
```xml
<xacro:joint_iface name="leg_1_coxa_joint"  lower="-0.415" upper="0.415"/>
<xacro:joint_iface name="leg_1_femur_joint" lower="-1.493" upper="1.493"/>
<xacro:joint_iface name="leg_1_tibia_joint" lower="-1.161" upper="1.161"/>
```

**Dasselbe Schema für leg_2 bis leg_6** (joint_name unterscheidet sich
pro Bein, aber lower/upper sind identisch).

---

## SCHRITT 3 — Build + xacro-Verify

**T3:**
```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_description --symlink-install
source install/setup.bash
```

**Erwartet:** Build grün. Falls Build-Error: xacro-Syntax in den editierten
Files prüfen.

**Verifizieren via xacro:**
```bash
xacro $(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/check.urdf
echo "Exit: $?"
grep -c "<limit" /tmp/check.urdf
grep "<limit" /tmp/check.urdf | sort -u | wc -l
```

**Erwartet:**
- Exit 0
- `grep -c` = 18 (= 18 Joints mit Limit-Tags)
- `sort -u | wc -l` = 3 (= drei eindeutige Limit-Werte: coxa, femur, tibia)
  → Beweist dass alle 6 Coxa-Joints, alle 6 Femur-Joints, alle 6
  Tibia-Joints jeweils dieselben Limits haben

Wenn `sort -u` != 3: irgendwo ist noch ein Bein abweichend, suchen mit:
```bash
grep "<limit" /tmp/check.urdf | sort | uniq -c | sort -rn
```

---

## SCHRITT 4 — Plugin starten (T1)

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartet:**
- Plugin-Init-Logs durchgelaufen (`Stage 0.5: /hexapod_safety_reset
  service ready`, 6× `Configured and activated leg_<n>_controller`)
- **KEIN** `safety_freeze`-Trigger
- Alle 6 Beine visuell in T-Pose

**❌ Falls safety_freeze beim Init:** STOP. Heißt: pulse_zero ist
außerhalb der neuen [pulse_min, pulse_max]-Range (sollte nicht passieren
da wir pulse-Werte nicht geändert haben). Plugin-Logs prüfen welcher Pin.

---

## SCHRITT 5 — Controllers prüfen (T3)

**T3:**
```bash
ros2 control list_controllers
```

**Erwartet — alle 7 active:**
```
joint_state_broadcaster    active
leg_1_controller           active
...
leg_6_controller           active
```

---

## SCHRITT 6 — gait_node + Stand-Pose-Symmetrie-Check (T2 + visual)

> **Direkt-Verifikation des Stage F Ziels.** Vor Stage F war die
> Stand-Pose visuell asymmetrisch rechts/links. Nach Stage F sollte
> sie symmetrisch sein.

**T2:**
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

**Erwartet in T2:**
- Log: `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- Log: `gait_node init: pattern=tripod, ..., body_height=-0.070 m
  (range [-0.080, -0.030]), step_length_max=0.035 m
  (linear_max=0.035 m/s) ...`
- KEIN `IKError`
- KEIN `safety_freeze` in T1

**Erwartet visuell:**
- Alle 6 Beine fahren simultan in Stand-Pose
- Stand-Pose **visuell symmetrisch rechts/links** —
  Femur+Tibia rechts (legs 1/2/3) und links (legs 4/5/6) in
  spiegelbildlicher Pose
- 30 s stabil, kein periodisches Zucken

**Vergleich zum Pre-Stage-F-Stand:** wenn du noch das Stage-E2.3-Bild
im Kopf hast (rechts deutlich stärker eingeknickt als links), sollte
das jetzt weg sein.

**Status notieren:** ✓ symmetrisch / ❌ <Symptom>

---

## SCHRITT 7 — Walking-Tempo-Treppe (T3)

> Wiederholung von Stage E2.5 — verifiziert dass Symmetrisierung das
> Walking nicht kaputt macht.

### 7.1 cmd_vel x=0.02

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartet:** Tripod-Walking-Rhythmus, 30 s sauber, keine IKError.

Strg+C nach 30 s.

### 7.2 cmd_vel x=0.03

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**Erwartet:** wie 7.1.

Strg+C nach 30 s.

### 7.3 cmd_vel x=0.035 (linear_max)

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.035}}'
```

**Erwartet:** wie 7.1.

Strg+C nach 30 s.

### 7.4 cmd_vel x=0.04 (Clamp-Verifikation)

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.04}}'
```

**Erwartet:** alle 2 s WARN-Log:
```
[WARN] [gait_node]: cmd_vel clamped: input (vx=0.040, vy=0.000, omega=0.000) > max-leg-speed 0.035 m/s
```

Walking-Visual identisch zu 7.3 (Engine clampt auf 0.035). Keine IKError.

Strg+C.

---

## SCHRITT 8 — (Optional) `sim_walk.yaml` regenerieren

> Mit der jetzt symmetrischen URDF kann der Walking-Envelope-Tool
> neue Werte vorschlagen. Wahrscheinlich nur minimal anders, aber
> Sanity-Run lohnt.

**T3:**
```bash
python3 tools/walking_envelope_check.py recommend \
  --body-height -0.07 --safety-margin 0.10 \
  --output /tmp/sim_walk_post_stage_f.yaml
diff src/hexapod_gait/config/presets/sim_walk.yaml /tmp/sim_walk_post_stage_f.yaml
```

**Erwartet:** Diff zeigt evtl. leicht andere Werte (z.B. step_length_max
± 5 mm, step_height ± 5 mm). Wenn dramatisch (z.B. > 30% Änderung):
auffällig, aber nicht Stage-F-Blocker.

**Bei akzeptablem Diff:**
```bash
cp /tmp/sim_walk_post_stage_f.yaml src/hexapod_gait/config/presets/sim_walk.yaml
colcon build --packages-select hexapod_gait
```

Dann gait_node neu starten und Walking nochmal kurz testen.

**Bei zu großem Diff:** Stage A wird das Thema gründlich behandeln,
können wir jetzt skippen.

---

## SCHRITT 9 — Sauber Beenden

Reihenfolge:
1. T3 — cmd_vel-Publisher (falls noch läuft)
2. T2 — gait_node
3. T1 — Plugin

**Verifikation:**
```bash
ps aux | grep -E "gait_node|controller_manager|hexapod" | grep -v grep
```
→ Erwartet: leer.

---

## Status-Meldung an Claude

Nach Stage F live kurz:

```
Stage F (URDF rad-Limits symmetrieren):
  S1+S2 URDF-Patch:           ✓ / ❌
  S3 colcon build:            ✓ / ❌
  S3 xacro 18 limits, 3 uniq: ✓ / ❌
  S4 Plugin-Start ohne freeze: ✓ / ❌
  S5 Controllers all active:  ✓ / ❌
  S6 gait_node Stand-Pose:    ✓ symmetrisch / ❌ <Symptom>
  S7.1 Walk 0.02:             ✓ / ❌
  S7.2 Walk 0.03:             ✓ / ❌
  S7.3 Walk 0.035:            ✓ / ❌
  S7.4 Walk 0.04 (Clamp-WARN): ✓ / ❌
  S8 sim_walk.yaml regen:     ✓ / skipped / ❌

Beobachtungen:
  - Stand-Pose-Symmetrie visuell:    <perfekt / sehr gut / leichter Rest / unverändert>
  - Walking-Visual:                  <glatt / ruckelig>
  - Servo-Akustik:                   <ruhig / Klick / Brumm>
  - Sonstiges:                       <kurz>
```

---

## Diagnostik bei Problemen

### colcon build-Error im hexapod_description

```bash
xacro src/hexapod_description/urdf/hexapod.urdf.xacro 2>&1 | head -30
```
Zeigt den xacro-Parse-Fehler. Häufige Probleme: Tippfehler in den 6
leg-Calls, fehlende Anführungszeichen, falsche Attribut-Namen.

### Plugin-safety_freeze nach Stage F

Plugin-Logs prüfen welcher Pin out-of-range ist:
```bash
# In T1 visuell scrollen oder filtern:
ros2 topic echo /rosout | grep -i safety_freeze
```

Wenn Pin identifiziert: mathematisch prüfen warum:
- new_joint_lower (= -0.415 / -1.493 / -1.161)
- pulse_zero - pulse_min für direction=+1 oder pulse_max - pulse_zero für direction=-1
- Slope = (pulse-Bereich) / |joint_lower|
- pulse_command bei rad=new_joint_lower muss in [pulse_min, pulse_max] liegen

### IKError bei Stand-Pose

Möglich falls IK-Output für radial=0.295, body_height=-0.07 jetzt
außerhalb der engeren Limits liegt. Sollte nicht — alle Stand-Pose-rad
sind <1.0, und neue Limits sind ≥1.16.

Falls doch:
```bash
ros2 param set /gait_node body_height -0.05      # weniger Crouch
ros2 param set /gait_node radial_distance 0.30   # Foot weiter aus
```

### Stand-Pose visuell weiterhin asymmetrisch

Theoretisch sollte das nach §3.3-Math nicht passieren (Differenz <1°).
Wenn doch sichtbar:
- Foto vorher/nachher vergleichen — vielleicht subjektive Wahrnehmung
- pulse_zero pro Femur visuell prüfen (Wasserwaage) — der alte
  Wasserwaage-Ansatz als Folge-Fix möglich (siehe archivierte Stage F)

---

**Erstellt 2026-05-25. Plan + Konzept in
[`servo_real_cal_stage_f_urdf_symmetrize_plan.md`](servo_real_cal_stage_f_urdf_symmetrize_plan.md).**
