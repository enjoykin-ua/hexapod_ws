# Stufe 1 — Test-Befehle (Sim, interaktiv)

> **Skizze vor Implementierung** (CLAUDE.md §4; final nach Code). Du führst aus,
> knappe Status-Meldung zurück. Vollständige Befehle, aus dem Doc aufrufbar.
> Setzt Stufe 0 (IMU läuft, `/imu/data`) + gebauten Workspace voraus.
>
> ⚠️ Parameternamen/Topics (`tip_angle_crit`, Safe-State-Reaktion) existieren erst
> **nach** der Stufe-1-Implementierung — bis dahin Soll-Ablauf.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait hexapod_sensors
source install/setup.bash
# Sim + Gait starten (zwei Terminals, jeweils gesourcet):
ros2 launch hexapod_bringup sim.launch.py enable_imu:=true
ros2 launch hexapod_gait gait.launch.py use_sim_time:=true
```

Aktuelle Schwellen einsehen:

```bash
ros2 param get /gait_node tip_angle_crit
ros2 param get /gait_node tip_rate_crit
ros2 param get /gait_node tip_debounce_ticks
```

---

## T1.6 — Unit-Tests (zuerst, ohne Sim)

```bash
colcon test --packages-select hexapod_gait --event-handlers console_direct+
colcon test-result --verbose
```

**Erwartung:** `TipMonitor`-Tests grün (Schwellen, Hysterese, Gating, Reset).

---

## T1.1 / T1.5 — Über Schwelle → Reaktion feuert

Roboter steht (STANDING). Modell im Gazebo-GUI langsam über `tip_angle_crit`
kippen (T1.1) bzw. ruckartig stoßen (T1.5, Rate-Trigger). Beobachten:

```bash
ros2 topic echo /imu/monitor          # Lage/Rate
# Safe-State-Beleg (je nach gewählter Reaktion):
ros2 service call /hexapod_safety_freeze std_srvs/srv/Trigger    # -> wird vom node gefeuert? Log prüfen
ros2 topic echo /rosout | grep -i 'tip\|safe\|freeze'
```

**Erwartung:** über `crit` → Safe-State (freeze/sit/gestaffelt laut §4-Entscheidung)
wird ausgelöst und geloggt; bei T1.5 schon durch schnelles Kippen unter dem
Winkel-Limit.

---

## T1.2 — Unter Schwelle → nichts

Roboter steht, Modell nur leicht antippen (< `warn`).

**Erwartung:** keine Reaktion, kein Safe-State, keine Warn-Spam.

---

## T1.3 — Laufen ohne Fehlalarm

```bash
ros2 topic pub -r 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.04}}'
# mehrere Gangzyklen beobachten:
ros2 topic echo /rosout | grep -i 'tip\|safe'
```

**Erwartung:** normales Laufen über mehrere Zyklen löst **nichts** aus
(Entprellung/Hysterese fängt den Gang-Ripple).

---

## T1.4 — Gating beim Aufstehen

Aus dem Sitzen aufstehen lassen (frischer Start, der Roboter durchläuft
`CARTESIAN_STANDUP`/`REPOSITION` — dort kippt der Körper gewollt):

```bash
# gait neu starten, Aufsteh-Sequenz beobachten:
ros2 topic echo /rosout | grep -i 'tip\|safe\|state'
```

**Erwartung:** während der Aufsteh-/Reposition-States **keine** Kipp-Reaktion
(State-Gating greift), erst in STANDING/WALKING wieder aktiv.

---

## Status-Rückmeldung (Vorlage)

```
T1.6 unit=OK/__   T1.1 crit=OK/__   T1.5 rate=OK/__   T1.2 quiet=OK/__   T1.3 walk=OK/__   T1.4 gate=OK/__
```
