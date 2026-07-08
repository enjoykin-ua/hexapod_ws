# Stufe 8 — Test-Befehle: Fußkontakt-Closed-Loop auf HW

> **Copy-paste-fertig.** Jeder Test enthält **alle** Terminals/Befehle (Bringup wiederholt sich
> bewusst — jeder Block ist allein ausführbar). Plan:
> [`stage_8_hw_foot_closed_loop_plan.md`](stage_8_hw_foot_closed_loop_plan.md).
>
> **Ziel:** die sim-verifizierten Fußkontakt-Features (S4-2 adaptiver Touchdown, S4-4 Slip→Freeze,
> S4-5 Sensor-Fault-Fail-Safe, S4-7 Adaptive Stand) am **bestromten Roboter** verifizieren + die
> Timing-Params auf HW nachziehen. **Kein neuer Code** — nur einschalten, fahren, messen, tunen.
>
> **Reihenfolge (User-Entscheid, weicht vom Plan-§2 ab):** die Timing-Charakterisierung (HW8.1)
> läuft **am Boden beim Gate-Lauf mit** (aufgebockt lassen sich nicht 5–6 Taster gleichzeitig
> drücken; am Boden liefern alle 6 Beine echte Touchdown-Flanken automatisch). Aufgebockt bleibt
> nur der taster-freie Probe-Test (HW8.2a).

## ✅ HW8.0 — bereits erledigt (Vorab-Verify durch User)

Alle 6 Taster → richtiges `/leg_<n>/foot_contact`-Topic → richtiger Fuß in RViz (grün/grau),
keine Geister. **Fail-safe-Richtung geklärt:** abgesteckter Taster/Kabelbruch = offener Kreis =
`False` (Luft) = **sichere** Fehlrichtung (schlimmstenfalls Fehl-Freeze, nie „fälschlich geerdet"
über einer Kante); die S4-5-dead-Erkennung maskiert den Dauer-False-Fall. Kein weiterer Test nötig.

## ⚠️ Safety (CLAUDE.md §9)

- **2S-LiPo, Kill-Switch in der Hand**, erst aufgebockt (HW8.2a), dann Boden. Langsam (`x=0.03 m/s`).
- **Safety-Freeze auf HW = HALTEN, nicht schlaff:** das Plugin hält die letzte gültige PWM-Position
  und füttert den FW-Watchdog weiter (kein Relay-Drop). Der Roboter bleibt also stehen/stemmt sich.
- **Recovery nach jedem Freeze (Slip oder Tip) — genau diese Reihenfolge:**
  ```bash
  # 1. Stick loslassen / cmd_vel stoppen (falls Publisher läuft: Strg+C bzw.)
  ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
  # 2. Plugin-Freeze lösen (gait published während Freeze-Latch nichts -> kein Sprung):
  ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger '{}'
  # 3. gait-seitigen Latch per State-Wechsel lösen + saubere Pose:
  ros2 service call /hexapod_sit_down std_srvs/srv/Trigger '{}'
  ros2 service call /hexapod_stand_up std_srvs/srv/Trigger '{}'
  ```
- Slip/Fault **gezielt provozieren** (Podest-Kante, abgesteckter Taster) — nie „mal schauen".
- Alle Befehle laufen **lokal auf dem Pi** (SSH-Terminals), außer wo „Desktop" dransteht.

## Konventionen

- **Sourcing** je Terminal: `cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash`
  (in den Blöcken jeweils ausgeschrieben).
- **Vor dem ersten `ros2 param set` einer Session:** einmal `ros2 daemon stop` („node not found"-Falle).
- **Alle S4-Params sind live** — Umschalten ohne Node-Neustart. Enable-Flags Default **false** (Opt-in).
- **Diagnose-Log lesen (Terminal 2, 1 Hz, `foot_contact_debug_enable` Default an):**
  `foot_contact [111111] | L1 td12 lat1.2/3 miss0 apex0 gap4 | …`
  - `[..]` = aktuelle Kontakt-Bits leg_1..6 · `td` = gezählte Touchdowns · `lat avg/max` =
    Touchdown-Latenz in **Ticks** (50 Hz → ×20 ms) · `miss` = Stance komplett ohne Kontakt ·
    `apex` = Kontakt mitten im Schwung · `gap` = kein Kontakt mitten in der Stance.
  - Dazu pro Bein-1-Flanke: `L1 contact RISE|FALL | cmd_z=… act_z=… dz=…mm phase=…`.

---

## Schritt 0 — Einmalig pro Session

**0a — Code auf den Pi holen + bauen** (auf dem Pi; Voraussetzung: Stand ist committet + gepusht —
Git machst du):
```bash
cd ~/hexapod_ws
git fetch origin
git checkout -B imu_balance origin/imu_balance
git reset --hard origin/imu_balance     # Pi = reiner Ziel-Klon; verwirft lokale Pi-Änderungen!
source /opt/ros/jazzy/setup.bash
colcon build                            # hexapod_gazebo wird am Pi per COLCON_IGNORE übersprungen
source install/setup.bash
```

**0b — PS4-Controller (Bluetooth, bereits gepairt, MAC `D0:27:88:3D:68:9A`):**
```bash
# PS-Taste drücken -> verbindet automatisch. Prüfen:
ls /dev/input/js*
bluetoothctl connect D0:27:88:3D:68:9A    # nur falls PS-Taste nicht reicht
```
> Fallback ohne Controller — konstante Fahrt/Stopp per Terminal:
> ```bash
> ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.03}}'   # fahren
> ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'                  # stoppen
> ```

---

## Param-Referenz — alle S4-Stellhebel mit Defaults (copy-paste-Reset)

```bash
# S4-2 adaptiver Touchdown (WALKING):
ros2 param set /gait_node adaptive_touchdown_enable            false
ros2 param set /gait_node touchdown_probe_start_stance_phase   0.35
ros2 param set /gait_node touchdown_search_end_stance_phase    0.6
ros2 param set /gait_node touchdown_max_extra_depth            0.02

# S4-4 Slip/Kante -> Freeze (WALKING):
ros2 param set /gait_node slip_detection_enable                false
ros2 param set /gait_node cliff_depth                          0.03
ros2 param set /gait_node slip_debounce_ticks                  8
ros2 param set /gait_node slip_min_lost_legs                   1
ros2 param set /gait_node slip_grace_stance_phase              0.6

# S4-5 Sensor-Plausibilität -> maskieren (WALKING):
ros2 param set /gait_node sensor_plausibility_enable           false
ros2 param set /gait_node sensor_apex_band_low                 0.3
ros2 param set /gait_node sensor_apex_band_high                0.7
ros2 param set /gait_node sensor_apex_fault_cycles             3
ros2 param set /gait_node sensor_dead_cycles                   2

# S4-7 Adaptive Stand (STANDING):
ros2 param set /gait_node adaptive_stand_enable                false
ros2 param set /gait_node stand_conform_max_depth              0.04
ros2 param set /gait_node stand_conform_rate                   0.02

# Diagnose (S4-1, live):
ros2 param set /gait_node foot_contact_debug_enable            true
```
> Alle aktuellen Werte ansehen: `ros2 param dump /gait_node | grep -E "touchdown_|slip_|cliff_|sensor_|stand_conform|adaptive_|foot_contact"`

---

# HW8.2a — Adaptiver Touchdown aufgebockt (Probe ohne Boden)

**Ziel:** aufgebockt gibt es keinen Kontakt → **jedes Bein probt in jeder Stance bis zum Floor**
(`body_height − max_extra_depth` = 2 cm tiefer) — „sucht den Boden, der nicht da ist". Prüft den
Probe-Pfad + Körper-Anker: kein IKError, kein Ruckeln, Strom unauffällig.

```bash
# ── Terminal 1 (Pi): Servo-Stack (aufgebockt! Kill-Switch bereit; enable_imu hier NICHT nötig) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + automatisches Aufstehen (kartesisch, ~8 s) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Teleop (PS4-BT; PS-Taste drücken) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): Kontakt-Bits live (bleiben aufgebockt [000000], außer du drückst) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /foot_contacts
```
```bash
# ── Terminal 5 (Pi): Tuning-Terminal — Referenzlauf OHNE, dann MIT Touchdown ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop
ros2 param get /gait_node adaptive_touchdown_enable     # Boolean value is: False -> Node lebt

# A) Referenz: laufen lassen OHNE adaptiv (PS4: R1 halten + linker Stick vor; oder cmd_vel-Fallback)
#    -> nominales Gangbild aufgebockt einprägen.

# B) Touchdown AN (live), gleiche Fahrt:
ros2 param set /gait_node adaptive_touchdown_enable true
```

**✅ Erwartung (B vs. A):**
- Jedes Bein senkt in der **späten Stance** sichtbar ~2 cm tiefer als nominal (Probe bis Floor) und
  resettet im Schwung — gleichmäßig, ruhig, **kein** IKError im Terminal-2-Log, **kein** Zucken.
- Der Diagnose-Log zeigt `miss` zählend hoch (kein Boden = kein Touchdown — **hier korrekt**, kein Fehler).
- Terminal 1: kein `OVERCURRENT`/Watchdog.
- **Optionaler Spot-Check (ein Taster von Hand):** einen Fuß-Taster gedrückt halten, während dieses
  Bein in der Stance ist → Terminal 4 zeigt das Bit, das Bein friert auf der aktuellen Höhe ein
  statt weiter zu proben (Terminal 2 `L1 contact RISE` falls Bein 1).

```bash
# Ende: Touchdown wieder AUS (Boden-Gate läuft ohne):
ros2 param set /gait_node adaptive_touchdown_enable false
# Stoppen: Stick loslassen. Danach Terminals stehen lassen oder Strg+C (T2 dann T1).
```

**Tuning-Tabelle S4-2 (falls hier oder in HW8.3 nötig — immer nur EINE Schraube):**

| Param (Default) | Wert **kleiner** | Wert **größer** | Woran du es erkennst |
|---|---|---|---|
| `touchdown_probe_start_stance_phase` (0.35) | Probe startet früher in der Stance → schnelleres Nachreichen, ABER: startet er **vor** der echten Kontakt-Latenz, probt der Fuß auf flachem Boden los, bevor der Kontakt registriert ist → **Absacken/Drift auf flachem Boden** | Probe startet später → sicherer gegen Fehl-Proben, aber weniger Zeit zum Nachreichen (Fuß erreicht tiefe Stellen evtl. nicht mehr im Fenster) | flacher Boden: `cmd_z` muss konstant `body_height` bleiben (−0.0800). Sackt er ab → Wert **hoch**. HW-Latenz aus HW8.1: Gate muss > (lat_max in Stance-Phase) sein |
| `touchdown_search_end_stance_phase` (0.6) | kürzeres Suchfenster → steilere Senk-Rampe (ruckiger), früher am Floor | längeres Fenster → sanftere Senkung, aber Suche ragt in die späte Stance (Fuß noch nicht gesetzt, wenn das Bein schon Vortrieb leisten soll) | Senk-Bewegung ruckig → Fenster länger; Bein „rutscht" beim Vortrieb → Fenster kürzer. Muss > probe_start bleiben (Validierung) |
| `touchdown_max_extra_depth` (0.02) | weniger Reach → flache Stufen werden nicht mehr erreicht (`miss` steigt an Vertiefungen) | mehr Reach in Senken, ABER Envelope! Vor Erhöhen offline prüfen (Desktop): `python3 tools/walking_envelope_check.py check --body-height -0.105 --scenario all` (Beispiel bh −0.080 + 0.025) | Fuß hängt über der Stufe in der Luft + `miss` zählt → Tiefe rauf (envelope-geprüft). IKError im Log → zu tief |

---

# HW8.2b + HW8.1 — Boden-Lauf-Gate + Timing-Charakterisierung (EIN Lauf)

**Ziel (Gate):** läuft der Roboter am Boden mit voller Last **überhaupt stabil geradeaus**?
(S4 UND Leveling AUS — evtl. der erste echte Boden-Lauf. Läuft er nicht sauber → **hier stoppen**,
das ist ein separates Gang-/Traktions-/Strom-Problem, nicht Stufe 8.)
**Ziel (Timing):** dabei misst die `ContactDiagnostic` passiv das echte HW-Flanken-Timing aller
6 Beine → Basis für `touchdown_probe_start` (HW8.3), `slip_debounce_ticks` (HW8.4),
`sensor_dead_cycles` (HW8.5). Sim-Referenz: lat ≈ 13 Ticks (JTC-Ausführungs-Lag) — auf HW erwarten
wir deutlich weniger (Taster feuert mechanisch, FW-Entprellung nur ~1–2 Ticks).

```bash
# ── Terminal 1 (Pi): Servo-Stack (Roboter auf dem BODEN, freie ebene Fläche >= ~1,5 m, Kill-Switch!) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait-Node + Aufstehen (Diagnose-Log läuft hier; S4/Leveling sind Default-aus) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Teleop (PS4-BT; PS-Taste drücken) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): Sanity + Beobachtung ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop
ros2 param get /gait_node adaptive_touchdown_enable    # False (Gate läuft nackt)
ros2 topic echo /foot_contacts                         # beim Stehen [1,1,1,1,1,1] erwartet
```

**Ablauf:** R1 (Dead-Man) halten + linker Stick vor → ~1 m geradeaus, stoppen, ~1 min laufen
insgesamt (gern mehrere Bahnen; auch mal Kurve). Dann Diagnose ablesen.

**✅ Erwartung Gate (HW8.2b):**
- Läuft stabil geradeaus, kein Umkippen/Wegdriften/Trippeln, kein `OVERCURRENT` (Terminal 1),
  kein IKError (Terminal 2).
- Im Stand zeigen alle 6 Kontakte `1` (Terminal 4).

**✅ Ablesen Timing (HW8.1) — letzte `foot_contact`-Log-Zeile in Terminal 2 nach dem Lauf:**

| Metrik | notieren | gut | auffällig |
|---|---|---|---|
| `lat avg/max` pro Bein (Ticks ×20 ms) | ✍️ | wenige Ticks, alle Beine ähnlich | > ~10 Ticks oder ein Bein-Ausreißer (Taster-Position am Fuß prüfen) |
| `miss` | ✍️ | 0 (jede Stance findet Kontakt) | > 0 auf flachem Boden = Taster trifft nicht jeden Aufsetzer → mechanisch prüfen, sonst wird HW8.4 heikel |
| `apex` | ✍️ | 0 oder einstellig (Nachhall) | zählt zügig hoch = Taster löst zu früh/hängt → Band/`fault_cycles` in HW8.5 beachten |
| `gap` | ✍️ | klein | groß = Kontakt flackert unter Last (Prellen > FW-Entprellung) → `slip_debounce_ticks` in HW8.4 eher hoch |

> **Daraus ableiten (für die nächsten Tests):**
> `touchdown_probe_start` muss (in Stance-Phase umgerechnet) über `lat_max` liegen — bei
> `cycle_time 2.0` ist 1 Stance-Tick ≈ 0.008 Phase; Default 0.35 hat also massiv Marge, wenn
> lat ≪ 13 Ticks. `slip_debounce_ticks` (8 = 160 ms) muss über der längsten „gesunden"
> Kontakt-Lücke (`gap`-Verhalten) liegen.

```bash
# Melde-Format (knapp): Gate ok/nicht ok + die foot_contact-Zeile(n) aus Terminal 2 kopieren.
```

---

# HW8.3 — S4-2 adaptiver Touchdown am Boden (Stufe/Graben — der Payoff)

**Ziel:** Roboter läuft über die **echte Stufe (~2–4 cm ab) / den Graben (fußbreit)** — einzelne
Füße **reichen nach**, Körper bleibt stabil. A/B gegen AUS.

**Aufbau:** Test-Terrain in die Laufbahn (Stufe ab bzw. Graben **quer** zur Laufrichtung).
Bringup wie HW8.2b (Terminals 1–4 identisch):
```bash
# ── Terminal 1 (Pi) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): erst Referenz AUS, dann AN ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop

# A) Referenz AUS: langsam über Stufe/Graben fahren -> Füße stelzen über die Kante,
#    Körper kippt/holpert stärker (einprägen; bei 2-cm-Stufe subtil).

# B) Touchdown AN:
ros2 param set /gait_node adaptive_touchdown_enable true
#    Bei 2-cm-Stufe knapp am Reach-Limit -> für die klare Demo Tiefe auf 0.025 (envelope-GREEN
#    vorab am Desktop geprüft: tools/walking_envelope_check.py check --body-height -0.105 --scenario all):
ros2 param set /gait_node touchdown_max_extra_depth 0.025
```

**✅ Erwartung (B):**
- An der Kante/über dem Graben reicht das betroffene Bein sichtbar nach unten und **setzt auf**
  (Terminal 2: `L1 contact RISE` mit `cmd_z` unter −0.080, falls Bein 1 betroffen); Körper bleibt
  ruhiger als in (A).
- Auf dem flachen Teil davor/danach: exakt nominales Laufen, **kein** Absacken/Ducken/Rückwärts
  (der Körper-Anker — die Anti-Drift-Eigenschaft von Option A).
- `miss` bleibt klein (Füße, die den Grabenboden erreichen, zählen nicht).
- **Tuning nach Bedarf:** Tabelle bei HW8.2a (Werte aus HW8.1 einfließen lassen). Geänderte gute
  Werte ✍️ notieren → `hw_terrain.yaml` (HW8.8).

```bash
# Ende: stoppen (Stick), Touchdown-Entscheid: AN lassen für HW8.4 ist ok (getestet), oder aus:
ros2 param set /gait_node adaptive_touchdown_enable false
```

---

# HW8.4 — S4-4 Slip→Freeze an der Podest-Kante

**Ziel:** Stütz-Bein ohne Kontakt (über der Kante) → **Freeze rechtzeitig** vor dem Kippen;
auf gutem Boden **kein** Fehl-Freeze.

**Aufbau:** Roboter läuft auf dem **Podest (~5–15 cm hoch)** auf die Kante zu (Kante quer zur
Laufrichtung). Absturzhöhe ist unkritisch, trotzdem: Hand bereit. **Freeze-Latenz einplanen:**
mit Defaults (grace 0.6 + debounce 8 @ cycle 2.0, v 0.03) legt der Roboter nach der Kante noch
**~2–3 cm** zurück, bevor der Freeze feuert — Anlauf so wählen, dass das auf dem Podest passiert.

**Vorab EINMALIG am Desktop (Envelope für den tieferen Probe-Floor):** bei aktivem Slip reicht der
Touchdown-Probe bis `cliff_depth` (0.03) statt 0.02 → Floor −0.110:
```bash
# Desktop:
cd ~/hexapod_ws && python3 tools/walking_envelope_check.py check --body-height -0.110 --scenario all
# GREEN -> cliff_depth 0.03 ok. Nicht GREEN -> cliff_depth auf 0.025 senken (unten) + neu prüfen.
```

```bash
# ── Terminal 1 (Pi) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): Slip + Touchdown scharf ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true    # empfohlen: Probe nutzt cliff-Reach
ros2 param set /gait_node slip_detection_enable     true
```

**Test A — Fehl-Freeze-Gegenprobe (ZUERST, auf gutem Boden):** 2–3 Bahnen auf dem flachen
Podest-Teil (ohne Kante) laufen.
**✅ Erwartung:** läuft normal durch, **kein** Freeze, kein ERROR in Terminal 2.
> Freezt es hier fälschlich → `gap`-Werte aus HW8.1 ansehen und `slip_debounce_ticks` erhöhen
> (Tabelle unten), NICHT einfach weiterfahren.

**Test B — Kante:** langsam (x=0.03) auf die Podest-Kante zu, bis 1–2 Beine über die Kante greifen.
**✅ Erwartung:**
- Das überhängende Stütz-Bein findet bis `cliff_depth` keinen Boden → nach Grace+Debounce:
  Terminal 2 `Stütz-Verlust erkannt (… Bein(e) ohne Halt …) — Safety-Freeze`, Roboter **hält
  Position** (stemmt sich, wird NICHT schlaff), bevor er kippt.
- Terminal 1: Plugin-Log zum Freeze.
- **Recovery** (Reihenfolge!): siehe Safety-Block oben (`/hexapod_safety_reset` → sit → stand).

**Tuning-Tabelle S4-4:**

| Param (Default) | Wert **kleiner** | Wert **größer** | Woran du es erkennst |
|---|---|---|---|
| `slip_debounce_ticks` (8) | Freeze kommt schneller (weniger Weg über der Kante), ABER anfälliger für Kontakt-Flackern unter Last → **Fehl-Freeze** auf gutem Boden. Muss > FW-Entprellung + Nachhall bleiben (≥ ~3) | träger, toleranter gegen Prellen — Roboter kommt weiter über die Kante, bevor er stoppt | Fehl-Freeze auf flachem Boden → **hoch**. Freeze erst, wenn er schon kippelt → **runter** (erst `gap` aus HW8.1 prüfen) |
| `slip_grace_stance_phase` (0.6) | Stance-Bein wird früher „stütz-pflichtig" → früherer Freeze, aber: Grace muss die Touchdown-/Probe-Phase abdecken, sonst Fehl-Freeze bei jedem normalen Aufsetzen | später — mehr Zeit für Probe/Aufsetzen, späterer Freeze | Fehl-Freeze direkt nach dem Aufsetzen (früh in der Stance) → **hoch**. cycle_time-abhängig: schnellerer Gang → eher höher |
| `slip_min_lost_legs` (1) | — (Minimum) | 2+: erst wenn mehrere Beine gleichzeitig haltlos → robuster gegen Einzel-Bein-Artefakte, aber an einer geraden Kante greift oft nur 1 Bein/Tripod über → **Freeze käme zu spät** | bei 1 zu nervös trotz debounce-Tuning → auf 2 nur, wenn die Kanten-Geometrie das hergibt |
| `cliff_depth` (0.03) | Grenze „folgbares Terrain ↔ Abgrund" sinkt → schon flachere Absätze gelten als Abgrund (mehr Freezes, weniger Terrain-Folgen) | Fuß probt tiefer, bevor „haltlos" gilt → folgt tieferen Stufen, ABER Envelope-Check Pflicht (oben) + später Freeze | Stufe, die er in HW8.3 noch nahm, freezt jetzt → cliff_depth etwas **hoch** (envelope-geprüft). Kante wird zu spät erkannt → **runter** |

```bash
# Ende: Slip aus (für HW8.5-Variante A):
ros2 param set /gait_node slip_detection_enable false
```

---

# HW8.5 — S4-5 Sensor-Fault (Taster real abgesteckt)

**Ziel:** ein realer Sensor-Ausfall **degradiert** (Bein maskiert + WARN, Open-Loop), stoppt aber
nicht (**kein** Freeze) und flaggt keine gesunden Beine (keine FP-Kaskade — das gz-Apex-Artefakt
existiert auf HW nicht).

> ⚠️ **Wichtig fürs Test-Design:** Kabel **im Lauf** ziehen ist vom echten Slip nicht unterscheidbar
> (Bein hatte Kontakt und „verliert" ihn) → bei aktivem S4-4 freezt das **korrekt** (dokumentierter
> Tradeoff, kein Fehler!). Der saubere Fault-Test ist **von Start an abgesteckt** (Kabel VOR dem
> Lauf am Servo2040-Sensor-Header abziehen — stromlos oder im Stand, z. B. Bein 2).

```bash
# ── Terminal 1 (Pi): (Taster von Bein 2 ist bereits abgesteckt) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```

**Variante A — nur Plausibilität (Slip AUS):**
```bash
# ── Terminal 4 (Pi) ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop
ros2 param set /gait_node slip_detection_enable       false
ros2 param set /gait_node adaptive_touchdown_enable   true
ros2 param set /gait_node sensor_plausibility_enable  true
```
Auf gutem, flachem Boden ~2 Gang-Zyklen laufen (Defaults: dead nach 2 Cycles = ~4 s @ cycle 2.0).
**✅ Erwartung:** Terminal 2: `Sensor fault leg 2 (dead) — ignoring contact …` + throttled
`Foot-contact sensor(s) masked: [2]`. Roboter **läuft weiter** (Bein 2 Open-Loop), **kein** Freeze,
**keine weiteren Beine** werden geflaggt (Maske bleibt `[2]`).

**Variante B — der kritische Race-Test (Plausibilität + Slip beide AN):**
```bash
ros2 param set /gait_node slip_detection_enable true
```
Wieder auf gutem Boden laufen (frischer Start aus dem Stand: einmal stoppen, kurz stehen, wieder los —
State-Wechsel resettet die Monitore).
**✅ Erwartung:** **kein** Fehl-Freeze durch das nie-kontaktierende Bein 2 (der `_ever_contacted`-
Ausschluss greift, solange S4-5 an ist); nach ~2 Cycles wieder `dead`-Maskierung `[2]`. Die anderen
5 Beine schützen weiter normal (S4-4 aktiv).

**Tuning-Tabelle S4-5:**

| Param (Default) | Wert **kleiner** | Wert **größer** | Woran du es erkennst |
|---|---|---|---|
| `sensor_dead_cycles` (2) | toter Sensor wird schneller maskiert (weniger Zeit „ungeschützt-nervös") | träger — in Variante B länger Verlass auf den `_ever_contacted`-Schutz | Maskierung dauert spürbar zu lang → **runter** (min 1). Fehl-`dead` bei einem gesunden, aber selten aufsetzenden Bein (sollte nicht vorkommen, `miss`>0-Beine aus HW8.1 ansehen) → **hoch** |
| `sensor_apex_fault_cycles` (3) | stuck-on wird nach weniger lückenlosen Apex-Pässen geflaggt → schneller, aber anfälliger für einen ungünstig klemmend-prellenden Taster | robuster (mehr Pässe nötig), stuck-on-Erkennung dauert länger | gesunde Beine werden als `stuck_on` geflaggt (FP) → **hoch**. Echter Klemmer (Taster mechanisch blockiert) wird nicht erkannt → **runter** |
| `sensor_apex_band_low/high` (0.3/0.7) | Band breiter (low runter/high rauf): mehr Schwung-Phase zählt als „Kontakt unmöglich" → empfindlicher, aber low muss über dem Kontakt-Nachhall am Schwung-Anfang bleiben | Band schmaler: konservativer | `apex`-Zähler in HW8.1 schon ohne Fault hoch? → low eher **rauf** (0.35–0.4), sonst Default lassen |

```bash
# Ende: Taster von Bein 2 wieder anstecken (stromlos/im Stand), Enables nach Bedarf:
ros2 param set /gait_node sensor_plausibility_enable false
```

---

# HW8.6 — S4-7 Adaptive Stand (ERST Sim-Rubicon am Desktop, DANN HW)

**Teil 1 — Sim-Rubicon-Verify (Desktop!)** — der noch offene Sim-Schritt aus Stufe 4
(Voll-Doku: [`stage_4f_adaptive_stand_test_commands.md`](stage_4f_adaptive_stand_test_commands.md),
hier der Kern):
```bash
# Desktop, Terminal 1 — Rubicon-Welt (Fuel-Welt ggf. einmalig: gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"):
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup rubicon.launch.py
```
```bash
# Desktop, Terminal 2 — Aufstehen (Leveling isoliert AUS):
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py leveling_enable:=false
```
```bash
# Desktop, Terminal 3 — Kontakte beobachten:
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /foot_contacts
```
```bash
# Desktop, Terminal 4 — A) Referenz aus, dann AN:
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param set /gait_node adaptive_stand_enable true
```
**✅ Erwartung Sim:** hängende Beine senken langsam ab (~2 s für 4 cm) und setzen auf →
`/foot_contacts` Richtung `[1,1,1,1,1,1]`; Dips > 4 cm hängen am Floor (dokumentierte v1-Grenze,
live bis 0.05 testbar); `adaptive_stand_enable false` → exakt starre Pose zurück. Stance-Wechsel
per PS4 L2/R2 → Füße konformen **frisch** von der neuen Höhe (kein Überstrecken).

**Teil 2 — HW (erst aufgebockt-sinnfrei überspringen → direkt Boden auf unebenem Grund):**
Bretter/Klötze (~1–3 cm) unter einzelne Fuß-Positionen legen, sodass beim Stehen 1–2 Füße in der
Luft hängen würden.
```bash
# ── Terminal 1 (Pi) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
```bash
# ── Terminal 3 (Pi): Kontakt-Bits ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /foot_contacts
```
```bash
# ── Terminal 4 (Pi): A) Referenz: stehen mit hängendem Fuß ([.. 0 ..] in T3). B) AN: ──
cd ~/hexapod_ws && source install/setup.bash
ros2 daemon stop
ros2 param set /gait_node adaptive_stand_enable true
```
**✅ Erwartung HW:** der hängende Fuß senkt langsam ab und **setzt auf** (Bit → 1), Körper bleibt
ruhig; `false` → starre Pose zurück (Fuß hebt wieder ab). Kein Zittern am Kontaktpunkt (Taster-
Prellen am Rand → ggf. `stand_conform_rate` runter).

**Tuning-Tabelle S4-7:**

| Param (Default) | Wert **kleiner** | Wert **größer** | Woran du es erkennst |
|---|---|---|---|
| `stand_conform_max_depth` (0.04) | flachere Senken erreichbar, tiefere bleiben hängen | tiefere Senken erreichbar — **Envelope-Grenze 0.05** (offline: `python3 tools/stand_conform_envelope_check.py --max-depth 0.05`; 0.06 → „hoch" RED) | Fuß hängt trotz AN über der Senke → schrittweise Richtung 0.05. IKError/Überstreckung → runter |
| `stand_conform_rate` (0.02) | langsameres Absenken (sanfter, taster-schonend, weniger Prell-Zittern am Kontakt) | schnelleres Aufsetzen, aber härterer Kontakt + Übersenk-Risiko bei Kontakt-Latenz | Absenken dauert nervig lange (>3–4 s) → hoch. Fuß „stempelt" auf / friert sichtbar unter der Auflage ein → runter |

---

# HW8.7 — Kombi S4 + IMU-Leveling (die nie getestete Kombination)

**Ziel:** adaptive-z **unter** aktiver Leveling-Rotation bleibt geometrisch sauber — kein
IKError-Spam, kein Zucken/Konflikt. (Erster gemeinsamer Lauf beider Regelkreise; hier kann sich
ein kleiner Integrations-Fix zeigen → dann zurück zu mir.)

```bash
# ── Terminal 1 (Pi): Servo-Stack + IMU (Boden; Kill-Switch!) ──
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash && source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false enable_imu:=true initial_pose:=power_on_mid
```
```bash
# ── Terminal 2 (Pi): Gait + verifizierte Leveling-Konfig (hw_balance.yaml; leveling_enable bleibt false im Preset) ──
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF" \
    params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/hw_balance.yaml
```
```bash
# ── Terminal 3 (Pi): Teleop ──
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
```bash
# ── Terminal 4 (Pi): Lage + Kontakte im Blick ──
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /imu/monitor        # roll/pitch [rad]
# (zweites Fenster optional: ros2 topic echo /foot_contacts)
```

**Test A — Stand-Kombi (Adaptive Stand + horizontal-Leveling), unebener Untergrund/Kipp-Platte:**
```bash
ros2 daemon stop
ros2 param set /gait_node adaptive_stand_enable true
ros2 param set /gait_node leveling_mode         horizontal
ros2 param set /gait_node leveling_enable       true
```
**✅ Erwartung:** Körper levelt horizontal UND hängende Füße konformen auf den Boden — beides
gleichzeitig, ruhig, kein Pendeln zwischen den beiden Regelkreisen, kein IKError (Terminal 2).

**Test B — Lauf-Kombi (adaptiver Touchdown + terrain-Leveling), über die Stufe/Graben von HW8.3:**
```bash
ros2 param set /gait_node adaptive_stand_enable     false
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 param set /gait_node slip_detection_enable     true
ros2 param set /gait_node leveling_mode             terrain
ros2 param set /gait_node leveling_enable           true
```
Langsam über das HW8.3-Terrain fahren.
**✅ Erwartung:** Nachreichen an der Stufe wie HW8.3 **plus** ruhigerer Körper (Leveling dämpft);
kein IKError-Spam, kein gegenseitiges Aufschaukeln (adaptive-z ↔ Rotation), Slip-Schutz bleibt
scharf. Bei Konflikt (Zucken an der Stufe, IKError-Serie): sofort
`ros2 param set /gait_node leveling_enable false` → Befund melden (das wäre der erwartbare
Integrations-Fix-Fall).

```bash
# Ende:
ros2 param set /gait_node leveling_enable false
```

---

# HW8.8 — Gute Werte sichern (→ `hw_terrain.yaml`)

Während HW8.2–8.7 geänderte, für gut befundene Werte hier eintragen (✍️) und melden — ich erstelle
daraus `hexapod_gait/config/presets/hw_terrain.yaml` (S4-Params, getrennt von `hw_balance.yaml`)
+ Doku HW vs. Sim-Default. Lade-Weg danach:
```bash
# beide Presets zusammen geht NICHT über params_file (nur EIN File) -> hw_terrain.yaml wird die
# S4-Werte enthalten; für Kombi-Läufe lade ich die Leveling-Werte mit hinein (wird bei Erstellung
# entschieden + dokumentiert).
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF" \
    params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/hw_terrain.yaml
```

| Param | Sim-Default | HW-Wert ✍️ | Begründung ✍️ |
|---|---|---|---|
| `touchdown_probe_start_stance_phase` | 0.35 | | |
| `touchdown_search_end_stance_phase` | 0.6 | | |
| `touchdown_max_extra_depth` | 0.02 | | |
| `cliff_depth` | 0.03 | | |
| `slip_debounce_ticks` | 8 | | |
| `slip_min_lost_legs` | 1 | | |
| `slip_grace_stance_phase` | 0.6 | | |
| `sensor_apex_band_low` / `high` | 0.3 / 0.7 | | |
| `sensor_apex_fault_cycles` | 3 | | |
| `sensor_dead_cycles` | 2 | | |
| `stand_conform_max_depth` | 0.04 | | |
| `stand_conform_rate` | 0.02 | | |
| HW8.1-Messwerte (lat avg/max, miss, apex, gap) | — | | Basis der Timing-Entscheide |

---

## Was NICHT getestet wird (scope-out, Plan §3)

- **S4-3 free-gait** (Gang-Timing am Kontakt) — optional, nur falls fixed-timing nicht reicht.
- **Quer-/Diagonal-Terrain**, adaptiver Slope-Schätzer (D1), state-abhängige Fenster (D3).
- **Unit-Tests** — Regler sind sim-unit-getestet; Stufe 8 = HW-Verifikation + Timing-Tuning.
- **Enable-Defaults bleiben false** — Opt-in-Scharfschalten pro Lauf (bzw. später via `hw_terrain.yaml`).

## Melde-Format (pro Test, knapp)

- **HW8.2a:** stabil j/n · IKError j/n · Spot-Check-Einfrieren j/n
- **HW8.2b/8.1:** Gate ok j/n · die `foot_contact […] | L1 …`-Log-Zeile(n) kopieren
- **HW8.3:** reicht nach j/n · flach nominal j/n · geänderte Params
- **HW8.4:** A kein Fehl-Freeze j/n · B Freeze vor Kippen j/n · Latenz gefühlt/Weg über Kante · Params
- **HW8.5:** A masked `[n]` + läuft weiter j/n · B kein Fehl-Freeze j/n
- **HW8.6:** Sim: Füße setzen auf j/n · HW: hängender Fuß setzt auf j/n
- **HW8.7:** A ruhig j/n · B kein Konflikt/IKError j/n (sonst: Log-Ausschnitt)
