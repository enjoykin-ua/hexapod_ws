"""
Block-B4-Glue-Tests für gait_node: Show-Pose-Toggle + /cmd_show-Offsets.

Strategie (wie test_sitdown_node.py): GaitNode direkt instanziieren, die
Service-/Subscriber-Handler als Methoden aufrufen (kein Executor-Roundtrip).
Engine-State wird für Guard-Tests direkt gesetzt.

Deckt B4.4 (Toggle-Service + Guards, /cmd_show-Subscriber + Skalierung +
Staleness, Params).
"""

import math
import time

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import (
    _STANCE_DEFAULT_IDX,
    _STANCE_FREE_LEG_IDX,
    _STANCE_MODES,
    GaitNode,
)

import pytest
import rclpy
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import SetBool, Trigger


_SHOW_PARAMS = (
    'show_enter_duration', 'show_exit_duration', 'show_body_shift_back',
    'show_shift_fraction', 'show_safety_margin', 'show_front_radial',
    'show_front_z', 'show_return_rate', 'show_lat_scale', 'show_vert_scale',
    'show_radial_scale',
)


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


def _toggle(node):
    return node._on_show_toggle(Trigger.Request(), Trigger.Response())


def _cycle_stance(node, higher):
    req = SetBool.Request()
    req.data = higher
    return node._on_cycle_stance(req, SetBool.Response())


# ----- Params --------------------------------------------------------- #

def test_show_params_have_range(node):
    """Alle 10 Show-Params haben FloatingPointRange (rqt-Slider)."""
    for name in _SHOW_PARAMS:
        fr = node.describe_parameter(name).floating_point_range
        assert len(fr) == 1, f'{name} fehlt FloatingPointRange'
        assert fr[0].from_value < fr[0].to_value


def test_show_param_defaults(node):
    """
    Defaults = Phase-10-Auslegung (phase_10_free_leg_plan.md §1.1).

    Offline belegt durch ``tools/show_pose_cog_check.py --sweep``: 44.7 mm
    Neutral-Marge, 38.6 mm Worst-Case über die Stick-Hülle, 98 % erreichbar,
    15 mm Bodenfreiheit. Wer hier Werte ändert, muss das Tool erneut fahren.
    """
    assert node._show_body_shift_back == pytest.approx(0.060)
    assert node._show_shift_fraction == pytest.approx(0.5)
    assert node._show_safety_margin == pytest.approx(0.030)
    assert node._show_front_radial == pytest.approx(0.19)
    assert node._show_front_lat == pytest.approx(0.04)
    assert node._show_front_z == pytest.approx(0.0)
    assert node._show_body_pitch_deg == pytest.approx(5.0)
    assert node._show_lat_scale == pytest.approx(0.04)
    assert node._show_vert_scale == pytest.approx(0.05)
    assert node._show_radial_scale == pytest.approx(0.03)


def test_show_coxa_budget_within_urdf_limit(node):
    """
    FL-T4: Neutral-Anteil + Stick-Ausschlag müssen ins Coxa-Limit passen.

    ``show_front_lat`` und ``show_lat_scale`` teilen sich denselben Bereich —
    zusammen dürfen sie ±0.415 rad nicht überschreiten, sonst hängt der Stick
    am Limit statt zu bewegen.
    """
    coxa_max = math.atan2(
        node._show_front_lat + node._show_lat_scale, node._show_front_radial)
    assert coxa_max < 0.415, f'Coxa-Budget gesprengt: {coxa_max:.3f} rad'
    assert coxa_max > 0.30, (
        f'Coxa-Budget verschenkt: nur {coxa_max:.3f} rad von 0.415 genutzt')


def test_show_ground_clearance(node):
    """
    FL-T3: der Fuß darf im tiefsten Punkt nicht in den Boden fahren.

    Boden liegt bei ``body_height``; setzte der Fuß auf, würde er das
    Stützpolygon verfälschen und die CoG-Rechnung wertlos machen.
    """
    lowest = node._show_front_z - node._show_vert_scale
    clearance = lowest - (-0.065)      # tiefe Stance
    assert clearance >= 0.010, f'nur {clearance * 1000:.0f} mm Bodenfreiheit'


# ----- Toggle --------------------------------------------------------- #

def test_show_toggle_from_standing_enters(node):
    """Toggle aus STANDING → SHOW_ENTER."""
    assert node._engine.state == GaitEngine.STATE_STANDING
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_ENTER


def test_show_toggle_from_active_exits(node):
    """Toggle aus SHOW_ACTIVE → SHOW_EXIT (Round-Trip raus)."""
    node._engine._state = GaitEngine.STATE_SHOW_ACTIVE
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_EXIT


def test_show_toggle_from_enter_exits(node):
    """Toggle mitten in SHOW_ENTER → SHOW_EXIT (auch aus Enter herausführbar)."""
    node._engine._state = GaitEngine.STATE_SHOW_ENTER
    resp = _toggle(node)
    assert resp.success is True
    assert node._engine.state == GaitEngine.STATE_SHOW_EXIT


def test_show_toggle_rejected_when_walking(node):
    """Toggle aus WALKING wird abgelehnt (kein State-Change)."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _toggle(node)
    assert resp.success is False
    assert node._engine.state == GaitEngine.STATE_WALKING


def test_show_toggle_resets_cmd_show_on_enter(node):
    """Beim Eintreten werden alte Stick-Werte verworfen (Neutral-Start)."""
    node._cmd_show = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    _toggle(node)
    assert node._cmd_show == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


# ----- /cmd_show-Subscriber ------------------------------------------- #

def test_cmd_show_caches_six_values(node):
    """/cmd_show speichert die 6 Achsen-Werte + Timestamp (B4.11)."""
    msg = Float64MultiArray()
    msg.data = [0.5, -0.5, 0.2, 0.25, 0.75, 0.4]
    node._on_cmd_show(msg)
    assert node._cmd_show == [0.5, -0.5, 0.2, 0.25, 0.75, 0.4]
    assert node._last_cmd_show_time is not None


def test_cmd_show_ignores_malformed(node):
    """Zu kurzes Array (< 6) → ignoriert (kein State-Change)."""
    node._cmd_show = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    msg = Float64MultiArray()
    msg.data = [0.1, 0.2, 0.3, 0.4]
    node._on_cmd_show(msg)
    assert node._cmd_show == [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


# ----- /cmd_show → Engine-Offsets (Skalierung + Staleness) ------------ #

def test_update_show_offsets_scales_and_maps(node):
    """Stick/Trigger→Meter-Skalierung + Mapping leg6/leg1 (lat,vert,radial)."""
    node._show_lat_scale = 0.06
    node._show_vert_scale = 0.05
    node._show_radial_scale = 0.04
    # [l6_lat, l6_vert, l6_radial, l1_lat, l1_vert, l1_radial]
    node._cmd_show = [1.0, -1.0, 0.5, -0.5, 0.5, 1.0]
    node._last_cmd_show_time = time.monotonic()
    node._update_show_offsets(time.monotonic())
    tgt = node._engine._show_offset_target
    assert tgt['leg_6'] == pytest.approx((0.06, -0.05, 0.02))
    assert tgt['leg_1'] == pytest.approx((-0.03, 0.025, 0.04))


def test_update_show_offsets_stale_zeroes(node):
    """Ohne frisches /cmd_show (Disconnect) → Offsets 0 (Rückkehr Neutral)."""
    node._show_lat_scale = 0.06
    node._show_vert_scale = 0.06
    node._show_radial_scale = 0.05
    node._cmd_show = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    # Timestamp weit in der Vergangenheit → stale.
    node._last_cmd_show_time = time.monotonic() - 10.0
    node._update_show_offsets(time.monotonic())
    tgt = node._engine._show_offset_target
    assert tgt['leg_6'] == pytest.approx((0.0, 0.0, 0.0))
    assert tgt['leg_1'] == pytest.approx((0.0, 0.0, 0.0))


# ----- Stance-Modi (Stage 1) ------------------------------------------ #

def test_stance_default_is_mittel(node):
    """Boot-Modus = mittel (Standup-Basis)."""
    assert node._stance_idx == _STANCE_DEFAULT_IDX
    assert _STANCE_MODES[node._stance_idx].name == 'mittel'


def test_cycle_stance_higher_from_standing(node):
    """data=True aus STANDING → höher (mittel→hoch), Engine im Switch."""
    resp = _cycle_stance(node, True)
    assert resp.success is True
    assert _STANCE_MODES[node._stance_idx].name == 'hoch'
    assert node._engine.state == GaitEngine.STATE_STANCE_SWITCH


def test_cycle_stance_lower_from_standing(node):
    """data=False aus STANDING → tiefer (mittel→tief)."""
    resp = _cycle_stance(node, False)
    assert resp.success is True
    assert _STANCE_MODES[node._stance_idx].name == 'tief'
    assert node._engine.state == GaitEngine.STATE_STANCE_SWITCH


def test_cycle_stance_clamps_at_top(node):
    """Am höchsten Modus → kein Wrap, kein State-Change."""
    node._stance_idx = len(_STANCE_MODES) - 1   # hoch
    resp = _cycle_stance(node, True)
    assert resp.success is True
    assert node._stance_idx == len(_STANCE_MODES) - 1
    assert node._engine.state == GaitEngine.STATE_STANDING   # kein Switch


def test_cycle_stance_rejected_when_not_standing(node):
    """cycle_stance außerhalb STANDING wird abgelehnt."""
    node._engine._state = GaitEngine.STATE_WALKING
    resp = _cycle_stance(node, True)
    assert resp.success is False
    assert _STANCE_MODES[node._stance_idx].name == 'mittel'  # unverändert


def test_sit_below_sit_safe_routes_through_mittel(node):
    """
    Hinsetzen unterhalb _SIT_SAFE_MIN_BH → erst Stance-Switch auf mittel, dann sit.

    leg_changes (S5): mit dem einheitlichen Radius 0.160 liegt KEIN Stance-Modus
    mehr unter der Schwelle (tiefste "hoch" -0.100 > -0.115) → alle Modi sitzen
    direkt (siehe test_sit_from_hoch_direct). Die Routing-Sicherung kann aber via
    /cmd_body_height (body_height bis -0.110) noch relevant werden — hier per
    Engine-Pose unter die Schwelle erzwungen, um den Pfad abzudecken.
    """
    node._stance_idx = len(_STANCE_MODES) - 1   # hoch
    node._engine.radial_distance = _STANCE_MODES[-1].radial
    node._engine.body_height = -0.120   # < _SIT_SAFE_MIN_BH (-0.115), erzwungen
    resp = node._on_sit_down(Trigger.Request(), Trigger.Response())
    assert resp.success is True
    # NICHT direkt hingesetzt, sondern Switch auf mittel + pending.
    assert node._engine.state == GaitEngine.STATE_STANCE_SWITCH
    assert node._pending_sitdown is True
    assert _STANCE_MODES[node._stance_idx].name == 'mittel'


def test_sit_from_hoch_direct(node):
    """leg_changes: Hinsetzen aus hoch (-0.100, sit-safe) → direkt, kein Routing."""
    hoch_idx = len(_STANCE_MODES) - 1
    node._stance_idx = hoch_idx
    node._engine.radial_distance = _STANCE_MODES[hoch_idx].radial
    node._engine.body_height = _STANCE_MODES[hoch_idx].body_height  # -0.100
    resp = node._on_sit_down(Trigger.Request(), Trigger.Response())
    assert resp.success is True
    assert node._pending_sitdown is False
    # leg_changes/S6: hoch -0.100 > _SIT_SAFE_MIN_BH → direkt hinsetzen (kein
    # Routing über mittel); standup_radial 0.21 ≠ walk 0.160 → Phase-1-Reposition.
    assert node._engine.state == GaitEngine.STATE_REPOSITION


def test_sit_from_mittel_direct(node):
    """Hinsetzen aus mittel (sit-safe) → direkt (kein Routing über mittel)."""
    resp = node._on_sit_down(Trigger.Request(), Trigger.Response())
    assert resp.success is True
    assert node._pending_sitdown is False
    # Direkt in die Sitdown-Sequenz (Phase-1-Reposition Füße raus), nicht Stance-Switch.
    assert node._engine.state == GaitEngine.STATE_REPOSITION


# ----- Block I Phase 10: free_leg über show_mode ----------------------- #

def test_free_leg_starts_show_from_low_stance(node):
    """
    FL-T8: ``show_mode='free_leg'`` startet die B4-Show — nicht mehr Platzhalter.

    Steht der Roboter schon tief, geht es direkt in SHOW_ENTER (kein
    Stance-Wechsel dazwischen).
    """
    node._stance_idx = _STANCE_FREE_LEG_IDX
    node._engine._state = GaitEngine.STATE_STANDING
    assert node._set_show_mode('free_leg') == 'free_leg'
    assert node._engine.state == GaitEngine.STATE_SHOW_ENTER
    assert node._pending_show_enter is False


def test_free_leg_switches_stance_first(node):
    """
    FL-T10: aus mittel/hoch wird ZUERST auf tief gewechselt.

    Der Show-Start wartet dann auf das Ende des Switches (``_pending_show_enter``,
    Muster von ``_pending_sitdown``) — sonst liefe start_show_enter gegen den
    STANCE_SWITCH-State und würde abgelehnt.
    """
    node._stance_idx = _STANCE_DEFAULT_IDX      # mittel
    node._engine._state = GaitEngine.STATE_STANDING
    assert node._set_show_mode('free_leg') == 'free_leg'
    assert node._engine.state == GaitEngine.STATE_STANCE_SWITCH
    assert node._pending_show_enter is True
    # Die App muss den Modus schon während des Wechsels sehen: _set_show_mode
    # liefert 'free_leg' zurück (der Aufrufer schreibt es nach _show_mode, aus
    # dem _publish_status das Status-Feld speist) — nicht erst nach dem Switch.


def test_free_leg_none_exits_show(node):
    """``show_mode='none'`` verlässt die Show über SHOW_EXIT (Rückweg immer offen)."""
    node._stance_idx = _STANCE_FREE_LEG_IDX
    node._engine._state = GaitEngine.STATE_STANDING
    node._show_mode = node._set_show_mode('free_leg')   # wie _apply_param
    node._engine._state = GaitEngine.STATE_SHOW_ACTIVE
    assert node._set_show_mode('none') == 'none'
    assert node._engine.state == GaitEngine.STATE_SHOW_EXIT


def test_free_leg_none_cancels_pending_start(node):
    """
    Ein noch wartender Show-Start wird durch ``none`` verworfen.

    Sonst liefe die Show nach dem Stance-Wechsel doch noch an, obwohl der
    Nutzer sie bereits abgewählt hat.
    """
    node._stance_idx = _STANCE_DEFAULT_IDX
    node._engine._state = GaitEngine.STATE_STANDING
    node._show_mode = node._set_show_mode('free_leg')   # wie _apply_param
    assert node._pending_show_enter is True
    node._set_show_mode('none')
    assert node._pending_show_enter is False


def test_reset_show_mode_cancels_pending_start(node):
    """Recovery/Hinsetzen verwirft einen wartenden Show-Start ebenfalls."""
    node._stance_idx = _STANCE_DEFAULT_IDX
    node._engine._state = GaitEngine.STATE_STANDING
    node._show_mode = node._set_show_mode('free_leg')   # wie _apply_param
    node._reset_show_mode('test')
    assert node._pending_show_enter is False
    assert node._show_mode == 'none'
