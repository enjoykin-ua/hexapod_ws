# C1+ — USB-Teleop erweitert — Test-Anleitung (SIM + HW)

> Offline (Unit/Lint) grün. SIM/HW brauchen einen **PS4-Controller per USB**.
> Plan: [`C_teleop.md`](C_teleop.md). Mapping-Tabelle: dort §1 + `hexapod_teleop/README.md`.

## 0. Offline (bereits grün)

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_teleop
colcon test-result --test-result-base build/hexapod_gait    # 140 tests, 0 fail
colcon test-result --test-result-base build/hexapod_teleop   # 15 tests, 0 fail
```

## 1. SIM — Aufbau

**Terminal A — Sim:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
**Terminal B — Gait (Preset, warten bis `STATE_STANDING`):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
```
**Terminal C — Teleop (PS4 USB; Controller eingesteckt):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
# Falls Latenz: autorepeat beim joy_node erhöhen (siehe README-Stolperfallen).
```
**Terminal D (optional) — Achsen/Buttons verifizieren:**
```bash
ros2 topic echo /joy     # Sticks/Buttons live bewegen → Indizes/Vorzeichen prüfen
```

## 2. SIM — Funktions-Checks (C1+.8)

| Test | Eingabe | Erwartet |
|---|---|---|
| Fahren vorwärts | **R1 halten** + linker Stick **hoch** | läuft vorwärts (dosiert mit Stick-Weg) |
| Seitwärts | R1 + linker Stick **links/rechts** | seitwärts (omnidirektional) |
| Drehen | R1 + rechter Stick **links/rechts** | dreht auf der Stelle |
| Diagonal | R1 + linker Stick schräg | Bogen/Diagonale (Engine clampt) |
| Langsam | R1 + **L1** + Stick | halbes Tempo |
| Dead-Man | Stick **ohne** R1 | **keine** Bewegung |
| Höhe senken/heben | **L2 / R2** (je Druck) | ±1 cm, stoppt an den Grenzen |
| **Hinsetzen/Aufstehen** | **△ Triangle** | steht→setzt sich; sitzt→steht auf (Toggle) |
| **Shutdown** | **○ Circle ~1 s halten** | setzt sich + Relay-Aus (Sim: Log „nicht verfügbar") |
| **Show-Pose** | **✕ Cross ~1 s halten** | Log „noch nicht implementiert (B4)" — sonst nichts |

> **Vorzeichen prüfen:** Fährt er rückwärts statt vor → `sign_ly` in `ps4_usb.yaml` auf `-1.0`.
> Dreht/seitwärts verkehrt → `sign_rx` bzw. `sign_lx` flippen. Danach Teleop neu starten.

## 3. HW aufgebockt → Boden (C1+.9) — `use_sim_time:=false`

> ⚠️ **CLAUDE.md §9:** Roboter **aufgebockt** (Beine frei), **PSU-Kill-Switch griffbereit**,
> langsam/kurz. PS4-Controller per USB am Rechner. Relay wird beim Plugin-Activate automatisch
> gesetzt — kein manueller `/hexapod_relay_set` nötig.

**Terminal 1 — Hardware (Servo2040 an `/dev/ttyACM0`):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```

**Terminal 2 — RViz HW-Spiegel (optional, zum Mitsehen):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```

**Terminal 3 — Gait (`use_sim_time:=false`! + Preset), warten bis `STATE_STANDING`:**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml
```
→ Roboter steht automatisch auf (Cartesian-Standup → Reposition) → im Log erscheint
`STATE_STANDING`. **Erst weiter, wenn er steht.**

**Terminal 4 — Teleop (PS4 USB):**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py
```

**Terminal 5 (optional) — Achsen/Buttons verifizieren:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joy     # Sticks/Buttons live bewegen → Indizes/Vorzeichen prüfen
```

### 3.1 Checks aufgebockt (in dieser Reihenfolge)

| Test | Eingabe | Erwartet |
|---|---|---|
| Vorzeichen prüfen | `/joy` mitlesen, Sticks bewegen | linker Stick hoch → axis 1 ändert sich; etc. |
| Fahren | **R1 halten** + linker Stick hoch/seitwärts | Beine laufen vorwärts/seitwärts (in der Luft) |
| Drehen | R1 + rechter Stick | Dreh-Gangbild |
| Langsam | R1 + **L1** + Stick | halbes Tempo |
| Höhe | **L2 / R2** | Körper senkt/hebt um 1 cm, stoppt an Grenzen |
| **Hinsetzen** | **△ Triangle** (steht gerade) | setzt sich kontrolliert → Spawn-Pose (Beine hoch) |
| **Aufstehen** | **△ Triangle** (sitzt gerade) | steht wieder auf → STANDING |

> **Vorzeichen falsch?** rückwärts statt vor → `sign_ly: -1.0`; dreht/seitwärts verkehrt →
> `sign_rx` / `sign_lx` flippen (in installiertem `ps4_usb.yaml` oder Source + rebuild),
> dann Teleop (Terminal 4) neu starten.

### 3.2 Erst danach: Boden
Aufgebockt sauber → Roboter auf den Boden stellen, gleiche Checks vorsichtig/langsam, dann
**○ Circle ~1 s halten** = Shutdown (setzt sich + echtes Relay-Aus → Servos schlaff, kein Ruck).

## 4. Fertig-Kriterium
- **C1+.8 SIM:** alle Checks aus Abschnitt 2 wie erwartet; Vorzeichen ggf. in YAML justiert.
- **C1+.9 HW:** aufgebockt (3.1) sauber → Boden (3.2) sicher (Fahren, Toggle, Shutdown).
