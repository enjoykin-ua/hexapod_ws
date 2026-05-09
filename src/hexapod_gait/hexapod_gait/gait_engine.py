"""
Gait-Engine — pro Tick Foot-Targets je Bein.

Stufe F: Daten-getriebene Gangart-Engine. Jede Gangart wird als
``GaitPattern`` (Phasen-Offsets + Swing-Duty) übergeben. Der Engine-
Algorithmus ist für alle Patterns identisch: pro Bein Phase berechnen,
dann Swing-Trajektorie oder Stand-Pose.

State: STANDING vs. WALKING via ``enable_walk``. STANDING → alle 6 Beine
in Stand-Pose, kein Cycle. WALKING → Pattern-Logik.

Stance-Penetration: Stufe E hatte einen ``_STANCE_PENETRATION``-Trick
mit asymmetrischem 5:1-Hebel. In Stufe F wurde dieser durch eine
**globale ``body_height``-Senkung um 5 mm** im Launch-File ersetzt
(siehe Design-Entscheidung 1 in ``docs/phase_5_progress.md``). Engine
braucht den Trick deshalb nicht mehr.

Pure-Python (math + hexapod_kinematics + gait_patterns), kein rclpy.
Einzeln testbar.
"""

from __future__ import annotations

from hexapod_gait.gait_patterns import GaitPattern
from hexapod_gait.trajectory_gen import stand_pose, swing_traj
from hexapod_kinematics import HEXAPOD, IKError, leg_ik


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]


class GaitEngine:
    """Daten-getriebene Gait-Engine (Stufe F)."""

    def __init__(
        self,
        pattern: GaitPattern,
        step_height: float,
        cycle_time: float,
        radial_distance: float,
        body_height: float,
        enable_walk: bool = False,
    ):
        if cycle_time <= 0.0:
            raise ValueError(
                f'cycle_time must be > 0, got {cycle_time}'
            )

        self.pattern = pattern
        self.step_height = step_height
        self.cycle_time = cycle_time
        self.radial_distance = radial_distance
        self.body_height = body_height
        self.enable_walk = enable_walk

    def compute_foot_targets(self, t: float) -> dict:
        """
        Berechne Foot-Position pro Bein im Bein-Frame zur Zeit t.

        STANDING (``enable_walk=False``): alle 6 Beine in Stand-Pose,
        kein Cycle.

        WALKING (``enable_walk=True``): pro Bein
        ``phase = ((t / cycle_time) + offset) % 1``. Wenn
        ``phase < swing_duty`` → Halbsinus-Schwung über
        ``swing_phase = phase / swing_duty`` ∈ [0, 1). Wenn
        ``phase >= swing_duty`` oder ``offset is None`` (Bein schwingt
        nie): Stand-Pose.
        """
        targets = {}
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            offset = self.pattern.phase_offset_per_leg.get(leg_id)

            if not self.enable_walk or offset is None:
                target = stand_pose(self.radial_distance, self.body_height)
            else:
                cycle_phase = (
                    (t / self.cycle_time) + offset
                ) % 1.0
                if cycle_phase < self.pattern.swing_duty:
                    swing_phase = cycle_phase / self.pattern.swing_duty
                    target = swing_traj(
                        phase=swing_phase,
                        radial_neutral=self.radial_distance,
                        body_height=self.body_height,
                        step_height=self.step_height,
                        step_length=0.0,
                    )
                else:
                    target = stand_pose(
                        self.radial_distance, self.body_height
                    )
            targets[leg.name] = target
        return targets

    def compute_joint_angles(self, t: float) -> dict:
        """
        Berechne Joint-Winkel pro Bein durch IK auf den Foot-Targets.

        Returns dict {leg_name: (theta_coxa, theta_femur, theta_tibia)}.
        Wirft IKError mit Bein-Kontext, falls IK out-of-reach trifft.
        """
        targets = self.compute_foot_targets(t)
        angles = {}
        for leg in HEXAPOD.legs:
            try:
                angles[leg.name] = leg_ik(*targets[leg.name], leg)
            except IKError as exc:
                raise IKError(
                    f'IK failed for {leg.name} at t={t:.3f}s, target='
                    f'{targets[leg.name]}: {exc}'
                ) from exc
        return angles
