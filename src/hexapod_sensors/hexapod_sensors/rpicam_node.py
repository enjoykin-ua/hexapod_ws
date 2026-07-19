"""
Block I Phase 7B — hexapod_camera: echte Raspi-Cam (OV5647) → ROS-Image-Topic.

Publisht die Kamera als **`sensor_msgs/CompressedImage`** (JPEG) auf
`/camera/image_raw/compressed` — dieselbe Topic-Basis, die in der Sim der
Gazebo-Kamera-Sensor roh liefert. Der bestehende `web_video_server` streamt es
(HW: `…&type=ros_compressed`, reicht die JPEGs durch — kein Pi-Decode).

Zwei Quellen (Param ``source``):
- ``rpicam`` (Default, **Pi**): `rpicam-vid --codec mjpeg -o -` als Subprozess;
  der MJPEG-Bytestrom wird in einzelne JPEGs (FFD8…FFD9) zerlegt + publiziert.
- ``test`` (**Desktop**): publisht ein statisches Test-JPEG (`assets/`) in der
  ``framerate``-Loop → die Kette Node→CompressedImage→web_video_server→Bild ist
  **ohne Pi** verifizierbar.

``camera_enable`` (Param) startet/stoppt die Quelle live (Strom/Wärme).
"""

import os
import subprocess
import threading

from ament_index_python.packages import (
    get_package_share_directory,
    PackageNotFoundError,
)
from rcl_interfaces.msg import SetParametersResult
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


# Sanity-Cap: verwirft den Puffer, wenn er ohne vollständiges JPEG so groß wird
# (korrupter/verschobener Strom) — verhindert unbegrenztes Wachstum.
_MAX_BUFFER_BYTES = 4 * 1024 * 1024


class RpicamNode(Node):
    """OV5647 (oder Test-JPEG) → CompressedImage auf /camera/image_raw/compressed."""

    def __init__(self):
        super().__init__('hexapod_camera')

        try:
            share = get_package_share_directory('hexapod_sensors')
            default_test_img = os.path.join(share, 'assets', 'test_pattern.jpg')
        except PackageNotFoundError:
            default_test_img = ''

        self._source = str(self.declare_parameter('source', 'rpicam').value)
        self._w = int(self.declare_parameter('width', 1280).value)
        self._h = int(self.declare_parameter('height', 720).value)
        self._fps = float(self.declare_parameter('framerate', 15.0).value)
        self._frame_id = str(
            self.declare_parameter('frame_id', 'camera_link').value)
        self._test_image = str(
            self.declare_parameter('test_image', default_test_img).value)
        self._enabled = bool(self.declare_parameter('camera_enable', True).value)

        self._pub = self.create_publisher(
            CompressedImage, '/camera/image_raw/compressed', 10)

        self._proc = None            # rpicam-vid Popen
        self._reader = None          # stdout-Reader-Thread
        self._timer = None           # test-Modus-Timer
        self._test_jpeg = None       # geladene Test-JPEG-Bytes
        self._rpicam_missing_logged = False

        self.add_on_set_parameters_callback(self._on_param)

        if self._enabled:
            self._start()

        self.get_logger().info(
            f'hexapod_camera bereit — source={self._source!r}, '
            f'{self._w}x{self._h}@{self._fps:.0f}, camera_enable={self._enabled}'
        )

    # ----- Start / Stop der Quelle ----------------------------------- #

    def _start(self) -> None:
        if self._source == 'test':
            self._start_test()
        else:
            self._start_rpicam()

    def _stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    # ----- rpicam-Quelle (Pi) ---------------------------------------- #

    def _start_rpicam(self) -> None:
        cmd = [
            'rpicam-vid', '-t', '0', '-n', '--codec', 'mjpeg',
            '--framerate', str(int(self._fps)),
            '--width', str(self._w), '--height', str(self._h),
            '--inline', '-o', '-',
        ]
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, bufsize=0)
        except FileNotFoundError:
            if not self._rpicam_missing_logged:
                self.get_logger().error(
                    'rpicam-vid nicht gefunden — Kamera-Userland fehlt. Setup: '
                    'peripherals_tests/camera_ov5647_v13.md (libcamera+rpicam-apps).'
                )
                self._rpicam_missing_logged = True
            self._proc = None
            return
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self) -> None:
        buf = b''
        proc = self._proc
        while rclpy.ok() and proc is not None and proc.poll() is None:
            chunk = proc.stdout.read(4096)
            if not chunk:
                break
            buf += chunk
            buf = self._emit_complete_jpegs(buf)
            if len(buf) > _MAX_BUFFER_BYTES:
                self.get_logger().warn(
                    'JPEG-Puffer über Limit ohne vollständigen Frame — verworfen')
                buf = b''

    def _emit_complete_jpegs(self, buf: bytes) -> bytes:
        """
        Vollständige JPEGs (SOI FFD8 … EOI FFD9) publizieren, Rest zurückgeben.

        Zuverlässig für well-formed JPEG: FF-Bytes im Entropie-Strom sind
        byte-gestuffed (FF00) bzw. Restart-Marker (FFD0–D7) → FFD9 tritt nur als
        echtes EOI auf.
        """
        while True:
            soi = buf.find(b'\xff\xd8')
            if soi < 0:
                return b''
            eoi = buf.find(b'\xff\xd9', soi + 2)
            if eoi < 0:
                return buf[soi:]        # unvollständig → SOI-Rest behalten
            self._publish(buf[soi:eoi + 2])
            buf = buf[eoi + 2:]

    # ----- test-Quelle (Desktop) ------------------------------------- #

    def _start_test(self) -> None:
        if not os.path.isfile(self._test_image):
            self.get_logger().error(f'Test-JPEG fehlt: {self._test_image}')
            return
        with open(self._test_image, 'rb') as fh:
            self._test_jpeg = fh.read()
        self._timer = self.create_timer(1.0 / self._fps, self._publish_test)

    def _publish_test(self) -> None:
        if self._test_jpeg is not None:
            self._publish(self._test_jpeg)

    # ----- Publish --------------------------------------------------- #

    def _publish(self, jpeg: bytes) -> None:
        msg = CompressedImage()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        msg.format = 'jpeg'
        msg.data = jpeg
        self._pub.publish(msg)

    # ----- camera_enable live ---------------------------------------- #

    def _on_param(self, params) -> SetParametersResult:
        for p in params:
            if p.name == 'camera_enable':
                want = bool(p.value)
                if want and not self._enabled:
                    self._start()
                elif not want and self._enabled:
                    self._stop()
                self._enabled = want
        return SetParametersResult(successful=True)

    # ----- Cleanup --------------------------------------------------- #

    def destroy_node(self) -> bool:
        """Beim Herunterfahren die Quelle sauber stoppen."""
        self._stop()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RpicamNode()
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
