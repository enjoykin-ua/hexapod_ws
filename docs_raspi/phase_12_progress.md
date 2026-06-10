# Phase 12 — Progress-Tracker

**Phase:** Pi-Plattform & Portierung (Block D1)
**Plan:** [phase_12_pi_platform.md](phase_12_pi_platform.md)
**Deployment-Workflow:** [dev_workflow_desktop_to_pi.md](dev_workflow_desktop_to_pi.md)
**Provisioning-Skript:** [`tools/provision_pi.sh`](../tools/provision_pi.sh)
**Status:** ✅ Kern abgeschlossen — Plattform steht, Stack baut + läuft
(Loopback) am Pi. D/G.2/F.3 bewusst deferiert. Offen nur noch: Git-Commit
+ Tag `phase-12-done` (User). Echter HW-Start = Phase 13.

> Pro erledigtem Bullet `[ ]` → `[x]` umstellen, **nicht batchen**
> (Memory `feedback_phase_progress_tracking.md`).

> **Reihenfolge (mit User abgestimmt):**
> 1. Phase 12 **A–F** zuerst — Pi rein in Software aufsetzen (OS/SSH/ROS2/
>    Build/DDS/Loopback), ohne HW, ohne OLED/Button. Risikofreies Fundament.
> 2. Danach HW an den Pi (3 Starts via tmux, aufgebockt) — eigentlich schon
>    Phase-13-Gebiet, der erste echte Start gehoert aber hierher.
> 3. **OLED + GPIO-Button + systemd** kommen NICHT in diese Phase, sondern
>    in ein **eigenes D4/D5-Doc** (Autonom/untethered). Phase 12 bleibt schlank.

---

## Design-Entscheidungen vor Stufe A

### A. Provisioning als Code statt manueller Einrichtung — Final

- **Final:** Idempotentes Bash-Skript [`tools/provision_pi.sh`](../tools/provision_pi.sh),
  das alle System-Ebenen-Einstellungen haelt, die NICHT im Workspace-Git
  liegen (APT-Pakete, ROS-Repo, Locale, ~/.bashrc-Env, udev). Workspace +
  Kalibrierung sind bereits ueber Git reproduzierbar
  ([servo_mapping.yaml](../src/hexapod_hardware/config/servo_mapping.yaml) u. a.
  sind getrackt).
- **Verworfen:** Ansible (fuer *einen* Pi Overkill, Tooling-Overhead),
  reines `dd`-Image (Black-Box, veraltet, keine Config-as-Code).
- **Optional/ergaenzend:** `dd`-Image des fertigen Systems als *schnellster*
  Recovery-Pfad — aber das Skript bleibt Source of Truth.
- **Arbeitsweise:** Skript wird in Stufen B/C/E **mitwachsend** befuellt
  statt vorab "fertig" geschrieben → am Phasenende genau einmal real
  erprobt. Stellen mit Verifikationsbedarf am echten Pi: `# VERIFY@PI`.
- **Recovery-Vertrag (User-Wunsch):** Skript automatisiert was es kann und
  gibt am Ende eine **MANUELLE-SCHRITTE-Liste** aus fuer alles, was es nicht
  wissen kann (ROS_DOMAIN_ID-Abgleich, Servo2040-VID:PID, PS4-BT-Re-Pairing,
  WLAN/SSH-Key aus dem Imager).
- **Schutz:** Architektur-Guard (`aarch64`) verhindert versehentliche
  Ausfuehrung am x86-Desktop (CLAUDE.md §5).

### B. 3 Starts bleiben getrennt, via tmux — Final

- **Final:** Die 3 Launches ([real.launch.py](../src/hexapod_bringup/launch/real.launch.py)
  → [gait.launch.py](../src/hexapod_gait/launch/gait.launch.py) →
  [joy_teleop.launch.py](../src/hexapod_teleop/launch/joy_teleop.launch.py))
  bleiben in Phase 12 getrennt und werden via `tmux`-Panes ueber SSH
  gefahren. Abhaengigkeit: real (JTCs active) → gait → teleop.
- **Verschoben:** Ein kombiniertes `autonomous.launch.py` (3 Starts
  gebuendelt) gehoert zum Autonom-Betrieb (D4/D5), nicht hierher.
- **Falle:** `gait.launch.py` mit `use_sim_time:=false` starten (Default ist
  bereits false, aber explizit dokumentieren — Memory
  `project_phase13_gait_launch_sim_time_default.md`).

---

## Stufen-Checkliste

### Stufe A — OS-Image flashen (operativ, User)

- [ ] A.1 Storage gewaehlt (USB-3-SSD bevorzugt, sonst A2-SD)
- [ ] A.2 Ubuntu Server 24.04 LTS arm64 via Imager geflasht (Hostname
      `hexapod-pi`, SSH-Pubkey, WLAN, Locale gesetzt)
- [x] A.3 Erstbootup ok, `ssh pi@hexapod-pi` erfolgreich
      (Pi=hexapod-pi @ 192.168.2.65, User=`pi`; `.local`/mDNS inaktiv → reiner
      Name via Router-DNS; Desktop-Hostname=`enjoykin-ubutu`)
- [ ] A-DK: `uname -a` zeigt aarch64 / 24.04 LTS

### Stufe B — SSH-Workflow & Basis (teils Skript)

- [x] B.0 APT-Pocket `noble-updates` aktiviert (Pflicht-Vorschritt; Image
      kam nur mit `noble`+`noble-security`, sonst ROS-`-dev`-Versionskonflikte)
- [x] B.1 `~/.ssh/config`-Alias `hexapod-pi` am Desktop funktioniert
      (Key-Auth, `ssh hexapod-pi` passwortlos)
- [ ] B.2 Basis-Tools via `provision_pi.sh` (vim/git/curl/net-tools/tmux/htop)
- [ ] B.3 Locale + universe + ROS-Repo via `provision_pi.sh`, `apt update` sauber
- [ ] B-DK: SSH-Alias + Basis-Tools + ROS-Repo stehen

### Stufe C — ROS2 Jazzy (Skript)

- [x] C.1 ROS-`ros-base`-Paketliste via `provision_pi.sh` installiert
      (kein desktop/ros-gz/gz-ros2-control)
- [x] C.2 ~/.bashrc-Env via Skript (source ros, ROS_DOMAIN_ID, RMW)
- [x] C.3 `ROS_DOMAIN_ID=42` mit Desktop abgeglichen (Desktop verifiziert)
- [x] C-DK: ROS funktioniert (colcon build nutzt es), `ros2 pkg list` zeigt Pakete

### Stufe D — DDS-Konnektivität Desktop ↔ Pi  ⏸️ DEFERIERT

> **Bewusst zurückgestellt (User-Entscheidung).** Für den autonomen Pi
> (Stack läuft komplett am Pi, Teleop via BT) NICHT nötig — Desktop und Pi
> müssen keinen gemeinsamen ROS-Graph bilden. Risiko bei gleicher
> `ROS_DOMAIN_ID`: Desktop-Sim + Pi-Roboter würden ungewollt zusammenreden.
> **Nachholen**, wenn RViz-Remote gewünscht (User-Plan: Desktop + HW via
> Pi + RViz später). Voraussetzung (gleiche Domain-ID) steht bereits.

- [ ] D.1–D.3 / D-DK — deferiert (optionaler Remote-Debugging-Komfort)

### Stufe E — Workspace klonen + bauen

- [x] E.1 `git clone` nach `~/hexapod_ws` (HTTPS)
- [x] E.2 `hexapod_gazebo/COLCON_IGNORE` via Skript gesetzt (beim Build übersprungen)
- [x] E.3 `rosdep install` + `colcon build --symlink-install` grün (8 Pakete, 52.7s)
- [x] E.4 `gait_node` startet ohne Crash (gait.launch.py lief: „Cartesian-Standup gestartet")
- [x] E-DK: Workspace baut grün (ausser hexapod_gazebo), keine fehlenden Deps

### Stufe F — Loopback-Test + 3 Starts via tmux

- [x] F.1 `real.launch.py loopback_mode:=true` auf Pi: Stack startet
- [x] F.2 `ros2 control list_controllers` = 1× JSB + 6× JTC active (verifiziert)
- [ ] F.3 `/joint_states`-Echo — nicht explizit geprüft (Controller active +
      gait publisht impliziert Datenfluss); unkritisch, nachholbar
- [x] F.4 Multi-Launch erprobt: `real` + `gait` parallel active (separate
      SSH-Terminals statt tmux-Splits); `teleop` + tmux-Splits offen, aber
      Workflow im Kern bestätigt
- [x] F-DK: Stack auf Pi ohne echte HW grün (real + gait parallel active)

### Stufe G — Deployment-Workflow

- [x] G.1 Git-Weg erprobt (clone + Build am Pi)
- [ ] G.2 rsync-Probe — deferiert (nice-to-have für schnelle Iteration)
- [x] G-DK: `dev_workflow_desktop_to_pi.md` final

### Stufe H — Shutdown-Disziplin

- [x] H.1 Shutdown-Prozedur dokumentiert (`sudo shutdown -h now`, LED, dann Strom)
- [x] H.2 `hexapod-shutdown`-Alias dokumentiert
- [x] H-DK: sicheres Runterfahren via SSH erprobt (User hat Pi so ausgeschaltet)

### Stufe I — Phase-Abschluss

- [x] I.1 `provision_pi.sh` real erprobt; `VERIFY@PI` aufgelöst: noble-updates,
      `ROS_DOMAIN_ID=42` (= Desktop), Servo2040 VID `2e8a` → `/dev/servo2040`
- [x] I.2 Recovery-Pfad dokumentiert (Imager → clone → provision → build)
- [ ] I.3 Git-Commit + Tag `phase-12-done` — **User** (macht Commits selbst)
- [x] I.4 `PHASE.md` aktualisiert
- [x] I.5 Retrospektive (siehe unten)

---

## Post-Review (Self-Review zum Phasen-Abschluss)

| Punkt | Status |
|---|---|
| OS/SSH/ROS2/Build/Loopback alle grün | OK |
| `provision_pi.sh` idempotent + arm64-Guard + noble-updates-Check + skip-keys | OK |
| Reproduzierbarkeit (Recovery-Pfad dokumentiert, Configs/Cal im Git) | OK |
| Servo2040 udev `/dev/servo2040` verifiziert (VID 2e8a) | OK |
| Stufe D (DDS/RViz) nicht getestet | 🟢 später (bewusst, für autonom nicht nötig) |
| F.3 joint_states-Echo nicht explizit geprüft | 🟢 später (unkritisch) |
| G.2 rsync-Probe nicht durchgespielt | 🟢 später (Git-Weg erprobt) |
| `apt upgrade` nicht im Skript (war §5-Genehmigung nötig) | 🟡 vormerken: ggf. bei nächstem frischen Pi prüfen, ob nach noble-updates noch nötig |
| Erster echter HW-Start (`loopback_mode:=false`) | 🔴 NICHT in Phase 12 — Phase 13, aufgebockt (§9) + Plan-Doku |

---

## Retrospektive

**Lief gut:** Provisioning-as-Code-Ansatz hat sich bewährt — die zwei
unerwarteten Stolpersteine (`noble-updates` fehlte im Image; `rosdep`
ignoriert `COLCON_IGNORE` → zog Gazebo-Bridge) wurden im Skript fest
abgefangen (Pocket-Check + `--skip-keys`), sodass der nächste frische Pi
sie nicht mehr hat. udev-`/dev/servo2040` + ROS_DOMAIN_ID-Abgleich sauber
verifiziert.

**Hat länger gedauert / Reibung:** SSH-Login (falscher User `enjoykin`
statt `pi`), SSH-Timeout killte das Provisioning mitten im dpkg (→ tmux-
Empfehlung), `apt upgrade` als §5-Genehmigung. Alles in Doku/Skript
abgefangen.

**Offen / nächster Schritt:** Der **erste echte Hardware-Start am Pi**
(`loopback_mode:=false serial_port:=/dev/servo2040`) ist bewusst NICHT
Teil von Phase 12 — er gehört nach Phase 13: aufgebockt (§9, Kill-Switch,
langsam), Power-On-Zentrier-Sequenz beachten, eigene Plan-Doku zuerst.
Außerdem deferiert: D (DDS/RViz-Remote), G.2 (rsync), F.3 (joint_states-Echo).
