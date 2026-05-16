"""Phase 9 real-hardware bringup (Stage G).

HW-Pendant zu sim.launch.py: startet den vollen ros2_control-Stack
OHNE Gazebo. Statt gz_ros2_control laedt der controller_manager das
hexapod_hardware-Plugin (siehe phase_9_progress.md Stage E/F), das
ueber USB-CDC mit der Servo2040-Firmware spricht (Phase 7).

Topologie:
  1. robot_state_publisher mit HW-URDF (use_sim:=false; LaunchArg
     loopback_mode und serial_port werden via xacro durchgereicht und
     landen im <param>-Block des hexapod_hardware-Plugins).
  2. ros2_control_node (controller_manager) mit controllers.real.yaml.
     Das Plugin laeuft im on_init/on_configure-Lifecycle.
  3. spawn_joint_state_broadcaster (one-shot Node).
  4. Nach JSB-Exit (OnProcessExit): 6 parallel leg_<n>_controller-
     Spawner. JTCs brauchen /joint_states-Flow zum Aktivieren, sonst
     bleibt deren State-Estimate leer.

Launch-Args:
  - loopback_mode (default false):
      true  -> Plugin oeffnet KEINEN seriellen Port, gibt geschriebene
               Commands als state zurueck. CI-/Dry-Run-/Bringup-Smoke.
      false -> Plugin oeffnet serial_port und kommuniziert mit echter
               Servo2040-Firmware. Stage H ff.
  - serial_port (default /dev/ttyACM0):
      USB-CDC-Device der Servo2040. Nur relevant wenn loopback_mode=false.

Was dieser Launch bewusst NICHT macht (siehe Plan-Doku Stufe G):
  - kein gait + kein teleop (Konsistenz zu sim.launch.py; User startet
    bei Bedarf 'ros2 launch hexapod_gait gait.launch.py' separat).
  - kein RViz (beim echten Roboter steht das physische Modell vor einem;
    bei Bedarf separat 'rviz2 -d view.rviz').
  - kein Gazebo, keine ros_gz-Bridge (das ist sim.launch.py's Job).
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    pkg_desc = FindPackageShare('hexapod_description')
    pkg_ctrl = FindPackageShare('hexapod_control')

    xacro_path = PathJoinSubstitution(
        [pkg_desc, 'urdf', 'hexapod.urdf.xacro'],
    )
    real_yaml = PathJoinSubstitution(
        [pkg_ctrl, 'config', 'controllers.real.yaml'],
    )

    declare_loopback_mode = DeclareLaunchArgument(
        'loopback_mode',
        default_value='false',
        description=(
            'true: Plugin oeffnet KEINEN seriellen Port und liefert '
            'geschriebene Commands als state zurueck. Fuer CI / Dry-Run / '
            'Bringup-Smoke ohne Hardware. '
            'false (default): echte Servo2040-Anbindung ueber serial_port.'
        ),
    )

    declare_serial_port = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyACM0',
        description=(
            'USB-CDC-Device der Servo2040. Nur relevant wenn loopback_mode=false. '
            'Bench-Setups mit mehreren USB-Devices: hier ueberschreiben.'
        ),
    )

    # robot_description: xacro wird zur Launch-Zeit evaluiert. use_sim
    # ist fest auf false (= HW-Pfad), die anderen beiden Args reichen
    # die LaunchConfiguration unveraendert an xacro weiter, sodass das
    # generierte URDF den <param>-Block des hexapod_hardware-Plugins
    # mit den richtigen Werten enthaelt.
    robot_description = {
        'robot_description': ParameterValue(
            Command([
                'xacro ', xacro_path,
                ' use_sim:=false',
                ' loopback_mode:=', LaunchConfiguration('loopback_mode'),
                ' serial_port:=', LaunchConfiguration('serial_port'),
            ]),
            value_type=str,
        ),
        'use_sim_time': False,
    }

    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[robot_description],
    )

    # ros2_control_node bekommt robot_description (fuer Hardware-Info-
    # Parsing) UND controllers.real.yaml (fuer controller_manager-Params
    # + die 7 Controller-Type-Deklarationen).
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        name='controller_manager',
        output='screen',
        parameters=[robot_description, real_yaml],
    )

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

    leg_spawners = [
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

    # JSB-Spawner exit -> 6 leg-Spawner parallel. JTCs brauchen
    # /joint_states-Flow zum Aktivieren, sonst leerer State-Estimate.
    # Pattern 1:1 wie sim.launch.py.
    after_jsb_start_leg_controllers = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_jsb,
            on_exit=leg_spawners,
        ),
    )

    return LaunchDescription([
        declare_loopback_mode,
        declare_serial_port,
        rsp,
        controller_manager,
        spawn_jsb,
        after_jsb_start_leg_controllers,
    ])
