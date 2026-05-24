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
Display the hexapod URDF in RViz with joint sliders.

Startet:
  - static_transform_publisher (world -> base_link, hebt Roboter so an,
    dass die Chassis-Unterseite auf world.z=0 liegt)
  - robot_state_publisher (mit xacro-verarbeitetem URDF)
  - joint_state_publisher_gui (Slider fuer alle revolute Joints)
  - rviz2 (mit config/view.rviz)
"""

from launch import LaunchDescription
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# Z-Offset von base_link ueber world.
# Ergibt sich aus max(coxa_height, body_height) / 2, weil die Coxa-Boxen
# Z-symmetrisch um die Chassis-Mitte sitzen und (weil coxa_height > body_height)
# der unterste Punkt des Roboters die Coxa-Unterkante ist, nicht der Body.
# Hard-coded weil Launch-Files keine Xacro-Properties lesen koennen
# (Werte aus urdf/hexapod_physical_properties.xacro: coxa_height = 0.0582).
# Bei Aenderung von coxa_height oder body_height: hier nachziehen.
BASE_LINK_Z_OVER_WORLD = '0.0291'


def generate_launch_description() -> LaunchDescription:
    pkg_share = FindPackageShare('hexapod_description')

    xacro_path = PathJoinSubstitution([pkg_share, 'urdf', 'hexapod.urdf.xacro'])
    rviz_config = PathJoinSubstitution([pkg_share, 'config', 'view.rviz'])

    robot_description = {
        'robot_description': ParameterValue(
            Command(['xacro ', xacro_path]),
            value_type=str,
        ),
    }

    return LaunchDescription([
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='world_to_base_link',
            output='screen',
            arguments=[
                '--x', '0', '--y', '0', '--z', BASE_LINK_Z_OVER_WORLD,
                '--frame-id', 'world',
                '--child-frame-id', 'base_link',
            ],
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[robot_description],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config],
        ),
    ])
