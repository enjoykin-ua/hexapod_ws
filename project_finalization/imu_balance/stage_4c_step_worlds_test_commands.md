# S4-6 — Test-Befehle (Stufen- + Graben-Welt, Demo des adaptiven Touchdowns)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** den S4-2-Nutzen **sichtbar**
> machen. Stage 4 **isoliert** (`leveling_enable:=false`, Default in `*_walk`).
>
> **➡️ Der eindeutige Test ist [T4 — Graben](#t4--graben-die-klare-demo-der-per-fuß-reach).** Befund
> aus T1: eine vollbreite **Stufe ab** wird fast komplett vom Körper-**Pitch** geschluckt
> (Touchdown-Anteil nur ~3 mm) → schwache Demo. Ein **schmaler Graben** isoliert den per-Fuß-Reach
> (`cmd_z` ~−0.10 statt −0.08, Körper bleibt eben). T1–T3 (Stufe) bleiben als funktionaler Beleg +
> Grenz-/Gegenprobe.

## Konventionen

- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop`. Adaptiv-/Tiefe-Param **live** setzen.
- **Welt:** `step_walk.launch.py` = Ein-Befehl-Bringup (Sim + Stufe + Spawn + Auto-Standup), Default
  `leveling_enable:=false`. `step_drop` signiert: **+ = ab** (Payoff), **− = auf** (Gegenprobe).
- **Bauen vorab:**
  ```bash
  cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
  colcon build --packages-select hexapod_gazebo hexapod_bringup --symlink-install
  ```

## Reach-Budget (warum welche Stufenhöhe)

Option A reicht **nur nach unten** bis `body_height − touchdown_max_extra_depth`. Mit Default
`max_extra_depth = 0.02` → Floor `−0.10`, also **max ~2 cm** unter Nominalhöhe (+ kleine
pitch-Extrareichweite, wenn die Vorderbeine über die Kante kippen).

| Stufe ab | Erwartung |
|---|---|
| **2 cm** | im Reach → Vorderbeine setzen sauber auf die untere Ebene (`cmd_z` < −0.08 an der Kante). **Für mehr Marge `max_extra_depth:=0.025` setzen** (envelope-GREEN bis −0.12). |
| **4 cm** | **fixed-timing-Grenze**: Fuß erreicht nur den Floor (−0.10), findet keinen Boden → Bein hängt, Körper kippt nach vorn. Zeigt ehrlich die Grenze (→ später S4-3 free-gait). |
| Stufe **auf** | Option A tut **nichts** (reicht nicht nach oben) → `cmd_z` bleibt −0.08, Open-Loop nimmt die Stufe. |

## Beobachten (gait_node-Terminal)

`_debug_leg1_contact` bei jeder Bein-1-Flanke:
```
L1 contact RISE | cmd_z=-0.0950 act_z=-0.0840 dz=11.0mm bh=-0.0800 phase=stance0.45
```
→ an der **Stufe ab** mit adaptiv AN soll `cmd_z` an der Kante **deutlich unter −0.0800** gehen
(Nachreichen). Auf flachem Boden + ohne adaptiv bleibt `cmd_z` = −0.0800.

---

## T1 — Stufe 2 cm ab: der Payoff (A/B)

**▶ Terminal 1 — Stufe 2 cm ab starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=0.02 gait_pattern:=tripod
```
⏳ aufstehen abwarten (~12–15 s). Der Roboter steht auf der **oberen** Plattform, Kante bei x=0.

**▶ Terminal 2 — Demo-Marge setzen + langsam zur Kante fahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param set /gait_node touchdown_max_extra_depth 0.025      # Demo-Marge (Default 0.02)
# A) Referenz adaptiv AUS: über die Kante fahren, beobachten
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
# ... wie setzen die Vorderbeine an der Kante auf? (in der Luft landen / stampfen?) ...
# B) adaptiv AN (während er läuft / im zweiten Anlauf):
ros2 param set /gait_node adaptive_touchdown_enable true
```

**✅ Erwartung:** mit AN **reichen die Vorderbeine über die Kante nach unten** und setzen auf der
unteren Ebene auf (`cmd_z` < −0.0800 an der Kante, im Bein-1-Log) → weicher Übergang. Mit AUS
„landet" der Fuß an fester Höhe (−0.0800) über der unteren Ebene → kurzer Fall/Stampfer.

**Stoppen:** `Ctrl-C` auf den `cmd_vel`-Publisher.

---

## T2 — Stufe 4 cm ab: die fixed-timing-Grenze

```bash
# Terminal 1:
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=0.04 gait_pattern:=tripod
# Terminal 2 (nach Aufstehen):
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** der Fuß reicht bis zum Floor (`cmd_z` ≈ −0.10), findet aber keinen Boden (4 cm >
Reach) → das vordere Bein hängt, der Körper kippt nach vorn. **Ehrliche Grenze** des fixed-timing-
Ansatzes (kein Defekt) — größere Sprünge bräuchten free-gait (S4-3).

---

## T3 — Stufe auf: Gegenprobe (adaptiv tut korrekt nichts)

```bash
# Terminal 1:
ros2 launch hexapod_bringup step_walk.launch.py step_drop:=-0.02 gait_pattern:=tripod
# Terminal 2 (nach Aufstehen):
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** der Roboter steigt die 2-cm-Stufe **auf**; `cmd_z` bleibt **−0.0800** (Option A
reicht nicht nach oben → kein Eingriff). Belegt: das Adaptive ist **selektiv** (nur tieferer Boden).

---

---

## T4 — Graben (DIE klare Demo): der per-Fuß-Reach

> **Warum dieser Test der eindeutige ist:** eine vollbreite Stufe ab (T1) wird fast komplett vom
> Körper-**Pitch** geschluckt (Körper kippt über die Kante → Vorderbeine erreichen den unteren Boden
> von selbst, Touchdown-Anteil nur ~3 mm). Ein **schmaler Graben quer zur Laufrichtung** lässt das
> nicht zu: die 4 Beine auf den beidseitigen Plattformen halten den Körper **eben**, nur das einzelne
> Bein über dem Graben muss runter → der per-Fuß-Reach wird **isoliert sichtbar** (`cmd_z` ~−0.10
> statt −0.08).

**▶ Terminal 1 — Graben (2 cm tief, 10 cm breit) starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup trench_walk.launch.py trench_depth:=0.02 trench_width:=0.10 gait_pattern:=tripod
```
⏳ aufstehen abwarten. Der Roboter steht auf der **Nah-Plattform**, Graben bei x=0.

**▶ Terminal 2 — Demo-Marge setzen + über den Graben fahren, A/B:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param set /gait_node touchdown_max_extra_depth 0.025      # Floor −0.105 → 5 mm Marge unter dem 2-cm-Grabenboden
# A) Referenz adaptiv AUS: langsam über den Graben fahren, beobachten
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
# B) adaptiv AN (zweiter Anlauf / Roboter zurückfahren):
ros2 param set /gait_node adaptive_touchdown_enable true
```

### Was du EXAKT siehst (Sim-verifiziert ✅, `max_extra_depth:=0.025`)

**Adaptiv AN:**
- **Bein-1-Log:** wenn Bein 1 über dem Graben steht, geht `cmd_z` (RISE) bis auf den **Floor ≈
  −0.105** runter (= ~2.5 cm Nachreichen, `act_z` ≈ −0.088 → Fuß geht in den Graben). Auf den
  Plattformen wieder `cmd_z = −0.0800`. Beispiel: `cmd_z=-0.1050 act_z=-0.0878 phase=stance0.65`.
- **IMU** (`imu_monitor`): roll bleibt **klein (~±1.3°)**, der Körper bleibt ruhig — von den 4 Beinen
  auf den Plattformen eben gehalten.

**Adaptiv AUS (Referenz):**
- **Bein-1-Log:** `cmd_z = −0.0800` **durchgehend** (reicht NIE nach unten), auch über dem Graben.
- **IMU:** roll schwingt **deutlich stärker (~±2.7°)** — der Körper kippt pro Querung zur
  ungestützten Ecke. ~2× unruhiger als mit AN.

> **Die Signatur des per-Fuß-Reach** = `cmd_z` **−0.105 vs −0.080** über dem Graben (~2.5 cm) **+
> Roll ±1.3° vs ±2.7°** (Körper ~2× ruhiger). Das ist der Unterschied, den die **Stufe** (T1) NICHT
> zeigen konnte (dort nur ~3 mm, weil der Pitch sie „cheatet").
>
> **Hinweis (Mess-Erwartung korrigiert):** `miss` bleibt in **beiden** Fällen **0** — der 10-cm-Graben
> ist schmal genug, dass die Füße ihn teils **überstraddeln**, statt den Touchdown ganz zu verpassen.
> Die klare Signatur ist also **Reach + halbierter Roll**, nicht ein `miss`-Sprung. (Breiterer Graben
> → mehr Bein-in-Loch, aber Vorsicht: zu breit → der Körper pitcht wieder wie bei der Stufe.)

**Optional — Graben zu tief (Grenze):** `trench_depth:=0.03` → Fuß reicht nur bis Floor (−0.105),
findet keinen Boden (3 cm > Reach) → Bein hängt im Graben, Ecke sackt (fixed-timing-Grenze, wie T2).

---

## Rückmeldung an mich (knapp genügt)

- **T4 (Graben — der wichtige):** mit AN gleitet er eben drüber + `cmd_z` geht auf ~−0.10 über dem Graben? Mit AUS sackt/ruckt der Körper + `cmd_z` bleibt −0.08 + `miss` steigt?
- T1 (2 cm Stufe ab): subtil (vom Pitch geschluckt) — nur zur Info.
- T2 (4 cm Stufe) / T3 (Stufe auf): Grenze bzw. Gegenprobe wie beschrieben?
- Auffälligkeiten: Freeze, Absacken auf flach (sollte NICHT, Anker), Logs?
