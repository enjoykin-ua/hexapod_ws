# Phase 11 — Stufe A — Plan

> **Status:** Plan, in Vorbereitung der Implementation.
>
> **Parent-Plan:** [`phase_11_param_gui.md`](phase_11_param_gui.md)
> Stufe A — gait_node Param-Callback für Live-Tuning.
>
> **Vorbedingung:** Phase 10 abgeschlossen, Phase-11-Mutter-Plan
> finalisiert + User-Freigabe.

---

## Ziel

`gait_node` so erweitern, dass **alle relevanten Walking-Parameter live
per `ros2 param set` änderbar** sind. Damit funktioniert
`rqt_reconfigure` als Standard-GUI für gait-Tuning ohne Restart.

**Was geht aktuell schon:** Params werden in `gait.launch.py` als
`LaunchConfiguration` deklariert und an gait_node beim Start übergeben.
Sie sind über `ros2 param get /gait_node body_height` abfragbar.

**Was geht NICHT:** `ros2 param set /gait_node body_height -0.060` setzt
zwar den Param-Wert, aber das Node-interne Verhalten ändert sich nicht —
die `body_height`-Variable wird nur in `on_init` gelesen, nicht im
laufenden Cycle.

**Was Stage A liefert:** `on_set_parameters_callback` der bei Live-Update
den internen State aktualisiert.

---

## 🔍 Pre-Implementation Code-Inspection (für nächste Session)

> **Wichtig für Continuity** (z.B. Chat-Reset): bevor Code-Edit anfängt,
> diese Files lesen damit Stage A nicht erfindet was schon existiert.

### Existierende gait_node-Struktur (Stand 2026-05-19)

**File:** `src/hexapod_gait/hexapod_gait/gait_node.py` (~277 Zeilen)

- **14 Parameter** schon deklariert in `__init__` (line 44-57):
  `gait_pattern`, `step_height`, `cycle_time`, `tick_rate`, `body_height`,
  `radial_distance`, `time_from_start_factor`, `step_length_max`,
  `default_linear_x/y`, `default_angular_z`, `cmd_vel_timeout`,
  `body_height_min`, `body_height_max` — **plus `use_sim_time`**
  von rclpy automatisch
- **Member-Variablen** als `self._<param_name>` gesetzt (line 67-90)
- **State-Machine** lebt in `GaitEngine` (line 101) — eigenes Objekt,
  hat `state` Property mit `STATE_STANDING` / `STATE_WALKING` etc.
- **Timer** mit `self._timer = self.create_timer(1.0 / self._tick_rate, self._tick)`
  (line 134) — bei `tick_rate`-Update muss Timer destroyed + neu erstellt werden
- **GAIT_PRESETS** in `hexapod_gait/gait_patterns.py` — Dict
  mit Pattern-Konfig pro Pattern-Name
- **Engine-Init** mit `self._pattern = GAIT_PRESETS[pattern_name]` (line 65)
  + `self._engine = GaitEngine(pattern=self._pattern, ...)` —
  Pattern-Wechsel braucht Engine-Reset oder Pattern-Swap-Methode

### Bestehende Live-Update-Patterns (= Vorbild)

**`/cmd_body_height` Topic-Handler** (line 159-188) zeigt **wie
body_height live geändert wird**:

- **Sicherheits-Constraint:** nur in `STATE_STANDING` akzeptieren
  (Body-Pose-Wechsel mitten im Walk-Cycle würde Roboter zum Kippen
  bringen, line 168-171)
- **Clamping:** auf `[body_height_min, body_height_max]`
- **Engine-Update:** `self._engine.body_height = clamped` (line 188)

**Implikation für Stage A:** der Param-Callback für `body_height` muss
**dasselbe Pattern** nutzen — nur in STANDING akzeptieren ODER
SetParametersResult(False) mit reason. Sonst inkonsistent zum
bestehenden Topic-Handler. **Empfehlung:** Param-Update lehnt
während WALKING ab (sauberer als silent-ignore).

### Existierende Tests

**File:** `src/hexapod_gait/test/`

- `test_copyright.py`, `test_flake8.py`, `test_pep257.py` — **Linter-Only**
- **KEINE Unit-Tests für gait_node selber existieren!**

**Implikation für Stage A:** wir führen die **ersten echten Unit-Tests**
für gait_node ein. Pattern aus hexapod_kinematics (`test_*.py` mit
pytest-Style) übernehmen.

---

## ⚠️ Kritische Punkte (Self-Review der Plan-Doku, vor Code-Beginn)

### 1. Threading / Race-Conditions

ROS2 Param-Callback läuft im Service-Thread, Timer-Callback (`_tick`)
im Timer-Thread. Beide können gleichzeitig auf `self._engine.body_height`,
`self._tick_rate`, etc. schreiben/lesen.

**Mitigation:**

- **Option A:** `MutuallyExclusiveCallbackGroup` für beide Callbacks
  → seriealisierte Ausführung, keine Races
- **Option B:** atomare Member-Updates (Python GIL hilft für simple
  Assignments, aber `self._engine = ...` oder Timer-Restart nicht atomic)
- **Empfehlung:** Option A. Plus: bei `_restart_timer()` zuerst
  `self._timer.cancel()` warten lassen, dann neuen erstellen.

### 2. `gait_pattern` mid-WALKING

**Problem:** Pattern-Wechsel während Roboter läuft = Beine wären
plötzlich in falscher Tripod-Phase → potentieller Kipp-Crash.

**Empfehlung:**

- Param-Callback **lehnt** `gait_pattern`-Update während WALKING ab
  (analog `cmd_body_height`)
- Nur in STANDING-State erlaubt
- User muss erst stoppen (`cmd_vel.linear.x = 0`), dann Pattern wechseln

Das ist **wichtige Anpassung** zu der ursprünglichen User-Antwort A-Q2
(gait_pattern live wechselbar) — die war zu optimistisch.

### 3. `tick_rate` Live-Update

**Problem:** Timer-Restart während aktivem Tick → Race-Condition,
verlorene Frames.

**Empfehlung:**

- Timer in STANDING-State neu erstellen (sicher)
- Während WALKING: ablehnen oder bis zum nächsten STANDING-State warten
- **Sichere Variante:** read-only während WALKING

### 4. `cycle_time` Live-Update

**Problem:** Engine berechnet Stride basierend auf `cycle_time`.
Wechsel mid-cycle würde Stride-Länge inkonsistent machen.

**Empfehlung:**

- Engine-Internal-Variable updaten, **nächster Cycle** nutzt neuen Wert
- aktueller Cycle läuft erst zu Ende
- Edge-Case: was wenn `cycle_time` von 4.0 auf 0.5 sinkt während aktivem
  4-Sekunden-Cycle? → Engine muss das sauber handeln

### 5. Cross-Param-Constraints (`body_height_min` vs. `body_height_max`)

**Problem:** wenn User `body_height_min` auf -0.030 setzt während
`body_height_max` noch bei -0.080 ist → min > max, ungültig.

**Empfehlung:**

- Pre-Validate: für **alle** Params in der Callback-Liste zusammen
  prüfen, nicht einzeln
- Bei Inkonsistenz: SetParametersResult(False) zurück, **keine** Updates
  durchführen (atomic-all-or-nothing)

### 6. `use_sim_time` als read-only

Clock-Mode-Wechsel zur Laufzeit ist tricky in rclpy. Stage A markiert
das als `read_only=true` im Descriptor.

### 7. Regression-Schutz für bestehenden `/cmd_body_height` Topic-Handler

Phase 6 hat den Topic-Handler getuned (PS4 L2/R2-Trigger). Stage A darf
das nicht brechen — beide Pfade (Topic + Param) sollten denselben
Effekt haben.

**Test-Empfehlung:** existierender PS4-Workflow (sim-only) sollte nach
Stage A weiter funktionieren.

### 8. rqt_reconfigure mit String-Param (`gait_pattern`)

`gait_pattern` ist string-typed. ROS2 ParameterDescriptor unterstützt
keine native Enum-Dropdown — rqt_reconfigure würde Text-Eingabe zeigen,
User muss exakt `tripod`, `single_leg_1`, etc. tippen.

**Workaround:** `additional_constraints` im Descriptor als Hinweis-Text
(„valid values: tripod | single_leg_1..6"). Plus: Validation lehnt
unbekannte Patterns ab.

### 9. Stage A muss in Sim laufen — Tibia-Update-Verifikation mitnehmen?

Stage A entwickelt + testet Param-Callback in **Sim** (Gazebo + RViz).
Das ist faktisch eine Sim-Session = passt zur Pendenz
`project_phase10_tibia_length_sim_pending.md`.

**Empfehlung:**

- **Stage A** kann den Sim-Smoke-Walk mit alter cmd_vel-Methodik abdecken
  → Tibia-Update verifiziert „nebenbei"
- **Stage E** macht es offiziell + Memory-Eintrag schließen
- → User-Sichtkontrolle in Stage A reicht für Konfidenz

---

## Strategie / Architektur-Entscheidungen

### A. Welche Parameter sollen live tunbar sein?

**Final:** alle Parameter aus `gait.launch.py` (~13 Args, siehe Tabelle
unten).

**Verworfen:** nur Subset — wäre inkonsistent, User könnte vergessen
welche Params live sind und welche nicht.

### B. Welche Params brauchen wieviel Reaktivität?

| Param | Live-Update wirkt | Erklärung |
|---|---|---|
| `body_height` | **nur in STANDING** (analog `cmd_body_height`-Topic-Handler) | in WALKING ablehnen mit SetParametersResult(False) — Kipp-Risiko |
| `radial_distance` | **nur in STANDING** | analog body_height, Stand-Pose-Reset |
| `step_height` | **sofort** (nächster Swing nutzt neuen Wert) | unkritisch |
| `step_length_max` | **sofort** (clampt cmd_vel im nächsten Cycle) | unkritisch |
| `default_linear_x/y/angular_z` | **sofort** | Fallback-Werte, keine Auswirkung auf aktive Trajectory |
| `cmd_vel_timeout` | **sofort** | nur Timer-Threshold-Vergleich |
| `body_height_min/max` | **atomic mit body_height** | Cross-Constraint, nur in STANDING ändern wenn body_height außerhalb käme |
| `cycle_time` | **nur in STANDING** | sonst Stride-Inkonsistenz mid-cycle |
| `tick_rate` | **nur in STANDING** (Timer-Restart-Risiko) | in WALKING ablehnen |
| `time_from_start_factor` | **sofort** | nur Lookahead-Math |
| `gait_pattern` | **nur in STANDING** (Engine-Reset-Risiko) | analog cmd_body_height |
| `use_sim_time` | **read_only=true** | Clock-Mode-Wechsel zur Laufzeit broken in rclpy |

### C. ParameterDescriptor mit Range

**Final:** jeder Param bekommt einen `ParameterDescriptor` mit:
- `description` (Erklär-Text)
- `floating_point_range` oder `integer_range` (Min/Max + Step) wo
  sinnvoll
- `read_only=true` für Params die nicht live änderbar sind
  (z.B. `use_sim_time`)

**Effekt:** rqt_reconfigure zeigt Slider mit klaren Bereichen.

### D. Validation in `on_set_parameters_callback`

Pro Param-Update prüfen:
- Wert im erlaubten Range (über Descriptor automatisch)
- Cross-Param-Constraints: z.B. `body_height` muss in
  `[body_height_min, body_height_max]` sein
- Bei Fehler: `SetParametersResult(successful=False, reason="...")`
  zurückgeben — rqt_reconfigure zeigt das als Error

### E. State-Update-Strategie

**Final:** Callback updated **interne Member-Variablen** des Nodes
**und** triggered Re-Berechnung wo nötig:

```python
def on_param_change(self, params):
    for p in params:
        if p.name == 'body_height':
            self._body_height = p.value
            self._recompute_stand_pose()  # sofortige Wirkung
        elif p.name == 'tick_rate':
            self._tick_rate = p.value
            self._restart_timer()  # Timer mit neuer Frequenz
        elif p.name == 'gait_pattern':
            self._gait_pattern_name = p.value
            self._load_gait_pattern()  # Pattern wechseln
        ...
    return SetParametersResult(successful=True)
```

---

## User-Antworten (vor Implementation — pending)

| # | Frage | Empfehlung |
|---|---|---|
| **A-Q1** Alle gait_node-Params live machen oder Subset? | **A** — alle 14 Params (gait_node deklariert die schon, siehe Inspection) | (B) nur Walking-Pose-Params |
| **A-Q2** `gait_pattern` live wechselbar während WALKING? | **B (geändert!)** — nur in STANDING erlaubt, in WALKING ablehnen (analog `cmd_body_height`-Topic-Handler line 168-171). Sicherer als ursprünglich vorgeschlagen | (A) Mid-WALKING-Wechsel mit Engine-Reset (kipp-Risiko) |
| **A-Q3** Validation bei Cross-Param-Constraints | **A** — atomic-all-or-nothing: alle Param-Updates zusammen validieren, bei Inkonsistenz ablehnen | (B) Wert clampen silently |
| **A-Q4** `use_sim_time` live tunbar? | **B** — `read_only=true` im Descriptor | (A) versuchen (riskant) |
| **A-Q5** Threading / Race-Conditions | **A** — `MutuallyExclusiveCallbackGroup` für Timer + Param-Callback | (B) Atomic-Member-Assignments (riskanter) |
| **A-Q6** `body_height`-Param-Update während WALKING | **A** — analog `/cmd_body_height`-Topic-Handler: nur in STANDING akzeptieren | (B) immer akzeptieren (Kipp-Risiko) |
| **A-Q7** `tick_rate` Live-Update während WALKING | **B** — nur in STANDING (Timer-Restart mid-Tick = Race-Condition) | (A) versuchen mit Timer-Cancel-Wait |
| **A-Q8** Tibia-Update-Sim-Verifikation in Stage A nebenbei? | **A** — User-Sichtkontrolle in Stage A reicht; offizielle Memory-Eintrag-Schließung in Stage E | (B) separat in Stage E erst |

---

## Logik-Skizze

### A.0 — Vorbereitung (~10 min)

Plan-Doku finalisiert (diese Datei), User-Freigabe, test_commands.md
Skelett. Build-Status grün bestätigt.

### A.1 — gait_node Param-Descriptors deklarieren (~2 h)

Im gait_node-Konstruktor:

```python
from rcl_interfaces.msg import ParameterDescriptor, FloatingPointRange, IntegerRange, ParameterType

# Beispiel body_height
body_height_descriptor = ParameterDescriptor(
    type=ParameterType.PARAMETER_DOUBLE,
    description='Stand-Pose Foot-Z im Bein-Frame (m). HW-Default -0.047, Sim -0.052.',
    floating_point_range=[FloatingPointRange(from_value=-0.100, to_value=-0.020, step=0.001)],
)
self.declare_parameter('body_height', -0.052, body_height_descriptor)

# ... analog für alle 13 Params
```

### A.2 — `on_set_parameters_callback` registrieren (~1 h)

```python
self.add_on_set_parameters_callback(self._on_param_change)

def _on_param_change(self, params):
    """Live-Update Callback. Validation + State-Update + Wirkung."""
    # Pre-validation
    for p in params:
        if p.name == 'body_height':
            if not (self._body_height_min <= p.value <= self._body_height_max):
                return SetParametersResult(
                    successful=False,
                    reason=f'body_height={p.value} outside [{self._body_height_min}, {self._body_height_max}]'
                )

    # Apply updates
    for p in params:
        if p.name == 'body_height':
            self._body_height = p.value
            self._recompute_stand_pose()
        elif p.name == 'step_height':
            self._step_height = p.value  # next swing uses new value
        elif p.name == 'cycle_time':
            self._cycle_time = p.value
            # next cycle uses new period (current cycle completes)
        elif p.name == 'tick_rate':
            self._tick_rate = p.value
            self._restart_timer()
        elif p.name == 'gait_pattern':
            self._gait_pattern_name = p.value
            self._load_gait_pattern()
        # ... etc.

    return SetParametersResult(successful=True)
```

### A.3 — State-Update-Methoden (~2 h)

Implementiere die Helper-Methoden:

- `_recompute_stand_pose()` — Foot-Targets für Standing-State neu berechnen
- `_restart_timer()` — Timer mit neuer Frequenz neu starten
- `_load_gait_pattern()` — neues Pattern-Preset laden, State-Machine zurücksetzen wenn nötig

### A.4 — Unit-Tests (~1.5 h)

In `hexapod_gait/test/test_param_callback.py`:

- `test_param_set_body_height_updates_state` — Param-Update → interne Variable
- `test_param_set_invalid_body_height_rejected` — out-of-range → SetParametersResult(False)
- `test_param_set_tick_rate_restarts_timer` — Timer-Period prüfen
- `test_param_set_gait_pattern_loads_preset` — Pattern-Wechsel
- `test_param_descriptor_has_range` — alle relevanten Params haben Range

### A.5 — launch_testing-Smoke (~1 h)

In `hexapod_gait/test/launch/test_gait_param_live.py`:

- gait_node starten, ParamClient-Service nutzen um Live-Params zu setzen
- Topic-Output prüfen: nach `body_height=-0.060` setzen sollte sich die
  Stand-Pose-Joint-Werte ändern
- Assert dass kein Crash beim Param-Update

### A.6 — User-Smoke: rqt_reconfigure manuell (~10 min)

```bash
# Terminal 1: Sim
ros2 launch hexapod_bringup sim.launch.py

# Terminal 2: gait_node
ros2 launch hexapod_gait gait.launch.py

# Terminal 3: rqt
ros2 run rqt_reconfigure rqt_reconfigure
# → /gait_node auswählen, Slider verschieben → Hexapod reagiert in Gazebo
```

### A.7 — Self-Review

CLAUDE.md §4-Pflicht-Tabelle.

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| A-T1 | `colcon build --packages-select hexapod_gait` | grün | Claude |
| A-T2 | `colcon test --packages-select hexapod_gait` | alle Tests grün, neue Param-Callback-Tests dabei | Claude |
| A-T3 | `colcon test --packages-select hexapod_bringup hexapod_hardware` | 18/0/0 + 208/0/20 unverändert | Claude |
| A-T4 (User) | `ros2 param set /gait_node body_height -0.060` während Sim läuft → Hexapod Position ändert sich | manuelle Bestätigung | User |
| A-T5 (User) | rqt_reconfigure öffnen, Slider `body_height` verschieben → Live-Effekt in Gazebo | manuelle Bestätigung | User |
| A-T6 (User) | rqt_reconfigure: `gait_pattern` dropdown wechseln (z.B. tripod → single_leg_3) → State-Machine-Wechsel | manuelle Bestätigung | User |
| A-T7 (User) | rqt_reconfigure: invaliden Wert eingeben (z.B. body_height -1.0) → Fehler-Meldung | manuelle Bestätigung | User |

### Was bewusst NICHT in Stage A getestet wird

- **Plugin-Param-Callback** (Stage B)
- **/servo_pulses Topic** (Stage C)
- **params_file-Arg in Launch-Files** (Stage D)
- **Preset-YAMLs** (Stage E)
- **Echte HW-Verbindung** — Stage A ist Sim-only

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

- [ ] A.1 phase_11_stage_a_plan.md (Plan-Doku) finalisiert + User-Freigabe
- [ ] A.2 phase_11_stage_a_test_commands.md angelegt
- [ ] A.3 gait_node ParameterDescriptors für alle 13 Params deklariert
- [ ] A.4 `on_set_parameters_callback` registriert
- [ ] A.5 Helper-Methoden implementiert (_recompute_stand_pose, _restart_timer, _load_gait_pattern)
- [ ] A.6 Edge-Case-Handling (Param-Wechsel während WALKING)
- [ ] A.7 A-T1 colcon build grün
- [ ] A.8 A-T2 colcon test grün (neue Param-Callback-Tests)
- [ ] A.9 A-T3 keine Regression in hexapod_bringup / hexapod_hardware
- [ ] A.10 A-T4..A-T7 User-Smoke
- [ ] A.11 Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] A.12 Stage-A-Notizen + Übergang Stage B

**Done-Kriterium A erreicht:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke A-T4..A-T7 bestätigt.

---

## Erwartete Stage-A-Dauer

- A.1 Plan-Doku (diese Datei): ~30 min Claude (erledigt)
- A.2 test_commands.md: ~15 min Claude
- A.3 Param-Descriptors deklarieren: ~2 h Claude
- A.4 Callback registrieren + Validation: ~1 h Claude
- A.5 State-Update-Helper: ~2 h Claude
- A.6 Edge-Case-Handling: ~30 min Claude
- A.7-A.9 Build + Test: ~30 min
- A.10 User-Smoke: ~15 min User
- A.11 Self-Review: ~15 min Claude

**Schätzung:** ~7 h Claude + ~15 min User = **~1 d Gesamt**.
