# H2 — Tempo-Presets + Schrittweiten-Deckel — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus [`H2_speed_presets_plan.md`](H2_speed_presets_plan.md) §3.
> Alle `[x]` = H2 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Post-Review-Tabelle nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> **Kern-Entscheide (User, §0 des Plans):** `step_length_max` = fester Tabellenwert pro
> Stance-Modus (**tief 0.06 / mittel 0.09 / hoch 0.05**, Gate-validiert in H1) ·
> Tempo = nur `cycle_time` + joy-Scales (envelope-frei) · Umschalten Service+PS4,
> **D-Pad ↑/↓ umgewidmet** von Schrittweiten-Adjust (C3) auf Tempo-Cycle ·
> Startwerte **aggressiv 1.5 / schnell 2.0 (Boot) / mittel 2.6 / langsam 3.3** —
> im Sim-Test live tunen, finale Werte in die Tabelle nachziehen.

```
H2 (Tempo-Presets + Schrittweiten-Deckel):
- [ ] H2.1 Offline: engine-check-Transitions für die sl-Deckel-Zellen (tief 0.04/0.06, mittel 0.05/0.09) exit-code-basiert GREEN (hoch 0.08/0.05 bereits H1.2)
- [ ] H2.2 gait_node: _StanceMode+step_length_max (0.06/0.09/0.05) + Switch setzt sl + Validator-Reject + Init-Deckelung + Param-Default 0.050->0.090 + adjust_step_length-Handler auf Modus-Deckel geclampt + Param-Server-Sync DEFERRED nach Switch-Abschluss (erst bei STANDING; body_height/radial sind standing_only) (H1-Puffer-Fix)
- [ ] H2.3 joy_to_twist: _TEMPO_MODES (Startwerte: schnell/Boot = 2.0 + HEUTIGE YAML-Scales 0.05/0.05/0.46 [sprungfrei!]; aggressiv 1.5/0.17/0.13/1.2; mittel 2.6; langsam 3.3) + D-Pad hoch/runter = Tempo-Cycle (cycle_time via AsyncParameterClient-Future an gait, Ablehnung/Timeout -> kein lokaler Scale-Wechsel + Log) + adjust_step_length-Binding entfernt (Service bleibt)
- [ ] H2.4 Tests (gait sl-Deckel/Switch/Sync + teleop Tempo/D-Pad/Reject-Pfad + Back-Compat) + colcon test hexapod_gait hexapod_kinematics hexapod_teleop + Lint gruen
- [ ] H2.5 Sim: Tempo-Stufen durchschalten + Werte-TUNING (User: Startwerte live verstellen) -> finale _TEMPO_MODES-Werte nachgezogen + erneut Tests
- [ ] H2.6 HW: aggressiv-Realitaets-Check (Servo-Speed/Strom/Stabilitaet, hw_terrain-Alltags-Setup) + Tempo-Wechsel im Feld
- [ ] H2.7 Doku: README (gait+teleop), ai_navigation (Stance-Tabelle 4. Feld + Tempo-Eintrag + C3-Umwidmung), Backlog, H2-test_commands final (self-contained, Param-Tabellen Default/hoch/runter)
- [ ] H2.8 kritische Self-Review-Tabelle
```

## Tempo-Tuning-Tabelle (H2.5-Ergebnis — nach Sim-Tuning füllen)

| Stufe | cycle_time Start | cycle_time final ✍️ | Scales (x/y/z) Start | Scales final ✍️ |
|---|---|---|---|---|
| aggressiv | 1.5 | | 0.17 / 0.13 / 1.2 | |
| schnell (Boot) | 2.0 | | 0.128 / 0.098 / 0.90 | |
| mittel | 2.6 | | 0.098 / 0.075 / 0.69 | |
| langsam | 3.3 | | 0.077 / 0.059 / 0.55 | |
