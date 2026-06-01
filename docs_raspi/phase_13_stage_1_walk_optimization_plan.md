# Phase 13 Stage 1 — Lauf-Optimierung (kalibrierte Reichweite ausnutzen)

> **STATUS: 🟡 AKTIV — Teil 1 ✅ erledigt, Teil 2 in Diskussion (Stand 2026-06-01).**
> Phase 13 Stage 0 ist **komplett fertig** (Boot → Aufstehen → stabil am Boden,
> Tibia-Re-Cal 0.6.6 validiert). Diese Stage geht das **Laufen** an: der Roboter
> bewegt sich aktuell viel weniger als er mechanisch kann, weil **konservative
> Software-Limits** (v.a. Tibia-Beuge) die kalibrierte Reichweite künstlich
> beschneiden. Ziel: das echte Bewegungs-Potenzial nutzen → sichtbar besseres Laufen.
>
> **✅ ERLEDIGT — Teil 1 (Reachability-Viz):** RViz-Tool, das die erreichbare
> Fuß-Wolke pro Bein zeigt (🔵 aktuelles Limit vs 🔴 volle kalibrierte Tibia-Beuge).
> Node `hexapod_gait/reachability_viz.py` + `reachability_viz.launch.py` +
> `view_reach.rviz` + Benutzungs-Doku `phase_13_stage_1_reachability_viz_test_commands.md`.
> Gebaut + getestet (FK verifiziert), committed. **Live umschaltbar** (`leg:=leg_N`/`all`).
>
> **➡️ TEIL 2+ — entschieden: Weg B-Voll (Selbst-Kollisions-Check).** Zentraler Befund
> (User-Handtest): **das Tibia-Beuge-Limit ist FEMUR-GEKOPPELT** (Body-Kollision) → ein
> konstantes Limit ist falsch (§4.2.0). Lösung = geometrie-getriebener Kollisions-Check.
> **Eigener Plan (zu reviewen NACH der RViz-Stage):
> [`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md).**

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

#### 4.2.0 ⭐ ZENTRALER BEFUND (User-Handtest 2026-06-01): das Limit ist FEMUR-GEKOPPELT
Der User hat das Bein von Hand bewegt und festgestellt: **die sichere Tibia-Beuge
hängt vom Femur-Winkel ab** (Body-Kollision), es gibt **kein einzelnes konstantes
Tibia-Limit**:

| Femur-Stellung | max. Tibia-Beuge bis Kollision |
|---|---|
| horizontal | ~150° |
| nach UNTEN (bis 90° runter) | sinkt auf **~90°** (Fuß trifft früher) |
| nach OBEN | ~150° (volle Beuge); Strecken nur bis 0° (für Gehen egal) |

**Konsequenz:** Ein fester URDF-Tibia-Wert (wie +1.30) passt konzeptionell nicht —
die echte Grenze ist eine **2D-Funktion (Femur × Tibia)** bzw. ein **Selbst-
Kollisions-Modell** (Fuß darf nicht in den Body). Das ist die Antwort auf „wie soll
man das überhaupt kalibrieren?".

**Die gute Nachricht fürs Laufen:** Beim **Laufen + Aufstehen zeigt der Femur immer
nach OBEN** (~14–37° hoch; Stand-Pose Femur −0.24 = 14° hoch, power_on_mid 27° hoch).
Genau dort kann die Tibia **fast voll (~150°) beugen.** Die Kollisions-Einschränkung
(Femur-unten → ~90°) trifft nur Posen, die wir **gar nicht benutzen.** → Für die
feet-closer Lauf-Pose **dürfen wir das Tibia-Limit deutlich anheben**, *weil der
Femur beim Laufen oben ist.*

> ⚠️ **Offene Sub-Frage (§7.10):** Kollidiert „Femur-unten + Tibia-90°" mit dem
> **Body**, dem **Boden** oder dem eigenen **Femur**? (Boden = aufgebockt irrelevant.)

#### 4.2.1 ✅ ENTSCHEIDUNG (User 2026-06-01): Weg B-Voll
Statt eines starren konstanten Tibia-Limits → ein **geometrie-getriebener
Selbst-Kollisions-Check** (Fuß + Tibia-Segment vs Body), der die Femur-Tibia-Kopplung
exakt erfasst (hängt von Maßen/Längen ab, nicht hardkodiert). Das Tibia-Joint-Limit darf
dann aufs mechanische Maximum, der Check macht die pose-abhängige Sicherheit. Damit wird
die feet-closer Lauf-Pose sicher möglich.

> **→ Der gesamte „Rest" (Kollisions-Check, Limit-Anhebung, feet-closer Pose, Re-Tune,
> Zwei-Phasen) ist im eigenen Plan ausgearbeitet:**
> **[`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md)**
> (zu reviewen NACH der RViz-Stage). Die alte Weg-A/B-Diskussion + die alten Teile 3/4
> wurden dorthin überführt / sind dort als Teil 2a–2d strukturiert.

---

## 5. Tests-Liste — nur Teil 1 (Rest siehe Kollisions-Plan)
- **Teil 1 (Viz):** Node baut + läuft; RViz zeigt die Fuß-Wolke pro Bein; zwei-Wolken-
  Overlay (blau aktuell / rot volle Tibia) sichtbar; FK-Punkte stimmen mit dem Modell überein.
- **Teil 2+ (Kollisions-Check, Limit, Pose, Re-Tune):** Tests-Liste im
  [`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md) §3.

---

## 6. Progress-Checkliste
```
### Teil 1 — Reachability-Viz-Tool  ✅ (1.1–1.4), 1.5 = RViz-Live durch User (morgen)
- [x] 1.1  Viz-Node `hexapod_gait/reachability_viz.py`: Sweep coxa/femur/tibia → leg_fk → MarkerArray (base_link, via mount_yaw/xyz)
- [x] 1.2  Zwei-Wolken-Overlay: blau=aktuelles URDF-Limit (live xacro), rot=volle kalibrierte Tibia (`tibia_full_upper` default 2.60≈149°)
- [x] 1.3  Param `leg` (leg_1..6 / 'all'), live umschaltbar; `resolution`/`tibia_full_upper` parametrierbar
- [x] 1.4  `reachability_viz.launch.py` + `view_reach.rviz`; Build grün; FK-Stichprobe vs Modell verifiziert (leg_1 @0 → base (0.316,−0.294,0)); Benutzungs-Doku `phase_13_stage_1_reachability_viz_test_commands.md`
- [ ] 1.5  User sieht die Hülle + den verschenkten roten Raum (RViz-Live)
```
**Teil 2+ (Kollisions-Check Weg B-Voll → Limit → feet-closer Pose → Re-Tune → Zwei-Phasen):**
Checkliste (2a–2d) im **[`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md) §4.**

---

## 7. Offene Punkte für User-Review (vor Code-Beginn)
| # | Frage | Status |
|---|---|---|
| 7.1 | Reihenfolge: erst Viz-Tool (sehen), dann tunen? | ✅ **ja** — Viz (Teil 1) erledigt, jetzt Teil 2 |
| 7.2 | Viz: ein Bein oder alle 6? Auflösung? | ✅ **umschaltbar** (Default 1 Bein, `leg:=all` möglich), Default-Auflösung 14 |
| 7.3 | Tibia-Beuge-Limit: trotz „kalibriert" noch HW-Kollisions-Check? | ⏳ **läuft in 7.8 auf** (femur-gekoppelt — siehe §4.2.0) |
| 7.4 | Neuer Beuge-Limit-Zielwert? | ⏳ siehe 7.9 |
| 7.5 | Walking: omnidirektional-grün ODER vorwärts-optimiert (Sidestep eingeschränkt)? | ⏳ |
| 7.6 | Zwei-Phasen jetzt oder nach dem einfachen Limit+Pose-Tuning? | ⏳ |
| 7.7 | Stage-Nummer/Name ok (Phase 13 Stage 1)? PHASE.md aktualisieren | ✅ erledigt (PHASE.md zeigt auf Stage 1) |
| **7.8** | Weg A (konstant) vs Weg B (Kollisions-Check)? | ✅ **Weg B-Voll** (geometrie-getrieben) — Plan: `phase_13_stage_1_collision_check_plan.md` |
| **7.9** | Tibia-Limit-Zielwert | ✅ **mechanisches Max (~+2.6)**, Check sichert ab (collision plan §5.5) |
| **7.10** | Femur-unten-Kollision: Body/Boden/Femur? | ✅ **moot** (Posen nie genutzt; Check deckt's generisch ab — User-Einsicht 2026-06-01) |

---

## 7a. Teil-2-Entscheidungen — Diskussions-Historie (✅ ENTSCHIEDEN: Weg B-Voll)

> **Ergebnis (User 2026-06-01): Weg B-Voll** — der geometrie-getriebene Selbst-Kollisions-
> Check ist die saubere, nicht-hardkodierte Lösung; die Umsetzung steht im
> **[`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md)**.
> Der ursprüngliche „Weg A jetzt"-Vorschlag wurde verworfen. Die folgende Diskussion
> bleibt als **Begründungs-Historie** stehen (warum B statt A; 7.10 ist moot).

### 7.8 — Weg A (konstantes Limit) vs Weg B (Selbst-Kollisions-Check)

**Weg A — ein konstantes, lauf-getuntes Tibia-Limit** (z.B. +2.0 rad):
- Fester URDF-Wert, der für den **Lauf-Femur-Bereich (oben) sicher** ist. Nur ein
  Wert ändern (URDF + config.py + cal `pulse_min`).
- ✅ **Schnell** — in ~1 Session beim besseren Laufen.
- ⚠️ Der feste Wert gilt für *alle* Femur-Winkel, würde also theoretisch auch
  „Femur-unten + tief beugen" erlauben (Kollision). **Aber:** Gait + Standup halten
  den Femur immer oben → diese Pose wird nie kommandiert. Praktisch sicher.

**Weg B — Selbst-Kollisions-Check in der IK** (Fuß-vs-Body):
- `leg_ik` lehnt Posen ab, bei denen der Fuß in den Body würde → erfasst die
  Femur-Tibia-Kopplung **exakt**, volle Range wo sicher, automatisch begrenzt wo nicht.
- ✅ **Sauber + zukunftssicher** — gilt auch für Balance / unebenen Boden / andere
  Bewegungen. Das konstante Limit könnte man dann ganz lockern.
- ⚠️ **Mehr Arbeit:** Body-Kollisions-Volumen modellieren, Check + Tests, Edge-Cases.

> **Vorschlag: Weg A jetzt, Weg B später.** Ziel ist „sichtbar besser laufen" — Weg A
> liefert das sicher + schnell (Femur beim Laufen oben). Weg B ist die größere
> Investition, die sich erst bei komplexeren Bewegungen (Balance/Terrain) richtig
> lohnt. Erst einfach + schnell, Robustheit nachrüsten wenn nötig.

### 7.9 — Falls Weg A: welcher Zielwert?
Aktuell +1.30 (74°). Bedarf: Stand-Pose +0.76 (43°), feet-closer Lauf-Pose ~90–100°
(1.6–1.75), plus Reserve für Stride.

| Wert | Winkel | Bewertung |
|---|---|---|
| +1.57 | 90° | „Überall-sicher" (auch Femur-unten-Worst-Case). Nur +16° über jetzt → magerer Lauf-Gewinn. |
| **+2.0** | **115°** | **Komfortabel für deutlich nähere Lauf-Pose + Stride; 35° Marge zum ~150°-Lauf-Limit. Empfohlen.** |
| +2.6 | 149° | Volles lauf-sicheres Maximum. Maximaler Spielraum, aber 0 Marge zur Kollision (Femur-oben). Aggressiv. |

> **Vorschlag: +2.0 (115°)** — solider Schritt, ermöglicht nähere/größere-Schritt-Pose
> mit Sicherheits-Marge. Exakten Bedarf der feet-closer Pose dann mit
> `walking_envelope_check` (Teil 3) validieren + ggf. nachziehen. Nicht gleich +2.6
> (lieber Marge behalten).

### 7.10 — Femur-unten + Tibia-90°: kollidiert Fuß mit Body / Boden / Femur?
Ändert, ob die Einschränkung überhaupt relevant ist:
- **Boden:** aufgebockt irrelevant; beim Laufen steht der Fuß eh am Boden → **kein**
  Joint-Limit-Thema.
- **Body** (Fuß schwenkt unter den Körper): echte Selbst-Kollision, femur-gekoppelt →
  spricht für Weg B / Vorsicht bei Weg A.
- **Femur** (Tibia gegen Femur-Segment): wäre ein *konstanter* Knie-Anschlag — aber
  die max. Beuge **variiert** mit dem Femur-Winkel (150°/90°), also ist es
  **wahrscheinlich NICHT** der Femur → eher Body oder Boden.

> **Vorschlag:** kurz an der HW schauen, **was** bei Femur-unten den Fuß stoppt.
> Tipp: Boden/Body, nicht Femur — dann ist die Femur-unten-Grenze fürs aufgebockte
> Laufen ohnehin kein Thema → Weg A noch unbedenklicher.

### Nachgelagert (Teil 3/4 — später)
- **7.5** — Walking **omnidirektional-grün** (alle Richtungen sicher, kleinere Schritte)
  **oder vorwärts-optimiert** (große Vorwärts-Schritte, Sidestep eingeschränkt + Warnung)?
- **7.6** — **Zwei-Phasen-Architektur** (aufstehen → Füße-reposition → laufen) **jetzt**
  bauen oder erst nach Limit+Pose-Tuning sehen, ob nötig?

### 📌 Zusammengefasster Vorschlag
Weg **A** mit **+2.0**, vorher kurz **7.10** an der HW klären (was stoppt den Fuß bei
Femur-unten). Alternative: gleich Weg **B** (sauberes Kollisions-Modell), falls Robustheit
Vorrang hat.

---

## 8. Cross-References
- Tibia-Kontext: `phase_13_stage_0_progress.md` (0.6.5/0.6.6), `phase_13_stage_0_6_5_tibia_measure_test_commands.md`,
  `phase_13_stage_0_6_6_tibia_recal_plan.md`
- Tools: `tools/walking_envelope_check.py` (+README), `tools/standup_envelope_check.py`
- Code: `gait_node.py`, `hexapod.urdf.xacro` / `hexapod.ros2_control.xacro` /
  `hexapod_physical_properties.xacro`, `config.py`, `servo_mapping.yaml`, `leg_ik.py`/`leg_fk`
- **Teil 1 (erledigt):** `src/hexapod_gait/hexapod_gait/reachability_viz.py`,
  `src/hexapod_gait/launch/reachability_viz.launch.py`,
  `src/hexapod_description/config/view_reach.rviz`,
  Benutzung: [`phase_13_stage_1_reachability_viz_test_commands.md`](phase_13_stage_1_reachability_viz_test_commands.md)
- **Teil 2+ (aktiv, Weg B-Voll):** [`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md)
- Memory: `project_two_joint_limit_sources`, `project_phase11_convenience_aliases`
