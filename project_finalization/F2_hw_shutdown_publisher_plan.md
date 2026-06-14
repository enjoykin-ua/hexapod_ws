# Stage F2 — hexapod_hardware: Bit 7 → latched Bool `/hexapod/shutdown_request`

> Teil von [Block F](F_systemsteuerung_plan.md). Detail-Plan nach CLAUDE.md §4.
> Code: `~/hexapod_ws/src/hexapod_hardware` (C++ ros2_control SystemInterface).
> Voraussetzung: F1 (FW sendet `status_flags` Bit 7) 🟢.
> Test-Anleitung: [`F2_hw_shutdown_publisher_test_commands.md`](F2_hw_shutdown_publisher_test_commands.md).

---

## 1. Logik-Skizze / Pseudocode

**Ausgangslage (verifiziert):** Die FW sendet Bit 7 in jeder `STATE_RESPONSE`. Der
Reader dekodiert `status_flags` in `StatePayload` und hält sie in `latest_state()`
([`servo2040_reader.cpp:79`](../src/hexapod_hardware/src/servo2040_reader.cpp#L79)) —
**aber `latest_state()` wird heute nirgends konsumiert** (`read()` macht nur
Joint-Echo + Error-Queue-Drain). F2 schließt diese Lücke.

### 1.1 Mirror-Konstante (`servo2040_protocol.hpp`)
```cpp
namespace status_flag {
  ...
  constexpr uint8_t RELAY_ON          = 1u << 6;
  constexpr uint8_t SHUTDOWN_REQUEST  = 1u << 7;   // NEU — spiegelt FW config.hpp
}
```

### 1.2 Neue Member (`hexapod_system.hpp`)
```cpp
rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr shutdown_request_pub_{};
bool last_shutdown_request_{false};   // publish-on-change-Tracking
```

### 1.3 Publisher anlegen (`on_configure`, im `get_node()`-Block)
Bei den anderen Services (vor dem `loopback_mode_`-Early-Return, damit CI/Tests den
Topic auch im Loopback haben):
```cpp
shutdown_request_pub_ = node->create_publisher<std_msgs::msg::Bool>(
    "/hexapod/shutdown_request",
    rclcpp::QoS(1).transient_local());      // latched: späte Subscriber bekommen den letzten Stand
std_msgs::msg::Bool init; init.data = false;
shutdown_request_pub_->publish(init);       // definierter Startwert
last_shutdown_request_ = false;
```

### 1.3b GET_STATE-Poll in `write()` (KRITISCH — sonst kein Update)
**Befund bei Live-Test:** Der Plugin fordert **nie** `GET_STATE` an. Joint-Feedback
ist Echo-basiert, Trips kommen als **unsolicited ERROR_REPORT** — `STATE_RESPONSE`
(mit Bit 7) sendet die FW aber **nur auf Anfrage**. Ohne Poll bleibt
`latest_state()` ewig leer, der Topic hängt auf dem Init-`false`.
```cpp
// write(), non-loopback, nach SET_TARGETS — gedrosselt (~5 Hz bei 50 Hz update):
if (++get_state_poll_counter_ >= GET_STATE_POLL_EVERY /*10*/) {
    get_state_poll_counter_ = 0;
    auto gs = encode_get_state(seq_.fetch_add(1));
    serial_port_.write_all(gs.data(), gs.size());   // best-effort, Fehler nur WARN
}
```
Der Reader-Thread legt die `STATE_RESPONSE` async in `latest_state()`; das nächste
`read()` konsumiert sie. 3-s-FW-Halten versteckt die Sub-Sekunden-Latenz.

### 1.4 Konsum in `read()` (im bestehenden `if (!loopback_mode_)`-Block)
```cpp
if (auto st = reader_.latest_state()) {
    bool req = (st->status_flags & status_flag::SHUTDOWN_REQUEST) != 0;
    if (req != last_shutdown_request_) {              // publish-on-change
        std_msgs::msg::Bool m; m.data = req;
        shutdown_request_pub_->publish(m);
        last_shutdown_request_ = req;
    }
}
```

### Begründung pro Design-Entscheidung
- **Latched (`transient_local`, Tiefe 1):** der Supervisor (F4) startet evtl. später
  und muss trotzdem sofort den aktuellen Stand kennen. Kein Polling, kein Verpassen.
- **publish-on-change:** Topic bleibt ruhig (flippt nur bei echtem Request), kein
  50–100-Hz-Bool-Spam. Latched deckt späte Subscriber trotzdem ab.
- **Absoluter Topic-Name `/hexapod/shutdown_request`:** der Supervisor abonniert
  einen festen Namen, nicht node-relativ (`~/…`).
- **Publisher vor Loopback-Return + Initial-`false`:** Topic existiert auch in
  CI/Tests; definierter Startzustand statt „nie publiziert".
- **`latest_state()` endlich konsumiert:** schließt den toten Decode-Pfad (E4).

---

## 2. Tests-Liste mit Begründung

| ID | Test | Erwartung | Warum |
|---|---|---|---|
| F2-U1 | Unit (`test_servo2040_protocol.cpp`): `decode_state` mit gesetztem Bit 7 | `StatePayload.status_flags & SHUTDOWN_REQUEST` ≠ 0 | Decode-/Mask-Korrektheit ohne HW |
| F2-U2 | `colcon build --packages-select hexapod_hardware` | grün | — |
| F2-U3 | `colcon test --packages-select hexapod_hardware` (+ lint) | grün | Regression |
| F2-L1 | Live (Board + F1-FW): `ros2 topic echo /hexapod/shutdown_request` | `false`; Schalter ≥3 s offen → `true`; zu → `false` | echte Kette FW→HW→Topic |
| F2-L2 | Late-Join: `ros2 topic echo` **nach** gesetztem Request starten | bekommt sofort `true` (latched) | `transient_local` verifizieren |

**Bewusst NICHT getestet (deferred):**
- Supervisor-Konsum (Arm/Flanke/Retry) → **F4**.
- End-to-End hinsetzen+shutdown → **F5**.
- Loopback kann Bit 7 nicht treiben (keine echte FW) → die Mask-Logik deckt F2-U1 ab;
  die Kette deckt F2-L1 (Board nötig).

---

## 3. Progress-Checkliste (Done-Vertrag — 1:1 ins Progress-File)

```
- [ ] F2.1  servo2040_protocol.hpp: status_flag::SHUTDOWN_REQUEST (1u<<7) Mirror
- [ ] F2.2  hexapod_system.hpp: shutdown_request_pub_ + last_shutdown_request_ Member
- [ ] F2.3  on_configure: latched Publisher /hexapod/shutdown_request + Initial false
- [ ] F2.4  read(): latest_state() Bit 7 konsumieren, publish-on-change
- [ ] F2.5  Unit-Test F2-U1 (Bit-7-Decode) in test_servo2040_protocol.cpp
- [ ] F2.6  colcon build + test + lint grün (hexapod_hardware)
- [ ] F2.7  Live F2-L1/F2-L2 grün (Board + ros2 topic echo)
- [ ] F2.8  Self-Review-Tabelle (CLAUDE.md §4)
```

---

## 4. Offene Punkte für User-Review (vor Code-Beginn)

1. **Topic-Name:** `/hexapod/shutdown_request` (absolut). Passt, oder anderes Schema?
2. **QoS:** latched `transient_local`, Tiefe 1, reliable. Der Supervisor (F4) muss
   exakt matchen. Einverstanden?
3. **publish-on-change** statt jede read()-Tick. Vorschlag on-change (ruhiger Topic,
   latched deckt späte Subscriber). OK?
