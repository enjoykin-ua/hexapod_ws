# Servo-Real-Calibration — Plan & Todos

> **Status (2026-05-21 Ende):**
> - ✅ **Cal-Phasen 1 + 2 abgeschlossen** für alle 18 Servos (siehe
>   Sektion „Cal-Session-Results" unten)
> - ⏳ **Phase 3+ noch offen:** URDF-Macro-Refactoring (Code-Change),
>   servo_mapping.yaml-Übertragung, Sim-Verifikation, Direction-Cal,
>   Hardware-Walking-Test
> - User hat die PWM-Werte komplett ausgemessen, Findings dokumentiert
>   und ist ready für die Plugin/URDF-Übertragung im nächsten Chat
>
> **Hintergrund:** Diese Doku entstand aus einer Diskussion in Phase
> 11 (rqt-Live-Cal-Tooling abgeschlossen 2026-05-21). User hat das
> bisherige Cal-Konzept aus
> [`docs_raspi/servo_calibration_approach.md`](servo_calibration_approach.md)
> als konzeptionell unvollständig erkannt — es fehlt die saubere
> Math zwischen PWM und Joint-Winkel wenn Cal auf mech-Stops basiert
> (statt auf URDF-Hardwarelimits). Cal-Werte wurden anschließend
> entsprechend dem überarbeiteten Konzept (Weg B in Sektion 3)
> systematisch gemessen.

---

## 1. Ziel

Sauber-konsistente Cal aller 18 Servos im realen Hexapod sodass:

1. **Cal-Werte** (`pulse_min`/`pulse_zero`/`pulse_max` pro Servo) auf den
   mechanischen Anschlägen oder Self-Collision-Grenzen basieren — NICHT
   auf der theoretischen Servo-Hardware-Range
2. **URDF-Joint-Limits** (`joint_lower`/`joint_upper` pro Joint) auf die
   echte erreichbare rad-Range gesetzt sind — NICHT pauschal auf ±1.57
3. **Math konsistent:** wenn IK rad=+0.5 kommandiert, geht der Servo
   physisch genau dorthin (statt auf einen skalierten Bruchteil)
4. **Walking funktioniert** im Sim UND auf echter Hardware mit gleicher
   Bein-Geometrie/Bewegungs-Charakteristik

## 2. Wieso — das Problem im aktuellen System

Aktueller Stand:
- `servo_mapping.yaml` hat Phase-10-Cal für leg_6 (Pin 15-17) — mit
  pulse_min/zero/max die dem mech-Stop bzw. Self-Collision-Grenze
  entsprechen (z.B. leg_6_coxa: 1280/1550/1860)
- URDF hat einheitliche Joint-Limits ±1.57 rad für Coxa/Femur, ±1.50
  für Tibia (siehe `docs/00_conventions.md` §11.4)
- **Inkonsistenz:** Plugin nimmt an dass pulse_max ↔ joint_upper=+1.57
  rad ist, aber physisch entspricht pulse_max nur z.B. +60° (nicht 90°)
- **Konsequenz:** IK-Math + gait_engine planen mit rad-Werten die nicht
  zur Hardware-Realität passen → Foot-Position falsch berechnet →
  Walking unsauber oder gar nicht möglich

Phase 10 ist damit „durchgekommen" weil nur leg_6 für isolierte
Single-Leg-Tests kalibriert war. Bei Full-Hexapod-Cal mit
Self-Collision-Schutz bricht die Math-Konvention zusammen.

User-Beobachtung 2026-05-21 die das aufgedeckt hat: leg_5_coxa Cal mit
pulse_min=1350, pulse_zero=1500, pulse_max=1650 → Servo dreht visuell
nur ~30° (statt ±90° wie URDF annimmt). Sample-Math:
- (1650−1500) × 0.00236 rad/µs ≈ +0.35 rad ≈ +20° (statt erwartet ±90°)
- Faktor ~4-5× kompressiert in der Plugin-Math

→ Hexapod würde "denken" er macht große Bewegungen, physisch aber
viel kleinere.

## 3. Wozu — Strategie-Wahl

Drei Lösungswege wurden diskutiert:

| Weg | Was | Empfehlung |
|---|---|---|
| **A** Status quo akzeptieren (Phase-10-Pattern) — Cal auf mech-Stop, URDF unverändert | Bewusste Math-Inkonsistenz, `step_length_max` muss klein gewählt werden | ❌ unehrlich, langfristig problematisch |
| **B** URDF-Limits pro Joint anpassen — Cal-Werte UND URDF beide auf echte Hardware-Realität | Konsistente Math, IK plant innerhalb echter Range, **kein Plugin-Code-Change** | ✅ **gewählt** (User-Entscheidung 2026-05-21) |
| **C** Cal-Schema erweitern (rad_min/rad_max pro Servo in YAML) | Cal self-contained, aber **Plugin-Code-Change** + IK/URDF-Integration unklar | ❌ zu viel Aufwand für initial nicht-fundamentaler Vorteil |

**Gewählt: Weg B** — Cal-Werte UND URDF synchron auf reale Hardware
kalibrieren.

## 3.5 Cal-Session-Results (2026-05-21)

User hat Cal-Phasen 1 + 2 für alle 18 Servos durchgeführt. Ergebnisse:

### 3.5.1 µs/°-Konstante (Phase-1-Ergebnis)

**Validated über alle 18 Servos:** ~7.32 µs/° (= **0.00237 rad/µs**)

- Coxa Mittel: 7.32 µs/°
- Femur Mittel: 7.31 µs/°
- Tibia Mittel: 7.37 µs/°
- Streuung: ±3% (= Servo-Toleranz, völlig normal)

Sehr nah am Datenblatt-Wert 7.36 µs/° für 270°-Servos (Diymore +
Miuzei). Cross-Check beider Servo-Typen erfolgreich. **Konstante
0.00237 rad/µs für alle 18 Servos verwendbar.**

### 3.5.2 PWM-Werte für servo_mapping.yaml (numerisch, Plugin-Format)

**Pulse-Werte (numerisch sortiert für Plugin: `pulse_min < pulse_zero < pulse_max`):**

| Pin | Joint | pulse_min | pulse_zero | pulse_max |
|---|---|---|---|---|
| 0 | leg_1_coxa | 1145 | 1460 | 1700 |
| 1 | leg_1_femur | 815 | 1460 | 2120 |
| 2 | leg_1_tibia | 870 | 1680 | 2185 |
| 3 | leg_2_coxa | 1375 | 1575 | 1750 |
| 4 | leg_2_femur | 880 | 1550 | 2190 |
| 5 | leg_2_tibia | 860 | 1370 | 2200 |
| 6 | leg_3_coxa | 1200 ⚠️ | 1410 | 1745 |
| 7 | leg_3_femur | 800 | 1445 | 2100 |
| 8 | leg_3_tibia | 790 | 1620 | 2120 |
| 9 | leg_4_coxa | 1200 | 1520 | 1700 |
| 10 | leg_4_femur | 870 | 1560 | 2190 |
| 11 | leg_4_tibia | 815 | 1320 | 2140 |
| 12 | leg_5_coxa | 1300 | 1500 | 1700 |
| 13 | leg_5_femur | 860 | 1530 | 2190 |
| 14 | leg_5_tibia | 885 | 1720 | 2210 |
| 15 | leg_6_coxa | 1290 | 1530 | 1870 |
| 16 | leg_6_femur | 840 | 1540 | 2170 |
| 17 | leg_6_tibia | 850 | 1340 | 2170 |

⚠️ **leg_3_coxa pulse_min = 1200** war in User-Notiz mit „vielleicht"
markiert — Unsicherheit, sollte ggf. nachverifiziert werden bevor
Phase 3.

### 3.5.3 rad-Limits für URDF (berechnet mit rad_per_µs = 0.00237)

**Berechnungsformel:**
- `joint_upper = (pulse_max − pulse_zero) × 0.00237`
- `joint_lower = (pulse_min − pulse_zero) × 0.00237`

**WICHTIG:** diese Werte sind **PWM-zentrisch** (= ohne
direction_normal-Berücksichtigung). Wenn ein Bein im Direction-Cal
direction_normal=-1 bekommt, müssen die rad-Limits **gespiegelt**
eingetragen werden (siehe Finding 3.5.5).

| Pin | Joint | joint_lower | joint_upper |
|---|---|---|---|
| 0 | leg_1_coxa | -0.747 | +0.569 |
| 1 | leg_1_femur | -1.529 | +1.565 |
| 2 | leg_1_tibia | -1.920 | +1.197 |
| 3 | leg_2_coxa | -0.474 | +0.415 |
| 4 | leg_2_femur | -1.588 | +1.517 |
| 5 | leg_2_tibia | -1.209 | +1.967 |
| 6 | leg_3_coxa | -0.498 | +0.794 |
| 7 | leg_3_femur | -1.529 | +1.553 |
| 8 | leg_3_tibia | -1.967 | +1.185 |
| 9 | leg_4_coxa | -0.758 | +0.427 |
| 10 | leg_4_femur | -1.636 | +1.493 |
| 11 | leg_4_tibia | -1.197 | +1.943 |
| 12 | leg_5_coxa | -0.474 | +0.474 |
| 13 | leg_5_femur | -1.588 | +1.564 |
| 14 | leg_5_tibia | -1.979 | +1.161 |
| 15 | leg_6_coxa | -0.569 | +0.806 |
| 16 | leg_6_femur | -1.659 | +1.493 |
| 17 | leg_6_tibia | -1.161 | +1.967 |

### 3.5.4 „save start position" Daten (für Phase-13-Initial-Pose)

User hat pro Bein eine sichere Anfahr-Position für Femur + Tibia
notiert (Bein hängend nach unten, Self-Collision-frei). Aktuell nicht
Plugin-relevant, aber Vorbereitung für Phase-13-Initial-Pose-Presets
(siehe Memory `project_phase13_initial_pose_presets.md`).

| Pin | Joint | save_start_pwm | Bedeutung |
|---|---|---|---|
| 1 | leg_1_femur | 815 | Bein hängt nach unten |
| 2 | leg_1_tibia | 870 (femur bei 815) | Bein 90° zu Boden |
| 4 | leg_2_femur | 2190 | Bein hängend, Mount-Spiegel-Konvention |
| 5 | leg_2_tibia | 2200 (femur bei 2190) | analog |
| 7 | leg_3_femur | 800 | Bein hängend |
| 8 | leg_3_tibia | 790 (femur bei 800) | analog |
| 10 | leg_4_femur | 2190 | Mount-Spiegel-Konvention |
| 11 | leg_4_tibia | 2140 (femur bei 2190) | analog |
| 13 | leg_5_femur | 860 | Bein hängend |
| 14 | leg_5_tibia | 885 (femur bei 860) | analog |
| 16 | leg_6_femur | 2170 | Mount-Spiegel-Konvention |
| 17 | leg_6_tibia | 2170 (femur bei 2170) | analog |

→ Für Phase-13-Implementation: diese 12 PWM-Werte (Femur + Tibia pro
Bein) ergeben zusammen mit pulse_zero für Coxa eine sichere
„hängende Initial-Pose" für den aufgebockten Hexapod.

### 3.5.5 Findings aus der Cal-Session

**1. Mount-Versatz Tibia ist links/rechts gespiegelt (mit 2 Outliern):**

Differenz (Bein-0°) − (Servo-0°) für Tibia:
- Rechte Beine (leg_1, 3): +155, +160 µs (positiver Versatz)
- Linke Beine (leg_4, 6): −160, −155 µs (negativer Versatz)
- **Outlier leg_2 (rechts):** −170 µs (Mount-180°-verdreht?)
- **Outlier leg_5 (links):** +140 µs (Mount-180°-verdreht?)

Konsequenz: Tibia-direction wird pro Bein im Direction-Cal individuell
bestimmt werden müssen — nicht nur „alle linken Beine = direction=-1".

**2. Femur-Direction nicht systematisch pro Bein-Seite:**

Auf welcher Servo-Drehrichtung „Bein nach oben" entspricht:
- leg_1: +90° Servo → Bein zu Boden (Mount-Konv A)
- leg_2: +90° Servo → Bein nach oben (Mount-Konv B)
- leg_3: +90° Servo → Bein zu Boden (A)
- leg_4: +90° Servo → Bein nach oben (B)
- leg_5: +90° Servo → Bein nach unten (A)
- leg_6: +90° Servo → Bein nach unten (A)

→ Pro Bein-Mount individuell, kein systematisches Pattern.

**3. URDF-rad-Limits-Spiegelung für direction=-1-Beine:**

Die in Sektion 3.5.3 berechneten rad-Limits sind **PWM-zentrisch**
(direkt aus PWM-Δ). Wenn direction_normal=-1 für ein Bein, müssen
die URDF-Limits **gespiegelt** eingetragen werden:
- joint_lower und joint_upper Vorzeichen tauschen
- joint_lower und joint_upper Werte vertauschen

**Beispiel leg_6_tibia (vermutlich direction=-1 wegen Mount-Spiegel):**
- PWM-zentrisch: `joint_lower=-1.161, joint_upper=+1.967`
- URDF gespiegelt: `joint_lower=-1.967, joint_upper=+1.161`

Damit IK-Math konsistent ist: rad=+1.16 entspricht „Bein-Segment nach
oben" für beide Bein-Seiten.

**4. Range-Pair-Symmetrie bestätigt:**

| Pair | Coxa Range | Femur Range | Tibia Range |
|---|---|---|---|
| leg_1 ↔ leg_6 | 555 vs 580 µs ✓ | 1305 vs 1330 µs ✓ | 1315 vs 1320 µs ✓ |
| leg_2 ↔ leg_5 | 375 vs 400 µs ✓ | 1310 vs 1330 µs ✓ | 1340 vs 1325 µs ✓ |
| leg_3 ↔ leg_4 | 545 vs 500 µs ✓ | 1300 vs 1320 µs ✓ | 1330 vs 1325 µs ✓ |

Bein-Seiten sind sehr konsistent → Mechanik ist sauber gebaut.

**5. Mittel-Beine haben deutlich weniger Coxa-Range:**

- Eck-Beine (1, 3, 4, 6): ~70-80° Gesamt-Coxa-Range
- Mittel-Beine (2, 5): ~50° Gesamt-Coxa-Range

→ Physikalisch plausibel: Mittel-Beine haben Nachbarn auf BEIDEN
Seiten (vorne+hinten), mehr Self-Collision-Constraints. Für Walking:
`step_length_max` so wählen dass Mittel-Beine mitkommen.

**6. Plugin-Math-Limitation bei direction=-1 + asymmetrischer Cal:**

Bei Beinen mit `direction_normal=-1` UND asymmetrischer Cal (= meiste
hier!) ist `radians_to_pulse_us` nicht perfekt linear:
- Bei rad=+joint_upper geht Servo nicht ganz auf pulse_min
- Firmware clamped → kein Schaden, aber Servo erreicht nicht ganz die
  echte mech-Range
- IK-Math leicht inkonsistent zur Hardware-Position

Für ersten Walking-Test akzeptabel. Bei späterer Feinabstimmung (Phase
13+) müsste man entweder:
- a) Cal-Schema erweitern (Weg C aus Sektion 3)
- b) Plugin-Math mit per-Direction-Slope-Logic erweitern
- c) Akzeptieren (was wir jetzt machen)

**7. Naming-Konvention „min/max" verkehrt zur Plugin-Logik:**

User-Notation in Mess-Notizen:
- „mech min" = physikalische Richtung (z.B. „zu Bein 2") = oft
  NUMERISCH GRÖSSER
- „mech max" = andere Richtung = oft NUMERISCH KLEINER

Plugin braucht numerisch `pulse_min < pulse_zero < pulse_max`.

→ **Beim Eintragen ins servo_mapping.yaml die obige Tabelle 3.5.2
verwenden** (dort ist es bereits korrekt numerisch sortiert). Nicht
die User-Original-Notation direkt übernehmen.

### 3.5.6 Was im Cal-Session noch offen geblieben ist

1. **leg_3_coxa pulse_min = 1200** mit „vielleicht"-Markierung — vor
   Phase 3 nachverifizieren ob das wirklich der Self-Collision-Stop
   ist.
2. **direction_normal-Werte für alle 18 Pins** — komplett unbekannt,
   wird in Direction-Cal-Phase (= Phase 5 erweitert) festgestellt
3. **Verifikation Mount-Spiegel-Hypothese** für leg_2 + leg_5 Tibia
   (Outlier-Mount-Versatz) — wird Direction-Cal automatisch zeigen

## 4. Wie — Der 6-Phasen-Plan

### Phase 1 — Servo-Charakterisierung (ohne Last) ✅ ABGESCHLOSSEN

**Status:** User hat Phase 1 für alle 18 Servos durchgeführt
(2026-05-21). Ergebnis-Konstante: **0.00237 rad/µs** für alle Diymore
+ Miuzei Servos. Siehe Sektion 3.5.1 für Details.

**Ursprüngliches Ziel:** rad/µs-Konstante pro Servo-Typ messen (statt
Datenblatt annehmen).

**Setup:**
- Bein 2 + Bein 5 abmontieren → 6 Servos werden frei (Pin 3,4,5 +
  Pin 12,13,14): 2 Coxa, 2 Femur, 2 Tibia jeweils
- Servo-Horn drauf (oder anderes optisch-sichtbares Element auf der
  Servo-Welle)
- Plugin im real-Mode (NICHT loopback)

**Pro Servo:**
1. PWM auf Servo-Mitte (typisch 1500 µs):
   ```bash
   ros2 param set /hexapodsystem pin_<N>.pulse_zero 1500
   ```
   → Servo geht auf Mitte. Horn-Position notieren (Foto/Marker).
2. PWM auf z.B. 2000 µs:
   ```bash
   ros2 param set /hexapodsystem pin_<N>.pulse_zero 2000
   ```
   → Servo dreht. **Augenmaß:** ist das visuell eine 1/4-Drehung
   (90°)? Falls nicht: PWM-Wert ändern bis es visuell überzeugend
   +90° ist.
   → Notiere die ΔPWM für +90° (z.B. 470 µs wenn überzeugend bei 1970)
3. Analog für -90°-Seite: PWM z.B. auf 1000 µs.
4. Berechne pro Servo: `rad_per_µs = (π/2) / ΔPWM`

**Erwartung (Datenblatt-Spec):**
- Diymore 8120MG + Miuzei MS61 sind beide 270°-Servos
- 500-2500 µs = 270° = 4.712 rad
- → ~0.00236 rad/µs

**Cross-Check:**
- Die 2 Diymore-Coxas sollten konsistente Konstanten zeigen
- Die 4 Miuzei (Femur+Tibia) auch konsistent
- Falls weit auseinander → Servo-Toleranz oder Mess-Fehler, näher
  schauen

**Pragma:** wenn die 2 Cross-Check-Werte pro Typ ähnlich sind, gilt
die Konstante für alle 6 Coxas bzw. alle 12 Femur/Tibias. Nicht alle
18 einzeln charakterisieren nötig.

### Phase 2 — Mech-Stop-Cal (Beine montiert, Hexapod aufgebockt) ✅ ABGESCHLOSSEN

**Status:** User hat Phase 2 für alle 18 Servos durchgeführt
(2026-05-21). Alle PWM-Werte in Sektion 3.5.2, rad-Limits in
Sektion 3.5.3. Eine Unsicherheit: leg_3_coxa pulse_min „vielleicht
1200" — vor Phase 3 nachverifizieren.

**Ursprüngliches Ziel:** pulse_min/zero/max pro Servo bei real verbautem
Bein finden (Self-Collision-frei).

**Setup:**
- Bein 2 + Bein 5 wieder montiert (gesamter Hexapod komplett)
- **HEXAPOD AUFGEBOCKT** — Beine ohne Bodenkontakt (Sicherheit
  gegen falsche Pulse-Werte die Servos beschädigen könnten)
- Plugin im real-Mode

**Pro Servo (alle 18 nacheinander):**
1. Slider in rqt für `pin_<N>.pulse_zero` auf visuelle Stand-Pose-Mitte
   drehen → notieren als `pulse_zero` (= Bein zeigt radial nach außen
   für Coxa, neutral horizontal für Femur, gerade ausgestreckt für
   Tibia)
2. Slider in eine Richtung drehen bis mechanischer Anschlag oder
   Self-Collision (Bein berührt Nachbarbein/Body) → notieren +
   20 µs Reserve zurück = `pulse_max`
3. Analog andere Richtung → `pulse_min`
4. **Rechnen** mit rad_per_µs aus Phase 1:
   ```
   joint_upper = (pulse_max − pulse_zero) × rad_per_µs   (in rad)
   joint_lower = (pulse_min − pulse_zero) × rad_per_µs   (in rad)
   ```
5. Notiere alle vier Werte (pulse_min/zero/max + die zwei rad-Werte)
   pro Servo auf Papier / Spreadsheet

**Wichtig — zwei verschiedene „Nullpunkte":**
- Phase-1 „Servo-Mitte" (1500 µs typ.) = geometrisches Hardware-Zentrum
- Phase-2 `pulse_zero` = PWM bei Stand-Pose-Mitte (kann z.B. 1450 µs
  sein wegen Mount-Versatz)
- **Beide sind unterschiedlich.** Phase-1 liefert nur die Skala
  (rad/µs-Konstante), Phase-2 liefert den Anker (welcher PWM = URDF-0°)

### Phase 3 — Konfiguration speichern + URDF anpassen

**Schritt 3.1 — servo_mapping.yaml via /save_calibration:**
```bash
ros2 service call /save_calibration std_srvs/srv/Trigger
```
Schreibt die pulse_min/zero/max + direction in install-tree mit
Timestamp-Bak.

**Schritt 3.2 — install → src kopieren (sonst weg bei colcon build!):**
```bash
cp install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml \
   src/hexapod_hardware/config/servo_mapping.yaml
```

**Schritt 3.3 — URDF mit pro-Joint-Limits aktualisieren** ← **Code-
Änderung nötig, siehe Sektion 5:**
- Bein-Macro um pro-Joint-Limit-Args erweitert (vorher Code-Vorbedingung)
- Top-Level-URDF: für jedes der 6 Beine die 6 individuellen rad-Werte
  setzen (= insgesamt 18 verschiedene `joint_lower`/`joint_upper`)
- Aus Phase-2-Berechnungen direkt eintragen

**Schritt 3.4 — Rebuild + Plugin neu starten:**
```bash
colcon build --packages-select hexapod_description hexapod_hardware
pkill -9 -f "ros2|gait_node|rviz2|rqt"; sleep 4
ros2 launch hexapod_bringup real.launch.py
```

### Phase 4 — Sim-Verifikation

**Ziel:** vor Hardware-Walking sicherstellen dass die neue
Cal-Konfiguration in der Sim funktioniert (= URDF-Limits passen, IK
geht nicht out-of-reach beim Walking).

**Setup:**
- Plugin killen, Sim-Stack starten:
  ```bash
  ros2 launch hexapod_bringup sim.launch.py
  ros2 run rviz2 rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz
  ```

**Checks:**
1. **Visual:** Stand-Pose in RViz/Gazebo normal? Alle 6 Beine
   gleichmäßig radial nach außen? Keine verrenkten Joints?
2. **gait_node starten + langsam walking:**
   ```bash
   ros2 launch hexapod_gait gait.launch.py \
     params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
   ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
   ```
3. **IK-Errors prüfen:** gait_node-Terminal nach `IKError`-Logs
   scannen. **Wenn welche** → URDF-Limits zu eng oder pulse_zero
   falsch → Phase-2-Wert nachjustieren
4. **Walking sieht stabil aus** in Sim → Phase 5 starten

### Phase 5 — Hardware-Verifikation (schrittweise, aufgebockt!)

**Schritt 5.1 — Ein Joint hin/her:**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  trajectory_msgs/msg/JointTrajectory \
  '{joint_names: ["leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint"],
    points: [{positions: [0.3, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```
Servo dreht? Smooth? Kein mech-Stop-Surren?

**Schritt 5.2 — Zurück auf 0, dann andere Richtung:**
```bash
ros2 topic pub --once /leg_6_controller/joint_trajectory \
  ... positions: [-0.3, 0.0, 0.0] ...
```

**Schritt 5.3 — 1 ganzes Bein (alle 3 Joints koordiniert):**
```bash
... positions: [0.2, 0.5, -0.5] ...
```

**Schritt 5.4 — Mehrere Beine simultan** (vorsichtig, weil
Drehmoment-Gesamtbelastung steigt):
Beine sollten nicht plötzlich abnormal springen, keine
mech-Stop-Geräusche, keine IK-Errors im Logger.

### Phase 6 — Gait gehen lassen (immer noch aufgebockt!)

```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

Alle 6 Beine bewegen sich in Tripod-Gait. Bei aufgebocktem Hexapod
sieht man die Schwung/Stance-Bewegung in der Luft. Visuelle Kontrolle:
- Beine wechseln im Tripod-Rhythmus
- Keine Selbstkollisionen
- Keine IK-Errors im gait_node-Terminal
- Servos arbeiten gleichmäßig (kein einzelner Servo der zittert oder
  surrt)

Tempo schrittweise erhöhen (`linear.x` 0.02 → 0.04 → 0.05).

**Erst NACH erfolgreichem Aufgebockt-Walking:** Hexapod absetzen
und bodengebundenen Walking-Test machen.

## 5. Code-Änderungen die VOR Cal-Session gemacht werden müssen

### URDF-Bein-Macro erweitern für pro-Joint-Limits

**Aktueller Stand:**
- `src/hexapod_description/urdf/` enthält die URDF + Xacro-Macros
- Bein-Macro nutzt vermutlich gemeinsame Limits für alle 6 Beine
- Siehe `docs/00_conventions.md` §11.4:
  > „Falls in Phase 3 oder Phase 7 festgestellt wird, dass einzelne
  > Beine mechanisch andere Anschläge haben, wird das Bein-Macro so
  > erweitert, dass Limits per Parameter überschrieben werden können."

→ Das war als Möglichkeit angelegt aber noch nicht implementiert. Für
diesen Cal-Plan wird das Refactoring zwingend.

**Konzept (Sollzustand):**
```xml
<!-- Bein-Macro mit individuellen Limits pro Joint -->
<xacro:leg_macro
  leg_id="5"
  coxa_lower="-0.353"  coxa_upper="0.353"
  femur_lower="-0.800" femur_upper="0.800"
  tibia_lower="-0.900" tibia_upper="0.700"
  ...
/>
```

**Defaults:**
- Wenn Args nicht angegeben → fallback auf aktuelle globale Werte
  (±1.57 für Coxa/Femur, ±1.50 für Tibia)
- Backwards-Compat: bestehende Aufrufe ohne neue Args funktionieren
  weiter

**Schritte für das Refactoring:**
1. URDF-Code-Inspektion: `src/hexapod_description/urdf/` durchsehen,
   welche xacro-Files das Bein-Macro definieren
2. Macro um 6 neue optionale Args erweitern (lower/upper pro
   Joint-Typ)
3. Defaults setzen (= bisherige globale Werte aus 00_conventions.md
   §11.4)
4. Bestehende Tests laufen lassen (sollte alles grün bleiben, da
   Defaults = vorheriges Verhalten)
5. Sim-Test mit unveränderten Werten — Roboter muss noch in
   Stand-Pose stehen
6. **Plus:** Test-Cal für 1 Joint mit anderem Limit, um Macro-
   Funktionalität zu verifizieren

**Aufwand:** ~1-2 h Code + Tests.

**Plan-Doku separat?** Wenn ja: `phase_12_xx_urdf_macro_per_joint_limits_plan.md`
oder ähnlich (Phase 12 ist nächste aktive Phase nach Phase 11).

## 6. Offene Fragen die der nächste Chat klären muss

### F1 — Reihenfolge URDF-Macro vs. Cal-Session? ✅ ERLEDIGT (de facto)

User hat Cal-Session ohne URDF-Macro-Refactoring durchgeführt
(= Option B aus Original-Frage). Funktional ok weil Cal-Daten
sind PWM-zentrisch und werden erst bei URDF-Eintrag in rad konvertiert.

**Konsequenz für nächsten Chat:**
- URDF-Macro-Refactoring jetzt **vor** Phase 3 (servo_mapping.yaml +
  URDF eintragen) machen
- Mit Default-Werten = bisherige globale ±1.57 für Backwards-Compat
- Dann pro Bein die individuellen rad-Werte aus Sektion 3.5.3
  eintragen

### F2 — URDF-Macro-Refactoring als eigene Plan-Doku?

**Status:** noch nicht entschieden. Vorschlag bleibt: **kompakte
Plan-Doku** (1-2 Seiten), nicht so ausführlich wie Phase-11-Stage-
Plans. Memory `feedback_decision_alternatives_log.md` verlangt
strukturierten Workflow.

→ User-Entscheidung im nächsten Chat einholen.

### F3 — Wie viele Servos pro Typ charakterisieren? ✅ ERLEDIGT

User hat alle 18 Servos individuell charakterisiert (Phase 1).
µs/°-Konstante zeigt ~7.32 µs/° konsistent über alle. Cross-Check
bestätigt Datenblatt-Spec für 270°-Servos.

### F4 — Verfügbarkeit Servo-Horn für Charakterisierung? ✅ ERLEDIGT

User hatte Sicht-Hilfe verfügbar, Phase 1 erfolgreich durchgeführt.

### F5 — Aufgebockt-Vorrichtung für Phase 5+6?

**Status:** noch zu klären. Bleibt für Phase 5+6 relevant
(Hardware-Direction-Cal + Gait-Test).

→ User-Vorab-Check im nächsten Chat.

### F6 — Welches Bein zuerst für Phase 5?

**Status:** noch zu klären. Vorschlag bleibt **leg_6** wegen
Phase-10-Cal-Cross-Reference. Plus alternative: **leg_1** weil
zuerst kalibriert in dieser Session, könnte als „proof of concept"
für die ganze Pipeline dienen.

→ User-Entscheidung im nächsten Chat.

### F7 — Reihenfolge der Cal-Session ✅ ERLEDIGT

User hat eigene Reihenfolge gewählt (pro Bein, leg_1 → leg_6).
Erfolgreich durchgeführt.

### F8 — Sim-Verifikation in Phase 4 — wie streng?

**Status:** noch zu klären für Phase 4.

→ Empfehlung weiterhin mindestens visual + Walking-Smoke. Bei
Problemen erweitern auf mehrere Sim-Tuning-Workshop-Szenarien.

### F9 — NEU (aus Cal-Findings): leg_3_coxa pulse_min nachverifizieren?

User-Notiz hatte „vielleicht 1200" für leg_3_coxa pulse_min. Vor
Phase 3 (Eintragung ins YAML) sollte das verifiziert werden — sonst
ist leg_3_coxa potentiell falsch kalibriert.

→ User-Aktion im nächsten Chat: Slider bei pin_6 nochmal kurz
testen, exakten mech-Stop-Wert bestätigen.

### F10 — NEU: Plugin-Math-Limitation bei direction=-1 — wie damit umgehen?

Siehe Finding 3.5.5 Punkt 6. Bei den linken Beinen (vermutlich
direction=-1) + asymmetrischer Cal ist Plugin-Math nicht ganz
linear. Optionen:
- a) Akzeptieren für ersten Walking-Test (Pragmatic-Empfehlung)
- b) Cal-Schema erweitern (= Weg C aus Sektion 3, Plugin-Code-
  Change)
- c) Plugin-Math mit per-Direction-Slope-Logic erweitern

→ Vorschlag (a) für jetzt, (b) oder (c) später falls Walking-
Performance-Issues. User-Entscheidung im nächsten Chat.

### F11 — NEU: Phase-13-Initial-Pose mit save_start_position-Daten?

User hat in Cal-Session die „save start position" pro Femur+Tibia
(12 Werte) notiert (Sektion 3.5.4). Das sind die Hängend-Pose-PWM-
Werte für aufgebockten Hexapod.

Optionen:
- a) Schon jetzt eine `init_pose.yaml` anlegen (= Plan für Phase-13)
- b) Nur als Reference-Daten festhalten, Phase-13-Implementation
  später
- c) Schon Plugin-Code-Change für Phase-13-Initial-Pose-Mechanik
  vorziehen

→ Vorschlag (b) — Daten sind dokumentiert, Plugin-Erweiterung
bleibt Phase-13-Material. User-Entscheidung im nächsten Chat.

## 7. Referenz-Dokumente die der nächste Chat lesen sollte

### Pflicht zum Start

1. **`CLAUDE.md`** — Projekt-Konvention, Sprache, Workflow
2. **`PHASE.md`** — Aktuelle Phase (= Phase 12 Pi-Plattform, aber
   Cal-Session ist Cross-Phase)
3. **Diese Datei** — Plan-Doku
4. **`docs/00_conventions.md` §11.4** — aktuelle Joint-Limits-
   Konvention + Hinweis dass pro-Joint-Limits geplant waren

### Cal-spezifisch

5. **`docs_raspi/servo_calibration_approach.md`** — bisheriger
   Cal-Workflow-Vorschlag (Stage-B-Slider-basiert ohne URDF-Math).
   **Wichtig:** dieser Plan ersetzt nicht den bisherigen sondern
   erweitert ihn. Phase 1 ist neu, Phase 2 ist erweitert (rad-
   Berechnung), Phase 3 ist erweitert (URDF-Update), Phase 4-6 ist
   neu (Sim-Verifikation, schrittweiser Hardware-Test).
6. **`src/hexapod_hardware/config/servo_mapping.yaml`** — aktuelle
   Cal (Phase 10 hat leg_6 grob, rest defaults)
7. **`src/hexapod_hardware/README.md`** Phase-11-Sektion — Plugin-
   Cal-Param-Mechanismus
8. **`docs_raspi/phase_11_rqt_setup.md`** — rqt-Workflow

### Memory-Einträge (werden automatisch geladen)

- `project_hexapod_servo_models.md` — Diymore + Miuzei Servo-Specs
  (beide 270°)
- `project_phase11_convenience_aliases.md` — Bash-Aliases für Save-Cal
- `project_phase13_initial_pose_presets.md` — Phase-13-Pose-Management
  (NICHT verwechseln mit dieser Cal-Plan-Doku!)
- `feedback_decision_alternatives_log.md` — strukturierter Plan-
  Workflow
- `feedback_user_does_commits.md` — User committet selbst

### Sim/Hardware-Setup-Doku

9. **`docs_raspi/phase_11_sim_tuning_workshop.md`** — Walking-Szenarien
   für Phase 4-Sim-Verifikation
10. **`tools/hexapod-shell-aliases.sh`** — Convenience-Aliases

## 8. Wichtige Vorbedingungen — Status

### Für Phase 1+2 (= bereits abgeschlossen)

- ✅ Phase 11 abgeschlossen (Live-Cal-Slider + /save_calibration-
  Service ready)
- ✅ Servo2040 + Servos elektrisch funktionsfähig (Phase 10
  verifiziert + Cal-Session 2026-05-21)
- ✅ servo_mapping.yaml hat saubere Defaults (Phase 7)
- ✅ Servo-Horn-Sichthilfe vorhanden (User-Verifikation Cal-Session)

### Für Phase 3+ (= noch offen)

- ⏳ URDF-Macro-Refactoring fertig (= Code-Change aus Sektion 5)
  — **Jetzt der erste konkrete Schritt im nächsten Chat**
- ⏳ leg_3_coxa pulse_min nachverifiziert (F9, Sektion 3.5.6)
- ⏳ Hexapod-Aufbockung verfügbar für Phase 5+6 (F5)
- ⏳ direction_normal-Bestimmung pro Pin via Direction-Cal-Test
  (Phase 5)

## 9. Was bewusst NICHT in diesem Plan ist

- **Initial/Stand/Shutdown-Pose-Management** — Phase-13-Material,
  siehe Memory `project_phase13_initial_pose_presets.md`. Cal-Plan
  hier fokussiert auf rad↔µs-Konsistenz, nicht auf Pose-State-Machine.
- **Auto-Cal-Tool** — wenn manueller 18-Servo-Workflow zu lange dauert,
  könnte ein semi-automatisches Tool (Strom-Anstieg-basierte mech-
  Stop-Detection) helfen. Phase 13+ falls jemals gewollt.
- **Bench-Strom-Profil-Verifikation** — `project_phase10_real_yaml_vel_limits.md`
  ist eigene Phase-13-Pendenz, nicht hier.
- **Cal-Validierung im Walking auf Boden** — finaler Test ist
  bodengebundenes Walking, aber als „Sicherheits-Stage" außerhalb
  dieses Plans gedacht (nach Phase 6 aufgebockt = ok, dann erst
  abbocken).

## 10. Quick-Reference — Math-Formeln

```
# Phase 1 (Charakterisierung pro Servo-Typ):
rad_per_µs = (π / 2) / ΔPWM_for_90_degrees
# Erwartung für 270°-Servos (Diymore/Miuzei):
# ~0.00236 rad/µs (= 4.712 rad / 2000 µs)

# Phase 2 (Pro Servo, aus pulse-Cal):
joint_upper = (pulse_max - pulse_zero) × rad_per_µs       # in rad
joint_lower = (pulse_min - pulse_zero) × rad_per_µs       # in rad

# Plugin-Math (für Verständnis, schon implementiert):
pulse_us = pulse_zero + direction × rad × slope
slope = (pulse_max - pulse_zero) / joint_upper            # für rad ≥ 0
      = (pulse_zero - pulse_min) / |joint_lower|          # für rad < 0
```

## 11. Erwarteter Aufwand — Updated 2026-05-21

| Phase | Dauer | Wer | Status |
|---|---|---|---|
| Phase 1 — Servo-Charakterisierung | ~1 h tatsächlich | User | ✅ done |
| Phase 2 — Mech-Stop-Cal (18 Servos) | ~2-3 h tatsächlich | User | ✅ done (leg_3 coxa unsicher) |
| URDF-Macro-Refactoring (Sektion 5) | 1-2 h | Claude (Code + Tests) | ⏳ Nächster Chat |
| Phase 3 — Konfig speichern + URDF eintragen | ~45 min | User + Claude (alle 18 Werte aus Tabellen) | ⏳ |
| Phase 4 — Sim-Verifikation | ~30 min | User + Claude (visual + Walking) | ⏳ |
| Phase 5 — Direction-Cal pro Bein (Hardware + RViz) | ~1-2 h | User (Trajectory-Pubs, RViz-Vergleich) | ⏳ |
| Phase 6 — Gait aufgebockt | ~30 min | User (visual) | ⏳ |

**Bisheriger Aufwand (Phase 1+2):** ~3-4 h User-Cal-Session.
**Verbleibender Aufwand:** ~4-5 h Claude+User für Phase 3-6.

## 12. Was im neuen Chat als erstes machen

**Status zum Start des neuen Chats:** Cal-Phasen 1 + 2 sind abgeschlossen,
alle 18 PWM-Werte + rad-Limits sind in Sektion 3.5 dokumentiert.
Nächste Schritte sind ausschließlich Code + Konfig + Verifikation.

### Pflicht-Reihenfolge

1. **CLAUDE.md + PHASE.md + diese Datei lesen** (Pflicht-Start)
2. **Sektion 3.5 dieser Datei besonders aufmerksam lesen** — dort
   sind alle Cal-Daten + Findings dokumentiert
3. **leg_3_coxa pulse_min nachverifizieren mit User** (F9 — kleine
   Unsicherheit aus Cal-Session, vor Phase 3 klären)
4. **F2 (Plan-Doku für URDF-Macro?), F5 (Aufbockung verfügbar?), F6
   (welches Bein zuerst?), F8 (Sim-Strenge?), F10 (Plugin-Math-
   Limitation akzeptieren?), F11 (init_pose.yaml jetzt?) mit User
   klären**
5. **URDF-Macro-Refactoring** (= Code-Change aus Sektion 5):
   - Plan-Doku-Stil je nach F2-Antwort
   - User-Freigabe
   - Implementation + Tests grün
6. **Phase 3 — servo_mapping.yaml + URDF eintragen:**
   - PWM-Werte aus Sektion 3.5.2 ins YAML (achten auf
     pulse_min < pulse_zero < pulse_max numerisch!)
   - rad-Werte aus Sektion 3.5.3 ins URDF
   - **Wichtig:** rad-Werte sind PWM-zentrisch. Für direction=-1-
     Beine später bei Phase 5 ggf. spiegeln im URDF (siehe Finding
     3.5.5 Punkt 3) — alternativ direkt einmal eintragen und in
     Phase 5 nachjustieren
   - colcon build hexapod_description + hexapod_hardware
   - install → src sync (cp-Befehl aus Phase 3.2)
7. **Phase 4 — Sim-Verifikation** (visual + Walking ohne IK-Errors)
8. **Phase 5 — Direction-Cal pro Bein** (Hardware + RViz parallel,
   1 Bein nach dem anderen, ggf. direction_normal=false setzen)
9. **Phase 6 — Gait aufgebockt** (defensive_walk-Preset, langsam
   beginnen)

### Memory-Update am Ende

- Dieser Plan-Doku-Pfad bleibt als historische Referenz für die
  Cal-Methodik
- Bei erfolgreichem Walking → Memory-Eintrag erstellen
  „Hexapod-Hardware-Cal-2026-05-21 erfolgreich, alle 18 Servos
  calibrated, direction-map siehe servo_mapping.yaml"
- Cross-Phase-Pendenzen die diese Cal eröffnet (Phase-13-Initial-Pose,
  Plugin-Math-Verfeinerung) ggf. in eigene Memory-Einträge auslagern

### Wichtige Cal-Daten-Quellen (alle in dieser Datei)

- **Sektion 3.5.2** = PWM-Werte für servo_mapping.yaml (numerisch
  sortiert)
- **Sektion 3.5.3** = rad-Werte für URDF (PWM-zentrisch, ggf.
  spiegeln für direction=-1)
- **Sektion 3.5.4** = save_start-Positions für Phase-13-Initial-
  Pose (12 PWM-Werte für Femur+Tibia)
- **Sektion 3.5.5** = Findings/Patterns (Mount-Versatz, Direction-
  Konvention, Range-Symmetrie, Plugin-Math-Limitation, Naming-
  Verwechslung)

---

**Erstellt 2026-05-21 am Ende von Phase 11 — User-Initiative nach Erkenntnis
dass bisheriges Cal-Konzept nicht mathematisch konsistent ist.**

**Updated 2026-05-21 nach erfolgreicher Cal-Session — alle 18 Servos
gemessen + Findings dokumentiert. Ready für URDF-Macro-Refactoring +
Plugin-Übertragung im nächsten Chat.**
