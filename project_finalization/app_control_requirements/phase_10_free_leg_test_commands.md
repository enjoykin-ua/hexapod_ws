# Phase 10 — Test-Befehle: Show „Free-Leg" (Simulation)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:** **▶ ROS** = Desktop-Terminal ·
> **▶ App** = echte App (Android-Session) · **▶ Offline** = reine Rechnung, kein Roboter.
>
> **Ziel:** Der Roboter stützt sich auf die 4 hinteren Beine, die 2 Vorderbeine folgen den Sticks.
> Gestartet aus der App über `show_mode = free_leg`.
> Plan: [`phase_10_free_leg_plan.md`](phase_10_free_leg_plan.md) · Progress:
> [`phase_10_free_leg_progress.md`](phase_10_free_leg_progress.md).
>
> ⚠️ **Reihenfolge:** §1 (Offline) → §2 (Unit) → §3 (Sim ohne App) → §4 (Sim mit App) → §5 (Grenzen).
> §3 vor §4, weil du in §3 ohne Handy siehst, ob die Pose überhaupt stimmt.
>
> **§3 und §4 sind zwei verschiedene Startwege — nicht gleichzeitig laufen lassen:**
> §3 startet mit `ramp_walk.launch.py` alles auf einmal (Gazebo + Roboter + Aufstehen) — schnell zum
> Hinsehen. §4 startet nur die **Always-On-Schicht**; den Roboter fährt dann die **App** hoch, genau
> wie am echten Hexapod. Beides zusammen kollidiert auf Port 9090.

---

## 0. Was vorher schon feststeht

Diese Werte sind **offline belegt** (§1) und in den Defaults eingetragen — du testest, ob sich der
Roboter auch so verhält:

| | Wert |
|---|---|
| Neutral-Pose Vorderbein | radial **0.19**, lateral **0.04**, z **0.00** |
| Stick-Skalen | lat **0.04**, vert **0.05**, Trigger **0.03** |
| Körper-Rückversatz / Neigung | **0.060 m** / **5°** (Nase hoch) |
| CoG-Marge | **44.7 mm** neutral, **38.6 mm** Worst-Case über die ganze Stick-Hülle |
| Fuß-Abstand vorne | **0.34 m** neutral, per Stick auf **0.29 m** zusammenführbar |
| Bodenfreiheit | **15 mm** im tiefsten Punkt |

---

## 1. Offline-Auslegung nachvollziehen (▶ Offline)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
python3 tools/show_pose_cog_check.py \
  --radial 0.160 --body-height -0.065 \
  --show-radial 0.19 --show-lat 0.04 --show-z 0.00 \
  --pitch-deg 5 --margin-goal 0.030 --shift-max 0.060 \
  --sweep --lat-scale 0.04 --vert-scale 0.05 --radial-scale 0.03 --steps 5
echo "EXIT=$?"
```
**✅ Erwartung:** `AUSLEGUNG BESTANDEN (FL-T1/T2/T3)`, `EXIT=0`, und die drei Gates auf `OK`:
Hülle ≥ 95 % (ist 98 %), Worst-Case-Marge ≥ 30 mm (ist 38.6), Bodenfreiheit ≥ 10 mm (ist 15).

**Gegenprobe, dass das Tool wirklich prüft** (muss **durchfallen**):
```bash
python3 tools/show_pose_cog_check.py --radial 0.160 --body-height -0.065 \
  --show-radial 0.19 --show-lat 0.04 --show-z 0.00 --pitch-deg 5 \
  --sweep --lat-scale 0.09 --vert-scale 0.05 --radial-scale 0.03 --shift-max 0.060
echo "EXIT=$?"
```
**✅ Erwartung:** `AUSLEGUNG DURCHGEFALLEN`, `EXIT=1` — mit lat-Skala 0.09 sprengt der Stick das
Coxa-Limit. Wenn *das* auch „bestanden" meldet, prüft das Tool nicht richtig.

---

## 2. Unit-Tests (▶ ROS)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --symlink-install --packages-select hexapod_gait hexapod_teleop
colcon test --packages-select hexapod_gait hexapod_teleop
colcon test-result --test-result-base build/hexapod_gait --all
colcon test-result --test-result-base build/hexapod_teleop --all
```
**✅ Erwartung:** `hexapod_gait: 560 tests, 0 errors, 0 failures`,
`hexapod_teleop: 64 tests, 0 errors, 0 failures` (je 1 skipped = Bestand).

Darin enthalten sind die Phase-10-Nachweise: die **27 wieder entsperrten** Engine-Tests
(`test_show_pose.py`), die neuen Node-Tests (`free_leg` startet/beendet, Stance-Wechsel,
abgebrochener Start), der **Massen-Regressionstest** (`test_mass_model.py` — Default unverändert)
und die **Gate-Trennung** im Teleop.

---

## 3. Sim ohne App — sieht die Pose gut aus? (▶ ROS)

```bash
# Terminal 1 — Sim + Stack (Auto-Standup)
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py
```
Warten, bis der Roboter steht.

```bash
# Terminal 2 — Show starten (ohne App: direkt den Param setzen)
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node show_mode free_leg
```

**✅ Erwartung — die Kette in dieser Reihenfolge:**
1. Der Roboter wechselt **zuerst auf die tiefe Stance** (falls er nicht schon tief steht) — das ist
   gewollt, kein Fehler.
2. Der Körper fährt **zurück** (alle 6 Füße bleiben am Boden).
3. Die **beiden Vorderbeine heben ab**, der Körper **lehnt sich 5° zurück** (Nase hoch).
4. Gesamtdauer bis oben: **~7 s** (Stance-Wechsel + 4 s Eintritt).

**Was du dir dabei ansiehst (das ist der eigentliche Zweck):**
- Zeigen die Vorderbeine **nach vorne** statt schräg nach außen? (Das war die alte Kritik.)
- Steht der Roboter **ruhig**, ohne zu kippeln?
- Berührt ein Vorderbein den Boden? (Darf nicht — 15 mm Freiheit im tiefsten Punkt.)

```bash
# Zustand prüfen
ros2 topic echo /hexapod/status --once
```
**✅ Erwartung:** `"state":"SHOW_ACTIVE"`, `"show_mode":"free_leg"`, `"stance":"tief"`.

**Beine bewegen (ohne Controller, per Topic):**

> ⚠️ **Zwei Dinge, die man wissen muss, sonst wundert man sich:**
> 1. `/cmd_show` trägt **normierte Stick-Werte −1…+1**, **nicht** Meter. Der Node multipliziert
>    selbst mit den Skalen (`show_lat_scale` 0.04 usw.). `1.0` = Vollausschlag = 4 cm seitlich.
> 2. Es gibt einen **Staleness-Schutz**: kommt länger als `cmd_vel_timeout` (0,5 s) kein
>    `/cmd_show`, fallen die Offsets auf 0 und die Beine federn in die Neutral-Pose zurück (das
>    ist der Ersatz für „R1 losgelassen"). Ein einmaliges `pub -1` wirkt also nur einen Wimpernschlag
>    — deshalb hier **`-r 10`** (dauerhaft senden) und mit `Strg-C` beenden.

```bash
# Reihenfolge: [l6_lat, l6_vert, l6_radial, l1_lat, l1_vert, l1_radial], je -1..+1
# linkes Vorderbein ganz hoch, rechtes ganz runter (Strg-C zum Beenden):
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray \
  "{data: [0.0, 1.0, 0.0, 0.0, -1.0, 0.0]}"

# beide nach innen zusammenführen (das ist die interessante Geste):
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray \
  "{data: [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]}"

# beide nach außen spreizen:
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray \
  "{data: [-1.0, 0.0, 0.0, -1.0, 0.0, 0.0]}"

# beide ausstrecken (Trigger-Äquivalent, einseitig 0..1):
ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray \
  "{data: [0.0, 0.0, 1.0, 0.0, 0.0, 1.0]}"
```
**✅ Erwartung:** Die Beine folgen weich (rate-limitiert), fahren nirgends ruckartig, und der
Roboter bleibt stabil. Nach `Strg-C` federn sie binnen ~0,5 s in die Neutral-Pose zurück. Am
Anschlag **hält** das Bein einfach — es darf **kein** Freeze und kein IK-Fehler auftreten.

**Fuß-Abstand nachmessen** (die Zahl aus der Auslegung — 0,34 m neutral, 0,29 m zusammengeführt):
```bash
ros2 run tf2_ros tf2_echo base_link leg_1_foot_link 2>/dev/null | head -12
```

**Show verlassen + weiterlaufen (der Round-Trip ist das Wichtigste):**
```bash
ros2 param set /gait_node show_mode none
# ~3 s warten, dann:
ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.03}}"
```
**✅ Erwartung:** erst gehen die Vorderbeine **runter**, dann fährt der Körper **vor**, Zustand →
`STANDING` — und der Roboter **läuft danach normal**. Genau hier ist die alte Show früher
hängengeblieben.

---

## 4. Sim mit App — der echte App-Flow (▶ ROS + App)

> **Eigenständiger Test — §3 vorher beenden.** §3 startet mit `ramp_walk.launch.py` den kompletten
> Stack in einem Rutsch (Gazebo + Roboter + Aufstehen). **Der App-Weg ist ein anderer:** im Terminal
> läuft nur die **Always-On-Schicht**, und *die App* fährt den schweren Stack hoch — genauso wie am
> echten Roboter. Beides gleichzeitig kollidiert (zwei rosbridge auf Port 9090, zwei Gazebo).
>
> ```bash
> # falls §3 noch läuft: im Terminal 1 mit Strg-C beenden und kurz warten
> pgrep -fa "gz sim|ramp_walk|rosbridge" || echo "sauber, nichts laeuft mehr"
> ```

### 4.1 Terminal: nur die Always-On-Schicht starten (▶ ROS)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py
```
Das ist der Sim-Default (`mode:=sim`, `scene:=ramp`). **Es startet KEIN Gazebo und keinen Roboter** —
nur rosbridge (Port 9090), `bringup_launcher`, `shutdown_supervisor` und `hmi_status`. Genau das,
was am Pi ab Boot als Dienst läuft.

**Prüfen (zweites Terminal):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 node list
```
**✅ Erwartung:** `rosbridge_websocket`, `rosapi`, `bringup_launcher`, `shutdown_supervisor`,
`hmi_status` — und **kein** `gait_node` (der kommt erst mit dem Stack).

### 4.2 Die Adresse für die App (▶ ROS)

```bash
hostname -I | awk '{print $1}'
```
Diese IP im Verbinden-Screen der App eintragen, Port **9090**. Handy und Desktop müssen im selben
Netz sein. **Video-Modus: Sim** (die App wählt dafür `type=mjpeg`; am Pi wäre es `ros_compressed`).

### 4.3 In der App: verbinden → starten → aufstehen (▶ App)

| Schritt | ✅ Erwartung |
|---|---|
| **Verbinden** | Verbindung steht; Status-/Config-Panel füllt sich (die Always-On-Topics sind sofort da). Der Roboter existiert noch nicht |
| **„Hexapod starten"** | Jetzt erst startet Gazebo, der Roboter wird gespawnt und liegt **auf dem Bauch** (`SAT`) — das ist der Bauch-Start, kein Fehler. Dauert spürbar: der `gait_node` kommt erst nach `gait_delay` (12 s), die App wartet bis zu 40 s auf den ersten Status-Tick |
| **„Aufstehen"** | Roboter steht auf → `STANDING` |

> ⚠️ Wenn du hier ungeduldig wirst: „Stack läuft" ist **nicht** „bedienbar". Warte, bis die App
> „Aufstehen" freigibt.

### 4.4 Die Show aus der App (▶ App)

| Schritt | ✅ Erwartung |
|---|---|
| Show-Menü öffnen | **„Free-Leg" ist auswählbar** — der Eintrag stand schon immer im Menü, jetzt tut er etwas |
| **„Free-Leg" wählen** | Der Roboter wechselt zuerst auf die **tiefe** Stance (falls nötig), fährt den Körper zurück, hebt die **beiden Vorderbeine** und lehnt sich **5° zurück**. Gesamt **~7 s**. Der Menüpunkt zeigt Free-Leg **sofort** als aktiv, nicht erst nach dem Stance-Wechsel |
| **R1 halten** + linker Stick | linkes Vorderbein bewegt sich (hoch/runter, seitlich) |
| **R1 halten** + rechter Stick | rechtes Vorderbein bewegt sich |
| **R1 halten** + L2 / R2 | linkes / rechtes Bein streckt sich aus (~3 cm — bewusst wenig) |
| **R1 loslassen** | beide Beine federn weich in die Neutral-Pose zurück |
| **„Normalbetrieb"** wählen | erst die Vorderbeine runter, dann der Körper vor → `STANDING`; danach **normal fahrbar** |

**Der Punkt, auf den es ankommt:** Die App wurde für Phase 10 **nicht angepasst**. Musste sie doch,
stimmt etwas am Contract-Verständnis nicht (v0.14: keine App-Änderung nötig).

**Mitlesen im zweiten Terminal (optional):**
```bash
ros2 topic echo /hexapod/status --once      # state + show_mode + stance
ros2 topic echo /cmd_show                   # was der Controller schickt, 6 Werte
```

### 4.5 Aufräumen

In der App **„Stack neu starten"** → **stoppen**, oder direkt im Terminal 1 `Strg-C`
(beendet Always-On **und** den als Subprozess gestarteten Stack).

---

## 5. Grenzen und Fehlerfälle (▶ ROS)

| Test | Befehl / Aktion | ✅ Erwartung |
|---|---|---|
| **Show aus dem Gehen** | während `cmd_vel` läuft: `ros2 param set /gait_node show_mode free_leg` | **Reject** mit `requires STATE_STANDING` — Show nur aus dem Stand |
| **Show bei E-Stop** | `ros2 service call /hexapod_estop std_srvs/srv/Trigger {}` dann `show_mode free_leg` | **Reject**; nach `/hexapod_recover` geht es wieder |
| **Rückweg immer offen** | mitten im Eintritt (~2 s nach dem Start) `show_mode none` | Show bricht sauber ab und endet in STANDING |
| **Hinsetzen aus der Show** | `ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}` | **Reject** („erst show_mode=none") — bewusst, sonst sackt er aus der 4-Bein-Stütze |
| **Extremer Stick** | `ros2 topic pub -r 10 /cmd_show std_msgs/msg/Float64MultiArray "{data: [2.0, 2.0, 2.0, 2.0, 2.0, 2.0]}"` (doppelter Vollausschlag) | Beine gehen bis zum Limit und **halten** dort; **kein** Freeze, kein IKError im Log |
| **Selbstkollision** | Beine maximal zusammenführen (lat 0.04 beidseitig) und dabei in RViz/Gazebo **hinsehen** | Beine berühren sich **nicht**. ⚠️ Es gibt keinen automatischen Kollisions-Check im Projekt — das hier ist die einzige Prüfung |

---

## 6. Was danach kommt (nicht Teil dieses Test-Docs)

- **HW aufgebockt → Boden** (FL.14 im Progress) — CoG-kritisch, erst nach grüner Sim.
- **IMU-Messung** (FL.15): 5° kommandieren, `/imu/monitor` ablesen. Die Differenz ist die
  **Servo-Durchsackung** — die Zahl, die erklärt, warum die alte Show auf HW nach vorne kippte.
  ```bash
  # auf dem Pi, waehrend die Show laeuft:
  ros2 topic echo /imu/monitor --once
  ```
  Abweichung ≤ 1–2° → Sache erledigt. Größer → Soll-Pitch überhöhen (z.B. 8° für real 5°).
