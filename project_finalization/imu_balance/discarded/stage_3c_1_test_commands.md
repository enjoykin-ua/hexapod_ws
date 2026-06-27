# Stufe 3c-1 — Test-Befehle (interaktiv)

> # ❌ VERWORFEN (2026-06-27)
> Testbefehle für den verworfenen 3c-1-Ansatz (Voll-Leveling + θ-Tabelle). Der zugehörige
> Code ist zurückgesetzt → diese Befehle laufen nicht mehr. **Nachfolge: Terrain-Following**
> ([Plan](../stage_3_terrain_following_plan.md), [Retro](../terrain_following_pivot_retro.md)). Nur als
> Referenz behalten.

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** (frische Terminals + vollständige Befehle). Setzt 3a (🟢) voraus.

## Konventionen

- **Sourcing** steht in jedem Befehlsblock mit drin (`source /opt/ros/jazzy/setup.bash
  && source ~/hexapod_ws/install/setup.bash`).
- **Zwischen Tests:** alle Terminals mit `Strg-C` beenden.
- **`/imu/monitor`** = `Vector3` mit **x=roll, y=pitch, z=yaw** (Radiant; ×57.3 = Grad).
  Auf der +Y-geneigten Rampe ist **y (pitch)** der Hangwinkel.
- **Neu in 3c-1:** mit `slope_adapt_enable:=true` levelt der Roboter im Lauf **voll**
  (Walking-Clamp wird auf die Tabellen-Range angehoben, statt 3a-4°) und passt
  body_height/radial/step_length/Schwunghöhe an θ an.
- **Tabelle = Option A (`--anchor-nominal`):** **θ=0 = dein Nominal-Stance**
  (−0.080/0.160/0.050), step_length **nie über Nominal**, body/radial senken sich **nur
  am Hang nach Bedarf**. Auf flachem Boden also **kein** Unterschied zum Normalverhalten.
  Reichweite voll-gelevelt **~+7° / −9°** (α=0 = Körper exakt horizontal ist envelope-
  teuer; steilere Hänge = 3c-2). Das 2.5°-Totband hält „flach" (θ≤2.5°) am Nominal.

---

## Einmalig: bauen

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## T3c1.U — Unit- + Tool-Tests (ohne Sim)

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon test --packages-select hexapod_kinematics hexapod_gait --event-handlers console_direct+
colcon test-result --verbose
# Tool-Tests (nicht in colcon):
pytest tools/test_slope_param_table.py -q
# θ→Param-Tabelle ansehen (committet, Option A):
cat src/hexapod_gait/config/slope_params.yaml
```
**Erwartung:** Paket-Tests grün (gait 282 + kinematics 43, 0 Fehler); Tool 16 grün;
Tabelle θ ≈ −9° … +7°, θ=0-Zeile = −0.080/0.160/0.050, body_height sinkt + step_length
schrumpft mit |θ|.

---

## T3c1.1 — Sanity: Rampe 8° hoch, Adaption greift

**Terminal 1 — Ramp-Welt 8°:**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
**Terminal 2 — gait (Leveling + Slope-Adapt AN):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true slope_adapt_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
> Beim Start loggt der Node `Slope-Param-Tabelle geladen: … (θ -9..7°)`. Fehlt die Zeile
> (`Slope-Tabelle nicht geladen`), wurde `config/slope_params.yaml` nicht installiert →
> neu bauen (oben).

**Terminal 3 — pitch beobachten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```
**Terminal 4 — langsam vorwärts in die Rampe:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Terminal 5 (optional) — Geometrie gegenchecken:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
watch -n0.5 'ros2 param get /gait_node body_height; ros2 param get /gait_node step_length_max'
```

**Erwartung:** spawnt flach, läuft +x in die Rampe, levelt voll → **pitch (y) bleibt nahe
0** (±~2.5° Totband, NICHT ~4° wie in 3a), kein Freeze; `body_height` wandert beim
Klettern Richtung Hang-Zeile (~−0.10).

---

## T3c1.2 — Voll-Leveling im Lauf: A (ohne) vs. B (mit Slope-Adapt)

Beide auf einer **8°-Rampe**. Erst A komplett durchlaufen, alle Terminals mit `Strg-C`
beenden, dann B.

### A) OHNE Slope-Adapt (3a-Baseline)

**Terminal 1 — Welt:**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
**Terminal 2 — gait (nur Leveling, KEIN slope_adapt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
**Terminal 3 — pitch:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```
**Terminal 4 — vorwärts:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Erwartung A:** levelt nur ~4° (Walking-Clamp) → Körper neigt sich sichtbar mit
(**pitch ~4°**); ggf. Stufe-1-Tip-WARN.

### B) MIT Slope-Adapt

**Terminal 1 — Welt:**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
**Terminal 2 — gait (Leveling + slope_adapt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true slope_adapt_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
**Terminal 3 — pitch:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```
**Terminal 4 — vorwärts:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Erwartung B:** **Körper voll gelevelt** (pitch nahe 0, NICHT ~4°), Schwungbeine heben
sichtbar höher (Apex-Boost), `body_height` senkt sich, kein Freeze. Tip stoppt **nicht**
(volles Leveling → Rest-Neigung ~0).

**Melde:** ist der Körper in B sichtbar waagerechter als in A? Apex-Boost sichtbar?

---

## T3c1.3 — Wechselnder Hang: Params folgen θ stetig (kein Sprung/Freeze am Knick)

Die Ramp-Welt ist flach→Hang→Plateau. Langsam **komplett** über die Rampe aufs Plateau
fahren; die Adaption muss am Knick (flach→Hang bei x=0 und Hang→Plateau) **kontinuierlich**
mitlaufen.

**Terminal 1 — Welt 8°:**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
**Terminal 2 — gait (Leveling + slope_adapt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true slope_adapt_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
**Terminal 3 — pitch + Geometrie mitloggen:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
watch -n0.5 'ros2 topic echo /imu/monitor --once; ros2 param get /gait_node body_height; ros2 param get /gait_node step_length_max'
```
**Terminal 4 — vorwärts (laufen lassen, bis er aufs Plateau kommt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Erwartung:** am Knick **kein Ruck/Freeze**; body_height/step_length wandern glatt (Slew)
in die Hang-Zeile und auf dem Plateau wieder zurück Richtung θ=0-Zeile (−0.080/0.050).
pitch bleibt am Hang geleveled (~0).

---

## T3c1.4 — Ladder (Max-Winkel der Option-A-Tabelle)

Wie **T3c1.2-B**, aber `slope_deg` in **Terminal 1** nacheinander auf **4, 6, 8, 10, 12**
setzen (alle Terminals zwischen den Läufen mit `Strg-C` beenden). Melde den real sauber
voll-gelevelt erreichten Winkel.

**Terminal 1 — Welt (slope_deg pro Lauf ändern: 4.0 / 6.0 / 8.0 / 10.0 / 12.0):**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=4.0
```
**Terminal 2 — gait (Leveling + slope_adapt):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true leveling_enable:=true slope_adapt_enable:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
**Terminal 3 — pitch:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/monitor
```
**Terminal 4 — vorwärts:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
> **Erwartung:** voll-gelevelt sauber bis ~**+7°/−9°** (Tabellen-Max der konservativen
> Option-A-Tabelle). Jenseits klemmt die Tabelle auf die letzte Zeile → Rest-Neigung
> wächst → Stall/Tip erwartet. **Mehr Reichweite** = Tabelle ohne `--anchor-nominal` neu
> erzeugen (Option B) oder **3c-2** (Wave + α·θ-Setpoint-Blend). Echte HW-Grenze =
> Servo-Torque (Block A), nicht Sim-CoG.

> **Tip-Schwelle stört?** Falls bei steileren Läufen die Stufe-1-Kipp-Erkennung vorzeitig
> stoppt, in einem Extra-Terminal live anheben (Daemon-Hinweis s.u.):
> ```bash
> source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
> ros2 param set /gait_node tip_angle_warn_deg 35
> ros2 param set /gait_node tip_angle_crit_deg 45
> ```

---

## Hinweise

- **`ros2 param set … „Node not found"`:** stale ROS2-Daemon (häufig nach mehreren
  Launches) → `ros2 daemon stop` (startet neu) + `ros2 node list` zur Bestätigung, dann
  `ros2 param set` erneut.
- **Live umschalten statt Neustart:** `ros2 param set /gait_node slope_adapt_enable true`
  (bzw. `false`) — der Launch-Arg oben umgeht den Daemon-Stolperstein.

## Bekannte Grenzen / Beobachtungspunkte (3c-1)

- **Reichweite ~+7°/−9°** (Option A, voll gelevelt): konservativ (flach = Nominal). Steiler
  = Option B (Schranken lockern, 10-s-Tool-Lauf, kein Code) oder 3c-2 (Wave + α-Blend).
- **θ-Schätzung `slope = tilt + corr`** (zentrale neue Annahme): in T3c1.1/T3c1.3
  verifizieren, dass `body_height` beim Reinlaufen tatsächlich Richtung Hang-Zeile wandert
  (zeigt, dass θ den echten Hang trackt, obwohl gelevelt wird).
- **Cross-Slope** (rein seitlich am Hang): θ-entlang-Fahrt ≈ 0 → Tabelle gibt Nominal,
  aber das Leveling rotiert um die volle Hang-Magnitude → CoG dieser Pose ist offline
  **nicht** als θ=0 bewiesen. Für 3c-1 Randfall (Vorwärts-Klettern ist der Fokus); volle
  Robustheit = 3d. In Sim auf Schlupf/Kippen beim Quer-Traversieren achten.
- **Transient beim Rampen-Eintritt:** steigt der Hang schneller als der Param-Slew, wird
  kurz volles Leveling auf noch-nicht-adaptierter Geometrie versucht → IK-Fallback
  degradiert (skaliert), **kein** Freeze. Auf der graduellen Ramp-Welt unkritisch.
