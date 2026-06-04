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

## Was ist NOCH ZU TUN
- **B4.9 HW** (aufgebockt → Boden, CoG-kritisch) — wenn der Roboter verfügbar ist. Anleitung
  [`B4_show_pose_test_commands.md`](B4_show_pose_test_commands.md) §3. Alles davor (Code + Sim B4.8 +
  Tibia-Curl B4.11) ✅.
- Offen-optional / verworfen-vorerst: **Coxa-Weitung** (Vorderbeine weiter nach innen) — User denkt
  noch nach. Sauberer Weg wäre eine show-only/front-only zweite `JointLimits` + Plugin-Clamp-Frage
  (rad vs Puls) + Kollisions-Check; NICHT das globale Limit anfassen. Siehe Diskussion in dieser
  Thread-Historie (nicht implementiert).

---

# Architektur & Wartung (IST-Stand) — für künftige Anpassungen

> Spiegelt den **implementierten** Stand (nicht die ursprüngliche Skizze in `B4_show_pose_plan.md` §3,
> die das Vor-Implementierungs-Konzept zeigt). Erster Anlaufpunkt für „ich ändere X":
> [`project_architecture/ai_navigation.md`](../project_architecture/ai_navigation.md) → „Show-Pose (B4) ändern".

## Datenfluss (3 Schichten, „Teleop = UI")
```
PS4 (joy) ──► joy_to_twist.py ──┬─► /cmd_vel           (Fahren; in SHOW ignoriert)
  Cross-lang  _show_pose_hook ──┼─► /hexapod_show_toggle (Trigger-Service)
  Sticks+L2/R2 _show_from_joy ──┴─► /cmd_show  Float64MultiArray[6]
                                     [l6_lat,l6_vert,l6_radial, l1_lat,l1_vert,l1_radial], R1-gated
                                              │
gait_node.py: _on_show_toggle ──► engine.start_show_enter / start_show_exit (State-abh.)
              _update_show_offsets (nur SHOW_ACTIVE): Stick×Skala→m, Staleness→0
                                              │  engine.set_show_offsets({leg:(lat,vert,radial)})
gait_engine.py: State-Machine + Tick ──► IK pro Bein ──► /<leg>_controller/joint_trajectory
```

## State-Machine + σ-Skalar
- `STANDING ──toggle──► SHOW_ENTER ──(t)──► SHOW_ACTIVE ──toggle──► SHOW_EXIT ──(t)──► STANDING`.
- **σ ∈ [0,1]** ist der gemeinsame Show-Skalar (`_show_foot(leg, σ)`): **σ=0 = Walk-Stand-Pose**
  (= exakt STANDING → nahtlos), **σ=1 = volle Show-Pose**. ENTER fährt σ 0→1, ACTIVE hält σ=1,
  EXIT fährt σ aktuell→0 (deckt auch Abbruch mitten in ENTER inkl. frozen).
- **ENTER zweiphasig** (Param `show_shift_fraction`): Phase a = Körper-Rückversatz (alle 6 am Boden),
  Phase b = Vorderbeine 1,6 heben. **EXIT = umgekehrt** (erst Beine runter, dann Körper vor).
- **Vorderbein-Offsets** (B4.2/B4.11): pro Bein `(lat=Y, vert=Z, radial=X)` in m, rate-limitiert
  (`show_return_rate`) nachgeführt, mit Lift-Faktor λ(σ) skaliert → **verblasst beim EXIT** (kein Sprung).
- **CoG-Gate** nur in ENTER Phase b (`joint_load.compute_load`, Marge ≥ `show_safety_margin` → sonst
  Hold). **SHOW_ACTIVE hat KEIN Gate** — die URDF-Joint-Limits binden den CoG implizit (offline bewiesen,
  Worst-Case 42 mm @shift 0.065). **EXIT hat KEIN Gate** (σ nur fallend = monoton sicherer).
- **Clamp:** alle Vorderbein-Bewegungen via `leg_ik(...,URDF-Limits)`; Verletzung → **Hold der letzten
  gültigen Pose** (kein IKError-Freeze). cmd_vel in allen SHOW-States ignoriert (`set_command`-Guard).

## Parameter-Referenz (alle wertneutral)
**Engine** (Args von `start_show_enter(t, duration, body_shift_back, shift_fraction, front_radial,
front_z, safety_margin, return_rate, mass_model=None)`, `start_show_exit(t, duration)`,
`set_show_offsets({leg:(lat,vert[,radial])})`).
**gait_node-Params** (rqt/`ros2 param set`, beim Toggle gelesen):

| Param | Default | Safe-Range | Wirkung |
|---|---|---|---|
| `show_enter_duration` | 4.0 s | 1–15 | Dauer ENTER |
| `show_exit_duration` | 3.0 s | 1–15 | Dauer EXIT |
| `show_body_shift_back` | 0.065 m | **0.05–0.09** | Körper-Rückversatz (CoG); <0.05 → Marge<30 mm, >0.09 → Coxa-Limit |
| `show_shift_fraction` | 0.5 | 0.1–0.9 | Anteil Phase a (Shift) an ENTER |
| `show_safety_margin` | 0.030 m | 0–0.10 | CoG-Marge-Schwelle (ENTER-Gate) |
| `show_front_radial` | 0.22 m | 0.12–0.28 | Neutral-Hoch-Pose radial (höher heben → größer; Femur ±90°) |
| `show_front_z` | −0.04 m | −0.12–0.04 | Neutral-Hoch-Pose z (Boden = body_height) |
| `show_return_rate` | 0.5 m/s | 0.05–2.0 | Rate-Limit Offset-Nachführung/Rückkehr |
| `show_lat_scale` | 0.06 | 0–0.12 | Stick-X → seitlich (m) |
| `show_vert_scale` | 0.06 | 0–0.12 | Stick-Y → hoch/runter (m) |
| `show_radial_scale` | 0.05 | 0–0.08 (CoG-safe ≤0.06) | Trigger → reach/Tibia-Curl (m) |

**Teleop-Params** (`ps4_usb.yaml`/`ps4_bt.yaml`): `axis_ry`=4 (R-Stick-Y), `sign_show_lat/vert/radial`
(in Sim verifizieren: Stick hoch = Bein heben, Trigger = strecken), `deadman_button`=5 (R1),
`button_cross`=0 (Toggle, long), `longpress_sec`=0.8. L2/R2 = Curl (mit R1) bzw. Body-Höhe (ohne R1).

## Bekannte Constraints / Gotchas
- `show_body_shift_back` **∈ [0.05, 0.09]** (CoG-Marge-Boden ↔ Stütz-Coxa-Limit ±0.415).
- **Femur ±1.57 (±90°)** begrenzt Vorderbein-Hub UND blockiert „curl-in" (radial nur **raus**).
- **Zwei Limit-Quellen** (URDF vs config.py) gelten auch hier — IK nutzt URDF-Limits (HW-maßgeblich).
- `/cmd_show`-Reihenfolge in Node + Teleop **synchron** halten (6 Werte, per-Bein gruppiert).
- **Selbst-Kollision NICHT geprüft** (A4 pausiert) → bei Skalen-/Pose-Änderung visuell in Sim prüfen.
- **Comms-Loss-Failsafe greift in SHOW (noch) nicht** (offen → C4/E1).

## Re-Verifikation bei Änderung (Pflicht-Gates)
1. `colcon test --packages-select hexapod_gait hexapod_teleop` (Unit + flake8/pep257) grün.
2. **Bei vergrößerter Reichweiten-Hülle** (Skalen/Neutral-Pose/neue Achse/Shift): Offline-CoG/Reach
   neu — `python3 tools/show_pose_cog_check.py` (ENTER-Pose) **+** den Offset-Worst-Case-Sweep aus
   `B4_show_pose_plan.md` §4a/§9 mit den neuen Grenzen nachfahren → Marge muss > Schwelle bleiben.
3. **Sim** (`B4_show_pose_test_commands.md` §1/§2): rein → bewegen → raus → laufen; Kollision beobachten.
4. **HW** aufgebockt → Boden (CoG-kritisch).

## Offene Punkte / Notizen (aus Self-Review, Plan §9)
- CoG-Gate (ENTER) ist per-Tick → Design-Garantie-Test (`test_cog_margin_above_threshold`) deckt es ab.
- EXIT freezt nie (folgt dem validierten Pfad zurück).
- Test-Dateien: `test_show_pose.py` (Engine, 27) · `test_show_node.py` (Node, 11) ·
  `test_joy_to_twist.py` (Teleop, +B4-Fälle).
