# Tool-Katalog

> Eigen-Tools im Repo + wann man welches nutzt. Alle offline (kein HW nötig), außer wo vermerkt.

## Analyse / Validierung (`tools/`)
| Tool | Zweck | Typische Nutzung |
|---|---|---|
| `walking_envelope_check.py` | Prüft Lauf-Fußbahn gegen URDF-Limits + Reichweite (alle 4 cmd_vel-Szenarien). | `check` (eine Config), `sweep` (Übersicht radial×Höhe), `recommend` (fertiges Preset). Nutzt URDF-Limits **live**. README: `tools/walking_envelope_check.README.md`. |
| `standup_envelope_check.py` | Prüft den **Aufsteh-Pfad** (Touchdown + Push) gegen Limits/Schürfen. | `--radial --bh-final`. **Eigener Konsument** — Walk-Pose ≠ Standup-Pfad separat prüfen. |
| (geplant) `torque_viz` / Hitze-Tool | Quasi-statische Gelenk-Momente (Jᵀ·F) pro Pose → RViz Zahl+Farbe; Sweep für last-optimale Pose. | Hitze-Analyse, Body-Pose/CoG, Geometrie-Entscheidung. Siehe `../project_finalization/` (Block A1). |

## Visualisierung (RViz)
| Tool | Zweck |
|---|---|
| `hexapod_gait/reachability_viz.py` (+ `reachability_viz.launch.py`) | Erreichbare Fuß-Hülle pro Bein als MarkerArray (blau=aktuelles Limit, rot=volle Tibia). Pure FK, keine HW. Doku: `docs_raspi/phase_13_stage_1_reachability_viz_test_commands.md`. |
| `view_hw.rviz` / `view_reach.rviz` (`hexapod_description/config`) | RViz-Configs: HW-Spiegel bzw. Reachability. |

## Workflow / Komfort
| Tool | Zweck |
|---|---|
| `tools/hexapod-shell-aliases.sh` | Opt-in Aliases: `hexapod-save-walking-params`, `hexapod-load-walking-preset`, `hexapod-save-cal`, … Bei Cal-/Preset-Workflow darauf verweisen. ([[project_phase11_convenience_aliases]]) |
| `hexapod_gait/config/presets/*.yaml` | Gespeicherte Gait-Configs (z.B. `feet_closer_walk.yaml` = feet-closer high Walk-Pose). Laden via `params_file:=`. |

> **Pflege:** Neues Tool? Hier eintragen + in [`ai_navigation.md`](ai_navigation.md) §3 verlinken.
