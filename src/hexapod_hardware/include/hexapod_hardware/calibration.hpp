// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__CALIBRATION_HPP_
#define HEXAPOD_HARDWARE__CALIBRATION_HPP_

#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>

#include "hexapod_hardware/servo2040_protocol.hpp"

namespace hexapod_hardware
{

// Calibration record for a single servo (one row of servo_mapping.yaml).
// The three-point scheme + piecewise-linear conversion is documented in
// docs_raspi/phase_9_progress.md (Design-Entscheidung "Option C").
struct ServoCalibration
{
  std::string joint_name;
  int16_t pulse_min{500};
  int16_t pulse_zero{1500};
  int16_t pulse_max{2500};
  int8_t direction{+1};  // +1 or -1
  double joint_lower{-1.57};  // from URDF limit, set after construction
  double joint_upper{+1.57};  // from URDF limit, set after construction
};

class Calibration
{
public:
  // Load YAML from disk. Throws on parse error or schema violation.
  void load_from_file(const std::string & path);

  // Apply URDF-derived joint limits per joint name. Must be called after
  // load_from_file() and before any conversion call.
  void set_joint_limits(const std::string & joint_name, double lower, double upper);

  // Conversion API (piecewise-linear about pulse_zero, see progress.md).
  double radians_to_pulse_us(int output_idx, double rad) const;
  double pulse_us_to_radians(int output_idx, double pulse_us) const;

  // Lookup helpers.
  const ServoCalibration & at(int output_idx) const;
  int output_idx_for_joint(const std::string & joint_name) const;

private:
  std::array<ServoCalibration, NUM_SERVOS> servos_{};
  std::unordered_map<std::string, int> joint_name_to_idx_{};
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__CALIBRATION_HPP_
