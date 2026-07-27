"""
Block-I-Phase-8-Glue-Tests für gait_node: show_mode + /cmd_body_pose.

Strategie (wie test_show_node.py / test_sitdown_node.py): GaitNode direkt
instanziieren, Handler als Methoden aufrufen (kein Executor-Roundtrip); der
Engine-State wird für Guard-Tests direkt gesetzt.

Deckt:
  - T8.5  show_mode-Übergänge (look_around → BODY_POSE, none → zurück) und die
          Platzhalter dancing/free_leg (akzeptiert, no-op, bleiben bei none)
  - T8.6  Gate: Show-Modi nur aus STANDING, **'none' immer** (Rückweg!)
  - T8.3  /cmd_body_pose → skalierte DOF an die Engine (inkl. Staleness → 0)
  - T8.12 Status-Feld show_mode + serverseitiger Reset (Recovery)
"""

import json
import math
import time

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
import pytest
import rclpy
from rclpy.parameter import Parameter
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import Trigger


_BODY_POSE_PARAMS = (
    'body_pose_dx_max', 'body_pose_dy_max', 'body_pose_dz_max',
    'body_pose_roll_max_deg', 'body_pose_pitch_max_deg',
    'body_pose_yaw_max_deg', 'body_pose_rate_lin', 'body_pose_rate_ang_dps',
)


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    # Der Show-Start verlangt einen Roboter, der wirklich steht: erstes
    # /joint_states empfangen (_ramp_triggered) und kein aktiver Freeze. Im
    # echten Betrieb ist beides beim ersten STANDING gegeben; hier setzen wir
    # es, weil kein Executor läuft. Die beiden Guard-Tests am Ende der Datei
    # setzen es bewusst zurück.
    n._ramp_triggered = True
    yield n
    n.destroy_node()


def _set_show_mode(node, value):
    """show_mode über den echten Param-Pfad setzen (Validator + apply)."""
    return node.set_parameters_atomically([
        Parameter('show_mode', Parameter.Type.STRING, value),
    ])


def _publish_body_pose(node, values):
    msg = Float64MultiArray()
    msg.data = list(values)
    node._on_cmd_body_pose(msg)


# ----- Params ----------------------------------------------------------- #

def test_body_pose_params_have_range(node):
    """Alle Envelope-/Raten-Params haben FloatingPointRange (rqt-Slider)."""
    for name in _BODY_POSE_PARAMS:
        fr = node.describe_parameter(name).floating_point_range
        assert len(fr) == 1, f'{name} fehlt FloatingPointRange'


def test_envelope_defaults_match_tool(node):
    """
    Die Envelope-Defaults sind die vom Tool belegten Werte (Plan §4.4).

    Pinnt die Zahlen: wer sie ändert, muss ``look_around_envelope_check.py``
    erneut laufen lassen (Gate 1-3 GREEN) — sonst ist der Envelope-Beleg
    wertlos.
    """
    assert node.get_parameter('body_pose_dx_max').value == pytest.approx(0.050)
    assert node.get_parameter('body_pose_dy_max').value == pytest.approx(0.035)
    assert node.get_parameter('body_pose_dz_max').value == pytest.approx(0.020)
    assert node.get_parameter('body_pose_roll_max_deg').value == pytest.approx(0.0)
    assert node.get_parameter('body_pose_pitch_max_deg').value == pytest.approx(12.0)
    assert node.get_parameter('body_pose_yaw_max_deg').value == pytest.approx(10.0)


def test_show_mode_not_in_standing_only(node):
    """
    show_mode ist bewusst NICHT in der generischen standing_only-Liste.

    Sonst würde der Check auch 'none' im BODY_POSE ablehnen → die App käme aus
    der Show nicht mehr heraus ([D-Show-6a], Plan §4.1).
    """
    from hexapod_gait.gait_node import _STANDING_ONLY_PARAMS
    assert 'show_mode' not in _STANDING_ONLY_PARAMS


def test_show_mode_default_is_none(node):
    """Boot-Default = Normalbetrieb (keine Show ohne App-Aktion)."""
    assert node.get_parameter('show_mode').value == 'none'
    assert node._show_mode == 'none'


# ----- T8.5 Übergänge + Platzhalter ------------------------------------- #

def test_look_around_enters_body_pose(node):
    """T8.5: show_mode=look_around → Engine in STATE_BODY_POSE."""
    node._engine._state = GaitEngine.STATE_STANDING
    result = _set_show_mode(node, 'look_around')
    assert result.successful, result.reason
    assert node._engine.state == GaitEngine.STATE_BODY_POSE
    assert node._show_mode == 'look_around'


def test_none_leaves_body_pose(node):
    """T8.5: show_mode=none → Return-to-Origin, danach STANDING."""
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    result = _set_show_mode(node, 'none')
    assert result.successful, result.reason
    assert node._show_mode == 'none'
    # Der Exit läuft über den Rate-Limiter — nach genug Ticks ist er durch.
    t = time.monotonic() - node._t_start
    for _ in range(1000):
        t += 0.02
        node._engine.compute_joint_angles(t)
        if node._engine.state == GaitEngine.STATE_STANDING:
            break
    assert node._engine.state == GaitEngine.STATE_STANDING


@pytest.mark.parametrize('mode', ('dancing', 'free_leg'))
def test_placeholder_modes_are_accepted_but_noop(node, mode):
    """
    T8.5: dancing/free_leg werden **akzeptiert**, tun aber nichts.

    Das ist der App-Vorbau ([D-Show-5]): das Show-Menü kann alle vier Einträge
    schon senden; der Roboter bleibt STANDING und meldet wirksam 'none'.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    result = _set_show_mode(node, mode)
    assert result.successful, result.reason
    assert node._engine.state == GaitEngine.STATE_STANDING
    assert node._show_mode == 'none'
    assert node._pending_show_mode_sync, 'Param-Server-Sync nicht angefordert'


def test_show_to_show_switch_requires_none_first(node):
    """
    Direkter Show-zu-Show-Wechsel wird abgelehnt — der Weg führt über 'none'.

    Bewusste v1-Regel (§4.6): „Show-Modi nur aus STANDING" bleibt damit auch
    gültig, wenn Dancing später echt wird (ein direkter Wechsel bräuchte sonst
    eine Zwischensequenz „erst zurückfedern, dann neue Show"). Die App macht
    zwei Schritte: none → warten bis STANDING → neue Show.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    assert node._engine.state == GaitEngine.STATE_BODY_POSE

    result = _set_show_mode(node, 'dancing')
    assert not result.successful
    assert 'STANDING' in result.reason
    assert 'none' in result.reason, 'Reject-Grund nennt den Rückweg nicht'
    assert node._show_mode == 'look_around', 'Show wurde ungewollt verlassen'

    # Weg über none: verlassen, zurückfedern, dann ist der Wechsel möglich.
    assert _set_show_mode(node, 'none').successful
    t = time.monotonic() - node._t_start
    for _ in range(1000):
        t += 0.02
        node._engine.compute_joint_angles(t)
        if node._engine.state == GaitEngine.STATE_STANDING:
            break
    assert node._engine.state == GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'dancing').successful


def test_unknown_show_mode_rejected(node):
    """Unbekannte Werte werden mit Klartext-Grund abgelehnt."""
    result = _set_show_mode(node, 'breakdance')
    assert not result.successful
    assert 'show_mode' in result.reason


# ----- T8.6 Gate -------------------------------------------------------- #

def test_show_mode_requires_standing(node):
    """T8.6: Show-Modi außerhalb STANDING abgelehnt (mit Grund)."""
    node._engine._state = GaitEngine.STATE_WALKING
    result = _set_show_mode(node, 'look_around')
    assert not result.successful
    assert 'STANDING' in result.reason
    assert node._show_mode == 'none'


def test_none_always_allowed_even_in_body_pose(node):
    """
    T8.6 (der wichtige Teil): 'none' wird IMMER akzeptiert.

    Im BODY_POSE ist der State nicht STANDING — würde das Gate hier greifen,
    säße die App in der Show fest (Plan §4.1).
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    assert node._engine.state == GaitEngine.STATE_BODY_POSE
    result = _set_show_mode(node, 'none')
    assert result.successful, result.reason


def test_none_allowed_in_any_state(node):
    """'none' ist auch aus WALKING/SAT heraus setzbar (No-op, kein Reject)."""
    for state in (GaitEngine.STATE_WALKING, GaitEngine.STATE_SAT,
                  GaitEngine.STATE_STARTUP_RAMP):
        node._engine._state = state
        assert _set_show_mode(node, 'none').successful


# ----- T8.3 /cmd_body_pose ---------------------------------------------- #

def test_cmd_body_pose_scales_to_envelope(node):
    """
    T8.3: normierte Stick-Werte → Meter/Radiant mit den Envelope-Params.

    Volle Auslenkung auf allen Achsen ⇒ Ziel-DOF = exakt die Envelope-Grenzen
    (das Klemmen auf das kinematisch Mögliche macht danach die Engine).
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    _publish_body_pose(node, [1.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    node._update_body_pose(time.monotonic())
    target = node._engine._body_pose_target
    assert target[0] == pytest.approx(0.050)
    assert target[1] == pytest.approx(0.035)
    assert target[2] == pytest.approx(0.020)
    assert target[3] == pytest.approx(0.0)
    assert target[4] == pytest.approx(math.radians(12.0))
    assert target[5] == pytest.approx(math.radians(10.0))


def test_cmd_body_pose_negative_and_clamped(node):
    """Werte jenseits [-1,1] werden auf die Envelope-Grenze geklemmt."""
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    _publish_body_pose(node, [-3.0, 0.5, -2.0, 0.0, -1.5, 0.0])
    node._update_body_pose(time.monotonic())
    target = node._engine._body_pose_target
    assert target[0] == pytest.approx(-0.050)
    assert target[1] == pytest.approx(0.0175)
    assert target[2] == pytest.approx(-0.020)
    assert target[4] == pytest.approx(-math.radians(12.0))


def test_cmd_body_pose_staleness_returns_to_zero(node):
    """
    T8.3: ohne frisches /cmd_body_pose (> cmd_vel_timeout) → Ziel 0.

    Disconnect-Schutz: der Körper federt in die Ausgangs-Pose zurück, statt in
    einer Extrem-Pose zu verharren.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    _publish_body_pose(node, [1.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    now = time.monotonic()
    node._update_body_pose(now)
    assert node._engine._body_pose_target[0] == pytest.approx(0.050)
    # Uhr über den Timeout hinaus vorstellen.
    node._update_body_pose(now + node._cmd_vel_timeout + 1.0)
    assert node._engine._body_pose_target == (0.0,) * 6


def test_cmd_body_pose_ignores_short_array(node):
    """Malformed (< 6 Werte) wird ignoriert — kein State-Change."""
    node._cmd_body_pose = [0.1] * 6
    msg = Float64MultiArray()
    msg.data = [1.0, 2.0]
    node._on_cmd_body_pose(msg)
    assert node._cmd_body_pose == [0.1] * 6


def test_cmd_body_pose_ignored_outside_show(node):
    """
    Der Teleop publisht immer — außerhalb der Show darf das nichts bewirken.

    (Das ist die Grundlage dafür, dass /cmd_body_pose in beiden Profilen laufen
    kann, ohne dass ein Controller die Show erreicht.)
    """
    node._engine._state = GaitEngine.STATE_STANDING
    _publish_body_pose(node, [1.0, 1.0, 1.0, 0.0, 1.0, 1.0])
    node._engine.set_body_pose_target((0.05, 0.0, 0.0, 0.0, 0.0, 0.0))
    assert node._engine._body_pose_target == (0.0,) * 6
    assert node._engine.state == GaitEngine.STATE_STANDING


# ----- T8.12 Status + Reset --------------------------------------------- #

def test_status_carries_show_mode(node):
    """T8.12: /hexapod/status trägt show_mode + state=BODY_POSE."""
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    published = []
    node._status_pub.publish = lambda msg: published.append(msg)
    node._publish_status()
    payload = json.loads(published[-1].data)
    assert payload['show_mode'] == 'look_around'
    assert payload['state'] == GaitEngine.STATE_BODY_POSE


def test_recover_resets_show_mode(node):
    """
    T8.12: Recovery beendet die Show serverseitig (Param + Status folgen).

    Sonst stünde das App-Menü auf „Kamera-Umschauen", während der Roboter längst
    in den Stand zurückrampt.
    """
    node._latest_joints = {
        leg: (0.0, 0.0, 0.0)
        for leg in ('leg_1', 'leg_2', 'leg_3', 'leg_4', 'leg_5', 'leg_6')
    }
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    assert node._show_mode == 'look_around'

    response = node._on_recover(Trigger.Request(), Trigger.Response())
    assert response.success, response.message
    assert node._show_mode == 'none'
    assert node._pending_show_mode_sync
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP


def test_sync_heals_stale_show_mode(node):
    """
    Selbstheilung bei einem Show-Ende ohne Param-Set.

    Verlässt die Engine den BODY_POSE anders als über show_mode, zieht der Sync
    nach (fängt jeden künftigen Pfad ab).
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    node._engine._state = GaitEngine.STATE_STANDING   # „von außen" verlassen
    node._maybe_sync_show_mode()
    assert node._show_mode == 'none'
    assert node.get_parameter('show_mode').value == 'none'


def test_placeholder_sync_writes_none_to_param_server(node):
    """Nach einem Platzhalter-Set steht am Param-Server wieder 'none'."""
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'dancing').successful
    node._maybe_sync_show_mode()
    assert node.get_parameter('show_mode').value == 'none'
    assert node._show_mode == 'none'


def test_sit_down_rejected_during_show(node):
    """
    v1-Entscheidung (§4.6): Hinsetzen aus der Show wird mit Grund abgelehnt.

    Die App setzt erst show_mode=none. E-Stop bleibt davon unberührt.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    response = node._on_sit_down(Trigger.Request(), Trigger.Response())
    assert not response.success
    assert GaitEngine.STATE_BODY_POSE in response.message


def test_estop_works_during_show(node):
    """E-Stop muss aus jedem State greifen — auch mitten in der Show."""
    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    response = node._on_estop(Trigger.Request(), Trigger.Response())
    assert response.success
    assert node._safety_frozen


def test_show_rejected_while_frozen(node):
    """
    Show-Start bei aktivem Freeze wird abgelehnt (Self-Review-Fund).

    Der Tick ist nach einem E-Stop gated — die Show würde „starten", sich aber
    nicht bewegen. Die App zeigte dann eine laufende Show, die keine ist.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    node._safety_frozen = True
    result = _set_show_mode(node, 'look_around')
    assert not result.successful
    assert 'frozen' in result.reason
    assert node._engine.state == GaitEngine.STATE_STANDING
    # Nach Recovery geht es wieder (hier: Freeze von Hand lösen).
    node._safety_frozen = False
    assert _set_show_mode(node, 'look_around').successful


def test_show_rejected_before_first_joint_states(node):
    """
    Show-Start vor dem ersten /joint_states wird abgelehnt (Self-Review-Fund).

    STANDING ist zu diesem Zeitpunkt nur der Engine-Default — der Roboter liegt
    noch auf dem Bauch. Das folgende Aufstehen würde die Show sofort wieder
    überschreiben.
    """
    node._engine._state = GaitEngine.STATE_STANDING
    node._ramp_triggered = False
    result = _set_show_mode(node, 'look_around')
    assert not result.successful
    assert 'stood up' in result.reason


def test_body_pose_step_capped_after_tick_gap(node):
    """
    Ein Tick-Aussetzer führt nicht zu einem Sprung in einem Tick.

    Der Nachführ-Schritt ist auf _BODY_POSE_MAX_DT gedeckelt: nach 5 s Pause
    darf höchstens der Weg von 0.1 s zurückgelegt werden.
    """
    from hexapod_gait.gait_engine import _BODY_POSE_MAX_DT

    node._engine._state = GaitEngine.STATE_STANDING
    assert _set_show_mode(node, 'look_around').successful
    engine = node._engine
    t = 0.0
    engine._body_pose_last_t = t
    engine.set_body_pose_target((0.05, 0.0, 0.0, 0.0, 0.0, 0.0))
    engine.compute_joint_angles(t + 5.0)     # 5 s „Aussetzer"
    assert engine.body_pose[0] <= engine.body_pose_rate_lin * _BODY_POSE_MAX_DT + 1e-9
