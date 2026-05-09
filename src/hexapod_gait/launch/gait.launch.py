"""
Launch-File für gait_node — daten-getriebene Gangart-Engine (Stufe F).

Aufruf:
- ``ros2 launch hexapod_gait gait.launch.py``
  (Defaults: pattern=tripod, enable_walk=false → STANDING)
- ``ros2 launch hexapod_gait gait.launch.py enable_walk:=true``
  (Tripod startet sofort)
- ``ros2 launch hexapod_gait gait.launch.py gait_pattern:=single_leg_1
  enable_walk:=true``
  (Stufe-E-Backward-Compat: Bein 1 schwingt einzeln)

Live-Toggle ohne Restart:
- ``ros2 param set /gait_node enable_walk true``  (STANDING → WALKING)
- ``ros2 param set /gait_node enable_walk false`` (WALKING → STANDING)

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

    enable_walk_arg = DeclareLaunchArgument(
        'enable_walk',
        default_value='false',
        description=(
            'STANDING (false) ↔ WALKING (true). Live-toggelbar via '
            '`ros2 param set /gait_node enable_walk <bool>`.'
        ),
    )

    step_height_arg = DeclareLaunchArgument(
        'step_height',
        default_value='0.03',
        description=(
            'Schwung-Höhe in m über Stand-Pose. Default 0.03 (3 cm, '
            'klein genug dass Stütz-Tripod den Roboter trägt).'
        ),
    )

    cycle_time_arg = DeclareLaunchArgument(
        'cycle_time',
        default_value='2.0',
        description=(
            'Periode in s pro Cycle. Default 2.0 (1 s Swing + 1 s '
            'Stance bei Tripod) — gut sichtbar, JTC-konvergiert.'
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
            '(Stufe-F-Design-Entscheidung 1: löst JTC-Tracking-Lag '
            'bei Tripod 3:3 ohne Hebel-Trick).'
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
            'gait_pattern': LaunchConfiguration('gait_pattern'),
            'enable_walk': LaunchConfiguration('enable_walk'),
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
        gait_pattern_arg,
        enable_walk_arg,
        step_height_arg,
        cycle_time_arg,
        tick_rate_arg,
        body_height_arg,
        radial_distance_arg,
        tfs_factor_arg,
        use_sim_time_arg,
        gait_node,
    ])
