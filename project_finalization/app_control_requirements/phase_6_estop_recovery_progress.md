# Phase 6 — Recovery + Not-Halt (E-Stop) — Progress (ROS-Seite)

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus
> [`phase_6_estop_recovery_plan.md`](phase_6_estop_recovery_plan.md) §3.
> **Offene §4-Punkte entschieden** (User-Freigabe): §4.1 = **unified `_safety_frozen`**,
> §4.2 = **neuer `/hexapod_estop`**. Status: 🟢 **FINALISIERT (Sim-komplett)** — ROS-Seite
> (468/0/0/28 Tests) + App-Seite + **Sim-E2E** (ROS ↔ App) verifiziert; Contract v0.10. **Einziger
> deferierter Punkt: HW-Verifikation T6.8** am echten Roboter (Defer-Pattern wie Phase-3-DK4).

```
Phase 6 (Recovery + Not-Halt):
- [x] P6.1 [ROS] gait_node _tick auf _safety_frozen gaten (latched Freeze) + Auto-Freeze-Semantik geprueft (T6.1 ✅ unit)
- [x] P6.2 [ROS] E-Stop-Service /hexapod_estop (gait_node, Trigger): _safety_frozen=True + Plugin-safety_freeze (T6.2 ✅ unit)
- [x] P6.3 [ROS] /hexapod_recover-Service: Plugin-reset + Latches/Monitore-reset + start_ramp (Joint-Space) (T6.3/T6.5 ✅ unit)
- [x] P6.4 [ROS] recover_duration-Param (nicht standing_only) + _safety_reset_client; NICHT cartesian (Joint-Space, D6)
- [x] P6.5 [ROS] Unit-Tests: Ramp-kein-Limit (T6.4), reject-ohne-joints (T6.7), Reset-Latches (T6.6) — test_recover.py, 14 Tests
- [x] P6.6 [ROS] Contract §2/§6 festgezurrt (/hexapod_estop + /hexapod_recover), Version-Bump v0.10
- [x] P6.7 [ROS] colcon test (440 passed) + Lint gruen; Walking-Regression unit-grün (Live-T6.9 = User)
- [x] P6.8 [App] E-STOP-Button scharf (reservierter Slot aus P4) -> /hexapod_estop; deutlich/rot (App gebaut + E2E ✅)
- [x] P6.9 [App] Recover-Button -> /hexapod_recover; Status zeigt frozen/recovering (aus /hexapod/status.safety_frozen) (E2E ✅)
- [x] P6.10 [ROS] Self-Review + Doku (README/architecture/ai_navigation-Nachzug, Contract v0.10, test_commands)
- [~] P6.11 [Integration, User+App] **Sim-E2E ✅** (App friert ein, CLI-Freeze zeigt App frozen, Recover steht wieder auf); **HW-Teil T6.8 offen** (echter Roboter)
```

> **P6.8/P6.9** = **Android-Session** (zweiter Kontext, hexapod_app-Repo) gegen Contract §2/§6/§5 —
> **nicht** ROS-Seite. **P6.11** = User (Sim-E2E) bzw. echter Roboter (T6.8).

---

## Stand — ROS-Seite implementiert + statisch/unit verifiziert

**Fertig + verifiziert** (`colcon build` grün, `colcon test` **440 passed / 28 skipped / 0 failures**,
flake8 + pep257 clean; 14 neue Tests in `test_recover.py`):

- **`hexapod_gait/gait_node.py`:**
  - Freeze-Gate `if self._safety_frozen: return` als erste Zeile in `_tick` → latched Freeze (Sim+HW).
  - `_on_estop` (`/hexapod_estop`, Trigger): `_safety_frozen=True` + `_trigger_safety_freeze()`.
  - `_on_recover` (`/hexapod_recover`, Trigger): Reject bei `_shutdown_latched` / unvollständigem
    `_latest_joints`; sonst `_safety_reset_client` (guarded) → Latches + 4 Monitore reset →
    `engine.start_ramp` (Joint-Space) in den Stand.
  - `__init__`: `_safety_reset_client` + `_safety_reset_logged_unreachable`; beide Services in
    `_cb_group` (MutuallyExclusive = Tick-Gruppe → kein Race).
  - Neuer Param `recover_duration` (`_GAIT_PARAMS`, Default 3.0 s, fp_range 1.0–15.0, **nicht**
    standing_only) + init-read + Apply-Handler (live justierbar).
- **`hexapod_gait/test/test_recover.py`** (neu, 14 Tests): 3 Engine (T6.4 Ramp-in-limits aus
  Mid-Walk + near-limit Pose, Endpunkt=Stand) + 11 Node (E-Stop setzt Freeze, Gate blockt/passiert
  Tick, Recovery aus STANDING/WALKING, Joint-Space-nicht-cartesian, Reset-Latches+Monitore T6.6,
  Reject-ohne-joints T6.7, Reject-shutdown-latched, recover_duration-Range).

**Doku nachgezogen:** Contract **v0.10** (§2 Services + App-Nutzung + §6 erledigt + §6a safety_frozen);
`hexapod_gait/README.md` (Tip-CRIT-Latch-Note + E-Stop/Recovery-Services); `architecture.md` §3/§4;
`ai_navigation.md` (neuer „E-Stop / Recovery ändern"-Eintrag); `phase_6_..._test_commands.md`.

**Sim-Live-Test (User) — ✅ erfolgreich:** erst die reinen ROS-Befehle (estop →
`/hexapod/status.safety_frozen:true` latched → recover → STARTUP_RAMP→STANDING), dann der
**End-to-End mit der echten App**: E-Stop aus der App friert ein, ein **hier per CLI erzwungener**
`/hexapod_estop` wird in der App als frozen + Recover-Button angezeigt (beweist die
`/hexapod/status.safety_frozen`-Kopplung), Recover aus der App bringt ihn zurück nach STANDING.
Damit sind **P6.8/P6.9 (App) + der Sim-Teil von P6.11** verifiziert.

**Offen:** nur noch **P6.11 HW-Teil = T6.8** am echten Roboter (PWM-Hold beim E-Stop + smooth
Joint-Space-Ramp beim Recover), User — Sim-Seite (ROS + App) ist komplett.

### Implementierungs-Kern (verifiziert gegen den Code)

- **Freeze-Gate** (`gait_node._tick`, [gait_node.py:1588](../../src/hexapod_gait/hexapod_gait/gait_node.py#L1588)):
  `if self._safety_frozen: return` als **erste** Zeile → latched Freeze (Sim + HW). Verhaltensänderung:
  die bisherigen Auto-Freezes (Tip-CRIT [1659], IK-'joint limit' [1723], Slip [2044]) werden damit
  latched statt condition-based (§4.1 unified, gewollt).
- **E-Stop-Service** `/hexapod_estop` (`std_srvs/Trigger`, gait_node): `_safety_frozen=True` +
  `_trigger_safety_freeze()` (Plugin-PWM-Hold auf HW, in Sim skip via `service_is_ready()`-Guard).
- **Recovery-Service** `/hexapod_recover` (`std_srvs/Trigger`, gait_node): Reject bei `_shutdown_latched`
  bzw. unvollständigem `_latest_joints`; sonst Plugin-Freeze lösen (`_safety_reset_client`, guarded) →
  Latches (`_safety_frozen`, `_tip_crit_fired`, `_slip_freeze_fired`) + Monitore (`_balance`,
  `_slope_est`, `_support_monitor`, `_tip_monitor`) reset → **`engine.start_ramp`** (Joint-Space, kein
  IK, kein Re-Freeze — D6) aus der eingefrorenen Ist-Pose in den Stand.
- **Neu im `__init__`:** `_safety_reset_client = create_client(Trigger, '/hexapod_safety_reset')`
  (Muster = `_safety_freeze_client` [844]); `declare_parameter('recover_duration', 3.0)`.

### D6-Sicherheit (verifiziert)

- `start_ramp` lerpt rein im Joint-Space zwischen zwei **gültigen** Posen → konvexe Kombination pro
  Gelenk kann kein Limit verletzen; kein Per-Tick-IK während der Ramp.
- Während der Recovery-Ramp ist der State **STARTUP_RAMP** → Tip-Eval (nur STANDING/WALKING) und Slip
  (nur WALKING) feuern **nicht** → **kein Re-Freeze auf dem Rückweg**.

---

## Self-Review (P6.10)

| # | Punkt | Status |
|---|---|---|
| 1 | Freeze-Gate = erste Tick-Zeile → returnt vor jedem Publish; `_publish_status` (eigener Timer) läuft weiter → Overlay zeigt `safety_frozen` | OK |
| 2 | §4.1 unified: Auto-Freezes (Tip/Slip/IK-joint-limit) werden latched. Normal-Walking setzt `_safety_frozen` NUR über `_trigger_safety_freeze` (echte Fehler-Pfade); out-of-reach triggert es nicht → self-heilt weiter | OK (unit); 🟡 Live-T6.9 = User |
| 3 | Recovery-Ramp = Joint-Space (`start_ramp`), kein IK → kein Limit-Bruch, kein Re-Freeze (T6.4: 21 Samples aus Mid-Walk + near-limit in-limits) | OK |
| 4 | Während Recovery-Ramp State=STARTUP_RAMP → Tip (STANDING/WALKING-only) + Slip (WALKING-only) feuern nicht → kein Re-Freeze auf dem Rückweg | OK |
| 5 | Services in `_cb_group` (MutuallyExclusive = Tick-Gruppe) → kein Race auf `_safety_frozen`/Engine/`_latest_joints` | OK |
| 6 | `_safety_reset_client` guarded (`service_is_ready()`) → in Sim ohne Plugin skip + einmal WARN; gait-Reset wirkt Sim+HW | OK |
| 7 | Recovery ursachen-agnostisch (Reject nur bei `_shutdown_latched` / unvollständigem `_latest_joints`) — T6.5 aus WALKING + STANDING verifiziert | OK |
| 8 | Latches (`_safety_frozen`/`_tip_crit_fired`/`_slip_freeze_fired`) + 4 Monitore reset (T6.6, MagicMock-verifiziert) | OK |
| 9 | `recover_duration` NICHT standing_only (Recovery aus jedem State), live justierbar, range-validiert | OK |
| 10 | E-Stop-Name `/hexapod_estop` ≠ Plugin-`/hexapod_safety_freeze` → keine Zwei-Server-Kollision auf HW (§4.2) | OK |
| 11 | HW-Ordering: `_safety_reset` (async, ~ms) VOR `start_ramp`; Ramp startet smooth-step bei ~0 Geschwindigkeit → früh evtl. vom Plugin verworfene Ticks unkritisch (3 s Ramp holt auf) | 🟡 vormerken (HW-T6.8 beobachten) |
| 12 | `_sensor_health_monitor` + `_contact_diag` bewusst NICHT im Recovery-Reset: sensor_health = echter Fault soll persistieren (Bein bleibt maskiert bis gesund), contact_diag = nur Diagnose | 🟡 bewusst (Plan-4-Monitore) |
| 13 | Recovery aus SAT (nicht latched) steht auf: cause-agnostisch → Stand (D6-Geist); latched Shutdown wird abgelehnt (kein ungewolltes Aufstehen eines abgeschalteten Roboters) | OK |
| 14 | Fail-Pfad `start_ramp` raise: praktisch unerreichbar (duration≥1.0 validiert, Stand-Pose gültig); defensiv `_safety_frozen=True` re-armed → Roboter bleibt geschützt | 🟢 später (unreachable) |
| 15 | colcon build + 440 Tests + flake8 + pep257 grün; keine Unit-Regression | OK |

**Keine 🔴.** Die 🟡 sind bewusste v1-Grenzen bzw. HW-Live-Beobachtungspunkte (T6.8/T6.9 = User),
die 🟢 ein praktisch unerreichbarer Defensiv-Pfad. Keine Fixe nötig vor der Fertig-Meldung.

---

## Design-Entscheidungen (mit Alternativen)

- **§4.1 unified `_safety_frozen`** (nicht separates `_estop_latched`): ein Latch, ein Reset-Pfad
  (Recovery); deckt sich mit dem HW-Plugin (latcht bis `_reset`). Verworfen: separates Flag → zwei
  mentale Modelle + die Sim-auto-resume-vs-HW-Plugin-latch-Inkonsistenz bliebe.
- **§4.2 neuer `/hexapod_estop`** (nicht `/hexapod_safety_freeze` spiegeln): vermeidet die
  Zwei-Server-auf-einem-Namen-Kollision auf HW; ein App-Ziel Sim+HW. Verworfen: Namens-Spiegelung
  (nicht-deterministisches Service-Routing auf HW).
- **Recovery = `start_ramp` (Joint-Space), NICHT `start_cartesian_standup`** ([D6]): Cartesian nutzt
  IK → könnte re-freezen; Joint-Space-Lerp zweier gültiger Posen ist re-freeze-frei.
- **`_recover_duration` eigener Param** (Default 3.0 s), entkoppelt von `auto_standup_duration` —
  Recovery-Rückweg live justierbar, ohne den Boot-Standup zu beeinflussen.
