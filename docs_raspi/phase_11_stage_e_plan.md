# Phase 11 — Stufe E — Plan

> **Status:** Plan, in Vorbereitung der Implementation. **Pending User-Freigabe der 4 offenen Fragen E-Q1..E-Q4.**
>
> **Parent-Plan:** [`phase_11_param_gui.md`](phase_11_param_gui.md)
> Stufe E — Sim-Tuning-Workshop + Best-Param-Presets +
> Tibia-Sim-Verifikation.
>
> **Vorbedingung:** Stage A + B + C + D abgeschlossen. Vollständige
> Param-Tuning-Infrastruktur vorhanden (gait_node Live-Params,
> Plugin-Cal, Diagnostic-Topic, Preset-Workflow).

---

## Ziel

Stage E ist anders strukturiert als A-D — **wenig Code, mehr Sim-Session
+ Doku**:

1. **Workshop-Doku** mit Test-Szenarien — User-Manual für sinnvolle
   Tuning-Sessions (welche Params drehen für welchen Walking-Stil)
2. **Best-Param-Preset-YAMLs** — 2-3 zusätzliche Presets in
   `src/hexapod_gait/config/presets/` (Stage D hat schon
   `defensive_walk.yaml` + `current_state.yaml`)
3. **Cross-Phase-Pendenz schließen:** Sim-Verifikation des Tibia-Length-
   Updates aus Phase 10 (Memory
   `project_phase10_tibia_length_sim_pending.md`)

**Was Stage E NICHT macht:**
- Keine neuen Code-Features (alle Live-Param-Surfaces sind aus A/B/C/D)
- Keine neuen Tests im Plugin/gait_node
- Keine Phase-13-Material (Pose-Management, echte Hardware)

---

## 🔍 Pre-Implementation Code/Doku-Inspection

### Was schon da ist (Stage D-Output)

**Preset-Verzeichnis** [`src/hexapod_gait/config/presets/`](../src/hexapod_gait/config/presets/):
- `README.md` (Format + Workflows)
- `defensive_walk.yaml` (cycle_time=4.0, step_length_max=0.03,
  step_height=0.025, body_height=-0.050)
- `current_state.yaml` (Stage-A-Defaults Snapshot)

**Setup-Doku** [`phase_11_rqt_setup.md`](phase_11_rqt_setup.md):
- Multi-Plugin-Layout
- 3 Save/Load-Workflows (Gait + Cal + lokale Perspective)
- rqt_plot-Limitation + Workarounds
- Bash-Aliases-Sektion
- Kompletter Cal-Session-Workflow

**Convenience-Tools** [`tools/hexapod-shell-aliases.sh`](../tools/hexapod-shell-aliases.sh):
- `hexapod-save-walking-params <name>` → dump + Redirect (Jazzy)
- `hexapod-load-walking-preset <name>` → launch mit params_file
- Plus Save-Cal, List-Presets, List-Cal-Backups

### Cross-Phase-Pendenz Tibia-Update

Memory `project_phase10_tibia_length_sim_pending.md`:
> 2026-05-17 wurde tibia_length 0.1787→0.200 m angepasst (real-gemessen,
> +21.3 mm). xacro+config.py+Doku synchron. Sim+RViz+Walking-Smoke
> laut `feedback_urdf_refactor_full_smoke.md` pending bei nächstem
> Sim-Touch.

Stage E IST der nächste Sim-Touch → ideal um diese Pendenz zu schließen.

### Was Mutter-Plan für Stage E vorsah

Aus [`phase_11_param_gui.md`](phase_11_param_gui.md):
> 1. Workshop-Doku mit 6 Test-Szenarien (langsamer/schneller Walk,
>    Drehen, Kurvenfahrt, body_height-Variationen, Single-Leg-Debug)
> 2. 3 Best-Param-Preset-YAMLs (`defensive_walk` ← schon da,
>    `demo_walk`, `aggressive_walk`)
> 3. Tibia-Sim-Verifikation

---

## ⚠️ Kritische Punkte (Self-Review vor Code-Beginn)

### 1. „Best-Presets" ohne echtes Tuning sind Spekulation

Stage D's `defensive_walk.yaml` war eine ehrliche „konservative
Auswahl" — wir wissen nicht ob die Werte optimal sind. Bei `demo_walk`
und insbesondere `aggressive_walk` ist das Risiko größer: wenn wir
Werte ohne echte Sim-Tests committen, sind das nur Vorschläge.

**Empfehlung:** Stage E-User-Smoke MUSS jedes neue Preset mindestens
einmal in der Sim laufen lassen — kein Commit ohne Live-Beleg dass
der Roboter mit den Werten nicht kippt/zittert.

### 2. Workshop-Doku ↔ Preset-Files Konsistenz

Wenn die Workshop-Doku z.B. `cycle_time=1.0` für „aggressive_walk"
empfiehlt, MUSS `aggressive_walk.yaml` exakt das enthalten. Drift bei
späteren Param-Tweaks ist Risiko.

**Empfehlung:** Workshop-Doku referenziert die Preset-Files namentlich,
zeigt nicht die einzelnen Werte (= Single Source of Truth in YAML).

### 3. Tibia-Verifikation in Sim — was genau prüfen?

Tibia-Länge in URDF wurde von 0.1787 auf 0.200 m geändert. Was zu
verifizieren:
- Sim startet ohne URDF-Parse-Error
- RViz zeigt Robot mit visuell-korrekt-langen-Tibias
- Walking-Smoke (z.B. `defensive_walk`-Preset): Roboter läuft ohne
  Bein-Kollision, IK liefert keine OutOfReach-Errors
- Default-Stand-Pose ist physisch sinnvoll (Beine nicht abnormal weit
  gestreckt oder geknickt)

**Empfehlung:** Stage E-User-Smoke E-T4 macht genau diese 4 Punkte als
Sub-Checks. Memory-Eintrag schließen wenn alle ✅.

### 4. Aggressive-Walk-Sicherheit

`aggressive_walk` mit cycle_time=1.0 + step_length_max=0.08 +
step_height=0.04 — User-Vorschau:
- linear_max = step_length_max / stance_duration = 0.08 / (1.0 * 0.5)
  = 0.16 m/s (Faktor 3 gegenüber default 0.05 m/s)
- IK kann bei step_length_max=0.08 + ggf. body_height-Drift
  out-of-reach laufen

**Empfehlung:** vor Commit in Sim verifizieren dass IK nicht throwt.
Bei IK-Fail Werte konservativer wählen (z.B. step_length_max=0.06).

### 5. Single-Leg-Debug-Preset — wirklich Stage E?

Single-Leg-Walking ist ein Debug-Tool — wird User in Phase 13 sowieso
für Bench-Tests brauchen, wenn er pro Bein die Cal verifiziert. Aber:
heute hat noch niemand das in der Sim getestet.

**Optionen:** siehe E-Q1.

---

## Offene Fragen für User-Review (E-Q1..E-Q4)

### E-Q1 — Welche Presets sollen in Stage E entstehen?

Aktuell vorhanden (Stage D): `defensive_walk.yaml`, `current_state.yaml`.

| Option | Was kommt dazu | Tradeoff |
|---|---|---|
| **A** | `demo_walk.yaml` + `aggressive_walk.yaml` (Mutter-Plan-Default) | 2 zusätzliche Presets, klare Spannweite langsam-mittel-schnell; aggressive_walk muss in Sim verifiziert werden (IK-Risk) |
| **B** | Nur `demo_walk.yaml` | 1 zusätzliches Preset, minimaler Drift-Risiko, aggressive auf Phase 13 verschoben wenn echte HW da ist |
| **C** | `demo_walk.yaml` + `aggressive_walk.yaml` + `single_leg_3_test.yaml` | 3 zusätzliche Presets inkl. Debug-Tool, Demo-Material reicher; höherer Maintenance-Aufwand |
| **D** | Nur `current_state.yaml` neu dumpen (nach Sim-Session) | minimaler Stage-E-Scope, nur Pendenz erledigen; keine zusätzlichen Preset-Files |

**Empfehlung: A** — matched Mutter-Plan, Spannweite reicht für
Demo + Phase-13-Vorbereitung, single_leg passt thematisch besser in
Phase 13 wo echtes Bench-Debug ansteht.

### E-Q2 — Workshop-Doku-Detailtiefe?

Workshop-Doku in `docs_raspi/phase_11_sim_tuning_workshop.md`:

| Option | Inhalt pro Szenario | Tradeoff |
|---|---|---|
| **A** | Param-Kombi (verweist auf Preset-Files) + erwartete Beobachtung in Worten („Roboter läuft sichtbar schneller, größere Schritte") | balanciert, User versteht warum Werte gewählt sind ohne Schreibflut |
| **B** | + numerische Metriken (Stop-Latenz aus cmd_vel=0, linear_max-Berechnung, Cycle-Frequenz) | präziser, gut für späteren Regression-Vergleich; mehr Schreibaufwand + möglicherweise out-of-date |
| **C** | + Screenshots von Sim/RViz (z.B. seitliche Walking-Ansicht) | visuell ansprechend für Workshop-Demo; Screenshots veralten wenn URDF/Sim sich ändert |
| **D** | Minimal — nur Tabelle „Preset → was es tut" ohne ausführliche Erklärungen | weniger Doku zu pflegen; aber User-Mehrwert niedrig (Preset-Files haben eh README) |

**Empfehlung: A** — pragmatischer Default. Option B/C als Phase-13-
Polish wenn echte HW-Daten + Demo-Videos anstehen.

### E-Q3 — Tibia-Sim-Verifikation: jetzt mit Stage E oder separat?

| Option | Wann | Tradeoff |
|---|---|---|
| **A** | Jetzt in Stage E (= Memory-Pendenz schließen, User-Smoke E-T4 ist die Verifikation) | Sim läuft sowieso für Workshop-Presets, marginaler Mehraufwand; Memory wird aktuell |
| **B** | Separat als Mini-Aufgabe nach Phase 11 (eigener Plan-Doc oder Phase-13-Bonus) | Stage E bleibt fokussiert auf Workshop-Doku; Memory bleibt offen |

**Empfehlung: A** — Stage E ist eine Sim-Session, Tibia mit-verifizieren
kostet 5 Min extra, Memory wird sauber geschlossen.

### E-Q4 — Wie ausführlich ist der User-Smoke der neuen Presets?

User-Smoke prüft pro Preset:

| Option | Was User testet | Tradeoff |
|---|---|---|
| **A** | Jeden Preset einmal Laden + walking via cmd_vel pub für ~10 s + visuelle Bestätigung „läuft wie beschrieben in Workshop-Doku" | gründlich, ~5-10 min User-Aktion pro Preset; deckt IK-Out-of-Reach-Risiko von aggressive_walk ab |
| **B** | Nur einen Preset (z.B. demo_walk) ausführlich, andere nur Smoke „Preset-File ladbar" | weniger User-Aufwand, aber aggressive_walk wäre nicht in Sim verifiziert (Commit-Risk) |
| **C** | Visual-only (RViz, kein walking) — nur Stand-Pose-Check | ~2 min pro Preset, aber kein Walking-Bug-Catching |

**Empfehlung: A** — `aggressive_walk` muss in Sim verifiziert werden
(siehe Kritischer Punkt 4 oben). User-Aufwand ist überschaubar (15-30 min
total für 2-3 Presets).

---

## Logik-Skizze

### E.0 — Vorbereitung

Plan-Doku (diese Datei) + User-Freigabe der E-Q1..E-Q4.
test_commands.md Skelett. Build-Status grün (Stage-D-Stand:
hexapod_gait 20/0/1, hexapod_bringup 18/0/0, hexapod_hardware 220/0/20).

### E.1 — Workshop-Doku-Skelett (~30 min)

Neue Datei `docs_raspi/phase_11_sim_tuning_workshop.md` mit Sektionen
für 6 Test-Szenarien:

1. **Langsamer Vorwärts-Walk** — `defensive_walk.yaml`
2. **Mittel-schneller Vorwärts-Walk** — `demo_walk.yaml` (neu)
3. **Schneller Vorwärts-Walk** — `aggressive_walk.yaml` (neu, falls
   E-Q1=A oder C)
4. **Drehen auf der Stelle** — Default-Preset + `angular.z`-cmd_vel
5. **Kurvenfahrt** — Default-Preset + kombiniertes `linear.x` +
   `angular.z`
6. **body_height-Variation** — `defensive_walk` + Live-Slider auf
   body_height
7. (optional, falls E-Q1=C) **Single-Leg-Debug** —
   `single_leg_3_test.yaml`

Pro Szenario:
- Sim-Setup (Launch-Befehle)
- Cmd_vel-Pub-Beispiele
- Erwartetes Verhalten in Worten (E-Q2 Option A)
- Verweis auf zugehörige Preset-Files

### E.2 — Best-Preset-YAMLs erzeugen (~30 min — Sim-Session-abhängig)

Pro neuen Preset (E-Q1-abhängig):

**`demo_walk.yaml`** — manuell konfiguriert, mittel-schneller Walk
- cycle_time=2.0 (Default)
- step_length_max=0.05 (Default)
- step_height=0.035 (etwas höher als Default)
- body_height=-0.052 (Default)

**`aggressive_walk.yaml`** — manuell konfiguriert + Sim-verifiziert
- cycle_time=1.5 (statt Default 2.0 — schneller)
- step_length_max=0.06 (statt 0.05 — größere Schritte, aber konservativ
  gewählt um IK-OutOfReach zu vermeiden)
- step_height=0.04 (höher für visuell-aktiveres Walking)
- body_height=-0.055 (etwas tiefer, mehr Stabilität bei höherem Tempo)

**Optional `single_leg_3_test.yaml`** (E-Q1=C):
- gait_pattern=single_leg_3
- cycle_time=4.0 (langsam, gut zum Beobachten)
- step_length_max=0.02
- step_height=0.025

### E.3 — Workshop-Doku ausfüllen mit echten Sim-Beobachtungen (~1 h)

User-Session: jedes neue Preset in Sim laufen lassen, beobachten,
Doku entsprechend befüllen. Bei IK-Errors oder visuell schlechtem
Verhalten: Preset-Werte konservativer (siehe Kritischer Punkt 4).

### E.4 — Tibia-Sim-Verifikation (~15 min)

User-Smoke E-T4:
1. Sim starten: `ros2 launch hexapod_bringup sim.launch.py`
2. RViz prüfen: tibias visuell ~20 cm lang (statt vorher ~17.9 cm)
3. Stand-Pose-Check: keine abnormale Bein-Geometrie
4. Walking-Smoke: `defensive_walk`-Preset laden, cmd_vel publishen,
   ~10 s laufen lassen → kein IK-Error, kein Kippen
5. Memory-Eintrag `project_phase10_tibia_length_sim_pending.md`
   löschen oder als „erledigt"-markieren

### E.5 — README-Updates

- `src/hexapod_gait/config/presets/README.md`: Tabelle „Aktuelle
  Presets" um demo_walk + aggressive_walk erweitern
- `src/hexapod_gait/README.md`: Phase-11-Block um Workshop-Doku-
  Verweis erweitern

### E.6 — Build + Regression (~10 min)

- `colcon build --packages-select hexapod_gait`
- `colcon test`: hexapod_gait 20/0/1 + presets im install-tree

### E.7 — Self-Review-Tabelle

CLAUDE.md §4-Pflicht.

### E.8 — Stage-E-Notizen + Übergang Stage F

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| E-T1 | `colcon build --packages-select hexapod_gait` | grün | Claude |
| E-T2 | `colcon test`: hexapod_gait 20/0/1 + new presets im install-tree | grün, neue Preset-YAMLs unter `install/hexapod_gait/share/hexapod_gait/config/presets/` | Claude |
| E-T3 (User) | jeden neuen Preset laden + ~10 s walking via cmd_vel → läuft visuell wie in Workshop-Doku beschrieben (kein IK-Error, kein Kippen) | User |
| E-T4 (User) | Tibia-Sim-Verifikation: RViz-Tibia-Länge ~20 cm + Stand-Pose-Check + Walking-Smoke | User |
| E-T5 (User, falls E-Q1=C) | `single_leg_3_test.yaml` lädt + cmd_vel → nur leg_3 schwingt | User |

### Was bewusst NICHT in Stage E getestet wird

- **Echte HW-Bench-Verifikation der Presets** (Phase 13)
- **Initial/Stand/Shutdown-Posen** (Phase 13)
- **Performance-Profiling** (CPU/Memory) der verschiedenen Presets
- **Auto-Tuning** (z.B. Bayesian-Optimierung über Parameter-Raum)

---

## Progress-Checkliste

- [ ] E.1 phase_11_stage_e_plan.md (diese Datei) finalisiert + User-Freigabe der E-Q1..E-Q4
- [ ] E.2 phase_11_stage_e_test_commands.md Skelett
- [ ] E.3 Workshop-Doku `docs_raspi/phase_11_sim_tuning_workshop.md` mit 6-7 Test-Szenarien
- [ ] E.4 `demo_walk.yaml` committet + in Sim verifiziert
- [ ] E.5 `aggressive_walk.yaml` committet + in Sim verifiziert (falls E-Q1=A oder C)
- [ ] E.6 `single_leg_3_test.yaml` committet (falls E-Q1=C)
- [ ] E.7 Tibia-Sim-Verifikation durchgeführt + Memory-Eintrag `project_phase10_tibia_length_sim_pending.md` geschlossen
- [ ] E.8 README hexapod_gait + presets/README.md updaten
- [ ] E.9 colcon build + Regression grün
- [ ] E.10 User-Smoke E-T3..E-T4 (+E-T5 falls E-Q1=C)
- [ ] E.11 Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] E.12 Stage-E-Notizen + Übergang Stage F (Phase-11-Abschluss)

**Done-Kriterium E:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke E-T3..E-T4 bestätigt, Tibia-Memory-Pendenz geschlossen.

---

## Erwartete Stage-E-Dauer

- E.0 Plan-Doku (diese Datei): ~30 min Claude (in Arbeit)
- E.1-E.2 Test-Doku + Workshop-Skelett: ~45 min Claude
- E.3 Preset-YAMLs anlegen: ~15 min Claude
- E.4 Sim-Sessions + Workshop-Doku ausfüllen: ~1 h User + Claude (User-Smoke parallel)
- E.5 Tibia-Sim-Verifikation: ~15 min User
- E.6 README-Updates: ~15 min Claude
- E.7-E.8 Build + Regression: ~10 min Claude
- E.9 Self-Review + Notes: ~15 min Claude

**Schätzung:** ~2.5 h Claude + 1.5 h User = **~0.5 d Gesamt** (matched
Mutter-Plan).

---

## Bewusst NICHT in Stage E

- **Auto-Tuning-Tool** — wäre interessant aber Phase-13+-Polish
- **Headless-Sim-Benchmark** (CI-Performance-Vergleich der Presets) —
  nice-to-have, kein Done-Kriterium
- **PS4-Controller-Mapping** der Presets („Knopf X = aggressive_walk") —
  Phase-13-Material
- **Initial/Stand/Shutdown-Posen** — Phase-13-Material
- **Echte Hardware-Verifikation der Presets** — Phase 13
