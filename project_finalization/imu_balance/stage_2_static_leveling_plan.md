# Stufe 2 — Statisches Körper-Leveling

> Stufe 2 von Block A5 ([Master](00_imu_balance_plan.md)). **Ziel:** auf einer
> **statischen Schräge** den Körper horizontal halten (roll/pitch → 0), indem die
> Fuß-Targets um eine Körper-Rotation gedreht werden — geliefert von einem
> **austauschbaren `BalanceController`**. Erste echte geschlossene Regelschleife.
> **Nur STANDING** (Laufen = Stufe 3).
>
> **Status: ⚪ offen — §4-Plan-Review erledigt, Entscheidungen stehen (§4/§5).**
> User liest den Plan, danach Implementierung. Test-Befehle entstehen am Ende
> der Implementierung. Voraussetzung: Stufe 0 + 1 (🟢).

---

## 0. Kontext & Voraussetzungen

- Stufe 0: `/imu/data` fließt; Stufe 1: `gait_node` abonniert es schon, hat
  `_imu_roll`/`_imu_pitch`. Stufe 2 baut darauf auf.
- Hier werden die **Risiken 1 (IKError→Freeze), 2 (CoG/Selbst-Kollision A4),
  3 (Fuß-Scrub), 6 (zwei Limit-Quellen)** aus dem Master scharf.
- B4/Show-Pose hat den Base-Frame-Umweg (`leg_to_base_frame` → modifizieren →
  `base_to_leg_frame`) bereits gebaut — Leveling = dasselbe Muster als **Rotation**.

## 1. Logik-Skizze / Pseudocode

### A. Schräg-Welt (`hexapod_gazebo/worlds/`) — **parametrisch, mild, stehend spawnen**
- **Ein parametrisches `slope.sdf`** (Neigungswinkel via Launch-Arg), Basis wie
  `empty_imu.sdf` (inkl. `gz-sim-imu-system`!) + geneigte **Stützfläche**: große
  dünne **statische Box** (z.B. 6×6×0.2 m) um θ geneigt, hohe Reibung
  (`mu1=mu2≥1.0`). Box-Struktur so schneiden, dass die **Stufe-3-Keilwelt**
  (flach→Steigung, zum Hineinlaufen) daraus wiederverwendbar ist.
- **Roboter spawnt stehend** auf der gekippten Fläche (Spawn-Pose-Offset: z +
  Orientierung, damit die Füße auf der Box sitzen). Begründung (Plan-Review):
  der Hexapod startet realistisch nie auf einem steilen Hang, sondern läuft von
  eben hinein (= Stufe 3). Der statische Leveling-Test braucht aber nur einen
  *stehenden* Kipp-Test → milder Hang genügt.
- **Test-Winkel 5/8/10°** — alle **≤ `tip_angle_warn` (15°)**, damit der
  Anfangs-Transient die Stufe-1-Kipp-Erkennung nicht triggert (siehe §4).
- Holt zugleich den **strikten Ground-Truth (T0.3)** + die **Stufe-1-Schwellen-
  Feinjustage** nach (statischer Kippwinkel = sauber vergleichbar).

### B. BalanceController (`hexapod_gait/balance_controller.py`, ROS-frei, testbar)
- Schnittstelle: `update(roll, pitch, dt) -> (corr_roll, corr_pitch)` (Setpoint 0
  intern). Gleiche Trennung wie `TipMonitor`/Kinematik.
- **v1-Gesetz** pro Achse: **Totband-PI + Slew-Rate-Limit + Anti-Windup**:
  - `error = 0 − measured` (Soll = horizontal).
  - **Totband:** `|error| < deadband` → Integrator einfrieren / kein Korrektur-
    Update (kein Chattern der 18 Servos um die Soll).
  - **PI:** `out = Kp·error + Ki·∫error`.
  - **Slew:** `|Δcorr/dt| ≤ slew_max` (sanft → schützt vor Fuß-Scrub-Spikes).
  - **Anti-Windup:** Integrator clampen; `out` clampen auf `max_level_angle`.
- Liefert die **Körper-Rotation**, die die gemessene Neigung kontert (Vorzeichen:
  Körper gegen die Neigung drehen).
- **Austauschbar:** dahinter passt als zweite Implementierung das **Dual-Tiefpass/
  Dual-Fenster-Schema** des Users (Vergleich in Gazebo, Master D3).

### C. Stellpfad in der Engine (`gait_engine.py`)
- neue Methode `set_body_orientation_offset(corr_roll, corr_pitch)` (cached die
  Korrektur, wie `set_command`).
- zentral in `compute_joint_angles` (Stufe 2: nur im STANDING-Pfad): pro Bein
  `leg_to_base_frame(target)` → `R(corr_roll, corr_pitch)` um base-Ursprung →
  `base_to_leg_frame` → `leg_ik`. = B4-Round-Trip als Rotation.
- **Clamp VOR der IK (Risiko 1):** die kommandierte Korrektur darf **nie**
  out-of-envelope sein → kein `IKError`-Freeze durch Leveling. Strategie (entschieden,
  §4): harter Clamp auf `max_level_angle` (offline in 2.5 als envelope-sicher bewiesen,
  Start 10°) **+ IKError-Fallback** (bei IKError Korrektur skalieren statt freezen).
  Limits = **URDF-geparste** `joint_limits` (Risiko 6, NICHT stale config.py).

### D. ROS-Glue (`gait_node`)
- `/imu/data` schon abonniert (Stufe 1). Im Tick (nur STANDING):
  `corr = self._balance.update(roll, pitch, dt)` → `engine.set_body_orientation_offset(*corr)`.
- Params: `leveling_enable`, `Kp`, `Ki`, `deadband_deg`, `slew_max_dps`,
  `max_level_angle_deg`.
- **Gating:** nur STANDING (Stufe 2). Sonst `corr=0` + Controller-`reset()`.

### E. Fuß-Scrub / Reposition (Risiko 3)
- Beim Leveln im Stand müssen die aufgesetzten Füße relativ zum Boden wandern
  (geschlossene Kette). Bei kleinen Winkeln + Slew gering. Watch-Item: übersteigt
  die Korrektur eine Scrub-Schwelle → kurze **Reposition** (lift-and-reset,
  `REPOSITION`-Muster). v1 evtl. erst kleine Winkel + Slew, Reposition als Option.

### F. CoG / Selbst-Kollision (Risiko 2)
- Offline prüfen: gelevelte Stand-Pose bei max θ ist **CoG-stabil + in-limit +
  kollisionsfrei** (A4 reaktivieren). Am Hang schrumpft das Stützpolygon bergab.

## 2. Tests-Liste (mit Begründung)

| Test | Prüft | Done-Idee |
|---|---|---|
| Unit BalanceController | Totband, PI-Konvergenz, Slew, Anti-Windup, max-Clamp | pytest grün |
| Unit/Engine Rotation | `R` auf Targets korrekt (Round-Trip; bekannte Eingabe → erwartete Joints) | pytest grün |
| Offline-Envelope | gelevelte Pose für θ∈{5,8,10,15°} in-limit + CoG-stabil (θ als Tool-Arg) | envelope-Tool grün |
| Sim (live, am Ende) | auf milden Hängen (`slope` 8/10°) levelt Körper ~θ→~0°, bleibt, **kein** IKError/Freeze, Scrub klein | Ground-Truth (gz-Pose) ≈ 0° |
| Ground-Truth strikt (T0.3-Nachhol) | IMU vs. statischer Rampenwinkel | ±1–2° |

**Bewusst NICHT:** Laufen (Stufe 3), Gyro-Wackel-Dämpfung (Stufe 3),
Hang-Parameter-Adaption (Stufe 3), Terrain/Kontakte (Stufe 4).

## 3. Progress-Checkliste (Template → Progress-File)

```
- [ ] 2.1 Parametrische slope.sdf (geneigte Box, Winkel via Launch-Arg, gz-sim-imu-system) + Roboter stehend spawnen (Spawn-Pose-Offset) + Launch-Resolve; Box-Struktur Stufe-3-keilwelt-tauglich
- [ ] 2.2 BalanceController (ROS-frei): Totband-PI + Slew + Anti-Windup + max-Clamp + Unit-Tests
- [ ] 2.3 geometry.rotate_xy-Helfer + gait_engine: set_body_orientation_offset + R-Rotation in compute_joint_angles (STANDING) + Clamp VOR IK (URDF-Limits) + IKError-Fallback (skalieren statt freezen)
- [ ] 2.4 gait_node: BalanceController-Wiring (STANDING-Gating) + Params (Kp/Ki/deadband/slew/max_level_angle/leveling_enable) + Live-Tuning via _on_param_change (Leveling- UND Stufe-1-Tip-Params) + optionaler Startup-Grace-Gate
- [ ] 2.5 Offline-Envelope/CoG-Check (θ als Tool-Argument → Re-Check anderer Winkel billig) für θ∈{5,8,10,15°} (A4 reaktiviert); bestätigt max_level_angle (Start 10°)
- [ ] 2.6 Fuß-Scrub bewertet (akzeptiert oder Reposition-Trigger)
- [ ] 2.7 Sim-Verify auf milden Hängen (slope 8/10°): Leveling ~θ→~0°, Ground-Truth, kein Freeze, Scrub klein + strikter T0.3-Nachhol
- [ ] 2.8 README/Konzept-Update (Leveling, Stellpfad, Clamp+Fallback, parametrische Welt)
- [ ] 2.9 colcon test + Lint grün
- [ ] 2.10 kritische Self-Review-Tabelle
```

## 4. Plan-Review — getroffene Entscheidungen

> Die „Offene Punkte" wurden im §4-Plan-Review (CLAUDE.md §4) entschieden. Die
> ursprünglichen Optionen siehe Git-Historie dieser Datei.

- **Clamp-Strategie:** fester `max_level_angle` (Start **10°**, offline in 2.5 als
  envelope-sicher zu beweisen) **+ IKError-Fallback** — bei IKError die Korrektur
  skalieren (z.B. ×0.5) und erneut versuchen, **statt den ganzen Roboter zu
  freezen** (Risiko 1). Zwei Schichten: bewiesene statische Schranke + dynamisches
  Sicherheitsnetz; eine Lücke im Offline-Beweis degradiert sanft („weniger
  Leveling"). Limits = **URDF-geparst** (Risiko 6). *Offline-Envelope-Lookup pro
  Stance-Modus = Stufe-3-Option, falls echte Hänge >10° verlangen.*
- **Setpoint:** **horizontal (0/0)**. Body-Mitneigen zum Hang (mehr Beinrange →
  steilere Hänge, Preis: CoG-Marge) ist ein bewusster Stufe-3-Knopf (Teil der
  θ→Parameter-Familie, Weg A), **hier nicht** umgesetzt.
- **Welt-Modellierung:** **ein parametrisches `slope.sdf`** (Winkel via Launch-Arg),
  Box-Struktur wiederverwendbar für die Stufe-3-Keilwelt. Roboter **spawnt stehend**
  auf milder Neigung. Test-Winkel **5/8/10°** (alle ≤ tip_warn). Siehe §1.A.
- **Nur STANDING:** bestätigt (Laufen = Stufe 3).
- **⚠️ Wechselwirkung Leveling ↔ Tip-Erkennung:** entschärft durch die milden
  Test-Hänge. Physik: Leveling hält den **Body** horizontal → die body-montierte
  IMU liest nach Konvergenz roll/pitch ≈ **0**, obwohl der Roboter am Hang steht →
  Tip (liest dieselbe IMU) sieht ~0 von allein. Einziger Konfliktfall = der
  **Transient** beim Spawn; bei Hängen **≤ tip_warn (15°)** bleibt der unter der
  Schwelle. Daher: **Stufe-1-Tip-Logik unverändert**, nur ein optionaler kurzer
  **Startup-Grace-Gate** (Tip ~1 s nach Spawn / solange `|corr|` aktiv slewt
  unterdrücken; WARN in STANDING ist ohnehin nur `cmd_vel=0`, harmlos). Die echte
  **Residual-Tip + Konvergenz-Gate**-Robustheit für *steile* Hänge → **Stufe 3**
  (Hineinlaufen, Leveling durchgehend aktiv → IMU bleibt klein).
- **Live-Tuning:** Leveling-Params **und** Stufe-1-Tip-Params über
  `_on_param_change` live verstellbar (rqt_reconfigure) — fürs Rampen-Tuning (löst
  zugleich den Stufe-1-Post-Review-Punkt „tip-Params Init-only").
- **Fuß-Scrub:** in v1 **akzeptieren** (kleine Winkel + niedrige Slew);
  Reposition-Trigger vorgemerkt, nicht implementiert (siehe §1.E).
- **Start-Gains** (live tunbar, auf der Rampe nachziehen): `Kp≈0.4`, `Ki≈0.1`,
  `deadband≈1.5°`, `slew_max≈8°/s`, `max_level_angle=10°`. Konservativ → langsamer
  Winkel-Loop, kein Servo-Jagen.
- **max θ:** der Clamp deckelt den *voll-gelevelten* Hang auf `max_level_angle`
  (10° Start). Der *physikalisch* stehbare Max-Hang (CoG/Reibung) ist davon getrennt
  und kommt aus dem Offline-CoG-Check (2.5) + Sim.
- **Aufstehen auf der Schräge:** entfällt für Stufe 2 — der Roboter **spawnt
  stehend**. Standup-auf-Schräge / eben-aufstehen-dann-hineinlaufen = Stufe 3.

## 5. Design-Entscheidungen (final aus dem Plan-Review)

| Entscheidung | Gewählt | Alternative | Warum |
|---|---|---|---|
| Regler-Modul | austauschbarer ROS-freier `BalanceController` | inline im Node/Engine | unit-testbar + Algorithmus tauschbar (Master D1/D3) |
| Stellpfad | `R(roll,pitch)` zentral in `compute_joint_angles` (B4-Muster), neuer Helfer `rotate_xy` | in jeden Trajektorien-Generator | eine Stelle, kein Verstreuen (Master D2) |
| Clamp | **vor** der IK, gegen URDF-Limits, fester max 10° **+ IKError-Fallback** (skalieren) | nur fester max / Lookup pro Stance | IKError = Freeze des ganzen Roboters (Risiko 1); Fallback = sanfte Degradation |
| Setpoint | horizontal (0/0) | Mitneigen-Blend (α·θ) | Stabilität + Kamera-Horizont; Mitneigen = Stufe-3-Knopf (Beinrange↔CoG) |
| v1-Gesetz | Totband-PI + Slew + Anti-Windup | Dual-Tiefpass/Dual-Fenster | kleinerer Parameterraum; Dual-Schema als 2. Impl offen |
| Welt | **ein parametrisches `slope.sdf`**, stehend spawnen, 5/8/10° | feste Winkel-Files / Keilwelt jetzt | flexibel, Keilwelt-wiederverwendbar; Keil/Hineinlaufen = Stufe 3 |
| Tip↔Leveling | Tip unverändert + Startup-Grace, milde Hänge | Residual-Tip + Konvergenz-Gate jetzt | milde Hänge → IMU geht nach Konvergenz auf ~0; Residual-Robustheit erst Stufe 3 nötig |
