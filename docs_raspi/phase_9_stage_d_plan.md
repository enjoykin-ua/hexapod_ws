# Phase 9 — Stufe D — Plan

> **Status:** Plan, noch nicht implementiert.
> **Zweck dieser Datei:** Stufe D ist die größte und komplexeste Stufe in
> Phase 9 (Lifecycle, Threading, Serial-I/O, Reconnect-Logik). Damit nichts
> blind gecodet wird, dokumentieren wir hier zuerst Architektur und
> Sub-Staging und holen User-Bestätigung. Implementiert wird erst nach
> Freigabe.
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md) Stufe D.
> **Sub-Stage-Tests:** pro D.x ein eigenes `phase_9_stage_d_x_test_commands.md` (wird mit der jeweiligen Sub-Stage erstellt).

---

## Ziel der Stufe D

Die `HexapodSystemHardware`-Klasse aus Stufe A — bisher nur ein Stub mit
SUCCESS-Returns — wird zum **vollständigen ros2_control-`SystemInterface`-Plugin**.
Nach Stufe D kann ein `controller_manager` das Plugin laden, der
Lifecycle (init → configure → activate → read/write 50 Hz → deactivate)
läuft sauber durch, und auf der Wire kommen die in Stufe B implementierten
Frames raus.

Ende von Stufe D:
- **In Loopback-Modus** (kein Serial-Port nötig) ist das Plugin komplett
  end-to-end testbar — Lifecycle, `read()`, `write()`, Pulse-Konversion.
- **Mit echtem Servo2040 am USB** funktioniert die Anbindung — aber das
  Verifizieren am Logic-Analyzer/Oszi passiert erst in Stufe H. In D
  selbst sichert nur „Plugin baut, läuft, blockiert nicht".

---

## Architektur-Entscheidungen

Drei Punkte sind vor der Implementation klar (mit User abgestimmt am
2026-05-15):

### A — Threading-Modell

Ein einziger zusätzlicher Thread, den wir starten und stoppen: der
**Reader-Thread**. Der ros2_control-`controller_manager` läuft in
seinem eigenen Thread, den verwalten wir nicht.

```
┌─────────────────────────────────────────────────────────────┐
│ Thread A — controller_manager (von ros2_control gestartet)  │
│ Läuft mit 50 Hz fest:                                       │
│   1. ruft unser read()  ← liest aus Cache, nicht-blockierend│
│   2. Controller berechnen (JTC, JSB) — nicht unser Code     │
│   3. ruft unser write() ← schickt SET_TARGETS raus (~1 ms)  │
│ Wenn write() oder read() blockieren, blockiert ALLES.       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ read()/write() Aufrufe
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ HexapodSystemHardware (unser Plugin)                        │
│   - last_command_pulse_us_[18] ← write() schreibt rein      │
│   - state_cache + error_queue  ← Reader-Thread füllt rein   │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Mutex-geschützt
                              │
┌─────────────────────────────────────────────────────────────┐
│ Thread B — Reader (WIR starten/stoppen ihn)                 │
│ Liest blockierend vom /dev/ttyACM0:                         │
│   - sammelt Bytes bis 0x00                                  │
│   - decode_frame()                                          │
│   - bei STATE_RESPONSE → in state_cache                     │
│   - bei ERROR_REPORT   → in error_queue                     │
│   - bei ACK/NACK       → loggen (DEBUG)                     │
│ Bei Disconnect: Reconnect-Schleife mit Backoff.             │
└─────────────────────────────────────────────────────────────┘
```

**Datenfluss „raus" (Host → Servo2040):** *nur* Thread A schreibt Bytes
auf den FD (in `write()` und im Activate-Stagger). Ein einziger Sender.

**Datenfluss „rein" (Servo2040 → Host):** *nur* Thread B liest Bytes
vom FD und parst Frames. Ein einziger Empfänger.

→ Keine Schreib-Race auf dem FD selbst. Synchronisation nur am
**State-Cache und Error-Queue** (`std::mutex`) und beim
**Shutdown-Signal** an Thread B (`std::atomic<bool> stop_requested_`).

**Implementation:** `std::thread`. Standard, keine externen Libs.

### B — Kein GET_STATE-Polling in Phase 9

Wir senden **keine GET_STATE-Frames** in dieser Phase. Konsequenz: der
Reader-Thread sieht **nur unsolicited Frames** vom Servo2040 —
hauptsächlich ERROR_REPORTs bei Trip-Events (Watchdog, Overcurrent,
Undervoltage).

**Warum kein Polling?**

- Die einzige Information für ros2_controls `read()` wäre die echte
  Servo-Position — die liefern die Servos hardwareseitig **nicht**. Wir
  spiegeln stattdessen den letzten `write()`-Sollwert zurück
  (**Echo-State**, siehe Punkt unten).
- Voltage/Current wären über GET_STATE abrufbar, aber wir haben in
  Phase 9 **keinen Konsumenten** dafür — kein Diagnostik-Topic, kein
  Effort-Interface (siehe C). Daten holen die niemand nutzt = Overhead.
- ERROR_REPORTs kommen **unsolicited** mit dem aux-Feld als
  Messwert-Snapshot (z.B. `aux = gemessene mA bei Overcurrent`). Damit
  haben wir genau das was wir für Logs/Diagnose brauchen, **ohne** zu
  pollen.

**Reader-Thread im Normalbetrieb 99% der Zeit:** blockiert auf
`read(fd, …)` mit Timeout, kein Verkehr von Servo2040. Wenn ein
Trip-Event passiert: Reader liest das ERROR_REPORT-Frame, dispatched
es in die Queue, `read()`-Callback im Plugin holt es ab und loggt per
`RCLCPP_ERROR`.

### C — Position-only Interfaces, kein Effort

Pro Joint exportieren wir **nur**:
- `position` als `CommandInterface`
- `position` als `StateInterface`

**Kein** Effort-Interface. Begründung: Servo2040-Hardware liefert nur
Total-Rail-Strom, keinen Per-Servo-Strom. Ein Effort-Slot mit
Slot-0=Gesamt-und-Rest=0 wäre verwirrend für jeden Consumer (JTC,
RViz, Bag-Recording).

Wenn wir später Diagnostik brauchen, kommt das als **eigenes
ROS-Topic** (`/hexapod/voltage`, `/hexapod/total_current_ma`,
`/hexapod/status_flags`) aus einem separaten Diagnose-Pfad. Das ist
Phase-10-Stoff oder eigene IMU-/Sensor-Phase.

### Datenfluss bei Echo-State im Detail

```
gait_node → JTC → controller_manager.write() → HexapodSystemHardware.write()
                                                  │
                                                  ▼
        hw_command_positions_[i] ← Joint-Sollwert in Radiant (vom JTC)
                                                  │
                                                  │ Calibration.radians_to_pulse_us
                                                  ▼
        last_command_pulse_us_[i] ← Pulse-µs (int16, geclamped passiert auf FW-Seite)
                                                  │
                                                  │ encode_set_targets(seq, pulses)
                                                  ▼
                                              write(fd, …)
                                                  │
                                                  ▼
                                            Servo2040 setzt PWM


Beim nächsten read()-Tick (50 Hz später):
                  HexapodSystemHardware.read()
                                                  │
        last_command_pulse_us_[i] ─────────────┐
                                               │
                                               │ Calibration.pulse_us_to_radians
                                               ▼
                                hw_state_positions_[i]   ← was JTC als „aktueller Joint"-Wert sieht
                                               │
                                               ▼
              controller_manager → JTC: Tracking-Error ≈ 0 (strukturell)
```

→ Der Tracking-Error des JTC ist **immer null**, weil wir den Sollwert
direkt als Istwert zurückgeben. Das ist eine bekannte Limitation und
schon in der README dokumentiert. Diagnose-Ersatz wäre Strommessung —
deferred auf später.

---

## Sub-Stages D.1 — D.8

Die Stufe ist linear: jede Sub-Stage baut auf der vorherigen auf. Jede
hat ein eigenes Done-Kriterium und einen eigenen Test (in einem
`phase_9_stage_d_<x>_test_commands.md` der mit der Sub-Stage erstellt
wird).

### D.1 — Serial-Port-Wrapper

**Was:** Eine RAII-Klasse `SerialPort` die einen POSIX-FD auf
`/dev/ttyACM*` öffnet, termios konfiguriert und automatisch
schliesst.

**Wichtig:** `cfmakeraw()` zwingend benutzen. Ohne das ist die
Linux-TTY-Line-Discipline aktiv und mappt `0x0D` automatisch zu `0x0A`
beim Lesen (ICRNL) bzw. expandiert `0x0A` zu `0x0D 0x0A` beim Schreiben
(ONLCR). Bei binärem COBS+CRC-Protokoll bricht das jedes Frame mit
einem `0x0D` im CRC-Feld. Das war einer der zwei Bugs in Phase 7 C.4
(Postmortem ausführlich dokumentiert).

**API-Skizze:**
```cpp
class SerialPort {
public:
    void open(const std::string & path);              // wirft bei Fehler
    void close() noexcept;
    bool is_open() const noexcept;
    void write_all(const uint8_t * data, size_t len); // blockt bis alles raus
    ssize_t read_some(uint8_t * buf, size_t max_len); // blockt mit VTIME-Timeout
    ~SerialPort();                                    // schließt FD
};
```

Termios-Setup: `cfmakeraw`, `VMIN=0`, `VTIME=10` (= 1 s Timeout pro
read-Aufruf), Baudrate egal (USB-CDC ignoriert).

**Done-Kriterium D.1:**
- `SerialPort` baut, leakt keinen FD bei Exception
- Test mit Linux-PTY-Pair (`openpty(3)`): Schreiben in den Master, Lesen
  vom Slave funktioniert binär-sauber (alle 256 Byte-Werte überleben)
- `read_some` mit VTIME-Timeout liefert 0 zurück wenn nichts kommt

### D.2 — Reader-Thread

**Was:** Eine Klasse `Servo2040Reader` (oder als Methoden in
`HexapodSystemHardware`), die im Hintergrund-Thread Bytes vom
`SerialPort` liest, auf `0x00` splittet, `decode_frame()` aufruft und
die Ergebnisse in zwei Caches verteilt.

**API-Skizze:**
```cpp
class Servo2040Reader {
public:
    void start(SerialPort & port);   // forkt Thread
    void stop() noexcept;            // setzt Atomic-Flag, joined Thread

    // Thread-safe Zugriff für Plugin:
    std::optional<StatePayload> latest_state();           // peek, kein consume
    std::vector<ErrorReport>    drain_error_queue();      // alles in einem
};
```

**Synchronisation:**
- `state_cache_`: `std::mutex` + `std::optional<StatePayload>`. Reader
  schreibt, Plugin liest.
- `error_queue_`: `std::mutex` + `std::vector<ErrorReport>`. Reader
  pusht, Plugin drained pro `read()`-Tick.
- `stop_requested_`: `std::atomic<bool>`. Reader prüft nach jedem
  Read-Timeout.

**Reader-Loop in Pseudocode:**
```
buffer = []
while (!stop_requested_) {
    bytes_read = port.read_some(tmp_buf, …);
    if (bytes_read < 0 && errno indicates disconnect)
        → trigger reconnect (siehe D.7), break Reader-Loop
    for byte in tmp_buf[:bytes_read]:
        if byte == 0x00:
            frame = decode_frame(buffer);
            if (frame) dispatch(frame);
            buffer.clear();
        else:
            buffer.push_back(byte);
}
```

**Dispatch-Logik:**
- `cmd == STATE_RESPONSE`: `decode_state()` → `state_cache_`
- `cmd == ERROR_REPORT`: `decode_error_report()` → `error_queue_`
- `cmd == ACK / NACK`: `RCLCPP_DEBUG`-Log
- sonst: `RCLCPP_WARN("Unknown frame opcode 0x%02X")`

**Done-Kriterium D.2:**
- Reader baut, hat sauberen Start/Stop-Lifecycle
- Test mit PTY-Pair: Schreiben gültiger Frames in den Master, Reader
  sieht sie korrekt sortiert im Cache/Queue
- Test: Reader stoppt sauber wenn `stop()` aufgerufen wird (kein Hang,
  kein detach, kein Leak)
- Test: ungültige Frames (CRC-Bug, COBS-Bug, unbekannter Opcode) gehen
  in WARN-Log, nicht in Cache/Queue

### D.3 — `on_init`: URDF parsen, Calibration laden

**Was:** Der Lifecycle-Hook `on_init(HardwareComponentInterfaceParams &)`
wird vom `controller_manager` beim Plugin-Laden aufgerufen. Hier:

1. `info_ = params.hardware_info` (durch Base-Klasse)
2. `info_.joints` durchgehen — **muss exakt 18 sein**
3. Pro Joint:
   - Name validieren (`leg_<n>_{coxa,femur,tibia}_joint`-Schema)
   - URDF-`<limit lower upper>` aus `joint.command_interfaces`
     extrahieren (oder aus parameters, je nach ros2_control-Version)
4. Hardware-Parameter aus URDF auslesen:
   - `serial_port` (default `/dev/ttyACM0`)
   - `calibration_file` (default `$(find hexapod_hardware)/config/servo_mapping.yaml`)
   - `loopback_mode` (default `false`)
5. `Calibration::load_from_file(calibration_file_)`
6. Pro Joint: `Calibration::set_joint_limits(joint.name, lower, upper)`
7. State-/Command-Vektoren auf `info_.joints.size()` allokieren
8. `last_command_pulse_us_` auf `pulse_zero` initialisieren (neutral)

**Done-Kriterium D.3:**
- Test mit synthetischer `HardwareInfo` (18 Joints, alle 4 Parameter
  gesetzt): `on_init` returns SUCCESS, alle internen Strukturen befüllt
- Test mit fehlenden Joints (17 oder 19) → ERROR
- Test mit ungültigem `calibration_file`-Pfad → ERROR
- Test mit ungültigem `loopback_mode`-String → ERROR

### D.4 — `on_configure` / `on_cleanup`: Port öffnen, Reader starten

**Was:** Lifecycle-Hooks zwischen `init` und `activate`.

- `on_configure`:
  - Wenn `loopback_mode_ == true`: nichts tun, Returns SUCCESS
  - Sonst: `serial_port_.open(serial_port_path_)` + Reader-Thread
    starten
- `on_cleanup`:
  - Reader stoppen
  - Serial-Port schliessen
  - State auf „nicht-configured" setzen

**Done-Kriterium D.4:**
- Loopback-Test: `on_configure` → SUCCESS ohne Port-Open, Reader läuft
  nicht (auch nicht versehentlich)
- PTY-Test: `on_configure` öffnet PTY-Slave-Path, Reader-Thread läuft
- `on_cleanup` schliesst sauber, kein Thread-Leak
- Fehler-Pfad: ungültiger Port-Path → `on_configure` returns ERROR

### D.5 — `on_activate` / `on_deactivate`: Host-Stagger

**Was:** Im `on_activate`-Hook schickt der Host **18× `ENABLE_SERVO`**
mit **50 ms Pause zwischen den Frames** (PROTOCOL.md §5, Phase-7
Design-Entscheidung D.1). Total ~900 ms.

```cpp
hardware_interface::CallbackReturn on_activate(...) {
    for (uint8_t i = 0; i < NUM_SERVOS; ++i) {
        auto frame = encode_enable_servo(seq_++, i, /*enable=*/true);
        if (!loopback_mode_) serial_port_.write_all(frame.data(), frame.size());
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    return CallbackReturn::SUCCESS;
}
```

`on_deactivate` macht das Spiegelbild: 18× `ENABLE_SERVO(idx, false)`,
ohne Stagger (Disable ist nicht Inrush-kritisch).

**Done-Kriterium D.5:**
- Loopback-Test: `on_activate` → SUCCESS in ~900 ms, hat `seq_`
  18× inkrementiert
- Plus, weil der Stagger den Tick blockiert: Plugin-Lifecycle muss
  damit klarkommen. ros2_control erlaubt Activate-Hooks die etwas
  brauchen — wir sind im erlaubten Bereich.
- PTY-Test: Reader auf der anderen Seite sieht 18 ENABLE_SERVO-Frames
  in korrekter Reihenfolge mit ~50 ms Abstand

### D.6 — `read()` / `write()` mit Echo-State + Pulse-Konversion

**Was:** Die zwei Methoden die ros2_control bei jedem Tick (50 Hz)
aufruft.

**`write()`:**
```cpp
return_type write(...) {
    std::array<int16_t, NUM_SERVOS> pulses;
    for (size_t i = 0; i < NUM_SERVOS; ++i) {
        double rad = hw_command_positions_[i];
        if (std::isnan(rad)) {
            RCLCPP_WARN_ONCE("NaN command for joint %s, using last good value",
                             info_.joints[i].name.c_str());
            // Behalten last_command_pulse_us_[i]
            pulses[i] = last_command_pulse_us_[i];
        } else {
            double p = calibration_.radians_to_pulse_us(i, rad);
            pulses[i] = static_cast<int16_t>(std::round(p));
            last_command_pulse_us_[i] = pulses[i];
        }
    }
    if (!loopback_mode_) {
        auto frame = encode_set_targets(seq_++, pulses);
        try {
            serial_port_.write_all(frame.data(), frame.size());
        } catch (...) {
            // Disconnect → reconnect-state setzen, kommt in D.7
            return return_type::ERROR;
        }
    }
    return return_type::OK;
}
```

**`read()`:**
```cpp
return_type read(...) {
    // Echo-State: spiegele last_command_pulse_us_ zurück
    for (size_t i = 0; i < NUM_SERVOS; ++i) {
        hw_state_positions_[i] = calibration_.pulse_us_to_radians(
            i, last_command_pulse_us_[i]);
    }
    // Drain ERROR_REPORTs vom Reader-Thread
    if (reader_) {
        for (auto & er : reader_->drain_error_queue()) {
            RCLCPP_ERROR(get_logger(),
                "Servo2040 reported error_code=0x%02X servo_idx=%u aux=%d",
                er.error_code, er.servo_idx, er.aux);
        }
    }
    return return_type::OK;
}
```

**Done-Kriterium D.6:**
- Loopback-Test: in einer Schleife `write()` → `read()` → verifizieren
  dass `hw_state_positions_[i] == hw_command_positions_[i]` modulo
  Pulse-Rundungs-Toleranz (~1.6e-3 rad bei 1-µs-Rundung)
- NaN-Test: `hw_command_positions_[5] = NaN`, write() → warnt + behält
  letzten Wert, read() spiegelt den
- ERROR_REPORT-Test (mit gemocktem Reader): drain liefert Reports →
  `RCLCPP_ERROR` wird aufgerufen mit korrekten Feldern

### D.7 — USB-Reconnect-Logik

**Was:** Wenn der USB-Stecker während Betrieb gezogen wird, müssen
wir das erkennen und versuchen wieder zu connecten.

**Erkennung:**
- `write_all()` failt mit `errno == EIO` oder `ENXIO` oder `ENODEV`
- `read_some()` im Reader-Thread failt analog

**Reaktion (im Reader-Thread, weil der's zuerst sieht):**
1. SerialPort schließen, `is_connected_` Atomic auf false
2. Backoff-Schleife: alle 100, 200, 500, 1000, 2000, 5000, 5000, …
   ms versuchen `serial_port_.open()`
3. Bei Erfolg: `is_connected_` auf true, Reader-Loop wieder normal
4. `write()` im Hauptthread prüft `is_connected_` vor jedem
   `write_all()`. Wenn `false` → `return_type::ERROR` zurück, dann
   gerät ros2_control der Controller in `inactive`-State.

**Done-Kriterium D.7:**
- Manueller Test mit echter HW (kommt erst in Stufe H): Kabel ziehen
  → `RCLCPP_ERROR`-Log + Controller-State wechselt zu inactive →
  Kabel wieder rein → Reader connectet automatisch wieder
- gtest mit PTY-close-Simulation: kann die Backoff-Logik testen, aber
  das vollständige USB-Disconnect-Verhalten ist nur am echten Gerät
  prüfbar

### D.8 — ERROR_REPORT-Routing mit Logging-Detail

**Was:** Die ERROR_REPORT-Drainage aus D.6 verfeinern — pro Error-Code
einen aussagekräftigen Log-Output. Das ist der Punkt wo der User in der
Konsole sieht **was** passiert ist (nicht nur „error_code=0x40").

**Übersetzungs-Tabelle:**
| `error_code` | Log-Message |
|---|---|
| `0x01 FRAME_CRC` | „Firmware reported CRC error" |
| `0x02 FRAME_MALFORMED` | „Firmware reported malformed frame (expected LEN=%d)" |
| `0x03 UNKNOWN_OPCODE` | „Firmware reported unknown opcode" |
| `0x04 PAYLOAD_LEN` | „Firmware reported payload length mismatch (expected %d)" |
| `0x10 PULSE_OUT_OF_RANGE` | „Pulse out of range for servo %u, clamped to %d µs" |
| `0x20 SERVO_OVERCURRENT` | „Servo %u overcurrent at %d mA" |
| `0x21 TOTAL_OVERCURRENT` | „Total overcurrent: %d mA, all servos disabled" |
| `0x30 UNDERVOLTAGE` | „Undervoltage at %d mV (servo_idx=0xFF=warn / 0x00=trip)" |
| `0x40 WATCHDOG_TRIPPED` | „Watchdog tripped, all servos disabled — send RESET to recover" |

**Done-Kriterium D.8:**
- Pro Error-Code ein gtest-Case der den passenden Log-Output verifiziert
  (mit `RCLCPP_*_TEST` o.ä.)

---

## Reihenfolge und Abhängigkeiten

```
D.1 (SerialPort)
  └─→ D.2 (Reader-Thread)         braucht SerialPort
       └─→ D.4 (on_configure)     braucht beide
            └─→ D.5 (on_activate) braucht D.4
                 └─→ D.6 (read/write)  braucht D.5
                      └─→ D.7 (Reconnect) braucht D.6
                           └─→ D.8 (Logging-Detail) verfeinert D.6

D.3 (on_init)                     parallel zu D.1–D.7 möglich,
                                  aber sinnvoll vor D.4 weil on_init
                                  vor on_configure läuft
```

Pragmatisch in der Reihenfolge: **D.1 → D.2 → D.3 → D.4 → D.5 → D.6 → D.7 → D.8**.

Bei jeder Sub-Stage:
1. Code + Tests + lokal grün
2. Sub-Stage-Test-Anleitung (`phase_9_stage_d_<x>_test_commands.md`) schreiben
3. User fährt Tests nach
4. Sub-Stage-Bullets in `phase_9_progress.md` abhaken
5. README-Abschnitt zu der Sub-Stage erweitern (falls Konzept-Erklärung wert)
6. Erst dann nächste Sub-Stage

---

## Test-Strategie pro Sub-Stage

| Sub | Test-Form | CI-fähig? |
|---|---|---|
| D.1 | gtest mit `openpty(3)` Master/Slave-Pair, alle 256 Bytes round-trippen | ✓ |
| D.2 | gtest mit pty, gültige + ungültige Frames durchschicken | ✓ |
| D.3 | gtest mit manuell gebauter `HardwareInfo`-Struktur | ✓ |
| D.4 | gtest in Loopback-Mode (kein Port-Open); separat pty-Test für echten Pfad | ✓ |
| D.5 | gtest in Loopback (verifiziert seq++); pty-Test misst Timing | ✓ |
| D.6 | gtest in Loopback: write→read Roundtrip, NaN-Handling | ✓ |
| D.7 | gtest mit pty-close für Backoff; **echter Disconnect-Test in Stufe H** | partial |
| D.8 | gtest pro Error-Code mit `EXPECT_THAT`-Pattern für Log-Output | ✓ |

→ Stufe D ist bis auf den USB-Reconnect-Edge-Case (D.7 vollständig)
**komplett in CI testbar**, ohne dass Hardware angeschlossen ist.

---

## Was Stufe D explizit **nicht** macht

- **Kein** `gz_ros2_control`/sim-Pfad — das ist Stufe F (URDF-Switch)
- **Kein** `real.launch.py` — Stufe G
- **Kein** Strom-/Spannungs-Monitoring als ROS-Topic — späterer Diagnose-Pfad
- **Kein** automatisches RESET nach WATCHDOG_TRIPPED — User entscheidet
  (Plugin loggt, geht in ERROR-State, User schickt RESET über ein
  zukünftiges Tool oder restartet den Stack)
- **Kein** SEQ-Wraparound-Handling — Modulo-256 reicht, Firmware ist
  state-less bei SEQ
- **Kein** Performance-Tuning — bei 50 Hz × 18 Servos sind wir bei
  ~7 kB/s, USB-CDC schafft 125 kB/s, Headroom 17×

---

## Was zu User-Bestätigung ansteht

Bevor wir mit D.1 starten möchte ich Bestätigung zu:

1. **Sub-Staging D.1–D.8** wie hier aufgeteilt — passt das, oder
   anders schneiden?
2. **`SerialPort`-Klasse mit POSIX-FD** statt z.B. boost::asio — ist OK?
3. **`std::thread` statt boost::asio/coroutine** — ist OK?
4. **`std::optional<StatePayload>` als State-Cache, Mutex-geschützt** —
   ist OK, oder lieber lockfree-Atomic?
5. **NaN-Handling: behalte last good value + WARN_ONCE** — passt, oder
   sollte das Plugin in ERROR-State gehen?
6. **Watchdog-Recovery manuell** (User schickt RESET) — passt, oder
   sollte das Plugin nach N Sekunden automatisch RESET versuchen?

Wenn alle Punkte „passt" sind, ist Default:
- D.1–D.8 wie oben
- POSIX-FD, `std::thread`, `std::optional + mutex`
- NaN → WARN_ONCE + behalten
- Watchdog-Recovery manuell

Dann fange ich mit **D.1** an.
