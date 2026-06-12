"""
Per-Bein-rad-Limit-Waechter — schliesst das Loch, das test_config.py laesst.

``test_config.py`` prueft ``config.py`` nur gegen die *Property* in
``hexapod_physical_properties.xacro``. Die 6 per-Bein-Werte in
``hexapod.urdf.xacro`` und ``hexapod.ros2_control.xacro`` (die MAßGEBLICHEN
Limits seit Stage F) liest es nicht — ein einzelner vergessener per-Bein-Wert
bliebe gruen, faellt aber auf HW als Stall/Trip auf (Memory
``two_joint_limit_sources``, ai_navigation §0/§1).

Dieser Test verifiziert die drei Invarianten, die das Loch schliessen:
  1. **Symmetrie** — alle 6 Beine haben identische coxa/femur/tibia-Limits
     (gegen den per-Bein-Asymmetrie-Bug, Memory ``phase13_femur_zero_asymmetry``).
     Ein vergessener Wert an EINEM Bein bricht hier.
  2. **URDF-Sync** — ``hexapod.urdf.xacro`` == ``hexapod.ros2_control.xacro``
     (die beiden URDF-Limit-Quellen duerfen nicht auseinanderdriften).
  3. **IK-Anker** — ``config.py`` coxa/femur/tibia == die per-Bein-URDF-Werte;
     haengt den IK-Mirror an die ECHTEN per-Bein-Werte, nicht nur an die Property.

Seit leg_changes S3 ist auch Coxa konsistent (``config.py`` ``_COXA_LIMITS`` =
``(-0.415, 0.415)`` == per-Bein-URDF; die frueheren ``(-1.57, 1.57)`` waren die
Datenblatt-Verifikations-Cal). Der Anker deckt jetzt alle 3 Joints ab.
"""

from pathlib import Path
import re

from hexapod_kinematics.config import HEXAPOD


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
URDF_XACRO = (
    WORKSPACE_ROOT / 'src' / 'hexapod_description' / 'urdf' / 'hexapod.urdf.xacro'
)
ROS2_CONTROL_XACRO = (
    WORKSPACE_ROOT
    / 'src'
    / 'hexapod_description'
    / 'urdf'
    / 'hexapod.ros2_control.xacro'
)

_NUM = r'\s*(-?\d+(?:\.\d+)?)\s*'
_JOINTS = ('coxa', 'femur', 'tibia')


def _parse_leg_calls(path: Path) -> dict:
    """``<xacro:leg id=N ... tibia_lower=..>`` → ``{id: {joint: (lo, hi)}}``."""
    text = path.read_text()
    legs: dict = {}
    for block in re.finditer(r'<xacro:leg\s+id="(\d+)"(.*?)/>', text, re.DOTALL):
        leg_id = int(block.group(1))
        body = block.group(2)
        entry = {}
        for joint in _JOINTS:
            lo = re.search(rf'{joint}_lower="{_NUM}"', body)
            hi = re.search(rf'{joint}_upper="{_NUM}"', body)
            assert lo and hi, f'leg {leg_id}: {joint}_lower/upper fehlt im xacro:leg'
            entry[joint] = (float(lo.group(1)), float(hi.group(1)))
        legs[leg_id] = entry
    return legs


def _parse_joint_iface_calls(path: Path) -> dict:
    """``<xacro:joint_iface name=.. lower=.. upper=..>`` → ``{name: (lo, hi)}``."""
    text = path.read_text()
    pattern = (
        r'<xacro:joint_iface\s+name="(leg_\d+_\w+_joint)"\s+'
        rf'lower="{_NUM}"\s+upper="{_NUM}"'
    )
    return {
        m.group(1): (float(m.group(2)), float(m.group(3)))
        for m in re.finditer(pattern, text)
    }


def test_parsing_found_everything():
    """Sanity: 6 ``xacro:leg`` + 18 ``xacro:joint_iface`` wirklich geparst."""
    legs = _parse_leg_calls(URDF_XACRO)
    ifaces = _parse_joint_iface_calls(ROS2_CONTROL_XACRO)
    assert set(legs) == {1, 2, 3, 4, 5, 6}, f'nur Beine {sorted(legs)} geparst'
    assert len(ifaces) == 18, f'nur {len(ifaces)} joint_iface geparst (erwartet 18)'


def test_legs_symmetric():
    """
    Alle 6 Beine identische rad-Limits (per-Bein-Asymmetrie-Bug-Schutz).

    Genau hier bricht es, wenn ein einzelner ``tibia_lower`` auf dem alten Wert
    vergessen wurde — die ``test_config.py``-Luecke.
    """
    legs = _parse_leg_calls(URDF_XACRO)
    reference = legs[1]
    for leg_id in (2, 3, 4, 5, 6):
        assert legs[leg_id] == reference, (
            f'leg {leg_id} {legs[leg_id]} != leg 1 {reference} — '
            f'rad-Limits muessen ueber alle 6 Beine identisch sein'
        )


def test_urdf_matches_ros2_control():
    """``hexapod.urdf.xacro`` per-Bein-Limits == ros2_control command-Clamps."""
    legs = _parse_leg_calls(URDF_XACRO)
    ifaces = _parse_joint_iface_calls(ROS2_CONTROL_XACRO)
    for leg_id, joints in legs.items():
        for joint, limits in joints.items():
            name = f'leg_{leg_id}_{joint}_joint'
            assert ifaces[name] == limits, (
                f'{name}: urdf {limits} != ros2_control {ifaces[name]} — '
                f'die beiden URDF-Limit-Quellen sind auseinandergedriftet'
            )


def test_config_py_anchors_all_joints():
    """
    config.py coxa/femur/tibia-Limits == die maßgeblichen per-Bein-URDF-Werte.

    Verankert den IK-Mirror an den ECHTEN per-Bein-Werten (nicht nur an der
    Property). Coxa seit leg_changes S3 ebenfalls konsistent (±0.415).
    """
    reference = _parse_leg_calls(URDF_XACRO)[1]
    cfg = HEXAPOD.legs[0]
    assert cfg.coxa_limits == reference['coxa'], (
        f'config.py _COXA_LIMITS {cfg.coxa_limits} != urdf {reference["coxa"]}'
    )
    assert cfg.femur_limits == reference['femur'], (
        f'config.py _FEMUR_LIMITS {cfg.femur_limits} != urdf {reference["femur"]}'
    )
    assert cfg.tibia_limits == reference['tibia'], (
        f'config.py _TIBIA_LIMITS {cfg.tibia_limits} != urdf {reference["tibia"]}'
    )
