# Phase 9 — Stufe D.3 — Test-Anleitung

**Was geprüft wird:** Der `on_init`-Lifecycle-Hook validiert eine
synthetische `HardwareInfo`, parst die drei Hardware-Parameter
(`serial_port`, `calibration_file`, `loopback_mode`), lädt die
Calibration-YAML, baut die URDF→Servo-Pin-Übersetzungs-Tabelle, und
allokiert die State-Vektoren. Edge-Cases (falsche Joint-Anzahl,
fehlende oder ungültige Parameter, unbekannte Joints, permutierte
Reihenfolge, leere URDF-Limits) werden korrekt behandelt.

**Was NICHT in D.3 geprüft wird:**
- Serial-Port-Öffnen / Reader-Thread-Start → **D.4** (`on_configure`)
- ENABLE_SERVO-Sequenz → **D.5** (`on_activate`)
- write()/read() mit Pulse-Konversion + Joint→Pin-Mapping in Aktion → **D.6**

D.3 ist ein **C++-Unit-Test-Smoke-Test** mit synthetischer
`HardwareInfo` (von Hand gebaut, nicht aus echter URDF). Kein ROS-Stack,
keine Hardware.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.3.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `Summary: 1 package finished [X.XXs]`
- Kein `stderr: hexapod_hardware`-Block
- Keine `warning:`-Zeilen

---

## Test D.3.2 — Volle Test-Suite grün (9/9)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 156 tests, 0 errors, 0 failures, 15 skipped`

Die neun Tests:
1. `test_calibration` (30 gtest-Cases)
2. `test_serial_port` (14 gtest-Cases)
3. `test_servo2040_protocol` (36 gtest-Cases)
4. `test_servo2040_reader` (17 gtest-Cases)
5. **`test_hexapod_system`** — neu in D.3 (14 gtest-Cases)
6. `cppcheck`
7. `lint_cmake`
8. `uncrustify`
9. `xmllint`

---

## Test D.3.3 — Alle 14 on_init-gtest-Cases sichtbar machen

```bash
./build/hexapod_hardware/test_hexapod_system
```

**Erwartung am Ende:**
```
[==========] 17 tests from 1 test suite ran. (~16 ms total)
[  PASSED  ] 17 tests.
```

Die einzige Suite `HexapodSystemInit`:

| Test | Was geprüft wird |
|---|---|
| `ValidHardwareInfoSucceeds` | Happy-Path mit 18 canonical Joints + alle 3 Params → SUCCESS, 18 state + 18 command interfaces exportiert |
| `ExportedInterfaceNamesMatchUrdfOrder` | Reihenfolge der exportierten Interfaces entspricht URDF-Reihenfolge |
| `RejectsTooFewJoints` | 17 Joints → ERROR |
| `RejectsTooManyJoints` | 19 Joints → ERROR |
| `RejectsMissingCalibrationFile` | Param fehlt → ERROR |
| `RejectsEmptyCalibrationFile` | Param = "" → ERROR |
| `RejectsNonExistentCalibrationFile` | Pfad zeigt auf nicht-existente Datei → ERROR (clean, kein Crash) |
| **`AcceptsAllBoolStringsForLoopback`** | 11 verschiedene true/false-Strings (case-insensitive: TRUE/True/true/1/yes/no/…) werden akzeptiert |
| `RejectsGarbageLoopbackString` | "maybe" → ERROR |
| `LoopbackDefaultsToFalseIfOmitted` | Param fehlt komplett → default `false` → SUCCESS |
| **`AcceptsPermutedJointOrder`** | URDF-Joint-Liste reversed → SUCCESS, `export_command_interfaces` behält URDF-Reihenfolge (Servo-Pin-Mapping passiert intern via `joint_to_output_idx_`) |
| `RejectsUnknownJointName` | Joint-Name nicht im YAML → ERROR (mit Joint-Name in der Log-Message) |
| `ParsesJointLimitsFromUrdf` | Asymmetrische Limits in URDF (z.B. `-1.2, +0.8`) → SUCCESS |
| `EmptyJointLimitsFallBackToDefaults` | Leere `min`/`max`-Strings → WARN-Log + SUCCESS (Fallback auf ±1.57) |
| **`RejectsSwappedJointLimits`** | `lower=+1.57, upper=-1.57` (vertauschtes URDF-Macro) → FATAL + ERROR (Mirroring lebt in `direction`, nicht in Limits) |
| **`RejectsEqualJointLimits`** | `lower==upper==0` (eingerasteter Joint, keine Range) → ERROR |
| **`FailedReinitDoesNotMutateTable`** | Strong-Exception-Guarantee: nach failed re-init bleibt das vorige `joint_to_output_idx_`-Mapping erhalten |

---

## Test D.3.4 — Permutations-Test fokussiert

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*Permuted*:*ExportedInterfaceNamesMatchUrdfOrder*"
```

**Erwartung:** beide Tests passed.

Hintergrund: bei permutierter URDF-Joint-Liste wird der `export_command_interfaces`-
Output nach URDF-Reihenfolge ausgegeben (so will es ros2_control), aber
intern sind die Servo-Pins anders zugeordnet. Die korrekte Anwendung der
Übersetzungs-Tabelle wird in **D.6** (write/read) funktional verifiziert
— hier in D.3 prüfen wir nur, dass die Tabelle ohne Crash gebaut wird
und die Exports konsistent sind.

---

## Test D.3.5 — Log-Output beim Happy-Path

Manuell wenn gewünscht — `./build/hexapod_hardware/test_hexapod_system --gtest_filter="*Valid*"`
sollte u.a. zeigen:

```
[INFO] [...] [hexapod_hardware]: HexapodSystemHardware::on_init starting (info_.joints.size=18)
[INFO] [...] [hexapod_hardware]: Config: serial_port=/dev/ttyACM0,
       calibration_file=.../servo_mapping.yaml, loopback_mode=true
[INFO] [...] [hexapod_hardware]: on_init complete — 18 joints mapped to
       18 servo pins, calibration loaded from .../servo_mapping.yaml
```

Bei Fehler-Tests (`Rejects*`): `[FATAL]`-Log mit klarer Message vor dem ERROR-Return.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `ValidHardwareInfoSucceeds` schlägt fehl mit YAML-Fehler | `SOURCE_DIR_FOR_TESTS`-Pfad zeigt auf falschen Ort | `CMakeLists.txt` prüfen, `target_compile_definitions(test_hexapod_system PRIVATE SOURCE_DIR_FOR_TESTS=...)` |
| `RejectsTooFewJoints` zeigt SUCCESS statt ERROR | Joint-count-Check in on_init fehlt | `if (info_.joints.size() != NUM_SERVOS)` in `on_init` prüfen |
| `AcceptsAllBoolStringsForLoopback` failt bei "TRUE" | Bool-Parser ist case-sensitive | `parse_bool()`-Helper in `hexapod_system.cpp` prüfen — `std::transform` für lower-case |
| `AcceptsPermutedJointOrder` failt mit ERROR | `joint_to_output_idx_` baut nicht korrekt auf, oder duplicate-Detection wirft fälschlich | Tabelle-Aufbau-Schleife + `std::adjacent_find`-Check prüfen |
| `RejectsUnknownJointName` zeigt SUCCESS | `Calibration::output_idx_for_joint` wirft nicht oder Exception wird gefangen ohne ERROR-Return | Exception-Handling-Block in der `joint_to_output_idx_`-Aufbau-Schleife |

---

## Statusmeldung an Claude

- `D.3.1–D.3.3 alle grün` → weiter mit **D.4** (`on_configure` + `on_cleanup`: Serial-Port öffnen/schließen, Reader-Thread starten/stoppen, loopback-skip)
- `D.3.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
