# Phase 6 Stufe A — Test-Befehle (PS4-Controller via USB)

Live-Verifikation des `hexapod_teleop`-Pakets mit PS4-Controller per
USB. **Vier Terminals** (T1-T4), jeweils klar gekennzeichnet was wo
läuft.

> **Wichtig zur Befehls-Notation:**
> Jeder Befehlsblock ist mit **`# T1`**, **`# T2`**, **`# T3`** oder
> **`# T4`** im Kommentar markiert — **das Terminal in dem du den
> Befehl ausführen sollst**.

> **Voraussetzungen:**
> - Phase 5 abgeschlossen (Sim + Stand + Gait laufen via cmd_vel)
> - PS4-Controller per USB-Kabel angeschlossen
> - `ros2 topic echo /joy` zeigt Werte (User hat das vorab bestätigt)
> - `colcon build --packages-select hexapod_gait hexapod_teleop` grün

---

## Vorbereitung (alle Terminals)

In **jedem Terminal**, das du öffnest:

```bash
# T1 / T2 / T3 / T4: in jedem!
cd ~/hexapod_ws
source install/setup.bash
```

Falls Pakete neu gebaut werden müssen:

```bash
# T1 (oder beliebiges)
colcon build --packages-select hexapod_kinematics hexapod_sensors hexapod_gait hexapod_teleop hexapod_description hexapod_bringup
source install/setup.bash
```

### Cleanup-Snippet vor Test

```bash
# T1
pkill -9 -f "joy_to_twist" 2>/dev/null
pkill -9 -f "joy_node" 2>/dev/null
pkill -9 -f "ros2 topic pub" 2>/dev/null
pkill -9 -f "ros2" 2>/dev/null
pkill -9 -f "gz" 2>/dev/null
pkill -9 -f "ruby" 2>/dev/null
pkill -9 -f "parameter_bridge" 2>/dev/null
pkill -9 -f "robot_state_publisher" 2>/dev/null
pkill -9 -f "controller_manager" 2>/dev/null
pkill -9 -f "foot_contact_publisher" 2>/dev/null
pkill -9 -f "stand_node" 2>/dev/null
pkill -9 -f "gait_node" 2>/dev/null
sleep 4

# Verify nichts mehr läuft:
ps aux | grep -E "(joy_node|joy_to_twist|gait_node|ros2|gz|hexapod)" | grep -v grep
```

---

## Schritt 1 — Sim mit Foot-Contact starten

```bash
# T1
ros2 launch hexapod_bringup sim.launch.py enable_foot_contact:=true > /tmp/sim.log 2>&1 &
sleep 12
```

Warten bis Gazebo-Fenster offen ist und Roboter auf dem Bauch liegt.

**Verify:**

```bash
# T1 (im selben Terminal nach &)
ros2 control list_controllers
```

**Erwartet:** `joint_state_broadcaster` + 6× `leg_<n>_controller`
alle `active`.

---

## Schritt 2 — Stand-Pose anfahren

```bash
# T2
ros2 launch hexapod_gait stand.launch.py
sleep 6
```

**Erwartet:** `stand_node` läuft ~5 s und beendet sich sauber.
Roboter steht auf 6 Beinen mit `body_height = -0.052 m`.

---

## Schritt 3 — gait_node starten

```bash
# T2 (selbes Terminal nach stand_node)
ros2 launch hexapod_gait gait.launch.py
```

**Erwartet — Init-Log:**

```
gait_node init: pattern=tripod, step_height=0.030 m, cycle_time=2.00 s,
                body_height=-0.052 m (range [-0.080, -0.030]),
                step_length_max=0.050 m (linear_max=0.050 m/s),
                ...
```

`gait_node` läuft kontinuierlich. **T2 NICHT schließen** — `gait_node`
muss laufen während du in T3-T4 testest. Beenden später mit `Ctrl+C`.

---

## Schritt 4 — `joy_node` + `joy_to_twist` starten

```bash
# T3
ros2 launch hexapod_teleop joy_teleop.launch.py
```

**Erwartet — Init-Logs:**

```
[joy_node]: Opened joystick: /dev/input/js0.
[joy_to_twist]: joy_to_twist init:
   D-Pad axes (x=6, y=7, signs (+1, +1)),
   L2 axis=2, R2 axis=5, threshold=0.5,
   deadman button=5,
   scales (linear=0.050, angular=0.460),
   body_step=0.0050 m
```

Falls `joy_node` keinen Joystick findet:

```bash
# T4 (parallel zum laufenden joy_node)
ls /dev/input/js* 2>/dev/null || echo "kein Joystick gefunden!"
groups | grep input || echo "WARN: User nicht in Gruppe 'input'"
```

- Falls Joystick auf einem anderen Index als 0 ist (mehrere Controller
  angeschlossen): `joy_device_id:=1` oder `2`. Der Parameter ist ein
  **SDL-Joystick-Index**, NICHT ein `/dev/input/jsX`-Pfad.
- Falls Permission-Fehler: User in Gruppe `input` aufnehmen
  (`sudo usermod -a -G input $USER` + neu einloggen).

**T3 läuft die ganze Zeit** während du den Controller bedienst.

---

## Schritt 5 — DK 4: D-Pad ↑/↓ → Vor/Zurück

In T4 öffnest du parallel `gz model -p` Snapshots vor und nach dem Walk.

```bash
# T4
echo "=== Body-Pose VOR Walk ==="
gz model -m hexapod -p
```

Notiere x-Wert.

**Jetzt am Controller:**
1. **R1 halten** (Dead-Man)
2. **D-Pad ↑ ca. 5 Sekunden gedrückt halten**
3. R1 + D-Pad ↑ loslassen

**Erwartet visuell:** Roboter läuft sichtbar vorwärts. Im T2-Terminal
siehst du die `cmd_vel`-Pubs ankommen (Engine-State wechselt zu
WALKING).

```bash
# T4
echo "=== Body-Pose NACH 5s Vorwärts ==="
gz model -m hexapod -p
```

**Akzeptanz:** x-Drift ≥ 0.10 m (theoretisch 0.05 m/s · 5 s = 0.25 m,
JTC-Lag reduziert auf real ~50%).

**Rückwärts-Test analog:**
1. R1 halten
2. **D-Pad ↓ 3 Sekunden**
3. Loslassen

**Erwartet:** x-Position nimmt ab (geht zurück Richtung Start).

---

## Schritt 6 — DK 4: D-Pad ←/→ → Drehen am Stand

```bash
# T4
echo "=== Body-Pose VOR Drehen links ==="
gz model -m hexapod -p
```

Notiere Yaw-Wert (RPY 3. Wert).

**Am Controller:**
1. **R1 halten**
2. **D-Pad ← ca. 4 Sekunden**
3. Loslassen

**Erwartet visuell:** Roboter dreht sich gegen Uhrzeigersinn. Body-x/y
bleibt etwa konstant.

```bash
# T4
echo "=== Body-Pose NACH Drehen ==="
gz model -m hexapod -p
```

**Akzeptanz:** Yaw-Differenz ca. +0.46 rad/s · 4 s = +1.84 rad
(≈ 105°). Tolerance ±50%, also [+0.9, +2.7] rad. Body x/y-Drift
< 0.10 m.

**D-Pad → analog:** Yaw nimmt ab (negativ).

---

## Schritt 7 — DK 4: Multi-Direction → Bogen

```bash
# T4
echo "=== Body-Pose VOR Bogen ==="
gz model -m hexapod -p
```

**Am Controller:**
1. **R1 halten**
2. **D-Pad ↑ UND D-Pad ← gleichzeitig** für 5 Sekunden

> Auf PS4-D-Pad ist das schwierig — die 4 Tasten sind oft so geformt
> dass nur eine zur Zeit feuert. Wenn ↑+← nicht gleichzeitig
> funktionieren, ist das eine **Hardware-Limitation des D-Pads**, kein
> Software-Bug.
>
> **Falls Multi-Direction am D-Pad nicht geht:** in
> `ros2 topic echo /joy` während Test schauen — sehen beide
> axes[6] und axes[7] gleichzeitig non-zero? Wenn ja: Software OK.
> Wenn nicht: D-Pad-Hardware fired nur eine Achse zur Zeit, dann ist
> Bogen-Walk nur mit Sticks (Stufe-B-Mapping) möglich.

**Erwartet visuell** (wenn Hardware Multi-Direction kann): Roboter
läuft auf einem Bogen (vorwärts + dreht links).

```bash
# T4
gz model -m hexapod -p
```

Sowohl x als auch yaw haben sich verändert.

---

## Schritt 8 — DK 5: Dead-Man-Switch

```bash
# T4
echo "=== Test Dead-Man ==="
```

**Am Controller:**
1. **R1 halten** + **D-Pad ↑** (Roboter läuft)
2. Mitten im Walk: **R1 loslassen** (D-Pad weiter halten)

**Erwartet visuell:** Roboter stoppt sofort (innerhalb der DK-3-
Stopp-Latenz von max 1.3 s). Auch wenn D-Pad weiter gedrückt ist!

**Kritisches Akzeptanz-Kriterium DK 5:** Loslassen von R1 bedeutet
Stopp. Wenn das nicht funktioniert — Bug, vor Phase 7 fixen!

---

## Schritt 9 — Body-Lift mit R2 (anheben)

> **Wichtig:** Body-Lift funktioniert **nur wenn Roboter steht** —
> Engine ist im STANDING-State. Während WALKING wird L2/R2 ignoriert
> mit Warning-Log.

```bash
# T4
echo "=== Body-Pose VOR R2-Press ==="
gz model -m hexapod -p
```

Notiere z-Wert (3. XYZ-Wert in Meter).

**Am Controller** (R1 NICHT halten — Roboter muss stehen):
1. **R2 1× drücken** (volldurchgedrückt, dann loslassen)
2. Im **T2-Terminal** sollte stehen:
   ```
   [gait_node]: body_height -> -0.0470 m
   ```
3. Im **T3-Terminal** sollte stehen:
   ```
   [joy_to_twist]: body_height target -> -0.0470 m (raise)
   ```
4. Visuell: Roboter wird ca. 5 mm höher (sichtbar).

```bash
# T4
sleep 1
echo "=== Body-Pose NACH 1× R2 ==="
gz model -m hexapod -p
```

**Akzeptanz:** z-Wert ist um ca. 5 mm gestiegen.

**Wiederhole:** R2 noch 2× drücken. Body sollte 15 mm höher als
ursprünglich sein.

---

## Schritt 10 — Body-Lift mit L2 (absenken)

```bash
# T4
echo "=== Body-Pose VOR L2-Press ==="
gz model -m hexapod -p
```

**Am Controller:**
1. **L2 5× drücken** (5 mm * 5 = 25 mm absenken)

**Erwartet:** Body geht zurück nach unten. Bei 5× L2-Press von
z.B. -0.037 sollte target nun -0.062 sein.

```bash
# T4
sleep 1
echo "=== Body-Pose NACH 5× L2 ==="
gz model -m hexapod -p
```

**Akzeptanz:** z-Wert ist ca. 25 mm niedriger als vor den 5 Presses.

---

## Schritt 11 — Body-Lift während WALKING wird ignoriert

> **Sicherheits-Constraint-Test:** L2/R2 darf den Body nicht ändern
> während Roboter läuft.

**Am Controller:**
1. **R1 + D-Pad ↑** halten (Walking starten)
2. Während Walking: **R2 1× drücken**
3. Im **T2-Terminal** sollte folgende Warning erscheinen:
   ```
   [gait_node]: cmd_body_height ignored: state=WALKING, must be STANDING.
   ```
4. **R1 loslassen** (Stopp)
5. Im **T2-Terminal**: `cmd_body_height ignored`-Warnings hören auf
   (nach STOPPING-State-Transition).

**Erwartet:** Warning ist da, Body-Pose hat sich **nicht** geändert.

---

## Schritt 12 — Body-Height-Limits (Clamping)

**Am Controller:**
1. R1 NICHT halten (STANDING)
2. **R2 sehr oft drücken** (z.B. 20× in Folge)
3. Im **T2-Terminal** sollte irgendwann stehen:
   ```
   [gait_node]: cmd_body_height clamped: -0.022 -> -0.030 (range [-0.080, -0.030])
   ```

**Erwartet:** Engine clampt auf `body_height_max = -0.030 m`.
Roboter steigt nicht weiter, Warnings im Log.

Analog für L2: nach genug Drücken kommt Clamp auf `body_height_min
= -0.080 m`.

---

## Schritt 13 — Aufräumen

```bash
# T3 (joy_to_twist + joy_node)
# Strg+C
```

```bash
# T2 (gait_node)
# Strg+C
```

```bash
# T1 (sim)
kill %1
# oder Cleanup-Snippet von oben
```

---

## Optionale Variationen

### Achsen-Vorzeichen schnell-Diagnose

Falls D-Pad ↑ den Roboter rückwärts laufen lässt (Vorzeichen-Bug):

```bash
# T3: Strg+C, dann
ros2 launch hexapod_teleop joy_teleop.launch.py
```

Editiere [config/ps4_usb.yaml](../src/hexapod_teleop/config/ps4_usb.yaml)
und ändere `sign_dpad_y: -1.0`. Build + relaunch:

```bash
# T1
colcon build --packages-select hexapod_teleop
source install/setup.bash
# T3
ros2 launch hexapod_teleop joy_teleop.launch.py
```

### Joy-Topic während Test live mitlesen

```bash
# T4 (parallel zum Test)
ros2 topic echo /joy --once
# nochmal & nochmal um sehen wie sich axes/buttons ändern
```

### `cmd_vel`-Echo während Test

```bash
# T4
ros2 topic echo /cmd_vel
```

Sollte Twist-Werte ausgeben sobald R1 + D-Pad gedrückt.

---

## Stolperfallen

(Aus Phase 5 + Phase 6 destilliert.)

1. **`/dev/input/js0` existiert nicht** → Controller nicht erkannt.
   Anderen USB-Port probieren, oder `ls /dev/input/by-id/`.
2. **Permissions auf `/dev/input/js0`** → User in Gruppe `input`
   aufnehmen, neu einloggen.
3. **`joy_node`-Permission-Error** → siehe oben.
4. **Roboter läuft Vollgas trotz minimal D-Pad** → D-Pad ist digital,
   das ist normal. PS-Sticks (analog) wären für Modulation, in
   Stufe A nicht gemappt.
5. **L2/R2 reagiert auch wenn Walk** → Constraint-Bug. Engine-State
   prüfen mit `ros2 param get /gait_node ...` (geht nicht direkt).
   Stattdessen `/gait_node`-Init-Log prüfen für Body-Height-Range.
6. **Multi-Direction D-Pad ↑+← geht nicht** → wahrscheinlich
   Hardware-Limitation des D-Pads (PS4-DualShock teils-mechanisch
   exklusiv). `ros2 topic echo /joy` zeigt im Test ob beide axes
   simultan getriggert werden. Workaround: in Stufe B mit Sticks.
7. **Stale Prozesse zwischen Tests** → Cleanup-Snippet jedes Mal
   komplett laufen lassen.
8. **`autorepeat_rate` zu niedrig** → Latenz spürbar (Stick muss
   bewegt werden für neuen `/joy`-Pub). Default 20 Hz reicht für
   D-Pad/Trigger. Bei Sticks evtl. höher.
