// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Stage-B unit tests for the Servo2040 wire-protocol layer.
// Verifies CRC, COBS, frame encode/decode, and payload decoders.
// Cross-checked against ~/hexapod_servo_driver/tools/test_servo2040.py
// (Python reference) and PROTOCOL.md hex-dump examples.

#include <gtest/gtest.h>

#include <array>
#include <cstdint>
#include <stdexcept>
#include <vector>

#include "hexapod_hardware/servo2040_protocol.hpp"

using hexapod_hardware::cobs_decode;
using hexapod_hardware::cobs_encode;
using hexapod_hardware::crc16_ccitt_false;
using hexapod_hardware::decode_error_report;
using hexapod_hardware::decode_frame;
using hexapod_hardware::decode_state;
using hexapod_hardware::encode_enable_servo;
using hexapod_hardware::encode_frame;
using hexapod_hardware::encode_get_state;
using hexapod_hardware::encode_relay_control;
using hexapod_hardware::encode_reset;
using hexapod_hardware::encode_set_targets;
using hexapod_hardware::ErrorReport;
using hexapod_hardware::MAX_PAYLOAD_LEN;
using hexapod_hardware::NUM_SERVOS;
using hexapod_hardware::opcode::ENABLE_SERVO;
using hexapod_hardware::opcode::GET_STATE;
using hexapod_hardware::opcode::RELAY_CONTROL;
using hexapod_hardware::opcode::RESET;
using hexapod_hardware::opcode::SET_TARGETS;
using hexapod_hardware::StatePayload;

// ============================================================================
// CRC-16/CCITT-FALSE
// ============================================================================

TEST(Crc16CcittFalse, SelfTestString123456789)
{
  // The canonical self-test vector for CRC-16/CCITT-FALSE.
  // Implementations that pass this match the spec; ones that don't, don't.
  const std::vector<uint8_t> data{'1', '2', '3', '4', '5', '6', '7', '8', '9'};
  EXPECT_EQ(crc16_ccitt_false(data.data(), data.size()), 0x29B1);
}

TEST(Crc16CcittFalse, EmptyInputEqualsInitValue)
{
  // Init register is 0xFFFF; with no data processed it stays 0xFFFF.
  EXPECT_EQ(crc16_ccitt_false(nullptr, 0), 0xFFFF);
}

TEST(Crc16CcittFalse, SingleByteIsDeterministic)
{
  // Sanity: same input always produces same output.
  const uint8_t b = 0xA5;
  const uint16_t c1 = crc16_ccitt_false(&b, 1);
  const uint16_t c2 = crc16_ccitt_false(&b, 1);
  EXPECT_EQ(c1, c2);
}

// ============================================================================
// COBS
// ============================================================================

TEST(Cobs, EmptyInput)
{
  // Empty data → one byte: a single block count of 1 (block contains only
  // the count byte itself, zero data bytes).
  auto enc = cobs_encode({});
  EXPECT_EQ(enc, (std::vector<uint8_t>{0x01}));

  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_TRUE(dec->empty());
}

TEST(Cobs, SingleZeroByte)
{
  // [0x00] → [0x01][0x01]: first block ends at the zero (count=1, no data),
  // then a terminating block with count=1 (no data after the implied zero).
  const std::vector<uint8_t> in{0x00};
  auto enc = cobs_encode(in);
  EXPECT_EQ(enc, (std::vector<uint8_t>{0x01, 0x01}));

  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, NoZerosShortBlock)
{
  const std::vector<uint8_t> in{0x11, 0x22, 0x33};
  auto enc = cobs_encode(in);
  // Single block of 4: count=0x04 then the three data bytes.
  EXPECT_EQ(enc, (std::vector<uint8_t>{0x04, 0x11, 0x22, 0x33}));

  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, ZeroInMiddle)
{
  const std::vector<uint8_t> in{0x11, 0x22, 0x00, 0x33};
  auto enc = cobs_encode(in);
  EXPECT_EQ(enc, (std::vector<uint8_t>{0x03, 0x11, 0x22, 0x02, 0x33}));

  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, RoundtripPreservesAllByteValues)
{
  // 256-byte sequence covering all possible byte values.
  std::vector<uint8_t> in;
  in.reserve(256);
  for (int i = 0; i < 256; ++i) {
    in.push_back(static_cast<uint8_t>(i));
  }
  auto enc = cobs_encode(in);
  // Encoded must never contain 0x00 (that's the whole point of COBS).
  for (uint8_t b : enc) {
    EXPECT_NE(b, 0);
  }

  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, BoundaryAt254NonZeroBytes)
{
  // 254 non-zero bytes exercises the 0xFF chain-extension branch.
  std::vector<uint8_t> in(254, 0xAB);
  auto enc = cobs_encode(in);
  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, BoundaryAt255NonZeroBytes)
{
  std::vector<uint8_t> in(255, 0xAB);
  auto enc = cobs_encode(in);
  auto dec = cobs_decode(enc);
  ASSERT_TRUE(dec.has_value());
  EXPECT_EQ(*dec, in);
}

TEST(Cobs, DecodeRejectsZeroByteInStream)
{
  // 0x00 inside the COBS stream is illegal — it should only appear as
  // the frame delimiter, which the caller strips before decoding.
  EXPECT_FALSE(cobs_decode({0x03, 0x11, 0x00, 0x22}).has_value());
}

TEST(Cobs, DecodeRejectsTruncatedBlock)
{
  // Count byte says 4 (so 3 data bytes should follow) but only 1 is present.
  EXPECT_FALSE(cobs_decode({0x04, 0x11}).has_value());
}

// ============================================================================
// encode_frame / decode_frame — round-trip and structural checks
// ============================================================================

TEST(Frame, EncodeEndsWithZeroDelimiter)
{
  auto wire = encode_get_state(0);
  ASSERT_FALSE(wire.empty());
  EXPECT_EQ(wire.back(), 0x00);
  // No other 0x00 inside the wire bytes (COBS guarantee).
  for (std::size_t i = 0; i + 1 < wire.size(); ++i) {
    EXPECT_NE(wire[i], 0x00) << "unexpected 0x00 at index " << i;
  }
}

TEST(Frame, RoundtripGetState)
{
  const uint8_t seq = 42;
  auto wire = encode_get_state(seq);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, seq);
  EXPECT_EQ(decoded->cmd, GET_STATE);
  EXPECT_TRUE(decoded->payload.empty());
}

TEST(Frame, RoundtripReset)
{
  auto wire = encode_reset(128);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 128);
  EXPECT_EQ(decoded->cmd, RESET);
  EXPECT_TRUE(decoded->payload.empty());
}

TEST(Frame, RoundtripEnableServo)
{
  auto wire = encode_enable_servo(7, /*servo_idx=*/5, /*enable=*/true);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 7);
  EXPECT_EQ(decoded->cmd, ENABLE_SERVO);
  ASSERT_EQ(decoded->payload.size(), 2u);
  EXPECT_EQ(decoded->payload[0], 5);
  EXPECT_EQ(decoded->payload[1], 1);
}

TEST(Frame, RoundtripRelayControlOn)
{
  auto wire = encode_relay_control(7, /*on=*/true);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 7);
  EXPECT_EQ(decoded->cmd, RELAY_CONTROL);  // 0x51
  ASSERT_EQ(decoded->payload.size(), 1u);
  EXPECT_EQ(decoded->payload[0], 1);
}

TEST(Frame, RoundtripRelayControlOff)
{
  auto wire = encode_relay_control(200, /*on=*/false);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 200);
  EXPECT_EQ(decoded->cmd, RELAY_CONTROL);
  ASSERT_EQ(decoded->payload.size(), 1u);
  EXPECT_EQ(decoded->payload[0], 0);
}

TEST(Frame, RoundtripDisableServo)
{
  auto wire = encode_enable_servo(8, /*servo_idx=*/12, /*enable=*/false);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->payload[0], 12);
  EXPECT_EQ(decoded->payload[1], 0);
}

TEST(Frame, RoundtripSetTargetsAllNeutral)
{
  std::array<int16_t, NUM_SERVOS> pulses{};
  pulses.fill(1500);
  auto wire = encode_set_targets(0, pulses);

  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 0);
  EXPECT_EQ(decoded->cmd, SET_TARGETS);
  ASSERT_EQ(decoded->payload.size(), NUM_SERVOS * 2);

  // Each int16 LE should be DC 05 = 0x05DC = 1500.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    EXPECT_EQ(decoded->payload[i * 2], 0xDC) << "low byte servo " << i;
    EXPECT_EQ(decoded->payload[i * 2 + 1], 0x05) << "high byte servo " << i;
  }
}

TEST(Frame, RoundtripSetTargetsDistinctValues)
{
  // Each servo gets a unique pulse so we can spot index swaps if they happen.
  std::array<int16_t, NUM_SERVOS> pulses{};
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    pulses[i] = static_cast<int16_t>(1000 + 50 * i);
  }
  auto wire = encode_set_targets(99, pulses);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 99);
  EXPECT_EQ(decoded->cmd, SET_TARGETS);

  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const int16_t v = static_cast<int16_t>(
      static_cast<uint16_t>(decoded->payload[i * 2]) |
      static_cast<uint16_t>(decoded->payload[i * 2 + 1]) << 8);
    EXPECT_EQ(v, pulses[i]) << "mismatch at servo " << i;
  }
}

TEST(Frame, RoundtripSetTargetsNegativePulse)
{
  // int16 must survive negative values too — guard against unsigned coercion.
  std::array<int16_t, NUM_SERVOS> pulses{};
  pulses.fill(-1234);
  auto wire = encode_set_targets(1, pulses);
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const int16_t v = static_cast<int16_t>(
      static_cast<uint16_t>(decoded->payload[i * 2]) |
      static_cast<uint16_t>(decoded->payload[i * 2 + 1]) << 8);
    EXPECT_EQ(v, -1234);
  }
}

TEST(Frame, DecodeWithoutTrailingZeroAlsoWorks)
{
  // The reader may have already stripped the 0x00 delimiter when splitting
  // a stream into frames. Decoder must accept both with and without.
  auto wire = encode_get_state(11);
  ASSERT_EQ(wire.back(), 0x00);
  std::vector<uint8_t> without_zero(wire.begin(), wire.end() - 1);
  auto decoded = decode_frame(without_zero);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->seq, 11);
  EXPECT_EQ(decoded->cmd, GET_STATE);
}

TEST(Frame, DecodeRejectsCorruptedCrc)
{
  auto wire = encode_set_targets(0, {});
  // Flip a bit in the middle of the wire (not the delimiter).
  ASSERT_GT(wire.size(), 5u);
  wire[wire.size() / 2] ^= 0x01;
  EXPECT_FALSE(decode_frame(wire).has_value());
}

TEST(Frame, DecodeRejectsTruncatedFrame)
{
  auto wire = encode_get_state(0);
  wire.resize(wire.size() / 2);  // cut the frame in half
  EXPECT_FALSE(decode_frame(wire).has_value());
}

TEST(Frame, DecodeRejectsEmptyInput)
{
  EXPECT_FALSE(decode_frame({}).has_value());
  EXPECT_FALSE(decode_frame({0x00}).has_value());  // just a delimiter
}

TEST(Frame, EncodeFrameRejectsOversizedPayload)
{
  // LEN field is one byte; payload > MAX_PAYLOAD_LEN (253) would overflow
  // silently and corrupt the wire. Must throw, not "silently produce garbage".
  std::vector<uint8_t> oversized(MAX_PAYLOAD_LEN + 1, 0xAA);
  EXPECT_THROW(encode_frame(0, 0x01, oversized), std::invalid_argument);
}

TEST(Frame, EncodeFrameAcceptsMaxPayload)
{
  // Boundary on the other side: exactly MAX_PAYLOAD_LEN must work.
  std::vector<uint8_t> at_limit(MAX_PAYLOAD_LEN, 0xBB);
  std::vector<uint8_t> wire;
  EXPECT_NO_THROW(wire = encode_frame(0, 0x01, at_limit));
  auto decoded = decode_frame(wire);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->payload.size(), MAX_PAYLOAD_LEN);
}

// ============================================================================
// Golden hex vectors — generated by the Python reference implementation in
// ~/hexapod_servo_driver/tools/test_servo2040.py (which is independently
// verified against the firmware via end-to-end board tests in Phase 7).
//
// These tests anchor our C++ encoder against an independent implementation.
// If the C++ COBS or CRC routines had a matching bug to their decoder, the
// roundtrip tests above would pass but real wire transmission would fail.
// These tests catch that class of error.
//
// To regenerate after a protocol change, run:
//   cd ~/hexapod_servo_driver/tools && python3 -c "
//   from test_servo2040 import encode_frame
//   print(encode_frame(0, 0x02, b'').hex())"
// and update the vectors below.
// ============================================================================

TEST(GoldenHex, EncodeGetStateSeq0)
{
  // Python reference: encode_frame(seq=0, cmd=0x02, payload=b'')
  // → 01 02 02 03 fe aa 00
  const std::vector<uint8_t> expected{0x01, 0x02, 0x02, 0x03, 0xFE, 0xAA, 0x00};
  EXPECT_EQ(encode_get_state(0), expected);
}

TEST(GoldenHex, EncodeGetStateSeq1)
{
  // Python reference: encode_frame(seq=1, cmd=0x02, payload=b'')
  // → 03 01 02 03 ce 9d 00
  const std::vector<uint8_t> expected{0x03, 0x01, 0x02, 0x03, 0xCE, 0x9D, 0x00};
  EXPECT_EQ(encode_get_state(1), expected);
}

TEST(GoldenHex, EncodeResetSeq3)
{
  // Python reference: encode_frame(seq=3, cmd=0x50, payload=b'')
  // → 03 03 50 03 73 9b 00
  const std::vector<uint8_t> expected{0x03, 0x03, 0x50, 0x03, 0x73, 0x9B, 0x00};
  EXPECT_EQ(encode_reset(3), expected);
}

TEST(GoldenHex, EncodeEnableServoSeq2Idx5On)
{
  // Python reference: encode_frame(seq=2, cmd=0x20, payload=bytes([5, 1]))
  // → 08 02 20 02 05 01 75 e3 00
  const std::vector<uint8_t> expected{
    0x08, 0x02, 0x20, 0x02, 0x05, 0x01, 0x75, 0xE3, 0x00};
  EXPECT_EQ(encode_enable_servo(2, 5, true), expected);
}

TEST(GoldenHex, EncodeSetTargetsAllNeutral)
{
  // Python reference: encode_frame(seq=0, cmd=0x01, payload=b'\xDC\x05' * 18)
  // → 01 29 01 24 (dc 05)×18 5f b6 00
  std::array<int16_t, NUM_SERVOS> pulses{};
  pulses.fill(1500);
  const std::vector<uint8_t> expected{
    0x01, 0x29, 0x01, 0x24,
    0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05,
    0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05,
    0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05, 0xDC, 0x05,
    0x5F, 0xB6, 0x00};
  EXPECT_EQ(encode_set_targets(0, pulses), expected);
}

// ============================================================================
// Payload decoders
// ============================================================================

TEST(PayloadDecoders, DecodeStateValid)
{
  // Build a 75-byte STATE payload by hand:
  // 18× int16 LE pulse = (1500, 1501, ..., 1517)
  // 18× uint16 LE current_mA = (100, 110, ..., 270)
  // voltage_mV = 6000 (LE: 0x70, 0x17)
  // status_flags = 0x04 (TOTAL_OVERCURRENT_TRIPPED)
  std::vector<uint8_t> payload;
  payload.reserve(75);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const int16_t v = static_cast<int16_t>(1500 + i);
    payload.push_back(static_cast<uint8_t>(v & 0xFF));
    payload.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
  }
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const uint16_t v = static_cast<uint16_t>(100 + 10 * i);
    payload.push_back(static_cast<uint8_t>(v & 0xFF));
    payload.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
  }
  payload.push_back(0x70);  // voltage low
  payload.push_back(0x17);  // voltage high (0x1770 = 6000)
  payload.push_back(0x04);  // status

  auto decoded = decode_state(payload);
  ASSERT_TRUE(decoded.has_value());
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    EXPECT_EQ(decoded->last_pulse_us[i], static_cast<int16_t>(1500 + i));
    EXPECT_EQ(decoded->last_current_ma[i], static_cast<uint16_t>(100 + 10 * i));
  }
  EXPECT_EQ(decoded->voltage_mv, 6000);
  EXPECT_EQ(decoded->status_flags, 0x04);
}

TEST(PayloadDecoders, DecodeStateRejectsWrongLength)
{
  EXPECT_FALSE(decode_state({}).has_value());
  EXPECT_FALSE(decode_state(std::vector<uint8_t>(74, 0)).has_value());
  EXPECT_FALSE(decode_state(std::vector<uint8_t>(76, 0)).has_value());
}

TEST(PayloadDecoders, DecodeErrorReportValid)
{
  // error_code = 0x10 (PULSE_OUT_OF_RANGE), servo_idx = 5,
  // aux = -100 (LE: 0x9C 0xFF)
  const std::vector<uint8_t> payload{0x10, 0x05, 0x9C, 0xFF};
  auto decoded = decode_error_report(payload);
  ASSERT_TRUE(decoded.has_value());
  EXPECT_EQ(decoded->error_code, 0x10);
  EXPECT_EQ(decoded->servo_idx, 5);
  EXPECT_EQ(decoded->aux, -100);
}

TEST(PayloadDecoders, DecodeErrorReportRejectsWrongLength)
{
  EXPECT_FALSE(decode_error_report({}).has_value());
  EXPECT_FALSE(decode_error_report({0x10, 0x05, 0x00}).has_value());     // 3
  EXPECT_FALSE(decode_error_report({0x10, 0x05, 0x00, 0x00, 0}).has_value());  // 5
}

// ============================================================================
// End-to-end: encode a STATE frame, decode through both layers
// ============================================================================

TEST(EndToEnd, EncodeStateFrameDecodeBothLayers)
{
  // Build a 75-byte STATE payload (all zero pulses, all zero current,
  // voltage 7500 mV, status WATCHDOG_TRIPPED).
  std::vector<uint8_t> payload(75, 0);
  payload[NUM_SERVOS * 4 + 0] = 0x4C;  // 0x1D4C = 7500 (LE: 0x4C 0x1D)
  payload[NUM_SERVOS * 4 + 1] = 0x1D;
  payload[NUM_SERVOS * 4 + 2] = 0x01;  // WATCHDOG_TRIPPED

  auto wire = encode_frame(/*seq=*/3, /*cmd=*/0x82, payload);  // STATE_RESPONSE
  auto frame = decode_frame(wire);
  ASSERT_TRUE(frame.has_value());
  EXPECT_EQ(frame->seq, 3);
  EXPECT_EQ(frame->cmd, 0x82);

  auto state = decode_state(frame->payload);
  ASSERT_TRUE(state.has_value());
  EXPECT_EQ(state->voltage_mv, 7500);
  EXPECT_EQ(state->status_flags & 0x01, 0x01);  // WATCHDOG_TRIPPED bit set
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
