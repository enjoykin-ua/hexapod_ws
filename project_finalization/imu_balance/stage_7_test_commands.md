# Stufe 7 — Test-Befehle: Balance-Regler v2 auf HW (7.10)

> **Copy-paste-fertig.** Jeder Test enthält **alle** Terminals/Befehle. Zwei Teile:
> **TEIL A — Stehen** (Standing-Leveling, `horizontal`): (a) Default = kein Regress, (b) Hysterese
> killt das Pendeln aus IP3.2, (c) per-Achse + Validierung. **✅ HW-verifiziert** (Kipp-Platte).
> **TEIL B — Laufen** (Terrain-Following, `terrain`, **am Boden**): (d) flach stabil (Gyro-D dämpft),
> Hang folgen ohne Aufschwingen, Grenz-Hang notieren. Plan:
> [`stage_7_balance_controller_v2_plan.md`](stage_7_balance_controller_v2_plan.md).
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

**0a — Stufe-7-Code auf den Pi holen + bauen** (auf dem Pi). Voraussetzung: der Stufe-7-Stand ist
auf dem Dev **committet + gepusht** (Git machst du). Workflow-Referenz:
[`../../docs_raspi/dev_workflow_desktop_to_pi.md`](../../docs_raspi/dev_workflow_desktop_to_pi.md).
```bash
# --- Pi: aktuellen Branch-Stand holen + lokalen Stand HART ersetzen ---
cd ~/hexapod_ws
git fetch origin
git checkout -B imu_balance origin/imu_balance   # Branch anlegen/auf origin-Stand wechseln
git reset --hard origin/imu_balance              # lokalen Stand hart durch den gepushten ersetzen
git status                                        # erwartet: "up to date" + working tree clean
```
> ⚠️ `git reset --hard` **verwirft lokale, ungespeicherte Pi-Änderungen** — nur nutzen, wenn der Pi
> reiner Ziel-Klon ist (kein Pi-seitiges Editieren). `COLCON_IGNORE` in `hexapod_gazebo` ist erwartet
> (kein Git-Tracking) und bleibt.
```bash
# --- Pi: bauen + sourcen ---
source /opt/ros/jazzy/setup.bash
# Erstes Mal / nach frischem Reset: GANZEN Workspace bauen (sonst fehlt z.B. hexapod.imu.xacro
# im installierten hexapod_description und real.launch.py bricht beim xacro ab):
colcon build            # hexapod_gazebo wird per COLCON_IGNORE auf dem Pi uebersprungen
# (Nur wenn du SICHER weisst, dass sich seit dem letzten Voll-Build nur hexapod_gait aenderte,
#  reicht das Teil-Build:  colcon build --packages-select hexapod_gait)
source install/setup.bash
```
> Bei „No such file … hexapod.imu.xacro" o. ä. → es fehlt ein Paket-Build: `colcon build` (voll) bzw.
> `colcon build --packages-select hexapod_description` nachziehen.

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
# ── Terminal 4 (Pi): TUNING-Terminal — hier tippst du ALLE `ros2 param set`-Befehle der Tests ein ──
#    (Live-Tuning der Regler-Werte ohne Node-Neustart). Vorab EIN Funktions-Check, dass wirklich der
#    Stufe-7-Build laeuft (sonst verstellst du Werte "ins Leere"):
cd ~/hexapod_ws && source install/setup.bash
ros2 param get /gait_node leveling_kp_roll
#    Erwartung: "Double value is: 0.4"  -> gait_node laeuft + die NEUEN per-Achse-Params (v2) sind da.
#    Fehler / "not set" / "node not found" -> alter/falscher Build oder Node nicht hochgekommen: erst fixen.
```
> Weitere Sanity-Checks: `ros2 node list` zeigt `/gait_node`, `/bno055_imu`, `/imu_monitor`;
> `ros2 topic hz /imu/data` ~50 Hz.

---

## Param-Referenz — alle Stellhebel mit Defaults (copy-paste, getrennt roll/pitch)

> **Zweck:** (1) schnell auf Defaults **zurücksetzen**, (2) Nachschlagen welche Params es gibt. Für den
> **Steh-Test** zusätzlich `leveling_mode horizontal` (unten bei „Gemeinsam"). Wirkung je Param →
> Feintuning-Tabelle unten.

**ROLL — Neigung links/rechts (seitlich kippen) — Defaults:**
```bash
ros2 param set /gait_node leveling_kp_roll                 0.4
ros2 param set /gait_node leveling_ki_roll                 0.1
ros2 param set /gait_node leveling_kd_roll                 0.03
ros2 param set /gait_node leveling_deadband_inner_deg_roll 1.5
ros2 param set /gait_node leveling_deadband_outer_deg_roll 1.5
ros2 param set /gait_node leveling_slew_max_dps_roll       8.0
ros2 param set /gait_node leveling_tau_fast_s_roll         0.0
ros2 param set /gait_node leveling_tau_slow_s_roll         0.0
ros2 param set /gait_node tip_angle_warn_deg_roll          15.0
ros2 param set /gait_node tip_angle_crit_deg_roll          25.0
```

**PITCH — Neigung Nase vor/zurück (vorn/hinten kippen) — Defaults:**
```bash
ros2 param set /gait_node leveling_kp_pitch                 0.4
ros2 param set /gait_node leveling_ki_pitch                 0.1
ros2 param set /gait_node leveling_kd_pitch                 0.03
ros2 param set /gait_node leveling_deadband_inner_deg_pitch 1.5
ros2 param set /gait_node leveling_deadband_outer_deg_pitch 1.5
ros2 param set /gait_node leveling_slew_max_dps_pitch       8.0
ros2 param set /gait_node leveling_tau_fast_s_pitch         0.0
ros2 param set /gait_node leveling_tau_slow_s_pitch         0.0
ros2 param set /gait_node tip_angle_warn_deg_pitch          15.0
ros2 param set /gait_node tip_angle_crit_deg_pitch          25.0
```

**Gemeinsam (nicht per-Achse) + An/Aus:**
```bash
ros2 param set /gait_node leveling_mode                  horizontal   # STEHEN: horizontal | (Laufen: terrain)
ros2 param set /gait_node leveling_max_angle_deg         10.0         # STANDING-Clamp (nicht ohne Envelope-Check hoch)
ros2 param set /gait_node leveling_max_angle_walking_deg 4.0          # WALKING-Clamp
ros2 param set /gait_node leveling_startup_grace         true
ros2 param set /gait_node tip_detection_enable           true
ros2 param set /gait_node tip_rate_crit_dps              80.0         # Kipprate-CRIT (gemeinsam)
ros2 param set /gait_node tip_debounce_ticks             5            # Entprellung (gemeinsam)
ros2 param set /gait_node leveling_enable                true         # zuletzt scharf (Leveling AN)
```
> **Alle aktuellen Werte auf einmal ansehen:** `ros2 param dump /gait_node | grep -E "leveling_|tip_"`.

---

# TEIL A — Stehen (Standing-Leveling, `horizontal`-Modus)  ✅ HW-verifiziert

> Roboter **steht** (aufgebockt ODER auf einer von Hand kippbaren Platte am Boden). Du kippst, der
> Körper (bzw. aufgebockt die Beine) levelt zurück.

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

# TEIL B — Laufen (Terrain-Following, `terrain`-Modus, am Boden)

> **WO:** Roboter **auf dem Boden** (nicht aufgebockt/nicht auf der Kipp-Platte) — er trägt sein Gewicht
> und läuft. Freie, **ebene Lauf-Fläche ≥ ~1,5 m gerade**; für den Hang-Teil zusätzlich eine **flache,
> feste Rampe/schiefe Ebene ~5–10°** (z. B. Brett unterlegt), breit genug zum Drauflaufen **in Falllinie**
> (geradeaus rauf — **nicht quer**, Quer-Hang ist out-of-scope).
> **WANN:** **nach Teil A** (Stehen sauber = erledigt) **und** nachdem der Roboter am Boden überhaupt
> **stabil geradeaus läuft** (das prüft 7.10d-0 zuerst).
> **SICHERHEIT (§9):** langsam (`x=0.03 m/s`), **Kill-Switch in der Hand**, erst flach, dann Hang. Bei
> Aufschwingen/Ruck sofort `leveling_enable false` bzw. Strom trennen.

## Bringup Teil B (Roboter auf dem Boden)

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU (Roboter steht auf dem BODEN, Kill-Switch bereit!) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + Aufstehen + verifizierte Leveling-Konfig laden ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF" \
    params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/hw_balance.yaml
#   -> steht auf; laedt die HW-Konfig (kp1.3 / Hysterese 1.0-2.0). leveling_enable bleibt false (Preset).
```
```bash
# ── Terminal 3 (Pi): Hang-Schaetzung + Lage live ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /imu/slope     # [slope_roll_deg, slope_pitch_deg] -> geschaetzter Hang
#   (optional zweites Fenster: ros2 topic echo /imu/monitor = rohe Lage roll/pitch [rad])
```
```bash
# ── Terminal 4 (Pi): terrain-Modus + fahren/tunen ──
cd ~/hexapod_ws && source install/setup.bash
ros2 param get /gait_node leveling_kp_roll     # 1.3 -> Preset geladen, Node lebt
```

## 7.10d-0 — Lauf-Smoke OHNE Leveling (Safety-Gate, ZUERST)

**Zweck:** sicherstellen, dass der Roboter am Boden **überhaupt stabil geradeaus läuft**, bevor Leveling
dazukommt. Läuft er hier nicht sauber → **separates** Problem (Gang/Traktion/Strom), NICHT Stufe 7.
```bash
ros2 param set /gait_node leveling_enable false
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
```
**Prüfen:** läuft geradeaus, kein Umkippen/Wegdriften, Terminal 1 kein `OVERCURRENT`. Dann stoppen:
```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
```
> Läuft er **nicht** stabil → hier stoppen, Gang/Boden separat klären (nicht mit Leveling überdecken).

## 7.10d-1 — Flach + Leveling (terrain): Gyro-D dämpft, kein Aufschwingen

```bash
ros2 param set /gait_node leveling_mode   terrain
ros2 param set /gait_node leveling_enable true
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
```
**Prüfen:**
- Flach: Körper bleibt ruhig, **kein Aufschwingen/Aufschaukeln**. A/B: `leveling_enable false` → Wackeln
  nimmt zu; `true` → ruhiger (Gyro-D wirkt).
- **Falls es aufschwingt** (Ausschlag wächst) → sofort stoppen und Dämpfung hoch / Kd sind schon 0.03:
  ```bash
  ros2 param set /gait_node leveling_kd_pitch 0.05
  ros2 param set /gait_node leveling_kd_roll  0.05
  ```
```bash
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
```

## 7.10d-2 — Hang folgen (geradeaus rauf) + Grenz-Hang

```bash
# Terminal 3 offen (/imu/slope). Terminal 4: langsam in Falllinie die Rampe hochfahren:
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'
```
**Prüfen (Terminal 3 `/imu/slope` + Blick auf den Roboter):**
- Beim Auffahren: `/imu/slope` pitch geht Richtung Rampenwinkel; der **Körper folgt dem Hang**
  (hangparallel) statt dagegen zu kämpfen — **kein Ruck am Knick**, kein Aufschwingen.
- roll bleibt ~0 (Geradeaus-Klettern). Quer-Hang **nicht** testen (out-of-scope, TF-Quer).
- **Grenz-Hang notieren:** ab welchem Rampenwinkel wird's unsauber (Wackeln/Hängen an der Kante)?
- **Tuning bei Bedarf:**
  ```bash
  ros2 param set /gait_node slope_estimate_tau_s 0.8   # zappelige Hang-Schaetzung glaetten (Default 0.5)
  ros2 param set /gait_node leveling_kd_pitch     0.04 # Daempfung; hoch = ruhiger, zu hoch = Zittern
  ```
```bash
# stoppen + Leveling aus + Shutdown:
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
ros2 param set /gait_node leveling_enable false
# Terminal 2 Strg+C, Terminal 1 Strg+C
```

> **Gute terrain-Werte notieren** (Gyro-`kd`, `slope_estimate_tau_s`, Grenz-Hang) → in `hw_balance.yaml`
> (terrain-Teil) nachtragen; dann ist die Konfig für **Stehen + Laufen** vollständig.

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

## Ergebnis (→ Progress-File)

- **TEIL A (Stehen):** 7.10a/b/c ✅ **HW-verifiziert** — Bullet 7.10 abgehakt, Konfig in `hw_balance.yaml`.
- **TEIL B (Laufen):** 7.10d-0 (Lauf-Smoke) + 7.10d-1 (flach stabil) + 7.10d-2 (Hang folgen, Grenz-Hang)
  sauber → **IMU-Balance auf v2 vollständig HW-verifiziert** (Stehen + Laufen). Gute terrain-Werte in
  `hw_balance.yaml` nachtragen. **User committet selbst.**

## Was NICHT hier (→ später)
- **Kombi S4 (Fußtaster) + Leveling** — eigener bestromter Integrationstest.
- **Quer-/Diagonal-Hang** (`TF-Quer`), **adaptiver Slope-Schätzer** (Knick, D1), **state-abhängige
  Fenster** (D3) — deferred.
