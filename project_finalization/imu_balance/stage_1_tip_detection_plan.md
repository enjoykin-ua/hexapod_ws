# Stufe 1 — Kipp-/Sturz-Erkennung → Safe-State

> Stufe 1 von Block A5 ([Master](00_imu_balance_plan.md)). **Ziel:** erster
> *Konsument* der IMU — ein Schwellwert-Wächter, der bei zu großer Kippung/zu
> schnellem Kippen einen **Safe-State** auslöst. Billig, sicherheitsrelevant, und
> das **Sicherheitsnetz**, bevor Stufe 2 anfängt, Körper-Rotationen zu kommandieren.
> Plan nach CLAUDE.md §4. Test-Befehle: [`stage_1_tip_detection_test_commands.md`](stage_1_tip_detection_test_commands.md).
>
> **Status: 🟢 fertig (Sim verifiziert).** Die `[ ]` in §3 sind das **Template**
> (§4-Konvention: abgehakt wird im Progress-File) — der echte Stand (alle `1.x`
> `[x]` + Self-Review) steht in [`imu_balance_progress.md`](imu_balance_progress.md).

---

## 1. Logik-Skizze / Pseudocode

- **Eingang:** `/imu/data` → `|roll|`, `|pitch|` (Kippung gegen Horizontal) +
  `|Gyro-Rate|` (schnelles Kippen). roll/pitch aus Quaternion (wie `imu_monitor`,
  Stufe 0).
- **Schwellen (Parameter):** `tip_angle_warn`, `tip_angle_crit`, `tip_rate_crit`.
- **Entprellung/Hysterese:** Auslösen erst nach **N aufeinanderfolgenden Ticks**
  über Schwelle (gegen Fehlalarm durch Gang-Ripple); Rückfall mit Hysterese-Marge.
- **Reaktion (Entscheidung offen, §4) — nutzt VORHANDENE Mechanik, nicht neu
  erfinden:** bei `crit` → Safe-State über `/hexapod_safety_freeze` **oder** die
  **B1-Hinsetz-Sequenz** (senkt CoG — am Hang oft sicherer als freeze) **oder**
  gestaffelt (`warn` → stoppen/langsamer, `crit` → hinsetzen).
- **Ein Safe-State-Arbiter:** konsistent mit dem bestehenden `_check_comms_loss`-
  Fail-safe — Kipp-Trigger und Comms-Loss dürfen sich **nicht** widersprechen
  (gemeinsamer Eintritts-Pfad, nicht zwei konkurrierende Auslöser).
- **Edge-getriggert/gelatcht:** einmal feuern (Muster `_shutdown_latched`), nicht
  jeden Tick → kein Reaktions-Spam, definierte Single-Action.
- **State-Gating (User-Punkt 4):** Auswertung **nur in `STANDING`/`WALKING`**. In
  `STARTUP_RAMP` / `CARTESIAN_STANDUP` / `REPOSITION` / `SITDOWN_*` / `STANCE_SWITCH`
  / `SHOW_*` **ausgesetzt** (Körper kippt/bewegt sich dort *gewollt*) + Monitor-Reset.
- **Ort:** im `gait_node` (hat State + Service-Clients + Tick schon); reine
  Schwellen-/Hysterese-Logik als **testbare Funktion/Klasse `TipMonitor`** (ohne
  ROS) — gleiche Trennung wie `BalanceController` (Master D1).

Pseudocode (im Tick, nach `compute_joint_angles`):

```
if engine.state in {STANDING, WALKING}:
    level = TipMonitor.update(roll, pitch, gyro_rate, dt)   # NONE | WARN | CRIT (entprellt)
    if level == CRIT and not safe_state_latched:
        enter_safe_state(reason="tip")   # GEMEINSAMER Pfad mit comms-loss; einmalig
    elif level == WARN:
        ...                              # (optional) stoppen/langsamer
else:
    TipMonitor.reset()                   # Gating: nicht auswerten, Zustand klar
```

---

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done wenn |
|---|---|---|
| **T1.1** | über `crit` → Reaktion feuert | Erkennung + Aktion | Kippen über Schwelle in Sim → Safe-State ausgelöst |
| **T1.2** | unter Schwelle → nichts | kein Fehlalarm | normales Stehen / leichtes Wackeln → keine Reaktion |
| **T1.3** | Gang-Ripple kein Fehlalarm | Hysterese/Entprellung wirkt | normales Laufen über mehrere Zyklen → keine Reaktion |
| **T1.4** | Gating beim Aufstehen | State-Gate wirkt | während `CARTESIAN_STANDUP`/`REPOSITION` (gewolltes Kippen) → **keine** Reaktion |
| **T1.5** | Rate-Trigger | schnelles Kippen erkannt | schneller Stoß > `tip_rate_crit` → Reaktion auch unter Winkel-Schwelle |
| **T1.6** | Unit-Tests Schwellen-Logik | reine Logik isoliert | pytest grün (Schwellen, Hysterese, Gating, Reset, Edge/Latch) |

**Bewusst NICHT getestet (scope-out):** Leveling/Korrektur (Stufe 2),
Wiederaufstehen nach Sturz (Block E1), HW-Feintuning der Schwellen (in Gazebo grob,
HW fein), gewollte Hangneigung als Sonderfall (→ Stufe 3, siehe §4).

---

## 3. Progress-Checkliste (→ [`imu_balance_progress.md`](imu_balance_progress.md))

```
- [ ] 1.1 TipMonitor: Schwellen-/Hysterese-/Edge-Logik als testbare Funktion/Klasse (ohne ROS)
- [ ] 1.2 /imu/data-Subscriber in gait_node (sensor-QoS) + roll/pitch/gyro-Ableitung
- [ ] 1.3 State-Gating (Auswertung nur in STANDING/WALKING, sonst reset)
- [ ] 1.4 Reaktion ueber VORHANDENE Safe-State-Mechanik (/hexapod_safety_freeze | B1-Sit), edge/latch, EIN Arbiter mit comms-loss - freeze/sit/gestaffelt nach §4
- [ ] 1.5 Parameter deklariert + dokumentiert (tip_angle_warn/crit, tip_rate_crit, debounce_ticks)
- [ ] 1.6 T1.1-T1.6 grün (Unit + Sim)
- [ ] 1.7 README/Konzept-Update (Safe-State-Verhalten, Schwellen, Gating, Arbiter)
- [ ] 1.8 colcon test + Lint grün
- [ ] 1.9 kritische Self-Review-Tabelle
```

---

## 4. Entscheidungen + Offene Punkte

**Entschieden (User-Freigabe):**
- **Reaktion:** gestaffelt — `warn` (15°) → `cmd_vel=0` (stoppen/setteln); `crit`
  (25° **oder** 80°/s) → `/hexapod_safety_freeze` (hart, gelatcht, einmalig). **Kein
  Hinsetzen** (am Hang würde die Sitz-Bewegung selbst den CoG über die bergab-Kante
  schieben → kippt beim Hinsetzen).
- **Startwerte:** `tip_angle_warn_deg=15`, `tip_angle_crit_deg=25`,
  `tip_rate_crit_dps=80`, `tip_debounce_ticks=5` (0.1 s). Init-only; Winkel-Feintuning
  auf der Schräge in Stufe 2 (+ HW). Flach laufen roll/pitch bei ±0.1° → viel Marge.
- **Ort:** `gait_node` (State + Tick + Service-Clients); Logik ROS-frei in `TipMonitor`.

**Offen (später):**
- **Wechselwirkung mit Hang (Stufe 3):** dann ist gewollte Körperneigung normal →
  Schwelle relativ zum *gelevelten Soll* statt absolut. Für Stufe 1 (flach) absolut ok.
- **Live-Tuning:** tip-Params sind Init-only (nicht in `_on_param_change`); bei Bedarf
  in Stufe 2 fürs Rampen-Tuning live-schaltbar machen.

---

## 5. Design-Entscheidungen (Stufe 1)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Ort | `gait_node` | eigener Safety-Node | gait_node hat State + Tick + Service-Clients schon; eigener Node müsste State spiegeln. |
| Schwellen-Logik | ROS-freie Klasse `TipMonitor` | inline im Tick | unit-testbar, wie `BalanceController`/Kinematik. |
| Auslöse-Art | edge-getriggert/gelatcht | level (jeden Tick) | verhindert Reaktions-Spam + garantiert Single-Action. |
| Safe-State | WARN→`cmd_vel=0`, CRIT→vorhandenes `/hexapod_safety_freeze` | Hinsetzen (B1) als crit-Reaktion | Sit würde am Hang selbst kippen (CoG über bergab-Kante); freeze ist hart + universell aus jedem State. |
| Bezugsgröße | absolute Kippung (Stufe 1, flach) | relativ-zum-Soll | relativ erst mit Leveling sinnvoll (Stufe 3). |
