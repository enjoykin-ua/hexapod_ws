# Phase 9 — Stufe I — Test-Anleitung

**Was geprüft wird:** Polish-Anteile vor Phase-9-Abschluss in Stage J.
Konkret: launch_testing-Suite für `real.launch.py` (loopback) läuft
headless-CI grün; `hexapod_hardware/README` hat einen vollständigen
Quick-Start-Block am Anfang; bestehende 208 Plugin-Tests und sim.launch.py-
Bringup sind regression-frei.

**Was NICHT in I ausgeführt wird:**
- Plugin-API-Migration auf `on_export_*_interfaces()` (out-of-scope,
  alte API gewinnt sowieso solange Override non-empty)
- URDF-`<ros2_control name>`-Rename (Stage J Polish)
- echte Servo2040-Anbindung (Stage H hat das schon)

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select hexapod_bringup hexapod_hardware
source install/setup.bash
```

> In jedem neuen Terminal beide Source-Zeilen erneut ausführen.

---

## Test I-T1 — Build grün

```bash
colcon build --packages-select hexapod_bringup --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`, keine
`warning:`. Die neue launch_testing-Datei
`test/launch/test_real_launch_loopback.py` ist im build-tree registriert.

---

## Test I-T2 — `hexapod_hardware`-Tests weiter 208/0

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --test-result-base build/hexapod_hardware --verbose | tail -3
```

**Erwartung:** `Summary: 208 tests, 0 errors, 0 failures, 20 skipped` —
identisch zum Stage-H-Endstand. Plugin in Stage I nicht angefasst,
strikt 0 Diff erwartet.

---

## Test I-T3 — launch_testing-Smoke für real.launch.py loopback

```bash
colcon test --packages-select hexapod_bringup
colcon test-result --test-result-base build/hexapod_bringup --verbose | tail -3
```

**Erwartung:** `Summary: 18 tests, 0 errors, 0 failures, 0 skipped`
(3 launch_test-Cases + 15 Lint-Subtests). Die drei launch_test-Cases:

| Test | Was geprüft wird |
|---|---|
| `test_hardware_component_active` | `controller_manager/list_hardware_components`-Service liefert genau 1 Komponente mit `plugin_name=hexapod_hardware/HexapodSystemHardware` im state `LIFECYCLE_PRIMARY_STATE_ACTIVE` (id=3) innerhalb 30 s Service-Verfügbarkeit + 10 s Active-State-Erreichung |
| `test_all_controllers_active` | `controller_manager/list_controllers`-Service zeigt alle 7 Controller (`joint_state_broadcaster` + 6× `leg_X_controller`) als `active`. 45 s Retry-Loop für langsame CI-Container, OnProcessExit-Chain-Latenz |
| `test_no_error_exit_codes` (post-shutdown) | Keiner der gelaunchten Prozesse exit'd mit unerwartetem Code. Akzeptiert: `0` (sauber), `-2` (SIGINT von launch_testing-Shutdown), `-15` (SIGTERM für noch-laufende Spawner) |

Headless ausführbar — kein Display, kein USB-Device, kein Servo2040
nötig (loopback).

---

## Test I-T4 — README-Sanity-Check (manuell)

Öffne `src/hexapod_hardware/README.md` und prüfe den neuen Quick-Start-
Block am Anfang (zwischen Status-Zeile und „Was dieses Paket tut"-Sektion):

- ✅ Markdown-Block rendert sauber (Codeblocks, Tabellen, Listen)
- ✅ Die 4 Aufruf-Beispiele matchen die LaunchArgs von `real.launch.py`
  (default, `loopback_mode:=true`, `serial_port:=`, kombiniert)
- ✅ Plugin-Parameter-Tabelle (3 Zeilen: serial_port, calibration_file,
  loopback_mode) hat korrekte Defaults wie in
  [`hexapod.urdf.xacro`](../../../src/hexapod_description/urdf/hexapod.urdf.xacro)
- ✅ Topics-Tabelle (5 Topics) entspricht dem real.launch.py-Setup
  (JSB + 6× JTC → /joint_states + follow_joint_trajectory-Actions)
- ✅ Echo-State-Limitation hat 4 Konsequenzen-Bullets
- ✅ „Bekannte kosmetische WARN beim Boot"-Hinweis erklärt das
  USB-CDC-Boot-Garbage-Verhalten aus Stage H

---

## Test I-T5 — *entfällt*

Ursprünglich war I-T5 als „USB-Boot-Garbage-Regression nach tcflush-Fix"
geplant. Da Stage I.2 (tcflush-Fix) zurückgezogen wurde (Code existiert
bereits in `serial_port.cpp` Zeile 136), entfällt der Regressions-Test.
Die WARN ist als bekannt-kosmetisch in der README dokumentiert.

---

## Test I-T6 — Sim-Pfad weiter funktional (sim.launch.py-Regression)

Analog Stage F/G/H-Pattern: auch wenn Stage I nicht direkt am
sim.launch.py-Code arbeitet, hat Stage I 2 Copyright-Header in
`launch/*.py` geändert (von keine zu Apache-2.0) und neue
launch_testing-Files dazugegeben. Sanity-Check dass das alles nicht
den Sim-Pfad bricht.

**Terminal 1:**
```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch hexapod_bringup sim.launch.py
```

**Erwartung:** identisch zu Stage F's F-T8a — Gazebo öffnet,
Hexapod-Modell sichtbar, alle 7 Controller active nach ~3 s.

**Terminal 2 (optional):**
```bash
ros2 control list_controllers
```

**Erwartung:** 7 Zeilen `active` (wie F-T8a).

### Cleanup
Ctrl-C in Terminal 1.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| I-T1 Build-Warnung `launch_testing_ament_cmake nicht gefunden` | `<test_depend>launch_testing_ament_cmake</test_depend>` fehlt in package.xml | Eintrag ergänzen + rebuild |
| I-T2 Plugin-Tests-Anzahl != 208 | jemand hat in Stage I doch Plugin-Code angefasst (sollte nicht passieren) | `git diff src/hexapod_hardware/src/` — falls Diff: dokumentieren in progress.md |
| I-T3 `test_hardware_component_active` Timeout 30 s | controller_manager-Service nicht verfügbar; Plugin-Loading scheitert | Logs aus dem launch_testing-Process-Output prüfen (`/tmp/launch_testing*-stderr.log`). Häufig: `pluginlib not found` → `colcon build hexapod_hardware` |
| I-T3 `test_all_controllers_active` Timeout 45 s | Spawner-Chain hängt — OnProcessExit-Event nicht gefeuert | Logs prüfen ob `[spawn_joint_state_broadcaster]: Configured and activated joint_state_broadcaster` erschien |
| I-T3 `test_no_error_exit_codes` Failure mit exit_code != 0/-2/-15 | echter Crash eines Prozesses | exit_code im Failure-Output anschauen; sucht im stderr-Log nach Stack-Trace |
| I-T3 flake8 I100 Import-Order-Failure | Imports nicht alphabetisch sortiert nach Standard | ament_flake8 verwendet `flake8-import-order` mit google-Style — Reihenfolge: stdlib, third-party (alphabetisch innerhalb Gruppe), eigene |
| I-T3 pep257 D213/D403/D202 | Docstring-Format passt nicht | Linter-Output zeigt Zeile + Regel-Code — siehe [pydocstyle-Doku](http://www.pydocstyle.org/) |
| I-T3 copyright-Linter fail | `# Copyright YYYY ...` + Apache-Header fehlt | Header aus `launch_testing_ros/examples/talker_listener_launch_test.py` kopieren |
| I-T6 sim.launch.py crash nach Stage-I-Änderungen | Copyright-Header-Hinzufügung hat sim.launch.py beschädigt | `git diff src/hexapod_bringup/launch/sim.launch.py` — sollte nur Header-Lines diff zeigen, kein Code |

---

## Statusmeldung an Claude

- `I-T1–I-T6 alle grün` → **Stufe I komplett.** Weiter mit **Stufe J**
  (Phase-9-Abschluss: optional `<ros2_control name>`-Rename, git tag
  `phase-9-done`, PHASE.md auf Phase 10)
- `I-TX failt: <Symptom>` → ich diagnostiziere
- I-T1/T2/T3 sind CI (kein User-Input nötig); I-T4 ist manueller
  Read-Through (kann ich oder du machen); I-T6 ist User-Smoke

Vollausgabe nur bei Fehler; sonst kurz „I-TX grün" reicht.
