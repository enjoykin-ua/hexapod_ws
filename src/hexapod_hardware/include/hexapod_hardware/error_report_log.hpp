// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__ERROR_REPORT_LOG_HPP_
#define HEXAPOD_HARDWARE__ERROR_REPORT_LOG_HPP_

#include <string>

#include "hexapod_hardware/servo2040_protocol.hpp"

namespace hexapod_hardware
{

// Severity routing for firmware ErrorReports. Different codes carry
// different operational weight — a watchdog trip (all servos disabled)
// is louder than a single dropped frame.
//
// HexapodSystemHardware::read() inspects severity_for(report) to pick
// the right RCLCPP_* macro (WARN / ERROR / FATAL).
enum class ErrorSeverity
{
  WARN,    // diagnostic, robot keeps running (frame-layer drops, single clamp)
  ERROR,   // user-actionable, something is off but not necessarily disabling
  FATAL,   // operational stop — all (or many) servos disabled by firmware
};

// Decide log severity for a given ErrorReport. Pure function, no logging.
// Codes not in the firmware spec fall back to ERROR (forward-compat).
ErrorSeverity severity_for(const ErrorReport & report);

// Format a one-line, human-readable diagnostic string for the report.
// Includes the symbolic code name, servo_idx when relevant, an
// interpretation of the aux field per code (mA / µs / mV / expected
// LEN / …), and a recovery hint where applicable. Always returns a
// non-empty string, including for unknown codes (hex fallback).
//
// The set of codes formatted explicitly tracks PROTOCOL.md §3.4 (Phase-7
// firmware). One notable omission: 0x20 SERVO_OVERCURRENT is NOT in the
// switch on purpose — the Servo2040 board only measures total current
// (no per-servo sensing), so the firmware cannot send this code on the
// current hardware. If it ever appears (firmware bug, future hardware
// revision with per-servo sensing), it lands in the unknown-code fallback
// branch where the user still sees an actionable line.
//
// UNDERVOLTAGE (0x30) is formatted as a single ERROR-severity message
// without distinguishing WARN-threshold vs TRIP-threshold sub-cases —
// the Phase-9 plan reviewed this and the firmware does not currently
// expose the distinction reliably. Phase 10 can refine if needed.
std::string format_error_report(const ErrorReport & report);

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__ERROR_REPORT_LOG_HPP_
