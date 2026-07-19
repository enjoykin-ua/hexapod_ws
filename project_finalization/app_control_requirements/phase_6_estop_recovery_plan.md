# Phase 6 — Recovery + Not-Halt (E-Stop) — §4-Plan

> **Ziel:** ein **scharfer Not-Halt** (E-Stop) aus der App, der den Roboter sofort stoppt/hält,
> und ein **Ein-Klick-Recovery**, das ihn ursachen-agnostisch aus der eingefrorenen Pose zurück in
> den **Stand** bringt — ohne System-Neustart ([D6]). ROS-Seite = ein Recovery-Service + eine
> latched Freeze-Gate; App-Seite = E-Stop-Button (scharf) + Recover-Button.
>
> **Seite:** ROS + App. **Status: 🟡 Plan.** Self-contained für einen frischen Chat.
> Contract: [`interface_contract.md`](interface_contract.md) (§2 + §6 `[TBD-Phase 6]`).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da, [E]):**
- **`/hexapod_safety_freeze`** (`std_srvs/Trigger`) — im **C++-Plugin `hexapod_hardware`**
  (`hexapod_system.cpp/.hpp`): setzt `safety_freeze_`-Flag → alle Joints halten ihre letzte PWM.
  **Nur HW** (das Plugin läuft im `real.launch.py`-Pfad; in Sim gibt es den Service nicht).
- **`/hexapod_safety_reset`** (`std_srvs/Trigger`, Plugin) — löst den Plugin-Freeze.
- **`gait_node._trigger_safety_freeze()`** — ruft das Plugin-`safety_freeze` bei IK-/Tip-/Slip-
  Ereignissen (fire-and-forget); der lokale Stop (Tick publiziert keine Trajektorie → JTC hält) ist
  ohnehin da. Setzt `self._safety_frozen = True` (heute nur fürs Status-Topic, **gated den Tick noch
  nicht**).

**Neu in Phase 6:**
1. **E-Stop app-tauglich + latched:** ein **gait_node-Freeze-Gate** — der Tick hält, solange
   `_safety_frozen` gesetzt ist (stoppt das Kommandieren, in Sim **und** HW), und der App-E-Stop
   setzt es (+ triggert den Plugin-Freeze auf HW).
2. **Recovery-Service** (`/hexapod_recover`, `std_srvs/Trigger`, im `gait_node`): Plugin-Freeze
   lösen → gait-Latches + Monitore reset → **Joint-Space-Ramp** aus der eingefrorenen Pose in den
   Stand ([D6]).

**Bewusst NICHT in Phase 6:**
- **Umgekippt/auf der Seite/zu steiler Hang aufrichten** — kann kein Bein-Ramp; **Mensch** stellt
  den Roboter grob aufrecht auf ebeneren Boden, *dann* Recover ([D6]-Grenze).
- **Scrape-/Kollisions-bewusster Rückweg** — Joint-Space-Ramp fährt beliebige Fuß-Bögen; auf flachem
  Boden + grob aufrecht unkritisch (v1).
- **Params fixen** — Recovery stellt nur den *Zustand* wieder her; bei weiter schlechten Params
  freezt er nach dem Loslaufen wieder (akzeptiert).
- **Audio/Kamera** — Phase 7.

---

## 1. Logik-Skizze / Pseudocode (ROS-Seite)

### 1a. Freeze-Gate im `gait_node._tick` (E-Stop wirksam machen)
Heute setzt `_trigger_safety_freeze` nur `_safety_frozen` (Status). Neu: **den Tick darauf gaten**,
damit ein Freeze **latched** hält (nicht auto-resumt, wenn die Ursache verschwindet — ein Not-Halt
soll bis zur bewussten Recovery halten, [D6]).
```python
def _tick(self):
    if self._safety_frozen:
        return                 # hält die letzte Pose (kein Publish); latched bis Recovery
    ...                        # (Rest unverändert)
```
⚠️ **Konsequenz:** die bisherigen Auto-Freezes (IK/Tip-Crit/Slip) werden damit **latched** statt
condition-based. Das ist gewollt (Safety-Freeze = bleibt bis Reset) — aber Verhaltensänderung, im
Self-Review + Tests prüfen. Siehe **Offener Punkt §4.1** (unified `_safety_frozen` vs. separates
`_estop_latched`).

### 1b. E-Stop-Service (app-facing)
**Entscheidung §4.2:** die App braucht einen E-Stop, der **in Sim UND HW** wirkt. Reines
Plugin-`safety_freeze` wirkt nur auf HW. Daher ein **gait_node-Service** (Vorschlag Name
`/hexapod_estop`, `std_srvs/Trigger` — oder Contract-konform `/hexapod_safety_freeze` in gait_node
spiegeln):
```python
def _on_estop(self, request, response):
    self._safety_frozen = True                 # gated den Tick (1a) → gait hält sofort
    self._trigger_safety_freeze()              # ruft zusätzlich das Plugin-safety_freeze (HW-PWM-Hold)
    response.success = True
    response.message = 'E-STOP — frozen (recover to resume)'
    return response
```

### 1c. Recovery-Service `/hexapod_recover` (`std_srvs/Trigger`, gait_node) — [D6]
Spiegelt `_on_stand_up` (Z. 2329), aber **ursachen-agnostisch** (jeder State) + räumt vorher auf.
Reuse: `_latest_joints` (Z. 863, vom `/joint_states`-Sub gepflegt) + `engine.start_ramp` (Z. 447 —
Smooth-Step-Joint-Space-Lerp **ohne IK** → kann kein Limit verletzen, [D6]).
```python
def _on_recover(self, request, response):
    if self._shutdown_latched:                 # wie _on_stand_up: nicht nach Shutdown
        response.success = False; response.message = 'shutdown latched'; return response
    if len(self._latest_joints) != len(HEXAPOD.legs):
        response.success = False; response.message = 'no complete /joint_states yet'; return response
    # 1) Plugin-Freeze lösen (nur HW; in Sim Service nicht da → skip wie _trigger_safety_freeze)
    if self._safety_reset_client.service_is_ready():
        self._safety_reset_client.call_async(Trigger.Request())
    # 2) gait-Latches + Monitore reset (ursachen-agnostisch)
    self._safety_frozen = False
    self._tip_crit_fired = False
    self._slip_freeze_fired = False
    self._balance.reset(); self._slope_est.reset()
    self._support_monitor.reset(); self._tip_monitor.reset()
    # 3) Joint-Space-Ramp aus der EINGEFRORENEN Ist-Pose in den Stand (kein IK, D6)
    t = time.monotonic() - self._t_start
    try:
        self._engine.start_ramp(self._latest_joints, t, self._recover_duration)
    except (ValueError, IKError) as exc:
        response.success = False; response.message = f'recover failed: {exc}'; return response
    response.success = True
    response.message = 'recovering — joint-space ramp to stand'
    return response
```
Neu nötig im `__init__`: `self._safety_reset_client = self.create_client(Trigger, '/hexapod_safety_reset')`
+ Param `self._recover_duration` (Default z.B. 3.0 s; eigener Param, damit unabhängig vom
`auto_standup_duration`). **NICHT `start_cartesian_standup`** (nutzt IK → könnte re-freezen); D6
verlangt Joint-Space.

### 1d. Warum das sicher ist ([D6])
`start_ramp` lerpt pro Gelenk zwischen zwei **gültigen** Posen (Ist-Pose ist real gefahren = gültig;
Stand-Pose per Definition gültig) → **konvexe Kombination kann kein Joint-Limit verletzen** → kein
IK, kein Re-Freeze-durch-Limit auf dem Rückweg.

**Verworfene Alternativen ([D6]):** Recovery = Hinsetzen (aus verkrümmter Pose evtl. schlechter);
Cartesian-Rückweg (IK → Re-Freeze-Risiko).

---

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Warum |
|---|---|---|
| **T6.1** E-Stop-Service → `_safety_frozen` True + Tick hält (kein `joint_trajectory`-Publish) | Freeze-Gate | Not-Halt wirkt |
| **T6.2** E-Stop im WALKING → Roboter stoppt sofort + bleibt (latched, resumt nicht) | latched Freeze | Kern-Deliverable |
| **T6.3** Recovery aus eingefrorener Pose → Joint-Space-Ramp → STANDING (Sim) | Recovery-Kern | [D6] |
| **T6.4** Recovery-Ramp verletzt **kein** Joint-Limit (Unit: Lerp zweier gültiger Posen) | Sicherheit | D6-Kernargument |
| **T6.5** Recovery ursachen-agnostisch: aus WALKING/STANDING/nach-Tip-Freeze | any-state | [D6] |
| **T6.6** Latches/Monitore nach Recovery zurückgesetzt (tip/slip/balance/support) | sauberer Wiederanlauf | kein Sofort-Re-Freeze |
| **T6.7** `unit`: `_on_recover` ohne komplette `_latest_joints` → sauberer Reject | Robustheit | keine halbe Ramp |
| **T6.8 (HW, User)** E-Stop → PWM-Hold am echten Roboter; Recover → smooth in den Stand | HW-Verifikation | am fertigen Roboter |
| **T6.9** colcon test + Lint grün, Walking-Regression unverändert | keine Regression | §4-Pflicht |

**Bewusst offen/später:** Aufrichten aus Kipplage (Mensch); scrape-freier Rückweg; Recovery-Ramp-
Dauer final justieren (Live); E-Stop-Hardware-Taster (falls je gewünscht) — App-Button reicht v1.

---

## 3. Progress-Checkliste (→ `phase_6_..._progress.md`, Done-Vertrag)
```
Phase 6 (Recovery + Not-Halt):
- [ ] P6.1 [ROS] gait_node _tick auf _safety_frozen gaten (latched Freeze) + Auto-Freeze-Semantik geprueft (T6.1)
- [ ] P6.2 [ROS] E-Stop-Service (gait_node, Trigger): _safety_frozen=True + Plugin-safety_freeze (T6.2)
- [ ] P6.3 [ROS] /hexapod_recover-Service: Plugin-reset + Latches/Monitore-reset + start_ramp (Joint-Space) (T6.3/T6.5)
- [ ] P6.4 [ROS] _recover_duration-Param + _safety_reset_client; NICHT cartesian (Joint-Space, D6)
- [ ] P6.5 [ROS] Unit-Tests: Ramp-kein-Limit (T6.4), reject-ohne-joints (T6.7), Reset-Latches (T6.6)
- [ ] P6.6 [ROS] Contract §2/§6 festgezurrt (E-Stop-Service-Name + /hexapod_recover), Version-Bump
- [ ] P6.7 [ROS] colcon test + Lint gruen + Walking-Regression (T6.9)
- [ ] P6.8 [App] E-STOP-Button scharf (reservierter Slot aus P4) -> E-Stop-Service; deutlich/rot
- [ ] P6.9 [App] Recover-Button -> /hexapod_recover; Status zeigt frozen/recovering (aus /hexapod/status.safety_frozen)
- [ ] P6.10 [ROS] Self-Review + Doku (README/architecture-Nachzug, test_commands)
- [ ] P6.11 [Integration, User+App/HW] E-Stop stoppt + Recover steht wieder auf (Sim, dann echter Roboter T6.8)
```

---

## 4. Offene Punkte / Risiken (vor Code entscheiden)
1. **Unified `_safety_frozen`-Latch vs. separates `_estop_latched`.** Der Tick auf `_safety_frozen`
   zu gaten macht **alle** Freezes (IK/Tip/Slip + E-Stop) latched (bleiben bis Recovery). **Empfehlung:
   unified** — ein Safety-Freeze SOLL bis zur bewussten Recovery halten ([D6]-Geist); `_safety_frozen`
   existiert + wird schon im Status publiziert. Risiko: Verhaltensänderung der Auto-Freezes (heute
   condition-based) → Walking-Regression-Test (T6.9) + Self-Review.
2. **E-Stop-Service-Name.** `/hexapod_estop` (neu, klar) **vs.** `/hexapod_safety_freeze` in gait_node
   spiegeln (Contract §2 nennt letzteres schon als App-Not-Halt — aber das ist der Plugin-Service).
   **Empfehlung:** neuer `/hexapod_estop` im gait_node (der intern das Plugin-`safety_freeze` ruft) →
   ein App-Ziel, wirkt Sim+HW; Contract §2 entsprechend präzisieren.
3. **`_recover_duration`** Default (Vorschlag 3.0 s) — Live justierbar.
4. **Recovery-Startpose = Ist-Pose aus `_latest_joints`.** Bei sehr alter/stiller `/joint_states`
   (E-Stop hielt lange) ist die Ist-Pose weiterhin gültig (Roboter hat sich nicht bewegt) → ok.

---

## 5. App-Seiten-Brief (self-contained) — E-Stop + Recover

**Interface = `interface_contract.md §2/§6`** (nach P6.6 festgezurrt). Alles über rosbridge `call_service`.

- **E-STOP-Button** (der in Phase 4 **reservierte** Slot, unten rechts): groß, rot, immer sichtbar →
  `call_service` auf den E-Stop-Service (`std_srvs/Trigger`). Nach Auslösen: Overlay zeigt **frozen**
  (aus `/hexapod/status.safety_frozen == true`).
- **Recover-Button** (erscheint/aktiv, wenn `safety_frozen`): → `/hexapod_recover` (`std_srvs/Trigger`).
  Danach zeigt der Status `state: STARTUP_RAMP` → `STANDING`. Kurzer Hinweis-Text: „Roboter grob
  aufrecht auf ebenen Boden stellen, dann Recover" (D6-Grenze: kein Aufrichten aus Kipplage).
- **Kein** Dead-Man o. Ä. — E-Stop ist ein einzelner, bewusster Tap; Recover ebenso.
- **Bewusst noch NICHT:** Kipp-/Recovery-Automatik, Hardware-Taster.

---

## 6. Contract-Touchpoints (→ festzurren)
- **§2:** E-Stop-Service-Name präzisieren (App → gait_node, wirkt Sim+HW; ruft intern Plugin-Freeze).
  `/hexapod_safety_reset` bleibt Plugin (Recovery ruft es intern).
- **§6:** `/hexapod_recover` (`std_srvs/Trigger`) festzurren — der Ein-Klick-Recovery ([D6]).
  Version-Bump (v0.10).

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_6_..._progress.md` + `phase_6_..._test_commands.md`.
- `architecture.md` §4 (neue Services) + `ai_navigation.md` (E-Stop/Recovery-Naht).
- App-`CLAUDE.md`-Zeile „Aktuell: Phase 6".

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

> Alle Zeilennummern gegen `src/hexapod_gait/hexapod_gait/gait_node.py` bzw. `gait_engine.py`
> (Stand dieser Doku) — vor dem Edit per grep gegenchecken.

### Schritt 1 — Freeze-Gate im Tick
`gait_node._tick` (def bei ~Z. 1573): als **erste** Zeile im Tick `if self._safety_frozen: return`.
`_safety_frozen` existiert (Init ~Z. 965, gesetzt in `_trigger_safety_freeze` ~Z. 1766).

### Schritt 2 — E-Stop-Service
Im `__init__` (bei den anderen `create_service`, z.B. neben `/hexapod_stand_up` ~Z. 1274):
```python
self._estop_service = self.create_service(Trigger, '/hexapod_estop', self._on_estop)
```
`_on_estop` = Pseudocode §1b. (`Trigger` ist importiert.)

### Schritt 3 — Recovery-Service + Client + Param
- `__init__`: `self._safety_reset_client = self.create_client(Trigger, '/hexapod_safety_reset')`
  (Muster = `_safety_freeze_client` ~Z. 843).
- `declare_parameter('recover_duration', 3.0)` → `self._recover_duration`.
- `self.create_service(Trigger, '/hexapod_recover', self._on_recover)`.
- `_on_recover` = Pseudocode §1c. **`start_ramp`** (nicht cartesian). Monitore-Reset:
  `self._balance.reset()`, `self._slope_est.reset()`, `self._support_monitor.reset()`,
  `self._tip_monitor.reset()` (existieren alle — vgl. Aufrufe in `_update_leveling`/`_update_tip`/
  Slip-Logik ~Z. 1826/1925/2012).

### Schritt 4 — Muster & Reuse
- **`_on_stand_up`** (~Z. 2329) = das Struktur-Muster (State-/joints-Check, `t = now - self._t_start`,
  `start_ramp(self._latest_joints, t, dur)`). Recovery = wie das, aber ohne den `state == SAT`-Check
  (ursachen-agnostisch) + mit dem Aufräumen (Schritt-3-Punkte 1+2) davor.
- **`engine.start_ramp`** (gait_engine ~Z. 447): Joint-Space-Smooth-Step-Lerp `_latest_joints` →
  Stand-Pose, `_state = STARTUP_RAMP`, auto-`STANDING` nach Ablauf. Genau der D6-Rückweg.

### Schritt 5 — Tests
- `test/test_recover.py` (hexapod_gait): (a) `_on_recover` setzt Latches zurück + ruft `start_ramp`
  (Fake-Engine o. echte Engine, prüfe `state == STARTUP_RAMP`); (b) reject ohne komplette
  `_latest_joints`; (c) Ramp-kein-Limit = Engine-Unit: nach `start_ramp` alle Zwischen-Posen
  (Sample über Progress 0..1) innerhalb der URDF-Limits (Reuse `test_per_leg_limits`-Limitquelle).
- Regression: die bestehenden gait-Tests + der neue Tick-Gate dürfen Walking nicht brechen.

### Schritt 6 — Build + Sim-Test
```bash
colcon build --packages-select hexapod_gait && source install/setup.bash
# Sim-Stack hoch (ramp_walk oder always_on+bringup_start), aufstehen, laufen, dann:
ros2 service call /hexapod_estop std_srvs/srv/Trigger {}     # Roboter friert ein (haelt)
ros2 topic echo /hexapod/status --once                        # safety_frozen: true
ros2 service call /hexapod_recover std_srvs/srv/Trigger {}   # Joint-Space-Ramp -> STANDING
```
### App-Seite
Siehe §5. Video-/Status-URLs unverändert; nur zwei neue `call_service`-Ziele + die frozen/recovering-
Anzeige aus `/hexapod/status.safety_frozen`.
