# Phase 12 — Voll-Bringup mit echtem Roboter

**Dauer-Schätzung:** 4–6 Tage (Kalenderzeit, viele Iterationen — inkl.
neuer Stufe B für SW-Auto-Kalibrierung der 15 in Phase 10 nicht
kalibrierten Servos)
**Maschine:** Raspberry Pi 4 am Roboter, Desktop für Monitoring/Teleop
**Vorbedingung:** Phase 11 abgeschlossen (Pi-Plattform steht), Phase 10
abgeschlossen (leg_6 = Pin 15/16/17 am Desktop kalibriert; die anderen
15 Servos sind in `servo_mapping.yaml` weiter Platzhalter und werden
**in Stufe B dieser Phase** per SW-Tool kalibriert)

---

## Ziel

Den vollen Hexapod-Stack auf dem Pi mit echter Hardware in Betrieb nehmen.
Reihenfolge: **15 verbleibende Servos per SW-Tool kalibrieren** → alle
18 Beine in Stand-Pose aufgebockt → Tripod in der Luft → Stand auf Boden
(Hängevorrichtung) → erster Walk → Phase-6-PS4-Vollbetrieb.

**Sicherheits-Schwerpunkt der Phase.** Jede Stufe hat einen
„Goldenen-Regeln"-Block, der **gelesen sein muss** bevor der Hauptschalter
zugeht.

---

## Hardware-Setup für diese Phase

- Pi am Roboter montiert oder in unmittelbarer Nähe
- Servo2040 am Pi per USB-C-Kabel (3 m XT60-Kabel reicht für Bench-Strom)
- Bench-PSU als Stromquelle (kein Akku)
- DCDC versorgt Pi
- leg_6 (Pin 15/16/17) bereits kalibriert in `servo_mapping.yaml` (aus
  Phase 10); die 15 verbleibenden Pins werden in **Stufe B dieser Phase**
  per SW-Auto-Cal-Tool kalibriert
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
2. **Alle 18 Servos in `servo_mapping.yaml` mit Status `calibrated` —
   15 davon per SW-Auto-Cal in Stufe B, leg_6 bereits aus Phase 10
   (Stufe B)**
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

### Stufe B — SW-Auto-Kalibrierung der 15 verbleibenden Servos

**Ziel:** Die 15 Servos in `servo_mapping.yaml`, die nach Phase 10 noch
Platzhalter sind (alles außer Pin 15/16/17 = leg_6), per SW-Tool über
den echten Plugin-→-Firmware-→-Servo-Pfad kalibrieren. Genauer als der
HJ-Tester in Phase 10, weil **gleiche PWM-Pipeline wie im
Produktiv-Betrieb** (kein Tester-vs-Stack-Drift) und **Self-Collision-
Test direkt mit beiden Nachbar-Beinen möglich**.

**Vorbedingung:** Stufe A grün (Plugin läuft auf Pi gegen Servo2040,
USB stabil, `STATE`-Frames kommen). Hexapod **aufgebockt**, alle 18
Servos montiert, alle 18 Servos elektrisch angeschlossen (im Gegensatz
zu Phase 10, wo nur leg_6 verkabelt war). Bench-PSU 7.0 V, CC-Limit
großzügig (Cal-Tool bewegt nur 1 Bein gleichzeitig + 2 Referenz-Beine
passiv).

**Begründung (cross-ref Phase-10-Stage-B Strategie B'):** Phase 10
hat für leg_6 mit dem HJ-Tester die `pulse_min`/`max`/`zero`-Werte
ermittelt — funktioniert für 3 Servos, skaliert aber schlecht auf 15.
Auto-Cal-Tool nutzt die **selbe Pulse-Hard-Stop-Strategie**
(Self-Collision-sichere Hardware-Anschläge mit 5° Sicherheits-Abstand
zu Nachbar-Beinen), automatisiert aber den Mess-Vorgang über die
Stack-Pipeline.

#### B.1 Architektur-Entscheidung (vor Implementation)

| Frage | Vorschlag | Verworfen | Begründung |
|---|---|---|---|
| **Wo lebt das Tool?** | Neues Python-Paket `hexapod_calibration` oder Skript-Unterordner in `hexapod_hardware` | Plugin-Erweiterung (C++) | Tool nutzt das bestehende Plugin als Black Box (Pulse rein, Bewegung raus), keine Plugin-Code-Änderung nötig — schneller zu bauen + testen, niedriger Wartungsaufwand |
| **Wie sendet das Tool Pulse?** | Direkt per `forward_position_controller` (Joint-Position-Goals in rad, Plugin macht rad→pulse-Konvertierung) **oder** Roh-Pulse über einen Cal-Mode im Plugin | Plugin-Cal-Mode | Roh-Pulse über Cal-Mode wäre Plugin-Code-Change. Stattdessen: Tool sendet rad-Goals mit Test-`pulse_per_rad`-Schätzung, iteriert. Genaue Werte werden über Δrad↔Δpulse-Beobachtung am realen Bein zurückgerechnet. |
| **User-Interface** | Terminal-Tastatur: `←`/`→` für ±5 µs, `Enter` = „das ist die Grenze", `q` = abbrechen, `n` = next servo | Vollautomatisch (Encoder-Feedback) | Encoder gibt's nicht (Echo-State). Mensch im Loop ist Pflicht, weil visuelle Self-Collision-Beurteilung nicht ohne Sensorik geht. |
| **Reihenfolge der Servos** | leg-für-leg, pro Bein Coxa → Femur → Tibia (analog Phase-10-Stage-B-C-D-E) | Alle Coxas zuerst, dann alle Femurs, dann alle Tibias | Pro-Bein-Reihenfolge erlaubt Stand-Pose-Snapshot nach jedem Bein als Sanity-Check; Alle-Coxas-zuerst macht keinen Stand möglich. |
| **Self-Collision-Test pro Coxa** | Beide Nachbar-Beine in worst-case-Pose schwenken, Cal-Tool fährt aktives Bein langsam ran bis User „Enter" drückt 5° vor Berührung | Nur einseitiger Test wie in Phase 10 | Mittel-Beine (leg_2, leg_5) haben **zwei** Nachbarn — beide müssen begrenzt werden. Phase 10 leg_6 hat nur leg_5 als Nachbar (Eck-Bein). |

#### B.2 Tool-Funktions-Skizze (Pseudo-Code, ~150 Zeilen)

```python
# tools/auto_calibrate.py
#
# Usage:
#   ros2 run hexapod_calibration auto_calibrate \
#       --leg leg_2 --joint coxa
#
# Schritte:
#   1. Lade servo_mapping.yaml, finde Pin für (leg, joint)
#   2. Sende JTC-Goal zur erwarteten Joint-Mitte (Default-`pulse_zero` 1500 µs
#      → über `pulse_per_rad`-Schätzung in rad umrechnen)
#   3. User-Loop:
#      ←/→ = Trim ±5 µs, Bein-Verhalten beobachten
#      Enter (PHASE 1) = „das ist visuelle Joint-Mitte" → pulse_zero gespeichert
#   4. Sende inkrementelle Goals Richtung -1.5 rad (Self-Collision-Seite)
#      User-Loop:
#      Visuell beurteilen wie nah Bein dem Nachbar-Bein kommt
#      Enter (PHASE 2) = „STOP, 5° vor Berührung" → pulse_min gespeichert
#   5. Analog Richtung +1.5 rad
#      Enter (PHASE 3) = pulse_max gespeichert
#   6. YAML-Update: schreibe Pin-Eintrag mit pulse_min/zero/max + direction +
#      status: calibrated + calibrated_at: <ISO>
#   7. Backup vorheriges YAML als .bak.<timestamp>
```

#### B.3 Pre-Cal-Vorbereitung pro Bein

Pro Bein vor dem Auto-Cal-Run:

1. **PSU AUS**, Bein-Mechanik prüfen (Schrauben fest, Kabel ohne Spannung,
   Servos können sich frei drehen)
2. **Nachbar-Beine in worst-case-Pose** schwenken:
   - Eck-Beine (leg_1, leg_3, leg_4, leg_6): nur **ein** Nachbar (Mittel-Bein)
     in worst-case
   - Mittel-Beine (leg_2, leg_5): **beide** Nachbarn (Eck-Beine) in worst-case
3. Friction-Check: bleiben Nachbar-Beine ohne Strom in worst-case-Pose?
   - Falls Servo zurückrutscht: Klebeband oder Schaumstoff temporär
4. **PSU AN**, Plugin läuft (aus Stufe A), aktives Bein per User-Hand
   in geometrische Mitte gehalten (Initial-Pulse-Mitigation analog
   Phase-10-Stages-C/D/E — Memory `project_phase12_initial_pose_presets.md`
   ist Cross-Phase-Outlook, in B nicht implementiert)

#### B.4 Auto-Cal-Run pro Joint

Erwartete Dauer pro Joint: ~3 min (vs. ~10 min HJ-Tester in Phase 10).
15 Joints × 3 min ≈ 45 min reine Mess-Zeit + ~30 min Bein-Vorbereitung
pro Bein-Wechsel.

Reihenfolge: **leg_1 → leg_2 → leg_3 → leg_4 → leg_5** (Coxa → Femur →
Tibia jeweils).

Pro Joint (User-Workflow):
1. Auto-Cal-Tool starten mit `--leg leg_X --joint <coxa|femur|tibia>`
2. Phase 1 (`pulse_zero`): visuelle Joint-Mitte mit `←`/`→` finden,
   `Enter`
3. Phase 2 (`pulse_min`): langsam Richtung Self-Collision/mech. Anschlag
   trimmen, `Enter` 5° vor Grenze
4. Phase 3 (`pulse_max`): analog Phase 2 in andere Richtung
5. Phase 4 (`direction`-Beobachtung): Tool fragt „Bein dreht in
   URDF-positive Richtung beim positiven Trim? y/n" — bei n flipt
   Tool `direction: -1` direkt im YAML
6. Tool schreibt YAML, fertig

#### B.5 Plausibilitäts-Validation am Ende von Stufe B

Nach allen 15 Joints kalibriert:
- `servo_mapping.yaml` enthält für alle 18 Pins `status: calibrated`
- Pro Pin: `pulse_min < pulse_zero < pulse_max`, alle in [800, 2200] µs
- Stand-Pose-Sanity-Test aufgebockt (alle 18 fahren in Joint-Mitte) —
  visuell symmetrische Pose, kein Servo brummt am Anschlag

#### B.6 Tool-Implementation: was muss neu gebaut werden

- **Neues Paket** `hexapod_calibration` (Python, ament_python)
- **Node** `auto_calibrate` (~150 Zeilen Python)
- **YAML-Schema bleibt unverändert** — Tool schreibt in bestehendes
  Format
- **Code-Anpassungen am Plugin oder Firmware:** **keine**

Tool-Test-Strategie (vor B.3 am echten Bein):
- Unit-Tests für YAML-Read/Write + Plausibilitäts-Check
- Smoke-Test mit Loopback-Mode (`real.launch.py loopback:=true`) —
  Tool sendet Goals, Plugin echo't zurück, Tool validiert dass
  YAML-Write korrekt ist

**Done-Kriterium B:**
1. `hexapod_calibration`-Paket existiert, Build grün, Unit-Tests grün
2. Smoke-Test im Loopback-Mode bestanden (Tool kann YAML lesen +
   schreiben + Goals senden)
3. Alle 15 verbleibenden Servos durchkalibriert, YAML für alle 18 Pins
   hat `status: calibrated`
4. Stand-Pose-Sanity aufgebockt symmetrisch
5. Cal-Log pro Bein (analog `phase_10_stage_b_calibration_log.md`):
   `phase_12_stage_b_calibration_log.md` mit allen 15 Mess-Eintragungen
   als Audit-Trail

---

### Stufe C — Stand-Pose alle 18 aufgebockt

**Ziel:** Erstmaliger Voll-Stand, aufgebockt. Erster echter Stresstest
der Boot-Sequenz.

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

### Stufe D — Tripod-Cycle aufgebockt

**Ziel:** Vollständiger Tripod-Cycle, drei Beine schwingen, drei „stützen"
(in der Luft, ohne Last). Synchronität verifizieren.

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

Wert in `phase_12_progress.md` festhalten.

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
- [ ] Git-Commit + Tag `phase-12-done`
- [ ] `PHASE.md` aktualisiert (Phase 12 abgeschlossen)
- [ ] Retrospektive in `phase_12_progress.md`
