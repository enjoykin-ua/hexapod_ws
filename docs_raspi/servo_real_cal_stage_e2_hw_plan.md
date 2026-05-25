# Stage E2 (HW-Walking aufgebockt) — Plan

> **Status:** Live-HW-Walking-Verifikation **aufgebockt**, nach Stage C
> (Direction-Cal HW) abgeschlossen 2026-05-24.
>
> **Operative Anleitung:** [`servo_real_cal_stage_e2_hw_test_commands.md`](servo_real_cal_stage_e2_hw_test_commands.md)
> (Terminal-für-Terminal-Snippets mit erwarteten Outputs + ❌-Diagnose).
>
> **Vorbedingungen:** Stages 0 / 0.5 / 0.6 / A / B / D / E(Sim) / C fertig &
> committed ([`servo_real_cal_plan.md`](servo_real_cal_plan.md) status-
> Tabelle alle ✅).

---

## 1. Ziel

Verifizieren dass die Cal-Werte aus Stages A/B (PWM) + D (rad-Limits) +
C (direction-Map) am **echten Hexapod** ein stabiles Walking produzieren —
mit **aufgebocktem** Roboter (Beine hängen frei, kein Bodenkontakt), so
dass Cal-Fehler ohne mechanische Konsequenzen sichtbar werden.

Stufenweise hochskalieren:

1. ein Bein, 3 Joints koordiniert (E2.1)
2. mehrere Beine simultan (E2.2)
3. `gait_node` Stand-Pose alle 6 Beine (E2.3)
4. Tripod-Walking mit kleinem `cmd_vel` (E2.4)
5. Tempo-Treppe bis IKError / Symptom (E2.5)

## 2. Was Stage E2 verifiziert (vs. Sim-Vorab nicht abgedeckt)

| Aspekt | Verifikations-Mechanismus |
|---|---|
| Plugin-Calibration-Load (PWM-Map + direction) am echten Bus | Plugin-Init-Logs in `real.launch.py`, keine Activate-Errors |
| Servo-Latenz unter koordinierter Trajektorie | E2.1 — visuell ob alle 3 Joints synchron ankommen, kein Joint hängt nach |
| USB-CDC-Bus-Throughput bei 9 simultanen Joint-Commands | E2.2 — keine `serial port write timeout`-Logs |
| URDF-Stand-Pose mechanisch erreichbar (alle 6) | E2.3 — kein Servo-Anschlag-Klick, kein blockierter Joint |
| Gait-Engine + echte Servo-Trägheit kompatibel | E2.4 — Tripod-Rhythmus visuell glatt, keine Body-Sprünge |
| Cal-Range deckt cmd_vel-Tempo-Bereich ab | E2.5 — wo bricht's? IKError-Bein/Joint identifiziert |
| Stage-0.5 PWM-OoR-Freeze triggert *nicht* im Normalbetrieb | Plugin-Logs in T1, kein `safety_freeze`-Log über alle Stufen |
| Stage-0.6 IK-Joint-Limit-Service triggert *nicht* unter sim_walk-Preset | gait_node-Logs in T2, kein `IKError`-Log in E2.3/E2.4 |

## 3. Was Stage E2 NICHT verifiziert

- **Boden-Walking** (Reibung, Stand-Stabilität, Rutschen) — kommt erst
  nach Stage E2, evtl. in Phase 13 oder eigener Stage F.
- **Pose-Stabilität gegen Schwerkraft** (Servos halten unter Last) —
  Aufgebockt entlastet die Beine teilweise, echter Stand kommt später.
- **Strom-Limits unter Last** — aufgebockte Beine ziehen weniger Strom
  als bei Bodenkontakt-Stand.
- **Lange Walking-Sessions** (>1 min) — wir testen 30 s pro Tempo.

→ Phase-13-Pendenzen, siehe §13 weiter unten + Memory
[[project-phase13-femur-zero-asymmetry]] + [[project-phase13-gait-launch-sim-time-default]].

## 4. Sub-Stages — Logik-Skizze + Tests

### E2.1 — Ein Bein, 3 Joints koordiniert

**Logik:**
- Aufgebockt, Plugin aus `real.launch.py` aktiv (alle Servos in pulse_zero
  = rad 0 = T-Pose: radial-out neutral, femur horizontal, tibia straight)
- Pro Bein einmal: 3-Joint-Trajectory mit 2 Waypoints publishen
  - Waypoint 1 (`t=2s`): `[coxa=0.0, femur=-0.3, tibia=+0.3]` —
    "Bein leicht angehoben" (femur dreht Bein nach oben, tibia gleicht aus)
  - Waypoint 2 (`t=4s`): `[0.0, 0.0, 0.0]` — zurück zu T-Pose
- JTC interpoliert kontinuierlich → glatte Bewegung
- ±0.3 rad ist weit innerhalb URDF-Limits (engste Range leg_3 tibia_upper=+1.185 rad)

**Begründung Werte-Wahl:**
- coxa=0: kein horizontales Schwenken, isoliert Femur+Tibia-Test
- femur=-0.3: nach Stage-C-Direction-Map sollte das das Bein nach oben
  (relativ zur Schwerkraft) bewegen — leg hängt aufgebockt, also "weiter
  weg vom Boden"
- tibia=+0.3: knickt das Bein leicht ein (Schenkel kürzer)
- 2 s pro Waypoint: langsam genug für Beobachtung, schnell genug für 6
  Beine in ~30 s gesamt

**Tests:**
- T1: Bein bewegt sich glatt von T-Pose in lifted-Pose und zurück
- T2: keine `safety_freeze`-Logs im Plugin
- T3: alle 3 Joints synchron — kein Joint hängt nach, kein Klick
- T4: visuell symmetrisch — Hin- und Zurück-Bewegung gleich glatt
- T5 (negativ): nicht in Stage E2.1, später in E2.5

**NICHT getestet in E2.1:** Multi-Bein-Sync, IK-Berechnung, Walking-Gait
(kommt in E2.2 / E2.3 / E2.4).

**Progress-Checkliste (kopiert in `phase_12_progress.md`):**
- [ ] E2.1.1 leg_1 — 3-Joint-Trajectory ✓
- [ ] E2.1.2 leg_2 — 3-Joint-Trajectory ✓
- [ ] E2.1.3 leg_3 — 3-Joint-Trajectory ✓
- [ ] E2.1.4 leg_4 — 3-Joint-Trajectory ✓
- [ ] E2.1.5 leg_5 — 3-Joint-Trajectory ✓
- [ ] E2.1.6 leg_6 — 3-Joint-Trajectory ✓
- [ ] E2.1.7 keine Plugin-Errors / safety_freeze über alle 6 Beine

### E2.2 — Tripod-Set (3 Beine simultan) heben/senken

**Logik:**
- Tripod-Sets: {leg_1, leg_3, leg_5} und {leg_2, leg_4, leg_6}
- Pro Set: 3× `ros2 topic pub --once` mit `&` parallel ausführen
- Bash `wait` synchronisiert ende
- JTC-Trajectory pro Bein identisch zu E2.1: 2 Waypoints

**Begründung:**
- Tripod-Sets sind die zwei Phasen-Gruppen des späteren Tripod-Gait
- Simultane Bewegung testet ob USB-CDC-Throughput 9 Joints gleichzeitig
  schafft (Plugin schreibt PWM in ~10ms-Frames an Servo2040)
- Wenn ein Bein bei E2.2 zickt obwohl es in E2.1 ging → Bus-Throughput
  oder Plugin-Concurrency

**Tests:**
- T1: alle 3 Beine starten **gleichzeitig** (innerhalb <100 ms Versatz visuell)
- T2: alle 3 enden gleichzeitig zurück in T-Pose
- T3: keine `safety_freeze`-Logs, keine `serial port`-Errors
- T4: kein einzelnes Bein-Latency-Verzug

**NICHT getestet in E2.2:** IK, gait_node, Stand-Pose-Math.

**Progress-Checkliste:**
- [ ] E2.2.1 Tripod-Set A (legs 1, 3, 5) — simultanes Heben+Senken ✓
- [ ] E2.2.2 Tripod-Set B (legs 2, 4, 6) — simultanes Heben+Senken ✓
- [ ] E2.2.3 Beide Sets ohne Plugin-Errors

### E2.3 — gait_node + sim_walk.yaml, Stand-Pose, kein cmd_vel

**Logik:**
- `ros2 launch hexapod_gait gait.launch.py params_file:=sim_walk.yaml`
- gait_node liest URDF, rechnet IK für Stand-Pose
  (`radial_distance=0.295`, `body_height=-0.070`)
- gait_node startet in `STATE_STANDING` (kein cmd_vel publisht)
- Tickt mit 50 Hz, schickt Stand-Pose-Trajectory an alle 6 leg_controllers
- Alle 6 Beine bewegen sich aus T-Pose (rad 0/0/0) in Stand-Pose
  (≈ leichte Kniebeuge mit body_height -7 cm)

**Begründung:**
- Erstmals IK im Spiel — verifiziert dass die rad-Targets aus IK
  innerhalb der Cal-Range bleiben (sim_walk.yaml ist sim-getestet, aber
  HW kann andere Toleranzen haben)
- Aufgebockt: Beine hängen, "Stand-Pose" ist also visuell die Beine in
  Knickposition in der Luft — kein Boden, kein Tragen
- Wenn ein Bein in Stand-Pose nicht erreichbar ist → IKError oder
  Servo-Anschlag-Klick → Cal-Doku Tab. 3.3 zu eng

**Tests:**
- T1: gait_node-Log: `Stage 0.6: parsed joint limits for 6 legs from robot_description`
- T2: gait_node-Log: `gait_node init: pattern=tripod, ..., body_height=-0.070 m, ..., step_length_max=0.035 m (linear_max=0.035 m/s)`
- T3: alle 6 Beine fahren simultan in Stand-Pose, **keine** asynchronen Beine
- T4: keine IKError-Logs in T2
- T5: keine safety_freeze-Logs in T1
- T6: 30 s in Stand-Pose ohne Drift, kein Bein zuckt periodisch

**NICHT getestet in E2.3:** Walking-Trajektorien (kein Swing/Stance),
cmd_vel-Clamping.

**Progress-Checkliste:**
- [ ] E2.3.1 gait_node startet ohne URDF-Parse-Error
- [ ] E2.3.2 `Stage 0.6: parsed joint limits for 6 legs` Log sichtbar
- [ ] E2.3.3 Alle 6 Beine in Stand-Pose simultan ohne IKError
- [ ] E2.3.4 30 s Stand-Pose stabil (kein periodisches Zucken)
- [ ] E2.3.5 Keine safety_freeze-Logs

### E2.4 — Walking aufgebockt mit cmd_vel 0.02 m/s

**Logik:**
- gait_node weiterhin aktiv aus E2.3
- T3: `ros2 topic pub --rate 10 /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'`
- gait_engine wechselt zu `STATE_WALKING`, generiert Tripod-Trajektorien
  (Bezier-Swing für 3 Beine, Stance-Push für die anderen 3, alternierend)
- Aufgebockt: "Walking" heißt Beine machen die Walking-Bewegung in der
  Luft — Swing-Phase hebt+schwingt+senkt, Stance-Phase zieht zurück

**Begründung:**
- 0.02 m/s = ~60% von linear_max (0.035 m/s), gute Sicherheits-Marge
- Tripod-Pattern sichtbar im Luftraum: 3 Beine "schwingen vor", 3 stehen
  (in der Luft fix), alternierend pro cycle_time/2 = 1s
- Wenn Walking sauber 30 s läuft → Gait-Engine + Cal + Mechanik passen
  zusammen

**Tests:**
- T1: visueller Tripod-Rhythmus erkennbar — 3 Beine schwingen, 3 ruhen,
  alternierend
- T2: gait_node-Log: weiterhin keine IKError, keine WARN
- T3: 30 s ohne Symptom (Bein-Zucken, Plugin-Errors)
- T4: Plugin-Logs (T1): keine `safety_freeze`-, keine `serial`-Errors
- T5: Body bewegt sich nicht weg (aufgebockt, festgehalten)

**Progress-Checkliste:**
- [ ] E2.4.1 cmd_vel x=0.02 wird angenommen, Walking startet
- [ ] E2.4.2 Tripod-Rhythmus sichtbar, alternierend
- [ ] E2.4.3 30 s ohne IKError, ohne safety_freeze
- [ ] E2.4.4 Strg+C-Stop führt zu STATE_STOPPING → STANDING (kein Crash)

### E2.5 — Tempo-Treppe 0.02 → 0.03 → 0.035 m/s

**Logik:**
- Stop cmd_vel-Publisher (Strg+C T3), neu mit `linear.x=0.03` starten
- 30 s beobachten, dann Strg+C, neu mit `linear.x=0.035` starten
- 0.035 m/s = linear_max, gait-engine sollte nicht clampen
  (oder genau am Limit)
- Wenn 0.035 sauber: optional 0.05 versuchen → erwarteter Clamp-Log
  in gait_node:
  `cmd_vel clamped: input (vx=0.050, ...) > max-leg-speed 0.035 m/s`

**Begründung:**
- Treppenweise hoch: bei welchem Tempo bricht's? Cal-Range-Edge-Test
- Diagnostik: wenn 0.02 OK aber 0.03 zickt → Servo-Latenz oder Cal-Range
  zu eng am oberen Tempo
- 0.05 als "Über-Limit": verifiziert dass gait_engine clamps statt
  IK-Crashes produziert

**Tests:**
- T1: 0.02 → 0.03 → 0.035: jeweils 30 s, jeweils sauber
- T2: optional 0.05: Clamp-WARN-Log sichtbar, Walking-Visual identisch
  zu 0.035
- T3: bei IKError-Event: Bein/Joint im Log notieren, das ist die nächste
  Stage-Pendenz
- T4: keine Servo-Bus-Errors über alle Tempo-Stufen

**NICHT getestet:** Sehr lange Sessions, Boden-Walking.

**Progress-Checkliste:**
- [ ] E2.5.1 cmd_vel x=0.03 — 30 s sauber
- [ ] E2.5.2 cmd_vel x=0.035 — 30 s sauber
- [ ] E2.5.3 (optional) cmd_vel x=0.05 — Clamp-WARN sichtbar, kein IKError
- [ ] E2.5.4 Falls IKError bei einem Tempo: Bein/Joint identifiziert

## 5. Kritische Betrachtung

### 5.1 Was kann katastrophal werden

**Worst-Case-Szenarien aufgebockt** (Roboter hängt frei, Beine in der Luft):

| Szenario | Wahrscheinlichkeit | Konsequenz | Mitigation |
|---|---|---|---|
| Bein↔Chassis-Kollision in Swing-Phase | mittel | Servo-Strom-Spike, evtl. Beschädigung Servo oder Bein | Aufgebockt: durch die Luft-Bewegung weniger kritisch als auf Boden. `sim_walk.yaml` ist envelope-getestet → IK respektiert Joint-Limits. Trotzdem: Augen drauf, Kill-Switch griffbereit. |
| Servo-Über-Strom bei blockiertem Joint | mittel | Servo wird heiß, evtl. dauerhaft beschädigt | Aufgebockt: Beine hängen frei, sollten nicht blockieren. Plugin-Stage-0.5 freeze bei PWM-OoR (kein direkter Strom-Schutz aber Cal-konform). Hardware-Limit: Servo-PSU sollte Strom-Limit haben. |
| Body-Sprung beim ersten Walking-Tick | gering | Robot wackelt am Aufbock-Halter, evtl. fällt vom Halter | Aufgebockt: Halter sollte stabil sein. Stand-Pose vor cmd_vel (E2.3 vor E2.4) gibt sanften Übergang. |
| Plugin-Crash / verlorener Joint-State | gering | Servos halten letzte Position (kein Aktiv-Stop) | Plugin hat keine Reaktion auf Crash — Kill-Switch ist Plan B. Strg+C im T1 stoppt Plugin-Knoten, Servos halten dann passiv. |
| Falsche direction in servo_mapping.yaml (Stage-C-Bug entwischt) | sehr gering | Bein bewegt sich in falsche Richtung → Kollision | Stage C hat alle 18 Pins verifiziert. Aber: bei E2.3 (erstmals alle 6 simultan) wird das nochmal indirekt geprüft. |
| Servo-Latenz > erwartet → JTC-Position-Error | gering | JTC abort-controller könnte den ganzen Bein-Controller deaktivieren | sim_walk.yaml-Werte sind langsam (cycle_time=2s), Latenz-Budget groß. |

### 5.2 Welche Sim-Annahmen halten bei HW evtl. nicht

| Annahme aus Sim | HW-Realität | Implikation |
|---|---|---|
| Servos reagieren instant auf JTC-Command | Servo-Latenz ~10-20 ms zwischen PWM-Update und Bewegung | Visuell kann ein Bein "nachhängen", aber sim_walk.yaml ist mit cycle_time=2s langsam genug, dass 20 ms unkritisch sind |
| Joint-Limits aus URDF sind exakt erreichbar | Mechanik hat ±2° Toleranz pro Servo-Mount | Sim-Werte sind auch noch mit 10% Safety-Margin in sim_walk.yaml — sollte ausreichen |
| Trägheit der Beine ist gering | Aufgebockt: Beine hängen → Schwerkraft + Massenträgheit beim Schwingen | gait-engine kompensiert nicht explizit für Inertia, könnte Position-Error verursachen — beobachten in E2.4 |
| Servo-Mount ist starr | Stick-Slip beim Halten gegen Schwerkraft möglich | Sichtbar als "Bein zittert" — kein Cal-Bug, sondern mechanische Toleranz |
| Plugin schreibt 60 Hz PWM-Frames | USB-CDC-Throughput-Limit bei 9 simultanen Joints unbekannt | E2.2 testet das explizit (Tripod-Set) — wenn Bus-Error: Plugin-Stage-evaluieren |

### 5.3 Safety-Layer-Übersicht (was schützt was)

```
Layer 1: gait_node (Software, ROS-Level)
  ↳ Stage 0.6 IK-Joint-Limit-Check
    → IKError, gait_node loggt + ruft /hexapod_safety_freeze-Service
  ↳ cmd_vel-Clamp (linear_max)
    → WARN-Log statt IK-Crash

Layer 2: hexapod_hardware-Plugin (Software, Plugin-Level)
  ↳ Stage 0.5 PWM-OoR-Detection
    → wenn rad → PWM außerhalb [pulse_min, pulse_max]: atomic<bool>
      safety_freeze=true, Plugin hält letztes good-PWM, ignoriert
      weitere Commands bis Service /hexapod_safety_reset
  ↳ Direction-Map aus servo_mapping.yaml (Stage C verifiziert)

Layer 3: Mensch (Hardware-Level)
  ↳ Kill-Switch am Servo-PSU
    → Strom weg, Servos lose, Beine fallen
    → IRREVERSIBEL: nach Kill-Switch muss Plugin neu starten + Cal
       neu geladen werden

Layer 4: Mechanik (Hardware-Level, passiv)
  ↳ URDF-Joint-Limits ↔ Cal-PWM-Range sind math-konsistent
    (Stage 0 fix + Stage D)
  ↳ Servo eigene mechanische Anschläge (HW-redundant zu Cal)
```

**Wann welcher Layer:**
- Layer 1+2 reagieren auf Software-Bugs (z.B. cmd_vel zu groß, Cal-Edge)
- Layer 3 reagiert auf alles was Layer 1+2 nicht abfängt (z.B. unerwartete
  mechanische Probleme, sichtbares Fehlverhalten ohne Log-Symptom)
- Layer 4 ist passiv: schützt vor reinen Soft-Bugs

### 5.4 Notfall-Stop-Reihenfolge

**Bei sichtbarem Problem (zuckendes Bein, asynchroner Schritt, ungewöhnliches Geräusch):**

1. **KILL-SWITCH am Servo-PSU** — Strom weg, Servos entlastet
   - Begründung: Strg+C im Terminal sendet evtl. noch einen letzten
     JTC-Tick raus bevor der Knoten stirbt
2. **Strg+C in T2** (gait_node) — stoppt Trajectory-Generation
3. **Strg+C in T1** (Plugin) — stoppt PWM-Output
4. Visual / Sound-Check am Roboter
5. Plugin-Logs (T1) auf `safety_freeze`-Trigger prüfen
6. gait_node-Logs (T2) auf IKError prüfen
7. **Erst nach Diagnose:** Strom wieder einschalten, Plugin neu starten

**Wichtig:** Nach Kill-Switch ist der Plugin-Zustand inkonsistent
(letzte commanded PWM ≠ aktuelle Servo-Position). Plugin neu starten
mit `real.launch.py`.

## 6. Risiken-Tabelle (gespiegelt aus E.4-E.5 Stage-E-Sim, HW-spezifisch ergänzt)

| Symptom | Wahrscheinliche Ursache | Aktion |
|---|---|---|
| Plugin-Init: `failed to open /dev/ttyACM0` | Servo2040 nicht angeschlossen oder Permissions fehlen | USB prüfen, evtl. `sudo usermod -a -G dialout $USER` (nach Logout/Login wirksam) |
| Plugin-Init: `safety_freeze triggered on activate` | Cal-Eintrag in servo_mapping.yaml mit `pulse_zero` außerhalb `[pulse_min, pulse_max]` | servo_mapping.yaml prüfen — Stage B+C committed values nicht versehentlich angefasst |
| E2.1: ein Bein bewegt sich nicht (kein Klick, kein Twitch) | JTC nicht aktiv für das Bein, oder Servo defekt | `ros2 control list_controllers` — alle 6 active? Wenn aktiv aber kein Bewegung: Servo-Verkabelung Bein N prüfen |
| E2.1: Bein zuckt heftig statt glatt zu bewegen | Servo-Strom unterdimensioniert oder Latenz-Problem | Servo-PSU-Spannung prüfen (sollte 7.4V nom 2S-LiPo oder Bench-PSU); Test mit langsamerer Trajectory (time_from_start=4s statt 2s) |
| E2.2: Tripod-Set asynchron, ein Bein hängt nach | USB-CDC-Throughput-Limit oder Plugin-Concurrency | Plugin-Logs auf `serial write timeout` prüfen, ggf. Trajectory-Rate reduzieren |
| E2.3: ein Bein erreicht Stand-Pose nicht | Cal-Range zu eng für IK-Result, oder mechanischer Anschlag | gait_node-Log auf IKError + Bein/Joint, in Cal-Doku Tab. 3.3 prüfen ob Limit gemessen wurde oder geschätzt |
| E2.3: gait_node-Log `Stage 0.6: ... 0 legs from robot_description` | robot_description-Param leer | gait.launch.py wurde ohne `robot_description_file:=...` gestartet ODER xacro-Pfad falsch |
| E2.4: Walking sieht ruckelig, nicht glatt | Servo-Latenz, Cycle_time zu kurz für HW | gait_node `cycle_time` per rqt_reconfigure auf 3.0 setzen, beobachten |
| E2.4: ein Bein in Swing fällt aus Tripod-Sync | Bein-spezifisches IK-Problem oder Servo-Latenz | gait_node-Log auf IKError für das Bein, Bein-Index merken |
| E2.5: 0.035 m/s zickt, 0.02 OK | Cal-Range zu eng am oberen Bewegungsbereich | sim_walk.yaml mit weniger linear_max neu generieren via walking_envelope_check.py recommend |
| Plugin-Logs `safety_freeze` mitten in E2.4/E2.5 | Cal-Bug für ein spezifisches Bein (PWM rutscht außerhalb) | T1-Log: welcher Pin? `pin_<N>.pulse_min/max` in rqt_reconfigure prüfen — möglich dass Stage B-Wert für einen Pin off ist |

## 7. Erfolgs-Kriterien — Stage E2 DONE

| # | Kriterium |
|---|---|
| 1 | E2.1: alle 6 Beine bewegen sich koordiniert (3 Joints) in lifted-Pose und zurück, keine Plugin-Errors |
| 2 | E2.2: beide Tripod-Sets bewegen sich simultan ohne USB-Bus-Errors |
| 3 | E2.3: gait_node parst URDF, alle 6 Beine in Stand-Pose, 30 s stabil ohne IKError |
| 4 | E2.4: Walking mit cmd_vel x=0.02 läuft 30 s ohne Symptom, Tripod-Rhythmus sichtbar |
| 5 | E2.5: cmd_vel x=0.03 und x=0.035 laufen 30 s ohne IKError (oder, falls IKError bei einem Tempo: Bein/Joint dokumentiert) |
| 6 | Sauberes Beenden ohne zombie-Prozesse, Servos halten letzte Position |
| 7 | Self-Review-Tabelle ohne 🔴-Punkte (🟡/🟢 erlaubt, dokumentiert) |

## 8. Was passiert wenn alles grün

- `servo_real_cal_plan.md` Stage E2 → ✅ 2026-05-25
- Memory `project_servo_real_cal_done.md` anlegen (cross-phase-thread fertig)
- Phase 13 (Voll-Bringup) kann starten
- §13 dieser Plan-Doku + die zwei Phase-13-Pendenz-Memories werden die nächste Plan-Grundlage

## 9. Was passiert wenn Probleme

- **Wenn einzelnes Bein zickt in E2.1:** Bein-spezifische Cal-Re-Messung
  (Stage B-Werte für diesen Pin nochmal), evtl. neue Stage F nach E2
- **Wenn IKError bei sim_walk.yaml-Werten in E2.3:** sim_walk.yaml war
  Sim-optimal, HW braucht konservativere Werte → walking_envelope_check.py
  mit kleinerem `--safety-margin` neu generieren, oder `defensive_walk.yaml`
  als Fallback
- **Wenn USB-Bus-Errors in E2.2:** Plugin-Concurrency-Bug — Phase-13-Pendenz,
  Stage E2 trotzdem abschließbar wenn E2.3+ einzeln laufen
- **Wenn safety_freeze unerwartet triggert:** Plugin-Log T1 zeigt Pin →
  Stage B/C-Re-Verify für diesen Pin

## 10. Beobachtungs-Notizen (während Live-Tests)

User soll während E2.4-E2.5 dokumentieren:
- **Walking-Visual:** glatt / ruckelig / asynchron?
- **Servo-Akustik:** ruhig / klickt / brummt / Strom-Stutter?
- **Body-Bewegung:** stabil am Aufbock-Halter / wackelt / springt?
- **Bein-Identifikation:** welches Bein zickt zuerst falls was zickt?
- **Tempo-Edge:** bei welchem cmd_vel kommt das erste Symptom?

Diese Notizen sind Input für Phase 13 (Voll-Bringup) und evtl. Cal-Doku-
Update.

## 11. Offene Punkte für User-Review

Bereits geklärt (Session vor Phase 1):
- **Q1** Single-Joint-Roundtrip gestrichen — Servos liefern kein
  Positions-Feedback, Test wäre Software-Loopback ohne Mehrwert
- **Q2** sim_walk.yaml als Preset für E2.3+
- **Q3** Tempo-Treppe 0.02 → 0.03 → 0.035 m/s
- **Q4** Notfall-Stop = Kill-Switch first, dann Strg+C T2 (gait_node) + T1 (Plugin)
- **Q5** Reihenfolge E2.1 → E2.2 → E2.3 → E2.4 → E2.5 (Komplexitäts-Stufung,
  isolierte Diagnose pro Schritt)

Keine weiteren Punkte vor Code-/Test-Beginn. Direkt nach User-Freigabe
geht es in Phase 3 (Live-HW-Tests).

---

## 12. Self-Review nach Stage E2 (2026-05-25)

| Punkt | Status | Detail |
|---|---|---|
| E2.1 — 6 Beine je 3 Joints koordiniert | OK | Alle 6 Beine bewegen sich glatt, RViz↔HW sync |
| E2.2 — Tripod-Sets simultan | OK | Beide Sets (1+3+5, 2+4+6) simultan ohne Bus-Errors |
| E2.3 — Stand-Pose alle 6 Beine | OK | gait_node fährt alle 6 in Stand-Pose, 30 s stabil, kein IKError, kein safety_freeze |
| E2.4 — Walking cmd_vel 0.02 m/s | OK | Tripod-Walking-Rhythmus visuell sichtbar, 30 s sauber |
| E2.5 — Tempo-Treppe 0.02 → 0.03 → 0.035 | OK | Alle 3 Tempos ohne IKError. Bei 0.04 m/s greift Clamp-WARN korrekt (linear_max=0.035) |
| Sauber Beenden | OK | Strg+C in T3/T2/T1, keine zombie-Prozesse |
| **`use_sim_time=true` Default in gait.launch.py blockt rclpy-Timer auf HW** | 🔴 → ✅ FIXED 2026-05-25 | Stage E2.3 erstmalig sichtbar, da Sim mit Gazebo `/clock` nicht betroffen war. **Fix:** Test-Commands.md fordert jetzt explizit `use_sim_time:=false`. Launch-File Default unverändert gelassen, um Sim nicht zu brechen — Phase-13-Pendenz prüfen ob bessere Default-Wahl + getrennte sim/real-Launch-Args sinnvoll sind. |
| **Femur rechts (legs 1/2/3) vs links (4/5/6) Asymmetrie ~5°** | 🟡 Phase-13-Pendenz | pulse_zero rechts Ø 1485 µs, links Ø 1543 µs → ~5° Offset bei "0 rad" → IK-Stand-Pose macht rechts stärker eingeknickt visuell. Walking funktioniert aufgebockt, keine IKError. Optionen + Vorgehen: siehe §13. |
| RViz↔HW visueller Sync | OK | E2.1 und E2.2 bestätigt — Plugin-Echo `/joint_states` reflektiert URDF-Konvention 1:1 |
| Stage-0.5/0.6-Safety im Live-Walking | OK | Über alle E2-Sub-Stages keine `safety_freeze`, keine `IKError`-Trigger. Layer-1/2/4 unauffällig — Layer-3 (Kill-Switch) nicht aktiviert nötig. |

**Resultat:** Stage E2 ✅ DONE. Cross-Phase-Thread "servo_real_cal" komplett.

## 13. Offene Phase-13-Pendenz aus Stage E2

### 13.1 Femur-Asymmetrie rechts/links (~5°)

**Beobachtung Stage E2.3 (2026-05-25):**
Beim gait_node-Stand-Pose-Kommando (radial=0.295, body_height=-0.07) sind
die Femur-Joints der rechten Beine (1, 2, 3) sichtbar stärker eingeknickt
als die der linken Beine (4, 5, 6).

**Daten aus `servo_mapping.yaml`:**

| Bein | Seite | pulse_zero (µs) | direction |
|---|---|---|---|
| leg_1 | rechts | 1460 | +1 |
| leg_2 | rechts | 1550 | +1 |
| leg_3 | rechts | 1445 | +1 |
| **Ø rechts** | | **1485** | |
| leg_4 | links | 1560 | -1 |
| leg_5 | links | 1530 | -1 |
| leg_6 | links | 1540 | -1 |
| **Ø links** | | **1543** | |
| **Δ Seiten** | | **~58 µs ≈ 5°** | |

**Mechanismus:** Stage-B-Cal hat pulse_zero per Auge auf "horizontal"
getrimmt — das hat einen ±2-3°-Fehler eingeführt, der sich beim
Mitteln über die Seite auf ~5° Offset summiert. IK rechnet symmetrisch,
also landen die echten Joint-Winkel pro Seite mit konstantem Offset
versetzt.

**Warum Stage C das nicht aufgedeckt hat:** Stage C testete nur die
**Richtung** (binär — bewegt sich Servo in gleiche Richtung wie RViz?).
Absolute pulse_zero-Genauigkeit wurde nicht geprüft.

**Status:** Walking aufgebockt funktioniert ohne IKError/safety_freeze,
also kein E2-Blocker. Beim Boden-Walking (zukünftige Phase) könnte die
Asymmetrie zu Body-Tilt führen.

**Optionen zur Behebung (Phase 13 oder neue Stage F vor Boden-Walking):**

| Option | Aufwand | Vorgehen | Wann sinnvoll |
|---|---|---|---|
| **A) Akzeptieren** | 0 min | Asymmetrie in Cal-Doku notieren, beobachten ob Boden-Walking betroffen ist | Wenn Reibung + Schwerkraft beim Boden-Walking den Body ausrichten und 5° tolerierbar sind |
| **B) pulse_zero rechts vs. links re-cal** | 30–60 min | Pro Femur visuell exakt auf "horizontal" trimmen (Wasserwaage am Femur-Segment), pulse_zero via `ros2 param set /hexapodsystem pin_<N>.pulse_zero <µs>` + `/save_calibration` persistieren | Wenn Boden-Walking als nächste Phase ansteht. Direkter Cal-Fix ohne Code/URDF-Änderung |
| **C) URDF `mount_offset` pro Bein** | 1–2 h | URDF-Param `femur_zero_offset` pro Bein einführen, in Xacro-Macro + IK-Pipeline propagieren | Wenn Mechanik selbst asymmetrisch ist (Servo-Schraubenposition o.ä.) und die Cal-Werte sauber sein sollen |

**Empfehlung:** Option A für jetzt → bei erster Boden-Walking-Stage
beobachten → wenn Tilt sichtbar, Option B (einfacher Fix mit
bestehenden Tools).

→ Memory-Eintrag: `project_phase13_femur_zero_asymmetry.md`

### 13.2 gait.launch.py `use_sim_time`-Default

Stage E2 hat aufgedeckt, dass `default_value='true'` für `use_sim_time`
auf HW zur stillen Timer-Blockade führt. Aktueller Workaround: explizit
`use_sim_time:=false` auf HW. Bessere Lösung für Phase 13:
- Entweder Default auf `false` und Stage-E-Sim-Docs explizit `true`
  passen lassen
- Oder getrennte `gait_sim.launch.py` / `gait_real.launch.py` mit
  korrektem Default pro Variante
- Oder hexapod_bringup `real.launch.py` includet gait-Launch mit
  korrektem Flag

→ Memory-Eintrag: `project_phase13_gait_launch_sim_time_default.md`

---

**Stage E2 ✅ abgeschlossen 2026-05-25. Cross-Phase-Thread
"servo_real_cal" komplett.** Operative Anleitung weiterhin in
[`servo_real_cal_stage_e2_hw_test_commands.md`](servo_real_cal_stage_e2_hw_test_commands.md).
