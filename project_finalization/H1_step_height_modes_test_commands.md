# H1 — Test-Befehle: Schritthöhen-Modi (Sim-Smoke + HW-Apex-Messung)

> **Copy-paste-fertig.** Stand nach H1.3: die `_STANCE_MODES`-Tabelle trägt per-Modus-Schritthöhen
> (**tief 0.04 / mittel 0.05 / hoch 0.08**, Einheits-Radius 0.160), der L2/R2-Switch setzt sie
> automatisch, manuelles Überschreiten wird rejected. Offline-Gate + Transitions sind grün
> (440 gait / 43 kin Tests). Hier: **H1.4** Sim-Smoke → **H1.5** HW-Apex-Messung (aufgebockt) →
> **H1.6** HW Boden. Plan/Datenlage: [`H1_step_height_modes_plan.md`](H1_step_height_modes_plan.md).

## Was sich im Alltag ändert

- **Boot/mittel:** Schritthöhe jetzt **0.05** statt 0.04 (+1 cm Default-Gangbild).
- **hoch (R2):** Schritthöhe **0.08** — der Terrain-Modus (2× alter Hub kommandiert).
- `ros2 param set /gait_node step_height X` mit X über dem Modus-Deckel → `Set parameter failed`
  (gewollt — das war die IKError+Freeze-Falle).

## IMU + Fußtaster in diesen Tests

- **Taster-Topics laufen immer mit** (`publish_foot_contacts` default an) — harmlos.
- **H1.4/H1.5: S4-Enables + Leveling bewusst AUS** (Defaults). Grund (H1.5): aufgebockt gibt es
  keinen Bodenkontakt → der adaptive Touchdown würde jeden Stance-Fuß bis zum Probe-Floor senken
  → `apex_meter` mäße `step_height + 0.03` statt `step_height` — **Messung unbrauchbar**.
- **H1.6 (Boden): volles `hw_terrain.yaml`** (IMU + `auto`-Leveling + adaptiver Touchdown +
  Slip-Schutz + Adaptive Stand) — der Alltags-Zustand; am Boden ankert der Kontakt den Fuß bei
  `body_height`, die Messung bleibt aussagekräftig.

---

# Schritt 0 — Einmalig: bauen (Desktop) + Code auf den Pi holen + bauen (Pi)

**0a — Desktop bauen + Tests (nach jedem Code-Stand):**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_kinematics && colcon test-result --test-result-base build/hexapod_gait
# Erwartung: 440 gait / 43 kin, 0 failures. Tool-Tests separat:
python3 -m pytest tools/test_walking_envelope_check.py -q     # 18 passed
```

**0b — Pi: aktuellen Branch-Stand holen + lokalen Stand HART ersetzen** (auf dem Pi; Voraussetzung:
Desktop-Stand ist committet + gepusht — Git machst du):
```bash
cd ~/hexapod_ws
git fetch origin
git checkout -B imu_balance origin/imu_balance   # Branch anlegen/auf origin-Stand wechseln
git reset --hard origin/imu_balance              # lokalen Stand hart durch den gepushten ersetzen
git status                                        # erwartet: "up to date" + working tree clean
```
> ⚠️ `git reset --hard` **verwirft lokale, ungespeicherte Pi-Änderungen** — nur nutzen, wenn der
> Pi reiner Ziel-Klon ist (kein Pi-seitiges Editieren; ist bei uns der Fall). `COLCON_IGNORE` in
> `hexapod_gazebo` ist erwartet (kein Git-Tracking) und bleibt liegen.

**0c — Pi bauen + sourcen:**
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build            # voll (hexapod_gazebo wird am Pi per COLCON_IGNORE übersprungen);
                        # nur-hexapod_gait-Änderung: colcon build --packages-select hexapod_gait
source install/setup.bash
ros2 param describe /gait_node step_height 2>/dev/null || true   # (nur bei laufendem Node)
# Schneller Build-Stand-Check ohne laufenden Node:
python3 -c "from hexapod_gait.gait_node import _STANCE_MODES; print(_STANCE_MODES)"
# Erwartung: ... step_height=0.04 / 0.05 / 0.08 -> H1-Stand ist drauf.
```

---

# H1.4 — Sim-Smoke (Desktop) — Welt frei wählbar

**Terminal 1 — EINE Welt aussuchen** (alle spawnen flach, IMU-Welt inklusive):

```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash

# A) Leere Welt (der Basis-Smoke):
ros2 launch hexapod_bringup sim.launch.py

# B) Stufe (Hindernis; step_drop: + = Stufe ABwärts, − = AUFwärts — für die neuen
#    Schritthöhen interessant: −0.02/−0.04 = 2/4 cm HOCHsteigen):
ros2 launch hexapod_bringup step.launch.py step_drop:=-0.04

# C) Graben (fußbreiter Spalt — die klare per-Fuß-Reach-Demo):
ros2 launch hexapod_bringup trench.launch.py            # trench_width/trench_depth optional

# D) Rampe (flach → Hang → Plateau; zum Hineinlaufen):
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0

# E) Rubicon (unebenes Gelände; Fuel-Welt einmalig cachen falls nötig:
#    gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"):
ros2 launch hexapod_bringup rubicon.launch.py            # spawn_x:=5 = rauere Stelle
```

> **Ein-Befehl-Alternativen** (Sim + Gait zusammen, Terminal 2 entfällt):
> `step_walk.launch.py step_drop:=-0.04` bzw. `trench_walk.launch.py` — Args wie oben,
> `leveling_enable` default false. ⚠️ **`ramp_walk.launch.py` NICHT verwenden** — bekannte
> Standup-Regression (steht joint-space statt kartesisch auf, Füße schleifen;
> [[project_ramp_walk_standup_joint_space_regression]]) → für die Rampe D) + Terminal 2 nehmen.

```bash
# ── Terminal 2: Gait (steht automatisch auf, Boot = mittel @ sh 0.05) ──
#    (entfällt bei den *_walk-Ein-Befehl-Varianten)
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py
```

> **Für die Terrain-Welten B/C/E lohnt S4 dazu** (die neuen Schritthöhen + adaptiver
> Touchdown sind das Alltags-Duo; Enables live, Terminal 4):
> ```bash
> ros2 daemon stop
> ros2 param set /gait_node adaptive_touchdown_enable true
> ros2 param set /gait_node adaptive_stand_enable true      # Rubicon: Füße setzen im Stand auf
> ```
```bash
# ── Terminal 3: Teleop ──
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb   # oder ps4_bt
```
```bash
# ── Terminal 4: Sanity + Deckel-Probe ──
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param get /gait_node step_height          # Double value is: 0.05  (neuer Boot-Default)
ros2 param set /gait_node step_height 0.08     # ERWARTET: Set parameter failed (mittel-Deckel 0.05)
ros2 param set /gait_node step_height 0.03     # ok (kleiner immer erlaubt)
ros2 param set /gait_node step_height 0.05     # ok (zurück auf Modus-Wert)
```

**Ablauf:** je Modus (R2 = höher, L2 = tiefer, im Stand) laufen — geradeaus, seitwärts, drehen,
Übergänge im Stand durchschalten (tief↔mittel↔hoch).
**✅ Erwartung:** kein IKError im Terminal-2-Log, sichtbar höherer Schwung in mittel/hoch,
Übergänge sauber (Tripod-Reposition), im hoch-Modus deutlich sichtbarer 8-cm-Bogen.

---

# H1.5 — HW aufgebockt: Apex-Messung (wie viel Hub kommt real an?)

**Bringup wie gehabt** (3-Terminal-Muster, aufgebockt, Kill-Switch):
```bash
# ── Terminal 1 (Pi): Servo-Stack ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false \
    robot_description_file:="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): DER MESS-SCHRITT — apex_meter (Report alle 2 s) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
python3 tools/apex_meter.py
#   Ausgabe: hub[mm] L1  48.3 | L2  47.9 | ...  = real erreichter Hub je Bein
#   (max−min der FK-Fußhöhe über 10-s-Fenster; beim Laufen ≈ Apex über Stance)
```

**Ablauf:** je Modus (L2/R2 im Stand durchschalten) ~30 s aufgebockt laufen und die
`hub[mm]`-Zeile ablesen; Werte in die Progress-Tabelle (H1.5) eintragen:

| Modus | kommandiert | hub[mm] gemessen ✍️ | Verlust ✍️ |
|---|---|---|---|
| tief | 40 | | |
| mittel | 50 | | |
| hoch | 80 | | |

**Optional — Lag-Anteil isolieren:** langsamer laufen lassen und erneut messen:
```bash
ros2 daemon stop
ros2 param set /gait_node cycle_time 3.0     # nur im Stand setzbar (standing_only)
```
| Param (Default) | Wert kleiner | Wert größer | Woran du es erkennst |
|---|---|---|---|
| `cycle_time` (2.0) | schnellerer Gang → mehr Servo-Lag → **weniger** realer Hub | langsamer → Servo trackt besser → Hub näher am kommandierten Wert | hub[mm] bei 3.0 deutlich > bei 2.0 ⇒ Verlust war v. a. Lag. Bleibt er gleich ⇒ Einfedern der Stützbeine (open-loop nicht behebbar, aufgebockt aber ≈ 0) |

> Aufgebockt tragen die Beine nichts → der gemessene Verlust ist der reine **Servo-Lag**.
> Der Einfeder-Anteil kommt erst am Boden dazu (H1.6, gleiche Messung dort wiederholen).

---

# H1.6 — HW Boden: alle 3 Modi + Klein-Terrain (volles Alltags-Setup)

**Roboter am Boden**, freie Fläche, Kill-Switch. Jetzt mit **IMU + Tastern + allen Regelkreisen**
(`hw_terrain.yaml`: `auto`-Leveling + adaptiver Touchdown + Slip-Schutz + Adaptive Stand) — der
Zustand, in dem die neuen Schritthöhen im Alltag laufen. Der neue mittel-Default 0.05 + hoch 0.08
gelten automatisch (das Preset setzt `step_height` nicht; Deckel + Switch-Kopplung kommen aus
der Tabelle).

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait + Komplett-Preset (steht automatisch auf, alles aktiv) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false \
    robot_description_file:="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro" \
    params_file:="$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/hw_terrain.yaml"
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): apex_meter weiterlaufen lassen (Boden-Messung = Lag + Einfedern) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
python3 tools/apex_meter.py
```

**Ablauf:**
1. Je Modus 1–2 Bahnen geradeaus + Kurve: stabil, kein IKError, kein `OVERCURRENT` (Terminal 1),
   `hub[mm]` notieren (Vergleich zu H1.5 = Einfeder-Anteil; kleine Abweichungen durch S4/Leveling
   sind am Boden normal — der Kontakt ankert den Fuß bei `body_height`).
2. **hoch-Modus über dein Klein-Terrain** (Steinchen/1–2-cm-Hindernisse): steigt sichtbar drüber,
   wo er in mittel/tief hängen blieb; der adaptive Touchdown fängt die Lande-Unebenheiten.

**Melde-Format (knapp):** je Modus stabil j/n · hub[mm] H1.5 (aufgebockt) vs. H1.6 (Boden) ·
hoch über Terrain j/n · Auffälligkeiten (Strom/Wackeln).

---

## Was NICHT getestet wird (scope-out)

- **Tempo-Presets** (cycle/step_length-Stufen + Scales) → Block **H2** (braucht per-Zelle
  validierte max-Schrittweite — 0.12 ist NUR in mittel @ sh ≤ 0.05 valide, H1.2-Befund!).
- **Nicht-Tripod-Gangarten** mit den neuen Schritthöhen → zweite Runde nach H1.
- **9/10 cm Hub** — datenbasiert verworfen (Apex-Marge bzw. S4-Floor-Reach, Plan §0).
