"""
Launch-File für PS-Controller-Teleop (Stufe A, USB).

Startet ``joy_node`` (ros-jazzy-joy) und ``joy_to_twist`` mit der
gewünschten Controller-Konfiguration aus ``config/<controller>.yaml``.

Aufruf:
- ``ros2 launch hexapod_teleop joy_teleop.launch.py``
  (Default: PS4 via USB — ``joy_source:=controller``)
- ``ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt``
  (Stufe B, BT)
- ``ros2 launch hexapod_teleop joy_teleop.launch.py joy_source:=app use_sim_time:=true``
  (Block I Phase 2: kein joy_node — die Android-App publisht /joy über
  rosbridge; siehe hexapod_bringup/launch/app_teleop.launch.py)

Voraussetzung (controller-Modus): PS4-Controller per USB angeschlossen,
``/dev/input/js0`` vorhanden. Roboter sollte schon laufen (Sim + Stand +
Gait), dieser Knoten erzeugt nur ``/cmd_vel`` + ``/cmd_body_height``.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    controller_arg = DeclareLaunchArgument(
        'controller',
        default_value='ps4_usb',
        description=(
            'Controller-Profilname (ohne .yaml) aus config/. Verfügbar: '
            'ps4_usb (USB) | ps4_bt (Bluetooth, C4). Lädt '
            'config/<controller>.yaml.'
        ),
    )

    joy_device_id_arg = DeclareLaunchArgument(
        'joy_device_id',
        default_value='0',
        description=(
            'SDL-Joystick-Index (int). Default 0 = erster Joystick. '
            'Bei mehreren Controllern kann das auf 1, 2, ... gesetzt '
            'werden. NICHT der /dev/input/jsX-Pfad — joy_node nutzt '
            'SDL2-Indizes, nicht Linux-Device-Pfade.'
        ),
    )

    autorepeat_rate_arg = DeclareLaunchArgument(
        'autorepeat_rate',
        default_value='20.0',
        description=(
            'joy_node-Rate in Hz für Auto-Repeat-Pubs während Stick '
            'gehalten wird. 20 Hz reicht für unsere 50-Hz-Engine.'
        ),
    )

    # Block I Phase 2: Wer ist die /joy-Quelle?
    #   controller (Default, unverändert) = joy_node (PS4-USB) + joy_to_twist.
    #   app = NUR joy_to_twist; /joy kommt von der Android-App über rosbridge.
    # NF7: immer genau EINE Quelle (kein Doppel-Publisher).
    joy_source_arg = DeclareLaunchArgument(
        'joy_source',
        default_value='controller',
        description=(
            'controller = joy_node (PS4-USB) + joy_to_twist (unverändert). '
            'app = nur joy_to_twist; die App publisht /joy über rosbridge '
            '(kein joy_node). NF7: genau eine /joy-Quelle.'
        ),
    )

    # In der Sim braucht joy_to_twist /clock (Long-Press-Timing). Bei echtem
    # USB-Controller ohne Sim = false (Wall-Clock). app_teleop.launch.py setzt true.
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description=(
            'true in der Sim (joy_to_twist gegen /clock), false bei echtem '
            'USB-Controller. Vom Komfort-Launch app_teleop auf true gesetzt.'
        ),
    )

    config_path = PathJoinSubstitution([
        FindPackageShare('hexapod_teleop'),
        'config',
        [LaunchConfiguration('controller'), '.yaml'],
    ])

    # joy_node nur im controller-Modus (im app-Modus ist die App die Quelle).
    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        output='screen',
        parameters=[{
            'device_id': LaunchConfiguration('joy_device_id'),
            'autorepeat_rate': LaunchConfiguration('autorepeat_rate'),
            'deadzone': 0.05,
        }],
        condition=IfCondition(PythonExpression([
            "'", LaunchConfiguration('joy_source'), "' == 'controller'",
        ])),
    )

    joy_to_twist_node = Node(
        package='hexapod_teleop',
        executable='joy_to_twist',
        name='joy_to_twist',
        output='screen',
        emulate_tty=True,
        parameters=[
            config_path,
            {'use_sim_time': ParameterValue(
                LaunchConfiguration('use_sim_time'), value_type=bool)},
        ],
    )

    return LaunchDescription([
        controller_arg,
        joy_device_id_arg,
        autorepeat_rate_arg,
        joy_source_arg,
        use_sim_time_arg,
        joy_node,
        joy_to_twist_node,
    ])
