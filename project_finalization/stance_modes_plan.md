# Stance-Modi — 3 validierte Lauf-Höhen (Plan + Fortschritt)

> **Kontext:** Phase-13 Stage 1 (Lauf-Optimierung). Entstanden beim B4-Test: stufenlose Höhe/
> step_length brach die Lauf-Envelope (Femur-±90°-Wand + fixer step_height). Lösung: **3 diskrete,
> envelope-validierte Stance-Modi** statt stufenloser Höhe. **Unabhängig von B4** (B4 fertig).
>
> **Lese-Reihenfolge:** `CLAUDE.md` §4/§5/§9 · `project_architecture/ai_navigation.md`
> (Eintrag „Stance-Modi") · DIESE Datei · `B_lokomotion_kern.md` (Engine-Ist-Zustand).

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 fertig.

## Ziel
3 fest validierte Stance-Modi (Höhe + radial + step_height je vorab envelope-grün), per Controller
umschaltbar. Damit ist jeder einstellbare Zustand garantiert lauffähig (keine IK-Freezes durch
out-of-envelope-Höhen mehr).

## Werte (validiert mit der ECHTEN ENGINE über alle cmd_vel-Richtungen @ sl 0.089)
| Modus | body_height | radial | step_height | step_length | Tibia-Last | Femur-Marge | Hinweis |
|---|---|---|---|---|---|---|---|
| **hoch** | −0.140 | **0.225** | 0.080 | 0.089 | ~11.5 % | ~0.36 rad | NICHT direkt aufstehbar → Standup-Basis −0.100, dann +Lift |
| **mittel** | −0.100 | **0.245** | 0.080 | 0.089 | ~14.7 % | ~0.23 rad | **Standup-Basis** (direkt aufstehbar @ standup_radial 0.295) |
| **tief** | −0.070 | **0.255** | 0.080 | 0.089 | ~16.7 % | ~0.15 rad | geduckt, Beine weiter außen |

> ⚠️ **KORREKTUR (Bug-Fix):** Erste Werte (radial 0.190/0.220/0.235, last-optimaler Min-Radial,
> sl_max 0.12) lagen am **Femur-±90°-Wand-Rand** → fehlerten im echten Engine-Pfad (worst-femur
> −1.56…−1.57). **Das `walking_envelope_check`-Tool ist am Rand zu optimistisch** (meldete GREEN).
> Korrektur: Radien mit **Femur-Marge** (Füße weiter raus) + **step_length_max zurück auf 0.089**,
> verifiziert mit einer **echten-Engine-Simulation** (alle cmd_vel-Richtungen, `test_stance_switch.py
> ::test_mode_walks_all_directions_no_ikerror`). Lehre: „Füße näher fürs Kühlen" gilt nur im **Stehen**
> (kein Swing), beim omnidirektionalen **Laufen** zwingt die Femur-Wand die Füße raus.

step_length: Default/max **0.089** (war fälschlich 0.12 — sicheres Maximum über alle Modi inkl. tief),
Trim-Stufe **0.01**. Schrittweite skaliert stufenlos mit Stick — Trim setzt nur das Maximum.

## Architektur
- **Engine (`gait_engine.py`):** neuer State **`STATE_STANCE_SWITCH`** — gekoppelte Tripod-Reposition,
  die **radial UND body_height gleichzeitig** vom Ist- zum Ziel-Modus interpoliert, mit **kleinem
  `stance_switch_step_height`** (~0.025, damit der Swing-Apex bei keiner Zwischen-Höhe die Femur-Wand
  trifft). Bei Abschluss: `radial_distance/body_height/step_height` = Ziel-Modus → STANDING.
  `start_stance_switch(t, target_radial, target_bh, target_step_height, ...)`. Nur aus STANDING.
- **Node (`gait_node.py`):** Mode-Tabelle (3 Modi) + aktiver Index; Service **`/hexapod_cycle_stance`**
  (`SetBool`: true=höher, false=tiefer, nur STANDING) → `start_stance_switch`. Standup-Defaults =
  **mittel** (−0.100/0.220). Params: `stance_switch_duration`, `stance_switch_step_height`.
  step_length-Trim: `step_length_intent_step` 0.01, `_max` 0.12. **`body_height` fp_range-Floor auf
  −0.140 freigeben** (für hoch).
- **Teleop (`joy_to_twist.py`):** **L2/R2 ohne R1** → `/hexapod_cycle_stance` (L2=tiefer, R2=höher,
  edge). Mit R1 (Show) bleiben L2/R2 = Tibia-Curl (B4.11). **Stufenlose Höhe entfällt** (war das
  Problem). Startup-`/cmd_body_height` = −0.100 (Stand-Sync zur mittel-Basis).

## Standup / Boot
Standup landet auf **mittel** (−0.100 @ standup_radial 0.295 → Reposition auf 0.220 — direkt
aufstehbar, validiert). hoch (−0.140) ist NICHT direkt aufstehbar → erreichbar nur als Mode-Switch
von mittel (Lift +Reposition). tief (−0.070) = Switch von mittel (Absenken + Reposition).

## Checkliste
```
- [x] S.0  Offline: 3 Modi envelope-grün + alle 6 Transitions in-limit; Boot-Reposition + Standup→mittel GRÜN; Sit-from-hoch out-of-reach erkannt → Routing
- [x] S.1  Engine: STATE_STANCE_SWITCH (gekoppelt radial+bh, switch-step_height) + start_stance_switch; cmd_vel ignoriert. 12 Tests (test_stance_switch.py)
- [x] S.2  Node: _STANCE_MODES + /hexapod_cycle_stance (SetBool, nur STANDING, clamp); Defaults=mittel; stance_switch_*-Params; body_height-Range −0.140; step_length-Trim 0.01/max 0.12; Sit-from-hoch-Routing über mittel (_pending_sitdown)
- [x] S.3  Teleop: L2/R2 ohne R1 → cycle_stance (tiefer/höher); stufenlose Höhe raus; body_height_init/min = −0.100/−0.140 (usb+bt)
- [x] S.4  Unit-Tests: Switch-Pfad in-limit (6 Übergänge), Ziel-Modus, nur STANDING, cmd_vel ignoriert; cycle_stance-Guards+clamp; Sit-Routing; Teleop L2/R2 R1-Trennung
- [x] S.5  Regression + Lint grün: gait 201/0/1-skip, teleop 30/0/1-skip
- [ ] S.6  SIM: aufstehen→mittel; L2/R2 cyclen hoch/mittel/tief, jeweils laufen ohne Fehler; hinsetzen aus jedem Modus (aus hoch via mittel)
- [ ] S.7  HW aufgebockt → Boden
- [x] S.8  Self-Review (oben in Chat) + Doku (ai_navigation-Eintrag, Test-Markdown stance_modes_test_commands.md)
```

## Sit-from-hoch-Routing (S.2, wichtige Design-Entscheidung)
hoch (−0.140) ist NICHT direkt sit-/standup-fähig (−0.140 @ standup_radial 0.295 = out-of-reach,
d=0.288>0.280). Standup landet daher immer auf **mittel** (−0.100, direkt aufstehbar); hoch nur per
cycle_stance erreichbar. **Hinsetzen aus hoch** routet automatisch: `_start_sitdown_sequence` erkennt
`body_height < −0.120`, fährt erst einen Stance-Switch auf mittel, setzt `_pending_sitdown`, und holt
das Hinsetzen im Tick nach, sobald STANDING (mittel) erreicht ist. Gilt auch für Shutdown + Comms-Loss
(Relay-Intent bleibt über den Switch erhalten).

## Self-Review (S.8) — keine 🔴
Boot→mittel GRÜN · 3 Modi GRÜN · 6 Transitions in-limit · Sit-from-hoch geroutet+getestet · cmd_vel
im Switch ignoriert · L2/R2 nur ohne R1 · pending-Sit-Check vor Comms-Loss (richtige Reihenfolge).
🟡 Selbst-Kollision beim Switch nur visuell (A4); Boot-Pose −0.120→−0.100 geändert (feet_closer-Preset
jetzt legacy); `_adjust_body_height` im Teleop nur noch Helper (Startup-Sync), nicht mehr an L2/R2.

## Tests (Begründung)
- Engine-Unit (pure-python): jeder Übergang (mittel→hoch, hoch→mittel, mittel→tief, tief→mittel)
  über alle Ticks in-limit (URDF); Endpose = Ziel-Modus-Params; Switch nur aus STANDING; cmd_vel
  ignoriert im Switch. NICHT: dynamisches Kippen (quasi-statisch), Selbst-Kollision (A4).
- Node/Teleop: cycle_stance-Guards (nur STANDING, wrap/clamp der 3 Modi); L2/R2-ohne-R1→cycle,
  mit-R1→kein cycle (Show-Curl).

## Validierungs-Gates
Build → Unit/Lint → Envelope (3 Modi + Transitions offline) → SIM → HW aufgebockt → Boden.

## Fortschritt
(wird beim Umsetzen abgehakt)
