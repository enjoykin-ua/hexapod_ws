# Phase 13 Stage 0.4 — Gait Stand-up (all-6 simultan, ab power_on_mid)

> **Übergeordnet:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §3/§6.
> **Vorbedingung:** 0.1 (Relay) ✅, 0.2 (Re-Cal) ✅, 0.3 (power_on_mid Init-Pose +
> relay-gated on_activate) ✅.
> **Test-Anleitung:** `phase_13_stage_0_4_standup_test_commands.md` (just-in-time
> nach Code).
> **Status:** ⚪ Plan, wartet auf §4-Klärung + Freigabe.

**Ziel:** Der Hexapod fährt nach dem Plugin-Init (power_on_mid, Beine
angehoben/eingezogen, Bauch liegt auf) **mit allen 6 Beinen gleichzeitig** sanft
in die Stand-Pose hoch — „vom Bauch aufstehen". Nahtloser Übergang
Boot → Init-Pose → **Stand-up** → STANDING (bereit für cmd_vel/Walking).

---

## 1. Design-Entscheidung: all-6 simultan (NICHT Tripod 3+3)

**Entscheidung (User, 2026-05-30):** Aufstehen erfolgt mit **allen 6 Beinen
gleichzeitig**, nicht gestaffelt 3+3. Begründung:

- Beim Aufstehen **vom Bauch** (bzw. aufgehängt-am-Bauch auf der Testaufhängung,
  die den Boden simuliert) ist **der Bauch/Boden die Stütze** — nicht die Beine.
  Es gibt keinen Grund, 3 Beine als statisches Stativ am Boden zu halten.
- Tripod 3+3 ist für **statische Stabilität nötig, wenn der Körper allein auf
  den Beinen steht** und Füße umgesetzt werden (z. B. Bein-Radius ändern im
  Stand: 3 planted, 3 repositionieren). Das ist **kein** 0.4-Thema.
- Beim **Hochdrücken** verteilt all-6 die Last auf 6 Beine statt 3 → geringeres
  Drehmoment/Stall-Risiko pro Servo. Tripod wäre beim Lift sogar ungünstiger.

> **Vertrags-Korrektur:** Der Stage-0-Plan §6/§7 sagte „Tripod 3+3 Stand-up".
> Das wird mit obiger Begründung auf **all-6-simultan** korrigiert (siehe
> Patch in `phase_13_stage_0_plan.md` + Design-Log DL-7). Tripod bleibt das
> Lauf-Pattern (existiert, unverändert).

## 2. Ausgangslage: der Stand-up existiert bereits (STARTUP_RAMP)

Die `gait_engine` hat seit Phase-13-Stage-A einen `STATE_STARTUP_RAMP`
([gait_engine.py:163](../src/hexapod_gait/hexapod_gait/gait_engine.py#L163) ff.):

1. `gait_node` abonniert `/joint_states`
   ([gait_node.py:500](../src/hexapod_gait/hexapod_gait/gait_node.py#L500)).
2. Beim **ersten vollständigen** Empfang (alle 18 Joints) ruft es
   `engine.start_ramp(start_joints, t, auto_standup_duration)` — `start_joints`
   ist die **real gemessene Pose** aus `/joint_states`.
3. Die Engine lerpt **joint-space, all-6 gleichzeitig**, per Smooth-Step
   (`s = p²(3−2p)`, Geschwindigkeit 0 an beiden Enden) von `start_joints` zur
   Stand-Pose-IK (`radial_distance` / `body_height`).
4. Bei `progress ≥ 1` → automatisch `STATE_STANDING`. `cmd_vel` wird während des
   Ramps ignoriert.

**Was 0.3 daran geändert hat:** Vor 0.3 war der erwartete Startpunkt das
obsolete `suspended`-Preset (femur=+1.45). Nach 0.3 meldet `/joint_states`
**automatisch die power_on_mid-Pose** (Echo-State aus `last_command_pulse_us_ =
1500`). Der Ramp-Mechanismus ist also bereits korrekt verdrahtet — **nur die
Test-Fixtures referenzieren noch den alten suspended-Startpunkt.**

## 3. Verifizierte Zahlen (power_on_mid → Stand-Pose)

> **⚠️ Korrektur (2026-05-30): Stand-Pose-Limit-Bug entdeckt + behoben.**
> Beim Berechnen der Sim-Initpose (User-Wunsch: exakte HW-Werte) fielen ZWEI
> Fehler auf, die in der lenienten Phase-5-Sim nie sichtbar waren:
>
> 1. **Falsche Limit-Quelle in der 0.4-Erstfassung:** `pulse_us_to_radians(1500)`
>    + In-Limits-Test nutzten `config.py`-Limits (coxa ±1.57, tibia ±1.50). Die
>    **echten** Limits, die das Plugin via `set_joint_limits` aus der URDF nimmt,
>    sind aber **coxa ±0.415, femur ±1.57, tibia ±1.161** (Stage-F-strict-min).
>    Da die Slope-Formel von den Limits abhängt, waren die power_on_mid-coxa/tibia-
>    Werte falsch skaliert.
> 2. **Stand-Pose (radial 0.27 / body_height −0.052) verletzt das Tibia-Limit:**
>    sie verlangt **tibia = 1.332 rad**, aber das Limit ist **1.161**. Auf der HW
>    → Stage-0.5-`safety_freeze` für die rechten Beine (PWM 751 µs < cal-min
>    870 µs). Wurzel: die Stand-Pose-Defaults wurden bei der Stage-F-Limit-
>    Verengung (2026-05-25) **nicht mitgezogen**; die Sim-IK lief lenient → nie
>    aufgefallen. **Fix:** radial 0.27 → **0.295**, body_height −0.052 → **−0.080**
>    (Beine weiter gestreckt → Tibia knickt weniger → 0.758 rad, klar in-limit).

### 3.1 power_on_mid (1500 µs) — KORREKT mit URDF-Limits

| pin/joint | rad | deg | in [limit] |
|---|---|---|---|
| leg_1 coxa/femur/tibia | −0.069 / −0.469 / +0.258 | −4.0 / −26.9 / +14.8 | ✓ |
| leg_2 coxa/femur/tibia | +0.156 / −0.637 / +0.255 | +8.9 / −36.5 / +14.6 | ✓ |
| leg_3 coxa/femur/tibia | −0.111 / −0.439 / +0.168 | −6.4 / −25.1 / +9.6 | ✓ |
| leg_4 coxa/femur/tibia | +0.026 / −0.477 / +0.255 | +1.5 / −27.3 / +14.6 | ✓ |
| leg_5 coxa/femur/tibia | +0.104 / −0.419 / +0.156 | +5.9 / −24.0 / +8.9 | ✓ |
| leg_6 coxa/femur/tibia | +0.052 / −0.496 / +0.224 | +3.0 / −28.4 / +12.8 | ✓ |

(femur ist umbau-bedingt ~−27° = Servo-Mitte nach 35°-Umbau; coxa/tibia-
Abweichungen = reine Servo-Montage-/Cal-Toleranz, alle in-limit.)

### 3.2 Stand-Pose (radial 0.295 / body_height −0.080) — alle 6 Beine

`coxa = 0.000, femur = −0.240, tibia = +0.758` (rad), identisch für alle 6
Beine (symmetrische Geometrie). Alle in-limit (tibia 0.758 ≪ 1.161).

### 3.3 Gültige Stand-Höhen (Referenz für Live-Tuning 0.6, Param-anfahrbar)

Alle 6 Beine ∈ URDF-rad-Limits **und** ∈ cal-PWM-Range. `body_height` = Foot-Z
im Bein-Frame (negativer = tiefer/geduckter):

| body_height | radial gültig | empf. radial | tibia @ empf. |
|---|---|---|---|
| −0.05 | 0.285–0.310 | 0.300 | +0.82 |
| −0.06 | 0.280–0.310 | 0.295 | +0.88 |
| −0.07 | 0.280–0.310 | 0.295 | +0.82 |
| **−0.08 (DEFAULT)** | **0.275–0.310** | **0.295** | **+0.76** |
| −0.09 | 0.270–0.305 | 0.290 | +0.79 |
| −0.10 | 0.270–0.305 | 0.290 | +0.71 |
| −0.11 | 0.265–0.300 | 0.285 | +0.72 |

Bei fixem radial=0.295 ist body_height von −0.020 bis −0.120 gültig → die
`/cmd_body_height`-Live-Mutation-Grenzen werden auf min −0.115 / max −0.030
gesetzt (innerhalb des gültigen Bereichs mit Reserve).

**Bewegungs-Charakter Aufstehen:** Coxas zentrieren auf 0°, Femurs heben von
~−27° (power_on_mid) auf ~−14° (Stand), **Tibias knicken von ~+13° auf ~+43°
ein** — der „Hochdrück"-Move. Da Smooth-Step **monoton** zwischen power_on_mid
und Stand-Pose interpoliert und beide Endpunkte in-limits sind, sind **alle
Zwischenwerte ebenfalls in-limits** → kein Freeze während des Aufstehens
(Test `power_on_mid_start_ramp_in_limits` mit den KORREKTEN Limits).

## 4. Offene Punkte für User-Review

| # | Frage | Vorschlag |
|---|---|---|
| 4.1 | **Stand-up-Pfad:** gait_node `STARTUP_RAMP` (joint-space, 50 Hz, nahtloser Übergang ins Walking) vs. stand_node (one-shot, ein JTC-Goal, cartesian-IK, Phase-5-Sim-Artefakt)? | **gait_node STARTUP_RAMP** — bereits all-6, bereits getestet, mündet direkt in STANDING→cmd_vel. stand_node bleibt als Sim-Helfer, wird nicht der HW-Stand-up-Pfad |
| 4.2 | **auto_standup_duration** Default 4.0 s ok? (größte Bewegung Tibia ~64° → ~16°/s = 0.28 rad/s, weit unter 2.0 rad/s URDF-Cap) | **4.0 s behalten** — sanft, konservativ. Live in 0.6 justierbar (Param) |
| 4.3 | **Stand-Pose-Parameter** radial=0.27 / body_height=−0.052: aus Sim/Phase-5. Für HW aufgebockt ok, oder anderer Wert? | **Sim-Default behalten** für 0.4 (Logik-Stage); HW-Feintuning in 0.6 live (Param) |
| 4.4 | **suspended-Fixture** in `test_startup_ramp.py` (femur=1.45): ersetzen durch power_on_mid oder beide behalten? | **Ersetzen** durch power_on_mid-Fixture (realer Startpunkt); Lerp-Math ist start-agnostisch, aber Fixture soll Realität spiegeln. Ein generischer Math-Test bleibt start-agnostisch |
| 4.5 | **Engine-Code-Änderung nötig?** Analyse sagt: nein (all-6 Ramp existiert, in-limits garantiert). 0.4 = Tests + Validierung + Doku | **Bestätigen**: kein Engine-Rewrite. Falls Validierung (4.x/0.5) ein echtes Gap zeigt → dann fixen + Plan ergänzen |

## 5. Logik-Skizze (was tatsächlich passiert, kein Neubau)

```
# Boot-Flow (real.launch.py + gait.launch.py):
1. Plugin on_activate (0.3) → Servos auf power_on_mid (1500 µs), Relay an.
2. joint_state_broadcaster publisht /joint_states (Echo = power_on_mid-rad).
3. gait_node erster /joint_states-Empfang → start_ramp(power_on_mid_pose, t, 4.0).
4. Engine STATE_STARTUP_RAMP: pro 50-Hz-Tick joint-space-Smooth-Step
   power_on_mid → stand-pose, alle 6 Beine gleichzeitig, monoton, in-limits.
5. progress ≥ 1 → STATE_STANDING. Roboter steht. cmd_vel ab jetzt aktiv.
```

**Arbeitsinhalt 0.4 (klein, da Mechanik vorhanden):**
- `test_startup_ramp.py`: suspended-Fixture → power_on_mid-Fixture; Test
  ergänzen, der **In-Limits über den ganzen Ramp** belegt (alle Zwischensamples
  ∈ URDF-Limits) + **all-6-simultan** (alle Beine bewegen sich im selben
  Progress, keine Staffelung).
- Validierung: monotoner, in-limits Sweep ab power_on_mid (pure-python).
- Doku: gait README / Stand-up-Abschnitt auf power_on_mid + all-6 aktualisieren,
  suspended als obsolet markieren.
- **Kein** Engine-/Node-Logik-Rewrite, sofern Validierung kein Gap zeigt.

## 6. Tests-Liste mit Begründung

### 6.1 Pure-Python (pytest, `colcon test hexapod_gait`)
| Test | Prüft | Warum |
|---|---|---|
| `power_on_mid_start_ramp_in_limits` | jeder Zwischensample (11 Stützstellen) aller 18 Joints ∈ URDF-Limits | Belegt: kein Plugin-Freeze während Stand-up (HW-Sicherheit) |
| `power_on_mid_ramp_endpoint_is_stand_pose` | Ramp-Ende == Stand-Pose-IK (alle 6 Beine) | Korrektes Ziel |
| `power_on_mid_ramp_all_six_simultaneous` | alle 6 Beine bei gleichem progress denselben Lerp-Faktor (keine Staffelung) | Belegt all-6-Design (Abgrenzung zu 3+3) |
| `power_on_mid_ramp_monotonic` | jeder Joint monoton start→ziel über 11 Samples | Kein Zurückschwingen / Slam |
| bestehende suspended-Tests | auf power_on_mid-Fixture umgestellt | Fixture-Realität nach 0.3 |

### 6.2 Bewusst NICHT in 0.4 (Scope-out)
- **Sim-Visualisierung** (Gazebo/RViz Stand-up ansehen) → 0.5.
- **HW aufgebockt** (echtes Aufstehen am Roboter) → 0.6.
- **Boden-Test** (liegt am Boden, Füße greifen) → 0.7.
- **Walking nach Stand-up** → spätere Phase-13-Stage / Phase 12.

## 7. Progress-Checkliste (→ phase_13_stage_0_progress.md, 0.4.x)

```
- [ ] 0.4.1  Design all-6 (nicht 3+3) im Stage-0-Plan §6/§7 + DL-7 korrigiert
- [ ] 0.4.2  test_startup_ramp.py: suspended-Fixture → power_on_mid-Fixture
- [ ] 0.4.3  Test power_on_mid_start_ramp_in_limits (alle Zwischensamples in-limits)
- [ ] 0.4.4  Test power_on_mid_ramp_endpoint_is_stand_pose
- [ ] 0.4.5  Test power_on_mid_ramp_all_six_simultaneous
- [ ] 0.4.6  Test power_on_mid_ramp_monotonic (auf power_on_mid-Start)
- [ ] 0.4.7  (nur falls Gap) Engine/Node-Fix + Begründung
- [ ] 0.4.8  colcon test hexapod_gait grün (+ flake8/pep257/copyright)
- [ ] 0.4.9  gait README Stand-up-Abschnitt: power_on_mid + all-6, suspended obsolet
- [ ] 0.4.10 Self-Review-Tabelle, Fixe erledigt
```

## 8. Cross-References
- [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §6/§7 · [`phase_13_stage_0_progress.md`](phase_13_stage_0_progress.md)
- Code: [`gait_engine.py`](../src/hexapod_gait/hexapod_gait/gait_engine.py) (STARTUP_RAMP) · [`gait_node.py`](../src/hexapod_gait/hexapod_gait/gait_node.py) (_on_joint_states) · [`trajectory_gen.py`](../src/hexapod_gait/hexapod_gait/trajectory_gen.py) (stand_pose) · [`leg_ik.py`](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py)
- Tests: [`test_startup_ramp.py`](../src/hexapod_gait/test/test_startup_ramp.py)
- Memory: `project_phase13_gait_launch_sim_time_default` (gait.launch.py use_sim_time-Default — relevant ab 0.6 HW), `project_phase13_onactivate_watchdog_heartbeat`
