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
Torque-/Hitze-Viz (Phase 13 Finalisierung, Stage A1, Live-RViz).

Startet alles zum Anschauen der Gelenk-Auslastung in RViz — keine Sim/HW noetig:
  - static_transform_publisher (world -> base_link)
  - robot_state_publisher (xacro-URDF) + joint_state_publisher_gui (Slider,
    damit man Posen fahren und die Last live sehen kann)
  - torque_viz (publisht /torque_markers: N·m + % je Gelenk, CoG, Stuetz-Polygon)
  - rviz2 (view_torque.rviz, Fixed Frame base_link)

Laeuft alternativ auch gegen Sim/HW: dort einfach NUR den torque_viz-Node
(``ros2 run hexapod_gait torque_viz``) zusaetzlich starten und in der laufenden
RViz eine MarkerArray-Anzeige auf /torque_markers hinzufuegen.

Aufruf:
  ros2 launch hexapod_gait torque_viz.launch.py
  ros2 launch hexapod_gait torque_viz.launch.py total_mass:=3.0
  ros2 param set /torque_viz total_mass 3.0   (live)
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

BASE_LINK_Z_OVER_WORLD = '0.0291'


def generate_launch_description() -> LaunchDescription:
    desc_share = FindPackageShare('hexapod_description')
    xacro_path = PathJoinSubstitution([desc_share, 'urdf', 'hexapod.urdf.xacro'])
    rviz_config = PathJoinSubstitution([desc_share, 'config', 'view_torque.rviz'])

    robot_description = {
        'robot_description': ParameterValue(
            Command(['xacro ', xacro_path]), value_type=str),
    }

    total_mass_arg = DeclareLaunchArgument(
        'total_mass', default_value='0.0',
        description='Echtes Gesamtgewicht kg (0 = URDF-Massen ~2.63). '
                    'Live: ros2 param set /torque_viz total_mass 3.0')
    pose_arg = DeclareLaunchArgument(
        'pose', default_value='stand',
        description="'stand' = feet-closer Stand-Pose anzeigen (pose_publisher), "
                    "'slider' = joint_state_publisher_gui zum Hand-Fahren.")
    radial_arg = DeclareLaunchArgument(
        'radial', default_value='0.215',
        description='Stand-Pose radial (m), nur bei pose:=stand.')
    body_height_arg = DeclareLaunchArgument(
        'body_height', default_value='-0.120',
        description='Stand-Pose body_height (m), nur bei pose:=stand.')

    is_stand = IfCondition(
        PythonExpression(["'", LaunchConfiguration('pose'), "' == 'stand'"]))
    is_slider = IfCondition(
        PythonExpression(["'", LaunchConfiguration('pose'), "' == 'slider'"]))

    return LaunchDescription([
        total_mass_arg, pose_arg, radial_arg, body_height_arg,
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
        # pose:=stand → statische feet-closer Stand-Pose anzeigen
        Node(
            package='hexapod_gait', executable='pose_publisher',
            name='pose_publisher', output='screen', condition=is_stand,
            parameters=[{
                'radial': ParameterValue(
                    LaunchConfiguration('radial'), value_type=float),
                'body_height': ParameterValue(
                    LaunchConfiguration('body_height'), value_type=float),
            }],
        ),
        # pose:=slider → Gelenke per GUI fahren
        Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui', output='screen',
            condition=is_slider,
        ),
        Node(
            package='hexapod_gait', executable='torque_viz',
            name='torque_viz', output='screen',
            parameters=[{
                'total_mass': ParameterValue(
                    LaunchConfiguration('total_mass'), value_type=float),
            }],
        ),
        Node(
            package='rviz2', executable='rviz2', name='rviz2', output='screen',
            arguments=['-d', rviz_config],
        ),
    ])
