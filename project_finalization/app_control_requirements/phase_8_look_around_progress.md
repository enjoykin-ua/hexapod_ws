# Phase 8 — Show „Look-Around" (Kamera-Umschauen) — Progress

> **Done-Vertrag** aus [`phase_8_look_around_plan.md`](phase_8_look_around_plan.md) §3.
> Alle Bullets `[x]` = Phase fertig. Keine retroaktive Anpassung der Kriterien.
>
> **Stand: ROS-Seite fertig** (implementiert, unit-getestet, Contract v0.13 festgezurrt).
> Offen: App-Seite (P8.9/P8.10) + Sim-/HW-Abnahme (P8.12).

---

## Checkliste

```
Phase 8 (Show-Erweiterung Look-Around):
- [x] P8.0 [ROS] Envelope-Tool tools/look_around_envelope_check.py + Default-Grenzen belegt (alle 3 Stance-Höhen, CoG-Marge) (T8.13)
- [x] P8.1 [ROS] Engine: STATE_BODY_POSE + 6-DOF-Körper-IK (dx/dy/dz/roll/pitch/yaw) bei fixen Füßen (Fuß-Snapshot), Envelope-clamped (T8.1/T8.2)
- [x] P8.2 [ROS] Engine: start_body_pose/stop_body_pose + Return-to-Origin (rate-limitiert, Exit bei Konvergenz) (T8.4)
- [x] P8.2b [ROS] Engine: greedy-Achsen-Clamp + Notausgang statt IKError/Freeze; cmd_vel-Guard für BODY_POSE (T8.10/T8.11)
- [x] P8.3 [ROS] gait_node: show_mode-Param (none|look_around|dancing|free_leg) + eigenes Gate (Show-Modi nur STANDING, none immer) (T8.5/T8.6)
- [x] P8.4 [ROS] gait_node: neues /cmd_body_pose-Sub (6 DOF, Staleness->0) + Envelope-/Raten-Params -> Engine (T8.3)
- [x] P8.5 [ROS] dancing/free_leg = Platzhalter (akzeptiert, no-op, Log; kein State-Wechsel) (T8.5)
- [x] P8.5b [ROS] gait_node: show_mode im /hexapod/status + serverseitiger Reset auf none (Recovery/Hinsetzen) (T8.12)
- [x] P8.6 [ROS] joy_to_twist: Look-Around-Stick-Mapping -> /cmd_body_pose (rechter=pitch/yaw, linker=dx/dy, R2-L2=dz), R1-Dead-Man, beide Profile
- [x] P8.7 [ROS] Unit-Tests (T8.1-T8.6, T8.10-T8.12) + Lint + Walking-Regression (T8.9)
- [x] P8.8 [ROS] Contract §3/§4/§6 festgezurrt (show_mode + /cmd_body_pose + status.show_mode + capabilities.show_modes), Version-Bump v0.13
- [ ] P8.9 [App] Show-Menü (NICHT Config-Panel): Kamera-Umschauen / Dancing / Free-Leg / Normalbetrieb -> setzt show_mode
- [ ] P8.10 [App] Look-Around-Stick-Hinweis (R1 halten; rechter=schauen, linker=wandern, L2/R2=Höhe); Dancing/Free-Leg als Platzhalter sichtbar
- [x] P8.11 [ROS] Self-Review + Doku (README/architecture/ai_navigation, progress/test_commands)
- [ ] P8.12 [Integration, User+App/HW] Umschauen in Sim, dann am echten Roboter (T8.7/T8.8)
```

---

## Was gebaut wurde

### Engine (`hexapod_gait/gait_engine.py`)
- **`STATE_BODY_POSE`** — neuer Zustand: alle 6 Füße weltfest, der Körper bewegt sich in 6 DOF.
- **`start_body_pose(t)`** friert die aktuellen Stand-Fuß-Positionen ein (base-Frame **und**
  Bein-Frame). Der Bein-Frame-Snapshot ist der Nullpunkt-Kurzschluss: bei DOF = 0 wird er direkt
  geliefert, damit der Eintritt **bit-genau** sprungfrei ist (der base-Round-Trip wäre nur
  mathematisch, nicht numerisch die Identität).
- **`_compute_body_pose_angles(t)`** pro Tick: DOF rate-limitiert nachführen → `R⁻¹·(foot−d)` →
  `base_to_leg_frame` → `leg_ik`. `R = Rz(yaw)·Ry(pitch)·Rx(roll)`, Inverse exakt in `_rot_body_inv`
  (bewusst **nicht** `rotate_xy(p,−roll,−pitch)` — falsche Reihenfolge).
- **Greedy-Achsen-Clamp** (`_advance_body_pose`): Gesamt-Schritt testen; schlägt er fehl,
  achsenweise in Priorität `dz, pitch, yaw, roll, dx, dy` anwenden und je Achse nur behalten, was
  gültig bleibt. Plus **Notausgang** (`_rescue_body_pose`): ungültige Ist-Pose Richtung 0 halbieren.
  → **aus der Show kann kein `IKError` und damit kein Safety-Freeze entstehen.**
- **`stop_body_pose(t)`** setzt Ziel 0 + Exit-Flag; bei Konvergenz → `STANDING`, geliefert wird die
  **Snapshot-Pose** (nicht die starre Stand-Pose — sonst würde ein adaptiv abgesenktes Bein
  hochgezogen).
- **Adaptive Stand (S4-7):** der Konform-Zustand bleibt über die Show erhalten (Rückkehr aus
  `BODY_POSE` ist kein frischer STANDING-Eintritt) — die Füße standen ja fix.
- `set_command` ignoriert `cmd_vel` im `BODY_POSE`.

### gait_node (`hexapod_gait/gait_node.py`)
- **Param `show_mode`** mit **eigenem Gate** (nicht `standing_only`): Show-Modi nur aus STANDING,
  **`none` immer**. `dancing`/`free_leg` = akzeptiert + WARN + Rückfall auf `none`.
- **9 neue Params**: `body_pose_{dx,dy,dz}_max`, `body_pose_{roll,pitch,yaw}_max_deg`,
  `body_pose_rate_lin`, `body_pose_rate_ang_dps` (+ `show_mode`) — alle live, alle mit Range.
- **Sub `/cmd_body_pose`** + `_update_body_pose` (Skalierung + Per-Achse-Clamp + Staleness→0).
- **`show_mode` im `/hexapod/status`**; serverseitiger Reset bei Recovery + **Selbstheilung**
  (`_maybe_sync_show_mode`), Param-Server-Sync **deferred im Tick** (ein `set_parameters` im
  Param-Callback wäre rekursiv).

### joy_to_twist (`hexapod_teleop/joy_to_twist.py`)
- **`_body_pose_from_joy`** → `/cmd_body_pose`, R1-gegated, in **beiden** Profilen, zustandslos.
  `dz = R2−L2`; Vorzeichen über `sign_body_pose_{pitch,yaw,z}`.

### Tools + Tests
- `tools/look_around_envelope_check.py` — Gate 1 (Einzelachsen), Gate 2 (CoG-Marge im Welt-Frame),
  Gate 3 (Bedien-Gesten), Exit-Code-basiert.
- `test_body_pose.py` (Engine, 24 Tests) + `test_body_pose_node.py` (Node, 23 Tests) +
  6 neue Teleop-Tests. **Gesamt: 1010 Tests grün, 0 Fehler** (gait + teleop + supervisor +
  kinematics), Lint grün.

---

## Envelope-Belege (P8.0)

`python3 tools/look_around_envelope_check.py` → **GREEN, Exit 0** über alle drei Stance-Höhen.

| DOF | Default | Einzelachs-Max (schlechteste Höhe) | Marge |
|---|---|---|---|
| `body_pose_dx_max` | ±0.050 m | ±0.062 m | 19 % |
| `body_pose_dy_max` | ±0.035 m | ±0.048 m | 27 % |
| `body_pose_dz_max` | ±0.020 m | +0.054/−0.058 m | gesten-gebunden |
| `body_pose_pitch_max_deg` | ±12° | ±20° | 40 % |
| `body_pose_yaw_max_deg` | ±10° | ±14° | 29 % |
| `body_pose_roll_max_deg` | 0° (v1 aus) | ±17° | — |

- **CoG-Marge 166–200 mm** im 6-Bein-Polygon → Kippen ist kein Thema, **kein Laufzeit-CoG-Gate**
  nötig (anders als B4, wo nur 4 Beine tragen).
- **`dz` ↔ `pitch` konkurrieren** (Femur-Wand ±1.57): pitch 15° → dz nur 10 mm; pitch 12° → 20 mm;
  pitch 10° → 25 mm. Gewählt: **pitch-Vorrang** (Umschauen ist der Kern der Show).
- Bindend ist sonst fast immer **coxa ±0.415** (dx, dy und yaw addieren sich lateral).

---

## Design-Entscheidungen dieser Phase (Kurzfassung, Details im Plan §9)

| # | Entscheidung | Verworfen |
|---|---|---|
| D-Show-6a | `show_mode` mit eigenem Gate (`none` immer erlaubt) | generische `standing_only`-Liste (App säße in der Show fest); `BODY_POSE` als `STANDING` ausgeben |
| D-Show-7 | eigenes Topic `/cmd_body_pose` | `/cmd_show`-Reuse (inkompatible Mappings, hätte Teleop zustandsbehaftet gemacht + die instabile B4-Show reaktiviert) |
| D-Show-8 | großzügiger Per-Achse-Clamp + Greedy-Achsen-Nachführung | statisch-kombinationsfest (±22 mm/±5,6° — kaum sichtbar); L1-Budget (Heuristik); globaler Skalar-Fallback (eine Achse zieht alle runter) |
| D-Show-9 | R1-Dead-Man verlangt *(User)* | ohne Dead-Man (bequemer, aber Bedienungs-Bruch) |
| D-Show-10 | Params heißen `body_pose_*` (nicht `look_around_*`) | show-spezifische Namen (die Mechanik erbt „Dancing") |
| D-Show-11 | Fuß-Snapshot beim Eintritt | Live-`_compute_standing_targets` (adaptive Absenkung würde weiterlaufen → Füße wandern) |
| D-Show-12 | kein Laufzeit-CoG-Gate, stattdessen offline belegt | Gate pro Tick (Rechenlast + Hold mitten in der Show) |
| §4.6 | Hinsetzen aus der Show → Reject mit Grund | Komfort-Routing (Sequenz-Verschachtelung) |
| §4.6b | Show-zu-Show-Wechsel nur über `none` | direkter Wechsel (bräuchte eine Zwischensequenz, sobald Dancing echt wird) |

---

## Self-Review (CLAUDE.md §4, Pflicht vor „fertig")

| # | Punkt | Bewertung | Status |
|---|---|---|---|
| 1 | **Show-Start bei aktivem Freeze**: `_safety_frozen` gated den Tick — die Show hätte „gestartet", sich aber nicht bewegt. Die App zeigte eine laufende Show, die keine ist. | echter Fund | 🔴→**OK**: Gate lehnt jetzt ab („robot is frozen — call /hexapod_recover first"), Test `test_show_rejected_while_frozen` |
| 2 | **Show-Start vor dem ersten `/joint_states`**: `STANDING` ist dann nur der Engine-Default (Roboter liegt auf dem Bauch); das folgende Auto-Standup hätte die Show sofort überschrieben. | echter Fund | 🔴→**OK**: Gate prüft `_ramp_triggered`, Test `test_show_rejected_before_first_joint_states` |
| 3 | **Tick-Aussetzer** (CPU-Hänger/Debugger): `dt` hätte den Nachführ-Schritt in **einem** Tick aufgeholt — limit-sicher (IK prüft), aber ruckartig für die Servos. | Robustheit | 🟡→**OK**: `_BODY_POSE_MAX_DT = 0.1 s` deckelt, Test `test_body_pose_step_capped_after_tick_gap` |
| 4 | **`set_parameters` im Param-Callback wäre rekursiv** (Platzhalter-Rückfall + Reset). | echter Fund (beim Bau) | **OK**: deferred `_maybe_sync_show_mode` im Tick, Muster `_maybe_sync_stance_params` |
| 5 | **Engine-Raten vor Engine-Erzeugung gespiegelt** → `AttributeError` beim Node-Start. | echter Fund (Test) | **OK**: Spiegelung hinter `GaitEngine(...)` gezogen; Node-Tests hätten es sonst erst live gezeigt |
| 6 | **Exit-Pose bei aktivem Adaptive Stand**: `_compute_stand_pose_joints()` liefert die STARRE Pose → ein konform tiefer verankertes Bein wäre beim Verlassen hochgezogen worden. | echter Fund | **OK**: Exit liefert die Snapshot-Pose; Konform-Zustand bleibt über die Show erhalten; Test `test_foot_snapshot_survives_adaptive_stand` (bit-genau) |
| 7 | **Rotations-Reihenfolge**: `rotate_xy(p,−roll,−pitch)` ist **nicht** die Inverse von `Ry·Rx`. | Fallstrick | **OK**: eigenes `_rot_body_inv` (exakt `Rx(−roll)·Ry(−pitch)·Rz(−yaw)`), Test `test_rot_body_inv_is_true_inverse` + Quervergleich mit unabhängiger Rechnung (`test_body_pose_matches_direct_ik`) |
| 8 | **Kipp-Erkennung ist in der Show aus** (`_update_tip` gated auf STANDING/WALKING). Auf einem Hang + 12° pitch gibt es keine Tip-Warnung. | bewusst | **OK (dokumentiert)**: identisch zu den B4-Show-States („kippt gewollt"); statisch abgesichert durch 6 tragende Füße + CoG-Marge ≥ 166 mm (offline belegt) |
| 9 | **Comms-Loss-Fail-safe greift in der Show nicht** (`_check_comms_loss` nur aus STANDING) → bei Verbindungsverlust setzt sich der Roboter nicht hin, sondern bleibt in der Show. | bewusst | **OK (dokumentiert)**: der Staleness-Pfad führt den Körper trotzdem in die Ausgangs-Pose zurück; Param ist Default 0 (aus). 🟢 später: Show-Ende bei Comms-Loss |
| 10 | **Vorzeichen der Stick-Achsen** sind hergeleitet, nicht gemessen. | offen | 🟡 **Sim-Verify** (T8.7): Korrektur = ein Param (`sign_body_pose_*`), kein Code |
| 11 | **Kein Audio-Cue** beim Betreten/Verlassen der Show (Phase 7A kennt nur standup/sitdown/reposition/freeze). | Politur | 🟢 später (eine Zeile `_emit_audio_cue`, wenn gewünscht) |
| 12 | **Envelope-Defaults sind gepinnt** (`test_envelope_defaults_match_tool`) — wer sie ändert, ohne das Tool zu fahren, bekommt einen roten Test. | Absicherung | **OK** |
| 13 | **`show_mode` doppelt bedienbar?** Nein — nicht im `config_manifest` (Test `test_show_mode_not_in_config_panel`), Controller-Weg bleibt per `show_enabled: false` tot. | Absicherung | **OK** |

## Offene Punkte / Nachträge

- **P8.9/P8.10 (App):** Show-Menü bauen — Start-Brief: [`phase_8_app_brief.md`](phase_8_app_brief.md)
  (self-contained, verweist auf Contract §6c).
- **P8.12 (Sim/HW):** T8.7 (Sim) + T8.8 (HW) durch den User, Befehle in
  [`phase_8_look_around_test_commands.md`](phase_8_look_around_test_commands.md).
- **Vorzeichen der Stick-Achsen** (`sign_body_pose_{pitch,yaw,z}`) sind hergeleitet, aber **in der
  Sim zu verifizieren** („Stick hoch = Kamera hoch", „R2 = höher"). Korrektur = ein Param, kein Code.
- **`roll` v1 aus** (`body_pose_roll_max_deg: 0.0`) — Slot + Engine sind 6-DOF-fähig, „Dancing"
  kann ihn ohne Interface-Änderung scharf schalten.
- 🟡 **Deferred:** Komfort-Routing „Hinsetzen direkt aus der Show" und der direkte
  Show-zu-Show-Wechsel (beide heute Reject mit Klartext-Grund).
