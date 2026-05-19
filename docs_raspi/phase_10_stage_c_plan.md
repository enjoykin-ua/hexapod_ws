# Phase 10 — Stufe C — Plan

> **Status:** Plan, in Vorbereitung der HW-Arbeit.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe C — Stack-Validation `leg_6_coxa` (1 Servo).
>
> **Vorbedingung:** Stufe B komplett (`servo_mapping.yaml` Pin 15/16/17
> vor-kalibriert, Werte committed mit Tag/Commit aus 2026-05-17). Hexapod
> aufgebockt an Stock-Halterung, leg_5 darf jetzt wieder zurück in eine
> ruhige Default-Pose (worst-case-Pose nur für Stage B nötig — für
> Stage C ist nur **leg_6_coxa** unter Strom, leg_5 bleibt mechanisch
> montiert aber elektrisch abgeklemmt).

---

## Ziel

**Erste echte Servo-Bewegung dieser Phase, über die volle Stack-Pipeline.**
Der `leg_6_coxa`-Servo (Pin 15, Diymore 8120MG) wird:

1. Am Servo2040 angeschlossen (Femur + Tibia bleiben abgeklemmt)
2. Bench-PSU 7.0 V, CC-Limit 3 A
3. Plugin via `real.launch.py loopback:=false` aktiviert
4. Über `leg_6_controller` (JTC) bewegt:
   - kleiner Test-Schritt `+0.1 rad` → **direction-Bestimmung**
   - graduelle Erweiterung `±0.5 rad`, `±1.0 rad` → **Endlagen-Test**
5. Bei falscher Bewegungsrichtung: YAML edit `direction: -1`, rebuild, retest
   (Architektur-Entscheidung I aus Mutter-Plan-Doku)

Nach Stage C ist `direction` für `leg_6_coxa_joint` in
`servo_mapping.yaml` final gesetzt und über echte Bewegung verifiziert.
**Direction bleibt das einzige Cal-Feld das Stage C ändert** — pulse_min/zero/max
aus Stage B bleiben unverändert.

**Was Stage C NICHT macht:**

- Kein Femur-/Tibia-Test (Stage D / Stage E)
- Kein IK-Aufruf (Stage F)
- Kein Strom-Logging-CSV (Stage F)
- Keine Vel/Accel-Limit-Messung (Stage G)

---

## Strategie / Architektur-Erinnerungen

| Punkt | Entscheidung | Quelle |
|---|---|---|
| Bench-PSU | 7.0 V, CC 3 A (nur 1 Coxa-Servo) | Mutter-Plan §B, [`safety_setup.md`](phase_10_safety_setup.md) §2 |
| Verkabelungs-Sequenz | PSU-AUS → Stecker → Sichtprüfung → PSU-AN | Mutter-Plan §D, [`safety_setup.md`](phase_10_safety_setup.md) §4 |
| Initial-Pulse-Mitigation | User hält Bein nahe Coxa-Joint-Mitte (Bein radial außen) vor erstem ENABLE | Mutter-Plan §C, [`safety_setup.md`](phase_10_safety_setup.md) §6 |
| direction-Flip | Build-Edit-Build pro Flip (kein Live-Param) | Mutter-Plan §I |
| RViz-Sync-Check | RViz **separat** starten (`rviz2`) — `real.launch.py` hat keinen `rviz:=true`-Arg, Drift gegenüber Mutter-Plan §F | siehe Plan-Korrektur unten |
| Kill-Switch | Bench-PSU OUTPUT-Taste | [`safety_setup.md`](phase_10_safety_setup.md) §5 |

---

## Plan-Korrektur ggü. Mutter-Plan-Doku §F (RViz-Workflow)

Mutter-Plan-Architektur-Entscheidung F schreibt:
> „In Stages C/D/E/F läuft `real.launch.py` mit `rviz:=true`."

**Tatsächliche Situation:** [`real.launch.py`](../src/hexapod_bringup/launch/real.launch.py)
hat **keinen** `rviz`-LaunchArg — das wurde in Phase 9 bewusst ausgespart
(Docstring: „beim echten Roboter steht das physische Modell vor einem;
bei Bedarf separat `rviz2 -d view.rviz`"). Echo-State über
`/joint_states` wird per `robot_state_publisher` an tf2 publiziert,
RViz greift das ab wenn separat gestartet.

**Konsequenz für Stage C:** User startet RViz in einem **zweiten
Terminal** parallel zu `real.launch.py`:

```bash
# Terminal 1: Plugin + Controller-Manager
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false

# Terminal 2 (parallel): RViz
rviz2
# (Add → RobotModel, Description-Topic /robot_description)
# (Add → TF, Fixed Frame "base_link")
```

**Verworfen:** real.launch.py um `rviz:=true` erweitern — Aufwand
(launch-Code-Change + launch_testing-Anpassung + Doku) ist > der
Workflow-Gewinn (2 Terminals statt 1, einmal pro Stage).
**Phase-12-Kandidat falls Voll-Bringup das organisch wünscht.**

---

## Logik-Skizze

### C.0 — Bench-Setup-Check (Vorbereitung, ~5 min)

1. **Servo2040 USB** am Desktop, sichtbar als `/dev/ttyACM0`
   (`ls -l /dev/ttyACM*` → Servo2040)
2. **Bench-PSU OUTPUT AUS**, Spannungs-Setpoint **7.0 V**, CC-Limit **3 A**
3. **leg_6_coxa-Servo angesteckt** an Servo2040 Pin 15
   (Femur Pin 16, Tibia Pin 17 = **abgeklemmt**, leeres Header-Loch)
4. **leg_5** mechanisch montiert, elektrisch sowieso abgeklemmt (kein
   Strom an leg_5-Pins). Pose: zurück in ruhige Default — kein
   worst-case-Bedarf mehr für Stage C, weil Coxa-`pulse_min` aus Stage B
   bereits die Self-Collision-sichere Grenze ist.
5. **User-Position:** Hand bereit, leg_6 in Coxa-Joint-Mitte zu halten
   (Bein radial außen). PSU-Aus-Knopf griffbereit.

### C.1 — Plugin-Bringup (~2 min)

```bash
# Terminal 1
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

Erwartete Log-Sequenz (Stage-G-Pattern aus Phase 9):
- `HexapodSystemHardware::on_init starting (info_.joints.size=18)`
- `on_init complete — 18 joints mapped to 18 servo pins, calibration loaded from .../servo_mapping.yaml`
- `on_configure complete — serial port /dev/ttyACM0 opened`
- `on_activate` → 18× `ENABLE_SERVO` + neutralen `SET_TARGETS`-Frame
- joint_state_broadcaster + 6 leg-controller spawned
- keine `UNDERVOLTAGE_TRIPPED` / `WATCHDOG_TRIPPED` / `ANY_SERVO_OVERCURRENT`
  im Log

**Initial-Pulse-Schlag-Mitigation:** User hält das Bein während des
Bringups in Position mit Coxa nahe Mitte. Beim `on_activate` springt
der Coxa-Servo auf `pulse_zero = 1550 µs`. Wenn das Bein passiv etwas
seitlich war, dreht der Servo es zur Mitte (kleiner Sprung). Femur+Tibia
sind ungeladen — Bein hängt mech. nach Gravity.

**Bei Fehler:** PSU **sofort** AUS, dann Log analysieren.

### C.2 — direction-Test mit kleinem JTC-Goal (~5 min)

```bash
# Terminal 2 — RViz vorab (für Sync-Check)
rviz2  # RobotModel + TF wie oben

# Terminal 3 — Test-Goal an leg_6_controller
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [
        {positions: [0.1, 0.0, 0.0], time_from_start: {sec: 3, nanosec: 0}}
      ]
    }
  }"
```

**Beobachten am echten Bein:**

- Coxa-Joint dreht das Bein um **0.1 rad ≈ 5.7°**, das ist visuell
  ein kleiner aber sichtbarer Schwenk
- **Welche Richtung?** Konvention nach
  [`docs/00_conventions.md`](../docs/00_conventions.md) §2: Coxa-Achse =
  Z, positive Werte → Bein rotiert im Sinn der Rechte-Hand-Regel um Z
  (= im Body-Frame **gegen den Uhrzeigersinn von oben gesehen**)
- Bei leg_6 (vorne-links, yaw +π/4): positive Coxa-Drehung → Bein
  schwenkt **Richtung +Y-Achse (nach hinten-links, weg von leg_1)**
- **Wenn echtes Bein in genau diese Richtung dreht** → `direction = +1`
  ist korrekt, kein YAML-Edit nötig
- **Wenn echtes Bein in entgegengesetzte Richtung dreht** (zur
  Body-Mitte / Richtung leg_1) → `direction = -1` ist nötig

**RViz-Sync-Check (parallel):** RViz zeigt das Echo-State-Modell.
Wenn `direction` aktuell richtig ist, dreht das RViz-Bein **synchron**
zum echten Bein. Wenn falsch, dreht RViz-Bein in eine andere Richtung
als das echte (RViz folgt der URDF-Konvention, echtes Bein der Servo-
Mechanik) — Sync-Mismatch ist der eindeutige Indikator für falsches
`direction`.

### C.3 — Optional: direction-Flip falls nötig (~10 min)

**Wenn C.2 zeigt: echtes Bein dreht falsch:**

```bash
# Terminal 1: Ctrl-C (real.launch.py beenden)
# Terminal 4: YAML edit
# in src/hexapod_hardware/config/servo_mapping.yaml:
#   15:
#     joint: leg_6_coxa_joint
#     pulse_min:  1280
#     pulse_zero: 1550
#     pulse_max:  1860
#     direction:  -1     # NEU: Flip von default +1
```

Dann:

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
# Bench-PSU AUS (sicher), Terminal 1 wieder hochfahren
ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
```

C.2 retest. Wenn jetzt grün → `direction = -1` final.
Wenn immer noch falsch → Logik-Fehler in dieser Analyse oder URDF-
Konvention falsch interpretiert; STOP, gemeinsam diagnostizieren.

### C.4 — Endlagen-Test (±1.0 rad in 2 Schritten, ~10 min)

Mit korrektem `direction`:

```bash
# Test 1: +0.5 rad in 3 s
ros2 action send_goal /leg_6_controller/follow_joint_trajectory \
  control_msgs/action/FollowJointTrajectory "{
    trajectory: {
      joint_names: ['leg_6_coxa_joint', 'leg_6_femur_joint', 'leg_6_tibia_joint'],
      points: [{positions: [0.5, 0.0, 0.0], time_from_start: {sec: 3, nanosec: 0}}]
    }
  }"

# Test 2: +1.0 rad (zur Coxa-Plus-Endlage gemessen in Stage B)
# Hinweis: pulse_max=1860 µs entspricht etwa +1.57 rad (URDF-Limit),
# aber unsere Stage-B-Coxa-Range war asymmetrisch — +1.0 rad ist gut
# innerhalb, kein Stall-Risiko erwartet
... positions: [1.0, 0.0, 0.0] ...

# Test 3: zurück zu 0.0
... positions: [0.0, 0.0, 0.0] ...

# Test 4: -0.5 rad (Self-Collision-Seite, vorsichtig)
... positions: [-0.5, 0.0, 0.0] ...

# Test 5: -1.0 rad (Self-Collision-Seite, immer noch innerhalb pulse_min=1280)
# pulse_min=1280 ist 5° vor Self-Collision mit leg_5 → bei direction=+1
# entspricht das ungefähr -1.0 rad. Wenn der JTC eine Goal-Position
# innerhalb [-1.0, +1.0] schickt, bleibt der Pulse in [pulse_min, pulse_max]
# und es gibt kein Anschlag-Brumm.
... positions: [-1.0, 0.0, 0.0] ...

# Final: zurück zu 0.0
... positions: [0.0, 0.0, 0.0] ...
```

**Beobachten:**

- Jede Bewegung sauber, kein Servo-Brumm, kein Watchdog-Trip
- Strom bei Bench-PSU < 1 A statisch, < 2 A während Bewegung
  (Stall-Limit ist 3 A)
- RViz und echtes Bein synchron in allen Posen
- **Bei -1.0 rad:** sicher-stellen dass Bein NICHT leg_5 berührt
  (Stage B Self-Collision-Sicherheits-Marge sollte greifen, aber
  Sichtkontrolle)

**Bei Stall/Brumm:** PSU **sofort** aus, im Log nach
`ANY_SERVO_OVERCURRENT`/`WATCHDOG` schauen, pulse_min/max im YAML
überdenken.

### C.5 — Shutdown + Abklemm-Sequenz (~3 min)

```bash
# Terminal 1: Ctrl-C → real.launch.py sauberer Shutdown
# Plugin sendet 18× DISABLE_SERVO automatisch (on_deactivate)
```

Dann:

1. Bench-PSU **OUTPUT AUS**
2. Coxa-Servo-Connector von Pin 15 **abziehen** (Vorbereitung für Stage D)
3. Bench-PSU bleibt eingestellt (7.0 V / 3 A), wartet auf Stage D

### C.6 — Build/Test/Self-Review

- Wenn `direction = -1` final: `colcon build --packages-select hexapod_hardware`
  bestätigen + `colcon test` weiter grün (208/0/20)
- Wenn `direction = +1` bleibt: kein Build-Edit nötig, nur Test-Lauf
  zur Sicherheit
- Self-Review-Tabelle pro CLAUDE.md §4
- Test-Commands-Doc finalisieren

---

## Tests-Liste (CI + User-Smoke)

| # | Test | Erwartung | Wer |
|---|---|---|---|
| C-T1 | `colcon build --packages-select hexapod_hardware` | grün, regression-frei (relevant wenn direction-Flip auf -1) | Claude |
| C-T2 | `colcon test --packages-select hexapod_hardware hexapod_bringup` | 208/0/20 + 18/0/0 unverändert | Claude |
| C-T3 (User) | Plugin-Bringup ohne Errors (`real.launch.py loopback_mode:=false` startet, 18× ENABLE_SERVO im Log, kein TRIP) | manuelle Bestätigung | User |
| C-T4 (User) | direction-Test mit +0.1 rad: Coxa-Bein dreht **sichtbar** in URDF-positive Richtung (= weg von leg_1, Richtung +Y) | manuelle Bestätigung | User |
| C-T5 (User) | RViz-Bein und echtes Bein **synchron** in derselben Pose nach +0.1 rad | manuelle Bestätigung | User |
| C-T6 (User) | Endlagen-Test ±1.0 rad: alle 5 Goals erreicht, kein Stall/Brumm, kein Trip | manuelle Bestätigung | User |
| C-T7 (User) | leg_6 berührt **NIEMALS** leg_5 während C.2–C.4 (Self-Collision-Schutz aus Stage B greift) | manuelle Bestätigung + Sichtkontrolle | User |
| C-T8 | YAML-Inspektion: `direction`-Wert für Pin 15 reflektiert C.2-Ergebnis (+1 default oder -1 wenn Flip) | sichtbar im Diff (wenn Flip) | Claude + User |

### Was bewusst NICHT in Stage C getestet wird

- **Femur + Tibia direction:** Stage D / Stage E
- **Bein-Geometrie-Lineal-Check:** Stage F.1
- **IK-Trajectory:** Stage F.2
- **gait_node:** Stage F.3
- **Strom-Logging-CSV:** Stage F (nur Augenmaß auf PSU-Display in C)
- **Vel/Accel-Limits:** Stage G

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

Diese Bullets werden 1:1 in `phase_10_progress.md` Stage-C-Sektion
kopiert und dort `[ ]`→`[x]` umgestellt.

- [ ] C.1 phase_10_stage_c_plan.md (diese Plan-Doku) finalisiert + User-Freigabe
- [ ] C.2 phase_10_stage_c_test_commands.md angelegt mit operativer Anleitung (C-T3..C-T7 User-Smoke-Schritte)
- [ ] C.3 C.0 Bench-Setup-Check ausgeführt vom User (PSU 7.0 V / 3 A, Coxa-Servo an Pin 15, Femur/Tibia abgeklemmt, leg_5 in ruhiger Pose)
- [ ] C.4 C.1 Plugin-Bringup grün: `on_init`/`on_configure`/`on_activate` ohne Errors, 18× ENABLE_SERVO im Log
- [ ] C.5 C.2 direction-Test +0.1 rad gefahren, Bewegungsrichtung dokumentiert
- [ ] C.6 C.3 (optional) direction-Flip auf -1 mit YAML-Edit + colcon build + relaunch (nur wenn C.5 zeigt: falsch herum)
- [ ] C.7 C.4 Endlagen-Test ±0.5 rad und ±1.0 rad alle erreicht, kein Stall
- [ ] C.8 C.5 PSU AUS, Coxa-Servo abgeklemmt
- [ ] C.9 C.6 colcon build grün (regression-frei, relevant wenn direction-Flip)
- [ ] C.10 C.6 colcon test grün 208/0/20 + 18/0/0
- [ ] C.11 C-T3 + C-T4 + C-T5 + C-T6 + C-T7 User-Bestätigung
- [ ] C.12 C-T8 YAML-Inspektion (direction-Wert sichtbar im Diff falls Flip)
- [ ] C.13 Kritischer Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] C.14 Eventuelle Post-Review-Fixes
- [ ] C.15 Stage-C-Notizen + finale Doku-Updates

**Done-Kriterium C erreicht:** wenn alle Bullets `[x]` UND
Self-Review keine 🔴 offenen Punkte hat UND User-Smoke C-T3..C-T7
bestätigt.

---

## User-Antworten (User-Freigabe 2026-05-17)

Diese Punkte wurden vor Stage-C-Implementation geklärt:

| Frage | Antwort | Konsequenz |
|---|---|---|
| **C-Q1** Trajectory-Mechanismus | **A** — `ros2 action send_goal` | Goal-Akzeptanz-Check + Trajectory-Validation gegen URDF-Limits explizit beim Senden. **Wichtig:** wegen Echo-State (kein echtes Servo-Feedback) ist `status=SUCCEEDED` **immer** erfüllt — visuelle Beobachtung am echten Bein bleibt einzige Wahrheit. Phase 13 Walking nutzt später Topic-Streaming für 50-Hz-Updates aus gait_node; Action ist Stage-C/D/E/F.2-spezifisch zum Debuggen. |
| **C-Q2** Anzahl Endlagen-Test-Schritte | **A** — 5-stufig (+0.5, +1.0, 0, -0.5, -1.0, 0) | Graduelle Steigerung; Diagnose-Wert bei Stall (= „letzte gute Pose" identifizierbar) |
| **C-Q3** RViz separat oder Launch-Extension | **A** — separat starten (`rviz2` Terminal 2) | Plan-Korrektur ggü. Mutter-Plan §F. Kein Code-Change in Phase 10. |
| **C-Q4** User-Hand-Position während Bringup | **A** — Bein nahe Coxa-Mitte, Femur/Tibia passiv hängend | Femur/Tibia sind stromlos in Stage C (Pins 16/17 abgeklemmt) → pendeln stört Coxa-Beobachtung praktisch nicht |
| **C-Q5** Bei Stall-Brumm bei -1.0 rad | **A** — `pulse_min` im YAML auf 1300 erhöhen, rebuild, retest | Hardware-Fix bei zu enger Stage-B-5°-Marge. Korrektur wird im `phase_10_stage_b_calibration_log.md` §5 vermerkt (Spätere Korrekturen Stage C+). Niedrige Eintritts-Wahrscheinlichkeit. |

### Stage-Aufbau über Phase 10 (zur Erinnerung)

User-Frage vom 2026-05-17: „testen wir alle Servos einzeln, oder alle 3 angeschlossen?"

| Stage | Elektrisch angeschlossen | Stromlos abgeklemmt | Test |
|---|---|---|---|
| **C** (jetzt) | **nur Coxa Pin 15** | Femur Pin 16, Tibia Pin 17 | Coxa direction + Endlagen |
| **D** | Coxa Pin 15 + Femur Pin 16 | Tibia Pin 17 | Femur direction + 2-Joint-Coordination |
| **E** | **nur Tibia Pin 17** | Coxa Pin 15, Femur Pin 16 | Tibia isoliert (kein Bein-Gewicht-Hebel an Tibia-Servo) |
| **F** | alle 3 (Pin 15+16+17) | — | IK-Aufruf + gait_node Voll-Pipeline |

Stages C/D testen je 1 neuen Servo (direction-Bestimmung), Stage E isoliert Tibia diagnostisch, Stage F bringt alle 3 unter IK-Kontrolle.

---

## (Archivierte) Offene Punkte vor User-Review

Original-Optionen siehe oben im User-Antworten-Block. Alle entschieden 2026-05-17.

---

## Erwartete Stage-C-Dauer

- C.1 Plan-Doku (diese Datei): ~30 min Claude (erledigt)
- C.2 test_commands.md (Skelett): ~20 min Claude
- C.3 Bench-Setup-Check: ~5 min User
- C.4 Plugin-Bringup: ~2 min User
- C.5 direction-Test: ~5 min User
- C.6 direction-Flip (falls nötig): ~10 min Build + Relaunch
- C.7 Endlagen-Test: ~10 min User
- C.8 Abklemmen: ~3 min User
- C.9–C.10 Build+Test: ~5 min Claude
- C.11–C.12 User-Bestätigung: ~5 min sync
- C.13 Self-Review: ~15 min Claude
- C.14 Post-Review-Fixes: variabel

**Schätzung:** ~1 h Claude-Arbeit + ~30 min User-HW-Arbeit + ~30 min Sync
= **~2 h Gesamt** (etwas weniger als Stage B weil keine Tester-Mess-Iteration,
aber + Risiko direction-Flip-Iteration).
