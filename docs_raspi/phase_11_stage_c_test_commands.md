# Phase 11 — Stufe C — Test-Kommandos

> **Stage C:** `/servo_pulses` Diagnostic-Topic mit Live-Toggle.
>
> **Plan:** [`phase_11_stage_c_plan.md`](phase_11_stage_c_plan.md)

---

## Vorbedingung

- Stage A + B abgeschlossen + Stage-C-Code committet (= Plugin-Binary
  enthält den `publish_servo_pulses`-Param + Publisher).
- **Wichtig:** wenn vorher noch ein altes Plugin lief, **erst killen**:
  ```bash
  # User's Standard-Kill-Block + sleep 4
  pkill -9 -f "ros2"; pkill -9 -f "rqt"; sleep 4
  ```

---

## Setup pro Test-Session — drei Terminals parallel

### Terminal 1 — Plugin

```bash
cd ~/hexapod_ws
source install/setup.bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

Warten bis Logger zeigt:
```
[hexapod_hardware]: Phase 11 Stage B+C: 72 live-cal params + publish_servo_pulses ...
```

### Terminal 2 — rqt_reconfigure (für Param-Toggle)

```bash
source install/setup.bash
ros2 run rqt_reconfigure rqt_reconfigure
```

Im linken Panel **`hexapodsystem`** anklicken → rechts erscheint die
komplette Param-Liste. Sortierung ist alphabetisch:

1. `pin_0.direction_normal` ... `pin_17.pulse_zero` (72 Pin-Params)
2. **`publish_servo_pulses`** ← als Bool-Checkbox, **unten in der Liste**
3. `use_sim_time` (ganz unten)

> **Falls `publish_servo_pulses` fehlt:** Plugin läuft noch in der
> Stage-B-Version. `ros2 param list /hexapodsystem | grep publish`
> ergibt dann nichts. Plugin neu starten (Vorbedingung oben).

### Terminal 3 — rqt_plot (für Live-Visualisierung)

```bash
source install/setup.bash
ros2 run rqt_plot rqt_plot /hexapodsystem/servo_pulses/data[15]
```

Plot-Fenster öffnet sich. **Initial leer mit Skala 0..1.0** — das ist
normal, sobald Daten fließen rezoomt rqt_plot automatisch auf den
echten Pulse-Bereich (~1000-2000 µs).

---

## Claude-Tests (CI-Pfad)

### C-T1 — colcon build hexapod_hardware grün

```bash
colcon build --packages-select hexapod_hardware
```

**Erwartung:** ✅ `Summary: 1 package finished` (am 2026-05-20 bestätigt).

### C-T2 — colcon test hexapod_hardware grün

```bash
colcon test --packages-select hexapod_hardware
colcon test-result --verbose --test-result-base build/hexapod_hardware
```

**Erwartung:** ✅ 220/0/20 (bestehend, Stage-C-E2E via User-Smoke,
2026-05-20 bestätigt).

### C-T3 — Regression hexapod_gait + hexapod_bringup

```bash
colcon test --packages-select hexapod_gait hexapod_bringup
```

**Erwartung:** ✅ hexapod_gait 20/0/1, hexapod_bringup 18/0/0 (2026-05-20
bestätigt).

---

## User-Smoke-Tests

Pro Test gibt es zwei Wege — **GUI** über rqt_reconfigure (Checkbox)
oder **CLI** über `ros2 param set`. Beides hat exakt denselben Effekt
auf das Plugin. CLI ist schneller fürs Testen, GUI ist näher am
echten Cal-Workflow.

### C-T4 — Default + Topic-Existenz

```bash
# Param-Default lesen
ros2 param get /hexapodsystem publish_servo_pulses
# Erwartung: Boolean value is: False

# Topic ist da (Publisher existiert immer, auch wenn Param off)
ros2 topic list | grep servo_pulses
# Erwartung: /hexapodsystem/servo_pulses

ros2 topic info /hexapodsystem/servo_pulses
# Erwartung: Type: std_msgs/msg/Int32MultiArray, Publisher count: 1
```

### C-T5 — Toggle ein → rqt_plot zeigt Daten

**CLI-Variante** (einfacher fürs Testen):
```bash
ros2 param set /hexapodsystem publish_servo_pulses true
# Erwartung: Set parameter successful
# Plugin-Terminal-Logger: "param updated: publish_servo_pulses = true"
```

**GUI-Variante:**
- In rqt_reconfigure → `hexapodsystem` → unten in der Liste die
  **`publish_servo_pulses`**-Checkbox aktivieren.
- Falls die Checkbox nicht direkt sichtbar: nach unten scrollen (die
  72 Pin-Params kommen alphabetisch vorher).

**Erwartung in rqt_plot:**
- Eine horizontale Linie erscheint bei `pin_15.pulse_zero` aktuellem
  Wert (z.B. 1700 µs falls aus Stage-B noch der set-Wert da ist, oder
  1550 µs falls frisch aus YAML).
- Y-Achse rezoomt sich automatisch auf den Pulse-Bereich.

**Verify zusätzlich (optional):**
```bash
ros2 topic echo /hexapodsystem/servo_pulses --once
# Erwartung: data: [1500, 1500, ..., 1700, ...]  (18 Werte)
```

### C-T6 — Slider mitläuft im Plot

Während Toggle aus C-T5 noch `true` ist:

**CLI-Variante:**
```bash
ros2 param set /hexapodsystem pin_15.pulse_zero 1800
# Erwartung: Set parameter successful
# Plugin-Logger: "cal updated: pin_15.pulse_zero = 1800"
```

**GUI-Variante:**
- In rqt_reconfigure den Slider `pin_15.pulse_zero` von z.B. 1700 → 1800
  ziehen.

**Erwartung in rqt_plot:** Kurve springt sofort von 1700 auf 1800 (1 Tick
= 20 ms Latenz, optisch unmittelbar). Bei kontinuierlichem Slider-Drag in
rqt_reconfigure sieht man ein „mitläuft".

### C-T7 — Toggle aus → Publishing stoppt

**CLI-Variante:**
```bash
ros2 param set /hexapodsystem publish_servo_pulses false
# Erwartung: Set parameter successful
# Plugin-Logger: "param updated: publish_servo_pulses = false"
```

**GUI-Variante:** Checkbox `publish_servo_pulses` in rqt_reconfigure
deaktivieren.

**Erwartung in rqt_plot:**
- Kurve „friert ein" — keine neuen Datenpunkte mehr (X-Achse läuft
  weiter, aber Y-Wert bleibt am letzten Sample stehen, oder die Linie
  bricht ab je nach rqt_plot-Version).

**Topic-Verify:**
```bash
timeout 2 ros2 topic echo /hexapodsystem/servo_pulses --once
# Erwartung: nichts (timeout), weil Publisher nicht mehr feuert
```

---

## Bewusst NICHT getestet in Stage C

- **params_file-Arg in Launch-Files** (Stage D)
- **Preset-YAMLs** (Stage E)
- **Echte HW-Verbindung** — Stage C ist loopback-only

---

## Häufige Stolperfallen

| Symptom | Wahrscheinliche Ursache | Fix |
|---|---|---|
| `publish_servo_pulses` nicht in rqt_reconfigure sichtbar | Plugin läuft noch in alter Stage-B-Version | Plugin killen + relaunch |
| `ros2 topic list` zeigt `/servo_pulses` nicht | Plugin nicht hochgekommen (z.B. wegen YAML-Parse-Error oder fehlendem `loopback_mode:=true`) | Plugin-Terminal auf Errors prüfen |
| rqt_plot zeigt Linie bei 0 statt bei ~1500 | Toggle ist noch `false`, keine Daten fließen | C-T5 ausführen |
| rqt_plot zeigt Skala 0..1.0 trotz Daten | Auto-Range hat noch nicht gegriffen | im rqt_plot rechts-klick → „Autoscale" |
| Topic existiert, aber `echo` zeigt nichts | Param-Toggle off ODER kein Subscriber bei Toggle-Check | `ros2 param get publish_servo_pulses` prüfen; bei `false` siehe C-T5 |

---

## Status-Tracking

Pro Test in [phase_11_progress.md](phase_11_progress.md) abhaken.
