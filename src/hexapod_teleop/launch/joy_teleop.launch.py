"""
Launch-File für PS-Controller-Teleop (Stufe A, USB).

Startet ``joy_node`` (ros-jazzy-joy) und ``joy_to_twist`` mit der
gewünschten Controller-Konfiguration aus ``config/<controller>.yaml``.

Aufruf:
- ``ros2 launch hexapod_teleop joy_teleop.launch.py``
  (Default: PS4 via USB)
- ``ros2 launch hexapod_teleop joy_teleop.launch.py controller:=ps4_bt``
  (Stufe B, BT)

Voraussetzung: PS4-Controller per USB angeschlossen, ``/dev/input/js0``
vorhanden. Roboter sollte schon laufen (Sim + Stand + Gait), dieser
Knoten erzeugt nur ``/cmd_vel`` + ``/cmd_body_height``.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
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

    config_path = PathJoinSubstitution([
        FindPackageShare('hexapod_teleop'),
        'config',
        [LaunchConfiguration('controller'), '.yaml'],
    ])

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
    )

    joy_to_twist_node = Node(
        package='hexapod_teleop',
        executable='joy_to_twist',
        name='joy_to_twist',
        output='screen',
        emulate_tty=True,
        parameters=[config_path],
    )

    return LaunchDescription([
        controller_arg,
        joy_device_id_arg,
        autorepeat_rate_arg,
        joy_node,
        joy_to_twist_node,
    ])
