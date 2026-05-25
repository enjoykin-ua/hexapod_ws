# Phase 13 — Voll-Bringup mit echtem Roboter

**Dauer-Schätzung:** 3–5 Tage (Kalenderzeit, viele Iterationen — Stufe B
reduziert auf Pi-Recheck + Femur-Asymmetrie-Fix, da Cross-Phase-Thread
`servo_real_cal` 2026-05-25 alle 18 Pins bereits kalibriert hat)
**Maschine:** Raspberry Pi 4 am Roboter, Desktop für Monitoring/Teleop
**Vorbedingung:**
- Phase 12 abgeschlossen (Pi-Plattform steht)
- Phase 10 abgeschlossen (Single-Leg-Bringup mit leg_6 am Desktop)
- **Cross-Phase-Thread `servo_real_cal` ✅ 2026-05-25** — alle 18 Pins
  kalibriert mit direction-Map (`servo_mapping.yaml`), Stage 0.5/0.6
  Safety-Layer in Plugin + gait_node, URDF mit per-Pin asymm rad-Limits,
  HW-Walking aufgebockt verifiziert (`cmd_vel` 0.02/0.03/0.035 m/s ohne
  IKError). Plan-Index: `servo_real_cal_plan.md`.

---

## Ziel

Den vollen Hexapod-Stack auf dem Pi mit echter Hardware in Betrieb nehmen.
Reihenfolge: **Pi-Recheck Cal + Femur-Asymmetrie-Fix** (Stufe B) → alle
18 Beine in Stand-Pose aufgebockt am Pi (Stufe C, vorher am Desktop in
servo_real_cal-E2.3 ✓) → Tripod in der Luft (Stufe D, vorher
E2.4/E2.5 ✓) → Stand auf Boden (Hängevorrichtung, Stufe E — neu) →
erster Walk (Stufe F — neu) → Phase-6-PS4-Vollbetrieb (Stufe G).

**Sicherheits-Schwerpunkt der Phase.** Jede Stufe hat einen
„Goldenen-Regeln"-Block, der **gelesen sein muss** bevor der Hauptschalter
zugeht.

---

## Hardware-Setup für diese Phase

- Pi am Roboter montiert oder in unmittelbarer Nähe
- Servo2040 am Pi per USB-C-Kabel (3 m XT60-Kabel reicht für Bench-Strom)
- Bench-PSU als Stromquelle (kein Akku)
- DCDC versorgt Pi
- Alle 18 Pins bereits kalibriert in `servo_mapping.yaml` durch Cross-
  Phase-Thread `servo_real_cal` (am Desktop). Stufe B macht Pi-Recheck +
  Femur-Asymmetrie-Fix (siehe Memory `project_phase13_femur_zero_asymmetry`)
- Hängevorrichtung über dem Roboter (Seil/Gurt durch Body-Aufhängung, an
  Decken-Haken oder Stativ)
- PS4-Controller (USB)
- Notebook am SSH-Terminal für Live-Diagnose

---

## Sicherheits-Recap (CLAUDE.md §9 + Phase 7 Sicherheits-Ebenen)

- **Aufgebockt** bis Stufe F
- Hand am PSU-Aus-Knopf bei jeder neuen Stufe
- `controllers.real.yaml` mit **reduzierten Velocity/Acceleration-Limits**
  zum Start (30 % der Sim-Werte) — werden in Stufe G hochgezogen
- Servo2040-Watchdog **aktiv** (Phase 7)
- Per-Servo-Strom-Limits **aktiv** (Phase 7)
- Low-Voltage-Cutoff aktiv
- Dead-Man-Switch (R1) ist Pflicht für `cmd_vel`-Bewegung
- Bei unerwartetem Verhalten: **erst Strom aus, dann analysieren**

---

## Done-Kriterien

1. Servo2040 hängt am Pi (USB), `hexapod_hardware` läuft auf Pi (Stufe A)
2. **Alle 18 Servos in `servo_mapping.yaml` `calibrated` (am Desktop fertig
   im servo_real_cal-Thread); Pi-Recheck dass Cal nach Pi-Transfer noch
   klappt + Femur-Asymmetrie aus servo_real_cal-E2 gefixt (Stufe B)**
3. Stand-Pose alle 18 aufgebockt stabil > 5 min (Stufe C)
4. Tripod-Cycle aufgebockt sichtbar synchron (Stufe D)
5. Stand-Pose mit Bodenkontakt > 30 s stabil, Hängevorrichtung trägt
   nicht (Stufe E)
6. Mindestens 1 m Walk geradeaus ohne Eingriff, Hängevorrichtung trägt
   nicht (Stufe F)
7. PS4-Vollbetrieb wie Phase 6, alle Modi aus Phase-5-Stufe-H funktional
   (Stufe G)
8. Limits hochgezogen auf Phase-5/6-Werte (Stufe H)
9. Yaw-Drift charakterisiert und dokumentiert (Stufe H)
10. Phase-Abschluss-Doku komplett (Stufe I)

---

## Stufen

### Stufe A — Servo2040 ans Pi umziehen

**Ziel:** Stack der Phase 9/10/11 jetzt auf dem Pi mit Servo2040 fahren.

#### A.1 Hardware

- Bench-PSU **aus**
- USB-Kabel Servo2040 ↔ Desktop ziehen
- USB-Kabel Servo2040 ↔ Pi anschließen
- Pi-Power weiter über DCDC, Servo-Power weiter über PSU
- Hauptschalter (= PSU) zu, Pi muss bootbar bleiben

#### A.2 Pi-seitig

```bash
ssh hexapod-pi
ls -l /dev/ttyACM*       # erwartet: Servo2040 sichtbar
```

User in `dialout`-Gruppe? Falls nicht:
```bash
sudo usermod -aG dialout $USER
# einmal aus- und neu einloggen, dann nochmal ls
```

#### A.3 Loopback-Test → echt-Test

```bash
cd ~/hexapod_ws
source install/setup.bash

# Loopback first (kein Servo2040-Verkehr)
ros2 launch hexapod_bringup real.launch.py loopback:=true
# Ctrl-C

# Dann echt — KEINE Servos angeschlossen (sicherheits-Buffer)
# Hauptschalter PSU AUS, dann starten:
ros2 launch hexapod_bringup real.launch.py loopback:=false
```

Beobachten:
- `/dev/ttyACM0` wird geöffnet (Logs schauen)
- `STATE`-Frames kommen rein (Strom-Telemetrie)
- Watchdog feuert nicht (alle 20 ms ein Frame raus)

#### A.4 Servos hot-anstecken? NEIN.

Vorgehen für die Servo-Anbindung:
1. Pi und ROS-Stack **runterfahren**
2. PSU **aus**
3. Erst dann Servo-Kabel umstöpseln
4. PSU an, Pi an, ROS-Stack an

Hot-Plugging der Servo-Kabel ist nicht riskant für die Elektronik, aber
ein Strom-Spike beim Verbinden kann die Sicherheits-Logik in
verwirrendem Zustand triggern.

**Done-Kriterium A:**
1. Servo2040 vom Pi sichtbar als `/dev/ttyACM0`
2. Stack läuft, `STATE`-Frames kommen, kein Watchdog-Trip
3. Pi/PSU-Abschalt-Reihenfolge dokumentiert

---

### Stufe B — Pi-Recheck Cal + Femur-Asymmetrie-Fix

**Ziel:** Verifizieren dass die in `servo_real_cal` (am Desktop fertig
2026-05-25) ermittelten Cal-Werte für alle 18 Pins nach Pi-Transfer
identisch funktionieren, und die in `servo_real_cal-E2.3` entdeckte
Femur-Asymmetrie rechts/links (~5°) beheben.

**Vorbedingung:** Stufe A grün (Plugin läuft auf Pi gegen Servo2040,
USB stabil). Hexapod **aufgebockt**. `servo_mapping.yaml` ist identisch
zur Desktop-Version (Git-Pull oder File-Sync).

**Begründung des Scope-Wechsels:** Stage B war ursprünglich
„SW-Auto-Cal für 15 verbleibende Servos". Der Cross-Phase-Thread
`servo_real_cal` (Stages B/C/D) hat alle 18 Pins kalibriert
(`pulse_min/zero/max` + `direction`), inkl. Mount-Tausch-Korrektur
leg_2↔leg_5. Damit ist die Auto-Cal-Tool-Pflicht entfallen. Stage B
wird stattdessen zum **Pi-Recheck mit Femur-Asymmetrie-Fix** —
deutlich kürzer (~30–60 min statt 2 d).

#### B.1 Pi-Sanity: `servo_mapping.yaml` identisch zu Desktop

```bash
# Auf Pi:
cd ~/hexapod_ws
md5sum src/hexapod_hardware/config/servo_mapping.yaml
# Auf Desktop:
ssh desktop "md5sum ~/hexapod_ws/src/hexapod_hardware/config/servo_mapping.yaml"
```

→ Hashes müssen übereinstimmen. Wenn nicht: Git-Pull / rsync.

#### B.2 Loopback-Test: Plugin lädt Cal sauber am Pi

```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

Erwartet: Plugin-Init-Logs `Stage 0.5: /hexapod_safety_reset service ready`,
6× `Configured and activated leg_<n>_controller`, **KEIN**
`safety_freeze` beim Init. Stoppt mit Strg+C.

#### B.3 Femur-Asymmetrie-Fix (Option B aus Memory)

**Hintergrund:** Memory [[project-phase13-femur-zero-asymmetry]] —
`servo_real_cal-E2.3` zeigt visuell, dass Femur-pulse_zero rechts
(legs 1/2/3, Ø 1485 µs) vs. links (legs 4/5/6, Ø 1543 µs) ~58 µs
auseinanderliegt → ~5° Offset. Bei IK-Stand-Pose stärker eingeknickt
rechts. Auf Boden würde das zu Body-Tilt führen.

**Vorgehen mit Wasserwaage am Femur-Segment** pro Bein:

1. Plugin läuft im echten Mode (`real.launch.py` ohne loopback)
2. Bein-Trajectory zur Joint-Null senden:
   ```bash
   ros2 topic pub --once /leg_<N>_controller/joint_trajectory \
     trajectory_msgs/msg/JointTrajectory \
     '{joint_names: ["leg_<N>_coxa_joint", "leg_<N>_femur_joint", "leg_<N>_tibia_joint"],
       points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
   ```
3. Wasserwaage auf Femur-Segment — ist es horizontal?
4. Falls nein: pulse_zero anpassen via rqt_reconfigure ODER CLI:
   ```bash
   ros2 param set /hexapodsystem pin_<N>.pulse_zero <neuer_Wert>
   ```
   Werte trimmen bis horizontal. Pro µs ≈ 0.09°. ~50 µs Spielraum erwartet.
5. Wiederholen für alle 6 Femur-Pins (1, 4, 7, 10, 13, 16)
6. Wenn alle 6 horizontal: persistieren
   ```bash
   ros2 service call /save_calibration std_srvs/srv/Trigger '{}'
   ```
   → `servo_mapping.yaml` wird mit Backup `.bak.<timestamp>` aktualisiert

#### B.4 Stand-Pose-Recheck am Pi

```bash
# T2:
ros2 launch hexapod_gait gait.launch.py \
  use_sim_time:=false \
  robot_description_file:=$(ros2 pkg prefix hexapod_description)/share/hexapod_description/urdf/hexapod.urdf.xacro \
  params_file:=$(ros2 pkg prefix hexapod_gait)/share/hexapod_gait/config/presets/sim_walk.yaml
```

Erwartet: gait_node fährt alle 6 in Stand-Pose, **diesmal visuell
symmetrisch rechts/links** (Femur-Asymmetrie behoben). 30 s stabil.

#### B.5 (Optional) Memory-Update + Phase-13-Pendenz schließen

Wenn B.3 erfolgreich:
- Memory `project_phase13_femur_zero_asymmetry.md` als ✅ markieren
  oder löschen
- Falls Asymmetrie aus B.3 nicht ganz weg ist (mechanisch limitiert):
  Option C aus Memory (URDF-`mount_offset`) als neue Sub-Pendenz öffnen

**Done-Kriterium B:**
1. `servo_mapping.yaml` MD5 identisch Desktop↔Pi (B.1)
2. Plugin-Loopback-Init grün am Pi (B.2)
3. Alle 6 Femur-Segmente bei `rad=0` horizontal — Wasserwaage bestätigt (B.3)
4. `/save_calibration` ausgeführt, Backup `.bak.*` vorhanden (B.3)
5. gait_node-Stand-Pose visuell symmetrisch rechts/links, 30 s stabil (B.4)
6. Memory-Pendenz `project_phase13_femur_zero_asymmetry.md` aktualisiert

---

### Stufe C — Stand-Pose alle 18 aufgebockt (Pi-Recheck)

**Ziel:** Voll-Stand am Pi, aufgebockt. Stresstest der Boot-Sequenz.

> **Wurde am Desktop in `servo_real_cal-E2.3` (2026-05-25) bereits
> verifiziert** — alle 6 Beine fahren simultan in Stand-Pose, 30 s stabil,
> kein IKError, kein safety_freeze. Auf Pi ist's hier der Recheck dass
> das identisch klappt. Falls es klappt: ✓ schnell durch. Falls nicht:
> Pi-spezifisches Problem (DDS, USB-Latenz, Strom).

#### C.1 Vorbereitung

- Roboter **aufgebockt**, Beine in der Luft
- Beine manuell in **ungefähre Stand-Pose** vorpositionieren (reduziert
  Anlauf-Wege beim Enable)
- PSU **aus**
- Pi an, `real.launch.py loopback:=false` läuft, **kein** `cmd_vel`-Eingang

#### C.2 Power-On

1. **Schaue auf die Beine, nicht auf das Terminal.**
2. Hand am PSU-Aus-Knopf.
3. PSU einschalten → Servo2040 boot-Sequenz feuert
4. Beine fahren gestaffelt (aus Phase 7 Stufe D) in Stand-Pose
5. **Wenn ein Bein in falsche Richtung fährt:** PSU sofort aus,
   Kalibrierung prüfen
6. **Wenn alles gut:** 5 min in Stand-Pose halten

#### C.3 Stand-Pose-Stabilität

In separatem SSH-Terminal:

```bash
ros2 topic echo /joint_states --field effort
# Stromwerte pro Joint (Effort-Interface = Current-Sense)
```

Beobachten:
- Statische Stromwerte pro Servo: wenige hundert mA, < 80 % Stallstrom
- Body-Pose visuell symmetrisch
- Kein hörbares Zucken / Vibrieren

#### C.4 Body-Höhe-Korrektur

Default in `gait_node` ist `body_height = -0.052` (Sim-Workaround).
**Für echte HW: -0.047** (siehe Phase-6-Übergabe in PHASE.md).

Per LaunchArg oder direkt im YAML setzen, vor `real.launch.py`-Start.

**Done-Kriterium C:**
1. Boot-Sequenz: Beine fahren gestaffelt ohne Stalls
2. Stand-Pose visuell symmetrisch
3. Strom-Mittelwert pro Servo < 80 % Stall
4. 5 min stabil, keine Trips
5. `body_height` auf -0,047 umgestellt für HW

---

### Stufe D — Tripod-Cycle aufgebockt (Pi-Recheck)

**Ziel:** Vollständiger Tripod-Cycle, drei Beine schwingen, drei „stützen"
(in der Luft, ohne Last). Synchronität verifizieren.

> **Wurde am Desktop in `servo_real_cal-E2.4/E2.5` (2026-05-25) bereits
> verifiziert** — Tripod-Walking aufgebockt mit cmd_vel 0.02/0.03/0.035 m/s
> ohne IKError, Clamp-WARN bei 0.04 m/s korrekt. Auf Pi: Recheck.
> **Hinweis:** `gait.launch.py` braucht `use_sim_time:=false` auf HW
> (siehe Memory [[project-phase13-gait-launch-sim-time-default]]).
> sim_walk.yaml-Preset hat `linear_max=0.035 m/s`.

#### D.1 Foot-Contact deaktivieren

`gait_node` erwartet in Sim die `/foot_contact_*`-Topics von Gazebo. Auf
echter HW gibt's diese Sensoren nicht.

Param `enable_foot_contact:=false` setzen. State-Machine läuft dann rein
zeitgesteuert (siehe Phase-5-Stufe-G-Logik).

Per LaunchArg oder als gait-Param-YAML.

#### D.2 Schwenk-Test

In einem Terminal:
```bash
ros2 topic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}, angular: {z: 0.0}}'
```

Erwartung:
- Drei Beine schwingen (Tripod A), drei stehen (Tripod B), dann Wechsel
- Sieht symmetrisch aus? Trajektorien glatt?
- Echte Servos haben keinen JTC-Tracking-Lag — Bewegung sollte **glatter**
  aussehen als Sim

#### D.3 Omnidirektional

`linear.y`, `angular.z`, Kombinationen. Alle Phase-5-Stufe-H-Modi
durchprobieren — in der Luft.

#### D.4 Strom-Profil unter Walk-in-Luft

5 min Walk-Cycle laufen lassen. Strom pro Servo loggen:

```bash
ros2 bag record /joint_states /cmd_vel
```

Bag später analysieren. Spitzen sollten nicht > 80 % Stall.

**Done-Kriterium D:**
1. Tripod-Cycle sichtbar synchron in der Luft
2. Omnidirektional alle Modi funktional
3. 5 min Walk-in-Luft ohne Trips
4. Strom-Profil dokumentiert

---

### Stufe E — Stand-Pose auf Boden (Hängevorrichtung sichert)

**Ziel:** Roboter vom Bock auf Boden, aber **mit Hängevorrichtung** über
ihm. Stand trägt sich selbst, Hängevorrichtung darf den Roboter **nicht**
hochziehen — sie ist nur Sturz-Schutz.

#### E.1 Hängevorrichtung

- Seil/Gurt durch Body-Aufhängung
- An Decken-Haken oder stabilem Stativ befestigt
- Länge so eingestellt, dass Roboter den Boden gerade berührt
- **Hand drauf:** kann den Roboter bei Bedarf hochheben

#### E.2 Stand-Pose mit Last

`gait_node` in STANDING-State, `cmd_vel = (0, 0, 0)`. Roboter trägt sein
eigenes Gewicht.

Beobachten:
- Trägt der Femur-Servo das halbe Roboter-Gewicht?
- Erwartete Stromwerte pro Femur-Servo: **deutlich höher als aufgebockt**,
  1–2 A statisch realistisch
- Wenn deutlich höher: Servo arbeitet gegen sich selbst (Kalibrierungs-
  Fehler) oder mechanische Verspannung. Zurück zu Stufe B.

#### E.3 Stand-Pose-Dauer

5 min Stand mit Bodenkontakt:
- Sinkt der Body merklich? (= Servo-Droop, akzeptabel wenn < 5 mm)
- Werden Servos heiß? (Hand an Gehäuse, oder IR-Thermometer; > 60 °C ist
  Alarm)

**Done-Kriterium E:**
1. Stand mit Bodenkontakt > 30 s stabil
2. Hängevorrichtung trägt nicht
3. Stromwerte pro Servo in plausiblem Bereich, < 80 % Stall
4. Servo-Temperaturen < 60 °C nach 5 min Stand

---

### Stufe F — Erster Walk auf Boden

**Ziel:** Erste echte Schritte. Klein anfangen.

#### F.1 Minimaler Walk

Per PS4 (mit R1-Dead-Man): D-Pad ↑ kurz drücken, `cmd_vel.linear.x = 0,02 m/s`.

Roboter macht **einen Schritt**, vielleicht zwei. Dann loslassen.

Beobachten:
- Tracking visuell OK? (Beine landen wo erwartet?)
- Yaw-Drift sichtbar?
- Stürzt der Roboter? (Hängevorrichtung fängt ab — kein Schaden)
- Strom-Spitzen, die Limits triggern?

**Bei Sturz:** nicht in Panik mehr Code schreiben. Erst analysieren
(Stromlog, Video, was war zuerst).

#### F.2 Schrittweise verlängern

Wenn 1 Schritt OK: 2 Schritte. Dann 5. Dann 1 m geradeaus.

#### F.3 Yaw-Drift charakterisieren

Bei 1 m geradeaus: wie viel Grad Yaw-Drift?
- < 5 °: super
- 5–15 °: typisch bei Hexapod ohne IMU
- > 15 °: Kalibrierungs-Verdacht, Bein-spezifischen Drift suchen

Wert in `phase_13_progress.md` festhalten.

**Done-Kriterium F:**
1. Mindestens 1 m geradeaus ohne Eingriff
2. Hängevorrichtung wurde nicht gebraucht
3. Keine Strom-Limit-Trips
4. Yaw-Drift dokumentiert

---

### Stufe G — PS4-Vollbetrieb wie Phase 6

**Ziel:** Alle Phase-6-Funktionen auf echter HW.

#### G.1 Standard-Bewegung

- D-Pad ↑ / ↓ / ← / → für vor/zurück und Drehung am Stand
- R1 als Dead-Man (Pflicht)
- L2/R2 für Body-Lift (nur im STANDING-State)

#### G.2 Sturz-Vermeidung

- Hängevorrichtung weiter aktiv
- Schrittweise Tests, nicht direkt Vollausschlag
- Bei jeder neuen Modus-Kombination: erstmal aufgebockt verifizieren,
  dann auf Boden

#### G.3 Omnidirektional auf Boden

`linear.y`-Anteil, `angular.z`-Anteil, Kombinationen.

**Done-Kriterium G:**
1. PS4-Vollbetrieb wie Phase 6 funktional
2. Omnidirektional auf Boden in alle Richtungen
3. Body-Lift im STANDING-State funktioniert

---

### Stufe H — Limits hochziehen + Tuning

**Ziel:** `controllers.real.yaml`-Limits Schritt für Schritt von 30 % auf
Phase-5/6-Sim-Werte hochziehen.

#### H.1 Schritt-für-Schritt

- `max_linear_x`: 0,02 → 0,05 → 0,10 → Phase-5-Wert
- Nach jedem Step: aufgebockt → mit Hängevorrichtung → frei
- Auf Trips, Stalls, Stürze achten

#### H.2 Velocity/Acceleration-Limits

`controllers.real.yaml` schrittweise lockern. Vergleich zur Sim — die Sim
hatte schon „funktioniert"-Werte, also sind das die Obergrenzen.

#### H.3 Soft-Ramp in Firmware anpassen?

Wenn JTC-Trajectories sauberer fahren als die Soft-Ramp es zulässt: in
Phase-7-Firmware `MAX_DELTA_PER_TICK` hochsetzen. Sicherheits-Buffer
behalten, aber nicht künstlich limitieren.

**Done-Kriterium H:**
1. Limits auf Phase-5/6-Werte hochgezogen
2. Kein Servo-Strom-Limit unter normalem Betrieb
3. Yaw-Drift bei vollem Walking dokumentiert

---

### Stufe I — Phase-12-Abschluss

- `phase_13_progress.md` finalisieren:
  - Strom-Profile pro Bewegungstyp
  - Yaw-Drift
  - Servo-Temperaturen
  - Foto/Video vom ersten Walk
- `00_conventions.md` ergänzen mit HW-spezifischen Werten:
  - Endgültige `body_height` für HW
  - Endgültige Velocity/Acceleration-Limits
  - Servo-Strom-Schwellen
- Memory-Einträge für Cross-Phase-Themen
- Git-Commit + Tag `phase-13-done` im hexapod_ws
- `PHASE.md` markiert Phase 13 als abgeschlossen
- Retrospektive: was lief gut, was hat länger gedauert, was ist offen für
  Phase 13+

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Servo bewegt sich falsch herum (war in Phase 10 OK) | Servo-Kabel beim Umstecken vertauscht | Mapping-Tabelle gegen physische Verkabelung verifizieren |
| Beim Walk fällt der Roboter sofort um | Reibung Boden ↔ Foot-Link zu niedrig | Untergrund mit Anti-Rutsch (Gummi-Matte, Teppich) |
| Stand-Pose-Strom zu hoch | Mechanische Verspannung, schiefe Kalibrierung | Pro Bein einzeln nochmal Stufe-B-Verfahren |
| Watchdog feuert während Walk | Pi-Timing-Jitter, USB-Latenz | Watchdog-Timeout in Phase-7-Firmware lockerer (300 ms), Pi-Power-Save-Settings prüfen |
| Brown-out bei Bewegung | Bulk-Caps zu klein oder PSU-CC zu eng | Phase-8-Bulk-Caps prüfen, PSU-CC voll aufdrehen |
| Yaw-Drift > 15 ° / m | Einzel-Bein-Kalibrierung schief | Per-Bein-Stand-Pose verifizieren, gleichseitige Beine vergleichen |
| Servo-Temperatur > 60 °C nach < 10 min | Stand-Pose zwingt Servo in schweren Winkel | URDF-Body-Höhe / Stand-Pose-Geometrie verifizieren, Body-Höhe niedriger |
| Walk klappt aufgebockt aber stürzt am Boden | Foot-Trajektorie hebt nicht hoch genug | Phase-5-Gait-Param `swing_height` hoch, Phase-12-Param-Override |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Akku (Phase 13+)
- Keine neuen Gangarten (Wave, Ripple) — separate Phase
- Keine IMU/Sensor-Integration
- Kein Closed-Loop-Yaw-Korrektur
- Kein Bluetooth-PS4
- Keine echten Foot-Contact-Sensoren

---

## Konventions-Erweiterungen für `00_conventions.md`

In Stufe H ergänzen:
- HW-spezifischer `body_height` (z. B. -0,047)
- Velocity/Acceleration-Limits für HW
- Servo-Strom-Schwellen final
- Boot-Pose-Sequenz-Timing aus Phase 7
- Cross-Reference auf Phase-7-Firmware-Repo

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–H Done-Kriterien erfüllt
- [ ] **Alle 15 verbleibenden Servos per Auto-Cal-Tool kalibriert (Stufe B)**
- [ ] `servo_mapping.yaml` für alle 18 Pins `status: calibrated`
- [ ] Erster Walk auf Boden erfolgreich (Stufe F)
- [ ] PS4-Vollbetrieb wie Phase 6 (Stufe G)
- [ ] Limits hochgezogen (Stufe H)
- [ ] Yaw-Drift charakterisiert
- [ ] Strom-Profile dokumentiert
- [ ] Servo-Temperaturen dokumentiert
- [ ] `00_conventions.md` ergänzt
- [ ] Git-Commit + Tag `phase-13-done`
- [ ] `PHASE.md` aktualisiert (Phase 13 abgeschlossen)
- [ ] Retrospektive in `phase_13_progress.md`
