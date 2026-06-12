# Stage S2 — Servo-Cal eintragen (plan.md Schritt 3, HW-Schicht)

> Detail-Sub-Plan gemäß CLAUDE.md §4. Übergeordnet: [`plan.md`](plan.md) ·
> Werte-Quelle: [`handover.md`](handover.md) §1 (NICHT die gespeicherte yaml —
> es gab kein `/save_calibration`). Branch `leg_changes`.
> **Nur die Hardware-Anbindungs-Schicht** (`servo_mapping.yaml`) — orthogonal zu
> S1 (Modell). 12 Femur/Tibia-Einträge, **Coxa unberührt**.

---

## 1. Logik / was geändert wird

[`servo_mapping.yaml`](../../src/hexapod_hardware/config/servo_mapping.yaml):
die 12 Femur+Tibia-Pins mit den Handover-§1-Werten ersetzen. **Coxa (Pin
0/3/6/9/12/15) bleibt komplett unverändert** (alte Cal, vom User bestätigt).
`directions` bleiben (geprüft: Femur R+1/L−1, Tibia R−1/L+1 = aktuelle yaml).

| Pin | Joint | pulse_min | pulse_zero | pulse_max | dir |
|---|---|---|---|---|---|
| 1  | leg_1_femur | 1162 | 1828 | 2485 | +1 |
| 4  | leg_2_femur | 1247 | 1890 | 2500 | +1 |
| 7  | leg_3_femur | 1206 | 1841 | 2499 | +1 |
| 10 | leg_4_femur |  502 | 1155 | 1819 | −1 |
| 13 | leg_5_femur |  517 | 1150 | 1814 | −1 |
| 16 | leg_6_femur |  536 | 1172 | 1841 | −1 |
| 2  | leg_1_tibia | 800 | 1860 | 2017 | −1 |
| 5  | leg_2_tibia | 798 | 1901 | 2016 | −1 |
| 8  | leg_3_tibia | 845 | 1940 | 2090 | −1 |
| 11 | leg_4_tibia | 895 | 1050 | 2123 | +1 |
| 14 | leg_5_tibia | 930 | 1079 | 2159 | +1 |
| 17 | leg_6_tibia | 970 | 1134 | 2215 | +1 |

Vorab geprüft: alle 12 erfüllen `pulse_min < pulse_zero < pulse_max` und liegen
in `[500, 2500]` (min 502, max 2500). Header-Kommentar (`status`/`calibrated_at`
+ Cal-Historie) auf den Bein-Umbau aktualisieren.

## 2. Design-Entscheidungen

- **DS2-1 — Backup nach `/tmp`, nicht in den Source-Tree.** git (Branch
  `leg_changes`) ist die kanonische Historie; ein `.bak` im `config/` wäre
  redundant + Clutter. Sicherheits-Kopie nach `/tmp/servo_mapping_legv1.bak`
  vor dem Edit (erfüllt die Handover-„`.bak` vorher"-Intention ohne Tree-Müll).
- **DS2-2 — Cal-seitigen Wächter ergänzen** (analog S1, DS1-4): `RealConfigFile`
  prüft heute nur Parse + Coxa-pin0. Ich erweitere ihn, sodass er die neuen
  Werte + das Cal×Limit-Zusammenspiel abdeckt. _Verworfen:_ nur manuell prüfen →
  kein Regressionsschutz für die Cal (gleiche Begründung wie S1).

## 3. Tests / Done-Kriterium

> ⚠️ **Verzahnung Cal × Limit:** `radians_to_pulse_us` rechnet
> `pulse = pulse_zero + dir·rad·slope`, `slope` aus `pulse_min/max` **und** den
> URDF-Limits. Da der controller_manager rad auf `[lower, upper]` clampt (S1) und
> alle `pulse_min/max ∈ [500,2500]`, bleibt der ausgegebene Puls automatisch
> in-range. Der neue Test verifiziert das mit den **echten** Werten + Limits.

| # | Test | fängt |
|---|---|---|
| T1 | `colcon build --packages-select hexapod_hardware` | Build-Bruch |
| T2 | `colcon test hexapod_hardware` — `RealConfigFile` (echte yaml parst → Monotonie aller 12; Coxa pin0=1460 unverändert) | Tippfehler/degenerate triplet |
| T3 | … alle Roundtrip/Konversions-Tests (synthetisch, unberührt) grün | Konversions-Mathe-Regress |
| T4 | **Wächter-Erweiterung** (DS2-2): echte yaml + echte Tibia-Limits (−0.28/2.50) → leg_1_tibia (dir −1) **und** leg_4_tibia (dir +1) roundtrip + Puls an den Limits ∈ [500,2500]; Spot-Check 2–3 neue Femur/Tibia-`pulse_zero` als Baseline | Cal/Limit-Drift, vergessene Werte |
| T5 | **Manueller Diff:** die 12 eingetragenen Werte == Handover-Tabelle (volle yaml-Sektion zeigen) | Eintrag-Fehler |

### Bewusst NICHT in S2 (scope-out)
- **Physische Slope-Korrektheit** (ist −0.28 für JEDES Bein der echte rad-Anschlag,
  oder leicht komprimiert?) — nicht unit-testbar; **HW-Check S6** (rad-0 visuell == RViz
  + Sweep ohne Stall/Freeze). Der Streck-Bereich (−rad) wird ohnehin nie aktiv genutzt.
- Envelope/Reichweite → S3. Sim → S4.

## 4. Progress-Checkliste (Done-Vertrag → plan.md §5)

```
### Schritt 3 (HW-Schicht) — Servo-Cal  [S2] ✅
- [x] S2.1 ~~Backup~~ entfällt (User: Commit + eigener Branch = Absicherung)
- [x] S2.2 6 Femur-Pins (1/4/7/10/13/16) ersetzt (Handover-Tabelle)
- [x] S2.3 6 Tibia-Pins (2/5/8/11/14/17) ersetzt; Coxa unberührt; directions unverändert
- [x] S2.4 Header-Kommentar (status/calibrated_at/Historie) aktualisiert
- [x] S2.5 RealConfigFile-Wächter erweitert (DS2-2) — LegChangesCalValuesAndLimitInterplay
- [x] +Fund: test_hexapod_system::kExpectedPulseZero (2. Hardcode-Stelle) nachgezogen
- [x] T1 build · T2 RealConfigFile · T3 Roundtrip · T4 Wächter · T5 Diff grün (549 tests, 0 failures)
- [x] Self-Review-Tabelle (§6), dann Fertig-Meldung
```

---

## 6. Ergebnis + Self-Review (S2 fertig)

`colcon test hexapod_hardware`: **549 tests, 0 failures, 25 skipped** (Lint inkl.).
Neuer Wächter `RealConfigFile.LegChangesCalValuesAndLimitInterplay` grün.

| Punkt | Status |
|---|---|
| 12 Femur/Tibia-Werte == Handover-Tabelle (T5 Diff Zeile-für-Zeile) | OK |
| Coxa (Pin 0/3/6/9/12/15) unverändert; directions unverändert (Femur R+1/L−1, Tibia R−1/L+1) | OK |
| Monotonie `min<zero<max` + Roundtrip + Puls-in-range an den Limits (Wächter, beide dir-Vorzeichen) | OK |
| `pulse_zero` aller 18 doppelt verifiziert: Wächter-Spot-Checks + `test_hexapod_system` (neutral-pulse-Frame) | OK |
| **Fund:** `test_hexapod_system::kExpectedPulseZero` war eine 2. Hardcode-Stelle der Cal — im S2-Plan NICHT antizipiert, von `colcon test` gefangen + nachgezogen | OK (gefixt) |
| `calibrated_at=2026-06-12` = SW-Eintrag-Datum (echtes Cal-Session-Datum nicht in Handover) | 🟡 User kann korrigieren |
| **Physische Slope-Korrektheit** (ist −0.28 je Bein der echte Anschlag? Streck-Slope hat Kink bei rad 0) — Streck wird nie aktiv gefahren; Beuge-Slope ~424 µs/rad = erwartet | 🟢 S6 (HW: rad-0 == RViz + Sweep) |

**Keine 🔴.** S2 erfüllt den Done-Vertrag — die HW-Anbindungs-Schicht trägt die neue
Cal, konsistent mit den S1-rad-Limits, dauerhaft durch einen Wächter abgesichert.

## 5. Offene Punkte für User-Review
1. Backup nach `/tmp` statt `.bak` im Tree (DS2-1) — ok? (git ist eh die Historie.)
2. Wächter-Umfang (T4): leg_1 + leg_4 Tibia (beide Richtungen) + Spot-Checks reicht, oder
   alle 18 Servos in-range/roundtrip durchsweepen? (Vorschlag: die fokussierte Variante.)
