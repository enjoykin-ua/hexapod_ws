# Phase 13 Stage 0 — Progress-Tracker + Design-Log

> Done-Kriterien-Vertrag für Stage 0 (CLAUDE.md §4). Bullets werden pro
> erledigtem Schritt sofort `[ ]`→`[x]` (Memory `feedback_phase_progress_tracking`).
> Plan-Übersicht: [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md).

**Stand:** 2026-05-30 — Sub-Stage 0.1 ✅ + Sub-Stage 0.2 ✅ FERTIG (Umbau +
Re-Cal + Femur-Limits ±1.57 + FW UV/OC-Relay-Gate-Fix; Live verifiziert,
Tests 351/0, Self-Review ohne 🔴). Bereit für Commit. Nächste: 0.3
(relay-gated Init-Sequenz — löst Init-Race + K3-Init-Pose).

---

## Sub-Stage 0.1 — Relay-Frame + Fail-safe + Plugin-Service ✅ FERTIG (2026-05-30)

Plan: [`phase_13_stage_0_1_relay_plan.md`](phase_13_stage_0_1_relay_plan.md)

- [x] 0.1.1  FW: RELAY_CONTROL=0x51 in config.hpp cmd-namespace
- [x] 0.1.2  FW: RELAY_PIN/relay_on Globals + GP26-Boot-LOW vor servos.init()
- [x] 0.1.3  FW: set_relay() Helper + handle_relay_control() + dispatch-Case
- [x] 0.1.4  FW: Fail-safe set_relay(false) in handle_reset + 3 Trip-Blöcke
- [x] 0.1.5  FW: RELAY_ON Status-Bit (1u<<6) in status-namespace + GET_STATE
- [x] 0.1.6  FW: Build clean (cmake .. && make -j$(nproc)) → exit=0, .elf gelinkt
- [x] 0.1.7  FW: tools/test_servo2040.py test_relay_control() grün auf HW (T1); C.3 soft-ramp-Fix (enable-vor-Ramp) grün
- [x] 0.1.8  FW: vom User geflasht (python3 tools/flash_and_verify.py)
- [x] 0.1.9  Plugin: encode_relay_control + opcode + RELAY_ON in servo2040_protocol
- [x] 0.1.10 Plugin: /hexapod_relay_set Service (SetBool) + serial_write_mutex_
- [x] 0.1.11 Plugin: on_deactivate sendet RELAY_CONTROL(off) vor Disable
- [x] 0.1.12 Plugin: colcon build hexapod_hardware grün
- [x] 0.1.13 Plugin: colcon test hexapod_hardware grün (12/12, neue Relay-Tests inkl.)
- [x] 0.1.14 Live: Relay klickt on/off via Service ✓ (T3)
- [x] 0.1.15 Live: Watchdog-Trip (pkill) droppt Relay ✓ (T4)
- [x] 0.1.16 RESET-Frame droppt Relay — FW-verifiziert in T1 (test_relay_control: "after RESET relay is OFF" ✓); kein Laufzeit-RESET-Service
- [x] 0.1.17 Self-Review-Tabelle (unten), keine 🔴-Fixe offen

### Sub-Stage 0.1 — Post-Review (2026-05-30)

| # | Punkt | Status |
|---|---|---|
| R1 | Serial-Write Thread-Safety: `write()` (CM-Thread) vs. Service-Callback (Executor-Thread) | OK — `serial_write_mutex_` an allen 4 `write_all`-Stellen, je Frame atomar (kein Lock über Sleeps) |
| R2 | `handle_reset` RELAY_ON-Bit-Clobber durch `status_flags = …`-Reassign | OK — `set_relay(false)` davor; beide ergeben Bit=0, konsistent |
| R3 | Boot: GP26 LOW vor `servos.init()` (Floating-Window) | OK — erste Statements in `main()`, direkt `gpio_put(...,0)` |
| R4 | Loopback `on_deactivate` darf keinen Relay-Frame senden | OK — Relay-Block liegt nach dem Loopback-Early-Return; `LoopbackActivateAndDeactivateAreFast` grün |
| R5 | `on_deactivate` Relay-Off wenn Reader tot | OK — `if(!reader_.died())` geguarded; FW-Watchdog ist Backstop |
| R6 | RELAY_CONTROL(on) **während latched Trip** → Rail an + Servos disabled (PWM aus) → MID-Drift-Risiko | 🟡 vormerken für 0.3 — kein Normalpfad (Recovery ist RESET, der Relay droppt; `on_activate` sendet RESET zuerst). Ggf. Guard „kein relay-on bei latched Trip" in 0.3 |
| R7 | Service-Callback hat keinen dedizierten Unit-Test (Executor+Client schwer) | 🟢 später — encode+write-Glue ist via `PtyDeactivateSendsDisableForAllServos` (sendet echten Relay-Frame über PTY) abgedeckt; Callback selbst live in T3 |
| R8 | GET_STATE-Payload-Größe durch RELAY_ON geändert? | OK — RELAY_ON ist nur ein Bit im bestehenden `status_flags`-Byte, Payload-Layout unverändert |
| R9 | Encoder-Korrektheit (opcode 0x51, len 1, payload) | OK — `Frame.RoundtripRelayControlOn/Off` grün |

## Sub-Stage 0.2 — Mech-Umbau + Re-Cal + Femur-Limits ✅ FERTIG (2026-05-30)

Plan: [`phase_13_stage_0_2_remount_recal_plan.md`](phase_13_stage_0_2_remount_recal_plan.md)

- [x] 0.2.1  Mech-Umbau alle 6 Femurs (§6-Trick), Direction pro Bein verifiziert
- [x] 0.2.2  35°-Ruhepose kollisionsfrei (Femurs erreichen ±90° beidseitig)
- [x] 0.2.3  rqt zum Messen genutzt (Range real [500,2500], kein Clamp-Problem)
- [x] 0.2.4  Re-Cal pulse_zero (=horizontal) für 6 Femur-Pins gemessen
- [x] 0.2.5  Re-Cal up/down bei ±90° gemessen → pulse_min/max numerisch zugeordnet
- [x] 0.2.6  servo_mapping.yaml 6 Femur-Einträge aktualisiert + pulse_min<zero<max ok
- [x] 0.2.7  k cross-checked (~415–427 µs/rad vs alt ~420 @±1.57) — konsistent
- [x] 0.2.8  Limits **global symmetrisch** entschieden (User maß beidseitig ±90°)
- [x] 0.2.9  **KORREKTUR:** Femur-Limits werden per **per-Bein-Override** gesetzt (nicht der `femur_lower`-Property!). Stage-F-Overrides standen stale auf ±1.493 → in `hexapod.urdf.xacro` (6×) + `hexapod.ros2_control.xacro` (6×) auf **±1.57** korrigiert. Generierte URDF verifiziert ±1.57. Nötig weil pulse_min/max bei ±90° gemessen → joint_limit MUSS = 90° (sonst Skalenfehler + Freeze bei rad<−1.493)
- [x] 0.2.10 config.py _FEMUR_LIMITS = (-1.57, 1.57) — war schon 1.57, jetzt konsistent mit dem korrigierten Override (vorher IK 1.57 ↔ Plugin 1.493 inkonsistent)
- [x] 0.2.11 colcon build hardware + kinematics grün
- [x] 0.2.12 colcon test grün (351, 0 Failures; Fixture kExpectedPulseZero nachgezogen)
- [x] 0.2.13 Live: rad=0 → horizontal (alle 6, HW + RViz) ✓ 2026-05-30
- [x] 0.2.14 Live: rad=-0.611 → ~35° hoch (alle 6, HW + RViz) ✓ 2026-05-30
- [x] 0.2.15 Live: rad-Sweep ±1.5 über Range → sauber, kein Stall (nach Limit-Fix ±1.57)
- [x] 0.2.16 Live: Power-On via Relay → Servos kommen hoch (Servo-Mitte ~27° hoch); Init-Race (1 Bein bleibt zufällig unten) bekannt → 0.3
- [x] 0.2.17 Self-Review (unten), keine offenen 🔴
  (K3: initial_poses.yaml Femur-Wert aus pulse_us_to_radians(1500) → Stage 0.3)

### Sub-Stage 0.2 — Post-Review (2026-05-30)

| # | Punkt | Status |
|---|---|---|
| R1 | Femur-Cal (6 Pins) in servo_mapping.yaml, `pulse_min<zero<max`, Tests 351/0 | OK |
| R2 | Re-Cal/Weg A live verifiziert: rad=0→horizontal, rad=−0.611→~35°, Sweep ±1.5 ohne Freeze, HW=RViz | OK |
| R3 | **Limit-Override-Miss:** anfangs „±1.57, keine Änderung" behauptet, aber per-Bein-Overrides standen ±1.493 → Sweep-Freeze. Lektion: **echte generierte URDF prüfen, nicht nur die Property** | OK (gefixt: ±1.57, URDF verifiziert) + Lektion |
| R4 | IK↔Plugin-Limit-Konsistenz: vorher config.py 1.57 ↔ Override 1.493 inkonsistent | OK (jetzt beide 1.57) |
| R5 | ±1.57 vs exakt π/2=1.5708 (90°): 0.046° Label-Fehler, ~0.2 µs im Arbeitsbereich | 🟢 vernachlässigbar, dokumentiert |
| R6 | leg_2 down-slope 376 vs Rest ~404–414 (~9% Ausreißer) — Messimpräzision leg_2 down-µs/zero | 🟡 vormerken: falls leg_2 im Walking asymmetrisch auffällt → leg_2 down-µs neu messen |
| R7 | Init-Race „1 Bein bleibt zufällig unten": obsoletes +1.45-Preset + JTC/read-Startup-Race | 🟡 → 0.3 (K3 Init-Pose + relay-gated Sequenz löst es per Design) |
| R8 | FW UV/OC-Trip-Gate (DL-6) — Schutz bei Relay-AN noch intakt? | OK (`if(!relay_on) return` nur bei AUS; bei AN trippt UV/OC normal + droppt Relay) |
| R9 | Femur-Range ±1.493→±1.57 (etwas weiter): invalidiert sim_walk.yaml-Envelope? | 🟢 weiter = permissiver, bestehende Posen ⊂ Range gültig; Envelope-Regen nur falls Walking >±1.493 nutzt |
| R10 | Tibia/Coxa unverändert trotz Femur-Umbau | OK (IK rechnet Kette; tibia relativ zu femur unverändert) |
| R11 | Servo-Mitte real ~27° hoch statt nominal 35° (§6-Trick-Toleranz) | 🟢 sichere erhöhte Pose; exakter Init-Wert kommt via K3 (0.3) |

## Sub-Stage 0.3 — Plugin on_activate Relay-gated Init-Sequenz

Plan: [`phase_13_stage_0_3_init_sequence_plan.md`](phase_13_stage_0_3_init_sequence_plan.md)
+ `_test_commands.md`. Löst Init-Race (0.2-Finding) + K3.

- [ ] 0.3.1  on_activate: init_pulse = 1500 µs (Servo-Mitte) für alle 18 Pins (K3)
- [ ] 0.3.2  on_activate: hw_state_positions_ = rad(1500) → Race-Fix (JTC liest echte Pose)
- [ ] 0.3.3  on_activate: gestaffelte Sequenz RESET→SET_TARGETS→6×Femur-ENABLE→RELAY-ON→Coxa→Tibia→reaffirm
- [ ] 0.3.4  initial_poses.yaml: "suspended" (+1.45) obsolet → power_on_mid / Doku
- [ ] 0.3.5  initial_pose-Default-Param (urdf.xacro) angepasst
- [ ] 0.3.6  Unit-Tests (Sequenz-Order, init=1500, hw_state) + bestehende angepasst
- [ ] 0.3.7  colcon build + test hexapod_hardware grün
- [ ] 0.3.8  Live T2: Init-Sequenz fährt alle 6 sauber hoch, kein Ruck, kein Trip
- [ ] 0.3.9  Live T3: 5× Restart → nie bleibt ein Bein unten (Race weg)
- [ ] 0.3.10 Live T4: Strom beim Staffel-Enable unter Limit
- [ ] 0.3.11 Live T5: on_deactivate Relay-off (Regression)
- [ ] 0.3.12 Self-Review-Tabelle, Fixe erledigt
- **K3-Pendenz (aus 0.2):** Init-Pose-Femur-Wert NICHT hartkodiert −0.611,
  sondern pro Pin aus `pulse_us_to_radians(1500)` (echte Servo-Power-On-Mitte),
  damit `/joint_states` die wahre Startpose meldet und Stand-up (0.4) sauber
  rampt.
- **Init-Pose-Finding (0.2 live):** das alte `initial_poses.yaml`-Preset
  "suspended" (femur=**+1.45** ≈ 90° runter) ist nach dem Umbau obsolet/falsch
  und muss in 0.3 ersetzt werden. Zusätzlich JTC-Startup-Race (read() echot
  pulse_zero bis erster read-Tick) → leg_1 (timing-flaky) folgte beim Init dem
  Down-Target statt der Race-Pose. Beides in der 0.3-Init-Sequenz sauber lösen.

## Sub-Stage 0.4 — Gait Stand-up (Tripod 3+3)

_Plan just-in-time nach 0.3._

## Sub-Stage 0.5 — Sim-Visualisierung

_test_commands just-in-time._

## Sub-Stage 0.6 — HW Live aufgebockt

_test_commands just-in-time._

## Sub-Stage 0.7 — Boden-Test

_test_commands just-in-time._

---

## Design-Entscheidungs-Log

| # | Entscheidung | Alternative (verworfen) | Begründung | Datum |
|---|---|---|---|---|
| DL-1 | **Weg A:** 35°-Offset nur in Kalibrierung; rad=0 bleibt horizontal | Weg B: rad=0=35°hoch via URDF-origin + IK/FK-Offset | A hält IK-Formel nativ passend zur URDF, keine Magic-Konstante in der Mathe-Schicht, kein Re-Test der Kinematik; B kein kinematischer Mehrwert | 2026-05-30 |
| DL-2 | **Reihenfolge:** FW-Relay + Plugin-Service (0.1) vor Mech-Umbau (0.2) | Umbau zuerst via Standalone-Tool | Umbau nutzt manuelle `/hexapod_relay_set`-Steuerung der fertigen Pipeline; entkoppelt nichts unnötig | 2026-05-30 |
| DL-3 | **Relay fail-safe depower** (Boot-LOW + Off bei 3 Trips + RESET + Deactivate) | Relay HIGH halten / nur explizit per Service | Sicherster Default; Host-Tod → FW erkennt autonom (200 ms Watchdog) → stromlos | 2026-05-30 |
| DL-4 | **servo2040_fix behalten** als Fundament | verwerfen | Gated PWM auf disabled Pins ist Voraussetzung für Relay-Ansatz; löst nicht MID-on-Power, aber komplementär | 2026-05-30 |
| DL-5 | **Femur-Limits asymmetrisch**, datengetrieben nach Re-Cal | symmetrisch ±X (Stage-F-Stil) | Mechanik ist nach Umbau real asymmetrisch (mehr Range unten); Symmetrie wäre künstliche Beschränkung | 2026-05-30 |
| DL-6 | **UV/OC-Trips nur scharf wenn `relay_on`** (FW) + Sense-Warmup-Reset beim Relay-On | Trips immer scharf (0.1-Stand) | **0.2-Blocker-Fix:** Relay default-OFF → Rail liest ~0 V (gemessen 129 mV) → FW trippte Undervoltage **sofort nach Boot** → latch-disable aller Servos → Servos kamen trotz späterem Relay-On nie hoch. Relay bricht die „Rail immer bestromt"-Annahme der Schutzlogik. Gehört zur sauberen Relay-Integration (in 0.1 übersehen) | 2026-05-30 |

## Offene Punkte (cross-Sub-Stage, zu klären wenn erreicht)

| # | Frage | Wann |
|---|---|---|
| O-1 | Femur-Limits global-asymmetrisch (alle 6 gleich) oder per-Bein? | nach 0.2 Re-Cal-Messwerten |
| O-2 | Exakter 35°-Wert vs. real erreichter Winkel pro Bein (Mech-Toleranz) | 0.2 Umbau/Re-Cal |
| O-3 | Gleiche Tripod-Sequenz für Bench + Boden, oder zwei Varianten? | 0.6/0.7 Live |
| O-4 | Gazebo-Genauigkeit für Stand-up-Dynamik ausreichend? | 0.5 Sim |
