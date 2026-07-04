"""
Unit-Tests für foot_contact_viz (Block A5 Stufe 5, HW5v).

Prüft den reinen Bool→Marker-Adapter: Farben (grün/grau/stale-dunkel),
frame_ids (Overlay am foot_link) und den Stale-Timeout. Kein RViz-Rendering,
kein TF, kein serieller Pfad (siehe stage_5-Plan §10.3 Scope-out).
"""

from hexapod_gait.foot_contact_viz import (
    _DARK, _GREEN, _GREY, _LEG_IDS, FootContactViz,
)
import pytest
import rclpy
from rclpy.parameter import Parameter
from visualization_msgs.msg import Marker


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = FootContactViz()
    yield n
    n.destroy_node()


def _fresh(node, now, legs):
    """Alle Beine 'legs' als frisch empfangen markieren (nicht stale)."""
    for leg in legs:
        node._last_t[leg] = now


def test_init_state(node):
    # 6 Subs + Publisher + Cache, Default alle False.
    assert set(node._contact.keys()) == set(_LEG_IDS)
    assert all(v is False for v in node._contact.values())
    assert len(node._subs) == 6


def test_six_markers_with_foot_link_frames(node):
    now = 100.0
    _fresh(node, now, _LEG_IDS)
    arr = node._build_markers(now)
    assert len(arr.markers) == 6
    for leg, m in zip(_LEG_IDS, arr.markers):
        assert m.header.frame_id == f'leg_{leg}_foot_link'
        assert m.type == Marker.SPHERE
        assert m.action == Marker.ADD
        assert m.ns == 'foot_contact'
        assert m.id == leg
        # Overlay: Position 0 im foot_link-Frame.
        assert (m.pose.position.x, m.pose.position.y, m.pose.position.z) == (0.0, 0.0, 0.0)


def test_marker_stamp_is_zero_for_latest_tf(node):
    # Stamp 0 → RViz nimmt die neueste TF (kein „extrapolation into the future"-
    # Flackern bei den nachhängenden foot_link-Blatt-Frames).
    arr = node._build_markers(100.0)
    for m in arr.markers:
        assert m.header.stamp.sec == 0
        assert m.header.stamp.nanosec == 0


def test_contact_is_green_open_is_grey(node):
    now = 100.0
    _fresh(node, now, _LEG_IDS)
    node._contact[2] = True   # Kontakt
    node._contact[5] = True   # Kontakt
    arr = node._build_markers(now)
    by_id = {m.id: m for m in arr.markers}
    assert by_id[2].color == _GREEN
    assert by_id[5].color == _GREEN
    for leg in (1, 3, 4, 6):
        assert by_id[leg].color == _GREY


def test_stale_is_dark(node):
    now = 100.0
    # Bein 1 frisch + Kontakt, Bein 3 frisch + offen, Rest nie empfangen (0.0).
    node._last_t[1] = now
    node._contact[1] = True
    node._last_t[3] = now
    node._contact[3] = False
    arr = node._build_markers(now)
    by_id = {m.id: m for m in arr.markers}
    assert by_id[1].color == _GREEN
    assert by_id[3].color == _GREY
    # Beine 2,4,5,6: _last_t=0.0 → now-0 >> stale_timeout → dunkel.
    for leg in (2, 4, 5, 6):
        assert by_id[leg].color == _DARK


def test_stale_boundary(node):
    # Genau am Timeout noch NICHT stale (>-Vergleich), knapp darüber schon.
    node.set_parameters([
        Parameter('stale_timeout', Parameter.Type.DOUBLE, 0.5),
    ])
    now = 100.0
    node._contact[1] = True
    node._last_t[1] = now - 0.5   # exakt am Timeout → nicht stale
    node._last_t[2] = now - 0.51  # knapp drüber → stale
    node._contact[2] = True
    arr = node._build_markers(now)
    by_id = {m.id: m for m in arr.markers}
    assert by_id[1].color == _GREEN
    assert by_id[2].color == _DARK


def test_marker_scale_param_live(node):
    node.set_parameters([
        Parameter('marker_scale', Parameter.Type.DOUBLE, 0.03),
    ])
    now = 100.0
    _fresh(node, now, _LEG_IDS)
    arr = node._build_markers(now)
    m = arr.markers[0]
    assert m.scale.x == pytest.approx(0.03)
    assert m.scale.y == pytest.approx(0.03)
    assert m.scale.z == pytest.approx(0.03)


def test_callback_updates_cache_and_stamp(node):
    from std_msgs.msg import Bool
    before = node._last_t[4]
    cb = node._make_cb(4)
    cb(Bool(data=True))
    assert node._contact[4] is True
    assert node._last_t[4] > before
    cb(Bool(data=False))
    assert node._contact[4] is False
