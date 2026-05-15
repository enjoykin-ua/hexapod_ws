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

**Concurrency-Schutz (Punkt 2 aus Review):** Im Reconnect-Pfad
(siehe D.7) ruft der Reader-Thread `close()` und `open()` auf, während
der Hauptthread möglicherweise mitten in `write_all()` ist. Ein
`std::shared_mutex` in `SerialPort` schützt vor diesem Race:
- `write_all()` und `read_some()` nehmen `shared_lock` (parallel OK,
  wir haben nur je einen Schreiber/Leser, der Lock-Typ ist
  Reconnect-vs-IO-Schutz, nicht IO-vs-IO)
- `close()` + `open()` im Reconnect-Pfad nehmen `unique_lock` —
  blockiert bis kein I/O läuft

**Write-Timeout (Punkt 5):** `write()` auf TTY-FD blockiert per Default
bis Buffer frei wird. Wenn die USB-CDC-FIFO voll ist (z.B. Firmware
hängt), würde das den controller_manager-Tick einfrieren. Daher:
FD mit `O_NONBLOCK` öffnen, in `write_all()` `poll(POLLOUT)` mit
Timeout (z.B. 50 ms = ein voller Tick bei 50 Hz) verwenden. Bei
Timeout → `throw std::system_error` mit klarer Message.

**API-Skizze:**
```cpp
class SerialPort {
public:
    void open(const std::string & path);              // wirft bei Fehler (klare Message für EACCES, ENOENT)
    void close() noexcept;
    bool is_open() const noexcept;
    void write_all(const uint8_t * data, size_t len); // poll+timeout, wirft bei Disconnect
    ssize_t read_some(uint8_t * buf, size_t max_len); // poll+VTIME-Timeout
    ~SerialPort();                                    // schließt FD

    // Für die Reconnect-Logik in D.7 (exklusiver Lock-Aufruf):
    std::unique_lock<std::shared_mutex> exclusive_lock();

private:
    int fd_{-1};
    mutable std::shared_mutex mtx_;
};
```

Termios-Setup: `cfmakeraw`, `VMIN=0`, `VTIME=10` (= 1 s Timeout pro
read-Aufruf), Baudrate egal (USB-CDC ignoriert). FD geöffnet mit
`O_RDWR | O_NOCTTY | O_NONBLOCK`.

**Done-Kriterium D.1:**
- `SerialPort` baut, leakt keinen FD bei Exception
- Test mit Linux-PTY-Pair (`openpty(3)`): Schreiben in den Master, Lesen
  vom Slave funktioniert binär-sauber (alle 256 Byte-Werte überleben)
- **`cfmakeraw`-spezifischer Test (Punkt 9):** Schicke `0x0D` und
  `0x0A` einzeln und gemischt — beide müssen byte-exakt überleben,
  KEIN automatisches CR/LF-Mapping. Ohne `cfmakeraw` würde der Test
  failen weil ICRNL aktiv wäre.
- `read_some` mit VTIME-Timeout liefert 0 zurück wenn nichts kommt
- `write_all` mit blockiertem Reader auf der Gegenseite (Buffer voll)
  wirft nach 50 ms Timeout — verifiziert per pty wo der Slave nichts
  liest
- Permissions-Test: `open()` auf einen Path ohne Rechte (`/dev/null` mit
  chmod 000 — oder einfach nicht-existenter Path) wirft mit Message
  die `EACCES`/`ENOENT` klar macht

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
try {
    while (!stop_requested_) {
        bytes_read = port.read_some(tmp_buf, …);
        if (bytes_read < 0 && errno indicates disconnect)
            → trigger reconnect (siehe D.7), continue (Reconnect-Loop läuft
              im selben Thread; nach Erfolg geht's normal weiter)
        for byte in tmp_buf[:bytes_read]:
            if byte == 0x00:
                frame = decode_frame(buffer);
                if (frame) dispatch(frame);
                buffer.clear();
            else:
                buffer.push_back(byte);
    }
} catch (const std::exception & e) {
    RCLCPP_FATAL("Reader thread died with exception: %s", e.what());
    // Setze einen Flag, der read() im Hauptthread veranlasst, return_type::ERROR
    // zurückzugeben — Plugin geht in inactive, User muss restarten.
    reader_died_ = true;
}
```

**Exception-Sicherheit (Punkt 4 aus Review):** Die ganze Main-Loop ist
in `try/catch` eingebettet. Ohne das würde z.B. ein `std::bad_alloc`
aus `buffer.push_back` den Thread mit `std::terminate` abbrechen — was
nach C++-Spec den ganzen Prozess killt. Das `reader_died_`-Flag wird
in `read()` geprüft und signalisiert den controller_manager.

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

**Konzeptuell:** `on_init` ist der Lifecycle-Hook den der
`controller_manager` aufruft, **sobald das Plugin geladen wird** (beim
Stack-Start). Wir bekommen die geparste URDF in der Hand und bereiten
das Plugin vor: wir lernen welche 18 Joints es zu steuern gibt, mit
welchen Limits, an welchem Servo-Pin jeder hängt, und wo die
Servo-Kalibrierung herkommt.

Das ist der Punkt der **drei Konfigurations-Quellen** miteinander
verheiratet — siehe „Konfigurations-Quellen" in der Plugin-README.

**Konkret:**

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
7. **Joint→Output-Index-Tabelle aufbauen (Punkt 1 aus Review):**
   ```cpp
   joint_to_output_idx_.resize(info_.joints.size());
   for (size_t i = 0; i < info_.joints.size(); ++i) {
       joint_to_output_idx_[i] = calibration_.output_idx_for_joint(
           info_.joints[i].name);  // wirft wenn Joint unbekannt
   }
   ```
8. State-/Command-Vektoren auf `info_.joints.size()` allokieren —
   indiziert nach URDF-Reihenfolge `i`
9. `last_command_pulse_us_[18]` auf `pulse_zero` initialisieren —
   indiziert nach **Servo-Pin-Index** `output_idx`, nicht nach `i`

**Wichtig: zwei verschiedene Indizes (Punkt 1):** Die URDF kann die
18 Joints in beliebiger Reihenfolge im `<ros2_control>`-Block listen.
ros2_control nimmt diese Reihenfolge als Position-Interface-Reihenfolge,
also ist `hw_command_positions_[i]` indiziert nach **URDF-Index** `i`.
Aber `last_command_pulse_us_[output_idx]` und `encode_set_targets`
arbeiten mit dem **Servo-Pin-Index** (= Position 0..17 im
`servo2040_output_to_joint`-YAML). Die Übersetzung ist
`joint_to_output_idx_[i] = output_idx` aus `Calibration::output_idx_for_joint`.

Beispiel (denkbar wenn jemand die URDF kreativ sortiert):
```
info_.joints[0].name = "leg_3_femur_joint"    → output_idx = 7
info_.joints[1].name = "leg_1_coxa_joint"     → output_idx = 0
...
```
`hw_command_positions_[0]` ist dann der Sollwert für `leg_3_femur_joint`,
und der gehört in `last_command_pulse_us_[7]` → entspricht `servo2040.pin 7`.

**Done-Kriterium D.3:**
- Test mit synthetischer `HardwareInfo` (18 Joints, alle 4 Parameter
  gesetzt): `on_init` returns SUCCESS, alle internen Strukturen befüllt
- Test mit fehlenden Joints (17 oder 19) → ERROR
- Test mit ungültigem `calibration_file`-Pfad → ERROR
- Test mit ungültigem `loopback_mode`-String → ERROR
- **Test mit permutierter Joint-Reihenfolge im HardwareInfo:**
  `joint_to_output_idx_[i]` zeigt korrekt auf den jeweiligen Servo-Pin
  (nicht einfach `[0,1,2,…,17]`)
- Test mit URDF-Joint dessen Name nicht im YAML steht → ERROR aus
  `output_idx_for_joint`

### Was passiert bei Geometrie-Änderungen? (Wichtig für spätere Wartung)

Wenn sich am Roboter etwas ändert — Beinlänge, Körpermaße, Coxa-Winkel,
Joint-Endanschläge — muss man nicht in `on_init` reinschreiben. Die
URDF ist die einzige Quelle für die Geometrie; on_init liest sie immer
neu beim Plugin-Load. **Die Servo-Kalibrierung
(`servo_mapping.yaml`) bleibt davon unberührt**, weil im Direct-Drive-
Setup (Servo-Welle = Joint-Achse) der Servo dieselbe Anzahl Radiant für
dieselbe Pulsbreite dreht — egal wie lang das Bein ist.

| Du änderst… | Was du anfasst | D.3 picked es automatisch auf? |
|---|---|---|
| Femur 1 cm länger | URDF (`femur_length`) | ✅ — neue Limits aus URDF, Calibration unangetastet |
| Körpermaße ändern sich | URDF (`body_width` etc.) | ✅ — D.3 liest die Werte beim nächsten Start |
| Coxa-Mount-Winkel ändert sich | URDF (`leg_<n>_yaw`-Macro) | ✅ |
| Mechanischer Joint-Endanschlag ändert sich (z.B. Bein stößt früher an Chassis) | URDF `<limit lower upper>` | ✅ — D.3 reicht neue Limits an Calibration weiter |
| **Servo getauscht** (anderes Modell, andere µs/rad-Steigung) | `servo_mapping.yaml` (`pulse_min/zero/max` neu — Phase-10-Kalibrierungstool oder manuell) | ⚠️ User-Aktion nötig |
| **Servo um 90° gedreht montiert** (Pulse-Mitte verschoben) | `servo_mapping.yaml` (`pulse_zero` neu, ggf. `direction` Flip) | ⚠️ User-Aktion nötig |
| Anderer USB-Port (`ttyACM0` → `ttyACM1`) | `hexapod.ros2_control.xacro` (`<param name="serial_port">`) | ⚠️ User-Aktion nötig |

→ Die häufigsten Iterationen am Roboter (Bein-Geometrie, Gewichte,
Joint-Range bei Re-Konstruktion) erfordern **null** Anpassung an D.3 —
einfach URDF aktualisieren, `colcon build` der Description, Plugin
restarten.

→ YAML anpassen nur bei tatsächlichen Eingriffen am Servo selbst
(Tausch / Re-Montage / mechanischer Servo-Anschlag wandert).

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

**Was:** Im `on_activate`-Hook schickt der Host eine Boot-Sequenz mit
drei Phasen:

1. **`RESET` voran (Punkt 6 aus Review).** Setzt den Firmware-State
   zurück falls vorher etwas im WATCHDOG_TRIPPED-Zustand stehen geblieben
   ist (kann passieren wenn das Plugin ohne sauberen `on_deactivate`
   weggebrochen ist, z.B. SIGKILL oder Crash). Ohne RESET würden alle
   nachfolgenden `ENABLE_SERVO` mit NACK beantwortet.

2. **18× `ENABLE_SERVO` mit 50 ms Host-Stagger** (PROTOCOL.md §5,
   Phase-7 Design-Entscheidung D.1). Total ~900 ms. Das hält außerdem
   den Watchdog warm (jeder Frame zählt als „valider Frame" und
   resettet den 200 ms Timer firmware-seitig).

3. **`SET_TARGETS` mit allen `pulse_zero`-Werten am Ende
   (Punkt 3 aus Review).** Setzt den Roboter in eine definierte
   Neutralpose UND hält den Watchdog warm für die Zeit zwischen
   `on_activate`-Ende und dem ersten `controller_manager`-Tick. Ohne
   diesen Frame könnte der Watchdog nach 200 ms tripen wenn der erste
   `write()`-Aufruf zu spät kommt.

```cpp
hardware_interface::CallbackReturn on_activate(...) {
    if (!loopback_mode_) {
        // 1) Reset firmware state (clears WATCHDOG_TRIPPED if needed).
        auto reset_frame = encode_reset(seq_++);
        serial_port_.write_all(reset_frame.data(), reset_frame.size());
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    // 2) Per-servo enable with 50 ms host-side stagger.
    const auto stagger = loopback_mode_
        ? std::chrono::milliseconds(0)        // skip in loopback for fast tests
        : std::chrono::milliseconds(50);
    for (uint8_t i = 0; i < NUM_SERVOS; ++i) {
        auto frame = encode_enable_servo(seq_++, i, /*enable=*/true);
        if (!loopback_mode_) serial_port_.write_all(frame.data(), frame.size());
        std::this_thread::sleep_for(stagger);
    }

    // 3) Send neutral SET_TARGETS to:
    //    - keep the firmware watchdog warm until the first write() tick
    //    - put the robot in a defined initial pose (all pulse_zero = ~1500 µs)
    std::array<int16_t, NUM_SERVOS> neutral_pulses;
    for (size_t k = 0; k < NUM_SERVOS; ++k) {
        neutral_pulses[k] = calibration_.at(k).pulse_zero;
        last_command_pulse_us_[k] = neutral_pulses[k];
    }
    if (!loopback_mode_) {
        auto targets = encode_set_targets(seq_++, neutral_pulses);
        serial_port_.write_all(targets.data(), targets.size());
    }
    return CallbackReturn::SUCCESS;
}
```

`on_deactivate` macht das Spiegelbild: 18× `ENABLE_SERVO(idx, false)`,
ohne Stagger (Disable ist nicht Inrush-kritisch, alle Servos
spannungsfrei zu schalten kann simultan).

**Loopback-Stagger übersprungen:** Im Loopback macht der 50 ms-Schlaf
keinen Sinn (keine echte Servo-Inrush-Mitigation nötig), und 900 ms
Activate-Zeit machen CI-Tests langsam. In Loopback wird der Stagger zu
0 — siehe Pseudocode.

**Done-Kriterium D.5:**
- Loopback-Test: `on_activate` → SUCCESS in **< 100 ms** (kein Stagger),
  `seq_` ist um 20 inkrementiert (1 RESET + 18 ENABLE + 1 SET_TARGETS)
- PTY-Test mit Mock-Firmware: Reader auf der Master-Seite sieht
  in Reihenfolge: 1× RESET, 18× ENABLE_SERVO mit ~50 ms Abstand,
  1× SET_TARGETS mit allen Pulses auf pulse_zero
- PTY-Test prüft auch Timing: 900 ms ± 100 ms gesamt mit echtem Stagger
- `last_command_pulse_us_` ist nach `on_activate` auf alle `pulse_zero`
  gesetzt (Initial-State definiert)

### D.6 — `read()` / `write()` mit Echo-State + Pulse-Konversion

**Was:** Die zwei Methoden die ros2_control bei jedem Tick (50 Hz)
aufruft.

**`write()`:** (mit Joint-Index-Mapping aus D.3 und Pulse-Overflow-Clamp)
```cpp
return_type write(...) {
    std::array<int16_t, NUM_SERVOS> pulses;
    pulses.fill(0);  // wird gleich überschrieben für alle 18 Slots

    for (size_t i = 0; i < info_.joints.size(); ++i) {
        const int output_idx = joint_to_output_idx_[i];   // urdf-i → servo-pin
        const double rad = hw_command_positions_[i];

        if (std::isnan(rad)) {
            RCLCPP_WARN_THROTTLE(get_logger(), *clock_, 5000,
                "NaN command for joint %s, using last good value",
                info_.joints[i].name.c_str());
            pulses[output_idx] = last_command_pulse_us_[output_idx];
            continue;
        }

        const double p = calibration_.radians_to_pulse_us(output_idx, rad);

        // Pulse-Overflow-Schutz (Punkt 7 aus Review). Bei extremen
        // rad-Werten könnte p außerhalb int16-Range liegen — vorher
        // clampen, sonst ist der Cast UB. Die Firmware clampt nochmal
        // gegen pulse_min/pulse_max, das ist Verteidigung in der Tiefe.
        const double clamped = std::clamp(
            p, static_cast<double>(INT16_MIN), static_cast<double>(INT16_MAX));
        pulses[output_idx] = static_cast<int16_t>(std::round(clamped));
        last_command_pulse_us_[output_idx] = pulses[output_idx];
    }

    if (!loopback_mode_) {
        auto frame = encode_set_targets(seq_++, pulses);
        try {
            serial_port_.write_all(frame.data(), frame.size());
        } catch (const std::exception & e) {
            RCLCPP_ERROR_THROTTLE(get_logger(), *clock_, 1000,
                "SerialPort write failed (disconnect?): %s", e.what());
            return return_type::ERROR;  // controller_manager bringt Plugin in inactive
        }
    }
    return return_type::OK;
}
```

**`read()`:** (mit Joint-Index-Mapping)
```cpp
return_type read(...) {
    // Echo-State: spiegele last_command_pulse_us_ zurück, indiziert nach
    // URDF-Joint-Reihenfolge.
    for (size_t i = 0; i < info_.joints.size(); ++i) {
        const int output_idx = joint_to_output_idx_[i];
        hw_state_positions_[i] = calibration_.pulse_us_to_radians(
            output_idx, last_command_pulse_us_[output_idx]);
    }

    // Drain ERROR_REPORTs vom Reader-Thread (formatierte Logs in D.8).
    if (reader_) {
        for (auto & er : reader_->drain_error_queue()) {
            log_error_report(er);  // Übersetzung pro Error-Code, siehe D.8
        }
        if (reader_->died()) {
            RCLCPP_ERROR_ONCE(get_logger(), "Reader thread died — see earlier FATAL log");
            return return_type::ERROR;
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
- Permutierter Joint-Test: URDF-Reihenfolge `[3,1,0,…]`, `hw_command_positions_[0] = +0.5`
  geht an Servo-Pin 7 (= `output_idx_for_joint("leg_3_femur_joint")`),
  nicht an Pin 0
- Pulse-Overflow-Test: `hw_command_positions_[i] = 100.0` (extrem) →
  `last_command_pulse_us_[output_idx]` ist auf `INT16_MAX` geclamped,
  kein UB, kein Crash
- ERROR_REPORT-Test (mit gemocktem Reader): drain liefert Reports →
  formatierter Log-Output (Detail in D.8)

### D.7 — USB-Reconnect-Logik

**Was:** Wenn der USB-Stecker während Betrieb gezogen wird, müssen
wir das erkennen und versuchen wieder zu connecten.

**Erkennung:**
- `write_all()` failt mit `errno == EIO` oder `ENXIO` oder `ENODEV`
- `read_some()` im Reader-Thread failt analog

**Reaktion (im Reader-Thread, weil der's zuerst sieht):**
1. Reader nimmt **exclusive lock** auf `SerialPort` (siehe D.1
   `shared_mutex`). Damit blockiert jeder gleichzeitige `write_all`-Aufruf
   im Hauptthread.
2. SerialPort `close()`, `is_connected_` Atomic auf false
3. Backoff-Schleife: 100, 200, 500, 1 000, 2 000, 5 000, 5 000, … ms
   versuchen `serial_port_.open()`
4. Bei Erfolg: `is_connected_` auf true, exclusive lock freigeben,
   Reader-Loop läuft wieder normal
5. Hauptthread `write()` sieht `is_connected_ == false` (oder bekommt
   eine Exception aus `write_all` weil Port während des Backoff
   geschlossen war) → returnst `return_type::ERROR` → ros2_control bringt
   Plugin in inactive-State.

**Race-Schutz (Punkt 2 aus Review):** Der `shared_mutex` in `SerialPort`
verhindert das TOCTOU-Pattern „Hauptthread checkt is_connected_, ist
true, Reader schließt den FD, Hauptthread schreibt auf gerade
geschlossenen FD". Reader nimmt den unique-Lock für die ganze
`close+open`-Phase. Hauptthread, der gerade in `write_all` ist und den
shared-lock hält, blockiert den Reader-Lock-Acquire bis er fertig ist —
und danach blockiert er selber, weil der Reader jetzt den unique-Lock
hat. Sauber serialisiert.

**Recovery-Workflow für den User (Punkt 8 aus Review):**
Nach erfolgreichem Reconnect ist das Plugin **immer noch in
`inactive`-State** — der Reader läuft zwar wieder, aber ros2_control hat
den Controller deaktiviert weil `write()` mal ERROR returned hat.
Manueller User-Schritt nötig:

```bash
# Status prüfen:
ros2 control list_controllers
# alle Leg-Controller stehen jetzt als "inactive"

# Re-aktivieren:
ros2 control switch_controllers --activate \
    joint_state_broadcaster leg_1_controller leg_2_controller \
    leg_3_controller leg_4_controller leg_5_controller leg_6_controller
```

Das ist bewusst nicht automatisch, weil nach einem Disconnect der
Roboter mechanisch in undefinierter Pose sein kann (Servos gehen
spannungsfrei, Beine sacken durch). Der User soll explizit bestätigen
„OK, ich habe geprüft, kann wieder fahren".

Wird in der Plugin-README (Stufe I) als Recovery-Procedure dokumentiert.

**Done-Kriterium D.7:**
- Manueller Test mit echter HW (kommt erst in Stufe H): Kabel ziehen
  → `RCLCPP_ERROR`-Log + Controller-State wechselt zu inactive →
  Kabel wieder rein → Reader connectet automatisch wieder →
  manuelles `switch_controllers --activate` bringt das System zurück
- gtest mit PTY-close-Simulation: kann die Backoff-Logik testen
  (Reader sieht close, fängt an zu retryen, erste open() liefert
  schon ein Reopen-Pty zurück → Reader läuft weiter)
- gtest für shared_mutex-Verhalten: zwei Threads, einer schreibt
  permanent, anderer ruft `reconnect()` auf — kein Crash, write
  blockiert während Reconnect

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

## Sicherheits-Hinweis (Punkt 10 aus Review)

**Vor `switch_controllers --activate`: Roboter aufbocken.**

Das ist in `~/hexapod_ws/CLAUDE.md §9` schon dokumentiert, aber Stufe D
ist die erste Stufe wo Servos tatsächlich loslegen, sobald jemand den
Activate-Befehl absetzt. Konkret:

1. Das `on_activate` schickt eine `SET_TARGETS`-Sequenz mit Neutralpose
   (alle Pulse = `pulse_zero`, ≈ 1500 µs). Die Servos snappen sofort
   dorthin — d.h. wenn das Bein vorher in einer beliebigen Pose lag,
   springt es in einem Schlag in die mechanische Mitte.
2. Hexapod aufbocken (Beine in der Luft, kein Bodenkontakt) **bevor**
   irgendwer `switch_controllers --activate` aufruft.
3. Hardware-Kill-Switch (z.B. Power-Trennung am Bench-PSU) in
   Reichweite.
4. Erste Aktivierungen mit **reduzierter Geschwindigkeit** (Stufe F
   `controllers.real.yaml` mit ~30 % vel/accel-Limits gegenüber Sim).

Das gehört prominent in die Plugin-README — Anwender liest die zuerst.

---

## Implementation hints / minor Punkte aus dem Review

Kleinere Verbesserungen die in der Implementation berücksichtigt werden,
aber kein eigenes Sub-Stage rechtfertigen:

- **`/dev/ttyACM0` vs `ttyACM1` known-issue:** Bei mehreren USB-CDC-Geräten
  am Host kann sich der Path verschieben. Phase 9 nimmt das hin, der User
  setzt den `serial_port`-Parameter im URDF passend. Stable-Symlink via
  `udev`-Regel ist möglich aber Out-of-scope. → README erwähnt das im
  Troubleshooting-Abschnitt.
- **`WARN_THROTTLE` statt `WARN_ONCE` für persistent NaN:** Schon im D.6-
  Pseudocode (`RCLCPP_WARN_THROTTLE(*clock_, 5000, ...)`).
- **Loopback-Mode überspringt Activate-Stagger:** Schon im D.5-Pseudocode
  (`stagger = loopback_mode_ ? 0 : 50ms`).
- **Multiple Plugin-Instances:** Wenn jemand zwei `<ros2_control>`-Blöcke
  mit dem Plugin lädt, würden beide `/dev/ttyACM0` öffnen wollen — der
  zweite kriegt `EBUSY`. Wir fangen das im `on_configure` mit klarem
  Error-Log ab. Pragmatisch nicht supported; nicht erwartet bei
  Single-Hexapod-Setup.
- **Lifecycle-INFO-Logging:** Jeder `on_*`-Hook loggt am Anfang ein
  `RCLCPP_INFO("Configuring/Activating/...")` für Debug-Sichtbarkeit.
- **`on_error_processing`-Hook:** Default-Implementation in der
  Base-Klasse reicht (return SUCCESS). Wir override es nicht.
- **SEQ-Wraparound:** `seq_` ist `uint8_t`, Modulo-256 ist OK weil die
  Firmware stateless bei SEQ ist (echoiert nur in Antworten). Kein
  Spezial-Handling.

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
2. **`SerialPort`-Klasse mit POSIX-FD + `shared_mutex`** statt z.B.
   boost::asio — ist OK?
3. **`std::thread` statt boost::asio/coroutine** — ist OK?
4. **`std::optional<StatePayload>` als State-Cache, Mutex-geschützt** —
   ist OK, oder lieber lockfree-Atomic?
5. **NaN-Handling: behalte last good value + WARN_THROTTLE (5 s)** —
   passt, oder sollte das Plugin in ERROR-State gehen?
6. **Watchdog-Recovery manuell** (User schickt RESET) — passt, oder
   sollte das Plugin nach N Sekunden automatisch RESET versuchen?
7. **Reconnect-Recovery manuell** (User ruft `switch_controllers
   --activate` nach Kabel-rein) — passt, oder automatisch?

Wenn alle Punkte „passt" sind, ist Default:
- D.1–D.8 wie oben
- POSIX-FD mit `shared_mutex`, `std::thread`, `std::optional + mutex`
- NaN → WARN_THROTTLE + behalten
- Watchdog-Recovery manuell
- Reconnect-Recovery manuell

Dann fange ich mit **D.1** an.
