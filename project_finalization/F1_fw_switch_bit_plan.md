# Stage F1 — servo2040 FW: Schalter → `status_flags` Bit 7

> Teil von [Block F](F_systemsteuerung_plan.md). Detail-Plan nach CLAUDE.md §4.
> Code-Repo: `~/hexapod_servo_driver` (eigenständig, kein ROS2). FW-Phase 7 ist
> abgeschlossen → Progress hier (Block F), **nicht** in `phase_7_progress.md`.
> Protokoll-Spec-Update: `hexapod_servo_driver/PROTOCOL.md` (Bit 7).
> Test-Anleitung: [`F1_fw_switch_bit_test_commands.md`](F1_fw_switch_bit_test_commands.md).

---

## 1. Logik-Skizze / Pseudocode

**Ausgangslage (bereits da, Wiring-Test):** A1 = GP27, interner Pull-Down,
active-high (zu=1=grün, auf=0=rot). `poll_switch()` entprellt (2 Ticks = 20 ms) und
treibt die LED rot/grün aus `switch_state_stable`. LED-Verhalten **bleibt unverändert**.

**Neu:** aus dem entprellten Pegel ein **zeit-qualifiziertes, gearmtes**
„Shutdown-Request"-Signal ableiten und als Bit 7 in jeder STATE_RESPONSE mitsenden.

### Konstanten (`config.hpp`)
```cpp
namespace cfg { constexpr uint32_t SHUTDOWN_HOLD_MS = 3000; }   // F5: ≥3 s offen
namespace status { constexpr uint8_t SHUTDOWN_REQUEST = 1u << 7; }  // freies Bit
```

### Zustand (Globals in `main.cpp`)
```cpp
bool            switch_armed      = false;  // true, sobald einmal CLOSED gesehen
absolute_time_t switch_open_since;          // Zeitstempel: Pegel wurde OPEN
bool            shutdown_request  = false;  // Quelle für Bit 7
```

### Erweiterung `poll_switch()` (läuft jede Tick, 100 Hz)
```
auf entprellter Transition → CLOSED:
    switch_armed     = true        // arm (F2/Fa)
    shutdown_request = false       // Schließen storniert einen offenen Request
    LED grün                       // (wie gehabt)

auf entprellter Transition → OPEN:
    switch_open_since = now()
    LED rot                        // (wie gehabt) — assert NOCH NICHT

jede Tick, zusätzlich (Pegel-Halten prüfen, nicht nur auf Flanke):
    if switch_state_stable == OPEN
       and switch_armed
       and not shutdown_request
       and (now() - switch_open_since) >= SHUTDOWN_HOLD_MS:
            shutdown_request = true          // 3 s gehalten → Request
```

### Bit 7 senden (`handle_get_state`)
Bit 7 wird **am Sendezeitpunkt aus `shutdown_request` abgeleitet** (NICHT im
`status_flags`-Global mitgeführt) — so kann ein RESET (der `status_flags` neu setzt)
das Bit nicht versehentlich verwischen:
```cpp
uint8_t flags = status_flags;
if (shutdown_request) flags |= status::SHUTDOWN_REQUEST;
payload[off++] = flags;
```

### Begründung pro Design-Entscheidung
- **3-s-Halten in der FW** (E2): Bit ist ein sauberes „bewusster Wunsch", kein roher
  Pegel-Zappler. Host bleibt dumm.
- **Arm-nach-CLOSED** (E3/F2): Boot mit offenem Schalter darf **nicht** sofort
  Shutdown anfordern. Erst „zu gesehen" → scharf.
- **Schließen storniert** (track-level, kein FW-Latch): vorhersagbar fürs Bench-
  Testen; die *Nicht-zurücknehmen*-Semantik macht der Supervisor (latcht ROS-seitig).
- **Bit am Sendezeitpunkt ableiten**: entkoppelt von RESET/Trip-Logik im
  `status_flags`-Global, keine Sync-Fallen.
- **LED unverändert**: rot = offen = (wird/ist) Request — konsistente Optik, keine
  zweite Bedeutung nötig.

---

## 2. Tests-Liste mit Begründung

**Bench (Board an USB-Strom, Schalter an A1, `tools/log_state.py` `flags`-Spalte):**

| ID | Test | Erwartung | Warum |
|---|---|---|---|
| F1-T1 | LED-Regression: zu/auf umlegen | grün/rot wie bisher | Wiring-Test darf nicht kaputtgehen |
| F1-T2 | Boot mit Schalter **OFFEN**, >3 s warten | Bit 7 bleibt **0** (`flags` nie `…80`) | Arm-Guard (F2): kein Boot→Shutdown |
| F1-T3 | zu (grün) → auf (rot), halten | Bit 7 = 0 für <3 s, kippt bei ~3 s auf **1** (`0x80`) | Kern: 3-s-Halten |
| F1-T4 | auf <3 s, dann wieder zu | Bit 7 **nie** gesetzt | Fehlauslöse-Schutz |
| F1-T5 | nach Bit 7 = 1: Schalter wieder zu | Bit 7 **clear** (0x80 weg) | track-level / Storno |
| F1-T6 | Build grün | `make` ohne Fehler/Warnung | — |

**Bewusst NICHT getestet (deferred / scope-out):**
- ROS-Konsum des Bits → **F2+** (hier kein ROS).
- Exakte 3-s-Genauigkeit per Oszi/Logic-Analyzer → unnötig; `log_state.py` @ 20 Hz
  sieht die ~3-s-Flanke klar genug. (Analog [[project_phase9_h_oscilloscope_pending]].)
- Host-konfigurierbare Haltezeit → FW-Konstante reicht, keine SET_*-Erweiterung.

---

## 3. Progress-Checkliste (Done-Vertrag — 1:1 ins Progress-File)

```
- [ ] F1.1  config.hpp: SHUTDOWN_HOLD_MS=3000 + status::SHUTDOWN_REQUEST (1u<<7)
- [ ] F1.2  main.cpp: switch_armed + switch_open_since + shutdown_request Globals
- [ ] F1.3  main.cpp: poll_switch() um Arm + 3-s-Halten erweitert
- [ ] F1.4  main.cpp: handle_get_state() leitet Bit 7 aus shutdown_request ab
- [ ] F1.5  LED-Rohpegel (grün/rot) unverändert (Regression)
- [ ] F1.6  Build grün (make, keine Warnung)
- [ ] F1.7  Bench F1-T1..T5 grün (via flash_and_verify.py + log_state.py)
- [ ] F1.8  PROTOCOL.md: Bit 7 SHUTDOWN_REQUEST dokumentiert
- [ ] F1.9  Self-Review-Tabelle (CLAUDE.md §4) — Fixe vor Fertig-Meldung
```

---

## 4. Entscheidungen (User-Review erledigt, vor Code-Beginn)

Alle drei vom User bestätigt — keine offenen Punkte mehr:

1. **track-level (kein FW-Latch):** Schließen des Schalters storniert einen noch
   nicht konsumierten Request (Bit 7 → 0). Die Endgültigkeit („Shutdown nicht mehr
   zurücknehmbar") latcht der **Supervisor** ROS-seitig (Block F, Stage F4), nicht
   die FW. Begründung: einfacher fürs Bench-Testen, klare Schichtentrennung.
   *Verworfen:* Bit in der FW latchen bis RESET/Power-Cycle.
2. **LED simpel rot bei aktivem Request:** kein Blinken/keine Zweit-Bedeutung. Rot =
   offen = (wird/ist) Request — eine konsistente Optik. *Verworfen:* Blink-Bestätigung
   ab „Request gesetzt".
3. **Haltezeit = FW-Konstante `SHUTDOWN_HOLD_MS` (3000 ms):** nicht host-
   konfigurierbar. *Verworfen:* Protokoll-Erweiterung für eine einstellbare Haltezeit
   (unnötiger Aufwand).
