# Phase 9 — Stufe D.7 — Plan

> **Status:** Plan, noch nicht implementiert. **Code beginnt erst nach
> User-Freigabe** (CLAUDE.md §4).
>
> **Parent-Plan:** [`phase_9_stage_d_plan.md §D.7`](phase_9_stage_d_plan.md)
> — Architektur-Skizze, Race-Schutz, Recovery-Workflow.
>
> **Test-Anleitung:** wird nach Implementations-Freigabe finalisiert
> (`phase_9_stage_d_7_test_commands.md`).

---

## Ziel der Sub-Stage

Bisher (Stand D.6): Wenn der USB-Stecker während Betrieb gezogen wird,
**stirbt der Reader-Thread** (setzt `died_ = true`), `write()` / `read()`
returnen `ERROR`, ros2_control deaktiviert das Plugin. Nach Stecker-rein
muss der User den **ganzen Stack neu starten** — Plugin reloaded, Reader
startet, etc.

D.7 macht den Reader-Thread **disconnect-tolerant**: bei einem
USB-Disconnect versucht er in einer Backoff-Schleife wiederholt zu
reconnecten. Wenn das gelingt, kann der User den Controller manuell
re-aktivieren (`ros2 control switch_controllers --activate ...`), ohne
den Stack zu beenden.

Das ist **die zentrale Robustheits-Stufe** für Phase 10+ (Bench-Bringup
mit Stecker-Wackeln, Phase-11/Pi-Plattform mit USB-Reset). Ohne D.7 ist
jeder Disconnect ein Stack-Restart.

---

## Was geändert wird (Architektur-Übersicht)

```
                        Vorher (D.6)                  Nachher (D.7)
                        ─────────────                 ──────────────
USB-Disconnect           read_some() throws            read_some() throws
                              │                              │
                              ▼                              ▼
Reader-Thread            died_ = true                  trigger_reconnect()
                          (Thread exit)                  ┌──────────────┐
                              │                          │ port.close() │
                              ▼                          │ Backoff-Loop:│
write()/read()           return ERROR                    │  open() retry│
                              │                          └──────────────┘
                              ▼                              │
ros2_control             deactivate                      bei Erfolg:
                                                         normaler Loop weiter
                                                              │
                                                              ▼
                         Plugin im inactive          Plugin BLEIBT inactive
                         (Stack-Restart nötig)       (Re-Activate per CLI)
```

**Drei Bausteine ändern sich:**

1. **`Servo2040Reader::loop`** — bei `system_error` aus `read_some` nicht
   mehr `died_=true`+exit, sondern in eine Reconnect-Routine springen
   und dann den Loop fortsetzen.
2. **Neue Methode `Servo2040Reader::reconnect_loop`** — schließt FD,
   versucht open() mit Backoff bis Erfolg ODER stop_requested.
3. **`SerialPort` exclusive_lock** — bisher nur in Tests verifiziert
   (D.1), jetzt im echten Reconnect-Pfad genutzt: während close+open hält
   der Reader-Thread den exclusive_lock; ein paralleler `write_all()` aus
   dem Plugin-Tick blockiert auf shared_lock.

---

## Pseudocode

### `Servo2040Reader::loop` (geänderter Teil)

```cpp
while (!stop_requested_) {
    std::size_t n = 0;
    try {
        n = port.read_some(buf.data(), buf.size());   // shared_lock intern
    } catch (const std::system_error & e) {
        RCLCPP_ERROR(reader_logger(),
            "Reader: read failed (%s) — entering reconnect-loop", e.what());
        if (!reconnect_loop(port)) {
            // stop_requested_ wurde gesetzt während wir reconnecten;
            // sauber raus.
            return;
        }
        // Erfolgreich reconnected → assembly-Puffer leeren (mid-frame
        // Bytes vom alten Stream sind nutzlos) und Loop fortsetzen.
        assembly.clear();
        continue;
    }
    // ... Frame-Assembly wie vorher ...
}
```

### Neue `Servo2040Reader::reconnect_loop`

```cpp
// Returns true bei Erfolg, false wenn stop_requested_ während Backoff.
bool Servo2040Reader::reconnect_loop(SerialPort & port)
{
    const std::array<int, 7> backoff_ms = {100, 200, 500, 1000, 2000, 5000, 5000};

    // exklusiver Lock blockt parallele write_all-Aufrufe aus dem Plugin-Tick
    auto lock = port.exclusive_lock();
    const std::string path = port.path();    // gemerkter Pfad (Stage D.4 setzt ihn)
    port.close();   // FD weg, parallele writes failen jetzt clean

    std::size_t attempt = 0;
    while (!stop_requested_) {
        const int wait_ms = backoff_ms[std::min(attempt, backoff_ms.size() - 1)];
        RCLCPP_WARN(reader_logger(),
            "Reader: reconnect attempt %zu (wait %d ms before next try)",
            attempt + 1, wait_ms);

        // Sleep aufgeteilt in 50-ms-Chunks, damit stop_requested_ schnell durchkommt
        for (int slept = 0; slept < wait_ms && !stop_requested_; slept += 50) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        if (stop_requested_) {return false;}

        try {
            port.open(path);
            RCLCPP_INFO(reader_logger(),
                "Reader: reconnect SUCCESS after %zu attempts. "
                "Plugin remains in inactive — manually run "
                "`ros2 control switch_controllers --activate <controllers>`",
                attempt + 1);
            return true;
        } catch (const std::exception & e) {
            // open() failt weiterhin → nächste Backoff-Stufe
            RCLCPP_DEBUG(reader_logger(),
                "Reader: reconnect attempt %zu failed: %s",
                attempt + 1, e.what());
        }
        ++attempt;
    }
    return false;
}
```

### Kleine SerialPort-Ergänzungen

```cpp
class SerialPort {
public:
    // ... bestehend ...
    const std::string & path() const noexcept;   // NEU: zuletzt geöffneter Pfad
private:
    std::string path_{};   // gesetzt in open(), gelöscht in close()
};
```

Ohne `path()` müsste der Reader sich den Pfad in `start()` merken — auch
machbar, aber er liegt logisch beim `SerialPort` (er weiß ja, wo er
gerade geöffnet ist). Ein `string`-Member zusätzlich, ~3 Zeilen Code.

---

## Begründung der Design-Entscheidungen

**Reconnect im Reader-Thread, nicht im Plugin-Hauptthread.**
- Reader sieht den Disconnect zuerst (POLLHUP / EIO im `poll`-Loop).
- Plugin-Tick (50 Hz) darf nicht blockieren — bei Backoff > 20 ms
  würde der Tick einfrieren. Im Reader-Thread ist Backoff ok.
- Phase-9-Plan-Doku §D.7 ist explizit: „im Reader-Thread, weil der's
  zuerst sieht".

**Backoff-Sequenz `{100, 200, 500, 1000, 2000, 5000, 5000, …}` (feste Liste).**
- Erste 3 schnell (100/200/500 ms): typischer USB-Reset auf Linux
  dauert ~200 ms, dann ist `/dev/ttyACM0` wieder da.
- Dann linear flacher (1/2/5 s): wenn das Re-Plug länger dauert, ist
  busy-polling unhöflich gegen den Scheduler.
- Steady-state 5 s: lange auf den Stecker warten ist OK; CPU-Load
  vernachlässigbar.
- Alternative wäre exponentielles Backoff (100, 200, 400, 800, …),
  aber die Plan-Doku §D.7 spezifiziert die feste Liste — ich halte mich
  daran (vermutlich mit guter Begründung aus Phase-7-Erfahrung).

**`exclusive_lock` aus SerialPort wird hier endlich genutzt.**
- D.1 hat den `shared_mutex` reingebaut, D.7 ist der Use-Case.
- Race: parallel write_all (Plugin-Tick) + close+open (Reader-Reconnect).
- Reader hält exclusive für die ganze close→open-Phase. Wenn ein write_all
  parallel reinkommt, blockt es auf `read_some`'s shared_lock-Acquire
  bis Reader fertig.
- **Nachher**: write_all liefert ENTWEDER auf den neuen FD (Reconnect erfolgreich)
  ODER scheitert nach Timeout/Disconnect-Errno (Reconnect läuft noch).

**Plugin bleibt im `inactive`-State nach erfolgreichem Reconnect.**
- Das ist bewusst: nach einem Disconnect kann der Roboter mechanisch
  in undefinierter Pose sein (Servos waren spannungsfrei, Beine sacken).
- User muss „OK, ich habe geprüft" durch explizites
  `ros2 control switch_controllers --activate ...` signalisieren.
- INFO-Log nach Reconnect zeigt den nötigen Befehl prominent.

**Backoff-Schlaf in 50-ms-Chunks, statt einem großen `sleep_for(5s)`.**
- Wenn der User `on_cleanup` aufruft während Reader im Reconnect-Loop,
  muss er innerhalb von 1.5 s aussteigen (Test `StopJoinsCleanlyWithin1500ms`
  aus D.2 deckelt das).
- 50-ms-Chunks: max Stop-Latenz ~50 ms. Akzeptabel.

**`died_` semantik bleibt „terminal error".**
- D.6 nutzt `died_` als Signal an `read()` für `return_type::ERROR`.
- Bei Reconnect-Success in D.7 darf der Reader NICHT mehr `died_` setzen
  — er läuft ja wieder.
- Nur wenn Reconnect endgültig scheitert (z.B. interner Exception-Pfad),
  setzen wir `died_`. Backoff alleine ist kein Tod.

---

## Tests (Suite `HexapodSystemReconnect`, ~5 Tests)

Die PTY-basierten Tests für Reconnect sind tricky — eine geschlossene
master-Seite gibt's nicht „wieder", und neue `openpty()` liefert einen
neuen slave-Pfad. Wir testen daher die Bausteine direkt am Reader-Thread,
nicht den vollen Plugin-Lifecycle:

| # | Test | Was wird geprüft |
|---|---|---|
| 1 | `ReaderEntersReconnectLoopInsteadOfDying` | pty pair, Reader start, master close → `is_running() == true` bleibt (kein died_), `died()` bleibt false; nach 500 ms Reader stoppen → sauberer Exit |
| 2 | `ReaderReconnectBackoffRespectsStopSignal` | wie oben + stop() während Backoff (z.B. nach 300 ms, mitten in der ersten Wartezeit) → Reader joined in < 100 ms (innerhalb eines 50-ms-Chunks) |
| 3 | `ReaderReconnectSucceedsAfterPathBecomesAvailable` | start mit nicht-existentem Pfad nach echtem disconnect, dann **mid-test** den Pfad existent machen (z.B. neuen pty erstellen + symlinken) → Reader open() klappt, `is_running()` weiter true. **Heuristik:** dieser Test wird tricky; evtl. nutzen wir eine Test-Hook in SerialPort statt echtem Disconnect-Recovery |
| 4 | `WriteBlocksDuringReconnectAndFailsCleanly` | Concurrency-Test: Thread A spammt write_all, Thread B löst Disconnect + reconnect_loop aus. Verifiziere: keine Race, kein Crash, write_all liefert entweder OK oder system_error (kein Garbage) |
| 5 | `PluginStaysInactiveAfterSuccessfulReconnect` | Full-Plugin-Test: configure → activate → disconnect → wait for reconnect-success → read()/write() liefern weiterhin ERROR (Plugin in inactive bleibt) |

### Test 3 — Reconnect-Erfolg ist die Kern-Schwierigkeit

Mehrere Optionen, mit Tradeoffs:

**Option A: Test-Hook in SerialPort.** Eine `set_open_hook(fn)`-Methode,
die im Test eine künstliche Erfolgs-/Fehl-Sequenz zurückgibt. Sauber
testbar, aber API-Polution (Test-Only-Methode in Production-Klasse).

**Option B: Pfad-via-symlink.** Test erstellt `/tmp/hexapod_test_ttyACM`
als symlink zu pty-A. Reader öffnet via symlink. Bei Disconnect:
master_fd von A closen, A's pty wird unbrauchbar — Reader sieht
Disconnect. Test löscht symlink, erstellt neuen zu pty-B. Reader's open()
über den symlink-Pfad öffnet jetzt pty-B. **Realistischer**, aber
filesystem-abhängig (`/tmp` muss schreibbar sein, Race zwischen Symlink-
Wechsel und open-Versuch).

**Option C: nur testen dass Reader IM Backoff bleibt, nicht dass er
erfolgreich reconnected.** Test 3 fällt weg, Test 1 + 2 reichen für
„nicht-mehr-stirbt-und-stop-sauber". Reconnect-Erfolg wird in **Stage H**
(echte HW) verifiziert via Kabel-ziehen-und-rein-Test.

**Mein Vorschlag: Option C** (siehe „Offene Punkte" unten).

---

## Was Stufe D.7 explizit **nicht** macht

- Kein **automatischer Re-Activate** des Controllers nach Reconnect —
  bewusst manuell (siehe „Plugin bleibt inactive" oben). User-Recovery-
  Workflow wird in der README dokumentiert.
- Keine **Unlimited-Backoff-Cap** — die Backoff-Schleife läuft theoretisch
  unendlich (bis stop oder Erfolg). Wenn der Roboter über Stunden ohne
  Stecker bleibt: ok, Reader-Thread wartet, CPU-Last ~0.
- Keine **per-Servo-Reconnect** — Disconnect ist immer der USB-Stecker
  als Ganzes; einzelne Servos können nicht „verschwinden".
- Kein **Reconnect bei NACK / Watchdog-Trip mid-run** — das ist
  protokoll-level, nicht USB-level. Watchdog-Recovery bleibt manuell
  (Plan-Doku §6, kommt in Phase 10).
- Keine **Auto-Re-Activate via Service-Call** — wäre eine separate
  Komfort-Schicht (Phase 10+), nicht hier.

---

## Progress-Checkliste (geht 1:1 in `phase_9_progress.md`)

Done-Vertrag — alle `[x]` = Sub-Stage fertig:

- [ ] D.7.1 `SerialPort::path()`-Getter ergänzen + `path_`-Member in `open()`/`adopt_fd()` setzen, in `close()` löschen
- [ ] D.7.2 `Servo2040Reader::reconnect_loop` private Methode implementiert:
  1. exclusive_lock auf SerialPort
  2. Path KOPIEREN vor close: `const std::string path = port.path();`
  3. **Early-out wenn `path.empty()`** (adopt_fd-Pfad — kein Reopen möglich, → `died_=true` + return false)
  4. close() — `path_` im SerialPort wird leer, aber unsere lokale Kopie bleibt
  5. Backoff-Schleife mit `{100, 200, 500, 1000, 2000, 5000, 5000}` ms
  6. Sleep in 50-ms-Chunks (für saubere stop_requested_-Reaktion)
  7. open(path) Erfolg → INFO-Log mit Recovery-Befehl + return true
  8. stop_requested_ während Backoff → return false (Reader exit)
- [ ] D.7.3 `Servo2040Reader::loop`-`catch (system_error)` ruft `reconnect_loop` statt sofort `died_=true`. Bei `false` (stop): clean return; bei `true`: assembly-Puffer leeren + `continue`
- [ ] D.7.4 `died_` semantik dokumentiert (Header + .cpp): nur bei terminal-error (Exception aus Loop oder Bad-Alloc), nicht bei Disconnect
- [ ] D.7.5 Tests `test_servo2040_reader.cpp` neue Suite `Servo2040ReaderReconnect`:
  - `EntersReconnectLoopInsteadOfDying` (Disconnect → kein died_, `is_running()` true)
  - `ReconnectBackoffRespectsStopSignal` (stop während Backoff → join < 100 ms)
  - `WriteBlocksDuringReconnectAndFailsCleanly` (concurrency: parallel write_all + reconnect)
- [ ] D.7.6 Tests `test_hexapod_system.cpp` neue Suite `HexapodSystemReconnect`:
  - `PluginStaysInactiveAfterReaderEntersReconnect` (full lifecycle: configure→activate→disconnect → read/write liefert ERROR weiterhin)
- [ ] D.7.7 `colcon build`: grün, keine Warnings
- [ ] D.7.8 `colcon test`: alle gtests grün, total mind. **181 tests, 0 errors, 0 failures**
- [ ] D.7.9 Kritischer Self-Review-Tabelle in `phase_9_progress.md`
- [ ] D.7.10 Eventuelle Post-Review-Fixes mit Code-Kommentaren
- [ ] D.7.11 `phase_9_stage_d_7_test_commands.md` finalisiert mit Test-Filter-Befehlen + Erwartungen + Fehler-Diagnose-Tabelle
- [ ] D.7.12 README.md: Status auf D.7/8, Lifecycle-Tabelle Reconnect-Verhalten dokumentieren, neuer Abschnitt **„USB-Disconnect-Recovery — User-Workflow"** mit konkretem `ros2 control switch_controllers --activate`-Befehl
- [ ] D.7.13 progress.md: D.7-Sektion mit obigen Bullets + Notizen + Post-Review-Tabelle + „Was D.7 nicht macht"

---

## Finale Entscheidungen (vom User am 2026-05-15 freigegeben)

> Hintergrund-Kontext aus dem Freigabe-Gespräch: Der Roboter ist so
> verkabelt, dass **physisches Kabel-Ziehen praktisch ausgeschlossen** ist.
> Realistische Disconnect-Ursachen sind also software-/system-seitig:
> Linux-USB-CDC-Stack-Hänger, udev-Re-Enumerate beim Pi-Boot/Suspend,
> Firmware-Reboot durch Watchdog/Brown-Out, Power-Glitches. **Alle diese
> Fälle führen typischerweise zu einem 100–500 ms-Disconnect mit
> demselben Pfad danach.**

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| 1 | Reconnect-Erfolgs-Test in CI? | **C — nur „Reader bleibt im Backoff + stoppt sauber" in CI testen; Erfolgs-Pfad in Stage H mit echter HW** | Bei seltenen Disconnects lohnt sich der Test-Hook / Symlink-Aufwand nicht. Stage H kann den Erfolgs-Pfad einfach via `echo 1 > /sys/bus/usb/.../authorized` oder Firmware-SIGINT provozieren — kein Kabel-Ziehen nötig |
| 2 | Pfad-Speicherung | **A — `SerialPort::path()`-Getter** | Konzeptionell sauber („SerialPort weiß wo es offen ist"), 3 Zeilen Code; `adopt_fd`-Pfad bleibt `path_=""` was im Reconnect-Loop explizit behandelt wird (ohne Pfad → keine Reconnect-Möglichkeit, `died_=true`) |
| 3 | Backoff-Sequenz | **fix hardcoded** `{100, 200, 500, 1000, 2000, 5000, 5000}` ms | Aus Phase-7-Empirie; bei seltenen Disconnects keine Tuning-Notwendigkeit; URDF-Parameter wäre Phase-10-Material |
| 4 | Logging-Level | **Vorschlag A (laut)** — ERROR (Disconnect erkannt) → WARN (pro Backoff-Iter) → INFO (Reconnect-Erfolg mit Recovery-Befehl) | Seltene Events soll man umso lauter sehen; User WILL Disconnect-Logs sehen weil sie auf System-/Power-/Firmware-Probleme hinweisen |
| 5 | `assembly.clear()` nach Reconnect | **clear** + DEBUG-Log | Mid-frame-Bytes vom alten Stream sind nutzlos; clean restart einfacher und robuster |
| 6 | `port.path_`-Lifetime im reconnect_loop | **explizit `const std::string path = port.path();`** | Wertkopie auf Reader-Stack, unabhängig vom `path_`-Member im SerialPort; defensiver gegen `auto`-Refactoring später |
| Neu | Scope: D.7 voll, minimal, oder skip? | **X — Voller Plan (Backoff-Loop)** | Phase 12 (Pi-Boot/Re-Enumerate) braucht Auto-Recovery, ~80 Zeilen Code günstig; Variante Y (1× Retry) wäre auch ok aber inkonsistent bei längeren Hängern |

**Konsequenzen für die Implementation:**
- `adopt_fd`-Pfad: kein `path_` gesetzt → reconnect_loop muss früh prüfen
  und mit `died_=true` aussteigen statt unendlich open("") zu versuchen.
  Wird in D.7.2-Bullet ergänzt.

### Plan-Korrektur während der Implementation (Lock-Strategie)

**Erste Iteration** (im Plan vorgeschlagen): `exclusive_lock` für die
GESAMTE reconnect_loop-Funktion. Problem: paralleler `write_all` aus
dem controller_manager-Tick blockt für die volle Backoff-Dauer (bis 5 s)
→ Controller-Tick eingefroren.

**Zweite Iteration:** `exclusive_lock` nur momentweise (close + jeder
open()-Versuch). Problem entdeckt beim ersten Testlauf: **EDEADLK
"Resource deadlock avoided"**. Weil `port.path()`, `port.close()` und
`port.open()` jeweils ihre eigenen internen Locks auf demselben mutex
nehmen, und `std::shared_mutex` NICHT rekursiv ist — ein extern
gehaltener exclusive_lock kollidiert mit den intern genommenen Locks.

**Finale Lösung:** KEIN externer Lock im `reconnect_loop`. SerialPort's
interne Locks pro Call (close/open) serialisieren ausreichend:

| Phase | Internes Lock | Effekt auf parallel `write_all` |
|---|---|---|
| `port.path()` | shared (kurz) | blockt µs |
| `port.close()` | unique (kurz) | blockt µs, danach `fd_<0` → `write_all` wirft „port not open" |
| Backoff-Sleep | **kein Lock** | `write_all` kriegt shared, sieht `fd_<0`, wirft sofort — **kein Tick-Freeze** |
| `port.open(path)` | unique (kurz) | blockt µs, bei Erfolg danach normal |

Race-Schutz bleibt erhalten weil der mutex jeden einzelnen Call serialisiert.
Der `SerialPort::exclusive_lock()`-Getter (Public-API von D.1) wird im
reconnect-Pfad gar nicht gebraucht — bleibt für andere Use-Cases im API.

Code-Kommentar in `reconnect_loop` dokumentiert die Strategie + warum
**KEIN** externer exclusive_lock (Self-Deadlock-Hazard).

---

## ~~Was offen ist und User-Feedback braucht~~ (entschieden, siehe oben)

1. **Test 3 (Reconnect-Erfolg) — Option A/B/C?** Ich tendiere zu **C**
   (nur „bleibt im Backoff, stoppt sauber" testen; Erfolg-Verifikation
   in Stage H mit echter HW). Option A wäre sauber aber API-Polution;
   Option B realistisch aber Filesystem-Race. **Empfehlung: C** —
   einfacher, in CI deterministisch, deckt das Risiko ab (das eigentliche
   Risiko ist „Reader hängt unfindbar im Backoff", nicht „open klappt nicht").

2. **`SerialPort::path()`-Getter — OK so?** Alternative wäre `path` als
   Argument an `Servo2040Reader::start(port, path)` mitzugeben. Beide
   sind ~3 Zeilen. SerialPort-intern fühlt sich richtig an (es WEISS
   wo es offen ist).

3. **Backoff-Sequenz fix oder konfigurierbar?** Aktuell hardcoded
   im reconnect_loop. Konfigurierbar (z.B. via URDF-`<param>`) wäre
   Phase-10-Material. Für D.7: fix.

4. **Logging-Level für Backoff-Versuche?** Mein Vorschlag: erstes
   `RCLCPP_ERROR` (Disconnect erkannt), dann `RCLCPP_WARN` pro Backoff-
   Iteration (User sieht „Reader retrying"), bei Erfolg `RCLCPP_INFO`
   mit Recovery-Befehl. Alternative: nur 1× WARN am Start, dann DEBUG
   pro Iter (weniger Log-Spam). **Aktuell: WARN pro Iter** — Bias auf
   sichtbarkeit, weil Disconnect-Events selten und wichtig sind.

5. **`assembly.clear()` nach Reconnect — wichtig?** Ja: alte Bytes-im-Flug
   sind nutzlos und produzieren CRC-Errors. Aber: könnte ein Bug-Risiko
   sein wenn assembly bei reconnect_loop noch mid-frame ist. Plan: clear
   + WARN-Log dass evtl. ein Frame verloren ging.

6. **Lifetime von `port.path_`:** Wenn der Reader während on_cleanup
   stop, geht's via close() → path_ gelöscht. Reader-Thread im
   reconnect_loop hält aber noch eine Kopie des Pfads (lokal, in der
   Funktion). Race? Nein, wir kopieren `const std::string path = port.path();`
   BEVOR wir close() rufen, dann existiert die Kopie lokal. ✓ OK.

---

## Reihenfolge nach Plan-Freigabe

1. ☐ User reviewt diesen Plan + die 6 Fragen → Feedback / Freigabe
2. ☐ Code: D.7.1 SerialPort::path()
3. ☐ Code: D.7.2 reconnect_loop
4. ☐ Code: D.7.3 loop-Integration
5. ☐ Tests D.7.5 + D.7.6
6. ☐ Build + colcon test grün
7. ☐ Kritischer Self-Review (Pflicht-Schritt nach CLAUDE.md §4)
8. ☐ Post-Review-Fixes wenn was auftaucht
9. ☐ Doku-Update (progress.md, README.md, test_commands.md)
10. ☐ Fertig-Meldung für User-Commit
