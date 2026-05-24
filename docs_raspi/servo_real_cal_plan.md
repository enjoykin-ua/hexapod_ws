# Servo-Real-Cal — Implementation-Plan

> **Vorbereitungs-Doku:** [`servo_real_calibration_todos.md`](servo_real_calibration_todos.md)
> enthält die finalen Cal-Daten (Tab. 3.2 PWM / 3.3 rad-Limits / 3.4
> Initial-Pose) und die Findings. Diese Doku ist der konkrete
> Implementation-Plan dazu, strukturiert in 6 Stages.

> **Strategie-Entscheidungen (User 2026-05-24):**
> - **F10 → Option (c) Plugin-Math fixen.** Volle asymm Range nutzen,
>   kein Range-Verlust durch Sym-Kürzung. Plugin-Code-Comment-Mismatch
>   parallel beheben.
> - **F2 → kompakte eigene Plan-Doku** (= diese Datei). Kein Mega-Plan
>   pro Sub-Stage; alle 6 Stages in einer Datei mit jeweils
>   Logik-Skizze + Tests + Progress + offene Punkte.
> - **F5 → Hexapod aufgebockt** (verifiziert User 2026-05-23).
> - **F6 → leg_6 zuerst** für Direction-Cal (Phase-10-Walking-Baseline).
> - **F8 → Sim-Verifikation visual + Walking-Smoke** reicht.
> - **F11 → Initial-Pose-PWMs nur dokumentieren** (12 Werte in
>   [`servo_real_calibration_todos.md`](servo_real_calibration_todos.md)
>   Sektion 3.4 — bleiben Phase-13-Material).
> - **Mount-Tausch leg_2↔leg_5** (2026-05-24): leg_2 und leg_5 waren
>   physisch vertauscht montiert, wurde korrigiert + re-kalibriert.
>   Cal-Daten in Cal-Doku reflektieren den Post-Tausch-Zustand.

---

## 1. Phasen-Einordnung

Diese Cal-Arbeit ist ein **Cross-Phase-Thread parallel zu Phase 12**.
Phase 12 (Pi-Plattform) bleibt aktiv im `PHASE.md`, dieser Plan macht
keine Phase-12-Done-Kriterien-Aussagen. Dokumente unter Präfix
`servo_real_cal_*` damit die Phase-12-Pi-Arbeit klar abgegrenzt bleibt.

## 2. Stage-Übersicht

| Stage | Was | Aufwand | Wer |
|---|---|---|---|
| **0** | Plugin-Math-Fix (Comment-Mismatch + direction-aware slope) | ~1 h | Claude |
| **0.5** | Plugin-Hard-Stop bei Pulse-Out-of-Range + Reset-Service | ~2 h | Claude |
| **0.6** | IK-Joint-Limit-Check + sofortiger safety_freeze bei Verletzung | ~1.5 h | Claude |
| **A** | URDF-Macro-Refactor (pro-Joint-Limit-Args, Defaults unverändert) | ~1 h | Claude |
| **B** | `servo_mapping.yaml` mit echten PWM-Werten (Cal-Doku Tab. 3.2) + direction=+1 Default für alle Pins | ~30 min | Claude |
| **C** | Direction-Cal HW+Sim parallel (6 Beine, je 3 Joints) | ~1–2 h | User + Claude |
| **D** | URDF mit finalen asymm rad-Limits aus Cal-Doku Tab. 3.3 (PWM-zentrisch, KEINE Spiegelung dank Plugin-Fix) | ~30 min | Claude |
| **E** | Sim-Verifikation (visual + Walking-Smoke) + Walking aufgebockt | ~1 h | User + Claude |

**Total: ~9–10 h verteilt über ≥ 2 Sessions** (Stage C+E sind interaktiv mit HW).

---

## Stage 0 — Plugin-Math-Fix

### 0.1 Logik-Skizze

**Problem (verifiziert 2026-05-24):**
[`calibration.cpp:176-197`](../src/hexapod_hardware/src/calibration.cpp#L176)
`radians_to_pulse_us` und `pulse_us_to_radians` haben Code-Comment-
Mismatch. Comment dokumentiert „sign of the (mechanical, not
signed-by-direction) joint side", Code-Bedingung ist aber `rad >= 0`
(= URDF-rad sign). Bei `direction=+1` identisch, bei `direction=-1`
+ asymm Cal divergiert → falsche slope wird gewählt → Servo-PWM
am Joint-Extremum ist halfway statt am mech-Anschlag.

**Fix-Strategie:**
Slope-Auswahl direction-aware machen. Bei `direction=+1` bleibt
Verhalten unverändert (slope_right=`(pulse_max-pulse_zero)/joint_upper`
für rad≥0). Bei `direction=-1` muss slope für rad≥0 stattdessen
`(pulse_zero-pulse_min)/joint_upper` sein, weil rad=+joint_upper
in URDF-Konvention dann physisch auf pulse_min landet (Mech-rad
= -URDF-rad).

**Pseudocode `radians_to_pulse_us`:**
```
double slope;
if (rad >= 0.0) {
    if (direction > 0)
        slope = (pulse_max - pulse_zero) / joint_upper;
    else
        slope = (pulse_zero - pulse_min) / joint_upper;
} else {
    if (direction > 0)
        slope = (pulse_zero - pulse_min) / |joint_lower|;
    else
        slope = (pulse_max - pulse_zero) / |joint_lower|;
}
return pulse_zero + direction * rad * slope;
```

**Inverse `pulse_us_to_radians`:** analog, slope-Auswahl basiert auf
`direction * dp >= 0` (= mech-rad-sign) — das ist bereits korrekt im
bestehenden Code (Z.213-219), nur die Forward-Funktion war buggy.
Vorsicht: bei direction=-1 muss auch hier die slope-Formula
direction-aware werden — `direction * dp >= 0` wählt die Mech-rad>=0-
Seite, dort ist die Distanz in PWM bei direction=-1 `pulse_zero-pulse_min`,
nicht `pulse_max-pulse_zero`.

**Mathematische Verifikation (hypothetisch leg_1_tibia, direction=-1,
pulse=870/1680/2185, joint_lower=-1.92, joint_upper=+1.197):**
- rad=+1.197: rad≥0, direction<0 → slope=(1680-870)/1.197=677 →
  pulse=1680+(-1)(1.197)(677)=**870** ✓ pulse_min
- rad=-1.92: rad<0, direction<0 → slope=(2185-1680)/1.92=263 →
  pulse=1680+(-1)(-1.92)(263)=**2185** ✓ pulse_max
- Roundtrip von pulse=870: dp=-810, direction·dp=+810≥0,
  direction<0 → slope=(1680-870)/1.197=677 →
  rad=-810/((-1)(677))=**+1.197** ✓

**Backwards-Compat:**
- direction=+1: Code-Verhalten unverändert, alle alten Tests bleiben grün
- direction=-1 + symm Cal: slope_right und slope_left bei direction=-1
  ergeben dieselben Werte wie bei direction=+1 (weil symm), Test
  `NegativeDirectionMirrors` bleibt grün
- direction=-1 + asymm Cal: NEU richtig (vorher Plugin-Math-Bug)

### 0.2 Tests-Liste

**Neu hinzufügen:**

| Test | Was | Begründung |
|---|---|---|
| `RadiansToPulse.NegativeDirectionAsymmetricUsesCorrectSide` | direction=-1 + asymm Cal, prüft Endpunkte (rad=joint_upper → pulse_min, rad=joint_lower → pulse_max) + 1 Zwischenwert | Deckt den genauen Bug-Fall ab |
| `Roundtrip.NegativeDirectionAsymmetricRoundtrips` | direction=-1 + asymm Cal, Loop über rad-Range, forward∘inverse = identity ±1e-9 | Sichert Konsistenz Forward↔Inverse bei der neuen direction-aware Math |

**Bestehende Tests die grün bleiben müssen:**
- `RadiansToPulse.SymmetricSlopesAtPulseZero`
- `RadiansToPulse.AsymmetricSlopesUseCorrectSide` (direction=+1, asymm)
- `RadiansToPulse.NegativeDirectionMirrors` (direction=-1, symm)
- `Roundtrip.ForwardThenInverseIsIdentitySymmetric`
- `Roundtrip.ForwardThenInverseIsIdentityAsymmetric` (direction=+1)
- `Roundtrip.NegativeDirectionRoundtrips` (direction=-1, symm)

**NICHT getestet (scope-out):**
- Verhalten bei direction außerhalb {-1, +1}. Schon durch
  `update_servo_cal`-Validation und `load_from_string`-Schema-Check
  abgedeckt.
- Verhalten bei `joint_upper <= 0` oder `joint_lower >= 0` (wäre
  invalid URDF). `set_joint_limits` macht dafür keine
  Sanity-Check — bewusst out-of-scope für diesen Fix.

### 0.3 Progress-Checkliste

```
- [ ] 0.1 calibration.cpp::radians_to_pulse_us slope-Auswahl
        direction-aware umschreiben (Pseudocode aus 0.1)
- [ ] 0.2 calibration.cpp::pulse_us_to_radians inverse-slope-Formel
        direction-aware umschreiben (analog)
- [ ] 0.3 Code-Kommentar in calibration.cpp Z.189-190 aktualisieren
        (Comment-Mismatch beheben, neue Logik dokumentieren)
- [ ] 0.4 Neuer Test RadiansToPulse.NegativeDirectionAsymmetricUsesCorrectSide
        in test_calibration.cpp (Cal-Werte aus leg_1_tibia-Setup)
- [ ] 0.5 Neuer Test Roundtrip.NegativeDirectionAsymmetricRoundtrips
- [ ] 0.6 colcon test --packages-select hexapod_hardware grün
        (alle alten + 2 neue Tests)
- [ ] 0.7 Self-Review-Tabelle: Edge-Cases (rad=0, pulse_zero ist
        an pulse_min/max-Grenze, joint_lower=joint_upper=0)
```

### 0.4 Offene Punkte für User-Review

- **0-Q1:** Soll der Comment-Mismatch-Fix als separater Commit oder
  zusammen mit der Math-Änderung? Empfehlung: ein Commit
  (`phase12: fix plugin-cal direction-aware slope selection`).
- **0-Q2:** Test-Suite-Stelle — neue Tests neben den bestehenden
  asymm/direction-Tests einfügen? Empfehlung: ja, in Reihenfolge
  parallel zur bestehenden Struktur.

---

## Stage 0.5 — Plugin-Hard-Stop bei Pulse-Out-of-Range

> **Hintergrund:** Firmware bleibt dumm (User-Entscheidung 2026-05-24)
> — das ROS-Plugin im hexapod_ws ist allein verantwortlich, niemals
> ein PWM-Signal außerhalb `[pulse_min, pulse_max]` zu senden. Stage 0.5
> implementiert die Last-Defense gegen Servo-Schaden.

### 0.5.1 Logik-Skizze

**Detektion:** in `hexapod_system.cpp::write()` nach `radians_to_pulse_us`:
wenn `pulse_raw` außerhalb `[pulse_min, pulse_max]` (mit 1 µs FP-Toleranz)
→ Hard-Stop-Mechanismus.

**Hard-Stop-Aktion:**
1. Plugin setzt internen Flag `safety_freeze_ = true`
2. Solange freeze aktiv: write() schreibt **letzte gültige PWM** zu allen
   Pins (alle Beine halten letzte Position)
3. `RCLCPP_ERROR` mit klarer Recovery-Anweisung (verweist auf
   `/hexapod_safety_reset` Service)
4. Optional: ein State-Topic `/hexapod_safety_state` publisht „frozen"
   damit gait_node + UI informiert sind

**Recovery via ROS-Service `/hexapod_safety_reset` (`std_srvs/Trigger`):**
1. User-Aufruf: `ros2 service call /hexapod_safety_reset std_srvs/srv/Trigger`
2. Plugin: `safety_freeze_ = false`, State-Topic „recovered"
3. **gait_node-side** (siehe Phase-13-Pendenz): fährt Hexapod erst zu
   `pose_standing` bevor cmd_vel akzeptiert wird

**Pseudocode `hexapod_system.cpp::write()` Ergänzung:**
```cpp
const auto & cal_pin = calibration_.at(output_idx);
const double pulse_raw = calibration_.radians_to_pulse_us(output_idx, rad);

// Stage 0.5: Last-Defense Hard-Stop gegen Servo-Schaden.
// Firmware ist dumb — Plugin garantiert PWM ∈ [pulse_min, pulse_max].
constexpr double FP_TOLERANCE = 1.0;  // µs, gegen FP-Rundung am Limit
const bool out_of_range =
  (pulse_raw < cal_pin.pulse_min - FP_TOLERANCE) ||
  (pulse_raw > cal_pin.pulse_max + FP_TOLERANCE);

if (out_of_range && !safety_freeze_.load()) {
  safety_freeze_.store(true);
  RCLCPP_ERROR(plugin_logger(),
    "SAFETY FREEZE: joint '%s' pulse %.1f µs outside cal range "
    "[%d, %d] — IK/URDF/cal mismatch. Hexapod frozen, all joints "
    "holding. Recover via: ros2 service call /hexapod_safety_reset "
    "std_srvs/srv/Trigger",
    info_.joints[i].name.c_str(), pulse_raw,
    cal_pin.pulse_min, cal_pin.pulse_max);
}

// Always write last_command (in freeze) or new clamped value (normal):
double pulse_out;
if (safety_freeze_.load()) {
  pulse_out = static_cast<double>(last_command_pulse_us_[output_idx]);
} else {
  pulse_out = std::clamp(pulse_raw,
    static_cast<double>(cal_pin.pulse_min),
    static_cast<double>(cal_pin.pulse_max));
}
last_command_pulse_us_[output_idx] = static_cast<int16_t>(std::round(pulse_out));
```

> **Warum Clamp ZUSÄTZLICH zum Hard-Stop?** Zwischen Detektion des
> Out-of-Range im Tick T und dem nächsten write() Tick T+1 muss ETWAS
> zur Firmware. Hard-Stop greift erst in Tick T+1. Im T-Tick selbst
> wird das geclampte (sichere) PWM gesendet, NICHT das raw-PWM.

### 0.5.2 Tests-Liste

| Test | Was |
|---|---|
| `WriteCycle.OutOfRangeAboveTriggersFreezeAndHoldsLastGood` | rad weit über joint_upper → pulse > pulse_max → safety_freeze=true, nächste write() schreibt last_command |
| `WriteCycle.OutOfRangeBelowTriggersFreeze` | analog untere Seite |
| `WriteCycle.InRangeRadDoesNotFreezeAndNoLogSpam` | rad innerhalb cal-Range, kein Freeze, kein Warning |
| `WriteCycle.FpToleranceAtPulseMaxDoesNotTrigger` | rad=joint_upper mit FP-Drift `pulse_raw = pulse_max + 0.4 µs` → kein Trigger |
| `SafetyResetService.ClearsFreezeFlag` | Service-Call setzt safety_freeze_ auf false |
| `SafetyResetService.WhileNotFrozenReturnsSuccess` | Idempotent (Service-Call wenn nicht frozen → ok) |

**NICHT getestet (scope-out):**
- Auto-Standing-Rampe nach Reset → Phase-13-Pendenz, siehe unten
- gait_node-Verhalten während Freeze (= heutiges Verhalten: gait_node
  publisht weiter Trajectorien, JTC schickt zu Plugin, Plugin verwirft
  und hält freeze. OK für jetzt)

### 0.5.3 Progress-Checkliste

```
- [ ] 0.5.1 hexapod_system.cpp::write() — safety_freeze_-Flag + Detektion
        + Hard-Stop-Logic + ERROR-Log + Clamp-zum-sicheren-Wert
- [ ] 0.5.2 hexapod_system.hpp — std::atomic<bool> safety_freeze_ Member
- [ ] 0.5.3 hexapod_system.cpp — Service-Server /hexapod_safety_reset
        (std_srvs/srv/Trigger)
- [ ] 0.5.4 Comment Z.657-660 aktualisiert: "firmware-clamp" entfernt,
        ersetzt durch "Plugin-side hard-clamp + safety_freeze"
- [ ] 0.5.5 6 neue Tests in test_hexapod_system.cpp (siehe Tabelle)
- [ ] 0.5.6 colcon test grün
- [ ] 0.5.7 Self-Review-Tabelle
```

### 0.5.4 Offene Punkte für User-Review

- **0.5-Q1:** State-Topic `/hexapod_safety_state` jetzt implementieren
  oder Phase 13? Empfehlung: jetzt nicht — gait_node-Integration kommt
  in Phase 13 zusammen mit Auto-Standing-Rampe.

---

## Stage 0.6 — IK-Joint-Limit-Check + sofortiger Freeze

> **Hintergrund:** [`leg_ik.py:17-18`](../src/hexapod_kinematics/hexapod_kinematics/leg_ik.py)
> dokumentiert explizit: „Keine Joint-Limit-Prüfung". IK kann rad-Werte
> außerhalb URDF-Limits ausgeben — die werden dann erst im Plugin-write()
> auf Stage 0.5 hart gestoppt. Stage 0.6 fügt die Frühwarnung in der
> Planning-Phase hinzu.

### 0.6.1 Logik-Skizze

**IK-Erweiterung (`leg_ik.py`):**
- Neue Funktion-Signatur: `leg_ik(x, y, z, leg_cfg, joint_limits=None)`
- Nach Berechnung von `(theta_coxa, theta_femur, theta_tibia)`: wenn
  `joint_limits` gesetzt + irgendein theta außerhalb → `IKError` werfen
  mit Detail (welcher Joint, welcher Wert, welches Limit)
- Backwards-Compat: ohne `joint_limits`-Arg → bisheriges lenient
  Verhalten

**Joint-Limits-Quelle:** URDF-Limits via `hexapod_kinematics.config.LegConfig`
oder direkt aus ROS-Parameter-Server in gait_node (latter wahrscheinlich
einfacher).

**gait_engine-Reaktion (User-Entscheidung 2026-05-24: sofortiger Freeze):**

Bei jedem IK-Joint-Limit-Error → gait_engine ruft sofort
`/hexapod_safety_freeze` Service (gegenstück zu `/hexapod_safety_reset`).
Plugin geht in Hard-Stop, alle Beine halten letzte Position. Recovery
über `/hexapod_safety_reset` wie in Stage 0.5.

**Warum N=1 statt graduierter Toleranz:** User-Wahl — Extremfall-
Sicherheit hat Vorrang vor transient-Glitch-Toleranz. Wenn IK ein
einziges Mal out-of-Joint-Limit rechnet, ist das ein echter
Konfig/Cal-Mismatch und darf nicht mit Hold-Position gemuted werden.

**Neuer Service `/hexapod_safety_freeze` (`std_srvs/Trigger`):** ergänzt
das Reset-Service-Paar aus Stage 0.5. User OR gait_engine kann den
Freeze auslösen.

### 0.6.2 Tests-Liste

| Test | Was |
|---|---|
| `LegIK.JointLimitViolationRaisesIKError` (pytest) | leg_ik mit joint_limits-Arg, rad außerhalb → IKError mit klarer Message |
| `LegIK.WithinJointLimitsReturnsSameAsBefore` (pytest) | Backwards-Compat: gleiches Bein, kein Joint-Limit-Bruch → identisches Ergebnis |
| `LegIK.NoJointLimitsArgIsLenient` (pytest) | Default-Verhalten unverändert |
| `GaitEngine.IKJointLimitErrorTriggersFreezeService` (pytest) | 1 IKError → safety_freeze-Service wird sofort gerufen |
| `SafetyFreezeService.SetsFreezeFlag` (gtest) | analog Reset-Service, setzt safety_freeze=true |

**NICHT getestet (scope-out):**
- Step-Truncate (Schritt verkürzen über ALLE Beine basierend auf
  limitierendem Bein) → Phase-13-Pendenz
- Auto-Recovery nach safety_freeze → Phase 13

### 0.6.3 Progress-Checkliste

```
- [ ] 0.6.1 leg_ik.py: joint_limits-Arg hinzufügen, Check nach
        rad-Berechnung, IKError mit Detail
- [ ] 0.6.2 hexapod_kinematics.config: LegConfig um optional
        joint_limits-Feld erweitern (joint_lower/joint_upper pro Joint)
- [ ] 0.6.3 gait_engine.py: bei IKError catch → ruft
        /hexapod_safety_freeze Service sofort (kein Counter)
- [ ] 0.6.4 gait_node.py: Lese URDF-Limits aus Param-Server, übergebe an
        gait_engine bei Init; Service-Client für /hexapod_safety_freeze
- [ ] 0.6.5 hexapod_system.cpp: zweiter Service /hexapod_safety_freeze
        (Pendant zu /hexapod_safety_reset aus Stage 0.5)
- [ ] 0.6.6 3 IK pytest-Tests + 2 gait_engine pytest-Tests + 1 gtest
- [ ] 0.6.7 colcon test grün (Sim-Tests dürfen nicht regressieren)
- [ ] 0.6.8 Self-Review-Tabelle
```

### 0.6.4 Offene Punkte für User-Review

- **0.6-Q1:** ✅ entschieden — N=1 (sofortiger Freeze beim ersten
  IK-Joint-Limit-Error). Extremfall-Sicherheit vor transient-Toleranz.
- **0.6-Q2:** Status-Topic `/gait_health` → Phase 13 (siehe Pendenzen).

---

## Phase-13-Pendenz aus Stage 0.5 + 0.6

Folgende Items werden in Stage 0.5/0.6 **nicht** implementiert und
müssen in Phase 13 (Voll-Bringup mit echtem Roboter) nachgeholt werden:

1. **`pose_standing`-PWMs definieren** via RViz-IK + HW-Verifikation
   (Cal-Doku [Sektion 3.4](servo_real_calibration_todos.md) hat Platzhalter).
2. **Auto-Standing-Rampe** in gait_node nach `/hexapod_safety_reset`:
   Hexapod fährt smooth zu `pose_standing` bevor cmd_vel akzeptiert
   wird. Plugin signalisiert „recovered"-State über Topic.
3. **Step-Truncate über alle Beine:** wenn IK an einem Bein out-of-range
   geht, berechnet gait_engine den maximal erreichbaren Schritt pro
   Bein, nimmt das Minimum als globalen step-scaler, alle Beine gehen
   synchron reduziert. Ersetzt Stage-0.6 Hold-Eskalation für Extremfälle.
4. **`/gait_health`-Topic** für Status-Sichtbarkeit (`OK`/`DEGRADED`/`FROZEN`).
5. **Plugin State-Topic `/hexapod_safety_state`** als Read-only Status
   für UI/Diagnose.

→ Diese Liste wandert in Memory-Eintrag
`project_phase13_safety_pendenzen.md` (anzulegen am Ende von Stage 0.6).

---

## Stage A — URDF-Macro-Refactor

### A.1 Logik-Skizze

**Aktueller Stand:**
- [`leg.xacro`](../src/hexapod_description/urdf/leg.xacro) Macro liest
  Joint-Limits aus globalen xacro:properties (`coxa_lower`, `coxa_upper`,
  `femur_lower`, `femur_upper`, `tibia_lower`, `tibia_upper`)
- Properties in [`hexapod_physical_properties.xacro`](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
  Z.31-36 — alle einheitlich ±1.57 (Coxa/Femur) bzw. ±1.50 (Tibia)
- Top-Level [`hexapod.urdf.xacro`](../src/hexapod_description/urdf/hexapod.urdf.xacro)
  ruft `xacro:leg id="N"` 6× auf, ohne Limit-Args

**Refactor-Ziel:**
- Macro `leg` um 6 optionale Params erweitern: `coxa_lower, coxa_upper,
  femur_lower, femur_upper, tibia_lower, tibia_upper`
- Default-Werte = aktuelle globale Properties (Backwards-Compat)
- Top-Level-Calls können (aber müssen nicht) pro-Bein individuelle
  Limits übergeben

**xacro-Syntax (params mit Defaults via `:=`):**
```xml
<xacro:macro name="leg"
    params="id mount_x mount_y mount_z mount_yaw
            coxa_lower:=^|${coxa_lower}|
            coxa_upper:=^|${coxa_upper}|
            femur_lower:=^|${femur_lower}|
            femur_upper:=^|${femur_upper}|
            tibia_lower:=^|${tibia_lower}|
            tibia_upper:=^|${tibia_upper}|">
```

Das `^|…|`-Pattern (xacro-Substitution mit fallback-property) ist
sicherer als nackte `${…}`-Defaults — wenn der Caller den Arg setzt,
gewinnt der Arg, sonst die globale Property.

> **Alternative (verworfen):** Macro nimmt nur ein einziges Joint-
> Limits-Dict per Pin. Vorteil: weniger Tipparbeit beim Caller.
> Nachteil: weniger explizit, xacro-Maps sind unpraktisch. Lieber
> 6 Args sichtbar.

**Migration des Top-Level:**
- Stage A: KEINE Änderung an `hexapod.urdf.xacro` (Defaults greifen)
- Stage D: pro-Bein-Limits eintragen

### A.2 Tests-Liste

| Test | Was | Begründung |
|---|---|---|
| `colcon build --packages-select hexapod_description` | xacro-Parse + URDF-Generation | Stage-A muss baubar bleiben |
| `xacro hexapod.urdf.xacro > /tmp/before.urdf` (vorher) und `xacro` mit refactored Macro → diff zeigt **keine Änderung** in Joint-Limits | Verifiziert dass Defaults exakt das alte Verhalten reproduzieren | |
| Bestehende `hexapod_description`-Tests | URDF-Konsistenz-Tests aus Phase 2/4 | |
| Sim-Smoke `ros2 launch hexapod_bringup sim.launch.py` | Hexapod spawnt in Stand-Pose, keine Joint-Errors | |

**NICHT getestet (scope-out):**
- Pro-Bein-Limit-Override (kommt in Stage D)
- HW-Plugin-Konsistenz (kommt in Stage E)

### A.3 Progress-Checkliste

```
- [ ] A.1 leg.xacro Macro um 6 optionale Args (coxa_lower/upper,
        femur_lower/upper, tibia_lower/upper) erweitern mit
        ^|${property}|-Default-Pattern
- [ ] A.2 colcon build hexapod_description grün
- [ ] A.3 xacro-Output-Diff vorher/nachher zeigt KEINE Änderung
        an Joint-Limits (Default-Backwards-Compat verifiziert)
- [ ] A.4 Sim-Smoke (hexapod spawnt normal in Stand-Pose)
- [ ] A.5 Self-Review-Tabelle
```

### A.4 Offene Punkte für User-Review

- **A-Q1:** Soll der `^|…|`-Default-Mechanismus genutzt werden, oder
  lieber nackte `${coxa_lower}`-Substitution? Beide funktionieren,
  `^|…|` ist robuster bei nested Macros. Empfehlung: `^|…|`.

---

## Stage B — servo_mapping.yaml-Eintrag

### B.1 Logik-Skizze

**Aktueller Stand:**
- [`src/hexapod_hardware/config/servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml)
  hat aus Phase 10 grobe Cal nur für leg_6 (Pin 15-17), Rest Defaults
- Plugin-Schema: `defaults`-Block + `servo2040_output_to_joint`-Map
  mit 18 Einträgen (Pins 0-17), jeder mit `joint`, `pulse_min`,
  `pulse_zero`, `pulse_max`, optional `direction` (default +1)

**Eintrag:**
- Pulse-Werte aus [Cal-Doku Tab. 3.2](servo_real_calibration_todos.md)
  übernehmen (numerisch sortiert für Plugin: min < zero < max)
- `direction: 1` für alle 18 Pins (Default — wird in Stage C pro Pin
  korrigiert)
- leg_6 bekommt die NEUEN Werte aus Cal-Session 2026-05-21
  (1290/1530/1870 statt Phase-10 1280/1550/1860)

**install→src-Sync nach Build:**
Plugin lädt YAML aus `install/`, aber Source-of-Truth ist `src/`.
Nach Edit in `src/` + `colcon build`: install-Copy ist aktuell.
Live-Edits via rqt schreiben über `/save_calibration` ins
install-Tree → muss zurück nach `src/` kopiert werden.

### B.2 Tests-Liste

| Test | Was | Begründung |
|---|---|---|
| `colcon build --packages-select hexapod_hardware` | YAML-Schema-Validierung (lädt im Plugin-Init) | |
| Bestehende Plugin-Tests | YAML-Loader-Tests | |
| Plugin-Start `ros2 launch hexapod_bringup real.launch.py` (HW angeschlossen) | keine Init-Errors, Pin-zu-Joint-Map korrekt | |

**NICHT getestet (scope-out):**
- Direction-Korrektheit (Stage C)
- URDF-Limits-Konsistenz (Stage D — bis dahin sind URDF-Limits noch ±1.57)

### B.3 Progress-Checkliste

```
- [ ] B.1 servo_mapping.yaml mit 18 PWM-Tripeln aus Cal-Doku Tab. 3.2,
        direction=1 für alle Pins, joint_name pro Pin gesetzt
- [ ] B.2 colcon build hexapod_hardware grün
- [ ] B.3 Plugin-Init-Smoke: real.launch.py startet ohne Schema-Errors
- [ ] B.4 Self-Review-Tabelle
```

### B.4 Offene Punkte für User-Review

- **B-Q1:** leg_6-Werte: alte Phase-10-Cal (1280/1550/1860) oder neue
  Session-Werte (1290/1530/1870)? Empfehlung: neue, weil aus
  konsistenter Mess-Session mit allen 6 Beinen.

---

## Stage C — Direction-Cal HW+Sim parallel

### C.1 Logik-Skizze

**Ziel:** für jeden der 18 Pins `direction_normal ∈ {+1, -1}` bestimmen,
sodass in RViz und HW dieselbe Joint-Bewegung sichtbar ist (sprich:
URDF-rad-Konvention = Mech-Rotation in derselben Richtung).

**Setup:**
- HW: `ros2 launch hexapod_bringup real.launch.py` (Plugin mit Stage-B
  servo_mapping.yaml, URDF-Limits noch ±1.57 aus Stage A Defaults)
- Sim parallel auf zweitem Workspace? Nein — die einfachere Variante
  ist `view.launch.py` (URDF in RViz ohne Sim-Physik) parallel zum
  Plugin. RViz visualisiert Joint-States, Plugin schreibt sie.

**Workflow pro Joint (54× total = 18 Pins × 3 Joints? Nein — 18 Pins =
18 Joints. Aber Cal pro Bein ist effizienter):**

Für jeden Joint (in Stage-empfohlener Reihenfolge leg_6 zuerst, dann
leg_1, leg_5, leg_4, leg_3, leg_2):

1. Joint-Command publishen: `ros2 topic pub --once /leg_N_controller/...`
   mit Trajectory `positions=[0.3, 0, 0]` für Coxa (oder analog Femur/Tibia)
2. **In RViz:** sichtbare Joint-Bewegung in welche Richtung?
3. **In HW (visuell):** Servo bewegt sich in welche physische Richtung?
4. **Vergleich:** wenn beide gleich → direction bleibt +1. Wenn
   verkehrt → direction auf -1 setzen via Live-Param:
   `ros2 param set /hexapodsystem pin_<N>.direction -1`
5. Re-Test rad=+0.3 → jetzt sollte HW und RViz übereinstimmen
6. `ros2 service call /save_calibration std_srvs/srv/Trigger`

**Reihenfolge leg_6 first:** Phase 10 hat leg_6 bereits walking-
verifiziert, dort kennen wir die korrekten directions als
Sanity-Anker. Wenn unsere Direction-Cal-Methodik für leg_6 die
Phase-10-direction-Werte reproduziert → Methode ist valide.

**Post-Cal install→src-Sync:**
```bash
cp install/hexapod_hardware/share/hexapod_hardware/config/servo_mapping.yaml \
   src/hexapod_hardware/config/servo_mapping.yaml
```

**Wieso vor Stage D:** wir brauchen die echten direction-Werte um in
Stage D zu entscheiden, OB die rad-Limits aus Cal-Doku Tab. 3.3 direkt
eintragbar sind (= bei direction=+1) oder ob Plugin-Fix sie korrekt
handhabt (= bei direction=-1, was nach Stage 0 der Fall ist).

**Wichtig (dank Stage-0-Fix):** mit gefixtem Plugin-Math können wir
in Stage D die PWM-zentrischen rad-Limits aus Cal-Doku Tab. 3.3
**direkt** eintragen — egal ob direction=+1 oder -1. Keine Spiegelung
im URDF nötig.

**Vorhersage Direction-Map** (nach systematischem Mount-Pattern aus
Cal-Doku Findings 3.5 Punkt 1/2): rechte Bein-Seite einheitlich, linke
Bein-Seite gespiegelt einheitlich. Statt 18× würfeln wird Stage C eine
„verify-the-mirror"-Übung.

### C.2 Tests-Liste

| Test | Was | Begründung |
|---|---|---|
| Pro Pin: rad=+0.3-Command in RViz und HW → gleiche Richtung | Direction-Cal-Done-Kriterium | |
| `/save_calibration` schreibt YAML mit `direction`-Map | Persistenz | |
| Roundtrip-Smoke nach Save: Plugin-Restart liest YAML zurück, direction stimmt | Persistenz-Verifikation | |

**NICHT getestet (scope-out):**
- Walking während Direction-Cal — nur Single-Joint-Commands
- Self-Collision-Verhalten (URDF noch ±1.57, Plugin clampt notfalls)

### C.3 Progress-Checkliste

```
- [ ] C.1 view.launch.py oder gleichwertiges Setup für RViz-Parallel
        zum Plugin
- [ ] C.2 Direction-Cal-Test-Anleitung (test_commands.md) geschrieben
        mit Topic-Publish-Snippets pro Bein
- [ ] C.3 leg_6 direction-Cal (3 Joints) — Sanity-Check gegen Phase 10
- [ ] C.4 leg_1 direction-Cal (3 Joints)
- [ ] C.5 leg_5 direction-Cal (3 Joints)
- [ ] C.6 leg_4 direction-Cal (3 Joints)
- [ ] C.7 leg_3 direction-Cal (3 Joints)
- [ ] C.8 leg_2 direction-Cal (3 Joints)
- [ ] C.9 /save_calibration → install→src-Sync
- [ ] C.10 Plugin-Restart, Roundtrip-Smoke der direction-Werte
- [ ] C.11 Self-Review-Tabelle (auch: welche Beine waren direction=-1?
        Pattern dokumentieren)
```

### C.4 Offene Punkte für User-Review

- **C-Q1:** Soll `view.launch.py` als RViz-Setup reichen, oder lieber
  parallel `sim.launch.py` (mit Gazebo)? Empfehlung: `view.launch.py`
  — Gazebo-Physik ist hier irrelevant, nur Joint-Sichtbarkeit zählt.
- **C-Q2:** Joint-Command für Direction-Test — Magnitude +0.3 rad
  ausreichend, oder größer? Empfehlung: +0.3 rad ist gut sichtbar
  und sicher innerhalb jedem Cal-Range.
- **C-Q3:** Reihenfolge der Beine fest leg_6→1→5→4→3→2 oder flexibel?
  Empfehlung: leg_6 zwingend zuerst (Phase-10-Anker), Rest egal.

---

## Stage D — URDF mit finalen rad-Limits

### D.1 Logik-Skizze

**Eintrag direkt aus Cal-Doku Tab. 3.3:** die PWM-zentrisch berechneten
rad-Limits (joint_lower/joint_upper aus `(pulse_X − pulse_zero) ×
0.00237`) gehen 1:1 als `<limit lower upper>` ins URDF. KEINE
Spiegelung für direction=-1 nötig — dank Stage-0-Fix handhabt das
Plugin den direction-Flip korrekt mit PWM-zentrischen Limits.

**Konkret im Top-Level:**
```xml
<xacro:leg id="1"
           mount_x="${ body_length/2}" mount_y="${-body_width/2}"
           mount_z="${leg_mount_z}"    mount_yaw="${-pi/4}"
           coxa_lower="-0.747" coxa_upper="+0.569"
           femur_lower="-1.529" femur_upper="+1.565"
           tibia_lower="-1.920" tibia_upper="+1.197"/>
<!-- ... analog für leg_2..leg_6 ... -->
```

Alle 18 rad-Paare sind in Cal-Doku Tab. 3.3 vorberechnet.

**Validation:** xacro-Parse + URDF-Generate. `colcon test` ruft die
bestehenden `RejectsSwappedJointLimits`/`RejectsEqualJointLimits`-Tests
auf — falls ich versehentlich `lower > upper` eintrage, scheitert
der Build.

### D.2 Tests-Liste

| Test | Was | Begründung |
|---|---|---|
| `colcon build --packages-select hexapod_description hexapod_hardware` | URDF-Parse + Plugin-set_joint_limits | |
| Plugin-Test `RejectsSwappedJointLimits` | Sanity-Net falls Eintragefehler | |
| Sim-Spawn `sim.launch.py` | Hexapod in Stand-Pose, alle 6 Beine sichtbar | |
| Manueller URDF-Check via xacro-Output-Diff | alle 18 `<limit>`-Werte stimmen mit Cal-Doku Tab. 3.3 | |

**NICHT getestet (scope-out):**
- Walking-Verhalten — kommt in Stage E

### D.3 Progress-Checkliste

```
- [ ] D.1 hexapod.urdf.xacro: 6× xacro:leg-Call mit individuellen
        coxa/femur/tibia_lower/upper-Args (18 Werte aus Cal-Doku Tab. 3.3)
- [ ] D.2 colcon build hexapod_description + hexapod_hardware grün
- [ ] D.3 xacro-Output-Diff: alle 18 <limit lower upper>-Paare
        stimmen mit Cal-Doku Tab. 3.3
- [ ] D.4 Sim-Spawn Smoke (Stand-Pose visuell ok)
- [ ] D.5 Self-Review-Tabelle
```

### D.4 Offene Punkte für User-Review

- **D-Q1:** rad-Werte aus Cal-Doku Tab. 3.3 nutzen wir auf 3
  Nachkommastellen. Ausreichend Präzision? Empfehlung: ja, entspricht
  ±0.0005 rad ≈ 0.03° = unter Servo-Toleranz.
- **D-Q2:** Falls in Stage C eine mech-Stop-Nachjustierung erfolgt:
  Wert in Cal-Doku Tab. 3.2/3.3 mit-syncen? Empfehlung: ja, Cal-Doku
  ist Single-Source-of-Truth.

---

## Stage E — Sim-Verifikation + Walking aufgebockt

### E.1 Logik-Skizze

**Sim-Verifikation (Phase-4 in der Original-Doku):**
1. `sim.launch.py` — Hexapod spawnt, Stand-Pose visual normal
2. `gait_node` mit `defensive_walk.yaml`-Preset starten
3. `ros2 topic pub --rate 10 /cmd_vel ... linear.x=0.02`
4. Hexapod bewegt sich, **keine `IKError`** im gait_node-Terminal
5. Walking sieht stabil aus (Tripod-Rhythmus, keine Glitches)

**Walking aufgebockt (Phase-5+6 in der Original-Doku):**
1. HW: `real.launch.py` mit Stage-D-URDF + Stage-C-direction-Cal
2. Single-Joint-Commands pro Bein (rad=+0.3, -0.3) → Servo bewegt smooth
3. Ein Bein komplett (3 Joints koordiniert)
4. Mehrere Beine simultan
5. gait_node starten, `defensive_walk`, `cmd_vel x=0.02`
6. Alle 6 Beine im Tripod, keine Glitches, keine IK-Errors
7. Tempo schrittweise hoch (0.02 → 0.04 → 0.05)

**Erst NACH erfolgreichem Aufgebockt-Walking:** Hexapod absetzen für
bodengebundenes Walking (außerhalb dieser Doku — gehört in
Phase-13-Voll-Bringup).

### E.2 Tests-Liste

| Test | Was | Begründung |
|---|---|---|
| Sim visual: Stand-Pose normal | Default-Doku-Anforderung | |
| Sim Walking-Smoke `cmd_vel x=0.02` | keine IK-Errors, Tripod sichtbar | |
| HW Single-Joint `±0.3 rad` pro Bein | Direction-Cal verifiziert in voller Pipeline | |
| HW gait_node + cmd_vel | aufgebockt Walking, alle 6 Beine | |

**NICHT getestet (scope-out):**
- Bodengebundenes Walking (Phase 13)
- Body-Tilt, Stand-Pose-Variation (Phase 13)
- Vel/Accel-Limits unter Last (Memory `project_phase10_real_yaml_vel_limits.md`)

### E.3 Progress-Checkliste

```
- [ ] E.1 servo_real_cal_test_commands.md mit konkreten Topic-
        Publish-Snippets, gait-Launch-Befehlen, Visual-Check-Liste
- [ ] E.2 Sim-Verifikation: visual + Walking-Smoke
- [ ] E.3 HW Single-Joint pro Bein (leg_6 → leg_1 → ...)
- [ ] E.4 HW komplettes Bein (3 Joints koordiniert), leg_6
- [ ] E.5 HW alle 6 Beine, gait_node, cmd_vel x=0.02 aufgebockt
- [ ] E.6 Tempo-Hoch (0.02 → 0.04 → 0.05) ohne Glitches
- [ ] E.7 Self-Review-Tabelle (Walking-Performance,
        Range-Nutzungs-Hinweise für Phase 13)
- [ ] E.8 Memory-Eintrag: „Hexapod-Hardware-Cal 2026-05-XX
        erfolgreich, alle 18 Servos calibrated"
```

### E.4 Offene Punkte für User-Review

- **E-Q1:** Welches Walking-Preset für ersten HW-Test? Empfehlung:
  `defensive_walk.yaml` (konservativ, kurze Schritte).
- **E-Q2:** Stride-Length-Reduktion für Mittel-Beine (leg_2/5 haben
  nur ~50° Coxa-Range)? Empfehlung: gait_node nutzt eh `step_length_max`
  global — wenn Mittel-Beine schaffen, schaffen alle. Erst bei IK-Errors
  reduzieren.
- **E-Q3:** Logging-Strategie bei Walking-Test? Empfehlung:
  rosbag-Aufnahme während aufgebockt, falls Issues nachträglich
  analysierbar.

---

## 3. Cross-Stage offene Punkte

- **X-Q1:** Memory-Update nach erfolgreicher Cal — neue Memory-Datei
  „Hexapod-Hardware-Cal-2026-05-XX abgeschlossen" mit direction-Map,
  finalen rad-Limits, Walking-Notes. Empfehlung: ja, als
  `project_servo_real_cal_done.md`.
- **X-Q2:** Soll diese Cal-Arbeit als Phase-13-Stage-Voraussetzung
  notiert werden? Empfehlung: ja, in PHASE.md erweitern dass
  Phase 13 (Voll-Bringup) diese Cal-Pipeline als Done-Kriterium hat.
- **X-Q3:** Falls Stage E Walking-Probleme zeigt die nicht auf
  Cal-Werte zurückführbar sind: Plan ad-hoc erweitern oder
  Phase-13-Material? Empfehlung: case-by-case; kleine Tunings hier,
  größere Refactors (z.B. Pose-Management) bleiben Phase 13.

---

## 4. Erwartete Reihenfolge & Session-Plan

**Session 1 (Claude-Code-Arbeit, ohne HW):**
- Stage 0 (Plugin-Math-Fix) → User-Freigabe → Implementation
- Stage A (URDF-Macro-Refactor) → Implementation
- Stage B (servo_mapping.yaml-Eintrag) → Implementation
- Stage D (URDF-Limits eintragen) — als „Trockenlauf" mit
  PWM-zentrischen Werten; wird in Stage C ggf. nicht verändert,
  aber direction-Map kommt erst danach

**Session 2 (User + Claude, mit HW):**
- Stage C (Direction-Cal) — interaktiv mit RViz + HW
- Stage E (Sim-Verifikation + Walking) — interaktiv

**Hinweis:** Stage D kann tatsächlich VOR Stage C laufen, weil
die rad-Werte aus Cal-Doku Tab. 3.3 schon endgültig sind
(Plugin-Fix macht direction-Spiegelung transparent). Falls Stage C
aber beim Direction-Cal feststellt dass irgendein Cal-Wert revidiert
werden muss (z.B. neue mech-Anschlag-Entdeckung), würde Stage D
nochmal angefasst.

---

## 5. Was bewusst NICHT in diesem Plan ist

- **Pose-Management (Initial/Stand/Shutdown):** Phase-13-Material,
  siehe Memory `project_phase13_initial_pose_presets.md`. Cal-Plan
  hier fokussiert auf rad↔µs-Konsistenz.
- **Sym-Kürzung der rad-Range:** durch Stage 0 (Plugin-Math-Fix)
  obsolet geworden. Volle asymm Range nutzbar.
- **Vel/Accel-Limit-Tuning unter Last:** Memory `project_phase10_real_yaml_vel_limits.md`,
  Phase-13-Pendenz.
- **Body-Tilt/Crouch/erweiterte Stand-Posen:** Phase 13.
- **Auto-Cal-Tool für die anderen 15 Servos:** Phase 13 falls jemals
  gewollt; aktuell ist die manuelle Cal-Doku komplett.

---

## 6. Referenz-Dokumente

- [`servo_real_calibration_todos.md`](servo_real_calibration_todos.md)
  — Cal-Daten + Findings + Strategie-Diskussion
- [`docs/00_conventions.md`](../docs/00_conventions.md) §11.4 —
  Joint-Limits-Konvention
- [`calibration.cpp`](../src/hexapod_hardware/src/calibration.cpp)
  Z.176-222 — Plugin-Math (vor Stage-0-Fix)
- [`leg.xacro`](../src/hexapod_description/urdf/leg.xacro) — Bein-Macro
- [`hexapod_physical_properties.xacro`](../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
  — globale Joint-Limit-Defaults (bleiben unverändert)
- Memory-Einträge bleiben relevant: `project_hexapod_servo_models.md`,
  `project_phase13_initial_pose_presets.md`, `feedback_user_does_commits.md`,
  `feedback_decision_alternatives_log.md`

---

**Erstellt 2026-05-24 nach User-Wahl Option B (Plugin-Math-Fix) für F10.
Plan ersetzt nicht servo_real_calibration_todos.md, sondern setzt es um.**
