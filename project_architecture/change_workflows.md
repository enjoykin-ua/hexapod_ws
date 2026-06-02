# Change-Workflows (Schritt-für-Schritt)

> Detaillierte „wenn … dann tu …"-Abläufe. Die **Schnell-Karte** steht in
> [`ai_navigation.md`](ai_navigation.md) §1 — hier die ausführlichen Schritte.
> Bestehende Szenarien-Sammlung: **`docs/01_hardware_change_workflow.md` (12 Szenarien)** —
> diese Datei konsolidiert/ergänzt sie; bei Lücken dort nachsehen.

## Status
🟡 **Wachsendes Dokument.** Kern-Workflows unten; weitere aus `docs/01_hardware_change_workflow.md`
übernehmen, wenn berührt.

## Servo getauscht (1 Pin)
1. `servo_mapping.yaml`: für den Pin `pulse_min/zero/max` + `direction` neu kalibrieren (rqt-Sweep).
2. rad=0 → Bein visuell gerade (HW=RViz); bekannte Beuge gegenprüfen.
3. `colcon test hexapod_hardware` (Calibration-Roundtrip) grün.
4. Detail: `docs/01_hardware_change_workflow.md` + `docs_raspi/phase_13_stage_0_6_6_tibia_recal_*`.

## Joint-Limit ändern
→ siehe [`ai_navigation.md`](ai_navigation.md) §1 „Joint-Limit ändern" (5 Dateien + Envelopes + Sim-Smoke).
Vorbild end-to-end: `docs_raspi/phase_13_stage_1_tibia_unlock_plan.md`.

## Geometrie ändern (Bein-Länge / Body-Maße)
⚠️ Großer Rattenschwanz — siehe [`ai_navigation.md`](ai_navigation.md) §1 „Geometrie". Modell-Rechnung +
explizite Freigabe vor Umbau (Reichweite, Re-Cal, Presets, Posen alle neu).

## Gait-Parameter / neue Lauf-Pose
1. `walking_envelope_check sweep/recommend` → validierte (radial/step/height)-Werte.
2. `standup_envelope_check --radial <neu>` → Aufsteh-Pfad separat prüfen!
3. Preset in `config/presets/` schreiben (self-contained: standup- + walk-Werte).
4. Sim (RViz+Gazebo) → HW aufgebockt → Boden.

## Neue Gangart
`gait_patterns.py` → `GaitPattern` + `GAIT_PRESETS` → Tests + Envelope + Sim.

## Sim ↔ HW umschalten
`hexapod_bringup sim.launch.py` vs `real.launch.py`; HW braucht `use_sim_time:=false`
(kein /clock) — siehe [[project_phase13_gait_launch_sim_time_default]].
