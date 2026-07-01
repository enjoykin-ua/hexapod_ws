"""
Tests für das Live-Tuning der Teleop-Tempo-Params (TLS).

joy_to_twist las die Scales früher nur beim Start → ``ros2 param set`` blieb
wirkungslos. Mit dem ``_on_param_change``-Callback (validate-then-apply) werden
die Tuning-Werte jetzt live übernommen; ungültige Werte werden abgelehnt, ohne
das Attribut zu verändern; strukturelle Params bleiben unbehandelt (kein Crash).
"""

from hexapod_teleop.joy_to_twist import JoyToTwist
import pytest
import rclpy
from rclpy.parameter import Parameter


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    rclpy.init()
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = JoyToTwist()
    yield n
    n.destroy_node()


def test_scales_live_update(node):
    res = node.set_parameters([
        Parameter('linear_x_scale', Parameter.Type.DOUBLE, 0.2),
        Parameter('linear_y_scale', Parameter.Type.DOUBLE, 0.15),
        Parameter('angular_z_scale', Parameter.Type.DOUBLE, 0.8),
    ])
    assert all(r.successful for r in res)
    assert node._linear_x_scale == pytest.approx(0.2)
    assert node._linear_y_scale == pytest.approx(0.15)
    assert node._angular_z_scale == pytest.approx(0.8)


def test_slow_factor_and_deadzone_live(node):
    res = node.set_parameters([
        Parameter('slow_factor', Parameter.Type.DOUBLE, 0.3),
        Parameter('deadzone', Parameter.Type.DOUBLE, 0.2),
    ])
    assert all(r.successful for r in res)
    assert node._slow_factor == pytest.approx(0.3)
    assert node._deadzone == pytest.approx(0.2)


@pytest.mark.parametrize('name,value', [
    ('linear_x_scale', -0.1),
    ('linear_y_scale', -0.01),
    ('angular_z_scale', -1.0),
    ('slow_factor', 1.5),
    ('slow_factor', -0.1),
    ('deadzone', 1.0),
    ('deadzone', -0.1),
])
def test_invalid_rejected_and_unchanged(node, name, value):
    before = getattr(node, f'_{name}')
    res = node.set_parameters([Parameter(name, Parameter.Type.DOUBLE, value)])
    assert not res[0].successful
    # Attribut bleibt unverändert (kein Teil-Apply).
    assert getattr(node, f'_{name}') == pytest.approx(before)


def test_structural_param_accepted_no_crash(node):
    # Ein nicht-behandelter (struktureller) Param wird akzeptiert, ohne Crash;
    # der Hot-Path nutzt weiter den Startwert.
    before = node._axis_ly
    res = node.set_parameters([
        Parameter('axis_ly', Parameter.Type.INTEGER, 4),
    ])
    assert res[0].successful
    assert node._axis_ly == before  # Start-only, nicht live übernommen


def test_atomic_reject_keeps_all(node):
    # Atomar (Callback EINMAL mit der ganzen Liste): einer ungültig → der ganze
    # Set wird abgelehnt, KEINER angewandt (validate-then-apply).
    x_before = node._linear_x_scale
    result = node.set_parameters_atomically([
        Parameter('linear_x_scale', Parameter.Type.DOUBLE, 0.25),
        Parameter('slow_factor', Parameter.Type.DOUBLE, 2.0),  # ungültig
    ])
    assert not result.successful
    assert node._linear_x_scale == pytest.approx(x_before)
