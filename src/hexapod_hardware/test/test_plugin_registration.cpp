// Copyright 2026 enjoykin
// Licensed under the Apache License, Version 2.0
//
// Stage E — pluginlib runtime registration tests for HexapodSystemHardware.
//
// These tests prove that the plugin manifest, the package.xml export
// and the installed shared library line up well enough that pluginlib's
// ClassLoader can find, load and instantiate the plugin at runtime.
// The on_init smoke check additionally pins the contract that a
// plugin loaded through pluginlib behaves the same as a directly
// constructed one — no ABI / symbol-loading drift between the .so and
// the declared base class.
//
// Black-box on purpose: we do NOT include hexapod_system.hpp here.
// The "18 interfaces" expectation in Test 3 comes from the package
// specification (6 legs × 3 joints, CLAUDE.md §1), not from the
// plugin's internal NUM_SERVOS constant. If someone changes the
// plugin to a different joint count without updating the spec,
// this test should — and will — fail.
//
// What this file deliberately does NOT cover:
//   - end-to-end lifecycle through controller_manager (Stage F/G/H)
//   - launch_testing with ros2_control_node (Plan §"Was Stage E NICHT macht")

#include <gtest/gtest.h>

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "pluginlib/class_loader.hpp"

#include "test_helpers.hpp"

namespace
{

// Manifest entry name in hexapod_hardware.xml — must match the
// `<class name="...">` attribute exactly.
constexpr const char * kPluginName = "hexapod_hardware/HexapodSystemHardware";

// Pluginlib looks up the base class via the ROS package that owns it
// (hardware_interface) plus its fully qualified C++ type.
constexpr const char * kBasePackage = "hardware_interface";
constexpr const char * kBaseClass = "hardware_interface::SystemInterface";

// Spec-derived: 6 legs × 3 joints/leg (CLAUDE.md §1). Hardcoded on
// purpose so a silent NUM_SERVOS change in the plugin is caught.
constexpr std::size_t kExpectedInterfaceCount = 18;

}  // namespace

// ============================================================================
// Test 1 — pluginlib finds the manifest entry AND can instantiate it.
// Catches: missing/typo'd <class name="..."> in hexapod_hardware.xml,
// missing pluginlib_export_plugin_description_file() in CMakeLists.txt,
// missing <hardware_interface plugin="..."/> export in package.xml,
// or a shared-library symbol that doesn't match the manifest type.
// ============================================================================

TEST(PluginRegistration, PluginIsLoadableViaPluginlib)
{
  pluginlib::ClassLoader<hardware_interface::SystemInterface> loader(
    kBasePackage, kBaseClass);

  const auto classes = loader.getDeclaredClasses();
  EXPECT_NE(
    std::find(classes.begin(), classes.end(), kPluginName),
    classes.end())
    << "Plugin '" << kPluginName << "' not found in pluginlib registry. "
    << "Check hexapod_hardware.xml + package.xml + "
    << "share/ament_index/resource_index/hardware_interface__pluginlib__plugin/hexapod_hardware";

  std::shared_ptr<hardware_interface::SystemInterface> plugin;
  ASSERT_NO_THROW(
    plugin = loader.createSharedInstance(kPluginName))
    << "createSharedInstance threw — likely missing/unexported symbol in libhexapod_hardware.so";
  ASSERT_NE(plugin, nullptr);
}

// ============================================================================
// Test 2 — the plugin loaded via pluginlib behaves identically to a
// directly constructed one for on_init. Anchors the contract that the
// shared library, base-class vtable and the declared type match.
// Uses loopback_mode=true so no real serial port is touched.
// ============================================================================

TEST(PluginRegistration, LoadedPluginPassesOnInit)
{
  pluginlib::ClassLoader<hardware_interface::SystemInterface> loader(
    kBasePackage, kBaseClass);
  auto plugin = loader.createSharedInstance(kPluginName);
  ASSERT_NE(plugin, nullptr);

  EXPECT_EQ(
    plugin->on_init(
      hexapod_hardware_test::make_params(hexapod_hardware_test::make_valid_info())),
    hardware_interface::CallbackReturn::SUCCESS);
}

// ============================================================================
// Test 3 — the loaded plugin exposes the spec'd interface count.
// Verifies that export_state_interfaces() / export_command_interfaces()
// stay reachable through the pluginlib-loaded vtable and that the
// plugin honours its 18-joint contract.
// ============================================================================

TEST(PluginRegistration, LoadedPluginExposes18Interfaces)
{
  pluginlib::ClassLoader<hardware_interface::SystemInterface> loader(
    kBasePackage, kBaseClass);
  auto plugin = loader.createSharedInstance(kPluginName);
  ASSERT_NE(plugin, nullptr);

  ASSERT_EQ(
    plugin->on_init(
      hexapod_hardware_test::make_params(hexapod_hardware_test::make_valid_info())),
    hardware_interface::CallbackReturn::SUCCESS);

  // The plugin overrides the old export_*_interfaces() API (Stage A–D),
  // so we must query it through the same vtable slot. The base-class
  // declaration carries [[deprecated]] in jazzy; suppress locally rather
  // than migrating the whole plugin to on_export_*_interfaces() — that
  // is a larger refactor that is out of Stage E's scope. Per
  // hardware_component_interface.hpp: when the old override returns a
  // non-empty vector, the framework uses it and skips on_export_*.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"
  EXPECT_EQ(plugin->export_state_interfaces().size(), kExpectedInterfaceCount);
  EXPECT_EQ(plugin->export_command_interfaces().size(), kExpectedInterfaceCount);
#pragma GCC diagnostic pop
}
