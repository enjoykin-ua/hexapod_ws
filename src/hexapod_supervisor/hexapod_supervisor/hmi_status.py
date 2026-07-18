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
hmi_status node (Block I Phase 5) — Always-On HMI-Glue für die App.

Lebt in der **Always-On-Schicht** (``always_on.launch.py``, ab Boot) — damit das
App-Config-Panel + die Dropdowns schon **beim Connect** befüllt sind, VOR dem
On-Demand-Stack. Publiziert drei App-Naht-Topics (JSON in ``std_msgs/String``):

  - ``/hexapod/capabilities``   (gelatcht) : statische Enums (Gangarten/Stance/
                                             Tempo) für die Dropdowns.
  - ``/hexapod/config_manifest`` (gelatcht): die kuratierte Whitelist der
                                             verstellbaren Params (Gruppe/Label/
                                             Hint/Default/min/max/Widget/Gating).
                                             Die App rendert das Panel generisch;
                                             get/set der Werte läuft über die
                                             nativen rosbridge-Param-Services.
  - ``/hexapod/alerts``          (gelatcht, Tiefe N): WARN/ERROR/FATAL aus
                                             ``/rosout`` republished → Fehler-/
                                             Warn-Liste in der App.

Capabilities + Manifest kommen aus **einer** YAML (Single Source):
``hexapod_supervisor/config/hmi_config_manifest.yaml``. Der Live-**Status**
(``/hexapod/status``, State/Stance/Gangart) kommt NICHT hier her, sondern aus dem
``gait_node`` (Daten existieren nur im laufenden Stack).

Contract §6 (Block I Phase 5).
"""

import json
import os

from ament_index_python.packages import get_package_share_directory
from rcl_interfaces.msg import Log
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
import yaml

# rcl_interfaces/msg/Log-Level: DEBUG=10 INFO=20 WARN=30 ERROR=40 FATAL=50.
_LEVEL_WARN = 30
_LEVEL_NAMES = {30: 'WARN', 40: 'ERROR', 50: 'FATAL'}


def _alert_dict(level: int, name: str, text: str,
                stamp_sec: int, stamp_nsec: int) -> dict | None:
    """
    Ein /rosout-Log-Level+Feld zu einem Alert-Dict formen (pure, testbar).

    Gibt ``None`` zurück, wenn ``level`` unter WARN liegt (kein Alert).
    """
    if level < _LEVEL_WARN:
        return None
    return {
        'stamp': round(stamp_sec + stamp_nsec * 1e-9, 3),
        'level': _LEVEL_NAMES.get(level, str(level)),
        'name': name,
        'msg': text,
    }


def _latched_qos(depth: int = 1) -> QoSProfile:
    """Gelatchte QoS (reliable + transient_local) → späte Subscriber bekommen es."""
    return QoSProfile(
        depth=depth,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        reliability=ReliabilityPolicy.RELIABLE,
    )


class HmiStatus(Node):
    """Publiziert Capabilities + Config-Manifest (gelatcht) + Alerts (aus /rosout)."""

    def __init__(self):
        """Manifest laden, Capabilities/Manifest latchen, /rosout abonnieren."""
        super().__init__('hmi_status')

        self.declare_parameter('manifest_file', '')
        self.declare_parameter('alerts_history', 50)

        data = self._load_manifest()
        capabilities = data.get('capabilities', {})
        manifest = data.get('manifest', {})
        n_params = len(manifest.get('params', []))

        # Capabilities (gelatcht, einmal).
        self._cap_pub = self.create_publisher(
            String, '/hexapod/capabilities', _latched_qos())
        self._cap_pub.publish(String(data=json.dumps(capabilities)))

        # Config-Manifest (gelatcht, einmal).
        self._manifest_pub = self.create_publisher(
            String, '/hexapod/config_manifest', _latched_qos())
        self._manifest_pub.publish(String(data=json.dumps(manifest)))

        # Alerts: WARN+ aus /rosout republished. Gelatcht mit Tiefe N, damit ein
        # spät verbindender App-Subscriber die letzten N Alerts bekommt.
        hist = max(1, int(self.get_parameter('alerts_history').value))
        self._alerts_pub = self.create_publisher(
            String, '/hexapod/alerts', _latched_qos(depth=hist))
        # /rosout VOLATILE abonnieren → nur NEUE Logs, kein Voll-Backlog-Flood
        # (der /rosout-Publisher ist transient_local mit grosser Tiefe).
        self.create_subscription(
            Log, '/rosout', self._on_log,
            QoSProfile(depth=100, durability=DurabilityPolicy.VOLATILE,
                       reliability=ReliabilityPolicy.RELIABLE))

        self.get_logger().info(
            f'hmi_status: capabilities + config_manifest ({n_params} params) '
            f'gelatcht; Alerts aus /rosout (WARN+, Historie {hist}).')

    def _load_manifest(self) -> dict:
        """YAML-Manifest laden (Param-Pfad oder Default aus dem share-Verzeichnis)."""
        path = str(self.get_parameter('manifest_file').value)
        if not path:
            path = os.path.join(
                get_package_share_directory('hexapod_supervisor'),
                'config', 'hmi_config_manifest.yaml')
        with open(path) as handle:
            return yaml.safe_load(handle) or {}

    def _on_log(self, msg: Log) -> None:
        """Ein /rosout-Log ab WARN als JSON auf /hexapod/alerts republishen."""
        # Eigene Logs nicht mit-republishen (Rausch-/Loop-Schutz).
        if msg.name == self.get_name():
            return
        alert = _alert_dict(
            msg.level, msg.name, msg.msg, msg.stamp.sec, msg.stamp.nanosec)
        if alert is None:
            return
        self._alerts_pub.publish(String(data=json.dumps(alert)))


def main(args=None):
    """Entry point: spin the HMI status node."""
    rclpy.init(args=args)
    node = HmiStatus()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
