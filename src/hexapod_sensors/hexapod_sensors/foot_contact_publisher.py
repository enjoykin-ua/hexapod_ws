"""
foot_contact_publisher — Sim-zu-Bool-Adapter für Foot-Bodenkontakt.

Subscribed auf 6 ``ros_gz_interfaces/Contacts``-Topics (vom ros_gz_bridge
gespeist mit Gazebo-Contact-Sensor-Output) und publisht pro Bein einen
``std_msgs/Bool`` auf ``/leg_<n>/foot_contact``.

**Pattern:** Gazebo Contact-Sensoren sind event-basiert — sie publishen nur
wenn Kontakt da ist (im Stand-Pose: ~50 Hz, im Schwung: silent). Konsumenten
erwarten aber ein dauerhaftes Bool-Signal (passt zur Phase-7-HW-Realität,
wo ein Microswitch-Treiber periodisch publisht). Daher: Knoten hält pro Bein
``_last_contact_time`` und publisht in einem Timer-Callback (Default 50 Hz)
``Bool(now - last_contact_time < contact_timeout)``. Damit fließt **immer**
ein aktuelles Signal — `true` wenn kürzlich Contact, sonst `false`.

Sim/HW-Abstraktion (Stufe-D-Design-Entscheidung 2): in Phase 7 publisht
der HW-Treiber direkt periodisch ``Bool``. Konsumenten sehen denselben
Topic-Typ und denselben Pattern (periodisches Bool-Update), unabhängig
ob Sim oder HW.
"""

import time

import rclpy
from rclpy.node import Node
from ros_gz_interfaces.msg import Contacts
from std_msgs.msg import Bool


_LEG_IDS = (1, 2, 3, 4, 5, 6)


class FootContactPublisher(Node):
    """6 Subs (Contacts) -> 6 Pubs (Bool), Timer-basierte Publication."""

    def __init__(self):
        super().__init__('foot_contact_publisher')

        self.declare_parameter('publish_rate', 50.0)
        self.declare_parameter('contact_timeout', 0.1)
        self._rate = float(self.get_parameter('publish_rate').value)
        self._timeout = float(self.get_parameter('contact_timeout').value)

        # Letzter Kontakt-Zeitstempel pro Bein (Sekunden, Sim-Zeit). Initial 0
        # heißt "nie Kontakt" -> in der ersten Timer-Iteration wird Bool(false)
        # publisht (so lange bis tatsächlich ein Kontakt eintrifft).
        self._last_contact_time = {leg_id: 0.0 for leg_id in _LEG_IDS}

        self._pubs = {}
        self._subs = {}

        for leg_id in _LEG_IDS:
            out_topic = f'/leg_{leg_id}/foot_contact'
            self._pubs[leg_id] = self.create_publisher(Bool, out_topic, 10)

            in_topic = f'/leg_{leg_id}/foot_contact_raw'
            self._subs[leg_id] = self.create_subscription(
                Contacts,
                in_topic,
                self._make_callback(leg_id),
                10,
            )

        self._timer = self.create_timer(1.0 / self._rate, self._publish_all)

        self.get_logger().info(
            f'foot_contact_publisher init: '
            f'{len(_LEG_IDS)} legs, publish_rate={self._rate:.0f} Hz, '
            f'contact_timeout={self._timeout:.3f} s'
        )

    def _make_callback(self, leg_id: int):
        """Closure-Factory pro Bein, damit leg_id im Callback gebunden bleibt."""
        def _cb(msg: Contacts):
            if len(msg.contacts) > 0:
                # Wall-clock (time.monotonic) statt Sim-Zeit, damit der Timer
                # auch dann zuverlässig läuft, wenn /clock noch nicht
                # subscribed ist (DDS-Discovery-Race in rclpy/Jazzy). Sim-RTF=1
                # in Phase 5, also kein praktischer Drift-Effekt.
                self._last_contact_time[leg_id] = time.monotonic()
        return _cb

    def _publish_all(self):
        """Pro Tick: aktuelle Bool-Status pro Bein berechnen + publishen."""
        now = time.monotonic()
        for leg_id in _LEG_IDS:
            in_contact = (now - self._last_contact_time[leg_id]) < self._timeout
            self._pubs[leg_id].publish(Bool(data=in_contact))


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
