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
Fußkontakt-Viz (Block A5 Stufe 5, HW5v) — RViz-Sichtprüfung der Taster.

Abonniert die 6 ``/leg_<n>/foot_contact`` (``std_msgs/Bool``) und publisht eine
``MarkerArray``: **eine Kugel pro Fuß am ``leg_<n>_foot_link``-TF-Frame**,
eingefärbt nach Kontakt-Status. Der Marker (Ø ``marker_scale``, minimal größer
als die schwarze URDF-Fußkugel Ø 0,016 m) **überdeckt** die vorhandene Fußkugel
→ der Fuß selbst „wird" farbig:

  - **grün**  = Kontakt (Taster gedrückt / Fuß am Boden),
  - **grau**  = kein Kontakt (Taster offen),
  - **dunkel/transparent** = stale (länger als ``stale_timeout`` keine Message →
    keine/tote Pipeline; ehrlich als „keine Daten" statt fälschlich „offen").

**Quellen-agnostisch:** funktioniert identisch mit der Sim
(``foot_contact_publisher``) und der HW (``hexapod_hardware``-Plugin). Der
RobotModel + die TF-Frames kommen vom ``robot_state_publisher`` (Sim- bzw.
``real.launch.py``-Bringup) — dieser Node hängt sich nur an die Bool-Topics.

Betrieb (3 Terminals, HW-Bench ohne Servo-Power):
  ros2 launch hexapod_bringup real.launch.py loopback_mode:=false
  ros2 run hexapod_gait foot_contact_viz
  rviz2 -d <hexapod_description>/config/view_hw.rviz
"""

from __future__ import annotations

import time

from geometry_msgs.msg import Point

import rclpy
from rclpy.node import Node

from std_msgs.msg import Bool, ColorRGBA

from visualization_msgs.msg import Marker, MarkerArray


_LEG_IDS = (1, 2, 3, 4, 5, 6)

# Kontakt = grün, offen = neutralgrau, stale = dunkel + halbtransparent.
_GREEN = ColorRGBA(r=0.1, g=0.8, b=0.1, a=1.0)
_GREY = ColorRGBA(r=0.5, g=0.5, b=0.5, a=0.9)
_DARK = ColorRGBA(r=0.15, g=0.15, b=0.15, a=0.4)


class FootContactViz(Node):
    """6 Bool-Subs -> 6 farbige Fuß-Marker (MarkerArray), Timer-Republish."""

    def __init__(self) -> None:
        super().__init__('foot_contact_viz')

        # Ø der Kugel (m). 0,020 überdeckt die URDF-Fußkugel (foot_radius 0,008
        # → Ø 0,016), sodass der Fuß selbst die Farbe annimmt. Live-tunbar.
        self.declare_parameter('marker_scale', 0.020)
        # Wall-clock-Staleness: länger als das keine Message auf einem Bein →
        # dunkler „keine-Daten"-Marker statt fälschlich „offen/grau".
        self.declare_parameter('stale_timeout', 0.5)
        # RViz-schonender Republish; display-only, daher niedrige Rate genügt.
        self.declare_parameter('publish_rate', 5.0)

        self._contact = {leg: False for leg in _LEG_IDS}
        # Letzter Message-Empfang je Bein (time.monotonic, wall-clock — robust
        # ohne /clock auf HW; gleiche Wahl wie foot_contact_publisher.py). 0.0 =
        # noch nie empfangen → beim Start alle Marker stale/dunkel.
        self._last_t = {leg: 0.0 for leg in _LEG_IDS}

        self._pub = self.create_publisher(MarkerArray, 'foot_contact_markers', 1)
        self._subs = {
            leg: self.create_subscription(
                Bool, f'/leg_{leg}/foot_contact',
                self._make_cb(leg), 10,
            )
            for leg in _LEG_IDS
        }

        rate = float(self.get_parameter('publish_rate').value)
        self._timer = self.create_timer(1.0 / rate, self._publish)

        self.get_logger().info(
            f'foot_contact_viz init: {len(_LEG_IDS)} legs, '
            f'publish_rate={rate:.0f} Hz, '
            f"stale_timeout={self.get_parameter('stale_timeout').value:.2f} s"
        )

    def _make_cb(self, leg: int):
        """Closure pro Bein: cacht Kontakt-State + Empfangs-Zeitpunkt."""
        def _cb(msg: Bool) -> None:
            self._contact[leg] = bool(msg.data)
            self._last_t[leg] = time.monotonic()
        return _cb

    def _color_for(self, leg: int, now: float) -> ColorRGBA:
        """Stale (kein/toter Publisher) > offen; sonst grün/grau nach Kontakt."""
        stale = float(self.get_parameter('stale_timeout').value)
        if now - self._last_t[leg] > stale:
            return _DARK
        return _GREEN if self._contact[leg] else _GREY

    def _build_markers(self, now: float) -> MarkerArray:
        """Baut die MarkerArray (1 Kugel je Fuß am foot_link-Frame). now = monotonic."""
        scale = float(self.get_parameter('marker_scale').value)
        arr = MarkerArray()
        for leg in _LEG_IDS:
            m = Marker()
            m.header.frame_id = f'leg_{leg}_foot_link'
            # Stamp bewusst 0 (Marker-Default): RViz nimmt die NEUESTE verfügbare
            # TF statt der exakten Stempelzeit. foot_link ist ein Blatt-Frame, der
            # dem base_link (Fixed Frame) ein paar ms hinterherhängt — mit einem
            # now()-Stempel würde RViz „extrapolation into the future" werfen und
            # den Marker jeden Tick kurz verwerfen (Flackern). Stamp 0 = stabil.
            m.ns = 'foot_contact'
            m.id = leg
            m.type = Marker.SPHERE
            m.action = Marker.ADD
            # Position 0 im foot_link-Frame → RViz platziert per TF genau auf
            # die vorhandene Fußkugel.
            m.pose.position = Point(x=0.0, y=0.0, z=0.0)
            m.pose.orientation.w = 1.0
            m.scale.x = m.scale.y = m.scale.z = scale
            m.color = self._color_for(leg, now)
            arr.markers.append(m)
        return arr

    def _publish(self) -> None:
        now = time.monotonic()
        self._pub.publish(self._build_markers(now))
        n_contact = sum(
            1 for leg in _LEG_IDS
            if (now - self._last_t[leg]) <= float(
                self.get_parameter('stale_timeout').value)
            and self._contact[leg]
        )
        self.get_logger().info(
            f'foot_contact_viz: {n_contact}/6 in contact',
            throttle_duration_sec=2.0)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = FootContactViz()
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
