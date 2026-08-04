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
from std_srvs.srv import SetBool
import yaml

try:
    # Block I Phase 11: die Auslegungs-Invarianten koppeln die Tempo-Tabelle
    # an die Stance-Deckel (der Deckel wirkt nur, wenn Skala × Bodenzeit ihn
    # freigibt). Reiner test_depend — zur Laufzeit hängt das Teleop nicht am
    # gait-Paket. Fehlt es (out-of-tree-Build), werden die Pins übersprungen.
    from hexapod_gait.gait_node import (
        _CLAMP_WARN_FACTOR,
        _GAIT_PARAMS,
        _STANCE_DEFAULT_IDX,
        _STANCE_MODES,
    )
    from hexapod_gait.gait_patterns import GAIT_PRESETS
    _GAIT_AVAILABLE = True
except ImportError:                                   # pragma: no cover
    _GAIT_AVAILABLE = False

_requires_gait = pytest.mark.skipif(
    not _GAIT_AVAILABLE, reason='hexapod_gait nicht im Pfad')

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
    """
    Pinne die Phase-11-Startwerte (finale Werte = Sim-Tuning P11.6).

    Auslegung „Geschwindigkeit halten, Schritte länger": die Scales
    bleiben wie gehabt, die Zykluszeiten sind verlängert, damit der Fuß
    länger am Boden bleibt und derselbe Vortrieb in längeren Schritten
    passiert (schnell: 0.050 m/s × 1.7 s = 0.085 m = mittel-Deckel).
    „aggressiv" ist gebremst, damit der angehobene Stance-Deckel die
    Stufe nicht ungewollt schneller macht.
    """
    assert [tuple(m) for m in _TEMPO_MODES] == [
        ('langsam', 4.0, 0.03, 0.03, 0.28),
        ('mittel', 3.6, 0.04, 0.04, 0.35),
        ('schnell', 3.4, 0.05, 0.05, 0.46),
        ('aggressiv', 1.7, 0.10, 0.09, 0.95),
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
    assert _scales(node) == pytest.approx((
        aggressiv.linear_x_scale,
        aggressiv.linear_y_scale,
        aggressiv.angular_z_scale,
    ))
    # Eigener Param-Server synchron (Scales via validate-then-apply gesetzt).
    assert node.get_parameter('linear_x_scale').value == pytest.approx(
        aggressiv.linear_x_scale)
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


# ----- Block I Phase 5: /hexapod_cycle_tempo (Tempo-Dropdown-Setz-Weg) ----- #

def test_cycle_tempo_returns_true_when_initiated(node):
    """Erfolgreicher Cycle gibt True (Request raus, idx folgt der Antwort)."""
    node._gait_param_client = _FakeParamClient(ready=True, successful=True)
    assert node._cycle_tempo(True, now=100.0) is True   # schnell → aggressiv
    assert node._tempo_idx == 3


def test_cycle_tempo_returns_true_at_limit(node):
    """Am Limit ist ein weiterer Cycle ein No-op (True, kein Fehler)."""
    node._gait_param_client = _FakeParamClient(ready=True, successful=True)
    node._cycle_tempo(True, now=100.0)                  # → aggressiv (idx 3)
    assert node._tempo_idx == 3
    assert node._cycle_tempo(True, now=101.0) is True   # bereits am schnellsten
    assert node._tempo_idx == 3


def test_cycle_tempo_returns_false_when_services_down(node):
    """gait-Param-Services nicht bereit → blockiert (False)."""
    node._gait_param_client = _FakeParamClient(ready=False)
    assert node._cycle_tempo(True, now=100.0) is False


def test_cycle_tempo_returns_false_when_pending(node):
    """Zweiter Cycle während einer laufenden Anfrage → blockiert (False)."""
    node._gait_param_client = _FakeParamClient(respond=False)
    assert node._cycle_tempo(True, now=100.0) is True    # erster Request raus
    assert node._cycle_tempo(True, now=100.5) is False   # pending < Timeout


def test_service_cycle_tempo_maps_return_to_success(node):
    """Der SetBool-Service spiegelt den _cycle_tempo-Return auf success."""
    node._gait_param_client = _FakeParamClient(ready=True, successful=True)
    resp = node._on_cycle_tempo(SetBool.Request(data=True), SetBool.Response())
    assert resp.success is True
    assert 'schneller' in resp.message
    node._gait_param_client = _FakeParamClient(ready=False)
    resp2 = node._on_cycle_tempo(SetBool.Request(data=False), SetBool.Response())
    assert resp2.success is False


# ===== Block I Phase 11 — Auslegungs-Invarianten ========================
#
# Die real gefahrene Schrittweite ist
#     s = min(scale, linear_max) × T_stance,
#     T_stance = cycle_time × (1 − swing_duty),
#     linear_max = step_length_max / T_stance.
# Diese Pins halten die Auslegung fest, damit niemand die Tabelle
# unbemerkt zurück in den 50-mm-Zustand dreht.

_SWING_DUTY_TRIPOD = 0.5

# Effektive Fahrgeschwindigkeit je Stufe VOR Phase 11 (cycle_time/Skala von
# damals, mittel-Deckel 0.080) — Referenz für „keine Stufe wird schneller".
_V_BEFORE_PHASE11 = {
    'langsam': 0.030,
    'mittel': 0.040,
    'schnell': 0.050,
    'aggressiv': 0.080 / (1.5 * _SWING_DUTY_TRIPOD),   # Engine-Clamp: 0.1067
}


def _stance_duration(cycle_time):
    return cycle_time * (1.0 - _SWING_DUTY_TRIPOD)


def _effective_speed(mode, cap):
    """min(Stick-Skala, linear_max) — was real gefahren wird."""
    return min(mode.linear_x_scale, cap / _stance_duration(mode.cycle_time))


@_requires_gait
def test_boot_cycle_time_matches_gait_default():
    """
    Zweite Sprung-Quelle: Boot-Stufe == gait_node-`cycle_time`-Default.

    Der Tempo-Wechsel setzt `cycle_time` am gait_node. Stimmte der
    Tabellenwert der Boot-Stufe nicht mit dem Node-Default überein,
    würde der erste Tempo-Wechsel die Zykluszeit springen lassen.
    """
    spec = next(s for s in _GAIT_PARAMS if s.name == 'cycle_time')
    assert spec.default == pytest.approx(
        _TEMPO_MODES[_TEMPO_DEFAULT_IDX].cycle_time)


@_requires_gait
def test_boot_tempo_exhausts_boot_stance_cap():
    """
    Ausschöpfungs-Pin: die Boot-Stufe erreicht den Boot-Stance-Deckel.

    Das ist der Kern von Phase 11 — vorher klemmte die Skala bei 50 mm,
    obwohl der Deckel 80 mm erlaubt hätte. Rutscht dieser Test, ist der
    Schrittweiten-Gewinn wieder weg.
    """
    boot = _TEMPO_MODES[_TEMPO_DEFAULT_IDX]
    cap = _STANCE_MODES[_STANCE_DEFAULT_IDX].step_length_max
    stride = boot.linear_x_scale * _stance_duration(boot.cycle_time)
    assert stride == pytest.approx(cap, abs=0.005), (
        f'Boot-Stufe faehrt {stride * 1000:.0f} mm, Deckel erlaubt '
        f'{cap * 1000:.0f} mm — Auslegung gebrochen')


@_requires_gait
def test_no_tempo_step_got_faster():
    """
    User-Vorgabe: längere Schritte, aber **keine** Stufe schneller.

    Der angehobene Stance-Deckel hebt sonst den Engine-Clamp mit —
    genau deshalb ist „aggressiv" gebremst.
    """
    cap = _STANCE_MODES[_STANCE_DEFAULT_IDX].step_length_max
    for mode in _TEMPO_MODES:
        v_new = _effective_speed(mode, cap)
        assert v_new <= _V_BEFORE_PHASE11[mode.name] + 1e-9, (
            f'{mode.name}: {v_new:.4f} m/s > vorher '
            f'{_V_BEFORE_PHASE11[mode.name]:.4f} m/s')


@_requires_gait
def test_no_designed_operating_point_triggers_a_clamp_warning():
    """
    Kein ausgelegter Betriebspunkt darf eine Clamp-WARN erzeugen.

    Seit der Tempo-Auslegung liegt die Stick-Skala in vielen Kombinationen
    über `linear_max` — der Clamp ist dort **Normalbetrieb**. Würde der
    Node ihn als WARN melden, liefe die App-Alert-Liste
    (`/hexapod/alerts` ← `/rosout` WARN+) im Fahren voll und echte
    Warnungen gingen unter.

    Geprüft werden alle 4 Gangarten × 4 Tempo-Stufen × 3 Stance-Modi.
    Der kleinste reguläre Faktor (wave + schnell + hoch) muss mit Abstand
    über `_CLAMP_WARN_FACTOR` liegen.
    """
    worst = 1.0
    for gait in ('tripod', 'wave', 'tetrapod', 'ripple'):
        swing_duty = GAIT_PRESETS[gait].swing_duty
        for mode in _TEMPO_MODES:
            t_stance = mode.cycle_time * (1.0 - swing_duty)
            for stance in _STANCE_MODES:
                linear_max = stance.step_length_max / t_stance
                factor = min(1.0, linear_max / mode.linear_x_scale)
                worst = min(worst, factor)
                assert factor > _CLAMP_WARN_FACTOR, (
                    f'{gait}/{mode.name}/{stance.name}: Clamp-Faktor '
                    f'{factor:.2f} <= Schwelle {_CLAMP_WARN_FACTOR} → '
                    f'WARN im Normalbetrieb')
    # Sanity: die Schwelle darf nicht so tief liegen, dass sie nie greift.
    assert _CLAMP_WARN_FACTOR > worst / 2.0, (
        f'Schwelle {_CLAMP_WARN_FACTOR} ist gegenüber dem regulären '
        f'Worst-Case {worst:.2f} zu konservativ — sie meldet dann nichts mehr')


@_requires_gait
def test_tempo_monotonic_in_every_stance_mode():
    """
    Bedien-Logik: „schneller" muss in **jedem** Stance-Modus schneller sein.

    In den Modi mit kleinem Deckel begrenzt `linear_max` statt der Skala —
    eine unbedachte Zykluszeit könnte „schnell" dort langsamer machen als
    „mittel". Das wäre für den Nutzer nicht nachvollziehbar.
    """
    for stance in _STANCE_MODES:
        speeds = [
            _effective_speed(m, stance.step_length_max) for m in _TEMPO_MODES
        ]
        assert speeds == sorted(speeds), (
            f'{stance.name}: Tempo-Stufen nicht monoton — {speeds}')
        assert len(set(speeds)) == len(speeds), (
            f'{stance.name}: zwei Stufen gleich schnell — {speeds}')
