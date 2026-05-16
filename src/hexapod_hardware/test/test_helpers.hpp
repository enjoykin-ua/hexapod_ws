// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Shared test fixtures for hexapod_hardware gtests.
//
// Hosts the synthetic HardwareInfo builder used both by test_hexapod_system
// (Stage D, on_init/on_configure/on_activate/read/write) and by
// test_plugin_registration (Stage E, runtime pluginlib loading). Both
// suites need an identical "looks like the real URDF" HardwareInfo to
// drive on_init through to SUCCESS, so it lives here once.
//
// All entities are inline so the header can be included from multiple
// translation units without ODR violations. Each translation unit that
// includes this header MUST be compiled with -DSOURCE_DIR_FOR_TESTS=...
// (see CMakeLists.txt — `target_compile_definitions(... SOURCE_DIR_FOR_TESTS=...)`).
#ifndef HEXAPOD_HARDWARE_TEST__TEST_HELPERS_HPP_
#define HEXAPOD_HARDWARE_TEST__TEST_HELPERS_HPP_

#include <string>
#include <vector>

#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"

namespace hexapod_hardware_test
{

// Path to the in-tree calibration YAML. Injected via CMake
// target_compile_definitions — same trick test_calibration uses for its
// RealConfigFile test.
inline const std::string YAML_PATH =
  std::string(SOURCE_DIR_FOR_TESTS) + "/config/servo_mapping.yaml";

// The canonical joint name list, in the order Calibration assigns
// servo-pin indices (0..17) — see config/servo_mapping.yaml.
inline const std::vector<std::string> CANONICAL_JOINT_NAMES = {
  "leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint",
  "leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint",
  "leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint",
  "leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint",
  "leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint",
  "leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint",
};

// Build one URDF joint entry: a position command interface with the given
// limits + a position state interface. That matches what xacro emits from
// the <ros2_control> block in hexapod.ros2_control.xacro.
inline hardware_interface::ComponentInfo make_joint(
  const std::string & name, double lower = -1.57, double upper = +1.57)
{
  hardware_interface::ComponentInfo j;
  j.name = name;
  j.type = "joint";

  hardware_interface::InterfaceInfo cmd;
  cmd.name = "position";
  cmd.min = std::to_string(lower);
  cmd.max = std::to_string(upper);
  j.command_interfaces.push_back(cmd);

  hardware_interface::InterfaceInfo state;
  state.name = "position";
  j.state_interfaces.push_back(state);

  return j;
}

// Build a fully-valid HardwareInfo (18 joints in canonical order, all
// 3 hardware_parameters set, calibration_file pointing at the real YAML).
inline hardware_interface::HardwareInfo make_valid_info()
{
  hardware_interface::HardwareInfo info;
  info.name = "HexapodSystem";
  info.type = "system";
  info.hardware_parameters = {
    {"serial_port", "/dev/ttyACM0"},
    {"calibration_file", YAML_PATH},
    {"loopback_mode", "true"},  // tests run without hardware
  };
  for (const auto & name : CANONICAL_JOINT_NAMES) {
    info.joints.push_back(make_joint(name));
  }
  return info;
}

// Wrap a HardwareInfo into the params struct on_init wants.
inline hardware_interface::HardwareComponentInterfaceParams make_params(
  const hardware_interface::HardwareInfo & info)
{
  hardware_interface::HardwareComponentInterfaceParams p;
  p.hardware_info = info;
  // executor stays default-constructed (empty weak_ptr). on_init does
  // not touch the executor; later lifecycle stages might.
  return p;
}

}  // namespace hexapod_hardware_test

#endif  // HEXAPOD_HARDWARE_TEST__TEST_HELPERS_HPP_
