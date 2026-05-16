# hexapod_hardware

ROS2-Plugin (`ros2_control` SystemInterface), das den Hexapod über das
**Servo2040-Board** per USB-CDC steuert. Das Plugin ersetzt zur Laufzeit
das Sim-Plugin `gz_ros2_control` und exportiert 18 Position-Command-/
State-Interfaces an `controller_manager`.

Status: 🟢 **Phase 9 abgeschlossen (2026-05-16).**
Alle 10 Stufen A–J durchgelaufen: Wire-Protokoll (B) + Kalibrierung (C) +
Plugin-Lifecycle (D, alle 8 Sub-Stages) + Pluginlib-Registrierung (E) +
URDF-Sim/HW-Switch (F) + real.launch.py-Bringup (G) + echte Servo2040-
Anbindung (H, CI-Anteil grün, Oszi/Logic-Analyzer-Verifikation H-T8/H-T9
⏸️ pending wegen Hardware-Limit) + Tests/Doku-Polish (I) + Phase-9-Abschluss
mit ros2_control-name-Rename (J). Aktuell:
- Wire-Protokoll-Layer (36 Tests inkl. 5 goldener Hex-Anker gegen Python-Ref)
- Kalibrierungs-Lib (30 Tests, piecewise-linear Konversion + Strong-EH-Guarantee)
- SerialPort-Wrapper (14 Tests inkl. cfmakeraw-Byte-Exaktheit + Mutex-Race-Serialisierung)
- Reader-Thread (17 Tests inkl. RAII-Lifecycle + Stress-Test 5× start/stop)
- `on_init` (17 Tests inkl. permutierte Joint-Reihenfolge, Bool-Parser-Robustheit,
  Lower-<-Upper-Limit-Validation, Strong-EH-Guarantee bei Re-Init)
- `on_configure` / `on_cleanup` (6 Tests: Loopback-Skip, pty-Open + Reader-Start,
  Bad-Path-Reject, Configure/Cleanup-Cycle 3×, RAII-Destructor)
- `on_activate` / `on_deactivate` (6 Tests: Loopback-Fast, Pty-Boot-Sequence-Order
  verifiziert byteweise, Stagger-Timing 900 ms ± 100 ms, Deactivate-Disable-All,
  Activate/Deactivate-Cycle 2×, Activate-Fails-Clean bei Port-Broken)
- `read()` / `write()` mit Pulse-Konversion (9 Tests: Loopback-Roundtrip ±2 mrad,
  Permutations-Aware-Mapping mit reversed URDF, NaN-Sanity, Int16-Clamp,
  PTY-SET_TARGETS-Frame-Verifikation, ERROR_REPORT-Drain, Reconnect-Verhalten
  für beide Hooks)
- USB-Reconnect-Logik mit Backoff (5 Tests: Reader geht in Backoff statt
  zu sterben, Stop-Signal-Latenz, adopt_fd-Fallback, parallel-write-Race,
  full Plugin-Lifecycle während Disconnect). Backoff-Sequenz
  `{100, 200, 500, 1000, 2000, 5000, 5000}` ms, manuelle Recovery per
  `switch_controllers --activate` nach Reconnect.
- **Firmware-Error-Diagnose mit Severity-Routing (11 Tests: pro Error-Code
  human-readable Message, WARN/ERROR/FATAL je nach operativer Konsequenz;
  forward-compat-Fallback für unbekannte Codes; 0x20 SERVO_OVERCURRENT
  bewusst in Fallback weil Servo2040 keine Per-Servo-Stromsensoren hat)**
- **Pluginlib-Registrierung verifiziert (3 Tests: ClassLoader findet
  `hexapod_hardware/HexapodSystemHardware`, geladene Instanz besteht
  on_init, exportiert die spezifizierten 18 Interfaces). Damit ist die
  Manifest-/package.xml-/CMake-/.so-Verdrahtung runtime-bewiesen.)**

Total: **154 gtest-Cases** über sieben Test-Binaries, plus 1
launch_testing-Smoke (`hexapod_bringup`-Paket, Stage I.4).

---

## Quick-Start (Phase 9 Stage G/H/I)

Echte Hardware (Servo2040 am USB, Servo-Netzteil auf 6.0 V; mit oder
ohne Hexapod-Servos):

```bash
ros2 launch hexapod_bringup real.launch.py
```

Loopback-Modus (CI / Dry-Run, kein USB-Port wird geöffnet, kein
Servo-Netzteil nötig):

```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

Anderer USB-Port (z.B. `/dev/ttyACM1` wenn `/dev/ttyACM0` schon belegt):

```bash
ros2 launch hexapod_bringup real.launch.py serial_port:=/dev/ttyACM1
```

Args kombiniert:

```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true serial_port:=/dev/null
```

### Plugin-Parameter

Gesetzt im URDF-`<param>`-Block in
[`hexapod.ros2_control.xacro`](../hexapod_description/urdf/hexapod.ros2_control.xacro),
per xacro-Args überschreibbar:

| Param | Default | Wirkung |
|---|---|---|
| `serial_port` | `/dev/ttyACM0` | USB-CDC-Device der Servo2040 |
| `calibration_file` | `$(find hexapod_hardware)/config/servo_mapping.yaml` | Pulse-µs ↔ Joint-Winkel-Mapping pro Servo |
| `loopback_mode` | `false` | `true` = kein seriellen Port öffnen, Echo-State auch ohne HW |

### Topics

Das Plugin publisht **keine** ROS-Topics direkt — State + Command-
Interfaces gehen über `controller_manager` an die Controller. Sichtbare
Topics nach `real.launch.py`-Start (via `joint_state_broadcaster` + 6×
`JointTrajectoryController` aus
[`controllers.real.yaml`](../hexapod_control/config/controllers.real.yaml)):

| Topic | Typ | Wer |
|---|---|---|
| `/joint_states` | `sensor_msgs/JointState` | `joint_state_broadcaster`, alle 18 Joints, 50 Hz |
| `/leg_<n>_controller/follow_joint_trajectory` | `control_msgs/action/FollowJointTrajectory` | JTC-Action pro Bein |
| `/leg_<n>_controller/joint_trajectory` | `trajectory_msgs/JointTrajectory` | JTC Topic-Interface pro Bein |
| `/robot_description` | `std_msgs/String` (latched) | `robot_state_publisher`, generiertes URDF |
| `/tf` | `tf2_msgs/TFMessage` | `robot_state_publisher`, kinematische Transformationen |

Verifikation nach Bringup (in zweitem Terminal):

```bash
ros2 control list_hardware_components   # Plugin sollte active sein
ros2 control list_controllers           # 7 Zeilen active (1× JSB + 6× JTC)
```

### Wichtige Limitation — Echo-State

Der Servo2040 liefert **kein echtes Position-Feedback** (siehe
ausführliche Erklärung in Sektion „Echo-State-Pfad" weiter unten).
Das Plugin gibt als Position-State zurück was zuletzt geschickt wurde,
in Radiant rückgerechnet. **Konsequenzen:**

- JTC-Tracking-Error ist strukturell ≈ 0
- `stopped_velocity_tolerance` aus JTC-Konfig greift nicht
- echte Servo-Position kann (bei real angeschlossenen Servos)
  vom Echo-State abweichen, z.B. wenn Servo am Endanschlag steht
  oder mechanisch verklemmt ist
- Diagnose-Ersatz wäre Stromsense (Effort-Interface aus
  Servo2040-STATE-Frames, deferiert auf später)

### Bekannte kosmetische WARN beim Boot

Beim ersten `read()` nach `SerialPort::open()` kann im Log eine
einmalige Zeile erscheinen:

```
[hexapod_hardware.reader]: Servo2040Reader: frame decode failed (CRC/COBS/length, NN B)
```

Das ist USB-CDC-Boot-Garbage: zwischen `tcflush(TCIOFLUSH)` (in
`SerialPort::configure_termios()`) und dem ersten `read()` durch den
Reader-Thread können neue Bytes von der Firmware ankommen (Race-
Condition, nicht durch `tcflush` verhinderbar). Der Reader syncht
sich nach dem nächsten Frame-Delimiter (0x00) wieder ein. **Eine
einzelne WARN ist erwartet und unkritisch.** Wenn ein Sturm
auftritt: USB-Kabel / -Hub prüfen, Firmware-Stand verifizieren.

---

## Was dieses Paket tut (Gesamtbild)

```
                       ┌────────────────────────────────────────────┐
   ros2_control-Stack  │  controller_manager                        │
   (Hexapod-Sim-Code)  │   ├── joint_state_broadcaster              │
                       │   └── 6× joint_trajectory_controller       │
                       └────────────┬───────────────────────────────┘
                                    │ via SystemInterface API
                                    │ (read / write 50 Hz)
                       ┌────────────▼───────────────────────────────┐
                       │  hexapod_hardware::HexapodSystemHardware   │  ← dieses Paket
                       │   ├── Calibration (rad ↔ pulse-µs)         │
                       │   └── Servo2040-Protokoll (COBS + CRC-16)  │
                       └────────────┬───────────────────────────────┘
                                    │ USB-CDC, /dev/ttyACM0
                       ┌────────────▼───────────────────────────────┐
                       │  Servo2040 (Pimoroni, RP2040)              │  ← Phase 7 Firmware
                       │   ├── 18× PWM-Output                       │
                       │   └── Sicherheits-Layer (Clamp, Watchdog…) │
                       └────────────┬───────────────────────────────┘
                                    │ 18× PWM
                                    ▼
                              18 Servos (Hexapod-Beine)
```

**Sim/HW-Switch:** In der URDF wählt ein `<xacro:if>` zwischen
`gz_ros2_control` (für Gazebo) und `hexapod_hardware` (für echte HW).
Beide Pfade sind nie gleichzeitig geladen.

**Echo-State-Limitation:** Die Servos liefern **kein** echtes
Positions-Feedback. Was wir als Position-State zurückgeben ist der
letzte gesendete Sollwert, in Radiant umgerechnet. Konsequenz:
JTC-Tracking-Error ist strukturell ≈ 0, `stopped_velocity_tolerance`
greift nicht. Diagnose-Ersatz wäre Strommessung (deferiert auf später).

---

## Konfigurations-Quellen

Das Plugin wird von **drei Konfigurations-Quellen** gefüttert
(URDF / `servo_mapping.yaml` / `<param>`-Block in `hexapod.ros2_control.xacro`)
mit klar getrennten Verantwortungen. Da das ein Cross-Phasen-Thema ist
das auch andere Pakete (`hexapod_description`, `hexapod_control`)
betrifft, liegt der ausführliche **Änderungs-Workflow** zentral in:

→ [docs/01_hardware_change_workflow.md](../../docs/01_hardware_change_workflow.md)

Dort findest du:
- **„Hardware-Quellen-Stack ab Phase 9"** — die 4 zusätzlichen
  Wahrheits-Orte für die Hardware-Anbindung
- **Szenarien 8–12** mit konkreten Anleitungen:
  - Servo gegen anderes Modell tauschen
  - Servo gespiegelt / gedreht montieren
  - USB-Port wechseln
  - Loopback-Modus für CI aktivieren
  - Sim ↔ Hardware umschalten

**Plugin-spezifischer Kern in Kürze** (Details und Szenarien im
zentralen Doc oben):

| Quelle | Wann anfassen |
|---|---|
| URDF (`hexapod_physical_properties.xacro` + ros2_control-Block) | Geometrie-/Mechanik-Änderung, Joint-Limits, Plugin-Setup |
| `config/servo_mapping.yaml` | Servo-Tausch, Servo-Re-Montage |
| `hexapod.ros2_control.xacro` `<param>` | USB-Port-Wechsel, Loopback-Toggle |

**Wichtige Tatsache** (Begründung in `docs_raspi/phase_9_progress.md`
Design-Entscheidung Option C): im **Direct-Drive-Setup** (Servo-Welle =
Joint-Achse) dreht der Servo dieselbe Anzahl Radiant für dieselbe
Pulsbreite — **egal wie lang das Bein ist**. Beinlänge wirkt sich auf
Reichweite und Kraftarm aus, das ist URDF/Kinematik-Sache.
Servo-Kalibrierung bleibt davon unberührt. Daraus folgt: Geometrie-
Änderungen erfordern **kein** YAML-Update. YAML nur anfassen bei
tatsächlichen Eingriffen am Servo selbst (Tausch / Re-Montage /
mechanischer Servo-Anschlag wandert).

---

## Code-Struktur

```
hexapod_hardware/
├── CMakeLists.txt                # Build: shared lib + pluginlib export + gtest
├── package.xml                   # Dependencies + pluginlib-Manifest-Verweis
├── hexapod_hardware.xml          # pluginlib-Beschreibung (welche Klasse, welche Basis)
├── README.md                     # diese Datei
├── include/hexapod_hardware/
│   ├── servo2040_protocol.hpp    # Opcodes, Error-Codes, Status-Flags, Frame-API
│   ├── calibration.hpp           # rad↔pulse-Konversion (3-Punkt piecewise-linear)
│   └── hexapod_system.hpp        # die SystemInterface-Subklasse
├── src/
│   ├── servo2040_protocol.cpp    # Frame-Encoder/Decoder (Stubs in Stufe A, real in Stufe B)
│   ├── calibration.cpp           # Konversion + YAML-Loader (Stubs in Stufe A, real in Stufe C)
│   └── hexapod_system.cpp        # Lifecycle + read/write (Stubs in Stufe A, real in Stufe D)
├── config/
│   └── servo_mapping.yaml        # Pin-Index → Joint-Name + Kalibrierungs-Punkte
└── test/
    └── test_calibration.cpp      # gtest (Stub in Stufe A, voll in Stufe C)
```

---

## Klassen-Übersicht (Stand Stufe A)

### `hexapod_hardware::SerialPort` (neu in Stufe D.1)

POSIX-FD-Wrapper für `/dev/ttyACM*`. RAII-Owner, non-copyable,
non-movable. Drei Designentscheidungen:

1. **`cfmakeraw()`** — schaltet die Linux-TTY-Line-Discipline ab. Ohne
   das würde der Kernel `0x0D` automatisch zu `0x0A` mappen (ICRNL) bzw.
   `0x0A` zu `0x0D 0x0A` expandieren (ONLCR) — und damit jedes
   COBS+CRC-Frame zerstören, dessen CRC-Byte zufällig `0x0D` ist. Das
   war einer der zwei Bugs in Phase 7 C.4 (siehe fw-Repo
   `phase_7_progress.md` Postmortem). Drei spezifische Tests verifizieren
   dass `0x0D`, `0x0A` und gemischte Sequenzen byte-exakt durchkommen.

2. **`O_NONBLOCK` + `poll()` für Timing** — statt im blocking-Mode mit
   `VTIME` zu arbeiten. Vorteil: `write_all` kann mit einem 50-ms-Timeout
   abbrechen wenn die USB-CDC-FIFO wegen Firmware-Hang voll ist (ohne
   das würde der controller_manager-Tick blockieren). `read_some` hat
   einen 1-s-Timeout für den Reader-Thread, der nach Timeout sein
   Shutdown-Flag checken kann.

3. **`std::shared_mutex` als Member** — schützt vor dem Reconnect-Race
   (D.7): wenn der Reader-Thread `close()` + `open()` macht, während
   der Hauptthread mitten in `write_all()` ist, hätten wir ein
   TOCTOU-Pattern. Lösung: `write_all`/`read_some` nehmen
   `shared_lock`, der Reconnect-Pfad nimmt `exclusive_lock` via
   `port.exclusive_lock()`. Ein Test verifiziert die Serialisierung
   per Zeitmessung (Writer blockiert ≥ 200 ms wenn exclusive_lock
   200 ms gehalten wird).

API-Skizze:
```cpp
SerialPort port;
port.open("/dev/ttyACM0");        // wirft std::system_error bei Fehler

uint8_t frame[] = {…};
port.write_all(frame, sizeof(frame));   // poll+50ms timeout
                                        // wirft bei disconnect

uint8_t buf[256];
size_t n = port.read_some(buf, sizeof(buf));  // poll+1s, returnst 0 bei timeout

// Im Reconnect-Pfad:
{
  auto lock = port.exclusive_lock();   // blockiert bis kein I/O läuft
  port.close();
  // ... Backoff …
  port.open(path);
}  // lock released, write_all/read_some können wieder
```

Tests in [`test/test_serial_port.cpp`](test/test_serial_port.cpp)
(14 Test-Cases in 3 Suites): Lifecycle, alle 256 Byte-Werte
roundtrippen, **CR/LF byte-exakt** (cfmakeraw-Verifikation),
read-timeout 1 s, write delivers, write-on-closed throws, und
**Mutex-Contention zwischen write_all und exclusive_lock**.

### `hexapod_hardware::Servo2040Reader` (neu in Stufe D.2)

Hintergrund-Thread der die Servo2040-Wire-Bytes konsumiert,
auf `0x00`-Delimiter splittet, `decode_frame()` aufruft und nach
Opcode dispatched. Wichtige Eigenschaften:

**Saubere Lifecycle-Garantien.** Der User-Hinweis war klar: „stark auf
den Thread aufpassen, sauber starten und schließen, nicht im Hintergrund
weiterlaufen". Konkret garantiert die Implementation:

1. **Genau ein Thread**, gestartet in `start()`, gejoined in `stop()`.
   Nie detach. Nie ein zweiter parallel laufender Reader für dieselbe
   Instanz (double-start wirft `std::runtime_error`).
2. **Stop-Latenz deterministisch beschränkt** auf ~1 s (= `SerialPort`
   Read-Timeout). Test `StopJoinsCleanlyWithin1500ms` deckelt das.
3. **Destruktor ist RAII-sauber:** Wenn der Reader im Scope stirbt, wird
   automatisch `stop()` aufgerufen, der Thread joined. Test
   `DestructorJoinsRunningThread` verifiziert.
4. **`lifecycle_mtx_`** serialisiert `start`/`stop`/`is_running`/Destruktor
   gegen sich selbst — auch wenn ros2_control-Lifecycle bereits
   sequentiell ist, schützt das Mutex vor zukünftigen Race-Bugs.
5. **5× start/stop-Stress-Test** (`RepeatedStartStopLeavesNoThreadBehind`)
   verifiziert dass nach jedem Stop-Zyklus `is_running() == false` und
   `died() == false` ist — kein vergessener Thread.

**Dispatch-Verhalten:**

| Eingehender Frame-Opcode | Action |
|---|---|
| `STATE_RESPONSE` (`0x82`) | `latest_state_` (mutex-geschützt) updaten — peek-not-consume |
| `ERROR_REPORT` (`0x7F`) | in `error_queue_` (mutex-geschützt) anhängen |
| `ACK` (`0xFF`) / `NACK` (`0xFE`) | `RCLCPP_DEBUG`-Log, sonst nichts |
| unbekannter Opcode | `RCLCPP_WARN`, sonst nichts |
| CRC-Fehler / COBS-Fehler | `RCLCPP_WARN`, Frame verworfen |

`latest_state()` (peek) wird vom Plugin aktuell **nicht** benutzt — in
Phase 9 pollen wir GET_STATE nicht (Architektur-Entscheidung B in der
Stage-D-Plan-Doku). Der Cache ist für Phase 10 / spätere
Diagnostik-Zwecke vorbereitet.

`drain_error_queue()` wird in Stufe **D.6** (`read()`) bei jedem Tick
aufgerufen, jeder Eintrag per `RCLCPP_ERROR` geloggt (Detail-Formatierung
in **D.8**).

**Exception-Sicherheit:** Die gesamte Main-Loop ist in `try/catch`
eingebettet. Wenn z.B. `std::bad_alloc` aus dem Frame-Assembler fliegt
oder `std::system_error` aus `SerialPort::read_some` (Disconnect), wird
`died_ = true` gesetzt und der Thread beendet sich sauber.
`HexapodSystemHardware::read()` (Stufe D.6) prüft `died()` und meldet
das an ros2_control via `return_type::ERROR`. Echter Reconnect kommt
erst in **D.7**.

API-Skizze:
```cpp
SerialPort port;
port.open("/dev/ttyACM0");

Servo2040Reader reader;
reader.start(port);           // forkt Thread
// ... während Plugin läuft, Reader sammelt Frames im Hintergrund ...

// Pro read()-Tick:
for (auto & er : reader.drain_error_queue()) {
    RCLCPP_ERROR(logger, "FW error %02X (servo %u, aux %d)",
                 er.error_code, er.servo_idx, er.aux);
}
if (reader.died()) {
    return return_type::ERROR;
}

// Shutdown:
reader.stop();    // joined Thread, höchstens 1 s
port.close();
```

Tests in [`test/test_servo2040_reader.cpp`](test/test_servo2040_reader.cpp)
(17 Test-Cases in 2 Suites): `ReaderLifecycle` (6 — inkl. Stress-Test
und Destructor-RAII), `ReaderPty` (11 — alle Dispatch-Pfade inkl.
Bad-Frame-Discard und Chunked-Delivery-Reassembly).

### `hexapod_hardware::HexapodSystemHardware`

Subklasse von `hardware_interface::SystemInterface`. Wird zur Laufzeit
über `pluginlib` geladen und vom `controller_manager` durch eine feste
**Lifecycle**-Reihenfolge gefahren:

| Lifecycle-Hook | Aufgabe (Stand D.5/8) |
|---|---|
| `on_init`        | ✅ URDF-Joint-Liste validieren, Joint→Pin-Tabelle bauen, Kalibrierung laden, Limits injizieren, last_command_pulse_us_ auf pulse_zero |
| `on_configure`   | ✅ Serial-Port öffnen, Reader-Thread starten (in Loopback: skipt beides) |
| `on_activate`    | ✅ RESET → 18× ENABLE_SERVO mit 50 ms Stagger → SET_TARGETS neutral (Watchdog warmhalten + definierte Initial-Pose) |
| `on_deactivate`  | ✅ 18× DISABLE_SERVO ohne Stagger (Best-Effort — Torque-off so schnell wie möglich) |
| `on_cleanup`     | ✅ Reader-Thread stoppen, Serial-Port schließen (in dieser Reihenfolge) |
| `read`           | ✅ Echo via Calibration::pulse_us_to_radians (rad-Konsumenten sehen letzten Sollwert als „Istwert"); ERROR_REPORT-Drain mit per-Code Severity-Routing (siehe „Firmware-Error-Diagnose"); reader.died() → return_type::ERROR |
| `write`          | ✅ NaN-Sanity → keep last good; rad → pulse_us via Calibration; int16-Clamp gegen UB; in non-loopback: SET_TARGETS-Frame senden |

Plus die `export_*_interfaces`-Methoden, die dem `controller_manager`
sagen, welche Joints welche Position-Interfaces haben.

**Aktuell (Stufe A):** Alle Methoden sind **Stubs**, die SUCCESS / OK /
0 zurückgeben. `read` reflektiert `command` direkt nach `state` (das
strukturelle Echo-Verhalten ist schon eingebaut, aber ohne
Pulse-Konversion).

### `hexapod_hardware::Calibration`

Pro-Servo-Kalibrierung. Schema kommt aus `config/servo_mapping.yaml`
(im fw-Repo unter `contrib/` als Single Source of Truth bis Phase 10).

Pro Servo speichern wir vier Werte:
- `pulse_min` (µs) — Pulsbreite bei der der Servo am unteren Anschlag ist
- `pulse_zero` (µs) — Pulsbreite bei `joint_rad == 0`
- `pulse_max` (µs) — Pulsbreite am oberen Anschlag
- `direction` (±1) — Vorzeichen-Flip wenn Servo-Achse vs URDF-Joint-Achse
  invertiert montiert ist

**Drei-Punkt-Schema mit piecewise-linearer Konversion** (siehe
[Wire-Protokoll-Layer (Stufe B)](#wire-protokoll-layer-stufe-b) für die
Wire-Bytes-Sicht und der Abschnitt
[Kalibrierungs-Layer (Stufe C)](#kalibrierungs-layer-stufe-c) unten für die
ausführliche Erklärung der Konversion).

Die URDF-Joint-Limits (`joint_lower`, `joint_upper`) werden in
`on_init` aus der URDF gelesen und per `set_joint_limits()` an die
`Calibration`-Instanz übergeben.

**Aktuell (Stufe C):** Voll implementiert. yaml-cpp Loader mit
Schema-Validierung, piecewise-linear Konversion in beide Richtungen,
27 Unit-Tests grün.

### `servo2040_protocol.hpp` / `.cpp`

Konstanten und Frame-API gespiegelt aus dem Firmware-Repo
(`~/hexapod_servo_driver/src/config.hpp` + `PROTOCOL.md`):

- Opcodes: `SET_TARGETS=0x01`, `GET_STATE=0x02`, `STATE_RESPONSE=0x82`,
  `ENABLE_SERVO=0x20`, `RESET=0x50`, `ACK=0xFF`, `NACK=0xFE`,
  `ERROR_REPORT=0x7F`, … (vollständige Liste siehe Header)
- Error-Codes: `FRAME_CRC=0x01`, `PULSE_OUT_OF_RANGE=0x10`,
  `WATCHDOG_TRIPPED=0x40`, …
- Status-Flag-Bits (für das `status_flags`-Byte im STATE-Frame)

Frame-API (voll implementiert in Stufe B):
- `encode_set_targets(seq, pulse_us[18]) → bytes` (mit 0x00-Trenner am Ende)
- `encode_get_state(seq)`, `encode_enable_servo(seq, idx, on/off)`,
  `encode_reset(seq)`
- `encode_frame(seq, cmd, payload) → bytes` — der generische Helper
- `decode_frame(cobs_bytes) → optional<DecodedFrame{seq, cmd, payload}>`
- `decode_state(payload) → optional<StatePayload>`
- `decode_error_report(payload) → optional<ErrorReport>`
- `crc16_ccitt_false`, `cobs_encode`, `cobs_decode` — die unteren Bausteine

---

## Wire-Protokoll-Layer (Stufe B)

Diese Schicht spricht binär mit der Servo2040-Firmware. Vollständige
Spec: `~/hexapod_servo_driver/PROTOCOL.md`. Hier nur das Wesentliche
für jemanden, der die `servo2040_protocol.*`-Dateien liest.

### Frame-Aufbau

```
       Pre-COBS (5..258 Byte):
       ┌─────┬─────┬─────┬─────────────────┬──────────────┐
       │ SEQ │ CMD │ LEN │ PAYLOAD (LEN B) │ CRC16-LE (2) │
       └─────┴─────┴─────┴─────────────────┴──────────────┘
                CRC ist über SEQ ‖ CMD ‖ LEN ‖ PAYLOAD

       Nach COBS-Encoding (max +1 Byte/254):
       ┌──────────────────────────────────────────────────┐  ┌──────┐
       │ COBS(SEQ ‖ CMD ‖ LEN ‖ PAYLOAD ‖ CRC16)          │  │ 0x00 │
       └──────────────────────────────────────────────────┘  └──────┘
       Enthält garantiert kein 0x00-Byte                     Trenner
```

### COBS — Consistent Overhead Byte Stuffing

**Problem:** Wenn wir Frames in einem Byte-Stream voneinander trennen
wollen, brauchen wir ein Trenner-Byte. Wenn der Trenner irgendwo
**inside** des Payload auftauchen kann, geht das nicht — der Empfänger
würde mitten im Frame einen falschen „Frame-Anfang" detektieren.

**Lösung COBS** (Cheshire & Baker, 1999): Wir ersetzen jedes `0x00`
im Payload durch einen Zähler, sodass `0x00` **garantiert nur als
Frame-Trenner** vorkommen kann. Der Empfänger kann jederzeit auf den
nächsten Frame resync'en, indem er bis zum nächsten `0x00` liest.

**Wie das konkret aussieht:**

| Input (vor COBS) | Output (nach COBS) | Erklärung |
|---|---|---|
| _leer_ | `01` | Ein Block mit Länge 1 (nur das Count-Byte selbst) |
| `00` | `01 01` | Block-1 endet vor der Null, dann neuer Block mit nur Count |
| `11 22 33` | `04 11 22 33` | Ein Block der Länge 4 (Count + 3 Daten-Bytes) |
| `11 22 00 33` | `03 11 22 02 33` | Block(3): `11 22`, dann Block(2): `33` (implizite 0 zwischen Blöcken) |
| `0xAB × 254` | `FF AB×254 01` | Chain-Extension-Block (0xFF) + Termination |

**Overhead:** Maximal `⌈n/254⌉` Bytes für `n` Input-Bytes. Bei unserem
größten Frame (258 Byte vor COBS) sind das maximal 2 zusätzliche Bytes.

Implementierung: [`src/servo2040_protocol.cpp`](src/servo2040_protocol.cpp)
`cobs_encode` / `cobs_decode`.

### CRC-16/CCITT-FALSE

**Problem:** USB-CDC hat zwar Transport-CRC, aber ein einzelnes
gekippten Bit zwischen der USB-Schicht und unserem Frame-Parser würde
einen Servo auf eine völlig falsche Pulsbreite schicken. Spätere
Portierungs-Optionen (UART direkt auf den Pi, SPI, …) haben keine
Transport-CRC mehr.

**Lösung:** Eine 16-Bit-Prüfsumme über `SEQ ‖ CMD ‖ LEN ‖ PAYLOAD`,
in **little endian** ans Frame-Ende geschrieben (vor COBS-Encoding).
Der Empfänger berechnet dieselbe Prüfsumme über das empfangene Frame
und vergleicht. Bei Mismatch → Frame verwerfen, `ERR_FRAME_CRC` an
den Host melden.

**Variante CCITT-FALSE** ist die in Embedded-Welten verbreitete:
- Polynom `0x1021`
- Init-Register `0xFFFF`
- Keine Bit-Reflektion an Input oder Output
- XorOut `0x0000`

**Validitäts-Selbsttest:** `crc16("123456789") == 0x29B1`. Jede
konforme Implementation liefert genau diesen Wert. Wenn deine
Implementation einen anderen Wert liefert, hast du irgendwo einen
Parameter falsch (häufiger Fehler: Polynom-Reflektion, oder Init `0x0000`
statt `0xFFFF`).

**Erkennungsfähigkeit:**
- Alle 1- und 2-Bit-Fehler
- Alle Burst-Fehler bis 16 Bit Länge
- 99,997 % aller längeren Burst-Fehler

Implementierung: [`src/servo2040_protocol.cpp`](src/servo2040_protocol.cpp)
`crc16_ccitt_false`. Bit-by-bit Algorithmus (keine Lookup-Table) — am
Host nicht throughput-relevant, dafür kompakt und gut lesbar.

### Frame-Roundtrip in Code

```cpp
// Host sendet einen SET_TARGETS-Frame (alle Servos auf 1500 µs):
std::array<int16_t, 18> pulses;
pulses.fill(1500);
auto wire = encode_set_targets(/*seq=*/0, pulses);

// `wire` enthält jetzt die COBS-encodeten Bytes inklusive 0x00-Trenner —
// kann direkt mit write(fd, wire.data(), wire.size()) raus.

// Auf der Empfänger-Seite (z.B. unsere read()-Methode):
auto frame = decode_frame(cobs_bytes_until_zero);
if (frame) {
    if (frame->cmd == opcode::STATE_RESPONSE) {
        auto state = decode_state(frame->payload);
        // state->voltage_mv, state->status_flags, state->last_pulse_us[i], ...
    }
}
```

Tests in [`test/test_servo2040_protocol.cpp`](test/test_servo2040_protocol.cpp)
(36 Test-Cases in 6 Suites): CRC-Self-Test, COBS-Edge-Cases inklusive
0xFF chain-extension, alle vier Encoder im Roundtrip, negative
Pulse-Werte, CRC-Korruption, Truncation, STATE- und
ERROR_REPORT-Payload-Decoder, Payload-Overflow-Boundary
(`std::invalid_argument` bei `>MAX_PAYLOAD_LEN`), und **fünf goldene
Hex-Vektoren** mit exakten Wire-Bytes aus der Python-Referenz
(`~/hexapod_servo_driver/tools/test_servo2040.py`). Letztere schützen
vor übereinstimmenden Bugs in Encoder + Decoder, die ein Roundtrip-Test
nicht fängt.

---

## Kalibrierungs-Layer (Stufe C)

Diese Schicht übersetzt **Joint-Winkel in Radiant** (was `ros2_control`
und der Gait-Stack sprechen) in **PWM-Pulsbreiten in Mikrosekunden**
(was die Servos verstehen) — und zurück, für den Echo-State.

### Warum nicht eine einzige Formel?

Naive Idee: ein einziger Skalierungsfaktor `pulse_per_rad`, fertig.
Das **bricht**, sobald der Servo asymmetrisch montiert ist:

```
Symmetrisch (Joint und Servo lineare 1:1-Abbildung):
   joint_lower = -1.57       joint = 0       joint_upper = +1.57
   pulse_min   =  500        pulse_zero = 1500    pulse_max = 2500
   (1500-500)/1.57 = 636.94 µs/rad     ← gleich auf beiden Seiten
   (2500-1500)/1.57 = 636.94 µs/rad

Asymmetrisch (Servo um 30° geneigt montiert, Mechanik blockt rechts früher):
   joint_lower = -1.57       joint = 0       joint_upper = +1.00
   pulse_min   =  500        pulse_zero = 1500    pulse_max = 2400
   (1500-500)/1.57 = 636.94 µs/rad    ← linke Seite
   (2400-1500)/1.0  = 900.00 µs/rad    ← rechte Seite, andere Steigung
```

Im asymmetrischen Fall würde eine einzige Steigung entweder die
mechanische Grenze auf einer Seite verletzen, oder unnötig konservativ
sein.

### Drei-Punkt-Schema mit piecewise-linearer Konversion

Pro Servo speichern wir vier Werte (in [`servo_mapping.yaml`](config/servo_mapping.yaml)):

| Feld | Bedeutung |
|---|---|
| `pulse_min` (µs) | Pulsbreite die den Servo an den **unteren** Anschlag fährt — entspricht `joint_lower` (aus URDF) |
| `pulse_zero` (µs) | Pulsbreite die den Servo auf die **Joint-Mitte** (joint_rad = 0) fährt |
| `pulse_max` (µs) | Pulsbreite die den Servo an den **oberen** Anschlag fährt — entspricht `joint_upper` (aus URDF) |
| `direction` (±1) | Vorzeichen-Flip wenn Servo-Welle vs URDF-Joint-Achse entgegengesetzt montiert |

Aus diesen drei Pulse-Werten + den URDF-Joint-Limits berechnen wir zur
Laufzeit zwei Steigungen:

```
slope_left  = (pulse_zero - pulse_min) / |joint_lower|   µs/rad
slope_right = (pulse_max - pulse_zero) /  joint_upper    µs/rad
```

Und konvertieren stückweise linear (piecewise-linear):

```
joint_rad ≥ 0:  pulse_us = pulse_zero + direction · joint_rad · slope_right
joint_rad < 0:  pulse_us = pulse_zero + direction · joint_rad · slope_left
```

Sanity-Check: bei `joint_rad = joint_upper` ergibt das genau `pulse_max`,
bei `joint_rad = 0` genau `pulse_zero`, bei `joint_rad = joint_lower`
genau `pulse_min`. Linear dazwischen.

### Was `direction` macht

Stell dir Bein 1 (vorne-rechts) und Bein 6 (vorne-links) vor. Beide
heben das gleiche physische „Bein-anheben" — aber der Femur-Servo auf
der linken Seite ist **gespiegelt montiert** (Welle zeigt in die andere
Richtung). Bei `direction = +1` würde positives `joint_rad` auf der
linken Seite den Servo **runter** statt **hoch** fahren — falsch.

`direction = -1` für gespiegelte Beine kehrt das um. Konkret:
```
joint_rad = +0.5 mit direction = +1 → pulse_us = pulse_zero + 0.5·slope_right
joint_rad = +0.5 mit direction = -1 → pulse_us = pulse_zero - 0.5·slope_right
                                              (UNTER pulse_zero!)
```

Die echten Vorzeichen pro Servo werden in **Phase 10** beim Bring-up
einzeln per Jog ermittelt und in die YAML geschrieben. In Phase 9 sind
alle 18 noch `+1` (Platzhalter).

### Echo-State: warum wir die Inverse brauchen

Die Servos liefern kein echtes Position-Feedback. Was wir `read()` als
Position-State zurückgeben, muss der ros2_control-Stack als **Radiant**
sehen können — sonst rechnet der JTC mit Pulse-µs und alles ist
quatsch.

Workflow:
1. Gait-Stack schickt einen Trajectory-Sollwert in Radiant
2. Wir konvertieren `rad → pulse_us` via `radians_to_pulse_us`
3. Wir schicken `SET_TARGETS` mit Pulse-Werten zur Firmware
4. Im nächsten `read()`: kein echtes Feedback, also reflektieren wir den
   `last_command_pulse_us` zurück durch `pulse_us_to_radians`
5. Resultat in `hw_state_positions_[i]` — der JTC sieht *fast* exakt
   das, was er kommandiert hat (modulo Rundung)

Konsequenz: JTC-Tracking-Error ist strukturell ≈ 0. Das ist eine
Limitation, keine Eigenschaft des Plugins. Diagnose-Ersatz wäre
Strommessung — deferred auf Phase 10 oder später.

### Schema-Validierung

Der Loader ist absichtlich „strict aber freundlich":

- **Pflicht:** `servo2040_output_to_joint`-Map mit allen 18 Indizes
  (0..17), jeder Eintrag mit `joint:`-Name
- **Optional:** `defaults`-Block + per-Servo-Override für
  `pulse_min`/`pulse_zero`/`pulse_max`/`direction` (fallen sonst auf
  Defaults zurück)
- **Invariante:** `pulse_min < pulse_zero < pulse_max` strikt — sonst
  würde die Konversion negative oder unendliche Steigungen ergeben

Bei jeder Verletzung: `std::runtime_error` mit klarer Message statt
NaN-Quellen im Plugin-Lifecycle.

Tests in [`test/test_calibration.cpp`](test/test_calibration.cpp)
(30 Test-Cases in 8 Suites): Loader Happy-Path, Schema-Error-Path
(inkl. Type-Mismatch als `std::runtime_error`), `set_joint_limits`
(inkl. Silent-Ignore unbekannter Joints), symmetrische und asymmetrische
Konversion, Mirror-Direction, Inverse-Identitäten, Roundtrip in drei
Konfigurationen, Bounds-Checks, ein Real-File-Test gegen
`config/servo_mapping.yaml`, und **Strong-Exception-Guarantee**
(`load_from_string` lässt Member-State unangetastet wenn er mid-parse
wirft — lokale Strukturen + `std::move`-Commit am Ende).

---

## Firmware-Error-Diagnose (Stufe D.8)

Wenn die Servo2040-Firmware ein Problem erkennt, schickt sie ein
`ERROR_REPORT`-Frame mit drei Feldern:

```
struct ErrorReport {
    uint8_t error_code;   // siehe Tabelle unten
    uint8_t servo_idx;    // bei servo-spezifischen Codes der betroffene Pin
    int16_t aux;           // codeabhängig: mA, µs, mV, expected LEN, ...
};
```

Der Reader-Thread queued das, `read()` drainet pro Tick und loggt jeden
Eintrag mit einer **per-Code passenden Severity** und einer
**human-readable Message**, die das `aux`-Feld interpretiert. Damit ist
Fehler-Diagnose direkt aus den ROS-Logs machbar — kein Hex-Look-up in
`PROTOCOL.md` nötig.

### Code-Tabelle (Phase 9 Stufe D.8)

| Code | Severity | Message-Kern | Bedeutung |
|---|---|---|---|
| `0x01 FRAME_CRC` | `[WARN]` | „CRC error on incoming frame" | Einzelner Frame verworfen, FW re-syncs |
| `0x02 FRAME_MALFORMED` | `[WARN]` | „malformed frame (expected LEN=%d)" | LEN-Feld-Mismatch, Frame verworfen |
| `0x03 UNKNOWN_OPCODE` | `[WARN]` | „unknown opcode — protocol drift?" | Host/Firmware-Versions-Mismatch wahrscheinlich |
| `0x04 PAYLOAD_LEN` | `[WARN]` | „payload length mismatch (expected %d)" | Payload-Größe stimmt nicht zur Opcode-Spec |
| `0x10 PULSE_OUT_OF_RANGE` | `[WARN]` | „clamped pulse on servo %u to %d µs" | Host-Calibration zu großzügig; FW clampt selbst |
| `0x21 TOTAL_OVERCURRENT` | `[FATAL]` | „total current %d mA — ALL servos disabled" | Hard-Trip, ganzer Roboter aus |
| `0x30 UNDERVOLTAGE` | `[ERROR]` | „undervoltage at %d mV — check power supply" | Versorgungsspannung kritisch; PSU/Akku prüfen |
| `0x40 WATCHDOG_TRIPPED` | `[FATAL]` | „WATCHDOG_TRIPPED — send RESET + ENABLE_SERVO" | Host hat > 200 ms keine Frames geschickt; FW-Schutz griff |
| unbekannt (inkl. `0x20`) | `[ERROR]` | „Unknown firmware error: code=0xNN servo_idx=%u aux=%d" | Forward-Compat-Fallback |

**Hinweis zum fehlenden `0x20 SERVO_OVERCURRENT`:** Die Servo2040-
Hardware hat nur einen **Gesamt-Stromsensor**, kein Per-Servo-Sensing.
Die Firmware kann diesen Code physikalisch nicht senden. Falls jemand in
Phase 11+ eine Hardware-Revision mit Per-Servo-Stromsensoren baut und
die Firmware das beibringt: sauber im `error_report_log.cpp`-switch
ergänzen, plus zwei Tests.

**Hinweis zu UNDERVOLTAGE:** Phase 9 verzichtet bewusst auf eine
Unterscheidung zwischen WARN-Schwelle und TRIP-Schwelle. Eine
einheitliche `[ERROR]`-Meldung mit Spannungswert deckt beide Fälle, ohne
Annahmen über die Firmware-Konvention zu treffen. Wenn Phase 10 auf der
Bench tatsächlich Undervoltage sieht und die Unterscheidung relevant
wird: Firmware um 0x31 UNDERVOLTAGE_TRIP erweitern und im Plugin
separat formatieren.

### Wo lebt der Code?

```
include/hexapod_hardware/error_report_log.hpp   # ErrorSeverity + freie Funktionen
src/error_report_log.cpp                        # switch-Statements
test/test_error_report_log.cpp                  # 11 pure-function-Tests
```

Tests sind **pure-function-Tests** (kein RCLCPP-Log-Capture nötig) — die
Format-Logik wird direkt aufgerufen und der Output per Substring-Match
verifiziert. Schnell (< 1 ms gesamt), deterministisch, leicht erweiterbar.

---

## Pluginlib-Registrierung (Stufe E) — wie ros2_control unser Plugin findet

Dieses Paket erscheint nicht durch Magie im `controller_manager`. Damit
ein ros2_control-Stack zur Laufzeit unsere `HexapodSystemHardware` als
SystemInterface laden kann, müssen **vier Dinge zusammenpassen** — fehlt
eines, bricht das Laden mit (oft kryptischen) pluginlib-Exceptions ab.

Stufe E beweist diese Verdrahtung mit drei Runtime-Tests in
`test/test_plugin_registration.cpp`. Was geprüft wird:

```
                                            ┌─────────────────────────┐
[1] hexapod_hardware.xml          ─────────►│ Manifest                │
   (in Repo-Root des Pakets)                │  <library path="...">   │
                                            │   <class name="..."     │
                                            │          type="..."     │
                                            │     base_class_type=... │
                                            └────────────┬────────────┘
                                                         │
                                                         ▼
[2] CMakeLists.txt                ─────────► installiert nach
   pluginlib_export_plugin_         share/hexapod_hardware/...xml
   description_file(...)            UND legt Resource-Index-Eintrag an:
                                    share/ament_index/resource_index/
                                      hardware_interface__pluginlib__plugin/
                                        hexapod_hardware
                                                         │
                                                         ▼
[3] package.xml                   ─────────► <export>
   <hardware_interface              │   <hardware_interface
    plugin="${prefix}/...xml"/>     │      plugin="${prefix}/...xml"/>
                                    │ </export>
                                    │
                                                         │
                                                         ▼
[4] libhexapod_hardware.so        ─────────► PLUGINLIB_EXPORT_CLASS-Macro
   in src/hexapod_system.cpp                  am Ende von hexapod_system.cpp
                                              registriert die Klasse als
                                              Pluginlib-loadable Symbol
                                                         │
                                                         ▼
                                            ┌─────────────────────────┐
                                            │ pluginlib::ClassLoader  │
                                            │  scannt AMENT_PREFIX_   │
                                            │  PATH nach allen Resource│
                                            │  -Index-Einträgen,      │
                                            │  baut Plugin-Liste,     │
                                            │  dlopen()'t die .so,    │
                                            │  instanziiert via       │
                                            │  Factory-Pattern.       │
                                            └─────────────────────────┘
```

**Zentraler Punkt:** Der `share/ament_index/resource_index/...`-Eintrag
ist der **Auto-Discovery-Mechanismus** von ament/pluginlib — ohne ihn
findet pluginlib das Plugin nicht, auch wenn `.so` und Manifest da
sind. Genau diesen Eintrag legt `pluginlib_export_plugin_description_file`
in CMake an. Verifizieren mit:

```bash
cat install/hexapod_hardware/share/ament_index/resource_index/\
hardware_interface__pluginlib__plugin/hexapod_hardware
# Erwartet: share/hexapod_hardware/hexapod_hardware.xml
```

Die drei Tests (jeweils ohne `controller_manager`-Setup, rein per
ClassLoader-API):

| Test | Was bewiesen wird |
|---|---|
| `PluginIsLoadableViaPluginlib` | Resource-Index + Manifest sind sichtbar; `createSharedInstance` lädt die `.so` und instanziiert die Klasse |
| `LoadedPluginPassesOnInit` | Vtable + Symbol-Loading stimmen — die geladene Instanz ist funktional identisch zur direkt-konstruierten (`on_init` mit valid HardwareInfo → SUCCESS) |
| `LoadedPluginExposes18Interfaces` | Plugin-Spec-Vertrag: 6 Beine × 3 Joints, exportiert über die Base-Class-Vtable |

Für den End-to-End-Test mit echtem `controller_manager` (`ros2 control
list_hardware_components`) brauchen wir Stage F (URDF-Switch zwischen
`gz_ros2_control` Sim und `hexapod_hardware`) plus Stage G
(`real.launch.py`). Stage E beweist nur die **Plugin-Verdrahtung selbst**.

### Test-Helper-Refactor (Stage E.1)

Die `make_valid_info()`/`make_params()`/`make_joint()`-Builder, die seit
Stage D.3 in `test_hexapod_system.cpp` lebten, sind in Stage E.1 in
einen gemeinsamen Header `test/test_helpers.hpp` (namespace
`hexapod_hardware_test`, alle Symbole `inline` für ODR-Sicherheit)
verschoben. Beide Stage-D- und Stage-E-Test-Binaries nutzen jetzt den
selben HardwareInfo-Builder — DRY ohne Duplikation, kein Rauschen
beim Vergleich der Test-Setups.

---

## USB-Disconnect-Recovery (Stufe D.7) — User-Workflow

Bei einem Disconnect (Software-USB-Stack-Hänger, udev-Re-Enumerate beim
Pi-Boot, Firmware-Reboot durch Watchdog/Brown-Out, Power-Glitch) macht
das Plugin Folgendes:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Reader-Thread sieht POLLHUP/EIO im read_some()                   │
│    → catch (system_error) im loop()                                 │
│    → ruft reconnect_loop(port) auf                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. reconnect_loop                                                   │
│    • Pfad merken (z.B. "/dev/ttyACM0")                              │
│    • port.close() — fd_ → -1                                        │
│    • Backoff-Schleife: {100, 200, 500, 1000, 2000, 5000, 5000} ms   │
│    • Pro Iter: 50-ms-Sleep-Chunks → port.open(path) retry           │
│    • Bei Erfolg: INFO-Log mit Recovery-Befehl, return true          │
│    • Bei stop_requested_: return false (Reader exit)                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Während des Backoff (port closed):                               │
│    • write() versucht write_all → throws "port not open" → ERROR    │
│    • read()  echoiert weiterhin last_command_pulse_us_ → OK         │
│      (reader.died()==false weil aktiv retrying)                     │
│    • ros2_control sieht die write-ERRORs, deaktiviert Controller    │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Bei erfolgreichem Reopen:                                        │
│    • Reader läuft normal weiter (assembly.clear() → fresh frames)   │
│    • Plugin bleibt im INACTIVE state                                │
│    • INFO-Log zeigt User den nötigen Re-Activate-Befehl             │
└─────────────────────────────────────────────────────────────────────┘
```

### User-Recovery-Workflow

Nach einem Reconnect-Erfolg läuft der Reader-Thread wieder, aber
ros2_control hat die Controller wegen der `write()`-ERRORs schon
deaktiviert. Das Plugin **macht den Re-Activate NICHT automatisch** —
nach einem Disconnect kann der Roboter mechanisch in undefinierter Pose
sein (Servos waren spannungsfrei, Beine können durchgesackt sein). Der
User muss das explizit bestätigen:

```bash
# 1. Status prüfen
ros2 control list_controllers
# → alle Leg-Controller sind „inactive"

# 2. Roboter visuell prüfen — Beine in sinnvoller Pose? Aufgebockt?
#    Wenn die Beine durchgesackt sind: hand-positionieren, dann erst Schritt 3.

# 3. Re-Aktivieren
ros2 control switch_controllers --activate \
    joint_state_broadcaster \
    leg_1_controller leg_2_controller leg_3_controller \
    leg_4_controller leg_5_controller leg_6_controller
```

Das `on_activate` schickt dann die übliche Boot-Sequenz (RESET → 18×
ENABLE_SERVO mit 50 ms Stagger → SET_TARGETS neutral, siehe Stufe D.5)
und der Roboter ist wieder fahrbereit.

### Was `died()` jetzt bedeutet (gegenüber D.6)

`Servo2040Reader::died()` returnt nur dann true, wenn der Reader-Thread
**unwiderruflich** ausgefallen ist:
- Exception aus dem Main-Loop (z.B. `std::bad_alloc`)
- `adopt_fd`-Pfad: kein `path_` gespeichert → keine Möglichkeit zum
  Re-Open. Im Plugin-Produktivbetrieb tritt das nicht auf (das Plugin
  nutzt immer `serial_port_.open(path)`).

Normale USB-Disconnects setzen `died_` **nicht** mehr — der Reader ist
im Backoff aktiv und wird beim nächsten erfolgreichen `open()` weiter
laufen. `is_running()` bleibt während des Backoff true.

### Backoff-Sequenz — Begründung

Die Folge `{100, 200, 500, 1000, 2000, 5000, 5000}` ms ist Phase-7-
empirisch: ein USB-CDC-Re-Enumerate auf Linux dauert typisch ~200 ms,
ein udev-Reset etwas länger. Erste 3 Stufen schnell, dann ausweitend,
steady-state bei 5 s (CPU-Last vernachlässigbar, dem Kernel-USB-Stack
Zeit zur Erholung gegeben). Sleep ist in 50-ms-Chunks unterteilt, damit
ein paralleler `stop()` aus dem Plugin-`on_cleanup` innerhalb von ~50 ms
ankommt — auch beim steady-state-5-s-Wait.

Tests in [`test/test_servo2040_reader.cpp`](test/test_servo2040_reader.cpp)
(`ReaderReconnect`-Suite mit 4 Tests) und
[`test/test_hexapod_system.cpp`](test/test_hexapod_system.cpp)
(`HexapodSystemReconnect`-Suite mit 1 Test) verifizieren die einzelnen
Bausteine. **Der Reconnect-Erfolgs-Pfad selbst wird in Stage H mit echter
Hardware verifiziert** — PTYs können den Slave-Pfad nach Master-Close
nicht wiederbeleben, also können wir „open() klappt nach Disconnect" in
CI nicht direkt simulieren (Plan-Doku §D.7 Option C, vom User
freigegeben).

---

## Echo-State-Pfad — die Konversion in Aktion (Stufe D.6)

`write()` und `read()` werden vom `controller_manager` bei jedem 50-Hz-Tick
aufgerufen. Sie verbinden die ros2_control-Welt (Radiant, URDF-indexed)
mit der Servo-Welt (Pulse-µs, Servo-Pin-indexed) — und nutzen dabei
sowohl die `Calibration`-Lib aus Stufe C als auch die in `on_init`
gebaute Joint→Pin-Tabelle.

### `write()` — eine Frame-Engine pro Tick

```
hw_command_positions_[i]  (rad, URDF-Slot)
        │
        │   NaN-Check (keep last good + WARN)
        │
        │   joint_to_output_idx_[i] → output_idx (Pin 0..17)
        │   Calibration::radians_to_pulse_us(output_idx, rad)
        │   std::clamp(pulse, INT16_MIN, INT16_MAX)
        ▼
last_command_pulse_us_[output_idx]  (Pulse-µs, Servo-Pin)
        │
        │   encode_set_targets(seq++, last_command_pulse_us_)
        ▼
                 Wire-Frame
        │
        │   serial_port_.write_all()    (50 ms POLLOUT-Timeout)
        ▼
              USB-CDC → Servo2040
```

Drei Sicherheits-Layer pro Tick:

1. **`reader_.died()`-Check VOR jedem Tick.** Wenn der Reader-Thread
   bereits einen Disconnect detektiert hat (POLLHUP/EIO), bricht write()
   sofort mit `ERROR_ONCE`-Log und `return_type::ERROR` ab. ros2_control
   sieht den Error und bringt den Controller in `inactive`.
2. **NaN-Sanity.** Ein bug-haftes JTC-Spline oder ein numerischer Glitch
   kann NaN in `hw_command_positions_` schreiben. Wir lassen NaN
   **niemals** in die Calibration-Konversion oder auf die Wire — wir
   loggen die bug-verdächtige Eingabe (WARN) und behalten den letzten
   guten Pulse-Wert für diesen Pin.
3. **int16-Clamp.** `radians_to_pulse_us` extrapoliert linear über die
   Joint-Limits hinaus (kein Hard-Clamp dort — by design, um Limit-
   Verletzungen sichtbar zu machen). Für extreme rad-Werte könnte
   `pulse_d` aus dem int16-Range fliegen → `std::clamp` zwingt vor dem
   Cast in den gültigen Bereich. Defense-in-depth: die Firmware clampt
   nochmal auf `pulse_min`/`pulse_max` pro Servo (Phase-7 Stufe C.1).

### `read()` — Echo-State zurück

```
last_command_pulse_us_[output_idx]  (was wir gerade rausgeschickt haben)
        │
        │   joint_to_output_idx_[i] (für URDF-Slot i)
        │   Calibration::pulse_us_to_radians(output_idx, pulse_us)
        ▼
hw_state_positions_[i]              (rad, URDF-Slot — vom JTC gelesen)
```

Die Servos liefern **kein** echtes Positions-Feedback (Phase-7-Hardware-
Begrenzung). Stattdessen reflektiert `read()` den letzten Sollwert
zurück durch die inverse Konversion. JTC sieht damit ein perfekt
verfolgendes Robot — strukturell ist der Tracking-Error ≈ 0.

Das hat eine **wichtige Konsequenz für `controllers.yaml`** (Stufe F):
- `stopped_velocity_tolerance` greift nicht (Velocity ≈ 0 zwischen Ticks
  weil Echo identisch zum letzten Sollwert ist)
- JTC-Goal-Tolerance-Checks sind trivial erfüllt
- Echte Diagnose erfordert Strommessung oder einen externen Sensor
  (Phase 10+)

Zusätzlich erledigt `read()` zwei Buchhaltungs-Aufgaben:

- **Drain der ERROR_REPORT-Queue.** Der Reader-Thread queueisiert
  Firmware-Errors (WATCHDOG_TRIPPED, OVERCURRENT, …) wie sie ankommen.
  `read()` drainet einmal pro Tick und loggt jeden Eintrag. Per-Code-
  Translation kommt in D.8.
- **`reader_.died()`-Check.** Analog zu write(). Wenn der Reader im
  Hintergrund gestorben ist, surface'n wir das via `return_type::ERROR`.

### Permutation-Awareness durch `joint_to_output_idx_`

Die URDF kann die 18 Joints in **beliebiger Reihenfolge** im
`<ros2_control>`-Block listen. Bei write/read muss die richtige
Übersetzung passieren:

```
URDF-Slot 0  =  leg_3_femur_joint  =  Servo-Pin 7
URDF-Slot 1  =  leg_1_coxa_joint   =  Servo-Pin 0
   …
```

`hw_command_positions_[0]` ist also der Sollwert für `leg_3_femur_joint`,
und der gehört auf `last_command_pulse_us_[7]` → Pin 7. Die
`joint_to_output_idx_`-Tabelle (in `on_init` gebaut) übersetzt das.

Test `LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` setzt eine
reverse-sortierte URDF mit per-Slot distinkten Werten — wenn die
Mapping-Tabelle in write()/read() vergessen würde (z.B.
`hw_state_positions_[output_idx]` statt `hw_state_positions_[i]`),
würden Werte auf falschen Slots landen und der Test failed sofort.

### Was passiert in Loopback?

In `loopback_mode=true` (URDF-Param) skipt das Plugin alle Wire-I/O,
aber **macht die gesamte Konversion trotzdem** — d.h.:

- write() führt Konversion + last_command_pulse_us_-Update durch,
  überspringt aber `encode_set_targets + write_all`
- read() führt Echo + Konversion durch
- ERROR_REPORT-Queue ist leer (kein Reader-Thread läuft)
- `reader_.died()`-Check entfällt (kein Reader)

Damit ist Loopback ein vollwertiger End-to-End-Test-Modus für CI: alle
Logik-Pfade werden durchlaufen, nur die echte USB-Kommunikation fällt
aus. Tests `LoopbackRoundtripsCommandThroughCalibration` und
`LoopbackEchoesAreSlotCorrectWithPermutedJointOrder` verifizieren, dass
`rad → pulse → rad` ≤ 2 mrad Toleranz roundtrippt.

Tests in [`test/test_hexapod_system.cpp`](test/test_hexapod_system.cpp)
(9 Test-Cases in der Suite `HexapodSystemWriteRead`): Roundtrip-Genauigkeit,
Permutations-Mapping, NaN-Sanity, Int16-Clamp gegen UB, byteweise
Verifikation des SET_TARGETS-Frames, ERROR_REPORT-Drainage, und
Disconnect-Verhalten für beide Hooks.

---

## Boot-Sequenz (Stufe D.5) — was passiert beim Activate?

`on_activate` ist der Lifecycle-Hook, den `controller_manager` aufruft, wenn
ein User (oder ein Launch-File) den Plugin aus dem `inactive`-State in
`active` schaltet — also genau dann, wenn die Servos „echt loslegen sollen".

Die Implementation folgt einer 3-Phasen-Boot-Sequenz, die in
[`~/hexapod_servo_driver/PROTOCOL.md §5–§6`](file:///home/enjoykin/hexapod_servo_driver/PROTOCOL.md)
spezifiziert ist und in Phase 7 (Firmware) Design-Entscheidung D.1 fixiert
wurde:

```
on_activate:
  ┌──────────────────────────────────────────────────────────────┐
  │ 1. RESET (1 Frame)                                           │
  │    Clears WATCHDOG_TRIPPED falls Plugin vorher unsauber weg  │
  │    Sleep 10 ms (Firmware-Atempause)                          │
  └──────────────────────────────────────────────────────────────┘
            │
            ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ 2. ENABLE_SERVO × 18 (mit 50 ms Stagger zwischen Frames)     │
  │    pin 0 → enable=true → sleep 50 ms                         │
  │    pin 1 → enable=true → sleep 50 ms                         │
  │    ...                                                       │
  │    pin 17 → enable=true → sleep 50 ms                        │
  │    ───────────────────────                                   │
  │    Total: ~900 ms (18 × 50 ms)                               │
  └──────────────────────────────────────────────────────────────┘
            │
            ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ 3. SET_TARGETS [alle 18 pulse_zero]                          │
  │    Definierte Neutralpose (≈ 1500 µs ≡ 0 rad)                │
  │    Watchdog warmhalten bis erster write()-Tick               │
  └──────────────────────────────────────────────────────────────┘

Total Activate-Dauer: ~910 ms in non-loopback, < 100 ms in loopback (skip stagger)
```

### Warum diese drei Phasen?

**RESET-voran (Punkt 1):** Wenn das Plugin in einem vorherigen Run unsauber
weggebrochen ist (SIGKILL, Crash, USB gezogen), kann die Firmware noch im
`WATCHDOG_TRIPPED`-Zustand stecken — in dem Zustand werden alle nachfolgenden
`ENABLE_SERVO`-Frames mit `NACK` beantwortet (PROTOCOL.md §6). RESET macht
die Boot-Sequenz **idempotent** unabhängig davon, wie der letzte Run endete.

**Stagger 50 ms (Punkt 2):** Wenn alle 18 Servos gleichzeitig spannungsfrei
→ spannungs-versorgt werden, sehen wir bis zu **18 × Inrush-Strom-Peak**
auf dem Servo-Rail. Das kann die Bench-PSU (oder später den Akku) in den
Overcurrent-Cut-Off treiben. Mit 50 ms Pause zwischen den Servos sind die
Peaks zeitlich entkoppelt (~900 ms Gesamtdauer ist aufs Boot-Erlebnis
hinnehmbar). Phase-7-Design-Entscheidung D.1: **Host macht den Stagger**,
Firmware bleibt dumm.

**Neutralpose-Frame (Punkt 3):** Zwei Funktionen gleichzeitig:
1. **Definierter Initial-State.** Vor der ersten JTC-Trajectory steht
   der Roboter in einer bekannten Pose (alle Joints auf 0 rad,
   ≈ 1500 µs pulse_zero pro Servo). Sonst würde das Robot je nach
   letztem Servo-Befehl irgendwo stehen.
2. **Watchdog-Bridge.** Die Firmware-seitige Watchdog wirft `WATCHDOG_TRIPPED`
   wenn 200 ms lang **kein valides Frame** ankommt (PROTOCOL.md §6).
   Zwischen Activate-Ende und dem ersten `controller_manager`-Tick könnten
   in pathologischen Launch-Timings > 200 ms vergehen. Das SET_TARGETS-Frame
   am Activate-Ende setzt den Timer auf 0 und überbrückt die Lücke.

### Defensives `send_frame`-Pattern

Alle Wire-Writes in `on_activate` gehen durch eine lokale Lambda
`send_frame(frame, what)`, die zwei Sicherheitsmaßnahmen bündelt:

1. **`reader_.died()`-Check vor jedem Write.** Wenn der USB-Stecker zwischen
   `on_configure` und `on_activate` gezogen wurde, hat der Reader-Thread
   bereits `POLLHUP` gesehen und sein `died_`-Flag gesetzt. Statt jetzt
   blind ins offene Messer zu rennen (`write_all` → EIO → exception chain),
   bricht die Lambda mit einem klaren FATAL-Log ab und kehrt false zurück.
   `on_activate` returns `ERROR`, der `controller_manager` hält den
   Plugin in `inactive`.

2. **Exception-Catch um `write_all`.** Falls der Disconnect erst während
   Activate landet (z.B. mitten in den 18 ENABLE-Frames), wirft `write_all`
   ein `std::system_error`. Die Lambda catcht es, loggt FATAL mit Kontext
   („Failed to send ENABLE_SERVO frame: …") und bricht ab.

In **Loopback-Mode** (`loopback_mode=true` im URDF-`<param>`) ist die
Lambda ein No-Op und der Stagger ist 0 ms — die Boot-Sequenz wird komplett
in unter 100 ms durchlaufen für schnelle CI-Tests. Die Encoder-Aufrufe
und `seq_`-Increments werden trotzdem durchgeführt, sodass Tests indirekt
verifizieren können, dass die Sequenz „in trockener Form" funktioniert.

### `on_deactivate` — Spiegelbild ohne Stagger

`on_deactivate` schickt `ENABLE_SERVO(pin, false)` für alle 18 Servos
**ohne Stagger**. Disable hat keinen Inrush, und wir wollen Torque-off
so schnell wie möglich (z.B. wenn der User ein Sicherheits-Problem
erkennt und den Controller deaktiviert).

Failures beim Senden werden als WARN geloggt, die Schleife bricht aber
nicht ab (Best-Effort). Hintergrund: selbst wenn die Disable-Frames
verloren gehen (z.B. USB-Disconnect), springt nach 200 ms die
Firmware-Watchdog ein und disabled die Servos sowieso. Hard-Fail wäre
hier kontraproduktiv.

### Was passiert NICHT in D.5

- **Kein automatisches RESET** wenn Watchdog mid-run tripped. User
  entscheidet manuell (Phase-10-Tool oder Stack-Restart). Plugin loggt
  den Trip, `read()` (kommt in D.6) returnt `ERROR`, `controller_manager`
  fährt Plugin in `inactive`.
- **Kein read/write mit echter Pulse-Konversion** — D.6.
- **Kein Reconnect-Versuch im Activate-Pfad** — D.7. Mid-Activate-Disconnect
  führt zu sauberem Abort mit `ERROR`.

Tests in [`test/test_hexapod_system.cpp`](test/test_hexapod_system.cpp)
(6 Test-Cases in der Suite `HexapodSystemActivate`): byteweise Verifikation
der Wire-Frames auf einer PTY-Master-Seite, Stagger-Timing-Bounds,
Cycle-Repeatability, USB-Disconnect-Robustness.

---

## Die `on_init`-Signatur — was bedeutet das?

Beim Bauen in Stufe A kam initial folgende Warnung:

```
warning: 'on_init(const HardwareInfo &)' is deprecated:
  Use on_init(const HardwareComponentInterfaceParams & params) instead.
```

Damit du das einordnen kannst, hier die Hintergründe:

### Was ist eine „Funktions-Signatur" in C++?

Die Signatur einer Funktion = Funktions-**Name** + **Parameter-Typenliste**
(in genau der Reihenfolge, inklusive `const`/`&`-Modifier). Die
Parameter-**Namen** zählen nicht, der Rückgabetyp zählt bei freier
Funktion nicht, bei überschriebenen virtuellen Methoden aber schon.

Beispiele:
- `void f(int)` und `void f(double)` → **verschiedene** Signaturen
- `void f(int x)` und `void f(int y)` → **gleiche** Signatur
- `void f(const int &)` und `void f(int)` → **verschiedene** Signaturen

In C++ kann eine Klasse mit `override` eine virtuelle Methode der Basis-
Klasse überschreiben. Der Compiler prüft, dass die Signatur **exakt**
mit der Basis-Klassen-Methode übereinstimmt — wenn die Basis-Klasse die
Signatur ändert (anderer Parameter-Typ z.B.), bekommt unsere Subklasse
einen Compile-Fehler. Das ist der Mechanismus, der ros2_control hier
benutzt, um die API zu evolvieren.

### Alte vs. neue `on_init`-Signatur

**Alt** (deprecated in ros2_control 4.44, kommt aus Jazzy):
```cpp
virtual CallbackReturn on_init(const HardwareInfo & hardware_info);
```

`HardwareInfo` ist die geparste URDF-Information über das Hardware-
Plugin (Joint-Liste, Parameter, Limits).

**Neu** (empfohlen ab 4.44):
```cpp
virtual CallbackReturn on_init(const HardwareComponentInterfaceParams & params);
```

`HardwareComponentInterfaceParams` ist ein Struct, das **mehr** enthält:
```cpp
struct HardwareComponentInterfaceParams {
    HardwareInfo hardware_info;          // wie vorher
    rclcpp::Executor::WeakPtr executor;  // neu: Zugriff auf den ROS-Executor
};
```

### Warum hat sich das geändert?

Hardware-Plugins können jetzt einen **eigenen ROS-Node** in den
gemeinsamen Executor einhängen — z.B. um Topics zu publishen
(`/imu/data` oder Diagnose-Topics) ohne einen separaten Thread zu
brauchen. Der neue `executor`-WeakPtr ist der Hook dafür.

Für unser Plugin in **Phase 9** brauchen wir das nicht aktiv. Aber die
neue Signatur ist die zukunftssichere, und wenn wir später z.B.
Strom-Diagnose-Topics aus dem Plugin publishen wollen, ist der Weg
schon offen. Hätten wir die deprecated-Variante behalten, würden wir in
einer späteren ros2_control-Version (Kilted, L-Release) Compile-Fehler
bekommen.

### Was wir konkret gemacht haben

In [include/hexapod_hardware/hexapod_system.hpp](include/hexapod_hardware/hexapod_system.hpp):
```cpp
hardware_interface::CallbackReturn on_init(
  const hardware_interface::HardwareComponentInterfaceParams & params) override;
```

In [src/hexapod_system.cpp](src/hexapod_system.cpp):
```cpp
hardware_interface::CallbackReturn HexapodSystemHardware::on_init(
  const hardware_interface::HardwareComponentInterfaceParams & params)
{
  if (hardware_interface::SystemInterface::on_init(params) !=
    hardware_interface::CallbackReturn::SUCCESS) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  // ...
}
```

`params.hardware_info` ist dann das, was vorher direkt `info` hieß.
Innerhalb der Klasse greifen wir aber sowieso über `info_` zu — das ist
ein protected-Member, das von der Basis-Klasse aus `params` befüllt
wird, wenn `SystemInterface::on_init(params)` aufgerufen wird.

---

## Was kommt in den nächsten Stufen

| Stufe | Inhalt | Status |
|---|---|---|
| **A** | Paket-Skelett, Build, pluginlib-Setup | ✅ |
| **B** | COBS + CRC-16/CCITT-FALSE + alle Opcode-Encoder/Decoder mit 36 Unit-Tests | ✅ |
| **C** | YAML-Loader (yaml-cpp), 3-Punkt-Konversion, 30 Unit-Tests | ✅ |
| **D** | Lifecycle voll, Reader-Thread, Loopback-Mode, USB-Reconnect | 🟡 in Arbeit (D.1/8) |
| └ D.1 | SerialPort-Wrapper (cfmakeraw, O_NONBLOCK+poll, shared_mutex), 14 Tests | ✅ |
| └ D.2 | Reader-Thread mit Frame-Stream-Parser + RAII-Lifecycle, 17 Tests | ✅ |
| └ D.3 | on_init mit URDF-Joints + Calibration-Lookup-Tabelle, 17 Tests | ✅ |
| └ D.4 | on_configure / on_cleanup (Port öffnen/schließen, Reader-Lifecycle), 6 Tests | ✅ |
| └ D.5 | on_activate Boot-Sequenz (RESET + 18×ENABLE 50 ms stagger + SET_TARGETS neutral) + on_deactivate Disable-All, 6 Tests | ✅ |
| └ D.6 | read/write mit Echo-State + Pulse-Konversion + Permutations-Mapping-Test + NaN-Sanity + Int16-Clamp + ERROR_REPORT-Drain, 9 Tests | ✅ |
| └ D.7 | USB-Reconnect-Logik mit Backoff `{100..5000}` ms, Reader-Thread retried statt zu sterben, manueller Re-Activate, 5 Tests | ✅ |
| └ D.8 | ERROR_REPORT-Routing pro Error-Code mit WARN/ERROR/FATAL-Severity + human-readable Messages, 11 Tests | ✅ |
| **D** | **Komplett — 8/8 Sub-Stages** | ✅ |
| **E** | Plugin-Registrierung runtime via `pluginlib::ClassLoader` verifiziert (3 Tests) + Test-Helper-Refactor in `test/test_helpers.hpp` | ✅ |
| **F** | URDF-Switch (`use_sim` xacro-arg + `<xacro:if>`-Conditionals) + `controllers.real.yaml` (50 Hz, position-only state, no velocity); F-T8/T10 Sim-Regression-Smoke grün; F-T9 nach Stage G verschoben | ✅ |
| **G** | `real.launch.py` in `hexapod_bringup` (RSP + ros2_control_node + JSB+6JTC-Spawner-Chain) mit LaunchArgs `loopback_mode` (default false) + `serial_port` (default /dev/ttyACM0). G-T4 Loopback-Bringup-Smoke + G-T7/T8 Sim-Regression grün | ✅ |
| **H** | Echte Servo2040-Anbindung (CI-Anteil): real.launch.py ohne Loopback, Plugin lädt mit echter Firmware, JTC-Trajectory-Roundtrip, USB-Reconnect-Smoke (D.7 real-world bestätigt), Cleanup. **Oszi-Anteil (H-T8 PWM-Wellenform + H-T9 Logic-Analyzer-USB-Frame-Capture) ⏸️ pending wegen Hardware-Limit** — voll dokumentiert in `phase_9_stage_h_test_commands.md`, Cross-Session-Reminder im Memory | ✅ (CI) / ⏸️ (Oszi) |
| **I** | launch_testing-Suite für real.launch.py loopback (3 Tests headless-CI in hexapod_bringup), README-Quick-Start-Block (Aufrufe + Plugin-Params + Topics + Echo-State + bekannte WARN); tcflush-Fix-Vorschlag zurückgezogen (Code existiert bereits) | ✅ |
| **J** | Phase-9-Abschluss: `<ros2_control name="GazeboSimSystem">` → `name="HexapodSystem"` (1-Zeile-Rename), PHASE.md auf Phase 10 aktiv, hexapod_hardware/README Status 🟡 → 🟢, progress.md Stage-J + Phase-9-Done-Banner + Retro | ✅ |

---

## Quellen

- Phase-9-Plan: [`docs_raspi/phase_9_hexapod_hardware.md`](../../docs_raspi/phase_9_hexapod_hardware.md)
- Phase-9-Progress: [`docs_raspi/phase_9_progress.md`](../../docs_raspi/phase_9_progress.md)
- Firmware-Repo: `~/hexapod_servo_driver/`
- Wire-Protokoll: `~/hexapod_servo_driver/PROTOCOL.md`
- Servo-Mapping-Quelle: `~/hexapod_servo_driver/contrib/servo_mapping.yaml`
