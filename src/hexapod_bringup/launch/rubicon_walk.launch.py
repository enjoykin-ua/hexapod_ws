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
Block I — Rubicon-Ein-Befehl-Bringup (Terrain-Scene für den App-Flow).

Spiegelt ``ramp_walk.launch.py``, aber für die **Rubicon-Rauhterrain-Welt**:
inkludiert ``rubicon.launch.py`` (Sim + Rubicon-Welt + heightmap-Spawn) **und** —
nach ``gait_delay`` — den ``gait_node`` **mit dem Rubicon-Terrain-Preset**
(``config/presets/rubicon.yaml``: leveling + adaptiver Touchdown/Stand + Slip +
Sensor-Plausibilität ab Start scharf). Damit läuft der Roboter auf echtem
Gelände, ohne dass man erst in der App etwas einschalten muss.

Wird i.d.R. NICHT direkt gestartet, sondern über den On-Demand-Stack:
``always_on.launch.py scene:=rubicon`` → App-„Start" → ``bringup_ondemand
mode:=sim scene:=rubicon`` → hier. ``auto_standup_on_start:=false`` (Bauch-Start,
Aufstehen per App-Button) wird von ``bringup_ondemand`` gesetzt.

Standalone (ohne App, Auto-Standup):
    ros2 launch hexapod_bringup rubicon_walk.launch.py
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
    """gait.launch.py nach ``gait_delay`` s einbinden (mit Rubicon-Preset)."""
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
            'params_file': LaunchConfiguration('params_file').perform(context),
            'gait_pattern': LaunchConfiguration('gait_pattern').perform(context),
            'auto_standup_on_start': LaunchConfiguration(
                'auto_standup_on_start').perform(context),
        }.items(),
    )
    return [TimerAction(period=delay, actions=[gait_include])]


def generate_launch_description() -> LaunchDescription:
    bringup_share = get_package_share_directory('hexapod_bringup')
    rubicon_launch = os.path.join(bringup_share, 'launch', 'rubicon.launch.py')
    default_preset = os.path.join(
        get_package_share_directory('hexapod_gait'),
        'config', 'presets', 'rubicon.yaml',
    )

    rubicon_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rubicon_launch),
        launch_arguments={
            'spawn_x': LaunchConfiguration('spawn_x'),
            'spawn_z': LaunchConfiguration('spawn_z'),
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'spawn_x', default_value='3.0',
            description='Spawn-X (m) auf der flachen Tal-Strecke (rubicon.launch.py).',
        ),
        DeclareLaunchArgument(
            'spawn_z', default_value='1.50',
            description='Spawn-Höhe (m) über dem Rubicon-Tal (Heightmap-Schätzung).',
        ),
        DeclareLaunchArgument(
            'gait_pattern', default_value='tripod',
            description='Gangart-Preset: tripod | wave | tetrapod | ripple.',
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
                'true (Default) = Auto-Standup. false = Bauch-Start (SAT), '
                'Aufstehen per /hexapod_stand_up (bringup_ondemand setzt false).'
            ),
        ),
        DeclareLaunchArgument(
            'params_file', default_value=default_preset,
            description=(
                'gait_node-Preset. Default = Rubicon-Terrain-Preset (Regelkreise '
                'scharf). params_file überschreibt die gait.launch.py-Inline-Defaults.'
            ),
        ),
        rubicon_include,
        OpaqueFunction(function=_delayed_gait),
    ])
