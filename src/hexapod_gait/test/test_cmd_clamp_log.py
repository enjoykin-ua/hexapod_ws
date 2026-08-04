"""
Tests für die gestaffelte Clamp-Meldung (Block I Phase 11, B2b).

Die Engine stutzt ein cmd_vel proportional, sobald die größte Bein-
Geschwindigkeit über ``linear_max = step_length_max / stance_duration``
liegt. Seit der Tempo-Auslegung (längere Bodenzeit) ist ein **leichter**
Clamp der Normalfall — in den Stance-Modi mit kleinem Deckel (tief/hoch)
und bei den Nicht-Tripod-Gangarten liegt die Stick-Skala regelmäßig
darüber.

Vorher meldete der Node jeden Clamp als WARN alle 2 s. Diese Meldungen
laufen über ``/rosout`` → ``hmi_status`` → ``/hexapod/alerts`` **in die
App-Alert-Liste** und hätten dort im Normalbetrieb echte Warnungen
zugedeckt. Deshalb: WARN nur bei deutlicher Begrenzung, sonst debug —
beides mit 10 s Throttle.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import _CLAMP_WARN_FACTOR, GaitNode
from hexapod_gait.gait_patterns import GAIT_PRESETS
import pytest
import rclpy


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    yield n
    n.destroy_node()


class _FakeLogger:
    """Sammelt Log-Aufrufe statt sie auszugeben."""

    def __init__(self):
        self.calls = []

    def warn(self, msg, **kwargs):
        self.calls.append(('warn', msg, kwargs))

    def debug(self, msg, **kwargs):
        self.calls.append(('debug', msg, kwargs))

    def info(self, msg, **kwargs):
        self.calls.append(('info', msg, kwargs))

    def error(self, msg, **kwargs):
        self.calls.append(('error', msg, kwargs))


def _engine(step_length_max=0.085, cycle_time=3.4):
    return GaitEngine(
        pattern=GAIT_PRESETS['tripod'],
        step_height=0.050,
        cycle_time=cycle_time,
        radial_distance=0.160,
        body_height=-0.080,
        step_length_max=step_length_max,
    )


# ----- Engine: der Faktor selbst ---------------------------------------


def test_factor_is_one_without_clamp():
    """Ohne Begrenzung bleibt der Faktor exakt 1.0."""
    eng = _engine()
    assert eng.set_command(eng.linear_max * 0.5, 0.0, 0.0, 0.0) is False
    assert eng.last_clamp_factor == pytest.approx(1.0)


def test_factor_matches_ratio():
    """Doppeltes Kommando → Faktor 0.5 (proportionales Clamping)."""
    eng = _engine()
    assert eng.set_command(eng.linear_max * 2.0, 0.0, 0.0, 0.0) is True
    assert eng.last_clamp_factor == pytest.approx(0.5, abs=1e-6)


def test_factor_resets_on_next_free_command():
    """Ein freies Kommando nach einem Clamp setzt den Faktor zurück."""
    eng = _engine()
    eng.set_command(eng.linear_max * 3.0, 0.0, 0.0, 0.0)
    assert eng.last_clamp_factor < 1.0
    eng.set_command(eng.linear_max * 0.4, 0.0, 0.0, 0.1)
    assert eng.last_clamp_factor == pytest.approx(1.0)


# ----- Node: die Log-Staffelung ----------------------------------------


def test_light_clamp_logs_debug_not_warn(node):
    """
    Leichter Clamp (Faktor über der Schwelle) → nur debug.

    Das ist der Normalfall in vielen Kombinationen: dort ist linear_max
    kleiner als die Stick-Skala, ohne dass etwas im Argen liegt
    (34 der 48 ausgelegten Betriebspunkte clampen leicht).
    """
    log = _FakeLogger()
    node.get_logger = lambda: log
    lm = node._engine.linear_max
    # Faktor ~0.39 = der schlechteste REGULAERE Betriebspunkt
    # (wave + schnell + hoch) — muss still bleiben.
    node._engine.set_command(lm / 0.39, 0.0, 0.0, 0.0)
    assert node._engine.last_clamp_factor > _CLAMP_WARN_FACTOR
    node._log_cmd_clamp(lm / 0.39, 0.0, 0.0)
    assert [c[0] for c in log.calls] == ['debug']


def test_strong_clamp_logs_warn(node):
    """Echte Fehlkonfiguration (Kommando 8x ueber linear_max) → WARN."""
    log = _FakeLogger()
    node.get_logger = lambda: log
    lm = node._engine.linear_max
    node._engine.set_command(lm * 8.0, 0.0, 0.0, 0.0)
    assert node._engine.last_clamp_factor < _CLAMP_WARN_FACTOR
    node._log_cmd_clamp(lm * 8.0, 0.0, 0.0)
    assert [c[0] for c in log.calls] == ['warn']


def test_clamp_log_is_throttled_ten_seconds(node):
    """Beide Pfade drosseln auf 10 s (vorher 2 s WARN)."""
    log = _FakeLogger()
    node.get_logger = lambda: log
    lm = node._engine.linear_max
    for factor in (1.0 / 0.39, 8.0):
        node._engine.set_command(lm * factor, 0.0, 0.0, 0.0)
        node._log_cmd_clamp(lm * factor, 0.0, 0.0)
    assert len(log.calls) == 2
    for _level, _msg, kwargs in log.calls:
        assert kwargs.get('throttle_duration_sec') == pytest.approx(10.0)


def test_clamp_message_names_the_factor(node):
    """Die Meldung nennt den Faktor — sonst ist sie nicht deutbar."""
    log = _FakeLogger()
    node.get_logger = lambda: log
    lm = node._engine.linear_max
    node._engine.set_command(lm * 8.0, 0.0, 0.0, 0.0)
    node._log_cmd_clamp(lm * 8.0, 0.0, 0.0)
    assert 'Faktor 0.12' in log.calls[0][1]


def test_warn_threshold_is_sane():
    """Die Schwelle muss ein echter Bruchteil sein (0 < x < 1)."""
    assert 0.0 < _CLAMP_WARN_FACTOR < 1.0
