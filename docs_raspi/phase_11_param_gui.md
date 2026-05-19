# Phase 11 — Param-GUI mit Live-Tuning (rqt_reconfigure)

**Dauer-Schätzung:** ~4.5 d (Stages A-F)
**Maschine:** Desktop (Sim + HW parallel)
**Vorbedingung:** Phase 10 abgeschlossen (leg_6 voll kalibriert, IK +
gait_node-Walking verifiziert, alle 3 Hardware-Sicherheits-Schichten aktiv).
**Phase-Renumbering 2026-05-19:** vorherige Phase 11 (Pi-Plattform) ist
jetzt Phase 12; vorherige Phase 12 (Voll-Bringup) ist jetzt Phase 13.

> **Hinweis zur Entstehung:** Diese Phase entstand auf User-Wunsch nach
> Phase 10. Während des Stage-F-Walking-Tests wurde klar, dass mit
> Hardcoded-Params bei jeder Anpassung der Walking-Parameter eine
> Build-Edit-Build-Iteration nötig wäre (analog wie bei direction-Flips
> in Stages C/D). Eine Live-GUI für Param-Tuning macht das wesentlich
> schneller und erlaubt explorative Sim+HW-Sessions ohne Code-Edits.

---

## Ziel

ROS-Standard-Tool **`rqt_reconfigure`** mit den relevanten Hexapod-
Parametern aufstellen, damit User in Sim **und** Real-HW alle wichtigen
Walking-/Cal-Werte **live per Slider** verändern kann. Plus
ergänzende `rqt_plot`-/`rqt_topic`-Setup für Topic-Daten-Visualisierung.

### Was die GUI können soll (User-Wünsche aus Diskussion)

| Parameter | Wo lebt der? | Live-Effekt |
|---|---|---|
| **Schrittweite** (`step_length_max`) | gait_node | Walking-Stride größer/kleiner |
| **Schritthöhe** (`step_height`) | gait_node | Foot-Hub höher/niedriger |
| **Cycle-Granularität** (`tick_rate`, `cycle_time`) | gait_node | Walking-Geschwindigkeit + Auflösung |
| **Hexapod-Höhe** (`body_height`) | gait_node | Body über Boden, Live-Anpassbar |
| **Bein-Reach** (`radial_distance`) | gait_node | Füße näher/weiter weg vom Body |
| **Walking-Geschwindigkeit** (`linear.x`, `angular.z` via cmd_vel) | Topic-Publisher | Body-Geschwindigkeit |
| **Servo-Kalibrierung** (`pulse_min/zero/max/direction`) | hexapod_hardware Plugin | Live-Cal pro Servo |
| **Diagnostic** (Pulse-µs anzeigen) | hexapod_hardware Plugin → neuer Topic `/servo_pulses` | Visualisierung was an Servos rausgeht |

---

## Architektur-Entscheidungen

### A. Tool-Wahl: rqt_reconfigure (Standard ROS-GUI)

**Final:** `rqt_reconfigure` als zentrales GUI plus `rqt_plot` +
`rqt_topic` für Topic-Daten parallel in einem rqt-Fenster.

**Verworfen:**

- **Custom rqt-Plugin** (Punkt 2 aus Diskussion) — schöneres Layout
  möglich, aber ~3-5 Tage Mehraufwand. Für „Slider mit Namen"-User-Wunsch
  reicht rqt_reconfigure völlig.
- **RViz Custom Panel** — Aufwand ähnlich rqt-Plugin, aber komplexere
  Plugin-API. rqt parallel zu RViz/Gazebo ist pragmatisch.
- **Gazebo GUI Plugin** — Gazebo-Plugins sind für Sim-Verhalten, nicht
  für ROS-Param-Tuning UIs designed.
- **Standalone PyQt-App** — kein ROS-Standard, verlässt rqt-Ökosystem
- **Foxglove Studio** — modernes Tool, aber externe Dependency. Auch
  für Phase-13+-Polish wenn Handy-Zugriff gewünscht ist.
- **Web-App + rosbridge** — Aufwand für Handy-Zugriff. Phase-13+-Kandidat.

### B. Save/Load-Workflow für gute Param-Sets

**Final:** Kombination aus

1. **`ros2 param dump /gait_node --output-dir ...`** — Standard-CLI um
   aktuelle Live-Werte als YAML zu exportieren
2. **`params_file:=<yaml>` Launch-Arg** in `gait.launch.py`,
   `real.launch.py`, `sim.launch.py` — um gespeicherte Presets zu laden
3. **Preset-YAMLs** in `src/hexapod_gait/config/presets/` — committet
   ins Repo, dokumentiert

**Workflow:**

```bash
# Tuning-Session
ros2 launch hexapod_bringup sim.launch.py    # oder real.launch.py
ros2 run rqt_reconfigure rqt_reconfigure
# ... mit Slidern spielen ...

# Speichern
ros2 param dump /gait_node --output-dir src/hexapod_gait/config/presets/
mv src/hexapod_gait/config/presets/gait_node.yaml \
   src/hexapod_gait/config/presets/my_walking_preset.yaml

# Beim nächsten Start laden
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/my_walking_preset.yaml
```

**Verworfen:** GUI-Save-Button in Custom Plugin — würde Custom Plugin
erfordern, das wurde abgelehnt.

### C. Echo-State-Realität (aus Phase-10-Stage-G übernommen)

Plugin liefert kein echtes Position-Feedback (`current_state ==
command_state` immer). Daher:

- **JTC-Toleranz-Constraints** (goal_position_tolerance, trajectory)
  bleiben **faktisch wertlos** in unserem System
- **Vel/Accel-Limits via YAML-Override** könnten Sinn ergeben (echter
  Effekt auf Trajectory-Spline) — werden in Phase 11 als Param via
  rqt_reconfigure live tunbar, aber nicht zwingend in `controllers.real.yaml`
  fest eintragen
- **Hardware-Sicherheits-Schichten** bleiben primär: URDF-Vel-Cap +
  Pulse-Clamp + Position-Limits

### D. Plugin-Live-Cal: Pulse-Werte als Diagnostic-Topic

**Final:** hexapod_hardware Plugin um Topic `/servo_pulses`
(`std_msgs/Int32MultiArray` oder Custom-Message) erweitern, das die
18 Pulse-µs-Werte aus `SET_TARGETS` als ROS-Topic publisht.

**Vorteil:**

- Visualisierung in `rqt_plot` was an Servos rausgeht
- Bei Live-Cal-Slider-Änderung von `pulse_min/zero/max`: sofortige
  Pulse-Antwort sichtbar
- Phase-13-Voll-Bringup kann das auch für Strom-Profil-Auswertung nutzen

**Verworfen:**

- **Plugin-Log-only** — derzeit nur internal log, nicht ROS-Topic.
  Slider-Live-Effekt nicht visualisierbar.
- **Externer Konverter-Node** — würde rad → pulse-Math doppeln (Plugin
  hat sie schon)
- **Foxglove-Custom-Panel** — externe Tool-Dependency

---

## Hardware-Setup für diese Phase

Phase 11 ist primär Sim + optional HW:

- **Sim-only-Pfad:** Desktop mit Gazebo + RViz + rqt — kein Bench, keine
  Servos
- **Mit-HW-Pfad:** Sim PLUS leg_6 am Bench (PSU 7.0 V / 8 A, alle 3
  Servos Pin 15/16/17), Plugin im real-Modus

Beide Pfade nutzen die gleiche GUI. Live-Effekt in Sim und HW
parallel sichtbar = sehr eindrücklich.

---

## Done-Kriterien Phase 11

1. **gait_node Param-Callback** für alle relevanten gait-Params (Stage A)
2. **hexapod_hardware Plugin Param-Callback** für pulse_min/zero/max/direction
   pro Pin (Stage B)
3. **`/servo_pulses` Diagnostic-Topic** publiziert (Stage C)
4. **rqt-Setup-Doku + Save/Load-Workflow** (Stage D):
   - Multi-Plugin-Layout (rqt_reconfigure + rqt_plot + rqt_topic)
   - `params_file`-Arg in gait.launch.py / real.launch.py / sim.launch.py
   - `ros2 param dump`-Workflow dokumentiert
   - Bash-Alias als optional Bonus
5. **Sim-Tuning-Workshop-Doku** mit Test-Szenarien + Best-Param-Preset-YAMLs
   (Stage E)
6. **CI weiterhin grün:** hexapod_gait (Tests anpassen falls nötig),
   hexapod_hardware 208/0/20, hexapod_bringup 18/0/0

---

## Stages

### Stage A — gait_node Param-Callback (~1 d)

**Ziel:** alle gait_node-Parameter (siehe Liste in „Was die GUI können soll")
mit `on_set_parameters_callback` ausstatten, damit Live-Updates via
`ros2 param set` (und damit rqt_reconfigure) wirksam werden.

**Vorbedingung:** Phase 10 grün, gait_node-Code aktuell.

**Schritte:**

1. `gait_node.py` (oder C++-Pendant) `on_set_parameters_callback` registrieren
2. Pro Parameter `ParameterDescriptor` mit Range (min/max) + Default
3. Param-Callback updated den Live-State des Nodes:
   - `body_height` → Stand-Pose neu berechnen, sanft anfahren
   - `step_height` → nächster Swing nutzt neuen Wert
   - `cycle_time` → nächster Cycle nutzt neue Periode
   - `tick_rate` → Timer neu starten mit neuer Frequenz
   - etc.
4. Edge-Cases: was passiert wenn z.B. cycle_time während WALKING-State
   geändert wird? → sauber an Phase-Grenze umschalten
5. Test: `ros2 param set /gait_node body_height -0.060` → Sim-Hexapod
   reagiert live
6. Test: rqt_reconfigure öffnen, Slider verschieben → Live-Update
7. Unit-Tests für Param-Validation
8. launch_testing-Smoke-Test mit live-Param-Updates

**Done-Kriterium A:**

- Alle relevanten Params haben Callback + Range
- `ros2 param set` ändert Live-Verhalten in Sim
- `rqt_reconfigure` zeigt Slider, Live-Update funktioniert
- Tests grün

### Stage B — hexapod_hardware Plugin Live-Cal Param-Callback (~1 d)

**Ziel:** Plugin um Param-Callback für `pulse_min/zero/max/direction`
pro Pin erweitern → Live-Servo-Cal via rqt_reconfigure.

**Schritte:**

1. Plugin `on_set_parameters_callback` (C++) registrieren
2. Pro Pin (0–17) Params deklarieren:
   `pin_15_pulse_min`, `pin_15_pulse_zero`, `pin_15_pulse_max`,
   `pin_15_direction`, ... (18 × 4 = 72 Params)
3. ODER alternativ: ein Param-Namespace pro Pin, z.B. `pin_15.pulse_min`
4. Param-Callback updated die Calibration-Lookup-Tabelle live
5. Validation: pulse_min < pulse_zero < pulse_max, alle in [800, 2200] µs,
   direction in {-1, +1}
6. **YAML-Save-Funktion:** Helper-Service `/save_calibration` der die
   aktuellen Live-Werte zurück in `servo_mapping.yaml` schreibt (für
   Persistenz nach Tuning-Session)
7. Test: Slider ändert pulse_zero, Servo bewegt sich entsprechend
   (echtes Bein, nicht nur Echo)

**Done-Kriterium B:**

- Plugin akzeptiert Live-Param-Updates für Cal-Werte
- Slider-Änderung wirkt auf nächsten `SET_TARGETS`-Frame
- Save-Service schreibt YAML zurück
- Tests grün

### Stage C — Diagnostic-Topic `/servo_pulses` (~0.5 d)

**Ziel:** Plugin publiziert aktuelle Pulse-Werte als ROS-Topic für
Visualisierung in rqt_plot.

**Schritte:**

1. Plugin publisht in `write()` (= jedem Tick) ein Topic
   `/servo_pulses` mit den 18 µs-Werten
2. Topic-Typ: `std_msgs/Int32MultiArray` (einfach) oder Custom-Message
   `HexapodPulses` (sauberer, mit Timestamp + per-Pin-Namen)
3. Default-Rate: 50 Hz (matched controller_manager update_rate)
4. Tests: Topic existiert, Werte passen zu Joint-Positionen via Cal-Math

**Done-Kriterium C:**

- `/servo_pulses` Topic publiziert
- `rqt_plot /servo_pulses/data[15]` zeigt Pin-15-Pulse live
- Tests grün

### Stage D — rqt-Setup-Doku + Save/Load-Workflow (~1 d)

**Ziel:** komplette User-Anleitung wie man rqt nutzt + Preset-Workflow.

**Schritte:**

1. **Launch-File-Erweiterung:** `gait.launch.py`, `real.launch.py`,
   `sim.launch.py` um optionalen `params_file`-Arg erweitern
   (Standard-ROS-Pattern via `ParametersFile`)
2. **Preset-Verzeichnis** anlegen: `src/hexapod_gait/config/presets/`
   mit `README.md` der das Format erklärt
3. **rqt-Setup-Doku** (`docs_raspi/phase_11_rqt_setup.md`):
   - Multi-Plugin-Layout (Perspectives speichern)
   - Welche Plugins anhängen (Reconfigure, Plot, Topic)
   - Welche Topics in rqt_plot interessant sind
   - Tastatur-Shortcuts
   - **Save-Workflow:** `ros2 param dump` als Command + Bash-Alias-Vorschlag
   - **Load-Workflow:** params_file-Arg-Beispiele
4. **Bash-Alias-Datei** (optional): `tools/hexapod-shell-aliases.sh`
   mit `hexapod-save-walking-params`, `hexapod-load-preset`, etc.

**Done-Kriterium D:**

- params_file-Arg in 3 Launch-Files funktional
- Preset-Verzeichnis mit README
- rqt-Setup-Doku komplett
- Bash-Aliases dokumentiert (optional)

### Stage E — Sim-Tuning-Workshop-Doku + Best-Param-Presets (~0.5 d)

**Ziel:** Sammlung von Test-Szenarien und besten Param-Sets.

**Schritte:**

1. **Workshop-Doku** (`docs_raspi/phase_11_sim_tuning_workshop.md`):
   - Test-Szenario: „langsamer Vorwärts-Walk" (Defensiv-Default)
   - Test-Szenario: „schneller Vorwärts" (Maximum-Stride)
   - Test-Szenario: „Drehen auf der Stelle"
   - Test-Szenario: „Kurvenfahrt"
   - Test-Szenario: „tief gehen / hoch gehen" (body_height)
   - Test-Szenario: „Single-Leg" (debug)
   - Pro Szenario: Param-Kombi + erwartetes Verhalten + Beobachtungen
2. **Best-Param-Preset-YAMLs** in `src/hexapod_gait/config/presets/`:
   - `defensive_walk.yaml` (langsam, konservativ)
   - `demo_walk.yaml` (mittel-schnell, sichtbar)
   - `aggressive_walk.yaml` (Max-Speed, Phase-13-Vorbereitung)
   - **Plus Cross-Phase-Pendenz:** Sim-Verifikation des Tibia-Updates
     aus Phase 10 erledigen (Memory `project_phase10_tibia_length_sim_pending.md`)

**Done-Kriterium E:**

- Workshop-Doku mit min. 5 Test-Szenarien
- 2-3 Preset-YAMLs committed
- Sim-Verifikation Tibia-Update durchgeführt + Memory-Eintrag schließen

### Stage F — Phase-11-Abschluss (~0.5 d)

- `phase_11_progress.md` finalisieren mit Retrospektive
- README hexapod_gait + hexapod_hardware um Phase-11-Quick-Start
- PHASE.md: Phase 11 → 🟢, Phase 12 → 🟡 aktiv
- Git-Commit + Tag `phase-11-done` (durch User)

---

## Was in Phase 11 **NICHT** gemacht wird (deferred)

- **Custom rqt-Plugin** mit aggregierter UI (Phase 13+ falls gewünscht)
- **PS4-Controller-Erweiterung** für gait-Params (Phase 13+)
- **Foxglove Studio-Panel** für Handy-Zugriff (Phase 13+)
- **Pi-Plattform-Setup** — das ist Phase 12
- **Voll-Bringup mit echtem Roboter** — Phase 13
- **18-Servo-Kalibrierung** — Phase 13 Stufe B (Auto-Cal-Tool)

---

## Stolperfallen

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| rqt_reconfigure zeigt keine Slider, nur Textfelder | Param-Descriptor ohne Range deklariert | `ParameterDescriptor` mit `floating_point_range` ergänzen |
| Slider-Wert wird nicht übernommen | `on_set_parameters_callback` nicht registriert oder gibt `SetParametersResult(successful=False)` zurück | Callback-Logik prüfen, Validation-Reason loggen |
| Slider-Wert übernommen aber Verhalten ändert sich nicht | Param-Callback updated nicht den internen State | Callback muss interne Variablen + Timer/State neu setzen |
| `ros2 param dump` exportiert keine Range | Params ohne Descriptor deklariert | siehe oben |
| params_file-Arg lädt nicht | Launch-File-Code falsch (nicht alle Params überschreibbar) | Pattern aus ros2_control ableiten |
| Plugin-Param-Callback bricht JTC | Live-Update von pulse_min/max ändert die Kalibrierung während Trajectory läuft | Callback nur in idle-State akzeptieren oder atomic-Update |
| `/servo_pulses` zeigt veraltete Werte | Publisher-Rate zu langsam | auf 50 Hz erhöhen |

---

## Cross-Phase-Pendenzen die Phase 11 schließt

- `project_phase10_tibia_length_sim_pending.md` — Sim-Verifikation
  des Tibia-Updates (Stage E)

## Cross-Phase-Pendenzen die Phase 11 NICHT schließt (bleiben Phase 13)

- `project_phase10_real_yaml_vel_limits.md` — Vel/Accel mit Bench-Last
- `project_phase13_initial_pose_presets.md` — Initial-Pulse-Presets
- `project_phase9_h_oscilloscope_pending.md` — Oszi/Logic-Analyzer

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–E Done-Kriterien erfüllt
- [ ] CI weiterhin grün
- [ ] rqt_reconfigure funktional für gait_node + Plugin
- [ ] `/servo_pulses` Topic publiziert
- [ ] params_file-Arg in 3 Launch-Files
- [ ] Preset-Verzeichnis mit min. 2 YAMLs
- [ ] rqt-Setup-Doku + Sim-Tuning-Workshop-Doku
- [ ] Sim-Verifikation Tibia-Update (Memory-Eintrag schließen)
- [ ] Git-Commit + Tag `phase-11-done` (durch User)
- [ ] PHASE.md auf Phase 12 (Pi-Plattform) aktualisiert
- [ ] Retrospektive in `phase_11_progress.md`
