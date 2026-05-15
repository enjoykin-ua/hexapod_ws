// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for SerialPort. Uses openpty(3) to make a master/slave PTY
// pair: the slave end is adopted by SerialPort (= what the plugin sees in
// production); the master end is what the test pretends to be — the
// Servo2040 firmware echoing bytes back.

#include <gtest/gtest.h>

#include <fcntl.h>
#include <pty.h>
#include <termios.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <system_error>
#include <thread>
#include <vector>

#include "hexapod_hardware/serial_port.hpp"

using hexapod_hardware::SerialPort;

namespace
{

// Test fixture: opens a fresh PTY pair for each test, closes both ends
// at teardown. SerialPort adopts the slave FD.
class SerialPortPty : public ::testing::Test
{
protected:
  void SetUp() override
  {
    ASSERT_EQ(::openpty(&master_fd_, &slave_fd_, nullptr, nullptr, nullptr), 0)
      << "openpty failed: " << ::strerror(errno);
    // The master end stays in cooked-ish defaults. Force it to raw mode so
    // the loopback isn't doing CR/LF mangling on what *we* write (we want
    // to test that SerialPort's own cfmakeraw works, not the master end).
    struct termios m;
    ASSERT_EQ(::tcgetattr(master_fd_, &m), 0);
    ::cfmakeraw(&m);
    ASSERT_EQ(::tcsetattr(master_fd_, TCSANOW, &m), 0);
    port_.adopt_fd(slave_fd_);
  }

  void TearDown() override
  {
    port_.close();
    if (master_fd_ >= 0) {
      ::close(master_fd_);
    }
    // slave_fd_ is owned by `port_` after adopt_fd; close() handled it.
  }

  // Helper: write to master end (the "firmware" side).
  void master_write(const std::vector<uint8_t> & data)
  {
    const ssize_t n = ::write(master_fd_, data.data(), data.size());
    ASSERT_EQ(static_cast<std::size_t>(n), data.size());
  }

  int master_fd_{-1};
  int slave_fd_{-1};
  SerialPort port_;
};

}  // namespace

// ============================================================================
// Basic lifecycle
// ============================================================================

TEST(SerialPortLifecycle, IsClosedAfterDefaultConstruction)
{
  SerialPort p;
  EXPECT_FALSE(p.is_open());
}

TEST(SerialPortLifecycle, AdoptFdMakesItOpen)
{
  int master, slave;
  ASSERT_EQ(::openpty(&master, &slave, nullptr, nullptr, nullptr), 0);
  SerialPort p;
  p.adopt_fd(slave);
  EXPECT_TRUE(p.is_open());
  p.close();
  EXPECT_FALSE(p.is_open());
  ::close(master);
}

TEST(SerialPortLifecycle, CloseIsIdempotent)
{
  SerialPort p;
  p.close();
  p.close();  // must not throw
  EXPECT_FALSE(p.is_open());
}

TEST(SerialPortLifecycle, DoubleAdoptThrows)
{
  int m1, s1, m2, s2;
  ASSERT_EQ(::openpty(&m1, &s1, nullptr, nullptr, nullptr), 0);
  ASSERT_EQ(::openpty(&m2, &s2, nullptr, nullptr, nullptr), 0);
  SerialPort p;
  p.adopt_fd(s1);
  EXPECT_THROW(p.adopt_fd(s2), std::runtime_error);
  p.close();
  ::close(m1);
  ::close(m2);
  ::close(s2);  // p didn't adopt s2, we still own it
}

TEST(SerialPortLifecycle, OpenNonexistentPathThrowsSystemError)
{
  SerialPort p;
  try {
    p.open("/dev/this_path_should_not_exist_42_xyz");
    FAIL() << "expected throw";
  } catch (const std::system_error & e) {
    EXPECT_EQ(e.code().value(), ENOENT);
    // Message must mention the path so the user can diagnose.
    EXPECT_NE(std::string(e.what()).find("this_path_should_not_exist_42_xyz"),
      std::string::npos);
  }
}

// ============================================================================
// Roundtrip — all 256 byte values must survive
// ============================================================================

TEST_F(SerialPortPty, RoundtripAll256ByteValues)
{
  std::vector<uint8_t> sent(256);
  for (int i = 0; i < 256; ++i) {
    sent[i] = static_cast<uint8_t>(i);
  }
  master_write(sent);

  std::vector<uint8_t> received;
  received.reserve(256);
  uint8_t buf[64];
  // PTY layer may deliver in chunks; loop until we have 256 bytes or timeout.
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
  while (received.size() < 256 && std::chrono::steady_clock::now() < deadline) {
    const std::size_t n = port_.read_some(buf, sizeof(buf));
    received.insert(received.end(), buf, buf + n);
  }
  ASSERT_EQ(received.size(), 256u);
  EXPECT_EQ(received, sent);
}

// ============================================================================
// cfmakeraw verification — 0x0D and 0x0A must NOT be remapped
//
// This is the test that catches the Phase-7 C.4 bug class. If cfmakeraw
// isn't applied, the kernel's ICRNL/ONLCR mangles 0x0D <-> 0x0A and the
// COBS+CRC protocol breaks silently every time a CRC byte happens to be
// 0x0D.
// ============================================================================

TEST_F(SerialPortPty, CarriageReturnSurvivesByteExact)
{
  master_write({0x0D});
  uint8_t buf[4] = {0};
  std::size_t total = 0;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
  while (total == 0 && std::chrono::steady_clock::now() < deadline) {
    total = port_.read_some(buf, sizeof(buf));
  }
  ASSERT_EQ(total, 1u);
  EXPECT_EQ(buf[0], 0x0D) << "if this is 0x0A, ICRNL is still active — cfmakeraw missing";
}

TEST_F(SerialPortPty, LineFeedSurvivesByteExact)
{
  master_write({0x0A});
  uint8_t buf[4] = {0};
  std::size_t total = 0;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
  while (total == 0 && std::chrono::steady_clock::now() < deadline) {
    total = port_.read_some(buf, sizeof(buf));
  }
  ASSERT_EQ(total, 1u);
  EXPECT_EQ(buf[0], 0x0A);
}

TEST_F(SerialPortPty, MixedCrLfSequencesSurviveExact)
{
  const std::vector<uint8_t> sent{0x0D, 0x0A, 0x0D, 0x0D, 0x0A, 0x00, 0x0A, 0x0D};
  master_write(sent);
  std::vector<uint8_t> received;
  uint8_t buf[16];
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
  while (received.size() < sent.size() && std::chrono::steady_clock::now() < deadline) {
    const std::size_t n = port_.read_some(buf, sizeof(buf));
    received.insert(received.end(), buf, buf + n);
  }
  ASSERT_EQ(received.size(), sent.size());
  EXPECT_EQ(received, sent);
}

// ============================================================================
// Read timeout — returns 0 if no data within READ_TIMEOUT_MS
// ============================================================================

TEST_F(SerialPortPty, ReadSomeReturnsZeroOnTimeout)
{
  // Don't write anything from master. read_some should return 0 after
  // the internal 1 s timeout. (We accept anything <= 1.5 s here to
  // tolerate scheduling jitter.)
  uint8_t buf[16];
  const auto t0 = std::chrono::steady_clock::now();
  const std::size_t n = port_.read_some(buf, sizeof(buf));
  const auto dt = std::chrono::steady_clock::now() - t0;
  EXPECT_EQ(n, 0u);
  EXPECT_GE(dt, std::chrono::milliseconds(900));
  EXPECT_LE(dt, std::chrono::milliseconds(1500));
}

// ============================================================================
// Write — basic case
// ============================================================================

TEST_F(SerialPortPty, WriteAllDeliversAllBytes)
{
  const std::vector<uint8_t> payload{0x01, 0x02, 0xFE, 0xFF, 0x00, 0x42};
  ASSERT_NO_THROW(port_.write_all(payload.data(), payload.size()));
  // Read from the master side to verify.
  std::vector<uint8_t> received(payload.size(), 0);
  std::size_t total = 0;
  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
  while (total < payload.size() && std::chrono::steady_clock::now() < deadline) {
    const ssize_t n = ::read(master_fd_, received.data() + total,
        received.size() - total);
    if (n > 0) {
      total += static_cast<std::size_t>(n);
    } else if (n < 0 && errno != EAGAIN && errno != EINTR) {
      FAIL() << "master read failed: " << ::strerror(errno);
    }
  }
  ASSERT_EQ(total, payload.size());
  EXPECT_EQ(received, payload);
}

// ============================================================================
// write_all error: port not open
// ============================================================================

TEST(SerialPortError, WriteOnClosedPortThrows)
{
  SerialPort p;
  uint8_t b = 0x42;
  EXPECT_THROW(p.write_all(&b, 1), std::runtime_error);
}

TEST(SerialPortError, ReadOnClosedPortThrows)
{
  SerialPort p;
  uint8_t b;
  EXPECT_THROW(p.read_some(&b, 1), std::runtime_error);
}

// ============================================================================
// exclusive_lock contention — verifies the shared_mutex actually serializes
// the reconnect path against concurrent writes.
//
// Scenario: one thread holds the exclusive_lock for 200 ms (simulated
// reconnect). Another thread calls write_all() — it must block until the
// exclusive lock is released, but eventually succeed.
// ============================================================================

TEST_F(SerialPortPty, WriteBlocksUntilExclusiveLockReleased)
{
  std::atomic<bool> writer_returned{false};
  std::chrono::steady_clock::time_point write_done_at;

  // Hold the exclusive lock for ~200 ms.
  auto excl = port_.exclusive_lock();
  const auto t_lock_acquired = std::chrono::steady_clock::now();

  std::thread writer([&]() {
      const uint8_t b = 0xAB;
      port_.write_all(&b, 1);   // must block until we release excl
      write_done_at = std::chrono::steady_clock::now();
      writer_returned = true;
    });

  std::this_thread::sleep_for(std::chrono::milliseconds(200));
  EXPECT_FALSE(writer_returned) << "writer must NOT have returned while exclusive_lock held";

  // Release the lock.
  excl.unlock();
  writer.join();
  EXPECT_TRUE(writer_returned);
  EXPECT_GE(write_done_at - t_lock_acquired, std::chrono::milliseconds(200))
    << "writer returned too soon — exclusive_lock didn't actually block it";

  // Drain the byte from the master end.
  uint8_t buf[4];
  ::read(master_fd_, buf, sizeof(buf));
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
