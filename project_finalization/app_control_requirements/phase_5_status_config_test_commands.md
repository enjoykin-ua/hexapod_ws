# Phase 5 — Test-Befehle: Status-Overlay + Config-Manifest (Sim)

> Du führst aus, knappe Status-Meldung zurück. **Kontext-Tags:**
> **▶ ROS (hexapod_ws)** = Desktop-Terminal · **▶ App** = *echte App = Integration P5.15*.
> Hier simulieren `ros2 topic echo` / `ros2 param set` die App über rosbridge.
>
> **Ziel:** die Always-On-Schicht liefert Capabilities + Config-Manifest + Alerts schon **ohne**
> laufenden Stack; der laufende Stack liefert `/hexapod/status` (State/Stance/Gangart/Caps) +
> `/hexapod/tempo`; die Whitelist-Params sind **live** verstellbar (mit Reject bei Gating/Cap).
> Plan: [`phase_5_status_config_plan.md`](phase_5_status_config_plan.md) · Progress:
> [`phase_5_status_config_progress.md`](phase_5_status_config_progress.md).

---

## Vorbereitung (▶ ROS)
```bash
cd ~/hexapod_ws && colcon build --packages-select hexapod_gait hexapod_teleop hexapod_supervisor hexapod_bringup
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
```

## Setup: Always-On-Schicht (Terminal 1, ▶ ROS)
```bash
source /opt/ros/jazzy/setup.bash && source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_bringup always_on.launch.py        # rosbridge + supervisor + hmi_status
```
> **Terminal 2 (▶ ROS)** = Prüf-/Steuer-Befehle (jeweils zuerst sourcen).

---

## T5.3 — Capabilities gelatcht (ohne laufenden Stack)
```bash
ros2 topic echo /hexapod/capabilities --qos-reliability reliable --qos-durability transient_local --once --full-length
```
**✅ Erwartung:** vollständiges JSON mit `gaits`/`stance_modes`/`tempo_presets`. Kommt sofort
(gelatcht), obwohl Gazebo/gait **nicht** laufen.
> **Hinweis:** ohne `--full-length` kürzt `ros2 topic echo` lange Strings mit `…` — das ist reine
> **Anzeige-Kürzung**, die Daten sind vollständig (T5.4 beweist es für das große Manifest).

## T5.4 — Config-Manifest gelatcht (39 Params)
```bash
ros2 topic echo /hexapod/config_manifest --qos-reliability reliable --qos-durability transient_local --once --field data \
  | python3 -c "import sys,json; d=json.loads(next(l for l in sys.stdin if l.strip().startswith('{'))); print('params:', len(d['params']), '| advanced:', sum(1 for p in d['params'] if p.get('advanced')))"
```
**✅ Erwartung:** `params: 39 | advanced: 16`.

## T5.8 — Alerts: eine WARN erscheint auf /hexapod/alerts

**Terminal 2a (▶ ROS)** — Alerts im Vordergrund mitlesen (laufen lassen):
```bash
ros2 topic echo /hexapod/alerts --qos-reliability reliable --qos-durability transient_local
```
**Terminal 2b (▶ ROS)** — drei WARN auf `/rosout` erzeugen (mit kurzer Discovery-Wartezeit,
sonst geht die erste evtl. verloren):
```bash
python3 -c "
import rclpy
rclpy.init()
n = rclpy.create_node('alert_test')
rclpy.spin_once(n, timeout_sec=1.5)          # Discovery setteln lassen
for i in range(3):
    n.get_logger().warn(f'TESTWARN {i}')
    rclpy.spin_once(n, timeout_sec=0.4)
n.destroy_node(); rclpy.shutdown()
"
```
**✅ Erwartung:** in Terminal 2a erscheinen **genau 3** Zeilen
`{"stamp":…,"level":"WARN","name":"alert_test","msg":"TESTWARN 0/1/2"}`. (Ctrl-C in 2a zum Beenden.)
> **Sieht du jede WARN mehrfach?** Dann laufen mehrere `hmi_status` parallel (z.B. ein alter aus
> einem früheren `always_on`-Start). `ros2 node list | grep hmi_status` → sollte **genau einen**
> zeigen; sonst den alten `always_on`-Prozess sauber beenden (Ctrl-C) und neu starten.

---

## Stack starten → Status/Tempo/Live-Params

**Roboter hochfahren** (der App-Pfad: on-demand Stack = gait + teleop, Bauch-Start):
```bash
ros2 service call /hexapod_bringup_start std_srvs/srv/Trigger {}    # ~15 s, Roboter auf dem Bauch
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}         # aufstehen (STANDING)
```

## T5.1 — /hexapod/status wird published (~5 Hz)
```bash
ros2 topic hz /hexapod/status          # ~5 Hz
ros2 topic echo /hexapod/status --once # JSON: state/stance_idx/stance/gait/safety_frozen/tip/*_cap
```
**✅ Erwartung:** ~5 Hz; `state:"STANDING"`, `stance:"mittel"`, `gait:"tripod"`,
`step_height_cap:0.05`, `step_length_cap:0.08`.

## T5.2 — Dynamische Caps ändern sich mit dem Stance-Modus
```bash
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: true}"   # -> hoch
ros2 topic echo /hexapod/status --once   # stance:"hoch", step_height_cap:0.08, step_length_cap:0.05
ros2 service call /hexapod_cycle_stance std_srvs/srv/SetBool "{data: false}"  # zurueck -> mittel
```
**✅ Erwartung:** `stance` + `step_height_cap`/`step_length_cap` folgen dem Modus (tief 0.04/0.06 ·
mittel 0.05/0.08 · hoch 0.08/0.05).

## T5.2b — /hexapod/tempo (latched, aktives Preset)
```bash
ros2 topic echo /hexapod/tempo --qos-reliability reliable --qos-durability transient_local --once
```
**✅ Erwartung:** JSON `{"tempo":"schnell","tempo_idx":2,"linear_x_scale":...}` (Default-Preset).

## T5.5 — Whitelist-Param live verstellen (Slider-Ersatz)
```bash
ros2 param set /joy_to_twist linear_x_scale 0.12     # akzeptiert, wirkt sofort (schneller vor)
ros2 param set /gait_node step_height 0.03           # akzeptiert (unter mittel-Cap 0.05)
ros2 param set /gait_node leveling_enable true       # akzeptiert
```
**✅ Erwartung:** alle `Set parameter successful`; Fahren/Verhalten ändert sich entsprechend.

## T5.6 — Reject: standing_only-Param außerhalb STANDING
```bash
ros2 service call /hexapod_sit_down std_srvs/srv/Trigger {}     # -> SAT (nicht STANDING)
ros2 param set /gait_node cycle_time 1.5                        # ERWARTET: Reject
ros2 service call /hexapod_stand_up std_srvs/srv/Trigger {}     # wieder aufstehen
```
**✅ Erwartung:** `Setting parameter failed: params ['cycle_time'] require STATE_STANDING …` —
der `reason`-String, den die App anzeigt.

## T5.7 — Reject: step_height über dem Stance-Cap (H1)
```bash
ros2 param set /gait_node step_height 0.09      # mittel-Cap = 0.05 -> ERWARTET: Reject
```
**✅ Erwartung:** `… step_height 0.09 exceeds validated max 0.05 for stance mode 'mittel' (H1 gate…)`.

## T5.10 — Walking-Regression (Status-Timer stört den Gait-Tick nicht)
```bash
ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'   # Ctrl-C zum Stoppen
```
**✅ Erwartung:** Roboter läuft normal vorwärts (kein Ruckeln/Regression durch den 5-Hz-Status-Timer);
`/hexapod/status` zeigt `state:"WALKING"`.

---

## Was NICHT in Phase 5 (scope-out)
- App-Overlay/Config-Panel/Dropdowns/Alerts-View/3D-Viz (P5.10–P5.13) = **Android-Session** gegen den
  festgezurrten Contract §6.
- Config-Persistenz (nicht gewünscht) · E-Stop scharf/Recovery (Phase 6) · Audio (Phase 7).
- Contract §6 festzurren + v0.9 = **nach** dieser Live-Verifikation.

## Melde-Vorlage
T5.3 Capabilities? · T5.4 39/16? · T5.8 WARN in alerts? · T5.1 status ~5 Hz + Felder? · T5.2 Caps
folgen Stance? · T5.2b tempo? · T5.5 Sets akzeptiert + Wirkung? · T5.6 cycle_time-Reject? · T5.7
step_height-Cap-Reject? · T5.10 läuft normal? Plus Auffälligkeiten.
