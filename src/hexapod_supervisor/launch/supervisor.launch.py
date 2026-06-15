"""
Launch the hexapod shutdown supervisor (Block F4/F5).

Loads config/supervisor.yaml as the single source of truth. The same config runs
everywhere; the host guard decides whether an OS shutdown actually fires. On the
dev host it only logs 'would shut down now'. On the Pi, set pi_hostname in the yaml
(F5b) — that is the only value to change.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Start the shutdown_supervisor node parameterised from supervisor.yaml."""
    config = os.path.join(
        get_package_share_directory('hexapod_supervisor'),
        'config', 'supervisor.yaml')

    return LaunchDescription([
        Node(
            package='hexapod_supervisor',
            executable='shutdown_supervisor',
            name='shutdown_supervisor',
            output='screen',
            parameters=[config],
        ),
    ])
