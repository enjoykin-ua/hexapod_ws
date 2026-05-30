# Phase 13 Stage 0.2 — Femur-Mech-Umbau + Re-Cal (Weg A) + Femur-Limits

> **Übergeordnet:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §3/§4.
> **Vorbedingung:** Sub-Stage 0.1 ✅ (manuelle Relay-Steuerung
> `/hexapod_relay_set` + FW geflasht).
> **Test-Anleitung:** [`phase_13_stage_0_2_remount_recal_test_commands.md`](phase_13_stage_0_2_remount_recal_test_commands.md).
> **Status:** ✅ finalisiert 2026-05-30 (K1–K6 eingearbeitet, Decisions §4
> geklärt). Bereit für Umbau nach Commit.

**Ziel:** Die 6 Femur-Segmente werden mechanisch so versetzt, dass der Servo
bei seiner Power-On-Mitte (~1500 µs) **35° nach oben** zeigt. Anschließend
werden die 6 Femur-Pins **re-kalibriert** (Weg A: `rad=0` bleibt horizontal)
und die Femur-Joint-Limits auf die neue **asymmetrische** Mech-Range gesetzt.
URDF-Geometrie / IK-Formel / Gait bleiben **unangetastet**.

---

## 1. Logik-Skizze / Vorgehen

### 1.1 Mechanischer Umbau (User, pro Bein) — §6-Servo-Trick

**Warum der Trick:** „35° hoch" ist per Auge schlecht treffbar, „horizontal"
(0°) dagegen leicht (Wasserwaage / Augenmaß). Wir lassen den **Servo** den
35°-Offset definieren, montieren das Segment in der leicht treffbaren
Horizontalen, und drehen den Servo dann zurück zur Mitte.

Pro Bein:
1. Plugin läuft, `/hexapod_relay_set true` → Servos bestromt.
2. **Alle Femurs auf `rad = +0.611`** kommandieren (= +35°, IK-Konvention
   `+` = nach unten). Wegen der Direction-Map fahren alle 6 Femurs physisch
   **35° nach unten** — einheitlicher rad-Wert, kein per-Bein-Vorzeichen
   nötig (das Plugin spiegelt links/rechts selbst).
3. **Pro Bein:** Femur-Segment vom Servo-Horn lösen (Horn bleibt am Servo,
   Servo-Welle-Winkel unverändert), Segment in die **Horizontale** drehen
   (Wasserwaage), wieder festschrauben.
4. Nach allen 6: **`rad = 0`** kommandieren → Servo dreht 35° zurück → das
   (horizontal montierte) Segment hebt sich 35° → zeigt **35° nach oben**.
5. **Effekt:** bei Servo-Mitte (Power-On) = 35° hoch (Ziel erreicht).

> **Direction-Verifikation pro Bein (User-Hinweis §10.2):** beim Umbau pro
> Bein prüfen, dass `rad=0` nach dem Festschrauben wirklich „35° hoch" ergibt
> (nicht 35° runter). Falls ein Bein falsch herum geht → Segment um die
> Gegenrichtung montieren. Die Direction-Map in `servo_mapping.yaml` bleibt
> unverändert (Servo wird nicht gedreht).

> **K2 — 35° bestätigt (User 2026-05-30):** die 35°-Ruhepose ist
> **kollisionsfrei** (kein Body-Anschlag am Ruhepunkt). Nach Umbau ist die
> Range nach oben kürzer / nach unten länger — genau das fängt der Re-Cal
> (§1.2/§1.3) ein. 35° ist damit **fix**, keine provisorische Reduktion nötig.

> **K5 — Halten beim Umbau (User 2026-05-30):** enabled Servos lassen sich von
> Hand kaum bewegen; die JTC hält `rad=+0.611` stabil, die Referenz verrutscht
> beim Ab-/Anschrauben nicht. Hinweis: zwischen Umbau und Re-Cal zeigt RViz bei
> `rad=0` noch Horizontal, die HW aber 35° hoch — **erwarteter** Mismatch bis
> der Re-Cal fertig ist.

**Alternative (verworfen, als Fallback dokumentiert):** §12-Simpel —
bei `rad=0` (horizontal) abschrauben, Segment per Protraktor 35° hoch drehen,
festziehen. Verworfen weil 35°-Augenmaß ungenauer als Horizontale.

### 1.2 Re-Cal der 6 Femur-Pins (Weg A) — pulse_zero/min/max

Über die Phase-11-Live-Cal (rqt_reconfigure + `/servo_pulses`/GET_STATE-Ablesung
+ `/save_calibration`). **Direction-Map bleibt unverändert** — der Servo wird
nicht gedreht, nur das Segment.

> **⚠️ K4 — Clamp zuerst weiten:** die aktuellen `pulse_min/max` klemmen den
> Output (Stage 0.5). Um die *neuen* Anschläge zu erreichen, in rqt_reconfigure
> die Range erst weiten (innerhalb der globalen [800, 2200] µs), dann die Pins
> bis zum mech-Anschlag fahren und ablesen, dann auf die gefundenen Werte
> setzen.

> **⚠️ K1 — direction-aware erfassen:** „nach oben" / „nach unten" ≠ fest
> `pulse_min`/`pulse_max`! Femur-Direction ist rechts (1/2/3) = `+1`, links
> (4/5/6) = `−1`. Für linke Beine ist „unten" das **kleinere** µs. Daher:
> Anschläge **physisch nach up/down** erfassen, dann **numerisch** zuordnen.

Pro Femur-Pin (1, 4, 7, 10, 13, 16):
- **`pulse_zero`** = jog bis Femur **visuell horizontal** → notieren.
  (≈ Servo-Mitte ± ~35°-wert; für leg_1 illustrativ ~1727 µs statt alt 1460.)
- **Up-Anschlag**-µs = jog nach **oben** bis mech-Anschlag (Body/Coxa-Kollision;
  Up-Range nach Umbau **kurz**) → notieren.
- **Down-Anschlag**-µs = jog nach **unten** bis Anschlag/Servo-Limit
  (Down-Range **lang**) → notieren.
- Dann **numerisch zuordnen**: `pulse_min = min(up_µs, down_µs)`,
  `pulse_max = max(up_µs, down_µs)`. (Rechte Beine: up=min, down=max.
  Linke Beine: down=min, up=max.)
- Invariante `pulse_min < pulse_zero < pulse_max` (calibration.cpp erzwingt).

### 1.3 Femur-Joint-Limits herleiten (der kritische Schritt)

**Problem:** Die Calibration ist linear je Segment: `rad=0→pulse_zero`,
`rad=joint_upper→pulse_max`, `rad=joint_lower→pulse_min`. Für korrekte
**Zwischen**-Winkel muss `joint_upper` = der **echte physische Femur-Winkel**
(rad, von horizontal) am Down-Anschlag sein — sonst stimmt die Steigung nicht
und die IK setzt den Fuß falsch.

**Lösung (Steigung erhalten, in Magnituden — direction-unabhängig):** Die
Servo-Linearität `k` (µs pro rad, Betrag) ist eine **Servo-Eigenschaft** und
wird vom Umbau **nicht** verändert (der Umbau dreht nur Segment ↔ Welle). `k`
ist zudem die **empirisch validierte** Steigung (mit ihr lief der Roboter
korrekt). Wir rechnen daher in physischen Winkeln (up/down) + Magnituden und
mappen am Ende auf den URDF-Frame:

1. `k` pro Pin aus dem **alten** Cal (Gesamt-Spanne, direction-unabhängig):
   `k = (pulse_max_alt − pulse_min_alt) / (joint_upper_alt − joint_lower_alt)`
   (leg_1: `(2120−815)/(1.493−(−1.493)) = 1305/2.986 ≈ **437 µs/rad**`)
2. Neue physische Winkel aus gemessenen Anschlägen + erhaltenem `k`:
   - `θ_down = |down_Anschlag_µs − pulse_zero_neu| / k`   (Betrag, → +rad)
   - `θ_up   = |up_Anschlag_µs   − pulse_zero_neu| / k`   (Betrag, → wird −rad)
3. Auf URDF-Frame mappen (für **alle** Beine gleich gemeint, da `+rad = unten`
   im Segment-Frame unabhängig vom Servo):
   - `joint_upper = +θ_down`   (max nach unten)
   - `joint_lower = −θ_up`     (max nach oben)

**Warum das ohne Protraktor stimmt:** `θ_down = |down_µs − zero|/k` ist exakt
der physische Femur-Winkel am Down-Anschlag (weil `Δµs = k·Δrad`). Und weil die
calibration-Steigung intern aus genau diesen Limits + Pulse-Extremen wieder `k`
ergibt, sind auch die **Zwischen**-Winkel korrekt. Die Direction-Spiegelung
steckt nur in der `pulse_min/max`-Zuordnung (§1.2) + dem `direction`-Feld — die
URDF-Limits selbst sind direction-frei.

**Verifikation (optional, empfohlen):** an 1–2 Beinen den physischen
Down-Anschlag-Winkel mit Protraktor gegen `joint_upper·180/π` prüfen
(Erwartung ±2°). Bestätigt die Linearitäts-Annahme.

### 1.4 Welche Dateien (Weg A)

| Datei | Änderung |
|---|---|
| `src/hexapod_hardware/config/servo_mapping.yaml` | 6 Femur-Pins: `pulse_zero`/`pulse_min`/`pulse_max` neu |
| `src/hexapod_description/urdf/hexapod_physical_properties.xacro` | Femur `joint_lower`/`joint_upper` → neue asymmetrische Werte |
| `src/hexapod_kinematics/hexapod_kinematics/config.py` | `_FEMUR_LIMITS` → identisch zur xacro |
| **NICHT geändert** | `leg.xacro` (Femur-Geometrie/origin), `leg_ik.py` (IK/FK-Formel), RViz, Gazebo |
| **→ Stage 0.3 (nicht hier)** | `initial_poses.yaml` Femur-Init — **K3**: Wert aus `pulse_us_to_radians(1500)` pro Pin ableiten (echte Servo-Mitte = wahre Power-On-Pose), nicht hartkodiert −0.611. Gehört zur Init-Sequenz |

> **Limit-Quelle:** Femur-Limits sind in `hexapod_physical_properties.xacro`
> die Single Source (Convention §11). Das Plugin liest sie aus dem URDF
> (`set_joint_limits`), die IK aus `config.py`. Beide müssen identisch sein.
> Global vs. per-Bein → siehe Offene Punkte 4.3.

> **K6 — Tibia/Coxa bewusst unangetastet:** nur die Femur-Segmente werden
> umgebaut. Der Femur-35°-Versatz ändert die Tibia-/Coxa-Cal **nicht**, weil
> die Tibia relativ zum Femur montiert bleibt und die IK die Kette (Coxa→Femur
> →Tibia) sauber durchrechnet. Tibia/Coxa-Limits + -Cal bleiben unverändert.

---

## 2. Tests-Liste mit Begründung

### 2.1 Statisch (CI / Build)

| Test | Prüft | Begründung |
|---|---|---|
| `xacro`-Parse + `colcon build` (description, kinematics, hardware) | neue Limits parsen, keine Syntaxfehler | Grundlage |
| `colcon test hexapod_kinematics` | IK-Tests weiterhin grün | Weg A ändert IK-Formel nicht → müssen unverändert grün bleiben (Regression-Wächter) |
| `colcon test hexapod_hardware` | calibration-Tests + `pulse_min<zero<max`-Guard grün mit neuen Werten | Cal-Konsistenz |

### 2.2 Live (interaktiv, Test-Commands)

| Test | Prüft |
|---|---|
| Re-Cal-Konsistenz: `rad=0` → Femur **horizontal** (HW) **und** RViz zeigt horizontal | Weg-A-Vertrag HW↔Sim |
| `rad=−0.611` → Femur **35° hoch** (HW) **und** RViz identisch; ≈ Servo-Mitte | Init-Pose-Pose stimmt |
| rad-Sweep über `[joint_lower, joint_upper]` → kein PWM-OoR-Freeze, keine Servo-Stall am Anschlag | Limits sicher |
| Power-On-Check: Relay aus → Plugin → `/hexapod_relay_set true` → Femurs fahren auf ~35° hoch (= Servo-Mitte), **kein** Sprung Richtung horizontal | Kern-Ziel der Stage 0 erreicht |
| (optional) Protraktor an 1–2 Beinen am Down-Anschlag vs. `joint_upper·180/π` | Linearitäts-Annahme |

### 2.3 Bewusst NICHT getestet (Scope-out)

- **Walking / Gait-Stand-up** — kommt in 0.3/0.4.
- **Gazebo-Stand-up-Dynamik** — 0.5.
- **Tibia/Coxa-Re-Cal** — unverändert (nur Femur umgebaut).
- **Automatische on_activate-Sequenz** — 0.3 (hier noch manuelles Relay).

---

## 3. Progress-Checkliste (→ `phase_13_stage_0_progress.md`)

```
### Sub-Stage 0.2 — Mech-Umbau + Re-Cal (Weg A) + Femur-Limits
- [ ] 0.2.1  Mech-Umbau alle 6 Femurs (§6-Trick), Direction pro Bein verifiziert
- [ ] 0.2.2  35°-Ruhepose pro Bein kollisionsfrei bestätigt (K2)
- [ ] 0.2.3  rqt-Clamp-Range geweitet (K4) zum Anschlag-Suchen
- [ ] 0.2.4  Re-Cal pulse_zero (=horizontal) für 6 Femur-Pins
- [ ] 0.2.5  Re-Cal up-/down-Anschlag → pulse_min/max direction-aware zugeordnet (K1)
- [ ] 0.2.6  servo_mapping.yaml 6 Femur-Einträge aktualisiert + pulse_min<zero<max ok
- [ ] 0.2.7  k pro Pin (alt) + joint_lower/upper hergeleitet (Magnituden, §1.3) — notiert
- [ ] 0.2.8  Entscheidung global vs per-Bein-Limits (Offene Punkte 4.3)
- [ ] 0.2.9  hexapod_physical_properties.xacro Femur-Limits aktualisiert
- [ ] 0.2.10 config.py _FEMUR_LIMITS identisch zur xacro
- [ ] 0.2.11 colcon build (description/kinematics/hardware) grün
- [ ] 0.2.12 colcon test kinematics + hardware grün (IK-Regression)
- [ ] 0.2.13 Live: rad=0 → horizontal (HW + RViz identisch)
- [ ] 0.2.14 Live: rad=-0.611 → ~35° hoch (HW + RViz identisch, ≈ Servo-Mitte)
- [ ] 0.2.15 Live: rad-Sweep über Limits → kein OoR-Freeze, kein Stall
- [ ] 0.2.16 Live: Power-On via Relay → Femurs ~35° hoch, kein Horizontal-Sprung
- [ ] 0.2.17 Self-Review-Tabelle, Fixe erledigt
# K3 (initial_poses.yaml Femur-Wert aus pulse_us_to_radians(1500)) → Stage 0.3
```

---

## 4. Entscheidungen (mit User geklärt 2026-05-30)

| # | Frage | Entscheidung |
|---|---|---|
| 4.1 | Umbau-Methode | ✅ **§6-Servo-Trick** (horizontal montieren, Servo macht die 35° exakt) — genauer als 35°-Augenmaß |
| 4.2 | Limit-Herleitung | ✅ **Steigung-erhalten** in Magnituden (§1.3), `k` aus altem Cal; optionale Protraktor-Stichprobe an 1–2 Beinen |
| 4.3 | Femur-Limits global vs per-Bein | ✅ **datengetrieben**: 6 Werte messen (0.2.7) → eng beieinander = global (Minimum); stark streuend = per-Bein. Entscheidung in 0.2.8 |
| 4.4 | Femurs live anfahren/halten | ✅ **JointTrajectoryController** — einmal `/leg_N_controller/joint_trajectory` mit Femur=+0.611 publishen, JTC hält. Relay muss an sein. Helfer für alle 6 in test_commands |
| 4.5 | Re-Cal speichern | **Alias** `hexapod-save-cal` falls vorhanden ([[project_phase11_convenience_aliases]]), sonst `/save_calibration`-Service |
| 4.6 | Pre-Check `pulse_min<zero<max` vor Save | ✅ **Ja** — Sicherheitsnetz gegen rqt-Fehleingabe |
| **K3** | Init-Pose-Wert (Femur) | **→ Stage 0.3 verschoben**: `pulse_us_to_radians(1500)` pro Pin statt hartkodiert −0.611, damit `/joint_states` die wahre Power-On-Pose meldet und Stand-up (0.4) sauber rampt |

---

## 5. Cross-References

- [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §4 (Weg-A-Begründung)
- [`servo_real_cal_stage_f_urdf_symmetrize_plan.md`](servo_real_cal_stage_f_urdf_symmetrize_plan.md) — Symmetrie-Pattern (jetzt bewusst aufgebrochen)
- `servo_mapping.yaml`, `hexapod_physical_properties.xacro`, `config.py`, `leg_ik.py`
- Memory: [[project_phase13_femur_zero_asymmetry]] (Asymmetrie jetzt gewollt),
  [[project_phase11_convenience_aliases]], [[feedback_validate_hardware_hypothesis_via_code]]
