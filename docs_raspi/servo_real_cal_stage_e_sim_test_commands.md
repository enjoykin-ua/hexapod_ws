# Stage E (Sim-Vorab) — Test-Commands

> Operative Anleitung für die Sim-Walking-Verifikation **vor** Stage C
> (HW-Direction-Cal). Plan und Erfolgs-Kriterien:
> [`servo_real_cal_stage_e_sim_plan.md`](servo_real_cal_stage_e_sim_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Sim-Stack (Gazebo + ros2_control)
> - `T2` = gait_node (separate Konsole damit Logs lesbar bleiben)
> - `T3` = cmd_vel-Publisher / ros2 service / Inspection
> - `T4` = (optional) rviz2 + extra Tools
>
> User führt aus, meldet kurz Status (✓ / ❌ + 1-Zeilen-Symptom).

---

## Pre-Setup (alle Terminals)

```bash
cd ~/hexapod_ws
colcon build
source install/setup.bash
```

**Erwartung:** alle 4 Pakete grün. Wenn nicht: STOP, melden.

---

## Schritt 1 — Sim-Stack starten

**T1 (Sim):**
```bash
ros2 launch hexapod_bringup sim.launch.py
```

**Erwartung:**
- Gazebo-Window öffnet
- Hexapod spawnt mittig — alle 6 Beine sichtbar, radial nach außen ausgestreckt
- Body schwebt knapp über dem Boden
- Im Terminal **keine** Errors mit „URDF parse" / „joint limit violation" / „xacro"
- Im Terminal ist sichtbar: `joint_state_broadcaster started successfully` und 6× `leg_<n>_controller` aktive Logs

**Wenn Hexapod verdreht aussieht ODER ein Bein durch Boden klappt:** STOP.
URDF-Limits aus Stage D haben einen Fehler. → ❌ melden mit Screenshot.

---

## Schritt 2 — Controllers prüfen

**T3 (Inspection):**
```bash
ros2 control list_controllers
```

**Erwartung — exakt diese 7 Einträge:**
```
joint_state_broadcaster    active
leg_1_controller           active
leg_2_controller           active
leg_3_controller           active
leg_4_controller           active
leg_5_controller           active
leg_6_controller           active
```

Wenn Controller nicht alle `active`: 5 s warten, nochmal ausführen.
Falls weiterhin `inactive` → STOP.

---

## Schritt 3 — gait_node starten MIT robot_description (Stage 0.6 aktiv)

**T2 (gait_node):**
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```

**Erwartung — gait_node-Logs müssen folgendes enthalten:**
```
[INFO] [gait_node]: Stage 0.6: parsed joint limits for 6 legs from robot_description
[INFO] [gait_node]: gait_node init: pattern=tripod, step_height=0.040 m, ...
```

**Wenn stattdessen** `WARN: robot_description empty or unparseable — IK runs in lenient mode`:
xacro-File-Pfad ist falsch oder hexapod_description nicht gesourct. → STOP, fixen.

**Hexapod-Visual in Gazebo:** sollte unverändert in Stand-Pose stehen
(gait_engine ist in STATE_STANDING, hält Position).

---

## Schritt 4 — Walking-Smoke mit kleiner cmd_vel

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartung:**
- In Gazebo: Hexapod bewegt sich langsam vorwärts (~2 cm/s)
- Tripod-Gait sichtbar: 3 Beine am Boden, 3 Beine in der Luft, alternierend
- 30+ Sekunden ohne Glitch
- gait_node-Terminal (T2): **KEINE** `IKError`-Logs, **KEINE**
  `safety_freeze`-Logs

**Beobachtungs-Notizen (für Stage C/E2 später):**
- ☐ Walking ist glatt
- ☐ alle 6 Beine in Sync
- ☐ Body-Höhe stabil (kein Wackeln)
- ☐ Mittel-Beine (leg_2, leg_5) halten Tripod

**Wenn IKError auftritt:** Step-Length zu groß für Cal-Werte. Stop +
melden welcher Bein/Joint genannt wird.

**Strg+C in T3** zum Stoppen des cmd_vel-Publishers. Hexapod sollte
binnen 1-2 Schritten in STANDING gehen (gait_engine STATE_STOPPING-
Sequenz).

---

## Schritt 5 — Extremfall: provoziere IK-Joint-Limit-Error

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.5}}'
```

Das ist 25× normales Walking-Tempo — IK sollte rad-Werte produzieren
die out-of-URDF-Limit gehen.

**Erwartung in gait_node-Terminal (T2):**
```
[ERROR] [gait_node]: gait_engine: IK failed for leg_X at t=...: joint limit: leg 'leg_X' <joint> rad=... outside [..., ...] (foot=(...))
[ERROR] [gait_node]: /hexapod_safety_freeze service not available — proceeding with local stop only (no plugin-side freeze). This is OK in sim, but on hardware indicates a missing or crashed hexapod_hardware plugin.
```

**Erwartung in Gazebo:** Hexapod bleibt stehen oder macht nur einen
halben Schritt und friert ein. KEIN durchgehender Gallop.

**Wenn KEIN IKError erscheint:** Stage 0.6 IK-Joint-Limit-Check ist
nicht aktiv. Zeigt entweder robot_description nicht durchgereicht ODER
gait_engine joint_limits-Bug.

**Strg+C in T3.**

---

## Schritt 6 — Sauber Beenden

In dieser Reihenfolge Strg+C drücken:
1. **T3** — (cmd_vel-Publisher, falls noch läuft)
2. **T2** — gait_node
3. **T1** — Sim-Stack (Gazebo + ros2_control)

**Erwartung:**
- Alle Terminals zurück am Prompt
- Kein `Defunct`-Prozess: `ps aux | grep -E "gait|gz_sim|controller_manager" | grep -v grep` zeigt nichts

---

## Status-Meldung an Claude

Nach Schritt 1-6 kurz Bescheid geben mit folgendem Format:

```
Stage E (Sim):
  S1 Sim-Spawn:        ✓ / ❌ <Symptom>
  S2 Controllers:      ✓ / ❌
  S3 gait_node-Init:   ✓ / ❌ <"parsed joint limits" log sichtbar?>
  S4 Walking-Smoke:    ✓ / ❌ <was nicht stimmt>
  S5 Extremfall:       ✓ / ❌ <IKError-Log sichtbar?>
  S6 Sauber Beendet:   ✓ / ❌

Beobachtungen:
  - Walking glatt? <ja/nein>
  - Sync Tripod?    <ja/nein>
  - Auffälligkeiten: <kurz>
```

---

## Falls Schritte schief gehen — schnelle Diagnose-Snippets

### Wenn Sim-Stack nicht startet

**T3:**
```bash
xacro $(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro > /tmp/check.urdf
echo $?
grep "<limit" /tmp/check.urdf | wc -l
```
Erwartung: exit code 0, 18 limit-Tags. Wenn anders → xacro hat einen Bug
in unseren Stage-D-Werten.

### Wenn gait_node startet ohne joint_limits-Parse

**T3:**
```bash
ros2 param get /gait_node robot_description | head -3
```
Erwartung: URDF-XML-String (lang). Wenn empty: launch-File-Pfad
gait_node erreicht den Param nicht.

### Wenn IKError bei normalem cmd_vel auftritt

**T3:** gait_node-Params auf konservativere Werte setzen:
```bash
ros2 param set /gait_node step_length_max 0.02
ros2 param set /gait_node body_height -0.04
```
Dann Schritt 4 wiederholen.

### Wenn Hexapod auf Boden kippt

Cal-Werte erlauben aktuellen body_height nicht. Höhere body_height
(weniger negativ):
```bash
ros2 topic pub --once /cmd_body_height std_msgs/Float64 '{data: -0.03}'
```
Falls das geht: Cal-Doku-Werte sind grenzwertig, in test_commands.md notieren.
