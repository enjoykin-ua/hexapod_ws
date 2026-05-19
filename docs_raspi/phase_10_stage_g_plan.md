# Phase 10 — Stufe G — Plan

> **Status:** Plan, in Vorbereitung.
>
> **Parent-Plan:** [`phase_10_single_leg.md`](phase_10_single_leg.md)
> Stufe G — `controllers.real.yaml` Vel/Accel-Limits.
>
> **Vorbedingung:** Stufe F komplett (alle 3 leg_6-Servos kalibriert
> mit direction final, IK-Pipeline + gait_node verifiziert).
> **Kein HW-Test in Stage G** — reine YAML-Anpassung + Build/Test.

---

## Ziel

`controllers.real.yaml` um **Per-Joint-Vel/Accel-Limits + JTC constraints**
erweitern, damit Phase 13 mit konservativen Walking-Geschwindigkeiten
startet und gegen Trajectory-Verletzungen abgesichert ist.

Bisheriger Stand (Phase 9 Stage G + Stage F):
- `controllers.real.yaml` ist **limit-frei** — JTC akzeptiert jedes
  Goal innerhalb URDF-Limits, kein Tracking-Tolerance-Check
- TODO-Kommentar in der Datei (Z. 19-24) sagt explizit: „aus Bench-
  Trajektorie ableiten und hier einsetzen"
- Stage F.4 hat Strom-CSV-Pipeline **deferred zu Phase 13**
  (User-Entscheid: aufgehängtes Bein liefert nicht repräsentative Werte)

**Strategie für Stage G:** konservative URDF-Default-basierte Werte
eintragen (statt Bench-CSV). Phase 13 verfeinert das mit echten
Belastungsdaten.

---

## Strategie / Architektur-Erinnerungen

| Punkt | Wert | Quelle |
|---|---|---|
| URDF Joint-Velocity-Limit | 2.0 rad/s (alle Joints) | `00_conventions.md` §11.4 |
| URDF Joint-Effort-Limit | 5.0 Nm (alle Joints) | `00_conventions.md` §11.4 |
| URDF Joint-Position-Limits | Coxa/Femur ±1.57, Tibia ±1.50 rad | `00_conventions.md` §11.4 |
| Bench-Daten verfügbar? | **Nein** (F.4 deferred, Memory `project_phase10_real_yaml_vel_limits.md` aktiv) | Stage-F-Self-Review |
| 70%-Regel | 0.7 × URDF-Velocity = 1.4 rad/s als Default | Mutter-Plan §B + Stage-G-Plan-Korrektur |
| Phase-13-Verfeinerung | mit Voll-Stand-Belastung + Boden-Walking | Mutter-Plan §Stage-G + Phase 13 Stufe H |

---

## Plan-Korrektur ggü. Mutter-Plan-Doku §Stage-G

Mutter-Plan schreibt:
> „Vel-Limits pro Joint aus Stage-F-CSV ableiten: Δp_i / Δt = pulse-µs/s,
> umgerechnet über `pulse_per_rad`-Steigung auf rad/s"

**Tatsächliche Situation:** F.4 Strom-CSV ist auf User-Entscheid deferred
zu Phase 13 — aufgehängtes Bein ohne Last liefert keine repräsentativen
Werte für später-Voll-Last-Walking. Memory
`project_phase10_real_yaml_vel_limits.md` bleibt aktiv.

**Konsequenz für Stage G:** Vel/Accel-Limits werden aus **URDF-Defaults
× 0.7** abgeleitet statt aus Bench-CSV. Konservative Erst-Werte. Phase
12 verfeinert das im Stufe-G „Limits hochziehen"-Sub-Step.

**Verworfen:** Bench-CSV-Pipeline noch in Stage G nachholen — User-
Entscheid F.4 deferred, würde nur ~25 min Aufwand für nicht
repräsentative Werte produzieren.

---

## User-Antworten (User-Freigabe 2026-05-18 — **Option C deferren**)

**Wichtige User-Klarstellung 2026-05-18:** Echo-State ist permanent.
Servos liefern **niemals** echtes Position-Feedback; kein Wechsel zu
Feedback-Servos geplant. Damit sind JTC-Toleranz-Constraints faktisch
wertlos (alle Vergleiche Soll vs. Echo-von-Soll → Differenz 0).

| # | Frage | Antwort |
|---|---|---|
| **G-Q1 (neu)** Stage-G-Umfang | **C** — komplett deferren (YAML unverändert, nur TODO-Kommentar aktualisieren). Echo-State macht Constraints trivial; URDF-Hard-Cap (2.0 rad/s) ist bereits ausreichende Sicherheits-Schicht; Bench-Daten fehlen ohnehin (F.4 deferred Phase 13) |

**Was implementiert wird:**
- TODO-Kommentar in `controllers.real.yaml` wird auf den **neuen
  Wissensstand** aktualisiert (Echo-State + Phase-13-Verfeinerung)
- Stage-G-Done-Kriterium G1 wird **pragmatisch interpretiert**: „Vel/Accel-
  Limits in YAML" ⇒ „URDF-Hard-Cap aktiv, YAML-Override deferred Phase 13"
- Memory `project_phase10_real_yaml_vel_limits.md` bleibt aktiv

**Walking-Sicherheits-Schichten in Phase 13 (alle schon aktiv):**
1. URDF `<limit velocity="2.0" effort="5.0"/>` → JTC-Cap
2. `servo_mapping.yaml pulse_min/max` → Firmware-Hard-Clamp pro Servo (Stages B/C/D/E)
3. URDF Position-Limits ±1.57/±1.50 rad → JTC-Goal-Validation

Diese drei Schichten greifen **Echo-State-unabhängig** und sind in
Phase 10 voll verifiziert. Reicht für Phase-13-Stand-Walking.

---

## Logik-Skizze (Option C — minimal)

### G.0 — `controllers.real.yaml` TODO-Kommentar aktualisieren (~5 min)

Statt YAML-Werte zu ändern wird der Kopf-Kommentar erweitert um:

1. **Echo-State-Erklärung** als Stage-G-Plan-Korrektur-Hauptbegründung
2. **Drei aktive Sicherheits-Schichten** auflisten (URDF + Pulse-Clamp + Position-Limits)
3. **Phase-13-Verfeinerungs-Verweis** wenn Bench-Daten unter Voll-Last da sind

Das ersetzt den alten TODO-Kommentar Z. 19-24 („Vel/Accel-Limits aus
Bench-Trajektorie ableiten und hier einsetzen").

### G.1 — Build + Test (kein YAML-Wert-Edit) (~3 min)

```bash
colcon build --packages-select hexapod_control hexapod_bringup
colcon test --packages-select hexapod_control hexapod_bringup hexapod_hardware
```

**Erwartung:** alle grün, regression-frei. Stage G ändert keinen YAML-Wert
sondern nur Kommentar → kein Verhalten ändert sich, Tests bleiben grün.

### G.2 — Stage-G-Notizen + Phase-13-Pendenz dokumentieren (~5 min)

In `phase_10_progress.md`:
- Stage-G-Bullets abhaken
- Stage-G-Post-Review-Tabelle
- Echo-State-User-Klarstellung als Plan-Korrektur dokumentieren
- Cross-Phase-Verweis auf Memory `project_phase10_real_yaml_vel_limits.md`

### G.3 — Self-Review

CLAUDE.md §4-Pflicht.

---

## (Nicht implementiert — archiviert für Phase-13-Referenz) Option-B-Logik-Skizze

> Folgende Schritte wären gemacht worden wenn G-Q1 nicht **C** gewählt
> worden wäre. Für Phase 13 hier als Referenz.

### G.1-alt — JTC `constraints`-Block ergänzen pro leg-Controller (~10 min)

Pro `leg_X_controller`:

```yaml
leg_X_controller:
  ros__parameters:
    joints:
      - leg_X_coxa_joint
      - leg_X_femur_joint
      - leg_X_tibia_joint
    command_interfaces:
      - position
    state_interfaces:
      - position
    state_publish_rate: 50.0
    action_monitor_rate: 20.0

    # NEW in Stage G — Phase 10 conservative defaults from URDF × 0.7
    constraints:
      stopped_velocity_tolerance: 0.05
      goal_time: 0.5
      leg_X_coxa_joint:
        trajectory: 0.1
        goal: 0.05
      leg_X_femur_joint:
        trajectory: 0.1
        goal: 0.05
      leg_X_tibia_joint:
        trajectory: 0.1
        goal: 0.05
```

**Was die constraints machen:**
- `goal_time: 0.5` — JTC erlaubt 0.5 s Überzug über `time_from_start`, bevor Goal als „abgebrochen" gilt
- `goal_position_tolerance: 0.05 rad` — Joint-Position muss in 0.05 rad (~3°) vom Goal sein bei Trajectory-Ende
- `trajectory: 0.1 rad` — während der Trajectory-Ausführung darf Joint maximal 0.1 rad (~6°) abweichen von der Soll-Kurve
- `stopped_velocity_tolerance: 0.05` — wann gilt der Roboter als „gestoppt"

### G.2 — Vel/Accel-Limits (~5 min)

Diese gehen NICHT in den JTC-Controller-Block, sondern werden vom
**URDF gelesen** (JTC nutzt URDF `<limit velocity="..."/>` als hard cap).
Plus optional ein separater `joint_limits.yaml`-Block, der zur
Laufzeit überschreibt.

**Strategie:** wir lassen URDF velocity=2.0 unverändert (das ist die
*Hardware-Cap*) und ergänzen einen `joint_limits.yaml`-Block mit
**runtime-Override × 0.7**:

```yaml
# joint_limits.yaml (NEU)
joint_limits:
  leg_1_coxa_joint:
    has_velocity_limits: true
    max_velocity: 1.4   # 0.7 × URDF 2.0
    has_acceleration_limits: true
    max_acceleration: 7.0   # konservativ, Phase 13 verfeinert
  # ... 18 Joints insgesamt
```

**Alternativ (einfacher):** Vel/Accel-Limits **nicht in YAML, sondern
durchgehend per URDF**. JTC respektiert URDF-Velocity-Limits automatisch.
Acceleration ist nicht in URDF, würde fehlen.

**Empfehlung Phase 10:** **JTC-constraints reichen für jetzt**. Vel/Accel
Hard-Limits sind in URDF schon konservativ (2.0 rad/s aus Servo-Spec),
zusätzlicher `joint_limits.yaml`-Block ist Phase-13-Polish wenn man
fühlt die URDF-Werte sind nicht konservativ genug.

### G.3 — Smoke-Test (~5 min)

Loopback-Run von F.2 IK-Probe-Skript:

```bash
# Terminal 1
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true

# Terminal 2
python3 ~/hexapod_ws/tools/phase_10_f2_ik_probe.py
```

**Erwartung:**
- Goal akzeptiert (war in Stage F nach „Goal rejected"-Re-Run grün)
- `status=SUCCEEDED` mit den neuen constraints
- Falls JTC jetzt „Goal violated trajectory tolerance" wirft → constraints
  zu eng, Tolerance hochziehen

### G.4 — Build + Test (~3 min)

```bash
colcon build --packages-select hexapod_control hexapod_bringup
colcon test --packages-select hexapod_control hexapod_bringup hexapod_hardware
```

**Erwartung:**
- Build grün (YAML-Syntax-Validierung)
- Test grün: 208/0/20 + 18/0/0 + hexapod_control unverändert

### G.5 — Self-Review

CLAUDE.md §4 Pflicht-Tabelle.

---

## Tests-Liste (Option C — minimal)

| # | Test | Erwartung | Wer |
|---|---|---|---|
| G-T1 | `colcon build --packages-select hexapod_control hexapod_bringup` | grün | Claude |
| G-T2 | `colcon test --packages-select hexapod_control hexapod_bringup hexapod_hardware` | 208/0/20 + 18/0/0 unverändert | Claude |
| G-T3 | YAML-Diff-Inspektion: nur Kommentar-Block ersetzt, **keine YAML-Werte geändert** | sichtbar im Diff | Claude + User |

### Was bewusst NICHT in Stage G getestet wird

- **Kein Smoke-Test** — Stage G ändert keinen YAML-Wert, kein Verhalten
  ändert sich. Test-Suite reicht
- **Real-Modus mit Bench-PSU + Servos** — Stage G ist Doku-only
- **Vel/Accel-Limits aus Bench-CSV** (Phase 13)
- **JTC constraints-Block** (Echo-State macht das wertlos)

---

## Progress-Checkliste (Option C — minimal)

- [ ] G.1 phase_10_stage_g_plan.md (Plan-Doku) finalisiert + User-Freigabe (Option C entschieden)
- [ ] G.2 phase_10_stage_g_test_commands.md (entfällt für Option C — keine User-Smoke-Steps nötig)
- [ ] G.3 `controllers.real.yaml` TODO-Kommentar mit Echo-State-Erklärung + 3-Schicht-Sicherheits-Argument + Phase-13-Verweis aktualisiert
- [ ] G.4 colcon build grün (regression-frei, nur Kommentar geändert)
- [ ] G.5 colcon test grün 208/0/20 + 18/0/0
- [ ] G.6 G-T3 YAML-Inspektion (User): nur Kommentar geändert, keine Werte
- [ ] G.7 Kritischer Self-Review-Tabelle (CLAUDE.md §4-Pflicht)
- [ ] G.8 Stage-G-Notizen + Phase-13-Pendenz-Verweis

**Done-Kriterium G (pragmatisch interpretiert mit Echo-State-Realität):**
`controllers.real.yaml` dokumentiert die Stage-G-Entscheidung; URDF-
Hard-Cap aktiv; Memory `project_phase10_real_yaml_vel_limits.md` bleibt
für Phase 13.

---

## Erwartete Stage-G-Dauer

- G.1 Plan-Doku (diese Datei): ~30 min Claude (erledigt)
- G.2 test_commands.md (entfällt für Option C)
- G.3 YAML-Kommentar-Edit: ~5 min Claude
- G.4–G.5 Build + Test: ~3 min Claude
- G.6 YAML-Inspektion: ~2 min User
- G.7 Self-Review: ~10 min Claude

**Schätzung:** ~50 min Claude + ~2 min User = **~1 h Gesamt**. Kürzeste
Stage der Phase 10.
