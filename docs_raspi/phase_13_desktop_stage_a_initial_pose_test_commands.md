# Phase 13 Desktop Stage A — Test-Commands

> Operative Anleitung zur Stage A. Plan + Konzept:
> [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (`hexapod_bringup real.launch.py`)
> - `T2` = gait_node (`gait.launch.py`)
> - `T3` = cmd_vel + Inspect + Param-Set
> - `T4` = optional RViz / rqt_reconfigure
>
> **Reihenfolge:** Code-Änderungen (Claude) → Unit-Tests grün → Live HW
> mit User in der Reihenfolge L1-L7.

---

## ⚠️ SAFETY — vor Live-Test

- ✅ Hexapod aufgebockt, Beine hängen frei
- ✅ Kill-Switch am Servo-PSU griffbereit
- ✅ 30 cm-Radius frei
- ✅ Stage F ✅ (URDF symmetrische rad-Limits — Vorbedingung)

**Erwartete Verbesserung:** kein ruckartiges Hochspringen der Beine
beim Plugin-Start mehr. **Falls trotzdem ruckhaft:** sofort Kill-Switch
+ Plugin-Logs prüfen.

---

## SCHRITT 0 — Build + Unit-Tests (vor Live)

**T3:**
```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware hexapod_gait
source install/setup.bash
colcon test --packages-select hexapod_hardware hexapod_gait
colcon test-result --verbose | head -40
```

**Erwartet:**
- Build grün
- Tests grün (inkl. T1-T7 aus Plan-Doku §5.1)

**❌ Falls Tests rot:** STOP, Test-Output zeigt welcher Test failed.
Code-Fix bevor Live-Test.

---

## SCHRITT 1 — Pre-Stage-A Sanity (T1, Aktuelles Verhalten)

> Verifiziert dass das Problem auch noch reproduzierbar ist.

**PSU aus**, Beine hängen frei.

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartet (Pre-Stage-A-Verhalten):**
- Plugin-Init-Logs OK
- **Beine springen ruckartig in T-Pose hoch** — das ist das Pre-Stage-A-
  Verhalten, dokumentieren als Vergleich

**Strg+C in T1, PSU aus.**

---

## SCHRITT 2 — Stage-A-aktivieren (T1, neues Verhalten)

> Default `initial_pose:=suspended` aus Stage-A-Code.

**PSU aus**, Beine hängen frei.

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartet (L1 = Stage-A-Hauptpunkt):**
- Plugin-Init-Log: `loaded initial pose preset 'suspended' from <path>`
- Plugin-Init-Log: `Stage 0.5: /hexapod_safety_reset service ready`
- 6× `Configured and activated leg_<n>_controller`
- **Beine bleiben unten / minimal-Bewegung** — kein Sprung
- KEIN `safety_freeze`-Trigger

**Status notieren:** ✓ keine ruckartige Bewegung / ❌ <Symptom>

---

## SCHRITT 3 — Plugin-Echo verifizieren (T3)

> L2: bestätigt dass Plugin Suspended-Werte sendet.

**T3:**
```bash
ros2 topic echo --once /joint_states
```

**Erwartet:**
- 18 Joint-Position-Werte
- Femur-Werte aller 6 Beine: ca. **-1.45 rad** (suspended-Preset)
- Tibia-Werte aller 6 Beine: ca. **0.0 rad**
- Coxa-Werte aller 6 Beine: ca. **0.0 rad**

**Beispiel-Output:**
```yaml
name:
- leg_1_coxa_joint
- leg_1_femur_joint
- leg_1_tibia_joint
- leg_2_coxa_joint
# ...
position:
- 0.0       # leg_1_coxa
- -1.45     # leg_1_femur
- 0.0       # leg_1_tibia
- 0.0       # leg_2_coxa
- -1.45     # leg_2_femur
# ...
```

**Status notieren:** ✓ alle Femurs ~-1.45 / ❌ <abweichende Werte>

---

## SCHRITT 4 — gait_node starten + Auto-Stand-Pose-Ramp beobachten (T2)

> L3: visuelles Hauptevent — 4-s-Lerp zur Stand-Pose.

**T2:**
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

> **Beachte:** kein `use_sim_time:=false` mehr nötig — nach Stage-A-
> Mini-Fix ist `false` der Default.

**Erwartet in T2:**
- `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- **`Auto-Stand-Pose-Ramp gestartet: 4.00 s zur Default-Stand-Pose (radial=0.295, body_height=-0.070)`**
- `Engine state: STARTUP_RAMP`
- Nach ~4 s: `Engine state: STARTUP_RAMP → STANDING`
- `gait_node init: pattern=tripod, ..., linear_max=0.035 m/s ...`

**Erwartet visuell:**
- **Beine fahren SANFT in ~4 s** von hängender Position zur Stand-Pose
- Smooth-Step-Charakteristik: langsam beginnen, Mitte schneller,
  langsam enden — KEIN ruckartiger Stop am Ende
- Stand-Pose ist visuell symmetrisch rechts/links (= Stage-F-Verifikation)
- Nach Ramp: Beine in Stand-Pose stabil

**Status notieren:** ✓ sanft 4 s / ❌ <Symptom>

---

## SCHRITT 5 — cmd_vel-Block während Ramp testen (T3)

> L4: Sicherheits-Verifikation — cmd_vel soll während Ramp ignoriert werden.

**Setup:** Strg+C in T2 (gait_node stoppt). Beine bleiben in Stand-Pose
(Plugin hält). Wir starten gait_node neu und publishen sofort cmd_vel.

**T2 (neu):**
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

**Sofort danach in T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartet in T2 (während Ramp läuft):**
- WARN-Log alle 2 s: `cmd_vel received during STARTUP_RAMP — ignored. Wait ~4 s for ramp to complete.`
- Beine fahren weiterhin sanften Lerp **ohne Walking-Schwung**
- Nach Ramp-Ende: `Engine state: STARTUP_RAMP → STANDING` →
  **danach** beginnt Walking (Tripod-Rhythmus)

**Status notieren:** ✓ cmd_vel ignoriert während Ramp, Walking erst nach Ramp / ❌ <Symptom>

**Strg+C in T3, T2, T1 zum Beenden für nächsten Test.**

---

## SCHRITT 6 — Walking nach Ramp wie gewohnt (T3)

> L5: Walking funktioniert nach Ramp normal wie Stage E2/F.

**Setup neu:** Plugin (T1) + gait_node (T2) wie oben. Warten bis Ramp
fertig (~5 s sichern).

**T3 (nach Ramp):**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartet:** Tripod-Walking-Rhythmus wie in Stage E2/F. 30 s sauber.

**Status notieren:** ✓ Walking normal / ❌ <Symptom>

**Strg+C alle drei Terminals.**

---

## SCHRITT 7 — Fallback: `initial_pose:=pulse_zero` (Legacy)

> L6: verifiziert dass der Legacy-Pfad noch existiert.

**PSU aus**, Beine hängen frei.

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=pulse_zero
```

**Erwartet:**
- Plugin-Init-Log: `loaded initial pose preset 'pulse_zero' from <path>`
- **Beine springen in T-Pose hoch** (Legacy-Verhalten, OK für diesen Test)
- Plugin-Init OK, keine Errors

**Status:** ✓ Legacy-Fallback funktional / ❌

**Strg+C, PSU aus.**

---

## SCHRITT 8 — Fallback: fehlende YAML-Datei

> L7: verifiziert Robustheit bei missing config.

**T3 (vorbereiten):**
```bash
mv src/hexapod_hardware/config/initial_poses.yaml \
   src/hexapod_hardware/config/initial_poses.yaml.HIDDEN
```

**PSU aus**, Beine hängen frei.

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartet:**
- Plugin-Init-WARN: `initial_poses_file not found at <path>, falling back to pulse_zero`
- Beine springen in T-Pose hoch (= Legacy-Fallback)
- Plugin-Init OK ohne Crash

**Status:** ✓ Missing-YAML-Fallback funktional / ❌

**Strg+C, PSU aus.**

**Cleanup:**
```bash
mv src/hexapod_hardware/config/initial_poses.yaml.HIDDEN \
   src/hexapod_hardware/config/initial_poses.yaml
```

---

## SCHRITT 9 — Sauber Beenden

Reihenfolge:
1. T3 (cmd_vel-Publisher falls läuft)
2. T2 (gait_node)
3. T1 (Plugin)

**Verifikation:**
```bash
ps aux | grep -E "gait_node|controller_manager|hexapod" | grep -v grep
```
→ Erwartet: leer.

---

## Status-Meldung an Claude

Nach Stage A live kurz:

```
Stage A (Initial-Pose + Auto-Stand-Pose-Ramp):
  S0 Build + Unit-Tests:     ✓ / ❌
  L1 keine ruckartige Bewegung beim Plugin-Start: ✓ / ❌
  L2 /joint_states zeigt suspended-Werte:         ✓ / ❌
  L3 4-s-Ramp sanft visuell:                      ✓ / ❌
  L4 cmd_vel-Block während Ramp:                  ✓ / ❌
  L5 Walking nach Ramp normal:                    ✓ / ❌
  L6 pulse_zero-Fallback:                         ✓ / ❌
  L7 missing-YAML-Fallback:                       ✓ / ❌
  use_sim_time:=false-Default funktioniert:       ✓ / ❌

Beobachtungen:
  - Servo-Akustik bei Plugin-Start:        <ruhig / Klick / Strom-Stutter>
  - Ramp-Charakteristik visuell:           <sanft / merklich gestuft / ruckhaft>
  - Stand-Pose nach Ramp symmetrisch:      <ja / nein>
  - Sonstiges:                             <kurz>
```

---

## Diagnostik bei Problemen

### Plugin lädt YAML nicht

```bash
ros2 launch hexapod_bringup real.launch.py 2>&1 | grep -i "initial_pose\|pose preset\|yaml"
```
Zeigt was der Plugin-Loader macht. Wenn Pfad falsch:
```bash
ros2 pkg prefix hexapod_hardware
ls $(ros2 pkg prefix hexapod_hardware)/share/hexapod_hardware/config/initial_poses.yaml
```

### Beine springen trotz Stage A

Möglich dass der Preset-Wert nicht ankommt. Prüfen:
```bash
# Plugin-Param checken
ros2 param get /hexapodsystem initial_pose
# Suspended-Werte ausm YAML
cat src/hexapod_hardware/config/initial_poses.yaml | yq '.poses.suspended.joints'
# PWM-Berechnung manuell:
python3 -c "
# beispiel pin 4 (leg_2 femur, direction=+1)
pulse_zero, pulse_min, pulse_max = 1550, 880, 2190
joint_lower = -1.493
rad = -1.45
slope = (pulse_zero - pulse_min) / abs(joint_lower)
pulse = pulse_zero + 1 * rad * slope
print(f'pulse: {pulse:.1f}')
"
# Sollte in [pulse_min, pulse_max] liegen
```

### Ramp ruckhaft trotz 4 s

Tick-Rate verifizieren:
```bash
ros2 topic hz /leg_1_controller/joint_trajectory
```
Sollte ~50 Hz sein. Wenn deutlich weniger: gait_node-Performance-Problem.

Auto-Standup-Dauer hochschrauben:
```bash
ros2 param set /gait_node auto_standup_duration 6.0
```

### cmd_vel-Block geht nicht

Engine-State check:
```bash
ros2 param get /gait_node # falls Engine-State-Param exponiert ist
```
Oder gait_node-Logs filtern auf `STATE_`.

---

**Erstellt 2026-05-28.** Plan + Konzept in
[`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md).
