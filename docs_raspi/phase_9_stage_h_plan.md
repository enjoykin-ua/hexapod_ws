# Phase 9 — Stufe H — Plan

> **Status:** Plan, noch nicht implementiert. **Tests/Doku-Edits beginnen
> erst nach User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe H — Echte Servo2040-Anbindung (ohne Hexapod-Servos).
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_h_test_commands.md`).

---

## Ziel der Stufe

Das `hexapod_hardware`-Plugin produktiv mit der **echten Servo2040-
Firmware** verbinden (USB-CDC, `/dev/ttyACM0`), ohne dass Hexapod-Servos
angeschlossen sind. Damit verifizieren wir die volle USB-Wire-Protocol-
Pipeline (Plugin → COBS + CRC → Servo2040-Firmware) end-to-end im Real-
World-Setup. Phase 10 schließt dann erstmals echte Servos an.

**Was Stage H neu nachweist (vs. Stage G's Loopback-Smoke):**
- Plugin findet `/dev/ttyACM0`, öffnet es mit den korrekten Termios-
  Parametern (cfmakeraw aus Stage D.1)
- on_configure-Handshake + on_activate-Boot-Sequenz (RESET + 18×
  ENABLE_SERVO mit 50 ms Stagger aus Stage D.5) laufen sauber gegen
  echte Firmware ohne ERROR_REPORT-Sturm
- Reader-Thread (Stage D.2) sieht echte Firmware-Frames, sortiert sie
  korrekt in STATE-Cache und ERROR_REPORT-Queue
- JTC kann eine Test-Trajectory pumpen → write() schickt SET_TARGETS-
  Frames → Firmware schreibt PWM auf GPIOs (ohne dass was angeschlossen
  ist, aber das ist OK — Firmware crasht nicht)
- read() liefert Echo-State zurück, JTC sieht „erreichte Position" und
  meldet `goal_status=SUCCEEDED`

**Was beim Bench-Setup hier vorausgesetzt wird:**
- Servo2040-Board am Desktop-USB angeschlossen (siehe Phase-7-Bench-
  Setup in `phase_7_servo2040_fw.md`)
- Firmware-Tag `phase-7-done` geflasht (alle Phase-7-Smokes grün)
- User in `dialout`-Gruppe (`groups | grep dialout`)
- Keine Hexapod-Servos verbunden (Stage H, by design; Phase 10 macht
  den Anschluss)

---

## Was Stufe H NICHT macht

- **Keine echten Hexapod-Servos** — Phase 10. Verifikation der echten
  Pulse-µs-zu-Winkel-Konversion mit kalibrierten Endlagen kommt dort.
- **Keine PWM-Wellenform-Verifikation am Output-Pin** — braucht Oszi/
  Logic-Analyzer, die in unserem aktuellen Setup nicht verfügbar sind.
  Wird als **optionaler Pflicht-Schritt** in der Test-Anleitung
  dokumentiert (H-T8 + H-T9), damit jemand mit der Hardware (oder
  zukünftiges Self) den Schritt nachholen kann.
- **Keine Plugin-Code-Änderungen** — Plugin ist nach Stage E + F + G
  unverändert. Stage H ist pure Verifikation + Test-Doku.
- **Kein gait + kein teleop** — Konsistenz zu Stage F/G-Walking-Smoke-
  Pattern. Bench-Tests mit Bewegung wären in Phase 10/11 relevant, hier
  geht es nur um die USB-Pipeline.
- **Kein `<ros2_control name>`-Rename** — Stage J Polish.
- **Keine launch_testing-Suite** — Konsistenz zu Stage E/F/G; User-Smokes
  reichen für die „echte HW läuft"-Frage.

---

## Logik-Skizze

### H.1 Voraussetzungs-Checks (H-T1 bis H-T3)

Drei Pre-Flight-Checks, die schiefgehen können ohne dass es am Plugin
liegt:

- **H-T1 USB-Device sichtbar?** `ls -l /dev/ttyACM0`. Servo2040 muss
  als USB-CDC enumeriert sein. Wenn nicht: Kabel prüfen, dmesg lesen.
- **H-T2 Permission OK?** `groups | grep dialout`. Plus „kann mein
  User read+write auf /dev/ttyACM0?" — Tipp aus
  `phase_9_hexapod_hardware.md` Zeile 424 (`sudo usermod -aG dialout
  $USER` falls fehlt, einmal neu einloggen).
- **H-T3 Firmware-Tag verifizieren** — fw-Repo `git -C ~/hexapod_servo_driver
  describe --tags` muss `phase-7-done` zeigen. Falls nicht: in einer
  alten/abgebrochenen Firmware-Version kann das Protokoll-Verhalten
  abweichen (Phase 7 hat z.B. das ERROR_REPORT-Severity-Routing
  finalisiert).

### H.2 End-to-End-Bringup ohne Loopback (H-T4)

`ros2 launch hexapod_bringup real.launch.py` (Default: `loopback_mode:=false`).
Erwartetes Log-Verhalten:

```
[robot_state_publisher]: got segment base_link ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_init starting (info_.joints.size=18)
[ros2_control_node-2] [INFO]: ... loopback_mode=false ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_configure starting (loopback_mode=false, serial_port=/dev/ttyACM0)
[ros2_control_node-2] [INFO]: ... opened /dev/ttyACM0 ...
[ros2_control_node-2] [INFO]: ... reader thread started ...
[ros2_control_node-2] [INFO]: HexapodSystemHardware::on_activate starting boot sequence (RESET + 18× ENABLE_SERVO)
[ros2_control_node-2] [INFO]: ... boot sequence complete after ~900 ms ...
[spawn_joint_state_broadcaster] [INFO]: Configured and activated joint_state_broadcaster
[spawn_leg_1_controller] [INFO]: Configured and activated leg_1_controller
... (analog leg_2 bis leg_6)
```

Wichtige Negativ-Bestätigung: **kein ERROR_REPORT-Sturm** aus dem
Reader-Thread (kein RCLCPP_WARN/ERROR/FATAL mit `[ERROR_REPORT]`-
Präfix). Pro Stage D.8 würde z.B. ein FRAME_CRC-Storm anzeigen dass
USB-Bit-Errors auftreten (Kabel/Adapter-Problem).

### H.3 Trajectory-Smoke (H-T5)

Test, dass JTC.Trajectory-Action sauber durchläuft. Wir schicken eine
**minimale** Test-Trajectory an `leg_1_controller` (1 Joint, kleine
Auslenkung, kurze Dauer, neutrale Endposition wieder zurück), prüfen
auf `goal_status=SUCCEEDED`:

```bash
ros2 action send_goal /leg_1_controller/follow_joint_trajectory \
    control_msgs/action/FollowJointTrajectory \
    "{trajectory: {joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint],
                   points: [
                     {positions: [0.1, 0.0, 0.0], time_from_start: {sec: 1}},
                     {positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}
                   ]}}" \
    --feedback
```

Erwartung: `Goal accepted`, dann ~2 s Feedback-Stream, dann
`Goal finished with status: SUCCEEDED`. Plugin's write() hat
SET_TARGETS-Frames geschickt, read() hat Echo-State zurückgeliefert,
JTC sieht „Soll == Ist" am Goal-Ende.

**Warum nur 0.1 rad und nur ein Bein?** Stage H hat keine Servos
angeschlossen — die Firmware schreibt zwar PWM auf die GPIOs, aber
nichts bewegt sich. Wir wollen aber sicherstellen dass die Pipeline
nicht durch eine zu wilde Trajectory einen UNDERVOLTAGE oder
TOTAL_OVERCURRENT triggert (was bei real angeschlossenen Servos
passieren könnte). Klein + harmlos.

### H.4 USB-Disconnect/Reconnect-Smoke (H-T6)

Stage D.7 hat USB-Reconnect-Logik mit Backoff `{100..5000}` ms
implementiert. Real-World-Verifikation:

1. real.launch.py läuft, JTCs sind active
2. **USB-Kabel vom Servo2040 ziehen**
3. Reader-Thread soll im Log Backoff melden statt zu sterben
   (`[WARN] reader: read failed, retrying in 100 ms ...`)
4. write() schlägt fehl mit graceful Error (kein Crash)
5. Kabel wieder einstecken
6. Reader-Thread soll wiederverbinden, Backoff stoppt
7. **Manuelle Re-Activate** (per Stage D.7-Design): in einem zweiten
   Terminal:
   ```bash
   ros2 control switch_controllers --activate leg_1_controller ...
   ```
   (oder einfach Plugin neu in `active`-State bringen)

### H.5 PWM-Wellenform-Verifikation (H-T8 + H-T9, OPTIONAL)

**Diese Schritte sind in unserem aktuellen Setup nicht ausführbar
(kein Oszi/Logic-Analyzer).** Sie werden trotzdem in der Test-Anleitung
dokumentiert, damit:
- Jemand mit der Hardware sie nachholen kann (Bekannter, zukünftiges
  Self, Phase-10-Bench-Setup wenn Oszi dazukommt)
- Das Done-Kriterium aus der Mutter-Plan-Doku
  (`phase_9_hexapod_hardware.md` Done-Kriterium 6) klar formuliert ist
  und nicht in Vergessenheit gerät

Stage-H-Status wird dann mit dem Vermerk **„CI-Anteil grün, Oszi-Anteil
dokumentiert aber wegen Hardware-Limit nicht ausgeführt"** abgeschlossen.
In Phase 10 oder später kann das nachgeholt werden — Memory-Eintrag
dokumentiert die Pendenz cross-session.

**H-T8 (Oszi):** Pulsweiten am Servo-Output-Pin messen während write()
SET_TARGETS schickt mit verschiedenen Joint-Positionen. Erwartete
Korrelation: pulse_us aus `calibration.cpp::radians_to_pulse_us()` muss
mit gemessener PWM-Pulsweite übereinstimmen (±~10 µs Toleranz für
PWM-Quantisierung). Test-Setup: Oszi-Kanal auf Servo2040-Pin
GPIO16 (= leg_1_coxa-Servo per servo_mapping.yaml), Joint langsam von
`-1.57` zu `+1.57` fahren, dabei alle paar 100 ms Pulsweite ablesen
und mit erwartetem Pulse-µs aus dem yaml vergleichen.

**H-T9 (Logic-Analyzer):** USB-CDC-Stream zwischen Plugin und Firmware
mitschneiden, mit dem in `~/hexapod_servo_driver/python_tests/` o.ä.
verfügbaren Decoder (oder Wireshark-USB-Capture) Frames decoden,
gegen die in Stage B implementierten Encoder-Outputs cross-validieren.

### H.6 Cleanup-Verifikation (H-T7)

Nach Ctrl-C in Terminal 1: keine hängenden ros2_control_node-Prozesse,
USB-Device wieder frei (`lsof /dev/ttyACM0` zeigt nichts), Plugin's
on_deactivate hat 18× DISABLE_SERVO geschickt (im Log sichtbar).

---

## Tests / Verifikation

| # | Test | Was geprüft wird | Ausführung |
|---|---|---|---|
| H-T1 | `ls -l /dev/ttyACM0` zeigt das Device | Servo2040 als USB-CDC enumeriert | User-Voraussetzung |
| H-T2 | `groups | grep dialout` zeigt den User | USB-Read/Write-Permission | User-Voraussetzung |
| H-T3 | `git -C ~/hexapod_servo_driver describe --tags` zeigt `phase-7-done` (oder neuer) | Firmware ist auf bekannt-grünem Stand | User-Voraussetzung |
| H-T4 | `ros2 launch hexapod_bringup real.launch.py` (Default loopback=false): kein `[ERROR]`/`[FATAL]`, kein ERROR_REPORT-Sturm, alle 7 Controller active | End-to-End-Bringup mit echter USB-CDC-Kommunikation | User-Smoke |
| H-T5 | `ros2 action send_goal /leg_1_controller/follow_joint_trajectory ...` mit kleiner Test-Trajectory → `Goal finished with status: SUCCEEDED` | JTC-→-Plugin-Roundtrip: write() schickt SET_TARGETS, read() liefert Echo-State, JTC sieht Soll=Ist | User-Smoke |
| H-T6 | USB-Kabel ziehen → Reader-Thread Backoff im Log → Kabel wieder einstecken → reconnect → `switch_controllers --activate` → Stack läuft weiter | Stage-D.7-USB-Reconnect-Verhalten real-world | User-Smoke |
| H-T7 | Ctrl-C in Launch-Terminal: kein hängender Prozess (`ps`), USB-Device frei (`lsof /dev/ttyACM0`), DISABLE_SERVO im Log sichtbar | Sauberes Shutdown, on_deactivate funktioniert | User-Smoke |
| H-T8 | **OPTIONAL (Oszi):** Pulsweiten an Servo2040-Output-Pin korrelieren mit erwartetem Pulse-µs aus `radians_to_pulse_us()` (±10 µs Toleranz) | PWM-Output strukturell + wert-mäßig korrekt | **NICHT in unserem Setup** — dokumentiert für später/jemand-mit-Oszi |
| H-T9 | **OPTIONAL (Logic-Analyzer):** USB-CDC-Frames mitschneiden + decoden + mit Stage-B-Encoder-Outputs cross-validieren | Wire-Protokoll on-the-wire identisch zu Plugin-Outputs | **NICHT in unserem Setup** — dokumentiert für später |
| H-T10 | `colcon test --packages-select hexapod_hardware` weiter 208/0 (Plugin nicht angefasst in Stage H) | Regression-Check | CI |

**Was bewusst NICHT getestet wird in Stage H:**
- echte Servo-Bewegung mit kalibrierten Endlagen (Phase 10)
- Volle 6-Bein-Trajectory durch gait_node (Phase 10/12)
- Stromverbrauch + Brown-Out-Detection unter Last (Phase 10 mit Servos)
- Multi-Stunden-Stress-Test (Phase 12 voll-Bringup)

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` (oder dokumentiert „nicht ausgeführt — Hardware
fehlt") = Stage fertig:

- [x] H.1 Vorab-User-Antworten zu den 4 offenen Fragen (siehe „User-Entscheidungen"-Tabelle oben; alle 4 = A, plus Setup-Klärung „Servo-Netzteil wird angeschlossen vor H-T4")
- [ ] H.2 `phase_9_stage_h_test_commands.md` finalisiert (alle 10 Tests mit Schritt-für-Schritt-Anleitungen, H-T8/T9 explizit als „OPTIONAL — braucht Oszi/Logic-Analyzer" markiert)
- [ ] H.3 User-Voraussetzungs-Checks H-T1 + H-T2 + H-T3 grün
- [ ] H.4 Test H-T4 (real.launch.py ohne Loopback startet sauber, alle 7 Controller active, kein ERROR_REPORT-Sturm — User-ausgeführt)
- [ ] H.5 Test H-T5 (JTC-Trajectory-Smoke `leg_1_controller` → SUCCEEDED — User-ausgeführt)
- [ ] H.6 Test H-T6 (USB-Reconnect-Smoke, Stage-D.7-Verhalten verifiziert — User-ausgeführt)
- [ ] H.7 Test H-T7 (Cleanup-Verifikation nach Ctrl-C — User-ausgeführt)
- [ ] H.8 Test H-T8 (Oszi-PWM-Wellenform-Verifikation) — **nicht ausgeführt: kein Oszi verfügbar**. Anweisung in test_commands.md dokumentiert. Memory-Eintrag erstellt damit Cross-Session-Reminder besteht.
- [ ] H.9 Test H-T9 (Logic-Analyzer-USB-Frame-Capture) — **nicht ausgeführt: kein Logic-Analyzer verfügbar**. Anweisung dokumentiert. Memory-Eintrag (kann mit H.8 zusammengefasst werden).
- [ ] H.10 Test H-T10 (hexapod_hardware-Tests weiter 208/0)
- [ ] H.11 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] H.12 Eventuelle Post-Review-Fixes
- [ ] H.13 README-Update: `hexapod_hardware/README.md` Status-Zeile + Stufentabelle (Stufe H ✅ CI-Anteil, ⏸️ Oszi-Anteil)
- [ ] H.14 progress.md: H-Sektion mit Bullets + Notizen + Post-Review-Tabelle + Pendenz-Eintrag „Oszi/Logic-Analyzer-Verifikation"
- [ ] H.15 Memory-Eintrag schreiben: Cross-Session-Reminder „Phase 9 Stage H Oszi/Logic-Analyzer-Tests H-T8 + H-T9 noch nicht ausgeführt — bei Hardware-Verfügbarkeit nachholen"

---

## User-Entscheidungen (2026-05-16)

| Frage | Antwort | Auswirkung |
|---|---|---|
| H-Q1 Bench-Setup | **A** (modifiziert) — Servo2040 per USB verbunden, **Servo-Netzteil wird vor H-T4 angeschlossen** (User-Entscheidung nach Diskussion). Phase-7-Firmware geflasht; dialout-Gruppe OK. | H-T4 voll aussagekräftig (kein UNDERVOLTAGE-Sturm), H-T5 Trajectory-Smoke voll testbar. Setup-Block im test_commands.md vor H-T4 muss explizit auf Netzteil-Anschluss + 6.0 V + CC-Limit hinweisen. |
| H-Q2 Trajectory-Tiefe | **A** — minimale Trajectory an leg_1_controller, 0.1 rad | Kompakter End-to-End-Beweis, niedriges Failure-Surface. |
| H-Q3 USB-Reconnect-Smoke | **A** — jetzt schon | Stage-D.7-Verhalten real-world im kontrollierten Desktop-Setup verifizieren bevor Phase 12/13 zusätzliche Faktoren reinbringt. |
| H-Q4 Oszi/Logic-Analyzer-Doku | **A** — ausführliche Schritt-für-Schritt-Anleitung | H-T8 + H-T9 als „OPTIONAL — braucht Hardware" markiert mit konkreten Pin-Nummern, erwarteten Werten, Tools-Empfehlungen. Memory-Eintrag für Cross-Session-Pendenz. |

**Zentrale Setup-Anweisung (aus H-Q1-Diskussion):** Bench-PSU vor H-T4
auf 6.0 V einstellen, CC-Limit ~0.5 A, an Servo2040-Rail-Eingang
verkabeln, anschalten. Bleibt an für H-T4 bis H-T7. Bei H-T6 wird nur
USB gezogen, nicht Strom.

---

## Was offen war und User-Feedback gebraucht hat (vor Plan-Freigabe)

### Frage 1 — Bench-Setup Status

Verifikations-Voraussetzung, kein Design-Trade-off:
- Servo2040-Board am Desktop-USB angeschlossen?
- Phase-7-Firmware geflasht (Tag `phase-7-done` im fw-Repo)?
- User in `dialout`-Gruppe (`groups | grep dialout`)?

Falls etwas davon nicht zutrifft: erstmal das nachholen, dann Stage H.

### Frage 2 — Trajectory-Test-Tiefe (H-T5)?

- **A (mein Vorschlag): minimale Trajectory, nur eine leg_1_controller-
  Aktion, kleine Auslenkung (0.1 rad), goal_status=SUCCEEDED prüfen.**
  Schneller, beweist das End-to-End-Verhalten ohne Komplexität.
- B: zusätzlich Multi-Bein-Trajectory parallel (alle 6 leg_X_controller
  gleichzeitig), eventuell mit `ros2 topic echo /joint_states` parallel
  laufen lassen um Echo-State zu sehen. Mehr Coverage, mehr Aufwand,
  mehr Failure-Surface. Stage H ist kein Performance-Test.

### Frage 3 — USB-Reconnect-Smoke (H-T6) jetzt machen?

- **A (mein Vorschlag): ja, jetzt schon.** Stage D.7 hat die Logik
  implementiert + Unit-getestet (5 Tests in test_hexapod_system.cpp),
  aber real-world ist anders (USB-Stack-Race, Pi-USB-Hotplug-Latenz).
  Hier am Desktop mit kontrolliertem Kabelziehen ist die ideale
  Gelegenheit, das Verhalten zu sehen bevor es in Phase 12/13 im
  Roboter mit zusätzlichen Vibrations-Faktoren passiert.
- B: erst in Phase 12/13 wenn der Pi im Spiel ist. Aber dort ist das
  Setup komplexer, Diagnose schwieriger.

### Frage 4 — Oszi/Logic-Analyzer-Doku-Tiefe (H-T8 + H-T9)?

- **A (mein Vorschlag): ausführliche Schritt-für-Schritt-Anleitung
  in test_commands.md, mit konkreten Pin-Nummern (GPIO16 für
  leg_1_coxa), erwarteten Pulsweiten-Bereichen (1000–2000 µs), Tools-
  Empfehlungen (Saleae Logic 8, Rigol DS1054Z o.ä.).** Plus Memory-
  Eintrag als Cross-Session-Reminder. So kann das nachgeholt werden
  ohne dass jemand neu in den Plan eintauchen muss.
- B: nur kurzer TODO-Eintrag „PWM mit Oszi prüfen, siehe Mutter-Plan-
  Doku Done-Kriterium 6". Spart Schreib-Aufwand, aber bei späterer
  Ausführung muss man sich alles neu zusammensuchen.

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt Plan + 4 Fragen → Antworten
2. ☐ Bei Bedarf Plan anpassen
3. ☐ `phase_9_stage_h_test_commands.md` schreiben (alle 10 Tests mit
   ausführlichen Anleitungen, H-T8/T9 als OPTIONAL markiert)
4. ☐ User führt H-T1 bis H-T3 (Voraussetzungs-Checks) aus → Bestätigung
5. ☐ User führt H-T4 bis H-T7 (Bringup, Trajectory, Reconnect, Cleanup)
   aus → Bestätigung, bei Problem Diagnose
6. ☐ H-T10 (hexapod_hardware-Tests weiter grün) — CI
7. ☐ Kritischer Self-Review
8. ☐ README-Update + progress.md-Update
9. ☐ Memory-Eintrag für H-T8/H-T9-Pendenz
10. ☐ Fertig-Meldung für User-Commit

Mit Stage H ist die **Plugin-zu-Firmware-Pipeline produktiv verifiziert**
(im verfügbaren Umfang). Danach Stage I (Tests-Polish + Doku-Polish),
dann Stage J (Phase-9-Abschluss).

---

## Plan-Korrekturen während Implementation (2026-05-16)

Drei substanzielle Plan-Drift-Punkte, alle aus den User-Smoke-Real-World-
Beobachtungen — nicht antizipiert in der Vorab-Plan-Doku:

1. **H-T3 `phase-7-done`-Tag fehlt im fw-Repo.** Plan ging davon aus dass
   `git -C ~/hexapod_servo_driver describe --tags` den Tag zeigt. Real:
   `legacy-pushups-10-g6525ffe` — User hat in Phase 7 keinen Tag im
   fw-Repo gesetzt (PHASE.md erwähnte das als optionalen Phasenwechsel-
   Schritt). **Fix:** test_commands.md H-T3-Anweisung aufgeweicht zu
   „User-Bestätigung neueste FW geflasht reicht; Tag-Cleanup optional
   via `git tag phase-7-done HEAD` retroaktiv". Doku-Drift dokumentiert
   in progress.md F-Bullet H.3 und Self-Review.

2. **USB-CDC-Boot-Garbage WARN in H-T4 nicht antizipiert.** Eine
   einzelne `Servo2040Reader: frame decode failed (CRC/COBS/length,
   83 B)`-WARN erschien während on_activate. Typisches Verhalten beim
   Initial-Open von `/dev/ttyACM0`: Kernel-USB-Puffer enthält noch
   Alt-Frames von vor dem Plugin-Open. Reader liest, decode-Failure,
   eine WARN, danach läuft alles sauber weiter. **Nicht kritisch**
   (keine Folgefehler, alle 20 Boot-Frames sauber ACK'd). **Fix-
   Vorschlag** für Stage I/J: `tcflush(fd, TCIFLUSH)` direkt nach
   `SerialPort::open()` einfügen um den Initial-Puffer zu purgen.
   Kosmetischer Plugin-Code-Change, nicht in Stage H ausgeführt.

3. **H-T6 ros2_control Auto-Deactivate-Verhalten der Hardware-Komponente
   bei write-Fail.** Stage-D.7-Design ging davon aus dass bei
   USB-Disconnect nur der Reader-Thread in Backoff geht und die
   Controller deaktiviert werden — die **Hardware-Komponente selbst**
   (das Plugin) wurde im Plan nicht erwähnt. Real: ros2_control hat
   einen Auto-Deactivate-Mechanismus für die Hardware-Komponente bei
   write-Fail (`Deactivating following hardware components ...
   [ GazeboSimSystem ]` im Log). Recovery-Procedure muss daher
   **zuerst** `ros2 control set_hardware_component_state GazeboSimSystem
   active` und **dann** `switch_controllers --activate ...` machen.
   Der User-Smoke ist auf diese Doku-Lücke gestoßen (`Unable to
   activate controller ... command interface ... is not available`).
   **Fix:** test_commands.md H-T6 Schritt 3 retroaktiv umgeschrieben
   mit der korrekten zweistufigen Reactivate-Sequenz + Erklärung
   warum es so sein muss. Plugin-Code unverändert (das Auto-Deactivate-
   Verhalten ist ros2_control-default, nicht Plugin-Bug).

**Zusätzlich (Kommunikations-Doku-Verbesserung):** Während des Smokes
ist der User auf zwei Bash-Pitfalls reingelaufen, die als Test-Doku-
Lessons festgehalten sind:
- Inline-`# Kommentare`-Zeilen in Multi-Line-Bash-Blöcken brechen den
  Command bei `#` ab (kein Block-Paste wenn Kommentare drin sind)
- `ros2 launch` mit `-p robot_description:="$(xacro ...)"` bricht
  den rcl-arg-parser (war schon in Stage F's F-T9-Verschiebung
  dokumentiert; hier nochmal relevant gewesen weil User in der
  Recovery-Sequenz Inline-Kommentare mit-kopiert hat)

Diese Lessons stehen im **`phase_9_stage_h_test_commands.md`**-
Fehlerdiagnose-Block + sind im progress.md-Bullet H.12 dokumentiert.
