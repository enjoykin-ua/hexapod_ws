# Stage F2 — Test-Anleitung (hexapod_hardware: Bit 7 → `/hexapod/shutdown_request`)

> Plan: [`F2_hw_shutdown_publisher_plan.md`](F2_hw_shutdown_publisher_plan.md).
> Unit-Tests laufen ohne HW; der Live-Test braucht das Board mit der **F1+F2-FW**
> geflasht. Workspace: `~/hexapod_ws`. User führt aus, knappe Status-Meldung genügt.

## Voraussetzungen

- Board mit aktueller FW (F1: Schalter→Bit 7) geflasht, Schalter an A1 verdrahtet.
- Workspace gebaut + gesourct:
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_hardware
source install/setup.bash
```

---

## F2-U1..U3 — Unit + Build + Lint (ohne HW)

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon test --packages-select hexapod_hardware
colcon test-result --all | grep hexapod_hardware
```
**Erwartung:** alle `0 errors, 0 failures`. Insbesondere
`test_servo2040_protocol.gtest.xml` enthält `DecodeStateShutdownRequestBit`
(Bit-7-Decode). Lint (uncrustify/cppcheck/lint_cmake) grün.

---

## F2-L1 — Live: Topic folgt dem Schalter (Board nötig)

Terminal A — realer Bringup gegen das Board:
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```

Terminal B — Topic mitlesen. **Wichtig:** QoS muss den Publisher matchen —
`reliable` **und** `transient_local`. Ein best_effort-Subscriber bekommt den
gelatchten Wert NICHT (transient_local-Historie wird nur über reliable geliefert):
```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 topic echo /hexapod/shutdown_request \
  --qos-reliability reliable --qos-durability transient_local
```

Ablauf:
1. Nach Start: `data: false` (Initial-Wert, latched).
2. Schalter **zu** (grün) → kurz → **auf** (rot) und **offen lassen**.
3. **Erwartung:** nach ~3 s erscheint **`data: true`**.
4. Schalter wieder **zu** → **`data: false`**.

(Während Normalbetrieb kommt **keine** neue Nachricht — publish-on-change. Nur die
echten Wechsel werden publiziert.)

## F2-L2 — Late-Join: latched Wert (Board nötig)

1. F2-L1 bis Schritt 3 fahren, sodass der letzte publizierte Wert **`true`** ist.
2. Echo aus Schritt B **beenden** und **neu** starten:
```bash
ros2 topic echo /hexapod/shutdown_request \
  --qos-reliability reliable --qos-durability transient_local
```
**Erwartung:** der neu gestartete Echo bekommt **sofort `data: true`** (latched),
ohne dass der Schalter erneut bewegt wird.

---

## Erfolgs-Kriterium F2
F2-U1..U3 grün **und** F2-L1/L2 wie erwartet → Progress-Checkliste F2.1–F2.7
abhaken, dann Self-Review (Plan §3, F2.8). Danach F3 (gait_node Confirm-Flag).
