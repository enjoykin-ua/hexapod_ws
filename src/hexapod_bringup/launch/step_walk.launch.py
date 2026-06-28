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
Block A5 Stufe 4 / S4-6 — Ein-Befehl-Bringup für die Stufen-Welt (Komfort).

Startet in **einem** Aufruf: Gazebo + Stufen-Welt + Spawn (flach) **und** — nach
``gait_delay`` s — den ``gait_node`` mit Auto-Standup. Danach steht der Roboter;
du gibst nur die Lauf-Befehle, z.B.:
    ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.04}}'

Für die S4-2-Demo (adaptiver Touchdown) ist ``leveling_enable`` per Default
**false** (Stage 4 isoliert von IMU/TF); ``adaptive_touchdown_enable`` live setzen.

Beispiele:
    ros2 launch hexapod_bringup step_walk.launch.py                  # Stufe 2 cm ab
    ros2 launch hexapod_bringup step_walk.launch.py step_drop:=0.04  # Grenze (fixed-timing)
    ros2 launch hexapod_bringup step_walk.launch.py step_drop:=-0.02 # Stufe auf (Gegenprobe)
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
    step_launch = os.path.join(
        get_package_share_directory('hexapod_bringup'),
        'launch', 'step.launch.py',
    )

    step_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(step_launch),
        launch_arguments={
            'step_drop': LaunchConfiguration('step_drop'),
            'step_x': LaunchConfiguration('step_x'),
            'spawn_x': LaunchConfiguration('spawn_x'),
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'step_drop', default_value='0.02',
            description=(
                'Stufenhöhe in m, signiert: + = ab (S4-2-Payoff), - = auf '
                '(Gegenprobe). 0.02 ≈ Reach-Grenze, 0.04 zeigt die fixed-timing-Grenze.'
            ),
        ),
        DeclareLaunchArgument(
            'step_x', default_value='0.0',
            description='x-Position der Kante (m).',
        ),
        DeclareLaunchArgument(
            'spawn_x', default_value='-0.7',
            description='Spawn-X (m) auf der Start-Seite (x < step_x).',
        ),
        DeclareLaunchArgument(
            'gait_pattern', default_value='tripod',
            description='Gangart-Preset: tripod | wave | tetrapod | ripple.',
        ),
        DeclareLaunchArgument(
            'leveling_enable', default_value='false',
            description=(
                'Body-Stabilisierung (TF). Default false → Stage 4 (adaptiver '
                'Touchdown) isoliert von IMU/TF. true = mit terrain-Leveling.'
            ),
        ),
        DeclareLaunchArgument(
            'gait_delay', default_value='12.0',
            description=(
                'Wartezeit (s) vor gait_node-Start, bis Gazebo + Spawn + '
                'Controller hochgekommen sind. Bei langsamem Kaltstart erhöhen.'
            ),
        ),
        step_include,
        OpaqueFunction(function=_delayed_gait),
    ])
