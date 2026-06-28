# S4-1 — Test-Befehle (Fußkontakt-Verifikation)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** verifizieren, dass das
> Fußkontakt-Signal **rechtzeitig + plausibel** feuert — flach **und** am Hang, über
> `cycle_time`/`step_height` — **bevor** der adaptive Touchdown (S4-2) darauf baut. **Kein
> Verhaltens-Change** in dieser Stufe.

## Konventionen

- **Sourcing** in jedem Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set`/`node list` einmal `ros2 daemon stop` (sonst „Node not
  found" trotz laufendem Node — bekanntes Jazzy-Problem).
- **Pipeline läuft per Default** (`enable_foot_contact:=true`, auch in `ramp_walk.launch.py`).

## Einmalig vorab: bauen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## Was du beobachtest

### `/foot_contacts` (Live-Muster) — `std_msgs/Float64MultiArray`
```bash
ros2 topic echo /foot_contacts
```
→ `data: [c1, c2, c3, c4, c5, c6]` (1.0 = Kontakt, 0.0 = kein). Beim Tripod-Laufen sollte sich
das Muster im Takt ändern (eine Tripod-Gruppe trägt, die andere schwingt).

### Diagnose-Log (im gait_node-Terminal, throttled 1 Hz)
```
foot_contact [101010] | L1 td7 lat0.6/1 miss0 apex0 gap0 | L2 td0 lat-/0 miss0 apex0 gap0 | ...
```
| Feld | Bedeutung | Soll |
|---|---|---|
| `[101010]` | aktuelle 6 Kontakte (1=Kontakt) | wechselt im Takt |
| `td` | gezählte Touchdowns (steigende Flanken in der Stance) | > 0 beim Laufen |
| `lat a/m` | Touchdown-**Latenz** Ø/max in **Ticks** (1 Tick = 20 ms) | **≤ 2** |
| `miss` | Touchdowns ganz **verpasst** (kein Kontakt in der Stance) | **0** |
| `apex` | Kontakt im **Schwung-Apex** (Fuß sollte oben sein) | **0** |
| `gap` | **kein** Kontakt in der **Stance-Mitte** (belastetes Bein) | klein / 0 |

> **Frisches Mess-Fenster pro Konfig:** `foot_contact_debug_enable` **false→true** setzt die
> Diagnose-Zähler zurück (s. Matrix unten).

---

## T1 — Grund-Check flach (8°-frei) + am Hang

**▶ Terminal 1 — flach (slope_deg:=0) starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0 gait_pattern:=tripod leveling_enable:=false
```
⏳ warten bis aufgestanden (~12–15 s). (`leveling_enable:=false` → Stage 4 isoliert von der IMU.)

**▶ Terminal 2 — beobachten + fahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 topic echo /foot_contacts            # Muster wechselt im Takt?
# in einem dritten Terminal fahren:
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
~20–30 s laufen lassen, dann im **gait_node-Terminal (Terminal 1)** das Diagnose-Log ablesen.

**Erwartung:** `td` steigt pro Bein, `lat ≤ 2`, `miss 0`, `apex 0`, `gap` klein. `/foot_contacts`
wechselt sauber im Takt.

**Hang:** dasselbe mit `slope_deg:=8.0` (Terminal 1 neu). Erwartung identisch — der Kontakt feuert
auch auf der geneigten Fläche zuverlässig.

---

## T2 — Verifikations-Matrix (flach + Hang × cycle × step)

> **8 Konfigs.** `slope_deg` braucht Neustart (andere Welt); `cycle_time`/`step_height` werden
> **live im STANDING** gesetzt (kein Neustart). Vor jeder Messung die Diagnose **zurücksetzen**.

**Pro Welt** (einmal `slope_deg:=0.0`, einmal `slope_deg:=8.0`) — Terminal 1:
```bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0 gait_pattern:=tripod leveling_enable:=false
```

**Terminal 2 — pro Konfig (4 je Welt):** im STANDING (kein cmd_vel) setzen, dann fahren:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop

# --- Konfig A: cycle 2.0 / step 0.04 ---
ros2 param set /gait_node cycle_time 2.0
ros2 param set /gait_node step_height 0.04
ros2 param set /gait_node foot_contact_debug_enable false
ros2 param set /gait_node foot_contact_debug_enable true     # ← Diagnose zurückgesetzt
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # ~25 s, dann Strg-C
#   → Diagnose-Log (Terminal 1) ablesen + notieren

# --- Konfig B: cycle 1.0 / step 0.04 (schneller — die dokumentierte Schwachstelle) ---
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'   # stoppen → STANDING
ros2 param set /gait_node cycle_time 1.0
ros2 param set /gait_node foot_contact_debug_enable false
ros2 param set /gait_node foot_contact_debug_enable true
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # ~25 s

# --- Konfig C: cycle 2.0 / step 0.06 ---
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
ros2 param set /gait_node cycle_time 2.0
ros2 param set /gait_node step_height 0.06
ros2 param set /gait_node foot_contact_debug_enable false
ros2 param set /gait_node foot_contact_debug_enable true
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # ~25 s

# --- Konfig D: cycle 1.0 / step 0.06 ---
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
ros2 param set /gait_node cycle_time 1.0
ros2 param set /gait_node foot_contact_debug_enable false
ros2 param set /gait_node foot_contact_debug_enable true
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # ~25 s
```
Dann Terminal 1 neu mit `slope_deg:=8.0` und die 4 Konfigs wiederholen.

**Pro Konfig notieren** (aus dem Diagnose-Log, schlechtestes Bein): `lat Ø/max`, `miss`, `apex`,
`gap`, Quote-Eindruck.

**Akzeptanz (Done-Idee S4-1):**
- **`lat ≤ 2` Ticks** (≤ 40 ms) in **allen 8** Konfigs, **`apex = 0`** systematisch.
- `miss = 0`; `gap` klein (einzelne Aussetzer ok, keine Dauer-Lücken).
- Bricht das bei **cycle 1.0** (schnell) → genau die dokumentierte Schwachstelle → **Hebel 2/3**
  in S4-2 (Umbrella §3): `contact_timeout` / Touchdown-Penetrations-Offset. (Langsamer fahren ist
  **ausgeschlossen**.)

---

## Hinweise

- **Counters sind kumulativ** seit Node-Start → `foot_contact_debug_enable` false→true vor jeder
  Messung gibt ein frisches Fenster (ohne Neustart).
- **Stage 4 isoliert:** `leveling_enable:=false` (IMU aus) — erst Kontakt allein verifizieren,
  Kombination mit TF kommt später.
- Findet die Verifikation, dass selbst Hebel 2/3 nicht reichen → Hebel 4 (Fuß-Geometrie) ist ein
  separater, ausdrücklich freizugebender Punkt (Geometrie-TABU).
