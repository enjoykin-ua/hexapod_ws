// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Stage A placeholder: just verifies the test framework wires up and the
// header includes. Real conversion tests come in stage C.
#include <gtest/gtest.h>

#include "hexapod_hardware/calibration.hpp"

TEST(CalibrationStub, ZeroIsNeutral)
{
  // Stub returns 1500 µs for any input — replaced by real impl in stage C.
  hexapod_hardware::Calibration cal;
  EXPECT_DOUBLE_EQ(cal.radians_to_pulse_us(0, 0.0), 1500.0);
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
