# Tools — Hexapod Workspace

Optionale Helper-Scripts. Nichts hier ist Voraussetzung für `colcon build`
oder die ROS-Funktionalität.

## Inhalt

| File | Zweck | Wann nützlich |
|---|---|---|
| [`hexapod-shell-aliases.sh`](hexapod-shell-aliases.sh) | Bash-Funktionen für Gait-Preset-save/load + Plugin-Cal-Save + Backup-Listing (Phase 11 Stage D) | Cal-Sessions, Phase-13-Bringup, Demos — wo wiederkehrende lange `ros2`-Befehle vereinfacht werden sollen |
| [`phase_10_f2_ik_probe.py`](phase_10_f2_ik_probe.py) | IK-Probe-Skript aus Phase 10 Stage F.2 | Phase-10-spezifisch, dokumentiert in `docs_raspi/phase_10_progress.md` |

## hexapod-shell-aliases.sh

Optional via `~/.bashrc` source-en:

```bash
echo 'source ~/hexapod_ws/tools/hexapod-shell-aliases.sh' >> ~/.bashrc
```

Danach stehen folgende Funktionen zur Verfügung:

- `hexapod-save-walking-params <name>` — Gait-Preset speichern
- `hexapod-load-walking-preset <name>` — Gait-Preset laden
- `hexapod-save-cal` — Plugin-Cal speichern (Stage-B-Service)
- `hexapod-list-presets` — verfügbare Gait-Presets
- `hexapod-list-cal-backups` — verfügbare Plugin-Cal-Backups

Vollständige Beschreibung + Beispiel-Workflow im File-Top-Kommentar
selbst.

Bei abweichendem Workspace-Pfad:
```bash
export HEXAPOD_WS=/your/custom/path
source ~/hexapod_ws/tools/hexapod-shell-aliases.sh
```

**Shell-Kompatibilität:** Bash und meist zsh. Fish nicht unterstützt.
