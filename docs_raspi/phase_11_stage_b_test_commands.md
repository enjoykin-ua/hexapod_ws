# Phase 11 — Stufe B — Test-Kommandos

> **Stage B:** hexapod_hardware Plugin Live-Cal Param-Callback + Save-Service.
>
> **Plan:** [`phase_11_stage_b_plan.md`](phase_11_stage_b_plan.md)
> **Tests-Liste-Begründung:** siehe Plan-Doku §Tests-Liste.

---

## Vorbedingung

- Stage A abgeschlossen, hexapod_gait 20/0/1 grün.
- Stage-B-Implementation abgeschlossen (Calibration-API + Plugin-Params +
  Callback + Save-Service).
- Sim-only-Pfad mit `loopback_mode_:=true` möglich (kein echtes Servo2040
  nötig).

---

## Setup pro Test-Session

**Workspace bauen + sourcen:**

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
source install/setup.bash
```

**Plugin im Loopback-Modus starten (Terminal 1):**

```bash
ros2 launch hexapod_bringup real.launch.py loopback_mode:=true
```

> Plugin lädt `servo_mapping.yaml` (leg_6 calibrated, rest defaults),
> Lifecycle-State `inactive` nach launch.

**rqt starten (Terminal 2):**

```bash
ros2 run rqt_reconfigure rqt_reconfigure
```

> Im linken Panel **`hexapodsystem`** (lowercase!) auswählen (Name kommt aus dem
> URDF `<ros2_control name="HexapodSystem">` — von ros2_control zu lowercase normalisiert für ROS-Node-Konvention). Tree mit 72 Pin-Params
> erscheint rechts (`pin_0` .. `pin_17`, jeweils mit 4 Untereinträgen).
>
> **Wichtig:** `/controller_manager` ist NICHT der Plugin-Node — der
> ist fast leer (nur Controller-Manager-eigene Settings).
> `HexapodSystem` ist der Hardware-Component-Node, hier landen die
> Live-Cal-Params.
>
> Real-Node-Name verifizieren falls unsicher:
> ```bash
> ros2 node list | grep -i hexa
> ros2 param list /hexapodsystem | head -5
> ```

---

## Claude-Tests (CI-Pfad)

### B-T1 — colcon build hexapod_hardware grün

```bash
cd ~/hexapod_ws
colcon build --packages-select hexapod_hardware
```

**Erwartung:** `Summary: 1 package finished` ohne Errors.

### B-T2 — colcon test hexapod_hardware grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --verbose --test-result-base build/hexapod_hardware
```

**Erwartung:**

- Bestehende 208/0/20 weiterhin grün.
- Neue Calibration-Tests grün (`test_calibration.cpp`):
  - `Calibration::update_servo_cal` valide Werte
  - `Calibration::update_servo_cal` Rejection bei pulse-Constraints
  - `Calibration::snapshot` thread-safety (kein Daten-Race)
  - `Calibration::save_to_file` schreibt valides YAML
  - `Calibration::save_to_file` erzeugt Timestamp-bak
- Neue Plugin-Param-Tests grün (`test_param_callback_plugin.cpp` o.ä.):
  - 72 Params deklariert mit Range
  - Live-Update propagiert in Calibration
  - Atomic-Reject bei Cross-Constraint-Verletzung
  - Direction-Update in active-State rejected
  - Direction-Update in inactive-State akzeptiert

### B-T3 — Keine Regression in hexapod_gait / hexapod_bringup

```bash
colcon test --packages-select hexapod_gait hexapod_bringup --event-handlers console_direct+
```

**Erwartung:** hexapod_gait 20/0/1, hexapod_bringup 18/0/0 unverändert.

---

## User-Smoke-Tests (loopback_mode, manuell)

### B-T4 — Live-Update via `ros2 param set`

```bash
ros2 param get /hexapodsystem pin_15.pulse_zero
# erwartet: 1550 (aus servo_mapping.yaml leg_6 coxa)

ros2 param set /hexapodsystem pin_15.pulse_zero 1600
# erwartet: Set parameter successful
```

**Erwartung:**

- Logger im Plugin-Terminal: `cal updated: pin_15.pulse_zero=1550 → 1600`
- `ros2 param get` zeigt jetzt 1600.

> **Hinweis:** Plugin-Node-Name kommt aus dem URDF
> (`<hardware><name>HexapodSystem</name>`). Mit `ros2 node list` bzw.
> `ros2 param list /hexapodsystem` verifizieren.
>
> **Fallstrick:** Falls statt `/hexapodsystem` versehentlich
> `/controller_manager` als Node-Name verwendet wird: dort hat
> Controller-Manager `allow_undeclared_parameters=true`, daher würde
> `ros2 param set` ohne Fehler einen unbenutzten Param-Eintrag
> erzeugen — das Plugin liest aber NICHT von `/controller_manager`.

### B-T5 — rqt_reconfigure Tree-Slider

In rqt_reconfigure den Plugin-Node anklicken → Tree zeigt 18 Pin-Gruppen,
jede mit 4 Untereinträgen.

- `pin_15` ausklappen → `pulse_zero`-Slider von 1600 auf 1700 ziehen
- Logger meldet Update
- `pin_5` (uncalibrated, default 1500) → von 1500 auf 1550 ziehen
- Werte bleiben nach Slider-Release stabil

### B-T6 — Atomic-Reject bei Cross-Constraint-Verletzung

```bash
# Single-update: würde Constraint pulse_min < pulse_zero brechen
ros2 param set /hexapodsystem pin_15.pulse_min 1700
# erwartet: Set parameter failed
# Reason: "pin_15: pulse_min=1700 must be < pulse_zero=1600"

# Atomic-update: beide zusammen valide
cat > /tmp/atomic_pin15.yaml <<'EOF'
/hexapodsystem:
  ros__parameters:
    pin_15:
      pulse_min: 1700
      pulse_zero: 1750
EOF
ros2 param load /hexapodsystem /tmp/atomic_pin15.yaml
# erwartet: beide übernommen
```

### B-T7 — `/save_calibration` Service

```bash
# 1. Aktuelles YAML sichern (User-Vorsicht, optional)
cp src/hexapod_hardware/config/servo_mapping.yaml /tmp/before_save.yaml

# 2. Service aufrufen
ros2 service call /save_calibration std_srvs/srv/Trigger
# erwartet: success: true, message: "saved 18 cals to <path>"

# 3. Verifikation
ls -la src/hexapod_hardware/config/servo_mapping.yaml*
# erwartet: servo_mapping.yaml (neu) + servo_mapping.yaml.bak-YYYYMMDD-HHMMSS

# 4. Inhalt prüfen
diff /tmp/before_save.yaml src/hexapod_hardware/config/servo_mapping.yaml.bak-*
# erwartet: kein Diff (bak ist Original)

grep -A4 'pin 15' src/hexapod_hardware/config/servo_mapping.yaml | head
# oder
ros2 param get /hexapodsystem pin_15.pulse_zero
# erwartet: 1750 (= unsere Live-Werte)
```

### B-T8a — Direction-Flip in `inactive`-State → Accept

**Voraussetzung:** Plugin im `inactive`-Lifecycle-State. **Wichtig:**
Hardware-Components haben ihr **eigenes** Lifecycle (über
`ros2 control`-CLI, NICHT `ros2 lifecycle` — letzteres ist nur für
`LifecycleNode`s, das Plugin ist keine).

```bash
# Aktuellen State prüfen
ros2 control list_hardware_components
# Erwartung: HexapodSystem state.label = active (nach real.launch.py-Default)

# Hardware in inactive forcen — Controllers vorher deaktivieren:
ros2 control set_controller_state joint_state_broadcaster inactive
for leg in leg_1 leg_2 leg_3 leg_4 leg_5 leg_6; do
  ros2 control set_controller_state ${leg}_controller inactive
done
ros2 control set_hardware_component_state HexapodSystem inactive

# Re-check
ros2 control list_hardware_components
# Erwartung: HexapodSystem state.label = inactive

# Jetzt Direction-Flip
ros2 param set /hexapodsystem pin_15.direction_normal false
# erwartet: Set parameter successful
# Logger: cal updated: pin_15.direction_normal = false (-1)
```

### B-T8b — Direction-Flip in `active`-State → Reject

**Voraussetzung:** Plugin im `active`-State (Default nach
`real.launch.py` durch automatische Controller-Spawn-Sequenz).

```bash
ros2 control list_hardware_components
# Erwartung: HexapodSystem state.label = active

ros2 param set /hexapodsystem pin_15.direction_normal true
# erwartet: Set parameter failed
# Reason: "pin_15.direction_normal can only change in 'inactive' lifecycle state
#          (active-flip = servo-sprung um 180°)"
```

---

## Bewusst NICHT getestet in Stage B

- **`/servo_pulses` Diagnostic-Topic** (Stage C)
- **params_file-Arg in Launch-Files** (Stage D)
- **Preset-YAMLs** (Stage E)
- **Echte HW-Verbindung** — Stage B ist Plugin-Level mit loopback_mode_

---

## Status-Tracking

Pro Test in [phase_11_progress.md](phase_11_progress.md) abhaken.
