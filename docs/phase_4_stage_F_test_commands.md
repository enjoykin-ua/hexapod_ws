# Phase 4 — Stufe F: Test-Befehle (User-Operations-Handbuch)

> **Rollen-Aufteilung** wie in Stufe E:
> - **Du** führst alle Befehle aus, gibst pro Schritt eine **kurze**
>   Status-Rückmeldung an Claude.
> - **Claude** wartet auf deine Status-Meldung, hakt im Progress-File ab,
>   gibt nächsten Schritt frei oder geht in Diagnose / Tuning, wenn was
>   schiefgeht.
>
> **Ziel der Stufe:** Phase-3-Done-Kriterium 4 nachholen — Roboter steht
> stabil auf 6 Foot-Kugeln in der Stand-Pose `[0, -0.5, 1.0]`,
> Reibungswerte (`mu1`, `mu2`, `kp`, `kd`) verifiziert oder nachjustiert.
>
> **Tuning-Strategie:** erst mit Default-Werten testen (`mu=1.0`,
> `kp=1e6`, `kd=100`), nur tunen wenn ein konkretes Problem auftritt.
> Pro Iteration genau **eine** Stellschraube, sonst lässt sich Ursache
> und Wirkung nicht mehr trennen.

---

## Vorbereitung — Terminals einrichten

Wie in Stufe E. **Drei Terminals**, in jedem als erstes:

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

| Terminal | Zweck |
|---|---|
| **T1** | Sim-Launch (bleibt offen, läuft die ganze Stufe) |
| **T2** | Stand-Pose-Befehl + `gz model`-Drift-Messung |
| **T3** | RViz (optional, hilfreich für 3D-Sicht der Stand-Pose) |

Logs der Sim wieder nach `/tmp/sim.log`, damit Claude bei Problemen
gezielt grep-en kann.

---

## Status-Rückmeldung an Claude — Format

Pro Schritt **eine** Zeile reicht. Beispiele:

- `Schritt 1 OK`
- `Schritt 3 OK, steht stabil auf 6 Beinen, kein Zittern`
- `Schritt 3 PROBLEM: Bein 2 rutscht weg, Roboter dreht sich langsam`
- `Schritt 4 OK, z=0.0431 konstant, RPY ändert sich um <0.1°`

Bei Problemen: `grep`-Output oder Pfad zum Log, niemals Vollausgabe.

---

## Schritt 1 — Sim starten (T1)

**Befehl in T1:**
```bash
ros2 launch hexapod_bringup sim.launch.py 2>&1 | tee /tmp/sim.log
```

**Was du sehen solltest** (identisch zu Stufe E Schritt 2):
1. Gazebo-GUI öffnet sich
2. Hexapod fällt aus 0.20 m, landet, **liegt auf dem Bauch**
3. T1-Logs: 7× `Configured and activated <controller_name>`

**Status an Claude:** `Schritt 1 OK` oder Fehlermeldung.

---

## Schritt 2 — RViz starten (T3, optional aber empfohlen)

Hilft beim 3D-Eindruck der Stand-Pose, weil die Gazebo-Kamera oft
suboptimal positioniert ist.

**Befehl in T3:**
```bash
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
```

**RViz-Setup** (wie in Stufe E Schritt 6):
1. **Add** → **By display type** → **RobotModel** → OK
2. `RobotModel` aufklappen → `Description Topic` = `/robot_description`
3. `Fixed Frame` = `base_link`

**Status an Claude:** `Schritt 2 OK` oder `Schritt 2 SKIP` (wenn ohne
RViz reicht).

---

## Schritt 3 — Stand-Pose auf alle 6 Beine in 4 s (T2)

**Pose:** `coxa=0`, `femur=-0.5`, `tibia=+1.0` — kanonische Stand-Pose
ohne coxa-Schwenk, jedes Bein zeigt natürlich in seine Mountpunkt-
Richtung.

**`time_from_start: 4` s** (nicht 2 s wie in Stufe E Schritt 5):
sanfteres Anfahren reduziert Sprung-/Schwung-Effekte beim ersten
Bodenkontakt der Foot-Kugeln.

**Befehl in T2:**

```bash
for i in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${i}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
    "{joint_names: [leg_${i}_coxa_joint, leg_${i}_femur_joint, leg_${i}_tibia_joint], points: [{positions: [0.0, -0.5, 1.0], time_from_start: {sec: 4}}]}" &
done; wait
```

**Was du sehen solltest in Gazebo (über die nächsten ~4-5 s):**
1. Alle 6 Beine fahren synchron nach unten
2. Foot-Kugeln berühren den Boden, Chassis hebt sich vom Boden ab
3. Nach 4 s: Roboter steht auf 6 Foot-Kugeln, Chassis schwebt knapp
   über dem Boden
4. Pose **bleibt stabil** stehen (kein Wegrutschen, kein Zittern, kein
   Kippen)

**Status an Claude:**
- ok-Variante: `Schritt 3 OK, steht stabil auf 6 Beinen`
- problem-Variante (kurze Beobachtung): z. B.
  - `Schritt 3 PROBLEM: hochfrequentes Zittern in den Tibias`
  - `Schritt 3 PROBLEM: Bein N rutscht weg / Chassis dreht sich`
  - `Schritt 3 PROBLEM: Beine geben unter Last nach, Chassis sinkt durch`
  - `Schritt 3 PROBLEM: Roboter springt beim Pose-Anfahren ab`

**Sim NICHT beenden bei Problemen** — Claude diagnostiziert mit dir
gemeinsam und gibt eine gezielte Stellschraube an, die wir per
Code-Edit + Re-Build + Schritt 1 erneut testen.

---

## Schritt 4 — Numerische Drift-Messung (T2)

Visuell „steht stabil" reicht für die erste Aussage, aber Done-Kriterium
fordert Drift `< 1 mm` / `< 0.5°` über 5 Sekunden. Das misst der
folgende Befehl.

**Befehl in T2** (5 Samples mit 1 s Abstand):

```bash
for s in 1 2 3 4 5; do
  echo "--- Sample ${s} ---"
  gz model -m hexapod -p
  sleep 1
done | tee /tmp/pose_drift.log
```

**Erwartung im Output:** 5 Pose-Blöcke. In jedem Block:
- `Pose [ XYZ (m) ]`-Zeile mit drei Werten — der **dritte** Wert ist `z`
  (Höhe über Boden)
- `Pose [ RPY (rad) ]` oder Quaternion-Block — dort die Orientierung

**Was wir prüfen** (manuell durchsehen):
- `z` ändert sich zwischen den 5 Samples um < 0.001 m (1 mm)
- RPY-Werte ändern sich um < 0.0087 rad (= 0.5°)

**Status an Claude:** `Schritt 4 OK, z drifted um Xmm, RPY um Y°` oder
Pfad zum Log mit der Bitte, Claude soll selbst prüfen:
`Schritt 4 OK, Log unter /tmp/pose_drift.log` — Claude liest dann
gezielt mit `grep` nach.

**Bei merklichem Drift** (> 1 mm pro Sekunde, oder Roboter „sickert"
sichtbar): `Schritt 4 PROBLEM: Drift X mm/s`. Das deutet auf zu weichen
Kontakt (`kp`) oder zu schwachen Boden hin.

---

## Schritt 5 — Bewertung + Entscheidung

Drei mögliche Ausgänge, je nachdem wie Schritt 3 + 4 gelaufen sind:

### A — Alles grün, Default-Werte ausreichend

**Aktionen** (Claude führt aus):
- [hexapod_gazebo/README.md](../src/hexapod_gazebo/README.md) Defer-Hinweis
  durch „verifiziert in Phase 4 Stufe F" ersetzen
- [phase_3_progress.md](phase_3_progress.md) DK4-Status auf ✅
- [README.md](../README.md) Workspace-Status entsprechend updaten
- Memory-Eintrag
  [project_phase3_defer_stand_test.md](file:///home/enjoykin/.claude/projects/-home-enjoykin-hexapod-ws/memory/project_phase3_defer_stand_test.md)
  als „erledigt" markieren oder löschen

### B — Problem, gezielte Stellschraube ziehen

| Symptom | Erste Stellschraube |
|---|---|
| Wegrutschen | `mu1`, `mu2` `1.0` → `1.5` in [hexapod.gazebo.xacro](../src/hexapod_description/urdf/hexapod.gazebo.xacro) |
| Zittern (hochfrequent) | `kp` `1e6` → `1e7` in [hexapod.gazebo.xacro](../src/hexapod_description/urdf/hexapod.gazebo.xacro) |
| Zittern bleibt nach kp-Erhöhung | `inertia_min` `1e-5` → `1e-4` in [inertials.xacro](../src/hexapod_description/urdf/inertials.xacro) |
| Beine geben unter Last nach | `time_from_start` 4s → 6s im Pose-Befehl |
| Springen beim Pose-Anfahren | `time_from_start` 4s → 6s, ggf. 8s |

**Vorgehen pro Iteration:**
1. T1 mit Strg-C beenden (Sim stoppen)
2. Claude editiert die eine Stellschraube
3. T1 neu builden + sourcen + Sim starten:
   ```bash
   colcon build --packages-select hexapod_description --symlink-install
   source install/setup.bash
   ros2 launch hexapod_bringup sim.launch.py 2>&1 | tee /tmp/sim.log
   ```
4. Schritt 3 + 4 erneut, Vergleich mit der vorherigen Iteration
5. Iteration im Phasenabschluss-Bericht festhalten (was wurde geändert,
   was war der Effekt)

### C — Problem ist nicht durch Reibung lösbar

Beispiel: Beine geben strukturell nach trotz langer Trajektorie und
hoher Reibung → JTC-PID-Gains in [controllers.yaml](../src/hexapod_control/config/controllers.yaml)
setzen. Das ist der größere Eingriff (eigene Iteration, eigene Beobachtung).

---

## Aufräumen nach Stufe F

```bash
# T2, T3: Strg-C falls Prozesse laufen
# T1: Strg-C beendet die Sim
# Logs aufräumen optional:
rm /tmp/sim.log /tmp/pose_drift.log
```

---

## Bei Problemen — wie Logs an Claude übermitteln

Gleiche Regel wie Stufe E: **niemals** den vollen Sim-Log paste.
Statt­dessen gezielt:

```bash
# Letzte 30 Zeilen
tail -n 30 /tmp/sim.log

# Nur ERROR/WARN
grep -E '\[(ERROR|WARN)\]' /tmp/sim.log

# Spezifischen Controller checken (z. B. wenn Bein 3 nachgibt)
grep leg_3_controller /tmp/sim.log

# Pose-Drift-Log auswerten
cat /tmp/pose_drift.log
```

Übermittlung an Claude: Output-Zeilen direkt (≤ ~20 Zeilen) oder
`Log unter /tmp/sim.log, bitte gezielt prüfen`.

---

## Was Claude im Hintergrund tut

Während du die Schritte abarbeitest:
- pro positiver Status-Meldung den entsprechenden Bullet in
  `phase_4_progress.md` Stufe F abhaken
- bei Problem-Status: Diagnose-Vorschlag, gezielte Stellschraube,
  ggf. Edit-Vorschlag mit User-Bestätigung
- nach Erfolg in Schritt 5: Doku-Updates (READMEs, Phase-3-progress,
  Memory) automatisch ziehen
- Stufen-Header F auf ✅ setzen, sobald Done-Kriterien erfüllt
