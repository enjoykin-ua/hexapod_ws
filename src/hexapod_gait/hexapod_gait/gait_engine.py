"""
Gait-Engine — pro Tick Foot-Targets je Bein.

Stufe E: Single-Leg-Schwung. Ein Bein (which_leg) führt periodisch
einen Halbsinus-Schwung aus, die anderen 5 halten Stand-Pose. Kein
Vortrieb, keine State-Machine (kommt in Stufe F).

Pure-Python (math + hexapod_kinematics), kein rclpy. Einzeln testbar.
"""

from __future__ import annotations

from hexapod_gait.trajectory_gen import stand_pose, swing_traj
from hexapod_kinematics import HEXAPOD, IKError, leg_ik


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]

# Extra Penetrations-Tiefe für das Swing-Bein in Stance-Phase. Nur das eine
# Bein, das gerade aus der Luft zurückkommt, wird minimal tiefer kommandiert,
# damit der JTC-Tracking-Lag sicher überwunden wird und der Foot tatsächlich
# Boden-Kontakt mit micro-Penetration erreicht. 5 mm reicht — die anderen 5
# Stütz-Beine halten den Body fest auf body_height-Niveau, das eine tiefer-
# gedrückte Bein hebt den Body NICHT (Hebel über 5 Stütz-Beine zu stark).
# Resultat: Stufe-D-Foot-Contact-Sensor sieht zuverlässig Penetration und
# togglet `true`/`false` synchron zum Schwung.
_STANCE_PENETRATION = 0.005


class GaitEngine:
    """Single-Leg-Schwung-Engine (Stufe E)."""

    def __init__(
        self,
        which_leg: int,
        step_height: float,
        cycle_time: float,
        radial_distance: float,
        body_height: float,
    ):
        if not 1 <= which_leg <= 6:
            raise ValueError(
                f'which_leg must be in 1..6, got {which_leg}'
            )
        if cycle_time <= 0.0:
            raise ValueError(
                f'cycle_time must be > 0, got {cycle_time}'
            )

        self.which_leg = which_leg
        self.step_height = step_height
        self.cycle_time = cycle_time
        self.radial_distance = radial_distance
        self.body_height = body_height

    def compute_foot_targets(self, t: float) -> dict:
        """
        Berechne Foot-Position pro Bein im Bein-Frame zur Zeit t.

        t in Sekunden seit Engine-Start. Cycle-Phase = (t / cycle_time) mod 1.

        Bein-Cycle ist 50/50 Swing/Stance (matches Tripod-Pattern aus
        Stufe F):
          - cycle_phase ∈ [0, 0.5]: SWING (Halbsinus über swing_phase 0..1)
          - cycle_phase ∈ [0.5, 1]: STANCE (Foot ruht in Stand-Pose)

        Ohne diesen Split würde der Foot nur instantan bei cycle_phase=0
        und =1 auf Stand-Höhe sein — JTC-Trajectory-Lag (0.04 s) lässt
        den realen Foot dann nie ganz auf den Boden, der Stufe-D-
        Foot-Contact-Sensor zeigt durchgängig false.
        """
        cycle_phase = (t / self.cycle_time) % 1.0
        targets = {}
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            if leg_id == self.which_leg:
                if cycle_phase < 0.5:
                    swing_phase = cycle_phase * 2.0
                    target = swing_traj(
                        phase=swing_phase,
                        radial_neutral=self.radial_distance,
                        body_height=self.body_height,
                        step_height=self.step_height,
                        step_length=0.0,
                    )
                else:
                    # Swing-Bein in Stance: 5 mm tiefer als andere 5 Beine,
                    # damit JTC-Tracking-Lag sicher überwunden wird und
                    # micro-Penetration für Sensor-Event entsteht.
                    target = stand_pose(
                        self.radial_distance,
                        self.body_height - _STANCE_PENETRATION,
                    )
            else:
                # Stütz-Beine an Default-body_height — halten Body-Höhe
                # konstant, damit das oben "tieferkommandierte" Bein
                # tatsächlich Penetration kriegt (Hebel-Verhältnis 5:1).
                target = stand_pose(self.radial_distance, self.body_height)
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
