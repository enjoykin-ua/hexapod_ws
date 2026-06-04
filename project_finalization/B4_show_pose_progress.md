# B4 — Show-Pose (Free-Leg): Fortschritt / Status-Board

> **Zweck:** Live-Status von B4 (was ist erledigt, was kommt, was ist offen) — getrennt
> vom Design-Doc. Der **Done-Vertrag** (unveränderliche Checkliste) steht in
> [`B4_show_pose_plan.md`](B4_show_pose_plan.md) §5; hier wird pro Bullet abgehakt + datiert.
>
> **Lese-Reihenfolge neuer Chat:** `CLAUDE.md` §4/§5/§9 · `project_architecture/ai_navigation.md`
> · [`B4_show_pose_plan.md`](B4_show_pose_plan.md) (Plan, B4.0-Ergebnis §4a, Design-Log §9) · DIESE Datei.
> Block-Kontext: [`B_lokomotion_kern.md`](B_lokomotion_kern.md) §B4.

Status-Legende: ⚪ offen — 🟡 aktiv — 🟢 fertig — 🔴 blockiert — 💤 deferiert.

## Ziel (entschieden, User 2026-06-04)
Stütz auf 4 hinteren Beinen (leg_2,3,4,5), 2 Vorderbeine (leg_1=R, leg_6=L) frei per Joystick.
Linker Stick→leg_6, rechter Stick→leg_1, unabhängig; Y=hoch/runter, X=seitwärts; geclampt auf
URDF-Limits; R1 = Dead-Man. Rein/raus per Cross-lang-Toggle. **Round-Trip Show→STANDING muss sauber
sein, damit danach wieder gelaufen werden kann** (User-Vorgabe). Kanal = eigenes Topic `/cmd_show` (Q3).

## Sub-Stage-Status
| # | Inhalt | Status | Datum | Artefakte |
|---|---|---|---|---|
| B4.0 | Kritischer Vorab-Check (CoG/Reach offline) | 🟢 fertig | 2026-06-04 | `tools/show_pose_cog_check.py`, Plan §4a |
| B4.1 | Engine STATE_SHOW_ENTER + SHOW_ACTIVE + CoG-Gate | 🟢 fertig | 2026-06-04 | `gait_engine.py`, `test/test_show_pose.py` (12) |
| B4.2 | Engine SHOW_ACTIVE: Vorderbeine folgen `/cmd_show` (leg_ik + URDF-Clamp; Dead-Man) | 🟢 fertig | 2026-06-04 | `gait_engine.py`, `test_show_pose.py` (+6) |
| B4.3 | Engine STATE_SHOW_EXIT → STANDING (Round-Trip!) | 🟢 fertig | 2026-06-04 | `gait_engine.py`, `test_show_pose.py` (+8) |
| B4.4 | Node: `/hexapod_show_toggle` + `/cmd_show`-Sub + Params | 🟢 fertig | 2026-06-04 | `gait_node.py`, `test_show_node.py` (11) |
| B4.5 | Teleop: Cross-lang→Toggle, Sticks→`/cmd_show` | 🟢 fertig | 2026-06-04 | `joy_to_twist.py`, `ps4_*.yaml`, `test_joy_to_twist.py` (+6) |
| B4.6 | Unit-Tests komplett (ENTER/ACTIVE/EXIT, Gate, Clamp, Guards, Node, Teleop) | 🟢 fertig | 2026-06-04 | `test_show_pose.py`(26)+`test_show_node.py`(11)+`test_joy_to_twist.py`(+6) |
| B4.7 | Envelope/Regression + Lint grün, Bestand unberührt | 🟢 fertig | 2026-06-04 | gait 181/0, teleop 28/0 |
| B4.8 | SIM (RViz+Gazebo): rein→bewegen→raus, kein Kippen/Freeze | 🟢 fertig (User 2026-06-04) | 2026-06-04 | `B4_show_pose_test_commands.md` |
| B4.9 | HW aufgebockt → Boden (CoG-kritisch!) | 🟡 bereit (User, wenn HW verfügbar) | — | `B4_show_pose_test_commands.md` §3 |
| B4.10 | Self-Review + Design-Log + Test-Markdown | 🟢 Self-Review+Log (Plan §9) fertig; Test-MD geschrieben | 2026-06-04 | `B4_show_pose_test_commands.md` |
| **B4.11** | **Tibia-Curl: radiale Vorderbein-Achse (Trigger)** | 🟢 Code fertig, Sim offen | 2026-06-04 | `gait_engine/node.py`, `joy_to_twist.py`, Tests |

## Was ist ERLEDIGT (Details)
- **B4.0** ✅ — Offline nachgewiesen: sichere Show-Stütz-Pose existiert. Empfohlen
  `show_body_shift_back ≈ 0.06–0.07 m` → CoG-Marge ~50–58 mm, alle 4 Stützbeine in-URDF-Limit.
  Obergrenze: Coxa ±0.415 @ Shift ≈0.092 m. Femur ±1.57 begrenzt Vorderbein-Hub (höher = radial weiter raus).
- **B4.1** ✅ — `STATE_SHOW_ENTER` (Phase a: Körper-Rückversatz, alle 6 am Boden; Phase b: Vorderbeine
  1,6 hoch) + `STATE_SHOW_ACTIVE` (statisches Halten). CoG-Marge-Gate pro Tick in Phase b (Hold bei
  Unterschreitung). cmd_vel in beiden SHOW-States ignoriert. Wertneutral (Args via `start_show_enter`).
- **B4.3** ✅ — `STATE_SHOW_EXIT` über gemeinsamen Show-Skalar σ∈[0,1] (σ=0=Walk-Stand, σ=1=volle Show).
  EXIT fährt σ→0 (erst Vorderbeine runter, dann Körper vor) → nahtlos STANDING → **Laufen wieder möglich**
  (Round-Trip erfüllt). Funktioniert aus SHOW_ACTIVE, mid-ENTER und frozen-ENTER. KEIN CoG-Gate (σ nur
  fallend = monoton sicherer).
- **B4.2** ✅ — `set_show_offsets({leg:(lat,vert)} in m)`; rate-limitierte Nachführung
  (`show_return_rate`) + harte Clamp via Hold-bei-IKError; Offset·λ(σ) verblasst beim EXIT (kein Sprung).
  **Offline-Sicherheit:** über ALLE 3025 in-limit-Offsets min CoG-Marge 44 mm @shift 0.065 → kein
  ACTIVE-CoG-Gate nötig (Joint-Clamp bindet CoG implizit; `show_body_shift_back` ≥ 0.05 halten).
  Gesamt: 26 Engine-Tests + Regression 170/0/1-skip + flake8/pep257 grün.

- **B4.11** ✅ Code — **radiale Vorderbein-Achse** (3. DOF: lat, vert, **radial**). `/cmd_show` 4→6
  Werte `[l6_lat,l6_vert,l6_radial, l1_lat,l1_vert,l1_radial]`; Teleop: **L2→leg_6, R2→leg_1** (analog,
  R1-gated), Body-Höhe nur ohne R1. Befund: „reach out" (Trigger drücken = Bein streckt, **Tibia
  ~0.65 rad auf**); „curl in" ist von der Neutral-Pose femur-limit-blockiert → einseitig. Offline-CoG
  über alle in-limit (lat,vert,radial)-Kombis = **42 mm** @shift 0.065 → kein ACTIVE-Gate nötig.
  Param `show_radial_scale` (Default 0.05, safe bis 0.06). Tests: gait 182/0, teleop 30/0, Lint grün.
  **Offen:** Sim-Verifikation (Trigger → Tibia fährt auf, weich, in-limit, keine Kollision).

## Was ist NOCH ZU TUN (kurz)
- **B4.4 (nächster):** Node — Service `/hexapod_show_toggle` (Trigger, STANDING↔SHOW; aus SHOW_*
  → start_show_exit, inkl. frozen), `/cmd_show`-Subscriber (Stick→m-Skalen-Params + Dead-Man R1 →
  set_show_offsets), Params (Dauer/Shift/Marge/Front-Pose/return_rate/Skalen). Node-Unit-Tests.
- **B4.5:** Teleop — Cross-lang-Hook (`joy_to_twist.py::_show_pose_hook`) → Toggle; Sticks (links→leg_6,
  rechts→leg_1; X=lateral, Y=vertikal) + R1-Dead-Man → `/cmd_show`.
- **B4.8/B4.9:** Sim (zuerst, komplett sauber) → HW aufgebockt → Boden.

## Engine-API für den Node (B4.4-Anschluss)
- `engine.start_show_enter(t, duration, body_shift_back, shift_fraction, front_radial, front_z, safety_margin, return_rate, mass_model=None)` → bool (nur aus STANDING).
- `engine.start_show_exit(t, duration)` → bool (aus jedem SHOW-State, inkl. frozen).
- `engine.set_show_offsets({'leg_1': (lat,vert), 'leg_6': (lat,vert)})` — Meter, Bein-Frame, pro /cmd_show-Tick.
- States: `STATE_SHOW_ENTER / STATE_SHOW_ACTIVE / STATE_SHOW_EXIT` (cmd_vel in allen ignoriert).
- Empfohlene Defaults: `body_shift_back` 0.065 (≥0.05), `shift_fraction` 0.5, `front_radial` 0.22,
  `front_z` −0.04, `safety_margin` 0.030, `return_rate` ~0.5 m/s, Stick-Skalen lat/vert konservativ (Sim).

## Offene Punkte / Notizen (aus Self-Review, Plan §9)
- CoG-Gate ist per-Tick → Design-Garantie-Test deckt es ab (sicher auch ohne Gate bei sanen Params).
- EXIT darf NICHT mitten drin freezen (sonst gestrandet) → EXIT folgt dem in B4.0 validierten Pfad zurück, ohne Gate-Abbruch.
- Comms-Loss-Failsafe greift in SHOW (noch) nicht → Note B4.4/E1.
- Test-Markdown `B4_show_pose_test_commands.md` wird vor der Sim-Stage (B4.8) geschrieben.
