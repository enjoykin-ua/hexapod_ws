# Rubicon-Scene für den App-Flow — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets aus [`rubicon_scene_plan.md`](rubicon_scene_plan.md) §3.
> **ROS-Seite implementiert + statisch verifiziert**; das Live-End-to-End (R6/RS.8) = User.

```
Rubicon-Scene (App-Flow):
- [x] RS.1 presets/rubicon.yaml (Sim-Terrain-Enables, keine Launch-Params) + installiert
- [x] RS.2 rubicon_walk.launch.py (Rubicon-Sim + delayed gait + params_file:=rubicon.yaml)
- [x] RS.3 bringup_ondemand.launch.py: scene-Arg + sim-branch-Switch (ramp|rubicon)
- [x] RS.4 always_on.launch.py: scene-Arg -> _launcher_cfg waehlt launcher.sim.rubicon.yaml
- [x] RS.5 rubicon.sdf: gz-sim-sensors-system (Kamera)
- [x] RS.6 Static-Verify R1-R5 (parse/routing/config-select/xmllint/build/lint)
- [x] RS.7 Doku (Plan/Progress) + Self-Review  [README-Zeile + test_commands: Nachzug]
- [x] RS.8a [Live, User] Rubicon + Kamera + Aufstehen (nach JSB-Timeout-Fix) ✅ — Welt/Kamera/Standup live bestätigt (JSB manuell aktiviert; Fix implementiert für 1-Rutsch-Start)
- [ ] RS.8b [Live, User] Re-Test: always_on scene:=rubicon läuft OHNE manuelles JSB-Aktivieren durch + laufen
```

## Ein-Befehl-Nutzung (Ziel erreicht)
```bash
ros2 launch hexapod_bringup always_on.launch.py scene:=rubicon
```
→ App verbindet → „Start" (`bringup_start`) → Gazebo lädt **Rubicon** (+ Kamera) → gait kommt mit
**Terrain-Regelkreisen scharf** hoch (leveling + adaptiver Touchdown/Stand + Slip + Sensor-Plaus.)
→ Aufstehen + laufen. **Default (ohne `scene:=`) = flache Rampe, unverändert.**

## Kette (alle Glieder statisch verifiziert)
`always_on scene:=rubicon` → **`_launcher_cfg` → `launcher.sim.rubicon.yaml`** (offline-Test) →
`bringup_launcher` startet `bringup_ondemand mode:=sim scene:=rubicon` (getestete Launcher-Mechanik)
→ **sim-Zweig routet `scene==rubicon` → `rubicon_walk`** (bogus-scene wirft; ramp→ramp_walk) →
`rubicon.launch.py` (Rubicon-Welt + `gz-sim-sensors-system` für Kamera + heightmap-Spawn) +
verzögerter `gait.launch.py` **`params_file:=presets/rubicon.yaml`** (Toggles scharf; params_file
gewinnt über Inline-Args).

## Verifikation (grün)
- **R1** py_compile + `colcon build` (bringup/gait/gazebo/supervisor) grün.
- **R2** `_launcher_cfg`: rubicon→`launcher.sim.rubicon.yaml`, ramp/leer→`launcher.sim.yaml`,
  real→`launcher.real.yaml` (offline-Test); `launcher.sim.rubicon.yaml` = `['mode:=sim','scene:=rubicon']`.
- **R3** `rubicon.sdf` `xmllint`-valide + hat sensors/imu/contact-system.
- **R4** `rubicon.yaml` lädt, setzt genau die 7 Enables, **keine** `use_sim_time`/`auto_standup`/
  `robot_description` (die kämen sonst aus dem Preset statt Launch).
- **R5** Routing: `bringup_ondemand._setup` liefert rubicon→rubicon_walk / ramp→ramp_walk /
  bogus→RuntimeError; ament_flake8/pep257/copyright auf alle neuen/geänderten Files **No problems**.

**⚠️ Loopback-Launch-Test (`test_real_launch_loopback`) 1 Failure = Kontamination, KEINE
Regression:** während des Testlaufs lief die Live-Sim-Session des Users (ein `/controller_manager`
war schon da → der zweite aus `real.launch.py` kollidiert). Ich habe `real.launch.py` nicht
angefasst (keine Code-Kopplung); in Phase 4 lief der Test isoliert grün. **Bei freier Session
isoliert nachverifizieren.**

## Self-Review

| # | Punkt | Status |
|---|---|---|
| 1 | Default-Pfad (ohne scene) unverändert = flache Rampe | OK (`_launcher_cfg` ramp/leer→launcher.sim.yaml) |
| 2 | scene threadet: always_on→cfg→bringup_ondemand→rubicon_walk | OK (offline verifiziert, jedes Glied) |
| 3 | Kamera in Rubicon: `gz-sim-sensors-system` in `rubicon.sdf` | OK (Phase-4-Gotcha geschlossen) |
| 4 | Terrain-Toggles scharf ohne App-Toggeln: `params_file` gewinnt über Inline | OK (Merge-Reihenfolge geprüft) |
| 5 | Preset setzt NICHT use_sim_time/auto_standup/robot_description | OK (R4-Test) |
| 6 | Param-Dict-Override verworfen (Wildcard verliert gegen yaml-Key) → Config-File | OK (empirisch entdeckt + gefixt) |
| 7 | `real`-Pfad unberührt (scene nur sim) | OK (`_launcher_cfg` real→launcher.real.yaml) |
| 8 | ament-Lint + build grün | OK |
| 9 | Live: Rubicon lädt + Kamera rendert + Toggles=true + läuft | 🟢 RS.8 (User) |
| 10 | `slip_detection` freezt evtl. an Rubicon-Abhängen | 🟡 bewusst an (User „alle Sachen"), App-toggelbar |
| 11 | Heightmap-Spawn-Höhe (z=1.5) ggf. justieren | 🟡 Live (rubicon.launch.py-`spawn_z`) |

Keine 🔴. Die 🟡 sind Live-Justage/Verhalten; die 🟢 der Pflicht-Live-Test.

## Offene Punkte (Live)
1. `slip_detection_enable` an — falls es beim Laufen ständig freezt: im Preset false, per App zu.
2. `leveling_mode: auto` (Stand horizontal, Lauf folgt Hang).
3. Spawn-Höhe `z=1.5` (rubicon.launch.py-Default) — bei Einsinken/Fall justieren.
