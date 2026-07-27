# Phase 8 — Show-Erweiterung: „Look-Around" (Kamera-Umschauen) — Plan

> **Ziel:** eine App-startbare **Show „Look-Around"** — der Roboter steht (alle 6 Füße **fix am
> Boden**) und der **Körper** wird per Sticks in mehreren Freiheitsgraden bewegt: **umschauen**
> (Kamera hoch/runter/links/rechts), in der Ebene **wandern** und die **Höhe** stufenlos verstellen.
> Beim Loslassen federt alles sanft in die Ausgangs-Pose zurück. Das Show-Menü der App bekommt
> zusätzlich **Platzhalter** für „Dancing" und „Free-Leg" (ROS nimmt sie an, tut aber noch nichts),
> damit die App **einmal** vollständig gebaut werden kann.
>
> **Seite:** ROS + App. **Status: 🟡 Plan — §4 entschieden, User-Freigabe für die Umsetzung
> eingeholt.** Self-contained für einen frischen Chat.
> Contract: [`interface_contract.md`](interface_contract.md) (§3/§4/§6, `[TBD-Phase 8]`).

---

## 0. Ziel + Abgrenzung

**Bestand (schon da, wiederverwendbar):**
- **Show-Infrastruktur** (Block B4): Engine-States `STATE_SHOW_ENTER`/`_ACTIVE`/`_EXIT`; der
  `/hexapod_show_toggle`-Service; das Topic **`/cmd_show`** (`std_msgs/Float64MultiArray`, **6 Werte**,
  vom `joy_to_twist` aus den Sticks, im gait_node via `_on_cmd_show` gecacht + `_update_show_offsets`
  angewandt, mit Staleness-→-0-Handling). Das **Muster** dieser Naht (Stick-Werte → normiertes
  6-Wert-Topic → gait_node skaliert im passenden State + Rate-Limit) wird übernommen — **das Topic
  selbst nicht** (eigenes `/cmd_body_pose`, Begründung §4.2). B4 bleibt komplett unberührt.
- **Körper-Neigung bei fixen Füßen** existiert bereits über den Leveling-Mechanismus
  (`_engine.set_body_orientation_offset(roll, pitch)` → die Bein-IK gleicht bei fixen Füßen aus).
- **Höhe (Z)** über `body_height` (stufenlos setzbar).
- **`/hexapod/status`** (Phase 5, `state`-Feld) + `standing_only`-Param-Logik.

**Neu in Phase 8:**
1. **Body-Pose-Engine:** ein neuer Zustand (`STATE_BODY_POSE`), in dem der Körper in **6 DOF**
   relativ zu **fixen Füßen** bewegt wird. Die roll/pitch-Rotation gibt es als Mechanik schon
   (Leveling); **`dx`/`dy` (XY-Wandern), `dz` und `yaw`** sind neu. Begrenzung zweistufig:
   **Per-Achse-Clamp + Greedy-Achsen-Nachführung** (§1b/§4.4) — nie out-of-limit, nie Freeze.
2. **Show-Auswahl app-tauglich:** ein Param **`show_mode`** (string, **eigenes Gate**: Show-Modi nur
   aus STANDING, `none` immer) auf dem gait_node mit den Werten
   **`none` / `look_around` / `dancing` / `free_leg`**. Die App setzt ihn — **app-exklusiv**, kein
   Controller-Weg. **Nur `look_around` ist implementiert**; `dancing`/`free_leg` werden
   **akzeptiert, aber no-op** (Platzhalter, Log „not yet implemented", bleibt STANDING).
3. **Stick-Mapping** für Look-Around auf dem **neuen Topic `/cmd_body_pose`** (rechter Stick =
   Kamera-Blick, linker = Wandern, L2/R2 = Höhe, **R1 = Dead-Man**) + **Return-to-Origin**
   (Loslassen → zurückfedern).
4. **Envelope-Tool** `tools/look_around_envelope_check.py` (belegt die Grenzen offline, P8.0).

**Bewusst NICHT in Phase 8 (spätere Phasen / vom User selbst gemerkt):**
- **`roll`** als steuerbare Achse (Look-Around nutzt v1 nur pitch/yaw + XY + Z).
- **Dancing** (kommt später, nutzt u.a. roll) — hier nur **Platzhalter**.
- **Free-Leg** (die alte B4-Vorderbein-Show, durch leg_changes/Kal kaputt) — hier nur **Platzhalter**,
  Reparatur später.
- Kein Laufen/`cmd_vel` während der Show (Füße bleiben fix).

---

## 1. Logik-Skizze / Pseudocode

### 1a. Show-Auswahl — Param `show_mode` (App-only, [D-Show-1] / [D-Show-6a])
```python
# _ParamSpec: name='show_mode', default='none', standing_only=False (!),
#   string_constraint='none | look_around | dancing | free_leg'
#
# EIGENES Gate in _on_param_change (NICHT die generische _STANDING_ONLY_PARAMS-
# Liste — die würde auch 'none' im BODY_POSE ablehnen = Sackgasse, s. §4.1):
for p in params:
    if p.name != 'show_mode':
        continue
    if p.value not in ('none', 'look_around', 'dancing', 'free_leg'):
        return SetParametersResult(successful=False, reason='unknown show_mode …')
    if p.value != 'none' and self._engine.state != GaitEngine.STATE_STANDING:
        return SetParametersResult(
            successful=False,
            reason=f'show_mode {p.value!r} braucht STANDING (state={…})')
    # 'none' ist IMMER erlaubt = der Rückweg aus dem BODY_POSE.

# _apply_param:
elif name == 'show_mode':
    self._set_show_mode(value)

def _set_show_mode(self, mode):
    if mode == self._show_mode:
        return
    if mode == 'look_around':
        self._engine.start_body_pose(t)          # -> STATE_BODY_POSE (fixe Füße)
    elif mode in ('dancing', 'free_leg'):
        self.get_logger().warn(f'show_mode {mode!r} noch nicht implementiert (Platzhalter)')
        mode = 'none'                            # kein State-Wechsel, bleibt STANDING
    elif mode == 'none':
        self._engine.stop_body_pose(t)           # Return-to-Origin -> STANDING
    self._show_mode = mode
```
> Umschalten passiert **nur über diesen Param** (App via `set_parameters`), nicht über eine
> Controller-Taste — **Shows sind app-exklusiv** (User-Vorgabe): ein Controller publisht nur `/joy`
> und kann keine Parameter setzen. Der alte Controller-Einstieg (Cross-Longpress →
> `/hexapod_show_toggle`) bleibt unangetastet und ist per `show_enabled: false` in
> `ps4_usb.yaml`/`ps4_bt.yaml` ohnehin tot.
>
> **Nicht ins Config-Manifest** (`hmi_config_manifest.yaml`): `show_mode` wird im **Show-Menü** der
> App gesetzt, nicht im Config-Panel (User-Vorgabe). Technisch derselbe `set_parameters`-Aufruf,
> nur ein anderer Ort im UI. Im Manifest würde das Panel es automatisch als Dropdown mitrendern.
>
> **Ist-Zustand:** `show_mode` kommt zusätzlich ins `/hexapod/status`-JSON (§6) — die App spiegelt
> ihn, statt ihn zu raten. Verlässt der Roboter den BODY_POSE serverseitig (Recovery, Hinsetzen),
> wird `show_mode` auf `none` zurückgesetzt und der Param-Server nachgezogen.

### 1b. Body-Pose-Engine — Körper in 6 DOF bei fixen Füßen ([D-Show-2])
Kern: die **Fuß-Weltpositionen** der Stand-Pose bleiben **fix**; der **Körper** wird um
`(dx, dy, dz, roll, pitch, yaw)` transformiert; die Bein-IK rechnet die neuen Gelenkwinkel für jeden
Fuß **im Körper-Frame**:
```
foot_base_fix = SNAPSHOT beim Eintritt: leg_to_base_frame(_compute_standing_targets(t)[leg], leg)
R             = Rz(yaw) · Ry(pitch) · Rx(roll)            # Körper-Drehung
foot_in_body  = R⁻¹ · (foot_base_fix − (dx,dy,dz))        # Fuß im (bewegten) Körper-Frame
angles        = leg_ik(base_to_leg_frame(foot_in_body, leg), leg, URDF_LIMITS)
```
- **Fuß-Snapshot statt Live-Neuberechnung** ([D-Show-11]): beim Eintritt werden die aktuellen
  Stand-Fuß-Targets **einmal** in den base-Frame gerechnet und festgehalten. Damit stehen die Füße
  wirklich fix — auch wenn Adaptive Stand (S4-7) sie vorher unterschiedlich tief verankert hat — und
  DOF = 0 liefert **bit-genau** die Stand-Pose (T8.1, nahtloser Eintritt).
- `roll/pitch` gibt es als Rotation schon (`_leveled_ik_at` = derselbe Round-Trip ohne Translation/
  yaw) — der neue Teil ist die volle 6-DOF-Transformation inkl. **`dx/dy` + `yaw`**.
- **Zweistufige Begrenzung** ([D-Show-8], User-Entscheidung §4.4 „großzügig + weicher Fallback"):
  1. **Per-Achse-Clamp** auf die Envelope-Params (Zahlen + Herleitung §4.4) — großzügig, aus dem
     Einzelachsen-Sweep mit Marge.
  2. **Greedy-Achsen-Nachführung** pro Tick: der rate-limitierte Kandidat wird als **Gesamt-Pose**
     per IK getestet; schlägt er fehl, wird er **achsenweise** angewandt (feste Reihenfolge
     `dz, pitch, yaw, dx, dy`) und je Achse nur übernommen, wenn die resultierende Gesamt-Pose
     gültig bleibt. Effekt: eine Achse an der Wand blockiert die anderen **nicht**; es fühlt sich
     an wie ein Gummiband statt eines Freeze. Muster = `_compute_show_active_angles` (B4:
     „Schritt nur übernehmen, wenn IK gültig"), nur per Achse statt global.
  3. **Notausgang** (nur bei externer Param-Änderung während der Show, z.B. `body_height`): ist
     schon der Ist-Zustand ungültig, wird er halbiert Richtung 0, bis er gültig ist (0 = Stand-Pose
     ist per Definition gültig). Kein IKError → **kein Freeze durch die Show**.
- `STATE_BODY_POSE` hält statisch (wie SHOW_ACTIVE) und liest pro Tick die Ziel-DOF aus
  `/cmd_body_pose`. `cmd_vel` wird in diesem State ignoriert (`set_command`-Guard — ai_navigation-
  Falle „jeder neue State muss cmd_vel ignorieren").
- **Kein Leveling im BODY_POSE:** `_LEVELING_STATES` bleibt unverändert (STANDING/WALKING/STOPPING)
  → der Node setzt in diesem State Offset 0/0 + Controller-Reset. Gewollt: die Body-Pose **ist**
  bewusst geneigt, ein Leveling-Regler würde dagegenarbeiten.
- **CoG:** bei 6 Füßen am Boden ist das Stützpolygon groß; bindend ist praktisch immer das
  Coxa-Limit ±0.415, nicht die Kipp-Stabilität. Das wird im Envelope-Tool **mitgemessen**
  (`joint_load.compute_load`, 6-Bein-Polygon) statt behauptet — kein Laufzeit-CoG-Gate (anders als
  B4, wo nur 4 Beine tragen).

### 1c. Stick-Mapping (Sticks → 6 DOF → `/cmd_body_pose`, [D-Show-3] / [D-Show-7])
`joy_to_twist` publisht ein **neues, eigenes Topic** `/cmd_body_pose`
(`std_msgs/Float64MultiArray[6]`, normiert −1..+1) — **nicht** `/cmd_show` (Begründung §4.2):
```
/cmd_body_pose = [dx, dy, dz, roll, pitch, yaw]   # −1..+1, gait_node skaliert auf den Envelope
    rechter Stick Y (axis_ry) -> pitch   (Kamera hoch/runter)
    rechter Stick X (axis_rx) -> yaw     (Kamera links/rechts)
    linker  Stick Y (axis_ly) -> dx      (vor/zurück wandern)
    linker  Stick X (axis_lx) -> dy      (seitwärts wandern)
    R2 - L2 (axis_r2/axis_l2) -> dz      (Höhe hoch/runter, Differenz der Trigger-Anteile)
    roll = 0                             (v1 nicht belegt, Slot bleibt für „Dancing")
```
- **Dead-Man R1** (User-Entscheidung §4.3): ohne gehaltenes R1 publisht `joy_to_twist` sechs Nullen
  → der Körper federt zurück. Identisch zum `cmd_vel`-/`cmd_show`-Gate, ein Muster für alles.
  Konfliktfrei: L2/R2 **ohne** R1 sind weiterhin der Stance-Cycle, **mit** R1 sind sie hier `dz`
  (dieselbe zustandslose Trennung wie bei B4.11).
- **Zustandslos + immer publishen** (User-Entscheidung): `joy_to_twist` kennt den Engine-State nicht
  (Design-Prinzip C §0) und publisht in **beiden** Profilen (`controller` + `app`). Wirkungslos,
  solange kein `show_mode` gesetzt ist — und setzen kann ihn nur die App. Nebeneffekt: die
  Sim-Abnahme (T8.7) ist mit dem PS4-Controller fahrbar (`ros2 param set /gait_node show_mode …`).

### 1d. Return-to-Origin ([D-Show-4])
Bei neutralen Sticks / losgelassenem R1 (`/cmd_body_pose ≈ 0`, bzw. stale nach `cmd_vel_timeout` —
vorhandenes Staleness-Muster) führt die Engine die Ist-DOF **rate-limitiert gegen 0** (Feder-Gefühl):
getrennte Raten für Translation (`body_pose_rate_lin`, m/s) und Rotation (`body_pose_rate_ang_dps`,
°/s), dieselbe Rate gilt fürs Folgen **und** fürs Zurückfedern (Muster B4 `show_return_rate`).
**Verlassen (`show_mode=none`)** nutzt genau diesen Weg: Ziel-DOF auf 0 setzen + „Exit-Flag";
sobald alle DOF konvergiert sind (< Epsilon), wechselt der State nach `STANDING` — kein Sprung,
keine zweite Sequenz-Mechanik.

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
| **T8.2** Body-Pose-IK bleibt **in URDF-Limits** über gesampelte 6-DOF-Auslenkungen (alle Envelope-Ecken × 3 Stance-Höhen) | Sicherheit | kein out-of-reach/Kippen |
| **T8.3** Stick-Mapping: `/cmd_body_pose`-Werte → korrekte DOF (pitch/yaw/dx/dy/dz), roll=0, **R1-Gate** (ohne Dead-Man alle 6 = 0) | Mapping | Steuerung stimmt |
| **T8.4** Return-to-Origin: neutrale/stale `/cmd_body_pose` → DOF konvergieren rate-limitiert monoton gegen 0; `show_mode=none` → nach Konvergenz STANDING | Feder-Verhalten | UX + Sicherheit |
| **T8.5** `show_mode=look_around` → `STATE_BODY_POSE`; `=none` → STANDING; `=dancing`/`free_leg` → **no-op + Log + bleibt STANDING/none** | Auswahl + Platzhalter | Kern + App-Vorbau |
| **T8.6** Gate: Show-Modi außerhalb STANDING rejected (mit `reason`), **`none` auch im BODY_POSE akzeptiert** (Rückweg) | Gating | Sackgasse-Schutz (§4.1) |
| **T8.7 (Sim, User)** Look-Around fahren: Körper bewegt sich, **Füße bleiben fix**; Loslassen → zurück; `none` → wieder normal laufen | E2E | Kern-Deliverable |
| **T8.8 (HW, User)** am echten Roboter: Kamera schwenkt beim Umschauen, sauberer Rückweg | HW | am fertigen Roboter |
| **T8.9** `colcon test` + Lint grün, Walking-Regression unverändert | keine Regression | §4-Pflicht |
| **T8.10** Greedy-Achsen-Clamp: eine Achse am Anschlag blockiert die anderen nicht; **keine** Kombination verlässt die URDF-Limits; kein IKError nach außen | Kern-Sicherheitsnetz | ersetzt den harten Freeze (§1b.2) |
| **T8.11** `cmd_vel` wird im BODY_POSE ignoriert (kein WALKING-Übergang) | State-Guard | ai_navigation-Falle |
| **T8.12** Status/Reset: `/hexapod/status` trägt `show_mode` + `state=BODY_POSE`; Recovery/Hinsetzen setzen `show_mode` serverseitig auf `none` | App-Konsistenz | App spiegelt, statt zu raten |
| **T8.13** Envelope-Tool `look_around_envelope_check.py` GREEN für die Default-Grenzen über **alle 3 Stance-Höhen** (+ CoG-Marge berichtet) | Offline-Gate | Werte belegt statt geraten |

**Bewusst offen/später:** `roll`-Achse, Dancing, Free-Leg (nur Platzhalter); Choreografie-Automatik;
Komfort-Routing „Hinsetzen aus dem Look-Around" (v1: Reject mit klarem Grund, App setzt erst
`show_mode=none` — §4.6).

---

## 3. Progress-Checkliste (→ `phase_8_look_around_progress.md`, Done-Vertrag)
```
Phase 8 (Show-Erweiterung Look-Around):
- [ ] P8.0 [ROS] Envelope-Tool tools/look_around_envelope_check.py + Default-Grenzen belegt (alle 3 Stance-Höhen, CoG-Marge) (T8.13)
- [ ] P8.1 [ROS] Engine: STATE_BODY_POSE + 6-DOF-Körper-IK (dx/dy/dz/roll/pitch/yaw) bei fixen Füßen (Fuß-Snapshot), Envelope-clamped (T8.1/T8.2)
- [ ] P8.2 [ROS] Engine: start_body_pose/stop_body_pose + Return-to-Origin (rate-limitiert gegen 0, Exit bei Konvergenz) (T8.4)
- [ ] P8.2b [ROS] Engine: greedy-Achsen-Clamp + Notausgang statt IKError/Freeze; cmd_vel-Guard für BODY_POSE (T8.10/T8.11)
- [ ] P8.3 [ROS] gait_node: show_mode-Param (none|look_around|dancing|free_leg) + eigenes Gate (Show-Modi nur STANDING, none immer) (T8.5/T8.6)
- [ ] P8.4 [ROS] gait_node: neues /cmd_body_pose-Sub (6 DOF, Staleness->0) + Envelope-/Raten-Params -> Engine (T8.3)
- [ ] P8.5 [ROS] dancing/free_leg = Platzhalter (akzeptiert, no-op, Log; kein State-Wechsel) (T8.5)
- [ ] P8.5b [ROS] gait_node: show_mode im /hexapod/status + serverseitiger Reset auf none (Recovery/Hinsetzen) (T8.12)
- [ ] P8.6 [ROS] joy_to_twist: Look-Around-Stick-Mapping -> /cmd_body_pose (rechter=pitch/yaw, linker=dx/dy, R2-L2=dz), R1-Dead-Man, beide Profile
- [ ] P8.7 [ROS] Unit-Tests (T8.1-T8.6, T8.10-T8.12) + Lint + Walking-Regression (T8.9)
- [ ] P8.8 [ROS] Contract §3/§4/§6 festgezurrt (show_mode + /cmd_body_pose + status.show_mode + capabilities.show_modes), Version-Bump v0.13
- [ ] P8.9 [App] Show-Menü (NICHT Config-Panel): Kamera-Umschauen / Dancing / Free-Leg / Normalbetrieb -> setzt show_mode
- [ ] P8.10 [App] Look-Around-Stick-Hinweis (R1 halten; rechter=schauen, linker=wandern, L2/R2=Höhe); Dancing/Free-Leg als Platzhalter sichtbar
- [ ] P8.11 [ROS] Self-Review + Doku (README/architecture/ai_navigation, progress/test_commands)
- [ ] P8.12 [Integration, User+App/HW] Umschauen in Sim, dann am echten Roboter (T8.7/T8.8)
```

---

## 4. Entscheidungen (vor Code geklärt — User-Freigabe eingeholt)

> Alle Punkte sind **entschieden**; die Alternativen stehen als Design-Log in §9.

**4.1 Show-Auswahl-Interface → Param `show_mode` mit EIGENEM Gate** (nicht `standing_only`,
nicht Service). Grund für das eigene Gate: Look-Around ist ein **eigener** Engine-State
(`BODY_POSE`), nicht `STANDING`. Der generische `_STANDING_ONLY_PARAMS`-Check
(`gait_node._on_param_change`) würde dort **jeden** `show_mode`-Set ablehnen — auch `none`, also
den Rückweg → die App käme aus der Show nicht mehr heraus. Regel daher: Show-Modi nur aus
STANDING, **`none` immer**. *Verworfen:* (a) `standing_only` wörtlich (Sackgasse, bräuchte einen
zweiten „Verlassen"-Service oder ein verfälschtes Status-`state`), (b) eigener Service (erstes
Custom-`.srv` im Projekt — Contract §7.3 hat sich bewusst dagegen entschieden; dritter Aufruf-Pfad
in der App; Ist-Zustand nicht per `get_parameters` lesbar).
**Zusatz-Vorgabe (User): Shows sind app-exklusiv** — kein Controller-Einstieg (der kann keine
Params setzen); und die Auswahl gehört ins **Show-Menü**, **nicht** ins Config-Panel → `show_mode`
kommt **nicht** ins `hmi_config_manifest.yaml`.

**4.2 Stick-Naht → neues Topic `/cmd_body_pose`** (kein `/cmd_show`-Reuse). Drei Gründe:
1. **Die Mappings sind inkompatibel.** `/cmd_show` trägt
   `[l6_lat,l6_vert,l6_radial,l1_lat,l1_vert,l1_radial]`; Look-Around braucht u.a. `dz = R2−L2`
   (eine *Kombination* zweier Achsen). Ein Array kann nicht beide Semantiken tragen.
2. **`joy_to_twist` müsste den Engine-State kennen**, um umzuschalten — das bricht dessen
   Design-Prinzip (C §0: „Teleop ist reines UI, kennt KEINEN Engine-State").
3. **`/cmd_show` wird aktuell gar nicht publisht** (`show_enabled: false` in `ps4_usb.yaml` **und**
   `ps4_bt.yaml`, leg_changes/S6: Free-Leg-Show auf HW instabil). Ein Reuse hätte diesen Schalter
   mit-aktiviert und damit die alte, instabile Show wieder erreichbar gemacht.
Das neue Topic hält beide Shows sauber getrennt; die Free-Leg-Reparatur bleibt unberührt möglich.

**4.3 Dead-Man → R1 wird verlangt** (User-Entscheidung). Ohne gehaltenes R1 sind alle sechs Werte 0
→ der Körper federt zurück. Konsistent mit `cmd_vel`/`/cmd_show`; L2/R2 ohne R1 bleiben der
Stance-Cycle. *Verworfen:* ohne Dead-Man (wäre bequemer beim beidhändigen Umschauen, aber
uneinheitlich zum Rest der Bedienung).

**4.4 Envelope-Grenzen → großzügig pro Achse + weicher Greedy-Clamp** (User-Entscheidung).
Vorab gerechnet gegen die **URDF-Limits** (coxa ±0.415 / femur ±1.57 / tibia −0.28..+2.50),
Fuß fix, alle drei Stance-Höhen:

| | dx | dy | dz | pitch | yaw |
|---|---|---|---|---|---|
| **einzeln** (Stance mittel) | ±68 mm | ±60 mm | +74/−72 mm | ±26° | ±14° |
| **einzeln** (schlechteste der 3 Höhen) | ±62 mm | ±48 mm | +54/−58 mm | ±20° | ±14° |
| **alle gleichzeitig** (Worst-Case-Ecke) | ±22 mm | ±22 mm | ±11 mm | ±5,6° | ±5,6° |

Bindend ist fast immer **coxa ±0.415** (dx, dy und yaw addieren sich lateral), sonst der Reach
(0.194 m) bzw. die **Femur-Wand ±1.57** (bei pitch + Absenken). **Konsequenz:** ein statischer,
kombinationsfester Clamp müsste auf ±2 cm / ±5° gehen — die Show wäre kaum sichtbar. Daher
großzügige Einzelachs-Grenzen **plus** die Greedy-Nachführung aus §1b.2, die Kombinationen weich
einbremst.

**Default-Grenzen (P8.0 belegt, `look_around_envelope_check.py` GREEN, Exit 0):**

| DOF | Default | Einzelachs-Maximum (schlechteste Stance-Höhe) | Marge |
|---|---|---|---|
| `body_pose_dx_max` | **±0.050 m** | ±0.062 m | 19 % |
| `body_pose_dy_max` | **±0.035 m** | ±0.048 m | 27 % |
| `body_pose_dz_max` | **±0.020 m** | +0.054/−0.058 m | s.u. (Gesten-gebunden) |
| `body_pose_pitch_max_deg` | **±12°** | ±20° | 40 % |
| `body_pose_yaw_max_deg` | **±10°** | ±14° | 29 % |
| `body_pose_roll_max_deg` | **0°** (v1 aus) | ±17° | — |

Das Gate prüft drei Stufen: (1) **Einzelachse** an der Grenze, (2) **CoG-Marge** ≥ 30 mm — gemessen
im **Welt-Frame** (Neigung geht korrekt ein), Ergebnis **166–200 mm**, also weit unkritisch (belegt
[D-Show-12]), und (3) **Bedien-Gesten**: was *eine* Hand in *einer* Bewegung erzeugt — Stick-
Diagonalen (mit Gewicht 0.75 statt 1.0, weil ein Analog-Stick in einem runden Gate läuft und die
Diagonale physisch nur ~0.71 pro Achse liefert), sowie „Stick voll + Trigger voll".
**`dz` und `pitch` konkurrieren** (beide laden die Femur-Wand): pitch 15° erlaubt nur dz 10 mm,
pitch 12° erlaubt dz 20 mm, pitch 10° erlaubt dz 25 mm. Gewählt wurde **pitch 12° / dz 20 mm** —
Vorrang fürs Umschauen (Kern der Show), Höhe ist Beiwerk (dafür gibt es die Stance-Modi).
*Verworfen:* konservativ-statisch (zahm), L1-Budget-Normierung (deterministisch, aber die Grenze
wäre eine Heuristik statt der echten IK-Wahrheit).

**4.5 Raten:** `body_pose_rate_lin` (m/s) + `body_pose_rate_ang_dps` (°/s), live justierbar, gelten
fürs Folgen **und** fürs Zurückfedern (Muster B4 `show_return_rate`). Startwerte: 0.08 m/s / 30 °/s.

**4.6 Hinsetzen aus dem Look-Around** (beim Bau aufgetaucht): `/hexapod_sit_down` verlangt STANDING.
v1 = **Reject mit klarem Grund** („erst `show_mode=none`"), den die App anzeigt — kein
Komfort-Routing. Begründung: weniger Sequenz-Verschachtelung, und der Rückweg ist ein einziger
Param-Set. E-Stop bleibt aus jedem State möglich (prüft keinen State).

**4.6b Show-zu-Show-Wechsel** (beim Bau aufgetaucht): ein direkter Wechsel `look_around → dancing`
wird **abgelehnt** — der Weg führt über `none`. So bleibt die Regel „Show-Modi nur aus STANDING"
auch gültig, wenn Dancing später echt wird (ein direkter Wechsel bräuchte sonst eine Zwischen-
sequenz „erst zurückfedern, dann neue Show starten"). Die App macht zwei Schritte.

**4.7 Zwei zusätzliche Start-Guards** (aus dem Self-Review, §Progress-Tabelle 1+2): ein Show-Start
wird auch abgelehnt, wenn (a) `_safety_frozen` gesetzt ist (der Tick ist gated → die Show würde
„starten", sich aber nicht bewegen) oder (b) noch kein `/joint_states` kam (`STANDING` ist dann nur
der Engine-Default; das folgende Aufstehen würde die Show sofort überschreiben).

---

## 5. App-Seiten-Brief (self-contained)
- **Show-Menü** — ein **eigener Menüpunkt „Show"**, ausdrücklich **nicht** im Config-Panel
  (User-Vorgabe). Vier Einträge, nur in **STANDING** wählbar:
  - **Kamera-Umschauen** (`look_around`) — implementiert.
  - **Dancing** (`dancing`) — **Platzhalter** (ROS akzeptiert, tut noch nichts).
  - **Free-Leg** (`free_leg`) — **Platzhalter**.
  - **Normalbetrieb** (`none`) — Show verlassen, danach normal fahren.
- Auswahl = **`show_mode`** auf `/gait_node` setzen (native rosbridge-`set_parameters`, technisch
  dasselbe Muster wie das Config-Panel, nur an anderer UI-Stelle). Außerhalb STANDING kommt
  `successful=false` + `reason` → anzeigen. **`none` wird immer akzeptiert** (= Verlassen).
- **Ist-Zustand spiegeln:** `/hexapod/status` trägt jetzt `show_mode` (+ `state` = `BODY_POSE`
  während der Show) — das Menü zeigt den aktiven Eintrag daraus, statt den eigenen Klick zu raten
  (der Roboter setzt `show_mode` z.B. bei Recovery selbst auf `none` zurück).
- **Im Look-Around** steuern die Sticks den Körper — **R1 halten** (Dead-Man, wie beim Fahren):
  **rechter Stick = umschauen** (hoch/runter/links/rechts), **linker Stick = wandern**
  (vor/zurück/seitwärts), **L2/R2 = Höhe**. Loslassen → federt zurück.
  (Läuft über `/joy` wie gehabt — die App muss dafür **nichts Neues** tun, nur den Modus setzen.)
- **Hinsetzen** geht aus der Show nicht direkt: erst `show_mode=none`, dann `/hexapod_sit_down`
  (der Reject-`reason` sagt es auch). **E-Stop** geht jederzeit.
- **Der Clou:** Menü **komplett** bauen (alle vier Einträge). `dancing`/`free_leg` sind schon
  triggerbar — wenn ROS sie später umsetzt, ist **kein** App-Eingriff mehr nötig.

## 6. Contract-Touchpoints (→ festzurren, v0.13)
- **§4 (Params):** `show_mode` (string, `/gait_node`, Enum `none|look_around|dancing|free_leg`;
  Gate: Show-Modi nur aus STANDING, `none` immer; nur `look_around` wirkt, Rest Platzhalter).
  Ausdrücklich **nicht** im `config_manifest` (App-Show-Menü statt Config-Panel).
- **§3 (Topics):** **neu** `/cmd_body_pose` (`std_msgs/Float64MultiArray[6]`,
  `[dx,dy,dz,roll,pitch,yaw]`, −1..+1, App/Teleop → Roboter, nur im BODY_POSE wirksam, R1-gegated).
  `/cmd_show` behält seine B4-Semantik **unverändert**.
- **§6a `/hexapod/status`:** neues Feld `show_mode` + neuer `state`-Wert `BODY_POSE`.
- **§6a `capabilities`:** `show_modes`-Enum ergänzen, damit die App das Menü generisch rendern kann.
- **Version-Bump v0.13.**

## 7. Doku-Nachzug (nach Umsetzung)
- `phase_8_look_around_progress.md` + `phase_8_look_around_test_commands.md`.
- `hexapod_gait/README.md` (Body-Pose-Modus) + `architecture.md` + `ai_navigation.md`
  („Show/Body-Pose ändern"-Eintrag).

---

## 8. Implementierungs-Leitfaden (self-contained — für einen frischen Chat)

### Schritt 0 — Envelope-Tool (P8.0, VOR der Engine)
- `tools/look_around_envelope_check.py` (Muster: `stand_conform_envelope_check.py`): sampelt die
  6-DOF-Body-Pose bei fixen Füßen gegen die **URDF-Limits** über alle 3 Stance-Höhen, meldet
  Einzelachs-Maxima, alle Vorzeichen-Ecken der Default-Grenzen und die **CoG-Marge** im 6-Bein-
  Polygon (`joint_load.compute_load`). Exit-Code-basiert auswerten (ai_navigation-Lehre H1.2).
  Ergebnis = die finalen Default-Werte der `body_pose_*_max`-Params.

### Schritt 1 — Engine (Body-Pose)
- `gait_engine.py`: `STATE_BODY_POSE` + `start_body_pose(t)`/`stop_body_pose(t)`; beim Start
  **Fuß-Snapshot** (§1b): `_compute_standing_targets(t)` → `leg_to_base_frame` → einfrieren.
  Pro Tick `_compute_body_pose_angles(t)`: DOF nachführen (Rate-Limit + Greedy-Clamp) →
  `R⁻¹·(foot_fix − d)` → `base_to_leg_frame` → `leg_ik`. **Reuse:** der Round-Trip
  `leg_to_base_frame → rotieren → base_to_leg_frame → leg_ik` existiert als `_leveled_ik_at`
  (Leveling) — hier um Translation + yaw erweitert; `rotate_z`/`rotate_xy` aus `geometry.py`.
- `set_body_pose_target(dx,dy,dz,roll,pitch,yaw)` (vom Node pro Tick, bereits skaliert + geklemmt).
- Return-to-Origin + Exit bei Konvergenz (§1d); Muster = `_rate_limit` (existiert schon, B4).
- `set_command`-Guard um `STATE_BODY_POSE` erweitern (cmd_vel ignorieren).

### Schritt 2 — gait_node
- `_ParamSpec('show_mode', 'none', standing_only=False, string_constraint=…)` + eigenes Gate in
  `_on_param_change` (§1a) + `_apply_param`-Zweig + `_set_show_mode`. `dancing`/`free_leg` =
  Log + no-op (fällt auf `none` zurück).
- Envelope-/Raten-Params (§4.4/§4.5) → Engine spiegeln (Muster: `touchdown_*`/`stand_conform_*`).
- Neues Sub `/cmd_body_pose` → `_on_cmd_body_pose` (cachen + Timestamp, `len>=6`-Guard) +
  `_update_body_pose(now)` im Tick **nur** im BODY_POSE (Staleness > `cmd_vel_timeout` → alle 0,
  Muster `_update_show_offsets`).
- `_publish_status`: Feld `show_mode`. Reset auf `none` in `_on_recover` +
  `_start_sitdown_sequence` (+ Param-Server nachziehen — `none` passiert das eigene Gate).

### Schritt 3 — joy_to_twist
- Look-Around-Mapping (§1c) → **neuer Publisher** `/cmd_body_pose`, **R1-gegated**, in **beiden**
  Profilen, zustandslos (kein Status-Sub, kein neuer Enable-Param). `_body_pose_from_joy(msg)`
  analog `_show_from_joy`; `dz` = `_trigger_frac(r2) − _trigger_frac(l2)`.

### Schritt 4 — Tests
- Engine-Unit `test_body_pose.py`: Neutral==Stand bit-genau (T8.1), 6-DOF-Sampling in-limits (T8.2,
  Muster `test_startup_ramp.py`-Limitcheck), Return-to-Origin + Exit (T8.4), Greedy-Clamp (T8.10),
  cmd_vel-Guard (T8.11).
- Node-Unit `test_body_pose_node.py`: `show_mode`-Übergänge + Platzhalter + Gate inkl.
  `none`-Rückweg (T8.5/T8.6), `/cmd_body_pose`-Staleness, Status-Feld + Reset (T8.12) — Muster
  `test_sitdown_node.py` / `test_show_node.py`.
- Teleop-Unit: Mapping + R1-Gate (T8.3) — Muster `test_joy_to_twist.py`.

### Schritt 5 — Build + Sim-Test
```bash
colcon build --packages-select hexapod_gait hexapod_teleop && source install/setup.bash
# Sim hoch, aufstehen (STANDING), dann:
ros2 param set /gait_node show_mode look_around      # -> Körper per Sticks bewegbar, Füße fix
# R1 HALTEN; rechter Stick = umschauen, linker = wandern, L2/R2 = Höhe; loslassen -> zurück
ros2 param set /gait_node show_mode dancing          # -> Log "Platzhalter", bleibt STANDING
ros2 param set /gait_node show_mode none             # -> zurück, normal fahren
```
(Vollständige, ausführbare Befehle kommen nach der Implementierung in
`phase_8_look_around_test_commands.md` — dort führt der User sie aus.)

---

## 9. Design-Entscheidungen (mit Alternativen)

- **[D-Show-1] Shows 1–4 = EINE Show „Look-Around"** (6-DOF-Body-Pose), nicht vier getrennte. Ein
  Mechanismus, eine Bedienung, ein Menüpunkt; die früheren Einzel-Ideen (nur Yaw / nur XY / nur Höhe /
  Kamera+Höhe) sind **Teilmengen** (nutzt man nur die jeweiligen Achsen). **Verworfen:** vier separate
  Shows (Menü-Klutter, vierfacher Code für denselben Mechanismus).
- **[D-Show-2] Body-Pose bei fixen Füßen** (nicht Free-Leg). Statisch stabil (alle 6 Füße am Boden),
  Kamera schwenkt mit, nicht durch die Vorderbein-Kalibrierung begrenzt. roll/pitch/Z reuse, XY+yaw neu.
- **[D-Show-3] `show_mode`-Param** (statt Custom-Service) für die Show-Auswahl. Konsistent mit
  `gait_pattern`/`leveling_mode`, App nutzt ihr vorhandenes `set_parameters`-Muster.
  **Verworfen:** Custom-`.srv` (erstes im Projekt, Contract §7.3 dagegen).
  ⚠️ **Revidiert ggü. dem Erstentwurf:** `/cmd_show`-**Reuse verworfen** → eigenes Topic
  `/cmd_body_pose`, siehe [D-Show-7] und §4.2.
- **[D-Show-4] Return-to-Origin** (Loslassen → zurückfedern) statt Halten. „Feder-Gefühl", idioten-
  sicher, kein versehentliches Verharren in Extrem-Pose. Rate-limitiert.
- **[D-Show-5] `dancing`/`free_leg` als Platzhalter von Anfang an** im `show_mode`-Enum → App wird
  **einmal** komplett gebaut; spätere ROS-Umsetzung braucht **keinen** App-Eingriff. **Verworfen:**
  Enum erst später erweitern (dann müsste die App nochmal ran).
- **[D-Show-6] `roll` v1 weggelassen** — für „Umschauen" nicht intuitiv nötig; hält das Mapping sauber
  (kommt evtl. mit „Dancing"). *(User-Vorgabe.)* Der Slot im Topic **bleibt** reserviert, die Engine
  ist 6-DOF-fähig, der Param `body_pose_roll_max_deg` existiert mit Default **0.0** (= aus) →
  Dancing kann ihn später scharf schalten, ohne Interface-Änderung.
- **[D-Show-6a] `show_mode` mit eigenem Gate statt `standing_only`** — Show-Modi nur aus STANDING,
  **`none` immer** (Rückweg aus dem BODY_POSE). **Verworfen:** die generische standing_only-Liste
  (sperrt die App in der Show ein, §4.1). **Verworfen:** `BODY_POSE` im Status als `STANDING`
  ausgeben (verfälscht das Overlay und öffnet alle anderen standing_only-Params mitten in der Show).
  Zusatz: **nicht** ins `config_manifest` — die Auswahl gehört ins App-Show-Menü *(User-Vorgabe)*.
- **[D-Show-7] Eigenes Topic `/cmd_body_pose`** statt `/cmd_show`-Reuse. Die beiden Mappings sind
  inkompatibel (`dz = R2−L2` ist eine Achsen-Kombination), ein Reuse hätte `joy_to_twist`
  zustandsbehaftet gemacht (bricht C §0) und über `show_enabled` die auf HW instabile Free-Leg-Show
  wieder erreichbar gemacht. **Verworfen:** Reuse mit Status-Sub; Reuse unter Aufgabe des
  Free-Leg-Mappings. Kosten: ein Topic mehr im Contract — dafür bleiben beide Shows unabhängig.
- **[D-Show-8] Zweistufige Begrenzung: großzügiger Per-Achse-Clamp + Greedy-Achsen-Nachführung**
  statt eines kombinationsfesten statischen Clamps. Datenlage §4.4: kombinationsfest wären nur
  ±22 mm / ±5,6°, einzeln aber ±62 mm / ±20°. Die Greedy-Stufe gibt „so viel wie geht" pro Achse
  und **verhindert jeden IKError aus der Show** (kein Freeze, Gummiband-Gefühl).
  **Verworfen:** (a) konservativ-statisch (Show kaum sichtbar), (b) L1-Budget-Normierung
  (deterministisch, aber Heuristik statt IK-Wahrheit), (c) globaler Skalar-Fallback à la
  `_LEVEL_FALLBACK_SCALES` (eine Achse an der Wand würde alle anderen mit runterskalieren).
- **[D-Show-9] Dead-Man R1 verlangt** *(User-Entscheidung)* — einheitlich zu `cmd_vel`/`cmd_show`;
  Loslassen = sofortiges Zurückfedern. **Verworfen:** ohne Dead-Man (bequemer beidhändig, aber
  Bedienungs-Bruch).
- **[D-Show-10] Param-Namensschema `body_pose_*`** (nicht `look_around_*`) für Envelope + Raten:
  die Mechanik ist generisch (Körper über fixen Füßen) und wird von „Dancing" wiederverwendet;
  der Show-Name lebt allein im `show_mode`-Enum. Passt zum Topic-Namen `/cmd_body_pose`.
- **[D-Show-11] Fuß-Snapshot beim Eintritt** statt Live-`_compute_standing_targets` pro Tick:
  garantiert wirklich fixe Füße (auch mit Adaptive Stand S4-7, das per Bein unterschiedlich tief
  verankert) und macht DOF=0 bit-genau zur Stand-Pose. **Verworfen:** Live-Neuberechnung (die
  adaptive Absenkung würde während der Show weiterlaufen → Füße wandern).
- **[D-Show-12] Kein Laufzeit-CoG-Gate** (anders als B4): hier tragen **6** Beine, das Coxa-Limit
  bindet lange vor der Kipp-Grenze. Statt eines Gates wird die CoG-Marge **offline im
  Envelope-Tool** über alle Ecken belegt (P8.0/T8.13). **Verworfen:** Gate pro Tick (Rechenlast +
  Hold-Verhalten mitten in einer flüssigen Show).
