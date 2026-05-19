# Phase 10 — Single-Leg Bring-up + Kalibrierung

**Dauer-Schätzung:** ~5 Tage (Stages A–I, mit Stage F als 1.5-d-Wildcard für IK + gait_node Voll-Pipeline-Test)
**Maschine:** Desktop (Servo2040 + 1 Bein am Desktop, Pi noch nicht im Spiel)
**Vorbedingung:** Phase 9 abgeschlossen (`hexapod_hardware`-Plugin läuft real
gegen Servo2040 über USB-CDC), Hexapod aufgebockt an Stock-Halterung,
leg_6 mit allen 3 Servos mechanisch montiert, alle Servos aktuell
**abgeklemmt**, HJ Digital Servo/ESC Consistency Tester verfügbar (eigenes
Netzteil, Signal-Range 800–2200 µs).
**Roboter-Status:** **aufgebockt** an Stock-Halterung — alle Beine hängen
frei nach unten, kein Bodenkontakt, Selbst-Beschädigungs-Risiko begrenzt
auf bein-eigene Mechanik.

> **Hinweis zum vorherigen Plan-Entwurf vom 2026-05-14:** Eine frühere
> Skizze dieser Datei plante alle 6 Beine kalibrieren in Phase 10 mit
> `pulse_per_rad`-Schema. Beides wurde verworfen: Phase 9 hat
> `pulse_per_rad` zugunsten eines 3-Punkt-Schemas
> (`pulse_min`/`pulse_zero`/`pulse_max`) ersetzt, und User-Entscheidung
> 2026-05-16 reduziert Phase 10 auf leg_6 (single-leg-Bring-up).
> Die anderen 5 Beine + 15 Servos kommen in Phase 13 (Voll-Bringup).

---

## Ziel

**Erste echte Servo-Bewegung am Hexapod.** Phase 10 schließt die Lücke
zwischen Phase 9 (Plugin spricht mit Servo2040-Firmware, aber ohne Hexapod-
Servos) und Phase 13 (Voll-Bringup mit allen 6 Beinen). Konkret:

1. **Drei Servos** des Beines **leg_6** (vorne-links, Pin 15/16/17) werden:
   - mit dem HJ-Tester pre-kalibriert (mechanische Mitte, sicherer Endlagen-Bereich)
   - dann am Servo2040 in `servo_mapping.yaml` final kalibriert (mit `direction`)
   - als 3-Servo-Bein per JointTrajectoryController koordiniert bewegt
   - mit einer einfachen IK-Trajectory aus Phase 5 gefahren
2. **Velocity- und Acceleration-Limits** in `controllers.real.yaml` werden mit
   Bench-Daten aus Stage F gemessen und eingetragen
   (Memory-Pendenz `project_phase10_real_yaml_vel_limits.md`).
3. **`servo_mapping.yaml` für leg_6** geht von `status: placeholder` auf
   `status: calibrated` mit ISO-Timestamp. Die anderen 15 Servos
   (leg_1..5) bleiben Platzhalter — Phase 13 macht die voll-Kalibrierung
   wenn alle Beine montiert + verkabelt sind.

> **Echo-State-Erinnerung:** Die Servos liefern **kein** echtes Position-Feedback.
> Was in RViz angezeigt wird, ist die Reflexion des zuletzt gesendeten
> Sollwerts (in Radiant rückkonvertiert) — **nicht** die echt gemessene
> Servo-Position. Die visuelle Beobachtung des realen Roboters bleibt die
> einzige Quelle der Wahrheit für „macht der Servo wirklich was er soll".

**Was Phase 10 NICHT macht:**

- Keine 6-Bein-Koordination (Phase 13).
- Kein Gait-Engine am echten Roboter (Phase 13).
- Kein Pi (Phase 12).
- Kein Akku-Betrieb — Phase 10 läuft ausschließlich mit Bench-PSU.
- Keine Cable-Management-Endmontage (Phase 13 wenn alle 18 Servos angeschlossen sind).
- Keine Oszi/Logic-Analyzer-Tests (User-Entscheidung 2026-05-16: aus
  Phase-9-Pendenz nicht in Phase 10 nachgeholt). Memory-Eintrag
  `project_phase9_h_oscilloscope_pending.md` bleibt Cross-Session-Pendenz.

---

## Architektur-Entscheidungen

### A. Hybride Tester-First-Kalibrierungs-Methodik (kompakt: nur leg_6)

**Workflow pro Servo:**

1. **Mechanische End-Stop-Prüfung stromlos** (Stage B-Sub-Stage):
   - Vor jedem Tester-Anschluss: Bein per Hand durch alle 3 Joints
     schwenken, ohne Strom auf dem Servo. Wo schlägt das Bein gegen den
     Body? Gibt es asymmetrische Anschläge? Diese Werte fließen in
     `pulse_min/max` ein wenn sie enger als URDF sind.
2. **Pre-Calibration mit HJ-Tester** (Stage B-Hauptarbeit, offline):
   - Servo nur Signal/GND am Tester, Tester-PSU versorgt → Bench-PSU bleibt aus
   - Mitte finden → `pulse_zero` notieren (typisch ~1500 µs ± 50 µs Servo-Streuung)
   - Vorsichtig in beide Richtungen drehen bis kurz vor mech. Anschlag oder
     URDF-Limit (was zuerst kommt) → `pulse_min`/`pulse_max` notieren, **mit
     ~5 % Sicherheitsabstand**
   - Werte vorab in `servo_mapping.yaml` eintragen, `direction: +1` als Platzhalter
3. **Stack-Validation** (Stages C/D/E):
   - Servo an Servo2040 anschließen (PSU AUS → Servo anstecken → PSU AN)
   - Plugin hochfahren, kleine Trajectory 0→+0.1 rad fahren
   - Bewegungsrichtung beobachten:
     - dreht in URDF-positive Richtung → `direction = +1` final
     - dreht in URDF-negative Richtung → YAML edit `direction: -1`, rebuild, retest
   - Endlagen-Test: ±1.0 rad fahren (innerhalb URDF-Limit ±1.57),
     prüfen kein Anschlag-Brumm, kein Watchdog-Trip

**Warum hybrid und nicht reine Methode:** Tester findet mechanische Werte
ohne Stack-Risiko (kein Plugin-Bug kann den Servo zerstören). Stack-Validation
findet `direction` (per Tester nicht erkennbar) und prüft die Plugin-→-Firmware-
→-Servo-Pipeline. Stromlose Hand-Schwenk-Prüfung **vor** dem Tester findet
Body-Kollisionen.

**Warum kompakt (nur leg_6, nicht alle 18):** User-Setup hat nur 4 Beine
montiert (leg_1/3/5/6), und leg_6 (vorne-links) ist mechanisch am besten
zugänglich. Phase 10 ist Single-Leg-Bring-up — die anderen Servos
brauchen wir erst in Phase 13 wenn der Hexapod voll montiert + verkabelt
ist.

**Strategie für `pulse_min`/`pulse_max` — Konservativ-Pragmatisch (Strategie B', User-Entscheid 2026-05-17):**

`pulse_min`/`pulse_max` für leg_6 werden als **Self-Collision-sichere
Hardware-Hard-Stops** kalibriert, nicht als maximaler mechanischer
Single-Leg-Range:

- **Workflow:** leg_5 (direkter Nachbar) wird **einmalig in eine
  worst-case-Pose** geschwenkt (Coxa maximal Richtung leg_6) und bleibt
  passiv in dieser Pose während der gesamten Stage B (Servo-Getriebe-
  Friction hält ohne Strom). Anschließend wird leg_6 per Tester so
  bewegt, dass `pulse_min`/`pulse_max` mit **5° Sicherheits-Abstand
  vor dem Berührungspunkt mit leg_5** gesetzt werden.
- **Konsequenz:** leg_6 kann **physisch** leg_5 nicht treffen — auch bei
  Software-Vollbug, IK-Fehler, falscher Trajectory etc. Plugin-Konversion
  + Firmware-Hard-Clamp setzen die Pulse-Werte durch.
- **Range-Verlust:** voraussichtlich ~20–30 % für leg_6-Coxa (einseitiger
  Nachbar leg_5). Mittel-Beine in Phase 13 (leg_2/leg_5) werden ~50 %
  Range-Verlust haben (zwei Nachbarn). Akzeptiert für maximale Hardware-
  Sicherheit.
- **Defense in Depth:** Phase 13 setzt Workspace-Boxes (`hexapod_kinematics`)
  **innerhalb** dieser Pulse-Hard-Stops. Beide Schichten zusammen
  garantieren Self-Collision-Vermeidung sowohl in Software (Workspace)
  als auch in Hardware (Pulse-Clamp).

**Verworfen:**
- **Strategie A — Voller Range im YAML, Self-Collision nur durch Software:**
  ursprünglich vorgeschlagen, aber User-Sicherheits-Priorität spricht
  dagegen. Bei Software-Bug kein Hardware-Schutz.
- **Strategie C — leg_5 demontieren für maximalen Single-Leg-Range:**
  ursprünglich auch im Plan, verworfen am 2026-05-17. Hardware-Sicherheit
  jetzt höher gewichtet als Range-Maximierung.
- **Strategie B (strikt) — leg_5 vor jeder Messung neu in worst-case schwenken:**
  zu viel Mess-Aufwand, kein praktischer Sicherheits-Vorteil gegenüber B'.
- **Tester-only:** spart Stack-Stages aber findet `direction` nicht. Risikoreicher.
- **Stack-only (Manuelles Jog vom User per `joint_state_publisher_gui`):**
  geht in Theorie, aber ohne Tester-Pre-Cal müsste man am Stack die mech.
  Endlagen suchen → höheres Risiko von Anschlag-Brumm.
- **Voll-Calibration aller 18 Servos in Phase 10 (Original-Skizze vom 14. Mai):**
  out-of-scope, weil nur leg_6 in dieser Phase bewegt wird. Phase-13-Job.
- **`pulse_per_rad`-Feld als Kalibrierungs-Parameter (Original-Skizze):**
  Phase-9-Design-Entscheidung hat das zugunsten 3-Punkt-Schema verworfen
  — siehe `project_phase9_decisions.md`.

### B. Bench-Setup für Stages C–F (mit echtem Servo)

> **Operative Anleitung:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §2
> (PSU-Setpoint-Tabelle pro Stage) und §7 (Pre-Stage-Checkliste).

| Parameter | Wert | Begründung |
|---|---|---|
| Bench-PSU Spannung | **7.0 V** | LiPo-Plateau-Mitte. Eine 2S-LiPo entlädt von 8.4 → 6.0 V und sitzt am längsten um 7.0–7.4 V; 7.4 V ist der nominelle Mittelpunkt, nicht der durchschnittliche Betriebspunkt. Beide Servo-Modelle (Diymore 8120MG, Miuzei MS61) vertragen bis 8.4 V. 7.0 V kalibriert am realistischen Betriebspunkt mit Sicherheits-Marge. |
| CC-Limit, 1 Coxa-Servo | **3 A** | Diymore 8120MG (20 kg·cm) Stall ~2.5 A @ 7.4 V × 1.2 Sicherheitsmarge. Bei mech. Anschlag-Brumm trippt PSU in CC-Modus → Spannung sinkt → Servo gibt nach. |
| CC-Limit, 1 Femur/Tibia-Servo | **4 A** | Miuzei MS61 (35 kg·cm) Stall ~3.5 A × 1.15. Höheres Drehmoment = höherer Stall-Strom. |
| CC-Limit, 2-Servo (Coxa + Femur, Stage D) | **7 A** | Σ aus 1-Servo-Limits: 3 A Coxa + 4 A Femur. |
| CC-Limit, 3-Servo-Bein (leg_6 voll) | **8 A** | Σ Idle ~1.5 A + Trajectory-Peaks. Drei gleichzeitige Stalls extrem unwahrscheinlich. |
| Aufbockung | Hexapod an Stock-Halterung, Bauch montiert, Beine hängen frei nach unten | Selbst-Beschädigungs-Risiko begrenzt auf Bein-eigene Mechanik. Keine externen Kollisionen. |
| Servos angeschlossen während C-F | nur leg_6 (Pin 15/16/17), andere 15 abgeklemmt | Strom-Risiko strikt auf 3 Servos begrenzt. Plugin sendet zwar 18× ENABLE_SERVO aber Pins ohne Servo sind elektrisch egal. |
| Kill-Switch | Bench-PSU OUTPUT-Taste | Sofort stromlos → Servos werden passiv → Bein hängt durch Schwerkraft. PSU bleibt eingestellt für schnellen Wiedereinstieg. |
| Normaler Stop | Ctrl-C am `ros2 launch`-Terminal | Sauberer `on_deactivate` → 18× DISABLE_SERVO. PSU bleibt an. |

### C. Initial-Pulse-Schlag-Mitigation (kritisch für erste Aktivierung pro Servo)

> **Operative Anleitung:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §6
> (User-Hand-Haltung-Tabelle pro Stage).

**Problem:** Beim ersten `on_activate` schickt das Plugin nach den ENABLE-
Frames einen neutralen `SET_TARGETS` mit `pulse_zero=1500 µs`. Der Servo
war vorher stromlos und passiv → mechanisch in der Position, in die das
Bein-Gewicht ihn gezogen hat (bei Femur/Tibia: hängt am Anschlag nach
unten). Beim ENABLE springt der Servo **schlagartig** auf 1500 µs ≈
Joint-Mitte. Bei Femur/Tibia bedeutet das einen 60–86°-Sprung gegen
Bein-Gewicht → möglicher Stall-Brumm beim ersten Hochfahren.

**Mitigation pro Stage:**

- Vor jeder ersten Aktivierung: User **hält das Bein manuell** in eine
  Position nahe der Servo-Mitte (Bein horizontal nach außen für Femur,
  Tibia gestreckt). Dann Launch starten → ENABLE springt nur wenige Grad
  → minimaler Stoß. Nach dem Hochfahren Bein loslassen.
- Plugin-CC-Limit ist die zweite Schutzschicht: bei Stall trippt die PSU.

**Alternativen für spätere Phasen (nicht in Phase 10):**

- **Soft-Start im Plugin:** erstes SET_TARGETS nicht auf `pulse_zero`,
  sondern langsam von „aktuelle physische Position" zur Joint-Mitte rampen.
  Setzt Position-Feedback voraus, das wir nicht haben (Echo-State).
- **Ramped-Enable in der Firmware:** Servo2040 könnte beim ENABLE den
  PWM-Puls von 1500 µs aus weichem Anlauf hochfahren. Phase-12+-Kandidat
  falls Plugin-seitige Lösung nicht ausreicht.
- **Initial-Pulse-Presets pro Setup-Variante (User-Konzept 2026-05-16):**
  YAML erweitert um `initial_pulse: { suspended: ..., resting: ... }`
  pro Servo + Plugin-Param `initial_pose_preset`. Plugin schickt beim
  ENABLE den preset-spezifischen Initial-Pulse (z.B. `pulse_min`-Nähe
  für Femur im suspended-Setup, weil Bein passiv hängt), kein Sprung
  gegen Schwerkraft. JTC/gait fährt danach die echte Soll-Pose an. Nur
  2 Presets nötig — `suspended` (Testbench aufgebockt) und `resting`
  (Bauch-liegend); kein `stand`-Preset, weil Stand eine **Ziel-Pose**
  ist, keine Start-Pose. Aufwand: ~2–3 d Plugin-Code-Change + YAML-
  Migration + Tests + Cal-Tool für Preset-Werte. **Phase-13-Kandidat**
  — skaliert besser als User-Hand-Mitigation bei 18 Servos.
  Cross-Phase-Reminder: Memory `project_phase13_initial_pose_presets.md`.

### D. Verkabelungs-Sequenz und -Polarität

> **Operative Anleitung:** [`phase_10_safety_setup.md`](phase_10_safety_setup.md) §3
> (Polaritäts-Diagramm) und §4 (Anschluss-/Abklemm-Sequenz).

**Polarität (kritisch — falsche Polarität tötet Servo in Sekunden):**

| Servo-Pin | Farbe (Standard JST/Futaba/PWM-3-Pin) | Servo2040-Pin |
|---|---|---|
| GND | braun oder schwarz | GND-Reihe |
| V+ | rot | V+-Reihe |
| Signal | gelb, orange, oder weiß | Signal-Reihe (Pin 15/16/17 für leg_6) |

**Anschluss-Sequenz (jedes Mal wenn ein Servo angeklemmt wird):**

1. Bench-PSU **OUTPUT AUS**
2. Servo-Connector am Servo2040-Header anstecken (auf Polarität achten)
3. Sichtprüfung: Stecker sitzt komplett, kein Pin daneben
4. Bench-PSU OUTPUT AN
5. PSU-Anzeige beobachten: Strom < 200 mA (1 Servo idle) erwartet
   - Strom > 500 mA = Verdacht auf Kurzschluss/Stall → sofort OFF, prüfen
6. Servo2040-LED sollte normales Pattern zeigen (kein Boot-Loop, kein Trip)

**Abklemm-Sequenz:**

1. Bench-PSU **OUTPUT AUS**
2. Servo-Connector vom Servo2040-Header abziehen
3. (optional) Bench-PSU OUTPUT wieder AN wenn nächster Test direkt folgt

### E. Tester-Range vs URDF-Joint-Range

HJ-Tester deckt 800–2200 µs ab. URDF-Joint-Limits:

| Joint | URDF-Limit (rad) | URDF-Limit (Grad) | Erwartete Pulse-Range (µs) bei 270°-Servo |
|---|---|---|---|
| Coxa | ±1.57 | ±90° | ~1000–2000 |
| Femur | ±1.57 | ±90° | ~1000–2000 |
| Tibia | ±1.50 | ±86° | ~1050–1950 |

Tester-Range 800–2200 µs **deckt alle URDF-Limits voll ab**. Falls beim
Tester-Pre-Cal die mech. Endlage außerhalb 800–2200 µs läge, hieße das:
der Servo hat noch mehr Range, aber wir kalibrieren ohnehin auf URDF-
Limits. Kein Show-Stopper.

### F. RViz-Sync-Beobachtung als Verifikations-Hilfe

In Stages C/D/E/F läuft `real.launch.py` mit `rviz:=true`. RViz visualisiert
die `/joint_states`-Topic-Werte (= Echo-State, also was das Plugin gesendet
hat). **Visuell-vergleichen:** Bein in RViz und Bein in echt sollten in
derselben Pose stehen. Bei Diskrepanz:

- Plugin glaubt der Servo ist an Position X, aber Servo ist physisch
  woanders → Indikation für Stall, Anschlag, oder falsche Kalibrierung.
- RViz allein **beweist nicht** dass der Servo richtig steht. Augenmaß
  am echten Bein bleibt Pflicht.

### G. Strom-Logging mit `tools/log_state.py` aus fw-Repo

Stage F protokolliert während IK-Trajectory parallel den Servo2040-State
in eine CSV (über USB-CDC, 20 Hz Polling-Rate aus der Firmware-Logik):

```bash
python3 ~/hexapod_servo_driver/tools/log_state.py \
  --out leg6_ik_$(date +%Y%m%dT%H%M).csv
```

CSV-Spalten: `t_s, voltage_mv, current_ma (Rail-Total), flags, p0..p17`.
Die `current_ma`-Spalte ist **Gesamt-Rail-Strom**, kein per-Servo-Wert
(Servo2040-HW hat nur einen Shunt). Für Vel/Accel-Limits in Stage G
auswerten: max gefahrene rad/s pro Joint aus Δp_i/Δt, Strom-Spitzen
als Validierungs-Korrelat.

### H. Bein-Geometrie-Verifikation als Stage-F.1-Sub-Step (verworfen: Stage A)

URDF-Bein-Längen (`coxa_length=43.6 mm`, `femur_length=79.94 mm`,
`tibia_length=178.7 mm`) sind **nur für die IK relevant**. Stages B–E
machen reine Per-Joint-Trajectories, unabhängig von Bein-Längen.

**Entscheidung:** Lineal-Check kommt als erster Sub-Step von Stage F (F.1),
**nicht** als Vorbereitungs-Item in Stage A. Damit bleibt Stage A schlank
und der Check passiert direkt vor dem ersten IK-Aufruf.

**Verworfen:** Variante A (Check in Stage A) — würde Stage A um ~30 min
verlängern ohne Mehrwert für B–E.

### I. `direction`-Flip-Mechanismus: statisches YAML + Build-Cycle (verworfen: Live-Parameter)

Das `direction`-Feld in `servo_mapping.yaml` wird beim Plugin-Start
(`on_init`) gelesen und bleibt für die Laufzeit fest. Ein Flip erfordert:

```
YAML editieren → colcon build --packages-select hexapod_hardware
→ source install/setup.bash → launch neu starten
```

~5–10 min pro Flip. Bei 3 leg_6-Servos worst case = 30 min Gesamtzeit.

**Entscheidung:** Build-Edit-Build pro Flip. Plugin-Code bleibt unangetastet.

**Verworfen:** Plugin-Erweiterung mit `direction` als ROS-Live-Parameter —
Aufwand 2–3 Tage Entwicklungszeit (Code + Tests + Doku), nicht
amortisierbar bei 3 Servos. Phase 13 kann das als separate
Architektur-Frage evaluieren (18 Servos → ~3 h worst case → Plugin-Change
lohnt sich dort eher).

### J. IK-Trajectory-Source in Stage F: Hybrid (direkter IK + gait_node)

Stage F testet die IK + leg_6-Mechanik in **zwei Sub-Steps** nacheinander:

- **F.2 — direkter IK-Aufruf:** kleines Python-Skript (~30 Zeilen)
  ruft `hexapod_kinematics::inverse_kinematics` direkt mit gewähltem
  Fuß-Ziel auf, generiert 2-Punkt-JointTrajectory, sendet an
  `leg_6_controller`. Eine klar definierte Bewegung (3 cm Fuß-Hub
  vertikal), andere 5 Beine ruhig (keine Goals an sie).
- **F.3 — gait_node mit `/cmd_vel`-Stub:** voller Walking-Pfad wie in
  Phase 13. gait_node generiert Tripod-Pattern für alle 6 Beine,
  publisht JTC-Goals an alle 6 `leg_X_controller`. leg_6 bewegt sich
  physisch entsprechend, andere 5 Beine bekommen Pulse-Streams an
  Pins 0–14 ohne angeschlossene Servos (harmlos).

**Diagnose-Trennung:**
- F.2 hängt → Problem in IK selbst oder in Kalibrierung
- F.2 grün und F.3 hängt → Problem in gait_node oder cmd_vel-Mapping
- Beide grün → Phase-13-ROS-Pipeline ist bewiesen; Phase 13 hat nur
  noch HW-Punkte (Servo-Cal anderer 15, Stand-Belastung, Cable-Mgmt,
  Boden-Walking).

**Warum nicht nur Variante B (gait_node pure):** ohne F.2-Diagnose-Probe
ist schwer zu trennen ob ein Stage-F-Fehler in IK, JTC oder gait_node
liegt. F.2 ist 30 Zeilen Python, kostet 30 min, kann diese Trennung machen.

**Was Variante B in Phase 10 mit nur leg_6 physisch beweist (User-Frage 2026-05-16):**
der **volle ROS-Software-Stack-Pfad** ist verifiziert (gait_node → JTC →
Plugin → Firmware → Servos). Was Phase 13 noch leistet: Kalibrierung der
15 anderen Servos, Bein-Längen-Check aller 6 Beine, 6-Bein-Stand-Belastung
(Roboter trägt sich selbst auf Beinen → echte Stall-Profile), PSU-Strom-
Budget mit 18-Servo-Last, Cable-Management, Walking auf Boden mit echter
Reibung. **Software-Pipeline-Risiken sind nach Stage F.3 weitestgehend
geschlossen.**

**Verworfen:** Pure Variante A oder Pure Variante B — A allein deckt
Phase-13-Pfad nicht ab, B allein hat schlechtere Diagnose-Trennung.

---

## Done-Kriterien Phase 10

1. **leg_6 voll kalibriert:** `servo_mapping.yaml` hat für Pins 15/16/17 echte
   Werte mit `direction`, übrige 15 Servos bleiben dokumentiert als
   placeholder. YAML pro leg_6-Eintrag `status: calibrated`,
   `calibrated_at: <ISO>`.
2. **3-Servo-Bewegung:** JTC fährt eine koordinierte Trajectory durch
   `leg_6_controller`, Goal wird erreicht, kein Watchdog-Trip, kein Overcurrent.
3. **IK-Sanity-Test:** eine einfache Phase-5-Bein-Trajectory (Fuß linear
   ~3 cm Hub) wird sauber gefahren ohne Anschlag-Brumm.
4. **`controllers.real.yaml` mit Bench-Daten:** Vel/Accel-Limits aus
   Stage-F-Messungen eingetragen, committed.
5. **Sicherheits-Workflow dokumentiert:** Aufbock-Setup, Verkabelungs-
   Polarität, Anschluss-Sequenz, Initial-Pulse-Mitigation, Kill-Switch
   in jedem Stage-Test-Commands-Doc.
6. **CI weiterhin grün:** hexapod_hardware 208/0, hexapod_bringup 18/0
   unverändert (Phase 10 macht keine Code-Änderungen, nur YAML/Config-Edits).

---

## Stufen

### Stage A — Phase-10-Mutter-Plan-Doku + Sicherheits-Setup

**Vorbedingung:** keine. Reine Doku-/Vorbereitungs-Arbeit, keine HW-Bewegung.

- Phase-10-Mutter-Plan-Doku (diese Datei) finalisiert + User-Freigabe
- `phase_10_progress.md` anlegen mit Stages A–I als Sektionen
- Bench-Setup-Checkliste schreiben (PSU 7.0 V, CC-Limit-Tabelle, Verkabelung)
- Verkabelungs-Polaritäts-Diagramm (Sektion D oben) in `phase_10_stage_b_test_commands.md` einbetten
- Kill-Switch-Position dokumentiert
- Initial-Pulse-Mitigation als Sicherheits-Hinweis ganz oben in
  jeder Stage-C/D/E/F-Test-Commands-Doc

**Done-Kriterium A:** Doku committed, kein Code-Edit.

### Stage B — Mech. End-Stop-Check stromlos + HJ-Tester Pre-Cal leg_6

**Vorbedingung:** leg_6 mechanisch montiert (gegeben), HJ-Tester vorhanden,
Tester-PSU bereit, Servo2040 ist offline (Bench-PSU AUS).

#### B.1 — Mech. End-Stop-Check stromlos (vor allem anderen)

Pro Joint (coxa, femur, tibia) bei leg_6:
- Bein per Hand durch den Joint schwenken (ohne Strom)
- Wo schlägt das Bein gegen den Body oder gegen sich selbst an?
- Winkel mit Hand-Augenmaß oder Winkelmesser schätzen
- Mit URDF-Limit vergleichen:
  - Coxa: ±1.57 rad = ±90°
  - Femur: ±1.57 rad = ±90°
  - Tibia: ±1.50 rad = ±86°
- **Wenn mech. Anschlag enger als URDF-Limit:** den engeren Wert für
  spätere Kalibrierung notieren — `pulse_min`/`pulse_max` in YAML soll
  bei der engeren Grenze landen, nicht bei der URDF-Grenze.

#### B.2 — HJ-Tester Pre-Cal

Pro Servo (3× nacheinander):
- Servo nur Signal/GND am Tester (Strom aus Tester-PSU, Bench-PSU bleibt AUS)
- Tester-Drehknopf langsam von Mitte aus drehen
- **`pulse_zero` finden:** Joint steht in geometrischer Mitte
  (Coxa: Bein zeigt radial nach außen vom Body weg)
  (Femur: Femur horizontal)
  (Tibia: gerade gestreckt, kein Knie-Knick)
  → Pulswert vom Tester-Display ablesen, notieren
- **`pulse_min` finden:** vorsichtig zum unteren mech. Anschlag oder
  URDF-Limit-Position fahren (was zuerst kommt), +5 % Sicherheitsabstand
- **`pulse_max` finden:** analog zum oberen Anschlag/URDF-Limit
- Werte in `servo_mapping.yaml` eintragen, `direction: +1` belassen,
  Status pro Servo bleibt `placeholder` (Tester-Stand, ohne Stack-Validation)

#### B.3 — Werte committen

Werte für Pins 15/16/17 in YAML, Commit-Nachricht
„phase10: leg_6 servo pre-calibration values from HJ tester".

**Done-Kriterium B:**
1. Mech. End-Stops dokumentiert (leg_6, 3 Joints)
2. YAML hat für Pins 15/16/17 Tester-Werte
3. Tester-Werte plausibel (`pulse_min < pulse_zero < pulse_max`, alle in
   800–2200 µs)
4. Servos nach Stage B wieder abgeklemmt, Bench-PSU AUS

### Stage C — Stack-Validation leg_6_coxa (1 Servo)

**Vorbedingung:** Stage B fertig.

- Coxa-Servo am Servo2040 Pin 15 anstecken (Anschluss-Sequenz aus Architektur-Entscheidung D)
- User hält das Bein in eine Position nahe Joint-Mitte (Bein horizontal nach außen)
- `ros2 launch hexapod_bringup real.launch.py rviz:=true` starten
- Im Log verifizieren: HexapodSystemHardware activates, 18× ENABLE_SERVO
  durchgelaufen, kein UNDERVOLTAGE-Trip
- RViz: Bein 6 visuell in Default-Pose (= URDF-Null-Pose)
- Erste Trajectory: `leg_6_controller` → `leg_6_coxa_joint` auf +0.1 rad in 3 s
- Beobachten:
  - Dreht das Bein in URDF-positive Richtung? → `direction = +1` final
  - Dreht es in URDF-negative Richtung? → YAML edit `direction: -1`,
    rebuild, retest
- RViz-Sync-Check: Bein in RViz dreht zur gleichen Richtung wie echtes Bein
- Endlagen-Test: Trajectory auf ±1.0 rad (gut innerhalb URDF-Limit ±1.57),
  prüfen kein Anschlag-Brumm, kein Watchdog-Trip
- Servo nach Test abklemmen (PSU AUS → abklemmen)

**Done-Kriterium C:**
1. Coxa `direction` final in YAML
2. Bewegung in beide Richtungen ohne Stall
3. JTC-Goal erreicht
4. RViz und echtes Bein bewegen sich synchron
5. Keine Firmware-Errors (kein ANY_SERVO_OVERCURRENT, UNDERVOLTAGE_TRIPPED, WATCHDOG_TRIPPED)

### Stage D — Stack-Validation leg_6_coxa + leg_6_femur (2 Servos)

**Vorbedingung:** Stage C fertig.

- Coxa-Servo wieder anstecken, Femur-Servo zusätzlich an Pin 16
- User hält das Bein in geometrische Mitte
- Plugin starten mit rviz:=true, beide Servos aktivieren
- 2-Joint-Trajectory: `leg_6_coxa` auf +0.1 rad UND `leg_6_femur` auf +0.1 rad gleichzeitig in 3 s
- Femur-`direction` analog zu Stage C bestimmen
- Endlagen-Test femur: ±1.0 rad, **mit User-Hand bereit** Bein zu fangen falls Stall
- Beide Servos nach Test abklemmen

**Done-Kriterium D:**
1. Femur `direction` final in YAML
2. Beide Servos koordiniert ohne Phasen-Versatz (Goal-Zeit-Slot gleich)
3. RViz Sync OK
4. Keine Firmware-Errors

### Stage E — Stack-Validation leg_6_tibia (1 Servo isoliert)

**Vorbedingung:** Stage D fertig.

- Tibia-Servo an Pin 17 anstecken (Coxa, Femur abgeklemmt — Tibia isoliert)
- User hält Tibia gestreckt (~0 rad ≈ pulse_zero)
- Trajectory analog zu C, dann ±1.0 rad
- Tibia-`direction` bestimmen
- RViz-Sync-Check
- Servo abklemmen

**Done-Kriterium E:**
1. Tibia `direction` final
2. Keine Stalls (Tibia ist isoliert, kein Bein-Gewicht-Hebel)
3. RViz Sync OK
4. Keine Firmware-Errors

### Stage F — IK-Roundtrip leg_6 voll (3 Servos) + Voll-Pipeline-Test

**Vorbedingung:** Stages C/D/E fertig, alle 3 `direction`s final, YAML
hat finale Werte für Pins 15/16/17.

**Dauer:** ~1.5 d (Wildcard — hängt von Geometrie-Match + IK-Verhalten ab).

#### F.1 — Bein-Geometrie-Verifikation

Lineal/Schieblehre an leg_6 anlegen, mit URDF-Werten vergleichen:
- `coxa_length` = 43.6 mm (von Coxa-Joint-Achse bis Femur-Joint-Achse)
- `femur_length` = 79.94 mm (Femur-Joint-Achse bis Tibia-Joint-Achse)
- `tibia_length` = 178.7 mm (Tibia-Joint-Achse bis Fuß-Spitze)

Drehachsen sind die Servo-Wellen → mittlere Schraube/Welle jedes Joints.

**Bei Abweichung > 5 mm:** Stop, URDF (`hexapod_physical_properties.xacro`)
anpassen, `colcon build --packages-select hexapod_description hexapod_hardware`
neu, dann F.2 starten.

#### F.2 — Direkter IK-Aufruf (Diagnose-Probe)

**Ziel:** isolierte IK-Validation. Wenn das hängt, wissen wir es ist die IK
selbst, bevor gait_node mit dazukommt.

Setup:
- Alle 3 leg_6-Servos anstecken (Pin 15/16/17), CC-Limit 8 A bei 7.0 V
- User hält Bein in Phase-5-Stand-Position (Fuß ~50 cm unter Body in Default-Pose)
- Plugin starten mit `rviz:=true`, alle 3 aktivieren

Logger (Terminal 1):
```bash
python3 ~/hexapod_servo_driver/tools/log_state.py \
  --out leg6_F2_$(date +%Y%m%dT%H%M).csv
```

Diagnose-Skript (Terminal 2 — ~30 Zeilen Python, Phase-10-Stage-F-spezifisch):
```python
# pseudocode
from hexapod_kinematics import inverse_kinematics
import rclpy, ...

goal_a = (0.15, 0.10, -0.10)   # Fuß-Start im Body-Frame
goal_b = (0.15, 0.10, -0.07)   # Fuß-Ende: 3 cm Hub vertikal

angles_a = inverse_kinematics("leg_6", goal_a)
angles_b = inverse_kinematics("leg_6", goal_b)

# 2-Punkt JointTrajectory an /leg_6_controller/follow_joint_trajectory senden
# duration = 2.0 s, langsam für Diagnose
```

Beobachten:
- Fuß bewegt sich linear vertikal um ca. 3 cm (Lineal-Sicht)
- RViz und echtes Bein synchron
- Kein Anschlag, kein Watchdog-Trip
- Strom-CSV läuft, Peak < CC-Limit

**Wenn F.2 hängt:** vor F.3 stoppen, IK debuggen (KDL-Warning prüfen,
Bein-Geometrie nochmal messen, direction-Werte verifizieren).

#### F.3 — gait_node mit `/cmd_vel`-Stub (Voll-Pipeline-Test)

**Ziel:** gleicher Software-Pfad wie Phase 13. gait_node + JTC + Plugin +
Firmware + Servos koordiniert testen.

Setup bleibt wie F.2 (Servos angeschlossen, PSU an).

Logger weiter laufen lassen (oder neu mit `leg6_F3_*.csv`).

gait_node starten (genaue Launch-Form klärt Stage-F-Plan-Doku):
```bash
ros2 launch hexapod_bringup real.launch.py rviz:=true gait:=true
```

`/cmd_vel` minimal füttern:
```bash
ros2 topic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.02}}'
```

Beobachten:
- gait_node generiert Tripod-Pattern für alle 6 Beine
- leg_6 schwingt physisch vor/zurück entsprechend Gait-Phase
- andere 5 Beine bekommen JTC-Goals → Plugin sendet Pulse an Pins 0–14
  (harmlos, weil dort nichts angeschlossen)
- RViz zeigt alle 6 Beine im Tripod-Pattern (Echo-State)
- Strom-CSV zeigt klare Korrelation zur leg_6-Bewegungsphase

Stop nach ~10 s mit Ctrl-C (`/cmd_vel`-Topic) und dann `ros2 launch`.

**Wenn F.3 hängt aber F.2 grün war:** Problem in gait_node oder cmd_vel-
Mapping. Debug-Pfad: `ros2 topic echo /leg_6_controller/joint_trajectory`
zeigt was gait_node sendet, vergleichen mit F.2's IK-Output.

#### F.4 — Strom-Profil-Auswertung

Logger stoppen, CSV in Pandas/Python laden:
```python
import pandas as pd
df = pd.read_csv("leg6_F3_...csv")
df.plot(x="t_s", y=["p15", "p16", "p17", "current_ma"])
```

Pro Joint (p15/p16/p17) max gefahrene Pulse-Δ/s → über `pulse_per_rad`
auf rad/s umrechnen. Strom-Peaks zur Stage-G-Vel/Accel-Limit-Auslegung
verwenden (Memory `project_phase10_real_yaml_vel_limits.md`).

**Done-Kriterium F:**
1. Bein-Geometrie verifiziert oder URDF angepasst
2. F.2: direkter IK-Trajectory wird ohne Fehler gefahren, Fuß-Hub ~3 cm visuell
3. F.3: gait_node + cmd_vel funktioniert, leg_6 schwingt im Tripod-Pattern
4. Kein Servo-Stall, kein Firmware-Trip in F.2 oder F.3
5. Strom-CSVs aus F.2 + F.3 aufgezeichnet, Peak-Werte pro Joint dokumentiert
6. RViz-Bewegung synchron zur echten Bewegung (Echo-State-Verifikation)

**Risiko-Hinweise Stage F:**
- Wenn IK nicht trifft (Fuß landet > 2 cm neben Ziel): Phase-5-IK vs reale
  Bein-Geometrie checken. Memory `project_phase5_kdl_warning_fix.md`
  könnte hier relevant werden (Dummy-Root-Link-Fix falls Warning beim
  Debug stört).
- Wenn ein Servo wiederholt stallt: CC-Limit prüfen, Initial-Pulse-Mitigation
  prüfen, Bein-Hebel zur Schwerkraft-Achse betrachten.
- Wenn F.3 ohne /cmd_vel-Eingabe schon laute Trajectories für andere 5 Beine
  generiert: gait_node-Verhalten prüfen — möglicherweise Default-Pose-Hold
  als initiale Trajectory. Unkritisch wenn leg_6 in Default-Pose bleibt.

### Stage G — `controllers.real.yaml` Vel/Accel-Limits

**Vorbedingung:** Stage F fertig, Strom-/Geschwindigkeits-CSV aus F vorhanden.

- Vel-Limits pro Joint aus Stage-F-CSV ableiten:
  Δp_i / Δt = pulse-µs/s, umgerechnet über `pulse_per_rad`-Steigung
  auf rad/s
- Accel-Limits aus Δvelocity/Δtime im CSV
- Konservativ ~70 % der gemessenen Peaks als Limit eintragen
- `controllers.real.yaml` aktualisieren:
  - `command_interfaces`, `state_interfaces`
  - JTC `constraints` (goal_time, goal_position_tolerance) — schon
    aus Phase 9 da, ggf. anpassen
  - Per-Joint Vel/Accel-Limits ergänzen
- Smoke-Test: Stage-F-Trajectory nochmal fahren, sollte weiter funktionieren
- launch_testing 18/0 unverändert

**Done-Kriterium G:**
1. `controllers.real.yaml` enthält Vel/Accel-Limits für leg_6-Joints
2. Stage-F-Trajectory weiter erfolgreich
3. launch_testing weiter 18/0

### Stage H — (entfällt: Oszi/LA-Tests gestrichen)

Stage H aus dem ersten Phase-10-Brainstorm war Oszi/Logic-Analyzer-Tests
(H-T8/H-T9 aus Phase 9). Auf User-Entscheidung (2026-05-16) gestrichen
und komplett aus Phase 10 entfernt. Memory-Eintrag
`project_phase9_h_oscilloscope_pending.md` bleibt als Cross-Session-
Pendenz ohne Phasen-Verankerung.

### Stage I — Phase-10-Abschluss

- `phase_10_progress.md` finalisieren mit Retrospektive
- `servo_mapping.yaml` Status:
  - Pro Pin 15/16/17: ggf. eigenes `status: calibrated`,
    `calibrated_at: <ISO>` als per-Eintrag-Feld (Top-Level bleibt
    `placeholder` solange andere 15 Pins nicht kalibriert sind)
- README hexapod_hardware: Phase-10-Quick-Start-Snippet ergänzen
  (leg_6 verifizierten Status)
- PHASE.md: Phase 10 → 🟢, Phase 12 → 🟡 aktiv
- Git-Commit + Tag `phase-10-done` (durch User)

**Done-Kriterium I:**
1. Doku finalisiert
2. PHASE.md aktualisiert
3. Git-Tag `phase-10-done` gesetzt (durch User)

---

## Entschiedene Fragen vor Stage-B-Start

Drei Punkte wurden beim Stage-A-Plan-Review am 2026-05-16 geklärt
(siehe Architektur-Entscheidungen H/I/J oben):

| Frage | Entscheidung | Verworfen | Begründung |
|---|---|---|---|
| Bein-Geometrie-Check Timing | **F.1** (Stage-F-Sub-Step) | Stage A | Stages B–E sind längen-unabhängig; Check nur vor IK nötig |
| `direction`-Flip-Mechanismus | **Build-Edit-Build pro Flip** | Plugin-Live-Parameter | Bei 3 Servos in Phase 10 nicht amortisierbar; Phase 13 kann separat entscheiden |
| IK-Trajectory-Source in F | **Hybrid F.2 (direkter IK) + F.3 (gait_node)** | reine F.2 oder reine F.3 | Diagnose-Trennung IK vs. gait_node; Voll-Pipeline-Verifikation für Phase 13 |

---

## Stolperfallen (lessons-learned-vorab, plus übernommen aus altem Plan-Entwurf)

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| Servo dreht beim ersten ENABLE schlagartig 60–90° gegen Schwerkraft | Initial-Pulse-Schlag (Plugin sendet `pulse_zero` nach Enable, Servo war passiv woanders) | User hält Bein in Servo-Mitte beim ersten Aktivieren (Architektur-Entscheidung C) |
| Servo brummt am Anschlag | `pulse_min` oder `pulse_max` zu nah am mech. Anschlag, Servo versucht weiter zu drehen, Firmware-Clamp greift erst spät | YAML-Werte mit ~5 % Sicherheitsabstand zum gemessenen mech. Anschlag eintragen |
| Bewegung dreht in falsche Richtung | `direction: +1` vs. URDF-Konvention nicht passend | YAML auf `direction: -1`, rebuild, retest |
| Servo bewegt sich nicht trotz Plugin-Bringup | Verkabelung: GND/Signal vertauscht, oder Signal an falschem Pin | Polaritäts-Check (braun=GND, rot=V+, gelb=Signal), Pin-Index in YAML verifizieren |
| Servo verbrennt nach Verkabelung | V+ und GND vertauscht | Servo ist zerstört. Polaritäts-Check vor jedem Anstecken zwingend |
| PSU springt sofort in CC bei Bringup | Stall an mech. Anschlag, oder Servo defekt | PSU AUS, Servo prüfen, Verkabelung prüfen, `pulse_zero` vs. mech. Mitte prüfen |
| Watchdog-Trip im Log | Plugin schickt < 5 Hz SET_TARGETS, Firmware-Watchdog (200 ms) greift | `controller_manager update_rate` >= 50 Hz prüfen |
| UNDERVOLTAGE_TRIPPED-Sturm | Bench-PSU < 5.5 V am Servo-Rail | PSU-Setpoint auf 7.0 V verifizieren, V+/GND-Anschluss prüfen |
| ANY_SERVO_OVERCURRENT für leeren Pin | Servo2040-Firmware misst Strom auf nicht-belegtem Pin als false-positive | Nur leg_6-Servos angeschlossen lassen, Plugin-Log auf welcher Servo-Idx der Error kommt prüfen |
| IK-Trajectory landet 2+ cm neben Ziel | Bein-Geometrie weicht von URDF ab | Lineal-Check `coxa_length`/`femur_length`/`tibia_length`, URDF anpassen |
| Servo zittert in Stand-Pose (kein Stall, kein Trip) | Digital-Servo kompensiert minimale Soll-/Ist-Abweichung | Akzeptieren (typisch für Digital-Servos) oder JTC `goal_position_tolerance` lockerer |
| Servo wird heiß ohne sichtbare Bewegung | Mechanische Verspannung — Servo arbeitet gegen sich selbst | Kalibrierung prüfen, Bein händisch in Pose, prüfen ob Servo nach Hand-Eingriff entspannt ist |
| Stand-Pose visuell schief | falsche `direction` oder falsche `pulse_zero` an einem oder mehreren Joints | Pro Joint einzeln verifizieren, asymmetrische Beine sind verdächtig |
| RViz zeigt korrekte Pose, echtes Bein nicht | Echo-State-Limitation: Plugin glaubt Servo ist da, ist es aber nicht | Indikation für Stall, Anschlag, oder Servo-Defekt. **Augenmaß am Bein bleibt Pflicht.** |

---

## Was in dieser Phase **NICHT** gemacht wird

- Kein Walken auf dem Boden (Phase 13)
- Kein Pi (Phase 12)
- Keine PS4-Vollbetrieb-Tests (Phase 13)
- Kein Akku (Phase 13+)
- Keine Cable-Management-Endmontage (Phase 13)
- Keine voll-6-Bein-Kalibrierung (Phase 13)
- Keine Oszi/Logic-Analyzer-Tests (User-Entscheidung 2026-05-16)

---

## Phasenabschluss-Checkliste

- [ ] Stages A–G Done-Kriterien erfüllt (Stage H entfällt)
- [ ] `servo_mapping.yaml` leg_6 (Pin 15/16/17) `status: calibrated`
- [ ] `controllers.real.yaml` mit Vel/Accel-Limits aus Bench-Daten
- [ ] CI weiterhin grün (hexapod_hardware 208/0, hexapod_bringup 18/0)
- [ ] User-Smoke F (3-Servo + IK) grün dokumentiert
- [ ] Strom-CSV aus Stage F im Repo (für Phase-13-Referenz)
- [ ] Git-Commit + Tag `phase-10-done` (durch User)
- [ ] `PHASE.md` auf Phase 12 (Pi-Plattform) aktualisiert
- [ ] Retrospektive in `phase_10_progress.md`
