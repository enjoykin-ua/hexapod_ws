# Phase 11 — Stufe B — Plan

> **Status:** Plan, in Vorbereitung der Implementation. **Pending User-Freigabe der 9 offenen Fragen B-Q1..B-Q9.**
>
> **Parent-Plan:** [`phase_11_param_gui.md`](phase_11_param_gui.md)
> Stufe B — hexapod_hardware Plugin Live-Cal Param-Callback (C++).
>
> **Vorbedingung:** Stage A abgeschlossen, gait_node Live-Param-Pattern
> etabliert (`_ParamSpec`-Tabelle, atomic-all-or-nothing-Validation,
> `param updated`-Logging) — siehe [phase_11_stage_a_plan.md](phase_11_stage_a_plan.md).

---

## Ziel

`hexapod_hardware`-Plugin so erweitern, dass **alle 72 Servo-Cal-Werte
(18 Pins × 4 Felder)** live per `ros2 param set` änderbar sind. Plus
**`/save_calibration`-Service** der die aktuellen Live-Werte zurück in
`servo_mapping.yaml` schreibt.

**Was geht aktuell schon:** Calibration wird in `on_init` aus
`servo_mapping.yaml` geladen, in `write()` (50 Hz Controller-Thread)
für rad→µs-Math genutzt. Werte sind statisch nach Plugin-Start.

**Was geht NICHT:** Live-Anpassung. Cal-Iteration braucht heute
Edit-YAML → Restart-Plugin → Lifecycle-Re-Activate. Bei Phase-10-leg-6
hat das pro Servo 5–10 Iterationen gekostet (siehe Phase-10-Retro).

**Was Stage B liefert:**

1. Plugin deklariert pro Pin 4 ROS-Params (`pin_<N>.pulse_min`,
   `pin_<N>.pulse_zero`, `pin_<N>.pulse_max`, `pin_<N>.direction_normal`),
   sliderbar in rqt_reconfigure.
2. `on_set_parameters_callback` aktualisiert `Calibration` live + thread-
   sicher mit `write()`.
3. `/save_calibration`-Service schreibt Live-Werte zurück in
   `servo_mapping.yaml` (mit `.bak`-Backup gegen Daten-Verlust).

---

## 🔍 Pre-Implementation Code-Inspection (für Continuity)

> **Wichtig für Continuity** (z.B. Chat-Reset): bevor Code-Edit anfängt,
> diese Stellen lesen damit Stage B nicht erfindet was schon existiert.

### Plugin-Struktur (Stand 2026-05-20)

**File:** [`src/hexapod_hardware/include/hexapod_hardware/hexapod_system.hpp`](../src/hexapod_hardware/include/hexapod_hardware/hexapod_system.hpp)

- C++ Plugin via pluginlib, Klasse `HexapodSystemHardware : public hardware_interface::SystemInterface`
- Member `Calibration calibration_` (private) — 18-Array von `ServoCalibration`
- Aktuelle `hardware_parameters`-Reads in `on_init` (line 87-113):
  `serial_port`, `calibration_file`, `loopback_mode` — über URDF
  `<param>`-Block, **nicht** über ROS-Param-Service. Statisch nach Init.
- `write()` (line 594-660) ruft `calibration_.radians_to_pulse_us(...)`
  18 mal pro Tick → Hot-Path
- **`get_node()`** verfügbar via Basis-Klasse `HardwareComponentInterface::get_node()`
  ([ros2_control Jazzy](/opt/ros/jazzy/include/hardware_interface/hardware_interface/hardware_component_interface.hpp#L580))
  — liefert `rclcpp::Node::SharedPtr` nach `on_init`

### Calibration-API (Stand 2026-05-20)

**File:** [`src/hexapod_hardware/include/hexapod_hardware/calibration.hpp`](../src/hexapod_hardware/include/hexapod_hardware/calibration.hpp)

- `ServoCalibration`-Struct mit Feldern `joint_name`, `pulse_min/zero/max`
  (int16_t), `direction` (int8_t ∈ {-1,+1}), `joint_lower/upper` (double)
- **Aktuell nur Read-API:** `at()`, `radians_to_pulse_us`,
  `pulse_us_to_radians`, `output_idx_for_joint`
- **Schreibe-API** nur durch `load_from_file/string` (komplettes Reload)
  und `set_joint_limits` (URDF-Limits, nicht Cal-Werte)
- **Keine Thread-Sicherheit aktuell** — single-threaded by convention
  (alles im on_init oder im Controller-Thread)
- Validation in `load_from_string` (line 94 in calibration.cpp):
  pulse_min < pulse_zero < pulse_max, alle ∈ [800, 2200] µs,
  direction ∈ {-1, +1}

### YAML-Format

**File:** [`src/hexapod_hardware/config/servo_mapping.yaml`](../src/hexapod_hardware/config/servo_mapping.yaml)

- Header: 60+ Zeilen Kommentar mit Pin-Convention, Direction-Convention,
  Pulse-Calibration-Geschichte
- Top-Level: `version`, `phase`, `status`, `calibrated_at`
- `defaults`-Block: `pulse_min: 500`, `pulse_max: 2500`, `pulse_zero: 1500`, `direction: 1`
- `servo2040_output_to_joint`-Map: 18 Pins, jeder mit mindestens `joint:`-Feld;
  optional pro-Pin Override für `pulse_min/zero/max/direction`,
  plus Metadaten `status`/`calibrated_at`/Kommentare
- Pins ohne Override fallen auf `defaults` zurück (host-side merge im Loader)

### Existierende Tests

**File:** [`src/hexapod_hardware/test/`](../src/hexapod_hardware/test/)

- `test_calibration.cpp` (722 Zeilen) — vollständige YAML-Load + Math-Tests
- `test_hexapod_system.cpp` (1390 Zeilen) — Plugin-Lifecycle + Loopback-Tests
- `test_plugin_registration.cpp` — pluginlib-Smoke
- gtest-basiert; Pattern: `class TestFixture : public ::testing::Test`

**Aktuell 208 passed, 0 failed, 20 skipped.**

---

## ⚠️ Kritische Punkte (Self-Review der Plan-Doku, vor Code-Beginn)

### 1. Thread-Safety zwischen `write()` und Param-Callback

`write()` läuft im controller_manager-Thread (50 Hz), Param-Callback im
rclcpp-Param-Service-Thread. Beide greifen auf `Calibration::servos_`
zu — Race-Condition garantiert ohne Sync.

**Optionen:** siehe B-Q5 unten.

### 2. YAML-Save überschreibt Cal-File mit Datenverlust-Potential

`servo_mapping.yaml` hat 60+ Zeilen Header-Kommentar + pro-Pin
historische Kommentare + Phase-10-Stage-I-`status: calibrated`-Marker.
Naiver yaml-cpp-Emit verliert ALLES.

**Empfehlung:** `.bak`-Backup vor jedem Save + flacher Output (alle 18
Pin-Felder explizit) + Header-Template mit „auto-generated"-Banner.
**Verbessern später** (Stage E/F oder Phase 13): Roundtrip-Preserving.

### 3. Slider-Drag während aktiver HW = Servo-Sprung

Wenn User in rqt `pin_15.pulse_zero` von 1550 auf 1700 zieht, springt
Servo sofort beim nächsten `write()`-Tick (~20 ms später) um 150 µs ≈ 15°.
Bei Hexapod-Bench mit aufgehängten Beinen ist das ok (= Sinn von
Live-Cal), bei Robotik mit Bodenkontakt potentiell Crash-Risiko.

**Empfehlung:** **Always-allow** im Stage-B-Scope (Live-Cal IST der
Zweck). Sicherheit via Range-Cap (pulse-Wert geclamped auf [800, 2200]
µs durch Descriptor) + Cross-Constraint `pulse_min < pulse_zero <
pulse_max`. Im README + Test-Doku: „Bench-Setup mit aufgehängten Beinen".

### 4. Direction-Flip mid-WALK = Bein dreht 180°

Wenn User `pin_15.direction_normal` von true auf false flippt während
Plugin aktiv: nächster `write()` liefert pulse_us mit umgekehrtem
Vorzeichen → Servo dreht in Gegenrichtung → mechanisch katastrophal.

**Empfehlung:** Direction-Flip akzeptieren aber **mit deutlicher Warnung
im Logger** + nur in `inactive`-Lifecycle-State erlauben (analog
Stage-A-STANDING-only). Active-State = Live-Cal nur Pulse-Werte
erlaubt, Direction read-only.

### 5. 72 Params = unübersichtlich in rqt_reconfigure

Ein Block mit 72 Slidern wäre nicht navigierbar. Namespace-Hierarchie
(`pin_15.pulse_min`) gruppiert in rqt automatisch.

**Empfehlung:** Punkt-Namespace `pin_<N>.<field>`. rqt zeigt
ausklappbare Tree-Struktur.

### 6. Cross-Constraint-Validation für 18 Pins

Aktuell: pulse_min < pulse_zero < pulse_max gilt **pro Pin**. Bei
Cross-Update (z.B. `ros2 param load` aus YAML mit allen 72 Werten)
müssen alle 18 Tripel zusammen valide sein.

**Empfehlung:** atomic-all-or-nothing-Validation analog Stage A. Pro
Pin Tripel-Check, bei einem einzigen Fail kompletter Rollback.

### 7. `joint_lower`/`joint_upper` bleiben URDF-only

Die URDF-`<limit>`-Werte werden in `on_init` per `set_joint_limits`
gesetzt — sind **nicht** in `servo_mapping.yaml` und sollten **nicht**
live tunbar sein (URDF ist die Source of Truth für Joint-Limits).

**Empfehlung:** Stage B exponiert NICHT `joint_lower`/`joint_upper` als
Params. Klar dokumentieren.

### 8. Plugin hat keinen eigenen Node-Spin

`get_node()` liefert den controller_manager's Node, aber das Plugin
spinnt selbst nicht. Param-Service läuft im controller_manager-Executor
— Callback wird also synchron darin aufgerufen.

**Konsequenz:** kein Locking-Issue wenn `write()` und Param-Callback im
selben Executor laufen würden — aber Standard ist
ControllerManager-MultiThreadedExecutor mit separatem Realtime-Thread
für read/write. Daher: **immer Locking annehmen.**

### 9. Save-Service-API: Custom Message oder Trigger?

`std_srvs/Trigger` ist Standard, hat aber kein Argument-Feld. Custom
Service erlaubt Output-Path-Arg aber bringt neue Message-Definition.

**Empfehlung:** Trigger ohne Args, schreibt zurück in `calibration_file_`
(aus URDF) mit automatischem `.bak`-Backup. Wenn anderes File: User
ändert URDF + Restart (selten).

---

## Plan-Review-Korrekturen (2026-05-20, vor Code-Beginn)

Sechs Findings aus kritischem Plan-Review nach User-Bestätigung
B-Q4/B-Q7/B-Q9. Vor Implementation eingearbeitet:

### F1 — Timestamp-Suffix für `.bak`-Backups

**Problem:** Plan hatte `.bak` als einzige Datei — Save 2 würde Save 1
überschreiben, Original ginge bei wiederholter Cal-Session verloren.

**Fix:** **Timestamp-Suffix** `servo_mapping.yaml.bak-YYYYMMDD-HHMMSS`.
Jeder Save erzeugt ein eindeutiges Backup, nichts wird je überschrieben.
Pro YAML ~4 KB → 1000 Sessions = 4 MB, vernachlässigbar.

### F2 — Lifecycle-State via eigenen Member statt `get_lifecycle_state()`

**Problem:** Plan sagte `get_node()->get_lifecycle_state()` — aber
`get_node()` liefert `rclcpp::Node::SharedPtr`, nicht `LifecycleNode`.
Diese API existiert so nicht.

**Fix:** Plugin trackt seinen eigenen Lifecycle-State in einem
`std::atomic<bool> is_active_` Member. Set in `on_activate` (true) und
`on_deactivate` (false). Param-Callback liest das atomic flag.

```cpp
// in hexapod_system.hpp
std::atomic<bool> is_active_{false};

// in on_activate (am Ende, vor SUCCESS):
is_active_.store(true);

// in on_deactivate (am Anfang):
is_active_.store(false);

// im param-callback:
if (param.name.endswith(".direction_normal") && is_active_.load()) {
  return SetParametersResult{false, "direction can only change in inactive"};
}
```

### F3 — CMakeLists.txt + package.xml Update

**Problem:** Stage B fügt `std_srvs/Trigger`-Service hinzu — neue
Build-Dependency.

**Fix:** Sub-Stage B.4 erweitert um:
- `package.xml`: `<depend>std_srvs</depend>` hinzufügen
- `CMakeLists.txt`: `find_package(std_srvs REQUIRED)` +
  `ament_target_dependencies(${PROJECT_NAME} std_srvs ...)` ergänzen

### F4 — README-Update als Pflicht-Bullet

**Problem:** Memory `feedback_stage_readme_and_concepts.md` verlangt
README-Pflege pro Stage — fehlte in Progress-Checkliste.

**Fix:** Neue Sub-Stage B.12a — README hexapod_hardware um
„Phase-11-Stage-B Live-Cal-Quick-Start" erweitern:
- Wie die 72 Pin-Params heißen
- Wie `/save_calibration` aufgerufen wird
- Wie Backup-Files funktionieren (Timestamp-Suffix)
- Direction-Restriction im active-State

### F5 — YAML-Save-Format konkretisieren

**Problem:** Plan sagte „flat ohne defaults" — unklar wie der
defaults-Block behandelt wird (entfernen? leeren?).

**Fix:** **`defaults`-Block bleibt erhalten** (Schema-Compat mit
existierendem Loader), aber **jeder Pin hat ALLE 4 Cal-Felder
explizit** — keine Implicit-Inheritance mehr. Verlust: User-Diff zu
Original größer. Vorteil: vollständig deterministisch + Loader-Code
ändert sich nicht.

**Beispiel-Output:**
```yaml
# Auto-generated by /save_calibration (Phase 11 Stage B)
# Original-Header in servo_mapping.yaml.bak-<timestamp>
version: 1
phase: 11
status: calibrated
calibrated_at: "2026-05-20T14:30:15"

defaults:           # behalten für Schema-Compat, alle Pins überschreiben
  pulse_min:  500
  pulse_max:  2500
  pulse_zero: 1500
  direction:  1

servo2040_output_to_joint:
  0:
    joint: leg_1_coxa_joint
    pulse_min:  500
    pulse_zero: 1500
    pulse_max:  2500
    direction:  1
  # ... 17 weitere Pins, alle Felder explizit
```

### F6 — Tmpdir-Fixture-Pattern für Save-Service-Tests

**Problem:** Filesystem-Tests heikel — bestehende Patterns aus
`test_calibration.cpp` nicht referenziert.

**Fix:** B.5 (Tests) erweitert um expliziten Hinweis: vor
Test-Implementation `grep -n "tmpdir\|filesystem\|create_temp" test_calibration.cpp`
ausführen und das bestehende Tmpdir-Pattern übernehmen (statt eigenes
zu erfinden).

### F7 & F8 — Vorab-Notizen für Self-Review

Nicht plan-blocker, in Self-Review explizit prüfen:

- **F7:** Atomic-Validation + Lifecycle-State-Race-Möglichkeit (User
  ändert Direction während User parallel Lifecycle-Deactivate triggert).
  Praktisch irrelevant (Sekunden vs. Millisekunden), aber als
  🟡-Punkt in Self-Review notieren.
- **F8:** User-Smoke B-T8 wird in zwei Sub-Tests gesplittet:
  - **B-T8a:** Direction-Flip in `inactive`-State → accept
  - **B-T8b:** Direction-Flip in `active`-State → reject

---

## Architektur-Entscheidungen (vor User-Freigabe)

### A. Param-Namensschema

**Empfehlung:** **Punkt-Namespace** `pin_<N>.<field>` (analog ROS2-
Standard für hierarchische Params).

**Beispiele:**
- `pin_15.pulse_min` (int)
- `pin_15.pulse_zero` (int)
- `pin_15.pulse_max` (int)
- `pin_15.direction_normal` (bool)

**Verworfen:** Flat-Namespace `pin_15_pulse_min` (1 Underscore-Variante
geht in `ros2 param`-Tools schlecht zu pattern-matchen).

### B. Param-Typen

**Pulse-Werte:** **Integer** mit `IntegerRange(800, 2200, 1)` µs.
Native für int16_t. rqt zeigt Integer-Slider.

**Direction:** **Bool** `direction_normal` (true = +1, false = -1).
User-freundlicher als `direction: -1` Integer. Internal Mapping in
Apply-Logic.

**Verworfen:** Integer-Range(-1,+1,2) für Direction — rqt-Slider mit
nur 2 valid steps wirkt kaputt.

### C. ParameterDescriptor-Tabelle (analog `_GAIT_PARAMS`)

**Empfehlung:** **Vector von `ParamSpec`-Structs** in C++ — analog
Stage-A-`_GAIT_PARAMS`-Pattern. Generierung aus 18 Pins × 4 Feldern via
Helper. Single Source of Truth.

```cpp
// Pseudocode
struct PinParamSpec {
  int pin;
  std::string field;          // "pulse_min" etc.
  std::string param_name;     // "pin_15.pulse_min"
  // Range + default werden dynamisch aus Calibration entnommen
};

// generated in on_init:
std::vector<PinParamSpec> _all_pin_params;
for (int pin = 0; pin < NUM_SERVOS; ++pin) {
  _all_pin_params.push_back({pin, "pulse_min", "pin_" + N + ".pulse_min"});
  // ... 3 weitere
}
```

### D. Thread-Sicherheit Calibration ↔ write()

**Empfehlung Option A: `std::mutex` in `Calibration`.**

```cpp
class Calibration {
 public:
  // Setter (Stage B neu): atomic update of one servo's cal
  void update_servo_cal(int output_idx, const ServoCalibration & c);
  // Read-Accessor (Stage B neu, lockt):
  ServoCalibration snapshot(int output_idx) const;
  // Existing: radians_to_pulse_us etc. — lockt internal
 private:
  mutable std::mutex mutex_;
  std::array<ServoCalibration, NUM_SERVOS> servos_;
};
```

Hot-path-Overhead: 18 × Lock/Tick × 50 Hz = 900 Locks/s, bei nicht-
contention ~50 ns/Lock = 45 µs/s Overhead. Vernachlässigbar bei 20 ms
Tick-Budget.

**Verworfen Option B: `std::shared_ptr<const Calibration>` mit atomic
swap.** Sauberer aber neuer Stil + Copy-Cost bei Param-Update. Stage B
priorisiert Einfachheit; Option B als Future-Optim falls Lock-Contention
messbar.

### E. STANDING-only-Äquivalent: Lifecycle-Check

**Empfehlung:** Pulse-Werte (pulse_min/zero/max) **always allow** — Sinn
von Live-Cal. Direction **nur in `inactive`-Lifecycle-State** akzeptieren
(weil Mid-Active-Direction-Flip = Servo-Sprung um 180°).

```cpp
// Pseudocode in callback
if (param.endswith(".direction_normal") &&
    get_node()->get_lifecycle_state() == active) {
  return SetParametersResult(false,
    "direction_normal can only be changed in 'inactive' lifecycle state "
    "(active-flip = servo-sprung um 180°)");
}
```

### F. Save-Service-API

**Empfehlung:** `std_srvs/Trigger`-Service `/save_calibration`, schreibt
nach `calibration_file_` (aus URDF) mit `.bak`-Backup. Flat YAML-Output
(alle 18 Pins explizit, keine defaults-Inheritance) + Header-Template
mit „auto-generated by save_calibration"-Banner.

**Verworfen:**
- Custom-Service mit Output-Path-Arg: bringt neue Message-Def, selten
  gebraucht
- Roundtrip-Preserving YAML: hoher Aufwand, Phase 13 oder später

### G. Atomic-all-or-nothing-Validation (analog Stage A)

**Empfehlung:** Pro Pin Cross-Constraint pulse_min < pulse_zero <
pulse_max, plus alle pulse-Werte ∈ [800, 2200] µs, alle Updates
zusammen prüfen. Bei einem Fail: kompletter Rollback, kein partieller
State-Change.

---

## Offene Fragen für User-Review (B-Q1..B-Q9)

| # | Frage | Empfehlung | Alternative |
|---|---|---|---|
| **B-Q1** Param-Namensschema | **✅ A** — Namespace `pin_15.pulse_min` (Tree-Struktur in rqt) | (B) Flat `pin_15_pulse_min` |
| **B-Q2** Pulse-Wert-Type | **✅ A** — Integer mit `IntegerRange(800, 2200, 1)` (native) | (B) Float (rqt-Slider-Step-Bug-Risiko) |
| **B-Q3** Direction-Type | **✅ A** — Bool `direction_normal` (true=+1, false=-1; user-freundlich) | (B) Integer mit Range(-1,+1,2) (rqt zeigt nur 2 steps) |
| **B-Q4** Live-Update wann erlaubt? | **✅ A** — Pulse always, Direction nur in `inactive` (Mid-Active-Flip = Servo-Sprung 180°); **F2-Fix: via eigenen `is_active_`-Member tracken, nicht via `get_lifecycle_state()`** | (B) Alles always (Direction-Risiko); (C) Alles nur in `inactive` (Live-Cal verliert Sinn) |
| **B-Q5** Thread-Sicherheit | **✅ A** — `std::mutex` in `Calibration` (einfach, korrekt, ~45 µs/s Overhead) | (B) `std::shared_ptr<const Calibration>` mit atomic swap (sauberer, mehr Code, Future-Optim) |
| **B-Q6** Save-Service-API | **✅ A** — `std_srvs/Trigger` + `.bak-<timestamp>`-Backup (siehe F1) | (B) Custom-Service mit Output-Path-Arg; (C) Live-Persistence in Plugin (kein Service) |
| **B-Q7** YAML-Format-Preserving | **✅ B** — flat Output mit `defaults`-Block + alle 18 Pins explizit (siehe F5), Header-Template mit Auto-Gen-Banner + Timestamp | (A) Roundtrip-Preserving (hoher Aufwand, Phase 13+) |
| **B-Q8** ParamSpec-Tabelle | **✅ A** — analog Stage A: `std::vector<PinParamSpec>` generiert aus 18×4 (Single Source of Truth) | (B) 72 separate declare_parameter-Aufrufe (Boilerplate) |
| **B-Q9** Cross-Constraint-Validation | **✅ A** — atomic-all-or-nothing analog Stage A: alle Updates zusammen prüfen, bei Fail kompletter Rollback | (B) Pro Param einzeln (Konsistenz-Risiko bei Multi-Update) |

---

## Logik-Skizze

### B.0 — Vorbereitung

Plan-Doku finalisiert, User-Freigabe der 9 Fragen, test_commands.md
Skelett. Build-Status grün bestätigt (208/0/20).

### B.1 — Calibration-API erweitern (~2 h)

In [calibration.hpp](../src/hexapod_hardware/include/hexapod_hardware/calibration.hpp)
+ [calibration.cpp](../src/hexapod_hardware/src/calibration.cpp):

- Member `mutable std::mutex mutex_` hinzufügen
- Bestehende `at()`, `radians_to_pulse_us`, `pulse_us_to_radians`,
  `output_idx_for_joint` umbauen: locken
- Neue Methoden:
  - `void update_servo_cal(int output_idx, const ServoCalibration & c)` —
    lockt + validiert (pulse-Constraints) + überschreibt eine Zeile
  - `ServoCalibration snapshot(int output_idx) const` — lockt + Copy
  - `void save_to_file(const std::string & path) const` — lockt + emit
    YAML mit Header-Template + flat Output
- Unit-Tests in `test_calibration.cpp` für die neuen Methoden

### B.2 — PinParamSpec-Tabelle + declare_parameters (~1.5 h)

In [hexapod_system.hpp](../src/hexapod_hardware/include/hexapod_hardware/hexapod_system.hpp)
+ [hexapod_system.cpp](../src/hexapod_hardware/src/hexapod_system.cpp):

- Helper-Methode `register_live_cal_params()` nach `on_init` aufgerufen:
  - Iteriert 18 Pins × 4 Felder
  - Pro pulse_*: `declare_parameter<int>(name, current_value, IntegerRange(800, 2200, 1))`
  - Pro direction_normal: `declare_parameter<bool>(name, value > 0)`
  - Defaults aus aktuell geladenen `calibration_.snapshot(pin)`
- Membervariable für Callback-Handle:
  `rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr cb_handle_`

### B.3 — `_on_param_change`-Callback (~2 h)

Analog Stage-A-`_on_param_change`:

- **Pre-Validation:**
  - Parse param-Name → `pin`/`field`
  - Direction-Update + active-State → Reject
  - Pulse-Werte ∈ [800, 2200] (Descriptor schützt schon, defensive)
  - Pro Pin Tripel-Check nach Apply: pulse_min < pulse_zero < pulse_max
    (über `proposed`-Map analog Stage A)
- **Apply:**
  - Pro Param: aktuelle `Calibration`-Zeile holen, modifizieren,
    `update_servo_cal(pin, modified)` rufen
  - Logger: `cal updated: pin_15.pulse_zero=1550 → 1700`

### B.4 — `/save_calibration`-Service (~1.5 h)

- Service-Server in `on_configure` registrieren (Node verfügbar)
- Callback ruft `calibration_.save_to_file(calibration_file_)`:
  - Erst `mv calibration_file_ → calibration_file_ + ".bak"`
  - Dann yaml-cpp-Emit mit Template-Header + flat Output
- Response: `success: true`, `message: "saved 18 cals to <path>"`

### B.5 — Unit-Tests Plugin-Level (~1.5 h)

In neuer Datei `test/test_param_callback_plugin.cpp`:

- Plugin im loopback_mode_ initialisieren (kein serial nötig)
- `set_parameters([pin_15.pulse_zero=1700])` → check
  `calibration_.snapshot(15).pulse_zero == 1700`
- Invalid (pulse_zero > pulse_max) → SetParametersResult(false)
- Atomic-Rollback bei Multi-Param-Update
- Save-Service: ruft Trigger → check `.bak` + neuer YAML existieren

### B.6 — Build + Tests grün + Regression

```bash
colcon build --packages-select hexapod_hardware
colcon test --packages-select hexapod_hardware
# erwartet: 208 + N_new tests, 0 errors, 0 failures, 20 skipped
# Regression: hexapod_gait 20/0/1, hexapod_bringup 18/0/0
```

### B.7 — User-Smoke (~30 min)

- Plugin in loopback_mode_ + rqt_reconfigure starten
- `pin_15.pulse_zero` Slider verschieben → Logger meldet update,
  `/servo_pulses` (kommt erst in Stage C) noch nicht da
- `/save_calibration` aufrufen via `ros2 service call`
- `.bak` + neue YAML inspizieren

### B.8 — Self-Review

CLAUDE.md §4-Pflicht-Tabelle.

---

## Tests-Liste

| # | Test | Erwartung | Wer |
|---|---|---|---|
| B-T1 | `colcon build --packages-select hexapod_hardware` | grün | Claude |
| B-T2 | `colcon test --packages-select hexapod_hardware` | alle bestehenden + neue Tests grün | Claude |
| B-T3 | `colcon test --packages-select hexapod_gait hexapod_bringup` | unverändert (20/0/1, 18/0/0) | Claude |
| B-T4 (User) | `ros2 param set /hardware_interface/pin_15.pulse_zero 1600` → Calibration snapshot stimmt | Claude/User |
| B-T5 (User) | rqt_reconfigure öffnen, Pin-Slider verschieben, Logger meldet update | User |
| B-T6 (User) | Pulse-min > pulse-max via `set_parameters_atomically` → Reject | User |
| B-T7 (User) | `ros2 service call /save_calibration std_srvs/Trigger` → `.bak` + neuer YAML existieren, YAML enthält Live-Werte | User |
| B-T8a (User) | Direction-Flip in `inactive`-Lifecycle → Accept + Calibration-Update sichtbar | User |
| B-T8b (User) | Direction-Flip in `active`-Lifecycle → Reject mit klarer Reason | User |

### Was bewusst NICHT in Stage B getestet wird

- **`/servo_pulses` Diagnostic-Topic** (Stage C)
- **rqt-Multi-Plugin-Layout** (Stage D)
- **Sim-Tuning-Workshop** (Stage E)
- **Echter Servo-Bewegungstest** — Stage B ist Plugin-Level, kein
  echtes Bench-Setup nötig (loopback reicht). HW-Bench kommt bei
  Phase-13-Wiedereinstieg

---

## Progress-Checkliste (Done-Kriterium-Vertrag)

- [x] B.1 phase_11_stage_b_plan.md finalisiert + User-Freigabe der B-Q1..B-Q9 + F1..F6-Fixes (2026-05-20)
- [ ] B.2 phase_11_stage_b_test_commands.md Skelett
- [ ] B.3 Calibration-API erweitert (`mutex_`, `update_servo_cal`, `snapshot`, `save_to_file` mit Timestamp-Bak)
- [ ] B.4 `register_live_cal_params()` + Param-Descriptors für alle 72 Pin-Params (`PinParamSpec`-Tabelle)
- [ ] B.5 `is_active_` atomic-Member + Set in `on_activate`/`on_deactivate` (F2)
- [ ] B.6 `_on_param_change`-Callback mit atomic-all-or-nothing-Validation + Direction-active-Reject
- [ ] B.7 `/save_calibration`-Service (Trigger + `.bak-<timestamp>`-Backup + flat YAML-Output mit Header-Template, F1+F5)
- [ ] B.8 package.xml + CMakeLists.txt: `std_srvs`-Dependency hinzufügen (F3)
- [ ] B.9 Logging `cal updated: pin_<N>.<field>=<old> → <new>` nach Apply
- [ ] B.10 B-T1 colcon build grün
- [ ] B.11 B-T2 colcon test grün (neue Plugin-Param-Tests + Calibration-Tests, tmpdir-Pattern aus test_calibration.cpp F6)
- [ ] B.12 B-T3 keine Regression in hexapod_gait / hexapod_bringup
- [ ] B.12a README hexapod_hardware Phase-11-Stage-B-Block: Param-Liste + Save-Service + Backup-Schema + Direction-Restriction (F4)
- [ ] B.13 B-T4..B-T8a/b User-Smoke
- [ ] B.14 Self-Review-Tabelle (CLAUDE.md §4-Pflicht; F7 + F8 explizit prüfen)
- [ ] B.15 Stage-B-Notizen + Übergang Stage C

**Done-Kriterium B:** alle Bullets `[x]`, Self-Review ohne 🔴,
User-Smoke B-T4..B-T8 bestätigt.

---

## Erwartete Stage-B-Dauer

- B.1 Plan-Doku (diese Datei): ~30 min Claude (erledigt)
- B.2 test_commands.md: ~15 min Claude
- B.3 Calibration-API erweitern: ~2 h Claude
- B.4 declare_parameters: ~1.5 h Claude
- B.5 Callback: ~2 h Claude
- B.6 Save-Service: ~1.5 h Claude
- B.7 Logging: ~15 min
- B.8-B.10 Build + Tests: ~30 min
- B.11 User-Smoke: ~30 min User
- B.12 Self-Review: ~15 min Claude

**Schätzung:** ~8.5 h Claude + ~30 min User = **~1.5 d Gesamt**.
(Original-Schätzung im Mutter-Plan: ~1 d — Stage B hat mehr
Engineering-Detail als ursprünglich antizipiert: Thread-Safety + YAML-
Save mit Header-Template + Lifecycle-State-Check für Direction.)
