# Phase 13 Stage 0 — Progress-Tracker + Design-Log

> Done-Kriterien-Vertrag für Stage 0 (CLAUDE.md §4). Bullets werden pro
> erledigtem Schritt sofort `[ ]`→`[x]` (Memory `feedback_phase_progress_tracking`).
> Plan-Übersicht: [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md).

**Stand:** 2026-05-30 — 0.1 ✅ + 0.2 ✅ + **Sub-Stage 0.3 ✅ FERTIG**:
`power_on_mid`-Init (1500 µs alle 18 Pins, zero-jerk), relay-gated gestaffelte
on_activate-Sequenz (RESET→SET_TARGETS→6×femur→RELAY→coxa→tibia→reaffirm) mit
Settle-Heartbeat gegen FW-Watchdog (R16). Tests **352/0/25-skip**, uncrustify
clean. Live T2–T5 aufgebockt verifiziert (Relay hält, Race weg, kein Trip,
Shutdown stromlos). Code- + Final-Review ohne 🔴 (zwei 🟡-Merker: T5b-Live +
0.7-Boden-limp). **Bereit für Commit (User).**

**+ Sub-Stage 0.4 ✅ FERTIG (2026-05-30):** Gait Stand-up = **all-6 simultan**
ab power_on_mid (STARTUP_RAMP existierte → Validierung, DL-7 Tripod-3+3→all-6).
**+ Korrektur (bei 0.5-Vorbereitung entdeckt):** Stand-Pose-Limit-Bug behoben —
alte Pose (radial 0.27/bh −0.052) verletzte das Tibia-Limit (1.33>1.161 rad,
HW-Freeze, in lenienter Sim nie sichtbar) → **radial 0.295 / bh −0.080**; plus
falsche Limit-Quelle im Test korrigiert (echte URDF-Limits statt config.py).
**colcon test hexapod_gait 357/0/25**, Regression-Test ergänzt, README + Plan
(§3 + Höhentabelle) aktualisiert, Self-Review ohne offene 🔴. Nächste: 0.5.

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

- [x] 0.3.1  on_activate: init_pulse = 1500 µs (Servo-Mitte) für alle 18 Pins (K3) — `power_on_mid`-Modus in `load_initial_pose_preset()`, Konstante `SERVO_POWER_ON_MID_US`
- [x] 0.3.2  on_activate: hw_state_positions_ = rad(1500) → Race-Fix — bestehender Sync-Block rechnet aus `initial_pulse_us_`; Test `DefaultModeIsPowerOnMid` prüft echo-State
- [x] 0.3.3  on_activate: gestaffelte Sequenz RESET→SET_TARGETS→6×Femur-ENABLE→RELAY-ON→settle→Coxa→settle→Tibia→reaffirm (`enable_group`-Lambda, Pin-Gruppen aus on_init)
- [x] 0.3.4  initial_poses.yaml: "suspended" (+1.45) als Legacy markiert; `power_on_mid` als built-in Default dokumentiert
- [x] 0.3.5  initial_pose-Default-Param `power_on_mid` (urdf.xacro + ros2_control.xacro Kommentar)
- [x] 0.3.6  Unit-Tests: `PtyActivateRelayGatedSequenceOrder` (22 Frames/Order/1500), `DefaultModeIsPowerOnMid`, `PowerOnMidExplicitNeedsNoYaml`, Timing-Band ~2020 ms; bestehende angepasst (write-Tests unberührt — rufen on_activate nicht)
- [x] 0.3.7  colcon build (exit 0) + test hexapod_hardware grün (**352/0/25 skip**) + uncrustify clean
- [x] 0.3.8  Live T2: Init-Sequenz fährt alle 6 sauber hoch, Relay bleibt an, kein Ruck, kein Trip (2026-05-30, nach R16-Heartbeat-Fix)
- [x] 0.3.9  Live T3: 5× Restart → nie bleibt ein Bein unten (Race weg)
- [x] 0.3.10 Live T4: Strom beim Staffel-Enable unter Limit (kein Overcurrent-Trip)
- [x] 0.3.11 Live T5: Shutdown depowert die Rail ✅ — bei Strg+C via FW-Watchdog-Fail-safe (kein expliziter Relay-Klick, da SIGINT on_deactivate nicht sauber durchfährt). Safety-Ziel erfüllt; expliziter Frame-Pfad 🟡 (T5b separat, kein Blocker)
- [x] 0.3.12 Self-Review-Tabelle (Code ✅ vor Live + Final-Review unten nach T2–T5), Fixe erledigt
- **K3-Pendenz (aus 0.2):** Init-Pose-Femur-Wert NICHT hartkodiert −0.611,
  sondern pro Pin aus `pulse_us_to_radians(1500)` (echte Servo-Power-On-Mitte),
  damit `/joint_states` die wahre Startpose meldet und Stand-up (0.4) sauber
  rampt.
- **Init-Pose-Finding (0.2 live):** das alte `initial_poses.yaml`-Preset
  "suspended" (femur=**+1.45** ≈ 90° runter) ist nach dem Umbau obsolet/falsch
  und muss in 0.3 ersetzt werden. Zusätzlich JTC-Startup-Race (read() echot
  pulse_zero bis erster read-Tick) → leg_1 (timing-flaky) folgte beim Init dem
  Down-Target statt der Race-Pose. Beides in der 0.3-Init-Sequenz sauber lösen.

### Sub-Stage 0.3 — Post-Review (Code, vor Live-Tests) (2026-05-30)

> Code-Level-Self-Review nach Implementierung + grünen Unit-Tests, **vor** den
> Live-Tests T2–T5 (de-riskt die HW-Session). Final-Review (mit Live-Findings)
> schließt 0.3.12 nach T2–T5.

| # | Punkt | Status |
|---|---|---|
| R1 | Init=1500 ∈ [pulse_min,pulse_max] **aller 18 Pins** (jeden durchgerechnet) → kein Stage-0.5-`safety_freeze` beim Init-Send; Roundtrip `rad→pulse` exakt (gleiche Slope-Branch beidseitig) → JTC hält konsistent | OK (`DefaultModeIsPowerOnMid` prüft echo-State = rad(1500)) |
| R2 | Frame-Sequenz byteweise: 22 Frames RESET→SET_TARGETS(1500)→6×femur-ENABLE→**RELAY(on)**→6×coxa→6×tibia→SET_TARGETS; SEQ 0..21 monoton | OK (`PtyActivateRelayGatedSequenceOrder`) |
| R3 | Pin-Gruppen partitionieren 0..17 (FATAL-Check sum≠18); per Joint-Name klassifiziert + sortiert → deterministische Wire-Order auch bei permutierter URDF | OK (`AcceptsPermutedJointOrder` weiter grün) |
| R4 | Femur-Settle 700 ms ≥ FW-Sense-Warmup 400 ms (re-armed bei Relay-On) → Überstrom-Trip scharf + IIR gesettled bevor Coxa-Gruppe zieht | OK (bewusst aligned, Plan §4.2/4.3) |
| R5 | Coxa/Tibia **limp-Fenster** (V+ an, PWM aus) zwischen Relay-On und ihrem Enable → kleines Nachsetzen beim Enable | 🟡 vormerken **0.7 (Boden)**: dort relevanter (Beine gesplayed) — ggf. Sequenz/Reihenfolge anpassen. Aufgebockt unkritisch; in test_commands T2 dokumentiert |
| R6 | Abort nach Relay-On (USB weg, send_frame=false) → **kein** explizites Relay-Off (Wire ist tot, Frame ginge eh nicht); FW-Watchdog (200 ms) droppt Relay autonom | OK (designter Backstop; `ActivateFailsCleanlyIfPortIsBroken` grün) |
| R7 | write-Tests unberührt — sie rufen on_activate **nicht** + setzen hw_command explizit → `kExpectedPulseZero`-Erwartung bei rad=0 bleibt korrekt | OK (geprüft, alle WriteRead-Tests grün) |
| R8 | Loopback: alle Delays (stagger+settle) = 0 → `LoopbackActivateAndDeactivateAreFast` < 100 ms; seq +22 | OK |
| R9 | 0.1-Review-R6 (relay-on bei latched Trip) durch **RESET vor Relay-On** im Design abgedeckt — RESET cleart Trips + droppt Relay (FW), dann erst relay-on | OK |
| R10 | `safety_freeze_` wird von on_activate nicht gecleart (pre-existing) — bei Fresh-Launch `false`, für Live irrelevant; in-process Re-Activate nach Freeze hielte Init-Pose | 🟢 pre-existing, out-of-scope (Recovery = /hexapod_safety_reset oder Re-Launch) |
| R11 | Legacy "suspended" femur=1.45 mit **neuer** Femur-Cal weiter in-range (alle 6 Pins gerechnet, ~45–50 µs Margin rechts) → kein OoR-Fallback | OK (`SuspendedPresetLoadsAndApplies` grün) |
| R12 | PTY-Activate-Tests jetzt ~3 s (Settles real in non-loopback), Suite +~13 s | 🟢 akzeptabel für HW-Paket |
| R13 | Servo-MID-on-Power-On bleibt physikalisch unvermeidbar — power_on_mid macht genau das zum Feature (zero-jerk), löst Init-Race per Design statt per Timing | OK (Kern-Designentscheidung) |

**Ergebnis Code-Review:** keine 🔴. Ein 🟡 (R5) ist ein bewusster Merker für die
Boden-Stage 0.7, kein Blocker für die aufgebockten Tests T2–T5. Bereit für Live.

**Live-Debug-Findings (T2, 2026-05-30):**
- **R14 🔴→gefixt:** `real.launch.py` deklarierte `initial_pose` mit Default
  **`suspended`** und reichte ihn an xacro durch → überschrieb den neuen
  URDF-Default `power_on_mid`. Plugin lief also mit dem Legacy-Preset (Beine
  runter) statt 1500. Fix: Launch-Default → `power_on_mid`. **Lektion:** beim
  Ändern eines xacro-Default-Args **immer** die Launch-Arg-Defaults mitziehen,
  die ihn shadowen.
- **R15 🔴→gefixt:** `*_test_commands.md` **Vorbereitung** baute nur
  `hexapod_hardware` — aber 0.3 änderte auch `hexapod_bringup` (Launch) +
  `hexapod_description` (URDF). Wer nur das Plugin baut, fährt mit altem
  Launch/URDF. Fix: Build-Schritt + Diagnose-D-T2 bauen alle 3 Pakete; T2/T3
  setzen `initial_pose:=power_on_mid` explizit; redundantes `use_sim_time:=false`
  (von real.launch.py nicht deklariert) entfernt. (User-Catch, danke.)
- **R16 🔴→gefixt (Watchdog-Trip in der Settle-Lücke):** Live T2 zeigte „Relay
  klickt an, ~200 ms später wieder aus, mitten in der Sequenz". Wurzel: der
  FW-Watchdog ([main.cpp:385-403](../../hexapod_servo_driver/src/main.cpp#L385-L403),
  `WATCHDOG_TIMEOUT_MS=200`) disabled alle Servos **+ `set_relay(false)`**, wenn
  >200 ms kein gültiger Frame kommt. Meine 700-ms-`femur_settle` (und 400-ms-
  `coxa_settle`) waren **nackte `sleep_for`** ohne Frame → on_activate blockt die
  write()-Loop → Watchdog trippt nach 200 ms. Mein Code-Review **R4** wog Settle
  gegen das 400-ms-Sense-Warmup-Gate ab, **übersah aber das 200-ms-Watchdog-
  Timeout** (der alte 50-ms-Stagger hatte den Watchdog implizit warm gehalten).
  **Fix (host-only, kein FW-Change):** `settle_with_heartbeat()` schläft in
  100-ms-Slices und sendet zwischen den Slices ein **idempotentes
  `SET_TARGETS(1500)`** (Target unverändert → keine Bewegung, füttert aber den
  Watchdog). 100 ms ≪ 200 ms = 2× Margin. **Lektion:** jede Frame-Stille
  >200 ms in on_activate = Watchdog-Trip; Heartbeat ist Pflicht.
- **Test-Anpassung:** `PtyActivateRelayGatedSequenceOrder` von starrer
  22-Frame-Assertion auf **Cursor-Walk** umgestellt, der die Heartbeat-
  SET_TARGETS(1500) zwischen den Gruppen toleriert (`skip_heartbeats()`);
  Struktur-Frame-Order + SEQ-Monotonie weiter streng geprüft. Loopback bleibt
  22 Frames (settle=0). Tests **352/0/25**, uncrustify clean.
- **Offen:** Live-Re-Test T2 nach Rebuild — Relay muss jetzt **an bleiben** über
  die ganze Sequenz (Heartbeat verhindert den Watchdog-Trip).

### Sub-Stage 0.3 — Final-Review (nach Live T2–T5) (2026-05-30)

> Abschluss-Review mit Live-Findings (CLAUDE.md §4). Ergänzt den Code-Review oben.

| # | Punkt | Status |
|---|---|---|
| F1 | **R16-Fix live validiert:** on_activate 327.761→329.785 = **2,024 s**, Relay bleibt durchgehend an, kein Watchdog-Trip. Heartbeats ändern die Gesamtdauer nicht (laufen in den Sleeps) | OK |
| F2 | **Beweis neuer Code:** Log `on_activate complete — relay closed, … (seq counter advanced by 22)` + `initial_pose=power_on_mid` + `all 18 pins … 1500 µs` | OK |
| F3 | **T2 Init-Pose:** alle 6 Beine kommen sauber hoch, kein Bein bleibt unten, kein Ruck (Race per Design weg) | OK |
| F4 | **T3 5× Restart:** jedes Mal identisch, nie hängt ein Bein → Init-Race endgültig gelöst | OK |
| F5 | **T4 Strom:** gestaffeltes Enable, kein Overcurrent-/Undervoltage-Trip | OK |
| F6 | **T5 Shutdown-Safety:** Rail wird stromlos. Bei Strg+C über **FW-Watchdog-Fail-safe** (200 ms), nicht über den expliziten on_deactivate-Frame (SIGINT killt den Node bevor on_deactivate sauber läuft). Servos limp = sicher | OK (Safety-Ziel) |
| F7 | **Expliziter on_deactivate-Relay-off-Pfad** (RELAY_CONTROL(off) vor Disable) nur unit-getestet (`PtyDeactivateSendsDisableForAllServos`), live mit Strg+C nicht nachgewiesen | 🟡 vormerken: **T5b** (`set_hardware_component_state … inactive`) live nachziehen, wenn 0.6 sowieso am HW läuft. Kein Blocker — Watchdog ist redundanter Backstop (DL-3) |
| F8 | **R5 (limp-Fenster Coxa/Tibia 700 ms):** aufgebockt beobachtet — nur „kleines Nachsetzen" beim Enable, kein hartes Springen, wie erwartet | OK aufgebockt; bleibt 🟡-Merker für **0.7 Boden** |
| F9 | Tests nach R16-Fix weiter grün (352/0/25), uncrustify clean, Sequenz-Test heartbeat-tolerant (cursor-walk) | OK |

**Ergebnis Final-Review:** keine 🔴. Zwei 🟡 (F7 T5b-Live-Nachweis, F8/R5
Boden-limp) sind bewusste Merker für spätere Stages, kein Blocker für 0.3.
**Sub-Stage 0.3 fertig.** Geänderte Dateien bereit für User-Commit.

---

## Sub-Stage 0.4 — Gait Stand-up (all-6 simultan, ab power_on_mid) ✅ FERTIG (2026-05-30)

Plan: [`phase_13_stage_0_4_standup_plan.md`](phase_13_stage_0_4_standup_plan.md).
Pure-Python (STARTUP_RAMP-Mechanik existierte; 0.4 = Fixture-Realität +
Beweis-Tests + Doku + Vertrags-Korrektur + **Stand-Pose-Limit-Bug-Fix**).

- [x] 0.4.1  Design all-6 (nicht 3+3) im Stage-0-Plan §3/§6/§7 + DL-7 korrigiert
- [x] 0.4.2  test_startup_ramp.py: suspended-Fixture → **power_on_mid-Fixture mit ECHTEN URDF-Limits** (coxa ±0.415/tibia ±1.161, NICHT config.py ±1.57/±1.50; Slope-Formel limit-abhängig)
- [x] 0.4.3  Test `power_on_mid_start_ramp_in_limits` (21 Samples × 18 Joints ∈ echte URDF-Limits)
- [x] 0.4.4  Test `power_on_mid_ramp_endpoint_is_stand_pose`
- [x] 0.4.5  Test `power_on_mid_ramp_all_six_simultaneous` (gleicher smooth-step-Faktor alle 6 Beine)
- [x] 0.4.6  Test `power_on_mid_ramp_monotonic` + **`test_stand_pose_in_limits_for_all_legs`** (Regression: faengt Stand-Pose-Limit-Verletzung)
- [x] 0.4.7  **Stand-Pose-Limit-Bug behoben** (kein Engine-Rewrite, aber Default-Fix): radial 0.27→0.295, body_height −0.052→−0.080 in gait_node.py + gait.launch.py + stand_node.py + stand.launch.py; body_height_min −0.080→−0.115
- [x] 0.4.8  colcon test hexapod_gait grün (**357/0/25 skip**, inkl. flake8/pep257/copyright + neue Tests)
- [x] 0.4.9  gait README: STARTUP_RAMP-State + Stand-up-Abschnitt (all-6, in-limits, neue Stand-Pose + Bug-Hinweis, suspended obsolet)
- [x] 0.4.10 Self-Review (unten), keine offenen 🔴

### Sub-Stage 0.4 — Post-Review (2026-05-30)

| # | Punkt | Status |
|---|---|---|
| R1 | Stand-up-Mechanik existierte bereits (STARTUP_RAMP, all-6, joint-space smooth-step) — 0.4 ist Validierung + Test-Realität, kein Neubau | OK |
| R2 | power_on_mid-rad-Fixture aus servo_mapping.yaml via pulse_us_to_radians(1500) abgeleitet (Plan §3), hartkodiert im gait-Test um hexapod_hardware-Import zu vermeiden | OK — bei neuer Femur-Cal Fixture nachziehen (🟢 im Test-Kommentar dokumentiert) |
| R3 | In-Limits über ganzen Ramp empirisch belegt (21 Samples), nicht nur Endpunkte — fängt künftige Monotonie-Brüche | OK |
| R4 | all-6-simultan per Test belegt (gleicher smooth-step-Faktor) → Abgrenzung zu 3+3 maschinell gesichert | OK |
| R5 | Startpunkt = real gemessene `/joint_states`-Pose (nicht hartkodiert); Fixture spiegelt das nur für den Test | OK |
| R6 | Lerp joint-space-start-agnostisch: kleine HW-Cal-Toleranz ggü. Fixture bleibt korrekt/in-limits | OK |
| R7 | **🔴→behoben: Stand-Pose-Limit-Bug.** Alte Pose (radial 0.27/bh −0.052) verlangte tibia **1.33 rad > URDF-Limit 1.161** → auf HW Stage-0.5-Freeze rechte Beine (PWM 751<cal-min 870). In lenienter Phase-5-Sim nie sichtbar; bei Stage-F-Limit-Verengung (2026-05-25) Stand-Pose nicht mitgezogen. **Fix:** radial→0.295, bh→−0.080 (tibia 0.758, in-limit), alle 4 Default-Stellen + min/max. Regression-Test `test_stand_pose_in_limits_for_all_legs` | OK (gefixt + Test) |
| R8 | **Zweiter Fehler in 0.4-Erstfassung: falsche Limit-Quelle.** power_on_mid-Fixture + In-Limits-Test nutzten config.py-Limits (±1.57/±1.50) statt echter URDF-Limits (coxa ±0.415/tibia ±1.161). Slope-Formel ist limit-abhängig → coxa/tibia falsch skaliert. **Fix:** `_URDF_LIMITS` + Fixture neu berechnet | OK (gefixt) |
| R9 | Stand-Höhen-Tabelle (Plan §3.3): 7 gültige (body_height, radial)-Paare, per Param live anfahrbar (0.6) | OK |
| R10 | Konsumenten-Check: 7 Walking-Presets (`config/presets/`) nutzen bereits radial=0.30/bh −0.055..−0.06 → in-limit, vom Default-Wechsel unberührt | OK (verifiziert) |
| R11 | `auto_standup_duration` 4.0 s: größte Bewegung Tibia ~57–64° → ~0.25–0.28 rad/s ≪ 2.0 rad/s URDF-Cap | OK (konservativ) |
| R12 | gait.launch.py `use_sim_time`-Default (Memory `project_phase13_gait_launch_sim_time_default`) blockt rclpy-Timer auf HW ohne /clock | 🟡 → ab 0.6 HW (Workaround `use_sim_time:=false`), nicht 0.4 |

**Ergebnis:** keine 🔴. Zwei 🟡 (R7 Stand-Pose-Feintuning, R9 use_sim_time) sind
Live-Themen für 0.6, kein Blocker für die Pure-Python-Logik-Stage 0.4.
**Sub-Stage 0.4 fertig.** Bereit für User-Commit. Nächste: 0.5 (Sim-Visualisierung).

## Sub-Stage 0.5 — Sim-Visualisierung (Init→Aufstehen) ✅ FERTIG (2026-05-31)

Plan: [`phase_13_stage_0_5_sim_standup_plan.md`](phase_13_stage_0_5_sim_standup_plan.md) ·
Test: [`phase_13_stage_0_5_sim_standup_test_commands.md`](phase_13_stage_0_5_sim_standup_test_commands.md)

**§7-Klärung (User 2026-05-31):** 7.6 → **nur Gazebo** (RViz-tf-Check → 0.6).
Restliche §7 wie im Plan: 7.1✅ exakte HW-Cal-Werte · 7.2✅ spawn_z live · 7.3✅
Stand-Pose −0.080/0.295 · 7.7✅ HW-Pfad kompatibel · 7.4/7.5 Live-Punkte.

**Code-Änderungen (2026-05-31):** `initial_value` (18 power_on_mid-rad) **sim-only**
ins `joint_iface`-Macro (`<xacro:if use_sim>`) + 18 Calls; `spawn_z` 0.20→0.05.
Werte 1:1 aus `test_startup_ramp.py::_POWER_ON_MID` (= Plan-0.4 §3.1). Kein
Gait-/Plugin-Change.

- [x] 0.5.1  initial_value (18 power_on_mid-rad) sim-only in ros2_control.xacro
- [x] 0.5.2  xacro use_sim:=true → 18× initial_value da; use_sim:=false → 0× (HW-Pfad nackte position-state_interface, nur HexapodSystemHardware-Plugin)
- [x] 0.5.3  spawn_z angepasst (0.20→0.05, Bauch ~am Boden nach Drop; live iterierbar §7.2)
- [x] 0.5.4  colcon build hexapod_description + hexapod_bringup grün
- [x] 0.5.5  Live T1 ✅: Sim startet in power_on_mid — /joint_states **exakt** = power_on_mid (femur −0.468/−0.636/−0.438/−0.476/−0.418/−0.495, NICHT ≈0). **R4 aufgelöst: gz_ros2_control wendet `initial_value` an.** Bauch liegt auf, Femurs schräg hoch, ruhig
- [x] 0.5.6  Live T2 ✅: all-6 Stand-up, Körper hebt gleichmäßig, **stabil, Körper horizontal**, kein Kippen/Durchsacken, kein IKError. 🟡 **Befund: Füße schürfen ~15-22mm horizontal nach innen** beim Hochdrücken (s. Final-Review F-Scrape)
- [x] 0.5.7  Live T3 ✅: Endpose stabil — /joint_states = coxa ≈0 / femur −0.2404 / tibia +0.7584 alle 6, kein Drift
- [x] 0.5.8  ~~Live T4: RViz~~ — **N/A in 0.5 (§7.6 nur Gazebo)** → RViz-tf-Check in 0.6
- [x] 0.5.9  Final-Review (unten), keine offenen 🔴

### Sub-Stage 0.5 — Code-Review (vor Live-Tests) (2026-05-31)

> Code-Level-Self-Review nach Implementierung + grünen Parse-/Build-Checks,
> **vor** den Live-Tests T1–T3 (de-riskt die Sim-Session). Final-Review (mit
> Live-Findings) schließt 0.5.9 nach T1–T3.

| # | Punkt | Status |
|---|---|---|
| R1 | **HW-Pfad unberührt:** `initial_value` + velocity-state_interface liegen im `<xacro:if use_sim>`; im `<xacro:unless>` bleibt `<state_interface name="position"/>` nackt. Parse-Check use_sim:=false: 0× initial_value, 0× velocity, 18× nackte position, nur HexapodSystemHardware-Plugin (GazeboSimSystem nur in 2 Kommentarzeilen) | OK (verifiziert) |
| R2 | **18 Werte = Single Source:** exakt `_POWER_ON_MID` aus test_startup_ramp.py kopiert (kein Abtippen aus Prosa); Reihenfolge im generierten URDF stimmt (leg_1 c/f/t … leg_6 c/f/t) | OK |
| R3 | **Alle 18 ∈ URDF-Limits:** coxa −0.111…+0.156 ∈ ±0.415; femur −0.419…−0.637 ∈ ±1.57; tibia +0.156…+0.258 ∈ ±1.161 → kein Spawn-Clamp, kein Stage-0.5-`safety_freeze`-Äquivalent | OK |
| R4 | **gz_ros2_control liest `initial_value`?** Binär-Paket, Source nicht einsehbar → versionsabhängig. Mechanismus (param am position-state_interface) ist Standard-Jazzy | 🟡 Live-Verify **T1** + Fallback §7.5 dokumentiert (kein Blocker, kein Sys-Eingriff) |
| R5 | **Macro-Default `initial:=0.0`:** falls ein Call den Param vergisst → 0.0 (T-Pose-Joint), kein Parse-Fehler. Alle 18 Calls setzen ihn explizit | OK (defensiv) |
| R6 | **base_link ohne explizite Reibung** (nur Füße μ=1.0) → Bauch könnte beim Abheben kleben | 🟡 Live-Beobachtung **T2** (§7.4); Fix B (μ≈0.2 gazebo-only) nur falls nötig |
| R7 | **Stand-Pose in-limit:** Ziel radial 0.295/bh −0.080 (tibia 0.758 ≪ 1.161) — der in 0.4 gefixte Wert, nicht der alte buggy 0.27/−0.052 | OK (0.4-Fix aktiv) |
| R8 | **Sim-Limit-Check aktiv:** test_commands T2 setzt `robot_description_file:=$HEX_URDF` → gait_engine nicht-lenient, maskiert keine Limit-Verletzung (Memory `project_two_joint_limit_sources`) | OK (im Test-Doc verankert) |
| R9 | **use_sim_time-Falle:** test_commands T2 setzt `use_sim_time:=true` explizit (Memory `project_phase13_gait_launch_sim_time_default`) | OK (im Test-Doc verankert) |
| R10 | **Build-Vollständigkeit (0.3-R15-Lektion):** 0.5 ändert description+bringup; Test-Doc baut beide, nicht nur eins | OK (im Test-Doc verankert) |

**Ergebnis Code-Review:** keine 🔴. Zwei 🟡 (R4 gz-initial_value-Live-Verify,
R6 Bauch-Reibung) sind dokumentierte Live-Punkte mit Fallback, kein Blocker.
**Bereit für Live T1–T3 (User).**

### Sub-Stage 0.5 — Final-Review (nach Live T1–T3) (2026-05-31)

| # | Punkt | Status |
|---|---|---|
| F1 | **T1 — R4 aufgelöst:** /joint_states beim Spawn = power_on_mid bis auf <1e-3 (femur −0.468…−0.636, tibia +0.156…+0.258). gz_ros2_control wendet `initial_value` in dieser Jazzy/Harmonic-Version an → §7.5-Fallback **nicht** nötig | OK |
| F2 | **T2 — Stand-up funktioniert:** all-6 simultan, Körper hebt gleichmäßig, steht stabil, **Körper horizontal ausgerichtet**, kein Kippen/Durchsacken/Wegrutschen-zur-Seite, kein IKError | OK |
| F3 | **T3 — Endpose exakt + stabil:** alle 6 Beine coxa ≈0 / femur −0.2404 / tibia +0.7584 (= IK-Stand-Pose radial 0.295 / bh −0.080), velocity ~1e-10, kein Drift | OK |
| F4 | **R6 (Bauch-Reibung):** Bauch hob sauber ab, kein „Kleben"/Rucken → §7.4-Fix-B (μ≈0.2) nicht nötig | OK |
| F-Scrape | 🟡 **Füße schürfen horizontal nach innen** beim Hochdrücken. Code-Math (leg_fk über den Ramp): rx 0.310→0.295 mit Bulge 0.317 @p≈0.4, dann −15…−22mm nach innen in der **belasteten** zweiten Hälfte (rz +0.078→−0.080). **Wurzel = joint-space-Ramp** (Winkel-Lerp hält Fuß-x nicht konstant), **NICHT** Tibia-Länge — Tibia (0.2m) verstärkt nur den Hebel. User-Hypothese „Tibia kürzen" per Math falsifiziert | 🟡 → **0.6 (aufgebockt: kein Bodenkontakt, nur Bewegung) + 0.7 (Boden: echtes Schürfen messen)**. Fix falls nötig = cartesian/zwei-Phasen-Aufstehen, **NICHT** Tibia kürzen (§7.7 Geometrie-TABU bricht IK/FK/Cal). Memory `project_phase13_standup_foot_scrape` |
| F5 | **spawn_z=0.05:** Bauch kam nahe Boden zur Ruhe; User sah Spawn-Höhe nicht (Drop zu kurz) — unkritisch (§7.2 live), Ruhelage passt | OK |

**Ergebnis Final-Review:** keine 🔴. Ein 🟡 (F-Scrape) ist ein bewusster
HW-Verify-Merker für 0.6/0.7 mit klarem (software-only) Fix-Pfad, kein Blocker
für 0.5. **Sub-Stage 0.5 fertig** (Sim-Aufstehen validiert: Init-Pose echt,
Stand-up stabil + horizontal). Geänderte Dateien bereit für User-Commit.

## Sub-Stage 0.6 — HW Live aufgebockt (Init + Stand-up) ✅ FERTIG (2026-05-31)

Test: [`phase_13_stage_0_6_hw_standup_test_commands.md`](phase_13_stage_0_6_hw_standup_test_commands.md).
HW-Pendant zu 0.5: real.launch.py (0.3-Init) → gait.launch.py (0.4-Stand-up),
echter Roboter aufgebockt. **Live durch User:** Init + Stand-up all-6 sauber,
Endpose stabil, Shutdown stromlos, kein Stall/Freeze/IKError/Trip. **T4 = Füße
wandern sichtbar einwärts → Schürf-Befund auf HW bestätigt → kartesisches
Aufstehen als neue Stage 0.7 aktiviert (Umnummerierung 2026-05-31 ausgeführt).**

```
- [x] 0.6.1  Build hexapod_hardware + bringup + description + gait grün, gesourct
- [x] 0.6.2  T1: Init-Sequenz aufgebockt — alle 6 power_on_mid, Relay an, kein Trip
- [x] 0.6.3  T2: Stand-up all-6 sauber — kein Stall/hartes Springen/IKError/Watchdog/Overcurrent
- [x] 0.6.4  T3: Endpose stabil (≈ coxa 0 / femur −0.24 / tibia +0.76), Relay bleibt an
- [x] 0.6.5  T4: Schürf-Beurteilung — Füße wandern sichtbar einwärts → **kartesisches Aufstehen aktiviert (neue Stage 0.7)**
- [x] 0.6.6  T5: Shutdown stromlos (Servos limp)
- [x] 0.6.7  Self-Review (unten), keine offenen 🔴
```

### Sub-Stage 0.6 — Post-Review (2026-05-31)

| # | Punkt | Status |
|---|---|---|
| R1 | Init + Stand-up auf echter HW = konsistent zur Sim (0.5): power_on_mid-Init, all-6-Stand-up, Endpose stabil | OK |
| R2 | Kein Stall/Freeze/IKError/Watchdog/Overcurrent über Init + Stand-up + Endpose (aufgebockt) | OK |
| R3 | `use_sim_time:=false` + `robot_description_file` (nicht-lenienter Limit-Check) live korrekt — kein stiller Timer-Block, kein Limit-Freeze | OK |
| R4 | **T4 Schürf-Befund HW-bestätigt:** Füße wandern beim Aufstehen sichtbar einwärts (wie 0.5-FK-Prognose); Strom-Befund: Aufstehen >3,5 A / Stehen ~400 mA → kartesisches Aufstehen als **neue Stage 0.7** aktiviert, Umnummerierung 2026-05-31 ausgeführt | 🟡 → Stage 0.7 (DL-8) |
| R5 | Strom-Limit-Thema (Default 3500 mA) separat angefasst: User hebt auf 7000 mA an — FW-`config.hpp` + test_stage_e.py-Spiegel, Re-Flash (rebuild!) nötig | 🟡 → erledigt + Memory `project_fw_rebuild_before_flash` |

**Ergebnis:** keine 🔴. Zwei 🟡 (R4 → Stage 0.7 als nächste Arbeit, R5 → Limit-
Change) sind bewusste Folge-Schritte. **Sub-Stage 0.6 fertig.** Bereit für
User-Commit.

**→ Nächste Arbeit:** Stage 0.7 (kartesisches Aufstehen) ist durch T4 + den
Strom-Befund getriggert; Umnummerierung ausgeführt (DL-8).

## Sub-Stage 0.7 — Kartesisches schürffreies Aufstehen 🟡 AKTIV (E erledigt, A+B offen)

Plan: [`phase_13_stage_0_7_cartesian_standup_plan.md`](phase_13_stage_0_7_cartesian_standup_plan.md).
**Status:** Plan ausgearbeitet (§1a HW-Strom-Analyse), Paket E (Offline-Tool) ✅,
§8 datengetrieben geklärt; Engine-Code (A+B) + Tests (D) offen. Konzept:
zwei-Phasen-Aufstehen (Phase 1 Touchdown bauch-gestützt → Phase 2 Push mit fixen
Füßen, radial fix/nur body_height → schürffrei by design), nutzt vorhandene
cartesian-IK; **keine** Geometrie-Änderung (Tibia kürzen = §7.7 TABU, per Math
widerlegt). **Done-Kriterium:** Aufsteh-Strom am Boden nahe Stand-Niveau
(~400 mA) statt >3,5 A, kein Trip/Voltage-Drop. Checkliste 0.7.1–0.7.11 im Plan §7.

**Fortschritt:**
- [x] 0.7.1  Offline-Tool `tools/standup_envelope_check.py` (Paket E) — **GRÜN**:
  body_height_start **−13,5 mm**; Phase 1 (direkter cart. Lerp, kein vorzeitiger
  Bodenkontakt) + Phase 2 (Push, Knie 43–58°, keine Singularität) für alle 6
  Beine in-limits/erreichbar; limitierend Tibia (rad-Margin 0,13–0,15).
  §8.1/8.3/8.4 datengetrieben entschieden (Plan §5a/§8). Kinematisch ok ≠ Strom ok.
- [ ] 0.7.2 ff. Engine-Implementierung (A+B) + Tests (D) — nächster Schritt.

## Sub-Stage 0.8 — Boden-Test (Hexapod liegt am Bauch, Aufstehen all-6)

_test_commands just-in-time._ Läuft mit dem **schürffreien 0.7-Aufstehen** (nicht
dem joint-space-Schürf-Aufstehen). War vor der Umnummerierung 2026-05-31 als 0.7
geführt.

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
| DL-7 | **Stand-up all-6 simultan** (STARTUP_RAMP) | Tripod 3+3 (urspr. Stage-0-Plan §6/§7) | Aufstehen erfolgt **vom Bauch** (bzw. aufgehängt-am-Bauch = Boden-Sim): Bauch/Boden ist die Stütze, nicht die Beine → kein Stativ-Bedarf. Tripod 3+3 ist für statische Stabilität nötig, wenn der Körper allein auf den Beinen steht + Füße umgesetzt werden (z. B. Bein-Radius-Änderung — kein 0.4-Thema). all-6 verteilt zudem die Lift-Last auf 6 statt 3 Servos (weniger Stall-Risiko). Stage-0-Plan §6/§7 entsprechend korrigiert | 2026-05-30 |
| DL-8 | **Kartesisches schürffreies Aufstehen als neue Stage 0.7** (joint-space-STARTUP_RAMP bleibt als Legacy-Fallback); Boden-Test → 0.8 umnummeriert | joint-space-Aufstehen für HW behalten | 0.6-HW-Befund: joint-space-Ramp lässt Füße ~15–22 mm einwärts schürfen → am Boden >3,5 A + Voltage-Drop (Stehen kostet nur ~400 mA → Schürfen ist die Wurzel). Cartesian (Füße fix, nur body_height heben) eliminiert das Schürfen by design. Boden-Test muss mit dem schürffreien Aufstehen laufen → 0.7 schiebt sich davor, Boden→0.8. Plan: `phase_13_stage_0_7_cartesian_standup_plan.md` | 2026-05-31 |

## Offene Punkte (cross-Sub-Stage, zu klären wenn erreicht)

| # | Frage | Wann |
|---|---|---|
| O-1 | Femur-Limits global-asymmetrisch (alle 6 gleich) oder per-Bein? | nach 0.2 Re-Cal-Messwerten |
| O-2 | Exakter 35°-Wert vs. real erreichter Winkel pro Bein (Mech-Toleranz) | 0.2 Umbau/Re-Cal |
| O-3 | Gleiche Tripod-Sequenz für Bench + Boden, oder zwei Varianten? | 0.6/0.7 Live |
| O-4 | Gazebo-Genauigkeit für Stand-up-Dynamik ausreichend? | 0.5 Sim |
