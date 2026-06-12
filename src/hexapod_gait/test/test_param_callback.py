"""
Tests für gait_node Param-Callback (Phase 11 Stage A).

Strategie:
- ParameterDescriptors haben Range → rqt_reconfigure-Slider.
- Live-Update via ``node.set_parameters([Parameter(...)])`` ändert Member
  + Engine-State.
- atomic-all-or-nothing: bei Multi-Param-Update via
  ``set_parameters_atomically`` führt ein einziger Validation-Fail zur
  Ablehnung aller Updates.
- STANDING-only-Constraint: Updates auf body_height, cycle_time, tick_rate,
  radial_distance, gait_pattern, body_height_min/max nur in STANDING-State.
- Cross-Constraint body_height_min < body_height_max sowie
  body_height ∈ [min, max].
- ``use_sim_time`` read-only nach Init.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
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
    n = GaitNode()
    yield n
    n.destroy_node()


# ----- Descriptors ----------------------------------------------------


def test_param_descriptors_have_range(node):
    """Alle 13 Float-Params haben FloatingPointRange für rqt-Slider."""
    float_params = [
        'step_height', 'cycle_time', 'tick_rate', 'body_height',
        'radial_distance', 'time_from_start_factor', 'step_length_max',
        'default_linear_x', 'default_linear_y', 'default_angular_z',
        'cmd_vel_timeout', 'body_height_min', 'body_height_max',
    ]
    for name in float_params:
        descriptor = node.describe_parameter(name)
        assert len(descriptor.floating_point_range) == 1, (
            f'{name} fehlt FloatingPointRange'
        )
        fr = descriptor.floating_point_range[0]
        assert fr.from_value < fr.to_value, f'{name} Range invalid'


def test_param_gait_pattern_descriptor_has_constraint_hint(node):
    """gait_pattern (String) hat additional_constraints als Hint-Text."""
    descriptor = node.describe_parameter('gait_pattern')
    assert descriptor.additional_constraints
    assert 'tripod' in descriptor.additional_constraints
    assert 'single_leg' in descriptor.additional_constraints


# ----- Happy Path -----------------------------------------------------


def test_param_set_body_height_updates_state(node):
    """body_height-Update in STANDING ändert Member + Engine."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    result = node.set_parameters([
        Parameter('body_height', Parameter.Type.DOUBLE, -0.060),
    ])
    assert result[0].successful, result[0].reason
    assert node._body_height == pytest.approx(-0.060)
    assert node._engine.body_height == pytest.approx(-0.060)


def test_param_set_step_height_updates_engine(node):
    """step_height ist sofort live (kein STANDING-Check)."""
    result = node.set_parameters([
        Parameter('step_height', Parameter.Type.DOUBLE, 0.05),
    ])
    assert result[0].successful
    assert node._step_height == pytest.approx(0.05)
    assert node._engine.step_height == pytest.approx(0.05)


def test_param_set_step_length_max_updates_engine(node):
    """step_length_max wirkt sofort, linear_max rechnet via Property neu."""
    result = node.set_parameters([
        Parameter('step_length_max', Parameter.Type.DOUBLE, 0.08),
    ])
    assert result[0].successful
    assert node._engine.step_length_max == pytest.approx(0.08)
    # linear_max = step_length_max / stance_duration
    # = 0.08 / (cycle_time * (1 - swing_duty))
    # mit cycle_time=2.0, swing_duty=0.5 → stance_duration=1.0
    assert node._engine.linear_max == pytest.approx(0.08)


def test_param_set_cycle_time_updates_engine_linear_max(node):
    """cycle_time propagiert in linear_max via Property (A.2a-Refactor)."""
    result = node.set_parameters([
        Parameter('cycle_time', Parameter.Type.DOUBLE, 4.0),
    ])
    assert result[0].successful
    assert node._engine.cycle_time == pytest.approx(4.0)
    # stance_duration = 4.0 * 0.5 = 2.0 → linear_max = step_length_max/2.0.
    # Node-Default step_length_max = 0.03 (leg_changes S4) → 0.015.
    assert node._engine.stance_duration == pytest.approx(2.0)
    assert node._engine.linear_max == pytest.approx(0.015)


def test_param_set_tick_rate_restarts_timer(node):
    """tick_rate-Update destroyed alten Timer + erzeugt neuen."""
    old_timer = node._timer
    result = node.set_parameters([
        Parameter('tick_rate', Parameter.Type.DOUBLE, 100.0),
    ])
    assert result[0].successful
    assert node._tick_rate == pytest.approx(100.0)
    assert node._timer is not old_timer
    # timer_period_ns = 1e9 / 100 = 10_000_000
    assert node._timer.timer_period_ns == 10_000_000


def test_param_set_gait_pattern_loads_preset(node):
    """gait_pattern-Wechsel auf valides Preset lädt es in Node + Engine."""
    result = node.set_parameters([
        Parameter('gait_pattern', Parameter.Type.STRING, 'single_leg_3'),
    ])
    assert result[0].successful
    assert node._pattern.name == 'single_leg_3'
    assert node._engine.pattern.name == 'single_leg_3'


def test_param_set_atomic_apply_two_valid(node):
    """
    Atomic happy path: zwei zusammen valide werden beide übernommen.

    body_height_min = -0.040 + body_height = -0.035 wären sequenziell
    inkonsistent (erstes Update bricht Cross-Constraint), atomic aber OK.
    """
    result = node.set_parameters_atomically([
        Parameter('body_height_min', Parameter.Type.DOUBLE, -0.040),
        Parameter('body_height', Parameter.Type.DOUBLE, -0.035),
    ])
    assert result.successful, result.reason
    assert node._body_height_min == pytest.approx(-0.040)
    assert node._body_height == pytest.approx(-0.035)


# ----- Validation Rejects ---------------------------------------------


def test_param_set_body_height_out_of_constraint_rejected(node):
    """
    body_height außerhalb [min, max] wird abgelehnt.

    Default-Range ist [-0.140, -0.030], -0.029 ist out (über max).
    """
    result = node.set_parameters([
        Parameter('body_height', Parameter.Type.DOUBLE, -0.029),
    ])
    assert not result[0].successful
    assert 'outside' in result[0].reason
    # body_height unverändert (Stage-1-Default -0.100 = Modus mittel)
    assert node._body_height == pytest.approx(-0.100)


def test_param_set_min_above_max_rejected(node):
    """body_height_min >= body_height_max wird abgelehnt."""
    result = node.set_parameters([
        Parameter('body_height_min', Parameter.Type.DOUBLE, -0.025),
    ])
    assert not result[0].successful
    assert 'must be <' in result[0].reason
    assert node._body_height_min == pytest.approx(-0.140)


def test_param_set_atomic_rollback_one_invalid(node):
    """
    Atomic rollback: wenn ein Update der Liste invalide ist, alle ablehnen.

    body_height_min = -0.045 alleine wäre valide (< max), aber
    body_height = -0.090 wäre out-of-range. Atomic-Validation erkennt
    den Konflikt und rollt beide zurück.
    """
    initial_min = node._body_height_min
    initial_height = node._body_height
    result = node.set_parameters_atomically([
        Parameter('body_height_min', Parameter.Type.DOUBLE, -0.045),
        Parameter('body_height', Parameter.Type.DOUBLE, -0.090),
    ])
    assert not result.successful
    # Beide Werte unverändert
    assert node._body_height_min == pytest.approx(initial_min)
    assert node._body_height == pytest.approx(initial_height)


def test_param_set_unknown_gait_pattern_rejected(node):
    """gait_pattern außerhalb GAIT_PRESETS wird abgelehnt."""
    result = node.set_parameters([
        Parameter('gait_pattern', Parameter.Type.STRING, 'wave_xyz'),
    ])
    assert not result[0].successful
    assert 'unknown gait_pattern' in result[0].reason
    assert node._pattern.name == 'tripod'  # unverändert


def test_param_set_use_sim_time_rejected(node):
    """use_sim_time ist read-only nach Init."""
    result = node.set_parameters([
        Parameter('use_sim_time', Parameter.Type.BOOL, True),
    ])
    assert not result[0].successful
    assert 'read-only' in result[0].reason


# ----- STANDING-only ---------------------------------------------------


def test_param_set_body_height_rejected_while_walking(node):
    """
    body_height-Update wird in WALKING-State abgelehnt.

    Analog cmd_body_height-Topic-Handler in gait_node.py (Kipp-Risiko
    bei Body-Pose-Wechsel mitten im Walk-Cycle).
    """
    # Engine in WALKING zwingen
    node._engine.set_command(0.02, 0.0, 0.0, 0.0)
    assert node._engine.state == GaitEngine.STATE_WALKING

    result = node.set_parameters([
        Parameter('body_height', Parameter.Type.DOUBLE, -0.060),
    ])
    assert not result[0].successful
    assert 'STATE_STANDING' in result[0].reason
    assert node._body_height == pytest.approx(-0.100)  # unverändert (Stage-1-Default)


def test_param_set_step_height_allowed_while_walking(node):
    """
    step_height ist NICHT STANDING-only — Update in WALKING erlaubt.

    Wirkt erst beim nächsten Swing, kein Kipp-Risiko.
    """
    node._engine.set_command(0.02, 0.0, 0.0, 0.0)
    assert node._engine.state == GaitEngine.STATE_WALKING

    result = node.set_parameters([
        Parameter('step_height', Parameter.Type.DOUBLE, 0.05),
    ])
    assert result[0].successful
    assert node._step_height == pytest.approx(0.05)


# ----- Regression: Sync mit cmd_body_height-Topic-Handler --------------


def test_cmd_body_height_topic_syncs_node_member(node):
    """
    /cmd_body_height-Topic-Handler hält Node-Member synchron mit Engine.

    Vor Stage A setzte Phase-6-Handler nur ``engine.body_height`` und ließ
    ``node._body_height`` veraltet zurück. Stage-A-Param-Callback liest
    ``node._body_height`` in der Cross-Constraint-Pre-Validation — daher
    muss der Topic-Handler beides synchronisieren, sonst kann Param-
    Validation eine stale-Decision treffen.
    """
    from std_msgs.msg import Float64
    msg = Float64()
    msg.data = -0.065
    node._on_cmd_body_height(msg)
    assert node._body_height == pytest.approx(-0.065)
    assert node._engine.body_height == pytest.approx(-0.065)
