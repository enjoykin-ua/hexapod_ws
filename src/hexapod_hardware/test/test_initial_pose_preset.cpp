// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Tests for Phase 13 Stage A — Initial-Pose-Preset-Loader.
//
// Strategy: drive the plugin through on_init -> on_configure ->
// on_activate (loopback mode, no serial) and inspect the per-joint
// echo-state after a read() tick. The state is the pulse the plugin
// actually committed during on_activate (Stage A: initial_pulse_us_),
// converted back to radians via Calibration::pulse_us_to_radians.
//
// Test matrix (Phase 13 Stage 0.3: default is now power_on_mid):
//   Default mode:        power_on_mid -> all 18 pins at 1500 us (servo centre)
//   suspended preset:    legacy rad-preset -> femurs ~ 1.45 rad, others ~ 0
//   missing YAML file:   all joints ~ 0 rad (pulse_zero fallback)
//   unknown preset name: fallback pulse_zero
//   explicit pulse_zero: 0 rad (legacy path)

#include <gtest/gtest.h>

#include <cmath>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "rclcpp/rclcpp.hpp"

#include "hexapod_hardware/hexapod_system.hpp"
#include "hexapod_hardware/calibration.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

#include "test_helpers.hpp"

using hexapod_hardware::HexapodSystemHardware;
using hexapod_hardware::NUM_SERVOS;

using hexapod_hardware_test::make_joint;
using hexapod_hardware_test::make_valid_info;
using hexapod_hardware_test::make_params;
using hexapod_hardware_test::CANONICAL_JOINT_NAMES;
using hexapod_hardware_test::YAML_PATH;

namespace
{

inline const std::string INITIAL_POSES_YAML_PATH =
  std::string(SOURCE_DIR_FOR_TESTS) + "/config/initial_poses.yaml";

// Build a HardwareInfo identical to make_valid_info() but with the
// Stage-A hardware_parameters set. Preset-name + file-path are passed
// in so tests can exercise valid / missing / unknown-name cases.
hardware_interface::HardwareInfo make_info_with_initial_pose(
  const std::string & preset_name,
  const std::string & poses_file_path)
{
  auto info = make_valid_info();
  info.hardware_parameters["initial_pose"] = preset_name;
  info.hardware_parameters["initial_poses_file"] = poses_file_path;
  return info;
}

// Drive the plugin through full activate path in loopback. Returns the
// per-joint echo state after a single read() tick — these are the rad
// values the plugin will report on /joint_states once the controller
// is spawned. Order matches CANONICAL_JOINT_NAMES.
std::vector<double> activate_and_read_state(
  const hardware_interface::HardwareInfo & info)
{
  HexapodSystemHardware plugin;
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  EXPECT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State()),
    hardware_interface::CallbackReturn::SUCCESS);
  EXPECT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State()),
    hardware_interface::CallbackReturn::SUCCESS);

  // Wire up the state interfaces so we can read back the echo state.
  // export_state_interfaces returns handles into the plugin's internal
  // vectors; we just need the count, the data lives in those internal
  // vectors which read() updates.
  auto state_ifs = plugin.export_state_interfaces();
  EXPECT_EQ(state_ifs.size(), static_cast<std::size_t>(NUM_SERVOS));

  EXPECT_EQ(
    plugin.read(rclcpp::Time(0, 0), rclcpp::Duration::from_seconds(0.02)),
    hardware_interface::return_type::OK);

  std::vector<double> state(NUM_SERVOS, 0.0);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    state[i] = state_ifs[i].get_optional().value();
  }
  return state;
}

// Indices in CANONICAL_JOINT_NAMES order. Per leg n (1..6):
//   coxa  → (n-1)*3 + 0
//   femur → (n-1)*3 + 1
//   tibia → (n-1)*3 + 2
constexpr std::size_t coxa_idx(int leg) {return (leg - 1) * 3 + 0;}
constexpr std::size_t femur_idx(int leg) {return (leg - 1) * 3 + 1;}
constexpr std::size_t tibia_idx(int leg) {return (leg - 1) * 3 + 2;}

// Quantisation tolerance: pulses are int16, so the roundtrip
// rad -> int16(pulse) -> rad accumulates ~ 1 µs of error per
// conversion. With slope ~ (pulse_zero - pulse_min)/|joint_lower| ≈
// 600 µs/rad/2 = 300 µs/rad, 1 µs ≈ 3 mrad. We allow 0.01 rad
// (~0.6°) which is generous.
constexpr double TOLERANCE_RAD = 0.01;

// Expected per-pin echo-rad for the default power_on_mid mode, which
// commands SERVO_POWER_ON_MID_US (1500 us) to every pin. Computed with the
// SAME calibration + uniform +/-1.57 limits the plugin uses
// (servo_mapping.yaml + make_joint), so the comparison is exact up to int16
// quantisation.
inline std::vector<double> power_on_mid_expected_rads()
{
  hexapod_hardware::Calibration cal;
  cal.load_from_file(YAML_PATH);
  for (const auto & name : CANONICAL_JOINT_NAMES) {
    cal.set_joint_limits(name, -1.57, 1.57);
  }
  std::vector<double> rads(NUM_SERVOS, 0.0);
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    rads[pin] = cal.pulse_us_to_radians(static_cast<int>(pin), 1500.0);
  }
  return rads;
}

}  // namespace

// ============================================================================
// T1 + T2 — suspended preset loads + applies
// ============================================================================

TEST(InitialPosePreset, SuspendedPresetLoadsAndApplies)
{
  auto info = make_info_with_initial_pose(
    "suspended", INITIAL_POSES_YAML_PATH);
  auto state = activate_and_read_state(info);

  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_NEAR(state[coxa_idx(leg)], 0.0, TOLERANCE_RAD)
      << "leg " << leg << " coxa expected ~0 rad";
    EXPECT_NEAR(state[femur_idx(leg)], 1.45, TOLERANCE_RAD)
      << "leg " << leg << " femur expected ~1.45 rad (suspended)";
    EXPECT_NEAR(state[tibia_idx(leg)], 0.0, TOLERANCE_RAD)
      << "leg " << leg << " tibia expected ~0 rad";
  }
}

// ============================================================================
// T7 — missing YAML file → fallback pulse_zero (= 0 rad)
// ============================================================================

TEST(InitialPosePreset, MissingYamlFallsBackToPulseZero)
{
  auto info = make_info_with_initial_pose(
    "suspended", "/nonexistent/path/initial_poses.yaml");
  auto state = activate_and_read_state(info);

  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_NEAR(state[coxa_idx(leg)], 0.0, TOLERANCE_RAD);
    EXPECT_NEAR(state[femur_idx(leg)], 0.0, TOLERANCE_RAD)
      << "leg " << leg << " femur should fall back to 0 rad "
      << "(pulse_zero) when YAML is missing";
    EXPECT_NEAR(state[tibia_idx(leg)], 0.0, TOLERANCE_RAD);
  }
}

// ============================================================================
// Unknown preset name → fallback pulse_zero
// ============================================================================

TEST(InitialPosePreset, UnknownPresetFallsBackToPulseZero)
{
  auto info = make_info_with_initial_pose(
    "does_not_exist", INITIAL_POSES_YAML_PATH);
  auto state = activate_and_read_state(info);

  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_NEAR(state[femur_idx(leg)], 0.0, TOLERANCE_RAD)
      << "unknown preset must fall back to pulse_zero";
  }
}

// ============================================================================
// Explicit "pulse_zero" preset → Legacy 0-rad-T-pose
// ============================================================================

TEST(InitialPosePreset, PulseZeroPresetGivesZeroRadians)
{
  auto info = make_info_with_initial_pose(
    "pulse_zero", INITIAL_POSES_YAML_PATH);
  auto state = activate_and_read_state(info);

  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_NEAR(state[coxa_idx(leg)], 0.0, TOLERANCE_RAD);
    EXPECT_NEAR(state[femur_idx(leg)], 0.0, TOLERANCE_RAD);
    EXPECT_NEAR(state[tibia_idx(leg)], 0.0, TOLERANCE_RAD);
  }
}

// ============================================================================
// Default mode (no initial_pose param) -> power_on_mid: all 18 pins at the
// servo centre 1500 us. Phase 13 Stage 0.3 default; replaced the old
// "suspended" rad-preset. make_valid_info() sets no initial_pose param.
// ============================================================================

TEST(InitialPosePreset, DefaultModeIsPowerOnMid)
{
  auto info = make_valid_info();  // no initial_pose -> default power_on_mid
  auto state = activate_and_read_state(info);
  const auto expected = power_on_mid_expected_rads();

  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    EXPECT_NEAR(state[pin], expected[pin], 1e-6)
      << "pin " << pin << ": power_on_mid must echo pulse_us_to_radians(1500)";
  }
  // Sanity: the femurs are NOT at rad=0 anymore (1500 us != femur pulse_zero
  // after the 35-degree remount) -- guards against a silent regress to
  // pulse_zero.
  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_GT(std::abs(state[femur_idx(leg)]), 0.1)
      << "leg " << leg << " femur should be clearly off-zero at 1500 us";
  }
}

// ============================================================================
// Explicit initial_pose=power_on_mid needs NO initial_poses_file (built-in
// mode, not a YAML rad-preset).
// ============================================================================

TEST(InitialPosePreset, PowerOnMidExplicitNeedsNoYaml)
{
  auto info = make_valid_info();
  info.hardware_parameters["initial_pose"] = "power_on_mid";
  // deliberately no initial_poses_file set
  auto state = activate_and_read_state(info);
  const auto expected = power_on_mid_expected_rads();

  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    EXPECT_NEAR(state[pin], expected[pin], 1e-6) << "pin " << pin;
  }
}

// ============================================================================
// Regression test for the on_activate write()-race bug (2026-05-28):
//
// The original Stage-A code synced last_command_pulse_us_ but left
// hw_command_positions_ at 0.0 (init default). The first write()-tick
// after Plugin-on_activate (which runs BEFORE JTC-on_activate sets its
// hold-position) then read hw_command_positions_=0.0, converted to
// pulse_zero, and overwrote last_command_pulse_us_ — the suspended
// PWMs the plugin had just committed were lost in the very next tick.
// User saw /joint_states echo all 0.0 rad and the legs in T-pose.
//
// Fix: on_activate also seeds hw_command_positions_ + hw_state_positions_
// from initial_pulse_us_. This test calls write() once after activate
// and verifies last_command_pulse_us_ is still on the suspended PWMs
// (i.e. not regressed to pulse_zero).
// ============================================================================

TEST(InitialPosePreset, WriteAfterActivateKeepsSuspendedPulses)
{
  auto info = make_info_with_initial_pose(
    "suspended", INITIAL_POSES_YAML_PATH);

  HexapodSystemHardware plugin;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State()),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State()),
    hardware_interface::CallbackReturn::SUCCESS);

  // Simulate the controller_manager RT-loop: write() before JTC has
  // set its hold-position. Plugin must NOT regress to pulse_zero here.
  ASSERT_EQ(
    plugin.write(rclcpp::Time(0, 0), rclcpp::Duration::from_seconds(0.02)),
    hardware_interface::return_type::OK);
  ASSERT_EQ(
    plugin.read(rclcpp::Time(0, 0), rclcpp::Duration::from_seconds(0.02)),
    hardware_interface::return_type::OK);

  auto state_ifs = plugin.export_state_interfaces();
  std::vector<double> state(NUM_SERVOS, 0.0);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    state[i] = state_ifs[i].get_optional().value();
  }

  // Should still be at suspended after a full write+read cycle.
  for (int leg = 1; leg <= 6; ++leg) {
    EXPECT_NEAR(state[femur_idx(leg)], 1.45, TOLERANCE_RAD)
      << "leg " << leg << " femur: write() must not regress "
      << "suspended PWM to pulse_zero before JTC sets hold-position";
    EXPECT_NEAR(state[coxa_idx(leg)], 0.0, TOLERANCE_RAD);
    EXPECT_NEAR(state[tibia_idx(leg)], 0.0, TOLERANCE_RAD);
  }
}
