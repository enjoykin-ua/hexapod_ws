// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#include "hexapod_hardware/hexapod_system.hpp"

#include <pluginlib/class_list_macros.hpp>

namespace hexapod_hardware
{

// Stage D fills these in. Stubs return SUCCESS / OK so the plugin can
// be loaded and exercised end-to-end once stage E wires up the pluginlib
// export.

hardware_interface::CallbackReturn HexapodSystemHardware::on_init(
  const hardware_interface::HardwareComponentInterfaceParams & params)
{
  if (hardware_interface::SystemInterface::on_init(params) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }
  hw_state_positions_.assign(info_.joints.size(), 0.0);
  hw_command_positions_.assign(info_.joints.size(), 0.0);
  last_command_pulse_us_.assign(info_.joints.size(), 1500);
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_configure(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn HexapodSystemHardware::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
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
  // Echo-state stub: reflect last command back as state.
  for (std::size_t i = 0; i < hw_state_positions_.size(); ++i) {
    hw_state_positions_[i] = hw_command_positions_[i];
  }
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type HexapodSystemHardware::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  return hardware_interface::return_type::OK;
}

}  // namespace hexapod_hardware

PLUGINLIB_EXPORT_CLASS(
  hexapod_hardware::HexapodSystemHardware, hardware_interface::SystemInterface)
