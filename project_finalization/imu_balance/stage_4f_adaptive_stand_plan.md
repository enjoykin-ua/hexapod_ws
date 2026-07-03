# Stufe 4 / S4-7 — Terrain-anpassendes Stehen (Adaptive Stand)

> Teil-Stufe von [Stufe 4 Terrain-adaptiv](stage_4_terrain_adaptive_plan.md) (Block A5). **Ziel:** wenn
> die Fußkontakt-Pipeline aktiv ist, soll der Roboter im **STANDING** die Beine **einzeln bis zum
> Boden absenken** statt in der Luft zu hängen (auf unebenem Gelände wie Rubicon). Ist das Feature
> **aus**, bleibt STANDING **exakt** wie heute (starre Flachboden-Pose, keine Regression).
>
> **Status: 🟡 Code + Tests + Envelope + Doku fertig — Sim-Verify (Rubicon) durch User offen.**
> ⚠️ **Blocker beim Verify entdeckt + behoben (nicht S4-7):** Hinsetzen/Aufstehen/Stance-Wechsel über
> Service/PS4 kippten in den Stand zurück — Ursache war ein **vorbestehender Seiteneffekt in
> `compute_foot_targets`**, ausgelöst von der S4-1-Debug-Messung, **nicht** der S4-7-Konform-Code.
> Behoben (§9). S4-7-Sim-Verify damit **entblockt**.
> Engine (`_adaptive_stand_z` / `reset_stand_conform` / `_compute_standing_targets(t)`) + Node-Wiring
> (`adaptive_stand_enable` + Contact-Live-Guard + Re-Konform) + 3 Params + `tools/stand_conform_envelope_check.py`
> (tief/mittel/hoch GREEN; Default `max_depth` 0.04 = Rubicon-Sim-Feedback, Envelope-Max 0.05) implementiert;
> 782 Tests grün (22 neu). Alle
> Design-Entscheidungen in §4/§5 mit dem User geklärt. Voraussetzung S4-1/S4-2 🟢. Dies ist der
> **statische** Zwilling von S4-2 (adaptiver Touchdown), im STANDING statt im Schwung. Test-Doku:
> [`stage_4f_adaptive_stand_test_commands.md`](stage_4f_adaptive_stand_test_commands.md).

---

## 0. Kontext + warum

- Im STANDING liefert `gait_engine._compute_standing_targets` eine **starre Flachboden-Pose**: alle 6
  Füße auf `z = body_height` (gleiche Höhe unter der Körper-Aufhängung), x,y = Stand-Pose. **Keine**
  per-Fuß-Anpassung ans Gelände.
- Auf unebenem Boden ruht der Körper dann auf den Füßen, die auf **Erhöhungen** stehen; Füße über
  **Senken** hängen **in der Luft** (User-Befund auf Rubicon: `[001101]` = 3 Beine ohne Kontakt).
- Der **adaptive Touchdown (S4-2)** löst genau das — aber **nur im WALKING** (`_compute_walking_targets`).
  Im STANDING wird er nicht angewandt. S4-7 überträgt dieselbe Mechanik **statisch** in den Stand.
- **Anwendungsfall:** IMU + Taster eingeschaltet → er soll beim Stehenbleiben aufsetzen. Aus → normal.

## 1. Logik-Skizze + Pseudocode

### 1.1 Engine — statischer Absenk-Pfad (Zwilling von `_adaptive_touchdown_z`)
Pro Bein: von `body_height` **downward-only** langsam absenken, bis der Taster Kontakt meldet →
dort **einfrieren**; erreicht es den **Floor** (`body_height − stand_conform_max_depth`) ohne Kontakt
(zu tiefer Dip), dort halten (so tief wie möglich). x,y **unverändert** (nur z adaptiv). Zeitgesteuert
über die seit **STANDING-Eintritt** verstrichene Zeit (`t − t_stand_entry`), **nicht** call-count.

```
# Engine-State (neu): _stand_conform_z[leg] (frozen z | None), _t_stand_entry
# Reset (auf None / t_stand_entry=t) bei: STANDING-Eintritt  UND  body_height-Änderung.

_adaptive_stand_z(leg_id, t, z_nom=body_height):
    frozen = _stand_conform_z[leg_id]
    if frozen is not None:                      # schon gelandet → halten
        return frozen
    contact = _foot_contacts[leg_id]
    if contact:                                 # schon am Boden (Erhöhung/flach) → bei body_height verankern
        _stand_conform_z[leg_id] = body_height
        return body_height
    # kein Kontakt → langsam absenken (Rate · verstrichene Zeit) von body_height
    z_floor = body_height - stand_conform_max_depth
    descent = stand_conform_rate * max(0.0, t - _t_stand_entry)
    z = max(z_floor, body_height - descent)
    if contact:                                 # (nächster Tick) Kontakt im Absenken → hier einfrieren
        _stand_conform_z[leg_id] = z
    elif z <= z_floor:                          # Floor erreicht, kein Kontakt → Dip zu tief → am Floor halten
        _stand_conform_z[leg_id] = z_floor
    return z
```

Einbau in `_compute_standing_targets(t)` (Signatur bekommt `t`):
```
neutral = stand_pose(radial_distance, body_height)          # (x, y, body_height)
for leg:
    pt = neutral
    if adaptive_stand_enable:                               # nur z; x,y bit-identisch nominal
        pt = (pt.x, pt.y, _adaptive_stand_z(leg_id, t))
    targets[leg] = pt
# AUS: exakt neutral, keine State-Mutation → bit-identisches Fallback.
```
Leveling (`set_body_orientation_offset`) wird wie bisher **danach** in `compute_joint_angles` als
Körper-Rotation angewandt → komponiert oben drauf (v1: Bein-Frame-z, Näherung bei gekipptem Körper,
s. §5).

### 1.2 Node-Glue (`gait_node`)
- **Param `adaptive_stand_enable`** (Default false). Pro Tick auf die Engine spiegeln, **verUNDet mit
  dem Contact-Live-Guard** (wie S4-2: `engine.adaptive_stand_enable = param AND pipeline_live`; tote/
  stale Pipeline → aus → starre Pose). Kontakte kommen bereits jedes Tick via `set_foot_contacts`
  (`_update_foot_contacts` läuft state-unabhängig).
- **Re-Konform-Trigger (envelope-sicher, §4):**
  - **STANDING-(Wieder-)Eintritt** → Engine resettet `_stand_conform_z` + `_t_stand_entry` (deckt die
    Stance-Modus-Reposition ab: Höhen-Änderung läuft über REPOSITION → STANDING → Re-Konform „fällt raus").
  - **`body_height`-Änderung** (Param **oder** `/cmd_body_height`) im Stand → Engine-Reset auslösen
    (neu absenken auf der neuen Höhe). Grund: Offset-mit-reiten wäre nicht envelope-sicher (Überstreckung).
- **Params (live, validiert):** `adaptive_stand_enable` (false), `stand_conform_max_depth` (0.02 m, ≥0),
  `stand_conform_rate` (0.02 m/s, >0).

### 1.3 STANDING-Eintritt erkennen
Engine trackt `_prev_state`; beim Übergang **→ STANDING** (aus STOPPING/Standup): `_reset_stand_conform(t)`
(setzt `_stand_conform_z=None` je Bein, `_t_stand_entry=t`). Analog zu `_reset_touchdown_state` beim
WALKING-Eintritt.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: absenken→Kontakt** | Bein ohne Kontakt senkt über Zeit; Kontakt → friert bei aktuellem z ein | Zeit-Sequenz |
| **Unit: Dip zu tief** | kein Kontakt bis Floor → hält bei `body_height − max_depth` | Floor-Clamp |
| **Unit: schon Kontakt** | Kontakt bei body_height → verankert bei `body_height` (kein Absenken) | Erhöhung/flach |
| **Unit: x,y unverändert** | nur z adaptiv, x,y bit-identisch zur `stand_pose` | Regression |
| **Unit: AUS = bit-identisch** | `adaptive_stand_enable=false` → exakt `stand_pose`, keine State-Mutation | Fallback |
| **Unit: Reset STANDING-Eintritt** | frischer Absenk-Vorgang ab `t_stand_entry` | Reset-Hook |
| **Unit: Re-Konform body_height** | body_height-Änderung → neuer Absenk-Vorgang (nicht Offset-ride) | envelope-sicher |
| **Node: Wiring + Guard** | enable live; Pipeline tot/stale → starr; nur STANDING (nicht Walk/Sit/Show) | rclpy-Smoke |
| **Envelope (offline)** | Stand-Pose bei `radial_distance` je **Stance-Höhe** bis `body_height − max_depth` **IK-safe** gegen **URDF**-Limits (zwei Limit-Quellen) | Tool, GREEN |
| colcon + Lint | grün | 0 Fehler |
| **Sim (User) Rubicon** | uneben stehen → Füße setzen auf (moderate Dips); tiefe Dips hängen (dokumentiert); Stance-Höhe wechseln → Re-Konform; AUS = wie heute | beobachten |

**Bewusst NICHT (→ später, §6):** Körperhöhe/-neigung-Adaption (tiefe Dips + Buckel); welt-vertikale
Konform-Richtung; terrain-bewusste **Aufsteh-Sequenz**; S4-5-Maskierung im STANDING; kontinuierliches
Re-Konform (Rutschen).

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
S4-7:
- [ ] S4-7.1 Engine _adaptive_stand_z (static downward-only, Freeze bei Kontakt, Floor) + _stand_conform_z/_t_stand_entry + _reset_stand_conform bei STANDING-Eintritt; x,y unverändert; AUS bit-identisch
- [ ] S4-7.2 gait_node: adaptive_stand_enable-Wiring (Contact-Live-Guard) + Re-Konform-Trigger (STANDING-Eintritt via Engine + body_height-Änderung)
- [ ] S4-7.3 Params: adaptive_stand_enable (false), stand_conform_max_depth (0.02), stand_conform_rate (0.02) — live, validiert
- [ ] S4-7.4 Envelope-Check pro Stance-Höhe (radial × body_height bis Floor, URDF-Limits) GREEN
- [ ] S4-7.5 Unit-Tests (absenken/Dip/schon-Kontakt/x,y/AUS/Reset/Re-Konform) + Node-Smoke
- [ ] S4-7.6 colcon test + Lint grün
- [ ] S4-7.7 README/Konzept (terrain-anpassendes Stehen; Mechanik; Params; Grenzen)
- [ ] S4-7.8 Test-Doku stage_4f_adaptive_stand_test_commands.md (Rubicon) + Sim-Verify durch User
- [ ] S4-7.9 kritische Self-Review-Tabelle
```

## 4. User-Review-Entscheidungen (vor Code) — ✅ ALLE FREIGEGEBEN

1. **Scope v1 = nur Füße absenken** (Körperhöhe/-neigung unverändert). ✅ Körper-Adaption = später (§6).
2. **Konform-Richtung = Bein-Frame-z** (nach unten relativ zum Körper). ✅ Welt-vertikale Präzision = später (§6).
3. **Höhenänderung = Re-Konform** (nicht Offset-mit-reiten). ✅ **Grund:** envelope-sicher — der Bein-
   Arbeitsraum („Kegel") darf nicht überstreckt werden; der Roboter koppelt Höhe ohnehin mit Reposition
   (Stance-Modi S1, ersetzten die stufenlose Höhe genau deshalb). Re-Konform läuft über REPOSITION →
   STANDING (fällt raus) + body_height-Änderung.
4. **Einmal beim STANDING-Eintritt konformen + halten** (kein kontinuierliches Nachführen; Rutschen ignoriert). ✅
5. **Eigener Floor-Param** `stand_conform_max_depth` (Default 2 cm, envelope-verifiziert je Stance-Höhe). ✅
6. **Eigener Enable-Param** `adaptive_stand_enable` (Default false, opt-in). ✅ Nutzt die **Taster**;
   IMU/Leveling ist komplementär (Körper-Neigung), **nicht nötig** für „Füße auf den Boden".
7. **Aufstehen:** Sequenz **unverändert**; Konform erst **nach** Erreichen von STANDING. ✅ Caveat: die
   Aufsteh-**Rampe** nimmt weiter flachen Boden an (auf sehr rauem Grund evtl. kurz schief), erst in
   STANDING setzen die Füße nach. Terrain-bewusstes Aufstehen = später (§6).

## 5. Design-Entscheidungen (mit Alternativen)

| Entscheidung | Gewählt | Verworfen | Warum |
|---|---|---|---|
| Konform-Richtung | **Bein-Frame-z** | welt-vertikal (Schwerkraft) | einfach; bei ~waagerechtem Körper ~identisch; präzise Variante mit Körper-Item (§6) |
| Höhenänderung | **Re-Konform** | Offset-mit-reiten (`body_height + offset`) | Offset-ride ist glatter/weniger Code, ABER **nicht envelope-sicher** (Überstreckung bei zu hoch/tief); Re-Konform hält den Bein-Kegel im geprüften Bereich, konsistent mit Stance-Modi |
| Scope | **nur Füße** | + Körperhöhe/-neigung | v1 klein; Körper-Adaption löst tiefe Dips/Buckel, ist aber deutlich größer (§6) |
| Gate | **eigener Param** `adaptive_stand_enable` | an `adaptive_touchdown_enable` hängen | klar/explizit; STANDING ≠ WALKING-Feature |
| Static-Descent-Antrieb | **`t − t_stand_entry`** (Zeit seit Eintritt) | call-count | deterministisch, robust falls `compute_foot_targets` mehrfach/Tick aufgerufen wird |
| Aufstehen | **Konform nach STANDING** | terrain-bewusste Sequenz | v1 klein; Sequenz-Umbau = später |

## 6. Offene Punkte / Nice-to-have (später, je nach Sim-Tests)

- **Terrain-adaptive Körperhöhe/-neigung** — der große Nachfolger. Löst **tiefe Dips (>~2 cm)** und
  **Buckel** (Boden höher als `body_height`), die reines Fuß-Absenken nicht kann. **= die Antwort auf
  „der Fuß erreicht die Position gar nicht"** (User-Q2). Hier kommt die **IMU** ins Spiel (Neigung/Höhe
  nachführen). Auslöser: wenn Gazebo-Tests zeigen, dass Fuß-Absenken allein nicht reicht.
- **Welt-vertikale Konform-Richtung** (präzise bei stark gekipptem Körper) — zusammen mit dem Körper-Item.
- **Terrain-bewusste Aufsteh-Sequenz** (statt erst nach STANDING).
- **S4-5-Sensor-Fault-Maskierung auch im STANDING** (fauler Taster → Bein nicht falsch verankern/hängen).
  S4-5 ist aktuell WALKING-only.
- **Kontinuierliches Re-Konform** (falls der Roboter im Stand rutscht/gestoßen wird).

## 7. Handoff / Code-Anker

- **Engine (`hexapod_gait/hexapod_gait/gait_engine.py`):**
  - `_compute_standing_targets` (heute starr → hier `t` + Konform-z einbauen),
  - **Vorbild 1:1** `_compute_walking_targets` + **`_adaptive_touchdown_z`** (die Lauf-Variante: downward-
    only, Anker bei `body_height`, Freeze bei Kontakt, Floor) + `_reset_touchdown_state` (Reset-Muster),
  - `set_foot_contacts` / `self._foot_contacts` (Kontakt-Cache), `_touchdown_z`/`_td_searched` (State-Muster),
  - `compute_foot_targets` (Dispatch nach State — `_compute_standing_targets` braucht künftig `t`),
  - State-Konstanten + Übergänge (STANDING-Eintritt erkennen; `_prev_state`),
  - `set_body_orientation_offset` / Leveling-Rotation in `compute_joint_angles` (Komposition),
  - `stand_pose` in `trajectory_gen.py`.
- **Node (`gait_node.py`):**
  - `_update_foot_contacts` (Kontakt-Cache + **Contact-Live-Guard** `_foot_contact_received`/
    `_last_foot_contact_msg_t`/`_FOOT_CONTACT_STALE_S` — genau wie S4-2 gate spiegeln),
  - der **S4-2-Param-Block** (`adaptive_touchdown_enable` decl/validate/apply) als 1:1-Muster,
  - `_apply_param` / `_on_param_change` (validate-then-apply), `/cmd_body_height`-Handler + body_height-
    Apply (Re-Konform-Trigger), Tick-Reihenfolge (`_update_foot_contacts` **vor** `compute_joint_angles`).
- **Envelope-Tool:** das bestehende `tools/…envelope_check…` (für den Lauf-Floor) → für den **Stand-Floor
  je Stance-Höhe** erweitern/anwenden; **zwei Limit-Quellen** (URDF vs config.py) beachten.
- **Stance-Modi (S1):** wo `body_height`/`radial_distance` gekoppelt via REPOSITION wechseln → dort läuft
  der STANDING-Wiedereintritt, der das Re-Konform triggert.

## 8. Doku-Hygiene bei Abschluss
`imu_balance_progress.md` (S4-7-Checkliste + Post-Review; Umbrella S4-7 → 🟢), `hexapod_gait/README.md`,
`ai_navigation.md` (Fußkontakt-Eintrag um „Adaptive Stand" ergänzen), Memory
`project_a5_stage4_adaptive_touchdown` (S4-7 nachtragen), Test-Doku.

---

## 9. Nachtrag — der Sequenz-Revert-Bug (gefunden bei S4-7-Verify, aber NICHT S4-7)

> Beim Sim-Verify von S4-7 kippten **Hinsetzen, Aufstehen und Stance-Wechsel** über Service/PS4 immer
> wieder in den Stand zurück. Das Wesentliche der Diagnose:

### Symptom
- Sequenz startet (Roboter bewegt sich kurz), **kippt dann in den Ursprungszustand (STANDING) zurück**.
- Nur der **Sequenz-Pfad** (Service/PS4 → REPOSITION / CARTESIAN_STANDUP / SITDOWN / STANCE_SWITCH).
  **Sofort-Param** (`body_height` direkt setzen) und **zyklisches Laufen** waren unauffällig.
- Der Rücksprung fiel **exakt auf eine Fußkontakt-Flanke** (Standup beim ersten Bodenkontakt,
  Sit beim ersten Bein-Abheben). Auf **flacher Welt wie auf Rubicon**, RTF ≈ 1.0.

### Wurzel — ein Query mit State-Seiteneffekt
`gait_engine.compute_foot_targets(t)` ist eine **Query** (liefert Fuß-Targets), hatte aber einen
**Fallthrough**: alles, was nicht STANDING/WALKING war, fiel in `_compute_stopping_targets(t)` — und
das enthält die (legitime) STOPPING-Auto-Transition **`if all_settled: self._state = STANDING`**.
→ Wird `compute_foot_targets` in einem **Sequenz-Zustand** aufgerufen und sind die Füße „settled",
**erzwingt es STANDING und bricht die laufende Sequenz ab** — komplett an den Finish-Methoden
(`_finish_reposition` etc.) vorbei.

### Auslöser
Die **S4-1-Debug-Messung** `_debug_leg1_contact` (`foot_contact_debug_enable`, **Default an**) ruft bei
**jeder Kontakt-Flanke von Bein 1** `compute_foot_targets(t)` auf, nur um das kommandierte `cmd_z`
zu loggen. Jede Sequenz erzeugt solche Kontakt-Flanken (Beine heben/aufsetzen) → Debug feuert →
`compute_foot_targets` → STANDING erzwungen → Abbruch. Weil die Debug-Messung per Default an ist,
war der Bug **immer** aktiv (deshalb schürfte auch der Auto-Standup: seine Reposition wurde gekillt).

### Warum schwer zu finden
- Der **State-Chaining-Code war korrekt** (`start_sitdown` setzt `after=SITDOWN_LOWER`, `_finish_reposition`
  ehrt das). Instrumentierung der Finish-Methoden zeigte **nichts** — weil sie **nie erreicht** wurden.
- Der entscheidende Hinweis: die Übergänge liefen **außerhalb** der Sequenz-Logik und **synchron zu
  Kontakt-Flanken**. Gegenprobe `foot_contact_debug_enable:=false` → alles läuft sauber = Beweis.
- Irrwege unterwegs (ausgeschlossen): Zeitbasis/RTF (RTF war 1.0), stale `.pyc`/Build (Bytecode war
  aktuell; ein `35557f86`-Hash war ein `py_compile`-Docstring-Artefakt), Zweit-Workspace `~/install`
  (existiert, wird aber von `.bashrc` **nicht** gesourct).
- Ironie: die S4-7-Post-Review notierte bereits, dass `_debug_leg1_contact` `compute_foot_targets`
  „erneut" ruft — prüfte aber nur die **S4-7-Idempotenz**, nicht den **Stopping-Seiteneffekt** für
  Nicht-STANDING-Zustände.

### Fix (`gait_engine.py`)
1. **`compute_foot_targets`**: nur noch STOPPING → `_compute_stopping_targets`; **Sequenz-Zustände
   werden read-only bedient** (statische Stand-Pose via `_standing_targets`, **keine** Mutation).
2. **`_compute_stopping_targets`**: der `all_settled → STANDING`-Seiteneffekt ist an
   `self._state == STOPPING` gebunden (Defense-in-depth → read-safe für jeden Aufrufer).
→ 374 Tests grün, Lint sauber. Verifiziert: Auto-Standup schürffrei, Sit/Stand/Stance sauber, **mit**
Debug-Messung an, flach + Rubicon.

### Lektion
**Command-Query-Separation.** Eine „compute/get"-Methode darf **keinen** State mutieren. Die
Debug-Messung ging (berechtigt) von Read-Only aus — der versteckte Seiteneffekt in einem
über-breiten Fallthrough machte daraus eine scharfe Waffe gegen jede Nicht-STANDING/WALKING-Sequenz.
