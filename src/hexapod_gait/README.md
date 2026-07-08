# hexapod_gait

ROS-Knoten für Stand-Pose und Gait-Engine. Konsumiert
[hexapod_kinematics](../hexapod_kinematics/) für die IK pro Bein,
publiziert `JointTrajectory` an die 6 JTC-Controller aus Phase 4.

## Komponenten

| Datei | Zweck |
|---|---|
| [stand_node.py](hexapod_gait/stand_node.py) | One-shot rclpy-Knoten: fährt alle 6 Beine in Stand-Pose und beendet sich |
| [gait_node.py](hexapod_gait/gait_node.py) | 50 Hz Timer-Loop, cmd_vel-Subscriber, Engine-Tick → 6 JointTrajectory-Pubs |
| [gait_engine.py](hexapod_gait/gait_engine.py) | Pure-Python State-Machine STANDING / WALKING / STOPPING / STARTUP_RAMP / CARTESIAN_STANDUP / REPOSITION / SITDOWN_LOWER / SITDOWN_FLATTEN / SAT + Body-Frame-Mapping |
| [gait_patterns.py](hexapod_gait/gait_patterns.py) | `GaitPattern`-Dataclass + Presets `TRIPOD`, `SINGLE_LEG_1..6`, erweiterbar für Wave/Ripple |
| [trajectory_gen.py](hexapod_gait/trajectory_gen.py) | Pure-Python `swing_traj` (Halbsinus) + `stance_traj` (linear) im Bein-Frame |
| [tip_monitor.py](hexapod_gait/tip_monitor.py) | Pure-Python Kipp-/Sturz-Erkennung (Schwellen + Entprellung + Latch), Block A5 Stufe 1 |
| [balance_controller.py](hexapod_gait/balance_controller.py) | Pure-Python Body-Stabilisierungs-Regler **v2** (per Achse: Zwei-Fenster-Hysterese + Dual-Tiefpass + Totband-PI + Gyro-D + Slew), Block A5 Stufe 2 / TF-2 / **7** |
| [slope_estimator.py](hexapod_gait/slope_estimator.py) | Pure-Python Hang-Schätzung (langsamer Tiefpass + Residual), Block A5 TF-1 |
| [contact_diagnostic.py](hexapod_gait/contact_diagnostic.py) | Pure-Python Fußkontakt-Diagnose (Latenz/Plausibilität/Quote), Block A5 Stufe 4 / S4-1 |
| [support_monitor.py](hexapod_gait/support_monitor.py) | Pure-Python Stütz-Verlust-Erkennung (Slip/Kante → Freeze, Leaky-Entprellung + Latch), Block A5 Stufe 4 / S4-4 |
| [sensor_health_monitor.py](hexapod_gait/sensor_health_monitor.py) | Pure-Python Fußkontakt-Sensor-Plausibilität (stuck-on/dead → flaggen, Latch), Block A5 Stufe 4 / S4-5 |

## Kipp-/Sturz-Erkennung (Block A5 Stufe 1)

`gait_node` abonniert `/imu/data` (`sensor_msgs/Imu`, Sensor-QoS) und überwacht die
Körperlage gegen Kippen — Sicherheitsnetz, bevor Stufe 2 aktiv levelt.

- **Logik:** ROS-frei in [tip_monitor.py](hexapod_gait/tip_monitor.py) (`TipMonitor`):
  roll/pitch (aus Quaternion) + Kipprate (`hypot(gyro_x, gyro_y)`) gegen Schwellen,
  mit Entprellung (N Ticks) + Latch.
- **Reaktion:**
  - **WARN** (`tip_angle_warn_deg_{roll,pitch}`, Default 15°): `cmd_vel` → 0, Roboter stoppt/settelt.
  - **CRIT** (`tip_angle_crit_deg_{roll,pitch}` 25° **oder** `tip_rate_crit_dps` 80°/s): einmaliger
    `/hexapod_safety_freeze` (hart, gelatcht) + dieser Tick publisht nicht. Recovery:
    State-Wechsel (sit/stand-Service) setzt zurück. **Kein Hinsetzen** (am Hang würde
    die Sitz-Bewegung selbst kippen).
- **State-Gating:** nur in `STANDING`/`WALKING`; beim Aufstehen/Hinsetzen/Reposition/
  Show/Stance-Switch ausgesetzt (Körper kippt dort *gewollt*).
- **Ohne IMU** (kein `/imu/data`, z.B. `enable_imu:=false`): `TipMonitor` bleibt inaktiv
  → normales Laufen (graceful degradation).
- **Parameter (live; Stufe 7: warn/crit per Achse):** `tip_detection_enable`,
  `tip_angle_warn_deg_{roll,pitch}`, `tip_angle_crit_deg_{roll,pitch}`,
  `tip_rate_crit_dps`, `tip_debounce_ticks` — via
  `_on_param_change`/rqt_reconfigure verstellbar (Monitor-Rebuild). Winkel-Feintuning auf
  der Schräge.
- **TF-1 (slope-bewusst):** seit Terrain-Following bekommt der `TipMonitor` das **Residual**
  (Ist-Neigung − Hang-Schätzung) statt der rohen Neigung (s.u.) — feuert relativ zum Hang,
  nicht absolut.

## Passiv Terrain-Following + slope-bewusster Tip (Block A5 TF-1)

Beim Hang-Laufen folgt der Körper bei **Nominal-Stance** dem Boden von allein (Bein-Geometrie
identisch zur Flach-Pose — kein aktiver Stellpfad; aktive Stabilisierung = TF-2). TF-1 macht
nur die **Kipp-Erkennung hang-tauglich**, damit die gewollte Hang-Neigung nicht fälschlich als
Kippen feuert.

- **Hang-Schätzung:** ROS-frei in [slope_estimator.py](hexapod_gait/slope_estimator.py)
  (`SlopeEstimator`): langsamer Tiefpass (EMA, `alpha = dt/(τ+dt)`) auf roll/pitch. Weil der
  Körper dem Boden folgt, **ist** die langsame Komponente der Untergrund (= „der Hang").
  - **Snap-Init:** erstes Sample nach `reset()` springt direkt auf die Messung (kein Hochlauf
    von 0 → kein künstlicher Residual-Sprung beim Wiedereintritt auf einem Hang).
  - **Clamp** (`slope_clamp_deg`, Default **40°**): begrenzt die Schätzung, damit ein
    *langsames* Wegkippen sie nicht beliebig „mitwandern" lässt (sonst würde der Residual nie
    groß → blind für langsames Umkippen).
  - **State-Gating:** aktiv nur in `STANDING`/`WALKING` (wie die Tip-Auswertung); in Transition-
    States Reset (Körper kippt dort *gewollt*). Publiziert auf `/imu/slope` (Grad, Sim-Verify).
- **Slope-bewusster Tip:** der `TipMonitor` bekommt `residual = IMU − Hang-Schätzung`. Stetiger
  Hang → Residual ≈ 0 → **kein Fehlalarm**; echter Kipp → Filter lagt → Residual wächst → feuert
  wie gehabt. Die **Kipprate bleibt roh** (Sturz-Drehrate ist hang-unabhängig → primärer
  Schnell-Fänger).
- **Parameter (live):** `slope_aware_tip_enable` (Default **true**, strikt besser als absolut
  sobald IMU da), `slope_estimate_tau_s` (Default **0.5**, folgt dem Rampen-Eintritt, trackt
  keinen Sturz), `slope_clamp_deg` (Default **40°**).
- **Ohne IMU:** Schätzung reset, `TipMonitor` inaktiv (graceful, wie Stufe 1).

## Körper-Stabilisierung / Leveling (Block A5 Stufe 2 + 3a + TF-2)

Der `gait_node` stabilisiert die Körperlage, indem die Fuß-Targets um eine Körper-Rotation
gedreht werden. **Zwei Modi** (`leveling_mode`):

- **`terrain` (TF-2, Default):** Körper bleibt **parallel zum Boden** — **roll → 0**,
  **pitch folgt dem Hang** (flach → waagerecht, Hang → hangparallel) + **Wackel-Dämpfung**.
  Der Trick: per-Achse-Reglereingänge (Soll intern 0) — roll = roh (→0), pitch = **Residual**
  (IMU − Hang-Schätzung aus TF-1 → der langsame Hang fällt heraus, nur Wackeln wird korrigiert).
- **`horizontal` (Stufe 2/3a):** Körper **waagerecht** (roll **und** pitch → 0), egal wie der
  Boden liegt — fürs statische Horizontal-Stehen (z.B. Sensor-/Kamera-Plattform).

**Stufe 2:** im `STANDING`. **Stufe 3a/TF-2:** zusätzlich im `WALKING`/`STOPPING`. Drei
Schichten (analog Stufe 1):

- **Regler (v2, Stufe 7):** ROS-frei in [balance_controller.py](hexapod_gait/balance_controller.py)
  (`BalanceController`), **pro Achse roll/pitch getrennt** konfigurierbar. Pro Achse
  **Zwei-Fenster-Hysterese + Totband-PI + Gyro-D + Slew + Anti-Windup + optionaler
  Dual-Tiefpass**: `error = 0 − m_fast`. **Hysterese** (behebt den Stufe-2-Rand-Chatter):
  regeln ab `|m_slow| ≥ outer`, stoppen (P=0, Integrator eingefroren = hält die Lage) bei
  `|m_fast| < inner` — bei `inner==outer` = altes Single-Totband. **Gyro-D** `d = −Kd·Drehrate`
  dämpft Wackeln, wirkt **immer** (auch im Hold), auf roher Rate; Ausgang/Integrator auf
  `max_level_angle` geclampt; Slew begrenzt `|Δcorr/dt|`. **Dual-Tiefpass** (fast/slow-EMA,
  nur wenn Eingang **roh** — `filter_*`): slow entscheidet „resume", fast „stop"; im
  terrain-Modus ist pitch ein Residual → `filter_pitch=False` (kein Doppelfilter mit dem
  Slope-Schätzer, Finding A). **Snap-Init:** erstes Sample nach `reset` = Messung. Schnittstelle
  `update(roll, pitch, dt, gyro_roll=0, gyro_pitch=0, filter_roll=True, filter_pitch=True)`.
  **Back-Compat:** `inner==outer` + `tau==0` + roll==pitch → exakt Stufe-2/TF-2-Verhalten.
  ⚠️ D + kleines τ rausch-verstärkend; auf HW `Kd` konservativ, Fenster/τ live tunen.
- **Stellpfad:** in der `GaitEngine` (`set_body_orientation_offset` →
  `compute_joint_angles`, in STANDING/WALKING/STOPPING). Pro Bein der B4-Round-Trip als
  **Rotation**: `leg_to_base_frame` → `rotate_xy(corr_roll, corr_pitch)` um den
  base-Ursprung → `base_to_leg_frame` → `leg_ik`. Vorzeichen: Fuß-Rotation = **−corr**
  (eine Fuß-Rotation A dreht den Körper um −A; sonst positive Rückkopplung).
- **State-abhängiger Clamp (Stufe 3a):** STANDING nutzt die volle Hülle
  (`leveling_max_angle_deg`, ~10° offline bewiesen); WALKING/STOPPING die **engere
  Walking-Hülle** (`leveling_max_angle_walking_deg`, ~4°) — der gelevelte **Swing-Apex**
  bindet. Mehr Walking-Range = Stufe 3c (hang-bewusste Schwunghöhe; `step_height` NICHT
  senken → Schürf-Gefahr bergauf). Offline: `tools/leveling_envelope_check.py --walking`.
- **Clamp + Fallback (Risiko 1):** die Korrektur wird **vor der IK** hart auf
  `max_level_angle` geclampt (offline als envelope-sicher bewiesen, s.u.). Wirft die IK
  trotzdem, wird die Korrektur skaliert (1→0.5→0.25→0) und neu versucht — **sanfte
  Degradation statt Roboter-Freeze**. Erst wenn selbst Skala 0 (reine Stand-Pose) failt,
  ist die Grundpose out-of-envelope → echter `IKError`. Limits = **URDF-geparst** (nicht
  config.py — „zwei Limit-Quellen").
- **ROS-Glue:** im Tick (STANDING/WALKING/STOPPING) `BalanceController.update` →
  `engine.set_body_orientation_offset`; sonst Reset + Offset 0/0. **TF-2:** im `terrain`-Modus
  speist der Node pitch = Residual (gegen die TF-1-Hang-Schätzung, die diesen Tick **vorher**
  in `_update_slope_estimate` aktualisiert wurde) + die signierten Gyro-Achsenraten für den
  D-Term. Bei aktivem Leveling + `leveling_startup_grace` wird die Stufe-1-Kipp-Erkennung
  während der Konvergenz unterdrückt (greift im terrain-Modus praktisch nie — Korrektur klein).
- **Parameter (live; Stufe 7: Gains + Fenster + Filter je Achse `_roll`/`_pitch`):**
  `leveling_enable` (Default **false**, Opt-in; flach No-Op), `leveling_mode`
  (`terrain`|`horizontal`, Default **terrain**), `leveling_{kp,ki,kd}_{roll,pitch}`,
  `leveling_deadband_{inner,outer}_deg_{roll,pitch}` (Zwei-Fenster-Hysterese; Default
  inner==outer==1.5 = aus), `leveling_slew_max_dps_{roll,pitch}`,
  `leveling_tau_{fast,slow}_s_{roll,pitch}` (Dual-Tiefpass; Default 0 = aus),
  `leveling_max_angle_deg` (STANDING-Clamp, **10°**, gemeinsam),
  `leveling_max_angle_walking_deg` (WALKING-Clamp, **4°**), `leveling_startup_grace`.
  **Code-Default = Stufe-2-Verhalten** (E9); die HW-Arbeitswerte (Hysterese/Filter/per-Achse)
  leben in `config/presets/hw_balance.yaml`.
- **Quer-/Diagonal-Traversieren** (Hang seitlich) ist **noch nicht** abgedeckt: `terrain`
  regelt roll→0 (Geradeaus-Klettern). Sauberes Quer-Laufen braucht roll-Residual **+**
  `cmd_vel`-Richtungslogik → eigener Nachfolge-Block (`TF-Quer`). Kanten/Stufen (kein
  Bodenkontakt) = Stufe 4 (Fußtaster), kein Balance-Problem.
- **Envelope-Beweis:** [`tools/leveling_envelope_check.py`](../../tools/leveling_envelope_check.py)
  prüft offline (echte URDF-Limits + CoG via `compute_load`), dass die gelevelte Stand-Pose
  bei θ in-limit + CoG-stabil ist. Bestätigt `max_level_angle=10°` für alle Stance-Modi
  × {roll, pitch, combined}; ab 12° (combined) wird's eng.
- **Schräg-Welten:** `ros2 launch hexapod_bringup slope.launch.py slope_deg:=8.0`
  (statische Box, Stufe 2) · `ros2 launch hexapod_bringup ramp.launch.py slope_deg:=8.0`
  (flach→Hang→Plateau zum Hineinlaufen, Stufe 3a). Beide spawnen **flach** (gz-IMU
  spawn-referenziert → sonst maskiert ein gepitchter Spawn die Neigung).

## Fußkontakt-Consumer + Diagnose (Block A5 Stufe 4 / S4-1)

Erste Teil-Stufe der terrain-adaptiven Lokomotion: der `gait_node` **konsumiert** den
vorhandenen Fußkontakt-`Bool` und **verifiziert** ihn quantitativ — **kein Verhaltens-Change**
(der adaptive Touchdown selbst ist S4-2). De-risked das Signal, bevor Verhalten darauf baut.

- **Pipeline (existiert):** gz-Contact-Sensor pro `foot_link` → ros_gz_bridge →
  [foot_contact_publisher](../hexapod_sensors/hexapod_sensors/foot_contact_publisher.py) (Event→
  Dauer-`Bool`, 50 Hz) → `/leg_<n>/foot_contact`. Läuft per Default (`enable_foot_contact:=true`).
- **Consumer:** `gait_node` abonniert die 6 Topics (QoS 10) → `self._foot_contact[leg_id]`
  (graceful ohne Pipeline → alle `False`). Publisht `/foot_contacts` (`Float64MultiArray`, 6× 0/1).
- **Engine read-only:** `GaitEngine.leg_gait_states(t)` → pro Bein `(is_swing, local_phase)` (nur im
  WALKING echte Phase; sonst alle `(False, 0.0)`). Single Source of Truth — reuse für S4-2/S4-5.
- **Diagnose:** ROS-frei in [contact_diagnostic.py](hexapod_gait/contact_diagnostic.py)
  (`ContactDiagnostic`): misst pro Bein **Touchdown-Latenz** (Ticks zwischen Stance-Start und
  Kontakt-Anstieg; bei 50 Hz = 20 ms/Tick), **Apex-Fehlkontakt** (Kontakt im Schwung), **Stance-
  Aussetzer** (kein Kontakt im belasteten Stance), **Quote**. **Misst nur, reagiert nicht** (die
  Reaktion ist S4-5). Throttled-Log (1 Hz) + `/foot_contacts`.
- **Warum nötig:** dokumentierte Schwäche (JTC-Lag → Fuß schwebt knapp; „schneller Cycle weniger
  zuverlässig"). Vor dem adaptiven Touchdown muss feststehen, dass der Kontakt **rechtzeitig**
  (steigende Flanke ≤ ~2 Ticks) **und plausibel** feuert — flach **und** am Hang, über
  `cycle_time`/`step_height`.
- **Parameter (live):** `foot_contact_debug_enable` (Default **true**; throttled-Log an/aus).

## Adaptiver Touchdown (Block A5 Stufe 4 / S4-2)

Zweite Teil-Stufe: ein Fuß reicht auf **tieferes** Terrain nach (Knick-Übergang, Loch, abfallender
Boden) statt an fester Höhe in der Luft zu „landen". Methode = **fixed-timing** (Gait-Uhr
unverändert), **nur die Fuß-z-Komponente** wird kontakt-adaptiv (x,y = nominaler Vortrieb).

**Design = Option A (downward-only, an `body_height` verankert, lag-tolerant).** Ein erster Entwurf
(Senkung vom Schwung-Apex bis Floor, Freeze an der Kontakthöhe) erzeugte in der Sim eine
**closed-loop-Körper-Höhen-Instabilität**: er ersetzte die feste Stance-Höhe (= den Open-Loop-Körper-
Anker) durch „Fuß = Kontakthöhe", und der ~13-Tick-Kontakt-Lag (NICHT geschwindigkeitsabhängig)
ließ den Fuß auf flachem Boden über den echten Boden hinausreichen → Körper driftete → Ducken/
Rückwärtslaufen. Option A behebt das:

- **Anker bleibt:** nominaler Schwung-Bogen **und** nominale Stance (`z = body_height`) bleiben
  unverändert → flacher Boden = exakt das bisherige Verhalten (stabil).
- **Nur nach unten, erst nach einem Gate:** das Adaptive senkt den Fuß **nur unter `body_height`**
  und **erst ab `touchdown_probe_start_stance_phase`** (Default 0.35 der Stance), wenn bis dahin
  **kein Kontakt** kam. Das Gate wartet den Kontakt-Lag auf Nominalhöhe ab.
  - **Kontakt vor dem Gate** (flacher/höherer Boden) → bei `body_height` verankern, **kein**
    Tieferreichen → keine Körper-Drift.
  - **Kein Kontakt bis zum Gate** (Boden liegt tiefer) → langsam (linear in der Stance-Phase =
    konstante Senk-Geschwindigkeit) von `body_height` bis `body_height − touchdown_max_extra_depth`
    (Floor) nachreichen; bei Kontakt das aktuelle (tiefere) z als `touchdown_z` einfrieren =
    echte Terrain-Höhe für den Rest der Stance.
  - **Kein Kontakt bis Fenster-Ende** (`touchdown_search_end_stance_phase`, Default 0.6) → Floor
    halten **nur wenn das Bein wirklich gesucht hat** (`_td_searched`); sonst (Walk-Start mitten
    in der Stance) `body_height`.
- **Walk-Start sauber:** beim WALKING-Eintritt werden Beine, die bereits in der Stance sind, auf
  `body_height` **vorverankert** (kein 1-Cycle-Probe). Schwung-Beine starten frisch.
- **Bewusst aufgegeben (waren die Instabilitätsquelle):** „Buckel → höher einfrieren" und
  „flat-Latenz senken". Buckel/höherer Boden werden vom Open-Loop genommen (Fuß bei `body_height`).
- **Fallback = nominal, nie load-bearing:** `adaptive_touchdown_enable` Default **false** (Opt-in).
  Der Node verUNDet den Param pro Tick mit einem **Contact-Live-Guard** (Pipeline frisch =
  „je empfangen UND letzte `Bool`-Message < 0.5 s her"; der Publisher publisht 50 Hz dauernd,
  Stille = toter Publisher) → tote/abwesende Pipeline schaltet adaptiv **aus**. Engine ROS-frei
  (`set_foot_contacts()` + `adaptive_touchdown_enable` vom Node, **vor** `compute_joint_angles`).
- **Envelope:** der Probe-z ist auf den Floor `body_height − max_extra_depth` geklemmt; dieser ist
  offline envelope-verifiziert (`walking_envelope_check check --scenario all`, GREEN mittel+hoch
  bei `max_extra_depth` 0.02). IKError-Fallback bleibt nur Backstop.
- **Parameter (live):** `adaptive_touchdown_enable` (false), `touchdown_probe_start_stance_phase`
  (0.35, ∈[0,1)), `touchdown_search_end_stance_phase` (0.6, ∈(0,1], > probe_start),
  `touchdown_max_extra_depth` (0.02 m, ≥0).
- **Isoliert testen:** `leveling_enable:=false` (IMU/TF getrennt von der per-Fuß-Adaption).

## Terrain-anpassendes Stehen / Adaptive Stand (Block A5 Stufe 4 / S4-7)

Der **statische Zwilling** des adaptiven Touchdowns: auf unebenem Grund soll der Roboter im
**STANDING** die Beine einzeln **bis zum Boden absenken** (aufsetzen) statt in der Luft zu hängen
(User-Befund Rubicon: `[001101]` = 3 Beine ohne Kontakt). Dieselbe Mechanik wie S4-2, nur statisch:

- **Downward-only ab `body_height`:** pro Bein senkt `_adaptive_stand_z` (in `_compute_standing_targets`)
  über die seit dem STANDING-Eintritt verstrichene Zeit (`stand_conform_rate · (t − t_stand_entry)`,
  zeitgesteuert = deterministisch) nach unten, bis der Taster **Kontakt** meldet → dort **einfrieren**
  (echte Terrain-Höhe des Beins). Früher Kontakt (Erhöhung/flach) → verankert ~`body_height`; späterer
  (Senke) → verankert tiefer. Erreicht es den **Floor** (`body_height − stand_conform_max_depth`) ohne
  Kontakt (Dip zu tief) → dort halten (so tief wie envelope-erlaubt, kein Durchsacken). **x,y nominal**
  (nur z adaptiv).
- **AUS = bit-identisch:** `adaptive_stand_enable` Default **false** → `_compute_standing_targets`
  liefert exakt die starre Flachboden-Pose, **keine** State-Mutation (keine Regression). Derselbe
  **Contact-Live-Guard** wie S4-2 (toter/stale Publisher > 0.5 s → adaptiv aus → starre Pose).
- **Re-Konform (envelope-sicher):** bei **STANDING-(Wieder-)Eintritt** (Terrain kann sich geändert
  haben) und bei **`body_height`-Änderung** im Stand (`/cmd_body_height` oder Param) senkt die Engine
  **neu** ab (statt einen Offset mitzureiten → keine Überstreckung des Bein-Kegels). Ein Live-Enable
  mitten im Stand setzt ebenfalls einen frischen Konform-Anker.
- **Grenzen (v1, → später §6 des Plans):** tiefe Dips (> `max_depth`) hängen am Floor; Buckel (Boden
  über `body_height`) → Open-Loop bei `body_height`. Beides braucht **Körperhöhen-/Neigungs-Adaption**
  (der große Nachfolger, dort kommt die IMU ins Spiel). Konform-Richtung = Bein-Frame-z (v1-Näherung).
- **Offline-Envelope:** `tools/stand_conform_envelope_check.py` prüft die Stand-Pose bis zum Floor je
  Stance-Höhe gegen die **URDF**-Limits (zwei-Limit-Quellen) — tief/mittel/hoch GREEN bei Default 0.04
  (Floor hoch −0.140); **Envelope-Grenze über alle Modi = 0.05** (0.06 → "hoch" out-of-reach).
- **Parameter (live):** `adaptive_stand_enable` (false), `stand_conform_max_depth` (0.04 m, ≥0;
  Rubicon-Unebenheit ~3–5 cm; 0.02 war zu flach), `stand_conform_rate` (0.02 m/s, >0).

## Slip / Kontaktverlust → Freeze (Block A5 Stufe 4 / S4-4)

Ein **belasteter Fuß ohne Halt** — über eine Kante/einen Abgrund (der adaptive Touchdown findet bis
`cliff_depth` keinen Boden) oder weil ein Stance-Fuß den Kontakt **verliert** (Slip) — löst einen
**Freeze** (Safe-State) aus, bevor der Roboter kippt oder von einer Kante läuft. Reaktion = identisch
zum Stufe-1-Tip-CRIT (`/hexapod_safety_freeze` + lokaler Stopp, gelatcht, einmalig).

- **`SupportMonitor`** ([support_monitor.py](hexapod_gait/support_monitor.py), ROS-frei, wie
  `TipMonitor`): **Kern-Regel — ein Stance-Bein, das nach der Stance-Phase-Grace
  (`slip_grace_stance_phase`, 0.6) keinen Kontakt hat, gilt als „Halt verloren".** Die Grace lässt
  dem Touchdown/Probe Zeit (deckt den ~13-Tick-JTC-Lag); danach = echter Stütz-Verlust.
  **Leaky-Zähler** (Sim-Befund): bei Kontakt wird der Verlust-Zähler nur um 1 **dekrementiert** (nicht
  voll zurückgesetzt) — robust gegen **intermittierenden Kontakt beim Kippen über die Kante** (Beine
  brühren beim Neigen den Boden, was einen reset-auf-0-Zähler ausbremsen würde); legitimes Prellen
  (~50 % Kontakt) bleibt netto gedeckelt → kein Fehlalarm. Entprellung (`slip_debounce_ticks`, 8)
  muss den `contact_timeout` (0.1 s ≈ 5 Ticks, der die **fallende** Slip-Flanke verzögert)
  überschreiten. Erreichen `slip_min_lost_legs` (1) Beine den Verlust → **Freeze gelatcht**.
- **`cliff_depth` (0.03) = die Grenze zwischen folgbarem Terrain und „Abgrund":** ein Abfall
  **≤ cliff_depth** wird vom adaptiven Touchdown (S4-2) noch **gefunden** (Fuß setzt auf → gestützt,
  kein Freeze); ein Abfall **> cliff_depth** → kein Kontakt → (entprellt) **Freeze**. Bei armierter
  Erkennung wird `cliff_depth` als adaptiver **Probe-Floor** auf die Engine gespiegelt
  (`engine.cliff_probe_depth`), sodass der Fuß über einer Kante aktiv bis `cliff_depth` nach Boden
  sucht. Envelope: 0.03 → Floor −0.11 (GREEN bis −0.12 geprüft).
- **Gating:** nur in WALKING ausgewertet (Vortrieb über Kanten); sonst Monitor-Reset. **Recovery**
  über State-Wechsel (cmd_vel=0 → STOPPING → reset), wie Stufe 1. Default `slip_detection_enable`
  **false** (Opt-in).
- **Parameter (live):** `slip_detection_enable` (false), `cliff_depth` (0.03 m),
  `slip_debounce_ticks` (8), `slip_min_lost_legs` (1, ∈[1,6]), `slip_grace_stance_phase` (0.6).
  Monitor-Params live mit Rebuild.
- **Abgrenzung:** „Bein zurückziehen / Schritt nicht committen" = später (S4-4b); Sensor-Fault-
  Plausibilität = S4-5. v1 = nur Freeze.

## Sensor-Plausibilität / Fault-Fail-Safe (Block A5 Stufe 4 / S4-5)

Ein **defekter Fußkontakt-Sensor** darf das Verhalten nicht verschlechtern. Leitprinzip: **Taster =
Optimierung, nie load-bearing** — ein Sensor-Fault **degradiert** (das Bein fällt auf Open-Loop
zurück), er **stoppt nicht**. HW-gerichtet/defensiv (echte Microswitches prellen/klemmen/sterben,
Phase E2); in der zuverlässigen Sim (`miss 0`) nur via Test-Hook provozierbar.

- **Plausibilitäts-Anker = die Gait-Phase** (geometrische Grundwahrheit). Zwei Fehlerbilder:
  - **stuck-on** (klemmt „Kontakt"): ein gesunder Fuß ist im **Schwung-Apex** in der Luft → Kontakt
    dort ist unmöglich. **⚠️ Sim-Realität (Befund T1):** der gz-Kontakt + `contact_timeout` +
    Fußkugel-Clearance meldet auch bei **gesunden** Beinen **lückenhaften** Kontakt im Apex (das
    S4-1/S4-2-„Apex-Artefakt") → eine naive „irgendein Apex-Kontakt = Fault"-Logik flaggt reihenweise
    gesunde Beine. **Robuster Diskriminator:** ein **Schwung-Pass durch das Apex-Band
    (`sensor_apex_band_low/high` 0.3/0.7) mit Kontakt an JEDEM Tick (lückenlos)**, über
    `sensor_apex_fault_cycles` (3) **aufeinanderfolgende** Pässe. Ein klemmender Sensor (immer True)
    liefert lückenlose Pässe; ein gesundes Bein hat pro Pass eine Lücke → Reset → trippt nie (auch der
    Walk-Start-Transient = ein einzelner Pass wird gefiltert). stuck-on korrumpiert beide Vorstufen:
    er friert den adaptiven Touchdown (S4-2) per Phantom-Kontakt zu früh ein UND täuscht S4-4 „immer
    gestützt" vor (→ kein Freeze über einer Kante, gefährlich). Das Band beginnt bei **0.3**, damit der
    `contact_timeout`-Nachhall (~5 Ticks am Schwung-Anfang, Phase < 0.3) keinen Pass öffnet.
  - **dead/stuck-off** (klemmt „kein Kontakt" / tot): **überhaupt kein Kontakt** über
    `sensor_dead_cycles` (2) Cycles → Fault. Resettet bei **jedem** Kontakt → ein stuck-on-Sensor
    (immer True) erscheint **nie** als dead (sonst überschriebe das den `stuck_on`-Grund). Weniger
    gefährlich (Bein bekommt nur keine Optimierung → Open-Loop), löst aber in S4-4 sonst einen
    Dauer-**Fehl-Freeze** auf gutem Boden aus.
- **`SensorHealthMonitor`** ([sensor_health_monitor.py](hexapod_gait/sensor_health_monitor.py),
  ROS-frei, wie `TipMonitor`/`SupportMonitor`): Pass-Logik (lückenlose Apex-Pässe) + **Latch** (faulty
  bleibt bis `reset()`). `sensor_apex_fault_cycles` zählt **Schwung-Pässe** (= Cycles), `sensor_dead_cycles`
  ist in **Cycles**; der Node rechnet `dead_ticks = dead_cycles · cycle_time · tick_rate` (Rebuild bei
  cycle_time/tick_rate-Änderung) — analog zu `slip_grace_stance_phase` als Phasen-Bruch.
- **Reaktion = ignorieren + warnen (kein Freeze):** ein geflaggtes Bein wird latched **maskiert**:
  - **S4-2 adaptiv-aus** für das Bein (Engine `set_adaptive_masked_legs` → nominaler Bogen, Open-Loop;
    der unzuverlässige Kontakt steuert das Fuß-z nicht).
  - **S4-4 aus der Stütz-Zählung ausgeschlossen** (als „nicht Stance" durchgereicht → der
    `SupportMonitor`-Verlust-Zähler bleibt 0): ein totes Bein löst keinen Fehl-Freeze aus, ein
    stuck-on-Bein täuscht keine Stütze vor. Backstop bleibt der Stufe-1-Tip + die gesunden Beine.
  - **⚠️ Race-Fix (Befund T2): „nie kontaktiert" → sofort aus dem Slip-Freeze.** Die volle dead-
    Erkennung braucht 2 Cycles (~4 s), der Slip-Freeze würde aber schon nach Grace+Debounce (~1 s)
    feuern → ohne Zusatz **gewinnt der Freeze das Rennen** und stoppt den Roboter. Daher: ein Bein,
    das diese WALKING-Episode **nie** Kontakt hatte (toter/stuck-off-Sensor von Anfang an), gab nie
    Stütze → kann sie nicht „verlieren" → wird **sofort** aus der Slip-Zählung ausgeschlossen
    (`_ever_contacted`, nur bei aktivem S4-5 — pures S4-4 behält sein striktes Freeze-Verhalten). Ein
    **echter** Slip/Kante (Bein **hatte** Kontakt, verliert ihn) friert weiter sofort. **Bewusste
    Grenze (Plan §0):** ein Sensor, der **mitten im Lauf** stirbt, ist vom echten Slip nicht
    unterscheidbar → bleibt ein sicherer Freeze.
  - **Bei aktivem Safety-Freeze** (Slip/Tip) wird die Sensor-Health **nicht** ausgewertet (reset): der
    Roboter ist eingefroren, aber `t` läuft weiter → die berechnete Phase cyclet über eingefrorene
    Kontakte → sonst Geister-Flags (Befund T2).
  - **WARN-Log** (steigende Flanke, englisch in diesem Stage) `Sensor fault leg N (stuck_on|dead) —
    ignoring contact …` + throttled Reminder (5 s) `Foot-contact sensor(s) masked: […]`.
- **Sim-Test-Hook `sensor_fault_inject`** (Default aus, Debug): `'<leg>:stuck_on'` / `'<leg>:stuck_off'`
  zwingt den gecachten Kontakt EINES Beins auf einen Klemm-Wert (jeden Tick neu, vor allen Consumern)
  → erlaubt, die Erkennung in der fault-freien Sim zu provozieren. `''` / `'none'` = aus.
- **Gating:** nur in WALKING ausgewertet (sonst Reset → Latch fällt beim Anhalten). Default
  `sensor_plausibility_enable` **false** (Opt-in).
- **Parameter (live):** `sensor_plausibility_enable` (false), `sensor_apex_band_low/high` (0.3/0.7),
  `sensor_apex_fault_cycles` (3), `sensor_dead_cycles` (2), `sensor_fault_inject` (''). Monitor-Params
  live mit Rebuild.
- **Abgrenzung / bewusst NICHT (v1):** Auto-Recovery/Un-Flag bei wieder-gesundem Sensor (latched bis
  State-Wechsel; die WARN-Logs bleiben trackbar → erst beobachten, dann ggf. S4-5b); der mehrdeutige
  mid-Stance-Gap bleibt der **sichere S4-4-Freeze** (echter Halt-Verlust > Sensor-Annahme); echte
  HW-Taster-Faults (E2); Redundanz/Voting mehrerer Sensoren.

## Launch-Quickstart

### Stand-Pose anfahren

```bash
ros2 launch hexapod_gait stand.launch.py
```

Fährt alle 6 Beine in
`(radial=0.295, 0, body_height=-0.080)` (Phase 13 Stage 0.4 Stand-Pose,
in URDF-Limits). Beendet sich nach ~5 s.

### Stand-up / Aufstehen (Phase 13 Stage 0.4)

Auf der echten Hardware ist `stand_node` (one-shot, cartesian) **nicht** der
Aufsteh-Pfad — das macht der **STARTUP_RAMP-State** in `gait_node`/`gait_engine`:

- Nach dem HW-Plugin-Init (`hexapod_hardware` Stage 0.3) stehen die Servos auf
  der **power_on_mid-Pose** (Servo-Mitte 1500 µs: Femurs ~27° hoch, Beine
  angehoben/eingezogen, Bauch liegt auf).
- `gait_node` liest diese Pose beim ersten `/joint_states`-Empfang und rampt
  per Smooth-Step (`s = p²(3−2p)`) **alle 6 Beine gleichzeitig** in Joint-Space
  zur Stand-Pose hoch — der Hexapod **steht vom Bauch auf**. Auto-Übergang →
  STANDING bei `progress ≥ 1`; `cmd_vel` wird während des Ramps ignoriert.
- **all-6 simultan, nicht Tripod 3+3** (Stage-0 DL-7): Beim Aufstehen vom Bauch
  ist Bauch/Boden die Stütze, nicht die Beine — kein Stativ nötig. Tripod 3+3
  braucht man nur, wenn der Körper allein auf den Beinen steht und Füße
  umgesetzt werden (z. B. Bein-Radius im Stand ändern). all-6 verteilt zudem die
  Lift-Last auf 6 statt 3 Servos.
- **Stand-Pose = radial 0.295 / body_height −0.080** (tibia 0.758 rad, klar in
  URDF-Limit ±1.161). Stage 0.4 hat hier einen latenten Bug behoben: die alte
  Pose (radial 0.27 / −0.052) verlangte tibia 1.33 rad > Limit 1.161 → auf HW
  Stage-0.5-Freeze für die rechten Beine. In der lenienten Phase-5-Sim
  (IK ohne Limit-Check) nie aufgefallen; die Stand-Pose wurde bei der Stage-F-
  Limit-Verengung (2026-05-25) nicht mitgezogen. Weitere gültige
  (body_height, radial)-Höhen: `phase_13_stage_0_4_standup_plan.md` Tab. 3.3,
  per Param live anfahrbar.
- **In-Limits garantiert**: Smooth-Step interpoliert monoton zwischen
  power_on_mid und Stand-Pose; beide liegen in den URDF-Limits → jeder
  Zwischenwert auch. Kein Stage-0.5/0.6-Plugin-Freeze während des Aufstehens
  (Tests `test_power_on_mid_start_ramp_in_limits` + `test_stand_pose_in_limits_for_all_legs`,
  beide mit den ECHTEN URDF-Limits coxa ±0.415 / femur ±1.57 / tibia ±1.161).
- Param `auto_standup_duration` (Default 4.0 s) steuert die Ramp-Dauer. Das
  obsolete `suspended`-Preset (femur=+1.45) ist **nicht** mehr der Startpunkt
  (war Pre-0.3).

### Kartesisches schürffreies Aufstehen (Phase 13 Stage 0.7, **Default**)

Der joint-space-STARTUP_RAMP (oben) interpoliert die **Winkel** linear — dadurch
hält er die Fuß-x-Position **nicht** konstant: die Füße wandern beim Hochdrücken
~15–22 mm nach innen. Am Boden = **Schürfen unter Last** → hoher Strom (>3,5 A
gemessen, Bench-PSU bricht ein), obwohl das *Stehen* nur ~400 mA kostet. Wurzel
ist also die Reibung, nicht die Hub-Last. Der **`CARTESIAN_STANDUP`-State** löst
das (neuer Default, `standup_mode:=cartesian`):

- **Phase 1 — Touchdown** (bauch-gestützt, Anteil `standup_phase1_fraction`,
  Default 0.4): Füße kartesisch von power_on_mid (via `leg_fk`) nach unten zu den
  Boden-Aufsetzpunkten `(radial, 0, body_height_start)`. Der Bauch trägt, die
  Füße sind unbelastet/in der Luft → keine Reibung. `body_height_start ≈
  −0.0135 m` = Coxa-Höhe bei aufliegendem Bauch (Bauch-Box 0.043 / Foot-R 0.008).
- **Phase 2 — Push** (Füße fix): x+y bleiben am Aufsetzpunkt, nur `body_height`
  rampt zu −0.080 → Körper hebt **senkrecht** über den fixen Füßen. Da der
  horizontale Hebelarm (= radial) konstant bleibt, bleibt das Stütz-Drehmoment
  auf Stand-Niveau → **kein Schürfen, kein Strom-Peak** (by design).
- **Endpose identisch** zum joint-space-Ramp (radial 0.295 / −0.080) — nur der
  *Weg* dorthin ist schürffrei. `cmd_vel` wird wie beim STARTUP_RAMP ignoriert,
  Auto-Übergang → STANDING bei `progress ≥ 1`.
- **In-Limits/Reachability** ist hier (anders als beim monotonen joint-space-Lerp)
  nicht trivial — daher per Test über den ganzen Pfad belegt
  (`test_cartesian_standup.py`: `path_in_limits`, `reachable_no_ikerror`,
  `phase2_foot_xy_constant` = Schürf-frei-Beweis, `phase1_no_premature_ground_contact`,
  `endpoint_is_stand_pose`). Vorab-Validierung: `tools/standup_envelope_check.py`.
- **Mode-Switch:** `standup_mode` ∈ {`cartesian` (Default), `joint_space`
  (Legacy-STARTUP_RAMP, aufgebockt nützlich)}. Params `standup_phase1_fraction`,
  `body_height_start` sind STANDING-only + live-justierbar.
- **Done-Kriterium** (Stage 0.7): Aufsteh-Strom am **Boden** nahe Stand-Niveau
  statt >3,5 A — das misst erst der HW-Boden-Test (Stage 0.8), nicht die Sim.

### Gait starten

```bash
# Default: STANDING bis cmd_vel kommt
ros2 launch hexapod_gait gait.launch.py

# Demo-Mode: läuft sofort vorwärts ohne externe cmd_vel
ros2 launch hexapod_gait gait.launch.py default_linear_x:=0.05

# Demo-Mode: läuft im Bogen
ros2 launch hexapod_gait gait.launch.py \
  default_linear_x:=0.03 default_angular_z:=0.15

# Stufe-E-Backward-Compat: nur ein Bein schwingt
ros2 launch hexapod_gait gait.launch.py \
  gait_pattern:=single_leg_1 default_linear_x:=0.05

# Phase 11 Stage D: mit Preset-File starten
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
```

### Phase 11 — Live-Param-Tuning + Preset-Workflow

- Stage A — alle 14 gait_node-Params sind live via `ros2 param set` /
  `rqt_reconfigure` tunbar (Range-Constraints + atomic-all-or-nothing-
  Validation). Details in [gait_node.py](hexapod_gait/gait_node.py)
  `_GAIT_PARAMS`-Tabelle.
- Stage D — Preset-YAMLs unter [`config/presets/`](config/presets/),
  ladbar via `params_file:=<path>.yaml`-Launch-Arg. Erzeugung via
  `ros2 param dump /gait_node ...`.
- **Convenience:** [`tools/hexapod-shell-aliases.sh`](../../tools/hexapod-shell-aliases.sh)
  bietet `hexapod-save-walking-params`, `hexapod-load-walking-preset`,
  `hexapod-save-cal` etc. Opt-in: in `~/.bashrc` aufnehmen.
- **Setup-Doku:** [`docs_raspi/phase_11_rqt_setup.md`](../../docs_raspi/phase_11_rqt_setup.md)
  beschreibt rqt-Multi-Plugin-Aufbau + Save/Load-Workflows.
- **Workshop-Doku** (Stage E):
  [`docs_raspi/phase_11_sim_tuning_workshop.md`](../../docs_raspi/phase_11_sim_tuning_workshop.md)
  mit 6 Test-Szenarien (defensive/demo/aggressive Walk, Drehen,
  Kurvenfahrt, body_height-Variation) — Sim-Manual für sinnvolles
  Walking-Tuning.

### Walk steuern via cmd_vel

```bash
# Vorwärts
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.05}}'

# Drehen gegen Uhrzeigersinn
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{angular: {z: 0.3}}'

# Seitwärts +Y (links)
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {y: 0.05}}'

# Bogen
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.03}, angular: {z: 0.2}}'

# Stoppen
ros2 topic pub --once /cmd_vel geometry_msgs/Twist '{linear: {x: 0.0}}'
```

## cmd_vel-Format

`geometry_msgs/Twist`. Verwendete Felder:

| Feld | Bedeutung | Range |
|---|---|---|
| `linear.x` | Vorwärts/Rückwärts (m/s, base_link +X) | clamped auf `±linear_max` |
| `linear.y` | Seitwärts (m/s, base_link +Y = links) | clamped auf `±linear_max` |
| `angular.z` | Drehung (rad/s, +z = gegen Uhrzeigersinn von oben) | clamped auf `±linear_max / R_max` |

**`linear.z`, `angular.x`, `angular.y` werden ignoriert** — Body bleibt
horizontal in Phase 5.

**Clamping** (Stufe-H-Design-Entscheidung 1): wenn die maximale
Bein-Geschwindigkeit `|v_at_leg_mount|` über `linear_max` läuft, werden
alle drei Inputs proportional skaliert. Bewegungs-Richtung bleibt
erhalten, nur langsamer. Engine loggt `cmd_vel clamped`-Warning
(throttled 2 s).

## Knoten-Parameter

`gait_node` (stand:`stand.launch.py`, gait:`gait.launch.py`):

| Parameter | Default | Bedeutung |
|---|---|---|
| `gait_pattern` | `'tripod'` | Preset aus `GAIT_PRESETS`: tripod, single_leg_1..6 |
| `step_length_max` | `0.05` | Max Schritt-Länge (m) — definiert `linear_max = step_length_max / stance_duration` |
| `default_linear_x` | `0.0` | Fallback Vorwärts (m/s) wenn keine cmd_vel ankommt |
| `default_linear_y` | `0.0` | Fallback Seitwärts (m/s) |
| `default_angular_z` | `0.0` | Fallback Drehung (rad/s) |
| `cmd_vel_timeout` | `0.5` | Sekunden ohne cmd_vel → Fallback auf Defaults |
| `cycle_time` | `2.0` | Sekunden pro Tripod-Cycle (1 s Swing + 1 s Stance) |
| `step_height` | `0.03` | Schwung-Höhe (m über Stand-Pose) |
| `body_height` | `-0.052` | Stand-Pose Foot-Z (m, Bein-Frame) |
| `radial_distance` | `0.27` | Stand-Pose Foot-X (m, Bein-Frame) |
| `tick_rate` | `50.0` | Engine-Loop-Rate (Hz) |
| `time_from_start_factor` | `2.0` | JTC-Lookahead = factor / tick_rate |
| `leveling_enable` | `false` | Body-Stabilisierung aktivieren (Opt-in; flach No-Op) |
| `leveling_mode` | `terrain` | TF-2: `terrain` (roll→0, pitch folgt Hang) vs. `horizontal` (Voll-Leveln) |
| `leveling_{kp,ki}_{roll,pitch}` | `0.4` / `0.1` | PI-Gains je Achse (Stufe 7, live) |
| `leveling_kd_{roll,pitch}` | `0.03` | Gyro-Dämpfung (Wackeln); `0` = kein D |
| `leveling_deadband_{inner,outer}_deg_{roll,pitch}` | `1.5` / `1.5` | Zwei-Fenster-Hysterese; inner==outer = aus (Stufe 7) |
| `leveling_tau_{fast,slow}_s_{roll,pitch}` | `0.0` | Dual-Tiefpass (nur roher Eingang); 0 = aus (Stufe 7) |
| `leveling_slew_max_dps_{roll,pitch}` | `8.0` | Slew-Rate-Limit der Korrektur (°/s) |
| `leveling_max_angle_deg` | `10.0` | STANDING-Clamp vor IK (gemeinsam, offline-bewiesen) |
| `leveling_max_angle_walking_deg` | `4.0` | WALKING/STOPPING-Clamp (Stufe 3a, Swing-Apex bindet) |
| `leveling_startup_grace` | `true` | Tip während Leveling-Konvergenz unterdrücken |
| `slope_aware_tip_enable` | `true` | TF-1: Tip gegen Residual (IMU − Hang) statt absolut |
| `slope_estimate_tau_s` | `0.5` | TF-1: Tiefpass-τ der Hang-Schätzung (s) |
| `slope_clamp_deg` | `40.0` | TF-1: Betrags-Grenze der Hang-Schätzung |
| `foot_contact_debug_enable` | `true` | S4-1: throttled-Log der Fußkontakt-Diagnose an/aus |
| `adaptive_touchdown_enable` | `false` | S4-2: adaptiver Touchdown an/aus (Opt-in; mit Contact-Live-Guard verUNDet) |
| `touchdown_probe_start_stance_phase` | `0.35` | S4-2: Stance-Phase-Gate, ab der ohne Kontakt nach unten gesucht wird (∈[0,1)) |
| `touchdown_search_end_stance_phase` | `0.6` | S4-2: Stance-Phase, bis zu der gesucht wird, dann Floor (∈(0,1], > probe_start) |
| `touchdown_max_extra_depth` | `0.02` | S4-2: max. Tiefe unter `body_height` (m, Floor; envelope-verifiziert) |
| `adaptive_stand_enable` | `false` | S4-7: terrain-anpassendes Stehen an/aus (Opt-in; mit Contact-Live-Guard verUNDet) |
| `stand_conform_max_depth` | `0.04` | S4-7: max. Absenk-Tiefe unter `body_height` im Stand (m, Floor; ≥0; envelope-Max 0.05 über alle Stance-Modi) |
| `stand_conform_rate` | `0.02` | S4-7: Absenk-Rate im Stand (m/s, >0) |
| `slip_detection_enable` | `false` | S4-4: Slip/Kontaktverlust → Freeze an/aus (Opt-in) |
| `cliff_depth` | `0.03` | S4-4: Grenze folgbares Terrain ↔ Abgrund (m unter `body_height`; > = Freeze) |
| `slip_debounce_ticks` | `8` | S4-4: Ticks ohne Halt bis Freeze (muss > contact_timeout ≈5) |
| `slip_min_lost_legs` | `1` | S4-4: gleichzeitig haltlose Stütz-Beine bis Freeze (∈[1,6]) |
| `slip_grace_stance_phase` | `0.6` | S4-4: Stance-Phase-Grace (darunter no-contact nicht gewertet) |
| `sensor_plausibility_enable` | `false` | S4-5: Sensor-Fault-Plausibilität an/aus (Opt-in; flaggt+maskiert, kein Freeze) |
| `sensor_apex_band_low` | `0.3` | S4-5: untere Schwung-Apex-Band-Grenze (< = past contact_timeout-Nachhall) |
| `sensor_apex_band_high` | `0.7` | S4-5: obere Schwung-Apex-Band-Grenze (low < high) |
| `sensor_apex_fault_cycles` | `3` | S4-5: aufeinanderfolgende Schwung-Pässe mit lückenlosem Apex-Kontakt bis stuck-on-Flag (≥1) |
| `sensor_dead_cycles` | `2` | S4-5: Cycles ohne Touchdown bis dead-Flag (cycle_time-unabhängig, ≥1) |
| `sensor_fault_inject` | `''` | S4-5 Test-Hook (Debug): `'<leg>:stuck_on'`/`'<leg>:stuck_off'` klemmt 1 Kontakt; `''`/`'none'`=aus |

## State-Machine

```
        cmd_vel(|v|>eps)             |v|≈eps
STANDING ────────────────► WALKING ────────────► STOPPING
   ▲                          ▲                      │
   │                          │ cmd_vel(|v|>eps)     │ alle Beine
   │                          └──────────────────────┘ settled
   │                                                  │
   └──────────────────────────────────────────────────┘
                    auto-Transition
```

- **STANDING**: alle 6 Beine in Stand-Pose, kein Cycle.
- **WALKING**: Tripod-Pattern, Foot-Vortrieb gemäß cmd_vel mit
  Mount-Yaw-Rotation pro Bein.
- **STOPPING**: Beine in der Luft schwingen mit eingefrorener step_vec
  fertig (max 1 s bei cycle_time=2). Stütz-Beine interpolieren in
  0.3 s zu Neutral. Worst-Case-Latenz: 1.3 s (cycle_time=2) bzw. 0.8 s
  (cycle_time=1).

## Hinsetzen / Abschalten (Block B1)

Umkehrung des Aufstehens — sicheres Beenden auf echtem Boden (sonst:
Strom weg → Servos zentrieren HW-bedingt → Roboter fällt).

```
STANDING ──sit_down──► REPOSITION(after=SITDOWN_LOWER) ──► SITDOWN_LOWER
        ──► SITDOWN_FLATTEN ──► SAT  (bestromt, idle, rad 0)
SAT ──stand_up──► CARTESIAN_STANDUP ──► (REPOSITION) ──► STANDING
STANDING/SAT ──shutdown──► (hinsetzen falls nötig) ──► SAT + Relay-Aus (terminal)
```

- **Phase 1 — Reposition aus**: Füße `radial_distance` → `standup_radial_distance`
  (raus), Reuse des REPOSITION-States via `start_reposition(after=SITDOWN_LOWER)`.
  Dauer = `reposition_cycle_time`.
- **SITDOWN_LOWER**: reverse-kartesisch — Füße x/y fix @ standup_radial, body_height
  → `body_height_start` (Bauch am Boden). Dauer = `sitdown_duration · sitdown_lower_fraction`.
- **SITDOWN_FLATTEN**: Joint-Space-Lerp aller Joints zur **Boot-/Spawn-Pose** (Beine
  hoch, = die Pose in der der Roboter gespawnt/gebootet ist; der Node schneidet die erste
  `/joint_states` mit und übergibt sie als `rest_joints`). NICHT rad 0 — rad 0 wäre das Bein
  horizontal gestreckt. Dauer = `sitdown_duration · (1 − sitdown_lower_fraction)`.
- **SAT**: bestromt-idle, hält die Boot-Pose (Beine hoch, Bauch trägt). `cmd_vel` wird in
  allen Sitdown-Phasen + SAT ignoriert. Aufstehen aus SAT nutzt das start-pose-agnostische
  `start_cartesian_standup`. Das passive Hinlegen der Beine passiert erst beim Relay-Aus.

**Services** (`std_srvs/Trigger`): `/hexapod_sit_down` (Rest, bestromt),
`/hexapod_stand_up` (SAT→STANDING), `/hexapod_shutdown` (sit + Relay-Aus, terminal).
**Relay-Aus** über `/hexapod_relay_set` (`std_srvs/SetBool`, `data=false`) —
nur im Shutdown; in Sim ohne Plugin übersprungen. **Shutdown ist terminal** (Latch):
`stand_up` danach abgelehnt bis Relay-On/Reboot.

**Comms-Loss-Fail-safe** (opt-in `comms_loss_sitdown_timeout`, Default 0 = aus): bei
verstummtem `/cmd_vel` (echtes Disconnect; idle-Controller autorepeatet 0) → Auto-
Hinsetzen (**Rest**, bestromt — bei Reconnect via `stand_up` wieder hoch). Triggert nur
aus STANDING (aus WALKING stoppt erst `cmd_vel_timeout`).

Detail-Plan + Self-Review: [project_finalization/B1_sitdown_plan.md](../../project_finalization/B1_sitdown_plan.md);
Test-Anleitung: [project_finalization/B1_sitdown_test_commands.md](../../project_finalization/B1_sitdown_test_commands.md).

## Gait-Pattern erweitern

Neue Gangart hinzufügen = neue Konstante in `gait_patterns.py`:

```python
WAVE = GaitPattern(
    name='wave',
    phase_offset_per_leg={1: 0.0, 2: 1/6, 3: 2/6,
                          4: 3/6, 5: 4/6, 6: 5/6},
    swing_duty=1/6,
)

GAIT_PRESETS = {..., 'wave': WAVE}
```

→ Engine-Code muss **null** angefasst werden. Pattern-Logik ist
identisch, nur die Daten unterscheiden sich. Siehe Stufe-F-Design-
Entscheidung 4 in
[docs/phase_5_progress.md](../../docs/phase_5_progress.md).

## Konzept-Hintergrund

- **IK-Math**:
  [docs/phase_5_ik_explained.md](../../docs/phase_5_ik_explained.md)
- **Gait-State-Machine + Body-Frame-Mapping + Tripod-Math**:
  [docs/phase_5_gait_explained.md](../../docs/phase_5_gait_explained.md)
- **Phase-5-Verlauf**:
  [docs/phase_5_progress.md](../../docs/phase_5_progress.md)
- **Test-Anleitungen pro Stufe**:
  [docs/phase_5_stage_C..H_test_commands.md](../../docs/)

## Tests aufrufen

```bash
cd ~/hexapod_ws
colcon test --packages-select hexapod_gait
colcon test-result --verbose --test-result-base build/hexapod_gait
```

Erwartet: **3 Tests, 0 Failures, 1 skipped**. Aktuell nur Style-Tests
(flake8, pep257); funktionale Tests werden Pure-Python via Smoke-
Tests in den Stufen-Test-Doks abgedeckt.

## Stolperfallen (aus Live-Bringup destilliert)

1. **Stale Prozesse** — `gait_node`, `stand_node`,
   `foot_contact_publisher`, `ros2 topic pub` — pro Test-Lauf
   komplett cleanen. Cleanup-Snippet in den
   `phase_5_stage_*_test_commands.md`.
2. **JTC-Tracking-Lag** im Continuous-Pub-Mode. Lösung:
   `body_height = -0.052` (5 mm Penetration global), Detail in
   Stufe-F-Designentscheidung.
3. **`use_sim_time` + `get_clock().now()` Race** — Timer-Logik
   nutzt `time.monotonic()` (Wall-Clock), nicht Sim-Time.
4. **cmd_vel mit `--once`** triggert nicht sicher Walk — wegen
   `cmd_vel_timeout` 0.5 s. Stattdessen `--rate 10` für
   kontinuierliche Pubs.
5. **`single_leg_*` Pattern + cmd_vel** — Wenn nur ein Bein im
   Pattern aktiv ist, schwingt es nicht zwingend in Body-X-Richtung.
   `gait_pattern:=single_leg_1` ist primär ein Stufe-E-
   Backward-Compat-Modus, kein Walk-Mode.
