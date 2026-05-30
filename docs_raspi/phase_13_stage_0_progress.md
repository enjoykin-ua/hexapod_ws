# Phase 13 Stage 0 — Progress-Tracker + Design-Log

> Done-Kriterien-Vertrag für Stage 0 (CLAUDE.md §4). Bullets werden pro
> erledigtem Schritt sofort `[ ]`→`[x]` (Memory `feedback_phase_progress_tracking`).
> Plan-Übersicht: [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md).

**Stand:** 2026-05-30 — Sub-Stage 0.1 ✅ FERTIG. Sub-Stage 0.2 **Plan +
test_commands finalisiert** (K1–K6 eingearbeitet, Decisions geklärt), bereit
für den Umbau nach Commit. Implementierung/Umbau noch nicht begonnen.

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

## Sub-Stage 0.2 — Mech-Umbau + Re-Cal + Femur-Limits

Plan: [`phase_13_stage_0_2_remount_recal_plan.md`](phase_13_stage_0_2_remount_recal_plan.md)

- [ ] 0.2.1  Mech-Umbau alle 6 Femurs (§6-Trick), Direction pro Bein verifiziert
- [ ] 0.2.2  35°-Ruhepose pro Bein kollisionsfrei bestätigt (K2)
- [ ] 0.2.3  rqt-Clamp-Range geweitet (K4) zum Anschlag-Suchen
- [ ] 0.2.4  Re-Cal pulse_zero (=horizontal) für 6 Femur-Pins
- [ ] 0.2.5  Re-Cal up-/down-Anschlag → pulse_min/max direction-aware zugeordnet (K1)
- [ ] 0.2.6  servo_mapping.yaml 6 Femur-Einträge aktualisiert + pulse_min<zero<max ok
- [ ] 0.2.7  k pro Pin (alt) + joint_lower/upper hergeleitet (Magnituden, §1.3) — notiert
- [ ] 0.2.8  Entscheidung global vs per-Bein-Limits (Offene Punkte 4.3)
- [ ] 0.2.9  hexapod_physical_properties.xacro Femur-Limits aktualisiert
- [ ] 0.2.10 config.py _FEMUR_LIMITS identisch zur xacro
- [ ] 0.2.11 colcon build (description/kinematics/hardware) grün
- [ ] 0.2.12 colcon test kinematics + hardware grün (IK-Regression)
- [ ] 0.2.13 Live: rad=0 → horizontal (HW + RViz identisch)
- [ ] 0.2.14 Live: rad=-0.611 → ~35° hoch (HW + RViz identisch, ≈ Servo-Mitte)
- [ ] 0.2.15 Live: rad-Sweep über Limits → kein OoR-Freeze, kein Stall
- [ ] 0.2.16 Live: Power-On via Relay → Femurs ~35° hoch, kein Horizontal-Sprung
- [ ] 0.2.17 Self-Review-Tabelle, Fixe erledigt
  (K3: initial_poses.yaml Femur-Wert aus pulse_us_to_radians(1500) → Stage 0.3)

## Sub-Stage 0.3 — Plugin on_activate Relay-gated Init-Sequenz

_Plan just-in-time nach 0.2. Init-Target → Femur-Enable gestaffelt →
Relay-ON → Coxa → Tibia._
- **K3-Pendenz (aus 0.2):** Init-Pose-Femur-Wert NICHT hartkodiert −0.611,
  sondern pro Pin aus `pulse_us_to_radians(1500)` (echte Servo-Power-On-Mitte),
  damit `/joint_states` die wahre Startpose meldet und Stand-up (0.4) sauber
  rampt.

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

## Offene Punkte (cross-Sub-Stage, zu klären wenn erreicht)

| # | Frage | Wann |
|---|---|---|
| O-1 | Femur-Limits global-asymmetrisch (alle 6 gleich) oder per-Bein? | nach 0.2 Re-Cal-Messwerten |
| O-2 | Exakter 35°-Wert vs. real erreichter Winkel pro Bein (Mech-Toleranz) | 0.2 Umbau/Re-Cal |
| O-3 | Gleiche Tripod-Sequenz für Bench + Boden, oder zwei Varianten? | 0.6/0.7 Live |
| O-4 | Gazebo-Genauigkeit für Stand-up-Dynamik ausreichend? | 0.5 Sim |
