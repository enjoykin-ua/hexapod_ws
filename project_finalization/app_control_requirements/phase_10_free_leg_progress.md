# Phase 10 — Show „Free-Leg" — Progress

> **Done-Vertrag** aus [`phase_10_free_leg_plan.md`](phase_10_free_leg_plan.md) §5.
> Alle Bullets `[x]` = Phase fertig. Keine retroaktive Anpassung der Kriterien.
>
> **Stand: 🟡 Repo-Seite fertig** (Auslegung offline belegt, Code implementiert, Tests grün).
> Offen: die **Live-Tests** — Sim nach
> [`phase_10_free_leg_test_commands.md`](phase_10_free_leg_test_commands.md), danach HW.

---

## Checkliste

```
Phase 10 (Show „Free-Leg"):
- [x] FL.1 [Offline] Auslegung final: alle Werte gegen die vier Randbedingungen geprueft (FL-T1/T2/T3)
- [x] FL.2 [Tool] show_pose_cog_check.py um Pitch + Offset-Huelle erweitert; Plan an die Tool-Ausgabe nachgezogen
- [x] FL.3 [Engine] show_front_lat: Neutral-Pose mit Coxa-Anteil, spiegelbildlich fuer leg_1/leg_6
- [x] FL.4 [Engine] show_body_pitch_deg: Fuss-Targets ueber lambda(sigma) rotiert, Regression bei 0 Grad (FL-T6)
- [x] FL.5 [Engine/Node] neue Defaults eingetragen; Safe-Ranges korrigiert (0.065-Kante!)
- [x] FL.6 [Engine] MassModel um optionale Femur-/Tibia-Masse erweitert, Default unveraendert (FL-T7)
- [x] FL.7 [Node] show_mode='free_leg' startet die B4-Kette, 'none' beendet sie (FL-T8/T9)
- [x] FL.8 [Node] _pending_show_enter: Stance-Wechsel auf tief, dann Show (FL-T10)
- [x] FL.9 [Teleop] show_enabled-Gate getrennt: /cmd_show an, Cross-Toggle aus (FL-T11)
- [x] FL.10 [Tests] die 27 geskippten test_show_pose-Tests entsperrt + Fixtures auf die neue Geometrie
- [x] FL.11 [Tests] colcon test hexapod_gait (560) + hexapod_teleop (64) gruen, Lint gruen
- [x] FL.12 [Contract] v0.14: free_leg ist implementiert (App-Seite unveraendert)
- [ ] FL.13 [Sim] FL-T12 Round-Trip + FL-T13 Kollision visuell + FL-T14 Trigger-Richtung entschieden
- [ ] FL.14 [HW] FL-T15 aufgebockt -> Boden
- [ ] FL.15 [HW] FL-T16 IMU-Durchsackungs-Messung dokumentiert
- [x] FL.16 [Doku] progress-File + test_commands + ai_navigation; PHASE.md/00_overview auf Phase 10
```

---

## Die Auslegung (FL.1/FL.2 — offline belegt)

`tools/show_pose_cog_check.py --sweep` mit den Defaults aus Plan §1.1:

| Kriterium | Ergebnis | Ziel |
|---|---|---|
| CoG-Marge neutral | **44,7 mm** | — |
| CoG-Marge **Worst-Case über die ganze Stick-Hülle** | **38,6 mm** | ≥ 30 mm ✅ |
| Stick-/Trigger-Hülle erreichbar | **98 %** (123/125) | ≥ 95 % ✅ |
| Bodenfreiheit tiefster Punkt | **15 mm** | ≥ 10 mm ✅ |
| Fuß-Abstand vorne | 0,34 m neutral · 0,29 m zusammengeführt · 0,40 m gespreizt | — |

Nicht erreichbar sind zwei Würfel-**Ecken** (voller Seitenausschlag + voller Trigger + Extremhöhe) —
dort hält das Bein am Limit, was korrekt ist.

**Gegenprobe:** mit `--lat-scale 0.09` meldet das Tool `AUSLEGUNG DURCHGEFALLEN` (Exit 1) — es prüft
also wirklich, statt alles durchzuwinken.

---

## Befunde aus der Umsetzung

### 🔴→OK **Vorzeichenfehler in der Pitch-Rechnung** (gefunden durch Tool↔Engine-Abgleich)
Die erste Implementierung drehte den Schwerpunkt beim Rücktransport in den Welt-Frame mit `+p`
statt `−p`. Folge: das CoG-Gate meldete bei Nase-hoch-Pitch **30,8 mm** statt der realen **44,7 mm**
— die Aussage war ins Gegenteil verkehrt. Aufgefallen ist es nur, weil Engine und Tool dieselbe Pose
rechnen mussten und **unterschiedliche Zahlen** lieferten. Jetzt: beide 44,7 mm.
*(Genau die Falle, vor der `ai_navigation` bei Rotationen warnt.)*

### 🔴→OK **Das CoG-Gate rechnete im falschen Frame**
`compute_load` projiziert den Schwerpunkt in die **körperfeste** xy-Ebene. Bei geneigtem Körper
arbeitet die Schwerkraft aber gegen die **horizontale** Ebene. Ohne Korrektur wäre das Gate bei
Nase-hoch zu pessimistisch (friert eine Show ein, die real stabiler ist) — und bei Nase-runter
**zu optimistisch**, was gefährlich wäre. Jetzt dreht `_show_cog_margin_pitched` CoG und Stützfüße
gemeinsam in die Welt. Ohne Pitch bleibt der alte Pfad bit-identisch.

### 🔴→OK **Vorderbeine wurden fälschlich mitrotiert**
Erst rotierte der Pitch **alle sechs** Beine. Die Vorderbeine hängen aber in der Luft am Körper —
ihre Pose ist körperfest und kippt einfach mit. Sie mitzurotieren hätte sie im Raum festgehalten,
während der Körper sich darunter wegdreht. Jetzt: Pitch wirkt **nur auf die Stützfüße**, und er
fährt über **λ(σ)** erst in Phase b hoch (wenn die Vorderbeine abheben) — dadurch ist der Übergang
bei σ = shift_fraction stetig und der EXIT baut ihn ab, **bevor** die Beine aufsetzen.

### 🟡 **Clamp-Vorprüfung musste dieselbe Mathe bekommen**
`_compute_show_active_angles` prüft vor dem Übernehmen eines Offsets per `leg_ik`, ob die Pose
gültig ist. Diese Prüfung lief zunächst an einer anderen Funktion als der Tick — sie hätte eine
Pose durchwinken können, die der Tick danach als IKError verwirft. Beide nutzen jetzt
`_show_front_target`.

### 🟡 **Der radiale Test-Wert war nicht mehr erreichbar**
`test_radial_offset_extends_leg_and_moves_tibia` forderte 5 cm Ausfahrweg — mit den kurzen Beinen
sind es ~3 cm (der neue Default). Der Test prüft jetzt 3 cm; die Clamp am Limit hat ihren eigenen
Test.

### ℹ️ **Massen-Modell war veraltet, aber konservativ**
`joint_load` rechnete mit einem Einheits-Segment von 0.1167 kg für alle 18 — Stand vor dem
Bein-Umbau (real: Femur 0.102, Tibia 0.118, in Summe 2.550 statt 2.631 kg). Das **überschätzt** die
Beinmassen und damit den Vorwärts-Zug der angehobenen Vorderbeine, war also nie unsicher. Korrigiert
wurde es **nur im Show-Pfad** (optionale Felder, Default unverändert) — Torque-Analyse und
Leveling-Envelope rechnen unverändert weiter. Auf die Marge wirkt es sich mit ~0,1 mm aus.

---

## Was gebaut wurde

| Datei | Änderung |
|---|---|
| `tools/show_pose_cog_check.py` | `--show-lat`, `--pitch-deg`, `--sweep` (Offset-Hülle), Welt-Frame-Marge, Bodenfreiheits-Check, drei Gates mit Exit-Code |
| `gait_engine.py` | `show_front_lat` + `_SHOW_FRONT_LAT_SIGN`, `_show_pitch_at`/`_show_pitched`/`_show_front_target`, `_show_cog_margin_pitched` |
| `gait_node.py` | 2 neue Params (`show_front_lat`, `show_body_pitch_deg`), 6 neue Defaults, `_start_show_enter` (eine Quelle für beide Startwege), `free_leg` → B4-Kette, `_pending_show_enter` + Auto-Stance-Wechsel |
| `joint_load.py` | `MassModel.femur_mass`/`tibia_mass` (optional), `segment_masses()`, `REAL_*_MASS` |
| `joy_to_twist.py` | neuer Param `show_sticks_enabled` — trennt Bedienung vom Controller-Einstieg |
| `test_show_pose.py` | entsperrt (27 Tests), Fixtures auf tiefe Stance + neue Werte |
| `test_show_node.py` | 5 neue Tests (free_leg, Stance-Wechsel, Abbruch) + Coxa-Budget + Bodenfreiheit |
| `test_mass_model.py` | **neu** — 4 Regressionstests inkl. Abgleich gegen die URDF |
| `test_joy_to_twist.py` | Gate-Trennung statt „kein /cmd_show" |
| `interface_contract.md` | v0.14 |

---

## Offene Punkte

- **FL.13–FL.15 (Live):** Sim-Verifikation, dann HW. Befehle im
  [Test-Doc](phase_10_free_leg_test_commands.md).
- **Trigger-Richtung** (FL-T14): Variante A (nach außen, 0.03) ist gesetzt. Die Umkehr ist ein
  reiner Parameter (`sign_show_radial`, dann Skala 0.02) — in der Sim beides ausprobieren.
- **Selbstkollision:** es gibt im Projekt **keinen** automatischen Checker (A4 pausiert). Bei
  zusammengeführten Beinen erstmals relevant → nur visuell (FL-T13).
- **Comms-Loss greift in der Show nicht** (Altbestand aus B4): bricht das WLAN in der Show ab,
  bleibt der Roboter auf vier Beinen stehen. Statisch stabil, aber eine bekannte Lücke.
- **Ausbaustufen** (Plan §7): IMU-Messung → IMU-Regelung, Trigger als Winke-Oszillator,
  Coxa-Weitung, Stützbein-Reposition.
