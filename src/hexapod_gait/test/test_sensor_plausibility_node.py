"""
Node-Wiring für Sensor-Plausibilität / Fault-Fail-Safe (Block A5 S4-5).

Prüft: Param-Defaults, Live-Tuning + Validierung (inkl. apex-Band-Cross-Check
und inject-Format), Fault-Inject auf den Kontakt-Cache, Maskierung geflaggter
Beine (S4-2 adaptiv-aus via engine._adaptive_masked_legs + S4-4 aus der
Stütz-Zählung), End-to-End-Flag via inject stuck_on, und der dead_ticks-Rebuild
bei cycle_time-Änderung.
"""

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import GaitNode
from hexapod_gait.sensor_health_monitor import REASON_STUCK_ON
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


def test_params_default(node):
    assert node.get_parameter('sensor_plausibility_enable').value is False
    assert node._sensor_plausibility_enable is False
    assert node.get_parameter('sensor_apex_band_low').value == pytest.approx(0.3)
    assert node.get_parameter('sensor_apex_band_high').value == pytest.approx(0.7)
    assert node.get_parameter('sensor_apex_fault_cycles').value == 3
    assert node.get_parameter('sensor_dead_cycles').value == 2
    assert node.get_parameter('sensor_fault_inject').value == ''
    assert node._sensor_fault_inject is None
    assert node._sensor_faulty == set()
    assert node._sensor_health_monitor is not None


@pytest.mark.parametrize('name,ptype,value', [
    ('sensor_apex_band_low', Parameter.Type.DOUBLE, -0.1),
    ('sensor_apex_band_high', Parameter.Type.DOUBLE, 1.5),
    ('sensor_apex_fault_cycles', Parameter.Type.INTEGER, 0),
    ('sensor_dead_cycles', Parameter.Type.INTEGER, 0),
    ('sensor_fault_inject', Parameter.Type.STRING, '7:stuck_on'),
    ('sensor_fault_inject', Parameter.Type.STRING, '3:wobble'),
    ('sensor_fault_inject', Parameter.Type.STRING, 'garbage'),
])
def test_invalid_params_rejected(node, name, ptype, value):
    res = node.set_parameters([Parameter(name, ptype, value)])
    assert not res[0].successful


def test_apex_band_cross_constraint_rejected(node):
    # low >= high muss abgelehnt werden (atomar gegen den jeweils anderen).
    res = node.set_parameters([
        Parameter('sensor_apex_band_low', Parameter.Type.DOUBLE, 0.8),
    ])
    assert not res[0].successful
    # Beide gemeinsam mit low < high → ok.
    res = node.set_parameters([
        Parameter('sensor_apex_band_low', Parameter.Type.DOUBLE, 0.4),
        Parameter('sensor_apex_band_high', Parameter.Type.DOUBLE, 0.6),
    ])
    assert res[0].successful


def test_live_tuning_rebuilds_monitor(node):
    res = node.set_parameters([
        Parameter('sensor_apex_fault_cycles', Parameter.Type.INTEGER, 4),
        Parameter('sensor_dead_cycles', Parameter.Type.INTEGER, 4),
    ])
    assert res[0].successful
    assert node._sensor_apex_fault_cycles == 4
    assert node._sensor_dead_cycles == 4
    # apex_fault_cycles = Pässe (keine Tick-Umrechnung).
    assert node._sensor_health_monitor._apex_fault_cycles == 4
    # dead_ticks = 4 · cycle_time(2.0) · tick_rate(50) = 400.
    assert node._sensor_health_monitor._dead_ticks == 400


def test_fault_inject_parse_and_apply(node):
    res = node.set_parameters([
        Parameter('sensor_fault_inject', Parameter.Type.STRING, '2:stuck_on'),
    ])
    assert res[0].successful
    assert node._sensor_fault_inject == (2, True)
    node._foot_contact[2] = False
    node._apply_sensor_fault_inject()
    assert node._foot_contact[2] is True  # stuck_on klemmt auf Kontakt

    node.set_parameters([
        Parameter('sensor_fault_inject', Parameter.Type.STRING, '5:stuck_off'),
    ])
    assert node._sensor_fault_inject == (5, False)
    node._foot_contact[5] = True
    node._apply_sensor_fault_inject()
    assert node._foot_contact[5] is False  # stuck_off klemmt auf kein-Kontakt

    node.set_parameters([
        Parameter('sensor_fault_inject', Parameter.Type.STRING, 'none'),
    ])
    assert node._sensor_fault_inject is None


def test_disabled_no_masking(node):
    # enable false → Health-Monitor reset, kein Bein maskiert.
    node._sensor_faulty = {3}
    node._update_sensor_health(0.5)
    assert node._sensor_faulty == set()


def test_masking_excludes_from_adaptive(node):
    # geflaggtes Bein → engine bekommt es als adaptiv-maskiert durchgereicht.
    node._sensor_faulty = {2}
    node._update_foot_contacts(0.3)
    assert node._engine._adaptive_masked_legs == {2}


def test_masking_excludes_from_support_freeze(node):
    # Alle Beine ohne Halt + Slip scharf: ohne Maskierung Freeze, mit ALLEN
    # Beinen maskiert KEIN Freeze (alle aus der Zählung).
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('slip_grace_stance_phase', Parameter.Type.DOUBLE, 0.0),
        Parameter('slip_debounce_ticks', Parameter.Type.INTEGER, 2),
        Parameter('slip_min_lost_legs', Parameter.Type.INTEGER, 1),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = False
    node._sensor_faulty = {1, 2, 3, 4, 5, 6}  # alle maskiert
    frozen = False
    for _ in range(8):
        frozen = node._update_support(0.5) or frozen
    assert frozen is False
    assert node._support_monitor.freeze_latched is False


def test_never_contacted_leg_no_false_freeze(node):
    # T2-Szenario: ein Bein (2), das diese Episode NIE Kontakt hatte (stuck_off
    # von Start), darf bei aktivem S4-5 KEINEN Slip-Freeze auslösen — sonst
    # Fehl-Freeze, BEVOR die dead-Erkennung (2 Cycles) maskieren kann. Die
    # anderen Beine haben Kontakt.
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('sensor_plausibility_enable', Parameter.Type.BOOL, True),
        Parameter('slip_grace_stance_phase', Parameter.Type.DOUBLE, 0.0),
        Parameter('slip_debounce_ticks', Parameter.Type.INTEGER, 2),
        Parameter('slip_min_lost_legs', Parameter.Type.INTEGER, 1),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    frozen = False
    for i in range(120):  # ~2.4 s @ cycle 2.0 → Bein 2 ist mehrfach in Stance
        for leg_id in range(1, 7):
            node._foot_contact[leg_id] = (leg_id != 2)  # nur Bein 2 nie Kontakt
        frozen = node._update_support(0.02 * i) or frozen
    assert frozen is False
    assert node._support_monitor.freeze_latched is False


def test_never_contacted_freezes_without_plausibility(node):
    # Ohne S4-5 (plausibility off) behält S4-4 sein verifiziertes Verhalten: ein
    # nie-kontaktiertes Stance-Bein freezt (der ever_contacted-Ausschluss ist an
    # sensor_plausibility_enable gekoppelt).
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('slip_grace_stance_phase', Parameter.Type.DOUBLE, 0.0),
        Parameter('slip_debounce_ticks', Parameter.Type.INTEGER, 2),
        Parameter('slip_min_lost_legs', Parameter.Type.INTEGER, 1),
    ])  # sensor_plausibility_enable bleibt False (Default)
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = False
    frozen = False
    for _ in range(4):
        frozen = node._update_support(0.5) or frozen
    assert frozen is True


def test_contacted_then_lost_leg_still_freezes(node):
    # Gegenprobe: ein Bein, das HATTE Kontakt und verliert ihn (echter Slip/Kante)
    # → Freeze. Der ever_contacted-Ausschluss greift NUR für nie-kontaktierte.
    node.set_parameters([
        Parameter('slip_detection_enable', Parameter.Type.BOOL, True),
        Parameter('slip_grace_stance_phase', Parameter.Type.DOUBLE, 0.0),
        Parameter('slip_debounce_ticks', Parameter.Type.INTEGER, 2),
        Parameter('slip_min_lost_legs', Parameter.Type.INTEGER, 1),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    # Phase 1: Kontakt etablieren (ever_contacted).
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = True
    node._update_support(0.5)
    # Phase 2: Halt verlieren → Freeze.
    for leg_id in range(1, 7):
        node._foot_contact[leg_id] = False
    frozen = False
    for _ in range(4):
        frozen = node._update_support(0.5) or frozen
    assert frozen is True


def test_sensor_health_resets_on_active_freeze(node):
    # Bei aktivem Safety-Freeze keine Geister-Flags: reset + skip (Problem B).
    node.set_parameters([
        Parameter('sensor_plausibility_enable', Parameter.Type.BOOL, True),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    node._sensor_faulty = {3}
    node._slip_freeze_fired = True
    node._update_sensor_health(0.5)
    assert node._sensor_faulty == set()


def test_inject_stuck_on_flags_and_masks_end_to_end(node):
    # inject stuck_on + plausibility an → Bein wird (im WALKING) geflaggt.
    # apex_fault_cycles 2 (schnell), dead_cycles hoch (stuck-on greift, nicht dead).
    node.set_parameters([
        Parameter('sensor_plausibility_enable', Parameter.Type.BOOL, True),
        Parameter('sensor_apex_fault_cycles', Parameter.Type.INTEGER, 2),
        Parameter('sensor_dead_cycles', Parameter.Type.INTEGER, 50),
        Parameter('sensor_fault_inject', Parameter.Type.STRING, '3:stuck_on'),
    ])
    node._engine.set_command(0.05, 0.0, 0.0, 0.0)  # WALKING
    assert node._engine.state == GaitEngine.STATE_WALKING
    flagged = False
    # 400 Ticks @ dt 0.02 = 8 s = 4 Cycles (cycle_time 2.0) → ≥ 2 volle Apex-Pässe.
    for i in range(400):
        t = 0.02 * i
        node._apply_sensor_fault_inject()
        node._update_sensor_health(t)
        if 3 in node._sensor_faulty:
            flagged = True
            break
    assert flagged
    assert node._sensor_health_monitor._leg[3].reason == REASON_STUCK_ON


def test_dead_ticks_recomputed_on_cycle_time(node):
    # cycle_time-Änderung muss dead_ticks (Cycles → Ticks) neu rechnen.
    before = node._sensor_health_monitor._dead_ticks  # 2·2.0·50 = 200
    assert before == 200
    res = node.set_parameters([
        Parameter('cycle_time', Parameter.Type.DOUBLE, 1.0),
    ])
    assert res[0].successful
    assert node._sensor_health_monitor._dead_ticks == 100  # 2·1.0·50


def test_not_walking_resets_latch(node):
    node.set_parameters([
        Parameter('sensor_plausibility_enable', Parameter.Type.BOOL, True),
    ])
    # STANDING → reset, kein Bein maskiert.
    assert node._engine.state == GaitEngine.STATE_STANDING
    node._sensor_faulty = {4}
    node._update_sensor_health(0.5)
    assert node._sensor_faulty == set()
