"""
Freeze-Guard für die Sequenz-Services (Block I Phase 9, [D-Feld-9]).

**Der Befund, der dazu führte** (aus der App-Integration): ``_tick`` steigt bei
``_safety_frozen`` als erste Zeile aus — es wird keine Trajektorie mehr
publisht. Die Sequenz-Services prüften aber nur den Engine-**State**, und der
ist im Freeze unverändert (der Freeze gated den Tick, nicht den State). Ein
``sit_down`` bei aktivem E-Stop meldete deshalb ``success=true``, die Engine
wechselte intern auf REPOSITION — und dann passierte **nichts**. Ein Aufrufer,
der auf ``state == SAT`` wartet (die App tut das vor einem Stack-Neustart),
wartete ewig und stoppte danach hart, sodass der Roboter zusammensackt.

Diese Tests pinnen die Korrektur: **ein Service, der Erfolg meldet, ist auch
wirklich erfolgreich** — im Freeze wird mit Klartext-Grund abgelehnt.

Ebenso wichtig ist die Gegenrichtung: der **Ausweg** darf nie zu sein. ``estop``
und ``recover`` bleiben im Freeze erreichbar, und nach ``recover`` funktionieren
die Sequenz-Services wieder.

Strategie wie test_show_node/test_sitdown_node: GaitNode direkt instanziieren,
Handler als Methoden aufrufen (kein Executor-Roundtrip).
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
import pytest
import rclpy
from std_srvs.srv import SetBool, Trigger


_LEGS = ('leg_1', 'leg_2', 'leg_3', 'leg_4', 'leg_5', 'leg_6')


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    # Roboter „steht": erstes /joint_states empfangen, Pose vollständig.
    n._ramp_triggered = True
    n._latest_joints = {leg: (0.0, 0.0, 0.0) for leg in _LEGS}
    n._engine._state = GaitEngine.STATE_STANDING
    yield n
    n.destroy_node()


def _trigger(handler):
    return handler(Trigger.Request(), Trigger.Response())


def _setbool(handler, data):
    req = SetBool.Request()
    req.data = data
    return handler(req, SetBool.Response())


# Alle Handler, die eine Engine-SEQUENZ starten → müssen im Freeze ablehnen.
_SEQUENCE_SERVICES = (
    ('sit_down', lambda n: _trigger(n._on_sit_down)),
    ('stand_up', lambda n: _trigger(n._on_stand_up)),
    ('shutdown', lambda n: _trigger(n._on_shutdown)),
    ('cycle_stance', lambda n: _setbool(n._on_cycle_stance, True)),
    ('show_toggle', lambda n: _trigger(n._on_show_toggle)),
)


@pytest.mark.parametrize('name,call', _SEQUENCE_SERVICES)
def test_sequence_service_rejects_while_frozen(node, name, call):
    """
    T9.15: bei aktivem Freeze lehnt jeder Sequenz-Starter ab — mit Grund.

    Vor dem Fix meldeten sie `success=true` und taten nichts.
    """
    node._safety_frozen = True
    response = call(node)
    assert response.success is False, f'{name} meldet Erfolg trotz Freeze'
    assert 'frozen' in response.message, response.message
    assert '/hexapod_recover' in response.message, (
        f'{name}: der Reject nennt den Ausweg nicht'
    )


@pytest.mark.parametrize('name,call', _SEQUENCE_SERVICES)
def test_sequence_service_does_not_touch_engine_while_frozen(node, name, call):
    """
    Der Reject darf den Engine-State **nicht** verändern.

    Sonst stünde die Engine (wie vor dem Fix) in einer halb gestarteten Sequenz,
    die nie läuft — und ein späteres `recover` würde sie stillschweigend
    überschreiben.
    """
    node._safety_frozen = True
    call(node)
    assert node._engine.state == GaitEngine.STATE_STANDING, (
        f'{name} hat den Engine-State trotz Freeze verändert'
    )


def test_sitdown_does_not_arm_relay_off_while_frozen(node):
    """
    Der abgelehnte Shutdown darf das Relay-Aus nicht scharf schalten.

    `_relay_off_after_sat` würde sonst beim nächsten (recoverten) SAT feuern —
    ein Shutdown, den niemand mehr angefordert hat.
    """
    node._safety_frozen = True
    _trigger(node._on_shutdown)
    assert node._relay_off_after_sat is False


# ----- Der Ausweg muss immer offen sein -------------------------------- #

def test_estop_works_while_frozen(node):
    """T9.16: der Not-Halt bleibt idempotent aufrufbar."""
    node._safety_frozen = True
    response = _trigger(node._on_estop)
    assert response.success is True
    assert node._safety_frozen is True


def test_recover_works_while_frozen(node):
    """T9.16: Recovery ist der einzige Ausweg — nie gegated."""
    node._safety_frozen = True
    response = _trigger(node._on_recover)
    assert response.success is True, response.message
    assert node._safety_frozen is False
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_sequence_services_work_again_after_recover(node):
    """
    Nach dem Recover greift der Guard nicht mehr.

    Prüft den kompletten Weg, den die App fährt: Freeze → Reject → Recover →
    Sequenz startet wieder.
    """
    node._safety_frozen = True
    assert _trigger(node._on_sit_down).success is False

    assert _trigger(node._on_recover).success is True
    # Nach der Recovery-Ramp ist der Roboter wieder im Stand.
    node._engine._state = GaitEngine.STATE_STANDING

    response = _trigger(node._on_sit_down)
    assert response.success is True, response.message
    assert node._engine.state != GaitEngine.STATE_STANDING, (
        'Hinsetz-Sequenz wurde nicht gestartet'
    )


# ----- Reine Werte-Setzer bleiben offen (keine Sequenz) ---------------- #

def test_cycle_gait_not_gated_while_frozen(node):
    """
    `cycle_gait` setzt nur ein Pattern — keine Bewegung, kein Guard nötig.

    Der Wechsel wirkt erst beim nächsten Laufen; ihn im Freeze zu blockieren
    wäre unnötige Bevormundung.
    """
    node._safety_frozen = True
    response = _setbool(node._on_cycle_gait, True)
    assert response.success is True


def test_adjust_step_length_not_gated_while_frozen(node):
    """`adjust_step_length` ist ein reiner Wert — kein Guard."""
    node._safety_frozen = True
    response = _setbool(node._on_adjust_step_length, False)
    assert response.success is True


def test_show_mode_none_still_allowed_while_frozen(node):
    """
    Der Phase-8-Rückweg bleibt offen: `show_mode='none'` ist immer erlaubt.

    (Der Show-START ist bei Freeze schon seit Phase 8 gegated — hier geht es um
    das Verlassen, das nie blockiert werden darf.)
    """
    from rclpy.parameter import Parameter

    node._safety_frozen = True
    result = node.set_parameters_atomically([
        Parameter('show_mode', Parameter.Type.STRING, 'none'),
    ])
    assert result.successful, result.reason


# ----- Die Zusage, auf die sich die App verlässt ------------------------ #

def _status_payload(node):
    """Einmal `_publish_status` auslösen und das JSON zurückgeben."""
    import json
    captured = []
    node._status_pub.publish = lambda msg: captured.append(msg)
    node._publish_status()
    return json.loads(captured[-1].data)


def test_status_reports_safety_frozen_while_frozen(node):
    """
    `/hexapod/status.safety_frozen` ist während des Freeze **true**.

    Die App wertet das seit Contract v0.13.2 als **primäres** Signal aus (statt
    den Reject-Wortlaut zu parsen) und bricht ihren sit_down-Retry sofort ab.
    Ginge das Feld verloren, liefe sie wieder 15 s ins Leere und stoppte hart —
    der Roboter sackt zusammen. Deshalb hier gepinnt.
    """
    assert _status_payload(node)['safety_frozen'] is False
    _trigger(node._on_estop)
    assert _status_payload(node)['safety_frozen'] is True


def test_status_keeps_publishing_while_frozen(node):
    """
    Der Status-Timer läuft im Freeze **weiter** — er hängt nicht am gait-Tick.

    `_tick` steigt bei `_safety_frozen` sofort aus; `_publish_status` läuft auf
    einem eigenen 5-Hz-Timer. Würde jemand das zusammenlegen, verstummte der
    Status genau dann, wenn die App ihn am dringendsten braucht (E-Stop-Anzeige,
    Recover-Button, Restart-Entscheidung).
    """
    _trigger(node._on_estop)
    first = _status_payload(node)
    second = _status_payload(node)
    assert first['safety_frozen'] is True
    assert second['safety_frozen'] is True, 'Status verstummt im Freeze'
    assert second['state'] == first['state']


def test_status_clears_safety_frozen_after_recover(node):
    """Nach `recover` meldet der Status wieder `safety_frozen: false`."""
    _trigger(node._on_estop)
    assert _status_payload(node)['safety_frozen'] is True
    _trigger(node._on_recover)
    assert _status_payload(node)['safety_frozen'] is False
