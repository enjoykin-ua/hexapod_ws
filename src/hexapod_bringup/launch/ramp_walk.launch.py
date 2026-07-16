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
Block A5 Terrain-Following — Ein-Befehl-Bringup (Komfort).

Startet in **einem** Aufruf: Gazebo + Ramp-Welt + Spawn (flach) **und** — nach
einer kurzen Verzögerung (Gazebo + Spawn + Controller müssen erst hochkommen) —
den ``gait_node``, der den Roboter automatisch aufstehen lässt (Auto-Standup).

Danach steht der Roboter; du gibst nur noch die Lauf-Befehle, z.B.:
    ros2 topic pub -r10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}}'

Ersetzt die bisherige Zwei-Terminal-Prozedur (ramp.launch.py + gait.launch.py).

Beispiele:
    ros2 launch hexapod_bringup ramp_walk.launch.py
    ros2 launch hexapod_bringup ramp_walk.launch.py slope_deg:=16.0 gait_pattern:=ripple
    ros2 launch hexapod_bringup ramp_walk.launch.py leveling_enable:=false   # passiv (TF-1)

Hinweis: ``gait_delay`` (Default 12 s) ist die Wartezeit, bevor der gait_node
startet. Wenn Gazebo auf deinem Rechner länger zum ersten Laden braucht (kalter
Start) und der Roboter „komisch" aufsteht, ``gait_delay`` erhöhen.
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
            'auto_standup_on_start': LaunchConfiguration(
                'auto_standup_on_start').perform(context),
        }.items(),
    )
    return [TimerAction(period=delay, actions=[gait_include])]


def generate_launch_description() -> LaunchDescription:
    ramp_launch = os.path.join(
        get_package_share_directory('hexapod_bringup'),
        'launch', 'ramp.launch.py',
    )

    ramp_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ramp_launch),
        launch_arguments={
            'slope_deg': LaunchConfiguration('slope_deg'),
            'spawn_x': LaunchConfiguration('spawn_x'),
            'spawn_z': LaunchConfiguration('spawn_z'),
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'slope_deg', default_value='8.0',
            description='Rampen-Steigung in Grad (Pitch um +Y).',
        ),
        DeclareLaunchArgument(
            'spawn_x', default_value='-0.7',
            description='Spawn-X (m) auf dem ebenen Anlauf (Rampe steigt ab x=0).',
        ),
        DeclareLaunchArgument(
            'spawn_z', default_value='0.06',
            description='Spawn-Höhe über dem Anlauf (m).',
        ),
        DeclareLaunchArgument(
            'gait_pattern', default_value='tripod',
            description='Gangart-Preset: tripod | wave | tetrapod | ripple.',
        ),
        DeclareLaunchArgument(
            'leveling_enable', default_value='true',
            description=(
                'Body-Stabilisierung (TF-2) beim Start an. true = terrain-Modus '
                '(roll→0, pitch folgt Hang, Gyro-Dämpfung). false = passiv (TF-1).'
            ),
        ),
        DeclareLaunchArgument(
            'gait_delay', default_value='12.0',
            description=(
                'Wartezeit (s) vor gait_node-Start, bis Gazebo + Spawn + '
                'Controller hochgekommen sind. Bei langsamem Kaltstart erhöhen.'
            ),
        ),
        DeclareLaunchArgument(
            'auto_standup_on_start', default_value='true',
            description=(
                'true (Default) = Auto-Standup wie bisher. false = Roboter '
                'bleibt auf dem Bauch (SAT), Aufstehen per /hexapod_stand_up '
                '(Block I Phase 3; bringup_ondemand setzt false).'
            ),
        ),
        ramp_include,
        OpaqueFunction(function=_delayed_gait),
    ])
