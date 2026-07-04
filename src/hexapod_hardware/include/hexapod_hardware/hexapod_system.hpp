// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
#define HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_

#include <array>
#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rcl_interfaces/msg/set_parameters_result.hpp"
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/state.hpp"
#include "std_msgs/msg/int32_multi_array.hpp"
#include "std_msgs/msg/bool.hpp"
#include "std_srvs/srv/set_bool.hpp"
#include "std_srvs/srv/trigger.hpp"

#include "hexapod_hardware/calibration.hpp"
#include "hexapod_hardware/serial_port.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"
#include "hexapod_hardware/servo2040_reader.hpp"

namespace hexapod_hardware
{

class HexapodSystemHardware : public hardware_interface::SystemInterface
{
public:
  // Lifecycle hooks (stage D fills these in).
  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareComponentInterfaceParams & params) override;

  hardware_interface::CallbackReturn on_configure(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_cleanup(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & previous_state) override;

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;
  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

  hardware_interface::return_type write(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

  // ─── Stage 0.5 — Safety-Freeze Inspection + Recovery API ───────────────
  // Public API for diagnostics and tests. The freeze flag itself is set
  // implicitly from write() when an out-of-range pulse is detected;
  // there is no public setter — the only way to enter freeze is the OoR
  // detection (preserves the invariant "freeze only triggers when the
  // plugin actually sees a dangerous command").
  bool is_safety_frozen() const noexcept;

  // Clear the safety_freeze flag. Used by both the /hexapod_safety_reset
  // service callback AND tests. Returns true if a freeze was actually
  // cleared, false if the flag was already clear (idempotent).
  bool clear_safety_freeze() noexcept;

  // Stage 0.6: Set the safety_freeze flag (counterpart to clear).
  // Used by the /hexapod_safety_freeze service callback AND tests.
  // Returns true if the freeze was newly set, false if already set
  // (idempotent — no double-trigger spam).
  bool trigger_safety_freeze() noexcept;

private:
  // ─── Phase 13 Stage A — Initial-Pose-Preset-Loader ──────────────────────
  // Liest ``initial_poses_file_`` und fuellt ``initial_pulse_us_`` pro
  // Pin mit den Preset-Pulses. Reihenfolge:
  //   1. YAML-File lesen via yaml-cpp; bei Parse-Error oder fehlendem
  //      File: WARN + Fallback (alle Pins auf pulse_zero).
  //   2. Preset-Block ``poses[<initial_pose_name_>]`` lookuppen; bei
  //      unbekanntem Namen: WARN + Fallback.
  //   3. Pro URDF-Joint i:
  //      - Joint-Name parsen → segment-Typ (coxa/femur/tibia)
  //      - rad-Wert aus Preset lookuppen; bei fehlendem Segment: WARN
  //        + Pin auf pulse_zero
  //      - PWM via Calibration::radians_to_pulse_us berechnen
  //      - Pre-Validate: PWM ∈ [pulse_min, pulse_max]? Bei OoR: WARN +
  //        Pin auf pulse_zero (verhindert Stage-0.5-safety_freeze beim
  //        Aktivieren).
  //
  // Wird in on_init nach Cal-Load + joint_to_output_idx aufgerufen.
  // Best-Effort-Semantik: kein Throw, nur WARN-Logs. Pins die im
  // Preset oder via OoR ausfallen, kriegen pulse_zero (= sicherer
  // Fallback, da Cal-validate dort sicher passt).
  void load_initial_pose_preset();

  // ─── Phase 11 Stage B — Live-Cal-Params + Save-Service ──────────────────

  // Param-Spec für einen Pin × Cal-Feld. Wird in
  // ``register_live_cal_params`` für alle 18 × 4 = 72 Kombinationen
  // generiert; Single Source of Truth analog zu Stage-A-`_GAIT_PARAMS`.
  struct PinParamSpec
  {
    int pin;                 // 0..17
    std::string field;       // "pulse_min" | "pulse_zero" | "pulse_max" | "direction_normal"
    std::string param_name;  // e.g. "pin_15.pulse_min"
  };
  std::vector<PinParamSpec> pin_param_specs_{};

  // Param-Callback-Handle (lifecycle-managed): hält den
  // Param-Callback-Hook am Leben für die Plugin-Laufzeit.
  rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr
    param_cb_handle_{};

  // /save_calibration-Service (registriert in on_configure).
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr save_service_{};

  // ─── Stage 0.5 — Safety Hard-Stop bei Pulse-Out-of-Range ───────────────
  // Wenn `radians_to_pulse_us` einen Wert außerhalb von
  // [pulse_min, pulse_max] für irgendeinen Pin liefert, geht das Plugin
  // in safety_freeze: alle Joints halten ihre letzte gültige PWM-Position,
  // keine neuen Commands werden zur Firmware geschickt. Recovery nur
  // über `/hexapod_safety_reset` (std_srvs::Trigger) — bewusst manuelle
  // User-Aktion, da ein OoR-Trigger immer ein IK/URDF/Cal-Mismatch ist
  // und investigated werden muss, bevor weiter gefahren wird.
  //
  // Firmware bleibt dumb (User-Entscheidung 2026-05-24): das hexapod_ws
  // Plugin garantiert allein, dass kein PWM außerhalb cal-range gesendet
  // wird. Im freeze-Zustand schreibt write() last_command_pulse_us_ zu
  // allen Pins (= aktuell-eingenommene Position), unabhängig vom
  // ros2_control-Command.
  std::atomic<bool> safety_freeze_{false};

  // /hexapod_safety_reset-Service (registriert in on_configure parallel
  // zu /save_calibration).
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr safety_reset_service_{};

  // Service-Callback: clared safety_freeze_-Flag, gibt Status in
  // Response zurück (success=true wenn vorher frozen, success=true mit
  // Hinweis-Message wenn idempotent / nicht frozen).
  void handle_safety_reset(
    std_srvs::srv::Trigger::Request::ConstSharedPtr request,
    std_srvs::srv::Trigger::Response::SharedPtr response);

  // Stage 0.6: /hexapod_safety_freeze service — counterpart to
  // /hexapod_safety_reset. Triggers safety_freeze externally (vs. the
  // implicit OoR detection in write()). Used by gait_node when IK
  // detects a joint-limit violation: gait calls this async so the
  // plugin's hold-last-good kicks in immediately, even though the OoR
  // wouldn't have triggered the in-write detection (rad-Werte sind
  // out-of-URDF-Limit aber Plugin-Cal-Range würde es schaffen).
  rclcpp::Service<std_srvs::srv::Trigger>::SharedPtr safety_freeze_service_{};

  // Service-Callback: sets safety_freeze_=true and returns a status
  // message describing what happened (just-frozen vs already-frozen).
  void handle_safety_freeze(
    std_srvs::srv::Trigger::Request::ConstSharedPtr request,
    std_srvs::srv::Trigger::Response::SharedPtr response);

  // Phase 13 Stage 0.1: /hexapod_relay_set service — gate the servo V+ rail
  // via the Servo2040 relay (RELAY_CONTROL frame → GP26). req.data=true closes
  // the relay (servos powered). Fail-safe is firmware-side (relay drops on any
  // trip/RESET) plus on_deactivate sends relay-off. Manual control is what the
  // Stage-0.2 femur remount uses; the automatic on_activate relay sequence is
  // Stage 0.3.
  rclcpp::Service<std_srvs::srv::SetBool>::SharedPtr relay_set_service_{};

  void handle_relay_set(
    std_srvs::srv::SetBool::Request::ConstSharedPtr request,
    std_srvs::srv::SetBool::Response::SharedPtr response);

  // ─── Phase 11 Stage C — /servo_pulses Diagnostic-Topic ─────────────────
  // Live-Toggle für Cal-Session / Debugging. Default `false` —
  // im Normalbetrieb keine Topic-Last (4 KB/s gespart auf dem Pi).
  // Set via on_param_change wenn Param `publish_servo_pulses` toggled.
  std::atomic<bool> publish_pulses_enabled_{false};

  // Publisher selbst lebt immer (in on_init erzeugt) — wird in `write()`
  // nur conditional benutzt (Param-Toggle + Subscriber-Check).
  rclcpp::Publisher<std_msgs::msg::Int32MultiArray>::SharedPtr
    pulses_pub_{};

  // Block F2 — shutdown-switch state surfaced from the firmware's status_flags
  // bit 7 (SHUTDOWN_REQUEST) to ROS. Latched (transient_local) so a late/
  // restarting supervisor immediately gets the current value; published only on
  // change (read() runs at control rate). See F2_hw_shutdown_publisher_plan.md.
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr shutdown_request_pub_{};
  bool last_shutdown_request_{false};

  // ─── Block A5 Stufe 5 — HW foot-contact publishers ─────────────────────
  // Six std_msgs/Bool publishers on /leg_<n>/foot_contact, mirroring the sim's
  // foot_contact_publisher so gait_node's S4 pipeline is source-agnostic. Fed
  // from the firmware's debounced GET_INPUTS bitmask (reader_.latest_inputs()).
  // read() publishes only while the snapshot is fresh; a silent firmware lets
  // gait_node's 0.5 s contact live-guard trip (adaptive features → nominal).
  std::array<rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr, NUM_LEGS>
  foot_contact_pubs_{};
  bool publish_foot_contacts_{true};
  // Per-leg source bit in the GET_INPUTS bitmask: index = leg-1, value = bit
  // (0..5). Default identity (SENSOR_n = leg_n); overridable via the
  // "sensor_leg_map" hardware_parameter (CSV of 6 sensor channels 1..6).
  std::array<int, NUM_LEGS> sensor_bit_for_leg_{};

  // Block F2 — the plugin otherwise never requests state (joint feedback is
  // echo-based; trips arrive as unsolicited ERROR_REPORT), so the firmware would
  // never send a STATE_RESPONSE and latest_state() (carrying status_flags bit 7)
  // would stay empty. write() sends a throttled GET_STATE every N ticks to drive
  // the reply. ~5 Hz at a 50 Hz update rate; the 3 s FW hold hides the latency.
  unsigned get_state_poll_counter_{0};

  // Helper: deklariert die 72 Live-Cal-Params + registriert Callback.
  // Aufgerufen am Ende von on_init.
  void register_live_cal_params();

  // Param-Callback: atomic-all-or-nothing-Validation analog Stage A.
  // Direction-Updates in active-State werden abgelehnt
  // (siehe is_active_ + B-Q4-Entscheidung).
  rcl_interfaces::msg::SetParametersResult on_param_change(
    const std::vector<rclcpp::Parameter> & params);

  // Service-Callback: ruft calibration_.save_to_file(calibration_file_).
  // Stellt sicher dass <calibration_file>.bak-<timestamp> erzeugt wird.
  void handle_save_calibration(
    std_srvs::srv::Trigger::Request::ConstSharedPtr request,
    std_srvs::srv::Trigger::Response::SharedPtr response);

  // ─── Phase 13 Stage A — Initial-Pose-Preset ────────────────────────────
  // Plugin sendet beim on_activate die hier gespeicherten Pulse als
  // erstes SET_TARGETS-Frame (statt generisch pulse_zero). Mit Default-
  // Preset "suspended" haengt der Roboter aufgebockt mit den Beinen
  // schwerkraftbedingt nach unten — kein ruckartiges Hochspringen.
  //
  // Befuellt in on_init aus initial_poses.yaml (Preset-Name aus
  // hardware_parameter "initial_pose"). Wenn YAML fehlt oder Preset
  // unbekannt: pre-Validate sieht keine OoR, daher Fallback ist
  // pulse_zero pro Pin (= Legacy-Verhalten).
  //
  // Pre-Validate: Plugin rechnet pro Joint rad -> PWM via Calibration
  // BEREITS in on_init und prueft [pulse_min, pulse_max]; bei OoR fuer
  // einen Pin wird dieser Pin auf pulse_zero gesetzt + WARN-Log
  // (Strong-Exception-Style: andere Pins bleiben mit gueltigem Preset).
  std::array<int16_t, NUM_SERVOS> initial_pulse_us_{};

  // ─── Hardware-State (von Stage 9 her) ─────────────────────────────────
  // ─── Configuration (set in on_init from URDF + hardware_parameters) ──────
  std::string serial_port_path_{"/dev/ttyACM0"};
  std::string calibration_file_{};
  std::string initial_poses_file_{};   // Stage A: Pfad zu initial_poses.yaml
  std::string initial_pose_name_{"suspended"};  // Stage A: Preset-Name
  bool loopback_mode_{false};

  // ─── Joint mapping (set in on_init) ──────────────────────────────────────
  // Calibration parses servo_mapping.yaml; set_joint_limits() then injects
  // each joint's URDF <limit> values, indexed by joint name.
  Calibration calibration_{};

  // Translation table: index i is the URDF joint slot (which is what
  // ros2_control hands us via info_.joints[i]); the value is the matching
  // Servo2040 output pin (0..17). The two indices are NOT identical
  // because the URDF can list joints in any order.
  //
  // Example permutation that's legal:
  //    info_.joints[0].name = "leg_3_femur_joint" → output_idx 7
  //    info_.joints[1].name = "leg_1_coxa_joint"  → output_idx 0
  //    ...
  //
  // Used in write()/read() to translate between URDF-slot data
  // (hw_command_positions_, hw_state_positions_) and servo-pin data
  // (last_command_pulse_us_, encode_set_targets payload).
  std::vector<int> joint_to_output_idx_{};

  // ─── Phase 13 Stage 0.3 — Joint-group enable lists (servo-pin indexed) ──
  // Built in on_init by classifying joint names by segment. The relay-gated
  // on_activate sequence enables them in order femur → (relay-on) → coxa →
  // tibia to stage inrush current across the rail. Each is sorted ascending
  // by pin for a deterministic wire order. Together they partition 0..17.
  std::vector<uint8_t> coxa_pins_{};
  std::vector<uint8_t> femur_pins_{};
  std::vector<uint8_t> tibia_pins_{};

  // ─── State exposed to ros2_control via export_*_interfaces ───────────────
  // Indexed by URDF slot (i.e. info_.joints[i]). ros2_control captures
  // the addresses of these elements when on_init returns, so the vectors
  // must be sized and stable in memory before export_*_interfaces is called.
  std::vector<double> hw_state_positions_{};
  std::vector<double> hw_command_positions_{};

  // ─── Wire-side state (indexed by servo pin 0..17) ────────────────────────
  // Last pulse value we sent or are about to send to each Servo2040 output.
  // Sized to NUM_SERVOS at construction, not on_init — fixed by hardware.
  // Initialised to pulse_zero per servo at end of on_init.
  std::array<int16_t, NUM_SERVOS> last_command_pulse_us_{};

  // Frame sequence counter — incremented per outgoing frame. Atomic because
  // on_activate's RESET/ENABLE sequence and the controller_manager's write()
  // tick may race in pathological orderings (e.g. lifecycle race during
  // shutdown). uint8_t wraps at 256; firmware is stateless w.r.t. SEQ
  // (echoes it in replies) so wraparound is harmless.
  std::atomic<uint8_t> seq_{0};

  // Phase 11 Stage B — Lifecycle-State-Tracking für Param-Callback.
  // `get_node()` liefert `rclcpp::Node`, nicht `LifecycleNode` — wir
  // tracken den State daher selbst. true ab `on_activate`-Erfolg,
  // false ab `on_deactivate`-Start. Param-Callback liest atomic load
  // um Direction-Updates in active-State abzulehnen (Servo-Sprung 180°).
  std::atomic<bool> is_active_{false};

  // ─── Hardware (opened/started in on_configure, closed in on_cleanup) ─────
  // Declaration order is INTENTIONAL: serial_port_ is constructed first
  // and (per C++ rules) destroyed LAST. reader_ is constructed second and
  // destroyed FIRST — its destructor calls stop()+join() before
  // serial_port_'s destructor can close the FD out from under the running
  // reader thread. This makes the destruction path safe even if a user
  // forgets to call on_cleanup.
  //
  // Lifetime of the reference held by the reader thread:
  //   - Servo2040Reader::start(SerialPort & port) stores a SerialPort *
  //     inside the spawned thread (via lambda capture).
  //   - That reference is only valid as long as serial_port_ lives.
  //   - The declaration order above guarantees serial_port_ outlives
  //     reader_ because reader_'s destructor (stop+join) finishes before
  //     serial_port_'s destructor begins. Do not reorder these without
  //     understanding the consequence.
  //
  // In loopback_mode_ neither is actually used; both stay default-constructed
  // (port not open, reader not started).
  SerialPort serial_port_{};

  // Stage 0.1 — serialises serial_port_.write_all() across threads. write()
  // runs on the controller_manager update thread; service callbacks (relay,
  // …) run on the node executor thread. Without this lock two frames could
  // interleave on the wire and corrupt the COBS stream.
  mutable std::mutex serial_write_mutex_{};
  Servo2040Reader reader_{};
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
