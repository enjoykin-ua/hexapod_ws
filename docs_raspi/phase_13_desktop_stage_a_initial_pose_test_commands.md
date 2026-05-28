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
> **Reihenfolge:** Code-Aenderungen (Claude) → Unit-Tests gruen → Live HW
> mit User in der Reihenfolge L1-L7.

---

## ⚠️ SAFETY — vor Live-Test

- ✅ Hexapod aufgebockt, Beine haengen frei
- ✅ Kill-Switch am Servo-PSU griffbereit
- ✅ 30 cm-Radius frei
- ✅ Stage F ✅ (URDF symmetrische rad-Limits — Vorbedingung)

**Erwartete Verbesserung:** kein ruckartiges Hochspringen der Beine
beim Plugin-Start mehr. **Falls trotzdem ruckhaft:** sofort Kill-Switch
+ Plugin-Logs pruefen.

---

## 🧹 Sauber-Beenden + PSU-Reset (PFLICHT zwischen allen Tests)

> Jeder Test in Stage A geht davon aus, dass die Servos **depowered** in
> ihrer Schwerkraft-Position haengen, BEVOR der Plugin-Start die ersten
> PWMs sendet. Wenn die Servos noch in einer aktiven Pose (z.B.
> Stand-Pose vom letzten Test) gehalten werden und der naechste Test
> startet, sehen wir Servo-Bewegung Richtung suspended — nicht das
> erwartete "Beine bleiben unten".
>
> Daher: **vor JEDEM Test** dieser Block:

1. **Strg+C** in dieser Reihenfolge:
   - T3 (cmd_vel-Publisher falls aktiv)
   - T2 (gait_node)
   - T1 (Plugin / `real.launch.py`)
2. **PSU AUS** (Servo-Strom)
3. **~30 s warten** — Servos depowered, Beine sinken durch Schwerkraft
   nach unten
4. **Beine optional von Hand nach unten ziehen** falls noch verspannt
   (selten noetig nach 30 s — nur visuelle Kontrolle)
5. **PSU bleibt aus** bis Plugin-Start im naechsten Test

Hintergrund: Servos halten ihre letzte PWM-Position via Gear-Reibung
auch nach PSU-aus eine Weile. Bei sauberer Reihenfolge "Plugin runter →
PSU aus → 30 s warten" sind sie passiv genug, damit Schwerkraft
gewinnt.

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
- Build gruen
- Tests gruen (inkl. T1-T7: 5 `InitialPosePreset.*` GTests im
  hexapod_hardware-Suite + 11 `test_startup_ramp` pytest-Tests im
  hexapod_gait-Suite)

**❌ Falls Tests rot:** STOP, Test-Output zeigt welcher Test failed.
Code-Fix bevor Live-Test.

---

## SCHRITT 1 — Stage-A aktivieren (L1: keine ruckartige Bewegung)

> Default `initial_pose:=suspended` ist nach Stage-A-Code der
> Plugin-Default. **Sauber-Beenden + PSU-Reset** voraus (siehe oben).
>
> Pre-Stage-A-Reproduktion (Beine springen auf T-Pose) wird in
> SCHRITT 7 (L6 mit `initial_pose:=pulse_zero`) abgedeckt — kein
> separater Schritt noetig.

**Start-Workflow:**

1. PSU bleibt **aus**, Beine haengen unten.
2. **T1:**
   ```bash
   ros2 launch hexapod_bringup real.launch.py
   ```
3. Plugin laeuft, sendet suspended-PWMs ueber USB an Servo2040
   (gepuffert, da PSU aus → keine Servo-Bewegung).
4. **PSU AN** → Servos kriegen Strom, fahren minimal zur suspended-
   Pose (Pose ≈ wo sie schon haengen, Bewegung kaum sichtbar).
5. **~5 s warten** bis Servos in suspended-Pose stabilisiert sind.

**Erwartet (L1 = Stage-A-Hauptpunkt):**
- Plugin-Init-Log: `loaded initial pose preset 'suspended' from <path>:
  18/18 joints applied (fallback pulse_zero: 0 OoR, 0 unknown-segment)`
- Plugin-Init-Log: `Stage 0.5: /hexapod_safety_reset service ready`
- 6× `Configured and activated leg_<n>_controller`
- **Beine bleiben unten / minimale Bewegung** — kein Sprung
- KEIN `safety_freeze`-Trigger

**Status notieren:** ✓ keine ruckartige Bewegung / ❌ <Symptom>

---

## SCHRITT 2 — Plugin-Echo verifizieren (L2)

> Bestaetigt dass Plugin Suspended-Werte sendet.

**T3:**
```bash
ros2 topic echo --once /joint_states
```

**Erwartet:**
- 18 Joint-Position-Werte
- Femur-Werte aller 6 Beine: ca. **1.45 rad** (Toleranz ±0.01)
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
- 1.45     # leg_1_femur
- 0.0       # leg_1_tibia
- 0.0       # leg_2_coxa
- 1.45     # leg_2_femur
# ...
```

**Status notieren:** ✓ alle Femurs ~1.45 / ❌ <abweichende Werte>

---

## SCHRITT 3 — gait_node + Auto-Stand-Pose-Ramp (L3)

> Visuelles Hauptevent: 4-s-Lerp zur Stand-Pose.

**T2:**
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

> **Beachte:** kein `use_sim_time:=false` mehr noetig — nach Stage-A-
> Mini-Fix ist `false` der Default in `gait.launch.py`.

**Erwartet in T2:**
- `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- `gait_node init: ..., auto_standup_duration=4.00 s (waiting for
  /joint_states to trigger ramp)`
- Nach erstem `/joint_states`-Empfang:
  `Auto-Stand-Pose-Ramp gestartet: 4.00 s zur Default-Stand-Pose
  (radial=0.295, body_height=-0.070)`
- Nach ~4 s: `Engine state: STARTUP_RAMP -> STANDING
  (Auto-Stand-Pose-Ramp complete)`

**Erwartet visuell:**
- **Beine fahren SANFT in ~4 s** von haengender Position zur Stand-Pose
- Smooth-Step-Charakteristik: langsam beginnen, Mitte schneller,
  langsam enden — KEIN ruckartiger Stop am Ende
- Stand-Pose ist visuell symmetrisch rechts/links (= Stage-F-Verifikation)
- Nach Ramp: Beine in Stand-Pose stabil

**Status notieren:** ✓ sanft 4 s / ❌ <Symptom>

---

## SCHRITT 4 — cmd_vel-Block waehrend Ramp (L4)

> Sicherheits-Verifikation: cmd_vel waehrend STARTUP_RAMP wird ignoriert.

**Setup:**
- Strg+C in T2 (gait_node stoppt). Plugin (T1) laeuft weiter, haelt
  Stand-Pose.
- **Wichtig:** wir starten gait_node neu und publishen cmd_vel sofort.
  Ramp triggert beim ersten /joint_states; Stand-Pose-Start = Stand-
  Pose-Ziel → Lerp ist effektiv 0-Bewegung, aber 4 s lang STARTUP_RAMP-
  State → cmd_vel muss blockt sein.

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

**Erwartet in T2 (waehrend Ramp laeuft, ~4 s):**
- WARN-Log alle 2 s: `cmd_vel received during STARTUP_RAMP — ignored.
  Wait ~4.0 s for ramp to complete.`
- Beine bewegen sich **nicht** im Tripod-Rhythmus
- Nach Ramp-Ende: `Engine state: STARTUP_RAMP -> STANDING` →
  **danach** beginnt Walking (Tripod-Rhythmus)

**Status notieren:** ✓ cmd_vel ignoriert waehrend Ramp, Walking erst
nach Ramp / ❌ <Symptom>

**Strg+C in T3, T2 zum Beenden vor naechstem Test.** Plugin (T1) und
PSU koennen an bleiben fuer SCHRITT 5.

---

## SCHRITT 5 — Walking nach Ramp wie gewohnt (L5)

> Walking funktioniert nach Ramp normal wie Stage E2/F.

**Setup:** Plugin (T1) laeuft weiter aus SCHRITT 4. gait_node (T2) neu
starten und warten bis Ramp fertig.

**T2:**
```bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

> Warten bis `STARTUP_RAMP -> STANDING` im T2-Log auftaucht (~5 s mit
> Safety-Margin), dann erst T3 starten.

**T3 (nach Ramp):**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartet:** Tripod-Walking-Rhythmus wie in Stage E2/F. 30 s sauber.

**Status notieren:** ✓ Walking normal / ❌ <Symptom>

**Sauber-Beenden + PSU-Reset** vor naechstem Test (SCHRITT 6).

---

## SCHRITT 6 — Fallback: `initial_pose:=pulse_zero` (L6, Legacy)

> Verifiziert dass der Legacy-Pfad noch existiert. Hier sehen wir das
> alte Pre-Stage-A-Sprung-Verhalten als Vergleich.

**Sauber-Beenden + PSU-Reset** abgeschlossen (siehe oben). Beine
haengen unten.

**Start-Workflow:**

1. PSU aus, Beine haengen unten.
2. **T1:**
   ```bash
   ros2 launch hexapod_bringup real.launch.py initial_pose:=pulse_zero
   ```
3. **PSU AN** → Servos fahren auf T-Pose (= alte Pre-Stage-A-Bewegung).

**Erwartet:**
- Plugin-Init-Log: `loaded initial pose preset 'pulse_zero' from <path>:
  18/18 joints applied ...`
- **Beine springen in T-Pose hoch** (Legacy-Verhalten, OK fuer diesen
  Test)
- Plugin-Init OK, keine Errors

**Status:** ✓ Legacy-Fallback funktional / ❌

**Sauber-Beenden + PSU-Reset** vor naechstem Test.

---

## SCHRITT 7 — Fallback: fehlende YAML-Datei (L7)

> Verifiziert Robustheit bei missing config.

**Sauber-Beenden + PSU-Reset** abgeschlossen.

**T3 (vorbereiten):**
```bash
mv install/hexapod_hardware/share/hexapod_hardware/config/initial_poses.yaml \
   install/hexapod_hardware/share/hexapod_hardware/config/initial_poses.yaml.HIDDEN
```

> **Hinweis:** wir verschieben das installierte File (nicht das src/-
> Original), da das Plugin via `$(find hexapod_hardware)` aus dem
> install-Share laedt.

**PSU aus**, Beine haengen unten.

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**PSU AN.**

**Erwartet:**
- Plugin-Init-WARN: `Failed to load initial_poses_file '...': ...
  Falling back to pulse_zero (Legacy-T-Pose) for all servos.`
- **Beine springen in T-Pose hoch** (= Legacy-Fallback wie L6)
- Plugin-Init OK ohne Crash

**Status:** ✓ Missing-YAML-Fallback funktional / ❌

**Strg+C, PSU aus.**

**Cleanup:**
```bash
mv install/hexapod_hardware/share/hexapod_hardware/config/initial_poses.yaml.HIDDEN \
   install/hexapod_hardware/share/hexapod_hardware/config/initial_poses.yaml
```

---

## SCHRITT 8 — Sauber Beenden (Abschluss)

Reihenfolge:
1. T3 (cmd_vel-Publisher falls laeuft)
2. T2 (gait_node)
3. T1 (Plugin)
4. PSU aus

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
  S0 Build + Unit-Tests:                            ✓ / ❌
  L1 keine ruckartige Bewegung beim Plugin-Start:   ✓ / ❌
  L2 /joint_states zeigt suspended-Werte:           ✓ / ❌
  L3 4-s-Ramp sanft visuell:                        ✓ / ❌
  L4 cmd_vel-Block waehrend Ramp:                   ✓ / ❌
  L5 Walking nach Ramp normal:                      ✓ / ❌
  L6 pulse_zero-Fallback:                           ✓ / ❌
  L7 missing-YAML-Fallback:                         ✓ / ❌
  use_sim_time:=false-Default funktioniert:         ✓ / ❌

Beobachtungen:
  - Servo-Akustik bei Plugin-Start:        <ruhig / Klick / Strom-Stutter>
  - Ramp-Charakteristik visuell:           <sanft / merklich gestuft / ruckhaft>
  - Stand-Pose nach Ramp symmetrisch:      <ja / nein>
  - Sonstiges:                             <kurz>
```

---

## Diagnostik bei Problemen

### Plugin laedt YAML nicht

```bash
ros2 launch hexapod_bringup real.launch.py 2>&1 | grep -i "initial_pose\|pose preset\|yaml"
```
Zeigt was der Plugin-Loader macht. Wenn Pfad falsch:
```bash
ros2 pkg prefix hexapod_hardware
ls $(ros2 pkg prefix hexapod_hardware)/share/hexapod_hardware/config/initial_poses.yaml
```

### Beine springen trotz Stage A

Moeglich dass der Preset-Wert nicht ankommt. Pruefen:
```bash
# Suspended-Werte aus dem YAML
cat $(ros2 pkg prefix hexapod_hardware)/share/hexapod_hardware/config/initial_poses.yaml
# PWM-Berechnung manuell pruefen:
python3 -c "
# beispiel pin 4 (leg_2 femur, direction=+1)
pulse_zero, pulse_min, pulse_max = 1550, 880, 2190
joint_lower = -1.493
rad = 1.45
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

Auto-Standup-Dauer hochschrauben (nur in STANDING moeglich, also nach
Ramp-Ende — fuer naechsten Run wirksam):
```bash
ros2 param set /gait_node auto_standup_duration 6.0
```

### cmd_vel-Block geht nicht

Engine-State pruefen via Logs:
```bash
ros2 topic echo /rosout | grep -E "STARTUP_RAMP|STANDING"
```
Oder direkt: nach gait_node-Restart muss innerhalb ~1 s die
`Auto-Stand-Pose-Ramp gestartet`-Zeile kommen, und ein cmd_vel-Pub
direkt danach muss zu `cmd_vel received during STARTUP_RAMP — ignored`
WARN fuehren.

### /joint_states-Timeout

Wenn nach 10 s kein /joint_states ankommt:
```
No /joint_states received within 10 s — gait_node will not start
Auto-Stand-Pose-Ramp. Check that joint_state_broadcaster is running
and publishing.
```
Ursache: `joint_state_broadcaster`-Spawner gecrasht. Pruefen:
```bash
ros2 control list_controllers
```
Sollte `joint_state_broadcaster active` zeigen.

---

**Erstellt 2026-05-28.** Plan + Konzept in
[`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md).
