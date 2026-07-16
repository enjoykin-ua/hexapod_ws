cmake_minimum_required(VERSION 3.8)
project(hexapod_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch config systemd
  DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  # Phase 9 Stage I.4: launch_testing-Smoke fuer real.launch.py loopback.
  # Verifiziert headless-CI dass das hexapod_hardware-Plugin via pluginlib
  # geladen wird, alle 7 Controller (1x JSB + 6x JTC) active werden, und
  # keine Prozesse mit Fehler exit'en. Braucht kein USB-Device + keinen
  # Servo2040 (loopback_mode=true).
  find_package(launch_testing_ament_cmake REQUIRED)
  add_launch_test(
    test/launch/test_real_launch_loopback.py
    TIMEOUT 60
  )
endif()

ament_package()
