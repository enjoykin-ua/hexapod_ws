# S4-4 — Test-Befehle (Slip / Kontaktverlust → Freeze)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** ein **Stütz-Fuß ohne Halt**
> (über eine Kante/Abgrund tiefer als `cliff_depth`, oder Slip) → **Freeze**, bevor der Roboter
> kippt / von der Kante läuft. Stage 4 **isoliert** (`leveling_enable:=false`, Default in `*_walk`).

## Konventionen

- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop`.
- **Opt-in:** `slip_detection_enable` Default **false**. `cliff_depth` 0.03 (Grenze folgbares Terrain
  ↔ Abgrund). **Kante-Welt = `step_walk step_drop:=0.06`** (6 cm Abfall > cliff_depth → kein Boden
  in Reichweite → Freeze).
- **Bauen vorab:**
  ```bash
  cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
  colcon build --packages-select hexapod_gait hexapod_gazebo hexapod_bringup --symlink-install
  ```

## Beobachten (gait_node-Terminal)
- Beim Freeze: **ERROR-Log** `Stütz-Verlust erkannt (N Bein(e) ohne Halt — Kante/Abgrund oder Slip)
  — Safety-Freeze`. Danach publisht der Node keine neue Trajektorie mehr → der Roboter **hält an**
  (JTC friert die letzte Pose). In Sim ohne Plugin = lokaler Stopp (eine Service-unreachable-Meldung
  ist normal).

---

## T1 — Kante / Abgrund: freezt der Roboter, statt drüber zu laufen? (A/B)

**▶ Terminal 1 — 6-cm-Kante starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=0.06 gait_pattern:=tripod
```
⏳ aufstehen abwarten. Der Roboter steht auf der **oberen** Plattform, Kante bei x=0.

**▶ Terminal 2 — A) OHNE Slip-Erkennung (Default) auf die Kante zufahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
→ Erwartung: er läuft **über die Kante** (Vorderbeine finden keinen Boden, kippt/fällt). `Ctrl-C`.

**▶ Terminal 2 — B) MIT Slip-Erkennung:**
```bash
ros2 daemon stop
ros2 param set /gait_node slip_detection_enable true
# optional sichtbarer: der Fuß reicht aktiv bis cliff_depth in die Leere
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** sobald ein Vorderbein über der Kante in Stance **keinen Boden** findet (nach
Grace + Entprellung), kommt der **ERROR-Log + Freeze** → der Roboter **hält an der Kante** statt
hinunterzulaufen.

**Recovery:** `Ctrl-C` auf den Publisher (cmd_vel=0 → STOPPING → reset) — oder
`ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'`. Danach läuft er wieder normal.

---

## T2 — Flach: kein Fehlalarm

```bash
# Terminal 1:
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0 gait_pattern:=tripod leveling_enable:=false
# Terminal 2 (nach Aufstehen):
ros2 daemon stop
ros2 param set /gait_node slip_detection_enable true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** normaler Lauf, **kein** Freeze (Kontakt zuverlässig, `miss 0`). Belegt: keine
Fehlauslösung auf flachem Boden.

---

## T3 (optional) — Tuning

```bash
ros2 daemon stop
ros2 param set /gait_node cliff_depth 0.04            # tiefer folgen, erst >4 cm = Abgrund
ros2 param set /gait_node slip_debounce_ticks 5       # schnellerer Freeze (Minimum > contact_timeout)
ros2 param set /gait_node slip_min_lost_legs 1        # 1 Bein reicht (früh stoppen)
ros2 param set /gait_node slip_grace_stance_phase 0.6 # bei schnellerem cycle_time hochsetzen
```
> ⚠️ `slip_grace_stance_phase` ist cycle_time-abhängig (wie `touchdown_probe_start_stance_phase`):
> muss > Kontakt-Lag in Stance-Phasen (bei `cycle_time=2.0` ≈ 0.27) sein, sonst Fehlalarm auf flach.
> `slip_debounce_ticks` muss > `contact_timeout` (≈5 Ticks) bleiben.

---

## Rückmeldung an mich (knapp genügt)
- T1: freezt er an der Kante (ERROR-Log) statt drüber? Ohne Slip läuft er drüber/kippt?
- T2: flach **kein** Fehl-Freeze über längeren Lauf?
- Recovery via cmd_vel=0 ok (läuft danach weiter)?
- Auffälligkeiten: zu früh/zu spät Freeze, Logs?
