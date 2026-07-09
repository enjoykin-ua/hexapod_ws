"""
Tests für die per-Modus-step_height-Kopplung im gait_node (Block H1).

Die _STANCE_MODES-Tabelle trägt je Höhe die maximal Gate-validierte
step_height (tief 0.04 / mittel 0.05 / hoch 0.08 — H1_step_height_modes_
progress.md). Der Tabellenwert ist zugleich DECKEL für manuelles
`param set step_height` (Reject, _on_param_change) und wird vom
Stance-Switch automatisch gesetzt. Boot-Konsistenz: der step_height-
Param-Default == mittel-Tabellenwert; params_file-Overrides über dem
Boot-Deckel werden im Init gedeckelt (WARN) — sie laufen nicht durch
den Set-Callback.

Das Modul-rclpy-Init setzt bewusst einen Override step_height:=0.09
(über dem Boot-Deckel) — der erste Test beweist damit den Init-Check.
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


@pytest.fixture(scope='module', autouse=True)
def rclpy_lifecycle():
    # Override ÜBER dem Boot-Deckel (mittel 0.05) → Init-Konsistenz-Check
    # muss deckeln (test_boot_override_capped_to_mode).
    rclpy.init(args=['--ros-args', '-p', 'step_height:=0.09'])
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
    Pinne die H1.2-Gate-validierten Tabellenwerte.

    Änderungen nur mit neuem Offline-Gate-Durchlauf (Plan §0-Tabelle).
    """
    assert [(m.name, m.radial, m.body_height, m.step_height)
            for m in _STANCE_MODES] == [
        ('tief', 0.160, -0.065, 0.040),
        ('mittel', 0.160, -0.080, 0.050),
        ('hoch', 0.160, -0.100, 0.080),
    ]


def test_step_height_default_equals_boot_mode():
    """Konvention „Boot-Pose = Index 1 (mittel) = Param-Defaults"."""
    spec = next(s for s in _GAIT_PARAMS if s.name == 'step_height')
    assert spec.default == pytest.approx(
        _STANCE_MODES[_STANCE_DEFAULT_IDX].step_height)


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
