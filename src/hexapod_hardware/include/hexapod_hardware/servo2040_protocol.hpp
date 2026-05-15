// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__SERVO2040_PROTOCOL_HPP_
#define HEXAPOD_HARDWARE__SERVO2040_PROTOCOL_HPP_

#include <array>
#include <cstdint>
#include <optional>
#include <vector>

namespace hexapod_hardware
{

// Opcodes — mirror of ~/hexapod_servo_driver/src/config.hpp::cmd::*
// See PROTOCOL.md §3 for the wire-format spec.
namespace opcode
{
constexpr uint8_t SET_TARGETS = 0x01;
constexpr uint8_t GET_STATE = 0x02;
constexpr uint8_t STATE_RESPONSE = 0x82;
constexpr uint8_t SET_CALIBRATION = 0x10;
constexpr uint8_t SET_CURRENT_LIMIT = 0x11;
constexpr uint8_t ENABLE_SERVO = 0x20;
constexpr uint8_t SET_LED = 0x30;
constexpr uint8_t SET_LEDS_ALL = 0x31;
constexpr uint8_t GET_INPUTS = 0x40;
constexpr uint8_t INPUTS_RESPONSE = 0xC0;
constexpr uint8_t RESET = 0x50;
constexpr uint8_t ERROR_REPORT = 0x7F;
constexpr uint8_t NACK = 0xFE;
constexpr uint8_t ACK = 0xFF;
}  // namespace opcode

namespace error_code
{
constexpr uint8_t FRAME_CRC = 0x01;
constexpr uint8_t FRAME_MALFORMED = 0x02;
constexpr uint8_t UNKNOWN_OPCODE = 0x03;
constexpr uint8_t PAYLOAD_LEN = 0x04;
constexpr uint8_t PULSE_OUT_OF_RANGE = 0x10;
constexpr uint8_t SERVO_OVERCURRENT = 0x20;
constexpr uint8_t TOTAL_OVERCURRENT = 0x21;
constexpr uint8_t UNDERVOLTAGE = 0x30;
constexpr uint8_t WATCHDOG_TRIPPED = 0x40;
}  // namespace error_code

namespace status_flag
{
constexpr uint8_t WATCHDOG_TRIPPED = 1u << 0;
constexpr uint8_t UNDERVOLTAGE_TRIPPED = 1u << 1;
constexpr uint8_t TOTAL_OVERCURRENT_TRIPPED = 1u << 2;
constexpr uint8_t ANY_SERVO_OVERCURRENT_TRIPPED = 1u << 3;
constexpr uint8_t ANY_SERVO_DISABLED = 1u << 4;
constexpr uint8_t UNDERVOLTAGE_WARNING = 1u << 5;
}  // namespace status_flag

constexpr std::size_t NUM_SERVOS = 18;

// LEN field is a single byte in the wire frame (PROTOCOL.md §2.3). Payloads
// must be ≤ 253 bytes; 254 + 255 are reserved for future protocol use and
// passing more is undefined behaviour on the firmware side.
constexpr std::size_t MAX_PAYLOAD_LEN = 253;

struct StatePayload
{
  std::array<int16_t, NUM_SERVOS> last_pulse_us{};
  std::array<uint16_t, NUM_SERVOS> last_current_ma{};
  uint16_t voltage_mv{0};
  uint8_t status_flags{0};
};

struct ErrorReport
{
  uint8_t error_code{0};
  uint8_t servo_idx{0};
  int16_t aux{0};
};

// Result of decode_frame: the inner frame after COBS-strip + CRC-check.
struct DecodedFrame
{
  uint8_t seq{0};
  uint8_t cmd{0};
  std::vector<uint8_t> payload{};
};

// Specialised encoders — each returns the fully-wrapped wire bytes
// (COBS-encoded with a trailing 0x00 delimiter, ready to write to the
// serial port). See PROTOCOL.md §4 for example hex-dumps.
std::vector<uint8_t> encode_set_targets(
  uint8_t seq,
  const std::array<int16_t, NUM_SERVOS> & pulse_us);
std::vector<uint8_t> encode_get_state(uint8_t seq);
std::vector<uint8_t> encode_enable_servo(uint8_t seq, uint8_t servo_idx, bool enable);
std::vector<uint8_t> encode_reset(uint8_t seq);

// Generic frame encoder. Builds SEQ ‖ CMD ‖ LEN ‖ PAYLOAD ‖ CRC16-LE,
// COBS-encodes the lot, appends one trailing 0x00 delimiter.
//
// Precondition: payload.size() <= MAX_PAYLOAD_LEN (253).
// Throws std::invalid_argument if the payload would overflow the 1-byte LEN
// field — silent truncation would corrupt the wire and the firmware would
// drop the frame (or worse, mis-parse it as the start of the next one).
std::vector<uint8_t> encode_frame(
  uint8_t seq, uint8_t cmd,
  const std::vector<uint8_t> & payload);

// Generic frame decoder. Accepts the COBS-encoded bytes of one frame —
// trailing 0x00 is tolerated (stripped if present) but not required.
// Returns nullopt on COBS-decode failure, CRC mismatch, or malformed
// length field.
std::optional<DecodedFrame> decode_frame(const std::vector<uint8_t> & cobs_bytes);

// Payload decoders. Caller has already pulled the payload out of a
// DecodedFrame and verified the opcode.
std::optional<StatePayload> decode_state(const std::vector<uint8_t> & payload);
std::optional<ErrorReport> decode_error_report(const std::vector<uint8_t> & payload);

// Lower-level primitives. Public for testing and reuse.
uint16_t crc16_ccitt_false(const uint8_t * data, std::size_t len);
std::vector<uint8_t> cobs_encode(const std::vector<uint8_t> & input);
std::optional<std::vector<uint8_t>> cobs_decode(const std::vector<uint8_t> & input);

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__SERVO2040_PROTOCOL_HPP_
