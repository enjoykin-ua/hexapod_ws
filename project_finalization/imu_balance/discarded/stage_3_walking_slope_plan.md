# Stufe 3 — Leveling im Laufen + Wackel-Dämpfung + Hang-Parameter

> Stufe 3 von Block A5 ([Master](../00_imu_balance_plan.md)). **Ziel:** den Hang
> **laufend** meistern — (a) Leveling auch im WALKING, (b) Dämpfung des
> dynamischen Körper-Wackelns der Nicht-Tripod-Gangarten (= der A5-Fix für B3),
> (c) Anpassung der Gait-Parameter an den Hangwinkel (Weg-A-Fundament) inkl.
> automatischem Gangart-Wechsel.
>
> **Status: ⚪ offen — vorausgeplant** (gröber als Stufe 2, weil forschungsnah;
> viele Punkte werden mit Gazebo-Daten konkretisiert). Implementierung nach
> §4-Freigabe. Voraussetzung: Stufe 2 (🟢).
>
> ⚠️ **Hier fällt die A/B-Entscheidung** (kontinuierliche Familie A vs. Online-
> Planung B) — mit echten Daten (Master §2, §4 D5).

---

## 0. Kontext & Voraussetzungen

- Stufe 2 liefert: `BalanceController`, Rotations-Stellpfad + Clamp in der Engine,
  Schräg-Welten. Stufe 3 erweitert das auf WALKING + fügt Gyro-Dämpfung + Hang-
  Parameter-Adaption hinzu.
- Erinnerung Master §2: „der Hang ändert sich" unterscheidet A und B **nicht**
  (beide werten live das momentane θ aus). A vs. B = **glatte Schräge** (A reicht)
  vs. **per-Fuß-irreguläres Terrain** (B + Fußkontakte → Stufe 4).
- **Zwei Bedeutungen von „online" (aus Stufe-2-Review, wichtig):** (1) *live
  auswerten/anpassen* — θ messen, Params live setzen; das macht **Weg A genauso**
  (Weg A ist **nicht** statisch!). (2) *from scratch planen* — Params zur Laufzeit
  neu rechnen + live auf Machbarkeit (IK/CoG/Kontakt) prüfen + replan; nur **Weg B**,
  braucht Fußkontakte, lohnt erst bei unebenem Terrain (Stufe 4). „Höhe/Radius/
  Schrittweite am Hang live anpassen" = (1), **nicht** (2) → glatte Hänge brauchen
  kein Weg B.

## 0.5 Sub-Stufen-Zuschnitt (§4-Plan-Review)

Stufe 3 ist zu groß für einen §4-Block → **in Sub-Stufen geschnitten**, jede mit
eigenem §4-Review → Freigabe → Code → Test → Self-Review (wie Stufe 2):

| Sub | Inhalt | eigener Plan |
|---|---|---|
| **3a** | Leveling im WALKING (Stellpfad-Gating → WALKING + Fuß-Scrub) | [`stage_3a_leveling_walking_plan.md`](stage_3a_leveling_walking_plan.md) |
| **3b** | Wackel-Dämpfung (Gyro-D-Term im BalanceController, B3-Fix) | (folgt) |
| **3c** | θ→Parameter-Familie + Auto-Gait-Switch + flüssige In-Lauf-Höhe; **A/B-Entscheidung** | [`stage_3c_slope_params_plan.md`](stage_3c_slope_params_plan.md) |
| **3d** | Slip-Erkennung + Robustheit | (folgt) |

**Reihenfolge: 3a → 3b → 3c → 3d.** Begründung (Plan-Review): 3a/3b halten die Params
**fix** und legen nur Leveling/Dämpfung obendrauf → konsumieren die θ→Param-Familie (3c)
**nicht** → 3c-Vorziehen bringt 3a/3b keinen Mehrwert. 3a-Risiko (IKError-Freeze durch
Über-Leveln) ist durch den Stufe-2-Fallback + einen kleinen Offline-Walking-Hüllen-Check
(in 3a gezogen) gedeckt. 3a + 3b brauchen **beide** den „Gating auf WALKING"-Schritt → 3a
zuerst, 3b reitet drauf.

**Gelockte Entscheidungen (§4-Review):**
- **Wackel-Dämpfung** = Gyro-D-Term **im `BalanceController`** (ein Modul, zwei
  überlagerte Terme: langsamer Winkel-Loop + schneller Raten-Loop). Master D3.
- **Setpoint** = **horizontal (α=0)** in 3a/3b; α·θ-Mitneigen-Blend erst in 3c, wenn
  steilere Hänge/Envelope es verlangen.
- **A/B** bleibt offen → datengetrieben in **3c** (Weg-A-Fundament zuerst, progressiv).
- **Ramp-/Keil-Welt** (flach→Hang→flach): Roboter spawnt **flach**, läuft in den Hang
  (reales Szenario, umgeht Standup-auf-Schräge, hält die IMU welt-referenziert).

## 1. Logik-Skizze

### A. Leveling im WALKING
- Stellpfad-Gating von STANDING auf **WALKING erweitern** (Stufe 2 war nur STANDING).
- Fuß-Scrub in der Stütz-Kette wird relevant (mehrere Stützbeine über den Boden
  gekoppelt) → **Slew-Limit + kleine Winkel**; bei Bedarf Reposition (Risiko 3).

### B. Wackel-Dämpfung (B3-Fix)
- Zusätzlicher schneller **Gyro-Raten-Term (D)** im/neben dem `BalanceController` —
  reagiert auf die Körper-Drehrate (`angular_velocity`, `tilt_rate` aus Stufe 1)
  und dämpft das periodische Kippen von Tetrapod/Ripple.
- **Zwei überlagerte Beiträge** auf denselben Stellpfad: langsamer Winkel-Loop
  (Hang halten) + schneller Raten-Loop (Wackeln dämpfen). Unterschiedliche Signale
  + Gains (Master D3, „statisch vs. dynamisch").

### C. Hang-Parameter-Adaption (Weg A)
- Hangwinkel θ aus IMU (roll/pitch; Bergab-Richtung kommt aus der Projektion, kein
  yaw nötig) → Gait-Parameter aus **vorab-validierter θ→Parameter-Beziehung**:
  `θ → (body_height, step_height, radial, gait_pattern)`, **asymmetrisch hoch/runter**
  (pitch-Vorzeichen).
- **Offline einmal** berechnet (eigenes Tool in `tools/`, analog `reachability_viz`/
  `torque_viz`): pro θ den besten envelope-grünen + CoG-stabilen Parametersatz +
  Max-θ. → die „sichere Parameter-Hülle als Funktion von θ" (Master §2 Weg A).
- **Online:** θ messen → Kurve auswerten/interpolieren → Parameter setzen
  (kontinuierlich, auch bei wechselndem Hang; nie außerhalb der bewiesenen Hülle).
- **Feed-Forward + Closed-Loop (aus Stufe-2-Review):** die θ→Kurve ist die
  **Vorsteuerung** (bringt schnell + beweisbar sicher nahe ans Ziel); ein
  **Closed-Loop-Term** (IMU-Residuum jetzt, später Fußkontakt/Slip/Torque) korrigiert
  Modellfehler *innerhalb* der Hülle. Die Kurve ist kein Korsett, sondern der sichere
  Startpunkt — löst „Kurve passt nicht ganz → komme nicht hoch".
- **Kontinuierliches Gesetz, kein Hang-Modus (aus Stufe-2-Review):** θ→params ist
  **eine durchgehende Funktion** mit **flach = θ=0** (= die heutigen Stance-Modi) +
  **Totband** (~2–3°, nicht für Rausch-Winkel rumregeln). Kein harter Mode-Switch
  flach↔Hang → kein Umschalt-Ruckeln; spürbar wird es nur am Hang.
- **Flüssige Änderung IM Lauf (aus Stufe-2-Review):** `body_height`/`radial` als
  **rate-limitierte kontinuierliche Eingänge während WALKING** (nicht der diskrete
  `STATE_STANCE_SWITCH`, der `cmd_vel` stoppt). Jeder Tick rechnet die Targets neu →
  Swing-Beine landen auf der sich langsam ändernden Höhe, Stance-Beine strecken/beugen
  mit (= die Klett-Bewegung). Zwei Wächter: **Slew-Limit** (Swing-Bein schluckt die
  Delta in seiner Trajektorie) + **Envelope-Clamp bei *jeder* Zwischenhöhe**. Billig,
  weil die Engine ohnehin pro Tick parametrisch rechnet (Master §0.1).
- **Traktions-/Torque-Vorbehalt (aus Stufe-2-Review):** Höhe löst Geometrie/
  Stabilität, **nicht „Klettern" allein** — Hochkommen braucht zusätzlich Traktion
  (µ) + Torque-Reserve (Block-A-Torque-Tool). Sonst Slip/Stall trotz richtiger Höhe.
- **Schürf-/Clearance-Vorbehalt (aus 3a, User-Hinweis):** mehr Walking-Leveling-Range
  NICHT durch blindes Senken von `step_height` holen — am Hang kratzt der Swing-Fuß
  dann (bergauf steigt der Boden zum Fuß hin an; aktuelle Höhe ist auf HW „grad so
  genug"). 3c braucht **hang-bewusste Schwunghöhe** (bergauf MEHR anheben, asymmetrisch)
  statt kleinerer Schritte. Das ist auch der Grund, warum 3a den gelevelten Swing-Apex
  als Engpass hat (Walking-Clamp ~4°).
- **Auto-Gangart-Switch:** moderater Hang → Tripod; steiler → Wave (statisch
  stabiler, 5 Füße unten). Reuse B3 `gait_pattern`.
- **Kletter-Stall-Befund (aus 3a-Sim, fixe Params):** mit fixen Walk-Params bleibt der
  Roboter ab **~12°** stecken (Vortrieb/CoG, NICHT Reibung — Fuß µ=1.0). Genau das soll
  3c lösen: Körper tiefer + Schritt/Stance hang-adaptiv (+ ggf. Wave). **Fußschalter
  helfen hier NICHT** (Traktion/Vortrieb unverändert) — die sind Stufe-4-Terrain
  (Kontakt/Schlupf erkennen). **Echter Kletter-Ceiling auf HW = Servo-Torque** (Block-A-
  Torque-Tool messen), nicht Sim-Reibung (~50°).

### D. Slip-Erkennung (User-Idee)
- Leveling-Integrator läuft (korrigiert), Kippung bessert sich aber nicht →
  **Rutsch-Indikator** (fällt teils gratis aus dem Regler-Zustand). Reaktion offen
  (melden / langsamer / stoppen). Stärker mit Fußkontakten (Stufe 4).

### E. Welten
- **Rampe** (flach→Hang→flach) für Eintritt/Austritt + wechselnden Hang; ggf.
  gekrümmter Hügel. Aufbauend auf den Stufe-2-Schräg-Welten.

### F. A/B-Entscheidung (mit Daten)
- Kontinuierlich-A löst glatte (auch wechselnde) Hänge vollständig. B (Online +
  Kontakte) erst für irreguläres Terrain (Stufe 4) — und hängt an den Fußkontakten.
  → Stufe 3 = **A-Fundament**; finale A/B/Hybrid-Wahl hier dokumentieren.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| Unit | Gyro-D-Term, θ→params-Lookup/Interpolation, Gait-Switch-Logik, Slip-Detektor | pytest grün |
| **Offline-Batch** (Dev-Rechner) | **20 lineare + 20 wechselnde Hänge** (User-Plan): Planer liefert in-limit + CoG-stabile Parameter über θ; Max-θ | Skript grün, kein out-of-envelope |
| Sim | Rampe **hoch + runter** gelevelt; Nicht-Tripod-Wackeln messbar reduziert; Auto-Switch greift; kein Freeze/Scrub-Exzess | qualitativ + Logs |
| Sim wechselnder Hang | Parameter folgen θ kontinuierlich | kein Sprung/Freeze am Knick |

**Bewusst NICHT:** irreguläres per-Fuß-Terrain + Fußkontakte (Stufe 4).
**Test-Schichten** (Master §6): Offline-Batch (Planer) → Gazebo (Dynamik) → HW.

## 3. Progress-Checkliste (Template → Progress-File)

```
- [ ] 3.1 Leveling-Gating auf WALKING erweitert (Stellpfad + Scrub/Slew)
- [ ] 3.2 Gyro-Raten-Term (Wackel-Dämpfung) im BalanceController + Unit-Tests
- [ ] 3.3 θ→Parameter-Familie: Offline-Tool (tools/) + Repräsentation (Tabelle/Kurve) + Validierung
- [ ] 3.4 Online-Auswertung θ→params im gait_node + Auto-Gangart-Switch (Tripod/Wave)
- [ ] 3.5 Slip-Erkennung (Indikator + gewählte Reaktion)
- [ ] 3.6 Rampen-/wechselnde-Hang-Welten
- [ ] 3.7 Offline-Batch (20 linear + 20 wechselnd) grün
- [ ] 3.8 Sim-Verify hoch/runter + Wackel-Reduktion + Auto-Switch
- [ ] 3.9 A/B/Hybrid-Entscheidung dokumentiert (mit Daten)
- [ ] 3.10 README/Konzept-Update + colcon test/Lint + Self-Review
```

## 4. Offene Punkte für User-Review (viele — vor Code je Teil entscheiden)

- **A/B/Hybrid finale Wahl** (mit Gazebo-Daten) — der Kern.
- **θ→params-Familie:** wo berechnet, wie repräsentiert (Tabelle/Kurve/Funktion),
  wie validiert; Tool-Design (`tools/`).
- **Uphill/Downhill** asymmetrische Presets — wie genau (Bergab = der gefährliche
  Fall, CoG nach vorn).
- **Wackel-Dämpfung:** ein Controller mit D vs. zwei überlagerte Loops; Gains.
- **Fuß-Scrub im Walking-Leveling:** Reposition vs. kleiner-Winkel + Slew.
- **Slip-Erkennung:** nur melden? langsamer? stoppen? Schwelle?
- **Gait-Switch:** Schwellen + welche Gangarten (Tripod→Wave).
- **Setpoint (aus Stufe-2-Review verfeinert):** nicht nur level vs. terrain-parallel,
  sondern ein **Blend `α·θ`** mit `α∈[0,1]` als Knopf — α=0 = horizontal (max.
  Stabilität/Kamera-Horizont), α→1 = hangparallel (max. Beinrange → steilere Hänge,
  Preis: CoG-Marge); **α evtl. selbst Funktion von θ** (steiler → mehr mitneigen). Der
  Stufe-2-Clamp ist die degenerierte Version (harter Knick bei `max_level_angle`).
  Zudem: **Stufe-1-Kipp-Schwellen relativ zum gelevelten Soll** statt absolut
  (Residual-Tip + Konvergenz-Gate, Stufe-2-§4-Vormerker).
- **Echtzeit-Budget (50 Hz):** θ→params live evaluieren amortisiert (bei θ-Änderung,
  cachen) — nicht jeden Tick neu rechnen.

## 5. Design-Entscheidungen (vorläufig)

| Entscheidung | Gewählt (Vorschlag) | Alternative | Warum |
|---|---|---|---|
| Hang-Lokomotion | Weg-A-Fundament (Familie offline, online auswerten) | Voll-Online B | glatte Hänge = 1-Param; B braucht Kontakte (Stufe 4) + Echtzeit |
| Wackel-Dämpfung | Gyro-D als Beitrag im BalanceController | separater Node | teilt Stellpfad; ein Modul |
| Gangart-Switch | diskrete Preset-Wahl (B3-Patterns) | kontinuierlich | vor-validierte Presets, kein Live-Risiko |
| θ→params | offline-Familie (Vorsteuerung) + online-Eval + Closed-Loop-Korrektur | Live-Planung from scratch (B) | Sicherheit (Master §2); Feed-Forward+Feedback fängt Modellfehler |
| Setpoint | Blend `α·θ`, α = Funktion von θ | reines level / reines terrain-parallel | tauscht Beinrange ↔ CoG-Marge; level = α=0, hangparallel = α=1 |
| Höhen-/Param-Wechsel im Lauf | rate-limitiert kontinuierlich (WALKING) + Envelope-Clamp je Zwischenhöhe | diskreter STANCE_SWITCH | flüssig, kein Stopp; STANCE_SWITCH friert cmd_vel |
