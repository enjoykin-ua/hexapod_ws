# Stage 6 (HW-Validierung Desktop) — Plan (Bein-Umbau `leg_changes`)

> **Vorgänger:** S5 (Sim) ✅ — Modell/Posen/Presets/Tests grün, Aufstehen +
> Tripod-Lauf + Hinsetzen in Sim bestätigt. **S6-HW-Fix:** Aufstehen/Hinsetzen am
> breiten standup_radial 0.20 (schürffrei) → Reposition auf Walk-Radius 0.160 (s. §5b).
> **Diese Stage = S6 (HW Desktop, aufgehängt → Boden).** Danach S7 (Pi-Kurztest).
> **Plan nach CLAUDE.md §4** — User-Freigabe BEVOR HW läuft. HW-Befehle vollständig
> in [`stage_6_hw_test_commands.md`](stage_6_hw_test_commands.md), nicht im Chat
> ([[feedback_test_commands_in_doc_not_chat]]). Du führst aus, knappe Status zurück.

---

## 0. Ziel + Sicherheits-Prinzip

Die neuen Beine (Femur 0.060 / Tibia 0.134) + die S5-Parametrierung (radial 0.160,
mittel −0.080; Aufstehen breit @ 0.20 + Reposition) auf der **echten Hardware** (Servo2040 + 18 Servos,
Desktop, `/dev/ttyACM0`) validieren. **Reihenfolge zwingend (CLAUDE.md §9):
aufgebockt → Boden**, langsam, Kill-Switch in der Hand.

> **Maschine:** Desktop-Hauptsystem (nicht Pi). Servo2040 an `/dev/ttyACM0`.
> Pi-Kurztest ist S7 (separat).

**Kritisches Gate vorweg:** Die Cal der neuen Beine (S2) wurde aus **Messwerten
eingetragen, aber nie am laufenden Roboter geprüft** (Plan-Bullet 2.4 offen). S6
beginnt deshalb mit der **Cal-Verifikation** — kein Aufstehen/Laufen, bevor rad 0
== Bein gestreckt (HW == RViz) und ein vorsichtiger Sweep ohne Freeze/Stall sitzt.
Sonst fährt der Standup die Servos evtl. in einen Anschlag.

---

## 1. Logik-Skizze / Ablauf (Stufen, jede ist ein Gate für die nächste)

```
S6.1  Cal-Verify (= Plan-Bullet 2.4)  ── GATE ──
        real.launch.py loopback_mode:=false  (Plugin + Controller, KEIN gait)
        → Servos auf power_on_mid. Relay an, kein Trip.
        rad-0-Command an alle Beine → Beine gestreckt, HW == RViz (Sichtprüfung).
        Vorsichtiger Sweep je Joint (klein, langsam) → kein SAFETY_FREEZE/Stall/Ruck.
        WARUM zuerst: validiert die S2-Cal physisch. Ohne das kein Standup.

S6.2  Aufstehen aufgebockt (= 7.1)
        Zusätzlich gait.launch.py use_sim_time:=false robot_description_file:=<urdf>
        → Auto-Standup-Rampe (8 s) von power_on_mid zur Stand-Pose (radial 0.160,
          body_height −0.080). Touchdown breit @ standup_radial 0.20 (schürffrei),
          dann Tripod-Reposition auf 0.160. Erwartung: smooth, kein Stall/Ruck, Touchdown schürffrei.
        Sit/Stand-Toggle (Triangle) je Höhe testen, inkl. **direkt-Sit aus „hoch"
          (−0.100)** — auf HW mit Schwerkraft-Last der größte Absenk-Weg (User-Caveat).
        WARUM use_sim_time:=false: ohne /clock blockt der gait-Timer sonst still
          ([[project_phase13_gait_launch_sim_time_default]]).
        WARUM robot_description_file: aktiviert den IK-Joint-Limit-Check → Out-of-
          limit-Kommandos werden abgelehnt statt an die Servos geschickt.

S6.3  Laufen + Gangarten + Teleop aufgebockt (= 7.2)
        Tripod forward/sidestep/yaw/diagonal; Stance-Switch L2/R2 (tief/mittel/hoch);
          Schrittweite D-Pad; Gangarten D-Pad. Erwartung: kein IKError/Freeze, keine
          Stalls, Strom plausibel (grob beobachten), Beine bewegen sauber.

S6.4  Boden (= 7.3 / 7.4)  ── erst wenn S6.2/S6.3 sauber ──
        Roboter vom Bock auf den Boden. Aufstehen: schürffrei, Strom plausibel
          (kein Dauer-Stall). Dann Laufen + Gangarten am Boden.
        WARUM zuletzt: erst wenn aufgehängt nachweislich sauber, trägt der Roboter
          sein Gewicht — Strom/Stall-Risiko erst hier real.
```

### Berührte Dateien
**Keine Code-Änderung geplant** — S6 ist reine HW-Validierung der S1–S5-Stände.
Nur falls die HW etwas aufdeckt (Cal-Drift, Stall, Limit zu eng): gezielter Fix +
zurück in Sim-Validierung ([[feedback_urdf_refactor_full_smoke]]), dann erneut HW.
Cal-Korrekturen → `servo_mapping.yaml` (via Save-Service). Doku: dieser Plan +
`stage_6_hw_test_commands.md`.

---

## 2. Tests-Liste (Done-Marker) + bewusst NICHT getestet

**HW (User führt aus, knappe Status-Meldung — `stage_6_hw_test_commands.md`):**
- S6-T1 Cal-Verify: rad 0 = Beine gestreckt, HW == RViz; Sweep ohne Freeze/Stall.
- S6-T2 Aufstehen aufgebockt: Touchdown breit @ 0.20 schürffrei → Reposition auf 0.160, kein Stall.
- S6-T3 Sit/Stand je Höhe aufgebockt, inkl. direkt-Sit aus „hoch".
- S6-T4 Lauf aufgebockt: Tripod alle Richtungen + Stance-Switch + Schrittweite + Gangarten, kein Freeze/Stall.
- S6-T5 Boden: Aufstehen schürffrei + Strom plausibel.
- S6-T6 Boden: Laufen + Gangarten.

**Bewusst NICHT getestet (scope-out):**
- **Pi** — S7 (separater Kurztest).
- **Dauerlauf / thermisches Last-Profil / Strom-Limits + LVC** — Phase 8 Elektronik
  (Block D2); S6 prüft grob „Strom plausibel / kein Dauer-Stall", nicht quantitativ.
- **IMU/Balance** (Nicht-Tripod-Wackeln am Boden) — A5, später.
- **Untethered / Batterie** — Block D5.

---

## 3. Progress-Checkliste (Done-Vertrag — in plan.md §5 abhaken)

> Aktualisiert die `plan.md`-Bullets **2.4** + **7.1–7.4**. Pro Bullet sofort
> `[ ]`→`[x]`, nicht batchen ([[feedback_phase_progress_tracking]]).

```
### S6 — HW-Validierung Desktop
- [ ] 2.4  Cal-Verify HW: rad 0 = Bein gestreckt, HW == RViz; Sweep ohne SAFETY_FREEZE/Stall
- [ ] 7.1  aufgehängt: Init + Aufstehen sauber (Touchdown breit @ 0.20 schürffrei → Reposition auf 0.160, kein Stall/Freeze)
- [ ] 7.1b aufgehängt: Sit/Stand je Höhe inkl. direkt-Sit aus "hoch" (−0.100) — kein Stall beim Absenken
- [ ] 7.2  aufgehängt: Laufen (Tripod alle Richtungen) + Stance-Switch + Schrittweite + Gangarten + Teleop
- [ ] 7.3  Boden: Aufstehen schürffrei + Strom plausibel
- [ ] 7.4  Boden: Laufen + Gangarten
- [ ] S6-Self-Review-Tabelle (CLAUDE.md §4) + stage_6_hw_test_commands.md final
```

---

## 4. Offene Punkte für User-Review (vor S6.1)

1. **Versorgung am Bench:** 2S-LiPo (7.4 V nom) oder Bench-PSU? Strom-Anzeige
   vorhanden, um „plausibel/kein Dauer-Stall" grob zu beurteilen? (Quantitative
   Strom-/LVC-Absicherung ist Phase 8, hier nur Sichtkontrolle.)
2. **direkt-Sit aus „hoch":** in Sim sauber (kein Routing nötig). Auf HW der größte
   Absenk-Weg — falls es dort ruckt/stallt, route ich das Hinsetzen aus „hoch" doch
   über mittel (kleine `_SIT_SAFE_MIN_BH`-Anpassung). Erst HW-Beobachtung abwarten.
3. **Clamp-Default** (offen aus S5): `step_length_max` bei 0.050 lassen + D-Pad, oder
   auf 0.060 ziehen? Für HW egal (Lauf-Tempo per D-Pad/Stick steuerbar) — kann bleiben.
4. **Standup-Tempo:** `auto_standup_duration` 8 s (langsam = stromschonend). Für den
   ersten HW-Standup so lassen oder noch langsamer? (§9: erste Bewegung langsam.)

---

## 5b. Code-Fix (S6-HW-Finding): schürffreier Touchdown + Liftoff

> **HW-Beobachtung (aufgebockt):** Beim Aufstehen schleifen die Füße **kurz vor
> dem Touchdown**, beim Hinsetzen **am Flatten-Start** (kurz, dann in der Luft).
> Ursache: das Modell hält ~8 mm Boden-Clearance, real (Mechanik/Cal) minimal
> unterschritten → die **horizontale** Bewegung nahe Boden schleift.

**❌ Verworfen — Option B (xy/z entkoppeln für senkrechten Touchdown am 0.160):**
auf HW INFEASIBLE. Die Vorderbeine reiten ab `power_on_mid` an der Femur-(−90°)-
Wand; „x/y vor z" (einwärts bei hohem z) → IKError/Freeze. Details + warum erst auf
HW aufgefallen (Sim lenient + Test mit alter Config): [[project_standup_vertical_touchdown_infeasible]].
Reverted.

**✅ LÖSUNG (User-Idee): breit aufstehen + Reposition.** Statt am engen 0.160
(Femur-Wand) am **breiten `standup_radial` 0.20** aufstehen — das liegt ≈ der
power_on_mid-Fuß-Pose (~0.217), d.h. die Füße stehen dort schon → der Touchdown
ist **nahezu senkrecht** (kaum Horizontalbewegung) → **schürffrei**. Danach
Tripod-Reposition (Beine gehoben → schürffrei) auf den Walk-Radius **0.160**.
Spiegelbildlich beim Hinsetzen (Füße erst breit raus, dann Bauch senken). = der
Reposition-Mechanismus, der in S5 deaktiviert war, gezielt zurück. Kein neuer
Trajektorien-Code, nur `standup_radial_distance` 0.160 → **0.20**.

**Tests:** `test_cartesian_standup` auf `_RADIAL`=0.20 (prüft die reale breite
Standup-Pose, in-limit) + sit-down-Tests zurück auf REPOSITION; gait-Suite grün.
Walking (0.160) unverändert. Standup grün @ 0.20, walking grün @ 0.160 (Envelope).

**Done-Vertrag (Code-Fix):**
```
- [x] 5b.1 Vertikaler Touchdown (Option B, xy/z entkoppeln) versucht → auf HW INFEASIBLE → reverted
- [x] 5b.2 LÖSUNG (User-Idee): breit aufstehen @ standup_radial 0.20 (≈ power_on_mid → fast senkrechter, schürffreier Touchdown) → Tripod-Reposition auf walk 0.160. Reposition reaktiviert.
- [x] 5b.3 Tests migriert (test_cartesian_standup _RADIAL→0.20; sit-down zurück auf REPOSITION); gait 205/0/28
- [ ] 5b.4 HW-Verify: Touchdown @ 0.20 schürffrei + Reposition sauber (User, aufgebockt)
```

> **❌ Option B (vertikaler Touchdown) ist bei radial 0.160 GEOMETRISCH NICHT
> MACHBAR — auf HW verifiziert + zurückgebaut.** Die Vorderbeine (leg_1/leg_2)
> reiten ab `power_on_mid` an der Femur-(−90°)-Wand. Jede Entkopplung „x/y vor z"
> zieht den Fuß **einwärts während er noch hoch ist** → Femur < −1.57 → IKError
> (auf HW: Standup-Freeze bei leg_1/leg_2 @ z≈+0.03). Die Gegenrichtung „z vor x/y"
> (einwärts bei tiefem z) **schleift** erst recht. Die **gerade Diagonale koppelt
> Einwärts+Absenken** und ist der einzige feasible Pfad (HW-bewährt). → reverted,
> Engine-Konstante entfernt.
>
> **Warum erst auf HW aufgefallen:** (1) Sim lief **lenient** (ohne
> `robot_description` → kein Limit-Freeze); (2) `test_cartesian_standup` nutzte die
> **alten** S4-Werte 0.17/-0.10 (breiter, Femur-Marge) statt der S5-Produktiv-Werte
> 0.160/-0.080 → der Test war am 0.160-Rand blind. **Beides geschlossen:** Test auf
> 0.160/-0.080 migriert (deckt jetzt die reale Geometrie ab); HW-Lauf nutzt
> `robot_description_file` (Limit-Check aktiv).
>
> **Scrape-Mitigation, die bleibt (Option A):** `body_height_start` (Touchdown-z,
> standing_only, live) auf die **echte** Bauch-Auflage-Höhe tunen. Liegt der reale
> Bauch höher als −0.0135, werden die Füße zu tief gefahren → Schleifen; passend
> getrimmt berühren sie den Boden erst beim eigentlichen Touchdown. Alternativ:
> leichtes Schleifen akzeptieren (Füße am Touchdown unbelastet, mechanisch unkritisch),
> oder — wenn schürffrei zwingend — breiteres `standup_radial` + kleine Reposition
> (Femur-Marge für steileren Anflug; widerspricht aber dem Einzel-Radius-Wunsch).

---

## 5. Fallstricke (HW)
- **Cal-Verify ist Pflicht-Gate** — nie aufstehen, bevor rad-0 + Sweep sitzen.
- **`use_sim_time:=false`** für gait auf HW (sonst Timer-Stille).
- **`real.launch.py` muss durchlaufen** während des Tests (Plugin-Loop = Watchdog-
  Heartbeat); nicht zwischendrin beenden → sonst Relay-Drop.
- **Power-On-Zentrieren** der Servos ist HW-Firmware-bedingt unvermeidbar
  ([[project_phase13_initial_pose_presets]]) → **aufgebockt booten**, smooth rampen.
- **Kill-Switch immer griffbereit**; bei Stall/OVERCURRENT/WATCHDOG/Ruck sofort trennen.
- **Aufgebockt zuerst, Boden zuletzt** — Strom/Stall-Risiko erst unter Last real.
- **Lenient vs. Limit-Check:** gait mit `robot_description_file` starten, damit der
  IK-Limit-Check aktiv ist; zusätzlich clampt das Plugin command-seitig (S1 4.2b).
