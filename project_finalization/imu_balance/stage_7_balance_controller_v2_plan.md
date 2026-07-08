# Stufe 7 — Balance-Regler v2 (Hysterese + Dual-Tiefpass + per-Achse) (§4-Plan)

> **Status: 🟡 Plan (implementierungsreif, v2) — wartet auf User-Freigabe/Commit → dann Implementierung.**
> **Code-Default = heutiges Verhalten** (Hysterese/Filter aus); der Fix lebt in `hw_balance.yaml` (User-Entscheid E9).
> **Block A5 IMU-Balance.** Logisch ein Nachfolger des `BalanceController` aus Stufe 2/TF-2, aber
> **sequenziert nach Stufe 6**, weil das **HW-Tuning (IP3/6c) das Pendeln aufgedeckt** hat.
> **IP3/6c ist dafür pausiert** und wird **nach** Stufe 7 auf dem neuen Regler neu gefahren.
>
> Voraussetzung/Basis: Stufe 6 🟢 (`/imu/data` HW, base_link-korrekt, yaw-stabil). Regler sim-baubar/
> -verifizierbar wie Stufe 2/TF-2; HW-Tuning erst danach (6c auf v2).

---

## 0. Motivation (warum überhaupt)

Beim HW-Tuning (IP3.2, aufgebockt) **pendelt** das statische Leveling: der pitch schwingt an der
Totband-Kante (~2°) eine Weile hin und her, bevor er still steht. Ursache-Analyse (Code + HW):

- Der aktuelle `BalanceController` hat **ein** Totband mit **einer** Schwelle → **keine Hysterese**.
  Am Totband-Rand togglet der P-Term jeden Tick an/aus, sobald das (ungefilterte) Signal die Schwelle
  kreuzt → **Rand-Chatter / Grenzzyklus**. Verstärkt durch hohes `kp` (HW brauchte mehr als Sim, 1.3
  statt 0.4) und **Servo-Lag ohne Positions-Feedback**.
- Der Regler ist **pro Achse** (eigener Integrator/Ausgang für roll/pitch), teilt sich aber **dieselben
  Gains** — obwohl der Roboter **länglich/schmal** ist und **Roll** (seitlich) früher/sensibler kippt
  als **Pitch**.

Das ist keine Tuning-Frage mehr, sondern **neue Regler-Logik** → eigene Stufe (nicht IP3-„nur Gains").

---

## 1. Ziel

`BalanceController` **v2**, der:
1. das Pendeln beseitigt durch **Zwei-Fenster-Hysterese** (Schmitt-Trigger auf „regeln/nicht regeln"),
2. das statische/flache Leveln glättet durch **Dual-Tiefpass (fast/slow)** — **nur im horizontal-Modus**,
3. **alle** Gains + Fenster + Filter **per Achse** (roll/pitch) einstellbar macht,
4. **voll backward-kompatibel** bleibt: Filter aus + `inner==outer` + `roll==pitch` ⇒ **exakt heutiges
   Verhalten** ⇒ die Sim-Verifikation von Stufe 2/3a/TF-2 bleibt gültig.

Ergebnis = ein austauschbarer, unit-getesteter Regler hinter **derselben** `update()`-Schnittstelle
(die der Docstring seit Master D3 als Austausch-Variante bereits vorsieht).

---

## 2. Entschiedene Design-Punkte (User-Freigabe im Brainstorm)

| # | Entscheidung | Begründung |
|---|---|---|
| E1 | **Zwei-Fenster-Hysterese** (innen/außen): nicht-regelnd → **start** bei `|x_slow| ≥ außen`; regelnd → **stop** (P=0, Integrator hält) bei `|x_fast| ≤ innen` | tötet den Rand-Chatter; „stop" schnell (fast), „resume" träge (slow → ignoriert Transiente) |
| E2 | **Dual-Tiefpass (fast/slow) NUR im horizontal-Modus** | im terrain-Modus ist der `SlopeEstimator` schon die langsame Stufe → zweiter Filter = Doppelfilter-Problem (Knick-Lurch, Leveling engagiert kaum) |
| E3 | **terrain-Modus:** Hysterese auf dem **Residual** (IMU − Hang-Schätzung), Slope-Schätzer = langsame Stufe, **kein** zweiter Filter | roll→0, pitch folgt Hang; nur Wackeln wird gedämpft |
| E4 | **Per-Achse (roll/pitch) getrennt:** `kp, ki, kd, deadband_inner, deadband_outer, slew_max, tau_fast, tau_slow` — **Start-Default roll==pitch** | Roll kippt früher (schmal seitlich); Möglichkeit da, Tuning optional |
| E5 | **Tip-Schwellen per Achse:** `tip_angle_warn/crit` roll vs. pitch getrennt | Roll erreicht echten Umkipp-Winkel früher → kleinere Schwelle |
| E6 | **Gyro-D (`kd`) bleibt IMMER aktiv** (auch im „nicht-regelnd"-Hold) | Wackeln = kleiner Winkel + hohe Rate; „Hold" = D-only = heutiges In-Totband-Verhalten |
| E7 | **`converged` neu:** „beide Achsen **nicht-regelnd**" (statt „im Totband") | treibt den Startup-Grace/Tip-Netz-Gate — sicherheitsnah, muss stimmen |
| E8 | **Backward-kompatibel per Default** (Filter aus, `inner==outer`, roll==pitch) | Stufe 2/3a/TF-2-Sim-Verify bleibt gültig; v2-Features explizit dazuschalten |
| E9 | **Code-Default = heutiges Verhalten**; die HW-Arbeitswerte (Hysterese/Filter an) leben in `hw_balance.yaml` | sauberer Regressionsanker, kein stilles Verhaltens-Delta (User-Entscheid) |

**Deferred (bewusst NICHT in Stufe 7):**
- **D1 Adaptiver Slope-Schätzer** (variables τ: schnell bei anhaltendem Lehnen = Knick, langsam bei
  Wackeln/steady) — **erst nach HW-Knick-Messung** bauen, nur wenn der Lurch es rechtfertigt. Löst
  *zusätzlich* das Doppelfilter-Problem im terrain-Modus (ein adaptiver Filter statt zwei).
- **D2 Stufe vs. Hang** aus IMU allein nicht sicher trennbar (beide = Residual-Spike); echter
  Disambiguator = **Fußkontakte (Stufe 4)**. v2 folgt Anhaltendem, toleriert an einer Stufe einen
  kurzen, **slew-gedeckelten** Mit-Ausschlag. Perfekte Stufen-Behandlung = Stufe 4.
- **D3 State-abhängige Fenster** (STANDING eng / WALKING weit > Gang-Ripple) — als Tuning-Option
  vorsehen, aber **erst bei HW-Bedarf** scharf (sonst Param-Explosion). Siehe offene Punkte.
- **D4 Per-Achse Clamp / Tip-Rate** — `max_level_angle` bleibt vorerst gemeinsam (offline
  envelope-bewiesen, kombiniert); `tip_rate_crit/debounce` gemeinsam.
- **D5 Regelgröße-Filterung** → **aufgelöst** (s. §2.1-D): P/I-Eingang = `m_fast`.

### 2.1 Implementierungs-Entscheidungen (aufgelöste Findings A–I aus dem Plan-Review)

| # | Entscheidung | Auswirkung |
|---|---|---|
| **A** | **Filter-Applikabilität pro *Achse*, nicht pro *Modus*.** Der Regler bekommt pro Achse ein Flag `apply_filter` = „Eingang ist roh". `gait_node` setzt `filter_roll=True` (immer roh, →0), `filter_pitch = (mode != 'terrain')`. → im terrain-Modus wird **nur pitch** (Residual) nicht gefiltert, **roll** (roh) schon. | verhindert roll-Chatter beim Laufen **und** pitch-Doppelfilter am Hang. Wasserdicht macht E2/E3. |
| **B** | **Snap-Init pro Achse:** erstes Sample nach `reset()` setzt `m_fast=m_slow=measured` (+`_initialized`-Flag). | kein verzögertes Engagement beim Enable auf gekipptem Roboter (wie `SlopeEstimator`). |
| **C** | **Back-Compat-Defaults exakt gepinnt** (§3.3): `inner==outer==1.5`, `tau_fast==tau_slow==0`, roll==pitch, tip 15/25. | mit diesen Werten reduziert sich v2 **exakt** aufs heutige `_update_axis` → Regressionsanker. |
| **D** | **Stellgröße-Eingang = `m_fast`** (= geglättet wenn gefiltert, sonst == `measured`). D-Term auf **roher** Gyro-Rate. | einheitlich; mit `tau_fast=0` == roh (heute). |
| **E** | **Kein Skalar-Alias.** `hw_balance.yaml` (einziger Konsument) wird auf `_roll/_pitch` migriert. | vermeidet fragile Alias-Semantik; Verhaltens-Back-Compat kommt über die Default-**Werte** (C), nicht über Namen. |
| **F** | **`converged` = beide Achsen nicht-regelnd** — kann True sein, während der Körper zwischen `inner`/`outer` (bis ~`outer`) schief steht (unter `tip_warn`). | expliziter Node-Test; bewusst akzeptiert (Startup-Grace armt Tip bei leichter Rest-Schräge). |
| **G** | **Latch persistiert** über STANDING↔WALKING↔STOPPING; Reset **nur** beim Verlassen der `_LEVELING_NODE_STATES` (sit/standup/show). | gewollt (glatter Übergang); state-abhängiger Clamp greift via `set_gains` weiter. |
| **H** | **`update()`-Signatur wird erweitert** um `filter_roll`/`filter_pitch` (heute nicht vorhanden — die frühere Formulierung „hat's schon" war falsch). | `gait_node._update_leveling` reicht die Flags durch. |
| **I** | **`hw_balance.yaml`-Migration** auf per-Achse ist Teil von Bullet 7.3. | sonst beim Übergang zu 6c-auf-v2 vergessen. |

**Hysterese-Schwellen-Konvention (Back-Compat-genau):** resume `|m_slow| ≥ outer`, stop `|m_fast| < inner`.
Bei `inner==outer==D` ⇒ regelnd genau dann, wenn `|x| ≥ D` ⇒ identisch zum heutigen `not (|error| < D)`.

---

## 3. Logik-Skizze / Pseudocode

### 3.1 `BalanceController` v2 (ROS-frei, per-Achse)

Datenhaltung **pro Achse** (roll, pitch): Gains (kp,ki,kd,inner,outer,slew,tau_fast,tau_slow),
State (integ, out, m_fast, m_slow, `regulating`:bool, `initialized`:bool). `max_level_angle` =
**gemeinsam** (state-abhängig 10/4° vom gait_node via `set_gains` gesetzt — wie heute).

```
update(roll, pitch, dt, gyro_roll, gyro_pitch, filter_roll, filter_pitch):
    # filter_*: True = Eingang ist ROH -> Dual-TP anwenden; False = Eingang ist bereits
    # slope-gefiltert (Residual) -> KEIN zweiter Filter (Finding A / E2 / E3).
    # gait_node setzt: filter_roll=True immer; filter_pitch = (mode != 'terrain').
    out_roll  = _update_axis(ROLL,  roll,  dt, gyro_roll,  filter_roll)
    out_pitch = _update_axis(PITCH, pitch, dt, gyro_pitch, filter_pitch)
    return (out_roll, out_pitch)

_update_axis(ax, measured, dt, gyro_rate, apply_filter):
    p, s = params[ax], state[ax]

    # (B) Snap-Init: erstes Sample nach reset() -> Filter direkt auf Messung (kein Hochlauf).
    if not s.initialized:
        s.m_fast = s.m_slow = measured
        s.initialized = True

    # (1) Dual-Tiefpass NUR wenn Eingang roh UND Filter an (tau_slow>0). Sonst m = measured.
    #     terrain-pitch: apply_filter=False -> m=measured=Residual (kein Doppelfilter, E2/E3).
    if apply_filter and p.tau_slow > 0 and dt > 0:
        s.m_fast = ema(s.m_fast, measured, p.tau_fast, dt)   # alpha=dt/(tau+dt); tau_fast=0 -> =measured
        s.m_slow = ema(s.m_slow, measured, p.tau_slow, dt)
    else:
        s.m_fast = s.m_slow = measured

    # (2) Hysterese-Latch (E1). Back-Compat-genau: resume >=outer, stop <inner
    #     -> bei inner==outer == Single-Schwelle == heute (C).
    if not s.regulating:
        if abs(s.m_slow) >= p.outer:  s.regulating = True
    else:
        if abs(s.m_fast) <  p.inner:  s.regulating = False

    # (3) Regelung — Soll 0. Stellgröße-Eingang = m_fast (D): geglättet wenn gefiltert, sonst =measured.
    error = -s.m_fast
    if not s.regulating:
        p_term = 0.0                         # Integrator eingefroren (HÄLT die Korrektur)
    else:
        p_term = p.kp * error
        if dt > 0: s.integ = clamp(s.integ + p.ki*error*dt, max_level_angle)   # Anti-Windup

    d_term = -p.kd * gyro_rate               # (E6) IMMER aktiv, auf ROHER Gyro-Rate (D-Zweck)
    raw = clamp(p_term + s.integ + d_term, max_level_angle)

    # (4) Slew-Limit (Scrub-Schutz, deckelt Lurch-Rate am Knick). dt<=0 -> out unverändert.
    s.out = slew(s.out, raw, p.slew_max, dt)
    return s.out

converged():   # (E7/F) beide Achsen nicht-regelnd = eingeschwungen.
    # ACHTUNG: kann True sein, während der Körper zwischen inner/outer (bis ~outer) schief steht.
    return (not state[ROLL].regulating) and (not state[PITCH].regulating)

reset():   # State-Gating/Recovery je Achse: integ=out=m_fast=m_slow=0, regulating=False, initialized=False
```

### 3.2 `gait_node`-Anbindung (Änderungen minimal halten)

- `_update_leveling` berechnet wie heute `roll_in` (roh) + `pitch_in` (terrain: Residual /
  horizontal: roh) und ruft (H) `update(roll_in, pitch_in, dt, gyro_roll, gyro_pitch,
  filter_roll=True, filter_pitch=(self._leveling_mode != 'terrain'))`. Die `update()`-Signatur
  wird um die zwei Filter-Flags **erweitert** (heute nicht vorhanden). **Kein** neuer Stellpfad,
  Engine unverändert (Korrekturen klein, Clamp 10/4° + IKError-Fallback = Backstop).
- Params **per Achse** deklarieren: `leveling_{kp,ki,kd,deadband_inner_deg,deadband_outer_deg,
  slew_max_dps,tau_fast_s,tau_slow_s}_{roll,pitch}`. **KEIN Skalar-Alias** (E): `hw_balance.yaml`
  (einziger Konsument) wird auf `_roll/_pitch` migriert (7.3). Verhaltens-Back-Compat kommt über
  die Default-**Werte** (§3.3), nicht über Namen.
- `TipMonitor`: `tip_angle_warn/crit` **per Achse** (E5) — statt `tilt = max(|roll|,|pitch|)` gegen
  eine Schwelle → CRIT wenn `|roll| ≥ crit_roll` ODER `|pitch| ≥ crit_pitch` (ODER Rate), WARN
  analog; `rate_crit`/`debounce` gemeinsam. Im slope-aware-Modus füttert gait_node wie heute die
  Residual-Komponenten.
- Alle neuen Params **live** (`_on_param_change`) + Validierung (`inner ≤ outer`, `tau ≥ 0`, `slew ≥ 0`).
- `converged()` speist wie heute den Startup-Grace-Gate in `_update_tip` (F).

### 3.3 Back-Compat-Default-Werte (Code-Default = heute; Fix lebt in `hw_balance.yaml`, E9)

Pro Achse, roll == pitch:

| Param (je `_roll` / `_pitch`) | Default | Effekt |
|---|---|---|
| `leveling_kp` | 0.4 | wie Stufe 2 |
| `leveling_ki` | 0.1 | wie Stufe 2 |
| `leveling_kd` | 0.03 | wie TF-2 |
| `leveling_deadband_inner_deg` | 1.5 | **inner == outer → Hysterese AUS** |
| `leveling_deadband_outer_deg` | 1.5 | " |
| `leveling_slew_max_dps` | 8.0 | wie Stufe 2 |
| `leveling_tau_fast_s` | 0.0 | **Filter AUS** |
| `leveling_tau_slow_s` | 0.0 | **Filter AUS** |
| `tip_angle_warn_deg` | 15.0 | wie Stufe 1 |
| `tip_angle_crit_deg` | 25.0 | wie Stufe 1 |

Mit `inner==outer` + `tau==0` + roll==pitch reduziert sich v2 **exakt** auf das heutige `_update_axis`
(resume ≥ D, stop < D ⇒ regelnd iff `|x| ≥ D`; `error = -m_fast = -measured`) ⇒ **Regressionsanker**
(Test „Back-Compat", §4). Die HW-Arbeitswerte (Hysterese/Filter an, per-Achse) kommen **nur** aus
`hw_balance.yaml`.

---

## 4. Tests-Liste (mit Begründung)

**Regler-Unit-Tests (`test_balance_controller`, ROS-frei — der Kern):**
| Test | Prüft |
|---|---|
| **Hysterese enter/exit** | regelt ab `outer`, stoppt erst bei `inner`; dazwischen Zustand gehalten (kein Toggle) |
| **Kein Rand-Chatter** | Signal oszilliert eng um `outer` → **kein** ständiges an/aus (der ursprüngliche Bug) |
| **Back-Compat-Degradation** | `tau=0` + `inner==outer` + roll==pitch → **bit-nah heutiges** Single-Totband-Verhalten (Regressionsanker) |
| **Dual-Tiefpass horizontal** | fast/slow EMA korrekt (α=dt/(τ+dt)); slow entscheidet resume, fast entscheidet stop |
| **Filter-Flag pro Achse (A)** | `apply_filter=False` (Residual) → m_fast=m_slow=measured (kein Filter); `=True` (roh) → gefiltert. terrain ⇒ pitch bypass, roll gefiltert |
| **Snap-Init (B)** | erstes Sample nach `reset()` → m_fast=m_slow=measured; Latch engagiert sofort bei `|x|≥outer` (kein τ-Verzug) |
| **Back-Compat-Schwelle (C)** | resume `≥outer` / stop `<inner`: bei `inner==outer` regelnd iff `|x|≥D` (== heute, keine Toggle-Lücke am Gleichstand) |
| **Gyro-D immer aktiv** | D wirkt auch im „nicht-regelnd"-Hold (E6), auf roher Rate |
| **`converged` neu** | True ⇔ beide Achsen nicht-regelnd; nach reset True |
| **Per-Achse-Unabhängigkeit** | roll-Gains ≠ pitch-Gains → getrennte Ausgänge; Default-symmetrisch = wie ein gemeinsamer Satz |
| **Clamp/Anti-Windup/Slew** | unverändert wirksam (aus Stufe 2 getragen) |

**Node-Tests (`test_leveling_node`):**
| Test | Prüft |
|---|---|
| **Startup-Grace mit v2-`converged`** | Tip-Netz bleibt unterdrückt solange regelnd, armt sauber wenn eingeschwungen (Safety!) |
| **Per-Achse-Params live + Validierung** | `inner ≤ outer`, `tau ≥ 0` reject; `_roll`/`_pitch` getrennt live tunbar (kein Skalar-Alias) |
| **Per-Achse Tip-Schwellen** | roll-Schwelle feuert bei kleinerem Winkel als pitch |
| **Filter-Flag-Durchreichung** | gait_node setzt filter_roll=True immer, filter_pitch=(mode≠terrain) → korrekter Pfad je Achse |

**Sim-Re-Verifikation (User, gegen Regression):**
| Test | Prüft |
|---|---|
| **Default = alt** | mit Default-Params (Back-Compat) verhält sich Stufe 2/3a/TF-2 wie sim-verifiziert (kein Regress) |
| **Hysterese im Stand** | statisches Leveln: kein Pendeln mehr an der Fenster-Kante |
| **terrain-Lauf (TF-2)** | roll→0/pitch→folgen weiter ok, Dämpfung wirkt, kein Doppelfilter-Artefakt |

**Bewusst NICHT (→ deferred / später):**
- **Adaptiver Slope-Schätzer** (D1) — erst nach HW-Knick-Messung.
- **Stufe-vs-Hang-Perfektion** (D2) — Stufe 4 (Fußkontakte).
- **State-abhängige Fenster** (D3) — erst bei HW-Bedarf.
- **HW-Tuning selbst** — das ist **6c/IP3 auf v2** (Folge-Schritt), nicht Stufe 7.

---

## 5. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
Stufe 7 (Balance-Regler v2):
- [ ] 7.1 BalanceController v2: per-Achse-State + Zwei-Fenster-Hysterese (resume >=outer / stop <inner) + Snap-Init (B) + Gyro-D immer aktiv (rohe Rate) + Back-Compat-Degradation (inner==outer, tau==0)
- [ ] 7.2 Dual-Tiefpass (fast/slow EMA) pro-Achse via apply_filter-Flag (A): roh -> gefiltert, Residual -> bypass; Stellgroesse-Eingang = m_fast (D)
- [ ] 7.3 Per-Achse-Params in gait_node (kp/ki/kd/inner/outer/slew/tau_fast/tau_slow je roll,pitch), KEIN Skalar-Alias + hw_balance.yaml auf _roll/_pitch migrieren (E/I) + live + Validierung (inner<=outer, tau>=0)
- [ ] 7.4 converged neu definiert (beide Achsen nicht-regelnd) + Startup-Grace/Tip-Netz-Gate geprueft
- [ ] 7.5 TipMonitor: tip_angle_warn/crit per Achse (Rate/Debounce gemeinsam)
- [ ] 7.6 Unit-Tests (Hysterese, kein Chatter, Back-Compat, Dual-TP, terrain-no-filter, Gyro-D, converged, per-Achse) gruen
- [ ] 7.7 Node-Tests (Startup-Grace v2, per-Achse live+Validierung, Filter-Flag-Pfad roll/pitch) gruen
- [ ] 7.8 colcon test hexapod_gait hexapod_kinematics + Lint gruen
- [ ] 7.9 README/Konzept-Update (hexapod_gait: v2-Regler, Hysterese, Dual-TP horizontal-only, per-Achse, mode-Pfad)
- [ ] 7.10 Sim-Re-Verify (User): Default=alt (kein Regress) + Hysterese im Stand + TF-2-Lauf
- [ ] 7.11 Projekt-Architektur-Doku nachziehen (s. Abschnitt 9)
- [ ] 7.12 kritische Self-Review-Tabelle
```

---

## 6. Offene Punkte — ENTSCHIEDEN

1. **Fast-Filter:** ✅ **ja** (volles Dual-Schema, per `tau_fast=0` abschaltbar). [User wollte Dual-Filter]
2. **Regelgröße-Eingang (D5):** ✅ **= `m_fast`** (geglättet wenn gefiltert, sonst == `measured`).
3. **State-abhängige Fenster (D3):** ✅ **ein Satz**; STANDING/WALKING-Fenster **deferred** (erst bei HW-Bedarf).
4. **Param-Namen/Alias:** ✅ **kein Alias** → `hw_balance.yaml` auf `_roll/_pitch` migrieren (E/I).
5. **Code-Default:** ✅ **= heute** (Hysterese/Filter aus), Fix lebt in `hw_balance.yaml` (E9, User-Entscheid).

**Verbleibend „später, kein Blocker":** sinnvolle `tau_fast/tau_slow`-**Startwerte** fürs Enablen (Sim,
werden auf HW nachgezogen); ob/wann **D1** (adaptiver Slope-Schätzer) und **D3** (state-Fenster)
gebaut werden → nach HW-Messung in 6c-auf-v2.

---

## 7. Sicherheit (CLAUDE.md §9)

- **Reiner Regler-Umbau, sim-baubar** — HW erst in 6c-auf-v2 (aufgebockt, Kill-Switch, reduzierte Rate).
- **`converged`/Startup-Grace ist sicherheitsnah** (Tip-Netz-Gate) → expliziter Node-Test (7.4/7.7).
- **Back-Compat-Default** stellt sicher, dass ein unkonfiguriertes v2 sich wie das sim-verifizierte
  System verhält — kein stilles Verhaltens-Delta.

---

## 8. Handoff / Anker (Code + Dateien)

- **Regler:** `hexapod_gait/hexapod_gait/balance_controller.py` (v2-Kern), `tip_monitor.py`
  (per-Achse-Schwellen), `slope_estimator.py` (unverändert; adaptiv = deferred D1).
- **ROS-Glue:** `gait_node.py` — `_update_leveling` (Filter-Flags roll/pitch durchreichen), Param-Deklaration/-Handler
  (`_on_param_change`), `_update_tip`/`_rebuild_tip_monitor`, `converged`-Nutzung (Startup-Grace).
- **Stellpfad:** `gait_engine._compute_leveled_ik` — **unverändert** (Korrekturen klein).
- **Tests:** `test_balance_controller.py`, `test_leveling_node.py`, `test_tip_monitor.py`.
- **HW-Gains danach:** `hexapod_gait/config/presets/hw_balance.yaml` (6c/IP3 auf v2 neu).
- **Folgestufe:** [`stage_6c_imu_hw_balance_tuning_plan.md`](stage_6c_imu_hw_balance_tuning_plan.md)
  (IP3 pausiert, nach Stufe 7 auf v2 neu).

---

## 9. Doku-Nachzug — NICHT VERGESSEN (Projekt-Architektur)

> **Diese Regler-Parameter + „wann muss ich hier ran?" gehören in die Projekt-Architektur-Doku**,
> damit bei späterer Fehlersuche (Pendeln, Zittern, Aufschwingen, „Roboter folgt Hang nicht",
> „kippt beim Laufen") jemand die **Stellschrauben findet** und weiß, **in welchen Fällen** man
> daran dreht. Nach der Implementierung (Bullet 7.11) nachziehen:

- **`project_architecture/ai_navigation.md`** — den A5-Abschnitt „IMU-Balance / Leveling / Kipp-
  Erkennung" erweitern um:
  - **v2-Regler-Konzept:** Zwei-Fenster-Hysterese, Dual-Tiefpass (**nur horizontal**), per-Achse
    (roll/pitch), Gyro-D-immer-aktiv, `converged`=nicht-regelnd.
  - **„Wann dran?"-Tabelle (Symptom → Stellschraube):**
    - *Pendeln/Aufschwingen im Stand* → `kd` hoch bzw. `kp/ki` runter; Fenster prüfen.
    - *Zittern/Summen* → `kd` runter (D rausch-verstärkend auf HW).
    - *Jagt Gang-Ripple beim Laufen* → `deadband_inner` über Ripple heben (ggf. state-abh. Fenster D3).
    - *Roll sensibler als Pitch* → per-Achse `_roll`-Werte enger/schneller + Tip-Schwelle kleiner.
    - *Ruck/Lurch am Knick (flach→Hang)* → adaptiver Slope-Schätzer (D1) erwägen; Slew prüfen.
    - *Fuß findet an Kante/Stufe keinen Boden* → **kein** Balance-Problem → Stufe 4 (Fußkontakte).
  - **Dateien-Zeiger:** `balance_controller.py` (Hysterese/Filter/Gains), `slope_estimator.py`
    (Hang-Schätzung/τ), `tip_monitor.py` (Kipp-Schwellen), `gait_node.py` (Params live +
    `_update_leveling`/`_update_tip`/`_update_slope_estimate`), `gait_engine._compute_leveled_ik`
    (Stellpfad), `hw_balance.yaml` (HW-Gain-Satz), `tools/leveling_envelope_check.py` (Clamp-Grenzen).
- **`project_architecture/architecture.md`** — falls dort die Regel-Kette beschrieben ist, den
  v2-Regler + horizontal/terrain-Filter-Pfad ergänzen.
- **`project_architecture/ai_navigation.md` §3-Tabelle** („ändere X → Datei/Test") — Zeile
  „IMU-Balance" um die v2-Dateien + `test_balance_controller` aktualisieren.

> Außerdem beim Stufen-Start: `imu_balance_progress.md` (IP3 ⏸️ „wartet auf Stufe 7" markieren,
> Stufe-7-Checkliste aufnehmen) und ggf. `PHASE.md` (A5-Zeile) — reine Status-Pflege.
