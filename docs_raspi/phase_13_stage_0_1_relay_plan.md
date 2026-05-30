# Phase 13 Stage 0.1 — FW RELAY_CONTROL + Fail-safe + Plugin Relay-Service

> **Übergeordnet:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §5/§6.
> **Test-Anleitung:** [`phase_13_stage_0_1_relay_test_commands.md`](phase_13_stage_0_1_relay_test_commands.md).
> **Status:** ⚪ offen, wartet auf Freigabe (2026-05-30).

**Ziel:** Das Plugin kann den Strom-Rail der Servos über einen Relay
(GP26) schalten, und die FW wirft den Relay bei jedem Fehler-Trip / RESET
fail-safe ab. Damit existiert nach 0.1 die **manuelle** Relay-Steuerung
(`/hexapod_relay_set`), die der Mech-Umbau in 0.2 nutzt. Die **automatische**
relay-gated `on_activate`-Sequenz kommt erst in 0.3.

**Vorbedingung (vom User zu bestätigen, nicht Teil dieser Stage):**
- Relay physisch an GP26/A0 verdrahtet, high-trigger, normally-open
  (laut Brainstorm §8/§10 bereits erledigt + getestet).
- ⚠️ Servo2040 "Separate USB & Ext Power"-Trace **gecuttet** (sonst
  backfeed 7.4 V → USB → Host beim Relay-On). Siehe
  [`test_relay_power_sequence.cpp`](../../pimoroni_servo_fix/src/test_relay_power_sequence.cpp) Header.

---

## 1. Logik-Skizze / Pseudocode

### 1.1 FW (`hexapod_servo_driver/src/main.cpp` + `config.hpp`)

**(a) Neuer Opcode** in `config.hpp namespace cmd` (System-Range 0x50-0x5F):
```cpp
constexpr uint8_t RELAY_CONTROL = 0x51;   // payload: 1 byte (1=on/HIGH, 0=off/LOW)
```
*Begründung:* RESET ist 0x50; Relay ist ein System-Kommando → 0x51 im selben
Range. 1-Byte-Payload analog ENABLE_SERVO-Stil.

**(b) Relay-Pin + State** (`main.cpp` Globals):
```cpp
constexpr uint RELAY_PIN = servo::servo2040::ADC0;   // GP26 = A0 header
bool relay_on = false;                               // mirror of GP26
```

**(c) Boot-Init** — als ALLERERSTES in `main()`, vor `servos.init()`
(Pattern aus `test_relay_power_sequence.cpp`):
```cpp
gpio_init(RELAY_PIN);
gpio_set_dir(RELAY_PIN, GPIO_OUT);
gpio_put(RELAY_PIN, 0);   // LOW = relay open = servos unpowered
relay_on = false;
```
*Begründung:* Floating-Input-Fenster < 1 ms; Servos kriegen beim Boot
garantiert keinen Strom.

**(d) Helper** `set_relay(bool on)`:
```cpp
void set_relay(bool on) {
    gpio_put(RELAY_PIN, on ? 1 : 0);
    relay_on = on;
}
```

**(e) Frame-Handler** `handle_relay_control(seq, payload, len)`:
```cpp
if (len != 1) { send_error(seq, err::PAYLOAD_LEN, 0, 0); return; }
set_relay(payload[0] != 0);
send_ack(seq, cmd::RELAY_CONTROL);
```
Dispatch-Case in `dispatch()` ergänzen (case cmd::RELAY_CONTROL).

**(f) Fail-safe-Off** — `set_relay(false)` einfügen in:
- `handle_reset()` — nach `disable_all`, vor/bei den State-Resets.
- `on_tick()` Watchdog-Trip-Block (nach disable-Schleife).
- `on_tick()` Overcurrent-Trip-Block.
- `on_tick()` Undervoltage-Crit-Trip-Block.

*Begründung:* jeder Zustand "alles aus / Fehler" soll garantiert
stromlos sein. Konsistent mit der disable_all-Logik, die dort schon steht.

**(g) Optional (empfohlen, klein):** Status-Bit `RELAY_ON` in
`namespace status` + in GET_STATE-Response setzen, damit der Relay-Zustand
ohne Oszi automatisiert prüfbar ist. Falls Bit-Budget knapp → deferred,
dann nur physische Verifikation (Klick/LED).

### 1.2 Plugin (`hexapod_hardware`)

**(a) Protocol** (`servo2040_protocol.hpp/.cpp`):
```cpp
constexpr uint8_t RELAY_CONTROL = 0x51;   // opcode namespace
std::vector<uint8_t> encode_relay_control(uint8_t seq, bool on);
// -> encode_frame(seq, opcode::RELAY_CONTROL, { on ? 1u : 0u });
```

**(b) Service** `/hexapod_relay_set` (`std_srvs::srv::SetBool`) in
`hexapod_system.cpp`, erstellt analog `safety_reset_service_`:
- Callback: `encode_relay_control(seq_++, req->data)` → über die bestehende
  Serial-Write-Pipeline senden (dieselbe wie `handle_safety_reset`).
- `loopback_mode_`: Frame nur erzeugen/zählen, nicht physisch senden
  (CI-tauglich).
- Response: `success=true`, `message="relay set to <on/off>"`.

**(c) `on_deactivate`** — Fail-safe: vor dem Servo-Disable
`encode_relay_control(seq_++, false)` senden.
*Begründung:* sauberer Stop = Strom aus. (Die `on_activate`-Relay-ON-Sequenz
ist 0.3 — nach 0.1 bleibt der Relay beim Activate noch LOW, Steuerung
ausschließlich manuell via Service.)

---

## 2. Tests-Liste mit Begründung

### 2.1 Unit-Tests (CI, `colcon test --packages-select hexapod_hardware`)

| Test | Prüft | Begründung |
|---|---|---|
| `EncodeRelayControlOn` / `…Off` | Frame-Bytes: opcode 0x51, len 1, payload {1}/{0}, CRC ok | Encoder-Korrektheit isoliert |
| `RelaySetServiceSendsFrame` (loopback) | Service-Call `data=true` → genau 1 RELAY_CONTROL-Frame mit payload 1 erzeugt; `data=false` → payload 0 | Service↔Encoder-Verdrahtung |
| `OnDeactivateSendsRelayOff` (loopback) | nach `on_deactivate` wurde ein RELAY_CONTROL(off)-Frame gesendet | Fail-safe-Pfad |

### 2.2 FW-Host-Tests (`hexapod_servo_driver/tools/test_servo2040.py`)

| Test | Prüft |
|---|---|
| RELAY_CONTROL → ACK | FW ACKt den neuen Opcode (statt UNKNOWN_OPCODE) |
| RELAY_CONTROL len≠1 → ERROR PAYLOAD_LEN | Payload-Validierung |
| (falls Status-Bit) GET_STATE zeigt RELAY_ON nach on / clear nach off | Relay-State-Spiegel |

### 2.3 Live (Test-Commands, interaktiv — User führt aus)

Siehe [`_test_commands.md`](phase_13_stage_0_1_relay_test_commands.md):
Relay klickt on/off via Service; Watchdog-Trip (`pkill`) droppt Relay;
RESET droppt Relay.

### 2.4 Bewusst NICHT getestet (Scope-out)

- **Servo-Hochfahr-Verhalten in 35°** — braucht Mech-Umbau (0.2/0.3).
- **Automatische on_activate-Relay-Sequenz** — ist 0.3.
- **Brown-out beim Relay-On** — User: PSU schafft das (Brainstorm §10.3).
- **Oszi/Logic-Analyzer am GP26** — HW-Limit, analog Memory
  `project_phase9_h_oscilloscope_pending` bei Bedarf nachholen.

---

## 3. Progress-Checkliste (Done-Vertrag → `phase_13_stage_0_progress.md`)

```
### Sub-Stage 0.1 — Relay-Frame + Fail-safe + Plugin-Service
- [ ] 0.1.1  FW: RELAY_CONTROL=0x51 in config.hpp cmd-namespace
- [ ] 0.1.2  FW: RELAY_PIN/relay_on Globals + GP26-Boot-LOW vor servos.init()
- [ ] 0.1.3  FW: set_relay() Helper + handle_relay_control() + dispatch-Case
- [ ] 0.1.4  FW: Fail-safe set_relay(false) in handle_reset + 3 Trip-Blöcke
- [ ] 0.1.5  FW: (optional) RELAY_ON Status-Bit in GET_STATE
- [ ] 0.1.6  FW: Build clean (cmake .. && make -j$(nproc))
- [ ] 0.1.7  FW: tools/test_servo2040.py RELAY_CONTROL-Tests grün
- [ ] 0.1.8  FW: vom User geflasht (picotool load + reboot)
- [ ] 0.1.9  Plugin: encode_relay_control + opcode in servo2040_protocol
- [ ] 0.1.10 Plugin: /hexapod_relay_set Service (SetBool)
- [ ] 0.1.11 Plugin: on_deactivate sendet RELAY_CONTROL(off)
- [ ] 0.1.12 Plugin: colcon build hexapod_hardware grün
- [ ] 0.1.13 Plugin: colcon test hexapod_hardware grün (neue + alte Tests)
- [ ] 0.1.14 Live: Relay klickt on/off via Service ✓
- [ ] 0.1.15 Live: Watchdog-Trip (pkill) droppt Relay ✓
- [ ] 0.1.16 Live: RESET-Frame droppt Relay ✓
- [ ] 0.1.17 Self-Review-Tabelle, Fixe erledigt
```

---

## 4. Offene Punkte für User-Review (vor Code-Beginn)

| # | Frage | Vorschlag |
|---|---|---|
| 4.1 | `RELAY_ON`-Status-Bit in GET_STATE einbauen (0.1.5) oder deferred? | **Einbauen** — macht Live-Test automatisierbar, ~3 Zeilen. Wenn Bit-Budget im `status_flags`-Byte voll ist (prüfen), deferred + nur physische Verifikation. |
| 4.2 | Service-Typ `std_srvs/SetBool` ok, oder eigener Typ mit Timeout/Ack-Feedback? | **SetBool** — minimal, konsistent mit `/hexapod_safety_reset` (Trigger). Ack-Feedback aus dem Frame ist optional, kann später. |
| 4.3 | `on_deactivate`-Relay-Off schon in 0.1 (Fail-safe) oder erst mit Sequenz in 0.3? | **0.1** — gehört thematisch zum Fail-safe und ist 2 Zeilen; 0.3 baut nur die Activate-Seite. |
| 4.4 | FW-Rollback: alte `.uf2` vor Flash sichern? | **Ja** — `cp Hexapod_servo_driver.uf2{,.pre-0.1}` (analog servo2040_fix §8). |
| 4.5 | Relay-Off bei Watchdog-Trip: sofort, oder erst nach disable_all? | **Nach** disable_all (PWM erst sauber aus, dann Strom weg) — minimiert Signal-Transienten am Servo im Abschalt-Moment. |
