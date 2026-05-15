# Phase 9 — Stufe D.4 — Test-Anleitung

**Was geprüft wird:** `on_configure` öffnet den seriellen Port und
startet den Reader-Thread (oder skipt das in Loopback-Mode); `on_cleanup`
stoppt den Reader-Thread und schließt den Port — in dieser Reihenfolge.
Plus: configure/cleanup-Cycle wiederholbar, RAII-Destructor cleanen up,
bad path produziert klare ERROR-Logs.

**Was NICHT in D.4 geprüft wird:**
- ENABLE_SERVO + SET_TARGETS → **D.5** (`on_activate`)
- write/read mit Pulse-Konversion → **D.6**
- Reconnect bei mid-run-Disconnect → **D.7**

D.4 nutzt `openpty(3)` für PTY-basierte Tests — kein echter Servo2040
nötig.

---

## Vorbereitung

```bash
cd ~/hexapod_ws
source /opt/ros/jazzy/setup.bash
```

---

## Test D.4.1 — Build grün, keine Warnings

```bash
colcon build --packages-select hexapod_hardware --event-handlers console_direct+
```

**Erwartung:** `Summary: 1 package finished`, kein `stderr`-Block, keine `warning:`.

---

## Test D.4.2 — Volle Test-Suite grün

```bash
colcon test --packages-select hexapod_hardware --event-handlers console_direct+
colcon test-result --test-result-base build/hexapod_hardware
```

**Erwartung:**
- `colcon test` läuft ohne `with test failures`
- `colcon test-result` Endzeile: `Summary: 162 tests, 0 errors, 0 failures, 15 skipped`

---

## Test D.4.3 — D.4-Tests fokussiert (6 Tests, ~2 s)

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="HexapodSystemConfigure.*"
```

**Erwartung:**
```
[==========] 6 tests from HexapodSystemConfigure (~2 s total)
[  PASSED  ] 6 tests.
```

Die sechs Tests:

| Test | Was geprüft wird |
|---|---|
| `LoopbackConfigureSucceedsWithoutPort` | Loopback-Mode: `on_configure` returnt SUCCESS, ohne `/dev/ttyACM0` zu öffnen (das wäre auf den meisten CI-Maschinen nicht vorhanden) |
| `LoopbackCleanupIsSafeEvenIfNotConfigured` | `on_cleanup` ist idempotent: doppelter Aufruf + Aufruf ohne `on_configure` → SUCCESS |
| `RejectsNonExistentSerialPort` | `loopback_mode=false` + nicht-existenter Pfad → ERROR mit klarer Message in den Logs (Hinweis auf `dialout`-Gruppe + URDF-Param) |
| `ConfigureWithPtyOpensPortAndStartsReader` | pty-Pair: slave-Pfad als `serial_port` → `on_configure` öffnet, Reader läuft (verifiziert durch Garbage-Bytes vom Master); `on_cleanup` joined in < 1.5 s |
| `ConfigureCleanupCycleCanRepeat` | 3 × `on_configure`/`on_cleanup`-Zyklus → kein FD-Leak, kein Thread-Leak (ros2_control kann Lifecycle so durchlaufen z.B. nach Re-Activation) |
| `DestructorCleansUpAutomatically` | Plugin im Scope erstellen + configure, **kein** expliziter `on_cleanup` → Destructor joined Reader + schließt Port in < 1.5 s (RAII-Garantie) |

---

## Test D.4.4 — Reihenfolge der Cleanup-Operationen verifizieren

Die kritische Eigenschaft `reader.stop()` **vor** `serial_port.close()`
ist nicht direkt testbar, aber wenn sie verletzt wäre, würde
`ConfigureWithPtyOpensPortAndStartsReader` mit `died_=true` enden, weil
der Reader nach `read()` auf einem geschlossenen FD `EIO`/`POLLNVAL`
sieht und sich selbst killt. Aktuell läuft der Test grün → Reihenfolge
ist korrekt.

```bash
./build/hexapod_hardware/test_hexapod_system \
    --gtest_filter="*ConfigureWithPtyOpensPortAndStartsReader*"
```

---

## Was tun, wenn ein Test fehlschlägt

| Symptom | Häufige Ursache | Fix |
|---|---|---|
| `LoopbackConfigureSucceedsWithoutPort` failt mit Port-Open-Error | `on_configure` checkt `loopback_mode_` nicht früh genug | `if (loopback_mode_) return SUCCESS;` muss VOR `serial_port_.open()` stehen |
| `ConfigureWithPtyOpensPortAndStartsReader` failt mit Hang | `on_cleanup` ruft `serial_port_.close()` vor `reader_.stop()` | Reihenfolge umkehren — siehe Notizen in `hexapod_system.cpp` |
| `DestructorCleansUpAutomatically` failt mit Hang oder > 1.5 s | Member-Deklarations-Reihenfolge im Header falsch | `SerialPort serial_port_` muss VOR `Servo2040Reader reader_` deklariert sein (Destruktor läuft in umgekehrter Reihenfolge → Reader stop+join zuerst) |
| `ConfigureCleanupCycleCanRepeat` failt im 2. Zyklus | `serial_port_.open()` wirft beim Re-Open weil `fd_ >= 0` ist | Sicherstellen dass `on_cleanup` `serial_port_.close()` aufruft (setzt `fd_ = -1`) |
| Build-Fehler `openpty` not found | `util`-Link in CMakeLists fehlt | `target_link_libraries(test_hexapod_system util)` ergänzen |

---

## Statusmeldung an Claude

- `D.4.1–D.4.3 alle grün` → weiter mit **D.5** (`on_activate`/`on_deactivate`: Boot-Sequenz RESET → 18× ENABLE_SERVO mit 50 ms Host-Stagger → SET_TARGETS neutral)
- `D.4.X failt: <kurze Symptom-Beschreibung>` → ich diagnostiziere

Vollausgabe nur bei Fehler.
