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
Block A5 Stufe 3a — Ramp-Welt-Bringup (Leveling im WALKING).

Wrapper um ``sim.launch.py``: expandiert ``hexapod_gazebo/worlds/ramp.sdf.xacro``
mit ``slope_deg`` zur Laufzeit (Tempfile), startet die Sim und spawnt den Roboter
**flach auf dem ebenen Anlauf** (``spawn_x`` negativ). Der Roboter läuft per
``cmd_vel`` (+x) in den Hang; das Leveling im WALKING (gait_node
``leveling_enable:=true``) hält den Körper Richtung horizontal.

Das Leveling sitzt im gait_node (separate ``hexapod_gait gait.launch.py``) — siehe
``stage_3a_leveling_walking_test_commands.md``.

Beispiel:
    ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0
"""

import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
import xacro


def _expand_and_include(context, *args, **kwargs):
    """Ramp-Welt-xacro mit slope_deg expandieren → Tempfile → sim.launch.py."""
    slope_deg = LaunchConfiguration('slope_deg').perform(context)
    spawn_z = LaunchConfiguration('spawn_z').perform(context)
    spawn_x = LaunchConfiguration('spawn_x').perform(context)

    gazebo_share = get_package_share_directory('hexapod_gazebo')
    world_xacro = os.path.join(gazebo_share, 'worlds', 'ramp.sdf.xacro')
    doc = xacro.process_file(world_xacro, mappings={'slope_deg': slope_deg})
    out_path = os.path.join(
        tempfile.gettempdir(), f'hexapod_ramp_{slope_deg}.sdf',
    )
    with open(out_path, 'w') as handle:
        handle.write(doc.toprettyxml(indent='  '))

    bringup_share = get_package_share_directory('hexapod_bringup')
    sim_launch = os.path.join(bringup_share, 'launch', 'sim.launch.py')
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(sim_launch),
            launch_arguments={
                'world': out_path,
                'enable_imu': 'true',
                'spawn_z': spawn_z,
                'spawn_x': spawn_x,
                # Flach spawnen (IMU welt-referenziert) — Default in sim.launch.py.
            }.items(),
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'slope_deg',
            default_value='8.0',
            description='Steigung der Rampe in Grad (Pitch um +Y). Test-Ladder 0/6/12/18/24/30.',
        ),
        DeclareLaunchArgument(
            'spawn_z',
            default_value='0.06',
            description='Spawn-Höhe über dem ebenen Anlauf (z=0), m.',
        ),
        DeclareLaunchArgument(
            'spawn_x',
            default_value='-0.7',
            description=(
                'Spawn-X (m) auf dem ebenen Anlauf. Rampe steigt ab x=0 → kurzer '
                'Anlauf (~0.7 m), damit der Roboter nicht ewig bis zur Steigung läuft.'
            ),
        ),
        OpaqueFunction(function=_expand_and_include),
    ])
