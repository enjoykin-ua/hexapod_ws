// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/servo2040_reader.hpp"

#include <array>
#include <chrono>
#include <exception>
#include <stdexcept>
#include <string>
#include <system_error>
#include <thread>
#include <utility>

#include <rclcpp/rclcpp.hpp>

#include "hexapod_hardware/serial_port.hpp"

namespace hexapod_hardware
{

namespace
{
// Single named logger so RCLCPP_DEBUG / WARN attribute consistently.
rclcpp::Logger reader_logger()
{
  return rclcpp::get_logger("hexapod_hardware.reader");
}
}  // namespace

Servo2040Reader::~Servo2040Reader()
{
  stop();
}

void Servo2040Reader::start(SerialPort & port)
{
  std::lock_guard<std::mutex> lk(lifecycle_mtx_);
  if (thread_.joinable()) {
    throw std::runtime_error("Servo2040Reader::start: thread already running");
  }
  stop_requested_ = false;
  died_ = false;
  // The thread captures `&port` — caller must guarantee that the port
  // outlives the reader (i.e. call stop() before destroying the port).
  thread_ = std::thread([this, &port]() {this->loop(port);});
}

void Servo2040Reader::stop() noexcept
{
  // Set the flag first, OUTSIDE the lifecycle mutex, so that if the
  // reader is currently inside a long read_some() it sees the request
  // and exits as soon as the next read returns (timeout or data).
  stop_requested_ = true;

  // Then serialise the actual join() against any concurrent start()/stop().
  std::lock_guard<std::mutex> lk(lifecycle_mtx_);
  if (thread_.joinable()) {
    try {
      thread_.join();
    } catch (...) {
      // join() can only throw std::system_error on hard OS faults.
      // Nothing useful we can do here — destructor must not throw.
    }
  }
}

bool Servo2040Reader::is_running() const noexcept
{
  std::lock_guard<std::mutex> lk(lifecycle_mtx_);
  return thread_.joinable() && !died_;
}

bool Servo2040Reader::died() const noexcept
{
  return died_;
}

std::optional<StatePayload> Servo2040Reader::latest_state() const
{
  std::lock_guard<std::mutex> lk(state_mtx_);
  return latest_state_;
}

std::optional<InputsSnapshot> Servo2040Reader::latest_inputs() const
{
  std::lock_guard<std::mutex> lk(inputs_mtx_);
  return latest_inputs_;
}

std::vector<ErrorReport> Servo2040Reader::drain_error_queue()
{
  std::lock_guard<std::mutex> lk(error_mtx_);
  std::vector<ErrorReport> out;
  out.swap(error_queue_);
  return out;
}

void Servo2040Reader::loop(SerialPort & port)
{
  // The reader's job is dumb: bytes in, frames out, dispatch by opcode.
  // The entire body sits in a try/catch so that a bad_alloc, system_error
  // or anything else does not std::terminate the process. If we exit
  // abnormally we set died_, which read() in the plugin picks up.

  std::vector<uint8_t> assembly;   // current in-progress frame (pre-COBS-decode)
  assembly.reserve(64);
  std::array<uint8_t, 256> buf{};

  try {
    while (!stop_requested_) {
      std::size_t n = 0;
      try {
        n = port.read_some(buf.data(), buf.size());
      } catch (const std::system_error & e) {
        // Disconnect-class error (EIO/POLLHUP/ENXIO/ENODEV). Stage D.7:
        // hand off to reconnect_loop which closes + retries open() with
        // backoff. The reconnect-loop holds SerialPort's exclusive_lock
        // for the whole close+open window, so any parallel write_all()
        // call from the plugin tick blocks until we're done.
        RCLCPP_ERROR(
          reader_logger(),
          "Servo2040Reader: read failed (%s) — entering reconnect-loop",
          e.what());
        if (!reconnect_loop(port)) {
          // Either stop_requested_ tripped during backoff (clean exit)
          // or the port has no path to re-open against (adopt_fd case →
          // reconnect_loop already set died_=true). Either way, leave
          // the loop now.
          return;
        }
        // Reconnect succeeded. Mid-frame bytes in `assembly` belong to
        // the OLD stream — useless after re-open, would just produce
        // CRC mismatches. Drop them and resume the read loop fresh.
        if (!assembly.empty()) {
          RCLCPP_DEBUG(
            reader_logger(),
            "Servo2040Reader: discarding %zu mid-frame bytes after reconnect",
            assembly.size());
          assembly.clear();
        }
        continue;
      }

      for (std::size_t i = 0; i < n; ++i) {
        const uint8_t b = buf[i];
        if (b == 0x00) {
          if (!assembly.empty()) {
            auto frame = decode_frame(assembly);
            if (frame) {
              dispatch(*frame);
            } else {
              // No THROTTLE macro here — that requires an rclcpp::Clock,
              // and a Clock instance needs the rclcpp runtime initialised,
              // which is fine in production but breaks gtest fixtures
              // that don't call rclcpp::init(). Garbage frames should be
              // rare on USB-CDC anyway; if they spam, that's a real
              // problem the user wants to see.
              RCLCPP_WARN(
                reader_logger(),
                "Servo2040Reader: frame decode failed (CRC/COBS/length, %zu B)",
                assembly.size());
            }
            assembly.clear();
          }
          // Lone 0x00 between frames (e.g. resync byte) — skip silently.
        } else {
          assembly.push_back(b);
        }
      }
      // If read_some timed out (n == 0) we just loop and re-check
      // stop_requested_. No work to do.
    }
  } catch (const std::exception & e) {
    RCLCPP_FATAL(
      reader_logger(),
      "Servo2040Reader: thread died with exception: %s", e.what());
    died_ = true;
  } catch (...) {
    RCLCPP_FATAL(reader_logger(), "Servo2040Reader: thread died with unknown exception");
    died_ = true;
  }
}

bool Servo2040Reader::reconnect_loop(SerialPort & port)
{
  // The backoff sequence is empirical from Phase 7: typical USB-CDC
  // re-enumerate on Linux completes in ~200 ms, after that we widen
  // and cap at 5 s so an extended outage doesn't busy-poll the kernel.
  // Sleep is split into 50-ms chunks so a concurrent stop() request
  // lands within ~50 ms instead of blocking the whole stage (D.2's
  // StopJoinsCleanlyWithin1500ms test caps the latency at 1.5 s).
  constexpr std::array<int, 7> backoff_ms = {100, 200, 500, 1000, 2000, 5000, 5000};

  // Lock-Strategie: WIR halten KEINEN externen exclusive_lock im
  // reconnect_loop. Begründung:
  //   - SerialPort::close() und SerialPort::open() nehmen jeweils intern
  //     einen unique_lock<shared_mutex>. std::shared_mutex ist NICHT
  //     rekursiv — wenn wir AUSSEN einen exclusive_lock halten und dann
  //     close()/open() rufen würden, gibt's einen Self-Deadlock auf dem
  //     selben Mutex (glibc erkennt das und wirft EDEADLK).
  //   - Gleiches gilt für port.path() (nimmt shared_lock).
  // Der mutex serialisiert die einzelnen Calls schon korrekt:
  //   1. close() → unique_lock kurz, fd_=-1
  //   2. (Sleep, kein Lock gehalten)
  //   3. open() → unique_lock kurz, fd_=new
  // Parallele write_all() im controller_manager-Tick:
  //   - Während Sleep (kein Lock): write_all kriegt shared_lock, sieht
  //     fd_<0, wirft sofort "port not open" → write() returnt ERROR.
  //     Kein Tick-Freeze.
  //   - Während close()/open() (unique_lock): write_all blockt für die
  //     paar µs — vernachlässigbar.
  // Race-Schutz bleibt erhalten, weil der mutex jeden einzelnen Call
  // serialisiert; wir brauchen den exclusive_lock vom SerialPort
  // (Public-API von D.1) hier gar nicht.

  // Phase 1: Pfad merken (eigener shared_lock im path() intern).
  const std::string path = port.path();
  if (path.empty()) {
    // Port wurde via adopt_fd() angenommen (kein Pfad zum Re-Open).
    // Hauptsächlich Test-Pfad; in Produktion nimmt on_configure
    // immer open(). Recovery unmöglich → died_ und exit.
    RCLCPP_FATAL(
      reader_logger(),
      "Servo2040Reader: cannot reconnect, SerialPort has no path "
      "(adopted FD?). Reader thread will exit.");
    died_ = true;
    return false;
  }

  // Phase 2: close() — eigener unique_lock intern, dann released.
  port.close();   // fd_ → -1, path_ → "", parallele write_all wirft jetzt

  // Phase 3: Backoff-Schleife. Sleep OHNE Lock, open() macht sein eigenes.
  std::size_t attempt = 0;
  while (!stop_requested_) {
    const int wait_ms = backoff_ms[
      std::min<std::size_t>(attempt, backoff_ms.size() - 1)];
    RCLCPP_WARN(
      reader_logger(),
      "Servo2040Reader: reconnect attempt %zu — waiting %d ms before "
      "trying to re-open '%s'",
      attempt + 1, wait_ms, path.c_str());

    // Chunked sleep: max stop-Latenz ist ein Chunk (50 ms), auch
    // wenn das Steady-State-Backoff 5 s ist.
    for (int slept = 0; slept < wait_ms && !stop_requested_; slept += 50) {
      std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    if (stop_requested_) {return false;}

    try {
      port.open(path);   // eigener unique_lock intern
      RCLCPP_INFO(
        reader_logger(),
        "Servo2040Reader: reconnect SUCCESS after %zu attempts. "
        "Plugin stays in INACTIVE state — to bring controllers back, "
        "run: ros2 control switch_controllers --activate "
        "<your_controller_names>",
        attempt + 1);
      return true;
    } catch (const std::exception & e) {
      // open() failt weiter → nächste Backoff-Stufe.
      RCLCPP_DEBUG(
        reader_logger(),
        "Servo2040Reader: reconnect attempt %zu failed: %s",
        attempt + 1, e.what());
    }
    ++attempt;
  }
  // stop_requested_ tripped between attempts — clean exit.
  return false;
}

void Servo2040Reader::dispatch(const DecodedFrame & frame)
{
  switch (frame.cmd) {
    case opcode::STATE_RESPONSE: {
        auto parsed = decode_state(frame.payload);
        if (!parsed) {
          RCLCPP_WARN(
            reader_logger(),
            "Servo2040Reader: STATE_RESPONSE payload malformed (got %zu B, expected 75)",
            frame.payload.size());
          return;
        }
        std::lock_guard<std::mutex> lk(state_mtx_);
        latest_state_ = std::move(*parsed);
        break;
      }

    case opcode::INPUTS_RESPONSE: {
        auto parsed = decode_inputs(frame.payload);
        if (!parsed) {
          RCLCPP_WARN(
            reader_logger(),
            "Servo2040Reader: INPUTS_RESPONSE payload malformed (got %zu B, expected 1)",
            frame.payload.size());
          return;
        }
        std::lock_guard<std::mutex> lk(inputs_mtx_);
        latest_inputs_ = InputsSnapshot{*parsed, std::chrono::steady_clock::now()};
        break;
      }

    case opcode::ERROR_REPORT: {
        auto parsed = decode_error_report(frame.payload);
        if (!parsed) {
          RCLCPP_WARN(
            reader_logger(),
            "Servo2040Reader: ERROR_REPORT payload malformed (got %zu B, expected 4)",
            frame.payload.size());
          return;
        }
        std::lock_guard<std::mutex> lk(error_mtx_);
        error_queue_.push_back(*parsed);
        break;
      }

    case opcode::ACK:
      RCLCPP_DEBUG(reader_logger(), "ACK seq=%u", frame.seq);
      break;

    case opcode::NACK:
      // PROTOCOL.md §3 NACK = original_cmd + reason. Keep the bytes
      // observable; semantic interpretation comes in D.8.
      RCLCPP_DEBUG(
        reader_logger(),
        "NACK seq=%u (payload %zu B)", frame.seq, frame.payload.size());
      break;

    default:
      RCLCPP_WARN(
        reader_logger(),
        "Servo2040Reader: unknown opcode 0x%02X (seq=%u, %zu B payload)",
        frame.cmd, frame.seq, frame.payload.size());
      break;
  }
}

}  // namespace hexapod_hardware
