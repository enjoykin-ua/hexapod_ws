# Block I Phase 11 — Längere Schritte (Stance-Deckel + Tempo-Auslegung) — Plan

> **Status: 🟢 Repo-Seite umgesetzt (P11.1–P11.5) — offen: Sim über die App (P11.6) + HW (P11.7/8).**
> Stand + Messreihen + Self-Review: [`phase_11_stride_envelope_progress.md`](phase_11_stride_envelope_progress.md) ·
> Test-Anleitung: [`phase_11_stride_envelope_test_commands.md`](phase_11_stride_envelope_test_commands.md). Arbeitsweise CLAUDE.md §4 (Plan → Freigabe → Code → Tests →
> Self-Review), §5 (der Agent führt NIE git aus — der User committet selbst), Deutsch.
>
> **Motivation (User, auf echter HW im Gelände):** die Schritte sind zu kurz — gefühlt überall
> ~50 mm, unabhängig vom Stance-Modus.
>
> **Was die Messung ergeben hat:** die Stance-Deckel standen bereits **am geometrischen Optimum**
> (mehr als +5 mm gibt die Bein-Geometrie nicht her, der Fuß-Hub gar nichts). Der eigentliche
> Grund für die kurzen Schritte liegt woanders: **der Roboter schöpft seinen erlaubten Deckel
> nicht aus.** In der Stance „mittel" dürfte er 80 mm — er fährt 50, weil Stick-Skala × Bodenzeit
> nicht mehr hergeben. Diese Phase behebt beides: **B1** hebt die Deckel auf das gemessene
> Maximum, **B2** legt die Tempo-Stufen so aus, dass der Deckel tatsächlich erreicht wird.
>
> **Ergebnis in der Boot-Kombination (Stance „mittel" + Tempo „schnell"): 50 mm → 85 mm
> Schrittweite bei unveränderter Fahrgeschwindigkeit.**
>
> Vorgänger-Datenlage: [`H1_step_height_modes_*`](../H1_step_height_modes_plan.md) (Hub je Höhe) ·
> [`H2_speed_presets_*`](../H2_speed_presets_plan.md) (Schrittweiten-Deckel + Tempo-Presets) ·
> Gate-Kette + Fallen: [`ai_navigation.md`](../../project_architecture/ai_navigation.md)
> „Stance-Modi (3 Lauf-Höhen, Stage 1) ändern".

---

## 0. Die Physik, auf der alles beruht

```
Schrittweite  s  = v × T_stance                T_stance = cycle_time × (1 − swing_duty)
Fahrgeschwind. v = min(joy_scale, linear_max)  linear_max = step_length_max / T_stance
```

`step_length_max` (der Stance-Deckel) ist eine **Erlaubnis**, kein Antrieb. Den Schritt erzeugt
die Stick-Geschwindigkeit mal der Zeit, die der Fuß am Boden bleibt. Heute klemmt in drei von vier
Tempo-Stufen die **joy-Skala** — nicht der Deckel:

| Tempo | cycle | Skala | Schritt heute (mittel) | wer klemmt? |
|---|---|---|---|---|
| langsam | 3.3 | 0.030 | 50 mm | Skala |
| mittel | 2.6 | 0.040 | 52 mm | Skala |
| **schnell (Boot)** | 2.0 | 0.050 | **50 mm** | Skala |
| aggressiv | 1.5 | 0.170 | 80 mm | Deckel |

Zwei **getrennte** physikalische Grenzen begrenzen die Tabellenwerte (die Messung zeigt: sie sind
weitgehend unabhängig voneinander):

- **Fuß-Hub → Femur-Wand (±90°).** Je höher der Fuß schwingt, desto steiler klappt der Oberschenkel.
  Ab `body_height + step_height > −0.020` steht er am Anschlag. Messung an mittel: Hub 50 → 60 mm
  kostet **10,1°** Femur-Reserve (von 12,0° auf 1,9°).
- **Schrittweite → Reichweite (0.074…0.194 m ab Femur-Gelenk).** Der Fuß muss nach vorn ausholen
  **und** dabei 30 mm nach unten tasten können (S4-Kontaktsuche, Worst-Case „Fuß findet keinen
  Boden"). Messung an mittel: Weite 80 → 85 mm kostet nur **0,3°** Femur — hier bindet die Länge,
  nicht der Winkel.

---

## 1. Was umgesetzt wird

### 1.1 B1 — Stance-Deckel auf das gemessene Maximum

| Modus | radial | body_height | step_height | step_length_max | Änderung |
|---|---|---|---|---|---|
| tief | 0.160 | −0.065 | 0.040 | 0.060 → **0.065** | Weite +5 mm |
| **mittel** (Boot) | 0.160 | −0.080 | 0.050 | 0.080 → **0.085** | Weite +5 mm |
| hoch | 0.160 | −0.100 | 0.080 | 0.050 → **0.055** | Weite +5 mm |

**Der Fuß-Hub bleibt in allen drei Modi unverändert** — jede Erhöhung ist datenbasiert verworfen
(§7.1). Alle drei Zellen sind durch **beide** Gates (`check` + `engine-check`) und zusätzlich durch
**alle vier Gangarten** (tripod/wave/tetrapod/ripple) bestätigt.

### 1.2 B2 — Tempo-Auslegung „Geschwindigkeit halten, Schritte länger"

Auslegungsregel: jede Stufe behält ihre heutige Fahrgeschwindigkeit; die **Zykluszeit** wird
verlängert, damit der Fuß länger am Boden bleibt und derselbe Vortrieb in weniger, dafür längeren
Schritten passiert. Die **Stick-Skalen bleiben unverändert** (bis auf die aggressiv-Bremse).

| Stufe | cycle heute → neu | Skala x/y/z heute → neu | v | Schritt @ mittel |
|---|---|---|---|---|
| langsam | 3.3 → **4.0** | 0.030/0.030/0.28 (unverändert) | 0.030 | 60 mm |
| mittel | 2.6 → **3.6** | 0.040/0.040/0.35 (unverändert) | 0.040 | 72 mm |
| **schnell (Boot)** | 2.0 → **3.4** | 0.050/0.050/0.46 (unverändert) | 0.050 | **85 mm** |
| aggressiv | 1.5 → **1.7** | 0.170/0.130/1.20 → **0.100/0.090/0.95** | 0.100 | 85 mm |

Warum die aggressiv-Bremse: dort steht die Skala bewusst über `linear_max`, der Engine-Clamp
stutzt sie. Hebt man den Deckel, hebt sich dieser Clamp mit — die Stufe würde ungewollt schneller.
Mit 0.100 bleibt sie bei ihrer heutigen effektiven Geschwindigkeit (0.107 → 0.100 m/s).

### 1.3 Das Ergebnis (real gefahrene Schrittweite)

| Stance | Tempo | heute | nach Phase 11 |
|---|---|---|---|
| **mittel** | **schnell (Boot)** | **50 mm @ 0.050 m/s** | **85 mm @ 0.050 m/s** |
| mittel | aggressiv | 80 mm @ 0.107 | 85 mm @ 0.100 |
| tief | schnell | 50 mm @ 0.050 | 65 mm @ 0.038 |
| hoch | schnell | 50 mm @ 0.050 | 55 mm @ 0.032 |
| hoch | aggressiv | 50 mm @ 0.067 | 55 mm @ 0.065 |

> ⚠️ **Die eine Nebenwirkung, die man kennen muss:** `linear_max = Deckel ÷ Bodenzeit`. In den
> Modi mit kleinem Deckel (tief, hoch) sinkt durch die längere Zykluszeit die **Höchst-
> geschwindigkeit** in den unteren Tempo-Stufen. Wer im hoch-Modus zügiger will, geht eine Stufe
> höher — „aggressiv" liefert dort 0.065 m/s, praktisch der heutige Wert. Die Monotonie der Stufen
> bleibt in jedem Stance-Modus erhalten (v steigt von langsam nach aggressiv).

---

## 2. Logik-Skizze (Code-Änderungen)

### 2.1 B1 — Deckel (nur Zahlen, keine neue Mechanik)

```python
# gait_node.py — _STANCE_MODES (+ Kommentarblock mit der neuen Gate-Historie)
_StanceMode('tief',   0.160, -0.065, 0.040, 0.065),
_StanceMode('mittel', 0.160, -0.080, 0.050, 0.085),
_StanceMode('hoch',   0.160, -0.100, 0.080, 0.055),
```

| Stelle | heute → neu | warum |
|---|---|---|
| `_GAIT_PARAMS['step_length_max'].default` | 0.080 → **0.085** | Boot = Index 1 (mittel) |
| `_GAIT_PARAMS['step_length_intent_max'].default` | 0.080 → **0.085** | sonst **senkt** ein „größer"-Intent den Boot-Wert (H2-Bug, per Invarianten-Test gepinnt) |
| `gait.launch.py` `step_length_max` | 0.080 → **0.085** | zweite Default-Quelle; der Sim-App-Pfad (`ramp_walk`) lädt kein params_file → diese Defaults *sind* dort die gefahrenen Werte |
| beide `description`-Texte | Deckel-Aufzählung (tief 0.065 / mittel 0.085 / hoch 0.055) | Doku am Code |

`step_height` bleibt überall unverändert. Keine Engine-Änderung (wertneutral), keine neue
Schalt-Logik: Switch-Kopplung, Validator-Reject und Init-Deckelung existieren bereits.

### 2.2 B2 — Tempo (Tabelle + zwei cycle_time-Defaults)

```python
# joy_to_twist.py — _TEMPO_MODES (name, cycle_time, x, y, z)
_TempoMode('langsam',   4.0, 0.030, 0.030, 0.28),
_TempoMode('mittel',    3.6, 0.040, 0.040, 0.35),
_TempoMode('schnell',   3.4, 0.050, 0.050, 0.46),   # Boot — == YAML-Skalen (unverändert)
_TempoMode('aggressiv', 1.7, 0.100, 0.090, 0.95),   # Bremse gegen den angehobenen Deckel
```

- `gait_node` `_ParamSpec['cycle_time'].default` **2.0 → 3.4** und `gait.launch.py` `cycle_time`
  **2.0 → 3.4** — der Boot-Zustand muss der Boot-Tempo-Stufe entsprechen, sonst springt der erste
  D-Pad-Druck (Sprungfrei-Invariante, per Test gepinnt).
- `ps4_usb.yaml` / `ps4_bt.yaml`: die Skalen **bleiben wertgleich** (0.05/0.05/0.46) → nur die
  Kommentare werden nachgezogen.

### 2.3 B2b — Clamp-Meldung entschärfen (Folge von B2, §7.3)

`gait_node` loggt bei jedem Engine-Clamp eine **WARN alle 2 s**; diese Meldungen laufen über
`/rosout` in `/hexapod/alerts` und damit **in die App-Alert-Liste**. Nach B2 ist der Clamp in den
Modi tief/hoch und bei den Nicht-Tripod-Gangarten der **Normalfall** — die Liste liefe dauerhaft
voll. Änderung: WARN nur noch bei **echter Fehlkonfiguration** (Faktor < 0.25) und mit
`throttle_duration_sec=10.0`, darunter `debug`. Die Schwelle ist **gerechnet**: über alle 48
ausgelegten Betriebspunkte (4 Gangarten × 4 Tempo-Stufen × 3 Stance-Modi) clampen **34** leicht,
der kleinste reguläre Faktor ist **0.39** (wave + schnell + hoch). 0.25 lässt jeden regulären
Punkt still und meldet nur Kommandos, die mehr als 4× über `linear_max` liegen. Die Meldung selbst bleibt inhaltlich gleich.

### 2.4 Doku / Naht

| Datei | Was |
|---|---|
| [`hmi_config_manifest.yaml`](../../src/hexapod_supervisor/config/hmi_config_manifest.yaml) | `default:` von `step_length_max` (0.085) und `cycle_time` (3.4) nachziehen. ⚠️ **Always-On-Schicht** → Deploy braucht `systemctl --user restart hexapod_always_on` (reißt einen laufenden Stack mit) |
| [`interface_contract.md`](interface_contract.md) §6a | Beispiel-JSON-Caps aktualisieren + **v0.14.1**-Changelog-Zeile („kein Interface-Change, Caps liegen höher, Boot-`cycle_time` 3.4") |
| `hexapod_gait/README.md` | `step_length_max`- und `cycle_time`-Zeilen |
| `hexapod_teleop/README.md` | Tempo-Tabelle + Auslegungsregel + die `linear_max`-Nebenwirkung |
| [`ai_navigation.md`](../../project_architecture/ai_navigation.md) | „Stance-Modi": neue Werte + der Befund „Deckel wirkt nur, wenn Skala × Bodenzeit ihn freigibt"; „Teleop-Mapping": Auslegungsregel |
| [`00_backlog.md`](../00_backlog.md) | Block-H-Zeilen H1/H2 auf „durch Phase 11 abgelöst" |
| H1/H2-Progress | je eine Verweis-Zeile bei den offenen Sim/HW-Bullets (**Historie nicht umschreiben**) |
| `PHASE.md` | Phase-11-Zeile; Politur rückt auf Phase 12 |

---

## 3. Tests-Liste (mit Begründung)

| Test | Prüft | Warum |
|---|---|---|
| `test_step_height_modes_node`: Tabellen-Pin auf die neuen Quintupel | Vertrag | Werte-Änderung nur mit neuem Gate-Durchlauf |
| dito: Apex-Invariante `bh + sh ≤ −0.02` bleibt | Femur-Wand | schützt den unveränderten Hub |
| dito: sl-Reject je Modus nachgezogen (mittel 0.09 → Reject, 0.085 → ok; tief 0.07 → Reject; hoch 0.06 → Reject) | Deckel-Semantik | Reject ersetzt IKError+Freeze auf HW |
| dito: Boot-Override-Deckelung (Fixture 0.12 liegt weiter über 0.085) | `params_file`-Lücke | Overrides umgehen den Set-Callback |
| dito: `intent_max ≥ sl-Default` und `≤ Boot-Deckel` | Clamp-Artefakt | der H2-Bug |
| `test_stance_switch`: Modus-Tripel → **Quintupel**, `_engine()` fährt die **Modus-sl** | echte Validierung | der real-engine-Test fährt heute `step_length_max=0.05` fix und prüft die Schrittweite damit gar nicht |
| `test_stance_switch::test_mode_walks_all_directions_no_ikerror` grün | Wahrheit am Femur-Rand | das Envelope-Tool ist dort zu optimistisch |
| `test_param_callback`: `linear_max`-Erwartungen an neue Defaults | Folge-Rechnung | `linear_max = sl / T_stance`, beide Faktoren geändert |
| `test_tempo_presets`: Tabellen-Pin + Sprungfrei-Invariante (Code **und** beide YAMLs) | UX-Vertrag | der erste D-Pad-Druck darf nicht springen |
| **neu**: Boot-`cycle_time` == `gait_node`-Default == Launch-Default | zweite Sprung-Quelle | der Tempo-Wechsel setzt `cycle_time` |
| **neu**: Ausschöpfungs-Pin „Boot-Stufe erreicht den mittel-Deckel" (`skala × T_stance ≈ sl`, Toleranz) | Design-Regel | verhindert stillen Drift zurück in den 50-mm-Zustand |
| **neu**: „keine Stufe wird schneller" — `min(skala, linear_max)` je Stufe ≤ heutiger Wert | User-Vorgabe | der angehobene Deckel zieht sonst den aggressiv-Clamp mit hoch |
| **neu**: Tempo-Monotonie — v steigt von langsam → aggressiv in **jedem** Stance-Modus | Bedien-Logik | sonst wäre „schnell" in hoch langsamer als „mittel" |
| **neu**: Clamp-Log — kein WARN bei leichter Begrenzung, WARN bei Faktor < 0.8 | Alert-Flut | §7.3 |
| `test_hmi_status` grün (Manifest-Defaults in `[min,max]`) | App-Naht | `cycle_time` 3.4 ∈ [1.0, 4.0] |
| `test_hw_terrain_preset` grün | HW-Preset | enthält weder sl/sh noch `cycle_time` → erbt die neuen Defaults, muss unberührt bleiben |
| Volle Suiten gait / kinematics / teleop / supervisor + Lint | Gate | Baseline zu Beginn erheben |

**Bewusst NICHT (scope-out):**

- **Fuß-Hub erhöhen** — datenbasiert verworfen (§7.1), beide Fallback-Stufen RED.
- **Dynamischer Deckel je Terrain-Schalter** — bewusst als optionale Ausbaustufe **B3** (§9)
  zurückgestellt.
- **`cliff_depth` 0.03 → 0.02** als Budget-Quelle — bringt ~5 mm, kostet Kantenschutz (§7.1).
- **Walk-Radius ändern** — alle geprüften Alternativen deutlich schlechter (§7.1).
- **Servo-Drehmoment / Strom** — kein Offline-Gate möglich, Beobachtung im HW-Schritt.
- **Slip-Parameter präventiv ändern** — die längere Zykluszeit entschärft die H2.6-Ursache eher
  (§7.4); Rückfall-Werte liegen im test_commands bereit.
- **App-Änderungen** — keine nötig (§7.7).

---

## 4. Progress-Checkliste (Done-Vertrag → `phase_11_stride_envelope_progress.md`)

```
Phase 11 (Laengere Schritte):
- [x] P11.1 Offline-Gates: Deckel-Kandidaten + Fallback-Treppen exit-code-basiert gemessen (check UND engine-check), finale Werte + verworfene Alternativen mit Messreihe dokumentiert
- [ ] P11.2 Code B1: _STANCE_MODES sl (0.065/0.085/0.055) + step_length_max-Default + step_length_intent_max + gait.launch.py-Default inkl. description-Texte
- [ ] P11.3 Code B2: _TEMPO_MODES (4.0/3.6/3.4/1.7 + aggressiv-Bremse 0.100/0.090/0.95) + cycle_time-Default (Node + Launch) + ps4_usb/bt.yaml-Kommentare + Clamp-Log entschaerft (B2b)
- [ ] P11.4 Tests: Tabellen-/Apex-/Reject-/intent_max-Pins, test_stance_switch auf Modus-sl gehaertet, Tempo-Pins (Sprungfrei Code+YAML+cycle_time, Ausschoepfung, keine-Stufe-schneller, Monotonie), Clamp-Log-Test; colcon test hexapod_gait hexapod_kinematics hexapod_teleop hexapod_supervisor + Lint gruen
- [ ] P11.5 Doku: hmi_config_manifest-Defaults, interface_contract §6a + v0.14.1-Changelog, README gait+teleop, ai_navigation, Backlog, H1/H2-Progress-Verweise, PHASE.md
- [ ] P11.6 Sim UEBER DIE APP (ein Befehl: always_on.launch.py -> App verbinden -> Hexapod starten -> Aufstehen): 3 Stance-Modi x 4 Tempo-Stufen, Schrittweite gemessen, kein IKError/Freeze/Regress, Alert-Liste sauber
- [ ] P11.7 HW aufgebockt: Tempo-Stufen + Stance-Modi durchschalten, apex_meter (Hub unveraendert), Kontakt-/Slip-Logs beobachten
- [ ] P11.8 HW Boden -> Gelaende: Schrittweite subjektiv bewertet, Stopp-Nachlauf einmal bewusst geprueft, Strom/Stabilitaet ok, keine False-Positive-Freezes
- [ ] P11.9 kritische Self-Review-Tabelle
```

---

## 5. Test-Anleitung (Skizze — `phase_11_stride_envelope_test_commands.md` nach dem Code)

Jeder Block **eigenständig lauffähig** (eigener Bringup, eigene Erwartung, eigenes Melde-Format):

1. **Offline-Block** — die Gate-Aufrufe zum Nachvollziehen, exit-code-basiert.
2. **Unit-Block** — `colcon test` + `colcon test-result`, erwartete Zahlen.
3. **Sim-Block über die App** — **ein Befehl** im Terminal
   (`ros2 launch hexapod_bringup always_on.launch.py`), dann App verbinden → „Hexapod starten" →
   „Aufstehen". **Kein** paralleles `ramp_walk` (Port-9090-Kollision). Danach: Stance durchschalten,
   Tempo durchschalten, Schrittweite messen, Alert-Liste kontrollieren.
4. **HW-Block aufgebockt** — 3-Terminal-Muster, `apex_meter`, Kill-Switch.
5. **HW-Block Boden/Gelände** — inkl. Stopp-Nachlauf-Probe.
6. **Rückfall-Kasten** — Slip-Werte als Live-`param set`, Recovery-Prozedur.
7. **Deploy-Kasten** — `systemctl --user restart hexapod_always_on` nach der Manifest-Änderung.

---

## 6. Sicherheit (CLAUDE.md §9)

Offline-Gates → Sim → **HW aufgebockt** → Boden → Gelände. Kill-Switch griffbereit. Neu zu
beachten: der **Stopp-Nachlauf** wächst mit der Zykluszeit auf bis zu einen halben Zyklus
(≈ 1,7 s / ≈ 8 cm bei „schnell"). Das wird beim ersten Boden-Lauf bewusst einmal ausprobiert,
bevor es ins Gelände geht. Der **E-Stop ist davon nicht betroffen** — er greift im Tick-Gate
sofort, unabhängig von der Zykluszeit.

---

## 7. Kritische Prüfung (vor der Umsetzung durchgegangen)

### 7.1 Warum nicht mehr geht — die verworfenen Alternativen, alle gemessen

| Alternative | Messung | Verdikt |
|---|---|---|
| mittel Fuß-Hub 0.060 | femur **0.033** (sidestep/diagonal), auch allein ohne Weiten-Erhöhung | RED — Femur-Wand |
| mittel Fuß-Hub 0.055 | femur **0.082** | RED |
| hoch Weite 0.060…0.100 | out_of_reach am S4-Floor (d = 0.1942…0.1949 > 0.194) | RED — Reichweite |
| tief Weite 0.070…0.100 | femur 0.0885 → 0.0182 | RED |
| `cliff_depth` 0.03 → 0.02 (hoch) | 0.070 RED (femur 0.079), 0.080 RED (Reach) | bringt ~5 mm — Kantenschutz nicht wert |
| Walk-Radius 0.145 / 0.150 / 0.155 (hoch) | **alle 12 Zellen RED**, femur kollabiert auf 0.002–0.043 | 0.160 ist bereits das Optimum |
| Zwischen-Stances bh −0.085/−0.090/−0.095 mit mehr Hub | **alle 5 Zellen RED** (check und engine) | es gibt keine Kombination mit mehr Hub *und* mehr Weite |

### 7.2 Andere Gangarten — geprüft, unkritisch

Die neuen Deckel wurden mit **wave, tetrapod und ripple** durch beide Gates gefahren: **alle neun
Zellen GREEN**. Die Fuß-Hülle ist gangart-unabhängig (die Amplitude bleibt ≤ `step_length_max`,
nur die Phasenlage unterscheidet sich).

Was sich unterscheidet, ist die **Bodenzeit** (`swing_duty`: tripod 0.5 · tetrapod/ripple 1/3 ·
wave 1/6) und damit `linear_max`:

| Gangart | T_stance @ cycle 3.4 | linear_max (mittel) | Folge |
|---|---|---|---|
| tripod | 1.70 s | 0.050 m/s | Skala == linear_max, kein Clamp |
| tetrapod / ripple | 2.27 s | 0.037 m/s | Clamp (heute bei 0.060 knapp nicht) |
| wave | 2.83 s | 0.030 m/s | Clamp (heute schon so) |

Die **Schrittweite bleibt in allen Gangarten voll** (85 mm) — nur die Fahrgeschwindigkeit sinkt,
weil dieselbe Strecke auf mehr Bodenzeit verteilt wird. Zusätzlicher Vorteil: die Swing-Phase wird
länger (wave: 0.57 s statt 0.33 s), die Servos bekommen also **mehr** Zeit pro Schwung, nicht
weniger.

### 7.3 🔴 Die Clamp-Warnung — muss mitgefixt werden (B2b)

`gait_node` loggt bei jedem Engine-Clamp `cmd_vel clamped: …` als **WARN, throttled auf 2 s**.
Diese Meldungen landen über `/rosout` → `hmi_status` → `/hexapod/alerts` **in der App**. Nach B2
ist der Clamp der Normalfall (tief/hoch bei tripod, alle Modi bei wave/tetrapod/ripple) → die
Alert-Liste liefe im normalen Fahrbetrieb dauerhaft voll und würde echte Warnungen zudecken.
Deshalb ist die Entschärfung (§2.3) **Teil dieser Phase**, nicht optional.

### 7.4 Terrain-/Sensor-Parameter — profitieren eher

Alle S4-Schwellen sind **phasenbasiert** (`touchdown_probe_start_stance_phase` 0.35,
`slip_grace_stance_phase` 0.6) oder in Ticks (`slip_debounce_ticks` 14 = 0.28 s). Bei längerer
Zykluszeit wird der feste Kontakt-Lag ein **kleinerer** Phasen-Anteil — genau die Ursache der
H2.6-False-Positives kehrt sich also ins Positive. Das Such-Fenster des adaptiven Touchdowns wird
länger (0.43 s statt 0.25 s) → sanfteres Absenken. `sensor_dead_cycles` 2 meldet einen toten
Sensor später (6.8 s statt 4.0 s) — unkritisch, weil das nur eine Degradation maskiert, keinen
Schutz.

### 7.5 Zeitabhängige Sequenzen — nicht betroffen

`stance_switch_duration`, `reposition_cycle_time`, Sitdown-/Standup-Dauern, Show-Modi
(Look-Around/Free-Leg), `comms_loss_sitdown_timeout` und der E-Stop haben **eigene** Zeitbasen und
sind von `cycle_time` unabhängig. Geprüft: `cycle_time` bleibt `standing_only` (Tempo-Wechsel nur
im Stand), alle neuen Werte liegen in der `fp_range` (0.5…6.0) und im Manifest-Slider (1.0…4.0).

### 7.6 Bestehende Presets — bleiben gültig

`sim_walk` (sl 0.050), `demo_walk` (0.050), `defensive_walk` (0.030) und `aggressive_walk` (0.070)
liegen alle unter dem neuen mittel-Deckel 0.085 → kein Init-Reject. `hw_terrain.yaml` und
`rubicon.yaml` enthalten weder `step_length_max` noch `cycle_time` → sie **erben** die neuen
Defaults, was für den HW-/App-Pfad genau gewollt ist.

### 7.7 App-Seite — keine Änderung nötig

Die Slider klemmen live auf `status.step_length_cap`, und die Manifest-Grenzen (sl bis 0.12,
`cycle_time` bis 4.0) decken alle neuen Werte ab. Angefasst werden nur die `default:`-Felder im
Manifest — das ist ROS-seitig und erfordert lediglich den Always-On-Neustart beim Deploy.

### 7.8 Was subjektiv anders sein wird (bewusst)

Der Roboter läuft **gemächlicher und großschrittiger**: bei „schnell" dauert ein Zyklus 3,4 s statt
2,0 s, ein Bein ist 1,7 s in der Luft. Statisch stabil bleibt es (Tripod: immer 3 Beine am Boden),
aber Störungen wirken länger — auf HW beobachten. Das Stopp-Verhalten wird träger (§6).

---

## 8. Design-Log (Alternativen + warum verworfen)

- **[E1] Fuß-Hub anheben (mittel 0.050 → 0.060)** — verworfen, Messung: femur 0.033 statt
  geforderter 0.10. Auch 0.055 fällt (0.082). Der Apex läuft gegen die Femur-Wand; das war schon
  der H1.2-Befund und bestätigt sich mit der neuen Weite.
- **[E2] hoch auf 0.090/0.100** — verworfen, Messung: out_of_reach am S4-Probe-Floor. Bei
  `body_height` −0.100 liegt der Floor auf z = −0.13, die Basis-Distanz beträgt dort schon 0.1745
  von 0.194 möglichen. Reine Geometrie.
- **[E3] `cliff_depth` als Budget-Quelle** — verworfen (User + Messung): bringt ~5 mm und
  schwächt den Kanten-/Abgrundschutz, der auf HW ohnehin erst ab 2 Beinen greift.
- **[E4] Kleinerer Walk-Radius für hoch** — verworfen, alle 12 gemessenen Zellen RED: der Femur
  reitet an der Wand, die Reserve kollabiert auf 0,1–2,5°.
- **[E5] Neue/verschobene Stance-Höhe (bh −0.085…−0.095) mit mehr Hub** — verworfen, alle 5
  Zellen RED. Es existiert keine Kombination, die Hub und Weite gleichzeitig verbessert.
- **[E6] Nur Deckel anheben, Tempo lassen** — verworfen: in drei von vier Tempo-Stufen klemmt die
  Skala, der Gewinn käme nie am Boden an.
- **[E7] Stick-Skalen erhöhen statt Zykluszeit verlängern** — verworfen (User-Vorgabe): dieselbe
  Schrittweite, aber proportional höhere Fußgeschwindigkeit → mehr Schlupf und Last. Zusätzlich
  hätte es dauerhafte Clamp-WARNs erzeugt.
- **[E8] Tempo-Stufen umbenennen** (z. B. „Terrain") — verworfen: die Namen stehen im
  `capabilities.tempo_presets`-Enum und damit in der App-Naht.
- **[E9] Dynamischer Deckel je Terrain-Schalter** — **nicht verworfen, zurückgestellt** als
  optionale Ausbaustufe B3 (§9). Grund: mehr bewegliche Teile (Deckel zur Laufzeit veränderlich,
  fünf Lesestellen) für +15 mm in genau einem Modus — erst nach Feld-Erfahrung entscheiden.

---

## 9. Optionale Ausbaustufe B3 — Deckel folgt den Terrain-Schaltern

> **Nicht Teil dieser Phase.** Hier dokumentiert, damit die Entscheidung später ohne
> Neu-Recherche getroffen werden kann. Die Messwerte liegen bereits vor.

### 9.1 Idee

Die 30 mm Kontakt-Suchtiefe (S4) kosten Reichweite und damit Schrittweite. Sie entstehen nur, wenn
**Adaptiver Touchdown** (`touchdown_max_extra_depth` 0.02) oder **Kanten-Freeze**
(`cliff_depth` 0.03) aktiv sind — beides App-Toggles in der Gruppe *Sensorik / Terrain*. Sind sie
aus, dürfte der Fuß weiter ausholen.

### 9.2 Was es brächte (gemessen, beide Gates)

| Stance | beide Toggles an (= B1) | Kanten-Freeze aus (Floor 0.02) | beide aus (Floor 0) |
|---|---|---|---|
| tief | 0.065 | 0.065 | 0.065 |
| **mittel** | **0.085** | **0.095** | **0.100** |
| hoch | 0.055 | 0.055 | 0.055 |

**Nur mittel profitiert** (+15 mm) — in tief und hoch bindet die Femur-Reserve im Seitwärtsgang,
nicht die Reichweite.

### 9.3 Was zu bauen wäre

- `_StanceMode` bekommt ein zweites Weiten-Feld (mit/ohne Suchtiefe), z. B.
  `step_length_max_flat`.
- Eine Funktion `_effective_sl_cap()` ersetzt die heute **fünf** direkten Tabellen-Zugriffe
  (Validator-Block 1h3, `_do_stance_switch`, `_maybe_sync_stance_params`,
  `_on_adjust_step_length`, `_publish_status`).
- Beim **Einschalten** eines Terrain-Toggles muss die aktive `step_length_max` automatisch auf den
  kleineren Deckel gezogen werden (sonst IKError + Freeze beim nächsten Fuß, der ins Leere tastet).
- Damit der Gewinn ankommt, braucht die Boot-Stufe zusätzlich Skalen-Luft (z. B. 0.06 statt 0.05) —
  was ohne B3 nur Clamp-WARNs erzeugen würde und deshalb hier bewusst nicht gemacht wird.
- Umfang: ~60 Zeilen + ~8 Tests. **Keine App-Änderung** (die `dynamic_cap`-Mechanik meldet den
  neuen Deckel automatisch, der Slider folgt).

### 9.4 Wann sinnvoll

Wenn sich im Feld zeigt, dass 85 mm auf gutem Untergrund zu kurz sind **und** dort auf die
Terrain-Sicherung verzichtet werden kann. Auf unebenem Gelände bringt B3 nichts, weil dort die
Toggles ohnehin an sein sollen.
