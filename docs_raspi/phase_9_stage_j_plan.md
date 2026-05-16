# Phase 9 — Stufe J — Plan (knapp)

> **Status:** Plan, noch nicht implementiert.
>
> **Parent-Plan:** [`phase_9_hexapod_hardware.md`](phase_9_hexapod_hardware.md)
> Stufe J — Phase-9-Abschluss.
>
> **Hinweis:** Stage I hat bereits einen detaillierten **Stage-J-
> Übergabe-Items-Block** in [`phase_9_progress.md`](phase_9_progress.md)
> (am Ende der I-Sektion) angelegt. Dieser Plan ist die formelle
> Plan-Doku (CLAUDE.md §4) und referenziert die Übergabe-Items als
> die eigentliche Logik-Skizze.

---

## Ziel

Phase 9 mit allen verbleibenden Polish-Items + formellen Phase-Wechsel-
Aktionen abschließen. Kein neuer Code, keine neuen Features, keine
neuen Tests — nur Cleanup + Status-Updates + Hand-Off für User-Commit
+ User-Git-Tag.

---

## Logik-Skizze (vollständige Details siehe `phase_9_progress.md` Stage-J-Übergabe-Items)

1. **`<ros2_control name>`-Rename** in
   [`hexapod.ros2_control.xacro`](../src/hexapod_description/urdf/hexapod.ros2_control.xacro):
   `name="GazeboSimSystem"` → `name="HexapodSystem"`. 1-Zeile-Edit.
   `test_helpers.hpp` benutzt schon `"HexapodSystem"`, also keine
   Test-Anpassung.

2. **Build + Test-Regression-Check.** Erwartung: alle 208 hexapod_hardware-
   Tests grün + 3 launch_test grün. Falls F-T2 (Sim-URDF byte-equal) jetzt
   diffen würde: erwartet, weil das `name`-Attribut sich ändert; Stage F's
   Done-Kriterium ist bereits geschlossen, F-T2 ist kein laufender CI-Test.

3. **PHASE.md-Update:** Phase 9 Status auf 🟢 abgeschlossen, Phase 10
   (Single-Leg Bring-up) auf 🟡 aktiv. Kurze Phase-9-Retro.

4. **hexapod_hardware/README:** Status-Banner 🟡 → 🟢, Status-Zeile auf
   „A+B+C+D+E+F+G+H+I+J abgeschlossen", Stufentabelle J = ✅.

5. **phase_9_progress.md Stage-J-Sektion:** Bullets, Notizen, Self-Review,
   Done-Banner Phase 9 komplett.

6. **Git-Aktionen (User, nicht ich):**
   - `git add -A && git commit -m "phase9: stage J close — name rename + PHASE.md → phase 10"`
   - `git tag phase-9-done HEAD`
   - Optional: `cd ~/hexapod_servo_driver && git tag phase-7-done HEAD` (Stage H H-T3-Doku-Drift)

---

## Tests (alle CI, kein neuer User-Smoke)

| # | Test | Erwartung |
|---|---|---|
| J-T1 | `colcon build --packages-select hexapod_description hexapod_hardware hexapod_bringup` | grün, keine Warnings |
| J-T2 | `colcon test --packages-select hexapod_hardware` | 208/0 unverändert (Plugin nicht angefasst) |
| J-T3 | `colcon test --packages-select hexapod_bringup` | 18/0 unverändert (launch_testing weiterhin grün) |
| J-T4 | `xacro hexapod.urdf.xacro use_sim:=true \| grep "<ros2_control name"` | zeigt `name="HexapodSystem"` |

---

## Progress-Checkliste

- [ ] J.1 Vorab-User-Bestätigung zur einen offenen Frage (siehe unten)
- [ ] J.2 `<ros2_control name="GazeboSimSystem">` → `<ros2_control name="HexapodSystem">` in `hexapod.ros2_control.xacro`
- [ ] J.3 `colcon build` grün (J-T1)
- [ ] J.4 `colcon test` grün (J-T2 + J-T3)
- [ ] J-T4 (xacro-Output zeigt neuen Namen)
- [ ] J.5 PHASE.md: Phase 9 → 🟢, Phase 10 → 🟡, kurze Phase-9-Retro
- [ ] J.6 hexapod_hardware/README: Status-Banner 🟡 → 🟢, Status-Zeile final, Stufentabelle J = ✅
- [ ] J.7 phase_9_progress.md: Stage-J-Sektion mit Bullets + Notizen + Self-Review + Phase-9-Done-Banner
- [ ] J.8 Kritischer Self-Review (CLAUDE.md §4-Pflicht-Schritt, wird in J.7 integriert)
- [ ] J.9 Summary für User mit Commit-Message + Tag-Vorschlag (User führt aus)

---

## Eine offene Frage

### J-Q1 — Phase-7-Tag-Retro im fw-Repo

Aus Stage H H-T3-Doku-Drift: `phase-7-done`-Tag fehlt im
`hexapod_servo_driver`-Repo. Optionaler Cleanup.

- **A (mein Vorschlag): in den User-Commit-Summary aufnehmen als
  optionalen Tipp.** Ich modifiziere nicht das fw-Repo (gehört eher zu
  dir, du entscheidest ob der Phase-7-Hygiene-Tag rückwirkend sinnvoll
  ist).
- B: ignorieren (Doku-Drift bleibt offen, kein Memory-Eintrag mehr nötig
  weil schon in Stage-H-Plan-Korrektur dokumentiert).

---

## Reihenfolge nach Plan-Freigabe

1. User-Antwort zu J-Q1
2. J.2 1-Zeile-name-Rename
3. J.3 + J.4 Build + Test verifizieren
4. J.5 PHASE.md
5. J.6 README
6. J.7 progress.md Stage-J final + Phase-9-Done-Banner
7. Summary an User
8. **User commit + git tag** (nicht ich)

Mit Stage J ist **Phase 9 komplett abgeschlossen**. Nächste aktive
Phase: Phase 10 (Single-Leg Bring-up + Kalibrierung).
