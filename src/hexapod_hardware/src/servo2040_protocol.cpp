// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#include "hexapod_hardware/servo2040_protocol.hpp"

namespace hexapod_hardware
{

// Stage B fills these in. Stub returns empty/nullopt for now so the
// package compiles and links cleanly in stage A.

std::vector<uint8_t> encode_set_targets(uint8_t, const std::array<int16_t, NUM_SERVOS> &)
{
  return {};
}

std::vector<uint8_t> encode_get_state(uint8_t)
{
  return {};
}

std::vector<uint8_t> encode_enable_servo(uint8_t, uint8_t, bool)
{
  return {};
}

std::vector<uint8_t> encode_reset(uint8_t)
{
  return {};
}

std::optional<StatePayload> decode_state(const std::vector<uint8_t> &)
{
  return std::nullopt;
}

std::optional<ErrorReport> decode_error_report(const std::vector<uint8_t> &)
{
  return std::nullopt;
}

uint16_t crc16_ccitt_false(const uint8_t *, std::size_t)
{
  return 0;
}

std::vector<uint8_t> cobs_encode(const std::vector<uint8_t> &)
{
  return {};
}

std::optional<std::vector<uint8_t>> cobs_decode(const std::vector<uint8_t> &)
{
  return std::nullopt;
}

}  // namespace hexapod_hardware
