# Stufe 2 — Test-Befehle (interaktiv)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** — eigene Terminals + Befehle, setzt **nicht** voraus, dass aus
> einem vorherigen Test noch etwas läuft.

## Konventionen

- **Pro Test:** Terminals frisch öffnen; jeder Block beginnt mit dem Sourcing.
- **Zwischen zwei Tests:** alle Terminals mit **`Strg-C`** beenden.
- **Sourcing-Zeile** (steht in jedem Block):
  ```bash
  source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
  ```
- Stufe 2 levelt **nur im STANDING**. Ablauf: Sim mit Schräg-Welt starten →
  gait_node steht auf (Auto-Standup, bauch-gepitcht gespawnt) → erst dann wirkt
  das Leveling. **Milde Hänge** (5/8/10°) — der Anfangs-Transient bleibt unter
  `tip_angle_warn` (15°).
- `leveling_enable` ist per Default **false** (Opt-in) → in den Tests via
  `ros2 param set` eingeschaltet.

---

## Einmalig vorab: bauen

**Terminal (einmalig):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## Was du beobachtest — `/imu/monitor` lesen

`/imu/monitor` ist ein `geometry_msgs/Vector3`:

| Feld | Bedeutung | Einheit |
|---|---|---|
| `x` | **roll** | Radiant (× 57.3 = Grad) |
| `y` | **pitch** | Radiant (× 57.3 = Grad) |
| `z` | yaw | Radiant (driftet, ignorieren) |

→ Für „Körper-Neigung in Grad" interessiert **`y` (pitch)** auf der um Y geneigten
Box. `y = 0.14` ≈ 8°, `y ≈ 0` ≈ horizontal.

**Leichter ablesbar (Grad-Log):** im imu_monitor-Terminal stehen die Werte schon in
Grad:
```
roll=  -0.1  pitch=   8.0  yaw=   0.5  [deg]
```

**Ground-Truth (echte Körperlage aus Gazebo, unabhängig von der IMU):**
```bash
gz topic -et /world/empty/dynamic_pose/info | grep -A12 '"hexapod"'
```
→ zeigt die Orientierung (Quaternion) des Modells. Damit prüfst du, ob der Körper
*wirklich* geneigt ist, falls die IMU etwas anderes sagt.

---

## Befund: gz-IMU ist spawn-referenziert → FLACH spawnen (erledigt)

Verifiziert (2026-06): der gz-IMU-Sensor referenziert seine Orientierung auf die
**Spawn-Pose**. Ein um den Hangwinkel gepitchter Spawn legt die IMU-Null auf den
Hang → die reale Neigung wird maskiert (pitch liest 0 statt 8°). **Fix:** `slope.launch.py`
spawnt jetzt **flach** (Default `spawn_pitch_deg:=0`) → die IMU liest den echten
Hangwinkel (flach gespawnt: pitch = 0.1396 rad = 8.0°, Ground-Truth bestätigt).
Entspricht auch dem realen Szenario (Roboter startet eben, läuft in den Hang =
Stufe 3). Die Tests unten nutzen den flachen Default.

---

## T2.U — Unit- + Tool-Tests (ohne Sim)

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# Paket-Tests (BalanceController, rotate_xy, Engine-Leveling, Node-Wiring)
colcon test --packages-select hexapod_kinematics hexapod_gait \
  --pytest-args -k "balance or rotate_xy or leveling" \
  --event-handlers console_direct+
colcon test-result --verbose
# Offline-Envelope/CoG-Tool (bestätigt max_level_angle=10°)
python3 tools/leveling_envelope_check.py --theta-list 5,8,10,12,15
pytest tools/test_leveling_envelope_check.py -q
```

**Erwartung:** Paket-Tests grün; Tool meldet „max_level_angle=10° bestätigt"
(10° in allen Stance×Modi in-limit + CoG-stabil; ab 12° combined LIM);
Tool-Tests grün.

---

## T2.1 — Schräg-Welt lädt + Roboter steht + IMU zeigt den Hangwinkel

**Terminal 1 (Sim + Schräg-Welt 8°):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup slope.launch.py slope_deg:=8.0
```

**Terminal 2 (gait_node, Leveling AUS):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
> (Roboter steht über den Auto-Standup auf der geneigten Box auf.)

**Terminal 3 (IMU-Lage beobachten):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```

**Erwartung:** Roboter spawnt flach, steht auf und **neigt sich dabei auf die
Hangfläche**; `/imu/monitor` **y (pitch) ≈ 0.14 rad = 8°** (Leveling aus). Gazebo
zeigt den geneigten Körper. **Kein** Safety-Freeze.

---

## T2.2 — Leveling AN: Körper levelt ~θ → ~0°, kein Freeze, Scrub klein

> Wie T2.1 starten (Terminals 1–3), dann in einem 4. Terminal Leveling
> einschalten **nachdem** der Roboter steht.

**Terminal 4 (Leveling einschalten):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node leveling_enable true
```

**Erwartung (in Terminal 3, `/imu/monitor`):** pitch fährt binnen ~1–2 s von
~8° glatt auf **~0°** und bleibt dort. Gazebo: Körper richtet sich horizontal,
Füße bleiben am Boden (kleiner Scrub ok). **Kein** `IKError`/Safety-Freeze im
gait_node-Log. Tip-Erkennung feuert **nicht** (Startup-Grace + milder Hang).

**Gegencheck steiler (optional):** `slope_deg:=15.0` neu starten → Leveling
clampt bei 10°, Rest-Neigung ~5° bleibt, **trotzdem kein Freeze** (IKError-
Fallback / Clamp).

---

## T2.3 — Strikter Ground-Truth (T0.3-Nachhol): IMU vs. Box-Winkel

> Leveling **AUS** (wie T2.1). Vergleicht die IMU-Schätzung gegen den bekannten
> Box-Winkel (= `slope_deg`).

Für mehrere Winkel je einmal T2.1 mit `slope_deg:=5.0`, `8.0`, `10.0` starten
und in Terminal 3 den stationären pitch ablesen.

**Erwartung:** `/imu/monitor` pitch ≈ `slope_deg` ± **1–2°** für alle drei
Winkel (IMU schwerkraft-referenziert korrekt gegen den realen Rampenwinkel).

---

## T2.4 — Live-Tuning (Leveling- + Tip-Params)

> Sim wie T2.1 (Leveling AN, T2.2). Prüft, dass die Params zur Laufzeit greifen.

**Terminal 4:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# Leveling weicher/härter stellen
ros2 param set /gait_node leveling_slew_max_dps 4.0     # langsamer leveln
ros2 param set /gait_node leveling_kp 0.6
ros2 param set /gait_node leveling_max_angle_deg 12.0   # Clamp anheben
# Tip-Schwelle live (Stufe-1-Params jetzt live)
ros2 param set /gait_node tip_angle_warn_deg 18.0
ros2 param get /gait_node leveling_max_angle_deg
```

**Erwartung:** jede Zeile `Set parameter successful`; das Leveling-Tempo ändert
sich sichtbar (slew 4.0 → deutlich langsamer); `ros2 param get` zeigt 12.0.
Kein Crash/Freeze.

---

## Hinweise / bekannte Vereinfachungen

- **Auto-Standup statt echtem pre-stood-Spawn:** der Roboter spawnt bauch-um-θ-
  gepitcht und steht über den bestehenden Cartesian-Standup auf. Bei milden
  Hängen tragfähig; falls der Standup bei einem Winkel hakt → `slope_deg`
  senken. Echter pre-stood-Spawn (Initial-Joint-Pose) ist Stufe-3-Refinement.
- **Ground-Truth-Pose** alternativ direkt aus Gazebo:
  `gz topic -et /world/empty/dynamic_pose/info` (Modell „hexapod"-Orientierung).
