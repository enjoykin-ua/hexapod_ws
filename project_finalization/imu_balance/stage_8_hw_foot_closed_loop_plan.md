# Stufe 8 — Fußkontakt-Closed-Loop auf HW (§4-Plan)

> **Status: 🟡 freigegeben — Umsetzung läuft.** Test-Doku:
> [`stage_8_hw_foot_closed_loop_test_commands.md`](stage_8_hw_foot_closed_loop_test_commands.md) ·
> Done-Checkliste: [`imu_balance_progress.md`](imu_balance_progress.md) (Stufe 8). **HW8.0 ✅**
> (User-Vorab-Verify). ⚠️ **Reihenfolge-Umbau (User-Entscheid):** HW8.1 (Timing) läuft **am Boden
> beim HW8.2b-Gate-Lauf mit** statt aufgebockt — aufgebockt lassen sich nicht 5–6 Taster gleichzeitig
> drücken; am Boden liefern alle 6 Beine echte Flanken automatisch. Aufgebockt bleibt nur der
> taster-freie Probe-Test (HW8.2a).
> **Block A5.** Bringt das **adaptive Fußkontakt-Verhalten** (bisher **nur Sim**-verifiziert) auf die
> **echte Hardware** — mit den Tastern, die als Sensor-Kette (Stufe 5) schon HW-live sind. Regler-Code
> steht (S4-1/2/4/5/7) → **überwiegend HW-Verifikation + Timing-Re-Tuning**. ⚠️ Zwei Stellen können
> doch einen **kleinen Code-Fix** brauchen: die nie getestete **S4+Leveling-Kombi** (HW8.7 — Reihenfolge
> adaptive-z ↔ Leveling-Rotation) und evtl. HW-Timing-Edge-Cases.
>
> **User-Entscheide (Vorab):** alle 6 Taster verdrahtet+funktionieren · **gestaffelt** (Sensor-6 →
> Touchdown → Slip/Fault → dann Leveling-Kombi) · S4-7 (Adaptive Stand) + Kombi als spätere Schritte
> im selben Block.

---

## 0. Kontext + Warum HW-Verifikation nötig

**HW-verifiziert (Stufe 5):** nur die **Sensor-Kette** — Taster → FW `GET_INPUTS` → Plugin → 6
`/leg_<n>/foot_contact`-Bool-Topics → RViz. Die **gesamte Regelschleife** darauf ist **nur Sim**:

| Feature | Regler/Stellpfad | Status |
|---|---|---|
| S4-2 adaptiver Touchdown (downward-only bis Kontakt) | `gait_engine._adaptive_touchdown_z` | 🟢 Sim |
| S4-4 Slip/Kontaktverlust → Freeze | `support_monitor.py` (`SupportMonitor`) | 🟢 Sim |
| S4-5 Sensor-Fault-Fail-Safe (Bein maskieren) | `sensor_health_monitor.py` (`SensorHealthMonitor`) | 🟢 Sim |
| S4-7 Adaptive Stand (statischer Zwilling) | `gait_engine._adaptive_stand_z` | 🟡 **nicht mal Sim-verifiziert** (Rubicon offen) |

**Warum Sim ≠ HW hier besonders greift:**
- **Timing:** die Logik ist gegen **Sim-Annahmen** dimensioniert — ~13-Tick-JTC-Ausführungs-Lag,
  `contact_timeout` 5 Ticks. Auf HW gilt die **FW-Entprellung (~20–30 ms)** + echte JTC-Konvergenz →
  `touchdown_probe_start`, `slip_debounce_ticks`, `sensor_dead_cycles` **neu messen/tunen**.
- **gz-Apex-Artefakt:** die S4-5-stuck-on-Logik (lückenlose Apex-Pässe) wurde **gegen ein Sim-Artefakt**
  gebaut; auf HW existiert es nicht → echte Faults (Prellen/Klemmen/abgesteckt) sehen anders aus.
- **Kombi S4 + IMU-Leveling:** Stufe 4 lief **immer isoliert** (`leveling_enable:=false`). Die
  adaptive-z **unter** aktivem `set_body_orientation_offset` (Stufe 7) ist **nie zusammen** gefahren.
- **Safety-Freeze real:** in Sim = „lokaler Stopp" (JTC hält); auf HW feuert `/hexapod_safety_freeze`
  echt (Relay/Servo) — Freeze-Sequenzen brauchen den Watchdog-Heartbeat ([[project_phase13_onactivate_watchdog_heartbeat]]).

## 1. Ziel

Die sim-verifizierten Fußkontakt-Features am **bestromten Roboter** verifizieren + auf HW-Timing
nachziehen (aufgebockt zuerst, dann Boden, §9), und die **S4+Leveling-Kombi** erstmals fahren.
Ergebnis = HW-Gain-Satz (touchdown/slip/sensor-Params) in einer HW-Preset-YAML + Doku.

## 2. Logik-Skizze / Vorgehen (risk-aufsteigend, gestaffelt)

> **Isoliert zuerst:** wie in Sim läuft S4 anfangs mit `leveling_enable:=false` (nur Fußkontakte,
> keine IMU-Rotation). Die **Kombi mit Leveling** ist bewusst der **letzte** Schritt (HW8.7).

- **HW8.0 — Sensor-Kette alle 6 (aufgebockt, read-only).** Stufe 5 von leg 1 auf **alle 6** erweitern:
  Taster einzeln drücken → je `/leg_<n>/foot_contact` toggelt sauber; `foot_contact_viz` in RViz
  (6 Marker); keine Geister/Dauer-True. **Kein Servo-Enable nötig** (reine Sensor-Prüfung).
- **HW8.1 — Timing-Charakterisierung (aufgebockt).** Mit `ContactDiagnostic` (S4-1, `foot_contact_debug_enable`)
  das **echte Flanken-Timing** messen: FW-Entprellungs-Latenz + JTC-Konvergenz vs. die Sim-Annahmen
  (13-Tick-Lag, `contact_timeout` 5). Liefert die Basis, um `touchdown_probe_start_stance_phase`,
  `slip_debounce_ticks`, `sensor_dead_cycles` HW-korrekt zu setzen.
- **HW8.2 — S4-2 adaptiver Touchdown aufgebockt.** `adaptive_touchdown_enable:=true`, Beine in der Luft
  → downward-only-Nachreichen „zum Boden, der nicht da ist". Prüfen: **kein** Drift/Ducken/Rückwärts
  (Körper-Anker bei `body_height` hält), kein Durchsacken. `touchdown_probe_start`/`max_extra_depth`
  gegen das HW-Timing (HW8.1) nachstimmen.
- **HW8.2b — Boden-Lauf-Gate (ohne S4, ohne Leveling).** BEVOR S4 am Boden: verifizieren, dass der
  Roboter am Boden mit voller Last **überhaupt stabil geradeaus läuft** (S4 **und** Leveling AUS) —
  analog dem Stufe-7-Gate 7.10d-0. Womöglich der **erste echte Boden-Lauf**. Läuft er nicht sauber →
  separates Gang-/Traktions-/Strom-Problem, **nicht** Stufe 8; hier stoppen.
- **HW8.3 — S4-2 am Boden (der sichtbare Payoff).** Roboter läuft am Boden über eine **echte Stufe /
  einen Graben** → einzelne Füße **reichen nach**, Körper bleibt stabil. Strom beobachten, Kill-Switch.
- **HW8.4 — S4-4 Slip→Freeze am Boden.** `slip_detection_enable:=true`. Über eine **Kante/Abgrund** →
  Stütz-Bein ohne Kontakt nach Grace → **Freeze** rechtzeitig; auf **gutem Boden kein Fehl-Freeze**.
  `slip_debounce_ticks`/`slip_grace_stance_phase` gegen FW-Entprellung re-tunen; `cliff_depth` gegen
  echte HW-Reach.
- **HW8.5 — S4-5 Sensor-Fault am Boden (echter Fault, kein Inject).** `sensor_plausibility_enable:=true`.
  Einen Taster **real abstecken/klemmen** → betroffenes Bein **maskiert** + throttled WARN, **kein**
  Freeze, **keine** False-Positive-Kaskade (gz-Apex-Artefakt fehlt auf HW → Erkennung neu validieren).
- **HW8.6 — S4-7 Adaptive Stand.** **Zuerst der offene Sim-Rubicon-Verify** (Desktop), **dann** HW
  (aufgebockt → Boden): im STANDING reicht jedes Bein downward-only bis Kontakt; AUS = starre Pose.
- **HW8.7 — Kombi S4 + Leveling (die nie getestete Kombination).** `leveling_enable:=true` **und**
  adaptiver Touchdown/Stand → prüfen, dass die adaptive-z **unter** der Leveling-Rotation geometrisch
  sauber bleibt (kein Konflikt/IKError), Reihenfolge im Tick stimmt.
- **HW8.8 — HW-Gains sichern + Doku** (touchdown/slip/sensor-Params, HW vs Sim) in HW-Preset-YAML.
- **HW8.9 — kritische Self-Review.**

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Setup |
|---|---|---|
| **HW8.0** Sensor-6 | alle 6 Taster → saubere Topics + RViz, keine Geister | aufgebockt, read-only |
| **HW8.1** Timing | reale Flanken-Latenz gemessen → Param-Basis | aufgebockt, `ContactDiagnostic` |
| **HW8.2a** Touchdown aufgebockt stabil | kein Drift/Ducken/Durchsacken (Anker hält) | aufgebockt, `adaptive_touchdown_enable` |
| **HW8.3a** Touchdown Boden reicht nach | Fuß reicht in Stufe/Graben, Körper stabil | Boden + echte Stufe/Graben |
| **HW8.4a** Slip-Freeze feuert | echte Kante → Freeze rechtzeitig | Boden + Kante/Abgrund |
| **HW8.4b** kein Fehl-Freeze | guter Boden → **kein** Freeze | Boden flach |
| **HW8.5a** Fault maskiert | abgesteckter Taster → Bein maskiert + WARN, kein Freeze | Boden, Taster real trennen |
| **HW8.5b** keine FP-Kaskade | gesunde Beine bleiben unmaskiert (kein gz-Artefakt auf HW) | Boden |
| **HW8.6** Adaptive Stand | Sim-Rubicon zuerst; dann HW: reicht bis Kontakt / AUS=starr | Sim + HW aufgebockt/Boden |
| **HW8.7** S4+Leveling-Kombi | adaptive-z unter Leveling-Rotation sauber, kein IKError/Konflikt | Boden, beides an |
| **HW8.8** Gains gesichert | HW-Params in Preset-YAML + Doku (HW vs Sim) | — |

**Bewusst NICHT (→ scope-out / später):**
- **S4-3 free-gait** (Timing am Kontakt) — bleibt optional, nur falls fixed-timing nicht reicht.
- **Quer-/Diagonal-Terrain**, **adaptiver Slope-Schätzer** (Stufe-7-D1), **state-abhängige Fenster**.
- **Unit-Tests:** die Regler (`SupportMonitor`/`SensorHealthMonitor`/adaptive-z) sind sim-unit-getestet;
  Stufe 8 ist **HW-Verifikation + Timing-Tuning**, keine neue Kern-Logik.

## 4. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
Stufe 8 (Fußkontakt-Closed-Loop auf HW):
- [ ] HW8.0 Sensor-Kette alle 6 Taster HW-verifiziert (Topics + RViz, keine Geister) — aufgebockt, read-only
- [ ] HW8.1 Timing-Charakterisierung (ContactDiagnostic): FW-Entprellung + JTC-Lag gemessen -> Param-Basis
- [ ] HW8.2 S4-2 adaptiver Touchdown aufgebockt: kein Drift/Ducken/Durchsacken; probe_start/max_depth HW-getunt
- [ ] HW8.3 S4-2 am Boden: Fuss reicht in Stufe/Graben, Koerper stabil, Strom ok
- [ ] HW8.4 S4-4 Slip->Freeze: echte Kante -> Freeze rechtzeitig + guter Boden kein Fehlalarm; debounce/grace HW-getunt
- [ ] HW8.5 S4-5 Sensor-Fault (echt abgesteckt): Bein maskiert + WARN, kein Freeze, keine FP-Kaskade
- [ ] HW8.6 S4-7 Adaptive Stand: Sim-Rubicon-Verify zuerst, dann HW (aufgebockt->Boden)
- [ ] HW8.7 Kombi S4 + Leveling: adaptive-z unter Leveling-Rotation sauber (kein IKError/Konflikt)
- [ ] HW8.8 HW-Gains in Preset-YAML + Doku (HW vs Sim)
- [ ] HW8.9 kritische Self-Review-Tabelle
```

## 5. Sicherheit (CLAUDE.md §9)

- **Aufgebockt zuerst** (HW8.0–HW8.2), Kill-Switch/Strom-Trennung griffbereit, reduzierte Rate; dann Boden.
- **Enable-Flags sind Opt-in (Default false)** — gezielt live scharfschalten, nie unbeaufsichtigt beim Bringup.
- **Safety-Freeze real:** `/hexapod_safety_freeze` feuert auf HW echt (Relay/Servo). Freeze-Sequenzen
  müssen den **Watchdog-Heartbeat** füttern ([[project_phase13_onactivate_watchdog_heartbeat]]), sonst
  FW-Watchdog + Relay-Drop.
- **Slip/Fault provozieren gezielt** (Kante/abgesteckter Taster) — nie „mal schauen ob er kippt" ohne Netz.
- **Recovery nach Slip-Freeze** (gelatcht): `ros2 service call /hexapod_sit_down std_srvs/srv/Trigger '{}'`
  dann `/hexapod_stand_up` — State-Wechsel setzt `SupportMonitor`/Latch zurück (wie Tip-CRIT).
- **`foot_contact_debug_enable`-Default** auf HW beachten (der Sequenz-Revert-Bug hing daran; Fix ist drin,
  aber HW-Default bewusst setzen).

## 6. Offene Punkte — Stand (mit User geklärt / Rest markiert)

1. **Physisches Test-Terrain:** ✅ **vorhanden** (User) — Stufe (~2–4 cm), Graben (fußbreit),
   Kante/Abgrund.
2. **S4-7 Reihenfolge:** ✅ **Sim-Rubicon-Verify zuerst** (Desktop, der offene Sim-Schritt), dann HW = HW8.6.
3. **Kombi-Leveling:** ✅ **letzter Schritt HW8.7** (nach den isolierten S4-Tests).
4. **HW-Gain-Ablage:** ✅ **eigene Preset-YAML** für die S4-Params (touchdown/slip/sensor), getrennt von
   `hw_balance.yaml` (Leveling).
5. **Taster-Polarität:** ✅ **geklärt** — Boden-Kontakt = **True(1)**, Luft = **False(0)**. Deckt sich mit
   Code (`True`=Kontakt; `SupportMonitor` wertet Stance-Bein OHNE Kontakt als Slip) **und** HW-Stufe-5
   (Druck → „in contact"). `sensor_leg_map` = identity.
   - ✅ **Fail-safe-Richtung geklärt (HW8.0, User-Verify):** abgesteckter Taster/Kabelbruch = offener
     Kreis (Pull-Up) = wie „nicht gedrückt" = **`False`(Luft)** → die **sichere** Fehlrichtung
     (schlimmstenfalls Fehl-Slip-Freeze, nie „fälschlich geerdet" über einer Kante); die S4-5-dead-
     Erkennung maskiert den Dauer-False-Fall.
6. 🟡 **`cliff_depth`/Envelope-Floors** (0.02/0.03/0.04) gegen die **echte** HW-Reach + URDF-Limits — bei
   HW8.4 messen (Sim-lenient hat evtl. maskiert).
7. 🟡 **Boden-Lauf-Voraussetzung:** läuft der Roboter am Boden mit voller Last **überhaupt stabil**? →
   **HW8.2b-Gate** (unten) klärt das VOR den S4-Boden-Tests (analog Stufe-7-7.10d-0). Womöglich der erste
   echte Boden-Lauf.
8. 🟡 **HW-Slip-Timing:** auf HW gilt **NICHT** `contact_timeout` (5 Ticks, Sim), sondern **FW-Entprellung
     (~20–30 ms) + Plugin-Freshness-Gate (100 ms)** → `slip_debounce_ticks` daran neu bemessen (HW8.1/8.4).

## 7. Handoff / Anker (Code + Params, aus Bestandsaufnahme)

- **Regler (ROS-frei, sim-unit-getestet):** `support_monitor.py` (`SupportMonitor`, S4-4) ·
  `sensor_health_monitor.py` (`SensorHealthMonitor`, S4-5) · `contact_diagnostic.py` (`ContactDiagnostic`,
  S4-1 Mess-Tool) · `foot_contact_viz.py` (RViz-Adapter).
- **Stellpfad (Engine, ROS-frei):** `gait_engine.py` — `_adaptive_touchdown_z` (S4-2),
  `_adaptive_stand_z` (S4-7), `set_foot_contacts`, `set_adaptive_masked_legs`, `cliff_probe_depth`,
  `leg_gait_states`.
- **ROS-Glue:** `gait_node.py` — 6 `/leg_<n>/foot_contact`-Subs, `_update_support`,
  `_update_sensor_health`, `_rebuild_support_monitor`, alle S4-Params live.
- **Params (Namen + Defaults, alle live):**
  - S4-2: `adaptive_touchdown_enable`(false), `touchdown_probe_start_stance_phase`(0.35),
    `touchdown_search_end_stance_phase`(0.6), `touchdown_max_extra_depth`(0.02).
  - S4-4: `slip_detection_enable`(false), `cliff_depth`(0.03), `slip_debounce_ticks`(8),
    `slip_min_lost_legs`(1), `slip_grace_stance_phase`(0.6).
  - S4-5: `sensor_plausibility_enable`(false), `sensor_apex_band_low`(0.3), `sensor_apex_band_high`(0.7),
    `sensor_apex_fault_cycles`(3), `sensor_dead_cycles`(2), `sensor_fault_inject`('' — Sim-Debug-Hook).
  - S4-7: `adaptive_stand_enable`(false), `stand_conform_max_depth`(0.04), `stand_conform_rate`(0.02).
  - HW-Quelle: `publish_foot_contacts`(true), `sensor_leg_map` (identity) — `real.launch.py`.
- **HW-Bringup:** `real.launch.py loopback_mode:=false` (+ `enable_imu:=true` erst für HW8.7-Kombi);
  `foot_contact_viz` für RViz. **Bestehende HW-Doku:** `stage_5_hw_foot_contacts_test_commands.md`
  (nur Sensor-Kette) — Stufe 8 ergänzt die Closed-Loop-Test-Commands.
- **Sim-Welten (für S4-7-Rubicon + Referenz):** `step/trench/rubicon.sdf.xacro`,
  `step_walk/trench_walk/rubicon.launch.py`.

## 8. Doku-Nachzug (nach Implementierung)
- `imu_balance_progress.md`: Stufe-8-Abschnitt + Checkliste + Self-Review.
- `ai_navigation.md` (Fußkontakt-A5-Abschnitt): „Closed-Loop auf HW verifiziert" + Symptom→Stellschraube
  (Fehl-Freeze → `slip_debounce_ticks` hoch; Fault-FP → `sensor_apex_fault_cycles` hoch; Touchdown-Drift
  → `touchdown_probe_start` gegen HW-Lag).
- `PHASE.md`: A5-Zeile (Stufe 8 HW-Closed-Loop).
- HW-Test-Commands-Datei `stage_8_hw_foot_closed_loop_test_commands.md` (self-contained, copy-paste).
