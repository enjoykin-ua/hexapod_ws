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

| Preset | Zweck | Stand |
|---|---|---|
| `defensive_walk.yaml` | langsam-sicher, niedrige Stride/Step-Height | manuell konfiguriert |
| `current_state.yaml` | Snapshot der gait.launch.py-Defaults | dump-generiert 2026-05-20 |

## Bewusst NICHT hier

Plugin-Cal-Werte (pulse_min/zero/max/direction pro Pin) — die
persistieren über den Stage-B-Save-Service in `servo_mapping.yaml`
mit eigenem Timestamp-Backup-Mechanismus. Siehe
[`src/hexapod_hardware/README.md`](../../../hexapod_hardware/README.md)
„Phase 11 Stage B"-Sektion.

Initial/Stand/Shutdown-Posen — sind Plugin-Pulse-Werte pro Pin,
nicht gait_node-Params. Phase-13-Material, siehe Memory-Eintrag
`project_phase13_initial_pose_presets.md`.
