# hexapod_hardware

ROS2-Plugin (`ros2_control` SystemInterface), das den Hexapod über das
**Servo2040-Board** per USB-CDC steuert. Das Plugin ersetzt zur Laufzeit
das Sim-Plugin `gz_ros2_control` und exportiert 18 Position-Command-/
State-Interfaces an `controller_manager`.

Status: 🟡 **In Entwicklung — Phase 9.**
Aktueller Stand: Stufe A abgeschlossen (Skelett + Build-Setup).

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

### `hexapod_hardware::HexapodSystemHardware`

Subklasse von `hardware_interface::SystemInterface`. Wird zur Laufzeit
über `pluginlib` geladen und vom `controller_manager` durch eine feste
**Lifecycle**-Reihenfolge gefahren:

| Lifecycle-Hook | Aufgabe (Soll, kommt in Stufe D) |
|---|---|
| `on_init`        | URDF-Joint-Liste auswerten, Vektoren allokieren, Kalibrierungs-YAML laden |
| `on_configure`   | Serial-Port öffnen (`/dev/ttyACM0`), termios setzen, Reader-Thread starten |
| `on_activate`    | 18× `ENABLE_SERVO`-Frames mit 50 ms Stagger schicken (Host-Stagger, V1) |
| `on_deactivate`  | `DISABLE`-Frames, Reader-Thread stoppen, Port schließen |
| `read`           | Letztes STATE-Frame in `hw_state_positions_` schreiben (Echo) |
| `write`          | Command-Vektor → Pulse-µs → `SET_TARGETS`-Frame senden |

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
`docs_raspi/phase_9_progress.md` „Design-Entscheidung Option C"):

```
slope_left  = (pulse_zero - pulse_min) / |joint_lower|   µs/rad
slope_right = (pulse_max - pulse_zero) /  joint_upper    µs/rad

joint_rad ≥ 0:  pulse_us = pulse_zero + direction · joint_rad · slope_right
joint_rad < 0:  pulse_us = pulse_zero + direction · joint_rad · slope_left
```

Die URDF-Joint-Limits (`joint_lower`, `joint_upper`) werden in
`on_init` aus der URDF gelesen und per `set_joint_limits()` an die
`Calibration`-Instanz übergeben.

**Aktuell (Stufe A):** Stub-Implementierungen — `radians_to_pulse_us`
gibt fix `1500.0` zurück.

### `servo2040_protocol.hpp`

Konstanten und Frame-API gespiegelt aus dem Firmware-Repo
(`~/hexapod_servo_driver/src/config.hpp` + `PROTOCOL.md`):

- Opcodes: `SET_TARGETS=0x01`, `GET_STATE=0x02`, `STATE_RESPONSE=0x82`,
  `ENABLE_SERVO=0x20`, `RESET=0x50`, `ACK=0xFF`, `NACK=0xFE`,
  `ERROR_REPORT=0x7F`, … (vollständige Liste siehe Header)
- Error-Codes: `FRAME_CRC=0x01`, `PULSE_OUT_OF_RANGE=0x10`,
  `WATCHDOG_TRIPPED=0x40`, …
- Status-Flag-Bits (für das `status_flags`-Byte im STATE-Frame)

Frame-API (Forward-Decls; Implementierung in Stufe B):
- `encode_set_targets(seq, pulse_us[18]) → bytes`
- `encode_get_state(seq)`, `encode_enable_servo(seq, idx, on/off)`,
  `encode_reset(seq)`
- `decode_state(payload) → optional<StatePayload>`
- `decode_error_report(payload) → optional<ErrorReport>`
- `crc16_ccitt_false`, `cobs_encode`, `cobs_decode` — die unteren Bausteine

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
| **B** | COBS + CRC-16/CCITT-FALSE + alle Opcode-Encoder/Decoder mit Unit-Tests | offen |
| **C** | YAML-Loader (yaml-cpp), 3-Punkt-Konversion, Unit-Tests | offen |
| **D** | Lifecycle voll, Reader-Thread, Loopback-Mode, USB-Reconnect | offen |
| **E** | Plugin-Registrierung verifizieren | offen |
| **F** | URDF-Switch + `controllers.real.yaml` | offen |
| **G** | `real.launch.py` | offen |
| **H** | Echte Servo2040-Anbindung mit Oszi/Logic-Analyzer | offen |
| **I** | Tests + diese README finalisieren | offen |

---

## Quellen

- Phase-9-Plan: [`docs_raspi/phase_9_hexapod_hardware.md`](../../docs_raspi/phase_9_hexapod_hardware.md)
- Phase-9-Progress: [`docs_raspi/phase_9_progress.md`](../../docs_raspi/phase_9_progress.md)
- Firmware-Repo: `~/hexapod_servo_driver/`
- Wire-Protokoll: `~/hexapod_servo_driver/PROTOCOL.md`
- Servo-Mapping-Quelle: `~/hexapod_servo_driver/contrib/servo_mapping.yaml`
