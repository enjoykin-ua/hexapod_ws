"""
Block I Phase 7B — Unit-Tests für den hexapod_camera-Node (RpicamNode).

Deckt die desktop-testbaren Teile: JPEG-Framing (FFD8…FFD9, inkl. Split über
read-Grenzen), den CompressedImage-Publish-Kontrakt, den ``source:=test``-Pfad,
``camera_enable`` und Robustheit (kein rpicam-vid). Der echte rpicam-Stream +
web_video_server ist Pi- bzw. Desktop-E2E (test_commands), nicht Unit.

Strategie wie test_audio_node.py: Node direkt instanziieren (Popen gepatcht →
kein echter rpicam-Subprozess), Methoden gezielt aufrufen.
"""

from unittest.mock import MagicMock, patch

from hexapod_sensors.rpicam_node import RpicamNode
import pytest
import rclpy
from rclpy.parameter import Parameter


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    # Popen gepatcht: der Auto-Start (source=rpicam) findet kein rpicam-vid →
    # sauberer _proc=None-Zustand, deterministisch unabhängig vom Dev-Rechner.
    with patch('hexapod_sensors.rpicam_node.subprocess.Popen',
               side_effect=FileNotFoundError):
        n = RpicamNode()
    yield n
    n.destroy_node()


# ----- JPEG-Framing (T7B.1) ------------------------------------------ #

def test_framing_two_complete_jpegs(node):
    """Zwei zusammengeklebte JPEGs → beide publiziert, Rest leer."""
    node._publish = MagicMock()
    j1 = b'\xff\xd8AAA\xff\xd9'
    j2 = b'\xff\xd8BBBB\xff\xd9'
    rest = node._emit_complete_jpegs(j1 + j2)
    assert rest == b''
    assert [c.args[0] for c in node._publish.call_args_list] == [j1, j2]


def test_framing_incomplete_tail_kept(node):
    """Kompletter + unvollständiger (SOI ohne EOI) → 1 publiziert, Rest behalten."""
    node._publish = MagicMock()
    j1 = b'\xff\xd8AAA\xff\xd9'
    partial = b'\xff\xd8BBB'
    rest = node._emit_complete_jpegs(j1 + partial)
    assert node._publish.call_count == 1
    assert node._publish.call_args[0][0] == j1
    assert rest == partial


def test_framing_split_across_reads(node):
    """Ein über zwei read-chunks verteiltes JPEG wird erst komplett publiziert."""
    node._publish = MagicMock()
    part1 = b'\xff\xd8AA'
    rest = node._emit_complete_jpegs(part1)
    assert node._publish.call_count == 0
    assert rest == part1
    rest = node._emit_complete_jpegs(rest + b'A\xff\xd9')
    assert node._publish.call_count == 1
    assert node._publish.call_args[0][0] == b'\xff\xd8AAA\xff\xd9'
    assert rest == b''


def test_framing_no_soi_dropped(node):
    """Bytes ohne SOI → nichts publiziert, Puffer verworfen."""
    node._publish = MagicMock()
    rest = node._emit_complete_jpegs(b'no_marker_here')
    assert node._publish.call_count == 0
    assert rest == b''


# ----- Publish-Kontrakt (T7B.2) -------------------------------------- #

def test_publish_compressed_image(node):
    """_publish setzt format=jpeg, frame_id und die JPEG-Bytes."""
    node._pub.publish = MagicMock()
    node._publish(b'\xff\xd8XYZ\xff\xd9')
    msg = node._pub.publish.call_args[0][0]
    assert msg.format == 'jpeg'
    assert msg.header.frame_id == 'camera_link'
    assert bytes(msg.data) == b'\xff\xd8XYZ\xff\xd9'


# ----- source:=test (T7B.4) ------------------------------------------ #

def test_source_test_loads_and_publishes(node, tmp_path):
    """source=test lädt das Test-JPEG + _publish_test publisht es."""
    p = tmp_path / 'x.jpg'
    p.write_bytes(b'\xff\xd8TEST\xff\xd9')
    node._source = 'test'
    node._test_image = str(p)
    node._pub.publish = MagicMock()
    node._start_test()
    assert node._test_jpeg == b'\xff\xd8TEST\xff\xd9'
    node._publish_test()
    assert bytes(node._pub.publish.call_args[0][0].data) == b'\xff\xd8TEST\xff\xd9'
    node._stop()


def test_source_test_missing_file_no_crash(node):
    """source=test mit fehlendem Test-JPEG → ERROR, kein Timer, kein Crash."""
    node._source = 'test'
    node._test_image = '/does/not/exist.jpg'
    node._start_test()
    assert node._test_jpeg is None
    assert node._timer is None


def test_publish_test_without_jpeg_no_crash(node):
    """_publish_test ohne geladenes JPEG → kein Publish, kein Crash."""
    node._test_jpeg = None
    node._pub.publish = MagicMock()
    node._publish_test()
    node._pub.publish.assert_not_called()


# ----- camera_enable (T7B.3) ----------------------------------------- #

def test_camera_enable_toggle(node):
    """camera_enable false→_stop, true→_start (live)."""
    node._start = MagicMock()
    node._stop = MagicMock()
    node._enabled = True
    res = node._on_param([Parameter('camera_enable', value=False)])
    assert res.successful is True
    node._stop.assert_called_once()
    assert node._enabled is False
    node._on_param([Parameter('camera_enable', value=True)])
    node._start.assert_called_once()
    assert node._enabled is True


# ----- Robustheit ---------------------------------------------------- #

def test_rpicam_missing_no_crash(node):
    """Auto-Start ohne rpicam-vid (Dev) → _proc None, einmal geloggt, kein Crash."""
    assert node._proc is None
    assert node._rpicam_missing_logged is True
