# H1 — Schritthöhen-Modi — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus [`H1_step_height_modes_plan.md`](H1_step_height_modes_plan.md) §3.
> Alle `[x]` = H1 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Post-Review-Tabelle nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> **Ziel-Werte (nach Offline-Gate H1.2 final):** tief 0.160/−0.065/**0.04** (bleibt) ·
> mittel 0.160/−0.080/**0.06** · hoch **0.17|0.18**/−0.100/**0.10** (Fallback-Treppe Plan §6.2).
> Deckel-Semantik: **Reject**. Nur tripod; Tempo-Presets = H2.

```
H1 (Schritthöhen-Modi):
- [ ] H1.1 Tool: Margen-Report + --min-margin (auch fuer check) + --leveling-deg + engine-check-Subcommand (Transitions: Start/Richtungswechsel/Stopp/Stance-Switch/Sit-Stand) + volle Tick-Aufloesung + --s4-floor + apex_meter.py + Tool-Tests gruen
- [ ] H1.2 Offline-Validierung: Ziel-Zellen (mit --min-margin + --leveling-deg 4.0 + --s4-floor) + Uebergaenge + Sit/Stand engine-checked; finale Werte-Tabelle (inkl. hoch-radial 0.17 vs 0.18) dokumentiert
- [ ] H1.3 Code: _STANCE_MODES neue Werte + step_height_max-Feld + per-Modus-Reject + step_height-Param-Default 0.060 (Boot=mittel-Konsistenz) + Init-Konsistenz-Check (Boot-Override); Node-Tests (Deckel, full-cycle je Modus, Richtungswechsel im Lauf, Uebergaenge, Sit/Stand) + bestehende Suite + Lint gruen
- [ ] H1.4 Sim-Smoke: Hoehen durchschalten + laufen + Uebergaenge, kein IKError/Regress
- [ ] H1.5 HW aufgebockt: apex_meter-Messung je Modus (cmd vs real, ggf. cycle-Varianten) — Verlust-Zahl dokumentiert
- [ ] H1.6 HW Boden: alle 3 Modi laufen stabil; hoch-Modus ueber echtes Klein-Terrain; Strom/Stabilitaet ok
- [ ] H1.7 Presets/Doku nachgezogen: hw_terrain.yaml (hoch + finale sh), README (Stance-Tabelle + Deckel), ai_navigation (Stance-Modi-Abschnitt + Tool-Flags), tools_catalog (engine-check/apex_meter), Backlog
- [ ] H1.8 kritische Self-Review-Tabelle
```

## Offline-Werte-Tabelle (H1.2-Ergebnis — nach Ausführung füllen)

| Zelle | envelope-check | engine-check | final |
|---|---|---|---|
| tief 0.160 / 0.04 | ✓ GREEN | | |
| mittel 0.160 / 0.06 | ✓ GREEN | | |
| hoch 0.170 / 0.10 | ✓ GREEN | | |
| hoch 0.180 / 0.10 | ✓ GREEN | | |
| Übergang mittel↔hoch (Radius-Wechsel) | — | | |
| Sit/Stand aus hoch@neuem Radius | — | | |

## HW-Apex-Messung (H1.5-Ergebnis — nach Ausführung füllen)

| Modus | sh kommandiert | Apex real (apex_meter) | Verlust | Anmerkung |
|---|---|---|---|---|
| tief | 0.04 | | | |
| mittel | 0.06 | | | |
| hoch | 0.09/0.10 | | | |
