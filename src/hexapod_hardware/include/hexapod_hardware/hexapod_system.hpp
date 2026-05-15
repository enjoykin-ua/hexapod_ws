// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
#define HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_

#include <array>
#include <memory>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp_lifecycle/state.hpp"

#include "hexapod_hardware/calibration.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

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

private:
  // ─── Configuration (set in on_init from URDF + hardware_parameters) ──────
  std::string serial_port_path_{"/dev/ttyACM0"};
  std::string calibration_file_{};
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
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
