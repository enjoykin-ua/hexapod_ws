"""
foot_contact_publisher — Sim-zu-Bool-Adapter für Foot-Bodenkontakt.

Subscribed auf 6 ``ros_gz_interfaces/Contacts``-Topics (vom ros_gz_bridge
gespeist mit Gazebo-Contact-Sensor-Output) und publisht pro Bein einen
``std_msgs/Bool`` auf ``/leg_<n>/foot_contact``. Ein Foot ist im Kontakt,
wenn die Contacts-Message mindestens einen Eintrag hat.

Sim/HW-Abstraktion (Stufe-D-Design-Entscheidung 2): in Phase 7 publisht
der HW-Treiber auf den gleichen Output-Topic-Namen direkt ``Bool``
(GPIO/Servo2040-Switch-Read). Konsumenten sehen denselben Topic-Typ,
unabhängig ob Sim oder HW.

Toggle-Mechanik (Stufe-D-Design-Entscheidung 3): wird vom Launch-File
``enable_foot_contact:=false`` per ``IfCondition`` gestoppt. Selbst-
Auflösung (z. B. via ROS-Parameter) hier nicht nötig.
"""

import rclpy
from rclpy.node import Node
from ros_gz_interfaces.msg import Contacts
from std_msgs.msg import Bool


# Bein-IDs entsprechend Mountpunkten in hexapod_kinematics. Nicht aus
# hexapod_kinematics importiert, weil das Paket eine optionale Dependency
# wäre — die Bein-IDs sind hier statisch (1..6) und ändern sich nicht.
_LEG_IDS = (1, 2, 3, 4, 5, 6)


class FootContactPublisher(Node):
    """6 Subs (Contacts) -> 6 Pubs (Bool), eine Konversion pro Bein."""

    def __init__(self):
        super().__init__('foot_contact_publisher')

        self._pubs = {}
        self._subs = {}

        for leg_id in _LEG_IDS:
            # Output: std_msgs/Bool auf /leg_<n>/foot_contact
            out_topic = f'/leg_{leg_id}/foot_contact'
            self._pubs[leg_id] = self.create_publisher(Bool, out_topic, 10)

            # Input: ros_gz_interfaces/Contacts auf /leg_<n>/foot_contact_raw
            in_topic = f'/leg_{leg_id}/foot_contact_raw'
            self._subs[leg_id] = self.create_subscription(
                Contacts,
                in_topic,
                self._make_callback(leg_id),
                10,
            )

        self.get_logger().info(
            f'foot_contact_publisher init: '
            f'{len(_LEG_IDS)} legs, in /leg_<n>/foot_contact_raw -> '
            f'out /leg_<n>/foot_contact (Bool)'
        )

    def _make_callback(self, leg_id: int):
        """Closure-Factory pro Bein, damit leg_id im Callback gebunden bleibt."""
        def _cb(msg: Contacts):
            self._pubs[leg_id].publish(Bool(data=len(msg.contacts) > 0))
        return _cb


def main(args=None):
    rclpy.init(args=args)
    node = FootContactPublisher()
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
