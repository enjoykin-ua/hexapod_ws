# Phase 9 — Stufe I — Plan

> **Status:** Plan, noch nicht implementiert. **Code/Doku-Edits beginnen
> erst nach User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe I — Tests & Doku (Polish-Stage vor Phase-9-Abschluss in Stage J).
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_i_test_commands.md`).

---

## Ziel der Stufe

Phase 9 für den **Phase-9-Abschluss in Stage J** bereit machen. Drei
Themen-Bereiche:

1. **Code-Polish:** einen offenen 🟡-Vormerker aus Stage H aufräumen
   (`tcflush`-Fix für USB-Boot-Garbage-WARN).
2. **Test-Erweiterung:** eine launch_testing-Suite für `real.launch.py`
   im Loopback-Mode (per Mutter-Plan I.2 gefordert).
3. **Doku-Polish:** hexapod_hardware/README gegen die Mutter-Plan-I.3-
   Checkliste prüfen + Quick-Start-Block am Anfang ergänzen.

Stage J ist dann reine Phasen-Abschluss-Aktion (`name=`-Rename in URDF,
git tag, PHASE.md update) — Stage I liefert alle Code-/Doku-Polish-Items
damit Stage J nicht mehr fachlich werden muss.

---

## Was Stufe I NICHT macht

- **Kein Plugin-API-Migrations-Refactor** (von alter
  `export_*_interfaces()` zu neuer `on_export_*_interfaces()`-API).
  Die Stage-E-Pragma-Suppression bleibt als 🟢 später-Item dokumentiert.
  Begründung: größerer Refactor (Plugin + Tests), inhaltlich überflüssig
  weil die alte API laut `hardware_component_interface.hpp` Z.177 gewinnt
  sobald der Override non-empty Vector liefert. Phase 10/11 kann das
  machen wenn man eh am Plugin werkelt.
- **Kein `<ros2_control name>`-Rename** (`GazeboSimSystem` → `HexapodSystem`).
  Stage J Polish — dort wird auch der Phase-9-Tag gesetzt.
- **Keine echten Hexapod-Servos** — Phase 10.
- **Keine Oszi/Logic-Analyzer-Nachverfolgung** — Memory-Eintrag aus
  Stage H bleibt offen bis Hardware verfügbar.
- **Keine neuen Features.** Stage I ist Polish, nicht Funktionalitäts-
  Erweiterung.

---

## Logik-Skizze

### I.1 Code-Polish: `tcflush(fd, TCIFLUSH)` in SerialPort::open()

**Problem (aus Stage H H-T4):** beim Initial-Open von `/dev/ttyACM0`
liegen evtl. noch alte Bytes im Kernel-USB-Puffer (von vor dem
Plugin-Open). Reader liest die, decode failt, eine
`Servo2040Reader: frame decode failed`-WARN erscheint. Kosmetisch
unschön, nicht funktional.

**Fix:** in [`src/hexapod_hardware/src/serial_port.cpp`](../src/hexapod_hardware/src/serial_port.cpp)
direkt nach erfolgreichem `open()` + `tcsetattr()`:

```cpp
// Purge stale bytes that may have accumulated in the kernel USB-CDC
// buffer before we opened the port (e.g. from a previous session or
// from the Servo2040 booting while we were not listening). Prevents
// a spurious "frame decode failed" WARN at first read (observed in
// Phase 9 Stage H H-T4 user smoke).
if (::tcflush(fd_, TCIFLUSH) != 0) {
  RCLCPP_WARN(plugin_logger(),
    "tcflush(TCIFLUSH) failed (errno=%d) — non-fatal, continuing", errno);
}
```

**Tests:** ein neuer kleiner gtest-Case im `test_serial_port.cpp` der
verifiziert dass nach `SerialPort::open()` der Input-Buffer leer ist
(per `ioctl(FIONREAD)` lesbar). Plus: bestehende 14 SerialPort-Tests
müssen weiter grün bleiben (tcflush ist no-op wenn Buffer leer ist).

### I.2 launch_testing-Suite für real.launch.py

**Mutter-Plan I.2:** „launch_testing: Smoke-Test: Node startet, alle
Controller spawnen, in 10 s kein Crash."

**Was ich baue:** ein Python-launch_testing-File
`test/launch/test_real_launch_loopback.py` im `hexapod_bringup`-Paket
das:

1. `real.launch.py` mit `loopback_mode:=true` startet
2. wartet bis `controller_manager`-Service verfügbar ist (max 30 s)
3. `ros2 control list_hardware_components` aufruft, prüft dass das
   Plugin als `active` erscheint
4. `ros2 control list_controllers` aufruft, prüft dass alle 7
   Controller als `active` erscheinen
5. nach 10 s sauberes Shutdown

**CI-Anteil:** Headless ausführbar (kein RViz, kein Gazebo, kein
Display nötig). Läuft mit `colcon test --packages-select hexapod_bringup`.

**Was es NICHT macht:**
- keine echte HW-Anbindung (loopback only)
- kein Trajectory-Test (Stage H ist dafür da)
- kein USB-Reconnect-Test (Stage H)
- keine launch_testing-Suite für `sim.launch.py` (Gazebo-Sim launch_testing
  ist komplex und Sim-Regression wird per User-Smoke aus Stage F/G/H
  abgedeckt)

### I.3 README-Polish

hexapod_hardware/README ist mit 1200+ Zeilen sehr ausführlich, aber
hat keinen **Quick-Start-Block am Anfang**. Die Mutter-Plan-I.3-
Checkliste:

| Item aus Mutter-Plan I.3 | Aktueller README-Stand | Stage-I-Action |
|---|---|---|
| Zweck | ✅ Sektion „Was dieses Paket tut" (Zeile 43) | nichts |
| Topics | ❌ Plugin publisht keine ROS-Topics direkt | **kurze Klarstellungs-Notiz** ergänzen (state interfaces gehen über controller_manager → /joint_states, /leg_X_controller/follow_joint_trajectory) |
| Parameter (`serial_port`, `calibration_file`, `loopback_mode`) | ⚠️ verstreut dokumentiert in „Konfigurations-Quellen" + URDF-Header-Kommentar | **konsolidierte Parameter-Tabelle** im Quick-Start-Block |
| Beispiel-Launch | ❌ fehlt im hexapod_hardware/README (existiert in hexapod_bringup/README) | **kurzer Beispiel-Aufruf** + Verweis auf hexapod_bringup |
| Echo-State-Limitation | ✅ Sektion „Echo-State: warum wir die Inverse brauchen" (Zeile 555) + „Echo-State-Pfad — die Konversion in Aktion" (Zeile 860) | **expliziter Hinweis im Quick-Start** dass „kein Position-Feedback, JTC-Tracking-Error ≈ 0" |
| Reconnect-Verhalten | ✅ Sektion „USB-Disconnect-Recovery" (Zeile 755) | nichts |

**Konkret füge ich an Position nach Zeile 35 (Total-Test-Zahl) ein**:

```markdown
## Quick-Start (Phase 9 Stufe G+H+I)

Echte Hardware (Servo2040 am USB, kein Hexapod-Servo nötig):
```bash
ros2 launch hexapod_bringup real.launch.py
```

Loopback-Modus (CI / Dry-Run, kein USB-Port wird geöffnet):
```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

USB-Port abweichend:
```bash
ros2 launch hexapod_bringup real.launch.py serial_port:=/dev/ttyACM1
```

**Plugin-Parameter** (gesetzt im URDF `<param>`-Block, per xacro-Args
überschreibbar):

| Param | Default | Beschreibung |
|---|---|---|
| `serial_port` | `/dev/ttyACM0` | USB-CDC-Device der Servo2040 |
| `calibration_file` | `$(find hexapod_hardware)/config/servo_mapping.yaml` | Pulse-µs-zu-Joint-Winkel-Mapping pro Servo |
| `loopback_mode` | `false` | `true` = kein seriellen Port öffnen, Echo-State auch ohne HW |

**Topics:** das Plugin publisht selber keine ROS-Topics direkt. State + 
Command-Interfaces gehen über `controller_manager` an die JTC's und JSB.
Sichtbare Topics (via `joint_state_broadcaster` + 6× `JointTrajectoryController`):
- `/joint_states` (sensor_msgs/JointState) — von JSB veröffentlicht, alle 18 Joints
- `/leg_<n>_controller/follow_joint_trajectory` (control_msgs/action) — JTC-Action pro Bein
- `/leg_<n>_controller/joint_trajectory` (trajectory_msgs/JointTrajectory) — JTC Topic-Interface pro Bein

**Wichtige Limitation (Echo-State):** der Servo2040 liefert **kein
echtes Position-Feedback**. Das Plugin gibt als Position-State zurück
was zuletzt geschickt wurde (in Radiant rückgerechnet). Konsequenz:
JTC-Tracking-Error ist strukturell ≈ 0, `stopped_velocity_tolerance` 
greift nicht. Diagnose-Ersatz wäre Stromsense (eigene Stufe, deferiert).
Volle Erklärung: Sektion „Echo-State-Pfad — die Konversion in Aktion".
```

---

## Tests / Verifikation

| # | Test | Was geprüft wird | Ausführung |
|---|---|---|---|
| I-T1 | `colcon build --packages-up-to hexapod_bringup` grün, keine Warnings | Build inkl. tcflush-Fix + neuer launch_testing-File | CI |
| I-T2 | `colcon test --packages-select hexapod_hardware`: weiter alle Plugin-Tests grün + 1 neuer SerialPort-Test für tcflush-Verhalten | Plugin-Regression + neuer Tcflush-Unit-Test | CI |
| I-T3 | `colcon test --packages-select hexapod_bringup`: launch_testing-Smoke grün — real.launch.py loopback startet, Plugin active, alle 7 Controller active, sauberes Shutdown | Mutter-Plan I.2 Done-Kriterium | CI |
| I-T4 | README-Sanity-Check: Quick-Start-Block korrekt rendert (Markdown-Syntax OK), Beispiel-Aufrufe stimmen mit real.launch.py-Args, Topics-Liste konsistent mit controllers.real.yaml | Doku-Konsistenz | manuell (Read-Through) |
| I-T5 | **USB-Boot-Garbage-Regression** — H-T4 nochmal manuell laufen lassen, die `frame decode failed (83 B)`-WARN sollte jetzt weg sein (oder zumindest deutlich seltener) | tcflush-Fix-Wirkung verifizieren | User-Smoke (optional, weil schon im neuen Unit-Test abgedeckt) |
| I-T6 | Sanity: `ros2 launch hexapod_bringup sim.launch.py` weiter wie gehabt (Sim-Pfad regression-frei) | Sim-Pfad nicht durch Stage-I-Änderungen broken | User-Smoke |

**Was bewusst NICHT getestet wird in Stage I:**
- echte Servo2040-Anbindung-Wiederholung (Stage H hat das)
- Sim-Walking-Regression mit gait + teleop (Stage F + G haben das,
  Stage I berührt kein URDF / kein Sim-Setup)
- Stage-J-Items (`name`-Rename, git tag, PHASE.md)

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Stage fertig:

- [x] I.1 Vorab-User-Antworten zu den 3 offenen Fragen (siehe „User-Entscheidungen"-Tabelle oben; alle 3 = A)
- [ ] I.2 Code-Fix: `tcflush(fd, TCIFLUSH)` in `SerialPort::open()` direkt nach `tcsetattr()`. Mit RCLCPP_WARN-Fallback bei errno!=0 (nicht-fatal, weiter laufen)
- [ ] I.3 Neuer gtest-Case in `test_serial_port.cpp`: `OpenPurgesStaleInputBuffer` — verifiziert via `ioctl(FIONREAD)` dass nach `open()` keine alten Bytes im Read-Buffer sind, auch wenn vor `open()` Daten reingeschrieben wurden
- [ ] I.4 launch_testing-Suite `test/launch/test_real_launch_loopback.py` im `hexapod_bringup`-Paket
- [ ] I.5 `hexapod_bringup/CMakeLists.txt`: launch_testing-Test registriert via `add_launch_test()` (analog ros2_control Beispielen)
- [ ] I.6 `hexapod_bringup/package.xml`: `<test_depend>launch_testing_ament_cmake</test_depend>` + ggf. weitere test_depends ergänzt
- [ ] I.7 `colcon build` grün, keine Warnings
- [ ] I.8 Test I-T2 (hexapod_hardware-Tests: jetzt 209 statt 208 wegen neuem OpenPurgesStaleInputBuffer; 0 failures)
- [ ] I.9 Test I-T3 (hexapod_bringup launch_testing-Smoke grün)
- [ ] I.10 README-Polish: Quick-Start-Block + Parameter-Tabelle + Topics-Klarstellung + Echo-State-Hinweis am Anfang von `hexapod_hardware/README.md` (zwischen Status-Zeile und „Was dieses Paket tut"-Sektion)
- [ ] I.11 Test I-T4 (README-Sanity-Check)
- [ ] I.12 Test I-T5 (USB-Boot-Garbage Regression-Smoke — User-ausgeführt) **falls Frage 3 = A**
- [ ] I.13 Test I-T6 (sim.launch.py-Regression — User-ausgeführt)
- [ ] I.14 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] I.15 Eventuelle Post-Review-Fixes
- [ ] I.16 `phase_9_stage_i_test_commands.md` finalisiert
- [ ] I.17 hexapod_hardware/README Status-Zeile auf „A + B + C + D + E + F + G + H + I abgeschlossen" + Stufentabelle Stage I = ✅
- [ ] I.18 progress.md: I-Sektion mit Bullets + Notizen + Post-Review-Tabelle + Stage-J-Übergabe-Items vorbereiten

---

## User-Entscheidungen (2026-05-16)

| Frage | Antwort | Auswirkung |
|---|---|---|
| I-Q1 tcflush-Fix | **A → A (revidiert)** — Fix zurückgezogen, WARN als known-cosmetic akzeptiert | Beim Sondieren von `serial_port.cpp` direkt nach User-Freigabe wurde entdeckt: `::tcflush(fd_, TCIOFLUSH)` ist bereits in `configure_termios()` Zeile 136 implementiert, mit exakt der Begründung die ich vorgeschlagen hatte ("Flush any garbage from the input buffer so the first read isn't a pre-open boot banner..."). Mein Fix-Vorschlag wäre ein no-op gewesen. User-Entscheidung nach Re-Frage: **Variante A** — Fix zurückziehen, WARN als known-cosmetic im README dokumentieren. 208/0 Test-Total bleibt (keine neuen Plugin-Tests). |
| I-Q2 launch_testing-Suite | **A** — full Suite | ~150 Zeilen Python-File für `real.launch.py` loopback. Headless-CI-fähig. Mutter-Plan-I.2 Done-Kriterium erfüllt. |
| I-Q3 README-Polish-Tiefe | **A** — Quick-Start + Parameter-Tabelle + Topics + Echo-State-Hinweis | ~80 Zeilen-Block am Anfang von `hexapod_hardware/README`. Deckt alle 6 Mutter-Plan-I.3-Items ab. |

---

## Was offen war (vor Plan-Freigabe)

### Frage 1 — `tcflush`-Fix (I.2 + I.3) jetzt machen?

- **A (mein Vorschlag): ja, jetzt machen.** Kleiner Fix (ein-Liner +
  RCLCPP_WARN-Fallback), eliminiert die kosmetische WARN aus
  Stage H H-T4, plus ein neuer Unit-Test der das Verhalten pinnt
  (verhindert künftige Regression). 209/0 Test-Total am Ende.
- B: nicht jetzt — als 🟢 später-Item belassen. Stage I dann nur
  launch_testing + README-Polish.

### Frage 2 — launch_testing-Suite I.4 jetzt bauen?

- **A (mein Vorschlag): ja, full Suite.** Mutter-Plan I.2 verlangt's
  explizit. ~150 Zeilen Python, headless-CI-fähig. Smoke: real.launch.py
  loopback → controller_manager + Plugin + 7 Controller active → 10 s
  kein Crash → sauberes Shutdown.
- B: minimal — nur `ros2 launch --print-description` als headless
  Syntax-Check (~30 Zeilen). Schwächer aber schneller. Aber dann ist
  Done-Kriterium I.2 nicht erfüllt.
- C: keine — User-Smoke aus G-T4 reicht. Aber dann ist I.2 nicht
  erfüllt und Mutter-Plan-Done-Kriterium nicht abgedeckt.

### Frage 3 — README-Polish-Tiefe (I.10)?

- **A (mein Vorschlag): Quick-Start-Block am Anfang + Parameter-
  Tabelle + Topics-Klarstellung + Echo-State-Hinweis (gemäß Skizze
  oben in der Plan-Doku).** Deckt alle 6 Mutter-Plan-I.3-Items ab.
  ~80 Zeilen-Block am Anfang des sehr langen README. Bestehende
  Stage-Sektionen bleiben unverändert (Cross-References dorthin).
- B: minimal — nur die fehlenden 2 Items aus der I.3-Checkliste
  („Topics", „Beispiel-Launch") als kurze 1-Liner ergänzen, keinen
  Quick-Start-Block. Weniger Doku-Aufwand, aber schwächere Onboarding-
  Erfahrung für jemand der das README zum ersten Mal liest.
- C: zusätzliche Konsolidierung — README ist 1200+ Zeilen, einige
  Stage-spezifischen Sektionen könnten in progress.md ausgelagert
  werden. Großer Refactor, eigener Aufwand. Eher Stage J oder Phase
  10.

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt Plan + 3 Fragen → Antworten
2. ☐ Bei Bedarf Plan anpassen
3. ☐ `tcflush`-Fix in SerialPort + neuer Unit-Test (I.2 + I.3)
4. ☐ `colcon build hexapod_hardware && colcon test`: 209/0 grün (I-T2)
5. ☐ launch_testing-Suite + CMake-/package.xml-Updates (I.4 + I.5 + I.6)
6. ☐ `colcon build && colcon test hexapod_bringup`: launch_testing grün (I-T3)
7. ☐ README-Polish (I.10): Quick-Start-Block oben einfügen (I-T4)
8. ☐ User-Smokes I-T5 + I-T6 (Boot-Garbage-Regression + sim.launch.py)
9. ☐ Kritischer Self-Review (CLAUDE.md §4)
10. ☐ Doku-Updates (`hexapod_hardware/README` Status + Stufentabelle, `progress.md`)
11. ☐ Stage-J-Übergabe-Items vorbereiten (Liste was J zu tun hat)
12. ☐ Fertig-Meldung für User-Commit

Mit Stage I sind alle **Plugin-Code- und Doku-Polish-Items
abgeschlossen**. Stage J wird dann reine Phasen-Abschluss-Aktion
(`name`-Rename in URDF, git tag `phase-9-done`, `PHASE.md` auf Phase 10).

---

## Plan-Korrekturen während Implementation (2026-05-16)

Zwei substanzielle Plan-Drifts:

1. **I-Q1 (tcflush-Fix) zurückgezogen direkt nach Plan-Freigabe.** Beim
   Sondieren von `serial_port.cpp` direkt vor Code-Edit entdeckt: der
   `::tcflush(fd_, TCIOFLUSH)` ist bereits in `configure_termios()`
   Zeile 136 implementiert, mit exakt der Begründung die ich vorgeschlagen
   hatte. Mein „Fix" wäre ein nutzloser Duplikat-Code gewesen. **User-
   Re-Entscheidung:** Variante A — Fix zurückziehen, WARN als
   known-cosmetic im README dokumentieren (Quick-Start-Block in I.10
   hat dafür einen eigenen Abschnitt). Bullets I.2 + I.3 als „zurückgezogen"
   markiert; I-T5 als „entfällt". 208/0 Test-Total bleibt (kein neuer
   Plugin-Test). **Lesson:** vor Plan-Schreibung kurz den Ziel-Code lesen
   um zu sehen ob der vorgeschlagene Fix schon da ist. Hätte 1 Min
   gekostet und diese Plan-Korrektur erspart.

2. **launch_testing-Linter-Iterationen.** Mein erster Test-File-Wurf
   hat 4 verschiedene Linter-Failures produziert die in 3 Build-Iterationen
   gefixt werden mussten:
   - **copyright** (3 Files): meine Apache-Header-Inline-Notation war
     anders als die ament_copyright-Standard-Form. Plus: bestehende
     `launch/sim.launch.py` hatte gar keinen copyright-Header — wurde
     bisher nicht gelintet weil `add_launch_test()` neu durch I.5 in
     den BUILD_TESTING-Block kam und damit den Linter-Scope auf diese
     Datei erweitert hat. Stage I hat also retroaktiv einen Stage-4-
     Header-Drift mitgefixt.
   - **pep257 D213** in `real.launch.py`: docstring-summary auf erster
     Zeile statt zweiter. Fix: Newline nach `"""` einfügen.
   - **pep257 D403** in 2 Test-Methoden-Docstrings: `ListHardwareComponents`
     und `ListControllers` als erstes Wort wurden als nicht-capitalized
     erkannt. Fix: `Verify` vorne dranschreiben.
   - **flake8 F401**: `import launch_ros.actions` war unbenutzt (weil
     ich `IncludeLaunchDescription` statt `Node` benutze) → entfernt.
   - **flake8 I100** (2x): Import-Order. Standard für flake8-import-order
     in ament_flake8 ist alphabetische Sortierung innerhalb derselben
     Gruppe; `launch_ros.substitutions` muss vor `launch_testing.actions`,
     etc.

   **Lesson:** für künftige neue Python-Test-Files in ROS2-Paketen
   direkt ein bestehendes Beispiel als Vorlage nehmen
   (z.B. `launch_testing_ros/examples/talker_listener_launch_test.py`)
   und Imports + Docstrings 1:1 dem Style folgen — spart die
   Iteration-Schleife.
