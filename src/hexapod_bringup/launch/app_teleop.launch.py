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

"""
Block I Phase 2 — Komfort-Bringup der app-zugewandten Teleop-Schicht.

Ein Aufruf startet:
  - ``rosbridge_websocket`` + ``rosapi`` (:9090)  — die App<->ROS-Naht
  - ``joy_to_twist`` im **app-Modus** (KEIN ``joy_node`` → die App ist die
    alleinige ``/joy``-Quelle, D3/NF7)

Voraussetzung: ein Sim-Walk-Bringup läuft **bereits** (gait_node + Controller
+ Sim oben, Roboter steht), z.B.::

    ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=0.0

Danach publisht die Android-App (oder ``tools/joy_ws_test_client.py``)
``sensor_msgs/Joy`` über rosbridge → der Roboter fährt.

    ros2 launch hexapod_bringup app_teleop.launch.py

Args:
    controller     Controller-Profil (Default ps4_usb) — bestimmt das
                   /joy-Layout, gegen das joy_to_twist normalisiert.
    port           rosbridge-Port (Default 9090).
    use_sim_time   true (Sim-Default; joy_to_twist + rosbridge gegen /clock).
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    joy_teleop_launch = os.path.join(
        get_package_share_directory('hexapod_teleop'),
        'launch', 'joy_teleop.launch.py',
    )
    rosbridge_launch = os.path.join(
        get_package_share_directory('hexapod_bringup'),
        'launch', 'rosbridge.launch.py',
    )

    controller_arg = DeclareLaunchArgument(
        'controller', default_value='ps4_usb',
        description='Controller-Profil (config/<name>.yaml) = /joy-Layout.',
    )
    port_arg = DeclareLaunchArgument(
        'port', default_value='9090',
        description='rosbridge-WebSocket-Port (Contract §0).',
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='true in der Sim (gegen /clock), false auf echter HW.',
    )

    rosbridge = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rosbridge_launch),
        launch_arguments={
            'port': LaunchConfiguration('port'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
    )

    app_teleop = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(joy_teleop_launch),
        launch_arguments={
            'joy_source': 'app',
            'controller': LaunchConfiguration('controller'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
    )

    return LaunchDescription([
        controller_arg,
        port_arg,
        use_sim_time_arg,
        rosbridge,
        app_teleop,
    ])
