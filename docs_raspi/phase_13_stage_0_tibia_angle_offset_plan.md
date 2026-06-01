# Phase 13 Stage 0 — Tibia-Winkel-Offset-Korrektur (Geometrie/Cal)

> **STATUS: ⚪ PLAN — Befund + Messung stehen, Implementierung offen.**
> Quer-liegende Korrektur (betrifft 0.2/0.3/0.4/0.7 + Laufen). **Pausiert die
> laufende Stage 0.7** (kartesisches Aufstehen) — 0.7 wartet auf die korrigierte
> Geometrie. Erstellt 2026-05-31 als Übergabe an einen frischen Chat.
>
> **⚖️ ERSTE Entscheidung: Remount vs. reine Cal-Korrektur (§1a).** Tendenz nach
> User-Diskussion: **Remount** (mechanisch sauber, symmetrische Limits ohne
> Bewegungsverlust — wie Femur 0.2). Cal-Weg (§2) ist Fallback. Ein Mess-Schritt
> (echter Tibia-Winkelbereich beidseitig ab dem geraden Punkt) entscheidet.
>
> **🔵 ENTSCHEIDUNGEN 2026-06-01 (User):** (1) **Mess-Schritt zuerst** — kein
> HW-Umbau, bis Daten die Cal-vs-Remount-Frage tragen. (2) **Femur-Stil-Messung**
> (zwei optische Referenzen „gerade" + „90°" der virtuellen Knie→Fuß-Linie → Slope
> `k`; **kein Protraktor** — am geknickten Bein nicht sinnvoll messbar). (3) Diese
> Korrektur = **Stage 0.6.5** (zwischen 0.6 und 0.7, Vorbedingung für 0.7-Boden;
> Boden-Test bleibt 0.8). (4) **Branch-Entscheidung** (cal-only vs. remount)
> **vertagt** bis nach der Messung. → Mess-Sub-Stage 0.6.5 in **§9**, Test-Anleitung
> [`phase_13_stage_0_6_5_tibia_measure_test_commands.md`](phase_13_stage_0_6_5_tibia_measure_test_commands.md).

---

## 0. ⭐ FÜR DEN NÄCHSTEN CHAT: Was zuerst lesen + welches Vorwissen

**Du sollst den 23°-Tibia-Offset sauber einbauen.** Lies in dieser Reihenfolge:

### 0.1 Pflicht-Lektüre (Arbeitsweise + Kontext)
1. **`CLAUDE.md`** (Repo-Wurzel) — Arbeitsanweisung. Besonders **§4** (Plan →
   Freigabe → Implementierung → Tests → **kritischer Self-Review**) und **§5**
   (Shell-Verbote). **§9** (HW-Safety, aufgebockt zuerst).
2. **`PHASE.md`** — aktuelle Phase (Phase 13, Stage 0).
3. **`docs/00_conventions.md`** — Joint-Naming, Frames, **§11.4 Joint-Limits**.
4. **DIESE Datei** komplett.

### 0.2 Der Präzedenzfall (entscheidend — gleicher Mechanismus!)
5. **`docs_raspi/phase_13_stage_0_plan.md`** — Stage-0-Vertrag. **Vor allem
   DL-1 (Design-Log): „Weg A" — der Femur-35°-Offset lebt in der KALIBRIERUNG,
   nicht in der URDF-Geometrie.** Der Tibia-Offset wird **genauso** behandelt
   (Cal-Weg). Lies die Begründung von Weg A — sie gilt 1:1 für die Tibia.
6. **`docs_raspi/phase_13_stage_0_2_remount_recal_plan.md`** + dessen
   `_test_commands.md` — die Femur-Re-Cal-Stage. Das **Muster** für rqt-Messung
   + servo_mapping.yaml-Edit + Limit-Validierung, das wir hier wiederholen.
7. **`docs_raspi/phase_13_stage_0_progress.md`** — Design-Log (DL-1…DL-8) +
   Post-Reviews. Hier kommt die neue Korrektur als Eintrag rein.

### 0.3 Was die Korrektur betrifft (Folge-Stages)
8. **`docs_raspi/phase_13_stage_0_3_init_sequence_plan.md`** — power_on_mid
   (1500 µs) Init. **§3.1 hat die 18 rad-Werte, die sich ändern.**
9. **`docs_raspi/phase_13_stage_0_4_standup_plan.md`** — Stand-Pose-Definition.
10. **`docs_raspi/phase_13_stage_0_7_cartesian_standup_plan.md`** +
    **`..._creation_steps_description.md`** — das kartesische Aufstehen, das auf
    die korrigierte Geometrie wartet (Grund dieser Korrektur: Schleifen + Strom).

### 0.4 Code, der gelesen/geändert wird
- **`src/hexapod_hardware/config/servo_mapping.yaml`** — die 6 Tibia-`pulse_zero`
  (das ist der Haupt-Edit). Tibia-Pins: 2/5/8 (leg_1/2/3, dir −1), 11/14/17
  (leg_4/5/6, dir +1).
- **`src/hexapod_hardware/src/calibration.cpp`** — `radians_to_pulse_us` /
  `pulse_us_to_radians` (Zeile ~176-230): die Formel
  `pulse = pulse_zero + direction · rad · slope` mit **asymmetrischen Slopes**
  (zwei Slopes treffen bei pulse_zero; pulse_min/max ↔ ±joint_limit).
- **`src/hexapod_kinematics/hexapod_kinematics/leg_ik.py`** + **`config.py`** —
  IK/FK + `_L_TIBIA=0.200` (bleibt!) + `_TIBIA_LIMITS`.
- **`src/hexapod_description/urdf/hexapod.ros2_control.xacro`** — die 18
  Sim-`initial_value` (power_on_mid) + die Tibia-rad-Limits.
- **`src/hexapod_description/urdf/hexapod_physical_properties.xacro`** /
  `hexapod.urdf.xacro` — per-Bein Tibia-Joint-Limits.
- **`src/hexapod_gait/test/test_startup_ramp.py`** + **`test_cartesian_standup.py`**
  — beide haben `_POWER_ON_MID`-Fixtures (Tibia-Werte ändern sich).
- **`tools/standup_envelope_check.py`** — `_POWER_ON_MID` (nachziehen).

### 0.5 Relevante Memory-Einträge (im MEMORY.md-Index, verlinkte lesen)
- `project_phase13_femur_zero_asymmetry` — der Femur-Weg-A-Präzedenzfall + die
  „echte generierte URDF prüfen, nicht nur die Property"-Lektion.
- `project_two_joint_limit_sources` — ⚠️ **ZWEI** Limit-Quellen (URDF coxa±0.415/
  tibia±1.161 vs config.py ±1.57/±1.50). Bei rad↔pulse + Pose-Validierung IMMER
  die URDF-Limits. Gilt hier voll.
- `feedback_validate_hardware_hypothesis_via_code` — erst per Code/Math
  falsifizieren, dann bauen.
- `project_phase13_standup_foot_scrape` — der Schürf-Befund, der zu dieser
  Korrektur führte.
- `feedback_phase_progress_tracking`, `feedback_interactive_stage_test_doc`,
  `feedback_test_commands_in_doc_not_chat`, `feedback_no_trim_verification_output`,
  `feedback_user_does_commits`, `feedback_german_language`,
  `project_fw_rebuild_before_flash` (falls FW berührt — hier NICHT nötig).

### 0.6 Vorwissen, das du brauchst (Kurzfassung — Details unten in §1–§2)
- Die echte Tibia ist **geknickt** (Servo-Gelenk → 100 mm → 43°-Knick → 115 mm →
  Fuß). Das Modell nimmt **gerade** an. Die **Länge** (Gelenk→Fuß = 200 mm) ist
  **korrekt** (= `_L_TIBIA=0.200`). **Einziger Fehler = ein konstanter
  Winkel-Versatz von 23,2°** zwischen Servo-0rad-Richtung (kurzes Segment) und
  der echten Gelenk→Fuß-Linie.
- **⚖️ ZUERST §1a klären: Remount vs. reine Cal-Korrektur.** Der 23°-Versatz macht
  die Tibia-Bewegungsfreiheit **asymmetrisch** (~80°/27°) → kollidiert mit der
  „strikt symmetrische Limits"-Konvention. **Tendenz: Remount** (wie Femur 0.2,
  symmetrisch ohne Bewegungsverlust); reine Cal-Korrektur (§2) nur als Fallback.
  Ein Mess-Schritt (echter Winkelbereich beidseitig) entscheidet.
- **Cal-Weg (falls kein Remount):** Tibia-`pulse_zero` so verschieben, dass
  „rad = 0" die echte gerade-Pose trifft; IK/FK-Formel bleibt unberührt (Femur-
  Weg-A). ⚠️ asymmetrische Slope beachten (§2.3).
- **Der Init (1500 µs) bleibt physisch unverändert** (FW kommandiert weiter
  1500 µs); bei Remount wird die *Mechanik* versetzt, sodass 1500 µs dann die
  grade Pose ist (wie Femur). Nur die rad-Zahlen werden nachgezogen.
- **Die Re-Validierung ist der eigentliche Aufwand** (§5), nicht der Edit.

---

## 1. Befund + Messung (verifiziert 2026-05-31)

**Das Problem (Symptom):** Beim kartesischen Aufstehen (Stage 0.7) schürfen die
Tibias trotz schürffreier Fuß-Trajektorie leicht am Boden → erhöhter Strom +
PSU-Spannungseinbruch (Stehen kostet ~400 mA, Aufstehen >3,5 A). Ursache ist
**nicht** der Fuß (der bleibt fix), sondern die **Form** des Tibia-Segments.

**Die echte Tibia ist geknickt** (User-Vermessung + Skizze):
- Segment 1 (Gelenk-Drehpunkt → Knick): **100 mm**, zeigt in Servo-0rad-Richtung.
- Knick: **~43°** nach unten (Richtung Boden).
- Segment 2 (Knick → Fuß-Aufsetzpunkt): **115 mm**.
- **Gelenk → Fuß (Luftlinie, die „virtuelle gerade Tibia") = 200 mm.**

**Rechnung** (Kosinussatz, Dreieck a=100, b=115, c=200):
- Hypotenuse c = 200 mm = exakt `_L_TIBIA = 0.200` → **Länge stimmt, kein
  Längen-Fehler.**
- **Winkel-Offset (Segment 1 → Hypotenuse) = 23,17°** = der Winkel, um den die
  echte Gelenk→Fuß-Linie unter der Modell-Annahme (gerade in Servo-0rad-Richtung)
  liegt.
- (Knick-Innenwinkel 136,8° / 43° Abweichung — irrelevant, nur Gelenk+Fuß zählen.)

**Warum Laufen geht, Aufstehen schleift:** Die Länge stimmt → Fuß-Position grob
ok → Laufen toleriert die 23°. Beim Aufstehen liegt die Tibia flach am Boden →
der echte Fuß/das Segment liegt 23° tiefer als das Modell denkt → schleift.

**Cal-Gegenprobe (bestätigt den Befund):** Die User-„Tibia-horizontal"-Pulswerte
(870/860/790/2140/2210/2170) sind exakt die `pulse_min` (leg_1/2/3) bzw.
`pulse_max` (leg_4/5/6) aus servo_mapping.yaml — also die mechanischen Grenzen.

---

## 1a. ⚖️ GRUNDSATZ-ENTSCHEIDUNG ZUERST: Remount vs. reine Cal-Korrektur

> **Diese Entscheidung kommt VOR allem anderen** — sie bestimmt, ob §2 (Cal)
> überhaupt der richtige Weg ist. (Diskussion mit User 2026-05-31.)

Der 23°-Versatz heißt: der echte „gerade" Punkt der Tibia liegt **nicht mittig**
im mechanischen Servo-Bereich → die Bewegungsfreiheit ist **asymmetrisch** (grobe
Schätzung leg_1: ~80° in die eine, ~27° in die andere Richtung).

**Das kollidiert mit der Projekt-Konvention „strikt symmetrische Limits"**
(Stage F / `servo_real_cal`: tibia ±1,161 für alle 6, gegen Links/Rechts-
Asymmetrie). Ohne Remount bleiben nur:
- **(a) symmetrisch begrenzen** → auf den **kleineren** Bereich kappen → viel
  Beuge-Spielraum verschenkt.
- **(b) asymmetrisch begrenzen** → bricht die Konvention, gespiegelte Seiten
  sauber durchziehen, komplexer.

**Option C — Remount (mechanisch, wie Femur 0.2):** Servo-Horn um ~23° versetzt
neu aufsetzen → gerader Punkt wieder **mittig** → **symmetrischer** Bereich →
symmetrische Limits **ohne Bewegungsverlust**, Servo-Mitte (1500 µs) = grade
Bein-Pose. Aufwand: Horn ab + versetzt drauf + Re-Cal (pulse_zero/min/max), wie
Femur Stage 0.2.

**Mess-Schritt, der die Entscheidung trifft (ERSTER Schritt der Stage):**
Per rqt die echte gerade-Pose (grüne Linie gerade) anfahren, dann bis `pulse_min`
und bis `pulse_max` joggen und den **echten Tibia-Winkel in beide Richtungen
messen**. Dann ist schwarz auf weiß: reicht der „kurze" Bereich für Aufstehen +
Laufen (→ Cal genügt) oder nicht (→ Remount).

> **Tendenz nach der Diskussion:** Der Remount ist die saubere Lösung (symmetrisch,
> konsistent mit der Konvention, volle Reserve) — analog zum Femur. Die reine
> Cal-Korrektur (§2) ist der Fallback, falls der Mess-Schritt zeigt, dass die
> Asymmetrie unkritisch ist. **§2 unten beschreibt den Cal-Weg; bei Remount
> kommt zusätzlich der Mech-Schritt + volle Re-Cal dazu (Muster: Stage 0.2).**

## 2. Die Korrektur (Cal-Weg — nur falls §1a „kein Remount" ergibt)

**Prinzip (= Femur-Weg-A / DL-1):** Der 23°-Offset ist die Diskrepanz zwischen
„welcher Puls = rad 0" (Cal) und „was die IK als rad 0 erwartet" (Hypotenuse
gerade in Femur-Verlängerung). Wir verschieben den Tibia-`pulse_zero`, sodass
beide konsistent sind. **Die IK/FK-Formel (`leg_ik.py`) bleibt unangetastet.**

### 2.1 Cal-Formel (calibration.cpp)
```
pulse = pulse_zero + direction · rad · slope
  slope (rad≥0): dir+1 → (pulse_max−pulse_zero)/joint_upper
                 dir−1 → (pulse_zero−pulse_min)/joint_upper
  slope (rad<0): dir+1 → (pulse_zero−pulse_min)/|joint_lower|
                 dir−1 → (pulse_max−pulse_zero)/|joint_lower|
  joint_upper = joint_lower = 1.161 (Tibia-URDF-Limit)
```

### 2.2 Gerechnete Kandidaten für den neuen `pulse_zero`
Offset 23,17° = 0,4044 rad. Der neue pulse_zero ist der Puls, bei dem die echte
grüne Linie (Gelenk→Fuß) gerade in Femur-Verlängerung steht. Zwei Kandidaten je
nach Drehrichtung — **welcher stimmt, ist LIVE per rqt zu verifizieren** (Vorzeichen):

| Bein | Pin | dir | aktuell pulse_zero | Kand A (+off) | **Kand B (−off) ⭐ Vermutung** |
|---|---|---|---|---|---|
| leg_1 | 2  | −1 | 1680 | 1398 | **1856** |
| leg_2 | 5  | −1 | 1680 | 1394 | **1861** |
| leg_3 | 8  | −1 | 1620 | 1331 | **1794** |
| leg_4 | 11 | +1 | 1320 | 1606 | **1144** |
| leg_5 | 14 | +1 | 1390 | 1676 | **1214** |
| leg_6 | 17 | +1 | 1340 | 1629 | **1169** |

**Vermutung Kandidat B:** Die echte Hypotenuse liegt 23° UNTER Segment 1 (Fuß
tiefer = mehr Beugung). Um sie gerade zu bringen, muss die Tibia ~23° aufgerichtet
werden (weniger Beugung) → Kand B. **Aber das Vorzeichen MUSS live geprüft
werden** (rqt: pulse_zero-Kandidat setzen, prüfen ob die grüne Gelenk→Fuß-Linie
bei Femur-horizontal auch horizontal/gerade ist).

### 2.3 ⚠️⚠️ KRITISCH: asymmetrische Slope — reiner pulse_zero-Shift reicht NICHT
Die Cal benutzt **zwei asymmetrische Slopes**, berechnet aus
`(pulse_zero − pulse_min)` und `(pulse_max − pulse_zero)`. **Verschiebt man nur
`pulse_zero`, ändern sich BEIDE Slopes** → die rad↔pulse-Mapping verzerrt sich
über den ganzen Tibia-Bereich, nicht nur am Nullpunkt (Beispiel leg_1: slope rad≥0
698→849, slope rad<0 435→283 µs/rad). Ein physisch *linearer* Servo bräuchte aber
eine ~konstante Slope. **Konsequenz:** Die Kandidaten-Tabelle in §2.2 (reiner
pulse_zero-Shift) ist nur der **Startpunkt** für die Live-Verifikation, **nicht**
die fertige Cal.

**Daher wahrscheinlich nötig: eine saubere Tibia-Re-Kalibrierung** (wie Stage 0.2
Femur), nicht nur ein pulse_zero-Shift:
1. Den echten **rad-0-Puls** finden (grüne Linie gerade, per rqt) → neuer pulse_zero.
2. Die echten **mechanischen Grenzen** (pulse_min/max) bei den **echten ±-Winkeln**
   neu zuordnen — sodass die Slope physikalisch konsistent ist (konstante µs/rad,
   kein Skalen-Sprung am Nullpunkt).
3. URDF-Tibia-Limits (per-Bein-Override!) auf die real erreichbaren Winkel ziehen.

**Verifikation über MEHRERE Posen** (nicht nur Nullpunkt): rad=0, rad=±0.5, rad=
±limit → rqt setzen, echten Winkel der grünen Linie gegen die Erwartung messen.
- Roundtrip rad→pulse→rad konsistent (calibration-Tests).
- power_on_mid (1500 µs) bleibt in [pulse_min, pulse_max] (1500 liegt mittig).

---

## 3. Betroffene Dateien (Edit-Liste)

> **Vor dem Edit: `servo_mapping.yaml` sichern** (Kopie/git-Stand) — große
> Cal-Änderung, Rollback muss möglich sein.

| Datei | Änderung |
|---|---|
| `servo_mapping.yaml` | **6 Tibia-`pulse_zero`** (+ ggf. **pulse_min/max**, falls volle Re-Cal nach §2.3/§7.2) auf die verifizierten Werte. |
| `hexapod_physical_properties.xacro` / `hexapod.urdf.xacro` / `hexapod.ros2_control.xacro` | Tibia-rad-Limits prüfen/ggf. anpassen (asymmetrisch nach Shift) — **per-Bein-Override beachten** (Memory femur_zero_asymmetry). |
| `config.py` | `_TIBIA_LIMITS` konsistent zur URDF (Memory two_joint_limit_sources). |
| `hexapod.ros2_control.xacro` | **18 Sim-`initial_value`** (power_on_mid) — die **Tibia**-Werte neu = `pulse_us_to_radians(1500)` mit neuem pulse_zero. |
| `test_startup_ramp.py` + `test_cartesian_standup.py` | `_POWER_ON_MID`-Fixtures (Tibia-Werte) nachziehen. |
| `tools/standup_envelope_check.py` | `_POWER_ON_MID` nachziehen. |
| `phase_13_stage_0_progress.md` | neuer Design-Log-Eintrag (DL-9) + Sub-Stage-Eintrag. |

**NICHT geändert:** `leg_ik.py`-Formel (Cal-Weg!), `_L_TIBIA=0.200` (Länge
stimmt), FW/Servo2040 (kein Flash), die physische Mechanik.

---

## 4. Folgen für Posen/Verhalten — was sich ändert vs. nachziehen

**Wichtig zu verstehen:** Die kartesischen/rad-DEFINITIONEN (Stand-Pose als
radial/body_height, Walking-Trajektorien) bleiben gleich — die IK rechnet sie.
Mit korrigiertem pulse_zero landet der **echte Fuß jetzt dort, wo die IK ihn
will** (vorher 23° daneben). ABER:

- **power_on_mid-rad (Init, 0.3):** abgeleitet aus `pulse_us_to_radians(1500)` →
  die **Tibia**-Werte verschieben sich um ~23° (Richtung nach Vorzeichen-
  Verifikation). → Sim-`initial_value` + Test-Fixtures + Tool **neu rechnen**
  (mit der finalen Cal, nicht vorab).
- **Stand-Pose (0.4):** rad-Definition (radial 0.295/bh −0.080) bleibt, aber der
  echte Roboter steht jetzt physisch korrekt → **am HW neu prüfen** (Höhe/Stabilität).
- **Walking-Presets (`config/presets/`):** für die alte (23°-schiefe) Geometrie
  getunt → am echten Roboter **re-validieren**, ggf. nachziehen.
- **Aufstehen (0.7):** `body_height_start`, Phase-1/2-Trajektorie → mit
  korrigierter Geometrie neu prüfen (das Schleifen sollte verschwinden, weil die
  IK jetzt die richtige, steilere Tibia-Stellung kommandiert).

---

## 5. Stage-0-Re-Validierung (Test-Dokus wiederverwenden)

Die Korrektur berührt die Kinematik-Kette → betroffene Tests **nochmal durchlaufen**
(bestehende `*_test_commands.md` wiederverwenden). Reihenfolge + was sich am
erwarteten Ergebnis ändert:

1. **Cal-Verifikation (neu, rqt):** pro Bein den pulse_zero-Kandidaten setzen,
   prüfen dass die grüne Gelenk→Fuß-Linie bei Femur-horizontal gerade/horizontal
   ist. Erwartung neu: „rad=0 → grüne Linie gerade" (vorher: Segment 1 gerade).
2. **`colcon test hexapod_hardware`** (calibration roundtrip) + **`hexapod_gait`**
   (nach Fixture-Update) grün.
3. **`tools/standup_envelope_check.py`** — GRÜN mit neuen Werten (rechnerisch).
4. **Sim:** `phase_13_stage_0_5_sim_standup_test_commands.md` + ein **Laufen-Smoke**
   (cmd_vel, aufgebockt-Stil) — Aufstehen schürffrei UND Laufen noch ok.
5. **HW aufgebockt:** `phase_13_stage_0_6_hw_standup_test_commands.md` (Init +
   Stand-up) + `phase_13_stage_0_7_hw_standup_test_commands.md` Teil A.
6. **HW Boden:** `phase_13_stage_0_7_hw_standup_test_commands.md` Teil B —
   **Strom-Peak messen**: Schleifen weg → Strom nahe Stand-Niveau (Done-Kriterium).
7. **Laufen-Re-Check** (aufgebockt, cmd_vel) — die Geometrie-Korrektur darf das
   Laufen nicht verschlechtern; idealerweise verbessert sie die Fuß-Genauigkeit.

---

## 6. Reihenfolge / Ablauf (CLAUDE.md §4)

1. **Diesen Plan finalisieren** + User-Freigabe (Offset-Ort Cal ✅, Werte
   rechnerisch+verifizieren ✅).
2. **Cal-Verifikation live** (§5.1): den richtigen Kandidaten je Bein bestimmen.
3. **servo_mapping.yaml** + Limits + Sim-initial_value + Fixtures editieren.
4. **Rechnerisch validieren:** colcon test + standup_envelope_check.
5. **Sim** (Aufstehen + Laufen).
6. **HW** aufgebockt → Boden (Strom).
7. **Self-Review** + Progress/Design-Log (DL-9).

---

## 7. Offene Punkte für User-Review

| # | Frage | Status |
|---|---|---|
| 7.1 | Offset-Ort Cal vs URDF | ✅ **Cal** (Weg A, IK unberührt) |
| 7.2 | **Reiner pulse_zero-Shift vs. volle Tibia-Re-Cal?** Wegen der asymmetrischen Slope (§2.3) ist Shift-allein wahrscheinlich physikalisch inkonsistent | ⏳ **wahrscheinlich volle Re-Cal** (pulse_zero + min/max), wie Femur 0.2 — am Anfang entscheiden |
| 7.3 | Vorzeichen/Drehrichtung (Kand A vs B) | ⏳ **live per rqt** (Vermutung Kand B) |
| 7.4 | Tibia-rad-Limits nach Re-Cal anpassen? (per-Bein-Override!) | ⏳ aus den verifizierten Werten ableiten |
| 7.5 | Welche Walking-Presets re-tunen? | ⏳ nach dem Laufen-Re-Check entscheiden |
| 7.6 | Stand-Pose-Höhe nach Korrektur noch optimal? | ⏳ am HW prüfen (0.4-Tabelle) |
| 7.7 | Sind die aktuellen Tibia-Cal-Werte gültig? (User kalibrierte vor dem Femur-Umbau — Femur-Umbau ändert die Tibia-Mechanik nicht, also vermutlich ja, aber verifizieren) | ⏳ am Anfang prüfen |

---

## 9. Stage 0.6.5 — Mess-Sub-Stage (Plan, CLAUDE.md §4)

> Vorgelagerte Mess-Stage, die §1a datengetrieben entscheidet. Ändert **keinen
> Code, keine Cal** — nur Messen. Re-Cal/Limits/Init-Nachzug = eigene Folge-
> Sub-Stage je nach Branch.

### 9.1 Logik-Skizze
**Ziel:** empirisch bestimmen, ob die Tibia ab der echt-geraden Pose den geforderten
Beuge-Bereich (Standup-Demand **+0.16…+0.88 rad**, Ziel ≳ +1.05 rad / 60° mit
Reserve) **innerhalb der mechanischen Grenzen** erreicht → Cal-only genügt; sonst
Remount (§1a).

1. **Setup:** aufgebockt, Relay an, `publish_servo_pulses=true`. Femur+Coxa des
   Mess-Beins via JTC auf **rad=0** (Femur = horizontal nach 0.2). Nur die Tibia
   wird bewegt.
2. **Jog-Mechanismus:** pro Tibia-Pin (2/5/8/11/14/17) in rqt_reconfigure
   `pin_N.pulse_zero` sweepen — da Tibia-rad=0 gehalten, ist **Ausgangs-Puls =
   pulse_zero** → Servo folgt direkt; echten µs am `/servo_pulses` (Index = Pin)
   ablesen. Vorher `pin_N.pulse_min`→500 / `pulse_max`→2500 weiten, sonst klemmt
   der Clamp vor dem mech. Anschlag. (Param-Range ist [500,2500],
   `hexapod_system.cpp:1104` — deckt den ganzen Bereich ab.)
3. **4 Punkte je Bein** (virtuelle Knie→Fuß-Linie, Endpunkte physisch):
   - **A gerade** (Fuß waagrecht max. ausgestreckt, Knie-Höhe) → `pulse_straight`
   - **B 90°** (Fuß senkrecht unter Knie) → `pulse_perp`
   - **C Beuge-Anschlag** → `pulse_bend`  · **D Streck-Anschlag** → `pulse_ext`
4. **Auswertung:** `k = |pulse_perp − pulse_straight| / (π/2)`;
   `θ_bend = |pulse_bend − pulse_straight| / k`; `θ_ext = |pulse_ext − pulse_straight| / k`.
   **Cross-Check** `k` gegen die aktuelle Cal-Slope (Plausibilität ±~10 %, wie
   Femur 0.2). Asymmetrie `θ_bend` vs `θ_ext` = Datenbasis für die Branch-Frage.
5. **Pilot:** **leg_1 (Pin 2)** + **leg_4 (Pin 11)** zuerst (eine pro Seite,
   dir −1/+1) → **Decision-Gate**. Rest nur falls cal-only (bei Remount eh
   Re-Messung nach Umbau → kein Wegwerf-Aufwand).

> ⚠️ **Kritisch:** „gerade"/„90°" beziehen sich auf die **virtuelle Knie→Fuß-Linie**
> (Knie-Drehpunkt → Fußspitze), **nicht** das sichtbare geknickte Segment. Sonst
> wird der 23°-Bug reproduziert. Die **Länge** (200 mm) wird nicht gemessen/
> berührt — nur der **Winkel-Nullpunkt** (welcher Puls = gerade).

### 9.2 Tests-Liste (was „fertig" markiert)
- 8 Pilot-Werte (leg_1 + leg_4) vollständig erfasst.
- `k`, `θ_bend`, `θ_ext` berechnet + `k`-Cross-Check gegen Cal-Slope plausibel.
- Decision dokumentiert (`θ_bend` ≥/< Demand → cal-only/remount) mit Begründung.
- (falls cal-only) restliche 4 Beine erfasst.
- **Bewusst NICHT hier:** die eigentliche Re-Cal (pulse_zero/min/max-Edit),
  URDF/config-Limits, Init-Pose-Nachzug, Sim/HW-Re-Validierung, Walking — alles
  Folge-Sub-Stage je nach Branch.

### 9.3 Progress-Checkliste (→ `phase_13_stage_0_progress.md`, 0.6.5.x)
```
### Sub-Stage 0.6.5 — Tibia-Winkel-Messung (Femur-Stil, Decision-Gate)
- [ ] 0.6.5.1  Setup aufgebockt + Relay + publish_servo_pulses; Femur/Coxa rad=0 gehalten
- [ ] 0.6.5.2  Pilot leg_1 (Pin 2): pulse_straight/perp/bend/ext gemessen
- [ ] 0.6.5.3  Pilot leg_4 (Pin 11): pulse_straight/perp/bend/ext gemessen
- [ ] 0.6.5.4  k + θ_bend + θ_ext berechnet, gegen aktuelle Cal-Slope cross-checked
- [ ] 0.6.5.5  Decision-Gate: cal-only vs. remount (User + Claude, begründet)
- [ ] 0.6.5.6  (falls cal-only) leg_2/3/5/6 (Pins 5/8/14/17) gemessen
- [ ] 0.6.5.7  Folge-Sub-Stage angelegt (Re-Cal-Weg oder Remount-Weg) + Design-Log DL-9
```

### 9.4 Offene Punkte für User-Review
| # | Frage | Status |
|---|---|---|
| 9.1 | Virtuelle-Linie-Peilung zuverlässig treffbar? | ✅ User bestätigt 2026-06-01 |
| 9.2 | Falls Pilot-Beine widersprechen (eins reicht, eins nicht) → Mounting-Toleranz → spricht für Remount | ⏳ aus Pilot-Daten |
| 9.3 | Reichweiten-Schwelle „θ_bend ≳ 60°" ok, oder mehr Reserve fürs Walking? | ⏳ Walking-Tibia-Range ist < Standup-Demand; final nach Laufen-Re-Check |

---

## 8. Cross-References
- Präzedenz: `phase_13_stage_0_plan.md` DL-1 (Femur-Weg-A) · `phase_13_stage_0_2_remount_recal_plan.md`
- Auslöser: `phase_13_stage_0_7_cartesian_standup_plan.md` + `_creation_steps_description.md`,
  Memory `project_phase13_standup_foot_scrape`
- Code: `servo_mapping.yaml` · `calibration.cpp` (radians_to_pulse_us) ·
  `leg_ik.py`/`config.py` · `hexapod.ros2_control.xacro` (initial_value)
- Tests/Tool: `test_startup_ramp.py` · `test_cartesian_standup.py` · `standup_envelope_check.py`
- Mess-Daten: Segment 100/115 mm, Knick 43°, Hypotenuse 200 mm, Offset 23,17°
  (User 2026-05-31). Bild im Chat-Verlauf (geknicktes Bein: schwarz=real,
  grün=virtuelle gerade Tibia).
