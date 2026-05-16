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
Phase 4 simulation bringup with ros2_control.

Extends the Phase 3 sim launcher with controller-spawner nodes:
  1. gz sim + RSP + spawn + ros_gz bridge (parallel, like Phase 3)
  2. After spawn-Node exits: spawn joint_state_broadcaster
  3. After JSB-spawner exits: spawn the 6 leg_*_controller nodes

The two-stage OnProcessExit chain is the standard ros2_control pattern.
Reason: the controller_manager only exists after the gz_ros2_control
plugin loads, which only happens after the robot is spawned in the sim.
Starting spawners earlier would just produce retry-spam in the logs.

Phase 3's hexapod_gazebo/launch/sim.launch.py remains as the
"plain sim, no controllers" alternative (useful for friction/physics
debugging in isolation from the controller stack).
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
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
    pkg_hexapod_bringup = FindPackageShare('hexapod_bringup')
    pkg_ros_gz_sim = FindPackageShare('ros_gz_sim')

    default_urdf = PathJoinSubstitution([
        pkg_hexapod_description, 'urdf', 'hexapod.urdf.xacro',
    ])
    bridge_config = PathJoinSubstitution([
        pkg_hexapod_gazebo, 'config', 'bridge.yaml',
    ])
    bridge_foot_contact_config = PathJoinSubstitution([
        pkg_hexapod_bringup, 'config', 'bridge_foot_contact.yaml',
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
    declare_enable_foot_contact = DeclareLaunchArgument(
        'enable_foot_contact',
        default_value='true',
        description=(
            'Phase 5 Stufe D: Foot-Bodenkontakt-Sensoren aktivieren. '
            'Bei true: xacro-Sensor-Block, Bridge und Konversionsknoten '
            'starten. Bei false: keine Sensor-Computation in Gazebo, '
            'keine /leg_<n>/foot_contact-Topics in ROS.'
        ),
    )

    # robot_description: xacro is evaluated at launch time.
    # ParameterValue with value_type=str prevents rclpy from trying to
    # YAML-parse the URDF string into a dict (a common gotcha).
    # enable_foot_contact wird als xacro-Argument durchgereicht und steuert
    # den conditional Include von hexapod.foot_contact.xacro.
    robot_description = ParameterValue(
        Command([
            'xacro ', LaunchConfiguration('urdf'),
            ' enable_foot_contact:=', LaunchConfiguration('enable_foot_contact'),
        ]),
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

    # Foot-Kontakt-Bridge: separate Bridge-Instance, die nur dann
    # gestartet wird wenn enable_foot_contact:=true. Das ist die
    # mittlere Schicht der 3-Schicht-Toggle-Architektur (Stufe-D-
    # Design-Entscheidung 3 A): xacro-Sensor + Bridge + Conv-Node.
    foot_contact_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_foot_contact_bridge',
        output='screen',
        parameters=[{
            'config_file': bridge_foot_contact_config,
            'use_sim_time': True,
        }],
        condition=IfCondition(LaunchConfiguration('enable_foot_contact')),
    )

    # Foot-Kontakt-Konversionsknoten aus hexapod_sensors. Subscribed
    # auf 6 ros_gz_interfaces/Contacts und publisht 6 std_msgs/Bool
    # auf /leg_<n>/foot_contact. Conditional auf enable_foot_contact.
    foot_contact_publisher = Node(
        package='hexapod_sensors',
        executable='foot_contact_publisher',
        name='foot_contact_publisher',
        output='screen',
        parameters=[{
            'use_sim_time': True,
        }],
        condition=IfCondition(LaunchConfiguration('enable_foot_contact')),
    )

    # --- Controller spawners (each is a one-shot node) ---
    # The spawner loads, configures and activates a controller via the
    # /controller_manager/spawner service, then exits. We chain them via
    # OnProcessExit so each stage only fires once the prerequisite is up.

    spawn_jsb = Node(
        package='controller_manager',
        executable='spawner',
        name='spawn_joint_state_broadcaster',
        arguments=[
            'joint_state_broadcaster',
            '--controller-manager', '/controller_manager',
        ],
        output='screen',
    )

    leg_controller_spawners = [
        Node(
            package='controller_manager',
            executable='spawner',
            name=f'spawn_leg_{i}_controller',
            arguments=[
                f'leg_{i}_controller',
                '--controller-manager', '/controller_manager',
            ],
            output='screen',
        )
        for i in range(1, 7)
    ]

    # Stage 1: spawn-Node exit -> JSB-spawner.
    # spawn-Node exits once the robot is in the sim. Only then is the
    # gz_ros2_control plugin loaded and the controller_manager available.
    after_spawn_start_jsb = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn,
            on_exit=[spawn_jsb],
        ),
    )

    # Stage 2: JSB-spawner exit -> 6 leg-controller spawners (parallel).
    # Trajectory controllers need /joint_states to be flowing before they
    # activate, otherwise their state estimate is empty.
    after_jsb_start_leg_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_jsb,
            on_exit=leg_controller_spawners,
        ),
    )

    return LaunchDescription([
        declare_urdf,
        declare_world,
        declare_spawn_z,
        declare_enable_foot_contact,
        gz_sim,
        robot_state_publisher,
        spawn,
        bridge,
        foot_contact_bridge,
        foot_contact_publisher,
        after_spawn_start_jsb,
        after_jsb_start_leg_controllers,
    ])
