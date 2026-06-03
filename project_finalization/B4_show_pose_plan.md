# B4 — Body-Pose / Show-Pose (Free-Leg) — detaillierter Sub-Stage-Plan (Handover)

> **Status:** ⚪ Plan zur Freigabe. Block B war pausiert für B4 — jetzt reaktiviert (User 2026-06-04).
> Diese Datei ist **self-contained für einen neuen Chat**: enthält Ziel, Lese-Liste, Architektur,
> Logik, Reuse, offene Fragen, Checkliste, Tests, Validierungs-Gates und Handover-Notizen.

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

## 5. Progress-Checkliste (Done-Vertrag)
```
- [ ] B4.0  ⚠️ KRITISCHER VORAB-CHECK (vor jeglichem Code, Memory feedback_validate_hardware_hypothesis_via_code):
            offline mit joint_load nachweisen, dass es überhaupt eine SICHERE statische Pose gibt —
            d.h. ein body_shift_back, bei dem (a) CoG-Marge im 4-Bein-Polygon(2,3,4,5) komfortabel
            >0 (Ziel ≥30–50 mm) UND (b) alle 4 Stützbeine dabei in-reach/in-URDF-Limit bleiben (der
            Shift zieht die Stützfüße im Body-Frame nach vorne → kann Reichweite sprengen). Wenn KEIN
            solcher Shift existiert → Konzept anpassen (kleinerer Lift / Stütze anders) BEVOR codiert wird.
- [ ] B4.1  Engine: STATE_SHOW_ENTER (body-shift zurück + Vorderbeine hoch), CoG-Marge-Gate (joint_load)
- [ ] B4.2  Engine: STATE_SHOW_ACTIVE (Vorderbeine folgen Joystick-Delta, leg_ik + URDF-Clamp; cmd_vel ignoriert)
- [ ] B4.3  Engine: STATE_SHOW_EXIT → STANDING (Umkehrung); cmd_vel in allen SHOW-States ignoriert
- [ ] B4.4  Node: /hexapod_show_toggle (Trigger, STANDING↔SHOW); Joystick→Bein-Kanal (Q3); Params (Dauer/Shift/Marge/Skalen)
- [ ] B4.5  Teleop: Cross-lang → show_toggle (Hook ersetzen); Stick(s) → /cmd_show (Q1-Mapping)
- [ ] B4.6  Unit-Tests: ENTER/ACTIVE/EXIT in-limit; CoG-Marge>Schwelle über ENTER; Vorderbein-Clamp; cmd_vel ignoriert; Toggle-Guards
- [ ] B4.7  Envelope/Regression + Lint grün; bestehende Tests unberührt
- [ ] B4.8  SIM: rein → Vorderbeine per Stick bewegen → raus; kein Kippen/Freeze; Selbst-Kollision beobachten
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
```
