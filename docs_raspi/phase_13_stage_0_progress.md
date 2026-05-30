# Phase 13 Stage 0 — Progress-Tracker + Design-Log

> Done-Kriterien-Vertrag für Stage 0 (CLAUDE.md §4). Bullets werden pro
> erledigtem Schritt sofort `[ ]`→`[x]` (Memory `feedback_phase_progress_tracking`).
> Plan-Übersicht: [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md).

**Stand:** 2026-05-30 — Stage-0-Pläne (Übersicht + 0.1) angelegt, noch
nichts implementiert.

---

## Sub-Stage 0.1 — Relay-Frame + Fail-safe + Plugin-Service

Plan: [`phase_13_stage_0_1_relay_plan.md`](phase_13_stage_0_1_relay_plan.md)

- [ ] 0.1.1  FW: RELAY_CONTROL=0x51 in config.hpp cmd-namespace
- [ ] 0.1.2  FW: RELAY_PIN/relay_on Globals + GP26-Boot-LOW vor servos.init()
- [ ] 0.1.3  FW: set_relay() Helper + handle_relay_control() + dispatch-Case
- [ ] 0.1.4  FW: Fail-safe set_relay(false) in handle_reset + 3 Trip-Blöcke
- [ ] 0.1.5  FW: (optional) RELAY_ON Status-Bit in GET_STATE
- [ ] 0.1.6  FW: Build clean (cmake .. && make -j$(nproc))
- [ ] 0.1.7  FW: tools/test_servo2040.py RELAY_CONTROL-Tests grün
- [ ] 0.1.8  FW: vom User geflasht (picotool load + reboot)
- [ ] 0.1.9  Plugin: encode_relay_control + opcode in servo2040_protocol
- [ ] 0.1.10 Plugin: /hexapod_relay_set Service (SetBool)
- [ ] 0.1.11 Plugin: on_deactivate sendet RELAY_CONTROL(off)
- [ ] 0.1.12 Plugin: colcon build hexapod_hardware grün
- [ ] 0.1.13 Plugin: colcon test hexapod_hardware grün (neue + alte Tests)
- [ ] 0.1.14 Live: Relay klickt on/off via Service ✓
- [ ] 0.1.15 Live: Watchdog-Trip (pkill) droppt Relay ✓
- [ ] 0.1.16 Live: RESET-Frame droppt Relay ✓
- [ ] 0.1.17 Self-Review-Tabelle, Fixe erledigt

## Sub-Stage 0.2 — Mech-Umbau + Re-Cal + Femur-Limits

_Plan just-in-time nach 0.1. Inhalt: §6-Servo-Trick (Weg-A-Variante),
Re-Cal pulse_zero/min/max der 6 Femurs → servo_mapping.yaml, asymmetrische
Femur-Limits → physical_properties.xacro + config.py._

## Sub-Stage 0.3 — Plugin on_activate Relay-gated Init-Sequenz

_Plan just-in-time nach 0.2. Init-Target rad −0.611 → Femur-Enable
gestaffelt → Relay-ON → Coxa → Tibia._

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
