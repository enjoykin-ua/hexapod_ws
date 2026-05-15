// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#include "hexapod_hardware/calibration.hpp"

#include <stdexcept>

namespace hexapod_hardware
{

// Stage C fills these in. Stubs keep the package linkable in stage A.

void Calibration::load_from_file(const std::string & /*path*/)
{
}

void Calibration::set_joint_limits(
  const std::string & /*joint_name*/, double /*lower*/,
  double /*upper*/)
{
}

double Calibration::radians_to_pulse_us(int /*output_idx*/, double /*rad*/) const
{
  return 1500.0;
}

double Calibration::pulse_us_to_radians(int /*output_idx*/, double /*pulse_us*/) const
{
  return 0.0;
}

const ServoCalibration & Calibration::at(int output_idx) const
{
  if (output_idx < 0 || static_cast<std::size_t>(output_idx) >= servos_.size()) {
    throw std::out_of_range("output_idx out of range");
  }
  return servos_[output_idx];
}

int Calibration::output_idx_for_joint(const std::string & joint_name) const
{
  auto it = joint_name_to_idx_.find(joint_name);
  if (it == joint_name_to_idx_.end()) {
    throw std::out_of_range("joint not in calibration: " + joint_name);
  }
  return it->second;
}

}  // namespace hexapod_hardware
