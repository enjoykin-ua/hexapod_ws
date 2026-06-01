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
Reachability-Viz (Phase 13 Stage 1, Teil 1).

Startet alles zum Anschauen der erreichbaren Fuss-Huelle in RViz — keine
Sim/HW noetig:
  - static_transform_publisher (world -> base_link)
  - robot_state_publisher (xacro-URDF) + joint_state_publisher_gui (Modell +
    Slider, damit man das Bein in der Wolke bewegen kann)
  - reachability_viz (publisht /reachability_markers: blau=aktuelles Limit,
    rot=volle kalibrierte Tibia-Beuge)
  - rviz2 (view_reach.rviz, Fixed Frame base_link, MarkerArray-Display)

Aufruf:
  ros2 launch hexapod_gait reachability_viz.launch.py
  ros2 launch hexapod_gait reachability_viz.launch.py leg:=leg_3
  ros2 launch hexapod_gait reachability_viz.launch.py leg:=all resolution:=10

Bein live umschalten (ohne Neustart):
  ros2 param set /reachability_viz leg leg_4
  ros2 param set /reachability_viz leg all
  ros2 param set /reachability_viz tibia_full_upper 2.0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# Z-Offset base_link ueber world (= display.launch.py, coxa_height/2).
BASE_LINK_Z_OVER_WORLD = '0.0291'


def generate_launch_description() -> LaunchDescription:
    desc_share = FindPackageShare('hexapod_description')
    xacro_path = PathJoinSubstitution([desc_share, 'urdf', 'hexapod.urdf.xacro'])
    rviz_config = PathJoinSubstitution([desc_share, 'config', 'view_reach.rviz'])

    robot_description = {
        'robot_description': ParameterValue(
            Command(['xacro ', xacro_path]), value_type=str),
    }

    leg_arg = DeclareLaunchArgument(
        'leg', default_value='leg_1',
        description="Bein: 'leg_1'..'leg_6' oder 'all'. Live: "
                    'ros2 param set /reachability_viz leg leg_3')
    resolution_arg = DeclareLaunchArgument(
        'resolution', default_value='14',
        description='Sweep-Schritte pro Gelenk (14³ Punkte/Bein).')
    tibia_full_arg = DeclareLaunchArgument(
        'tibia_full_upper', default_value='2.60',
        description='Rotes Tibia-Beuge-Limit in rad (~150° kalibriert).')
    with_jsp_gui_arg = DeclareLaunchArgument(
        'with_jsp_gui', default_value='true',
        description='joint_state_publisher_gui (Slider) starten?')

    return LaunchDescription([
        leg_arg, resolution_arg, tibia_full_arg, with_jsp_gui_arg,
        Node(
            package='tf2_ros', executable='static_transform_publisher',
            name='world_to_base_link', output='screen',
            arguments=[
                '--x', '0', '--y', '0', '--z', BASE_LINK_Z_OVER_WORLD,
                '--frame-id', 'world', '--child-frame-id', 'base_link'],
        ),
        Node(
            package='robot_state_publisher', executable='robot_state_publisher',
            name='robot_state_publisher', output='screen',
            parameters=[robot_description],
        ),
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui', output='screen',
            condition=IfCondition(LaunchConfiguration('with_jsp_gui')),
        ),
        Node(
            package='hexapod_gait', executable='reachability_viz',
            name='reachability_viz', output='screen',
            parameters=[{
                'leg': LaunchConfiguration('leg'),
                'resolution': ParameterValue(
                    LaunchConfiguration('resolution'), value_type=int),
                'tibia_full_upper': ParameterValue(
                    LaunchConfiguration('tibia_full_upper'), value_type=float),
            }],
        ),
        Node(
            package='rviz2', executable='rviz2', name='rviz2', output='screen',
            arguments=['-d', rviz_config],
        ),
    ])
