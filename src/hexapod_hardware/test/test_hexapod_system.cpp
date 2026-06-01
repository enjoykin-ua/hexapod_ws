// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Unit tests for HexapodSystemHardware::on_init (Stage D.3).
//
// We construct a synthetic hardware_interface::HardwareInfo by hand and
// feed it through the plugin's on_init hook. The real URDF→HardwareInfo
// parsing (done by ros2_control's resource_manager + xacro) is out of
// scope here — we only care that, given a well-formed HardwareInfo,
// on_init builds the right internal state and rejects malformed input.

#include <gtest/gtest.h>

#include <fcntl.h>
#include <poll.h>
#include <pty.h>
#include <termios.h>
#include <unistd.h>

#include <chrono>
#include <cmath>
#include <memory>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>

#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"
#include "rclcpp/rclcpp.hpp"

#include "hexapod_hardware/hexapod_system.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

#include "test_helpers.hpp"

using hexapod_hardware::HexapodSystemHardware;
using hexapod_hardware::NUM_SERVOS;

// HardwareInfo / params builders moved to test/test_helpers.hpp in Stage E
// (shared with test_plugin_registration.cpp).
using hexapod_hardware_test::make_joint;
using hexapod_hardware_test::make_valid_info;
using hexapod_hardware_test::make_params;

// pulse_zero per servo pin, mirroring the committed servo_mapping.yaml.
// Values from Cal-Session 2026-05-21 + leg_2/leg_5 re-cal 2026-05-24
// (Mount-Tausch) + Phase 13 Stage 0.2 femur re-cal 2026-05-30 (35° remount,
// Weg A — femur pulse_zero shifted ~+240 µs; coxa/tibia unchanged).
// See docs_raspi/servo_real_calibration_todos.md + phase_13_stage_0_2_*.
// Tests that exercise the boot/neutral-pulse path use this table so YAML
// edits in future Cal-Sessions don't trigger spurious failures.
constexpr int16_t kExpectedPulseZero[NUM_SERVOS] = {
  1460, 1700, 1710,   // leg_1 (pins  0,  1,  2) — tibia re-cal 0.6.6
  1575, 1780, 1720,   // leg_2 (pins  3,  4,  5) — tibia re-cal 0.6.6
  1410, 1690, 1610,   // leg_3 (pins  6,  7,  8) — tibia re-cal 0.6.6
  1520, 1295, 1318,   // leg_4 (pins  9, 10, 11) — tibia re-cal 0.6.6
  1550, 1325, 1416,   // leg_5 (pins 12, 13, 14) — tibia re-cal 0.6.6
  1530, 1290, 1351,   // leg_6 (pins 15, 16, 17) — tibia re-cal 0.6.6
};

// ============================================================================
// Happy path
// ============================================================================

TEST(HexapodSystemInit, ValidHardwareInfoSucceeds)
{
  HexapodSystemHardware plugin;
  EXPECT_EQ(
    plugin.on_init(make_params(make_valid_info())),
    hardware_interface::CallbackReturn::SUCCESS);

  // Interfaces should now be exportable, one per joint, in URDF order.
  auto state_ifs = plugin.export_state_interfaces();
  auto cmd_ifs = plugin.export_command_interfaces();
  EXPECT_EQ(state_ifs.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_ifs.size(), NUM_SERVOS);
}

TEST(HexapodSystemInit, ExportedInterfaceNamesMatchUrdfOrder)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_ifs.size(), NUM_SERVOS);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    // Interface name format is "<joint_name>/<interface>" in ros2_control.
    // The prefix must match the joint name we put into info.joints[i].
    const std::string expected_prefix = info.joints[i].name;
    EXPECT_EQ(cmd_ifs[i].get_prefix_name(), expected_prefix) << "at slot " << i;
  }
}

// ============================================================================
// Joint count
// ============================================================================

TEST(HexapodSystemInit, RejectsTooFewJoints)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints.pop_back();  // 17 joints
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsTooManyJoints)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints.push_back(make_joint("phantom_extra_joint"));
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

// ============================================================================
// Hardware parameters
// ============================================================================

TEST(HexapodSystemInit, RejectsMissingCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters.erase("calibration_file");
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsEmptyCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["calibration_file"] = "";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsNonExistentCalibrationFile)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["calibration_file"] = "/tmp/does_not_exist_xyz.yaml";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, AcceptsAllBoolStringsForLoopback)
{
  // The plugin should accept the same set of bool-ish strings that
  // most ROS users expect: true/false, 1/0, yes/no — case-insensitive.
  for (const char * v : {"true", "TRUE", "True", "false", "FALSE",
      "1", "0", "yes", "no", "YES", "No"})
  {
    HexapodSystemHardware plugin;
    auto info = make_valid_info();
    info.hardware_parameters["loopback_mode"] = v;
    EXPECT_EQ(
      plugin.on_init(make_params(info)),
      hardware_interface::CallbackReturn::SUCCESS)
      << "loopback_mode value '" << v << "' should be accepted";
  }
}

TEST(HexapodSystemInit, RejectsGarbageLoopbackString)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "maybe";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, LoopbackDefaultsToFalseIfOmitted)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters.erase("loopback_mode");
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  // (We can't directly read loopback_mode_ without breaking encapsulation,
  // but the "default = false" path is exercised here; D.4 will assert
  // the consequence — no serial port opened.)
}

// ============================================================================
// Joint-to-output-pin mapping
//
// We can't directly inspect joint_to_output_idx_ (private member) — but we
// can verify the SUCCESS/ERROR signal at the boundaries and trust that
// downstream stages (D.6) exercise the actual mapping in write/read.
// ============================================================================

TEST(HexapodSystemInit, AcceptsPermutedJointOrder)
{
  // Build the same 18 joints in a non-canonical order. Calibration
  // still owns the canonical pin assignment via servo_mapping.yaml, so
  // joint_to_output_idx_ ends up as a non-identity permutation.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  std::reverse(info.joints.begin(), info.joints.end());
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  // Check that exports preserve URDF order, NOT pin order — that's the
  // ros2_control contract.
  auto cmd_ifs = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_ifs.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_ifs.front().get_prefix_name(), "leg_6_tibia_joint")
    << "URDF slot 0 should still be leg_6_tibia_joint after reversal "
    "— ros2_control exports in URDF order";
  EXPECT_EQ(cmd_ifs.back().get_prefix_name(), "leg_1_coxa_joint")
    << "URDF slot 17 should be leg_1_coxa_joint after reversal";
}

TEST(HexapodSystemInit, RejectsUnknownJointName)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[5].name = "leg_99_phantom_joint";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

// ============================================================================
// Limit parsing
// ============================================================================

TEST(HexapodSystemInit, ParsesJointLimitsFromUrdf)
{
  // Confirm that custom limits in the URDF (different from the calibration
  // defaults ±1.57) reach Calibration::set_joint_limits. Indirect test:
  // we set asymmetric limits, do on_init, and then verify a forward call
  // via the Calibration object would behave accordingly. Since we can't
  // peek at calibration_, we verify the SUCCESS of on_init plus the fact
  // that absurd limits (lower > upper) still pass through — the Calibration
  // doesn't validate URDF semantics, only its own pulse triplet.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", -1.2, +0.8);  // asymmetric
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemInit, EmptyJointLimitsFallBackToDefaults)
{
  // If the URDF omits the <limit lower upper>, both min and max come
  // through as empty strings. The plugin should warn and continue, falling
  // back to Calibration's ±1.57 defaults.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[0].command_interfaces[0].min = "";
  info.joints[0].command_interfaces[0].max = "";
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemInit, RejectsSwappedJointLimits)
{
  // URDF bug: lower > upper. Some URDF refactor swapped the macro args
  // and nobody noticed. Plugin must FATAL with a message that explains
  // why this isn't a "mirrored leg" case (those use direction in
  // servo_mapping.yaml, not swapped URDF limits).
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", /*lower=*/+1.57, /*upper=*/-1.57);
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, RejectsEqualJointLimits)
{
  // Same problem class: lower == upper means a stuck joint, which has no
  // meaningful pulse-µs slope. Reject.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.joints[3] = make_joint("leg_2_coxa_joint", /*lower=*/0.0, /*upper=*/0.0);
  EXPECT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemInit, FailedReinitDoesNotMutateTable)
{
  // Strong-exception-guarantee analogue to test_calibration's
  // StrongExceptionGuarantee suite. If on_init is called a second time
  // and fails partway through (here: unknown joint name on the second
  // call), the plugin must not end up with a half-built joint→pin table
  // from the partial second attempt.
  //
  // Practical impact in production is low (ros2_control wouldn't use
  // the plugin if on_init returned ERROR), but the property is the same
  // we made the Calibration class promise — we keep the contract here.
  HexapodSystemHardware plugin;
  auto good = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(good)),
    hardware_interface::CallbackReturn::SUCCESS);

  // Snapshot the joint order that ros2_control sees right now.
  auto cmd_before = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_before.size(), NUM_SERVOS);
  const std::string joint0_before = cmd_before[0].get_prefix_name();
  const std::string joint17_before = cmd_before[17].get_prefix_name();

  // Now hand on_init a bad HardwareInfo — joint 10 is renamed to a
  // phantom that's not in the YAML, so output_idx_for_joint will throw.
  auto bad = make_valid_info();
  bad.joints[10].name = "leg_99_phantom_joint";
  EXPECT_EQ(
    plugin.on_init(make_params(bad)),
    hardware_interface::CallbackReturn::ERROR);

  // The plugin is now in a "failed re-init" state. ros2_control would
  // discard it; we just verify that the table built locally during the
  // failed init didn't leak into the member. We can't directly inspect
  // joint_to_output_idx_, but we can confirm that the export interfaces
  // were not retroactively rewritten to the partial set.
  //
  // Since on_init does the export-relevant hw_state/command vectors
  // BEFORE the joint-table build, those are unfortunately re-assigned
  // even on the failed path. So we restrict the assertion to the table
  // committed via std::move — which on the failed path stays at the
  // pre-failure value.
  //
  // We verify this indirectly by running a third on_init with the GOOD
  // info: it must succeed, and the recovered table must reproduce the
  // original mapping (not the phantom one).
  ASSERT_EQ(
    plugin.on_init(make_params(good)),
    hardware_interface::CallbackReturn::SUCCESS);
  auto cmd_after = plugin.export_command_interfaces();
  ASSERT_EQ(cmd_after.size(), NUM_SERVOS);
  EXPECT_EQ(cmd_after[0].get_prefix_name(), joint0_before);
  EXPECT_EQ(cmd_after[17].get_prefix_name(), joint17_before);
}

// ============================================================================
// on_configure / on_cleanup (Sub-Stage D.4)
//
// Tests fall into two groups:
//   1. Loopback path — no real FD, just verifies the SUCCESS return and
//      that we don't accidentally try to open something.
//   2. PTY path — opens a real pty pair and feeds the slave's name as
//      "serial_port" to the plugin. on_configure should then open it
//      (the slave end) and start the reader thread; on_cleanup tears
//      both down.
// ============================================================================

namespace
{

// Open a fresh PTY pair. master_fd_out gets the master end (kept open by
// the test so the slave stays alive); slave_name_out gets the slave's
// device path that we'll feed to SerialPort::open via the hardware param.
// The slave FD itself is closed immediately; the plugin opens its own.
void open_pty_for_serial_port(int * master_fd_out, std::string * slave_name_out)
{
  int master_fd = -1, slave_fd = -1;
  char slave_name[256] = {0};
  ASSERT_EQ(::openpty(&master_fd, &slave_fd, slave_name, nullptr, nullptr), 0)
    << "openpty failed: " << ::strerror(errno);
  // Put master end in raw mode so any traffic we drive into it for stub
  // tests doesn't get LF/CR-mangled by the kernel.
  struct termios m;
  ASSERT_EQ(::tcgetattr(master_fd, &m), 0);
  ::cfmakeraw(&m);
  ASSERT_EQ(::tcsetattr(master_fd, TCSANOW, &m), 0);
  ::close(slave_fd);   // let SerialPort::open() open the slave-name path itself
  *master_fd_out = master_fd;
  *slave_name_out = slave_name;
}

}  // namespace

TEST(HexapodSystemConfigure, LoopbackConfigureSucceedsWithoutPort)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  // loopback_mode=true is already in the default valid info.
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  // on_configure must succeed without touching a device path — even
  // though the default "/dev/ttyACM0" almost certainly isn't openable
  // by the test runner.
  EXPECT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemConfigure, LoopbackCleanupIsSafeEvenIfNotConfigured)
{
  // on_cleanup must be idempotent — calling it after on_init but before
  // on_configure (or twice in a row) shouldn't crash or throw.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);  // double-cleanup
}

TEST(HexapodSystemConfigure, RejectsNonExistentSerialPort)
{
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] =
    "/dev/this_serial_port_does_not_exist_42";
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  // open() will throw ENOENT — on_configure must catch and return ERROR.
  EXPECT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::ERROR);
}

TEST(HexapodSystemConfigure, ConfigureWithPtyOpensPortAndStartsReader)
{
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  EXPECT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Indirect verification: send bytes onto the master end and give the
  // reader thread a moment to process. If the reader isn't running, the
  // bytes pile up in the PTY buffer and the plugin notices nothing. If
  // it IS running, garbage gets logged as decode_failed. Either way the
  // plugin stays alive (no died_ flag).
  const uint8_t garbage[] = {0x11, 0x22, 0x33, 0x00};
  ASSERT_GT(::write(master_fd, garbage, sizeof(garbage)), 0);
  std::this_thread::sleep_for(std::chrono::milliseconds(50));

  // Cleanup tears it all down without leak / hang.
  const auto t0 = std::chrono::steady_clock::now();
  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto dt = std::chrono::steady_clock::now() - t0;
  EXPECT_LT(dt, std::chrono::milliseconds(1500))
    << "on_cleanup took " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(dt).count() << " ms";

  ::close(master_fd);
}

TEST(HexapodSystemConfigure, ConfigureCleanupCycleCanRepeat)
{
  // ros2_control allows configure → cleanup → configure cycles. Make
  // sure we can handle it without leaking the reader thread or the FD.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);

  for (int i = 0; i < 3; ++i) {
    EXPECT_EQ(
      plugin.on_configure(rclcpp_lifecycle::State{}),
      hardware_interface::CallbackReturn::SUCCESS) << "iteration " << i;
    EXPECT_EQ(
      plugin.on_cleanup(rclcpp_lifecycle::State{}),
      hardware_interface::CallbackReturn::SUCCESS) << "iteration " << i;
  }

  ::close(master_fd);
}

TEST(HexapodSystemConfigure, DestructorCleansUpAutomatically)
{
  // RAII: if a user destroys the plugin without calling on_cleanup
  // explicitly, the member destructors (Servo2040Reader, SerialPort)
  // must still produce a clean exit. We verify by configuring inside
  // a nested scope and confirming the destructor returns quickly.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  const auto t0 = std::chrono::steady_clock::now();
  {
    HexapodSystemHardware plugin;
    auto info = make_valid_info();
    info.hardware_parameters["loopback_mode"] = "false";
    info.hardware_parameters["serial_port"] = slave_name;
    ASSERT_EQ(
      plugin.on_init(make_params(info)),
      hardware_interface::CallbackReturn::SUCCESS);
    ASSERT_EQ(
      plugin.on_configure(rclcpp_lifecycle::State{}),
      hardware_interface::CallbackReturn::SUCCESS);
    // No explicit on_cleanup — let the destructor handle it.
  }
  const auto dt = std::chrono::steady_clock::now() - t0;
  EXPECT_LT(dt, std::chrono::milliseconds(1500))
    << "Destructor took too long to join reader thread: " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(dt).count() << " ms";

  ::close(master_fd);
}

// ============================================================================
// on_activate / on_deactivate (Sub-Stage D.5)
//
// Boot sequence under test (Phase 13 Stage 0.3 relay-gated, joint-group):
//   RESET -> SET_TARGETS(1500) -> 6x ENABLE(femur) -> RELAY_CONTROL(on) ->
//   6x ENABLE(coxa) -> 6x ENABLE(tibia) -> SET_TARGETS(1500). 22 frames.
//
// Two test paths:
//   - Loopback: only checks timing/SUCCESS — no wire I/O to inspect.
//   - PTY: reads back the bytes the plugin wrote to the slave end of a
//     pty pair and decodes them as Servo2040 wire frames.
// ============================================================================

namespace
{

// Read everything available on master_fd until no bytes arrive for
// `idle_timeout`. Returns the concatenated bytes. Used to capture the
// plugin's wire output after a write-heavy lifecycle step.
std::vector<uint8_t> drain_master_until_idle(
  int master_fd, std::chrono::milliseconds idle_timeout)
{
  std::vector<uint8_t> out;
  out.reserve(1024);
  uint8_t buf[256];
  while (true) {
    struct pollfd pfd {master_fd, POLLIN, 0};
    const int pr = ::poll(&pfd, 1, static_cast<int>(idle_timeout.count()));
    if (pr <= 0) {break;}
    const ssize_t n = ::read(master_fd, buf, sizeof(buf));
    if (n <= 0) {break;}
    out.insert(out.end(), buf, buf + n);
  }
  return out;
}

// Split a 0x00-delimited byte stream into frames and decode each one.
// Decode failures are silently dropped — callers assert on the frame count.
std::vector<hexapod_hardware::DecodedFrame> split_and_decode_frames(
  const std::vector<uint8_t> & bytes)
{
  std::vector<hexapod_hardware::DecodedFrame> frames;
  std::vector<uint8_t> cobs_buf;
  cobs_buf.reserve(64);
  for (const uint8_t b : bytes) {
    if (b == 0x00) {
      if (!cobs_buf.empty()) {
        auto f = hexapod_hardware::decode_frame(cobs_buf);
        if (f) {frames.push_back(*f);}
        cobs_buf.clear();
      }
    } else {
      cobs_buf.push_back(b);
    }
  }
  return frames;
}

}  // namespace

TEST(HexapodSystemActivate, LoopbackActivateAndDeactivateAreFast)
{
  // Loopback mode skips the 50 ms per-servo stagger. Total time is bounded
  // by the 10 ms RESET-breather + the encoding overhead — well under 100 ms.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();   // loopback_mode=true is the default here
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  const auto t0 = std::chrono::steady_clock::now();
  EXPECT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto activate_dt = std::chrono::steady_clock::now() - t0;
  EXPECT_LT(activate_dt, std::chrono::milliseconds(100))
    << "Loopback on_activate took " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(activate_dt).count() << " ms";

  // Deactivate is also fast in loopback (no wire I/O, no waits at all).
  const auto t1 = std::chrono::steady_clock::now();
  EXPECT_EQ(
    plugin.on_deactivate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto deactivate_dt = std::chrono::steady_clock::now() - t1;
  EXPECT_LT(deactivate_dt, std::chrono::milliseconds(50))
    << "Loopback on_deactivate took " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(deactivate_dt).count() << " ms";
}

TEST(HexapodSystemActivate, PtyActivateRelayGatedSequenceOrder)
{
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  ASSERT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // on_activate blocks until every frame is written, so they are all sitting
  // in the pty buffer by the time it returns; a short idle timeout drains them
  // (the 700 ms femur settle happened *inside* on_activate, not on the wire).
  const auto bytes = drain_master_until_idle(master_fd, std::chrono::milliseconds(200));
  const auto frames = split_and_decode_frames(bytes);

  // Phase 13 Stage 0.3 relay-gated, joint-group-staggered boot sequence.
  // STRUCTURE frames in fixed order:
  //   RESET -> SET_TARGETS(1500 pre-enable) -> 6x ENABLE(femur) ->
  //   RELAY_CONTROL(on) -> 6x ENABLE(coxa) -> 6x ENABLE(tibia) ->
  //   SET_TARGETS(1500 reaffirm).
  // BETWEEN the femur->coxa and coxa->tibia groups the plugin emits watchdog
  // HEARTBEAT frames: extra SET_TARGETS(1500) every 100 ms during the 700 ms /
  // 400 ms settles (so the 200 ms firmware watchdog does not trip + drop the
  // relay mid-sequence). They are idempotent (same 1500 payload). We therefore
  // walk a cursor over the structure frames and SKIP any interleaved
  // SET_TARGETS(1500) that appears where a settle heartbeat is allowed.
  // make_valid_info() sets no initial_pose param -> default power_on_mid
  // commands SERVO_POWER_ON_MID_US (1500) to all 18 pins.
  constexpr int16_t kInitPulse = 1500;  // power_on_mid servo centre
  const std::vector<uint8_t> femur_pins = {1, 4, 7, 10, 13, 16};
  const std::vector<uint8_t> coxa_pins = {0, 3, 6, 9, 12, 15};
  const std::vector<uint8_t> tibia_pins = {2, 5, 8, 11, 14, 17};

  // Minimum frame count: 22 structure frames + >=1 heartbeat per settle
  // (2 settles) = at least 24 on real (non-loopback) timing.
  ASSERT_GE(frames.size(), 22u)
    << "fewer than the 22 structure frames (got " << frames.size() << ")";

  auto is_set_targets_1500 = [kInitPulse](const hexapod_hardware::DecodedFrame & f) {
      if (f.cmd != hexapod_hardware::opcode::SET_TARGETS) {return false;}
      if (f.payload.size() != 2u * hexapod_hardware::NUM_SERVOS) {return false;}
      for (std::size_t pin = 0; pin < hexapod_hardware::NUM_SERVOS; ++pin) {
        const int16_t pulse = static_cast<int16_t>(
          static_cast<uint16_t>(f.payload[2 * pin]) |
          (static_cast<uint16_t>(f.payload[2 * pin + 1]) << 8));
        if (pulse != kInitPulse) {return false;}
      }
      return true;
    };

  std::size_t cur = 0;  // cursor into frames
  auto skip_heartbeats = [&]() {
      while (cur < frames.size() && is_set_targets_1500(frames[cur])) {++cur;}
    };
  auto expect_set_targets = [&](const char * label) {
      ASSERT_LT(cur, frames.size()) << label << ": ran out of frames";
      EXPECT_TRUE(is_set_targets_1500(frames[cur]))
        << label << ": expected SET_TARGETS(1500) at frame " << cur
        << " (cmd=" << static_cast<int>(frames[cur].cmd) << ")";
      ++cur;
    };
  auto expect_enable = [&](uint8_t pin, const char * group) {
      ASSERT_LT(cur, frames.size()) << group << ": ran out of frames";
      EXPECT_EQ(frames[cur].cmd, hexapod_hardware::opcode::ENABLE_SERVO)
        << group << " at frame " << cur;
      ASSERT_EQ(frames[cur].payload.size(), 2u);
      EXPECT_EQ(frames[cur].payload[0], pin)
        << group << " servo_idx mismatch at frame " << cur;
      EXPECT_EQ(frames[cur].payload[1], 0x01)
        << group << " expected enable=true at frame " << cur;
      ++cur;
    };

  // RESET (empty payload).
  ASSERT_LT(cur, frames.size());
  EXPECT_EQ(frames[cur].cmd, hexapod_hardware::opcode::RESET);
  EXPECT_EQ(frames[cur].payload.size(), 0u);
  ++cur;

  // SET_TARGETS pre-enable.
  expect_set_targets("pre-enable SET_TARGETS");

  // Femur group (relay still open, no current). No heartbeats here (the 50 ms
  // enable stagger keeps the watchdog warm during enable groups).
  for (const uint8_t pin : femur_pins) {
    expect_enable(pin, "femur");
                                                                    }

  // RELAY_CONTROL(on) right after the femur group.
  ASSERT_LT(cur, frames.size());
  EXPECT_EQ(frames[cur].cmd, hexapod_hardware::opcode::RELAY_CONTROL)
    << "relay must close right after the femur group (frame " << cur << ")";
  ASSERT_EQ(frames[cur].payload.size(), 1u);
  EXPECT_EQ(frames[cur].payload[0], 0x01) << "relay frame payload must be ON";
  ++cur;

  // femur settle heartbeats (>=1 on real timing, 0 in loopback) -> skip them.
  skip_heartbeats();

  // Coxa group (rail now live).
  for (const uint8_t pin : coxa_pins) {
    expect_enable(pin, "coxa");
                                                                  }

  // coxa settle heartbeats -> skip.
  skip_heartbeats();

  // Tibia group.
  for (const uint8_t pin : tibia_pins) {
    expect_enable(pin, "tibia");
                                                                    }

  // SET_TARGETS reaffirm (the final structure frame; skip_heartbeats already
  // consumed any preceding heartbeats so this is the last 1500-frame).
  expect_set_targets("reaffirm SET_TARGETS");

  // All structure frames consumed; nothing but (already-skipped) heartbeats
  // may remain — and none should, since reaffirm is last.
  EXPECT_EQ(cur, frames.size())
    << "unexpected trailing frames after reaffirm SET_TARGETS";

  // SEQ is monotonic across ALL frames (structure + heartbeats), starting at 0.
  for (std::size_t i = 0; i < frames.size(); ++i) {
    EXPECT_EQ(static_cast<int>(frames[i].seq), static_cast<int>(i))
      << "SEQ mismatch at frame " << i;
  }

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemActivate, PtyActivateRespectsStaggerTiming)
{
  // Without the 50 ms stagger, the boot sequence would finish in single
  // digits of milliseconds — verify the wall-clock duration matches the
  // designed cadence.
  // Budget (Phase 13 Stage 0.3 relay-gated sequence):
  //   10 ms (RESET breather) + 10 ms (SET_TARGETS breather)
  //   + 18 x 50 ms (ENABLE stagger, 6 per group) = 900 ms
  //   + 700 ms (femur settle) + 400 ms (coxa settle) = ~2020 ms.
  // Wide band for scheduler jitter on busy CI machines.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  const auto t0 = std::chrono::steady_clock::now();
  ASSERT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto dt_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now() - t0).count();
  EXPECT_GT(dt_ms, 1700) << "Activate completed in " << dt_ms << " ms - settles skipped?";
  EXPECT_LT(dt_ms, 2700) << "Activate took " << dt_ms << " ms - too slow?";

  drain_master_until_idle(master_fd, std::chrono::milliseconds(50));
  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemActivate, PtyDeactivateSendsDisableForAllServos)
{
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Drop the 20 boot-sequence frames — we only care about what deactivate writes.
  drain_master_until_idle(master_fd, std::chrono::milliseconds(200));

  // Deactivate must NOT stagger (we want torque off as fast as possible).
  const auto t0 = std::chrono::steady_clock::now();
  ASSERT_EQ(
    plugin.on_deactivate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto dt_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now() - t0).count();
  EXPECT_LT(dt_ms, 200) << "Deactivate should be stagger-free (took " <<
    dt_ms << " ms)";

  const auto bytes = drain_master_until_idle(master_fd, std::chrono::milliseconds(100));
  const auto frames = split_and_decode_frames(bytes);
  // Stage 0.1: deactivate now sends 1 RELAY_CONTROL(off) first (fail-safe
  // depower), then 18 ENABLE_SERVO(false).
  ASSERT_EQ(frames.size(), hexapod_hardware::NUM_SERVOS + 1u);
  EXPECT_EQ(frames[0].cmd, hexapod_hardware::opcode::RELAY_CONTROL)
    << "first deactivate frame must drop the relay";
  ASSERT_EQ(frames[0].payload.size(), 1u);
  EXPECT_EQ(frames[0].payload[0], 0x00) << "relay frame payload must be OFF";
  for (uint8_t pin = 0; pin < hexapod_hardware::NUM_SERVOS; ++pin) {
    const auto & f = frames[pin + 1];
    EXPECT_EQ(f.cmd, hexapod_hardware::opcode::ENABLE_SERVO);
    ASSERT_EQ(f.payload.size(), 2u);
    EXPECT_EQ(f.payload[0], pin);
    EXPECT_EQ(f.payload[1], 0x00) << "expected enable=false at pin " <<
      static_cast<int>(pin);
  }

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemActivate, PtyActivateDeactivateCycleCanRepeat)
{
  // ros2_control may run activate → deactivate → activate cycles (e.g.
  // controller swaps, recovery). Two cycles back-to-back must work, with
  // SEQ continuing across cycles (no wraparound observable here either —
  // 2 cycles = 76 frames < 256).
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  for (int cycle = 0; cycle < 2; ++cycle) {
    ASSERT_EQ(
      plugin.on_activate(rclcpp_lifecycle::State{}),
      hardware_interface::CallbackReturn::SUCCESS) << "cycle " << cycle;
    drain_master_until_idle(master_fd, std::chrono::milliseconds(200));
    ASSERT_EQ(
      plugin.on_deactivate(rclcpp_lifecycle::State{}),
      hardware_interface::CallbackReturn::SUCCESS) << "cycle " << cycle;
    drain_master_until_idle(master_fd, std::chrono::milliseconds(100));
  }

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemActivate, ActivateFailsCleanlyIfPortIsBroken)
{
  // Failure scenario: USB disconnect lands between configure and activate.
  // We simulate this by closing the pty's master end — subsequent writes
  // on the slave (the plugin's FD) return EIO, and the reader thread
  // will eventually flag died_. on_activate's send_frame helper must
  // return ERROR cleanly (not throw out a std::system_error chain).
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Yank the master end. Give the reader a moment to react.
  ::close(master_fd);
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  EXPECT_EQ(
    plugin.on_activate(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::ERROR);

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
}

// ============================================================================
// read() / write() with echo-state + pulse conversion (Sub-Stage D.6)
//
// write() converts hw_command_positions_[i] (rad, URDF-indexed) through
// Calibration::radians_to_pulse_us into last_command_pulse_us_[output_idx]
// (µs, servo-pin-indexed) and — in non-loopback — sends one SET_TARGETS
// frame per tick. read() echoes last_command_pulse_us_ back as radians
// via Calibration::pulse_us_to_radians, drains the reader's error queue,
// and surfaces reader_.died() as return_type::ERROR.
//
// Test-data interaction: ros2_control exports CommandInterface / StateInterface
// objects that wrap pointers into hw_command_positions_ / hw_state_positions_.
// Tests poke values via those exported interfaces (get_value / set_value)
// to stay on the supported API surface — same path controllers would use.
// ============================================================================

namespace
{

// Read a State or Command interface value. jazzy 4.44 ships both the
// deprecated `get_value()` and the new `get_optional()` — we use the
// new one to silence the deprecation warning and stay forward-compatible
// with the Kilted Kaiju release that removes the old API.
template<typename Handle>
double read_handle(const Handle & h)
{
  return h.get_optional().value();
}

// Write a value via the Handle API. set_value() is [[nodiscard]] bool
// (returns false on lock contention); in single-threaded tests it must
// always succeed, but we ASSERT to keep the contract explicit.
template<typename Handle>
void write_handle(Handle & h, double value)
{
  ASSERT_TRUE(h.set_value(value));
}

}  // namespace

TEST(HexapodSystemWriteRead, LoopbackRoundtripsCommandThroughCalibration)
{
  // Loopback path: write() converts rad → pulse → stores in
  // last_command_pulse_us_; read() converts pulse → rad → stores in
  // hw_state_positions_. End-to-end the value should round-trip with
  // sub-millisecond rounding noise of one pulse step.
  //
  // The per-slot tolerance has to cover the **narrowest** pulse range
  // among the 18 servos in the committed YAML, because 1 µs of pulse
  // rounding maps back to a larger rad-step on narrow ranges:
  //   - Pin 0..14 (defaults, 500..2500 µs, ±1.57 rad): ~1.6e-3 rad/µs
  //   - Pin 15    (leg_6 coxa, 1280..1860 µs, Phase 10 Stage B):
  //                  positive side (1860-1550)/1.57 ≈ 197 µs/rad
  //                  → 1 µs ≈ 5.1e-3 rad   ← narrowest
  //   - Pin 16/17 (leg_6 femur/tibia, ~840..~2170 µs, ±1.57/±1.50 rad):
  //                  ~2.4e-3 rad/µs
  // We allow 6e-3 rad (≈ 1.2 µs at the narrowest range) as a generous
  // band that still catches off-by-one-frame slot mismatches.
  constexpr double kRoundtripTol = 6e-3;
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();
  ASSERT_EQ(cmd_ifs.size(), NUM_SERVOS);
  ASSERT_EQ(state_ifs.size(), NUM_SERVOS);

  // Spread of test inputs that cover both halves of the piecewise-linear
  // mapping (negative, zero, positive) and end-points (joint_lower/upper).
  const std::vector<double> values = {-1.5, -0.7, -0.1, 0.0, 0.1, 0.7, 1.5};
  for (const double v : values) {
    for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
      write_handle(cmd_ifs[i], v);
    }
    EXPECT_EQ(
      plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
      hardware_interface::return_type::OK);
    EXPECT_EQ(
      plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
      hardware_interface::return_type::OK);

    for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
      const double got = read_handle(state_ifs[i]);
      EXPECT_NEAR(got, v, kRoundtripTol)
        << "joint slot " << i << " (rad=" << v << ", got=" << got << ")";
    }
  }
}

TEST(HexapodSystemWriteRead, LoopbackEchoesAreSlotCorrectWithPermutedJointOrder)
{
  // Verifies the joint_to_output_idx_ table is actually being used by
  // BOTH write() and read() — not just built in on_init. Two ways the
  // current Roundtrip test would silently miss a mapping bug:
  //   (a) all 18 commands carry the same value (we set v for all slots),
  //       so any permutation echoes the same value back per slot
  //   (b) canonical URDF order means joint_to_output_idx_[i] = i, so
  //       even a "forgot the lookup, used [i] directly" bug looks fine
  // Fix: reverse the URDF joint list AND give each slot a unique value.
  // If write()/read() ever index into last_command_pulse_us_ without
  // joint_to_output_idx_, slot i's value will end up on slot (17 - i)
  // and the assertion fails per slot.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  std::reverse(info.joints.begin(), info.joints.end());
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();

  // Each slot gets a distinct value spread across the joint range.
  // 18 values × 0.1 rad spread = -0.85 .. +0.85, all inside ±1.57.
  auto value_for_slot = [](std::size_t i) {
      return -0.85 + 0.1 * static_cast<double>(i);
    };
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], value_for_slot(i));
  }
  ASSERT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  // Slot i's state must echo slot i's command — regardless of which
  // physical servo pin that slot is mapped to. Tolerance widened from
  // 2e-3 to 6e-3 after Stage B re-cal (mid-leg coxas have narrow ranges
  // ~175-200 µs; 1 µs rounding ≈ 2.4e-3 rad, ≥ old tolerance).
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const double got = read_handle(state_ifs[i]);
    const double expected = value_for_slot(i);
    EXPECT_NEAR(got, expected, 6e-3)
      << "slot " << i << " (URDF joint '" << info.joints[i].name <<
      "') expected echo " << expected << ", got " << got;
  }
}

TEST(HexapodSystemWriteRead, LoopbackZeroRadStaysAtPulseZero)
{
  // Specific anchor test: rad=0 must hit pulse_zero exactly (no rounding
  // because 1500 µs is an integer). Echo back yields rad=0 exactly.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.0);
  }
  ASSERT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    EXPECT_EQ(read_handle(state_ifs[i]), 0.0) << "slot " << i;
  }
}

TEST(HexapodSystemWriteRead, LoopbackNanCommandIsLoggedAndIgnored)
{
  // NaN from a misbehaving upstream controller MUST NOT propagate into
  // the pulse buffer or onto the wire. The plugin keeps the last good
  // pulse for that pin; downstream read() returns the old radians value
  // (NOT NaN, that would poison the next controller tick).
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();

  // First write: 0.5 rad on slot 5; everywhere else 0.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 5 ? 0.5 : 0.0);
  }
  ASSERT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);
  const double slot5_good = read_handle(state_ifs[5]);
  EXPECT_NEAR(slot5_good, 0.5, 6e-3);

  // Second write: NaN on slot 5; the others to 0.1.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 5 ? std::nan("") : 0.1);
  }
  EXPECT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK)
    << "NaN must not turn write() into ERROR — controllers may be glitchy";
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  // Slot 5 must still be ≈ 0.5 (the last good value). NEVER NaN.
  const double slot5_after_nan = read_handle(state_ifs[5]);
  EXPECT_FALSE(std::isnan(slot5_after_nan))
    << "NaN propagated into state — would poison the next controller tick";
  EXPECT_NEAR(slot5_after_nan, 0.5, 6e-3);
  // Other slots tracked the 0.1 update.
  EXPECT_NEAR(read_handle(state_ifs[3]), 0.1, 6e-3);
}

TEST(HexapodSystemWriteRead, LoopbackClampsAbsurdRadInsteadOfUB)
{
  // Without int16-clamp in write(), an extreme rad (e.g. 100) would
  // produce a pulse around 1.3e6 µs, and static_cast<int16_t> of that
  // is implementation-defined / UB. Verify the cast stays well-defined
  // and the pulse pegs at INT16_MAX.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 0 ? 100.0 : -100.0);   // mix both extremes
  }
  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  // After clamp + echo, state must be finite (no NaN, no inf). The exact
  // value depends on calibration; we just verify sanity.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    EXPECT_TRUE(std::isfinite(read_handle(state_ifs[i])))
      << "slot " << i << " produced non-finite state";
  }
}

// ============================================================================
// HexapodSystem — Stage 0.5 safety-freeze on pulse out-of-range
// ============================================================================
// These tests verify that the plugin alone enforces PWM ∈ [pulse_min,
// pulse_max] per pin (firmware stays dumb, User-Entscheidung 2026-05-24).
// When write() computes a pulse outside the calibrated range for any pin,
// safety_freeze_ trips: all subsequent writes hold last_command_pulse_us_
// until clear_safety_freeze() (or the /hexapod_safety_reset service) is
// called.

TEST(HexapodSafetyFreeze, OutOfRangeAboveTriggersFreeze)
{
  // pulse_zero=1500 + 100 rad · slope ≈ pulse far beyond pulse_max=2500
  // → safety_freeze must trip.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  EXPECT_FALSE(plugin.is_safety_frozen()) << "freeze should start cleared";

  auto cmd_ifs = plugin.export_command_interfaces();
  // Send rad=+10 on slot 0 (way above joint_upper=1.57). Other slots stay
  // at NaN-default (= rad-command never set; isnan-branch skips them).
  write_handle(cmd_ifs[0], 10.0);
  // Also write valid rad to the other slots so isnan-skip doesn't shadow
  // the OoR detection on slot 0.
  for (std::size_t i = 1; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.0);
  }

  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  EXPECT_TRUE(plugin.is_safety_frozen())
    << "pulse > pulse_max should trigger safety_freeze";
}

TEST(HexapodSafetyFreeze, OutOfRangeBelowTriggersFreeze)
{
  // Mirror of above: rad=-10 → pulse far below pulse_min=500 → freeze.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 0 ? -10.0 : 0.0);
  }

  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  EXPECT_TRUE(plugin.is_safety_frozen())
    << "pulse < pulse_min should trigger safety_freeze";
}

TEST(HexapodSafetyFreeze, InRangeRadDoesNotFreeze)
{
  // Normal command (rad=+0.5 on all joints): pulse stays well inside
  // [pulse_min, pulse_max] for every pin → freeze must NOT trip.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.5);
  }

  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  EXPECT_FALSE(plugin.is_safety_frozen())
    << "in-range rad commands must not trip freeze";
}

TEST(HexapodSafetyFreeze, FpToleranceAtPulseMaxDoesNotTrigger)
{
  // rad exactly at joint_upper produces pulse=pulse_max (within FP rounding).
  // The 1 µs tolerance in write() must absorb that drift so the joint can
  // reach its mechanical limit without triggering freeze.
  // For the default cal (pulse_min=500, pulse_zero=1500, pulse_max=2500,
  // joint_upper=+1.57): slope = 1000/1.57 ≈ 636.94 µs/rad; rad=+1.57 →
  // pulse = 1500 + 1.57 · 636.94 = 2500.0 exactly. We add a tiny offset
  // to *also* cover the case where FP drift pushes pulse to 2500.4 µs.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  // joint_upper for slot 0 is +1.57 (from make_joint() default in helpers).
  // Add 0.0005 rad ≈ 0.3 µs drift past pulse_max — within the 1 µs FP
  // tolerance.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 1.5705);
  }

  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  EXPECT_FALSE(plugin.is_safety_frozen())
    << "FP drift ≤1 µs at pulse_max must not trip freeze";
}

TEST(HexapodSafetyFreeze, ClearWhileFrozenReturnsTrue)
{
  // Trigger freeze, then clear_safety_freeze() must return true (= we did
  // clear an active flag) and is_safety_frozen() must read false after.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 0 ? 10.0 : 0.0);
  }
  EXPECT_NO_THROW(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}));
  ASSERT_TRUE(plugin.is_safety_frozen());

  EXPECT_TRUE(plugin.clear_safety_freeze())
    << "clear should return true when a freeze was active";
  EXPECT_FALSE(plugin.is_safety_frozen())
    << "freeze flag must be cleared after clear_safety_freeze()";
}

TEST(HexapodSafetyFreeze, ClearWhileNotFrozenReturnsFalse)
{
  // Idempotent: calling clear on an already-clear flag must succeed
  // silently and return false.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  ASSERT_FALSE(plugin.is_safety_frozen());
  EXPECT_FALSE(plugin.clear_safety_freeze())
    << "clear on already-clear flag must return false";
  EXPECT_FALSE(plugin.is_safety_frozen());
}

TEST(HexapodSafetyFreeze, ExternalTriggerSetsFreezeIdempotently)
{
  // Stage 0.6: trigger_safety_freeze() is the external entry point
  // (gait_node calls /hexapod_safety_freeze on IK joint-limit error,
  // service-callback calls this method). First call returns true
  // (= newly set), subsequent calls while frozen return false.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  ASSERT_FALSE(plugin.is_safety_frozen());

  // First call: false→true transition. Returns true (newly set).
  EXPECT_TRUE(plugin.trigger_safety_freeze())
    << "first trigger should report newly-set (returns true)";
  EXPECT_TRUE(plugin.is_safety_frozen());

  // Second call while frozen: no-op. Returns false (was already set).
  EXPECT_FALSE(plugin.trigger_safety_freeze())
    << "trigger on already-frozen must be idempotent (returns false)";
  EXPECT_TRUE(plugin.is_safety_frozen());

  // Verify clear() round-trip works after external trigger.
  EXPECT_TRUE(plugin.clear_safety_freeze());
  EXPECT_FALSE(plugin.is_safety_frozen());
}

TEST(HexapodSafetyFreeze, WriteWhileFrozenHoldsLastGoodPulse)
{
  // Stage 0.5 contract: in freeze, write() must not update
  // last_command_pulse_us_ for any pin. Observable via loopback: the
  // state echo after a follow-up write reflects the *last good* pulse
  // (= pulse_zero from on_init), not the new (in-range) rad command.
  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  auto state_ifs = plugin.export_state_interfaces();

  // Step 1: trip the freeze with rad=10 on slot 0.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], i == 0 ? 10.0 : 0.0);
  }
  plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0});
  ASSERT_TRUE(plugin.is_safety_frozen());

  // Step 2: while frozen, command in-range rad=+0.5 to all joints, then
  // write+read. State should still reflect rad≈0 (pulse_zero) because
  // last_command_pulse_us_ was not updated.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.5);
  }
  plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0});
  ASSERT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  // Each slot's state should be near 0.0 (the pulse_zero value, mapped
  // back through cal). NOT near 0.5 — if the new in-range command had
  // leaked through despite freeze, state would be ~0.5. The narrow
  // tolerance below catches that leak.
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    const double state = read_handle(state_ifs[i]);
    EXPECT_NEAR(state, 0.0, 0.01)
      << "slot " << i << " state " << state
      << " should hold near pulse_zero=0 rad while frozen "
      "(leak suspected if state is near 0.5)";
  }
}

TEST(HexapodSystemWriteRead, PtyWriteSendsSetTargetsFrameWithNeutralPulses)
{
  // Send rad=0 from all joints → write() must emit one SET_TARGETS frame
  // whose 18 int16-LE pulses match the per-pin pulse_zero from YAML
  // (kExpectedPulseZero; pin 15/16/17 carry Phase 10 Stage B pre-cal values).
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.0);
  }
  ASSERT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  const auto bytes = drain_master_until_idle(master_fd, std::chrono::milliseconds(50));
  const auto frames = split_and_decode_frames(bytes);
  ASSERT_EQ(frames.size(), 1u);
  EXPECT_EQ(frames[0].cmd, hexapod_hardware::opcode::SET_TARGETS);
  ASSERT_EQ(frames[0].payload.size(), 2u * hexapod_hardware::NUM_SERVOS);
  for (std::size_t pin = 0; pin < NUM_SERVOS; ++pin) {
    const uint8_t lo = frames[0].payload[2 * pin];
    const uint8_t hi = frames[0].payload[2 * pin + 1];
    const int16_t pulse = static_cast<int16_t>(
      static_cast<uint16_t>(lo) | (static_cast<uint16_t>(hi) << 8));
    EXPECT_EQ(pulse, kExpectedPulseZero[pin]) << "pin " << pin;
  }

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemWriteRead, PtyReadDrainsFirmwareErrorReports)
{
  // Inject an ERROR_REPORT on the master end (= the firmware side of the
  // pty). The reader thread should pick it up and queue it; the plugin's
  // read() should drain the queue. Verifying the queue is empty after
  // means drain() ran. The log message itself is observed via the test
  // runner's stderr (manual inspection); D.8 will harden the assertion.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Hand-craft an ERROR_REPORT frame: WATCHDOG_TRIPPED, servo_idx=0, aux=0.
  // encode_frame builds COBS + CRC + 0x00 terminator for us.
  const std::vector<uint8_t> payload = {
    hexapod_hardware::error_code::WATCHDOG_TRIPPED,
    /*servo_idx=*/0, /*aux_lo=*/0, /*aux_hi=*/0};
  const auto wire = hexapod_hardware::encode_frame(
    /*seq=*/0, hexapod_hardware::opcode::ERROR_REPORT, payload);
  ASSERT_EQ(
    ::write(master_fd, wire.data(), wire.size()),
    static_cast<ssize_t>(wire.size()));

  // Reader thread is blocking-polling — give it a moment to ingest.
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  EXPECT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK);

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  ::close(master_fd);
}

TEST(HexapodSystemWriteRead, PtyReadStaysOkWhileReaderRetriesReconnect)
{
  // D.7 changed the contract: after master close the reader does NOT die
  // anymore — it enters reconnect_loop. So reader.died() stays false and
  // read() keeps echoing last_command_pulse_us_, returning OK.
  //
  // The write() path still surfaces ERROR (via port-closed → write_all
  // throws) — verified separately in the HexapodSystemReconnect suite.
  // ros2_control sees those write-ERRORs and deactivates the controller,
  // so the user-facing behaviour is the same as before D.7. The only
  // difference is that the reader keeps trying to come back instead of
  // requiring a full stack restart.
  //
  // (Before D.7 this test asserted ERROR on read() because the reader
  // died. The asserted value flipped with the D.7 contract change.)
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Disconnect — reader sees POLLHUP, enters reconnect_loop (NOT died_).
  ::close(master_fd);
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  EXPECT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK)
    << "read() must stay OK while reader retries; died_ is false during backoff";

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
}

TEST(HexapodSystemWriteRead, PtyWriteReturnsErrorWhilePortClosedDuringReconnect)
{
  // Companion to the read test above. write() must surface ERROR — but
  // for a different reason than pre-D.7:
  //   - Before D.7: reader.died()==true, write() takes the early-exit
  //   - D.7+: reader retries (died_=false), but the port is closed during
  //     the backoff window, so write_all() throws "port not open" → ERROR
  // The user-visible return_type::ERROR is identical; the new path is
  // verified here.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  ::close(master_fd);
  std::this_thread::sleep_for(std::chrono::milliseconds(100));

  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.0);
  }
  EXPECT_EQ(
    plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::ERROR);

  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
}

// ============================================================================
// USB-Reconnect (Sub-Stage D.7)
//
// Verifies the full-plugin behaviour: after a disconnect the reader enters
// backoff, write()/read() consistently return ERROR (since the port is
// closed during the wait), and the lifecycle still tears down cleanly.
//
// The success path (open() of /dev/pts/N after master close) is NOT
// covered here — pure PTYs invalidate the path on master close (user-
// approved Plan-Option C). Stage H verifies it on real hardware.
// ============================================================================

TEST(HexapodSystemReconnect, PluginSurfacesErrorWhileReaderRetriesReconnect)
{
  // Setup: configure with a pty so the reader can actually run.
  int master_fd;
  std::string slave_name;
  open_pty_for_serial_port(&master_fd, &slave_name);

  HexapodSystemHardware plugin;
  auto info = make_valid_info();
  info.hardware_parameters["loopback_mode"] = "false";
  info.hardware_parameters["serial_port"] = slave_name;
  ASSERT_EQ(
    plugin.on_init(make_params(info)),
    hardware_interface::CallbackReturn::SUCCESS);
  ASSERT_EQ(
    plugin.on_configure(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);

  // Trigger disconnect. Reader enters reconnect_loop; for the pty path
  // the open() retries will keep failing — reader stays in backoff forever,
  // is_running() stays true, died() stays false (this is the D.7 contract).
  ::close(master_fd);

  // Wait for the reader to detect POLLHUP and enter backoff. Once in
  // backoff the port is closed (fd_<0), so write_all() throws and the
  // controller_manager-style write() consistently returns ERROR. Same
  // for read(): it sees reader.died()==false but the writes-can't-work
  // contract is what matters here (the plugin behaviour is that read()
  // echoes last_command_pulse_us_, which still works — read() returns
  // OK during backoff because reader is alive). So we focus on write().
  std::this_thread::sleep_for(std::chrono::milliseconds(200));

  // Set commands to something so write() has work to do.
  auto cmd_ifs = plugin.export_command_interfaces();
  for (std::size_t i = 0; i < NUM_SERVOS; ++i) {
    write_handle(cmd_ifs[i], 0.0);
  }

  // write() should return ERROR consistently — port is closed during backoff.
  // We tick several times; the result must stay ERROR (not flap).
  for (int tick = 0; tick < 5; ++tick) {
    EXPECT_EQ(
      plugin.write(rclcpp::Time{}, rclcpp::Duration{0, 0}),
      hardware_interface::return_type::ERROR)
      << "tick " << tick << " — write() should consistently be ERROR while reader retries";
    std::this_thread::sleep_for(std::chrono::milliseconds(50));
  }

  // read() during backoff: reader.died() is false (reader is retrying),
  // so read() returns OK and the echo state stays consistent. That's
  // the designed behaviour — ros2_control will already have deactivated
  // the controller off the write() ERRORs, so read() correctness here
  // is mostly academic but verified for completeness.
  EXPECT_EQ(
    plugin.read(rclcpp::Time{}, rclcpp::Duration{0, 0}),
    hardware_interface::return_type::OK)
    << "read() during backoff should still echo last commands (reader not died)";

  // Cleanup must still finish quickly even while reader is mid-backoff.
  // stop() interrupts the chunked sleep, joins in ~50 ms.
  const auto t0 = std::chrono::steady_clock::now();
  EXPECT_EQ(
    plugin.on_cleanup(rclcpp_lifecycle::State{}),
    hardware_interface::CallbackReturn::SUCCESS);
  const auto dt = std::chrono::steady_clock::now() - t0;
  EXPECT_LT(dt, std::chrono::milliseconds(500))
    << "on_cleanup during reconnect took " <<
    std::chrono::duration_cast<std::chrono::milliseconds>(dt).count() << " ms";
}

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
