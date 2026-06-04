# Hexapod — Projekt-Architektur (Referenz-Index)

> **Lebende Nachschlagewerke.** Dieser Ordner beschreibt, *wie das System aufgebaut ist*
> und *wo man was findet/ändert*. Er ist **kein** Phasen-/Arbeitsplan — die offenen
> Aufgaben liegen in [`../project_finalization/`](../project_finalization/00_backlog.md).
>
> Verlinkt aus `CLAUDE.md` (§Projekt-Architektur) und `PHASE.md`.

## Inhalt dieses Ordners
| Datei | Zweck |
|---|---|
| [`architecture.md`](architecture.md) | Pakete, Node-Graph (Sim + HW), Topics/Services + ausgetauschte Daten, Controller, Hardware-Kette, Limit-/Cal-Quellen, Launch-Einstiegspunkte. |
| [`ai_navigation.md`](ai_navigation.md) | ⭐ **„README für AI"**: „Ich ändere X → schau hier, aktualisiere Y, validiere mit Z." Stolperstein-Karte. Zuerst lesen bei jeder Änderung. |
| [`change_workflows.md`](change_workflows.md) | Konkrete Schritt-für-Schritt-Workflows (Servo getauscht, Geometrie/Cal geändert, neue Gangart, neuer Param …). Konsolidiert `docs/01_hardware_change_workflow.md`. |
| [`tools_catalog.md`](tools_catalog.md) | Alle Eigen-Tools (envelope-checks, reachability-viz, geplant torque-viz, Shell-Aliases, Presets) + wann man welches nutzt. |
| [`sim_capabilities.md`](sim_capabilities.md) | Was Gazebo / RViz + unsere Viz-Tools können (was wir dazu implementiert haben). |

## Big Picture (Sim → HW → untethered)
- **Sim-Pfad** (Desktop): Gazebo + `gz_ros2_control` + RViz. Code 1:1 portierbar via `ros2_control`.
- **HW-Pfad** (Bench/Pi): `ros2_control_node` + `hexapod_hardware`-Plugin ↔ Servo2040 (USB) ↔ 18 Servos.
- **Ziel:** untethered auf Raspberry Pi 5 + 2S-LiPo. Reihenfolge + offene Stages: `../project_finalization/`.

## Source-of-Truth-Prinzip
Diese Docs bleiben **high-level** und verlinken auf die echten Dateien (URDF, config.py,
servo_mapping.yaml, …). Bei Code-Änderung: **die betroffene Doc hier nachziehen**
(`ai_navigation.md` sagt, welche). Sonst veraltet die Übersicht.

## Verwandte (historische / detaillierte) Docs
- `docs/` — Sim-Phasen 0–6 (abgeschlossen).
- `docs_raspi/` — HW-Phasen 7–13 Arbeits-/Verlaufs-Docs (inkl. Phase 13 Stage 1 Lauf-Optimierung).
- `CLAUDE.md` (Arbeitsanweisung), `PHASE.md` (aktuelle Phase), Memory-Einträge.
