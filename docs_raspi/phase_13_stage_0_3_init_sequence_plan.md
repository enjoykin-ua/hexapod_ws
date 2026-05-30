# Phase 13 Stage 0.3 — Relay-gated on_activate Init-Sequenz + K3-Init-Pose

> **Übergeordnet:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §3/§6.
> **Vorbedingung:** 0.1 (Relay-Frame + Service) ✅, 0.2 (Re-Cal + Femur-Limits
> ±1.57) ✅.
> **Test-Anleitung:** [`phase_13_stage_0_3_init_sequence_test_commands.md`](phase_13_stage_0_3_init_sequence_test_commands.md).
> **Status:** ⚪ offen, wartet auf Freigabe.

**Ziel:** Das Plugin `on_activate` fährt beim Start **zuverlässig** (kein
Race, kein hängendes Bein) in eine **sichere Init-Pose**, indem es den Relay
selbst gesteuert dazuschaltet und das Enable gestaffelt macht. Ersetzt das
obsolete Stage-A-„suspended"-Preset (femur=+1.45) und löst den in 0.2
beobachteten Init-Race.

---

## 1. Problem-Zusammenfassung (aus 0.2)

1. **Obsolete Init-Pose:** `initial_poses.yaml` „suspended" = femur **+1.45**
   (≈90° runter) — für die alte Montage, nach dem 35°-Umbau falsch.
2. **Init-Race:** beim Start aktivieren die 6 JTCs zu leicht versetzten Zeiten
   und „frieren" die Position ein, die sie über `/joint_states` lesen. Das
   Plugin `read()` echot aber bis zum ersten read-Tick nach `on_activate`
   transient `pulse_zero` (rad=0) statt der echten Pose ([hexapod_system.cpp:272-289](../src/hexapod_hardware/src/hexapod_system.cpp#L272-L289)).
   → je nach Timing erwischt ein (zufälliges) Bein den Down-Befehl und bleibt
   unten.
3. **Inrush:** beim Relay-On ziehen potenziell alle 18 Servos gleichzeitig
   (TOTAL_CURRENT_MAX_MA=3500); Enable gestaffelt nach Joint-Gruppe spreizt das.

## 2. Logik-Skizze

### 2.1 K3 — Init-Pose = Servo-Mitte (1500 µs), direkt als PWM

**Entscheidung:** Die Init-Pose ist **die Power-On-Position selbst** — jeder
Servo geht beim Einschalten hardware-bedingt auf **Servo-Mitte ≈ 1500 µs**.
Wenn wir genau das als Target setzen, gibt es **null Bewegung** beim Relay-On
und der JTC-Race ist **irrelevant** (alle JTCs frieren dieselbe Pose ein).

- `initial_pulse_us_[i] = 1500` für **alle 18 Pins** (statt rad→pulse aus dem
  „suspended"-Preset).
- Resultierende Pose ≈ Femurs ~27–35° hoch, Coxas radial-neutral, Tibias
  gestreckt — sichere „Beine hoch/außen"-Pose (aufgebockt + liegend ok).
- **Race-Fix:** in `on_activate` zusätzlich `hw_state_positions_[i] =
  Calibration::pulse_us_to_radians(i, 1500)` setzen, **bevor** die JTCs
  aktivieren — dann liest jeder JTC die *echte* Init-Pose und hält sie
  konsistent (löst den dokumentierten read-Race aus §1.2).

### 2.2 Relay-gated, gestaffelte on_activate-Sequenz

Pseudocode (ersetzt die aktuelle on_activate-Frame-Folge):
```
1. RESET                          # FW: disable_all, relay LOW, targets=pulse_zero, flags clear
2. SET_TARGETS(initial=1500 alle) # FW-Target = Servo-Mitte; Servos noch stromlos (relay aus)
3. for pin in FEMUR_PINS (1,4,7,10,13,16): ENABLE_SERVO(pin)   # 50 ms Stagger; PWM an, kein Strom
4. RELAY_CONTROL(on)              # Rail an → nur Femurs (enabled) bestromt, stehen schon auf 1500 → keine Bewegung
5. sleep ~700 ms                  # Femurs settle, Strom beobachtbar (nur 6 Servos)
6. for pin in COXA_PINS (0,3,6,9,12,15):  ENABLE_SERVO(pin)    # +6 Servos
7. sleep ~400 ms
8. for pin in TIBIA_PINS (2,5,8,11,14,17): ENABLE_SERVO(pin)   # +6 Servos
9. SET_TARGETS(initial=1500 alle) # reaffirm + Watchdog-Kick
   last_command_pulse_us_ = 1500; hw_state_positions_ = rad(1500)
```
- **on_deactivate** bleibt wie 0.1 (Relay-Off vor Disable) — kein Change.
- Pin-Gruppen: Femur = mittlerer Pin je Triple, Coxa = niedrigster, Tibia =
  höchster (servo_mapping.yaml-Konvention).

### 2.3 Obsoletes Preset

- `initial_poses.yaml` „suspended" (femur=+1.45) wird **entfernt/ersetzt** durch
  den direkten 1500-µs-Init (oder ein Preset `power_on_mid`). Der rad-basierte
  Preset-Loader kann bleiben (Legacy), aber Default ist jetzt 1500-µs-Init.
- Launch-Arg `initial_pose` Default → neuer Modus.

### 2.4 Welche Dateien
| Datei | Änderung |
|---|---|
| `hexapod_hardware/src/hexapod_system.cpp` | on_activate-Sequenz (gestaffelt + Relay-On), init=1500, hw_state-Race-Fix |
| `hexapod_hardware/config/initial_poses.yaml` | „suspended" obsolet → `power_on_mid` (1500 µs) bzw. Doku-Update |
| `hexapod_description/urdf/hexapod.urdf.xacro` | `initial_pose`-Default-Param ggf. anpassen |
| **kein FW-Change** | Relay-Frame + RELAY_CONTROL existieren (0.1) |

## 3. Tests-Liste mit Begründung

### 3.1 Unit (PTY, `colcon test hexapod_hardware`)
| Test | Prüft |
|---|---|
| `PtyActivateRelayGatedSequenceOrder` | Frame-Folge: RESET → SET_TARGETS → 6×ENABLE(femur) → **RELAY_CONTROL(on)** → 6×ENABLE(coxa) → 6×ENABLE(tibia) → SET_TARGETS reaffirm |
| `InitPulsesAreServoMid` | initial_pulse_us_ = 1500 für alle 18 |
| `ActivateSetsHwStateToInitPose` | hw_state_positions_ = rad(1500) nach activate (Race-Fix) |
| Bestehende Tests anpassen | `PtyActivateSendsBootSequenceInOrder` + Stagger-Timing-Band (neue Gruppen-Delays) |

### 3.2 Live (test_commands)
- Relay-On-Sequenz: **alle 6 Beine** erreichen die Init-Pose, **kein** Bein
  bleibt unten (Race-Fix), **kein** ruckartiges Springen.
- 5× Plugin-Restart → jedes Mal identisch (Race wirklich weg).
- Strom beim gestaffelten Enable beobachten — kein Overcurrent-Trip.

### 3.3 Bewusst NICHT getestet (Scope-out)
- **Stand-up / Aufstehen** → 0.4.
- **Sim-Visualisierung** → 0.5.

## 4. Offene Punkte für User-Review

| # | Frage | Vorschlag |
|---|---|---|
| 4.1 | Init-Pose = **1500 µs alle Pins** (Servo-Mitte, zero-jerk, race-immun) vs. definierte rad-Pose (femur mid-rad, coxa/tibia rad=0) | **1500 µs alle** — simpelste race-immune Lösung; Stand-Pose macht 0.4 |
| 4.2 | Gestaffelte Gruppen-Delays (femur 700 ms, coxa 400 ms)? | Startwerte; live justieren falls Overcurrent |
| 4.3 | Overcurrent-Risiko: 18 Servos holding > 3500 mA? | Gestaffeltes Enable + Live-Strom beobachten; falls nötig `SET_CURRENT_LIMIT` hochsetzen (FW-Frame existiert) — separat entscheiden |
| 4.4 | „suspended"-Preset löschen oder als Legacy behalten? | **Ersetzen** durch `power_on_mid`; rad-Loader bleibt für evtl. spätere Presets |
| 4.5 | Femur-vor-Relay-Enable-Reihenfolge ok (brainstorm §4) oder andere Gruppe zuerst? | **Femur zuerst** (brainstorm), dann Coxa, dann Tibia |

## 5. Cross-References
- [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §6 · [`phase_13_stage_0_progress.md`](phase_13_stage_0_progress.md) (0.2-Findings: Init-Race + K3)
- [`phase_13_stage_0_brainstorm.md`](phase_13_stage_0_brainstorm.md) §4 (Init-Sequenz-Konzept)
- Code: [`hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp) on_activate · `servo2040_protocol` (encode_relay_control, 0.1) · `calibration.cpp` (pulse_us_to_radians)
- Memory: `project_phase13_initial_pose_presets`, `project_phase13_gait_launch_sim_time_default`
