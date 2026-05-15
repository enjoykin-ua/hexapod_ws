// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/serial_port.hpp"

#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>

#include <cerrno>
#include <cstring>
#include <mutex>
#include <stdexcept>
#include <system_error>

namespace hexapod_hardware
{

namespace
{

// Timeouts. See phase_9_stage_d_plan.md §D.1.
//   - WRITE_TIMEOUT_MS: how long we'll wait for the OS write buffer to drain.
//     50 ms = one full controller_manager tick @ 20 ms with headroom. If
//     POLLOUT doesn't fire by then, we treat the FD as wedged.
//   - READ_TIMEOUT_MS: how long read_some() blocks before returning 0.
//     1 s is long enough that idle USB-CDC traffic isn't a busy-loop and
//     short enough that the Reader-Thread checks its stop flag often.
constexpr int WRITE_TIMEOUT_MS = 50;
constexpr int READ_TIMEOUT_MS = 1000;

// errno values that mean "the device went away" — disconnect, treat as fatal.
bool is_disconnect_errno(int e)
{
  return e == EIO || e == ENXIO || e == ENODEV || e == EBADF;
}

}  // namespace

SerialPort::~SerialPort()
{
  close();
}

void SerialPort::open(const std::string & path)
{
  std::unique_lock<std::shared_mutex> lock(mtx_);
  if (fd_ >= 0) {
    throw std::runtime_error("SerialPort::open: port is already open");
  }
  const int fd = ::open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd < 0) {
    const int e = errno;
    throw std::system_error(
            e, std::system_category(),
            "SerialPort::open(" + path + ")");
  }
  fd_ = fd;
  try {
    configure_termios();
  } catch (...) {
    ::close(fd_);
    fd_ = -1;
    throw;
  }
}

void SerialPort::adopt_fd(int fd)
{
  std::unique_lock<std::shared_mutex> lock(mtx_);
  if (fd_ >= 0) {
    throw std::runtime_error("SerialPort::adopt_fd: port is already open");
  }
  if (fd < 0) {
    throw std::invalid_argument("SerialPort::adopt_fd: fd must be >= 0");
  }
  // Force O_NONBLOCK on the adopted FD; the caller may not have set it.
  int flags = ::fcntl(fd, F_GETFL, 0);
  if (flags < 0) {
    throw std::system_error(errno, std::system_category(), "SerialPort::adopt_fd: fcntl(F_GETFL)");
  }
  if (::fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) {
    throw std::system_error(errno, std::system_category(), "SerialPort::adopt_fd: fcntl(F_SETFL)");
  }
  fd_ = fd;
  try {
    configure_termios();
  } catch (...) {
    fd_ = -1;  // don't close — caller owned the FD before we did
    throw;
  }
}

void SerialPort::configure_termios()
{
  // Called with mtx_ already held (open / adopt_fd are the only callers).
  struct termios tio;
  if (::tcgetattr(fd_, &tio) < 0) {
    throw std::system_error(
            errno, std::system_category(), "SerialPort::configure_termios: tcgetattr");
  }
  // cfmakeraw clears: ICRNL, OPOST, ECHO, ICANON, IEXTEN, ISIG, IXON, INPCK,
  // ISTRIP, PARMRK; sets CS8. This is the canonical "treat the FD as a raw
  // byte stream" setup — without it ICRNL would turn an incoming 0x0D into
  // 0x0A on the way to us, which corrupts every frame whose CRC contains
  // 0x0D (this exact bug bit Phase 7 stage C.4).
  ::cfmakeraw(&tio);

  // VMIN/VTIME would only matter in blocking mode; we use O_NONBLOCK + poll
  // instead, but set them defensively so any future code that bypasses
  // poll() still has sane defaults (poll-driven, no character timer).
  tio.c_cc[VMIN] = 0;
  tio.c_cc[VTIME] = 0;

  // Baud rate is ignored by USB-CDC (the FT232/CDC-ACM driver doesn't
  // throttle on Bxxxxxx values) but we set something deterministic for
  // any future UART migration.
  ::cfsetispeed(&tio, B115200);
  ::cfsetospeed(&tio, B115200);

  if (::tcsetattr(fd_, TCSANOW, &tio) < 0) {
    throw std::system_error(
            errno, std::system_category(), "SerialPort::configure_termios: tcsetattr");
  }

  // Flush any garbage from the input buffer so the first read isn't a
  // pre-open boot banner or stale bytes from a previous connection.
  ::tcflush(fd_, TCIOFLUSH);
}

void SerialPort::close() noexcept
{
  std::unique_lock<std::shared_mutex> lock(mtx_);
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

bool SerialPort::is_open() const noexcept
{
  std::shared_lock<std::shared_mutex> lock(mtx_);
  return fd_ >= 0;
}

void SerialPort::write_all(const uint8_t * data, std::size_t len)
{
  std::shared_lock<std::shared_mutex> lock(mtx_);
  if (fd_ < 0) {
    throw std::runtime_error("SerialPort::write_all: port not open");
  }
  std::size_t total = 0;
  while (total < len) {
    struct pollfd pfd{};
    pfd.fd = fd_;
    pfd.events = POLLOUT;
    const int pr = ::poll(&pfd, 1, WRITE_TIMEOUT_MS);
    if (pr < 0) {
      if (errno == EINTR) {
        continue;  // signal interrupted poll, retry
      }
      throw std::system_error(errno, std::system_category(), "SerialPort::write_all: poll");
    }
    if (pr == 0) {
      throw std::system_error(
              std::make_error_code(std::errc::timed_out),
              "SerialPort::write_all: timed out after " +
              std::to_string(WRITE_TIMEOUT_MS) + " ms (USB-CDC buffer wedged?)");
    }
    if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
      throw std::system_error(
              EIO, std::system_category(),
              "SerialPort::write_all: poll reported POLLERR/HUP/NVAL (disconnect)");
    }
    const ssize_t n = ::write(fd_, data + total, len - total);
    if (n < 0) {
      if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
        continue;
      }
      const int e = errno;
      if (is_disconnect_errno(e)) {
        throw std::system_error(e, std::system_category(), "SerialPort::write_all: disconnect");
      }
      throw std::system_error(e, std::system_category(), "SerialPort::write_all: write");
    }
    total += static_cast<std::size_t>(n);
  }
}

std::size_t SerialPort::read_some(uint8_t * buf, std::size_t max_len)
{
  std::shared_lock<std::shared_mutex> lock(mtx_);
  if (fd_ < 0) {
    throw std::runtime_error("SerialPort::read_some: port not open");
  }
  struct pollfd pfd{};
  pfd.fd = fd_;
  pfd.events = POLLIN;
  const int pr = ::poll(&pfd, 1, READ_TIMEOUT_MS);
  if (pr < 0) {
    if (errno == EINTR) {
      return 0;  // signal interrupted; caller will loop
    }
    throw std::system_error(errno, std::system_category(), "SerialPort::read_some: poll");
  }
  if (pr == 0) {
    return 0;  // timeout, no data
  }
  if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL)) {
    throw std::system_error(
            EIO, std::system_category(),
            "SerialPort::read_some: poll reported POLLERR/HUP/NVAL (disconnect)");
  }
  const ssize_t n = ::read(fd_, buf, max_len);
  if (n < 0) {
    if (errno == EAGAIN || errno == EWOULDBLOCK) {
      return 0;
    }
    const int e = errno;
    if (is_disconnect_errno(e)) {
      throw std::system_error(e, std::system_category(), "SerialPort::read_some: disconnect");
    }
    throw std::system_error(e, std::system_category(), "SerialPort::read_some: read");
  }
  return static_cast<std::size_t>(n);
}

std::unique_lock<std::shared_mutex> SerialPort::exclusive_lock()
{
  return std::unique_lock<std::shared_mutex>(mtx_);
}

}  // namespace hexapod_hardware
