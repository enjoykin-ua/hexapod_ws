// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0

#include "hexapod_hardware/servo2040_reader.hpp"

#include <array>
#include <exception>
#include <stdexcept>
#include <system_error>
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
        // Disconnect-class errors land here. In D.2 we just log and
        // exit the loop — the proper reconnect logic comes in D.7.
        RCLCPP_ERROR(
          reader_logger(),
          "Servo2040Reader: serial read failed (will exit thread until D.7 is in): %s",
          e.what());
        died_ = true;
        return;
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
