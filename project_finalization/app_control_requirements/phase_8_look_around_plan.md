# Phase 8 — Show-Erweiterung: „Look-Around" (Kamera-Umschauen) — Plan

> **Ziel:** eine App-startbare **Show „Look-Around"** — der Roboter steht (alle 6 Füße **fix am
> Boden**) und der **Körper** wird per Sticks in mehreren Freiheitsgraden bewegt: **umschauen**
> (Kamera hoch/runter/links/rechts), in der Ebene **wandern** und die **Höhe** stufenlos verstellen.
> Beim Loslassen federt alles sanft in die Ausgangs-Pose zurück. Das Show-Menü der App bekommt
> zusätzlich **Platzhalter** für „Dancing" und „Free-Leg" (ROS nimmt sie an, tut aber noch nichts),
> damit die App **einmal** vollständig gebaut werden kann.
>
> **Seite:** ROS + App. **Status: 🟡 Plan.** Self-contained für einen frischen Chat.
> Contract: [`interface_contract.md`](interface_contract.md) (§3/§4/§6, `[TBD-Phase 8]`).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da, wiederverwendbar):**
- **Show-Infrastruktur** (Block B4): Engine-States `STATE_SHOW_ENTER`/`_ACTIVE`/`_EXIT`; der
  `/hexapod_show_toggle`-Service; das Topic **`/cmd_show`** (`std_msgs/Float64MultiArray`, **6 Werte**,
  vom `joy_to_twist` aus den Sticks, im gait_node via `_on_cmd_show` gecacht + `_update_show_offsets`
  angewandt, mit Staleness-→-0-Handling). Diese Naht (Sticks → `/cmd_show` → gait_node) wird
  wiederverwendet.
- **Körper-Neigung bei fixen Füßen** existiert bereits über den Leveling-Mechanismus
  (`_engine.set_body_orientation_offset(roll, pitch)` → die Bein-IK gleicht bei fixen Füßen aus).
- **Höhe (Z)** über `body_height` (stufenlos setzbar).
- **`/hexapod/status`** (Phase 5, `state`-Feld) + `standing_only`-Param-Logik.

**Neu in Phase 8:**
1. **Body-Pose-Engine:** ein neuer Zustand, in dem der Körper in **6 DOF** relativ zu **fixen Füßen**
   bewegt wird. `roll/pitch` (Neigung) + `dz` (Höhe) sind da; **`dx`/`dy` (XY-Wandern) + `yaw`** sind
   neu. Alle Achsen auf den **IK-Envelope geklemmt**.
2. **Show-Auswahl app-tauglich:** ein Param **`show_mode`** (string, `standing_only`) auf dem
   gait_node mit den Werten **`none` / `look_around` / `dancing` / `free_leg`**. Die App setzt ihn.
   **Nur `look_around` ist implementiert**; `dancing`/`free_leg` werden **akzeptiert, aber no-op**
   (Platzhalter, Log „not yet implemented", bleibt STANDING).
3. **Stick-Mapping** für Look-Around (rechter Stick = Kamera-Blick, linker = Wandern, Trigger = Höhe)
   + **Return-to-Origin** (Loslassen → zurückfedern).

**Bewusst NICHT in Phase 8 (spätere Phasen / vom User selbst gemerkt):**
- **`roll`** als steuerbare Achse (Look-Around nutzt v1 nur pitch/yaw + XY + Z).
- **Dancing** (kommt später, nutzt u.a. roll) — hier nur **Platzhalter**.
- **Free-Leg** (die alte B4-Vorderbein-Show, durch leg_changes/Kal kaputt) — hier nur **Platzhalter**,
  Reparatur später.
- Kein Laufen/`cmd_vel` während der Show (Füße bleiben fix).

---

## 1. Logik-Skizze / Pseudocode

### 1a. Show-Auswahl — Param `show_mode` (App-only, [D-Show-1])
```python
# _ParamSpec: name='show_mode', default='none', standing_only=True,
#   string_constraint='none | look_around | dancing | free_leg'
# _apply_param / _on_param_change:
elif name == 'show_mode':
    self._set_show_mode(value)

def _set_show_mode(self, mode):
    if mode == self._show_mode:
        return
    if mode == 'look_around':
        self._engine.start_body_pose()          # -> STATE_BODY_POSE (fixe Füße)
    elif mode in ('dancing', 'free_leg'):
        self.get_logger().warn(f'show_mode {mode!r} noch nicht implementiert (Platzhalter)')
        mode = self._show_mode                   # kein State-Wechsel, bleibt STANDING
    elif mode == 'none':
        self._engine.stop_body_pose()            # -> zurück STANDING
    self._show_mode = mode
```
> `show_mode` ist `standing_only` → außerhalb STANDING abgelehnt (vorhandene Gate-Logik). Umschalten
> passiert **nur über diesen Param** (App), nicht über eine Controller-Taste (User-Vorgabe).

### 1b. Body-Pose-Engine — Körper in 6 DOF bei fixen Füßen ([D-Show-2])
Kern: die **Fuß-Weltpositionen** der Stand-Pose bleiben **fix**; der **Körper** wird um
`(dx, dy, dz, roll, pitch, yaw)` transformiert; die Bein-IK rechnet die neuen Gelenkwinkel für jeden
Fuß **im Körper-Frame**:
```
foot_world   = Stand-Fußposition (fix, pro Bein)
T_body       = Translation(dx,dy,dz) · Rotation(roll,pitch,yaw)   # Körper relativ zur Neutral-Pose
foot_in_body = T_body⁻¹ · foot_world      # Fuß im (bewegten) Körper-Frame
angles       = leg_ik(foot_in_body, leg, URDF_LIMITS)   # kann kein Limit verletzen (Envelope-clamped)
```
- `roll/pitch` + `dz` gibt es schon (Leveling-Offset + `body_height`) — der neue Teil ist die volle
  6-DOF-Transformation inkl. **`dx/dy` + `yaw`**.
- **Envelope-Clamp:** jede DOF wird VOR der IK auf sichere Grenzen geklemmt (`|dx|,|dy| ≤ …`,
  `|yaw| ≤ …`, `dz ∈ [bh_min, bh_max]`, `|roll/pitch| ≤ max_level_angle`) → nie out-of-reach.
- `STATE_BODY_POSE` hält statisch (wie SHOW_ACTIVE) und liest pro Tick die Ziel-DOF aus `/cmd_show`.

### 1c. Stick-Mapping (Sticks → 6 DOF → `/cmd_show`, [D-Show-3])
`joy_to_twist` publisht im Look-Around-Modus die relevanten Achsen als die **6 `/cmd_show`-Werte**
(Reuse des bestehenden 6-Wert-Topics; der gait_node interpretiert sie im `STATE_BODY_POSE`):
```
/cmd_show = [dx, dy, dz, roll, pitch, yaw]   # normalisiert -1..+1, gait_node skaliert auf Envelope
    rechter Stick Y (axis_ry) -> pitch   (Kamera hoch/runter)
    rechter Stick X (axis_rx) -> yaw     (Kamera links/rechts)
    linker  Stick Y (axis_ly) -> dx      (vor/zurück wandern)
    linker  Stick X (axis_lx) -> dy      (seitwärts wandern)
    R2 - L2 (axis_r2/axis_l2) -> dz       (Höhe hoch/runter)
    roll = 0                              (v1 nicht belegt)
```
### 1d. Return-to-Origin ([D-Show-4])
Bei neutralen Sticks (`/cmd_show ≈ 0`, bzw. stale nach `cmd_vel_timeout` — vorhandenes Handling)
lerpt die Engine die aktuellen DOF-Offsets **rate-limitiert gegen 0** (Feder-Gefühl). Keine harten
Sprünge; dieselbe Rate-Limit-Idee wie beim Show-Return (B4 `show_return_rate`).

### 1e. Platzhalter `dancing` / `free_leg` ([D-Show-5])
`show_mode` akzeptiert **alle vier** Werte von Anfang an; `dancing`/`free_leg` lösen **keinen**
State-Wechsel aus (Log „Platzhalter, noch nicht implementiert", Roboter bleibt STANDING). So kann die
**App das ganze Menü jetzt bauen**; wenn später Dancing/Free-Leg ROS-seitig kommen, muss die App
**nicht** angefasst werden (Menü + `show_mode`-Setzen existieren bereits).

---

## 2. Tests-Liste (+ was NICHT)

| Test | Prüft | Warum |
|---|---|---|
| **T8.1** Body-Pose-IK: Neutral (alle DOF 0) == Standing-Pose (bit-genau) | Nullpunkt | kein Sprung beim Eintritt |
| **T8.2** Body-Pose-IK bleibt **in URDF-Limits** über gesampelte 6-DOF-Auslenkungen (inkl. Envelope-Grenzen) | Sicherheit | kein out-of-reach/Kippen |
| **T8.3** Stick-Mapping: `/cmd_show`-Werte → korrekte DOF (pitch/yaw/dx/dy/dz), roll=0 | Mapping | Steuerung stimmt |
| **T8.4** Return-to-Origin: neutrale/stale `/cmd_show` → DOF lerpen rate-limitiert gegen 0 | Feder-Verhalten | UX + Sicherheit |
| **T8.5** `show_mode=look_around` → `STATE_BODY_POSE`; `=none` → STANDING; `=dancing`/`free_leg` → **no-op + Log + bleibt STANDING** | Auswahl + Platzhalter | Kern + App-Vorbau |
| **T8.6** `show_mode` `standing_only`: außerhalb STANDING rejected | Gating | wie andere Show-Aktionen |
| **T8.7 (Sim, User)** Look-Around fahren: Körper bewegt sich, **Füße bleiben fix**; Loslassen → zurück; `none` → wieder normal laufen | E2E | Kern-Deliverable |
| **T8.8 (HW, User)** am echten Roboter: Kamera schwenkt beim Umschauen, sauberer Rückweg | HW | am fertigen Roboter |
| **T8.9** `colcon test` + Lint grün, Walking-Regression unverändert | keine Regression | §4-Pflicht |

**Bewusst offen/später:** `roll`-Achse, Dancing, Free-Leg (nur Platzhalter); simultane 6-DOF-Extrem-
Kombis (Envelope-Clamp deckt Sicherheit ab); Choreografie-Automatik.

---

## 3. Progress-Checkliste (→ `phase_8_look_around_progress.md`, Done-Vertrag)
```
Phase 8 (Show-Erweiterung Look-Around):
- [ ] P8.1 [ROS] Engine: STATE_BODY_POSE + 6-DOF-Körper-IK (dx/dy/dz/roll/pitch/yaw) bei fixen Füßen, Envelope-clamped (T8.1/T8.2)
- [ ] P8.2 [ROS] Engine: start_body_pose/stop_body_pose + Return-to-Origin (rate-limitiert gegen 0) (T8.4)
- [ ] P8.3 [ROS] gait_node: show_mode-Param (none|look_around|dancing|free_leg, standing_only) + Handler (T8.5/T8.6)
- [ ] P8.4 [ROS] gait_node: /cmd_show im STATE_BODY_POSE als 6 DOF interpretieren (T8.3)
- [ ] P8.5 [ROS] dancing/free_leg = Platzhalter (akzeptiert, no-op, Log; kein State-Wechsel) (T8.5)
- [ ] P8.6 [ROS] joy_to_twist: Look-Around-Stick-Mapping -> /cmd_show (rechter=pitch/yaw, linker=dx/dy, Trigger=dz)
- [ ] P8.7 [ROS] Unit-Tests (T8.1-T8.6) + Lint + Walking-Regression (T8.9)
- [ ] P8.8 [ROS] Contract §3/§4/§6 festgezurrt (show_mode + /cmd_show-Semantik + Show-Enum), Version-Bump
- [ ] P8.9 [App] Show-Menü: Kamera-Umschauen / Dancing / Free-Leg / Normalbetrieb -> setzt show_mode (standing_only)
- [ ] P8.10 [App] Look-Around-Stick-Hinweis (rechter=schauen, linker=wandern, Trigger=Höhe); Dancing/Free-Leg als Platzhalter sichtbar
- [ ] P8.11 [ROS] Self-Review + Doku (README/architecture/ai_navigation, test_commands)
- [ ] P8.12 [Integration, User+App/HW] Umschauen in Sim, dann am echten Roboter (T8.7/T8.8)
```

---

## 4. Offene Punkte / Risiken (vor Code entscheiden)
1. **Show-Auswahl-Interface:** Param **`show_mode`** (string, `standing_only`, App via `set_parameters`
   — **Empfehlung**, konsistent mit `gait_pattern`/`leveling_mode`) **vs.** eigener Service/Topic. Der
   alte `/hexapod_show_toggle` (Controller-Taste) bleibt unberührt für die spätere Free-Leg-Show.
2. **`/cmd_show`-Reuse** (6 Werte = 6 DOF) **vs.** neues Topic. Reuse ist naht-sparend (das Topic hat
   exakt 6 Slots), aber die **Semantik** von `/cmd_show` hängt dann vom State ab (SHOW_ACTIVE =
   Vorderbeine; BODY_POSE = Körper-DOF). Empfehlung: **Reuse + im Contract dokumentieren**.
3. **Stick-Mapping-Ort:** in `joy_to_twist` (dort lebt das Show-Achsen-Mapping heute) **vs.** roh
   publishen + im gait_node mappen. Und: **Dead-Man (R1)** wie bei B4 verlangen, oder Look-Around
   ohne Dead-Man (bewusste Show)? **Empfehlung:** Mapping in `joy_to_twist`, **kein** Dead-Man nötig
   (Füße stehen fix, kein Fahr-Risiko) — aber Envelope-Clamp Pflicht.
4. **Envelope-Grenzen pro DOF** (wie weit `dx/dy`, `yaw`, `dz`) — offline aus dem IK-Envelope
   ableiten (analog Stance-Caps); ggf. ein kleines `look_around_envelope_check.py`.
5. **Return-Rate** (`show_return_rate`-analog) — Live justierbar.

---

## 5. App-Seiten-Brief (self-contained)
- **Show-Menü** (nur in **STANDING** aktiv) mit vier Einträgen:
  - **Kamera-Umschauen** (`look_around`) — implementiert.
  - **Dancing** (`dancing`) — **Platzhalter** (ROS akzeptiert, tut noch nichts).
  - **Free-Leg** (`free_leg`) — **Platzhalter**.
  - **Normalbetrieb** (`none`) — Show verlassen, danach normal fahren.
- Auswahl = **`show_mode`** auf `/gait_node` setzen (native rosbridge-`set_parameters`, Muster wie das
  Config-Panel). `standing_only` → außerhalb STANDING zeigt die App den Reject-`reason`.
- **Im Look-Around** steuern die Sticks den Körper: **rechter Stick = umschauen** (hoch/runter/links/
  rechts), **linker Stick = wandern** (vor/zurück/seitwärts), **L2/R2 = Höhe**. Loslassen → zurück.
  (Diese Stick-Bedienung läuft über `/joy` wie gehabt — die App muss dafür nichts Neues tun.)
- **Der Clou:** Menü **komplett** bauen (alle vier Einträge). `dancing`/`free_leg` sind schon
  triggerbar — wenn ROS sie später umsetzt, ist **kein** App-Eingriff mehr nötig.

## 6. Contract-Touchpoints (→ festzurren, v0.13)
- **§4 (Params):** `show_mode` (string, `/gait_node`, `standing_only`, Enum
  `none|look_around|dancing|free_leg`; nur `look_around` wirkt, Rest Platzhalter).
- **§3 (Topics):** `/cmd_show`-Semantik erweitern (im Look-Around = 6 Körper-DOF).
- **§6a `capabilities`:** ein `show_modes`-Enum ergänzen, damit die App das Menü generisch rendern kann.
- **Version-Bump v0.13.**

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_8_look_around_progress.md` + `phase_8_look_around_test_commands.md`.
- `hexapod_gait/README.md` (Body-Pose-Modus) + `architecture.md` + `ai_navigation.md`
  („Show/Body-Pose ändern"-Eintrag).

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

### Schritt 1 — Engine (Body-Pose)
- `gait_engine.py`: `STATE_BODY_POSE` + `start_body_pose()`/`stop_body_pose()`; pro Tick
  `_compute_body_pose_targets()` = Stand-Fußpositionen (fix) durch `T_body⁻¹` transformieren →
  `leg_ik` pro Bein. **Reuse:** die Stand-Fußpositionen liefert `_compute_standing_targets`; die
  roll/pitch-Transformation existiert schon (Leveling `set_body_orientation_offset`) — **erweitern**
  um `dx/dy/dz/yaw`. Envelope-Clamp vor der IK.
- Return-to-Origin: aktuelle DOF gegen 0 rate-limitieren (Muster = `show_return_rate` / Slew im Show-
  Exit).

### Schritt 2 — gait_node
- `_ParamSpec('show_mode', 'none', standing_only=True, string_constraint=…)` + `_apply_param`-Zweig +
  `_set_show_mode` (§1a). `dancing`/`free_leg` = Log + no-op.
- `/cmd_show`-Interpretation: im `STATE_BODY_POSE` die 6 Werte als DOF an die Engine geben (neben dem
  bestehenden SHOW_ACTIVE-Pfad in `_update_show_offsets`).

### Schritt 3 — joy_to_twist
- Look-Around-Mapping (§1c) → `/cmd_show`. Modus-Kenntnis: entweder aus `/hexapod/status.state`
  (BODY_POSE) subscriben oder show_mode spiegeln. Kein Dead-Man (Design-Punkt §4.3).

### Schritt 4 — Tests
- Engine-Unit `test_body_pose.py`: Neutral==Stand (T8.1), 6-DOF-Sampling in-limits (T8.2, Muster
  `test_startup_ramp.py`-Limitcheck), Return-to-Origin (T8.4).
- Node-Unit: `show_mode`-Übergänge + Platzhalter + standing_only (Muster `test_sitdown_node.py`).

### Schritt 5 — Build + Sim-Test
```bash
colcon build --packages-select hexapod_gait hexapod_teleop && source install/setup.bash
# Sim hoch, aufstehen (STANDING), dann:
ros2 param set /gait_node show_mode look_around      # -> Körper per Sticks bewegbar, Füße fix
# rechter Stick = umschauen, linker = wandern, L2/R2 = Höhe; loslassen -> zurück
ros2 param set /gait_node show_mode dancing          # -> Log "Platzhalter", bleibt STANDING
ros2 param set /gait_node show_mode none             # -> zurück, normal fahren
```

---

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Show-1] Shows 1–4 = EINE Show „Look-Around"** (6-DOF-Body-Pose), nicht vier getrennte. Ein
  Mechanismus, eine Bedienung, ein Menüpunkt; die früheren Einzel-Ideen (nur Yaw / nur XY / nur Höhe /
  Kamera+Höhe) sind **Teilmengen** (nutzt man nur die jeweiligen Achsen). **Verworfen:** vier separate
  Shows (Menü-Klutter, vierfacher Code für denselben Mechanismus).
- **[D-Show-2] Body-Pose bei fixen Füßen** (nicht Free-Leg). Statisch stabil (alle 6 Füße am Boden),
  Kamera schwenkt mit, nicht durch die Vorderbein-Kalibrierung begrenzt. roll/pitch/Z reuse, XY+yaw neu.
- **[D-Show-3] `show_mode`-Param + `/cmd_show`-Reuse** (statt neuer Service/Topic). Konsistent mit
  `gait_pattern`; `/cmd_show` hat exakt 6 Slots für 6 DOF. **Verworfen:** Custom-Service (Overhead),
  neues Topic (unnötig).
- **[D-Show-4] Return-to-Origin** (Loslassen → zurückfedern) statt Halten. „Feder-Gefühl", idioten-
  sicher, kein versehentliches Verharren in Extrem-Pose. Rate-limitiert.
- **[D-Show-5] `dancing`/`free_leg` als Platzhalter von Anfang an** im `show_mode`-Enum → App wird
  **einmal** komplett gebaut; spätere ROS-Umsetzung braucht **keinen** App-Eingriff. **Verworfen:**
  Enum erst später erweitern (dann müsste die App nochmal ran).
- **[D-Show-6] `roll` v1 weggelassen** — für „Umschauen" nicht intuitiv nötig; hält das Mapping sauber
  (kommt evtl. mit „Dancing"). *(User-Vorgabe.)*
