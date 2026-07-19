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
Block I Phase 7B — Kamera-Stream (echte Raspi-Cam am Pi).

Startet den ``hexapod_camera``-Node (OV5647 via ``rpicam-vid`` → CompressedImage
auf ``/camera/image_raw/compressed``) + den Stock-``web_video_server`` (:8080).
Vom real-Pfad (``bringup_ondemand mode:=real``) inkludiert (``source:=rpicam``);
für den Desktop-E2E direkt startbar mit ``source:=test`` (synthetisches JPEG).

Die App-Video-URL wählt den Stream-Typ je Host (Variante A, Contract §5):
  Sim  → http://<desktop>:8080/stream?topic=/camera/image_raw&type=mjpeg   (roh, Gazebo)
  HW   → http://<pi>:8080/stream?topic=/camera/image_raw&type=ros_compressed

Anmerkung: Im **Sim**-Pfad wird die Kamera weiterhin von ``sim.launch.py``
bedient (gz-Sensor + eigener ``web_video_server``) — dieses Launch ist NICHT für
Sim gedacht.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    enable_camera_arg = DeclareLaunchArgument(
        'enable_camera', default_value='true',
        description='Kamera-Node + web_video_server starten.',
    )
    source_arg = DeclareLaunchArgument(
        'source', default_value='rpicam',
        description='rpicam (Pi, OV5647) | test (Desktop, synthetisches JPEG).',
    )
    framerate_arg = DeclareLaunchArgument(
        'framerate', default_value='15.0',
        description='Bildrate (Hz).',
    )
    width_arg = DeclareLaunchArgument('width', default_value='1280')
    height_arg = DeclareLaunchArgument('height', default_value='720')
    port_arg = DeclareLaunchArgument(
        'port', default_value='8080',
        description='web_video_server-Port (MJPEG/ros_compressed).',
    )

    enabled = IfCondition(LaunchConfiguration('enable_camera'))

    camera_node = Node(
        package='hexapod_sensors',
        executable='hexapod_camera',
        name='hexapod_camera',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'source': LaunchConfiguration('source'),
            'framerate': LaunchConfiguration('framerate'),
            'width': LaunchConfiguration('width'),
            'height': LaunchConfiguration('height'),
        }],
        condition=enabled,
    )

    # Stock-Paket ros-jazzy-web-video-server: serviert /camera/image_raw als
    # MJPEG (raw) ODER ros_compressed (CompressedImage, JPEGs durchgereicht).
    web_video_server = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        output='screen',
        parameters=[{
            'port': LaunchConfiguration('port'),
            'address': '0.0.0.0',
        }],
        condition=enabled,
    )

    return LaunchDescription([
        enable_camera_arg,
        source_arg,
        framerate_arg,
        width_arg,
        height_arg,
        port_arg,
        camera_node,
        web_video_server,
    ])
