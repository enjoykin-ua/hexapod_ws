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
Block I Phase 3 — Always-On-Schicht ([D7] Stufe 1).

Die Schicht, die **ab Boot** läuft (auf dem Pi via systemd, in Sim manuell) — bevor
die App verbindet. Startet:
  - ``rosbridge_websocket`` + ``rosapi`` (:9090)     — die App↔ROS-Naht (Phase 2)
  - ``shutdown_supervisor``                          — Block F (HW-Schalter → Shutdown)
  - ``bringup_launcher``                             — startet/stoppt den schweren Stack
                                                       on demand + guarded Pi-Shutdown

Der schwere Gait-/Sim-/HW-Stack wird NICHT hier gestartet, sondern **on demand** von
der App über ``/hexapod_bringup_start`` (sicherer Default, [D7]).

Aufruf:
    ros2 launch hexapod_bringup always_on.launch.py                 # mode:=sim (Desktop)
    ros2 launch hexapod_bringup always_on.launch.py mode:=real      # Pi

``mode`` wählt die Launcher-Config (``launcher.sim.yaml`` / ``launcher.real.yaml``,
hexapod_supervisor) und ``use_sim_time`` für rosbridge (sim=true / real=false).
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    """Always-On-Schicht mode-abhängig bauen (rosbridge + supervisor + launcher)."""
    mode = LaunchConfiguration('mode').perform(context)
    if mode not in ('sim', 'real'):
        raise RuntimeError(f'always_on: unbekannter mode {mode!r} (sim|real)')
    use_sim_time = 'true' if mode == 'sim' else 'false'

    pkg_bringup = get_package_share_directory('hexapod_bringup')
    pkg_supervisor = get_package_share_directory('hexapod_supervisor')
    rosbridge_launch = os.path.join(pkg_bringup, 'launch', 'rosbridge.launch.py')
    supervisor_launch = os.path.join(
        pkg_supervisor, 'launch', 'supervisor.launch.py')
    launcher_cfg = os.path.join(
        pkg_supervisor, 'config', f'launcher.{mode}.yaml')

    rosbridge = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(rosbridge_launch),
        launch_arguments={'use_sim_time': use_sim_time}.items(),
    )
    supervisor = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(supervisor_launch),
    )
    launcher = Node(
        package='hexapod_supervisor',
        executable='bringup_launcher',
        name='bringup_launcher',
        output='screen',
        parameters=[launcher_cfg],
    )
    return [rosbridge, supervisor, launcher]


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'mode', default_value='sim',
            description='sim = Desktop/Gazebo | real = Raspberry Pi (HW).',
        ),
        OpaqueFunction(function=_setup),
    ])
