# Stufe 4 / S4-4 — Slip / Kontaktverlust → Safe-State (Freeze)

> Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5).
> **Ziel:** ein **Stütz-Fuß ohne Halt** (über eine Kante/Abgrund oder weggerutscht) wird erkannt →
> **Freeze** (Safe-State, wie Stufe 1), bevor der Roboter kippt oder von einer Kante läuft.
>
> **Status: ⚪ offen → Plan freigegeben (User: cliff_depth „mittel" 0.03, Reaktion = nur Freeze,
> live tunbar).** §4: Plan → Freigabe ✅ → Code → Test → Self-Review.
> Voraussetzung: S4-1/S4-2/S4-6 🟢.

---

## 0. Kontext + Kern-Idee

- **Symptom = „ein belasteter Fuß meldet keinen Kontakt".** Zwei Ursachen, **eine** Reaktion (Freeze):
  - **Kante/Abgrund:** der Fuß reicht beim adaptiven Touchdown nach unten, findet aber **bis
    `cliff_depth` keinen Boden** → kein Grund unter dem Bein.
  - **Slip (flach):** ein Stance-Fuß **verliert** den Kontakt (rutscht weg).
- **`cliff_depth` (0.03) ist die Grenze zwischen folgbarem Terrain und „Abgrund":** ein Abfall
  **≤ cliff_depth** wird vom adaptiven Touchdown (S4-2) noch **gefunden** (Fuß setzt auf → gestützt);
  ein Abfall **> cliff_depth** → kein Kontakt → **kein Halt** → (entprellt) **Freeze**. Damit ist
  `cliff_depth` genau „der Wert, ab dem es als zu tief gilt".
- **Envelope:** `cliff_depth` 0.03 → Floor −0.11, offline GREEN (bis −0.12 geprüft). Live tunbar.
- ⚠️ **`contact_timeout` (0.1 s = ~5 Ticks)** verzögert die **fallende** Flanke (Slip) → die
  Entprellung muss > 5 Ticks sein. (Die Kante hat keine fallende Flanke — der Fuß war nie in
  Kontakt → prompt.)
- **Reaktion = Freeze** (v1): `/hexapod_safety_freeze` + lokaler Stopp (kein neuer Trajektorien-
  Publish), **gelatcht** + einmalig auf der steigenden Flanke — exakt wie Stufe-1-Tip-CRIT.
  „Bein zurückziehen / Schritt nicht committen" = später (S4-4b), bewusst aus v1.

## 1. Logik-Skizze + Pseudocode

### 1.1 `SupportMonitor` (ROS-frei, wie `TipMonitor`)
Entprellung + Latch, per-Bein. **Kern-Regel: ein Stance-Bein, das bis zu einer Stance-Phase-Grace
keinen Kontakt hat, gilt als „Halt verloren".** Die Grace lässt dem Touchdown/Probe Zeit (deckt den
~13-Tick-JTC-Lag ab); danach = echter Halt-Verlust.

```
class SupportMonitor(debounce_ticks, min_lost_legs, grace_stance_phase):
  state per leg: lost_ticks=0;  latched=False

  reset():  # State-Gating (nur WALKING) / Recovery
     alle lost_ticks=0; latched=False

  update(legs):   # legs: leg_id -> (is_stance, stance_phase, contact)
     for leg in 1..6:
        is_stance, sp, contact = legs[leg]
        if not is_stance or sp < grace:  lost_ticks[leg]=0      # Schwung/Touchdown-Fenster: frisch
        elif contact:   lost_ticks[leg]=max(0, lost_ticks[leg]-1)  # LEAKY-Abbau (s. Sim-Befund)
        else:           lost_ticks[leg]+=1                      # Stance, nach Grace, kein Kontakt
     n_lost = count(lost_ticks[leg] >= debounce)
     if n_lost >= min_lost_legs: latched=True
     return n_lost, latched     # latched bleibt bis reset()

# Sim-Befund (Robustheit): Reset-auf-0 bei JEDEM Kontakt war zu fragil — beim Kippen über die
# Kante brühren die Beine intermittierend den Boden → consecutive-no-contact erreicht nie die
# Entprellung (Fall 2: kein Freeze trotz pitch 13°). LEAKY (Kontakt = nur −1) akkumuliert bei
# überwiegend-kein-Kontakt → Freeze, lässt aber legitimes ~50%-Prellen netto gedeckelt.
```

### 1.2 Engine — Probe-Floor = `cliff_depth` wenn slip armed
`_adaptive_touchdown_z` nutzt heute `z_floor = body_height − touchdown_max_extra_depth`. Neu:
optionaler **`self.cliff_probe_depth`** (0 = inaktiv). Effektiver Floor =
`body_height − max(touchdown_max_extra_depth, cliff_probe_depth)`. So reicht der Fuß bei armiertem
Slip bis `cliff_depth` (Terrain ≤ cliff_depth wird gefunden → gestützt; tiefer → kein Kontakt).
Node setzt `engine.cliff_probe_depth = cliff_depth if slip_detection_enable else 0.0`.

### 1.3 Node-Glue (`gait_node`)
- Pro Tick (im `_LEVELING_NODE_STATES`-Gating, nur WALKING relevant — STANDING hat keinen Vortrieb
  über Kanten): `legs = {leg_id: (is_stance, stance_phase, contact)}` aus `engine.leg_gait_states(t)`
  + `self._foot_contact`. `SupportMonitor.update(legs)`.
- `n_lost, freeze = ...`. **`freeze` steigende Flanke** → `get_logger().error(...)` +
  `_trigger_safety_freeze()` + `return` (kein Publish), genau wie Tip-CRIT. Latch via Monitor.
- Gating: nur in WALKING auswerten; sonst `SupportMonitor.reset()` (wie Tip).
- Params live (`_on_param_change`/`_apply_param`): `slip_detection_enable` (Default **false**),
  `cliff_depth` (0.03), `slip_debounce_ticks` (8), `slip_min_lost_legs` (1), `slip_grace_stance_phase`
  (0.6). Bei Änderung von debounce/min/grace → Monitor neu bauen (wie `_rebuild_tip_monitor`).

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: Halt-Verlust** | Stance + kein Kontakt nach Grace + Entprellung → lost; Kontakt → nicht | konstruierte Sequenzen |
| **Unit: Grace** | kein Flag während frühem Stance (Touchdown-Fenster) trotz no-contact | sp < grace → kein lost |
| **Unit: Schwung-Reset** | Schwung-Bein zählt nie als lost; Reset bei Schwung | (False,…)→0 |
| **Unit: min_legs + Latch** | erst ab `min_lost_legs` Freeze; danach gelatcht bis reset | count-Schwelle + Latch |
| **Unit: Entprellung > contact_timeout** | < debounce Ticks kein Freeze (Slip-Flanke-Lag) | debounce-Grenze |
| **Engine: cliff_probe_depth** | Floor = max(max_extra_depth, cliff_depth); 0 → unverändert | z-Wert |
| **Node: Wiring + Freeze + Gating** | lost-Beine → Freeze-Trigger; nur WALKING; reset sonst; Params live | rclpy-Smoke |
| colcon + Lint | alle grün | 0 Fehler |
| **Sim (User) Kante** | `step_walk step_drop:=0.06` (> cliff_depth): Roboter **freezt an der Kante** statt drüber; ohne slip läuft er drüber/kippt | A/B |
| **Sim (User) flach** | normaler Lauf → **kein** Fehl-Freeze (Kontakt zuverlässig) | Regression |

**Bewusst NICHT (→ später):** Bein-Zurückziehen / Schritt-Nicht-Committen (S4-4b); Recovery-Automatik
nach Freeze (wie Stufe 1 via State-Wechsel); Sensor-Fault-Plausibilität (S4-5); echte HW-Taster (E2).

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-4:
- [ ] S4-4.1 SupportMonitor (ROS-frei): per-Bein Entprellung + Latch + reset; Halt-Verlust = Stance+kein-Kontakt nach Grace
- [ ] S4-4.2 Engine: cliff_probe_depth-Attribut → Floor = body_height − max(max_extra_depth, cliff_probe_depth)
- [ ] S4-4.3 gait_node: SupportMonitor-Wiring (WALKING-Gating, reset sonst) + Freeze (steigende Flanke, _trigger_safety_freeze, kein Publish) + cliff_probe_depth setzen
- [ ] S4-4.4 Params: slip_detection_enable (false), cliff_depth (0.03), slip_debounce_ticks (8), slip_min_lost_legs (1), slip_grace_stance_phase (0.6) — live, validiert, Monitor-Rebuild
- [ ] S4-4.5 Unit-Tests (Halt-Verlust, Grace, Schwung-Reset, min_legs+Latch, Entprellung) + Engine + Node-Smoke
- [ ] S4-4.6 colcon test + Lint grün
- [ ] S4-4.7 README/Konzept (Slip/Kante → Freeze, cliff_depth-Grenze, Entprellung vs contact_timeout, Params)
- [ ] S4-4.8 Test-Doku stage_4d_slip_detection_test_commands.md (Kante step_drop:=0.06 A/B + flach kein Fehlalarm) + Sim-Verify durch User
- [ ] S4-4.9 kritische Self-Review-Tabelle
```

## 4. Offene Punkte — alle entschieden (User)
1. **cliff_depth = 0.03 (mittel)**, live tunbar (später ggf. erhöhen). ✅
2. **Reaktion = nur Freeze** (v1, wie Stufe 1); Zurückziehen = S4-4b später. ✅
3. **min_lost_legs = 1** (Default): an einer geraden Kante geht je Tripod **ein** Bein über den Rand
   → Freeze beim ersten „kein Grund", bevor mehr committet wird. Live hochsetzbar. *(Agent-Default,
   im Rahmen „Freeze reicht / sicher".)*
4. **grace 0.6** = `search_end_stance_phase` (Probe vorbei) · **debounce 8 Ticks** (> contact_timeout
   5 Ticks). *(Agent-Default; in Sim nachtunbar.)*

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| Detektion | **Stance + kein Kontakt nach Grace** (deckt Slip+Kante) | getrennte Slip/Cliff-Pfade | ein robustes Signal, adaptiv-unabhängig; Grace deckt JTC-Lag |
| `cliff_depth`-Rolle | **Terrain-Folge-Reach = Freeze-Grenze** (Abfall ≤ cliff_depth → gestützt, > → Freeze) | separater Cliff-Tiefen-Sensor | ein kohärenter Wert = „ab wann zu tief"; nutzt den S4-2-Probe |
| Reaktion | **Freeze (gelatcht, einmalig)** | Bein zurückziehen | sicher + einfach, = Stufe 1; Recovery via State-Wechsel |
| min_legs | **1** (live) | ≥2 | an gerader Kante 1 Bein/Tripod → früh stoppen ist sicher |
| Klasse | **SupportMonitor (ROS-frei)** | im Node | testbar wie TipMonitor; Node bleibt dünn |
| Entprellung | **8 Ticks** | < 5 | muss contact_timeout (5) überschreiten, sonst Slip-Fehlalarm |

## 6. Handoff / Code-Anker
- Vorlage: `tip_monitor.py` (`TipMonitor`) + `_update_tip`/`_trigger_safety_freeze`/`_rebuild_tip_monitor`
  + Tip-Param-Block in `gait_node.py`.
- Engine: `_adaptive_touchdown_z` (`z_floor`) + neues Attribut `cliff_probe_depth`.
- Kontakt + Phase: `self._foot_contact` (S4-1) + `engine.leg_gait_states(t)`.
- Sim-Welt (existiert): `step_walk.launch.py step_drop:=0.06` = 6-cm-Kante > cliff_depth (Abgrund).
- Reaktion: `_trigger_safety_freeze()` (Stufe 1) — in Sim lokaler Stopp (kein Plugin).

## 7. Doku-Hygiene bei Abschluss
- `imu_balance_progress.md` (S4-4-Checkliste + Post-Review), Umbrella (S4-4 → 🟢),
  `hexapod_gait/README.md`, `ai_navigation.md` (Stufe-4-Eintrag: Slip/Freeze + cliff_depth),
  Memory `project_a5_stage4_adaptive_touchdown`.
