"""
Tests für die Tempo-Presets (Block H2) — D-Pad ↑/↓ = Tempo-Cycle.

Tempo = NUR cycle_time (gait_node) + joy-Scales (envelope-frei, H2-Plan §0).
Zwei-Schritt-Protokoll: erst ``cycle_time`` am gait_node setzen
(AsyncParameterClient-Future); NUR bei Erfolg die eigenen Scales aus
``_TEMPO_MODES`` übernehmen. Der standing_only-Guard lebt allein im
gait_node — Ablehnung/Timeout ⇒ lokal ändert sich NICHTS (kein halber
Tempo-Wechsel). Der AsyncParameterClient wird durch Fakes ersetzt
(Future feuert den done-Callback synchron bzw. gar nicht für den
Timeout-Pfad).
"""

import os

from hexapod_teleop.joy_to_twist import (
    _TEMPO_DEFAULT_IDX,
    _TEMPO_MODES,
    JoyToTwist,
)
import pytest
from rcl_interfaces.msg import SetParametersResult
from rcl_interfaces.srv import SetParameters
import rclpy
import yaml

_CFG = os.path.join(os.path.dirname(__file__), '..', 'config')


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = JoyToTwist()
    yield n
    n.destroy_node()


class _FakeFuture:
    """Future-Ersatz: feuert den done-Callback sofort (oder nie)."""

    def __init__(self, successful=True, reason='', exc=None, respond=True):
        resp = SetParameters.Response()
        resp.results = [
            SetParametersResult(successful=successful, reason=reason)
        ]
        self._resp = resp
        self._exc = exc
        self._respond = respond

    def add_done_callback(self, cb):
        if self._respond:
            cb(self)

    def exception(self):
        return self._exc

    def result(self):
        return self._resp


class _FakeParamClient:
    """AsyncParameterClient-Ersatz: sammelt set_parameters-Aufrufe."""

    def __init__(self, ready=True, successful=True, reason='', exc=None,
                 respond=True):
        self._ready = ready
        self._successful = successful
        self._reason = reason
        self._exc = exc
        self._respond = respond
        self.calls = []

    def services_are_ready(self):
        return self._ready

    def set_parameters(self, params):
        self.calls.append({p.name: p.value for p in params})
        return _FakeFuture(self._successful, self._reason, self._exc,
                           self._respond)


def _scales(node):
    return (node._linear_x_scale, node._linear_y_scale,
            node._angular_z_scale)


# ----- Tabelle (Pin, Änderung nur bewusst nach H2.5-Tuning) ------------ #

def test_tempo_table_pinned():
    """Pinne die H2-Startwerte (finale Werte = Sim-Tuning H2.5)."""
    assert [tuple(m) for m in _TEMPO_MODES] == [
        ('langsam', 3.3, 0.03, 0.03, 0.28),
        ('mittel', 2.6, 0.04, 0.04, 0.35),
        ('schnell', 2.0, 0.05, 0.05, 0.46),
        ('aggressiv', 1.5, 0.17, 0.13, 1.2),
    ]
    assert _TEMPO_MODES[_TEMPO_DEFAULT_IDX].name == 'schnell'


def test_boot_is_jump_free(node):
    """
    Sprungfrei-Invariante: Boot-Scales == "schnell"-Tabelleneintrag.

    Der erste D-Pad-Druck darf keinen Verhaltens-Sprung erzeugen —
    YAML-Default-Scales und Tabellen-Boot-Eintrag müssen deckungsgleich
    sein (H2-Plan §1-B). cycle_time-Boot (gait_node-Default 2.0) ist
    per Tabellen-Pin oben abgedeckt.
    """
    boot = _TEMPO_MODES[_TEMPO_DEFAULT_IDX]
    assert node._tempo_idx == _TEMPO_DEFAULT_IDX
    assert _scales(node) == pytest.approx((
        boot.linear_x_scale, boot.linear_y_scale, boot.angular_z_scale))


@pytest.mark.parametrize('profile', ['ps4_usb.yaml', 'ps4_bt.yaml'])
def test_yaml_scales_match_boot_tempo(profile):
    """
    Sprungfrei-Invariante auch gegen die YAML-Profile.

    Zur Laufzeit kommen die Scales aus ps4_usb/bt.yaml (nicht aus den
    Code-Defaults) — weichen sie vom "schnell"-Tabelleneintrag ab, springt
    der erste D-Pad-Druck. Nach H2.5-Tuning beide Stellen nachziehen.
    """
    with open(os.path.join(_CFG, profile)) as f:
        params = yaml.safe_load(f)['joy_to_twist']['ros__parameters']
    boot = _TEMPO_MODES[_TEMPO_DEFAULT_IDX]
    assert params['linear_x_scale'] == pytest.approx(boot.linear_x_scale)
    assert params['linear_y_scale'] == pytest.approx(boot.linear_y_scale)
    assert params['angular_z_scale'] == pytest.approx(boot.angular_z_scale)


# ----- Erfolgs-Pfad: Cycle hoch/runter --------------------------------- #

def test_cycle_faster_sets_gait_and_scales(node):
    """↑ von schnell → aggressiv: cycle_time-Request + Scales + Sync."""
    fake = _FakeParamClient(successful=True)
    node._gait_param_client = fake
    node._cycle_tempo(True, now=100.0)
    aggressiv = _TEMPO_MODES[3]
    assert fake.calls == [{'cycle_time': aggressiv.cycle_time}]
    assert node._tempo_idx == 3
    assert _scales(node) == pytest.approx((0.17, 0.13, 1.2))
    # Eigener Param-Server synchron (Scales via validate-then-apply gesetzt).
    assert node.get_parameter('linear_x_scale').value == pytest.approx(0.17)
    assert not node._tempo_request_pending


def test_cycle_slower_sets_gait_and_scales(node):
    """↓ von schnell → mittel."""
    fake = _FakeParamClient(successful=True)
    node._gait_param_client = fake
    node._cycle_tempo(False, now=100.0)
    mittel = _TEMPO_MODES[1]
    assert fake.calls == [{'cycle_time': mittel.cycle_time}]
    assert node._tempo_idx == 1
    assert _scales(node) == pytest.approx((0.04, 0.04, 0.35))


def test_cycle_clamps_at_ends_without_request(node):
    """Am Tabellen-Ende: kein Request, Index bleibt (geklemmt, kein Wrap)."""
    fake = _FakeParamClient(successful=True)
    node._gait_param_client = fake
    node._cycle_tempo(True, now=100.0)   # schnell → aggressiv
    node._cycle_tempo(True, now=101.0)   # bereits am schnellsten
    assert len(fake.calls) == 1
    assert node._tempo_idx == 3


# ----- Reject-/Fehler-Pfade: lokal ändert sich NICHTS ------------------ #

def test_gait_reject_keeps_scales_and_index(node):
    """standing_only-Reject (nicht STANDING) → Scales+Index unverändert."""
    before = _scales(node)
    fake = _FakeParamClient(
        successful=False, reason='requires STATE_STANDING')
    node._gait_param_client = fake
    node._cycle_tempo(True, now=100.0)
    assert len(fake.calls) == 1          # Request ging raus
    assert node._tempo_idx == _TEMPO_DEFAULT_IDX
    assert _scales(node) == pytest.approx(before)
    assert not node._tempo_request_pending


def test_service_exception_keeps_scales(node):
    """Future-Exception (Service-Fehler) → unverändert, Lock gelöst."""
    before = _scales(node)
    node._gait_param_client = _FakeParamClient(exc=RuntimeError('boom'))
    node._cycle_tempo(True, now=100.0)
    assert node._tempo_idx == _TEMPO_DEFAULT_IDX
    assert _scales(node) == pytest.approx(before)
    assert not node._tempo_request_pending


def test_gait_node_absent_no_change(node):
    """Param-Services nicht ready (gait_node weg) → kein Request, nichts."""
    fake = _FakeParamClient(ready=False)
    node._gait_param_client = fake
    node._cycle_tempo(True, now=100.0)
    assert fake.calls == []
    assert node._tempo_idx == _TEMPO_DEFAULT_IDX


def test_pending_lock_and_timeout_release(node):
    """
    Ausbleibende Antwort: Lock blockt weitere Requests, Timeout löst ihn.

    gait_node stirbt zwischen ready-Check und Antwort → Future feuert nie.
    Innerhalb _TEMPO_REQUEST_TIMEOUT_S wird kein zweiter Request gesendet
    (kein Request-Stau); danach gibt der Timeout den Cycle wieder frei —
    geändert wurde die ganze Zeit nichts.
    """
    before = _scales(node)
    fake = _FakeParamClient(respond=False)
    node._gait_param_client = fake
    node._cycle_tempo(True, now=100.0)
    assert len(fake.calls) == 1
    assert node._tempo_request_pending
    node._cycle_tempo(True, now=100.5)   # < Timeout → geblockt
    assert len(fake.calls) == 1
    node._cycle_tempo(True, now=103.0)   # > Timeout → Lock gelöst, neuer Cycle
    assert len(fake.calls) == 2
    assert node._tempo_idx == _TEMPO_DEFAULT_IDX  # nie eine Antwort → alt
    assert _scales(node) == pytest.approx(before)
