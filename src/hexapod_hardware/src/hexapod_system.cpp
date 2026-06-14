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
#include <yaml-cpp/yaml.h>

#include "hexapod_hardware/error_report_log.hpp"

namespace hexapod_hardware
{

namespace
{

rclcpp::Logger plugin_logger()
{
  return rclcpp::get_logger("hexapod_hardware");
}

// Phase 13 Stage 0.3 — servo power-on centre pulse. Hobby servos (Miuzei MS61 /
// Diymore 8120MG) hardware-snap to ~1500 µs on power-up regardless of any PWM we
// send (exhaustively confirmed in ~/pimoroni_servo_fix/). The 35° femur remount
// (Stage 0.2) makes that unavoidable centre the safe init pose. Commanding
// exactly 1500 µs to all 18 pins on activate therefore means *zero* movement
// when the relay closes (servos are physically already there) — and the JTC
// startup-race becomes irrelevant (every JTC freezes the same pose). 1500 µs is
// inside [pulse_min, pulse_max] for all 18 pins of the current calibration, so
// it never trips the Stage-0.5 safety_freeze. See phase_13_stage_0_3_*_plan.md.
constexpr int16_t SERVO_POWER_ON_MID_US = 1500;

// Preset name that selects the built-in "all pins → SERVO_POWER_ON_MID_US"
// init mode (vs. a rad-valued preset loaded from initial_poses.yaml).
constexpr const char * POWER_ON_MID_PRESET = "power_on_mid";

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

    // Phase 13 Stage 0.3: Initial-Pose-Preset. Default ist jetzt
    // "power_on_mid" — der built-in Modus, der alle 18 Pins auf die
    // Servo-Power-On-Mitte (1500 µs) setzt (zero-jerk, race-immun nach dem
    // 35°-Femur-Umbau). Das alte rad-Preset "suspended" (femur=+1.45) ist
    // nach dem Umbau obsolet, bleibt aber als Legacy-rad-Preset in
    // initial_poses.yaml verfügbar. Bei einem rad-Preset-Namen lädt
    // load_initial_pose_preset() weiterhin aus der YAML (Fallback pulse_zero).
    initial_pose_name_ = param_or(
      info_.hardware_parameters, "initial_pose", POWER_ON_MID_PRESET);
    initial_poses_file_ = param_or(
      info_.hardware_parameters, "initial_poses_file", "");
  } catch (const std::exception & e) {
    RCLCPP_FATAL(plugin_logger(), "Failed to parse hardware parameters: %s", e.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(
    plugin_logger(),
    "Config: serial_port=%s, calibration_file=%s, loopback_mode=%s, "
    "initial_pose=%s, initial_poses_file=%s",
    serial_port_path_.c_str(), calibration_file_.c_str(),
    loopback_mode_ ? "true" : "false",
    initial_pose_name_.c_str(),
    initial_poses_file_.empty() ? "<none>" : initial_poses_file_.c_str());

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

  // ─── 5b) Phase 13 Stage 0.3 — Build joint-group enable lists ───────────
  // The relay-gated on_activate sequence (0.3) enables servos in segment
  // groups — femur → relay-on → coxa → tibia — to stage inrush current.
  // Classify each URDF joint by name suffix into its servo-pin group; sort
  // each group ascending by pin so the wire order is deterministic
  // regardless of URDF joint ordering (coxa = lowest pin of each leg-triple,
  // femur = middle, tibia = highest — servo_mapping.yaml convention).
  coxa_pins_.clear();
  femur_pins_.clear();
  tibia_pins_.clear();
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    const std::string & jn = info_.joints[i].name;
    const auto pin = static_cast<uint8_t>(joint_to_output_idx_[i]);
    if (jn.size() >= 11 && jn.compare(jn.size() - 11, 11, "_coxa_joint") == 0) {
      coxa_pins_.push_back(pin);
    } else if (jn.size() >= 12 && jn.compare(jn.size() - 12, 12, "_femur_joint") == 0) {
      femur_pins_.push_back(pin);
    } else if (jn.size() >= 12 && jn.compare(jn.size() - 12, 12, "_tibia_joint") == 0) {
      tibia_pins_.push_back(pin);
    } else {
      // Unknown segment — fold into the last (tibia) group so it still gets
      // enabled. Mirrors load_initial_pose_preset's tolerant classification.
      RCLCPP_WARN(
        plugin_logger(),
        "Joint '%s' does not match leg_<n>_{coxa,femur,tibia}_joint; "
        "enabling it in the tibia (last) group", jn.c_str());
      tibia_pins_.push_back(pin);
    }
  }
  std::sort(coxa_pins_.begin(), coxa_pins_.end());
  std::sort(femur_pins_.begin(), femur_pins_.end());
  std::sort(tibia_pins_.begin(), tibia_pins_.end());
  if (coxa_pins_.size() + femur_pins_.size() + tibia_pins_.size() != NUM_SERVOS) {
    RCLCPP_FATAL(
      plugin_logger(),
      "Joint-group partition incomplete: %zu coxa + %zu femur + %zu tibia "
      "!= %zu servos — check URDF joint names",
      coxa_pins_.size(), femur_pins_.size(), tibia_pins_.size(), NUM_SERVOS);
    return hardware_interface::CallbackReturn::ERROR;
  }

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
    // Phase 13 Stage A: initial_pulse_us_ default = pulse_zero pro Pin
    // (Legacy-Fallback). load_initial_pose_preset() ueberschreibt das
    // gleich pro Pin mit Preset-Werten, wenn YAML + Preset vorhanden.
    initial_pulse_us_[pin] = last_command_pulse_us_[pin];
  }

  // ─── 7b) Phase 13 Stage A — Initial-Pose-Preset laden ──────────────────
  // Fuellt initial_pulse_us_ aus initial_poses.yaml + initial_pose-Param.
  // Best-Effort: bei missing-File / unknown-Preset / OoR pro Pin gibts
  // WARN-Log + Fallback pulse_zero fuer den betroffenen Pin. Plugin
  // startet trotzdem (Legacy-Verhalten als safety net).
  load_initial_pose_preset();

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

    // Stage 0.5 — /hexapod_safety_reset service for recovering from
    // the pulse-out-of-range hard-stop. See safety_freeze_ docstring
    // in hexapod_system.hpp for the freeze semantics.
    safety_reset_service_ = node->create_service<std_srvs::srv::Trigger>(
      "hexapod_safety_reset",
      std::bind(
        &HexapodSystemHardware::handle_safety_reset, this,
        std::placeholders::_1, std::placeholders::_2));
    RCLCPP_INFO(
      plugin_logger(),
      "Stage 0.5: /hexapod_safety_reset service ready");

    // Stage 0.6 — /hexapod_safety_freeze service for external freeze
    // (called by gait_node when IK detects a joint-limit violation).
    safety_freeze_service_ = node->create_service<std_srvs::srv::Trigger>(
      "hexapod_safety_freeze",
      std::bind(
        &HexapodSystemHardware::handle_safety_freeze, this,
        std::placeholders::_1, std::placeholders::_2));
    RCLCPP_INFO(
      plugin_logger(),
      "Stage 0.6: /hexapod_safety_freeze service ready");

    // Phase 13 Stage 0.1 — /hexapod_relay_set: gate the servo V+ rail.
    relay_set_service_ = node->create_service<std_srvs::srv::SetBool>(
      "hexapod_relay_set",
      std::bind(
        &HexapodSystemHardware::handle_relay_set, this,
        std::placeholders::_1, std::placeholders::_2));
    RCLCPP_INFO(
      plugin_logger(),
      "Stage 0.1: /hexapod_relay_set service ready (relay default OFF)");

    // Block F2 — shutdown-switch state from firmware status_flags bit 7.
    // Latched (transient_local, depth 1) so a late/restarting supervisor gets
    // the current value immediately; read() publishes only on change. Created
    // before the loopback early-return so CI/tests see the topic too.
    shutdown_request_pub_ = node->create_publisher<std_msgs::msg::Bool>(
      "/hexapod/shutdown_request", rclcpp::QoS(1).transient_local());
    std_msgs::msg::Bool init_req;
    init_req.data = false;
    shutdown_request_pub_->publish(init_req);
    last_shutdown_request_ = false;
    RCLCPP_INFO(
      plugin_logger(),
      "Block F2: /hexapod/shutdown_request publisher ready (latched, init false)");
  } else {
    RCLCPP_WARN(
      plugin_logger(),
      "Phase 11 Stage B: get_node() returned null in on_configure — "
      "/save_calibration, /hexapod_safety_reset and /hexapod_safety_freeze "
      "services not registered");
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
  // identical (seq_ increments, frames are encoded) but skip wire I/O and
  // every wait. CI stays fast (< 100 ms) while a test can still assert the
  // full frame order. Phase 13 Stage 0.3: the sequence now sends 22 frames —
  // 1 RESET + 1 SET_TARGETS (pre-enable) + 6 ENABLE (femur) + 1 RELAY_CONTROL
  // (on) + 6 ENABLE (coxa) + 6 ENABLE (tibia) + 1 SET_TARGETS (reaffirm).
  const auto stagger = loopback_mode_ ?
    std::chrono::milliseconds(0) :
    std::chrono::milliseconds(50);

  // Phase 13 Stage 0.3 — inter-group settle delays. After the femur group is
  // powered (relay-on) we let the rail current settle before adding the next
  // group, so the staggered groups draw in observable stages. 700 ms ≥ the
  // firmware's 400 ms current-sense warmup gate (re-armed on relay-on in
  // main.cpp set_relay) so the over-current trip is armed AND the IIR filter
  // settled before the coxa group draws. Tunable starting values (plan §4.2);
  // zero in loopback so CI stays fast.
  const auto femur_settle = loopback_mode_ ?
    std::chrono::milliseconds(0) : std::chrono::milliseconds(700);
  const auto coxa_settle = loopback_mode_ ?
    std::chrono::milliseconds(0) : std::chrono::milliseconds(400);

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
        std::lock_guard<std::mutex> lk(serial_write_mutex_);
        serial_port_.write_all(frame.data(), frame.size());
      } catch (const std::exception & e) {
        RCLCPP_FATAL(plugin_logger(),
          "Failed to send %s frame: %s", what, e.what());
        return false;
      }
      return true;
    };

  // Phase 13 Stage 0.3 — enable one joint-segment group with the per-servo
  // host stagger. Returns false (and logs) if a frame fails to send so the
  // caller can abort on_activate cleanly. Each ENABLE_SERVO also kicks the
  // firmware's 200 ms watchdog, keeping it warm across the longer sequence.
  auto enable_group =
    [&](const std::vector<uint8_t> & pins, const char * group) -> bool {
      for (const uint8_t pin : pins) {
        auto frame = encode_enable_servo(seq_.fetch_add(1), pin, /*enable=*/true);
        if (!send_frame(frame, "ENABLE_SERVO")) {
          RCLCPP_FATAL(plugin_logger(),
            "on_activate aborted while enabling the %s group (pin %u)",
            group, static_cast<unsigned>(pin));
          return false;
        }
        std::this_thread::sleep_for(stagger);
      }
      return true;
    };

  // Phase 13 Stage 0.3 — CRITICAL: the firmware watchdog (cfg::WATCHDOG_TIMEOUT_MS
  // = 200 ms) disables all servos AND drops the relay if no valid frame arrives
  // within the timeout. on_activate blocks the controller_manager update thread,
  // so write() does NOT tick during the settle sleeps — a naked 700 ms sleep
  // therefore lets the watchdog trip mid-sequence (observed live 2026-05-30:
  // relay clicks on, then off ~200 ms later). The 50 ms enable stagger keeps the
  // watchdog warm during the enable groups, but the settle gaps need their own
  // heartbeat. This helper breaks a settle into <=100 ms slices, re-sending the
  // (idempotent) initial-pose SET_TARGETS between slices: it holds the exact same
  // target (no movement) while resetting last_valid_frame_time in the firmware.
  // 100 ms << 200 ms gives a 2x safety margin against scheduler jitter.
  auto settle_with_heartbeat =
    [&](std::chrono::milliseconds total, const char * phase) -> bool {
      if (loopback_mode_ || total.count() == 0) {return true;}
      constexpr auto kSlice = std::chrono::milliseconds(100);
      auto remaining = total;
      while (remaining.count() > 0) {
        const auto step = std::min(remaining, kSlice);
        std::this_thread::sleep_for(step);
        remaining -= step;
        // Heartbeat: idempotent SET_TARGETS(initial pose) keeps the watchdog fed
        // without moving anything (target unchanged from the pre-enable frame).
        auto hb = encode_set_targets(seq_.fetch_add(1), initial_pulse_us_);
        if (!send_frame(hb, "SET_TARGETS (settle heartbeat)")) {
          RCLCPP_FATAL(plugin_logger(),
            "on_activate aborted during %s settle heartbeat", phase);
          return false;
        }
      }
      return true;
    };

  // ─── 1) RESET: clear any latched WATCHDOG_TRIPPED from a prior run ────
  // If the plugin previously died without a clean on_deactivate (SIGKILL,
  // crash, USB yanked), the firmware may still have its watchdog flag set.
  // ENABLE_SERVO frames are NACK'd in that state; sending RESET first makes
  // the boot sequence idempotent regardless of how the last run ended.
  // Spec ref: PROTOCOL.md §6 "Recovery".
  //
  // Side effect of RESET in FW (main.cpp): target_pulse_us[i] = pulse_zero[i],
  // current_pulse_us[i] = pulse_zero[i]. Servos are still disabled — no
  // PWM is generated yet.
  {
    auto frame = encode_reset(seq_.fetch_add(1));
    if (!send_frame(frame, "RESET")) {
      return hardware_interface::CallbackReturn::ERROR;
    }
    // Small breather so the firmware can process RESET before the SET_TARGETS
    // arrives. 10 ms is well above the firmware's frame-dispatch cost (~ µs)
    // but invisible to the 50 ms per-servo cadence below.
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
  }

  // ─── 2) SET_TARGETS with initial-pose pulses (BEFORE enable) ───────────
  // Phase 13 Stage A — Frame-Order-Fix: SET_TARGETS muss VOR den ENABLE-
  // Frames kommen, sonst:
  //   - Nach RESET ist target_pulse_us[i] = pulse_zero (T-Pose-Mitte).
  //   - Jeder ENABLE_SERVO aktiviert den Servo, der dann via FW-Soft-Ramp
  //     (cfg::MAX_DELTA_PULSE_PER_TICK_US = 20 µs/tick @ 100 Hz) zur
  //     target_pulse_us laeuft — also Mitte = T-Pose.
  //   - Erst ein NACHTRAEGLICHES SET_TARGETS aendert target_pulse_us. Bis
  //     dahin sind alle Servos schon ~1 s in der horizontalen T-Pose
  //     gegen Schwerkraft (mechanischer Stress).
  //
  // Mit SET_TARGETS davor: target_pulse_us[i] ist sofort auf die Init-Pose-
  // PWMs eingestellt. Im Default-Modus power_on_mid ist das 1500 µs (Servo-
  // Mitte) fuer alle 18 Pins — die Servos stehen beim Power-On physisch schon
  // dort, also rampt beim ENABLE/Relay-On nichts (zero-jerk). Bei einem
  // rad-Preset rampt jeder Servo nach seinem ENABLE zur Preset-PWM.
  //
  // ``initial_pulse_us_`` wurde in on_init gefuellt: power_on_mid → 1500 alle
  // Pins; rad-Preset → aus initial_poses.yaml; missing/unknown → pulse_zero.
  auto init_frame = encode_set_targets(seq_.fetch_add(1), initial_pulse_us_);
  if (!send_frame(init_frame, "SET_TARGETS (initial-pose, pre-enable)")) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  // Phase 13 FW-Fix (2026-05-28): 10 ms Frame-Dispatch-Breather. Die
  // alte 400 ms Wartezeit (fuer FW-Soft-Ramp aufholen) ist nicht mehr
  // noetig, da die Servo2040-FW jetzt bei handle_set_targets() fuer
  // disabled Pins direkt current_pulse_us = target_pulse_us syncen +
  // Pimoroni-state aktualisieren. Beim folgenden ENABLE_SERVO geht
  // Pimoroni direkt zur target-PWM ohne Mitte-Snap.
  // Siehe docs_raspi/phase_13_servo2040_fix.md.
  std::this_thread::sleep_for(std::chrono::milliseconds(10));

  // ─── 3) Enable FEMUR group (relay still OFF → PWM present, no current) ──
  // Phase 13 Stage 0.3 relay-gated sequence. The femurs carry the leg weight
  // in the 35°-up init pose, so they are powered first: enable their PWM
  // while the rail is still dead (no movement, no current), then close the
  // relay. Because every pin's FW target was set to 1500 µs in step 2 (and
  // the FW syncs current=target for disabled pins), no servo ramps on enable.
  if (!enable_group(femur_pins_, "femur")) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 4) RELAY_CONTROL(on): close the V+ rail ───────────────────────────
  // Only the femur pins have live PWM at this point, so closing the relay
  // energises just those 6 servos — all already commanded 1500 µs and
  // physically at the servo power-on centre → they hold, no jump. The other
  // 12 pins have V+ but no PWM (disabled) → limp until enabled below. RESET
  // in step 1 cleared any latched trip, so relay-on is safe here (no
  // relay-on-during-latched-trip hazard; cf. Stage 0.1 review R6).
  {
    auto relay_frame = encode_relay_control(seq_.fetch_add(1), /*on=*/true);
    if (!send_frame(relay_frame, "RELAY_CONTROL(on)")) {
      return hardware_interface::CallbackReturn::ERROR;
    }
  }

  // Let the femur rail current settle (and the FW sense-warmup gate expire)
  // before adding the next group — see femur_settle rationale above. The
  // heartbeat keeps the firmware watchdog fed across the 700 ms gap.
  if (!settle_with_heartbeat(femur_settle, "femur")) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 5) Enable COXA group (rail now live → each draws on enable) ────────
  if (!enable_group(coxa_pins_, "coxa")) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  if (!settle_with_heartbeat(coxa_settle, "coxa")) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 6) Enable TIBIA group ─────────────────────────────────────────────
  if (!enable_group(tibia_pins_, "tibia")) {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // ─── 7) Re-send SET_TARGETS as safety-net + watchdog-kick ──────────────
  // Belt-and-suspenders: ein zweites SET_TARGETS am Ende der Boot-Sequenz
  // stellt sicher dass target_pulse_us konsistent ist und kickt den
  // Watchdog (200 ms Timer) noch einmal. Wichtig falls zwischen on_activate
  // und dem ersten controller_manager write()-Tick > 200 ms vergehen.
  auto reaffirm_frame = encode_set_targets(seq_.fetch_add(1), initial_pulse_us_);
  if (!send_frame(reaffirm_frame, "SET_TARGETS (initial-pose, reaffirm)")) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  // Sync last_command_pulse_us_ damit read() bis zum ersten write()-Tick
  // den Echo-State auf der Initial-Pose haelt (statt veraltetem Wert
  // aus on_init oder vorigem Cycle).
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    last_command_pulse_us_[pin] = initial_pulse_us_[pin];
  }

  // Phase 13 Stage A — hw_command_positions_ + hw_state_positions_ auf die
  // Initial-Pose-rad-Werte syncen. SONST kommt es zur folgenden Race:
  //   1. on_init setzt hw_command_positions_ = 0.0 fuer alle Joints
  //   2. on_activate sendet zwar die Init-Pose-PWMs (1500) an Servo2040, aber das
  //      controller_manager triggert SOFORT die write()/read()-Loop
  //   3. JTC-on_activate (das hw_state_positions_ → hw_command_positions_
  //      als hold-position setzt) passiert NACH Plugin-on_activate
  //   4. In der Race-Zeit dazwischen liest write() hw_command_positions_=0
  //      und konvertiert zu pulse_zero → last_command_pulse_us_ und
  //      damit die Servos werden auf T-Pose gesetzt
  //   5. read() echoed pulse_zero zurueck → /joint_states zeigt 0.0 rad
  //
  // Fix: hw_command_positions_ + hw_state_positions_ aus initial_pulse_us_
  // berechnen → write() haelt die Initial-Pose bis JTC eigene Commands
  // schickt, read() echoed konsistent.
  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    const int output_idx = joint_to_output_idx_[i];
    const double rad = calibration_.pulse_us_to_radians(
      output_idx,
      static_cast<double>(initial_pulse_us_[output_idx]));
    hw_command_positions_[i] = rad;
    hw_state_positions_[i] = rad;
  }

  // Phase 11 Stage B — Lifecycle-State markieren. Set NACH erfolgreichem
  // Activate (alle Frames gesendet), damit Param-Callback erst dann
  // Direction-Updates ablehnt wenn der Active-State wirklich erreicht ist.
  is_active_.store(true);

  RCLCPP_INFO(plugin_logger(),
    "on_activate complete — %s (seq counter advanced by 22)",
    loopback_mode_ ?
    "loopback path traced, no wire frames sent" :
    "relay closed, 18 servos enabled (femur->coxa->tibia staggered), "
    "init pose held");
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

  // Stage 0.1 — fail-safe: drop the relay (depower rail) BEFORE the disable
  // frames so the servos lose torque immediately. Best-effort; the firmware
  // also drops the relay on the watchdog trip that follows a lost connection.
  if (!reader_.died()) {
    auto relay_frame = encode_relay_control(seq_.fetch_add(1), /*on=*/false);
    try {
      std::lock_guard<std::mutex> lk(serial_write_mutex_);
      serial_port_.write_all(relay_frame.data(), relay_frame.size());
      RCLCPP_INFO(plugin_logger(), "on_deactivate: relay OFF frame sent");
    } catch (const std::exception & e) {
      RCLCPP_WARN(plugin_logger(),
        "on_deactivate: failed to send relay-off frame: %s", e.what());
    }
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
      std::lock_guard<std::mutex> lk(serial_write_mutex_);
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

    // ─── Block F2 — surface shutdown-switch state (status_flags bit 7) ───
    // Publish only on change; latched QoS keeps the last value for late
    // subscribers. latest_state() is nullopt until the first STATE_RESPONSE.
    if (auto st = reader_.latest_state()) {
      const bool req =
        (st->status_flags & status_flag::SHUTDOWN_REQUEST) != 0;
      if (req != last_shutdown_request_ && shutdown_request_pub_) {
        std_msgs::msg::Bool m;
        m.data = req;
        shutdown_request_pub_->publish(m);
        last_shutdown_request_ = req;
      }
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
  // Stage 0.5: Plugin is the ONLY layer that guarantees PWM ∈
  // [pulse_min, pulse_max] per pin — firmware stays dumb. If any pin's
  // computed pulse falls outside its calibrated range, we trip the
  // safety_freeze_: all subsequent writes hold last_command_pulse_us_
  // (= current servo position) until the user clears the freeze via
  // /hexapod_safety_reset. Out-of-range always indicates an IK/URDF/cal
  // mismatch and must be investigated — silently clamping would hide
  // the bug and allow servos to be slammed against mech stops.
  //
  // Two-phase pass: first detect any OoR (may flip safety_freeze_),
  // then either write last-known PWMs (frozen) or the freshly computed
  // values (normal). The freshly-computed value in this tick is also
  // clamped to int16 range (defensive cast safety against NaN/inf).
  constexpr double PULSE_FP_TOLERANCE_US = 1.0;  // accept ±1 µs FP-drift
                                                 // at limits as legitimate

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

    // If already frozen, hold current position — don't even compute the
    // new pulse (avoid spamming further OoR-detection on the same tick).
    if (safety_freeze_.load()) {
      continue;
    }

    const double pulse_d = calibration_.radians_to_pulse_us(output_idx, rad);
    const auto & cal_pin = calibration_.at(output_idx);

    // Stage 0.5 — pulse-out-of-range hard-stop.
    const bool out_of_range =
      (pulse_d < static_cast<double>(cal_pin.pulse_min) - PULSE_FP_TOLERANCE_US) ||
      (pulse_d > static_cast<double>(cal_pin.pulse_max) + PULSE_FP_TOLERANCE_US);
    if (out_of_range) {
      safety_freeze_.store(true);
      RCLCPP_ERROR(plugin_logger(),
        "SAFETY FREEZE: joint '%s' (pin %d): rad=%.4f produced pulse=%.1f µs, "
        "outside cal range [%d, %d]. All joints holding last position. "
        "Recover via: ros2 service call /hexapod_safety_reset "
        "std_srvs/srv/Trigger",
        info_.joints[i].name.c_str(), output_idx, rad, pulse_d,
        cal_pin.pulse_min, cal_pin.pulse_max);
      // Don't update last_command_pulse_us_ for this pin — keep the last
      // good value so the wire-frame sent below uses the safe position.
      // Continue the loop to detect other OoR pins in the same tick
      // (more useful log info).
      continue;
    }

    // Defensive clamp to int16 range — radians_to_pulse_us is unbounded
    // in theory (linear extrapolation past joint_lower/joint_upper).
    // After the OoR-check above, pulse_d is within [pulse_min, pulse_max]
    // (typically 500..2500 µs), which is well inside int16 — but the
    // clamp guards against any future change to that invariant and
    // against NaN/inf surviving the isnan check above.
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
    std::lock_guard<std::mutex> lk(serial_write_mutex_);
    serial_port_.write_all(frame.data(), frame.size());
  } catch (const std::exception & e) {
    RCLCPP_ERROR(plugin_logger(),
      "write(): SerialPort write_all failed: %s. Controller will be "
      "deactivated; reconnect logic comes in D.7.", e.what());
    return hardware_interface::return_type::ERROR;
  }

  // ─── Block F2 — periodic GET_STATE poll ──────────────────────────────
  // The firmware sends STATE_RESPONSE (carrying status_flags bit 7) only on
  // request. Without this poll latest_state() never updates and the shutdown-
  // switch bit would never reach read(). Throttled to ~5 Hz; best-effort, so a
  // failed poll only warns (don't deactivate the controller over telemetry).
  constexpr unsigned GET_STATE_POLL_EVERY = 10;  // ~5 Hz at a 50 Hz update rate
  if (++get_state_poll_counter_ >= GET_STATE_POLL_EVERY) {
    get_state_poll_counter_ = 0;
    auto gs = encode_get_state(seq_.fetch_add(1));
    try {
      std::lock_guard<std::mutex> lk(serial_write_mutex_);
      serial_port_.write_all(gs.data(), gs.size());
    } catch (const std::exception & e) {
      RCLCPP_WARN(plugin_logger(),
        "write(): GET_STATE poll failed: %s (shutdown-switch telemetry only)",
        e.what());
    }
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

bool HexapodSystemHardware::is_safety_frozen() const noexcept
{
  return safety_freeze_.load();
}

bool HexapodSystemHardware::clear_safety_freeze() noexcept
{
  return safety_freeze_.exchange(false);
}

bool HexapodSystemHardware::trigger_safety_freeze() noexcept
{
  // Returns the *previous* value via exchange. We invert: true if we
  // actually transitioned false→true (= newly set), false if already
  // true (= idempotent no-op).
  return !safety_freeze_.exchange(true);
}

void HexapodSystemHardware::handle_safety_reset(
  std_srvs::srv::Trigger::Request::ConstSharedPtr /*request*/,
  std_srvs::srv::Trigger::Response::SharedPtr response)
{
  // Idempotent: caller can call this any time. Always succeeds; the
  // message body distinguishes "freeze was active and is now cleared"
  // from "freeze was already clear" so the user gets useful feedback.
  const bool was_frozen = clear_safety_freeze();
  response->success = true;
  if (was_frozen) {
    response->message =
      "safety_freeze cleared — plugin will accept new commands again. "
      "NOTE: gait_node should reconcile to a known pose (e.g. standing) "
      "before resuming walking; that gait-side recovery is Phase-13 work.";
    RCLCPP_WARN(plugin_logger(), "%s", response->message.c_str());
  } else {
    response->message = "safety_freeze was not active — nothing to clear";
    RCLCPP_INFO(plugin_logger(), "%s", response->message.c_str());
  }
}

void HexapodSystemHardware::handle_safety_freeze(
  std_srvs::srv::Trigger::Request::ConstSharedPtr /*request*/,
  std_srvs::srv::Trigger::Response::SharedPtr response)
{
  // Stage 0.6: external freeze trigger, typically called by gait_node
  // when IK detected a joint-limit violation. Idempotent — repeated
  // calls in freeze are no-ops (response message reflects that).
  const bool newly_set = trigger_safety_freeze();
  response->success = true;
  if (newly_set) {
    response->message =
      "safety_freeze activated externally — plugin now holding last "
      "good PWM on all joints. Recover via /hexapod_safety_reset.";
    RCLCPP_ERROR(plugin_logger(), "%s", response->message.c_str());
  } else {
    response->message =
      "safety_freeze was already active — no change";
    RCLCPP_INFO(plugin_logger(), "%s", response->message.c_str());
  }
}

void HexapodSystemHardware::handle_relay_set(
  std_srvs::srv::SetBool::Request::ConstSharedPtr request,
  std_srvs::srv::SetBool::Response::SharedPtr response)
{
  // Phase 13 Stage 0.1 — gate the servo V+ rail via RELAY_CONTROL (GP26).
  const bool on = request->data;
  const char * what = on ? "ON" : "OFF";

  if (loopback_mode_) {
    // No serial port in loopback — report success so service-plumbing unit
    // tests pass without hardware. PTY-based tests exercise the wire frame.
    response->success = true;
    response->message = std::string("loopback: relay ") + what + " (no wire I/O)";
    RCLCPP_INFO(plugin_logger(), "%s", response->message.c_str());
    return;
  }

  if (reader_.died()) {
    response->success = false;
    response->message =
      "reader thread died (USB disconnect?) — relay frame not sent";
    RCLCPP_ERROR(plugin_logger(), "%s", response->message.c_str());
    return;
  }

  auto frame = encode_relay_control(seq_.fetch_add(1), on);
  try {
    std::lock_guard<std::mutex> lk(serial_write_mutex_);
    serial_port_.write_all(frame.data(), frame.size());
  } catch (const std::exception & e) {
    response->success = false;
    response->message = std::string("failed to send relay frame: ") + e.what();
    RCLCPP_ERROR(plugin_logger(), "%s", response->message.c_str());
    return;
  }

  response->success = true;
  response->message = std::string("relay set to ") + what;
  RCLCPP_INFO(plugin_logger(), "Stage 0.1: relay set %s", what);
}

// ═════════════════════════════════════════════════════════════════════════
// Phase 13 Stage A — Initial-Pose-Preset-Loader
// ═════════════════════════════════════════════════════════════════════════
//
// Liest initial_poses.yaml und fuellt initial_pulse_us_ aus dem Preset-
// Eintrag. Best-Effort: bei Fehlern bleibt der jeweilige Pin auf
// pulse_zero (in on_init bereits gesetzt) + WARN-Log. Plugin startet
// trotzdem, on_activate sendet dann die Mischung aus Preset + Fallback.
//
// Aufgerufen in on_init nach Schritt 7 (last_command_pulse_us_-Init).
// Voraussetzungen: calibration_ geladen, set_joint_limits gemacht,
// joint_to_output_idx_ gebaut, info_.joints[i].name verfuegbar.
//
// Joint-Segment-Klassifikation: parsed Suffix von joint.name —
// "leg_<n>_coxa_joint" → coxa, ditto femur/tibia. Joints die nicht
// matchen (Future-Variant, fixed joints) werden ignoriert + WARN.
void HexapodSystemHardware::load_initial_pose_preset()
{
  // Phase 13 Stage 0.3 — built-in "power_on_mid" mode (the default). Command
  // the servo power-on centre (1500 µs) to ALL 18 pins. This is NOT a
  // rad-valued YAML preset — it's the zero-jerk, race-immune init pose (see
  // SERVO_POWER_ON_MID_US docstring): after the 35° femur remount (Stage 0.2)
  // the unavoidable servo centre IS the safe init pose, so no YAML lookup is
  // needed and no initial_poses_file has to be present. on_activate then
  // relay-gates + staggers the enable so this pose comes up without inrush.
  if (initial_pose_name_ == POWER_ON_MID_PRESET) {
    for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
      initial_pulse_us_[pin] = SERVO_POWER_ON_MID_US;
    }
    RCLCPP_INFO(
      plugin_logger(),
      "initial pose 'power_on_mid': all %zu pins set to servo centre %d µs "
      "(zero-jerk init; relay-gated staggered enable in on_activate)",
      NUM_SERVOS, static_cast<int>(SERVO_POWER_ON_MID_US));
    return;
  }

  // Fall 0: kein File-Pfad gegeben → Legacy-Verhalten (alles pulse_zero)
  if (initial_poses_file_.empty()) {
    RCLCPP_WARN(plugin_logger(),
      "initial_poses_file not set — falling back to pulse_zero "
      "(Legacy-T-Pose) for all servos on activate");
    return;
  }

  // Fall 1: YAML-File laden
  YAML::Node root;
  try {
    root = YAML::LoadFile(initial_poses_file_);
  } catch (const YAML::Exception & e) {
    RCLCPP_WARN(plugin_logger(),
      "Failed to load initial_poses_file '%s': %s. "
      "Falling back to pulse_zero (Legacy-T-Pose) for all servos.",
      initial_poses_file_.c_str(), e.what());
    return;
  }

  // Fall 2: poses-Block + Preset-Lookup
  if (!root["poses"] || !root["poses"].IsMap()) {
    RCLCPP_WARN(plugin_logger(),
      "initial_poses_file '%s': missing or invalid top-level 'poses' map. "
      "Falling back to pulse_zero.",
      initial_poses_file_.c_str());
    return;
  }

  YAML::Node preset = root["poses"][initial_pose_name_];
  if (!preset || !preset.IsMap()) {
    RCLCPP_WARN(plugin_logger(),
      "initial_poses_file '%s': preset '%s' not found or invalid. "
      "Available presets are top-level keys under 'poses:'. "
      "Falling back to pulse_zero.",
      initial_poses_file_.c_str(), initial_pose_name_.c_str());
    return;
  }

  YAML::Node joints_block = preset["joints"];
  if (!joints_block || !joints_block.IsMap()) {
    RCLCPP_WARN(plugin_logger(),
      "initial_poses_file '%s': preset '%s' has no 'joints:' block. "
      "Falling back to pulse_zero.",
      initial_poses_file_.c_str(), initial_pose_name_.c_str());
    return;
  }

  // Fall 3: pro Segment-Typ rad-Wert lookuppen
  // Wenn ein Segment-Typ fehlt: Pin bleibt auf pulse_zero, WARN-Log
  // einmal pro Typ (nicht pro Pin, sonst 6x dasselbe Log).
  auto read_segment_rad =
    [&joints_block, this](const char * key, double & out) -> bool {
      if (!joints_block[key]) {
        RCLCPP_WARN(plugin_logger(),
          "initial_pose preset '%s': missing 'joints.%s', using "
          "pulse_zero (Legacy) for all matching servos",
          initial_pose_name_.c_str(), key);
        return false;
      }
      try {
        out = joints_block[key].as<double>();
      } catch (const YAML::Exception & e) {
        RCLCPP_WARN(plugin_logger(),
          "initial_pose preset '%s': 'joints.%s' not a number (%s), "
          "using pulse_zero for all matching servos",
          initial_pose_name_.c_str(), key, e.what());
        return false;
      }
      return true;
    };

  double coxa_rad = 0.0, femur_rad = 0.0, tibia_rad = 0.0;
  bool have_coxa = read_segment_rad("coxa", coxa_rad);
  bool have_femur = read_segment_rad("femur", femur_rad);
  bool have_tibia = read_segment_rad("tibia", tibia_rad);

  // Fall 4: pro URDF-Joint → segment-Typ klassifizieren, rad → PWM,
  // Pre-Validate, in initial_pulse_us_[pin] schreiben
  std::size_t applied = 0;
  std::size_t fallback_oor = 0;
  std::size_t fallback_unknown_segment = 0;

  for (std::size_t i = 0; i < info_.joints.size(); ++i) {
    const std::string & jname = info_.joints[i].name;
    const int output_idx = joint_to_output_idx_[i];

    // Segment-Klassifikation per Suffix
    double rad = 0.0;
    bool have_segment = false;
    if (jname.size() >= 11 && jname.compare(jname.size() - 11, 11, "_coxa_joint") == 0) {
      have_segment = have_coxa;
      rad = coxa_rad;
    } else if (jname.size() >= 12 && jname.compare(jname.size() - 12, 12, "_femur_joint") == 0) {
      have_segment = have_femur;
      rad = femur_rad;
    } else if (jname.size() >= 12 && jname.compare(jname.size() - 12, 12, "_tibia_joint") == 0) {
      have_segment = have_tibia;
      rad = tibia_rad;
    } else {
      RCLCPP_WARN(plugin_logger(),
        "Joint '%s': name does not match leg_<n>_{coxa,femur,tibia}_joint, "
        "using pulse_zero for initial pose", jname.c_str());
      ++fallback_unknown_segment;
      // initial_pulse_us_[output_idx] bleibt pulse_zero (= on_init-Default)
      continue;
    }

    if (!have_segment) {
      // initial_pulse_us_[output_idx] bleibt pulse_zero
      continue;
    }

    // rad → PWM via Calibration
    const double pulse_d = calibration_.radians_to_pulse_us(output_idx, rad);
    const auto & cal_pin = calibration_.at(output_idx);

    // Pre-Validate: PWM ∈ [pulse_min, pulse_max]? Bei OoR: pulse_zero
    // (verhindert Stage-0.5 safety_freeze beim on_activate-Send).
    // Tolerance analog zu write(): ±1 µs FP-drift.
    constexpr double PULSE_FP_TOLERANCE_US = 1.0;
    const bool out_of_range =
      (pulse_d < static_cast<double>(cal_pin.pulse_min) - PULSE_FP_TOLERANCE_US) ||
      (pulse_d > static_cast<double>(cal_pin.pulse_max) + PULSE_FP_TOLERANCE_US);

    if (out_of_range) {
      RCLCPP_WARN(plugin_logger(),
        "initial_pose '%s' for joint '%s' (pin %d): rad=%.4f → pulse=%.1f µs "
        "outside cal range [%d, %d]. Using pulse_zero for this pin. "
        "Adjust the preset's rad value or widen cal range.",
        initial_pose_name_.c_str(), jname.c_str(), output_idx, rad, pulse_d,
        cal_pin.pulse_min, cal_pin.pulse_max);
      ++fallback_oor;
      // initial_pulse_us_[output_idx] bleibt pulse_zero
      continue;
    }

    // Defensive clamp to int16 + round (analog write())
    const double pulse_clamped = std::clamp(
      pulse_d,
      static_cast<double>(INT16_MIN),
      static_cast<double>(INT16_MAX));
    initial_pulse_us_[output_idx] =
      static_cast<int16_t>(std::round(pulse_clamped));
    ++applied;
  }

  RCLCPP_INFO(plugin_logger(),
    "loaded initial pose preset '%s' from %s: %zu/%zu joints applied "
    "(fallback pulse_zero: %zu OoR, %zu unknown-segment)",
    initial_pose_name_.c_str(), initial_poses_file_.c_str(),
    applied, info_.joints.size(), fallback_oor, fallback_unknown_segment);
}

}  // namespace hexapod_hardware

PLUGINLIB_EXPORT_CLASS(
  hexapod_hardware::HexapodSystemHardware, hardware_interface::SystemInterface)
