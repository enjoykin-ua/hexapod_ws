# Phase 10 — Stufe D — Test-Anleitung (User-Smoke)

**Was geprüft wird:** Stack-Pipeline gegen 2 koordinierte Hexapod-Servos
(Coxa Pin 15 + Femur Pin 16). Ziel: `direction`-Bit für
`leg_6_femur_joint` bestimmen, 2-Joint-Coordination verifizieren,
Femur-Endlagen ±1.0 rad sauber fahren.

> 🚨 **Sicherheits-Schwerpunkt:** Femur-Initial-Pulse-Schlag ist das
> **maximale Stall-Risiko der ganzen Phase 10**. User-Hand muss das
> Bein **horizontal halten BEVOR** der Launch startet — sonst springt
> Femur 90° gegen Schwerkraft.

**Plan:** [`phase_10_stage_d_plan.md`](phase_10_stage_d_plan.md)
**Sicherheits-Setup:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md)

**Was NICHT in Stage D ausgeführt wird:**
- Tibia bleibt abgeklemmt (Stage E)
- Kein IK-Aufruf (Stage F)
- Kein Strom-Logging-CSV (Stage F)

---

## Bench-Setup (VOR allen Tests!)

> ⚡ **Sicherheits-Recap:** PSU OUTPUT bleibt AUS während Stecker-Arbeit.

1. **Bench-PSU OUTPUT AUS** (von Stage-C-Shutdown noch aus → bestätigen)
2. **CC-Limit auf 7 A umstellen** (war 3 A in Stage C — Mutter-Plan §B Tabelle)
3. **Setpoint:** weiter **7.0 V**
4. **Servo2040 USB** am Desktop, sichtbar:
   ```bash
   ls -l /dev/ttyACM*
   ```
5. **Coxa-Servo (Pin 15) wieder anstecken** — Polaritäts-Check: braun=GND, rot=V+, gelb/orange/weiß=Signal
6. **Femur-Servo (Pin 16) zusätzlich anstecken** — Polaritäts-Check identisch
7. **Tibia-Servo (Pin 17) bleibt abgeklemmt** (Header-Loch leer)
8. **leg_5:** ruhige Default-Pose
9. **PSU-OUTPUT AN** → Strom-Anzeige:
   - **< 300 mA idle erwartet** (2 Servos im Idle vor ENABLE)
   - > 800 mA = Verdacht auf Kurzschluss → sofort AUS, Stecker prüfen

---

## D-T3 — Plugin-Bringup mit Femur-User-Hand-Mitigation (~3 min)

> 🚨 **Kritischer Schritt der Phase 10.** Bitte ganz genau in der
> Reihenfolge unten!

### Schritt 1: User-Hand am Bein VOR Launch

```
1. leg_6 mit einer Hand vom passiven hängenden Zustand (-90° Femur) HOCH
   in eine horizontale Position bringen
2. Position: Femur horizontal, Bein zeigt radial nach außen vom Body
   (= Coxa in Mitte = Bein ~90° vom Body-Längsachse)
3. Hand bleibt am Bein, hält es aktiv gegen Schwerkraft
4. ERST jetzt → Schritt 2 (Launch)
```

### Schritt 2: Launch starten (mit Hand weiter am Bein)

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

### Schritt 3: Log-Sequenz beobachten

Erwartete Logs identisch zu Stage C:
- `on_init`, `on_configure`, `on_activate complete`
- joint_state_broadcaster + 6 leg-controller spawned

**Nicht erlaubte Errors (= sofort PSU AUS, Stage D STOP):**
- `UNDERVOLTAGE_TRIPPED` — PSU < 5.5 V
- `WATCHDOG_TRIPPED`
- `ANY_SERVO_OVERCURRENT` — Stall (besonders Femur!)

### Schritt 4: Erwartung am echten Bein

Nach `on_activate complete`:
- **Coxa-Servo:** zieht Bein in Coxa-Mitte (User-Hand schon dort → minimaler Sprung)
- **Femur-Servo:** zieht Bein in Femur-Mitte (= horizontal, User-Hand schon dort → minimaler Sprung)
- **Tibia:** stromlos, hängt mech.

### Schritt 5: Hand vom Bein wegnehmen

Wenn beide Servos sauber halten (Bein bleibt horizontal, kein Brumm):
**langsam** die Hand wegnehmen. Servos sollten das Bein aktiv halten.

**Bei Stall/Brumm während Hand-Wegnehmen:** Hand sofort zurück, PSU AUS,
Bringup-Strategie überdenken.

**User-Bestätigung D-T3:**
- [ ] Plugin-Bringup ohne `UNDERVOLTAGE`/`WATCHDOG`/`OVERCURRENT`-Errors
- [ ] Coxa + Femur halten Bein horizontal nach Bringup
- [ ] Hand erfolgreich wegnehmen, Bein bleibt stabil

---

## D-T4 — Femur direction-Test (~5 min)

### Schritt 1: RViz starten (Terminal 2, parallel)

```bash
# Terminal 2
source ~/hexapod_ws/install/setup.bash
rviz2
```

Im RViz: Add → RobotModel (Description Topic `/robot_description`),
Add → TF (Fixed Frame `base_link`).

### Schritt 2: Femur-isolierter Test (Coxa bleibt 0)

```bash
# Terminal 3 — nur Femur auf +0.1 rad
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.0, 1.0, 0.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

### Schritt 3: Bewegung beobachten + Vergleich RViz ↔ echtes Bein

| Beobachtung | direction-Wert | Aktion |
|---|---|---|
| RViz-Bein und echtes Bein bewegen **synchron** (Femur in dieselbe Richtung) | `+1` korrekt | D-T4 ✅ |
| RViz-Bein hebt sich, echtes Bein senkt sich (oder umgekehrt) | `-1` nötig | siehe D-T4.5 |

**Hinweis:** wenn die Bewegung „minimal" wirkt wie in Stage C, ist das
normal (5.7° = 0.1 rad ist schwer mit Auge zu beziffern). Wichtig ist nur
die **Richtung** (synchron mit RViz oder gegenläufig). Falls unklar:
größeren Wert testen (z.B. 0.3 rad).

**User-Bestätigung D-T4:**
- [ ] Femur hat sich bewegt
- [ ] Richtung dokumentiert: **synchron mit RViz** / **gegenläufig**

---

## D-T4.5 — Optional: Femur direction-Flip auf -1 (~10 min)

**Nur wenn D-T4 gegenläufig.**

```bash
# Terminal 1: Ctrl-C (real.launch.py beenden)
# Plugin sendet 18× DISABLE_SERVO → Bein hängt wieder passiv -90° Femur
# Bench-PSU OUTPUT AUS (für Sicherheit während YAML-Edit)
```

Claude (oder User) editiert das YAML:

```yaml
# src/hexapod_hardware/config/servo_mapping.yaml, Pin 16:
16:
  joint: leg_6_femur_joint
  pulse_min:  840
  pulse_zero: 1533
  pulse_max:  2170
  direction:  -1    # NEU: Stage D direction flip
```

Rebuild + Relaunch (User-Hand wieder am Bein für Bringup!):

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
# === WICHTIG === User hebt Bein horizontal an + hält es
# === DANN === PSU AN
# === DANN === launch
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Dann D-T4 wiederholen → jetzt sollte echtes Bein und RViz synchron sein.

---

## D-T5 — RViz-Sync-Check (~2 min)

Bereits in D-T4 mitabgefragt. Sync = beide Joints (Coxa und Femur) in
RViz und echtem Bein in identischer Pose.

**User-Bestätigung D-T5:**
- [ ] RViz-Modell und echtes Bein synchron nach D-T4

---

## D-T6 — 2-Joint-Coordination-Test (~5 min)

```bash
# Coxa und Femur beide auf +0.1 rad, gleichzeitig in 3 s
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.1, 0.1, 0.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

**Beobachten:**
- Beide Joints bewegen sich **gleichzeitig** über 3 s (keiner fängt
  früher an oder hört früher auf)
- RViz und echtes Bein synchron in identischer End-Pose

**User-Bestätigung D-T6:**
- [ ] Coxa und Femur bewegen sich **parallel** (kein Phasen-Versatz)
- [ ] End-Pose RViz = End-Pose echtes Bein

---

## D-T7 — Femur Endlagen-Test (~10 min)

> 🚨 **Strategie:** erst nach unten (mit Schwerkraft, sicher), dann
> nach oben (gegen Schwerkraft, höchstes Stall-Risiko). User-Hand
> bereit Bein zu fangen falls Stall.

Goals in dieser Reihenfolge:

| # | positions (coxa, femur, tibia) | Beobachtung | Strom-Erwartung |
|---|---|---|---|
| 1 | `[0.0, -0.5, 0.0]` | Femur 25° nach unten | < 2 A |
| 2 | `[0.0, -1.0, 0.0]` | Femur 57° nach unten | < 2 A |
| 3 | `[0.0, 0.0, 0.0]` | zurück zu horizontal (gegen Schwerkraft) | < 3 A (transient höher beim Anheben) |
| 4 | `[0.0, 0.5, 0.0]` | Femur 25° nach oben (gegen Last) | < 3 A |
| 5 | `[0.0, 1.0, 0.0]` | Femur 57° nach oben — höchste Last | < 4 A (Stall ~3.5 A bei Miuzei MS61) |
| 6 | `[0.0, 0.0, 0.0]` | zurück zu horizontal, sauberer Endstand | < 3 A |

**Bei jedem Goal:**
- Strom-Display der PSU beobachten
- Femur-Bewegung glatt, kein Brumm
- RViz und echtes Bein synchron

**Bei Stall oder Strom-Peak > 4 A:**
- **PSU sofort AUS**
- User-Hand fängt Bein
- D-Q5 Plan-B: pulse_min oder pulse_max im YAML enger ziehen (z.B.
  pulse_min von 840 auf 870, pulse_max von 2170 auf 2140), rebuild,
  retest

**User-Bestätigung D-T7:**
- [ ] Alle 6 Goals erreicht
- [ ] Kein Stall-Brumm
- [ ] PSU-Strom blieb < 4 A in allen Phasen
- [ ] RViz und echtes Bein synchron in allen Posen

---

## D-T8 — Shutdown + Abklemm-Sequenz (~3 min)

```bash
# Terminal 1: Ctrl-C → real.launch.py shutdown (18× DISABLE_SERVO)
```

Dann:
1. **Bench-PSU OUTPUT AUS**
2. **Coxa-Servo (Pin 15) abziehen**
3. **Femur-Servo (Pin 16) abziehen**
4. PSU bleibt eingestellt (7.0 V) — Stage E ändert CC auf 4 A

**User-Bestätigung D-T8:**
- [ ] real.launch.py sauber heruntergefahren
- [ ] PSU OUTPUT AUS
- [ ] Coxa + Femur abgeklemmt

---

## Fehlerdiagnose-Tabelle

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| Stall-Brumm im Femur sofort beim Bringup | User-Hand nicht am Bein → Femur springt 90° gegen Schwerkraft | PSU AUS, Bringup-Reihenfolge wiederholen mit Hand-First |
| `ANY_SERVO_OVERCURRENT` Pin 16 beim Bringup | Femur-Stall ODER pulse_zero=1533 nicht erreichbar weil Schwerkraft + niedrige PSU | PSU-Spannung auf 7.4 V testweise erhöhen, oder User-Hand das Bein bei pulse_zero stützen |
| Femur dreht falsch herum | direction=+1 nicht passend für leg_6 | D-T4.5 ausführen (YAML direction: -1, rebuild) |
| Coxa und Femur bewegen nicht synchron im D-T6 | JTC-Coordination-Issue oder kaputter Plugin-Pfad | `ros2 topic echo /joint_states` parallel beobachten, ist `time_from_start` für beide Joints identisch? |
| PSU springt in CC-Limit (= 7 A erreicht) | beide Servos im Stall, oder Verkabelungs-Kurzschluss | PSU AUS, Stecker prüfen, Servo einzeln testen |
| Femur-Endlagen-Test +1.0 rad → Stall | pulse_max=2170 µs zu nah am mech. Anschlag mit Last | D-Q5: pulse_max im YAML auf z.B. 2140 reduzieren, rebuild, retest |
| Bein fällt nach Bringup-Hand-Wegnahme zurück nach unten | Femur-Servo schafft Bein-Last nicht (zu schwacher Servo / falsche Spannung / Stall) | PSU AUS, Hand wieder ans Bein, Diagnose: Strom-Wert während on_activate prüfen |

---

## Done-Kriterium Stage D (User-Smoke-Anteil)

User bestätigt:
- [ ] D-T3 Plugin-Bringup mit Hand-Mitigation grün
- [ ] D-T4 Femur direction-Bestimmung abgeschlossen
- [ ] D-T5 RViz-Sync verifiziert
- [ ] D-T6 2-Joint-Coordination synchron
- [ ] D-T7 Femur Endlagen ±1.0 rad alle Goals erreicht ohne Stall
- [ ] D-T8 Shutdown + Abklemm-Sequenz sauber

Claude bestätigt (nach User-Smoke):
- [ ] D-T1 colcon build grün
- [ ] D-T2 colcon test grün 208/0/20 + 18/0/0
- [ ] D-T8 YAML-Inspektion (Femur direction sichtbar)
- [ ] Self-Review-Tabelle in `phase_10_progress.md`
- [ ] Eventuelle Post-Review-Fixes
