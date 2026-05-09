"""
Gait-Engine — pro Tick Foot-Targets je Bein.

Stufe G: cmd_vel-getriebene State-Machine mit STANDING/WALKING/STOPPING.

- ``set_command(v_body_x, v_body_y, t)`` aktualisiert Soll-Geschwindigkeit
  und triggert ggf. State-Übergänge:
  - STANDING + |v_body| > eps → WALKING
  - WALKING + v_body ≈ 0       → STOPPING (sauberer Stopp, Frage 4 C)
  - STOPPING + |v_body| > eps  → WALKING (sofortiges Resume)
- ``compute_foot_targets(t)`` liefert Foot-Targets je nach State.
  STOPPING auto-transitioniert zu STANDING wenn alle Beine settled.

Body↔Bein-Frame: ``cmd_vel.linear.x`` ist im base_link-Frame, jedes
Bein hat eigenen ``mount_yaw``. Engine rotiert Body-Geschwindigkeit
pro Bein in dessen Frame via ``rotate_z(-mount_yaw, ...)``.

Stützphase-Vortrieb: in WALKING wird die Stance-Trajektorie aus
``trajectory_gen.stance_traj`` benutzt — Foot bewegt sich rückwärts
relativ zum Body, sodass der Body sich vorwärts bewegt.

Sauberer Stopp (Frage 4 C):
- Bein in Swing bei Stop-Trigger → fertig schwingen mit eingefrorener
  step_vec (Touchdown an alter Position), dann Neutral.
- Bein in Stance bei Stop-Trigger → Position bei Stop einfrieren und
  linear über ``_STANCE_SETTLING_TIME`` zu Neutral interpolieren.
- Wenn alle 6 Beine bei Neutral angekommen → State STANDING.

Pure-Python (math + hexapod_kinematics + gait_patterns + trajectory_gen),
kein rclpy. Einzeln testbar.
"""

from __future__ import annotations

from hexapod_gait.gait_patterns import GaitPattern
from hexapod_gait.trajectory_gen import stance_traj, stand_pose, swing_traj
from hexapod_kinematics import HEXAPOD, IKError, leg_ik, rotate_z


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]
Vec2 = tuple[float, float]

# Geschwindigkeits-Schwellwert: cmd_vel-Werte unterhalb gelten als 0.
# Klein genug dass Float-Noise kein WALKING triggert, groß genug dass
# user-eingegebene 0.001 nicht als Stopp interpretiert wird.
_V_BODY_EPSILON = 1e-4

# Settling-Zeit für Stütz-Beine in STOPPING: linear-Interpolation von
# Stance-Position bei Stop-Trigger zu Neutral. 0.3 s ist ein Kompromiss
# zwischen "schnell genug" und "JTC-konvergierbar".
_STANCE_SETTLING_TIME = 0.3

# Toleranz für "Bein bei Neutral angekommen" — Settling-Check.
_NEUTRAL_TOLERANCE = 1e-4


class GaitEngine:
    """cmd_vel-getriebene Gait-Engine mit State-Machine (Stufe G)."""

    STATE_STANDING = 'STANDING'
    STATE_WALKING = 'WALKING'
    STATE_STOPPING = 'STOPPING'

    def __init__(
        self,
        pattern: GaitPattern,
        step_height: float,
        cycle_time: float,
        radial_distance: float,
        body_height: float,
        step_length_max: float,
    ):
        if cycle_time <= 0.0:
            raise ValueError(
                f'cycle_time must be > 0, got {cycle_time}'
            )
        if step_length_max <= 0.0:
            raise ValueError(
                f'step_length_max must be > 0, got {step_length_max}'
            )

        self.pattern = pattern
        self.step_height = step_height
        self.cycle_time = cycle_time
        self.radial_distance = radial_distance
        self.body_height = body_height
        self.step_length_max = step_length_max

        self._stance_duration = cycle_time * (1.0 - pattern.swing_duty)
        self._linear_max = step_length_max / self._stance_duration

        self._state = self.STATE_STANDING
        self._v_body: Vec2 = (0.0, 0.0)
        self._v_body_at_stop: Vec2 = (0.0, 0.0)
        self._t_stop_start: float = 0.0
        # Pro-Bein-Cycle-Phase eingefroren beim Stop-Trigger.
        self._cycle_phase_at_stop: dict[int, float] = {}
        # Pro-Bein-Stance-Position eingefroren beim Stop-Trigger.
        self._stance_pos_at_stop: dict[int, Point3] = {}

    @property
    def state(self) -> str:
        return self._state

    @property
    def linear_max(self) -> float:
        """Max erlaubte Body-Geschwindigkeit (m/s) durch step_length_max."""
        return self._linear_max

    def set_command(
        self,
        v_body_x: float,
        v_body_y: float,
        t: float,
    ) -> bool:
        """
        Setze Soll-Body-Geschwindigkeit und trigger State-Übergänge.

        ``v_body_x``, ``v_body_y`` werden auf ``±linear_max`` geclamped.
        Returns True wenn geclampt wurde (für Log-Warning im Node).

        ``t`` ist die aktuelle Zeit (gleicher Reference-Frame wie für
        ``compute_foot_targets``). Wird für State-Übergangs-Zeitstempel
        gebraucht.
        """
        clamped = False
        if abs(v_body_x) > self._linear_max:
            v_body_x = (
                self._linear_max if v_body_x > 0 else -self._linear_max
            )
            clamped = True
        if abs(v_body_y) > self._linear_max:
            v_body_y = (
                self._linear_max if v_body_y > 0 else -self._linear_max
            )
            clamped = True

        is_zero = (
            abs(v_body_x) < _V_BODY_EPSILON
            and abs(v_body_y) < _V_BODY_EPSILON
        )

        if is_zero:
            if self._state == self.STATE_WALKING:
                self._enter_stopping(t)
            # In STANDING oder STOPPING: kein State-Change bei v=0.
        else:
            self._v_body = (v_body_x, v_body_y)
            if self._state != self.STATE_WALKING:
                self._state = self.STATE_WALKING

        return clamped

    def _enter_stopping(self, t: float) -> None:
        """State-Übergang WALKING → STOPPING. Friert pro Bein ein."""
        self._state = self.STATE_STOPPING
        self._v_body_at_stop = self._v_body
        self._t_stop_start = t
        self._cycle_phase_at_stop = {}
        self._stance_pos_at_stop = {}

        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            offset = self.pattern.phase_offset_per_leg.get(leg_id)
            if offset is None:
                continue
            cycle_phase = ((t / self.cycle_time) + offset) % 1.0
            self._cycle_phase_at_stop[leg_id] = cycle_phase
            if cycle_phase >= self.pattern.swing_duty:
                # War in Stance — Position einfrieren für Settling.
                step_vec_leg = self._compute_step_vec_leg(leg, self._v_body)
                stance_phase = (
                    (cycle_phase - self.pattern.swing_duty)
                    / (1.0 - self.pattern.swing_duty)
                )
                self._stance_pos_at_stop[leg_id] = stance_traj(
                    phase=stance_phase,
                    radial_neutral=self.radial_distance,
                    body_height=self.body_height,
                    step_vec=step_vec_leg,
                )

        self._v_body = (0.0, 0.0)

    def _compute_step_vec_leg(self, leg, v_body: Vec2) -> Vec2:
        """
        Body-Geschwindigkeit → Bein-Frame-Schritt-Vektor pro Cycle.

        ``step_vec_leg`` ist der **Body-Schritt im Bein-Frame** —
        also wie weit sich der Body während der Stance-Dauer in
        den lokalen Bein-Koordinaten bewegt. Die Foot-Bewegung ist
        die Inverse (wird in ``stance_traj`` und ``swing_traj``
        durch Plus/Minus-Symmetrie erzeugt).

        Vorzeichen: positiv — entspricht direkt der Body-
        Geschwindigkeit in Bein-Frame-Koordinaten. ``stance_traj``
        geht intern von +step/2 nach -step/2 (Foot relativ zum
        Body rückwärts), also ergibt sich für positive step_vec
        ein Vortrieb in positive Body-Richtung.
        """
        v_body_x, v_body_y = v_body
        v_leg_3 = rotate_z(
            (v_body_x, v_body_y, 0.0),
            -leg.mount_yaw,
        )
        return (
            v_leg_3[0] * self._stance_duration,
            v_leg_3[1] * self._stance_duration,
        )

    def compute_foot_targets(self, t: float) -> dict:
        """
        Berechne Foot-Position pro Bein im Bein-Frame zur Zeit t.

        Auto-transitioniert STOPPING → STANDING wenn alle Beine settled.
        """
        if self._state == self.STATE_STANDING:
            return self._compute_standing_targets()
        if self._state == self.STATE_WALKING:
            return self._compute_walking_targets(t)
        return self._compute_stopping_targets(t)

    def _compute_standing_targets(self) -> dict:
        neutral = stand_pose(self.radial_distance, self.body_height)
        return {leg.name: neutral for leg in HEXAPOD.legs}

    def _compute_walking_targets(self, t: float) -> dict:
        targets = {}
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            offset = self.pattern.phase_offset_per_leg.get(leg_id)
            if offset is None:
                targets[leg.name] = stand_pose(
                    self.radial_distance, self.body_height
                )
                continue

            cycle_phase = ((t / self.cycle_time) + offset) % 1.0
            step_vec_leg = self._compute_step_vec_leg(leg, self._v_body)

            if cycle_phase < self.pattern.swing_duty:
                swing_phase = cycle_phase / self.pattern.swing_duty
                targets[leg.name] = swing_traj(
                    phase=swing_phase,
                    radial_neutral=self.radial_distance,
                    body_height=self.body_height,
                    step_height=self.step_height,
                    step_vec=step_vec_leg,
                )
            else:
                stance_phase = (
                    (cycle_phase - self.pattern.swing_duty)
                    / (1.0 - self.pattern.swing_duty)
                )
                targets[leg.name] = stance_traj(
                    phase=stance_phase,
                    radial_neutral=self.radial_distance,
                    body_height=self.body_height,
                    step_vec=step_vec_leg,
                )
        return targets

    def _compute_stopping_targets(self, t: float) -> dict:
        """
        Berechne STOPPING-Foot-Targets pro Bein.

        Frage 4 C: Swing-Beine schwingen mit eingefrorener step_vec
        fertig, dann Neutral. Stance-Beine interpolieren linear von
        Stance-Pos-bei-Stop zu Neutral über ``_STANCE_SETTLING_TIME``.
        Auto-Transition zu STANDING wenn alle Beine bei Neutral.
        """
        targets = {}
        all_settled = True
        neutral = stand_pose(self.radial_distance, self.body_height)
        tau = t - self._t_stop_start

        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            offset = self.pattern.phase_offset_per_leg.get(leg_id)
            if offset is None:
                targets[leg.name] = neutral
                continue

            cycle_phase_at_stop = self._cycle_phase_at_stop.get(leg_id)
            if cycle_phase_at_stop is None:
                # Bein hatte beim Stopp keine aktive Phase — direkt Neutral.
                targets[leg.name] = neutral
                continue

            if cycle_phase_at_stop < self.pattern.swing_duty:
                # War in Swing: weiter schwingen mit eingefrorener step_vec.
                step_vec_leg = self._compute_step_vec_leg(
                    leg, self._v_body_at_stop
                )
                swing_remaining_time = (
                    (self.pattern.swing_duty - cycle_phase_at_stop)
                    * self.cycle_time
                )
                if tau < swing_remaining_time:
                    # Swing-Phase im "Resttück":
                    # phase=cycle_phase_at_stop, ..., bis swing_duty.
                    cycle_phase_now = (
                        cycle_phase_at_stop + tau / self.cycle_time
                    )
                    swing_phase = (
                        cycle_phase_now / self.pattern.swing_duty
                    )
                    targets[leg.name] = swing_traj(
                        phase=swing_phase,
                        radial_neutral=self.radial_distance,
                        body_height=self.body_height,
                        step_height=self.step_height,
                        step_vec=step_vec_leg,
                    )
                    all_settled = False
                else:
                    # Swing zu Ende — Bein landet, dann Neutral interpolieren.
                    landed_pos = swing_traj(
                        phase=1.0,
                        radial_neutral=self.radial_distance,
                        body_height=self.body_height,
                        step_height=self.step_height,
                        step_vec=step_vec_leg,
                    )
                    settle_tau = tau - swing_remaining_time
                    progress = min(
                        1.0, settle_tau / _STANCE_SETTLING_TIME
                    )
                    targets[leg.name] = _lerp(landed_pos, neutral, progress)
                    if progress < 1.0:
                        all_settled = False
            else:
                # War in Stance: linear interpolieren von Pos-bei-Stop
                # zu Neutral.
                stance_pos = self._stance_pos_at_stop[leg_id]
                progress = min(1.0, tau / _STANCE_SETTLING_TIME)
                targets[leg.name] = _lerp(stance_pos, neutral, progress)
                if progress < 1.0:
                    all_settled = False

        if all_settled:
            self._state = self.STATE_STANDING

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


def _lerp(p_start: Point3, p_end: Point3, t: float) -> Point3:
    """Linear-Interpolation zwischen zwei 3D-Punkten."""
    return (
        p_start[0] + (p_end[0] - p_start[0]) * t,
        p_start[1] + (p_end[1] - p_start[1]) * t,
        p_start[2] + (p_end[2] - p_start[2]) * t,
    )
