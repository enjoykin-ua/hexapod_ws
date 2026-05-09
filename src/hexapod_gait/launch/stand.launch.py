"""
Launch-File für stand_node — Hexapod in Stand-Pose fahren.

Aufruf:
- ``ros2 launch hexapod_gait stand.launch.py`` (Defaults)
- ``ros2 launch hexapod_gait stand.launch.py body_height:=-0.06`` (tiefer)
- ``ros2 launch hexapod_gait stand.launch.py transition_duration:=6.0``

Voraussetzung: Sim läuft mit aktiven JTCs (Phase-4-Bringup).
Vollständiger Test-Flow: ``docs/phase_5_stage_C_test_commands.md``.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    body_height_arg = DeclareLaunchArgument(
        'body_height',
        default_value='-0.052',
        description=(
            'Foot-Z im Bein-Frame (m). Default -0.052 = Phase-4-Stand '
            '-0.047 minus 5 mm globale Penetration (Stufe-F-Design-'
            'Entscheidung 1: löst JTC-Tracking-Lag bei Tripod 3:3 ohne '
            'Hebel-Trick). Konsistent mit gait.launch.py — sonst Body-'
            'Sprung beim ersten gait-Tick.'
        ),
    )

    radial_distance_arg = DeclareLaunchArgument(
        'radial_distance',
        default_value='0.27',
        description=(
            'Foot-X im Bein-Frame (m). Radiale Distanz vom coxa_joint '
            'zur Foot-Position. Default 0.27.'
        ),
    )

    transition_duration_arg = DeclareLaunchArgument(
        'transition_duration',
        default_value='4.0',
        description=(
            'time_from_start (s) der JointTrajectory. Sanftes Anfahren der '
            'Stand-Pose; Default 4.0 wie in Phase-4-Stufe-F erprobt.'
        ),
    )

    discovery_wait_arg = DeclareLaunchArgument(
        'discovery_wait',
        default_value='2.0',
        description=(
            'Sekunden DDS-Discovery-Settling, bevor publiziert wird. '
            'Wenn die JTC-Subscriber im local graph state nicht sichtbar '
            'sind (rclpy-Jazzy-Race), wird trotzdem publiziert (non-fatal '
            'warning).'
        ),
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Sim-Time aus /clock verwenden (für Phase-5-Sim).',
    )

    stand_node = Node(
        package='hexapod_gait',
        executable='stand_node',
        name='stand_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'body_height': LaunchConfiguration('body_height'),
            'radial_distance': LaunchConfiguration('radial_distance'),
            'transition_duration': LaunchConfiguration('transition_duration'),
            'discovery_wait': LaunchConfiguration('discovery_wait'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }],
    )

    return LaunchDescription([
        body_height_arg,
        radial_distance_arg,
        transition_duration_arg,
        discovery_wait_arg,
        use_sim_time_arg,
        stand_node,
    ])
