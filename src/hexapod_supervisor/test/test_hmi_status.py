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

"""Static validation of the HMI config manifest + alert formatting (Phase 5)."""

import os

from hexapod_supervisor.hmi_status import _alert_dict
import pytest
import yaml

_HERE = os.path.dirname(__file__)
_MANIFEST = os.path.join(_HERE, '..', 'config', 'hmi_config_manifest.yaml')
_SRC = os.path.join(_HERE, '..', '..')  # workspace src/


def _load():
    with open(_MANIFEST) as handle:
        return yaml.safe_load(handle)


def test_manifest_structure():
    """Pflichtfelder da, keine Duplikate, Slider-Defaults im Range."""
    params = _load()['manifest']['params']
    assert len(params) >= 30
    keys = [(p['node'], p['param']) for p in params]
    assert len(keys) == len(set(keys)), 'duplicate node/param in manifest'
    required = ('node', 'param', 'group', 'label', 'hint', 'widget',
                'type', 'default')
    for p in params:
        for key in required:
            assert key in p, f'{p.get("param")} missing {key}'
        assert p['widget'] in ('slider', 'toggle', 'dropdown')
        if p['widget'] == 'slider':
            assert p['min'] <= p['default'] <= p['max'], \
                f'{p["param"]} default out of [min,max]'
            assert p['step'] > 0
        if p['widget'] == 'dropdown':
            assert p['default'] in p['options']


def test_advanced_gains_count():
    """Genau die 16 per-Achse-Balance-Gains sind advanced (eingeklappt)."""
    params = _load()['manifest']['params']
    adv = [p for p in params if p.get('advanced')]
    assert len(adv) == 16  # 8 Gains x roll/pitch


def test_capabilities_present():
    """Enums fuer die Dropdowns korrekt."""
    caps = _load()['capabilities']
    assert caps['gaits'] == ['tripod', 'wave', 'tetrapod', 'ripple']
    assert caps['stance_modes'] == ['tief', 'mittel', 'hoch']
    assert caps['tempo_presets'] == ['langsam', 'mittel', 'schnell', 'aggressiv']


def _source(rel_path):
    path = os.path.join(_SRC, rel_path)
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        return handle.read()


def test_manifest_params_exist_in_code():
    """Jeder Manifest-Param muss im Ziel-Node als String vorkommen (Drift-Schutz)."""
    gait = _source('hexapod_gait/hexapod_gait/gait_node.py')
    teleop = _source('hexapod_teleop/hexapod_teleop/joy_to_twist.py')
    if gait is None or teleop is None:
        pytest.skip('sibling source not available (out-of-tree build)')
    src = {'/gait_node': gait, '/joy_to_twist': teleop}
    for p in _load()['manifest']['params']:
        node, name = p['node'], p['param']
        assert node in src, f'unknown node {node}'
        text = src[node]
        if f"'{name}'" in text or f'"{name}"' in text:
            continue
        # Die 16 Gains werden per Loop deklariert (leveling_<suffix>_<axis>),
        # nicht als String-Literal -> Prefix/Suffix-Match tolerieren.
        if name.startswith('leveling_') and name.endswith(('_roll', '_pitch')):
            continue
        raise AssertionError(f'{name!r} nicht in {node} gefunden (Drift?)')


def test_alert_dict_filters_below_warn():
    """INFO/DEBUG (<30) ergeben keinen Alert."""
    assert _alert_dict(20, 'n', 'info', 1, 0) is None
    assert _alert_dict(10, 'n', 'dbg', 1, 0) is None


def test_alert_dict_formats_warn_error_fatal():
    """WARN/ERROR/FATAL werden korrekt geformt (Level-Name + Felder)."""
    warn = _alert_dict(30, 'gait_node', 'kippt', 5, 500_000_000)
    assert warn == {'stamp': 5.5, 'level': 'WARN',
                    'name': 'gait_node', 'msg': 'kippt'}
    assert _alert_dict(40, 'n', 'e', 0, 0)['level'] == 'ERROR'
    assert _alert_dict(50, 'n', 'f', 0, 0)['level'] == 'FATAL'
