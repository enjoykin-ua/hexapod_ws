# Phase 13 Stage 1 — Lauf-Optimierung (kalibrierte Reichweite ausnutzen)

> **STATUS: ⚪ PLAN / Handover — erstellt 2026-06-01 (Kontext-Übergabe an frischen Chat).**
> Phase 13 Stage 0 ist **komplett fertig** (Boot → Aufstehen → stabil am Boden,
> Tibia-Re-Cal 0.6.6 validiert). Diese Stage geht das **Laufen** an: der Roboter
> bewegt sich aktuell viel weniger als er mechanisch kann, weil **konservative
> Software-Limits** (v.a. Tibia-Beuge) die kalibrierte Reichweite künstlich
> beschneiden. Ziel: das echte Bewegungs-Potenzial nutzen → sichtbar besseres Laufen.

---

## 0. ⭐ FÜR DEN NÄCHSTEN CHAT: Was zuerst lesen

### 0.1 Pflicht-Lektüre (Arbeitsweise — immer zuerst)
1. **`CLAUDE.md`** (Repo-Wurzel) — Arbeitsanweisung. Besonders **§4** (Plan →
   Freigabe → Implementierung → Tests → **kritischer Self-Review**), **§5**
   (Shell-Verbote), **§9** (HW-Safety, aufgebockt zuerst).
2. **`PHASE.md`** — aktuelle Phase.
3. **`docs/00_conventions.md`** — Joint-Naming, Frames, **§11.4 Joint-Limits**.
4. **DIESE Datei** komplett.

### 0.2 Kontext dieser Stage (das Wichtigste — unbedingt lesen)
5. **`docs_raspi/phase_13_stage_0_progress.md`** — Sub-Stages **0.6.5** (Tibia-
   Winkel-Messung) + **0.6.6** (Tibia-Re-Cal) + Final-Reviews. **Hier steht der
   ganze Tibia-Kontext + warum das Limit aktuell −1.00/+1.30 ist.**
6. **`docs_raspi/phase_13_stage_0_6_5_tibia_measure_test_commands.md`** §2 — die
   **gemessenen Tibia-Werte** (A/B/C/D pro Bein). **Schlüssel: der Beuge-Anschlag
   lief in die Servo-Range-Grenze (500/2500 µs) bei ~150–160° Beugung — das ist
   die ECHTE kalibrierte Tibia-Range.**
7. **`docs_raspi/phase_13_stage_0_6_6_tibia_recal_plan.md`** — die aktuelle Cal
   (pulse_zero/min/max, Slope k=425, Limits −1.00/+1.30) + warum +1.30 *konservativ*
   gewählt wurde (body-kollisionssicher für die Tief-Hocke, NICHT mechanisches Max).

### 0.3 Code/Tools, die gelesen/geändert/gebaut werden
- **`tools/walking_envelope_check.py`** (+ `.README.md`) — prüft die Lauf-Fußbahn
  gegen Limits. `check`/`sweep`/`recommend`. **Nutzt live die URDF-Limits (xacro)
  + Geometrie aus config.py; NICHT die Puls-Cal (rad-Raum).**
- **`tools/standup_envelope_check.py`** — Aufsteh-Hülle (für den Standup-Pfad).
- **`src/hexapod_gait/hexapod_gait/gait_node.py`** — Walking-Params (`body_height`,
  `radial_distance`, `step_length_max`, `step_height`, `cycle_time`, `body_height_min/max`).
- **`src/hexapod_description/urdf/hexapod.urdf.xacro`** + `hexapod.ros2_control.xacro`
  + `hexapod_physical_properties.xacro` — die per-Bein-Joint-Limits (Tibia −1.00/+1.30).
- **`src/hexapod_kinematics/hexapod_kinematics/config.py`** — `_TIBIA_LIMITS` (muss
  zur URDF passen, Cross-Check `test_config.py`).
- **`src/hexapod_hardware/config/servo_mapping.yaml`** — die Puls-Cal (pulse_min/zero/max).
  **Bei Limit-Anhebung: Tibia-`pulse_min` (rechts) / `pulse_max` (links) runter/hoch
  ziehen, damit der neue rad-Bereich puls-seitig erreichbar ist (Slope k=425).**
- **NEU zu bauen:** ein **Reachability-Viz-Node** (RViz-Marker der erreichbaren Fuß-Hülle).

### 0.4 Relevante Memory-Einträge
- `project_two_joint_limit_sources` — ⚠️ ZWEI Limit-Quellen (URDF vs config.py),
  Tibia jetzt −1.00/+1.30, **Coxa-config.py noch stale ±1.57 vs URDF ±0.415**.
- `project_phase13_femur_zero_asymmetry`, `feedback_validate_hardware_hypothesis_via_code`
  (erst per Code/Math falsifizieren), `feedback_urdf_refactor_full_smoke`,
  `feedback_phase_progress_tracking`, `feedback_interactive_stage_test_doc`,
  `feedback_test_commands_in_doc_not_chat`, `feedback_no_trim_verification_output`,
  `feedback_user_does_commits`, `feedback_german_language`,
  `project_phase11_convenience_aliases` (Preset-Speichern).

---

## 1. WARUM machen wir das? (Motivation)

Der Hexapod **steht und richtet sich auf** (Stage 0 fertig), aber das **Laufen ist
mickrig**: an der HW + in RViz bewegen sich die Coxas nur ein paar Grad, der Fuß
hebt nur ~2–3 cm, die Schrittweite ist ~3 cm — und der Roboter kommt kaum vom Fleck
(auf rutschigem Boden „wie am Eis"). **Optisch ist klar, dass die Servos noch
extrem viel Spielraum haben.** Die Untersuchung (2026-06-01) hat ergeben: das ist
**kein** Tool-Bug und **nicht** die Geometrie, sondern **künstlich konservative
Software-Limits** (v.a. die Tibia-Beuge), die die *kalibrierte* mechanische Range
nicht ausnutzen. Diese Stage holt das Potenzial raus.

---

## 2. Sichtweisen (Stand der Diskussion 2026-06-01)

### 2.1 Claude-Analyse (meine Sicht)
- **Das Tool (`walking_envelope_check`) rechnet korrekt** — verifiziert: es lädt die
  Limits **live aus der xacro** (Tibia −1.0/+1.3 = 0.6.6) und die Geometrie aus
  config.py (Femur 79.9 / Tibia 200 mm, vom User als korrekt bestätigt); die
  Puls-Cal nutzt es nicht (rad-Raum, richtig so).
- **Ehrlichkeit / meine Fehler:** Ich hatte beim Stride **zweimal die falsche Achse**
  gerechnet (radiales Rein/Raus statt Coxa-Schwenk; und das Fuß-Anheben/den Schritt
  selbst vergessen, der die Tibia weiter faltet). Der User hat das korrekt
  hinterfragt. Lehre: per Tool/Math gegenrechnen, nicht aus dem Kopf.
- **Der echte Engpass = das Tibia-Beuge-Limit +1.30 (74°).** Mechanisch/kalibriert
  geht die Tibia **~150–160° Beugung** (0.6.5: Beuge-Anschlag = Servo-Range-Grenze
  500/2500 µs, frei erreicht). +1.30 wurde nur **konservativ** als „body-sicher"
  für die Tief-Hocke (Standup) gewählt.
- **Die aktuelle Stand-Pose (radial 0.295) ist die schlechteste fürs Laufen** — das
  Bein ist da zu **94% gestreckt** → kaum Vorwärts-Reichweite. Füße **näher** (kleineres
  radial) → mehr Stride, ABER das überfaltet die Tibia gegen das +1.30-Limit. Also:
  **Limit anheben → Füße näher → größerer Schritt.**
- Coxa ±0.415 (Stage-F-symmetrisiert auf Min) = auch etwas konservativ; Femur ±90° =
  am echten Anschlag. Geometrie (Femur/Tibia-Längen) ist korrekt.
- „Auf der Stelle/kratzt" = Mix aus rutschigem Boden + kleinen Schritten.

### 2.2 User-Sicht
- **Optisch haben alle Servos extrem viel Platz** in jede Richtung — an der HW UND
  in RViz. Coxa bewegt nur wenige Grad zwischen min/max; step_height nur ~2–3 cm;
  Schrittweite (Punkt-zu-Punkt) nur ~3 cm. **Da geht eindeutig viel mehr.**
- **Die Tibia ist voll kalibriert** — sie kann sich tatsächlich so weit bewegen; die
  500/2500 µs sind die echte Servo-Grenze (dort käme der Anschlag). Also ist die
  Range real und frei nutzbar.
- **Der Fuß muss näher zum Körper** (die Tibia steht zu „gestreckt", quasi am Limit).
  Das müssen wir herausfinden — evtl. den Körper anheben.
- **Zwei-Phasen-Idee:** aufstehen → Zwischenstation (beim/nach dem Aufstehen) →
  per **Tripod-Wechsel** die Füße auf eine neue (nähere) Position umsetzen → von dort
  laufen. (Entkoppelt den Aufsteh-Touchdown von der Lauf-Pose.)
- Wunsch: in **RViz visualisieren, wohin der Fuß sich bewegen kann**, um es sich
  vorstellen zu können.

---

## 3. Wo wir hinwollen (Ziel)

Ein Hexapod, der **sichtbar richtig läuft**: größere Schritte, mehr Fuß-Hub, echter
Vortrieb am (griffigen) Boden — durch **Ausnutzen der vollen kalibrierten
Gelenk-Range** statt der konservativen Defaults. Konkret:
- **Tibia-Beuge-Limit** auf den real nutzbaren Wert angehoben (kollisionsgeprüft).
- **Feet-closer Lauf-Pose** (kleineres radial), die durch die freie Beuge möglich wird.
- **Größere step_length / step_height + schnellerer cycle** für sichtbaren Gang.
- **Zwei-Phasen-Standup→Reposition→Walk** als saubere Architektur (Aufstehen braucht
  Füße-draußen für den Touchdown; Laufen will Füße-näher).
- **Reachability-Viz-Tool**, um die Fuß-Hülle (jetzt vs mechanisch) zu sehen.

---

## 4. Logik-Skizze / Vorgehen (die Teile)

### 4.1 Reachability-Viz-Tool (RViz) — zuerst, fürs Verständnis
**Was:** ein kleiner ROS2-Node, der **pro Bein** die 3 Gelenke über ihre Limits
durchsweept, per FK (`hexapod_kinematics.leg_fk`) die Fuß-Position rechnet und alle
erreichbaren Punkte als **`visualization_msgs/MarkerArray`** (Punkt-Wolke) im
`base_link`-Frame publisht. RViz zeigt die **3D-Hülle**, in der der Fuß sein kann.
- **Zwei Wolken überlagert:** 🔵 mit aktuellem Limit (+1.30) vs 🔴 mit mechanischem
  (~150°) → der zusätzliche (rote) Raum nach innen/unten ist das verschenkte Potenzial.
- **Pro Bein** (Fuß-Hülle), umschaltbar — erst ein Bein (klar), optional alle 6 transparent.
- Pure FK, kein HW nötig (läuft gegen RViz mit dem URDF-Modell).
- *(Designfrage Detailgrad/Auflösung der Wolke, Frame, Param-Schnittstelle → §7.)*

### 4.2 Tibia-Beuge-Limit anheben (global, alle 6)
- **HW-Kollisions-Check zuerst** (aufgebockt): ein Bein in lauf-/repositions-ähnlicher
  Femur-Stellung **schrittweise tiefer beugen** und schauen, **ab wann Fuß/Tibia
  wirklich den Body trifft** (der Cal-Pose war Femur-horizontal — andere Femur-Winkel
  müssen geprüft werden). → echter sicherer Beuge-Wert.
- **Dann:** URDF-Tibia-`upper` hoch (z.B. +1.6…+2.0, je nach Check) in
  `hexapod.urdf.xacro` + `hexapod.ros2_control.xacro` + Property + config.py
  (`test_config.py`-Cross-Check) **+** servo_mapping `pulse_min` (rechts) /
  `pulse_max` (links) auf `pulse_zero ∓ 425·neues_limit` ziehen (Slope k=425 bleibt).
- Roundtrip-/IK-Tests grün; `pulse_min<zero<max`; 1500 µs in-range.

### 4.3 Feet-closer Lauf-Pose + Re-Tune
- Mit angehobenem Tibia-Limit: kleineres `radial_distance` (Füße näher) → mehr
  Vorwärts-Reichweite → größerer Stride. Mit `walking_envelope_check recommend`
  (jetzt mit dem höheren Limit) die **validierte** (radial, step_length, step_height)-
  Config finden. `cycle_time` für Tempo.
- ⚠️ **Trade-off Sidestep** (kleines radial stresst die Coxa) — entscheiden, ob
  omnidirektional grün oder vorwärts-optimiert (mit Warnung bei Hart-Sidestep).

### 4.4 Zwei-Phasen-Standup → Reposition → Walk
- Aufstehen (kartesisch, Füße-draußen radial ~0.29 für den Touchdown) → in STANDING
  die Füße per **Tripod 3+3** auf die nähere Lauf-Pose umsetzen (3 planted, 3 move,
  schürffrei) → dann Laufen. Evtl. Körper dabei anheben.
- *(Engine-Erweiterung: ein „reposition"-State / eine Stand-Pose-Transition.)*

### 4.5 (separat/optional) Höher stehen
- Höher = Beine gerader = **weniger** Stride → nur als eigene Steh-Pose, NICHT als
  Lauf-Pose. Nachrangig.

---

## 5. Tests-Liste (was „fertig" markiert — pro Teil)
- **4.1 Viz:** Node baut + läuft; RViz zeigt die Fuß-Wolke pro Bein; zwei-Wolken-
  Overlay (aktuell vs mechanisch) sichtbar; FK-Punkte stimmen mit dem Modell überein.
- **4.2 Limit:** HW-Kollisions-Check dokumentiert (sicherer Beuge-Wert pro Bein);
  URDF/config/cal konsistent; `colcon test` hardware+kinematics+gait grün;
  generierte URDF verifiziert; Live: Tibia fährt neuen Bereich ohne Freeze/Stall.
- **4.3 Pose/Tune:** `walking_envelope_check` GRÜN mit neuer Config; Sim-Lauf;
  HW-Lauf **auf griffigem Boden** = echter Vortrieb (messbarer Versatz), größere
  Schritte/Hub sichtbar.
- **4.4 Zwei-Phasen:** Reposition stabil (kein Kippen/Schürfen), Übergang in Walking.
- **Bewusst NICHT:** Höher-stehen (4.5, separat); Balance/IMU (späte Phase).

---

## 6. Progress-Checkliste (Done-Kriterien-Vertrag — über Tage tragfähig)
```
### Teil 1 — Reachability-Viz-Tool
- [ ] 1.1  Viz-Node: pro Bein Gelenk-Sweep → FK → MarkerArray (base_link)
- [ ] 1.2  Zwei-Wolken-Overlay (aktuelles Limit vs mechanisch ~150°), Farben
- [ ] 1.3  Pro-Bein-Umschaltung (Param), optional alle 6 transparent
- [ ] 1.4  Launch/Doku; RViz-Config; FK-Stichprobe vs Modell stimmt
- [ ] 1.5  User sieht die Hülle + den verschenkten roten Raum

### Teil 2 — Tibia-Beuge-Limit anheben (global)
- [ ] 2.1  HW-Kollisions-Check aufgebockt: sicherer Beuge-Wert pro Bein gemessen
- [ ] 2.2  Gemeinsamen Beuge-Limit-Wert festgelegt (+ Begründung)
- [ ] 2.3  URDF (urdf.xacro + ros2_control.xacro + property) Tibia-upper angehoben
- [ ] 2.4  config.py _TIBIA_LIMITS konsistent (test_config.py grün)
- [ ] 2.5  servo_mapping Tibia pulse_min/max auf neues Limit (k=425), min<zero<max
- [ ] 2.6  colcon build + test (hardware/kinematics/gait) grün; generierte URDF verifiziert
- [ ] 2.7  Live aufgebockt: Tibia fährt neuen Bereich, kein Freeze/Stall/Trip
- [ ] 2.8  standup_envelope_check noch GRÜN (Standup nicht kaputt gemacht)

### Teil 3 — Feet-closer Lauf-Pose + Re-Tune
- [ ] 3.1  walking_envelope_check recommend mit neuem Limit → validierte Config
- [ ] 3.2  radial/step_length/step_height/cycle_time gesetzt (+ Sidestep-Entscheidung)
- [ ] 3.3  Sim-Lauf ok; HW-Lauf auf griffigem Boden = echter Vortrieb
- [ ] 3.4  Werte als Preset gespeichert (project_phase11_convenience_aliases)

### Teil 4 — Zwei-Phasen Standup → Reposition → Walk
- [ ] 4.1  Konzept/Engine-Design Reposition (Tripod 3+3 Stand-Pose-Transition)
- [ ] 4.2  Implementierung + Tests
- [ ] 4.3  Sim → HW aufgebockt → Boden

- [ ] 5.x  Self-Review-Tabelle pro Teil + Design-Log-Eintrag
```

---

## 7. Offene Punkte für User-Review (vor Code-Beginn)
| # | Frage | Status |
|---|---|---|
| 7.1 | Reihenfolge: erst Viz-Tool (sehen), dann tunen? | ⏳ Vorschlag ja |
| 7.2 | Viz: erst **ein Bein** oder gleich alle 6? Auflösung der Wolke? | ⏳ Vorschlag: ein Bein, mittlere Auflösung |
| 7.3 | Tibia-Beuge-Limit: trotz „kalibriert" noch HW-Kollisions-Check in Lauf-Femur-Stellung? (Cal war Femur-horizontal) | ⏳ empfohlen ja (Sicherheit) |
| 7.4 | Neuer Beuge-Limit-Zielwert (z.B. +1.6 / +1.8 / +2.0)? | ⏳ aus HW-Check |
| 7.5 | Walking: omnidirektional-grün ODER vorwärts-optimiert (Sidestep eingeschränkt)? | ⏳ |
| 7.6 | Zwei-Phasen jetzt oder nach dem einfachen Limit+Pose-Tuning? | ⏳ |
| 7.7 | Stage-Nummer/Name ok (Phase 13 Stage 1)? PHASE.md aktualisieren | ⏳ |

---

## 8. Cross-References
- Tibia-Kontext: `phase_13_stage_0_progress.md` (0.6.5/0.6.6), `phase_13_stage_0_6_5_tibia_measure_test_commands.md`,
  `phase_13_stage_0_6_6_tibia_recal_plan.md`
- Tools: `tools/walking_envelope_check.py` (+README), `tools/standup_envelope_check.py`
- Code: `gait_node.py`, `hexapod.urdf.xacro` / `hexapod.ros2_control.xacro` /
  `hexapod_physical_properties.xacro`, `config.py`, `servo_mapping.yaml`, `leg_ik.py`/`leg_fk`
- Memory: `project_two_joint_limit_sources`, `project_phase11_convenience_aliases`
