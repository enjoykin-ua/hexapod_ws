# Stage F (Femur-Asymmetrie-Fix) — Plan

> **Status:** Cross-Phase-Thread `servo_real_cal` — Folge-Stage nach
> Stage E2 ✅ 2026-05-25. Adressiert die in E2.3 entdeckte Femur-
> Asymmetrie rechts vs. links (~5° bei "rad=0").
>
> **Operative Anleitung:** [`servo_real_cal_stage_f_femur_test_commands.md`](servo_real_cal_stage_f_femur_test_commands.md)
> (Terminal-für-Terminal-Snippets pro Femur-Servo).
>
> **Übergeordneter Plan:** [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md)
> (Stage F ist Stage 1 von 5 in den Desktop-Pre-Bringup-Stages).
>
> **Vorbedingung:** Cross-Phase-Thread `servo_real_cal` Stages
> 0/0.5/0.6/A/B/D/E/C/E2 alle ✅ ([`servo_real_cal_plan.md`](servo_real_cal_plan.md)).

---

## 1. Ziel

Die in Stage E2.3 visuell aufgedeckte **Femur-Asymmetrie rechts vs.
links** (~5° bei "rad=0") beheben durch Re-Cal von `pulse_zero` der 6
Femur-Servos (Pins 1, 4, 7, 10, 13, 16) gegen visuell horizontalen Femur
mit Wasserwaage.

Nach Stage F:
- Bei `rad=0`-Kommando für jedes Femur-Joint steht das Femur-Segment
  **visuell horizontal** (geprüft mit Wasserwaage)
- `servo_mapping.yaml` enthält neue `pulse_zero`-Werte, persistiert via
  `/save_calibration`
- IK-Stand-Pose ist nun visuell **symmetrisch** rechts/links

## 2. Was Stage F verifiziert

| Aspekt | Verifikations-Mechanismus |
|---|---|
| Visuell horizontaler Femur bei rad=0 | Wasserwaage am Femur-Segment, libellengenau |
| Symmetrische Stand-Pose mit gait_node sim_walk-Preset | Nach Stage F neuer Lauf von `gait_node`, visueller rechts/links-Vergleich |
| Plugin akzeptiert neue pulse_zero-Werte ohne safety_freeze | Plugin-Init-Log nach `/save_calibration`-Persistierung — kein `safety_freeze`-Trigger |
| Cal-Doku konsistent bleibt | `servo_mapping.yaml` MD5-Vergleich, Backup-File `.bak.<timestamp>` vorhanden |
| Bestehende Walking-Performance unverändert | Stage E2-Tempo-Treppe (0.02/0.03/0.035 m/s) läuft auch nach Stage F ohne IKError |

## 3. Was Stage F NICHT verifiziert

- Mechanischer Wurzel-Cause der Asymmetrie (Servo-Mount-Toleranz vs.
  Cal-Auge-Fehler aus Stage B) — wir trimmen das visuell raus, nicht
  systematisch nachvermessen
- Coxa- und Tibia-Asymmetrien (falls vorhanden) — Stage F fokussiert
  nur Femur
- Boden-Walking-Stabilität — kommt in einer späteren Phase

## 4. Logik-Skizze

### 4.1 Vorgehen pro Bein (sequenziell, 6× Wiederholung)

Pro Femur (Pins 1, 4, 7, 10, 13, 16):

1. **Bein in Joint-Null fahren** via JointTrajectory mit `positions=[0,0,0]`
   - JTC interpoliert in 2 s zur Mitte
   - Bei aktuellen Cal-Werten ist "rad=0" für Femur noch leicht schief
     (~5° asymmetrisch)
2. **Wasserwaage an Femur-Segment legen** und Abweichung beobachten
3. **`pulse_zero` schrittweise trimmen** via `ros2 param set` (oder
   rqt_reconfigure)
   - Erhöhung/Senkung in 5-10 µs-Schritten (~0.5-1° physisch)
   - Nach jedem Trim: Bein bewegt sich live nach (Plugin-Live-Param),
     keine Re-Trajectory nötig
   - Stop wenn Wasserwaage anzeigt: Femur horizontal
4. **Pre-Check vor Persistierung** (Mitigation R2 aus Pre-Bringup-Plan):
   ```bash
   ros2 param get /hexapodsystem pin_<N>.pulse_min
   ros2 param get /hexapodsystem pin_<N>.pulse_zero
   ros2 param get /hexapodsystem pin_<N>.pulse_max
   ```
   Verifizieren `pulse_min < pulse_zero < pulse_max`. Wenn nicht: STOP,
   ist Cal-Bug — nicht persistieren.
5. **Werte notieren** (alter pulse_zero, neuer pulse_zero, Δ)
6. **Weiter zum nächsten Bein**

Nach allen 6 Femurs:

7. **`/save_calibration`-Service einmalig aufrufen** persistiert die 6
   neuen pulse_zero-Werte in `servo_mapping.yaml` mit Backup-File
8. **Sanity-Re-Run:** Plugin neu starten, gait_node mit sim_walk.yaml
   starten, Stand-Pose visuell rechts/links-symmetrisch?

### 4.2 Begründung Werte-Wahl

**Warum nur Femur, nicht Coxa/Tibia?**
- E2.3-Findung war **spezifisch Femur** (rechts mehr eingeknickt)
- Coxa-Pose bei rad=0 ist "radial nach außen" — wird in Stand-Pose
  vom IK eh überschrieben, also Asymmetrie weniger sichtbar
- Tibia-Asymmetrie würde Foot-Z verschieben, das fiel bisher visuell
  nicht auf
- Falls Coxa/Tibia auch asymmetrisch sind: separate Stage später
  (Stage G oder Phase-13-Pendenz)

**Warum 5-10 µs-Trim-Schritte?**
- 1 µs ≈ 0.09° (Standard-Servo 1000 µs / 90°)
- 5 µs ≈ 0.45° — feines Trimming
- 10 µs ≈ 0.9° — schneller bei großem Offset
- Wasserwaage zeigt Libellenausschlag bei ~0.5° klar an

**Warum sequenziell, nicht parallel?**
- User hat **eine** Wasserwaage und **eine** Hand pro Bein
- Sequenziell = klar welcher Servo gerade gemessen wird
- Pro Bein: ~5-10 min, gesamt ~30-60 min

**Warum erst alle 6 messen + dann einmal `/save_calibration`?**
- Atomic-Persistence — entweder alle 6 oder keine
- Backup `.bak.<timestamp>` ist eine Datei für alle Änderungen
- Falls user nach Bein 3 abbricht: Plugin-Live-Params bleiben gesetzt
  (RAM), aber `servo_mapping.yaml` bleibt alter Stand — kein
  inkonsistenter Mid-State

### 4.3 Risiken in Logik (siehe auch Pre-Bringup-Plan §5)

**R2 — Plugin-Hard-Stop bei pulse_zero außerhalb Range**

Wenn versehentlich `pulse_zero > pulse_max` oder `< pulse_min` gesetzt
wird → bei nächstem rad=0-Kommando feuert Plugin Stage 0.5 safety_freeze.

Mitigation: Pre-Check-Befehl vor `/save_calibration` (siehe §4.1
Schritt 4). In Praxis sehr unwahrscheinlich, weil aktuelle pulse_zeros
(1445-1560 µs) weit von Edges entfernt sind.

**R-Femur-Mechanisch — Wenn Femur nicht trimmbar ist**

Möglich dass ein Femur-Servo physikalisch in einer Pose montiert ist,
die `rad=0 = horizontal` nicht erlaubt (Schraubenposition versetzt,
Halterung schief). Dann hilft pulse_zero-Trim nicht.

Mitigation: Wasserwaage zeigt Anschlag-Bewegung; wenn nach 50+ µs
Trim immer noch nicht horizontal → STOP für diesen Pin, notieren als
Phase-13-Pendenz (URDF-mount_offset via Option C aus Memory
`project_phase13_femur_zero_asymmetry.md`).

## 5. Tests-Liste mit Begründung

### 5.1 Pflicht-Tests (Live mit User)

| # | Test | Begründung |
|---|---|---|
| T1 | Plugin-Aktivierung nach Stage F erfolgt ohne `safety_freeze`-Trigger | Pflicht-Sanity dass neuer pulse_zero innerhalb [pulse_min, pulse_max] persistiert wurde |
| T2 | Per-Bein bei rad=0 ist Femur visuell horizontal (Wasserwaage-Libelle in Mitte) | Direkt-Verifikation des Stage F Ziels |
| T3 | gait_node mit sim_walk.yaml fährt alle 6 Beine simultan in Stand-Pose, **visuell symmetrisch** rechts/links | Indirekt-Verifikation: vorher war's der primäre Symptom-Indikator |
| T4 | Pre-Check zeigt `pulse_min < pulse_zero < pulse_max` für alle 6 Femur-Pins | Safety-Net gegen R2 |
| T5 | `servo_mapping.yaml` MD5 hat sich geändert; `.bak.<timestamp>`-Datei existiert | Persistence-Verifikation |

### 5.2 Optionale Tests

| # | Test | Wenn ja |
|---|---|---|
| T6 | Walking 0.02 m/s aufgebockt läuft auch nach Stage F sauber (kein neuer IKError) | Bestätigt R1-Streichung — sim_walk.yaml bleibt valid |
| T7 | rqt_reconfigure zeigt neue `pin_<N>.pulse_zero`-Werte nach Plugin-Restart | Bestätigt YAML-Read-Path funktional |

### 5.3 Bewusst NICHT getestet (scope-out)

- **Coxa/Tibia-Asymmetrien** — separate Stage falls nötig
- **Boden-Walking-Stabilität** — kommt erst in späterer Stage
  (Hängevorrichtung oder Pi-Stufe E)
- **Mechanik-Wurzel-Diagnose** — wir trimmen visuell, nicht
  systematisch
- **Auto-Cal-Tool für Femur** — manuelle Wasserwaage ist 1×-Aufwand,
  Tool wäre Overkill für 6 Pins

## 6. Progress-Checkliste

Wird in `phase_<n>_progress`-Style ans Plan-File angehängt nach Live-
Ausführung. Format kopiert in `servo_real_cal_plan.md` Status-Tabelle:

- [ ] F.1 Plugin gestartet, Pre-Stage-F Stand-Pose visuell asymmetrisch
      (Sanity dass Bug noch da ist)
- [ ] F.2 leg_1 Femur (Pin 1) trimmed — neuer pulse_zero notiert
- [ ] F.3 leg_2 Femur (Pin 4) trimmed — neuer pulse_zero notiert
- [ ] F.4 leg_3 Femur (Pin 7) trimmed — neuer pulse_zero notiert
- [ ] F.5 leg_4 Femur (Pin 10) trimmed — neuer pulse_zero notiert
- [ ] F.6 leg_5 Femur (Pin 13) trimmed — neuer pulse_zero notiert
- [ ] F.7 leg_6 Femur (Pin 16) trimmed — neuer pulse_zero notiert
- [ ] F.8 Pre-Check: alle 6 `pulse_min < pulse_zero < pulse_max` ✓
- [ ] F.9 `/save_calibration` aufgerufen, `.bak.<timestamp>`-Datei
      existiert
- [ ] F.10 Plugin neu gestartet, kein safety_freeze
- [ ] F.11 gait_node mit sim_walk.yaml — Stand-Pose visuell rechts/
      links symmetrisch (Vergleich zu Pre-Stage-F-Bild)
- [ ] F.12 (optional) Walking 0.02 m/s aufgebockt läuft sauber
- [ ] F.13 Self-Review-Tabelle in diesem Plan ausgefüllt
- [ ] F.14 Memory `project_phase13_femur_zero_asymmetry.md` updaten
      (✅ wenn alle horizontal, oder Restprobleme notiert)
- [ ] F.15 Memory `project_servo_real_cal_done.md` updaten (Stage F
      als Nachtrag)
- [ ] F.16 `servo_real_cal_plan.md` Status-Tabelle: Stage F ✅
- [ ] F.17 `PHASE.md` Cross-Phase-Thread-Eintrag: Stage F ergänzt

## 7. Offene Punkte für User-Review

Vor Code/Live-Start:

| # | Frage | Mein Vorschlag |
|---|---|---|
| F-Q1 | Trim-Schritt-Größe (5 µs oder 10 µs)? | **10 µs für Erst-Annäherung, 5 µs für Fein-Trim** wenn Wasserwaage nahe Mitte |
| F-Q2 | Reihenfolge der Beine? leg_1 → leg_6 oder rechts-erst (1/2/3) dann links (4/5/6)? | **Rechts-erst** (legs 1/2/3), dann links (legs 4/5/6) — passt zum mentalen Modell "die rechte Seite hat den größeren Offset" aus den Daten |
| F-Q3 | Wasserwaage-Position am Femur — auf Oberkante des Segments? | **Oberkante** des Femur-Segments, parallel zur Femur-Längsachse. Bei Aufbock-Setup: Roboter steht senkrecht, Schwerkraft = Z-Achse, Wasserwaage zeigt Femur-Y-Achse als horizontal an |
| F-Q4 | Falls ein Femur sich nicht trimmen lässt (R-Femur-Mechanisch) — sofort STOP der ganzen Stage oder die anderen 5 weiter machen? | **Andere 5 weitermachen** — partial progress ist ok, problematischer Pin notieren als Phase-13-Pendenz |
| F-Q5 | `rqt_reconfigure` für Trim öffnen oder reine CLI `ros2 param set`? | **CLI** für präzise Werte; rqt als Fallback wenn User lieber Slider klickt. Test-Commands haben beide Varianten dokumentiert |

## 8. Self-Review (wird nach Live-Ausführung ausgefüllt)

| Punkt | Status | Detail |
|---|---|---|
| F-T1: kein safety_freeze nach neuer Cal | (offen) | |
| F-T2: alle 6 Femurs visuell horizontal | (offen) | |
| F-T3: Stand-Pose symmetrisch in gait_node | (offen) | |
| F-T4: Pre-Check vor /save_calibration grün | (offen) | |
| F-T5: YAML + Backup vorhanden | (offen) | |
| F-T6 (optional): Walking 0.02 m/s sauber | (offen) | |
| Mechanische Restprobleme (R-Femur-Mechanisch) | (offen) | |

## 9. Was passiert wenn alles grün

- `servo_real_cal_plan.md` Stage F → ✅ 2026-05-25
- Memory `project_phase13_femur_zero_asymmetry.md` als ✅ markiert
  (oder gelöscht, je nach Reststand)
- Memory `project_servo_real_cal_done.md` ergänzt um Stage F-Nachtrag
- PHASE.md Cross-Phase-Thread-Status: bleibt 🟡 (jetzt Desktop-Stages
  A-D Reihe)
- Bereit für Phase 13 Desktop Stage A (LUT-Infrastruktur)

## 10. Was passiert wenn Probleme

| Problem | Aktion |
|---|---|
| 1+ Femur lässt sich nicht horizontal trimmen | Notieren welcher Pin, andere 5 fertig machen, Phase-13-Pendenz mit Option C (URDF mount_offset) öffnen |
| Pre-Check zeigt pulse_zero außerhalb Range | NICHT `/save_calibration` aufrufen. Werte korrigieren in rqt/CLI. Wenn nicht behebbar: STAGE-F-STATE auf vorher zurücksetzen via Plugin-Neustart (Live-Params verfallen) |
| Plugin safety_freeze trotz Pre-Check | YAML manuell prüfen, ggf. .bak-Backup zurückspielen, Cal-Doku-Werte checken |
| Stand-Pose nach Stage F immer noch asymmetrisch | Coxa- oder Tibia-Asymmetrie zusätzlich vermutet. Neue Stage planen oder Phase-13-Pendenz |
| Walking-Tempo nach Stage F bricht IK-Error | sim_walk.yaml neu generieren via `walking_envelope_check.py recommend` (sollte aber laut R1-Analyse nicht nötig sein) |

---

**Erstellt 2026-05-25. Operative Anleitung liegt in
[`servo_real_cal_stage_f_femur_test_commands.md`](servo_real_cal_stage_f_femur_test_commands.md).**
