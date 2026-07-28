"""
Konsistenz-/Pin-Tests für das HW-Arbeitspreset ``hw_terrain.yaml``.

Das Preset ist der 3-Terminal-Alltags-Bringup (Stufe 8 / H2.6) — seine
Werte sind HW-getunt und sollen nur bewusst geändert werden (Muster:
Tabellen-Pins in test_step_height_modes_node / test_tempo_presets).

H2.6-Befund: die S4-4-Sim-Defaults (debounce 8 / min_lost 1, geeicht auf
cycle 2.0) feuerten bei Tempo "aggressiv" (cycle 1.5) einen
False-Positive-Freeze — das Preset fährt daher 14/2 (0.28 s Toleranz,
erst 2 gleichzeitig haltlose Beine). Tradeoff (Kanten-Schutz erst ab
2 Beinen) ist im YAML-Kommentar dokumentiert.

Zusätzlich: die Preset-Werte müssen die _on_param_change-Validator-
Ranges einhalten — params_file-Werte greifen zur Deklarations-Zeit am
Validator VORBEI (H1-Init-Deckel-Lehre), ein Range-Verstoß fiele sonst
erst auf der HW auf.
"""

import os

import yaml

_PRESET = os.path.join(
    os.path.dirname(__file__), '..', 'config', 'presets', 'hw_terrain.yaml')


def _load():
    with open(_PRESET) as f:
        data = yaml.safe_load(f)
    # Preset-Layout: ein Top-Level-Node-Key mit ros__parameters darunter.
    node_key = next(iter(data))
    return data[node_key]['ros__parameters']


def test_slip_block_pinned_h26_tuning():
    """
    Pinne die H2.6-getunten S4-4-Werte (aggressiv-tauglich).

    Änderung nur mit neuem HW-Befund (siehe H2_speed_presets_progress.md
    + YAML-Kommentar; Sim-Code-Defaults 8/1 bleiben davon unberührt).
    """
    p = _load()
    assert p['slip_detection_enable'] is True
    assert p['slip_debounce_ticks'] == 14
    assert p['slip_min_lost_legs'] == 2
    assert p['slip_grace_stance_phase'] == 0.6
    assert p['cliff_depth'] == 0.03


def test_slip_block_within_validator_ranges():
    """Preset-Werte halten die _on_param_change-Ranges ein (Block 1k)."""
    p = _load()
    assert p['slip_debounce_ticks'] >= 1
    assert 1 <= p['slip_min_lost_legs'] <= 6
    assert 0.0 <= p['slip_grace_stance_phase'] < 1.0
    assert p['cliff_depth'] >= 0.0


# ----- Block I Phase 9 — Feld-Fail-safe + App-Pfad --------------------- #

def test_comms_loss_fail_safe_pinned():
    """
    Pinne den Comms-Loss-Fail-safe (Phase 9).

    Bricht die Funkverbindung ab, setzt sich der Roboter nach dieser Zeit
    selbst hin, statt bestromt stehen zu bleiben. Der Wert ist eine
    bewusste Feld-Entscheidung (lang genug für einen Funkschatten, kurz
    genug gegen Dauerlast) — Änderung nur mit neuem Feld-Befund.
    """
    p = _load()
    assert p['comms_loss_sitdown_timeout'] == 25.0


def test_comms_loss_within_validator_range():
    """
    Der Wert muss die gait_node-fp_range einhalten (0.0 .. 30.0).

    params_file-Werte greifen zur Deklarations-Zeit am Set-Callback vorbei —
    ein Range-Verstoß fiele sonst erst auf der HW auf.
    """
    p = _load()
    assert 0.0 <= p['comms_loss_sitdown_timeout'] <= 30.0


def test_preset_has_no_structural_params():
    """
    Das Preset darf KEINE Struktur-Params enthalten.

    Seit Phase 9 lädt auch der App-Pfad dieses Preset
    (bringup_ondemand mode:=real). Da ``params_file`` gegen die
    Inline-Launch-Args gewinnt, würde ein hier gesetztes
    ``auto_standup_on_start`` den Bauch-Start aushebeln — der Roboter
    stünde beim App-Start unaufgefordert auf. Ebenso würden
    ``use_sim_time``/``robot_description`` den HW-Pfad brechen.
    """
    p = _load()
    for forbidden in (
        'auto_standup_on_start', 'use_sim_time', 'robot_description',
        'robot_description_file',
    ):
        assert forbidden not in p, (
            f'{forbidden!r} gehört nicht ins Preset (überschreibt den Launch-Arg)'
        )
