# Phase 11 — Stufe E — Test-Kommandos

> **Stage E:** Sim-Tuning-Workshop + Best-Param-Presets + Tibia-Sim-
> Verifikation.
>
> **Plan:** [`phase_11_stage_e_plan.md`](phase_11_stage_e_plan.md)
> **Workshop-Doku:** [`phase_11_sim_tuning_workshop.md`](phase_11_sim_tuning_workshop.md)

---

## Vorbedingung

- Stage A + B + C + D abgeschlossen
- Stage-E-Code committet: `demo_walk.yaml` + `aggressive_walk.yaml` +
  Workshop-Doku
- Frischer Sim-Stack (vorher killen falls noch was läuft):
  ```bash
  pkill -9 -f "ros2|gz|ruby|rviz2|rqt|gait_node"; sleep 4
  ```

---

## Terminal-Konvention für die User-Smoke-Tests

- **Terminal 1** = Sim-Bringup (`sim.launch.py` — Gazebo + Controllers, Vordergrund)
- **Terminal 2** = RViz (`rviz2 -d <view.rviz>`, Vordergrund)
- **Terminal 3** = gait_node (Vordergrund — bei jedem Preset-Wechsel Ctrl+C + neu starten)
- **Terminal 4** = Befehle gegen den Stack (cmd_vel publish, param get/set)

> **Wichtig — `params_file`-Pfad-Auflösung:**
> Die `params_file:=src/...`-Pfade in den folgenden Befehlen sind
> **relativ zum aktuellen Arbeitsverzeichnis**. ROS-Launch warnt nur
> mit `WARNING: Parameter file path is not a file: ...` falls Pfad
> nicht existiert — Launch startet trotzdem mit Inline-Defaults.
>
> **Vor jedem Terminal-3-Befehl:**
> ```bash
> cd ~/hexapod_ws
> ```
>
> Oder als robuste Alternative die Bash-Aliases nutzen (sourcen einmal
> pro Shell):
> ```bash
> source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
> hexapod-load-walking-preset demo_walk
> ```
> Der Alias nutzt intern den absoluten Pfad — funktioniert von überall.

---

## Claude-Tests (CI-Pfad)

### E-T1 — colcon build hexapod_gait grün

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait
```

**Erwartung:** grün.

### E-T2 — colcon test + Preset-Files im install-tree

```bash
colcon test --packages-select hexapod_gait
ls install/hexapod_gait/share/hexapod_gait/config/presets/
```

**Erwartung:**
- hexapod_gait 20/0/1 (unverändert)
- Liste der Preset-YAMLs zeigt:
  - `defensive_walk.yaml` (Stage D)
  - `current_state.yaml` (Stage D)
  - `demo_walk.yaml` (Stage E NEU)
  - `aggressive_walk.yaml` (Stage E NEU)
  - `README.md` (Stage D)

---

## User-Smoke-Tests (Sim, jeweils ~5-10 min)

### E-T3a — `demo_walk.yaml` in Sim

**Terminal 1** (Sim):
```bash
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
Warten bis alle Controller spawn-ed sind (Logger zeigt
`leg_*_controller — configured` ×6 + `joint_state_broadcaster — active`).

**Terminal 2** (RViz):
```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz
```

**Terminal 3** (gait_node mit Preset):
```bash
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/demo_walk.yaml
```

Logger sollte zeigen:
```
[gait_node]: gait_node init: ..., cycle_time=2.00 s, ...
              step_length_max=0.050 m (linear_max=0.050 m/s), ...
              step_height=0.035 m
```

**Terminal 4** (Walking starten):
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.04}}'
```

**Erwartung (~10 s beobachten):**
- Roboter läuft vorwärts mit sichtbarer Tripod-Gangart
- Beine heben sich ~3.5 cm hoch (etwas höher als defensive_walk's 2.5 cm)
- Keine IK-Errors im gait_node-Terminal
- Keine Stolper-/Kipp-Anzeichen in RViz

Walking stoppen: `Ctrl+C` im Terminal 4, dann
```bash
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{}'
```

→ ✅ wenn Roboter wie beschrieben läuft.

### E-T3b — `aggressive_walk.yaml` in Sim

**Terminal 3** — gait_node Ctrl+C, dann:
```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/aggressive_walk.yaml
```

Logger sollte zeigen:
```
[gait_node]: ..., cycle_time=1.50 s, ...
              step_length_max=0.060 m (linear_max=0.080 m/s), ...
              step_height=0.040 m, body_height=-0.055 m
```

**Terminal 4** (Walking — schneller als demo):
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.07}}'
```

**Erwartung (~10 s beobachten):**
- Roboter läuft deutlich schneller als demo_walk (linear_max=0.08 m/s
  statt 0.05 m/s)
- Beine schwingen weiter aus (step_length_max=0.06)
- **Kritisch:** keine IK-OutOfReach-Errors im gait_node-Terminal
- Keine Kipp-/Schlinger-Bewegungen in RViz
- Falls IK-Errors: aggressive_walk-Werte müssen konservativer (Plan-
  Korrektur in Stage E)

Walking stoppen wie bei E-T3a.

→ ✅ wenn Roboter merklich schneller läuft + keine IK-Errors.

### E-T4 — Tibia-Sim-Verifikation (Cross-Phase-Pendenz aus Phase 10)

**Voraussetzung:** Sim aus E-T3 noch läuft (RViz + Gazebo).

**Punkt 1: Tibia-Länge visuell in RViz**

RViz-Fenster prüfen: Tibia-Segmente (untere Bein-Hälfte) sollten ~20 cm
lang sein (vorher 17.87 cm). Per Distanz-Vergleich gegenüber Coxa-Mount-
Höhe oder Body-Width prüfbar.

→ ✅ wenn Tibias visuell länger als vor 2026-05-17.

**Punkt 2: Stand-Pose nicht abnormal**

`defensive_walk.yaml` laden (Stand-Pose mit body_height=-0.050):
```bash
# Terminal 3: gait_node neu
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
```

Roboter sollte in RViz **normaler Stand-Pose** stehen: alle 6 Beine
gleichmäßig nach außen gerichtet, keine knickenden oder unnatürlich
gestreckten Beine.

→ ✅ wenn Stand-Pose visuell korrekt.

**Punkt 3: Walking-Smoke mit Tibia-Update**

**Terminal 4:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.03}}'
```

**~10 s beobachten:**
- Roboter läuft stabil vorwärts
- Keine IK-Errors (jetzt mit längerem Tibia muss IK trotzdem reachable
  bleiben)
- Keine plötzlichen Bein-Bewegungen die auf URDF-Mismatch hinweisen

→ ✅ wenn Walking sauber durchläuft.

**Punkt 4: Memory-Eintrag schließen**

Wenn alle 3 Sub-Punkte ✅: `project_phase10_tibia_length_sim_pending.md`
kann gelöscht (oder als „erledigt"-markiert) werden.

---

## Status-Tracking

Pro Test in [phase_11_progress.md](phase_11_progress.md) abhaken.

Bei Problemen mit `aggressive_walk` (IK-Errors): Plan-Korrektur in
Stage E nötig — `step_length_max` / `cycle_time` konservativer wählen.

Bei Problemen mit Tibia-Verifikation (Bein-Kollision, Stand-Pose
abnormal): URDF-/IK-Code prüfen, ggf. tibia_length-Update zurückrollen.
