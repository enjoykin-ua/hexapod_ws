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
