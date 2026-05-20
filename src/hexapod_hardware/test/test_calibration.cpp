// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for the servo-mapping loader and rad↔pulse-µs conversion.
// Tests use the piecewise-linear three-point scheme described in
// docs_raspi/phase_9_progress.md "Design-Entscheidung Option C".

#include <gtest/gtest.h>

#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include "hexapod_hardware/calibration.hpp"

using hexapod_hardware::Calibration;
using hexapod_hardware::NUM_SERVOS;

namespace
{

// Minimal-valid YAML for tests. 18 entries are required.
const char * MINIMAL_YAML =
  R"yaml(
defaults:
  pulse_min:  500
  pulse_max:  2500
  pulse_zero: 1500
  direction:  1
servo2040_output_to_joint:
  0:  { joint: leg_1_coxa_joint  }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";

// Apply the standard hexapod URDF limits (docs/00_conventions.md §11.4) to
// all joints in the calibration. Coxa/femur ±1.57, tibia ±1.5 — but for
// most tests we just use ±1.57 everywhere for simplicity.
void apply_symmetric_limits(Calibration & c, double lower = -1.57, double upper = +1.57)
{
  for (int leg = 1; leg <= 6; ++leg) {
    for (const char * seg : {"coxa", "femur", "tibia"}) {
      const std::string joint = "leg_" + std::to_string(leg) + "_" + seg + "_joint";
      c.set_joint_limits(joint, lower, upper);
    }
  }
}

}  // namespace

// ============================================================================
// YAML Loader — happy path
// ============================================================================

TEST(YamlLoader, MinimalYamlLoads)
{
  Calibration c;
  EXPECT_NO_THROW(c.load_from_string(MINIMAL_YAML));

  // All 18 joints present and mapped.
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_FALSE(c.at(i).joint_name.empty());
  }
}

TEST(YamlLoader, JointNameToIndexLookup)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);

  EXPECT_EQ(c.output_idx_for_joint("leg_1_coxa_joint"), 0);
  EXPECT_EQ(c.output_idx_for_joint("leg_1_femur_joint"), 1);
  EXPECT_EQ(c.output_idx_for_joint("leg_6_tibia_joint"), 17);
  EXPECT_THROW(c.output_idx_for_joint("nonexistent_joint"), std::out_of_range);
}

TEST(YamlLoader, DefaultsFillMissingFields)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);

  // Every entry in MINIMAL_YAML omits per-servo overrides, so all should
  // inherit the defaults block.
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_EQ(c.at(i).pulse_min, 500);
    EXPECT_EQ(c.at(i).pulse_zero, 1500);
    EXPECT_EQ(c.at(i).pulse_max, 2500);
    EXPECT_EQ(c.at(i).direction, 1);
  }
}

TEST(YamlLoader, PerServoOverrideTakesPrecedence)
{
  // One joint overrides every field; the rest stay at defaults.
  const char * yaml =
    R"yaml(
defaults:
  pulse_min:  500
  pulse_max:  2500
  pulse_zero: 1500
  direction:  1
servo2040_output_to_joint:
  0: { joint: leg_1_coxa_joint, pulse_min: 700, pulse_zero: 1450, pulse_max: 2300, direction: -1 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  c.load_from_string(yaml);
  EXPECT_EQ(c.at(0).pulse_min, 700);
  EXPECT_EQ(c.at(0).pulse_zero, 1450);
  EXPECT_EQ(c.at(0).pulse_max, 2300);
  EXPECT_EQ(c.at(0).direction, -1);

  EXPECT_EQ(c.at(1).pulse_min, 500);  // still default
  EXPECT_EQ(c.at(1).direction, 1);
}

// ============================================================================
// YAML Loader — error path
// ============================================================================

TEST(YamlLoader, RejectsGarbageInput)
{
  Calibration c;
  EXPECT_THROW(c.load_from_string("not: { valid: yaml"), std::runtime_error);
}

TEST(YamlLoader, RejectsMissingServoMap)
{
  Calibration c;
  EXPECT_THROW(c.load_from_string("defaults: { pulse_min: 500 }"), std::runtime_error);
}

TEST(YamlLoader, RejectsMissingJointName)
{
  // Servo 0 has no `joint:` key — schema violation.
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { pulse_min: 600 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  EXPECT_THROW(c.load_from_string(yaml), std::runtime_error);
}

TEST(YamlLoader, RejectsMissingServoEntry)
{
  // Only 17 entries instead of 18 — missing index 17.
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { joint: leg_1_coxa_joint  }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
)yaml";
  Calibration c;
  EXPECT_THROW(c.load_from_string(yaml), std::runtime_error);
}

TEST(YamlLoader, RejectsInvalidDirection)
{
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 7 }
servo2040_output_to_joint:
  0:  { joint: leg_1_coxa_joint  }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  EXPECT_THROW(c.load_from_string(yaml), std::runtime_error);
}

TEST(YamlLoader, RejectsDegeneratePulseTriplet)
{
  // pulse_min > pulse_zero — degenerate, would yield negative slope.
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 1800, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { joint: leg_1_coxa_joint  }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  EXPECT_THROW(c.load_from_string(yaml), std::runtime_error);
}

TEST(YamlLoader, FileNotFoundThrows)
{
  Calibration c;
  EXPECT_THROW(c.load_from_file("/tmp/this_file_does_not_exist_42.yaml"),
    std::runtime_error);
}

TEST(YamlLoader, RejectsTypeMismatchAsRuntimeError)
{
  // Verifies the contract documented in the header: schema violations
  // (here: pulse_min is a string instead of int) come out as
  // std::runtime_error, not as some yaml-cpp-specific type. yaml-cpp
  // currently has YAML::Exception : public std::runtime_error so this
  // works transparently — this test catches that contract breaking if
  // yaml-cpp is upgraded and changes its exception hierarchy.
  const char * yaml =
    R"yaml(
defaults: { pulse_min: "not_a_number", pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { joint: leg_1_coxa_joint  }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  EXPECT_THROW(c.load_from_string(yaml), std::runtime_error);
}

// ============================================================================
// Strong exception guarantee — a failed load must not modify object state
// ============================================================================

TEST(StrongExceptionGuarantee, FailedLoadDoesNotMutateState)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  // After the successful load, we know exactly what state to expect.
  ASSERT_EQ(c.at(0).joint_name, "leg_1_coxa_joint");
  ASSERT_EQ(c.at(15).joint_name, "leg_6_coxa_joint");
  ASSERT_EQ(c.output_idx_for_joint("leg_6_tibia_joint"), 17);
  // Apply URDF-style limits so we can verify those survive too.
  apply_symmetric_limits(c, -1.0, +1.0);
  ASSERT_DOUBLE_EQ(c.at(0).joint_lower, -1.0);

  // Now attempt to load a YAML that fails partway through: only 10
  // entries instead of 18, plus different joint names so we can detect
  // any leak of partial state.
  const char * broken =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { joint: phantom_joint_0 }
  1:  { joint: phantom_joint_1 }
  2:  { joint: phantom_joint_2 }
  3:  { joint: phantom_joint_3 }
  4:  { joint: phantom_joint_4 }
  5:  { joint: phantom_joint_5 }
  6:  { joint: phantom_joint_6 }
  7:  { joint: phantom_joint_7 }
  8:  { joint: phantom_joint_8 }
  9:  { joint: phantom_joint_9 }
)yaml";
  EXPECT_THROW(c.load_from_string(broken), std::runtime_error);

  // Object state must be exactly what it was before the failed load.
  EXPECT_EQ(c.at(0).joint_name, "leg_1_coxa_joint") << "index 0 leaked";
  EXPECT_EQ(c.at(5).joint_name, "leg_2_tibia_joint") << "index 5 leaked";
  EXPECT_EQ(c.at(15).joint_name, "leg_6_coxa_joint") << "index 15 leaked";
  EXPECT_EQ(c.output_idx_for_joint("leg_6_tibia_joint"), 17);
  EXPECT_DOUBLE_EQ(c.at(0).joint_lower, -1.0) << "joint_limits leaked";
  // And the phantom names must NOT have leaked into the lookup map.
  EXPECT_THROW(c.output_idx_for_joint("phantom_joint_0"), std::out_of_range);
  EXPECT_THROW(c.output_idx_for_joint("phantom_joint_9"), std::out_of_range);
}

TEST(StrongExceptionGuarantee, FailedTypeMismatchDoesNotMutateState)
{
  // Same idea but the failure happens via a YAML type-mismatch deep in
  // the loop rather than via missing-key validation.
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  ASSERT_EQ(c.at(0).joint_name, "leg_1_coxa_joint");

  const char * broken =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0:  { joint: phantom_joint_0, pulse_min: "garbage" }
  1:  { joint: phantom_joint_1 }
  2:  { joint: phantom_joint_2 }
  3:  { joint: phantom_joint_3 }
  4:  { joint: phantom_joint_4 }
  5:  { joint: phantom_joint_5 }
  6:  { joint: phantom_joint_6 }
  7:  { joint: phantom_joint_7 }
  8:  { joint: phantom_joint_8 }
  9:  { joint: phantom_joint_9 }
  10: { joint: phantom_joint_10 }
  11: { joint: phantom_joint_11 }
  12: { joint: phantom_joint_12 }
  13: { joint: phantom_joint_13 }
  14: { joint: phantom_joint_14 }
  15: { joint: phantom_joint_15 }
  16: { joint: phantom_joint_16 }
  17: { joint: phantom_joint_17 }
)yaml";
  EXPECT_THROW(c.load_from_string(broken), std::runtime_error);

  EXPECT_EQ(c.at(0).joint_name, "leg_1_coxa_joint");
  EXPECT_THROW(c.output_idx_for_joint("phantom_joint_0"), std::out_of_range);
}

// ============================================================================
// set_joint_limits
// ============================================================================

TEST(SetJointLimits, AppliesLimitsToNamedJoint)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);

  c.set_joint_limits("leg_3_femur_joint", -1.0, +1.2);
  const auto & s = c.at(c.output_idx_for_joint("leg_3_femur_joint"));
  EXPECT_DOUBLE_EQ(s.joint_lower, -1.0);
  EXPECT_DOUBLE_EQ(s.joint_upper, +1.2);
}

TEST(SetJointLimits, SilentlyIgnoresUnknownJoint)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  // URDF may include passive joints we don't drive — must not throw.
  EXPECT_NO_THROW(c.set_joint_limits("phantom_joint", -1, +1));
}

// ============================================================================
// radians_to_pulse_us — symmetric default config (direction=+1)
// ============================================================================

TEST(RadiansToPulse, ZeroRadIsPulseZero)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_DOUBLE_EQ(c.radians_to_pulse_us(i, 0.0), 1500.0) << "servo " << i;
  }
}

TEST(RadiansToPulse, JointLowerHitsPulseMin)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c, -1.57, +1.57);
  // (1500 - 500) / 1.57 = ~636.94 µs/rad. rad=-1.57 → 1500 - 1.57·636.94 = 500.
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_NEAR(c.radians_to_pulse_us(i, -1.57), 500.0, 1e-9);
  }
}

TEST(RadiansToPulse, JointUpperHitsPulseMax)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c, -1.57, +1.57);
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_NEAR(c.radians_to_pulse_us(i, +1.57), 2500.0, 1e-9);
  }
}

TEST(RadiansToPulse, QuarterPiSymmetric)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c, -1.57, +1.57);
  // slope_right = (2500-1500)/1.57 = 636.943..
  // rad = +π/4 ≈ 0.7854 → 1500 + 0.7854 · 636.943 = 2000.297...
  const double expected = 1500.0 + (M_PI / 4.0) * ((2500.0 - 1500.0) / 1.57);
  EXPECT_NEAR(c.radians_to_pulse_us(0, M_PI / 4.0), expected, 1e-9);
  EXPECT_NEAR(c.radians_to_pulse_us(0, -M_PI / 4.0),
    1500.0 - (M_PI / 4.0) * ((1500.0 - 500.0) / 1.57), 1e-9);
}

// ============================================================================
// radians_to_pulse_us — asymmetric config (different slope left vs right)
// ============================================================================

TEST(RadiansToPulse, AsymmetricSlopesUseCorrectSide)
{
  // Construct a per-servo override where pulse_zero is NOT in the middle:
  // pulse_min=600, pulse_zero=1500, pulse_max=2400 → slope ratio not 1:1
  // joint_lower=-1.5, joint_upper=+1.0 → another asymmetry
  // slope_left  = (1500 - 600) / |-1.5| = 600 µs/rad
  // slope_right = (2400 - 1500) / 1.0    = 900 µs/rad
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0: { joint: leg_1_coxa_joint,  pulse_min: 600,  pulse_zero: 1500, pulse_max: 2400 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  c.load_from_string(yaml);
  c.set_joint_limits("leg_1_coxa_joint", -1.5, +1.0);

  // rad=+0.5 → pulse_zero + 0.5 · 900 = 1950
  EXPECT_NEAR(c.radians_to_pulse_us(0, +0.5), 1950.0, 1e-9);
  // rad=-1.0 → pulse_zero + (-1.0) · 600 = 900
  EXPECT_NEAR(c.radians_to_pulse_us(0, -1.0), 900.0, 1e-9);
  // Endpoints
  EXPECT_NEAR(c.radians_to_pulse_us(0, -1.5), 600.0, 1e-9);
  EXPECT_NEAR(c.radians_to_pulse_us(0, +1.0), 2400.0, 1e-9);
}

// ============================================================================
// radians_to_pulse_us — direction=-1 (mirror)
// ============================================================================

TEST(RadiansToPulse, NegativeDirectionMirrors)
{
  // Servo 0 mounted "backwards" relative to URDF joint axis.
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0: { joint: leg_1_coxa_joint, direction: -1 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  c.load_from_string(yaml);
  apply_symmetric_limits(c, -1.57, +1.57);

  // rad=+1.57 → pulse_zero + (-1) · 1.57 · slope_right
  //          = 1500 + (-1) · 1.57 · (1000/1.57) = 500   (mirrored!)
  EXPECT_NEAR(c.radians_to_pulse_us(0, +1.57), 500.0, 1e-9);
  EXPECT_NEAR(c.radians_to_pulse_us(0, -1.57), 2500.0, 1e-9);
  EXPECT_NEAR(c.radians_to_pulse_us(0, 0.0), 1500.0, 1e-9);
}

// ============================================================================
// pulse_us_to_radians — inverse
// ============================================================================

TEST(PulseToRadians, PulseZeroIsZeroRad)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  for (int i = 0; i < static_cast<int>(NUM_SERVOS); ++i) {
    EXPECT_NEAR(c.pulse_us_to_radians(i, 1500.0), 0.0, 1e-12);
  }
}

TEST(PulseToRadians, EndpointsRecoverJointLimits)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c, -1.57, +1.57);
  EXPECT_NEAR(c.pulse_us_to_radians(0, 500.0), -1.57, 1e-9);
  EXPECT_NEAR(c.pulse_us_to_radians(0, 2500.0), +1.57, 1e-9);
}

// ============================================================================
// Roundtrip — forward ∘ inverse = identity (modulo float rounding)
// ============================================================================

TEST(Roundtrip, ForwardThenInverseIsIdentitySymmetric)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  for (double rad = -1.5; rad <= 1.5; rad += 0.1) {
    const double pulse = c.radians_to_pulse_us(0, rad);
    const double recovered = c.pulse_us_to_radians(0, pulse);
    EXPECT_NEAR(recovered, rad, 1e-9) << "rad=" << rad;
  }
}

TEST(Roundtrip, ForwardThenInverseIsIdentityAsymmetric)
{
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0: { joint: leg_1_coxa_joint, pulse_min: 600, pulse_zero: 1500, pulse_max: 2400 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  c.load_from_string(yaml);
  c.set_joint_limits("leg_1_coxa_joint", -1.5, +1.0);

  for (double rad = -1.4; rad <= 0.9; rad += 0.1) {
    const double pulse = c.radians_to_pulse_us(0, rad);
    const double recovered = c.pulse_us_to_radians(0, pulse);
    EXPECT_NEAR(recovered, rad, 1e-9) << "rad=" << rad;
  }
}

TEST(Roundtrip, NegativeDirectionRoundtrips)
{
  const char * yaml =
    R"yaml(
defaults: { pulse_min: 500, pulse_max: 2500, pulse_zero: 1500, direction: 1 }
servo2040_output_to_joint:
  0: { joint: leg_1_coxa_joint, direction: -1 }
  1:  { joint: leg_1_femur_joint }
  2:  { joint: leg_1_tibia_joint }
  3:  { joint: leg_2_coxa_joint  }
  4:  { joint: leg_2_femur_joint }
  5:  { joint: leg_2_tibia_joint }
  6:  { joint: leg_3_coxa_joint  }
  7:  { joint: leg_3_femur_joint }
  8:  { joint: leg_3_tibia_joint }
  9:  { joint: leg_4_coxa_joint  }
  10: { joint: leg_4_femur_joint }
  11: { joint: leg_4_tibia_joint }
  12: { joint: leg_5_coxa_joint  }
  13: { joint: leg_5_femur_joint }
  14: { joint: leg_5_tibia_joint }
  15: { joint: leg_6_coxa_joint  }
  16: { joint: leg_6_femur_joint }
  17: { joint: leg_6_tibia_joint }
)yaml";
  Calibration c;
  c.load_from_string(yaml);
  apply_symmetric_limits(c, -1.57, +1.57);
  for (double rad = -1.5; rad <= 1.5; rad += 0.1) {
    const double pulse = c.radians_to_pulse_us(0, rad);
    const double recovered = c.pulse_us_to_radians(0, pulse);
    EXPECT_NEAR(recovered, rad, 1e-9) << "rad=" << rad;
  }
}

// ============================================================================
// Bounds checking
// ============================================================================

TEST(Bounds, NegativeIndexThrows)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  EXPECT_THROW(c.radians_to_pulse_us(-1, 0.0), std::out_of_range);
  EXPECT_THROW(c.pulse_us_to_radians(-1, 1500.0), std::out_of_range);
  EXPECT_THROW(c.at(-1), std::out_of_range);
}

TEST(Bounds, OverflowIndexThrows)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  EXPECT_THROW(c.radians_to_pulse_us(NUM_SERVOS, 0.0), std::out_of_range);
  EXPECT_THROW(c.pulse_us_to_radians(NUM_SERVOS, 1500.0), std::out_of_range);
  EXPECT_THROW(c.at(NUM_SERVOS), std::out_of_range);
}

// ============================================================================
// Real config file (sanity check — does the installed YAML parse cleanly?)
// ============================================================================

TEST(RealConfigFile, InstalledServoMappingParses)
{
  // The test runs from build/<pkg>/, the YAML lives under
  // src/<pkg>/config/. Take the source-tree path; the install copy is
  // exercised by the launch-testing smoke test later (stage I).
  const std::string source_yaml =
    std::string(SOURCE_DIR_FOR_TESTS) + "/config/servo_mapping.yaml";
  Calibration c;
  EXPECT_NO_THROW(c.load_from_file(source_yaml));
  // 18 mapped joints, all with default pulse triplet.
  EXPECT_EQ(c.output_idx_for_joint("leg_1_coxa_joint"), 0);
  EXPECT_EQ(c.output_idx_for_joint("leg_6_tibia_joint"), 17);
  EXPECT_EQ(c.at(0).pulse_zero, 1500);
}

// ============================================================================
// Phase 11 Stage B — Live-Cal-Update API (snapshot, update_servo_cal)
// ============================================================================

TEST(StageBLiveCal, SnapshotReturnsCurrentValues)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  const auto snap = c.snapshot(0);
  EXPECT_EQ(snap.joint_name, "leg_1_coxa_joint");
  EXPECT_EQ(snap.pulse_min, 500);
  EXPECT_EQ(snap.pulse_zero, 1500);
  EXPECT_EQ(snap.pulse_max, 2500);
  EXPECT_EQ(snap.direction, 1);
}

TEST(StageBLiveCal, SnapshotOutOfRangeThrows)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  EXPECT_THROW(c.snapshot(-1), std::out_of_range);
  EXPECT_THROW(c.snapshot(static_cast<int>(NUM_SERVOS)), std::out_of_range);
}

TEST(StageBLiveCal, UpdateServoCalHappyPath)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  auto cal = c.snapshot(15);
  cal.pulse_min = 1280;
  cal.pulse_zero = 1550;
  cal.pulse_max = 1860;
  cal.direction = -1;
  EXPECT_NO_THROW(c.update_servo_cal(15, cal));

  const auto after = c.snapshot(15);
  EXPECT_EQ(after.pulse_min, 1280);
  EXPECT_EQ(after.pulse_zero, 1550);
  EXPECT_EQ(after.pulse_max, 1860);
  EXPECT_EQ(after.direction, -1);
  EXPECT_EQ(after.joint_name, "leg_6_coxa_joint");  // preserved
}

TEST(StageBLiveCal, UpdateServoCalRejectsInvalidTriplet)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  auto cal = c.snapshot(0);
  cal.pulse_min = 1500;   // = zero, breaks min < zero
  cal.pulse_zero = 1500;
  cal.pulse_max = 2500;
  EXPECT_THROW(c.update_servo_cal(0, cal), std::runtime_error);

  // Original unverändert (strong exception guarantee)
  const auto unchanged = c.snapshot(0);
  EXPECT_EQ(unchanged.pulse_min, 500);
}

TEST(StageBLiveCal, UpdateServoCalRejectsInvalidDirection)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  auto cal = c.snapshot(0);
  cal.direction = 0;  // not ±1
  EXPECT_THROW(c.update_servo_cal(0, cal), std::runtime_error);
}

TEST(StageBLiveCal, UpdateServoCalOutOfRangeThrows)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  auto cal = c.snapshot(0);
  EXPECT_THROW(c.update_servo_cal(-1, cal), std::out_of_range);
  EXPECT_THROW(c.update_servo_cal(NUM_SERVOS, cal), std::out_of_range);
}

TEST(StageBLiveCal, RadiansToPulseUsesUpdatedValues)
{
  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  // Vorher: pulse_zero = 1500, direction = +1 → rad=0 ergibt 1500
  EXPECT_DOUBLE_EQ(c.radians_to_pulse_us(0, 0.0), 1500.0);

  auto cal = c.snapshot(0);
  cal.pulse_zero = 1450;
  c.update_servo_cal(0, cal);

  // Nach Update: rad=0 ergibt 1450
  EXPECT_DOUBLE_EQ(c.radians_to_pulse_us(0, 0.0), 1450.0);
}

// ============================================================================
// Phase 11 Stage B — save_to_file (Persistenz + Timestamp-Backup)
// ============================================================================

namespace
{

// Tmpdir-Pattern für Filesystem-Tests. Erzeugt unique-Verzeichnis pro
// Test, cleanup beim Destructor.
class TempDir
{
public:
  TempDir()
  {
    namespace fs = std::filesystem;
    auto base = fs::temp_directory_path();
    // Mikrosekunden + Test-Process-PID-Mix für Uniqueness
    const auto now = std::chrono::steady_clock::now().time_since_epoch();
    const auto us = std::chrono::duration_cast<std::chrono::microseconds>(now).count();
    path_ = base / ("hexapod_test_" + std::to_string(us));
    fs::create_directory(path_);
  }
  ~TempDir() {std::filesystem::remove_all(path_);}
  std::filesystem::path operator/(const std::string & sub) const
  {
    return path_ / sub;
  }
  std::string str(const std::string & sub) const
  {
    return (path_ / sub).string();
  }

private:
  std::filesystem::path path_;
};

}  // namespace

TEST(StageBSaveToFile, SaveRoundTripPreservesValues)
{
  TempDir tmp;
  const std::string path = tmp.str("servo_mapping.yaml");

  // Setup: erstmal aus Minimal-YAML laden + ein paar Werte ändern
  Calibration c1;
  c1.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c1);

  auto cal = c1.snapshot(15);
  cal.pulse_min = 1280;
  cal.pulse_zero = 1550;
  cal.pulse_max = 1860;
  cal.direction = -1;
  c1.update_servo_cal(15, cal);

  // Save
  EXPECT_NO_THROW(c1.save_to_file(path));
  EXPECT_TRUE(std::filesystem::exists(path));

  // Load in neue Calibration und vergleiche
  Calibration c2;
  EXPECT_NO_THROW(c2.load_from_file(path));
  const auto loaded = c2.snapshot(15);
  EXPECT_EQ(loaded.pulse_min, 1280);
  EXPECT_EQ(loaded.pulse_zero, 1550);
  EXPECT_EQ(loaded.pulse_max, 1860);
  EXPECT_EQ(loaded.direction, -1);
  EXPECT_EQ(loaded.joint_name, "leg_6_coxa_joint");

  // Andere Pins haben Defaults aus dem Save
  const auto pin_0 = c2.snapshot(0);
  EXPECT_EQ(pin_0.pulse_min, 500);
  EXPECT_EQ(pin_0.pulse_zero, 1500);
  EXPECT_EQ(pin_0.pulse_max, 2500);
}

TEST(StageBSaveToFile, FirstSaveCreatesNoBak)
{
  TempDir tmp;
  const std::string path = tmp.str("first.yaml");

  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);

  // Erster Save — Path existiert noch nicht → kein .bak
  c.save_to_file(path);
  EXPECT_TRUE(std::filesystem::exists(path));

  // Listing nach .bak-Files im tmpdir
  int bak_count = 0;
  for (const auto & entry : std::filesystem::directory_iterator(tmp / "")) {
    if (entry.path().filename().string().find(".bak-") != std::string::npos) {
      ++bak_count;
    }
  }
  EXPECT_EQ(bak_count, 0) << "first save should not create .bak file";
}

TEST(StageBSaveToFile, RepeatedSaveCreatesUniqueTimestampBak)
{
  TempDir tmp;
  const std::string path = tmp.str("evolving.yaml");

  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  c.save_to_file(path);  // erster Save = "original"

  // Sleep 1.1s damit Timestamp-Suffix unique ist (Sekunden-Auflösung).
  std::this_thread::sleep_for(std::chrono::milliseconds(1100));

  // Modify + Re-save → erzeugt erstes .bak (= original)
  auto cal = c.snapshot(0);
  cal.pulse_zero = 1450;
  c.update_servo_cal(0, cal);
  c.save_to_file(path);

  std::this_thread::sleep_for(std::chrono::milliseconds(1100));

  // Modify + Re-save → erzeugt zweites .bak (= 1. save-Inhalt)
  cal = c.snapshot(0);
  cal.pulse_zero = 1480;
  c.update_servo_cal(0, cal);
  c.save_to_file(path);

  // Erwartung: 2 .bak-Files mit unterschiedlichen Timestamps
  std::vector<std::filesystem::path> bak_files;
  for (const auto & entry : std::filesystem::directory_iterator(tmp / "")) {
    const std::string fname = entry.path().filename().string();
    if (fname.find("evolving.yaml.bak-") == 0) {
      bak_files.push_back(entry.path());
    }
  }
  EXPECT_EQ(bak_files.size(), 2u)
    << "expected 2 unique timestamp-baks after 2 re-saves";

  // Beide Filenamen matchen das Timestamp-Pattern .bak-YYYY-MM-DDTHH-MM-SS
  std::regex ts_re(R"(\.bak-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$)");
  for (const auto & p : bak_files) {
    EXPECT_TRUE(std::regex_search(p.filename().string(), ts_re))
      << "filename '" << p.filename().string() << "' does not match "
      << "timestamp pattern .bak-YYYY-MM-DDTHH-MM-SS";
  }
}

TEST(StageBSaveToFile, SavedYamlContainsHeaderBanner)
{
  TempDir tmp;
  const std::string path = tmp.str("with_header.yaml");

  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  c.save_to_file(path);

  std::ifstream ifs(path);
  std::stringstream ss;
  ss << ifs.rdbuf();
  const std::string content = ss.str();
  EXPECT_NE(content.find("Auto-generated by /save_calibration"),
    std::string::npos);
  EXPECT_NE(content.find("Phase 11 Stage B"), std::string::npos);
}

TEST(StageBSaveToFile, SavedYamlIsExplicitNotInheriting)
{
  TempDir tmp;
  const std::string path = tmp.str("explicit.yaml");

  Calibration c;
  c.load_from_string(MINIMAL_YAML);
  apply_symmetric_limits(c);
  c.save_to_file(path);

  // F5: alle 18 Pins müssen ALLE 4 Cal-Felder explizit haben
  // (keine Implicit-Inheritance vom defaults-Block).
  Calibration c2;
  c2.load_from_string(MINIMAL_YAML);  // load default state to compare baselines
  c.save_to_file(path);  // overwrite

  std::ifstream ifs(path);
  std::stringstream ss;
  ss << ifs.rdbuf();
  const std::string content = ss.str();
  // Pulse-Field-Counts: jeder Pin hat pulse_min/zero/max + direction
  // = 18 × 4 = 72 explizite Cal-Field-Vorkommen
  // (plus 4 im defaults-Block = total 76)
  std::size_t pulse_min_count = 0;
  std::size_t pos = 0;
  while ((pos = content.find("pulse_min:", pos)) != std::string::npos) {
    ++pulse_min_count;
    ++pos;
  }
  EXPECT_EQ(pulse_min_count, 19u)
    << "expected 18 explicit pulse_min entries + 1 in defaults = 19, got "
    << pulse_min_count;
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
