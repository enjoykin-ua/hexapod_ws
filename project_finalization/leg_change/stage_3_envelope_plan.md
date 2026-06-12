# Stage S3 — Mathe-Envelope-Validierung (plan.md Schritt 5, Teil „Mathe")

> Detail-Sub-Plan gemäß CLAUDE.md §4. Übergeordnet: [`plan.md`](plan.md).
> **Strenge Mathe VOR Sim** (ai_navigation D3). Reine Desktop-Rechnung, kein HW,
> keine Sim. Hier fallen die geparkten Entscheidungen — **mit Daten, nicht geraten**.

---

## 0. Ausgangslage / Befunde aus dem Tool-Lesen

- Tools lesen Geometrie aus `config.py` (HEXAPOD) + Limits **live** aus der URDF
  (xacro) → meine S1-Werte greifen automatisch.
- **Neue Reichweite:** innen `|L_f−L_t|`=0.074, außen `L_f+L_t`=0.194 (alt 0.120/0.280).
  Die Tool-Default-Ranges (radial 0.20–0.32) stammen von den **alten** Beinen →
  zum großen Teil out-of-reach → müssen verkleinert werden.
- `standup_envelope_check._POWER_ON_MID` (18 rad @1500 µs) ist nach der S2-Cal
  **veraltet** → neu rechnen (= `pulse_us_to_radians(1500)`).
- Envelope-Tools nutzen **URDF-Coxa-Limits** (±0.415), nicht `config.py` (±1.57)
  → Coxa-Fix unkritisch für die Lauf-Validierung (nur Konsistenz).

---

## 1. Logik / Schritte

### S3.1 — `power_on_mid` neu rechnen (Vorbereitung für Standup-Check)
- Kleines **validiertes** Python-Skript: `servo_mapping.yaml` laden, die
  `pulse_us_to_radians`-Formel (1:1 aus `calibration.cpp`) auf 1500 µs anwenden,
  18 rad-Werte ausgeben.
- **Validierung:** die 6 Coxa-Werte müssen die alten `_POWER_ON_MID`-Coxa-Werte
  exakt reproduzieren (Coxa-Cal unverändert) → beweist die Formel-Replik korrekt,
  dann sind die neuen Femur/Tibia-rad vertrauenswürdig.
- Eintragen in: `tools/standup_envelope_check.py::_POWER_ON_MID` **und**
  `hexapod.ros2_control.xacro` `initial="…"` (6×3) → löst den S4-🟡 gleich mit.

### S3.2 — Coxa-`config.py` verifizieren + entscheiden
- Grep: wer ruft `leg_ik` **ohne** explizite `joint_limits` (= nutzt
  `config.py`-Defaults) **mit nicht-null Coxa**? Envelope-Tools tun es nicht
  (URDF). Wenn kein kritischer Konsument → Fix ist reine Konsistenz.
- Entscheidung (S3.5, mit User): `_COXA_LIMITS (-1.57,1.57)→(-0.415,0.415)`
  jetzt fixen (sauber, `test_config` guard schon da) oder als Altlast lassen.

### S3.3 — Tool-Ranges an die neue Geometrie anpassen
- `walking_envelope_check`: radial-Such-Range in `_find_optimal_radial`
  (0.20–0.32) verkleinern (→ ~0.10–0.22) bzw. als CLI-Arg führen; height-Range
  passend (kürzere Beine = flacherer erreichbarer Höhenbereich).
- `torque_sweep` / `standup` / `show_cog`: Default-radial/height an die neue
  Reichweite anpassen (CLI-Args reichen, kein Code-Edit nötig wo parametrierbar).

### S3.4 — Envelopes rechnen
- **walking** `sweep` → Reichweiten-Tabelle (radial × body_height × step_length,
  alle 4 cmd_vel-Szenarien) = Basis für Laufhöhen + Stand-Pose.
- **standup** → Aufsteh-Pfad (power_on_mid → Touchdown → Stand) grün?
- **torque_sweep** (`--total-mass 3.0`) → quantifiziert die **Last-Verbesserung**
  durch kürzere/leichtere Beine (User-Ziel „Servo-Last senken").
- ~~show_cog~~ → **entfällt** (Show raus aus diesem Thread, User-Entscheid).

### S3.5 — Interpretieren + Entscheidungen (mit User, datengetrieben)
- Laufhöhen **2 vs 3** (aus der walking-Reichweiten-Tabelle).
- `tibia_lower` **−0.28 vs −0.36** (zeigt der Envelope Streck-Bedarf? sonst −0.28).
- Coxa-Fix jetzt/später (S3.2).
- **Empfohlene Stand-/Walk-Params** → Input für S5.

---

## 2. Design-Entscheidungen

- **DS3-1 — `power_on_mid` per Formel-Replik in Python, gegen Coxa validiert.**
  _Verworfen:_ C++-Utility bauen (schwergewichtig); Werte raten (CLAUDE.md-Verbot).
  Die Coxa-Selbstvalidierung macht die Python-Replik vertrauenswürdig.
- **DS3-2 — `power_on_mid` gleich in BEIDE Konsumenten** (standup-Tool +
  ros2_control.xacro). Eine Quelle, einmal rechnen.
- **DS3-3 — Tool-Range-Edits sind Dev-Tool-Pflege**, kein Modell-Eingriff —
  beeinflussen keine Roboter-Wahrheit. Wo CLI-Arg reicht, kein Code-Edit.
- **DS3-4 — Entscheidungen in S3.5 mit Daten**, nicht vorab (Handover §4).

---

## 3. Tests / Done-Kriterium

| # | Check | Aussage |
|---|---|---|
| T1 | `power_on_mid`-Replik: 6 Coxa-rad == alte `_POWER_ON_MID`-Coxa (exakt) | Formel-Replik korrekt → neue Femur/Tibia-rad gültig |
| T2 | `walking_envelope_check sweep` (angepasste Ranges) liefert eine **nicht-leere** GREEN-Region; Reichweiten-Tabelle plausibel (radial < 0.194) | Modell läuft, Reichweite konsistent |
| T3 | `standup_envelope_check` (neue `_POWER_ON_MID`, gewählte Stand-Pose) = GRÜN | Aufsteh-Pfad kinematisch sauber |
| T4 | `torque_sweep` läuft, Peak-/Balance-% plausibel + (Erwartung) niedriger als bei den langen Beinen | Last-Verbesserung belegt |
| T5 | falls Coxa-Fix angewandt: `colcon test hexapod_kinematics` grün (test_config) | kein config-Drift |
| T6 | nach `_POWER_ON_MID`/ros2_control-Edit: `colcon test hexapod_hardware` grün + xacro-Parse | kein Regress |

### Bewusst NICHT in S3 (scope-out)
- **Sim** (Gazebo/RViz, reachability_viz) → S4.
- **Param in Presets schreiben + Sim-validieren** → S5 (S3 liefert nur Empfehlungen).
- **Real-Engine `test_stance_switch`** (Stance-Modi) → S5 (ai_navigation warnt: Tool am
  Femur-Wand-Rand zu optimistisch; Stance-Modi mit echter Engine in S5).
- **HW** → S6.

---

## 4. Progress-Checkliste (Done-Vertrag → plan.md §5 Schritt 5.2)

```
### Schritt 5.2 — Mathe-Envelope  [S3] ✅
- [x] S3.1 power_on_mid (18 rad) neu gerechnet + gegen Coxa validiert (T1: alle 6 OK)
- [x] S3.1 eingetragen: standup _POWER_ON_MID + ros2_control.xacro initial (löst S4-🟡)
- [x] S3.2 Coxa-config: per-Bein-URDF maßgeblich, config.py war Altlast → gefixt (±0.415)
- [x] S3.3 Tool-Ranges: walking via `check` (explizite Posen) + torque_sweep CLI-Ranges
- [x] S3.4 walking (T2 grün, breit) · standup (T3 grün @ standup_radial 0.16) · torque (T4: 7-15%)
- [x] S3.5 Entscheidungen: 3 Höhen, tibia -0.28, Coxa-Fix ja, standup_radial ≥0.16
- [x] T5/T6 kinematics 36/0 grün + xacro-parse ok (gait 93 rot = Migration bis S5)
- [x] Self-Review (§6), dann Fertig-Meldung
```

---

## 6. Ergebnis + Self-Review (S3 fertig)

### Daten (Mathe-Envelope)
- **Reichweite:** erreichbar radial ~0.08–0.20 (höhenabhängig); im Stand kein
  Limit-Bottleneck, nur Geometrie (innen 0.074 / außen 0.194 = Handover).
- **Walking:** breiter grüner Bereich bh −0.07…−0.13 × radial 0.13–0.16,
  step_length 0.03, **alle 4 cmd_vel-Szenarien grün**.
- **Aufstehen:** grün für ALLE Zielhöhen (−0.07…−0.13) mit **standup_radial ≥0.16**
  (breiter Touchdown wg. Femur-±90°-Wand bei flacher Bauch-Pose; kleines radial
  bräuchte Femur jenseits −90°).
- **Servo-Last:** Peak **7–15 % @ 3.0 kg**, alle stabil (Marge 172–215 mm) → Umbau-Ziel erreicht.

### Empfehlung für S5 (Startwerte — real-engine + Sim feinjustieren!)
- **3 Stance-Modi:** hoch ~(radial 0.16, bh −0.07), mittel ~(0.145, −0.10), tief ~(0.13, −0.13).
- **standup_radial ≥0.16** (Zwei-Phasen: breiter Touchdown → engeres Walk-radial).
- **step_length-Start 0.03** (Max in S5 nachtunen).
- ⚠️ ai_navigation: `walking_envelope` ist am Femur-Wand-Rand zu optimistisch →
  Stance-Modi + Übergänge in S5 mit `test_stance_switch` (real-engine) + Sim prüfen.

### Self-Review
| Punkt | Status |
|---|---|
| power_on_mid Coxa-validiert (Formel-Replik korrekt), in Tool + ros2_control (Sim+HW xacro ok) | OK |
| Coxa-Fix: kinematics 36/0, URDF coxa ±0.415 (kein Regress), Wächter deckt jetzt 3 Joints | OK |
| Envelope-Reichweite == Handover (0.074/0.194) | OK |
| **5. power_on_mid-Stelle** (3 gait-Tests) bewusst NICHT angefasst → S5-Migration | 🟡 S5 |
| `walking_envelope` am Femur-Wand-Rand optimistisch | 🟡 S5 real-engine |
| hexapod_gait 93 rot (Migrations-Zustand, in plan.md notiert) | 🟡 S5 |

**Keine 🔴.** S3-Mathe liefert die Posen-Empfehlungen + geklärten Entscheidungen für S5.

---

## 5. Offene Punkte — geklärt
1. **Show-Pose: RAUS aus diesem Thread** (User) — Fokus Lokomotion-Kern; `show_cog`
   läuft in S3 NICHT; Show separat später neu auslegen (alte Show-Pose mit kurzen
   Beinen eh unerreichbar).
2. **`--total-mass = 3.0 kg`** (User: URDF-Summe + 2S-LiPo + Verkabelung).
3. Coxa-Fix + Laufhöhen + `tibia_lower` → **in S3.5 mit den Daten** entschieden.
