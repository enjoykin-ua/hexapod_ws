# hexapod_hardware

ROS2-Plugin (`ros2_control` SystemInterface), das den Hexapod über das
**Servo2040-Board** per USB-CDC steuert. Das Plugin ersetzt zur Laufzeit
das Sim-Plugin `gz_ros2_control` und exportiert 18 Position-Command-/
State-Interfaces an `controller_manager`.

Status: 🟡 **In Entwicklung — Phase 9.**
Aktueller Stand: Stufen A + B + C abgeschlossen — Skelett, Build-Setup,
Wire-Protokoll-Layer (36 Tests inkl. 5 goldener Hex-Anker), und
Kalibrierungs-Lib (30 Tests, piecewise-linear rad↔pulse-µs Konversion
mit yaml-cpp Loader und Strong-Exception-Guarantee beim Reload).

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
| **C** | YAML-Loader (yaml-cpp), 3-Punkt-Konversion, 27 Unit-Tests | ✅ |
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
