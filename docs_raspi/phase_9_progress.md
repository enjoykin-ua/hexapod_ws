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
- [x] B.12 **Post-Review-Fix:** Range-Check in `encode_frame` (throw `std::invalid_argument` bei `payload.size() > MAX_PAYLOAD_LEN=253`). Bug ohne Fix: 300-Byte-Payload → LEN-Feld überläuft auf 44, Wire wird ohne Warnung produziert, Firmware verwirft als FRAME_MALFORMED — silent corruption. Mit Test verifiziert.
- [x] B.13 **Post-Review:** Goldene Hex-Anker-Tests gegen Python-Referenz (`~/hexapod_servo_driver/tools/test_servo2040.py`): 5 Frames mit exakten Wire-Bytes verankert (GET_STATE seq=0/seq=1, RESET seq=3, ENABLE_SERVO seq=2 idx=5 on, SET_TARGETS seq=0 alle 1500). Schützt vor übereinstimmenden Bugs in Encoder + Decoder, die ein Roundtrip-Test nicht fängt.
- [x] B.14 **Post-Review:** unnötiger `<cstring>`-Include raus; Kommentar zu impl-defined `uint16→int16`-Cast im STATE-Decoder hinzugefügt (well-defined two's-complement-wrap auf x86_64 + ARM64, identisch mit Firmware-Idiom).
- [x] B.15 **Cross-Repo-Verifikation:** STATE-Payload-Layout (18× int16 pulse, 18× uint16 current_mA, uint16 voltage_mV, uint8 status_flags) und ERROR_REPORT-Layout (uint8 code, uint8 servo_idx, int16 LE aux) gegen Firmware-`main.cpp` `handle_get_state` + `send_error` byteweise abgeglichen. ✓ identisch.

**Done-Kriterium B erreicht:** ✅ (am 2026-05-15, inkl. Post-Review-Fixes; 36 gtest-Cases in 6 Test-Suites grün)

### Stufe-B-Notizen

- **CRC-Implementation:** Bit-by-bit (~16 Zeilen Code) statt Lookup-Table. Host ist nicht throughput-bound — bei 50 Hz × ~78 Byte/Frame liegt der Unterschied bei ~80 ns/Frame. Spart 512 Byte statische Tabelle, ist deutlich lesbarer. Self-Test `0x29B1` für `"123456789"` ist der kanonische Validitäts-Beweis: jede konforme CRC-16/CCITT-FALSE-Implementation liefert exakt diesen Wert.
- **COBS-0xFF-Edge-Case:** Bei genau 254 Nicht-Null-Bytes in Folge endet der Block mit `count=0xFF` — und der Decoder fügt **kein** implizites Null-Byte ein (Chain-Extension-Pattern). Bei `count` ∈ 1..254 fügt der Decoder dagegen immer ein 0x00 hinzu, **außer** wenn es der letzte Block im Stream ist. Tests `BoundaryAt254NonZeroBytes` und `BoundaryAt255NonZeroBytes` decken das ab.
- **Frame-Roundtrip-Symmetrie:** `encode_frame` hängt 0x00-Trenner an; `decode_frame` toleriert sowohl mit als auch ohne Trenner. Damit kann ein späterer Streaming-Reader (Stufe D) je nach Komfort 0x00 weglassen oder mitschicken.
- **Negativer-Pulse-Test:** `int16` ist signed, aber unsere Wire-Konversion arbeitet mit `uint8_t`. Der Test `RoundtripSetTargetsNegativePulse` mit `-1234` verifiziert, dass die Sign-Erhaltung an der Konversions-Grenze funktioniert (`int16 → 2× uint8 LE → zurück`).
- **Test-Vorbild:** Die Test-Vektoren sind teilweise direkt aus `~/hexapod_servo_driver/tools/test_servo2040.py` übernommen (Self-Test 0x29B1, SET_TARGETS 1500 µs → `DC 05`, ENABLE_SERVO Payload-Format). Damit ist Host-/Firmware-Kompatibilität strukturell schon getestet, ohne dass tatsächliche USB-Kommunikation läuft.

### Stufe-B-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| LEN-Overflow in `encode_frame` bei Payload > 253 | 🔴 → ✅ gefixt | throw `std::invalid_argument`, mit Boundary-Test |
| Hex-Dump-Anker gegen Python-Ref fehlt | 🟡 → ✅ ergänzt | 5 goldene Vektoren in `GoldenHex`-Test-Suite |
| `<cstring>`-Include unnötig | 🟢 → ✅ entfernt | — |
| `uint16 → int16`-Cast impl-defined pre-C++20 | 🟢 → ✅ kommentiert | well-defined auf unseren Targets, gleicher Idiom in fw |
| STATE/ERROR_REPORT Layout vs Firmware | ✅ verifiziert | byteweise Match mit `main.cpp` `handle_get_state` + `send_error` |
| SEQ-Counter im Plugin | 🟢 vormerk Stufe D | encode_frame nimmt SEQ vom Caller, atomic counter im Plugin |
| ERROR_REPORT-Routing im Plugin | 🟢 vormerk Stufe D | Reader-Thread + RCLCPP_ERROR-Log |
| PULSE_OUT_OF_RANGE handling | 🟢 vormerk Stufe D | wenn fw das schickt: zu großzügige Calibration oder extremes Target |

### Was Stufe B explizit **nicht** macht

- Kein USB-Port-Handling, keine echte Übertragung — kommt in Stufe D.
- Keine Streaming-Reader-Logik (Bytes häppchenweise einsammeln und auf 0x00 splitten) — auch Stufe D.
- Keine Decoder für `INPUTS`, `ACK`, `NACK` — werden in Stufe 9 nicht aktiv genutzt (laut Plan), können bei Bedarf nachträglich ergänzt werden (Header hat Opcodes bereits drin).

---

## Stufe C — Kalibrierungs-Lib

> Done-Kriterium C (aus Plan): Lib + Unit-Tests grün, Skelett-YAML mit Platzhalter-Werten.

- [x] C.1 `yaml-cpp`-basierter Loader (`load_from_file` + `load_from_string` für Tests)
- [x] C.2 Schema-Validierung: `defaults`-Block + `servo2040_output_to_joint` Map mit 18 Einträgen, jeder Eintrag mit `joint:`-Pflichtfeld; Pulse-Triplet-Sanity `pulse_min < pulse_zero < pulse_max`; `direction ∈ {+1, -1}`; klare Exception-Messages bei Verletzung
- [x] C.3 Defaults-Fallback: fehlende per-Servo-Felder erben aus `defaults`-Block
- [x] C.4 `set_joint_limits(joint_name, lower, upper)` — URDF-Limits per Joint-Name injizieren, unbekannte Joints werden stillschweigend ignoriert (für passive Joints)
- [x] C.5 `radians_to_pulse_us` piecewise-linear: zwei Steigungen meeten bei `pulse_zero`, `direction`-Flip eingebaut
- [x] C.6 `pulse_us_to_radians` Inverse: gleiche piecewise-Logik rückwärts, Vorzeichen-konsistent
- [x] C.7 Bounds-Checks (`std::out_of_range` bei `output_idx ∉ [0, 18)`)
- [x] C.8 `at()` + `output_idx_for_joint()` Lookup-Helper
- [x] C.9 Unit-Tests `test/test_calibration.cpp`: 27 Test-Cases in 7 Suites:
  - `YamlLoader` (5) — Happy-Path, Lookup, Defaults-Fallback, Per-Servo-Override
  - `YamlLoader` Error-Path (6) — Garbage, Missing Map/Joint-Name/Entry, Invalid Direction, Degenerate Triplet, File-Not-Found
  - `SetJointLimits` (2) — Named-Joint, Silent-Ignore-Unknown
  - `RadiansToPulse` (4) — Zero=Pulse-Zero, JointLower=PulseMin, JointUpper=PulseMax, ±π/4
  - `RadiansToPulse` Asymmetric (2) — Unterschiedliche Slopes links/rechts, Negative-Direction mirrors
  - `PulseToRadians` (2) — Inverse-Identitäten an Endpoints
  - `Roundtrip` (3) — Forward∘Inverse=Identity für sym/asym/mirror
  - `Bounds` (2) — Negative + Overflow-Index throws
  - `RealConfigFile` (1) — Echtes `config/servo_mapping.yaml` parst sauber
- [x] C.10 `CMakeLists.txt`: `target_compile_definitions(test_calibration PRIVATE SOURCE_DIR_FOR_TESTS=...)` damit Tests die echte YAML aus dem Source-Tree laden können
- [x] C.11 `colcon build`: grün, keine Warnings
- [x] C.12 `colcon test`: 6/6 grün
- [x] C.13 **Post-Review-Fix:** Strong-Exception-Guarantee in `load_from_string` — lädt jetzt in lokale `std::array` + `std::unordered_map`, committet erst am Ende per `std::move`. Bug ohne Fix: bei mid-parse throw blieb das Objekt halb-geladen (Frankenstein-Zustand mit gemischten alten + neuen Einträgen). Praktische Schwere für Phase 9 niedrig (Plugin `on_init` wirft bei Failure und nutzt Calibration nicht weiter), aber relevant für Phase-10-Reload-Workflow und Doku-Treue.
- [x] C.14 **Post-Review-Tests:** `StrongExceptionGuarantee`-Suite (2 Tests) verifiziert, dass ein fehlgeschlagener `load_from_string` Member-State und vorherige `set_joint_limits`-Werte unangetastet lässt. Plus `YamlLoader.RejectsTypeMismatchAsRuntimeError` als Regressions-Schutz für die yaml-cpp-Exception-Hierarchie (`YAML::Exception : std::runtime_error`).
- [x] C.15 **Post-Review-Doku:** `set_joint_limits`-Kommentar präzisiert — vorher las er als wäre der Aufruf zwingend, tatsächlich läuft die Konversion auch ohne (mit ±1.57-Defaults aus `ServoCalibration{}`). Jetzt steht klar: „NOT strictly required, but if URDF limits differ from ±1.57 and this is skipped, pulse values will be silently wrong. Don't skip it."

**Done-Kriterium C erreicht:** ✅ (am 2026-05-15, inkl. Post-Review-Fixes; 30 gtest-Cases in 8 Test-Suites grün)

### Stufe-C-Notizen

- **YAML-Schema bewusst „strict aber freundlich":** Fehlende Pflichtfelder (`joint:`, fehlende Index-Einträge) sind harte Errors mit klarer Message. Optionale Pulse-Werte erben aus `defaults`. Das ist genau die Balance, die Phase-10-Kalibrierungstool braucht: es kann minimale Einträge schreiben (nur `joint:`-Name pro Servo, `defaults`-Block einmal), aber Schema-Verletzungen werden früh und deutlich angemerkt.
- **`pulse_min < pulse_zero < pulse_max` als Loader-Invariante:** Spart einen Haufen NaN-Debug in der Konversionspipeline. Würde es nicht früh gecheckt, hätten Phase-10-Werte mit Bug zu negativen Slopes und stillschweigend falschen Pulse-Werten geführt.
- **`set_joint_limits` ignoriert unbekannte Joints stillschweigend:** Wenn die URDF passive Joints (z.B. mimic-Joints oder Fixed-Joints) enthält, würde das sonst beim `on_init` einen Loop-Fehler werfen. Bewusst defensiv gewählt.
- **Piecewise-Linear-Korrektheit:** Die `Roundtrip`-Suite verifiziert `inverse(forward(rad)) == rad` mit 1e-9 Toleranz über den ganzen Joint-Range, in drei Konfigurationen (symmetrisch, asymmetrisch, gespiegelt). Das fängt z.B. den Bug ab, wo die Inverse für `direction=-1` die falsche Seite wählen würde.
- **`RealConfigFile`-Test:** Lädt die echte `config/servo_mapping.yaml` aus dem Source-Tree und verifiziert, dass sie parst. Damit bricht das Test-Build, wenn jemand das YAML versehentlich kaputt-merged.

### Stufe-C-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| Type-Mismatch im YAML als richtige Exception-Klasse | 🟢 OK | `YAML::Exception` erbt von `std::runtime_error` — Header-Versprechen gehalten. Test als Regressions-Schutz hinzugefügt |
| Strong-Exception-Guarantee in `load_from_string` | 🔴 → ✅ gefixt | Local-vars + std::move-Commit am Ende; 2 Tests verifizieren dass Member-State und `set_joint_limits`-Werte bei mid-parse throw unangetastet bleiben |
| `set_joint_limits`-Kommentar irreführend | 🟡 → ✅ gefixt | Doku-Lüge korrigiert: Konversion läuft auch ohne, aber mit ±1.57-Defaults (was bei abweichendem URDF still-falsche Pulse-Werte gibt) |
| NaN-Input in `radians_to_pulse_us` | 🟢 vormerk Stufe D | propagiert als NaN durch — Plugin muss vor Konversion checken |
| `joint_lower==0` / `joint_upper==0` Edge | 🟢 vormerk Phase 10 | Division durch 0 → inf; tritt bei symmetrischen Joints nicht auf |
| Continuity bei `rad=0` / `dp=0` | ✅ verifiziert | Beide piecewise-Branches liefern denselben Wert am Übergang |

### Was Stufe C explizit **nicht** macht

- Kein Host-seitiges Pulse-Clamping. Hard-Clamp passiert auf Servo2040-Seite (Phase-7 Stufe C.1). Wenn Calibration einen Pulse < `pulse_min` oder > `pulse_max` produziert (z.B. wegen extremem Joint-Target), schickt das Plugin das raus, die Firmware clampt und meldet `ERR_PULSE_OUT_OF_RANGE`. Plugin loggt das in Stufe D.
- Kein Persistieren / Schreiben von YAML. Lesen reicht für Phase 9 — der Phase-10-Kalibrierungs-Workflow (Tool das jog'en und Werte schreiben kann) ist Phase-10-Scope.
- Keine `SET_CALIBRATION`-Frame-Generierung (Opcode `0x10` der Firmware). Die Firmware-seitigen Werte bleiben bei den Defaults aus `config.hpp`; die Host-Konversion ist die maßgebliche Stelle.

---

## Stufe D — `HexapodSystemHardware`-Klasse

> **Plan-Doku:** [`phase_9_stage_d_plan.md`](phase_9_stage_d_plan.md) — Architektur, Threading-Modell, Sub-Stage-Aufteilung, 10 Review-Punkte.
>
> Stufe D ist in **8 Sub-Stages D.1–D.8** aufgeteilt (Begründung in der Plan-Doku).

### Sub-Stage D.1 — Serial-Port-Wrapper

> Done-Kriterium D.1 (aus Plan): `SerialPort` baut + leakt keinen FD, Bytes überleben byte-exakt (insbesondere 0x0D/0x0A nach cfmakeraw), Read-Timeout funktioniert, write_all wirft bei Timeout, mutex schützt Reconnect-Race.

- [x] D.1.1 Header `include/hexapod_hardware/serial_port.hpp`: API mit `open`/`adopt_fd`/`close`/`write_all`/`read_some`/`exclusive_lock`, non-copyable/non-movable, `std::shared_mutex` als Member
- [x] D.1.2 Implementation `src/serial_port.cpp`:
  - `O_RDWR | O_NOCTTY | O_NONBLOCK` beim `open()`
  - `cfmakeraw()` + `tcflush()` in `configure_termios()` (gemeinsam für `open` + `adopt_fd`)
  - `write_all()` mit `poll(POLLOUT, 50 ms)` pro Chunk, throw `std::system_error` bei Timeout
  - `read_some()` mit `poll(POLLIN, 1000 ms)`, returnst 0 bei Timeout (kein Throw)
  - Klare Error-Messages bei disconnect-errnos (`EIO`, `ENXIO`, `ENODEV`, `EBADF`)
- [x] D.1.3 Unit-Tests `test/test_serial_port.cpp` mit `openpty(3)`: 14 Tests in 3 Suites:
  - `SerialPortLifecycle` (5): default-closed, adopt_fd, idempotent close, double-adopt-throws, ENOENT-message
  - `SerialPortPty` (8): 256-Byte-Roundtrip, **CR-byte-exact, LF-byte-exact, mixed-CR-LF-byte-exact** (cfmakeraw-Verifikation), read-timeout returns 0 (900..1500 ms), write delivers, **exclusive_lock blockt parallel write**
  - `SerialPortError` (2): write/read auf geschlossenem Port throws
- [x] D.1.4 `CMakeLists.txt`: `serial_port.cpp` in der Library, Test linkt `util` für `openpty`
- [x] D.1.5 `colcon build`: grün, keine Warnings
- [x] D.1.6 `colcon test`: 7/7 grün — `test_serial_port` (14), `test_calibration` (30), `test_servo2040_protocol` (36) + 4 linters

**Done-Kriterium D.1 erreicht:** ✅ (am 2026-05-15)

### Sub-Stage D.2 — Reader-Thread

> Done-Kriterium D.2 (aus Plan): Reader baut, sauberer Start/Stop ohne Hang, gültige Frames erreichen Cache/Queue, ungültige Frames werden verworfen ohne zu poisoning, Thread-Lifecycle ist sauber (kein detach, kein Leak).

- [x] D.2.1 Header `include/hexapod_hardware/servo2040_reader.hpp`: API mit `start`/`stop`/`is_running`/`died`/`latest_state`/`drain_error_queue`, non-copyable/non-movable, drei Mutexe (`lifecycle_mtx_`, `state_mtx_`, `error_mtx_`), zwei Atomics (`stop_requested_`, `died_`)
- [x] D.2.2 Implementation `src/servo2040_reader.cpp`:
  - Main-Loop: `read_some` → bytes → split on 0x00 → `decode_frame` → `dispatch`
  - Dispatch per opcode: STATE_RESPONSE → cache, ERROR_REPORT → queue, ACK/NACK → DEBUG-Log, unknown → WARN
  - **`try/catch` um die gesamte Loop** mit `died_=true` bei Exception (Review Punkt 4)
  - **`lifecycle_mtx_`** serialisiert `start`/`stop`/`is_running`/Destructor
  - `stop_requested_` wird **vor** dem Lifecycle-Lock gesetzt, damit ein hängender `read_some` sofort beim nächsten Timeout reagiert
  - Disconnect-Errors (`std::system_error` aus `SerialPort::read_some`) setzen `died_` und beenden den Thread (echte Reconnect-Logik kommt in D.7)
- [x] D.2.3 Unit-Tests `test/test_servo2040_reader.cpp` mit `openpty(3)`: **17 Tests in 2 Suites**:
  - **`ReaderLifecycle` (6)** — IsRunning-Lifecycle, DoubleStartThrows, StopIdempotent, StopJoinsCleanlyWithin1500ms, **RepeatedStartStopLeavesNoThreadBehind** (5 Zyklen Stress-Test), **DestructorJoinsRunningThread** (RAII-Verifikation)
  - **`ReaderPty` (11)** — StateFrameLandsInCache, ErrorReportLandsInQueue, MultipleErrorReportsAccumulateInOrder, DrainConsumesQueue, GarbageBytesAreDiscarded, UnknownOpcodeIsDiscarded, CorruptedCrcIsDiscarded, AckAndNackAreSilentlyAccepted, MultipleFramesBackToBackAllProcessed, ChunkedDeliveryIsReassembledCorrectly, LoneDelimiterByteIsIgnored
- [x] D.2.4 `CMakeLists.txt`: `servo2040_reader.cpp` in der Library, neuer `ament_add_gtest test_servo2040_reader` (linkt auch `util` für `openpty`)
- [x] D.2.5 `colcon build`: grün, keine Warnings
- [x] D.2.6 `colcon test`: 8/8 grün — `test_calibration` (30), `test_serial_port` (14), **`test_servo2040_protocol` (36)**, **`test_servo2040_reader` (17)**, plus 4 Linter = **97 gtest-Cases**

**Done-Kriterium D.2 erreicht:** ✅ (am 2026-05-15)

### Stufe-D.2-Notizen

- **Zwei UB-Fallen ausgemerzt während der Entwicklung:**
  1. `*rclcpp::Clock::make_shared()` als Argument für `RCLCPP_WARN_THROTTLE` — der `shared_ptr<Clock>` ist ein Temporary, das `*` dereferenziert ihn, das Macro hält intern eine Referenz auf den gleich-zerstörten Clock. Plus: in gtest-Fixtures ohne `rclcpp::init()` schlägt die Clock-Konstruktion fehl. Lösung: plain `RCLCPP_WARN` ohne Throttle. Garbage-Frames sind auf USB-CDC selten, Spam ist OK-genug Diagnose.
  2. Im Test selbst: `std::lock_guard<std::mutex> dummy(*std::make_unique<std::mutex>())` — gleicher Bug. Beide Fixes mit erklärenden Kommentaren im Code.
- **Thread-Lifecycle-Garantie:** `lifecycle_mtx_` serialisiert `start`/`stop`/Destruktor gegen sich selbst. Aufruf-Konvention bleibt sequentiell (ros2_control-Lifecycle-States sind ohnehin nicht parallel), aber das Mutex schützt vor Race-Condition wenn jemand das missachtet. Niemals vom Reader-Thread selbst gehalten — kein Deadlock-Risiko.
- **Stop-Latenz:** Maximal ~1 s wegen `SerialPort::read_some`-Timeout (VTIME entspricht 1 s effektiv). Bei Stop-Request wartet der Reader bis zum nächsten poll-Timeout, dann beendet er. Test `StopJoinsCleanlyWithin1500ms` deckelt das auf 1,5 s.
- **`died()`-Flag vs `is_running()`:** Wenn der Reader-Thread aufgrund einer Exception abbricht, ist `thread_.joinable()` weiter true (kein implizites `detach`), aber `died_` ist true. `is_running()` returnt false. Plugin muss in `read()` `died_` prüfen und `return_type::ERROR` zurückgeben — kommt in D.6.

### Was Stufe D.2 explizit **nicht** macht

- Kein Reconnect-Versuch bei Disconnect — Reader stirbt und `died_` wird gesetzt. Reconnect-Logik kommt in **D.7**.
- Keine semantische Auswertung von ERROR_REPORT-Codes (Code → Log-Message-Übersetzung) — kommt in **D.8**.
- Kein automatisches GET_STATE-Polling — siehe Architektur-Entscheidung B in der Plan-Doku.

### Sub-Stage D.3 — `on_init`

> **Konzept-Erklärung:** [phase_9_stage_d_plan.md §D.3](phase_9_stage_d_plan.md) — inklusive Abschnitt **„Was passiert bei Geometrie-Änderungen?"**.
>
> **Konfigurations-Quellen-Trennung:** [docs/01_hardware_change_workflow.md](../docs/01_hardware_change_workflow.md) — Cross-Phasen-Workflow, 12 Szenarien.
>
> Done-Kriterium D.3 (aus Plan): on_init validiert HardwareInfo, lädt Calibration, baut joint→servo-pin-Tabelle, allokiert Vektoren — alles mit klaren Error-Pfaden.

- [x] D.3.1 Header `hexapod_system.hpp` angepasst: neue Member `joint_to_output_idx_` (URDF→servo-pin), `last_command_pulse_us_` umgestellt von `std::vector<int16_t>` auf `std::array<int16_t, NUM_SERVOS>` (servo-pin-indiziert, fixe Größe 18)
- [x] D.3.2 `on_init` implementiert (170 Zeilen, in 7 nummerierten Schritten):
  1. Joint-count-Validation (`== NUM_SERVOS`)
  2. Hardware-Parameter parsen: `serial_port` (default `/dev/ttyACM0`), `calibration_file` (no default → error wenn fehlt), `loopback_mode` (case-insensitive bool-Parser, akzeptiert true/false/1/0/yes/no)
  3. `Calibration::load_from_file` mit klarem Error-Pfad bei YAML-Fehler
  4. URDF-`<limit lower upper>` aus `command_interfaces[].min/max` parsen + `Calibration::set_joint_limits` per Joint-Name
  5. `joint_to_output_idx_`-Tabelle aufbauen via `Calibration::output_idx_for_joint` (wirft bei unbekanntem Joint → ERROR)
  6. Duplicate-Detection: zwei URDF-Joints auf demselben Servo-Pin → ERROR
  7. State-Vektoren allokieren + `last_command_pulse_us_` mit pulse_zero pro Servo-Pin initialisieren
- [x] D.3.3 `RCLCPP_INFO`-Lifecycle-Logs am Anfang + Ende (Punkt aus Plan: Per-Lifecycle-INFO-Log)
- [x] D.3.4 Unit-Tests `test/test_hexapod_system.cpp`: **14 Tests in 1 Suite `HexapodSystemInit`**:
  - Happy-Path (`ValidHardwareInfoSucceeds`, `ExportedInterfaceNamesMatchUrdfOrder`)
  - Joint-Count (`RejectsTooFewJoints`, `RejectsTooManyJoints`)
  - Hardware-Parameter (`RejectsMissingCalibrationFile`, `RejectsEmptyCalibrationFile`, `RejectsNonExistentCalibrationFile`, **`AcceptsAllBoolStringsForLoopback`** — 11 Strings akzeptiert case-insensitive, `RejectsGarbageLoopbackString`, `LoopbackDefaultsToFalseIfOmitted`)
  - Joint-Mapping (`AcceptsPermutedJointOrder` — reversed Joint-Liste, verifiziert dass `export_command_interfaces` URDF-Reihenfolge behält; `RejectsUnknownJointName`)
  - Limit-Parsing (`ParsesJointLimitsFromUrdf` mit asymmetrischen Limits, `EmptyJointLimitsFallBackToDefaults` mit Warn-Log)
- [x] D.3.5 `CMakeLists.txt`: `ament_add_gtest test_hexapod_system` + `SOURCE_DIR_FOR_TESTS`-Compile-Definition (gleiches Pattern wie `test_calibration` für Real-YAML-Pfad)
- [x] D.3.6 `colcon build`: grün, keine Warnings
- [x] D.3.7 `colcon test`: 9/9 grün — `test_calibration` (30), `test_serial_port` (14), `test_servo2040_protocol` (36), `test_servo2040_reader` (17), **`test_hexapod_system` (14)**, plus 4 Linter
- [x] D.3.8 `colcon test-result`: **153 tests, 0 errors, 0 failures** (15 skipped sind ROS-Standard für nicht-aktivierte Linter-Sub-Suites)
- [x] D.3.9 **Post-Review-Fix:** Lower-≥-Upper-Check für URDF-Limits. Bug ohne Fix: vertauschte `<limit>`-Werte (URDF-Macro-Refactor-Versehen) ergeben negative Slopes in `Calibration` → NaN/inf in Pulse-Konversion → Servos fahren in falsche Richtung gegen mechanischen Anschlag. Spiegelung links/rechts ist **kein** Use-Case (die lebt in `direction` in der YAML, nicht in URDF-Limits — Code-Kommentar erklärt das explizit). Test `RejectsSwappedJointLimits` + `RejectsEqualJointLimits` verifizieren.
- [x] D.3.10 **Post-Review:** Strong-Exception-Guarantee für `joint_to_output_idx_`-Aufbau analog zu `Calibration::load_from_string` (Stufe C). Lokales `new_table`, am Ende `std::move` ins Member. Test `FailedReinitDoesNotMutateTable` verifiziert dass nach einem fehlgeschlagenen on_init der zweite (guter) on_init wieder das Original-Mapping liefert.
- [x] D.3.11 **Post-Review-Kommentare:** drei Code-Kommentare zu nicht-offensichtlichen Invarianten:
  1. „Mirrored-Leg-Hinweis" bei der Lower-<-Upper-Validation: erklärt warum URDF-Limits **immer** `lower < upper` sind und die physische Spiegelung in `direction` lebt
  2. `vector::assign(n, v)` mit `n ≤ capacity()` reallocates nicht → ros2_control-captured Pointers bleiben bei Re-Init stabil
  3. `hw_state_positions_=0.0` initial: ist konsistent mit `last_command_pulse_us_=pulse_zero` (in Stufe D.6, erstes read() gibt 0 rad zurück)
- [x] D.3.12 `colcon test`: 9/9 grün; `test_hexapod_system` jetzt 17 Tests; total **156 tests, 0 errors, 0 failures**

**Done-Kriterium D.3 erreicht:** ✅ (am 2026-05-15, inkl. Post-Review-Fixes; 17 gtest-Cases in 1 Test-Suite grün)

### Stufe-D.3-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| Lower-≥-Upper-Check fehlt für URDF-Limits | 🔴 → ✅ gefixt | Strict `lower < upper` + FATAL-Log mit „mirrored legs use direction"-Hinweis; 2 Tests verifizieren swap und equal |
| Strong-Exception-Guarantee bei `joint_to_output_idx_` | 🟡 → ✅ gefixt | Lokales `new_table` + `std::move` commit am Ende; Test verifiziert dass failed re-init das vorige Mapping nicht beschädigt |
| ros2-substitution-Erwartung bei Pfaden | 🟢 vormerk Stufe F | `<param name="calibration_file">` muss durch xacro `$(find ...)` aufgelöst sein — nicht Plugin-Aufgabe |
| `~`/relative Pfade nicht expanded | 🟢 vormerk README | Plugin-spezifische Doku-Note in Stufe I |
| Initial `hw_state_positions_=0.0` | ✅ konsistent | Mit `last_command_pulse_us_=pulse_zero` und D.6-Echo-Pfad ergibt das saubere 0-rad-Initial-State |
| `vector::assign` bei Re-Init reallocates nicht | ✅ verifiziert | cppref-Garantie + Code-Kommentar als Defense-in-Depth |

### Inbetriebnahme-Vormerks für D.4–D.7

(Nicht jetzt fixen, aber im Hinterkopf für die spätere Sub-Stage-Implementation:)

- **D.4 `on_configure`:** USB-Port-not-found mit klarem Hinweis auf `dialout`-Gruppe + Servo2040-Anschluss
- **D.5 `on_activate`:** Boot-Sequenz RESET → 18× ENABLE → SET_TARGETS neutral (schon in Plan-Doku)
- **D.6 `read/write`:** NaN-Check, Pulse-Overflow-Clamp, joint_to_output_idx_-Mapping in Aktion
- **D.7 Reconnect:** User-Recovery-Workflow nach Disconnect dokumentieren

### Stufe-D.3-Notizen

- **Build-Bug-Fund:** `hardware_interface::HardwareInfo` hat **kein** `hardware_class_type`-Feld in Jazzy 4.44, obwohl der Plan-Doku-Hinweis das suggerierte. Test-Helper musste den Eintrag rausnehmen — wird in D.4/E ohnehin via pluginlib gesetzt, nicht als Direct-Member.
- **Loop-Variable-Warning** wieder dasselbe `const std::string &` über `{"..."}`-initializer_list — Fix wie in Stufe C: `const char *` nehmen.
- **Joint-Limit-Reading-Pfad:** Wir lesen aus `joint.command_interfaces[k].min/max` (Strings), parsen via `std::stod`. Wenn die URDF die `<limit>`-Werte nicht setzt, kommt min/max als leere Strings — Plugin gibt einen WARN aus aber returnt SUCCESS (Fallback auf Calibration-Defaults ±1.57).
- **`joint_to_output_idx_` ist nicht extern sichtbar.** Tests verifizieren das Mapping indirekt über `export_command_interfaces`-Reihenfolge (muss URDF-Order entsprechen, NICHT pin-Order). Die direkte Anwendung der Tabelle (write/read) wird in **D.6** funktional getestet.
- **Duplicate-Detection:** `std::adjacent_find` auf sortiertem `joint_to_output_idx_` fängt den Fall ab, dass zwei URDF-Joints denselben Pin haben (z.B. wenn jemand servo_mapping.yaml + URDF inkonsistent macht). Tritt in der Praxis nur bei manuellem YAML-Editing-Fehler auf, aber schwer zu debuggen wenn nicht früh-detected.

### Was Stufe D.3 explizit **nicht** macht

- Kein Serial-Port-Open — kommt in **D.4** (`on_configure`)
- Kein Reader-Thread-Start — auch **D.4**
- Kein ENABLE_SERVO oder SET_TARGETS — **D.5** (`on_activate`)
- Kein write/read mit Pulse-Konversion — **D.6** (stubs aus Stufe A bleiben temporär)

### Sub-Stage D.4 — `on_configure` / `on_cleanup`

> Done-Kriterium D.4 (aus Plan): Loopback-Mode skipt Port-Open; PTY-Path öffnet Port + startet Reader; on_cleanup schließt sauber ohne Hang; ungültiger Pfad → ERROR.

- [x] D.4.1 Header: `SerialPort serial_port_` und `Servo2040Reader reader_` als Direct-Member. Deklarations-Reihenfolge bewusst: SerialPort zuerst (zerstört zuletzt), Reader danach (zerstört zuerst via RAII → stop+join vor close). `on_cleanup` als Lifecycle-Hook deklariert.
- [x] D.4.2 `on_configure` implementiert:
  - Loopback-Mode: return SUCCESS ohne Port-Open + Reader-Start (Architektur-Entscheidung aus Stage-D-Plan)
  - Sonst: `serial_port_.open(serial_port_path_)` mit klarem FATAL-Log bei Fehler (Hinweis auf `dialout`-Gruppe + URDF-Param)
  - Bei `reader_.start(serial_port_)`-Fehler: Port wieder schließen (Cleanup-Invarianz)
- [x] D.4.3 `on_cleanup` implementiert:
  - **Reihenfolge:** `reader_.stop()` ZUERST, dann `serial_port_.close()`. Sonst würde der Reader-Thread auf einem geschlossenen FD pollen und unnötig `died_=true` setzen (POLLNVAL/EBADF).
  - Beide Aufrufe sind idempotent + noexcept — sicher auch ohne vorheriges `on_configure` oder doppelt
- [x] D.4.4 Tests `test_hexapod_system.cpp` neue Suite `HexapodSystemConfigure` (6 Tests):
  - `LoopbackConfigureSucceedsWithoutPort` — loopback skipt Port-Open ohne ENOENT-Crash trotz nicht-existentem Default-Pfad
  - `LoopbackCleanupIsSafeEvenIfNotConfigured` — `on_cleanup` doppelt + ohne `on_configure` → SUCCESS
  - `RejectsNonExistentSerialPort` — bad path → ERROR mit klarem Log
  - `ConfigureWithPtyOpensPortAndStartsReader` — pty-Pair + serial_port=ttyname(slave) → Port wird geöffnet, Reader läuft (verifiziert durch Garbage-Bytes-Schicken auf master + Reader-Verarbeitung); `on_cleanup` joined in < 1.5 s
  - `ConfigureCleanupCycleCanRepeat` — 3 × configure/cleanup-Zyklus → kein FD-Leak, kein Thread-Leak
  - `DestructorCleansUpAutomatically` — Plugin im Scope erstellen, configure, **kein** explizites `on_cleanup` → Destructor joined Reader-Thread + schließt Port automatisch in < 1.5 s
- [x] D.4.5 `CMakeLists.txt`: `target_link_libraries(test_hexapod_system util)` für `openpty(3)` ergänzt
- [x] D.4.6 `colcon build`: grün, keine Warnings
- [x] D.4.7 `colcon test`: 9/9 grün; `test_hexapod_system` jetzt 23 Tests; **162 tests, 0 errors, 0 failures**
- [x] D.4.8 **Post-Review:** drei defensive Ergänzungen:
  1. **`died_`-Check 10 ms nach `reader_.start()`** — fängt das Edge-Case ab, dass der Reader-Thread zwischen `open()` und seinem ersten `poll()` einen Disconnect-EIO sieht. Ohne den Check würde `on_configure` SUCCESS returnen und erst der erste `read()`-Tick (~20 ms später) den Fehler melden. Mit dem Check schlägt es früher und mit besserem Log fehl. Cleanup (`reader_.stop()` + `serial_port_.close()`) korrekt nachgezogen.
  2. **Code-Kommentar zu doppeltem `on_configure`** — erklärt, dass `serial_port_.open()` „already open" wirft, ERROR-Pfad keine State-Corruption macht (Port bleibt offen wie vor dem Call). ros2_control-Lifecycle erlaubt das ohnehin nicht, aber der Hinweis spart einem zukünftigen Reviewer die Analyse.
  3. **Member-Lifetime-Kommentar im Header** — erklärt explizit warum die Deklarations-Reihenfolge `SerialPort` vor `Servo2040Reader` der Reader-Thread-Referenz Sicherheit gibt (Reader-Destruktor joined den Thread bevor SerialPort zerstört wird). Schützt vor späterer Member-Umsortierung ohne Verständnis.

### Stufe-D.4-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| Member-Destruktion-Reihenfolge | ✅ verifiziert | C++-Garantie umgekehrte Konstruktions-Reihenfolge, Test `DestructorCleansUpAutomatically`. Kommentar im Header verewigt. |
| Cleanup-Reihenfolge stop→close | ✅ verifiziert | Sonst POLLNVAL/EBADF im Reader, unnötiger `died_=true`. Kommentar in `on_cleanup`. |
| Doppelter on_configure | ✅ dokumentiert | Open wirft, ERROR-Return, Port-State intakt. Kommentar im Code. |
| Reader-died direkt nach start() | 🟡 → ✅ defensiv gefixt | 10 ms Sleep + `died()`-Check + cleaner Cleanup-Pfad |
| Reader-Thread-Reference-Lifetime | ✅ dokumentiert | Member-Deklaration im Header explizit kommentiert, schützt vor späterer Re-Order |

### Stufe-D.4-Notizen

- **Member-Deklarations-Reihenfolge ist kritisch:** `SerialPort` vor `Servo2040Reader`. C++-Garantie: Destruction in umgekehrter Reihenfolge. → Reader-Destruktor läuft zuerst (stop+join), SerialPort-Destruktor danach (close). Verhindert die „Reader liest noch, Port wird geschlossen → SIGSEGV/EBADF"-Race. Selbst wenn der User `on_cleanup` vergisst, ist die RAII-Kette sicher (Test `DestructorCleansUpAutomatically` verifiziert).
- **Cleanup-Reihenfolge umgekehrt zur Setup-Reihenfolge:** `on_configure` macht `open → start`; `on_cleanup` macht `stop → close`. Niemals Reader laufen lassen während FD geschlossen wird.
- **Loopback bleibt komplett serial-port-frei:** kein `open()`, kein Reader-Thread. Sogar in D.5 (`on_activate`) wird die Stagger-Sleep auf 0 reduziert und Wire-Frames werden nicht generiert. Damit ist Loopback ein vollwertiger CI-Modus ohne irgendwelche IO-Voraussetzungen.
- **Repeat-Cycle robust:** `ConfigureCleanupCycleCanRepeat` macht 3 × full-cycle. Wichtig weil ros2_control configure→cleanup→configure-Lifecycle erlaubt (z.B. nach einem Fehler-Recover-Versuch). `SerialPort::open` checkt `fd_ >= 0` und wirft beim doppelten open — aber unsere Cleanup setzt `fd_ = -1`, also funktioniert das Re-Open.

### Was Stufe D.4 explizit **nicht** macht

- Keine ENABLE_SERVO-Frames — kommt in **D.5** (`on_activate`)
- Kein SET_TARGETS oder ergebnis-relevantes write/read — **D.6**
- Kein Reconnect-Retry bei verlorenem Port — **D.7** (D.4-Verhalten bei mid-run-Disconnect: Reader-Thread stirbt mit `died_=true`)

### Sub-Stage D.5 — `on_activate` / `on_deactivate` mit Boot-Sequenz

> **Konzept-Erklärung:** [`phase_9_stage_d_plan.md §D.5`](phase_9_stage_d_plan.md) — RESET → 18×ENABLE 50 ms stagger → SET_TARGETS neutral.
>
> Done-Kriterium D.5 (aus Plan): Loopback `on_activate` < 100 ms; PTY: Boot-Sequenz in Order auf der Wire, Stagger ~ 900 ms gesamt, last_command_pulse_us_ landet auf pulse_zero.

- [x] D.5.1 Header `hexapod_system.hpp`: `std::atomic<uint8_t> seq_{0}` als Member ergänzt, `<atomic>` + `<cstdint>` Includes
- [x] D.5.2 `on_activate` implementiert (3 Phasen, ~95 Zeilen):
  1. RESET-Frame schicken (PROTOCOL.md §6 — clears WATCHDOG_TRIPPED falls vom letzten Run hängengeblieben), 10 ms Breather
  2. 18× ENABLE_SERVO(pin, true) mit 50 ms Stagger (in Loopback: 0 ms, schnelle CI). Setzt Watchdog warm bei jedem Frame.
  3. SET_TARGETS mit allen pulse_zero (= 1500 µs aus YAML-defaults). Re-asserts `last_command_pulse_us_` auf Neutral, hält Watchdog während Gap bis erster write()-Tick warm.
  - Defensive `send_frame`-Lambda: prüft `reader_.died()` vor jedem `write_all`; catched exceptions → FATAL-Log + return ERROR. Loopback skipt Wire-I/O komplett.
- [x] D.5.3 `on_deactivate` implementiert: 18× ENABLE_SERVO(pin, false) ohne Stagger (Torque-off so schnell wie möglich, Disable hat keinen Inrush). Best-Effort-Semantik (Failures → WARN, weiter, weil Watchdog 200 ms später eh disabled).
- [x] D.5.4 Tests `test_hexapod_system.cpp` neue Suite `HexapodSystemActivate` (6 Tests):
  - `LoopbackActivateAndDeactivateAreFast` — Loopback Activate < 100 ms, Deactivate < 50 ms
  - `PtyActivateSendsBootSequenceInOrder` — auf master-end exakt 20 Frames: 1× RESET (cmd=0x50) + 18× ENABLE_SERVO mit pin=0..17, enable=0x01 + 1× SET_TARGETS mit allen 18 Pulses = 1500 µs. SEQ wraparound-frei 0..19.
  - `PtyActivateRespectsStaggerTiming` — Wallclock 800..1200 ms (Soll 910 ms ± Scheduler-Jitter)
  - `PtyDeactivateSendsDisableForAllServos` — nach Activate: 18× ENABLE_SERVO mit pin=0..17, enable=0x00; gesamte Deactivate < 200 ms (kein Stagger)
  - `PtyActivateDeactivateCycleCanRepeat` — 2 × Activate/Deactivate-Zyklus, SEQ läuft über Cycles weiter (76 Frames < 256, kein wraparound observable)
  - `ActivateFailsCleanlyIfPortIsBroken` — Master closen → Reader detektiert POLLHUP → `died_=true` → on_activate bricht beim ersten send_frame mit FATAL+ERROR ab; cleanup nachgelagert ok
- [x] D.5.5 Test-Helper `drain_master_until_idle` + `split_and_decode_frames` (parsen Wire-Bytes als COBS-Frames). `<poll.h>`-Include ergänzt.
- [x] D.5.6 `colcon build`: grün, keine Warnings
- [x] D.5.7 `colcon test`: 9/9 grün; `test_hexapod_system` jetzt **29 Tests**; total **168 tests, 0 errors, 0 failures**
- [x] D.5.8 **Post-Review:** Logging-Differenzierung Loopback vs. Hardware in `on_activate`-INFO-Log am Ende (`"loopback path traced, no wire frames sent"` vs. `"18 servos enabled, neutral pose commanded"`) — verhindert irreführende „neutral pose commanded"-Meldung in CI-Runs wo gar nichts auf die Wire ging.

**Done-Kriterium D.5 erreicht:** ✅ (am 2026-05-15; 6 gtest-Cases in 1 Test-Suite grün)

### Stufe-D.5-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| SEQ-Race zwischen Activate-Sequence und späteren write()-Ticks | ✅ defensiv gelöst | `std::atomic<uint8_t>` mit `fetch_add` — auch wenn ros2_control sequentiell aufruft, ist atomic Defense-in-Depth |
| SEQ-Wraparound bei 256 Frames | ✅ harmless | Firmware ist stateless wrt SEQ (echoiert nur), Header-Kommentar dokumentiert |
| Encoder-Exception-Pfade (`encode_set_targets` etc.) | ✅ verifiziert | Werfen nur bei Payload > 253 B; unsere Payloads sind 0/2/36 B, immer unter Limit |
| Reader-died-Check vor jedem write_all | ✅ verifiziert | Test `ActivateFailsCleanlyIfPortIsBroken` fängt USB-Disconnect zwischen configure und activate sauber ab |
| Loopback skipt 50 ms Stagger | ✅ verifiziert | Test `LoopbackActivateAndDeactivateAreFast` deckelt auf 100 ms |
| Neutral-Pulses in SET_TARGETS-Frame | ✅ verifiziert | Test parst Wire-Payload byteweise, alle 18 × 1500 µs (= 0xDC 0x05 LE) |
| Loopback-Logging-Klarheit | 🟡 → ✅ gefixt | INFO-Log diferenziert „loopback path traced" vs. „neutral pose commanded" |
| Member-Lifetime (atomic seq_) | ✅ trivial | std::atomic<uint8_t> ist POD-ähnlich, lebt im Plugin-Lifetime |
| on_deactivate Best-Effort vs. Hard-Fail | ✅ bewusst Best-Effort | Firmware-Watchdog (200 ms) ist Fallback bei Verlust von Disable-Frames |
| Test verankert pulse_zero=1500 gegen YAML | ✅ bewusst | Phase-10-Calibration mit Custom-Werten würde Test brechen — gewünschte Regression-Detection |

### Stufe-D.5-Notizen

- **`send_frame`-Lambda als „defensiver Funnel":** Alle Wire-Writes in `on_activate` gehen durch die gleiche Lambda. Sie prüft `reader_.died()` (USB grad weg?), catched `std::exception` aus `write_all`, loggt FATAL mit Kontext (was sollte das werden?). Damit ist on_activate auch bei mid-sequence disconnect robust: bricht beim nächsten Frame ab statt Exception aus dem Lifecycle-Hook fliegen zu lassen. Loopback skipt den Funnel komplett (return true ohne write).
- **Stagger 50 ms ist HOST-seitig:** Firmware bleibt dumm (siehe Phase-7 D.1-Design + V1-Decision oben). Insgesamt 18 × 50 ms + 10 ms RESET-Breather = ~910 ms Activate-Zeit auf echter HW; in Loopback komplett gemoddelt-fast (~12 ms inkl. RESET-Breather).
- **Watchdog warmhalten:** Das initiale `SET_TARGETS` mit Neutralpose dient zwei Zwecken — definierter Initial-State UND Bridge zwischen on_activate-Ende und erstem 50-Hz-write()-Tick. Ohne den könnte der Watchdog (200 ms) tripen wenn der erste Controller-Tick mal länger braucht (z.B. launch-Timing).
- **last_command_pulse_us_ Re-Assertion in on_activate:** Bereits in on_init auf pulse_zero gesetzt. on_activate setzt sie nochmal — wichtig bei Re-Activate nach einem Disconnect-Recovery-Cycle, wo last_command_pulse_us_ zwischendurch durch write()-Ticks irgendwo anders hingewandert sein könnte.
- **Test-Helper `drain_master_until_idle(idle_timeout)`:** Idle-Timeout muss > Stagger (50 ms) sein, sonst deklariert Test fälschlicherweise „idle" zwischen zwei Frames. 200 ms gewählt = 4× Sicherheits-Faktor.

### Was Stufe D.5 explizit **nicht** macht

- Kein write/read mit Pulse-Konversion — kommt in **D.6**. Aktuell sind die write/read-Hooks noch Stubs mit 1:1-Echo aus Stufe A.
- Kein automatisches RESET nach Watchdog-Trip mid-run — User entscheidet manuell (siehe Plan-Doku §6 + Phase-10).
- Keine Reconnect-Logik im Activate-Pfad — kommt in **D.7**. D.5-Verhalten bei mid-Activate-Disconnect: clean abort mit ERROR, Plugin geht in inactive.

### Sub-Stage D.6 — `read()` / `write()` mit Echo-State + Pulse-Konversion

> **Vorab-Plan:** [`phase_9_stage_d_6_plan.md`](phase_9_stage_d_6_plan.md) — Logik-Skizze, Design-Begründungen, 8 (geplante) Tests + 1 Post-Review-Test, Progress-Checkliste als Done-Vertrag.
>
> Done-Kriterium D.6 (aus Plan): write→read-Roundtrip ≤ 2 mrad, NaN-Sanity, Int16-Clamp, ERROR_REPORT-Drainage, reader.died() → ERROR.

- [x] D.6.1 `<cmath>` + `<climits>` Includes in `src/hexapod_system.cpp` ergänzt
- [x] D.6.2 `write()` implementiert mit:
  1. `reader_.died()`-Defensive-Check (non-loopback) → ERROR_ONCE + return ERROR
  2. Pro Joint i: `joint_to_output_idx_[i]` lookup, NaN-Check (WARN + keep last good), `radians_to_pulse_us`, `std::clamp` auf int16-Range, `last_command_pulse_us_[output_idx]` Update
  3. In loopback: nur Konversion, kein Wire-I/O — return OK
  4. Non-loopback: `encode_set_targets` + `serial_port_.write_all`, catch → ERROR
- [x] D.6.3 `read()` implementiert mit:
  1. Pro Joint i: Echo via `pulse_us_to_radians(output_idx, last_command_pulse_us_[output_idx])` → `hw_state_positions_[i]`
  2. Non-loopback: `reader_.drain_error_queue()`, pro Eintrag RCLCPP_ERROR mit Code/Servo/Aux (Format-Detail D.8)
  3. `reader_.died()`-Check → ERROR_ONCE + return ERROR
- [x] D.6.4 Tests `test_hexapod_system.cpp` neue Suite `HexapodSystemWriteRead` (**9 Tests** — 8 geplant + 1 Post-Review):
  - `LoopbackRoundtripsCommandThroughCalibration` (7 rad-Werte ±1.5, alle 18 Slots, Toleranz 2 mrad)
  - **`LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` (Post-Review)** — reversed URDF + per-slot distinct values → verifiziert dass `joint_to_output_idx_` in BEIDE Hooks (write + read) tatsächlich angewandt wird
  - `LoopbackZeroRadStaysAtPulseZero` (exakte Identität bei 0)
  - `LoopbackNanCommandIsLoggedAndIgnored` (NaN bei Slot 5 → keep 0.5, andere Slots tracken 0.1)
  - `LoopbackClampsAbsurdRadInsteadOfUB` (rad=±100 → finite state, no UB)
  - `PtyWriteSendsSetTargetsFrameWithNeutralPulses` (rad=0 → SET_TARGETS mit 18× 1500 µs)
  - `PtyReadDrainsFirmwareErrorReports` (ERROR_REPORT-Frame inject → read() OK + Drain läuft)
  - `PtyReadReturnsErrorWhenReaderDies` (master close → POLLHUP → died → read() ERROR)
  - `PtyWriteReturnsErrorWhenReaderDies` (gleiches für write() → ERROR ohne Exception)
- [x] D.6.5 Test-Helper im anonymous namespace: `read_handle()` (via `get_optional().value()` für jazzy-4.44-API-Drift), `write_handle()` (via `set_value()` mit `[[nodiscard]]`-ASSERT)
- [x] D.6.6 `colcon build`: grün, keine Warnings (keine `get_value()`-Deprecation-Warnings)
- [x] D.6.7 `colcon test`: alle gtests grün, `test_hexapod_system` jetzt **32 Tests**; total **177 tests, 0 errors, 0 failures**
- [x] D.6.8 Self-Review-Tabelle mit Mapping-Bug-Lücke identifiziert + gefixt
- [x] D.6.9 **Post-Review-Fix:** zusätzlicher Test `LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` verifiziert dass `joint_to_output_idx_` in write() und read() angewandt wird (nicht nur in on_init gebaut). Lückenschluss zum vorhandenen Roundtrip-Test, der wegen uniform-Werte + kanonischer URDF keine Permutations-Bugs gefangen hätte.
- [x] D.6.10 `phase_9_stage_d_6_test_commands.md` finalisiert
- [x] D.6.11 README.md: Status auf D.6/8, Lifecycle-Tabelle `read` / `write` von 🟡 auf ✅, neuer Abschnitt „Echo-State-Pfad — die Konversion in Aktion (D.6)"
- [x] D.6.12 progress.md: diese D.6-Sektion mit Bullets + Notizen + Post-Review-Tabelle + „Was Stufe D.6 explizit nicht macht"

**Done-Kriterium D.6 erreicht:** ✅ (am 2026-05-15; 9 gtest-Cases in 1 Test-Suite grün)

### Stufe-D.6-Post-Review (kritische Punkte, durchgegangen am 2026-05-15)

| Punkt | Status | Detail |
|---|---|---|
| Joint-Permutations-Mapping nicht verifiziert in Roundtrip-Test | 🔴 → ✅ gefixt | Roundtrip setzt uniform value an alle Slots + kanonische URDF → ein `[i]`-statt-`[output_idx]`-Bug wäre nicht aufgefallen. Neuer Test mit reversed URDF + distinkten Werten pro Slot fängt das ab |
| NaN-Logging nicht throttled | 🟡 vormerk D.8 | Auf echter HW selten; D.8 könnte Counter-Throttle hinzufügen wenn nötig |
| ERROR_REPORT-Drain-Verifikation indirekt | 🟢 vormerk D.8 | Stärkere Log-Capture-Verifikation in D.8 mit Per-Code-Translation |
| `RCLCPP_ERROR_ONCE` callsite-global statt instance-global | 🟢 OK | Single-Plugin-Setup unkritisch; bei Multi-Plugin (z.B. zwei Hexapods am Pi) würde nur erster loggen — nicht erwartet |
| `set_value()` `[[nodiscard]]`-Pflicht im Test | ✅ OK | Test-Helper `write_handle()` mit ASSERT_TRUE konsumiert Return |
| Encoder-Exception-Pfad in write() | ✅ OK | encode_set_targets-Payload immer 36 B < MAX_PAYLOAD_LEN=253, kein Throw |
| Bounds-Check `joint_to_output_idx_[i]` ∈ [0,18) | ✅ OK | In on_init validiert via output_idx_for_joint; D.6 nutzt nur die garantierten Werte |
| Race-Conditions write() ↔ read() ↔ Reader-Thread | ✅ OK | write/read sequentiell im controller_manager-Thread; reader → main via atomic + mutex (queue/state) |
| Roundtrip-Genauigkeit 2 mrad | ✅ verifiziert | 1 µs pulse-round ≈ 1.6 mrad bei standard slope; 2 mrad Toleranz |

### Stufe-D.6-Notizen

- **Konversions-Pfad „rad → pulse → rad" liefert strukturell ≈ 0 Tracking-Error für JTC.** Das Plugin echoiert den letzten Sollwert als „aktuelle Position" zurück (keine echten Servos-Position-Feedbacks). JTC sieht damit immer „Roboter perfekt auf Sollwert" → `stopped_velocity_tolerance` und ähnliche Konvergenz-Checks greifen nicht. Limitation, nicht Bug. Diagnose-Ersatz (Strommessung etc.) ist Phase-10-Material.
- **`joint_to_output_idx_` als Schlüssel-Tabelle wird hier in Aktion:** D.3 hat sie gebaut, D.6 nutzt sie in BEIDEN Hooks (write: `last_command_pulse_us_[output_idx] = ...`, read: `... = last_command_pulse_us_[output_idx]`). Der neue Post-Review-Test (mit reverse URDF + distinkten Werten) ist die explizite Bug-Insurance dafür.
- **Loopback macht trotzdem die Konversion durch.** Das wäre die naive Vereinfachung gewesen („skip in loopback weil eh kein Wire-I/O"), aber dann würde der Roundtrip-Test nicht funktionieren — last_command_pulse_us_ bliebe auf pulse_zero, read() würde immer 0 rad zurückgeben. Loopback skipt nur `encode_set_targets + write_all`, nicht die Konversions-Schleife.
- **`std::clamp(pulse_d, INT16_MIN, INT16_MAX)` vor `static_cast<int16_t>`:** ohne den Clamp ist der Cast bei extrem-rad UB (signed integer narrowing). Test `LoopbackClampsAbsurdRadInsteadOfUB` setzt rad=±100 → verifiziert `std::isfinite(state)`. Firmware hat als Defense-in-Depth einen weiteren Clamp gegen pulse_min/pulse_max pro Servo (Phase-7 Stufe C.1).

### Was Stufe D.6 explizit **nicht** macht

- Kein Reconnect bei mid-run-Disconnect — kommt in **D.7**. D.6-Verhalten: write()/read() returnen ERROR, ros2_control bringt Plugin in inactive. Manuelle Re-Activation nach Stecker rein nötig.
- Keine ERROR_REPORT-Übersetzungs-Tabelle (Code → human-readable Message) — kommt in **D.8**. Aktuell loggt read() einen einzeiligen Hex-Dump pro Eintrag.
- Kein automatisches RESET nach `WATCHDOG_TRIPPED` mid-run — User entscheidet manuell (Plan-Doku §7).
- Keine `GET_STATE`-Polling für Diagnostik — Architektur-Entscheidung B in Plan-Doku (kein Konsument in Phase 9).
- Kein NaN-Throttle — falls in der Praxis spammy (Phase 10/H), kommt mit D.8 ein Counter-basierter Throttle.

### Sub-Stage D.7 — USB-Reconnect-Logik

(folgt nach D.6)

### Sub-Stage D.8 — ERROR_REPORT-Logging-Detail

(folgt nach D.7)

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
