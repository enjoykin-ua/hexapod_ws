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
Block A5 Stufe 4 / S4-6 — Graben-Welt-Bringup (klare Demo des adaptiven Touchdowns).

Wrapper um ``sim.launch.py``: expandiert ``hexapod_gazebo/worlds/trench.sdf.xacro``
(zwei Plattformen Oberkante z=0 + Lücke = Graben, Boden bei −``trench_depth``) und
spawnt den Roboter **flach auf der Nah-Plattform** (z=0). Er läuft per ``cmd_vel``
(+x) über den Graben; die 4 Beine auf den Plattformen halten den Körper eben, nur
das Bein über dem Graben reicht nach unten → der per-Fuß-Reach wird isoliert sichtbar.

Beispiel:
    ros2 launch hexapod_bringup trench.launch.py trench_depth:=0.02 trench_width:=0.10
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
    """Trench-Welt-xacro expandieren → Tempfile → sim.launch.py (flach auf z=0)."""
    trench_width = LaunchConfiguration('trench_width').perform(context)
    trench_depth = LaunchConfiguration('trench_depth').perform(context)
    trench_x = LaunchConfiguration('trench_x').perform(context)
    spawn_x = LaunchConfiguration('spawn_x').perform(context)
    spawn_clearance = float(LaunchConfiguration('spawn_clearance').perform(context))

    # Start-Fläche = Nah-Plattform-Oberkante (z=0) → spawn_z = clearance.
    spawn_z = spawn_clearance

    gazebo_share = get_package_share_directory('hexapod_gazebo')
    world_xacro = os.path.join(gazebo_share, 'worlds', 'trench.sdf.xacro')
    doc = xacro.process_file(
        world_xacro,
        mappings={
            'trench_width': trench_width,
            'trench_depth': trench_depth,
            'trench_x': trench_x,
        },
    )
    out_path = os.path.join(
        tempfile.gettempdir(),
        f'hexapod_trench_{trench_width}_{trench_depth}_{trench_x}.sdf',
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
            'trench_width',
            default_value='0.10',
            description=(
                'x-Breite der Graben-Lücke in m (~ein Fuß). Schmal genug, dass die '
                'Stütz-Beine den Körper eben halten (kein Pitch-„Cheat" wie bei der '
                'Vollbreit-Stufe). Zu breit → Körper kippt; zu schmal → kein Bein trifft.'
            ),
        ),
        DeclareLaunchArgument(
            'trench_depth',
            default_value='0.02',
            description=(
                'Graben-Tiefe unter der Plattform in m. ≤ touchdown_max_extra_depth '
                '(0.02) damit der Fuß den Grabenboden erreicht; größer = Bein hängt.'
            ),
        ),
        DeclareLaunchArgument(
            'trench_x',
            default_value='0.0',
            description='x-Mitte des Grabens (m). Roboter spawnt bei spawn_x davor.',
        ),
        DeclareLaunchArgument(
            'spawn_x',
            default_value='-0.7',
            description='Spawn-X (m) auf der Nah-Plattform (vor dem Graben).',
        ),
        DeclareLaunchArgument(
            'spawn_clearance',
            default_value='0.06',
            description='Spawn-Höhe über der Nah-Plattform (Oberkante z=0), m.',
        ),
        OpaqueFunction(function=_expand_and_include),
    ])
