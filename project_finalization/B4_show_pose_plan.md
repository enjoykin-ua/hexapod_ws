# B4 — Body-Pose / Show-Pose (Free-Leg) — detaillierter Sub-Stage-Plan (Handover)

> **Status:** 🟡 aktiv — B4.0 ✅ + B4.1 ✅ (2026-06-04). Block B war pausiert für B4 — reaktiviert.
> Diese Datei ist **self-contained für einen neuen Chat**: enthält Ziel, Lese-Liste, Architektur,
> Logik, Reuse, offene Fragen, Checkliste, Tests, Validierungs-Gates und Handover-Notizen.
>
> **📊 Live-Status (done/todo pro Sub-Stage):** [`B4_show_pose_progress.md`](B4_show_pose_progress.md).

## 0. ZUERST LESEN (für den umsetzenden Chat, in dieser Reihenfolge)
1. `CLAUDE.md` §4 (Plan→Freigabe→Tests→Self-Review), §5 (Shell-Verbote), §9 (HW-Safety).
2. `PHASE.md` (aktive Phase) + `project_architecture/ai_navigation.md` (§0 Goldene Regeln,
   §1 „Standup/Reposition/Zwei-Phasen-Logik", §2 Validierungs-Gates, §3 „Wo finde ich …").
3. `project_architecture/architecture.md` (Node-Graph §2/§3, Limit-Quellen §6).
4. **DIESE Datei.** Block-Kontext: `project_finalization/B_lokomotion_kern.md` §B4 + Status-Tabelle.
   Backlog: `project_finalization/00_backlog.md` (B4-Zeile).
5. **Relevante Memories** (im Recall sichtbar): `project_two_joint_limit_sources`,
   `project_gait_offset_convention`, `project_nontripod_gait_wobble` (A5/IMU-Balance =
   verwandtes Thema), `feedback_validate_hardware_hypothesis_via_code`, `feedback_user_does_commits`,
   `feedback_german_language`.
6. **Code, der angefasst/wiederverwendet wird:**
   - `src/hexapod_gait/hexapod_gait/gait_engine.py` — State-Machine (Vorbild: die Sitdown-States
     `SITDOWN_LOWER`/`SITDOWN_FLATTEN`/`SAT` + `start_sitdown`/`_compute_*`; `start_reposition`
     richtungs-agnostisch; `_lerp`; `compute_joint_angles`-Dispatch; `set_command`-cmd_vel-Ignore-Tuple).
   - `src/hexapod_gait/hexapod_gait/joint_load.py` — **CoG + Stütz-Polygon-Marge** (A1). DAS Werkzeug
     für die Stabilitätsgarantie. API prüfen (Funktionen für CoG/Marge aus Joint-Winkeln).
   - `src/hexapod_kinematics/` — `leg_ik(x,y,z,leg,limits)`, `leg_fk`, `HEXAPOD` (Bein-Layout,
     `mount_xyz`/`mount_yaw`), `JointLimits`, `config.py` (Geometrie/Limits).
   - `src/hexapod_gait/hexapod_gait/gait_node.py` — Param-Tabelle `_GAIT_PARAMS`, `_apply_param`,
     Service-Muster (B1 `/hexapod_sit_down` etc., C2 `/hexapod_cycle_gait`), Tick-Loop.
   - `src/hexapod_teleop/hexapod_teleop/joy_to_twist.py` — der **Cross-Long-Press-Hook**
     (`_show_pose_hook`, aktuell nur Log) ist die vorgesehene Einsprungstelle; `ps4_usb.yaml`/`ps4_bt.yaml`.
   - `tools/walking_envelope_check.py` / `standup_envelope_check.py` — Envelope-Validierung (Vorbild).

## 1. Ziel (User 2026-06-04)
Der Hexapod stützt sich **sicher auf den 4 hinteren Beinen** (mid+rear: leg_2,3,4,5) ab, **ohne
umzufallen**, und hebt die **2 Vorderbeine** (leg_1 = vorne-rechts, leg_6 = vorne-links) in die Luft.
Diese kann man dann **per Joystick bewegen** (hoch/runter im **maximalen Servo-Range**, möglichst
auch **seitwärts**; idealerweise links+rechts gleichzeitig). Man **geht in den Modus rein und wieder
raus**; währenddessen **steht** der Roboter (läuft nicht, cmd_vel-Fahren ist aus). Drei Phasen:
**Hinstellen** (sichere Show-Stütz-Pose einnehmen) → **Show** (Vorderbeine per Joystick) → **Beenden**
(zurück zur normalen Stand-Pose).

Bein-Layout: leg_1=vorne-R, leg_2=mitte-R, leg_3=hinten-R, leg_4=hinten-L, leg_5=mitte-L, leg_6=vorne-L.

## 2. Architektur-Entscheidung (Vorschlag — im Plan-Review bestätigen)
- **Engine-States** (analog zu den B1-Sitdown-States, KEIN separater Node):
  - `STATE_SHOW_ENTER` — „Hinstellen": Körper/CoG **nach hinten verlagern** (alle 6 Füße noch unten,
    body translatiert rückwärts → CoG wandert in das Polygon der hinteren 4), **dann** die 2
    Vorderbeine in eine **neutrale Hoch-Pose** heben. Während der ganzen Phase per `joint_load`
    sicherstellen: CoG-Marge im 4-Bein-Polygon (2,3,4,5) **> Sicherheits-Schwelle**.
  - `STATE_SHOW_ACTIVE` — Vorderbeine (1,6) folgen dem Joystick (IK pro Tick, **geclampt auf
    URDF-Limits**). Stütz-Beine (2,3,4,5) statisch in der verlagerten Pose. cmd_vel-Fahren wird
    ignoriert (im `set_command`-Ignore-Tuple).
  - `STATE_SHOW_EXIT` — Vorderbeine zurück runter auf die Stand-Pose, Körper wieder vor →
    `STATE_STANDING`. (Umkehrung von ENTER.)
- **Teleop = reines UI (Design-Prinzip aus C, `C_teleop.md` §0):** Der Cross-Long-Press
  (`_show_pose_hook`) ruft einen **Intent-Service** `/hexapod_show_toggle` (Trigger) → gait_node
  geht SHOW_ENTER↔SHOW_EXIT je nach State. Die Joystick-Bewegung der Vorderbeine kommt über einen
  **eigenen Kanal** an den gait_node (Vorschlag: neues Topic `/cmd_show` mit den 2 Stick-Achsen
  bzw. wiederverwendet `/cmd_vel` nur im SHOW_ACTIVE-State umgedeutet — siehe Offene Frage Q3).
- **Wertneutral:** alle Posen/Verlagerungs-Distanzen/Limits aus Params/Config, nicht hartkodiert.

## 3. Logik-Skizze / Pseudocode
```
# Trigger (Teleop Cross-lang → /hexapod_show_toggle):
on_show_toggle():
    if STATE_STANDING:  start_show_enter(t)     # rein
    elif STATE_SHOW_*:  start_show_exit(t)      # raus
    else: reject (nur aus STANDING rein)

STATE_SHOW_ENTER (Dauer show_enter_duration, smooth-step):
    Phase a: body_shift x: 0 → -show_body_shift_back  (alle Füße bleiben am Boden;
             Foot-Targets in Body-Frame um +shift nach vorne → Körper effektiv zurück)
    Phase b: Vorderbeine 1,6 von Stand-Pose → neutrale Hoch-Pose (radial etwas rein, z hoch)
    JEDER Tick: joint_load-CoG-Marge im Polygon(2,3,4,5) >= show_safety_margin  → sonst Abbruch/Stop
    progress>=1 → STATE_SHOW_ACTIVE

STATE_SHOW_ACTIVE:
    Stütz 2,3,4,5: statisch (verlagerte Pose)
    Vorderbeine UNABHÄNGIG:
      leg_6 (links)  Foot = neutral_hoch + (0, +lat_scale*L_stick_x, up_scale*L_stick_y)
      leg_1 (rechts) Foot = neutral_hoch + (0, +lat_scale*R_stick_x, up_scale*R_stick_y)
      → leg_ik(...,limits) (clamp auf kalibrierte URDF-Limits). x (radial) bleibt neutral.
    Dead-Man-Gate: nur wenn R1 gehalten werden die Stick-Offsets angewandt; sonst (oder
      Stick zentriert) Offset=0 → Vorderbeine zurück in neutral_hoch.
    cmd_vel-Fahren ignoriert (SHOW-States im set_command-Ignore-Tuple).

STATE_SHOW_EXIT (Dauer show_exit_duration):
    Reihenfolge wichtig: ZUERST Vorderbeine 1,6 runter auf Stand-Pose (→ wieder 6-Bein-Stütze),
    DANN body_shift zurück auf 0. (Nicht gleichzeitig: erst Stütze zurückgewinnen, dann Körper vor.)
    progress>=1 → STATE_STANDING

# Hinweis Rückkehr-zu-Neutral (SHOW_ACTIVE): Stick zentriert / R1 los → Offset 0. NICHT hart
# springen, sondern rate-limitiert/gelerpt gegen ruckartige Servo-Bewegung.
```
**Reuse:** `_lerp`, das State-/Tick-Muster der Sitdown-States, `leg_ik`(+limits), `joint_load` für
CoG/Marge, der C1+-Cross-Hook + Teleop-Param-Muster, `_compute_standing_targets` als Basis.

## 4. ENTSCHIEDEN (User 2026-06-04) + ein offener Punkt
- ✅ **Q1 Vorderbein-Steuerung:** **unabhängig** — **linker Stick → linkes Vorderbein leg_6**,
  **rechter Stick → rechtes Vorderbein leg_1**. Stick-**Y = hoch/runter** (Foot-z), Stick-**X =
  seitwärts** (Foot-y/lateral, coxa-Schwenk). Pro Bein 2 DOF; IK löst alle 3 Joints.
- ✅ **Q2 Trigger + Dead-Man:** **Cross lang halten = rein** (aus STANDING), **nochmal Cross lang =
  raus** (zurück STANDING). **R1 (Dead-Man) MUSS gehalten werden, um die Vorderbeine zu bewegen.**
  Stick zentriert ODER R1 losgelassen → Vorderbeine in die **Ausgangs-Hoch-Pose** (kein Offset).
- ✅ **Q4/Q5 Range:** Foot-Target = neutrale-Hoch-Pose **+ Stick-Offset (x=seitwärts, z=hoch/runter)**,
  hart **geclampt auf die kalibrierten URDF-Limits** (nichts über den kalibrierten Servo-Range
  hinaus — `leg_ik(...,limits)` wirft bei Verletzung; vorher clampen). Seitwärts ist drin (coxa).
  ⚠️ Selbst-Kollision wird NICHT geprüft (A4 pausiert) → in Sim visuell beobachten, ggf. Skalen
  konservativer. Zentrierter Stick = Neutral (Rückkehr-Verhalten).
- ✅ **Q3 (bestätigt) Stütz-Basis:** Stütz = leg_2,3,4,5 (mitte+hinten), frei = leg_1,6 (vorne).
- ⏳ **Offen (nächster Chat):** Joystick→Bein-Kanal: eigenes Topic `/cmd_show`
  (z.B. `geometry_msgs/Twist` o. `Float64MultiArray` mit 4 Achsen = 2 Sticks × xy) **vs** `/cmd_vel`+
  zweiter Stick. Vorschlag: **eigenes Topic `/cmd_show`** (Teleop publisht beide Stick-Paare; gait_node
  liest es nur im SHOW_ACTIVE). Sauber zum „Teleop=UI"-Prinzip. Plus Tuning-Skalen (up/lat) als Params.

## 4a. B4.0-Ergebnis (KRITISCHER VORAB-CHECK, 2026-06-04) ✅ BESTANDEN
Tool: `tools/show_pose_cog_check.py` (offline, reuse `leg_ik`+`joint_load`, **URDF-Limits via xacro**
= HW-Quelle). Stand-Pose radial 0.215 / body_height −0.120. Stütze = leg_2,3,4,5, Vorderbeine 1,6 frei.

**URDF-Limits (alle 6 Beine identisch, Stage F):** coxa **±0.415**, femur **±1.57**, tibia −1.00…+2.50.

**Befunde:**
1. **Vorderbein-Hoch-Pose:** Der **Femur-Limit ±1.57 (±90°)** begrenzt die Hub-Höhe. Ein Fuß über
   Coxa-Höhe verlangt Femur < −90° → nicht erreichbar. „Angehoben" = Fuß über dem Stand-Boden
   (z > −0.120). Höher heben erfordert **radial weiter raus** (z.B. radial 0.24 → Fuß bis ~120–240 mm
   über Boden; radial 0.20 → max ~60 mm). Tradeoff: höher/weiter-vorne = CoG weiter vorne.
2. **CoG-Marge-Gate:** Mit der **Worst-Case-Vorderbein-Pose** (radial 0.24, z 0.00, Fuß 120 mm hoch,
   weit vorne) liefert der Body-Rückversatz `s`:
   - s = 0.000 → Marge 2.3 mm (grenzwertig, CoG knapp im Polygon)
   - s = 0.050 → **41.9 mm** · s = 0.060 → **49.8 mm** · s = 0.070 → **57.6 mm** · s = 0.090 → **73.3 mm**
   - Ziel ≥40 mm erreicht für **s ∈ [0.050, 0.090] m**.
3. **Stützbein-Schranke:** Ab **s ≈ 0.092 m** verletzen ALLE 4 Stützbeine den **Coxa-Limit ±0.415**
   (der Rückversatz schwenkt die Stützfüße seitlich im Bein-Frame → coxa wächst). → harte Obergrenze.
4. **Massen-Robustheit:** Mit realistisch höherer zentraler Masse (3.5 / 4.5 kg statt 2.63 kg URDF-Summe,
   Akku mittig) wird das Ergebnis **robuster** (Marge minimal höher, Ziel-Fenster weitet sich auf [0.045, 0.090]).

**Empfohlener Betriebspunkt:** `show_body_shift_back ≈ 0.060–0.070 m` (Marge ~50–58 mm, komfortabel
weg von beiden Rändern: unterer Marge-Rand UND Coxa-Limit-Rand bei 0.090). **Param**, nicht hartkodiert.
**Reproduktion:** `python3 tools/show_pose_cog_check.py --show-radial 0.24 --show-z 0.00`.

## 5. Progress-Checkliste (Done-Vertrag)
```
- [x] B4.0  ⚠️ KRITISCHER VORAB-CHECK (vor jeglichem Code, Memory feedback_validate_hardware_hypothesis_via_code):
            ✅ BESTANDEN 2026-06-04 (Tool `tools/show_pose_cog_check.py`, echte leg_ik + joint_load
            + URDF-Limits). Ergebnis siehe §4a unten. Sichere Show-Stütz-Pose existiert: Rückversatz
            ~0.06–0.07 m → CoG-Marge ~50–63 mm, alle 4 Stützbeine in-URDF-Limit; robust auch bei
            höherer zentraler Akku-Masse. Bindende Obergrenze: Coxa-Limit ±0.415 der Stützbeine ab
            Shift ≈0.090 m (seitlicher Schwenk durch Rückversatz).
- [x] B4.1  Engine: STATE_SHOW_ENTER (body-shift zurück + Vorderbeine hoch), CoG-Marge-Gate (joint_load)
            ✅ 2026-06-04: STATE_SHOW_ENTER (2 Phasen) + STATE_SHOW_ACTIVE (statisches Halten) in
            gait_engine.py; CoG-Gate pro Tick in Phase b (Hold bei Marge<Schwelle); Kanal-Wahl
            /cmd_show (Q3, User). 12 Unit-Tests (test_show_pose.py) + Regression 156/0 + Lint grün.
            Self-Review §9. cmd_vel in beiden SHOW-States ignoriert.
- [x] B4.2  Engine: STATE_SHOW_ACTIVE (Vorderbeine folgen Joystick-Delta, leg_ik + URDF-Clamp; cmd_vel ignoriert)
            ✅ 2026-06-04: set_show_offsets({leg: (lat,vert)} in Metern, Q-API-Wahl); rate-limitierte
            Nachführung (show_return_rate, Q-Wahl) + harte Clamp via Hold-bei-IKError; Offset·λ(σ)
            → verblasst beim EXIT (kein Sprung). Offline-Nachweis: über ALLE 3025 in-limit-Offsets
            min CoG-Marge 44 mm @shift 0.065 (URDF-Masse) → kein ACTIVE-CoG-Gate nötig, Clamp reicht.
            6 neue Tests (move/clamp/rate-limit/return/exit-fade/reset). 170/0 grün.
- [x] B4.3  Engine: STATE_SHOW_EXIT → STANDING (Umkehrung); cmd_vel in allen SHOW-States ignoriert
            ✅ 2026-06-04: STATE_SHOW_EXIT über gemeinsamen Show-Skalar σ∈[0,1] (σ=0=Walk-Stand,
            σ=1=volle Show); EXIT fährt σ→0 (erst Vorderbeine runter, dann Körper vor), nahtlos in
            STANDING (σ=0==stand_pose) → Laufen wieder möglich. Funktioniert auch aus mid-ENTER +
            frozen-ENTER (σ0=aktuelles σ). 8 neue Tests (Round-Trip, EXIT-Pfad, walk-after). 164/0 grün.
- [x] B4.4  Node: /hexapod_show_toggle (Trigger, STANDING↔SHOW); Joystick→Bein-Kanal (Q3); Params (Dauer/Shift/Marge/Skalen)
            ✅ 2026-06-04: `/hexapod_show_toggle` (STANDING→ENTER, SHOW_*→EXIT, sonst reject);
            `/cmd_show` (Float64MultiArray[4]=[l6_lat,l6_vert,l1_lat,l1_vert], Q-Wahl); 10 Params
            (Dauer/Shift/Fraction/Marge/Front-Pose/return_rate/lat+vert-Scale); Tick skaliert Stick→m
            + Staleness-Schutz (Disconnect→Neutral). 11 Node-Tests. 181/0 grün.
- [x] B4.5  Teleop: Cross-lang → show_toggle (Hook ersetzen); Stick(s) → /cmd_show (Q1-Mapping)
            ✅ 2026-06-04: `_show_pose_hook` → `/hexapod_show_toggle`; `_show_from_joy` publisht
            `/cmd_show` (L-Stick→leg_6, R-Stick→leg_1; X=lat, Y=vert; R1-Dead-Man). Zustandsloser
            Teleop (beide Topics immer, Node wählt je State). axis_ry/sign_show_* in ps4_usb+bt.yaml.
            6 Teleop-Tests. 28/0 grün.
- [x] B4.6  Unit-Tests: ENTER/ACTIVE/EXIT in-limit; CoG-Marge>Schwelle über ENTER; Vorderbein-Clamp; cmd_vel ignoriert; Toggle-Guards
            ✅ 2026-06-04: Engine 26 (test_show_pose.py) + Node 11 (test_show_node.py) + Teleop 6
            (test_joy_to_twist.py). Alle genannten Fälle abgedeckt.
- [x] B4.7  Envelope/Regression + Lint grün; bestehende Tests unberührt
            ✅ 2026-06-04: gait 181/0/1-skip, teleop 28/0/1-skip, flake8/pep257 grün. Bestand unberührt.
- [x] B4.8  SIM: rein → Vorderbeine per Stick bewegen → raus; kein Kippen/Freeze; Selbst-Kollision beobachten
            ✅ 2026-06-04 (User): ENTER (Körper zurück + Vorderbeine hoch) ohne Kippen/Freeze; PS4-USB-
            Stick bewegt die Vorderbeine unabhängig; EXIT → STANDING; Laufen danach ok. Kriterien 1–4 erfüllt.
- [ ] B4.9  DANACH HW aufgebockt → Boden: sicher (CoG!), kein Umfallen
- [ ] B4.10 Self-Review + Design-Log + Test-Markdown (`B4_show_pose_test_commands.md`)
```

## 6. Tests-Liste (+ Begründung, + was NICHT)
- Engine-Unit (Stil wie `test_sitdown.py`, pure-python): ENTER/ACTIVE/EXIT-Pfade in-limit (URDF-Limits);
  **CoG-Marge ≥ show_safety_margin** an jeder ENTER-Phase (joint_load, wie B3-Stabilitäts-Analyse);
  Vorderbein-Joystick-Delta wird auf URDF-Limits geclampt; cmd_vel kippt SHOW-State nicht auf WALKING;
  Toggle nur aus STANDING rein / aus SHOW raus; EXIT endet in STANDING-Pose.
- Node/Teleop-Unit: Service existiert + Guards; Cross-lang ruft Toggle; Stick→/cmd_show-Mapping.
- **NICHT getestet (scope-out):** Selbst-Kollision (A4 pausiert → visuell in Sim); dynamisches Kippen
  unter Last (quasi-statisch via CoG-Marge); HW-Servo-Stall am Extrem (HW-Beobachtung).

## 7. Validierungs-Gates (ai_navigation §2) + Safety
Build → Unit/Lint → CoG-Marge-Check (joint_load offline, wie B3) + Envelope unberührt → **SIM (RViz+
Gazebo)** → **HW aufgebockt → Boden** (CLAUDE.md §9: aufgebockt zuerst, Kill-Switch; CoG-kritisch, da
nur 4 Stützbeine!). **Sim VOR HW.** Erst Sim komplett sauber (User-Vorgabe 2026-06-04).

## 8. Handover-Notizen (falls Kontext nicht reicht)
- **Reuse-First:** Die Sitdown-States (B1) sind das exakte Vorbild für die SHOW-States (gleiches
  start_*/_compute_*/Dispatch/Ignore-Tuple-Muster). `joint_load` (A1) liefert CoG+Marge — die
  Stabilitätsgarantie ist Pflicht (nur 4 Stützbeine). `leg_ik(...,limits)` clampt die Vorderbeine.
- **Gotchas:** zwei Limit-Quellen (URDF vs config.py) synchron halten (`project_two_joint_limit_sources`);
  Sim-IK ist lenient → mit URDF-Limits validieren (`feedback_validate_hardware_hypothesis_via_code`);
  Hypothese (CoG-Marge reicht) ERST per Code/joint_load falsifizieren, bevor Plan drauf gebaut wird.
- **CoG-Risiko:** Vorderbeine heben ⇒ CoG nahe Vorder-Kante des 4-Bein-Polygons ⇒ Body MUSS zurück.
  Vorab mit joint_load die nötige `show_body_shift_back` so wählen, dass Marge komfortabel > 0
  (Ziel z.B. ≥ 30–50 mm, vgl. B3: Tripod 108 mm, Ripple-grenzwertig 7 mm).
- **Commits:** macht der User. **Antworten Deutsch.** Pro Sub-Schritt Plan→Freigabe→Code→Tests→Self-Review.
- **Show-Pose-Hook** ist schon in `joy_to_twist.py::_show_pose_hook` (C1+) — nur ersetzen.

## 9. Design-Log + Self-Review B4.1 (2026-06-04)
**Entschieden:**
- **Q3 Kanal = eigenes Topic `/cmd_show`** (User). Verworfen: `/cmd_vel` umdeuten (überlädt Semantik,
  bräuchte trotzdem 2.-Stick-Kanal). `/cmd_show` wird in B4.5 vom Teleop publisht, in B4.2 nur in
  SHOW_ACTIVE gelesen.
- **Zwei-Phasen-ENTER** (erst Körper zurück mit allen 6 Füßen am Boden, dann Vorderbeine heben):
  CoG wandert vor dem Anheben sicher ins hintere Polygon. Verworfen: gleichzeitig (CoG nahe Kante
  während Übergang). Param `show_shift_fraction` = Phase-a-Anteil.
- **CoG-Gate als per-Tick-Hold** (Freeze letzte sichere Pose) statt IKError/Freeze: das Anheben ist
  per B4.0 design-sicher; das Gate ist die Laufzeit-Absicherung. Verworfen: IKError werfen (würde
  unnötig safety_freeze triggern bei einem an sich harmlosen Marge-Dip).
- **B4.3 — gemeinsamer Show-Skalar σ∈[0,1]** (ENTER 0→1, ACTIVE σ=1, EXIT aktuell→0) statt separater
  EXIT-Geometrie. σ=0 ist per Konstruktion exakt die Walk-Stand-Pose → nahtloser STANDING-Übergang,
  danach Laufen wieder möglich (User-Vorgabe Round-Trip erfüllt). EXIT funktioniert aus jedem
  SHOW-State (σ0 = aktuelles σ, deckt mid-ENTER + frozen ab). EXIT hat KEIN CoG-Gate (σ nur fallend
  → Vorderbeine nur runter → Stütze monoton besser; ein Gate-Abbruch würde nur stranden). σ linear,
  Smoothstep intern pro Sub-Phase (Geschwindigkeit-Null an Start/Phasengrenze/Ende).
- **B4.2 Q-Entscheidungen (User 2026-06-04):** (a) Engine-API = **Offsets in Metern**
  (`set_show_offsets`), Node skaliert Stick→m + Dead-Man → Engine wertneutral. (b) Rückkehr zu
  Neutral = **rate-limitiert** (`show_return_rate` m/s) gegen ruckartige Servo-Bewegung.
  Clamp auf URDF-Limits = **Hold-bei-IKError** (letzter gültiger Offset) statt cartesian-Vorab-Clamp
  (einfach + immer in-limit). Offset wird mit Lift-Faktor λ(σ) skaliert → nur in der Luft wirksam,
  **verblasst beim Aufsetzen** (kein EXIT-Sprung).
- **B4.2 Sicherheit ohne ACTIVE-CoG-Gate (offline falsifiziert):** Sweep über ALLE 3025 in-limit
  Vorderbein-Offset-Kombis (URDF-Masse, konservativ) → min CoG-Marge **44 mm @ shift 0.065** (32 mm
  @0.05, 56 mm @0.08). Der URDF-Joint-Limit-Clamp **bindet die CoG implizit** → kein Laufzeit-CoG-
  Gate in SHOW_ACTIVE nötig. Constraint: `show_body_shift_back` ≥ 0.05 halten (Worst-Case-Offset-
  Marge ≥ 30 mm). Worst-Case = beide Vorderbeine runter (vert −0.10) + seitlich ausgeschwenkt.
- **Engine wertneutral:** alle Show-Zahlen kommen über `start_show_enter`-Args (Node/Config, B4.4),
  inkl. `mass_model`. Default = URDF-Masse = konservativster (niedrigste-Marge) Fall.

**User-Vorgabe (2026-06-04):** Round-Trip Show→STANDING muss sauber sein (danach wieder laufen).
→ ENTER cached keine Live-Pose (Stand-Pose deterministisch aus radial/body_height) → EXIT (B4.3) =
triviale Umkehrung zurück auf Walk-Pose radial 0.215. **B4.3 zwingend VOR jeglicher Sim/HW.**

**Self-Review (🟡 = nachfolgende Sub-Stage / HW-Beobachtung, kein B4.1-Blocker):**
| Punkt | Status |
|---|---|
| CoG-Gate nur per-Tick (Skip bei zu kurzer duration) — Design-Garantie-Test deckt es ab, @50 Hz unkritisch | 🟡 Note B4.4 |
| Kein EXIT aus SHOW_ACTIVE/SHOW_ENTER in B4.1 (Round-Trip!) | 🟡 B4.3, vor Sim |
| Frozen-State terminal bis EXIT existiert → Toggle muss auch aus (frozen) SHOW_ENTER führen | 🟡 B4.3/B4.4 |
| Front-Neutral-Config out-of-reach → IKError → safety_freeze (bestehend); optional fail-fast Pre-Check | 🟢 später B4.4 |
| Stützfüße bleiben exakt am Boden (reine base-X-Translation, per Test); Rutsch-Risiko HW | 🟡 HW B4.9 |
| Coxa-Headroom @shift 0.065: ~0.28 « 0.415 (Limit @0.092) | OK |
| Comms-Loss-Failsafe greift in SHOW nicht | 🟡 Note B4.4/E1 |

- **B4.4 Kanal `/cmd_show` = Float64MultiArray[4]** `[leg6_lat, leg6_vert, leg1_lat, leg1_vert]`
  (User-Wahl). Verworfen: TwistStamped×2 (2 Topics) / eigene .msg (Build-Dep). Node skaliert Stick→m
  (`show_lat_scale`/`show_vert_scale`), Staleness-Schutz (>cmd_vel_timeout → 0, Disconnect→Neutral).
  Toggle-Service `/hexapod_show_toggle` löst nach State auf (STANDING→ENTER, SHOW_*→EXIT). 10 Params,
  mass_model=URDF (konservativ).
- **B4.5 zustandsloser Teleop:** publisht IMMER beide `/cmd_vel` + `/cmd_show` (beide R1-Dead-Man-gated);
  der gait_node wählt je State (cmd_vel außerhalb SHOW, cmd_show nur in SHOW_ACTIVE). Kein State im
  Teleop nötig (UI-Prinzip). L-Stick→leg_6, R-Stick→leg_1; X=lat, Y=vert. Cross-lang → Toggle-Intent.

**Status:** kompletter Code-Pfad fertig — Engine + Node + Teleop. gait 181/0, teleop 28/0, Lint grün.
**Test-Anleitung (SIM/HW):** [`B4_show_pose_test_commands.md`](B4_show_pose_test_commands.md).
Offen: **B4.8 SIM** (User-Test) → **B4.9 HW** aufgebockt → Boden.
