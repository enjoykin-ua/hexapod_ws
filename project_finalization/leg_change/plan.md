# Bein-Umbau (kürzere Femur + Tibia) — Plan & Tracking

> **Branch:** `leg_changes` (abgezweigt von `main` @ Tag `legs-tibia-long`).
> **Test-Anleitung:** [`test_commands.md`](test_commands.md) (Live-/HW-Befehle).
> **Referenz-Checkliste (nicht duplizieren):**
> [`docs/01_hardware_change_workflow.md`](../../docs/01_hardware_change_workflow.md)
> Szenario 1 (Bein-Segment-Größen) + Pflicht-Sektion „Lokomotion neu validieren".
> **AI-Navigation:** [`project_architecture/ai_navigation.md`](../../project_architecture/ai_navigation.md).

> Pro erledigtem Bullet `[ ]`→`[x]`, **nicht batchen**
> ([[feedback_phase_progress_tracking]]). Live-/HW-Befehle stehen im
> `test_commands.md`, nicht im Chat ([[feedback_test_commands_in_doc_not_chat]]).

---

## ⚠️ Test-Status (Migrations-Zustand bis S4 = Re-Param)

> **Stand nach S1+S2.** Die S1-Geometrie (kürzere Beine) bricht erwartungsgemäß
> ~93/204 `hexapod_gait`-Tests — sie prüfen Posen/Reichweiten, die für die alten
> langen Beine kalibriert waren. **Migrations-Zustand, kein Bug.**

| Paket | Status |
|---|---|
| `hexapod_kinematics` / `hexapod_hardware` / `hexapod_teleop` | 🟢 grün (S1/S2) |
| `hexapod_gait` | 🔴 ~93 rot **bis S5** |

`hexapod_gait`-Kategorien:
- **power_on_mid** (`test_startup_ramp` + Teile standup/reposition): die 18 rad-Werte
  in S3.1 neu gerechnet + in `standup_envelope_check.py` + `ros2_control.xacro`
  eingetragen; die **Test-Kopien** werden in S5 migriert.
- **Posen-/Reichweiten-/Massen-abhängig** (`stance_switch`, `sitdown`, `gait_patterns`,
  `joint_load`, reposition/standup-reach): grün erst mit den NEUEN Posen (S5).
- **Show-Pose** (`test_show_pose`, 23): Show RAUS aus diesem Thread → in S5 skippen/separat.

**Done-Vertrag bleibt:** in **S4 (Re-Param)** sind ALLE gait-Tests wieder grün (mit
neuen Posen migriert), BEVOR der Thread fertig ist. **Detail-Plan/Handover-Anker:**
[`stage_4_reparam_handover.md`](stage_4_reparam_handover.md). Auf dem `leg_changes`-WIP-
Branch sind die roten gait-Tests bis dahin bewusst akzeptiert (User-Entscheid) + hier notiert.

> **Stage-Reihenfolge (korrigiert):** S1 Modell ✅ · S2 Cal ✅ · S3 Envelope ✅ ·
> **S4 Re-Param** (nächste) · **S5 Sim** · S6 HW-Desktop · S7 Pi · S8 Abschluss.
> (Re-Param VOR Sim — man kann nicht sinnvoll simulieren, bevor die Posen drin sind.)

---

## 1. Ziel & Anlass

Bei den HW-Tests (Phase 13, Pi-Bringup) hat sich gezeigt: die **Tibias sind zu
lang**. Beine wurden mechanisch umgebaut:

- **Coxa:** unverändert (Länge + Range), nur **Sichtprüfung** bei der Cal.
- **Femur:** **etwas kürzer**, evtl. **mehr Range nach oben** (zeigt sich bei der Cal).
- **Tibia:** **deutlich kürzer**, evtl. **andere Winkelreichweite** (zeigt sich bei der Cal).
- **rad-Limits ändern sich** → Cal und rad-Limits sind **verzahnt**: erst die
  mechanischen Anschläge bei der Cal bestimmen, dann Limits konsistent setzen.

Ziel: Das gesamte System (Init → Aufstehen → Laufen → Gangarten → Teleop) ist mit
den neuen Beinen wieder lauffähig und validiert — erst in Sim, dann HW aufgehängt,
dann Boden (am Desktop-Hauptsystem), dann ein Kurztest am Pi. Danach `leg_changes`
→ `main` mergen.

**Neue Längen** (werden bei der Cal/Vermessung eingetragen):

| Segment | alt (Tag `legs-tibia-long`) | neu | Quelle |
|---|---|---|---|
| Coxa  | 0.0436 m | unverändert | — |
| Femur | 0.07994 m | **0.060 m** | handover.md §1 (S1) |
| Tibia | 0.200 m | **0.134 m** | handover.md §1 (S1) |
| Massen | segment_mass 0.1167 (alle) | **coxa 0.1167 / femur 0.102 / tibia 0.118** | handover.md §1; Inertien auto via inertials.xacro |

---

## 2. Die zwei Wahrheits-Schichten (orthogonal — aus dem Workflow)

1. **Roboter-Modell (Geometrie/IK):**
   - [`hexapod_physical_properties.xacro`](../../src/hexapod_description/urdf/hexapod_physical_properties.xacro)
     — Längen, Massen, Inertien, rad-Limits (Referenz/Default). Propagiert
     **automatisch** nach URDF/Gazebo/RViz.
   - [`hexapod.urdf.xacro`](../../src/hexapod_description/urdf/hexapod.urdf.xacro)
     — **per-Bein rad-Limits** (6×, maßgeblich seit Stage F) + Mountpunkte.
   - [`hexapod_kinematics/config.py`](../../src/hexapod_kinematics/hexapod_kinematics/config.py)
     — IK-Mirror, **manuell** zu pflegen; `test_config.py` fängt Drift.
2. **Hardware-Anbindung (Servo-Cal):**
   - [`servo_mapping.yaml`](../../src/hexapod_hardware/config/servo_mapping.yaml)
     — `pulse_min/zero/max` + `direction` pro Servo (Cal-Tool schreibt das).

**Verzahnung in diesem Umbau:** Normalerweise sind Geometrie (Längen) und Cal
(Pulse) orthogonal. Hier ändern sich aber **beide** — die Längen (Modell) *und*
die mechanischen Anschläge (→ Cal-Pulse *und* rad-Limits). Daher die
Reihenfolge unten.

---

## 3. Ablauf (9 Schritte)

| # | Schritt | Wo | braucht Längen? |
|---|---|---|---|
| 0 | ✅ Tag `legs-tibia-long` + Branch `leg_changes` | git | — |
| 1 | Neue Beine montieren (Servos auf `power_on_mid` → montieren) | HW | nein |
| 2 | **Servo-Cal** Femur+Tibia (Coxa-Sichtprüfung) → `servo_mapping.yaml` + rad-0-Sichtprüfung (HW == RViz) | HW + Tool | nein |
| 3 | **Geometrie** messen → `physical_properties.xacro` + `config.py` (Mirror) + Massen/Inertien | Modell | **ja** |
| 4 | **rad-Limits** aus den Anschlägen (Schritt 2) → `hexapod.urdf.xacro` (6×, **symmetrisch**) + `config.py` | Modell | — |
| 5 | **Cross-Check + Sim:** `colcon test hexapod_kinematics`, Envelope-Tools (Mathe), Gazebo/RViz-Spawn + Reachability-Viz | Sim/Test | ja |
| 6 | **Neu-Parametrierung:** Stand-Pose, Laufhöhen (2 vs 3?), `radial_distance`, `step_length`, Stance-Modi, Show-CoG | Sim | ja |
| 7 | **HW-Validierung Desktop:** aufgehängt → Boden (Init, Aufstehen, Laufen, Gangarten, Teleop) | HW Desktop | — |
| 8 | **Pi-Kurztest** (Branch am Pi ziehen, Init+Aufstehen+kurz fahren) | HW Pi | — |
| 9 | **Doku-Updates + Merge** `leg_changes` → `main` | git/Doku | — |

> **Reihenfolge-Logik:** Cal (Schritt 2) braucht die Längen **nicht** (rad↔pulse
> ist geometrieunabhängig) und kann sofort nach der Montage laufen. Die Anschläge
> aus der Cal liefern aber die Basis für die **rad-Limits** (Schritt 4). Die
> **Längen** brauchst du erst ab Schritt 3 (Modell) und 5/6 (Envelope/Posen).

---

## 4. Design-Entscheidungen

### D1 — rad-Limits strikt symmetrisch halten (Final)
Die URDF nutzt seit Stage F **strict-symmetrische** rad-Limits (gegen den
Femur-/Tibia-Asymmetrie-Bug [[project_phase13_femur_zero_asymmetry]]). Falls die
neuen Anschläge asymmetrisch ausfallen (z. B. Femur mehr oben): **die engere
Seite als symmetrisches ±-Limit** nehmen (konservativ). Keine asymmetrischen
per-Bein-Limits.

### D2 — Zwei Limit-Quellen synchron (Final)
rad-Limits **immer** in `hexapod.urdf.xacro` (6 Beine) **und** `config.py`
gleich setzen [[project_two_joint_limit_sources]]. `test_config.py` fängt Drift.

### D3 — Validierung Mathe vor Sim vor HW (Final)
Gazebo/RViz sind **lenient** und verstecken out-of-reach/IK-Freeze. Daher:
**Envelope-Tools (Mathe) zuerst**, dann Sim (visuell), dann HW. Reihenfolge der
HW-Validierung: **aufgehängt → Boden** (§9 CLAUDE.md).

### D4 — Laufhöhen offen (2 vs 3) (zu klären in Schritt 6)
Mit kürzerer Tibia schrumpft der erreichbare Höhenbereich — evtl. nur noch
**2 Stance-Höhen** statt 3. Wird aus dem Envelope (Schritt 5/6) bestimmt, nicht
vorab festgelegt.

### D5 — Montage bei `power_on_mid` (Final, User-Vorgabe)
Servos vor der Montage auf den Enable-Init-Wert (`power_on_mid`, 1500 µs) fahren,
**dann** montieren, **dann** kalibrieren — so liegt die mechanische Lage nahe der
Servo-Mitte, und die Cal bestimmt die echte rad↔pulse-Beziehung.

---

## 5. Progress-Checkliste (Done-Vertrag)

```
### Schritt 1 — Montage
- [ ] 1.1 Servos auf power_on_mid, neue Femur+Tibia montiert, Coxa unangetastet

### Schritt 2 — Servo-Cal  (Messung: HW vom User → Handover; Eintrag: S2, stage_2_cal_plan.md)
- [x] 2.1 Femur-Pulse (min/zero/max) für alle 6 → servo_mapping.yaml (S2)
- [x] 2.2 Tibia-Pulse (min/zero/max) für alle 6 → servo_mapping.yaml (S2)
- [x] 2.3 Coxa-Sichtprüfung (unverändert bestätigt — Coxa-Pins unberührt)
- [ ] 2.4 rad-0-Sichtprüfung: Bein gestreckt, HW == RViz, Sweep ohne Freeze → S6 (HW)
- [x] 2.5 mechanische Anschläge (Femur/Tibia) notiert → Handover §1

### Schritt 3 — Geometrie  ✅ S1 (Detail: stage_1_model_plan.md)
- [x] 3.1 Femur+Tibia-Längen gemessen, §1-Tabelle gefüllt (0.060 / 0.134)
- [x] 3.2 physical_properties.xacro: Längen + Massen-Split (coxa/femur/tibia_mass) + Inertien (auto)
- [x] 3.2b leg.xacro: 3 box_inertia-Massen-Referenzen umgehängt
- [x] 3.3 config.py: Längen gespiegelt

### Schritt 4 — rad-Limits  ✅ S1
- [x] 4.1 neue rad-Limits (symmetrisch, D1): tibia_lower -1.00 → -0.28
- [x] 4.2 hexapod.urdf.xacro (6 Beine) gesetzt
- [x] 4.2b hexapod.ros2_control.xacro (6 Beine, command-Clamp) gesetzt — Handover-Lücke
- [x] 4.3 config.py-Limits gespiegelt (D2)
- [x] 4.4 automatisierter Wächter test_per_leg_limits.py (Symmetrie + URDF-Sync + IK-Anker)

### Schritt 5 — Cross-Check + Sim
- [x] 5.1 colcon test hexapod_kinematics grün (xacro↔config.py) — S1, 35 passed
- [x] 5.2 Envelope-Tools gerechnet (walking/standup/torque) — S3, stage_3_envelope_plan.md §6
      (Show entfällt; Empfehlungen: 3 Stance-Höhen, standup_radial ≥0.16, tibia −0.28, Coxa-Fix)
- [ ] 5.3 Gazebo-Spawn + RViz: Modell stimmt visuell, Reachability-Viz plausibel

### Schritt 6 — Neu-Parametrierung
- [ ] 6.1 Stand-Pose (radial_distance, body_height) neu
- [ ] 6.2 Laufhöhen / Stance-Modi (2 vs 3) festgelegt (D4)
- [ ] 6.3 step_length / cycle_time / Walking-Params neu getunt (Sim)
- [ ] 6.4 Show-Pose CoG-Marge (falls Show genutzt)

### Schritt 7 — HW-Validierung Desktop
- [ ] 7.1 aufgehängt: Init + Aufstehen sauber (kein Stall/Freeze)
- [ ] 7.2 aufgehängt: Laufen + Gangarten + Teleop
- [ ] 7.3 Boden: Aufstehen schürffrei + Strom plausibel
- [ ] 7.4 Boden: Laufen + Gangarten

### Schritt 8 — Pi-Kurztest
- [ ] 8.1 Branch am Pi gezogen + gebaut
- [ ] 8.2 Init + Aufstehen + kurz fahren am Pi ok

### Schritt 9 — Abschluss
- [ ] 9.1 00_conventions.md §11 (Geometrie-Tabelle) aktualisiert
- [ ] 9.2 ggf. 01_hardware_change_workflow.md ergänzt
- [ ] 9.3 Self-Review (Tabelle) + diese Checkliste vollständig
- [ ] 9.4 Merge leg_changes → main (+ Tag z. B. legs-v2-done) — User
```

---

## 6. Bewusst NICHT in diesem Thread (scope-out)

- Keine Body-/Coxa-Geometrie-Änderung (nur Femur/Tibia).
- Kein Servo-Tausch (gleiche Servos, nur kürzere Segmente).
- Keine neuen Features (Gangart-Logik, Show, Teleop-Mapping bleiben) — nur
  **Re-Parametrierung** an die neue Geometrie.
- Kein IMU/Balance (A5, separater Thread).
- Pi: nur **Kurztest**, keine volle Pi-Bringup-Wiederholung.

---

## 7. Offene Punkte für User-Review (vor Schritt 1)

1. **Doku-Sprache** der `test_commands.md`: Deutsch (wie Projekt) — bestätigt?
2. **Cal-Tool:** dieselbe Pipeline wie `servo_real_cal` / Phase 10–11
   (rqt + `servo_mapping.yaml`), oder anders? (Beeinflusst `test_commands.md` Teil A.)
3. **Stand-Pose-Referenz:** Soll das kartesische Aufstehen (aktuell Default)
   die Basis bleiben, oder erwartest du durch die kürzere Tibia einen anderen
   Aufsteh-Pfad?
