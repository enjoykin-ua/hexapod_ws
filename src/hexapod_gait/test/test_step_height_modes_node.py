"""
Tests für die per-Modus-Deckel-Kopplung im gait_node (Block H1 + H2).

Die _STANCE_MODES-Tabelle trägt je Höhe die maximal Gate-validierte
step_height (H1: tief 0.04 / mittel 0.05 / hoch 0.08) UND step_length_max
(H2: tief 0.06 / mittel 0.08 / hoch 0.05 — engine-check-Transitions H2.1;
0.09 fiel im B:diagonal am S4-Floor). Beide Tabellenwerte sind zugleich
DECKEL für manuelles `param set` (Reject, _on_param_change) und werden
vom Stance-Switch automatisch gesetzt. Boot-Konsistenz: die Param-
Defaults == mittel-Tabellenwerte; params_file-Overrides über dem
Boot-Deckel werden im Init gedeckelt (WARN) — sie laufen nicht durch
den Set-Callback.

H2 zusätzlich: der Param-Server wird nach dem Stance-Switch DEFERRED
nachgezogen (_maybe_sync_stance_params, erst bei STANDING —
body_height/radial_distance sind standing_only, ein Sync im
STANCE_SWITCH würde vom eigenen Validator rejected). Und der
/hexapod_adjust_step_length-Handler clampt auf den Modus-Deckel
(er schreibt am Validator vorbei).

Das Modul-rclpy-Init setzt bewusst Overrides step_height:=0.09 und
step_length_max:=0.12 (über den Boot-Deckeln) — die Init-Check-Tests
beweisen damit die Deckelung.
"""

import math

from hexapod_gait.gait_engine import GaitEngine
from hexapod_gait.gait_node import (
    _GAIT_PARAMS,
    _STANCE_DEFAULT_IDX,
    _STANCE_MODES,
    GaitNode,
)
import pytest
import rclpy
from rclpy.parameter import Parameter
from std_srvs.srv import SetBool


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    # Overrides ÜBER den Boot-Deckeln (mittel sh 0.05 / sl 0.08) →
    # Init-Konsistenz-Checks müssen deckeln (test_boot_override_*).
    rclpy.init(args=[
        '--ros-args',
        '-p', 'step_height:=0.09',
        '-p', 'step_length_max:=0.12',
    ])
    yield
    rclpy.shutdown()


@pytest.fixture
def node():
    n = GaitNode()
    yield n
    n.destroy_node()


# ----- Tabelle + Default-Kopplung (pure, ohne Node) ---------------------


def test_stance_modes_table_pinned():
    """
    Pinne die Gate-validierten Tabellenwerte (H1.2 sh + H2.1 sl).

    Änderungen nur mit neuem Offline-Gate-Durchlauf (check + engine-check;
    H2.1: mittel sl 0.09 fiel im engine-check B:diagonal am S4-Floor —
    0.08 GREEN).
    """
    assert [tuple(m) for m in _STANCE_MODES] == [
        ('tief', 0.160, -0.065, 0.040, 0.060),
        ('mittel', 0.160, -0.080, 0.050, 0.080),
        ('hoch', 0.160, -0.100, 0.080, 0.050),
    ]


def test_step_height_default_equals_boot_mode():
    """Konvention „Boot-Pose = Index 1 (mittel) = Param-Defaults"."""
    spec = next(s for s in _GAIT_PARAMS if s.name == 'step_height')
    assert spec.default == pytest.approx(
        _STANCE_MODES[_STANCE_DEFAULT_IDX].step_height)


def test_step_length_max_default_equals_boot_mode():
    """H2: auch der step_length_max-Default folgt der Boot-Konvention."""
    spec = next(s for s in _GAIT_PARAMS if s.name == 'step_length_max')
    assert spec.default == pytest.approx(
        _STANCE_MODES[_STANCE_DEFAULT_IDX].step_length_max)


def test_step_length_intent_max_within_boot_cap():
    """
    H2: intent_max ≤ mittel-Deckel — UND ≥ Boot-Default.

    Wäre intent_max < Boot-sl (der alte 0.070-Wert), würde ein
    „größer"-Intent den Wert SENKEN (Clamp-Artefakt).
    """
    intent_max = next(
        s for s in _GAIT_PARAMS if s.name == 'step_length_intent_max')
    sl_default = next(
        s for s in _GAIT_PARAMS if s.name == 'step_length_max')
    boot_cap = _STANCE_MODES[_STANCE_DEFAULT_IDX].step_length_max
    assert intent_max.default <= boot_cap + 1e-9
    assert intent_max.default >= sl_default.default - 1e-9


# ----- Init-Konsistenz-Check (Boot-Override umgeht den Validator) --------


def test_boot_override_capped_to_mode(node):
    """
    Init-Check deckelt einen Boot-Override über dem Modus-Deckel.

    params_file-/CLI-Override 0.09 > Boot-Deckel 0.05 → im Init auf den
    Deckel gesetzt (WARN) statt später IKError+Freeze auf HW.
    """
    cap = _STANCE_MODES[_STANCE_DEFAULT_IDX].step_height
    assert node._step_height == pytest.approx(cap)
    assert node._engine.step_height == pytest.approx(cap)


def test_boot_override_sl_capped_to_mode(node):
    """H2: Boot-Override step_length_max 0.12 > Deckel 0.08 → gedeckelt."""
    cap = _STANCE_MODES[_STANCE_DEFAULT_IDX].step_length_max
    assert node._step_length_max == pytest.approx(cap)
    assert node._engine.step_length_max == pytest.approx(cap)


# ----- Deckel-Reject im laufenden Betrieb --------------------------------


def test_cap_reject_above_current_mode(node):
    """0.08 im Boot-Modus (mittel, Deckel 0.05) → Reject mit Begründung."""
    res = node.set_parameters([
        Parameter('step_height', Parameter.Type.DOUBLE, 0.08),
    ])
    assert not res[0].successful
    assert 'exceeds validated max' in res[0].reason
    assert node._step_height == pytest.approx(0.05)  # unverändert


def test_cap_allows_at_and_below(node):
    """Deckel exakt + kleinere Werte sind erlaubt (nur oben gedeckelt)."""
    for value in (0.05, 0.03):
        res = node.set_parameters([
            Parameter('step_height', Parameter.Type.DOUBLE, value),
        ])
        assert res[0].successful, res[0].reason
        assert node._step_height == pytest.approx(value)


def test_cap_follows_stance_mode(node):
    """
    Der Deckel hängt am AKTUELLEN Stance-Modus.

    tief lehnt 0.05 ab, hoch erlaubt 0.08 — genau der User-HW-Befund
    (IKError je nach Höhe).
    """
    node._stance_idx = 0  # tief (white-box; Switch-Pfad separat getestet)
    res = node.set_parameters([
        Parameter('step_height', Parameter.Type.DOUBLE, 0.05),
    ])
    assert not res[0].successful
    assert "'tief'" in res[0].reason

    node._stance_idx = 2  # hoch
    res = node.set_parameters([
        Parameter('step_height', Parameter.Type.DOUBLE, 0.08),
    ])
    assert res[0].successful, res[0].reason
    assert node._step_height == pytest.approx(0.08)


# ----- Switch setzt die gekoppelte step_height automatisch ---------------


def test_switch_applies_mode_step_height(node):
    """
    Der Stance-Switch übernimmt die Tabellen-step_height gekoppelt.

    L2/R2-Pfad: _do_stance_switch(hoch) setzt sh 0.08 in Node UND Engine —
    die „nur valide Kombinationen durchschaltbar"-Kopplung.
    """
    assert node._engine.state == GaitEngine.STATE_STANDING
    ok = node._do_stance_switch(2)  # hoch
    assert ok
    assert node._stance_idx == 2
    assert node._step_height == pytest.approx(0.08)
    assert node._engine.state == GaitEngine.STATE_STANCE_SWITCH
    # Switch zu Ende fahren → Engine übernimmt Ziel-Modus komplett.
    node._engine.compute_joint_angles(1e6)
    assert node._engine.state == GaitEngine.STATE_STANDING
    assert node._engine.step_height == pytest.approx(0.08)
    assert node._engine.body_height == pytest.approx(-0.100)


def test_switch_down_caps_step_height(node):
    """Runterschalten deckelt automatisch: hoch (0.08) → tief (0.04)."""
    assert node._do_stance_switch(2)
    node._engine.compute_joint_angles(1e6)          # Switch fertig
    assert node._do_stance_switch(0)                # → tief
    assert node._step_height == pytest.approx(0.04)
    node._engine.compute_joint_angles(2e6)
    assert node._engine.step_height == pytest.approx(0.04)


# ----- Apex-Invariante (der physikalische Grund des Deckels) -------------


def test_mode_apex_stays_below_femur_wall():
    """
    Apex-Invariante: bh + sh ≤ −0.02 für jeden Modus.

    Die H1.2-gemessene Femur-Wand-Grenze — schützt vor unbedachten
    Tabellen-Änderungen ohne neuen Offline-Gate-Durchlauf.
    """
    for m in _STANCE_MODES:
        apex = m.body_height + m.step_height
        assert apex <= -0.02 + 1e-9, (
            f'{m.name}: Apex {apex:.3f} über der Femur-Wand-Grenze −0.02 — '
            f'Offline-Gate (H1.2) neu laufen lassen!')
        assert math.isfinite(apex)


# ===== Block H2 — step_length_max-Deckel + Switch-Kopplung + Sync ========


def test_sl_reject_above_current_mode(node):
    """0.09 im Boot-Modus (mittel, Deckel 0.08) → Reject (H2.1-RED-Zelle)."""
    res = node.set_parameters([
        Parameter('step_length_max', Parameter.Type.DOUBLE, 0.09),
    ])
    assert not res[0].successful
    assert 'exceeds validated max' in res[0].reason
    assert node._step_length_max == pytest.approx(0.08)  # unverändert


def test_sl_allows_at_and_below(node):
    """Deckel exakt + kleinere Werte sind erlaubt (nur oben gedeckelt)."""
    for value in (0.08, 0.05):
        res = node.set_parameters([
            Parameter('step_length_max', Parameter.Type.DOUBLE, value),
        ])
        assert res[0].successful, res[0].reason
        assert node._step_length_max == pytest.approx(value)
        assert node._engine.step_length_max == pytest.approx(value)


def test_sl_cap_follows_stance_mode(node):
    """
    Der sl-Deckel hängt am AKTUELLEN Stance-Modus.

    tief lehnt 0.07 ab (Deckel 0.06); hoch lehnt 0.06 ab (Deckel 0.05,
    der User-Sim-Befund out-of-reach) — mittel erlaubt 0.08.
    """
    node._stance_idx = 0  # tief (white-box; Switch-Pfad separat getestet)
    res = node.set_parameters([
        Parameter('step_length_max', Parameter.Type.DOUBLE, 0.07),
    ])
    assert not res[0].successful
    assert "'tief'" in res[0].reason

    node._stance_idx = 2  # hoch
    res = node.set_parameters([
        Parameter('step_length_max', Parameter.Type.DOUBLE, 0.06),
    ])
    assert not res[0].successful
    assert "'hoch'" in res[0].reason
    res = node.set_parameters([
        Parameter('step_length_max', Parameter.Type.DOUBLE, 0.05),
    ])
    assert res[0].successful, res[0].reason


def test_switch_applies_mode_step_length(node):
    """Der Stance-Switch übernimmt sl gekoppelt (hoch 0.05, zurück 0.08)."""
    assert node._do_stance_switch(2)  # hoch
    assert node._step_length_max == pytest.approx(0.05)
    assert node._engine.step_length_max == pytest.approx(0.05)
    node._engine.compute_joint_angles(1e6)          # Switch fertig
    assert node._do_stance_switch(1)                # zurück mittel
    assert node._step_length_max == pytest.approx(0.08)
    assert node._engine.step_length_max == pytest.approx(0.08)


def test_param_server_sync_deferred_until_standing(node):
    """
    H1-🟡-Fix: Param-Server-Sync erst bei Switch-ABSCHLUSS (STANDING).

    Im STANCE_SWITCH darf der Sync nicht laufen (body_height/radial sind
    standing_only — der eigene Validator würde rejecten). Nach Abschluss
    zieht _maybe_sync_stance_params alle vier gekoppelten Params nach —
    `ros2 param get` zeigt dann die Tabellenwerte statt der Boot-Werte.
    """
    assert node._do_stance_switch(2)  # hoch
    assert node._pending_stance_param_sync
    # Mid-Switch: Sync muss deferred bleiben (Param-Server zeigt alt).
    node._maybe_sync_stance_params()
    assert node._pending_stance_param_sync
    assert node.get_parameter('body_height').value == pytest.approx(-0.080)
    # Switch zu Ende fahren → STANDING → Sync läuft durch.
    node._engine.compute_joint_angles(1e6)
    assert node._engine.state == GaitEngine.STATE_STANDING
    node._maybe_sync_stance_params()
    assert not node._pending_stance_param_sync
    mode = _STANCE_MODES[2]
    assert node.get_parameter('radial_distance').value == pytest.approx(
        mode.radial)
    assert node.get_parameter('body_height').value == pytest.approx(
        mode.body_height)
    assert node.get_parameter('step_height').value == pytest.approx(
        mode.step_height)
    assert node.get_parameter('step_length_max').value == pytest.approx(
        mode.step_length_max)
    # Member/Engine unverändert konsistent (Apply war idempotent).
    assert node._body_height == pytest.approx(mode.body_height)
    assert node._engine.body_height == pytest.approx(mode.body_height)


def test_adjust_step_length_clamped_to_mode_cap(node):
    """
    /hexapod_adjust_step_length clampt auf den Modus-Deckel (H2).

    Der Intent-Handler schreibt _step_length_max am Validator vorbei —
    in hoch (Deckel 0.05) darf ein „größer"-Intent nicht über 0.05.
    """
    assert node._do_stance_switch(2)  # hoch → sl 0.05
    node._engine.compute_joint_angles(1e6)
    node._maybe_sync_stance_params()
    req = SetBool.Request()
    req.data = True   # größer
    resp = node._on_adjust_step_length(req, SetBool.Response())
    assert resp.success
    assert node._step_length_max == pytest.approx(0.05)  # geclampt
    assert node._engine.step_length_max == pytest.approx(0.05)
    # Kleiner geht weiterhin (intent_step 0.01).
    req.data = False
    node._on_adjust_step_length(req, SetBool.Response())
    assert node._step_length_max == pytest.approx(0.04)
