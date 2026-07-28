"""
Pin-Tests für die Shutdown-Konfiguration (Block I Phase 9 — Feld-Autonomie).

Warum diese Tests: der „sanfte Shutdown" (Schalter am Roboter **und**
App-Button „Pi herunterfahren") lief bis Phase 9 nur bis zum Relay-Aus. Der
Poweroff selbst feuerte **nie**, weil ``pi_hostname`` leer war — der dritte
Guard in ``os_shutdown.guarded_shutdown`` verglich den echten Hostnamen mit
``''`` und meldete ``host-mismatch``. Sichtbar war das nicht: Hinsetzen und
Relay sind die auffälligen Teile, der fehlende Poweroff nicht. Danach wurde der
Pi am Hauptschalter hart getrennt (SD-Karten-Risiko).

Diese Tests pinnen deshalb die beiden Werte, die das reparieren — in **beiden**
Configs, denn sie werden von zwei verschiedenen Nodes gelesen
(``shutdown_supervisor`` = HW-Schalter-Pfad, ``bringup_launcher`` =
App-Button-Pfad). Läuft einer der beiden leer, ist genau einer der zwei Wege
still kaputt.

Sicherheit auf dem Dev-Rechner hängt **nicht** an diesen Werten: ``DEV_HOSTS``
blockt dort hart und parameter-unabhängig (siehe ``test_os_shutdown_guard.py``).
"""

import os

import yaml

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')

# Der echte Pi (``hostname`` auf dem Gerät). Ändert sich der Hostname, müssen
# beide Configs UND dieser Test nachgezogen werden — genau das soll auffallen.
_PI_HOSTNAME = 'hexapod-pi'

# 'sudo -n' (non-interactive): aus einem systemd-Dienst gibt es kein Terminal.
# Ohne -n würde sudo auf eine Passwort-Eingabe warten, die nie kommt — der
# Shutdown hinge still. Mit -n scheitert er sofort und die Ursache steht im Log.
_SHUTDOWN_COMMAND = 'sudo -n shutdown -h now'

_CASES = (
    ('supervisor.yaml', 'shutdown_supervisor'),      # HW-Schalter-Pfad
    ('launcher.real.yaml', 'bringup_launcher'),      # App-Button-Pfad
)


def _params(filename, node_key):
    with open(os.path.join(_CONFIG_DIR, filename)) as handle:
        data = yaml.safe_load(handle)
    return data[node_key]['ros__parameters']


def test_pi_hostname_set_in_both_configs():
    """Beide Shutdown-Pfade kennen den echten Pi-Hostnamen (sonst kein Poweroff)."""
    for filename, node_key in _CASES:
        p = _params(filename, node_key)
        assert p['pi_hostname'] == _PI_HOSTNAME, (
            f'{filename}: pi_hostname={p["pi_hostname"]!r} — leer/falsch bedeutet '
            'host-mismatch, der Pi faehrt nie herunter'
        )


def test_shutdown_command_is_non_interactive():
    """``sudo -n``: ohne Terminal sofort scheitern statt auf ein Passwort warten."""
    for filename, node_key in _CASES:
        p = _params(filename, node_key)
        assert p['shutdown_command'] == _SHUTDOWN_COMMAND, (
            f'{filename}: shutdown_command={p["shutdown_command"]!r}'
        )


def test_os_shutdown_enabled_in_both_configs():
    """Master-Arm bleibt an — der Dev-Host ist über DEV_HOSTS geschuetzt."""
    for filename, node_key in _CASES:
        p = _params(filename, node_key)
        assert p['enable_os_shutdown'] is True, filename


def test_both_configs_agree():
    """
    Die beiden Configs muessen dieselben Guard-Werte tragen.

    Sonst haette ein Weg (Schalter oder App-Button) eine andere Wahrheit als der
    andere — und man wuerde es erst im Feld merken.
    """
    a = _params(*_CASES[0])
    b = _params(*_CASES[1])
    for key in ('pi_hostname', 'shutdown_command', 'enable_os_shutdown'):
        assert a[key] == b[key], f'{key} weicht zwischen den Configs ab'
