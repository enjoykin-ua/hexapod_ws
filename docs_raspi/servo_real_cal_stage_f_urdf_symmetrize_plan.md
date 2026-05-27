# Stage F (URDF rad-Limits symmetrieren) — Plan

> **Status:** Cross-Phase-Thread `servo_real_cal` — Folge-Stage nach
> Stage E2 ✅ 2026-05-25. **Ersetzt** den ursprünglichen Wasserwaage-
> Ansatz (siehe [`_archive_servo_real_cal_stage_f_femur_wasserwaage_plan.md`](_archive_servo_real_cal_stage_f_femur_wasserwaage_plan.md)).
>
> **Operative Anleitung:** [`servo_real_cal_stage_f_urdf_symmetrize_test_commands.md`](servo_real_cal_stage_f_urdf_symmetrize_test_commands.md).
>
> **Übergeordneter Plan:** [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md).

---

## 1. Ziel

Die in Stage E2.3 entdeckte **visuelle Asymmetrie** rechts/links während
gait_node-Stand-Pose und Walking eliminieren durch **Symmetrisierung
der URDF rad-Limits** auf gemeinsame Werte für alle 6 Beine.

Erwartung nach Stage F:
- gait_node-Stand-Pose visuell symmetrisch rechts/links
- Walking aufgebockt 0.02/0.03/0.035 m/s weiterhin sauber
- Femur + Tibia + Coxa-rad-Limits **identisch** für alle 6 Beine
- Plugin-Code **unverändert** (keine C++ Änderungen)
- `servo_mapping.yaml` **unverändert** (keine pulse_zero-Änderungen)

## 2. Wurzel des Problems (kurzfassung)

Aus Stage D (`hexapod.urdf.xacro` + `hexapod.ros2_control.xacro`) wurden
per-Bein-asymmetrische rad-Limits eingetragen, basierend auf den
Stage-B-Cal-Werten:

| Bein | tibia_lower | tibia_upper |
|---|---|---|
| leg_1 (rechts) | -1.920 | +1.197 |
| leg_4 (links)  | -1.197 | +1.943 |

(volle Tabelle aller 3 Joint-Typen × 6 Beine: siehe §3)

Die rechte und linke Seite sind **mirror-shifted**, weil pulse_zero
innerhalb des mechanischen pulse-Range auf den beiden Seiten
mirror-shifted sitzt (Konsequenz aus mirror-mounted Servos).

**Konsequenz:** Plugin-Slope-Formel
`slope = (pulse_extreme - pulse_zero) / joint_upper` produziert
unterschiedliche µs/rad-Skalen pro Bein. Bei IK-Stand-Pose
`theta_tibia = +0.823 rad`:

| Bein | physisch |
|---|---|
| leg_1 (rechts, joint_upper=1.197) | **-75.2°** |
| leg_4 (links, joint_upper=1.943)  | **+46.9°** |
| Magnitude-Differenz | **~28°** |

Dieser ~28°-Unterschied ist die sichtbare Asymmetrie.

## 3. Logik-Skizze

### 3.1 Strict-symmetric Werte (alle 6 Beine identisch)

Für jeden Joint-Typ wird der **kleinste gemeinsame magnitude-Wert**
gewählt, dann symmetrisch um 0 angewendet:

| Joint-Typ | Aktuell (per Bein) | Neu (alle 6 identisch) | Begründung |
|---|---|---|---|
| **Coxa** | lower: -0.474 bis -0.758; upper: +0.415 bis +0.806 | **lower = -0.415; upper = +0.415** | min(min(|lower|), min(upper)) = 0.415 (leg_2 upper) |
| **Femur** | lower: -1.529 bis -1.659; upper: +1.493 bis +1.564 | **lower = -1.493; upper = +1.493** | min(min(|lower|), min(upper)) = 1.493 (leg_4 + leg_6 upper) |
| **Tibia** | lower: -1.161 bis -1.967; upper: +1.185 bis +1.967 | **lower = -1.161; upper = +1.161** | min(min(|lower|), min(upper)) = 1.161 (leg_6 lower) |

### 3.2 Warum strict-symmetric

| Variante | Pro | Contra |
|---|---|---|
| **A) Strict-symmetric** (gewählt) | Plugin-Slope_pos = Slope_neg pro Joint; einfaches Mental-Modell; saubere Symmetrie | Etwas mehr rad-Range Verlust (auf "engster der engen Seite") |
| **B) Smallest-common-asymmetric** (z.B. tibia [-1.161, +1.185]) | Etwas mehr nutzbarer rad-Range | Slope_pos ≠ Slope_neg pro Joint; bleibt minimal asymmetrisch |
| **C) User's Vorschlag ±1.197 / ±1.20** | Pragmatisch, runde Werte | leg_6 tibia_lower mechanisch nur -1.161, ±1.197 würde knapp am Anschlag sein |

→ **Variante A gewählt** — Robustheit > 0.04 rad Range.

### 3.3 Auswirkung auf IK + Walking

**Probe-Rechnung für Stand-Pose nach Symmetrisierung:**

| Bein | direction | slope (rad>0) | pulse-Δ bei rad=0.823 | physisch |
|---|---|---|---|---|
| leg_1 (rechts) | -1 | (1680-870)/1.161 = 697.7 | -574 µs | **-77.5°** |
| leg_4 (links)  | +1 | (2140-1320)/1.161 = 706.3 | +581 µs | **+78.4°** |

**Magnitude-Differenz: ~0.9°** — praktisch eliminiert.

### 3.4 Was sich NICHT ändert

- `pulse_min`/`pulse_zero`/`pulse_max` in `servo_mapping.yaml`
- Plugin-Code (`calibration.cpp` Slope-Formel)
- Stage C direction-map (`direction: ±1` Werte)
- IK-Code in `hexapod_kinematics/leg_ik.py`
- gait_node Code

### 3.5 Was sich ändert

- `src/hexapod_description/urdf/hexapod.urdf.xacro` — alle 6
  `<xacro:leg ...>`-Aufrufe bekommen identische rad-Limit-Args
- `src/hexapod_description/urdf/hexapod.ros2_control.xacro` — alle 18
  `<xacro:joint_iface ...>`-Aufrufe bekommen identische lower/upper

### 3.6 Erwarteter Aufwand

- URDF-Patch: ~10 min (zwei xacro-Files editieren)
- Build + Source: ~30 s
- Live-Test aufgebockt: ~10 min
- (Optional) `sim_walk.yaml` regenerieren via `walking_envelope_check.py
  recommend` (sollte sich nur minimal ändern, da IK-Output für aktuelle
  Stand-Pose weit innerhalb der neuen Limits liegt)

**Gesamt:** ~30-45 min, deutlich schneller als der Wasserwaage-Ansatz.

## 4. Tests-Liste mit Begründung

### 4.1 Pflicht-Tests

| # | Test | Begründung |
|---|---|---|
| T1 | `colcon build --packages-select hexapod_description` grün | Sanity dass URDF + xacro parsen |
| T2 | `xacro hexapod.urdf.xacro` produziert valides URDF mit 18 `<limit>`-Tags | Sanity dass URDF-Struktur stimmt |
| T3 | Plugin-Aktivierung ohne `safety_freeze`-Trigger | Sanity dass URDF-Limits-Parse im Plugin nicht kollidiert mit pulse_min/max |
| T4 | gait_node-Init `Stage 0.6: parsed joint limits for 6 legs` Log + `defaults=(linear_x=0.000, ...)` | Sanity dass gait_node URDF-Limits sieht |
| T5 | gait_node-Stand-Pose visuell **symmetrisch** rechts/links | Direkt-Verifikation des Stage F Ziels |
| T6 | Walking 0.02 m/s aufgebockt — 30 s sauber, kein IKError | Symmetrisches Walking bestätigt |
| T7 | Walking 0.03 + 0.035 m/s — wie Stage E2.5 sauber | Tempo-Treppe verifiziert |
| T8 | `sim_walk.yaml` Pre-Stage-F-Werte funktionieren weiterhin | Backward-Compat — Stand-Pose-Foot bleibt innerhalb neuer Limits |

### 4.2 Optionale Tests

| # | Test | Wenn ja |
|---|---|---|
| T9 | `walking_envelope_check.py recommend` mit neuer URDF — gleiche oder leicht andere Werte? | Bestätigt dass Envelope nicht dramatisch geschrumpft |
| T10 | RViz parallel zu HW — visueller Cross-Check | Plus an Sicherheit |

### 4.3 Bewusst NICHT getestet

- **Mechanische rad-Limit-Endanschläge:** wir gehen nicht bis zum
  Anschlag in dieser Stage. URDF-Limits sind innerhalb der mech-
  Anschläge gewählt; safety_freeze ist Backup.
- **Boden-Walking:** kommt erst in späterer Phase
- **Coxa-Range bei großem Tripod-Swing:** für aktuelles step_length_max
  = 0.035 m ist Coxa-Swing ≪ 0.4 rad, also unkritisch

## 5. Progress-Checkliste

Wird ins `phase_<n>_progress`-Stil ans Plan-File angehängt nach Live-
Ausführung:

- [ ] F.1 `hexapod.urdf.xacro` — alle 6 leg-Calls auf identische
      symmetrische Werte umgestellt (coxa ±0.415 / femur ±1.493 / tibia ±1.161)
- [ ] F.2 `hexapod.ros2_control.xacro` — alle 18 joint_iface auf
      identische symmetrische Werte umgestellt
- [ ] F.3 `colcon build --packages-select hexapod_description` grün
- [ ] F.4 `xacro`-Parse-Test grün (18 `<limit>`-Tags)
- [ ] F.5 Plugin-Start ohne safety_freeze
- [ ] F.6 gait_node-Init mit korrektem `parsed joint limits`-Log
- [ ] F.7 Stand-Pose visuell symmetrisch (vor/nach-Vergleich, ggf. Foto)
- [ ] F.8 Walking 0.02 m/s — 30 s sauber
- [ ] F.9 Walking 0.03 m/s — 30 s sauber
- [ ] F.10 Walking 0.035 m/s — 30 s sauber
- [ ] F.11 0.04 m/s Clamp-WARN sichtbar (wie Stage E2.5 Edge-Test)
- [ ] F.12 (Optional) `sim_walk.yaml` regeneriert mit
      `walking_envelope_check.py recommend`
- [ ] F.13 Self-Review-Tabelle in diesem Plan ausgefüllt
- [ ] F.14 Memory `project_phase13_femur_zero_asymmetry.md` updaten
      (ERLEDIGT durch URDF-Symmetrisierung — Femur-pulse_zero war nicht
      die Quelle)
- [ ] F.15 Memory `project_servo_real_cal_done.md` ergänzen: "Stage F
      via URDF-Symmetrisierung 2026-05-25"
- [ ] F.16 `servo_real_cal_plan.md` Status-Tabelle: Stage F ✅
- [ ] F.17 `phase_13_desktop_pre_bringup_plan.md` §2 Stage-Übersicht
      updaten: Stage F neuer Inhalt
- [ ] F.18 `PHASE.md` Cross-Phase-Thread-Eintrag aktualisieren

## 6. Offene Punkte für User-Review

| # | Frage | Vorschlag |
|---|---|---|
| F-Q1 | Strict-symmetric (`A`) vs. Smallest-common-asymmetric (`B`) vs. User's pragmatisch ±1.20 (`C`)? | **A** — robusteste, saubere Symmetrie. Aufwand-Differenz zu B/C minimal |
| F-Q2 | `sim_walk.yaml` regenerieren JETZT (Stage F.12) oder später vor Stage A? | **Stage F.12 als optional**; sollte unverändert funktionieren, Regenerate ist nice-to-have. Sicher in Stage A (LUT-Generator) wo eh frisch generiert wird |
| F-Q3 | Coxa-Symmetrisierung in dieser Stage mitnehmen oder separat? | **Mitnehmen** — selber URDF-Patch, kein Aufwand-Unterschied, Symmetrie für komplette Pipeline |
| F-Q4 | Wir ändern auch Phase-11-Workshop-Doku-Compat (gait_node-Limits-Visualisation)? | **NEIN** — Doku zeigt rad-Limits, die jetzt nur noch identisch sind statt asymmetrisch. Workshop bleibt funktional |
| F-Q5 | URDF-Refactor (Properties statt per-Bein-Args) hier mitnehmen? | **NEIN** — Out-of-Scope. Aktuelle Struktur mit per-Bein-Args bleibt, nur Werte werden identisch. Refactor wäre eigene Stage (z.B. nach Phase 13) |

## 7. Risiken & Mitigations

| # | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | URDF-Joint-Limit-Validation in Plugin schlägt fehl wenn neuer joint_lower bzw. joint_upper außerhalb [pulse_min, pulse_max]/(µs/rad)-Range | gering | Stage 0.5 würde safety_freeze triggern. Pre-Check: math verifiziert dass pulse_zero ± joint_extreme × slope-µs/rad innerhalb [pulse_min, pulse_max]. Bei strict-symmetric 0.415/1.493/1.161 ist das immer der Fall. |
| R2 | `sim_walk.yaml` Stand-Pose-Foot landet plötzlich außerhalb neuer Limits → IKError | gering | Aktueller Stand-Pose: tibia=0.823 rad, femur=-0.33 rad, coxa=0 rad. Alle weit innerhalb der neuen ±-Werte (0.823 < 1.161). |
| R3 | Walking-Tempo-Treppe (0.03 / 0.035) bringt jetzt IKError wo vorher nicht (weil IK-Output knapp an alter, weiterer Limit-Seite war) | gering | Stage E2.5 zeigt 0.035 m/s sauber. IK-Output für leichten Tripod-Swing ist coxa ±~0.15 / tibia ±0.5 — weit innerhalb. |
| R4 | Stand-Pose visuell asymmetrisch bleibt (Restproblem) | gering | Berechnung zeigt <1° Differenz nach Symmetrisierung. Falls trotzdem sichtbar: Re-Cal pulse_zero pro Servo nötig (= alter Wasserwaage-Ansatz dann erst). |

## 8. Self-Review (nach Live-Ausführung 2026-05-25)

| Punkt | Status | Detail |
|---|---|---|
| F-T1: colcon build grün | ✅ | `colcon build --packages-select hexapod_description` ohne Fehler |
| F-T2: xacro produziert 18 limit-Tags, 3 unique Werte | ✅ | 18 `<limit>`-Tags bestätigt; 3 unique pro Joint-Typ (false-positive war ein Kommentar mit "<limit>" im Text) |
| F-T3: Plugin-Start kein safety_freeze | ✅ | `real.launch.py` startet sauber, 6× `Configured and activated leg_<n>_controller`, kein freeze-Trigger |
| F-T4: gait_node-Init Logs ok | ✅ | `Stage 0.6: parsed joint limits for 6 legs`, `linear_max=0.035 m/s` |
| F-T5: Stand-Pose visuell symmetrisch | ✅ | **Hauptpunkt erreicht** — alle 6 Beine symmetrisch rechts/links nach gait_node-Stand-Pose. User-Bestätigung: "Beine sehen symmetrisch aus!" |
| F-T6: Walking 0.02 m/s sauber | ✅ | 30 s ohne IKError oder safety_freeze |
| F-T7: Walking 0.03 + 0.035 m/s sauber | ✅ | beide Tempos 30 s sauber |
| F-T8 (Bonus): Walking 0.04 m/s Clamp-WARN korrekt | ✅ | gait_node loggt `cmd_vel clamped: input vx=0.040 > max-leg-speed 0.035 m/s` wie erwartet |
| F-T9 (Bonus): `walking_envelope_check.py recommend` post-symmetrize | ✅ | Bottleneck wechselt von `sidestep:out_of_reach` zu `sidestep:joint_limit`; step_length_max 0.035 → 0.032 (-8.6%); sim_walk.yaml NICHT überschrieben (Stage A wird LUT mit recommend-multi generieren) |
| F-T10 (Bonus): Coxa-Drehtest mit `angular.z=0.3` | ✅ | User-Verständnis: Coxa-Schwung bei Forward-Walking inhärent klein (~5-7° p2p), bei Yaw-Rotation deutlich sichtbar. Kein Cal-Issue, sondern Tripod-Geometrie |
| Restprobleme (pulse_zero-Re-Cal nötig?) | ✅ keine | Femur-Symmetrie war NICHT durch pulse_zero-Drift verursacht. Wasserwaage-Ansatz war nicht nötig. |

## 8b. Lessons Learned — was lief schief und wie haben wir's gelöst

### Was schief lief

**Initial-Hypothese war falsch.** Erste Stage F (`_archive_servo_real_cal_stage_f_femur_wasserwaage_*`) basierte auf der Annahme: visuelle Femur-Asymmetrie rechts/links aus Stage E2.3 → kommt von Cal-Drift im `pulse_zero` → Lösung = Wasserwaage am Femur + pulse_zero manuell trimmen. Dafür wurden Plan-Doku + Test-Commands geschrieben (~700 Zeilen).

**Wäre Wasserwaage live ausgeführt worden, hätte das nichts gebracht:**
- Manual rad=0 für jeden Femur war bereits symmetrisch
- Asymmetrie zeigt sich nur bei **non-zero rad** (IK-Stand-Pose, Walking)
- pulse_zero-Trim hätte das non-zero-Verhalten **nicht** verändert (siehe Slope-Formel-Mathe in §3.3)

### Wie wir's gelöst haben

**User-Skepsis als Trigger:** vor Live-Ausführung hat der User die Hypothese hinterfragt — *"anfahren tut es glaube ich gut wenn man einzeln anfährt aber beim gehen ist asymm"*. Diese Beobachtung war der Schlüssel.

**Code-Analyse statt Live-Test:** wir haben:
1. URDF rad-Limits (`hexapod.urdf.xacro` Stage D) inspiziert → asymmetrisch per Bein (Tibia rechts/links spiegel: ±1.197 vs ±1.943)
2. Plugin-Slope-Formel (`calibration.cpp`) analysiert → benutzt `joint_upper`/`joint_lower` als Skalierungsfaktor
3. Konkret durchgerechnet: IK-Stand-Pose-rad=+0.823 (Tibia) → physische Drehung **75° rechts vs 47° links** = **28° Differenz**
4. User-Vorschlag (URDF-rad-Limits symmetrieren) durchgerechnet → Differenz reduziert sich auf <1°

**Konsequenz:** alte Stage F als `_archive_*` archiviert, neue Stage F konzipiert (URDF-Symmetrisierung statt pulse_zero-Trim). Live-Test bestätigte die Math-Analyse vollständig.

### Generalisierbare Lektion

Wenn die initial-vermutete Wurzelursache **rein durch Code/Math-Analyse falsifizierbar** ist, das **vor** dem Live-Test tun. Spart Mech-Aufwand + verhindert dass eine Stage am Ende ohne Wirkung durchgezogen wird. Hardware-Fixe sollten erst nach Code-seitiger Hypothesen-Validierung kommen.

→ Wandert in Memory `feedback_validate_hardware_hypothesis_via_code.md`.

### Bonus-Erkenntnisse aus Live-Test

**Coxa-Bewegung bei Forward-Walking ist inhärent klein.** User fragte warum sich Coxas kaum bewegen. Rechnung: `coxa_angle ≈ atan2(step_length/2, radial_distance) = atan2(0.0175, 0.295) ≈ 3.4°` pro Seite, also ~7° peak-to-peak für Mittel-Beine. Drehung (`angular.z`) ist der visuelle Coxa-Test, nicht Vorwärtslaufen.

**Bottleneck-Wechsel nach Symmetrisierung:** `walking_envelope_check.py recommend` zeigt: vor Symmetrisierung war Bottleneck `sidestep:out_of_reach` (geometrische Reichweite), nach Symmetrisierung `sidestep:joint_limit` (rad-Limit greift). Konsistent mit Theorie — wir haben die rad-Range straffer gemacht.

**Linear_max-Reduktion ~8.6%:** step_length_max 0.035 → 0.032 m. Walking-Range bleibt vollständig nutzbar, nur Maximal-Tempo leicht reduziert. Für aktuelle Sessions nicht relevant (Stage A wird Multi-Slot-LUT eh frisch generieren).

## 9. Was passiert wenn alles grün

- `servo_real_cal_plan.md` Stage F → ✅ 2026-05-25
- Memory `project_phase13_femur_zero_asymmetry.md` als ✅ (Wurzel war
  URDF, nicht pulse_zero)
- Memory `project_servo_real_cal_done.md` ergänzt
- PHASE.md Cross-Phase-Thread-Status: 🟡 für Stage A laufende Pre-Bringup-Stages
- Phase 13 Desktop Stage A (LUT-Infrastruktur) ist der nächste Schritt

## 10. Was passiert wenn Probleme

| Problem | Aktion |
|---|---|
| Build-Error im URDF (xacro-Parse) | xacro-Output prüfen, Tippfehler in den 6 leg-Calls finden |
| Plugin-safety_freeze beim Init | pulse_min/zero/max + neuer joint_lower/upper mathematisch checken: pulse_zero ± joint_extreme × slope-µs/rad muss in [pulse_min, pulse_max] sein |
| Stand-Pose visuell weiterhin asymmetrisch (>5°) | Wasserwaage-Ansatz reaktivieren (alter Stage F → Stage G?) für Femur-pulse_zero-Trim als Folge-Fix |
| IKError bei Stand-Pose nach Symmetrisierung | tibia/femur joint_upper/lower zu eng — Symmetrisierung lockerer wählen (z.B. ±1.18 statt ±1.161) ODER `body_height`/`radial_distance` zurücknehmen |
| Walking-Tempo bricht jetzt früher als 0.035 m/s | gait_node-`step_length_max` reduzieren oder `cycle_time` erhöhen; sim_walk.yaml regenerieren |

---

**Erstellt 2026-05-25 nach Analyse-Ergebnis (URDF-Asymmetrie als Wurzel).
Ersetzt** [`_archive_servo_real_cal_stage_f_femur_wasserwaage_plan.md`](_archive_servo_real_cal_stage_f_femur_wasserwaage_plan.md). **Operative Anleitung in**
[`servo_real_cal_stage_f_urdf_symmetrize_test_commands.md`](servo_real_cal_stage_f_urdf_symmetrize_test_commands.md).
