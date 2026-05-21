# Phase 11 — Sim-Tuning-Workshop

User-Manual mit Test-Szenarien für sinnvolles Walking-Param-Tuning in
der Gazebo-Sim. Verbindet die 14 gait_node-Live-Params (Stage A), die
Preset-YAMLs (Stage D + E) und die Save/Load-Workflows (Stage D-Setup-
Doku) zu konkreten Übungs-Aufgaben.

> **Vorbedingung:** Phase 11 Stage A-E abgeschlossen, alle Live-Param-
> Surfaces verifiziert. Sim-Stack hochgefahren (siehe Setup-Sektion
> unten).

---

## Setup

> **Wichtig:** alle `params_file:=src/...`-Pfade in den Szenarien sind
> **relativ zum aktuellen Arbeitsverzeichnis**. Daher in **Terminal 3**
> (gait_node) vorher `cd ~/hexapod_ws`. Falls vergessen: ROS-Launch
> warnt mit `WARNING: Parameter file path is not a file: ...` und
> startet mit Inline-Defaults statt mit dem Preset.
>
> Alternative — Bash-Aliases (sourcen einmal pro Shell):
> ```bash
> source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
> hexapod-load-walking-preset <preset-name>
> ```
> Alias nutzt absoluten Pfad → funktioniert unabhängig vom cwd.

Wenn die folgenden Szenarien durchgespielt werden sollen, in 4
Terminals:

```bash
# Terminal 1 — Sim
ros2 launch hexapod_bringup sim.launch.py

# Terminal 2 — RViz (Robot-Visualisierung)
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz

# Terminal 3 — gait_node (wird pro Szenario neu gestartet)
ros2 launch hexapod_gait gait.launch.py

# Terminal 4 — Befehle (cmd_vel, param get/set, rqt)
# Hier laufen die Szenario-Befehle
```

Für Live-Param-Tuning zusätzlich:
```bash
# Terminal 5 (optional)
ros2 run rqt_reconfigure rqt_reconfigure
```

Optional Convenience-Aliases sourcen (siehe
[phase_11_rqt_setup.md](phase_11_rqt_setup.md) Sektion 5):
```bash
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
```

---

## Szenario 1 — Langsamer Vorwärts-Walk (Defensive)

**Use-Case:** Erstinbetriebnahme, Bench-Tests, neue Hardware-Cal-Sessions.
Konservative Werte minimieren Stress auf Servos und IK.

**Preset:** [`defensive_walk.yaml`](../src/hexapod_gait/config/presets/defensive_walk.yaml)
(Stage D)

**Charakteristik (siehe Preset-File für Werte):**
cycle_time deutlich langsamer, kleinere Stride, niedrigere Foot-Hub,
Body etwas höher.

**Befehle:**
```bash
# Terminal 3: gait_node mit Preset
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml

# Terminal 4: vorwärts mit niedrigem Tempo
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Erwartete Beobachtung:**
- Roboter läuft sichtbar langsam, lange Pausen zwischen Bein-Hubs
- Tripod-Gangart deutlich erkennbar (immer 3 Beine in der Luft)
- Sehr stabil — keine Schwankungen, keine Stride-Kollisionen
- Anti-Tipp-Reserve hoch (Body sichtbar höher über Boden)

**Wofür gut:** als Einstiegs-Konfiguration zum Verstehen wie das gait_node
walking macht. Für Hardware-Bench-First-Tests die sicherste Wahl.

---

## Szenario 2 — Mittel-schneller Vorwärts-Walk (Demo)

**Use-Case:** Phase-11-Doku-Beispiele, Demo-Videos, Erst-Eindruck wie
der Roboter aussieht.

**Preset:** [`demo_walk.yaml`](../src/hexapod_gait/config/presets/demo_walk.yaml)
(Stage E)

**Charakteristik:** Defaults + leicht erhöhter step_height für aktiveres
Walking. Alle anderen Werte = `gait.launch.py`-Defaults.

**Befehle:**
```bash
# Terminal 3
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/demo_walk.yaml

# Terminal 4
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.04}}'
```

**Erwartete Beobachtung:**
- Mittleres Tempo (linear_max=0.05 m/s)
- Beine heben sichtbar höher als bei defensive_walk (3.5 cm statt 2.5 cm)
- Tripod-Gangart in „normalem" Rhythmus
- Stabil, kein Schlingern

**Wofür gut:** zum Zeigen wie der Hexapod „normal" aussieht. Ausgangs-
Konfiguration für eigene Tuning-Experimente.

---

## Szenario 3 — Schneller Vorwärts-Walk (Aggressive)

**Use-Case:** Phase-13-Performance-Test, Stress-Demo, Verständnis wo
die IK-/Mechanik-Limits liegen.

**Preset:** [`aggressive_walk.yaml`](../src/hexapod_gait/config/presets/aggressive_walk.yaml)
(Stage E)

**Charakteristik:** schnellerer Cycle (1.5 s), größere Stride (0.06 m),
höhere Foot-Hub (4 cm), Body etwas tiefer (-0.055 m).

`linear_max = step_length_max / stance_duration = 0.06 / 0.75 = 0.08 m/s`
(Faktor 1.6× Default).

**Befehle:**
```bash
# Terminal 3
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/aggressive_walk.yaml

# Terminal 4
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.07}}'
```

**Erwartete Beobachtung:**
- Merklich schneller als demo_walk
- Beine schwingen weiter aus
- Etwas „nervöser" Gang — größere Bewegungen pro Tick

**⚠️ Achtung — Risiko-Punkte:**
- Bei `cycle_time` noch kürzer (z.B. 1.0): IK kann out-of-reach
  laufen wenn die Beine ihre maximale Reichweite überschreiten
- Auf echter HW (Phase 13): Stromaufnahme wird deutlich höher, Servos
  arbeiten unter Volllast
- Bei Wechsel auf aggressive_walk first time: Roboter aufgebockt halten
  (Beine ohne Bodenkontakt) und linear.x schrittweise hochfahren

**Wofür gut:** zum Probieren wo das System seine Grenzen hat. Bevor
echte Hardware-Demos.

---

## Szenario 4 — Drehen auf der Stelle

**Use-Case:** Wendeverhalten verifizieren, ohne dass der Roboter
linear fährt. Wichtig für später Joystick-Tests in Phase 13.

**Preset:** beliebig — typisch `demo_walk.yaml` oder `defensive_walk.yaml`.

**Befehle:**
```bash
# Terminal 3 (irgendeines der Walking-Presets — hier demo)
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/demo_walk.yaml

# Terminal 4 — nur angular.z
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{angular: {z: 0.4}}'
```

**Erwartete Beobachtung:**
- Roboter dreht sich um die Body-Z-Achse (Yaw) gegen Uhrzeigersinn
  (positive z = CCW, ROS-Standard)
- Beine treten gleichmäßig nach außen versetzt
- Position bleibt etwa konstant (= Stationäre Rotation)
- Tripod-Tempo wie beim Vorwärtslauf

**Variation — gegen Uhrzeigersinn:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{angular: {z: -0.4}}'
```

**Wofür gut:** Beweis dass `angular.z`-Komponente getrennt funktioniert.
In Phase 6 als Joystick-Yaw-Mapping verwendet.

---

## Szenario 5 — Kurvenfahrt (linear + angular kombiniert)

**Use-Case:** Demonstration der Stage-H-Omnidirektional-Fähigkeit. Roboter
läuft vorwärts und dreht gleichzeitig — beschreibt eine Kurve.

**Preset:** `demo_walk.yaml` oder Default.

**Befehle:**
```bash
# Terminal 3
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/demo_walk.yaml

# Terminal 4 — kombinierte cmd_vel
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.03}, angular: {z: 0.2}}'
```

**Erwartete Beobachtung:**
- Roboter läuft vorwärts UND dreht — beschreibt eine Bogen-Kurve
- Tripod-Gangart bleibt sauber
- Falls beide Werte zu hoch: Engine clampt automatisch
  (siehe `linear_max`-Begrenzung in gait_engine.set_command)

**Wofür gut:** Verifikation dass die Engine omnidirektional clamped statt
nur einen Wert zu accepten. Phase-6-Joystick-Demo basiert darauf.

---

## Szenario 6 — body_height-Live-Variation

**Use-Case:** Demonstration der Stage-A-Live-Param-Funktionalität.
Roboter „atmet" durch Höhen-Variation während des Walks.

**Voraussetzung:** Roboter in STANDING-State (gait_node läuft, aber
keine cmd_vel-Stream aktiv).

**Befehle:**
```bash
# Terminal 3
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml

# Terminal 5 — rqt_reconfigure
ros2 run rqt_reconfigure rqt_reconfigure
# /gait_node-Node auswählen, body_height-Slider verschieben

# Alternative: per CLI
ros2 param set /gait_node body_height -0.045    # höher
ros2 param set /gait_node body_height -0.075    # tiefer
ros2 param set /gait_node body_height -0.052    # zurück zu Default
```

**Erwartete Beobachtung:**
- Roboter hebt/senkt sich live in RViz und Gazebo
- Smooth-Transition durch JTC-Interpolation
- Bei `body_height > body_height_max` (Default -0.030) oder
  `< body_height_min` (Default -0.080): Param-Update wird abgelehnt
  (Stage-A Cross-Constraint-Validation)

**Wichtige Stage-A-Restriction:**
- `body_height`-Update **nur in STANDING-State** akzeptiert (Kipp-Schutz)
- Wenn cmd_vel aktiv läuft (= WALKING): Update wird mit klarer reason
  abgelehnt

**Wofür gut:** Demonstration der STANDING-only-Sicherheitslogik aus
Stage A.

---

## Weiterführend — Cross-Phase-Hinweise

| Thema | Wo dokumentiert |
|---|---|
| Wie man Params live ändert (rqt_reconfigure) | [phase_11_rqt_setup.md](phase_11_rqt_setup.md) Sektion 1 |
| Eigene Tuning-Snapshots speichern | [phase_11_rqt_setup.md](phase_11_rqt_setup.md) Sektion 2-3 |
| Plugin-Cal-Tuning (anderer Mechanismus) | [hexapod_hardware/README.md](../src/hexapod_hardware/README.md) Phase-11-Stage-B-Sektion |
| Convenience-Aliases | [tools/hexapod-shell-aliases.sh](../tools/hexapod-shell-aliases.sh) Top-Kommentar |
| Initial/Stand/Shutdown-Posen (Phase 13) | Memory `project_phase13_initial_pose_presets.md` |
| PS4-Controller-Integration (Phase 6) | [hexapod_teleop/README.md](../src/hexapod_teleop/README.md) — kombiniert Szenarien 1-5 unter einem Joystick |

---

## Was bewusst NICHT in der Workshop-Doku

- **Performance-Profiling** (CPU/Memory) der Presets — Phase-13-Polish
- **Auto-Tuning** (Bayesian-Optimierung) — Phase-13+
- **Echte HW-Beobachtungen** — Phase 13 (diese Doku ist Sim-only)
- **Numerische Metriken** (Stop-Latenz aus cmd_vel=0 etc.) — bei
  Bedarf in Phase 13 mit Bench-Daten ergänzbar
