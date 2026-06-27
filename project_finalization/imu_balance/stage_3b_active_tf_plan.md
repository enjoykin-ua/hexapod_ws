# Stufe 3 / TF-2 — Aktive Körper-Stabilisierung (roll→0, pitch→folgen) + Gyro-Dämpfung

> Zweite Teil-Stufe von [Stufe 3 Terrain-Following](stage_3_terrain_following_plan.md) (Block A5).
> **Ziel:** den Körper beim Hang-Laufen **sauber parallel zum Boden** halten (flach → waagerecht,
> Hang → hangparallel) und das mechanische/gang-bedingte **Wackeln dämpfen** — der sichtbare
> IMU-Mehrwert, der auch die Nicht-Tripod-Gangarten ruhiger macht und die Plateau-Übergänge glättet.
>
> **Status: ⚪ offen — Plan zum Review.** §4-Workflow: Plan → **User-Freigabe** → Code → Test →
> Self-Review. Voraussetzung: TF-1 (🟡 Code+Tests fertig, Sim-Schätzung bestätigt). Nachfolge:
> **TF-3** (optional: Schwerpunkt-Hilfe + Schlupf).

---

## 0. Kontext & Abgrenzung

- **TF-1 lieferte die Bausteine.** Die Hang-Schätzung (`SlopeEstimator`, langsamer Tiefpass) und
  das **Residual** (= IMU − Hang) sind schon da. TF-2 nutzt **dasselbe Residual** auch als
  Regelgröße — kein neuer Schätzer.
- **Kern-Erkenntnis (Mathe):** „roll → 0 ausrichten, pitch → dem Hang folgen" lässt sich
  **vollständig** über die Reglereingänge ausdrücken, ohne neue Regelstruktur:
  - **roll-Achse:** Eingang = **rohe** IMU-roll, Sollwert 0 → der Regler treibt roll → 0.
  - **pitch-Achse:** Eingang = **Residual** (IMU-pitch − Hang-Schätzung), Sollwert 0 → der
    Regler treibt das *Residual* → 0, d.h. den Körper **auf den Hang** (der langsame Hang-Anteil
    fällt heraus, nur die schnelle Abweichung = Wackeln wird korrigiert). **Das ist „pitch folgt
    dem Hang" + „pitch-Wackeln dämpfen" in einem.**
- **Damit bleibt der `BalanceController` strukturell unverändert** (Sollwert intern weiter 0) —
  die „Umpolung" ist allein, **welche Größe** pro Achse hineingeht. Neu ist nur ein **Gyro-D-Term**.
- **Stellpfad unverändert.** Die Engine-Rotation `R(corr_roll, corr_pitch)` auf die Fuß-Targets
  (Stufe 2/3a, mit Clamp + IKError-Fallback) wird **wiederverwendet**. Weil die Korrekturen
  **klein** sind (nur roll→0 + Wackeln, **kein** Voll-Aufrichten), bleiben sie mühelos im
  Envelope → **keine** θ-Geometrie-Tabelle, **kein** neues Offline-Tool.
- **Abgegrenzt (NICHT TF-2, [Sim-Befund TF-1](stage_3a_passive_tf_test_commands.md)):** „Bein
  findet keinen Boden an Kante/Stufe" (Plateau-Scheitel, 35°-Bordstein) ist ein **Terrain-/
  Bodenkontakt-Problem → Stufe 4 (Fußtaster)**, kein Balance-Problem. TF-2 macht die Übergänge
  **ruhiger**, überwindet aber **keine** Kanten/Stufen. Diese Erwartung wird bewusst nicht gestellt.

## 1. Logik-Skizze

### 1.1 Gyro-Raten cachen (gait_node `_on_imu`)
- Zusätzlich zu `_imu_tilt_rate` (= `hypot(gx, gy)`, bleibt für den Tip) die **signierten**
  Achsen-Raten cachen: `_imu_gyro_roll = ang_vel.x`, `_imu_gyro_pitch = ang_vel.y`.

### 1.2 Gyro-D-Term im `BalanceController`
- Signatur erweitern, **rückwärtskompatibel**: `update(roll, pitch, dt, gyro_roll=0.0,
  gyro_pitch=0.0)`. Bestehende Stufe-2/3a-Aufrufe (`update(roll, pitch, dt)`) funktionieren
  unverändert (Kd·0 = 0).
- Pro Achse: `d = −Kd · gyro_rate` (dämpft die Drehrate, vorzeichen-gegenläufig). Der D-Anteil
  wirkt **immer** (auch im Winkel-Totband — Wackeln hat kleinen Winkel, aber hohe Rate); P/I
  bleiben totband-gegatet wie gehabt.
- Reihenfolge je Achse: `raw = clamp(p_term + I + d, max)` → **dann** Slew. (D **vor** dem Slew →
  das Slew-Limit bindet die *Gesamt*-Stellbewegung weiter als Scrub-Schutz; siehe offener Punkt.)
- Neuer Gain `Kd` (+ `set_gains(kd=…)` für Live-Tuning). Default-Verhalten ohne gesetztes Kd =
  identisch zu Stufe 2.

### 1.3 Stell-Eingänge pro Achse (gait_node `_update_leveling` → TF-Modus)
- Modus-Schalter `leveling_mode ∈ {horizontal, terrain}` (Default **terrain**, s. offener Punkt):
  - **`terrain` (TF-2):** `roll_in = imu_roll`, `pitch_in = residual_pitch`
    (`= imu_pitch − slope_pitch`, aus dem TF-1-`SlopeEstimator`).
  - **`horizontal` (Stufe 2/3a, beibehalten):** `roll_in = imu_roll`, `pitch_in = imu_pitch`
    (Voll-Leveln auf 0/0 — der bisherige Modus, für statisches Horizontal-Stehen).
- `corr = balance.update(roll_in, pitch_in, dt, gyro_roll, gyro_pitch)` →
  `engine.set_body_orientation_offset(*corr)` (unverändert).
- Gating wie 3a: aktiv in `STANDING`/`WALKING`/`STOPPING`; sonst Controller-`reset` + Offset 0/0.
- State-abhängiger Clamp (STANDING 10° / WALKING 4°) bleibt; die TF-2-Korrekturen sind klein →
  Clamp ist Backstop, nicht der bindende Faktor.
- **Pseudocode:**
  ```
  if not leveling_enable or imu is None or state not in {STANDING,WALKING,STOPPING}:
      balance.reset(); engine.set_body_orientation_offset(0,0); return
  dt = monotonic_delta()
  balance.set_gains(max_level_angle = clamp_for_state(state))
  if leveling_mode == 'terrain':
      roll_in, pitch_in = imu_roll, (imu_pitch - slope_pitch)   # roll→0, pitch→Hang
  else:  # horizontal
      roll_in, pitch_in = imu_roll, imu_pitch                   # Voll-Leveln (alt)
  corr = balance.update(roll_in, pitch_in, dt, imu_gyro_roll, imu_gyro_pitch)
  engine.set_body_orientation_offset(*corr)
  ```

### 1.4 Parameter
- Neu: `leveling_mode` (string, Default `terrain`), `leveling_kd` (Default klein, s.u.), alle
  **live** via `_on_param_change` (+ String-Validierung `horizontal|terrain` analog `standup_mode`).
- Wiederverwendet: `leveling_enable`, `leveling_kp/ki/deadband/slew_max/max_angle*`,
  `slope_estimate_tau_s` (die „langsam = Hang"-Zeitkonstante aus TF-1).

### 1.5 Vorzeichen (kritisch, wie Stufe 2)
- Der Round-Trip-Test aus Stufe 2 pinnt die Dreh-Richtung (`corr` kontert die Neigung). TF-2
  ändert daran nichts (gleicher Stellpfad). Der Gyro-D braucht einen **eigenen** Vorzeichen-Test:
  positive Drehrate → Korrektur, die ihr **entgegen** wirkt (sonst positive Rückkopplung = Aufschwingen).

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: Gyro-D Vorzeichen+Betrag** | `d = −Kd·gyro`; wirkt der Rate entgegen; Kd=0 → unverändert (Back-Compat Stufe 2) | white-box |
| **Unit: D im Totband aktiv** | kleiner Winkel + hohe Rate → D korrigiert trotz P/I-Totband | Ausgang ≠ 0 |
| **Unit: D + Clamp/Slew** | `p+I+d` bleibt in `±max`; Slew bindet weiter | kein Überschuss |
| **Unit: pitch-Residual-Regelung** | terrain-Modus: konstanter Hang → `pitch_in=residual≈0` → **keine** pitch-Korrektur (folgt Hang); roll voll → roll→0 | Closed-Loop |
| **Unit: Closed-Loop-Konvergenz mit D** | Dämpfung reduziert Überschwingen vs. ohne D | Schritt-Antwort |
| **Engine: Round-Trip Vorzeichen** | (aus Stufe 2 getragen) Stellpfad unverändert korrekt | abs 1e-6 |
| **Node: terrain vs horizontal Wiring** | terrain → pitch_in=residual, roll_in=roh; horizontal → beide roh; gyro durchgereicht; mode live | Node-Smoke |
| **Node: Gating STANDING/WALKING/STOPPING** | außerhalb reset+0/0 | wie 3a |
| colcon + Lint | alle bestehenden + neue grün | 0 Fehler |
| **Sim (User)** | Rampe 8/12/16°: Körper sichtbar **ruhig parallel**, Wackeln **gedämpft** vs. TF-1, Plateau-Übergang **sauberer** (kein Hängenbleiben in der Hang-Pose), kein Freeze; horizontal-Modus levelt weiter auf 0 | qualitativ + `/imu/monitor`+`/imu/slope` |

**Bewusst NICHT getestet (→ spätere Stufen / Scope-out):**
- **Quer-/Diagonal-Hang** (roll-Sollwert ≠ 0, Seithang-Komponente) → **eigener Nachfolge-Block §6**
  (roll-Residual + `cmd_vel`-Richtungslogik); TF-2 = Geradeaus-Klettern.
- **Kanten/Stufen-Überwindung** (Plateau-Scheitel, 35°-Bordstein) → **Stufe 4 (Fußkontakte)**,
  prinzipiell kein Balance-Problem ([TF-1-Befund](stage_3a_passive_tf_test_commands.md)).
- **Reale Dämpfungs-Gains** (Kd/Slew final) → Sim grob, **HW** nachziehen (D6: Sim=Logik, HW=Gains).
- **Schwerpunkt-Hilfe / Schlupf** → TF-3.

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
TF-2:
- [ ] TF2.1 gait_node _on_imu: signierte Gyro-Achsenraten cachen (_imu_gyro_roll/pitch)
- [ ] TF2.2 BalanceController: Gyro-D-Term (update(...,gyro_roll=0,gyro_pitch=0), d=−Kd·rate, D vor Slew, im Totband aktiv) + Kd in set_gains, rückwärtskompatibel
- [ ] TF2.3 gait_node: leveling_mode (horizontal|terrain, Default terrain) → terrain füttert pitch=residual/roll=roh, horizontal=beide roh; Gyro durchreichen
- [ ] TF2.4 Params leveling_mode + leveling_kd deklariert + live (_on_param_change, mode-String-Validierung)
- [ ] TF2.5 Unit-Tests (Gyro-D Vorzeichen/Totband/Clamp+Slew, pitch-Residual-Regelung, Closed-Loop mit D) + Node-Wiring-Tests
- [ ] TF2.6 colcon test + Lint grün
- [ ] TF2.7 README/Konzept-Update (terrain-Modus, per-Achse-Sollwert, Gyro-D, Modus-Schalter, Params)
- [ ] TF2.8 Test-Doku stage_3b_active_tf_test_commands.md — KOMFORTABEL (User-Wunsch): strikte Terminal-Reihenfolge (wie TF-1), fertige copy-paste-Befehle, Kd/slew_max-Tuning-Pfad Schritt für Schritt mit „beobachte X", terrain-vs-horizontal-Vergleich, Rampe 8/12/16° + Sim-Verify durch User
- [ ] TF2.9 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

## 4. Entschiedene Punkte (User-Freigabe — code-ready)

1. **Modus-Schalter — ✅ Modus-Param.** `leveling_mode ∈ {horizontal, terrain}`, Default
   **terrain**. `horizontal` behält das Stufe-2-Voll-Leveling (statisch waagerecht stehen, z.B.
   Sensor-/Kamera-Plattform), `terrain` = TF-2. Minimaler Eingriff, keine Regression, Option bleibt.
2. **Gyro-D vs. Slew — ✅ D vor dem Slew.** Das Slew-Limit bindet die *Gesamt*-Stellbewegung weiter
   als Scrub-Schutz; die Dämpfungs-Bandbreite wird über `slew_max` (live) getunt. **Fallback
   dokumentiert:** wenn Sim/HW zu träge dämpft, erst `Kd`↑, dann `slew_max`↑, zuletzt D am Slew
   vorbei. ⚠️ **Test-Doku muss diesen Tuning-Pfad komfortabel führen** (User-Wunsch) — fertige
   `ros2 param set`-Zeilen + „beobachte X"-Erwartung pro Schritt (TF2.8).
3. **Kd-Start + Achsen — ✅ beide Achsen, klein starten.** D auf roll **und** pitch. Startwert
   **`Kd ≈ 0.03 s`** (Auslegung: ~50°/s Wackeln → ~1–2° Gegen-Korrektur), **live tunbar**, in Sim
   hochtasten. ⚠️ D differenziert → **rausch-verstärkend**: gz-IMU ist rauschfrei (Sim zeigt das
   nicht), auf HW ggf. `Kd` zurücknehmen (D6: Sim=Logik, HW=Gains).
4. **roll-Eingang — ✅ roh (roll→0).** Für TF-2 = Geradeaus-Klettern + robuste Seiten-
   Stabilisierung. **Quer-/Diagonal-Traversieren ist ein eigener späterer Block** (roll auf
   Residual **+** `cmd_vel`-Richtungslogik, weil eine roll-Neigung je nach Fahrtrichtung „gewollter
   Seithang" *oder* „Schieflage" ist) — siehe §6. **Unebenes per-Fuß-Terrain bleibt Stufe 4**
   (Fußtaster), von dieser Entscheidung unabhängig.
5. **Gating — ✅ wie 3a** (STANDING+WALKING+STOPPING). Im STANDING auf dem Hang ist roll→0 +
   pitch=Hang sinnvoll (No-Op wenn schon parallel).
6. **Startup-Grace — ✅ beibehalten.** Im terrain-Modus konvergiert nur eine kleine Korrektur →
   Grace greift praktisch nie, schadet aber nicht (Sicherheitsnetz; TF-1-Residual-Tip fängt die
   Anfangs-Hangneigung ohnehin).

## 5. Design-Entscheidungen (mit verworfenen Alternativen)

| Entscheidung | Gewählt (freigegeben) | Verworfen / Alternative | Warum |
|---|---|---|---|
| „pitch folgt Hang" | **pitch-Eingang = Residual** (Sollwert intern 0) | pitch-Sollwert dynamisch = Hang setzen | mathematisch identisch, aber Regler bleibt **unverändert** + nutzt TF-1-Residual wieder |
| „roll → 0" | **roll-Eingang = roh** (Sollwert 0) | roll-Residual (slope-kompensiert) | Geradeaus-Klettern hat keinen gewollten roll → voll auf 0; Seithang = später |
| Wackel-Dämpfung | **Gyro-D im BalanceController** | separater Dämpfungs-Node / Topic | teilt Stellpfad + Clamp, ein Modul, kein 50-Hz-Topic-Umweg (= das alte „3b") |
| D vs. Totband | **D wirkt immer** (auch im Winkel-Totband) | D ebenfalls totband-gaten | Wackeln = kleiner Winkel + hohe Rate → sonst würde D im Totband genau dort nichts tun |
| Regler-Struktur | **bestehender Totband-PI wiederverwendet** + D | neuer Regler from scratch | Stufe 2 ist getestet/envelope-bewiesen; minimaler, risikoarmer Eingriff |
| Stellpfad/Envelope | **Stufe-2/3a-Rotation + Clamp unverändert** | neue θ-Geometrie-Tabelle / Offline-Tool | TF-Korrekturen sind klein → mühelos im Envelope (kein Voll-Aufrichten) |
| Modus | **`leveling_mode` {horizontal,terrain}**, Default terrain | terrain hart ersetzt horizontal | behält statisches Horizontal-Stehen (Stufe 2) als Option |
| Kante/Stufe (35°) | **out-of-scope (Stufe 4 Fußtaster)** | in TF-2 lösen wollen | kein Balance-Problem (fehlender Bodenkontakt) → prinzipiell nicht per IMU lösbar |

## 6. Nachfolge-Block: Quer-/Diagonal-Traversieren (NICHT in TF-2, bewusst getrennt)

> **Festgehalten auf User-Wunsch**, damit es später wiedergefunden wird. TF-2 regelt
> **roll → 0** (Fokus Geradeaus-Klettern). Reines **Quer-/Diagonal-Traversieren am Hang** (Hang
> seitlich/schräg) ist damit *funktionsfähig, aber suboptimal* — der Regler richtet den Seithang-
> roll bis zum Clamp (~4°) teilweise auf (kein Umkippen, aber leicht „aufgerichteter" Look).

**Was der eigene Block bräuchte (Scope):**
- **roll-Eingang auf Residual** umstellen (slope-kompensiert, symmetrisch zu pitch) → „roll **folgt**
  dem Seithang" statt ihn auf 0 zu zwingen.
- **`cmd_vel`-Richtungslogik** als Disambiguierung: eine roll-Neigung ist **je nach Fahrtrichtung**
  ein *gewollter Seithang* (folgen) ODER eine *ungewollte Schieflage/Kippgefahr* (ausgleichen).
  Fahre ich seit-/diagonalwärts → roll-Neigung gewollt → folgen; fahre ich geradeaus → ausgleichen.
  Ohne diese Logik wäre „roll auf Residual" ein stumpfes „folge allem" und verlöre die roll→0-
  Robustheit. **Genau deshalb gehört es nicht halb in TF-2, sondern als eigener, sauberer Block.**

**Abgrenzung zu Stufe 4:** *Quer-Traversieren* (globale Seithang-Lage) ≠ *unebenes per-Fuß-Terrain*.
Letzteres sieht die IMU prinzipiell nicht (sie kennt nur die Gesamt-Körperneigung) → bleibt
**Stufe 4 (Fußkontakt-Taster)**, unabhängig von dieser roll-Frage.

**Reihenfolge:** nach TF-2 (und ggf. TF-3). Eigener §4-Review → Freigabe → Code → Test.

## 7. Doku-/Querverweis-Plan (bei Live-Schaltung / nach Fertigstellung nachziehen)

- **[`../../project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md)**
  (Eintrag „IMU-Balance/Leveling/Kipp"): nach TF-2-Abschluss ergänzen — `leveling_mode`
  {horizontal,terrain}, Gyro-D (`leveling_kd`), **die roll→0-Entscheidung + der Quer-Traversieren-
  Nachfolge-Block** (§6), damit beides später auffindbar ist (**User-Wunsch**).
- `hexapod_gait/README.md`: terrain-Modus, per-Achse-Sollwert, Gyro-D, neue Params (TF2.7).
- [`imu_balance_progress.md`](imu_balance_progress.md): TF-2-Checkliste abhaken (Done-Vertrag).
- `architecture.md`: ggf. `leveling_mode`/`leveling_kd` bei der Balance-Beschreibung erwähnen
  (Sim-only bis HW-Schaltung; konsistent mit TF-1 `/imu/slope`-Defer).
