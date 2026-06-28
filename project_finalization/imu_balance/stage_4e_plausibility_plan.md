# Stufe 4 / S4-5 — Plausibilität + Sensor-Fault-Fail-Safe

> Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5). **Der letzte
> geplante Stufe-4-Baustein.** **Ziel:** ein **defekter Fußkontakt-Sensor** (klemmt auf „Kontakt"
> oder „kein Kontakt") darf das Verhalten **nicht** verschlechtern → unplausible Signale erkennen →
> den betroffenen Sensor **flaggen + ignorieren** (Bein fällt auf Open-Loop zurück) + **warnen**.
> Leitprinzip (Umbrella §2.D): **Taster = Optimierung, nie load-bearing.**
>
> **Status: 🟡 §4-Freigabe erteilt → Implementierung steht aus.** §4: Plan → **User-Freigabe ✅** →
> Code → Test → Self-Review. **§4-Entscheide:** Scope **stuck-on + dead** · Schwellen apex_band
> **0.3/0.7** / apex_fault_count **5** / dead_cycles **2** · Reaktion **ignorieren + warnen** ·
> **latched** · Sim-**Inject-Hook ja**. Voraussetzung: S4-1/S4-2/S4-4/S4-6 🟢.

---

## 0. Kontext + warum das nötig ist

- Der gz-Sim-Sensor ist **zuverlässig** (`miss 0`) → der Sim-Nutzen ist klein; **S4-5 ist
  HW-gerichtet/defensiv** (echte Microswitches prellen/klemmen/sterben, Phase E2).
- **Gefahr ohne S4-5:** ein **stuck-on**-Sensor (klemmt „Kontakt") korrumpiert beide bisherigen
  Stufen — S4-2 friert den Touchdown zu früh ein (Phantom-Kontakt), und S4-4 hält das Bein für
  „immer gestützt" → **kein Freeze über einer Kante** (gefährlich). Ein **stuck-off/toter** Sensor
  ist weniger gefährlich (Bein bekommt nur keine Optimierung → Open-Loop, der sichere Default), kann
  aber einen **Fehl-Freeze** in S4-4 auslösen (scheinbarer Halt-Verlust auf gutem Boden).
- **Plausibilitäts-Anker = die Gait-Phase** (geometrische Grundwahrheit): im **Schwung-Apex** ist
  der Fuß zwingend in der Luft → `contact=True` dort ist **physikalisch unmöglich** = Sensor-Fault
  (eindeutig). „Kein Touchdown über mehrere Cycles" beim Laufen = toter Sensor (klar). Der
  **mehrdeutige** Fall (kein Kontakt in belasteter Stance) ist **entweder** echter Halt-Verlust
  (→ S4-4-Freeze, sicher) **oder** stuck-off — den lassen wir bewusst beim sicheren S4-4-Freeze.

## 1. Logik-Skizze + Pseudocode

### 1.1 `SensorHealthMonitor` (ROS-frei, wie `TipMonitor`/`SupportMonitor`)
Per-Bein-Fault-Erkennung mit Leaky-/Entprell-Zählern + Flag (latched bis `reset()`).

```
class SensorHealthMonitor(apex_lo, apex_hi, apex_fault_count, dead_ticks):
  per leg: apex_hits=0;  ticks_since_td=0;  prev_contact=False;  faulty=False; reason=None

  reset(): alle Zähler/Flags 0 / None / False

  update(legs):   # legs: leg_id -> (is_swing, local_phase, contact)
    for leg in 1..6:
      is_swing, ph, contact = legs[leg]
      # --- stuck-on: Kontakt im Schwung-Apex (geometrisch unmöglich) ---
      in_apex = is_swing and (apex_lo <= ph <= apex_hi)
      if in_apex and contact:   apex_hits += 1
      elif in_apex:             apex_hits = max(0, apex_hits - 1)   # leaky
      if apex_hits >= apex_fault_count:  faulty=True; reason='stuck_on'
      # --- dead/stuck-off: kein Touchdown (steigende Flanke in Stance) über dead_ticks ---
      td_edge = (not is_swing) and contact and (not prev_contact)
      if td_edge:    ticks_since_td = 0
      else:          ticks_since_td += 1
      if ticks_since_td >= dead_ticks:   faulty=True; reason='dead'
      prev_contact = contact
    return {leg: (faulty, reason)}   # faulty latched bis reset()
```

### 1.2 Node-Glue (`gait_node`) — flaggen → ignorieren → warnen
- Pro Tick (WALKING): `legs = {leg_id: (is_swing, local_phase, contact)}` aus
  `engine.leg_gait_states(t)` + `self._foot_contact`. `SensorHealthMonitor.update(legs)`.
  (Der Monitor arbeitet in **Ticks**; `dead_ticks = sensor_dead_cycles · cycle_time · tick_rate`
  wird vom Node beim Bauen/Rebuild übergeben — Param ist cycle_time-unabhängig in Cycles.)
- **Reaktion pro geflaggtem Bein (graceful degradation):** das Bein wird für **beide** bisherigen
  Stufen **maskiert** (sein `contact` ist nicht vertrauenswürdig):
  - **S4-2 adaptiv:** geflaggtes Bein → **kein** adaptiver Touchdown (nominaler `swing_traj`,
    Open-Loop) — der Phantom-/Fehl-Kontakt darf das Fuß-z nicht steuern.
  - **S4-4 slip:** geflaggtes Bein **aus der Stütz-Verlust-Zählung ausgeschlossen** (weder „lost"
    noch garantiert „gestützt") — ein toter Sensor löst keinen Fehl-Freeze aus, ein stuck-on-Sensor
    täuscht keine Stütze vor. Backstop bleibt der Stufe-1-Tip + die **anderen** Beine.
  - **Warnen:** throttled WARN-Log `Sensor-Fault Bein N (stuck_on|dead) — ignoriere Kontakt`.
- Umsetzung der Maskierung: der Node führt ein `self._sensor_faulty[leg]`-Set; beim Durchreichen der
  Kontakte an Engine (`set_foot_contacts`) und an den `SupportMonitor` werden geflaggte Beine
  neutralisiert (Engine: adaptiv-aus für das Bein; Support: übersprungen).
- **Gating:** nur in WALKING auswerten (sonst reset). Default `sensor_plausibility_enable` **false**.
- **Sim-Test-Hook (optional, §4):** `sensor_fault_inject` (Bein-ID + Modus stuck_on/stuck_off) zwingt
  den gecachten Kontakt eines Beins auf einen Klemm-Wert → erlaubt, die Erkennung in der zuverlässigen
  Sim zu provozieren.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: stuck-on** | Kontakt im Apex-Band über `apex_fault_count` → faulty('stuck_on'); sauberer Apex → nicht | leaky-Sequenz |
| **Unit: dead** | kein Touchdown über `dead_ticks` (Bein cycelt) → faulty('dead'); regelmäßiger Touchdown → nicht | Sequenz |
| **Unit: gesund** | normaler Swing/Stance mit plausiblem Kontakt → nie faulty | Regression |
| **Unit: Latch + reset** | faulty bleibt bis `reset()` | Latch |
| **Node: Maskierung** | geflaggtes Bein → adaptiv-aus + aus Support-Zählung; Warn-Log; Params live | rclpy-Smoke |
| **Node: fault-inject** | inject stuck_on → Bein wird geflaggt + maskiert | Smoke |
| colcon + Lint | grün | 0 Fehler |
| **Sim (User) stuck-on** | inject stuck_on an einem Bein → WARN + dieses Bein ignoriert (kein Fehl-Freeze-Suppress, kein z-Phantom); Lauf bleibt stabil | inject + beobachten |
| **Sim (User) dead** | inject stuck_off → WARN + Bein auf Open-Loop, **kein** Fehl-Freeze | inject + beobachten |

**Bewusst NICHT (→ später):** Recovery/Un-Flag bei wieder-gesundem Sensor (v1 latched bis
State-Wechsel); mehrdeutiger mid-Stance-Gap als Fault (bleibt S4-4-Freeze); echte HW-Taster-Faults
(E2); Redundanz/Voting mehrerer Sensoren.

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-5:
- [ ] S4-5.1 SensorHealthMonitor (ROS-frei): stuck-on (Apex-Kontakt, leaky) + dead (kein Touchdown über dead_ticks) + Latch + reset
- [ ] S4-5.2 gait_node: Monitor-Wiring (WALKING-Gating) + Maskierung geflaggter Beine (S4-2 adaptiv-aus + S4-4 ausgeschlossen) + throttled WARN
- [ ] S4-5.3 Sim-Test-Hook sensor_fault_inject (Bein + stuck_on/stuck_off, Default aus, klar Debug)
- [ ] S4-5.4 Params: sensor_plausibility_enable (false), sensor_apex_band_low/high (0.3/0.7), sensor_apex_fault_count (5), sensor_dead_cycles (2) — alle live, validiert, Monitor-Rebuild
- [ ] S4-5.5 Unit-Tests (stuck-on, dead, gesund, Latch) + Node-Smoke (Maskierung, inject)
- [ ] S4-5.6 colcon test + Lint grün
- [ ] S4-5.7 README/Konzept (Sensor-Health, Plausibilitäts-Anker Gait-Phase, Maskierung, Params)
- [ ] S4-5.8 Test-Doku stage_4e_plausibility_test_commands.md (inject stuck_on/stuck_off) + Sim-Verify durch User
- [ ] S4-5.9 kritische Self-Review-Tabelle
```

## 4. User-Review-Entscheidungen (vor Code) — ✅ ALLE FREIGEGEBEN

1. **Scope v1 = stuck-on UND dead.** ✅ Begründung: ein einzelner toter Schalter (häufiger HW-Defekt)
   würde S4-4 sonst per Dauer-Fehl-Freeze unbrauchbar machen → dead-Behandlung schließt das tote
   Bein aus → Roboter bleibt fahrbar.
2. **Schwellen (live tunbar):** `sensor_apex_band_low/high` = **0.3 / 0.7** · `sensor_apex_fault_count`
   = **5** · `sensor_dead_cycles` = **2** (als **Cycles**, der Node rechnet via `cycle_time·tick_rate`
   in Ticks um — cycle_time-unabhängig, anders als ein roher Tick-Wert). ✅
3. **Reaktion = ignorieren + warnen** (Open-Loop-Degradation, **kein** Freeze). ✅ Prinzip „Taster =
   Optimierung, nie load-bearing" — ein Sensor-Fault degradiert, stoppt nicht. Stopp-Schutz bleibt
   Stufe-1-Tip + die gesunden Beine.
4. **Latched bis State-Wechsel** (Auto-Recovery → später S4-5b). ✅ Ein einmal implausibler Sensor ist
   verdächtig → bis zum sauberen Neustart maskiert; die **WARN-Logs sind trackbar**, so dass man
   intermittierende Faults beobachten kann, bevor man Auto-Recovery baut.
5. **Sim-Test-Hook `sensor_fault_inject` = ja** (Bein-ID + stuck_on/stuck_off, Default aus, klar
   Debug). ✅ Einzige Möglichkeit, S4-5 in der fault-freien Sim zu verifizieren.

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt (Vorschlag) | Verworfen | Warum |
|---|---|---|---|
| Plausibilitäts-Anker | **Gait-Phase** (Apex = Fuß oben) | reine Kontakt-Statistik | geometrische Grundwahrheit, eindeutig (stuck-on) |
| Reaktion | **ignorieren + warnen** (Open-Loop) | Freeze | Taster = Optimierung, nie load-bearing; Fault darf nicht stoppen |
| mehrdeutiger mid-Stance-Gap | **als S4-4-Freeze behandeln** (nicht als Fault) | als Fault flaggen | sicher: echter Halt-Verlust > Sensor-Annahme |
| Klasse | **SensorHealthMonitor (ROS-frei)** | im Node | testbar wie Tip/Support |
| Maskierung | **S4-2 adaptiv-aus + S4-4 ausgeschlossen** | nur eines | beide werden vom Fault korrumpiert |
| Test-Hook | **sensor_fault_inject** | nur Unit | Sim ist fault-frei → sonst nicht live verifizierbar |

## 6. Handoff / Code-Anker
- Vorlagen: `tip_monitor.py` / `support_monitor.py` (ROS-frei, Entprellung/Latch/reset) +
  `contact_diagnostic.py` (zählt bereits `apex_false`/`missed`/`touchdowns` — gleiche Signale).
- Node: `_update_foot_contacts` / `_update_support` (Tick-Hooks, Phase via `leg_gait_states`,
  Kontakt-Cache `_foot_contact`); `set_foot_contacts` (Maskierung an Engine);
  `engine.adaptive_touchdown_enable` (pro Bein lässt sich das nicht — also: maskiertes Bein über
  einen per-Bein-„contact=False + adaptiv-neutral"-Pfad; im Code-Schritt klären, ob per-Bein-Flag
  in der Engine nötig ist oder Maskierung über den durchgereichten Kontakt reicht).
- Reaktion-Warnung: throttled WARN (wie `cmd_vel clamped`).
- Sim: `sensor_fault_inject`-Param + `ramp_walk`/`step_walk` zum Beobachten.

## 7. Doku-Hygiene bei Abschluss
- `imu_balance_progress.md` (S4-5-Checkliste + Post-Review; Umbrella S4-5 → 🟢; **Stufe-4-Kern
  komplett**), `hexapod_gait/README.md`, `ai_navigation.md`, Memory
  `project_a5_stage4_adaptive_touchdown`.
