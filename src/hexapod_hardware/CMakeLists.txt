cmake_minimum_required(VERSION 3.16)
project(hexapod_hardware)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
  set(CMAKE_CXX_STANDARD_REQUIRED ON)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(controller_manager REQUIRED)
find_package(yaml-cpp REQUIRED)
find_package(std_srvs REQUIRED)
find_package(std_msgs REQUIRED)

add_library(${PROJECT_NAME} SHARED
  src/servo2040_protocol.cpp
  src/calibration.cpp
  src/serial_port.cpp
  src/servo2040_reader.cpp
  src/error_report_log.cpp
  src/hexapod_system.cpp
)

target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

ament_target_dependencies(${PROJECT_NAME}
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
  std_srvs
  std_msgs
)

target_link_libraries(${PROJECT_NAME} yaml-cpp)

pluginlib_export_plugin_description_file(hardware_interface hexapod_hardware.xml)

install(
  TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

install(
  DIRECTORY include/
  DESTINATION include
)

install(
  DIRECTORY config
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  find_package(ament_cmake_gtest REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(test_calibration test/test_calibration.cpp)
  target_link_libraries(test_calibration ${PROJECT_NAME})
  # Inject source-tree path so the test can load the installed YAML
  # directly from src/ (build-tree path is stable; install-path lookup is
  # exercised separately by the stage-I launch-testing smoke test).
  target_compile_definitions(test_calibration PRIVATE
    SOURCE_DIR_FOR_TESTS="${CMAKE_CURRENT_SOURCE_DIR}")

  ament_add_gtest(test_servo2040_protocol test/test_servo2040_protocol.cpp)
  target_link_libraries(test_servo2040_protocol ${PROJECT_NAME})

  ament_add_gtest(test_serial_port test/test_serial_port.cpp)
  # -lutil for openpty(3); only the test needs it, not the runtime lib.
  target_link_libraries(test_serial_port ${PROJECT_NAME} util)

  ament_add_gtest(test_servo2040_reader test/test_servo2040_reader.cpp)
  target_link_libraries(test_servo2040_reader ${PROJECT_NAME} util)

  ament_add_gtest(test_error_report_log test/test_error_report_log.cpp)
  target_link_libraries(test_error_report_log ${PROJECT_NAME})

  ament_add_gtest(test_hexapod_system test/test_hexapod_system.cpp)
  # util for openpty(3) (used by D.4 on_configure tests).
  target_link_libraries(test_hexapod_system ${PROJECT_NAME} util)
  # Source-tree YAML path for the on_init happy-path test.
  target_compile_definitions(test_hexapod_system PRIVATE
    SOURCE_DIR_FOR_TESTS="${CMAKE_CURRENT_SOURCE_DIR}")

  # Stage E — pluginlib runtime registration. Loads the installed plugin
  # via pluginlib::ClassLoader and verifies the manifest/library wiring.
  ament_add_gtest(test_plugin_registration test/test_plugin_registration.cpp)
  target_link_libraries(test_plugin_registration ${PROJECT_NAME})
  ament_target_dependencies(test_plugin_registration pluginlib hardware_interface)
  # Same SOURCE_DIR_FOR_TESTS define as test_hexapod_system — the shared
  # test_helpers.hpp uses it to locate config/servo_mapping.yaml.
  target_compile_definitions(test_plugin_registration PRIVATE
    SOURCE_DIR_FOR_TESTS="${CMAKE_CURRENT_SOURCE_DIR}")
endif()

ament_export_include_directories(include)
ament_export_libraries(${PROJECT_NAME})
ament_export_dependencies(
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
  std_srvs
  std_msgs
)

ament_package()
