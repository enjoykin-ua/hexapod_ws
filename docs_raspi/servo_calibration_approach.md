# Servo-Kalibration — Schritt-für-Schritt-Anleitung

End-to-End-Workflow um die 18 Hexapod-Servos zu kalibrieren mit den
Tools aus Phase 11. Drei Phasen:

1. **Pulse-Cal** — pro Servo `pulse_min` / `pulse_zero` / `pulse_max`
   finden durch Live-Slider-Drehen
2. **Direction-Cal** — pro Servo `direction_normal` verifizieren durch
   RViz-vs-Hardware-Vergleich
3. **Save + Sync** — Cal-Werte permanent ablegen

> **Vorbedingungen:**
> - Phase 11 abgeschlossen (Live-Cal-Slider + `/save_calibration`-Service)
> - Hexapod-Hardware verkabelt: Servo2040 über USB-CDC am Workstation,
>   Servos an Pin 0..17 angeschlossen, Stromversorgung steht
> - **Roboter aufgebockt** (Beine ohne Bodenkontakt) für die Cal-Session
>   — sonst können fehlerhafte pulse_min/max-Werte den Roboter
>   mechanisch in einen Endanschlag fahren und beschädigen

---

## Bekannte Verkabelung (Pin → Joint)

Aus [`src/hexapod_hardware/config/servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml):

| Pin | Joint | Bein |
|---|---|---|
| 0,1,2 | leg_1_coxa, leg_1_femur, leg_1_tibia | leg_1 (vorne rechts) |
| 3,4,5 | leg_2_coxa, leg_2_femur, leg_2_tibia | leg_2 (mitte rechts) |
| 6,7,8 | leg_3_coxa, leg_3_femur, leg_3_tibia | leg_3 (hinten rechts) |
| 9,10,11 | leg_4_coxa, leg_4_femur, leg_4_tibia | leg_4 (hinten links) |
| 12,13,14 | leg_5_coxa, leg_5_femur, leg_5_tibia | leg_5 (mitte links) |
| 15,16,17 | leg_6_coxa, leg_6_femur, leg_6_tibia | leg_6 (vorne links) |

Pro Bein: coxa = unterster Pin (Hüfte, Z-Achse), femur = mittlerer
(Oberschenkel, Y-Achse), tibia = oberster (Schienbein, Y-Achse).

---

## Setup pro Cal-Session

```bash
# Plugin im real-Modus starten (NICHT loopback — Servos sollen sich
# wirklich bewegen)
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```

Logger sollte zeigen:
```
[hexapod_hardware]: Phase 11 Stage B+C: 72 live-cal params + publish_servo_pulses
                    declared, on_set_parameters_callback registered,
                    ~/servo_pulses publisher ready
```

In separatem Terminal: rqt_reconfigure für Slider:

```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

Im rqt-Panel links **`hexapodsystem`** anklicken (lowercase!) → Tree
mit 72 Pin-Params + `publish_servo_pulses`-Checkbox erscheint.

---

## Phase 1 — Pulse-Cal (alle 18 Servos nacheinander)

**Konzept:** Plugin sendet pro Tick die aktuelle `pulse_zero` an jeden
Servo wenn keine Joint-Trajectory kommandiert ist (= kein `gait_node`
läuft). Wenn du den `pin_<N>.pulse_zero`-Slider drehst, fährt der Servo
live zur neuen Mittelposition. Damit kannst du den mechanischen
Endanschlag in beide Richtungen abtasten.

Default-Range pro Servo: `pulse_min=500`, `pulse_zero=1500`,
`pulse_max=2500`. Damit ist der Slider-Bewegungsraum maximal.

### Pro Pin (Pin 0 bis Pin 17 nacheinander)

**Sicherheits-Check vor jedem Pin:** das entsprechende Bein hängt frei,
nicht am Boden. Wenn der Servo gegen den mechanischen Anschlag fährt,
gibt's keine Last die ihn beschädigt.

**Schritt 1 — Maximum-Pulse finden:**

In rqt den `pin_<N>.pulse_zero`-Slider **langsam** in eine Richtung
drehen (z.B. von 1500 nach oben Richtung 2500). Beobachten:

- Servo bewegt sich live mit
- Bei einem bestimmten Pulse-Wert erreicht der Servo seinen mechanischen
  Stop — er surrt aber dreht nicht weiter
- **Notiere diesen Wert + zieh den Slider SOFORT um 20-30 µs zurück**
  damit Servo nicht dauerhaft gegen den Anschlag drückt (Wärme + Strom)

→ Dieser zurückgezogene Wert ist dein `pulse_max`-Kandidat.

**Beispiel:** Slider auf 1850 → Servo stoppt, dreht nicht weiter →
zurück auf 1830 → notiert: **pulse_max = 1830** (mit 20 µs Reserve).

**Schritt 2 — Minimum-Pulse finden:**

Slider in die andere Richtung drehen (von 1500 nach unten Richtung 500).
Analog vorgehen: bei mech. Stop notieren + Reserve einhalten.

→ Dieser Wert ist dein `pulse_min`-Kandidat.

**Beispiel:** Slider auf 1180 → Servo stoppt → zurück auf 1200 →
notiert: **pulse_min = 1200** (mit 20 µs Reserve).

**Schritt 3 — Zero-Position (Mitte) finden:**

Slider auf die Position drehen, an der der Servo seine **Stand-Pose-
Mitte** einnimmt. Für coxa typisch: Bein zeigt radial nach außen vom
Body. Für femur typisch: Bein-Oberschenkel horizontal. Für tibia
typisch: Knie gerade ausgestreckt.

→ Notieren als `pulse_zero`.

**Beispiel:** Slider auf 1330 → Bein sieht "neutral" aus → notiert:
**pulse_zero = 1330**.

**Schritt 4 — Werte ins Plugin schreiben:**

Du hast jetzt drei Werte für Pin `<N>` auf Papier. Setze sie ins Plugin
sequenziell (Reihenfolge ist unwichtig, weil du dich immer innerhalb
der aktuellen Range bewegst — sequenzielle Set-Schritte halten die
Cross-Constraint `pulse_min < pulse_zero < pulse_max` immer ein):

```bash
ros2 param set /hexapodsystem pin_<N>.pulse_zero 1330
ros2 param set /hexapodsystem pin_<N>.pulse_min  1200
ros2 param set /hexapodsystem pin_<N>.pulse_max  1830
```

Logger im Plugin-Terminal:
```
cal updated: pin_<N>.pulse_zero = 1330
cal updated: pin_<N>.pulse_min = 1200
cal updated: pin_<N>.pulse_max = 1830
```

> **Tipp:** wenn du `<N>` durch deine Pin-Nummer ersetzen willst ohne
> jedes Mal zu tippen, kannst du eine Schleife nutzen oder die rqt-
> Slider direkt auf die finalen Werte ziehen. Funktional identisch.

**Schritt 5 — Verifikation:**

```bash
ros2 param get /hexapodsystem pin_<N>.pulse_zero
ros2 param get /hexapodsystem pin_<N>.pulse_min
ros2 param get /hexapodsystem pin_<N>.pulse_max
```

Sollte die 3 gesetzten Werte zeigen.

### Wiederholen für alle 18 Pins

Wenn alle 6 Beine × 3 Servos kalibriert sind, **alle 54 Werte stehen
jetzt im Plugin-State** (aber noch nicht persistiert auf Disk —
das kommt in Phase 3).

---

## Phase 2 — Direction-Cal (nach pulse-Cal)

**Konzept:** `direction_normal` bestimmt ob ein positiver Joint-Winkel
in eine positive ODER negative Pulse-µs-Delta umgesetzt wird. Das ist
NICHT durch Slider-Drehen verifizierbar (Slider ändert `pulse_zero` nur,
wirkt unabhängig von Direction). Du musst den Joint AKTIV bewegen und
Hardware-Bewegung mit URDF-Erwartung vergleichen.

**RViz als URDF-Referenz:** `real.launch.py` startet `robot_state_publisher`,
der TF aus den von `joint_state_broadcaster` publishten `joint_states`
berechnet. RViz visualisiert das. Da Plugin im Echo-Mode ist (kein
echtes Position-Feedback), zeigt RViz das was das **Plugin glaubt** —
also was URDF mit dem aktuellen Joint-Command-Wert macht. Hardware
zeigt was **wirklich** passiert.

**Wenn RViz und Hardware in dieselbe Richtung drehen → direction
richtig. Wenn entgegengesetzt → flippen.**

### Setup für Direction-Cal

Falls noch nicht offen:
```bash
# Terminal A: real.launch.py läuft schon aus Phase 1

# Terminal B: RViz
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz
```

RViz zeigt jetzt das URDF-Modell. Initial sind alle Joints auf 0 →
Roboter in URDF-Default-Pose.

### Pro Pin (alle 18 nacheinander)

**Voraussetzung:** Plugin im `inactive`-Lifecycle-State für den
`direction_normal`-Flip (Stage-B-Sicherheits-Restriction). Sequenz:

```bash
# Plugin deaktivieren (= Controllers inactive setzen)
ros2 control set_controller_state joint_state_broadcaster inactive
for leg in leg_1 leg_2 leg_3 leg_4 leg_5 leg_6; do
  ros2 control set_controller_state ${leg}_controller inactive
done
ros2 control set_hardware_component_state HexapodSystem inactive
```

(Aktuelle State prüfen mit `ros2 control list_hardware_components`.)

**Direction-Test pro Pin/Joint:**

1. **Aktiv-Setzen** (für JTC-Trajectory-Annahme):
   ```bash
   ros2 control set_hardware_component_state HexapodSystem active
   ros2 control set_controller_state joint_state_broadcaster active
   ros2 control set_controller_state leg_<n>_controller active
   ```
   (`<n>` = 1..6, je nach Bein das du gerade testest.)

2. **Joint auf +0.5 rad fahren** via Trajectory-Pub (Beispiel Pin 0 = leg_1_coxa):
   ```bash
   ros2 topic pub --once /leg_1_controller/joint_trajectory \
     trajectory_msgs/msg/JointTrajectory \
     '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
       points: [{positions: [0.5, 0.0, 0.0], time_from_start: {sec: 2}}]}'
   ```
   (Nur den zu testenden Joint ändern, andere auf 0. Hier coxa auf +0.5 rad,
   femur/tibia bleiben bei 0.)

3. **Beobachten parallel:**
   - **RViz:** das URDF-Modell zeigt die erwartete Bein-Bewegung
     (positive coxa = ... je nach Bein, siehe `00_conventions.md` Mount-Yaws)
   - **Hardware:** echter Servo bewegt sich physisch

4. **Vergleich:**
   - **Beide in dieselbe Richtung** → `direction_normal` ist korrekt
     (Default true = +1)
   - **Beide in entgegengesetzte Richtung** → Direction muss geflippt
     werden

5. **Falls Flip nötig:**
   ```bash
   # Wieder inactive (Stage-B-Restriction)
   ros2 control set_controller_state leg_<n>_controller inactive
   ros2 control set_controller_state joint_state_broadcaster inactive
   ros2 control set_hardware_component_state HexapodSystem inactive

   # Flip direction
   ros2 param set /hexapodsystem pin_<N>.direction_normal false
   # Logger: cal updated: pin_<N>.direction_normal = false (-1)

   # Wieder active
   ros2 control set_hardware_component_state HexapodSystem active
   ros2 control set_controller_state joint_state_broadcaster active
   ros2 control set_controller_state leg_<n>_controller active

   # Test wiederholen — Servo sollte jetzt in selber Richtung wie RViz drehen
   ros2 topic pub --once /leg_1_controller/joint_trajectory ...
   ```

6. **Joint zurück auf 0** vor nächstem Test:
   ```bash
   ros2 topic pub --once /leg_1_controller/joint_trajectory \
     trajectory_msgs/msg/JointTrajectory \
     '{joint_names: ["leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint"],
       points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
   ```

### Wiederholen für alle 18 Pins

Nach allen Pins haben alle Servos sowohl korrekte pulse-Werte als auch
korrekte `direction_normal`.

> **Tipp:** wenn du beim Sichten der RViz-Erwartung unsicher bist
> (welche Richtung ist „positive coxa" für leg_3?), schau in
> [`docs/00_conventions.md`](../docs/00_conventions.md) §11.3
> Mount-Punkte: jedes Bein hat einen `yaw` (mount-orientation), der die
> Richtung der positive coxa-Drehung mitbestimmt. RViz zeigt das aber
> direkt — beobachten ist meist klarer als ausrechnen.

---

## Phase 3 — Save + Sync install → src

Stand jetzt: alle 72 Cal-Param-Werte sind im **Plugin-Memory** korrekt,
aber noch nicht auf Disk.

### Schritt 1 — Save in install-tree

```bash
ros2 service call /save_calibration std_srvs/srv/Trigger
```

Erwartete Antwort:
```
success: True
message: 'saved 18 cals to /home/enjoykin/hexapod_ws/install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml
          (backup as .bak-<timestamp>)'
```

Das schreibt nach `install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml`
mit Timestamp-Backup-File. **Nächster Plugin-Start würde diese Werte
laden** — solange du keinen `colcon build` machst.

### Schritt 2 — Wichtig! install → src zurückkopieren

**Problem:** beim nächsten `colcon build --packages-select hexapod_hardware`
wird das install-File durch das src-File überschrieben — deine Cal-
Werte sind weg.

**Lösung:** manuell zurückkopieren in src-Tree:

```bash
cp install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml \
   src/hexapod_hardware/config/servo_mapping.yaml
```

Damit ist der Cal-Stand auch im Repo gespeichert und bleibt persistent
über Builds und Git-Commits.

### Schritt 3 — Verifikation + Rebuild

```bash
# Vergleich src und install — sollten identisch sein
diff src/hexapod_hardware/config/servo_mapping.yaml \
     install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml
# Erwartung: keine Ausgabe (= identisch)

# Optional: Rebuild damit alles konsistent
colcon build --packages-select hexapod_hardware

# Plugin neu starten zum Test
pkill -9 -f "ros2|gait_node|rviz2|rqt"; sleep 4
ros2 launch hexapod_bringup real.launch.py
# Logger sollte zeigen dass die kalibrierten pulse-Werte geladen wurden
```

Wenn du jetzt `ros2 param get /hexapodsystem pin_15.pulse_zero` (oder
beliebigen Pin) abfragst, sollten die kalibrierten Werte da sein.

### Schritt 4 — Git-Commit (optional aber empfohlen)

```bash
git status
# servo_mapping.yaml als modified anzeigen, plus evtl. .bak-Files

# Cal-Stand committen:
git add src/hexapod_hardware/config/servo_mapping.yaml
git commit -m "calibration: all 18 servos calibrated (<datum>)"

# Backup-Files (.bak-<timestamp>) NICHT committen — gitignoren wäre sauber.
# Vorschlag: in .gitignore folgenden Eintrag aufnehmen:
#   src/hexapod_hardware/config/servo_mapping.yaml.bak-*
```

---

## Stolperfallen / Häufige Probleme

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| `Setting parameter failed: pin_N: requires pulse_min < pulse_zero < pulse_max` | Cross-Constraint verletzt — du versuchst pulse_min auf einen Wert ≥ aktuellem pulse_zero zu setzen | Setze pulse_zero zuerst (in die enge Range), dann pulse_min und pulse_max |
| `Setting parameter failed: pin_N.direction_normal can only change in 'inactive'` | Direction-Flip versucht während Plugin aktiv | Wie in Phase 2 Schritt 5: erst Controllers + Hardware-Component auf `inactive`, dann flip |
| Servo brummt aber dreht nicht / wird warm | pulse_min oder pulse_max zu nah am mechanischen Anschlag (Servo drückt dauerhaft) | Pulse-Wert um 20-30 µs nach innen verschieben (Reserve einbauen) |
| Nach `colcon build` sind meine Cal-Werte weg | Schritt 2 (Phase 3) vergessen — install ist mit src überschrieben worden | Aus letztem `.bak-<timestamp>` zurückspielen: `cp install/.../servo_mapping.yaml.bak-<latest> src/.../servo_mapping.yaml`, dann `colcon build` |
| RViz zeigt Hexapod „verrenkt" nach Cal | Cal-Werte ergeben unsinnige rad-Berechnung — z.B. pulse_zero in falscher Mitte | pulse_zero auf visuell-mittlere Position für jeden Servo justieren, Save + Restart |
| `ros2 topic pub` Joint-Trajectory wirkt nicht | Controller nicht aktiv | `ros2 control list_controllers` zeigt welche aktiv sind; mit `ros2 control set_controller_state <name> active` aktivieren |
| Plugin-Restart lädt alte Cal | Plugin liest aus install — falls install veraltet ist (z.B. nach Reset des Workspaces): `colcon build --packages-select hexapod_hardware` neu erstellt install aus src | Sicherstellen dass src-File die gewünschten Cal-Werte hat (Phase 3 Schritt 2) |
| Nach `pkill -9` + Restart von `real.launch.py`: Plugin aktiv, alle Controllers aktiv, Param-Service reachable, USB-Device sichtbar — aber Slider-Drehung bewegt Servo nicht | Servo2040-Firmware oder USB-CDC-Treiber-State hängen geblieben (passiert wenn `pkill -9` ohne sauberes Plugin-Shutdown läuft → Firmware sieht keine RESET-Frame, bleibt in altem State) | **Hardware-Reset:** Servo-Netzteil ausschalten, USB-Kabel vom Servo2040 abziehen, ~5 s warten, USB neu einstecken, Netzteil wieder an. Plugin via `real.launch.py` neu starten — danach reagieren Slider wieder normal |

---

## Was diese Doku NICHT abdeckt

- **Start-Pose / Initial-Pose / Shutdown-Pose:** das sind Plugin-Pulse-
  Werte für definierte Posen beim Boot/Power-off. Phase-13-Material,
  siehe Memory-Eintrag `project_phase13_initial_pose_presets.md`.
- **Auto-Cal-Tool:** wenn manueller Workflow für 18 Servos zu lange
  dauert, wäre ein semi-automatisches Tool denkbar (Servo dreht
  langsam, Strom-Anstieg detektiert mech. Stop). Phase-13-Material.
- **Cal-Validierung im Walking:** sobald alle 18 Servos kalibriert
  sind, läuft `ros2 launch hexapod_gait gait.launch.py` mit echtem
  cmd_vel. Wenn Walking unsauber: einzelne Cal-Werte nachjustieren.
  Phase-13-Material.

---

## Bezug zu Phase 11

Diese Anleitung nutzt direkt die Tools aus Phase 11:

| Stage | Was wir hier nutzen |
|---|---|
| **A** | gait_node Live-Params — hier irrelevant (gait_node läuft nicht), aber als Konzept-Vorbild |
| **B** | **72 Live-Cal-Params** (pin_<N>.pulse_min/zero/max/direction_normal) + `/save_calibration`-Service + Timestamp-Bak |
| **C** | `/servo_pulses`-Diagnostic-Topic — optional zum Visualisieren während Cal: `rqt_plot /hexapodsystem/servo_pulses/data[<N>]` |
| **D** | params_file-Mechanismus + Setup-Doku [`phase_11_rqt_setup.md`](phase_11_rqt_setup.md) — siehe dort für rqt-Tipps |
| **E** | Workshop-Doku [`phase_11_sim_tuning_workshop.md`](phase_11_sim_tuning_workshop.md) — nicht direkt relevant für Cal, aber zeigt wie kalibrierte Werte später im Walk genutzt werden |

Plus Convenience-Aliases aus [`tools/hexapod-shell-aliases.sh`](../tools/hexapod-shell-aliases.sh):
- `hexapod-save-cal` — kürzer als `ros2 service call /save_calibration ...`
- `hexapod-list-cal-backups` — zeigt vorhandene .bak-Files mit Timestamp
