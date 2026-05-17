# Phase 10 — Stufe E — Test-Anleitung (User-Smoke)

**Was geprüft wird:** Stack-Pipeline gegen Tibia-Servo isoliert
(Pin 17, Coxa+Femur abgeklemmt). Ziel: `direction`-Bit für
`leg_6_tibia_joint` bestimmen, Endlagen ±1.0 rad fahren.

> ⚡ **Einfachster der drei direction-Test-Stages.** Tibia passive Pose ≈
> pulse_zero, kein Schwerkraft-Drama. PSU 7.0 V / **CC 4 A**.

**Plan:** [`phase_10_stage_e_plan.md`](phase_10_stage_e_plan.md)
**Sicherheits-Setup:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md)

**Was NICHT in Stage E ausgeführt wird:**
- Coxa + Femur bleiben abgeklemmt (Stage F integriert alle 3)
- Kein IK-Aufruf (Stage F)
- Kein Strom-Logging-CSV (Stage F)

---

## Bench-Setup (VOR allen Tests!)

1. **Bench-PSU OUTPUT AUS** (von Stage-D-Shutdown)
2. **CC-Limit umstellen 7 A → 4 A** (1 Femur/Tibia-Servo, Miuzei MS61)
3. **Setpoint:** weiter **7.0 V**
4. **Servo2040 USB** am Desktop sichtbar:
   ```bash
   ls -l /dev/ttyACM*
   ```
5. **Tibia-Servo (Pin 17) anstecken** — Polaritäts-Check
6. **Coxa (Pin 15) + Femur (Pin 16) bleiben elektrisch abgeklemmt**
7. **leg_5:** ruhige Default-Pose
8. **leg_6-Mechanik:** Bein hängt passiv nach Schwerkraft — Coxa+Femur
   stromlos → Bein hängt mit Femur senkrecht unten, Tibia in Verlängerung
9. **PSU OUTPUT AN** → Strom-Anzeige:
   - **< 200 mA idle erwartet** (1 Servo im Idle)
   - > 500 mA = Verdacht auf Kurzschluss → sofort AUS

---

## E-T3 — Plugin-Bringup (~2 min)

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

**Erwartete Logs:**
- `on_init`, `on_configure`, `on_activate complete`
- 6 leg-controller spawned

**Erwartung am echten Bein:**
- Coxa + Femur: stromlos, Bein hängt mit Femur senkrecht nach unten
- **Tibia:** kleine Korrektur zum pulse_zero=1539 → minimaler Sprung
  (passive Tibia ≈ gestreckt ≈ Joint-Mitte)

**Nicht erlaubte Errors (= PSU AUS, Stage E STOP):**
- `UNDERVOLTAGE_TRIPPED` / `WATCHDOG_TRIPPED` / `ANY_SERVO_OVERCURRENT`

**User-Bestätigung E-T3:**
- [ ] Plugin-Bringup ohne Errors
- [ ] Tibia hält Joint-Mitte stabil

---

## E-T4 — Tibia direction-Test (~5 min)

### Schritt 1: RViz starten (Terminal 2)

```bash
rviz2  # Add RobotModel + TF, Fixed Frame base_link
```

### Schritt 2: Tibia isoliert auf +0.1 rad

```bash
# Terminal 3
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.0, 0.0, -1.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

### Schritt 3: Vergleich RViz ↔ echtes Bein

| Beobachtung | direction-Wert | Aktion |
|---|---|---|
| RViz und echtes Bein synchron (Tibia knickt in dieselbe Richtung) | `+1` korrekt | E-T4 ✅ |
| RViz und echtes Bein gegenläufig | `-1` nötig | siehe E-T4.5 |

**Hinweis:** wenn 0.1 rad zu klein zum Beurteilen ist, größer testen
(0.3 oder 0.5 rad) — Tibia hat keinen Schwerkraft-Hebel, also Risiko niedrig.

**User-Bestätigung E-T4:**
- [ ] Tibia hat sich bewegt
- [ ] Richtung dokumentiert: **synchron** / **gegenläufig**

---

## E-T4.5 — Optional: Tibia direction-Flip auf -1 (~10 min)

**Nur wenn E-T4 gegenläufig.**

```bash
# Terminal 1: Ctrl-C → real.launch.py beenden
# Bench-PSU OUTPUT AUS
```

YAML edit Pin 17:

```yaml
17:
  joint: leg_6_tibia_joint
  pulse_min:  840
  pulse_zero: 1539
  pulse_max:  2172
  direction:  -1    # NEU: Stage E direction flip
```

Rebuild + Relaunch:

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
# Bench-PSU OUTPUT AN
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

E-T4 retest → jetzt synchron.

---

## E-T5 — RViz-Sync-Check (~2 min)

Bereits in E-T4 mitabgefragt.

**User-Bestätigung E-T5:**
- [ ] RViz und echtes Bein synchron nach E-T4

---

## E-T6 — Tibia Endlagen-Test (~10 min)

Goals (Reihenfolge wie Stage C, kein Schwerkraft-Hebel):

| # | positions (coxa, femur, tibia) | Beobachtung |
|---|---|---|
| 1 | `[0.0, 0.0, +0.5]` | Tibia ~25° |
| 2 | `[0.0, 0.0, +1.0]` | Tibia ~57° |
| 3 | `[0.0, 0.0, 0.0]` | zurück zur Mitte |
| 4 | `[0.0, 0.0, -0.5]` | andere Richtung |
| 5 | `[0.0, 0.0, -1.0]` | andere Endlage |
| 6 | `[0.0, 0.0, 0.0]` | sauberer Endstand |

**Bei jedem Goal:**
- Strom < 2 A (Tibia hat keinen Bein-Last)
- Kein Brumm
- RViz synchron

**Bei Stall:**
- PSU AUS, pulse_min/max +30 µs enger ziehen (analog Stages C/D)

**User-Bestätigung E-T6:**
- [ ] Alle 6 Goals erreicht (oder verkürzt 4: ±0.5, ±1.0)
- [ ] Kein Stall-Brumm
- [ ] PSU-Strom < 2 A

---

## E-T7 — Shutdown + Abklemm (~3 min)

```bash
# Terminal 1: Ctrl-C → 18× DISABLE_SERVO
```

Dann:
1. **Bench-PSU OUTPUT AUS**
2. **Tibia-Servo (Pin 17) abziehen**
3. PSU bleibt 7.0 V — Stage F ändert CC auf **8 A** (3-Servo-Bein)

**User-Bestätigung E-T7:**
- [ ] real.launch.py sauber heruntergefahren
- [ ] PSU OUTPUT AUS
- [ ] Tibia abgeklemmt

---

## Fehlerdiagnose-Tabelle

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| Tibia dreht falsch herum | direction=+1 nicht passend | E-T4.5 (YAML direction: -1, rebuild) |
| Tibia bewegt sich nicht trotz Goal | Pin 17 Verkabelung oder Servo-Defekt | PSU AUS, Polarität prüfen, Stecker neu stecken |
| `ANY_SERVO_OVERCURRENT` für Pin 17 | Tibia-Stall (selten ohne Bein-Last) | PSU AUS, pulse_min/max-Werte prüfen |
| `ANY_SERVO_OVERCURRENT` für Pin 15/16 (leer) | false-positive aus Firmware ohne Servo am Pin | aus Stolperfallen-Liste: tolerieren, wenn Pin 17 ok |
| Stall bei -1.0 rad | pulse_min=840 zu nah am mech. Anschlag | YAML pulse_min auf 870, rebuild, retest |
| Stall bei +1.0 rad | pulse_max=2172 zu nah am mech. Anschlag | YAML pulse_max auf 2140, rebuild, retest |

---

## Done-Kriterium Stage E

User bestätigt:
- [ ] E-T3 Plugin-Bringup grün
- [ ] E-T4 Tibia direction (mit oder ohne Flip)
- [ ] E-T5 RViz-Sync OK
- [ ] E-T6 Endlagen-Test ohne Stall
- [ ] E-T7 Shutdown + Abklemm

Claude bestätigt:
- [ ] E-T1 colcon build grün
- [ ] E-T2 colcon test 208/0/20 + 18/0/0
- [ ] E-T7 YAML-Inspektion (Tibia direction sichtbar)
- [ ] Self-Review in `phase_10_progress.md`
