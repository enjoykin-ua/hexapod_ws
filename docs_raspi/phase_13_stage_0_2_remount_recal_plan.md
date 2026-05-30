# Phase 13 Stage 0.2 — Femur-Mech-Umbau + Re-Cal (Weg A) + Femur-Limits

> **Übergeordnet:** [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §3/§4.
> **Vorbedingung:** Sub-Stage 0.1 ✅ (manuelle Relay-Steuerung
> `/hexapod_relay_set` + FW geflasht).
> **Test-Anleitung:** [`phase_13_stage_0_2_remount_recal_test_commands.md`](phase_13_stage_0_2_remount_recal_test_commands.md).
> **Status:** ⚪ offen, wartet auf Freigabe (2026-05-30).

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

**Alternative (verworfen, als Fallback dokumentiert):** §12-Simpel —
bei `rad=0` (horizontal) abschrauben, Segment per Protraktor 35° hoch drehen,
festziehen. Verworfen weil 35°-Augenmaß ungenauer als Horizontale.

### 1.2 Re-Cal der 6 Femur-Pins (Weg A) — pulse_zero/min/max

Über die Phase-11-Live-Cal (rqt_reconfigure-Sliders + `/save_calibration`):

Pro Femur-Pin (1, 4, 7, 10, 13, 16):
- **`pulse_zero`** = jog bis Femur **visuell horizontal** → notieren.
  (≈ Servo-Mitte + ~35°-wert; für leg_1 illustrativ ~1727 µs statt alt 1460.)
- **`pulse_min`** = jog **nach oben** bis mechanischer Anschlag (Kollision
  mit Body/Coxa) → notieren. (Up-Range ist nach Umbau **kurz**.)
- **`pulse_max`** = jog **nach unten** bis Anschlag/Servo-Limit → notieren.
  (Down-Range ist **lang**.)
- Invariante `pulse_min < pulse_zero < pulse_max` (calibration.cpp erzwingt).

### 1.3 Femur-Joint-Limits herleiten (der kritische Schritt)

**Problem:** Die Calibration ist linear je Segment: `rad=0→pulse_zero`,
`rad=joint_upper→pulse_max`, `rad=joint_lower→pulse_min`. Für korrekte
**Zwischen**-Winkel muss `joint_upper` = der **echte physische Femur-Winkel**
(rad, von horizontal) am Down-Anschlag sein — sonst stimmt die Steigung nicht
und die IK setzt den Fuß falsch.

**Lösung (Steigung erhalten):** Die Servo-Linearität (µs pro rad) ist eine
**Servo-Eigenschaft** und wird vom Umbau **nicht** verändert (der Umbau dreht
nur Segment ↔ Welle). Also:

1. Vor-Umbau-Steigung pro Pin aus altem Cal berechnen:
   - `slope_down = (pulse_max_alt − pulse_zero_alt) / joint_upper_alt`
   - `slope_up   = (pulse_zero_alt − pulse_min_alt) / |joint_lower_alt|`
   - (leg_1: slope_down=(2120−1460)/1.493 ≈ **442 µs/rad**, slope_up=(1460−815)/1.493 ≈ **432 µs/rad**)
2. Neue Limits aus gemessenen neuen Pulse-Extremen + erhaltener Steigung:
   - `joint_upper_neu = (pulse_max_neu − pulse_zero_neu) / slope_down`
   - `joint_lower_neu = (pulse_min_neu − pulse_zero_neu) / slope_up`  (negativ)
3. Diese Limits in `servo_mapping.yaml` (joint_lower/upper pro Pin werden vom
   Plugin aus URDF gesetzt — siehe unten) bzw. URDF + config.py eintragen.

**Selbst-konsistenz-Check:** mit `joint_upper_neu` wird die calibration-Steigung
`(pulse_max_neu − pulse_zero_neu)/joint_upper_neu = slope_down` → exakt die
erhaltene Servo-Steigung. ✓ Damit sind Zwischen-Winkel korrekt **ohne**
Protraktor-Messung.

> **Verifikation (optional, empfohlen):** an 1–2 Beinen den physischen Winkel
> am Down-Anschlag mit Protraktor gegen `joint_upper_neu·(180/π)` prüfen
> (Erwartung: ~±2°). Bestätigt die Linearitäts-Annahme.

### 1.4 Welche Dateien (Weg A)

| Datei | Änderung |
|---|---|
| `src/hexapod_hardware/config/servo_mapping.yaml` | 6 Femur-Pins: `pulse_zero`/`pulse_min`/`pulse_max` neu |
| `src/hexapod_description/urdf/hexapod_physical_properties.xacro` | Femur `joint_lower`/`joint_upper` → neue asymmetrische Werte |
| `src/hexapod_kinematics/hexapod_kinematics/config.py` | `_FEMUR_LIMITS` → identisch zur xacro |
| `src/hexapod_hardware/config/initial_poses.yaml` | Init-Pose Femur-Wert (alt −1.45) → **−0.611** (35° hoch); coxa/tibia bleiben |
| **NICHT geändert** | `leg.xacro` (Femur-Geometrie/origin), `leg_ik.py` (IK/FK-Formel), RViz, Gazebo |

> **Limit-Quelle:** Femur-Limits sind in `hexapod_physical_properties.xacro`
> die Single Source (Convention §11). Das Plugin liest sie aus dem URDF
> (`set_joint_limits`), die IK aus `config.py`. Beide müssen identisch sein.
> Global vs. per-Bein → siehe Offene Punkte 4.3.

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
- [ ] 0.2.2  Re-Cal pulse_zero (=horizontal) für 6 Femur-Pins
- [ ] 0.2.3  Re-Cal pulse_min (oben-Anschlag) + pulse_max (unten) für 6 Pins
- [ ] 0.2.4  servo_mapping.yaml 6 Femur-Einträge aktualisiert + pulse_min<zero<max ok
- [ ] 0.2.5  Femur joint_lower/upper hergeleitet (Steigung erhalten) — pro Pin notiert
- [ ] 0.2.6  Entscheidung global vs per-Bein-Limits (Offene Punkte 4.3)
- [ ] 0.2.7  hexapod_physical_properties.xacro Femur-Limits aktualisiert
- [ ] 0.2.8  config.py _FEMUR_LIMITS identisch zur xacro
- [ ] 0.2.9  initial_poses.yaml Femur → -0.611
- [ ] 0.2.10 colcon build (description/kinematics/hardware) grün
- [ ] 0.2.11 colcon test kinematics + hardware grün (IK-Regression)
- [ ] 0.2.12 Live: rad=0 → horizontal (HW + RViz identisch)
- [ ] 0.2.13 Live: rad=-0.611 → 35° hoch (HW + RViz identisch, ≈ Servo-Mitte)
- [ ] 0.2.14 Live: rad-Sweep über Limits → kein OoR-Freeze, kein Stall
- [ ] 0.2.15 Live: Power-On via Relay → Femurs ~35° hoch, kein Horizontal-Sprung
- [ ] 0.2.16 Self-Review-Tabelle, Fixe erledigt
```

---

## 4. Offene Punkte für User-Review (vor Code/Umbau-Beginn)

| # | Frage | Vorschlag |
|---|---|---|
| 4.1 | Umbau-Methode: §6-Servo-Trick (mount horizontal, Servo definiert 35°) vs §12-Simpel (35° per Auge) | **§6-Trick** — horizontale Referenz genauer als 35°-Augenmaß |
| 4.2 | Limit-Herleitung: Steigung-erhalten (§1.3, ohne Protraktor) vs. physische Winkelmessung | **Steigung-erhalten** + optionale Protraktor-Stichprobe an 1–2 Beinen |
| 4.3 | Femur-Limits **global** (alle 6 gleich, konservativstes Min) oder **per-Bein** (echte Range je Bein) | **Erst messen, dann entscheiden.** Wenn die 6 Werte eng beieinander liegen → global (min nehmen, Symmetrie-Stil); wenn stark streuend → per-Bein. Datengetrieben nach 0.2.5 |
| 4.4 | Wie Femurs live auf rad=+0.611 / rad=0 halten beim Umbau? | Über bestehende Joint-Command-Kette (forward-controller / joint_value_publisher aus Phase 10/11) — exakte Befehle in test_commands |
| 4.5 | Re-Cal-Speichern via `/save_calibration`-Service oder `hexapod-save-cal`-Alias? | **Alias** falls vorhanden ([[project_phase11_convenience_aliases]]), sonst Service |
| 4.6 | Pre-Check `pulse_min < pulse_zero < pulse_max` vor Save (analog Stage-F R2)? | **Ja** — Sicherheitsnetz gegen rqt-Fehleingabe |

---

## 5. Cross-References

- [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §4 (Weg-A-Begründung)
- [`servo_real_cal_stage_f_urdf_symmetrize_plan.md`](servo_real_cal_stage_f_urdf_symmetrize_plan.md) — Symmetrie-Pattern (jetzt bewusst aufgebrochen)
- `servo_mapping.yaml`, `hexapod_physical_properties.xacro`, `config.py`, `leg_ik.py`
- Memory: [[project_phase13_femur_zero_asymmetry]] (Asymmetrie jetzt gewollt),
  [[project_phase11_convenience_aliases]], [[feedback_validate_hardware_hypothesis_via_code]]
