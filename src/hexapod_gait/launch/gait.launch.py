"""
Launch-File für gait_node — cmd_vel-getriebener Walk (Stufe G).

Aufruf:
- ``ros2 launch hexapod_gait gait.launch.py``
  (Defaults: pattern=tripod, default_linear_x=0 → STANDING bis cmd_vel)
- ``ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05``
  (Demo-Mode: Roboter läuft sofort vorwärts ohne externe cmd_vel)
- ``ros2 launch hexapod_gait gait.launch.py cycle_time:=1.0``
  (DK-3-Test mit schnellerem Cycle für <0.5 s Stopp-Latenz)

Walk via cmd_vel:
- ``ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist
  '{linear: {x: 0.05}}'``  (vorwärts mit 5 cm/s)
- ``ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{}'``
  (linear.x = 0 → STANDING-Trigger)

Voraussetzung: Sim läuft mit aktiven JTCs (Phase-4-Bringup), Roboter
sollte vorab in Stand-Pose stehen (z. B. via stand.launch.py mit
gleichem ``body_height``-Default), damit es keinen Body-Sprung beim
ersten WALKING-Tick gibt.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    gait_pattern_arg = DeclareLaunchArgument(
        'gait_pattern',
        default_value='tripod',
        description=(
            'Gangart-Preset-Name aus GAIT_PRESETS. Aktuell verfügbar: '
            'tripod, single_leg_1..single_leg_6.'
        ),
    )

    step_height_arg = DeclareLaunchArgument(
        'step_height',
        default_value='0.03',
        description=(
            'Schwung-Höhe in m über Stand-Pose. Default 0.03 (3 cm).'
        ),
    )

    cycle_time_arg = DeclareLaunchArgument(
        'cycle_time',
        default_value='2.0',
        description=(
            'Periode in s pro Cycle. Default 2.0 (1 s Swing + 1 s '
            'Stance bei Tripod). Für DK-3-Test (Stopp-Latenz <0.5 s) '
            'auf 1.0 setzen.'
        ),
    )

    tick_rate_arg = DeclareLaunchArgument(
        'tick_rate',
        default_value='50.0',
        description='Knoten-Loop-Rate in Hz. Default 50.',
    )

    body_height_arg = DeclareLaunchArgument(
        'body_height',
        default_value='-0.052',
        description=(
            'Stand-Pose Foot-Z im Bein-Frame (m). Default -0.052 = '
            'Phase-4-Stand -0.047 minus 5 mm globale Penetration '
            '(Stufe-F-Design-Entscheidung 1).'
        ),
    )

    radial_distance_arg = DeclareLaunchArgument(
        'radial_distance',
        default_value='0.27',
        description='Stand-Pose Foot-X im Bein-Frame (m). Default 0.27.',
    )

    tfs_factor_arg = DeclareLaunchArgument(
        'time_from_start_factor',
        default_value='2.0',
        description=(
            'time_from_start = factor / tick_rate. Default 2.0 = '
            '0.04 s Lookahead bei 50 Hz Tick.'
        ),
    )

    step_length_max_arg = DeclareLaunchArgument(
        'step_length_max',
        default_value='0.05',
        description=(
            'Obere Schranke für Schritt-Länge in m. Aus '
            'step_length_max + cycle_time leitet Engine den maximalen '
            'cmd_vel.linear.x ab: linear_max = step_length_max / '
            'stance_duration. Default 0.05 m → linear_max = 0.05 m/s '
            'bei cycle_time=2 (DK-2-tauglich).'
        ),
    )

    default_linear_x_arg = DeclareLaunchArgument(
        'default_linear_x',
        default_value='0.0',
        description=(
            'Fallback-Vorwärtsgeschwindigkeit (m/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0 → STANDING. '
            'Beispiel: 0.05 → Roboter läuft sofort vorwärts in Demo-Mode.'
        ),
    )

    default_linear_y_arg = DeclareLaunchArgument(
        'default_linear_y',
        default_value='0.0',
        description=(
            'Fallback-Seitwärtsgeschwindigkeit (m/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0. Beispiel: '
            '0.04 → Roboter läuft seitwärts in Demo-Mode.'
        ),
    )

    default_angular_z_arg = DeclareLaunchArgument(
        'default_angular_z',
        default_value='0.0',
        description=(
            'Fallback-Drehgeschwindigkeit (rad/s) wenn keine cmd_vel '
            'innerhalb cmd_vel_timeout ankommt. Default 0.0. Positiv = '
            'gegen Uhrzeigersinn (Standard ROS-Konvention für '
            'Z-Rotation um base_link).'
        ),
    )

    cmd_vel_timeout_arg = DeclareLaunchArgument(
        'cmd_vel_timeout',
        default_value='0.5',
        description=(
            'Activity-Timeout in s. Wenn länger als das keine cmd_vel '
            'ankommt, fällt Engine auf default_linear_x zurück. '
            'Default 0.5 s aus Phase-5-Roadmap.'
        ),
    )

    body_height_min_arg = DeclareLaunchArgument(
        'body_height_min',
        default_value='-0.080',
        description=(
            'Untere Schranke für body_height (m, Bein-Frame Z). '
            'Für /cmd_body_height-Subscriber (Phase 6). Default -0.080 '
            'm = 28 mm tiefer als Default Stand-Pose.'
        ),
    )

    body_height_max_arg = DeclareLaunchArgument(
        'body_height_max',
        default_value='-0.030',
        description=(
            'Obere Schranke für body_height (m, Bein-Frame Z). '
            'Für /cmd_body_height-Subscriber (Phase 6). Default -0.030 '
            'm = 22 mm höher als Default Stand-Pose.'
        ),
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Sim-Time aus /clock verwenden.',
    )

    # Phase 11 Stage D — Preset-File-Loader (D-Q1 Option A).
    # Optional: wenn nicht-leer, wird das YAML zusätzlich zur
    # Inline-Default-Parametersliste übergeben. ROS2 priorisiert
    # spätere Einträge → params_file überschreibt die Inline-Defaults.
    # Bei leerem params_file: nur Inline-Defaults wirken.
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value='',
        description=(
            'Optionales YAML-Preset-File mit gait_node-Parametern. '
            'Bei nicht-leer: überschreibt die individuellen Launch-Args. '
            'Beispiele liegen unter '
            'src/hexapod_gait/config/presets/. '
            'Erzeugung: ros2 param dump /gait_node --output-dir ... '
            '--filename <name>.'
        ),
    )

    # Stage 0.6 — URDF-File-Pfad für Joint-Limit-Parse. gait_node parsed
    # die per-Bein-Limits beim Start und übergibt sie an gait_engine. Bei
    # leerem Wert: gait_engine läuft lenient (= Phase-5-Verhalten). Im
    # sim.launch.py-Stack wird der Pfad aus hexapod_description-Share
    # genommen, manuelle Override z.B. für Tests via Launch-Argument.
    robot_description_file_arg = DeclareLaunchArgument(
        'robot_description_file',
        default_value='',
        description=(
            'Pfad zur xacro-File. Bei nicht-leer wird das xacro evaluiert '
            'und als robot_description-Param an gait_node übergeben, '
            'damit Stage-0.6-IK-joint-limit-Check aktiv ist. Leer = '
            'gait_engine läuft lenient.'
        ),
    )

    def setup_gait_node(context, *args, **kwargs):
        """
        Build Node-Aktion mit conditional params_file-Loading.

        Standard ROS2-Launch-Pattern: LaunchConfiguration kann nicht
        zur Plan-Zeit verglichen werden, daher OpaqueFunction die zur
        Launch-Zeit den Substitution-Wert evaluiert.
        """
        params_file = LaunchConfiguration('params_file').perform(context)

        # Stage 0.6 — robot_description aus xacro evaluieren wenn File-
        # Pfad gegeben. Empty string → gait_engine läuft lenient (=
        # Phase-5-Verhalten, kein joint-limit-Check).
        urdf_xml = ''
        urdf_file = LaunchConfiguration('robot_description_file').perform(context)
        if urdf_file:
            import subprocess
            try:
                urdf_xml = subprocess.check_output(
                    ['xacro', urdf_file], text=True)
            except subprocess.CalledProcessError as e:
                # Fail loud — leerer URDF wäre weniger sicher als crashen.
                raise RuntimeError(
                    f'xacro evaluation failed for {urdf_file}: {e}'
                ) from e

        inline_params = {
            'gait_pattern': LaunchConfiguration('gait_pattern').perform(context),
            'step_height': float(
                LaunchConfiguration('step_height').perform(context)),
            'cycle_time': float(
                LaunchConfiguration('cycle_time').perform(context)),
            'tick_rate': float(
                LaunchConfiguration('tick_rate').perform(context)),
            'body_height': float(
                LaunchConfiguration('body_height').perform(context)),
            'radial_distance': float(
                LaunchConfiguration('radial_distance').perform(context)),
            'time_from_start_factor': float(
                LaunchConfiguration('time_from_start_factor').perform(context)),
            'step_length_max': float(
                LaunchConfiguration('step_length_max').perform(context)),
            'default_linear_x': float(
                LaunchConfiguration('default_linear_x').perform(context)),
            'default_linear_y': float(
                LaunchConfiguration('default_linear_y').perform(context)),
            'default_angular_z': float(
                LaunchConfiguration('default_angular_z').perform(context)),
            'cmd_vel_timeout': float(
                LaunchConfiguration('cmd_vel_timeout').perform(context)),
            'body_height_min': float(
                LaunchConfiguration('body_height_min').perform(context)),
            'body_height_max': float(
                LaunchConfiguration('body_height_max').perform(context)),
            'use_sim_time': (
                LaunchConfiguration('use_sim_time').perform(context).lower()
                == 'true'),
            'robot_description': urdf_xml,
        }

        # parameters-Liste: erst Inline-Defaults, dann (falls gegeben)
        # das Preset-File. ROS2 wendet sie sequenziell an — letzter
        # Eintrag gewinnt bei Kollision.
        parameters = [inline_params]
        if params_file:
            parameters.append(params_file)

        return [Node(
            package='hexapod_gait',
            executable='gait_node',
            name='gait_node',
            output='screen',
            emulate_tty=True,
            parameters=parameters,
        )]

    return LaunchDescription([
        gait_pattern_arg,
        step_height_arg,
        cycle_time_arg,
        tick_rate_arg,
        body_height_arg,
        radial_distance_arg,
        tfs_factor_arg,
        step_length_max_arg,
        default_linear_x_arg,
        default_linear_y_arg,
        default_angular_z_arg,
        cmd_vel_timeout_arg,
        body_height_min_arg,
        body_height_max_arg,
        use_sim_time_arg,
        params_file_arg,
        robot_description_file_arg,
        OpaqueFunction(function=setup_gait_node),
    ])
