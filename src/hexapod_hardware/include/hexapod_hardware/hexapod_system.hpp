// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
#define HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_

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
  // Filled from URDF / hardware parameters in on_init.
  std::string serial_port_{"/dev/ttyACM0"};
  std::string calibration_file_{};
  bool loopback_mode_{false};

  Calibration calibration_{};

  // Per-joint state vectors. Sized to info_.joints.size() in on_init,
  // expected to equal NUM_SERVOS = 18.
  std::vector<double> hw_state_positions_{};
  std::vector<double> hw_command_positions_{};
  std::vector<int16_t> last_command_pulse_us_{};
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__HEXAPOD_SYSTEM_HPP_
