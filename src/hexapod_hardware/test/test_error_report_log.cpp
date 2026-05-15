// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for error_report_log: severity routing + human-readable
// formatting for firmware ErrorReports. Pure-function testing — no
// RCLCPP log capture needed.
//
// Code map covered (PROTOCOL.md §3.4):
//   0x01 FRAME_CRC          WARN
//   0x02 FRAME_MALFORMED    WARN  (aux = expected LEN)
//   0x03 UNKNOWN_OPCODE     WARN
//   0x04 PAYLOAD_LEN        WARN  (aux = expected LEN)
//   0x10 PULSE_OUT_OF_RANGE WARN  (servo_idx, aux = clamped pulse µs)
//   0x21 TOTAL_OVERCURRENT  FATAL (aux = mA)
//   0x30 UNDERVOLTAGE       ERROR (aux = mV; no WARN/TRIP sub-case)
//   0x40 WATCHDOG_TRIPPED   FATAL
// Explicitly NOT covered as a normal code (falls into unknown fallback):
//   0x20 SERVO_OVERCURRENT  — Servo2040 has no per-servo current sensing,
//                             firmware cannot send this. Verified to land
//                             in the unknown-fallback branch.

#include <gtest/gtest.h>

#include <string>

#include "hexapod_hardware/error_report_log.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

using hexapod_hardware::ErrorReport;
using hexapod_hardware::ErrorSeverity;
using hexapod_hardware::format_error_report;
using hexapod_hardware::severity_for;
namespace ec = hexapod_hardware::error_code;

namespace
{

// Small helper: assert that the formatted string contains the given
// substring. Gives clearer failure output than EXPECT_NE(find, npos).
::testing::AssertionResult Contains(const std::string & haystack, const std::string & needle)
{
  if (haystack.find(needle) != std::string::npos) {
    return ::testing::AssertionSuccess();
  }
  return ::testing::AssertionFailure() <<
         "expected substring '" << needle << "' not found in:\n  " << haystack;
}

}  // namespace

// ============================================================================
// Per-code: severity + format
// ============================================================================

TEST(ErrorReportLogFormat, FrameCrcIsWarnAndMentionsCrc)
{
  ErrorReport r{ec::FRAME_CRC, 0, 0};
  EXPECT_EQ(severity_for(r), ErrorSeverity::WARN);
  EXPECT_TRUE(Contains(format_error_report(r), "CRC"));
}

TEST(ErrorReportLogFormat, FrameMalformedMentionsExpectedLen)
{
  ErrorReport r{ec::FRAME_MALFORMED, 0, /*aux=*/42};
  EXPECT_EQ(severity_for(r), ErrorSeverity::WARN);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "malformed"));
  EXPECT_TRUE(Contains(msg, "42"));
}

TEST(ErrorReportLogFormat, UnknownOpcodeIsWarnAndMentionsDrift)
{
  ErrorReport r{ec::UNKNOWN_OPCODE, 0, 0};
  EXPECT_EQ(severity_for(r), ErrorSeverity::WARN);
  // The message hints at protocol-drift since the typical cause is
  // host/firmware versions out of sync.
  EXPECT_TRUE(Contains(format_error_report(r), "drift"));
}

TEST(ErrorReportLogFormat, PayloadLenMentionsExpectedSize)
{
  ErrorReport r{ec::PAYLOAD_LEN, 0, /*aux=*/18};
  EXPECT_EQ(severity_for(r), ErrorSeverity::WARN);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "payload"));
  EXPECT_TRUE(Contains(msg, "18"));
}

TEST(ErrorReportLogFormat, PulseOutOfRangeMentionsServoIdxAndClamped)
{
  ErrorReport r{ec::PULSE_OUT_OF_RANGE, /*servo_idx=*/7, /*aux=*/2500};
  EXPECT_EQ(severity_for(r), ErrorSeverity::WARN);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "clamped"));
  EXPECT_TRUE(Contains(msg, "servo 7"));
  EXPECT_TRUE(Contains(msg, "2500"));
}

TEST(ErrorReportLogFormat, TotalOvercurrentIsFatalAndMentionsLimit)
{
  ErrorReport r{ec::TOTAL_OVERCURRENT, 0, /*aux=*/4200};
  EXPECT_EQ(severity_for(r), ErrorSeverity::FATAL);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "4200"));
  EXPECT_TRUE(Contains(msg, "ALL"));
}

TEST(ErrorReportLogFormat, UndervoltageIsErrorAndMentionsMv)
{
  // Single ERROR-severity message for both WARN-threshold and TRIP-threshold
  // cases (Phase-9 plan, user-approved variant B). servo_idx is ignored
  // intentionally — the firmware does not reliably distinguish the cases.
  ErrorReport r{ec::UNDERVOLTAGE, 0, /*aux=*/4500};
  EXPECT_EQ(severity_for(r), ErrorSeverity::ERROR);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "undervoltage"));
  EXPECT_TRUE(Contains(msg, "4500"));
  // No "WARN" or "TRIP" wording — there should be no claim about which
  // threshold tripped.
  EXPECT_EQ(msg.find("TRIP"), std::string::npos)
    << "format must not claim WARN vs TRIP semantics: " << msg;
}

TEST(ErrorReportLogFormat, WatchdogTrippedIsFatalAndMentionsReset)
{
  ErrorReport r{ec::WATCHDOG_TRIPPED, 0, 0};
  EXPECT_EQ(severity_for(r), ErrorSeverity::FATAL);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "WATCHDOG"));
  // The recovery hint MUST mention RESET (firmware NACKs ENABLE_SERVO
  // until RESET has cleared the trip flag — PROTOCOL.md §6).
  EXPECT_TRUE(Contains(msg, "RESET"));
}

// ============================================================================
// Unknown / forward-compat
// ============================================================================

TEST(ErrorReportLogFormat, UnknownCodeFallsBackToHexDump)
{
  // 0xAB is not in the firmware spec — falls into the default branch.
  ErrorReport r{0xAB, /*servo_idx=*/5, /*aux=*/-123};
  EXPECT_EQ(severity_for(r), ErrorSeverity::ERROR);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "Unknown"));
  EXPECT_TRUE(Contains(msg, "0xAB"));
}

TEST(ErrorReportLogFormat, ServoOvercurrentCodeFallsBackToUnknown)
{
  // 0x20 SERVO_OVERCURRENT is in the protocol header as a constant but
  // Servo2040 hardware has no per-servo current sensing, so the firmware
  // cannot generate it. We MUST treat it as an unknown code (forward-
  // compat for a future per-servo sensing hardware revision) rather than
  // silently producing a wrong message. This test pins the contract.
  ErrorReport r{ec::SERVO_OVERCURRENT, /*servo_idx=*/3, /*aux=*/850};
  EXPECT_EQ(severity_for(r), ErrorSeverity::ERROR);
  const auto msg = format_error_report(r);
  EXPECT_TRUE(Contains(msg, "Unknown"));
  // 0x20 (32 decimal) must appear in the hex dump.
  EXPECT_TRUE(Contains(msg, "0x20"));
}

// ============================================================================
// Smoke
// ============================================================================

TEST(ErrorReportLogFormat, AllSpecCodesReturnNonEmptyString)
{
  const uint8_t codes[] = {
    ec::FRAME_CRC,
    ec::FRAME_MALFORMED,
    ec::UNKNOWN_OPCODE,
    ec::PAYLOAD_LEN,
    ec::PULSE_OUT_OF_RANGE,
    ec::TOTAL_OVERCURRENT,
    ec::UNDERVOLTAGE,
    ec::WATCHDOG_TRIPPED,
    /*unknown*/ 0xFE,
  };
  for (const uint8_t c : codes) {
    ErrorReport r{c, /*servo_idx=*/0, /*aux=*/0};
    const auto msg = format_error_report(r);
    EXPECT_FALSE(msg.empty())
      << "format_error_report produced empty string for code 0x" <<
      std::hex << static_cast<unsigned>(c);
  }
}
