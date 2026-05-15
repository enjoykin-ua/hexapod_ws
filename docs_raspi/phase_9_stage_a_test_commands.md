# Phase 9 — Stufe A — Test-Anleitung

**Was geprüft wird:** Das Paket `hexapod_hardware` ist sauber aufgesetzt
(Build grün, Tests grün, pluginlib-Resource-Index korrekt installiert,
alle Install-Artefakte am erwarteten Platz).

**Was NICHT in Stufe A geprüft wird (kommt später):**
- Plugin wird tatsächlich von `controller_manager` geladen → **Stufe E + G**
- Loopback-Modus → **Stufe D**
- Echte USB-Kommunikation mit Servo2040 → **Stufe H**

Diese Stufe ist ein reiner **Compile- und Install-Smoke-Test**. Kein
ROS-Stack muss laufen, kein Servo2040 angeschlossen sein.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test A.1 — Build grün

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- Letzte Zeile zeigt: `Summary: 1 package finished [X.XXs]`
- **Kein** Block mit `stderr:` (keine Compile-Warnings)
- Keine Zeilen mit `error:` oder `failed`

---

## Test A.2 — Tests grün (5/5)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `100% tests passed, 0 tests failed out of 5`
- Die fünf Tests sind:
  1. `test_calibration` (gtest-Stub)
  2. `cppcheck` (statische Code-Analyse)
  3. `lint_cmake` (CMake-Style)
  4. `uncrustify` (C++-Style)
  5. `xmllint` (XML-Validierung von `package.xml` + `hexapod_hardware.xml`)

Zusätzlich:
```bash
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:** `Summary: 5 tests, 0 errors, 0 failures, 0 skipped`

---

## Test A.3 — Install-Artefakte vorhanden

```bash
source install/setup.bash
ls -la install/hexapod_hardware/lib/libhexapod_hardware.so
ls -la install/hexapod_hardware/share/hexapod_hardware/hexapod_hardware.xml
ls -la install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml
ls -la install/hexapod_hardware/include/hexapod_hardware/
```

**Erwartung:**
- `libhexapod_hardware.so` existiert (Shared Library mit dem Plugin)
- `hexapod_hardware.xml` existiert (pluginlib-Manifest)
- `servo_mapping.yaml` existiert (Kopie aus fw-Repo)
- Im `include/`-Verzeichnis liegen drei Header:
  - `calibration.hpp`
  - `hexapod_system.hpp`
  - `servo2040_protocol.hpp`

---

## Test A.4 — Shared-Library hat alle Dependencies aufgelöst

```bash
ldd install/hexapod_hardware/lib/libhexapod_hardware.so | grep -E "not found|hardware_interface|pluginlib|yaml"
```

**Erwartung:**
- **Keine** Zeile mit `not found`
- Mindestens diese Libraries werden gelinkt:
  - `libhardware_interface.so` (aus `/opt/ros/jazzy/lib/`)
  - `libpluginlib*.so` (aus `/opt/ros/jazzy/lib/`)
  - `libyaml-cpp.so.0.8` (aus `/usr/lib/x86_64-linux-gnu/`)

---

## Test A.5 — pluginlib findet das Plugin

```bash
ros2 pkg prefix hexapod_hardware
```

**Erwartung:** Output ist `/home/enjoykin/hexapod_ws/install/hexapod_hardware`

```bash
cat install/hexapod_hardware/share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware
```

**Erwartung:** Output ist genau `share/hexapod_hardware/hexapod_hardware.xml`
(ohne Newline am Ende ist OK). Das ist der Hinweis-Eintrag, durch den
`controller_manager` in späteren Stufen das Plugin findet.

```bash
cat install/hexapod_hardware/share/hexapod_hardware/hexapod_hardware.xml
```

**Erwartung:** Die XML enthält:
- `<library path="hexapod_hardware">`
- `<class name="hexapod_hardware/HexapodSystemHardware"`
- `base_class_type="hardware_interface::SystemInterface"`

---

## Test A.6 — `package.xml`-Export ist korrekt

```bash
grep -A 1 "<export>" src/hexapod_hardware/package.xml
```

**Erwartung:** Innerhalb des `<export>`-Blocks steht:
```xml
<hardware_interface plugin="${prefix}/hexapod_hardware.xml"/>
```

Das ist der Mechanismus, durch den ament beim Build die Resource-Index-
Datei aus Test A.5 anlegt.

---

## Test A.7 — Keine versteckten Probleme im Build-Log

```bash
grep -E "warning:|error:" log/latest_build/hexapod_hardware/stdout_stderr.log | head -20
```

**Erwartung:** Output ist **leer** (keine Treffer).

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| Build-Fehler `yaml-cpp not found` | `libyaml-cpp-dev` nicht installiert | `sudo apt install libyaml-cpp-dev` |
| Build-Fehler `hardware_interface not found` | ROS-Setup nicht gesourced | `source /opt/ros/jazzy/setup.bash` |
| `uncrustify`-Test failt mit Code-Style-Divergenz | Nach Edit irgendwo Zeile zu lang oder Einrückung verschoben | Diff lesen, Vorschlag 1:1 anwenden |
| `cppcheck`-Test failt | Ungenutzte Variable oder unsafe pointer | Konkrete Warnung im Log lesen |
| `ldd` zeigt `not found` für lib | `LD_LIBRARY_PATH` / `install/setup.bash` nicht gesourced | `source install/setup.bash` aus `~/hexapod_ws` |
| `ros2 pkg prefix` findet Paket nicht | Setup nicht gesourced | siehe oben |

---

## Statusmeldung an Claude

Nach Durchlauf der sieben Tests reicht eine knappe Rückmeldung:
- `A.1–A.7 alle grün` → wir können mit Stufe B (Frame-Encoder/Decoder)
  weitermachen
- `A.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe der Logs ist nicht nötig — nur bei Fehlern den relevanten Teil.
