# Phase 11 — rqt-Multi-Plugin-Setup + Save/Load-Workflow

Phase-11-User-Manual: wie man die Live-Param-Surfaces aus Stage A
(gait_node, 14 Params), Stage B (Plugin-Cal, 72 Params) und Stage C
(Diagnostic-Topic) zusammen in einem rqt-Fenster nutzt, plus
Save/Load-Mechanismen für Tuning-Sessions.

---

## 1. Multi-Plugin-Layout aufbauen (manuell, D-Q4 Option B)

`rqt` ist ein Qt-basiertes Container-Programm für ROS-GUIs. Statt drei
Standalone-Fenster (rqt_reconfigure, rqt_plot, rqt_topic) kann man ein
einziges Fenster mit mehreren Plugins parallel öffnen.

### Aufbau

```bash
rqt
```

> **Hinweis (ROS-Jazzy-Quirk):** `rqt` direkt aufrufen, **nicht**
> `ros2 run rqt rqt`. Das `rqt`-Executable liegt in
> `/opt/ros/jazzy/bin/` (im PATH durch ROS-Setup) und ist NICHT als
> `ros2 run`-Executable registriert. Falls `rqt` "command not found"
> sagt: `sudo apt install ros-jazzy-rqt ros-jazzy-rqt-common-plugins`.

Im rqt-Menü (Standard-Layout: leer):

1. **Plugins → Configuration → Dynamic Reconfigure** — für die
   Param-Slider (Gait + Plugin-Cal)
2. **Plugins → Visualization → Plot** — für Live-Visualisierung
   `/servo_pulses` (Stage C)
3. **Plugins → Topics → Topic Monitor** — für `/joint_states`,
   `/cmd_vel` etc. zur Diagnose
4. **Plugins → Logging → Console** — für Plugin- und gait_node-Logger
   live

Layout per Drag&Drop (Empfehlung 2×2-Grid):

```
┌─────────────────┬───────────────────────────┐
│ Dynamic         │  Plot                     │
│ Reconfigure     │  (/hexapodsystem/         │
│                 │   servo_pulses)           │
├─────────────────┼───────────────────────────┤
│ Topic Monitor   │  Console                  │
└─────────────────┴───────────────────────────┘
```

### Plugin-Settings

**Dynamic Reconfigure (links oben):**
- Im linken Panel `/hexapodsystem` UND `/gait_node` selektieren
- 72 Pin-Slider (`pin_0..pin_17` mit je 4 Untereinträgen) plus
  14 gait-Params plus `publish_servo_pulses`-Checkbox sind sichtbar

**Plot (rechts oben):**
- Topic im oberen Eingabefeld eintippen:
  `/hexapodsystem/servo_pulses/data[15]`
- Auf `+`-Button klicken (Hinweis: in ROS-Jazzy ist der Button bei
  `MultiArray.data[N]`-Indexing manchmal ausgegraut — siehe Stage-C-
  Limitation unten für Workaround)

**Topic Monitor (links unten):**
- Aktiviert sich automatisch
- Interessante Topics für Tuning: `/joint_states`,
  `/leg_<n>_controller/joint_trajectory`

**Console (rechts unten):**
- Filter optional auf `hexapod_hardware` + `gait_node`-Logger

### Eigene Perspective lokal speichern (optional, nicht ins Repo)

Wenn du dein Layout wieder haben willst beim nächsten Start:

```
rqt → Perspectives → Save Perspective As → my_hexapod_layout
```

Die Datei landet in `~/.config/ros.org/rqt_gui.ini`. **Bewusst nicht
versioniert** (siehe Plan-Doku D-Q4 Option B): Perspective-Files sind
bildschirmauflösungs-abhängig + nicht portabel zwischen Systemen.
User-spezifisch ist OK, Repo-committed wäre Drift-Risiko.

Beim nächsten Start:
```bash
rqt --perspective my_hexapod_layout
```

---

## 2. Save-Workflow

Drei verschiedene Persistenz-Mechanismen — **nicht verwechseln:**

### 2.1 Gait-Params (Stage D — Preset-YAML)

```bash
ros2 param dump /gait_node > src/hexapod_gait/config/presets/my_walking_preset.yaml
```

→ Erzeugt `src/hexapod_gait/config/presets/my_walking_preset.yaml`
mit allen 14 gait_node-Live-Params zum aktuellen Stand.

> **Hinweis:** ROS Jazzy hat keine `--output-dir`/`--filename`-Args
> mehr für `ros2 param dump` (gab's in älteren ROS-Versionen). Output
> geht ausschließlich auf stdout — Redirect via `>` ist der Standard.

Mit Convenience-Alias (siehe Sektion 5):
```bash
hexapod-save-walking-params my_walking_preset
```

### 2.2 Plugin-Cal (Stage B — servo_mapping.yaml + Timestamp-Backup)

```bash
ros2 service call /save_calibration std_srvs/srv/Trigger
```

→ Erzeugt
`src/hexapod_hardware/config/servo_mapping.yaml.bak-YYYY-MM-DDTHH-MM-SS`
als Backup und überschreibt `servo_mapping.yaml` mit den aktuellen
Live-Cal-Werten. Bei jedem Save = neuer eindeutiger Timestamp →
**nichts wird je überschrieben**, beliebig viele Cal-Sessions sammeln
sich als Versionsgeschichte.

Mit Alias:
```bash
hexapod-save-cal
```

### 2.3 Was NICHT Stage-D-relevant ist

- **rqt-Perspective:** lokal in `~/.config/ros.org/`, nicht ins Repo
- **Initial/Stand/Shutdown-Posen:** Phase-13-Material, nicht in Stage D
  (siehe Plan-Doku „Bewusst NICHT in Stage D"-Sektion)

---

## 3. Load-Workflow

### 3.1 Gait-Preset beim Launch

```bash
ros2 launch hexapod_gait gait.launch.py \
  params_file:=src/hexapod_gait/config/presets/my_walking_preset.yaml
```

Mit Alias:
```bash
hexapod-load-walking-preset my_walking_preset
```

Wie `params_file` wirkt: die Inline-Defaults aus `gait.launch.py`
werden zuerst gesetzt, dann das Preset darüber gelegt. Felder im Preset
überschreiben die Defaults. Felder die das Preset weglässt, behalten
die Defaults — Presets können also ein Subset sein.

### 3.2 Plugin-Cal automatisch beim Plugin-Start

`servo_mapping.yaml` wird beim `on_init` aus der URDF-Plugin-Param
`calibration_file` geladen. Nach `/save_calibration` (Sektion 2.2)
enthält die Datei die aktuellen Cal-Werte — nächster Plugin-Start
hat die automatisch da.

Bei Bedarf manuell ein älteres Backup zurückladen:
```bash
cp src/hexapod_hardware/config/servo_mapping.yaml.bak-2026-05-17T10-30-00 \
   src/hexapod_hardware/config/servo_mapping.yaml
# Plugin neu starten (kill + relaunch)
```

---

## 4. rqt_plot-Limitation (Stage C / Jazzy-Bug)

`MultiArray.data[N]`-Indexing in rqt_plot funktioniert in ROS-Jazzy
unzuverlässig — der `+`-Button bleibt manchmal ausgegraut.

**Workarounds:**

```bash
# Option 1: CLI-echo (immer zuverlässig)
ros2 topic echo /hexapodsystem/servo_pulses --once

# Option 2: rqt_plot ohne Indexing (zeigt alle 18 Werte als Linien)
ros2 run rqt_plot rqt_plot /hexapodsystem/servo_pulses/data

# Option 3: Toggle der Diagnostic-Publish
ros2 param set /hexapodsystem publish_servo_pulses true
# topic echo dann ein, danach wieder false
ros2 param set /hexapodsystem publish_servo_pulses false
```

Phase-13-Polish: Custom-Message `HexapodPulses` mit per-Pin-Feldern
(`pin_0`, `pin_1`, ...) würde rqt_plot direkt unterstützen — bewusst
in Stage C verworfen zugunsten Schlankheit.

---

## 5. Convenience Aliases (optional)

Datei [`tools/hexapod-shell-aliases.sh`](../tools/hexapod-shell-aliases.sh)
enthält Bash-Funktionen, die wiederkehrende lange ros2-Befehle
verkürzen. **Opt-in** — sourcen wenn gewünscht:

```bash
echo 'source ~/hexapod_ws/tools/hexapod-shell-aliases.sh' >> ~/.bashrc
```

Oder pro Session:
```bash
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
```

Verfügbare Funktionen:

| Alias | Macht |
|---|---|
| `hexapod-save-walking-params <name>` | `ros2 param dump /gait_node ...` |
| `hexapod-load-walking-preset <name>` | `ros2 launch ... params_file:=...` |
| `hexapod-save-cal` | `ros2 service call /save_calibration ...` |
| `hexapod-list-presets` | listet Gait-Presets |
| `hexapod-list-cal-backups` | listet Plugin-Cal-Backups mit Timestamp |

Vollständige Doku im File-Top-Kommentar des Scripts selbst (inkl.
Beispiel-Cal-Session-Workflow).

**Bei abweichendem Workspace-Pfad:**
```bash
export HEXAPOD_WS=/your/custom/path
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
```

---

## 6. Typischer Cal-Session-Workflow (alles zusammen)

```bash
# 0. Bash-Aliases verfügbar machen (einmaliger Setup)
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh

# 1. Plugin starten (in eigenem Terminal)
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
# Für echte Hardware: ohne loopback_mode

# 2. gait_node starten — entweder mit Default oder Preset
hexapod-load-walking-preset defensive_walk
# Oder ohne Preset: ros2 launch hexapod_gait gait.launch.py

# 3. rqt aufmachen
rqt
# Multi-Plugin-Layout aufbauen (siehe Sektion 1)

# 4. In rqt slidern:
#    - Plugin-Cal pro Pin tunen
#    - Gait-Params anpassen (body_height, cycle_time, etc.)
#    - publish_servo_pulses togglen für Live-Visualisierung

# 5. Speichern:
hexapod-save-cal                                  # Plugin-Cal → servo_mapping.yaml
hexapod-save-walking-params session_2026_05_20    # Gait → presets/

# 6. Backup verifizieren:
hexapod-list-cal-backups
hexapod-list-presets
```

---

## 7. Cross-Phase-Hinweise

| Thema | Wo dokumentiert |
|---|---|
| Stage-A Gait-Params (welche, was tun sie) | [`src/hexapod_gait/README.md`](../src/hexapod_gait/README.md) |
| Stage-B Plugin-Cal + `/save_calibration` | [`src/hexapod_hardware/README.md`](../src/hexapod_hardware/README.md) Phase-11-Block |
| Stage-C `/servo_pulses` Diagnostic-Topic | wie oben, eigener Sub-Abschnitt |
| Initial/Stand/Shutdown-Posen (Phase 13) | Memory `project_phase13_initial_pose_presets.md` |
