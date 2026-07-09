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
- [x] H1.1 Tool: Margen-Report + --min-margin (auch fuer check) + --leveling-deg + engine-check-Subcommand (Transitions: Start/Richtungswechsel/Stopp/Stance-Switch/Sit-Stand) + volle Tick-Aufloesung + --s4-floor + apex_meter.py + Tool-Tests gruen  [18 Tool-Tests; Design-Iterationen aus der Eichung: (a) Sequenz-Margen (Sitdown faehrt bewusst grenznah, femur 0.070) ohne Schwelle/informativ, (b) Leveling-Ecken = Coverage-Metrik statt Hard-Fail (heutiger tief-Modus schafft 4°-Voll-Ecken am Apex nicht — 3a-Befund; Engine-Fallback degradiert sanft), (c) min-margin haerten NUR den nominalen Pfad]
- [x] H1.2 Offline-Validierung: Ziel-Zellen + Uebergaenge + Sit/Stand engine-checked; Werte-Tabelle dokumentiert (Plan §0, KORRIGIERT)  [⚠️ Vor-Plan-Tabelle war durch grep|tail-Auslese-Fehler verfaelscht → exit-code-basiert neu gemessen. Ergebnis: mittel 0.06 verfehlt Schwelle um 2 mrad (0.05 komfortabel); hoch 0.09 NUR @ radial 0.170 + cliff_depth 0.02; hoch 0.10 faellt an Apex-Marge (0.067); radial 0.180 faellt am S4-Floor-Reach; Schrittweite 0.12 nur mittel @ sh ≤ 0.05. engine-check-Transitions alle GREEN. → finale Tabellenwerte = User-Entscheid (mittel 0.05|0.06, hoch 0.08@0.16|0.09@0.17+cliff0.02)]
- [x] H1.3 Code: _STANCE_MODES neue Werte (tief 0.04 / mittel 0.05 / hoch 0.08 @ 0.160) + per-Modus-Reject (Deckel = Tabellen-sh, kein Extra-Feld noetig) + step_height-Param-Default 0.050 (Boot=mittel; H1.2-Entscheid statt 0.060) + Init-Konsistenz-Check (Boot-Override deckeln+WARN); test_stance_switch auf ECHTE Tabellenwerte umgestellt (fuhren veraltete Vor-leg_changes-Konstanten 0.13/-0.13!) + neues test_step_height_modes_node.py (9 Tests: Tabelle/Default-Pin, Init-Deckel via Override 0.09, Reject/erlaubt, Deckel folgt Modus, Switch-Kopplung hoch+runter, Apex-Invariante bh+sh <= -0.02); Suite 440 gait / 43 kin + Lint gruen  [Richtungswechsel-im-Lauf + Sit/Stand laufen im Tool-engine-check (H1.2), nicht doppelt als Node-Test]
- [ ] H1.4 Sim-Smoke: Hoehen durchschalten + laufen + Uebergaenge, kein IKError/Regress
- [ ] H1.5 HW aufgebockt: apex_meter-Messung je Modus (cmd vs real, ggf. cycle-Varianten) — Verlust-Zahl dokumentiert
- [ ] H1.6 HW Boden: alle 3 Modi laufen stabil; hoch-Modus ueber echtes Klein-Terrain; Strom/Stabilitaet ok
- [ ] H1.7 Presets/Doku nachgezogen: hw_terrain.yaml (hoch + finale sh), README (Stance-Tabelle + Deckel), ai_navigation (Stance-Modi-Abschnitt + Tool-Flags), tools_catalog (engine-check/apex_meter), Backlog
- [ ] H1.8 kritische Self-Review-Tabelle
```

## Offline-Werte-Tabelle (H1.2-Ergebnis, Gate: min-margin 0.10 + leveling-4°-Coverage + s4-floor)

| Zelle | check (Gate) | engine-check (Transitions) | final |
|---|---|---|---|
| tief 0.160 / 0.04 (heute) | ✅ worst 0.142, cov 92.5 % | ✅ (inkl. Switch→mittel) | **✅ 0.04 (final)** |
| mittel 0.160 / 0.05 | ✅ worst 0.218, cov 100 % | ✅ (Basis + Switch→hoch-final) | **✅ 0.05 (final, User-Entscheid)** |
| mittel 0.160 / 0.06 | ❌ worst 0.098 (2 mrad unter Schwelle), cov 80.3 % | — | verworfen (User: Schwelle glaubwürdig halten) |
| hoch 0.160 / 0.08 (cliff 0.03) | ✅ worst 0.108, cov 84.3 % | ✅ (Basis + Switch→tief + Sitdown/Repos) | **✅ 0.08 (final, User-Entscheid: konservativ)** |
| hoch 0.170 / 0.09 (**cliff 0.02**) | ✅ worst 0.157, cov 97 % | ✅ | verworfen (User: kein Radius-Bruch/cliff-Tradeoff) |
| hoch 0.170 / 0.10 | ❌ Apex-Marge 0.067 | — | verworfen |
| hoch 0.180 / 0.09–0.10 | ❌ S4-Floor-Reach (auch @ cliff 0.02) | — | verworfen |
| Schrittweite 0.12 | nur mittel @ sh ≤ 0.05 GREEN | — | H2: per-Zelle max-sl |

> **Finale Tabellenwerte (H1.3):** tief (0.160, −0.065, **0.04**) · mittel (0.160, −0.080, **0.05**)
> · hoch (0.160, −0.100, **0.08**) — Einheits-Radius bleibt, cliff_depth bleibt 0.03,
> `step_height`-Param-Default 0.040 → **0.050** (Boot = mittel). Deckel = Tabellen-sh je Modus (Reject).

## HW-Apex-Messung (H1.5-Ergebnis — nach Ausführung füllen)

| Modus | sh kommandiert | hub[mm] aufgebockt (H1.5) | hub[mm] Boden (H1.6) | Anmerkung |
|---|---|---|---|---|
| tief | 0.04 | | | |
| mittel | 0.05 | | | |
| hoch | 0.08 | | | |

## Zwischen-Self-Review (nach H1.1–H1.3; finale Tabelle nach H1.6/H1.8)

| Punkt | Status |
|---|---|
| **Auslese-Fehler der Vor-Plan-Tabelle** (`grep\|tail` übersah RED in sidestep/diagonal — ❌-Zeilen enthalten das Wort „RED" nicht) | 🔴→✅ eingestanden + systemisch behoben: alle Auswertungen exit-code-basiert; Plan-§0-Tabelle korrigiert; Lehre in ai_navigation (Stance-Modi-Eintrag) verankert — deckt sich mit [[feedback_no_trim_verification_output]] |
| Gate-Eichung am IST-Zustand (heutige 3 Modi müssen GREEN sein) | ✅ nach 2 Design-Iterationen: (a) Sequenz-Margen ohne Schwelle (Sitdown-Flatten fährt bewährt bis 0.070), (b) Leveling-Ecken = Coverage statt Hard-Fail (3a-Befund: combined ~2°, Apex bindet — Fallback degradiert sanft). Danach: heute GREEN (0.142–0.258), bekannte Schwächen RED |
| 9/10-cm-Wunsch datenbasiert entschieden statt gewünscht-gerechnet | ✅ 0.10 → Apex-Marge 0.067; radial 0.17/0.18 → S4-Floor-Reach; 0.09@0.17+cliff0.02 wäre gegangen — User wählte konservativ 0.08@0.160 |
| `--s4-floor` nutzt den ECHTEN S4-2-Probe-Pfad (adaptive_touchdown_enable + max_extra_depth, keine Kontakte) | OK (Test: moderat GREEN mit ≤-Marge, absurd 0.15 RED) |
| Init-Deckel nutzt den Boot-Modus (mittel) — bei Custom-body_height-Overrides nur Näherung | 🟡 dokumentiert (wie §6.9: wer Preset-System verlässt → IKError-Backstop) |
| `_do_stance_switch` setzt `_step_height` am Param-Server vorbei → `ros2 param get step_height` zeigt nach Switch ggf. den alten Wert | 🟡 vormerken — vorbestehende Inkonsistenz, jetzt sichtbarer (Werte differieren pro Modus); Kandidat: Param nach Switch nachziehen |
| README-Param-Tabelle hat WEITERE veraltete Defaults (body_height −0.052, radial 0.27 — Vor-leg_changes) | 🟡 vormerken — vorbestehender Doku-Drift, nicht H1-Scope; nur step_height-Zeile aktualisiert |
| `test_stance_switch` fuhr veraltete Vor-leg_changes-Konstanten (0.13/−0.13) statt der echten Tabelle | 🔴→✅ auf echte Werte umgestellt + Sync-Pin in `test_step_height_modes_node.py` |
| engine-check prüft Transitions OHNE Leveling-Ecken (die laufen im steady-state-`check`) | 🟢 bewusste Grenze, im Plan/Hilfe dokumentiert |
| H2-Prämisse „Schrittweite 0.12 überall" durch H1.2 widerlegt | ✅ Backlog-H2 korrigiert (per-Zelle max-Schrittweite via `_find_max_step_length`) |
