# B1 — Hinsetz-/Abschalt-Sequenz — detaillierter Sub-Stage-Plan

> **Status:** ⚪ Plan zur Freigabe (CLAUDE.md §4: Plan → Freigabe → Code → Tests → Self-Review).
> Block-Kontext + abgehakte Vor-Entscheidungen: [`B_lokomotion_kern.md`](B_lokomotion_kern.md) §B1.
> Architektur/Validierungs-Gates: [`../project_architecture/ai_navigation.md`](../project_architecture/ai_navigation.md).
> Test-Anleitung (vor Code skizziert, nach Code final): `B1_sitdown_test_commands.md`.

---

## 0. Ziel (1 Satz)

Kontrolliertes, sicheres **Hinsetzen** (Umkehrung des Aufstehens) + zwei Endmodi
(**Rest** = bestromt sitzen, später wieder aufstehen; **Shutdown** = sitzen + Relay-Aus,
terminal), damit auf echtem Boden kein „Strom-weg → Servos zentrieren → Roboter kippt" passiert.

---

## 1. Logik-Skizze / Pseudocode (mit Begründung pro Design-Entscheidung)

### 1.1 Ablauf (Umkehrung Aufstehen+Reposition)

Start nur aus **STANDING** (Walk-Pose: `radial_distance` 0.215 @ `body_height` −0.120).

```
start_sitdown(t):                       # nur erlaubt wenn state == STANDING
    # Phase 1 — Reposition AUS (Füße raus): radial → standup_radial @ body_height
    start_reposition(t, from=radial_distance, to=standup_radial_distance,
                     after=SITDOWN_LOWER)   # ← richtungs-agnostisch, Reuse
    # → State REPOSITION; bei progress>=1 NICHT STANDING, sondern Continuation
    #   in SITDOWN_LOWER (siehe _finish_reposition).
```

**Warum erst Füße RAUS, dann absenken?** Exakt der Grund, warum der Standup mit der
*breiten* Pose (`standup_radial` 0.295) aufsetzt: Den Körper an der *engen* Walk-Pose
(0.215) bis auf Bauchhöhe abzusenken zwingt Femur/Tibia über die URDF-Limits (genau der
2.3-Befund). Also Reverse: erst auf 0.295 weiten, dann absenken. = Reverse der
Standup-Kette (Touchdown-Pose → Push), Schritt für Schritt rückwärts.

```
SITDOWN_LOWER (reverse-kartesisch, Füße x/y FIX @ standup_radial):
    progress = (t - t0) / sitdown_lower_dur          # sitdown_lower_dur = sitdown_duration * sitdown_lower_fraction
    z = body_height + (body_height_start - body_height) * smoothstep(progress)
    foot[leg] = (standup_radial, 0, z)   → IK (limit-checked)
    progress>=1 → start_sitdown_flatten(t)
```
= **exakte Umkehrung** der CARTESIAN_STANDUP Phase-2-Push (x/y fix, nur body_height rampt).
`body_height_start` (−0.0135, Bauch am Boden) wird **wiederverwendet** (kein neuer Wert).

```
SITDOWN_FLATTEN (Joint-Space-Lerp zur Boot-/Spawn-Pose):
    start = IK(standup_radial, 0, body_height_start)   # = Lower-Endpose, deterministisch
    target = rest_joints  (= Boot-/Spawn-Pose je Bein; Fallback rad 0)
    progress = (t - t0) / sitdown_flatten_dur          # = sitdown_duration * (1 - sitdown_lower_fraction)
    angle[leg] = lerp(start, target, smoothstep(progress))   # KEIN IK
    progress>=1 → state = SAT (hält rest_joints)
```
**Zielpose = Boot-/Spawn-Pose (User 2026-06-03, Korrektur des Q2-Irrtums):** Der Roboter endet
in **genau der Pose, in der er gespawnt/gebootet ist** (Beine **hoch**), NICHT flach. Der Node
schneidet die erste vollständige `/joint_states` (Spawn-Pose) mit und übergibt sie als
``rest_joints``. Bauch trägt, Beine in der Luft → das passive Hinlegen der Beine passiert erst
beim **Relay-Aus** (Servos schlaff → Beine fallen). ⚠️ **rad 0 ist NICHT „Beine hoch":** laut FK
ist rad 0 das Bein *horizontal gestreckt* (Fuß auf Coxa-Höhe) — genau das ursprünglich falsch
gewählte Ziel. ``rest_joints=None`` → Fallback rad 0 (nur Engine-Default ohne Node).
**Warum Joint-Space, kein IK?** Joint-Space-Lerp zwischen zwei in-limit-Posen bleibt
**box-konvex in-limit** → trivial limit-sicher, kein Reach-Problem nahe Singularität.
Mirror von STARTUP_RAMP.

```
SAT (terminal-idle, bestromt):
    compute_joint_angles → konstant rest_joints (Boot-Pose) je Bein halten, kein IK
    set_command → cmd_vel ignorieren
```

### 1.2 Aufstehen aus SAT (start-pose-agnostisch)

`start_cartesian_standup` ist bereits start-pose-agnostisch (FK'd die übergebenen
`start_joints`). Aus SAT (rad 0) heraus aufgerufen: Phase 1 Touchdown bewegt die Füße von
rad-0 (≈Coxa-Höhe) nach (standup_radial, 0, body_height_start) runter+raus, Phase 2 Push hoch,
dann ggf. Reposition → STANDING. **Kein neuer Code in der Engine** — nur Node ruft es mit den
aktuellen joint_states auf.

### 1.3 State-Machine-Erweiterung (Engine)

Neu: `STATE_SITDOWN_LOWER`, `STATE_SITDOWN_FLATTEN`, `STATE_SAT`.
Phase 1 nutzt den **bestehenden** `STATE_REPOSITION` (direction-agnostic gemacht).

```
STANDING --sit_down--> REPOSITION(after=SITDOWN_LOWER) --auto--> SITDOWN_LOWER
       --auto--> SITDOWN_FLATTEN --auto--> SAT
SAT --stand_up--> CARTESIAN_STANDUP --> (REPOSITION) --> STANDING
SAT/STANDING --shutdown--> (sit falls STANDING) --> SAT + Relay-Aus (terminal)
```

`set_command` ignoriert cmd_vel in allen vier neuen/erweiterten States
(REPOSITION ist schon drin; SITDOWN_LOWER/FLATTEN/SAT ergänzen).

### 1.4 Reuse von `start_reposition` (richtungs-agnostisch)

`start_reposition(t, from_radial=None, to_radial=None, after=STATE_STANDING)`:
- Defaults (None) → wie bisher `standup_radial → radial` (Standup-Pfad **unverändert**,
  test_reposition.py bleibt grün).
- Sit-down ruft mit `from=radial, to=standup_radial, after=SITDOWN_LOWER`.
- `_finish_reposition(t)`: `after==SITDOWN_LOWER` → `start_sitdown_lower(t)` + dessen Angles;
  sonst `STATE_STANDING` (Default, exakt heutiges Verhalten). Coupling = **ein** Conditional.

### 1.5 Node-Glue (gait_node)

- **3 Services** (`std_srvs/Trigger`):
  - `/hexapod_sit_down` — nur STANDING → `engine.start_sitdown(t)`; setzt `_relay_off_after_sat=False`. Endzustand SAT (bestromt). Return sofort (Sequenz läuft über Ticks).
  - `/hexapod_stand_up` — nur SAT **und nicht** `_shutdown_latched` → `engine.start_cartesian_standup(latest_joints, …)` → STANDING. Bei gesetztem Latch: Reject mit Meldung „erst Relay-On/Reboot".
  - `/hexapod_shutdown` — STANDING **oder** SAT → falls STANDING erst `start_sitdown`; `_relay_off_after_sat=True`. Wenn schon SAT: sofort Relay-Aus. Setzt nach erfolgtem Relay-Aus `_shutdown_latched=True` (terminal, Entscheidung Frage 2/Var 1).
- **Relay-Aus** (B1.5): Client auf `/hexapod_relay_set` (`std_srvs/SetBool`), `data=false`.
  Pattern wie `_trigger_safety_freeze`: `service_is_ready()` → sonst einmal WARN + skip (Sim
  hat kein Plugin). Gefeuert **einmal** im `_tick`, sobald `state==SAT` und `_relay_off_after_sat`.
- **Comms-Loss-Fail-safe** (B1.6, opt-in): Param `comms_loss_sitdown_timeout` (Default **0=aus**).
  Im `_tick`: wenn >0 **und** `_last_cmd_time is not None` **und** `(now-_last_cmd_time) >
  timeout` **und** `state==STANDING` **und** nicht schon im Sit-down/SAT → `start_sitdown` (Rest).
  - Gate auf `STANDING`: aus WALKING erst stoppen — der bestehende `cmd_vel_timeout` (0.5 s ≪
    comms_loss z.B. 5 s) bringt ihn über STOPPING→STANDING, *dann* greift der Fail-safe.
  - `_last_cmd_time is None` (nie cmd_vel empfangen) → **nicht** triggern (kein false-fire in
    Sim/manuell). Idle-Controller autorepeatet cmd_vel=0 → kein Timeout; echtes Disconnect →
    cmd_vel verstummt → Timeout.
- **latest_joints**: `_on_joint_states` aktualisiert künftig **immer** ein `self._latest_joints`
  (vollständiges Tripel-Dict), auch nach `_ramp_triggered` — der stand_up-Service braucht die
  aktuelle Pose. (Boot-Ramp-Einmal-Trigger bleibt unberührt.)

### 1.6 Neue/erweiterte Params (wertneutral, in `_GAIT_PARAMS`)

| Param | Default | Range/Step | standing_only | Zweck |
|---|---|---|---|---|
| `sitdown_duration` | 4.0 | (1.0, 15.0, 0.1) | nein | Dauer Phase 2+3 (Lower+Flatten) |
| `sitdown_lower_fraction` | 0.6 | (0.1, 0.9, 0.05) | nein | Anteil davon auf Lower (Rest Flatten) |
| `comms_loss_sitdown_timeout` | 0.0 | (0.0, 30.0, 0.5) | nein | 0=aus; sonst Fail-safe-Schwelle (s) |

**Reuse (kein neuer Wert):** `standup_radial_distance`, `radial_distance`, `body_height`,
`body_height_start`, `reposition_cycle_time` (=Phase-1-Dauer), `step_height` (Reposition-Hub).

---

## 2. Tests-Liste (+ Begründung, + was bewusst NICHT)

**Engine-Unit (`test/test_sitdown.py`, pytest, kein rclpy — Stil wie `test_reposition.py`):**
1. `test_sitdown_only_from_standing` — start_sitdown aus WALKING/REPOSITION/SAT = No-op/Reject.
2. `test_sitdown_phase1_widens_feet` — Reposition-aus: Füße radial→standup_radial, max 3 in Luft, beide Tripod-Gruppen heben.
3. `test_sitdown_full_path_in_limits` — alle Phasen über sampled t: kein IKError (URDF-Limits).
4. `test_sitdown_lower_xy_fixed_z_monotonic` — Phase 2: x/y konstant @ standup_radial, z monoton body_height→body_height_start.
5. `test_sitdown_flatten_ends_rad_zero` — Endpose alle 18 Joints == (0,0,0); Transition belly→rad0 in-limit (box-konvex).
6. `test_sitdown_ends_in_sat` — Endzustand == SAT.
7. `test_cmd_vel_ignored_in_sitdown_and_sat` — cmd_vel kippt keinen Sit-down/SAT-State auf WALKING.
8. `test_standup_from_sat_in_limits` — start_cartesian_standup aus rad-0: Pfad in-limit, endet STANDING.
9. `test_sitdown_value_neutral` — andere radii (0.28↔0.24) laufen generisch (kein Hardcode).
10. `test_reposition_default_unchanged` — Standup→Reposition→STANDING ohne `after` unverändert (Regression; sonst deckt das bestehende `test_reposition.py` ab).

**Node-Unit (erweitert `test/test_param_callback.py` o. neues `test_sitdown_node.py`):**
11. Services `/hexapod_sit_down`, `/hexapod_stand_up`, `/hexapod_shutdown` existieren + State-Guards (sit nur STANDING, stand_up nur SAT).
12. `comms_loss_sitdown_timeout`-Param deklariert, Default 0; Fail-safe-Logik (mit gefälschter Uhr/`_last_cmd_time`) feuert nur in STANDING + nur wenn last_cmd gesetzt.

**Envelope/Lint (B1.8):** `standup_envelope_check` + `walking_envelope_check` unberührt grün
(keine Pose-Param-Defaults geändert); `colcon test` + `ament_flake8`/`ament_pep257` grün.

**Bewusst NICHT getestet (scope-out / deferred):**
- **Dynamisches Kippen unter Last** — Modell ist quasi-statisch (CoG im Polygon via `joint_load`);
  echte Dynamik erst HW-Beobachtung (B1.10).
- **Reales Relay-Timing / Strom-Spitze beim Lower** — HW-only (B1.10), nicht im Unit-Test.
- **Bluetooth-Comms-Loss-Vollbehandlung** — eigener Scope Block C4/E1; hier nur opt-in-Timeout.

---

## 3. Progress-Checkliste (Done-Vertrag, 1:1 nach `B_lokomotion_kern.md` §B1)

```
- [x] B1.1  Engine: start_sitdown + Phasen (Reposition aus → Körper absenken → rad 0) → SAT-State
- [x] B1.2  Engine: SAT-State (bestromt, idle); Aufstehen AUS SAT (start_cartesian_standup start-pose-agnostisch) → STANDING
- [x] B1.3  Engine: cmd_vel in Sitdown/SAT ignorieren (nur stand_up/shutdown akzeptiert)
- [x] B1.4  Node: Services /hexapod_sit_down (→SAT Rest), /hexapod_stand_up (SAT→STANDING), /hexapod_shutdown (sit + Relay-Aus)
- [x] B1.5  Node: Relay-Aus nur im Shutdown (/hexapod_relay_set SetBool data=false; Sim übersprungen)
- [x] B1.6  Node: Fail-safe Comms-Loss (opt-in, Default 0) → /hexapod_sit_down (Rest); aus WALKING erst stoppen
- [x] B1.7  Unit-Tests: Pfad in-limit (alle 6, jede Phase), Reposition-aus = rückwärts, Endpose=rad 0, max 3 in Luft, SAT→STANDING in-limit
- [x] B1.8  standup/walking_envelope unberührt grün; Regression + Lint grün (111 tests, 0 fail)
- [x] B1.9  SIM: Stehen→Hinsetzen(SAT)→Aufstehen smooth, kein Freeze/Kippen; Services triggern (Laufen→anhalten→hinsetzen End-to-End ok)
- [x] B1.10 HW aufgebockt → Boden: Hinsetzen + Aufstehen + Shutdown(Relay) sicher (User-Verify 2026-06-03)
- [x] B1.11 Self-Review + Design-Log; Test-Markdown (dieser Abschnitt 5/6 + B1_sitdown_test_commands.md)
```

> **🟢 B1 ABGESCHLOSSEN (2026-06-03):** alle Punkte B1.1–B1.11 erledigt. Code + Tests
> (116, 0 fail) + Lint + Envelope grün; SIM + HW (aufgebockt **und** Boden) vom User
> verifiziert wie gewünscht (End-Pose = Spawn-Pose/Beine hoch, Hinsetzen→Aufstehen→
> Shutdown sicher, Laufen→anhalten→hinsetzen ok).

## 5. Implementierungs-Notizen + Design-Log

**Dateien geändert/neu:**
- `hexapod_gait/gait_engine.py`: States `SITDOWN_LOWER`/`SITDOWN_FLATTEN`/`SAT`; `start_sitdown`,
  `start_sitdown_lower`, `start_sitdown_flatten`, `_compute_sitdown_*`, `_compute_sat_angles`;
  `start_reposition` um `from_radial`/`to_radial`/`after` erweitert; `_finish_reposition` (Continuation).
- `hexapod_gait/gait_node.py`: 3 Services + Handler, Relay-Client (`/hexapod_relay_set`),
  `_check_comms_loss`, `_latest_joints`, `_shutdown_latched`, `_relay_off_after_sat`; 3 Params.
- Neu: `test/test_sitdown.py` (15 Engine-Tests), `test/test_sitdown_node.py` (16 Node-Tests).

**Design-Entscheidungen (mit verworfenen Alternativen):**
- **Lazy Phasen-Uhr:** Jede Phase startet ihre Uhr beim Tick, der die Vorgänger-Grenze
  überschreitet (nicht beim exakten Grenz-t). Korrekt fürs dichte 50-Hz-Ticking; Unit-Tests
  müssen daher dicht ticken statt zu springen (siehe `_drive`-Helper). Konsistent mit
  Standup→Reposition. *Alternative (absolute Phasen-Startzeiten vorab):* fragil bei Live-Param-
  Änderung der Dauern, verworfen.
- **Reposition-Reuse via Continuation statt eigenem State:** `_reposition_after`-Feld + ein
  Conditional in `_finish_reposition`. *Alternative (dedizierter SITDOWN_REPOSITION):* mehr Code,
  null Coupling — verworfen zugunsten max. Reuse (User-Entscheidung).
- **Flatten in Joint-Space (kein IK pro Tick):** box-konvex limit-sicher, mirror von STARTUP_RAMP.
  Start-Pose deterministisch aus IK der Lower-Endpose (kein Live-Angle-Tracking).
- **Shutdown-Latch im Node, Engine bleibt SAT:** Power-Zustand ist kein Engine-Konzept. Latch
  blockt `stand_up` bis Relay-On/Reboot. *Alternative (eigener Engine-State SHUTDOWN):* unnötig,
  Power gehört in den Node.
- **Relay fire-and-forget** (wie `_trigger_safety_freeze`): kein Blockieren des 50-Hz-Ticks;
  Latch ist der SW-Guard, FW-Fail-safe (Relay fällt bei Trip/RESET) deckt den Rest.

## 6. Self-Review (kritischer Durchgang 2026-06-03)

| # | Punkt | Status | Befund |
|---|---|---|---|
| 1 | Comms-Loss kein Re-Trigger | OK | Nach Trigger state≠STANDING → Guard blockt; in SAT geblockt. |
| 2 | Reconnect → autom. wieder hoch? | 🟡 vormerken | B1 = nur Rest-Hinsetzen; Auto-Restand bei cmd_vel-Reconnect NICHT drin → Block C4/E1. |
| 3 | Shutdown-Latch-Reset | OK | Nur via Reboot (Node-Reinit). Entspricht „Re-Power = Reboot". |
| 4 | Relay async vs Latch | OK | fire-and-forget + sofort latchen; Latch = SW-Guard, FW-Fail-safe deckt Rest. |
| 5 | `_reposition_after`-Reset | OK | `start_reposition` ohne `after` → STANDING; via `test_standup_from_sat` auf gleicher Engine verifiziert. |
| 6 | Doppel-Trigger mid-Sequenz | OK | sit nur STANDING, shutdown nur STANDING/SAT → mid-Sequenz abgelehnt. |
| 7 | Standup aus SAT (rad 0) ground-contact | 🟡 SIM-verify | kinematisch in-limit getestet; standup_envelope prüft nur ab power_on_mid → in SIM beobachten. |
| 8 | Flatten-Ziel = Boot-/Spawn-Pose (Korrektur) | OK (SIM-verify) | rad 0 wäre flach-horizontal; jetzt Lerp zur mitgeschnittenen Spawn-Pose (Beine hoch). Box-konvex limit-sicher. SIM: stabile Bauchlage prüfen. |
| 9 | Wertneutralität | OK | `test_sitdown_value_neutral` grün; Lower/Reposition nutzen Params. |
| 10 | Continuity Lower→Flatten | OK | Flatten-Start = IK der Lower-Endpose → nahtlos. |

Keine 🔴. Zwei 🟡 = SIM-Beobachtungspunkte (B1.9), ein bewusst deferierter Scope (#2 → C4/E1).

---

## 4. Entschiedene Punkte (User-Freigabe 2026-06-03)

- **Q3 (Geschwindigkeit/Params) — ENTSCHIEDEN (Vorschlag 2):** **eigener `sitdown_duration`**
  (Phase 2+3) + **`sitdown_lower_fraction`** (Split Lower/Flatten), Phase 1 nutzt
  **`reposition_cycle_time`** (Reuse). Hinsetzen damit unabhängig vom Aufstehen tunebar;
  Param-Muster analog `auto_standup_duration`+`standup_phase1_fraction`. 2 neue Timing-Params.
- **Q4 (Relay-Off) — geklärt:** `/hexapod_relay_set` (`std_srvs/SetBool`, `data=false` =
  Relay öffnen → Servos stromlos). FW-Fail-safe (Relay fällt bei Trip/RESET). Sim: Service
  fehlt → skip (Pattern wie safety_freeze).
- **Reposition-Reuse — ENTSCHIEDEN:** Phase 1 nutzt den **bestehenden STATE_REPOSITION** via
  `start_reposition(after=SITDOWN_LOWER)` (ein Conditional in `_finish_reposition`). Standup-Pfad
  unverändert (Default `after=STATE_STANDING`).
- **`/hexapod_shutdown` terminal — ENTSCHIEDEN (Variante 1, Latch):** Nach Relay-Aus bleibt der
  State **SAT** + Node-Flag `_shutdown_latched=True`. `/hexapod_stand_up` wird danach **abgelehnt**
  bis Relay-On/Reboot (aufgebockt, wie Boot). Sicher gegen Aufstehen mit stromlosen Servos +
  Power-On-Zentrier-Ruck.

> **Alle offenen Punkte geklärt → bereit für Implementierung (B1.1 ff.) nach finalem User-OK.**
```
