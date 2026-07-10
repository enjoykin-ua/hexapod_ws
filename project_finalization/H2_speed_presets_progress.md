# H2 — Tempo-Presets + Schrittweiten-Deckel — Progress

> **Done-Vertrag** (CLAUDE.md §4). Bullets 1:1 aus [`H2_speed_presets_plan.md`](H2_speed_presets_plan.md) §3.
> Alle `[x]` = H2 fertig; pro erledigtem Bullet sofort abhaken (nicht batchen).
> Post-Review-Tabelle nach Implementierung (`OK` / 🔴 fixen / 🟡 vormerken / 🟢 später).
>
> **Kern-Entscheide (User, §0 des Plans):** `step_length_max` = fester Tabellenwert pro
> Stance-Modus (Gate-validiert) · Tempo = nur `cycle_time` + joy-Scales (envelope-frei) ·
> Umschalten Service+PS4, **D-Pad ↑/↓ umgewidmet** von Schrittweiten-Adjust (C3) auf
> Tempo-Cycle · Startwerte **aggressiv 1.5 / schnell 2.0 (Boot) / mittel 2.6 / langsam 3.3**
> — im Sim-Test live tunen, finale Werte in die Tabelle nachziehen.
>
> ⚠️ **Abweichung vom §0-Plan-Wert (H2.1-Gate-Befund): mittel-sl-Deckel = 0.08, NICHT 0.09.**
> Der §0-Wert 0.09 stammte aus dem steady-state-Gate (H1.2); der H2.1-**engine-check**
> (Transitions) riss bei 0.09 im `B:diagonal`-Richtungswechsel den S4-Probe-Floor
> out-of-reach (d=0.1953 > reach 0.194). 0.085 GREEN mit nur ~1 mm Reach-Rest,
> **0.08 GREEN mit Marge** (femur 0.159) → konservativ 0.08 (H1-Präzedenz „Schwelle
> glaubwürdig halten"). Messreihe unten. Finale Tabelle: **tief 0.06 / mittel 0.08 / hoch 0.05.**

```
H2 (Tempo-Presets + Schrittweiten-Deckel):
- [x] H2.1 Offline: engine-check-Transitions für die sl-Deckel-Zellen exit-code-basiert (hoch 0.08/0.05 bereits H1.2)  [tief 0.04/0.06 GREEN (inkl. Switch→mittel @ sl 0.06); mittel 0.05/0.09 RED (B:diagonal, S4-Floor out-of-reach d=0.1953>0.194) → Treppe: 0.085 GREEN (knapp, ~1 mm Reach), 0.08 GREEN (femur-Marge 0.159) → mittel-Deckel = 0.08. mittel-Lauf OHNE --switch-to: der C:walk_target_mode-Pfad führe mit der QUELL-sl im Zielmodus — genau das unreale Szenario, das die H2-Kopplung verhindert; die Switch-Motion selbst ist sl-unabhängig + H1.2-validiert]
- [x] H2.2 gait_node: _StanceMode+step_length_max (0.06/0.08/0.05) + Switch setzt sl (Node+Engine) + Validator-Reject (Block 1h3) + Init-Deckelung + Param-Default 0.050->0.080 + adjust_step_length-Handler auf Modus-Deckel geclampt + Param-Server-Sync DEFERRED nach Switch-Abschluss via _maybe_sync_stance_params im _tick, VOR dem _pending_sitdown-Check (H1-Puffer-Fix)  [zusätzlich: step_length_intent_max 0.070->0.080 (sonst SENKT ein „größer"-Intent den Boot-Wert 0.08 auf 0.07 — Clamp-Artefakt) + gait.launch.py-Defaults nachgezogen (sl 0.050->0.080 UND sh 0.040->0.050 — H1-Leftover, Launch-Arg überschrieb den Node-Default)]
- [x] H2.3 joy_to_twist: _TEMPO_MODES (schnell/Boot = 2.0 + HEUTIGE YAML-Scales 0.05/0.05/0.46 [sprungfrei, per Test gepinnt]; aggressiv 1.5/0.17/0.13/1.2; mittel 2.6/0.04/0.04/0.35; langsam 3.3/0.03/0.03/0.28) + D-Pad hoch/runter = Tempo-Cycle (cycle_time via AsyncParameterClient-Future an gait, Ablehnung/Exception/Timeout -> kein lokaler Scale-Wechsel + Log; Pending-Lock + 2s-Timeout-Freigabe gegen Request-Stau) + adjust_step_length-Binding entfernt (Service bleibt) + ps4_usb/bt.yaml-Kommentare (Scales == schnell-Eintrag halten)
- [x] H2.4 Tests: gait +9 (sl-Tabellen/Default-Pin, intent_max-Invariante, Init-Deckel via Override 0.12, Reject/erlaubt, Deckel folgt Modus, Switch-Kopplung, Sync-deferred-bis-STANDING, adjust-Clamp in hoch) · teleop +11 (test_tempo_presets.py: Tabellen-Pin, Sprungfrei-Invariante Code UND YAML usb+bt, Cycle hoch/runter+Param-Sync, Klemmen, Reject/Exception/absent/Timeout-Lock; test_joy_to_twist D-Pad-↑/↓ umgewidmet) · Suiten 449 gait / 43 kin / 53 teleop + Lint gruen (Baseline 440/43/42) · Tool-Tests 18 passed · test_param_callback-linear_max-Erwartung 0.025->0.040 (folgt neuem sl-Default)
- [ ] H2.5 Sim: Tempo-Stufen durchschalten + Werte-TUNING (User: Startwerte live verstellen) -> finale _TEMPO_MODES-Werte nachgezogen + erneut Tests
- [ ] H2.6 HW: aggressiv-Realitaets-Check (Servo-Speed/Strom/Stabilitaet, hw_terrain-Alltags-Setup) + Tempo-Wechsel im Feld  [🟡 Zwischenbefund 1: aggressiv @ hw_terrain → S4-4-False-Positive-Freeze („Stütz-Verlust 1 Bein") — S4-Slip-Params waren auf cycle 2.0 geeicht, bei 1.5 wird der feste Kontakt-Lag ein größerer Phasen-Anteil + mehr Wackeln/Servo-Lag. ✅ Fix (User-Entscheid „Option B"): hw_terrain.yaml → slip_debounce_ticks 14 + slip_min_lost_legs 2, Werte-Pin `test_hw_terrain_preset.py` (+2 Tests → 451 gait; Code-Sim-Defaults 8/1 unverändert, kein bestehender Test betroffen). ⚠️ Tradeoff dokumentiert: Kanten-Schutz greift erst ab 2 Beinen (Tip+IKError bleiben Backstop). Recovery-Prozedur (R1 los → /hexapod_safety_reset) in test_commands. aggressiv-Wiederholung auf HW ausstehend]
- [x] H2.7 Doku: README gait (sl-/cycle_time-Zeilen) + teleop (Mapping-Tabelle, Tempo-Konzept-Abschnitt inkl. AsyncParameterClient-Idiom, L2/R2-Zeile + Tests-Abschnitt entstaubt), ai_navigation (Stance-Modi: 5. Feld + deferred Sync + adjust-Clamp + Zwei-Gates-Lehre + Launch-Default-Falle; Teleop-Mapping: Tempo-Presets-Eintrag mit Fallen), Backlog H2-Zeile, Plan-§0-Korrektur-Vermerk, H2_speed_presets_test_commands.md (self-contained: H2.5a Funktions-Durchlauf + H2.5b Tuning-Block mit Param-Tabelle Default/kleiner/groesser/woran-erkennbar + H2.6 HW-Treppe/Dauerprobe + Melde-Formate)
- [x] H2.8 kritische Self-Review-Tabelle (unten)
```

## Kritischer Self-Review (H2.8, nach H2.1–H2.4+H2.7; final nach H2.5/H2.6)

| Punkt | Status |
|---|---|
| **§0-Plan-Wert mittel sl 0.09 riss das eigene H2.1-Gate** (engine-check B:diagonal @ S4-Floor; steady-state-Gate hatte ihn GREEN gemeldet) — datenbasiert auf **0.08** korrigiert statt den Done-Vertrag („exit-code-basiert GREEN") aufzuweichen; H1-Präzedenz „Schwelle glaubwürdig halten" | 🟡 **User-Ack in H2.5**: falls mehr Stride gewünscht — 0.085 ist GREEN, aber nur ~1 mm Reach-Rest im Diagonal-Übergang (Messreihe oben) |
| `gait.launch.py` = **zweite Default-Quelle**, überschrieb den Node-Default (sl 0.050); dabei H1-Leftover gefunden: sh-Launch-Default stand noch auf 0.040 | 🔴→✅ beide nachgezogen (sh 0.050 / sl 0.080) + Falle in ai_navigation verankert |
| `step_length_intent_max` 0.070 < neuer Boot-sl 0.080 → ein „größer"-Intent hätte den Wert GESENKT (Clamp-Artefakt) | 🔴→✅ Default 0.080 + Modus-Deckel-Clamp im Handler + Invarianten-Test (intent_max ≥ sl-Default) |
| Sprungfrei-Invariante war nur gegen Code-Defaults gepinnt — zur Laufzeit kommen die Scales aus den YAMLs (`test_bt_config` prüft nur Keys, nicht Werte) | ✅ YAML-Werte-Pin für ps4_usb UND ps4_bt ergänzt (`test_yaml_scales_match_boot_tempo`) |
| Deferred-Sync-Timing: Sync läuft im ersten STANDING-Tick VOR `set_command` (Tick-Reihenfolge) → auch bei sofort anliegendem cmd_vel kein Fenster, in dem der Sync von WALKING verdrängt wird; VOR `_pending_sitdown` (sonst nie wieder STANDING → stale bis zum nächsten Aufstehen) | OK (Reihenfolge im `_tick` + Kommentar + Test) |
| Wer sh/sl WÄHREND des Switch manuell setzt (nicht standing_only!), bekommt den Wert beim STANDING-Sync auf den Tabellenwert zurückgesetzt | 🟢 Kopplungs-Vertrag (Switch = Preset-Anwendung), kein Fix nötig |
| Manuelles `param set cycle_time` verstellt `_tempo_idx` NICHT → nächster D-Pad-Druck springt auf den Tabellen-Nachbarn des ALTEN Index | 🟢 dokumentiert (test_commands ⚠️-Box beim Tuning-Block); bewusst simpel gehalten |
| Future ohne Antwort (gait_node stirbt zwischen ready-Check und Antwort): Pending-Lock verhindert Request-Stau, 2-s-Timeout gibt den Cycle frei, geändert wird nichts | OK (getestet; Timeout hardcoded — bewusst kein Param) |
| `aggressiv`-Scales > linear_max ⇒ Engine-Clamp + throttled WARN | 🟢 bewusst (Plan §1-B), in Doku + Tabellen-Kommentar erklärt |
| Sync-Fehlschlag (nach Design unmöglich: Tabellenwerte + STANDING) → einmalige WARN, KEIN Retry-Loop (Flag vor dem Call gelöscht) | OK |
| README-Param-Tabelle gait: `body_height −0.052`/`radial 0.27` weiter veraltet (vorbestehender Drift, schon H1-🟡) | 🟡 bleibt vorgemerkt (nicht H2-Scope; nur sl-/cycle_time-Zeilen angefasst) |
| PHASE.md-Block-H-Zeile fehlt weiter (A5-Zeile bekannt veraltet) | 🟢 beim Block-H-Abschluss (nach H2.6) in einem Zug |

## sl-Deckel-Messreihe (H2.1-Ergebnis, engine-check: min-margin 0.10 + s4-floor 0.03)

| Zelle | engine-check | Detail | final |
|---|---|---|---|
| tief 0.160/−0.065/0.04 @ sl **0.06** (+Switch→mittel) | ✅ GREEN | worst femur 0.117 (B:sidestep) | **✅ 0.06** |
| mittel 0.160/−0.080/0.05 @ sl **0.09** (§0-Kandidat) | ❌ RED | B:diagonal @ S4-Floor: d=0.1953 > reach 0.194 (1 Tick out-of-reach) | verworfen |
| mittel @ sl **0.085** | ✅ GREEN | Reach-Rest ~1 mm im selben Pfad — zu knapp | verworfen (konservativ) |
| mittel @ sl **0.08** | ✅ GREEN | worst femur 0.159 (B:sidestep), Reach-Rest ~3.7 mm | **✅ 0.08 (final)** |
| hoch 0.160/−0.100/0.08 @ sl **0.05** | ✅ (H1.2) | Basis + Switch→tief + Sitdown/Repos | **✅ 0.05** |

## Tempo-Tuning-Tabelle (H2.5-Ergebnis — nach Sim-Tuning füllen)

> Start-Scales = Plan §1-B (Code-verifiziert gegen ps4_usb.yaml; die früheren
> Tabellenwerte hier waren ein veralteter Zwischenstand vor dem Sprungfrei-Entscheid).

| Stufe | cycle_time Start | cycle_time final ✍️ | Scales (x/y/z) Start | Scales final ✍️ |
|---|---|---|---|---|
| aggressiv | 1.5 | | 0.17 / 0.13 / 1.2 | |
| schnell (Boot) | 2.0 | | 0.05 / 0.05 / 0.46 (= YAML) | |
| mittel | 2.6 | | 0.04 / 0.04 / 0.35 | |
| langsam | 3.3 | | 0.03 / 0.03 / 0.28 | |
