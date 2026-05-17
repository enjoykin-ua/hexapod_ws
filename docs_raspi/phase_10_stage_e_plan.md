# Phase 10 — Stufe E — Plan

> **Status:** Plan, in Vorbereitung der HW-Arbeit.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe E — Stack-Validation `leg_6_tibia` (1 Servo isoliert).
>
> **Vorbedingung:** Stufe D komplett (Femur direction=-1 final committed,
> 2-Joint-Coordination verifiziert). Hexapod aufgebockt, Bench-PSU 7.0 V,
> **OUTPUT AUS**, alle leg_6-Servos elektrisch abgeklemmt nach Stage-D-Shutdown.

---

## Ziel

**Stack-Validation des dritten und letzten Servos** dieser Phase.
Konkret:

1. `leg_6_tibia-Servo` (Pin 17, Miuzei MS61) **isoliert** anstecken
   — Coxa Pin 15 + Femur Pin 16 **abgeklemmt**
2. Bench-PSU 7.0 V, **CC-Limit 4 A** (1 Femur/Tibia-Servo — Mutter-Plan §B)
3. Plugin via `real.launch.py loopback_mode:=false` aktivieren
4. **Tibia direction-Test** mit isolierter Trajectory (Tibia +0.1 rad,
   Coxa+Femur auf 0)
5. Bei Bedarf direction-Flip + rebuild
6. **Tibia Endlagen-Test** ±1.0 rad

Nach Stage E ist `direction` für alle 3 leg_6-Joints final gesetzt und
einzeln über Stack-Beobachtung verifiziert. **Stage F integriert die
3 Joints koordiniert mit IK.**

**Was Stage E NICHT macht:**

- Kein IK-Aufruf (Stage F)
- Kein 3-Servo-koordinierter Test (Stage F)
- Kein Strom-Logging-CSV (Stage F)
- Kein Vel/Accel-Limit-Messung (Stage G)

---

## Warum Tibia isoliert (vs. „alle 3 zusammen")?

Aus Mutter-Plan §Stage-E-Vorbedingung: **Tibia isoliert ist die
diagnostisch sauberste Variante**, weil:

1. **Kein Bein-Gewicht-Hebel:** Coxa+Femur stromlos → hängen passiv,
   der Tibia-Servo bewegt **nur sich selbst + die untere Tibia-Hälfte**,
   nicht das ganze Bein gegen Gravity wie bei Femur in Stage D.
2. **Passive Tibia-Pose nahe pulse_zero:** Bein hängt passiv mit Femur
   senkrecht, Tibia in Verlängerung → Tibia-Joint ist „gestreckt" =
   ~0 rad ≈ pulse_zero=1539. **Kein Initial-Pulse-Schlag**.
3. **Direction-Diagnose unverwechselbar:** wenn nur Tibia bewegt, ist
   die Beobachtung „in welche Richtung dreht Tibia" eindeutig.

**Stage F bringt die Voll-Integration:** alle 3 Servos zusammen, IK
schickt koordinierte Goals.

---

## Strategie / Architektur-Erinnerungen

| Punkt | Wert | Quelle |
|---|---|---|
| Bench-PSU Spannung | 7.0 V | Mutter-Plan §B |
| Bench-PSU CC-Limit | **4 A** (1 Femur/Tibia-Servo, Miuzei MS61) | Mutter-Plan §B |
| Verkabelungs-Sequenz | PSU-AUS → Tibia an Pin 17 → Sichtprüfung → PSU-AN | Mutter-Plan §D |
| Initial-Pulse-Mitigation | **Minimal** — Tibia passive Pose ≈ pulse_zero, kaum Sprung beim ENABLE | siehe oben |
| direction-Flip | Build-Edit-Build pro Flip | Mutter-Plan §I |
| RViz-Sync-Check | RViz separat starten (`rviz2`) | Stage-C-Plan-Korrektur |
| Kill-Switch | Bench-PSU OUTPUT-Taste | [`safety_setup.md`](phase_10_safety_setup.md) §5 |
| Coxa direction | -1 (Stage C, unverändert) | committed |
| Femur direction | -1 (Stage D, unverändert) | committed |

---

## User-Antworten (User-Freigabe 2026-05-17)

Alle 4 Punkte mit **Empfehlung A** entschieden:

| Frage | Antwort | Konsequenz |
|---|---|---|
| **E-Q1** Tibia direction-Test-Form | **A** — Tibia isoliert (Goal `[0.0, 0.0, 0.1]`) | Saubere isolierte Diagnose |
| **E-Q2** Endlagen-Test Reihenfolge | **A** — Stage-C-Pattern (6 Goals +0.5/+1.0/0/-0.5/-1.0/0) | Schwerkraft-neutral weil Tibia isoliert |
| **E-Q3** User-Hand-Position vor Launch | **A** — locker neben Bench, nicht aktiv halten | Tibia passive ≈ pulse_zero, kein Initial-Pulse-Drama |
| **E-Q4** Bei Tibia-Stall in Endlagen | **A** — pulse_min/max +30 µs enger, rebuild, retest | Hardware-Fix, konsistent zu Stages C/D |

---

## Logik-Skizze

### E.0 — Bench-Setup-Check (~5 min)

1. **Bench-PSU OUTPUT AUS** (von Stage-D-Shutdown)
2. **CC-Limit umstellen von 7 A auf 4 A** (1 Servo)
3. **Setpoint:** 7.0 V (unverändert)
4. **Tibia-Servo (Pin 17) anstecken** — Polaritäts-Sichtprüfung
5. **Coxa (Pin 15) + Femur (Pin 16) bleiben abgeklemmt** (Header-Loch leer)
6. **leg_5:** ruhige Default-Pose
7. **User-Position:** locker neben Bench, Hand kann anfassen falls
   Bein durch Tibia-Bewegung pendelt. PSU-Aus-Knopf griffbereit.
8. **PSU OUTPUT AN** → Strom-Anzeige < 200 mA idle erwartet
   - > 500 mA = Verdacht auf Kurzschluss, sofort AUS

### E.1 — Plugin-Bringup (~2 min)

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

**Erwartete Log-Sequenz** (wie Stage C/D):
- `on_init`, `on_configure`, `on_activate complete`
- joint_state_broadcaster + 6 leg-controller spawned

**Erwartung am echten Bein:**
- Coxa: stromlos, Bein hängt passiv radial außen
- Femur: stromlos, hängt -90° nach unten
- **Tibia:** kleine Korrektur von passiv ~0 rad zu pulse_zero=1539 µs
  → minimaler Sprung, kein Stall-Risiko

**Nicht erlaubte Errors:**
- `UNDERVOLTAGE_TRIPPED` / `WATCHDOG_TRIPPED` / `ANY_SERVO_OVERCURRENT`

### E.2 — Tibia direction-Test (~5 min)

```bash
# Terminal 2: RViz starten
rviz2  # Add RobotModel + TF

# Terminal 3: Tibia isoliert auf +0.1 rad
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.0, 0.0, 0.1], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

**Beobachten:**
- Tibia dreht ~5.7° (0.1 rad)
- Tibia-Joint dreht um Y-Achse: positive rad → „Knie wie?" — visuell
  beurteilen (Knie zu/auf, je nach Konvention)
- **Vergleich RViz vs. echtes Bein:**

| Beobachtung | direction-Wert | Aktion |
|---|---|---|
| RViz und echtes Bein synchron | `+1` korrekt | E-T4 ✅ |
| RViz vs. echtes Bein gegenläufig | `-1` nötig | siehe E.3 |

**Cross-Phase-Hypothese:** wenn Coxa und Femur bei leg_6 beide `-1` sind,
könnte Tibia auch `-1` sein (Left-Side-Konsistenz aus Stage-D-Notiz).
Aber Beobachtung ist die Wahrheit, nicht die Hypothese.

### E.3 — Optional: Tibia direction-Flip auf -1 (~10 min)

Analog Stage C/D — YAML edit Pin 17, rebuild, relaunch.

### E.4 — Tibia Endlagen-Test (±1.0 rad) (~10 min)

Stage-C-Pattern (Tibia hat keinen Schwerkraft-Hebel, also Reihenfolge
egal). Goals:

| # | positions (coxa, femur, tibia) | Beobachtung |
|---|---|---|
| 1 | `[0.0, 0.0, +0.5]` | Tibia 25° in eine Richtung |
| 2 | `[0.0, 0.0, +1.0]` | Tibia 57° — innerhalb URDF-Limit ±1.50 |
| 3 | `[0.0, 0.0, 0.0]` | zurück zu Mitte |
| 4 | `[0.0, 0.0, -0.5]` | Tibia in andere Richtung |
| 5 | `[0.0, 0.0, -1.0]` | Tibia 57° andere Richtung |
| 6 | `[0.0, 0.0, 0.0]` | sauberer Endstand |

**Beobachten:**
- Strom < 2 A in allen Posen (kein Bein-Gewicht-Hebel = niedrige Last)
- Keine Stalls/Brumm
- RViz und echtes Bein synchron

### E.5 — Shutdown + Abklemm-Sequenz (~3 min)

```bash
# Terminal 1: Ctrl-C → 18× DISABLE_SERVO
```

Dann:
1. Bench-PSU **OUTPUT AUS**
2. **Tibia-Servo (Pin 17) abziehen**
3. PSU bleibt eingestellt (7.0 V), CC ändert für Stage F von 4 A → **8 A**
   (3-Servo-Bein voll)

### E.6 — Build/Test/Self-Review

- Wenn Tibia direction-Flip: rebuild
- `colcon test`: 208/0/20 + 18/0/0 regression-frei
- Self-Review nach CLAUDE.md §4

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| E-T1 | `colcon build` | grün, regression-frei | Claude |
| E-T2 | `colcon test` | 208/0/20 + 18/0/0 | Claude |
| E-T3 (User) | Plugin-Bringup ohne Errors | manuelle Bestätigung | User |
| E-T4 (User) | Tibia direction-Test (isoliert): Richtung dokumentiert | manuelle Bestätigung | User |
| E-T5 (User) | RViz-Bein und echtes Bein synchron | manuelle Bestätigung | User |
| E-T6 (User) | Tibia Endlagen-Test ±1.0 rad alle Goals, kein Stall | manuelle Bestätigung | User |
| E-T7 | YAML-Inspektion: Tibia direction-Wert reflektiert E.2/E.3-Ergebnis | sichtbar im Diff (falls Flip) | Claude + User |

### Was bewusst NICHT in Stage E getestet wird

- **3-Servo-koordinierte Trajectory** (Stage F)
- **IK-Aufruf** (Stage F)
- **Strom-Logging-CSV** (Stage F)
- **Vel/Accel-Limits** (Stage G)

---

## Progress-Checkliste

- [ ] E.1 phase_10_stage_e_plan.md (Plan-Doku) finalisiert + User-Freigabe
- [ ] E.2 phase_10_stage_e_test_commands.md angelegt
- [ ] E.3 E.0 Bench-Setup-Check (PSU 7.0 V / **4 A**, nur Tibia an Pin 17)
- [ ] E.4 E.1 Plugin-Bringup grün, 18× ENABLE_SERVO im Log, kein Trip
- [ ] E.5 E.2 Tibia direction-Test (isoliert) gefahren, Richtung dokumentiert
- [ ] E.6 E.3 (optional) Tibia direction-Flip auf -1 mit YAML-Edit + colcon build + relaunch
- [ ] E.7 E.4 Tibia Endlagen-Test ±1.0 rad alle 6 Goals erreicht, kein Stall
- [ ] E.8 E.5 PSU AUS, Tibia abgeklemmt
- [ ] E.9 E.6 colcon build grün (regression-frei)
- [ ] E.10 E.6 colcon test grün 208/0/20 + 18/0/0
- [ ] E.11 E-T3..E-T6 User-Bestätigung
- [ ] E.12 E-T7 YAML-Inspektion (Tibia direction sichtbar)
- [ ] E.13 Kritischer Self-Review-Tabelle
- [ ] E.14 Eventuelle Post-Review-Fixes + Stage-E-Notizen

**Done-Kriterium E erreicht:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke E-T3..E-T6 bestätigt.

---

## Erwartete Stage-E-Dauer

- E.1 Plan-Doku: ~20 min Claude (erledigt mit dieser Datei)
- E.2 test_commands.md: ~15 min Claude
- E.3 Bench-Setup-Check: ~5 min User
- E.4 Plugin-Bringup: ~2 min User
- E.5 direction-Test: ~5 min User
- E.6 direction-Flip (falls nötig): ~10 min
- E.7 Endlagen-Test: ~10 min User
- E.8 Abklemm: ~3 min User
- E.9–E.10 Build + Test: ~5 min Claude
- E.11–E.12 User-Bestätigung: ~5 min Sync
- E.13 Self-Review: ~15 min Claude

**Schätzung:** ~45 min Claude + ~30 min User + ~20 min Sync = **~1.5 h Gesamt**
(kürzer als Stage C/D weil kein Schwerkraft-Drama, simplerer Setup).
