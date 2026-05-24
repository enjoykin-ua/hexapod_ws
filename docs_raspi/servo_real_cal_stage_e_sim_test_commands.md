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

## Schritt 3 — gait_node starten MIT robot_description + Sim-Preset

**T2 (gait_node):**
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

> **`sim_walk.yaml`** enthält die in Stage E (2026-05-24) manuell
> getuneten Walking-Envelope-Werte: `radial_distance=0.30`,
> `body_height=-0.075`, `step_length_max=0.03`, `step_height=0.02`.
> Siehe [`walking_envelope_tool_spec.md`](walking_envelope_tool_spec.md)
> für Math und das (geplante) Sweep-Tool das systematisch optimale
> Werte pro Höhe findet.

**Erwartung — gait_node-Logs:**
```
[INFO] [gait_node]: Stage 0.6: parsed joint limits for 6 legs from robot_description
[INFO] [gait_node]: gait_node init: pattern=tripod, step_height=0.020 m, ..., body_height=-0.075 m ..., step_length_max=0.030 m (linear_max=0.015 m/s) ...
```

**Wenn stattdessen** `WARN: robot_description empty or unparseable — IK runs in lenient mode`:
xacro-File-Pfad ist falsch oder hexapod_description nicht gesourct. → STOP, fixen.

**Wenn `linear_max=0.050 m/s`** (Default-Werte statt Preset):
params_file-Pfad nicht gefunden. Preset wurde nicht geladen. → STOP, fixen.

**Hexapod-Visual in Gazebo:** sollte in Stand-Pose stehen, Beine etwas
weiter raus + tiefer als bei reinem Default.

---

## Schritt 4 — Walking-Smoke mit cmd_vel

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.015}}'
```

> **Warum 0.015 m/s?** Mit `step_length_max=0.03 m` und `cycle_time=2.0 s`
> ist `linear_max = 0.03/2.0 = 0.015 m/s`. Größere Werte werden geclamped
> mit WARN-Log (siehe Schritt 5).

**Erwartung:**
- In Gazebo: Hexapod bewegt sich langsam vorwärts (~1.5 cm/s)
- Tripod-Gait sichtbar: 3 Beine am Boden, 3 Beine in der Luft, alternierend
- 30+ Sekunden ohne Glitch
- gait_node-Terminal (T2): **KEINE** `IKError`-Logs

**Beobachtungs-Notizen:**
- ☐ Walking ist glatt
- ☐ alle 6 Beine in Sync
- ☐ Body-Höhe stabil
- ☐ Mittel-Beine (leg_2, leg_5) halten Tripod

**Wenn IKError auftritt:** Cal-Werte sind enger als erwartet. Sim-Preset
muss neu getunt werden — sag Bescheid mit dem Bein/Joint-Detail aus dem
Log.

**Strg+C in T3** nach 30 s. Hexapod geht in STATE_STOPPING → STANDING.

---

## Schritt 5 — cmd_vel-Clamp-Verhalten (statt Extremfall)

> **Hinweis:** Der ursprüngliche "Extremfall" (cmd_vel=0.5 zum
> Provozieren von IKError) funktioniert mit dem Sim-Preset NICHT mehr,
> weil gait_engine cmd_vel auf `linear_max=0.015 m/s` clampt BEVOR IK
> rechnet. Stattdessen verifizieren wir den Clamp-Mechanismus.

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.5}}'
```

**Erwartung in T2 — alle 2 s eine WARN-Zeile:**
```
[WARN] [gait_node]: cmd_vel clamped: input (vx=0.500, vy=0.000, omega=0.000) > max-leg-speed 0.015 m/s
```

**Erwartung in Gazebo:** Hexapod läuft mit linear_max=0.015 m/s
(genauso schnell wie in Schritt 4). KEINE IKError-Logs.

**Strg+C in T3.**

> **Test der Stage-0.6-Joint-Limit-Detection** (optional, manuell):
> Wenn du den IKError-Pfad live sehen willst, müsstest du
> `step_length_max` temporär außerhalb-Envelope setzen
> (`ros2 param set /gait_node step_length_max 0.08`) und Walking
> versuchen. Wird IKError + Service-Fallback-Log auslösen für leg_3.
> Danach `ros2 param set /gait_node step_length_max 0.03` zurücksetzen.

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
