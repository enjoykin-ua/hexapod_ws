"""Display the hexapod URDF in RViz with joint sliders.

Startet:
  - robot_state_publisher (mit xacro-verarbeitetem URDF)
  - joint_state_publisher_gui (Slider fuer alle revolute Joints)
  - rviz2 (mit config/view.rviz)
"""

from launch import LaunchDescription
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


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
