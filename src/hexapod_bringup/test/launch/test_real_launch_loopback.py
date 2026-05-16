# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# launch_testing-Smoke fuer real.launch.py im Loopback-Modus (Phase 9 Stage I.4).
#
# Verifiziert end-to-end im headless-CI dass:
#   1. real.launch.py mit loopback_mode:=true startet (kein USB-Port wird
#      geoeffnet, kein Servo2040-Anschluss noetig).
#   2. controller_manager-Services innerhalb von 30 s verfuegbar werden.
#   3. ListHardwareComponents zeigt die hexapod_hardware-Plugin-Komponente
#      im State PRIMARY_STATE_ACTIVE (id=3).
#   4. ListControllers zeigt alle 7 Controller (1x JSB + 6x leg_X_controller)
#      im State "active".
#   5. Innerhalb von 10 s nach Test-Start keinen Crash, dann sauberes
#      Shutdown durch launch_testing-Framework.
#
# Was dieser Test bewusst NICHT macht:
#   - Keine echte Servo2040-Anbindung (das war Stage H mit User-Smoke).
#   - Keine Trajectory-Action (Stage H H-T5).
#   - Kein USB-Disconnect-Smoke (Stage H H-T6).

import unittest

from controller_manager_msgs.srv import ListControllers, ListHardwareComponents

import launch
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
import launch_testing.actions

import pytest

import rclpy
from rclpy.node import Node


# lifecycle_msgs/State.PRIMARY_STATE_ACTIVE
LIFECYCLE_PRIMARY_STATE_ACTIVE = 3

EXPECTED_CONTROLLERS = [
    'joint_state_broadcaster',
    'leg_1_controller',
    'leg_2_controller',
    'leg_3_controller',
    'leg_4_controller',
    'leg_5_controller',
    'leg_6_controller',
]

# Timeout to wait for controllers + hardware components to fully come up.
# Spawner-Chain (JSB -> 6 JTC parallel via OnProcessExit) braucht typischerweise
# ~3-5 s; wir geben grosszuegig 30 s damit CI-Slowdowns abgefedert sind.
STARTUP_TIMEOUT_SEC = 30.0


@pytest.mark.rostest
def generate_test_description():
    real_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('hexapod_bringup'),
                'launch',
                'real.launch.py',
            ]),
        ),
        launch_arguments=[
            ('loopback_mode', 'true'),
        ],
    )

    return (
        launch.LaunchDescription([
            real_launch,
            launch_testing.actions.ReadyToTest(),
        ]),
        {},
    )


class TestRealLaunchLoopback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node: Node = rclpy.create_node('test_real_launch_loopback')

    def tearDown(self):
        self.node.destroy_node()

    def _wait_for_service(self, client, timeout_sec: float) -> bool:
        end_time = self.node.get_clock().now().nanoseconds + int(timeout_sec * 1e9)
        while self.node.get_clock().now().nanoseconds < end_time:
            if client.service_is_ready():
                return True
            rclpy.spin_once(self.node, timeout_sec=0.1)
        return False

    def _call_service(self, client, request, timeout_sec: float = 10.0):
        future = client.call_async(request)
        end_time = self.node.get_clock().now().nanoseconds + int(timeout_sec * 1e9)
        while self.node.get_clock().now().nanoseconds < end_time:
            rclpy.spin_once(self.node, timeout_sec=0.1)
            if future.done():
                return future.result()
        raise TimeoutError(f'Service call did not complete within {timeout_sec} s')

    def test_hardware_component_active(self):
        """Verify ListHardwareComponents zeigt das Plugin im ACTIVE-State."""
        client = self.node.create_client(
            ListHardwareComponents,
            '/controller_manager/list_hardware_components',
        )
        try:
            self.assertTrue(
                self._wait_for_service(client, STARTUP_TIMEOUT_SEC),
                f'/controller_manager/list_hardware_components nicht verfuegbar '
                f'nach {STARTUP_TIMEOUT_SEC} s',
            )
            # Retry the call up to 10 s in case the component is still being
            # configured/activated when the service first becomes available.
            end_time = self.node.get_clock().now().nanoseconds + int(10.0 * 1e9)
            last_components = []
            while self.node.get_clock().now().nanoseconds < end_time:
                response = self._call_service(client, ListHardwareComponents.Request())
                last_components = list(response.component)
                if any(
                    c.state.id == LIFECYCLE_PRIMARY_STATE_ACTIVE
                    and c.plugin_name == 'hexapod_hardware/HexapodSystemHardware'
                    for c in last_components
                ):
                    break
                rclpy.spin_once(self.node, timeout_sec=0.5)

            matching = [
                c for c in last_components
                if c.plugin_name == 'hexapod_hardware/HexapodSystemHardware'
            ]
            self.assertEqual(
                len(matching), 1,
                f'Expected exactly 1 hexapod_hardware-Component, got {len(matching)}: '
                f'{[(c.name, c.plugin_name) for c in last_components]}',
            )
            self.assertEqual(
                matching[0].state.id, LIFECYCLE_PRIMARY_STATE_ACTIVE,
                f'Plugin nicht im ACTIVE-State: state.id={matching[0].state.id} '
                f'(label={matching[0].state.label!r})',
            )
        finally:
            self.node.destroy_client(client)

    def test_all_controllers_active(self):
        """Verify ListControllers zeigt alle 7 Controller im active-State."""
        client = self.node.create_client(
            ListControllers,
            '/controller_manager/list_controllers',
        )
        try:
            self.assertTrue(
                self._wait_for_service(client, STARTUP_TIMEOUT_SEC),
                f'/controller_manager/list_controllers nicht verfuegbar '
                f'nach {STARTUP_TIMEOUT_SEC} s',
            )
            # Retry bis alle 7 Controller active sind oder Timeout.
            # Spawner-Chain (JSB -> 6 JTC via OnProcessExit) ist sequenziell:
            # nach jedem Spawner-Exit ~250 ms bis der naechste startet.
            # Gesamt-Activate-Zeit empirisch ~5-8 s; CI kann langsamer sein.
            # Wir warten bis zu 45 s damit auch langsame CI-Container abgedeckt.
            end_time = self.node.get_clock().now().nanoseconds + int(45.0 * 1e9)
            last_controllers = []
            while self.node.get_clock().now().nanoseconds < end_time:
                response = self._call_service(client, ListControllers.Request())
                last_controllers = list(response.controller)
                active_names = {
                    c.name for c in last_controllers if c.state == 'active'
                }
                if set(EXPECTED_CONTROLLERS).issubset(active_names):
                    break
                rclpy.spin_once(self.node, timeout_sec=0.5)

            names_states = {c.name: c.state for c in last_controllers}
            for expected in EXPECTED_CONTROLLERS:
                self.assertIn(
                    expected, names_states,
                    f'Controller {expected!r} nicht geladen. Geladen: '
                    f'{list(names_states.keys())}',
                )
                self.assertEqual(
                    names_states[expected], 'active',
                    f'Controller {expected!r} nicht active, sondern '
                    f'{names_states[expected]!r}',
                )
        finally:
            self.node.destroy_client(client)


# This test class runs after the launched processes have been shut down.
@launch_testing.post_shutdown_test()
class TestProcessOutput(unittest.TestCase):

    def test_no_error_exit_codes(self, proc_info):
        """Verify keiner der gelaunchten Prozesse mit Fehler-Exit-Code beendet."""
        # launch_testing.asserts.assertExitCodes() wirft AssertionError wenn
        # irgendein Prozess mit != 0 exit'd. Wir akzeptieren zusaetzlich:
        #   - 0:    sauberes Exit (Spawner-Nodes nach erfolgreichem Activate)
        #   - -2:   SIGINT (ros2_control_node + RSP von launch_testing-Shutdown)
        #   - -15:  SIGTERM (Spawner-Nodes die zur Shutdown-Zeit noch laufen
        #           weil OnProcessExit-Chain noch nicht durch war)
        launch_testing.asserts.assertExitCodes(
            proc_info,
            allowable_exit_codes=[0, -2, -15],
        )
