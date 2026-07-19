"""
Unit-Tests für den hexapod_audio-Node (Block I Phase 7A).

Strategie (wie test_sitdown_node.py in hexapod_gait): AudioNode direkt
instanziieren, die Handler als Methoden aufrufen. subprocess.Popen +
os.path.isfile werden gemockt — kein echtes mpg123/ALSA nötig. Deckt Mute-Logik
(Auto vs. manuell), neuer-bricht-alten-ab, Robustheit, Sim-log-only und den
latched Mute-Status.
"""

from unittest.mock import MagicMock, patch

from hexapod_audio.audio_node import AudioNode
import pytest
import rclpy
from std_msgs.msg import String


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = AudioNode()
    # Deterministische Test-Map + -Verzeichnis (unabhängig vom Paket-share).
    n._sound_map = {
        'standup': 'sound_aufstehen.mp3',
        'sitdown': 'sound_hinsetzen.mp3',
        'reposition': 'sound_repositioning.mp3',
        'freeze': 'sound_freeze.mp3',
        'sound_01': 'sound_01.mp3',
    }
    n._sound_dir = '/sounds'
    n._playback = True
    yield n
    n.destroy_node()


def _cue(node, name):
    node._on_cue(String(data=name))


def _play(node, name):
    node._on_play(String(data=name))


# ----- Auto-Cue Mute-Logik ------------------------------------------- #

def test_auto_cue_plays_when_enabled(node):
    """Auto-Cue bei sound_enable=true → spielt die gemappte Datei."""
    node._sound_enable = True
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _cue(node, 'standup')
    popen.assert_called_once()
    assert popen.call_args[0][0][-1] == '/sounds/sound_aufstehen.mp3'


def test_auto_cue_muted_when_disabled(node):
    """Auto-Cue bei sound_enable=false → spielt NICHT (gemutet)."""
    node._sound_enable = False
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _cue(node, 'standup')
    popen.assert_not_called()


def test_manual_play_always_plays_even_when_muted(node):
    """Manueller play_sound spielt IMMER, auch bei sound_enable=false."""
    node._sound_enable = False
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _play(node, 'sound_01')
    popen.assert_called_once()
    assert popen.call_args[0][0][-1] == '/sounds/sound_01.mp3'


# ----- neuer bricht alten ab ----------------------------------------- #

def test_new_sound_terminates_running(node):
    """Ein laufender Sound wird beim nächsten Trigger abgebrochen."""
    node._sound_enable = True
    running = MagicMock()
    running.poll.return_value = None            # läuft noch
    node._proc = running
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _play(node, 'sound_01')
    running.terminate.assert_called_once()
    popen.assert_called_once()


def test_finished_sound_not_terminated(node):
    """Ein bereits beendeter Prozess wird nicht nochmal terminiert."""
    node._sound_enable = True
    done = MagicMock()
    done.poll.return_value = 0                   # schon fertig
    node._proc = done
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen'):
        _play(node, 'sound_01')
    done.terminate.assert_not_called()


# ----- Robustheit ---------------------------------------------------- #

def test_unknown_key_no_crash_no_play(node):
    """Unbekannter Sound-Key → WARN, kein Popen, kein Crash."""
    node._sound_enable = True
    with patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _play(node, 'does_not_exist')
    popen.assert_not_called()


def test_missing_file_no_crash_no_play(node):
    """Fehlende mp3-Datei → WARN, kein Popen."""
    node._sound_enable = True
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=False), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _play(node, 'sound_01')
    popen.assert_not_called()


def test_mpg123_missing_no_crash(node):
    """Fehlt mpg123 (FileNotFoundError) → kein Crash, einmal geloggt."""
    node._sound_enable = True
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen',
               side_effect=FileNotFoundError):
        _play(node, 'sound_01')      # darf nicht werfen
        _play(node, 'sound_01')      # zweiter Aufruf: kein erneutes Log
    assert node._mpg123_missing_logged is True


# ----- Sim log-only -------------------------------------------------- #

def test_playback_disabled_is_log_only(node):
    """playback_enabled=false (Sim) → kein Subprozess, nur Log."""
    node._sound_enable = True
    node._playback = False
    with patch('hexapod_audio.audio_node.os.path.isfile', return_value=True), \
         patch('hexapod_audio.audio_node.subprocess.Popen') as popen:
        _cue(node, 'standup')
    popen.assert_not_called()


# ----- Mute-Status + Toggle ------------------------------------------ #

def test_sound_enabled_publisher_is_latched(node):
    """/hexapod/sound_enabled ist reliable + transient_local (latched)."""
    from rclpy.qos import DurabilityPolicy, ReliabilityPolicy
    qos = node._enabled_pub.qos_profile
    assert qos.durability == DurabilityPolicy.TRANSIENT_LOCAL
    assert qos.reliability == ReliabilityPolicy.RELIABLE


def test_sound_enable_toggle_republishes_status(node):
    """sound_enable live-Toggle → _publish_enabled feuert mit neuem Wert."""
    node._enabled_pub.publish = MagicMock()
    from rclpy.parameter import Parameter
    res = node._on_param([Parameter('sound_enable', value=False)])
    assert res.successful is True
    assert node._sound_enable is False
    assert node._enabled_pub.publish.call_args[0][0].data is False
