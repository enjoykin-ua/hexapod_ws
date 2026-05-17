# Phase 10 — Stufe C — Test-Anleitung (User-Smoke)

**Was geprüft wird:** Erstes echtes Aktivieren der Stack-Pipeline gegen
einen einzelnen Hexapod-Servo. Ziel: `direction`-Bit für
`leg_6_coxa_joint` final bestimmen und Endlagen-Test ±1.0 rad fahren
ohne Stall oder Watchdog-Trip.

> ⚡ **Erste echte Servo-Bewegung dieser Phase.** PSU 7.0 V / CC 3 A,
> User-Hand bereit, PSU-Aus-Knopf griffbereit.

**Plan:** [`phase_10_stage_c_plan.md`](phase_10_stage_c_plan.md)
**Sicherheits-Setup:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md)

**Was NICHT in Stage C ausgeführt wird:**
- **Femur + Tibia bleiben abgeklemmt** (Stage D / Stage E)
- **Kein IK-Aufruf** (Stage F)
- **Kein Strom-Logging-CSV** (Stage F)

---

## Bench-Setup (VOR allen Tests!)

> ⚡ **Sicherheits-Recap:** PSU OUTPUT bleibt AUS während Stecken/Abklemmen.
> [`safety_setup.md`](phase_10_safety_setup.md) §4 Anschluss-Sequenz.

1. **Bench-PSU OUTPUT AUS**
2. **Setpoint:** 7.0 V, **CC-Limit 3 A** (für 1 Coxa-Servo, Diymore 8120MG Stall ~2.5 A × 1.2 Marge)
3. **Servo2040 USB** am Desktop, sichtbar:
   ```bash
   ls -l /dev/ttyACM*
   # erwartet: /dev/ttyACM0 → Servo2040
   ```
4. **Coxa-Servo (Pin 15)** an Servo2040-Header anstecken:
   - Polarität: braun=GND, rot=V+, gelb/orange/weiß=Signal
   - Sichtprüfung: kein Pin daneben
5. **Femur (Pin 16) + Tibia (Pin 17) bleiben elektrisch abgeklemmt**
   (Header-Loch leer; Servos hängen mechanisch am Bein, sind aber stromlos)
6. **leg_5:** zurück in **ruhige Default-Pose** (keine worst-case-Pose mehr
   nötig — Stage B `pulse_min=1280` schützt gegen Self-Collision)
7. **leg_6-Mechanik:**
   - User-Hand bereit, Bein **radial außen** zu halten (= Coxa nahe Joint-Mitte)
   - Femur+Tibia hängen passiv nach Schwerkraft (irrelevant für Coxa-Test)
8. **PSU-OUTPUT AN** — Strom-Anzeige beobachten:
   - **< 200 mA idle erwartet** (Servo2040 + 1 stromloser Servo-Header-Wartemodus)
   - Strom > 500 mA = Verdacht auf Kurzschluss, sofort AUS, Stecker prüfen

---

## C-T3 — Plugin-Bringup (~3 min)

> **Vorbedingung:** Bench-Setup oben grün.

### Schritt 1: Launch starten

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

### Schritt 2: User-Hand-Position (kritisch!)

> 🚨 **User hält leg_6 nahe Coxa-Joint-Mitte** während der nächsten ~5 s,
> bis das `on_activate`-ENABLE durch ist. Position: Bein radial außen
> vom Body weg (90° zur Body-Längsachse).

### Schritt 3: Log-Sequenz beobachten

**Erwartete Logs (in Reihenfolge):**

```
[INFO] [...] [hexapod_hardware]: HexapodSystemHardware::on_init starting (info_.joints.size=18)
[INFO] [...] [hexapod_hardware]: Config: serial_port=/dev/ttyACM0, calibration_file=.../servo_mapping.yaml, loopback_mode=false
[INFO] [...] [hexapod_hardware]: on_init complete — 18 joints mapped to 18 servo pins, calibration loaded from .../servo_mapping.yaml
[INFO] [...] [hexapod_hardware]: on_configure complete — serial port /dev/ttyACM0 opened, RX worker started
[INFO] [...] [hexapod_hardware]: on_activate starting (boot sequence: 1 RESET + 18 ENABLE_SERVO + 1 SET_TARGETS, ~1 s)
[INFO] [...] [hexapod_hardware]: on_activate complete — 18 servos enabled, neutral pulses set
[INFO] [...] spawn_joint_state_broadcaster ... configured ... activated
[INFO] [...] spawn_leg_6_controller ... configured ... activated
... (alle 6 leg-Controller)
```

**Nicht erlaubte Errors (= sofort PSU AUS, Stage C STOP):**
- `UNDERVOLTAGE_TRIPPED` — PSU < 5.5 V
- `WATCHDOG_TRIPPED` — Plugin sendet < 5 Hz SET_TARGETS
- `ANY_SERVO_OVERCURRENT` — Stall am Anschlag

### Schritt 4: Erwartung am echten Bein

Nach `on_activate complete`:
- **Coxa-Servo** zieht das Bein zur Joint-Mitte (`pulse_zero = 1550 µs`)
- Wenn User-Hand das Bein schon dort hielt: minimal-bis-keine Bewegung
- **Femur + Tibia:** bleiben stromlos, hängen mechanisch nach Gravity

**User-Bestätigung C-T3:**
- [ ] Plugin-Bringup ohne `UNDERVOLTAGE`/`WATCHDOG`/`OVERCURRENT`-Errors
- [ ] Coxa-Servo bewegt das Bein zur Joint-Mitte (sichtbar oder schon dort)
- [ ] Kein Stall-Brumm

---

## C-T4 — direction-Bestimmung (+0.1 rad) (~5 min)

### Schritt 1: RViz starten (Terminal 2, parallel)

```bash
# Terminal 2
source ~/hexapod_ws/install/setup.bash
rviz2
```

Im RViz:
- **Add** → **RobotModel**, Description Topic = `/robot_description`
- **Add** → **TF**, Fixed Frame = `base_link`
- RViz zeigt das Hexapod-Modell in Default-Pose

### Schritt 2: Test-Goal +0.1 rad

```bash
# Terminal 3
source ~/hexapod_ws/install/setup.bash
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [-1.0, 0.0, 0.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

### Schritt 3: Bewegung beobachten

**Coxa-Drehung visuell:** ~5.7° (= 0.1 rad). Klein, aber sichtbar.

**Richtungs-Konvention (URDF-positive):**
- leg_6 sitzt vorne-links (siehe [`docs/00_conventions.md`](../docs/00_conventions.md) §1)
- Coxa-Joint dreht um Z-Achse (vertikal)
- **+0.1 rad → Bein schwenkt gegen Uhrzeigersinn (von oben gesehen)**
  → das heißt für leg_6: **das Fußende geht Richtung HINTEN-LINKS** (Richtung leg_5)

### Schritt 4: Vergleich RViz ↔ echtes Bein

| Beobachtung | direction-Wert | Aktion |
|---|---|---|
| RViz-Bein und echtes Bein drehen **synchron** in dieselbe Richtung | `+1` korrekt | Nichts tun, C-T4 ✅ |
| RViz dreht Richtung leg_5, echtes Bein dreht Richtung leg_1 | `-1` nötig | siehe C-T4.5 |

**User-Bestätigung C-T4:**
- [ ] Coxa-Bein hat ~5° geschwenkt
- [ ] Richtung dokumentiert: **synchron mit RViz** / **gegenläufig** (eine Option ankreuzen)

---

## C-T4.5 — Optional: direction-Flip auf -1 (nur wenn C-T4 gegenläufig) (~10 min)

```bash
# Terminal 1: Ctrl-C (real.launch.py beenden)
#   → Plugin sendet 18× DISABLE_SERVO automatisch
# Bench-PSU OUTPUT AUS (für Sicherheit während YAML-Edit)
```

Claude editiert das YAML:

```yaml
# src/hexapod_hardware/config/servo_mapping.yaml, Pin 15:
15:
  joint: leg_6_coxa_joint
  pulse_min:  1280
  pulse_zero: 1550
  pulse_max:  1860
  direction:  -1    # NEU: Flip von default +1
```

Rebuild + Relaunch:

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
# Bench-PSU OUTPUT AN
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Dann C-T4 wiederholen. Jetzt sollte echtes Bein und RViz synchron sein.

---

## C-T5 — RViz-Sync-Check (~2 min)

Bereits in C-T4 mitabgefragt. **Sync = die richtige Bewegung in beide
Richtungen, sowohl in RViz als auch real, in identischer Pose.**

**User-Bestätigung C-T5:**
- [ ] RViz-Modell zeigt nach +0.1-rad-Goal **dieselbe Coxa-Pose** wie echtes Bein

---

## C-T6 — Endlagen-Test (±1.0 rad in 5 Schritten) (~10 min)

> 🚨 **Vor jedem Goal:** Bein-Bewegung beobachten, PSU-Strom checken
> (< 2 A erwartet), Sichtkontrolle ob Bein-zu-leg_5-Abstand > 1 cm bleibt.

### Schritt-Sequenz (jeweils via `ros2 action send_goal`, Format wie C-T4)

| # | positions (coxa, femur, tibia) | time_from_start | Beobachtung |
|---|---|---|---|
| 1 | `[0.5, 0.0, 0.0]` | 3 s | Bein schwenkt +25° (URDF-positive) |
| 2 | `[1.0, 0.0, 0.0]` | 3 s | Bein nochmal +25° → gesamt +57° |
| 3 | `[0.0, 0.0, 0.0]` | 3 s | zurück zur Mitte |
| 4 | `[-0.5, 0.0, 0.0]` | 3 s | Bein schwenkt -25° (Richtung leg_5) |
| 5 | `[-1.0, 0.0, 0.0]` | 3 s | Bein nochmal -25° → gesamt -57°, **Sichtkontrolle: > 1 cm Abstand zu leg_5** |
| 6 | `[0.0, 0.0, 0.0]` | 3 s | final zurück zur Mitte |

**Bei jedem Goal:**
- Strom-Display der PSU < 2 A
- Kein Servo-Brumm
- RViz und echtes Bein synchron

**User-Bestätigung C-T6:**
- [ ] Alle 6 Goals erreicht
- [ ] Kein Stall-Brumm in irgendeiner Pose
- [ ] PSU-Strom blieb < 2 A
- [ ] Bei -1.0 rad: leg_6 **berührte leg_5 NICHT** (Sichtkontrolle)

---

## C-T7 — Shutdown + Abklemm-Sequenz (~3 min)

```bash
# Terminal 1: Ctrl-C → real.launch.py shutdown
# Plugin sendet automatisch 18× DISABLE_SERVO
```

Dann:

1. **Bench-PSU OUTPUT AUS**
2. **Coxa-Servo-Connector** von Pin 15 abziehen (für Stage D Vorbereitung)
3. PSU bleibt eingestellt (7.0 V / 3 A), wartet auf Stage D

**User-Bestätigung C-T7:**
- [ ] real.launch.py sauber heruntergefahren
- [ ] PSU OUTPUT AUS
- [ ] Coxa-Servo abgeklemmt

---

## Fehlerdiagnose-Tabelle

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| Plugin findet `/dev/ttyACM0` nicht | Servo2040 nicht via USB verbunden oder fehlende dialout-Gruppe | `ls -l /dev/ttyACM*` → Symlink prüfen; ggf. `sudo usermod -aG dialout $USER` + neu einloggen |
| UNDERVOLTAGE_TRIPPED beim Bringup | Bench-PSU < 5.5 V am Servo-Rail | PSU 7.0 V verifizieren, V+/GND-Anschluss prüfen, dünne Kabel? |
| WATCHDOG_TRIPPED während Test | Plugin sendet < 5 Hz SET_TARGETS | `controller_manager update_rate` checken (sollte 50 Hz aus `controllers.real.yaml` sein) |
| ANY_SERVO_OVERCURRENT für leeren Pin | Firmware misst falsch auf Pin ohne Servo | aus Stolperfallen-Liste: Log auf welchem Servo-Idx Error kommt → wenn Pin 16/17, ignorieren (kein Servo dran) |
| Coxa-Servo brummt am Anschlag | pulse_min/max zu nah am mech. Anschlag | PSU AUS, YAML pulse_min auf 1300 erhöhen (+20 µs Marge), rebuild, retest |
| Coxa-Bein dreht in falsche Richtung | direction = +1 stimmt nicht für URDF-Konvention | C-T4.5 ausführen (YAML direction: -1, rebuild) |
| RViz-Bein bewegt sich nicht | `/joint_states` kommt nicht an | `ros2 topic echo /joint_states` checken; joint_state_broadcaster spawned? |
| RViz-Modell zeigt nichts | RobotModel-Plugin nicht geladen oder Description-Topic falsch | RobotModel hinzufügen, Description Topic = `/robot_description` |
| PSU springt sofort in CC bei Bringup | Stall oder Servo-Defekt | PSU AUS, Verkabelung prüfen, pulse_zero vs. mech. Mitte prüfen (Stage-B-Werte sollten sicher sein) |
| Servo dreht visuell weiter als JTC-Goal | JTC-Goal-Tracking-Failure oder direction stimmt nicht | Log `ros2 topic echo /joint_states` mit echtem Goal vergleichen |

---

## Done-Kriterium Stage C (User-Smoke-Anteil)

User bestätigt:
- [ ] C-T3 Plugin-Bringup grün
- [ ] C-T4 direction-Bestimmung (mit oder ohne C-T4.5-Flip) abgeschlossen
- [ ] C-T5 RViz-Sync verifiziert
- [ ] C-T6 Endlagen-Test ±1.0 rad alle 6 Goals erreicht
- [ ] C-T7 Shutdown + Abklemm-Sequenz sauber

Claude bestätigt (nach User-Smoke):
- [ ] C-T1 colcon build grün (regression-frei, relevant wenn direction-Flip)
- [ ] C-T2 colcon test grün 208/0/20 + 18/0/0
- [ ] C-T8 YAML-Inspektion: direction-Wert reflektiert C-T4-Ergebnis
- [ ] Self-Review-Tabelle in `phase_10_progress.md`
- [ ] Eventuelle Post-Review-Fixes
