# C4 — Bluetooth (PS4 DualShock-4) — Test-Anleitung

> Headless/CLI-Pairing (kein GUI nötig — gilt 1:1 für den Pi später). Teleop-Logik unverändert,
> nur Profil `ps4_bt.yaml` + Pairing. Plan: [`C_teleop.md`](C_teleop.md) §C4.

---

## 0. Offline (bereits grün)
```bash
cd ~/hexapod_ws && source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_teleop
source install/setup.bash
colcon test --packages-select hexapod_teleop     # 22, 0 fail (inkl. BT-Konsistenz-Test)
```

---

## 1. DS4 per Bluetooth koppeln (headless, `bluetoothctl`)

> **Controller in Pairing-Mode:** **Share + PS-Taste** zusammen ~5 s halten, bis die Lightbar
> **schnell weiß-blau blinkt** (nicht dauerhaft leuchten).

```bash
bluetoothctl
# in der interaktiven Shell:
power on
agent on
default-agent
scan on
#   warten bis eine Zeile wie:  [NEW] Device A0:AB:51:XX:XX:XX Wireless Controller
#   → die MAC notieren
pair A0:AB:51:XX:XX:XX
trust A0:AB:51:XX:XX:XX     # merkt sich den Controller → künftig Auto-Reconnect
connect A0:AB:51:XX:XX:XX
scan off
quit
```
**Verifizieren:**
```bash
ls /dev/input/js*          # js0 sollte jetzt existieren
ros2 run joy joy_node &    # kurz, oder gleich über die Launch unten
ros2 topic echo /joy       # Sticks/Buttons bewegen → Werte ändern sich?
```
> **Reconnect später:** einfach die **PS-Taste** drücken (Controller ist „trusted") → verbindet
> automatisch. Trennen: `bluetoothctl` → `disconnect <MAC>`.

---

## 2. Indizes über BT verifizieren (ohne Roboter, schnell)

```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 run joy joy_node
# zweites Terminal:
cd ~/hexapod_ws && source install/setup.bash
ros2 topic echo /joy
#   linker Stick hoch  → axes[1] ändert sich?   seitwärts → axes[0]?
#   rechter Stick      → axes[3]?
#   R1 (Dead-Man)      → buttons[5]=1?   L1 → buttons[4]?
#   △/○/✕              → buttons[2]/[1]/[0]?   D-Pad → axes[6]/[7]?
```
Stimmen die Indizes/Vorzeichen → `ps4_bt.yaml` passt unverändert (beide mit Ctrl-C beenden).
Sonst → `config/ps4_bt.yaml` korrigieren (`axis_*`/`sign_*`/`button_*`), Teleop neu starten.

## 3. Voller Test mit Roboter (Sim) über BT

**Terminal A — Sim:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```
**Terminal B — Gait (feet-closer-Preset), warten bis `STATE_STANDING`:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_gait gait.launch.py \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/feet_closer_walk.yaml \
  use_sim_time:=true
```
**Terminal C — Teleop mit BT-Profil:**
```bash
cd ~/hexapod_ws && source install/setup.bash
ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt
```
→ Über den Controller testen (wie bei USB): R1 + linker Stick = fahren, rechter Stick = drehen,
L2/R2 = Höhe (ohne R1), △ = Sit/Stand-Toggle, ○-lang = Shutdown, ✕-lang = Show-Pose rein/raus
(in Show: R1 + Sticks = Vorderbeine, R1 + L2/R2 = Tibia-Reach), D-Pad ←/→ = Gangart, ↑/↓ = Schrittweite.

> **Index/Vorzeichen weichen ab?** In `config/ps4_bt.yaml` korrigieren (`axis_*`, `sign_*`,
> `button_*`), rebuild (`colcon build --packages-select hexapod_teleop`) bzw. installiertes YAML
> editieren, Teleop neu starten. (Auf Ubuntu 24.04 / `hid-playstation` ist das Layout meist
> identisch zu USB → oft keine Änderung nötig.)

---

## 4. Comms-Loss-Fail-safe für BT aktivieren (empfohlen)

Bei BT-Betrieb sinnvoll: wenn die Funkverbindung abreißt, verstummt `/joy` → der B1-Fail-safe
setzt den Roboter automatisch hin (Rest), statt regungslos zu stehen.

```bash
# am laufenden gait_node (STANDING):
ros2 param set /gait_node comms_loss_sitdown_timeout 5.0
# Test: Controller AUSSCHALTEN (PS-Taste ~10 s halten) → nach ~5 s ohne /cmd_vel:
#   Log "comms-loss ... auto sit-down (Rest)" + Roboter setzt sich hin.
# Wieder einschalten (PS-Taste) + /hexapod_stand_up bzw. △ → wieder hoch.
# Im Normalbetrieb ohne Controller wieder 0 setzen (sonst false-fire bei manuellem cmd_vel):
ros2 param set /gait_node comms_loss_sitdown_timeout 0.0
```

---

## 5. Fertig-Kriterium
- DS4 koppelt headless via `bluetoothctl`, `/joy` kommt über BT.
- Alle C2/C3-Funktionen über BT wie über USB (Indizes ggf. in `ps4_bt.yaml` justiert).
- (optional) Comms-Loss-Fail-safe greift bei BT-Abriss.
