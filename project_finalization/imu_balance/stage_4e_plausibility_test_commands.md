# S4-5 — Test-Befehle (Plausibilität / Sensor-Fault-Fail-Safe)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Ziel:** ein **defekter Fußkontakt-Sensor**
> (klemmt auf „Kontakt" = stuck-on, oder auf „kein Kontakt" = dead/stuck-off) **verschlechtert das
> Verhalten nicht** — der betroffene Sensor wird **erkannt → geflaggt → ignoriert** (das Bein fällt
> auf Open-Loop zurück + ist aus der Slip-Zählung raus) + **gewarnt**. **Kein Freeze** (Leitprinzip:
> Taster = Optimierung, nie load-bearing). Stage 4 **isoliert** (`leveling_enable:=false`, Default
> in `*_walk`).
>
> **Wichtig:** Der gz-Sim-Sensor ist zuverlässig (`miss 0`) → es gibt in der Sim **keinen echten
> Fault**. Deshalb der **Test-Hook `sensor_fault_inject`**: er zwingt EINEN gecachten Kontakt auf
> einen Klemm-Wert und provoziert so die Erkennung. S4-5 ist HW-gerichtet (echte Microswitches
> prellen/klemmen/sterben, Phase E2) — der Inject ist die einzige Möglichkeit, es live zu verifizieren.

## Konventionen

- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop` (sonst „Node not found").
- **Opt-in:** `sensor_plausibility_enable` Default **false**. Schwellen-Defaults: apex_band
  **0.3 / 0.7**, `sensor_apex_fault_cycles` **3** (lückenlose Apex-Pässe in Folge), `sensor_dead_cycles`
  **2** (Cycles, cycle_time-unabhängig).
- **Inject-Format:** `sensor_fault_inject:='<leg>:stuck_on'` oder `'<leg>:stuck_off'` (`leg` ∈ 1..6).
  `''` / `'none'` = aus (Default).
- **Logs in diesem Stage englisch** (User-Wunsch): `Sensor fault leg N (…)`, `Foot-contact sensor(s) masked: […]`.
- **Bauen vorab:**
  ```bash
  cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
  colcon build --packages-select hexapod_gait hexapod_gazebo hexapod_bringup --symlink-install
  ```

## Beobachten (gait_node-Terminal)
- Beim Erkennen eines Faults: **WARN-Log** `Sensor fault leg N (stuck_on|dead) — ignoring contact
  (adaptive off + excluded from slip count)` (einmalig, steigende Flanke) + periodischer Reminder
  (alle 5 s) `Foot-contact sensor(s) masked: [N]`.
- **Degradation statt Stopp:** der Roboter **läuft weiter**. Das geflaggte Bein nutzt nur noch den
  nominalen Bogen (Open-Loop) und löst keinen Slip-Freeze (mehr) aus. **Kein** ERROR/Freeze von S4-5.
- **⚠️ Wichtig (T1-Befund + Redesign):** Es darf **nur das injizierte Bein** geflaggt werden — die
  gesunden Beine dürfen NICHT nach und nach mitmaskiert werden. Der gz-Kontakt meldet auch gesund
  lückenhaften Apex-Kontakt (die `apex`-Zähler im `foot_contact`-Log klettern für alle Beine — das
  ist **normal/Artefakt**, kein Fault). Die stuck-on-Erkennung verlangt jetzt **3 lückenlose
  Apex-Pässe in Folge**, was nur ein wirklich klemmender (injizierter) Sensor erreicht. Das injizierte
  Bein wird daher erst nach **~3 Cycles** (`sensor_apex_fault_cycles` 3, bei cycle_time 2.0 ≈ 6 s)
  geflaggt — etwas später als beim ersten Entwurf, dafür **ohne Falsch-Positive**.

---

## T1 — stuck-on: Phantom-Kontakt wird erkannt + maskiert (verhindert Fehl-Suppress eines Freezes)

**Worum es geht:** ein stuck-on-Sensor (klemmt „Kontakt") würde sonst (a) S4-2 per Phantom-Kontakt zu
früh einfrieren und (b) S4-4 „immer gestützt" vortäuschen → **kein Freeze über einer Kante** (gefährlich).
S4-5 erkennt den Apex-Kontakt (geometrisch unmöglich) und nimmt das Bein aus beiden Stufen.

**▶ Terminal 1 — Graben-Welt starten (per-Fuß-Reach sichtbar):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup trench_walk.launch.py gait_pattern:=tripod
```
⏳ aufstehen abwarten.

**▶ Terminal 2 — Plausibilität + adaptiven Touchdown scharf, dann stuck-on injizieren + losfahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
ros2 param set /gait_node adaptive_touchdown_enable true
ros2 param set /gait_node sensor_plausibility_enable true
ros2 param set /gait_node sensor_fault_inject "1:stuck_on"
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** nach ~3 Cycles (≈ 6 s) **WARN** `Sensor fault leg 1 (stuck_on) — ignoring contact …`
+ `Foot-contact sensor(s) masked: [1]`. Danach läuft der Roboter **stabil weiter**; Bein 1 reicht über
dem Graben **nicht** mehr adaptiv nach (Open-Loop), die anderen Beine arbeiten normal. **Kein** Freeze,
**kein** Absacken. **Entscheidend:** die Maske bleibt bei **[1]** — Beine 2–6 dürfen NICHT mit
geflaggt werden (sonst ist die stuck-on-Erkennung zu empfindlich → zurückmelden).

**Gegenprobe (ohne S4-5):** `Ctrl-C`, dann `sensor_plausibility_enable false` + erneut fahren → das
stuck-on-Bein 1 friert seinen Touchdown sofort bei `body_height` ein (Phantom) bzw. täuscht Stütze
vor — der korrumpierte Zustand, den S4-5 verhindert.

---

## T2 — dead/stuck-off: totes Bein → Open-Loop, KEIN Fehl-Freeze in S4-4

**Worum es geht:** ein toter Sensor (klemmt „kein Kontakt") würde sonst in S4-4 einen **Fehl-Freeze**
auf gutem Boden auslösen (scheinbarer Halt-Verlust). S4-5 erkennt „kein Kontakt über 2 Cycles" → flaggt
das Bein → schließt es aus der Slip-Zählung aus → der Roboter bleibt fahrbar.

> **⚠️ Wichtig (T2-Befund 1. Runde + Fix):** die volle dead-Erkennung braucht 2 Cycles (~4 s), der
> Slip-Freeze würde aber schon nach Grace+Debounce (~1–1.5 s) feuern → der Freeze **gewann das Rennen**
> und stoppte den Roboter (Fehl-Freeze, genau was S4-5 verhindern soll). **Fix:** ein Bein, das diese
> Lauf-Episode **nie** Kontakt hatte (toter/stuck-off-Sensor von Anfang an), gab nie Stütze → es kann
> sie nicht „verlieren" → es wird **sofort** aus der Slip-Zählung ausgeschlossen (nicht erst nach 2
> Cycles). Ein **echter** Slip/Kante (Bein **hatte** Kontakt, verliert ihn) friert weiterhin sofort.
> **Bewusste Grenze:** ein Sensor, der **mitten im Lauf** stirbt (hatte Kontakt, dann still), ist vom
> echten Slip nicht unterscheidbar → bleibt ein **sicherer Freeze** (Plan §0). Nur der stuck-off-von-
> Start-Fall wird fahrbar gehalten.

**▶ Terminal 1 — flach starten:**
```bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0 gait_pattern:=tripod leveling_enable:=false
```

**▶ Terminal 2 — Slip-Erkennung UND Plausibilität an, dead injizieren, losfahren:**
```bash
ros2 daemon stop
ros2 param set /gait_node slip_detection_enable true
ros2 param set /gait_node sensor_plausibility_enable true
ros2 param set /gait_node sensor_fault_inject "2:stuck_off"
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
```
**✅ Erwartung:** der Roboter **läuft durchgehend weiter** — **kein** Slip-Freeze (Bein 2 wird ab dem
ersten Stance-Fenster aus der Slip-Zählung ausgeschlossen, weil es nie Kontakt hatte). Nach ~2 Cycles
(≈ 4 s) zusätzlich **WARN** `Sensor fault leg 2 (dead) — ignoring contact …` + `masked: [2]`.
**Entscheidend:** **kein** ERROR `Stütz-Verlust …`, der Roboter stoppt NICHT, und die Maske bleibt
**[2]** (Beine 1,3,4,5,6 bleiben gesund).

**Gegenprobe (ohne S4-5):** `Ctrl-C`, `sensor_plausibility_enable false` (Slip weiter an), erneut fahren
→ das tote Bein 2 triggert nach Grace+Debounce den **Fehl-Freeze** (ERROR `Stütz-Verlust …`) und der
Roboter **stoppt**, obwohl der Boden gut ist. Genau das verhindert S4-5 — der ever_contacted-Ausschluss
ist an `sensor_plausibility_enable` gekoppelt, „pures S4-4" behält also sein striktes Freeze-Verhalten.

---

## T3 — Latch + Recovery

- Der Flag ist **latched** bis State-Wechsel: nach dem WARN bleibt das Bein maskiert, auch wenn der
  Inject entfernt wird (`sensor_fault_inject none`) — bis `cmd_vel=0` (→ STOPPING → reset) oder Stop.
- **Recovery:** `Ctrl-C` auf den Publisher (oder `ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'`).
  Beim nächsten Losfahren ist die Maske gelöscht (sofern der Inject aus ist).

---

## T4 (optional) — Tuning / Schwellen

```bash
ros2 daemon stop
ros2 param set /gait_node sensor_apex_band_low 0.3      # Apex-Band-Untergrenze (> contact_timeout-Nachhall)
ros2 param set /gait_node sensor_apex_band_high 0.7     # Apex-Band-Obergrenze
ros2 param set /gait_node sensor_apex_fault_cycles 3    # lückenlose Apex-Pässe in Folge bis stuck-on (2 = schneller, 4 = robuster)
ros2 param set /gait_node sensor_dead_cycles 2          # Cycles ohne Kontakt bis dead
```
> ⚠️ `sensor_dead_cycles` ist in **Cycles** (cycle_time-unabhängig) — der Node rechnet via
> `cycle_time · tick_rate` in Ticks um (Rebuild bei cycle_time/tick_rate-Änderung). `sensor_apex_band_low`
> bewusst **0.3** (nicht tiefer): der `contact_timeout`-Nachhall (~5 Ticks) liegt am Schwung-Anfang
> bei Phase < 0.3 und darf keinen Apex-Pass öffnen. `sensor_apex_fault_cycles` runter (2) = schnellere
> Erkennung des injizierten Beins, aber kleinere Marge gegen den Walk-Start-Transient.

---

## Rückmeldung an mich (knapp genügt)
- T1: WARN `stuck_on leg 1` nach ~3 Cycles? **Maske bleibt [1]** (Beine 2–6 NICHT mitgeflaggt)?
  Läuft stabil weiter? Ohne S4-5 sichtbar korrupt?
- T2: WARN `dead leg 2` nach ~2 Cycles? **Kein** Fehl-Freeze mit S4-5? Ohne S4-5 Fehl-Freeze (Gegenprobe)?
- T3: Bein bleibt maskiert bis cmd_vel=0; Recovery danach ok?
- Auffälligkeiten: zu früh/spät erkannt, falsches/zu viele Beine, Logs?
