# Phase 13 — Stage 0.5: Sim-Visualisierung (Init-Pose → Aufstehen)

> **STATUS: ✅ FERTIG (2026-05-31).** Live T1–T3 durch User grün: Sim startet
> exakt in power_on_mid (gz_ros2_control wendet `initial_value` an → §7.5-Fallback
> nicht nötig), all-6 Stand-up stabil + Körper horizontal, Endpose exakt
> Stand-Pose. **1 🟡-Befund:** Füße schürfen ~15-22mm horizontal nach innen
> (joint-space-Ramp, NICHT Tibia-Länge — per Math falsifiziert) → HW-Verify in
> 0.6/0.7. Details: `phase_13_stage_0_progress.md` Final-Review + Memory
> `project_phase13_standup_foot_scrape`.

---

## 0. ⭐ FÜR DEN NÄCHSTEN CHAT: Was zuerst lesen + wie anfangen

**Du (frischer Chat) sollst Sub-Stage 0.5 umsetzen. Lies in dieser Reihenfolge:**

1. **`CLAUDE.md`** (Repo-Wurzel) — Arbeitsanweisung. Besonders §4 (Arbeitsweise:
   Plan → Freigabe → Implementierung → Tests → Self-Review) und §5 (Shell-Verbote).
2. **`PHASE.md`** — aktuelle Phase (Phase 13, Stage 0).
3. **`docs/00_conventions.md`** — Joint-Naming, Frames, Einheiten, §11.4 Joint-Limits.
4. **`docs_raspi/phase_13_stage_0_plan.md`** — Stage-0-Gesamtvertrag (§3 Lösungskonzept,
   §6 Sub-Stage-Kette, §7 Done-Kriterium, Design-Log DL-1…DL-7).
5. **`docs_raspi/phase_13_stage_0_progress.md`** — Done-Tracker. Stand: 0.1✅ 0.2✅
   0.3✅ 0.4✅. Lies die Post-Reviews von 0.3 (Relay/Init) + 0.4 (Stand-up + der
   Stand-Pose-Limit-Bug, der dort gefixt wurde).
6. **`docs_raspi/phase_13_stage_0_4_standup_plan.md`** — der Stand-up-Mechanismus,
   den 0.5 visualisiert. **Besonders §3.1 (power_on_mid-rad-Werte)** und
   **§3.3 (gültige Stand-Höhen-Tabelle)** — die brauchst du direkt.
7. **DIESE Datei** (`phase_13_stage_0_5_sim_standup_plan.md`) — der 0.5-Plan.

**Relevante Memory-Einträge** (stehen im MEMORY.md-Index, lies die verlinkten):
- `project_two_joint_limit_sources` — ⚠️ KRITISCH: zwei Joint-Limit-Quellen
  (URDF coxa±0.415/tibia±1.161 vs config.py ±1.57/±1.50). Für rad↔pulse + Pose-
  Validierung IMMER die URDF-Limits. Sim läuft „lenient" (ohne Limit-Check) und
  **maskiert** Limit-Verletzungen, die auf HW freezen — genau dieser Effekt hat in
  0.4 den Stand-Pose-Bug verursacht.
- `project_phase13_gait_launch_sim_time_default` — `gait.launch.py` braucht in der
  Sim `use_sim_time:=true`; Default ist `false` (HW). Ohne /clock blockt der
  rclpy-Timer.
- `feedback_interactive_stage_test_doc` + `feedback_test_commands_in_doc_not_chat`
  — 0.5 ist interaktiv: ALLE Live-Befehle gehören vollständig+ausführbar in
  `phase_13_stage_0_5_sim_standup_test_commands.md`, nicht in den Chat.
- `feedback_no_trim_verification_output` — Verifikations-Outputs nicht mit
  tail/grep beschneiden.
- `feedback_user_does_commits` — der User committet selbst. Keine git-commits.

**Erste Handlung im neuen Chat:** §7 (offene Punkte) mit dem User klären, DANN
nach Freigabe implementieren. NICHT direkt loscoden.

---

## 1. Was ist Stage 0.5 und warum?

**Einordnung in die Kette:** Stage 0 bringt den Hexapod vom Einschalten bis zum
Aufstehen:
- **0.3 ✅** Plugin-Init: Relay an, alle Servos auf Servo-Mitte (power_on_mid =
  1500 µs). Der Roboter liegt dann mit angehobenen/eingezogenen Beinen, Bauch ~am
  Boden.
- **0.4 ✅** Aufsteh-**Logik** (pure-Python, getestet): `gait_node` rampt mit der
  STARTUP_RAMP-State-Machine **alle 6 Beine gleichzeitig** smooth von der Start-
  Pose zur Stand-Pose. In 0.4 wurde dabei ein Bug gefunden+gefixt (Stand-Pose
  verletzte das Tibia-Limit → Stand-Pose ist jetzt radial 0.295 / body_height −0.080).
- **0.5 (DIESE Stage)** = das Aufstehen **in der Simulation (Gazebo + RViz)
  sichtbar machen + physikalisch validieren**, BEVOR es am echten Roboter läuft.
- **0.6** = dasselbe am echten Roboter, aufgebockt.
- **0.7** = am Boden, volle Schwerkraft.

**Sinn von 0.5 (Risiko-Reduktion):** 0.4 hat nur die *Mathematik* bewiesen
(Winkel in-limits, monoton). Die Sim zeigt zusätzlich die **Physik + Dynamik**:
Kippt der Körper beim Hochdrücken? Rutschen die Füße weg? Sackt er durch? Hebt der
Bauch sauber ab? Das kann man risikolos in Gazebo sehen, bevor echte Servos unter
Last fahren (CLAUDE.md §4: erst Logik, dann Sim, dann HW).

**User-Kernidee (2026-05-30):** Die Sim soll **bei power_on_mid starten** — also
genau der Pose, in der die echte HW nach dem Servo2040-Init steht — und von dort
aufstehen. So ist die Sim repräsentativ für 0.6, nicht nur ein generischer Test.

---

## 2. Wie Sim und HW sich unterscheiden (wichtig zu verstehen)

Der Roboter hat **zwei ros2_control-„Backends"**, umgeschaltet per xacro-Arg
`use_sim` (in `hexapod.ros2_control.xacro`):

| | **Sim-Pfad** (`use_sim:=true`) | **HW-Pfad** (`use_sim:=false`) |
|---|---|---|
| Plugin | `gz_ros2_control/GazeboSimSystem` | `hexapod_hardware/HexapodSystemHardware` |
| Physik | Gazebo (Schwerkraft, Kontakt, Reibung) | echte Servos |
| Init-Pose kommt von | **`initial_value` in der URDF** (das baut 0.5 ein) | Plugin `on_activate` (1500 µs, Stage 0.3) |
| Relay / Strom-Gate | **gibt es nicht** | echtes Relay (GP26) |
| Servo-Mitte-Verhalten | physikalisch nicht vorhanden | HW-Firmware-bedingt |

**Konsequenz, die du verstehen musst:** Es gibt in Gazebo **kein Relay und keine
Servo-Firmware**. Die Sim kann power_on_mid also NICHT über den Plugin-Mechanismus
bekommen. Stattdessen setzt man die Sim-Startwinkel direkt in der URDF über
`<param name="initial_value">` im `state_interface`. Das ist der Standard-
ros2_control-Weg. Wichtig: dieser Parameter wird **nur vom gz-Plugin gelesen**,
das HW-Plugin ignoriert ihn — deshalb ist die Änderung HW-sicher, wenn man sie in
den `<xacro:if value="${use_sim}">`-Zweig setzt.

---

## 3. Physik-Fakten aus dem aktuellen Code (verifiziert 2026-05-30)

Damit der nächste Chat nicht rätselt — das steht WIRKLICH im Code:

- **`base_link` (Bauch) hat eine Kollisions-Box** (`hexapod.urdf.xacro`, Block
  `<link name="base_link">`): `<collision><box size="body_length × body_width ×
  body_height"/>`. Der Bauch kann also physisch auf dem Boden aufliegen. ✅
- **Reibung** (`hexapod.urdf.xacro` → `hexapod.gazebo.xacro`): **NUR die 6
  Foot-Kugeln haben explizite Reibung** (`mu1=mu2=1.0`, kp=1e6, kd=100). Für
  `base_link` und die Bein-Segmente ist **KEINE** Reibung gesetzt → Gazebo-
  Default (in gz Harmonic typ. μ≈1.0). ⚠️ KORREKTUR ggü. erstem Entwurf: die
  vorher genannten Werte „Bauch μ=0.1 / Beine μ=0.3" waren falsch/erfunden — es
  gibt sie nicht. Falls der Bauch beim Aufstehen nicht sauber abrutscht/abhebt,
  ist das ein in 0.5 zu beobachtender Punkt (ggf. Bauch-Reibung gezielt
  ergänzen — offener Punkt §7.4).
- **`initial_value`** ist ein Standard-ros2_control-Feature (`hardware_info.hpp`,
  `handle.hpp` in /opt/ros/jazzy). Ob das **gz**-Plugin es beim Spawn anwendet,
  ist **nicht 100% garantiert** und muss live geprüft werden (Test T1, mit
  Fallback §7.5).
- **Stand-up-Logik** liegt komplett in `gait_node.py` (STARTUP_RAMP, Stage 0.4) —
  **0.5 braucht KEINEN Code-Change an der Gait-Logik**.
- **Stand-Pose-Defaults** (nach 0.4-Fix): radial_distance **0.295**, body_height
  **−0.080**. Diese gelten in gait_node.py + gait.launch.py + stand_node.py +
  stand.launch.py.
- **power_on_mid-rad pro Joint** (Sim-Startwinkel) stehen in Plan-0.4 §3.1.
  Kurzfassung (rad): coxa −0.069…+0.156 (leg-spezifisch, Cal-Toleranz), femur
  −0.42…−0.64, tibia +0.16…+0.26. **Exakte 18 Werte: Plan-0.4 §3.1.**

---

## 4. Was 0.5 konkret tut (geplante Änderungen)

| Datei | Änderung | Begründung |
|---|---|---|
| `hexapod_description/urdf/hexapod.ros2_control.xacro` | Im `joint_iface`-Macro pro Joint `<param name="initial_value">` setzen, **nur** im `<xacro:if value="${use_sim}">`-Zweig. 18 exakte power_on_mid-rad-Werte (Plan-0.4 §3.1). | Sim startet bei der realen HW-Init-Pose. HW-Pfad unberührt (liest den Param nicht). |
| `hexapod_bringup/launch/sim.launch.py` | `spawn_z` so wählen, dass der Bauch nach dem Fallenlassen ~knapp über/auf dem Boden zur Ruhe kommt. | Aufstehen „vom Bauch" soll sichtbar sein, nicht aus der Luft. |
| **kein** Gait-/Plugin-Change | — | Stand-up-Logik ist in 0.4 fertig; HW-Pfad bleibt unangetastet. |

**Ablauf beim Live-Test:**
1. `sim.launch.py` (use_sim:=true) → Gazebo, Roboter spawnt bei power_on_mid,
   fällt minimal, Bauch liegt auf, JTCs aktiv.
2. `gait.launch.py use_sim_time:=true robot_description_file:=…` → gait_node liest
   `/joint_states` (= power_on_mid), startet STARTUP_RAMP, rampt all-6 zur
   Stand-Pose über ~4 s.
3. In Gazebo + RViz beobachten: sauberes Aufstehen, kein Kippen, stabile Endpose.

---

## 5. Tests (Done-Kriterium 0.5)

### 5.1 Build/Parse (ohne HW, CI-nah)
- `xacro …/hexapod.urdf.xacro use_sim:=true` parst, `initial_value` vorhanden.
- `xacro …/hexapod.urdf.xacro use_sim:=false` parst, **kein** `initial_value`
  (beweist: HW-Pfad unberührt).
- `colcon build --packages-select hexapod_description` grün.

### 5.2 Live (interaktiv, in test_commands)
- **T1:** Sim-Start → Roboter steht in power_on_mid (Femurs hoch, Bauch ~Boden),
  **nicht** in T-Pose. (Verifiziert, dass `initial_value` wirkt.)
- **T2:** gait_node → alle 6 Beine rampen all-6 zur Stand-Pose, Körper hebt sich,
  **kein Kippen / Wegrutschen / Durchsacken**.
- **T3:** Endpose stabil über mehrere Sekunden.
- **T4:** RViz zeigt konsistente Pose (tf2 ok), passend zu Gazebo.

### 5.3 Bewusst NICHT in 0.5
- Relay/Strom (HW-only → 0.6). Walking nach dem Stehen (spätere Stage).
- Boden-Aufstehen unter voller Last am echten Roboter (→ 0.7).

---

## 6. Progress-Checkliste (kommt nach Freigabe ins progress-File als 0.5.x)

```
- [ ] 0.5.1  initial_value (18 power_on_mid-rad) sim-only in ros2_control.xacro
- [ ] 0.5.2  xacro use_sim:=true → initial_value da; use_sim:=false → NICHT da (HW unberührt)
- [ ] 0.5.3  spawn_z angepasst (Bauch ~am Boden nach Drop)
- [ ] 0.5.4  colcon build hexapod_description grün
- [ ] 0.5.5  Live T1: Sim startet in power_on_mid (nicht T-Pose)
- [ ] 0.5.6  Live T2: all-6 Stand-up sauber, kein Kippen/Rutschen
- [ ] 0.5.7  Live T3: Endpose stabil
- [ ] 0.5.8  Live T4: RViz konsistent mit Gazebo
- [ ] 0.5.9  Self-Review-Tabelle, Fixe erledigt
```

---

## 7. Offene Punkte / Entscheidungen

Jede Frage hier mit **ausführlicher** Erklärung der Optionen + Konsequenzen,
damit der User die Auswirkung versteht.

> **Entscheidungs-Status (2026-05-30):**
> 7.1 ✅ exakte Cal-Werte · 7.2 ✅ live iterieren · 7.3 ✅ Default −0.080/0.295 ·
> 7.7 ✅ Sim↔HW kompatibel (Geometrie tabu) · 7.6 ✅ nur Gazebo (User 2026-05-31)
> · 7.4/7.5 ⏳ Live-Punkte (erst beim Sim-Start).

### 7.1 — Welche power_on_mid-Werte als Sim-Startpose? — ✅ Option A
**ENTSCHIEDEN (User 2026-05-30): Option A (18 exakte HW-Cal-Werte).** Begründung:
„wir simulieren unsere echte Hardware, also exakte Werte". Wartungshinweis: bei
Neu-Kalibrierung der Servos die 18 Werte nachziehen + im Code dokumentieren.

**Worum geht's:** Die 18 Startwinkel der Sim. Zwei Möglichkeiten.
- **Option A — 18 exakte HW-Cal-Werte** (Plan-0.4 §3.1): Jeder Joint bekommt
  genau den rad-Wert, den `pulse_us_to_radians(1500)` mit der echten Kalibrierung
  liefert. *Konsequenz:* Die Sim zeigt exakt die Pose, die `/joint_states` auf der
  echten HW nach dem Init meldet — inkl. der kleinen per-Bein-Asymmetrien
  (Coxa −6°…+9°), die aus Servo-Montage-Toleranz stammen. Maximale Echtheit.
  *Nachteil:* Koppelt die Sim-URDF an die aktuelle Kalibrierung — wird neu
  kalibriert, müssten die Werte nachgezogen werden (dokumentieren!).
- **Option B — idealisiert-symmetrisch** (coxa 0 / femur −0.49 / tibia 0, alle
  Beine gleich): Saubere mechanische Servo-Mitte nach Umbau, entkoppelt von der
  Cal. *Konsequenz:* Sim-Start sieht „aufgeräumter" aus, weicht aber sichtbar von
  der echten HW-Startpose ab.
- **User-Tendenz bisher (2026-05-30):** Option A („wir simulieren unsere echte
  Hardware, also exakte Werte"). **→ Im neuen Chat bestätigen lassen.**

### 7.2 — spawn_z (Fallhöhe / Bauch-Abstand zum Boden) — ✅ Option A
**ENTSCHIEDEN (User 2026-05-30): Option A (live iterieren).** Groben Startwert
(Roboter fällt aus ~2–3 cm) setzen, in T1 anschauen, justieren. Gazebo findet die
Ruhelage selbst; exakter Wert unkritisch.

**Worum geht's:** Aus welcher Höhe der Roboter in Gazebo gespawnt wird. Aktuell
`spawn_z=0.20` (fällt 20 cm). Für 0.5 soll der **Bauch nahe am Boden** zur Ruhe
kommen, damit „Aufstehen vom Bauch" sichtbar ist.
- **Option A — live iterieren:** Startwert grob setzen, in T1 anschauen, anpassen.
  *Konsequenz:* schnell, pragmatisch, 1–2 Sim-Starts mehr.
- **Option B — vorab exakt berechnen:** Aus der power_on_mid-Bein-Geometrie den
  tiefsten Punkt (Fuß-Z relativ base_link) rechnen → spawn_z so, dass Bauch ~0,5 cm
  über Boden. *Konsequenz:* erster Start sitzt, etwas mehr Rechnung vorab.
- **Hinweis:** Eigentlich kann man den Roboter auch einfach aus geringer Höhe
  (z.B. 2–3 cm) fallen lassen und Gazebo die Ruhelage finden lassen — die Beine in
  power_on_mid sind eingezogen, der Bauch ist ohnehin der tiefste/zentrale Punkt.

### 7.3 — Stand-Höhe für die Demo — ✅ Default −0.080/0.295
**ENTSCHIEDEN (User 2026-05-30): Default −0.080 / radial 0.295** (0.4-Default,
mittlere stabile Höhe, tibia 0.758 rad in-limit). Andere Höhen per Param live.

**Worum geht's:** Auf welche Höhe der Roboter aufsteht. Default nach 0.4:
body_height −0.080 / radial 0.295 (tibia 0.758 rad, in-limit).
- *Konsequenz:* Das ist eine mittlere, stabile Höhe. Andere gültige Höhen
  (Tabelle Plan-0.4 §3.3, −0.05 bis −0.11) sind per Param live anfahrbar, falls
  man im Sim verschiedene zeigen will. **Vorschlag: Default −0.080 nehmen.**

### 7.4 — Bauch-Reibung (potenzielles Aufsteh-Problem)
**Worum geht's:** Nur die Füße haben getunte Reibung (μ=1.0). Der Bauch nutzt
Gazebo-Default. Beim Aufstehen drücken die Füße den Körper hoch, der Bauch hebt
ab — sollte gehen. *Falls* der Bauch in der Sim „klebt" oder ruckt:
- **Option A — erstmal nichts ändern**, beobachten (T2). Wenn sauber → fertig.
- **Option B — falls Problem:** dem `base_link` in `hexapod.gazebo.xacro` eine
  niedrige Reibung geben (z.B. μ=0.2), damit er beim Hochdrücken sauber gleitet.
  *Konsequenz:* zusätzlicher gazebo-only Block (HW-unschädlich, RSP ignoriert ihn).
- **Vorschlag:** A (beobachten), B nur wenn nötig.

### 7.5 — Fallback wenn gz_ros2_control `initial_value` ignoriert
**Worum geht's:** Es ist nicht 100% sicher, dass das gz-Plugin `initial_value`
beim Spawn anwendet (versionsabhängig). Falls T1 zeigt, dass der Roboter doch in
T-Pose (rad≈0) startet:
- **Option A — als bekannte Sim-Limitation dokumentieren** und das Aufstehen
  trotzdem zeigen (von T-Pose statt power_on_mid). *Konsequenz:* Die Stand-up-
  Bewegung wird validiert, aber nicht aus der exakten HW-Startpose. Weniger
  realistisch, aber kein Blocker für die Logik-Validierung.
- **Option B — Workaround:** Eine kurze „Vorpose-Phase" (z.B. einmal power_on_mid
  als JTC-Goal anfahren) bevor STARTUP_RAMP startet. *Konsequenz:* mehr Aufwand,
  künstlicher als die echte Init-Sequenz.
- **Entscheidung erst wenn der Fall eintritt** (in 0.5 live).

### 7.6 — RViz zusätzlich zu Gazebo? — ⏳ Empfehlung: nur Gazebo
**Worum geht's:** Visualisierung in 0.5. Gazebo zeigt Physik, RViz zeigt tf/Pose.
**Empfehlung (im neuen Chat bestätigen):** Für 0.5 **nur Gazebo**. Begründung:
RViz simuliert nichts, es spiegelt nur `/joint_states` — in der Sim zeigt Gazebo
ohnehin schon das gerenderte Modell *mit* Physik, RViz daneben wäre nahezu
redundant (nur tf-Frame-Check). RViz entfaltet seinen Wert erst in **0.6 (HW)**,
wo es das einzige Visualisierungsfenster ist (kein Gazebo auf echter HW).
- Falls doch RViz in 0.5 gewünscht: **ohne** `joint_state_publisher_gui`
  starten (`display.launch.py with_jsp_gui:=false`) — sonst kollidiert dessen
  eigener /joint_states-Strom mit dem aus der Sim. Genauen Startbefehl dann im
  test_commands fixieren.

### 7.7 — Sim↔HW-Kompatibilität: brechen die 0.5-Änderungen den HW-Pfad? — ✅ geklärt
**User-Frage (2026-05-30):** „Derzeit kann man entweder Gazebo+RViz ODER
RViz+echte HW gleichzeitig benutzen. Wenn wir für das Sim-Aufstehen etwas ändern
(Höhe, initial_value …) — spielen RViz + echte HW dann noch zusammen?"

**Antwort: Ja, voll kompatibel — solange wir die URDF-*Geometrie* nicht anfassen
(tun wir nicht).** Aufschlüsselung der 0.5-Änderungen:

| 0.5-Änderung | Wo | Wirkt auf HW-Pfad? | Bricht Kompatibilität? |
|---|---|---|---|
| `initial_value` (Sim-Startpose) | ros2_control.xacro, **`<xacro:if use_sim>`** | Nein — bei `use_sim:=false` existiert der Block im URDF gar nicht; HW-Plugin liest ihn nie | **Nein** |
| `spawn_z` (Fallhöhe) | `sim.launch.py` | Nein — `real.launch.py` kennt kein spawn_z | **Nein** |
| Stand-Höhe-Param (−0.080/0.295) | gait_node/launch (Zahlen) | Ja, aber **gewollt gleich** (gefixte in-limit Stand-Pose für beide) | Nein (gewollt) |
| **URDF-Geometrie** (Mounts, Längen, Femur-Achse) | — **wird NICHT geändert** — | — | **Nein** |

**Der kritische Punkt (warum die Sorge berechtigt war):** Würde man die
URDF-*Geometrie* ändern (z. B. den Femur-Mount-Origin physisch um 35° rotieren,
um die Sim „schön" zu machen), DANN bräche es — die Geometrie liest **jeder**
Pfad (Sim+HW, RViz+Plugin+IK). Das wäre der eine Weg, RViz+HW zu zerstören.

**Genau deshalb haben wir in Stage 0.2 „Weg A" (DL-1) gewählt:** der 35°-Femur-
Umbau lebt in der **Kalibrierung**, NICHT in der URDF-Geometrie. Die Geometrie
ist für Sim und HW identisch und bleibt in 0.5 **unangetastet**. Der `use_sim`-
Switch trennt nur die Backend-Plugins + den `initial_value`-Block, nicht die
Geometrie.

> **⛔ Regel für 0.5 (und Folge-Stages):** Die URDF-Geometrie (Mount-Origins,
> Segmentlängen, Joint-Achsen) ist TABU. Sim-Anpassungen passieren über
> `initial_value` (sim-only), Launch-Parameter und Kalibrierung — NIE über
> Geometrie-Edits. Sonst bricht der HW-Pfad.

---

## 8. Cross-References
- **Stage-0:** `phase_13_stage_0_plan.md` (Vertrag) · `phase_13_stage_0_progress.md` (Tracker + DL-7 all-6)
- **Vorgänger:** `phase_13_stage_0_3_init_sequence_plan.md` (Init) · `phase_13_stage_0_4_standup_plan.md` (Stand-up + §3.1 power_on_mid-rad + §3.3 Höhen)
- **Code (lesen bei Implementierung):**
  - `src/hexapod_description/urdf/hexapod.ros2_control.xacro` (joint_iface-Macro, use_sim-Switch)
  - `src/hexapod_description/urdf/hexapod.gazebo.xacro` (Reibung)
  - `src/hexapod_bringup/launch/sim.launch.py` (Sim-Bringup, spawn_z, JSB+JTC-Spawner)
  - `src/hexapod_gait/launch/gait.launch.py` (use_sim_time, robot_description_file)
  - `src/hexapod_description/launch/display.launch.py` (RViz, with_jsp_gui)
- **Tool:** `tools/walking_envelope_check.py` (Posen gegen echte Limits prüfen)
- **Memory:** `project_two_joint_limit_sources`, `project_phase13_gait_launch_sim_time_default`,
  `feedback_interactive_stage_test_doc`, `feedback_test_commands_in_doc_not_chat`,
  `feedback_user_does_commits`

---

## 9. Zusammenfassung für den User (was passiert hier, kurz)

0.5 lässt den Hexapod **in der Simulation aufstehen** — als Generalprobe vor dem
echten Roboter. Neu ist nur: wir sagen Gazebo, dass der Roboter in der **echten
Einschalt-Pose** (power_on_mid, Bauch am Boden, Beine eingezogen) starten soll
(über einen URDF-Parameter, der nur die Sim betrifft — die echte Hardware bleibt
unberührt). Dann übernimmt die schon fertige Aufsteh-Logik aus 0.4 und drückt den
Körper mit allen 6 Beinen hoch. Wir schauen in Gazebo (Physik) + RViz (Pose), ob
das sauber, kippfrei und ohne Limit-Verletzung passiert. Kein Risiko für echte
Servos. Was wir bewusst NICHT testen: Relay/Strom (gibt's nur auf HW → 0.6) und
das Aufstehen unter voller Last am Boden (→ 0.7).
