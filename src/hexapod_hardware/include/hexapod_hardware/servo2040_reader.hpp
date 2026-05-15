// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
#ifndef HEXAPOD_HARDWARE__SERVO2040_READER_HPP_
#define HEXAPOD_HARDWARE__SERVO2040_READER_HPP_

#include <atomic>
#include <cstdint>
#include <mutex>
#include <optional>
#include <thread>
#include <vector>

#include "hexapod_hardware/servo2040_protocol.hpp"

namespace hexapod_hardware
{

// Forward decl to avoid the include cycle: serial_port.hpp doesn't need
// to know about the reader, only the .cpp does.
class SerialPort;

// Background thread that consumes the byte stream from a SerialPort, splits
// it on 0x00 delimiters, decodes frames, and routes them by opcode:
//   - STATE_RESPONSE → latest_state_ (overwrite, "peek-not-consume" semantics)
//   - ERROR_REPORT   → error_queue_  (drained by Plugin per read() tick)
//   - ACK / NACK     → debug log (kept observable for future use)
//   - bad / unknown  → warn log
//
// Concurrency model (see docs_raspi/phase_9_stage_d_plan.md §D.2):
//   - exactly one reader thread, started in start(), joined in stop()
//   - state_mtx_  protects latest_state_
//   - error_mtx_  protects error_queue_
//   - lifecycle_mtx_ serialises start()/stop() against each other and
//     against the destructor (the user-side guarantee is that ros2_control
//     calls these sequentially, but we don't want a future caller to
//     learn about the race the hard way)
//   - stop_requested_ and died_ are atomic flags
//   - the SerialPort itself has its own shared_mutex (D.1) — we hold a
//     shared_lock via SerialPort::read_some()
//
// Lifetime contract: the SerialPort reference passed to start() MUST
// outlive the reader thread. The intended pattern is the plugin owning
// both: the destructor of Servo2040Reader stops + joins; only THEN may
// the SerialPort be destroyed. Calling code that destroys the port first
// is undefined behaviour.
//
// Exception safety (Review Punkt 4): the whole reader loop is wrapped in
// try/catch. If anything escapes, died_ is set and the next read() tick
// in the plugin will surface the failure via return_type::ERROR.
class Servo2040Reader
{
public:
  Servo2040Reader() = default;
  ~Servo2040Reader();

  // Non-copyable, non-movable: owns a thread and mutexes.
  Servo2040Reader(const Servo2040Reader &) = delete;
  Servo2040Reader & operator=(const Servo2040Reader &) = delete;
  Servo2040Reader(Servo2040Reader &&) = delete;
  Servo2040Reader & operator=(Servo2040Reader &&) = delete;

  // Fork the reader thread. The port reference must outlive stop().
  // Calling start() twice without an intervening stop() throws.
  void start(SerialPort & port);

  // Signal the reader to exit and join. Idempotent, never throws.
  // Latency: up to ~1 s (the SerialPort read timeout) before the thread
  // notices the stop flag and exits.
  void stop() noexcept;

  // True if the reader is alive and processing. False after stop() or
  // after an unrecoverable error in the loop (see died()).
  bool is_running() const noexcept;

  // True if the reader thread caught an exception and exited
  // prematurely. The plugin's read() inspects this and surfaces it to
  // ros2_control as return_type::ERROR.
  bool died() const noexcept;

  // Peek at the latest STATE-RESPONSE frame, if any has arrived since
  // start(). Returns nullopt until the firmware first responds to a
  // GET_STATE — in Phase 9 we don't poll, so this stays empty most of
  // the time (kept for Phase 10's monitoring needs).
  std::optional<StatePayload> latest_state() const;

  // Drain all queued ERROR_REPORTs. Each call returns everything that
  // arrived since the previous call. Called once per read() tick by
  // the plugin to log them.
  std::vector<ErrorReport> drain_error_queue();

private:
  void loop(SerialPort & port);
  void dispatch(const DecodedFrame & frame);

  std::atomic<bool> stop_requested_{false};
  std::atomic<bool> died_{false};
  std::thread thread_;

  // Serialises start()/stop()/destructor against each other so concurrent
  // lifecycle calls can't race on thread_.joinable() / thread_.join().
  // Never held by the reader thread itself.
  mutable std::mutex lifecycle_mtx_;

  mutable std::mutex state_mtx_;
  std::optional<StatePayload> latest_state_;

  std::mutex error_mtx_;
  std::vector<ErrorReport> error_queue_;
};

}  // namespace hexapod_hardware

#endif  // HEXAPOD_HARDWARE__SERVO2040_READER_HPP_
