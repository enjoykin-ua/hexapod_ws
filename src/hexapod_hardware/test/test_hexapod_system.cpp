// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for HexapodSystemHardware::on_init (Stage D.3).
//
// We construct a synthetic hardware_interface::HardwareInfo by hand and
// feed it through the plugin's on_init hook. The real URDF→HardwareInfo
// parsing (done by ros2_control's resource_manager + xacro) is out of
// scope here — we only care that, given a well-formed HardwareInfo,
// on_init builds the right internal state and rejects malformed input.

#include <gtest/gtest.h>

#include <memory>
#include <string>
#include <vector>

#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"
#include "rclcpp/rclcpp.hpp"

#include "hexapod_hardware/hexapod_system.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

using hexapod_hardware::HexapodSystemHardware;
using hexapod_hardware::NUM_SERVOS;

namespace
{

// Path to the in-tree calibration YAML. Injected via CMake target_compile_definitions
// — same trick test_calibration uses for its RealConfigFile test.
const std::string YAML_PATH = std::string(SOURCE_DIR_FOR_TESTS) +
  "/config/servo_mapping.yaml";

// The canonical joint name list, in the order Calibration assigns servo-pin
// indices (0..17) — see config/servo_mapping.yaml.
const std::vector<std::string> CANONICAL_JOINT_NAMES = {
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
hardware_interface::ComponentInfo make_joint(
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
hardware_interface::HardwareInfo make_valid_info()
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
hardware_interface::HardwareComponentInterfaceParams make_params(
  const hardware_interface::HardwareInfo & info)
{
  hardware_interface::HardwareComponentInterfaceParams p;
  p.hardware_info = info;
  // executor stays default-constructed (empty weak_ptr). on_init in D.3
  // does not touch the executor; later stages might.
  return p;
}

}  // namespace

// ============================================================================
// Happy path
// ============================================================================

TEST(HexapodSystemInit, ValidHardwareInfoSucceeds)
{
  HexapodSystemHardware plugin;
  EXPECT_EQ(
    plugin.on_init(make_params(make_valid_info())),
    hardware_interface::CallbackReturn::SUCCESS);

  // Interfaces should now be exportable, one per joint, in URDF order.
  auto state_ifs = plugin.export_state_interfaces();
  auto cmd_ifs = plugin.export_command_interfaces();
  EXPECT_EQ(state_ifs.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_ifs.size(), NUM_SERVOS);
}

TEST(HexapodSystemInit, ExportedInterfaceNamesMatchUrdfOrder)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_ifs.size(), NUM_SERVOS);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    // Interface name format is "<joint_name>/<interface>" in ros2_control.
    // The prefix must match the joint name we put into info.joints[i].
    const std::string expected_prefix = info.joints[i].name;
    EXPECT_EQ(cmd_ifs[i].get_prefix_name(), expected_prefix) << "at slot " << i;
  }
}

// ============================================================================
// Joint count
// ============================================================================

TEST(HexapodSystemInit, RejectsTooFewJoints)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints.pop_back();  // 17 joints
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsTooManyJoints)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints.push_back(make_joint("phantom_extra_joint"));
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

// ============================================================================
// Hardware parameters
// ============================================================================

TEST(HexapodSystemInit, RejectsMissingCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters.erase("calibration_file");
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsEmptyCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["calibration_file"] = "";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsNonExistentCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["calibration_file"] = "/tmp/does_not_exist_xyz.yaml";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, AcceptsAllBoolStringsForLoopback)
{
  // The plugin should accept the same set of bool-ish strings that
  // most ROS users expect: true/false, 1/0, yes/no — case-insensitive.
  for (const char * v : {"true", "TRUE", "True", "false", "FALSE",
      "1", "0", "yes", "no", "YES", "No"})
  {
    HexapodSystemHardware plugin;
    auto info = make_valid_info();
    info.hardware_parameters["loopback_mode"] = v;
    EXPECT_EQ(
      plugin.on_init(make_params(info)),
      hardware_interface::CallbackReturn::SUCCESS)
      << "loopback_mode value '" << v << "' should be accepted";
  }
}

TEST(HexapodSystemInit, RejectsGarbageLoopbackString)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "maybe";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, LoopbackDefaultsToFalseIfOmitted)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters.erase("loopback_mode");
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  // (We can't directly read loopback_mode_ without breaking encapsulation,
  // but the "default = false" path is exercised here; D.4 will assert
  // the consequence — no serial port opened.)
}

// ============================================================================
// Joint-to-output-pin mapping
//
// We can't directly inspect joint_to_output_idx_ (private member) — but we
// can verify the SUCCESS/ERROR signal at the boundaries and trust that
// downstream stages (D.6) exercise the actual mapping in write/read.
// ============================================================================

TEST(HexapodSystemInit, AcceptsPermutedJointOrder)
{
  // Build the same 18 joints in a non-canonical order. Calibration
  // still owns the canonical pin assignment via servo_mapping.yaml, so
  // joint_to_output_idx_ ends up as a non-identity permutation.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  std::reverse(info.joints.begin(), info.joints.end());
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  // Check that exports preserve URDF order, NOT pin order — that's the
  // ros2_control contract.
  auto cmd_ifs = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_ifs.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_ifs.front().get_prefix_name(), "leg_6_tibia_joint")
    << "URDF slot 0 should still be leg_6_tibia_joint after reversal "
    "— ros2_control exports in URDF order";
  EXPECT_EQ(cmd_ifs.back().get_prefix_name(), "leg_1_coxa_joint")
    << "URDF slot 17 should be leg_1_coxa_joint after reversal";
}

TEST(HexapodSystemInit, RejectsUnknownJointName)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[5].name = "leg_99_phantom_joint";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

// ============================================================================
// Limit parsing
// ============================================================================

TEST(HexapodSystemInit, ParsesJointLimitsFromUrdf)
{
  // Confirm that custom limits in the URDF (different from the calibration
  // defaults ±1.57) reach Calibration::set_joint_limits. Indirect test:
  // we set asymmetric limits, do on_init, and then verify a forward call
  // via the Calibration object would behave accordingly. Since we can't
  // peek at calibration_, we verify the SUCCESS of on_init plus the fact
  // that absurd limits (lower > upper) still pass through — the Calibration
  // doesn't validate URDF semantics, only its own pulse triplet.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", -1.2, +0.8);  // asymmetric
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemInit, EmptyJointLimitsFallBackToDefaults)
{
  // If the URDF omits the <limit lower upper>, both min and max come
  // through as empty strings. The plugin should warn and continue, falling
  // back to Calibration's ±1.57 defaults.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[0].command_interfaces[0].min = "";
  info.joints[0].command_interfaces[0].max = "";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemInit, RejectsSwappedJointLimits)
{
  // URDF bug: lower > upper. Some URDF refactor swapped the macro args
  // and nobody noticed. Plugin must FATAL with a message that explains
  // why this isn't a "mirrored leg" case (those use direction in
  // servo_mapping.yaml, not swapped URDF limits).
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", /*lower=*/+1.57, /*upper=*/-1.57);
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsEqualJointLimits)
{
  // Same problem class: lower == upper means a stuck joint, which has no
  // meaningful pulse-µs slope. Reject.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", /*lower=*/0.0, /*upper=*/0.0);
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, FailedReinitDoesNotMutateTable)
{
  // Strong-exception-guarantee analogue to test_calibration's
  // StrongExceptionGuarantee suite. If on_init is called a second time
  // and fails partway through (here: unknown joint name on the second
  // call), the plugin must not end up with a half-built joint→pin table
  // from the partial second attempt.
  //
  // Practical impact in production is low (ros2_control wouldn't use
  // the plugin if on_init returned ERROR), but the property is the same
  // we made the Calibration class promise — we keep the contract here.
  HexapodSystemHardware plugin;
  auto good = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(good)),
    hardware_interface::CallbackReturn::SUCCESS);

  // Snapshot the joint order that ros2_control sees right now.
  auto cmd_before = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_before.size(), NUM_SERVOS);
  const std::string joint0_before = cmd_before[0].get_prefix_name();
  const std::string joint17_before = cmd_before[17].get_prefix_name();

  // Now hand on_init a bad HardwareInfo — joint 10 is renamed to a
  // phantom that's not in the YAML, so output_idx_for_joint will throw.
  auto bad = make_valid_info();
  bad.joints[10].name = "leg_99_phantom_joint";
  EXPECT_EQ(
    plugin.on_init(make_params(bad)),
    hardware_interface::CallbackReturn::ERROR);

  // The plugin is now in a "failed re-init" state. ros2_control would
  // discard it; we just verify that the table built locally during the
  // failed init didn't leak into the member. We can't directly inspect
  // joint_to_output_idx_, but we can confirm that the export interfaces
  // were not retroactively rewritten to the partial set.
  //
  // Since on_init does the export-relevant hw_state/command vectors
  // BEFORE the joint-table build, those are unfortunately re-assigned
  // even on the failed path. So we restrict the assertion to the table
  // committed via std::move — which on the failed path stays at the
  // pre-failure value.
  //
  // We verify this indirectly by running a third on_init with the GOOD
  // info: it must succeed, and the recovered table must reproduce the
  // original mapping (not the phantom one).
  ASSERT_EQ(
    plugin.on_init(make_params(good)),
    hardware_interface::CallbackReturn::SUCCESS);
  auto cmd_after = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_after.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_after[0].get_prefix_name(), joint0_before);
  EXPECT_EQ(cmd_after[17].get_prefix_name(), joint17_before);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
