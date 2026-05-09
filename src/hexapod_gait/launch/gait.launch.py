"""
Launch-File für gait_node — Single-Leg-Schwung in der Luft (Stufe E).

Aufruf:
- ``ros2 launch hexapod_gait gait.launch.py`` (Defaults: leg 1, sin 50 Hz)
- ``ros2 launch hexapod_gait gait.launch.py which_leg:=3 step_height:=0.03``
- ``ros2 launch hexapod_gait gait.launch.py cycle_time:=2.0`` (langsamer)

Voraussetzung: Sim läuft mit aktiven JTCs (Phase-4-Bringup), Roboter
sollte vorab in Stand-Pose stehen (z. B. via stand.launch.py), damit
die 5 Stütz-Beine den Roboter tragen.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    which_leg_arg = DeclareLaunchArgument(
        'which_leg',
        default_value='1',
        description='Bein-ID 1..6, das schwingt. Default 1 (vorne rechts).',
    )

    step_height_arg = DeclareLaunchArgument(
        'step_height',
        default_value='0.05',
        description='Schwung-Höhe in m über Stand-Pose. Default 0.05 (5 cm, gut sichtbar).',
    )

    cycle_time_arg = DeclareLaunchArgument(
        'cycle_time',
        default_value='1.0',
        description='Periode in s pro Schwung-Zyklus. Default 1.0.',
    )

    tick_rate_arg = DeclareLaunchArgument(
        'tick_rate',
        default_value='50.0',
        description='Knoten-Loop-Rate in Hz. Default 50.',
    )

    body_height_arg = DeclareLaunchArgument(
        'body_height',
        default_value='-0.047',
        description=(
            'Stand-Pose Foot-Z im Bein-Frame (m). Default -0.047 = '
            'Phase-4-Stand-Pose (Stufe-C-konsistent).'
        ),
    )

    radial_distance_arg = DeclareLaunchArgument(
        'radial_distance',
        default_value='0.27',
        description='Stand-Pose Foot-X im Bein-Frame (m). Default 0.27.',
    )

    tfs_factor_arg = DeclareLaunchArgument(
        'time_from_start_factor',
        default_value='2.0',
        description=(
            'time_from_start = factor / tick_rate. Default 2.0 = '
            '0.04 s Lookahead bei 50 Hz Tick.'
        ),
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Sim-Time aus /clock verwenden.',
    )

    gait_node = Node(
        package='hexapod_gait',
        executable='gait_node',
        name='gait_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'which_leg': LaunchConfiguration('which_leg'),
            'step_height': LaunchConfiguration('step_height'),
            'cycle_time': LaunchConfiguration('cycle_time'),
            'tick_rate': LaunchConfiguration('tick_rate'),
            'body_height': LaunchConfiguration('body_height'),
            'radial_distance': LaunchConfiguration('radial_distance'),
            'time_from_start_factor': LaunchConfiguration(
                'time_from_start_factor'
            ),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    return LaunchDescription([
        which_leg_arg,
        step_height_arg,
        cycle_time_arg,
        tick_rate_arg,
        body_height_arg,
        radial_distance_arg,
        tfs_factor_arg,
        use_sim_time_arg,
        gait_node,
    ])
