// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for Servo2040Reader. Uses openpty(3) to simulate the
// firmware side: the master end is what we (the "firmware") write
// frames into; the slave end is adopted by SerialPort, which the reader
// consumes.

#include <gtest/gtest.h>

#include <fcntl.h>
#include <pty.h>
#include <termios.h>
#include <unistd.h>

#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <thread>
#include <vector>

#include "hexapod_hardware/serial_port.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"
#include "hexapod_hardware/servo2040_reader.hpp"

using hexapod_hardware::DecodedFrame;
using hexapod_hardware::encode_enable_servo;
using hexapod_hardware::encode_frame;
using hexapod_hardware::ErrorReport;
using hexapod_hardware::NUM_SERVOS;
using hexapod_hardware::opcode::ACK;
using hexapod_hardware::opcode::ERROR_REPORT;
using hexapod_hardware::opcode::NACK;
using hexapod_hardware::opcode::STATE_RESPONSE;
using hexapod_hardware::SerialPort;
using hexapod_hardware::Servo2040Reader;
using hexapod_hardware::StatePayload;

namespace
{

class ReaderPty : public ::testing::Test
{
protected:
  void SetUp() override
  {
    ASSERT_EQ(::openpty(&master_fd_, &slave_fd_, nullptr, nullptr, nullptr), 0)
      << "openpty failed: " << ::strerror(errno);
    struct termios m;
    ASSERT_EQ(::tcgetattr(master_fd_, &m), 0);
    ::cfmakeraw(&m);
    ASSERT_EQ(::tcsetattr(master_fd_, TCSANOW, &m), 0);
    port_.adopt_fd(slave_fd_);
    reader_.start(port_);
  }

  void TearDown() override
  {
    reader_.stop();
    port_.close();
    if (master_fd_ >= 0) {
      ::close(master_fd_);
    }
  }

  // Write raw bytes onto the master end (= what the firmware would send).
  void firmware_send(const std::vector<uint8_t> & data)
  {
    const ssize_t n = ::write(master_fd_, data.data(), data.size());
    ASSERT_EQ(static_cast<std::size_t>(n), data.size());
  }

  // Wait up to timeout_ms for `predicate` to become true, with light polling.
  template<typename Pred>
  bool wait_for(Pred predicate, int timeout_ms = 2000)
  {
    const auto deadline = std::chrono::steady_clock::now() +
      std::chrono::milliseconds(timeout_ms);
    while (std::chrono::steady_clock::now() < deadline) {
      if (predicate()) {return true;}
      std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    return predicate();
  }

  // Build a 75-byte STATE payload with the given voltage / status.
  std::vector<uint8_t> build_state_payload(uint16_t voltage_mv, uint8_t status_flags)
  {
    std::vector<uint8_t> p(75, 0);
    // pulse (36 B) + current (36 B) all zero → bytes 0..71 stay 0
    p[72] = static_cast<uint8_t>(voltage_mv & 0xFF);
    p[73] = static_cast<uint8_t>((voltage_mv >> 8) & 0xFF);
    p[74] = status_flags;
    return p;
  }

  int master_fd_{-1};
  int slave_fd_{-1};
  SerialPort port_;
  Servo2040Reader reader_;
};

}  // namespace

// ============================================================================
// Lifecycle
// ============================================================================

TEST(ReaderLifecycle, IsRunningAfterStartFalseAfterStop)
{
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort port;
  port.adopt_fd(slave);

  Servo2040Reader reader;
  EXPECT_FALSE(reader.is_running());
  reader.start(port);
  EXPECT_TRUE(reader.is_running());
  reader.stop();
  EXPECT_FALSE(reader.is_running());

  port.close();
  ::close(master);
}

TEST(ReaderLifecycle, DoubleStartThrows)
{
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort port;
  port.adopt_fd(slave);

  Servo2040Reader reader;
  reader.start(port);
  EXPECT_THROW(reader.start(port), std::runtime_error);
  reader.stop();
  port.close();
  ::close(master);
}

TEST(ReaderLifecycle, StopIsIdempotent)
{
  Servo2040Reader reader;
  reader.stop();   // never started
  reader.stop();   // double-stop
  EXPECT_FALSE(reader.is_running());
}

TEST(ReaderLifecycle, StopJoinsCleanlyWithin1500ms)
{
  // The reader's read_some has a 1 s timeout, so worst-case stop()
  // latency is just over 1 s. Verify it joins well under 1.5 s.
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort port;
  port.adopt_fd(slave);

  Servo2040Reader reader;
  reader.start(port);

  const auto t0 = std::chrono::steady_clock::now();
  reader.stop();
  const auto dt = std::chrono::steady_clock::now() - t0;

  EXPECT_LT(dt, std::chrono::milliseconds(1500))
    << "stop() took " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(dt).count() << " ms";

  port.close();
  ::close(master);
}

TEST(ReaderLifecycle, RepeatedStartStopLeavesNoThreadBehind)
{
  // The classic "thread leak" hazard: a thread that didn't get joined
  // shows up in the process's thread count. We do 5 start/stop cycles
  // and verify the same Reader instance ends up clean every time.
  // (We also rely on TSan / ASan to catch any double-free or join
  // hazards if the test is run under those sanitizers — out of scope here
  // but the test is structured to be sanitizer-friendly.)
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort port;
  port.adopt_fd(slave);

  Servo2040Reader reader;
  for (int i = 0; i < 5; ++i) {
    reader.start(port);
    EXPECT_TRUE(reader.is_running()) << "iteration " << i;
    // Send one frame to make sure the thread actually does work, not
    // just spins on read timeout.
    const std::vector<uint8_t> payload(75, 0);
    auto wire = encode_frame(/*seq=*/static_cast<uint8_t>(i), STATE_RESPONSE, payload);
    ::write(master, wire.data(), wire.size());
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    reader.stop();
    EXPECT_FALSE(reader.is_running()) << "iteration " << i;
    EXPECT_FALSE(reader.died()) << "iteration " << i;
  }
  port.close();
  ::close(master);
}

TEST(ReaderLifecycle, DestructorJoinsRunningThread)
{
  // If the reader is destroyed while running (e.g. the plugin gets
  // unloaded), the destructor must stop+join — no detached thread
  // wandering off into the heat death of the universe.
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort port;
  port.adopt_fd(slave);

  const auto t0 = std::chrono::steady_clock::now();
  {
    Servo2040Reader reader;
    reader.start(port);
    EXPECT_TRUE(reader.is_running());
    // Destructor runs at end of scope — must join.
  }
  const auto dt = std::chrono::steady_clock::now() - t0;
  EXPECT_LT(dt, std::chrono::milliseconds(1500))
    << "destructor took too long to join: " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(dt).count() << " ms";

  port.close();
  ::close(master);
}

// ============================================================================
// Frame dispatch
// ============================================================================

TEST_F(ReaderPty, StateFrameLandsInCache)
{
  // Send a STATE_RESPONSE from "firmware" side.
  auto payload = build_state_payload(/*voltage_mv=*/6000, /*status_flags=*/0x10);
  auto wire = encode_frame(/*seq=*/1, STATE_RESPONSE, payload);
  firmware_send(wire);

  ASSERT_TRUE(wait_for([&]() {return reader_.latest_state().has_value();}));
  auto s = reader_.latest_state();
  ASSERT_TRUE(s.has_value());
  EXPECT_EQ(s->voltage_mv, 6000);
  EXPECT_EQ(s->status_flags, 0x10);
}

TEST_F(ReaderPty, ErrorReportLandsInQueue)
{
  // ERROR_REPORT payload: error_code (u8), servo_idx (u8), aux (int16 LE)
  const std::vector<uint8_t> payload{0x40, 0x00, 0x00, 0x00};   // WATCHDOG_TRIPPED
  auto wire = encode_frame(/*seq=*/0, ERROR_REPORT, payload);
  firmware_send(wire);

  // We can't poll drain_error_queue() because it consumes — peek would
  // be nicer but the API is deliberately drain-only. Just give the
  // reader a moment to process and then drain once.
  std::this_thread::sleep_for(std::chrono::milliseconds(100));
  auto drained = reader_.drain_error_queue();
  ASSERT_EQ(drained.size(), 1u);
  EXPECT_EQ(drained[0].error_code, 0x40);   // WATCHDOG_TRIPPED
  EXPECT_EQ(drained[0].servo_idx, 0);
  EXPECT_EQ(drained[0].aux, 0);
}

TEST_F(ReaderPty, MultipleErrorReportsAccumulateInOrder)
{
  // Push three reports with distinct aux values, drain once, verify
  // ordering. We have to call drain only once at the end — drain_error_queue
  // consumes.
  for (int i = 0; i < 3; ++i) {
    const int16_t aux = static_cast<int16_t>(100 + i);
    const std::vector<uint8_t> p{
      0x10, static_cast<uint8_t>(i),
      static_cast<uint8_t>(aux & 0xFF),
      static_cast<uint8_t>((aux >> 8) & 0xFF)};
    firmware_send(encode_frame(/*seq=*/i, ERROR_REPORT, p));
  }

  // Wait for at least 3 reports to have arrived. We can't drain in
  // wait_for (would consume) so peek by re-running the loop until enough
  // accumulate. Reader is fast; ~50 ms is enough.
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  auto drained = reader_.drain_error_queue();
  ASSERT_EQ(drained.size(), 3u);
  EXPECT_EQ(drained[0].aux, 100);
  EXPECT_EQ(drained[1].aux, 101);
  EXPECT_EQ(drained[2].aux, 102);
  EXPECT_EQ(drained[0].servo_idx, 0);
  EXPECT_EQ(drained[1].servo_idx, 1);
  EXPECT_EQ(drained[2].servo_idx, 2);
}

TEST_F(ReaderPty, DrainConsumesQueue)
{
  const std::vector<uint8_t> p{0x40, 0x00, 0x00, 0x00};
  firmware_send(encode_frame(/*seq=*/0, ERROR_REPORT, p));
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  auto first = reader_.drain_error_queue();
  EXPECT_EQ(first.size(), 1u);

  auto second = reader_.drain_error_queue();
  EXPECT_TRUE(second.empty()) << "second drain should be empty after first consumed";
}

// ============================================================================
// Bad / unknown frames — must NOT poison the caches
// ============================================================================

TEST_F(ReaderPty, GarbageBytesAreDiscarded)
{
  // Wire-format-violating bytes: random non-zero bytes followed by 0x00.
  // decode_frame will reject because COBS / CRC / length all fail.
  firmware_send({0x11, 0x22, 0x33, 0x44, 0x00});
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  EXPECT_FALSE(reader_.latest_state().has_value());
  EXPECT_TRUE(reader_.drain_error_queue().empty());
  EXPECT_FALSE(reader_.died());
}

TEST_F(ReaderPty, UnknownOpcodeIsDiscarded)
{
  // Build a valid frame with an opcode we don't handle (e.g. 0x99).
  auto wire = encode_frame(/*seq=*/0, /*cmd=*/0x99, {0xAA, 0xBB});
  firmware_send(wire);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  EXPECT_FALSE(reader_.latest_state().has_value());
  EXPECT_TRUE(reader_.drain_error_queue().empty());
  EXPECT_FALSE(reader_.died());
}

TEST_F(ReaderPty, CorruptedCrcIsDiscarded)
{
  auto wire = encode_frame(/*seq=*/0, STATE_RESPONSE, build_state_payload(6000, 0));
  ASSERT_GT(wire.size(), 5u);
  // Flip a bit in the middle of the wire so CRC fails on decode.
  wire[wire.size() / 2] ^= 0x01;
  firmware_send(wire);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  EXPECT_FALSE(reader_.latest_state().has_value());
  EXPECT_FALSE(reader_.died());
}

TEST_F(ReaderPty, AckAndNackAreSilentlyAccepted)
{
  // ACK: 1-byte payload (original_cmd). Reader should log at DEBUG and
  // not poison any cache.
  firmware_send(encode_frame(/*seq=*/0, ACK, {0x01}));
  firmware_send(encode_frame(/*seq=*/1, NACK, {0x20, 0x40}));
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  EXPECT_FALSE(reader_.latest_state().has_value());
  EXPECT_TRUE(reader_.drain_error_queue().empty());
  EXPECT_FALSE(reader_.died());
}

// ============================================================================
// Stream-level robustness
// ============================================================================

TEST_F(ReaderPty, MultipleFramesBackToBackAllProcessed)
{
  auto state_wire = encode_frame(/*seq=*/0, STATE_RESPONSE,
      build_state_payload(5500, 0x02));
  std::vector<uint8_t> err_payload{0x21, 0x00, 0x10, 0x0E};   // TOTAL_OVERCURRENT 3600 mA
  auto err_wire = encode_frame(/*seq=*/1, ERROR_REPORT, err_payload);

  // Send STATE then ERROR_REPORT in one big write.
  std::vector<uint8_t> combined;
  combined.insert(combined.end(), state_wire.begin(), state_wire.end());
  combined.insert(combined.end(), err_wire.begin(), err_wire.end());
  firmware_send(combined);

  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  // STATE landed in cache:
  auto s = reader_.latest_state();
  ASSERT_TRUE(s.has_value());
  EXPECT_EQ(s->voltage_mv, 5500);
  EXPECT_EQ(s->status_flags, 0x02);

  // ERROR_REPORT landed in queue:
  auto errs = reader_.drain_error_queue();
  ASSERT_EQ(errs.size(), 1u);
  EXPECT_EQ(errs[0].error_code, 0x21);
  EXPECT_EQ(errs[0].aux, 0x0E10);
}

TEST_F(ReaderPty, ChunkedDeliveryIsReassembledCorrectly)
{
  // PTY may deliver the bytes in chunks. Force that by writing the
  // frame byte-by-byte with tiny pauses. Reader must still assemble
  // correctly.
  auto wire = encode_frame(/*seq=*/0, STATE_RESPONSE,
      build_state_payload(7100, 0x01));
  for (uint8_t b : wire) {
    firmware_send({b});
    std::this_thread::sleep_for(std::chrono::microseconds(100));
  }

  ASSERT_TRUE(wait_for([&]() {return reader_.latest_state().has_value();}));
  auto s = reader_.latest_state();
  EXPECT_EQ(s->voltage_mv, 7100);
}

TEST_F(ReaderPty, LoneDelimiterByteIsIgnored)
{
  // Stray 0x00 between frames (could happen if firmware emits a resync
  // byte, or if buffer boundary lands awkwardly) must not crash and must
  // not produce a bogus empty frame.
  firmware_send({0x00});
  std::this_thread::sleep_for(std::chrono::milliseconds(50));
  EXPECT_FALSE(reader_.died());
  EXPECT_FALSE(reader_.latest_state().has_value());
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
