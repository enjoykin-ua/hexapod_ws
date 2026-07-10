# H2 — Test-Befehle: Tempo-Presets + Schrittweiten-Deckel (Sim-Tuning + HW)

> **Copy-paste-fertig.** Stand nach H2.4: `_STANCE_MODES` trägt per-Modus `step_length_max`
> (**tief 0.06 / mittel 0.08 / hoch 0.05** — ⚠️ 0.09 fiel im H2.1-engine-check, siehe
> [`H2_speed_presets_progress.md`](H2_speed_presets_progress.md)), D-Pad ↑/↓ cyclet die
> **Tempo-Presets** (`_TEMPO_MODES` in `joy_to_twist.py`: langsam 3.3 / mittel 2.6 /
> **schnell 2.0 = Boot** / aggressiv 1.5), Suite 449 gait / 43 kin / 53 teleop grün.
> Hier: **H2.5** Sim durchschalten + Werte-Tuning → **H2.6** HW (aggressiv-Realitäts-Check).
> Plan: [`H2_speed_presets_plan.md`](H2_speed_presets_plan.md).

## Was sich im Alltag ändert

- **D-Pad ↑/↓ = Tempo** (schneller/langsamer), NICHT mehr Schrittweite. ←/→ bleibt Gangart.
- **Tempo-Wechsel nur im Stand** (gait-Guard auf `cycle_time`) — im Lauf: R1 loslassen,
  anhalten lassen, dann D-Pad. Log im Teleop: `Tempo -> <name> …` bzw. `Tempo nur im Stand …`.
- **Boot = „schnell"** (cycle 2.0 + bisherige Scales) → ohne D-Pad-Druck fährt alles wie bisher.
- `step_length_max` ist jetzt **pro Stance-Modus gedeckelt** (Reject über Deckel) und wird vom
  L2/R2-Stance-Switch mitgesetzt; `ros2 param get` zeigt nach dem Switch die echten Modus-Werte
  (neuer deferred Param-Sync).
- Der Service `/hexapod_adjust_step_length` existiert weiter (ohne Controller-Taste), clampt
  zusätzlich auf den Modus-Deckel.

## IMU + Fußtaster in diesen Tests

- **H2.5 (Sim): S4 + Leveling AUS lassen** (Defaults) — getunt wird das nackte Tempo-Gefühl;
  die Envelope ist tempo-unabhängig bewiesen, Regelkreise verfälschen nur den Eindruck.
- **H2.6 (HW Boden): volles `hw_terrain.yaml`** — der Alltags-Zustand. `hw_terrain.yaml`
  braucht KEINEN Tempo-Eintrag (Boot = schnell = heutiges Verhalten, per Design sprungfrei).

---

# Schritt 0 — Einmalig: bauen + Tests (Desktop; Pi analog H1-Doku Schritt 0b/0c)

```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop
source install/setup.bash
colcon test --packages-select hexapod_gait hexapod_kinematics hexapod_teleop && \
  colcon test-result --test-result-base build/hexapod_gait && \
  colcon test-result --test-result-base build/hexapod_teleop
# Erwartung: 449 gait / 43 kin / 53 teleop, 0 failures.
# Schneller Code-Stand-Check ohne laufenden Node:
python3 -c "from hexapod_gait.gait_node import _STANCE_MODES; print(_STANCE_MODES)"
# Erwartung: ... step_length_max=0.06 / 0.08 / 0.05  -> H2-Stand ist drauf.
python3 -c "from hexapod_teleop.joy_to_twist import _TEMPO_MODES; print(*_TEMPO_MODES, sep='\n')"
# Erwartung: langsam 3.3 / mittel 2.6 / schnell 2.0 / aggressiv 1.5 (+ Scales)
```

---

# H2.5 — Sim: Tempo-Stufen durchschalten + Werte-Tuning (Desktop)

**Terminal 1 — EINE Welt aussuchen** (alle spawnen flach; fürs reine Tempo-Gefühl reicht A,
für aggressiv-auf-Terrain-Eindruck lohnen B/C/E):

```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash

# A) Leere Welt (der Basis-Fall fürs Tempo-Tuning):
ros2 launch hexapod_bringup sim.launch.py

# B) Stufe (step_drop: + = Stufe ABwärts, − = AUFwärts; z. B. 2 cm hochsteigen):
ros2 launch hexapod_bringup step.launch.py step_drop:=-0.02

# C) Graben (fußbreiter Spalt — per-Fuß-Reach-Demo):
ros2 launch hexapod_bringup trench.launch.py            # trench_width/trench_depth optional

# D) Rampe (flach → Hang → Plateau; zum Hineinlaufen):
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0

# E) Rubicon (unebenes Gelände; Fuel-Welt einmalig cachen falls nötig:
#    gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"):
ros2 launch hexapod_bringup rubicon.launch.py            # spawn_x:=5 = rauere Stelle
```

> **Ein-Befehl-Alternativen** (Sim + Gait zusammen, Terminal 2 entfällt):
> `step_walk.launch.py step_drop:=-0.02` bzw. `trench_walk.launch.py` — Args wie oben,
> `leveling_enable` default false. ⚠️ **`ramp_walk.launch.py` NICHT verwenden** — bekannte
> Standup-Regression (steht joint-space statt kartesisch auf, Füße schleifen;
> [[project_ramp_walk_standup_joint_space_regression]]) → für die Rampe D) + Terminal 2 nehmen.
>
> Für die Terrain-Welten B/C/E lohnt S4 dazu (Enables live, Terminal 4):
> ```bash
> ros2 daemon stop
> ros2 param set /gait_node adaptive_touchdown_enable true
> ros2 param set /gait_node adaptive_stand_enable true      # Rubicon: Füße setzen im Stand auf
> ```
> (Fürs reine Tempo-**Tuning** H2.5b danach wieder aus bzw. Welt A nehmen — Regelkreise
> verfälschen das Tempo-Gefühl.)
```bash
# ── Terminal 2: Gait (steht automatisch auf, Boot = mittel-Stance @ Tempo "schnell") ──
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py
```
```bash
# ── Terminal 3: Teleop ──
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb   # oder ps4_bt
```

## H2.5a — Funktions-Durchlauf (vor dem Tuning)

**Ablauf:** im Stand D-Pad ↑ bis `aggressiv`, dann ↓ bis `langsam` (Teleop-Log je Druck:
`Tempo -> <name>`); je Stufe eine kurze Bahn (geradeaus + Kurve). Danach die Guards provozieren:

1. **Im Lauf** (R1 + Stick halten) D-Pad ↑ → Teleop-Log `Tempo nur im Stand — gait_node lehnt ab…`,
   Fahrverhalten ändert sich NICHT (kein halber Wechsel).
2. An den **Enden** weiterdrücken → `Tempo bereits am schnellsten/langsamsten (…)`, kein Request.
3. **Stance-Wechsel-Kopplung:** L2/R2 durchschalten und sl prüfen (Terminal 4).

```bash
# ── Terminal 4: Sanity + Deckel-Proben ──
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop      # gegen stale "Node not found" bei ros2 param
ros2 param get /gait_node cycle_time            # folgt dem D-Pad-Tempo (2.0 Boot)
ros2 param get /joy_to_twist linear_x_scale     # folgt dem D-Pad-Tempo (0.05 Boot)
ros2 param get /gait_node step_length_max       # Double value is: 0.08  (Boot = mittel)
ros2 param set /gait_node step_length_max 0.09  # ERWARTET: Set parameter failed (mittel-Deckel 0.08)
ros2 param set /gait_node step_length_max 0.05  # ok (kleiner immer erlaubt)
ros2 param set /gait_node step_length_max 0.08  # ok (zurück auf Modus-Wert)
# Stance-Kopplung + deferred Param-Sync (R2 im Stand = hoch, kurz warten bis Reposition fertig):
ros2 param get /gait_node step_length_max       # nach Switch hoch: 0.05
ros2 param get /gait_node body_height           # nach Switch hoch: -0.1 (Sync-Beleg, H1-🟡-Fix)
```

**✅ Erwartung H2.5a:** alle 4 Stufen fahrbar, kein IKError (Terminal 2), sichtbare Tempo-Sprünge
pro Stufe, Guards greifen (Lauf-Reject + Klemmen), sl/body_height folgen dem Stance-Switch auch
im `ros2 param get`.

## H2.5b — Werte-TUNING (du fährst, verstellst live, meldest finale Werte)

Pro Stufe: D-Pad auf die Stufe, fahren, dann **live nachstellen** bis es sich richtig anfühlt —
`cycle_time` am gait_node (nur im Stand!), Scales am Teleop (sofort wirksam):

```bash
# Tempo-Charakter (im STAND setzen):
ros2 param set /gait_node cycle_time 1.8
# cmd-Limits (live, wirken sofort — Reihenfolge egal):
ros2 param set /joy_to_twist linear_x_scale 0.06
ros2 param set /joy_to_twist linear_y_scale 0.05
ros2 param set /joy_to_twist angular_z_scale 0.55
```

| Param (Boot-Default) | Wert kleiner | Wert größer | Woran du es erkennst |
|---|---|---|---|
| `cycle_time` (2.0, standing_only) | hektischer Takt, mehr Servo-Lag-Risiko (HW) | gemächlicher Takt, Füße tracken sauberer | Schrittfrequenz; bei zu klein wirken Schwünge „abgehackt" |
| `linear_x_scale` (0.05) | Voll-Stick fährt langsamer vor/zurück | schneller — bis `linear_max = sl/stance` clampt | Vorwärts-Speed am Voll-Stick; Clamp = `cmd_vel clamped`-WARN in Terminal 2 |
| `linear_y_scale` (0.05) | seitwärts langsamer | seitwärts schneller (Clamp wie oben) | Sidestep-Speed |
| `angular_z_scale` (0.46) | Drehen träger | Drehen giftiger | Dreh-Rate am Voll-Stick |

> ⚠️ **D-Pad-Druck überschreibt dein Live-Tuning** mit den Tabellenwerten der Ziel-Stufe —
> erst Werte notieren, dann weiterschalten. `cycle_time` manuell zu setzen verstellt den
> Tempo-Index NICHT (die Tabelle greift erst beim nächsten D-Pad-Druck).

**Melde-Format (knapp), je Stufe:** `<name>: cycle=<x> scales=<x>/<y>/<z>` — ich trage sie in
`_TEMPO_MODES` + die Progress-Tabelle ein und lasse die Suiten neu laufen (Tabellen-Pin-Test
ändert sich mit).

| Stufe | cycle_time Start | Scales Start (x/y/z) | final ✍️ |
|---|---|---|---|
| aggressiv | 1.5 | 0.17 / 0.13 / 1.2 | |
| schnell (Boot) | 2.0 | 0.05 / 0.05 / 0.46 | |
| mittel | 2.6 | 0.04 / 0.04 / 0.35 | |
| langsam | 3.3 | 0.03 / 0.03 / 0.28 | |

> Hinweis aggressiv: `linear_x_scale 0.17` liegt bewusst ÜBER `linear_max`
> (= sl/stance = 0.08/0.75 ≈ 0.107 @ cycle 1.5 im mittel-Stance) → die Engine clampt
> proportional + warnt throttled. Das ist ok (Stick-Feinfühligkeit oben raus),
> stört dich die WARN, Scale ≤ linear_max wählen.

---

# H2.6 — HW: aggressiv-Realitäts-Check + Tempo-Wechsel im Feld (Pi, Boden)

**Voraussetzung:** H2.5-Werte final + committet + auf dem Pi gebaut (H1-Doku Schritt 0b/0c).
Referenzpunkt Sicherheit: cycle 1.5 lief auf HW bereits; die unbewiesene Größe ist der
**Servo-Speed über längere aggressiv-Bahnen** (Strom/Wärme/Stabilität). §9: Kill-Switch
griffbereit; die erste aggressiv-Minute aufgebockt sichten, dann Boden.

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait + Komplett-Preset (Alltags-Setup) ──
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

**Ablauf:**
1. **Tempo-Treppe im Feld:** langsam → mittel → schnell → aggressiv, je Stufe 1–2 Bahnen
   (geradeaus + Kurve + Stopp). Wechsel jeweils im Stand (D-Pad ↑).
2. **aggressiv-Dauerprobe:** 2–3 min fahren; **Terminal 1 beobachten**: `OVERCURRENT`/Strom-WARNs,
   Servo-Pfeifen/Wärme, Stolpern/Aufschwingen. Bei Auffälligkeit: D-Pad ↓ (im Stand) oder Kill.
3. **Tempo-Wechsel-Robustheit:** mehrfach im Stand hoch/runter durchschalten, dazwischen fahren —
   kein Freeze, kein Ruck beim ersten Schritt nach dem Wechsel.
4. Optional je Stance-Modus wiederholen (hoch-Stance + aggressiv = kürzeste Schritte,
   höchster Hub — der Terrain-Extremfall).

**Melde-Format (knapp):** je Stufe stabil j/n · aggressiv: Strom/Wärme/Verhalten ·
Wechsel-Ruck j/n · ggf. finale HW-Korrektur der Tabelle (→ ich ziehe nach wie H2.5).

---

## Was NICHT getestet wird (scope-out)

- **Nicht-Tripod-Gangarten** mit Tempo-Presets → eigene Runde (Open-Loop-Wackeln, s. Backlog).
- **Neue Envelope-Rechnung fürs Tempo** — envelope-frei bewiesen (Hülle hängt nicht am Tempo);
  die sl-Deckel-Zellen sind offline gate-validiert (H2.1, exit-code-basiert).
- **Tempo-Wechsel IM Lauf** — bewusst nicht unterstützt (Stride-Math-Konsistenz; gait-Guard).
