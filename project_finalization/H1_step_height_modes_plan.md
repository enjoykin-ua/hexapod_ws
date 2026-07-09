# H1 — Schritthöhen-Modi (per-Stance-Höhe validierte step_height + radial)

> **Status: 🟡 Plan — §6 mit User geklärt → Freigabe → Implementierung.**
> **Block H (Lauf-Envelope-Ausbau).** Motivation: fürs Laufen auf echtem Terrain (draußen,
> Steinchen) braucht der Roboter deutlich mehr Fuß-Hub. Heute: `step_height` einheitlich 0.04
> über alle Stance-Modi; User-Beobachtung auf HW: davon kommen optisch nur ~1,5–2 cm an.
> Ziel: **pro Stance-Modus die maximal valide Schritthöhe** — tief 0.04 (bleibt) / mittel 0.06 /
> **hoch 0.10** (mit per-Modus-Radius 0.17–0.18, User-Entscheid) — als **gekoppelte, nur-valide-
> schaltbare Presets** (L2/R2 schaltet automatisch die validierte Kombination durch; manuelles
> Überschreiten → Reject).
>
> **User-Entscheide (Vorab):** keine neue Körperhöhe (−0.110/−0.120 gestrichen; bestehende 3
> Höhen) · hoch-Ziel **0.09 UND 0.10** erreichen — per-Modus-**radial** (0.17–0.18) dafür ok,
> Reposition beim Modus-Wechsel akzeptiert · Deckel-Semantik = **Reject** (kein Clamp) ·
> zuerst **tripod**, andere Gangarten als zweite Runde · Tempo-Presets = **H2** (eigener Plan).

---

## 0. Offline-Datenlage (walking_envelope_check, echte URDF-Limits)

Grenze überall: Schwung-Apex (`body_height + step_height`) ≤ ~−0.02 (Femur-Wand). Gemessen
(Szenario `all`, step_length 0.05 **und** 0.12):

| Modus | body_height | radial | sh 0.04 | 0.06 | 0.08 | 0.09 | 0.10 |
|---|---|---|---|---|---|---|---|
| tief | −0.065 | 0.160 | ✓ | ❌ | ❌ | — | — |
| mittel | −0.080 | 0.160 | ✓ | ✓ | ❌ | — | — |
| hoch | −0.100 | 0.160 | ✓ | ✓ | ✓ | ✓ | ❌ |
| hoch | −0.100 | **0.170** | — | — | — | ✓ | ✓ |
| hoch | −0.100 | **0.180** | — | — | — | ✓ | ✓ |

(step_length 0.12 = Aggressiv-Schrittweite ändert daran nichts — alle ✓-Zellen bleiben GREEN.)

⚠️ **Bekannte Falle — Ursache jetzt Code-verifiziert:** `walking_envelope_check` nutzt zwar
schon die **echte `GaitEngine`** (`check_envelope`: `set_command` + `compute_joint_angles`),
ist aber aus vier Gründen am Femur-Rand zu optimistisch:
(1) es prüft **nur eingeschwungenes Laufen** (2 Zyklen konstantes Kommando) — keine Übergänge
(Stopp-Settle, Richtungswechsel im Lauf, Stance-Switch, Sit/Stand-Reposition; dort trat der
Stance-Modi-Befund auf); (2) **binär in-limit ohne Margen-Schwelle** (GREEN bei 0.001 rad
Restabstand — auf HW kommen Cal-Toleranz + Servo-Quantisierung dazu); (3) **Leveling fehlt**
(bis 4° Rotation im WALKING, mit `hw_terrain` immer aktiv — verschiebt alle Gelenkwinkel);
(4) 50 statt 100 Ticks/Zyklus. Alle vier werden in H1.1 **im Tool** behoben — die Rand-Zellen
(mittel 0.06, hoch 0.09/0.10) sind erst danach „wirklich grün".

## 1. Logik-Skizze

### H1.1 Tool-Erweiterung `walking_envelope_check` (Optimismus entschärfen)
- **Margen-Report + `--min-margin <rad>`:** pro Joint den minimalen Abstand zum URDF-Limit über
  den ganzen Lauf ausweisen; GREEN nur, wenn Marge ≥ Schwelle (Default-Vorschlag 0.10 rad,
  Femur-Faustregel 0.15 als dokumentierte Empfehlung). Gilt auch fürs bestehende `check`.
- **`--leveling-deg <deg>`:** Worst-Case-Leveling-Rotation (z. B. 4.0 = Walking-Clamp) via
  `engine.set_body_orientation_offset` in den Lauf einrechnen — prüft erstmals die Kombination
  Leveling × Schritthöhe (bisher nur getrennt via `leveling_envelope_check`).
- **Neues Subcommand `engine-check` (Transition-Coverage):** fährt zusätzlich zu den 4
  steady-state-Szenarien die **Übergänge**: STANDING→WALKING-Start bei mehreren Phasenlagen,
  Richtungswechsel mitten im Lauf (forward→sidestep→yaw ohne Stopp), STOPPING-Settle,
  Stance-Switch beide Richtungen (mit Radius-Wechsel!), Sit/Stand-Sequenz — IKError = FAIL mit
  Tick/Bein/Joint-Report + Margen-Ausweis. (Muster: `test_mode_walks_all_directions_no_ikerror`.)
- **Volle Tick-Auflösung:** `ticks_per_cycle` an reale `tick_rate × cycle_time` (100) angleichen.
- **Flag `--s4-floor`:** prüft zusätzlich den adaptiven Probe-Floor (`body_height −
  max(touchdown_max_extra_depth, cliff_depth)`) — der tiefste Punkt, den S4-2 real kommandiert.
- **Neues Mess-Skript `tools/apex_meter.py`** (read-only rclpy): abonniert `/joint_states`,
  rechnet per FK die reale Fuß-Höhe, reportet pro Bein die **erreichte Apex-Höhe über Boden**
  (min/avg/max über N Zyklen). Beantwortet auf HW „wie viel von kommandierten 6/9/10 cm kommt
  an" — die Basis, um ggf. cycle_time-Empfehlungen (Lag) abzuleiten.

### H1.2 Offline-Validierung (Gate für die Code-Werte)
Alle Ziel-Zellen per `engine-check` (tripod, step_length bis 0.12, `--s4-floor`):
tief 0.160/0.04 · mittel 0.160/0.06 · hoch 0.170/0.10 **und** 0.180/0.10 (Kandidaten — der mit
mehr Femur-Marge gewinnt) · Fallbacks (mittel 0.05, hoch 0.160/0.09) falls Rand-Zellen fallen.
**Zusätzlich die Übergänge:** Stance-Switch mittel↔hoch mit **Radius-Wechsel** 0.160↔0.17/0.18
(gekoppelte Reposition existiert strukturell — `start_stance_switch` nimmt radial+bh+sh aus der
Tabelle) und Sit/Stand aus hoch@neuem Radius (standup_radial 0.20 → Reposition auf 0.17/0.18 =
kürzerer Weg als heute auf 0.160; bh −0.100 > Sit-Safe −0.115 → kein Routing nötig).

### H1.3 Code (klein, `gait_node.py`)
- **`_STANCE_MODES`-Werte** (nach H1.2-Ergebnis), Ziel:
  `tief (0.160, −0.065, 0.04)` · `mittel (0.160, −0.080, 0.06)` · `hoch (0.17|0.18, −0.100, 0.10)`.
  Der L2/R2-Switch setzt radial/bh/sh bereits gekoppelt (bestehende Mechanik) → **nur valide
  Kombinationen durchschaltbar**, keine neue Schalt-Logik.
- **Per-Modus-`step_height`-Deckel im Validator** (Reject): `param set step_height X` mit
  X > Deckel des **aktuellen** Modus → `Set parameter failed` mit Begründung
  (`max step_height for mode '<name>' is <Y>`). Deckel-Quelle = neues Feld in `_StanceMode`
  (`step_height_max`, = validierter Tabellenwert). Modus-Wechsel selbst setzt sh eh aus der
  Tabelle (auto-Deckelung beim Runterschalten).
- **Param-Default-Kopplung (Konvention „Boot-Pose = Index 1 (mittel) = Param-Defaults"):**
  der `step_height`-Param-Default steigt mit 0.040 → **0.060** (mittel-Tabellenwert), sonst
  bootet der Node inkonsistent zur Tabelle. `body_height`/`radial_distance`-Defaults bleiben
  (mittel unverändert −0.080/0.160). Presets, die sh explizit setzen (z. B. `sim_walk` 0.04),
  bleiben gültig (unter dem Deckel).
- **Kein Engine-Code** — Engine ist wertneutral (Werte leben in Tabelle/Presets).

### H1.4 Sim + HW
Sim-Smoke (Höhen durchschalten, laufen, Übergänge) → HW aufgebockt (`apex_meter`: reale
Apex-Höhe je Modus, ggf. × cycle_time-Varianten) → HW Boden (Terrain-Probe: Steinchen/Stufe
mit hoch-Modus) → `hw_terrain.yaml` auf hoch + finale Werte nachziehen.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Warum |
|---|---|---|
| Tool: `engine-check` meldet bekannte RED-Zelle (tief/0.08) als FAIL | Detektionskraft | sonst validiert das neue Gate nichts |
| Tool: `engine-check` GREEN für bestehende Modi (tief/mittel/hoch @ 0.04) | kein False-Positive | heutige validierte Werte müssen durchgehen |
| Tool: `--s4-floor` verschiebt Floor korrekt | S4-Kopplung | Probe-Floor ist der echte Tiefstpunkt |
| Node: `_STANCE_MODES`-Werte + Switch setzt sh/radial gekoppelt | die Kern-Kopplung | „nur valide durchschaltbar" |
| Node: Deckel-Reject je Modus (0.08 in tief → fail; 0.10 in hoch → ok) | Reject-Semantik | User-Entscheid, verhindert IKError+Freeze auf HW |
| Node: full-cycle alle 4 Richtungen je Modus mit neuen Werten (echte Engine) | die eigentliche Validierung | `test_stance_switch`-Erweiterung |
| Node: Übergänge tief↔mittel↔hoch inkl. Radius-Wechsel, kein IKError | Reposition-Kopplung | hoch bricht den Einheits-Radius |
| Node: Sit/Stand aus hoch@neuem Radius | Sequenz-Sicherheit | Standup-Reposition-Ziel ändert sich |
| Node: Richtungswechsel im Lauf je Modus (fwd→side→yaw ohne Stopp) | Bahn-Sprünge | die vom alten Tool ungeprüfte Transition-Klasse |
| Tool: Margen-Schwelle lehnt knappe GREEN-Zelle ab (`--min-margin`) | Optimismus-Fix | der eigentliche H1.1-Kern |
| Bestehende Suite grün (431 gait / 43 kin) | Back-Compat | Tabellenwerte ändern Default-Boot (mittel bleibt Boot-Modus, sh 0.06!) — bewusst prüfen |

**Bewusst NICHT (scope-out):**
- **Tempo-Presets** (cycle_time/step_length-Stufen + joy-Scales) → **H2** (envelope-frei, da
  Hülle geschwindigkeitsunabhängig; nur HW-Check aggressiv).
- **Nicht-Tripod-Gangarten** → zweite Runde nach H1 (Hülle identisch, aber kürzere Schwungfenster
  + Open-Loop-Wackeln → eigene HW-Bewertung).
- **Early-Contact „Fuß stoppt auf Erhöhung"** → geparkt (S4-8-Kandidat).
- **Körperhöhen > hoch** (−0.110/−0.120) → gestrichen (User-Entscheid).

## 3. Progress-Checkliste (→ `H1_step_height_modes_progress.md`, Done-Vertrag)

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

## 4. Test-Anleitung (Skizze — Datei `H1_step_height_modes_test_commands.md` nach Implementierung)

Sim: Ein-Befehl-Bringup + L2/R2-Durchschalten + Fahren je Modus (A/B alt/neu). HW: 3-Terminal-
Bringup (HW8.8a-Muster) + `apex_meter`-Aufruf + Melde-Format (Apex-Real-Werte je Modus); Terrain-
Probe hoch-Modus. Param-Tabellen: step_height je Modus (Deckel), cycle_time-Einfluss auf
Real-Apex.

## 5. Sicherheit (CLAUDE.md §9)

Wie gehabt: Sim → HW aufgebockt → Boden; Kill-Switch; hoch-Modus mit 10-cm-Schwüngen zuerst
aufgebockt ansehen (größte Bewegung, höchster CoG); IKError+Freeze bleibt Backstop; Deckel-
Reject reduziert die Fehlbedienungs-Fläche.

## 6. Offene Punkte — Stand

1. **hoch-radial 0.17 vs 0.18:** ✅ Vorgehen geklärt (beide engine-checken, Marge entscheidet);
   finaler Wert = H1.2-Ergebnis.
2. **hoch-sh 0.10 fällt im engine-check durch?** → Fallback-Treppe 0.09 @ 0.17/0.18, dann
   0.09 @ 0.160 (offline GREEN), dann 0.08. User will 0.09–0.10 — erst Daten, dann festnageln.
3. **mittel 0.06 fällt durch?** → 0.05 als Fallback (offline GREEN mit Marge).
4. 🟡 **Default-Boot-Verhalten:** Boot-Modus bleibt „mittel" — dessen sh steigt 0.04→0.06.
   Bewusst ok? (Alternative: Tabelle neu, aber Boot-sh-Param-Default bleibt 0.04 bis zum ersten
   Switch — inkonsistent, nicht empfohlen.)
5. 🟡 **`stance_switch_step_height` (0.025):** bleibt für die Übergangs-Schwünge (Apex unter
   Femur-Wand bei Zwischenhöhen) — H1.2 prüft die Übergänge mit; nur bei Befund anfassen.
6. 🟡 **Apex-Verlust-Befund (H1.5):** wenn Real-Apex ≪ kommandiert bleibt → cycle_time-Empfehlung
   je Modus in die Doku (kein Code); Einfedern der Stützbeine ist open-loop nicht behebbar.
7. 🟡 **Boot-Override umgeht den Deckel:** `params_file`-Werte greifen zur Deklarations-Zeit
   (vor Registrierung des Set-Callbacks) — ein Preset mit sh > Deckel würde beim Start NICHT
   rejected. Fix im Scope: einmaliger Konsistenz-Check im Init (WARN + auf Deckel setzen),
   sonst bleibt IKError+Freeze der Backstop.
8. 🟡 **Show-Pose (B4) aus hoch@0.17/0.18:** der CoG-/Reach-Beweis der Show-Pose lief auf dem
   alten Setup (Einheits-Radius 0.160). Vor Freischalten der Show im neuen hoch-Modus:
   `tools/show_pose_cog_check.py` + Offset-Worst-Case mit neuem Radius nachrechnen — sonst
   Show im hoch-Modus zunächst als „ungeprüft" dokumentieren.
9. 🟡 **Deckel gilt pro Modus, nicht pro (Modus, radial):** wer `radial_distance` manuell
   verstellt, verlässt das validierte Preset-System — der Deckel bleibt dann nur Näherung,
   IKError+Freeze bleibt Backstop (dokumentieren, kein Extra-Code).
10. 🟡 **Leveling-Marge:** die Ziel-Zellen werden mit `--leveling-deg 4.0` (Walking-Clamp)
   validiert, weil `hw_terrain.yaml` Leveling dauerhaft aktiviert — fällt eine Zelle NUR mit
   Leveling durch, entscheidet die Fallback-Treppe (§6.2), nicht ein Leveling-Verzicht.

## 7. Doku-Nachzug (nach Implementierung)
`H1_..._progress.md` (Checkliste + Self-Review) · `H1_..._test_commands.md` · `00_backlog.md`
(Block H) · `hexapod_gait/README.md` · `ai_navigation.md` (Stance-Modi + Tool) ·
`tools_catalog.md` · `hw_terrain.yaml` · PHASE.md (Block-Zeile) bei Block-Abschluss.
