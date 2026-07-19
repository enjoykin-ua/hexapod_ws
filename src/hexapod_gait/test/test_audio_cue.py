"""
Block I Phase 7A — gait_node Audio-Cue-Emit-Tests.

Prüft, dass der gait_node an den Sequenz-Startpunkten den richtigen Cue auf
``/hexapod/audio_cue`` feuert (standup/sitdown/reposition/freeze) und dass
**Recovery bewusst stumm** ist (kein Cue). Strategie wie test_sitdown_node.py:
GaitNode direkt instanziieren, Handler aufrufen, den Cue-Publisher spyen.
"""

from unittest.mock import MagicMock

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
from hexapod_kinematics import HEXAPOD
import pytest
import rclpy
from std_srvs.srv import SetBool, Trigger


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    n._audio_cue_pub.publish = MagicMock()   # Cue-Publisher spyen
    yield n
    n.destroy_node()


def _rad0_joints():
    return {leg.name: (0.0, 0.0, 0.0) for leg in HEXAPOD.legs}


def _cues(node):
    """Alle bisher gefeuerten Cue-Namen (in Reihenfolge)."""
    return [c.args[0].data for c in node._audio_cue_pub.publish.call_args_list]


def _trigger(handler):
    return handler(Trigger.Request(), Trigger.Response())


# ----- standup (nur _on_stand_up, NICHT Recovery/Boot) --------------- #

def test_stand_up_emits_standup_cue(node):
    """Erfolgreiches _on_stand_up (aus SAT) → 'standup'-Cue."""
    node._engine._state = GaitEngine.STATE_SAT
    node._latest_joints = _rad0_joints()
    resp = _trigger(node._on_stand_up)
    assert resp.success is True
    assert _cues(node) == ['standup']


def test_stand_up_rejected_emits_no_cue(node):
    """Abgelehntes stand_up (nicht SAT) → kein Cue."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    _trigger(node._on_stand_up)
    assert _cues(node) == []


def test_recover_emits_no_cue(node):
    """Recovery-Aufstehen ist STUMM (kein standup-Cue) — RA2/[D-Audio-1]."""
    node._latest_joints = _rad0_joints()
    node._safety_frozen = True
    resp = _trigger(node._on_recover)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_STARTUP_RAMP
    assert 'standup' not in _cues(node)


# ----- sitdown ------------------------------------------------------- #

def test_sit_down_emits_sitdown_cue(node):
    """Erfolgreiches _on_sit_down (aus STANDING) → 'sitdown'-Cue."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _trigger(node._on_sit_down)
    assert resp.success is True
    assert 'sitdown' in _cues(node)
    # Der interne Stance-Switch (falls aus 'hoch') feuert KEIN reposition.
    assert 'reposition' not in _cues(node)


def test_sit_down_rejected_emits_no_cue(node):
    """Abgelehntes sit_down (nicht STANDING) → kein Cue."""
    node._engine._state = GaitEngine.STATE_WALKING
    _trigger(node._on_sit_down)
    assert _cues(node) == []


# ----- reposition (Höhenwechsel) ------------------------------------- #

def test_cycle_stance_emits_reposition_cue(node):
    """Echter Stance-Switch → 'reposition'-Cue."""
    node._engine._state = GaitEngine.STATE_STANDING
    node._stance_idx = 1
    node._do_stance_switch = MagicMock(return_value=True)
    req = SetBool.Request()
    req.data = True          # höher
    resp = node._on_cycle_stance(req, SetBool.Response())
    assert resp.success is True
    assert _cues(node) == ['reposition']


def test_cycle_stance_no_switch_no_cue(node):
    """Bereits am Rand-Modus (kein Switch) → kein Cue."""
    node._engine._state = GaitEngine.STATE_STANDING
    node._stance_idx = 0
    req = SetBool.Request()
    req.data = False          # tiefer → schon am Rand
    resp = node._on_cycle_stance(req, SetBool.Response())
    assert resp.success is True
    assert _cues(node) == []


# ----- freeze (nur beim Übergang) ------------------------------------ #

def test_freeze_emits_cue_once_on_transition(node):
    """_trigger_safety_freeze feuert 'freeze' NUR beim Eintritt (nicht doppelt)."""
    assert node._safety_frozen is False
    node._trigger_safety_freeze()
    node._trigger_safety_freeze()          # schon frozen → kein zweiter Cue
    assert _cues(node) == ['freeze']


def test_estop_emits_freeze_cue(node):
    """_on_estop feuert (über _trigger_safety_freeze) den 'freeze'-Cue."""
    _trigger(node._on_estop)
    assert _cues(node) == ['freeze']
    assert node._safety_frozen is True
