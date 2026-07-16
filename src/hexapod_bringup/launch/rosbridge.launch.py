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
Block I Phase 2 — rosbridge-Aufnahmeschicht (die App<->ROS-Naht, D2).

Startet ``rosbridge_websocket`` (WebSocket<->ROS-Brücke, JSON) auf Port 9090
+ ``rosapi_node`` (Topic-/Service-Discovery für die App). Ein WebSocket-Client
— die Android-App ODER ``tools/joy_ws_test_client.py`` — verbindet sich auf
``ws://<host>:9090``, publisht ``sensor_msgs/Joy`` und ruft Services. Die
bestehende ROS-Seite (``joy_to_twist`` etc.) läuft dabei **unverändert** (D3).

rosbridge ist **Unicast-TCP** → kein DDS-Multicast-Problem, funktioniert über
Router (Sim) UND Handy-Hotspot (real HW) identisch (D2/D4).

Aufruf (Sim, neben einem laufenden ``*_walk``-Bringup):
    ros2 launch hexapod_bringup rosbridge.launch.py

Args:
    port           WebSocket-Port (Default 9090 = interface_contract.md §0).
    address        Bind-Adresse ('' = alle Interfaces; im Feld ggf. auf die
                   Hotspot-IP einschränken).
    use_sim_time   true in der Sim (gegen /clock), false auf echter HW.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    port_arg = DeclareLaunchArgument(
        'port', default_value='9090',
        description='rosbridge-WebSocket-Port (Contract §0 = 9090).',
    )
    address_arg = DeclareLaunchArgument(
        'address', default_value='',
        description=(
            "Bind-Adresse. '' = alle Interfaces (Default). Im Feld optional "
            'auf die Hotspot-IP einschränken.'
        ),
    )
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='true in der Sim (gegen /clock), false auf echter HW (Pi).',
    )

    use_sim_time = ParameterValue(
        LaunchConfiguration('use_sim_time'), value_type=bool,
    )

    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        output='screen',
        parameters=[{
            'port': ParameterValue(LaunchConfiguration('port'), value_type=int),
            'address': LaunchConfiguration('address'),
            'use_sim_time': use_sim_time,
            # Service-Calls der App in eigenem Thread → kein Deadlock, wenn ein
            # Service selbst wieder über rosbridge kommuniziert.
            'call_services_in_new_thread': True,
            'send_action_goals_in_new_thread': True,
        }],
    )

    rosapi = Node(
        package='rosapi',
        executable='rosapi_node',
        name='rosapi',
        output='screen',
        parameters=[{
            'use_sim_time': use_sim_time,
        }],
    )

    return LaunchDescription([
        port_arg,
        address_arg,
        use_sim_time_arg,
        rosbridge,
        rosapi,
    ])
