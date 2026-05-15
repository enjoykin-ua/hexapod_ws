// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/error_report_log.hpp"

#include <array>
#include <cstdio>
#include <string>

namespace hexapod_hardware
{

namespace
{

// Small printf-style helper that returns a std::string. snprintf into a
// fixed local buffer is fine here — none of our format strings produce
// more than ~200 characters even in the worst case (Watchdog message
// is the longest).
template<typename ... Args>
std::string fmt(const char * format, Args... args)
{
  std::array<char, 256> buf{};
  // The format is a compile-time C-string from this translation unit;
  // -Wformat-security is satisfied because we always pass a literal.
  const int n = std::snprintf(buf.data(), buf.size(), format, args ...);
  if (n <= 0) {return {};}
  return std::string(buf.data(),
           static_cast<std::size_t>(n) < buf.size() ?
           static_cast<std::size_t>(n) :
           buf.size() - 1);
}

}  // namespace

ErrorSeverity severity_for(const ErrorReport & report)
{
  // Frame-layer errors: firmware drops the offending frame and re-syncs
  // on the next 0x00. No robot impact, but worth surfacing for diagnosis.
  switch (report.error_code) {
    case error_code::FRAME_CRC:
    case error_code::FRAME_MALFORMED:
    case error_code::UNKNOWN_OPCODE:
    case error_code::PAYLOAD_LEN:
    case error_code::PULSE_OUT_OF_RANGE:
      return ErrorSeverity::WARN;

    // Hard trips — multiple or all servos disabled by the firmware's
    // safety layer. ros2_control should treat these as terminal.
    case error_code::TOTAL_OVERCURRENT:
    case error_code::WATCHDOG_TRIPPED:
      return ErrorSeverity::FATAL;

    // Power-supply sag. The Phase-9 plan does not distinguish WARN-/
    // TRIP-thresholds — one severity covers both. ERROR is actionable
    // (check PSU / wiring) without claiming "all servos off" the way
    // FATAL would.
    case error_code::UNDERVOLTAGE:
      return ErrorSeverity::ERROR;

    // SERVO_OVERCURRENT (0x20) intentionally not listed — Servo2040 has
    // no per-servo current sensing, so the firmware cannot produce this
    // on current hardware. Falls through to default (ERROR) on the off
    // chance a future firmware/hardware revision does send it.
    default:
      return ErrorSeverity::ERROR;
  }
}

std::string format_error_report(const ErrorReport & report)
{
  switch (report.error_code) {
    case error_code::FRAME_CRC:
      // aux/servo_idx not meaningful here — firmware just dropped a
      // frame that failed the CRC check.
      return std::string("Firmware reported CRC error on incoming frame");

    case error_code::FRAME_MALFORMED:
      // aux carries the LEN value the firmware expected for the opcode.
      return fmt(
        "Firmware reported malformed frame (LEN field mismatch, expected %d)",
        static_cast<int>(report.aux));

    case error_code::UNKNOWN_OPCODE:
      // Host sent a CMD byte the firmware does not implement. Usually a
      // protocol-drift symptom (e.g. host updated, firmware not yet).
      return std::string(
        "Firmware reported unknown opcode — host/firmware protocol drift?");

    case error_code::PAYLOAD_LEN:
      // aux carries the LEN the firmware expected for that opcode.
      return fmt(
        "Firmware reported payload length mismatch (expected %d for that opcode)",
        static_cast<int>(report.aux));

    case error_code::PULSE_OUT_OF_RANGE:
      // servo_idx = which servo, aux = the clamped pulse value the
      // firmware actually applied. Hints that the host calibration is
      // wider than the firmware's per-servo pulse_min/pulse_max.
      return fmt(
        "Firmware clamped pulse on servo %u to %d µs "
        "(host calibration too generous?)",
        static_cast<unsigned>(report.servo_idx),
        static_cast<int>(report.aux));

    case error_code::TOTAL_OVERCURRENT:
      // aux = measured total current at the moment of the trip, in mA.
      return fmt(
        "Total servo current %d mA exceeded limit — ALL servos disabled",
        static_cast<int>(report.aux));

    case error_code::UNDERVOLTAGE:
      // aux = measured rail voltage in mV. The Phase-9 plan keeps this
      // as a single ERROR rather than splitting into WARN-/TRIP-sub-cases.
      return fmt(
        "Firmware reported undervoltage at %d mV — check power supply",
        static_cast<int>(report.aux));

    case error_code::WATCHDOG_TRIPPED:
      // The firmware watchdog (200 ms, see PROTOCOL.md §6) fired because
      // the host stopped sending valid frames. All servos are now disabled
      // and the firmware will NACK new ENABLE_SERVO until RESET clears it.
      return std::string(
        "WATCHDOG_TRIPPED — host stopped sending frames > 200 ms, "
        "all servos disabled. Send RESET + ENABLE_SERVO to recover.");

    default:
      // Forward-compat fallback. Includes 0x20 SERVO_OVERCURRENT (current
      // hardware has no per-servo sensing) and any future codes the
      // firmware might introduce.
      return fmt(
        "Unknown firmware error: code=0x%02X servo_idx=%u aux=%d",
        static_cast<unsigned>(report.error_code),
        static_cast<unsigned>(report.servo_idx),
        static_cast<int>(report.aux));
  }
}

}  // namespace hexapod_hardware
