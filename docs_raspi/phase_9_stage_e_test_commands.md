# Phase 9 — Stufe E — Test-Anleitung

**Was geprüft wird:** Das Plugin `hexapod_hardware/HexapodSystemHardware`
ist via **pluginlib** zur Laufzeit ladbar — d.h. das XML-Manifest, der
`<hardware_interface plugin="..."/>`-Export in `package.xml`, der
`pluginlib_export_plugin_description_file`-Aufruf in `CMakeLists.txt`
und die installierte `libhexapod_hardware.so` passen zusammen, sodass
`pluginlib::ClassLoader` die Klasse findet, instanziiert und einen
sauberen `on_init` durchlaufen lässt.

**Was NICHT in E in CI geprüft wird:**
- End-to-End-Lifecycle über `controller_manager` (kommt in Stage F/G/H
  mit echtem `real.launch.py`)
- `ros2 control list_hardware_components` (braucht laufenden
  controller_manager — dito Stage F/G)
- `launch_testing` mit `ros2_control_node` (überzogen für die
  „Pluginlib lädt"-Frage; Plan-Doku §"Was Stage E NICHT macht")

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
```

---

## Test E.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine
`warning:`. Die `hexapod_hardware.xml` wird nach
`install/hexapod_hardware/share/hexapod_hardware/` kopiert und der
Resource-Index-Eintrag unter
`share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware`
angelegt.

---

## Test E.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile (ungefähr): `Summary: 208 tests, 0 errors, 0 failures, 20 skipped`
  - Davon **154 reine gtest-Cases** über sieben Test-Binaries (vorher 151,
    +3 für die neue `PluginRegistration`-Suite)
  - Der Rest sind Lint-Subtests (cppcheck, lint_cmake, uncrustify, xmllint,
    plus per-target-Wrapper)

---

## Test E.3 — Stage-E-Tests fokussiert (3 Tests, < 100 ms)

```bash
./build/hexapod_hardware/test_plugin_registration
```

**Erwartung:**
```
[==========] 3 tests from PluginRegistration (< 100 ms total)
[  PASSED  ] 3 tests.
```

Die drei Tests:

| Test | Was geprüft wird |
|---|---|
| `PluginIsLoadableViaPluginlib` | `pluginlib::ClassLoader<SystemInterface>::getDeclaredClasses()` liefert eine Liste die `hexapod_hardware/HexapodSystemHardware` enthält; `createSharedInstance()` wirft nicht und gibt non-null zurück |
| `LoadedPluginPassesOnInit` | Geladenes Plugin besteht `on_init` mit voll-validem `HardwareInfo` (loopback_mode=true, alle 18 Joints, calibration_file gesetzt) → `CallbackReturn::SUCCESS` |
| `LoadedPluginExposes18Interfaces` | Nach `on_init` liefern `export_state_interfaces()` und `export_command_interfaces()` jeweils 18 Einträge (Spec aus CLAUDE.md §1: 6 Beine × 3 Joints) |

---

## Test E.4 — Bestehende Stage-A–D-Tests weiter grün (Refactor-Sicherheit)

Der Test-Helper-Refactor (Variante B in der Stage-E-Plan-Doku) hat
`make_joint`/`make_valid_info`/`make_params` aus `test_hexapod_system.cpp`
nach `test/test_helpers.hpp` extrahiert. Damit darf nichts an den 39 D.x-
Tests gebrochen sein:

```bash
./build/hexapod_hardware/test_hexapod_system 2>&1 | tail -3
```

**Erwartung:** `[  PASSED  ] 39 tests.` (Stage D.3 + D.4 + D.5 + D.6 +
D.7-Erweiterungen).

---

## Test E.5 — Resource-Index-Eintrag manuell sichtbar

```bash
cat install/hexapod_hardware/share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware
```

**Erwartung:** Eine Zeile, die auf das installierte Manifest zeigt:
```
share/hexapod_hardware/hexapod_hardware.xml
```

(Diesen Resource-Index nutzt `pluginlib::ClassLoader` zur Auto-Discovery
aller Pakete im AMENT_PREFIX_PATH — ohne den Eintrag findet pluginlib
das Plugin nicht, auch wenn die `.so` da ist.)

---

## Test E.6 — Manifest-XML valid

```bash
xmllint --noout install/hexapod_hardware/share/hexapod_hardware/hexapod_hardware.xml && echo "VALID"
```

**Erwartung:** Output `VALID`. Kein Fehler-Output (bei XML-Syntax-Fehler
würde xmllint mit Exit-Code ≠ 0 abbrechen und die fehlerhafte Stelle
ausgeben).

---

## Test E.7 — Shared-Library-Symbole alle resolved

```bash
ldd install/hexapod_hardware/lib/libhexapod_hardware.so
```

**Erwartung:** Volle Liste der dynamisch gelinkten Libraries (ROS2-,
yaml-cpp-, libstdc++-, libc-Pfade), **keine `not found`-Zeile**. Wenn
`not found` erscheint, fehlt eine runtime-Dependency und pluginlib
würde beim `createSharedInstance` mit `LibraryLoadException` abbrechen.

---

## Test E.8 — `ros2 control list_hardware_components` ist NICHT Teil Stage E

Dieser Befehl braucht einen **laufenden** `controller_manager` mit
geladener URDF — beides bringt erst Stage F (URDF-Switch
Sim↔HW) plus Stage G (`real.launch.py`). Aktueller Status:

```bash
ros2 control list_hardware_components 2>&1 | head -3
```

**Erwartung jetzt:** `Could not contact service /controller_manager/list_hardware_components`
(weil keiner läuft) — das ist normal in Stage E. Der echte E2E-Smoke-Test
folgt mit Stage G.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `PluginIsLoadableViaPluginlib` failt mit „not found in pluginlib registry" | Resource-Index-Eintrag fehlt nach Build | `pluginlib_export_plugin_description_file(hardware_interface hexapod_hardware.xml)` in CMakeLists prüfen, dann clean rebuild (`rm -rf build install && colcon build`) |
| `PluginIsLoadableViaPluginlib` failt mit „createSharedInstance threw" | Symbol nicht exportiert oder Manifest-`type=`-Mismatch | `<class type="hexapod_hardware::HexapodSystemHardware">` in `hexapod_hardware.xml` muss exakt dem FQN der Klasse entsprechen; PLUGINLIB_EXPORT_CLASS-Makro im `hexapod_system.cpp` prüfen |
| `LoadedPluginPassesOnInit` failt mit `ERROR` | Calibration-YAML nicht gefunden oder HardwareInfo-Mismatch | Im Test-Output nach `RCLCPP_FATAL`-Zeile suchen (Zeit-Stempel-Block); `SOURCE_DIR_FOR_TESTS`-Define im CMake prüfen |
| `LoadedPluginExposes18Interfaces` failt mit Anzahl ≠ 18 | Plugin-NUM_SERVOS geändert oder on_init hat Joints nicht voll registriert | Wenn Hardware-Revision gewollt: Spec in CLAUDE.md §1 + diesen Test synchron updaten. Sonst: on_init-Implementierung prüfen |
| Test E.4 (D.x-Suite) failt nach Helper-Refactor | `using`-Declaration im umgestellten `test_hexapod_system.cpp` fehlt eine der drei Helper-Funktionen | `using hexapod_hardware_test::make_{joint,valid_info,params};` muss vorhanden sein, sonst Name-Lookup-Fehler |
| Resource-Index-File fehlt (Test E.5) | Build hat das Plugin nicht installiert | `colcon build` nochmal mit `--cmake-clean-cache`; `install/`-Tree komplett wegwerfen falls hartnäckig |
| `xmllint VALID` failt | Syntax-Fehler im Manifest (z.B. unschließendes Tag) | xmllint zeigt Zeile + Spalte; Manifest entsprechend fixen |
| `ldd not found`-Zeilen | Runtime-Dep nicht installiert | Das fehlende `lib*.so` per apt installieren (Output zeigt welches); typisch passiert das nicht, weil `find_package(...)` im CMake die Build-Deps schon erzwingt |
| Build-Warnung `export_state_interfaces deprecated` taucht wieder auf | `#pragma GCC diagnostic`-Block in `test_plugin_registration.cpp` Test 3 weggefallen | Pragma-push/pop um die zwei `EXPECT_EQ`-Calls wiederherstellen, oder Plugin auf `on_export_*_interfaces()` migrieren (eigener Refactor) |

---

## Statusmeldung an Claude

- `E.1–E.7 alle grün` → **Stufe E komplett.** Weiter mit **Stufe F**
  (URDF-Switch zwischen `gz_ros2_control` Sim und `hexapod_hardware`,
  plus `controllers.real.yaml`)
- `E.8` als „contact service failed" beobachtet — **erwartet**, kein Bug
- `E.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
