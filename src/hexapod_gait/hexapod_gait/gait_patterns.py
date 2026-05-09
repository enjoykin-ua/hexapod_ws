"""
Gangart-Definitionen als reine Daten.

Stufe F: alle realistischen statischen Gangarten unterscheiden sich nur
in zwei Werten — Phasen-Offset pro Bein und Swing-Duty (Anteil des
Cycles, in dem das Bein schwingt). Die Berechnungs-Logik in
``gait_engine`` ist für alle Patterns identisch.

Neue Gangart hinzufügen = neue ``GaitPattern``-Konstante + Eintrag in
``GAIT_PRESETS``. Kein Engine-Code-Change nötig.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GaitPattern:
    """
    Reine Daten-Beschreibung einer Gangart.

    Attribute:
        name: Identifier-String (matched ``GAIT_PRESETS``-Key).
        phase_offset_per_leg: Pro Bein-ID (1..6) der Phasen-Offset im
            Cycle, oder ``None`` wenn das Bein nie schwingt
            (Single-Leg-Modi). Offset in [0, 1).
        swing_duty: Anteil des Cycles im Swing-Status, in (0, 1).
            Stance-Anteil = 1 - swing_duty. Tripod nutzt 0.5 (50/50),
            Wave nutzt 1/6 (1 Bein gleichzeitig in der Luft, andere 5
            stützen).
    """

    name: str
    phase_offset_per_leg: dict[int, float | None]
    swing_duty: float

    def __post_init__(self):
        if not 0.0 < self.swing_duty < 1.0:
            raise ValueError(
                f'swing_duty must be in (0, 1), got {self.swing_duty}'
            )
        for leg_id, offset in self.phase_offset_per_leg.items():
            if not 1 <= leg_id <= 6:
                raise ValueError(
                    f'leg_id must be in 1..6, got {leg_id}'
                )
            if offset is not None and not 0.0 <= offset < 1.0:
                raise ValueError(
                    f'offset for leg {leg_id} must be in [0, 1) or None, '
                    f'got {offset}'
                )


def _single_leg(leg_id: int) -> GaitPattern:
    """Pattern für Stufe-E-Backward-Compat: nur ein Bein schwingt."""
    offsets: dict[int, float | None] = {i: None for i in range(1, 7)}
    offsets[leg_id] = 0.0
    return GaitPattern(
        name=f'single_leg_{leg_id}',
        phase_offset_per_leg=offsets,
        swing_duty=0.5,
    )


SINGLE_LEG_1 = _single_leg(1)
SINGLE_LEG_2 = _single_leg(2)
SINGLE_LEG_3 = _single_leg(3)
SINGLE_LEG_4 = _single_leg(4)
SINGLE_LEG_5 = _single_leg(5)
SINGLE_LEG_6 = _single_leg(6)

TRIPOD = GaitPattern(
    name='tripod',
    phase_offset_per_leg={
        1: 0.0,
        3: 0.0,
        5: 0.0,
        2: 0.5,
        4: 0.5,
        6: 0.5,
    },
    swing_duty=0.5,
)


GAIT_PRESETS: dict[str, GaitPattern] = {
    'single_leg_1': SINGLE_LEG_1,
    'single_leg_2': SINGLE_LEG_2,
    'single_leg_3': SINGLE_LEG_3,
    'single_leg_4': SINGLE_LEG_4,
    'single_leg_5': SINGLE_LEG_5,
    'single_leg_6': SINGLE_LEG_6,
    'tripod': TRIPOD,
}
