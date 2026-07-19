"""
Block I Phase 7A — hexapod_audio: mp3-Wiedergabe auf dem Roboter-Speaker.

Ein dünner Node, der zwei Topics abonniert und kurze mp3s spielt ([D5]):

- ``/hexapod/audio_cue`` (``std_msgs/String``, vom ``gait_node``): **Auto-Sounds**
  bei Bewegungs-Ereignissen — ``standup``/``sitdown``/``reposition``/``freeze``.
  Werden über den Param ``sound_enable`` **gemutet**.
- ``/hexapod/play_sound`` (``std_msgs/String``, von der App): **manuelle Sounds** —
  ``sound_01``/``sound_02``/``sound_03``. Spielen **immer** (auch bei ``sound_enable=false``).

Wiedergabe via ``mpg123``-Subprozess (``plughw:0,0``, MAX98357A). Ein neuer Sound
bricht den laufenden ab (letzter Trigger gewinnt). In Sim ohne Speaker läuft der
Node mit ``playback_enabled=false`` (log-only). Der aktuelle Mute-Zustand wird
latched auf ``/hexapod/sound_enabled`` (``std_msgs/Bool``) für die App-Anzeige
publiziert. Sound spielt **nur** auf dem Roboter, nie am Handy.
"""

import os
import subprocess

from ament_index_python.packages import (
    get_package_share_directory,
    PackageNotFoundError,
)
from rcl_interfaces.msg import SetParametersResult
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String
import yaml


_LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)


class AudioNode(Node):
    """Spielt kurze mp3s auf Bewegungs-Cues + manuelle App-Trigger."""

    def __init__(self):
        super().__init__('hexapod_audio')

        # Default-Pfade aus dem Paket-share (mp3s + Mapping git-versioniert).
        try:
            share = get_package_share_directory('hexapod_audio')
            default_dir = os.path.join(share, 'sounds')
            default_map = os.path.join(share, 'config', 'sound_map.yaml')
        except PackageNotFoundError:
            default_dir, default_map = '', ''

        self._sound_enable = bool(
            self.declare_parameter('sound_enable', True).value
        )
        self._sound_dir = str(
            self.declare_parameter('sound_dir', default_dir).value
        )
        self._alsa_device = str(
            self.declare_parameter('alsa_device', 'plughw:0,0').value
        )
        self._playback = bool(
            self.declare_parameter('playback_enabled', True).value
        )
        self._sound_map_file = str(
            self.declare_parameter('sound_map_file', default_map).value
        )

        self._sound_map = self._load_sound_map(self._sound_map_file)
        self._proc = None                       # aktueller mpg123-Popen
        self._mpg123_missing_logged = False

        self.create_subscription(
            String, '/hexapod/audio_cue', self._on_cue, 10)
        self.create_subscription(
            String, '/hexapod/play_sound', self._on_play, 10)

        self._enabled_pub = self.create_publisher(
            Bool, '/hexapod/sound_enabled', _LATCHED_QOS)
        self._publish_enabled()

        self.add_on_set_parameters_callback(self._on_param)

        self.get_logger().info(
            f'hexapod_audio bereit — sound_enable={self._sound_enable}, '
            f'playback_enabled={self._playback}, dir={self._sound_dir!r}, '
            f'{len(self._sound_map)} keys'
        )

    # ----- Mapping / Config ------------------------------------------ #

    def _load_sound_map(self, path: str) -> dict:
        """
        Sound-Key -> Dateiname aus der yaml laden (robust).

        Fehlt die Datei oder ist sie fehlerhaft, wird ein leeres Mapping
        zurückgegeben + geloggt (der Node läuft weiter, spielt nur nichts).
        """
        if not path or not os.path.isfile(path):
            self.get_logger().warn(f'sound_map fehlt: {path!r}')
            return {}
        try:
            with open(path, 'r') as fh:
                data = yaml.safe_load(fh) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.get_logger().error(f'sound_map nicht lesbar ({path}): {exc}')
            return {}
        return {str(k): str(v) for k, v in data.items()}

    # ----- Subscriptions --------------------------------------------- #

    def _on_cue(self, msg: String) -> None:
        """Auto-Sound (Bewegungs-Cue) — nur wenn ``sound_enable`` gesetzt."""
        if not self._sound_enable:
            return
        self._play_key(msg.data)

    def _on_play(self, msg: String) -> None:
        """Manueller Sound (App-Button) — spielt immer (unabhängig vom Mute)."""
        self._play_key(msg.data)

    # ----- Playback -------------------------------------------------- #

    def _play_key(self, key: str) -> None:
        """Sound-Key auf eine Datei mappen + abspielen."""
        fname = self._sound_map.get(key)
        if fname is None:
            self.get_logger().warn(f'unbekannter sound key {key!r}')
            return
        self._play_file(os.path.join(self._sound_dir, fname))

    def _play_file(self, path: str) -> None:
        """
        Eine mp3 abspielen — neuer Sound bricht den laufenden ab.

        Fehlt die Datei -> WARN (kein Crash). ``playback_enabled=false``
        (Sim/Dev ohne Speaker) -> nur Log. Fehlt ``mpg123`` -> einmal ERROR.
        """
        if not os.path.isfile(path):
            self.get_logger().warn(f'sound-Datei fehlt: {path}')
            return
        if not self._playback:
            self.get_logger().info(f'[dry-run] wuerde abspielen: {path}')
            return
        # Neuer Sound bricht den laufenden ab (letzter Trigger gewinnt).
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        try:
            self._proc = subprocess.Popen(
                ['mpg123', '-q', '-a', self._alsa_device, path])
        except FileNotFoundError:
            if not self._mpg123_missing_logged:
                self.get_logger().error(
                    'mpg123 nicht installiert — kein Audio. '
                    "Auf dem Pi: 'sudo apt install mpg123'."
                )
                self._mpg123_missing_logged = True

    # ----- sound_enable live + Mute-Status --------------------------- #

    def _on_param(self, params) -> SetParametersResult:
        """``sound_enable`` live übernehmen + Mute-Status re-publishen."""
        changed = False
        for p in params:
            if p.name == 'sound_enable':
                self._sound_enable = bool(p.value)
                changed = True
        if changed:
            self._publish_enabled()
        return SetParametersResult(successful=True)

    def _publish_enabled(self) -> None:
        """Aktuellen Mute-Zustand latched publishen (App-Anzeige)."""
        self._enabled_pub.publish(Bool(data=self._sound_enable))

    # ----- Cleanup --------------------------------------------------- #

    def destroy_node(self) -> bool:
        """Beim Herunterfahren einen noch laufenden mpg123 beenden."""
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AudioNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
