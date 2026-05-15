# Phase 9 — Progress-Tracker

**Phase:** ROS2-Plugin `hexapod_hardware`
**Plan:** [phase_9_hexapod_hardware.md](phase_9_hexapod_hardware.md)
**Aktiv seit:** 2026-05-15

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**.
> Design-Entscheidungen + verworfene Alternativen unten festhalten,
> damit Re-Design später möglich ist ohne Erinnerung.

---

## Design-Entscheidungen vor Stufe A

### Boot-Stagger: Host vs. Firmware → **V1 Host**

- **Final:** `hexapod_hardware::on_activate` schickt 18× `ENABLE_SERVO` mit
  50 ms Pause zwischen den Frames. Firmware bleibt dumm.
- **Konsistenz:** Entspricht `~/hexapod_servo_driver/PROTOCOL.md §5` und
  Phase-7 Design-Entscheidung D.1.
- **Verworfen:**
  - **V2 Firmware-seitiger Single-Frame-Stagger** (neuer Opcode
    `ENABLE_ALL_STAGGERED`) — Grund: würde Phase-7-Abschluss aufreißen
    (neuer Tag, neue Tests), widerspricht „Firmware bleibt dumm"-Prinzip
    aus fw-Repo `CLAUDE.md §1`.
- **Plan-Doku-Korrektur:** `phase_9_hexapod_hardware.md` Stufe-D-Tabelle
  Wording „Servo2040 macht den Stagger" → „Host macht den Stagger".

### YAML-Loader: yaml-cpp vs. handrolled vs. ros-params → **V1 yaml-cpp**

- **Final:** `libyaml-cpp-dev` (System-Paket, 0.8.0 installiert),
  `<depend>yaml-cpp</depend>` in `hexapod_hardware/package.xml`.
- **Begründung:** `yaml-cpp::Emitter` erlaubt programmatisches Schreiben
  der `servo_mapping.yaml` durch das Phase-10-Kalibrierungstool. Bleibt
  menschen-lesbar/editierbar. Standard im ROS-Ökosystem (`yaml-cpp-vendor`
  ist transitive Dep von ros2_control sowieso).
- **Verworfen:**
  - **V2 selber parsen** — Grund: identisches Ergebnis bei mehr
    Wartungsaufwand + Bug-Potenzial. Emitter-Teil müsste auch neu gebaut werden.
  - **V3 rclcpp-Parameter** — Grund: erzwingt flache Parameter-Struktur
    (`joint_0.direction`, …) statt sauberer Map pro Joint. Lifecycle-Kopplung
    macht Initialisierungs-Order kompliziert.

### Pulse-Konversion: 4-Punkt vs. 3-Punkt-Schema → **Option C 3-Punkt piecewise-linear**

- **Final:** YAML-Schema bleibt `pulse_min` + `pulse_zero` + `pulse_max`
  + `direction` pro Joint (so wie `~/hexapod_servo_driver/contrib/servo_mapping.yaml`
  es bereits hat — KEIN extra `pulse_per_rad`-Feld).
- **Konversion zur Laufzeit:** `calibration.cpp` berechnet aus den drei
  Pulse-Werten + URDF-Joint-Limits (`joint_lower`, `joint_upper`) zwei
  Steigungen:
  - linke Hälfte: `(pulse_zero − pulse_min) / |joint_lower|` µs/rad
  - rechte Hälfte: `(pulse_max − pulse_zero) /  joint_upper`  µs/rad
- **Konversionsformel** (piecewise-linear):
  ```
  joint_rad ≥ 0:   pulse_us = pulse_zero + direction · joint_rad · slope_right
  joint_rad < 0:   pulse_us = pulse_zero + direction · joint_rad · slope_left
  ```
- **Begründung:** Die drei Punkte (min, zero, max) sind genau das, was
  ein Kalibrierungs-Tool natürlich misst (jog zum unteren Anschlag →
  `pulse_min` notieren, jog zur Joint-Mitte → `pulse_zero`, jog zum
  oberen Anschlag → `pulse_max`). Piecewise-linear fängt asymmetrische
  Montagen / leicht non-lineare Servos sauber ab.
- **Verworfen:**
  - **Option A (extra `pulse_per_rad`-Feld im YAML):** Grund: redundant,
    weil aus drei Punkten + URDF-Limits ableitbar. Phase-10-Kalibrierung
    müsste das Feld zusätzlich schreiben.
  - **Option B (einzelne Steigung aus `pulse_min`/`pulse_max` und
    `joint_lower`/`joint_upper`):** Grund: nimmt symmetrische Servo-Range
    an, scheitert bei asymmetrischer Servo-Montage gegenüber Joint-Zero.
- **Plan-Doku-Korrektur:** `phase_9_hexapod_hardware.md` Stufe-C-Block
  Wording „Pro Joint: …, `pulse_per_rad`, …" → drei Punkte +
  piecewise-linear-Konversion.

### IMU-Anbindung → **eigenes SensorInterface-Plugin in späterer Phase**

- **Final:** IMU kommt NICHT ins `hexapod_hardware`-Paket. Eigenes Paket
  (z.B. `hexapod_imu_hardware`), eigener `<ros2_control type="sensor">`-Block
  in der URDF, Topic `/imu/data` (`sensor_msgs/Imu`).
- **Begründung:** `ros2_control` trennt `SystemInterface` (Aktoren) und
  `SensorInterface` (Sensoren) bewusst. IMU hängt nicht am Servo2040
  (keine I²C/SPI-Pins frei) sondern direkt am Pi/Desktop.
- **Action für Phase 9:** Keine. URDF-Switch-Block lässt automatisch
  Platz für einen späteren zweiten `<ros2_control>`-Block.

### Echo-State + Reader-Thread → **Konzept, Detail in Stufe D**

- **Konzept:** Reader-Thread liest USB-CDC kontinuierlich, sortiert
  Frames in STATE-Cache + ERROR_REPORT-Queue. `read()`-Callback liest
  nicht-blockierend aus dem Cache (Echo-State aus `last_command_`).
  Polling von `GET_STATE` für Voltage/Current optional (z.B. 5 Hz reicht).
- **Buslast unkritisch:** Bei 50 Hz `SET_TARGETS` + 50 Hz `GET_STATE` ≈
  6.9 kB/s, das sind ~5% der USB-CDC-Full-Speed-Bandbreite (~125 kB/s).
- **Echte Detail-Entscheidung in Stufe D.**

---

## Stufe A — Paket anlegen

> Done-Kriterium A (aus Plan): Paket baut leer grün mit Skelett-Klassen.

- [x] A.1 `phase_9_progress.md` mit Design-Entscheidungen erstellt (2026-05-15)
- [x] A.2 Plan-Doku Stufe C+D Wording korrigiert (Host-Stagger, Option C)
- [x] A.3 Paket `hexapod_hardware` via `ros2 pkg create --build-type ament_cmake` angelegt
- [x] A.4 Verzeichnis-Skelett (`include/`, `src/`, `config/`, `test/`) erstellt
- [x] A.5 Skelett-Header angelegt: `servo2040_protocol.hpp` (Opcodes/Error/Status-Konstanten gespiegelt aus fw-Repo `src/config.hpp`, Frame-API-Forward-Decls), `calibration.hpp` (`ServoCalibration` + `Calibration`-Klasse, Option-C-API), `hexapod_system.hpp` (`HexapodSystemHardware : SystemInterface`, neue `on_init(HardwareComponentInterfaceParams&)`-Signatur für ros2_control 4.44)
- [x] A.6 Skelett-`.cpp`-Dateien angelegt (Stubs return SUCCESS / OK / 0)
- [x] A.7 `package.xml` mit allen Deps + `<hardware_interface plugin="${prefix}/hexapod_hardware.xml"/>`-Export
- [x] A.8 `CMakeLists.txt`: shared lib, `pluginlib_export_plugin_description_file(hardware_interface hexapod_hardware.xml)`, `ament_add_gtest`, Install-Targets für lib/headers/config
- [x] A.9 `hexapod_hardware.xml` (pluginlib-Beschreibung) angelegt
- [x] A.10 `colcon build --packages-select hexapod_hardware` grün (keine Warnungen)
- [x] A.11 `servo_mapping.yaml` aus fw-Repo nach `config/` kopiert
- [x] A.12 `colcon test --packages-select hexapod_hardware` grün (5/5: gtest-Stub, cppcheck, lint_cmake, uncrustify, xmllint)
- [x] A.13 pluginlib-Resource-Index verifiziert: `install/hexapod_hardware/share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware` zeigt auf `share/hexapod_hardware/hexapod_hardware.xml`

**Done-Kriterium A erreicht:** ✅ (am 2026-05-15)

### Stufe-A-Notizen

- **Architektur-Doku und Signatur-Erklärung:** vollständig in
  [`src/hexapod_hardware/README.md`](../src/hexapod_hardware/README.md)
  — dort steht das Klassen-Layout, was die Stubs aktuell tun, und ein
  ausführlicher Abschnitt „Die `on_init`-Signatur — was bedeutet das?"
  mit Erklärung zu C++-Funktions-Signaturen, alter vs. neuer ros2_control-
  API und warum wir direkt die neue benutzen.
- **Test-Anleitung:** [`docs_raspi/phase_9_stage_a_test_commands.md`](phase_9_stage_a_test_commands.md)
  — sieben Smoke-Tests (Build, colcon test, Install-Artefakte, ldd,
  pluginlib-Resource-Index, package.xml-Export, Build-Log-Check).
- **Echo-State im Stub:** `read()` reflektiert `hw_command_positions_[i]`
  direkt in `hw_state_positions_[i]`. Strukturell ist Echo-State bereits
  drin, die Pulse-µs-Konversion über `Calibration` kommt in Stufe D dazu.
- **uncrustify-Style:** ROS-Style umbricht Funktions-Signaturen ab
  ~100 Zeichen. Linter fängt das beim ersten Lauf — Vorschlägen 1:1
  folgen, dann grün.
- **Kein expliziter `controller_manager`-Export nötig:**
  `ament_export_dependencies` listet nur die Build-Deps, nicht
  `controller_manager` — das wird nur zum Laden des Plugins gebraucht,
  nicht für seine API.

---

## Stufe B — Frame-Encoder/Decoder

> Done-Kriterium B (aus Plan): Protokoll-Code mit Unit-Tests, alle grün.

- [x] B.1 CRC-16/CCITT-FALSE bit-by-bit implementiert (Poly 0x1021, Init 0xFFFF, no reflect, XorOut 0x0000)
- [x] B.2 CRC-Selbsttest `crc16("123456789") == 0x29B1` verifiziert
- [x] B.3 COBS encode/decode implementiert (Cheshire & Baker 1999), inkl. 0xFF chain-extension Edge-Case
- [x] B.4 `encode_frame(seq, cmd, payload)`-Helper: baut SEQ+CMD+LEN+PAYLOAD+CRC16-LE, COBS-encodet, hängt Trenner-0x00 an
- [x] B.5 `decode_frame(cobs_bytes)`-Helper: strip optional 0x00, COBS-decode, CRC-Check, Length-Check, gibt `DecodedFrame{seq, cmd, payload}` zurück
- [x] B.6 Spezialisierte Encoder: `encode_set_targets`, `encode_get_state`, `encode_enable_servo`, `encode_reset`
- [x] B.7 Payload-Decoder: `decode_state` (75 Byte STATE-Payload nach `StatePayload`), `decode_error_report` (4 Byte → `ErrorReport`)
- [x] B.8 Unit-Tests `test/test_servo2040_protocol.cpp`: 29 Test-Cases in 5 Suites (Crc16CcittFalse, Cobs, Frame, PayloadDecoders, EndToEnd)
- [x] B.9 `CMakeLists.txt`: zweiter `ament_add_gtest` registriert
- [x] B.10 `colcon build`: grün, keine Warnings
- [x] B.11 `colcon test`: 6/6 grün (test_calibration, test_servo2040_protocol, cppcheck, lint_cmake, uncrustify, xmllint)

**Done-Kriterium B erreicht:** ✅ (am 2026-05-15)

### Stufe-B-Notizen

- **CRC-Implementation:** Bit-by-bit (~16 Zeilen Code) statt Lookup-Table. Host ist nicht throughput-bound — bei 50 Hz × ~78 Byte/Frame liegt der Unterschied bei ~80 ns/Frame. Spart 512 Byte statische Tabelle, ist deutlich lesbarer. Self-Test `0x29B1` für `"123456789"` ist der kanonische Validitäts-Beweis: jede konforme CRC-16/CCITT-FALSE-Implementation liefert exakt diesen Wert.
- **COBS-0xFF-Edge-Case:** Bei genau 254 Nicht-Null-Bytes in Folge endet der Block mit `count=0xFF` — und der Decoder fügt **kein** implizites Null-Byte ein (Chain-Extension-Pattern). Bei `count` ∈ 1..254 fügt der Decoder dagegen immer ein 0x00 hinzu, **außer** wenn es der letzte Block im Stream ist. Tests `BoundaryAt254NonZeroBytes` und `BoundaryAt255NonZeroBytes` decken das ab.
- **Frame-Roundtrip-Symmetrie:** `encode_frame` hängt 0x00-Trenner an; `decode_frame` toleriert sowohl mit als auch ohne Trenner. Damit kann ein späterer Streaming-Reader (Stufe D) je nach Komfort 0x00 weglassen oder mitschicken.
- **Negativer-Pulse-Test:** `int16` ist signed, aber unsere Wire-Konversion arbeitet mit `uint8_t`. Der Test `RoundtripSetTargetsNegativePulse` mit `-1234` verifiziert, dass die Sign-Erhaltung an der Konversions-Grenze funktioniert (`int16 → 2× uint8 LE → zurück`).
- **Test-Vorbild:** Die Test-Vektoren sind teilweise direkt aus `~/hexapod_servo_driver/tools/test_servo2040.py` übernommen (Self-Test 0x29B1, SET_TARGETS 1500 µs → `DC 05`, ENABLE_SERVO Payload-Format). Damit ist Host-/Firmware-Kompatibilität strukturell schon getestet, ohne dass tatsächliche USB-Kommunikation läuft.

### Was Stufe B explizit **nicht** macht

- Kein USB-Port-Handling, keine echte Übertragung — kommt in Stufe D.
- Keine Streaming-Reader-Logik (Bytes häppchenweise einsammeln und auf 0x00 splitten) — auch Stufe D.
- Keine Decoder für `INPUTS`, `ACK`, `NACK` — werden in Stufe 9 nicht aktiv genutzt (laut Plan), können bei Bedarf nachträglich ergänzt werden (Header hat Opcodes bereits drin).

---

## Stufe C — Kalibrierungs-Lib

(folgt nach Stufe B)

---

## Stufe D — `HexapodSystemHardware`-Klasse

(folgt nach Stufe C)

---

## Stufe E — Plugin-Registrierung

(folgt nach Stufe D)

---

## Stufe F — URDF-Anpassung & `controllers.real.yaml`

(folgt nach Stufe E)

---

## Stufe G — `real.launch.py`

(folgt nach Stufe F)

---

## Stufe H — Echte Servo2040-Anbindung

(folgt nach Stufe G)

---

## Stufe I — Tests & Doku

(folgt nach Stufe H)

---

## Stufe J — Phase-9-Abschluss

(folgt nach Stufe I)
