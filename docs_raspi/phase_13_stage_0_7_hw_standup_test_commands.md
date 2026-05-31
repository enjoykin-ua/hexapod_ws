# Phase 13 Stage 0.7 — HW-Test-Anleitung (0.7.8 aufgebockt + 0.7.9 Boden + Strom)

> Plan: [`phase_13_stage_0_7_cartesian_standup_plan.md`](phase_13_stage_0_7_cartesian_standup_plan.md).
> **Interaktiv** — User führt aus dem Doc aus, knappe Status
> (Memory [[feedback_test_commands_in_doc_not_chat]], [[feedback_interactive_stage_test_doc]]).
> **Teil A = 0.7.8** (aufgebockt, Sicherheits-Check) → **Teil B = 0.7.9** (Boden,
> Strom-Messung = **das eigentliche Done-Kriterium der Stage**).

## ⚠️ Safety (CLAUDE.md §9)
- **Erst aufgebockt (Teil A), dann Boden (Teil B)** — nicht überspringen.
- **PSU-Kill-Switch griffbereit**, bei jedem Stall/unerwarteten Ruck sofort trennen.
- Strom-Limit der FW ist jetzt **7000 mA** (geflasht). Aufstehen rampt über ~4 s.
- Voraussetzung: die FW mit dem 7000-mA-Wert ist geflasht (sonst Trip bei 3,5 A).

---

## 0. Vorbereitung (in jedem Terminal `source`)
0.7 hat nur **`hexapod_gait`** geändert (Engine + Node). Bauen + sourcen:
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
echo "$HEX_URDF"
```

---

# TEIL A — HW aufgebockt (0.7.8, Sicherheits-Check)

> Zweck: verifizieren, dass das **kartesische** Aufstehen auf der echten Hardware
> sauber läuft (kein Stall/Freeze/IKError/Overcurrent), **bevor** es am Boden
> unter Last fährt. Aufgebockt gibt es **keinen Boden** — die Touchdown-Phase
> fährt die Füße „zum Boden, der nicht da ist".

## A-T1 — Init-Sequenz aufgebockt (Vorbedingung)
```bash
# Terminal 1 — Hardware + Relay-gated Init + JTCs (laeuft weiter!)
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
- [ ] Alle 6 Beine kommen sauber in power_on_mid hoch, Relay an, kein Trip (= 0.6 T1).

## A-T2 — Kartesisches Aufstehen aufgebockt
```bash
# Terminal 2
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian
```
**Erwartung (über ~4 s, am aufgebockten Roboter):**
- [ ] **Phase 1** (~erste 1,6 s): die Beine **strecken** sich nach außen-unten
      (Füße fahren auf die Touchdown-Höhe — in der Luft, da kein Boden). Das
      Bein ist dabei recht **gestreckt** (Knie ~58°) — das sieht ungewöhnlich
      aus, ist aber **normal/erwartet** (R6 im Self-Review).
- [ ] **Phase 2** (~restliche 2,4 s): die Beine **beugen** sich in die Stand-
      Konfiguration (Tibia knickt ein).
- [ ] **Kein Servo-Stall**, **kein** hartes Springen, **kein** `IKError`
      (Terminal 2), **kein** `SAFETY FREEZE`/`OVERCURRENT`/`WATCHDOG` (Terminal 1).
- [ ] Terminal 2: Log `Cartesian-Standup gestartet … (phase1=0.40, bh_start=-0.0135)`.

> **🟡 Achtung Tibia-Margin (R7):** die Touchdown-Pose ist die gestreckteste des
> Pfades. Falls **ein Bein in Phase 1 einfriert** (Plugin `safety_freeze`, PWM
> am Cal-Limit), ist `body_height_start` für die reale Cal zu tief → in Teil B
> etwas höher setzen (z. B. `body_height_start:=-0.010`). Aufgebockt unkritisch
> (nur beobachten + melden).

## A-T3 — Endpose stabil
- [ ] Beine halten die Stand-Konfiguration ruhig (aufgebockt hängend), kein Zittern.
```bash
# Terminal 3 (optional): ros2 topic echo /joint_states --once
# erwartet alle 6: coxa ~0 / femur -0.240 / tibia +0.758
```

## A-T4 — Shutdown
```bash
# Terminal 2 Strg+C (gait), dann Terminal 1 Strg+C (real.launch.py)
```
- [ ] Rail wird stromlos (Servos limp).

**→ Wenn Teil A sauber war: Roboter vom Bock nehmen, auf den Bauch legen, weiter mit Teil B.**

---

# TEIL B — HW am Boden (0.7.9, **Done-Kriterium: Strom**)

> Zweck: messen, dass das kartesische Aufstehen am Boden **schürffrei** ist und
> der Strom **nahe Stand-Niveau** bleibt (statt >3,5 A mit Voltage-Drop beim
> alten joint-space-Aufstehen). Das ist der Beweis, dass Stage 0.7 das
> ursprüngliche Problem löst.

**Aufbau:** Roboter liegt am Bauch auf dem Boden (Beine in power_on_mid einziehbar),
PSU mit **Stromanzeige** sichtbar, Kill-Switch in der Hand.

## B-T1 — Init am Boden
```bash
# Terminal 1
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
- [ ] Init sauber, alle 6 in power_on_mid (Bauch liegt auf), Relay an.

## B-T2 — Kartesisches Aufstehen am Boden + **Strom messen** (Kern)
**Die PSU-Stromanzeige während des ganzen Aufstehens beobachten und den Peak notieren.**

### B-T2a — RViz parallel starten (Terminal 3, **vor** dem gait-Launch)
> Zeigt das Modell live aus den **echten** Servo-Positionen — `real.launch.py`
> (B-T1) publisht bereits `/joint_states` (vom Plugin), `/tf` + `/robot_description`
> (robot_state_publisher). RViz muss nur zuschauen. **Nicht** `display.launch.py`
> nehmen — die startet einen zweiten robot_state_publisher (+ Slider-GUI) und
> kollidiert mit der HW-Pipeline. Config = HW-Variante mit Fixed Frame `base_link`
> (auf HW gibt es keinen `world`-Frame).
```bash
# Terminal 3 (real.launch.py aus B-T1 läuft schon)
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
- [ ] RViz zeigt den Hexapod in der power_on_mid-Pose (Beine eingezogen), **keine**
      „Fixed Frame does not exist"-Meldung (Fixed Frame = base_link).

### B-T2b — Aufstehen starten (Terminal 2)
```bash
# Terminal 2
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian \
    auto_standup_duration:=8
```
- [ ] **RViz spiegelt das Aufstehen** synchron zur echten HW (Phase 1 Touchdown,
      Phase 2 Push) — Modell und realer Roboter zeigen dieselbe Pose.
> **Aufsteh-Dauer 8 s** (Stage-0.7-Anpassung): langsamer Hub → niedrigerer
> Strom-Spitzenwert → weniger PSU-Spannungseinbruch (8 s ist seit 2026-05-31 auch
> der Default). Reicht 8 s nicht, höher gehen — bis `auto_standup_duration:=15`.

**Erwartung / zu melden:**
- [ ] **Strom-Peak** während des Aufstehens: __________ mA (Erwartung: **deutlich
      unter 3,5 A**, nahe Stand-Niveau; kein Overcurrent-Trip, **kein** Voltage-Drop).
- [ ] Spannung bricht **nicht** mehr bis Undervoltage ein (Roboter steht **ganz**
      auf, nicht nur halb).
- [ ] **Schürffrei:** in Phase 2 bleiben die Füße auf ihrem Bodenpunkt stehen
      (kein sichtbares Einwärts-Rutschen), der Körper hebt senkrecht.
- [ ] Der Roboter **steht am Ende wirklich** (alle 6 Beine tragen, Bauch frei),
      stabil, kein Kippen.
- [ ] Terminal 1: kein `OVERCURRENT`/`UNDERVOLTAGE`/`WATCHDOG`; Terminal 2: kein `IKError`.

> **Falls ein Bein einfriert** (Tibia-Margin, s. A-T2): Sim+gait stoppen, mit
> höherem `body_height_start` neu starten, z. B.:
> ```bash
> ros2 launch hexapod_gait gait.launch.py use_sim_time:=false \
>     robot_description_file:="$HEX_URDF" standup_mode:=cartesian \
>     auto_standup_duration:=8 body_height_start:=-0.010
> ```
> **Falls die Füße in Phase 1 schon schürfen** (zu tief): `body_height_start`
> höher (weniger negativ). **Falls der Körper am Übergang durchsackt** (zu hoch):
> `body_height_start` tiefer (negativer). Iterieren bis sauber.

## B-T3 — (optional, sehr aufschlussreich) Vergleich joint_space am Boden
> Das ist der **direkte Beweis** des Unterschieds — Vorsicht: das alte Aufstehen
> zieht hohen Strom + Spannungseinbruch (du kennst es). Kill-Switch bereit.
```bash
# Terminal 1 neu (Init), Terminal 2 — gleiche 8 s wie B-T2 für fairen Vergleich:
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false \
    robot_description_file:="$HEX_URDF" standup_mode:=joint_space \
    auto_standup_duration:=8
```
- [ ] **Strom-Peak joint_space:** __________ mA (Erwartung: >3,5 A, Voltage-Drop,
      Füße schürfen sichtbar nach innen). **Vergleich** zu B-T2 (gleiche 8 s) =
      der 0.7-Beweis: gleicher Hub, nur der schürffreie Weg spart den Strom.

## B-T4 — Endpose stabil am Boden
- [ ] Roboter steht mehrere Sekunden stabil, Strom im Stand ~400 mA, kein Trip.

## B-T5 — Shutdown
```bash
# Terminal 2 Strg+C, dann Terminal 1 Strg+C
pgrep -af "ros2 launch|gait_node|ros2_control_node" || echo "alle Prozesse beendet"
```

---

## Done-Mapping (→ phase_13_stage_0_progress.md 0.7.x)
| Test | Bullet |
|---|---|
| A-T1..T4 aufgebockt: cartesian läuft sauber, kein Stall/Freeze | **0.7.8** |
| B-T2 Boden: Strom nahe Stand-Niveau, schürffrei, Roboter steht | **0.7.9 (Done-Kriterium)** |
| B-T3 joint_space-Vergleich (optional) | 0.7.9 Beleg |

## Findings (User)
| Test | Status | Beobachtung / Messwert |
|---|---|---|
| A-T1 Init aufgebockt | | |
| A-T2 cartesian aufgebockt (kein Stall/Freeze) | | |
| A-T3 Endpose aufgebockt | | |
| B-T2 cartesian Boden — **Strom-Peak** | | ______ mA |
| B-T2 schürffrei + steht | | |
| B-T3 joint_space Boden — Strom-Peak (optional) | | ______ mA |
| B-T4 Endpose Boden stabil | | |
