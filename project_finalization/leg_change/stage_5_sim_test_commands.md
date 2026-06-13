# Stage 5 (Sim/Gazebo) — Test-/Live-Anleitung (Bein-Umbau `leg_changes`)

> **Plan:** [`stage_5_sim_plan.md`](stage_5_sim_plan.md) · **Thread-Plan:** [`plan.md`](plan.md)
> (Schritt 5.3 + 6.x) · **Cal/Modell-Anleitung (TEIL A):** [`test_commands.md`](test_commands.md).
>
> **Interaktiv** — du führst aus dem Doc aus, knappe Status-Meldungen zurück
> ([[feedback_test_commands_in_doc_not_chat]]). **Maschine: Desktop** (Gazebo-GUI).
> Branch: `leg_changes`.

## Ziel

Modell visuell ok → Reachability plausibel → stabiles Aufstehen auf **mittel**
→ stabiler Tripod-Lauf @ mittel (Teleop), tief/hoch mitgeprüft. Gazebo ist
**lenient** → das ist die *visuelle/physikalische* Bestätigung in Sim, **nicht**
der Strom-/HW-Beweis (der kommt in S6, [`test_commands.md`](test_commands.md) TEIL C).

## Aufgabenteilung

- **Du (Live-Sim):** B.1–B.6 (Gazebo/RViz/Teleop am Desktop), Beobachtungen melden.
- **Ich (danach):** finale Params synchron eintragen, Presets aktualisieren/löschen,
  Tests, Self-Review — B.8.

---

## B.0 — Build + sourcen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
git branch --show-current          # "leg_changes"
colcon build --symlink-install
source install/setup.bash
```

## B.1 — Modell-Visual-Check (Gazebo)  [S5-T1]
```bash
# Terminal 1 (läuft durch) — Gazebo + ros2_control, Bauch nahe Boden (spawn_z 0.05)
ros2 launch hexapod_bringup sim.launch.py
```
- [ ] Gazebo öffnet, Hexapod gespawnt; **kurze** Beine sichtbar (Femur 0.060 / Tibia 0.134).
- [ ] **Keine** URDF-/Mesh-/xacro-Fehler in der Konsole (rotes „Error"/„failed to load").
- [ ] Alle 6 `leg_*_controller` + `joint_state_broadcaster` werden „activated" geloggt.
- [ ] Roboter liegt in power_on_mid auf dem Bauch (noch kein Aufstehen — gait nicht gestartet).

## B.2 — Modell in RViz + tf2  [S5-T2]
```bash
# Terminal 2 — reines Modell (separater Prozess, unabhängig von Gazebo)
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_description display.launch.py
```
- [ ] RViz zeigt den vollständigen tf2-Baum (base_link → coxa/femur/tibia/foot je Bein), keine „No transform"-Fehler.
- [ ] Proportionen plausibel (kurze Tibia), keine fehlenden Frames/Links.
> Danach Terminal 2 wieder schließen (RViz/display brauchen wir für B.3 in eigener Config).

## B.3 — Reachability-Viz  [S5-T3]
```bash
# Terminal 2 — erreichbare Fuß-Hülle pro Bein (pure FK, keine HW/Gazebo nötig)
ros2 launch hexapod_gait reachability_viz.launch.py
```
- [ ] Pro Bein eine Hülle (blau = aktuelles rad-Limit). Konsistent mit neuem reach-Band.
- [ ] Die mittel-Pose (radial 0.145 @ body_height −0.10) liegt **innerhalb** der Hülle, mit
      sichtbarer Marge zum Rand (nicht am Limit klebend).
> Danach Terminal 2 schließen.

## B.4 — Aufstehen auf mittel (Zwei-Phasen + ggf. Reposition)  [S5-T4]
Gazebo (Terminal 1) läuft weiter. Jetzt gait_node dazu:
```bash
# Terminal 2 (läuft durch) — gait_node, SIM-Zeit zwingend
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```
> ⚠️ **Der gait_node steht beim Start AUTOMATISCH auf** (Auto-Standup-Rampe beim
> ersten `/joint_states`, Log: `Cartesian-Standup gestartet ... zur Stand-Pose`).
> Es ist **kein** `/hexapod_stand_up`-Aufruf nötig — der Service ist nur fürs
> Wieder-Aufstehen NACH einem Hinsetzen (aus dem SAT-Zustand). Aus STANDING
> antwortet er `stand_up only from SAT` (= korrekt, kein Fehler).

> **NEU ab S5-Re-Param:** mittel ist jetzt **radial 0.160 / body_height −0.080**,
> `standup_radial == radial` → **direktes Aufstehen, KEINE Zwischen-Reposition**
> mehr (kein „Füße erst breit, dann enger"). Vor dem Test neu bauen (`colcon build`).

- [ ] Bauch hebt sauber ab; Füße schürfen **nicht** sichtbar nach innen; kein Kippeln/Zucken.
- [ ] Endpose = mittel (radial 0.160, body_height −0.080), Roboter steht stabil, **etwas tiefer** als vorher.
- [ ] **Erwartet: KEIN Reposition-Hop** (steht direkt in der Lauf-Pose). Falls doch einer
      sichtbar ist → melden (dann ist standup_radial ≠ radial geblieben).

### B.4b — Reposition wegtunen (OPTIONAL — in S5 bereits berechnet+eingetragen)
> Erledigt: `standup_radial == radial == 0.160` ist eingetragen → Reposition ist
> bereits weg. Dieser Abschnitt nur, falls du den Aufsteh-Radius noch live variieren willst.
Hypothese: mit den kurzen Beinen reicht die **schmale** Walk-Pose (radial 0.145)
schon als Touchdown-Pose → `standup_radial` == `radial` → **keine Reposition** nötig.
Test (Roboter steht gerade, alle Params standing-only = nur in STANDING setzbar):
```bash
# Terminal 5 — rqt offen lassen (Node /gait_node)
ros2 run rqt_reconfigure rqt_reconfigure
#   → standup_radial_distance: 0.170 → 0.145   (= radial, Reposition = 0)
```
```bash
# Terminal 3 — Sit → Stand-Zyklus, prüft den neuen Aufsteh-Pfad
ros2 service call /hexapod_sit_down  std_srvs/srv/Trigger     # setzt sich (→ SAT)
ros2 service call /hexapod_stand_up  std_srvs/srv/Trigger     # steht mit neuem standup_radial auf
```
- [ ] Aufstehen @ standup_radial 0.145 **schürffrei**, kein Femur-Freeze / `IKError`,
      steht stabil, **ohne** Reposition.
- [ ] Falls der Femur am Touchdown kämpft/freezt: standup_radial schrittweise zurück
      (0.150 → 0.160 …) bis sauber. Der kleinste saubere Wert = nötige Reposition-Marge.
- [ ] Optional (deine Idee): zusätzlich `radial_distance` / `body_height` leicht
      Richtung „tiefer/weniger gestreckt" (z. B. body_height −0.10 → −0.095) — niedrigere
      Stand-Höhe macht den direkten Touchdown leichter. Gefundene Werte **melden**.

## B.5 — Tripod-Lauf @ mittel (Teleop)  [S5-T5]
```bash
# Terminal 4 — vorhandenes Teleop (PS4). USB: controller:=ps4_usb (Default), BT: ps4_bt
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```
Alternativ **ohne Controller** (deterministisch, ein Cycle vorwärts):
```bash
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.02, y: 0.0, z: 0.0}, angular: {z: 0.0}}'
```
- [ ] **forward** (linker Stick vor / x>0): stabiler Tripod, Beine heben sichtbar, kein Wegrutschen.
- [ ] **sidestep** (y≠0), **yaw** (angular.z≠0), **diagonal**: jeweils stabil, kein Einknicken.
- [ ] **Kein** IK-WARN-Spam in der gait-Konsole (`OutOfReach` / `IKError`).
- [ ] **Clamp-Spam:** mit `step_length_max` jetzt 0.050 (max-leg-speed 0.05 m/s) sollte der
      `cmd_vel clamped`-Spam bei normalem Stick-Tempo **weg** sein (nur bei Vollausschlag möglich).
- [ ] Stance-Höhen mit Teleop durchschalten (L2/R2 → `/hexapod_cycle_stance`): **tief**
      und **hoch** ebenfalls aufstehen+laufen? (→ D4: behalten wir 3 Höhen, oder reduzieren.)
> Stance auch deterministisch schaltbar: `ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool '{data: true}'` (höher) / `{data: false}` (tiefer).

### B.5b — Lauf-Speed / `cmd_vel clamped`-Tuning (OPTIONAL — in S5 bereits eingetragen)
> Erledigt: `step_length_max` Default 0.050 + D-Pad-Cycle 0.030–0.070 eingetragen
> (envelope-grün). Dieser Abschnitt nur, falls du live noch weiter hochgehen willst.
`cmd_vel clamped ... > max-leg-speed 0.030 m/s` = das Teleop will schneller, als die
Gangart liefert. `max-leg-speed = step_length_max / (cycle_time × 0.5)`. Hebel in rqt
(`/gait_node`), beim Vorwärtslaufen die gait-Konsole beobachten:
```bash
# step_length_max schrittweise hoch — größere Schritte = schneller
#   step_length_max: 0.03 → 0.04 → 0.05      (max-leg-speed 0.04 / 0.05 m/s @ cycle 2.0)
# optional zusätzlich Takt schneller:
#   cycle_time:      2.0 → 1.5               (kürzere Zyklen)
```
- [ ] Höchster `step_length_max`, bei dem **kein** `OutOfReach`/`IKError`-WARN auftritt
      und der Tripod **stabil** bleibt → das ist das echte Engine-Limit (Envelope-Tool ist
      am Rand zu optimistisch). **Diesen Wert melden.**
- [ ] Danach ziehe ich (B.8) die Teleop-Max-Geschwindigkeit auf denselben Wert nach,
      damit der Clamp-Spam verschwindet (Teleop will dann nicht mehr als die Gangart kann).

## B.6 — Live-Tuning (optional, falls B.4/B.5 nicht sauber)
```bash
# Terminal 5 — Live-Param-Verstellung am laufenden gait_node (nur in STANDING)
ros2 run rqt_reconfigure rqt_reconfigure          # Node /gait_node
```
Verstellbare Hebel (Plan §1): `standup_radial_distance`, `reposition_cycle_time`,
`step_height`, `step_length_max`, `radial_distance` (mittel). **Gefundene gute Werte
melden** — ich trage sie final in `gait_node.py` + `gait.launch.py` (+ teleop/stand, synchron) ein.

## B.7 — Sauberes Beenden
```bash
# In jedem Terminal Strg+C (Reihenfolge egal; Gazebo zuletzt)
```

---

## B.8 — Nach den Sim-Tests (ich erledige: Code/Preset/Doku)
- finale mittel-Params + standup/reposition + `_SIT_SAFE_MIN_BH` eintragen (synchron, 4 Quellen:
  `gait_node.py` · `gait.launch.py` · `stand.launch.py` · teleop `body_height_init`)
- Presets: sim_walk/defensive/demo/aggressive **aktualisieren**;
  current_state/alias_test/my_test_session/feet_closer **löschen** (feet_closer → sim_walk)
- `colcon test` gait/kinematics/teleop kein Regress; `pytest tools/test_walking_envelope_check.py` grün
- Self-Review-Tabelle (CLAUDE.md §4), plan.md-Bullets 5.3 + 6.x abhaken

## Schnell-Diagnose (Sim)

| Symptom | wahrscheinlich | Sofort |
|---|---|---|
| Gazebo spawnt nicht / „failed to load" | xacro-/Mesh-Pfad / `package://` | Konsole T1 lesen; `enable_foot_contact:=false` zum Eingrenzen |
| Controller bleibt „inactive"/spawner-Retry | gz_ros2_control-Plugin nicht geladen | T1: erst Spawn, dann JSB, dann leg-Controller — warten |
| Body springt beim gait-Start | Boot-Default ≠ mittel (3 Quellen) | gait.launch radial/body_height == mittel? |
| `OutOfReach`/`IKError`-WARN beim Lauf | Pose am reach-Rand / step zu groß | step_length_max/radial via rqt (B.6) zurücknehmen |
| gait reagiert nicht auf cmd_vel | `use_sim_time` fehlt → Timer still | gait.launch.py **`use_sim_time:=true`** ([[project_phase13_gait_launch_sim_time_default]]) |
