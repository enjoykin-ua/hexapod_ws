# Phase 8 — Test-Befehle: Show „Look-Around" (Kamera-Umschauen)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:** **▶ ROS** = Desktop-Terminal ·
> **▶ Pi** = auf dem Roboter (ssh) · **▶ App** = *echte App (Android-Session)*.
>
> **Ziel:** der Roboter steht, **alle 6 Füße bleiben fix am Boden**, und der **Körper** lässt sich
> per Sticks bewegen — rechter Stick = umschauen, linker = wandern, L2/R2 = Höhe, **R1 halten**
> (Dead-Man). Loslassen → federt zurück. Plan:
> [`phase_8_look_around_plan.md`](phase_8_look_around_plan.md) · Progress:
> [`phase_8_look_around_progress.md`](phase_8_look_around_progress.md) · Contract §6c (v0.13).
>
> **Die Show ist app-exklusiv** — gestartet wird sie über den Param `show_mode`. Für den Sim-Test
> setzt du ihn von Hand (`ros2 param set`), die App macht später denselben Aufruf.

---

## 0. Offline — Envelope-Gate (▶ ROS, ohne Sim)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
python3 tools/look_around_envelope_check.py
echo "EXIT=$?"
```
**✅ Erwartung (T8.13):** letzte Zeile `GREEN — Einzelachsen + Stick-Paare + CoG-Marge über alle
Stance-Höhen ok`, `EXIT=0`. Pro Stance-Höhe: Gate 1+2 alle `GREEN` (CoG ~166–200 mm), Gate 3 alle
`GREEN`.

Einzelachs-Maxima zusätzlich sehen (informativ):
```bash
python3 tools/look_around_envelope_check.py --sweep
```

---

## 1. Unit-Tests (▶ ROS) — ohne Sim/HW

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --packages-select hexapod_gait hexapod_teleop hexapod_supervisor
colcon test --packages-select hexapod_gait hexapod_teleop hexapod_supervisor
colcon test-result --all
```
**✅ Erwartung (T8.9):** `0 errors, 0 failures` über alle drei Pakete (gait ~548, teleop ~48,
supervisor 34), Lint (`flake8`/`pep257`) grün.

Nur die Phase-8-Tests gezielt:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
python3 -m pytest src/hexapod_gait/test/test_body_pose.py \
                 src/hexapod_gait/test/test_body_pose_node.py \
                 src/hexapod_teleop/test/test_joy_to_twist.py -q
```

---

## 2. Sim-Test **ohne App** (PS4-/Debug-Pfad)

> Braucht einen PS4-Controller am Desktop. **Wenn du mit der App testest, überspring diesen
> Abschnitt und geh direkt zu §3** — dort steht der Ein-Befehl-App-Ablauf. Beide Wege laufen gegen
> denselben ROS-Code; dieser hier ist der schnellere für Einzelachsen-Checks per `ros2 topic pub`.

### Terminal 1 (▶ ROS) — Sim-Stack hoch (Ein-Befehl-Bringup, Auto-Standup)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup ramp_walk.launch.py
```
> Warten, bis der Roboter **steht** (Log `Engine state: … -> STANDING`, ~15–20 s).

### Terminal 2 (▶ ROS) — Status mitlesen (laufen lassen)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /hexapod/status
```
> Zeigt `state` und **`show_mode`** live (5 Hz).

### Terminal 3 (▶ ROS) — Show starten
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node show_mode look_around
```
**✅ Erwartung (T8.5):** `Set parameter successful`; in Terminal 1 die Zeile
`show_mode: look_around — Körper folgt den Sticks (R1 halten), Füße bleiben fix`;
in Terminal 2 springt `"state"` auf **`BODY_POSE`** und `"show_mode"` auf `look_around`.

### Jetzt mit dem PS4-Controller fahren (▶ ROS)
> Der Controller muss verbunden sein (der Stack startet `joy_node` im controller-Profil).
> **R1 gedrückt halten**, sonst passiert nichts (Dead-Man).

| Eingabe | Erwartung |
|---|---|
| R1 + rechter Stick **hoch/runter** | Körper nickt — **Kamera schaut hoch/runter** (±12°) |
| R1 + rechter Stick **links/rechts** | Körper dreht sich um die Hochachse (±10°) |
| R1 + linker Stick **hoch/runter** | Körper wandert vor/zurück (±50 mm) |
| R1 + linker Stick **links/rechts** | Körper wandert seitwärts (±35 mm) |
| R1 + **R2** / **L2** | Körper hebt/senkt sich (±20 mm) |
| **R1 loslassen** | alles federt sanft in die Ausgangs-Pose zurück |

**✅ Erwartung (T8.7 — der Kern):**
1. Der **Körper** bewegt sich, **die Füße bleiben stehen** (in Gazebo gut an den Fußpunkten zu
   sehen — sie dürfen nicht rutschen oder abheben).
2. Alles fühlt sich weich an, keine Sprünge, kein Ruckeln beim Eintritt/Verlassen.
3. Auch bei **vollem Ausschlag in mehreren Achsen gleichzeitig**: der Roboter friert **nicht** ein
   (kein `Safety-Freeze`, kein `IK failed` im Log) — er wird nur „zäher" in einzelnen Achsen.
4. Loslassen → zurück in die Ausgangs-Pose.

> ⚠️ **Vorzeichen prüfen** (der eine noch offene Punkt): Stick **hoch** soll die **Kamera nach oben**
> schauen lassen, **R2** soll den Körper **heben**. Stimmt eine Richtung nicht, ist es ein Param —
> kein Code. Korrektur live:
> ```bash
> ros2 param set /joy_to_twist sign_body_pose_pitch 1.0     # pitch invertieren
> ros2 param set /joy_to_twist sign_body_pose_yaw -1.0      # yaw invertieren
> ros2 param set /joy_to_twist sign_body_pose_z -1.0        # Höhe invertieren
> ```
> Melde mir, welche Achsen invertiert werden mussten — ich ziehe die Defaults nach.

### Ohne Controller: Achsen einzeln von Hand testen (▶ ROS)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# pitch voll (Kamera hoch), 3 s halten:
ros2 topic pub -r 20 /cmd_body_pose std_msgs/msg/Float64MultiArray \
  "{data: [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]}"
# (Strg-C) -> ohne frische Nachrichten federt der Körper nach 0.5 s selbsttätig zurück
```
> Reihenfolge: `[dx, dy, dz, roll, pitch, yaw]`, jeweils −1..+1. `roll` (Index 3) bleibt v1 wirkungslos.

```bash
# alle Achsen gleichzeitig ans Maximum (Greedy-Clamp sichtbar machen):
ros2 topic pub -r 20 /cmd_body_pose std_msgs/msg/Float64MultiArray \
  "{data: [1.0, 1.0, 1.0, 0.0, 1.0, 1.0]}"
```
**✅ Erwartung (T8.10):** Körper fährt in eine Misch-Pose, **kein** `IK failed`/Freeze im Log.

### Show verlassen (T8.5)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node show_mode none
```
**✅ Erwartung:** Körper federt zurück, `state` geht auf `STANDING`, `show_mode` auf `none` —
**und der Roboter lässt sich sofort wieder normal fahren** (R1 + linker Stick).

### Platzhalter (T8.5)
```bash
ros2 param set /gait_node show_mode dancing
ros2 param get /gait_node show_mode
```
**✅ Erwartung:** `Set parameter successful`, im Stack-Log
`show_mode 'dancing' ist noch nicht implementiert (Platzhalter)`, der Roboter **bleibt STANDING**,
und `ros2 param get` liefert nach ~1 s wieder **`none`** (der Server zieht den wirksamen Wert nach).
Dasselbe mit `free_leg`.

### Gates (T8.6)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
# (a) Show-Start im Lauf -> Reject. Erst losfahren:
ros2 topic pub -r 20 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.03}}" &
sleep 2
ros2 param set /gait_node show_mode look_around      # -> FEHLER erwartet
kill %1
```
**✅ Erwartung:** `Setting parameter failed: show_mode 'look_around' requires STATE_STANDING,
current state=WALKING (set show_mode='none' to leave a running show)`.

```bash
# (b) 'none' ist IMMER erlaubt — auch mitten in der Show (der Rückweg):
ros2 param set /gait_node show_mode look_around
ros2 param set /gait_node show_mode none             # -> muss GELINGEN
```

```bash
# (c) Hinsetzen aus der Show -> Reject mit Grund (v1-Entscheidung §4.6):
ros2 param set /gait_node show_mode look_around
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}
```
**✅ Erwartung:** `success=False`, `message: 'sit_down only from STANDING, state=BODY_POSE'`.

```bash
# (c2) Show-Start bei aktivem Freeze -> Reject (Self-Review-Guard):
ros2 param set /gait_node show_mode none
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
ros2 param set /gait_node show_mode look_around      # -> FEHLER erwartet ("robot is frozen")
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}
```

```bash
# (d) E-Stop greift auch in der Show, Recovery beendet sie:
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
ros2 topic echo /hexapod/status --once      # safety_frozen: true, state: BODY_POSE
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}
ros2 topic echo /hexapod/status --once      # show_mode: none, state: STARTUP_RAMP -> STANDING
```
**✅ Erwartung (T8.12):** nach `recover` steht `show_mode` **von selbst** auf `none` (das App-Menü
darf nicht auf „Kamera-Umschauen" hängen bleiben).

### Walking-Regression (T8.9, live)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param get /gait_node show_mode          # muss 'none' sein
# dann mit dem Controller normal fahren: R1 + linker Stick, Gangart D-Pad, Stance L2/R2
```
**✅ Erwartung:** Laufen, Gangart-Wechsel, Stance-Wechsel, Sitzen/Stehen **unverändert** wie vor
Phase 8.

---

## 3. Sim-Test **aus der App** (T8.7 App-Variante) — der eigentliche Abnahmetest

> Das ist der Weg, den du im Alltag nutzt: **ein Befehl** auf dem Desktop, alles Weitere macht die
> App. Der Direkt-Pfad aus §2 (`ramp_walk.launch.py`) bleibt als PS4-/Debug-Weg bestehen — beide
> laufen gegen denselben ROS-Code.

### Terminal 1 (▶ ROS) — der eine Befehl
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
colcon build --symlink-install --packages-select hexapod_gait hexapod_teleop hexapod_supervisor
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py
```
> Flache Welt. Für Rauhterrain (Kamera + Terrain-Regelkreise scharf):
> `ros2 launch hexapod_bringup always_on.launch.py scene:=rubicon` — dann ~20–30 s warten, bis die
> Welt steht. **Mehr startest du auf dem Desktop nicht** — Gazebo + gait + Teleop startet die App
> selbst über „Hexapod starten".

### Terminal 2 (▶ ROS, optional aber empfohlen) — mitlesen
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 topic echo /hexapod/status
```
> Zeigt `state` (→ `BODY_POSE` während der Show) und `show_mode` live. Läuft erst, wenn der Stack
> über die App gestartet ist.

### Ablauf in der App (▶ App)

| # | Schritt | ✅ Erwartung |
|---|---|---|
| 1 | Verbinden (Desktop-IP, Port 9090) | Verbindung steht, Video kommt nach „Start" |
| 2 | **Hexapod starten** | schwerer Stack läuft, Roboter liegt auf dem **Bauch** (SAT) |
| 3 | **Aufstehen** | `state: STANDING` |
| 4 | Show-Menü öffnen | vier Einträge: Kamera-Umschauen / Dancing / Free-Leg / Normalbetrieb |
| 5 | **„Kamera-Umschauen"** | `state` springt auf **`BODY_POSE`**, `show_mode: look_around` |
| 6 | **R1 halten + rechter Stick** | **das Video schwenkt mit** — hoch/runter + links/rechts |
| 7 | R1 + linker Stick | Körper wandert vor/zurück/seitwärts, **die Füße bleiben stehen** |
| 8 | R1 + L2/R2 | Körper hebt/senkt sich |
| 9 | R1 loslassen | alles federt sanft in die Ausgangs-Pose zurück |
| 10 | mehrere Achsen gleichzeitig voll ausfahren | wird nur „zäher", **kein Einfrieren** (kein `safety_frozen`, kein `IK failed` in Terminal 1) |
| 11 | **„Dancing"** | Meldung „noch nicht implementiert", Roboter bleibt stehen, Menü fällt auf **Normalbetrieb** zurück |
| 12 | **„Normalbetrieb"** | zurück auf `STANDING` — **und sofort wieder normal fahrbar** (R1 + linker Stick) |
| 13 | losfahren, dann Show-Menü antippen | Eintrag ausgegraut **oder** Reject-Grund sichtbar |
| 14 | Show starten, **E-Stop**, dann **Recover** | Menü zeigt danach von selbst „Normalbetrieb" (`show_mode` wurde serverseitig zurückgesetzt) |
| 15 | Show starten, dann **Hinsetzen** | Reject mit Grund („nur aus STANDING") — erst Normalbetrieb, dann Hinsetzen |

> ⚠️ **Der eine noch offene Punkt — Stick-Vorzeichen prüfen (Schritt 6/8):** „Stick hoch" soll die
> **Kamera nach oben** schauen lassen, **R2** soll den Körper **heben**. Stimmt eine Richtung nicht,
> ist es ein Parameter — kein Code. Live korrigieren (▶ ROS, drittes Terminal):
> ```bash
> source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
> ros2 param set /joy_to_twist sign_body_pose_pitch 1.0     # pitch invertieren
> ros2 param set /joy_to_twist sign_body_pose_yaw -1.0      # yaw invertieren
> ros2 param set /joy_to_twist sign_body_pose_z -1.0        # Höhe invertieren
> ```
> Sag mir, welche Achsen invertiert werden mussten — ich ziehe die Defaults dauerhaft nach.

**Wenn Schritt 5 abgelehnt wird**, sagt der Grund, warum:
- `requires STATE_STANDING` → der Roboter steht nicht (liegt/läuft noch).
- `robot is frozen` → E-Stop aktiv, erst **Recover**.
- `has not stood up yet` → der Stack ist gerade erst hochgekommen (kein `/joint_states`).

---

## 4. HW-Test (T8.8, ▶ Pi) — am echten Roboter

> **Erst aufgebockt**, dann am Boden (CLAUDE.md §9). Die Show ist statisch stabil (alle 6 Füße
> tragen, CoG-Marge ≥ 166 mm), aber die Servos halten hier echtes Gewicht.
>
> **Erst nach grüner Sim-Abnahme (§3).**

### Schritt 1 — neuen Code auf den Pi bringen (▶ Pi)
```bash
ssh <pi>
cd ~/hexapod_ws
git pull
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select hexapod_gait hexapod_teleop hexapod_supervisor
source ~/hexapod_ws/install/setup.bash
```
> Ohne diesen Schritt kennt der Pi weder `show_mode` noch `/cmd_body_pose` — die App bekäme
> „unknown parameter".

### Schritt 2 — derselbe Ein-Befehl-Start wie in der README, nur `mode:=real` (▶ Pi)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py mode:=real
```
> Tipp: in `tmux` starten, damit es einen SSH-Abbruch überlebt. Die App verbindet dann auf die
> **Pi-IP** (Hotspot, Port 9090) — Ablauf **identisch zu §3**: Start → Aufstehen → Show-Menü.

### Schritt 3 — Show fahren
Alles wie in §3 (Tabelle Schritt 4–15), nur eben am echten Roboter. Alternativ ohne App per Hand:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 param set /gait_node show_mode look_around
```

**✅ Erwartung (T8.8):**
1. Die **Kamera schwenkt sichtbar** (im App-Video gut zu sehen), die Füße bleiben stehen.
2. Kein Servo-Zittern/Summen an den Grenzen, kein Freeze.
3. Loslassen → sauberer, ruhiger Rückweg.
4. `ros2 param set /gait_node show_mode none` → danach normal fahrbar.

**Falls es auf HW zäh/zittrig wirkt** (Servo-Last), Tempo herunternehmen — live:
```bash
ros2 param set /gait_node body_pose_rate_lin 0.05      # langsamer wandern (Default 0.08 m/s)
ros2 param set /gait_node body_pose_rate_ang_dps 20.0  # langsamer schauen (Default 30 °/s)
```
**Falls eine Achse zu weit geht** (mechanisch unruhig), Envelope live verkleinern:
```bash
ros2 param set /gait_node body_pose_pitch_max_deg 9.0
ros2 param set /gait_node body_pose_dx_max 0.035
```
> ⚠️ Werte **erhöhen** nur nach erneutem `look_around_envelope_check.py`-Lauf (GREEN + Exit 0).
