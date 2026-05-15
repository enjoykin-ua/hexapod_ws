# Phase 9 — Stufe C — Test-Anleitung

**Was geprüft wird:** Die Kalibrierungs-Lib (`calibration.*`) lädt das
YAML-Schema korrekt, validiert es streng, konvertiert Joint-Radiant zu
Pulse-µs piecewise-linear über drei Stützstellen, und die Inverse
liefert die Roundtrip-Identität — auch in asymmetrischen und
gespiegelten Konfigurationen.

**Was NICHT in Stufe C geprüft wird:**
- Echte URDF-Limits aus dem Hexapod-Modell automatisch lesen → **Stufe D** (`on_init` parsed `info_.joints`)
- Plugin-Lifecycle, `read()`/`write()` → **Stufe D**
- Phase-10-Kalibrierungstool (jog + YAML schreiben) → **Phase 10**

Diese Stufe ist ein reiner **C++-Unit-Test-Smoke-Test**. Kein ROS-Stack,
keine HW.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test C.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:**
- `Summary: 1 package finished [X.XXs]`
- **Kein** Block mit `stderr: hexapod_hardware`
- Keine `warning:`-Zeilen im Output

---

## Test C.2 — Volle Test-Suite grün (6/6)

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** Letzte Zusammenfassung zeigt
`100% tests passed, 0 tests failed out of 6`.

Die sechs Tests sind:
1. `test_calibration` — **erweitert in Stufe C** (27 gtest-Cases)
2. `test_servo2040_protocol` — aus Stufe B (36 gtest-Cases)
3. `cppcheck`
4. `lint_cmake`
5. `uncrustify`
6. `xmllint`

---

## Test C.3 — Alle 30 Calibration-gtest-Cases sichtbar machen

```bash
./build/hexapod_hardware/test_calibration
```

**Erwartung am Ende:**
```
[==========] 30 tests from 8 test suites ran. (X ms total)
[  PASSED  ] 30 tests.
```

Die acht Test-Suites sind:
- `YamlLoader` (12 Tests) — Happy-Path (4: Loads, Lookup, Defaults-Fallback, Per-Servo-Override), Error-Path (8: GarbageInput, MissingServoMap, MissingJointName, MissingServoEntry, InvalidDirection, DegeneratePulseTriplet, FileNotFound, **TypeMismatchAsRuntimeError**)
- `SetJointLimits` (2 Tests) — Named-Joint, Silent-Ignore-Unknown
- `RadiansToPulse` (6 Tests) — Zero=Pulse-Zero, JointLower=PulseMin, JointUpper=PulseMax, ±π/4, Asymmetric-Slopes, Negative-Direction-Mirror
- `PulseToRadians` (2 Tests) — Inverse für Pulse-Zero und für Endpoints
- `Roundtrip` (3 Tests) — Forward∘Inverse=Identity für symmetrisch, asymmetrisch, gespiegelt
- `Bounds` (2 Tests) — Negative + Overflow-Index `std::out_of_range`
- `RealConfigFile` (1 Test) — Echtes `src/hexapod_hardware/config/servo_mapping.yaml` parst ohne Fehler
- **`StrongExceptionGuarantee` (2 Tests)** — `FailedLoadDoesNotMutateState` (missing entries), `FailedTypeMismatchDoesNotMutateState` (type-mismatch deep im Loop) — beide verifizieren dass ein fehlgeschlagener `load_from_string` Member-State und `set_joint_limits`-Werte unangetastet lässt

---

## Test C.4 — Roundtrip-Identität manuell verifizieren

Optional, zur Beruhigung dass die Konversion mathematisch sauber ist:

```bash
./build/hexapod_hardware/test_calibration --gtest_filter="Roundtrip.*"
```

**Erwartung:**
```
[       OK ] Roundtrip.ForwardThenInverseIsIdentitySymmetric
[       OK ] Roundtrip.ForwardThenInverseIsIdentityAsymmetric
[       OK ] Roundtrip.NegativeDirectionRoundtrips
[  PASSED  ] 3 tests.
```

Diese drei Tests iterieren über den ganzen Joint-Range in 0.1-rad-Schritten
und prüfen `inverse(forward(rad)) == rad` mit 1e-9 Toleranz — in symmetrischer,
asymmetrischer (`pulse_min/zero/max=600/1500/2400`, `joint=[-1.5,+1.0]`)
und gespiegelter (`direction=-1`) Konfiguration.

---

## Test C.5 — YAML-Schema-Error-Path

Optional, zur Beruhigung dass der Loader fehlerhafte YAMLs sauber abweist:

```bash
./build/hexapod_hardware/test_calibration --gtest_filter="YamlLoader.Rejects*"
```

**Erwartung:**
```
[       OK ] YamlLoader.RejectsGarbageInput
[       OK ] YamlLoader.RejectsMissingServoMap
[       OK ] YamlLoader.RejectsMissingJointName
[       OK ] YamlLoader.RejectsMissingServoEntry
[       OK ] YamlLoader.RejectsInvalidDirection
[       OK ] YamlLoader.RejectsDegeneratePulseTriplet
[  PASSED  ] 6 tests.
```

Jeder dieser Tests erwartet eine `std::runtime_error`-Exception mit
spezifischer Schema-Verletzung im Message-Text. Wenn ein Test als
**PASSED** läuft obwohl er FAILT erwartet wird — d.h. der Loader nimmt
kaputte YAML widerstandslos an — ist das ein Regression.

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `Roundtrip.*` failt | Inverse wählt die falsche piecewise-Seite, oder direction-Flip im Vorzeichen falsch | `pulse_us_to_radians` in `src/calibration.cpp` re-prüfen — `direction * dp >= 0`-Check ist das Herzstück |
| `RadiansToPulse.JointLowerHitsPulseMin` failt | URDF-Limit nicht gesetzt, fallback ±1.57 greift, Test rechnet aber mit anderem Wert | `apply_symmetric_limits()`-Helper im Test gucken |
| `RealConfigFile.InstalledServoMappingParses` failt | YAML im Source-Tree ist kaputt (vielleicht versehentlich editiert?) | `src/hexapod_hardware/config/servo_mapping.yaml` mit `yamllint` validieren |
| `YamlLoader.RejectsDegeneratePulseTriplet` PASSED obwohl es FAILT erwartet | Sanity-Check `pulse_min < pulse_zero < pulse_max` ist weg | `load_from_string()` in `src/calibration.cpp` — der throw-Block für degenerate Triplets |

---

## Statusmeldung an Claude

Nach Durchlauf der Tests reicht eine knappe Rückmeldung:
- `C.1–C.3 alle grün` → wir können mit Stufe D (`HexapodSystemHardware`
  voll implementieren — Lifecycle, Reader-Thread, Loopback-Mode,
  USB-Reconnect) weitermachen
- `C.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe der gtest-Logs ist nicht nötig — nur bei Fehlern den
relevanten gtest-Output (failende Assertion + Datei:Zeile).
