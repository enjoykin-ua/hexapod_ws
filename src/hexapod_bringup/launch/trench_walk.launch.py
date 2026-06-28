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
Block A5 Stufe 4 / S4-6 — Ein-Befehl-Bringup für die Graben-Welt (klare Demo).

Startet in **einem** Aufruf: Gazebo + Graben-Welt + Spawn (flach auf der Nah-
Plattform) **und** — nach ``gait_delay`` s — den ``gait_node`` mit Auto-Standup.
Danach läufst du per ``cmd_vel`` (+x) über den Graben.

Für die S4-2-Demo ist ``leveling_enable`` per Default **false** (Stage 4 isoliert);
``adaptive_touchdown_enable`` live setzen.

Beispiele:
    ros2 launch hexapod_bringup trench_walk.launch.py                    # 2 cm tief, 10 cm breit
    ros2 launch hexapod_bringup trench_walk.launch.py trench_depth:=0.025
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def _delayed_gait(context, *args, **kwargs):
    """gait.launch.py nach ``gait_delay`` s einbinden (Controller erst hoch)."""
    delay = float(LaunchConfiguration('gait_delay').perform(context))

    gait_launch = os.path.join(
        get_package_share_directory('hexapod_gait'), 'launch', 'gait.launch.py',
    )
    urdf = os.path.join(
        get_package_share_directory('hexapod_description'),
        'urdf', 'hexapod.urdf.xacro',
    )

    gait_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gait_launch),
        launch_arguments={
            'use_sim_time': 'true',
            'robot_description_file': urdf,
            'leveling_enable': LaunchConfiguration('leveling_enable').perform(
                context),
            'gait_pattern': LaunchConfiguration('gait_pattern').perform(context),
        }.items(),
    )
    return [TimerAction(period=delay, actions=[gait_include])]


def generate_launch_description() -> LaunchDescription:
    trench_launch = os.path.join(
        get_package_share_directory('hexapod_bringup'),
        'launch', 'trench.launch.py',
    )

    trench_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(trench_launch),
        launch_arguments={
            'trench_width': LaunchConfiguration('trench_width'),
            'trench_depth': LaunchConfiguration('trench_depth'),
            'trench_x': LaunchConfiguration('trench_x'),
            'spawn_x': LaunchConfiguration('spawn_x'),
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'trench_width', default_value='0.10',
            description='x-Breite des Grabens (m). Schmal genug für Pitch-freien per-Fuß-Reach.',
        ),
        DeclareLaunchArgument(
            'trench_depth', default_value='0.02',
            description='Graben-Tiefe (m). ≤ touchdown_max_extra_depth (0.02).',
        ),
        DeclareLaunchArgument(
            'trench_x', default_value='0.0',
            description='x-Mitte des Grabens (m).',
        ),
        DeclareLaunchArgument(
            'spawn_x', default_value='-0.7',
            description='Spawn-X (m) auf der Nah-Plattform.',
        ),
        DeclareLaunchArgument(
            'gait_pattern', default_value='tripod',
            description='Gangart-Preset: tripod | wave | tetrapod | ripple.',
        ),
        DeclareLaunchArgument(
            'leveling_enable', default_value='false',
            description=(
                'Body-Stabilisierung (TF). Default false → Stage 4 (adaptiver '
                'Touchdown) isoliert. true = mit terrain-Leveling.'
            ),
        ),
        DeclareLaunchArgument(
            'gait_delay', default_value='12.0',
            description='Wartezeit (s) vor gait_node-Start (Gazebo+Spawn+Controller hoch).',
        ),
        trench_include,
        OpaqueFunction(function=_delayed_gait),
    ])
