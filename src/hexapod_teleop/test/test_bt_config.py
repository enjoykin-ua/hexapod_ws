"""
Konsistenz-Test für die Controller-Profile (Block C4).

ps4_bt.yaml muss dieselben joy_to_twist-Parameter-Keys haben wie ps4_usb.yaml
(nur Werte/Indizes dürfen abweichen) — sonst fehlt beim BT-Profil ein Param
und joy_to_twist fällt auf einen Default zurück.
"""

import os

import yaml

_CFG = os.path.join(os.path.dirname(__file__), '..', 'config')


def _param_keys(name):
    with open(os.path.join(_CFG, name)) as f:
        data = yaml.safe_load(f)
    return set(data['joy_to_twist']['ros__parameters'].keys())


def test_bt_profile_has_same_keys_as_usb():
    """ps4_bt.yaml deckt exakt dieselben Param-Keys ab wie ps4_usb.yaml."""
    assert _param_keys('ps4_bt.yaml') == _param_keys('ps4_usb.yaml')
