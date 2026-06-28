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
Block A5 Stufe 4 / S4-6 — Stufen-Welt-Bringup (Demo des adaptiven Touchdowns).

Wrapper um ``sim.launch.py``: expandiert ``hexapod_gazebo/worlds/step.sdf.xacro``
mit ``step_drop``/``step_x`` zur Laufzeit (Tempfile), startet die Sim und spawnt
den Roboter **flach auf der Start-Seite** (x < ``step_x``). Die Spawn-Höhe richtet
sich automatisch nach der Start-Fläche:
  - ``step_drop`` > 0 (Stufe AB): Start auf der oberen Box (z = step_drop) →
    spawn_z = step_drop + ``spawn_clearance``.
  - ``step_drop`` < 0 (Stufe AUF): Start auf dem ground_plane (z = 0) →
    spawn_z = ``spawn_clearance``.

Der Roboter läuft per ``cmd_vel`` (+x) über die Kante; bei Stufe AB reichen die
Vorderbeine mit aktivem adaptivem Touchdown (gait_node ``adaptive_touchdown_enable``)
über die Kante nach unten. Isoliert testen: ``leveling_enable:=false``.

Beispiel:
    ros2 launch hexapod_bringup step.launch.py step_drop:=0.02
    ros2 launch hexapod_bringup step.launch.py step_drop:=-0.02   # Stufe auf (Gegenprobe)
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
    """Step-Welt-xacro mit step_drop/step_x expandieren → Tempfile → sim.launch.py."""
    step_drop = LaunchConfiguration('step_drop').perform(context)
    step_x = LaunchConfiguration('step_x').perform(context)
    spawn_x = LaunchConfiguration('spawn_x').perform(context)
    spawn_clearance = float(LaunchConfiguration('spawn_clearance').perform(context))

    # Start-Fläche: obere Box (z=|step_drop|) bei Stufe AB, ground_plane (z=0) bei AUF.
    sd = float(step_drop)
    start_z = abs(sd) if sd >= 0.0 else 0.0
    spawn_z = start_z + spawn_clearance

    gazebo_share = get_package_share_directory('hexapod_gazebo')
    world_xacro = os.path.join(gazebo_share, 'worlds', 'step.sdf.xacro')
    doc = xacro.process_file(
        world_xacro, mappings={'step_drop': step_drop, 'step_x': step_x},
    )
    out_path = os.path.join(
        tempfile.gettempdir(), f'hexapod_step_{step_drop}_{step_x}.sdf',
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
                'spawn_z': f'{spawn_z:.4f}',
                'spawn_x': spawn_x,
                # Flach spawnen (IMU welt-referenziert) — Default in sim.launch.py.
            }.items(),
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'step_drop',
            default_value='0.02',
            description=(
                'Stufenhöhe in m, signiert: + = ab (Start oben, S4-2-Payoff), '
                '- = auf (Start unten, Gegenprobe). |step_drop| ≲ '
                'touchdown_max_extra_depth (0.02) damit der Fuß den unteren Boden '
                'beim Herabsteigen erreicht.'
            ),
        ),
        DeclareLaunchArgument(
            'step_x',
            default_value='0.0',
            description='x-Position der Kante (m). Roboter spawnt bei spawn_x < step_x.',
        ),
        DeclareLaunchArgument(
            'spawn_x',
            default_value='-0.7',
            description=(
                'Spawn-X (m) auf der Start-Seite (x < step_x). Kurzer Anlauf bis '
                'zur Kante, damit der Roboter nicht ewig läuft.'
            ),
        ),
        DeclareLaunchArgument(
            'spawn_clearance',
            default_value='0.06',
            description=(
                'Spawn-Höhe über der Start-Fläche (m). spawn_z wird automatisch = '
                'Start-Flächen-z + spawn_clearance (Start-Fläche = obere Box bei '
                'Stufe ab, ground_plane bei Stufe auf).'
            ),
        ),
        OpaqueFunction(function=_expand_and_include),
    ])
