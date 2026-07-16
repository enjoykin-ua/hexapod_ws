# Phase 2 — Test-Befehle: Steuer-Grundstrecke (rosbridge + /joy in Sim)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:**
> **▶ ROS (hexapod_ws)** = Desktop-Terminal · **▶ Handy** = Bedienung am Gerät ·
> **▶ App** = *in dieser Phase noch nicht* (echte App = Integration P2.10).
>
> **Ziel:** beweisen, dass ein WebSocket-Client `/joy` über rosbridge publisht → der
> **Sim-Roboter fährt** (Meilenstein T2.2), inkl. NF1-Failsafe. Ohne Handy, mit Test-Client.
> Plan: [`phase_2_control_baseline_plan.md`](phase_2_control_baseline_plan.md).

---

## Vorbereitung (einmalig)

**▶ ROS:**
```bash
# 1. rosbridge installieren (einzige apt-Installation dieser Phase):
sudo apt install -y ros-jazzy-rosbridge-suite

# 2. Test-Client-Abhängigkeit (Ubuntu 24.04: System-Paket, kein pip wegen PEP 668):
sudo apt install -y python3-websocket

# 3. Workspace bauen (falls noch nicht):
cd ~/hexapod_ws && colcon build --packages-select hexapod_bringup hexapod_teleop
```

> **Firewall (nur falls `ufw` aktiv):** Port 9090 im lokalen Netz öffnen, damit das Handy
> später rankommt (für den Test-Client auf demselben Rechner nicht nötig):
> ```bash
> sudo ufw status
> sudo ufw allow from 192.168.0.0/16 to any port 9090 proto tcp   # nur privates Netz
> ```

---

## Setup: drei Terminals (alle ▶ ROS)

Jeweils zuerst sourcen:
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

**Terminal 1 — Sim-Walk (flach), Roboter steht nach Auto-Standup auf:**
```bash
ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0
```
> ~12 s warten (gait_delay), bis der Roboter **steht**. Erst dann weiter.

**Terminal 2 — app-Teleop-Schicht (rosbridge :9090 + joy_to_twist im app-Modus, KEIN joy_node):**
```bash
ros2 launch hexapod_bringup app_teleop.launch.py
```

**Terminal 3 — Prüfungen + Test-Client** (Befehle der einzelnen Tests unten).

---

## T2.1 — rosbridge kommt hoch

**▶ ROS (Terminal 3):**
```bash
ros2 node list | grep -E "rosbridge_websocket|rosapi"
ss -tlnp 2>/dev/null | grep 9090        # Port lauscht?
```
**✅ Erwartung:** beide Nodes gelistet; `:9090` im LISTEN-Zustand.

## T2.2 — Meilenstein: Test-Client fährt den Sim-Roboter

**▶ ROS (Terminal 3):**
```bash
python3 ~/hexapod_ws/tools/joy_ws_test_client.py --host 127.0.0.1 --duration 5 --forward 0.6
```
**✅ Erwartung:** In Gazebo **läuft der Roboter ~5 s vorwärts** (R1-Dead-Man gehalten + linker
Stick vor), dann stoppt der Client. → Kette rosbridge→`/joy`→`joy_to_twist`→`/cmd_vel`→gait→Sim.

> Melde: fährt er vorwärts? Ruckelt/zuckt etwas? Dreht statt vor (→ Vorzeichen)?

## T2.3 — genau eine /joy-Quelle (kein joy_node)

**▶ ROS (Terminal 3), während der Client läuft (Duration hochsetzen, z.B. `--duration 15`):**
```bash
ros2 node list | grep joy_node          # MUSS leer sein (app-Modus)
ros2 topic info /joy                     # Publisher count = 1 (rosbridge)
```
**✅ Erwartung:** kein `joy_node`; genau **1** `/joy`-Publisher.

## T2.4 — /joy-QoS kompatibel

**▶ ROS (Terminal 3), während der Client läuft:**
```bash
ros2 topic info /joy --verbose          # QoS Publisher (rosbridge) + Subscriber (joy_to_twist)
```
**✅ Erwartung:** Publisher **und** Subscriber gelistet, Reliability/Durability kompatibel (dass
T2.2 fuhr, beweist die Zustellung schon). Melde Reliability des Publishers (RELIABLE/BEST_EFFORT).

## T2.5 — NF1 Comms-Loss: Publish-Stop → Roboter stoppt

**▶ ROS (Terminal 3), zwei Schritte:**
```bash
# a) /cmd_vel mitlesen (eigenes Fenster oder vor dem Client starten):
ros2 topic echo /cmd_vel
# b) Client kurz fahren lassen, dann NICHT neu starten:
python3 ~/hexapod_ws/tools/joy_ws_test_client.py --duration 4 --forward 0.6
```
**✅ Erwartung:** Während des Laufs `/cmd_vel` ≠ 0; **nach** Client-Ende verstummt `/joy` →
`cmd_vel_timeout` greift → Roboter **hält an** (kein Weiterlaufen). Das ist das Screen-Lock-/
Absturz-Sicherheitsnetz.

## T2.6 — Handy erreicht die Desktop-rosbridge (Netz über Router)

**▶ ROS:** Desktop-IP im Router-Netz ermitteln:
```bash
hostname -I
```
**▶ Handy:** im Browser `http://<Desktop-IP>:9090` öffnen.
**✅ Erwartung:** rosbridge antwortet (typisch: „Can \"Upgrade\" only to \"WebSocket\".") →
der Port ist **vom Handy aus erreichbar**. (Kein hübsches Bild — die Fehlermeldung *ist* der
Beweis, dass die Verbindung durchkommt.)

## Gegentest — ohne Dead-Man darf er NICHT fahren

**▶ ROS (Terminal 3):**
```bash
python3 ~/hexapod_ws/tools/joy_ws_test_client.py --duration 3 --forward 0.6 --no-deadman
```
**✅ Erwartung:** Roboter **bleibt stehen** (R1 nicht gehalten → Dead-Man sperrt). Beweist, dass
die Sicherheits-Gating-Logik greift.

---

## Was NICHT in Phase 2 (scope-out)

- Echte Android-App End-to-End (Handy → rosbridge → Sim) = **Integration P2.10** (Android-Session).
- Vorzeichen-Endverifikation aller Achsen/Buttons = im Integrations-Schritt mit der App.
- systemd-Boot-Start = Pi/HW-Netz-Stage (hier nur Artefakt).
- Harte Latenz-Zahl (NF3) = qualitativ, spätere Politur.

## Melde-Vorlage

T2.1 ok? · T2.2 fährt vorwärts? · T2.3 kein joy_node / 1 Publisher? · T2.4 QoS? · T2.5 stoppt
nach Client-Ende? · T2.6 Handy erreicht :9090? · Gegentest steht still? Plus Auffälligkeiten.
