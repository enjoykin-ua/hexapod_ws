# Phase 13 Stage 0 — Hardware Init-Pose via Femur-Umbau + Relay (Übersicht / Vertrag)

> **Status:** ✅ formaler Plan (löst das Brainstorm
> [`phase_13_stage_0_brainstorm.md`](phase_13_stage_0_brainstorm.md) ab).
> Erstellt 2026-05-30.
>
> **Naming:** Stage **0** = Hardware-Stage **vor** allen Plugin-Stages
> (A/B/C…) der Phase-13-Desktop-Pre-Bringup-Kette
> ([`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md)).
> Die alte **Stage A** ("suspended"-Preset beim Activate) ist **obsolet** —
> ihr Konzept wurde durch das Servo-MID-on-Power-On-Verhalten widerlegt
> (siehe §2).
>
> **Dieser Plan ist der Vertrag** für Stage 0. Pro Sub-Stage (0.1–0.4) gibt
> es ein eigenes Detail-Plan-File (CLAUDE.md §4: Plan → Freigabe →
> Implementierung → Tests → Self-Review). Die interaktiven Stages (0.5–0.7)
> bekommen nur `*_test_commands.md`.

---

## 1. Zweck

Der Hexapod soll beim Plugin-Start in eine mechanisch sichere Init-Pose
fahren — **Femurs ~35° nach oben** — sodass sowohl aufgebockt als auch
liegend ein sauberes Aufstehen zur Stand-Pose möglich ist, **ohne** dass
die Servos beim Einschalten unkontrolliert losschnappen.

## 2. Wurzel-Problem (warum die bisherigen Ansätze scheiterten)

Hobby-Servos (Miuzei MS61 / Diymore 8120MG, siehe Memory
`project_hexapod_servo_models`) fahren beim **Power-On hardware-bedingt zur
Servo-Mitte (~1500 µs)**. Das ist Servo-eigen und **nicht** umgehbar — weder
durch Software-Sequencing, Frame-Reordering, Double-Pulse, Warmup noch
Power-Sequencing (alle in `~/pimoroni_servo_fix/` erschöpfend getestet).

Konsequenz: Wir steuern nicht mehr, *wo* der Servo beim Init landet. Wir
passen die **Mechanik** so an, dass die unvermeidbare Mitte-Position die
gewünschte Init-Pose ist.

> **Hinweis zum FW-Fix** ([`phase_13_servo2040_fix.md`](phase_13_servo2040_fix.md)):
> die dort eingebauten FW-Änderungen (`servo_enabled`-Respekt in `on_tick`,
> `disable_all` in `handle_reset`, `current=target`-Sync) lösen das
> MID-on-Power-On **nicht**, halten aber PWM auf disabled Pins sauber aus.
> Das ist **Voraussetzung** für den Relay-Ansatz (nur Relay+Enable fahren
> die Servos hoch) und wird **als Fundament behalten**.

## 3. Lösungs-Konzept (drei Bausteine)

1. **Mechanische Verschiebung** der Femur-Segmente um ~35°: bei Servo-Mitte
   (Power-On-Position) zeigt der Femur 35° hoch statt horizontal. Coxa/Tibia
   bleiben unverändert.
2. **Relay** (GP26 / A0-Header, normally-open, high-trigger) als Strom-Gate:
   Default LOW = Servos stromlos. Das Plugin schaltet V+ erst auf, wenn die
   PWM-Signale sauber stehen.
3. **Plugin-Init-Sequenz** (gestaffeltes Enable: Femur → Relay-On → Coxa →
   Tibia) + **Gait-Stand-up** (Tripod 3+3) zum Aufstehen.

## 4. Design-Entscheidung: 35°-Offset lebt in der Kalibrierung (Weg A)

**Entscheidung (2026-05-30):** Das 35°-Offset wird **ausschließlich in der
Kalibrierung** (`servo_mapping.yaml` / `calibration.cpp`) absorbiert. Der
kinematische Vertrag bleibt unverändert:

> `rad_femur = 0` bedeutet weiterhin **Femur horizontal**, `+` = Bein nach
> unten. Die Init-Pose (35° hoch) ist schlicht `rad_femur ≈ −0.611`.

**Folgen:**

| Komponente | Änderung |
|---|---|
| `servo_mapping.yaml` (6 Femurs) | `pulse_zero` (=horizontal), `pulse_min` (oben-Kollision), `pulse_max` (unten) **neu kalibrieren** |
| Femur-Joint-Limits | **asymmetrisch** (mehr Range unten als oben), datengetrieben nach Re-Cal |
| URDF-Geometrie (`leg.xacro`) | **keine** — Femur-Box/Achse/origin unverändert |
| IK/FK (`leg_ik.py`, `config.py`) | **keine Formel-Änderung** — nur `_FEMUR_LIMITS`-Werte ziehen nach |
| RViz / Gazebo | **keine** — werden aus rad + unveränderter URDF korrekt gerendert |
| Init-Pose-Wert | `rad_femur ≈ −0.611` (alter "suspended"-Wert −1.45 ersetzt) |

**Warum Weg A statt "rad=0 = 35° hoch" (Weg B):**

Der Joint-Nullpunkt ist Konvention. Weg A hält den kinematischen Nullpunkt
dort, wo die IK-Trigonometrie sauber ist (horizontal), und lässt die
Kalibrierung den mechanischen Mount-Offset absorbieren — das ist der
designierte Ort dafür. Die analytische IK-Formel passt damit **nativ** zur
URDF (beide: θ=0 → Femur entlang +X). Weg B (URDF-`origin` um 35° rotieren)
würde die IK-Formel von der URDF entkoppeln und eine **magische
−0.611-Konstante** in IK *und* FK erzwingen plus alle IK-Tests anpassen —
mehr Eingriff in die validierte Kinematik-Kette, kein kinematischer Mehrwert
gegenüber A. Verworfen.

**Verworfene Alternative B:** rad=0 = 35° hoch, `pulse_zero` bleibt
~Servo-Mitte, dafür URDF-femur-origin + IK/FK + config.py + IK-Tests
offsetten. Verworfen — siehe oben.

## 5. Relay-Safety: Fail-safe depower

**Entscheidung (2026-05-30):** Relay = fail-safe. GP26 ist LOW (Strom aus)
außer in der expliziten `on_activate`-Sequenz. Aktiv abgeschaltet wird bei:

| Auslöser | Ursache | Aktion |
|---|---|---|
| Boot der FW | Power-On Servo2040 | GP26 als erstes auf LOW |
| Watchdog-Trip | Host sendet >200 ms keinen gültigen Frame (Plugin-Crash, `pkill`, USB ab, Host-Hänger) — FW erkennt das autonom | disable_all **+ Relay LOW** |
| Overcurrent-Trip | Gesamt-Rail-Strom > Limit (latched) | disable_all **+ Relay LOW** |
| Undervoltage-Crit-Trip | Rail < 5.0 V (latched) | disable_all **+ Relay LOW** |
| RESET-Frame | Plugin beim Activate (`on_activate` Schritt 1). **Nicht** `/hexapod_safety_reset` — der löscht nur das plugin-seitige `safety_freeze_`-Flag, sendet keinen FW-Frame | disable_all **+ Relay LOW** |
| `on_deactivate` | sauberer Plugin-Stop | Plugin sendet RELAY_CONTROL(off) vor Servo-Disable |

Relay HIGH **nur** explizit in der `on_activate`-Sequenz (0.3), nachdem die
PWM-Targets gesetzt und die Femur-Pins enabled sind.

## 6. Sub-Stage-Kette + Reihenfolge

Reihenfolge-Entscheidung: **FW-Relay + Plugin-Service zuerst**, der Umbau
nutzt danach die manuelle Relay-Steuerung (`/hexapod_relay_set`) der fertigen
Pipeline.

| Sub-Stage | Inhalt | Art | Plan-File |
|---|---|---|---|
| **0.1** | FW RELAY_CONTROL-Frame (0x51) + Fail-safe-Relay-Off + GP26-Boot-LOW; Plugin `/hexapod_relay_set` Service + `encode_relay_control` + on_deactivate-Relay-Off | Code, standalone testbar | [`phase_13_stage_0_1_relay_plan.md`](phase_13_stage_0_1_relay_plan.md) |
| **0.2** | Mech-Umbau (§6-Servo-Trick, an Weg A angepasst) + Re-Cal Femurs (pulse_zero/min/max) + asymm. Femur-Limits | User-Mechanik + Cal | _just-in-time_ |
| **0.3** | Plugin `on_activate` Relay-gated Init-Sequenz (Init-Target → Femur-Enable gestaffelt → Relay-ON → Coxa → Tibia); Init-Pose-Wert rad −0.611 | Code + Unit-Tests | _just-in-time_ |
| **0.4** | Gait Stand-up Tripod-3+3-States ab Init-Pose | Pure-Python + Unit-Tests | _just-in-time_ |
| **0.5** | Sim-Visualisierung Init + Stand-up (Gazebo + RViz) | interaktiv | _just-in-time test_commands_ |
| **0.6** | HW Live aufgebockt — Init + Stand-up | interaktiv | _just-in-time test_commands_ |
| **0.7** | Boden-Test — Hexapod liegt, Aufstehen via Tripod | interaktiv | _just-in-time test_commands_ |

Die Pläne für 0.2–0.7 werden **just-in-time** erstellt, weil ihre Inhalte
(asymmetrische Limits, Init-Pose-Start) von Mess-/Vorergebnissen abhängen.

## 7. Done-Kriterium Stage 0

Alle Sub-Stages 0.1–0.7 grün laut
[`phase_13_stage_0_progress.md`](phase_13_stage_0_progress.md):
Roboter fährt beim Plugin-Start ruckfrei in die 35°-Init-Pose (aufgebockt
**und** liegend) und steht via Tripod-3+3-Sequenz auf, ohne Foot-Schramm,
ohne IKError, ohne Servo-Stall.

## 8. Cross-References

**Stage-0-Detail:**
- [`phase_13_stage_0_1_relay_plan.md`](phase_13_stage_0_1_relay_plan.md) + `_test_commands.md`
- [`phase_13_stage_0_progress.md`](phase_13_stage_0_progress.md) — Done-Tracker + Design-Log
- [`phase_13_stage_0_brainstorm.md`](phase_13_stage_0_brainstorm.md) — Vorläufer (superseded)

**Phase-13-Kontext:**
- [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md) — übergeordnete Stage-Kette
- [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md) — obsolet
- [`phase_13_servo2040_fix.md`](phase_13_servo2040_fix.md) — FW-Fundament (behalten)

**Code:**
- FW: [`hexapod_servo_driver/src/main.cpp`](../../hexapod_servo_driver/src/main.cpp) · `src/config.hpp`
- Plugin: [`hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp) · `servo2040_protocol.{hpp,cpp}` · `calibration.cpp`
- Cal: [`servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml)
- Limits: [`hexapod_physical_properties.xacro`](../src/hexapod_description/urdf/hexapod_physical_properties.xacro) · [`config.py`](../src/hexapod_kinematics/hexapod_kinematics/config.py)
- Gait: `hexapod_gait/hexapod_gait/gait_engine.py` · `gait_node.py`
- Relay-Vorlage: [`pimoroni_servo_fix/src/test_relay_power_sequence.cpp`](../../pimoroni_servo_fix/src/test_relay_power_sequence.cpp)

**Memory:** `project_phase13_initial_pose_presets`, `project_phase13_femur_zero_asymmetry`,
`project_hexapod_servo_models`, `feedback_validate_hardware_hypothesis_via_code`.
