# Gait-Presets — Phase 11 Stage D

YAML-Files mit gespeicherten `gait_node`-Parameter-Konfigurationen.

## Format

Jede Datei ist ein Standard-ROS2-Param-File mit dem `/gait_node`-Namespace
als Top-Level-Sektion:

```yaml
/gait_node:
  ros__parameters:
    body_height: -0.052
    cycle_time: 2.0
    # ... weitere gait-Params
```

Felder die nicht angegeben sind, behalten den Default aus
`gait.launch.py`. Ein Preset kann also ein Subset der 14 Live-Params
enthalten.

## Lade-Workflow

```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/<name>.yaml
```

Oder mit den Convenience-Aliases aus
[`tools/hexapod-shell-aliases.sh`](../../../../tools/hexapod-shell-aliases.sh):

```bash
hexapod-load-walking-preset <name>
```

## Save-Workflow

Nach Live-Tuning via rqt_reconfigure:

```bash
ros2 param dump /gait_node > src/hexapod_gait/config/presets/my_session.yaml
```

> **Hinweis:** `ros2 param dump` (ROS Jazzy) gibt nur auf stdout aus.
> Die `--output-dir`/`--filename`-Args aus früheren ROS-Versionen
> existieren nicht mehr → Redirect via `>` ist der Standard-Weg.

Oder mit Alias:

```bash
hexapod-save-walking-params my_session
```

## Naming-Convention

- `<walking_style>.yaml` (z.B. `defensive_walk.yaml`, `demo_walk.yaml`)
- `current_state.yaml` reserviert für Snapshots der aktuellen
  Tuning-Session (per `ros2 param dump`)
- `_<test_session>.yaml` mit führendem Underscore für temporäre
  experimentelle Files

## Aktuelle Presets

Alle envelope-validiert für die kurzen Beine (leg_changes / S5): einheitlicher
Radius 0.160, body_height −0.080 (Stance-Modus „mittel"), direktes Aufstehen
ohne Reposition. Reproduzierbar via `tools/walking_envelope_check.py check …`
(Kopfzeile jeder Datei nennt den exakten Befehl).

| Preset | Zweck | radial / bh / step_len / step_h / cycle |
|---|---|---|
| `sim_walk.yaml` | kanonische Sim-Lauf-Pose (Test-Anker) | 0.160 / −0.080 / 0.050 / 0.040 / 2.0 |
| `defensive_walk.yaml` | langsam-sicher (Erst-HW, neue Cal) | 0.160 / −0.080 / 0.030 / 0.030 / 4.0 |
| `demo_walk.yaml` | sichtbarer Lauf (Demo/Video) | 0.160 / −0.080 / 0.050 / 0.050 / 2.0 |
| `aggressive_walk.yaml` | schnell / Stress-Test | 0.160 / −0.080 / 0.070 / 0.050 / 1.5 |

> Gelöscht in S5 (veraltet, alte Lang-Bein-Radii): `current_state.yaml`,
> `alias_test.yaml`, `my_test_session.yaml`, `feet_closer_walk.yaml`.
> `feet_closer_walk` ist mit den kurzen Beinen redundant (jede Pose ist
> feet-closer) → in `sim_walk` aufgegangen.

## Bewusst NICHT hier

Plugin-Cal-Werte (pulse_min/zero/max/direction pro Pin) — die
persistieren über den Stage-B-Save-Service in `servo_mapping.yaml`
mit eigenem Timestamp-Backup-Mechanismus. Siehe
[`src/hexapod_hardware/README.md`](../../../hexapod_hardware/README.md)
„Phase 11 Stage B"-Sektion.

Initial/Stand/Shutdown-Posen — sind Plugin-Pulse-Werte pro Pin,
nicht gait_node-Params. Phase-13-Material, siehe Memory-Eintrag
`project_phase13_initial_pose_presets.md`.
