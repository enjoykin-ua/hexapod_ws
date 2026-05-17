# Phase 10 — Stufe B — Kalibrierungs-Log (Audit-Trail)

**Plan:** [`phase_10_stage_b_plan.md`](phase_10_stage_b_plan.md)
**Operative Anleitung:** [`phase_10_stage_b_test_commands.md`](phase_10_stage_b_test_commands.md)

**Zweck:** Dieser Log dokumentiert die **rohen Tester-Ablesungen** und
die **mechanischen End-Stops** von leg_6 (Pin 15/16/17), bevor sie ins
`servo_mapping.yaml` konsolidiert werden. Audit-Trail für späteres
Nachvollziehen: woher kam ein konkreter Pulse-Wert (Tester-Ablesung
vs. URDF-berechnet vs. Stack-Korrektur).

**Status:** 🟡 in Arbeit. Wird während Stage B vom User + Claude
gefüllt; nach B.3-YAML-Konsolidierung bleibt das Log als
**unveränderliches Referenz-Dokument** im Repo (kein retroaktives
Editieren erlaubt — falls Werte später korrigiert werden müssen,
ein neuer Eintrag mit Datum + Begründung anhängen).

---

## §1 — Mech. End-Stops + Self-Collision-Anschläge stromlos (B.1)

**Strategie B' (User-Entscheid 2026-05-17):** leg_5 wird einmal in
worst-case-Pose geschwenkt (Coxa maximal Richtung leg_6) und bleibt
passiv dort für die ganze Stage B. Anschläge sind primär
**Self-Collision mit leg_5**, sekundär Body-Collision oder
Single-Leg-Mechanik.

**leg_5-worst-case-Pose:** ☐ verifiziert (User-Check vor B.1-Start)

### §1.1 — leg_6_coxa_joint (Pin 15)

- **Anschlag negativ (−):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD: Self-Collision mit leg_5 / Body-Kollision / Servo-Mechanik]**
- **Anschlag positiv (+):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD]**
- **URDF-Limit:** ±1.57 rad ≈ ±90°
- **Bindend für `pulse_min`/`max` (Strategie B' — Self-Collision-sicher):** **[TBD: -5° vor Self-Collision-Punkt / Single-Leg-Anschlag / URDF-Limit (engerer Wert gewinnt)]**

### §1.2 — leg_6_femur_joint (Pin 16)

- **Anschlag negativ (−):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD]**
- **Anschlag positiv (+):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD]**
- **URDF-Limit:** ±1.57 rad ≈ ±90°
- **Bindend für `pulse_min`/`max`:** **[TBD]** (typisch Single-Leg-Mechanik oder URDF-Limit, weil Femur leg_5 selten erreicht)

### §1.3 — leg_6_tibia_joint (Pin 17)

- **Anschlag negativ (−):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD]**
- **Anschlag positiv (+):** Winkel ≈ **[TBD]°**, begrenzt durch **[TBD]**
- **URDF-Limit:** ±1.50 rad ≈ ±86°
- **Bindend für `pulse_min`/`max`:** **[TBD]** (typisch Single-Leg-Mechanik oder URDF-Limit, weil Tibia leg_5 nicht erreicht)

---

## §2 — HJ-Tester Pre-Cal (B.2)

User schließt pro Servo Signal/V+/GND am HJ-Tester an, Tester-PSU
auf **7.0 V** eingestellt. Drei Pulsweiten pro Servo ablesen:
`pulse_zero` (visuelle Joint-Mitte), `pulse_min` (kurz vor neg. Anschlag,
+5–10 µs Sicherheits-Abstand), `pulse_max` (kurz vor pos. Anschlag).

**Setup-Konfiguration während B.2:**
- Tester-PSU-Spannung: **7.0 V** (verifiziert am Tester-Display)
- Bench-PSU: **AUS** (irrelevant für Stage B)
- Servo bleibt mech. im Bein montiert; nur Signal/V+/GND-Adapter zum Tester
- **leg_5 ist in worst-case-Pose** (aus B.1-Vorbereitung) und bleibt
  dort während ganzer B.2-Pre-Cal. `pulse_min`/`max` werden mit **5°
  Sicherheits-Abstand vor Self-Collision mit leg_5** gesetzt (Strategie B').

### §2.1 — leg_6_coxa_joint (Pin 15, Diymore 8120MG)

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **[TBD]** | Bein 90° vom Body radial außen (Augenmaß) | — |
| `pulse_min`  | **[TBD]** | Tester zur neg. Endlage, dann +5–10 µs Sicherheitsabstand | **[TBD: mech. Anschlag oder URDF-Limit?]** |
| `pulse_max`  | **[TBD]** | Tester zur pos. Endlage, dann -5–10 µs Sicherheitsabstand | **[TBD]** |

**Plausibilitäts-Check:**
- [ ] `pulse_min < pulse_zero < pulse_max`
- [ ] alle Werte in [800, 2200] µs (Tester-Range)
- [ ] Spannweite plausibel (Coxa: erwartet ~1000–2000 µs für ±90°-Range)

### §2.2 — leg_6_femur_joint (Pin 16, Miuzei MS61)

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **[TBD]** | Femur horizontal zum Boden (Augenmaß) | **Hinweis:** User muss Bein gegen Schwerkraft halten während Mess-Vorgang, weil passive Femur-Pose ist 90° unten |
| `pulse_min`  | **[TBD]** | Tester zur neg. Endlage | **[TBD]** |
| `pulse_max`  | **[TBD]** | Tester zur pos. Endlage | **[TBD]** |

**Plausibilitäts-Check:**
- [ ] `pulse_min < pulse_zero < pulse_max`
- [ ] alle Werte in [800, 2200] µs
- [ ] Spannweite plausibel (Femur: erwartet ~1000–2000 µs für ±90°-Range)

### §2.3 — leg_6_tibia_joint (Pin 17, Miuzei MS61)

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **[TBD]** | Knie gerade, Tibia in Femur-Verlängerung (Augenmaß) | **Hinweis:** passive Tibia-Pose ist gestreckt = bereits nahe Joint-Mitte, kaum aktives Halten nötig |
| `pulse_min`  | **[TBD]** | Tester zur neg. Endlage | **[TBD]** |
| `pulse_max`  | **[TBD]** | Tester zur pos. Endlage | **[TBD]** |

**Plausibilitäts-Check:**
- [ ] `pulse_min < pulse_zero < pulse_max`
- [ ] alle Werte in [800, 2200] µs
- [ ] Spannweite plausibel (Tibia: erwartet ~1050–1950 µs für ±86°-Range)

---

## §3 — Konsolidierung in `servo_mapping.yaml` (B.3)

Werte aus §2 ins YAML übertragen für Pin 15/16/17. `direction` bleibt
durchgehend `+1` (Stage C/D/E entscheidet finalen Wert per
Stack-Beobachtung).

**Vorher (Stand vor B.3):**
```yaml
15: { joint: leg_6_coxa_joint  }
16: { joint: leg_6_femur_joint }
17: { joint: leg_6_tibia_joint }
```

**Nachher (Stand nach B.3, [TBD]):**
```yaml
15:
  joint: leg_6_coxa_joint
  pulse_min:  [TBD]
  pulse_zero: [TBD]
  pulse_max:  [TBD]
16:
  joint: leg_6_femur_joint
  pulse_min:  [TBD]
  pulse_zero: [TBD]
  pulse_max:  [TBD]
17:
  joint: leg_6_tibia_joint
  pulse_min:  [TBD]
  pulse_zero: [TBD]
  pulse_max:  [TBD]
```

**Konsolidierungs-Datum:** [TBD: ISO-Date]
**Commit-Message:** `phase10: leg_6 servo pre-calibration values from HJ tester`

---

## §4 — Audit-Notizen / Abweichungen

(Hier landen alle Punkte wo das Pre-Cal-Vorgehen vom Standard-Workflow
abgewichen ist, z.B. „Anschlag außerhalb Tester-Range, berechneter
Wert" oder „Servo-Streuung im pulse_zero > ±50 µs, dreifach gemessen
und gemittelt".)

[TBD: Einträge nach Stage B falls Abweichungen auftreten]

---

## §5 — Spätere Korrekturen (Stage C+)

Falls Stages C/D/E zeigen dass ein Pre-Cal-Wert nicht ganz passt
(z.B. `pulse_zero` ist 30 µs daneben weil Augenmaß ungenau war),
wird der Wert im YAML korrigiert. Hier ein Eintrag mit Datum +
Begründung:

[TBD: Einträge falls Stages C–E Korrekturen erfordern]
