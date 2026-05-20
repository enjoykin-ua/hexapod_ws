# Phase 11 — Stufe A — Test-Kommandos

> **Stage A:** gait_node Param-Callback für Live-Tuning via `ros2 param set`
> und `rqt_reconfigure`.
>
> **Plan:** [`phase_11_stage_a_plan.md`](phase_11_stage_a_plan.md)
> **Tests-Liste-Begründung:** siehe Plan-Doku §Tests-Liste.

---

## Vorbedingung

- Phase 10 abgeschlossen, hexapod_gait baut grün.
- Sim-only (Gazebo + RViz), keine HW.
- Stage-A-Implementation abgeschlossen (Param-Descriptors + Callback +
  Helper-Methoden + Edge-Case-Handling).

---

## Setup pro Test-Session

**Workspace bauen + sourcen:**

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait
source install/setup.bash
```

**Sim-Stack starten (Terminal 1):**

```bash
ros2 launch hexapod_bringup sim.launch.py
```

> Startet Gazebo + RSP + Controllers (joint_state_broadcaster + 6×
> leg-controller). **Kein RViz** — das muss separat gestartet werden.

**RViz starten (Terminal 1b):**

```bash
ros2 run rviz2 rviz2 -d $(ros2 pkg prefix hexapod_description)/share/hexapod_description/config/view.rviz
```

> RViz mit projekt-spezifischer View-Config. Hexapod sollte in
> Stand-Pose erscheinen sobald die Controller in Terminal 1 spawnen.

**gait_node starten (Terminal 2):**

```bash
ros2 launch hexapod_gait gait.launch.py
```

> Roboter sollte in Standing-Pose stehen (STATE_STANDING).

**rqt starten (Terminal 3):**

```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

> Im linken Panel `/gait_node` anklicken → Slider erscheinen rechts.

---

## Claude-Tests (CI-Pfad)

### A-T1 — colcon build hexapod_gait grün

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_gait
```

**Erwartung:** Build summary `Summary: 1 package finished` ohne Errors.

### A-T2 — colcon test hexapod_gait grün

```bash
colcon test --packages-select hexapod_gait --event-handlers console_direct+
colcon test-result --verbose --test-result-base build/hexapod_gait
```

**Erwartung:**

- Bestehende Linter-Tests (`test_copyright`, `test_flake8`, `test_pep257`)
  weiterhin grün.
- Neue Param-Callback-Tests (siehe Plan §Tests-Liste) grün:
  - `test_param_set_body_height_updates_state`
  - `test_param_set_invalid_body_height_rejected`
  - `test_param_set_body_height_rejected_while_walking`
  - `test_param_set_tick_rate_restarts_timer`
  - `test_param_set_gait_pattern_loads_preset`
  - `test_param_descriptor_has_range`
  - `test_param_atomic_cross_constraint_rejected`
- launch_testing-Smoke (`test_gait_param_live`) grün.

### A-T3 — Keine Regression in hexapod_bringup / hexapod_hardware

```bash
colcon test --packages-select hexapod_bringup hexapod_hardware --event-handlers console_direct+
colcon test-result --verbose --test-result-base build/hexapod_bringup
colcon test-result --verbose --test-result-base build/hexapod_hardware
```

**Erwartung:** `hexapod_bringup` 18/0/0, `hexapod_hardware` 208/0/20
(20 Skipped wie vor Stage A).

---

## User-Smoke-Tests (in Sim, manuell)

> Setup oben durchführen. Pro Test: Erwartung beobachten, Status melden
> (kurze Status-Meldung reicht — kein Vollausgaben-Paste, Memory
> `feedback_interactive_stage_test_doc.md`).

### A-T4 — `ros2 param set` ändert `body_height` live (STANDING)

**Voraussetzung:** Roboter in STATE_STANDING (kein cmd_vel publisht).

```bash
# Terminal 4 (neu)
ros2 param get /gait_node body_height
# → erwartete Anzeige: Double value is: -0.052

ros2 param set /gait_node body_height -0.060
# → Set parameter successful
```

**Erwartung:**

- gait_node loggt `body_height -> -0.0600 m`
- In RViz / Gazebo sieht man, dass der Hexapod sanft tiefer geht
  (Body sinkt ~8 mm).
- `ros2 param get /gait_node body_height` zeigt jetzt `-0.060`.

### A-T5 — rqt_reconfigure Slider verschieben (STANDING)

In rqt_reconfigure `/gait_node` auswählen → `body_height`-Slider von
-0.052 auf -0.040 schieben.

**Erwartung:**

- Hexapod **senkt sich** live in Gazebo (Body sinkt ~12 mm).
  Erklärung: `body_height` ist Foot-Z im Bein-Frame; weniger negativ =
  Foot näher am Coxa-Joint = Body näher zum Boden.
- gait_node-Logger meldet `param updated: body_height=-0.04`.
- Slider bleibt auf -0.040 stehen.

Weitere Slider durchprobieren (`step_height`, `step_length_max`,
`cycle_time` — letzteres nur in STANDING-State):

- `step_height` 0.03 → 0.05 (Erwartung: nächster Walk hebt Beine höher,
  in STANDING aber keine sichtbare Bewegung — nur Log)
- `step_length_max` 0.05 → 0.08 (analog, kein Live-Effekt in STANDING,
  aber Log + Param-Get bestätigen Update)

### A-T6 — `gait_pattern` wechseln (STANDING)

In rqt_reconfigure `gait_pattern` Text-Feld von `tripod` auf
`single_leg_3` ändern (rqt zeigt String-Feld, kein Dropdown).

**Erwartung:**

- gait_node-Logger meldet `param updated: gait_pattern=single_leg_3`
  (gesetztes Param wird übernommen, **kein sichtbarer Roboter-Effekt
  in STANDING** — Pattern wirkt erst beim Walk).
- Wenn anschließend cmd_vel gesendet wird (siehe A-T8): nur leg_3 bewegt
  sich. Das ist der eigentliche Pattern-Beleg.
- Test mit invalidem Pattern (z.B. `tripod_xyz`) → SetParametersResult
  fail, Logger meldet *kein* `param updated`, Wert bleibt unverändert.

### A-T7 — Invalider Wert wird abgelehnt

```bash
ros2 param set /gait_node body_height -1.0
# → Erwartung: Set parameter failed
#   Reason: "body_height=-1.0 outside [-0.080, -0.030]"
```

Analog in rqt: Slider außerhalb Range ziehen (rqt sollte den Range schon
visuell begrenzen, aber Direct-Eingabe testen).

**Erwartung:** Param-Wert bleibt unverändert auf vorherigem Wert.

### A-T8 — Param-Update während WALKING wird abgelehnt

**Voraussetzung:** Roboter in WALKING (cmd_vel publishen, Terminal 4):

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 0.02}}' &
# Roboter läuft nun langsam vorwärts
```

Während dessen Param-Update versuchen:

```bash
ros2 param set /gait_node body_height -0.060
# → Erwartung: Set parameter failed
#   Reason: "body_height update rejected: state=WALKING, must be STANDING"
```

cmd_vel stoppen:

```bash
kill %1
# oder Ctrl+C im cmd_vel-Terminal
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{}'
```

Nach Stopp (zurück in STANDING):

```bash
ros2 param set /gait_node body_height -0.060
# → erwartet: Set parameter successful
```

### A-T9 — Cross-Param-Constraint atomic-all-or-nothing

Aktueller Zustand: `body_height = -0.052`, `body_height_min = -0.080`,
`body_height_max = -0.030`.

```bash
# Single update bricht Constraint
ros2 param set /gait_node body_height_min -0.040
# → Erwartung: Set parameter failed
#   Reason: "body_height_min=-0.040 > body_height=-0.052 (invalid)"

# Atomic-Update mit gleichzeitiger body_height-Anpassung über YAML-Load
cat > /tmp/atomic_test.yaml <<'EOF'
/gait_node:
  ros__parameters:
    body_height: -0.035
    body_height_min: -0.040
EOF
ros2 param load /gait_node /tmp/atomic_test.yaml
# → Erwartung: beide Updates akzeptiert
ros2 param get /gait_node body_height
# → -0.035
ros2 param get /gait_node body_height_min
# → -0.040
```

---

## Bewusst NICHT getestet in Stage A

- **Plugin-Param-Callback** (Stage B)
- **`/servo_pulses` Topic** (Stage C)
- **params_file-Arg in Launch-Files** (Stage D)
- **Preset-YAMLs** (Stage E)
- **Echte HW-Verbindung** — Stage A ist Sim-only
- **Oszi/Logic-Analyzer-Pulses** — Phase 13

---

## Status-Tracking

Nach jedem Test Status in [phase_11_progress.md](phase_11_progress.md)
unter Stage A pflegen:

- `[x]` für grün
- `[!]` für Issue (mit Kurz-Hinweis)

Bei Issue: erst Fix + Re-Test, dann Stage A als „fertig" melden.
