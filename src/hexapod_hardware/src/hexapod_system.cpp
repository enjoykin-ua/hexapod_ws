// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/hexapod_system.hpp"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <exception>
#include <stdexcept>
#include <string>

#include <pluginlib/class_list_macros.hpp>
#include <rclcpp/rclcpp.hpp>

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

  RCLCPP_INFO(
    plugin_logger(), "on_init complete — %zu joints mapped to 18 servo pins, "
    "calibration loaded from %s",
    info_.joints.size(), calibration_file_.c_str());
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_configure(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  // Stage D.4 fills this in (serial port open, reader thread start).
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  // Stage D.5 fills this in (RESET + 18× ENABLE_SERVO stagger + neutral SET_TARGETS).
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  // Stage D.5 fills this in (DISABLE_SERVO for all).
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
  // Stage D.6 fills this in with the proper echo via calibration_.
  // Until then, naive 1:1 echo (which only works while D.6 isn't using
  // pulse-µs conversion yet).
  for (std::size_t i = 0; i < hw_state_positions_.size(); ++i) {
    hw_state_positions_[i] = hw_command_positions_[i];
  }
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type HexapodSystemHardware::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  // Stage D.6 fills this in.
  return hardware_interface::return_type::OK;
}

}  // namespace hexapod_hardware

PLUGINLIB_EXPORT_CLASS(
  hexapod_hardware::HexapodSystemHardware, hardware_interface::SystemInterface)
