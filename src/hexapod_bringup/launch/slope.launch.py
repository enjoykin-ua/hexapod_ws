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
Block A5 Stufe 2 — Schräg-Welt-Bringup (statisches Körper-Leveling).

Wrapper um ``sim.launch.py``: expandiert ``hexapod_gazebo/worlds/slope.sdf.xacro``
mit dem ``slope_deg``-Arg zur Laufzeit in ein konkretes SDF (Tempfile), startet
damit die normale Sim (gz + Controller + IMU-Bridge/-Monitor) und spawnt den
Roboter **flach** (welt-ausgerichtet). Der Roboter steht über den Auto-Standup auf
und neigt sich dabei auf die Hangfläche; der gz-IMU-Sensor (spawn-referenziert)
liest so den echten Hangwinkel. Auf der Schräge auf-/hineinlaufen = Stufe 3.

Das Leveling selbst sitzt im gait_node (Param ``leveling_enable:=true``) und wird
über die separate ``hexapod_gait gait.launch.py`` gestartet — siehe
``stage_2_static_leveling_test_commands.md``.

Beispiel:
    ros2 launch hexapod_bringup slope.launch.py slope_deg:=8.0
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
    """Schräg-Welt-xacro mit slope_deg expandieren → Tempfile → sim.launch.py."""
    slope_deg = LaunchConfiguration('slope_deg').perform(context)
    spawn_z = LaunchConfiguration('spawn_z').perform(context)
    # Default: FLACH spawnen (welt-ausgerichtet). Wichtig: der gz-IMU-Sensor
    # referenziert seine Orientierung auf die Spawn-Pose — ein gepitchter Spawn
    # legt die IMU-Null auf den Hangwinkel und maskiert die reale Neigung
    # (verifiziert 2026-06). Flacher Spawn = IMU welt-referenziert (liest den
    # echten Hangwinkel); entspricht auch dem realen Szenario (Roboter startet
    # auf ebenem Boden, läuft in den Hang). Überschreibbar via spawn_pitch_deg.
    spawn_pitch_deg = LaunchConfiguration('spawn_pitch_deg').perform(context)
    if not spawn_pitch_deg:
        spawn_pitch_deg = '0.0'

    gazebo_share = get_package_share_directory('hexapod_gazebo')
    world_xacro = os.path.join(gazebo_share, 'worlds', 'slope.sdf.xacro')
    doc = xacro.process_file(world_xacro, mappings={'slope_deg': slope_deg})
    out_path = os.path.join(
        tempfile.gettempdir(), f'hexapod_slope_{slope_deg}.sdf',
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
                # Body bei Kontakt parallel zur um +Y geneigten Box.
                'spawn_pitch_deg': spawn_pitch_deg,
            }.items(),
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'slope_deg',
            default_value='8.0',
            description=(
                'Hangwinkel der geneigten Box in Grad (Pitch um +Y). Stufe-2-'
                'Test-Regime mild (5/8/10°, ≤ tip_warn). Default 8.0.'
            ),
        ),
        DeclareLaunchArgument(
            'spawn_z',
            default_value='0.08',
            description=(
                'Spawn-Höhe über dem Box-Ursprung (m). Etwas höher als flach '
                '(empty_imu), da die geneigte Box-Oberseite am Ursprung liegt.'
            ),
        ),
        DeclareLaunchArgument(
            'spawn_pitch_deg',
            default_value='',
            description=(
                'Spawn-Pitch (Grad). Leer = 0 (FLACH, welt-ausgerichtet). '
                'Grund: der gz-IMU-Sensor ist spawn-referenziert — ein '
                'gepitchter Spawn maskiert die reale Hang-Neigung. Flach lassen, '
                'außer du weißt was du tust.'
            ),
        ),
        OpaqueFunction(function=_expand_and_include),
    ])
