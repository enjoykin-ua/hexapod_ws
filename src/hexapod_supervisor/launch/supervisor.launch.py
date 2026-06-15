"""
Launch the hexapod shutdown supervisor (Block F4/F5).

OS shutdown is disabled by default (enable_os_shutdown=false) — the node only
logs 'would shut down now'. Block F5 wires the real Pi parameters/privileges.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Start the shutdown_supervisor node with overridable guard params."""
    enable_arg = DeclareLaunchArgument(
        'enable_os_shutdown', default_value='false',
        description='Master guard. false -> dry-run (log only). Arm on the Pi only.')
    pi_hostname_arg = DeclareLaunchArgument(
        'pi_hostname', default_value='',
        description='OS shutdown fires only when gethostname()==pi_hostname.')

    return LaunchDescription([
        enable_arg,
        pi_hostname_arg,
        Node(
            package='hexapod_supervisor',
            executable='shutdown_supervisor',
            name='shutdown_supervisor',
            output='screen',
            parameters=[{
                'enable_os_shutdown': LaunchConfiguration('enable_os_shutdown'),
                'pi_hostname': LaunchConfiguration('pi_hostname'),
            }],
        ),
    ])
