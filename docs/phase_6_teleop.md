# Phase 6 — Teleop (Tastatur, PS-Controller)

**Dauer-Schätzung:** 1–2 Tage (Tastatur), +1–2 Tage (PS-Controller)
**Maschine:** nur Desktop
**Vorbedingung:** Phase 5 abgeschlossen, Roboter läuft auf `/cmd_vel`

---

## Ziel

Steuerung des Hexapods per Tastatur und (optional) PS4/PS5-Controller.
Beide Eingabegeräte erzeugen `/cmd_vel`-Nachrichten, die der Gait-Knoten
aus Phase 5 verarbeitet.

---

## Done-Kriterien

1. Tastatur-Teleop läuft mit fertigem `teleop_twist_keyboard`-Paket,
   Roboter fährt vor/zurück/seitwärts/dreht in Gazebo.
2. Eigenes Paket `hexapod_teleop` mit PS-Controller-Support gebaut.
3. PS4 oder PS5 Controller über USB ODER Bluetooth verbunden,
   `joy_node` zeigt Achsen/Buttons.
4. Mapping-Knoten erzeugt aus `/joy` korrekte `/cmd_vel`-Werte.
5. Definierter „Dead-Man-Switch": Bewegung nur, wenn ein Trigger gedrückt
   ist. Loslassen = sofortiger Stopp.

---

## Schritt 1: Tastatur (10 Minuten)

Fertiges Paket nutzen, nichts selber schreiben:

```bash
sudo apt install ros-jazzy-teleop-twist-keyboard
```

In Terminal A:

```bash
ros2 launch hexapod_bringup sim.launch.py
```

In Terminal B:

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Tasten i/k/j/l usw. erzeugen `/cmd_vel`. Roboter sollte laufen.

> **Wenn nichts passiert:** Topic-Name prüfen. `teleop_twist_keyboard`
> publisht standardmäßig auf `/cmd_vel` — passt nur, wenn dein Gait-Knoten
> dort lauscht. Sonst:
> `ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args
>   --remap cmd_vel:=/hexapod/cmd_vel`

Damit ist Done-Kriterium 1 erfüllt.

---

## Schritt 2: PS-Controller — Hardware-Vorbereitung

### USB-Verbindung (einfachster Weg)

Controller per USB-Kabel anschließen. Linux erkennt PS4/PS5 als Gamepad
out-of-the-box.

Test:

```bash
ls /dev/input/js*
# oder
ls /dev/input/by-id/ | grep -i play
```

Erwartung: `/dev/input/js0` o. ä. existiert.

```bash
sudo apt install joystick
jstest /dev/input/js0
```

Bewegung der Sticks zeigt sich live.

### Bluetooth (optional, für kabellos)

PS4 (DualShock 4): Share + PS-Button gleichzeitig drücken bis LED blinkt.
PS5 (DualSense): PS + Create gleichzeitig drücken.

```bash
bluetoothctl
> scan on
> pair <MAC>
> trust <MAC>
> connect <MAC>
> exit
```

> **Hinweis:** PS5-DualSense funktioniert mit aktuellem Linux-Kernel
> nativ, aber nicht alle Features (Touchpad, adaptive Trigger,
> Lichtleiste) sind über `joy_node` zugänglich. Für Steuerung reicht's.

---

## Schritt 3: ROS2-Joy-Knoten

```bash
sudo apt install ros-jazzy-joy
ros2 run joy joy_node
```

In zweitem Terminal:

```bash
ros2 topic echo /joy
```

Sticks bewegen → Werte ändern sich. Buttons drücken → entsprechender
Index in `buttons[]` wird 1.

> **Achsen- und Button-Mapping notieren!** Das unterscheidet sich
> zwischen PS4 und PS5 und auch zwischen USB und Bluetooth.
> Schreib's ins README von `hexapod_teleop`.

Typisches Mapping (PS4 USB, kann abweichen):

| Index | Achse |
|---|---|
| 0 | Linker Stick X (links/rechts) |
| 1 | Linker Stick Y (vor/zurück) |
| 3 | Rechter Stick X (drehen) |
| 4 | Rechter Stick Y |
| 2 | L2 (analog) |
| 5 | R2 (analog) |

| Index | Button |
|---|---|
| 0 | Cross |
| 1 | Circle |
| 4 | L1 |
| 5 | R1 |

---

## Schritt 4: Eigenes Paket `hexapod_teleop`

```bash
cd ~/hexapod_ws/src
ros2 pkg create --build-type ament_python --license Apache-2.0 \
  --dependencies rclpy sensor_msgs geometry_msgs hexapod_teleop
```

Inhalt:

```
hexapod_teleop/
├── package.xml
├── setup.py
├── hexapod_teleop/
│   ├── __init__.py
│   └── joy_to_twist.py
├── config/
│   ├── ps4_usb.yaml
│   ├── ps4_bt.yaml
│   └── ps5.yaml
└── launch/
    └── joy_teleop.launch.py
```

`joy_to_twist.py` (Knoten):

- Subscribe: `/joy`
- Publish: `/cmd_vel`
- Parameter:
  - `axis_linear_x`, `axis_linear_y`, `axis_angular_z` (Achsen-Indizes)
  - `scale_linear_x`, `scale_linear_y`, `scale_angular_z` (max. Geschw.)
  - `deadman_button` (Index, z. B. R1)
  - `deadzone` (z. B. 0.1)

Logik:

```python
def joy_callback(msg):
    if msg.buttons[deadman_button] != 1:
        publish_zero_twist()       # Dead-Man losgelassen → Stopp
        return
    twist = Twist()
    twist.linear.x = apply_deadzone(msg.axes[axis_linear_x]) * scale_lin_x
    twist.linear.y = apply_deadzone(msg.axes[axis_linear_y]) * scale_lin_y
    twist.angular.z = apply_deadzone(msg.axes[axis_angular_z]) * scale_ang_z
    publish(twist)
```

> **Dead-Man-Switch ist nicht optional.** Auch in der Sim. Gewohnheit
> für Phase 7, wenn echte Servos angeschlossen sind. Loslassen = Stopp.

### Config-YAMLs

```yaml
# ps4_usb.yaml
joy_to_twist:
  ros__parameters:
    axis_linear_x:  1
    axis_linear_y:  0
    axis_angular_z: 3
    scale_linear_x:  0.05    # m/s
    scale_linear_y:  0.03
    scale_angular_z: 0.5     # rad/s
    deadman_button:  5       # R1
    deadzone:        0.1
```

### Launch-File

`launch/joy_teleop.launch.py`:

1. `joy_node` mit Parameter `deadzone: 0.05` und `autorepeat_rate: 20.0`
2. `joy_to_twist` mit der gewünschten Config-YAML
3. Argument `controller` (default `ps4_usb`) wählt YAML

---

## Schritt 5: Integration und Test

```bash
colcon build --packages-select hexapod_teleop
source install/setup.bash

# Terminal A:
ros2 launch hexapod_bringup sim.launch.py

# Terminal B:
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```

Mit gehaltenem R1 + linkem Stick: Hexapod fährt in Gazebo.
R1 loslassen: Stopp.

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| `/joy` zeigt nichts | Berechtigungen `/dev/input/js0` | User in Gruppe `input` aufnehmen, neu einloggen |
| BT-Controller verbindet, aber `/dev/input/js*` nicht da | Kernel-Modul / hidraw-Konflikt | trennen, neu pairen, evtl. ohne `bluez-input-driver` |
| Achsen falsch belegt | Mapping zwischen USB/BT/PS4/PS5 unterschiedlich | `ros2 topic echo /joy`, YAML anpassen |
| Roboter fährt rückwärts statt vor | Achsen-Vorzeichen | `scale_*` mit −1 multiplizieren |
| Roboter fährt mit Vollgas trotz minimal Stick | Deadzone fehlt oder Skalierung falsch | Deadzone aktivieren, Skalierung prüfen |
| Latenz spürbar | `joy_node` Default-Rate niedrig | `autorepeat_rate: 50.0` |

---

## Was in dieser Phase **NICHT** gemacht wird

- Keine Erweiterung der Gait-Engine
- Keine Sensor-Integration
- Kein Custom-Mapping über das Touchpad oder Lichtleiste
- Keine Pi-Portierung

---

## Phasenabschluss

- [ ] Alle 5 Done-Kriterien erfüllt
- [ ] Mapping pro genutztem Controller in README dokumentiert
- [ ] Dead-Man-Switch funktioniert nachweislich
- [ ] Timeshift-Snapshot `phase_6_done`
- [ ] Git-Commit + Tag `phase-6-done`
- [ ] `PHASE.md` auf Phase 7 aktualisiert
