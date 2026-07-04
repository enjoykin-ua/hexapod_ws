// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Implementation of the Servo2040 wire protocol on the host side.
// Cross-verified against ~/hexapod_servo_driver/src/proto/*.cpp and
// the Python reference in ~/hexapod_servo_driver/tools/test_servo2040.py.
// See ~/hexapod_servo_driver/PROTOCOL.md for the wire format.

#include "hexapod_hardware/servo2040_protocol.hpp"

#include <stdexcept>
#include <string>

namespace hexapod_hardware
{

// ---------------------------------------------------------------------------
// CRC-16/CCITT-FALSE — poly 0x1021, init 0xFFFF, no reflect, xorout 0x0000.
// Self-test: crc16("123456789") == 0x29B1. Bit-by-bit implementation; the
// host is not throughput-bound and the table version saves ~80 ns/frame
// at 50 Hz — not worth the 512 B static table.
// ---------------------------------------------------------------------------
uint16_t crc16_ccitt_false(const uint8_t * data, std::size_t len)
{
  uint16_t crc = 0xFFFF;
  for (std::size_t i = 0; i < len; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (int bit = 0; bit < 8; ++bit) {
      if (crc & 0x8000) {
        crc = static_cast<uint16_t>((crc << 1) ^ 0x1021);
      } else {
        crc = static_cast<uint16_t>(crc << 1);
      }
    }
  }
  return crc;
}

// ---------------------------------------------------------------------------
// COBS — Consistent Overhead Byte Stuffing.
// Reference: Cheshire & Baker, 1999. The encoded output contains no 0x00
// bytes; the caller appends a single 0x00 as frame delimiter. Overhead
// is at most ⌈n/254⌉ bytes for n input bytes.
// ---------------------------------------------------------------------------
std::vector<uint8_t> cobs_encode(const std::vector<uint8_t> & input)
{
  std::vector<uint8_t> out;
  out.reserve(input.size() + input.size() / 254 + 2);

  // Lay down a placeholder for the first block's count byte; we'll fill
  // it in once we know how many non-zero bytes followed.
  std::size_t block_start = out.size();
  out.push_back(0);
  uint8_t block_len = 1;  // includes the count byte itself

  for (uint8_t b : input) {
    if (b == 0) {
      // Close current block at the zero.
      out[block_start] = block_len;
      block_start = out.size();
      out.push_back(0);
      block_len = 1;
    } else {
      out.push_back(b);
      ++block_len;
      if (block_len == 0xFF) {
        // Maximal-length run with no zero — special "chain extension"
        // block. No implicit zero is added by the decoder for 0xFF.
        out[block_start] = 0xFF;
        block_start = out.size();
        out.push_back(0);
        block_len = 1;
      }
    }
  }
  out[block_start] = block_len;
  return out;
}

std::optional<std::vector<uint8_t>> cobs_decode(const std::vector<uint8_t> & input)
{
  std::vector<uint8_t> out;
  out.reserve(input.size());

  std::size_t i = 0;
  const std::size_t n = input.size();
  while (i < n) {
    const uint8_t count = input[i];
    if (count == 0) {
      // 0x00 inside the COBS stream is illegal — it should only appear
      // as the frame delimiter, which the caller strips.
      return std::nullopt;
    }
    ++i;
    // The next (count - 1) bytes are literal data.
    for (uint8_t j = 1; j < count; ++j) {
      if (i >= n) {
        return std::nullopt;  // truncated block
      }
      out.push_back(input[i]);
      ++i;
    }
    // After a regular block (count 1..254) the decoder injects an
    // implicit 0x00 — unless this was the *final* block of the message.
    // Count 0xFF is the chain-extension block: no implicit zero.
    if (i < n && count < 0xFF) {
      out.push_back(0);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Frame encode / decode.
// Pre-COBS layout (PROTOCOL.md §2.3):
//   [SEQ:1][CMD:1][LEN:1][PAYLOAD:LEN][CRC16-LE:2]
// CRC is computed over SEQ ‖ CMD ‖ LEN ‖ PAYLOAD.
// ---------------------------------------------------------------------------
std::vector<uint8_t> encode_frame(
  uint8_t seq, uint8_t cmd,
  const std::vector<uint8_t> & payload)
{
  if (payload.size() > MAX_PAYLOAD_LEN) {
    throw std::invalid_argument(
            "hexapod_hardware::encode_frame: payload size " +
            std::to_string(payload.size()) +
            " exceeds MAX_PAYLOAD_LEN=" + std::to_string(MAX_PAYLOAD_LEN));
  }
  std::vector<uint8_t> pre_cobs;
  pre_cobs.reserve(payload.size() + 5);
  pre_cobs.push_back(seq);
  pre_cobs.push_back(cmd);
  pre_cobs.push_back(static_cast<uint8_t>(payload.size()));
  pre_cobs.insert(pre_cobs.end(), payload.begin(), payload.end());

  const uint16_t crc = crc16_ccitt_false(pre_cobs.data(), pre_cobs.size());
  pre_cobs.push_back(static_cast<uint8_t>(crc & 0xFF));         // LE: low byte
  pre_cobs.push_back(static_cast<uint8_t>((crc >> 8) & 0xFF));  // LE: high byte

  std::vector<uint8_t> wire = cobs_encode(pre_cobs);
  wire.push_back(0);  // frame delimiter
  return wire;
}

std::optional<DecodedFrame> decode_frame(const std::vector<uint8_t> & cobs_bytes)
{
  // Tolerate (but don't require) a trailing 0x00 delimiter.
  std::vector<uint8_t> trimmed = cobs_bytes;
  if (!trimmed.empty() && trimmed.back() == 0) {
    trimmed.pop_back();
  }
  if (trimmed.empty()) {
    return std::nullopt;
  }

  auto decoded = cobs_decode(trimmed);
  if (!decoded.has_value()) {
    return std::nullopt;
  }
  const std::vector<uint8_t> & inner = *decoded;

  // Minimum: SEQ + CMD + LEN + (LEN=0) + CRC16 = 5 bytes
  if (inner.size() < 5) {
    return std::nullopt;
  }

  const uint8_t seq = inner[0];
  const uint8_t cmd = inner[1];
  const uint8_t len = inner[2];

  // Total expected length: 3 header + len payload + 2 CRC
  if (inner.size() != static_cast<std::size_t>(3 + len + 2)) {
    return std::nullopt;
  }

  // CRC is over SEQ ‖ CMD ‖ LEN ‖ PAYLOAD (everything except the CRC itself).
  const uint16_t computed_crc = crc16_ccitt_false(inner.data(), 3 + len);
  const uint16_t received_crc =
    static_cast<uint16_t>(inner[3 + len]) |
    static_cast<uint16_t>(inner[3 + len + 1]) << 8;
  if (computed_crc != received_crc) {
    return std::nullopt;
  }

  DecodedFrame out;
  out.seq = seq;
  out.cmd = cmd;
  out.payload.assign(inner.begin() + 3, inner.begin() + 3 + len);
  return out;
}

// ---------------------------------------------------------------------------
// Specialised encoders (thin wrappers around encode_frame).
// ---------------------------------------------------------------------------
std::vector<uint8_t> encode_set_targets(
  uint8_t seq,
  const std::array<int16_t, NUM_SERVOS> & pulse_us)
{
  std::vector<uint8_t> payload;
  payload.reserve(NUM_SERVOS * 2);
  for (int16_t p : pulse_us) {
    payload.push_back(static_cast<uint8_t>(p & 0xFF));
    payload.push_back(static_cast<uint8_t>((p >> 8) & 0xFF));
  }
  return encode_frame(seq, opcode::SET_TARGETS, payload);
}

std::vector<uint8_t> encode_get_state(uint8_t seq)
{
  return encode_frame(seq, opcode::GET_STATE, {});
}

std::vector<uint8_t> encode_get_inputs(uint8_t seq)
{
  return encode_frame(seq, opcode::GET_INPUTS, {});
}

std::vector<uint8_t> encode_enable_servo(uint8_t seq, uint8_t servo_idx, bool enable)
{
  std::vector<uint8_t> payload{servo_idx, static_cast<uint8_t>(enable ? 1 : 0)};
  return encode_frame(seq, opcode::ENABLE_SERVO, payload);
}

std::vector<uint8_t> encode_reset(uint8_t seq)
{
  return encode_frame(seq, opcode::RESET, {});
}

std::vector<uint8_t> encode_relay_control(uint8_t seq, bool on)
{
  std::vector<uint8_t> payload{static_cast<uint8_t>(on ? 1 : 0)};
  return encode_frame(seq, opcode::RELAY_CONTROL, payload);
}

// ---------------------------------------------------------------------------
// Payload decoders. Layout per PROTOCOL.md §3.1 / §3.4.
// ---------------------------------------------------------------------------
std::optional<StatePayload> decode_state(const std::vector<uint8_t> & payload)
{
  // 18 × int16 LE last_pulse  (36 B)
  // 18 × uint16 LE last_current_ma  (36 B)
  //  1 × uint16 LE voltage_mv  (2 B)
  //  1 × uint8  status_flags   (1 B)
  // Total: 75 B
  constexpr std::size_t expected_len = NUM_SERVOS * 2 + NUM_SERVOS * 2 + 2 + 1;
  if (payload.size() != expected_len) {
    return std::nullopt;
  }

  StatePayload out;
  std::size_t offset = 0;
  // Note on the uint16 → int16 casts below: pre-C++20 the conversion of an
  // unsigned value > INT16_MAX to int16_t is implementation-defined. On every
  // platform we ship to (x86_64 Linux, ARM64 Linux) this is well-defined two's-
  // complement wrap, which is exactly the wire format. Same idiom as the
  // firmware reference in ~/hexapod_servo_driver/src/main.cpp.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    out.last_pulse_us[i] = static_cast<int16_t>(
      static_cast<uint16_t>(payload[offset]) |
      static_cast<uint16_t>(payload[offset + 1]) << 8);
    offset += 2;
  }
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    out.last_current_ma[i] = static_cast<uint16_t>(
      static_cast<uint16_t>(payload[offset]) |
      static_cast<uint16_t>(payload[offset + 1]) << 8);
    offset += 2;
  }
  out.voltage_mv = static_cast<uint16_t>(
    static_cast<uint16_t>(payload[offset]) |
    static_cast<uint16_t>(payload[offset + 1]) << 8);
  offset += 2;
  out.status_flags = payload[offset];
  return out;
}

std::optional<ErrorReport> decode_error_report(const std::vector<uint8_t> & payload)
{
  // PROTOCOL.md §3.4: error_code (u8), servo_idx (u8), aux (int16 LE) = 4 B
  if (payload.size() != 4) {
    return std::nullopt;
  }
  ErrorReport out;
  out.error_code = payload[0];
  out.servo_idx = payload[1];
  out.aux = static_cast<int16_t>(
    static_cast<uint16_t>(payload[2]) |
    static_cast<uint16_t>(payload[3]) << 8);
  return out;
}

std::optional<uint8_t> decode_inputs(const std::vector<uint8_t> & payload)
{
  // PROTOCOL.md §3.2: single-byte debounced input bitmask.
  if (payload.size() != 1) {
    return std::nullopt;
  }
  return payload[0];
}

}  // namespace hexapod_hardware
