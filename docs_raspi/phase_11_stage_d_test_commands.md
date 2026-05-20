# Phase 11 — Stufe D — Test-Kommandos

> **Stage D:** Preset-Workflow + rqt-Setup-Doku + Bash-Aliases.
>
> **Plan:** [`phase_11_stage_d_plan.md`](phase_11_stage_d_plan.md)
> **Setup-Doku:** [`phase_11_rqt_setup.md`](phase_11_rqt_setup.md)

---

## Vorbedingung

- Stage A + B + C abgeschlossen, alle Live-Param-Surfaces verifiziert
- Stage-D-Code committet (params_file-Arg, Preset-Verzeichnis,
  Setup-Doku, Bash-Aliases)
- Falls vorher noch ein altes gait_node lief: erst killen
  ```bash
  pkill -9 -f gait_node; sleep 2
  ```

---

## Claude-Tests (CI-Pfad)

### C-T1 — colcon build hexapod_gait + hexapod_bringup grün

**Terminal beliebig:**
```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait hexapod_bringup
```

**Erwartung:** beide grün, kein Linter-Fehler.

### C-T2 — colcon test alle Pakete

**Terminal beliebig:**
```bash
colcon test --packages-select hexapod_gait hexapod_bringup hexapod_hardware
```

**Erwartung unverändert:**
- hexapod_gait: 20/0/1
- hexapod_bringup: 18/0/0
- hexapod_hardware: 220/0/20

---

## User-Smoke-Tests

> **Terminal-Konvention für die Tests:**
> - **Terminal 1** = gait_node (vordergrund — gait_node-Logger
>   sichtbar; bei Restart kill via Ctrl+C)
> - **Terminal 2** = Befehle gegen den laufenden Node (param get/set,
>   topic pub, etc.)
>
> Vor jedem Test der gait_node neu startet: in Terminal 1 erst Ctrl+C
> (oder `pkill -9 -f gait_node` in Terminal 2).

### D-T3 — Launch ohne params_file → Defaults wirken

**Terminal 1** (gait_node, vordergrund):
```bash
source ~/hexapod_ws/install/setup.bash
ros2 launch hexapod_gait gait.launch.py
```

Warten bis Logger zeigt:
```
[gait_node]: gait_node init: pattern=tripod, step_height=0.030 m, ...
                                body_height=-0.052 m ...
```

**Terminal 2** (verify):
```bash
ros2 param get /gait_node body_height
# Erwartung: Double value is: -0.052 (= gait.launch.py-Default)

ros2 param get /gait_node cycle_time
# Erwartung: Double value is: 2.0
```

→ ✅ wenn beide Defaults wie erwartet.

### D-T4 — Launch mit params_file → Preset-Werte wirken

**Terminal 1** — gait_node beenden (Ctrl+C), dann mit Preset starten:
```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/defensive_walk.yaml
```

Logger sollte zeigen:
```
[gait_node]: gait_node init: ..., cycle_time=4.00 s, ...
              step_length_max=0.030 m (linear_max=0.015 m/s), ...
```

(cycle_time=4.0 statt 2.0, step_length_max=0.030 statt 0.05 →
Preset-Override greift.)

**Terminal 2** — verifizieren:
```bash
ros2 param get /gait_node cycle_time
# Erwartung: Double value is: 4.0

ros2 param get /gait_node step_length_max
# Erwartung: Double value is: 0.03

ros2 param get /gait_node body_height
# Erwartung: Double value is: -0.05 (Preset-Override, statt default -0.052)

ros2 param get /gait_node gait_pattern
# Erwartung: String value is: tripod (= Default, weil Preset das Feld nicht enthält)
```

→ ✅ wenn alle vier Werte stimmen (3× Preset-Override + 1× Default-Inherit).

### D-T5 — Roundtrip: dump → load

Diese Test demonstriert den vollen Tuning-Save-Reload-Workflow.

**Terminal 1** — gait_node läuft (entweder noch von D-T4 oder neu starten mit
`ros2 launch hexapod_gait gait.launch.py` für sauberen Default-State).

**Terminal 2** — Werte ändern, dann dumpen:
```bash
# Live-Tuning via CLI
ros2 param set /gait_node body_height -0.060
ros2 param set /gait_node step_height 0.04

# Dump in eine eigene Preset-YAML (Jazzy-Syntax: stdout-Redirect!)
ros2 param dump /gait_node > src/hexapod_gait/config/presets/my_test_session.yaml

# Inspizieren
cat src/hexapod_gait/config/presets/my_test_session.yaml
# Erwartung: enthält body_height: -0.06, step_height: 0.04 unter /gait_node:
```

**Terminal 1** — gait_node killen (Ctrl+C), mit eigenem Preset neu starten:
```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/my_test_session.yaml
```

**Terminal 2** — Roundtrip-Verifikation:
```bash
ros2 param get /gait_node body_height
# Erwartung: Double value is: -0.06 (= unser Tuning, persistiert)

ros2 param get /gait_node step_height
# Erwartung: Double value is: 0.04
```

→ ✅ wenn beide Werte aus unserem Tuning wieder da sind.

### D-T6 — Bash-Aliases (D-Q3 Option A)

**Terminal 2** — Aliases sourcen + verifizieren:
```bash
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh

# Verify functions exist
type hexapod-save-walking-params
# Erwartung: hexapod-save-walking-params is a function

# Alle 5 Funktionen vorhanden?
for fn in hexapod-save-walking-params hexapod-load-walking-preset \
          hexapod-save-cal hexapod-list-presets hexapod-list-cal-backups; do
  type ${fn} 2>&1 | head -1
done
# Erwartung: 5× "<name> is a function"
```

**Terminal 2** — Save-Alias mit laufendem gait_node (von D-T5 noch aktiv):
```bash
hexapod-save-walking-params alias_test
# Erwartung: "Saved /gait_node params to .../alias_test.yaml"

hexapod-list-presets
# Erwartung: defensive_walk.yaml, current_state.yaml, my_test_session.yaml,
#            alias_test.yaml (mind. die 4 sollten erscheinen)
```

→ ✅ wenn die Funktionen existieren und alias_test.yaml angelegt wird.

### D-T7 — rqt-Multi-Plugin-Layout (D-Q4 Option B)

Verifikations-Ziel: Setup-Doku [`phase_11_rqt_setup.md`](phase_11_rqt_setup.md)
Sektion 1 ist klar genug, dass User das Layout in <5 min aufbaut.

**Terminal 3** (neu, für rqt):
```bash
source ~/hexapod_ws/install/setup.bash
rqt
```

Im rqt-Fenster (leer beim Start), Setup-Doku Sektion 1 folgen:
1. Plugins → Configuration → Dynamic Reconfigure
2. Plugins → Visualization → Plot
3. Plugins → Topics → Topic Monitor
4. Plugins → Logging → Console
5. Fenster-Layout per Drag&Drop (Empfehlung 2×2-Grid)
6. Im Dynamic Reconfigure den `/hexapodsystem` und `/gait_node` selektieren
   (falls beide vorhanden — `/hexapodsystem` fehlt wenn nur gait_node läuft)
7. Im Plot Topic eintippen: `/hexapodsystem/servo_pulses/data[15]`
   (siehe Stage-C-Limitation in Setup-Doku falls `+`-Button ausgegraut)

**Erwartung:** in unter 5 Minuten ein funktionsfähiges Multi-Plugin-Layout
gemäß Doku. Falls Doku unklar war oder Schritte fehlen → bitte sagen,
damit Plan-Korrektur auf D-Q4 Option A (Perspective committen) möglich
ist.

→ ✅ wenn Setup-Doku-Schritte ohne externe Hilfe funktionieren.

---

## Bewusst NICHT in Stage D getestet

- Plugin-Cal-Reload über params_file (= D-Q1 Option B/C, verworfen)
- Sim-Tuning-Szenarien (Stage E)
- Tibia-Sim-Verifikation (Stage E Cross-Phase-Pendenz)

---

## Status-Tracking

Pro Test in [phase_11_progress.md](phase_11_progress.md) abhaken.
