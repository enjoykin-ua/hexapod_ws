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
Block I Phase 3 — On-Demand-Stack (von der App über den Launcher gestartet).

Das ist der **schwere** Stack, den ``bringup_launcher`` (hexapod_supervisor) auf
``/hexapod_bringup_start`` als Subprozess startet. **Ohne rosbridge** — die läuft
in der Always-On-Schicht (``always_on.launch.py``). Startet in EINEM Prozessbaum:

  mode:=sim  (Desktop):  ramp_walk.launch.py (flach, slope_deg:=0) + joy_to_twist(app)
  mode:=real (Pi):       real.launch.py (with_supervisor:=false) + gait + joy_to_twist(app)

**Bauch-Start:** in beiden Modi ``auto_standup_on_start:=false`` → der Roboter kommt
auf dem Bauch hoch (SAT) und steht erst per ``/hexapod_stand_up`` (App-Button) auf.

⚠️ ``mode:=real`` ist für den späteren Pi-Port (HW-Netz-Stage) vorbereitet, aber auf
echter HW noch **nicht** end-to-end getestet — Phase 3 verifiziert ``mode:=sim``.

Aufruf (i.d.R. über den Launcher, nicht direkt):
    ros2 launch hexapod_bringup bringup_ondemand.launch.py mode:=sim
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


def _setup(context, *args, **kwargs):
    """Mode-abhängig den passenden Stack zusammenstellen (sim | real)."""
    pkg_bringup = get_package_share_directory('hexapod_bringup')
    ramp_walk_launch = os.path.join(pkg_bringup, 'launch', 'ramp_walk.launch.py')
    rubicon_walk_launch = os.path.join(
        pkg_bringup, 'launch', 'rubicon_walk.launch.py')
    real_launch = os.path.join(pkg_bringup, 'launch', 'real.launch.py')
    gait_launch = os.path.join(
        get_package_share_directory('hexapod_gait'), 'launch', 'gait.launch.py')
    teleop_launch = os.path.join(
        get_package_share_directory('hexapod_teleop'),
        'launch', 'joy_teleop.launch.py')
    hw_urdf = os.path.join(
        get_package_share_directory('hexapod_description'),
        'urdf', 'hexapod.urdf.xacro')

    mode = LaunchConfiguration('mode').perform(context)
    controller = LaunchConfiguration('controller').perform(context)
    gait_delay = float(LaunchConfiguration('gait_delay').perform(context))
    scene = LaunchConfiguration('scene').perform(context)

    if mode == 'sim':
        # Scene wählt die Sim-Welt (Default flache Rampe). rubicon = Rauhterrain
        # + Kamera + Terrain-Regelkreise scharf (rubicon_walk lädt das Preset).
        if scene == 'rubicon':
            walk = IncludeLaunchDescription(
                PythonLaunchDescriptionSource(rubicon_walk_launch),
                launch_arguments={
                    'auto_standup_on_start': 'false',
                    'gait_delay': str(gait_delay),
                }.items(),
            )
        elif scene in ('ramp', 'flat', ''):
            # ramp_walk bringt Gazebo + Spawn + gait (mit eigenem gait_delay-Timer).
            walk = IncludeLaunchDescription(
                PythonLaunchDescriptionSource(ramp_walk_launch),
                launch_arguments={
                    'slope_deg': '0.0',
                    'auto_standup_on_start': 'false',
                    'gait_delay': str(gait_delay),
                }.items(),
            )
        else:
            raise RuntimeError(
                f'bringup_ondemand: unbekannte scene {scene!r} (ramp|rubicon)')
        teleop = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(teleop_launch),
            launch_arguments={
                'joy_source': 'app',
                'controller': controller,
                'use_sim_time': 'true',
            }.items(),
        )
        return [walk, teleop]

    if mode == 'real':
        # HW-Control (ohne Supervisor — der lebt in der Always-On-Schicht).
        ctrl = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(real_launch),
            launch_arguments={'with_supervisor': 'false'}.items(),
        )
        # gait erst nach gait_delay (controller_manager + JTCs müssen erst hoch).
        gait = TimerAction(
            period=gait_delay,
            actions=[IncludeLaunchDescription(
                PythonLaunchDescriptionSource(gait_launch),
                launch_arguments={
                    'use_sim_time': 'false',
                    'auto_standup_on_start': 'false',
                    'robot_description_file': hw_urdf,
                    'audio_playback': 'true',   # Phase 7A — echter Speaker
                }.items(),
            )],
        )
        teleop = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(teleop_launch),
            launch_arguments={
                'joy_source': 'app',
                'controller': controller,
                'use_sim_time': 'false',
            }.items(),
        )
        return [ctrl, gait, teleop]

    raise RuntimeError(f'bringup_ondemand: unbekannter mode {mode!r} (sim|real)')


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription([
        DeclareLaunchArgument(
            'mode', default_value='sim',
            description='sim = Gazebo (Desktop) | real = HW-Stack (Pi).',
        ),
        DeclareLaunchArgument(
            'scene', default_value='ramp',
            description=(
                'Sim-Welt (nur mode:=sim): ramp = flache Rampe (Default) | '
                'rubicon = Rauhterrain + Kamera + Terrain-Regelkreise scharf.'
            ),
        ),
        DeclareLaunchArgument(
            'controller', default_value='ps4_usb',
            description='Controller-Profil (config/<name>.yaml) = /joy-Layout.',
        ),
        DeclareLaunchArgument(
            'gait_delay', default_value='12.0',
            description=(
                'Wartezeit (s) vor gait_node-Start (Sim + Real), bis Sim/'
                'Controller hochgekommen sind. Bei langsamem Kaltstart erhöhen.'
            ),
        ),
        OpaqueFunction(function=_setup),
    ])
