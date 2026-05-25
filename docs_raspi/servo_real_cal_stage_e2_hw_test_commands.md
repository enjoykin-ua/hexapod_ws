# Stage E2 (HW-Walking aufgebockt) — Test-Commands

> Operative Anleitung für Live-HW-Walking-Verifikation aufgebockt. Plan +
> Erfolgs-Kriterien: [`servo_real_cal_stage_e2_hw_plan.md`](servo_real_cal_stage_e2_hw_plan.md).
>
> **Terminal-Konvention:**
> - `T1` = Plugin (`hexapod_bringup real.launch.py`, Servo2040 + USB)
> - `T2` = gait_node (ab E2.3)
> - `T3` = Joint-Trajectory-Publisher / `cmd_vel` / Inspection
> - `T4` = rqt_reconfigure (Live-Param-GUI, optional)
> - `T5` = RViz als visuelle URDF-Referenz (optional)
>
> User führt aus, meldet pro Schritt kurz Status (✓ / ❌ + 1-Zeilen-Symptom).

---

## ⚠️ SAFETY — vor JEGLICHEM Befehl

**Hardware-Setup:**
- ✅ Hexapod **aufgebockt** — Body fest auf Halter, alle 6 Beine hängen
  frei in der Luft, kein Bodenkontakt möglich
- ✅ Hardware-Kill-Switch (Servo-PSU-Trennung) griffbereit, max. 1 s
  Reaktionszeit vom Sitzplatz
- ✅ Kein Mensch / Tier / Objekt im Bewegungsradius (~30 cm um den Roboter)
- ✅ Augen weg von Beinen beim ersten Test pro Stage (Klicken hört man,
  Zucken sieht man im Peripherblick)

**Notfall-Stop-Reihenfolge bei sichtbarem Problem:**

1. **KILL-SWITCH zuerst** (Strom weg, Servos lose)
2. **Strg+C in T3** (cmd_vel-Publisher, falls läuft)
3. **Strg+C in T2** (gait_node)
4. **Strg+C in T1** (Plugin)
5. Logs (T1 + T2) auf safety_freeze / IKError prüfen
6. Erst nach Diagnose: Strom an + Plugin neu starten

> **Warum Kill-Switch first:** Strg+C im gait_node schickt evtl. noch
> einen letzten 50-Hz-Tick raus, bevor der Knoten stirbt — bei
> Fehlverhalten will man die Strom-Trennung sofort, nicht erst nach
> dem nächsten Tick.

---

## VORBEREITUNG (alle Terminals, einmalig)

```bash
cd ~/hexapod_ws
colcon build
source install/setup.bash
```

**Erwartung:** alle Pakete grün gebaut. Wenn nicht: STOP, melden.

---

## SCHRITT 1 — Plugin starten (T1)

**T1:**
```bash
ros2 launch hexapod_bringup real.launch.py
```

**Erwartung in T1:**
- Log: `Stage 0.5: /hexapod_safety_reset service ready`
- Log: `Stage 0.6: /hexapod_safety_freeze service ready`
- Log: `Phase 11 Stage B: /save_calibration service ready`
- Log: `controller_manager` aktiv
- Log: 6× `Configured and activated leg_<n>_controller` (oder ähnlich)
- KEINE `ERROR`-Logs
- KEIN `safety_freeze`-Trigger im Init

**Beine visuell:** alle 6 Beine in T-Pose (radial-out neutral, femur
horizontal, tibia gerade). Servos halten unter leichtem Drehmoment.

**❌ Falls Servo2040 nicht erreichbar** (`failed to open /dev/ttyACM0`):
USB-Kabel prüfen, Strom-Servo2040 prüfen, ggf. `ls /dev/ttyACM*`.

**❌ Falls safety_freeze beim Init triggered:**
STOP. servo_mapping.yaml ist inkonsistent (pulse_zero außerhalb
[pulse_min, pulse_max]). Plugin-Logs zeigen welcher Pin.

---

## SCHRITT 2 — Controllers prüfen (T3)

**T3:**
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

**❌ Wenn nicht alle `active`:** 5 s warten, nochmal ausführen. Falls
weiterhin `inactive`: STOP, T1-Logs prüfen.

---

## SCHRITT 3 — (optional) RViz starten (T5)

> **Nice-to-have:** für visuelle Referenz, was das Plugin als
> `/joint_states` publisht. Nicht zwingend, aber hilft beim Cross-Check.

**T5:**
```bash
ros2 launch hexapod_description display.launch.py with_jsp_gui:=false
```

> **`with_jsp_gui:=false`** verhindert dass `joint_state_publisher_gui`
> mit dem Plugin um `/joint_states` konkurriert (Stage-C-Findung).

---

## E2.1 — Ein Bein, 3 Joints koordiniert

**Vorgehen:** pro Bein einmal die untenstehende Trajectory publishen.
Bein bewegt sich in ~2 s in lifted-Pose, hält 0 s (sofortiger Übergang),
geht in ~2 s zurück zu T-Pose. Pause 3 s, dann nächstes Bein.

### E2.1 — Fresh-Start (Reproduktion von Null)

> Wenn vorher alles gekillt wurde: SCHRITT 1 (Plugin) + SCHRITT 2
> (Controllers) wiederholen (alle 6 Beine in T-Pose), dann hier weiter mit
> Trajectory-Publish pro Bein in T3.

> **Werte-Logik:** `[coxa=0, femur=-0.3, tibia=+0.3]` — coxa neutral,
> femur dreht das Bein leicht "nach oben" (weg vom Aufbock-Punkt), tibia
> knickt leicht ein. Bei aufgebocktem Hexapod hebt sich das Bein vom
> Hängezustand sichtbar nach oben.

### E2.1.1 — leg_1

**T3:**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

**Erwartung:**
- Bein bewegt sich ~2 s in lifted-Pose (femur dreht hoch, tibia knickt ein)
- Bein bewegt sich ~2 s zurück zu T-Pose
- Alle 3 Joints synchron — kein einzelner Joint hängt nach
- Keine Servo-Klicks, kein Brummen, kein Stutter
- T1: keine `safety_freeze`-Logs

**Status notieren:** ✓ glatt / ❌ <Symptom>

---

### E2.1.2 — leg_2

**T3:**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

---

### E2.1.3 — leg_3

**T3:**
```bash
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

---

### E2.1.4 — leg_4

**T3:**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

---

### E2.1.5 — leg_5

**T3:**
```bash
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

---

### E2.1.6 — leg_6

**T3:**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}'
```

---

**Status E2.1:** alle 6 Beine sauber durchgelaufen → ✓ weiter zu E2.2.
Wenn ein Bein ❌: STOP, melden welches Bein + Symptom.

---

## E2.2 — Tripod-Set (3 Beine simultan)

**Vorgehen:** pro Tripod-Set 3 `ros2 topic pub --once` parallel mit `&`,
dann `wait`. Beine sollten visuell **gleichzeitig** starten.

### E2.2 — Fresh-Start (Reproduktion von Null)

> Wenn vorher alles gekillt wurde: SCHRITT 1 (Plugin) + SCHRITT 2
> (Controllers) wiederholen (alle 6 Beine in T-Pose), dann hier weiter mit
> Parallel-Publish in T3.

### E2.2.1 — Tripod-Set A: legs 1+3+5 simultan

**T3:**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
ros2 topic pub --once /leg_3_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
ros2 topic pub --once /leg_5_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
wait
```

**Erwartung:**
- 3 Beine starten visuell gleichzeitig (Versatz < 100 ms)
- 3 Beine kommen gleichzeitig in lifted-Pose an (t≈2s)
- 3 Beine sind gleichzeitig zurück in T-Pose (t≈4s)
- T1: keine `safety_freeze`, keine `serial write timeout`
- T1: keine `controller_manager`-Warnings

**❌ Wenn ein Bein deutlich nachhängt (>500 ms):** USB-CDC-Bus-Throughput-
Problem oder Plugin-Concurrency-Bug. T1-Logs prüfen, notieren welches Bein.

---

### E2.2.2 — Tripod-Set B: legs 2+4+6 simultan

**T3:**
```bash
ros2 topic pub --once /leg_2_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
ros2 topic pub --once /leg_4_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.0, -0.3, 0.3], time_from_start: {sec: 2}},
             {positions: [0.0,  0.0, 0.0], time_from_start: {sec: 4}}]}' &
wait
```

**Erwartung:** identisch zu E2.2.1, aber für Tripod-Set B.

---

**Status E2.2:** beide Sets sauber → ✓ weiter zu E2.3.

---

## E2.3 — gait_node + sim_walk.yaml, Stand-Pose alle 6 Beine

**Vorgehen:** gait_node starten in separatem Terminal. gait_node liest
URDF + Cal-Werte, rechnet IK für Stand-Pose, schickt alle 6 Beine
synchron in Stand-Pose. Kein cmd_vel publishen — Roboter bleibt in
STATE_STANDING.

### E2.3 — Fresh-Start (Reproduktion von Null)

> Wenn vorher alles gekillt wurde: diese Reihenfolge bringt dich auf den
> Stand "gait_node hält Stand-Pose, kein cmd_vel". Pro Terminal jeweils
> einmal `cd ~/hexapod_ws && source install/setup.bash` vorausgesetzt.

**T1 (Plugin):**
```bash
ros2 launch hexapod_bringup real.launch.py
```
→ warten bis `controller_manager` + 6 `leg_<n>_controller activated`-Logs
sichtbar, alle 6 Beine in T-Pose.

**T3 (Controllers prüfen, einmalig):**
```bash
ros2 control list_controllers
```
→ 7 Zeilen alle `active`. Wenn nicht: 5 s warten, nochmal.

**T5 (optional, RViz-URDF-Referenz):**
```bash
ros2 launch hexapod_description display.launch.py with_jsp_gui:=false
```

**T2 (gait_node — der eigentliche E2.3-Trigger):**
```bash
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

> **`use_sim_time:=false` ist Pflicht auf HW!** `gait.launch.py` hat
> Default `use_sim_time=true` (für Stage E Sim mit Gazebo's `/clock`-
> Publisher). Auf HW gibt's kein `/clock` → rclpy-Timer blockt für immer
> auf Sim-Zeit, `_tick` feuert nie, gait_node publisht keine
> JTC-Trajectories. Symptom: gait_node lebt aber Beine stehen still.

**Erwartung in T2:**
- Log: `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- Log: `gait_node init: pattern=tripod, step_height=0.020 m, ..., body_height=-0.070 m ..., step_length_max=0.035 m (linear_max=0.035 m/s) ...`
- Log: gait_node tickt mit 50 Hz, evtl. periodische STATE-Logs
- KEIN `IKError`
- KEIN `safety_freeze`

**❌ Falls** `WARN: robot_description empty or unparseable`:
xacro-Pfad falsch oder `hexapod_description` nicht gesourct. STOP.

**❌ Falls** `linear_max=0.050 m/s`:
params_file nicht geladen. Pfad prüfen.

**❌ Falls** `IKError: joint limit ...`:
sim_walk.yaml-Werte für HW zu aggressiv. Aufnehmen welcher Joint,
Tempo-Anpassung in §"Diagnostik" weiter unten.

---

### E2.3.2 — Visueller Stand-Pose-Check

**Visuell beobachten** (~10 s nach gait_node-Start):
- Alle 6 Beine fahren simultan aus T-Pose in Stand-Pose
- Stand-Pose visuell: leichte Kniebeuge mit `body_height=-0.070 m`,
  also Beine etwas weiter "unten" als bei T-Pose — bei aufgebocktem
  Hexapod heißt das Beine pendeln in Kniebeuge-Pose in der Luft
- Keine asynchronen Beine
- 30 s in Stand-Pose stabil, kein periodisches Zucken

**T3 (Inspect):**
```bash
ros2 topic echo --once /gait_state 2>/dev/null || ros2 node list
```

> **Hinweis:** Stage 9 hat `/gait_state` evtl. noch nicht — Fallback ist
> einfach gait_node-Log in T2 prüfen.

**Status notieren:** ✓ alle 6 in Stand-Pose / ❌ <Bein/Symptom>

---

**Status E2.3:** Stand-Pose stabil → ✓ weiter zu E2.4.
Wenn IKError für ein Bein: STOP, melden Bein + Joint + Log-Zeile.

---

## E2.4 — Walking aufgebockt mit cmd_vel 0.02 m/s

**Vorgehen:** kleinen cmd_vel publishen. gait_engine wechselt zu
STATE_WALKING. Aufgebockt: Beine machen Walking-Bewegung in der Luft.

### E2.4 — Fresh-Start (Reproduktion von Null)

> Wenn vorher alles gekillt wurde: erst E2.3-Fresh-Start ausführen (Plugin
> + gait_node + Stand-Pose), dann hier weiter mit cmd_vel-Publish in T3.

### E2.4.1 — cmd_vel starten

**T3 (cmd_vel):**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

> **Warum 0.02 m/s?** sim_walk.yaml hat `linear_max=0.035 m/s`. 0.02 ist
> ~60% davon, gute Sicherheits-Marge für ersten HW-Walking-Test.

**Erwartung (visuell, ~10 s nach Start):**
- Tripod-Rhythmus: 3 Beine schwingen nach vorne (Swing-Phase),
  3 Beine ziehen nach hinten (Stance-Phase in der Luft, da aufgebockt)
- Alternierend pro 1 s (cycle_time/2 mit `cycle_time=2.0 s`)
- Alle Beine in Sync — Tripod-Set A vorne/oben, Set B hinten/unten,
  dann Wechsel
- T2 (gait_node): KEINE `IKError`, KEINE `WARN`
- T1 (Plugin): KEINE `safety_freeze`, KEINE `serial`-Errors

**Beobachtungs-Notizen:**
- ☐ Walking-Rhythmus glatt
- ☐ Tripod-Sets klar erkennbar
- ☐ Servos ruhig (kein Klicken/Brummen)
- ☐ Body wackelt nicht am Halter

**30 s laufen lassen, dann Strg+C in T3.**

**Erwartung nach Strg+C:**
- gait_engine: STATE_WALKING → STATE_STOPPING → STATE_STANDING
- Beine fahren in Stand-Pose zurück

**Status notieren:** ✓ 30 s sauber / ❌ <Symptom>

---

**Status E2.4:** Walking 0.02 sauber → ✓ weiter zu E2.5.

---

## E2.5 — Tempo-Treppe 0.02 → 0.03 → 0.035 m/s

**Vorgehen:** dieselbe `cmd_vel`-Schleife wie E2.4, aber höhere `x`-Werte
schrittweise. Zwischen den Stufen Strg+C, dann nächste Stufe.

### E2.5 — Fresh-Start (Reproduktion von Null)

> Wenn vorher alles gekillt wurde: erst E2.3-Fresh-Start ausführen (Plugin
> + gait_node + Stand-Pose), dann hier weiter mit cmd_vel-Publish in T3.

### E2.5.1 — cmd_vel x=0.03

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**Erwartung:** wie E2.4, leicht schneller. 30 s sauber. Strg+C.

**Status:** ✓ / ❌ <Symptom>

---

### E2.5.2 — cmd_vel x=0.035 (linear_max)

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.035}}'
```

**Erwartung:** Walking mit voller `linear_max=0.035 m/s`. gait-engine
clampt nicht (Wert ist genau am Limit). 30 s sauber. Strg+C.

**Status:** ✓ / ❌ <Symptom>

---

### E2.5.3 — (optional) cmd_vel x=0.05 — Clamp-Verifikation

**T3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05}}'
```

**Erwartung in T2** (alle 2 s eine WARN-Zeile):
```
[WARN] [gait_node]: cmd_vel clamped: input (vx=0.050, vy=0.000, omega=0.000) > max-leg-speed 0.035 m/s
```

**Visuell:** Walking-Tempo identisch zu E2.5.2 (gleich wie 0.035), KEINE
IKError-Logs.

**Status:** ✓ Clamp-WARN gesehen + Walking-Tempo wie 0.035 / ❌ <Symptom>

---

**Status E2.5:** alle Tempo-Stufen sauber → ✓ weiter zu Sauber-Beenden.

Falls IKError bei einer Stufe:
- Stop sofort (Strg+C T3, Kill-Switch optional falls Bein zickt)
- Melde Bein + Joint + Tempo
- Wir können in Phase 13 die Cal nachschärfen oder sim_walk.yaml neu
  generieren mit niedrigerem `--safety-margin`

---

## SAUBER BEENDEN

In dieser Reihenfolge Strg+C drücken:
1. **T3** — cmd_vel-Publisher (falls noch läuft)
2. **T2** — gait_node
3. **T1** — Plugin (`real.launch.py`)
4. **T4/T5** — rqt_reconfigure / RViz (falls offen)

**Erwartung:**
- Alle Terminals zurück am Prompt
- Beine halten letzte commanded Position (Servos noch unter Strom)
- Kein zombie-Prozess:
  ```bash
  ps aux | grep -E "gait_node|controller_manager|hexapod" | grep -v grep
  ```
  → leer

**Optional: Strom abschalten** wenn Session zu Ende, Beine fallen
locker dann (Schwerkraft, da Aufbock-Halter sie hält).

---

## Status-Meldung an Claude

Nach Stage E2 kurz Bescheid geben mit folgendem Format:

```
Stage E2 (HW-Walking aufgebockt):
  S1 Plugin-Start:        ✓ / ❌ <Symptom>
  S2 Controllers:         ✓ / ❌
  E2.1 1 Bein x 6:        ✓ / ❌ <Bein/Symptom>
  E2.2 Tripod-Sets:       ✓ / ❌ <Set/Symptom>
  E2.3 Stand-Pose:        ✓ / ❌ <Bein/Symptom>
  E2.4 Walk 0.02:         ✓ / ❌ <Symptom>
  E2.5 Walk 0.03/0.035:   ✓ / ❌ <Tempo/Symptom>
  Sauber Beendet:         ✓ / ❌

Beobachtungen:
  - Walking-Visual glatt?  <ja/nein>
  - Servo-Akustik ruhig?   <ja/nein>
  - Body stabil am Halter? <ja/nein>
  - Sonstiges:             <kurz>
```

---

## Diagnostik-Snippets bei Problemen

### Wenn Plugin nicht startet

```bash
ls /dev/ttyACM*                 # Servo2040 da?
groups | grep dialout           # User in dialout-Gruppe?
sudo dmesg | tail -20           # Kernel-Meldungen zu USB?
```

### Wenn `safety_freeze` triggered

**T3:**
```bash
ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger '{}'
```
- Wenn das den freeze löscht: Cal-Bug für einen spezifischen Pin,
  welcher Pin? T1-Log filtern auf `safety_freeze`.
- Wenn freeze sofort wieder kommt: Cal in `servo_mapping.yaml` falsch
  → Stage B-Wert für Pin neu messen.

### Wenn gait_node IKError für ein Bein

T2-Log gibt Bein + Joint. Typische Ursachen:
- Cal-Doku Tab. 3.3 für dieses Bein zu eng → in Phase 13 nachmessen
- Stand-Pose-Werte aus sim_walk.yaml zu aggressiv für HW

**Workaround live:**
```bash
ros2 param set /gait_node body_height -0.05   # weniger Kniebeuge
ros2 param set /gait_node step_length_max 0.02
```

### Wenn ein Bein in E2.1 nicht reagiert

```bash
ros2 control list_hardware_components       # Plugin loaded?
ros2 control list_controllers               # Bein-Controller active?
ros2 topic echo --once /joint_states        # Plugin publisht?
```

### Wenn Walking ruckelig in E2.4/E2.5

**T3:**
```bash
ros2 param set /gait_node cycle_time 3.0   # langsamer Cycle
```
Wenn das hilft: HW-Servos brauchen mehr Zeit pro Schritt als Sim.
Notieren für Phase 13.

---

**Erstellt 2026-05-25. Plan + Konzept liegt in
[`servo_real_cal_stage_e2_hw_plan.md`](servo_real_cal_stage_e2_hw_plan.md).**
