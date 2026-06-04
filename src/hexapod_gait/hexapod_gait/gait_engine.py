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
from hexapod_gait.joint_load import compute_load, MassModel
from hexapod_gait.trajectory_gen import stance_traj, stand_pose, swing_traj
from hexapod_kinematics import (
    base_to_leg_frame,
    HEXAPOD,
    IKError,
    JointLimits,
    leg_fk,
    leg_ik,
    leg_to_base_frame,
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

# Block B4 — Show-Pose (Free-Leg): die 4 Stützbeine (mitte+hinten) tragen,
# die 2 Vorderbeine (vorne-R/L) sind frei. Bein-Layout (config.py):
# 1=vorne-R, 2=mitte-R, 3=hinten-R, 4=hinten-L, 5=mitte-L, 6=vorne-L.
_SHOW_SUPPORT_LEGS = ('leg_2', 'leg_3', 'leg_4', 'leg_5')
_SHOW_FRONT_LEGS = ('leg_1', 'leg_6')


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
    # Block B1: Hinsetz-Sequenz (Umkehrung des Aufstehens). Drei Phasen:
    #   Phase 1 (Füße raus) reuse STATE_REPOSITION mit vertauschten radii
    #     (radial_distance → standup_radial_distance) via start_reposition(
    #     after=SITDOWN_LOWER) — kein eigener State.
    #   STATE_SITDOWN_LOWER: reverse-kartesisch — Füße x/y FIX @ standup_radial,
    #     nur body_height rampt von self.body_height → body_height_start (Bauch
    #     am Boden). = Umkehrung der CARTESIAN_STANDUP-Push-Phase.
    #   STATE_SITDOWN_FLATTEN: Joint-Space-Lerp aller Joints zu rad 0 (Beine
    #     flach, Bauch trägt, Fuß ~2 cm über Grund). Box-konvex limit-sicher,
    #     kein IK. Mirror von STARTUP_RAMP.
    # Endzustand STATE_SAT: bestromt, idle, hält rad 0. cmd_vel wird in allen
    # drei Sitdown-Phasen UND in SAT ignoriert (nur Node-Services stand_up/
    # shutdown reagieren). Aufstehen aus SAT = start_cartesian_standup (start-
    # pose-agnostisch) — kein eigener Engine-Code.
    STATE_SITDOWN_LOWER = 'SITDOWN_LOWER'
    STATE_SITDOWN_FLATTEN = 'SITDOWN_FLATTEN'
    STATE_SAT = 'SAT'

    # Block B4 — Show-Pose (Free-Leg). Aus STANDING per Toggle:
    #   STATE_SHOW_ENTER: zweiphasig. Phase a (alle 6 Füße am Boden): Körper
    #     verlagert sich um show_body_shift_back nach hinten (= Foot-Targets im
    #     Body-Frame um +shift nach vorne) → CoG wandert ins Polygon der
    #     hinteren 4 (leg_2,3,4,5). Phase b: die 2 Vorderbeine (leg_1,6) heben
    #     von der verlagerten Boden-Pose in eine neutrale Hoch-Pose. JEDER Tick
    #     in Phase b: CoG-Marge im 4-Bein-Polygon >= show_safety_margin
    #     (joint_load.compute_load) — sonst Hold (freeze) der letzten sicheren
    #     Pose. B4.0 (tools/show_pose_cog_check.py) hat die Existenz einer
    #     sicheren Pose offline nachgewiesen; das Gate ist die Laufzeit-Absicherung.
    #   STATE_SHOW_ACTIVE: hält die eingenommene Show-Pose statisch (B4.1). Das
    #     Joystick-Folgen der Vorderbeine (B4.2) baut darauf auf. cmd_vel-Fahren
    #     wird in allen SHOW-States ignoriert (nur der Show-Toggle führt heraus).
    #   STATE_SHOW_EXIT (B4.3): Umkehrung von ENTER zurück nach STANDING — ZUERST
    #     Vorderbeine runter (→ wieder 6-Bein-Stütze), DANN Körper vor. Realisiert
    #     über einen gemeinsamen Show-Skalar σ ∈ [0,1] (σ=0 = Walk-Stand-Pose,
    #     σ=1 = volle Show-Pose); EXIT fährt σ von aktuell → 0. σ=0 ist exakt die
    #     STANDING-Pose → nahtloser Übergang, danach ist Laufen wieder möglich.
    #     Funktioniert auch aus (ggf. frozen) SHOW_ENTER (σ_start = aktuelles σ).
    STATE_SHOW_ENTER = 'SHOW_ENTER'
    STATE_SHOW_ACTIVE = 'SHOW_ACTIVE'
    STATE_SHOW_EXIT = 'SHOW_EXIT'

    # Stance-Modi (Phase 13 Stage 1): Wechsel zwischen 3 validierten Lauf-Höhen
    # (radial + body_height + step_height je Modus). STATE_STANCE_SWITCH fährt
    # per Tripod-Reposition radial UND body_height gleichzeitig vom Ist- zum
    # Ziel-Modus, mit kleinem stance_switch_step_height (Apex bleibt unter der
    # Femur-Wand bei jeder Zwischenhöhe). Nur aus STANDING. cmd_vel ignoriert.
    STATE_STANCE_SWITCH = 'STANCE_SWITCH'

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
        # Block B1 — Folgezustand nach der Reposition. Default STANDING (= das
        # bisherige Standup→Walk-Verhalten, unverändert). Die Hinsetz-Sequenz
        # setzt SITDOWN_LOWER, damit Phase 1 (Füße raus) den bestehenden
        # REPOSITION-State wiederverwendet, danach aber ins Absenken übergeht.
        self._reposition_after: str = self.STATE_STANDING

        # Block B1 — SITDOWN_LOWER / SITDOWN_FLATTEN-State-Daten.
        self._sitdown_lower_start_t: float = 0.0
        self._sitdown_lower_duration: float = 0.0
        self._sitdown_flatten_start_t: float = 0.0
        self._sitdown_flatten_duration: float = 0.0
        self._sitdown_bh_start: float = -0.0135
        self._flatten_start_joints: dict[str, JointAngles] = {}
        # Block B1 (User 2026-06-03): SAT-Ruhe-Pose = Boot-/Spawn-Pose (Beine
        # hoch), NICHT flach-rad-0. Wird vom Node beim Sit-down übergeben (die
        # beim Boot gelesene Spawn-Joint-Pose). None → Fallback rad 0 je Bein
        # (Backward-Compat / Engine-Default ohne Node). Wertneutral.
        self._sitdown_rest_joints: dict[str, JointAngles] | None = None

        # Block B4 — SHOW_ENTER/SHOW_ACTIVE-State-Daten. Wertneutral: die
        # konkreten Posen-/Marge-Zahlen kommen über start_show_enter vom
        # Node/Config. Defaults hier sind nur Fallback-Platzhalter.
        self._show_start_t: float = 0.0
        self._show_duration: float = 0.0
        self._show_shift_back: float = 0.0       # Body-Rückversatz (m)
        self._show_shift_fraction: float = 0.5   # Anteil Phase a (Shift)
        self._show_front_radial: float = radial_distance   # Vorderbein-Neutral
        self._show_front_z: float = body_height
        self._show_safety_margin: float = 0.0    # min. CoG-Marge (m)
        self._show_mass_model: MassModel = MassModel()
        # CoG-Gate-Hold: bei Marge-Unterschreitung in Phase b wird die letzte
        # sichere Pose gehalten (kein Weiter-Heben). Reset bei start_show_enter.
        self._show_frozen: bool = False
        self._show_hold_angles: dict[str, JointAngles] = {}
        # Show-Skalar σ der zuletzt emittierten Pose (0 = Stand, 1 = volle
        # Show-Pose). ENTER aktualisiert ihn pro Tick; EXIT startet bei diesem
        # Wert (deckt auch Abbruch mitten in ENTER inkl. frozen ab).
        self._show_sigma: float = 0.0
        # Block B4.3 — SHOW_EXIT-State-Daten.
        self._show_exit_start_t: float = 0.0
        self._show_exit_duration: float = 0.0
        self._show_exit_sigma0: float = 1.0

        # Stance-Switch-State-Daten (Phase 13 Stage 1).
        self._stance_start_t: float = 0.0
        self._stance_duration: float = 0.0
        self._stance_from_radial: float = radial_distance
        self._stance_to_radial: float = radial_distance
        self._stance_from_bh: float = body_height
        self._stance_to_bh: float = body_height
        self._stance_to_step_height: float = self.step_height
        self._stance_switch_step_height: float = 0.025
        # Block B4.2/B4.11 — Vorderbein-Joystick-Offsets (Bein-Frame, Meter):
        # (lateral=Y, vertical=Z, radial=X) je Vorderbein. _target = vom Node
        # kommandiert (bereits skaliert + Dead-Man), _current = rate-limitiert
        # nachgeführt. Mit Lift-Faktor λ(σ) skaliert → verblasst beim EXIT.
        # B4.11: radiale Achse (X) = reach/curl der Tibia (Trigger).
        self._show_offset_target: dict[str, Point3] = {
            name: (0.0, 0.0, 0.0) for name in _SHOW_FRONT_LEGS
        }
        self._show_offset_current: dict[str, Point3] = {
            name: (0.0, 0.0, 0.0) for name in _SHOW_FRONT_LEGS
        }
        self._show_return_rate: float = 0.0   # m/s, Nachführ-/Rückkehr-Rate
        self._show_active_last_t: float = 0.0  # für dt im Rate-Limit

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
        # Phase 13 Stage A/0.7/2.3 + Block B1: cmd_vel waehrend Aufsteh-Sequenz
        # (joint-space ODER kartesisch), waehrend der Tripod-Reposition UND
        # waehrend der gesamten Hinsetz-Sequenz/SAT komplett verwerfen — nur
        # STANDING/WALKING nehmen cmd_vel an. Aus Sitdown/SAT führen allein die
        # Node-Services stand_up/shutdown heraus.
        if self._state in (
            self.STATE_STARTUP_RAMP,
            self.STATE_CARTESIAN_STANDUP,
            self.STATE_REPOSITION,
            self.STATE_SITDOWN_LOWER,
            self.STATE_SITDOWN_FLATTEN,
            self.STATE_SAT,
            self.STATE_SHOW_ENTER,
            self.STATE_SHOW_ACTIVE,
            self.STATE_SHOW_EXIT,
            self.STATE_STANCE_SWITCH,
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
        # Block B1 — Hinsetz-Sequenz (Lower → Flatten) + SAT-Idle.
        if self._state == self.STATE_SITDOWN_LOWER:
            return self._compute_sitdown_lower_angles(t)
        if self._state == self.STATE_SITDOWN_FLATTEN:
            return self._compute_sitdown_flatten_angles(t)
        if self._state == self.STATE_SAT:
            return self._compute_sat_angles()
        # Block B4 — Show-Pose (Free-Leg): Hinstellen + statisches Halten.
        if self._state == self.STATE_SHOW_ENTER:
            return self._compute_show_enter_angles(t)
        if self._state == self.STATE_SHOW_ACTIVE:
            return self._compute_show_active_angles(t)
        if self._state == self.STATE_SHOW_EXIT:
            return self._compute_show_exit_angles(t)
        if self._state == self.STATE_STANCE_SWITCH:
            return self._compute_stance_switch_angles(t)

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

    def start_reposition(
        self,
        t: float,
        from_radial: float | None = None,
        to_radial: float | None = None,
        after: str | None = None,
    ) -> None:
        """
        Tripod-Reposition einleiten (Stage 1 Teil 2.3, richtungs-agnostisch).

        Füße von ``from_radial`` zu ``to_radial`` (beide @ ``body_height``), in
        zwei Tripod-Halb-Zyklen. Dauer = ``reposition_cycle_time``. Setzt
        STATE_REPOSITION.

        Defaults (alle ``None``) = das bisherige Standup→Walk-Verhalten:
        ``standup_radial_distance`` → ``radial_distance``, danach STANDING.

        Block B1: Die Hinsetz-Sequenz ruft mit vertauschten radii
        (``radial_distance`` → ``standup_radial_distance``) und
        ``after=STATE_SITDOWN_LOWER`` auf, damit Phase 1 (Füße raus) den
        bestehenden Reposition-State wiederverwendet, danach aber statt STANDING
        ins Körper-Absenken übergeht (siehe ``_finish_reposition``).
        """
        self._repos_from_radial = (
            self.standup_radial_distance if from_radial is None else from_radial
        )
        self._repos_to_radial = (
            self.radial_distance if to_radial is None else to_radial
        )
        self._reposition_after = (
            self.STATE_STANDING if after is None else after
        )
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
        progress >= 1: Übergang via ``_finish_reposition`` — Standup-Pfad →
        STANDING (Füße auf ``radial_distance``), Hinsetz-Pfad → SITDOWN_LOWER.
        IK-Verletzung wirft IKError mit Bein-Kontext (wie der Standup) →
        gait_node fängt sie im Tick-Handler.
        """
        tau = t - self._repos_start_t
        if self._repos_duration <= 0.0:
            return self._finish_reposition(t)
        progress = tau / self._repos_duration
        if progress >= 1.0:
            return self._finish_reposition(t)
        targets: dict[str, Point3] = {}
        for leg in HEXAPOD.legs:
            leg_id = int(leg.name.split('_')[1])
            targets[leg.name] = self._reposition_foot(leg_id, progress)
        return self._reposition_ik(targets, t)

    def _finish_reposition(self, t: float) -> dict[str, JointAngles]:
        """
        Übergang am Ende der Reposition (Block B1).

        Default (``_reposition_after == STATE_STANDING``): wie bisher → STANDING,
        Füße auf ``_repos_to_radial`` (Walk-Pose). Hinsetz-Pfad
        (``_reposition_after == STATE_SITDOWN_LOWER``): direkt ins Körper-
        Absenken übergehen — ``start_sitdown_lower`` setzen und dessen Angles für
        diesen Tick liefern (nahtlos, da Lower bei progress 0 exakt die
        Reposition-Endpose @ ``standup_radial``/``body_height`` ausgibt).
        """
        if self._reposition_after == self.STATE_SITDOWN_LOWER:
            self.start_sitdown_lower(t)
            return self._compute_sitdown_lower_angles(t)
        self._state = self.STATE_STANDING
        return self._reposition_ik(
            self._standing_targets(self._repos_to_radial), t,
        )

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

    # ----- Block B1: Hinsetz-Sequenz (Reposition aus → Lower → Flatten → SAT) --

    # Fallback-Ruhe-Pose (SAT), falls der Node keine Spawn-Pose übergibt: alle
    # Joints rad 0. ⚠️ rad 0 = Bein HORIZONTAL gestreckt (Fuß auf Coxa-Höhe) —
    # NICHT die gewünschte Beine-hoch-Pose. Im Normalbetrieb übergibt der Node
    # die Boot-/Spawn-Pose via rest_joints (User 2026-06-03).
    _SIT_REST_ANGLES: JointAngles = (0.0, 0.0, 0.0)

    def _rest_angles(self, leg_name: str) -> JointAngles:
        """SAT-Ruhe-Pose je Bein: übergebene Spawn-Pose, sonst Fallback rad 0."""
        if self._sitdown_rest_joints is None:
            return self._SIT_REST_ANGLES
        return self._sitdown_rest_joints.get(leg_name, self._SIT_REST_ANGLES)

    def start_sitdown(
        self,
        t: float,
        lower_duration: float,
        flatten_duration: float,
        body_height_start: float = -0.0135,
        rest_joints: dict[str, JointAngles] | None = None,
    ) -> bool:
        """
        Hinsetz-Sequenz einleiten (Block B1). Nur aus STANDING erlaubt.

        Phase 1 (Füße raus) reuse der bestehende REPOSITION-State via
        ``start_reposition(from=radial_distance, to=standup_radial_distance,
        after=SITDOWN_LOWER)``; Dauer = ``reposition_cycle_time``.
        Phase 2 (Lower, Dauer ``lower_duration``) + Phase 3 (Flatten, Dauer
        ``flatten_duration``) folgen automatisch über die Finish-Übergänge.
        ``body_height_start`` (Foot-z @ Bauch am Boden, negativ) wird für die
        Lower-/Flatten-Start-Pose verwendet (Reuse des Standup-Werts).

        ``rest_joints`` (User 2026-06-03) = Ziel-/SAT-Ruhe-Pose je Bein, in die
        Phase 3 lerpt und die SAT statisch hält. Typisch die beim Boot gelesene
        **Spawn-Pose** (Beine hoch) → der Roboter endet in genau der Pose, in der
        er gestartet ist; der Bauch trägt, die Beine fallen erst beim Relay-Aus.
        ``None`` → Fallback rad 0 je Bein (flach; nur Engine-Default ohne Node).

        Returns ``True`` wenn gestartet, ``False`` wenn der State != STANDING
        ist (Defense-in-depth; der Node prüft ohnehin vorher).
        """
        if self._state != self.STATE_STANDING:
            return False
        if lower_duration <= 0.0:
            raise ValueError(
                f'lower_duration must be > 0, got {lower_duration}'
            )
        if flatten_duration <= 0.0:
            raise ValueError(
                f'flatten_duration must be > 0, got {flatten_duration}'
            )
        self._sitdown_lower_duration = lower_duration
        self._sitdown_flatten_duration = flatten_duration
        self._sitdown_bh_start = body_height_start
        self._sitdown_rest_joints = rest_joints
        # Phase 1: Reposition AUS (radial → standup_radial), danach LOWER.
        self.start_reposition(
            t,
            from_radial=self.radial_distance,
            to_radial=self.standup_radial_distance,
            after=self.STATE_SITDOWN_LOWER,
        )
        return True

    def start_sitdown_lower(self, t: float) -> None:
        """
        Phase 2 — Körper absenken (reverse-kartesisch). Setzt SITDOWN_LOWER.

        Füße x/y bleiben fix @ ``standup_radial_distance`` (Reposition-Endpose),
        nur ``body_height`` rampt von ``self.body_height`` → ``_sitdown_bh_start``.
        Exakte Umkehrung der CARTESIAN_STANDUP-Push-Phase.
        """
        self._sitdown_lower_start_t = t
        self._state = self.STATE_SITDOWN_LOWER

    def _compute_sitdown_lower_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        SITDOWN_LOWER: pro Tick Foot-Targets (x/y fix, z rampt) → IK.

        Bei progress >= 1: Übergang in SITDOWN_FLATTEN, dessen Angles für diesen
        Tick geliefert. IK-Limit-/Reach-Verletzung wirft IKError mit Bein-Kontext
        → gait_node fängt sie im Tick-Handler.
        """
        tau = t - self._sitdown_lower_start_t
        if self._sitdown_lower_duration <= 0.0:
            self.start_sitdown_flatten(t)
            return self._compute_sitdown_flatten_angles(t)
        progress = tau / self._sitdown_lower_duration
        if progress >= 1.0:
            self.start_sitdown_flatten(t)
            return self._compute_sitdown_flatten_angles(t)
        # Smooth-Step: Geschwindigkeit-Null an beiden Enden (weiches Absenken).
        s = progress * progress * (3.0 - 2.0 * progress)
        z = self.body_height + (self._sitdown_bh_start - self.body_height) * s
        radial = self.standup_radial_distance
        targets = {
            leg.name: (radial, 0.0, z) for leg in HEXAPOD.legs
        }
        return self._sitdown_lower_ik(targets, t)

    def _sitdown_lower_ik(
        self, foot_targets: dict[str, Point3], t: float,
    ) -> dict[str, JointAngles]:
        """IK pro Bein für die Lower-Targets, IKError mit Bein-Kontext."""
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(
                    *foot_targets[leg.name], leg, leg_limits,
                )
            except IKError as exc:
                raise IKError(
                    f'sitdown lower IK failed for {leg.name} at '
                    f't={t:.3f}s, target={foot_targets[leg.name]}: {exc}'
                ) from exc
        return angles

    def start_sitdown_flatten(self, t: float) -> None:
        """
        Phase 3 — Beine flach zu rad 0 (Joint-Space-Lerp). Setzt SITDOWN_FLATTEN.

        Start-Pose = IK der Lower-Endpose (``standup_radial`` @
        ``_sitdown_bh_start``), deterministisch berechnet — kein Tracking der
        Live-Angles nötig. Ziel = rad 0 je Bein. Der Lerp läuft in Joint-Space
        (kein IK pro Tick); zwischen zwei in-limit-Posen bleibt er box-konvex
        in-limit. IKError der Start-Pose-IK wäre ein Config-Bug → propagiert.
        """
        lower_end = stand_pose(
            self.standup_radial_distance, self._sitdown_bh_start,
        )
        start_joints: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                start_joints[leg.name] = leg_ik(*lower_end, leg, leg_limits)
            except IKError as exc:
                raise IKError(
                    f'sitdown flatten start IK failed for {leg.name} at '
                    f't={t:.3f}s, target={lower_end}: {exc}'
                ) from exc
        self._flatten_start_joints = start_joints
        self._sitdown_flatten_start_t = t
        self._state = self.STATE_SITDOWN_FLATTEN

    def _compute_sitdown_flatten_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        SITDOWN_FLATTEN: Joint-Space-Lerp ``_flatten_start_joints`` → rad 0.

        Smooth-Step-Lerp pro Joint (kein IK). Bei progress >= 1: State → SAT,
        Ruhe-Pose (rad 0) geliefert.
        """
        tau = t - self._sitdown_flatten_start_t
        if self._sitdown_flatten_duration <= 0.0:
            self._state = self.STATE_SAT
            return self._compute_sat_angles()
        progress = tau / self._sitdown_flatten_duration
        if progress >= 1.0:
            self._state = self.STATE_SAT
            return self._compute_sat_angles()
        s = progress * progress * (3.0 - 2.0 * progress)
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            start = self._flatten_start_joints[leg.name]
            angles[leg.name] = _lerp(start, self._rest_angles(leg.name), s)
        return angles

    def _compute_sat_angles(self) -> dict[str, JointAngles]:
        """SAT-Idle: Ruhe-Pose je Bein statisch halten (bestromt)."""
        return {
            leg.name: self._rest_angles(leg.name) for leg in HEXAPOD.legs
        }

    # ----- Block B4: Show-Pose (Free-Leg) — Hinstellen + statisches Halten -----

    def start_show_enter(
        self,
        t: float,
        duration: float,
        body_shift_back: float,
        shift_fraction: float,
        front_radial: float,
        front_z: float,
        safety_margin: float,
        return_rate: float = 0.0,
        mass_model: MassModel | None = None,
    ) -> bool:
        """
        Show-Pose einleiten (Block B4). Nur aus STANDING erlaubt.

        Zweiphasig (siehe ``_show_enter_foot``): Phase a (Anteil
        ``shift_fraction``) verlagert den Körper um ``body_shift_back`` nach
        hinten (alle 6 Füße am Boden), Phase b hebt die 2 Vorderbeine in die
        neutrale Hoch-Pose (Bein-Frame ``(front_radial, 0, front_z)``). In
        Phase b prüft jeder Tick die CoG-Marge im 4-Bein-Polygon gegen
        ``safety_margin`` (``mass_model`` = Massen-Annahme, Default URDF-Summe).

        Wertneutral: alle Posen-/Marge-Zahlen kommen vom Node/Config (B4.4),
        die Engine hardcodet nichts. Die Existenz einer sicheren Pose ist
        offline in B4.0 (``tools/show_pose_cog_check.py``) nachgewiesen.

        Returns ``True`` wenn gestartet, ``False`` wenn der State != STANDING
        ist (Defense-in-depth; der Node prüft ohnehin vorher).
        """
        if self._state != self.STATE_STANDING:
            return False
        if duration <= 0.0:
            raise ValueError(f'duration must be > 0, got {duration}')
        if not 0.0 < shift_fraction < 1.0:
            raise ValueError(
                f'shift_fraction must be in (0, 1), got {shift_fraction}'
            )
        self._show_start_t = t
        self._show_duration = duration
        self._show_shift_back = body_shift_back
        self._show_shift_fraction = shift_fraction
        self._show_front_radial = front_radial
        self._show_front_z = front_z
        self._show_safety_margin = safety_margin
        self._show_return_rate = return_rate
        self._show_mass_model = mass_model or MassModel()
        self._show_frozen = False
        self._show_hold_angles = {}
        self._show_sigma = 0.0
        # B4.2/B4.11: Vorderbein-Offsets bei jedem Show-Eintritt auf 0 (Neutral).
        self._show_offset_target = {
            n: (0.0, 0.0, 0.0) for n in _SHOW_FRONT_LEGS
        }
        self._show_offset_current = {
            n: (0.0, 0.0, 0.0) for n in _SHOW_FRONT_LEGS
        }
        self._show_active_last_t = 0.0
        self._state = self.STATE_SHOW_ENTER
        return True

    def set_show_offsets(self, offsets: dict[str, tuple]) -> None:
        """
        Soll-Offsets der Vorderbeine setzen (B4.2/B4.11; Node ruft pro Tick).

        ``offsets`` = ``{leg_name: (lateral, vertical[, radial])}`` in **Metern**,
        Bein-Frame (lateral = Y = seitwärts/coxa-Schwenk, vertical = Z = hoch/
        runter, radial = X = reach/Tibia-Curl). Fehlt ``radial`` (2-Tupel) → 0.
        Relativ zur neutralen Hoch-Pose. Der Node hat Stick→Meter bereits
        skaliert UND den Dead-Man (R1) angewandt (R1 los / Achse zentriert →
        0). Die Engine führt den IST-Offset rate-limitiert nach
        (``show_return_rate``) und clampt hart auf die URDF-Limits. Nur in
        SHOW_ACTIVE wirksam; unbekannte Bein-Namen werden ignoriert.
        """
        for name in _SHOW_FRONT_LEGS:
            if name in offsets:
                vals = offsets[name]
                lat = float(vals[0])
                vert = float(vals[1])
                radial = float(vals[2]) if len(vals) > 2 else 0.0
                self._show_offset_target[name] = (lat, vert, radial)

    def _show_foot(self, leg, sigma: float) -> Point3:
        """
        Foot-Target eines Beins für den Show-Skalar ``sigma`` (Bein-Frame).

        ``sigma`` ∈ [0, 1] parametrisiert die gesamte Show-Geste — geteilt von
        ENTER (σ: 0→1), ACTIVE (σ=1) und EXIT (σ: aktuell→0):
        - **σ=0** = Walk-Stand-Pose ``(radial_distance, 0, body_height)`` (= exakt
          die STANDING-Pose → nahtloser EXIT-Übergang).
        - Phase a (``σ <= shift_fraction``): alle 6 Füße am Boden, Körper-
          Rückversatz ``s`` smooth-step 0 → ``body_shift_back`` (im Body-Frame
          wandern die Füße um +s nach vorne).
        - Phase b (``σ > shift_fraction``, nur Vorderbeine 1,6): Lerp von der
          verlagerten Boden-Pose → neutrale Hoch-Pose ``(front_radial, 0,
          front_z)``. Stützbeine bleiben auf der voll-verlagerten Boden-Pose.
        """
        frac = self._show_shift_fraction
        sub_a = min(sigma / frac, 1.0) if frac > 0.0 else 1.0
        s = self._show_shift_back * (sub_a * sub_a * (3.0 - 2.0 * sub_a))
        # Verlagerte Boden-Pose: Stand-Fuß (Bein-Frame) → base, +s nach vorne,
        # zurück in den Bein-Frame.
        stand_base = leg_to_base_frame(
            stand_pose(self.radial_distance, self.body_height), leg,
        )
        ground_leg = base_to_leg_frame(
            (stand_base[0] + s, stand_base[1], stand_base[2]), leg,
        )
        if leg.name in _SHOW_FRONT_LEGS and sigma > frac:
            sub_b = (sigma - frac) / (1.0 - frac)
            s_b = sub_b * sub_b * (3.0 - 2.0 * sub_b)
            neutral = (self._show_front_radial, 0.0, self._show_front_z)
            return _lerp(ground_leg, neutral, s_b)
        return ground_leg

    def _show_front_offset_factor(self, sigma: float) -> float:
        """
        Lift-Faktor λ(σ) ∈ [0, 1] für den Joystick-Offset eines Vorderbeins.

        λ=0 solange das Bein am Boden ist (σ <= shift_fraction), linear → 1
        bei voll gehobenem Bein (σ=1). So wirkt der Offset nur in der Luft und
        **verblasst beim EXIT** automatisch (kein Sprung beim Aufsetzen).
        """
        frac = self._show_shift_fraction
        if sigma <= frac:
            return 0.0
        return min(1.0, (sigma - frac) / (1.0 - frac))

    def _front_foot(self, leg, sigma: float, offset: Point3) -> Point3:
        """
        Vorderbein-Foot: Basis-Show-Pose + Joystick-Offset·λ(σ) (Bein-Frame).

        ``offset`` = ``(lateral=Y, vertical=Z, radial=X)`` in Metern. λ(σ)
        skaliert den Offset (1 oben, 0 am Boden) → verblasst beim EXIT.
        """
        fx, fy, fz = self._show_foot(leg, sigma)
        lam = self._show_front_offset_factor(sigma)
        return (
            fx + offset[2] * lam,
            fy + offset[0] * lam,
            fz + offset[1] * lam,
        )

    def _show_pose_targets(self, sigma: float) -> dict[str, Point3]:
        """
        Foot-Targets aller 6 Beine für σ (Stützbeine + Vorderbeine mit Offset).

        Verwendet von ENTER (Offsets = 0) und EXIT (Offsets eingefroren →
        verblassen über λ(σ)). SHOW_ACTIVE führt die Offsets vorher
        rate-limitiert nach und ruft dann mit σ=1.
        """
        targets: dict[str, Point3] = {}
        for leg in HEXAPOD.legs:
            if leg.name in _SHOW_FRONT_LEGS:
                targets[leg.name] = self._front_foot(
                    leg, sigma, self._show_offset_current[leg.name],
                )
            else:
                targets[leg.name] = self._show_foot(leg, sigma)
        return targets

    def _compute_show_enter_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        SHOW_ENTER: pro Tick Foot-Targets → IK + CoG-Marge-Gate (Phase b).

        ``progress = (t - _show_start_t) / _show_duration``. Bei progress >= 1:
        State → SHOW_ACTIVE. In Phase b wird die CoG-Marge im 4-Bein-Polygon
        geprüft; unterschreitet sie ``_show_safety_margin``, wird die letzte
        sichere Pose gehalten (``_show_frozen``) statt weiter zu heben — das
        Gate ist die Laufzeit-Absicherung zur offline-B4.0-Garantie. IK-Limit-/
        Reach-Verletzung wirft IKError mit Bein-Kontext → gait_node fängt sie.
        """
        if self._show_frozen:
            return dict(self._show_hold_angles)
        if self._show_duration <= 0.0:
            self._show_sigma = 1.0
            self._state = self.STATE_SHOW_ACTIVE
            return self._compute_show_active_angles(t)
        progress = (t - self._show_start_t) / self._show_duration
        if progress >= 1.0:
            self._show_sigma = 1.0
            self._state = self.STATE_SHOW_ACTIVE
            return self._compute_show_active_angles(t)

        # σ = linearer Progress; _show_foot smoothstept intern pro Sub-Phase
        # (Geschwindigkeit-Null an Start, Phasen-Grenze und Ende). Offsets sind
        # in ENTER 0 (Joystick erst in SHOW_ACTIVE).
        sigma = progress
        targets = self._show_pose_targets(sigma)
        angles = self._show_ik(targets, t, 'show enter')

        # CoG-Gate nur in Phase b (Vorderbeine in der Luft → 4-Bein-Stütze).
        if sigma > self._show_shift_fraction:
            margin = self._show_cog_margin(angles)
            if margin < self._show_safety_margin:
                self._show_frozen = True
                return dict(self._show_hold_angles or angles)

        self._show_sigma = sigma
        self._show_hold_angles = angles
        return angles

    def _compute_show_active_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        SHOW_ACTIVE: Vorderbeine folgen den Joystick-Offsets (B4.2).

        σ=1 (volle Show-Pose). Pro Tick wird der IST-Offset jedes Vorderbeins
        rate-limitiert (``show_return_rate`` · dt) Richtung Soll-Offset
        (``set_show_offsets``) nachgeführt; würde der Schritt die URDF-Limits
        verletzen (``leg_ik`` IKError), wird der letzte gültige Offset gehalten
        (= weiche Clamp am Limit-Rand). Stützbeine bleiben statisch verlagert.
        """
        dt = t - self._show_active_last_t if self._show_active_last_t > 0.0 else 0.0
        if dt < 0.0:
            dt = 0.0
        self._show_active_last_t = t
        max_delta = self._show_return_rate * dt

        # Vorderbein-Offsets rate-limitiert nachführen + clampen.
        for name in _SHOW_FRONT_LEGS:
            leg = HEXAPOD.by_name(name)
            cur = self._show_offset_current[name]
            new = _rate_limit(cur, self._show_offset_target[name], max_delta)
            if new != cur:
                leg_limits = self.joint_limits.get(name)
                try:
                    leg_ik(*self._front_foot(leg, 1.0, new), leg, leg_limits)
                    self._show_offset_current[name] = new
                except IKError:
                    pass   # Limit-Rand erreicht → letzten gültigen Offset halten

        targets = self._show_pose_targets(1.0)
        return self._show_ik(targets, t, 'show active')

    def start_show_exit(self, t: float, duration: float) -> bool:
        """
        Show-Pose verlassen (Block B4.3). Nur aus einem SHOW-State erlaubt.

        Fährt den Show-Skalar σ von seinem aktuellen Wert → 0 (= Walk-Stand-Pose)
        über ``duration``. Durch die σ-Geometrie (siehe ``_show_foot``) bedeutet
        das: ZUERST die Vorderbeine runter (σ von 1 nach shift_fraction → wieder
        6-Bein-Stütze), DANN den Körper vor (σ von shift_fraction nach 0). Bei
        Abschluss → STANDING (Füße auf ``radial_distance``) → Laufen wieder möglich.

        Funktioniert aus SHOW_ACTIVE (σ=1) genauso wie aus einem laufenden oder
        eingefrorenen SHOW_ENTER (σ = aktuell erreichter Wert), sodass der
        Round-Trip immer sauber endet. EXIT folgt dem in B4.0 validierten Pfad
        rückwärts und hat KEIN CoG-Gate-Abbruch (sonst Strandung mitten im Exit).

        Returns ``True`` wenn gestartet, ``False`` wenn der State kein SHOW-State
        ist (Defense-in-depth; der Node prüft ohnehin vorher).
        """
        if self._state not in (
            self.STATE_SHOW_ENTER,
            self.STATE_SHOW_ACTIVE,
            self.STATE_SHOW_EXIT,
        ):
            return False
        if duration <= 0.0:
            raise ValueError(f'duration must be > 0, got {duration}')
        self._show_exit_sigma0 = (
            1.0 if self._state == self.STATE_SHOW_ACTIVE else self._show_sigma
        )
        self._show_exit_start_t = t
        self._show_exit_duration = duration
        self._show_frozen = False
        self._state = self.STATE_SHOW_EXIT
        return True

    def _compute_show_exit_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        SHOW_EXIT: Show-Skalar σ von ``_show_exit_sigma0`` → 0, dann STANDING.

        ``progress = (t - _show_exit_start_t) / _show_exit_duration``. σ =
        ``sigma0 * (1 - progress)`` (linear; ``_show_foot`` smoothstept intern pro
        Sub-Phase → Geschwindigkeit-Null an Start, Phasen-Grenze und Ende —
        konsistent zu ENTER). Bei progress >= 1: σ=0 → State STANDING, Walk-Stand-
        Pose geliefert (nahtlos, da ``_show_foot(σ=0)`` == ``stand_pose``). IK-
        Limit-/Reach-Verletzung wirft IKError mit Bein-Kontext → gait_node fängt sie.
        """
        if self._show_exit_duration <= 0.0:
            self._show_sigma = 0.0
            self._state = self.STATE_STANDING
            return self._compute_stand_pose_joints()
        progress = (t - self._show_exit_start_t) / self._show_exit_duration
        if progress >= 1.0:
            self._show_sigma = 0.0
            self._state = self.STATE_STANDING
            return self._compute_stand_pose_joints()
        sigma = self._show_exit_sigma0 * (1.0 - progress)
        self._show_sigma = sigma
        # Eingefrorene Offsets verblassen über λ(σ) → kein Sprung beim Aufsetzen.
        targets = self._show_pose_targets(sigma)
        return self._show_ik(targets, t, 'show exit')

    def _show_ik(
        self, foot_targets: dict[str, Point3], t: float, context: str,
    ) -> dict[str, JointAngles]:
        """IK pro Bein für die Show-Targets, IKError mit Bein-Kontext."""
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(
                    *foot_targets[leg.name], leg, leg_limits,
                )
            except IKError as exc:
                raise IKError(
                    f'{context} IK failed for {leg.name} at '
                    f't={t:.3f}s, target={foot_targets[leg.name]}: {exc}'
                ) from exc
        return angles

    def _show_cog_margin(self, angles: dict[str, JointAngles]) -> float:
        """CoG-Marge (m) im 4-Bein-Stützpolygon (leg_2,3,4,5) für eine Pose."""
        load = compute_load(
            angles,
            stance_legs=list(_SHOW_SUPPORT_LEGS),
            masses=self._show_mass_model,
        )
        return load.stability_margin_m

    # ----- Phase 13 Stage 1: Stance-Modus-Wechsel (radial + body_height) ----

    def start_stance_switch(
        self,
        t: float,
        target_radial: float,
        target_body_height: float,
        target_step_height: float,
        duration: float,
        switch_step_height: float = 0.025,
    ) -> bool:
        """
        Wechsel zu einem anderen Stance-Modus (Phase 13 Stage 1). Nur aus STANDING.

        Fährt per Tripod-Reposition (zwei Halb-Zyklen) ``radial_distance`` UND
        ``body_height`` gleichzeitig vom Ist-Wert zum Ziel-Modus. ``body_height``
        lerpt global (Körper hebt/senkt über den planted Stützfüßen), ``radial``
        pro Bein während seiner Swing-Hälfte. ``switch_step_height`` (klein) hält
        den Swing-Apex unter der Femur-Wand bei jeder Zwischenhöhe. Bei Abschluss
        werden ``radial_distance``/``body_height``/``step_height`` auf den Ziel-
        Modus gesetzt → STANDING (= lauffähig im neuen Modus).

        Returns ``True`` wenn gestartet, ``False`` wenn State != STANDING.
        """
        if self._state != self.STATE_STANDING:
            return False
        if duration <= 0.0:
            raise ValueError(f'duration must be > 0, got {duration}')
        self._stance_from_radial = self.radial_distance
        self._stance_to_radial = target_radial
        self._stance_from_bh = self.body_height
        self._stance_to_bh = target_body_height
        self._stance_to_step_height = target_step_height
        self._stance_switch_step_height = switch_step_height
        self._stance_start_t = t
        self._stance_duration = duration
        self._state = self.STATE_STANCE_SWITCH
        return True

    def _stance_switch_foot(self, leg_id: int, progress: float) -> Point3:
        """
        Foot-Target eines Beins während STANCE_SWITCH (Bein-Frame).

        Tripod ({1,3,5} Hälfte 1, {2,4,6} Hälfte 2). ``body_height`` lerpt global
        (smooth-step) über die ganze Dauer; ``radial`` lerpt pro Bein während
        seiner Swing-Hälfte (smooth-step) + Halbsinus-Hub ``switch_step_height``.
        Stützbeine: radial auf from (vor Swing) bzw. to (nach Swing); z folgt der
        globalen body_height-Rampe (Körper bewegt sich über planted Füßen).
        """
        sg = progress * progress * (3.0 - 2.0 * progress)
        bh = self._stance_from_bh + (self._stance_to_bh - self._stance_from_bh) * sg
        frm, to = self._stance_from_radial, self._stance_to_radial
        # Tripod-Gruppe: ungerade Beine (1,3,5) Hälfte 1, gerade (2,4,6) Hälfte 2.
        swing_start = 0.0 if leg_id % 2 == 1 else 0.5
        swing_end = swing_start + 0.5
        if progress < swing_start:
            return (frm, 0.0, bh)
        if progress >= swing_end:
            return (to, 0.0, bh)
        sub = (progress - swing_start) / 0.5
        s = sub * sub * (3.0 - 2.0 * sub)
        x = frm + (to - frm) * s
        z = bh + self._stance_switch_step_height * math.sin(math.pi * sub)
        return (x, 0.0, z)

    def _compute_stance_switch_angles(
        self, t: float,
    ) -> dict[str, JointAngles]:
        """
        STANCE_SWITCH: pro Tick Foot-Targets → IK.

        Bei progress >= 1: Ziel-Modus (radial/body_height/step_height)
        übernehmen → STANDING (nahtlos lauffähig im neuen Modus).
        """
        if self._stance_duration <= 0.0:
            return self._finish_stance_switch(t)
        progress = (t - self._stance_start_t) / self._stance_duration
        if progress >= 1.0:
            return self._finish_stance_switch(t)
        targets = {
            leg.name: self._stance_switch_foot(
                int(leg.name.split('_')[1]), progress,
            )
            for leg in HEXAPOD.legs
        }
        angles: dict[str, JointAngles] = {}
        for leg in HEXAPOD.legs:
            leg_limits = self.joint_limits.get(leg.name)
            try:
                angles[leg.name] = leg_ik(*targets[leg.name], leg, leg_limits)
            except IKError as exc:
                raise IKError(
                    f'stance switch IK failed for {leg.name} at '
                    f't={t:.3f}s, target={targets[leg.name]}: {exc}'
                ) from exc
        return angles

    def _finish_stance_switch(self, t: float) -> dict[str, JointAngles]:
        """Ziel-Modus-Params übernehmen, STANDING liefern (nahtlos)."""
        self.radial_distance = self._stance_to_radial
        self.body_height = self._stance_to_bh
        self.step_height = self._stance_to_step_height
        self._state = self.STATE_STANDING
        return self._compute_stand_pose_joints()


def _rate_limit(cur: tuple, target: tuple, max_delta: float) -> tuple:
    """Bewege ``cur`` je Komponente um max. ``max_delta`` Richtung ``target``."""
    out = []
    for c, g in zip(cur, target):
        d = g - c
        if d > max_delta:
            d = max_delta
        elif d < -max_delta:
            d = -max_delta
        out.append(c + d)
    return tuple(out)


def _lerp(p_start: Point3, p_end: Point3, t: float) -> Point3:
    """Linear-Interpolation zwischen zwei 3D-Punkten."""
    return (
        p_start[0] + (p_end[0] - p_start[0]) * t,
        p_start[1] + (p_end[1] - p_start[1]) * t,
        p_start[2] + (p_end[2] - p_start[2]) * t,
    )
