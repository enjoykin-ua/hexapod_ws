# Bein-Umbau — Test- & Cal-Anleitung (Live-Befehle)

> Plan: [`plan.md`](plan.md). **Interaktiv** — du führst aus dem Doc aus,
> knappe Status-Meldungen zurück ([[feedback_test_commands_in_doc_not_chat]]).
> **Maschine: Desktop-Hauptsystem** (nicht Pi) → serieller Port `/dev/ttyACM0`.
> Branch: `leg_changes`.

## ⚠️ Safety (CLAUDE.md §9)
- Beim Montieren/Kalibrieren **aufgebockt/aufgehängt** — Beine frei, kein Bodenkontakt.
- **PSU-Kill-Switch in der Hand.** Servo-Stall / Ruck / `OVERCURRENT` / `WATCHDOG` → sofort trennen.
- `real.launch.py` muss **durchlaufen**, solange du kalibrierst (das Plugin pollt
  im Loop = Watchdog-Heartbeat). Nicht zwischendrin beenden, sonst Relay-Drop.

---

# TEIL A — Montage + Servo-Cal (Schritt 1 + 2)

> Ziel: Beine bei `power_on_mid` (Servo-Mitte, 1500 µs) montieren, dann pro Servo
> `pulse_zero` (rad 0 = Bein gestreckt), `pulse_min`, `pulse_max` (mechanische
> Anschläge) live via `rqt_reconfigure` setzen. **Kein Aufstehen** — wir starten
> nur das Plugin, nicht `gait`.

## A.0 — Build + sourcen (Branch leg_changes)
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
git branch --show-current          # muss "leg_changes" zeigen
colcon build --symlink-install
source install/setup.bash
```

## A.1 — Plugin starten (Servos → Mitte, KEIN Standup)
```bash
# Terminal 1 (läuft durch!) — echter HW-Zugriff, initial_pose=power_on_mid (Default)
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```
- [ ] Alle 18 Servos gehen smooth auf `power_on_mid` (1500 µs), Relay an, kein Trip.
- [ ] **Kein** Aufstehen (gait wird NICHT gestartet) — Servos bleiben auf Mitte.

> Das ist die Montage-Ausgangslage: bei gehaltener Servo-Mitte montierst du die
> Beine, danach kalibrierst du. Default `serial_port:=/dev/ttyACM0`, `initial_pose:=power_on_mid`.

## A.2 — rqt_reconfigure starten (Live-Cal-GUI)
```bash
# Terminal 2
cd ~/hexapod_ws && source install/setup.bash
ros2 run rqt_reconfigure rqt_reconfigure
```
- [ ] GUI offen, Node **`/hexapodsystem`** auswählen → Pin-Cal-Parameter
      (`pulse_min` / `pulse_zero` / `pulse_max` pro Pin) als Slider/Felder sichtbar.

> Optional — Live-PWM mitlesen (zweites Terminal/Plot):
> ```bash
> ros2 param set /hexapodsystem publish_servo_pulses true
> ros2 run rqt_plot rqt_plot /hexapodsystem/servo_pulses/data
> ```

## A.3 — Cal-Methodik (wichtig: pulse-Werte sind keine Grenzen!)

Die drei Werte `pulse_min/zero/max` sind **keine PWM-Grenzen (Clamps)**, sondern
die **Stützpunkte der rad→PWM-Kurve** (`PWM = pulse_zero + direction·rad·slope`):
- `pulse_zero` = PWM bei **rad 0** (Offset → verschiebt die *ganze* Kurve)
- `pulse_max`  = PWM beim **oberen** rad-Limit (Steigung obere Hälfte, rad ≥ 0)
- `pulse_min`  = PWM beim **unteren** rad-Limit (Steigung untere Hälfte, rad < 0)

Verstellst du einen Stützpunkt, **fährt der Servo** — weil sich die Abbildung
ändert, nicht weil es eine Grenze ist.

**Mess-Trick:** Bei **rad-Command = 0** wird `PWM = pulse_zero` (rad·slope = 0).
Dann ist `pulse_zero` ein **direkter PWM-Regler** (Servo folgt 1:1) und
`pulse_min/max` bewegen nichts mehr. So liest du die Werte sauber ab.

## A.3b — rad-Command auf 0 setzen

**Alle 6 Beine auf einmal:**
```bash
for n in 1 2 3 4 5 6; do
  ros2 topic pub --once /leg_${n}_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
  "{joint_names: [leg_${n}_coxa_joint, leg_${n}_femur_joint, leg_${n}_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 1}}]}"
done
```

**Einzelnes Bein** (die `1` durch 1..6 ersetzen):
```bash
ros2 topic pub --once /leg_1_controller/joint_trajectory trajectory_msgs/msg/JointTrajectory \
'{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 1}}]}'
```
- [ ] Nach dem Command bewegen `pulse_min`/`pulse_max` den Servo **nicht** mehr,
      nur `pulse_zero` (= Beweis, dass rad-Command 0 ist).

> ⚠️ Der Command **bewegt** die Servos (auf ihren aktuellen `pulse_zero`).
> Aufgebockt, Kill-Switch bereit.

## A.3c — Mess-Prozedur pro Servo (Femur + Tibia; Coxa NICHT)

Während `real.launch.py` + `rqt_reconfigure` laufen und rad-Command = 0:
1. Segment bei der Servo-Mitte **montieren**.
2. `pulse_min`/`pulse_max` **weit aufmachen** (z. B. 500 / 2500), damit das
   Plugin nicht wegen „PWM außerhalb [min,max]" einfriert.
3. `pulse_zero` als **Fahrregler** nutzen, zu den Lagen fahren, Wert ablesen
   (siehe A.3d).

> - **Femur:** die **±90° sind die Anschläge** → `B↑`/`B↓` *sind* `pulse_max`/`pulse_min`
>   (rad-Limit = ±π/2). Kein extra C/D.
> - **Tibia:** B bei 90° messen; **falls der Anschlag weiter als 90° geht**, zusätzlich
>   C/D (die echten Anschläge) — sonst C/D leer lassen, dann gilt 90° = Anschlag.
> - **Coxa: NICHT neu kalibrieren** (unverändert). **directions bleiben wie alt.**
> - `A → pulse_zero`. Falls 90° (B) nicht erreichbar → B leer, ich rechne aus der Gegenseite.

- [ ] Femur aller 6 Beine: A/B↑/B↓ gemessen + in A.3d eingetragen
- [ ] Tibia aller 6 Beine: A/B↑/B↓ (+ C/D falls nötig) gemessen + eingetragen

## A.3d — Kalibrations-Notizen (Werte hier eintragen)

```
=== GEOMETRIE ===
Femur-Länge (m): ______      Femur-Masse (kg): ______
Tibia-Länge (m): ______      Tibia-Masse (kg): ______


######## LEG 1 — rechts vorne ########

Femur (Pin 1)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (senkrecht nach OBEN = Anschlag):______
  B↓  90°    (senkrecht nach UNTEN = Anschlag):______

Tibia (Pin 2)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (geknickt Richtung 1):           ______
  B↓  90°    (geknickt Richtung 2):           ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______


######## LEG 2 — rechts mitte ########

Femur (Pin 4)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (oben = Anschlag):               ______
  B↓  90°    (unten = Anschlag):              ______

Tibia (Pin 5)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (Richtung 1):                    ______
  B↓  90°    (Richtung 2):                    ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______


######## LEG 3 — rechts hinten ########

Femur (Pin 7)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (oben = Anschlag):               ______
  B↓  90°    (unten = Anschlag):              ______

Tibia (Pin 8)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (Richtung 1):                    ______
  B↓  90°    (Richtung 2):                    ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______


######## LEG 4 — links hinten ########

Femur (Pin 10)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (oben = Anschlag):               ______
  B↓  90°    (unten = Anschlag):              ______

Tibia (Pin 11)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (Richtung 1):                    ______
  B↓  90°    (Richtung 2):                    ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______


######## LEG 5 — links mitte ########

Femur (Pin 13)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (oben = Anschlag):               ______
  B↓  90°    (unten = Anschlag):              ______

Tibia (Pin 14)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (Richtung 1):                    ______
  B↓  90°    (Richtung 2):                    ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______


######## LEG 6 — links vorne ########

Femur (Pin 16)
  A   rad 0  (Femur waagerecht):              ______
  B↑  90°    (oben = Anschlag):               ______
  B↓  90°    (unten = Anschlag):              ______

Tibia (Pin 17)
  A   rad 0  (Tibia gerade):                  ______
  B↑  90°    (Richtung 1):                    ______
  B↓  90°    (Richtung 2):                    ______
  C   Anschlag R1 (nur falls > 90°):          ______
  D   Anschlag R2 (nur falls > 90°):          ______
```

> Mapping: `A → pulse_zero`. Femur: `B↑/B↓ → pulse_max/pulse_min` (rad-Limit ±π/2).
> Tibia: aus `A` + `B↑/B↓` (+ ggf. `C/D`) rechne ich slope + rad-Limits aus.

## A.4 — rad-0-Sichtprüfung + Sweep
- [ ] Jedes Bein bei rad 0 **gestreckt** (HW == RViz), kein schiefes Segment (Montage ok).
- [ ] Vorsichtiger Sweep über den Bereich: **kein** `SAFETY FREEZE` / Stall / unerwartetes Springen.

## A.5 — Kalibrierung speichern
```bash
# Terminal 3 — schreibt servo_mapping.yaml + .bak-<timestamp>
ros2 service call /save_calibration std_srvs/srv/Trigger
```
(oder Komfort-Alias `hexapod-save-cal`, falls
[`tools/hexapod-shell-aliases.sh`](../../tools/hexapod-shell-aliases.sh) gesourct.)
- [ ] `servo_mapping.yaml` aktualisiert; Backup `servo_mapping.yaml.bak-…` angelegt.

## A.6 — Sauberes Beenden
```bash
# Terminal 1: Strg+C (Rail stromlos → Servos limp)
```
→ danach im Plan **Schritt 3** (Geometrie/Längen in xacro + config.py).

---

# TEIL B — Sim/Gazebo (S5) → eigene Datei

> Die S5-Sim-Tests (Modell-Visual-Check, Reachability-Viz, Aufstehen, Tripod-Lauf,
> Live-Tuning) stehen in [`stage_5_sim_test_commands.md`](stage_5_sim_test_commands.md).
> Plan dazu: [`stage_5_sim_plan.md`](stage_5_sim_plan.md).

# TEIL C — HW-Validierung Desktop (Schritt 7) — _Gerüst_

- aufgehängt: Init + Aufstehen + Laufen + Gangarten + Teleop
- Boden: Aufstehen schürffrei + Strom + Laufen

# TEIL D — Pi-Kurztest (Schritt 8) — _Gerüst_

- Branch am Pi ziehen + bauen, Init + Aufstehen + kurz fahren

---

## Schnell-Diagnose

| Symptom | wahrscheinlich | Sofort |
|---|---|---|
| Servo zuckt hart / Trip beim Enable | Power-On / Anschlag / Montage schief | Kill-Switch; pulse_zero/Montage prüfen |
| `/hexapodsystem` fehlt in rqt | real.launch nicht aktiv / nicht gesourct | Terminal 1 läuft? `source install/setup.bash` |
| `SAFETY FREEZE` beim Sweep | PWM am Cal-Limit / pulse_min/max zu eng | Limits in rqt weiten, vorsichtig |
| Cal nicht gespeichert | Service-Name / Plugin-Node | `ros2 service list \| grep calibration` |
