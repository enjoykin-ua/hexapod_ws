# Phase 12 — Progress-Tracker

**Phase:** Pi-Plattform & Portierung (Block D1)
**Plan:** [phase_12_pi_platform.md](phase_12_pi_platform.md)
**Deployment-Workflow:** [dev_workflow_desktop_to_pi.md](dev_workflow_desktop_to_pi.md)
**Provisioning-Skript:** [`tools/provision_pi.sh`](../tools/provision_pi.sh)
**Status:** 🟡 in Arbeit (Vorbereitung Doku/Skript)

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

- [ ] B.1 `~/.ssh/config`-Alias `hexapod-pi` am Desktop funktioniert
- [ ] B.2 Basis-Tools via `provision_pi.sh` (vim/git/curl/net-tools/tmux/htop)
- [ ] B.3 Locale + universe + ROS-Repo via `provision_pi.sh`, `apt update` sauber
- [ ] B-DK: SSH-Alias + Basis-Tools + ROS-Repo stehen

### Stufe C — ROS2 Jazzy (Skript)

- [ ] C.1 ROS-`ros-base`-Paketliste via `provision_pi.sh` installiert
      (kein desktop/ros-gz/gz-ros2-control)
- [ ] C.2 ~/.bashrc-Env via Skript (source ros, ROS_DOMAIN_ID, RMW)
- [ ] C.3 `ROS_DOMAIN_ID` mit Desktop abgeglichen (MANUELLER Schritt)
- [ ] C-DK: `ros2 --help`, `ros2 pkg list`, `echo $ROS_DOMAIN_ID` == Desktop

### Stufe D — DDS-Konnektivität Desktop ↔ Pi

- [ ] D.1 Talker/Listener Desktop → Pi grün
- [ ] D.2 Talker/Listener Pi → Desktop grün
- [ ] D.3 `ros2 topic list` zeigt Topics beider Seiten
- [ ] D-DK: bidirektionale DDS-Kommunikation bestaetigt

### Stufe E — Workspace klonen + bauen

- [ ] E.1 `git clone` nach `~/hexapod_ws`
- [ ] E.2 `hexapod_gazebo/COLCON_IGNORE` via Skript gesetzt
- [ ] E.3 `rosdep install` + `colcon build --symlink-install` grün
- [ ] E.4 `ros2 run hexapod_gait gait_node` startet ohne Crash
- [ ] E-DK: Workspace baut grün (ausser hexapod_gazebo), keine fehlenden Deps

### Stufe F — Loopback-Test + 3 Starts via tmux

- [ ] F.1 `real.launch.py loopback_mode:=true` auf Pi: alle Controller active
- [ ] F.2 `ros2 control list_controllers` = 1× JSB + 6× JTC active
- [ ] F.3 `/joint_states` publisht (18 Joints, loopback echo)
- [ ] F.4 3-Starts-tmux-Ablauf durchgespielt (real → gait → teleop,
      `use_sim_time:=false`)
- [ ] F-DK: Stack auf Pi ohne echte HW grün, tmux-Workflow steht

### Stufe G — Deployment-Workflow

- [ ] G.1 Workflow-Probe mit Git durchgespielt
- [ ] G.2 Workflow-Probe mit rsync durchgespielt
- [ ] G-DK: `dev_workflow_desktop_to_pi.md` final

### Stufe H — Shutdown-Disziplin

- [ ] H.1 Shutdown-Prozedur dokumentiert (`sudo shutdown -h now`, LED, dann Strom)
- [ ] H.2 `hexapod-shutdown`-Alias am Desktop
- [ ] H-DK: sicheres Hoch-/Runterfahren ohne physischen Zugang via SSH

### Stufe I — Phase-Abschluss

- [ ] I.1 `provision_pi.sh` einmal vollstaendig real erprobt (alle `VERIFY@PI` aufgeloest)
- [ ] I.2 Recovery-Pfad dokumentiert (Imager → clone → provision → build)
- [ ] I.3 Git-Commit + Tag `phase-12-done`
- [ ] I.4 `PHASE.md` aktualisiert (naechster Block)
- [ ] I.5 Retrospektive in diesem File

---

## Post-Review (pro Stufe nach Implementierung)

> Tabelle pro Stufe: Punkt / Status (OK / 🔴 fixen / 🟡 vormerken / 🟢 später).
> Wird beim Self-Review nach jeder Stufe befuellt (CLAUDE.md §4).

_(noch leer — wird ab Stufe A befuellt)_
