# TF-2 — Test-Befehle (interaktiv, komfortabel)

> Du führst die Tests aus, knappe Status-Meldung zurück. **Jeder Testfall ist
> eigenständig** — eigene Terminals + Befehle, setzt **nicht** voraus, dass aus
> einem vorherigen Test noch etwas läuft.
>
> **Ziel TF-2:** den Körper beim Hang-Laufen **sauber parallel zum Boden** halten
> (flach → waagerecht, Hang → hangparallel) und das **Wackeln dämpfen** (Gyro-D).
> Modus `terrain` = roll→0 / pitch folgt Hang; `horizontal` = Voll-Leveln (Stufe 2).

## Konventionen (wichtig — spart Frust)

- **Pro Test:** Terminals frisch öffnen; jeder Block beginnt mit dem Sourcing.
- **Zwischen zwei Tests:** alle Terminals mit **`Strg-C`** beenden.
- **Sourcing-Zeile** (steht in jedem Block):
  ```bash
  source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
  ```
- ⚠️ **Strikte Startreihenfolge** (wie TF-1): `/imu/slope`, `/imu/monitor` & die
  `gait_node`-Params existieren **erst, wenn der gait_node läuft**. Darum immer:
  **1) Sim → 2) gait_node (aufstehen abwarten) → 3) Beobachtungs-Terminals → 4) fahren/tunen.**
- **`leveling_enable` ist Default `false`** (Opt-in) → in den Tests via `ros2 param set` an.
  Modus-Default ist **`terrain`**.
- **Flach spawnen** ist Pflicht (gz-IMU spawn-referenziert) — `ramp.launch.py` tut das.

---

## Einmalig vorab: bauen

**Terminal (einmalig):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_kinematics hexapod_gait hexapod_bringup hexapod_gazebo --symlink-install
```

---

## ⭐ Schnellstart (EIN Befehl: Sim + Spawn + Aufstehen)

Statt zwei Terminals (ramp + gait) nacheinander: **ein** Launch startet Gazebo +
Ramp-Welt + Spawn **und** (nach ~12 s, wenn die Controller hochgekommen sind) den
gait_node, der **automatisch aufsteht**. Stabilisierung per Default **an** (`terrain`-Modus).

> 🛑 **WICHTIG: NICHT zusätzlich `gait.launch.py` starten!** `ramp_walk.launch.py` startet
> den gait_node **schon selbst**. Wenn du danach noch die manuelle Prozedur (T1, Terminal 2
> mit `gait.launch.py`) ausführst, läuft ein **zweiter** `/gait_node` — beide schicken
> Befehle an dieselben Controller und **kämpfen gegeneinander** (Roboter zuckt/kämpft gegen
> den Stand). **Schnellstart ODER manuelle Prozedur — niemals beides.**

**▶ Terminal 1 — alles starten. Gangart am besten gleich hier als Arg setzen:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py gait_pattern:=wave
# weitere Varianten:
#   ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=16.0 gait_pattern:=ripple
#   ros2 launch hexapod_bringup ramp_walk.launch.py leveling_enable:=false   # passiv (TF-1)
#   ros2 launch hexapod_bringup ramp_walk.launch.py gait_delay:=18.0         # langsamer Rechner
# gait_pattern: tripod | wave | tetrapod | ripple
#   → wave/ripple wackeln am meisten → Dämpfung am besten sichtbar; tripod ist wackelfrei.
```
⏳ **Warten,** bis der Roboter **steht** (Auto-Standup; ~12–15 s nach Start).

**▶ Terminal 2 — prüfen, beobachten, fahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# ⚠️ ZUERST den Daemon frisch machen — sonst ist `node list`/`param set` LEER bzw.
#    "Node not found", OBWOHL der gait_node längst läuft (stale-Daemon-Bug in Jazzy):
ros2 daemon stop
ros2 node list                    # jetzt: /gait_node + gazebo + controller_manager etc.
#   (noch leer? 1× wiederholen — der frische Daemon braucht ~2 s zum Entdecken;
#    immer noch leer? -> `ros2 node list --no-daemon` zeigt sie direkt = Daemon defekt)
ros2 topic echo /imu/slope        # Hang-Schätzung (oder /imu/monitor für rohe Lage)
# in den Hang laufen:
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```

**Gangart NACH dem Start wechseln** (statt per Launch-Arg) — nach dem `daemon stop` oben:
```bash
ros2 param set /gait_node gait_pattern wave    # tripod | wave | tetrapod | ripple (STANDING-only)
```
> Der `/gait_node` aus `ramp_walk` **ist** der „Aufsteh-Node" — er macht den Auto-Standup
> **und** das Laufen **und** hält die `gait_pattern`/`leveling_*`-Params. Es gibt keinen
> separaten „Aufsteh-Befehl"; du startest `gait.launch.py` **nicht** zusätzlich.

> Die ausführlichen Einzel-Tests **T1–T4 unten sind die ALTERNATIVE** (manuelle Zwei-Terminal-
> Prozedur, mehr Kontrolle). **Entweder Schnellstart ODER T1–T4 — nicht beides gleichzeitig.**

---

## Was du beobachtest

- **`/imu/monitor`** (`geometry_msgs/Vector3`): rohe Körperlage. `x`=roll, `y`=pitch,
  `z`=yaw (rad, ×57.3=Grad). Auf der um Y geneigten Rampe zählt **`y` (pitch)**.
- **`/imu/slope`** (`std_msgs/Float64MultiArray`): `data:[slope_roll_deg, slope_pitch_deg]` —
  die langsame Hang-Schätzung (Soll: trackt den echten Hang).
- **Visuell in Gazebo:** bleibt der Körper **ruhig & parallel** zum Hang? Wackelt er weniger
  als mit TF-1 (passiv)? Schwingt der Plateau-Übergang sauber aus?

```bash
# in je einem eigenen Terminal (NACH gait_node-Standup):
ros2 topic echo /imu/monitor
ros2 topic echo /imu/slope
```

---

## TU — Unit-Tests (ohne Sim)

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon test --packages-select hexapod_kinematics hexapod_gait \
  --pytest-args -k "balance or leveling or slope or tip" \
  --event-handlers console_direct+
colcon test-result --verbose
```
**Erwartung:** grün — u.a. Gyro-D (Vorzeichen/Totband/Clamp/Closed-Loop-Dämpfung),
terrain-vs-horizontal-Wiring, pitch-Residual-Regelung, Modus-Validierung.

---

# ── Manuelle Zwei-Terminal-Prozedur (Alternative zum Schnellstart) ──

> 🛑 **Nur nutzen, wenn du den ⭐ Schnellstart oben NICHT verwendet hast.** Hier startest du
> Sim und gait_node **getrennt** (Terminal 1 = `ramp.launch.py` ohne gait_node, Terminal 2 =
> `gait.launch.py`). Hast du oben schon `ramp_walk.launch.py` gestartet, läuft der gait_node
> bereits — dann hier **nichts** mehr starten, sonst zwei konkurrierende `/gait_node`.

## T1 — terrain-Modus: Körper bleibt hangparallel + Wackeln gedämpft (8°)

**▶ Terminal 1 — Sim + Rampe 8° (zuerst):**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
```
⏳ **Warten,** bis Gazebo geladen + Roboter (flach) sichtbar.

**▶ Terminal 2 — gait_node (als Zweites):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro
```
⏳ **Warten,** bis der Roboter **aufgestanden** ist.

**▶ Terminal 3 — Hang-Schätzung beobachten (als Drittes):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /imu/slope
```

**▶ Terminal 4 — Stabilisierung AN (terrain ist Default) + losfahren:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# Stabilisierung einschalten (Modus terrain ist Default):
ros2 param set /gait_node leveling_enable true
# in den Hang laufen:
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```

**Erwartung:** Roboter läuft in die Rampe; `/imu/slope` pitch → ~8°; der Körper bleibt
**hangparallel** (NICHT waagerecht-gezwungen) und **ruhiger** als ohne Stabilisierung,
roll bleibt nahe 0. **Kein** Safety-Freeze. Plateau-Übergang oben schwingt sauber aus.

**Gegenprobe „Stabilisierung aus" (optional):** in Terminal 4
`ros2 param set /gait_node leveling_enable false` → Wackeln nimmt sichtbar zu (= TF-1 passiv).

---

## T2 — terrain vs. horizontal direkt vergleichen

> Wie T1 (Terminals 1–3), in Terminal 4 zwischen den Modi umschalten — **am Hang stehend**
> (kein cmd_vel), damit der Unterschied klar sichtbar ist.

**▶ Terminal 4:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node leveling_enable true
# terrain (Default): Körper bleibt am Hang geneigt (hangparallel):
ros2 param set /gait_node leveling_mode terrain
#   → /imu/monitor pitch bleibt ~8° (Körper folgt dem Hang)
# horizontal: Körper richtet sich waagerecht auf (Stufe-2-Verhalten):
ros2 param set /gait_node leveling_mode horizontal
#   → /imu/monitor pitch fährt Richtung 0 (bis zum Clamp ~10° STANDING)
# zurück:
ros2 param set /gait_node leveling_mode terrain
```

**Erwartung:** `terrain` → pitch bleibt ~Hangwinkel (parallel, natürlich); `horizontal` →
pitch geht sichtbar Richtung 0 (Körper hebt die Nase, „sprawliger" Look). Das ist der
beabsichtigte Unterschied. Reject-Probe: `ros2 param set /gait_node leveling_mode bogus`
→ schlägt fehl (`valid: horizontal | terrain`), Node läuft weiter.

---

## T3 — Wackel-Dämpfung tunen (Kd / slew_max) — Schritt für Schritt

> **Kern von TF-2.** Sim wie T1 (terrain, `leveling_enable true`), beim Hochlaufen
> (`/cmd_vel` aktiv) das Wackeln in Gazebo + `/imu/monitor` beobachten. **Eine** Änderung
> pro Schritt, dann schauen. Der empfohlene Pfad: **erst Kd hoch, dann (falls nötig) slew_max**.

**▶ Terminal 5:**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash

# Ausgangswert (Default):
ros2 param get /gait_node leveling_kd            # 0.03

# Schritt 1 — Kd erhöhen, bis das Wackeln sichtbar abnimmt:
ros2 param set /gait_node leveling_kd 0.06
#   beobachte: roll/pitch in /imu/monitor zappeln weniger, Körper „steht ruhiger"

ros2 param set /gait_node leveling_kd 0.10
#   beobachte: weiter ruhiger? ODER beginnt es zu zittern/zappeln (überdämpft/Rauschen)?

# Schritt 2 — wenn die Dämpfung zu TRÄGE wirkt (D wird vom Slew gebremst):
ros2 param set /gait_node leveling_slew_max_dps 16.0
#   beobachte: die Korrektur darf jetzt schneller folgen → Dämpfung greift zügiger
#   ⚠️ höher = mehr Stell-Tempo = mehr Fuß-Scrub-Risiko → nicht übertreiben

# Schritt 3 — zu aggressiv? wieder runter:
ros2 param set /gait_node leveling_kd 0.04
ros2 param set /gait_node leveling_slew_max_dps 8.0
```

**Erwartung / Leseanleitung:**
- **`Kd` zu klein** → kaum Dämpfung (wie TF-1, wackelt).
- **`Kd` gut** → Körper merklich ruhiger, Schwingungen klingen schneller ab.
- **`Kd` zu groß** → Zittern/Zappeln (D verstärkt Rauschen / regt selbst an) → zurücknehmen.
- **Dämpfung träge trotz hohem Kd** → `slew_max` anheben (D wird sonst vom Slew gebremst).
- ⚠️ In Sim ist die IMU **rauschfrei** → das Rausch-Limit von Kd siehst du hier kaum; auf
  echter HW `Kd` eher konservativ.

Notiere die Kombination (`Kd`, `slew_max`), bei der es am ruhigsten läuft — das ist der
Startpunkt fürs HW-Tuning.

> **Vergleichen OHNE Neustart** (gegen den „Roboter ist schon weggelaufen"-Frust): du musst
> ihn nicht zurücksetzen — **rückwärts fahren** bringt ihn den Hang wieder runter, dann mit
> anderem Wert wieder hoch:
> ```bash
> # runter (rückwärts):
> ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: -0.05}}'
> # Wert umschalten (Strg-C auf dem pub, dann):
> ros2 param set /gait_node leveling_kd 0.0     # "vorher"
> # wieder hoch:
> ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
> ```
> So fährst du dieselbe Steigung mehrfach mit verschiedenen Einstellungen — identische
> Bedingungen, kein Neustart. (Stoppen = `'{}'` publishen oder den pub mit Strg-C beenden.)

---

## T4 — Plateau-Übergang (Wackeln am Knick gedämpft?)

> Wie T1, Fokus auf den **Übergang Hang→Plateau** oben. TF-2 löst **nicht** das
> Kanten-/Bodenkontakt-Problem (das ist Stufe 4), aber es soll das **Wackeln** beim
> Übergang sichtbar dämpfen.

**Erwartung:** der Körper schwingt am Plateau-Scheitel **weniger** und beruhigt sich
**schneller** als mit TF-1 (passiv). Bleibt ein Bein an der Kante „in der Luft" hängen,
ist das **erwartet** (Stufe-4-Thema, kein TF-2-Versagen).

---

## Troubleshooting

**`ros2 node list` ist LEER bzw. `ros2 param set /gait_node ...` → „Node not found"**,
obwohl der Roboter steht und auf `cmd_vel` läuft — d.h. der gait_node **läuft** (sonst
keine Bewegung), aber der **ROS2-Daemon** zeigt eine veraltete/leere Discovery-Liste
(bekannter Jazzy-Bug, v.a. wenn ein Daemon aus einer früheren Session stale ist).

**Beweis + Fix:**
```bash
ros2 node list --no-daemon          # umgeht den Daemon → zeigt die Nodes? dann ist's der Daemon
ros2 daemon stop                    # alten Daemon killen; nächster Befehl startet einen frischen
ros2 node list                      # ggf. 1× wiederholen (Discovery braucht ~2 s)
ros2 param set /gait_node gait_pattern wave   # greift jetzt
```
- **NICHT** stattdessen `gait.launch.py` starten — das wäre ein **zweiter** `/gait_node`,
  der gegen den ersten kämpft (Roboter zuckt). Der gait_node aus `ramp_walk` läuft schon.
- **Gangart** umgeht den Daemon ganz als Launch-Arg: `ros2 launch ... ramp_walk.launch.py gait_pattern:=wave`.
- **`leveling_kd`/`leveling_mode`** haben keinen Launch-Arg → `param set` nötig → einmal
  `ros2 daemon stop`, dann zuverlässig.

## Hinweise / bekannte Grenzen

- **Quer-/Diagonal-Hang:** `terrain` regelt **roll→0** (Geradeaus-Klettern). Seitlich/diagonal
  am Hang richtet es den Seithang-roll bis zum Clamp teilweise auf (kein Umkippen, aber nicht
  „folgend"). Sauberes Quer-Laufen = eigener Nachfolge-Block (roll-Residual + `cmd_vel`-Richtung).
- **Kanten/Stufen** (Plateau-Scheitel, ~35°-Bordstein): **Stufe 4 (Fußtaster)**, kein
  Balance-Problem ([TF-1-Befund](stage_3a_passive_tf_test_commands.md)).
- **Gains = HW-Sache:** Sim validiert die **Logik** (folgt/dämpft korrekt, kein Freeze); die
  finalen `Kd`/`slew_max` werden auf der echten HW nachgezogen (D6: Sim=Logik, HW=Gains).
- **Ground-Truth-Pose** alternativ aus Gazebo:
  `gz topic -et /world/empty/dynamic_pose/info` (Modell „hexapod"-Orientierung).
