# Stufe 7 — Test-Befehle: Balance-Regler v2 auf HW (aufgebockt, 7.10)

> **Copy-paste-fertig.** Jeder Test enthält **alle** Terminals/Befehle (Source, Bringup, Aufstehen,
> Teleop, Tuning). **HW, aufgebockt** (CLAUDE.md §9). Ziel: v2 (a) läuft per **Default wie Stufe 2**
> (kein Regress), (b) die **Hysterese killt das Pendeln** aus IP3.2, (c) **per-Achse** + Validierung.
> Plan: [`stage_7_balance_controller_v2_plan.md`](stage_7_balance_controller_v2_plan.md).
>
> **Warum HW statt Sim:** die Logik ist durch 426 Unit-Tests abgedeckt; Gazebo ist **rauschfrei** und
> kann den Pendel-Fix gar nicht zeigen. Der Beweis geht nur auf HW (aufgebockt genügt — du hast das
> Pendeln dort gefunden). _(Optionaler Sim-Smoke: `ramp_walk.launch.py slope_deg:=8.0` → levelt wie
> vorher; ersetzt den HW-Test aber nicht.)_
>
> **Was du aufgebockt siehst:** der Körper hängt fest → er levelt sich nicht selbst, sondern **die Beine
> reagieren** (fahren in die kompensierende Stellung). Pendeln = die Beine/`pitch` schwingen hin und her.

## ⚠️ Safety (CLAUDE.md §9)
- **2S-LiPo dran, Roboter aufgebockt** (Beine frei), **Kill-Switch in der Hand**.
- **Gentle kippen** (wenige Grad, langsam) — zu weit/schnell → IP3.1-Tip-Netz **friert** ein (CRIT).
  Recovery: `ros2 service call /hexapod_sit_down std_srvs/srv/Trigger '{}'` dann `/hexapod_stand_up`.
- Alle Befehle laufen **lokal auf dem Pi** (SSH-Terminals) — kein DDS/Netzwerk nötig.

---

## Schritt 0 — Allgemein (einmalig pro Session)

**0a — Bauen + sourcen** (auf dem Pi):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
```

**0b — PS4-Controller bereitstellen** (optional — zum Fahren später; die Steh-Tests brauchen ihn
nicht, da du von Hand kippst). Der Controller muss an dem Rechner gekoppelt sein, der `joy_node`
startet (hier: Pi):

*Variante A — per USB-Kabel* (kein Pairing):
```bash
ls /dev/input/js*                                                   # js0 sichtbar?
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb # <- Teleop-Start (USB)
```

*Variante B — per Bluetooth* (bereits gekoppelt/trusted, MAC `D0:27:88:3D:68:9A`):
```bash
# PS-Taste druecken -> verbindet automatisch. Pruefen:
ls /dev/input/js*
bluetoothctl connect D0:27:88:3D:68:9A                             # nur falls PS-Taste nicht reicht
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt  # <- Teleop-Start (Bluetooth)
```
> Ohne Controller: `ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'`.
> Neu koppeln: [`../C4_test_commands.md`](../C4_test_commands.md).

---

## Schritt 1 — HW-Bringup + Aufstehen (aufgebockt) — Basis für alle Tests

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU (2S-LiPo dran, aufgebockt, Kill-Switch bereit!) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py \
    loopback_mode:=false \
    enable_imu:=true \
    initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + AUTOMATISCHES Aufstehen (kartesisch, ~8 s) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
#   -> steht automatisch auf (Node-Defaults standup_mode=cartesian, ~8 s), dann STANDING.
#      robot_description_file => URDF-Limits aktiv (Pflicht fuer Leveling-Clamp).
```
```bash
# ── Terminal 3 (Pi): Lage live mitschauen (fuer alle Tests offen lassen) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /imu/monitor      # x=roll, y=pitch, z=yaw [rad]; Grad = rad*57.3
```
```bash
# ── Terminal 4 (Pi): Tuning (hier laufen die param-set-Befehle der Tests) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 param get /gait_node leveling_kp_roll   # 0.4 -> Node lebt, per-Achse-Params da
```
> Sanity: `ros2 node list` zeigt `/gait_node`, `/bno055_imu`, `/imu_monitor`; `ros2 topic hz /imu/data` ~50 Hz.

---

## Test 7.10a — Default = kein Regress (Hysterese aus)

**Ziel:** mit **Default-Params** (inner==outer==1.5, Filter aus, roll==pitch) levelt v2 wie Stufe 2 —
die Beine reagieren beim Kippen genauso wie mit dem alten Regler.

```bash
# Terminal 4 — Leveling im horizontal-Modus scharf (Defaults sonst unveraendert):
ros2 param set /gait_node leveling_mode    horizontal
ros2 param set /gait_node leveling_enable  true
```

**Prüfen (aufgebockt, gentle):**
- Roboter **sanft** ~5° kippen und halten → **die Beine wandern mit** (kompensieren), wie mit v1.
- Geradestellen → Beine gehen zurück. **Kein** neues Zittern/Aufschwingen ggü. früher.
- `leveling_enable false` → Beine reagieren nicht mehr (Gegenprobe). Dann wieder `true`.
```bash
ros2 param set /gait_node leveling_enable false
ros2 param set /gait_node leveling_enable true
```

---

## Test 7.10b — Hysterese killt das Pendeln (der eigentliche Beweis)

**Ziel:** das Pendeln aus IP3.2 (`pitch` schwingt an der Totband-Kante ~2° hin und her) verschwindet mit
der Zwei-Fenster-Hysterese.

**Schritt 1 — Pendeln REPRODUZIEREN** (Single-Fenster = altes Verhalten, inner==outer==2.0):
```bash
ros2 param set /gait_node leveling_deadband_inner_deg_pitch 2.0
ros2 param set /gait_node leveling_deadband_outer_deg_pitch 2.0
ros2 param set /gait_node leveling_deadband_inner_deg_roll  2.0
ros2 param set /gait_node leveling_deadband_outer_deg_roll  2.0
# (kp hoch wie in IP3.2, damit der Effekt deutlich ist)
ros2 param set /gait_node leveling_kp_pitch 1.3
ros2 param set /gait_node leveling_kp_roll  1.3
```
→ sanft kippen, sodass `pitch` sich um ~2° einpendelt (Terminal 3) → **beobachte das Hin-und-Her**
an der Kante (das ist der Bug).

**Schritt 2 — Hysterese AN** (innen 1.0 < außen 2.0):
```bash
ros2 param set /gait_node leveling_deadband_inner_deg_pitch 1.0
ros2 param set /gait_node leveling_deadband_outer_deg_pitch 2.0
ros2 param set /gait_node leveling_deadband_inner_deg_roll  1.0
ros2 param set /gait_node leveling_deadband_outer_deg_roll  2.0
```
→ gleiche Kipp-Bewegung → **erwartet:** `pitch` fährt bis ~1° runter und **hält ruhig** — **kein
Pendeln** mehr an der Kante. Das ist der Stufe-7-Beweis.

> Reagiert es zu träge/schnell → `leveling_kd_*` (Dämpfung) bzw. `leveling_slew_max_dps_*` nachziehen;
> die guten Werte notieren → gehen später in `hw_balance.yaml` (6c-auf-v2).

---

## Test 7.10c — per-Achse getrennt + Validierung

**Ziel:** roll und pitch sind **unabhängig** einstellbar; ungültige Fenster/Filter werden abgelehnt.

```bash
# per-Achse: roll kraeftig/schnell, pitch sanft -> unterschiedliche Reaktion:
ros2 param set /gait_node leveling_kp_roll  1.3
ros2 param set /gait_node leveling_kp_pitch 0.4
```
→ Roboter mal in **roll** (seitlich), mal in **pitch** (vorn/hinten) kippen → roll reagiert spürbar
kräftiger/schneller als pitch (per-Achse wirkt).

```bash
# Validierung greift (beide muessen "Set parameter failed" bringen):
ros2 param set /gait_node leveling_deadband_inner_deg_roll 3.0   # inner > outer(2.0) -> REJECT
ros2 param set /gait_node leveling_tau_slow_s_pitch -0.1         # tau < 0 -> REJECT
```
→ erwartet: beide `Set parameter failed`, Node läuft weiter.

```bash
# Leveling aus + Shutdown:
ros2 param set /gait_node leveling_enable false
# Terminal 2 Strg+C (gait), dann Terminal 1 Strg+C (real)
```

---

## Feintuning — was jeder Parameter bewirkt (kleiner ↔ größer)

Alle per Achse (`_roll` / `_pitch`) live; die Start-Werte oben sind nur Ausprobier-Punkte.

| Param | Wert **kleiner** | Wert **größer** | Kopplung / Hinweis |
|---|---|---|---|
| `leveling_kp` (0.4) | schwächere/langsamere Rückstellung; bleibt eher schief | kräftiger/schneller, aber **Überschwingen → Pendeln** | Antrieb (P); braucht `kd` als Bremse |
| `leveling_ki` (0.1) | Rest-Schräge bleibt länger, dafür stabiler | drückt Rest-Schräge schneller raus, aber **träges Nachpendeln** | langsam-aufintegrierend; zu hoch = Wind-up-Schwingen |
| `leveling_kd` (0.03) | **weniger Dämpfung → Pendeln bleibt/steigt** | dämpft das Pendeln, ABER ab zu hoch **Summen/Zittern** | **Haupthebel gegen Pendeln**; D rauscht auf HW → konservativ |
| `leveling_deadband_inner_deg` (stop) | levelt **genauer** (näher 0°), regelt länger | hört **früher** auf → gröbere Rest-Schräge im Hold | „stop"-Schwelle; **muss < outer** |
| `leveling_deadband_outer_deg` (start) | startet **früher** zu regeln (empfindlicher) | startet **später** (träger, toleriert mehr Schräge bis Eingriff) | „start"-Schwelle; **muss > inner** |
| *Hysterese-Breite* (`outer − inner`) | kleiner → weniger Anti-Chatter (Richtung Single-Totband) | größer → **stärker gegen Pendeln/Chatter**, aber mehr „Totzone" (Lage darf mehr driften) | der eigentliche Stufe-7-Hebel |
| `leveling_slew_max_dps` (8) | sanft/langsam nachführen (ruckfrei), aber träge | schneller, aber ruckiger; lässt Oszillation schneller durch | Tempo-Limit; begrenzt auch, wie schnell `kd` wirkt |
| `leveling_tau_fast_s` (0) | 0 = „stop"-Entscheidung sofort (reagiert auf Rauschen) | größer → „stop" träger/glatter | nur **horizontal**-Eingang; entscheidet, *wann aufgehört* wird |
| `leveling_tau_slow_s` (0) | 0 = Dual-Tiefpass **aus** | größer → „resume" träger → ignoriert Transiente/Ripple mehr, reagiert aber **später auf echte Drift** | **Wertträger** des Filters; nur horizontal-Eingang (terrain = bypass) |
| `leveling_max_angle_deg` (10) | kappt Korrektur früher (weniger Schräge ausgeregelt) | **NICHT erhöhen** ohne `leveling_envelope_check` | harter Clamp (gemeinsam), kein Tuning-Knopf |

> **Gegen Pendeln (in dieser Reihenfolge, immer nur EINE Schraube):** (1) `leveling_kd_*` **hoch** bis
> knapp vors Summen. (2) reicht's nicht → `leveling_kp_*` (und/oder `ki`) **runter** (weniger treiben).
> (3) `leveling_slew_max_dps_*` **runter** (langsamer). (4) zappelt's eng um die Nulllage → Hysterese-
> Breite vergrößern (`inner` runter **oder** `outer` hoch). (5) Rausch/Ripple → `leveling_tau_slow_s_*`
> **> 0** (nur horizontal-Modus). Faustregel: erst dämpfen (kd↑), dann Antrieb zähmen (kp/ki↓).

> **Per-Achse-Faustregel:** der Roboter ist seitlich **schmal** → **Roll** kippt früher/sensibler.
> Tendenz: `_roll`-Fenster **enger** / `kp_roll` **höher** als pitch, und `tip_angle_*_roll` **kleiner**.

## Ergebnis (→ Progress-File 7.10)

7.10a (kein Regress) + 7.10b (Hysterese killt Pendeln) + 7.10c (per-Achse + Validierung) sauber →
**Stufe 7 🟢 komplett**, `imu_balance_progress.md` Bullet 7.10 abhaken. **User committet selbst.**
Danach nahtlos **6c/IP3 = HW-Gain-Tuning auf v2** (die guten Werte in `hw_balance.yaml` per-Achse
nachziehen; Terrain-Following-Lauf am Boden = IP3.3-auf-v2).

## Was NICHT hier (→ 6c-auf-v2 / später)
- **Terrain-Following im Laufen** (terrain-Modus am Boden, Hang folgen) — braucht Boden, = IP3.3-auf-v2.
- **Dual-Tiefpass-Tuning** (tau_slow>0 gegen Rausch/Ripple) — auf HW im Lauf.
- **Adaptiver Slope-Schätzer** (Knick) / **state-abhängige Fenster** — deferred (D1/D3).
