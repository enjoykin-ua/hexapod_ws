# Rubicon-Scene für den App-Flow — §4-Plan

> **Ziel:** ein einziger Befehl **`ros2 launch hexapod_bringup always_on.launch.py scene:=rubicon`**
> → App verbindet → „Start" → Gazebo lädt die **Rubicon-Rauhterrain-Welt** (mit **Kamera**) →
> gait kommt mit **allen Terrain-Regelkreisen scharf** hoch → aufstehen + laufen. Der bisherige
> Flow (leere/flache Welt) bleibt Default unverändert; nur `scene:=rubicon` schaltet um.
>
> **Seite:** ROS (Launch/Welt/Preset). **Status: 🟡 Plan.**

---

## 0. Ziel + Abgrenzung

- **Ein-Befehl-Umschaltung** der On-Demand-Sim-Welt über einen `scene`-Arg, der durch die
  bestehende **config-getriebene** Launcher-Kette fließt (kein Umbau des App-Lifecycles).
- **Rubicon mit Kamera** (das `gz-sim-sensors-system` fehlt der Welt noch — Phase-4-Naht).
- **Terrain-Features default-scharf** für Rubicon (leveling + adaptive touchdown/stand + …), damit
  kein manuelles App-Toggling nötig ist. Umgesetzt per **Preset-`params_file`**, NICHT durch
  Ändern der `gait_node`-Code-Defaults (die bleiben opt-in `false` für alle anderen Welten).
- **Bewusst NICHT:** neue App-Arbeit (die App zeigt die scharfen Toggles automatisch, weil sie die
  Ist-Werte via `get_parameters` liest — §6a). Terrain-Lauf-Qualität/Tuning = Live-Sache (App-Panel).
  Der `real`-Pfad (HW) bleibt unberührt (`scene` greift nur im sim-Zweig).

## 1. Logik / Änderungspunkte

Kette: `always_on.launch.py scene:=rubicon` → `bringup_launcher` (`bringup_launch_args`) →
`bringup_ondemand.launch.py mode:=sim scene:=rubicon` → **`rubicon_walk`** (statt `ramp_walk`).

1. **`hexapod_gait/config/presets/rubicon.yaml`** (NEU) — Sim-Terrain-Preset: nur die **Enables**
   + `leveling_mode` scharf; Gains/Schwellen bleiben Code-Sim-Defaults. **Nicht** `use_sim_time`/
   `auto_standup_on_start`/`robot_description` setzen (die kommen aus dem Launch; `params_file`
   würde sie sonst überschreiben — Merge-Reihenfolge in `gait.launch.py`: params_file gewinnt).
2. **`hexapod_bringup/launch/rubicon_walk.launch.py`** (NEU) — spiegelt `ramp_walk`: inkludiert
   `rubicon.launch.py` (Sim + Rubicon-Welt + heightmap-Spawn) **+** verzögerten `gait.launch.py`
   (`params_file:=<rubicon.yaml>`, `use_sim_time:=true`, `auto_standup_on_start`-passthrough,
   `robot_description_file:=<urdf>`).
3. **`hexapod_bringup/launch/bringup_ondemand.launch.py`** — `scene`-Arg (Default `ramp`); im
   sim-Zweig `scene=='rubicon'` → `rubicon_walk` (auto_standup:=false, gait_delay), sonst wie bisher
   `ramp_walk` (slope 0).
4. **`hexapod_bringup/launch/always_on.launch.py`** — `scene`-Arg (Default `ramp`); wählt über
   `_launcher_cfg(mode, scene)` bei `scene:=rubicon` (sim) die Config **`launcher.sim.rubicon.yaml`**.
   ⚠️ **Nicht** per Param-Dict-Override (verifiziert: ein Plain-Dict landet unter Wildcard `/**` und
   der spezifische yaml-Node-Key `bringup_launcher:` schlägt ihn in rcl reihenfolge-unabhängig).
   Eine scene-spezifische yaml (spezifischer Key) ist zuverlässig. `_launcher_cfg` = pure Helper →
   offline testbar.
5. **`hexapod_supervisor/config/launcher.sim.rubicon.yaml`** (NEU) — Kopie von `launcher.sim.yaml`,
   nur `bringup_launch_args: ["mode:=sim", "scene:=rubicon"]`. (Guard-Params bei Änderung in beiden
   sim-Configs nachziehen.)
6. **`hexapod_gazebo/worlds/rubicon.sdf`** — `gz-sim-sensors-system` (ogre2) ergänzen (Kamera
   rendert sonst nicht — Phase-4-Gotcha). imu-/contact-system bleiben.

**Rubicon-Terrain-Preset — die Enables (aus `hw_terrain.yaml` abgeleitet, Sim-Gains):**
`leveling_enable` · `leveling_mode: auto` · `adaptive_touchdown_enable` · `adaptive_stand_enable` ·
`sensor_plausibility_enable` · `tip_detection_enable` · `slip_detection_enable`.
> ⚠️ `slip_detection_enable` (Kanten-Freeze) kann auf Rubicon-Abhängen triggern → im Preset an
> (User-Wunsch „alle Sachen"), aber **in der App live abschaltbar** (schöne Phase-5-Demo).

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Wie |
|---|---|---|
| **R1** alle geänderten Launch-Files parsen | Syntax | `ros2 launch … --print`/Import |
| **R2** `scene:=rubicon` erreicht `bringup_launch_args` | Plumbing | `always_on … --print` zeigt `scene:=rubicon` |
| **R3** `rubicon.sdf` valide + hat sensors/imu/contact-system | Kamera-Welt | `xmllint`/grep |
| **R4** `rubicon.yaml` lädt, setzt genau die Enables (kein use_sim_time/auto_standup) | Preset | yaml-Load-Check |
| **R5** `colcon build` + bestehende Tests grün (keine Regression) | Regression | `colcon test` |
| **R6 (Live/User)** `always_on scene:=rubicon` → App-Start → Rubicon lädt + `/camera/image_raw` rendert + `ros2 param get /gait_node adaptive_touchdown_enable` = true + App-Panel zeigt Toggles AN + Roboter läuft | End-to-End | test_commands (User) |

**Bewusst offen:** Terrain-Lauf-Qualität auf Rubicon (Live-Tuning via App) · echte Heightmap-
Spawn-Höhe justieren falls Roboter sackt/fällt (rubicon.launch.py-`spawn_z`).

## 3. Progress-Checkliste (Done-Vertrag)
```
Rubicon-Scene (App-Flow):
- [ ] RS.1 presets/rubicon.yaml (Sim-Terrain-Enables, keine Launch-Params) + im Paket installiert
- [ ] RS.2 rubicon_walk.launch.py (Rubicon-Sim + delayed gait + params_file:=rubicon.yaml)
- [ ] RS.3 bringup_ondemand.launch.py: scene-Arg + sim-branch-Switch (ramp|rubicon)
- [ ] RS.4 always_on.launch.py: scene-Arg -> bringup_launch_args-Override
- [ ] RS.5 rubicon.sdf: gz-sim-sensors-system (Kamera)
- [ ] RS.6 Static-Verify R1-R5 gruen (parse/print/xmllint/build/test)
- [ ] RS.7 Doku (README-Zeile scene:=rubicon, test_commands) + Self-Review
- [ ] RS.8 [Live, User] R6 End-to-End: Rubicon + Kamera + Toggles scharf + laufen
```

## 4. Offene Punkte
1. **`slip_detection_enable` an oder aus?** Vorschlag: **an** (User „alle Sachen"), mit App-Toggle als
   Ausweg. Falls es beim ersten Test ständig freezt → im Preset auf false, per App zuschaltbar.
2. **`leveling_mode: auto` vs `terrain`?** Vorschlag `auto` (Stand horizontal, Lauf folgt Hang — wie
   `hw_terrain.yaml`).
3. **Spawn-Höhe** — `rubicon.launch.py`-Default; ggf. beim ersten Live-Blick justieren.

## 5. Nachtrag (Live-Befund RS.8) — Controller-Timeout auf der schweren Welt

**Symptom:** Rubicon-Welt + Roboter + Kamera-Bild da, aber **kein Aufstehen**. `list_controllers`:
alle 6 Bein-Controller `active`, **`joint_state_broadcaster` `inactive`** → kein `/joint_states` →
`gait_node` gibt Auto-Standup auf. Manueller Fix bestätigt:
`ros2 control set_controller_state joint_state_broadcaster active` → Aufstehen klappt.

**Wurzel:** der JSB-Spawner feuert direkt nach dem Spawn (zuerst in der Kette). Auf der schweren
Rubicon-Heightmap + Kamera-Rendering ist das `gz_ros2_control`-Hardware-Interface da noch nicht
bereit → JSB-Aktivierung läuft in den Default-**5-s-Switch-Timeout** und bleibt inaktiv. Die
Bein-Controller feuern ~5 s später (auf JSB-Spawner-Exit) → da *ist* die Hardware bereit → sie
aktivieren. Klassisches Slow-World-Race.

**Fix (implementiert):**
- **`sim.launch.py`** — alle Controller-Spawner mit `--switch-timeout 30` +
  `--controller-manager-timeout 60`. Der Spawner wartet auf die langsam initialisierende Hardware;
  **harmlos für schnelle Welten** (aktivieren in <1 s, Timeout wird nie erreicht). Shared → hilft
  auch step/trench/slope, falls schwer.
- **`launcher.sim.rubicon.yaml`** — `gait_delay:=30.0` (statt 12) im `bringup_launch_args` →
  `gait_node` startet erst nach fliessenden `/joint_states` → Auto-Standup klappt ohne Nachhelfen.
