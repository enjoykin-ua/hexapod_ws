# Phase 13 — Servo2040 FW-Fix: PWM-Auto-Enable beim Boot/Reset

> **Status (2026-05-30):** ✅ FW-Änderungen (3.1–3.4) sind in `main.cpp`
> umgesetzt und werden als **Fundament behalten**. **Wichtig:** dieser Fix
> löst das eigentliche **MID-on-Power-On-Verhalten NICHT** (das ist
> Servo-hardware-bedingt, siehe [`phase_13_stage_0_plan.md`](phase_13_stage_0_plan.md) §2).
> Sein bleibender Wert: er hält PWM auf disabled Pins sauber aus — das ist
> **Voraussetzung** für den Relay-Ansatz von Stage 0 (nur Relay + ENABLE
> fahren die Servos hoch). Die in §3 angedachte "Zucken weg"-Erwartung ist
> damit überholt; das Zucken-Problem wird in Stage 0 mechanisch (Femur-Umbau)
> + per Relay-Gate gelöst, nicht FW-seitig.
>
> **Ursprünglicher Status:** ⚪ offen, Plan-Doku, wartet auf User-Freigabe (2026-05-28)
>
> **Vorgaenger:** Phase 13 Desktop Stage A
> ([`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md))
> hat aufgedeckt dass das Plugin allein das beim Plugin-Start beobachtete
> Zucken nicht vollstaendig beheben kann — die Wurzel liegt in der
> Servo2040-FW + der Pimoroni-`ServoCluster`-API. Dieser Fix adressiert
> die FW-Seite.
>
> **Repository:** `~/hexapod_servo_driver` (separates Repo, kein
> ROS2-Workspace). Build-/Flash-Workflow siehe
> [`hexapod_servo_driver/README.md`](../../hexapod_servo_driver/README.md).
>
> **Nachfolger:** nach Flash der neuen FW wird Stage A re-verifiziert
> ([`phase_13_desktop_stage_a_initial_pose_test_commands.md`](phase_13_desktop_stage_a_initial_pose_test_commands.md)).
> Erwartung: kein Zucken mehr bei Plugin-Start in keinem der Szenarien
> (Cold-Start, Plugin-Restart, pkill-Recovery).

---

## 1. Problem-Beobachtung

Beim Plugin-Start (`ros2 launch hexapod_bringup real.launch.py`) zucken
die Servos kurz in Richtung horizontale T-Pose, bevor sie in die
suspended-Position gehen. Beobachtet vom User in mehreren Szenarien
(2026-05-28):

| Szenario | Beobachtung |
|---|---|
| Cold-Start (USB-Cycle, FW frisch gebootet) | Leichtes Zucken (~300 ms, kleine Bewegung Richtung Mitte, dann zurueck nach unten) |
| Plugin-Restart waehrend Beine schon in suspended haengen | Leichtes Zucken (gleiches Muster wie Cold-Start) |
| pkill-Restart (`pkill -9 -f ros2`, dann Plugin neu) | Staerkeres Zucken (Beine gehen sichtbar hoeher als bei Cold-Start) |

Plugin-side wurden in Stage A bereits zwei Workarounds eingebaut:

1. **Frame-Reihenfolge geaendert** ([hexapod_system.cpp:489-549](../../src/hexapod_hardware/src/hexapod_system.cpp#L489-L549)):
   `SET_TARGETS suspended` wird **vor** den 18 ENABLE_SERVO-Frames
   gesendet, damit `target_pulse_us` schon korrekt ist beim Aktivieren.
2. **400 ms breather** zwischen `SET_TARGETS pre-enable` und dem ersten
   ENABLE: gibt der FW-Soft-Ramp Zeit, `current_pulse_us` von pulse_zero
   zu suspended zu rampen, bevor PWM "scharf" wird.

Beide Workarounds reduzieren das Zucken aber eliminieren es nicht. Live-
Verifikation zeigt: das Zucken bleibt sichtbar bei jedem Plugin-Start.

---

## 2. Wurzel-Analyse

**Pimoroni `ServoCluster::pulse(idx, val)` aktiviert den Pin
automatisch**, sobald `val >= MIN_VALID_PULSE` (~500 µs). Quelle:
[`pimoroni-pico/drivers/servo/servo_state.cpp:43-53`](../../../pimoroni-pico/drivers/servo/servo_state.cpp#L43-L53):

```cpp
float ServoState::set_pulse_with_return(float pulse) {
  if (pulse >= MIN_VALID_PULSE) {
    ...
    return _enable_with_return();   // ← setzt enabled=true, PWM an
  }
  return disable_with_return();
}
```

Servo2040-FW hat aber eine **eigene `servo_enabled[i]`-Variable** die
parallel zur Pimoroni-Library lebt
([`hexapod_servo_driver/src/main.cpp:48`](../../hexapod_servo_driver/src/main.cpp#L48)).
Diese FW-Variable wird **nicht mit dem Pimoroni-State synchronisiert**:

- `handle_enable_servo()` setzt nur `servo_enabled[i] = en` — kein
  `g_servos->enable()` / `g_servos->disable()`-Call zur Pimoroni-Lib.
- `handle_reset()` setzt `servo_enabled[i] = false` + `current_pulse_us[i] =
  pulse_zero` — ruft `g_servos->load()` aber kein `g_servos->disable_all()`.
- `on_tick()` callt `g_servos->pulse(i, current_pulse_us[i], false)` **fuer
  alle 18 Pins unbedingt**, ohne `servo_enabled[i]`-Check.

**Konsequenz:** sobald die FW bootet (oder das Plugin RESET sendet),
schreibt `on_tick()` Pimoroni-`pulse(i, pulse_zero)` raus → Pimoroni
schaltet die Pins **automatisch ein** mit `pulse_zero` als PWM (~1500 µs
= horizontale T-Pose-Mitte). Wenn die Servos zu dem Zeitpunkt Strom haben
(PSU an), fahren sie aktiv zur Mitte.

Das geschieht in den ~50 ms zwischen FW-Boot/RESET und dem ersten
`SET_TARGETS suspended`-Frame vom Plugin. In dieser Zeit zuckt der Servo
zur Mitte. Wenn dann `SET_TARGETS suspended` kommt + Soft-Ramp anlaeuft,
rampt der Servo zurueck nach unten — sichtbar als das Zucken.

**Beim pkill-Restart-Szenario verstaerkt sich das Problem:** vor dem
Restart hatte der Servo PWM=suspended via Pimoroni. Watchdog-Trip ruft
`g_servos->disable_all()` → Pimoroni-PWM auf 0 (PWM ganz aus → Servo
passiv). Plugin restart: RESET-Frame setzt FW-vars zurueck auf
`pulse_zero` (1500 µs). Beim **naechsten on_tick** callt FW
`pulse(i, 1500)` → Pimoroni schaltet PWM wieder ein mit 1500 µs. Servo
wechselt schlagartig von "passiv" zu "aktiv auf 1500 µs" → sichtbares
"Aufschnellen" Richtung Mitte, dann zurueck.

---

## 3. Was korrigiert wird

Drei kleine Aenderungen in `hexapod_servo_driver/src/main.cpp`, die
zusammen das Pimoroni-`servo_enabled`-Verhalten an die FW-State-Variable
binden:

### 3.1 Fix 1 — `on_tick` respektiert `servo_enabled[i]`

**Wo:** `on_tick()` ([main.cpp:316-329](../../hexapod_servo_driver/src/main.cpp#L316-L329))

**Aktuell:**
```cpp
for (uint i = 0; i < NUM_SERVOS; ++i) {
    int16_t delta = target_pulse_us[i] - current_pulse_us[i];
    if      (delta >  step) current_pulse_us[i] += step;
    else if (delta < -step) current_pulse_us[i] -= step;
    else                    current_pulse_us[i]  = target_pulse_us[i];
    g_servos->pulse(static_cast<uint8_t>(i),
                    static_cast<float>(current_pulse_us[i]),
                    /*load=*/false);
}
```

**Soll:**
```cpp
for (uint i = 0; i < NUM_SERVOS; ++i) {
    int16_t delta = target_pulse_us[i] - current_pulse_us[i];
    if      (delta >  step) current_pulse_us[i] += step;
    else if (delta < -step) current_pulse_us[i] -= step;
    else                    current_pulse_us[i]  = target_pulse_us[i];

    // Phase 13 FW-Fix: respect servo_enabled to avoid Pimoroni's pulse()
    // auto-enable side-effect on disabled pins.
    if (servo_enabled[i]) {
        g_servos->pulse(static_cast<uint8_t>(i),
                        static_cast<float>(current_pulse_us[i]),
                        /*load=*/false);
    } else {
        g_servos->disable(static_cast<uint8_t>(i), /*load=*/false);
    }
}
```

**Begruendung:** solange ein Pin im FW-Sinn disabled ist, bleibt PWM
hart aus. Pimoroni-`disable()` setzt `enabled=false` und PWM-Output auf
0 (= kein gueltiges Signal → Servo passiv).

### 3.2 Fix 2 — `handle_set_targets` syncen `current = target` bei disabled Pins

**Wo:** `handle_set_targets()` ([main.cpp ~270-294](../../hexapod_servo_driver/src/main.cpp))

**Aktuell:** setzt nur `target_pulse_us[i]`, Soft-Ramp ueberlegt current
zu target ueber mehrere Ticks.

**Soll:** zusaetzlich bei disabled Pins direkt `current = target` setzen,
ohne Soft-Ramp:

```cpp
for (uint i = 0; i < NUM_SERVOS; ++i) {
    int16_t raw = ...;
    bool clamped = false;
    target_pulse_us[i] = clamp_pulse(static_cast<uint8_t>(i), raw, clamped);

    // Phase 13 FW-Fix: while servo is disabled, soft-ramp is meaningless
    // (no PWM output anyway). Sync current to target so the very first
    // PWM output AFTER ENABLE_SERVO is already at target.
    if (!servo_enabled[i]) {
        current_pulse_us[i] = target_pulse_us[i];
    }

    ...
}
```

**Begruendung:** Soft-Ramp ist ein Safety-Feature fuer ACTIVE Servos
(Schutz vor abrupten Bewegungen). Bei disabled Servos gibt es keine
Bewegung — kein Schutzbedarf. Plus: nach diesem Fix ist beim ENABLE
`current == target`, und Fix 3.4 (siehe unten) emittiert PWM=current=target
direkt beim Enable.

**Historie (2026-05-28):** eine fruehere Variante dieses Fixes versuchte
ueber `g_servos->pulse(target, false)` + `g_servos->disable(false)` die
Pimoroni-`last_enabled_pulse`-Variable zu synchen damit ein spaeterer
`g_servos->enable()`-Call nicht zur MID-Position fallback. Das hat in der
Praxis nicht funktioniert (Beine blieben visuell auf MID-PWM=horizontal,
obwohl joint_states suspended zeigte). Statt da weiter zu debuggen, loest
Fix 3.4 das Problem cleaner indem `handle_enable_servo` gar nicht mehr
`g_servos->enable()` callt — sondern direkt `g_servos->pulse(target)`.

### 3.3 Fix 3 — `handle_reset` callt `g_servos->disable_all()`

**Wo:** `handle_reset()` ([main.cpp:155-178](../../hexapod_servo_driver/src/main.cpp#L155-L178))

**Aktuell:**
```cpp
for (uint i = 0; i < NUM_SERVOS; ++i) {
    servo_enabled[i]    = false;
    target_pulse_us[i]  = pulse_zero_us[i];
    current_pulse_us[i] = pulse_zero_us[i];
}
if (g_servos) g_servos->load();
```

**Soll:**
```cpp
// Phase 13 FW-Fix: explicitly disable PWM output for all pins BEFORE
// resetting state vars. Otherwise the next on_tick would call
// g_servos->pulse() which auto-enables Pimoroni back on.
if (g_servos) g_servos->disable_all(/*load=*/false);
for (uint i = 0; i < NUM_SERVOS; ++i) {
    servo_enabled[i]    = false;
    target_pulse_us[i]  = pulse_zero_us[i];
    current_pulse_us[i] = pulse_zero_us[i];
}
if (g_servos) g_servos->load();
```

**Begruendung:** RESET soll garantiert PWM-aus produzieren. Vorher
konnte das vom on_tick-Verhalten abhaengen.

### 3.4 Fix 4 — `handle_enable_servo` callt `pulse(target)` statt `enable()`

**Wo:** `handle_enable_servo()` ([main.cpp:259-300](../../hexapod_servo_driver/src/main.cpp#L259-L300))

**Aktuell (pre-Fix 3.4):**
```cpp
servo_enabled[idx] = (en != 0);
if (g_servos) {
    if (en) g_servos->enable(idx, true);
    else    g_servos->disable(idx, true);
}
```

**Soll:**
```cpp
servo_enabled[idx] = (en != 0);
if (g_servos) {
    if (en) {
        g_servos->pulse(idx, static_cast<float>(current_pulse_us[idx]),
                        /*load=*/true);
    } else {
        g_servos->disable(idx, true);
    }
}
```

**Begruendung:** Pimoroni's `ServoCluster::enable()` ruft intern
`ServoState::enable_with_return()`, das **MID** (1500 µs) zurueckgibt
wenn `last_enabled_pulse < MIN_VALID_PULSE` (= 1.0 µs). Diese Variable
wird nur in `pulse()` oder `set_value()` gesetzt — also bei frischem
FW-Boot oder nach RESET ist sie noch 0. Folge: `enable()` setzt PWM auf
MID = horizontale T-Pose-Mitte, **unabhaengig** davon was im FW
`target_pulse_us[idx]` steht. Diesen MID-Fallback umgehen wir indem
wir gar nicht `enable()` callen — `pulse(target, load=true)` setzt
ServoState::last_enabled_pulse=target + enabled=true + emittiert
PWM=target in einem Schritt. Mit Fix 3.2 ist `current_pulse_us[idx] ==
target_pulse_us[idx]` zu diesem Zeitpunkt, also exakt die Initial-Pose.

Voraussetzung: Plugin sendet **vor** ENABLE_SERVO mindestens einmal
`SET_TARGETS` (was es in on_activate macht). Falls ein User einen
ENABLE_SERVO ohne vorheriges SET_TARGETS schickt: `current_pulse_us[idx]
== pulse_zero_us[idx]` (= DEFAULT_PULSE_ZERO_US = 1500 µs) → Servo zur
Mitte, was der Pre-Fix-3.4-Default war.

---

## 4. Plugin-Side Anpassungen (im hexapod_ws)

Nach FW-Flash sind zwei Plugin-Anpassungen noetig:

### 4.1 400 ms breather entfernen

**Wo:** [`hexapod_system.cpp:528-557`](../src/hexapod_hardware/src/hexapod_system.cpp#L528-L557)

Mit FW-Fix ist `current = target` schon bei SET_TARGETS pre-enable
gesetzt (Fix 2). Soft-Ramp braucht keine Aufhol-Zeit. Der breather wird
zu 10 ms zurueckgesetzt (analog zum RESET-breather, nur Frame-Dispatch-
Reserve fuer die FW).

```cpp
// Phase 13 FW-Fix: breather kann auf 10 ms zurueck, da FW-Fix 2
// current_pulse_us bei disabled servos direkt syncen statt soft-rampen.
if (!loopback_mode_) {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
}
```

### 4.2 Test-Band fuer `PtyActivateRespectsStaggerTiming` zurueck

**Wo:** [`test_hexapod_system.cpp:727-761`](../src/hexapod_hardware/test/test_hexapod_system.cpp#L727-L761)

Budget jetzt: 10 ms RESET-breather + 10 ms SET_TARGETS-breather + 18×50 ms
Stagger = ~910 ms. Band: `[800, 1200]` ms (wie pre-Stage-A).

### 4.3 Code-Kommentare aktualisieren

- Den ausfuehrlichen Kommentar zum 400 ms-breather entfernen / kuerzen.
- Die "Pendenz fuer FW-Side-Optimierung" in
  [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md)
  §3 als ✅ markieren.

---

## 5. Test-Plan

### 5.1 FW-Side: bestehende Live-Tests aktualisieren

`tools/test_servo2040.py:461`:
```python
# NOTE: at ENABLE_SERVO the servo snaps to current_pulse_us (= 1500 µs).
```

Stimmt nach Fix 1+2 nicht mehr — der Servo bleibt am `current` (was
gleich `target` ist nach `handle_set_targets` bei disabled servos).
Kommentar updaten:

```python
# NOTE: Phase 13 FW-Fix — at ENABLE_SERVO the servo activates with the
# current commanded target pulse. If no SET_TARGETS was sent yet,
# current == pulse_zero from RESET. If SET_TARGETS was sent before
# ENABLE, current was synced to target → servo activates directly at
# target without snap.
```

Plus pruefen ob andere Tests im Repo eine Annahme zu "snap zu 1500 µs"
treffen. `tools/probe.py` durchschauen.

### 5.2 FW-Build + Flash

```bash
cd ~/hexapod_servo_driver/build
cmake ..
make -j$(nproc)
sudo picotool load Hexapod_servo_driver.uf2
sudo picotool reboot
```

Erwartet: build clean, picotool ack.

### 5.3 Live-Verifikation pre-Stage-A-Re-Test

Mit aufgebocktem Hexapod, vor dem eigentlichen Stage-A-Re-Test:

**Test V1 — Cold-Start ohne Plugin:**
1. PSU aus, USB raus → USB rein → Servo2040 boots ohne Plugin
2. PSU an
3. Beobachten: Beine bleiben **passiv** in der haengenden Position (keine
   Bewegung, kein Geraeusch). Ohne Plugin kommt kein ENABLE → kein PWM.

**Test V2 — Plugin-Boot ohne PSU:**
1. PSU aus, USB rein
2. `ros2 launch hexapod_bringup real.launch.py`
3. Plugin durchlaeuft on_activate (Servos sind depowered, kein sichtbarer
   Effekt)
4. PSU an
5. Beobachten: Beine fahren **direkt** in die suspended-Position (vom
   Hold-Last-Servo-Verhalten) — kein Zwischen-Stopp bei horizontal.

**Test V3 — Plugin-Restart (Hot):**
1. Plugin laeuft, Beine in suspended (von V2)
2. Strg+C → Plugin neu starten
3. Beobachten: Beine bleiben (fast) wo sie sind, kein Aufschnellen
   Richtung Mitte.

**Test V4 — pkill-Restart:**
1. Plugin laeuft, Beine in suspended
2. `pkill -9 -f ros2` (kill ohne Cleanup)
3. Beobachten: Watchdog-Trip nach 200 ms → Servos werden passiv (PWM-aus)
   → Beine bleiben kurz haengen (Servo-Gear-Reibung) und sinken dann
   minimal.
4. Plugin neu starten
5. Beobachten: Beine fahren **direkt** in suspended ohne Aufschnellen.

### 5.4 Stage-A-Re-Verifikation

Nach erfolgreichen V1-V4: kompletter Stage-A-Test-Workflow aus
[`phase_13_desktop_stage_a_initial_pose_test_commands.md`](phase_13_desktop_stage_a_initial_pose_test_commands.md)
durchlaufen. Erwartung: alle Schritte gruen ohne Zucken-Beobachtungen.

---

## 6. Done-Kriterien

- [ ] FW-Code-Aenderungen 3.1, 3.2, 3.3 in `~/hexapod_servo_driver/src/main.cpp`
- [ ] FW-Build erfolgreich (`cmake .. && make -j$(nproc)`)
- [ ] FW geflasht via picotool (`sudo picotool load` + `reboot`)
- [ ] `tools/test_servo2040.py` Kommentare aktualisiert
- [ ] Plugin: 400 ms breather → 10 ms ([`hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp))
- [ ] Plugin: `PtyActivateRespectsStaggerTiming` Band → `[800, 1200]` ms
- [ ] Plugin: `colcon build --packages-select hexapod_hardware` gruen
- [ ] Plugin: `colcon test --packages-select hexapod_hardware` 239 gruen
- [ ] Live V1 (Cold-Start ohne Plugin): Beine passiv ✓
- [ ] Live V2 (Plugin-Boot ohne PSU): Beine fahren direkt in suspended ✓
- [ ] Live V3 (Plugin-Restart hot): kein Aufschnellen ✓
- [ ] Live V4 (pkill-Restart): kein Aufschnellen ✓
- [ ] Stage A komplett re-verifiziert (L1-L7 aus Stage-A-Test-Commands)
- [ ] Stage-A-Plan-Doku §3 (Pendenz FW-Optimierung) als ✅ markiert
- [ ] Memory-Eintrag: `project_servo2040_fw_phase13_fix.md` mit Datum +
      Commit-Hash der FW und Plugin-Aenderungen

---

## 7. Auswirkungen / Risiken

| # | Risiko | Wahrscheinlichkeit | Mitigation |
|---|---|---|---|
| R1 | FW-Fix bricht andere Use-Cases (z.B. `/probe.py`-Tests) | mittel | Vor Flash: `test_servo2040.py` + `probe.py` lesen, jede Annahme zu PWM-Output-bei-disabled checken |
| R2 | Co-Versionierung: alte Plugin (mit 400 ms breather) + neue FW → on_activate dauert ~1.3 s, ist aber funktional. Neue Plugin (10 ms breather) + alte FW → Zucken bleibt | gering, da User Build/Flash gemeinsam macht | Plugin- und FW-Aenderung sequenziell committen, gemeinsame Memory-Pendenz |
| R3 | `g_servos->disable_all()` in handle_reset koennte Pimoroni in einen unerwartet- en Zustand bringen (Pin-Konfiguration verloren) | gering | `disable()` setzt nur `enabled=false` + PWM auf 0, behaelt Calibration. Live-V1-Test verifiziert |
| R4 | FW-Fix 2 (`current=target` bei disabled) wenn Servo gerade enabled wird mit grossen Delta → schlagartige Bewegung | gering — Soft-Ramp ist fuer ACTIVE Servos, was wir hier eigentlich entkoppeln. ENABLE_SERVO setzt servo_enabled=true; nachfolgende SET_TARGETS triggern Soft-Ramp normal | Live-V2-Test verifiziert. Plus: Stage-A ENABLE_SERVO-Stagger 50 ms bleibt erhalten, also pro Bein nur ein Servo "schaltet scharf" |
| R5 | Flash schlaegt fehl (picotool nicht im PATH, USB-Issue) | gering | User hat picotool aus Phase 7. README beschreibt den Workflow. Bei Fehlern: Servo2040 manuell in BOOTSEL-Modus (BOOTSEL-Taste halten beim Anstecken) |
| R6 | Andere FW-Tests (Phase 7 Stages C/E) zeigen unerwartet andere Symptome | mittel | Test-Plan §5.3 mit V1-V4 deckt die haeufigsten Faelle ab. Bei Stage-A-Re-Verifikation Test L1-L7 zusaetzliche Validation |

---

## 8. Rollback-Plan

Falls die neue FW unerwartetes Verhalten zeigt:

1. **Alte FW behalten:** vor dem Flash die alte `Hexapod_servo_driver.uf2`
   wegsichern:
   ```bash
   cp ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2 \
      ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2.pre-phase13-fix
   ```
2. **Rollback:**
   ```bash
   sudo picotool load ~/hexapod_servo_driver/build/Hexapod_servo_driver.uf2.pre-phase13-fix
   sudo picotool reboot
   ```
3. **Plugin-Rollback:** git revert der hexapod_hardware-Aenderungen
   (breather + Test-Band):
   ```bash
   cd ~/hexapod_ws
   git log --oneline src/hexapod_hardware/src/hexapod_system.cpp
   git revert <commit-hash-der-FW-fix-plugin-anpassung>
   ```

Sicherer ist ein eigener Git-Branch fuer den Fix:
```bash
cd ~/hexapod_servo_driver
git checkout -b phase13-fw-fix
# ... Aenderungen ...
git commit -am "phase13: fix Pimoroni PWM auto-enable on FW boot/reset"
# Bei Bedarf: git checkout main && git branch -D phase13-fw-fix
```

Plugin-side analog (im hexapod_ws).

---

## 9. Cross-References

**FW-Repo:**
- [`hexapod_servo_driver/CLAUDE.md`](../../hexapod_servo_driver/CLAUDE.md) — FW-Repo-Konventionen
- [`hexapod_servo_driver/README.md`](../../hexapod_servo_driver/README.md) — Build/Flash-Workflow
- [`hexapod_servo_driver/src/main.cpp`](../../hexapod_servo_driver/src/main.cpp) — FW-Source (alle Fixes hier)
- [`pimoroni-pico/drivers/servo/servo_state.cpp`](../../../pimoroni-pico/drivers/servo/servo_state.cpp) — Wurzel: `set_pulse_with_return` enabled automatisch

**Plugin-Repo (hexapod_ws):**
- [`hexapod_system.cpp`](../src/hexapod_hardware/src/hexapod_system.cpp) — Plugin (breather entfernen)
- [`test_hexapod_system.cpp`](../src/hexapod_hardware/test/test_hexapod_system.cpp) — Test-Band zurueck

**Stage-A-Kontext:**
- [`phase_13_desktop_stage_a_initial_pose_plan.md`](phase_13_desktop_stage_a_initial_pose_plan.md)
- [`phase_13_desktop_stage_a_initial_pose_test_commands.md`](phase_13_desktop_stage_a_initial_pose_test_commands.md)
- [`phase_13_desktop_pre_bringup_plan.md`](phase_13_desktop_pre_bringup_plan.md)

**Phase 7 FW-Doku (Vorgaenger):**
- [`phase_7_servo2040_fw.md`](phase_7_servo2040_fw.md) — Original FW-Stage
- [`phase_7_progress.md`](phase_7_progress.md) — FW-Stage-Progress

**Memory-Pendenzen (nach Abschluss):**
- `project_servo2040_fw_phase13_fix.md` — Commit-Hashes FW + Plugin, Datum
- `feedback_validate_hardware_hypothesis_via_code.md` (existing) — diese
  Stage ist ein weiteres Beispiel: das Pimoroni-Verhalten wurde durch
  Code-Lese verifiziert bevor wir geraten haben

---

## 10. Reihenfolge der Ausfuehrung

1. **User-Freigabe dieser Plan-Doku** ← jetzt
2. FW-Aenderungen 3.1, 3.2, 3.3 in `~/hexapod_servo_driver/src/main.cpp`
3. `tools/test_servo2040.py` Kommentar aktualisieren (FW-Repo)
4. FW-Build (`cmake .. && make`)
5. **User flasht** die neue FW (`sudo picotool load ... && reboot`)
6. Plugin-Aenderungen: 400 ms-breather → 10 ms, Test-Band auf [800, 1200]
7. Plugin-Build + Tests gruen
8. **User fuehrt Live-V1-V4 durch**, kurze Status-Meldung pro Test
9. Falls V1-V4 gruen: **User fuehrt Stage-A-Re-Verifikation** durch
   (Schritte aus phase_13_desktop_stage_a_initial_pose_test_commands.md)
10. Falls Stage-A gruen: Done-Kriterien §6 abhaken, Memory-Eintrag,
    Stage-A-Plan-Doku §3 ✅, Phase-13-Desktop-Pre-Bringup-Plan §2
    Stage-A-Status auf ✅.

---

**Erstellt 2026-05-28.** Wartet auf User-Freigabe vor Implementation.
