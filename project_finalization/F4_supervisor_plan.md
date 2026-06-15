# Stage F4 — hexapod_supervisor: Shutdown-Orchestrierung + OS-Guard

> Teil von [Block F](F_systemsteuerung_plan.md). Detail-Plan nach CLAUDE.md §4.
> **Größte Stage.** Neues Paket `hexapod_supervisor` (rclpy, ament_python).
> Voraussetzung: F2 🟢 (`/hexapod/shutdown_request`), F3 🟢 (`/hexapod/shutdown_complete`).
> Test-Anleitung: [`F4_supervisor_test_commands.md`](F4_supervisor_test_commands.md).
> ⚠️ Sicherheits-Anker: [[feedback_no_shutdown_on_dev_host]] — Dev-Host `enjoykin-ubuntu`
> darf den OS-Shutdown NIE ausführen.

---

## 1. Logik-Skizze / Pseudocode

### 1.0 Was F4 NICHT macht (existiert schon)
Hinsetzen, Relay-Aus, Latch erledigt `/hexapod_shutdown` (gait_node) idempotent.
Der Supervisor **orchestriert** nur: Bit erkennen → Service rufen → auf „fertig"
warten → OS runterfahren (guarded). Keine Gait-/Relay-Logik im Supervisor.

### 1.1 Neues Paket (ament_python, Skelett wie `hexapod_teleop`)
```
src/hexapod_supervisor/
├── package.xml              # deps: rclpy, std_msgs, std_srvs
├── setup.py                 # entry_point: shutdown_supervisor
├── setup.cfg · resource/hexapod_supervisor · LICENSE · README.md
├── hexapod_supervisor/
│   ├── __init__.py
│   ├── shutdown_supervisor.py   # der Node
│   └── os_shutdown.py           # isoliertes, guarded OS-Shutdown-Modul
├── launch/supervisor.launch.py  # (Bringup-Einhängung erst F5)
└── test/  test_shutdown_supervisor.py · test_os_shutdown_guard.py
         + test_copyright/flake8/pep257.py
```

### 1.2 Parameter
| Param | Default | Zweck |
|---|---|---|
| `enable_os_shutdown` | **`false`** | Master-Schalter. false → nur „würde herunterfahren"-Log |
| `pi_hostname` | `''` | OS-Shutdown nur wenn `gethostname()==pi_hostname`. Leer → matcht nie (sicher) |
| `shutdown_command` | `'sudo shutdown -h now'` | Tatsächliches Kommando (Mechanismus/Privileg → F5) |
| `shutdown_retry_period` | `1.0` s | Retry-Intervall für `/hexapod_shutdown` (K2) |
| `shutdown_complete_timeout` | `12.0` s | Backstop: kein „complete" → Fallback. F4-L1 maß STANDING→Sit ~7,0 s → 12 s = ~5 s Marge (8 s war zu knapp) |
| `force_relay_off_on_timeout` | `true` | Im Backstop zusätzlich `/hexapod_relay_set false` feuern |

### 1.3 Schnittstellen (QoS-Vertrag aus F2/F3: reliable + transient_local)
- Sub `/hexapod/shutdown_request` (Bool, latched) — Auslöser
- Sub `/hexapod/shutdown_complete` (Bool, latched) — „sitzt + Relay aus"
- Client `/hexapod_shutdown` (Trigger) — startet Hinsetz-/Relay-Sequenz
- Client `/hexapod_relay_set` (SetBool) — nur Backstop-Fallback

### 1.4 State-Machine
```
IDLE ──(request False→True, armed)──► SHUTTING_DOWN ──► DONE
```
**Arm/Flanke (E3 Defense-in-Depth):**
```
_on_request(msg):
    if _last_request is None:        # erster (gelatchter) Wert = Baseline
        _last_request = msg.data     # KEIN Trigger, auch wenn True (Node-Restart-Schutz)
        return
    if (not _last_request) and msg.data and state == IDLE:
        _begin_shutdown()            # echte False→True-Flanke
    _last_request = msg.data
```
**SHUTTING_DOWN:**
```
_begin_shutdown():
    state = SHUTTING_DOWN
    _service_ok = False
    start retry_timer(shutdown_retry_period) -> _try_shutdown_service()

_try_shutdown_service():               # K2: lehnt im WALKING ab → retry
    if _service_ok or call pending: return
    future = shutdown_client.call_async(Trigger.Request())
    on done: if resp.success: _service_ok = True
                              cancel retry_timer
                              start backstop_timer(shutdown_complete_timeout)
             else: (bleibt, retry feuert erneut)

_on_complete(msg):                     # Happy-Path
    if state==SHUTTING_DOWN and _service_ok and msg.data:
        _finish('complete')

backstop_timer fires:                  # F4-Policy: SD-Schutz gewinnt
    if force_relay_off_on_timeout: relay_client.call_async(SetBool(False))
    _finish('timeout')

_finish(reason):
    cancel timers
    ok, why = os_shutdown.guarded_shutdown(enable_os_shutdown, pi_hostname,
                                            shutdown_command, logger)
    log(reason, ok, why)
    state = DONE
```

### 1.5 `os_shutdown.py` (isoliert, der gefährliche Teil)
```python
def guarded_shutdown(enable, pi_hostname, command, logger):
    host = socket.gethostname()
    if host == 'enjoykin-ubuntu':            # HARTER Block, unabhängig von Params
        logger.warn(f'OS-Shutdown auf Dev-Host {host} BLOCKIERT'); return (False, 'dev-host')
    if not enable:
        logger.info('enable_os_shutdown=false → würde jetzt herunterfahren'); return (False, 'disabled')
    if host != pi_hostname:
        logger.warn(f'hostname {host} != pi_hostname {pi_hostname} → kein Shutdown'); return (False, 'host-mismatch')
    logger.warn(f'Führe OS-Shutdown aus: {command}')
    subprocess.run(shlex.split(command), check=False)
    return (True, 'executed')
```
**Drei Schichten:** (1) harter `enjoykin-ubuntu`-Block, (2) `enable_os_shutdown`,
(3) Hostname-Match. Auf Dev nie ausgeführt; auf Pi erst spät scharf.

### Begründung
- **Subscriptions latched + reliable+transient_local:** [[project_latched_topic_qos_reliable]].
- **Baseline-Arm (kein Trigger auf Startup-True):** Supervisor-Neustart bei
  gelatchtem True (FW noch armed) löst NICHT versehentlich Shutdown aus (E3).
- **Retry statt Mid-Walk-Force (K2):** `/hexapod_shutdown` lehnt im WALKING ab →
  retry bis STANDING/SAT. Kein Roboter-Drop im Lauf.
- **Backstop nur als Notnetz (E5):** Happy-Path = `shutdown_complete`-Flag;
  Timeout nur falls Hinsetzen scheitert (F4-Policy: trotzdem stromlos + runterfahren).
- **os_shutdown isoliert + 3-fach-Guard:** der einzige Ort mit `subprocess`;
  trivial als No-Op auf Dev, dev-host hart geblockt.

---

## 2. Tests-Liste mit Begründung

**`test_os_shutdown_guard.py` (Kern-Sicherheit, mock `socket`+`subprocess`):**
| ID | Test | Erwartung |
|---|---|---|
| F4-G1 | host=`enjoykin-ubuntu`, enable=True, match | `(False,'dev-host')`, subprocess NICHT aufgerufen |
| F4-G2 | enable=False (anderer Host) | `(False,'disabled')`, kein subprocess |
| F4-G3 | enable=True, host≠pi_hostname | `(False,'host-mismatch')`, kein subprocess |
| F4-G4 | enable=True, host==pi_hostname (gemockt, ≠dev) | `(True,'executed')`, subprocess mit `command` aufgerufen |

**`test_shutdown_supervisor.py` (Node direkt, mock Clients + os_shutdown):**
| ID | Test | Erwartung |
|---|---|---|
| F4-S1 | Startup-Wert True (Baseline) | KEIN `_begin_shutdown` |
| F4-S2 | False→True-Flanke | `_begin_shutdown`, state=SHUTTING_DOWN |
| F4-S3 | `/hexapod_shutdown` resp.success=False (WALKING) | bleibt SHUTTING_DOWN, retry feuert erneut |
| F4-S4 | resp.success=True → `shutdown_complete`=True | `guarded_shutdown` 1× aufgerufen, state=DONE |
| F4-S5 | resp.success=True, Backstop-Timeout (kein complete) | `relay_set(False)` + `guarded_shutdown` aufgerufen |
| F4-S6 | True→False→True (Re-Trigger nach Storno) | erneut `_begin_shutdown` |

**Bewusst NICHT getestet (deferred):**
- Echter `subprocess`-Shutdown → **nie** im Test ausgeführt (gemockt); real erst F5/Pi.
- End-to-End Schalter→OS-Halt → **F5** (Pi, Guard scharf).
- polkit/sudoers-Privileg → **F5** Deployment.

---

## 3. Progress-Checkliste (Done-Vertrag — 1:1 ins Progress-File)

```
- [ ] F4.1  Paket hexapod_supervisor angelegt (package.xml/setup.py/cfg/resource)
- [ ] F4.2  os_shutdown.py: guarded_shutdown (3-Schicht-Guard, dev-host hart)
- [ ] F4.3  shutdown_supervisor.py: Params + Subs + Clients + State-Machine
- [ ] F4.4  Arm/Flanke (Baseline, kein Startup-True-Trigger)
- [ ] F4.5  Retry /hexapod_shutdown (K2) + Backstop-Timeout + Fallback-Relay-Off
- [ ] F4.6  guarded OS-Shutdown am Ende (Dry-Run auf Dev)
- [ ] F4.7  Tests F4-G1..G4 + F4-S1..S6
- [ ] F4.8  colcon build + test + flake8/pep257 grün
- [ ] F4.9  Dev-Smoke: Node läuft, Flip → „würde herunterfahren"-Log (Guard aus)
- [ ] F4.10 Self-Review-Tabelle (CLAUDE.md §4)
```

---

## 4. Entscheidungen (User-Review erledigt, vor Code-Beginn)

Alle sechs vom User bestätigt — keine offenen Punkte mehr:

1. **Backstop-Timeout** `shutdown_complete_timeout` = **8 s** (sit 5 s + Marge).
2. **Backstop-Aktion:** zusätzlich `/hexapod_relay_set false` feuern
   (`force_relay_off_on_timeout=true`). *Verworfen:* nur auf Watchdog verlassen —
   explizit ist sauberer (Servos sicher stromlos).
3. **Endlos-Retry bei Dauer-WALKING** (K2-strikt): kein Roboter-Drop im Lauf; User
   stoppt Fahren → STANDING → Shutdown läuft. *Verworfen:* globaler Max-Wait mit
   Force-Fallback (würde laufenden Roboter fallen lassen).
4. **`shutdown_command`** Default `'sudo shutdown -h now'` als Platzhalter; endgültiger
   Mechanismus (sudoers vs. `systemctl poweroff`/polkit) in **F5**.
5. **`pi_hostname`** Default leer (matcht nie → sicher); echten Pi-Hostnamen liefert
   der User bei F5-Scharfschaltung.
6. **Stage als ein Plan**, Checkliste = Abarbeitungs-Reihenfolge. *Verworfen:*
   F4.1/F4.2-Split.
