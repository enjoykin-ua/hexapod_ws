# Phase 12 — Voll-Bringup mit echtem Roboter

**Dauer-Schätzung:** 3–5 Tage (Kalenderzeit, viele Iterationen)
**Maschine:** Raspberry Pi 4 am Roboter, Desktop für Monitoring/Teleop
**Vorbedingung:** Phase 11 abgeschlossen (Pi-Plattform steht), Phase 10
abgeschlossen (alle 18 Servos am Desktop kalibriert)

---

## Ziel

Den vollen Hexapod-Stack auf dem Pi mit echter Hardware in Betrieb nehmen.
Reihenfolge: alle 18 Beine in Stand-Pose aufgebockt → Tripod in der Luft
→ Stand auf Boden (Hängevorrichtung) → erster Walk → Phase-6-PS4-Vollbetrieb.

**Sicherheits-Schwerpunkt der Phase.** Jede Stufe hat einen
„Goldenen-Regeln"-Block, der **gelesen sein muss** bevor der Hauptschalter
zugeht.

---

## Hardware-Setup für diese Phase

- Pi am Roboter montiert oder in unmittelbarer Nähe
- Servo2040 am Pi per USB-C-Kabel (3 m XT60-Kabel reicht für Bench-Strom)
- Bench-PSU als Stromquelle (kein Akku)
- DCDC versorgt Pi
- Alle 6 Beine kalibriert in `servo_mapping.yaml` (aus Phase 10)
- Hängevorrichtung über dem Roboter (Seil/Gurt durch Body-Aufhängung, an
  Decken-Haken oder Stativ)
- PS4-Controller (USB)
- Notebook am SSH-Terminal für Live-Diagnose

---

## Sicherheits-Recap (CLAUDE.md §9 + Phase 7 Sicherheits-Ebenen)

- **Aufgebockt** bis Stufe E
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

1. Servo2040 hängt am Pi (USB), `hexapod_hardware` läuft auf Pi
2. Stand-Pose alle 18 aufgebockt stabil > 5 min (Stufe B)
3. Tripod-Cycle aufgebockt sichtbar synchron (Stufe C)
4. Stand-Pose mit Bodenkontakt > 30 s stabil, Hängevorrichtung trägt
   nicht (Stufe D)
5. Mindestens 1 m Walk geradeaus ohne Eingriff, Hängevorrichtung trägt
   nicht (Stufe E)
6. PS4-Vollbetrieb wie Phase 6, alle Modi aus Phase-5-Stufe-H funktional
   (Stufe F)
7. Limits hochgezogen auf Phase-5/6-Werte (Stufe G)
8. Yaw-Drift charakterisiert und dokumentiert (Stufe G)
9. Phase-Abschluss-Doku komplett (Stufe H)

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

### Stufe B — Stand-Pose alle 18 aufgebockt

**Ziel:** Erstmaliger Voll-Stand, aufgebockt. Erster echter Stresstest
der Boot-Sequenz.

#### B.1 Vorbereitung

- Roboter **aufgebockt**, Beine in der Luft
- Beine manuell in **ungefähre Stand-Pose** vorpositionieren (reduziert
  Anlauf-Wege beim Enable)
- PSU **aus**
- Pi an, `real.launch.py loopback:=false` läuft, **kein** `cmd_vel`-Eingang

#### B.2 Power-On

1. **Schaue auf die Beine, nicht auf das Terminal.**
2. Hand am PSU-Aus-Knopf.
3. PSU einschalten → Servo2040 boot-Sequenz feuert
4. Beine fahren gestaffelt (aus Phase 7 Stufe D) in Stand-Pose
5. **Wenn ein Bein in falsche Richtung fährt:** PSU sofort aus,
   Kalibrierung prüfen
6. **Wenn alles gut:** 5 min in Stand-Pose halten

#### B.3 Stand-Pose-Stabilität

In separatem SSH-Terminal:

```bash
ros2 topic echo /joint_states --field effort
# Stromwerte pro Joint (Effort-Interface = Current-Sense)
```

Beobachten:
- Statische Stromwerte pro Servo: wenige hundert mA, < 80 % Stallstrom
- Body-Pose visuell symmetrisch
- Kein hörbares Zucken / Vibrieren

#### B.4 Body-Höhe-Korrektur

Default in `gait_node` ist `body_height = -0.052` (Sim-Workaround).
**Für echte HW: -0.047** (siehe Phase-6-Übergabe in PHASE.md).

Per LaunchArg oder direkt im YAML setzen, vor `real.launch.py`-Start.

**Done-Kriterium B:**
1. Boot-Sequenz: Beine fahren gestaffelt ohne Stalls
2. Stand-Pose visuell symmetrisch
3. Strom-Mittelwert pro Servo < 80 % Stall
4. 5 min stabil, keine Trips
5. `body_height` auf -0,047 umgestellt für HW

---

### Stufe C — Tripod-Cycle aufgebockt

**Ziel:** Vollständiger Tripod-Cycle, drei Beine schwingen, drei „stützen"
(in der Luft, ohne Last). Synchronität verifizieren.

#### C.1 Foot-Contact deaktivieren

`gait_node` erwartet in Sim die `/foot_contact_*`-Topics von Gazebo. Auf
echter HW gibt's diese Sensoren nicht.

Param `enable_foot_contact:=false` setzen. State-Machine läuft dann rein
zeitgesteuert (siehe Phase-5-Stufe-G-Logik).

Per LaunchArg oder als gait-Param-YAML.

#### C.2 Schwenk-Test

In einem Terminal:
```bash
ros2 topic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}, angular: {z: 0.0}}'
```

Erwartung:
- Drei Beine schwingen (Tripod A), drei stehen (Tripod B), dann Wechsel
- Sieht symmetrisch aus? Trajektorien glatt?
- Echte Servos haben keinen JTC-Tracking-Lag — Bewegung sollte **glatter**
  aussehen als Sim

#### C.3 Omnidirektional

`linear.y`, `angular.z`, Kombinationen. Alle Phase-5-Stufe-H-Modi
durchprobieren — in der Luft.

#### C.4 Strom-Profil unter Walk-in-Luft

5 min Walk-Cycle laufen lassen. Strom pro Servo loggen:

```bash
ros2 bag record /joint_states /cmd_vel
```

Bag später analysieren. Spitzen sollten nicht > 80 % Stall.

**Done-Kriterium C:**
1. Tripod-Cycle sichtbar synchron in der Luft
2. Omnidirektional alle Modi funktional
3. 5 min Walk-in-Luft ohne Trips
4. Strom-Profil dokumentiert

---

### Stufe D — Stand-Pose auf Boden (Hängevorrichtung sichert)

**Ziel:** Roboter vom Bock auf Boden, aber **mit Hängevorrichtung** über
ihm. Stand trägt sich selbst, Hängevorrichtung darf den Roboter **nicht**
hochziehen — sie ist nur Sturz-Schutz.

#### D.1 Hängevorrichtung

- Seil/Gurt durch Body-Aufhängung
- An Decken-Haken oder stabilem Stativ befestigt
- Länge so eingestellt, dass Roboter den Boden gerade berührt
- **Hand drauf:** kann den Roboter bei Bedarf hochheben

#### D.2 Stand-Pose mit Last

`gait_node` in STANDING-State, `cmd_vel = (0, 0, 0)`. Roboter trägt sein
eigenes Gewicht.

Beobachten:
- Trägt der Femur-Servo das halbe Roboter-Gewicht?
- Erwartete Stromwerte pro Femur-Servo: **deutlich höher als aufgebockt**,
  1–2 A statisch realistisch
- Wenn deutlich höher: Servo arbeitet gegen sich selbst (Kalibrierungs-
  Fehler) oder mechanische Verspannung. Zurück zu Stufe B.

#### D.3 Stand-Pose-Dauer

5 min Stand mit Bodenkontakt:
- Sinkt der Body merklich? (= Servo-Droop, akzeptabel wenn < 5 mm)
- Werden Servos heiß? (Hand an Gehäuse, oder IR-Thermometer; > 60 °C ist
  Alarm)

**Done-Kriterium D:**
1. Stand mit Bodenkontakt > 30 s stabil
2. Hängevorrichtung trägt nicht
3. Stromwerte pro Servo in plausiblem Bereich, < 80 % Stall
4. Servo-Temperaturen < 60 °C nach 5 min Stand

---

### Stufe E — Erster Walk auf Boden

**Ziel:** Erste echte Schritte. Klein anfangen.

#### E.1 Minimaler Walk

Per PS4 (mit R1-Dead-Man): D-Pad ↑ kurz drücken, `cmd_vel.linear.x = 0,02 m/s`.

Roboter macht **einen Schritt**, vielleicht zwei. Dann loslassen.

Beobachten:
- Tracking visuell OK? (Beine landen wo erwartet?)
- Yaw-Drift sichtbar?
- Stürzt der Roboter? (Hängevorrichtung fängt ab — kein Schaden)
- Strom-Spitzen, die Limits triggern?

**Bei Sturz:** nicht in Panik mehr Code schreiben. Erst analysieren
(Stromlog, Video, was war zuerst).

#### E.2 Schrittweise verlängern

Wenn 1 Schritt OK: 2 Schritte. Dann 5. Dann 1 m geradeaus.

#### E.3 Yaw-Drift charakterisieren

Bei 1 m geradeaus: wie viel Grad Yaw-Drift?
- < 5 °: super
- 5–15 °: typisch bei Hexapod ohne IMU
- > 15 °: Kalibrierungs-Verdacht, Bein-spezifischen Drift suchen

Wert in `phase_12_progress.md` festhalten.

**Done-Kriterium E:**
1. Mindestens 1 m geradeaus ohne Eingriff
2. Hängevorrichtung wurde nicht gebraucht
3. Keine Strom-Limit-Trips
4. Yaw-Drift dokumentiert

---

### Stufe F — PS4-Vollbetrieb wie Phase 6

**Ziel:** Alle Phase-6-Funktionen auf echter HW.

#### F.1 Standard-Bewegung

- D-Pad ↑ / ↓ / ← / → für vor/zurück und Drehung am Stand
- R1 als Dead-Man (Pflicht)
- L2/R2 für Body-Lift (nur im STANDING-State)

#### F.2 Sturz-Vermeidung

- Hängevorrichtung weiter aktiv
- Schrittweise Tests, nicht direkt Vollausschlag
- Bei jeder neuen Modus-Kombination: erstmal aufgebockt verifizieren,
  dann auf Boden

#### F.3 Omnidirektional auf Boden

`linear.y`-Anteil, `angular.z`-Anteil, Kombinationen.

**Done-Kriterium F:**
1. PS4-Vollbetrieb wie Phase 6 funktional
2. Omnidirektional auf Boden in alle Richtungen
3. Body-Lift im STANDING-State funktioniert

---

### Stufe G — Limits hochziehen + Tuning

**Ziel:** `controllers.real.yaml`-Limits Schritt für Schritt von 30 % auf
Phase-5/6-Sim-Werte hochziehen.

#### G.1 Schritt-für-Schritt

- `max_linear_x`: 0,02 → 0,05 → 0,10 → Phase-5-Wert
- Nach jedem Step: aufgebockt → mit Hängevorrichtung → frei
- Auf Trips, Stalls, Stürze achten

#### G.2 Velocity/Acceleration-Limits

`controllers.real.yaml` schrittweise lockern. Vergleich zur Sim — die Sim
hatte schon „funktioniert"-Werte, also sind das die Obergrenzen.

#### G.3 Soft-Ramp in Firmware anpassen?

Wenn JTC-Trajectories sauberer fahren als die Soft-Ramp es zulässt: in
Phase-7-Firmware `MAX_DELTA_PER_TICK` hochsetzen. Sicherheits-Buffer
behalten, aber nicht künstlich limitieren.

**Done-Kriterium G:**
1. Limits auf Phase-5/6-Werte hochgezogen
2. Kein Servo-Strom-Limit unter normalem Betrieb
3. Yaw-Drift bei vollem Walking dokumentiert

---

### Stufe H — Phase-12-Abschluss

- `phase_12_progress.md` finalisieren:
  - Strom-Profile pro Bewegungstyp
  - Yaw-Drift
  - Servo-Temperaturen
  - Foto/Video vom ersten Walk
- `00_conventions.md` ergänzen mit HW-spezifischen Werten:
  - Endgültige `body_height` für HW
  - Endgültige Velocity/Acceleration-Limits
  - Servo-Strom-Schwellen
- Memory-Einträge für Cross-Phase-Themen
- Git-Commit + Tag `phase-12-done` im hexapod_ws
- `PHASE.md` markiert Phase 12 als abgeschlossen
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

- [ ] Alle Stufen A–G Done-Kriterien erfüllt
- [ ] Erster Walk auf Boden erfolgreich (Stufe E)
- [ ] PS4-Vollbetrieb wie Phase 6 (Stufe F)
- [ ] Limits hochgezogen (Stufe G)
- [ ] Yaw-Drift charakterisiert
- [ ] Strom-Profile dokumentiert
- [ ] Servo-Temperaturen dokumentiert
- [ ] `00_conventions.md` ergänzt
- [ ] Git-Commit + Tag `phase-12-done`
- [ ] `PHASE.md` aktualisiert (Phase 12 abgeschlossen)
- [ ] Retrospektive in `phase_12_progress.md`
