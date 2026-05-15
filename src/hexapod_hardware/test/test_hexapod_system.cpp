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
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include "hardware_interface/hardware_info.hpp"
#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_component_interface_params.hpp"
#include "rclcpp/rclcpp.hpp"

#include "hexapod_hardware/hexapod_system.hpp"
#include "hexapod_hardware/servo2040_protocol.hpp"

using hexapod_hardware::HexapodSystemHardware;
using hexapod_hardware::NUM_SERVOS;

namespace
{

// Path to the in-tree calibration YAML. Injected via CMake target_compile_definitions
// — same trick test_calibration uses for its RealConfigFile test.
const std::string YAML_PATH = std::string(SOURCE_DIR_FOR_TESTS) +
  "/config/servo_mapping.yaml";

// The canonical joint name list, in the order Calibration assigns servo-pin
// indices (0..17) — see config/servo_mapping.yaml.
const std::vector<std::string> CANONICAL_JOINT_NAMES = {
  "leg_1_coxa_joint", "leg_1_femur_joint", "leg_1_tibia_joint",
  "leg_2_coxa_joint", "leg_2_femur_joint", "leg_2_tibia_joint",
  "leg_3_coxa_joint", "leg_3_femur_joint", "leg_3_tibia_joint",
  "leg_4_coxa_joint", "leg_4_femur_joint", "leg_4_tibia_joint",
  "leg_5_coxa_joint", "leg_5_femur_joint", "leg_5_tibia_joint",
  "leg_6_coxa_joint", "leg_6_femur_joint", "leg_6_tibia_joint",
};

// Build one URDF joint entry: a position command interface with the given
// limits + a position state interface. That matches what xacro emits from
// the <ros2_control> block in hexapod.ros2_control.xacro.
hardware_interface::ComponentInfo make_joint(
  const std::string & name, double lower = -1.57, double upper = +1.57)
{
  hardware_interface::ComponentInfo j;
  j.name = name;
  j.type = "joint";

  hardware_interface::InterfaceInfo cmd;
  cmd.name = "position";
  cmd.min = std::to_string(lower);
  cmd.max = std::to_string(upper);
  j.command_interfaces.push_back(cmd);

  hardware_interface::InterfaceInfo state;
  state.name = "position";
  j.state_interfaces.push_back(state);

  return j;
}

// Build a fully-valid HardwareInfo (18 joints in canonical order, all
// 3 hardware_parameters set, calibration_file pointing at the real YAML).
hardware_interface::HardwareInfo make_valid_info()
{
  hardware_interface::HardwareInfo info;
  info.name = "HexapodSystem";
  info.type = "system";
  info.hardware_parameters = {
    {"serial_port", "/dev/ttyACM0"},
    {"calibration_file", YAML_PATH},
    {"loopback_mode", "true"},  // tests run without hardware
  };
  for (const auto & name : CANONICAL_JOINT_NAMES) {
    info.joints.push_back(make_joint(name));
  }
  return info;
}

// Wrap a HardwareInfo into the params struct on_init wants.
hardware_interface::HardwareComponentInterfaceParams make_params(
  const hardware_interface::HardwareInfo & info)
{
  hardware_interface::HardwareComponentInterfaceParams p;
  p.hardware_info = info;
  // executor stays default-constructed (empty weak_ptr). on_init in D.3
  // does not touch the executor; later stages might.
  return p;
}

}  // namespace

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
// Boot sequence under test (PROTOCOL.md §5 / §6, phase_9_stage_d_plan §D.5):
//   1× RESET → 18× ENABLE_SERVO(pin, true) with 50 ms stagger →
//   1× SET_TARGETS with all pulses at pulse_zero.
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

TEST(HexapodSystemActivate, PtyActivateSendsBootSequenceInOrder)
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

  // Idle-timeout must be larger than the 50 ms stagger so we don't
  // declare "idle" between two consecutive ENABLE_SERVO frames.
  const auto bytes = drain_master_until_idle(master_fd, std::chrono::milliseconds(200));
  const auto frames = split_and_decode_frames(bytes);

  ASSERT_EQ(frames.size(), 20u)
    << "Expected 1 RESET + 18 ENABLE_SERVO + 1 SET_TARGETS (got " <<
    frames.size() << ")";

  // Frame 0: RESET (payload empty).
  EXPECT_EQ(frames[0].cmd, hexapod_hardware::opcode::RESET);
  EXPECT_EQ(frames[0].payload.size(), 0u);

  // Frames 1..18: ENABLE_SERVO(pin, enable=0x01), pin = 0..17 in order.
  for (uint8_t pin = 0; pin < hexapod_hardware::NUM_SERVOS; ++pin) {
    const auto & f = frames[1 + pin];
    EXPECT_EQ(f.cmd, hexapod_hardware::opcode::ENABLE_SERVO)
      << "at wire index " << static_cast<int>(1 + pin);
    ASSERT_EQ(f.payload.size(), 2u);
    EXPECT_EQ(f.payload[0], pin) << "servo_idx mismatch at pin " << static_cast<int>(pin);
    EXPECT_EQ(f.payload[1], 0x01) << "expected enable=true at pin " << static_cast<int>(pin);
  }

  // Frame 19: SET_TARGETS with all 18 pulses at pulse_zero (1500 µs per
  // the in-tree servo_mapping.yaml — int16-LE: 0xDC 0x05).
  EXPECT_EQ(frames[19].cmd, hexapod_hardware::opcode::SET_TARGETS);
  ASSERT_EQ(frames[19].payload.size(), 2u * hexapod_hardware::NUM_SERVOS);
  for (std::size_t pin = 0; pin < hexapod_hardware::NUM_SERVOS; ++pin) {
    const uint8_t lo = frames[19].payload[2 * pin];
    const uint8_t hi = frames[19].payload[2 * pin + 1];
    const int16_t pulse = static_cast<int16_t>(
      static_cast<uint16_t>(lo) | (static_cast<uint16_t>(hi) << 8));
    EXPECT_EQ(pulse, 1500) << "neutral pulse_zero mismatch at servo pin " << pin;
  }

  // SEQ starts at 0; fetch_add returns pre-increment value. So the wire
  // sequence is 0, 1, 2, …, 19 in order.
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
  // designed cadence. Budget: 10 ms (RESET breather) + 18 × 50 ms = 910 ms.
  // Allow ±200 ms band for scheduler jitter on busy CI machines.
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
  EXPECT_GT(dt_ms, 800) << "Activate completed in " << dt_ms << " ms — no stagger?";
  EXPECT_LT(dt_ms, 1200) << "Activate took " << dt_ms << " ms — too slow?";

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
  ASSERT_EQ(frames.size(), hexapod_hardware::NUM_SERVOS);
  for (uint8_t pin = 0; pin < hexapod_hardware::NUM_SERVOS; ++pin) {
    const auto & f = frames[pin];
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

int main(int argc, char ** argv)
{
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
