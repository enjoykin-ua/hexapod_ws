"""
Unit tests für die bringup_launcher-FSM (Block I Phase 3).

Strategie (wie test_shutdown_supervisor): Node direkt instanziieren, ``subprocess``,
``os``-Signale und ``guarded_shutdown`` mocken → nichts startet echt und nichts fährt
den OS herunter. Timer werden angelegt, aber nie gefeuert (Node nicht gespinnt).
"""

import signal
import subprocess
from unittest.mock import MagicMock, patch

from hexapod_supervisor.bringup_launcher import BringupLauncher
import pytest
import rclpy
from std_srvs.srv import Trigger


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    """Init/shutdown rclpy einmal pro Modul."""
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    """
    Frischer BringupLauncher pro Test.

    Teardown setzt ``_proc = None`` VOR destroy_node: sonst würde die
    Zombie-Schutz-Logik in destroy_node ``os.getpgid``/``killpg`` auf einen
    Fake-PID (MagicMock) anwenden und evtl. einen echten Prozess signalisieren.
    """
    n = BringupLauncher()
    yield n
    n._proc = None
    n.destroy_node()


def _fake_proc(pid=4242, alive=True):
    """Mock eines Popen-Handles: pid + poll (None=lebt)."""
    p = MagicMock()
    p.pid = pid
    p.poll.return_value = None if alive else 0
    p.returncode = 0
    return p


def test_start_launches_subprocess(node):
    """_on_start ruft ros2 launch <pkg> <ondemand> mode:=sim + Status running."""
    with patch('hexapod_supervisor.bringup_launcher.subprocess.Popen',
               return_value=_fake_proc()) as popen:
        resp = node._on_start(Trigger.Request(), Trigger.Response())
    assert resp.success
    popen.assert_called_once()
    cmd = popen.call_args[0][0]
    assert cmd[:3] == ['ros2', 'launch', 'hexapod_bringup']
    assert 'bringup_ondemand.launch.py' in cmd
    assert 'mode:=sim' in cmd
    assert node._is_running()


def test_double_start_is_idempotent(node):
    """Zweites _on_start bei laufendem Stack = no-op ('already running')."""
    with patch('hexapod_supervisor.bringup_launcher.subprocess.Popen',
               return_value=_fake_proc()) as popen:
        node._on_start(Trigger.Request(), Trigger.Response())
        resp = node._on_start(Trigger.Request(), Trigger.Response())
    assert resp.success
    assert 'already running' in resp.message
    popen.assert_called_once()


def test_stop_when_not_running(node):
    """_on_stop ohne laufenden Stack = success 'not running'."""
    resp = node._on_stop(Trigger.Request(), Trigger.Response())
    assert resp.success
    assert resp.message == 'not running'


def test_stop_terminates_running(node):
    """_on_stop bei laufendem Stack ruft _terminate_proc + Status stopped."""
    node._proc = _fake_proc()
    node._terminate_proc = MagicMock(return_value=True)
    resp = node._on_stop(Trigger.Request(), Trigger.Response())
    assert resp.success
    node._terminate_proc.assert_called_once()
    assert node._proc is None
    assert not node._is_running()


def test_status_reflects_state(node):
    """_on_status spiegelt stopped/running(pid)."""
    r0 = node._on_status(Trigger.Request(), Trigger.Response())
    assert r0.message == 'stopped'
    node._proc = _fake_proc(pid=99)
    r1 = node._on_status(Trigger.Request(), Trigger.Response())
    assert 'running' in r1.message
    assert '99' in r1.message


def test_terminate_sigint_clean(node):
    """_terminate_proc: SIGINT reicht (wait ok) → clean=True, ein killpg-Call."""
    proc = _fake_proc()
    node._proc = proc
    with patch('hexapod_supervisor.bringup_launcher.os.getpgid',
               return_value=proc.pid), \
            patch('hexapod_supervisor.bringup_launcher.os.killpg') as killpg:
        clean = node._terminate_proc()
    assert clean is True
    killpg.assert_called_once_with(proc.pid, signal.SIGINT)


def test_terminate_escalates_to_kill(node):
    """SIGINT+SIGTERM-Timeout → SIGKILL; killpg-Reihenfolge INT,TERM,KILL."""
    proc = _fake_proc()
    proc.wait.side_effect = [
        subprocess.TimeoutExpired('x', 1),
        subprocess.TimeoutExpired('x', 1),
        0,
    ]
    node._proc = proc
    with patch('hexapod_supervisor.bringup_launcher.os.getpgid',
               return_value=proc.pid), \
            patch('hexapod_supervisor.bringup_launcher.os.killpg') as killpg:
        clean = node._terminate_proc()
    assert clean is False
    sigs = [c.args[1] for c in killpg.call_args_list]
    assert sigs == [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]


def test_pi_shutdown_running_routes_to_supervisor(node):
    """Stack läuft → _on_pi_shutdown ruft /hexapod_request_shutdown (Block-F-Kette)."""
    node._proc = _fake_proc()
    node._shutdown_req_client = MagicMock()
    node._shutdown_req_client.service_is_ready.return_value = True
    resp = node._on_pi_shutdown(Trigger.Request(), Trigger.Response())
    assert resp.success
    node._shutdown_req_client.call_async.assert_called_once()


def test_pi_shutdown_running_no_supervisor(node):
    """Stack läuft, aber Supervisor-Service fehlt → success=False, kein Call."""
    node._proc = _fake_proc()
    node._shutdown_req_client = MagicMock()
    node._shutdown_req_client.service_is_ready.return_value = False
    resp = node._on_pi_shutdown(Trigger.Request(), Trigger.Response())
    assert resp.success is False
    node._shutdown_req_client.call_async.assert_not_called()


def test_pi_shutdown_idle_is_guarded(node):
    """Stack idle → direkter guarded_shutdown; Dev-Host = Dry-Run (performed False)."""
    with patch('hexapod_supervisor.bringup_launcher.guarded_shutdown',
               return_value=(False, 'dev-host')) as gs:
        resp = node._on_pi_shutdown(Trigger.Request(), Trigger.Response())
    assert resp.success
    gs.assert_called_once()
    assert 'performed=False' in resp.message
