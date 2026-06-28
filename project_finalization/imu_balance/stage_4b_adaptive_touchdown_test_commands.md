# S4-2 — Test-Befehle (Adaptiver Touchdown, Option A)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Design = Option A** (downward-only, an
> `body_height` verankert, lag-tolerant). **Zwei Ziele:** (1) **T1 flach — Stabilität:** mit
> adaptivem Touchdown läuft der Roboter **genauso ruhig wie ohne** — **kein Absacken, kein
> Rückwärtslaufen, kein Ducken** (das war der Bug des ersten Entwurfs). (2) **T2 Knick — Nutzen:**
> die Vorderbeine **reichen über die Plateau-Kante nach unten** auf den tieferen Boden → er kommt
> **besser über den Knick**. Stage 4 **isoliert** (`leveling_enable:=false`).

## Konventionen

- **Sourcing** je Terminal: `source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash`
- **Daemon:** vor dem ersten `param set` einmal `ros2 daemon stop`. Adaptiv-Param **live**
  umschalten (A/B im selben Lauf).
- **Pipeline läuft per Default** (`enable_foot_contact:=true`, auch in `ramp_walk.launch.py`).
- **Opt-in:** `adaptive_touchdown_enable` Default **false** → erster Lauf = altes Verhalten (Referenz).

## Einmalig vorab: bauen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## Was sich mit Option A NICHT mehr ändern darf (flacher Boden)

Auf flachem Boden ist „kein Kontakt bis zum Gate" nie der Fall → der Fuß bleibt auf `body_height`
= **exakt nominal**. Daher: **`lat`/`apex`/`dz` der S4-1-Diagnose ändern sich auf flachem Boden
NICHT** (anders als der erste Entwurf vorhatte — das war die Instabilitätsquelle). Der Beleg auf
flachem Boden ist **Stabilität**, nicht eine Latenz-Verbesserung. Der echte Nutzen zeigt sich am
**Knick** (T2).

`_debug_leg1_contact` (gait_node-Terminal, bei jeder Bein-1-Flanke):
```
L1 contact RISE | cmd_z=-0.0800 act_z=-0.0717 dz=8.3mm bh=-0.0800 phase=stance0.27
```
→ auf flachem Boden mit adaptiv AN sollte `cmd_z` in der Stance bei **−0.0800 (= body_height)**
bleiben und **nie tiefer** (kein −0.09/−0.10). `dz` bleibt ~8 mm (Kugelradius), wie ohne adaptiv.

---

## T1 — Flach: Stabilitäts-A/B (darf NICHT mehr absacken/rückwärts)

**▶ Terminal 1 — flach starten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0 gait_pattern:=tripod leveling_enable:=false
```
⏳ aufstehen abwarten (~12–15 s). (`leveling_enable:=false` → Stage 4 isoliert.)

**▶ Terminal 2 — fahren + adaptiv live umschalten:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
# A) Referenz (adaptiv AUS, Default): vorwärts laufen, ~10 s beobachten
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
# B) Adaptiv AN (während er läuft):
ros2 param set /gait_node adaptive_touchdown_enable true
# ... weiter ~15 s beobachten, mehrmals stoppen/anfahren (Ctrl-C auf den pub + erneut starten) ...
```

**✅ Erwartung Option A:** mit AN läuft er **genauso** wie mit AUS — **kein Absacken des Körpers,
kein Rückwärtslaufen, kein Ducken**, auch über mehrere Start/Stopp-Zyklen hinweg. `cmd_z` in der
Stance bleibt bei −0.0800 (Bein-1-Log). **Das ist der Stabilitäts-Beleg.**

> ⚠️ Falls er mit AN doch absackt/rückwärts läuft → bitte melden (mit ein paar `L1 contact`-Zeilen
> + `cmd_z`-Werten); dann stimmt das Gate/Lag-Timing für diesen `cycle_time` nicht.

**Stoppen:** `Ctrl-C` auf den `cmd_vel`-Publisher.

---

## T2 — Knick: kommt er mit adaptiv besser über die Kante?

**▶ Terminal 1 — Rampe mit Knick/Plateau:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=8.0 gait_pattern:=tripod leveling_enable:=false
```
⏳ aufstehen abwarten.

**▶ Terminal 2 — auf den Knick zufahren, A/B:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 daemon stop
# A) adaptiv AUS (Default): langsam auf die Plateau-Kante zu
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'
# B) adaptiv AN (neuer Anlauf / Roboter neu positionieren):
ros2 param set /gait_node adaptive_touchdown_enable true
```

**✅ Erwartung (qualitativ):** mit AN **reichen die Vorderbeine am konvexen Plateau-Scheitel nach
unten** auf den tieferen Boden (statt in der Luft an fester Höhe zu „landen") → er kommt **sichtbar
besser/sicherer über den Knick**. In den Bein-1-Logs am Knick darf `cmd_z` dann **unter −0.0800**
gehen (Nachreichen). Kein Anspruch auf scharfe Stufen (35°-Bordstein) — das bleibt S4-6/free-gait.

---

## T3 (optional) — Live-Tuning des Probe-Gates

Falls er am Knick zu wenig/zu spät nachreicht: Gate früher / Fenster länger / tiefer:
```bash
ros2 daemon stop
ros2 param set /gait_node touchdown_probe_start_stance_phase 0.30   # früher suchen (∈[0,1))
ros2 param set /gait_node touchdown_search_end_stance_phase 0.7     # länger suchen (> probe_start)
ros2 param set /gait_node touchdown_max_extra_depth 0.025           # tiefer reichen (m)
```
> **Wichtig:** `probe_start` **nicht zu klein** wählen — es muss **größer als der Kontakt-Lag in
> Stance-Phasen** sein (bei `cycle_time=2.0` ≈ 0.27), sonst beginnt das Suchen auf flachem Boden
> bevor der laggy Kontakt registriert → Absacken (genau der alte Bug). Default 0.35 hat Marge.
> Ungültige Werte werden abgewiesen (`probe_start ∈ [0,1)`, `search_end ∈ (0,1]`, `probe_start <
> search_end`, `max_extra_depth ≥ 0`).

---

## Befund (Sim-Verify ✅ — ramp 8°)

**Option A ist Sim-bestätigt: stabil + selektives Nachreichen.**
- **Stabilität (Kern-Ergebnis):** `cmd_z` in der Stance bleibt kontrolliert — flach/sanfter Hang
  exakt **−0.0800**, am **konvexen Plateau-Scheitel** (pitch −8°→0°) geführt bis **−0.0862** (~6 mm
  Nachreichen) und zurück. `dz` durchweg **8–14 mm**. **Kein** Floor-Durchsacken, **kein**
  Wegsacken/Rückwärtslaufen mehr (vs. Erst-Entwurf, der instabil war).
- **Selektiv:** nur der konvexe Übergang löst Nachreichen aus; konkave Ecke (flach→Hang) + flacher
  Boden → `cmd_z` bleibt −0.0800 (korrekt nichts). Ohne `adaptive_touchdown_enable` bleibt `cmd_z`
  auch am Scheitel −0.0800.
- **„Mit/ohne ähnlich" erklärt:** Nachreich-Hub nur ~6 mm (sanfter 8°-Scheitel verlangt nicht mehr);
  das sichtbare Bild dominiert das **Roll-Wackeln ±1–2°** = prinzipbedingtes **Tripod-CoG-Wackeln**
  (kein Touchdown-Effekt). **Sichtbarer Payoff braucht eine Stufe/scharfen Knick → S4-6.**
- **Diagnose-Hinweis:** hohe `apex`-Zähler am Hang = kumulatives **Artefakt** (`contact_timeout`
  0.1 s hält das Bool in den Schwung); **`miss 0`** überall → kein echter verpasster Touchdown.
