# Stufe 3 / TF-1 — Passiv Terrain-Following + slope-bewusster Tip

> Erste Teil-Stufe von [Stufe 3 Terrain-Following](stage_3_terrain_following_plan.md) (Block A5).
> **Ziel:** den Roboter Hänge **passiv** hochlaufen lassen (Körper folgt dem Boden, nominal
> Stance — kein aktives Leveln) und die **Stufe-1-Kipp-Erkennung slope-bewusst** machen, damit
> sie auf der gewollten Hang-Neigung **nicht fehlalarmiert**. Dann in Sim **charakterisieren**,
> wie steil er passiv kommt (Grenze = Kippen/Traktion, nicht Bein — [Retro](terrain_following_pivot_retro.md)).
>
> **Status: ⚪ offen — Plan zum Review.** §4-Workflow: Plan → **User-Freigabe** → Code → Test →
> Self-Review. Voraussetzung: Stufe 0/1 (🟢). Nachfolge: **TF-2** (aktive Körper-Stabilisierung).

---

## 0. Kontext & Abgrenzung

- **Passiv Terrain-Following ist kein neuer Regler** — mit `leveling_enable:=false` (Default)
  läuft der Roboter ohnehin mit Nominal-Stance, und der Körper **folgt dem Boden von allein**
  (Bein-Geometrie identisch zur Flach-Pose, [Retro](terrain_following_pivot_retro.md)). TF-1
  baut also **keinen** Stellpfad — der einzige Code ist die **slope-bewusste Tip-Erkennung** +
  eine **Hang-Schätzung**. Die aktive Stabilisierung (roll→0, pitch→folgen, Gyro-D) ist **TF-2**.
- **Warum slope-bewusster Tip nötig:** die Stufe-1-`TipMonitor` vergleicht die Neigung gegen
  **absolute** Schwellen (WARN 15° / CRIT 25°). Am 8°-Hang ist die Neigung gewollt 8° → noch
  ok. Aber TF kommt vermutlich **deutlich steiler** als 8° → ab ~15° Hang würde die absolute
  Schwelle **fälschlich** feuern. Für die Steil-Charakterisierung brauchen wir die Schwelle
  **relativ zum Untergrund**.

## 1. Logik-Skizze

### 1.1 Hang-Schätzung (gait_node)
- **Langsamer Tiefpass** auf die IMU-Neigung: `slope_roll/pitch = LP(roll, pitch, τ)`. Weil der
  Körper passiv dem Boden folgt, **ist die langsame Neigungs-Komponente der Untergrund**.
- **Zeitkonstante τ** so wählen, dass sie dem Hang folgt (Rampen-Eintritt ~1–2 s) aber **einen
  Sturz nicht trackt** (Sturz ~0.3–0.5 s) → Startwert **τ ≈ 1.0 s**. Der Lag ist genau der
  Mechanismus, der einen schnellen Kipp sichtbar macht.
- **Clamp** der Schätzung auf einen plausiblen Max-Hang (z.B. ±30°), damit ein *langsames*
  Wegkippen die Schätzung nicht beliebig „mitwandern" lässt (sonst würde der residual nie groß).

### 1.2 Slope-bewusster Tip (residual statt absolut)
- Statt der rohen Neigung bekommt die `TipMonitor` das **residual** = gemessene Neigung −
  Hang-Schätzung: `res_roll = roll − slope_roll`, `res_pitch = pitch − slope_pitch`.
- Die **Kipprate** (`tilt_rate` aus dem Gyro) bleibt **roh** — eine Sturz-Drehrate ist
  hang-unabhängig und ist der primäre Schnell-Sturz-Fänger.
- Wirkung: **stetiger Hang → residual ≈ 0 → kein Fehlalarm**; **echter Kipp** (schnell →
  Filter lagt → residual wächst, + Rate-Spike) → feuert wie gehabt (WARN→cmd_vel=0,
  CRIT→Freeze). Die `TipMonitor`-Logik selbst bleibt **unverändert** (bekommt nur residual).
- **Achsen-Hinweis (TF-Prinzip):** beim Geradeaus-Klettern ist roll gewollt ~0; der Tiefpass auf
  roll folgt dann ~0 → `res_roll ≈ roll`. Auf pitch folgt er dem Hang → `res_pitch` klein. Das
  deckt sich automatisch mit „roll überwachen / pitch dem Hang zugestehen". (Aktiv geregelt wird
  das erst in TF-2.)

### 1.3 Hang-Schätzung publizieren (optional, klein)
- `slope_roll/pitch` (Grad) auf ein Topic (z.B. `/imu/slope`) loggen — hilft der Sim-
  Verifikation („trackt die Schätzung den echten Hang?") und ist die Grundlage für TF-2.

### 1.4 Param-Schalter
- `slope_aware_tip_enable` (bool, Default **true** — strikt besser als absolut, sobald IMU da),
  `slope_estimate_tau_s` (Default 1.0), live tunbar (`_on_param_change`). Fällt die IMU aus
  (kein `/imu/data`): wie Stufe 1 graceful (TipMonitor NONE), Schätzung 0.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| **Unit: Tiefpass** | Konvergenz gegen konstante Eingabe; Lag bei Sprung | bekannte τ → erwartete Annäherung/Lag |
| **Unit: residual** | `res = measured − slope`; Clamp der Schätzung greift | Werte korrekt |
| **Unit: slope-aware Tip** | konstante Neigung (= Hang) → **kein** WARN/CRIT; schneller Neigungs-Sprung (+Rate) → feuert | residual-gefütterte `TipMonitor` |
| **Node-Smoke** | Schätzer + residual-Tip-Pfad laufen (rclpy) | kein Crash, Param live |
| colcon + Lint | alle bestehenden + neue grün | 0 Fehler |
| **Sim (User)** | Rampe steigend (8/12/16/20°): passiv hochlaufen, **Körper folgt dem Hang** (hangparallel, natürlich), slope-aware-Tip feuert **nicht** fälschlich; **bis wie steil** kommt er (Kippen/Rutschen)? | qualitativ + `/imu/monitor`+`/imu/slope` |

**Bewusst NICHT getestet (→ spätere Stufen):**
- Aktive Stabilisierung (roll→0, pitch→folgen, Gyro-Wackel-Dämpfung) → **TF-2**.
- Quer-/Diagonal-Hang (roll-Komponente des Hangs) → später.
- Schwerpunkt-Hilfe / Schlupf-Erkennung → TF-3.
- Unebenes per-Fuß-Terrain + Fußkontakte → Stufe 4.

## 3. Progress-Checkliste (→ Progress-File, Done-Vertrag)

```
TF-1:
- [ ] TF1.1 Hang-Schätzung in gait_node (langsamer Tiefpass auf roll/pitch, τ-Param, Clamp ±max)
- [ ] TF1.2 slope-bewusster Tip: residual (= IMU − Schätzung) an TipMonitor, tilt_rate roh; Param slope_aware_tip_enable (+ live)
- [ ] TF1.3 (optional) Hang-Schätzung auf /imu/slope publizieren (Sim-Verifikation)
- [ ] TF1.4 Unit-Tests (Tiefpass, residual+Clamp, slope-aware Tip feuert/feuert-nicht) + Node-Smoke
- [ ] TF1.5 colcon test + Lint grün
- [ ] TF1.6 README/Konzept-Update (hexapod_gait: passiv TF, Hang-Schätzung, slope-bewusster Tip)
- [ ] TF1.7 Test-Doku stage_3a_passive_tf_test_commands.md (Rampen-Ladder 8–20°) + Sim-Verify durch User
- [ ] TF1.8 kritische Self-Review-Tabelle (OK/🔴/🟡/🟢)
```

## 4. Offene Punkte für User-Review (vor Code)

- **τ des Tiefpasses** (Startwert 1.0 s?) — folgt dem Rampen-Eintritt, trackt aber keinen
  Sturz. Auf der Rampe nachtunen (live).
- **residual beide Achsen** (roll **und** pitch slope-kompensiert) **vs. nur pitch** (roll
  absolut, weil beim Geradeaus-Klettern gewollt 0). Vorschlag: **beide** (robust für Seithang,
  und beim Geradeaus-Lauf folgt roll-LP eh ~0). Bestätigen.
- **Slope-Clamp-Max** (±30°?) gegen „langsames Wegkippen trackt mit".
- **`/imu/slope`-Topic** — brauchen/wollen wir das (TF1.3), oder reicht `/imu/monitor`?
- **Sim-Charakterisierungs-Winkel** (8/12/16/20° — oder feiner)?

## 5. Design-Entscheidungen (mit verworfenen Alternativen)

| Entscheidung | Gewählt | Verworfen / Alternative | Warum |
|---|---|---|---|
| Passiv TF | **kein neuer Regler** (= Baseline `leveling_enable:=false`) | aktiver „TF-Modus" jetzt | Körper folgt dem Boden von allein; aktive Regelung = TF-2 |
| Slope-bewusster Tip | **residual = IMU − langsame Hang-Schätzung** an `TipMonitor` | (a) absolute Schwelle hochsetzen (verliert Empfindlichkeit am Steilhang); (b) Tip am Hang ausschalten (unsicher) | residual feuert relativ zum Untergrund → empfindlich UND fehlalarmfrei |
| TipMonitor | **unverändert** (bekommt residual statt roh) | TipMonitor refactoren | minimaler Eingriff, Stufe-1-Logik bleibt geprüft |
| Kipprate | **roh** (nicht slope-kompensiert) | auch kompensieren | Sturz-Drehrate ist hang-unabhängig → primärer Schnell-Fänger |
| Hang-Schätzung | **langsamer Tiefpass auf IMU** (Körper folgt Boden) | aus Fußkontakten schätzen | Fußkontakte = Stufe 4; passiv reicht IMU direkt |
| Schätzung-Clamp | **auf plausiblen Max-Hang** | ungeclampt | sonst trackt der Filter ein langsames Wegkippen mit |
