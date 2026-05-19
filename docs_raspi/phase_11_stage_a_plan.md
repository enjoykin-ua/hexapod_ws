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

## Strategie / Architektur-Entscheidungen

### A. Welche Parameter sollen live tunbar sein?

**Final:** alle Parameter aus `gait.launch.py` (~13 Args, siehe Tabelle
unten).

**Verworfen:** nur Subset — wäre inkonsistent, User könnte vergessen
welche Params live sind und welche nicht.

### B. Welche Params brauchen wieviel Reaktivität?

| Param | Live-Update wirkt | Erklärung |
|---|---|---|
| `body_height` | **sofort** (nächster Tick) | Stand-Pose-Höhe wird neu berechnet, sanft anfahren |
| `radial_distance` | **sofort** | analog body_height |
| `step_height` | **nächster Swing** | aktueller Swing läuft erst zu Ende |
| `step_length_max` | **nächster Cycle** | clampt cmd_vel im nächsten Cycle |
| `default_linear_x/y` | **sofort** | Fallback-Wert ändert sich |
| `default_angular_z` | **sofort** | dito |
| `cmd_vel_timeout` | **sofort** | Timer-Threshold |
| `body_height_min/max` | **sofort** als Clamp | bestehender body_height wird ggf. geclampt |
| `cycle_time` | **nächster Cycle** | aktueller Cycle läuft erst zu Ende, dann neue Periode |
| `tick_rate` | **kompletter Timer-Restart** | aktueller Timer abbrechen, neuer mit neuer Frequenz |
| `time_from_start_factor` | **sofort** | Lookahead-Berechnung |
| `gait_pattern` | **kompletter Pattern-Restart** | aktuelle Trajectory abbrechen, neuer Pattern laden |
| `use_sim_time` | **NICHT live** | Clock-Mode-Wechsel zur Laufzeit ist tricky, Restart nötig |

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
| **A-Q1** Alle gait_node-Params live machen oder Subset? | **A** — alle (~13 Params) für Konsistenz | (B) nur Walking-Pose-Params (body_height, step_height, radial_distance) |
| **A-Q2** `gait_pattern` live wechselbar? | **A** — ja, mit kompletter Pattern-Reload-Logik | (B) read-only, Restart nötig |
| **A-Q3** Validation bei Cross-Param-Constraints | **A** — strikt im Callback ablehnen (Setparameters returned False) | (B) Wert clampen statt ablehnen (silently) |
| **A-Q4** `use_sim_time` live tunbar? | **B** — read-only (Clock-Mode-Wechsel zur Laufzeit ist tricky) | (A) versuchen, aber riskant |
| **A-Q5** Implementation-Stil | **A** — Python (gait_node ist eh Python) | (B) C++ wäre nur bei Plugin-Stage-B relevant |

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
