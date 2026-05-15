// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__SERIAL_PORT_HPP_
#define HEXAPOD_HARDWARE__SERIAL_PORT_HPP_

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <shared_mutex>
#include <string>

namespace hexapod_hardware
{

// RAII wrapper around a POSIX serial-port FD.
//
// Configures the FD for binary, byte-stream I/O:
//   - O_NONBLOCK on the FD itself; timing comes from poll(2) in read/write.
//   - cfmakeraw() termios — no canonical mode, no echo, no NL/CR mapping.
//     This is CRITICAL for the binary COBS+CRC protocol: without it the
//     Linux TTY layer would translate 0x0D <-> 0x0A and silently mangle
//     any frame whose CRC happens to contain those bytes (Phase-7 C.4 bug).
//
// Concurrency: a std::shared_mutex protects against the
// "Reader-Thread reconnects while controller_manager-Thread is writing"
// race documented in phase_9_stage_d_plan.md §D.7.
//   - write_all() / read_some() take a shared lock.
//   - The reconnect path takes the exclusive lock via exclusive_lock().
//
class SerialPort
{
public:
  SerialPort() = default;
  ~SerialPort();

  // Non-copyable, non-movable: owns an OS resource (the FD) and a mutex.
  SerialPort(const SerialPort &) = delete;
  SerialPort & operator=(const SerialPort &) = delete;
  SerialPort(SerialPort &&) = delete;
  SerialPort & operator=(SerialPort &&) = delete;

  // Open the given device path (e.g. "/dev/ttyACM0"). Throws std::system_error
  // on failure with a message that names the path and the underlying errno
  // (typical hits: ENOENT, EACCES, EBUSY).
  void open(const std::string & path);

  // Adopt ownership of an already-open FD and apply the termios setup.
  // Used by tests with openpty(3); also handy for future ROS-param-based
  // FD passing. Takes ownership; closes the FD on close()/destructor.
  // Throws on termios setup failure.
  void adopt_fd(int fd);

  // Close the FD if open. Idempotent, never throws.
  void close() noexcept;

  bool is_open() const noexcept;

  // Write the entire buffer or throw. Uses poll(POLLOUT) with a 50 ms
  // timeout per chunk to avoid blocking the controller_manager tick
  // indefinitely when the USB-CDC FIFO is full (e.g. firmware hang).
  // Throws std::system_error on disconnect (EIO/ENXIO/ENODEV) or timeout.
  void write_all(const uint8_t * data, std::size_t len);

  // Read up to max_len bytes. Returns 0 if nothing was available within
  // the read timeout (1 s) — the caller can then check a stop flag and
  // loop. Throws std::system_error only on hard disconnect errors;
  // EAGAIN/EWOULDBLOCK is converted to a 0 return.
  std::size_t read_some(uint8_t * buf, std::size_t max_len);

  // Acquire the exclusive lock for the reconnect path. While this lock
  // is held, all calls to write_all() / read_some() block until it is
  // released — used by the Reader-Thread when it closes and re-opens the
  // FD after a USB disconnect.
  std::unique_lock<std::shared_mutex> exclusive_lock();

  // The path most recently passed to open(), or empty if the port was
  // adopted via adopt_fd() (no path available) or is currently closed.
  // The Reader-Thread's reconnect-loop (stage D.7) uses this to know
  // which device to re-open after a disconnect. Returned by value to
  // avoid lifetime issues if the caller closes the port concurrently.
  std::string path() const;

private:
  void configure_termios();  // helper used by both open() and adopt_fd()

  int fd_{-1};
  // Set in open(path), cleared in close()/adopt_fd. Guarded by mtx_ for
  // the same reason fd_ is — the reconnect-loop reads path_ under the
  // exclusive lock, callers of path() take the shared lock.
  std::string path_{};
  mutable std::shared_mutex mtx_;
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__SERIAL_PORT_HPP_
