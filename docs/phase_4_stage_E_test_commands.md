# Phase 4 — Stufe E: Test-Befehle (User-Operations-Handbuch)

> **Rollen-Aufteilung:**
> - **Du** führst alle Befehle aus, gibst pro Schritt eine **kurze**
>   Status-Rückmeldung an Claude (Format-Beispiele unten).
> - **Claude** wartet auf deine Status-Meldung, hakt im Progress-File ab,
>   gibt nächsten Schritt frei oder geht in Diagnose, wenn was schiefgeht.
>
> **Warum diese Aufteilung?** Wenn Claude die Sim selbst per
> `run_in_background` startete, würden alle Sim-Logs in seinen Kontext
> fließen — bei Gazebo + 7 Spawnern + JSB sind das schnell tausende
> Zeilen. Durch lokale Ausführung bleibt der Kontext schlank.

---

## Vorbereitung — Terminals einrichten

Du brauchst **drei Terminals**. In jedem als erstes:

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

| Terminal | Zweck |
|---|---|
| **T1** | Sim-Launch (bleibt offen, läuft die ganze Zeit) |
| **T2** | CLI-Checks (`ros2 control ...`, `ros2 topic ...`, Bewegungstests) |
| **T3** | RViz (erst ab Schritt 6 nötig) |

**Tipp:** Logs der Sim leiten wir nach `/tmp/sim.log` um, damit Claude bei
Problemen gezielt grep-en kann ohne den ganzen Output durchsuchen zu müssen.

---

## Status-Rückmeldung an Claude — Format

Pro Schritt **eine** Zeile reicht. Beispiele:

- `Schritt 1 OK`
- `Schritt 2 OK, Roboter steht stabil auf 6 Beinen, kein Wackeln`
- `Schritt 3 PROBLEM: leg_3_controller ist inactive statt active`
- `Schritt 5 PROBLEM: Bein bewegt sich nicht, im T1-Log steht XYZ`

Bei Problemen: kein Volltext-Log paste, sondern den Pfad zum Log-File
oder einen `grep`-Befehl, mit dem Claude gezielt nachschaut.

---

## Schritt 1 — Full Build (T1)

**Befehl in T1:**
```bash
colcon build --packages-select hexapod_description hexapod_gazebo hexapod_control hexapod_bringup --symlink-install
```

**Was du sehen solltest:**
```
Summary: 4 packages finished [Xs]
```
Keine `Failed` oder `[stderr]`-Sektionen. Die `--allow-overriding`-Warnung
ist OK (harmlos).

**Was bedeutet `--symlink-install`?** YAML- und Launch-Files werden per
Symlink in `install/` verlinkt statt kopiert. Folge: nachträgliche
Änderungen an `controllers.yaml` oder `sim.launch.py` greifen ohne
Re-Build. Praktisch für den Rest von Stufe E.

**Status an Claude:** `Schritt 1 OK` oder Fehlermeldung.

---

## Schritt 2 — Sim starten (T1)

**Befehl in T1:**
```bash
ros2 launch hexapod_bringup sim.launch.py 2>&1 | tee /tmp/sim.log
```

`tee` schreibt die Logs sowohl auf den Bildschirm als auch nach
`/tmp/sim.log` — Claude kann dort später gezielt grep-en, ohne dass du
den Kontext mit Vollausgabe flutest.

**Was du sehen solltest (Reihenfolge zählt):**
1. Gazebo-GUI öffnet sich (eventuell ein paar Sekunden Verzögerung)
2. Default-Welt sichtbar (Boden + Sonne)
3. Hexapod fällt aus 0.20 m auf den Boden, landet auf den 6 Foot-Kugeln
4. In den Logs (auf dem Terminal): mehrere
   `[spawner-N] Configured and activated <controller_name>` über die
   nächsten 5-10 Sekunden — insgesamt 7 Stück (1× JSB + 6× leg_*).

**Sollte NICHT vorkommen:**
- Crash mit Stack-Trace
- `[ERROR] [controller_manager]: Could not find a parameter file`
- `Failed to load controller`
- Roboter durchschlägt den Boden oder kollabiert

**Status an Claude:**
- ok-Variante: `Schritt 2 OK, alle 7 Spawner durchgelaufen, Roboter steht stabil`
- problem-Variante: `Schritt 2 PROBLEM: <kurze Beschreibung>, Log unter /tmp/sim.log`

**Wenn Probleme:** Sim **nicht** beenden. Lass T1 laufen, Claude wird
gezielte `grep`-Befehle für `/tmp/sim.log` schicken.

---

## Schritt 3 — Controller + Hardware-Interfaces (T2)

T1 läuft weiter. **Drei Befehle in T2 nacheinander:**

```bash
ros2 control list_controllers
```

**Erwartung:**
```
joint_state_broadcaster   ... JointStateBroadcaster   active
leg_1_controller          ... JointTrajectoryController  active
leg_2_controller          ... JointTrajectoryController  active
leg_3_controller          ... JointTrajectoryController  active
leg_4_controller          ... JointTrajectoryController  active
leg_5_controller          ... JointTrajectoryController  active
leg_6_controller          ... JointTrajectoryController  active
```
Alle 7 müssen `active` sein. Nicht `inactive`, nicht `unconfigured`.

```bash
ros2 control list_hardware_interfaces
```

**Erwartung — Anzahlen zählen:**
- `command interfaces`: 18 Einträge mit `position` (alle als `[available]` oder `[claimed]`)
- `state interfaces`: 36 Einträge — 18× `position`, 18× `velocity`

```bash
ros2 topic list | grep -E '/joint_states|/leg_._controller/joint_trajectory'
```

**Erwartung:**
```
/joint_states
/leg_1_controller/joint_trajectory
/leg_2_controller/joint_trajectory
/leg_3_controller/joint_trajectory
/leg_4_controller/joint_trajectory
/leg_5_controller/joint_trajectory
/leg_6_controller/joint_trajectory
```
7 Zeilen.

**Status an Claude:** `Schritt 3 OK: 7 Controller active, 18 cmd / 36 state interfaces, 7 Topics da`

Falls Differenzen: konkret welche Zahl abweicht oder welcher Controller
nicht active ist.

---

## Schritt 4 — `/joint_states`-Sanity (T2)

**Befehl in T2:**
```bash
ros2 topic echo /joint_states --once
```

**Erwartung:**
- `name:` Liste mit 18 Einträgen `leg_1_coxa_joint`, `leg_1_femur_joint`,
  …, `leg_6_tibia_joint`
- `position:` Liste mit 18 Floats, alle nahe 0 (Default-Pose, evtl.
  ±0.01 wegen Settling auf dem Boden)
- `velocity:` Liste mit 18 Floats, alle nahe 0 (Roboter steht still)

**Status an Claude:** `Schritt 4 OK: 18 Joints in /joint_states, alle Positionen ~0`

---

## Schritt 5 — Bewegungstest Bein 1 (T2)

**Befehl in T2 (eine Zeile, sicher per Copy-Paste):**
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory '{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.3, -0.5, 1.0], time_from_start: {sec: 2}}]}'
```

**Was du sehen solltest:**
1. T2-Output: `publisher: beginning loop` und kurz danach Exit (`--once`)
2. **In Gazebo:** Bein 1 (vorne rechts, siehe `00_conventions.md` §1)
   schwenkt + hebt + knickt sich binnen 2 s in die Zielpose. Sichtbar
   und smooth.
3. Nach 2 s steht der Roboter mit Bein 1 in der neuen Pose, alle
   anderen 5 Beine unverändert.

**Sollte NICHT vorkommen:**
- Bein zuckt nur, fährt nicht durch
- Bein bewegt sich abrupt / unkontrolliert
- Anderes Bein bewegt sich (Joint-Mismatch!)

**Status an Claude:** `Schritt 5 OK: Bein 1 fährt smooth in 2s in Zielpose`

Falls keine Bewegung: `Schritt 5 PROBLEM: Bein 1 bewegt sich nicht, T2 zeigt <X>`

---

## Schritt 6 — RViz parallel (T3)

**Befehl in T3:**
```bash
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
```

**In der RViz-GUI:**
1. Linke Spalte → "Add" Button (ganz unten) → Tab "By display type" →
   `RobotModel` auswählen → OK
2. Im Tree links: `RobotModel` aufklappen → `Description Topic` auf
   `/robot_description` setzen
3. Oben links: `Fixed Frame` von `map` auf `base_link` umstellen
4. Erwartung: Hexapod-Modell erscheint in RViz, **mit Bein 1 in der
   verschobenen Pose aus Schritt 5** (RViz sollte den aktuellen Stand
   zeigen, nicht die Default-Pose)

**Wichtig — was du NICHT machst:**
- Keine `joint_state_publisher`-Krücke starten (würde mit JSB doppelt
  publishen, Konflikt!)
- Wenn RViz statt Live-States die Default-Pose zeigt → Problem mit
  `use_sim_time` oder `/joint_states` kommt nicht durch

**Status an Claude:** `Schritt 6 OK: RViz folgt Gazebo, Bein 1 auch in RViz in verschobener Pose`

---

## Schritt 7 — Symmetrie-Test Bein 4 + Multi-Bein-Tests (T2)

Drei Teil-Befehle in dieser Reihenfolge.

### 7a — Symmetrie-Test Bein 4

**Befehl in T2:**
```bash
ros2 topic pub --once /leg_4_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory '{joint_names: [leg_4_coxa_joint, leg_4_femur_joint, leg_4_tibia_joint], points: [{positions: [0.3, -0.5, 1.0], time_from_start: {sec: 2}}]}'
```

**Erwartung:** Bein 4 (hinten links) fährt analog zu Bein 1 binnen 2 s in
gleiche Joint-Werte. Sowohl Gazebo als auch RViz folgen.

Nach 7a hängen Bein 1 und Bein 4 in `[0.3, -0.5, 1.0]`, die anderen 4 in der Default-Pose (auf dem Bauch).

### 7b — Reset: alle 6 Beine zurück auf Ursprung `[0, 0, 0]`

**Befehl in T2** (Bash-Schleife, sendet alle 6 Trajektorien parallel via
`&`, sodass sie quasi gleichzeitig in Gazebo ankommen):

```bash
for i in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${i}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${i}_coxa_joint, leg_${i}_femur_joint, leg_${i}_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}" &
done; wait
```

**Was passiert:** 6 `ros2 topic pub`-Prozesse werden parallel gestartet.
Jeder schickt seine Trajektorie an seinen Bein-Controller, dann beendet
sich (`--once`). `wait` sammelt alle Subprozesse ein, damit das Skript
sauber endet.

**Erwartung in Gazebo:**
- Bein 1 und Bein 4 fahren aus ihrer angehobenen Pose zurück in
  Default (alle Joints = 0)
- Andere 4 Beine bewegen sich praktisch nicht (waren schon ~0)
- Hexapod plumpst wieder auf den Bauch
- Innerhalb 2 s

### 7c — Alle 6 Beine anheben (Vorgriff auf Stand-Pose, „doppelt so hoch")

**Befehl in T2:**

```bash
for i in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${i}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${i}_coxa_joint, leg_${i}_femur_joint, leg_${i}_tibia_joint], points: [{positions: [0.3, -1.0, 1.5], time_from_start: {sec: 2}}]}" &
done; wait
```

**Pose-Begründung** (`[0.3, -1.0, 1.5]` statt der Schritt-5-Pose
`[0.3, -0.5, 1.0]`): naive Verdopplung der Hub-Werte (femur −0.5→−1.0,
tibia 1.0→2.0). Tibia ist allerdings durch das physische Joint-Limit
auf ±1.50 rad begrenzt (siehe `00_conventions.md` §11.4, am echten
Roboter mechanisch verifiziert) — daher `1.5` statt `2.0`.

**Erwartung in Gazebo:**
- Alle 6 Beine fahren synchron in 2 s in die Pose `[0.3, -1.0, 1.5]`
- Hexapod hebt sich deutlich höher vom Boden als bei der Schritt-5-Pose
- Wackel-/Rutsch-Verhalten zeigt einen ersten Eindruck der
  Reibungsparameter — wird in **Stufe F** mit der „echten"
  Stand-Pose `[0, -0.5, 1.0]` (ohne coxa-Schwenk, moderater Hub)
  systematisch verifiziert

**Tuning-Hinweis** (falls dir „doppelt so hoch" noch nicht hoch genug
ist): den femur-Wert weiter negativ ziehen (bis ca. `-1.5`, knapp
unter dem Limit ±1.57). tibia kann nicht über 1.5 hinaus —
mechanischer Anschlag.

**Status an Claude:** `Schritt 7 OK: 7a Bein 4 symmetrisch, 7b Reset auf Ursprung, 7c alle 6 Beine angehoben`

Falls 7b oder 7c Probleme zeigen (z.B. ein Bein bewegt sich nicht
synchron, Hexapod kippt seitlich um, etc.), Beobachtung kurz
beschreiben — das ist relevant für die Diagnose in Stufe F.

---

## Aufräumen nach Stufe E

```bash
# T2, T3: Strg-C falls noch Prozesse laufen
# T1: Strg-C beendet die Sim
```

`/tmp/sim.log` darf liegen bleiben (wird vom System eh aufgeräumt) oder
manuell `rm /tmp/sim.log`.

---

## Bei Problemen — wie Logs an Claude übermitteln

**Regel:** **Niemals** den vollen Sim-Log paste. Stattdessen:

```bash
# Letzte 30 Zeilen
tail -n 30 /tmp/sim.log

# Nur ERROR/WARN
grep -E '\[(ERROR|WARN)\]' /tmp/sim.log

# Nur Spawner-Output
grep -i spawner /tmp/sim.log

# Spezifischen Controller checken
grep leg_3_controller /tmp/sim.log
```

**Übermittlung an Claude:** entweder
- Die Output-Zeilen direkt (wenn ≤ ~20 Zeilen),
- oder `Log unter /tmp/sim.log, bitte gezielt prüfen`. Claude bekommt
  dann konkrete `grep`-Befehle dazu.

---

## Was Claude im Hintergrund tut

Während du die Schritte abarbeitest:
- pro positiver Status-Meldung den entsprechenden Bullet in
  `phase_4_progress.md` Stufe E abhaken
- bei Problem-Status: Diagnose-Befehle vorschlagen, gezielt `grep`
  über `/tmp/sim.log`
- Stufen-Header E auf ✅ setzen, sobald alle 7 Schritte grün
