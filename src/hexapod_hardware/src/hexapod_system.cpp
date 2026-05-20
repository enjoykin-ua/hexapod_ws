// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/hexapod_system.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <climits>
#include <cmath>
#include <cstdint>
#include <exception>
#include <map>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <pluginlib/class_list_macros.hpp>
#include <rclcpp/rclcpp.hpp>

#include "hexapod_hardware/error_report_log.hpp"

namespace hexapod_hardware
{

namespace
{

rclcpp::Logger plugin_logger()
{
  return rclcpp::get_logger("hexapod_hardware");
}

// Case-insensitive bool-string parser for hardware_parameters values.
// Accepts: "true"/"false", "1"/"0", "yes"/"no". Throws on anything else
// so a typo in the URDF doesn't silently fall back to the default.
bool parse_bool(const std::string & value, const std::string & key)
{
  std::string lower = value;
  std::transform(
    lower.begin(), lower.end(), lower.begin(),
    [](unsigned char c) {return static_cast<char>(std::tolower(c));});
  if (lower == "true" || lower == "1" || lower == "yes") {return true;}
  if (lower == "false" || lower == "0" || lower == "no") {return false;}
  throw std::runtime_error(
          "HexapodSystemHardware: hardware_parameter '" + key +
          "' must be true/false (got '" + value + "')");
}

// Convenience accessor for info_.hardware_parameters with a default.
std::string param_or(
  const std::unordered_map<std::string, std::string> & params,
  const std::string & key, const std::string & fallback)
{
  auto it = params.find(key);
  return it != params.end() ? it->second : fallback;
}

}  // namespace

hardware_interface::CallbackReturn HexapodSystemHardware::on_init(
  const hardware_interface::HardwareComponentInterfaceParams & params)
{
  // Let the base class populate info_ from params.hardware_info.
  if (hardware_interface::SystemInterface::on_init(params) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(
    plugin_logger(),
    "HexapodSystemHardware::on_init starting (info_.joints.size=%zu)",
    info_.joints.size());

  // ─── 1) Joint-count validation ─────────────────────────────────────────
  // The hexapod has exactly 18 joints (6 legs × 3 joints/leg). If the URDF
  // <ros2_control> block contains anything else, that's almost certainly a
  // typo/oversight that we'd rather fail loud than silently work-around.
  if (info_.joints.size() != NUM_SERVOS) {
    RCLCPP_FATAL(
      plugin_logger(),
      "Expected exactly %zu joints in <ros2_control>, got %zu",
      NUM_SERVOS, info_.joints.size());
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 2) Hardware parameters ────────────────────────────────────────────
  // Read three plugin parameters from the URDF <param> block.
  //  - serial_port:      defaults to /dev/ttyACM0 (typical Linux CDC path)
  //  - calibration_file: NO default — refuse to start without it
  //  - loopback_mode:    defaults to false (true = no serial, echo-only,
  //                      used for CI and dev work without hardware)
  try {
    serial_port_path_ = param_or(
      info_.hardware_parameters, "serial_port", "/dev/ttyACM0");

    calibration_file_ = param_or(
      info_.hardware_parameters, "calibration_file", "");
    if (calibration_file_.empty()) {
      RCLCPP_FATAL(
        plugin_logger(),
        "<param name=\"calibration_file\"> must be set in the URDF "
        "<ros2_control> block (no default — typically "
        "$(find hexapod_hardware)/config/servo_mapping.yaml)");
      return hardware_interface::CallbackReturn::ERROR;
    }

    const std::string lb = param_or(info_.hardware_parameters, "loopback_mode", "false");
    loopback_mode_ = parse_bool(lb, "loopback_mode");
  } catch (const std::exception & e) {
    RCLCPP_FATAL(plugin_logger(), "Failed to parse hardware parameters: %s", e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(
    plugin_logger(),
    "Config: serial_port=%s, calibration_file=%s, loopback_mode=%s",
    serial_port_path_.c_str(), calibration_file_.c_str(),
    loopback_mode_ ? "true" : "false");

  // ─── 3) Load calibration YAML ──────────────────────────────────────────
  try {
    calibration_.load_from_file(calibration_file_);
  } catch (const std::exception & e) {
    RCLCPP_FATAL(
      plugin_logger(),
      "Failed to load calibration file '%s': %s",
      calibration_file_.c_str(), e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 4) URDF joint limits → calibration ────────────────────────────────
  // ros2_control parses <limit lower="..." upper="..."/> from the URDF
  // and puts the values on the joint's position-interface as `min` and
  // `max` strings (see hardware_interface/InterfaceInfo). If a joint
  // doesn't have a position interface or has empty min/max strings, we
  // log a warning and fall through to the Calibration defaults (±1.57).
  //
  // INVARIANT we enforce here: lower < upper (strictly). The URDF spec
  // requires that — <limit lower upper> is an interval. If a URDF bug
  // swaps them (or sets both equal), Calibration would compute a
  // negative or zero slope and produce NaN/inf pulse values; the servo
  // would then jump to a hard-clamp or stay stuck. Fail loud here.
  //
  // NOTE on mirrored legs: you might wonder if left vs right legs need
  // swapped limits (the "sensor mounted backwards" pattern). They DON'T.
  // Both sides keep lower=-1.57 / upper=+1.57; the physical mirroring
  // lives in servo_mapping.yaml's `direction: ±1` field, which flips
  // the pulse-µs sign INSIDE Calibration::radians_to_pulse_us. URDF
  // limits stay the same shape for every joint by design.
  //
  // Calibration::set_joint_limits silently ignores unknown joint names,
  // so passing through more joints than we own is harmless.
  for (const auto & joint : info_.joints) {
    bool found_limits = false;
    for (const auto & cmd_if : joint.command_interfaces) {
      if (cmd_if.name == hardware_interface::HW_IF_POSITION) {
        if (!cmd_if.min.empty() && !cmd_if.max.empty()) {
          try {
            const double lower = std::stod(cmd_if.min);
            const double upper = std::stod(cmd_if.max);
            if (!(lower < upper)) {
              RCLCPP_FATAL(
                plugin_logger(),
                "Joint '%s' has invalid limits: lower=%.4f, upper=%.4f. "
                "URDF requires lower < upper strictly (interval, not signed "
                "mapping — mirrored legs use servo_mapping.yaml's `direction` "
                "instead).",
                joint.name.c_str(), lower, upper);
              return hardware_interface::CallbackReturn::ERROR;
            }
            calibration_.set_joint_limits(joint.name, lower, upper);
            found_limits = true;
          } catch (const std::invalid_argument & e) {
            RCLCPP_WARN(
              plugin_logger(),
              "Could not parse joint limits for '%s' (min='%s', max='%s'): %s "
              "— falling back to Calibration defaults (±1.57)",
              joint.name.c_str(), cmd_if.min.c_str(), cmd_if.max.c_str(), e.what());
          } catch (const std::out_of_range & e) {
            RCLCPP_WARN(
              plugin_logger(),
              "Joint limits for '%s' out of double range (min='%s', max='%s'): %s "
              "— falling back to Calibration defaults",
              joint.name.c_str(), cmd_if.min.c_str(), cmd_if.max.c_str(), e.what());
          }
        }
        break;
      }
    }
    if (!found_limits) {
      RCLCPP_WARN(
        plugin_logger(),
        "Joint '%s' has no <limit lower/upper> on its position command_interface "
        "— Calibration uses ±1.57 default; pulse values may be wrong if your "
        "URDF range differs",
        joint.name.c_str());
    }
  }

  // ─── 5) Build URDF-slot → servo-pin translation table ──────────────────
  // ros2_control hands us info_.joints in URDF order. Our wire protocol
  // (encode_set_targets) needs values in Servo-2040-output-pin order.
  // calibration_.output_idx_for_joint() does the lookup; it throws if the
  // joint name is not in servo_mapping.yaml — which is itself an error
  // worth surfacing (likely typo in the URDF or stale YAML).
  //
  // Strong exception guarantee: build into a local vector first, only
  // move into the member at the very end (after duplicate-detection
  // also passed). If we throw mid-loop, joint_to_output_idx_ keeps its
  // previous value (empty on first init, prior valid table on re-init).
  // Same idiom as Calibration::load_from_string in stage C.
  std::vector<int> new_table;
  new_table.reserve(info_.joints.size());
  try {
    for (const auto & joint : info_.joints) {
      new_table.push_back(calibration_.output_idx_for_joint(joint.name));
    }
  } catch (const std::exception & e) {
    RCLCPP_FATAL(
      plugin_logger(),
      "URDF joint name not found in calibration: %s", e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  // Sanity: every output_idx must be unique (each servo pin used by exactly
  // one URDF joint). Duplicates would point two URDF joints at the same
  // physical servo — silently wrong, hence a hard error.
  std::vector<int> sorted_idx = new_table;
  std::sort(sorted_idx.begin(), sorted_idx.end());
  if (std::adjacent_find(sorted_idx.begin(), sorted_idx.end()) != sorted_idx.end()) {
    RCLCPP_FATAL(
      plugin_logger(),
      "URDF maps two joints to the same Servo2040 output pin — "
      "check servo_mapping.yaml for duplicate joint entries");
    return hardware_interface::CallbackReturn::ERROR;
  }

  // Commit. std::vector move-assignment is no-throw.
  joint_to_output_idx_ = std::move(new_table);

  // ─── 6) Allocate state vectors (URDF-indexed) ──────────────────────────
  // Allocated once, never resized — ros2_control captures the element
  // addresses via export_*_interfaces() and they must stay stable.
  //
  // Pointer-stability detail: on re-init (cleanup→init), the vectors
  // already have size NUM_SERVOS from the previous run. vector::assign(n,v)
  // with n <= capacity() does NOT reallocate (cppref guarantee), so any
  // pointers ros2_control captured previously stay valid. The contract
  // ros2_control gives us is that it re-calls export_*_interfaces() after
  // every on_init, but we keep this property as defense in depth.
  hw_state_positions_.assign(info_.joints.size(), 0.0);
  hw_command_positions_.assign(info_.joints.size(), 0.0);

  // ─── 7) Initialise last_command_pulse_us_ (servo-pin-indexed) ──────────
  // At plugin load, every servo's "last commanded pulse" is its neutral
  // pulse_zero. read() reflects this back as 0 rad (the joint mid-point)
  // — the first JTC trajectory the user issues will then move from there.
  //
  // hw_state_positions_ stays at 0.0 until the first read() tick after
  // on_activate; D.6 will fill it via Calibration::pulse_us_to_radians
  // on the values we just initialised, which means the first read also
  // yields 0 rad — consistent with hw_command_positions_=0.0 above.
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    last_command_pulse_us_[pin] = calibration_.at(static_cast<int>(pin)).pulse_zero;
  }

  // ─── 8) Phase 11 Stage B — Live-Cal-Params + Save-Service ──────────────
  // Deklariert 72 Pin-Params (4 Felder × 18 Pins) mit ParameterDescriptor +
  // Range, registriert Param-Callback für Live-Updates. Defaults kommen aus
  // der gerade geladenen Calibration.
  // get_node() ist nach Basis-Klassen on_init verfügbar (ros2_control Jazzy).
  try {
    register_live_cal_params();
  } catch (const std::exception & e) {
    RCLCPP_FATAL(
      plugin_logger(),
      "Phase 11 Stage B: failed to register live-cal params: %s", e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(
    plugin_logger(), "on_init complete — %zu joints mapped to 18 servo pins, "
    "calibration loaded from %s, %zu live-cal params registered",
    info_.joints.size(), calibration_file_.c_str(),
    pin_param_specs_.size());
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_configure(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(plugin_logger(), "on_configure starting (loopback_mode=%s, serial_port=%s)",
    loopback_mode_ ? "true" : "false", serial_port_path_.c_str());

  // ─── Phase 11 Stage B — /save_calibration-Service ──────────────────
  // Vor dem loopback_mode_-Early-Return, damit auch Loopback-Pfade
  // (CI + Tests) den Service haben. Idempotent: bei erneutem on_configure
  // wird der alte Handle überschrieben.
  if (auto node = get_node()) {
    save_service_ = node->create_service<std_srvs::srv::Trigger>(
      "save_calibration",
      std::bind(
        &HexapodSystemHardware::handle_save_calibration, this,
        std::placeholders::_1, std::placeholders::_2));
    RCLCPP_INFO(
      plugin_logger(),
      "Phase 11 Stage B: /save_calibration service ready");
  } else {
    RCLCPP_WARN(
      plugin_logger(),
      "Phase 11 Stage B: get_node() returned null in on_configure — "
      "/save_calibration service not registered");
  }

  if (loopback_mode_) {
    // No serial port to open; no reader thread to start. The lifecycle
    // is otherwise identical so the rest of the plugin (write/read echo,
    // controller_manager interaction) works the same.
    RCLCPP_INFO(plugin_logger(),
      "Loopback mode: skipping serial-port open and reader-thread start");
    return hardware_interface::CallbackReturn::SUCCESS;
  }

  // ─── 1) Open serial port ───────────────────────────────────────────────
  // Note on repeated on_configure calls: ros2_control's lifecycle manager
  // only allows on_configure from the `unconfigured` state, so this code
  // path is normally entered exactly once per cycle. If somehow it IS
  // called twice without an intervening on_cleanup, serial_port_.open()
  // will throw "port is already open" — we catch it, return ERROR, and
  // leave the (already-open) port intact. No state corruption.
  try {
    serial_port_.open(serial_port_path_);
  } catch (const std::exception & e) {
    RCLCPP_FATAL(plugin_logger(),
      "Failed to open serial port '%s': %s. "
      "Common causes: device not plugged in, missing dialout-group "
      "membership (id | grep dialout), wrong path in URDF <param "
      "name=\"serial_port\">.",
      serial_port_path_.c_str(), e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 2) Start reader thread ────────────────────────────────────────────
  // Must come AFTER the port is open. If start() fails we have to close
  // the port again to keep the cleanup invariants consistent.
  try {
    reader_.start(serial_port_);
  } catch (const std::exception & e) {
    RCLCPP_FATAL(plugin_logger(), "Failed to start reader thread: %s", e.what());
    serial_port_.close();
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 3) Defensive: did the reader die in its first 10 ms? ──────────────
  // Edge case: USB disconnect lands between open() and the reader's first
  // poll() call — the thread reads EIO immediately and sets died_ = true.
  // Without this check we'd return SUCCESS, the lifecycle manager would
  // activate the plugin, and only the first read() tick (~20 ms later)
  // would catch the disconnect. With the check we fail loud right here.
  //
  // 10 ms is a deliberate choice: long enough for the reader's first
  // read_some() to land (it's blocking with a 1 s poll timeout, but a
  // device-disconnect errno comes back from poll() much faster than the
  // timeout); short enough that on_configure stays snappy.
  std::this_thread::sleep_for(std::chrono::milliseconds(10));
  if (reader_.died()) {
    RCLCPP_FATAL(plugin_logger(),
      "Reader thread died within 10 ms of start (probable disconnect "
      "between port open and first read). Check USB connection to "
      "Servo2040.");
    reader_.stop();   // idempotent, joins the already-exited thread
    serial_port_.close();
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(plugin_logger(),
    "on_configure complete (serial port open, reader thread running)");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_cleanup(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(plugin_logger(), "on_cleanup starting");

  // Order matters: stop the reader thread first so it can't be reading
  // from the FD when we close it (close while another thread is in
  // poll/read on the FD → POLLNVAL/EBADF — Servo2040Reader logs that
  // as a system_error and sets died_=true, which is needlessly alarming).
  //
  // Both stop() and close() are idempotent and noexcept — calling them
  // on an unconfigured plugin (loopback mode that never opened a port,
  // or on_init failed before on_configure) is safe.
  reader_.stop();
  serial_port_.close();

  RCLCPP_INFO(plugin_logger(), "on_cleanup complete");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(plugin_logger(), "on_activate starting (loopback_mode=%s)",
    loopback_mode_ ? "true" : "false");

  // In loopback mode we still walk the boot sequence to keep code paths
  // identical (seq_ increments, last_command_pulse_us_ is set to pulse_zero)
  // but skip wire I/O and the 50 ms stagger. CI stays fast (< 100 ms) and
  // a test can assert seq_ increments by 20 (1 RESET + 18 ENABLE + 1 SET_TARGETS).
  const auto stagger = loopback_mode_ ?
    std::chrono::milliseconds(0) :
    std::chrono::milliseconds(50);

  // Defensive helper: any write_all() call goes through this. If the reader
  // thread died (USB just got unplugged), bail out before throwing on the
  // closed FD — the resulting error log is much clearer than a system_error
  // chain. Returns false to signal the caller to abort the boot sequence.
  auto send_frame =
    [this](const std::vector<uint8_t> & frame, const char * what) -> bool {
      if (loopback_mode_) {return true;}
      if (reader_.died()) {
        RCLCPP_FATAL(plugin_logger(),
          "Reader thread died before/while sending %s — likely USB disconnect. "
          "Aborting on_activate; controller will stay inactive.", what);
        return false;
      }
      try {
        serial_port_.write_all(frame.data(), frame.size());
      } catch (const std::exception & e) {
        RCLCPP_FATAL(plugin_logger(),
          "Failed to send %s frame: %s", what, e.what());
        return false;
      }
      return true;
    };

  // ─── 1) RESET: clear any latched WATCHDOG_TRIPPED from a prior run ────
  // If the plugin previously died without a clean on_deactivate (SIGKILL,
  // crash, USB yanked), the firmware may still have its watchdog flag set.
  // ENABLE_SERVO frames are NACK'd in that state; sending RESET first makes
  // the boot sequence idempotent regardless of how the last run ended.
  // Spec ref: PROTOCOL.md §6 "Recovery".
  {
    auto frame = encode_reset(seq_.fetch_add(1));
    if (!send_frame(frame, "RESET")) {
      return hardware_interface::CallbackReturn::ERROR;
    }
    // Small breather so the firmware can process RESET before the ENABLE
    // barrage arrives. 10 ms is well above the firmware's frame-dispatch
    // cost (~ µs) but invisible to the 50 ms per-servo cadence below.
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  // ─── 2) 18× ENABLE_SERVO with 50 ms host-side stagger ──────────────────
  // Phase-7 design decision D.1: the host paces the per-servo enables to
  // spread inrush current across ~900 ms. Each frame also resets the
  // firmware's 200 ms watchdog (PROTOCOL.md §6), so the watchdog stays warm
  // throughout the boot.
  for (uint8_t pin = 0; pin < NUM_SERVOS; ++pin) {
    auto frame = encode_enable_servo(seq_.fetch_add(1), pin, /*enable=*/true);
    if (!send_frame(frame, "ENABLE_SERVO")) {
      return hardware_interface::CallbackReturn::ERROR;
    }
    std::this_thread::sleep_for(stagger);
  }

  // ─── 3) SET_TARGETS with neutral pulses ────────────────────────────────
  // Two purposes:
  //  - keep the watchdog warm during the gap between on_activate's exit and
  //    the first controller_manager write() tick (could be > 200 ms in
  //    pathological launch timings)
  //  - put the robot in a defined neutral pose (all joints at pulse_zero,
  //    ≈ 1500 µs ≡ 0 rad) so the first JTC trajectory has a known start
  //
  // last_command_pulse_us_ is already pulse_zero from on_init, but we
  // re-assert it here so a re-activate after a disconnect-recovery cycle
  // also lands in the neutral pose regardless of what the last write() set.
  std::array<int16_t, NUM_SERVOS> neutral_pulses{};
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    neutral_pulses[pin] = calibration_.at(static_cast<int>(pin)).pulse_zero;
    last_command_pulse_us_[pin] = neutral_pulses[pin];
  }
  auto neutral_frame = encode_set_targets(seq_.fetch_add(1), neutral_pulses);
  if (!send_frame(neutral_frame, "SET_TARGETS (neutral)")) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // Phase 11 Stage B — Lifecycle-State markieren. Set NACH erfolgreichem
  // Activate (alle Frames gesendet), damit Param-Callback erst dann
  // Direction-Updates ablehnt wenn der Active-State wirklich erreicht ist.
  is_active_.store(true);

  RCLCPP_INFO(plugin_logger(),
    "on_activate complete — %s (seq counter advanced by 20)",
    loopback_mode_ ?
    "loopback path traced, no wire frames sent" :
    "18 servos enabled, neutral pose commanded");
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  RCLCPP_INFO(plugin_logger(), "on_deactivate starting");

  // Phase 11 Stage B — Lifecycle-State zurücksetzen. Set zuerst (vor
  // Disable-Frames) damit Param-Callback ab sofort Direction-Updates
  // wieder akzeptiert (User kann während Deactivate-Sequenz schon
  // tunen).
  is_active_.store(false);

  // Unlike on_activate, on_deactivate runs WITHOUT stagger. Disable does
  // not draw inrush current (servos just go limp), and we want the robot
  // to lose torque as fast as possible — e.g. when a safety condition
  // triggers the user to switch the controller back to inactive.
  //
  // Best-effort semantics: if a frame fails to send (port already gone,
  // reader thread died), we log and continue with the remaining servos.
  // Returning ERROR would make ros2_control fault, but at deactivate-time
  // there's no recovery path anyway and the firmware's watchdog will
  // disable everything within 200 ms regardless.
  if (loopback_mode_) {
    RCLCPP_INFO(plugin_logger(),
      "Loopback mode: skipping disable frames");
    return hardware_interface::CallbackReturn::SUCCESS;
  }

  std::size_t failures = 0;
  for (uint8_t pin = 0; pin < NUM_SERVOS; ++pin) {
    if (reader_.died()) {
      RCLCPP_WARN(plugin_logger(),
        "Reader thread died during on_deactivate; skipping remaining "
        "ENABLE_SERVO(false) frames (firmware watchdog will disable "
        "everything within 200 ms anyway).");
      break;
    }
    auto frame = encode_enable_servo(seq_.fetch_add(1), pin, /*enable=*/false);
    try {
      serial_port_.write_all(frame.data(), frame.size());
    } catch (const std::exception & e) {
      ++failures;
      RCLCPP_WARN(plugin_logger(),
        "Failed to send ENABLE_SERVO(%u, false): %s", pin, e.what());
    }
  }

  if (failures > 0) {
    RCLCPP_WARN(plugin_logger(),
      "on_deactivate completed with %zu/%zu disable frames lost — relying "
      "on firmware watchdog for fallback", failures, NUM_SERVOS);
  } else {
    RCLCPP_INFO(plugin_logger(), "on_deactivate complete — 18 servos disabled");
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface>
HexapodSystemHardware::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> ifs;
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    ifs.emplace_back(
      info_.joints[i].name, hardware_interface::HW_IF_POSITION,
      &hw_state_positions_[i]);
  }
  return ifs;
}

std::vector<hardware_interface::CommandInterface>
HexapodSystemHardware::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> ifs;
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    ifs.emplace_back(
      info_.joints[i].name, hardware_interface::HW_IF_POSITION,
      &hw_command_positions_[i]);
  }
  return ifs;
}

hardware_interface::return_type HexapodSystemHardware::read(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  // ─── Echo-State: pulse → radians via Calibration ─────────────────────
  // The Servo2040 hardware does not report actual servo positions, so the
  // best we can do is reflect the last commanded pulse back as the current
  // state. The result is fed to JTC / joint_state_broadcaster as if the
  // robot tracked perfectly. Tracking error is therefore structurally zero
  // (limitation, not a feature — see README "Echo-State-Limitation").
  //
  // Index mapping: hw_state_positions_[i] is indexed by URDF slot;
  // last_command_pulse_us_[output_idx] is indexed by servo-pin. The
  // joint_to_output_idx_ table (built in on_init) bridges the two.
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    const int output_idx = joint_to_output_idx_[i];
    hw_state_positions_[i] = calibration_.pulse_us_to_radians(
      output_idx, static_cast<double>(last_command_pulse_us_[output_idx]));
  }

  // ─── Drain firmware error reports (loopback has no reader) ───────────
  // The reader thread queues ERROR_REPORT frames as the firmware sends
  // them (watchdog trips, overcurrent, etc.). Each entry is formatted
  // and logged at the severity that matches its operational weight —
  // frame-layer drops as WARN, undervoltage as ERROR, watchdog/total-
  // overcurrent as FATAL. See error_report_log.{hpp,cpp} for the table
  // and phase_9_stage_d_8_plan.md for the per-code rationale.
  if (!loopback_mode_) {
    for (const auto & er : reader_.drain_error_queue()) {
      const std::string msg = format_error_report(er);
      switch (severity_for(er)) {
        case ErrorSeverity::WARN:
          RCLCPP_WARN(plugin_logger(), "%s", msg.c_str());
          break;
        case ErrorSeverity::ERROR:
          RCLCPP_ERROR(plugin_logger(), "%s", msg.c_str());
          break;
        case ErrorSeverity::FATAL:
          RCLCPP_FATAL(plugin_logger(), "%s", msg.c_str());
          break;
      }
    }

    if (reader_.died()) {
      // ros2_control surfaces this by deactivating the controllers; the
      // user has to investigate (see README "Reconnect-Recovery").
      // Log ONCE-style by gating on a transient flag would be ideal —
      // but RCLCPP_ERROR_ONCE without a clock is fine: it's per-callsite
      // global, and read() has a single ERROR-return path.
      RCLCPP_ERROR_ONCE(plugin_logger(),
        "Reader thread died — see earlier FATAL log. Controller will "
        "be deactivated by ros2_control until you manually re-activate.");
      return hardware_interface::return_type::ERROR;
    }
  }
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type HexapodSystemHardware::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  // ─── Defensive: bail out early if the reader thread died ─────────────
  // Prevents write_all from throwing on an EIO'd FD; controller_manager
  // sees ERROR and deactivates cleanly. (Loopback has no reader.)
  if (!loopback_mode_ && reader_.died()) {
    RCLCPP_ERROR_ONCE(plugin_logger(),
      "write(): reader thread died — skipping wire I/O until re-activate");
    return hardware_interface::return_type::ERROR;
  }

  // ─── Convert each command (rad) → pulse_us, indexed by servo-pin ─────
  // The pulse-µs side is the wire-native representation (int16, signed),
  // so we clamp to the int16 range before casting. The firmware will
  // hard-clamp again to per-servo pulse_min/pulse_max (Phase-7 stage C.1);
  // this clamp here is purely to keep the cast well-defined even when
  // the controller hands us NaN or absurd values.
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    const int output_idx = joint_to_output_idx_[i];
    const double rad = hw_command_positions_[i];

    if (std::isnan(rad)) {
      // NaN from upstream — never let it reach calibration_ (would produce
      // NaN pulse and corrupt the wire frame). Keep the last good value.
      // No throttle: NaN in the trajectory is a real bug we want loud.
      RCLCPP_WARN(plugin_logger(),
        "NaN command for joint '%s' (slot %zu, pin %d); reusing last good "
        "pulse %d µs",
        info_.joints[i].name.c_str(), i, output_idx,
        last_command_pulse_us_[output_idx]);
      continue;
    }

    const double pulse_d = calibration_.radians_to_pulse_us(output_idx, rad);
    // clamp to int16 range — radians_to_pulse_us is unbounded in theory
    // (linear extrapolation past joint_lower/joint_upper). Without this
    // clamp, the static_cast<int16_t> below would be UB for extreme rad
    // (e.g. rad=100 → pulse ≈ 1.3e6 µs → out of int16). Firmware-side
    // clamp to pulse_min/pulse_max is the second line of defense.
    const double pulse_clamped = std::clamp(
      pulse_d,
      static_cast<double>(INT16_MIN),
      static_cast<double>(INT16_MAX));
    last_command_pulse_us_[output_idx] =
      static_cast<int16_t>(std::round(pulse_clamped));
  }

  // ─── Phase 11 Stage C — /servo_pulses Diagnostic-Topic ──────────────
  // Doppel-bedingt: Param `publish_servo_pulses` ON + jemand subscribed.
  // Beides false default → Zero-Cost im Normalbetrieb. Publish VOR dem
  // wire-Send damit auch loopback_mode_ den Topic sieht (Wire-Send
  // returnt früh in loopback).
  if (publish_pulses_enabled_.load() &&
    pulses_pub_ && pulses_pub_->get_subscription_count() > 0)
  {
    std_msgs::msg::Int32MultiArray msg;
    msg.data.reserve(NUM_SERVOS);
    for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
      msg.data.push_back(static_cast<int32_t>(last_command_pulse_us_[pin]));
    }
    pulses_pub_->publish(msg);
  }

  // ─── Send the wire frame (loopback skips) ────────────────────────────
  // One SET_TARGETS per tick = one wire frame at 50 Hz ≈ 7 kB/s, well
  // under the USB-CDC budget (~125 kB/s). encode_set_targets builds
  // SEQ + 18 × int16 LE + CRC + COBS in one allocation.
  if (loopback_mode_) {
    return hardware_interface::return_type::OK;
  }

  auto frame = encode_set_targets(seq_.fetch_add(1), last_command_pulse_us_);
  try {
    serial_port_.write_all(frame.data(), frame.size());
  } catch (const std::exception & e) {
    RCLCPP_ERROR(plugin_logger(),
      "write(): SerialPort write_all failed: %s. Controller will be "
      "deactivated; reconnect logic comes in D.7.", e.what());
    return hardware_interface::return_type::ERROR;
  }
  return hardware_interface::return_type::OK;
}

// ═════════════════════════════════════════════════════════════════════════
// Phase 11 Stage B — Live-Cal-Params + Save-Service
// ═════════════════════════════════════════════════════════════════════════

void HexapodSystemHardware::register_live_cal_params()
{
  auto node = get_node();
  if (!node) {
    // Plugin läuft außerhalb eines vollen controller_manager-Kontexts
    // (z.B. unit tests die das Plugin direkt instanziieren). Live-Cal
    // funktioniert dort nicht — aber on_init darf nicht failen, sonst
    // brechen alle Lifecycle-Tests.
    RCLCPP_WARN(
      plugin_logger(),
      "Phase 11 Stage B: get_node() returned null — live-cal params "
      "skipped (likely a unit-test context without controller_manager)");
    return;
  }

  // 72 Param-Specs generieren (18 Pins × 4 Felder). Single Source of
  // Truth analog Stage-A-`_GAIT_PARAMS`-Tabelle.
  pin_param_specs_.clear();
  pin_param_specs_.reserve(NUM_SERVOS * 4);
  for (int pin = 0; pin < static_cast<int>(NUM_SERVOS); ++pin) {
    const std::string prefix = "pin_" + std::to_string(pin) + ".";
    pin_param_specs_.push_back({pin, "pulse_min", prefix + "pulse_min"});
    pin_param_specs_.push_back({pin, "pulse_zero", prefix + "pulse_zero"});
    pin_param_specs_.push_back({pin, "pulse_max", prefix + "pulse_max"});
    pin_param_specs_.push_back({pin, "direction_normal",
        prefix + "direction_normal"});
  }

  // Declare Pro Pin alle 4 Params mit Range/Descriptor.
  // Defaults aus der gerade geladenen Calibration (snapshot read).
  for (int pin = 0; pin < static_cast<int>(NUM_SERVOS); ++pin) {
    const auto cal = calibration_.snapshot(pin);
    const std::string prefix = "pin_" + std::to_string(pin) + ".";

    // pulse_min/zero/max als Integer mit Range [500, 2500] —
    // Firmware-Standard-Servo-Range. Defaults in servo_mapping.yaml
    // sind 500/1500/2500, daher muss Range das umfassen sonst
    // declare_parameter wirft Range-Violation. HJ-Tester-Range [800, 2200]
    // ist Untermenge — Validation in update_servo_cal (+ Firmware-Clamp)
    // schützt zusätzlich vor mech. Anschlag.
    for (const auto & field_default : std::vector<std::pair<std::string, int16_t>>{
        {"pulse_min", cal.pulse_min},
        {"pulse_zero", cal.pulse_zero},
        {"pulse_max", cal.pulse_max},
      })
    {
      rcl_interfaces::msg::IntegerRange range;
      range.from_value = 500;
      range.to_value = 2500;
      range.step = 1;
      rcl_interfaces::msg::ParameterDescriptor desc;
      desc.type = rcl_interfaces::msg::ParameterType::PARAMETER_INTEGER;
      desc.description = "Pin " + std::to_string(pin) + " " +
        field_default.first + " (µs). Live-Cal — pulse_min < zero < max, "
        "all ∈ [500, 2500]. HJ-Tester typischer Bereich [800, 2200].";
      desc.integer_range = {range};
      node->declare_parameter<int64_t>(
        prefix + field_default.first,
        static_cast<int64_t>(field_default.second),
        desc);
    }

    // direction_normal: bool (true = +1, false = -1).
    {
      rcl_interfaces::msg::ParameterDescriptor desc;
      desc.type = rcl_interfaces::msg::ParameterType::PARAMETER_BOOL;
      desc.description = "Pin " + std::to_string(pin) + " direction. "
        "true = +1 (URDF angle direct), false = -1 (URDF angle inverted). "
        "Mid-active-flip = servo-sprung um 180°; nur in 'inactive' "
        "lifecycle state änderbar.";
      node->declare_parameter<bool>(
        prefix + "direction_normal", cal.direction > 0, desc);
    }
  }

  // ─── Phase 11 Stage C — Diagnostic-Topic + Toggle-Param ─────────
  {
    rcl_interfaces::msg::ParameterDescriptor desc;
    desc.type = rcl_interfaces::msg::ParameterType::PARAMETER_BOOL;
    desc.description =
      "Publish current 18 pulse-µs values to ~/servo_pulses (default "
      "off — enable only for cal sessions / debugging; ~4 KB/s overhead "
      "when on AND a subscriber is present).";
    node->declare_parameter<bool>("publish_servo_pulses", false, desc);
    publish_pulses_enabled_.store(false);

    // Publisher selbst lebt immer (rclcpp legt sich auch bei 0 Subscribers
    // nicht schlafen — Cost ist nur die Existenz, kein Daten-Fluss).
    // Topic-Name `~/servo_pulses` expandet zu `/<node-name>/servo_pulses`.
    pulses_pub_ = node->create_publisher<std_msgs::msg::Int32MultiArray>(
      "~/servo_pulses", rclcpp::QoS(10));
  }

  // Callback-Hook registrieren. Shared-ptr-Member hält den Hook am Leben.
  param_cb_handle_ = node->add_on_set_parameters_callback(
    std::bind(
      &HexapodSystemHardware::on_param_change, this, std::placeholders::_1));

  RCLCPP_INFO(
    plugin_logger(),
    "Phase 11 Stage B+C: %zu live-cal params + publish_servo_pulses "
    "(default off) declared, on_set_parameters_callback registered, "
    "~/servo_pulses publisher ready",
    pin_param_specs_.size());
}

rcl_interfaces::msg::SetParametersResult
HexapodSystemHardware::on_param_change(
  const std::vector<rclcpp::Parameter> & params)
{
  rcl_interfaces::msg::SetParametersResult result;
  result.successful = true;

  // Phase 11 Stage C — `publish_servo_pulses` Toggle.
  // Wird vor dem PinParamSpec-Filter behandelt damit es nicht in
  // relevant.empty() runter fällt. Atomar setzen, ein Log.
  for (const auto & p : params) {
    if (p.get_name() == "publish_servo_pulses") {
      publish_pulses_enabled_.store(p.as_bool());
      RCLCPP_INFO(
        plugin_logger(),
        "param updated: publish_servo_pulses = %s",
        p.as_bool() ? "true" : "false");
    }
  }

  // 1. Filter: nur Params die zu unseren PinParamSpecs gehören.
  //    Andere (hardware_parameters, use_sim_time, publish_servo_pulses
  //    etc.) immer akzeptieren — `publish_servo_pulses` ist oben schon
  //    ge-applied, ein zweites Mal hier wäre redundant aber harmlos.
  //    Index pair: (param-Pointer, spec-Pointer) für Schleifen-Reuse.
  std::vector<std::pair<const rclcpp::Parameter *, const PinParamSpec *>> relevant;
  for (const auto & p : params) {
    for (const auto & spec : pin_param_specs_) {
      if (spec.param_name == p.get_name()) {
        relevant.push_back({&p, &spec});
        break;
      }
    }
  }
  if (relevant.empty()) {
    return result;  // accept (kein PinParam, evtl. publish_servo_pulses ohnehin done)
  }

  // 2. Active-State-Direction-Reject (B-Q4-Entscheidung A).
  if (is_active_.load()) {
    for (const auto & [p, spec] : relevant) {
      if (spec->field == "direction_normal") {
        result.successful = false;
        result.reason =
          spec->param_name +
          " can only change in 'inactive' lifecycle state "
          "(active-flip = servo-sprung um 180°)";
        return result;
      }
    }
  }

  // 3. Bauen proposed cal per Pin (atomic-all-or-nothing-Strategie).
  //    Start: aktueller Snapshot. Dann pro Param overwriten.
  std::map<int, ServoCalibration> proposed;
  for (const auto & [p, spec] : relevant) {
    if (proposed.find(spec->pin) == proposed.end()) {
      proposed[spec->pin] = calibration_.snapshot(spec->pin);
    }
    auto & cal = proposed[spec->pin];
    if (spec->field == "pulse_min") {
      cal.pulse_min = static_cast<int16_t>(p->as_int());
    } else if (spec->field == "pulse_zero") {
      cal.pulse_zero = static_cast<int16_t>(p->as_int());
    } else if (spec->field == "pulse_max") {
      cal.pulse_max = static_cast<int16_t>(p->as_int());
    } else if (spec->field == "direction_normal") {
      cal.direction = p->as_bool() ? 1 : -1;
    }
  }

  // 4. Pre-Validation: pro Pin Tripel-Check.
  for (const auto & [pin, cal] : proposed) {
    if (!(cal.pulse_min < cal.pulse_zero && cal.pulse_zero < cal.pulse_max)) {
      result.successful = false;
      result.reason =
        "pin_" + std::to_string(pin) +
        ": requires pulse_min < pulse_zero < pulse_max, proposed " +
        std::to_string(cal.pulse_min) + "/" +
        std::to_string(cal.pulse_zero) + "/" +
        std::to_string(cal.pulse_max);
      return result;
    }
  }

  // 5. Apply (atomic: alle oder keiner — pre-validation hat das gecheckt).
  for (const auto & [pin, cal] : proposed) {
    try {
      calibration_.update_servo_cal(pin, cal);
    } catch (const std::exception & e) {
      // Sollte unreachable sein nach Pre-Validation, aber defensive
      // catch damit nicht der ganze Param-Service crasht.
      result.successful = false;
      result.reason = std::string("apply failure: ") + e.what();
      return result;
    }
  }

  // 6. Logging: pro Param eine Zeile (Stage-A-Pattern `cal updated: ...`).
  for (const auto & [p, spec] : relevant) {
    std::string new_val;
    if (spec->field == "direction_normal") {
      new_val = p->as_bool() ? "true (+1)" : "false (-1)";
    } else {
      new_val = std::to_string(p->as_int());
    }
    RCLCPP_INFO(
      plugin_logger(),
      "cal updated: %s = %s",
      p->get_name().c_str(), new_val.c_str());
  }

  return result;
}

void HexapodSystemHardware::handle_save_calibration(
  std_srvs::srv::Trigger::Request::ConstSharedPtr /*request*/,
  std_srvs::srv::Trigger::Response::SharedPtr response)
{
  try {
    calibration_.save_to_file(calibration_file_);
    response->success = true;
    response->message =
      "saved " + std::to_string(NUM_SERVOS) + " cals to " +
      calibration_file_ + " (backup as .bak-<timestamp>)";
    RCLCPP_INFO(plugin_logger(), "%s", response->message.c_str());
  } catch (const std::exception & e) {
    response->success = false;
    response->message =
      std::string("save_calibration failed: ") + e.what();
    RCLCPP_ERROR(plugin_logger(), "%s", response->message.c_str());
  }
}

}  // namespace hexapod_hardware

PLUGINLIB_EXPORT_CLASS(
  hexapod_hardware::HexapodSystemHardware, hardware_interface::SystemInterface)
