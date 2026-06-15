# Stage F5 — Integration + Pi-Deployment

> Teil von [Block F](F_systemsteuerung_plan.md), **letzte Stage**. Detail-Plan nach
> CLAUDE.md §4. Voraussetzung: F4 🟢.
> ⚠️ [[feedback_no_shutdown_on_dev_host]] — Dev (`enjoykin-ubutu`) fährt NIE runter.

**Leitidee (User):** *Eine* Config, *ein* Launch, **überall identisch** — der
Host-Guard entscheidet, ob wirklich heruntergefahren wird. Am Pi ist im Idealfall
nur **ein Wert** (`pi_hostname`) nachzutragen → plug-and-play.

Aufgeteilt in **F5a (jetzt, Dev — alles hier Testbare)** und **F5b (später, Pi —
vorbereitet als Schritt-Checkliste)**.

---

## 1. Logik-Skizze

### F5a — Integration (Dev, jetzt)

**1.1 Params-File `hexapod_supervisor/config/supervisor.yaml`**
```yaml
shutdown_supervisor:
  ros__parameters:
    enable_os_shutdown: true       # (offener Punkt §4.1) master arm
    pi_hostname: ''                 # LEER → matcht nie → Dev sicher; am Pi eintragen
    shutdown_command: 'sudo shutdown -h now'
    shutdown_retry_period: 1.0
    shutdown_complete_timeout: 12.0
    force_relay_off_on_timeout: true
```
Sicherheit auf Dev trotz `enable_os_shutdown: true`: `enjoykin-ubutu` ≠ `''`
(host-mismatch) **und** `DEV_HOSTS`-Hard-Block → doppelt blockiert.

**1.2 `supervisor.launch.py`** lädt die yaml; Launch-Args `enable_os_shutdown` /
`pi_hostname` überschreiben sie weiterhin (für Ad-hoc-Tests).

**1.3 `setup.py`** installiert `config/*.yaml` (data_files, wie hexapod_teleop).

**1.4 Einhängung in `real.launch.py`** (Basis-Bringup, kommt überall hoch):
`IncludeLaunchDescription(supervisor.launch.py)` + neuer Arg `with_supervisor`
(Default `true`; `false` für reine Sim/Unit-Arbeit ohne Supervisor). Der Supervisor
retryt `/hexapod_shutdown`, bis gait läuft → Start-Reihenfolge egal.

**Begründung:** automatischer Start mit der Basis = plug-and-play; eine Config
überall; Guard differenziert Host. `with_supervisor`-Off-Schalter für Dev-Sessions,
wo man ihn nicht will.

### F5b — Pi-Deployment (später, vorbereitet)
Reine Schritt-Checkliste (nicht jetzt ausführbar — Pi hat noch kein ROS2, Block D1):
1. **ROS2 + Workspace am Pi** (Block D1 Voraussetzung): Branch `leg_changes`,
   `colcon build` (ohne Gazebo).
2. **`pi_hostname` eintragen:** `hostname` am Pi ausführen → Wert in `supervisor.yaml`.
3. **Shutdown-Privileg** (eine der Optionen, §4.3):
   - sudoers NOPASSWD für genau das Kommando:
     `pi ALL=(root) NOPASSWD: /sbin/shutdown` in `/etc/sudoers.d/hexapod-shutdown`.
4. **End-to-End** (aufgebockt → Boden): physischer Schalter ≥3 s → hinsetzen →
   Relay-Aus → `shutdown finished (reason=complete, performed=True, guard=executed)`
   → Pi fährt sauber runter (SD intakt).

---

## 2. Tests-Liste mit Begründung

**F5a (Dev):**
| ID | Test | Erwartung |
|---|---|---|
| F5a-U1 | `colcon build` (hexapod_supervisor + hexapod_bringup) | grün, yaml installiert |
| F5a-L1 | `real.launch.py` starten | Supervisor-Node kommt automatisch mit hoch (Log „shutdown_supervisor up", `pi_hostname=''`) |
| F5a-L2 | Flip false→true (Schalter/topic pub), gait-Stack läuft | `guard=dev-host`, `performed=False` → Dev fährt NICHT runter |
| F5a-L3 | `real.launch.py with_supervisor:=false` | Supervisor startet NICHT (Off-Schalter) |

**Bewusst NICHT jetzt (F5b, Pi):** echter OS-Shutdown, polkit/sudoers, physischer
Schalter am Pi — erst wenn der Pi ROS2-ready ist (Block D1). Als Checkliste vorbereitet.

---

## 3. Progress-Checkliste (Done-Vertrag)

```
F5a (Dev, jetzt):
- [ ] F5a.1  config/supervisor.yaml (Params, enable=true + pi_hostname leer)
- [ ] F5a.2  supervisor.launch.py lädt yaml (+ Arg-Overrides)
- [ ] F5a.3  setup.py installiert config/*.yaml
- [ ] F5a.4  real.launch.py: with_supervisor-Arg + Include supervisor.launch.py
- [ ] F5a.5  colcon build + bestehende Tests grün
- [ ] F5a.6  F5a-L1/L2/L3 (Auto-Start, guard=dev-host, Off-Schalter) — User
- [ ] F5a.7  Self-Review

F5b (Pi, später — vorbereitet, an Block D1 gekoppelt):
- [ ] F5b.1  pi_hostname am Pi eintragen
- [ ] F5b.2  Shutdown-Privileg (sudoers/polkit) eingerichtet
- [ ] F5b.3  Branch leg_changes + colcon build am Pi
- [ ] F5b.4  End-to-End physischer Schalter → Pi fährt sauber runter
```

---

## 4. Entscheidungen (User-Review erledigt, vor Code-Beginn)

Alle vier bestätigt:

1. **`enable_os_shutdown: true`** in der yaml. Dev bleibt doppelt geschützt
   (host-mismatch gegen leeren `pi_hostname` + harter `DEV_HOSTS`-Block). Am Pi ist
   nur **`pi_hostname` = 1 Wert** nachzutragen. *Verworfen:* `false`-Default.
2. **Auto-Start, kein manueller Start:** Supervisor wird in `real.launch.py`
   eingehängt + `with_supervisor`-Arg (Default `true`, abschaltbar für Sim/Dev).
3. **Shutdown-Mechanismus** (sudoers NOPASSWD vs. polkit) endgültig bei **F5b am Pi**.
4. **Pi-Hostname** erst bei F5b bekannt; `pi_hostname` bleibt jetzt leer.
