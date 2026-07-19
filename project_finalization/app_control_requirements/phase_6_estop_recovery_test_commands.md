# Phase 6 — Test-Befehle: E-Stop + Recovery (Sim)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:**
> **▶ ROS (hexapod_ws)** = Desktop-Terminal · **▶ App** = *echte App = Integration P6.11 (Android-Session)*.
> Hier simulieren `ros2 service call` / `ros2 topic echo` die App über rosbridge.
>
> **Ziel:** ein **scharfer Not-Halt** friert den Roboter **latched** ein (Tick hält, kein
> `joint_trajectory`-Publish, `/hexapod/status.safety_frozen == true`, resumt **nicht** von selbst);
> **`/hexapod_recover`** bringt ihn ursachen-agnostisch per **Joint-Space-Ramp** zurück nach STANDING.
> Plan: [`phase_6_estop_recovery_plan.md`](phase_6_estop_recovery_plan.md) · Progress:
> [`phase_6_estop_recovery_progress.md`](phase_6_estop_recovery_progress.md).

---

## Vorbereitung (▶ ROS)
```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_gait
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

## Unit-Tests (▶ ROS) — T6.4 / T6.6 / T6.7 (laufen ohne Sim)
```bash
colcon test --packages-select hexapod_gait --event-handlers console_direct+
colcon test-result --verbose
```
**✅ Erwartung:** alle grün (0 errors / 0 failures), inkl. `test_recover.py`
(Ramp-kein-Limit T6.4, Reject-ohne-joints T6.7, Reset-Latches T6.6) + bestehende gait-Tests
(Walking-Regression, T6.9) unverändert.

---

## Sim-Stack hoch (Terminal 1, ▶ ROS)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py     # rosbridge + supervisor + hmi_status
```
**Terminal 2 (▶ ROS)** — Stack starten + aufstehen (jeweils zuerst sourcen):
```bash
ros2 service call /hexapod_bringup_start std_srvs/srv/Trigger {}   # ~15 s, Roboter auf dem Bauch (SAT)
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}        # aufstehen (STANDING)
```

---

## T6.1 — E-Stop friert ein (Status zeigt frozen)
```bash
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
ros2 topic echo /hexapod/status --once     # safety_frozen: true
```
**✅ Erwartung:** Service `success=true`, `message` „E-STOP …"; `/hexapod/status` zeigt
`safety_frozen: true`. Der Roboter hält seine Pose (kein neuer `joint_trajectory`-Publish).

## T6.2 — E-Stop im WALKING → sofort Stopp + latched (resumt NICHT)
**Terminal 3 (▶ ROS)** — vorwärts laufen lassen:
```bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**Terminal 2 (▶ ROS)** — während er läuft, Not-Halt:
```bash
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
ros2 topic echo /hexapod/status --once     # safety_frozen: true; state haelt
```
**✅ Erwartung:** Roboter stoppt **sofort** und bleibt stehen, **auch während `/cmd_vel` weiter
publisht** (latched — resumt nicht von selbst). (Terminal 3 mit Ctrl-C beenden.)

## T6.3 / T6.5 — Recovery aus eingefrorener Pose → STANDING (ursachen-agnostisch)
```bash
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}
ros2 topic echo /hexapod/status --once     # nach ~3 s: state STARTUP_RAMP -> STANDING, safety_frozen: false
```
**✅ Erwartung:** Service `success=true` „recovering — joint-space ramp to stand"; der Roboter
rampt **smooth** in den Stand; `/hexapod/status` zeigt `state: STARTUP_RAMP` → `STANDING` und
`safety_frozen: false`. Danach ist er wieder normal fahrbar.
> **T6.5 (any-state):** T6.3 einmal aus WALKING-Freeze (nach T6.2) und einmal aus STANDING-Freeze
> (nach T6.1) wiederholen — beide Male gleiches Ergebnis (ursachen-agnostisch).

## T6.6 (Live-Ergänzung) — nach Recovery kein Sofort-Re-Freeze
```bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # Ctrl-C zum Stoppen
ros2 topic echo /hexapod/status --once     # state: WALKING, safety_frozen: false, tip: none
```
**✅ Erwartung:** Roboter läuft normal an (Latches/Monitore sauber zurückgesetzt — kein sofortiger
erneuter Freeze).

## T6.9 — Walking-Regression (Freeze-Gate stört den normalen Lauf nicht)
```bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
```
**✅ Erwartung:** ohne vorherigen E-Stop läuft der Roboter unverändert normal (das neue
`if _safety_frozen: return` greift nur nach einem echten Freeze).

---

## T6.8 (HW, User) — am echten Roboter
- **E-Stop:** während des Laufens → **PWM-Hold** (Servos halten die letzte Position, Plugin-Freeze).
- **Recover:** → **smooth** per Joint-Space-Ramp wieder in den Stand.
> **Grenze [D6]:** kein Aufrichten aus Kipplage — Roboter vorher grob aufrecht auf ebenen Boden
> stellen, *dann* Recover.

---

## E2E mit der echten App (P6.11 — App + ROS zusammen)

> **Kontext-Tags:** **▶ ROS** = Desktop-Terminal · **▶ App** = Handy (Kishi). Ziel: E-Stop/Recover
> aus der App wirken auf den Sim-Roboter, **und** ein hier erzwungener Freeze wird in der App
> korrekt angezeigt (beweist: App leitet `frozen` aus `/hexapod/status.safety_frozen` ab).

### Setup (▶ ROS, Terminal 1) — Always-On-Schicht (damit die App connecten kann)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py
```
> Desktop-IP für die App: `hostname -I | awk '{print $1}'` → in der App als Host, Port 9090.

### Stack + Aufstehen — entweder in der App ODER hier (▶ ROS, Terminal 2)
**App-Weg (▶ App):** „Hexapod starten" → „Aufstehen". **CLI-Weg (▶ ROS, Terminal 2):**
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 service call /hexapod_bringup_start std_srvs/srv/Trigger {}   # ~15 s, Gazebo + gait, Bauch (SAT)
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}        # STANDING
```

### Status live mitlesen (▶ ROS, Terminal 2, laufen lassen)
```bash
ros2 topic echo /hexapod/status --field data
```
> Zeigt den JSON-String ~5 Hz; beim Testen siehst du `safety_frozen` und `state` live umspringen.

### Test A — E-Stop AUS DER APP → ROS beobachtet
**▶ App:** den roten **E-STOP** tappen. **✅ Erwartung:** in Terminal 2 springt
`"safety_frozen":true`, `state` hält; der Roboter friert in Gazebo ein; das App-Overlay zeigt
**frozen** + der **Recover-Button** erscheint.

### Test B — Freeze HIER erzwingen → App zeigt frozen (▶ ROS, Terminal 3)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}
```
**✅ Erwartung:** die **App** zeigt **frozen** + Recover-Button — obwohl der Freeze **nicht** vom
App-Button kam. Das beweist, dass die App `safety_frozen` aus `/hexapod/status` ableitet.

### Test C — Recover AUS DER APP → ROS beobachtet
**▶ App:** **Recover** tappen. **✅ Erwartung:** in Terminal 2 geht `state` `STARTUP_RAMP` →
`STANDING`, `safety_frozen":false`; der Roboter rampt in Gazebo **smooth** in den Stand; der
Recover-Button verschwindet wieder. Danach ist er normal fahrbar.

### Test D (optional, stärkster) — E-Stop IM LAUFEN aus der App
**▶ App:** mit dem Kishi vorfahren, dann **E-STOP** tappen. **✅ Erwartung:** Roboter stoppt
**sofort** + bleibt (latched, resumt nicht, auch wenn du weiter am Stick bist); Terminal 2
`safety_frozen":true`. Danach **Recover** → steht wieder.

---

## Was NICHT in Phase 6 (scope-out)
- App-E-STOP-/Recover-Button + frozen/recovering-Anzeige (P6.8/P6.9) = **Android-Session** gegen
  Contract §2/§6.
- Aufrichten aus Kipplage (Mensch); scrape-freier Rückweg; `recover_duration` final justieren (Live);
  E-Stop-Hardware-Taster. Params-Fix (Recovery stellt nur den Zustand her, nicht die Params).

## Melde-Vorlage
Unit-Tests grün (test_recover)? · T6.1 estop → frozen:true? · T6.2 Stopp im Walking + latched
(resumt nicht)? · T6.3 recover → STARTUP_RAMP→STANDING + frozen:false? · T6.5 any-state gleich? ·
T6.6 kein Sofort-Re-Freeze? · T6.9 normal-Walking unverändert? Plus Auffälligkeiten.
