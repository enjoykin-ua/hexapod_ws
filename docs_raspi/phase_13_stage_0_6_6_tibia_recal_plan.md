# Phase 13 Stage 0.6.6 — Tibia-Re-Cal (Cal-only, Weg A)

> **Übergeordnet:** [`phase_13_stage_0_tibia_angle_offset_plan.md`](phase_13_stage_0_tibia_angle_offset_plan.md)
> (Befund + §9 Messung). **Vorbedingung:** 0.6.5-Messung ✅ (alle 6 A/B/C/D,
> 2026-06-01). **Decision:** Cal-only (DL-9), kein Remount.
> **Test-Anleitung:** `phase_13_stage_0_6_6_tibia_recal_test_commands.md` (just-in-time nach Code).
> **Status:** ✅ FERTIG (2026-06-01). Code + Build/435 Tests/Envelope grün; Live
> validiert (rad=0 gerade, +0.758→~43° statt 75°, Aufstehen am Boden stabil, Strom
> weit unter Limit). Offene Punkte = Tuning (Stand-Pose/Gait) → Next-Steps-Planung.
> Final-Review: `phase_13_stage_0_progress.md` Sub-Stage 0.6.6.

**Ziel:** Die 6 Tibia-Pins auf die **gemessene echte Gerade** (`pulse_zero = A`)
mit **durchgehender Slope (~425 µs/rad)** re-kalibrieren und die Tibia-Limits auf
die reale Mechanik setzen. Behebt den **~33° Beuge-Über-Knick** der alten Cal
(Beuge-Slope ~700 statt 425 → Stand-Pose physisch 69–78° statt 43°). IK/FK-Formel,
`_L_TIBIA=0.200`, FW **unangetastet** (Weg A). Plus power_on_mid-Nachzug.

---

## 1. Logik-Skizze

### 1.1 Cal-Schema (pro Bein)
- **`pulse_zero` = A** (gemessen, echte Gerade).
- **Slope = global `k = 425` µs/rad** (Servo-Eigenschaft — siehe §1.2).
- **Limits global asymmetrisch:** `joint_upper = +1.30` (Beuge), `joint_lower = −1.00`
  (Streck). Begründung: die Tibia ist ein **einseitiges Knie** (Streck über gerade
  hinaus wird nie kommandiert) → Beuge generös (Demand +0.88 + Marge), Streck nur
  so weit dass es **innerhalb** aller mech. Streck-Stops bleibt.
- **`pulse_min`/`pulse_max` = `pulse_zero ∓ k·limit`** (Vorzeichen nach `direction`),
  sodass die Slope auf **beiden** Seiten 425 ist (kein Skalensprung am Nullpunkt
  wie in der alten Cal).

**Neue `servo_mapping.yaml`-Tibia-Werte:**

| Pin | Bein | pulse_min | pulse_zero | pulse_max | dir | 1500∈range | Streck-Stop-Marge |
|---|---|---|---|---|---|---|---|
| 2  | leg_1 | 1158 | **1710** | 2135 | −1 | ✓ | +24 µs |
| 5  | leg_2 | 1168 | **1720** | 2145 | −1 | ✓ | +55 µs |
| 8  | leg_3 | 1058 | **1610** | 2035 | −1 | ✓ | +85 µs |
| 11 | leg_4 |  893 | **1318** | 1870 | +1 | ✓ | +78 µs |
| 14 | leg_5 |  991 | **1416** | 1968 | +1 | ✓ | +106 µs |
| 17 | leg_6 |  926 | **1351** | 1904 | +1 | ✓ | +76 µs |

(Streck-Stop-Marge = Abstand `pulse_max`/`pulse_min` zum gemessenen mech. Streck-
Anschlag C; >0 = Limit liegt **vor** dem Stop, kein Stall. leg_1 mit +24 µs am
knappsten → §4.2.)

### 1.2 Warum globales k statt per-Bein
Gemessenes k: rechts 423–451 (Schnitt 436 ≈ Servo-Spec 424), **links 378–412**
(systematisch tief, weil „90° zu Boden" links unter-gedreht wurde, leg_6 −10°).
Da **alle Tibias derselbe Servo** (Miuzei MS61) sind, ist k eine Servo-Konstante;
die per-Bein-Streuung = B-Peilungs-Rauschen. **Cross-Check:** mit globalem k=425
werden die Streck-Stop-Winkel links/rechts deckungsgleich (~61–72°); mit per-Seite-k
driften sie auseinander → global 425 ist physikalisch korrekt. `pulse_zero = A` und
der Streck-Stop `C` (harter mech. Anschlag) bleiben per-Bein, **B fällt raus**.

### 1.3 Betroffene Dateien
| Datei | Änderung |
|---|---|
| `src/hexapod_hardware/config/servo_mapping.yaml` | 6 Tibia-Pins: `pulse_min/zero/max` → Tabelle §1.1. **Claude schreibt direkt** (kein `/save_calibration`). |
| `src/hexapod_description/urdf/hexapod.urdf.xacro` | 6× `tibia_lower="-1.00" tibia_upper="1.30"` (per-Bein-Override). |
| `src/hexapod_description/urdf/hexapod.ros2_control.xacro` | 6× Tibia `lower="-1.00" upper="1.30"` **+** `initial=` (neue power_on_mid-rad §1.4). |
| `src/hexapod_kinematics/hexapod_kinematics/config.py` | `_TIBIA_LIMITS = (-1.00, 1.30)`. |
| `src/hexapod_gait/test/test_startup_ramp.py` | `_POWER_ON_MID` Tibia-Werte → §1.4. |
| `src/hexapod_gait/test/test_cartesian_standup.py` | `_POWER_ON_MID` Tibia-Werte → §1.4. |
| `tools/standup_envelope_check.py` | `_POWER_ON_MID` Tibia-Werte → §1.4. |
| **NICHT geändert** | `leg_ik.py` (IK/FK-Formel), `_L_TIBIA=0.200`, FW/Servo2040, Coxa/Femur-Cal. |

### 1.4 Neue power_on_mid (1500 µs) Tibia-rad — Nachzug
Mit neuem `pulse_zero`/k ist 1500 µs eine andere rad-Stellung (Tibia stärker
gebeugt als vorher). Diese Werte ersetzen die alten in Sim-`initial_value` + Fixtures + Tool:

| Bein | neu rad | (alt) | neu ° |
|---|---|---|---|
| leg_1 | +0.494 | (+0.258) | +28.3 |
| leg_2 | +0.518 | (+0.255) | +29.7 |
| leg_3 | +0.259 | (+0.168) | +14.8 |
| leg_4 | +0.428 | (+0.255) | +24.5 |
| leg_5 | +0.198 | (+0.156) | +11.3 |
| leg_6 | +0.351 | (+0.224) | +20.1 |

Alle ∈ neuem Limit [−1.00, +1.30] und 1500 µs ∈ [pulse_min, pulse_max] → kein
Spawn-Clamp / Init-Freeze. Stand-Pose (+0.758) → Pulse 1288–1738, alle in-range ✓.

### 1.5 Validierungs-Prinzip (visuell, HW)
Da `pulse_zero = A` ein ~±4°-Peilungs-Rauschen hat: nach der Re-Cal pro Bein
**rad=0 → Bein sichtbar gerade** (Knie→Fuß auf Femur-Verlängerung) prüfen; weicht
ein Bein sichtbar ab → `pulse_zero` final ±wenige µs nachtrimmen (in rqt, dann in
die yaml). Plus eine **bekannte Beugung** (rad=+0.758) → Tibia ~43°, Fuß plausibel.

---

## 2. Tests-Liste mit Begründung

### 2.1 Statisch (CI / colcon)
| Test | Prüft | Warum |
|---|---|---|
| `xacro`-Parse + `colcon build` (description/kinematics/hardware) | neue Limits + initial_value parsen | Grundlage |
| `colcon test hexapod_hardware` | calibration Roundtrip `rad→pulse→rad` mit neuen Werten + `pulse_min<zero<max`-Guard | Cal-Konsistenz; **gleiche Slope beidseitig** → Roundtrip exakt |
| `colcon test hexapod_kinematics` | IK-Tests grün; Tibia-Limit-bezogene Erwartungen auf (−1.00, 1.30) angepasst | Limit-Änderung |
| `colcon test hexapod_gait` | `_POWER_ON_MID`-Fixtures aktualisiert; Stand-Pose + Ramp in-limits mit **neuen** Limits | Fixture-Realität + Limit-Regression |
| `tools/standup_envelope_check.py` | GRÜN mit neuem `_POWER_ON_MID` + Limits | rechnerische Aufsteh-Hülle |

### 2.2 Live (HW aufgebockt → Boden) — `_test_commands.md` just-in-time
| Test | Prüft |
|---|---|
| rad=0 → alle 6 Tibias **visuell gerade**, HW=RViz (§1.5) | Weg-A-Vertrag, pulse_zero korrekt |
| rad=+0.758 → Tibia ~43°, Fuß-Pos plausibel, HW=RViz | Slope korrekt (alt: kam 75°) |
| power_on_mid (1500) → Tibia ~0.2–0.52 rad, kein OoR-Freeze | Init in-range |
| Sweep [−1.00, +1.30] → kein Stall/Freeze | Limits sicher |
| **Re-Standup** Sim → HW aufgebockt → Boden + **Strom** | Schürfen weg, Strom nahe Stand-Niveau (DK) |
| Laufen-Re-Check (aufgebockt, cmd_vel) | Geometrie-Korrektur verschlechtert Laufen nicht |

### 2.3 Bewusst NICHT in 0.6.6 (Scope-out)
- **Walking-Preset-Re-Tuning** → separat nach dem Laufen-Re-Check (§4.6).
- **Kartesisches Aufstehen 0.7 finalisieren** → 0.7 (diese Korrektur ist dessen Vorbedingung; 0.7 läuft danach mit korrigierter Geometrie weiter).
- **Boden-Strom-Done-Kriterium** → gehört formal zu 0.7/0.8; hier nur Plausibilität.

---

## 3. Progress-Checkliste (→ `phase_13_stage_0_progress.md`, 0.6.6.x)
```
### Sub-Stage 0.6.6 — Tibia-Re-Cal (Cal-only, Weg A)
- [ ] 0.6.6.1  servo_mapping.yaml 6 Tibia-Pins (pulse_min/zero/max §1.1), pulse_min<zero<max ok
- [ ] 0.6.6.2  hexapod.urdf.xacro 6× Tibia-Limit -1.00/1.30 (per-Bein-Override)
- [ ] 0.6.6.3  hexapod.ros2_control.xacro 6× Tibia-Limit + initial (power_on_mid §1.4)
- [ ] 0.6.6.4  config.py _TIBIA_LIMITS = (-1.00, 1.30)
- [ ] 0.6.6.5  test_startup_ramp.py + test_cartesian_standup.py _POWER_ON_MID Tibia nachgezogen
- [ ] 0.6.6.6  tools/standup_envelope_check.py _POWER_ON_MID nachgezogen
- [ ] 0.6.6.7  colcon build (description/kinematics/hardware) grün
- [ ] 0.6.6.8  colcon test hardware + kinematics + gait grün; standup_envelope_check grün
- [ ] 0.6.6.9  generierte URDF verifiziert (alle 6 Tibia lower=-1.00 upper=1.30) — Femur-R3-Lektion
- [ ] 0.6.6.10 Live: rad=0 → alle 6 gerade (HW=RViz), ggf. pulse_zero-Feintuning
- [ ] 0.6.6.11 Live: rad=+0.758 → ~43°, Sweep ohne Freeze, power_on_mid ok
- [ ] 0.6.6.12 Live: Re-Standup Sim→HW→Boden, Schürfen weg, Strom geprüft
- [ ] 0.6.6.13 Laufen-Re-Check aufgebockt
- [ ] 0.6.6.14 Self-Review-Tabelle + Design-Log DL-10, Fixe erledigt
```

---

## 4. Offene Punkte für User-Review (vor Code-Beginn)
| # | Frage | Entscheidung (User 2026-06-01) |
|---|---|---|
| 4.1 | **Beuge-Limit `joint_upper`** = +1.30 (74°)? Demand +0.88 (50°); mech. Stop ≥162°. | ✅ **+1.30** (komfortable Marge, body-safe; später hochziehbar falls eine Gait mehr braucht + kollisionsfrei verifiziert). |
| 4.2 | **Streck-Limit `joint_lower`** = −1.00? leg_1 nur +24 µs Marge zum mech. Stop. | ✅ **−1.00** (Streck wird nie kommandiert, +24 µs reicht). |
| 4.3 | Limits **global** oder **per-Bein**? | ✅ **Global** (alle 6 gleich; Streck ungenutzt, Beuge-Reserve überall riesig). |
| 4.4 | **Symmetrisch** (±1.00) **oder asymmetrisch** (−1.00/+1.30)? | ✅ **Asymmetrisch** — einseitiges Knie; symmetrisch verschenkt Beuge (nur +7° über Demand). Links/Rechts bleibt symmetrisch. Analog Femur **DL-5**. |
| 4.5 | **k = 425** exakt, oder feintunen? | ✅ **425** (Servo-Spec + rechte Beine); ±4° pulse_zero-Rest visuell nachjustierbar (§1.5). |
| 4.6 | **Walking-Presets** re-tunen? | ⏳ **nach** dem Laufen-Re-Check (2.2) entscheiden; ggf. eigene Mini-Stage. |

---

## 5. Cross-References
- Befund + Messung: [`phase_13_stage_0_tibia_angle_offset_plan.md`](phase_13_stage_0_tibia_angle_offset_plan.md) §9 ·
  [`phase_13_stage_0_6_5_tibia_measure_test_commands.md`](phase_13_stage_0_6_5_tibia_measure_test_commands.md) §2
- Präzedenz Weg A + asymmetrische Limits: [`phase_13_stage_0_2_remount_recal_plan.md`](phase_13_stage_0_2_remount_recal_plan.md), Design-Log DL-1/DL-5
- Auslöser (0.7-Schürfen): Memory `project_phase13_standup_foot_scrape`, [`phase_13_stage_0_7_cartesian_standup_plan.md`](phase_13_stage_0_7_cartesian_standup_plan.md)
- Limit-Quellen-Falle: Memory `project_two_joint_limit_sources` (URDF vs config.py — beide auf −1.00/1.30 ziehen)
- Cal-Formel: `src/hexapod_hardware/src/calibration.cpp` (`radians_to_pulse_us`, zwei Slopes treffen bei pulse_zero)
