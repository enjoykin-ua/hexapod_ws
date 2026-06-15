"""Unit tests for the guarded OS-shutdown (Block F4, F4-G1..G4)."""

from unittest.mock import MagicMock

from hexapod_supervisor.os_shutdown import DEV_HOSTS, guarded_shutdown
import pytest


@pytest.mark.parametrize('dev_host', sorted(DEV_HOSTS))
def test_dev_host_hard_blocked(dev_host):
    """F4-G1: every known dev host is blocked even when enabled and matching."""
    run = MagicMock()
    performed, reason = guarded_shutdown(
        enable=True, pi_hostname=dev_host, command='sudo shutdown -h now',
        logger=MagicMock(), run=run, hostname=lambda: dev_host)
    assert performed is False
    assert reason == 'dev-host'
    run.assert_not_called()


def test_disabled_is_dry_run():
    """F4-G2: enable_os_shutdown=false never executes."""
    run = MagicMock()
    performed, reason = guarded_shutdown(
        enable=False, pi_hostname='hexapod-pi', command='x',
        logger=MagicMock(), run=run, hostname=lambda: 'hexapod-pi')
    assert performed is False
    assert reason == 'disabled'
    run.assert_not_called()


def test_host_mismatch_blocked():
    """F4-G3: a non-matching hostname blocks the shutdown."""
    run = MagicMock()
    performed, reason = guarded_shutdown(
        enable=True, pi_hostname='hexapod-pi', command='x',
        logger=MagicMock(), run=run, hostname=lambda: 'some-other-host')
    assert performed is False
    assert reason == 'host-mismatch'
    run.assert_not_called()


def test_enabled_and_matching_executes():
    """F4-G4: enabled + matching (non-dev) host runs the split command."""
    run = MagicMock()
    performed, reason = guarded_shutdown(
        enable=True, pi_hostname='hexapod-pi', command='sudo shutdown -h now',
        logger=MagicMock(), run=run, hostname=lambda: 'hexapod-pi')
    assert performed is True
    assert reason == 'executed'
    run.assert_called_once()
    assert run.call_args[0][0] == ['sudo', 'shutdown', '-h', 'now']
