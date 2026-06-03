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


# Block B3 — Helfer: phase_offset_per_leg aus einer expliziten HEBE-REIHENFOLGE.
#
# ⚠️ Offset-Konvention der Engine (s. _compute_walking_targets):
#   cycle_phase = (phi + offset) % 1 ; Swing wenn cycle_phase < swing_duty.
#   → ein Bein beginnt seinen Swing bei phi = (1 - offset) % 1, d.h. ein
#   GRÖSSERER Offset bedeutet FRÜHERES Heben. Das ist kontraintuitiv und hat in
#   B3.1 zu einer verdrehten Reihenfolge geführt. Dieser Helfer kapselt die
#   Umrechnung: man gibt die Reihenfolge der hebenden Gruppen an (Gruppe i hebt
#   bei Cycle-Phase i/num_phases), er liefert die passenden Offsets.
def _offsets_from_lift_order(
    groups: list[list[int]], num_phases: int,
) -> dict[int, float | None]:
    """Offsets, damit ``groups`` in genau dieser Reihenfolge heben."""
    offsets: dict[int, float | None] = {}
    for i, group in enumerate(groups):
        start = i / num_phases               # Cycle-Phase des Swing-Beginns
        off = (1.0 - start) % 1.0            # Engine: Swing-Start bei (1-off)%1
        for leg in group:
            offsets[leg] = off
    return offsets


# Block B3.1 — Wave (metachronal): nur 1 Bein gleichzeitig in der Luft, 5 tragen
# → last-ärmste/stabilste Gangart (langsamster Vortrieb). HEBE-Reihenfolge
# 3→2→1→4→5→6 (rechts hinten→vorne, dann links hinten→vorne; Layout 1=v-R,
# 2=m-R,3=h-R,4=h-L,5=m-L,6=v-L). swing_duty 1/6 + 6 Phasen → lückenloses Tiling,
# nie >1 Bein in der Luft. Engine generisch — kein Code-Change.
WAVE = GaitPattern(
    name='wave',
    phase_offset_per_leg=_offsets_from_lift_order(
        [[3], [2], [1], [4], [5], [6]], num_phases=6,
    ),
    swing_duty=1.0 / 6.0,
)

# Block B3.2 — Tetrapod: 3 Phasen, je ein DIAGONAL-Paar in der Luft (2 Beine),
# die anderen 4 tragen mittig-balanciert. Paare {1,4},{2,5},{3,6} heben in dieser
# Reihenfolge. swing_duty 1/3 + 3 Phasen → immer genau ein Paar in der Luft.
# Tempo zwischen Tripod und Wave.
TETRAPOD = GaitPattern(
    name='tetrapod',
    phase_offset_per_leg=_offsets_from_lift_order(
        [[1, 4], [2, 5], [3, 6]], num_phases=3,
    ),
    swing_duty=1.0 / 3.0,
)

# Block B3.3 — Ripple: überlappende Welle, 2 Beine gleichzeitig in der Luft,
# immer ECHT DIAGONAL (verschiedene Seite UND verschiedene Reihe). HEBE-Reihen-
# folge 1→5→3→6→2→4 (FR,ML,RR,FL,MR,RL — rundherum). swing_duty 1/3 (Fenster
# 2/6) bei 1/6-Phasen-Schritten → 2 überlappende Schwünge, immer diagonal.
#
# ⚠️ Reihenfolge per Stütz-Polygon-Marge gewählt (B3.3-Analyse 2026-06-03):
# „nur kontralateral" (z.B. 3,4,2,5,1,6) reicht NICHT — dort heben kurzzeitig
# BEIDE Hinterbeine (3+4) gleichzeitig → hintere Stütz-Kante ~durch den CoG →
# Marge nur 6,8 mm → kippelt. Die diagonale Folge 1,5,3,6,2,4 hält die zwei
# schwingenden Beine in verschiedener Reihe → Marge 120 mm (≈ Tripod/Tetrapod).
RIPPLE = GaitPattern(
    name='ripple',
    phase_offset_per_leg=_offsets_from_lift_order(
        [[1], [5], [3], [6], [2], [4]], num_phases=6,
    ),
    swing_duty=1.0 / 3.0,
)


GAIT_PRESETS: dict[str, GaitPattern] = {
    'single_leg_1': SINGLE_LEG_1,
    'single_leg_2': SINGLE_LEG_2,
    'single_leg_3': SINGLE_LEG_3,
    'single_leg_4': SINGLE_LEG_4,
    'single_leg_5': SINGLE_LEG_5,
    'single_leg_6': SINGLE_LEG_6,
    'tripod': TRIPOD,
    'wave': WAVE,
    'tetrapod': TETRAPOD,
    'ripple': RIPPLE,
}
