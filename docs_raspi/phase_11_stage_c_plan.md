# Phase 11 — Stufe C — Plan

> **Status:** Plan, in Vorbereitung der Implementation. **Pending User-Freigabe.**
>
> **Parent-Plan:** [`phase_11_param_gui.md`](phase_11_param_gui.md)
> Stufe C — `/servo_pulses` Diagnostic-Topic für rqt_plot-Visualisierung.
>
> **Vorbedingung:** Stage A + B abgeschlossen.

---

## Ziel

`hexapod_hardware`-Plugin um einen **opt-in Diagnostic-Topic** `/servo_pulses`
erweitern, der die aktuellen 18 Pulse-µs-Werte für rqt_plot-Visualisierung
publisht. **Default off** — nur bei Cal-Sessions / Debugging aktivieren.

**Was geht aktuell nicht:** Pulse-Werte gehen wire-only an die Servo2040.
Beim Live-Cal-Slider-Drag (Stage B) sieht man nur die `cal updated: ...`
Log-Zeile, aber nicht die resultierende Pulse-Kurve.

**Was Stage C liefert:**
- `std_msgs/Int32MultiArray`-Topic `/hexapodsystem/servo_pulses` mit
  18 int32 (= aktuelle `last_command_pulse_us_`-Werte aus dem write()-Hot-Path)
- Live-Param `publish_servo_pulses` (bool, default `false`) für ein/aus
- Publish-Rate = 50 Hz = controller_manager.update_rate (= jeder `write()`-Tick)

---

## Architektur-Entscheidungen (vorab)

### A. Topic-Type — `std_msgs/Int32MultiArray`

**Final:** Standard-Msg, kein Custom-Build nötig. Layout: 18 int32 in
`.data`-Array, Reihenfolge = Pin 0..17 (canonical aus `servo_mapping.yaml`).

**Verworfen:** Custom-Message `hexapod_msgs/PulseSnapshot` mit Timestamp +
per-Pin-Joint-Namen — sauberer, aber neue msg-Definition + CMakeLists +
Build-Dep. Phase-11-Mutter-Plan akzeptiert das Trade-off zugunsten Schlankheit.

### B. Topic-Rate — 50 Hz, gepublisht direkt in `write()`

**Final:** Im selben `write()`-Tick wie das wire-Frame. Damit ist das Topic
**bit-exakt** das was an den Servo geht — keine Async-Race zwischen
Topic-Publish und wire-Send.

**Verworfen:** Separater Timer (z.B. 10 Hz) — würde Daten verzerren wenn
zwischen Timer-Ticks gerade ein Param-Update kommt.

### C. Topic-Name — `/servo_pulses`

**Final:** Plain, lebt automatisch unter dem Plugin-Node-Namespace
`/hexapodsystem/servo_pulses`. Pluginlib-Standard, keine extra Convention.

### D. Default off + Live-Toggle (User-Wunsch B)

**Final:** Live-Param `publish_servo_pulses` (bool, default `false`).
Bei `true` → Plugin publisht 50 Hz; bei `false` → kein Publish.
Toggle via rqt_reconfigure-Checkbox (analog Direction-Bool-Params).

**Bonus-Defensive:** Plus Subscriber-Check `pub_->get_subscription_count() > 0`
— selbst wenn Param `true` ist aber niemand subscribed, kein Serialization-
Overhead. 1-Liner.

```cpp
// in write():
if (publish_pulses_enabled_.load() && pulses_pub_->get_subscription_count() > 0) {
  pulses_pub_->publish(msg);
}
```

**Konsequenz:** Zero-Cost wenn Param `false` oder kein Subscriber. Bei Cal-
Session: User toggled Param + öffnet `rqt_plot` → Pulse-Curve erscheint live.

---

## Logik-Skizze

### C.0 — Vorbereitung

Plan-Doku (diese Datei) + User-Freigabe. test_commands.md Skelett. Build-Status
grün (220/0/20 hexapod_hardware, 20/0/1 hexapod_gait, 18/0/0 hexapod_bringup).

### C.1 — Header + Imports erweitern (~10 min)

In [`hexapod_system.hpp`](../src/hexapod_hardware/include/hexapod_hardware/hexapod_system.hpp):

- `+ #include "std_msgs/msg/int32_multi_array.hpp"`
- `+ std::atomic<bool> publish_pulses_enabled_{false}`
- `+ rclcpp::Publisher<std_msgs::msg::Int32MultiArray>::SharedPtr pulses_pub_`

In [`CMakeLists.txt`](../src/hexapod_hardware/CMakeLists.txt) + [`package.xml`](../src/hexapod_hardware/package.xml):
- `+ <depend>std_msgs</depend>` (vermutlich schon transitively via hardware_interface, prüfen)
- `+ find_package(std_msgs REQUIRED)` (idem)
- `+ ament_target_dependencies(... std_msgs)`

### C.2 — Publisher + Param-Declaration (~20 min)

In `register_live_cal_params()` (oder neuer Helper `register_diagnostics()`):

```cpp
// Param declaration
rcl_interfaces::msg::ParameterDescriptor desc;
desc.type = rcl_interfaces::msg::ParameterType::PARAMETER_BOOL;
desc.description =
  "Publish current 18 pulse-µs values to /servo_pulses (default off — "
  "enable only for cal sessions / debugging; 4 KB/s overhead).";
node->declare_parameter<bool>("publish_servo_pulses", false, desc);

// Publisher (keep handle, lazy enable)
pulses_pub_ = node->create_publisher<std_msgs::msg::Int32MultiArray>(
  "~/servo_pulses", rclcpp::QoS(10));
```

Topic-Name `~/servo_pulses` → expanded zu `/hexapodsystem/servo_pulses`
(Plugin-Node-Namespace).

### C.3 — Param-Callback erweitern (~10 min)

In `on_param_change`: zusätzliches `if`-Branch für `publish_servo_pulses`:

```cpp
if (p.get_name() == "publish_servo_pulses") {
  publish_pulses_enabled_.store(p.as_bool());
  RCLCPP_INFO(plugin_logger(),
    "param updated: publish_servo_pulses = %s",
    p.as_bool() ? "true" : "false");
  continue;  // nicht Teil des PinParamSpec-Filterings
}
```

### C.4 — Publish-Pfad in `write()` (~5 min)

Am Ende von `write()` (nach erfolgreichem wire-Send):

```cpp
// Diagnostic-Topic publisht den frisch berechneten Pulse-Snapshot.
// Doppelt-bedingt: Param `publish_servo_pulses` ON + jemand subscribed.
if (publish_pulses_enabled_.load() &&
    pulses_pub_->get_subscription_count() > 0)
{
  std_msgs::msg::Int32MultiArray msg;
  msg.data.reserve(NUM_SERVOS);
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    msg.data.push_back(static_cast<int32_t>(last_command_pulse_us_[pin]));
  }
  pulses_pub_->publish(msg);
}
```

### C.5 — Tests (~30 min)

In `test_hexapod_system.cpp` (oder neue Datei `test_servo_pulses.cpp`):

- Test: Param `publish_servo_pulses` deklariert mit default `false`
- Test: Toggle auf `true` setzt `publish_pulses_enabled_`
- Test: Publisher existiert nach on_init
- Test: Topic-Type ist `std_msgs/Int32MultiArray`

Skip-Test wegen `get_node()`-null im Standalone-Mode — siehe Stage-B
Self-Review-Punkt 4. End-to-End via User-Smoke.

### C.6 — User-Smoke

`real.launch.py loopback_mode:=true` + rqt:
- Verify Param `publish_servo_pulses` (default `false`) sichtbar in rqt
- `rqt_plot /hexapodsystem/servo_pulses/data[15]` öffnen — leer (Param off)
- In rqt `publish_servo_pulses` auf `true` toggeln → rqt_plot zeigt Linie
- Slider `pin_15.pulse_zero` verschieben → Plot-Wert mitläuft
- Toggle zurück auf `false` → Publishing stoppt

### C.7 — README + Self-Review + Stage-D-Übergang

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| C-T1 | `colcon build --packages-select hexapod_hardware` | grün | Claude |
| C-T2 | `colcon test --packages-select hexapod_hardware` | bestehende 220/0/20 + Stage-C-Tests grün | Claude |
| C-T3 | Regression `hexapod_gait` + `hexapod_bringup` unverändert | 20/0/1 + 18/0/0 | Claude |
| C-T4 (User) | `ros2 param get /hexapodsystem publish_servo_pulses` → `false` (Default) | User |
| C-T5 (User) | `rqt_plot /hexapodsystem/servo_pulses/data[15]` öffnen, Param-Toggle in rqt → Plot startet | User |
| C-T6 (User) | Slider `pin_15.pulse_zero` verschieben → Plot-Wert mitläuft mit Cal-Math | User |
| C-T7 (User) | Toggle zurück auf `false` → Publishing stoppt (Plot bleibt stehen) | User |

---

## Progress-Checkliste

- [x] C.1 phase_11_stage_c_plan.md (Plan-Doku) finalisiert + User-Freigabe C-Q1..C-Q5 (2026-05-20)
- [ ] C.2 phase_11_stage_c_test_commands.md Skelett
- [ ] C.3 Header + Imports + Publisher-Member + Param-Declaration
- [ ] C.4 Param-Callback erweitert (`publish_servo_pulses` handling)
- [ ] C.5 Publish-Pfad in `write()` mit doppel-bedingung (Param + Subscriber)
- [ ] C.6 CMakeLists.txt + package.xml: `std_msgs`-Dep falls noch nicht da
- [ ] C.7 colcon build grün
- [ ] C.8 colcon test grün (neue Tests + Regression)
- [ ] C.9 README hexapod_hardware Phase-11-Stage-C-Block (Topic-Name, Toggle, Use-Cases)
- [ ] C.10 User-Smoke C-T4..C-T7
- [ ] C.11 Self-Review-Tabelle
- [ ] C.12 Stage-C-Notizen + Übergang Stage D

**Done-Kriterium C:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke C-T4..C-T7 bestätigt.

---

## Erwartete Stage-C-Dauer

- C.0 Plan-Doku (diese Datei): ~30 min Claude (erledigt)
- C.1-C.6 Implementation: ~1 h Claude
- C.7-C.8 Build + Tests: ~30 min
- C.9 README: ~15 min
- C.10 User-Smoke: ~15 min User
- C.11-C.12 Review + Übergang: ~15 min

**Schätzung:** ~2.5 h Claude + 15 min User = **~0.5 d Gesamt** (matched
Mutter-Plan).

---

## Offene Punkte für User-Review

| # | Frage | Empfehlung |
|---|---|---|
| **C-Q1** Topic-Type | **✅ A** Int32MultiArray (User-bestätigt) | (B) Custom-Msg |
| **C-Q2** Topic-Rate | **✅ A** 50 Hz in write() (User-bestätigt) | (B) niedriger Timer; (C) configurable |
| **C-Q3** Topic-Name | **✅ A** `/hexapodsystem/servo_pulses` (User-bestätigt) | (B) sub-namespace `/diagnostics/...` |
| **C-Q4** Toggle-Mechanismus | **✅ B** Live-Param `publish_servo_pulses` (User-bestätigt) + Bonus Subscriber-Check | (A) always-on (4 KB/s overhead); (C) nur Subscriber-Check (kein expliziter Toggle) |
| **C-Q5** Default-Wert | **✅ A** `false` (off-by-default, opt-in für Cal-Session, User-bestätigt 2026-05-20) | (B) `true` (always available) |

Alle C-Q1..C-Q5 durch User-Freigabe bestätigt.
