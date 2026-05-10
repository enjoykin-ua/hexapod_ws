# Phase 6 — Fortschritt (Teleop: PS4-Controller)

> **Phasenplan:** [phase_6_teleop.md](phase_6_teleop.md)
> (Konzept-Stand bei Phase-Start)
>
> **Phase-5-Handoff:** [phase_6_teleop_handoff.md](phase_6_teleop_handoff.md)
> (was Phase 5 als Output gibt, wo es im Code lebt, wie ansprechen)
>
> **Konzept-Hintergrund:** [phase_5_gait_explained.md](phase_5_gait_explained.md)
> (für Engine-internen Kontext bei Body-Lift-Erweiterung)

---

## Plan-Änderung (2026-05-10)

**Tastatur-Steuerung verworfen.** Ursprünglicher Plan war "Stufe A
Tastatur, Stufe B PS-Controller". Nach kurzer Konzept-Phase mit
`pynput`-Wayland-Risiko-Diskussion **direkter Sprung zum PS4-USB-
Controller**. Begründung:

- Tastatur war "Vorbereitung für PS-Controller", aber direkte PS4-
  Implementation ist genauso viel Aufwand wie kbd_to_twist gewesen
  wäre.
- Wayland-Risiko mit `pynput` (globaler Tastatur-Listener) wäre
  weiteres Debugging-Risiko gewesen.
- DK 1 aus dem Phasenplan (Tastatur via `teleop_twist_keyboard`)
  bleibt formal verworfen — DK 2-5 sind das eigentliche Phase-Ziel.

**Konsequenz:** nur eine Stufe A für PS4-USB-Controller. Stufe B
heißt jetzt "Bluetooth-Erweiterung" und ist optional auf später
verschoben.

---

## Phasen-Status

| Stufe | Inhalt | Status |
|---|---|---|
| A | PS4-Controller via USB + Engine-Erweiterung Body-Lift | 🟢 abgeschlossen 2026-05-10 |
| B | Bluetooth-Pairing für PS4 (optional) | ⚪ deferred, später bei Bedarf |

---

## Stufe A — PS4-Controller via USB

**Ziel:** PS4-Controller per USB → `/cmd_vel` (Twist) +
`/cmd_body_height` (Float64). DK 2-5 erfüllt.

**Was wir machen:**
- Engine-Erweiterung: `body_height` zur Laufzeit änderbar via Topic,
  aber **nur wenn Engine im STANDING-State** (Sicherheit: Body-Lift
  während Walk könnte umfallen).
- Neues Paket `src/hexapod_teleop/` mit `joy_to_twist.py`-Knoten.
- Subscribt `/joy`, publisht `/cmd_vel` + `/cmd_body_height`.
- Dead-Man-Switch (R1) — Bewegung nur wenn R1 gehalten.

### User-Vorgabe Mapping (final, 2026-05-10)

| PS4-Input | Effekt | Notiz |
|---|---|---|
| **R1** (halten) | Dead-Man — Bewegung erlaubt | DK 5 |
| **D-Pad ↑** | `linear.x = +0.05` (vorwärts) | nur wenn R1 |
| **D-Pad ↓** | `linear.x = -0.05` (rückwärts) | nur wenn R1 |
| **D-Pad ←** | `angular.z = +0.46` (drehen links am Stand) | nur wenn R1 |
| **D-Pad →** | `angular.z = -0.46` (drehen rechts am Stand) | nur wenn R1 |
| **L2** (Trigger) | Body senken (-5 mm pro Trigger-Press) | **nur wenn STANDING** |
| **R2** (Trigger) | Body anheben (+5 mm pro Trigger-Press) | **nur wenn STANDING** |

**Bewusst nicht gemappt:** Sticks, Face-Buttons, Speed-Scaling.
Können später dazu kommen.

**Body-Lift-Constraint:** L2/R2 sendet nur dann `/cmd_body_height`,
wenn der Roboter steht (Engine-State == STANDING). Während
WALKING/STOPPING wird die Trigger-Eingabe ignoriert mit Warning-Log.
Das verhindert dass Body-Pose-Wechsel mitten im Walk-Cycle den
Roboter umwirft.

**Seitwärts (`linear.y`) nicht gemappt:** PS-Controller's analoge
Sticks könnten linear.y, aber User-Mapping nutzt nur D-Pad
(digital). Kann später mit linkem Stick X erweitert werden.

### Design-Entscheidungen Stufe A

#### 1. Trigger-Edge-Detection (L2/R2)

**Problem:** `/joy`-Callbacks feuern bei jeder Stick-Bewegung. Wenn
User L2 hält, würden viele Callbacks "L2 ist gedrückt" sehen → wir
würden body_height in Loop senken statt um genau einen Schritt.

**Optionen:**
- **A) Rising-Edge-Detection** — body_height-Schritt nur wenn Trigger
  von "los" zu "gedrückt" wechselt. User muss loslassen + neu drücken
  für nächsten Schritt.
- B) Hold-Repeat — solange L2 gehalten, sende einen Step alle 200 ms.
- C) Analoge Skala — Trigger-Wert direkt als body_height-Offset
  (kontinuierlich, Position-Mapping).

**Gewählt: A** — User-Mental-Modell ist "ein Druck = ein Schritt".
Hold-Repeat würde das brechen. Analoge Skala wäre für eine andere
UX (Position-Stick statt Step-Trigger).

#### 2. Trigger-Schwelle für "gedrückt"

**Hintergrund:** L2/R2 sind analoge Achsen. PS4-USB-Default:
idle = +1.0, fully pressed = -1.0. "Gedrückt" muss schwell-basiert
sein.

**Gewählt: 0.5** — Trigger gilt als "gedrückt" wenn `axis_value < 0.5`
(also halb durchgedrückt). Edge fires beim Über-/Unterschreiten der
Schwelle.

#### 3. Body-Lift nur im STANDING

**Optionen:**
- **A) Engine-seitig prüfen** — `/cmd_body_height`-Subscriber in
  gait_node ignoriert msg wenn `engine.state != STANDING`, mit
  Warning-Log.
- B) Client-seitig prüfen — joy_to_twist liest `/joint_states` o.ä.
  und entscheidet selbst.
- C) Keine Prüfung — body_height-Mutation jederzeit erlaubt
  (Risiko: Roboter kippt mitten im Walk).

**Gewählt: A** — Engine ist Single-Source-of-Truth für State.
joy_to_twist hat diese Info nicht ohne extra Subscription.

#### 4. Dead-Man + Body-Lift

**Frage:** muss R1 auch gehalten werden für L2/R2 (Body-Lift)?

**Gewählt: NEIN** — Body-Lift ist genau für die Situation gedacht
"Roboter steht, ich will die Hocke ändern". R1 würde aber WALKING
erfordern (Dead-Man = Bewegung erlaubt). Daher: L2/R2 funktioniert
**unabhängig von R1**, nur Engine-State-Check (siehe Design 3).

#### 5. Ros-Joy-Driver-Wahl

**Optionen:**
- **A) `ros-jazzy-joy`** — Standard-ROS-Paket, einfach via apt.
- B) Custom-Driver via `evdev` direkt.

**Gewählt: A** — bereits installiert und funktioniert (User hat
`ros2 topic echo /joy` als Sanity-Check gemacht).

### Bullet-Liste Stufe A

- [x] Konzept besprochen (D-Pad-Mapping, L2/R2 für Body-Lift, R1
  Dead-Man, STANDING-only-Constraint, Edge-Detection)
- [x] **A.1 Engine-Erweiterung Body-Lift:**
  - [x] [gait_node.py](../src/hexapod_gait/hexapod_gait/gait_node.py): Subscription `/cmd_body_height` (`std_msgs/Float64`)
  - [x] State-Check `engine.state == STANDING`, sonst Warning + ignore (`throttle_duration_sec=1.0`)
  - [x] Clamp auf `[body_height_min, body_height_max]` mit Warning bei Clamp
  - [x] [gait.launch.py](../src/hexapod_gait/launch/gait.launch.py): neue Args `body_height_min=-0.080`, `body_height_max=-0.030`
  - [x] Pure-Python-Smoke-Test (Engine.body_height direkt mutieren, foot-targets passen sich an): bestanden
- [x] **A.2 Paket `hexapod_teleop` anlegen:**
  - [x] `ros2 pkg create --build-type ament_python` ausgeführt
  - [x] Dependencies: rclpy, sensor_msgs, geometry_msgs, std_msgs + `<exec_depend>joy</exec_depend>`
  - [x] [setup.py](../src/hexapod_teleop/setup.py) mit launch/+config/ data_files erweitert
  - [x] [package.xml](../src/hexapod_teleop/package.xml) Description befüllt
- [x] **A.3 [joy_to_twist.py](../src/hexapod_teleop/hexapod_teleop/joy_to_twist.py)**:
  - [x] Subscribe `/joy` (sensor_msgs/Joy)
  - [x] Publish `/cmd_vel` (Twist) + `/cmd_body_height` (Float64)
  - [x] D-Pad → cmd_vel (nur wenn R1 gehalten); andernfalls 0-Twist
  - [x] L2/R2 → cmd_body_height mit Rising-Edge-Detection (`_l2_was_pressed`, `_r2_was_pressed`)
  - [x] Internal state `_target_body_height` für absolute Pubs
  - [x] Param-konfigurierbar: alle Achsen-Indizes, Vorzeichen, Trigger-Schwelle, Scales, Body-Step, Dead-Man-Button
- [x] **A.4 [config/ps4_usb.yaml](../src/hexapod_teleop/config/ps4_usb.yaml)**:
  - [x] D-Pad axes 6/7, Trigger axes 2/5
  - [x] Vorzeichen +1 für beide D-Pad-Achsen (Live-Test prüft, ggf. invert)
  - [x] Trigger-Schwelle 0.5
  - [x] linear=0.05 m/s, angular=0.46 rad/s
  - [x] body_step=0.005 m
  - [x] deadman_button=5 (R1)
- [x] **A.5 [launch/joy_teleop.launch.py](../src/hexapod_teleop/launch/joy_teleop.launch.py)**:
  - [x] Startet `joy_node` (autorepeat_rate=20 Hz, deadzone=0.05)
  - [x] Startet `joy_to_twist` mit YAML aus controller-Arg
  - [x] LaunchArg `controller:=ps4_usb` (Default), `joy_device:=/dev/input/js0`
- [x] **A.6 [README.md](../src/hexapod_teleop/README.md)** für hexapod_teleop mit Mapping-Tabelle + 6 Stolperfallen
- [x] **A.7 Build + Test:**
  - [x] `colcon build --packages-select hexapod_gait hexapod_teleop` grün
  - [x] `colcon test --packages-select hexapod_gait hexapod_teleop` grün (1 Iteration: I100-Import-Order in setup.py korrigiert)
  - [x] Pure-Python Engine-Body-Height-Mutation-Smoke-Test grün (z=-0.052, -0.030, -0.080, -0.040 alle korrekt geliefert)
- [x] **A.8 [phase_6_stage_A_test_commands.md](phase_6_stage_A_test_commands.md)** geschrieben — 13 Schritte mit klaren T1/T2/T3/T4-Indikatoren
- [x] **Live-Verifikation** (User, 2026-05-10):
  - [x] DK 2: Paket `hexapod_teleop` mit PS-Support gebaut ✓
  - [x] DK 3: PS4 via USB, joy_node zeigt Werte ✓
  - [x] DK 4: joy_to_twist erzeugt korrekte cmd_vel ✓
  - [x] DK 5: Dead-Man-Switch (R1) — loslassen = sofort Stopp ✓
  - [x] D-Pad ↑/↓ → vor/zurück ✓
  - [x] D-Pad ←/→ → drehen am Stand ✓
  - [x] R2-Press → Body steigt 5 mm ✓
  - [x] L2-Press → Body senkt 5 mm ✓
  - [x] Body-Lift während WALKING → Warning, ignored ✓
  - [x] Multi-Direction: D-Pad ↑ + ← → Bogen-Walk (verifiziert, sofern PS4-D-Pad das hardware-seitig zulässt)

### Umsetzungsnotizen Stufe A

> **Test-Anleitung:** [phase_6_stage_A_test_commands.md](phase_6_stage_A_test_commands.md).

Stufe A lief mit **einer Live-Bug-Iteration** (kleiner Launch-File-
Bug, kein Engine-Bug). Tastatur-Pfad wurde komplett übersprungen,
direkt zum PS4-USB-Controller — gute Entscheidung, weil:

1. **`pynput`-Wayland-Risiko entfiel.**
2. **Custom-kbd_to_twist wäre Wegwerfcode** gewesen — alle Stufe-A-
   Funktionalität wird durch joy_to_twist abgedeckt.
3. Ergebnis: **Phase 6 in einem halben Tag** statt 2-4 Tagen wie
   ursprünglich geschätzt.

#### 1. Live-Bug: `joy_node`-Parameter `device_name` → `device_id`

Initial-Implementation in `joy_teleop.launch.py` hatte:

```python
'device_name': LaunchConfiguration('joy_device'),  # FALSCH
```

mit Default `joy_device:=/dev/input/js0`. **Falsch:** `device_name`
in ros-jazzy-joy ist eine **SDL-Joystick-Name-String-Match** (z.B.
"Sony Computer Entertainment Wireless Controller"), nicht ein
Linux-Device-Pfad.

**Symptom:**
```
[joy_node]: Could not get joystick with name /dev/input/js0:
```

joy_node hat versucht, einen Joystick zu finden **dessen Name**
"/dev/input/js0" ist — natürlich erfolglos.

**Fix:** auf `device_id` (int, SDL-Joystick-Index) gewechselt:

```python
'device_id': LaunchConfiguration('joy_device_id'),  # default 0
```

Default `joy_device_id:=0` matcht den ersten verfügbaren Joystick.
Bei mehreren Controllern kann `joy_device_id:=1` etc. gesetzt werden.

**Lehre:** ROS-Driver-Parameter immer am Source bzw. README prüfen,
nicht aus Annahmen ableiten. SDL2-Joystick-API arbeitet mit Indizes,
nicht mit Linux-Device-Pfaden.

#### 2. Body-Height-Engine-Mutation: kein Engine-Code-Change nötig

Die Engine las `self.body_height` schon seit Phase 5 **frisch in
jedem Tick** (in `_compute_walking_targets`, `_compute_stopping_targets`,
`_compute_standing_targets`). Setzen von `engine.body_height = X` von
außen wirkt also **sofort** beim nächsten Tick — keine Engine-
Modifikation nötig, nur das Topic + State-Check in gait_node.

Pre-Live-Smoke-Test (Pure-Python) hat das bestätigt:
- `engine.body_height = -0.030` → `compute_foot_targets()` liefert
  `leg_1.z = -0.030` sofort.
- Auch im WALKING-State: mid-stance-z folgt der Mutation live.

#### 3. STANDING-only-Constraint funktioniert sauber

`gait_node._on_cmd_body_height` prüft `engine.state == STANDING` und
ignoriert sonst mit Warning. Live-verifiziert: während Walk gibt's
einen `throttle_duration_sec=1.0`-gefilterten Warning-Log, body_height
bleibt unverändert. Erst nach Stopp + STANDING-State greifen die
nächsten L2/R2-Pubs.

#### 4. Edge-Detection für L2/R2 funktioniert

Rising-Edge-Logik (`_l2_was_pressed`, `_r2_was_pressed`) verhindert
dass beim Halten von L2/R2 mehrere body_height-Schritte feuern. User-
Mental-Modell "ein Druck = ein Schritt" wird sauber abgebildet.

#### 5. Was Stufe A NICHT macht

- Keine **Sticks** gemappt (analoge LS/RS) — nur D-Pad. Geschwindigkeits-
  Modulation kommt erst wenn nötig.
- Keine **`linear.y` (Seitwärts)** — D-Pad-Mapping nutzt linke Achse
  fürs Drehen statt Seitwärts (User-Mental-Modell "Tank-Steuerung").
  Sticks könnten linear.y später, wenn gewollt.
- Kein **Bluetooth** — Stufe-B-Aufgabe, optional.
- Kein **Touchpad / adaptive Trigger / Lichtleiste** — out-of-scope.

### Phase-6-Retro

**Was lief gut:**

- **Direkter PS4-Pfad statt Tastatur-Umweg.** Die Konzept-Diskussion
  hat gezeigt, dass Tastatur ein Zwischenschritt ohne echten Mehrwert
  gewesen wäre. Sprung zur Endlösung sparte ~1 Tag und ein Wayland-
  Debugging-Risiko.
- **Code-Symmetrie zur Phase 5.** `joy_to_twist.py` strukturell
  parallel zu Phase-5's `gait_node.py` (rclpy + Param-Konfiguration
  + Subscriber + Publisher). Kein Style-Reinvent.
- **YAML-getriebene Achsen-Mapping** statt hardcoded Indizes — Stufe
  B (BT, PS5) ist nur ein neues YAML, kein Code-Change.
- **Pre-Live-Smoke-Test der Engine-Body-Height-Mutation** hat
  bestätigt dass die Engine-Logik schon Phase-6-ready war (kein
  Engine-Code-Change nötig).
- **Klare Test-Doc mit T1/T2/T3/T4-Markern** hat den Live-Test
  geradlinig gemacht.

**Was hat länger gedauert als gedacht:**

- **`joy_node`-Parameter-Bug**: 2 Iterationen bis device_id statt
  device_name. Hätte mit Doku-Lookup vorab vermieden werden können.

**Was bleibt offen / Phase-7-Übergabe:**

- **Bluetooth-Pairing für PS4** — Stufe B nicht durchgeführt. Bei
  Bedarf später, kein technisches Risiko (selbe Code-Basis, neues
  YAML).
- **Sticks-Mapping** — analog LS/RS könnten Geschwindigkeits-
  Modulation und linear.y dazu nutzen. User hat das nicht gewollt
  in Stufe A.
- **`controllers.yaml use_sim_time: true`** und `body_height = -0.052`
  bleiben bis Phase 7 (HW-Port). Phase 7 ändert beides.
- **KDL-Warning** weiter offen (User-Entscheidung).

**Memory-Erkenntnisse aus Phase 6:**

- ROS-Driver-Parameter-Namen am Source / README prüfen, nicht aus
  Annahmen ableiten. Insbesondere SDL2-vs-Linux-Device-Pfad-
  Verwechslung war Phase-6-Lehre.
- Phase-Plan kann mid-flight angepasst werden wenn ein Ursprungs-
  Konzept (Tastatur als "Vorbereitung") sich als überflüssig erweist.

**Quantitative Bilanz:**

- Stufen: nur A (Stufe B Bluetooth deferred)
- Neue Pakete: 1 (`hexapod_teleop`)
- Engine-Erweiterung: 0 (Engine las body_height schon fresh) +
  gait_node-Erweiterung 1 (`/cmd_body_height` Subscription mit
  STANDING-only-Constraint)
- Neue Konzept-Dokus: 1 (`phase_6_progress.md`, dazu Stage-A-Test-Doc)
- Tests grün: alle bisherigen Phase-5-Tests + neuer Phase-6-
  Smoke-Test + Style-Tests `hexapod_teleop`
- Live-Bug-Iterationen: 1 (joy_node `device_name` → `device_id`)
- Phase-Dauer: ~0,5 Tage (statt 2-4 Tage geplant)

---

## Stufe B — Bluetooth-Pairing (optional, später)

**Ziel:** PS4-Controller kabellos. Selber Code-Pfad wie Stufe A,
nur andere Verbindungsart.

**Erwartete Aufgaben:**
- BT-Pairing dokumentieren (`bluetoothctl scan + pair + trust +
  connect`)
- Verifizieren ob `joy_node` mit BT identische Achsen-Indizes liefert
  (oft NICHT identisch zu USB)
- Falls Mapping anders: `config/ps4_bt.yaml` mit angepassten
  Indizes/Vorzeichen
- Test wie Stufe A mit BT-Verbindung

**Code-Aufwand minimal** wenn Mapping stabil, sonst YAML-Anpassung.

---

## Phasenabschluss (nach Stufe A)

- [ ] Alle relevanten Done-Kriterien aus
  [phase_6_teleop.md](phase_6_teleop.md) erfüllt (DK 2-5; DK 1
  Tastatur formal verworfen, siehe Plan-Änderung oben)
- [ ] Mapping in `src/hexapod_teleop/README.md` dokumentiert
- [ ] Dead-Man-Switch nachweislich
- [ ] Phase-6-Bericht in Workspace-`README.md`
- [ ] `PHASE.md` auf Phase 7 (oder Bluetooth-Stufe-B falls noch
  gewünscht)
- [ ] Timeshift-Snapshot `phase_6_done` (User)
- [ ] Git-Commit + Tag `phase-6-done` (User)
- [ ] Retro im Progress-File

---

## Memory-Erkenntnisse aus Phase 5 die hier relevant sind

- **Pre-Live-Smoke-Test** (Pure-Python ohne Sim) für Engine-Mutation
  in A.1.
- **Stale-Prozesse-Cleanup** für Tests:
  ```bash
  pkill -f "joy_node"
  pkill -f "joy_to_twist"
  pkill -f "ros2 topic pub"
  ```
- **Test-Doc vorab schreiben** mit klaren **Terminal-Indikatoren**
  (User-Memory `feedback_interactive_stage_test_doc.md`).
- **Design-Entscheidungen mit Alternativen** dokumentieren
  (User-Memory `feedback_decision_alternatives_log.md`).
- **Pro-erledigtem-Bullet abhakken**, nicht batchen
  (User-Memory `feedback_phase_progress_tracking.md`).
