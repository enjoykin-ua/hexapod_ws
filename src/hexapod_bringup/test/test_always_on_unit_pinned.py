# Copyright 2026 enjoykin
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Pin-Tests für die Always-On-systemd-Unit (Block I Phase 9 — Feld-Autonomie).

Warum diese Tests: seit Phase 9 startet die Always-On-Schicht auf dem Pi als
systemd-User-Dienst statt aus einer interaktiven SSH-Shell. Dabei ist eine
Falle aufgeflogen — die Unit startet mit ``bash -lc``, also einer **nicht
interaktiven** Shell, und Ubuntus ``~/.bashrc`` steigt dort in der ersten Zeile
aus (``case $- in *i*) ;; *) return;; esac``). Das von ``provision_pi.sh``
dorthin geschriebene ``export ROS_DOMAIN_ID=42`` wirkte im Dienst also **nie**:
der Dienst lief in Domain 0, jede SSH-Shell und der Desktop in 42. Sichtbar war
das nur indirekt (``ros2 node list`` leer, obwohl der Dienst lief), und die App
war gar nicht betroffen — rosbridge läuft im Dienst, der schwere Stack als
dessen Subprozess, also alles in *einer* Domain.

Der Fix ist ein explizites ``Environment=`` in der Unit. Damit gibt es den Wert
an **zwei** Stellen (Unit + ``provision_bashrc``), und genau das pinnen diese
Tests: laufen sie auseinander, sieht der Desktop den Roboter wieder nicht —
dasselbe Fehlerbild wie bei den zwei Shutdown-Configs
(``test_shutdown_config_pinned.py``).
"""

import os
import re
import shlex

import pytest

_HERE = os.path.dirname(__file__)
_UNIT = os.path.join(_HERE, '..', 'systemd', 'hexapod_always_on.service')
_PROVISION = os.path.join(_HERE, '..', '..', '..', 'tools', 'provision_pi.sh')

# Die Variablen, die im Dienst gesetzt sein MÜSSEN. ROS_DOMAIN_ID ist die
# eigentliche Ursache des Befunds; RMW_IMPLEMENTATION steht daneben, weil ein
# stiller RMW-Wechsel dasselbe Symptom erzeugen würde (zwei Prozesse, die sich
# nicht sehen).
_REQUIRED_VARS = ('ROS_DOMAIN_ID', 'RMW_IMPLEMENTATION')


def _unit_environment():
    """Alle ``Environment=``-Zuweisungen der Unit als dict."""
    env = {}
    with open(_UNIT) as handle:
        for line in handle:
            line = line.strip()
            if line.startswith('#') or not line.startswith('Environment='):
                continue
            # systemd erlaubt mehrere gequotete KEY=VALUE je Zeile.
            for token in shlex.split(line[len('Environment='):]):
                if '=' in token:
                    key, value = token.split('=', 1)
                    env[key] = value
    return env


def _provision_exports():
    """Die ``export KEY=VALUE`` aus provision_pi.sh (dort in echo-Zeilen)."""
    if not os.path.isfile(_PROVISION):
        pytest.skip('tools/provision_pi.sh nicht vorhanden (Paket ohne Workspace)')
    with open(_PROVISION) as handle:
        text = handle.read()
    exports = {}
    for key in _REQUIRED_VARS:
        match = re.search(r'export\s+%s=([^\s"\']+)' % key, text)
        if match:
            exports[key] = match.group(1)
    return exports


def test_unit_sets_ros_environment():
    """
    Die Unit bringt ihre ROS-Umgebung selbst mit.

    Ohne das erbt sie nichts Brauchbares: ``bash -lc`` ist nicht interaktiv,
    ``~/.bashrc`` tut dort per Ubuntu-Default nichts.
    """
    env = _unit_environment()
    for key in _REQUIRED_VARS:
        assert key in env, (
            f'{key} fehlt in der Unit — der Dienst laeuft dann in der '
            'Default-Domain, waehrend Shell und Desktop woanders sitzen '
            '(ros2 node list leer, Desktop-Tools sehen den Roboter nicht)'
        )


def test_unit_domain_matches_provisioned_bashrc():
    """Unit und ``provision_pi.sh`` müssen dieselben Werte setzen."""
    env = _unit_environment()
    exports = _provision_exports()
    for key in _REQUIRED_VARS:
        assert key in exports, f'{key} fehlt in provision_pi.sh (provision_bashrc)'
        assert env[key] == exports[key], (
            f'{key}: Unit={env[key]!r} vs. provision_pi.sh={exports[key]!r} — '
            'die beiden Quellen sind auseinandergelaufen'
        )


def test_domain_id_is_numeric():
    """``ROS_DOMAIN_ID`` muss eine Zahl sein (sonst ignoriert rmw sie still)."""
    value = _unit_environment()['ROS_DOMAIN_ID']
    assert value.isdigit(), f'ROS_DOMAIN_ID={value!r} ist keine Zahl'
    assert 0 <= int(value) <= 232, f'ROS_DOMAIN_ID={value} ausserhalb 0..232'


def test_unit_still_sources_overlay_and_starts_real_mode():
    """
    Die Kernaussage der Unit bleibt: ROS + Workspace sourcen, ``mode:=real``.

    Das ``Environment=`` ersetzt das Sourcen **nicht** — es ergänzt es nur um
    die Variablen, die ``~/.bashrc`` im Dienst nicht liefern kann.
    """
    with open(_UNIT) as handle:
        text = handle.read()
    exec_lines = [ln for ln in text.splitlines() if ln.startswith('ExecStart=')]
    assert len(exec_lines) == 1, 'genau eine ExecStart-Zeile erwartet'
    exec_start = exec_lines[0]
    assert 'source /opt/ros/jazzy/setup.bash' in exec_start, (
        'ExecStart sourced die ROS-Distro nicht mehr: ' + exec_start
    )
    assert 'install/setup.bash' in exec_start, (
        'ExecStart sourced das Workspace-Overlay nicht mehr: ' + exec_start
    )
    assert 'always_on.launch.py mode:=real' in exec_start, (
        'ExecStart startet nicht mehr die Always-On-Schicht im real-Modus: ' + exec_start
    )
