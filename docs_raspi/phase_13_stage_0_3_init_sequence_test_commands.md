# Phase 13 Stage 0.3 — Test-Commands (Relay-gated Init-Sequenz)

> **Plan:** [`phase_13_stage_0_3_init_sequence_plan.md`](phase_13_stage_0_3_init_sequence_plan.md).
> **Form:** User führt aus dem Doc aus, knappe Status-Meldungen
> (Memory [[feedback_test_commands_in_doc_not_chat]], [[feedback_interactive_stage_test_doc]]).
> **Status:** 🟢 final (2026-05-30). Build-Schritt umfasst **alle 3** in 0.3
> geänderten Pakete (hexapod_hardware + hexapod_bringup + hexapod_description).

⚠️ Roboter aufgebockt, PSU-Kill-Switch griffbereit. **Neu in 0.3:** das Plugin
schaltet den Relay in `on_activate` **selbst** zu — kein manueller
`/hexapod_relay_set true` mehr nötig zum Hochfahren.

---

## Vorbereitung
```bash
# Terminal 1 (Build) — ALLE drei in 0.3 geänderten Pakete neu bauen:
#   hexapod_hardware    → Plugin: relay-gated on_activate + power_on_mid
#   hexapod_bringup     → real.launch.py: initial_pose-Default → power_on_mid
#   hexapod_description → URDF: initial_pose-Default → power_on_mid
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description
source install/setup.bash
```
> ⚠️ Nur `hexapod_hardware` zu bauen reicht NICHT — sonst greift der alte
> Launch-Default (`initial_pose=suspended`) und/oder das alte Launch-/URDF-File.

## T1 — Unit-Tests (CI, ohne HW)
```bash
# Terminal 1
cd ~/hexapod_ws
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --verbose
```
**Erfolg:** alle grün (**352 Tests, 0 Failures, 25 skipped**), inkl.
`PtyActivateRelayGatedSequenceOrder` (Frame-Order: 22 Frames RESET → SET_TARGETS
→ 6× femur-ENABLE → RELAY(on) → 6× coxa → 6× tibia → SET_TARGETS, + 1500-Payload),
`DefaultModeIsPowerOnMid` + `PowerOnMidExplicitNeedsNoYaml` (init=1500 alle Pins
+ hw_state-Race-Fix-Echo), `PtyActivateRespectsStaggerTiming` (~2020 ms),
`SuspendedPresetLoadsAndApplies` (Legacy-rad-Loader unverändert).

> Hinweis: Die im Plan §3.1 skizzierten Test-Namen `InitPulsesAreServoMid` /
> `ActivateSetsHwStateToInitPose` wurden in `DefaultModeIsPowerOnMid` (prüft die
> echo-State = `pulse_us_to_radians(1500)` pro Pin = beides) zusammengeführt; die
> Frame-Payload-1500-Prüfung steckt zusätzlich in `PtyActivateRelayGatedSequenceOrder`.

## T2 — Init-Sequenz live (aufgebockt, PSU an)
```bash
# Terminal 1 — initial_pose explizit (Default ist nach dem Fix ebenfalls
# power_on_mid; explizit = unmissverständlich). real.launch.py erzwingt
# use_sim_time intern bereits auf false → kein use_sim_time-Arg nötig.
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Erwartung (Beobachtung am Roboter):**
1. Femur-Pins enablen gestaffelt (PWM, noch stromlos).
2. **Relay klickt selbst EIN** → Femurs bestromt, stehen auf Servo-Mitte (~35° hoch), **keine** Bewegung.
3. Coxas enablen (Rail jetzt an): greifen aus dem stromlos-limp-Zustand auf ~Mitte. Ein **kleines Nachsetzen** ist ok (Coxa hing kaum), **kein** Ruck.
4. Tibias enablen: Unterschenkel hingen ggf. limp (Rail an, aber PWM noch aus) → greifen auf ihre 1500-Position. **Kleines Nachsetzen** erwartet, kein hartes Springen.
5. **Alle 6 Beine** in sicherer Init-Pose; **KEIN** Bein bleibt unten; **kein** ruckartiges Hochschnappen.

> Erwartungs-Hinweis: Zwischen Relay-On und dem Enable von Coxa/Tibia liegen
> 700 ms (Femur-Settle) — in dieser Zeit hängen Coxa/Tibia stromlos-limp am
> bestromten Femur. Das ist by design; das kleine Nachsetzen beim Enable ist
> kein Fehler. Aufgebockt unkritisch (Beine in der Luft).

→ Terminal 1 auf `SAFETY FREEZE` / `OVERCURRENT` / `UNDERVOLTAGE` / `WATCHDOG` prüfen (darf nicht kommen).

> **Fix-Hinweis (2026-05-30, R16):** Falls der Relay **an- und gleich wieder
> ausgeht** (mitten in der Sequenz): das war der FW-Watchdog (200 ms), weil die
> 700-ms-Settle-Pause keinen Frame sendete. Behoben via Settle-Heartbeat
> (idempotentes SET_TARGETS alle 100 ms). **Voraussetzung:** `hexapod_hardware`
> neu gebaut (`colcon build --packages-select hexapod_hardware && source
> install/setup.bash`). Der Relay muss jetzt über die ganze ~2 s-Sequenz **an
> bleiben**.

## T3 — Race-Robustheit: 5× Restart
```bash
# Terminal 1: 5× Strg+C + neu starten
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid
```
**Erfolg:** bei **jedem** der 5 Starts kommen **alle 6** Beine sauber hoch —
**nie** bleibt ein Bein unten (Race endgültig weg). Notiere falls doch eins hängt.

## T4 — Strom beim gestaffelten Enable
Primär: **PSU-Stromanzeige** während T2 beobachten (das ist das relevante Maß).
Optional Pose-Kontrolle via Diagnostic-Topic — Param `publish_servo_pulses` muss
on sein, Topic-Name vorher prüfen: `ros2 topic list | grep servo_pulses`, dann
`ros2 topic echo <name>`.
**Erwartung:** Strom steigt in 3 Stufen (Femur→Coxa→Tibia), bleibt unter dem
FW-Limit (kein Overcurrent-Trip). Falls Trip: Wert notieren → ggf.
`SET_CURRENT_LIMIT` hochsetzen (Plan 4.3) — separat entscheiden.

## T5 — on_deactivate (Regression)
```bash
# Terminal 1: Strg+C im Launch
```
**Erfolg:** Relay wird beim Shutdown stromlos. Beobachtet 2026-05-30: bei
**Strg+C** kein hörbarer expliziter Relay-Klick — SIGINT terminiert den
ros2_control_node, der saubere `on_deactivate` (mit explizitem RELAY_CONTROL(off))
läuft dabei meist nicht durch. Die Rail wird stattdessen ~200 ms später über den
**FW-Watchdog-Fail-safe** ([main.cpp:400](../../hexapod_servo_driver/src/main.cpp#L400),
`set_relay(false)`) de-powered. **Safety-Ziel erfüllt** (Rail aus, Servos limp).

### T5b (optional) — expliziten on_deactivate-Relay-off-Pfad nachweisen
> Schließt den 🟡-Punkt: Controller sauber deaktivieren (statt SIGINT), dann
> klickt der explizite RELAY_CONTROL(off)-Frame.
```bash
# Terminal 2 (Launch in Terminal 1 läuft):
ros2 control set_hardware_component_state HexapodSystem inactive
# → erwartet: hörbarer Relay-Klick AUS + im Terminal-1-Log:
#   "on_deactivate: relay OFF frame sent"
# danach wieder hochfahren:
ros2 control set_hardware_component_state HexapodSystem active
```
**Erfolg T5b:** Relay klickt hörbar AUS beim inactive-Übergang; Log-Zeile
`on_deactivate: relay OFF frame sent` erscheint (0.1-Verhalten unverändert).

---

## Diagnose D-T2 — „Relay schaltet beim Launch nicht, keine Errors"

> Ziel: eindeutig feststellen, **welcher** `on_activate` läuft (oder ob er läuft).
> Zwei Fixe sind schon eingebaut: (1) Launch-Default `initial_pose` war fälschlich
> `suspended` → jetzt `power_on_mid`; (2) deshalb unbedingt **neu bauen + sourcen**.

### D-T2.1 — Sauber neu bauen (Plugin + Launch + URDF) und sourcen
```bash
# Terminal 1
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware hexapod_bringup hexapod_description
source install/setup.bash
```

### D-T2.2 — Launch mit Log-Mitschnitt, initial_pose explizit
```bash
# Terminal 1 — Launch laufen lassen, Ausgabe zusätzlich in Datei
ros2 launch hexapod_bringup real.launch.py initial_pose:=power_on_mid 2>&1 | tee /tmp/t2_launch.log
```

### D-T2.3 — In Terminal 2: welcher Code lief? (entscheidende Beweiszeile)
```bash
# Terminal 2 (vorher: source ~/hexapod_ws/install/setup.bash)
echo "===== on_init / on_configure / on_activate ====="
grep -nE "on_init complete|on_configure complete|on_activate starting|on_activate complete|power_on_mid|relay default OFF|relay closed|neutral pose commanded|Failed to open serial|FATAL|reader thread died" /tmp/t2_launch.log
echo "===== Hardware-Component-State (active = on_activate lief) ====="
ros2 control list_hardware_components
echo "===== Controller-State ====="
ros2 control list_controllers
echo "===== Relay-Service da? ====="
ros2 service list | grep -i relay
```

**Wie ich es lese (bitte Output von D-T2.3 posten):**

| Beobachtung im Log | Bedeutung |
|---|---|
| `on_activate complete — relay closed, 18 servos enabled (femur->coxa->tibia staggered)` | **Neuer Code lief, Relay-Frame WURDE gesendet** → Problem liegt FW-/HW-seitig (Frame kam nicht an / Relay nicht physisch geschaltet) |
| `on_activate complete — … 18 servos enabled, neutral pose commanded` | **Alter Code** läuft noch → Plugin nicht neu gebaut/gesourct (D-T2.1 nötig) |
| `on_activate starting` da, aber **kein** `complete` + ein `FATAL`/`reader thread died` dazwischen | on_activate **bricht vor dem Relay-On ab** (USB/Serial-Problem) |
| **gar kein** `on_activate` | Hardware wird nicht aktiviert → list_hardware_components zeigt `unconfigured`/`inactive` |
| `Failed to open serial port` | Servo2040 nicht erreichbar (Device-Pfad/`dialout`/Port belegt) |

> Manueller Gegencheck (falls nützlich): `ros2 service call /hexapod_relay_set std_srvs/srv/SetBool "{data: true}"` — klickt der Relay damit (wie in 0.2)? Wenn ja, ist die FW/HW ok und es liegt allein an on_activate.

---

## Findings (User)
| Test | Status | Beobachtung |
|---|---|---|
| D-T2 Diagnose (welcher on_activate?) | ✅ | Wurzel: FW-Watchdog-Trip in 700-ms-Settle (R16) → Heartbeat-Fix |
| T1 Unit | ✅ | 352/0/25 skip |
| T2 Init-Sequenz | ✅ | Relay bleibt an, Sequenz läuft sauber durch (2026-05-30) |
| T3 5× Restart (kein Bein unten) | ✅ | kein Bein bleibt unten (Race weg) |
| T4 Strom ok | ✅ | kein Overcurrent-Trip beim gestaffelten Enable |
| T5 Deactivate Relay-off | ✅ (via Watchdog) / 🟡 | Strg+C: kein hörbarer expliziter Relay-Klick. Ursache: SIGINT fährt den sauberen `on_deactivate` meist nicht durch → Rail wird via **FW-Watchdog (200 ms Fail-safe)** stromlos. Safety-Ziel (Rail aus, Servos limp) erfüllt; expliziter Frame-Pfad 🟡 separat via Controller-Deactivate prüfen |
