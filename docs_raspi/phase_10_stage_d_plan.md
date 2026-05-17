# Phase 10 — Stufe D — Plan

> **Status:** Plan, in Vorbereitung der HW-Arbeit.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe D — Stack-Validation `leg_6_coxa + leg_6_femur` (2 Servos parallel).
>
> **Vorbedingung:** Stufe C komplett (Coxa direction=-1 final committed,
> Endlagen ±1.0 rad bestätigt). Hexapod weiter aufgebockt, Bench-PSU
> auf 7.0 V eingestellt, **OUTPUT AUS**, alle leg_6-Servos elektrisch
> abgeklemmt nach Stage-C-Shutdown.

---

## Ziel

**Erster Test mit 2 koordinierten Servos** unter JTC-Trajectory-Steuerung.
Konkret:

1. `leg_6_coxa-Servo` (Pin 15, **direction bereits -1**) wieder anstecken
2. `leg_6_femur-Servo` (Pin 16, Miuzei MS61) zusätzlich anstecken
3. Bench-PSU 7.0 V, **CC-Limit 7 A** (3 A Coxa + 4 A Femur — Mutter-Plan §B)
4. Plugin via `real.launch.py loopback_mode:=false` aktivieren —
   **kritisch: User hält Bein horizontal gegen Schwerkraft** während des
   ersten ENABLE, weil Femur passiv -90° hängt
5. **Femur direction-Test** mit kleiner Trajectory analog Stage C
6. Bei Bedarf direction-Flip + rebuild (analog Stage C C-T4.5)
7. **2-Joint-Coordination-Test:** Coxa und Femur gleichzeitig auf +0.1 rad
   → prüft Goal-Phasen-Sync zwischen den Joints
8. **Femur Endlagen-Test** ±1.0 rad, vorsichtig mit Schwerkraft-Risiko

Nach Stage D ist `direction` für `leg_6_femur_joint` final gesetzt und
2-Servo-Koordination verifiziert. **Coxa-Werte bleiben unverändert**,
direction=-1 aus Stage C.

**Was Stage D NICHT macht:**

- Kein Tibia-Test (Stage E)
- Kein IK-Aufruf (Stage F)
- Kein Strom-Logging-CSV (Stage F)

---

## Sicherheits-Schwerpunkt: Femur-Initial-Pulse-Schlag

> 🚨 **Maximales Stall-Risiko der ganzen Phase 10** bei Femur-Erst-ENABLE.

**Warum:** Femur passive Pose (stromlos) = Bein hängt am mech. Anschlag
bei ca. **-90° unter horizontal** (Bein vertikal nach unten). Plugin
schickt beim `on_activate` neutralen `pulse_zero = 1533 µs` → das
entspricht **0 rad = Femur horizontal**. Bei direction=+1 (default
vor Stage-D-Test) bewegt das den Servo **schlagartig 90° gegen die
Bein-Schwerkraft** → Servo zieht hohen Strom + möglicher Stall-Brumm
+ PSU-CC-Trip.

**Mitigation:** **User-Hand stützt das Bein horizontal** während des
gesamten `on_activate`-Vorgangs (~1.5 s Boot-Sequenz). Hand bleibt am
Femur-Segment, hebt es passiv auf horizontale Position **vor** Launch-
Start und hält es dort bis Boot-Sequenz durch.

Cross-Phase: Memory `project_phase12_initial_pose_presets.md` ist die
elegantere Lösung (preset-spezifischer Initial-Pulse statt User-Hand) —
Phase-12-Kandidat, nicht Phase-10.

---

## Strategie / Architektur-Erinnerungen

| Punkt | Wert | Quelle |
|---|---|---|
| Bench-PSU Spannung | 7.0 V | Mutter-Plan §B |
| Bench-PSU CC-Limit | **7 A** (2 Servos: 3 A Coxa + 4 A Femur) | Mutter-Plan §B, [`safety_setup.md`](phase_10_safety_setup.md) §2 |
| Verkabelungs-Sequenz | PSU-AUS → beide Stecker rein → Sichtprüfung → PSU-AN | Mutter-Plan §D |
| Initial-Pulse-Mitigation | User-Hand hält **Bein horizontal** vor Launch (kritisch wegen Femur-Schwerkraft) | Mutter-Plan §C, siehe oben |
| direction-Flip | Build-Edit-Build pro Flip (kein Live-Param) | Mutter-Plan §I |
| RViz-Sync-Check | RViz separat starten (`rviz2`) | Stage-C-Plan-Korrektur, beibehalten |
| Kill-Switch | Bench-PSU OUTPUT-Taste | [`safety_setup.md`](phase_10_safety_setup.md) §5 |
| Coxa direction | **-1** (aus Stage C, unverändert) | committed 2026-05-17 |

---

## User-Antworten (User-Freigabe 2026-05-17)

Alle 5 Punkte mit der **Empfehlung A** entschieden:

| Frage | Antwort | Konsequenz |
|---|---|---|
| **D-Q1** Erste direction-Test-Form | **A** — Femur isoliert (+0.1 rad nur Femur, Coxa bleibt 0) | Saubere Diagnose-Trennung; 2-Joint-Coordination erst in D-T6 |
| **D-Q2** Endlagen-Test Reihenfolge | **A** — erst negativ (-0.5, -1.0), dann zurück, dann positiv (+0.5, +1.0) | Mit Schwerkraft-First: niedrigstes Anfangs-Stall-Risiko |
| **D-Q3** 2-Joint-Coordination-Test-Form | **A** — Coxa und Femur beide auf +0.1 rad, 3 s | Goal-Phasen-Sync prüfen mit kleinem Schritt |
| **D-Q4** User-Hand-Position vor Launch | **A** — Bein horizontal nach außen (Coxa-Mitte + Femur-Mitte) | Minimaler Sprung beim ENABLE bei beiden Servos |
| **D-Q5** Bei Femur-Stall in Endlagen | **A** — pulse_min/max im YAML enger ziehen (+30 µs Marge), retest | Hardware-Fix bei zu engen Stage-B-Werten; Notiz im Stage-B-calibration_log §5 |

---

## Logik-Skizze

### D.0 — Bench-Setup-Check (Vorbereitung, ~5 min)

1. **Bench-PSU OUTPUT AUS** (vor Servo-Stecker-Arbeit)
2. **CC-Limit umstellen von 3 A auf 7 A** (PSU-Setting)
3. **Coxa-Servo (Pin 15) wieder anstecken** — Polarität-Sichtprüfung
4. **Femur-Servo (Pin 16) anstecken** — Polarität-Sichtprüfung
5. **Tibia-Servo (Pin 17) bleibt abgeklemmt** (Stage E)
6. **leg_5**: ruhige Default-Pose (wie Stage C)
7. **User-Hand-Position prüfen:** Hand bereit, Bein in **horizontaler
   Pose** zu halten (Femur horizontal, Bein radial außen). PSU-Aus-Knopf
   griffbereit.
8. **PSU OUTPUT AN** → Strom-Anzeige < 300 mA idle erwartet
   (2 Servos im Idle vor ENABLE)
   - > 800 mA = Verdacht auf Kurzschluss, sofort AUS, Stecker prüfen

### D.1 — Plugin-Bringup mit Femur-User-Hand-Mitigation (~3 min)

> 🚨 **Reihenfolge kritisch:** User hält Bein **bevor** der Launch
> startet. Wenn die Launch-Command schon läuft und der User dann die
> Hand wegnimmt, fährt der Femur-Servo gegen die Schwerkraft.

```bash
# Step 1: User hebt leg_6 in horizontale Pose und hält es dort
# Step 2 (mit Hand am Bein): launch
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

**Erwartete Log-Sequenz** (identisch Stage C):
- `on_init` → 18 joints mapped
- `on_configure` → serial port opened
- `on_activate` → 18× ENABLE_SERVO + neutral SET_TARGETS
- joint_state_broadcaster + 6 leg-controller spawned

**Erwartung am echten Bein nach `on_activate`:**
- Coxa: zieht Bein in Coxa-Mitte (User-Hand schon dort → minimaler Sprung)
- Femur: zieht Bein in Femur-Mitte (= horizontal, User-Hand schon dort → minimaler Sprung)
- Tibia: stromlos, hängt mech.

**Nach Bestätigung dass beide Servos sauber sitzen:** User kann Hand vom Bein langsam wegnehmen — Servos halten die Pose aktiv.

**Bei Stall/Brumm:** PSU sofort AUS, Hand wieder ans Bein, Plan-B (Bringup nochmal mit besserer Hand-Position).

### D.2 — Femur direction-Test (~5 min)

> **Strategie:** Femur isoliert testen (Coxa bleibt 0), damit direction-
> Beobachtung sauber. Coxa+Femur-Coordination kommt erst in D.4.

```bash
# Terminal 2: RViz starten (Add RobotModel + TF)
rviz2

# Terminal 3: nur Femur auf +0.1 rad, Coxa und Tibia auf 0
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.0, 0.1, 0.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

**Beobachten:**

- Femur dreht ~5.7° (0.1 rad)
- Bei leg_6 mit URDF-axis Y für Femur und yaw +π/4: positive Femur-rad
  = ? (User beurteilt visuell, vergleicht RViz vs. echtes Bein)
- **Hebt sich das Bein nach OBEN oder senkt es sich nach UNTEN?**
- Vergleich: RViz vs. echtes Bein. Synchron = direction=+1 OK,
  gegenläufig = direction=-1 nötig (analog Stage C)

**RViz-Konvention für Femur:** ich gebe hier *keine* Vorhersage für die
URDF-positive Richtung, weil die Achsen-Konvention für Y-Rotation bei
yaw+π/4 nicht trivial intuitiv ist — User beurteilt rein per **Vergleich
mit RViz-Modell**, das ist die Wahrheit.

### D.3 — Optional: Femur direction-Flip auf -1 (~10 min)

**Wenn D.2 zeigt: echtes Bein dreht gegenläufig zu RViz** — analog
Stage C C-T4.5:

```bash
# Terminal 1: Ctrl-C real.launch.py
# Bench-PSU OUTPUT AUS

# YAML edit Pin 16:
#   16:
#     joint: leg_6_femur_joint
#     pulse_min:  840
#     pulse_zero: 1533
#     pulse_max:  2170
#     direction:  -1     # NEU: Flip

cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
# Bench-PSU OUTPUT AN (User-Hand wieder ans Bein!)
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Dann D.2 retest — jetzt sollte echtes Bein und RViz synchron sein.

### D.4 — 2-Joint-Coordination-Test (~5 min)

> **User-Hand kann jetzt locker neben dem Bein bleiben**, Servos halten
> sich selber. Aber bereit dazwischen zu fangen wenn was abrupt geht.

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
- Beide Joints bewegen sich **synchron** über die 3 s — keiner schneller
  als der andere
- RViz-Bein und echtes Bein in identischer Pose nach Trajectory
- Kein Stall, kein Brumm

**Erfolg = JTC liefert koordinierte Multi-Joint-Trajectories sauber an
das Plugin, Plugin schickt parallel beide Pulse, Servos drehen in
gleichem Zeitfenster.**

### D.5 — Femur Endlagen-Test (-1.0 / -0.5 / +0.5 / +1.0 rad) (~10 min)

> 🚨 **Strategie:** erst negative Richtung (Bein senkt sich, mit
> Schwerkraft, sicher), dann positive (Bein hebt sich, gegen
> Schwerkraft, potenzielles Stall-Risiko).

Goals in dieser Reihenfolge (Format wie D.4):

| # | positions (coxa, femur, tibia) | Begründung |
|---|---|---|
| 1 | `[0.0, -0.5, 0.0]` | Femur 25° nach unten, Schwerkraft hilft |
| 2 | `[0.0, -1.0, 0.0]` | Femur 57° nach unten, Bein hängt stärker. PSU-Strom < 3 A erwartet |
| 3 | `[0.0, 0.0, 0.0]` | zurück zu horizontal (gegen Schwerkraft, aus passiver Pose ~-1 rad → 0) |
| 4 | `[0.0, 0.5, 0.0]` | Femur 25° nach oben — gegen Schwerkraft + Bein-Last |
| 5 | `[0.0, 1.0, 0.0]` | Femur 57° nach oben — höchste Last. PSU-Strom < 4 A erwartet (Miuzei MS61 Stall ~3.5 A) |
| 6 | `[0.0, 0.0, 0.0]` | zurück zu horizontal, sauberer Endstand |

**Bei jedem Goal:**
- Strom-Display der PSU beobachten
- Femur-Bewegung visuell glatt, kein Brumm
- RViz und echtes Bein synchron

**Bei Stall (Brumm + Strom-Peak):**
- PSU sofort AUS
- Plan-B: pulse_min/max für Femur enger ziehen im YAML (siehe D-Q5)

### D.6 — Shutdown + Abklemm-Sequenz (~3 min)

```bash
# Terminal 1: Ctrl-C → real.launch.py shutdown (18× DISABLE_SERVO)
```

Dann:
1. Bench-PSU **OUTPUT AUS**
2. Coxa-Servo (Pin 15) **abziehen**
3. Femur-Servo (Pin 16) **abziehen**
4. Bench-PSU bleibt eingestellt für Stage E (wartet auf Tibia-Test)

### D.7 — Build/Test/Self-Review

- Wenn direction-Flip auf Femur: `colcon build --packages-select hexapod_hardware`
- `colcon test`: 208/0/20 + 18/0/0 (regression-frei)
- Self-Review-Tabelle nach CLAUDE.md §4

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| D-T1 | `colcon build --packages-select hexapod_hardware` | grün, regression-frei (relevant bei Femur-Flip) | Claude |
| D-T2 | `colcon test --packages-select hexapod_hardware hexapod_bringup` | 208/0/20 + 18/0/0 unverändert | Claude |
| D-T3 (User) | Plugin-Bringup mit beiden Servos ohne Errors, ohne Stall | manuelle Bestätigung | User |
| D-T4 (User) | Femur direction-Test (Femur isoliert) → Bewegungsrichtung dokumentiert | manuelle Bestätigung | User |
| D-T5 (User) | RViz-Bein und echtes Bein **synchron** nach Femur-Test | manuelle Bestätigung | User |
| D-T6 (User) | 2-Joint-Coordination: Coxa+Femur gleichzeitig auf +0.1, **keine Phasen-Versatz**, beide synchron in 3 s | manuelle Bestätigung | User |
| D-T7 (User) | Femur Endlagen-Test (-1.0/-0.5/+0.5/+1.0 rad) alle erreicht, kein Stall, PSU-Strom < 4 A | manuelle Bestätigung | User |
| D-T8 | YAML-Inspektion: Femur direction-Wert reflektiert D.2/D.3-Ergebnis | sichtbar im Diff (falls Flip) | Claude + User |

### Was bewusst NICHT in Stage D getestet wird

- **Tibia direction** (Stage E)
- **Strom-Logging-CSV** (Stage F)
- **IK-Trajectory** (Stage F)
- **Vel/Accel-Limits** (Stage G)

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

- [ ] D.1 phase_10_stage_d_plan.md (diese Plan-Doku) finalisiert + User-Freigabe
- [ ] D.2 phase_10_stage_d_test_commands.md angelegt mit operativer Anleitung
- [ ] D.3 D.0 Bench-Setup-Check ausgeführt vom User (PSU 7.0 V / **7 A**, Coxa+Femur an Pin 15+16, Tibia abgeklemmt, leg_5 ruhig)
- [ ] D.4 D.1 Plugin-Bringup grün mit **User-Hand am Bein**: 18× ENABLE_SERVO im Log, kein Trip
- [ ] D.5 D.2 Femur direction-Test (isoliert): Bewegungsrichtung dokumentiert
- [ ] D.6 D.3 (optional) Femur direction-Flip auf -1 mit YAML-Edit + colcon build + relaunch
- [ ] D.7 D.4 2-Joint-Coordination-Test gefahren: Coxa+Femur synchron auf +0.1 rad
- [ ] D.8 D.5 Femur Endlagen-Test -1.0/-0.5/0/+0.5/+1.0/0 rad alle erreicht, kein Stall
- [ ] D.9 D.6 PSU AUS, beide Servos abgeklemmt
- [ ] D.10 D.7 colcon build grün (regression-frei)
- [ ] D.11 D.7 colcon test grün 208/0/20 + 18/0/0
- [ ] D.12 D-T3..D-T7 User-Bestätigung
- [ ] D.13 D-T8 YAML-Inspektion (Femur direction sichtbar)
- [ ] D.14 Kritischer Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] D.15 Eventuelle Post-Review-Fixes + Stage-D-Notizen

**Done-Kriterium D erreicht:** wenn alle Bullets `[x]` UND
Self-Review keine 🔴 offenen Punkte hat UND User-Smoke D-T3..D-T7
bestätigt.

---

## Offene Punkte für User-Review (vor Implementation)

Siehe oben „User-Antworten"-Tabelle. 5 Punkte (D-Q1..D-Q5), Empfehlungen
dort.

---

## Erwartete Stage-D-Dauer

- D.1 Plan-Doku: ~30 min Claude (erledigt mit dieser Datei)
- D.2 test_commands.md: ~20 min Claude
- D.3 Bench-Setup-Check: ~5 min User
- D.4 Plugin-Bringup: ~3 min User
- D.5 Femur direction-Test: ~5 min User
- D.6 direction-Flip (falls nötig): ~10 min
- D.7 2-Joint-Coordination: ~5 min User
- D.8 Femur Endlagen-Test: ~10 min User
- D.9 Abklemm: ~3 min User
- D.10–D.11 Build + Test: ~5 min Claude
- D.12–D.13 User-Bestätigung: ~5 min Sync
- D.14 Self-Review: ~15 min Claude
- D.15 Post-Review-Fixes: variabel

**Schätzung:** ~1 h Claude-Arbeit + ~45 min User-HW-Arbeit + ~30 min Sync
= **~2.5 h Gesamt** (etwas länger als Stage C wegen 2-Joint-Koordination
+ höheres Femur-Stall-Risiko = mehr Vorsicht).
