# Phase 13 — Erster echter HW-Start am Pi (Test-Anleitung)

> Plan: [`phase_13_pi_hw_bringup_plan.md`](phase_13_pi_hw_bringup_plan.md).
> **Interaktiv** — alle Befehle laufen **am Pi** (`ssh hexapod-pi` oder
> Pi-Bildschirm). User führt aus dem Doc aus, knappe Status-Meldungen zurück.
> Launches am besten in **tmux** (`Strg+b` = Prefix, loslassen, dann `"`/`%`;
> DE-Tastatur: `"`=Shift+2) oder am Pi-Bildschirm.

## ⚠️ Safety (CLAUDE.md §9) — vor JEDER Stufe
- **Stages B–E aufgebockt** (Beine in der Luft). Erst Stage F am Boden.
- **PSU-Kill-Switch in der Hand.** Stall / Ruck / `OVERCURRENT` / `WATCHDOG` /
  `SAFETY FREEZE` → **sofort Strom trennen**.
- Sauberes Beenden: Launches `Strg+C` (Rail stromlos → Servos limp), dann PSU aus.

---

## 0. In jedem Terminal: sourcen + URDF-Pfad

```bash
cd ~/hexapod_ws
source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
echo "$HEX_URDF"
```

---

# STAGE A — Vorbereitung & Safety

## A-T1 — `/dev/servo2040` prüfen (Servo2040 am Pi angesteckt)
```bash
ls -l /dev/servo2040          # muss auf ../../ttyACMx zeigen
```
- [ ] Symlink vorhanden und zeigt auf einen ttyACM.

## A-T2 — Workspace aktuell bauen
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```
- [ ] Build grün.

## A-T3 — FW-Strom-Limit
- [ ] FW-Limit = **10 A total** (FW-seitig, `cfg::TOTAL_CURRENT_MAX_MA`).
      PSU steht auf **8,4 V / max 10 A**. ⚠️ PSU-Max = FW-Trip → **Kill-Switch
      ist die primäre Sicherung** (PSU kann bei Stall einbrechen, bevor FW trippt).

## A-T4 — Safety-Aufbau
- [ ] Roboter **aufgebockt** (Beine frei in der Luft).
- [ ] PSU mit **Stromanzeige** sichtbar, **Kill-Switch** in der Hand.

---

# STAGE B — Init aufgebockt (erster echter HW-Zugriff am Pi!)

> Das ist der kritische Erstkontakt: das Plugin öffnet `/dev/servo2040` und
> rampt die 18 Servos smooth auf die Mitte. **Hand am Kill-Switch.**

```bash
# Terminal 1 (läuft weiter!)
ros2 launch hexapod_bringup real.launch.py \
    loopback_mode:=false \
    serial_port:=/dev/servo2040 \
    initial_pose:=power_on_mid
```
- [ ] B.1 Alle 6 Beine kommen **smooth** in power_on_mid hoch, Relay klickt an,
      **kein** Trip / `WATCHDOG` / `SAFETY FREEZE` / Voltage-Drop.

```bash
# Terminal 2
cd ~/hexapod_ws && source install/setup.bash
ros2 control list_controllers
```
- [ ] B.2 1× `joint_state_broadcaster` + 6× `leg_N_controller` alle **active**.

> Wenn hier etwas zuckt/trippt → **sofort Kill-Switch**, melden, nicht weiter.

---

# STAGE C — Kartesisches Aufstehen aufgebockt

```bash
# Terminal 2 (Terminal 1 = real.launch läuft weiter)
cd ~/hexapod_ws && source install/setup.bash
HEX_URDF="$(ros2 pkg prefix --share hexapod_description)/urdf/hexapod.urdf.xacro"
ros2 launch hexapod_gait gait.launch.py \
    use_sim_time:=false \
    robot_description_file:="$HEX_URDF"
```
**Erwartung (~8 s, aufgebockt):**
- [ ] C.1 Log `Cartesian-Standup gestartet …`; Phase 1: Beine strecken nach
      außen-unten (Knie wirkt gestreckt — normal); Phase 2: Beine beugen in
      Stand-Konfiguration. **Kein** Stall / `IKError` / `SAFETY FREEZE` /
      `OVERCURRENT`.
- [ ] C.2 Endpose ruhig, kein Zittern.
```bash
# Terminal 3 (optional): plausible Endpose?
ros2 topic echo /joint_states --once
# erwartet je Bein ~ coxa 0 / femur -0.240 / tibia +0.758
```

---

# STAGE D — Teleop USB aufgebockt

> PS4-Controller **per USB** an den Pi. Roboter weiter aufgebockt — Beine
> bewegen sich auf Stick-Eingabe **in der Luft**.

```bash
ls /dev/input/js*            # js0 sollte existieren (USB-Controller)
```
- [ ] D.1a `/dev/input/js0` vorhanden.

```bash
# Terminal 4
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_usb
```
```bash
# Terminal 5 (optional): kommt /joy an?
ros2 topic echo /joy         # Sticks/Buttons bewegen → Werte ändern sich?
```
- [ ] D.1b `/joy` ändert sich bei Eingabe.
- [ ] D.2 **R1 gehalten** + linker Stick → Beine bewegen sich in der Luft;
      **ohne R1** → Neutral (Dead-Man greift). Langsam tasten, Kill-Switch bereit.

---

# STAGE E — Teleop Bluetooth aufgebockt

> DS4 zuerst per `bluetoothctl` am Pi koppeln. MAC laut Memory:
> **D0:27:88:3D:68:9A** (verifiziere mit `scan on`, falls abweichend).

## E-T0 — bluez sicherstellen (frisches Image hat es nicht)
```bash
sudo apt install -y bluez
sudo systemctl enable --now bluetooth
bluetoothctl list            # zeigt einen Controller? (Pi 5 hat BT eingebaut)
# falls leer: BT per rfkill entsperren
rfkill list
sudo rfkill unblock bluetooth
```
- [ ] E.0 `bluetoothctl list` zeigt einen Controller. *(Falls auch nach
      `rfkill unblock` leer → BT-Kernel-Modul fehlt, `linux-modules-extra-raspi`.)*

## E-T1 — DS4 koppeln
```bash
# USB-Teleop (Stage D) vorher beenden (Strg+C in Terminal 4)
bluetoothctl
```
im `bluetoothctl`-Prompt:
```
power on
agent on
default-agent
scan on
# DS4 in Pairing-Mode (Share + PS ~5 s, bis LED schnell blinkt), MAC abwarten
pair D0:27:88:3D:68:9A
trust D0:27:88:3D:68:9A
connect D0:27:88:3D:68:9A
scan off
exit
```
```bash
ls /dev/input/js*            # js0 jetzt über BT
ros2 topic echo /joy         # Werte ändern sich?
```
- [ ] E.1 DS4 gekoppelt (bonded+trusted), `/joy` über BT aktiv.

```bash
# Terminal 4
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
- [ ] E.2 Bewegung in der Luft wie D.2, jetzt **drahtlos**.

> Reconnect später: einfach **PS-Taste** drücken (Controller ist „trusted").

---

# STAGE F — Am Boden (Done-Kriterium: Strom)

> **Erst wenn B–E aufgebockt sauber waren.** Roboter vom Bock nehmen, auf den
> Bauch legen (Beine in power_on_mid einziehbar). PSU-Stromanzeige im Blick,
> Kill-Switch in der Hand.

## F-T1 — Init + Aufstehen am Boden, Strom messen
```bash
# Terminal 1
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false serial_port:=/dev/servo2040 initial_pose:=power_on_mid
# Terminal 2 (nach Init)
ros2 launch hexapod_gait gait.launch.py use_sim_time:=false robot_description_file:="$HEX_URDF"
```
**Strom-Peak während des Aufstehens notieren.**
- [ ] F.1 Aufstehen **schürffrei**, Strom-Peak **nahe Stand-Niveau** (nicht
      >3,5 A mit Voltage-Drop). Roboter steht stabil.

## F-T2 — Fahren am Boden (langsam)
```bash
# Terminal 4 — Teleop (USB oder BT)
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
- [ ] F.2 Mit R1 + Stick **langsam** vorwärts (Tripod), kurze Strecke, **kein**
      Trip / Freeze / Voltage-Drop. Kill-Switch bereit.

## F-T3 — Sauberes Beenden + Shutdown
```bash
# Launches Strg+C (Terminal 4 → 2 → 1), dann PSU aus, dann:
sudo shutdown -h now
```
- [ ] F.3 Rail stromlos (Servos limp), Pi sauber heruntergefahren.

---

## Bei Problemen — Schnell-Diagnose

| Symptom | wahrscheinlich | Sofort |
|---|---|---|
| Beine zucken hart / Trip beim Init | Power-On-Zentrieren ohne Relay-Gate, oder FW-Limit zu niedrig | Kill-Switch; Relay-Gate + 7000-mA-FW prüfen |
| `WATCHDOG` / Relay-Drop in on_activate | Frame-Stille >200 ms (Pi langsamer) | melden — Heartbeat-Pause-Logik prüfen |
| `Package ... not found` | Workspace nicht gesourct | `source install/setup.bash` |
| gait-Timer reagiert nicht | `use_sim_time` true (kein /clock) | `use_sim_time:=false` (ist Default) |
| Port öffnet nicht | `/dev/servo2040` fehlt / falsch | `ls -l /dev/servo2040`, Servo2040 angesteckt? |
| `/joy` leer | js0 fehlt / falscher Controller | `ls /dev/input/js*`, ps4_usb vs ps4_bt |
