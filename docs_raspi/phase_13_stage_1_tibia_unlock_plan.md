# Phase 13 Stage 1 / Teil 2 — Tibia-Beuge-Limit freischalten (Weg A, +2.5) + Lauf-Reichweite nutzen

> **STATUS: ⚪ PLAN — erstellt 2026-06-02. Zu reviewen + freigeben VOR Code.**
>
> **Entscheidung (User 2026-06-02): Weg A — Limit hart freischalten** auf das
> strikt-symmetrische Mechanik-Maximum **+2.5 rad (143°)** statt des
> geometrie-getriebenen Laufzeit-Kollisions-Checks (Weg B). Begründung siehe §1.
> **Weg B (`phase_13_stage_1_collision_check_plan.md`) ist damit auf eine spätere
> Phase verschoben** (Balance / unebener Boden / Body-Pose-Teleop) — fürs reine
> Vorwärts-/Omni-Laufen nie getriggert (Füße außen, Femur oben), also jetzt nicht nötig.

---

## 0. ⭐ FÜR DEN NÄCHSTEN CHAT: Was zuerst lesen
1. **`CLAUDE.md`** §4 (Plan→Freigabe→Tests→Self-Review), §5 (Shell-Verbote), §9 (HW-Safety, aufgebockt).
2. **`PHASE.md`**, **`docs/00_conventions.md`** §11.4 (Limits).
3. **`phase_13_stage_1_walk_optimization_plan.md`** — Übergeordnet: §1 Warum, §2 Sichtweisen,
   **§4.2.0 femur-gekoppelter Kollisions-Befund**, Teil 1 (RViz-Reachability).
4. **DIESE Datei** komplett.
5. **`phase_13_stage_0_6_6_tibia_recal_plan.md`** — Cal-Modell (k=425, `pulse_zero=A`,
   `pulse_min/max = pulse_zero ∓ k·limit`, Servo-Range [500,2500]).

**Code/Configs, die geändert werden:**
- `src/hexapod_description/urdf/hexapod_physical_properties.xacro` — Property `tibia_upper`.
- `src/hexapod_description/urdf/hexapod.urdf.xacro` — 6× `tibia_upper`.
- `src/hexapod_description/urdf/hexapod.ros2_control.xacro` — 6× Tibia `upper=`.
- `src/hexapod_kinematics/hexapod_kinematics/config.py` — `_TIBIA_LIMITS`.
- `src/hexapod_hardware/config/servo_mapping.yaml` — 6× Tibia-Beuge-Puls-Bound.
- (Teil 2.2) `src/hexapod_gait/hexapod_gait/gait_node.py` — Walking-Params.
- (Doku) `phase_13_stage_1_reachability_viz_test_commands.md` §3-Korrektur (Slider reicht jetzt
  in den vormals roten Bereich); `phase_13_stage_1_walk_optimization_plan.md` §4.2.1/§7.8
  Decision-Update (Weg A statt B); `collision_check_plan.md` Status → deferred.

---

## 1. Warum Weg A (statt des beschlossenen Weg B)

Aus dem femur-gekoppelten Befund (§4.2.0 des Übergeordneten):
- Es gibt **keinen** konstanten Tibia-Wert, der *gleichzeitig* überall sicher und
  gut fürs Laufen ist (überall-sicher = ~+1.57/90° → magerer Gewinn).
- Ein **großes** Limit (+2.5) ist sicher, **weil Gait + Standup den Femur immer oben
  halten und die Füße außen** (radial ≥ 0.25). Die gefährliche Ecke (Femur-unten +
  tief beugen) wird von den Lauf-/Aufsteh-Trajektorien **nie kommandiert.**
- Der **Laufzeit**-Check (Weg B) würde im Lauf-Normalbetrieb **nie auslösen** — sein
  Wert ist Robustheit für *spätere* dynamische Posen (Balance/Terrain/Body-Teleop),
  die außerhalb von Stage 1 liegen.
- **Design-Zeit-Sicherheit** statt Laufzeit-Netz: `walking_envelope_check` /
  `standup_envelope_check` validieren die konkrete Trajektorie offline gegen die
  Limits + den Body, plus HW-aufgebockt-Verify.

**Akzeptierter Trade-off (auf Protokoll):** Bei +2.5 ohne Laufzeit-Check fehlt das
Sicherheitsnetz, falls *zukünftiger* Code den Femur runter nimmt und tief beugt
(könnte Fuß in den Body fahren → Stall-Strom). Solange Stage 1 = reines Laufen
(Femur oben, Füße außen), ist das kein Thema. Weg B wird nachgerüstet, wenn
Balance/Terrain drankommen.

**Warum +2.5 und nicht +2.6:** +2.6 ist puls-seitig **nicht von allen Beinen
erreichbar** (leg_5 max 2.55, leg_3 grenzwertig) → würde per-Bein-Sättigung und damit
die in Stage F beseitigte Asymmetrie reintroduzieren. +2.5 (143°) ist der größte
**strikt-symmetrische** Wert, den *jeder* der 6 Servos innerhalb [500,2500] erreicht,
mit Reserve fürs ±4°-`pulse_zero`-Peilrauschen. Siehe [[project_phase13_femur_zero_asymmetry]],
[[feedback_validate_hardware_hypothesis_via_code]].

---

## 2. Logik-Skizze / Vorgehen

### Sub-Stage 2.1 — Limit-Unlock auf +2.5 (mechanische Änderung, atomar testbar)

**2.1.a — rad-Limit in allen Quellen auf +2.5 (untere −1.00 bleibt).**
Die Tibia-`upper`-Grenze ist an **vier** Stellen redundant hinterlegt (zwei
Limit-Quellen [[project_two_joint_limit_sources]] + URDF an zwei Stellen):

| Datei | Stelle | alt → neu |
|---|---|---|
| `hexapod_physical_properties.xacro` | Property `tibia_upper` | `1.30` → `2.50` |
| `hexapod.urdf.xacro` | 6× Bein-Makro-Arg `tibia_upper` | `1.30` → `2.50` |
| `hexapod.ros2_control.xacro` | 6× `joint_iface … upper=` | `1.30` → `2.50` |
| `config.py` | `_TIBIA_LIMITS` | `(-1.00, 1.30)` → `(-1.00, 2.50)` |

> `initial=`-Werte (power_on_mid) in ros2_control.xacro bleiben unverändert.
> Falls `hexapod.urdf.xacro` die Property `tibia_upper` bereits referenziert (statt
> Literal), reicht das Property-Update — beim Code-Beginn verifizieren, ob Literal
> oder Property; beide auf 2.50 bringen, generierte URDF ist die Wahrheit.

**2.1.b — servo_mapping.yaml: Beuge-Puls-Bound nachziehen** (`pulse_zero ∓ 425·2.5 = ∓1062.5`,
gerundet; Strecken-Seite −1.00 unverändert):

| Pin | Bein | dir | Feld | alt → neu | Guard |
|---|---|---|---|---|---|
| 2  | leg_1 | −1 | pulse_min | 1158 → **648**  | 648<1710<2135, 1500∈ ✓ |
| 5  | leg_2 | −1 | pulse_min | 1168 → **658**  | ✓ |
| 8  | leg_3 | −1 | pulse_min | 1058 → **548**  | 548>500 ✓ |
| 11 | leg_4 | +1 | pulse_max | 1870 → **2381** | ✓ |
| 14 | leg_5 | +1 | pulse_max | 1968 → **2479** | 2479<2500 ✓ |
| 17 | leg_6 | +1 | pulse_max | 1904 → **2414** | ✓ |

(Rundung ≤0.5 µs ≈ 0.0012 rad — vernachlässigbar, vom Roundtrip-Test toleriert.)

**2.1.c — Build + verifizieren:** `colcon build` (description/kinematics/hardware/gait),
generierte URDF prüfen (alle 6 Tibia `upper=2.5`), Tests grün (s. §3).

### Sub-Stage 2.2 — Feet-closer Lauf-Pose + Re-Tune (der eigentliche Lauf-Gewinn)
Das Unlock allein lässt den Roboter nicht besser laufen — es **ermöglicht** nur die
nähere Pose. Danach:
- `walking_envelope_check recommend` (nutzt live die jetzt +2.5-URDF-Limits) → validierte
  (radial / step_length / step_height)-Config finden, die die größere Beuge ausnutzt und
  gegen den Body Marge hält.
- Walking-Params in `gait_node.py` setzen: kleineres `radial` (Füße näher), größere
  `step_length_max` / `step_height`, ggf. kürzeres `cycle_time` (Tempo).
- Sidestep-Trade-off (kleines radial stresst Coxa ±0.415) → §5.1: omnidirektional vs
  vorwärts-optimiert nach Envelope-Ergebnis entscheiden.
- Sim → HW aufgebockt → HW griffiger Boden: echter Vortrieb, sichtbar größere Schritte.
- Gute Config als Preset speichern ([[project_phase11_convenience_aliases]]).

### (deferred) Sub-Stage 2.3 — Zwei-Phasen Standup→Reposition→Walk
Nur falls 2.2 zeigt, dass der Aufsteh-Touchdown (Füße-draußen) mit der Lauf-Pose
(Füße-näher) kollidiert. Sonst nicht nötig. → eigene Sub-Stage bei Bedarf.

---

## 3. Tests-Liste mit Begründung

### 3.1 Sub-Stage 2.1 (Unlock) — automatisiert
| Test | Prüft |
|---|---|
| `colcon build` description+kinematics+hardware+gait grün | xacro/config konsistent baut |
| Generierte URDF: `xacro hexapod.urdf.xacro` → alle 6 Tibia `upper="2.5"` | Property/Literal sauber durchgezogen |
| `colcon test hexapod_kinematics` (`test_config.py` URDF↔config-Cross-Check) | Beide Limit-Quellen synchron (+2.5) |
| `colcon test hexapod_hardware` (calibration Roundtrip rad→pulse→rad, `pulse_min<zero<max`) | Neue Puls-Bounds konsistent, in [500,2500] |
| `standup_envelope_check` noch GRÜN | Aufsteh-Pfad bleibt limit-konform (weiteres Limit kann nur permissiver sein) |
| IK-Regression (`leg_ik`-Tests) grün | Nichts an der Kinematik kaputt |

### 3.2 Sub-Stage 2.1 — Live (HW aufgebockt, §9-Safety)
| Test | Prüft |
|---|---|
| Tibia-Sweep über neuen Bereich (rad 0 → +2.5) pro Bein, kein OoR-Freeze | Puls-Bounds erreichen +2.5 ohne Sättigung |
| RViz = HW bei +2.5 (Bein faltet ~143°, Fuß tuckt nahe/unter) | rad↔Geometrie stimmt, [[feedback_urdf_refactor_full_smoke]] |
| Aufgebockt: keine Body-Berührung bei den *kommandierten* Posen (Femur oben) | Trade-off-Annahme (Femur oben → sicher) bestätigt |

### 3.3 Sub-Stage 2.2 — Live
| Test | Prüft |
|---|---|
| `walking_envelope_check` der feet-closer-Config GRÜN (Limits + Body-Marge) | Design-Zeit-Sicherheit der Trajektorie |
| Laufen aufgebockt mit neuer Pose → kein Freeze, sichtbar größere Coxa-Schwenke/Hub | Enabler funktioniert |
| Laufen am griffigen Boden → echter Vortrieb (vs „auf der Stelle") | Stage-1-Ziel erreicht |

### 3.4 Bewusst NICHT getestet (scope-out)
- **Laufzeit-Kollisions-Check (Weg B)** — verschoben; im Lauf nie getriggert.
- **Femur-unten-Posen** — werden nicht kommandiert; aufgebockt zudem Boden-irrelevant.
- **Bein-Bein-Kollision** — Wolken überschneiden sich nicht (User-Befund Teil 1).

---

## 4. Progress-Checkliste (→ eigener Progress-Abschnitt)
```
### Teil 2.1 — Tibia-Limit-Unlock (+2.5, strikt-symmetrisch)
- [x] 2.1.1  rad-Limit +2.5 in physical_properties + urdf.xacro(6×) + ros2_control.xacro(6×) + config.py (2026-06-02)
- [x] 2.1.2  servo_mapping.yaml: 6× Beuge-Puls-Bound (leg_1..3 pulse_min 648/658/548, leg_4..6 pulse_max 2381/2479/2414)
- [x] 2.1.3  colcon build grün (4 Pakete); generierte URDF = 6× Tibia `upper="2.5"` verifiziert
- [x] 2.1.4  test_config.py (7) + kinematics (32, 1 skip) + hardware calibration-Roundtrip (44) + IK-Regression grün
- [x] 2.1.5  standup_envelope_check GRÜN (alle 6 Beine)
- [x] 2.1.6  Self-Review-Tabelle + Design-Log (s.u. §7 / §8)
- [ ] 2.1.7  **SIM-Gate (RViz + Gazebo) — VOR Hardware:** Modell lädt mit +2.5; Tibia in
            Gazebo bis +2.5 kommandierbar ohne Controller-Error; **bestehender Gait
            läuft weiter (keine Regression)**; RViz-Slider/Modell erreicht +2.5.
            (URDF-Refactor-Smoke [[feedback_urdf_refactor_full_smoke]]) — Anleitung:
            `phase_13_stage_1_tibia_unlock_test_commands.md` §S
- [ ] 2.1.8  **DANACH** HW aufgebockt: Tibia-Sweep 0→+2.5 ohne Freeze, RViz=HW, keine
            Body-Berührung (Femur oben) — selbe Anleitung §T (User, nach Sim-Gate + Commit)

> **Stand 2026-06-02:** Desktop-Anteil (2.1.1–2.1.6) ✅ fertig. **Sequenz-Gate (User-Wunsch
> 2026-06-02):** erst **Sim (RViz + Gazebo)** verifizieren (2.1.7), DANN echte Hardware
> (2.1.8). Stale +1.30-Code-Referenzen mit-bereinigt + Doku 5.3/5.4 + Parent-Re-Decision.

### Teil 2.2 — Feet-closer Lauf-Pose + Re-Tune  (Sim VOR Hardware)
- [ ] 2.2.1  walking_envelope_check recommend → validierte radial/step_length/step_height-Config
- [ ] 2.2.2  gait_node-Params gesetzt (+ Sidestep-Entscheidung §5.1)
- [ ] 2.2.3  **SIM (RViz + Gazebo): sichtbar größere Schritte/Hub, kein Freeze/IKError** — Gate vor HW
- [ ] 2.2.4  DANACH HW aufgebockt: kein Freeze, größere Schritte/Hub
- [ ] 2.2.5  HW griffiger Boden: echter Vortrieb
- [ ] 2.2.6  Preset gespeichert + Self-Review
```

---

## 5. Offene Punkte für User-Review (vor Code)
| # | Frage | Vorschlag |
|---|---|---|
| 5.1 | Walking omnidirektional-grün ODER vorwärts-optimiert (Sidestep eingeschränkt + Warnung)? | **nach 2.2.1-Envelope entscheiden** — erst sehen, was die nähere Pose der Coxa abverlangt |
| 5.2 | 2.1 und 2.2 in einem Rutsch, oder getrennt? | ✅ **getrennt** (User): 2.1 → **Sim-Gate (RViz+Gazebo)** → Commit → 2.2. Sim VOR HW (User-Wunsch 2026-06-02). |
| 5.3 | Reachability-Viz-Doku §3 jetzt korrigieren (Slider erreicht nach Unlock den vormals roten Bereich)? | **ja, in 2.1** — sonst bleibt die irreführende Zeile stehen |
| 5.4 | Collision-Check-Plan (Weg B) als „deferred" markieren oder löschen? | **deferred markieren** — Konzept bleibt gültig für Balance/Terrain |
| 5.5 | Zwei-Phasen (2.3) — vorsehen oder erst bei nachgewiesenem Bedarf? | **erst bei Bedarf** (wenn 2.2 Touchdown-vs-Lauf-Pose-Konflikt zeigt) |

---

## 6. Cross-References
- Übergeordnet + Befund: [`phase_13_stage_1_walk_optimization_plan.md`](phase_13_stage_1_walk_optimization_plan.md) §4.2.0
- Verschobener Weg B: [`phase_13_stage_1_collision_check_plan.md`](phase_13_stage_1_collision_check_plan.md)
- Cal-Modell: [`phase_13_stage_0_6_6_tibia_recal_plan.md`](phase_13_stage_0_6_6_tibia_recal_plan.md), `calibration.cpp` (`radians_to_pulse_us`)
- Tools: `walking_envelope_check.py` (+README), `standup_envelope_check.py`
- Reachability-Viz: `reachability_viz.py`, [`phase_13_stage_1_reachability_viz_test_commands.md`](phase_13_stage_1_reachability_viz_test_commands.md)
- Memory: [[project_two_joint_limit_sources]], [[project_phase13_femur_zero_asymmetry]],
  [[feedback_validate_hardware_hypothesis_via_code]], [[feedback_urdf_refactor_full_smoke]],
  [[project_phase11_convenience_aliases]]

---

## 7. Kritischer Self-Review (2.1, 2026-06-02)
| # | Punkt | Status |
|---|---|---|
| 1 | Alle 4 Limit-Quellen (physical_properties-Property, urdf.xacro 6×, ros2_control 6×, config.py) auf +2.5; generierte URDF verifiziert 6× `upper="2.5"` | OK |
| 2 | Puls-Bounds neu: alle in [500,2500], `min<zero<max`, 1500 in-range; Calibration-Roundtrip-Test (44) grün | OK |
| 3 | URDF↔config-Cross-Check `test_config.py` (7) grün → beide Quellen synchron | OK |
| 4 | Stale `+1.30`-Code-Referenzen bereinigt (gait_node Param-Desc, reachability_viz Docstring); gait_node/reachability_viz/walking_envelope lesen URDF **live** → ziehen +2.5 automatisch | OK |
| 5 | `standup_envelope_check` GRÜN (weiteres Limit nur permissiver — Aufsteh-Pfad unberührt) | OK |
| 6 | HW-Test-Commands: Femur-Sign (negativ=oben, −0.24=14° belegt) + Controller-Topics korrekt | OK |
| 7 | **Kein Laufzeit-Kollisions-Check** → bei zukünftigen Femur-unten+tief-Posen (Balance/Terrain/Body-Teleop) ungeschützt | 🟢 später (Weg B deferred, auf Protokoll §1) |
| 8 | **leg_5 puls-Marge nur 21 µs** bei +2.5 (pulse_max 2479) → Sättigungsrisiko falls pulse_zero leicht abweicht | 🟡 HW-Test T2 prüft explizit (Brummen/Sättigung) |
| 9 | **Body-Marge bei Femur-horizontal** +2.5 (143°) nahe ~150°-Kollisionsgrenze | 🟡 HW-Test T4 beobachtet, informiert 2.2-Pose |
| 10 | Walking selbst **noch nicht** in Sim verifiziert (2.1 ändert nur Limits, nicht Gait — aber URDF-Smoke Pflicht) | 🟡 Sim-Gate 2.1.7 vor HW (User-Wunsch + [[feedback_urdf_refactor_full_smoke]]) |
| 11 | colcon „override"-Warning (Underlay) | OK (kosmetisch — Build lief in Overlay-install, rebuilt) |

**Fazit:** Kein 🔴. Desktop-Anteil sauber + getestet. Offene 🟡 sind HW-/Sim-Beobachtungen,
die per Gate (2.1.7 Sim → 2.1.8 HW) abgesichert werden, bevor 2.1 final „fertig" ist.

## 8. Design-Log (Entscheidungen + verworfene Alternativen)
- **Weg A (hart freischalten) statt Weg B (Laufzeit-Kollisions-Check):** gewählt, weil
  Gait/Standup den Femur immer oben halten → die femur-gekoppelte Kollisions-Ecke wird
  nie kommandiert; Sicherheit per Design-Zeit-Envelope reicht fürs Laufen. Verworfen:
  Weg B *jetzt* (mehr Aufwand, triggert im Lauf nie) → deferred auf Balance/Terrain.
- **+2.5 statt +2.6 (Mechanik-Max):** +2.6 ist puls-seitig nicht von allen 6 Servos
  uniform erreichbar (leg_5 max 2.55, leg_3 grenzwertig) → würde per-Bein-Sättigung und
  die in Stage F beseitigte Asymmetrie reintroduzieren. +2.5 = größter strikt-
  symmetrischer Wert, alle 6 erreichbar, Reserve fürs ±4°-pulse_zero-Peilrauschen.
  Verworfen: +2.55 (0 Marge), +1.57 (überall-sicher, aber magerer Lauf-Gewinn),
  per-Bein-asymmetrische Limits (würde Stage F rückgängig machen).
- **Sequenz Sim→HW:** Walking erst in RViz + Gazebo beweisen, dann echte Hardware
  (User-Wunsch 2026-06-02 + URDF-Refactor-Smoke-Regel).
