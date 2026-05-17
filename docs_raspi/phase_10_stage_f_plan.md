# Phase 10 — Stufe F — Plan

> **Status:** Plan, in Vorbereitung der HW-Arbeit.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe F — IK-Roundtrip leg_6 voll (3 Servos) + Voll-Pipeline-Test.
>
> **Vorbedingung:** Stufen C/D/E komplett (alle 3 leg_6-Joints
> `direction` final committed: Coxa=-1, Femur=-1, Tibia=+1). Hexapod
> aufgebockt, Bench-PSU 7.0 V, **OUTPUT AUS**, alle leg_6-Servos
> elektrisch abgeklemmt nach Stage-E-Shutdown.

---

## Ziel

**Voll-Integration aller 3 leg_6-Servos unter IK + gait_node-Kontrolle.**
Konkret in 4 Sub-Steps:

1. **F.1 Bein-Geometrie-Verifikation:** Lineal/Schieblehre an leg_6,
   Vergleich mit URDF-Werten (Coxa 43.6 mm, Femur 79.94 mm, Tibia 178.7 mm).
   Bei > 5 mm Abweichung: URDF anpassen vor F.2.
2. **F.2 Direkter IK-Aufruf:** ein kleines Python-Skript ruft
   `hexapod_kinematics.leg_ik()` auf, generiert 2-Punkt-JointTrajectory
   (Fuß 3 cm vertikal heben), sendet an `leg_6_controller`.
   **Diagnose-Probe für IK-Korrektheit isoliert.**
3. **F.3 gait_node mit /cmd_vel:** voller Walking-Software-Pfad
   (gait_node → JTC → Plugin → Firmware → Servos). leg_6 schwingt im
   Tripod-Pattern, andere 5 Beine bekommen Pulse-Streams an leere Pins.
4. **F.4 Strom-Profil-Auswertung:** CSVs aus F.2 + F.3 in Python/Pandas
   laden, max rad/s pro Joint ableiten, Strom-Peaks dokumentieren.
   **Stage-G-Vorbereitung** für Vel/Accel-Limits in `controllers.real.yaml`.
   CSV-Ablage: `~/hexapod_ws/data/phase_10/` (committed ins Repo gem.
   Mutter-Plan-Phasenabschluss-Checkliste).

Nach Stage F sind die folgenden **Phase-12-Software-Pipeline-Risiken**
weitestgehend geschlossen:
- gait_node ↔ JTC ↔ Plugin ↔ Firmware ↔ Servo-Pfad funktional verifiziert
- IK liefert geometrisch sinnvolle Joint-Winkel für leg_6
- 3-Servo-Koordination unter Trajectory-Streaming OK
- Strom-Profil unter Walking-Last bekannt

**Was Stage F NICHT macht:**

- Keine 6-Bein-Koordination physisch (nur leg_6 montiert + 5 leere Pins)
- Kein Vel/Accel-Limit-Eintrag in `controllers.real.yaml` (Stage G)
- Kein Boden-Walking (Phase 12, Stufe F)
- Keine 18-Servo-Kalibrierung (Phase 12, Stufe B = neue Auto-Cal)

---

## Sicherheits-Schwerpunkt: Femur unter Walking-Last

Femur-Initial-Pulse-Schlag (Stage-D-Problem) gilt weiterhin → **User-Hand
am Bein vor jedem Launch** (Bein horizontal vorhalten). Plus neu in
Stage F:

- **Walking-Trajectories sind dynamischer** als statische Goals in
  Stages C–E. Femur muss in F.3 das Bein während des Tripod-Cycles
  hochheben + absenken (Foot-Hub ~3 cm) — wiederholte Lastspitzen
  möglich.
- **3-Servo-Strom-Spitzen:** alle 3 Servos in Bewegung → kurzzeitige
  Strom-Summe > 1-Servo-Stalls allein. PSU 7.0 V / **CC 8 A**
  (Mutter-Plan §B Tabelle).

Kill-Switch (PSU OUTPUT) muss in F.2 + F.3 **griffbereit** bleiben.

---

## Strategie / Architektur-Erinnerungen

| Punkt | Wert | Quelle |
|---|---|---|
| Bench-PSU Spannung | 7.0 V | Mutter-Plan §B |
| Bench-PSU CC-Limit | **8 A** (3-Servo-Bein) | Mutter-Plan §B |
| Verkabelungs-Sequenz | PSU-AUS → alle 3 Stecker rein → PSU-AN | Mutter-Plan §D |
| Initial-Pulse-Mitigation | User-Hand am Bein horizontal vor Launch (Stage-D-Pattern) | Mutter-Plan §C |
| direction-Werte (alle final) | Coxa=-1, Femur=-1, Tibia=+1 | committed Stages C/D/E |
| Strom-Logging | `~/hexapod_servo_driver/tools/log_state.py` (20 Hz via USB-CDC) | Mutter-Plan §G |
| F.2 IK-Skript-Speicherort | **Standalone `tools/phase_10_f2_ik_probe.py`** im hexapod_ws | siehe F-Q2 unten |
| F.3 gait_node-Launch | **`ros2 launch hexapod_gait gait.launch.py body_height:=-0.047 use_sim_time:=false`** (HW-Args ZWINGEND, siehe HW-Launch-Args-Block unten) | Plan-Korrektur ggü. Mutter-Plan |
| RViz | separat starten (`rviz2`) | Stage-C-Plan-Korrektur |
| Bein-Geometrie-Check | F.1 vorab, Lineal/Schieblehre, > 5 mm = URDF anpassen | Mutter-Plan §H |

---

## Plan-Korrektur ggü. Mutter-Plan-Doku §Stage-F-F.3

Mutter-Plan schreibt:
> ```bash
> ros2 launch hexapod_bringup real.launch.py rviz:=true gait:=true
> ```

**Tatsächliche Situation:** [`real.launch.py`](../src/hexapod_bringup/launch/real.launch.py)
hat **keinen** `gait:=true`-Arg (analog zu `rviz:=true` aus Stage C
Plan-Korrektur). Phase 9 hat das bewusst separiert.

**Konsequenz für F.3:** User startet **drei parallele Launches** in
drei Terminals:
1. `ros2 launch hexapod_bringup real.launch.py loopback_mode:=false`
   (Plugin + Controller-Manager + JSB + 6 leg-Spawner)
2. `rviz2` (Visualisierung)
3. `ros2 launch hexapod_gait gait.launch.py body_height:=-0.047 use_sim_time:=false`
   (gait_node + State-Machine — **HW-Args ZWINGEND**, siehe unten)

Plus `ros2 topic pub /cmd_vel ...` in einem 4. Terminal als Input.
Klingt nach viel, ist aber bewusst separiert für Diagnose-Trennung
(jeder Stack-Layer ein eigenes Terminal-Window).

**Verworfen:** real.launch.py um `gait:=true` erweitern — gleiche
Begründung wie für `rviz:=true` in Stage C (Phase-12-Kandidat,
Phase-10-Aufwand nicht amortisierbar).

---

## HW-Launch-Args für `gait.launch.py` (Self-Review-Punkt #5 + #9)

`gait.launch.py` ist auf **Sim** vorkonfiguriert. Für HW-Betrieb in
Stage F.3 zwei Defaults überschreiben:

| Arg | Sim-Default | **HW-Wert** | Begründung |
|---|---|---|---|
| `body_height` | -0.052 | **-0.047** | Sim-Default kompensiert JTC-Tracking-Lag in Gazebo (Stand-Pose 5 mm tiefer = leichte Boden-Penetration für stabilere Reibung). HW hat keinen Tracking-Lag → Phase-6-Übergabe-Notiz aus PHASE.md: HW-Wert -0.047. |
| `use_sim_time` | true | **false** | Sim nutzt `/clock` aus Gazebo. HW nutzt Wallclock (analog `controllers.real.yaml use_sim_time: false` aus Phase 9). Falsch gesetzt → gait_node-Timer feuert nicht, gait hängt. |

**Korrekter F.3-Launch-Command:**

```bash
ros2 launch hexapod_gait gait.launch.py \
  body_height:=-0.047 \
  use_sim_time:=false
```

**Andere Defaults bleiben:**
- `tick_rate=50.0 Hz` — matched `controllers.real.yaml update_rate=50`
- `step_height=0.03 m` — Foot-Hub 3 cm (passt zur F.2-IK-Probe)
- `cycle_time=2.0 s` — gemütliche Geschwindigkeit für ersten Walk
- `radial_distance=0.27 m` — Stand-Pose-Geometrie (Phase-5-tested)

---

## User-Antworten (User-Freigabe 2026-05-17)

| Frage | Antwort | Konsequenz |
|---|---|---|
| **F-Q1** F.1 Lineal-Genauigkeit | **A** — Lineal/Schieblehre, ±5 mm | Mutter-Plan-Threshold |
| **F-Q2/F-Q3** F.2 IK-Skript | **A** — Standalone `tools/phase_10_f2_ik_probe.py` + Default-Ziele `(0.15, 0.10, -0.10)` → `(0.15, 0.10, -0.07)` | Skript hat IKError-Fallback; User kann Ziele editieren falls IK nicht trifft |
| **F-Q4** F.3 cmd_vel | **A** — `linear.x = 0.02 m/s` für ~10 s | Mutter-Plan-Default, langsamer Walk |
| **F-Q5** F.4 Strom-Auswertung | **A** — Pandas-Plot, User-Auge auf Peaks | Werte in Stage-G-Vorbereitungs-Tabelle |
| **F-Q6** Pause zwischen F.2 und F.3? | **B** — **Commit zwischen F.2 und F.3** (User-Anweisung „nichts kaputt machen") | Stage F wird in **zwei Halb-Stages** geteilt — F-Phase-1 (F.0–F.2 + Commit), F-Phase-2 (F.3 + F.4 + Commit). Doppelter Bringup-Aufwand mit Hand-Mitigation akzeptiert für mehr Sicherheits-Anker. |

## Workflow: Stage F in zwei Halb-Stages (User-Entscheid F-Q6)

**F-Phase-1 (heute):**
- F.0 Bench-Setup
- F.1 Lineal-Check (stromlos)
- F.2 Plugin-Bringup + IK-Probe-Test
- Shutdown + Abklemm
- Build + Test + Self-Review + Progress
- **User-Commit** vor F-Phase-2

**F-Phase-2 (separat):**
- Bench-Setup wieder (alle 3 Servos anstecken)
- F.3 gait_node + cmd_vel + Strom-CSV
- F.4 CSV-Auswertung in Pandas
- Shutdown + Abklemm
- Build + Test + Self-Review
- **User-Commit** vor Stage G

---

## Logik-Skizze

### F.0 — Bench-Setup-Check (~5 min)

1. **Bench-PSU OUTPUT AUS** (von Stage-E-Shutdown)
2. **CC-Limit umstellen 4 A → 8 A** (3-Servo-Bein)
3. Setpoint bleibt 7.0 V
4. **Alle 3 leg_6-Servos anstecken:** Coxa Pin 15, Femur Pin 16, Tibia Pin 17
   — Polaritäts-Sichtprüfung bei jedem
5. **leg_5:** ruhige Default-Pose
6. **User-Hand bereit:** Bein in **Phase-5-Stand-Position** vorhalten
   (Fuß ungefähr 5–10 cm unter Body in Default-Pose, alle Joints
   etwas geknickt). Plus weiter: PSU-Aus-Knopf griffbereit.
7. **PSU OUTPUT AN** → Strom < 400 mA idle erwartet (3 Servos)
   - > 1 A = Verdacht auf Kurzschluss, sofort AUS

### F.1 — Bein-Geometrie-Verifikation (~15 min, stromlos)

> **Stromlos:** für F.1 wird **kein Plugin gestartet**. Reine
> mechanische Messung.

Pro Segment:

| Segment | URDF-Wert | Mess-Punkt |
|---|---|---|
| Coxa | 43.6 mm | Coxa-Joint-Achse → Femur-Joint-Achse |
| Femur | 79.94 mm | Femur-Joint-Achse → Tibia-Joint-Achse |
| Tibia | 178.7 mm | Tibia-Joint-Achse → Fuß-Spitze |

Joint-Achsen = mittlere Schrauben/Servo-Wellen.

**Mess-Methodik:**
- Lineal oder Schieblehre an leg_6 anlegen
- Bein in geometrische Default-Pose halten (Coxa radial außen, Femur
  horizontal, Tibia gestreckt) — passt zur visuellen Joint-Mitte
- Pro Segment Wert ablesen, mit URDF vergleichen
- **Bei Abweichung > 5 mm:** STOP, URDF
  (`hexapod_physical_properties.xacro`) anpassen, `colcon build`,
  dann F.2

**Erwartung:** Abweichung wahrscheinlich < 5 mm (URDF basiert auf
verifizierter Geometrie aus Phase 2, [`docs/00_conventions.md`](../docs/00_conventions.md) §11.2).

### F.2 — Direkter IK-Aufruf (Diagnose-Probe) (~30 min)

**Setup:**
- Alle 3 leg_6-Servos angesteckt, PSU AN (8 A)
- **User-Hand am Bein** in Phase-5-Stand-Position vor Launch
- 3 Terminals:
  - Terminal 1: `real.launch.py loopback_mode:=false`
  - Terminal 2: `rviz2`
  - Terminal 3: Strom-CSV-Logger
  - Terminal 4: IK-Probe-Skript

**Logger (Terminal 3):**
```bash
python3 ~/hexapod_servo_driver/tools/log_state.py \
  --out ~/hexapod_ws/data/phase_10/leg6_F2_$(date +%Y%m%dT%H%M).csv
```

**IK-Probe-Skript (siehe F-Q2 → standalone in `tools/phase_10_f2_ik_probe.py`):**

```python
#!/usr/bin/env python3
"""Phase 10 Stage F.2 — direct IK probe for leg_6.

Calls hexapod_kinematics.leg_ik() directly, generates a 2-point
JointTrajectory (foot lifts vertically by 3 cm), sends it to
leg_6_controller via the FollowJointTrajectory action.

Usage:
  source ~/hexapod_ws/install/setup.bash
  python3 ~/hexapod_ws/tools/phase_10_f2_ik_probe.py
"""

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

from hexapod_kinematics.config import HexapodConfig
from hexapod_kinematics.leg_ik import leg_ik
from hexapod_kinematics.geometry import base_to_leg_frame

# Foot target points in base_link frame (m).
GOAL_A_BASE = (0.15, 0.10, -0.10)   # start
GOAL_B_BASE = (0.15, 0.10, -0.07)   # +3 cm up

def main():
    rclpy.init()
    node = Node("phase_10_f2_ik_probe")

    cfg = HexapodConfig.default()
    leg6 = cfg.leg("leg_6")

    # Transform from base_link frame into leg-local frame for IK.
    a_leg = base_to_leg_frame(GOAL_A_BASE, leg6)
    b_leg = base_to_leg_frame(GOAL_B_BASE, leg6)

    angles_a = leg_ik(*a_leg, leg6)
    angles_b = leg_ik(*b_leg, leg6)
    node.get_logger().info(f"IK A: {angles_a}, IK B: {angles_b}")

    client = ActionClient(node, FollowJointTrajectory,
                          "/leg_6_controller/follow_joint_trajectory")
    client.wait_for_server(timeout_sec=5.0)

    traj = JointTrajectory()
    traj.joint_names = ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"]

    p_a = JointTrajectoryPoint()
    p_a.positions = list(angles_a)
    p_a.time_from_start = Duration(sec=2, nanosec=0)

    p_b = JointTrajectoryPoint()
    p_b.positions = list(angles_b)
    p_b.time_from_start = Duration(sec=4, nanosec=0)

    traj.points = [p_a, p_b]

    goal = FollowJointTrajectory.Goal()
    goal.trajectory = traj

    future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future)
    result = future.result()
    node.get_logger().info(f"Goal result: {result.status}")

    rclpy.shutdown()

if __name__ == "__main__":
    main()
```

**Ablauf User-Smoke F.2:**

1. PSU AN, User-Hand am Bein, Plugin-Launch starten (Terminal 1)
2. Logger starten (Terminal 3) — läuft parallel zum Test
3. Hand vom Bein wegnehmen sobald Plugin stabil hält
4. IK-Probe-Skript starten (Terminal 4) → Bein bewegt sich:
   - Erst zu Punkt A (Fuß bei -10 cm Body-Höhe)
   - Dann zu Punkt B (Fuß bei -7 cm Body-Höhe = 3 cm hoch)
5. Beobachten:
   - Fuß bewegt sich **linear vertikal** ~3 cm
   - RViz und echtes Bein synchron
   - Kein Anschlag-Brumm, kein Watchdog-Trip
   - Strom-CSV läuft, Peak < 4 A
6. Logger nach ~10 s stoppen (Ctrl-C)
7. **Wenn F.2 hängt:** vor F.3 stoppen, IK diagnostizieren

### F.3 — gait_node mit /cmd_vel (Voll-Pipeline) (~30 min)

**Setup-Übergang von F.2:**
- Plugin (Terminal 1) **läuft weiter**
- Logger (Terminal 3) **läuft weiter** (oder neuer Log `leg6_F3_*.csv`)
- 2 neue Terminals dazu:
  - Terminal 5: `ros2 launch hexapod_gait gait.launch.py`
  - Terminal 6: `ros2 topic pub /cmd_vel ...`

**gait_node starten (Terminal 5):**

```bash
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py
# erwartet: gait_node spawned, /cmd_body_height etc. publiziert
```

**/cmd_vel füttern (Terminal 6):**

```bash
ros2 topic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

**Beobachten:**
- gait_node generiert Tripod-Pattern für **alle 6 Beine**
- **leg_6** schwingt physisch vor/zurück + Foot-Hub im Tripod-Phase
- **Andere 5 Beine** (leg_1..5): JTC schickt Goals → Plugin sendet
  Pulse an Pins 0–14 → keine Servos angeschlossen, harmlos.
  ANY_SERVO_OVERCURRENT-false-positives möglich (siehe Stolperfallen);
  tolerieren wenn leg_6 ok.
- RViz zeigt alle 6 Beine im Tripod-Pattern (Echo-State)
- Strom-CSV korreliert mit leg_6-Bewegungsphase

**Stop nach ~10 s:**
- Ctrl-C `cmd_vel` (Terminal 6)
- Ctrl-C `gait.launch.py` (Terminal 5)
- Plugin (Terminal 1) **läuft weiter** für F.4-Auswertung

**Wenn F.3 hängt aber F.2 grün war:**
- Problem in gait_node oder cmd_vel-Mapping
- Debug: `ros2 topic echo /leg_6_controller/joint_trajectory`
  zeigt was gait_node sendet, vergleichen mit F.2 IK-Output

### F.4 — Strom-Profil-Auswertung (~20 min)

**Plugin abschalten (Terminal 1 Ctrl-C), PSU AUS, 3 Servos abklemmen.**

CSV-Auswertung:

```python
import pandas as pd

df = pd.read_csv("leg6_F3_*.csv")
print(df.describe())  # min/max/mean pro Spalte
df.plot(x="t_s", y=["p15", "p16", "p17", "current_ma"])
# Subplots oder einzelne Plots
```

**Was wird extrahiert (für Stage G):**

| Metrik | Quelle | Stage-G-Zweck |
|---|---|---|
| Max Δp_i / Δt pro Joint (µs/s) | `p15`, `p16`, `p17` Spalten in CSV | rad/s pro Joint via `pulse_per_rad`-Steigung → Vel-Limit-Ableitung |
| Max d/dt(Δp/Δt) | Numerische 2. Ableitung der p-Spalten | rad/s² pro Joint → Accel-Limit-Ableitung |
| Peak `current_ma` | Rail-Total-Strom | Sanity-Check ob 8 A CC-Limit nie getriggert |
| Idle vs. Walking-Strom | Mean während idle vs. cmd_vel-Test | Strom-Budget für PSU-Sizing in Phase 8 |

**70 %-Regel:** Vel/Accel-Limits werden in Stage G **konservativ ~70 %
der gemessenen Peaks** in `controllers.real.yaml` eingetragen.

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| F-T1 | `colcon build --packages-select hexapod_hardware hexapod_kinematics hexapod_gait hexapod_bringup` | grün, regression-frei | Claude |
| F-T2 | `colcon test` | 208/0/20 + 18/0/0 (+hexapod_kinematics + hexapod_gait grün) | Claude |
| F-T3 (User) | F.1 Lineal-Check: alle 3 Segment-Längen innerhalb ±5 mm von URDF | manuelle Bestätigung | User |
| F-T4 (User) | F.2 IK-Probe: Fuß bewegt sich linear vertikal ~3 cm, kein Stall | manuelle Bestätigung + Strom-CSV | User |
| F-T5 (User) | F.2 RViz und echtes Bein synchron während IK-Test | manuelle Bestätigung | User |
| F-T6 (User) | F.3 gait_node + cmd_vel: leg_6 schwingt im Tripod-Pattern, kein Stall | manuelle Bestätigung + Strom-CSV | User |
| F-T7 (User) | F.3 alle 6 Beine in RViz im Tripod-Pattern (Echo-State) | manuelle Bestätigung | User |
| F-T8 | F.4 CSV-Auswertung: Vel-Peaks pro Joint, Accel-Peaks, Strom-Peak < 4 A | Claude + User (Plot-Sichtung) | beide |

### Was bewusst NICHT in Stage F getestet wird

- **Vel/Accel-Limits in YAML eintragen** (Stage G)
- **Boden-Walking** (Phase 12)
- **PS4-Controller** (Phase 12)
- **18-Servo-Voll-Stand** (Phase 12)

---

## Progress-Checkliste

- [ ] F.1 phase_10_stage_f_plan.md (Plan-Doku) finalisiert + User-Freigabe
- [ ] F.2 phase_10_stage_f_test_commands.md angelegt
- [ ] F.3 tools/phase_10_f2_ik_probe.py angelegt (Standalone Skript)
- [ ] F.4 F.0 Bench-Setup-Check (PSU 7.0 V / **8 A**, alle 3 Servos an Pin 15+16+17)
- [ ] F.5 F.1 Bein-Geometrie-Lineal-Check ausgeführt; Coxa/Femur/Tibia ±5 mm OK ODER URDF angepasst
- [ ] F.6 F.2 Plugin-Bringup grün mit User-Hand-Mitigation, alle 3 Servos halten Bein-Pose
- [ ] F.7 F.2 IK-Probe-Skript ausgeführt; Fuß-Hub ~3 cm sichtbar, kein Stall
- [ ] F.8 F.2 Strom-CSV `leg6_F2_*.csv` aufgezeichnet
- [ ] F.9 F.3 gait_node gestartet via `gait.launch.py`
- [ ] F.10 F.3 /cmd_vel mit linear.x=0.02 → leg_6 schwingt Tripod, alle 6 RViz-Beine bewegt
- [ ] F.11 F.3 Strom-CSV `leg6_F3_*.csv` aufgezeichnet
- [ ] F.12 F.4 CSV-Auswertung: Vel-Peaks + Accel-Peaks + Strom-Peaks dokumentiert (Plot oder Tabelle)
- [ ] F.13 Shutdown + alle 3 Servos abgeklemmt, PSU AUS
- [ ] F.14 colcon build + test grün
- [ ] F.15 User-Bestätigung F-T3..F-T7
- [ ] F.16 Kritischer Self-Review-Tabelle
- [ ] F.17 Stage-F-Notizen (Geometrie-Abweichungen, IK-Verhalten, Phase-12-Vorbereitung)

**Done-Kriterium F erreicht:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke F-T3..F-T7 bestätigt.

---

## Erwartete Stage-F-Dauer

- F.1 Plan-Doku (diese Datei): ~40 min Claude (erledigt)
- F.2 test_commands.md: ~25 min Claude
- F.3 IK-Probe-Skript: ~20 min Claude
- F.4–F.5 Bench-Setup + Lineal-Check: ~25 min User
- F.6–F.7 IK-Probe-Test: ~30 min (Hand + Bringup + Test)
- F.8 CSV-Logger Setup: ~5 min
- F.9–F.10 gait_node + cmd_vel: ~30 min
- F.11 CSV abgeschlossen: ~5 min
- F.12 F.4 CSV-Auswertung: ~25 min (User + Claude gemeinsam beim Plot)
- F.13 Shutdown: ~5 min
- F.14 Build + Test: ~5 min
- F.15–F.17 Sync + Self-Review + Notizen: ~30 min

**Schätzung:** ~1.5 h Claude-Arbeit + ~2 h User-HW-Arbeit + ~30 min Sync
= **~4 h Gesamt** (entspricht etwa 1 d aus Mutter-Plan-1.5-d-Schätzung,
das letzte 0.5 d wäre wenn IK + Geometrie nicht direkt zusammenpassen
und Iterations-Schleifen nötig sind).
