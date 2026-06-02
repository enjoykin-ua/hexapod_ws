# Phase 13 Stage 1 / Teil 2.2 — Test-Commands: Feet-closer Walk (Sim → HW)

> **Plan:** [`phase_13_stage_1_tibia_unlock_plan.md`](phase_13_stage_1_tibia_unlock_plan.md) §2 Sub-Stage 2.2.
> **Preset:** `src/hexapod_gait/config/presets/feet_closer_walk.yaml`
> (radial 0.220 / step_length 0.089 / step_height 0.040 / bh −0.080 / cycle 2.0).
> **Form:** Du führst aus, knappe Status zurück. **REIHENFOLGE: erst §S (Sim RViz+Gazebo),
> dann — wenn grün + committet — §T (HW aufgebockt).** (User-Wunsch: Sim vor HW.)
>
> **Was wir sehen wollen:** sichtbar **größere Schritte** (Schrittweite ~2× = 0.089 statt
> 0.05) und **mehr Coxa-Schwenk/Hub** als bisher, **ohne** `IKError`/Freeze, in **alle**
> Richtungen (vorwärts / seitwärts / drehen). Die Füße stehen näher am Körper.

---

# §S — SIM-Gate (RViz + Gazebo) — ZWEI-PHASEN-QUICKTEST  [Checkliste 2.2.3]

> **Wichtige Erkenntnis (2026-06-02):** Die feet-closer-Pose (radial 0.220) ist NUR
> fürs **Laufen** (Körper hoch, bh −0.080) erreichbar — **NICHT für den Aufsteh-Touchdown**
> (Bauch am Boden, bh_start −0.0135): dort müsste der Femur >90° (mech. Limit ±1.57) →
> IK-Fail (genau das Log aus dem ersten S1-Versuch). Lösung = **Zwei-Phasen**: mit dem
> standup-sicheren radial **0.295** aufstehen, dann in STANDING live auf **0.220**
> reposition, dann laufen. Dieser Quicktest macht das **per Live-Param ohne Code** (das
> Preset NICHT beim Standup laden!). Der Reset ist instantan (Fuß-Sprung) — in Sim ok;
> die saubere Tripod-Reposition kommt mit Sub-Stage 2.3.

## S0 — Build + Sim starten

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_description hexapod_bringup
source install/setup.bash
```
**Terminal 1 — Gazebo:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
Warten bis Gazebo offen + 7 Spawner aktiv.

## S1 — Aufstehen mit Default-radial 0.295 (OHNE Preset!) → STANDING

**Terminal 2** (kein `params_file` → radial 0.295, der standup-sichere Wert):
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian auto_standup_duration:=8
```
warten bis `STATE_STANDING`.
**Erwartung:** sauberes Aufstehen wie gehabt, **kein** IK-Fail (radial 0.295 ist
standup-grün). Beine relativ gestreckt (Füße weit draußen).

## S2 — Phase 2: Füße nach innen reposition (Live-Param, in STANDING)

**Terminal 3:**
```bash
cd ~/hexapod_ws && source install/setup.bash
# Füße nach innen (Stand-Pose-Reset, instantaner Sprung)
ros2 param set /gait_node radial_distance 0.220
# Schritt-Params der feet-closer-Pose live setzen
ros2 param set /gait_node step_length_max 0.089
ros2 param set /gait_node step_height 0.040
```
**Erwartung:** alle 6 Füße springen nach innen (radial 0.220), Knie sichtbar stärker
gebeugt; jeder `param set` → Log `param updated: …` in Terminal 2, **kein** `require
STATE_STANDING`-Reject (= Engine ist in STANDING), **kein** IK-Fail (0.220 bei bh −0.080
ist erreichbar).

## S3 — Vorwärts laufen (sichtbar größere Schritte)

**Terminal 3:**
```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.08}}'
```
~10–15 s beobachten (Gazebo + RViz), dann `Strg+C`.
**Erwartung:** deutlich **größere Schritte + mehr Hub** als vorher, sauberer Tripod,
**kein** `IKError`/Freeze, kein Umkippen.

## S4 — Omnidirektional gegenprüfen (war RED-kritisch)

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {y: 0.06}}'      # seitwärts
# Strg+C, dann:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'      # drehen
# Strg+C, dann:
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05, y: 0.04}}'  # diagonal
```
Jeweils ~8 s, dann `Strg+C`.
**Erwartung:** alle Richtungen sauber, **kein** `IKError`/Freeze (offline alle ✓ grün).

### Findings §S (User)
| Test | Status | Notiz |
|---|---|---|
| S1 Aufstehen @ radial 0.295 sauber (kein IK-Fail) | | |
| S2 Reposition → 0.220 live, kein Reject/IK-Fail | | |
| S3 Vorwärts: sichtbar größere Schritte/Hub | | |
| S4 Seitwärts / Drehen / Diagonal sauber | | |

> **→ Wenn §S grün: das Zwei-Phasen-Prinzip ist bewiesen → committen, dann §T (HW)
> bzw. Sub-Stage 2.3 (Zwei-Phasen sauber in die Engine bauen).**

---

# §T — HARDWARE (aufgebockt) — erst NACH §S + Commit  [Checkliste 2.2.4]

⚠️ **Sicherheit (CLAUDE.md §9):** aufgebockt, PSU-Kill-Switch griffbereit. Erst
langsam/kurz, bei Brummen/Stall/Body-Kontakt sofort `Strg+C`.

> **Auch HW = Zwei-Phasen:** Standup mit radial 0.295 (OHNE Preset), dann in STANDING
> live auf 0.220 reposition. **Der Reset ist ein instantaner Fuß-Sprung** — aufgebockt
> unkritisch, aber **am Boden** (T2) erst mit der sauberen Tripod-Reposition (2.3) machen,
> NICHT mit dem Sprung. T2 daher zunächst nur aufgebockt oder nach 2.3.

## T0 — Hardware + Aufstehen (radial 0.295, OHNE Preset)

**Terminal 1 — Hardware:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Terminal 2 — RViz (HW-Spiegel):**
```bash
cd ~/hexapod_ws && source install/setup.bash
rviz2 -d "$(ros2 pkg prefix --share hexapod_description)/config/view_hw.rviz"
```
**Terminal 3 — Gait (use_sim_time:=false!, kein params_file):**
```bash
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF" \
    standup_mode:=cartesian auto_standup_duration:=8
```
warten bis `STATE_STANDING`.

## T1 — Reposition + Vorwärts aufgebockt
**Terminal 4:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 param set /gait_node radial_distance 0.220
ros2 param set /gait_node step_length_max 0.089
ros2 param set /gait_node step_height 0.040
sleep 1
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.06}}'
```
~10 s, dann `Strg+C`. Optional 0.08.
**Erwartung:** Füße springen nach innen (aufgebockt ok), dann größere Schritte/Hub,
HW=RViz, kein `OVERCURRENT`/`WATCHDOG`/`SAFETY FREEZE` (T1) / `IKError` (T3), keine
Body-Berührung.

## T2 — griffiger Boden: echter Vortrieb (erst nach 2.3 / NICHT mit Sprung-Reset)
> Erst wenn die saubere Tripod-Reposition (2.3) existiert, am Boden testen — der
> instantane radial-Sprung würde am Boden destabilisieren.
**Erwartung (mit 2.3):** echter Vortrieb (nicht „auf der Stelle"), Strom im Rahmen.

### Findings §T (User)
| Test | Status | Notiz |
|---|---|---|
| T1 Reposition + Vorwärts aufgebockt, kein Freeze/Overcurrent | | |
| T2 griffiger Boden (nach 2.3): echter Vortrieb | | |
