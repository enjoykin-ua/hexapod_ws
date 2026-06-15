"""
Guarded OS-shutdown for the hexapod supervisor (Block F4).

This module isolates the only dangerous operation in the supervisor — invoking
the operating-system shutdown command — behind a three-layer guard so it can
never fire on the development host and only fires on the configured Pi once
explicitly enabled.

Guard layers (all must pass):
  1. Hard block on any known dev hostname (``DEV_HOSTS``, independent of params).
  2. ``enable_os_shutdown`` must be True.
  3. The current hostname must equal the configured ``pi_hostname``.

``run`` and ``hostname`` are injectable so tests never touch the real OS.
"""

import shlex
import socket
import subprocess


# The dev machine's actual hostname is ``enjoykin-ubutu`` (note the typo — it is
# missing the second 'n'); the docs/CLAUDE.md say ``enjoykin-ubuntu``. Block BOTH
# so the hard guard holds whether or not the hostname typo is ever corrected.
DEV_HOSTS = frozenset({'enjoykin-ubutu', 'enjoykin-ubuntu'})


def guarded_shutdown(enable, pi_hostname, command, logger,
                     run=subprocess.run, hostname=socket.gethostname):
    """
    Run the OS shutdown command iff all three guard layers pass.

    Returns a ``(performed, reason)`` tuple where ``performed`` is True only when
    the command was actually executed. The command is split with ``shlex`` and
    handed to ``run``; failures of the call itself are left to ``run``.
    """
    host = hostname()
    if host in DEV_HOSTS:
        logger.warn('OS shutdown on dev host %s is hard-blocked' % host)
        return (False, 'dev-host')
    if not enable:
        logger.info('enable_os_shutdown=false -> would shut down now (dry run)')
        return (False, 'disabled')
    if host != pi_hostname:
        logger.warn(
            'hostname %s != pi_hostname %r -> no OS shutdown' % (host, pi_hostname))
        return (False, 'host-mismatch')
    logger.warn('executing OS shutdown: %s' % command)
    run(shlex.split(command), check=False)
    return (True, 'executed')
