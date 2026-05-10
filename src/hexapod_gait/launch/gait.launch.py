"""
Launch-File für gait_node — cmd_vel-getriebener Walk (Stufe G).

Aufruf:
- ``ros2 launch hexapod_gait gait.launch.py``
  (Defaults: pattern=tripod, default_linear_x=0 → STANDING bis cmd_vel)
- ``ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05``
  (Demo-Mode: Roboter läuft sofort vorwärts ohne externe cmd_vel)
- ``ros2 launch hexapod_gait gait.launch.py cycle_time:=1.0``
  (DK-3-Test mit schnellerem Cycle für <0.5 s Stopp-Latenz)

Walk via cmd_vel:
- ``ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist
  '{linear: {x: 0.05}}'``  (vorwärts mit 5 cm/s)
- ``ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{}'``
  (linear.x = 0 → STANDING-Trigger)

Voraussetzung: Sim läuft mit aktiven JTCs (Phase-4-Bringup), Roboter
sollte vorab in Stand-Pose stehen (z. B. via stand.launch.py mit
gleichem ``body_height``-Default), damit es keinen Body-Sprung beim
ersten WALKING-Tick gibt.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    gait_pattern_arg = DeclareLaunchArgument(
        'gait_pattern',
        default_value='tripod',
        description=(
            'Gangart-Preset-Name aus GAIT_PRESETS. Aktuell verfügbar: '
            'tripod, single_leg_1..single_leg_6.'
        ),
    )

    step_height_arg = DeclareLaunchArgument(
        'step_height',
        default_value='0.03',
        description=(
            'Schwung-Höhe in m über Stand-Pose. Default 0.03 (3 cm).'
        ),
    )

    cycle_time_arg = DeclareLaunchArgument(
        'cycle_time',
        default_value='2.0',
        description=(
            'Periode in s pro Cycle. Default 2.0 (1 s Swing + 1 s '
            'Stance bei Tripod). Für DK-3-Test (Stopp-Latenz <0.5 s) '
            'auf 1.0 setzen.'
        ),
    )

    tick_rate_arg = DeclareLaunchArgument(
        'tick_rate',
        default_value='50.0',
        description='Knoten-Loop-Rate in Hz. Default 50.',
    )

    body_height_arg = DeclareLaunchArgument(
        'body_height',
        default_value='-0.052',
        description=(
            'Stand-Pose Foot-Z im Bein-Frame (m). Default -0.052 = '
            'Phase-4-Stand -0.047 minus 5 mm globale Penetration '
            '(Stufe-F-Design-Entscheidung 1).'
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

    step_length_max_arg = DeclareLaunchArgument(
        'step_length_max',
        default_value='0.05',
        description=(
            'Obere Schranke für Schritt-Länge in m. Aus '
            'step_length_max + cycle_time leitet Engine den maximalen '
            'cmd_vel.linear.x ab: linear_max = step_length_max / '
            'stance_duration. Default 0.05 m → linear_max = 0.05 m/s '
            'bei cycle_time=2 (DK-2-tauglich).'
        ),
    )

    default_linear_x_arg = DeclareLaunchArgument(
        'default_linear_x',
        default_value='0.0',
        description=(
            'Fallback-Vorwärtsgeschwindigkeit (m/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0 → STANDING. '
            'Beispiel: 0.05 → Roboter läuft sofort vorwärts in Demo-Mode.'
        ),
    )

    default_linear_y_arg = DeclareLaunchArgument(
        'default_linear_y',
        default_value='0.0',
        description=(
            'Fallback-Seitwärtsgeschwindigkeit (m/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0. Beispiel: '
            '0.04 → Roboter läuft seitwärts in Demo-Mode.'
        ),
    )

    default_angular_z_arg = DeclareLaunchArgument(
        'default_angular_z',
        default_value='0.0',
        description=(
            'Fallback-Drehgeschwindigkeit (rad/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0. Positiv = '
            'gegen Uhrzeigersinn (Standard ROS-Konvention für '
            'Z-Rotation um base_link).'
        ),
    )

    cmd_vel_timeout_arg = DeclareLaunchArgument(
        'cmd_vel_timeout',
        default_value='0.5',
        description=(
            'Activity-Timeout in s. Wenn länger als das keine cmd_vel '
            'ankommt, fällt Engine auf default_linear_x zurück. '
            'Default 0.5 s aus Phase-5-Roadmap.'
        ),
    )

    body_height_min_arg = DeclareLaunchArgument(
        'body_height_min',
        default_value='-0.080',
        description=(
            'Untere Schranke für body_height (m, Bein-Frame Z). '
            'Für /cmd_body_height-Subscriber (Phase 6). Default -0.080 '
            'm = 28 mm tiefer als Default Stand-Pose.'
        ),
    )

    body_height_max_arg = DeclareLaunchArgument(
        'body_height_max',
        default_value='-0.030',
        description=(
            'Obere Schranke für body_height (m, Bein-Frame Z). '
            'Für /cmd_body_height-Subscriber (Phase 6). Default -0.030 '
            'm = 22 mm höher als Default Stand-Pose.'
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
            'gait_pattern': LaunchConfiguration('gait_pattern'),
            'step_height': LaunchConfiguration('step_height'),
            'cycle_time': LaunchConfiguration('cycle_time'),
            'tick_rate': LaunchConfiguration('tick_rate'),
            'body_height': LaunchConfiguration('body_height'),
            'radial_distance': LaunchConfiguration('radial_distance'),
            'time_from_start_factor': LaunchConfiguration(
                'time_from_start_factor'
            ),
            'step_length_max': LaunchConfiguration('step_length_max'),
            'default_linear_x': LaunchConfiguration('default_linear_x'),
            'default_linear_y': LaunchConfiguration('default_linear_y'),
            'default_angular_z': LaunchConfiguration('default_angular_z'),
            'cmd_vel_timeout': LaunchConfiguration('cmd_vel_timeout'),
            'body_height_min': LaunchConfiguration('body_height_min'),
            'body_height_max': LaunchConfiguration('body_height_max'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    return LaunchDescription([
        gait_pattern_arg,
        step_height_arg,
        cycle_time_arg,
        tick_rate_arg,
        body_height_arg,
        radial_distance_arg,
        tfs_factor_arg,
        step_length_max_arg,
        default_linear_x_arg,
        default_linear_y_arg,
        default_angular_z_arg,
        cmd_vel_timeout_arg,
        body_height_min_arg,
        body_height_max_arg,
        use_sim_time_arg,
        gait_node,
    ])
