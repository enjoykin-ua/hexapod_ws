# Phase 13 Stage 0.3 — Test-Commands (Relay-gated Init-Sequenz)

> **Plan:** [`phase_13_stage_0_3_init_sequence_plan.md`](phase_13_stage_0_3_init_sequence_plan.md).
> **Form:** User führt aus dem Doc aus, knappe Status-Meldungen
> (Memory [[feedback_test_commands_in_doc_not_chat]], [[feedback_interactive_stage_test_doc]]).
> **Status:** ⚪ Test-Liste vorab; konkrete Befehle nach Implementierung final.

⚠️ Roboter aufgebockt, PSU-Kill-Switch griffbereit. **Neu in 0.3:** das Plugin
schaltet den Relay in `on_activate` **selbst** zu — kein manueller
`/hexapod_relay_set true` mehr nötig zum Hochfahren.

---

## Vorbereitung
```bash
# Terminal 1 (Build)
cd ~/hexapod_ws && colcon build --packages-select hexapod_hardware && source install/setup.bash
```

## T1 — Unit-Tests (CI, ohne HW)
```bash
# Terminal 1
cd ~/hexapod_ws
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --verbose
```
**Erfolg:** alle grün, inkl. `PtyActivateRelayGatedSequenceOrder`,
`InitPulsesAreServoMid`, `ActivateSetsHwStateToInitPose`.

## T2 — Init-Sequenz live (aufgebockt, PSU an)
```bash
# Terminal 1
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
```
**Erwartung (Beobachtung am Roboter):**
1. Femur-Pins enablen gestaffelt (PWM, noch stromlos).
2. **Relay klickt selbst EIN** → Femurs bestromt, stehen auf Servo-Mitte (~35° hoch), **keine** Bewegung.
3. Coxas enablen → stromlos→aktiv, halten radial-neutral.
4. Tibias enablen → halten.
5. **Alle 6 Beine** in sicherer Init-Pose; **KEIN** Bein bleibt unten; **kein** Ruck.

→ Terminal 1 auf `SAFETY FREEZE` / `OVERCURRENT` / `UNDERVOLTAGE` prüfen (darf nicht kommen).

## T3 — Race-Robustheit: 5× Restart
```bash
# Terminal 1: 5× Strg+C + neu starten
ros2 launch hexapod_bringup real.launch.py use_sim_time:=false
```
**Erfolg:** bei **jedem** der 5 Starts kommen **alle 6** Beine sauber hoch —
**nie** bleibt ein Bein unten (Race endgültig weg). Notiere falls doch eins hängt.

## T4 — Strom beim gestaffelten Enable
Während T2: PSU-Stromanzeige beobachten (oder `ros2 topic echo /hexapodsystem/servo_pulses`
zur Pose-Kontrolle).
**Erwartung:** Strom steigt in 3 Stufen (Femur→Coxa→Tibia), bleibt unter dem
FW-Limit (kein Overcurrent-Trip). Falls Trip: Wert notieren → ggf.
`SET_CURRENT_LIMIT` hochsetzen (Plan 4.3) — separat entscheiden.

## T5 — on_deactivate (Regression)
```bash
# Terminal 1: Strg+C im Launch
```
**Erfolg:** Relay klickt AUS beim Shutdown (0.1-Verhalten unverändert).

---

## Findings (User)
| Test | Status | Beobachtung |
|---|---|---|
| T1 Unit | | |
| T2 Init-Sequenz | | |
| T3 5× Restart (kein Bein unten) | | |
| T4 Strom ok | | |
| T5 Deactivate Relay-off | | |
