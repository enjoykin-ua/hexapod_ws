"""
Phase 3 simulation bringup.

Starts Gazebo Harmonic with the empty.sdf default world (ground_plane + sun),
spawns the hexapod 0.20 m above the ground, and bridges /clock so every
ROS node with use_sim_time:=true sees simulation time.

In Phase 4 this launch will be extended with ros2_control controllers and
joint-state/cmd bridging. For now: physics + spawn + clock.
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    pkg_hexapod_description = FindPackageShare('hexapod_description')
    pkg_hexapod_gazebo = FindPackageShare('hexapod_gazebo')
    pkg_ros_gz_sim = FindPackageShare('ros_gz_sim')

    default_urdf = PathJoinSubstitution([
        pkg_hexapod_description, 'urdf', 'hexapod.urdf.xacro',
    ])
    bridge_config = PathJoinSubstitution([
        pkg_hexapod_gazebo, 'config', 'bridge.yaml',
    ])

    declare_urdf = DeclareLaunchArgument(
        'urdf',
        default_value=default_urdf,
        description='Absolute path to the top-level xacro file.',
    )
    declare_world = DeclareLaunchArgument(
        'world',
        default_value='empty.sdf',
        description='Gazebo world file (resolved against gz-sim search paths).',
    )
    declare_spawn_z = DeclareLaunchArgument(
        'spawn_z',
        default_value='0.20',
        description='Initial spawn height in meters; robot drops to ground.',
    )

    # robot_description: xacro is evaluated at launch time.
    # ParameterValue with value_type=str prevents rclpy from trying to
    # YAML-parse the URDF string into a dict (a common gotcha).
    robot_description = ParameterValue(
        Command(['xacro ', LaunchConfiguration('urdf')]),
        value_type=str,
    )

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py']),
        ),
        launch_arguments={
            'gz_args': ['-r ', LaunchConfiguration('world')],
            'on_exit_shutdown': 'true',
        }.items(),
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_hexapod',
        output='screen',
        arguments=[
            '-topic', '/robot_description',
            '-name', 'hexapod',
            '-z', LaunchConfiguration('spawn_z'),
        ],
    )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge_config,
            'use_sim_time': True,
        }],
    )

    return LaunchDescription([
        declare_urdf,
        declare_world,
        declare_spawn_z,
        gz_sim,
        robot_state_publisher,
        spawn,
        bridge,
    ])
