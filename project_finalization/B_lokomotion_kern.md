# Block B — Lokomotion-Kern (Handover-Plan + Fortschritt)

> **Zweck:** Sammel-Plan für Block B (Lokomotion-Kern). Hält pro Stage Ziel, Logik-Skizze,
> betroffene Dateien, **abhakbare Punkte**, Tests und **offene Fragen** fest — so dass ein
> **neuer Chat nahtlos übernehmen** kann (was ist fertig, was kommt als Nächstes).
>
> **Lese-Reihenfolge für neuen Chat:** `CLAUDE.md` §4/§5/§9 · `project_architecture/ai_navigation.md`
> (wo-finde-ich-was + Validierungs-Gates) · DIESE Datei · die jeweilige Stage-Plan-/Test-Datei.
> Backlog-Kontext: [`00_backlog.md`](00_backlog.md). Status: ⚪ offen — 🟡 aktiv — 🟢 fertig — 💤 deferiert.

## Status-Übersicht (für Handover)
| Stage | Titel | Status | Plan-Datei | Test-Datei |
|---|---|---|---|---|
| **B1** | Hinsetz-/Abschalt-Sequenz | 🟢 **fertig** (SIM+HW Boden verifiziert 2026-06-03) | [`B1_sitdown_plan.md`](B1_sitdown_plan.md) | [`B1_sitdown_test_commands.md`](B1_sitdown_test_commands.md) |
| B2 | Velocity-Feedforward (Zittern-Fix) | ❌ versucht & zurückgebaut (kein Nutzen, 2026-06-03) | §B2 | — |
| B3 | Gangarten Wave→Tetrapod→Ripple (nacheinander) | ⚪ | §B3 | TODO |
| B4 | Body-Pose + „Show"-Pose | ⏸️ Doku fertig, Umsetzung später | §B4 | (später) |
| B5 | Volle 5 cm Körperhöhe (−0.130) | 💤 deferiert | §B5 | — |

> **Wichtiger Kontext (Ist-Zustand der Engine):** `gait_engine.py` hat States
> STANDING / WALKING / STOPPING / STARTUP_RAMP / CARTESIAN_STANDUP / **REPOSITION**.
> Aufsteh-Ablauf: power_on_mid(Bauch) → CARTESIAN_STANDUP (Touchdown@`standup_radial_distance`
> 0.295 → Push hoch auf `body_height` −0.120 @0.295) → **REPOSITION** (0.295→`radial_distance`
> 0.215 @ −0.120, Tripod 3+3) → STANDING. cmd_vel wird in allen Nicht-STANDING/WALKING-States
> ignoriert. Walk-Pose-Preset: `config/presets/feet_closer_walk.yaml`. Tools: `joint_load`
> (CoG/Last), `torque_viz`, `walking_/standup_envelope_check`.

---

## B1 — Hinsetz-/Abschalt-Sequenz  ⚪ (als Nächstes)

**Ziel:** Kontrolliertes, sicheres Hinsetzen (Umkehrung des Aufstehens) — Voraussetzung für
sicheres Beenden auf echtem Boden (sonst: Strom weg → Servos zentrieren HW-bedingt → Roboter
fällt). Graceful: erst hinsetzen, DANN Strom trennen (Relay/User).

**Logik-Skizze (Umkehrung Aufstehen+Reposition):**
1. Start nur aus **STANDING** (Walk-Pose `radial_distance` 0.215 @ `body_height` −0.120).
2. **Phase 1 — Reposition AUS:** Füße per Tripod von `radial_distance` → `standup_radial_distance`
   (0.215→0.295) @ aktueller Höhe. = die bestehende Reposition, nur Richtung umgekehrt
   (`start_reposition(from=radial_distance, to=standup_radial_distance)`).
3. **Phase 2 — Körper absenken:** reverse-kartesisch — x/y der Füße fix @ standup_radial,
   `body_height` rampt von −0.120 → `body_height_start` (−0.0135, Bauch am Boden).
   = Umkehrung der CARTESIAN_STANDUP-Push-Phase.
4. **Phase 3 — Ruhe-Pose (rad 0) → SAT (User 2026-06-02):** sanft in **alle Joints rad 0** lerpen
   (Beine flach), Endzustand **SAT** (Bauch am Boden, **bestromt**, idle). Geometrie: Fuß bei
   rad 0 ist im Bein-Frame z=0 = ~Coxa-Höhe → liegt **~2 cm über Grund** (kein Schürfen).
   **Zwei Modi (User-Zusatz 2026-06-02):**
   - **Rest (nicht-terminal):** in SAT **bestromt** bleiben → später per `/hexapod_stand_up`
     wieder aufstehen (Standup ist start-pose-agnostisch, nutzt die aktuellen joint_states als
     Start). Das ist auch das Ziel des **Comms-Loss-Fail-safe** (bei Reconnect wieder hoch).
   - **Shutdown (terminal):** zusätzlich **Relay aus** (HW). Servos werden stromlos/schlaff →
     **kein aktiver Ruck**; das Zentrieren passiert erst beim nächsten **Einschalten** (Boot wie bisher).
- cmd_vel während der ganzen Sequenz ignorieren (wie Standup/Reposition).

**Trigger / Services (User 2026-06-02, inkl. Rest+Stand-up-Zusatz):**
- `/hexapod_sit_down` (`std_srvs/Trigger`, nur STANDING) → **Rest**-Hinsetzen (SAT, bestromt).
- `/hexapod_stand_up` (`std_srvs/Trigger`, nur SAT) → Aufstehen + Reposition → STANDING
  (start-pose-agnostisch, nutzt aktuelle joint_states). Ermöglicht „Ausruhen → wieder hoch".
- `/hexapod_shutdown` (`std_srvs/Trigger`, STANDING od. SAT) → Hinsetzen (falls nötig) + **Relay-Aus** (terminal).
- **Fail-safe Comms-Loss:** opt-in `comms_loss_sitdown_timeout` (Default **0 = aus**; mit Controller
  z.B. 5 s) → automatisch `/hexapod_sit_down` (**Rest**, NICHT Shutdown — bei Reconnect wieder hoch).
  **Idle vs Disconnect:** verbundener Controller publisht via joy-autorepeat dauernd `/cmd_vel`
  (auch =0); echtes Disconnect → `/cmd_vel` verstummt ganz. Default aus (sonst false-trigger bei
  manuellem cmd_vel/Sim). Voll-Behandlung BT-Comms-Loss → Block C4 / E1.

**Dateien:** `gait_engine.py` (neue States `SITDOWN_REPOSITION`/`SITDOWN_LOWER`/`SAT` oder
ein STATE_SITDOWN mit Phasen; `start_sitdown`, `_compute_sitdown_angles`), `gait_node.py`
(Service-Server + Durchreichen), ggf. `gait.launch.py`. Wertneutral (radii/Höhen aus Params).

**Progress-Checkliste:** (Detail-Plan + Self-Review: [`B1_sitdown_plan.md`](B1_sitdown_plan.md))
```
- [x] B1.1  Engine: start_sitdown + Phasen (Reposition aus → Körper absenken → rad 0) → SAT-State
- [x] B1.2  Engine: SAT-State (bestromt, idle); Aufstehen AUS SAT (start_cartesian_standup start-pose-agnostisch) → STANDING
- [x] B1.3  Engine: cmd_vel in Sitdown/SAT ignorieren (nur stand_up/shutdown akzeptiert)
- [x] B1.4  Node: Services /hexapod_sit_down (→SAT Rest), /hexapod_stand_up (SAT→STANDING), /hexapod_shutdown (sit + Relay-Aus)
- [x] B1.5  Node: Relay-Aus nur im Shutdown (/hexapod_relay_set SetBool data=false; Sim übersprungen)
- [x] B1.6  Node: Fail-safe Comms-Loss (opt-in, Default 0) → /hexapod_sit_down (Rest); aus WALKING erst stoppen
- [x] B1.7  Unit-Tests: Pfad in-limit (alle 6, jede Phase), Reposition-aus = rückwärts, Endpose=rad 0, max 3 in Luft, SAT→STANDING in-limit
- [x] B1.8  standup/walking_envelope unberührt grün; Regression + Lint grün (111 tests, 0 fail)
- [x] B1.9  SIM: Stehen→Hinsetzen(SAT)→Aufstehen smooth, kein Freeze/Kippen; Services triggern
- [x] B1.10 HW aufgebockt → Boden: Hinsetzen + Aufstehen + Shutdown(Relay) sicher (2026-06-03)
- [x] B1.11 Self-Review + Design-Log; Test-Markdown
```
**Tests-Begründung:** Hinsetz-Pfad ist sicherheitskritisch (am Boden) → jede Phase in-limit +
stabil (CoG im Polygon, nutzt joint_load). NICHT getestet: dynamisches Kippen unter Last (quasi-statisch).

**Offene Fragen B1:**
- ✅ **Q1 Trigger:** Service `/hexapod_sit_down` **+** Fail-safe Comms-Loss (User). Erledigt.
- ✅ **Q2 Ruhe-Pose:** ~~alle Joints rad 0~~ → **KORRIGIERT (User 2026-06-03): Boot-/Spawn-Pose
  (Beine hoch)**, NICHT rad 0. rad 0 ist laut FK das Bein *horizontal gestreckt* (flach) — nicht
  gewollt. Der Node schneidet die Spawn-`/joint_states` mit und übergibt sie als `rest_joints`;
  der Roboter endet, wo er gespawnt ist. Passives Hinlegen der Beine erst beim Relay-Aus.
- ✅ **Q3 Geschwindigkeit:** eigener `sitdown_duration` + `sitdown_lower_fraction`;
  `reposition_cycle_time` für Phase 1 wiederverwendet (User 2026-06-03, Vorschlag 2).
- ✅ **Q4 Relay-Off:** `/hexapod_relay_set` (`std_srvs/SetBool`, `data=false` = Relay öffnen).
  Aus Phase 9 / `hexapod_hardware` (`hexapod_system.cpp`). Sim: Service fehlt → skip.

**Edge-Cases / Hinweise B1 (kritischer Durchgang):**
- **Trigger aus WALKING:** Service nur in STANDING annehmen; der **Comms-Loss-Fail-safe** kann
  aber im WALKING feuern → dann **erst stoppen** (→ STANDING über bestehenden cmd_vel-Timeout),
  **dann** hinsetzen. In SAT/Sitdown bereits → kein Re-Trigger.
- **Reuse statt Duplikat:** `start_reposition` ist richtungs-agnostisch (from→to) → Phase 1 nutzt
  sie mit vertauschten radii. Reverse-Kartesisch = Umkehrung der CARTESIAN_STANDUP-Push-Phase.
- **Sim:** kein Relay → Relay-Aus-Schritt überspringen (wie safety_freeze-Service: nur wenn verfügbar).

---

## B2 — Velocity-Feedforward (Zittern-Fix)  ❌ versucht & zurückgebaut

> **Ergebnis (2026-06-03): kein beobachtbarer Nutzen → vollständig zurückgebaut** (Working-Tree
> auf Commit `08ffcfa` = B1-fertig zurückgesetzt, alle B2-Änderungen verworfen). Was probiert
> wurde und warum es scheiterte:
> - **Umsetzung:** Finite-Differenz der kommandierten Joint-Winkel pro Tick →
>   `JointTrajectoryPoint.velocities` (Clamp auf URDF-Cap 2.0), Param `velocity_feedforward`.
> - **Nötiger JTC-Schalter gefunden:** ohne `allow_nonzero_velocity_at_trajectory_end: true`
>   verwirft der JTC jede gestreamte Einzelpunkt-Trajectory mit End-Velocity≠0 — das belegte
>   zwar, dass der JTC die velocities verarbeitet (Q3 ✅).
> - **Sim:** KEIN sichtbarer Glätte-Effekt (Gazebo hat keine Servo-Dynamik) + `true` fuhr träger
>   an (Mess-State-Artefakt im kubischen Spline). `open_loop_control: true` als Gegenmittel
>   verschlechterte auch den `false`-Fall → verworfen.
> - **HW aufgebockt:** **kein beobachtbarer Unterschied** true vs. false.
> - **Schluss:** Der FF ist auf diesem Setup der falsche Hebel (Servos/50-Hz-Streaming glätten
>   offenbar genug). **Falls das Zittern je real stört, ist der nächste Hebel Vel/Accel-Limits im
>   JTC** (`controllers.real.yaml`, war Q2/deferiert — braucht Bench-Daten), NICHT dieser FF.
> - **Reihenfolge:** weiter mit **B3** (Gangarten).

**Ziel:** Das beim Laufen/Reposition beobachtete Zittern beseitigen. Ursache (verifiziert):
gait_node publisht pro Tick **einen** Trajectory-Punkt **nur mit Position** → JTC plant je Punkt
ein „ankommen+anhalten" → Stop-pro-Punkt-Stottern. Fix: **Soll-Geschwindigkeit mitgeben** →
JTC interpoliert durch.

**Logik-Skizze:** in `gait_node._build_trajectory` (oder beim Tick) pro Joint die Soll-
Geschwindigkeit setzen. Berechnung: **Finite-Differenz** der Gelenk-Winkel zwischen den Ticks
(`(angle_now − angle_prev) / dt`, dt = Tick-Periode) — einfach, robust. (Alternative: analytisch
über Bein-Jacobi × Fuß-Geschwindigkeit — genauer, mehr Arbeit.) `JointTrajectoryPoint.velocities`
füllen. Ggf. Glättung/Clamp.

**Dateien:** `gait_node.py` (`_build_trajectory`, Tick: prev-angles speichern), evtl.
`controllers.real.yaml` (Velocity/Accel-Limits ergänzen, Phase-10-Defer).

**Progress-Checkliste:**
```
- [ ] B2.1  gait_node: Gelenk-Soll-Geschwindigkeit (Finite-Diff) → JointTrajectoryPoint.velocities
- [ ] B2.2  Sonderfälle: erster Tick (keine prev), State-Wechsel, Clamp gegen Sprünge
- [ ] B2.3  Unit/Regression + Lint grün
- [ ] B2.4  SIM: Zittern sichtbar reduziert (vs tfs_factor-Workaround); kein Überschwingen
- [ ] B2.5  HW aufgebockt: ruhigeres Gangbild; (optional) controllers.real.yaml Vel/Accel-Limits
- [ ] B2.6  Self-Review + Test-Markdown
```
**Offene Fragen / kritische Punkte B2:**
- **Q1:** Finite-Differenz (empfohlen, einfach) vs analytische Jacobi-Geschwindigkeit?
- **Q2:** Auch Vel/Accel-Limits in `controllers.real.yaml` setzen (Phase-10-Defer) — jetzt oder separat?
- ⚠️ **Q3 (kritisch):** Der JTC muss die mitgegebenen `velocities` für die Interpolation
  **nutzen** — sonst hat der Feedforward **keinen Effekt**. Vor B2: `controllers.yaml`/
  `controllers.real.yaml` prüfen (interpolation_method/Spline, `allow_*`), in Sim gegen-
  verifizieren (mit vs ohne velocities). Sonst ist das echte Mittel die Vel/Accel-Limit-Glättung (Q2).

---

## B3 — Weitere Gangarten (Wave / Ripple / Tetrapod)  ⚪

**Ziel:** Stabilere/last-ärmere Gangarten zusätzlich zum Tripod. **Wave** (1 Bein zur Zeit,
5 tragen) senkt die per-Bein-Last ~40 % → direkt gut gegen Hitze. Ripple/Tetrapod = Kompromisse.

**Logik-Skizze:** rein `gait_patterns.py` — neue `GaitPattern(phase_offset_per_leg, swing_duty)`
+ Eintrag in `GAIT_PRESETS`. Engine ist generisch (linear_max/stance_duration aus swing_duty).
Vorschlag (Sequenz/Offsets in Sim final verifizieren):
- **Wave** (metachronal, 1 Bein): swing_duty ≈ 1/6 (0.167); Offsets je Bein 0, 1/6, …, 5/6 in einer
  metachronalen Reihenfolge (z.B. 1→3→5→2→4→6 oder nach Lauf-Stabilität). ⏳ exakte Ordnung = Q1.
- **Tetrapod** (2 Beine/Phase, 3 Gruppen): swing_duty ≈ 1/3; 3 Paare gestaffelt.
- **Ripple** (überlappende Welle): swing_duty ≈ 1/3, Offsets feiner gestaffelt.
Gangart-Wechsel: `gait_pattern`-Param ist bereits `standing_only` → Wechsel im Stand ok.

**Dateien:** `gait_patterns.py` (+ Tests `test_*pattern*`). Optional Teleop-Anbindung → Block C.

**Progress-Checkliste:**
```
> **Reihenfolge (User 2026-06-02): alle drei, aber nacheinander** — erst Wave, dann Tetrapod,
> dann Ripple. Je Gangart: Pattern + Tests + Envelope + Sim/HW, dann die nächste.
- [ ] B3.1  **Wave**-Pattern (Offsets + swing_duty 1/6) + GAIT_PRESETS; Tests + Envelope + Sim
- [ ] B3.2  **Tetrapod**-Pattern (swing_duty 1/3, 3 Paare) + Tests + Envelope + Sim
- [ ] B3.3  **Ripple**-Pattern (überlappend) + Tests + Envelope + Sim
- [ ] B3.4  Unit-Tests je Pattern: max-Beine-in-Luft, linear_max plausibel, Offsets gültig
- [ ] B3.5  Gangart-Wechsel im Stand (gait_pattern ist standing_only) sauber
- [ ] B3.6  HW aufgebockt → Boden; Hitze-/Stabilitäts-Vergleich (torque_viz/Beobachtung)
- [ ] B3.7  Self-Review + Test-Markdown (je Gangart Befund festhalten)
```
**Offene Fragen B3:**
- ✅ **Q2 Welche:** **alle drei, nacheinander** (User). Erledigt.
- ⏳ **Q1:** Wave-Bein-Reihenfolge (metachronal) — Vorschlag bei B3.1 generieren + in Sim final wählen.

---

## B4 — Body-Pose ohne Laufen + „Show"-Pose  ⏸️ (Doku jetzt, Umsetzung später — User)

> **User 2026-06-02:** Doku jetzt vorbereiten, aber **pausieren** — angehen nach B1–B3.
> Reihenfolge intern entschieden: **erst gescriptete Body-Tilt-Posen, dann Free-Leg-Show.**

**Ziel:** Körper auf den Stützbeinen neigen/verschieben (roll/pitch/yaw + xyz) und/oder einzelne
Beine frei in der Luft bewegen (winken/„graben"/Spinnen-Pose). Show **und** Vorstufe zu Balance/
Manipulation. **CoG muss im Rest-Stützpolygon bleiben** (statisch) → nutzt `joint_load` (CoG +
Polygon + Marge) aus A1.

**Logik-Skizze:**
- **Body-Pose:** gegebenes (roll,pitch,yaw,dx,dy,dz) → Fuß-Targets so transformieren, dass die
  Füße am Boden bleiben während der Körper sich relativ bewegt → IK pro Bein. Limit- + CoG-Check.
- **Free-Leg-Mode:** ausgewählte Beine (z.B. 1 & 6 vorne) anheben + Luft-Trajektorie; Rest stützt;
  **vorher** CoG verlagern (Körper zurück) damit CoG im Rest-Polygon bleibt (joint_load-Marge>0).
- **Erst gescriptete Posen/Gesten** (Presets/Sequenzen), dann ggf. interaktiv (Teleop, Block C).

**Dateien:** wahrscheinlich eigener Modus/Node (`posture`/`gesture`) oder Engine-Erweiterung;
`joint_load` für CoG/Stabilität; Gesten als Daten (yaml/Sequenz).

**Progress-Checkliste:**
```
- [ ] B4.1  Body-Pose-Transform (roll/pitch/yaw + xyz) → Fuß-Targets → IK, Limit-Check
- [ ] B4.2  CoG-/Stabilitäts-Check (joint_load) — Pose nur erlauben wenn Marge>0
- [ ] B4.3  Free-Leg-Mode: N Beine anheben + Luft-Trajektorie, CoG-Verlagerung auf Rest-Polygon
- [ ] B4.4  Gescriptete Gesten (z.B. winken / Spinnen-Pose) als Sequenz/Preset
- [ ] B4.5  Unit-Tests (Transform, CoG-Marge, Limit) + Regression + Lint
- [ ] B4.6  SIM → HW aufgebockt → (vorsichtig) Boden
- [ ] B4.7  Self-Review + Test-Markdown
```
**Offene Fragen B4:**
- ✅ **Q1 Scope/Reihenfolge:** erst Body-Tilt, dann Free-Leg; **B4 pausiert, nach B1–B3** (User).
- ⏳ **Q2 Gesten:** welche konkret (winken / „graben" / Angriffspose)? Wie viele Beine frei (2 vorne)? — bei Reaktivierung klären.
- ⏳ **Q3 Trigger:** Service/Preset jetzt, Teleop-Anbindung später (Block C)? — bei Reaktivierung.

---

## B5 — Volle 5 cm Körperhöhe (−0.130)  💤 deferiert
**Ziel/Notiz:** Standup kann −0.130 nicht direkt (out-of-reach @ Touchdown-radial). Lösung:
`standup_body_height` (moderat) + Reposition interpoliert **body_height mit** (analog zum
radialen). Erst bauen, wenn 4 cm (−0.120) nicht reichen. Logik + Befund: `docs_raspi/
phase_13_stage_1_two_phase_reposition_plan.md` §7 (Design-Log) / §2.4-Verweis.

---

## Querschnitt / Konventionen für alle B-Stages
- **Wertneutral:** Pose-/Geschwindigkeits-Zahlen in Config/Preset/Params, nicht im Engine-Code
  hardcoden (wie bei 2.3 etabliert).
- **Validierungs-Gates** (ai_navigation §2): Build → Unit/Lint → Envelope-Tools → **SIM (RViz+
  Gazebo) → HW aufgebockt → Boden**. Sim VOR HW.
- **Je Stage:** Plan (hier oder eigenes file) + **Test-Markdown** (`<stage>_test_commands.md`).
- **Commit:** macht der User. Tests grün vor Commit.
