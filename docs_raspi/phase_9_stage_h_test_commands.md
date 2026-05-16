# Phase 9 — Stufe H — Test-Anleitung

**Was geprüft wird:** Das `hexapod_hardware`-Plugin spricht produktiv
mit der echten Servo2040-Firmware über USB-CDC (`/dev/ttyACM0`),
**ohne** dass Hexapod-Servos angeschlossen sind. Damit wird die volle
Wire-Protocol-Pipeline (Plugin → COBS + CRC → Firmware) real-world
verifiziert: USB-Verbindung steht, Boot-Sequenz (RESET + 18×
ENABLE_SERVO mit Stagger) läuft sauber, JTC kann Trajectory pumpen,
USB-Reconnect funktioniert, Cleanup ist sauber.

**Was NICHT in H ausgeführt wird (Hardware-Limit):**
- **H-T8 (Oszi):** PWM-Wellenform-Verifikation am Output-Pin —
  dokumentiert als optionaler Schritt für jemand mit Oszi
- **H-T9 (Logic-Analyzer):** USB-CDC-Frame-Capture + Cross-Validation —
  dokumentiert als optionaler Schritt
- Echte Servo-Bewegung mit kalibrierten Endlagen — Phase 10

---

## Bench-Setup (VOR allen Tests!)

> ⚡ **Sicherheits-Hinweis:** keine Servos verbunden. Wenn das Netzteil
> wider Erwarten >2 A zieht: sofort abschalten und Verkabelung prüfen
> (Kurzschluss zwischen V+ und GND möglich).

1. **Bench-PSU ausgeschaltet** lassen
2. Verkabelung verbinden:
   - PSU V+ → Servo2040 **V+ Rail-Eingang** (separater Eingang, nicht
     der USB-5V-Pfad)
   - PSU GND → Servo2040 **GND Rail-Eingang**
3. PSU einstellen:
   - **Spannung: 6.0 V** (Servo-Nominalspannung)
   - **CC-Limit: 0.5 A** (sicherheitshalber; ohne Servos sollte das
     Board <100 mA für VBAT-Sensing ziehen)
4. **PSU anschalten** → LED am Servo2040 sollte normal sein, kein
   Trip-Signal
5. USB-Kabel Servo2040 ↔ Desktop sollte schon stecken (sonst jetzt
   verbinden)
6. **Bleibt alles an** für H-T4 bis H-T7. PSU darf nicht abgeschaltet
   werden zwischen den Tests.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_bringup hexapod_hardware
source install/setup.bash
```

> **In JEDEM neuen Terminal das du für H-T4–H-T7 öffnest, beide
> Source-Zeilen wieder ausführen** (`source /opt/ros/jazzy/setup.bash`
> + `source install/setup.bash`).

---

## Test H-T1 — USB-Device sichtbar

```bash
ls -l /dev/ttyACM0
```

**Erwartung:**
```
crw-rw---- 1 root dialout 166, 0 ... /dev/ttyACM0
```

(`dialout`-Gruppe ist wichtig, siehe H-T2.)

Falls `ls` mit „No such file or directory" abbricht:
- USB-Kabel prüfen
- `dmesg | tail -20` zeigt evtl. ob Servo2040 erkannt wurde aber unter
  anderem Pfad enumeriert (z.B. `/dev/ttyACM1` wenn schon was anderes
  auf ACM0 liegt)

---

## Test H-T2 — Dialout-Gruppe + Permission

```bash
groups | grep dialout
```

**Erwartung:** Output enthält das Wort `dialout`.

Falls leer: `sudo usermod -aG dialout $USER`, dann einmal **neu
einloggen** (logout/login), dann nochmal `groups`.

---

## Test H-T3 — Firmware-Stand verifizieren

**Idealer Check (falls `phase-7-done`-Tag im fw-Repo gesetzt wurde):**
```bash
git -C ~/hexapod_servo_driver describe --tags 2>&1
```
**Erwartung:** zeigt `phase-7-done` (oder einen neueren Tag).

**Realität in diesem Setup (2026-05-16):** `phase-7-done`-Tag wurde
**nicht** im fw-Repo gesetzt (Doku-Drift aus Phase-7-Abschluss —
`PHASE.md` hatte das als optionalen Phasenwechsel-Schritt erwähnt,
ist aber nicht passiert). `git describe --tags` zeigt stattdessen
z.B. `legacy-pushups-10-g6525ffe` (10 Commits nach einem älteren
Tag).

**Manuelle Bestätigung reicht:**
- Du selbst weißt, dass die FW auf dem Servo2040 die in Phase 7 fertig-
  entwickelte Variante ist (kein Zwischen-Update, keine externen
  Branches)
- Servo2040 zeigt beim Boot normale LED-Pattern (kein Boot-Loop, keine
  Trip-Anzeige)
- Falls H-T4 später UNDERVOLTAGE/FRAME_CRC-Sturm zeigt: dann ist die
  FW evtl. doch eine alte Version — in dem Fall flashen mit dem
  aktuellen `~/hexapod_servo_driver`-HEAD

**Optional (für späteren Cleanup):** den Tag retroaktiv im fw-Repo
setzen:
```bash
cd ~/hexapod_servo_driver
git tag phase-7-done HEAD   # oder am exakten Phase-7-Abschluss-Commit
```
Das ist keine Stage-H-Aktion — nur ein Hygiene-Tipp für die nächste
Phase-7-Übergabe oder ein neues Build-Setup.

---

## Test H-T4 — Real-Bringup ohne Loopback

**Stage-H-Hauptbeweis Teil 1.** Verifiziert dass die volle USB-CDC-
Pipeline mit echter Firmware funktioniert.

### Schritt 1 — Launch starten

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py
```

(Default: `loopback_mode:=false`, `serial_port:=/dev/ttyACM0`.)

**Erwartung im Log** (in dieser Reihenfolge):
```
[robot_state_publisher]: got segment base_link ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_init starting (info_.joints.size=18)
[ros2_control_node-2] [INFO]: ... loopback_mode=false ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_configure starting (loopback_mode=false, serial_port=/dev/ttyACM0)
[ros2_control_node-2] [INFO]: ... opened /dev/ttyACM0 ...
[ros2_control_node-2] [INFO]: ... reader thread started ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_activate boot sequence (RESET + 18× ENABLE_SERVO @ 50 ms stagger)
[ros2_control_node-2] [INFO]: ... boot sequence complete (~900 ms) ...
[spawn_joint_state_broadcaster] [INFO]: Configured and activated joint_state_broadcaster
[spawn_leg_1_controller] [INFO]: Configured and activated leg_1_controller
... (analog leg_2 bis leg_6)
```

**Wichtige Negativ-Bestätigung:** kein **ERROR_REPORT-Sturm**. Wenn im
Log Zeilen erscheinen wie:
```
[ros2_control_node-2] [WARN]: ERROR_REPORT code=0x30 (UNDERVOLTAGE) ...
```
→ Netzteil checkt nicht durch (siehe Bench-Setup oben), oder PSU
liefert <5.0 V. Tests stoppen, PSU prüfen.

### Schritt 2 — Plugin- und Controller-Status verifizieren

**Terminal 2** (während Terminal 1 noch läuft):
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 control list_hardware_components
ros2 control list_controllers
```

**Erwartung `list_hardware_components`:**
```
Hardware Component 1
  name: GazeboSimSystem
  type: system
  plugin name: hexapod_hardware/HexapodSystemHardware
  state: id=3 label=active
```

**Erwartung `list_controllers`:** 7 Zeilen `active` (JSB + 6 leg_X_controller).

### Cleanup
Lass Terminal 1 weiter laufen — H-T5 nutzt es weiter.

---

## Test H-T5 — JTC-Trajectory-Smoke (leg_1_controller)

**Stage-H-Hauptbeweis Teil 2.** Verifiziert dass JTC.Trajectory-Action
sauber durchläuft: write() schickt SET_TARGETS-Frames → Firmware
schreibt PWM auf GPIOs (ohne Servos passiert physisch nichts) →
read() liefert Echo-State zurück → JTC sieht Soll=Ist → SUCCEEDED.

**Voraussetzung:** Terminal 1 aus H-T4 läuft noch.

**Terminal 2:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 action send_goal /leg_1_controller/follow_joint_trajectory \
    control_msgs/action/FollowJointTrajectory \
    "{trajectory: {joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
                   points: [
                     {positions: [0.1, 0.0, 0.0], time_from_start: {sec: 1}},
                     {positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}
                   ]}}" \
    --feedback
```

**Erwartung:**
```
Waiting for an action server to become available...
Sending goal:
   ...

Goal accepted with ID: <uuid>

Feedback:
   ... (Feedback-Stream ~2 s lang, joint_names + positions + velocities)

Result:
    error_code: 0
    error_string: ''

Goal finished with status: SUCCEEDED
```

**Wichtige Negativ-Bestätigung:** keine `Goal failed`-Meldung. Falls
`error_code != 0` (z.B. -3 PATH_TOLERANCE_VIOLATED): in Terminal 1 nach
ERROR_REPORT-Zeilen suchen, oft hängt das mit Pulse-Konversion zusammen
(yaml-Werte stimmen nicht zur Firmware-Kalibrierung).

### Cleanup
Lass Terminal 1 weiter laufen — H-T6 nutzt es weiter.

---

## Test H-T6 — USB-Reconnect-Smoke (Stage-D.7-Verhalten)

**Verifiziert die Stage-D.7-Reconnect-Logik real-world.** Plugin's
Reader-Thread soll Backoff machen statt zu sterben, write() schlägt
graceful fehl, nach Re-Verbindung läuft alles wieder.

> ⚠️ **Wichtig:** **Nur das USB-Kabel ziehen**, nicht das Strom-Kabel
> vom Servo-Netzteil! Das Strom bleibt an damit der Servo2040 nicht
> rebootet (sonst würde der Test über Reconnect-Verhalten irrelevant —
> wir würden stattdessen Re-Boot-Verhalten testen).

**Voraussetzung:** Terminal 1 aus H-T4 läuft noch, alle 7 Controller
sind active.

### Schritt 1 — USB-Kabel ziehen

Physisch USB-Kabel vom Servo2040 oder vom Desktop ziehen.

**Erwartung in Terminal 1 (Log):**
```
[ros2_control_node-2] [WARN]: reader thread: read failed (errno=5 EIO), retrying in 100 ms ...
[ros2_control_node-2] [WARN]: reader thread: retrying in 200 ms ...
[ros2_control_node-2] [WARN]: reader thread: retrying in 500 ms ...
... (Backoff-Sequenz {100, 200, 500, 1000, 2000, 5000, 5000} ms)
```

**Wichtige Negativ-Bestätigung:** keine `[FATAL]`-Zeile, kein „reader
thread terminated" — der Thread soll **leben bleiben** und nur
retrieren.

### Schritt 2 — USB-Kabel wieder einstecken

Physisch wieder verbinden. Warte ~2 s.

**Erwartung in Terminal 1:**
```
[ros2_control_node-2] [INFO]: reader thread: reconnected to /dev/ttyACM0
```

(Backoff stoppt, Reader-Thread läuft wieder normal.)

### Schritt 3 — Manuelle Re-Activate

**Wichtige Erkenntnis (aus dem H-T6-Smoke 2026-05-16):** ros2_control hat
einen Auto-Deactivate-Mechanismus bei write-Fail — **nicht nur** die
Controller, sondern auch die **Hardware-Komponente selbst** (das Plugin)
wird auf `inactive` gesetzt. Daher müssen wir in **dieser Reihenfolge**
re-aktivieren:

1. **erst** die Hardware-Komponente (Plugin) → das triggert ein neues
   `on_activate` mit der Boot-Sequenz (RESET + 18× ENABLE_SERVO mit
   Stagger)
2. **dann** die Controller via `switch_controllers`

Pro Schritt einzeln in **Terminal 2** ausführen, Output zwischen den
Schritten anschauen:

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

Status prüfen:
```bash
ros2 control list_hardware_components
```
*Erwartung: `GazeboSimSystem` in `state: id=2 label=inactive` (nicht `active`).*

```bash
ros2 control list_controllers
```
*Erwartung: alle 7 Controller `inactive`.*

Hardware-Komponente wieder aktivieren:
```bash
ros2 control set_hardware_component_state GazeboSimSystem active
```
*Erwartung: in Terminal 1 erscheinen neue on_activate-Log-Zeilen
(Boot-Sequenz nochmal mit RESET + 18× ENABLE_SERVO + neutral pose,
~900 ms). Hardware ist danach wieder `active`.*

Controller wieder aktivieren (ALLE Namen auf **einer Zeile**, keine
Inline-Kommentare, keine `#`-Zeichen):
```bash
ros2 control switch_controllers --activate joint_state_broadcaster leg_1_controller leg_2_controller leg_3_controller leg_4_controller leg_5_controller leg_6_controller
```
*Erwartung: `Switching successful`.*

Verifizieren:
```bash
ros2 control list_controllers
```
*Erwartung: alle 7 Controller wieder `active`.*

### Cleanup
Lass Terminal 1 weiter laufen — H-T7 nutzt es weiter.

---

## Test H-T7 — Cleanup-Verifikation

**Voraussetzung:** Terminal 1 läuft noch, alle Controller aktiv.

### Schritt 1 — Sauberes Beenden

Im Terminal 1: **Ctrl-C**.

**Erwartung im Log:**
```
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_deactivate starting (18× DISABLE_SERVO)
[ros2_control_node-2] [INFO]: ... 18 servos disabled ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_cleanup ...
[ros2_control_node-2] [INFO]: ... /dev/ttyACM0 closed ...
[ros2_control_node-2] [INFO]: ... reader thread stopped ...
```

### Schritt 2 — Kein hängender Prozess

**Terminal 2:**
```bash
ps aux | grep -E "ros2_control_node|robot_state_publisher|spawner" | grep -v grep
```

**Erwartung:** kein Output (alle Prozesse beendet).

### Schritt 3 — USB-Device frei

```bash
lsof /dev/ttyACM0 2>&1
```

**Erwartung:** `lsof: status error on /dev/ttyACM0: No such file or directory`
ODER leerer Output (= niemand hat das Device offen).

Falls noch ein Prozess das Device hält: `kill -9 <PID>`, dann nochmal.

### Cleanup
Bench-PSU kannst du jetzt abschalten (Stage H ist mit H-T7 inhaltlich
durch; H-T8/T9 sind dokumentiert aber nicht ausgeführt).

---

## Test H-T8 — PWM-Wellenform-Verifikation mit Oszi *(OPTIONAL — nicht in unserem Setup ausführbar)*

> ⏸️ **Status:** dokumentiert, aber **nicht ausgeführt** mangels Oszi.
> Memory-Eintrag dokumentiert die Cross-Session-Pendenz.

**Ziel:** verifizieren dass die PWM-Pulsweite an einem Servo-Output-Pin
mit dem aus `radians_to_pulse_us()` berechneten Pulse-µs übereinstimmt
(±~10 µs Toleranz für PWM-Quantisierung).

### Setup
- **Oszi:** beliebig (Saleae Logic 8, Rigol DS1054Z, ähnliche)
- **Sondierungs-Pin:** Servo2040 **GPIO16** (= leg_1_coxa-Servo per
  `~/hexapod_servo_driver/contrib/servo_mapping.yaml`)
- **Trigger:** Rising-Edge auf GPIO16
- **Erwarteter Pulsweiten-Bereich:** 1000–2000 µs (typisch für RC-Servo)
- **Periode:** 20 ms (50 Hz, RC-Servo-Standard)

### Sequenz
1. real.launch.py mit Loopback OFF starten (wie H-T4)
2. Oszi-Probe an GPIO16, Trigger setzen, Zeitbasis ~500 µs/div
3. Im Idle-State (kein JTC-Trajectory aktiv): Pulsweite messen
   - Erwartung: ~1500 µs (pulse_zero aus servo_mapping.yaml)
4. JTC-Trajectory pumpen (analog H-T5, aber langsamer von -1.57 zu
   +1.57 fahren über 10 s):
   ```bash
   ros2 action send_goal /leg_1_controller/follow_joint_trajectory \
       control_msgs/action/FollowJointTrajectory \
       "{trajectory: {joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
                      points: [
                        {positions: [-1.57, 0.0, 0.0], time_from_start: {sec: 5}},
                        {positions: [+1.57, 0.0, 0.0], time_from_start: {sec: 10}}
                      ]}}"
   ```
5. Während der Trajectory: Pulsweite alle ~1 s ablesen, mit dem
   erwarteten Wert aus `calibration::radians_to_pulse_us(rad)`
   vergleichen
6. Erwartete Werte (aus servo_mapping.yaml `pulse_min` / `pulse_zero`
   / `pulse_max` für leg_1_coxa, plus piecewise-linearer Konversion
   per Stage C):
   - bei `rad=-1.57`: Pulsweite ≈ `pulse_min` (typ. 1000 µs)
   - bei `rad=0.0`: Pulsweite ≈ `pulse_zero` (typ. 1500 µs)
   - bei `rad=+1.57`: Pulsweite ≈ `pulse_max` (typ. 2000 µs)
7. ±10 µs Toleranz für PWM-Quantisierung gilt als grün.

### Done-Kriterium
Pulsweite an GPIO16 entspricht der erwarteten Pulse-µs aus
`radians_to_pulse_us()` innerhalb ±10 µs Toleranz, über mindestens 3
gemessene Joint-Positionen verteilt.

---

## Test H-T9 — Logic-Analyzer-USB-Frame-Capture *(OPTIONAL — nicht in unserem Setup ausführbar)*

> ⏸️ **Status:** dokumentiert, aber **nicht ausgeführt** mangels
> Logic-Analyzer.

**Ziel:** USB-CDC-Stream zwischen Plugin und Firmware mitschneiden,
decoden, und gegen die in Stage B implementierten Encoder-Outputs
cross-validieren.

### Setup
- **Hardware:** USB-Logic-Analyzer (z.B. Saleae Logic 8 mit USB-Sniffer-
  Modul) ODER Wireshark mit `usbmon`-Kernel-Modul
- **Capture-Stelle:** USB-Bus zwischen Desktop und Servo2040
  (bei Wireshark: `tcpdump -i usbmon0` oder `tshark -i usbmon0`)

### Alternative ohne Hardware-Logic-Analyzer
Wireshark hat einen USB-Capture-Modus über das `usbmon`-Kernel-Modul.
Linux ab Kernel 2.6.11 unterstützt das:
```bash
sudo modprobe usbmon
sudo wireshark   # Interface 'usbmon0' wählen
# In Wireshark-Filter: usb.dst contains "1.0" (Bus.Device anpassen)
```

### Sequenz
1. Wireshark/Logic starten, USB-Bus filtern
2. real.launch.py starten (wie H-T4)
3. Im Capture sollten sichtbar sein:
   - Beim on_configure: nichts (Plugin öffnet nur Port)
   - Beim on_activate: 1 RESET-Frame, dann 18 ENABLE_SERVO-Frames mit
     50 ms Abstand
   - Im read/write-Loop: kontinuierlicher SET_TARGETS-Stream (50 Hz)
4. Capture stoppen, Frames extrahieren
5. Mit dem Python-Decoder in `~/hexapod_servo_driver/tools/` (z.B.
   die `decode_frame()`-Funktion aus `test_stage_e.py`) decoden
6. Decoded Output vergleichen mit den erwarteten Plugin-Outputs aus
   Stage B's Encoder-Tests (`test_servo2040_protocol.cpp` Hex-Anker)

### Done-Kriterium
Mindestens 5 mitgeschnittene Frames decoden sich zu validem
COBS+CRC-16-Format, mit erwarteten Opcodes (RESET, ENABLE_SERVO,
SET_TARGETS). Keine CRC-Fehler. Frame-Layout identisch zu Stage-B-
Encoder-Outputs.

---

## Test H-T10 — `hexapod_hardware`-Tests weiter alle grün (CI-Regression)

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --test-result-base build/hexapod_hardware --verbose | tail -3
```

**Erwartung:** `Summary: 208 tests, 0 errors, 0 failures, 20 skipped`
(unverändert vs. Stage-G-Endstand). Plugin-Code in Stage H nicht
angefasst, also strict 0 Diff erwartet.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| H-T1 `/dev/ttyACM0` nicht da | USB-Kabel lose, oder Device ist `/dev/ttyACM1` weil schon was auf ACM0 | `dmesg | tail -20`, ggf. `serial_port:=/dev/ttyACM1` als Launch-Override |
| H-T2 dialout-Permission failt | User-Gruppe noch nicht angewendet | `sudo usermod -aG dialout $USER`, **neu einloggen** (logout/login, nicht nur Terminal) |
| H-T3 Tag nicht `phase-7-done` | fw-Repo auf anderem Branch | `cd ~/hexapod_servo_driver && git checkout phase-7-done && reflash` |
| H-T4 UNDERVOLTAGE-Sturm | Netzteil unter 5.5 V oder gar aus | PSU prüfen — Spannung muss ≥5.5 V sein (WARN-Schwelle); 6.0 V optimal |
| H-T4 USB connect failt mit „Permission denied" | dialout-Gruppe trotz Membership nicht aktiv | Logout/Login wiederholen, oder `newgrp dialout` in dem Terminal |
| H-T4 boot sequence failt mit FRAME_CRC-Storm | USB-Bit-Errors, defektes Kabel oder schlechter USB-Hub | USB-Kabel direkt am Desktop (nicht über Hub) anschließen |
| H-T5 Trajectory failt mit `error_code=-3 PATH_TOLERANCE_VIOLATED` | Plugin's Echo-State stimmt nicht mit JTC-Erwartung überein | Im Terminal 1 nach ERROR_REPORT-Zeilen suchen; oft Calibration-yaml-Mismatch (Pulse-Werte aus yaml passen nicht zu Firmware) |
| H-T5 Trajectory failt mit Timeout (`Goal failed with status: ABORTED`) | Firmware antwortet nicht innerhalb action_monitor_rate | Servo2040 USB-Verbindung prüfen (`lsusb` zeigt es?), Firmware-Tag stimmt? |
| H-T6 Reader-Thread crasht statt Backoff | Stage-D.7-Logik nicht aktiv — sollte aber sein nach Stage E+F+G | Terminal-1-Log nach `[FATAL]` durchsuchen, Stack-Trace; ggf. Bug-Report im Plugin |
| H-T6 nach Reconnect: Controllers bleiben in `inactive` | Erwartet! Per Stage-D.7-Design ist manuelle Re-Activate nötig | `switch_controllers --activate ...` wie in Schritt 3 |
| H-T7 hängender Prozess nach Ctrl-C | ros2_control_node ignoriert SIGINT manchmal | `kill -9 <PID>` aus `ps aux | grep ros2_control_node` |
| H-T8/T9 nicht ausgeführt | kein Oszi/Logic-Analyzer | Erwartet, dokumentiert, Memory-Eintrag. Bei späterer Hardware-Verfügbarkeit nachholen |
| H-T10 hexapod_hardware-Tests failt | Sehr unwahrscheinlich — Plugin in Stage H nicht angefasst | `colcon build hexapod_hardware --cmake-clean-cache && colcon test --packages-select hexapod_hardware` |

---

## Statusmeldung an Claude

- `H-T1–H-T7 + H-T10 alle grün` → **Stufe H komplett (CI-Anteil).**
  H-T8/T9 als „⏸️ Hardware fehlt" akzeptiert. Weiter mit **Stufe I**
  (Tests-Polish + Doku-Polish).
- `H-TX failt: <Symptom>` → ich diagnostiziere
- `H-T8/T9 nachgeholt` (falls jemand mit Oszi/Logic-Analyzer das später
  durchführt) → Memory-Eintrag löschen, progress.md updaten

Vollausgabe nur bei Fehler; sonst kurz „H-TX grün" reicht.
