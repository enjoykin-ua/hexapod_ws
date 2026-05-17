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

**leg_5-worst-case-Pose:** ☒ verifiziert (User-Check vor B.1-Start, 2026-05-17)

> **Hinweis zur Mess-Methodik:** User hat in der Praxis §1 und §2 in
> einem Schritt am Tester ermittelt — der Tester-Drehknopf wurde direkt
> bis kurz vor den jeweiligen Anschlag bewegt, der µs-Wert abgelesen.
> Eine separate stromlose Winkel-Messung mit Augenmaß war nicht möglich
> (kein Goniometer/Winkelmesser am Bench). Die Anschlags-**Ursachen**
> sind dennoch qualitativ identifiziert (Self-Collision vs. mech. Anschlag).

### §1.1 — leg_6_coxa_joint (Pin 15)

- **Anschlag negativ (−):** Winkel nicht direkt gemessen (µs-Wert: 1280, siehe §2.1), begrenzt durch **Self-Collision mit leg_5** (Strategie B': 5° vor Berührungspunkt mit leg_5 in worst-case-Pose)
- **Anschlag positiv (+):** Winkel nicht direkt gemessen (µs-Wert: 1860, siehe §2.1), begrenzt durch **mech. Bein-Endlage** (Bein zeigt nach vorne, maximal weg von leg_5)
- **URDF-Limit:** ±1.57 rad ≈ ±90°
- **Bindend für `pulse_min`/`max` (Strategie B' — Self-Collision-sicher):** **Self-Collision-Punkt mit leg_5 für `pulse_min`** (engerer als URDF-Limit); **Single-Leg-mech. Anschlag für `pulse_max`**

### §1.2 — leg_6_femur_joint (Pin 16)

- **Anschlag negativ (−):** µs-Wert: 840 (siehe §2.2). Beobachtung: „Bein hängt nach unten". Servo dort **ruhig**, kein Stall-Brumm → mech. Anschlag liegt **außerhalb des HJ-Tester-Range (< 800 µs)**, 840 ist das Tester-Range-Limit, nicht der echte mech. Anschlag.
- **Anschlag positiv (+):** µs-Wert: 2170 (siehe §2.2). Beobachtung: „Bein zeigt nach oben". Servo ruhig → mech. Anschlag liegt **außerhalb Tester-Range (> 2200 µs)**, 2170 ist Tester-Range-Limit.
- **URDF-Limit:** ±1.57 rad ≈ ±90°
- **Bindend für `pulse_min`/`max`:** **URDF-Software-Clamp** im Plugin (rad-Goal → pulse) und in JTC (rad-Goal in URDF-Range geclampt). Tester-gemessene Pulse-Grenzen (840/2170) sind deutlich **weiter als URDF-Limit** → effektive Begrenzung kommt aus Software-Schicht, nicht aus Pulse-Hard-Stop. Phase 12 SW-Auto-Cal kann den echten mech. Anschlag jenseits 800/2200 µs ermitteln.

### §1.3 — leg_6_tibia_joint (Pin 17)

- **Anschlag negativ (−):** µs-Wert: 840 (siehe §2.3). Beobachtung: „Tibia zeigt vom Körper weg" (gemessen mit Femur passive Pose ~unten). Servo ruhig → Tester-Range-Limit (< 800 µs liegt mech. Anschlag).
- **Anschlag positiv (+):** µs-Wert: 2172 (siehe §2.3). Beobachtung: „Tibia zeigt zum Körper" (Knie zuklappen). Servo ruhig → Tester-Range-Limit (> 2200 µs liegt mech. Anschlag).
- **URDF-Limit:** ±1.50 rad ≈ ±86°
- **Bindend für `pulse_min`/`max`:** **URDF-Software-Clamp** im Plugin und JTC. Tester-gemessene Pulse-Grenzen sind weiter als URDF-Limit → effektive Begrenzung kommt aus Software. Phase 12 SW-Auto-Cal kann mech. Anschlag jenseits Tester-Range ermitteln.

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

**Gemessen am:** 2026-05-17, User am Bench mit HJ-Tester, Tester-PSU 7.0 V,
leg_5 in worst-case-Pose (Coxa max Richtung leg_6).

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **1550** | Bein 90° vom Body radial außen (Augenmaß) | typische Servo-Streuung gegenüber Nominal-1500 µs (+50 µs), unauffällig |
| `pulse_min`  | **1280** | Tester langsam Richtung leg_5 gedreht, gestoppt 5° vor Berührung mit leg_5 | **Self-Collision-Anschlag mit leg_5** — wenn niedriger gesetzt, kann leg_6 leg_5 treffen (Strategie B' bindender Wert) |
| `pulse_max`  | **1860** | Tester langsam in andere Richtung, bis Bein nach vorne zeigt (max weg von leg_5) | mech. Bein-Endlage Richtung +X — Single-Leg-Anschlag oder Bein-Geometrie-Grenze |

**Plausibilitäts-Check:**
- [x] `pulse_min < pulse_zero < pulse_max` (1280 < 1550 < 1860 ✓)
- [x] alle Werte in [800, 2200] µs (Tester-Range)
- [x] Spannweite plausibel (Coxa: erwartet ~1000–2000 µs für ±90°-Range — gemessen **580 µs** ist enger als generisches ±90°-Erwartungs-Range, aber das ist die Strategie-B'-Konsequenz: `pulse_min` begrenzt durch Self-Collision mit leg_5, nicht durch Single-Leg-Mechanik; `pulse_max` durch mech. Bein-Endlage. Asymmetrie um `pulse_zero` (-270 / +310 µs) ist erwartet — leg_5-Seite ist enger als die andere Seite.)

### §2.2 — leg_6_femur_joint (Pin 16, Miuzei MS61)

**Gemessen am:** 2026-05-17, User am Bench mit HJ-Tester, Tester-PSU 7.0 V.

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **1533** | Femur horizontal zum Boden (Augenmaß, Bein gegen Schwerkraft gehalten) | Servo-Streuung +33 µs gegenüber Nominal-1500 µs, unauffällig |
| `pulse_min`  | **840** | Tester zur neg. Endlage (Bein hängt nach unten) | Servo ruhig/kein Stall — Tester-Range-Limit erreicht, echter mech. Anschlag liegt < 800 µs (siehe §4 Audit) |
| `pulse_max`  | **2170** | Tester zur pos. Endlage (Bein zeigt nach oben) | Servo ruhig/kein Stall — Tester-Range-Limit, echter mech. Anschlag > 2200 µs (siehe §4 Audit) |

**Plausibilitäts-Check:**
- [x] `pulse_min < pulse_zero < pulse_max` (840 < 1533 < 2170 ✓)
- [x] alle Werte in [800, 2200] µs (Tester-Range, sogar nahe Range-Grenzen)
- [x] Spannweite plausibel — **Hinweis:** gemessen **1330 µs**, deutlich größer als generische ±90°-Erwartung (~900–1000 µs). Femur-Servo (Miuzei MS61, 270°-Servo) hat mech. mehr Range als URDF-Limit. URDF-Software-Clamp (±1.57 rad ≈ ±90°) ist die effektive Begrenzung, nicht der Pulse-Hard-Stop. Asymmetrie um `pulse_zero` (-693 / +637 µs) ist Servo-Eigenheit.

### §2.3 — leg_6_tibia_joint (Pin 17, Miuzei MS61)

**Gemessen am:** 2026-05-17, User am Bench mit HJ-Tester, Tester-PSU 7.0 V,
Femur dabei in passiver hängender Pose.

| Wert | Tester-Ablesung (µs) | Wie ermittelt | Notiz |
|---|---|---|---|
| `pulse_zero` | **1539** | Knie gerade, Tibia in Verlängerung Femur (Augenmaß) | Servo-Streuung +39 µs gegenüber Nominal-1500 µs, unauffällig |
| `pulse_min`  | **840** | Tester zur neg. Endlage (Tibia zeigt vom Körper weg) | Servo ruhig/kein Stall — Tester-Range-Limit (siehe §4 Audit) |
| `pulse_max`  | **2172** | Tester zur pos. Endlage (Tibia zum Körper, Knie zuklappen) | Servo ruhig/kein Stall — Tester-Range-Limit |

**Plausibilitäts-Check:**
- [x] `pulse_min < pulse_zero < pulse_max` (840 < 1539 < 2172 ✓)
- [x] alle Werte in [800, 2200] µs
- [x] Spannweite plausibel — **Hinweis:** gemessen **1332 µs**, deutlich größer als generische ±86°-Erwartung (~900 µs). Tibia-Servo (Miuzei MS61, 270°-Servo) hat mech. mehr Range als URDF-Limit. URDF-Software-Clamp (±1.50 rad ≈ ±86°) ist die effektive Begrenzung. Asymmetrie um `pulse_zero` (-699 / +633 µs) ist Servo-Eigenheit.

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

**Nachher (Stand nach B.3, 2026-05-17):**
```yaml
15:
  joint: leg_6_coxa_joint
  pulse_min:  1280   # 5° before self-collision with leg_5 (Strategy B')
  pulse_zero: 1550   # visual joint center, leg radial outward
  pulse_max:  1860   # mech. single-leg end stop, leg pointing forward
16:
  joint: leg_6_femur_joint
  pulse_min:  840    # HJ-Tester range limit (mech. stop < 800 µs)
  pulse_zero: 1533   # femur horizontal to ground
  pulse_max:  2170   # HJ-Tester range limit (mech. stop > 2200 µs)
17:
  joint: leg_6_tibia_joint
  pulse_min:  840    # HJ-Tester range limit (tibia pointing away from body)
  pulse_zero: 1539   # knee straight, tibia in femur extension
  pulse_max:  2172   # HJ-Tester range limit (tibia toward body)
```

**Konsolidierungs-Datum:** 2026-05-17
**Commit-Message:** `phase10: leg_6 servo pre-calibration values from HJ tester`

---

## §4 — Audit-Notizen / Abweichungen

(Hier landen alle Punkte wo das Pre-Cal-Vorgehen vom Standard-Workflow
abgewichen ist, z.B. „Anschlag außerhalb Tester-Range, berechneter
Wert" oder „Servo-Streuung im pulse_zero > ±50 µs, dreifach gemessen
und gemittelt".)

### §4.1 — Femur + Tibia: mech. Anschlag liegt außerhalb HJ-Tester-Range (2026-05-17)

**Beobachtung:** Beim Pre-Cal von Femur (§2.2) und Tibia (§2.3) wurden
die Tester-Werte `pulse_min = 840` und `pulse_max ≈ 2170/2172` gemessen
— quasi am Tester-Range-Limit (800–2200 µs). User-Bestätigung:
**Servos blieben ruhig**, kein Stall-Brumm an diesen Werten.

**Schlussfolgerung:** Der echte mechanische Servo-Anschlag liegt
**außerhalb des Tester-Range** (Femur: < 800 µs bzw. > 2200 µs, dito
Tibia). Beide Miuzei MS61 sind 270°-Servos und haben mechanisch
deutlich mehr Range als die ±90° (Femur) / ±86° (Tibia) aus URDF.
Coxa (Pin 15, §2.1) ist davon nicht betroffen — dort begrenzt die
Self-Collision mit leg_5, nicht die Servo-Mechanik.

**Konsequenz für Phase 10:**
- Pre-Cal-Werte werden 1:1 ins YAML übernommen (siehe §3).
- Effektive Joint-Begrenzung kommt aus der **URDF-Software-Clamp**
  (Plugin rad→pulse-Konvertierung respektiert URDF-Limits, JTC
  clampt rad-Goals an URDF). Pulse-Hard-Stop (Firmware-Clamp auf
  `pulse_min`/`max`) wird in Stages C–F faktisch **nicht
  getriggert**, weil die rad-Range aus URDF immer schon enger ist
  als der ins YAML eingetragene Pulse-Range.
- **Self-Collision-Schutz für Femur/Tibia ist in Phase 10 NICHT durch
  Pulse-Hard-Stop gegeben**, sondern allein durch URDF + User-Hand-
  Beobachtung. Praktisch unkritisch, weil Femur/Tibia bei leg_6
  geometrisch nicht in leg_5-Reichweite kommen (anders als Coxa).

**Konsequenz für Phase 12 (SW-Auto-Cal, neue Stufe B):**
- Phase-12-Tool kann den echten mech. Servo-Anschlag jenseits
  Tester-Range ermitteln (sendet kontrolliert Pulse < 800 oder > 2200
  und beobachtet Stall).
- Dadurch werden `pulse_min`/`max` enger gesetzt, näher am echten
  Anschlag — Defense-in-Depth für Phase 12 Voll-Stand + Walking
  mit allen 6 Beinen.
- Beim Mittel-Bein-Coxa (leg_2, leg_5) wird das Tool zusätzlich
  beidseitig die Self-Collision-Grenze prüfen (Phase 10 leg_6 hat
  nur leg_5 als Nachbar; Mittel-Beine haben zwei Nachbarn).

**Audit-Status:** Werte verbleiben so wie gemessen — Abweichung
transparent dokumentiert, Phase-12-Verfeinerung als Cross-Phase-
Pendenz vermerkt (siehe `phase_12_full_bringup.md` Stufe B).

---

## §5 — Spätere Korrekturen (Stage C+)

Falls Stages C/D/E zeigen dass ein Pre-Cal-Wert nicht ganz passt
(z.B. `pulse_zero` ist 30 µs daneben weil Augenmaß ungenau war),
wird der Wert im YAML korrigiert. Hier ein Eintrag mit Datum +
Begründung:

[TBD: Einträge falls Stages C–E Korrekturen erfordern]
