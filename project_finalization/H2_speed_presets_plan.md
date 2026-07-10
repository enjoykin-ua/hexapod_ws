# H2 — Tempo-Presets + Schrittweiten-Deckel (per-Modus step_length_max)

> **Status: 🟡 H2.1–H2.4 + H2.7 umgesetzt — offen: H2.5 Sim-Tuning + H2.6 HW.**
> Stand + Abweichungen: [`H2_speed_presets_progress.md`](H2_speed_presets_progress.md) ·
> Sim/HW-Doku: [`H2_speed_presets_test_commands.md`](H2_speed_presets_test_commands.md).
> ⚠️ **KORRIGIERT in H2.1:** der §0-Wert **mittel sl 0.09** stammte aus dem steady-state-Gate
> und fiel im **engine-check** (Transitions) `B:diagonal` am S4-Probe-Floor (out-of-reach
> d=0.1953 > 0.194) → **finaler mittel-Deckel 0.08** (0.085 GREEN aber nur ~1 mm Reach-Rest;
> konservativ nach H1-Präzedenz). Messreihe im Progress-File.
>
> **Block H (Lauf-Envelope-Ausbau), Nachfolger von H1.** Branch `imu_balance`.
> Arbeitsweise CLAUDE.md §4 (Progress-Checkliste = Done-Vertrag, abhaken in
> `H2_speed_presets_progress.md`), §5 (Agent macht NIE git — User committet), Deutsch.

---

## 0. Kontext + IST-Stand (nichts davon neu rechnen!)

- **H1 (Schritthöhen-Modi) Code+Offline fertig** (Sim-/HW-Smoke H1.4–1.6 offen, pausiert):
  `_STANCE_MODES` = tief (0.160, −0.065, 0.04) / mittel (0.160, −0.080, 0.05) / hoch
  (0.160, −0.100, 0.08); `step_height`-Deckel = Tabellenwert (Reject im Validator-Block
  „1h2" in `gait_node._on_param_change`) + Init-Deckelung von Boot-Overrides; Suite
  **440 gait / 43 kin / 18 Tool-Tests** grün.
- **Gate-validierte max-Schrittweiten je Modus** (voll-Gate `--min-margin 0.10
  --leveling-deg 4.0 --s4-floor 0.03 --scenario all`, exit-code-basiert gemessen):
  **tief 0.06 · mittel 0.09 · hoch 0.05.** Anschauung: Hub und Schrittweite teilen die
  Bein-Hülle — hoch = Terrain-Modus (hoher Schwung, kurze Schritte), mittel = Speed-Modus.
- **User-Sim-Repro:** hoch + `step_length_max 0.12` → out-of-reach-IKError (d≈0.20 >
  reach 0.194) bei Misch-Kommandos = die H1.2-RED-Zelle live bestätigt. `step_length_max`
  ist heute UNgedeckelt — genau die Lücke, die H2 schließt.
- **`cycle_time` ist envelope-frei** (Hülle hängt an Schrittweite/Hub/Höhe/Radius, nicht
  am Tempo) → die Tempo-Stufen brauchen KEINE neue Envelope-Rechnung.
- **Werkzeuge fertig (H1.1):** `walking_envelope_check` mit `--min-margin/--leveling-deg/
  --s4-floor` + `engine-check` (Transitions); `tools/apex_meter.py`. ⚠️ Ausgaben IMMER
  **exit-code-basiert** auswerten (H1.2-Lehre: `grep|tail` übersah RED-Szenarien).

**User-Entscheide (§4-Vorab, eingeholt):**
1. `step_length_max` wird **fester Tabellenwert pro Stance-Modus** (wie step_height:
   Switch setzt, darüber Reject) — der Stick moduliert die reale Schrittweite ohnehin.
2. Umschalten der Tempi: **Service + PS4-Taste** (analog Stance-Cycle), nur im Stand.
3. **D-Pad ↑/↓ wird umgewidmet**: von Schrittweiten-Adjust (C3) auf Tempo-Cycle
   (↑ schneller / ↓ langsamer). ←/→ bleibt Gangart.
4. Tempo-Stufen-**Startwerte**: aggressiv 1.5 / schnell 2.0 (= Boot) / mittel 2.6 /
   langsam 3.3 — **im Sim-Test live verstellbar, finale Werte danach in die Tabelle**
   (Muster hw_balance: Code trägt Startwerte, Tuning-Ergebnis wird nachgezogen).

## 1. Logik-Skizze

### H2-A: Schrittweiten-Deckel (gait_node — exakt das H1-Deckel-Muster kopieren)
- `_StanceMode` um Feld `step_length_max` erweitern → Tabelle
  `('tief', 0.160, −0.065, 0.040, 0.060)` / `('mittel', …, 0.050, 0.090)` /
  `('hoch', …, 0.080, 0.050)`.
- `_do_stance_switch`: zusätzlich `self._step_length_max` + `engine.step_length_max`
  auf den Modus-Wert setzen (Member-/Attribut-Namen im Code verifizieren — Handoff §7).
- Validator (`_on_param_change`, neben Block „1h2"): `step_length_max` > Modus-Deckel →
  Reject (`exceeds validated max … for stance mode …`); kleinere Werte immer erlaubt.
- Init-Konsistenz-Check (wie H1): Boot-Override > mittel-Deckel → WARN + deckeln.
- **Param-Default `step_length_max` 0.05 → 0.09** (Konvention Boot = mittel =
  Param-Defaults). Verhaltens-Hinweis: real ändert sich das Tempo dadurch NICHT —
  die joy-Scales begrenzen das Stick-Kommando; erst die Tempo-Presets heben sie.
- **H1-🟡-Fix gleich mit — ABER deferred (Code-verifiziert!):** `body_height` und
  `radial_distance` sind **standing_only** — ein `self.set_parameters` direkt in
  `_do_stance_switch` würde vom EIGENEN Validator rejected (State = STANCE_SWITCH).
  Design: `_do_stance_switch` setzt nur ein Flag `_pending_stance_param_sync`; der
  `_tick` führt den Sync aus, sobald `engine.state == STANDING` (dort existiert
  bereits das State-Transition-Muster „STARTUP_RAMP → STANDING"). Sync = die vier
  gekoppelten Params (`radial_distance`, `body_height`, `step_height`,
  `step_length_max`) via `self.set_parameters`; `_stance_idx` ist zu dem Zeitpunkt
  schon aktuell → Deckel-Validatoren passieren. `_apply_param`-Idempotenz verifizieren.
- **C3-Service mit-deckeln:** `/hexapod_adjust_step_length` schreibt
  `self._step_length_max` direkt (gait_node ~Z. 2338, Intent-Handler) — dort
  zusätzlich auf den Modus-Deckel clampen (sonst umgeht der Service den Validator).

### H2-B: Tempo-Presets (Ownership: joy_to_twist — der UX-Besitzer)
- **`_TEMPO_MODES`-Tabelle im Teleop** (`joy_to_twist.py`):
  `(name, cycle_time, linear_x_scale, linear_y_scale, angular_z_scale)` —
  **Startwerte (Code-verifiziert gegen ps4_usb.yaml!):**
  · **schnell (Boot-Index) = (2.0, 0.05, 0.05, 0.46) = EXAKT die heutigen
    YAML-Scales** — der erste D-Pad-Druck darf KEINEN Verhaltens-Sprung erzeugen
  · aggressiv = (1.5, 0.17, 0.13, 1.2) = User-erprobt
  · mittel = (2.6, 0.04, 0.04, 0.35) · langsam = (3.3, 0.03, 0.03, 0.28)
    (von schnell runterskaliert — alles H2.5-Tuning-Startpunkte, live verstellbar).
  Hinweis: die Scales sind cmd-Limits; die Engine clampt zusätzlich proportional auf
  `linear_max = step_length_max/stance` (aggressiv 0.17 > linear_max ⇒ WARN+clamp,
  bekannt/ok). `ps4_bt.yaml` auf identische Scale-Werte prüfen (Layout = USB).
- **D-Pad ↑/↓** (bisher `/hexapod_adjust_step_length`): cyclet den Tempo-Index
  (geklemmt, kein Wrap). Ablauf pro Wechsel: (1) `cycle_time` am **gait_node** via
  `AsyncParameterClient` setzen — der gait-seitige standing_only-Guard lehnt
  außerhalb STANDING ab → dann NICHTS lokal ändern + throttled Log („Tempo nur im
  Stand"); (2) bei Erfolg die eigenen Scales aus der Tabelle setzen (durch die
  bestehende validate-then-apply-Live-Mechanik der TLS-Scales). So bleiben gait und
  Teleop konsistent, der Guard lebt an EINER Stelle (gait).
- Der gait-Service `/hexapod_adjust_step_length` (C3) **bleibt bestehen**
  (rückwärtskompatibel, nur das Teleop-Binding wandert); in Doku als „ohne
  Teleop-Binding" markieren. Wert-Adjust wird durch den neuen sl-Deckel begrenzt.
- Alternative (verworfen, nur falls AsyncParameterClient hakt): gait_node-Service
  `/hexapod_cycle_tempo` + Tempo-Topic, Teleop folgt — mehr Schnittstellen, Tabelle
  läge im falschen Node (Scales sind Teleop-Domäne).

### H2-C: Offline-Nachzug (klein)
Die sl-Deckel-Zellen durch den **engine-check** (H1.2 lief mit sl 0.05):
tief/0.04/**0.06** und mittel/0.05/**0.09** (hoch/0.08/0.05 ist bereits GREEN,
inkl. Switch/Sitdown/Reposition). Befehle in §7.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Warum |
|---|---|---|
| gait: Tabellen-Pin um sl erweitert (`test_step_height_modes_node`) | Vertrag | Werte-Änderung nur mit neuem Gate |
| gait: sl-Reject über Modus-Deckel (0.09 in hoch → fail; 0.05 → ok) | Deckel | der heutige out-of-reach-Befund |
| gait: Deckel folgt Modus (tief 0.07 fail / mittel 0.09 ok) | Kopplung | analog step_height |
| gait: Switch setzt sl mit (hoch → 0.05, zurück mittel → 0.09) | Auto-Deckelung | „nur valide durchschaltbar" |
| gait: Init-Deckelung sl-Boot-Override | params_file-Lücke | wie H1 |
| gait: **Param-Server-Sync nach Switch-ABSCHLUSS** (`ros2 param get` == Member; Sync erst bei STANDING — body_height/radial sind standing_only!) | H1-🟡-Fix | zwei gekoppelte Params machen die Drift sonst sichtbar; Sync im STANCE_SWITCH würde selbst-rejected |
| gait: `/hexapod_adjust_step_length` clampt auf Modus-Deckel | Umgehungs-Schutz | der Intent-Handler schreibt am Validator vorbei |
| teleop: D-Pad ↑/↓ cyclet Tempo (Index, Klemmen) + Scales gesetzt | UX-Kern | Umwidmung C3 |
| teleop: gait lehnt ab (nicht STANDING) → Scales UNVERÄNDERT + Log | Konsistenz | kein halber Tempo-Wechsel |
| teleop: bestehende TLS-/joy-Tests grün (`test_live_scales`, `test_joy_to_twist`) | Back-Compat | C3-Umbau reißt nichts |
| Suiten: gait/kinematics/teleop + Lint grün | Gate | Baseline 440/43 + teleop |

**Bewusst NICHT:** neue Envelope-Rechnung für Tempo (envelope-frei) · Nicht-Tripod
(eigene Runde) · Teleop-Taste für Stance-sl-Feintuning (Stick moduliert).

## 3. Progress-Checkliste (→ `H2_speed_presets_progress.md`, Done-Vertrag)

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

## 4. Test-Anleitung (Skizze — `H2_speed_presets_test_commands.md` nach Implementierung)

Sim: 3-Terminal-Bringup (Welt frei wählbar, siehe H1-Doku) → D-Pad-Tempo-Durchschalten je
Stance-Modus → Tuning-Block (`ros2 param set /gait_node cycle_time …` +
`/joy_to_twist *_scale …` live, Tabelle Default/↑/↓/woran-erkennbar) → finale Werte melden.
HW: hw_terrain-Bringup (HW8.8a-Muster) + aggressiv-Bahnen (Strom in Terminal 1 beobachten).

## 5. Sicherheit
Tempo-Wechsel nur im Stand (gait-Guard, EINE Stelle). sl-Deckel verhindert die
out-of-reach-Zone. HW-aggressiv zuerst aufgebockt kurz sichten, dann Boden (§9);
Servo-Speed ist die unbewiesene Größe (cycle 1.5 lief auf HW bereits — Referenzpunkt).

## 6. Offene Punkte (im Implementier-Chat klären/verifizieren, KEINE User-Fragen nötig)

1. ✅ **Vorab-verifiziert (dieser Chat):** `AsyncParameterClient` existiert in rclpy Jazzy ·
   `self._step_length_max` + Engine-Konstruktor-Arg `step_length_max` existieren ·
   D-Pad: `axis_dpad_y` (↑/↓ heute Schrittweite) + `dpad_lockout_sec`-Debounce in
   `joy_to_twist.py` Z. ~70–78 · heutige ps4_usb.yaml-Scales = 0.05/0.05/0.46 ·
   **standing_only-Liste:** gait_pattern, cycle_time, tick_rate, **body_height**,
   **radial_distance**, standup_*, reposition_cycle_time, body_height_min/max (deshalb
   Sync deferred, §1-A).
2. `set_parameters`-Selbstaufruf im deferred Sync: Rekursion/`_apply_param`-Idempotenz
   verifizieren; Engine setzt `step_length_max` wie? (Attribut vs. nur Konstruktor —
   `_adjust_step_length`-Handler Z. 2338 ff. als Vorbild ansehen).
3. AsyncParameterClient-Antwort ist eine **Future** — Scales erst im done-Callback
   setzen (joy_to_twist ist event-getrieben, nicht blockieren); Timeout-Fall (gait_node
   weg) = nichts ändern + throttled WARN.
4. `ps4_bt.yaml`-Scales gegen ps4_usb.yaml abgleichen (Layout identisch laut C4).
5. Tempo-Anzeige: Log reicht (kein Topic) — bei Bedarf später.
6. hw_terrain.yaml: braucht KEINEN Tempo-Eintrag (Boot = schnell/2.0/heutige Scales =
   heutiges Verhalten, per Design sprungfrei).

## 7. Handoff-Anker für den nächsten Chat (ZUERST LESEN, Reihenfolge)

1. `CLAUDE.md` (§4 Plan→Freigabe→Code→Tests→Self-Review, §5 NIE git, Deutsch) + `PHASE.md`.
2. `project_architecture/ai_navigation.md` — Abschnitte „Stance-Modi" (H1-Absatz!),
   „Teleop-Mapping" (TLS-Live-Scales-Falle), „Gait-Parameter tunen".
3. **Dieser Plan** + [`H1_step_height_modes_plan.md`](H1_step_height_modes_plan.md) §0
   (korrigierte Datenlage) + [`H1_step_height_modes_progress.md`](H1_step_height_modes_progress.md)
   (Werte-Tabelle + Self-Review-Lehren).
4. Code-Muster (nur lesen): `gait_node.py` — `_STANCE_MODES`/`_StanceMode` (~Z. 560–585),
   Validator-Block „1h2" in `_on_param_change`, Init-Deckel nach dem step_height-Read
   (~Z. 625), `_do_stance_switch`; `test/test_step_height_modes_node.py` (das
   Test-Muster inkl. Boot-Override-Fixture); `joy_to_twist.py` — D-Pad-Intents (C3) +
   `_on_param_change`-TLS-Muster; `hexapod_teleop/test/test_live_scales.py`.
5. Tools (fertig, nur benutzen): `tools/walking_envelope_check.py` —
   Gate: `check --radial R --body-height BH --step-height SH --step-length SL
   --min-margin 0.10 --leveling-deg 4.0 --s4-floor 0.03 --scenario all`;
   Transitions: `engine-check … --switch-to "R,BH,SH" --s4-floor 0.03`.
   **Exit-Code auswerten, nie grep|tail.**
6. Build/Test-Baseline: `colcon build --packages-select hexapod_gait hexapod_teleop` ·
   `colcon test --packages-select hexapod_gait hexapod_kinematics hexapod_teleop` +
   `colcon test-result --test-result-base build/<pkg> --verbose` — Stand vor H2:
   **440 gait / 43 kin grün** (+ teleop-Baseline beim Start erheben) ·
   Tool-Tests: `python3 -m pytest tools/test_walking_envelope_check.py -q` → 18 passed.
7. Branch `imu_balance`, **User committet selbst** (Befehle nur vorschlagen).
   Bekannter vorbestehender Lint-Fail: `hexapod_bringup` copyright `rubicon.launch.py`
   (nicht anfassen, dokumentiert).
8. Kontext-Randnotizen: H1.4–1.6 (Sim/HW-Smoke) sind PAUSIERT, nicht fertig — H2 nicht
   damit vermischen; Block-Stufe-8-Rest ebenfalls pausiert (A5); PHASE.md-A5-Zeile ist
   bekannt veraltet (Update beim Block-Abschluss).
