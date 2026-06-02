"""
Gait-Engine — pro Tick Foot-Targets je Bein.

Stufe H: omnidirektionaler Walk. ``cmd_vel`` mit drei Komponenten
(linear.x, linear.y, angular.z) wird gleichzeitig verarbeitet. Body-
Velocity am Bein-Mount-Punkt wird per Rigid-Body-Formel
``v(P) = v_center + ω × P`` berechnet, dann pro Bein in dessen Frame
rotiert.

State-Machine (unverändert ggü. Stufe G):
- ``set_command(vx, vy, omega_z, t)`` aktualisiert Soll-Geschwindigkeit
  und triggert State-Übergänge:
  - STANDING + |v_total| > eps → WALKING
  - WALKING + |v_total| ≈ 0    → STOPPING (sauberer Stopp)
  - STOPPING + |v_total| > eps → WALKING (sofortiges Resume)
- ``compute_foot_targets(t)`` liefert Foot-Targets je nach State.
  STOPPING auto-transitioniert zu STANDING wenn alle Beine settled.

Clamping (Stufe-H-Design-Entscheidung 1, proportional):
Wenn die maximale Bein-Geschwindigkeit über alle 6 Beine
``|v_at_leg_mount|`` das Limit ``linear_max = step_length_max /
stance_duration`` überschreitet, werden alle drei Inputs (vx, vy,
omega_z) gleichzeitig mit dem Faktor ``linear_max / max_speed``
runterskaliert. Bewegungs-Richtung bleibt erhalten.

Stopp-Verhalten (Stufe-H-Design-Entscheidung 2, wie Stufe G):
Beine in Swing schwingen mit eingefrorener step_vec fertig (inkl.
omega-Beitrag), Stance-Beine interpolieren in 0.3 s zu Neutral.

Pure-Python (math + hexapod_kinematics + gait_patterns + trajectory_gen),
kein rclpy. Einzeln testbar.
"""

from __future__ import annotations

import math

from hexapod_gait.gait_patterns import GaitPattern
from hexapod_gait.trajectory_gen import stance_traj, stand_pose, swing_traj
from hexapod_kinematics import (
    HEXAPOD,
    IKError,
    JointLimits,
    leg_fk,
    leg_ik,
    rotate_z,
)


JointAngles = tuple[float, float, float]
Point3 = tuple[float, float, float]
Vec2 = tuple[float, float]

# Geschwindigkeits-Schwellwert: cmd_vel-Werte unterhalb gelten als 0.
# Klein genug dass Float-Noise kein WALKING triggert, groß genug dass
# user-eingegebene 0.001 nicht als Stopp interpretiert wird. Wird auf
# die maximale Bein-Geschwindigkeit angewandt (linear + omega·mount).
_V_BODY_EPSILON = 1e-4

# Settling-Zeit für Stütz-Beine in STOPPING: linear-Interpolation von
# Stance-Position bei Stop-Trigger zu Neutral. 0.3 s ist ein Kompromiss
# zwischen "schnell genug" und "JTC-konvergierbar".
_STANCE_SETTLING_TIME = 0.3


class GaitEngine:
    """Omnidirektionale Gait-Engine mit State-Machine (Stufe H)."""

    STATE_STANDING = 'STANDING'
    STATE_WALKING = 'WALKING'
    STATE_STOPPING = 'STOPPING'
    # Phase 13 Stage A: Smooth-Step-Lerp von einer beliebigen Start-Joint-
    # Position zur Stand-Pose. Wird via start_ramp() explizit getriggert
    # (vom gait_node bei erstem /joint_states-Empfang). In diesem State
    # ignoriert set_command() cmd_vel komplett, und compute_joint_angles()
    # liefert den Lerp-Punkt — kein IK-Aufruf waehrend Ramp.
    STATE_STARTUP_RAMP = 'STARTUP_RAMP'
    # Phase 13 Stage 0.7: kartesisches schürffreies Aufstehen vom Bauch.
    # Zwei Phasen in EINEM State (via start_cartesian_standup() getriggert):
    #   Phase 1 (Touchdown, bauch-gestützt): Füße kartesisch von der
    #     power_on_mid-Pose nach unten zu den Boden-Aufsetzpunkten
    #     (radial_distance, 0, body_height_start) — Füße noch unbelastet.
    #   Phase 2 (Push, Füße fix): x+y bleiben am Aufsetzpunkt, nur
    #     body_height rampt zu self.body_height → Körper hebt senkrecht
    #     über den fixen Füßen, kein Schürfen unter Last.
    # Ersetzt für das HW-Aufstehen den joint-space-STARTUP_RAMP (der bleibt
    # als Legacy-Mode erhalten). Wie STARTUP_RAMP wird cmd_vel ignoriert.
    STATE_CARTESIAN_STANDUP = 'CARTESIAN_STANDUP'
    # Phase 13 Stage 1 Teil 2.3: Tripod-Reposition nach dem Aufstehen — setzt
    # die Fuesse von der breiten Aufsteh-Pose (standup_radial_distance) auf die
    # naehere Walk-Pose (radial_distance) um, in zwei Tripod-Halb-Zyklen
    # (Gruppe {1,3,5} schwingt, dann {2,4,6}; nie >3 Beine in der Luft).
    # Auto-getriggert beim Standup-Ende, wenn sich die beiden radii
    # unterscheiden (sonst direkt STANDING). cmd_vel wird ignoriert bis STANDING.
    STATE_REPOSITION = 'REPOSITION'

    def __init__(
        self,
        pattern: GaitPattern,
        step_height: float,
        cycle_time: float,
        radial_distance: float,
        body_height: float,
        step_length_max: float,
        joint_limits: dict[str, JointLimits] | None = None,
        standup_radial_distance: float | None = None,
        reposition_cycle_time: float | None = None,
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

        # Phase 13 Stage 1 Teil 2.3 (Zwei-Phasen): standup_radial_distance =
        # breite, touchdown-sichere Aufsteh-Pose; reposition_cycle_time = Dauer
        # der Tripod-Umsetz-Bewegung. Beide Werte kommen vom Node/Config —
        # KEINE Pose-Zahl hier hartkodiert. Defaults (= radial_distance bzw.
        # cycle_time) → keine Reposition / Reposition so schnell wie ein Cycle.
        self.standup_radial_distance = (
            standup_radial_distance
            if standup_radial_distance is not None
            else radial_distance
        )
        self.reposition_cycle_time = (
            reposition_cycle_time
            if reposition_cycle_time is not None
            else cycle_time
        )

        # Stage 0.6: optional per-leg joint_limits (keyed by leg.name).
        # If None: IK runs lenient (= phase-5 behaviour). gait_node passes
        # the URDF-parsed limits in here on startup.
        self.joint_limits: dict[str, JointLimits] = joint_limits or {}

        self._state = self.STATE_STANDING
        self._v_body: Vec2 = (0.0, 0.0)
        self._omega: float = 0.0
        self._v_body_at_stop: Vec2 = (0.0, 0.0)
        self._omega_at_stop: float = 0.0
        self._t_stop_start: float = 0.0
        self._cycle_phase_at_stop: dict[int, float] = {}
        self._stance_pos_at_stop: dict[int, Point3] = {}

        # Phase 13 Stage A — STARTUP_RAMP-State-Daten.
        self._ramp_start_joints: dict[str, JointAngles] = {}
        self._ramp_target_joints: dict[str, JointAngles] = {}
        self._ramp_start_t: float = 0.0
        self._ramp_duration: float = 0.0

        # Phase 13 Stage 0.7 — CARTESIAN_STANDUP-State-Daten (Foot-Targets
        # im Bein-Frame pro Bein). start_foot = power_on_mid via leg_fk,
        # touchdown = Boden-Aufsetzpunkt, push_end = Stand-Pose.
        self._cart_start_foot: dict[str, Point3] = {}
        self._cart_touchdown: dict[str, Point3] = {}
        self._cart_push_end: dict[str, Point3] = {}
        self._cart_start_t: float = 0.0
        self._cart_duration: float = 0.0
        self._cart_phase1_frac: float = 0.4

        # Phase 13 Stage 1 Teil 2.3 — REPOSITION-State-Daten.
        self._repos_from_radial: float = radial_distance
        self._repos_to_radial: float = radial_distance
        self._repos_start_t: float = 0.0
        self._repos_duration: float = 0.0

    @property
    def state(self) -> str:
        return self._state

    @property
    def stance_duration(self) -> float:
        """
        Zeit pro Cycle in der ein Bein am Boden steht (s).

        Live aus ``cycle_time`` und ``pattern.swing_duty`` berechnet —
        Phase-11-Live-Tuning sicher gegen Cache-Drift.
        """
        return self.cycle_time * (1.0 - self.pattern.swing_duty)

    @property
    def linear_max(self) -> float:
        """
        Max erlaubte Bein-Geschwindigkeit (m/s) durch step_length_max.

        Pro Bein-Mount: ``|v_at_leg_mount| ≤ linear_max``. Bei pure
        Translation entspricht das ``|cmd_vel.linear| ≤ linear_max``.
        Bei Rotation gilt zusätzlich
        ``|omega·mount_xy_radius| ≤ linear_max``.

        Live aus ``step_length_max`` und ``stance_duration`` berechnet.
        """
        return self.step_length_max / self.stance_duration

    def _max_leg_speed(
        self,
        v_body_x: float,
        v_body_y: float,
        omega_z: float,
    ) -> float:
        """Max ``|v_at_leg_mount|`` über alle 6 Beine."""
        max_speed = 0.0
        for leg in HEXAPOD.legs:
            mx, my, _ = leg.mount_xyz
            vx_at_mount = v_body_x - omega_z * my
            vy_at_mount = v_body_y + omega_z * mx
            speed = math.hypot(vx_at_mount, vy_at_mount)
            if speed > max_speed:
                max_speed = speed
        return max_speed

    def start_ramp(
        self,
        start_joints: dict[str, JointAngles],
        t: float,
        duration: float,
    ) -> None:
        """
        Phase 13 Stage A: STARTUP_RAMP einleiten.

        ``start_joints`` ist die Start-Joint-Position pro Bein (typisch
        vom ersten /joint_states-Empfang im gait_node abgegriffen).
        ``duration`` ist die Ramp-Dauer in Sekunden. Smooth-Step-Lerp
        (``s = p²(3-2p)``) zur Default-Stand-Pose (Engine-Parameter
        ``radial_distance`` / ``body_height``) — sanftes Anlaufen +
        Abbremsen.

        Wenn ein Bein in ``start_joints`` fehlt, wird die Stand-Pose
        sowohl Start als auch Ziel — also keine Bewegung fuer das Bein.

        Setzt ``_state = STARTUP_RAMP``. ``compute_joint_angles`` setzt
        nach Ablauf automatisch zurueck auf STANDING.
        """
        if duration <= 0.0:
            raise ValueError(
                f'ramp duration must be > 0, got {duration}'
            )
        target = self._compute_stand_pose_joints()
        self._ramp_target_joints = target
        # Fehlende Beine: Start = Ziel → keine Bewegung dafuer.
        self._ramp_start_joints = {
            leg.name: start_joints.get(leg.name, target[leg.name])
            for leg in HEXAPOD.legs
        }
        self._ramp_start_t = t
        self._ramp_duration = duration
        self._state = self.STATE_STARTUP_RAMP

    def start_cartesian_standup(
        self,
        start_joints: dict[str, JointAngles],
        t: float,
        duration: float,
        phase1_fraction: float = 0.4,
        body_height_start: float = -0.0135,
    ) -> None:
        """
        Phase 13 Stage 0.7: kartesisches schürffreies Aufstehen einleiten.

        ``start_joints`` ist die gemessene Start-Pose pro Bein (vom ersten
        /joint_states-Empfang, = power_on_mid). Sie wird via ``leg_fk`` in
        kartesische Foot-Targets übersetzt. ``duration`` = Gesamtdauer (s),
        davon entfallen ``phase1_fraction`` auf Phase 1 (Touchdown), der Rest
        auf Phase 2 (Push). ``body_height_start`` = Foot-z relativ Coxa bei
        aufliegendem Bauch (≈ −0.0135 m, siehe standup_envelope_check.py).

        Touchdown- und Push-Ziel nutzen ``standup_radial_distance`` /
        ``body_height`` — die breite, touchdown-sichere Aufsteh-Pose (Stage 1
        Teil 2.3). Ist ``standup_radial_distance == radial_distance`` (Default),
        ist die Endpose wie bisher die Stand-Pose; sonst folgt nach dem Standup
        die Tripod-Reposition auf ``radial_distance`` (STATE_REPOSITION).

        Fehlt ein Bein in ``start_joints``, wird seine Start-Pose = Touchdown
        gesetzt (Phase 1 bewegungslos für dieses Bein).
        """
        if duration <= 0.0:
            raise ValueError(f'standup duration must be > 0, got {duration}')
        if not 0.0 < phase1_fraction < 1.0:
            raise ValueError(
                f'phase1_fraction must be in (0,1), got {phase1_fraction}'
            )
        touchdown_z = body_height_start
        self._cart_start_foot = {}
        self._cart_touchdown = {}
        self._cart_push_end = {}
        for leg in HEXAPOD.legs:
            touchdown = (self.standup_radial_distance, 0.0, touchdown_z)
            sj = start_joints.get(leg.name)
            if sj is None:
                start_foot: Point3 = touchdown
            else:
                start_foot = leg_fk(sj[0], sj[1], sj[2], leg)
            self._cart_start_foot[leg.name] = start_foot
            self._cart_touchdown[leg.name] = touchdown
            self._cart_push_end[leg.name] = stand_pose(
                self.standup_radial_distance, self.body_height,
            )
        self._cart_start_t = t
        self._cart_duration = duration
        self._cart_phase1_frac = phase1_fraction
        self._state = self.STATE_CARTESIAN_STANDUP

    def _compute_stand_pose_joints(self) -> dict[str, JointAngles]:
        """
        Stand-Pose-Joint-Angles via IK pro Bein.

        Mit den aktuellen Engine-Parametern ``radial_distance`` und
        ``body_height``. Helper fuer ``start_ramp`` — laeuft einmal
        beim Ramp-Trigger, nicht pro Tick.
        """
        targets = self._compute_standing_targets()
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            angles[leg.name] = leg_ik(*targets[leg.name], leg, leg_limits)
        return angles

    def set_command(
        self,
        v_body_x: float,
        v_body_y: float,
        omega_z: float,
        t: float,
    ) -> bool:
        """
        Setze Soll-Body-Geschwindigkeit und triggere State-Übergänge.

        Proportionales Clamping (Design-Entscheidung 1): wenn die
        maximale Bein-Geschwindigkeit über alle 6 Beine über
        ``linear_max`` liegt, werden alle drei Inputs mit demselben
        Faktor runterskaliert. Returns True wenn skaliert wurde.

        ``t`` ist die aktuelle Zeit (gleicher Reference-Frame wie für
        ``compute_foot_targets``).

        Phase 13 Stage A: in STATE_STARTUP_RAMP wird cmd_vel
        vollstaendig ignoriert (kein State-Change, kein Clamp). User
        muss warten bis Ramp fertig ist und Engine selbsttaetig auf
        STANDING wechselt.
        """
        # Phase 13 Stage A/0.7/2.3: cmd_vel waehrend Aufsteh-Sequenz (joint-
        # space ODER kartesisch) UND waehrend der Tripod-Reposition komplett
        # verwerfen — erst STANDING nimmt cmd_vel an.
        if self._state in (
            self.STATE_STARTUP_RAMP,
            self.STATE_CARTESIAN_STANDUP,
            self.STATE_REPOSITION,
        ):
            return False
        max_speed = self._max_leg_speed(v_body_x, v_body_y, omega_z)
        clamped = False
        linear_max = self.linear_max
        if max_speed > linear_max:
            scale = linear_max / max_speed
            v_body_x *= scale
            v_body_y *= scale
            omega_z *= scale
            clamped = True

        # is_zero check auf gemeinsame Skala — max_leg_speed nach Clamp.
        max_speed_after = self._max_leg_speed(
            v_body_x, v_body_y, omega_z
        )
        is_zero = max_speed_after < _V_BODY_EPSILON

        if is_zero:
            if self._state == self.STATE_WALKING:
                self._enter_stopping(t)
            # In STANDING oder STOPPING: kein State-Change bei v=0.
        else:
            self._v_body = (v_body_x, v_body_y)
            self._omega = omega_z
            if self._state != self.STATE_WALKING:
                self._state = self.STATE_WALKING

        return clamped

    def _enter_stopping(self, t: float) -> None:
        """State-Übergang WALKING → STOPPING. Friert pro Bein ein."""
        self._state = self.STATE_STOPPING
        self._v_body_at_stop = self._v_body
        self._omega_at_stop = self._omega
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
                step_vec_leg = self._compute_step_vec_leg(
                    leg, self._v_body, self._omega
                )
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
        self._omega = 0.0

    def _compute_step_vec_leg(
        self,
        leg,
        v_body: Vec2,
        omega: float,
    ) -> Vec2:
        """
        Body-Velocity → Bein-Frame-Schritt-Vektor pro Cycle.

        Standard-Rigid-Body-Velocity-Formel an Bein-Mount-Punkt:
        ``v_at_mount = v_body_center + omega × mount_xy``.
        In 2D: ``v_at_mount = (vx - omega·my, vy + omega·mx)``.

        Dann Rotation in Bein-Frame via ``rotate_z(-mount_yaw)``.

        Skalierung mit ``stance_duration`` ergibt den Body-Schritt im
        Bein-Frame (Foot-Bewegung ist die Inverse, durch
        Plus/Minus-Symmetrie in stance_traj/swing_traj erzeugt).
        """
        v_body_x, v_body_y = v_body
        mx, my, _ = leg.mount_xyz
        vx_at_mount = v_body_x - omega * my
        vy_at_mount = v_body_y + omega * mx
        v_leg_3 = rotate_z(
            (vx_at_mount, vy_at_mount, 0.0),
            -leg.mount_yaw,
        )
        stance_duration = self.stance_duration
        return (
            v_leg_3[0] * stance_duration,
            v_leg_3[1] * stance_duration,
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
            step_vec_leg = self._compute_step_vec_leg(
                leg, self._v_body, self._omega
            )

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
                targets[leg.name] = neutral
                continue

            if cycle_phase_at_stop < self.pattern.swing_duty:
                step_vec_leg = self._compute_step_vec_leg(
                    leg, self._v_body_at_stop, self._omega_at_stop
                )
                swing_remaining_time = (
                    (self.pattern.swing_duty - cycle_phase_at_stop)
                    * self.cycle_time
                )
                if tau < swing_remaining_time:
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
        Wirft IKError mit Bein-Kontext, falls IK out-of-reach trifft
        ODER (wenn ``self.joint_limits`` gesetzt ist) ein rad-Wert
        außerhalb der URDF-Joint-Limits liegt.

        Stage 0.6: gait_node fängt den IKError im Tick-Handler, ruft
        async den /hexapod_safety_freeze Service, und publisht in
        diesem Tick keine neue Trajectory → effektiver lokaler Stop.

        Phase 13 Stage A: in STATE_STARTUP_RAMP wird KEIN IK aufgerufen
        — der Rueckgabewert ist der Smooth-Step-Lerp zwischen
        ``_ramp_start_joints`` und ``_ramp_target_joints`` in Joint-
        Space. Wenn Ramp fertig ist (progress >= 1): State wechselt
        automatisch zu STANDING, Lerp-Endpunkt = Stand-Pose-IK wird
        returned.
        """
        # Phase 13 Stage A — STARTUP_RAMP: Joint-Space-Lerp ohne IK
        if self._state == self.STATE_STARTUP_RAMP:
            return self._compute_startup_ramp_angles(t)
        # Phase 13 Stage 0.7 — kartesisches Aufstehen (zwei Phasen, IK).
        if self._state == self.STATE_CARTESIAN_STANDUP:
            return self._compute_cartesian_standup_angles(t)
        # Phase 13 Stage 1 Teil 2.3 — Tripod-Reposition nach dem Aufstehen.
        if self._state == self.STATE_REPOSITION:
            return self._compute_reposition_angles(t)

        targets = self.compute_foot_targets(t)
        angles = {}
        for leg in HEXAPOD.legs:
            # Stage 0.6: per-leg joint_limits an IK durchreichen wenn
            # vorhanden. Ohne Limits-Dict: lenient (= Phase-5-Verhalten).
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(*targets[leg.name], leg, leg_limits)
            except IKError as exc:
                raise IKError(
                    f'IK failed for {leg.name} at t={t:.3f}s, target='
                    f'{targets[leg.name]}: {exc}'
                ) from exc
        return angles

    def _compute_startup_ramp_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        Smooth-Step-Lerp in Joint-Space waehrend STARTUP_RAMP.

        Mit ``progress = (t - _ramp_start_t) / _ramp_duration`` und
        Smooth-Step ``s = progress² * (3 - 2 * progress)``. Pro Joint:
        ``angle = start + (target - start) * s``. Bei progress >= 1
        wird ``_state`` auf STANDING zurueckgesetzt und der Target-
        Endpunkt geliefert — JTC interpoliert dann von dort weiter im
        normalen Stand-Pose-IK-Flow.
        """
        tau = t - self._ramp_start_t
        if self._ramp_duration <= 0.0:
            # Defensive: sollte durch start_ramp()-Check nie passieren
            self._state = self.STATE_STANDING
            return dict(self._ramp_target_joints)

        progress = tau / self._ramp_duration
        if progress >= 1.0:
            self._state = self.STATE_STANDING
            return dict(self._ramp_target_joints)

        # Smooth-Step: s(0)=0, s(1)=1, s'(0)=s'(1)=0 — Geschwindigkeits-
        # Null an beiden Enden, weicher Anlauf + Abbremsen.
        s = progress * progress * (3.0 - 2.0 * progress)

        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            start = self._ramp_start_joints.get(
                leg.name, self._ramp_target_joints[leg.name],
            )
            target = self._ramp_target_joints[leg.name]
            angles[leg.name] = (
                start[0] + (target[0] - start[0]) * s,
                start[1] + (target[1] - start[1]) * s,
                start[2] + (target[2] - start[2]) * s,
            )
        return angles

    def _compute_cartesian_standup_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        Kartesisches Aufstehen: pro Tick Foot-Targets → IK (Stage 0.7).

        ``progress = (t - _cart_start_t) / _cart_duration``.
        - Phase 1 (progress < phase1_frac): Foot kartesisch von start_foot
          → touchdown (Smooth-Step) — bauch-gestützt, Füße unbelastet.
        - Phase 2 (sonst): x+y FIX am Touchdown, nur z (body_height) von
          touchdown_z → push_end_z (Smooth-Step) → Körper hebt senkrecht
          über den fixen Füßen, kein Schürfen.
        Bei progress >= 1: State → STANDING, Stand-Pose-IK geliefert.
        IK-Limit-/Reach-Verletzung wirft IKError mit Bein-Kontext (wie
        compute_joint_angles) → gait_node fängt sie im Tick-Handler.
        """
        tau = t - self._cart_start_t
        if self._cart_duration <= 0.0:
            # Defensive: start_cartesian_standup() prueft duration > 0.
            self._finish_standup(t)
            return self._cartesian_standup_ik(self._cart_push_end, t)
        progress = tau / self._cart_duration
        if progress >= 1.0:
            self._finish_standup(t)
            return self._cartesian_standup_ik(self._cart_push_end, t)

        p1 = self._cart_phase1_frac
        targets: dict[str, Point3] = {}
        for leg in HEXAPOD.legs:
            touchdown = self._cart_touchdown[leg.name]
            if progress < p1:
                # Phase 1 — Touchdown: kartesischer Smooth-Step-Lerp.
                sub = progress / p1
                s = sub * sub * (3.0 - 2.0 * sub)
                targets[leg.name] = _lerp(
                    self._cart_start_foot[leg.name], touchdown, s,
                )
            else:
                # Phase 2 — Push: x+y fix, nur body_height (z) rampen.
                sub = (progress - p1) / (1.0 - p1)
                s = sub * sub * (3.0 - 2.0 * sub)
                end = self._cart_push_end[leg.name]
                z = touchdown[2] + (end[2] - touchdown[2]) * s
                targets[leg.name] = (touchdown[0], touchdown[1], z)
        return self._cartesian_standup_ik(targets, t)

    def _cartesian_standup_ik(
        self, foot_targets: dict[str, Point3], t: float,
    ) -> dict[str, JointAngles]:
        """IK pro Bein fuer die Standup-Targets, IKError mit Bein-Kontext."""
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(
                    *foot_targets[leg.name], leg, leg_limits,
                )
            except IKError as exc:
                raise IKError(
                    f'cartesian standup IK failed for {leg.name} at '
                    f't={t:.3f}s, target={foot_targets[leg.name]}: {exc}'
                ) from exc
        return angles

    # ----- Phase 13 Stage 1 Teil 2.3: Standup → Reposition → Walk -----

    # Toleranz, ab der eine Reposition lohnt: < 1 mm radial-Differenz →
    # direkt STANDING (kein unnötiger Tripod-Umsetz-Cycle).
    _REPOSITION_EPS = 1e-3

    def _finish_standup(self, t: float) -> None:
        """
        Übergang nach dem kartesischen Aufstehen.

        Unterscheiden sich ``standup_radial_distance`` (Aufsteh-Pose) und
        ``radial_distance`` (Walk-Pose) um mehr als ``_REPOSITION_EPS``, wird
        die Tripod-Reposition gestartet (STATE_REPOSITION); sonst direkt
        STANDING. Wertneutral — die konkreten radii kommen aus den Params.
        """
        if (
            abs(self.standup_radial_distance - self.radial_distance)
            > self._REPOSITION_EPS
        ):
            self.start_reposition(t)
        else:
            self._state = self.STATE_STANDING

    def start_reposition(self, t: float) -> None:
        """
        Tripod-Reposition einleiten (Stage 1 Teil 2.3).

        Füße von ``standup_radial_distance`` zu ``radial_distance`` (beide @
        ``body_height``), in zwei Tripod-Halb-Zyklen. Dauer =
        ``reposition_cycle_time``. Setzt STATE_REPOSITION.
        """
        self._repos_from_radial = self.standup_radial_distance
        self._repos_to_radial = self.radial_distance
        self._repos_start_t = t
        self._repos_duration = self.reposition_cycle_time
        self._state = self.STATE_REPOSITION

    def _reposition_foot(self, leg_id: int, progress: float) -> Point3:
        """
        Foot-Target eines Beins während der Reposition (Bein-Frame).

        Tripod: Gruppe mit phase_offset 0.0 ({1,3,5}) schwingt in der ersten
        Hälfte [0, 0.5), Gruppe 0.5 ({2,4,6}) in der zweiten [0.5, 1.0). Je
        Gruppe: nur die schwingenden 3 Beine in der Luft (statisch stabil).
        Schwing-Bein: radial Smooth-Step ``from→to`` + Halbsinus-Hub
        ``step_height``. Stütz-Bein: statisch auf ``from`` (vor seiner Hälfte)
        bzw. ``to`` (nach seiner Hälfte).
        """
        frm = self._repos_from_radial
        to = self._repos_to_radial
        bh = self.body_height
        offset = self.pattern.phase_offset_per_leg.get(leg_id)
        if offset is None:
            # Bein nicht im Pattern (z.B. single_leg) → direkt Ziel-Pose.
            return stand_pose(to, bh)

        swing_start = offset          # 0.0 (Gruppe A) oder 0.5 (Gruppe B)
        swing_end = offset + 0.5
        if progress < swing_start:
            return stand_pose(frm, bh)          # noch nicht umgesetzt
        if progress >= swing_end:
            return stand_pose(to, bh)           # schon umgesetzt
        # in der eigenen Schwing-Hälfte
        sub = (progress - swing_start) / 0.5
        s = sub * sub * (3.0 - 2.0 * sub)       # Smooth-Step für radial
        x = frm + (to - frm) * s
        z = bh + self.step_height * math.sin(math.pi * sub)  # Halbsinus-Hub
        return (x, 0.0, z)

    def _compute_reposition_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        STATE_REPOSITION: pro Tick Tripod-Foot-Targets → IK.

        ``progress = (t - _repos_start_t) / _repos_duration``. Bei
        progress >= 1: State → STANDING (Füße auf ``radial_distance``),
        Walk-Pose-IK geliefert. IK-Verletzung wirft IKError mit Bein-Kontext
        (wie der Standup) → gait_node fängt sie im Tick-Handler.
        """
        tau = t - self._repos_start_t
        if self._repos_duration <= 0.0:
            self._state = self.STATE_STANDING
            return self._reposition_ik(
                self._standing_targets(self._repos_to_radial), t,
            )
        progress = tau / self._repos_duration
        if progress >= 1.0:
            self._state = self.STATE_STANDING
            return self._reposition_ik(
                self._standing_targets(self._repos_to_radial), t,
            )
        targets: dict[str, Point3] = {}
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            targets[leg.name] = self._reposition_foot(leg_id, progress)
        return self._reposition_ik(targets, t)

    def _standing_targets(self, radial: float) -> dict[str, Point3]:
        """Statische Stand-Pose-Foot-Targets bei gegebenem radial."""
        neutral = stand_pose(radial, self.body_height)
        return {leg.name: neutral for leg in HEXAPOD.legs}

    def _reposition_ik(
        self, foot_targets: dict[str, Point3], t: float,
    ) -> dict[str, JointAngles]:
        """IK pro Bein für die Reposition-Targets, IKError mit Bein-Kontext."""
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(
                    *foot_targets[leg.name], leg, leg_limits,
                )
            except IKError as exc:
                raise IKError(
                    f'reposition IK failed for {leg.name} at '
                    f't={t:.3f}s, target={foot_targets[leg.name]}: {exc}'
                ) from exc
        return angles


def _lerp(p_start: Point3, p_end: Point3, t: float) -> Point3:
    """Linear-Interpolation zwischen zwei 3D-Punkten."""
    return (
        p_start[0] + (p_end[0] - p_start[0]) * t,
        p_start[1] + (p_end[1] - p_start[1]) * t,
        p_start[2] + (p_end[2] - p_start[2]) * t,
    )
