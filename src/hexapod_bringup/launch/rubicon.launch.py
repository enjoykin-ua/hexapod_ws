#!/usr/bin/env python3
"""
rubicon.launch.py — Hexapod in der Fuel-Outdoor-Welt "Rubicon" spawnen.

Wrapper um ``sim.launch.py``: lädt ``hexapod_gazebo/worlds/rubicon.sdf`` (die
Rubicon-Heightmap-Szene + unsere gz-System-Plugins) und spawnt den Roboter auf
der flachen "Tal"-Strecke (x≈3..7, y=0, Boden ~1.3 m). Danach läufst du per
``cmd_vel`` (+x) geradeaus durch das Tal.

Voraussetzung (einmalig, Fuel-Cache): ::

    gz fuel download -u "https://fuel.gazebosim.org/1.0/OpenRobotics/models/Rubicon"

Granular (wie gewünscht): Welt+Spawn hier, Aufstehen separat über
``hexapod_gait gait.launch.py``, dann ``cmd_vel``. ::

    # T1: Welt + Spawn (flaches Tal, +x-Blickrichtung)
    ros2 launch hexapod_bringup rubicon.launch.py
    # T2: Aufstehen
    ros2 launch hexapod_gait gait.launch.py
    # T3: geradeaus laufen
    ros2 topic pub -r 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'

Erstmal OHNE die IMU-Balance-Features (alle Default aus). Später per
``ros2 param set /gait_node ...`` (siehe general_commands_usability.md) zuschalten.

Spawn-Höhe (``spawn_z``) ist aus der Heightmap GESCHÄTZT — falls der Roboter
beim Start in den Boden sackt: ``spawn_z`` erhöhen; falls er aus großer Höhe
fällt/kippt: ``spawn_z`` senken. Tal-Bodenhöhen (gemessen): x=3→1.33, x=4→1.35,
x=5→1.33, x=6→1.26, x=7→1.29 m.
"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    bringup_share = get_package_share_directory('hexapod_bringup')
    sim_launch = os.path.join(bringup_share, 'launch', 'sim.launch.py')

    sim_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(sim_launch),
        launch_arguments={
            'world': 'rubicon.sdf',
            'enable_imu': LaunchConfiguration('enable_imu'),
            'enable_foot_contact': LaunchConfiguration('enable_foot_contact'),
            'spawn_x': LaunchConfiguration('spawn_x'),
            'spawn_z': LaunchConfiguration('spawn_z'),
            # Flach spawnen (IMU welt-referenziert) — Default in sim.launch.py.
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'spawn_x',
            default_value='3.0',
            description=(
                'Spawn-X (m): Anfang der flachen Tal-Strecke. Lauf +x bis ~x=7.5, '
                'danach steigt das Gelände wieder an.'
            ),
        ),
        DeclareLaunchArgument(
            'spawn_z',
            default_value='1.50',
            description=(
                'Spawn-Höhe (m). Tal-Boden ~1.33 m + Clearance. Bei Einsinken '
                'erhöhen, bei hartem Fall senken (Heightmap-Schätzung).'
            ),
        ),
        DeclareLaunchArgument(
            'enable_imu',
            default_value='true',
            description='gz-IMU-Sensor + Bridge + imu_monitor (für späteren IMU-Test).',
        ),
        DeclareLaunchArgument(
            'enable_foot_contact',
            default_value='true',
            description='Fußkontakt-Sensoren + Bridge + Publisher.',
        ),
        sim_include,
    ])
