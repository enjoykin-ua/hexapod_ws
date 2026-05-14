# Phase 10 — Single-Leg Bring-up + Kalibrierung

**Dauer-Schätzung:** 2–3 Tage (mechanische Endlagen + Per-Servo-Kalibrierung
sind handarbeit-lastig)
**Maschine:** Desktop (Servo2040 weiter am Desktop, Pi noch nicht im Spiel)
**Vorbedingung:** Phase 9 abgeschlossen (`hexapod_hardware` läuft am
Desktop), Phase 8 abgeschlossen (Bench-Strom steht)
**Roboter-Status:** **aufgebockt** — Beine in der Luft, kein Bodenkontakt

---

## Ziel

Erstmaliger Anschluss echter Hexapod-Servos. Wir gehen **bewusst**
schrittweise vor: erst alle Beine mechanisch durchschwenken, dann ein
einziges Bein elektrisch anschließen und kalibrieren, dann erst die
restlichen. Am Ende sind alle 6 Beine kalibriert in `servo_mapping.yaml`,
können einzeln über JTC-Trajectories angesteuert werden, und in **RViz
parallel** zur echten Bewegung visualisiert.

> **Wichtig (Erinnerung):** die Servos liefern **kein** Position-Feedback.
> Was in RViz angezeigt wird, ist die Echo-State-Reflexion des zuletzt
> gesendeten Sollwerts, **nicht** die echt gemessene Servo-Position. Die
> visuelle Beobachtung des realen Roboters bleibt die einzige Quelle der
> Wahrheit für „macht der Servo wirklich was er soll".

---

## Hardware-Setup für diese Phase

- Aus Phase 8: kompletter Bench-Aufbau (PSU, DCDC, Bulk-Caps, GND-Stern)
- Aus Phase 7/9: Servo2040 mit Firmware + `hexapod_hardware`-Plugin
- Roboter-Body **mechanisch komplett** (alle 6 Beine montiert), aber
  aufgebockt
- Servo-Kabel pro Bein, sortiert nach Joint
- Winkelmesser oder Foto-Referenz für Kalibrierungs-Verifikation
- Lab-PSU CC-Limit: pro Bein zunächst 2 A, schrittweise mehr
- Kill-Switch griffbereit (PSU-Aus-Knopf)

---

## Sicherheits-Recap (CLAUDE.md §9)

- **Aufgebockt** — Beine in der Luft, **kein** Bodenkontakt
- Hand am PSU-Aus-Knopf
- Reduzierte Velocity/Acceleration-Limits aus `controllers.real.yaml`
- Bei unerwartetem Verhalten **erst Strom aus, dann analysieren**
- Mechanische End-Stop-Prüfung **stromlos** vor dem ersten Power-On

---

## Done-Kriterien

1. Mechanische Endlagen aller 6 Beine händisch dokumentiert (Stufe A)
2. Bein 1 elektrisch angeschlossen, kalibriert, Stand-Pose mit < 5°
   Abweichung pro Joint (Stufe B)
3. RViz zeigt Bein 1 synchron zur echten Bewegung (Stufe C)
4. Strom-Profil von Bein 1 unter typischen Bewegungen dokumentiert (Stufe D)
5. Beine 2–6 analog kalibriert, alle Einträge in `servo_mapping.yaml`
   (Stufe E)
6. Test: alle 6 Beine fahren aufgebockt synchron Stand-Pose ohne Stalls
   (Stufe F)
7. Cable-Management ordentlich, keine Knick-/Klemmstellen (Stufe F)
8. Phase-Doku-Abschluss (Stufe G)

---

## Stufen

### Stufe A — Mechanische End-Stop-Prüfung (alle Beine, stromlos)

**Ziel:** Bevor irgendein Servo bestromt wird: per Hand jedes Bein komplett
durchschwenken. Wo schlägt das Bein gegen den Body oder gegen ein anderes
Bein an?

#### A.1 Pro Bein durchgehen

Für jedes Bein `leg_1` … `leg_6`:
1. Bein per Hand durch alle drei Joints schwenken (coxa, femur, tibia)
2. Winkel der harten mechanischen Anschläge mit Winkelmesser ermitteln
3. Vergleichen mit URDF-Limits aus `00_conventions.md` §11.4:
   - Coxa: ±1,57 rad (geplant)
   - Femur: ±1,57 rad
   - Tibia: ±1,50 rad
4. **Wenn der mechanische Anschlag enger ist als das URDF-Limit:** den
   engeren Wert für die Hard-Clamp in `servo_mapping.yaml` als
   `pulse_min/pulse_max` eintragen, damit die Firmware den engeren Wert
   durchsetzt.

#### A.2 Mittelbein-Spezifikum

Die mittleren Beine (leg_2, leg_5) sind an `body_width_middle = 0,170 m`
montiert, mit Yaw = ±π/2. Sie haben möglicherweise andere
Kollisionsgrenzen als die schrägen Beine (leg_1/3/4/6).

#### A.3 Dokumentation

In `phase_10_progress.md`:

```
leg_1:
  coxa:  mech ±1.55 rad (eng vs. URDF ±1.57)
  femur: mech ±1.50 rad (eng vs. URDF ±1.57)
  tibia: mech +1.40 / -1.30 rad (asymmetrisch!)
...
```

**Done-Kriterium A:**
1. Alle 6 Beine händisch durchgeschwenkt
2. Tabelle mit mechanischen Endlagen pro Joint
3. Engere Werte als URDF-Limit in `servo_mapping.yaml` als
   `pulse_min/pulse_max` eingetragen

---

### Stufe B — Bein 1 elektrisch anschließen + kalibrieren

**Ziel:** Erstes Bein elektrisch verbinden, drei Servos kalibrieren, Stand-
Pose anfahren können.

#### B.1 Anschluss

- PSU **aus**, Hauptschalter (= PSU-Knopf) aus
- 3 Servo-Kabel von Bein 1 (Coxa, Femur, Tibia) an Servo2040-Outputs
  gemäß Mapping anschließen
- PSU auf 7,4 V, CC-Limit **2 A**
- Servo-Mapping in `servo_mapping.yaml` für Bein 1 als „aktiv" markieren
  (Beine 2–6 vorerst auskommentiert oder mit disabled-Flag)

#### B.2 Per-Servo-Kalibrierung

**Pro Joint** (Coxa, Femur, Tibia) in dieser Reihenfolge:

1. Joint-Sollwert in JTC = 0,0 rad anfahren
2. **Beobachten:** wo steht der Servo wirklich?
3. **Erwartet:** das Bein steht in der „Null-Pose" aus URDF (Coxa
   geradeaus, Femur horizontal, Tibia gerade)
4. **Wenn Abweichung:** `pulse_zero[i]` in YAML so anpassen, dass
   Joint=0 dem URDF-Bild entspricht
5. Joint-Sollwert auf +π/4 rad anfahren
6. **Beobachten:** dreht der Servo um genau 45°?
7. **Wenn nicht:** `pulse_per_rad[i]` justieren
8. **Wenn falsche Drehrichtung:** `direction[i]` flippen (±1)
9. Joint-Sollwert auf -π/4 rad anfahren → Symmetrie-Test
10. Iteration bis Abweichung < 5°

**Konkrete Vorgehensweise per Tool:**

```bash
# Terminal A: real.launch.py mit Bein 1 aktiv
ros2 launch hexapod_bringup real.launch.py loopback:=false

# Terminal B: Punkt-Trajectory an Bein 1 Coxa
ros2 topic pub --once /leg_1_controller/joint_trajectory \
  trajectory_msgs/JointTrajectory '{joint_names: [leg_1_coxa_joint, leg_1_femur_joint, leg_1_tibia_joint], points: [{positions: [0.0, 0.0, 0.0], time_from_start: {sec: 2}}]}'
```

YAML editieren → `colcon build --packages-select hexapod_hardware` → neu
starten → erneut testen. Iterativ.

> **Tipp:** ein kleines Python-Skript `tools/calibrate_leg.py` im
> `hexapod_hardware`-Paket kann den iterativen Loop angenehmer machen
> (Sollwert eingeben, sehen, YAML-Wert vorschlagen).

#### B.3 Strom-Profil

Während der Kalibrierung das `effort`-State-Interface (= Strommessung) per
`ros2 topic echo /joint_states` mit `--field effort` loggen. Plausibilitäts-
Check:
- Statisch in Stand-Pose: pro Servo wenige hundert mA
- Während Bewegung: Spitzen bis ~1 A bei kleinen Servos
- **Kein Servo erreicht > 80 % Datenblatt-Stallstrom**

**CSV-Logging für spätere Analyse:** der `effort`-Topic-Echo zeigt aktuelle Werte
flüchtig. Für Plot/Analyse später nutzt man `~/hexapod_servo_driver/tools/log_state.py`
(aus Phase 7). Das Skript pollt das Servo2040 direkt mit 20 Hz via USB-CDC und
schreibt eine CSV: pro Sample 1 Zeile mit `t_s, voltage_mv, current_ma (Rail-Total),
flags, p0..p17 (alle 18 Pulse-Werte)`. Wichtig zu wissen: die `current_ma`-Spalte ist
**Gesamt-Rail-Strom**, kein per-Servo-Wert (Servo2040-HW hat nur einen Shunt).

```bash
# Terminal A — Logger startet vor der Kalibrierung, läuft parallel:
python3 ~/hexapod_servo_driver/tools/log_state.py --out leg1_cal_$(date +%Y%m%dT%H%M).csv

# Terminal B — Kalibrierungs-Jog wie oben in B.2 beschrieben
ros2 launch hexapod_bringup real.launch.py
# ... Sollwerte ändern, Servo bewegt sich ...

# Wenn fertig: Ctrl-C im Logger-Terminal → CSV liegt bereit
# Auswertung z.B. in Python:
#   import pandas as pd
#   df = pd.read_csv("leg1_cal_...csv")
#   df.plot(x="t_s", y=["p0", "p1", "p2", "current_ma"])
```

Nutzen: man sieht die zeitliche Korrelation Pulse-Sollwert ↔ Rail-Strom-Antwort
und kann die Soft-Ramp-Rate empirisch verifizieren (sollte ≤ 2000 µs/s entsprechend
`cfg::MAX_DELTA_PULSE_PER_TICK_US`).

**Done-Kriterium B:**
1. Bein 1 fährt Joint=0 → URDF-Null-Pose mit < 5° Abweichung
2. Bein 1 fährt ±π/4 mit korrekter Drehrichtung und korrektem Winkel
3. `servo_mapping.yaml` für Bein 1 vollständig eingetragen
4. Strom-Profil dokumentiert, keine Stalls

---

### Stufe C — RViz + Real synchron beobachten

**Ziel:** RViz-Visualisierung läuft parallel zur echten Bewegung. Beine
in der Sim-Welt = Beine in echt.

> **Erinnerung:** RViz zeigt die Echo-State-Reflexion (= „was hat der
> Stack gesendet"), **nicht** echte Servo-Positionen. Visuell gleicher
> Stand bedeutet: der Stack glaubt der Servo ist da. Ob er es wirklich
> ist, sieht man **nur** am echten Roboter.

#### C.1 Launch-Konfiguration

```bash
ros2 launch hexapod_bringup real.launch.py loopback:=false rviz:=true
```

`real.launch.py` bekommt optional `rviz:=true|false`. RViz-Config aus
`hexapod_bringup` wiederverwenden (gleiche wie `sim.launch.py`).

#### C.2 Synchron-Test

- JTC-Trajectory an Bein 1 senden (z. B. Coxa von 0 → +π/4)
- **In RViz**: Bein 1 bewegt sich
- **Am echten Roboter**: Bein 1 bewegt sich gleichzeitig
- **Visuell vergleichen**: Endpose stimmt überein

**Done-Kriterium C:**
1. RViz zeigt aktuelle Joint-Positionen (aus `/joint_states`)
2. Synchron zur echten Bewegung sichtbar

---

### Stufe D — Bewegungs-Tests mit Bein 1

**Ziel:** Bein 1 in komplexeren Bewegungen testen. Ziel ist herauszufinden
ob die Per-Servo-Kalibrierung auch in dynamischen Trajektorien hält.

#### D.1 Stand-Pose-Anflug

`stand_node` (aus Phase 5) angepasst für nur Bein 1 — oder manuell eine
Trajectory zur Stand-Pose.

Beobachten:
- Bewegung sanft, kein Sprung
- Soft-Ramp wirkt (Servo2040-Ebene)
- Endpose visuell passend zur erwarteten Stand-Pose

#### D.2 Schwing-Trajectory

Ein einfaches „Bein hebt und setzt wieder ab" als JointTrajectory mit
3–4 Punkten. Manuell publizieren oder Python-Skript.

#### D.3 cmd_vel-Test mit nur Bein 1

`gait_node` läuft, aber nur Bein 1 ist elektrisch verbunden. Andere
Controller würden zwar PWM-Frames generieren, aber an nicht-angeschlossenen
Servo2040-Outputs landen die ins Leere.

`cmd_vel.linear.x = 0,02` → Tripod-Pattern: in einem von zwei A/B-Tripods
ist Bein 1. Beobachten ob Bein 1 in der erwarteten Phase schwingt.

**Done-Kriterium D:**
1. Stand-Pose-Anflug sauber
2. Schwing-Trajectory sauber
3. Tripod-Pattern erkennbar synchron zur Sim

---

### Stufe E — Beine 2–6 analog kalibrieren

Wiederholung von Stufe B für jedes weitere Bein.

#### E.1 Schritt-für-Schritt

- Bein 2 elektrisch dazu, PSU-CC auf 3 A erhöhen
- Stufe-B-Prozess für Bein 2 durchgehen
- YAML committen, Stand-Pose-Test mit Beinen 1+2
- Bein 3 dazu, CC auf 4 A
- ...
- Bein 6 dazu, CC auf 7 A (alle 6 Beine bestromt)

#### E.2 Direction-Vorzeichen prüfen

Symmetrische Beine drehen mechanisch spiegelverkehrt. `direction`-Tabelle
sollte am Ende dieses Muster zeigen:

| Bein | Coxa direction | Femur direction | Tibia direction |
|---|---|---|---|
| leg_1 (vorne rechts) | +1 oder -1 | +1 oder -1 | +1 oder -1 |
| leg_2 (mitte rechts) | ... | ... | ... |
| leg_3 (hinten rechts) | ... | ... | ... |
| leg_4 (hinten links) | spiegelverkehrt zu leg_3 | ... | ... |
| leg_5 (mitte links) | spiegelverkehrt zu leg_2 | ... | ... |
| leg_6 (vorne links) | spiegelverkehrt zu leg_1 | ... | ... |

Konkrete Werte werden empirisch eingetragen.

**Done-Kriterium E:**
1. Alle 6 Beine kalibriert in `servo_mapping.yaml`
2. Symmetrie-Pattern in `direction` plausibel
3. Stand-Pose für alle 6 Beine aufgebockt: Body visuell symmetrisch

---

### Stufe F — Full-Pose-Test + Cable-Management

#### F.1 Stand-Pose alle 6

Alle 6 Beine in Stand-Pose, **aufgebockt**. 5 min halten.

Beobachten:
- Strom-Mittelwert pro Servo loggen
- Temperatur der Servo-Gehäuse mit Hand fühlen (oder IR-Thermometer)
- Kein Servo wird heiß über ~40 °C (ohne Last)

#### F.2 Cable-Management

- 18 Servokabel durch definierte Kanäle führen
- Spiralkabelschlauch oder Kabelbinder
- Wo Kabel über Gelenke laufen: Mindest-Biegeradius respektieren, kein
  Knick bei Endlagen
- Kabel nicht über bewegliche Teile schleifen lassen

**Done-Kriterium F:**
1. Stand-Pose 5 min stabil
2. Servo-Temperaturen < 40 °C nach 5 min Stand (ohne Last)
3. Cable-Management ordentlich, keine Klemm- oder Scheuerstellen

---

### Stufe G — Phase-10-Abschluss

- `phase_10_progress.md` finalisieren:
  - Kalibrierungs-Tabelle (Pulse-zero, Pulse-per-rad, Direction pro Joint)
  - Mechanische Endlagen-Tabelle
  - Strom-Profile pro Bewegungstyp
  - Foto des aufgebockten Roboters in Stand-Pose
- `servo_mapping.yaml` final committed
- `00_conventions.md` ergänzen: Per-Servo-Kalibrierungs-Methode
  (Phase-10-Stufe-B-Verfahren)
- Git-Commit + Tag `phase-10-done`
- `PHASE.md` auf Phase 11 aktualisieren

---

## Stolperfallen

| Symptom | Ursache | Fix |
|---|---|---|
| Servo dreht in falsche Richtung | `direction` (±1) im Mapping falsch | YAML korrigieren, neu builden |
| Servo erreicht andere Endlage als URDF | `pulse_per_rad` falsch | YAML korrigieren, Symmetrie-Test |
| Bein schlägt gegen Body | URDF-Limit zu weit, mechanisch enger | `pulse_min/max` in YAML enger setzen |
| Servo zittert in Stand-Pose | Digital-Servo kompensiert minimale Abweichung | Akzeptieren (typisch für Hobby-Digital-Servos) oder `goal_time` lockerer |
| Servo wird heiß ohne Bewegung | Mechanische Verspannung oder Servo arbeitet gegen sich selbst | Kalibrierung prüfen, Bein händisch in Pose, schauen ob Servo entspannt |
| Strom-Limit triggert ohne Last | `STALL_THRESHOLD_MA` zu eng eingestellt | In Firmware (Phase 7) Schwelle pro Servo-Typ hochsetzen |
| Stand-Pose visuell schief | ein oder mehrere Beine falsch kalibriert | pro Bein einzeln verifizieren, asymmetrische Beine sind verdächtig |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Walken auf dem Boden (Phase 12)
- Kein Pi (Phase 11)
- Keine PS4-Vollbetrieb-Tests (Phase 12)
- Kein Akku (Phase 13+)
- Keine `enable_foot_contact:=false`-Umstellung (kommt in Phase 12)

---

## Phasenabschluss-Checkliste

- [ ] Alle Stufen A–F Done-Kriterien erfüllt
- [ ] Mechanische Endlagen-Tabelle in Doku
- [ ] `servo_mapping.yaml` final mit allen 18 Joint-Einträgen
- [ ] Stand-Pose visuell symmetrisch
- [ ] Strom-Profile dokumentiert
- [ ] Cable-Management abgeschlossen
- [ ] `00_conventions.md` ergänzt
- [ ] Git-Commit + Tag `phase-10-done`
- [ ] `PHASE.md` auf Phase 11 aktualisiert
- [ ] Retrospektive in `phase_10_progress.md`
